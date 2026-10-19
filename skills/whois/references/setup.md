# Skill Setup Notes (Non-invasive)

This file intentionally avoids copy/paste installation commands.

## Required system binaries

- `whois` (WHOIS lookups)
- `dig` (DNS queries)
- `openssl` (TLS certificate checks)

## Optional screenshot support

The skill should only take a screenshot if screenshot tooling is already available:
- Prefer Hermes `browser_exec` / browser tools with a strict timeout (max 10s) and `--no-sandbox` if running in containers.
- Avoid standalone Node `domain-screenshot.js` unless verified non-hanging in the specific environment.
- **No premature deletion:** Do not schedule aggressive short-lived (<24h) auto-cleanup crons that delete uploaded images while the user is still reviewing.
- **Rendering:** In WebUI / API server environments, deliver via PicX/CDN link, direct URL, and local `MEDIA:/path` tag when supported.

If screenshot tooling is not available, times out, or fails, skip the screenshot immediately and output the text report.
