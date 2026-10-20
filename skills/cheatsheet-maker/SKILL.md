---
name: cheatsheet-maker
description: Use when the user asks for a cheat sheet on a topic (e.g. "cheatsheet for bash") or from a URL. Researches the topic, formats it like the Docker Compose Cheat Sheet page, and saves it to a SilverBullet space.
---

# Cheatsheet Maker

Create a one-page cheat sheet for a topic or URL and save it to the SilverBullet space as `<Topic> Cheat Sheet`.

## Setup

Credentials live in this skill's `.env` (same folder as this file; see `.env.example` for the template — copy it to `.env` and fill in your own values, and never commit a filled-in `.env`):

- `SB_SPACE_URL` — space base URL
- `SB_TOKEN` — bearer token for the space API

Read them before starting. If the file or token is missing, stop and ask the user. Never hardcode the token anywhere else, and never print it in chat output.

## Workflow

1. **Get the input.** If the user hasn't given a topic or URL, ask for one. A bare word or phrase ("bash", "tmux", "docker compose") is a topic; anything starting with `http` is a URL.
2. **Research.**
   - Topic: web research, official documentation first. Find the official docs/site URL — the intro must link it.
   - URL: fetch that page as the primary source. Fill template gaps (especially the official docs link) from the official documentation.
   - Verify commands and syntax against the sources; do not invent flags or options.
3. **Draft** using the template below. For a URL input, name the topic after the page's subject.
4. **Save** to the space (see "Saving"). If a page with the same name already exists, overwrite it without asking.
5. **Verify** by reading the page back.
6. **Update the index page** (see "Index page").
7. Report the page URL to the user.

## Template

Match the reference page (`Docker Compose Cheat Sheet` in the space):

- **Intro** — one short paragraph: what it is and what it's for, ending with a link to the official documentation/website. No H1 heading; the page name is the title.
- `---` separators between sections.
- **Syntax / commands** — one or more `##` sections of three-column tables: `| Item | Description | Example |` (adapt the first header as fits: Command, Option, Key...). Examples in backticks; multi-line examples in `<pre>` blocks like the reference.
- **One worked example** — a realistic, complete example in a fenced code block.
- **Notes** — a `> **Note:**` callout with the few gotchas that matter.
- **Interview Q&A (optional)** — include when the topic is a tool/technology people commonly interview on (Docker, Python, Kubernetes); skip for pure command references (rsync, tar). The user's request overrides either way ("with Q&A" / "no Q&A"). Format: `## Interview Questions`, then `### Q1: ...` / `**A1:** ...`. Max 5 questions.

## Size budget

One page, soft cap ~120 lines: intro, ~20–30 table rows total, one worked example, short notes. Cover the common 80%; drop exotic flags rather than splitting into a second page.

## Saving

Page name: `<Topic> Cheat Sheet` (title case), at the space root. Write with the HTTP API (the `sb` CLI can also write pages where it is available, but the HTTP API works in any environment):

```sh
curl -sS -X PUT "$SB_SPACE_URL/.fs/<Topic>%20Cheat%20Sheet.md" \
  -H "Authorization: Bearer $SB_TOKEN" \
  -H 'Content-Type: text/plain' \
  --data-binary @/tmp/cheatsheet.md
```

URL-encode the page name in the path. A 200 response means saved. Then read it back (`GET` the same URL) to confirm the content landed, and give the user the page URL: `$SB_SPACE_URL/<Topic>%20Cheat%20Sheet`.

## Index page

After saving, link the new cheat sheet from the space's index page:

1. `GET $SB_SPACE_URL/.fs/index.md`.
2. Find the `## Cheatsheets` section. If `[[<Topic> Cheat Sheet]]` is already listed there, do nothing.
3. Otherwise append a line in the section's existing format — `* [[<Topic> Cheat Sheet]]` — keeping the rest of the page identical. The index contains live query/widget blocks; never reformat or "clean up" anything else on it.
4. If there is no `## Cheatsheets` section, create one (heading plus the link) just before the page's first `----` divider, or at the end if there is none.
5. `PUT` the updated index back the same way as the cheat sheet, then read it back to verify the link is present.
