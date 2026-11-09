---
name: docren
description: "Intelligent document renamer with local and OneDrive sync."
version: 3.2.1
license: MIT
---

# Document Renaming Skill (docren)

Portable document renaming skill that works across environments. Uses vision-capable models for document understanding.

## Trigger Conditions
- User explicitly asks to run `docren` / process documents / rename files
- User types `docren` with a path → process all documents in that directory
- User uploads a PDF or Word document and mentions renaming → process only the uploaded document
- The request clearly and explicitly implies document renaming
- User asks to check email for PDFs, attachments, or mailbox documents and then run docren
- User asks to process multiple documents in a directory (batch mode)

## Mandatory Protocol
**When user runs batch docren:**
1. Reply with acknowledgment: "I swear I will not judge a file by its name."
2. Check the configured docren root directory and/or mailbox (e.g. via Himalaya)
3. Process documents from both locations (vision rename → ocrmypdf searchable)
4. **Automatic Execution & Sorting (MANDATORY)**: Automatically make the PDF searchable, apply renames immediately, and move the processed files into a `sorted/` subdirectory under the docren path. Do NOT ask the user for confirmation before executing.
5. After processing each email's attachment, delete or archive the processed email message from the mailbox
6. Clean up: delete `temp_vision/` when done
7. **Duplicate-check before uploading (mailbox faxes)**: senders re-transmit the same sheet (same ref, same page count), and a duped upload pollutes the archive. Before uploading, compare the new scan against the same-reference file already in `sorted/` by rendering both with `scripts/cmp_pdfs.py` — plain pixel diff alone is unreliable because fax header strips, skew and noise differ between transmissions; use the perceptual-hash hamming distance (~<=10/256 on matching page count = same document). On a match: do NOT upload a second copy, archive the email as usual, and tell the user a duplicate was skipped (offer to keep it if they want).
8. **Verify uploads by listing the remote folder**: an uploader's OK is a self-report. Run `python3 scripts/sync_onedrive.py verify` (or `rclone lsjson onedrive:docren/sorted --files-only`) and match name + byte size against local files before declaring success. Details in `references/onedrive-rclone-access.md`.
   - **Never clear a staging directory on the strength of a listing that came back empty.** An empty result is not proof the file is absent — enumerate the destination folder's children and compare names. A staging directory whose renamed copies are missing from the destination means that upload never landed, so deleting staging destroys the only copy; say so plainly instead of calling the folder "leftover, safe to delete".
9. **All remote I/O goes through `rclone`** — the ms-365 MCP server is no longer installed on this deployment. Use `scripts/sync_onedrive.py` (`pull` → rename → `link` → `push` → `verify` → `clean`) and `scripts/upload_onedrive.py` for a standalone upload. Never pipe file bytes through an LLM tool argument as base64: it bloats context and a truncated base64 string decodes silently into a corrupt file. rclone streams native bytes, so this hazard is structurally gone — keep it that way.
10. **`clean` only after `verify` passes.** The script refuses to delete a remote original unless the manifest holds an explicit original→renamed `link`, that renamed name is in the last verify report's `verified` list, and the renamed file still exists locally. Never delete remote originals by hand to "tidy up".
11. **Email dispatch after sorting (MANDATORY, all modes)**: immediately after each document lands in `sorted/`, send one notification email per document:
    `python3 scripts/notify_email.py send --file "<sorted.pdf>" --date YYYYMMDD --issuer "<company>" --number "<docno|NA>" --desc "<description>" --sorted-path "<path>"`
    The script sends to the recipient from `DOCREN_NOTIFY_TO` (env) or `--to`, subject `docren - <renamed filename>`, a metadata-summary body (date, issuer, doc number, sorted path), and attaches the PDF. A PDF over 20 MB is still reported but the attachment is omitted with a note (file stays safe in `sorted/`).
12. **Flush the mail spool at the START of every docren run**: `python3 scripts/notify_email.py flush`. Failed SMTP sends are spooled as JSON entries in the mail spool (`DOCREN_SPOOL_DIR`, default `~/.cache/docren/mail_spool/` — never under an auto-pruned tmp tree) storing the absolute `sorted/` path; flush retries every entry and removes the ones that send. Never treat a spooled send as delivered.
13. **Mail-loop prevention**: in Email Attachment Mode, skip any incoming message whose subject starts with `docren - ` or whose sender is the configured notification sender (`DOCREN_NOTIFY_FROM`) — those are docren's own notifications and must never be re-ingested.

