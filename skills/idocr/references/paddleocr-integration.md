# PaddleOCR PP-OCRv6 Integration

## Architecture

```
extract_id.py (Python 3.14 — Hermes venv)
    │
    ├── run_paddleocr(image_path)         ← subprocess call
    │       │
    │       └── python3.12 paddleocr_helper.py <image>
    │               │
    │               └── PaddleOCR(lang='ch') → JSON stdout
    │
    ├── run_easyocr(image_path)           ← fallback (native Py3.14)
    │       │
    │       └── easyocr.Reader(['ch_sim','en']) → text
    │
    └── run_tesseract(image_path, lang)   ← last resort
```

## Why Python 3.12?

PaddlePaddle only ships wheels for cp310–cp312 (check: `https://www.paddlepaddle.org.cn/packages/stable/cpu/paddlepaddle/`). The Hermes venv runs Python 3.14.6, so PaddlePaddle cannot be installed there. We install it under a separate Python 3.12 environment (scoop-managed) and call it via subprocess.

## Installation

```bash
# Python 3.12 (separate from Hermes venv)
<HOME>/scoop/apps/python312/current/python.exe -m pip install paddleocr
<HOME>/scoop/apps/python312/current/python.exe -m pip install paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

**Version pin**: PaddleOCR 3.7.0 + PaddlePaddle 3.2.2. PaddlePaddle 3.3.1 has a oneDNN bug on this system (NotImplementedError: ConvertPirAttribute2RuntimeAttribute). PaddlePaddle 3.0.0 has a PIR type mismatch (strides not Int32). 3.2.2 works.

## Output Format Differences vs EasyOCR

| Aspect | EasyOCR | PaddleOCR PP-OCRv6 |
|---|---|---|
| Field separation | Character-by-character with spaces | Line-by-line (separate text blocks) |
| Name position | "姓名[Name]" (label first) | "[Name] 姓名" (name first, line break before label) |
| Confidence | Per-block, typical 0.1–0.97 | Per-block, typical **0.999–1.0** |
| Text joining | " ".join(blocks) → normalization needed | blocks already well-separated |
| Address reading | 江酉省 (wrong) | 江西省 (correct) |
| Back-side authority | 龙虎田 (wrong) | 龙虎山 (correct) |

## Text Patterns

PaddleOCR outputs lines like:
```
[Name]         ← separate line
姓名           ← separate line
性别女         ← line (gender fused to label)
民族汉         ← line (ethnicity fused to label)
出生1994年9月2日  ← line (DOB fused to label)
```

After normalization (CJK whitespace stripped), lines merge into:
```
[Name]姓名性别女民族汉出生1994年9月2日...
```

This means PaddleOCR produces the same fused-CJK text as EasyOCR after normalization. The extraction regexes work identically on both engines' outputs.

## Extraction Adaptations Required

1. **Name-before-label fallback**: Regex `(?:^|[\s_`：:]+)([\u4e00-\u9fff]{2,4})姓名` captures name before "姓名" label
2. **Label-first rejection**: If the regex after "姓名" captures a known field label (性别, 民族), reject it and fall through to the name-before-label pattern
3. **Passport CJK name**: `姓名/Name 朱叶 ZHU, YE` → capture both Chinese and English names simultaneously
4. **Passport number**: Chinese passport = 2 letters + 7 digits (`[DocNumber]`). Regex: `\b([A-Z]{2}\d{7})\b`

## Confidence Caveat

PaddleOCR reports confidence 0.999–1.0 on nearly every block, even when digits are completely wrong. This is a known limitation of the PP-OCRv6 recognition model on challenging images. **Do not rely on PaddleOCR's confidence scores as a reliability indicator** — use ID checksum validation and DOB cross-checks instead.

## Passport Date Extraction

Chinese passports store issue date (签发日期/Date of issue) and expiry date (有效期至/Date of expiry) at the bottom of the data page. PaddleOCR reads these as separate lines. The pipeline's `_parse_date_any_format()` function handles **5 different date formats** for each date field, tried in order:

| Strategy | Format | Example | Regex pattern |
|---|---|---|---|
| 1 | DD 月/MMM YYYY (mixed) | `04 3月/MAR 2020` | `(\d{2})\s*\d*\s*月\s*/\s*(JAN\|...)\s+(\d{4})` |
| 2 | DD MMM YYYY (English) | `03 DEC 2018` | `(\d{2})\s+(JAN\|...)\s+(\d{4})` |
| 3 | YYYY年MM月DD日 (Chinese) | `2020年03月04日` | `(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?` |
| 4 | YYYY-MM-DD (numeric) | `[DOB]` | `(\d{4})[./-](\d{2})[./-](\d{2})` |
| 5 | DD-MM-YYYY (numeric) | `04-03-2020` | `(\d{2})[./-](\d{2})[./-](\d{4})` |

### Garbled Label Matching

Chinese passport labels are sometimes partially corrupted by OCR. The expiry label patterns try multiple fallbacks: `有效期限`, `有效期[限至到]`, `Date of expiry`, and `效[限期]` (matching just the first character when the rest is garbled as `效y/Da of expiry`).

### Fused-Text Handling

When OCR fuses the DOB label with the date value (e.g. `CHINESE12 MAY 1995`), the DD MMM YYYY regex uses a `(?<!\d)` negative lookbehind instead of `\b` word boundary. This allows matching dates appended to preceding text without a word boundary, while rejecting false matches from within numeric sequences.

### 10-Year Expiry Fallback

For Chinese passports where the issue date is found but the expiry date is missing, the pipeline computes expiry = issue_date + 10 years (standard Chinese passport validity for adults). Only fires when document type is `CN_PASSPORT`.

### Date Disambiguation

To avoid confusing the DOB with issue/expiry dates, the fallback date finder only considers dates that appear **after** the DOB label in the OCR text. It searches for the DOB label pattern (including garbled variants like `Datc of bina`) and uses its text position as a cutoff point.
