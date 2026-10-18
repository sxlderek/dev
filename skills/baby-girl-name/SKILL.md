---
name: baby-girl-name
description: "Use when generating cute, wholesome, brandable 8-12 letter social media usernames for baby-girl persona."
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
---

# baby-girl-name

Generate 10 unique baby-girl social media usernames based on phonetic rules and aesthetic constraints.

## Constraints & Requirements

| Property | Rule |
|---|---|
| **Quantity** | Exactly 10 unique usernames |
| **Length** | Strictly between 8 and 12 characters (inclusive) |
| **Allowed characters** | Lowercase letters only (`a–z`), no digits, no underscores, no symbols |
| **Tone & Persona** | Cute, playful, sweet, mildly flirty, positive, wholesome |
| **Chinese Pronounceability** | Vowel-heavy, open syllables (ending in `a, e, i, o, u` or soft nasals `n, ng`). Reduplication encouraged (`mimi`, `lulu`, `bebe`, `coco`, `kiki`). |
| **Forbidden Phonetics** | Heavy consonant clusters difficult for CJK speakers (`str`, `spl`, `thr`, `sch`, `ght`, `cl`, `scr`) |
| **Uniqueness & Safety** | No duplicates, no negative, offensive, or derogatory meanings in English or Chinese pinyin |
| **Output Format** | Strictly output only the 10 usernames, one per line, inside a markdown codeblock (` ``` `) |

---

## Theming & Input Arguments

- **Bare trigger:** `/baby-girl-name`  
  Generates 10 usernames using general baby-girl aesthetic roots (e.g. `peachy`, `honey`, `sweetie`, `cherry`, `sugar`, `blush`, `candy`).
- **Themed trigger:** `/baby-girl-name [theme]`  
  Biases root words toward the provided theme/keyword while strictly maintaining the 8–12 letter length and lowercase rule:
  - *fruit / food:* peach, berry, cherry, melon, cocoa, mocha, honey
  - *color / aesthetic:* pink, pastel, rosy, glow, pearl, angel, star
  - *animal / pet:* bunny, kitty, puppy, fawn, bear
  - *vibe / mood:* wink, kissy, blush, huggy, cutie, cozy, soft

---

## Phonetic Construction Formula

Combine 2 or 3 pleasant phonetic blocks:
1. **Adjective / Cute Noun Root** (4–6 chars): `peachy`, `honey`, `sweeti`, `cherry`, `candyi`, `sugary`, `rosie`, `cutie`, `blushy`, `angel`
2. **Cute Suffix / Reduplication Endings** (4–6 chars): `bebe`, `mimi`, `lulu`, `kiki`, `coco`, `doll`, `winks`, `berry`, `babe`, `puff`

### Strict Length Verification Table (Examples)
- `peachybebe` (10 letters) - OK
- `honeymimi` (9 letters) - OK
- `cutieblush` (10 letters) - OK
- `sweetimimi` (10 letters) - OK
- `cherrydoll` (10 letters) - OK
- `candylulu` (9 letters) - OK
- `kissyberry` (10 letters) - OK
- `babycocoa` (9 letters) - OK
- `sugarbebe` (9 letters) - OK
- `peachywinks` (11 letters) - OK

---

## Output Format Example

```text
peachybebe
honeymimi
cutieblush
sweetimimi
cherrydoll
candylulu
kissyberry
babycocoa
sugarbebe
peachywinks
```
