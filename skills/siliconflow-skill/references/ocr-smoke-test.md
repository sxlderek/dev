# OCR smoke test note

Session outcome:
- SiliconFlow OCR was reachable and returned a response successfully.
- Test image text was intended to be `OCR TEST` and `21470470`.
- OCR output came back as:
  - `0CR_TEST`
  - `21470470`

Takeaway:
- The workflow is operational, but OCR can confuse `O` and `0` on simple synthetic text.
- For exactness checks, use a clean high-contrast image and verify critical glyphs manually or with a second pass.

Test setup:
- Model: `PaddlePaddle/PaddleOCR-VL-1.5`
- Endpoint: SiliconFlow chat completions API
- Image: locally generated PNG with black text on white background

Use this as a smoke test pattern, not a benchmark for production accuracy.