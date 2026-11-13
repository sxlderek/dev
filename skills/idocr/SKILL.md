---
name: idocr
description: OCR identity documents (national IDs, passports) from multiple countries. LOCAL-ONLY by default — extracts structured fields with local Tesseract/OpenCV first; NEVER sends ID data to any remote API unless the user explicitly approves. Optional SiliconFlow Qwen3-VL remote fallback only after prior approval.
version: 2.9.0
author: <AUTHOR>
---

# ID-OCR Skill (Consolidated)

## Overview

Extract identity fields from ID document images using **local OCR (Tesseract + OpenCV) by default**. Remote engines (SiliconFlow Qwen3-VL-32B-Instruct) are used ONLY when the user has explicitly approved sending this specific ID to a remote API. Supports China (ID + Passport), Hong Kong (HKID), Japan (Passport + My Number), and Russia (Internal + International Passport).

This skill consolidates the former `id-ocr-skill`, `id-ocr-extraction`, and `idocr` skills into one.

## ⚠️ PRIVACY RULE — READ FIRST (Binding)

Contact with identity documents = handling PII. **Hard rules, never violated without explicit per-image approval:**

1. **NEVER transmit any part of an ID document — image, base64, extracted text, or fields — to ANY remote API, cloud service, or third party** (SiliconFlow, OpenRouter, vision model endpoints, GitHub, etc.) **unless the user explicitly approves it for THAT document first.** No standing approval; ask each time.
2. **WebUI Attachment Trap:** When running against a remote LLM provider, user-uploaded chat attachments are automatically embedded as base64 images into the conversation context and sent directly to the cloud model *before* any local script or tool runs.
   - When handling sensitive documents, instruct the user to **avoid WebUI chat attachments**.
   - Instead, instruct the user to place the file on the host filesystem (e.g. via local path/SFTP/mount) and provide only the local file path in chat.
   - If a script must call a cloud vision endpoint with prior user approval, run it in an isolated subprocess calling an explicit zero-data-retention (ZDR) endpoint rather than letting the main chat model ingest the raw image.
3. **Default workflow is 100% local-only:** Tesseract + OpenCV run entirely on this host. No data leaves the machine.
4. If local OCR quality is insufficient and a remote engine would help, STOP and ask the user for approval first before invoking any remote endpoint. user: "Local OCR was low-confidence on this ID. May I send this specific image to <remote engine> for better extraction?" Do NOT proceed on silence.
4. Never paste, log, or repeat ID numbers/names/DOBs into chat, memory, or any file unless the user asked for them there.
5. The `--no-remote` / local-only path is the baseline; treat any remote call as an exception that must be justified and approved afresh.
6. **Chat Attachment & Cloud LLM Leakage Trap:** When running Hermes with a remote/cloud LLM provider (e.g. OpenRouter, OmniRoute, cloud APIs), **attaching ID images in Hermes-WebUI or chat automatically transmits the image to that cloud provider** as multimodal context (`image_routing.py`) *before* any skill or local tool runs. If the user requires that ID documents NEVER leave the local machine, do NOT ask them to upload or attach ID images in a cloud-backed session. Instead, have them place the file on the local filesystem and execute `local_ocr.py` via CLI out-of-band, or ensure Hermes is running on a 100% local model.

## When to Use

Use this skill when the user types **"idocr"** or asks to OCR/scan/extract data from an ID document image.

## Local-First Pipeline (DEFINITIVE execution order)

Data NEVER leaves this host unless the user approves an exception. Run engines in this order and stop at the first that yields acceptable results:

1. **Local Tesseract + OpenCV** (default, always allowed) — run the local script:
   `python3 /opt/data/skills/productivity/idocr/scripts/local_ocr.py --input <ascii_path> --lang eng`
   - Add `--preprocess` for grayscale+Otsu thresholding on scans/blur.
   - Use `--lang chi_sim`/`chi_tra` for Chinese IDs; `eng+chi_sim` for bilingual docs.
   - `local_ocr.py` prints raw OCR text + best-effort structured fields; both are produced on-host.
   - **Phone-photo images (garbage/empty output):** escalate with `references/local-ocr-preprocessing.md` (upscale + bilateral + adaptive-threshold, then a CLAHE crop pass if binarisation stays noisy) BEFORE considering remote engines; expect name glyphs to stay unreadable while checksum-validated digits and multi-pass-confirmed address text are recoverable.
