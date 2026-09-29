---
name: docren
description: "Document renaming assistant that suggests structured filenames based on document content (PDF/Word). Format: YYYYMMDD company-slug document-number short-description"
version: 3.0.0
license: MIT
---

# Document Renaming Skill (docren)

Portable document renaming skill that works across environments. Uses vision-capable models for document understanding.

## Trigger Conditions
- User explicitly asks to run `docren` / process documents / rename files
- User types `docren` with a path → process all documents in that directory
- User uploads a PDF or Word document and mentions renaming → process only the uploaded document
- The request clearly and explicitly implies document renaming
- User asks to check email for PDFs, attachments, or mailbox documents and then run docren
- User asks to process multiple documents in a directory (batch mode)

## Mandatory Protocol
**When user runs batch docren:**
1. Reply with acknowledgment: "I swear I will not judge a file by its name."
2. Check the configured docren root directory and/or mailbox (e.g. via Himalaya)
3. Process documents from both locations (vision rename → ocrmypdf searchable)
4. After processing each email's attachment, delete or archive the processed email message from the mailbox
5. Clean up: delete `temp_vision/` when done

## Automation Policy
- **No scheduled processing**: do not create or rely on recurring cron jobs for docren unless the user explicitly asks for automation.
- **Explicit only**: do not auto-process just because the user typed `docren` alone; ask for or infer a specific explicit request instead.
- **Issue Resolution**: if issues are encountered during processing (e.g., missing dependencies, permission errors), diagnose and fix them so the requested task can complete.
- **Scope**: process only files directly in the target directory unless the user explicitly asks to include subdirectories.

## Configuration

### Docren Home Path
Read `DOCREN_PATH` from `.env` file or environment variables.

**IMPORTANT: Only process files directly in the docren root directory. NEVER process files in directories starting with underscore (`_`):**
- `_check/` — do not process
- `_good/` — do not process
- `_any_other_underscore_dir/` — do not process
- **NEVER move/copy/delete files TO or FROM underscore directories** — leave them completely alone

This rule is enforced to prevent accidents with Syncthing file movements.

Fallback order:
1. `DOCREN_PATH` env var (if set in shell)
2. `DOCREN_PATH` in `.env` file
3. Ask user for the docren directory path

Example `.env` entry:
```
DOCREN_PATH=/path/to/docren
```

### Vision Model
Uses a vision-capable model for visual document understanding (reading letterhead, dates, stamps, tables).

## Routing Policy
**Always use a vision-capable model or vision tool** for document understanding and renaming.

1. **Step 1 — Rename with Vision** (REQUIRED): Use vision analysis to identify date, issuer, number, type
2. **Step 2 — Convert to Searchable** (REQUIRED): Use `ocrmypdf` to make PDF searchable
3. Extract only minimum fields: date, company, document number, document type
4. Ask for clarification only when ambiguity remains

**Why vision first?**
- OCR text parsing is ~17% accurate for renaming (unreliable)
- Vision model is ~99% accurate for renaming
- OCR text parsing fails on: dates, issuer identification, document numbers, document types
- `ocrmypdf` is ONLY reliable for: converting scanned PDF → searchable PDF

## Workflow

### 1. Determine Mode

**Automatic Batch Mode:**
When the user types `docren` alone (no file upload, no explicit path):
- Read `DOCREN_PATH` from `.env` (see Configuration section)
- Process all documents in that directory
- Skip `sorted/` and `failed/` subdirectories
- **CRITICAL: Skip ALL directories starting with underscore (`_`) such as `_check/`, `_good/` — never process files in underscore directories**
- Create `sorted/` and `failed/` subdirectories if they don't exist
- Process each document and move to `sorted/` (success) or `failed/` (error)
- Report a summary

**Explicit Batch Mode:**
When the user specifies a directory path:
- Process all documents in that directory
- **Skip ALL directories starting with underscore (`_`)**
- Create `sorted/` and `failed/` subdirectories if they don't exist
- Move successfully renamed documents to `sorted/`
- Move failed documents to `failed/`
- Report a summary

