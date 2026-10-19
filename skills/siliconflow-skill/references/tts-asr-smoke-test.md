# SiliconFlow TTS/ASR Smoke Test

This note captures a reusable verification flow for SiliconFlow audio.

## What was verified

- `POST /v1/audio/speech` works with `FunAudioLLM/CosyVoice2-0.5B`
- `POST /v1/audio/transcriptions` works with `FunAudioLLM/SenseVoiceSmall`
- The same round-trip flow can be reused as a quick connectivity and sanity check

## Script

Use the linked script:

```bash
python3 scripts/tts_asr_smoke_test.py --text "Hello, this is a SiliconFlow text to speech test."
```

## Expected behavior

- TTS emits an MP3 file in `/tmp/siliconflow-tts-asr/tts.mp3`
- ASR returns JSON with a `text` field
- Minor recognition errors are normal; this is a smoke test, not an accuracy benchmark

## Caveat

- `FunAudioLLM/CosyVoice2-0.5B` was reachable and useful in this environment, but it should not be assumed to reliably produce Cantonese without verifying the actual output.
