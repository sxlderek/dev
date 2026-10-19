---
name: siliconflow-skill
slug: siliconflow-skill
version: 1.0.0
description: SiliconFlow workflows and API development for chat, image generation, image editing, video generation, OCR, TTS, and ASR.
---

## When to Use

Use this skill when the user wants to use **SiliconFlow** for:
- chat / text completion
- image generation or image editing
- text-to-video or image-to-video generation
- OCR / image text recognition
- text-to-speech (TTS)
- speech-to-text / ASR
- SiliconFlow API development, model selection, deployment, and feature discovery

## SiliconFlow API Development

This skill now also covers the broader SiliconFlow API workflow, not just media generation.

Use the API-focused parts of this skill when the user asks about:
- SiliconFlow endpoints and request/response shapes
- model catalogs and choosing the right model
- deployment or integration questions
- feature discovery and troubleshooting
- example use cases and implementation patterns

### Reference map

The upstream SiliconFlow API skill is organized around these doc areas:
- `api_reference.md` — endpoint-level API reference and payload shapes
- `deployment.md` — deployment and environment guidance
- `faqs.md` — common questions and troubleshooting
- `features.md` — platform capabilities and feature overview
- `models.md` — model listings and selection guidance
- `other.md` — miscellaneous notes
- `use_cases.md` — practical workflow examples
- `userguide.md` — onboarding and usage guidance
- `index.md` / `llms.md` / `llms-full.md` — generated overview and long-form reference views

### How to use it

- For endpoint details, start with the API reference.
- For choosing a model, check the models section first.
- For integration problems, consult deployment and FAQs.
- For practical examples, use the use-cases documentation.
- For this merged skill, prefer the existing script-backed workflows when the task is media/chat/ASR/TTS/OCR related.
- If the user wants a general SiliconFlow API answer, keep the response concise and factual instead of focusing only on the media scripts.

## Chat / Text Completion

Use SiliconFlow's OpenAI-compatible chat endpoint for plain text completion.

```bash
uv run {baseDir}/scripts/chat.py --prompt "Write a short reply" --model "Qwen/Qwen3.5-4B"
```

Default model:
- `Qwen/Qwen3.5-4B`

Notes:
- This is the default SiliconFlow chat model for this skill unless the user asks for another model.
- Keep prompts short and direct when you want fast completions.
- If the user needs a special style, supply it in the prompt instead of adding extra wrappers.
- The script should print the final assistant response as plain text.

## Chat / Text Completion Script

- `scripts/chat.py` — OpenAI-compatible chat completion wrapper using `Qwen/Qwen3.5-4B`


Do **not** use this skill as the wrapper for OmniRoute/OpenAI/ElevenLabs model routing. If the requested model lives in OmniRoute, call OmniRoute directly and use the provider-model-listing skill for discovery/debugging.

### Language caveat

In live tests, `FunAudioLLM/CosyVoice2-0.5B` was reachable through SiliconFlow and worked for Mandarin/English output, but it did **not** reliably produce Cantonese in this environment. If the user requests Cantonese audio, verify the language output before assuming CosyVoice is sufficient.

## Requirements

- Environment variable: `SILICONFLOW_API_KEY`
- Billing is through SiliconFlow credits/vouchers.
- Video jobs can take several minutes.

## Commands

### Image generation

```bash
uv run {baseDir}/scripts/image_gen.py --prompt "描述" --filename "output.png" [--model MODEL]
```

Models:
- `flux` → `black-forest-labs/FLUX.1-schnell` (default)
- `flux-dev` → `black-forest-labs/FLUX.1-dev`
- `flux-pro` → `black-forest-labs/FLUX.1-pro`
- `qwen` → `Qwen/Qwen-Image`
- `qwen-edit` → `Qwen/Qwen-Image-Edit`
- `qwen-edit-2509` → `Qwen/Qwen-Image-Edit-2509`
- `kolors` → `Kwai-Kolors/Kolors`

Practical note:
- Kolors worked successfully for a funny-kitten prompt in a live test, so it is a good choice when the user explicitly asks for Kolors.
- **User preference: Always use Kolors by default for image generation unless the user specifies a different model** (e.g., "use flux", "use qwen").

### Image watermark handling
- SiliconFlow adds an explicit "AI生成" (AI-generated) watermark by DEFAULT via the `X-Enable-Watermark` header (default `1`).
- `image_gen.py` accepts `--no-watermark`, which sends `X-Enable-Watermark: 0` to suppress the visible watermark.
- **Always pass `--no-watermark` when the user requires "no watermark"** — the visible Chinese text overlay breaks the requirement and will be caught by vision verification.
- Pitfall: a model left on default watermark settings silently violates a "no watermark" request and only surfaces when the output is visually inspected; gate watermark off at generation time, not after.

