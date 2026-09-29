# id-ocr — Avatar generation (on-demand)

Goal: turn the extracted ID photo rectangle into a clean, social-ready artistic avatar.

## Safety / consent
- Always ask for explicit confirmation if generating the avatar requires uploading/sending the cropped photo to a third-party service/model.
- Do not assist with impersonation or fraudulent use.

## Recommended workflow
1) Extract ID photo rectangle (preferred) or fallback crop.
2) Offer preset styles and ask the user to pick one.
3) Generate 1–3 variants.
4) Provide a square (1:1) version for socials.

## Style presets (example prompts)
- **Clean professional**: "Create a high-quality professional headshot avatar, natural skin tones, soft studio lighting, neutral background, realistic but slightly enhanced, sharp eyes, no artifacts."
- **Anime**: "Convert to anime-style portrait, clean line art, soft shading, faithful facial features, flattering, high resolution, simple pastel background."
- **Watercolor**: "Watercolor portrait, textured paper feel, soft washes, elegant, keep facial likeness."
- **Cyberpunk**: "Cyberpunk portrait, neon rim light, futuristic city bokeh background, keep facial likeness, high detail."

## Negative prompt ideas
"blurry, deformed face, extra fingers, text, watermark, logo, low quality, artifacts"

## Output checklist
- Face likeness preserved
- No text/watermarks
- Centered composition
- 1:1 crop for socials
