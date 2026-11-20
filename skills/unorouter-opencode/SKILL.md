---
name: UnoRouter OpenCode
description: Fetch UnoRouter text models (excluding `:free`) and register them in OpenCode so they are selectable as unorouter/<id>.
---

# UnoRouter OpenCode

Refreshes the `providers.unorouter.models` map in your global OpenCode config
(`~/.config/opencode/opencode.jsonc`) from the live UnoRouter inventory, so all
non-free text models become selectable in OpenCode as `unorouter/<modelID>`.

## What it does

1. Reads the UnoRouter API key from `UNOROUTER_API_KEY`, or from OpenCode's
   stored credentials (`auth.json`, set via `/connect` → UnoRouter).
2. `GET https://api.unorouter.com/v1/models` — the live model inventory.
3. Keeps text/chat models only:
   - drops every id ending in `:free`
   - drops models that are purely non-text at the UnoRouter layer
     (image-generation, aihorde, embedding, typesafe-decisions)
   - drops ids signaling image/video/audio/embedding/tts
     (`nano-banana`, `gpt-4o-image`, `grok-video-3`, `text-embedding-*`, …)
4. Enriches each model from `https://models.dev/api.json`:
   display name, family, release date, context/output limits, tool/temperature
   support, reasoning effort levels, and input/output cost.
5. Rewrites `providers.unorouter.models` in the config. A timestamped
   `.bak-<ts>` copy of the previous config is taken first. Everything else in
   the file is preserved.

Models whose live entry has no limits and no catalog metadata (e.g. the
`[1m]` fast variants) are still registered with identity-only entries so they
remain selectable.

## Run

```sh
# from the skill directory
node scripts/refresh.mjs
```

Options:

- `--dry-run` — report what would change without writing the config.
- `--json` — machine-readable summary of the refresh.

After running, models are available immediately in OpenCode as
`unorouter/claude-sonnet-5-5`, `unorouter/gpt-6.1-sol`, etc. (the config is
watched; no restart required).

## Re-run

UnoRouter's inventory changes over time. Re-run `node scripts/refresh.mjs`
whenever you want the model list re-synced; newly appeared models are added and
models no longer offered are dropped from `providers.unorouter.models`.
