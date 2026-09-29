#!/usr/bin/env python3
"""Render page 1 of a PDF into a vision-ready JPEG.

Why: Vision models and API proxies often fail with timeouts or payload limits on large
uncompressed images. Cap the max dimension at ~1000px and save as JPEG q80 -> typically 100-300 KB.

Usage:
    python render_page1.py <input.pdf> [output.jpg]

Output defaults to <input-stem>.vision.jpg next to the PDF. Prints the
output path and byte size to stdout.
"""
import sys
import os

import fitz  # pymupdf
from PIL import Image

MAX_DIM = 1000
JPEG_QUALITY = 80
DPI = 150


def main():
    if len(sys.argv) < 2:
        print("usage: render_page1.py <input.pdf> [output.jpg]", file=sys.stderr)
        sys.exit(2)

    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".vision.jpg"

    doc = fitz.open(src)
    pix = doc[0].get_pixmap(dpi=DPI)
    doc.close()

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # Downscale to cap the payload the vision proxy sees.
    w, h = img.size
    scale = min(1.0, MAX_DIM / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    img.save(out, "JPEG", quality=JPEG_QUALITY)
    print(f"{out}\t{os.path.getsize(out)} bytes\t{img.size[0]}x{img.size[1]}")


if __name__ == "__main__":
    main()
