---
name: renew_asusim
description: Use when the asus.im free-plan subscription renewal is due (scheduled 3 days before expiry), or when the user asks to renew or check the asus.im subscription, or fetch its v2ray subscription link. Auto-applies the site's monthly coupon so the ¥999 plan renews at ¥0.00 through a Cloudflare-protected v2board panel.
version: 1.0.0
license: MIT
---

# renew_asusim

Renews the free plan ("白嫖" / freeloader tier, 100 GB/month, 5 devices) on the
asus.im v2board panel by applying the site's monthly coupon, dropping the
¥999 renewal to ¥0.00. Runs on a schedule 3 days before the current expiry.

## Site facts

- Panel: `https://asus.im` — v2board SPA, Chinese UI, behind a Cloudflare
  managed challenge.
- Login: email `<EMAIL>` (fill from your agent's credential vault; NEVER
  accept the password from chat or type it into the DOM yourself).
- Plan: 白嫖-注意看说明 (100 GB/month, 5 devices).
- Coupon: generation rules are printed on the purchase page after login.
  As of 2026-11 the format is `Free` + year + month, no zero-padding
  (2026/11 → `Free202611`). RE-READ the rules on the page every run — the
  format can change. The price must drop ¥999 → ¥0.00 before submitting;
  if it does not, abort and report instead of paying.
- Blocking orders: an older UNPAID order (e.g. a ¥999 流量重置包 / traffic
  reset pack) silently blocks checkout. Cancel unpaid orders first —
  unpaid means nothing is lost.

## Procedure

1. Cloudflare: solve the managed challenge via a FlareSolverr endpoint
   (`<FLARESOLVER_URL>`), then import the `cf_clearance` cookie into your
   browser with a user agent exactly matching the one FlareSolverr used.
2. Log in with vault-supplied credentials.
3. Read the expiry date on the dashboard. If expiry is more than 3 days
   away, exit with "not due yet".
4. Open the plan's purchase page, read the coupon rules, generate the
   code, apply it, and confirm the total is ¥0.00.
5. Cancel any blocking UNPAID order, submit, and verify the order status
   reaches 已完成 (completed).
6. Verify end state: dashboard expiry moved +30 days, traffic counter reset.
7. Report: old/new expiry, order id, coupon used.

Reschedule after each success: next run = new expiry − 3 days.

## Pitfalls

- Vision models may be unavailable — do not depend on screenshots; work
  text-first through page-state and DOM inspection.
- Submits can fail silently with only a transient toast notification:
  instrument the page to capture toast errors.
- `localStorage.authorization` holds the RAW API token (no `Bearer` prefix)
  — the API rejects the prefixed form.

## Portability

Requires: browser automation, a credential vault (never plaintext
passwords), network access to a FlareSolverr instance for the Cloudflare
challenge, and a GitHub-token-authenticated git or REST client if
publishing. Site-specific facts (plan name, coupon format) drift — verify
them on the page each run.
