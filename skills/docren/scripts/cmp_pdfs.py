#!/usr/bin/env python3
"""Detect whether two PDFs are the same underlying document (fax re-transmissions).

Fax senders re-transmit the same sheet (same reference number, same page count), so
a duped upload pollutes the archive. Plain pixel diff is unreliable on its own: fax
header strips, skew and noise differ between transmissions and inflate it. Combine
(a) embedded image dimensions, (b) mean-abs pixel diff on width-normalized renders,
and (c) 16x16 perceptual-hash Hamming distance. phash <= ~10/256 on matching page
count + matching dims => same document.

Usage:
    conda-ocr-python3 cmp_pdfs.py <existing.pdf> <candidate.pdf>
Per-page verdicts: DUP / PROBABLE DUP / DIFFERENT. Exit 0 if every page matched
(a duplicate), 1 if any page ambiguous, 2 if any page differs.
"""
import sys
import numpy as np
from PIL import Image
import pymupdf


TARGET_W = 480


def image_specs(path):
    doc = pymupdf.open(path)
    out = []
    for pno in range(doc.page_count):
        for img in doc[pno].get_images(full=True):
            xref = img[0]
            info = doc.extract_image(xref)
            pix = pymupdf.Pixmap(doc, xref)
            out.append((pno, info['width'], info['height'], info['ext'],
                        pix.xres, pix.yres, bool(info.get('smask'))))
    return out


def render_norm(path, pno):
    doc = pymupdf.open(path)
    pix = doc[pno].get_pixmap(dpi=60)
    doc.close()
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    w, h = img.size
    img = img.resize((TARGET_W, max(1, int(h * TARGET_W / w))), Image.LANCZOS)
    return np.asarray(img.convert('L'), dtype=np.uint8)


def phash(arr, size=16):
    small = np.asarray(Image.fromarray(arr).resize((size, size), Image.LANCZOS),
                       dtype=np.float64)
    return (small > small.mean()).flatten()


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    old, new = sys.argv[1], sys.argv[2]
    print('== embedded image specs ==')
    for label, path in (('old', old), ('new', new)):
        for s in image_specs(path):
            print(f"{label} page {s[0]}: {s[1]}x{s[2]} {s[3]} dpi {s[4]}/{s[5]}"
                  + (' alpha' if s[6] else ''))
    print('== page compare ==')
    n_old = pymupdf.open(old).page_count
    n_new = pymupdf.open(new).page_count
    if n_old != n_new:
        print(f'page counts differ ({n_old} vs {n_new}) -> DIFFERENT')
        sys.exit(2)
    worst = 0
    for i in range(n_old):
        a = render_norm(old, i)
        b = render_norm(new, i)
        h = min(a.shape[0], b.shape[0])
        w = min(a.shape[1], b.shape[1])
        diff = np.abs(a[:h, :w].astype(int) - b[:h, :w].astype(int)).mean()
        ham = int(np.count_nonzero(phash(a) != phash(b)))
        if diff < 6 and ham <= 6:
            v, level = 'DUP', 0
        elif ham <= 10:
            v, level = 'PROBABLE DUP', 1
        else:
            v, level = 'DIFFERENT', 2
        worst = max(worst, level)
        print(f'page {i}: mean_abs_diff={diff:.1f} phash_hamming={ham} -> {v}')
    sys.exit(worst)


if __name__ == '__main__':
    main()
