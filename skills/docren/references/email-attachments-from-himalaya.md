# Email Attachments via Himalaya

Workflow for processing email attachments:

1. List inbox envelopes with attachments:

```bash
himalaya envelope list --account <ACCOUNT> --has-attachment --json
```

2. Download attachments for the selected message IDs into `<TEMP_DIR>/incoming/...`:

```bash
# Himalaya v2 CLI requires -d/--dir and takes one message ID per invocation:
for id in <MESSAGE_IDS>; do
  himalaya attachment download --account <ACCOUNT> -d <TEMP_DIR>/incoming/email-attachments "$id"
done
```

3. Process the resulting PDFs locally with docren.

4. Archive/delete processed messages from Inbox:

```bash
# Move to Trash to avoid missing trash mailbox alias errors:
himalaya message move --account <ACCOUNT> -f Inbox -t Trash <MESSAGE_IDS>
```

## Notes
- `himalaya envelope list --has-attachment --json` is useful because it exposes `has_attachment` and sender info cleanly (note: Himalaya v2 uses `--json`, not `--output json`).
- Message bodies can be image-only PDFs even when the envelope text looks fine.
- `pymupdf` + `rapidocr-onnxruntime` can be used for local extraction.
- `himalaya attachment download` writes attachment files using the original attachment names if available.
- Keep downloaded mail attachments in temporary staging before moving renamed files into `<DOCREN_PATH>/sorted/`.