Script toolchain: run skill scripts with a python that has `pymupdf` installed, and `ocrmypdf` for searchable conversion (languages `eng+chi_sim`). Write multi-line helpers as script files, not `python3 -c` one-liners — shell quoting mangles nested quotes/f-strings and costs retries.

## Automation Policy
- **No scheduled processing**: do not create or rely on recurring cron jobs for docren unless the user explicitly asks for automation.
- **Explicit only**: do not auto-process just because the user typed `docren` alone; ask for or infer a specific explicit request instead.
- **Issue Resolution**: if issues are encountered during processing (e.g., missing dependencies, permission errors), diagnose and fix them so the requested task can complete.
- **Scope**: process only files directly in the target directory unless the user explicitly asks to include subdirectories.

## Configuration

### Docren Home Path
Read `DOCREN_PATH` from `.env` file or environment variables.

**IMPORTANT: Only process files directly in the docren root directory. NEVER process files in directories starting with underscore (`_`):**
- `_check/` — do not process
- `_good/` — do not process
- `_any_other_underscore_dir/` — do not process
- **NEVER move/copy/delete files TO or FROM underscore directories** — leave them completely alone

This rule is enforced to prevent accidents with Syncthing file movements.

Fallback order:
1. `DOCREN_PATH` env var (if set in shell)
2. `DOCREN_PATH` in `.env` file
3. Ask user for the docren directory path

Example `.env` entry:
```
DOCREN_PATH=/path/to/docren
```

### Vision Model
Uses a vision-capable model for visual document understanding (reading letterhead, dates, stamps, tables).

## Routing Policy
**Always use a vision-capable model or vision tool** for document understanding and renaming.

1. **Step 1 — Rename with Vision** (REQUIRED): Use vision analysis to identify date, issuer, number, type
2. **Step 2 — Convert to Searchable** (REQUIRED): Use `ocrmypdf` to make PDF searchable
3. Extract only minimum fields: date, company, document number, document type
4. Ask for clarification only when ambiguity remains

**Why vision first?**
- OCR text parsing is ~17% accurate for renaming (unreliable)
- Vision model is ~99% accurate for renaming
- OCR text parsing fails on: dates, issuer identification, document numbers, document types
- `ocrmypdf` is ONLY reliable for: converting scanned PDF → searchable PDF

## Workflow

### 1. Determine Mode

**OneDrive Cloud Sync Mode:**
When the user mentions `docren` with OneDrive, or when `DOCREN_PATH` points to `onedrive/docren`:
- Execute `scripts/sync_onedrive.py pull`
- Downloads pending files from remote `/docren` to local staging `<CACHE>/docren/staging` (default `~/.cache/docren`)
- Applies OCR (`ocrmypdf`) and structured renaming into `<CACHE>/docren/sorted`
- Records each original→renamed pair with `sync_onedrive.py link <original> <renamed>`
- Uploads the processed searchable PDFs with `sync_onedrive.py push` (remote `/docren/sorted/`)
- Runs `sync_onedrive.py verify`, then `clean` to drop the remote originals
- Dispatches one notification email per sorted document via `scripts/notify_email.py` (Protocol step 11)
- **Transport is `rclone`, not an MCP server.** Directed `copy`/`deletefile`, stateless — deliberately not `rclone bisync` (its state cache aborts on batch rename+delete with "changes exceed safety threshold").

**Automatic Batch Mode:**
When the user types `docren` alone (no file upload, no explicit path):
- Read `DOCREN_PATH` from `.env` (see Configuration section)
- Process all documents in that directory
- Skip `sorted/` and `failed/` subdirectories
- **CRITICAL: Skip ALL directories starting with underscore (`_`) such as `_check/`, `_good/` — never process files in underscore directories**
- Create `sorted/` and `failed/` subdirectories if they don't exist
- Process each document and move to `sorted/` (success) or `failed/` (error)
- Dispatch notification email per sorted document via `scripts/notify_email.py` (see Protocol step 11); run `notify_email.py flush` first (step 12)
- Report a summary

**Explicit Batch Mode:**
When the user specifies a directory path:
- Process all documents in that directory
- **Skip ALL directories starting with underscore (`_`)**
- Create `sorted/` and `failed/` subdirectories if they don't exist
- Move successfully renamed documents to `sorted/`
- Move failed documents to `failed/`
- Dispatch notification email per sorted document via `scripts/notify_email.py` (Protocol step 11)
- Report a summary

