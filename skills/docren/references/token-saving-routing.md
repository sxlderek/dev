# Token-Saving Routing for docren

## What changed in this session
- Prefer text extraction first for PDFs and Word docs.
- OCR only when text extraction is empty or clearly incomplete.
- OCR page 1 first; only OCR more pages if needed.
- Reduce raw OCR output to a compact field summary before sending anything to the model.
- Ask only one clarification question at a time when a single field is missing.

## Suggested routing policy
1. Extract text locally (`pymupdf` for PDFs, direct text extraction for `.docx`).
2. If scanned/image-only, render page 1 and OCR that page first.
3. Extract only:
   - date
   - company
   - document number
   - document type
4. Use a low-cost model only on the compact summary.
5. Escalate only when ambiguity remains.

## Useful model split
- `gemini 2.5 lite`: good default for compact understanding.
- `glm-4.6v`: backup when a vision model is needed on scanned pages.
- `gpt-5-nano`: lightweight final formatter when extraction already did most of the work.

## Pitfall
Do not paste full OCR dumps into chat unless absolutely necessary.