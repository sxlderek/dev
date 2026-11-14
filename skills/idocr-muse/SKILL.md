---
name: idocr-muse
description: OCR identity documents (national IDs, passports) from multiple countries and extract structured fields. Muse reads the document images directly — no external OCR service. Also flattens card photos to <150KB JPGs and extracts the printed headshot photo.
version: 3.1.0
author: <AUTHOR>
---

# ID-OCR Skill

## Overview

Extract identity fields from ID document images. On Muse the extraction is done by reading the uploaded images directly — there is no external OCR API, no bot integration, and no separate vision provider to configure.

Supports China (ID card + passport), Hong Kong (HKID), Japan (passport + My Number card), and Russia (internal + international passport).

## When to Use

Use this skill when the user types **"idocr"** or asks to OCR/scan/extract data from an ID document image.

## Default Deliverables

For each idocr run, deliver all three, presented inline in the reply:

1. The 9-field extraction (code block below).
2. The flattened front and back card JPGs (<150 KB each) — see Card Photo Flattening.
3. The extracted headshot photo — see Headshot Photo Extraction.

## Required Output Fields (in exact order)

Return results in a **Markdown code block** by default. Each field on its own line:

```
Full Name (Native): ...
Full Name (EN): Surname, Given
DOB: YYYY-MM-DD
Document type: National ID | Driving License | Passport | HK/Macau Pass(港澳通行證) | [unclear]
Document number: ... | [unclear]
Issuing country of the document: ...
Expiry: YYYY-MM-DD | N/A | [unclear]
Address: (original language)
Address (EN): (English translation)
```

### Format notes (user preferences)
- **No field for date of issue** — the user explicitly removed it from the output format. Do not reintroduce it.
- **Full Name (EN) format**: surname first, then given name — `Doe, JOHN`, NOT `John, DOE`.
- **Copy-paste ready output**: the code block should contain ONLY the 9 fields, with no prefix or framing text inside it.
- Use proper markdown table formatting with spaces around pipes: `| Field | Value |`, not `|Field|Value|`.

**Field rules**:
| Field | Rule |
|---|---|
| Full Name (Native) | Native script name. `[unclear]` if missing |
| Full Name (EN) | Romanized name in **surname-first order**, e.g. `Doe, JOHN`. If the document prints it all-caps or given-name-first, normalize the case but keep surname-first order. |
| DOB | YYYY-MM-DD. `[unclear]` if illegible |
| Document type | `National ID`, `Passport`, `Driving License`, `HK/Macau Pass(港澳通行證)`, or `[unclear]` |
| Document number | Number or `[unclear]` |
| Issuing country | Full country name (e.g. "China", not "CHN") |
| Expiry | YYYY-MM-DD, `N/A` (no expiry), or `[unclear]` |
| Address | Original-language address exactly as printed on the document. `[unclear]` if illegible |
| Address (EN) | English translation of the address in proper English format (street, district, city, province, postal code) |

### Language Rules
- The output field labels are always in English.
- The surrounding commentary follows the user's language.
- Missing/illegible fields → `[unclear]`; no expiry date → `N/A`.
- Normalise all dates to YYYY-MM-DD.

## Workflow

1. If no image was provided, ask for one: a clear, in-focus photo or scan, front **and** back if the document has fields on the back, all four corners visible, no heavy glare.
2. Read the images directly and extract the fields. For two-sided documents (e.g. CN ID cards), read **both sides together** before extracting — the fields are split across the sides.
3. Run the cross-checks below and report the result with the extraction.
4. Produce the flattened card images and the headshot (Default Deliverables).

### Validation & Cross-Checks

| Check | What it catches |
|---|---|
| CN ID checksum (ISO 7064 MOD 11-2) | Wrong digits in the ID number |
| DOB ↔ ID number digits 7–14 | Inconsistent DOB vs the number's embedded birthdate |
| Region code (ID digits 1–6) ↔ printed address | Wrong digits; also identifies the original registration district |
| Gender digit (ID digit 17: odd = male, even = female) ↔ printed sex | Wrong digits |

Notes on apparent mismatches — flag them factually, do not fail fields over them:
- The region code records the holder's **original registration district**, which often differs from the current address.
- The issuing authority may differ from the address district — cards are routinely applied for away from the registered address.
- Validity length follows the holder's age band at issue (CN: under 16 → 5 years; 16–25 → 10; 26–45 → 20; 46+ → long-term). A term that doesn't fit the age band is worth one factual note.

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

Full field-level reference in `references/country-profiles.md`. Label hints and the image request checklist are in `references/extraction-notes.md`.

### Name Parsing by Country
- **Chinese**: surname is the first 1–2 characters (single-char surnames are most common; compound ones include 欧阳, 司马). The rest is the given name.
- **Japanese**: separate 氏名 and 名前 fields on the passport — no splitting needed.
- **Russian**: separate Фамилия, Имя, Отчество fields — no splitting needed.
- **HKID**: English name is printed `SURNAME, Given` — keep it in that surname-first order for the output.
- **MRZ**: ICAO 9303 standard — surname << given names.

### Date Parsing
| Format | Example | Countries |
|---|---|---|
| YYYY年MM月DD日 | 1990年07月10日 | CN (ID/passport) |
| YYYY-MM-DD / YYYY.MM.DD | 1990-01-15 | CN, JP |
| DD MMM YYYY | 02 SEP 1994 | Passports (CN, JP) |
| DD.MM.YYYY | 15.05.1985 | RU |
| DD-MM-YYYY | 15-03-1985 | HK |

