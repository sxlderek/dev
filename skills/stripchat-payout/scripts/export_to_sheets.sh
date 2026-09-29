#!/usr/bin/env bash
set -eo pipefail

SCRATCH_DIR="${TMPDIR:-/tmp}"
TSV_FILE="$SCRATCH_DIR/stripchat_tokens_$$.tsv"
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

# 3. Extract USERS and TOKENS from Stripchat
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
' | sed -n "/===BEGIN_TSV===/,/===END_TSV===/{ /===/d; s/^\[log\] //; p; }" > "$TSV_FILE"

# 4. Copy TSV data to clipboard
if command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -Command "Get-Content -Raw -Path '$TSV_FILE' | Set-Clipboard"
elif command -v pbcopy >/dev/null 2>&1; then
  cat "$TSV_FILE" | pbcopy
elif command -v xclip >/dev/null 2>&1; then
  cat "$TSV_FILE" | xclip -selection clipboard
fi

rm -f "$TSV_FILE"

# 5. Open a new Google Sheet, paste, set title and sharing
playwriter -s "$SESSION_ID" --timeout 60000 -e '
const sheetPage = await context.newPage();
await sheetPage.goto("https://sheets.new", { waitUntil: "domcontentloaded", timeout: 30000 });
await sheetPage.waitForSelector("canvas", { timeout: 20000 });
await sheetPage.waitForTimeout(2500);

const canvas = await sheetPage.$("canvas");
const box = await canvas.boundingBox();
if (box) {
  await sheetPage.mouse.click(box.x + 80, box.y + 40);
  await sheetPage.waitForTimeout(1000);
}

await sheetPage.keyboard.press("Control+v");
await sheetPage.waitForTimeout(2500);

// Rename sheet with timestamp
const title = "Stripchat Tokens History (" + new Date().toISOString().replace("T", " ").slice(0, 16) + ")";
await sheetPage.evaluate((t) => {
  const label = document.querySelector(".docs-title-input-label") || document.querySelector(".docs-title-widget");
  if (label) {
    label.click();
    const input = document.querySelector(".docs-title-input");
    if (input) {
      input.value = t;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      input.blur();
    }
  }
}, title);

await sheetPage.waitForTimeout(1500);

// Set sharing permissions: Anyone with the link
try {
  const shareBtn = await sheetPage.$("div[aria-label*=\"Share\"], [aria-label*=\"Private to only me\"], .scb-icon-button");
  if (shareBtn) {
    const sBox = await shareBtn.boundingBox();
    if (sBox) {
      await sheetPage.mouse.click(sBox.x + 25, sBox.y + 20);
      await sheetPage.waitForTimeout(3000);
      const shareFrame = sheetPage.frames().find(f => f.url().includes("drivesharing/driveshare"));
      if (shareFrame) {
        await shareFrame.click("button[aria-label=\"Restricted change general access\"]");
        await sheetPage.waitForTimeout(1000);
        await shareFrame.evaluate(() => {
          const opt = Array.from(document.querySelectorAll("[role=\"menuitem\"], [role=\"option\"], li, span"))
            .find(el => el.innerText.includes("Anyone with the link"));
          if (opt) opt.click();
        });
        await sheetPage.waitForTimeout(1500);
        await shareFrame.evaluate(() => {
          const btn = Array.from(document.querySelectorAll("button")).find(b => b.innerText.trim() === "Done");
          if (btn) btn.click();
        });
        await sheetPage.waitForTimeout(1500);
      }
    }
  }
} catch (e) {
  // Sharing step non-fatal
}

console.log("===SHEET_URL===");
console.log(await sheetPage.url());
console.log("===END_URL===");
' | sed -n "/===SHEET_URL===/,/===END_URL===/{ /===/d; s/^\[log\] //; p; }"