2. **Auto-description extraction** — if the image arrived via an API client and its description already lists all fields, reuse that (no new transmission; the image already reached you).
3. **Remote engines (SiliconFlow Qwen3-VL / vision model)** — **BLOCKED by default.** Only after the user explicitly approves sending this specific image to a specific remote engine. Never on standing approval, never on silence.
4. **PaddleOCR-VL remote engine (approved exception)** — when approved, prefer `PaddlePaddle/PaddleOCR-VL-1.5` on SiliconFlow (direct `api.siliconflow.cn` or OmniRoute passthrough as `siliconflow/PaddlePaddle/PaddleOCR-VL-1.5`) for dense CJK document text. Verified live on a real CN ID (2026-11-13): with its native task-prefix prompt it recovered the two name glyphs Tesseract could not read, and every field passed cross-checks (checksum, DOB↔ID digits, validity period). See the PaddleOCR-VL section below for the exact recipe and the prompt-prefix rule.

Environment notes (this host — rootless Docker, Linux x86_64):
- Local OCR env: micromamba env `ocr` at `/opt/data/tools/mamba-root/envs/ocr` (Python 3.12, OpenCV 4.10, Tesseract 5.5 with eng + chi_sim/chi_tra). Invoke the env python DIRECTLY — `/opt/data/tools/mamba-root/envs/ocr/bin/python3` — `micromamba` itself is often not on PATH in tool shells.
- **PaddlePaddle does NOT run on this host**: CPU (Intel Xeon X5650) has no AVX, and PaddlePaddle official CPU wheels require AVX (SIGILL crash). Do not attempt Paddle here; use Tesseract/OpenCV.
- Chinese/localized paths break OpenCV → always copy the image to an ASCII path first.


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
- **Attachment path translation in Hermes-WebUI container:** Attached files reported in prompts at `/home/hermeswebui/.hermes/webui/attachments/...` reside on disk at `/opt/data/webui/attachments/...` (or `$HERMES_HOME/webui/attachments/...`). If an attachment path produces FileNotFoundError, rewrite the `/home/hermeswebui/.hermes` prefix to `/opt/data`.
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
Validity: YYYYMMDD to YYYYMMDD | N/A | [unclear]
Address: (original language)
Address (EN): (English translation)
```

### Format notes (user preferences)
- **No field for date of issue or issue date** — user explicitly removed this from the output format.
- **Full Name (EN) format**: Surname first, then given name. Example: `Wu, CILIN` NOT `Cilin, WU`. The user's particular document uses the surname-first format `Wu, CILIN`.
- **Telegram auto-send**: Always send OCR results to the user's Telegram in a code box using the Bot API with `parse_mode: Markdown`.
- **Space before pipe in tables**: The user noticed and corrected spacing in tables. Use proper markdown table formatting with spaces around pipes: `| Field | Value |` not `|Field|Value|`.
- **Copy-paste ready output**: User prefers clean output that can be immediately copy-pasted without any prefix or framing text. The code block should contain ONLY the 9 fields.

**Field rules**:
| Field | Rule |
|---|---|
| Full Name (Native) | Native script name. `[unclear]` if missing |
| Full Name (EN) | Romanized name in **surname-first order with mixed case**, e.g. `Wu, CILIN` (surname capitalized, given name capitalized). The OCR may return all-caps like `WU, CILIN` — normalize case but keep surname-first order. |
| DOB | YYYY-MM-DD. `[unclear]` if illegible |
| Document type | `National ID`, `Passport`, `Driving License`, `HK/Macau Pass(港澳通行證)`, or `[unclear]` |
| Document number | Number or `[unclear]` |
| Issuing country | Full country name (e.g. "China" not "CHN") — user corrected this on [DOB]1 |
| Validity | `YYYYMMDD to YYYYMMDD` (from the card's validity period), `N/A` (no validity period), or `[unclear]` — replaces the old single Expiry line |
| Address | Original-language address exactly as printed on the document. `[unclear]` if illegible |
| Address (EN) | English translation of the address in proper English format (street, district, city, province, postal code) |

### Language Rules
- The output fields always use English labels regardless of the platform
- The surrounding commentary follows the user's language preference:
  - Cantonese → Traditional Chinese + HK vernacular/slang
  - English → plain simple English
  - Mandarin → Simplified Chinese + China vernacular/slang
- Missing/illegible fields → `[unclear]`
- No expiry date → `N/A`
- Convert ALL CAPS English names to mixed case, **given-name surname** order (e.g. `CHAN TAI MAN` → `Tai Man Chan`)
- Normalise single dates (DOB) to YYYY-MM-DD; keep the Validity line as the raw card period `YYYYMMDD to YYYYMMDD` — no separators, no reformatting

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
- Build the text payload programmatically from extracted fields (not copied from display output)

**Requirements:**
- Telegram bot token: stored in `.env` as `TELEGRAM_BOT_TOKEN` (do NOT hardcode — reading from `.env` at runtime)
- Chat ID: stored in `.env` as `TELEGRAM_HOME_CHANNEL` (this host; fall back to `TELEGRAM_CHAT_ID` on hosts that still use the old name) — check which var the host `.env` actually exports before scripting a send
- Use Python `requests` — never curl (curl shells break on Chinese characters in `--data`)
- Always use `parse_mode: "Markdown"` to render the code block correctly
- Send immediately after displaying the results — do not ask permission

---

## Vision Engine (REMOTE — blocked by default)

Remote vision engines (vision_analyze with `aa/gemma-4-31b-vision-combo`, or SiliconFlow Qwen3-VL-32B-Instruct) transmit your ID image to a cloud API. **Under the Privacy Rule above, do NOT use these unless the user explicitly approves sending this specific image to that engine.** Local Tesseract/OpenCV is the default; remote is the exception.

If the user approves a remote vision pass:
- `vision_analyze()` with `aa/gemma-4-31b-vision-combo` is the first remote choice.
- **Config:** Requires `auxiliary.vision.provider: custom:omniroute` (with colon) in config.yaml. Bare `custom` routes to Google Gemini, NOT OmniRoute. See `references/vision-config-pitfalls.md` for full details.

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

## OCR Backend (Local — default)

**Tesseract + OpenCV** via `scripts/local_ocr.py` — runs entirely on this host, no data leaves the machine. Primary and default.

### Workflow
1. User uploads ID image (photo or scan)
2. If PDF, render first page to PNG (150 DPI) locally
3. Copy image to an ASCII path (Chinese paths break OpenCV)
4. Run `python3 scripts/local_ocr.py --input <ascii_path> --lang <lang>` (optionally `--preprocess`)
5. Read the raw OCR text + structured fields from stdout; format into the 9-field output

### Remote backend (SiliconFlow Qwen3-VL-32B-Instruct) — only after explicit approval
Only for approved exceptions. Then per `scripts/ocr_via_siliconflow.py`.

### PaddleOCR-VL remote engine (approved exceptions — preferred for dense CJK)

`PaddlePaddle/PaddleOCR-VL-1.5` via SiliconFlow (`https://api.siliconflow.cn/v1/chat/completions`) or OmniRoute passthrough (`siliconflow/PaddlePaddle/PaddleOCR-VL-1.5`). Requires `SILICONFLOW_API_KEY`.