**Single-Document Mode:**
When user uploads a document or specifies a single file:
- Process the uploaded/specified document
- Rename it according to standard format
- Save to `sorted/` (success) or `failed/` (error)
- Dispatch notification email via `scripts/notify_email.py` (Protocol step 11)
- Report the new filename and location

- **Email Attachment Mode:**
When user asks to check email for PDF attachments:
- Use email tool or CLI (e.g. Himalaya) to list mail in INBOX:
  `himalaya envelope list --account <ACCOUNT> --has-attachment --json`
- **Skip any message with subject starting `docren - ` or from the configured notification sender** (docren's own notifications — Protocol step 13)
- Download attached PDFs one message at a time:
  `for id in <MESSAGE_IDS>; do himalaya attachment download --account <ACCOUNT> -d <TEMP_DIR> "$id"; done`
  (Himalaya v2 uses `-d <DIR>`, not `--downloads-dir`, and accepts one message ID per invocation).
- Extract and rename each attachment using standard docren rules.
- Save renamed outputs to `sorted/`.
- Archive processed messages:
  `himalaya message move --account <ACCOUNT> -f Inbox -t Trash <MESSAGE_IDS>`
- Report results.

### 2. Extraction Strategy

**CRITICAL RULE: Filename is ALWAYS wrong.**
- **NEVER** base judgment on filename
- **ALWAYS** trust the vision model (document content)
- Filename contains scanner date/time (NOT document date)
- Filename may have wrong document type, issuer, or number

**CRITICAL: OCR (ocrmypdf) is INACCURATE for parsing/renaming. Only use it for searchable conversion.**

**Workflow Order:**
1. **Step 1 — Rename with Vision** (REQUIRED): Use `vision_analyze` to identify date, issuer, number, type
2. **Step 2 — Convert to Searchable** (REQUIRED): Use `ocrmypdf` to make PDF searchable

**Text-based PDFs:**
1. Use `pymupdf` to extract text
2. Try to parse date, company, number, type from text
3. **ALWAYS verify with `vision_analyze`** — OCR text parsing is unreliable even for text PDFs
4. If vision agrees with text parsing, proceed
5. If vision disagrees, **trust vision**

**Scanned PDFs:**
1. Remove blank pages first (see Blank Page Removal section)
2. **Rename with vision first** (render page 1 to PNG, use `vision_analyze`)
3. **Then convert to searchable** with `ocrmypdf`
4. Save searchable PDF with the correct name

**Word Documents:**
1. Extract text directly from `.docx` files
2. **Verify with `vision_analyze`** for accuracy
3. If image-only, treat like scanned PDF

### 2.1 Blank Page Removal
Remove blank pages before OCR or vision analysis to improve accuracy and speed:
- Scanned multi-page PDFs often contain blank trailing pages (e.g. back of single-sided sheet on a duplex feeder).
- Render pages at 72 DPI and compute non-white pixel ratio (`sample < 240`). Pages with non-white ratio < 0.01 are blank and should be removed (`doc.delete_page(page_num)`) before running `ocrmypdf`.
- `import pymupdf`, not `import fitz` (fitz alias is deprecated and warns); and `Pixmap.is_unicolor` is a PROPERTY (`pix.is_unicolor`), not a method — calling it raises `TypeError: 'bool' object is not callable`.

### 2.2 PDF-to-Searchable Conversion
Use `ocrmypdf --skip-text -l eng+chi_tra "<input.pdf>" "<output.pdf>"` to convert scanned PDFs to searchable text.

**Check before OCR — many "scanned" bills are already digital.** Extract text per page with pymupdf first (`[len(p.get_text().strip()) for p in doc]`). Non-zero char counts on every non-blank page mean the PDF already carries a text layer and is searchable: skip `ocrmypdf` entirely rather than re-processing. A page-count that looks short is not proof of truncation — read the document's own page marker (e.g. "page 1/2") before assuming pages are missing.

### 3. Parse and Structure Information
- **Date (YYYYMMDD)**: Document issue date from content (never filename).
- **Company Slug**: Issuer (document creator/letterhead), NOT recipient.
- **Document Number**: Labeled reference/invoice number or `NA`.
- **Short Description**: Concise description (e.g. invoice, broadband-statement).

### 4. Output Suggested Filename
Format: `YYYYMMDD company-slug document-number short-description.pdf`

### 5. Move Files
Move original or converted document to `sorted/` (success) or `failed/` (error).

## Tools Required
- `rclone` - OneDrive transport (any recent version, remote name `onedrive`)
- `pymupdf` - text extraction and thumbnail rendering (any python env with pymupdf)
- Ghostscript CLI - instant zero-dependency page-1 rendering fallback:
  `gs -sDEVICE=jpeg -dFirstPage=1 -dLastPage=1 -r150 -o "<output.jpg>" "<input.pdf>" -q`
- Vision model / `vision_analyze` - document visual understanding
- `ocrmypdf` - searchable PDF layer generation
- `himalaya` - mail CLI: notification dispatch (SMTP) and attachment intake
- `python-docx` - Word text extraction support

## Portability

Configure via environment: `DOCREN_PATH` (docren root), `DOCREN_NOTIFY_TO` / `DOCREN_NOTIFY_FROM` (result-email recipient/sender), `DOCREN_SPOOL_DIR`, `DOCREN_WORK` (rclone pipeline cache), `HIMALAYA_ACCOUNT` (himalaya account name). Host needs: `rclone` (with an `onedrive` remote), `himalaya`, `ocrmypdf`, a python with `pymupdf`, and a vision-capable model for document understanding.

## Pitfalls
- **A local docren archive folder is NOT auto-synced with OneDrive `/docren`**: no cron job, daemon, or watcher mirrors either side. `sync_onedrive.py` is a manual one-shot pipeline that stages in its own cache dir and never touches a separate local archive folder. When asked whether the two folders sync automatically, check for cron jobs and running sync processes, then report that they have diverged — do not assume a mirror. When the user asks to reconcile the two sides, **do NOT propose a two-way merge — the user has explicitly rejected it.** OneDrive `/docren/sorted` is the archive of record: offer a one-way push (local → cloud), a one-way mirror (cloud → local), or a diff report only, and let the user pick.
- **Pair same-series documents by issuer + account + date + byte size, never by filename, when diffing local vs remote**: the same bill can exist on both sides under different description words (locally `Broadband and Home Phone Statement`, in the cloud `Broadband and Service Bill`) with byte sizes within ±1. A name-based sync treats them as distinct and uploads duplicates. Match on the issuer/account/date core of the name first; treat a description-word mismatch as a naming inconsistency to reconcile, not two documents.
- **Write staging dirs and helper scripts under a persistent, writable cache root** — never under a path the runtime restricts writes to or auto-prunes; e.g. `~/.cache/docren`.
- **Himalaya attachment downloads require `-d` and loop over IDs**: Himalaya v2 CLI rejects `--downloads-dir` and cannot batch multiple message IDs in a single `attachment download` call. Always loop message IDs with `-d <DIR>`.
- **Ghostscript avoids python environment mismatches**: If `pymupdf`/`fitz` is missing in the invoking interpreter, render thumbnails with `gs -sDEVICE=jpeg -dFirstPage=1 -dLastPage=1 -r150 -o out.jpg in.pdf` rather than failing or reinstalling packages.
- **Never move or sync files to `sorted/` with their original un-renamed names**: Every document must be renamed with the structured format (`YYYYMMDD company [number] description.pdf`) BEFORE moving to `sorted/` or uploading to cloud storage. Renaming and sorting are inseparable; moving a file to `sorted/` without renaming it defeats the purpose of the skill.
- **Never stream large base64 file payloads through LLM tool arguments for cloud sync**: Passing >500KB base64 encoded file buffers through LLM tool calls inflates model context by hundreds of thousands of tokens, causes timeouts, trips provider content safety filters, and hangs sessions. Execute transfers out-of-band via `rclone` (wrapped by `scripts/sync_onedrive.py` / `scripts/upload_onedrive.py`) so bytes never enter the context.
- **`rclone bisync` is the wrong tool for this pipeline**: bisync keeps a state cache and aborts with "changes exceed safety threshold" when a batch renames and deletes in one pass, needing `--resync` afterwards. docren is one-way, so use directed `rclone copy` + `deletefile`. Reserve bisync for a genuine two-sided mirror.
- **`rclone copy` without `--checksum` re-uploads unchanged files**: always pass `--checksum` so a re-run of `push` is cheap and idempotent.
- **Never `rclone delete`/`purge` a remote folder to "tidy up"**: deletions must go through `sync_onedrive.py clean`, which requires a prior passing `verify` plus an explicit original→renamed link. A remote-only delete can destroy the last copy of a document that never uploaded.
- **OCR (ocrmypdf) is INACCURATE for renaming**: OCR text parsing is only ~17% accurate for extracting date/issuer/number/type. Always use vision analysis for renaming. Use `ocrmypdf` ONLY for searchable PDF conversion.
- Scanned PDFs require vision analysis for accurate renaming; OCR text alone is unreliable.
- Preserve bilingual content when it matters.
- Multiple dates: prioritize the document issue date.
- No document number: use `NA`.
- Batch mode: skip files already in `sorted/` or `failed/` subdirectories.
- **NEVER process files in underscore directories** (`_check/`, `_good/`, etc.).
- Preflight write check: verify runtime can write to target directories before moving files.
- **Issuer is always the document CREATOR** — never use the recipient's name as the company slug.
- **Reuse the archive's existing description wording AND date basis for a recurring document series — but only when the new document IS another instance of that series**: before naming, look at the sibling files already in `sorted/` for the same issuer + account and copy their description word (`Broadband and Service Bill`, not `Monthly Statement`). Two description words for one series means the new file never matches its siblings by name, so upload verification and duplicate detection both read as "not present" and you cannot tell a failed upload from an inconsistent name. When the same issuer bills a DIFFERENT service (e.g. an on-site repair invoice from an issuer whose siblings are installation invoices), do not copy the sibling description verbatim — keep the series' naming style (slug, series prefix) but describe what THIS document actually bills, confirmed from its line items.
- **The filename date is the statement CUTOFF date, not the printed billing month**: monthly bills often print a billing month one month ahead of the cutoff (cutoff 2026/01/31, billing month 2026/02). Archives name on the cutoff: that statement is filed as `20260131 ... Jan 2026.pdf`. Naming off the printed billing month puts the file a month early and it will never match its siblings. Read page 1 of an existing sibling to confirm the convention before naming a new month; see `references/onedrive-rclone-access.md`.
- **Filename date is scanner date, not document date** — always extract from content.
- **Himalaya `message send` reads the message from stdin with NO positional arg** — this build rejects `-`; pipe the RFC822 message and pass only `--account`. `scripts/notify_email.py` already does this.
- **The docren mail spool must live in a persistent dir (`DOCREN_SPOOL_DIR`, default `~/.cache/docren/mail_spool/`), never in an auto-pruned tmp tree** — auto-pruning would silently delete queued notification emails.
- **Notification emails are `docren - <filename>` from the configured notification sender (`DOCREN_NOTIFY_FROM`)** — always filter them out during Email Attachment Mode ingestion or docren will ingest and rename its own notifications (mail loop).
- **Attachment filenames need BOTH `Content-Disposition: filename=` and `Content-Type: name=`** — receiving clients that name attachments only from the `name=` param (Outlook/Exchange, some webmail/mobile clients) show "Untitled Attachment NNNNN.pdf" when it is missing, even though the raw message carries the correct `Content-Disposition`. `scripts/notify_email.py` sets both via `iter_attachments()` + `set_param("name", ...)`; verified that himalaya's re-encode preserves both params. Don't strip the `name=` param when touching `build_message()`.
- **Sanity-check a vision-extracted date against the archive series before naming** — vision can confidently misread a year by decades. If the date breaks the sibling series (archive shows invoice #64891 dated last month; the new #64889 reads as 12 years earlier) or predates the fax/email receive date, do NOT file it: re-render just the date's region at higher DPI (`get_pixmap(dpi=220, clip=Rect(...))` over the header block) and re-ask; only then fall back to asking the user. A renamed file with a wrong date never matches its siblings and pollutes the series.
- **`vision_analyze` region crops are flaky — retry with a standalone file** — the `region` parameter can time out or return a nonsense "image not attached" reply even when the full-image call on the same file just worked. Render the region as its own PNG with pymupdf `clip=` and pass that file path instead of using the `region` parameter; a one-off timeout on a standalone-file call usually clears on a plain retry — retry once before switching methods, and fall back to the full-page image if it persists.
- **A OneDrive/rclone outage must not stall the run** — expired token or unreachable remote only blocks the cloud leg. Mail intake (Himalaya), vision rename, OCR, local sorting, and notification dispatch all continue; use a local archive mirror of `sorted/` for sibling-naming conventions and duplicate checks while the remote is down, and re-auth per `references/onedrive-rclone-access.md` (Token expiry section) for the upload leg.
