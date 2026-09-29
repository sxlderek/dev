---
name: idocr
description: OCR identity documents (national IDs, passports) from multiple countries — extract structured fields using `aa/gemma-4-31b-vision-combo` (primary) or SiliconFlow Qwen3-VL-32B-Instruct (fallback). Optional local PaddleOCR fallback.
version: 2.3.0
author: <AUTHOR>
---

# ID-OCR Skill (Consolidated)

## Overview

Extract identity fields from ID document images using **SiliconFlow Qwen3-VL-32B-Instruct** (primary) or local **PaddleOCR/EasyOCR/Tesseract** (offline fallback). Supports China (ID + Passport), Hong Kong (HKID), Japan (Passport + My Number), and Russia (Internal + International Passport).

This skill consolidates the former `id-ocr-skill`, `id-ocr-extraction`, and `idocr` skills into one.

## What Changed in This Version (2.1.0)

- Updated to reflect user corrections from a previous session:
  - Finalized the 7-field output format (removed `Issue date`)
  - Documented Telegram Bot API auto-send for code box rendering on platforms that can't render markdown fences
  - Documented Hermes Desktop GUI rendering behavior with code fences vs. images. See `references/platform_rendering.md`.
  - Captured Telegram E2EE research. See `references/telegram-privacy-and-e2ee.md`.
- Updated all references (test results + platform rendering + Telegram privacy)

## When to Use

Use this skill when the user types **"idocr"** or asks to OCR/scan/extract data from an ID document image.

## Performance Shortcut: Auto-Description Extraction

When images arrive via API-based clients (Open WebUI, Cherry Studio, etc.), Hermes may auto-describe them before you see them. If those descriptions contain the full readable text (names, numbers, dates), skip SiliconFlow and extract fields directly from the description. This is faster (instant vs 2-5s) and costs zero API tokens.

When to use this shortcut:
- Auto-description has all visible fields (as it did this session — name, DOB, ID number, issuing authority, expiry were all spelled out)
- Document is a common type (CN ID, passport, HKID)
- Image quality is good (well-lit, in-focus)

When NOT to use:
- Description is vague ("an ID card with some text")
- Image is blurry or low quality
- Document type is unusual or multilingual
- You need guaranteed OCR accuracy on tricky fields

Always verify extracted fields for internal consistency (DOB matches ID number digits, etc.). The auto-description is a free bonus, not a guaranteed feature.

## Core Rules

### Image Requirements
- Ask for the image first if none provided
- Document can be in any language — ask if unclear
- Copy to ASCII path if using the local PaddleOCR pipeline (Chinese paths break OpenCV)
### Required Output Fields (in exact order)

Return results in a **Markdown code block** by default (web clients, Cherry Studio, Open WebUI render them fine). Each field on its own line:

```
Full Name (Native): ...
Full Name (EN): Surname, Given
DOB: YYYY-MM-DD
Document type: National ID | Driving License | Passport | HK/Macau Pass(港澳通行證) | [unclear]
Document number: ... | [unclear]
Issuing country of the document: ...
Expiry: YYYY-MM-DD | N/A | [unclear]
```

### Format notes (user preferences)
- **No field for date of issue or issue date** — user explicitly removed this from the output format.
- **Full Name (EN) format**: Surname first, then given name. Example: `Wu, CILIN` NOT `Cilin, WU`. The user's particular document uses the surname-first format `Wu, CILIN`.
- **Telegram auto-send**: Always send OCR results to the user's Telegram in a code box using the Bot API with `parse_mode: Markdown`.
- **Space before pipe in tables**: The user noticed and corrected spacing in tables. Use proper markdown table formatting with spaces around pipes: `| Field | Value |` not `|Field|Value|`.
- **Copy-paste ready output**: User prefers clean output that can be immediately copy-pasted without any prefix or framing text. The code block should contain ONLY the 7 fields.

**Field rules**:
| Field | Rule |
|---|---|
| Full Name (Native) | Native script name. `[unclear]` if missing |
| Full Name (EN) | Romanized name in **surname-first order with mixed case**, e.g. `Wu, CILIN` (surname capitalized, given name capitalized). The OCR may return all-caps like `WU, CILIN` — normalize case but keep surname-first order. |
| DOB | YYYY-MM-DD. `[unclear]` if illegible |
| Document type | `National ID`, `Passport`, `Driving License`, `HK/Macau Pass(港澳通行證)`, or `[unclear]` |
| Document number | Number or `[unclear]` |
| Issuing country | Full country name (e.g. "China" not "CHN") — user corrected this on [DOB]1 |
| Expiry | YYYY-MM-DD, `N/A` (no expiry), or `[unclear]` |