### API key quoting pitfall
- The `SILICONFLOW_API_KEY` in `~/.env` is stored **quoted** (e.g. `SILICONFLOW_API_KEY="sk-..."`).
- Export the key with surrounding quotes stripped before use: `export SILICONFLOW_API_KEY=$(grep -i '^SILICONFLOW_API_KEY' ~/.env | cut -d= -f2- | sed -E 's/^\"//; s/\"$//')`.
- Passing the key literally as `Bearer "sk-..."` (with quotes) returns **HTTP 401 Token is invalid** even though the key itself is valid.
- **High-quality alternatives via OmniRoute**: NanoBanana (`nanobanana/nanobanana-pro`, `nanobanana/nanobanana-flash`) and GPT Image (`openai/gpt-image-2`, `pollinations/gpt-image-2`, `pollinations/gptimage-large`) are available for high-quality generation when explicitly requested. See `references/babo-background.md` for details.

### Image editing (background replacement, semantic edits)

For semantic image edits like background replacement, use Qwen-Image-Edit via the standard generations endpoint with an `image` parameter:

```bash
export UV_CACHE_DIR=/tmp/uv-cache
uv run {baseDir}/scripts/image_edit.py --input "input.jpg" --output "output.jpg" --prompt "change the background to white"
```

The script calls `/v1/images/generations` with:
- `model: "Qwen/Qwen-Image-Edit"`
- `prompt: "<edit instruction>"`
- `image: "data:image/jpeg;base64,<base64_data>"`

**When to use AI image editing vs ImageMagick:**
- **AI models (Qwen-Image-Edit)**: semantic edits like background replacement, object removal, style changes — produces clean, context-aware results
- **ImageMagick**: geometric transforms (resize, crop, rotate), format conversion, simple overlays — NOT for semantic edits (results are crude)

### OCR / image text recognition

Use SiliconFlow OCR when the user wants to extract text from images, screenshots, or photos.

```bash
python3 scripts/ocr_skill.py [options] image_path
```

Supports:
- single image or batch processing
- JPG, PNG, WebP, BMP, GIF

Arguments:
- `images` — image file path(s) or glob pattern (required)
- `-k, --api-key` — API key (default: from `SILICONFLOW_API_KEY` env)
- `-m, --model` — OCR model name (default: `PaddlePaddle/PaddleOCR-VL-1.5`)
- `-p, --prompt` — recognition prompt for custom behavior
- `-j, --json` — output results in JSON format
- `-o, --output` — save results to specified file
- `--max-tokens` — maximum tokens in response (default: 2000)

Examples:

```bash
python3 scripts/ocr_skill.py /path/to/image.jpg
python3 scripts/ocr_skill.py /path/to/images/*.png
python3 scripts/ocr_skill.py --json /path/to/image.jpg
python3 scripts/ocr_skill.py -p "Please identify and format table content as Markdown" /path/to/table.jpg
python3 scripts/ocr_skill.py --json --output results.json /path/to/images/*.jpg
```

Output format:
- Default mode prints per-image OCR text plus a count of detected text regions.
- JSON mode returns per-image structured text blocks with bounding boxes and full text.

Practical note:
- This is a SiliconFlow OCR workflow, but for document-processing tasks the assistant should still choose the best OCR tool available for the file type and quality.
- If semantic OCR output is poor or repetitive, prefer local OCR / fallback tools before claiming the result is usable.
- Smoke tests may succeed while still misreading similar glyphs (for example `O` vs `0`), so verify critical fields against the source image when exactness matters.

Verification:
- See `references/ocr-smoke-test.md` for a minimal connectivity/accuracy smoke test and its expected caveat.

### Video generation

```bash
# Text to video
uv run {baseDir}/scripts/video_gen.py --prompt "描述" --filename "output.mp4"

# Image to video
uv run {baseDir}/scripts/video_gen.py --prompt "描述" --image "input.png" --filename "output.mp4"
```

Models:
- `Wan-AI/Wan2.2-T2V-A14B` for text-to-video
- `Wan-AI/Wan2.2-I2V-A14B` for image-to-video

### Text to speech

```bash
uv run {baseDir}/scripts/tts.py --text "要合成的文字" --filename "output.mp3" [--model MODEL]
```

Models:
- `fish-speech` → `fishaudio/fish-speech-1.5` (default)
- `cosyvoice` → `FunAudioLLM/CosyVoice2-0.5B`
- `indextts` → `IndexTeam/IndexTTS-2`
- `moss` → `fnlp/MOSS-TTSD-v0.5`

