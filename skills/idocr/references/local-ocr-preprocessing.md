# Local OCR Preprocessing for Phone-Photo IDs

Tesseract's floor is a clean scan (≥ ~150 DPI). Phone photos of ID cards
(typically 810×1440 to 1440×810 JPEG) produce garbage or empty output from both
the default run and `local_ocr.py --preprocess` — its global Otsu threshold
flattens uneven photo lighting into noise. Escalate with the recipe below
BEFORE declaring local OCR insufficient and asking the user to approve a remote
engine.

## Working recipe (OpenCV → Tesseract)

Stage the image at an ASCII path first (Chinese paths break OpenCV), then run
with the ocr env python (any python3 with cv2 works):

```python
import cv2
img = cv2.imread('<ascii>.jpg', cv2.IMREAD_GRAYSCALE)
img = cv2.resize(img, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)  # 2.5-4x
img = cv2.bilateralFilter(img, 9, 75, 75)                                   # denoise, keeps edges
th = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                           cv2.THRESH_BINARY, 31, 12)                        # blockSize 31-41, C 12-15
cv2.imwrite('/tmp/th.png', th)
```

```bash
tesseract /tmp/th.png stdout -l chi_sim+eng --psm 3
```

Tuning knobs, in order of effect:
- Upscale factor 2.5-4x (INTER_CUBIC): below 2x small digits never resolve.
- adaptiveThreshold blockSize/C: raise both (e.g. 41/15) if strokes vanish; lower if the background speckles.
- `--psm 3` (auto layout) for a full card, `--psm 6` for a single text block.
- `chi_sim` for CN ID, `chi_tra` for HKID; add `+eng` for mixed Latin text.

ImageMagick `-normalize`/`-sharpen` upscale paths read as junk on this class of
image — use the OpenCV recipe, not ImageMagick filters.

## What to expect recoverable

- Digit fields with self-validation (CN ID number, DOB inside it, validity
  dates) often resolve even from poor photos — always pass candidates through
  the checksum below.
- Name glyphs (thin CJK strokes) are the first casualty of low resolution and
  thresholding; fixed-fraction crops of the name region can come back EMPTY
  because the threshold erases thin strokes entirely. When crops are empty,
  fall back to full-image thresholding and report the name `[unclear]` rather
  than guessing from noise.
- Confidence values mean nothing on photos — a completely wrong digit can
  score 1.0. Never pick between readings by confidence.

## Decide digit ties by checksum, not by re-voting

Tesseract passes disagree freely on digits of the same field. For CN ID
numbers, compute the ISO 7064 MOD 11-2 check digit of each 17-digit candidate
locally and keep the one that passes; also cross-check digits 7-14 against the
printed 出生日期. If neither candidate passes, report `[unclear]`.

```python
weights = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
codes   = ['1','0','X','9','8','7','6','5','4','3','2']
check = codes[sum(int(c)*w for c, w in zip(n17, weights)) % 11]
```

## Second-stage escalation: CLAHE crop when binarisation stays noisy

If adaptive thresholding still yields noise on a target field (labels and glyphs
shredded), crop that field's zone from the ~2x grayscale image and normalise with
CLAHE instead of binarising — it evens out uneven photo lighting while preserving
the thin strokes that a threshold erases:

```python
import cv2
img = cv2.imread('<full_2x>.png', cv2.IMREAD_GRAYSCALE)
h, w = img.shape
crop = img[int(h*0.50):int(h*0.85), 0:int(w*0.75)]   # zone of the field; tune per field
crop = cv2.resize(crop, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
crop = cv2.bilateralFilter(crop, 9, 75, 75)
crop = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(crop)
crop = cv2.resize(crop, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)  # net ~2x
cv2.imwrite('field_clahe.png', crop)
```

```bash
tesseract field_clahe.png stdout -l chi_sim --psm 4
```

- Keep the NET scale around 2x: a bare 4x full-image upscale (5000px+ side) makes
  Tesseract return completely empty output.
- `--psm 4` (variable-size text columns) reads the card's labelled line blocks
  better than psm 3/6 at this stage.
- Emit a recovered CJK field only after independent passes agree (vary crop zone,
  scale, or psm): single-pass CJK on phone photos still swaps adjacent glyphs.
