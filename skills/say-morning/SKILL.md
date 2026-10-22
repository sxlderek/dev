---
name: say-morning
description: Generate FIFA kid avatar saying 早晨 via gpt-image-2.5.
version: 1.0.0
license: MIT
---

# Say Morning Avatar Generator

## When to Use

Use this skill when generating morning greeting cartoon avatars of kids wearing FIFA national football jerseys with a "早晨" speech bubble, or when the user invokes `/say-morning`.

Generate a 1:1 square (512x512) 2D Japanese anime cartoon avatar in Hayao Miyazaki / Studio Ghibli style, featuring a 3-year-old chibi kid supporting a national football team from the FIFA Top 48, flashing a peace sign, with a cartoon speech bubble saying "早晨" (Good Morning), generated via Unorouter `gpt-image-2.5`.

## Specifications

- **Engine & Model**: Unorouter `gpt-image-2.5` (`https://api.unorouter.com/v1/images/generations`)
  - Authentication: `UNOROUTER_API_KEY` (or `HERMES_CUSTOM_API_UNOROUTER_COM_API_KEY`) in environment.
  - Request size: `1024x1024`.
  - Format: OpenAI image generations format, parse `data[0].b64_json` (or `data[0].url`).
  - Resize: Downscale from 1024x1024 to 512x512 using PIL (`Image.Resampling.LANCZOS`).
- **Subject**: 3-year-old chibi anime kid (always use `chibi anime kid` in prompts to prevent safety filters). Chubby cheeks, joyful and authentic open smile.
- **Aesthetic**: Authentic 2D Studio Ghibli / Hayao Miyazaki cel animation art style. Traditional hand-drawn watercolor/gouache background, soft hand-inked linework, matte finish. Zero 3D digital render, no CGI plastic sheen, no gloss.
- **Team Attire**: Randomly selected from FIFA Top 48 (or user-specified). Official national team jersey in accurate colors and crest, plus 1-2 themed accessories (flag hair tie, wristband, pin, or mini scarf).
- **Randomized Traits**: Guarantee unique combinations across runs: hair style (double buns, pigtails, wavy bob, messy bangs), hair color, eye shape/color, distinct facial details (freckles, dimples, hair clips/bows).
- **Pose & Eye Direction**: Large expressive eyes angled 15 degrees / looking toward viewer, hand flashing a clear peace sign (V-sign).
- **Speech Bubble**: Cartoon dialogue bubble containing crisp Chinese characters: `早晨`. `gpt-image-2.5` renders this natively and accurately.
- **Background & Lighting**: Clean, subtle muted geometric patterns in team-complementary pastel tones; soft even natural studio lighting with gentle diffused shadows.
- **Output Destination**: Save output image locally (e.g. `./images/avatar_<team>_<timestamp>.png` or custom path).

## FIFA Top 48 Pool

Argentina, France, Spain, England, Brazil, Belgium, Netherlands, Portugal, Colombia, Italy, Uruguay, Croatia, Germany, Morocco, Japan, USA, Senegal, Iran, Denmark, Switzerland, Korea Republic, Austria, Australia, Ukraine, Turkey, Ecuador, Sweden, Wales, Poland, Hungary, Serbia, Egypt, Nigeria, Algeria, Qatar, Peru, Tunisia, Panama, Scotland, Canada, Czechia, Norway, Slovakia, Romania, Greece, Chile, Paraguay, Mali.

## Generation Script

Run the automated helper script:
```bash
python3 scripts/generate_avatar.py [--team <team_name>] [--text 早晨] [--output <path>]
```

Requirements: Python 3, `Pillow` (`pip install pillow`), and `UNOROUTER_API_KEY` exported in the environment.

## Mandatory Verification Workflow

1. Execute image generation via `generate_avatar.py` or direct API call.
2. Confirm image file exists on disk and size > 0.
3. Inspect image:
   - Verify 2D Ghibli cel art style (not 3D).
   - Verify correct national jersey colors.
   - Verify peace sign hand pose.
   - Verify speech bubble clearly displays `早晨`.
   - Verify no watermarks or unwanted text.
4. Report output path to the user.