### Language Rules
- The output fields always use English labels regardless of the platform
- The surrounding commentary follows the user's language preference:
  - Cantonese → Traditional Chinese + HK vernacular/slang
  - English → plain simple English
  - Mandarin → Simplified Chinese + China vernacular/slang
- Missing/illegible fields → `[unclear]`
- No expiry date → `N/A`
- Convert ALL CAPS English names to mixed case, **given-name surname** order (e.g. `CHAN TAI MAN` → `Tai Man Chan`)
- Normalise all dates to YYYY-MM-DD

### Rendering Platform Detection

| Platform | Code fences | Images | Recommended format |
|---|---|---|---|
| Hermes Desktop GUI | ✗ Shows raw backticks | ✓ `![alt](url)` with HTTP(S) URL | Plain text, one field per line. For images, use markdown image syntax with GitHub-hosted URL. |
| Cherry Studio / Open WebUI / Web | ✓ Fenced blocks render | ✓ `![alt](url)` | Markdown with fenced code block. |
| Telegram (via bridge) | ✗ No formatting | ✗ | Send via Bot API with `parse_mode: "Markdown"` (see Telegram Auto-Send section). |
| WhatsApp | ✗ No formatting | ✗ | Plain text only. |

**Rule**: Default to plain text on Hermes Desktop GUI. Default to fenced code block on Web/Cherry/OpenWebUI. For Telegram, always provide plain text AND send via Bot API with `parse_mode: Markdown` for proper rendering.

### Telegram Auto-Send (Always)

After displaying results, **also send the results to the user's Telegram** in a code box using the Telegram Bot API:

**Endpoint:**
```json
POST https://api.telegram.org/bot/sendMessage
```

```json
{
  "chat_id": [CHAT_ID],
  "text": "```\nFull Name (Native): ...\nFull Name (EN): ...\nDOB: ...\n...\n```",
  "parse_mode": "Markdown"
}
```

**Critical:**
- **Never hardcode tokens or chat IDs in this file** — reference `.env` vars only
- Use Python `requests`, never curl (Chinese chars break curl `--data` on Windows MSYS/Git-Bash)
- Build the text payload programmatically from extracted fields (not copied from display output)
```

**Requirements:**
- Telegram bot token: stored in `.env` as `TELEGRAM_BOT_TOKEN` (do NOT hardcode — reading from `.env` at runtime)
- Chat ID: stored in `.env` as `TELEGRAM_CHAT_ID`
- Use Python `requests` library (not curl) to avoid shell escaping issues with Chinese characters
- Always use `parse_mode: "Markdown"` to render the code block correctly
- Send immediately after displaying the results — do not ask permission
- Build the text payload programmatically from the extracted fields, not from the display output
- Use Python `requests` library (NOT curl) — curl on Windows/MSYS breaks on Chinese characters

**Helper script:** `scripts/send_telegram_code_block.py` (reads from `.env` automatically)

---

## Vision Model (Primary)

**Primary: `aa/gemma-4-31b-vision-combo`** — use `vision_analyze()` with this model for ID document reading. This is the first choice for vision-based OCR.

**Config:** Requires `auxiliary.vision.provider: custom:omniroute` (with colon) in config.yaml. Bare `custom` routes to Google Gemini, NOT OmniRoute. See `references/vision-config-pitfalls.md` for full details.

When `vision_analyze` fails (provider down, model_not_found), fall back to **SiliconFlow Qwen3-VL-32B-Instruct** API.

## Config Reload Protocol (Critical)

Editing `config.yaml` → `vision_analyze` does NOT automatically pick up changes. You MUST restart the Hermes GUI process.

| Command | What it restarts | Vision config reloaded? |
|---------|-----------------|------------------------|
| `hermes gateway restart` | Messaging gateway only | ❌ NO |
| Full GUI restart (kill + relaunch) | Agent host + gateway | ✅ YES |

**Full GUI restart procedure (Windows):**
```powershell
# In PowerShell (not MSYS/Git-Bash):
taskkill /f /im Hermes.exe
hermes desktop
```

**Symptoms of stale config:**
- `grep` shows correct values in config.yaml but `vision_analyze` still fails with old error
- Provider still shows as `aa` instead of `custom:omniroute`
- `hermes auth list` shows `custom:omniroute` as empty (`[]`)

See `references/vision-config-pitfalls.md` for full debug checklist.

## OCR Backend (Fallback)

**SiliconFlow Qwen3-VL-32B-Instruct** via API. No local dependencies.

### Workflow
1. User uploads ID image (photo or scan)
2. If PDF, render first page to PNG at 150 DPI
3. Call `https://api.siliconflow.cn/v1/chat/completions` with `Qwen/Qwen3-VL-32B-Instruct`
4. Send base64-encoded image + extraction prompt at temperature 0.0
5. Parse structured fields from response

