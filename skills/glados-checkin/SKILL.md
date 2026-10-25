---
name: glados-checkin
description: Use when the user asks to run the GLaDOS check-in (签到), check GLaDOS points or remaining days, set up the GLaDOS auto check-in locally, or refresh an expired GLaDOS cookie. Runs a local Python script adapted from Devilstore/Glados-Railgun-checkin — no GitHub Actions; config and the account cookie live in the skill's own .env file.
version: 1.0.0
license: GPL-3.0-or-later
---

# glados-checkin

Daily check-in for the GLaDOS proxy service (domains `glados.cloud` and `railgun.info`). Check-in page: https://glados.space/console/checkin (log in first — console URLs bounce to the homepage while signed out). Each check-in earns points; points can optionally auto-exchange for subscription days (plan100 = 100 pts → 10 days, plan200 → 30 days, plan500 → 100 days).

Adapted from https://github.com/Devilstore/Glados-Railgun-checkin (GPL-3.0, see `LICENSE`) for local use. Changes vs upstream: config is loaded from the skill's `.env` (real environment variables still win), the PushDeer import is lazy so `requests` alone is enough when no push keys are set, and the script exits non-zero when every check-in fails so a failed run can't pass silently. One upstream bug fixed along the way: points gained are now carried into the summary (upstream dropped the field).

## Files

- `checkin.py` — the check-in script (status → checkin → points → optional exchange, per cookie × per domain)
- `logging_config.py` — Beijing-time logging with `[I]/[W]/[E]` level tags
- `.env` — live config; **treat it as a secret** (chmod 600, never commit or share it). `.env.example` documents every key.
- `.venv/` — local virtualenv with the dependencies (created during setup)
- `LICENSE` — GPL-3.0 license text

## Setup (once)

From the skill directory:

```bash
python3 -m venv .venv
.venv/bin/pip install requests          # core runs need only this
.venv/bin/pip install pypushdeer serverchan-sdk   # only if push keys will be set
cp .env.example .env
chmod 600 .env
```

Then fill in `GLADOS_COOKIES` in `.env` (see "Cookie" below) before the first real run.

## Running a check-in

```bash
.venv/bin/python checkin.py
```

Report the summary block (签到总结) to the user: per domain — success / repeat / fail, points gained, points total, days remaining, and any exchange result.

Exit codes: `0` = at least one domain succeeded or was already checked in; `1` = no cookie configured, an unexpected error, or every check-in failed.

Result meanings:
- **签到成功** — checked in, points gained shown.
- **重复签到** — already checked in today; harmless, counts as done.
- **签到失败 code=-2** — cookie expired/invalid → ask the user for a fresh cookie (below).
- **code=4 device-mismatch after retry** — the account's last login platform isn't covered by the built-in UA list; surface the `loginDevice` value from the log.

Note: the script tries both domains for every cookie. A failure on one domain with success on the other is normal when the account lives on just one of them — judge by the successful row, and say so.

## Cookie

`GLADOS_COOKIES` is the account's session cookie (`gld:sess=...; gld:sess.sig=...;`). To get/refresh it: log in, open the check-in page (https://glados.space/console/checkin), then F12 → Network → refresh → first request → copy the `Cookie` request-header value. Any other console page works too — the cookie rides on every console request. Multiple accounts: join cookies with `&`.

When the user supplies a new cookie, write it into `.env` (replace the `GLADOS_COOKIES=` value), keep the file chmod 600, never echo the value back, and re-run to verify.

## Config keys (.env)

| Key | Required | Meaning |
|---|---|---|
| `GLADOS_COOKIES` | yes | Session cookie(s), `&`-joined for multiple accounts |
| `GLADOS_EXCHANGE_PLAN` | no | `plan100` / `plan200` / `plan500`; empty = never auto-exchange |
| `PUSHDEER_SENDKEY` | no | PushDeer push key |
| `SERVERCHAN_SENDKEY` | no | Server酱 SendKey |
| `GLADOS_VERBOSE` | no | `true` for per-request logs |

## Scheduling

Manual by default — run it when the user asks. For hands-free daily runs, any scheduler works (cron, a systemd timer, Task Scheduler, or an agent's scheduled jobs); have the runner surface failures — especially code=-2 (expired cookie) — instead of staying silent, and report the summary (status, points, days remaining) after each run.

## Portability

Needs: Python 3.10+, network access to `glados.cloud` / `railgun.info`, and `requests` (plus the optional push SDKs only when push keys are configured). No GitHub account or Actions required.