**Single-Document Mode:**
When user uploads a document or specifies a single file:
- Process the uploaded/specified document
- Rename it according to standard format
- Save to `sorted/` (success) or `failed/` (error)
- Report the new filename and location

**Email Attachment Mode:**
When user asks to check email for PDF attachments:
- Use email tool or CLI (e.g. Himalaya) to list mail in INBOX
- Prefer messages with `has_attachment=true` or obvious PDF-related subjects/senders
- Download attached PDFs to a temporary working directory
- Extract and rename each attachment using standard docren rules
- Save renamed outputs to `sorted/`
- Report results

### 2. Extraction Strategy

**CRITICAL RULE: Filename is ALWAYS wrong.**
- **NEVER** base judgment on filename
- **ALWAYS** trust the vision model (document content)
- Filename contains scanner date/time (NOT document date)
- Filename may have wrong document type, issuer, or number

**CRITICAL: OCR (ocrmypdf) is INACCURATE for parsing/renaming. Only use it for searchable conversion.**

**Workflow Order:**
1. **Step 1 — Rename with Vision** (REQUIRED): Use `vision_analyze` to identify date, issuer, number, type
2. **Step 2 — Convert to Searchable** (REQUIRED): Use `ocrmypdf` to make PDF searchable

**Why this order?**
- OCR text parsing is ~17% accurate for renaming (unreliable)
- Vision model is ~99% accurate for renaming
- OCR text parsing fails on: dates, issuer identification, document numbers, document types
- `ocrmypdf` is ONLY reliable for: converting scanned PDF → searchable PDF

**Text-based PDFs:**
1. Use `pymupdf` to extract text
2. Try to parse date, company, number, type from text
3. **ALWAYS verify with `vision_analyze`** — OCR text parsing is unreliable even for text PDFs
4. If vision agrees with text parsing, proceed
5. If vision disagrees, **trust vision**

**Scanned PDFs:**
1. Remove blank pages first (see Blank Page Removal section)
2. **Rename with vision first** (render page 1 to PNG, use `vision_analyze`)
3. **Then convert to searchable** with `ocrmypdf`
4. Save searchable PDF with the correct name

**Word Documents:**
1. Extract text directly from `.docx` files
2. **Verify with `vision_analyze`** for accuracy
3. If image-only, treat like scanned PDF

### 2.1 Blank Page Removal

**Before OCR or vision analysis:**
1. Check each page for meaningful content
2. Treat a page as blank when it has:
   - No meaningful text (empty OCR result)
   - Only negligible marks (page number only, tiny specks/noise)
   - Only whitespace (all-white image)
3. Remove blank pages to improve OCR/vision accuracy
4. When saving final processed document, remove blank pages permanently

**Working code:**
```python
import pymupdf
import numpy as np

doc = pymupdf.open("document.pdf")
pages_to_keep = []

for page_num in range(len(doc)):
    page = doc[page_num]
    
    # Check 1: Text content
    text = page.get_text().strip()
    
    # Check 2: Render and check if all white
    pix = page.get_pixmap(dpi=72)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    is_all_white = np.all(img_data == 255)
    
    if text or not is_all_white:
        pages_to_keep.append(page_num)

if len(pages_to_keep) < len(doc):
    new_doc = pymupdf.open()
    for page_num in pages_to_keep:
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    new_doc.save("document_cleaned.pdf")
    print(f"Removed {len(doc) - len(pages_to_keep)} blank page(s)")
```

### 2.2 PDF-to-Searchable Conversion

**When PDF is image-only (un-searchable), use `ocrmypdf` (Tesseract OCR) — the ONLY working approach.**

**Primary Approach: Use `ocrmypdf` (REQUIRED)**

```bash
# On Linux / macOS:
ocrmypdf --force-ocr -l eng+chi_tra "<input.pdf>" "<output.pdf>"

# On Windows:
# Unset PYTHONPATH first if experiencing venv conflicts
unset PYTHONPATH
ocrmypdf --force-ocr -l eng+chi_tra "<input.pdf>" "<output.pdf>"
```