### Script
```bash
source ~/AppData/Local/hermes/.env
python3 scripts/ocr_via_siliconflow.py --input /path/to/id.jpg
```

### Dual-Side Processing (CN ID Card)
Chinese ID cards split info across front and back. Send **both images in one API call** for merged extraction:

```python
# Both images in a single content array — put back (info side) first
"content": [
  {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{back_b64}"}},
  {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{front_b64}"}},
  {"type": "text", "text": "These are the two sides of a Chinese national ID card. Extract ALL fields."}
]
```

See `references/dual-image-processing.md` for full example.

### Why SiliconFlow over local OCR
- Perfect accuracy on mixed CN/EN documents (tested)
- No local dependencies (no Tesseract, no OpenCV, no model weights)
- Handles any language, any layout
- ~2,700 tokens per call

### Caveats
- Requires `SILICONFLOW_API_KEY` in `.env` — source before use
- Large images (300+ DPI scans) may exceed payload limits — render at 150 DPI

---

## Offline Fallback (Legacy — Scripts **Removed**)

The former local PaddleOCR pipeline (`extract_id.py`, `paddleocr_helper.py`) was in `id-ocr-extraction` which has been consolidated into this skill. Those scripts are **no longer available** — the local pipeline is archived.

If offline OCR is needed again, restore the scripts from the git history or wiki backups at `<WORKSPACE>/...`.

### Legacy Engine Stack (for reference)

| Priority | Engine | Accuracy | Speed | Notes |
|---|---|---|---|---|
| 1° | PaddleOCR PP-OCRv6 | Best (CJK) | ~7s CPU | Python 3.12 subprocess |
| 2° | EasyOCR | Good | ~7s CPU | Python 3.14 |
| 3° | Tesseract v5+ | Poor (photos) | ~1s | Last resort |

