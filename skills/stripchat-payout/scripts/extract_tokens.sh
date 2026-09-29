#!/usr/bin/env bash
set -eo pipefail

CHROME_PROFILE_DIR="${STRIPCHAT_CHROME_DIR:-Default}"

# 1. Launch Chrome if not already running
if command -v cmd.exe >/dev/null 2>&1; then
  cmd.exe /c start chrome --profile-directory="$CHROME_PROFILE_DIR" "https://stripchat.com/earnings/tokens-history" >/dev/null 2>&1 || true
elif command -v google-chrome >/dev/null 2>&1; then
  google-chrome --profile-directory="$CHROME_PROFILE_DIR" "https://stripchat.com/earnings/tokens-history" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
  open -a "Google Chrome" "https://stripchat.com/earnings/tokens-history" >/dev/null 2>&1 || true
fi

# 2. Find active Playwriter session or create a new one
if [ -n "$STRIPCHAT_CHROME_PROFILE" ]; then
  SESSION_ID=$(playwriter session list 2>/dev/null | grep "$STRIPCHAT_CHROME_PROFILE" | awk '{print $1}' | head -n 1)
else
  SESSION_ID=$(playwriter session list 2>/dev/null | awk 'NR>2 && $1 ~ /^[0-9]+$/ {print $1}' | head -n 1)
fi

if [ -z "$SESSION_ID" ]; then
  SESSION_ID=$(playwriter session new 2>/dev/null | grep -oE "Session [0-9]+" | awk '{print $2}')
fi

if [ -z "$SESSION_ID" ]; then
  echo "Error: Failed to obtain Playwriter session ID" >&2
  exit 1
fi

# 3. Navigate, extract, and format clean TSV
playwriter -s "$SESSION_ID" --timeout 60000 -e '
await page.goto("https://stripchat.com/earnings/tokens-history", { waitUntil: "domcontentloaded", timeout: 30000 });
await page.waitForSelector(".data-table-body-row", { timeout: 15000 });
const tsv = await page.evaluate(() => {
  const rows = Array.from(document.querySelectorAll(".data-table-body-row"));
  const records = [["USERS", "TOKENS"]];
  for (const row of rows) {
    const userCell = row.querySelector(".table-cell-username") || row.children[0];
    const tokenCell = row.querySelector(".align-right") || row.children[3];
    const user = userCell ? userCell.innerText.trim() : "";
    let tokens = tokenCell ? tokenCell.innerText.trim() : "";
    tokens = tokens.replace(/[\s,]+/g, "");
    if (user || tokens) records.push([user, tokens]);
  }
  return records.map(r => r.join("\t")).join("\n");
});
console.log("===BEGIN_TSV===");
console.log(tsv);
console.log("===END_TSV===");
' | sed -n "/===BEGIN_TSV===/,/===END_TSV===/{ /===/d; s/^\[log\] //; p; }"
