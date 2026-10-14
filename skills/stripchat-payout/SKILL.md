---
name: stripchat-payout
description: Use when parsing Stripchat token history into payouts.
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
---

# Stripchat Payout Token-History Breakdown

Turn a Stripchat **studio admin "Tokens History for Last 30 Days"** table (screenshot or
pasted text) into grouped payout sections, each rendered as clean TSV.

## When To Use

- User pastes/shares a Stripchat Tokens History table (a payout row + "Transfer to studio"
  rows) and wants it organized per payout.
- User asks to break the table into sections by payout, or aggregate per user/token.

## Data Model

Each row: **USERS** | **DATE** | **TYPE** | **TOKENS**.

- The payout-account row → **Payout** → token count is **negative**.
- Any other row (studio/model accounts, deleted accounts) → **Transfer to studio** →
  positive.

## Rules (in order)

1. **Section boundary = each payout row.** A new section starts at every payout row; the
   rows that follow it (same/next studio-transfer dates) belong to that payout until the
   next payout row.
2. **Header for each section:** the payout **date + its token total**, e.g.
   `Section — Payout <date>: <total>`. The total is the single payout-row amount (one
   payout per section).
3. **Table body:** only **USERS and TOKENS** columns. Drop the header row and the payout
   row. Keep every "Transfer to studio" user row.
4. **Clean numbers:** strip all whitespace and commas from token counts
   (e.g. `1 234` → `1234`, `-5 678` → `-5678`). Preserve the negative sign.
5. **Output format:** each section as a fenced TSV block, `USER<TAB>TOKEN` per row, with
   no code-block-internal header row.
6. If a section has no transfer rows, state it (e.g. `<empty>`), don't invent data.
7. Preserve usernames verbatim as shown in the source.

## Output skeleton

```
**Section N — Payout <date>: <total>**
<user>	<token>
<user>	<token>
```

## Source ambiguity

When the input is a **screenshot**, cross-check the token counts with a vision step before
finalizing (numbers can be misread; don't trust a first glance). When it's **pasted text**
(extracted OCR/HTML), the numbers are authoritative if the paste is complete.

## Pitfalls

- Don't strip the negative sign from the payout row — that's the payout amount.
- Always end a section at the next payout row, even if a transfer date is newer.
- If a later payout row has no trailing transfers in the visible source, emit that payout
  as its own (possibly empty) section rather than merging.