### Limitations
- Chinese paths break OpenCV → always copy to ASCII path first
- PaddleOCR overconfidence: reports 1.0 even on wrong digits
- Python 3.12 subprocess bridge required (PaddlePaddle doesn't support 3.14)
- Model download ~200MB on first invocation

---

## Multi-Country Support

| Country | Document | Key Fields | Date Format |
|---|---|---|---|
| China 🇨🇳 | ID Card (身份证) | 姓名, 性别, 民族, 出生, 住址, 公民身份号码, 签发机关, 有效期限 | YYYY年MM月DD日 |
| China 🇨🇳 | Passport (护照) | 姓名/Name, 性别/Sex, 出生日期/DOB, 护照号, MRZ | YYYY-MM-DD or YYYY年MM月DD日 |
| Hong Kong 🇭🇰 | HKID (香港身份证) | 中文姓名, 英文姓名, 出生日期, 身份證號碼, 簽發日期 | DD-MM-YYYY |
| Japan 🇯🇵 | Passport (旅券) | 氏名, Surname, 名前, 生年月日, 旅券番号 | YYYY.MM.DD |
| Japan 🇯🇵 | My Number Card | 氏名, 生年月日, 個人番号 | YYYY年MM月DD日 |
| Russia 🇷🇺 | Internal Passport (Паспорт РФ) | Фамилия, Имя, Отчество, Дата рождения, Номер | DD.MM.YYYY |
| Russia 🇷🇺 | International Passport (Загранпаспорт) | Same as internal + MRZ | DD.MM.YYYY |

Full field-level reference in `references/country-profiles.md`.

### Name Parsing by Country
- **Chinese**: 200-surname lookup table. Single-char (李王张陈) → ~80%; compound (欧阳司马) → ~20%. Remaining text is given name.
- **Japanese**: Separate 氏名 and 名前 fields on passport — no splitting needed.
- **Russian**: Separate Фамилия, Имя, Отчество fields — no splitting needed.
- **HKID**: English name in SURNAME, Given format (comma-separated) — swap to **given-name surname** order for output (e.g. `Chan, Tai Man` → `Tai Man Chan`)
- **MRZ**: ICAO 9303 standard — surname << given names.

### Date Parsing
| Format | Example | Countries |
|---|---|---|
| YYYY年MM月DD日 | 1990年07月10日 | CN (ID/passport) |
| YYYY-MM-DD / YYYY.MM.DD | 1990-01-15 | CN, JP |
| DD MMM YYYY | 02 SEP 1994 | Passports (CN, JP) |
| DD.MM.YYYY | 15.05.1985 | RU |
| DD-MM-YYYY | 15-03-1985 | HK |

---

## Validation & Warning System

| Check | What it catches | Trigger |
|---|---|---|
| Confidence threshold | Blurry/unreadable photos | `_ocr_min_confidence` < 0.3 |
| CN ID checksum (ISO 7064 MOD 11-2) | Wrong ID number digits | Check digit mismatch |
| DOB ↔ ID cross-check | Inconsistent DOB vs ID digits 7-14 | ID number DOB ≠ extracted DOB |

**Critical finding:** Confidence ≠ accuracy. On blurry photos, PaddleOCR can report confidence 1.0 on completely wrong digits. The validation checks catch errors that confidence misses.

---

## Scripts Reference

### Primary
| Script | Purpose |
|---|---|
| `scripts/ocr_via_siliconflow.py` | **Primary OCR** — SiliconFlow Qwen VL API. Uses base64 image + temperature 0.0 for deterministic ID extraction. |
| `scripts/send_telegram_code_block.py` | **Telegram delivery** — wraps extracted fields in Markdown code block and sends via Bot API with `parse_mode: Markdown`. Accepts `--text "..."`, `--file /path/to/results.txt`, or stdin. Reads `TELEGRAM_BOT_TOKEN` from `.env`. Use Python, never curl (Chinese char escaping). |

### Legacy (Avatar/Photo Extraction + Old PaddleOCR Pipeline)
| Script | Purpose |
|---|---|
| `scripts/crop_headshot_opencv_dnn.py` | Crop ID headshot with OpenCV face detection |
| `scripts/crop_id_photo_opencv.py` | Crop ID photo rectangle using OpenCV |
| `scripts/extract_id_photo_fullface.py` | End-to-end ID photo extraction with MediaPipe |
| `scripts/extract_id_photo_rect_verified.py` | ID photo rectangle extraction with face verification |
| `scripts/flatten_id_card.py` | Deskew/flatten ID via card-boundary perspective transform |
| `scripts/mediapipe_facecheck.py` | Full-face verification via MediaPipe FaceMesh |

---

## Dependencies

### SiliconFlow Path
- `SILICONFLOW_API_KEY` in `.env`
- Optional: `pymupdf` for PDF input (`pip install pymupdf`)

### Local Pipeline Path
| Component | Target | Command |
|---|---|---|
| PaddleOCR 3.7.0 + PaddlePaddle 3.2.2 | Python 3.12 (scoop) | `pip install paddleocr paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/` |
| EasyOCR | Python 3.14 (venv) | `pip install easyocr` |
| Tesseract v5+ | System | `scoop install tesseract` + language packs |
| Pillow, numpy | Python 3.14 | `pip install Pillow numpy` |

Python 3.12 path: `<WORKSPACE>/...`

10. **Use Python requests, never curl, for Chinese character support** — curl shells out to MSYS/Git-Bash and Chinese chars in `--data` break. Python's requests.post(url, json=payload) always works.
11. **Vision provider ("aa") may be broken** — vision_analyze() relies on the active model provider. When "aa" combo is down (404 model_not_found), fall back to ocr_via_siliconflow.py (SiliconFlow Qwen3-VL) directly. SiliconFlow is the primary OCR path — don't wait for vision_analyze to work.

## Pitfalls

## Pitfalls

The user has corrected several issues. Be aware of all of them to avoid repeating mistakes:

1. **Output format is 7 fields, not 8** (user correction [DOB]1): Removed "Issue date" from the required output. Do not reintroduce it. Exact format is shown at the top of this document.
2. **Platform rendering differs** (user correction [DOB]1): Hermes Desktop GUI does not render code fences — use plain text literal newlines. Web/Cherry/OpenWebUI render fences correctly. See `references/platform_rendering.md` for the full breakdown.
3. **Telegram E2EE caveat** (user research [DOB]1): Regular Telegram Cloud Chats are **NOT** end-to-end encrypted — Telegram stores the keys. Secret Chats are E2EE but device-specific and don't sync. If the user wants true E2EE, Signal is the only major messenger that provides it by default. See `references/telegram-privacy-and-e2ee.md`.
4. **Photo quality is the real bottleneck** — no OCR engine fixes a blurry photo
5. **Chinese paths break OpenCV** → always copy to ASCII path first
6. **PaddleOCR overconfidence**: reports 1.0 even on wrong digits
7. **~7s per image** on CPU per engine for local pipeline
8. **Model download ~200MB** on first PaddleOCR invocation
9. **API-attached images are not on disk**: When the user sends images via Open WebUI, Cherry Studio API, or similar API-based clients, the images exist as in-memory data URLs — not as local files. The `ocr_via_siliconflow.py --input` script cannot reach them. Workarounds: (a) ask the user to upload the file directly, (b) use `write_file` to save a local copy if the data URL is available, or (c) call the SiliconFlow API directly with the base64-encoded image from the data URL using the dual-image pattern.
10. **Use Python requests, never curl, for Chinese character support** — curl shells out to MSYS/Git-Bash and Chinese chars in `--data` break. Python's requests.post(url, json=payload) always works.
11. **Vision provider config is non-trivial** — the `aa/` model prefix is parsed as a provider name, and config reload requires a full GUI restart (gateway restart is NOT sufficient). See `references/vision-config-pitfalls.md` before touching vision config.
## Pitfalls

The user has corrected several issues. Be aware of all of them to avoid repeating mistakes:
|---|---|---|---|
| Hermes Desktop GUI | ✗ Raw backticks | ✓ HTTP(S) URL only | Plain text, one field per line. For images: `![alt](https://url)`. Never local paths. |
| Cherry Studio / Open WebUI / Web | ✓ Fenced blocks render | ✓ | Markdown fenced code block. |
| Telegram (via bridge) | ✗ No formatting | ✗ | Bot API with `parse_mode: "Markdown"`. |
| WhatsApp | ✗ No formatting | ✗ | Plain text only. |

**Rule**: Default to plain text on Hermes GUI. Default to fenced code block on Web/Cherry/OpenWebUI. For Telegram, auto-send via Bot API with `parse_mode: Markdown`.

## Displaying Images on Hermes Desktop GUI

- `![alt](https://url)` — **Works** ✓ (HTTP(S) URLs only)
- `![alt](C:\local\path)` — **Does NOT work** ✗
- `vision_analyze(local_path)` — **Does NOT render** on Desktop GUI ✗
- **Solution: Upload to GitHub via API → use GitHub blob URL (`github.com/{owner}/{repo}/blob/{branch}/{path}`) in markdown image syntax (raw.githubusercontent.com 404s for private repos). See `github-publish` skill for full conventions.**

### References
- `references/telegram-auto-send.md` — How to send OCR results to Telegram
- `references/platform_rendering.md` — Platform-specific rendering notes
- `references/pii-sanitization.md` — Cross-platform PII scrubbing workflow (legacy version)
- `references/prompts-chat-pii-workflow.md` — **Platform-specific workflow for sanitizing prompts.chat skills when no delete endpoint exists** (the workflow used this session: scan → fetch via MCP → sanitize in-place → verify → git filter-repo for repos → final scan)

---

## PII Hygiene

This skill processes identity documents containing PII. Handle with care:

1. **Never hardcode PII** in SKILL.md or any committed reference file
2. **Use placeholders**: `[Name]`, `[DocNumber]`, `[DOB]`, `[Expiry]`, `[Country]`
3. **When publishing to public repos** (GitHub, prompts.chat): redact all examples first
4. **Reference files** should use synthetic or redacted data only
5. **Test results** should reference `[Name]` not real names
6. **Env vars** for tokens (`TELEGRAM_BOT_TOKEN`, `SILICONFLOW_API_KEY`, `TELEGRAM_CHAT_ID`) should never be committed — read from `.env` at runtime
7. **Scan the entire repo** before publishing — PII hides in scripts, configs, test results, not just Markdown

**Pre-publish checklist**:
- [ ] No Chinese/real names in any file
- [ ] No passport/ID numbers
- [ ] No real DOBs or expiry dates
- [ ] No tokens or API keys
- [ ] No real chat IDs (replace with `[CHAT_ID]`)
- [ ] `references/pii-sanitization.md` consulted for full workflow

See `references/pii-sanitization.md` for the full PII scrubbing workflow (scan → fix → filter-repo rewrite → verify).

---

| Model | Test Document | Verdict |
|---|---|---|
| Qwen3-VL-32B-Instruct | HK business letter + synthetic CN ID | ✅ Perfect extraction |
| DeepSeek-OCR | Same documents | ⚠️ Usable — spaces stripped, Chinese garbled |
| PaddleOCR-VL-1.5 | Same documents | ❌ Hallucinated, unusable |

See `references/test-results-2026-07-07.md` for full comparison.
See `references/test-results-2026-07-11.md` for live test with Chinese passport (post-consolidation).