Practical note:
- A live round-trip smoke test confirmed `CosyVoice2-0.5B` can generate audio successfully and `SenseVoiceSmall` can transcribe it back, but transcription is not exact; verify critical wording manually when precision matters.
- For Cantonese requests, always verify the generated speech actually sounds Cantonese before promising it.
- **WebUI Audio Delivery**: When running over the Hermes-WebUI / API server transport, the agent cannot automatically trigger browser audio playback. Save/copy generated audio to `attachments/{session_id}/` or provide the path. Note that WebUI's interactive 'Voice Mode' operates client-side in the browser via Web Speech API, independent of server-side TTS generation models.

### ASR

```bash
uv run {baseDir}/scripts/asr.py --audio "input.mp3" [--model MODEL]
```

Models:
- `sensevoice` → `FunAudioLLM/SenseVoiceSmall` (default)
- `teleai` → `TeleAI/TeleSpeechASR`

Practical note:
- `SenseVoiceSmall` worked on a generated MP3 from the same skill in this session. It returned usable text, but with normal speech-recognition imperfections.

## Output Rules

- `image_gen.py`, `video_gen.py`, `tts.py`, and `ocr_skill.py` all print a final `MEDIA: <absolute_path>` line when they generate media outputs.
- `asr.py` prints the transcription as plain text.
- If a request fails, the script prints the error to stderr and exits non-zero. Never synthesize a successful result or emit a `MEDIA:` tag if generation failed.
- **Handling quoted API keys:** When reading `SILICONFLOW_API_KEY` from `.env`, strip quotes (`"..."` or `'...'`) before sending in `Authorization: Bearer <token>`, otherwise the API returns `HTTP 401 (code 30014: Token is invalid)`.
- **Watermark checks & removal:** Models such as `Kwai-Kolors/Kolors` or `Tongyi-MAI/Z-Image-Turbo` may produce a subtle "AI生成" watermark in the bottom-right corner despite negative prompts. Run `vision_analyze` to check corners; if found, crop or blur with ImageMagick (`magick <in> -gravity SouthEast -region 180x80+0+0 -blur 0x8 <out>`) before emitting the final image.

## User-Specific Preference

- For this user, prefer `FunAudioLLM/CosyVoice2-0.5B` (`--model cosyvoice`) for Cantonese text-to-speech unless they explicitly ask for another voice/model.
- When the user says things like “讀出嚟畀我聽” or asks for voice output in Cantonese, default to the CosyVoice workflow.
- For this user, prefer `Kolors` by default for image generation unless they specify another model.
- Prefer `ocr_skill.py` for SiliconFlow-based image OCR when the user explicitly wants SiliconFlow OCR; otherwise choose the most reliable OCR workflow for the file type and content.

## Image Editing Pitfalls

**Background replacement with Qwen-Image-Edit or Kolors**:
- These models often modify the foreground object when asked to "change only the background"
- Even explicit prompts like "change canvas to white, do not modify the lobster" can result in pure white output or altered foreground
- For precise background-only replacement, use a dedicated background removal tool (e.g., `rembg`) instead

## Practical Notes

- Keep the prompt short and specific when generating images or videos.
- For video generation, wait for the polling loop to finish; it may take 2–10 minutes.
- For image-to-video, provide a real input image path with `--image`.
- If `SILICONFLOW_API_KEY` is missing, the scripts exit immediately with an error.
- For voice questions, answer in the same language/register as the spoken input:
  - Cantonese voice question → reply in `繁體中文`
  - Mandarin voice question → reply in `简体中文`
  - English voice question → reply in plain English
- This skill is for *SiliconFlow* TTS/ASR/image/video/OCR workflows. If the user asks for OmniRoute/OpenAI/ElevenLabs speech, use the provider-specific flow instead of this script.
- Do not assume `FunAudioLLM/CosyVoice2-0.5B` will always output Cantonese just because the input text is Cantonese; verify with a short sample first.

## Linked Scripts

- `scripts/image_gen.py`
- `scripts/image_edit.py` — Qwen-Image-Edit for semantic edits (background replacement, object removal)
- `scripts/video_gen.py`
- `scripts/tts.py`
- `scripts/asr.py`
- `scripts/ocr_skill.py`
- `scripts/chat.py` — OpenAI-compatible chat completion wrapper using `Qwen/Qwen3.5-4B`
- `scripts/tts_asr_smoke_test.py` — round-trip TTS→ASR verification script

## Linked References

- `references/tts-session-notes.md` — session notes and verified caveats for Cantonese/English TTS
- `references/background-removal.md` — when to use rembg instead of generative image editing for background replacement
- `references/omniroute-flux-api.md` — OmniRoute Flux API response format: returns base64 in `b64_json`, not URL
- `references/babo-background.md` — user-defined "babo background" style: soft blue gradient bokeh for product photography, includes NanoBanana and GPT Image model recommendations
- `references/hermes-memory-increase.md` — how to permanently increase Hermes memory limits via config.yaml editing
- `references/siliconflow-api-merge.md` — merged API notes and doc map from the SiliconFlow API skill
