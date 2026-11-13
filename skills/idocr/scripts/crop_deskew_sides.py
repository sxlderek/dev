#!/usr/bin/env python3
"""Crop, deskew, and orient ID-card side photos; save each as JPEG under a size cap.

Local-only (no network). Built for phone photos where the card nearly fills the
frame and classic quad/contour detection fails (no visible card border; bright
background touching the card on every side).

Pipeline:
  1. Orientation: --rotate auto votes across the 4 rotations by counting OCR
     keyword hits (tesseract); pass --rotate ccw|cw|180 to force a known fix.
  2. Card bbox: sharpness-energy mask (in-focus card face vs blurred background),
     largest component + merge overlaps.
  3. Edge refinement: brightness drop-off scans from inside the card on the
     column/row mean profiles (the sharpness bbox alone misses low-contrast edges).
  4. Deskew: horizontal text-line angle voting (median minAreaRect angle), warp
     with BORDER_REPLICATE then trim the fringe.
  5. Landscape enforcement, resize (INTER_CUBIC when upscaling, INTER_AREA when
     downscaling), JPEG quality scanned down from 96 to land under --max-kb.

Usage:
  crop_deskew_sides.py --input front.jpg --output front_clean.jpg --max-kb 100 \
      [--target-w 1100] [--rotate auto] [--expected-ar 1.585] [--keywords ...]

Exit codes: 0 ok, 2 input unreadable.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

CARD_AR_FALLBACK = 85.6 / 54.0  # CN ID card: 85.6mm x 54.0mm


def tesseract_bin():
    exe = shutil.which("tesseract") or os.environ.get("TESSERACT_BIN")
    if exe:
        return exe
    for cand in ("/opt/data/tools/conda-prefix/bin/tesseract",):
        if os.path.exists(cand):
            return cand
    return None


def _ocr(img, lang, psm):
    exe = tesseract_bin()
    if not exe:
        return ""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(buf.tobytes())
        tmp = f.name
    try:
        r = subprocess.run(
            [exe, tmp, "-", "--psm", str(psm), "-l", lang],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, "OMP_THREAD_LIMIT": "4"},
        )
        return r.stdout or ""
    except Exception:
        return ""
    finally:
        os.unlink(tmp)


def vote_orientation(img, keywords, lang="chi_sim"):
    """Return ((label, rot), hits) maximizing keyword hits across 4 orientations."""
    rots = [
        ("as-is", None),
        ("rot90cw", cv2.ROTATE_90_CLOCKWISE),
        ("rot180", cv2.ROTATE_180),
        ("rot90ccw", cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    best, best_hits = None, -1
    for label, rot in rots:
        im = img if rot is None else cv2.rotate(img, rot)
        txt = _ocr(im, lang, 3) + _ocr(im, lang, 6)
        hits = sum(1 for k in keywords if k in txt)
        if hits > best_hits:
            best, best_hits = (label, rot), hits
    return best, best_hits


def sharp_bbox(img, pad=8):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, 3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, 3)
    mag = cv2.blur(cv2.magnitude(gx, gy), (11, 11))
    hi = (mag > np.percentile(mag, 82)).astype(np.uint8) * 255
    hi = cv2.morphologyEx(hi, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(hi)
    if n <= 1:
        raise RuntimeError("sharpness bbox: no foreground found")
    i = 1 + int(np.argmax(stats[1:, 4]))
    x, y, w, h, _ = stats[i]
    H, W = img.shape[:2]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
    for j in range(1, n):
        if j == i:
            continue
        xj, yj, wj, hj, _ = stats[j]
        if xj < x1 and xj + wj > x0 and yj < y1 and yj + hj > y0:
            x0, y0 = min(x0, xj), min(y0, yj)
            x1, y1 = max(x1, xj + wj), max(y1, yj + hj)
    return int(x0), int(y0), int(x1), int(y1)


def refine_edges(img, bb, drop=18.0):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    cp, rp = g.mean(axis=0), g.mean(axis=1)
    x0, y0, x1, y1 = bb
    H, W = img.shape[:2]

    def scan(profile, start, direction, lo, hi):
        i, run = start, 0
        while lo <= i <= hi:
            j = i + direction
            if not (lo <= j <= hi):
                break
            if profile[i] - profile[j] >= drop:
                run += 1
                if run >= 3:
                    return i
            else:
                run = 0
            i = j
        return None

    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    e = scan(cp, (cx + x1) // 2, +1, x1 - 60, min(x1 + 200, W - 2))
    if e:
        x1 = e + 1
    e = scan(cp, (cx + x0) // 2, -1, max(x0 - 200, 1), x0 + 60)
    if e:
        x0 = e
    e = scan(rp, (cy + y1) // 2, +1, y1 - 60, min(y1 + 200, H - 2))
    if e:
        y1 = e + 1
    e = scan(rp, (cy + y0) // 2, -1, max(y0 - 200, 1), y0 + 60)
    if e:
        y0 = e
    return int(x0), int(y0), int(x1), int(y1)


def text_line_angle(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 25, 12)
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (35, 1)))
    cnts, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angs = []
    for c in cnts:
        if len(c) >= 5 and cv2.contourArea(c) > 300:
            (_, _), (w, h), ang = cv2.minAreaRect(c)
            if w > 40 and abs(ang) < 20:
                angs.append(ang if w >= h else ang + 90)
    if not angs:
        return 0.0
    med = float(np.median(np.array(angs)))
    if med > 45:
        med -= 90
    if med < -45:
        med += 90
    return med


def save_jpeg_under(img, out, max_kb, target_w):
    h, w = img.shape[:2]
    interp = cv2.INTER_CUBIC if target_w > w else cv2.INTER_AREA
    out_img = cv2.resize(img, (target_w, max(1, round(h * target_w / w))),
                         interpolation=interp)
    best = None
    for q in range(96, 39, -2):
        ok, buf = cv2.imencode(".jpg", out_img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if not ok:
            continue
        best = (q, buf)
        if len(buf) <= max_kb * 1024:
            break
    q, buf = best
    with open(out, "wb") as f:
        f.write(buf.tobytes())
    return out_img, q, len(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--target-w", type=int, default=1100)
    ap.add_argument("--max-kb", type=int, default=100)
    ap.add_argument("--rotate", choices=["auto", "none", "ccw", "cw", "180"],
                    default="none")
    ap.add_argument("--keywords",
                    default="居民身份,身份证,性别,出生,住址,公民",
                    help="comma-separated OCR keywords for --rotate auto voting")
    ap.add_argument("--expected-ar", type=float, default=None,
                    help="expected final aspect ratio, e.g. 1.585 for CN ID; warns on >2%% deviation")
    args = ap.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        print("ERROR: cannot read", args.input, file=sys.stderr)
        return 2

    if args.rotate != "none":
        mapping = {"ccw": cv2.ROTATE_90_COUNTERCLOCKWISE,
                   "cw": cv2.ROTATE_90_CLOCKWISE,
                   "180": cv2.ROTATE_180}
        rot = None
        if args.rotate == "auto":
            (label, rot), hits = vote_orientation(
                img, [k.strip() for k in args.keywords.split(",") if k.strip()])
            print(f"orientation vote: {label} ({hits} keyword hits)")
            if hits == 0:
                print("WARNING: zero keyword hits — verify orientation manually or "
                      "vote on digits (card backs: embossed doc number reads only "
                      "at the correct orientation; rerun with eng and a digit "
                      "regex, or pass --rotate explicitly)", file=sys.stderr)
        else:
            rot = mapping[args.rotate]
        if rot is not None:
            img = cv2.rotate(img, rot)

    bb = sharp_bbox(img)
    bb = refine_edges(img, bb)
    x0, y0, x1, y1 = bb
    crop = img[y0:y1, x0:x1]

    ang = text_line_angle(crop)
    if abs(ang) > 0.15:
        M = cv2.getRotationMatrix2D((crop.shape[1] / 2, crop.shape[0] / 2), ang, 1.0)
        crop = cv2.warpAffine(crop, M, (crop.shape[1], crop.shape[0]),
                              flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        crop = crop[3:-3, 3:-3]  # trim replicate fringe

    h, w = crop.shape[:2]
    if h > w:
        crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
        h, w = crop.shape[:2]

    out_img, q, nbytes = save_jpeg_under(crop, args.output, args.max_kb, args.target_w)
    ar = w / h if h else 0.0
    ref = args.expected_ar or CARD_AR_FALLBACK
    dev = abs(ar - ref) / ref * 100 if ref else 0.0
    print(f"{args.output}: bbox={bb} deskew={ang:.2f}deg crop={w}x{h} ar={ar:.3f} "
          f"(ref {ref:.3f}, dev {dev:.1f}%) q={q} bytes={nbytes}")
    if args.expected_ar and dev > 2.0:
        print("WARNING: aspect ratio deviates >2% from expected — recheck the crop "
              "(a wrong bbox usually shows up here first)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