**CRITICAL — task-prefix prompts are mandatory.** PaddleOCR-VL ignores generic prompts ("Extract all text from this image") and returns multilingual gibberish. It only works with its native task prefixes:
- `OCR:` plain text extraction (the one to use for ID documents)
- `Table Recognition:` / `Formula Recognition:` / `Chart Recognition:` / `Spotting:` (adds bbox location tokens) / `Seal Recognition:`

Verified recipe (live-tested 2026-11-13 on a real CN ID, exact field recovery vs checksum ground truth):

```bash
B64=$(base64 -w0 image.jpg)
curl -s https://api.siliconflow.cn/v1/chat/completions \
  -H "Authorization: Bearer $SILICONFLOW_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"PaddlePaddle/PaddleOCR-VL-1.5\",\"max_tokens\":512,\"temperature\":0,\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64,$B64\"}},{\"type\":\"text\",\"text\":\"OCR:\"}]}]}"
```

- `temperature: 0`, `max_tokens: 512`; plain text in `choices[0].message.content`. JPG/PNG/WebP/BMP/GIF all pass as data URLs; batch = loop per image.
- **Large payloads break curl's inline `--data`** (shell-escaping of big base64) → write the JSON payload to a temp file and use `curl -d @payload.json`. This is the difference between "parameter invalid" errors and first-try success.
- Via OmniRoute passthrough: `omniroute.sxl.pp.ua` sits behind Cloudflare — python-urllib UA gets 403 (error 1010); use curl or a browser-like User-Agent.
- Older verdict in `references/test-results-2026-07-07.md` ("hallucinated, unusable") was measured with generic prompts on mixed test docs — superseded by the task-prefix findings above. On clean deskewed card crops with `OCR:`, it beat local Tesseract (recovered name glyphs Tesseract could not read at phone-photo resolution).
- Output is raw OCR text (no field labels), so map lines to the 9-field format locally and keep the checksum / DOB↔ID cross-checks as the accuracy gate — engine confidence is never the tie-breaker.

