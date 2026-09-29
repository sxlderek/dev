#!/usr/bin/env python3
"""OCR an ID document image using SiliconFlow Qwen3-VL-32B-Instruct.

Usage:
  python3 ocr_via_siliconflow.py --input /path/to/id.jpg
  python3 ocr_via_siliconflow.py --input /path/to/id.pdf   (auto-renders to image)

Requires env var SILICONFLOW_API_KEY to be set (or --api-key passed).
Structured identity fields are printed to stdout.

Exit codes:
  0 - Success
  1 - API key / network error
  2 - Image not found / invalid
"""

import argparse, base64, io, json, os, sys, urllib.request, urllib.error

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3-VL-32B-Instruct"

SYSTEM_PROMPT = """You are an ID document OCR system. Extract the following fields from the ID document image and return them in exactly this format:

Full Name (Native): ...
Full Name (EN): First Last
DOB: YYYY-MM-DD
Document type: National ID | Driving License | Passport | HK/Macau Pass(港澳通行證) | [unclear]
Document number: ... | [unclear]
Issuing country: ...
Expiry: YYYY-MM-DD | N/A | [unclear]

Rules:
- If a field is missing or illegible, output [unclear]
- If no expiry date, output N/A
- Convert ALL CAPS English names to mixed case (e.g. "CHAN TAI MAN" → "Chan Tai Man")
- Normalise dates to YYYY-MM-DD
- Return ONLY the field list, nothing else."""


def load_image_bytes(path: str) -> bytes:
    """Load an image from path. If PDF, render first page to PNG at 150 DPI."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".pdf",):
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("ERROR: PyMuPDF (fitz) required for PDF input. Install: pip install pymupdf", file=sys.stderr)
            sys.exit(2)
        doc = fitz.open(path)
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        buf = io.BytesIO()
        buf.write(pix.tobytes("png"))
        doc.close()
        return buf.getvalue()
    else:
        with open(path, "rb") as f:
            return f.read()


def ocr(image_bytes: bytes, api_key: str, model: str = DEFAULT_MODEL) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    mime = "image/png" if image_bytes[:8] == b'\x89PNG\r\n\x1a\n' else "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "Extract all identity fields from this document."},
                ],
            },
        ],
        "max_tokens": 800,
        "temperature": 0.0,
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"ERROR: HTTP {e.code} — {body}"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    ap = argparse.ArgumentParser(description="OCR ID document via SiliconFlow Qwen VL")
    ap.add_argument("--input", required=True, help="Path to ID image or PDF")
    ap.add_argument("--api-key", help="SILICONFLOW_API_KEY (default: from env)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"ERROR: file not found: {args.input}", file=sys.stderr)
        return 2

    api_key = args.api_key or os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY not set. Pass --api-key or set env var.", file=sys.stderr)
        return 1

    img_bytes = load_image_bytes(args.input)
    if not img_bytes:
        print("ERROR: could not load input file", file=sys.stderr)
        return 2

    result = ocr(img_bytes, api_key, args.model)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
