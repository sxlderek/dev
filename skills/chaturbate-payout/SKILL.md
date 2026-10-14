---
name: chaturbate-payout
description: Use when parsing Chaturbate token history into payouts.
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
---

# Chaturbate Cashed-Out Tokens Breakdown

Extract the **"Cashed-Out Tokens Stats by Sub Account"** table from a Chaturbate
Affiliate dashboard (screenshot or pasted text), strip whitespace/commas from token
counts, and output a clean TSV with the sub-account and its token value.

## When To Use

- User pastes/shares a Chaturbate Affiliate **Stats** page and wants the
  "Cashed-Out Tokens Stats by Sub Account" table extracted.
- User asks for sub-account → token breakdown from that table.

## Data Model

The target table has three columns: **Sub Account** | **Tokens** | **Payout**.
We keep only the **Sub Account** and **Tokens** columns.

## Rules (in order)

1. **Locate the table** under the header *"Cashed-Out Tokens Stats by Sub Account"* —
   ignore the other sections (registration/revshare/contest/winnings/etc.) even though
   they also have a "Sub Account" column. Extract only the Cashed-Out Tokens table.
2. **Keep** the **Sub Account** and **Tokens** columns; drop the **Payout** column
   (dollar amount) unless the user asks for it.
3. **Remove the `Total` row.** Output only the individual sub-account rows.
4. **Clean numbers:** strip all whitespace and commas from token counts
   (e.g. `1 234` → `1234`, `567,890` → `567890`).
5. **Section header:** `Chaturbate <period>`. Source the period from the **Select Period**
   field (also exposed as `id="id_period"`) on the page, e.g.
   `Chaturbate Aug 16 - Aug 31, 2025`.
   - If **no period is visible** in the source, state that in the header rather than
     guessing, e.g. `Chaturbate <no period visible in source>`.
   - The `Select Date` / `Select Date Range` fields are NOT the period — use
     `Select Period` (`id_period`) only.
6. **Output format:** a fenced TSV block, `SUB_ACCOUNT<TAB>TOKEN` per row, no
   code-block-internal header row, no Total row.

## Output skeleton

```
**Chaturbate <period>**
<sub-account>	<token>
<sub-account>	<token>
```

## Source ambiguity

When the input is a **screenshot**, cross-check the token counts with a vision step
before finalizing (numbers can be misread; don't trust a first glance). When it's
**pasted text** (OCR/HTML), the numbers are authoritative if the paste is complete.

## Pitfalls

- Two different dashboards both show "Sub Account" columns — only extract under the exact
  header "Cashed-Out Tokens Stats by Sub Account".
- Always drop the `Total` row (individual accounts only).
- Don't let the `Select Date Range` (e.g. 10/01–10/15) replace `Select Period`
  (e.g. Aug 16 - Aug 31) — they are different fields and the period is the correct one.
- Don't invent a period when none is visible; say so in the header.
