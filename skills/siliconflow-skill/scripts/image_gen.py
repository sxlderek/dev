#!/usr/bin/env python3
"""SiliconFlow Image Generation helper.

Supports models:
- kolors (default): Kwai-Kolors/Kolors
- flux: black-forest-labs/FLUX.1-schnell
- flux-dev: black-forest-labs/FLUX.1-dev
- flux-pro: black-forest-labs/FLUX.1-pro
- qwen: Qwen/Qwen-Image
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.siliconflow.cn/v1"

MODEL_MAP = {
    "kolors": "Kwai-Kolors/Kolors",
    "flux": "black-forest-labs/FLUX.1-schnell",
    "flux-dev": "black-forest-labs/FLUX.1-dev",
    "flux-pro": "black-forest-labs/FLUX.1-pro",
    "qwen": "Qwen/Qwen-Image",
}


def main():
    parser = argparse.ArgumentParser(description="SiliconFlow Image Generation")
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--filename", required=True, help="Output image file path")
    parser.add_argument("--model", default="kolors", help="Model alias or ID (default: kolors)")
    parser.add_argument("--image-size", default="1024x1024", help="Dimensions (e.g. 1024x1024)")
    parser.add_argument("--no-watermark", action="store_true",
                        help="Disable the explicit 'AI-generated' watermark (passes X-Enable-Watermark: 0)")
    args = parser.parse_args()

    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY is missing", file=sys.stderr)
        return 1

    model = MODEL_MAP.get(args.model.lower(), args.model)
    payload = {
        "model": model,
        "prompt": args.prompt,
        "image_size": args.image_size,
    }

    req = urllib.request.Request(
        f"{API_BASE}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **({"X-Enable-Watermark": "0"} if args.no_watermark else {}),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    image_url = None
    if "images" in res and res["images"]:
        image_url = res["images"][0].get("url")
    elif "data" in res and res["data"]:
        image_url = res["data"][0].get("url")

    if not image_url:
        print(f"ERROR: No image URL in response: {res}", file=sys.stderr)
        return 3

    outpath = pathlib.Path(args.filename)
    outpath.parent.mkdir(parents=True, exist_ok=True)

    # Download generated image to outpath
    img_req = urllib.request.Request(image_url, headers={"User-Agent": "Hermes"})
    with urllib.request.urlopen(img_req, timeout=60) as img_resp:
        img_bytes = img_resp.read()
        outpath.write_bytes(img_bytes)

    print(f"IMAGE_OK bytes={len(img_bytes)} path={outpath}")
    print(f"MEDIA: {outpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