**Parameters:**
- `--force-ocr`: Force OCR even if PDF already has text layer
- `-l eng+chi_tra`: Language(s) for OCR
  - `eng` — English
  - `chi_tra` — Traditional Chinese (Hong Kong)
  - `chi_sim` — Simplified Chinese
  - `eng+chi_tra` — Both English and Traditional Chinese (recommended for HK docs)

**Verification (MANDATORY):**
```python
import pymupdf
doc = pymupdf.open('<output.pdf>')
assert len(doc[0].get_text()) > 0, "PDF is NOT searchable!"
print(f"✅ PDF is searchable ({len(doc[0].get_text())} chars extractable)")
```

**If `ocrmypdf` fails:**
- Save extracted text as `.txt` sidecar file (NOT embedded in PDF)
- Move image-only PDF to `sorted/` with a note

**Note:** This step is MANDATORY. Users expect output PDFs to be searchable/editable. Do NOT skip this step.

### 3. Parse and Structure Information

**Date (YYYYMMDD):**
- Look for issue date, statement date, invoice date, or document date (in document content ONLY)
- **Do NOT use date from filename** - it is the scanner date/time, NOT the document's issue date
- If no date in content, ask user for clarification or use `NA`
- Format as 8 digits

**Company Slug (1-3 words, max 15 chars):**
- **CRITICAL: Issuer = DOCUMENT CREATOR** (letterhead, "From:" field, signature), NOT recipient.
- Examples:
  - Regulatory notice sent TO ACME Corp → issuer=Regulator (NOT ACME)
  - HSBC MPF reminder → issuer=HSBC
  - ACME abbreviation ONLY when ACME Corp is the ISSUER (not recipient)
- Prefer shortest recognizable official name
- Abbreviate common phrases:
  - Hong Kong → HK
  - Limited → Ltd
  - Corporation → Corp
  - Company → Co
  - International → Intl
  - Enterprise → Ent
  - Holdings → Hldgs
  - Services → Svc
- Prefer English when both English and Chinese names appear
- Use Chinese only if no English company name appears
- Keep Chinese company names in Chinese; do not transliterate unless asked
- Company-specific abbreviations are local overrides only