### Why local-first
- **Privacy**: no ID data leaves the host — required by the Privacy Rule.
- Works offline, no API key, no per-call cost.
- Remote (SiliconFlow) historically had better accuracy on mixed CN/EN, but that is NOT a license to transmit; it is only consulted after the user approves that document.

### Caveats
- Requires `SILICONFLOW_API_KEY` in `.env` — source before use
- Large images (300+ DPI scans) may exceed payload limits — render at 150 DPI

### Crop / deskew / export card-side images (no field extraction)

When the user asks for cleaned card images (rotate/deskew/crop/compress) rather than extracted fields, run `scripts/crop_deskew_sides.py` — the validated local pipeline (sharpness-energy bbox + brightness-drop edge refinement + text-line angle deskew + JPEG quality scan under a size cap):

```bash
/opt/data/tools/mamba-root/envs/ocr/bin/python3 scripts/crop_deskew_sides.py \
  --input <img> --output <out.jpg> --max-kb 100 --rotate auto --expected-ar 1.585
```

- Determine orientation by OCR keyword voting across the 4 rotations (`--rotate auto`). For card backs the stronger signal is the embossed doc-number digits — they read cleanly ONLY at the correct orientation, while CJK keyword votes can tie at zero; verify orientation before cropping, a wrong rotation silently produces a rotated deliverable.
- Contour-quad card detection (including `scripts/flatten_id_card.py`) fails on phone photos where the card fills the frame — bright background touches the card on all sides and no border line exists, so quad candidates are garbage streaks. Do not retry quad variants; go straight to sharpness-bbox + edge refinement, and validate the result by aspect ratio (CN ID card = 1.585; >2% deviation means a wrong bbox).
- Upscale with INTER_CUBIC, never INTER_AREA — AREA blurs when upscaling; downscale with INTER_AREA.
- Deskew via median text-line angle, warp with BORDER_REPLICATE, then trim ~3px fringe so replicated edges stay out of the deliverable.
- The cropped image still shows the full card face (name, number) — it is PII. Deliver via a single `MEDIA:` tag from `/opt/data/images/` (WebUI path rule) and remind the user; never OCR name fields into chat just because the crop succeeded.

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

**Critical finding:** Confidence ≠ accuracy. On blurry photos, PaddleOCR can report confidence 1.0 on completely wrong digits. The validation checks catch errors that confidence misses. When two OCR passes disagree on ID digits, compute each candidate's check digit locally and keep the passing one — never resolve the tie by confidence.

**Region-code geography: verify, don't recall.** The CN ID's first 6 digits encode province/prefecture/county. Do not assert the holder's locale from memory in commentary — cross-check it against the address recovered from the card, and when the two disagree the multi-pass OCR'd address wins.

---

## Scripts Reference

### Primary
| Script | Purpose |
|---|---|
| `scripts/local_ocr.py` | **Primary OCR (local-first, default)** — Tesseract + OpenCV, runs entirely on this host. Raw text + structured fields to stdout. Never sends data off-host. |
| `scripts/crop_deskew_sides.py` | Crop/deskew/orient card-side photos to JPEG under a size cap — validated phone-photo pipeline for cases where quad detection fails (card fills the frame). |
| `scripts/ocr_via_siliconflow.py` | **Remote OCR (blocked by default)** — SiliconFlow Qwen VL API. Only after explicit user approval of that specific ID (Privacy Rule). |
| Telegram delivery (inline) | No dedicated script — send via a short Python `requests` POST to `https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage` with `parse_mode: "Markdown"`, reading the token and chat ID (`TELEGRAM_HOME_CHANNEL` on this host) from `.env` at runtime. Never curl (Chinese char escaping). |

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

