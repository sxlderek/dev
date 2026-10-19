#!/usr/bin/env python3
"""SiliconFlow text-to-speech helper."""

import argparse
import base64
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "fishaudio/fish-speech-1.5"
DEFAULT_VOICE = None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True, help="Text to synthesize")
    p.add_argument("--filename", required=True, help="Output file path")
    p.add_argument("--model", default="fish-speech", help="Model alias or full model id")
    p.add_argument("--voice", default=DEFAULT_VOICE, help="Voice id, when supported")
    p.add_argument("--stream", action="store_true", default=True, help="Request streaming audio")
    args = p.parse_args()

    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY is missing", file=sys.stderr)
        return 1

    model_map = {
        "fish-speech": "fishaudio/fish-speech-1.5",
        "cosyvoice": "FunAudioLLM/CosyVoice2-0.5B",
        "indextts": "IndexTeam/IndexTTS-2",
        "moss": "fnlp/MOSS-TTSD-v0.5",
    }
    model = model_map.get(args.model, args.model)

    payload = {
        "model": model,
        "input": args.text,
        "response_format": pathlib.Path(args.filename).suffix.lstrip('.') or 'mp3',
        "stream": bool(args.stream),
    }
    if args.voice:
        payload["voice"] = args.voice
    elif model == "FunAudioLLM/CosyVoice2-0.5B":
        payload["voice"] = "FunAudioLLM/CosyVoice2-0.5B:alex"

    req = urllib.request.Request(
        f"{API_BASE}/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        print(f"ERROR HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2

    out = pathlib.Path(args.filename)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio)
    print(f"MEDIA: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
