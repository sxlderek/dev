---
name: ai-model-research
description: Use when researching AI models and benchmarks.
---

# ai-model-research

Evaluate AI models for OpenClaw agentic office automation workflows.

## Execution Rules
- When called, ask for one or more AI models if none provided.
- Format must be strictly a bulleted list (no tables, no paragraphs, no introductory or concluding chatter).
- Each model entry must contain:
  - Name and parameter size
  - Context window length
  - SWE-bench Verified score (or labeled Lite/self-reported score, or `N/A`)
  - Concatenated capabilities emojis with no spaces: 👁️ Vision, 🎤 Voice Input, 🔍 Search, 🔧 Tool-use, 🧠 Reasoning
- Followed by bulleted pros/cons evaluating OpenClaw agentic office automation suitability (tool reliability, multi-step reasoning, context handling).
- Conclude with a single bulleted emoji legend defining the symbols used.
- If called with `--wiki`, use `silverbullet-remote` to publish the report to `https://sb.sxl.pp.ua/llm-wiki/research/models/<model-slug>.md` and verify using `browser_exec`.
