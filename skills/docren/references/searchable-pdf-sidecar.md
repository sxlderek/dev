# Searchable PDF sidecar workflow

Workflow for scanned PDFs that need an OCR text layer while preserving the original file.

## When to use
- The PDF is image-only or has poor embedded text.
- You want a safe conversion that keeps the original intact.
- You need to verify OCR quality before replacing anything.

## Important replacement rule
- If the user asks to *replace* PDFs with searchable versions, do **not** leave `*.searchable.pdf` sidecars behind.
- Save the searchable output only as a temporary intermediate.
- Replace the original file in place after verification, then confirm no sidecars remain.

## Working pattern
1. Open the PDF with `pymupdf`.
2. For each page:
   - render the page to an image at around `2.5x` zoom
   - run `RapidOCR` on the rendered image
   - collect the OCR lines in reading order
3. Create a new PDF with the same page geometry.
4. Insert the original page content into the new PDF.
5. Add an invisible OCR text layer with `insert_textbox(..., render_mode=3)`.
6. Save as `original.searchable.pdf` for verification.
7. Verify the output with `page.get_text('text')`.
8. If replacing in place, move the searchable file over the original filename and then delete any remaining sidecars.

## Notes
- Blank pages may produce no OCR result; keep the page and just skip the text layer.
- Sidecar output is safer than overwriting the source because it allows comparison and rollback.
- This workflow worked on a 4-page HK IRD business registration notice and on mixed Chinese/English scans.
- Chinese OCR was improved by downloading `chi_sim.traineddata` and `chi_tra.traineddata` into the Tesseract `tessdata` directory.

## Minimal snippet
```python
import fitz
from rapidocr_onnxruntime import RapidOCR

doc = fitz.open(src_pdf)
ocr = RapidOCR()
out = fitz.open()
for i, page in enumerate(doc):
    new_page = out.new_page(width=page.rect.width, height=page.rect.height)
    new_page.show_pdf_page(page.rect, doc, i)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
    result, _ = ocr(pix.tobytes("png"))
    if result:
        text = "\n".join(item[1].strip() for item in result if item and len(item) > 1 and item[1].strip())
        if text:
            new_page.insert_textbox(page.rect, text, fontsize=1, color=(1, 1, 1), overlay=True, render_mode=3)
out.save(dst_pdf, deflate=True, garbage=4)
```
