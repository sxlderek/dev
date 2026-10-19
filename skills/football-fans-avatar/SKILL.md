---
name: football-fans-avatar
description: Generate FIFA national football fan 2D cartoon avatars.
---

# Football Fans Avatar

Generate consistent, high-quality, 2D Miyazaki-style cartoon avatars of a chibi anime kid supporting national football teams from the FIFA Top 48.

## Mandatory Specifications

- **Engine / Model**: Always use Pollinations with model `black-forest-labs/flux.2-klein-4b`.
- **Target Resolution**: 1:1 square, 512×512 pixels.
- **Team Selection**: Randomly select from current FIFA Top 48 teams unless explicitly specified.
- **Seeded Randomization**: Always generate and append a unique random numeric seed (`seed=<random_int>`) to guarantee non-duplicate trait combinations.

## Enhanced Prompt Construction Guidelines

### 1. Directional Gaze & Eye Angle (Q1: A)
Do not rely on abstract degree math like "15 degrees". Use concrete anatomical & spatial tokens:
- `"large expressive eyes looking away toward her right side (viewer's left), pupils distinctly shifted toward her right border, subtle side-glance, three-quarter gaze, not looking directly at camera, off-center eye focus"`

### 2. Authentic Ghibli / Miyazaki Aesthetic (Q2: C)
Anchor both artistic medium and character lineage:
- `"classic 1980s-1990s Studio Ghibli cel animation, in the character design style of Mei from My Neighbor Totoro or Ponyo, authentic Hayao Miyazaki watercolor and ink character art, traditional hand-drawn gouache background, flat cel shading, soft hand-inked lineart, matte paper texture finish, zero 3D digital gloss, no CGI plastic sheen"`

### 3. Trait Randomization & Character Specs
- **Subject**: chibi anime kid, chubby rosy cheeks, bright cheerful open smile.
- **Randomized Traits**: Hair style (pigtails, bob, buns, wavy shoulder-length), hair color, eye color, distinct details (freckles, subtle dimples, hair clips/ribbons).
- **Attire**: Official national team jersey in accurate colors and crest, with 1-2 themed accessories (flag hair tie, mini wristband, scarf pin).
- **Background & Lighting**: Soft natural studio lighting, gentle diffused shadows. Clean, subtle muted geometric patterns in team-complementary pastel tones.
- **Negative Constraints**: `"no watermark, no logo, no signature, no text, no 3D render, no plastic skin, no centered direct camera stare, no distorted face"`

## Generation & Verification Workflow

1. **Construct Prompt**: Combine the enhanced gaze tokens, Ghibli character anchors, randomized traits, team details, and randomized seed (`seed=<random_int>`).
2. **Execute Generation**: Call Pollinations via `black-forest-labs/flux.2-klein-4b` (using `POLLINATIONS_API_KEY` from `.env`).
3. **Save**: Save image bytes to `./images/<team_slug>_<timestamp>.png` (`chmod 644`).
4. **Mandatory Vision Verification (`vision_analyze`)**:
   - Inspect the downloaded image.
   - Confirm pupils and gaze are shifted toward her right (off-camera side glance).
   - Confirm authentic 2D Ghibli/Miyazaki style (not glossy 3D/CGI).
   - Confirm accurate team jersey colors and zero watermarks.
   - *If gaze is staring dead-center at the camera or watermark is present, re-roll once with a different seed.*
5. **Display**: Emit strictly via WebUI mount path:
   `MEDIA:./images/<team_slug>_<timestamp>.png`
