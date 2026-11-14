#!/usr/bin/env python3
"""Crop the *ID photo rectangle* (the portrait photo area on the card).

Approach:
1) Detect the largest face using OpenCV DNN.
2) Search near that face for a rectangular contour likely to be the photo boundary.
3) Crop that rectangle and upscale to at least --min-width while preserving aspect ratio.

This is intentionally different from a headshot crop: the goal is the full ID photo area,
not "hair-to-chin".

Usage:
  python3 crop_id_photo_opencv.py --input in.jpg --output out.jpg --min-width 500

Exit codes:
  0 success
  2 no face detected
  3 no photo-rectangle detected (falls back to a conservative face-based crop unless --no-fallback)
"""

import argparse
import sys

import cv2
from PIL import Image


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def detect_largest_face_box_dnn(image_bgr, prototxt: str, weights: str, conf: float):
    """Return (x1,y1,x2,y2,score) in px, or None."""
    net = cv2.dnn.readNetFromCaffe(prototxt, weights)
    h, w = image_bgr.shape[:2]

    blob = cv2.dnn.blobFromImage(
        cv2.resize(image_bgr, (300, 300)),
        1.0,
        (300, 300),
        (104.0, 177.0, 123.0),
    )
    net.setInput(blob)
    det = net.forward()

    best = None
    best_area = 0

    for i in range(det.shape[2]):
        score = float(det[0, 0, i, 2])
        if score < conf:
            continue

        x1 = int(det[0, 0, i, 3] * w)
        y1 = int(det[0, 0, i, 4] * h)
        x2 = int(det[0, 0, i, 5] * w)
        y2 = int(det[0, 0, i, 6] * h)

        x1 = clamp(x1, 0, w - 1)
        y1 = clamp(y1, 0, h - 1)
        x2 = clamp(x2, x1 + 1, w)
        y2 = clamp(y2, y1 + 1, h)

        area = (x2 - x1) * (y2 - y1)
        if area > best_area:
            best_area = area
            best = (x1, y1, x2, y2, score)

    return best


def find_photo_rectangle_near_face(image_bgr, face_bbox, search_scale=2.2):
    """Try to find a 4-corner rectangle around the face that likely corresponds to the ID photo.

    Returns (x1,y1,x2,y2) in px for the full image, or None.
    """
    h, w = image_bgr.shape[:2]
    fx1, fy1, fx2, fy2 = face_bbox

    # define search ROI around face
    fw = fx2 - fx1
    fh = fy2 - fy1
    cx = (fx1 + fx2) / 2
    cy = (fy1 + fy2) / 2

    roi_w = fw * search_scale
    roi_h = fh * search_scale

    rx1 = int(round(cx - roi_w / 2))
    ry1 = int(round(cy - roi_h / 2))
    rx2 = int(round(cx + roi_w / 2))
    ry2 = int(round(cy + roi_h / 2))

    rx1 = clamp(rx1, 0, w - 1)
    ry1 = clamp(ry1, 0, h - 1)
    rx2 = clamp(rx2, rx1 + 2, w)
    ry2 = clamp(ry2, ry1 + 2, h)

    roi = image_bgr[ry1:ry2, rx1:rx2]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, None, iterations=1)
    edges = cv2.erode(edges, None, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # face center in ROI coords
    rcx = cx - rx1
    rcy = cy - ry1

    best = None
    best_area = 0

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4:
            continue

        x, y, ww, hh = cv2.boundingRect(approx)
        area = ww * hh
        if area < 0.15 * (roi.shape[0] * roi.shape[1]):
            # too small to be the photo boundary
            continue

        # must contain face center
        if not (x <= rcx <= x + ww and y <= rcy <= y + hh):
            continue

        # plausible portrait-ish photo aspect ratio
        ar = ww / float(hh)
        if ar < 0.55 or ar > 1.20:
            continue

        if area > best_area:
            best_area = area
            best = (x, y, x + ww, y + hh)

    if not best:
        return None

    bx1, by1, bx2, by2 = best
    # convert back to full-image coords
    return (bx1 + rx1, by1 + ry1, bx2 + rx1, by2 + ry1)


def upscale_min_width(pil_img: Image.Image, min_width: int) -> Image.Image:
    if pil_img.size[0] >= min_width:
        return pil_img
    new_w = min_width
    new_h = round(pil_img.size[1] * (new_w / pil_img.size[0]))
    return pil_img.resize((new_w, new_h), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-width", type=int, default=500)
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--search-scale", type=float, default=2.2)

    # model paths
    ap.add_argument(
        "--model-dir",
        default="<HOME>/.openclaw/workspace/skills/id-ocr/models/opencv-face",
        help="Directory containing deploy.prototxt and res10_*.caffemodel",
    )

    args = ap.parse_args()

    prototxt = f"{args.model_dir}/deploy.prototxt"
    weights = f"{args.model_dir}/res10_300x300_ssd_iter_140000_fp16.caffemodel"

    image_bgr = cv2.imread(args.input)
    if image_bgr is None:
        print("ERROR: failed to read input image", file=sys.stderr)
        return 1

    face = detect_largest_face_box_dnn(image_bgr, prototxt, weights, conf=args.conf)
    if not face:
        print("ERROR: no face detected", file=sys.stderr)
        return 2

    fx1, fy1, fx2, fy2, score = face
    photo_box = find_photo_rectangle_near_face(
        image_bgr, (fx1, fy1, fx2, fy2), search_scale=args.search_scale
    )

    pil = Image.open(args.input).convert("RGB")

    if photo_box:
        x1, y1, x2, y2 = photo_box
        crop = pil.crop((x1, y1, x2, y2))
        crop = upscale_min_width(crop, args.min_width)
        crop.save(args.output, "JPEG", quality=95)
        print(
            "OK",
            {
                "face_bbox": [fx1, fy1, fx2, fy2],
                "photo_bbox": [x1, y1, x2, y2],
                "score": score,
                "out_size": list(crop.size),
            },
        )
        return 0

    if args.no_fallback:
        print("ERROR: no photo rectangle detected", file=sys.stderr)
        return 3

    # Conservative fallback: modestly expand face box to approximate photo area
    # (much smaller than headshot padding).
    w, h = pil.size
    bw = fx2 - fx1
    bh = fy2 - fy1

    pad_l = 0.55
    pad_r = 0.55
    pad_t = 0.45
    pad_b = 0.85

    nx1 = clamp(int(round(fx1 - pad_l * bw)), 0, w - 1)
    ny1 = clamp(int(round(fy1 - pad_t * bh)), 0, h - 1)
    nx2 = clamp(int(round(fx2 + pad_r * bw)), nx1 + 2, w)
    ny2 = clamp(int(round(fy2 + pad_b * bh)), ny1 + 2, h)

    crop = pil.crop((nx1, ny1, nx2, ny2))
    crop = upscale_min_width(crop, args.min_width)
    crop.save(args.output, "JPEG", quality=95)

    print(
        "FALLBACK",
        {
            "face_bbox": [fx1, fy1, fx2, fy2],
            "photo_bbox": [nx1, ny1, nx2, ny2],
            "score": score,
            "out_size": list(crop.size),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