## Card Photo Flattening & JPG Export (<150KB)

Use `scripts/flatten_and_export.py`:

```bash
python3 scripts/flatten_and_export.py --input front.jpg back.jpg --out-dir <out-dir> --names front,back
```

Per image it: applies EXIF rotation → detects the card outline (Otsu threshold first; on pale cards photographed on pale backgrounds the gray levels overlap and Otsu merges card and background, so the script falls back to GrabCut segmentation with the image border as background — force it with `--strategy grabcut` if a warp comes out wrong) → perspective-warps ("deskews") to the ID-1 card ratio (85.6 × 54 mm) at 1200×757 → saves JPEG, stepping quality down (then size down) until the file is under 150 KB (it targets ≤149,500 bytes, so it passes under either KB reading).

Rules:
- **Corner order is the whole ballgame**: tl = min(x+y), br = max(x+y), tr = min(y−x), bl = max(y−x). Swapping tr/bl still produces a neat-looking image, but transposed and mirrored with unreadable text.
- **Always read the output images back and verify** the text is upright and legible before presenting them — never present an unverified warp. Both automatic detectors can fail (a pale card's edge can be segmented as background, leaving a skewed or clipped crop); if the warp is wrong, locate the four card corners directly and warp from those.
- Present the finished JPGs **inline as image attachments** in the reply.

## Headshot Photo Extraction

Use `scripts/extract_headshot.py` on the **flattened** front card (output of the flattening step above):

```bash
python3 scripts/extract_headshot.py --input id-card-front.jpg --output id-headshot.jpg
```

How it works: OpenCV DNN face detection (the `models/opencv-face` Caffe model) finds the face, then the printed photo rectangle is derived from the face box using the standard CN ID photo proportions (26 × 32 mm, w/h = 0.8125; face width ≈ 0.571 × photo width; photo top ≈ face top − 0.234 × face height; photo horizontally centred on the face). The crop is upscaled 2× and saved as JPEG.

Rules and pitfalls (learned on real cards, 2026-11-14):
- **OpenCV 4.x required** — OpenCV 5 removed `cv2.dnn.readNetFromCaffe`, which the face model needs.
- Rectangle-detection approaches failed on flattened cards, and a naively derived photo box overshoots (catching card guilloche at the top and a strip of the ID-number row at the bottom). The face-anchored derivation in this script is the method that works.
- **Always read the crop back and verify before presenting**: the photo's own background must show on all four sides, with no card text, digits or guilloche included. If the box is off, adjust from the reported face box rather than re-guessing blind.
- Present the finished headshot **inline as an image attachment** in the reply.

## Social Avatar Generation (on request)

When the user asks for an avatar from the ID photo, generate a Japanese anime-style avatar from the **extracted headshot** (not the full card):

- Use the headshot as the identity reference for image generation, so the avatar keeps the person's recognizable features (hairstyle and hair colour, face shape, top colour).
- Style: Japanese cartoon / anime, clean and suitable as a social-network profile picture.
- **Format: 1:1 square.**
- **Pose: head in three-quarter view, eyes in a side-glance toward the viewer — not looking straight at the camera.**
- A soft decorative background (e.g. cherry blossoms) is fine.
- Verify the result visually before presenting it, and present it **inline as an image attachment**.

This is an on-request extra, not part of the standard deliverables in "Default Deliverables" above.

## Scripts Reference

| Script | Purpose |
|---|---|
| `scripts/flatten_and_export.py` | **Photo cleanup** — EXIF-rotate, deskew (perspective warp to ID-1 ratio), crop to the card, export JPG under a size cap (default <150 KB) for inline presentation. Detection: Otsu with GrabCut fallback (`--strategy`). |
| `scripts/extract_headshot.py` | **Headshot extraction** — DNN face detection on the flattened card, photo rectangle derived from CN ID photo proportions (26 × 32 mm), 2× upscale, JPEG out. Needs OpenCV 4.x. `--model-dir` defaults to this skill's `models/opencv-face`. |

## Dependencies

- **Extraction**: Muse's own vision — no API keys or external services.
- **Image scripts**: Python with `pillow`, `numpy`, and OpenCV 4.x (`opencv-python-headless<5`).
- **Face model**: `models/opencv-face/` (`deploy.prototxt` + `res10_300x300_ssd_iter_140000_fp16.caffemodel`).

## PII Hygiene

This skill processes identity documents containing PII. Handle with care:

1. **Never hardcode PII** in SKILL.md or any committed reference file — use placeholders (`[Name]`, `[DocNumber]`, `[DOB]`) and synthetic examples only.
2. **Scan the entire skill** before publishing anywhere — PII hides in reference files and test notes, not just the main document.
3. Deliver extracted data in the chat it was requested in; don't copy it into other documents or skills.

## Pitfalls

1. **Output format is 9 fields, exactly as shown at the top of this document** — "Issue date" was removed by user correction and must not be reintroduced; "Address" and "Address (EN)" were added on 2026-11-14.
2. **Photo quality is the real bottleneck** — no processing fixes a blurry or glare-covered photo. Ask for a better photo rather than guessing fields.
3. **Verify every derived image visually before presenting it** — flattened warps and headshot crops can be wrong while looking tidy (transposed, clipped, or skewed). Read them back, every time.
4. **Two-sided documents**: never extract from one side alone — CN ID personal details and issuing authority/validity are on opposite sides.
