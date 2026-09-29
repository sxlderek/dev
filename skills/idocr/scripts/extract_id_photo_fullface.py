#!/usr/bin/env python3
"""End-to-end offline ID-photo extraction with:

1) Optional card flattening (perspective transform)
2) Photo rectangle detection (edge-based)
3) Aggressive padding retries
4) Full-face verification using MediaPipe FaceMesh (mouth + chin + forehead margins)

This is meant to be robust across many ID layouts by using verification rather than templates.

Usage:
  scripts/run_fullface_extract.sh --input in.jpg --output out.jpg
"""

import argparse
import os
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image

import mediapipe as mp

MOUTH_INDICES = [13, 14, 78, 308]
CHIN_INDEX = 152
FOREHEAD_INDEX = 10


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts, out_w):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))

    scale = out_w / float(maxWidth)
    out_h = int(round(maxHeight * scale))

    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype="float32",
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (out_w, out_h))


def flatten_card_if_possible(bgr, out_w=1100):
    orig = bgr
    h, w = bgr.shape[:2]
    scale = 900.0 / max(h, w)
    img = bgr
    if scale < 1.0:
        img = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, None, iterations=2)
    edges = cv2.erode(edges, None, iterations=1)

    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)

    card = None
    for c in cnts[:15]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            card = approx.reshape(4, 2).astype("float32")
            break

    if card is None:
        return orig, False

    if scale < 1.0:
        card = card / scale

    return four_point_transform(orig, card, out_w), True


def find_photo_rect(bgr, right_start=0.45):
    h, w = bgr.shape[:2]
    x0 = int(w * right_start)
    roi = bgr[:, x0:w]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
    edges = cv2.erode(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        ar = ww / float(hh + 1e-6)
        if area < 0.006 * roi.shape[0] * roi.shape[1]:
            continue
        if ar < 0.45 or ar > 1.10:
            continue
        boxes.append((area, x, y, ww, hh))

    if not boxes:
        return None

    boxes.sort(reverse=True)
    _, x, y, ww, hh = boxes[0]
    return (x + x0, y, x + x0 + ww, y + hh)


def facemesh_ok(bgr):
    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as fm:
        res = fm.process(rgb)
    if not res.multi_face_landmarks:
        return False, {"reason": "no_face"}

    lm = res.multi_face_landmarks[0].landmark

    def ypx(i):
        return lm[i].y * h

    mouth_ys = [ypx(i) for i in MOUTH_INDICES]
    chin_y = ypx(CHIN_INDEX)
    forehead_y = ypx(FOREHEAD_INDEX)

    mouth_bottom_margin = (h - max(mouth_ys)) / h
    chin_bottom_margin = (h - chin_y) / h
    forehead_top_margin = forehead_y / h

    ok = (mouth_bottom_margin >= 0.08) and (chin_bottom_margin >= 0.05) and (forehead_top_margin >= 0.05)
    return ok, {
        "mouth_bottom_margin": float(round(mouth_bottom_margin, 3)),
        "chin_bottom_margin": float(round(chin_bottom_margin, 3)),
        "forehead_top_margin": float(round(forehead_top_margin, 3)),
    }


def crop(bgr, box):
    x1, y1, x2, y2 = box
    return bgr[y1:y2, x1:x2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--flatten", action="store_true", default=True)
    ap.add_argument("--flat-width", type=int, default=1100)
    args = ap.parse_args()

    bgr = cv2.imread(args.input)
    if bgr is None:
        print("ERROR: cannot read input", file=sys.stderr)
        return 1

    if args.flatten:
        bgr2, did = flatten_card_if_possible(bgr, out_w=args.flat_width)
        bgr = bgr2

    rect = find_photo_rect(bgr)
    if rect is None:
        print("ERROR: no photo rectangle", file=sys.stderr)
        return 2

    x1, y1, x2, y2 = rect
    ww = x2 - x1
    hh = y2 - y1

    # aggressive padding ladder, with extra bottom bias
    pad_factors = [0.20, 0.35, 0.50, 0.70]
    for f in pad_factors:
        pad_x = int(round(f * ww))
        pad_t = int(round(0.25 * f * hh))
        pad_b = int(round(0.90 * f * hh))
        nx1 = clamp(x1 - pad_x, 0, bgr.shape[1] - 1)
        ny1 = clamp(y1 - pad_t, 0, bgr.shape[0] - 1)
        nx2 = clamp(x2 + pad_x, nx1 + 2, bgr.shape[1])
        ny2 = clamp(y2 + pad_b, ny1 + 2, bgr.shape[0])

        c = crop(bgr, (nx1, ny1, nx2, ny2))
        ok, diag = facemesh_ok(c)
        if ok:
            cv2.imwrite(args.output, c)
            print("OK", {"rect": list(rect), "crop": [nx1, ny1, nx2, ny2], "diag": diag, "pad_factor": f})
            return 0

    print("ERROR: could not verify full face", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
