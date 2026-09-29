# Dual-Image Processing (Front + Back of Chinese ID Card)

## When to Use

Chinese national ID cards split info across two sides:
- **Back side (国徽面)**: 姓名, 性别, 民族, 出生, 住址, 公民身份号码
- **Front side (人像面)**: 签发机关, 有效期限

The `ocr_via_siliconflow.py` script takes a single `--input`. For two-sided documents, **send both images in a single API call** to the VL model for merged extraction.

## Approach

Send a single chat completions request with **two image_url parts** in the same message, plus a prompt that asks for all fields from both sides.

```python
import base64, json, urllib.request

def encode_img(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()

back_b64 = encode_img('back.jpg')
front_b64 = encode_img('front.jpg')

payload = {
    "model": "Qwen/Qwen3-VL-32B-Instruct",
    "messages": [{
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{back_b64}"}
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{front_b64}"}
            },
            {
                "type": "text",
                "text": "These are the two sides of a Chinese national ID card. "
                        "Extract ALL fields: Full Name (Native), Full Name (EN), "
                        "DOB, Document type, Document number, Issuing country, "
                        "Issuing authority, Expiry. Return in structured format."
            }
        ]
    }],
    "max_tokens": 500,
    "temperature": 0.0
}
```

## Result

The VL model understands both images are the same document and merges fields correctly:

```
Full Name (Native): 陈曼
Full Name (EN): Chen Man
DOB: [DOB]0
Document type: National ID
Document number: 340406199007100063
Issuing country: China
Issuing authority: 淮南市公安局潘集分局
Expiry: 2045-03-19
```

## Tips

- **Order matters**: Put the back side (with personal info) first, front side second. The model processes images in order.
- **Format**: JPEG is fine — no need for PNG. Smaller payload = faster response.
- **Temperature 0.0**: Essential for deterministic structured output.
- **One-shot vs two-shot**: A single dual-image call produces a cleaner merged result than running two separate calls and merging manually. The model sees both sides together and can cross-reference.

## Known Working Example

Tested [DOB] with:
- Back: `445749949.jpg` (personal info side)
- Front: `1484325882.jpg` (issuing authority + expiry side)
- Model: `Qwen/Qwen3-VL-32B-Instruct`
- Result: All 8 fields extracted perfectly, first try.
