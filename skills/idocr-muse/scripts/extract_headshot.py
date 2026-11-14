#!/usr/bin/env python3
"""Extract the printed headshot photo from a (flattened) ID card image.

Method (verified 2026-11-14 on a CN Resident Identity Card):
  1. Detect the face with the OpenCV DNN face detector
     (models/opencv-face: deploy.prototxt + res10_300x300_ssd caffemodel).
  2. Derive the printed photo rectangle from the face box using the standard
     CN ID photo proportions (photo = 26 x 32 mm, w/h = 0.8125):
       photo width  = face width / 0.571
       photo height = photo width * 32/26
       photo centre-x = face centre-x
       photo top      = face top - 0.234 * face height
  3. Crop, upscale 2x (LANCZOS) for presentation, save as JPEG.

Why not the older approaches:
  - Rectangle detection found no photo rectangle on a flattened card in
    testing.
  - Face detection worked, but a photo box derived with naive margins
    overshoots (caught card guilloche at the top and a strip of the ID-number
    row at the bottom). This script uses the face box with the standard
    photo proportions instead.

Requirements: OpenCV 4.x (cv2.dnn.readNetFromCaffe was REMOVED in OpenCV 5),
numpy, pillow. Run it on the flattened card from flatten_and_export.py so the
geometry is standard (1200x757). Always visually verify the crop before
presenting: the photo's own background should show on all four sides, with no
card text or digits included.

Usage:
  python3 extract_headshot.py --input id-card-front.jpg --output id-headshot.jpg
  (--model-dir defaults to this skill's models/opencv-face directory.)
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image

PHOTO_RATIO = 26.0 / 32.0   # CN ID photo w/h
FACE_W_FRACTION = 0.571     # face width as a fraction of photo width
TOP_OFFSET = 0.234          # photo top sits this * face-height above the face box


def detect_face(net, img_bgr, conf_threshold=0.5):
    h, w = img_bgr.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(img_bgr, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
    )
    net.setInput(blob)
    dets = net.forward()
    best = None
    for i in range(dets.shape[2]):
        conf = float(dets[0, 0, i, 2])
        if conf < conf_threshold:
            continue
        box = (dets[0, 0, i, 3:7] * np.array([w, h, w, h])).astype(int)
        if best is None or conf > best[0]:
            best = (conf, box)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="flattened ID card front image")
    ap.add_argument("--output", required=True, help="output headshot JPEG")
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--model-dir", default=os.path.join(skill_dir, "models", "opencv-face"),
                    help="dir with deploy.prototxt + res10 caffemodel")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--upscale", type=int, default=2)
    args = ap.parse_args()

    prototxt = os.path.join(args.model_dir, "deploy.prototxt")
    weights = os.path.join(args.model_dir, "res10_300x300_ssd_iter_140000_fp16.caffemodel")
    if not (os.path.exists(prototxt) and os.path.exists(weights)):
        print(f"ERROR: face model files not found in {args.model_dir}", file=sys.stderr)
        return 2
    try:
        net = cv2.dnn.readNetFromCaffe(prototxt, weights)
    except AttributeError:
        print("ERROR: cv2.dnn.readNetFromCaffe unavailable — OpenCV 5 removed it; use OpenCV 4.x",
              file=sys.stderr)
        return 2

    img = cv2.imread(args.input)
    if img is None:
        print(f"ERROR: cannot read {args.input}", file=sys.stderr)
        return 2
    H, W = img.shape[:2]

    found = detect_face(net, img, args.conf)
    if not found:
        print("ERROR: no face detected — do not guess the crop", file=sys.stderr)
        return 1
    conf, (fx0, fy0, fx1, fy1) = found
    fw, fh = fx1 - fx0, fy1 - fy0

    photo_w = fw / FACE_W_FRACTION
    photo_h = photo_w / PHOTO_RATIO
    cx = (fx0 + fx1) / 2.0
    x0 = int(round(cx - photo_w / 2))
    y0 = int(round(fy0 - TOP_OFFSET * fh))
    x1 = int(round(x0 + photo_w))
    y1 = int(round(y0 + photo_h))
    # clamp inside the image
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)

    crop = Image.fromarray(cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2RGB))
    if args.upscale > 1:
        crop = crop.resize((crop.width * args.upscale, crop.height * args.upscale), Image.LANCZOS)
    crop.save(args.output, "JPEG", quality=90)
    print(f"face: conf={conf:.3f} box=({fx0},{fy0})-({fx1},{fy1})")
    print(f"photo box: ({x0},{y0})-({x1},{y1}) -> {args.output} {crop.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
