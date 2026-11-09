# Filename Parsing Patterns for Batch Processing

This reference documents the filename extraction patterns for batch document renaming when pymupdf/OCR is unavailable.

## When to Use

- Use in batch processing mode (`docren` alone)
- Use when pymupdf is not available in the environment
- Fall back to content extraction when filename parsing is insufficient

## Common Filename Patterns

### 1. Date-First Pattern
```
20240415_hkbn.pdf
→ date: 20240415 (YYYYMMDD in filename)
→ company: HKBN
→ doc_number: NA
→ type: document
```

### 2. ID-Date Pattern
```
[DocNumber]-24042025175041.pdf
→ date: 24042025 → 20240425 (DDMMYYYY → YYYYMMDD)
→ company: Unknown
→ doc_number: [DocNumber]
→ type: document
```

### 3. Company-DocType Pattern
```
HSBC MPF abc1.pdf
→ date: default (20250501)
→ company: HSBC
→ doc_number: abc1
→ type: mpf-statement
```

### 4. Invoice Pattern
```
ABC01-INV-75-Rental 260101.pdf
→ date: 260101 → 20260101 (YYMMDD → YYYYMMDD)
→ company: ABC01
→ doc_number: INV-75
→ type: rental-invoice
```

### 5. Company Invoice with Month
```
ACME-Invoice-64845 OCT2025-MAR2026 USD2418_HS.pdf
→ date: OCT2025 → 20251001
→ company: ACME
→ doc_number: 64845
→ type: invoice
```

### 6. eBill Pattern
```
eBill-012345678-202603-22-1.pdf
→ date: 20260322
→ company: HKBN (eBill is HKBN service)
→ doc_number: 012345678
→ type: invoice
```

## Date Format Conversions

| Original | Format | Converted |
|----------|--------|-----------|
| 20240415 | YYYYMMDD | 20240415 |
| 24042025 | DDMMYYYY | 20240425 |
| 260101 | YYMMDD | 20260101 |
| OCT2025 | MMMYYYY | 20251001 |

## Company Abbreviations

| Full Name | Slug |
|-----------|------|
| HKBN | hkbn |
| HSBC | hsbc |
| EastCo | eastco |
| ABC01 | abc01 |
| SunCo | abc01 |
| ACME | acme |

## Confirmed Rename-Output Conventions (by issuer)

Confirmed from archived `sorted/` names — match these exactly when renaming faxes/statements so the archive stays consistent. Skeleton: `<YYYYMMDD> <issuer-slug> <ref> <Description> <MMM YYYY>.pdf` where the date is the document's own date (bill cut date, statement date), not the fax/scan date.

| Issuer | Pattern | Example |
|--------|---------|---------|
| hkt (bills) | `YYYYMMDD hkt <account-no> Bill MMM YYYY.pdf` (date = bill cut date) | `20260921 hkt 68-123456-7890-12 Bill Sep 2026.pdf` |
| hkt (forms) | `YYYYMMDD hkt <ref> <Form Description>.pdf` | `20261010 hkt 12345678 Change of Registered Customer Application Form.pdf` |
| bochk (consolidated) | `YYYYMMDD bochk <statement-ref> Consolidated Statement MMM YYYY.pdf` | `20260831 bochk 1234567890 Consolidated Statement Aug 2026.pdf` |
| bochk (account) | `YYYYMMDD bochk <account-no> Account Statement MMM YYYY.pdf` | `20260831 bochk 014-123-0-004567-8 Account Statement Aug 2026.pdf` |

| clp | `YYYYMMDD clp <account-no> Electricity Bill MMM YYYY.pdf` (date = statement date) | `20260919 clp 12345-67890-1 Electricity Bill Sep 2026.pdf` |
| hkbn | `YYYYMMDD hkbn <account-no> Broadband and Service Bill MMM YYYY.pdf` (date = bill date) | `20260831 hkbn 123456789 Broadband and Service Bill Aug 2026.pdf` |

Before naming an unfamiliar issuer, list existing `sorted/` names (`orderby=name asc`) and match the established shape rather than inventing a new one.

## Document Type Mapping

| Keyword in filename | Document Type |
|---------------------|---------------|
| inv, invoice | invoice |
| mpf, inz | mpf-statement |
| rental | rental-invoice |
| contract | contract |
| statement | statement |
| schedule | schedule |

## Python Parsing Code

```python
import re
import os

def extract_info_from_filename(filename):
    basename = os.path.splitext(filename)[0]
    lower = basename.lower()
    
    info = {"company": None, "date": None, "doc_number": None, "doc_type": "document"}
    
    # 1. Date extraction
    # YYYYMMDD_
    match = re.search(r'^(\d{8})_', basename)
    if match:
        info["date"] = match.group(1)
    
    # DDMMYYYY (e.g., 24042025)
    if not info.get("date"):
        match = re.search(r'(\d{8})', basename)
        if match:
            d = match.group(1)
            try:
                day, month, year = int(d[:2]), int(d[2:4]), int(d[4:8])
                if 1 <= day <= 31 and 1 <= month <= 12:
                    info["date"] = f"{year:04d}{month:02d}{day:02d}"
            except:
                pass
    
    # YYMMDD (e.g., 260101)
    if not info.get("date"):
        match = re.search(r'(\d{6})$', basename.replace(' ', ''))
        if match:
            d = match.group(1)
            info["date"] = f"20{d[:2]}{d[2:4]}{d[4:6]}"
    
    # 2. Company extraction
    companies = {
        "hkbn": "HKBN",
        "hsbc": "HSBC",
        "eastco": "EastCo",
        "abc01": "ABC01",
        "acme": "ACME",
    }
    for key, company in companies.items():
        if key in lower:
            info["company"] = company
            break
    
    # 3. Document type
    if 'inv' in lower or 'invoice' in lower:
        info["doc_type"] = "invoice"
    elif 'mpf' in lower:
        info["doc_type"] = "mpf-statement"
    elif 'rental' in lower:
        info["doc_type"] = "rental-invoice"
    elif 'ebill' in lower:
        info["doc_type"] = "invoice"
        info["company"] = "HKBN"
    
    # 4. Document number
    match = re.search(r'INV-?(\d+)', basename, re.IGNORECASE)
    if match:
        info["doc_number"] = f"INV-{match.group(1)}"
    
    match = re.search(r'^([A-Z]?\d+)', basename)
    if match and not info.get("doc_number"):
        info["doc_number"] = match.group(1)
    
    # Defaults
    if not info.get("date"):
        info["date"] = "20250501"
    if not info.get("doc_number"):
        info["doc_number"] = "NA"
    
    return info
```

## Environment Note

When pymupdf is unavailable:
1. Try `poppler-utils` (pdftotext) first
2. Try `tesseract-ocr` for scanned PDFs
3. If neither available, fall back entirely to filename-based extraction
4. Document the limitation in the workflow output

**Group ownership:** Always create sorted/ and failed/ directories with group 100 (gid 100) for NAS environments.