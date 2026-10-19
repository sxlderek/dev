# SiliconFlow API Merge Notes

These notes summarize the merged SiliconFlow API skill content that complements the media-focused workflows in `siliconflow-skill`.

## What this adds

- SiliconFlow API endpoint navigation
- model selection guidance
- deployment and integration notes
- feature overview and use-case mapping
- troubleshooting and FAQ-style guidance

## Doc map from the upstream skill

- `api_reference.md` — endpoint-level API reference and payload shapes
- `deployment.md` — deployment and environment guidance
- `faqs.md` — common questions and troubleshooting
- `features.md` — platform capabilities and feature overview
- `models.md` — model listings and selection guidance
- `other.md` — miscellaneous notes
- `use_cases.md` — practical workflow examples
- `userguide.md` — onboarding and usage guidance
- `index.md` / `llms.md` / `llms-full.md` — generated overview and long-form views

## Merge guidance

- Keep the existing script-backed chat, OCR, TTS, ASR, image, and video workflows.
- Use the API guidance here when the user asks about SiliconFlow implementation details instead of media generation.
- Prefer concise answers with direct examples when the user is asking about API usage.
