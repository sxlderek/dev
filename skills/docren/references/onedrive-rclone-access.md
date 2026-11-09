# OneDrive Access via rclone (docren batch mode)

docren uses the `rclone` binary directly — no MCP server needed (an ms-365
MCP server would keep Node processes alive 24/7 and force every transfer
through base64-over-JSON-RPC).

- Binary: `rclone` on PATH (v1.75+)
- Remote name: `onedrive` (override with `RCLONE_REMOTE`)
- Config: `~/.config/rclone/rclone.conf`
- Remote root folder for this skill: `docren` (override with `RCLONE_DOCREN_ROOT`)

## Why directed copy, not `rclone bisync`

docren is a one-way pipeline: ingest → rename/OCR → egress → drop the original.
`bisync` keeps a state cache and aborts the whole run with *"changes exceed
safety threshold"* when a batch renames and deletes in one pass, and it needs a
`--resync` after every divergence. Directed `rclone copy` is stateless and has
no conflict model to get wrong.

Use `bisync` only for a genuine mirror of a folder that people edit on both
sides (e.g. a local docren folder ↔ remote `/docren`), and even then run it with
`--resync` on first use and a `--max-delete` guard.

## Pipeline commands

```bash
S=scripts/sync_onedrive.py
python3 $S status   # read-only: remote pending, remote sorted, local dirs
python3 $S pull     # remote /docren -> staging/
# ... vision rename + ocrmypdf each file into sorted/ ...
python3 $S link "scan_0001.pdf" "20260131 acme 1234567 Jan 2026.pdf"
python3 $S push     # sorted/ -> remote /docren/sorted/
python3 $S verify   # must report 0 missing / 0 mismatch
python3 $S clean    # delete remote originals ONLY if verify passed + link exists
```

`clean` is deliberately paranoid: it deletes a remote original only when the
manifest has an explicit original→renamed link, that renamed name appears in the
last `verify` report's `verified` list, and the renamed file still exists
locally. Anything else is kept and reported with the reason.

## Inspecting the remote archive

```bash
# Full listing with sizes (the authoritative archive inventory)
rclone lsjson onedrive:docren/sorted --files-only --no-mimetype

# Names only, newest last
rclone lsf onedrive:docren/sorted

# Pending (unprocessed) documents
rclone lsf onedrive:docren --max-depth 1 --files-only
```

Read the date+issuer series out of that listing to see which months are actually
present — a gap in a monthly series is how a missed upload shows up — and to copy
the established description wording.

**`lsjson` keys are Capitalized (`Name`, `Size`, `Path`)** — parsing the JSON with
lowercase `e['name']` either raises `KeyError` or (with `.get('name','')`) matches
nothing, which reads exactly like a failed upload. Before concluding an upload
never landed, check your parse keys against the raw JSON, or grep the listing for
the filename; a follow-up `rclone copy --checksum` that transfers 0 B confirms
the file was already up.

## Downloading one file (e.g. an existing sorted PDF for duplicate comparison)

```bash
rclone copyto "onedrive:docren/sorted/<name>.pdf" <CACHE>/cmp/existing.pdf
```

Then run `scripts/cmp_pdfs.py existing.pdf candidate.pdf`. rclone fetches native
bytes — no download-URL/JWT dance, and no risk of a redacted URL.

## Uploading and verification

`scripts/upload_onedrive.py` copies a local dir into a remote folder and then
re-lists the remote to compare byte sizes:

```bash
python3 scripts/upload_onedrive.py ~/.cache/docren/sorted
python3 scripts/upload_onedrive.py ./out "docren/sorted"
```

Exit 0 means every local file is present remotely with a matching size. Exit 1
means at least one file is missing or truncated — never delete the local copies
in that case.

- `rclone copy` with `--checksum` skips files already identical on the remote, so
  re-running a push is safe and cheap.
- OneDrive reports a *size*, not a hash, for most items; matching name + byte size
  is the practical verification. For a byte-exact check use `rclone check
  <local> onedrive:docren/sorted --size-only=false`.
- Compare by CONTENT as well as name when they disagree: identical text layer and
  page count on a raw/renamed pair means the renamed copy is just an OCR'd or
  recompressed twin. A local file whose date+issuer+account has no sibling in the
  destination listing is a document that exists nowhere in the cloud, not a
  naming variant.

## Token expiry (`invalid_grant`) and headless re-auth

Symptom: `pull`/any rclone call fails with `couldn't fetch token: invalid_grant:
maybe token expired? - try refreshing with "rclone config reconnect onedrive:"`.
The refresh token is dead; only a full re-auth fixes it.

Drive the wizard through a PTY (background terminal with `pty: true`, then answer
prompts via `process_manage` `submit`):

```bash
rclone config reconnect onedrive:
# "Token already configured - replace it?"  -> y
# "Use web browser to automatically authenticate?" -> n
```

It then starts a local OAuth proxy on `127.0.0.1:53682`, prints
`http://127.0.0.1:53682/auth?state=<STATE>`, and waits for the code.
The 53682 port is reachable only from the host running rclone; if there is no
desktop browser there, complete the flow through the USER's browser:

1. Fetch `curl -s -i 'http://127.0.0.1:53682/auth?state=<STATE>'` and read the
   `Location:` response header — it is the full
   `https://login.microsoftonline.com/.../authorize?...&state=<STATE>` link.
   Hand THAT link to the user — never handle their Microsoft login yourself.
2. User signs in on their own machine; their browser then fails to load the
   redirect to `http://localhost:53682/?code=...&state=<STATE>` (nothing
   listens there). Expected. User copies the full URL from their address bar
   and pastes it back in chat.
3. Replay that redirect against the container-local proxy so rclone (still
   waiting on 53682) receives the code:
   `curl 'http://127.0.0.1:53682/?code=<CODE>&state=<STATE>'`
   The wizard then writes the new token and exits; confirm with
   `rclone about onedrive:` before resuming the pipeline.

Hard rules for this flow:
- Launch the wizard by ABSOLUTE path in the PTY (`$(command -v rclone)`)
  — background pty shells do not inherit PATH, and a bare `rclone` dies with
  "command not found" only after the user has already been sent a link.
- Keep the wizard alive until the code is replayed. An OAuth code is single-use:
  if the wizard died (or the 53682 listener was an orphan), a "Success!" page
  still consumed the code and it is unrecoverable — a manual token POST to
  Microsoft returns `AADSTS70000 invalid_grant`. Kill leftover listeners and
  restart `config reconnect` for a fresh state; never recycle the old code.
- Single-quote the redirect URL when curling it — the code contains `*` and `!`
  that shell history expansion mangles.

While re-auth is pending, keep the run alive locally (mail intake, rename, OCR,
sort, notify) per the OneDrive-outage pitfall in SKILL.md.

## Throttling and retries

OneDrive/Graph throttles bursts (HTTP 429). rclone retries with backoff
automatically; keep `--low-level-retries 10` and `--transfers 4` for batch runs.
Raise `--transfers` only if the account is not being throttled.

## Naming convention for a recurring monthly series: cutoff date, not billing month

Many telco/broadband bills (e.g. Hong Kong ISPs) print a **billing month** (賬單月份) that is one month AHEAD of the
statement **cutoff date** (截數日期). The archive names on the cutoff: a statement
nwith cutoff 2026/01/31, billing month 2026/02, is filed as
`20260131 ... Jan 2026.pdf`. So:
- filename date = cutoff date
- description month = month of the cutoff date
- the printed billing month is NOT the description month (it is cutoff month + 1)
Confirm by reading page 1 of an existing sibling before naming a new month; naming
off the printed billing month produces a series where no file matches its siblings.
