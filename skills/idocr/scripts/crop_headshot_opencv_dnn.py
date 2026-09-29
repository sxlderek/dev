#!/usr/bin/env python3
"""Crop an ID headshot (hair-to-chin) using OpenCV DNN face detection + padding.

- Detects the largest face in the image.
- Expands the detected face box with configurable padding (top-heavy) to include hair + chin.
- Crops and upscales to at least 500px wide while preserving aspect ratio.

Usage:
  python3 crop_headshot_opencv_dnn.py \
    --input /path/to/id.jpg \
    --output /path/to/out.jpg \
    --min-width 500

Exit codes:
  0 success
  2 no face detected
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


def padded_box(x1, y1, x2, y2, w, h, pad_l, pad_r, pad_t, pad_b):
    bw = x2 - x1
    bh = y2 - y1

    nx1 = int(round(x1 - pad_l * bw))
    ny1 = int(round(y1 - pad_t * bh))
    nx2 = int(round(x2 + pad_r * bw))
    ny2 = int(round(y2 + pad_b * bh))

    nx1 = clamp(nx1, 0, w - 1)
    ny1 = clamp(ny1, 0, h - 1)
    nx2 = clamp(nx2, nx1 + 1, w)
    ny2 = clamp(ny2, ny1 + 1, h)

    return nx1, ny1, nx2, ny2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-width", type=int, default=500)
    ap.add_argument("--conf", type=float, default=0.5)

    # Padding factors relative to detected face box.
    # Defaults are intentionally generous to capture hair + chin.
    ap.add_argument("--pad-left", type=float, default=0.35)
    ap.add_argument("--pad-right", type=float, default=0.35)
    ap.add_argument("--pad-top", type=float, default=0.80)
    ap.add_argument("--pad-bottom", type=float, default=0.60)

    args = ap.parse_args()

    # model paths (stored alongside the skill)
    base = "<HOME>/.openclaw/workspace/skills/id-ocr/models/opencv-face"
    prototxt = f"{base}/deploy.prototxt"
    weights = f"{base}/res10_300x300_ssd_iter_140000_fp16.caffemodel"

    image_bgr = cv2.imread(args.input)
    if image_bgr is None:
        print("ERROR: failed to read input image", file=sys.stderr)
        return 1

    h, w = image_bgr.shape[:2]
    face = detect_largest_face_box_dnn(image_bgr, prototxt, weights, conf=args.conf)
    if not face:
        print("ERROR: no face detected", file=sys.stderr)
        return 2

    x1, y1, x2, y2, score = face
    nx1, ny1, nx2, ny2 = padded_box(
        x1,
        y1,
        x2,
        y2,
        w,
        h,
        pad_l=args.pad_left,
        pad_r=args.pad_right,
        pad_t=args.pad_top,
        pad_b=args.pad_bottom,
    )

    pil = Image.open(args.input).convert("RGB")
    crop = pil.crop((nx1, ny1, nx2, ny2))

    if crop.size[0] < args.min_width:
        new_w = args.min_width
        new_h = round(crop.size[1] * (new_w / crop.size[0]))
        crop = crop.resize((new_w, new_h), Image.LANCZOS)

    crop.save(args.output, "JPEG", quality=95)

    print(
        "OK",
        {
            "face_bbox": [x1, y1, x2, y2],
            "padded_bbox": [nx1, ny1, nx2, ny2],
            "score": score,
            "out_size": list(crop.size),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
