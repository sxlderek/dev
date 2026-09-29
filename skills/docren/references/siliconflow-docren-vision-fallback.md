# SiliconFlow docren vision fallback recipe

Pattern for scan-only business documents:

- Text extraction from the PDF can be empty even when the PDF has 2 pages.
- Rendering the PDF pages to PNG first is necessary for scanned documents.
- `PaddlePaddle/PaddleOCR-VL-1.5` may return a lot of unrelated or repetitive text on Chinese business scans.
- Use OCR for a first pass if needed, but verify the final fields with a vision-capable model.
- `Qwen/Qwen3-VL-32B-Instruct` successfully extracted compact JSON for:
  - issuer/company
  - date
  - document number/reference
  - document type
- For docren, the vision model is best used as a verifier of the final filename fields, not as a full-document transcription engine.

Suggested flow:
1. Render page 1 to image.
2. Run SiliconFlow OCR if you want text-first extraction.
3. If OCR is noisy, ask a vision model for compact structured fields.
4. Rename only after the issuer/date/number/type are consistent.
