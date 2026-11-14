#!/usr/bin/env python3
"""Extract the ID-photo rectangle from an ID document image, then verify the crop
contains the full face (hairline -> neck) using OpenCV DNN face detection.

Why:
- Pure rectangle detection can cut off nose/mouth/chin/neck.
- This script retries with progressively larger padding until the detected face
  has enough headroom and bottom margin.

Requires:
- python3-opencv
- pillow
- OpenCV DNN face detector weights (same as other scripts)

Usage:
  python3 extract_id_photo_rect_verified.py \
    --input id.jpg --output id_photo.jpg \
    --model-dir skills/id-ocr/models/opencv-face

Exit codes:
  0 success
  2 could not find a plausible photo rectangle
  3 could not detect a face in the crop after retries
"""

import argparse
import sys

import cv2
from PIL import Image


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def detect_largest_face_box_dnn(image_bgr, prototxt: str, weights: str, conf: float):
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


def find_photo_rectangle_edge_based(image_bgr, right_start: float = 0.50):
    """Find a portrait-ish rectangle in the right half of the ID card."""
    h, w = image_bgr.shape[:2]
    x0 = int(w * right_start)
    roi = image_bgr[:, x0:w]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
    edges = cv2.erode(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for c in contours:
        x, y, ww, hh = cv2.boundingRect(c)
        area = ww * hh
        ar = ww / float(hh + 1e-6)

        # Heuristics: photo is portrait-ish and not tiny
        if area < 0.008 * roi.shape[0] * roi.shape[1]:
            continue
        if ar < 0.45 or ar > 1.10:
            continue
        boxes.append((area, x, y, ww, hh, ar))

    if not boxes:
        return None

    boxes.sort(reverse=True)
    _, x, y, ww, hh, _ = boxes[0]
    # convert to full-image coordinates
    return (x + x0, y, x + x0 + ww, y + hh)


def crop_with_padding(pil_img: Image.Image, box, pad_x: int, pad_y: int):
    w, h = pil_img.size
    x1, y1, x2, y2 = box
    nx1 = clamp(x1 - pad_x, 0, w - 1)
    ny1 = clamp(y1 - pad_y, 0, h - 1)
    nx2 = clamp(x2 + pad_x, nx1 + 2, w)
    ny2 = clamp(y2 + pad_y, ny1 + 2, h)
    return pil_img.crop((nx1, ny1, nx2, ny2)), (nx1, ny1, nx2, ny2)


def face_coverage_ok(crop_bgr, face_bbox):
    """Require some margin above forehead and below chin for neck."""
    h, w = crop_bgr.shape[:2]
    x1, y1, x2, y2, _ = face_bbox
    fh = y2 - y1

    top_margin = y1
    bottom_margin = h - y2

    # headroom for hair + some margin for neck
    return (top_margin >= 0.15 * fh) and (bottom_margin >= 0.35 * fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model-dir", default="<HOME>/.openclaw/workspace/skills/id-ocr/models/opencv-face")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--right-start", type=float, default=0.50)
    ap.add_argument("--min-width", type=int, default=500)
    args = ap.parse_args()

    prototxt = f"{args.model_dir}/deploy.prototxt"
    weights = f"{args.model_dir}/res10_300x300_ssd_iter_140000_fp16.caffemodel"

    image_bgr = cv2.imread(args.input)
    if image_bgr is None:
        print("ERROR: failed to read input image", file=sys.stderr)
        return 1

    photo_box = find_photo_rectangle_edge_based(image_bgr, right_start=args.right_start)
    if not photo_box:
        print("ERROR: no photo rectangle detected", file=sys.stderr)
        return 2

    pil = Image.open(args.input).convert("RGB")

    # progressive padding factors
    pad_factors = [0.12, 0.20, 0.30, 0.42]
    last_face = None

    for f in pad_factors:
        x1, y1, x2, y2 = photo_box
        ww = x2 - x1
        hh = y2 - y1
        pad_x = max(10, int(round(f * ww)))
        pad_y = max(10, int(round(f * hh)))

        crop_pil, padded_box = crop_with_padding(pil, photo_box, pad_x, pad_y)
        crop_bgr = cv2.cvtColor(cv2.imread(args.input)[padded_box[1]:padded_box[3], padded_box[0]:padded_box[2]], cv2.COLOR_BGR2RGB)
        # read via PIL for saving; for face detection use cv2 from crop_pil
        crop_bgr2 = cv2.cvtColor(cv2.cvtColor(cv2.imread(args.input)[padded_box[1]:padded_box[3], padded_box[0]:padded_box[2]], cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
        # Use the actual color crop for face detection
        crop_bgr_color = cv2.cvtColor(cv2.imread(args.input)[padded_box[1]:padded_box[3], padded_box[0]:padded_box[2]], cv2.COLOR_BGR2RGB)
        crop_bgr_color = cv2.cvtColor(crop_bgr_color, cv2.COLOR_RGB2BGR)

        face = detect_largest_face_box_dnn(crop_bgr_color, prototxt, weights, conf=args.conf)
        last_face = face
        if face and face_coverage_ok(crop_bgr_color, face):
            # upscale if needed
            if crop_pil.size[0] < args.min_width:
                new_w = args.min_width
                new_h = round(crop_pil.size[1] * (new_w / crop_pil.size[0]))
                crop_pil = crop_pil.resize((new_w, new_h), Image.LANCZOS)
            crop_pil.save(args.output, "JPEG", quality=95)
            print("OK", {"photo_box": list(photo_box), "padded_box": list(padded_box), "face_bbox": list(face[:4]), "pad_factor": f})
            return 0

    print("ERROR: could not verify full-face coverage", {"last_face": None if not last_face else list(last_face[:4])}, file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
