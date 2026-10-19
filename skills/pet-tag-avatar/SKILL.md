---
name: pet-tag-avatar
description: Generate manga baby pet avatars with silver name ID tags.
---

# Pet Tag Avatar

Generate high-quality, 1:1 square, manga-style profile pictures of cute baby pets wearing a prominent rectangular silver ID tag customized with a user-provided name.

## Core Specifications

- **Engine / Model**: Always use Pollinations with model `black-forest-labs/flux.2-klein-4b`.
- **Target Resolution**: 1:1 square, 512×512 pixels.
- **Allowed Baby Pets**: Randomly select one from: `cat`, `dog`, `mouse`, `dragon`, `hamster`, `rabbit`, `fish`, `bird`.
- **Seeded Randomization**: Always generate and append a unique random numeric seed (`seed=<random_int>`) to guarantee variety.

## Enhanced Prompt Construction Guidelines

### 1. Subject & Silver ID Tag
- **Subject**: Extremely cute, cheerful baby pet (randomized from allowed list) with soft vibrant fur/scales/feathers, chubby cheeks, joyful expression.
- **Silver ID Tag**: Wearing a prominent, huge rectangular polished silver metal collar tag / pendant displaying the exact user-provided name engraved in very large, crisp, bold, dark ink text.

### 2. Pose & Directional Gaze
- **Gaze Specification**: Three-quarter head turn with large expressive glossy manga eyes directed off-center toward its right side (following the head angle, looking away from the camera), side-glance eye focus, not staring directly at the viewer.

### 3. Art Style & Lighting
- **Aesthetic**: Japanese manga / anime illustration, clean digital line art, vibrant warm saturated colors, soft cell shading.
- **Background & Lighting**: Soft-lit random pleasant pastel gradient background (peach, mint, lavender, warm cream), gentle diffused studio lighting.
- **Negative Constraints**: `no watermark, no logo, no signature, no extra text, no distorted lettering, no direct camera stare, no 3D CGI plastic render`.

## Execution Workflow

1. **Prompt for Name**: If the user has not provided a name, ask for the name to put on the silver tag.
2. **Select Pet**: Randomly choose one from `cat`, `dog`, `mouse`, `dragon`, `hamster`, `rabbit`, `fish`, `bird`.
3. **Execute Generation**:
   - Construct prompt with exact pet type, name on tag, gaze cue, aesthetic anchors, and random seed.
   - Call Pollinations API using model `black-forest-labs/flux.2-klein-4b` with authenticated `POLLINATIONS_API_KEY`.
4. **Save**: Save image bytes to `./images/baby_pet_<name>_<seed>.png` (`chmod 644`).
5. **Mandatory Vision Verification (`vision_analyze`)**:
   - Verify pet species and cute manga appearance.
   - Verify the name on the rectangular silver tag is clearly legible and correctly spelled.
   - Verify gaze is off-center (side-glance) and zero watermarks/signatures exist.
6. **Display**: Emit strictly via WebUI mount path:
   `MEDIA:./images/baby_pet_<name>_<seed>.png`
