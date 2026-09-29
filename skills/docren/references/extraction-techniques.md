# Extraction techniques for docren

Use this reference when the uploaded document is a PDF and text extraction is uncertain.

## Preferred order
1. `pymupdf` / `page.get_text()` for text-based PDFs
2. Tesseract OCR for scanned/image-only PDFs
3. Ask the user for missing fields if OCR is unavailable or ambiguous

## Tesseract Installation & Usage
- Install Tesseract system packages:
  ```bash
  sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
  ```
- Install python packages:
  ```bash
  pip install pytesseract Pillow
  ```
- Sample OCR execution:
  ```python
  from PIL import Image
  import pytesseract
  text = pytesseract.image_to_string(Image.open('/tmp/sample_page1.png'), lang='eng')
  ```

## Practical OCR note
- Tesseract is a real fallback for scanned PDFs, so prefer it before asking the user to transcribe fields manually.
- `lang='eng'` or `lang='eng+chi_tra'` depending on document language.

## Filename parsing pitfall observed
- OCR can surface noisy or partial document numbers. Verify the number against nearby labels before finalizing the suggestion.
- If the document is a confirmation/order form that contains both a customer number and a reference number, prefer the actual document reference over the customer number when it is clearly labeled.
