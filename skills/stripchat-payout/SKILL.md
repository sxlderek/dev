---
name: stripchat-payout
description: Extract Stripchat token history into a clean Google Sheet or TSV table.
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
---

# stripchat-payout

Extracts the `USERS` and `TOKENS` columns from the Stripchat token history page (`stripchat.com/earnings/tokens-history`) via a browser session (e.g. Chrome via Playwriter), strips whitespace and commas from token counts, and outputs either directly to a new Google Sheet or as clean TSV.

## Prerequisites

- **Google Chrome** with an active Stripchat model/studio login session.
- **Playwriter CLI** (`npm install -g playwriter@latest` or `npx playwriter@latest`) with the Chrome extension enabled, or equivalent browser automation.
- For Google Sheets export: Chrome logged into Google with access to create spreadsheets (`sheets.new`).

## Usage

### 1. Export Directly to a New Google Sheet

Opens a new Google Sheet, pastes the extracted data into columns `USERS` and `TOKENS`, sets the title, and returns the sheet URL:

```bash
# Optional configuration:
# export STRIPCHAT_CHROME_PROFILE="your_email@example.com"
# export STRIPCHAT_CHROME_DIR="Profile 1"

bash scripts/export_to_sheets.sh
```

### 2. Output as Clean TSV

Outputs tab-separated values directly to stdout:

```bash
bash scripts/extract_tokens.sh
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `STRIPCHAT_CHROME_PROFILE` | *(first active)* | Profile email/identifier to match in `playwriter session list` |
| `STRIPCHAT_CHROME_DIR` | `Default` | Profile directory name for launching Chrome (e.g. `Default`, `Profile 1`) |

## Data Extraction Rules

- Target URL: `https://stripchat.com/earnings/tokens-history`
- Table Structure: `div.data-table-body-row` containing `.table-cell-username` and `.align-right`
- Cleans whitespace (including non-breaking spaces) and commas from token counts (e.g. `9 090` -> `9090`, `-1 673` -> `-1673`)
- Output Headers: `USERS\tTOKENS`

## Portability

Assumes the host has `bash`, `node`/`playwriter`, and `chrome`. On Windows, clipboard transfer uses PowerShell (`Set-Clipboard`); on macOS/Linux, `pbcopy` or `xclip` can be used as fallback.
