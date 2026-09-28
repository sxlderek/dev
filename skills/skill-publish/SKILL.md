---
name: skill-publish
description: "Sanitize, generalize, and publish an agent skill to a public GitHub repo as its own subdirectory. Redacts PII/secrets, relativizes absolute paths, neutralizes agent-specific phrasing, then pushes via git or the REST API."
version: 1.0.0
license: MIT
---

# skill-publish

Publish an existing skill to a **public GitHub repository** in a form other
AI agents (Claude Code, OpenClaw, Cursor, etc.) can consume. Copies the skill
into `<repo>/skills/<skill-name>/`, sanitizing it so nothing private leaks.

The target is usually a **public** repo — anything pushed is world-readable and
effectively permanent (forks, caches, mirrors). Treat every byte as public.

## When to use

- User asks to "publish this skill", "push it to my public repo",
  "share this skill online", "make a reusable skill I can deploy elsewhere".
- A skill directory needs to be copied into a GitHub repo for distribution.

## Pipeline

Each step must complete before the next. Do not skip redaction to save time —
stopping before confidence is the safe failure.

### 1. Locate the skill

The source skill may live under a category subdirectory, not just the flat
skills root. Make a case-insensitive by-name search, e.g.
`find <skills-root> -iname SKILL.md -path "*/<name>/*"`. Copy the whole
directory (SKILL.md plus any references/ scripts/ templates/) to the work dir.

Inspect every file — SKILL.md, references, scripts, templates, assets. Secrets
hide in script files just as often as in the main doc.

### 2. Sanitize

Scan every file and replace, with their category label, anything that is:

**PII / identity**
- Email addresses, phone numbers, real/full names, personal usernames
- Street addresses, government IDs
- Payment identifiers (IBAN, SWIFT/BIC, card numbers)
- Company-internal account numbers

**Secrets**
- API keys, tokens (`gho_…`, `sk-…`, JWTs), passwords, private keys
- `.env` values, bearer tokens, AWS/cloud access keys

**Environment**
- Absolute paths (`C:\Users\<you>`, `/home/<you>`, `E:\…`, `/Users/<you>`)
- Hostnames that identify the machine
- Repo URLs pointing at private/identifying accounts

Replace with a stable placeholder, preserving shape so the meaning stays clear:

| Original | Replace with |
|---|---|
| `jane@example.com` | `<EMAIL>` |
| `Jane Doe` | `<AUTHOR>` |
| `acme-user` | `<OWNER>` |
| `C:\Users\<you>\...` | `<HOME>\...` |
| `https://github.com/acme-user/repo` | `<PUBLIC_REPO_URL>` |

If any file carries real secrets (a live API key, a token, a private key the
author still uses), do **not** publish a redacted copy that mangles it — stop
and tell the author; the secret must be rotated, not scrubbed.

### 3. Generalize

Neutralize anything that binds the skill to one agent so other agents can use it.

- **Frontmatter:** drop agent-specific fields (`metadata.hermes`, `related_skills`
  from a private catalog). Keep `name`, `description`, `version`, `license`.
- **Tool calls / commands:** replace agent-specific idioms with neutral ones —
  `mcp_*_save_skill(...)` -> "use your skill-file tool", `hermes config set` ->
  "set the config option", shell programs that may not exist -> reuse the REST
  API fallback (below).
- **Bug workarounds:** remove notes about a specific agent's rendering/display
  bugs, GUI quirks, or screen-reader behaviors — they are noise to other agents.
- **Absolute paths in prose/code:** rewrite as relative to a workspace root or
  `<REPO>`/`<SKILL>` placeholder.
- Optional: add a short "Portability" note listing what must exist on the host
  (e.g. `git`, `gh`/authed curl, network) to run the skill.

Skip anything that is genuinely (a)-agent-private (credentials for that agent's
own service) — do not generalize it; just stay out of scope rather than guess.

### 4. Publish

Clone-commit-push is the primary path; the REST API is the fallback.

**Path:** skills live in a top-level `skills/` directory, one subdirectory per
skill. The first publish creates `skills/`. Also create or update a
`skills/README.md` index listing every published skill.

**Clone-commit-push (preferred):**

1. Shallow-clone the target repo into a temp dir
   (`git clone --depth 1 <repo> <dir>`).
2. `mkdir -p <dir>/skills/<name>` and copy the sanitized files in.
3. Update `skills/README.md`.
4. `git add -A && git commit -m "Add <name> skill"`.
5. `git push`.

**REST API fallback (no git/gh on host):**

- Base URL `https://api.github.com/repos/<owner>/<repo>/contents/<path>`.
- Auth: `Authorization: Bearer <token>` (must have `repo` scope for private,
  `public_repo` for public-only writes).
- Create/update: `PUT` with JSON `{message, content: <base64>, sha?: <existing sha>}`.
- Delete a file: `DELETE` with `{message, sha}`.
- Directory creation is implicit — a PUT to `skills/<name>/SKILL.md` creates
  the parents, so create files bottom-up (deepest reference first).

### 5. Verify

After a successful push, confirm the files are live before telling the author
it worked:

- `curl -fsS <raw-url-of-skill>/SKILL.md` (raw URL only works for **public**
  repos — the whole point here). If it returns the sanitized content, published.
- Or `gh api repos/<owner>/<repo>/contents/skills/<name>`.

Report the browser link as `https://github.com/<owner>/<repo>/blob/<branch>/skills/<name>/SKILL.md`
— never raw.githubusercontent.com unless you confirmed it is public.

## Fail-closed

**Before pushing, if any file still contains identifiable material** — an
email, path under a home dir, a token-shaped string, the author's real name —
or the sanitizer hit something it couldn't confidently classify: **stop.** Show
the leftover matches, do not push. Publishing to a public repo is irreversible
(forks) — refusing is the correct failure.

## Portability

Assumes the host has: `git` (or `curl` + a GitHub token) and network access to
github.com. The skill itself is framework-agnostic after generalization; any
agent that can run shell commands and edit files can drive it.