**How to Identify the Issuer (The #1 Rule):**
1. **Letterhead** — top of page, largest/boldest text
2. **"From:" field** — explicitly labeled sender
3. **Signature block** — who signed it?
4. **Contact info** — phone/email/website of the issuing organization

**Recipient is NOT the Issuer:**
The recipient appears in the address block (e.g. "ACME CORPORATION, SUITE 100, 16/F...").
**Never** use the recipient name as `company-slug`.

**User Organization Abbreviation Rule:**
Your own company/organization slug should ONLY be used when your organization is the **ISSUER** (e.g., your invoice, your delivery note).
When your company is the **RECIPIENT** (e.g., bank statement sent TO you), the issuer is the bank, NOT your company.

**Issuer Reference Table:**
| Document | Recipient (address line) | Issuer (letterhead) |
|---|---|---|
| MPFA Payment Notice | ACME Corporation | MPFA |
| HSBC MPF reminder | ACME Corporation | HSBC |
| Bank of China cheque advice | ACME Corporation | BOCHK |
| Telecom service notice | ACME Corporation | Telco |
| Companies Registry inquiry | ACME Corporation | CR (Companies Registry) |
| Tax notice | ACME Corporation | Tax Authority |

**Document Number:**
- Prefer the labeled invoice/statement/policy/reference/quotation number
- Include prefixes if they are part of the number
- If no number exists or is uncertain, use `NA`

**Short Description (1-5 words, max 20 chars):**
- Common types: invoice, bank-statement, insurance-policy, receipt, quotation, contract, tax-invoice, credit-note, delivery-note, order-confirmation, application-form, price-list
- Prefer `cert` over `certificate` in filenames when document type is certificate-related
- **MPFA unpaid contribution letters:** Use `未繳強制性供款` (not "enquirer-letter" or "reminder") — this is the exact Chinese heading on the letter
- Keep it specific but concise

### 4. Output Suggested Filename

Format:
```
YYYYMMDD company-slug document-number short-description.pdf
```

Example: `20240415 HKBNES 22677128 order-confirmation.pdf`

### 5. Convert to Searchable PDF (MANDATORY)

**AFTER renaming with vision, convert image-only PDFs to searchable using `ocrmypdf`.**

**IMPORTANT: This step does NOT rename files. It only converts scanned PDFs to searchable PDFs. Renaming is done in Step 2 using vision.**

```bash
# Convert to searchable PDF using ocrmypdf (Tesseract OCR)
# Use the CORRECT filename from vision renaming
ocrmypdf --force-ocr -l eng+chi_tra "<docren_home>/<original.pdf>" "<docren_home>/sorted/<correct_name_from_vision.pdf>"
```

**Verification (MANDATORY):**
```python
import pymupdf
doc = pymupdf.open('<docren_home>/sorted/<correct_name_from_vision.pdf>')
assert len(doc[0].get_text()) > 0, "PDF is NOT searchable!"
print(f"✅ PDF is searchable ({len(doc[0].get_text())} chars extractable)")
```

### 6. Move Files

After successful rename:
1. Move original document to `sorted/` subdirectory
2. Use new filename
3. Preserve original file extension

If processing fails:
1. Move original document to `failed/` subdirectory
2. Log the reason for failure

## Tools Required
- `pymupdf` - primary text extraction for text PDFs
- Vision model or vision tool - visual document understanding for scanned docs
- `ocrmypdf` - searchable PDF layer generation
- `python-docx` or similar - Word text extraction support
- PDF-to-image converter (or `pymupdf` pixmap) for rendering scanned PDFs

## Troubleshooting — Vision Model Problems

### Problem: Vision API Timeout or Large Image Errors
High-resolution scans can exceed payload limits or cause timeout errors.

### Solution:
1. Downscale the rendered page 1 image using `scripts/render_page1.py` (caps dimension to ~1000px and saves as JPEG q80).
2. If vision model is temporarily unavailable, fall back to OCR text extraction:
   ```bash
   pip install rapidocr-onnxruntime
   python3 -c "
   from rapidocr_onnxruntime import RapidOCR
   ocr = RapidOCR()
   result, _ = ocr('document_page1.jpg')
   if result:
       print('\n'.join([t[1] for t in result]))
   "
   ```

## Pitfalls
- **OCR (ocrmypdf) is INACCURATE for renaming**: OCR text parsing is only ~17% accurate for extracting date/issuer/number/type. Always use vision analysis for renaming. Use `ocrmypdf` ONLY for searchable PDF conversion.
- Scanned PDFs require vision analysis for accurate renaming; OCR text alone is unreliable
- Preserve bilingual content when it matters
- Multiple dates: prioritize the document date
- No document number: use `NA` or ask for clarification
- Preserve original file extension
- Batch mode: handle filenames with spaces or special characters using proper quoting
- Batch mode: skip files already in `sorted/` or `failed/` subdirectories
- **NEVER process files in underscore directories** (`_check/`, `_good/`, etc.)
- Preflight write check: verify runtime can write to target directories before moving files
- Scanner-generated PDFs: if metadata shows scanner provenance and PDF is image-only, use vision analysis
- **Cleanup mandatory:** Always delete `temp_vision/` from docren root after processing is complete
- **Issuer is always the document CREATOR** — never use the recipient's name as the company slug
- **Filename date is scanner date, not document date** — always extract from content
- ❌ Using vision text embedding without ocrmypdf (does NOT create searchable text layer)
- ❌ Forgetting to unset `PYTHONPATH` before running `ocrmypdf` on Windows
- ❌ Using Unix paths for `ocrmypdf.exe` in subprocess (must use `shell=True` on Windows)
- ❌ Forgetting to verify searchability with `get_text()` before moving to `sorted/`

## Notes
- Keep slugs recognizable and consistent across documents from same company
- Prioritize clarity over brevity when in doubt
- Use `DOCREN_PATH` from `.env` or environment variables (not hardcoded paths)
- Always use a capable vision model (do NOT rely solely on OCR for renaming)