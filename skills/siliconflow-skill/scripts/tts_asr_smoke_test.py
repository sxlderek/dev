#!/usr/bin/env python3
"""SiliconFlow TTS + ASR smoke test.

Generates a short MP3 via /v1/audio/speech, then transcribes it via
/v1/audio/transcriptions.
"""

import argparse
import base64
import json
import os
import pathlib
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.siliconflow.cn/v1"


def http_json(url, payload, api_key, timeout=120):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers), r.status


def multipart_upload(url, api_key, fields, file_field, timeout=120):
    boundary = "----HermesBoundary" + base64.b32encode(os.urandom(10)).decode().rstrip("=")
    crlf = b"\r\n"
    chunks = []
    for name, value in fields.items():
        chunks.append(b"--" + boundary.encode("utf-8") + crlf)
        chunks.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8") + crlf + crlf)
        chunks.append(str(value).encode("utf-8") + crlf)
    file_name, file_bytes, content_type = file_field
    chunks.append(b"--" + boundary.encode("utf-8") + crlf)
    chunks.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode("utf-8") + crlf)
    chunks.append(f'Content-Type: {content_type}'.encode("utf-8") + crlf + crlf)
    chunks.append(file_bytes)
    chunks.append(crlf)
    chunks.append(b"--" + boundary.encode("utf-8") + b"--" + crlf)
    body = b"".join(chunks)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers), r.status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="Hello, this is a SiliconFlow text to speech test.")
    parser.add_argument("--tts-model", default="FunAudioLLM/CosyVoice2-0.5B")
    parser.add_argument("--tts-voice", default="FunAudioLLM/CosyVoice2-0.5B:alex")
    parser.add_argument("--asr-model", default="FunAudioLLM/SenseVoiceSmall")
    parser.add_argument("--output-dir", default="/tmp/siliconflow-tts-asr")
    args = parser.parse_args()

    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        print("ERROR: SILICONFLOW_API_KEY is missing", file=sys.stderr)
        return 1

    outdir = pathlib.Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    audio_path = outdir / "tts.mp3"

    speech_payload = {
        "model": args.tts_model,
        "input": args.text,
        "voice": args.tts_voice,
        "response_format": "mp3",
        "stream": True,
    }

    try:
        audio, headers, status = http_json(f"{API_BASE}/audio/speech", speech_payload, api_key)
    except urllib.error.HTTPError as e:
        print(f"TTS_ERROR HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"TTS_ERROR {e}", file=sys.stderr)
        return 2

    audio_path.write_bytes(audio)
    print(f"TTS_OK bytes={len(audio)} path={audio_path}")

    try:
        raw, headers, status = multipart_upload(
            f"{API_BASE}/audio/transcriptions",
            api_key,
            {"model": args.asr_model},
            (audio_path.name, audio_path.read_bytes(), "audio/mpeg"),
        )
    except urllib.error.HTTPError as e:
        print(f"ASR_ERROR HTTP {e.code}: {e.read().decode('utf-8', 'ignore')}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ASR_ERROR {e}", file=sys.stderr)
        return 3

    text = raw.decode("utf-8", "ignore")
    print(f"ASR_RAW {text}")
    try:
        data = json.loads(text)
        print(f"ASR_TEXT {data.get('text', '')}")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
