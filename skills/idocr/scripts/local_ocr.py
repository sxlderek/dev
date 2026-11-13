#!/usr/bin/env python3
"""LOCAL-ONLY OCR for ID documents. Never calls any remote API.

Engine: Tesseract (eng + chi_sim/chi_tra) with optional OpenCV preprocessing.
This is the LOCAL process used FIRST by the idocr skill. It runs entirely on
this host - ID data never leaves the machine.

Usage:
  python3 local_ocr.py --input /path/to/id.jpg [--lang eng+chi_sim] [--preprocess]

Prints raw OCR text blocks to stdout (block per line), then a JSON blob of the
extracted structured fields (best-effort regex) so callers can inspect locally.

Exit codes:
  0 - Success (OCR completed even if no fields extracted)
  1 - Image not found / invalid
  2 - Tesseract binary not found
"""

import argparse, json, os, re, subprocess, sys, tempfile

# Path to the micromamba 'ocr' env tools (rootless container layout).
# Adjust TESSERACT if it lives elsewhere on another host.
TESSERACT = "/opt/data/tools/mamba-root/envs/ocr/bin/tesseract"
if not os.path.exists(TESSERACT):
    for candidate in (
        "/opt/data/tools/bin/micromamba",
        "tesseract",
    ):
        if os.path.exists(candidate):
            TESSERACT = candidate
            break

FIELD_RE = {
    "name": re.compile(r"NAME\s*[:：]\s*(.+)$", re.I | re.M),
    "dob": re.compile(r"\bDOB\s*[:：]?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", re.I | re.M),
    "doc_number": re.compile(r"(?:ID\s*NUMBER|IDENTITY\s*CARD|NO\.?|證件號碼|证件号码|证件号)\s*[:：]?\s*([A-Z0-9]{6,})", re.I | re.M),
    "expiry": re.compile(r"EXPIRY\s*[:：]\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", re.I | re.M),
    "country": re.compile(r"(?:COUNTRY|ISSUING\s*COUNTRY)\s*[:：]\s*(.+)$", re.I | re.M),
}


def run_tesseract(image_path, lang):
    """Run Tesseract via direct binary or micromamba wrapper."""
    if TESSERACT.endswith("tesseract"):
        base = [TESSERACT, image_path, "stdout"]
    else:
        ocr_env = "/opt/data/tools/bin/micromamba"
        base = [ocr_env, "-r", "/opt/data/tools/mamba-root", "run", "-n", "ocr", "tesseract", image_path, "stdout"]
    if lang:
        base += ["-l", lang]
    proc = subprocess.run(base, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed ({proc.returncode}): {proc.stderr[-500:]}")
    return proc.stdout


def preprocess_with_opencv(image_path):
    """Return a temp path to a grayscale+thresholded version of the image, or
    the original path if OpenCV is unavailable. Raises if the image is invalid."""
    out_path = None
    try:
        import cv2
    except ImportError:
        return image_path, False
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"OpenCV could not read image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Otsu adaptive threshold for clean text
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out_path = os.path.join(tempfile.gettempdir(), "idocr_preprocess.png")
    cv2.imwrite(out_path, thresh)
    return out_path, True


def extract_fields(text):
    """Best-effort regex field extraction from raw OCR text. LOCAL only."""
    fields = {}
    for field, rx in FIELD_RE.items():
        m = rx.search(text)
        if m:
            fields[field] = m.group(1).strip()
    return fields


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--lang", default="eng")
    ap.add_argument("--preprocess", action="store_true")
    ap.add_argument("--free", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(json.dumps({"error": "image not found", "path": args.input}))
        sys.exit(1)

    img_path = args.input
    used_cv = False
    # If preprocessing requested, need OpenCV; otherwise try Tesseract directly
    work_path = img_path
    if args.preprocess:
        try:
            work_path, used_cv = preprocess_with_opencv(img_path)
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)

    try:
        text = run_tesseract(work_path, args.lang)
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)

    fields = extract_fields(text)

    print("=== RAW OCR (LOCAL, Tesseract) ===")
    print(text.strip())
    print("=== STRUCTURED ===")
    print(json.dumps({"fields": fields, "preprocessed": used_cv,
                      "engine": "tesseract", "local_only": True},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
