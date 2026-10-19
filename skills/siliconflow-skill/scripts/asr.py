#!/usr/bin/env python3
"""SiliconFlow ASR helper using FunAudioLLM/SenseVoiceSmall.

Transcribes audio to text via OpenAI-compatible /v1/audio/transcriptions.
Outputs the transcription as plain text.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "FunAudioLLM/SenseVoiceSmall"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True, help="Path to audio file (wav, mp3, m4a, etc.)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="SiliconFlow ASR model id")
    p.add_argument("--language", default="zh", help="Language hint (default: zh)")
    args = p.parse_args()

    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY is missing", file=sys.stderr)
        return 1

    if not os.path.isfile(args.audio):
        print(f"ERROR: audio file not found: {args.audio}", file=sys.stderr)
        return 1

    # Read audio file
    with open(args.audio, "rb") as f:
        audio_data = f.read()

    # Build multipart boundary
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model"\r\n\r\n'
        f"{args.model}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="language"\r\n\r\n'
        f"{args.language}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(args.audio)}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + audio_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"{API_BASE}/audio/transcriptions"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    attempts_left = 3
    result = None
    while attempts_left >= 0:
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempts_left > 0:
                print(f"WARN: HTTP 503, retrying ({attempts_left} left)...", file=sys.stderr)
                time.sleep(5)
                attempts_left -= 1
                continue
            print(f"ERROR: HTTP {e.code} {e.reason}", file=sys.stderr)
            print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
            return 1
        except urllib.error.URLError as e:
            print(f"ERROR: {e.reason}", file=sys.stderr)
            return 1
        else:
            break

    if "text" in result:
        print(result["text"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())