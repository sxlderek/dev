# Email Attachments via Himalaya

Workflow for processing email attachments:

1. List inbox envelopes with attachments:

```bash
himalaya envelope list --account <ACCOUNT> --output json
```

2. Download attachments for the selected message IDs into `<TEMP_DIR>/incoming/...`:

```bash
himalaya attachment download --account <ACCOUNT> --downloads-dir <TEMP_DIR>/incoming/email-attachments 2 3 4
```

3. Process the resulting PDFs locally with docren.

## Notes
- `himalaya envelope list --output json` is useful because it exposes `has_attachment` and sender info cleanly.
- Message bodies can be image-only PDFs even when the envelope text looks fine.
- `pymupdf` + `rapidocr-onnxruntime` can be used for local extraction.
- `himalaya attachment download` writes attachment files using the original attachment names if available.
- Keep downloaded mail attachments in temporary staging before moving renamed files into `<DOCREN_PATH>/sorted/`.
