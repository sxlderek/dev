---
name: ai-provider-research
description: "Use when researching AI providers for free and cheap models."
---

# AI Provider Research

Proactively research AI inference providers for verified free and low-cost text chat models (excluding embeddings and rerankers).

## Workflow

1. Prompt the user for one or multiple provider names, domains, or URLs if not supplied.
2. Check built-in reference matrix first for known providers (OpenRouter, Groq, DeepInfra, Cerebras, Together AI, SiliconFlow, Mistral, AnyAPI, BluesMinds). For uncataloged domains, conduct live searches via `web_search` and `web_extract`.
3. Allocate balanced quotas across all requested providers (e.g., top $20/N$ cheapest models per provider).
4. Output a Markdown table sorted ascending by output price per 1M tokens with columns:
   - **Model ID and Parameter Size** (use community estimates e.g. `~8B est.` if unpublished)
   - **Context Window and Capabilities** (concatenated emojis: 👁️ Vision, 🎤 Voice Input, 🔍 Search, 🔧 Tool-use, 🧠 Reasoning)
   - **Input/Output Price per 1M Tokens**
5. Include a one-line emoji legend immediately below the table.
6. Provide Free-Tier specifications for any free models (Registration requirements, Paywall boundaries, Usage limits like RPM/RPD, and explicit citation URLs).
7. Provide a 1-3 bullet point Privacy Policy summary covering ZDR, model training, and data sharing.
8. Offer to save the report to the user's SilverBullet LLM-Wiki at `https://sb.sxl.pp.ua/llm-wiki/research/<provider>.md`.
