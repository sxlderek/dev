#!/usr/bin/env python3
"""Flatten ID card photos: rotate (EXIF), deskew, crop to the card, export JPG <150KB.

For each input photo of an ID card (any side), this:
  1. Applies EXIF orientation so the photo is upright as shot.
  2. Detects the card outline and takes its quadrilateral:
       - strategy "otsu": Otsu threshold (bright card on darker background);
       - strategy "grabcut": GrabCut segmentation with the image border as
         background — rescues pale cards on pale backgrounds, where the gray
         levels overlap and Otsu merges card and background (seen 2026-11-14:
         a card on a beige quilt and on a light-gray surface).
     "auto" (default) tries Otsu first, then GrabCut. A quad is accepted only
     if it covers 25-99% of the frame and its side ratio is 1.30-1.90
     (the ID-1 ratio is 1.586, with perspective slack).
  3. Perspective-warps ("deskews") the quad to the ID-1 card ratio
     (85.6 x 54 mm) at --width px (default 1200x757).
  4. Saves JPEG, stepping quality down (then size down) until the file is
     under --max-kb (default 150 KB, with a small safety margin).

Corner ordering rule (getting this wrong transposes/mirrors the output):
  tl = min(x+y), br = max(x+y), tr = min(y-x), bl = max(y-x).

Always visually verify the outputs before presenting them — a wrong quad can
still pass the checks (e.g. bottom edge riding too high and cutting the ID
number line). If a warp looks wrong, rerun with --strategy grabcut.

Deps: opencv-python-headless (or opencv-python), numpy, pillow.

Usage:
  python3 flatten_and_export.py --input front.jpg back.jpg --out-dir ./out
  python3 flatten_and_export.py --input a.jpg b.jpg --out-dir ./out --names front,back
      -> ./out/id-card-front.jpg, ./out/id-card-back.jpg
  Without --names, outputs are <input-stem>-flattened.jpg.
"""
import argparse
import io
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps

CARD_RATIO = 85.6 / 54.0  # ID-1


def order_corners(pts):
    s = pts.sum(axis=1)               # tl = min, br = max
    d = np.diff(pts, axis=1).ravel()  # y - x: tr = min, bl = max
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype=np.float32,
    )


def _plausible(quad, img_area):
    q = order_corners(quad)
    area = cv2.contourArea(q.reshape(-1, 1, 2).astype(np.float32)) / img_area
    top = np.linalg.norm(q[1] - q[0])
    bottom = np.linalg.norm(q[2] - q[3])
    left = np.linalg.norm(q[3] - q[0])
    right = np.linalg.norm(q[2] - q[1])
    ratio = ((top + bottom) / 2) / max(((left + right) / 2), 1)
    return 0.25 <= area <= 0.99 and 1.30 <= ratio <= 1.90


def _quad_from_mask(mask, img_area):
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in sorted(cnts, key=cv2.contourArea, reverse=True)[:3]:
        peri = cv2.arcLength(cnt, True)
        for eps in (0.01, 0.015, 0.02, 0.03, 0.04, 0.05):
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
                if _plausible(quad, img_area):
                    return quad
    return None


def _quad_otsu(bgr, img_area):
    gray = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _quad_from_mask(mask, img_area)


def _quad_grabcut(bgr, img_area):
    h, w = bgr.shape[:2]
    gc_mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    mx, my = max(2, int(w * 0.015)), max(2, int(h * 0.015))
    cv2.grabCut(bgr, gc_mask, (mx, my, w - 2 * mx, h - 2 * my), bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    fg = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    return _quad_from_mask(fg, img_area)


def find_card_quad(img_bgr, strategy="auto"):
    img_area = img_bgr.shape[0] * img_bgr.shape[1]
    attempts = []
    if strategy in ("auto", "otsu"):
        attempts.append(("otsu", _quad_otsu))
    if strategy in ("auto", "grabcut"):
        attempts.append(("grabcut", _quad_grabcut))
    for name, fn in attempts:
        quad = fn(img_bgr, img_area)
        if quad is not None:
            print(f"  quad via {name}")
            return quad
    raise RuntimeError("no plausible card quad found (tried: " + ", ".join(n for n, _ in attempts) + ")")


def save_under_limit(pil_img, path, max_bytes):
    img = pil_img
    while True:
        for q in range(92, 55, -4):
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=q, optimize=True)
            if buf.tell() <= max_bytes:
                with open(path, "wb") as f:
                    f.write(buf.getvalue())
                return buf.tell(), q, img.size
        img = img.resize(
            (int(img.width * 0.9), int(img.height * 0.9)), Image.LANCZOS
        )


def process(src, dst, width, max_bytes, strategy):
    pil = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    bgr = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    quad = order_corners(find_card_quad(bgr, strategy))
    centre = quad.mean(axis=0)
    quad = centre + (quad - centre) * 0.996  # tiny inset avoids a background rim
    height = round(width / CARD_RATIO)
    dst_pts = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    m = cv2.getPerspectiveTransform(quad, dst_pts)
    warped = cv2.warpPerspective(bgr, m, (width, height))
    out = Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
    return save_under_limit(out, dst, max_bytes)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", nargs="+", required=True, help="input photo(s)")
    ap.add_argument("--out-dir", required=True, help="output directory")
    ap.add_argument("--names", default=None,
                    help="comma-separated side names, one per input (e.g. front,back); "
                         "outputs are named id-card-<name>.jpg")
    ap.add_argument("--width", type=int, default=1200, help="output width px (default 1200)")
    ap.add_argument("--max-kb", type=float, default=150.0, help="max file size in KB (default 150)")
    ap.add_argument("--strategy", choices=("auto", "otsu", "grabcut"), default="auto",
                    help="card detection strategy (default auto: otsu, then grabcut)")
    args = ap.parse_args()

    names = args.names.split(",") if args.names else None
    if names and len(names) != len(args.input):
        print("ERROR: --names must have one entry per input", file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    max_bytes = int(args.max_kb * 1000) - 500  # safety margin: under the limit either KB reading
    for i, src in enumerate(args.input):
        if names:
            dst = os.path.join(args.out_dir, f"id-card-{names[i]}.jpg")
        else:
            stem = os.path.splitext(os.path.basename(src))[0]
            dst = os.path.join(args.out_dir, f"{stem}-flattened.jpg")
        size, q, dims = process(src, dst, args.width, max_bytes, args.strategy)
        print(f"{dst}: {size} bytes, quality={q}, dims={dims}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
