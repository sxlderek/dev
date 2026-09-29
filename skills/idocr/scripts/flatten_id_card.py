#!/usr/bin/env python3
"""Deskew/flatten an ID document image via card-boundary detection.

This is a best-effort preprocessor:
- Finds the largest 4-corner contour (assumed to be the card)
- Applies perspective transform to a normalized rectangle

Usage:
  python3 flatten_id_card.py --input in.jpg --output flat.jpg --width 1100

Exit codes:
  0 success
  2 card boundary not found
"""

import argparse
import sys

import cv2
import numpy as np


def order_points(pts):
    # pts: (4,2)
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
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

    # scale to requested width
    scale = out_w / float(maxWidth)
    out_h = int(round(maxHeight * scale))

    dst = np.array([
        [0, 0],
        [out_w - 1, 0],
        [out_w - 1, out_h - 1],
        [0, out_h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (out_w, out_h))
    return warped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--width", type=int, default=1100)
    args = ap.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        print("ERROR: cannot read image", file=sys.stderr)
        return 1

    orig = img.copy()
    h, w = img.shape[:2]

    # downscale for contour detection
    scale = 900.0 / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

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
        print("ERROR: card boundary not found", file=sys.stderr)
        return 2

    # map points back to original scale
    if scale < 1.0:
        card = card / scale

    warped = four_point_transform(orig, card, args.width)
    cv2.imwrite(args.output, warped)
    print("OK", {"out": args.output, "size": warped.shape[:2]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
