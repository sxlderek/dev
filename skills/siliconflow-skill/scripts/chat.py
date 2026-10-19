#!/usr/bin/env python3
"""SiliconFlow chat completion helper using Qwen/Qwen3.5-4B.

Outputs the final assistant reply as plain text.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Qwen/Qwen3.5-4B"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True, help="User prompt")
    p.add_argument("--model", default=DEFAULT_MODEL, help="SiliconFlow model id")
    p.add_argument("--system", default="You are a helpful assistant.", help="System instruction")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=1024)
    args = p.parse_args()

    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY is missing", file=sys.stderr)
        return 1

    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": args.system},
            {"role": "user", "content": args.prompt},
        ],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": False,
        "enable_thinking": False,
    }

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2

    try:
        data = json.loads(raw)
        text = data["choices"][0]["message"]["content"]
    except Exception:
        print(raw)
        return 0

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
