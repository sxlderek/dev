---
name: yoursafe-transfer
description: Check Yoursafe balance and prepare SEPA transfers to a saved beneficiary.
version: 1.1.0
license: MIT
platforms: [linux, macos, windows]
---

# Yoursafe Transfer & Balance Skill

Automate checking balances and preparing SEPA transfers on [Yoursafe YOU](https://you.yoursafe.com) by driving the user's logged-in Chrome browser via browser automation (e.g. Playwriter).

## Prerequisites

- **Google Chrome** with the user already logged in to `https://you.yoursafe.com`.
  - If a call lands on `accounts.yoursafe.com/account/login`, the session has expired; the user must log in manually. Never automate credential entry.
- **Playwriter CLI** (`npm install -g playwriter@latest` or `npx playwriter@latest`) with the Chrome extension enabled, or equivalent Playwright/CDP automation.
- Launch Chrome with the profile containing the active Yoursafe cookies (e.g. `chrome.exe --profile-directory=Default`).
- Chrome must be running before establishing the automation session.

## Setup

```bash
playwriter session new                 # returns e.g. 1
playwriter -s 1 -e 'state.page = await context.newPage(); await state.page.goto("https://you.yoursafe.com/")'
```

## Reading Values

```bash
playwriter -s 1 --timeout 60000 -e 'const t = await state.page.locator("body").innerText(); console.log(t)'
```

## Endpoints & Flow

### 1. Check Available Balance & Calculate Suggested Transfer
- URL: `https://you.yoursafe.com/`
- Target fields in page text: `Available funds`, `secured as <amount> EUR`.
- Read with `state.page.locator("body").innerText()` and parse in JS.
- **Suggested Transfer Rule**:
  - Always suggest an **integer amount of EUR** to transfer to the user's destination account (e.g. WISE).
  - Leave **1 to 2 EUR** remaining in Yoursafe, factoring in the **0.75 EUR SEPA transfer fee**.
  - Formula:
    `Total deduction = Amount + 0.75 EUR fee`
    To leave between 1.00 and 2.00 EUR remaining from `secured_eur`:
    `suggested_int = Math.floor(secured_eur - 0.75 - 1.0)`
    *(Example: for `100.00 EUR`, suggested is `98 EUR`, deducting `98.75 EUR` and leaving `1.25 EUR` in Yoursafe).*
  - Present the balance, fee, suggested transfer amount, and calculated remainder clearly.

### 2. Initiate Transfer to Saved Beneficiary
1. Navigate to: `https://you.yoursafe.com/transfer`
2. Locate the saved beneficiary link (e.g. `https://you.yoursafe.com/transfer/beneficiary/<id>`).
3. Fill transfer parameters:
   - Amount input: `#id_instructed_amount input`
   - Currency: `#id_instructed_currency input` (default `EUR`)
   - Sender IBAN: `#id_chosen_sender_iban`
   - Note (optional): `#id_note textarea`
4. Form action button: `button:has-text("Confirm")` or `ys-button:has-text("Confirm")`.
5. **Safety rule**: Always pause and request explicit user confirmation before submitting any financial transaction. Never bypass 2FA / mobile app confirmation prompts.

## Filling Fields (Shadow DOM & Extension mode)
Yoursafe uses Web Components with Shadow DOM. In extension mode, click the field before filling to ensure focus:
```bash
playwriter -s 1 -e 'const f = state.page.locator("#id_instructed_amount input"); await f.click(); await f.fill("75")'
```

## Portability
Assumes the host has `node`, `playwriter` (or Playwright), and Chrome installed with active session cookies.
