# OCR fallbacks for docren

## When to use
Use this fallback path when a PDF has no embedded text, looks scanned, or extracted text is clearly incomplete.

## Proven workflow
1. Render page 1 to an image.
2. Run RapidOCR on the rendered image first.
3. If needed, try Tesseract with Chinese traineddata available in the `tessdata` directory.
4. Extract only the minimum required fields: date, company, document number, document type.
5. Do not keep temporary render images after OCR unless the user explicitly wants them.

## Practical notes
- RapidOCR on rendered page images worked reliably for scan-only Chinese/English PDFs here.
- If Tesseract Chinese traineddata is in a custom path, configure `TESSDATA_PREFIX=<path-to-tessdata>`.
- If OCR output is enough to identify the filename, stop early and avoid extra pages.
- If a document is bilingual, preserve English names when available and keep Chinese text only when needed.

## Failure handling
- If OCR is unavailable locally, install it rather than stopping early when the environment allows it.
- Separate OCR ambiguity from filesystem move failures when reporting problems.
- For scans with no embedded text, prefer OCR over guessing from metadata.

## Verification
A successful fallback should produce at least one of:
- a date
- a company name or slug
- a document number
- a document type
