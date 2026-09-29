# PaddleOCR PP-OCRv6 vs EasyOCR — Comparison Results

Last updated: [DOB]0 (PaddleOCR is now the DEFAULT engine)

## Installation (Windows, Python 3.12)

```bash
# Python 3.12+ required (PaddlePaddle does not support 3.14)
# Install paddlepaddle CPU first, then paddleocr
pip install paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install paddleocr
```

Models (~200MB) auto-download on first run to `~/.paddlex/official_models/`.

## Direct Comparison — Same Blurry Photo ([Name] 1587465116.jpg)

| Field | EasyOCR | Conf | PaddleOCR PP-OCRv6 | Conf | Ground Truth |
|---|---|---|---|---|---|
| Name | [Name] | 0.97 | [Name] | **1.000** | [Name] |
| Gender | 女 | 0.57 | 女 | **0.999** | 女 |
| Ethnicity | 汊 ❌ | 0.61 | **汉** ✅ | **1.000** | 汉 |
| DOB | [DOB]0 ❌ | 0.10 | [DOB]0 ❌ | **1.000** | [DOB] |
| ID number | 340406198310101785 ❌ | 0.91 | 340406198310101785 ❌ | **1.000** | 360681198509030528 |
| Address | 安徽省淮南市... ✅ | — | 安徽省淮南市... ✅ | — | Same |

## Clean Photo Comparison ([Name] 1246258893.jpg)

| Field | EasyOCR | Conf | PaddleOCR PP-OCRv6 | Conf | Ground Truth |
|---|---|---|---|---|---|
| Name | [Name] | 0.97 | [Name] | **1.000** | [Name] |
| Address province | 江**酉**省 ❌ | — | **江西省** ✅ | **1.000** | 江西省 |
| Issuing authority | 龙虎**田** ❌ | 0.08 | **龙虎山** ✅ | **1.000** | 龙虎山 |
| ID number | 360681198509030528 ✅ | 0.75 | 360681198509030528 ✅ | **1.000** | Same |
| DOB | [DOB] ✅ | 0.75 | [DOB] ✅ | **0.999** | Same |

## Key Findings

1. **PaddleOCR has higher confidence on every field** — everything ≥ 0.999 vs EasyOCR's 0.08–0.97
2. **Both engines read the SAME wrong digits** on the blurry photo — no OCR can distinguish 3/5/6/0 when pixels are smeared
3. **EasyOCR's lower confidence on DOB (0.10) was more honest** — the pipeline's `_warnings` correctly flagged it
4. **PaddleOCR's 1.000 confidence is misleading** — it's perfectly confident about wrong data
5. **PaddleOCR correctly reads character-level details** like 江西省 (vs EasyOCR's 江酉省) and 龙虎山 (vs EasyOCR's 龙虎田)
6. **PaddleOCR separates field labels from values** better (reads "姓名" and "[Name]" as distinct blocks vs EasyOCR's "[Name]姓名" merged)

## Practical Implications

- **Do NOT trust OCR confidence blindly** — PaddleOCR 1.000 can still be wrong. ID checksum validation catches errors regardless of engine.
- **PaddleOCR is a meaningful upgrade for clean and mid-quality images** — better CJK character discrimination (江西 vs 江酉, 汉 vs 汊, 龙虎山 vs 龙虎田)
- **Blurry photos defeat both engines** — physical image quality is the bottleneck, not the OCR engine choice
- **PaddleOCR adds ~500MB framework overhead** (PaddlePaddle) under a separate Python 3.12 environment

## Integration Status

PaddleOCR PP-OCRv6 is the **default engine** (since [DOB]0). Falls back to EasyOCR → Tesseract. The pipeline calls it via subprocess to `paddleocr_helper.py` running under Python 3.12.

## Usage (Python 3.12)

```python
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang='ch', use_textline_orientation=True)
for res in ocr.predict('image.jpg'):
    for text, score in zip(res['rec_texts'], res['rec_scores']):
        print(f'[{score:.3f}] {text}')
```

Note: Use `predict()` not `ocr()` in v3.7+ (deprecated). Output is an `OCRResult` object with `rec_texts` and `rec_scores` keys.
