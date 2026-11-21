---
name: rewrite
description: Rewrite or translate an email or message into polite, simple language for a target region.
version: 1.1.0
license: MIT
---

# Rewrite

## When to Use

- The user asks to rewrite, translate, or simplify an email or message for a specific region or language variant.
- The user supplies a target country code: `us`, `uk`, `hk`, `tw`, `cn`, or another code.
- No code supplied → silently default to `us` (US English).

Rewrite or translate an email message into friendly, polite, simple language for a target country.

## Step 1 — Resolve target country

| Code | Target |
|---|---|
| us | US English (color, organize) |
| uk | British English (colour, organise) |
| hk | Traditional Chinese, Hong Kong usage |
| tw | Traditional Chinese, Taiwan usage |
| cn | Simplified Chinese, mainland usage |

- **No code supplied** → silently default to `us` (US English). Do not ask.
- **Unknown code** (e.g. sg, jp, fr) → ask the user which language/usage to use. Never guess.

## Step 2 — Get the message

Ask the user to provide the email message (subject + body). Skip asking if the message was already supplied in the request.

## Step 3 — Rewrite rules

1. **Direction**: rewrite in the input's own language; translate only when the input language differs from the target. Mixed-language input → translate fully into the target language.
2. **Chinese targets**: tw/hk keep Traditional script, cn uses Simplified — convert script AND vocabulary, never characters alone.
3. **Tone**: friendly and polite.
4. **Reading level**: simple words and short sentences, understandable by a 10-year-old — but keep adult politeness. Simplify without dumbing down or sounding condescending.
5. **Grammar**: proper grammar in the target language.
6. **Vocabulary**: region-standard usage for the target region (e.g. 軟體 tw / 软件 cn / software us-uk spelling rules). Instruct-level awareness only — no embedded vocab tables. For Chinese regional vocabulary differences consult: https://zh.wikipedia.org/wiki/%E6%B1%89%E8%AF%AD%E5%9C%B0%E5%8C%BA%E7%94%A8%E8%AF%8D%E5%B7%AE%E5%BC%82%E5%88%97%E8%A1%A8
7. Preserve the subject line if the input had one; keep the structure the target language's email conventions require.
8. **Sign-off**: always sign with the user's actual name — never a placeholder like [Your name].

## Step 4 — Output

1. The rewritten content inside a fenced markdown code block (```), ready to copy-paste in one click. Subject line included if the input had one, signed with the user's name.
2. After the code block, a 2–3 line note of key changes: vocabulary choices, regional spellings, tone adjustments. The note stays outside the code block.

No preamble, no recap — just the two parts above.

## Revisions

Freeform follow-ups ("shorter", "more formal", "use X not Y") apply to the last rewrite. Unlimited revision rounds; each revision outputs the same two-part format.