## Pitfalls

The user has corrected several issues. Be aware of all of them to avoid repeating mistakes:

0. **Chat Attachments sent to Cloud LLM Provider**: Attaching images in Hermes-WebUI or chat while using a cloud inference provider automatically transmits the image to that cloud provider as multimodal context before any tool runs. The model may extract fields with high accuracy directly from that multimodal input, bypassing local-only intent. For air-gapped/strict local processing, place files on disk directly and run local scripts via CLI, or switch Hermes to a 100% local model.
1. **Output format is 9 fields, not 7 or 8**: Validity, Address and Address (EN) are required; "Issue date" stays removed — do not reintroduce it. Exact format is shown at the top of this document. When the user adds or changes a field, update ALL format references in this file in the same pass (template, field-rules table, field-count mentions, date-normalisation rule) — partial updates leave contradicting rules behind.
2. **Platform rendering differs** (user correction [DOB]1): Hermes Desktop GUI does not render code fences — use plain text literal newlines. Web/Cherry/OpenWebUI render fences correctly. See `references/platform_rendering.md` for the full breakdown.
3. **Telegram E2EE caveat** (user research [DOB]1): Regular Telegram Cloud Chats are **NOT** end-to-end encrypted — Telegram stores the keys. Secret Chats are E2EE but device-specific and don't sync. If the user wants true E2EE, Signal is the only major messenger that provides it by default. See `references/telegram-privacy-and-e2ee.md`.
4. **Photo quality is the real bottleneck** — no OCR engine fixes a blurry photo
5. **Chinese paths break OpenCV** → always copy to ASCII path first
6. **PaddleOCR overconfidence**: reports 1.0 even on wrong digits
7. **~7s per image** on CPU per engine for local pipeline
8. **Model download ~200MB** on first PaddleOCR invocation
9. **API-attached images are not on disk**: When the user sends images via Open WebUI, Cherry Studio API, or similar API-based clients, the images exist as in-memory data URLs — not as local files. The `ocr_via_siliconflow.py --input` script cannot reach them. Workarounds: (a) ask the user to upload the file directly, (b) use `write_file` to save a local copy if the data URL is available, or (c) call the SiliconFlow API directly with the base64-encoded image from the data URL using the dual-image pattern.
10. **Vision provider "aa" combo may be down** — vision_analyze() relies on the active model provider. When the "aa" combo is down (404 model_not_found), the local Tesseract path (`scripts/local_ocr.py`) is the default recovery — never auto-fall back to a remote engine. A remote engine (`scripts/ocr_via_siliconflow.py`) may only be used after the user explicitly approves sending that ID to it (Privacy Rule).
11. **Vision provider config is non-trivial** — the `aa/` model prefix is parsed as a provider name, and config reload requires a full GUI restart (gateway restart is NOT sufficient). See `references/vision-config-pitfalls.md` before touching vision config.
12. **PaddleOCR-VL needs task-prefix prompts** — a generic "extract all text" prompt returns multilingual gibberish and once earned the model a false "hallucinated, unusable" verdict. Always send its native prefixes (`OCR:`, `Table Recognition:`, ...) — see the PaddleOCR-VL section. Also: large base64 payloads fail when passed to curl as inline `--data` shell strings; write the JSON payload to a file and use `curl -d @file.json`.

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
| PaddleOCR-VL-1.5 | Same documents (generic prompt) | ❌ Hallucinated, unusable |
| PaddleOCR-VL-1.5 | Deskewed CN ID card crops + native `OCR:` task prefix (2026-11-13) | ✅ Perfect field recovery — beat local Tesseract on name glyphs; requires task-prefix prompts (see PaddleOCR-VL section) |

See `references/test-results-2026-07-07.md` for full comparison.
See `references/test-results-2026-07-11.md` for live test with Chinese passport (post-consolidation).
