#!/usr/bin/env python3
"""docren result-email dispatcher.

Sends one email per processed document to the configured recipient:
  Subject: "docren - <renamed filename>"
  Body:    metadata summary (date, issuer, document number, sorted path)
  Attach:  the processed PDF unless it exceeds ATTACHMENT_MAX_BYTES, in
           which case the email is still sent with an omission note.

If the SMTP send fails, the payload is spooled under SPOOL_DIR as a JSON
entry (the PDF itself is NOT copied — sorted/ is the permanent archive, so
the entry stores its absolute path). `--flush` retries every spooled entry
and removes the ones that succeed. Run `--flush` at the start of every
docren run.

Usage:
  notify_email.py send --file "<sorted.pdf>" --date 20260131 \
      --issuer "<company>" --number "<docno|NA>" --desc "<description>" \
      [--sorted-path "<path shown in body>"] [--to <recipient>] [--spool-only]
  notify_email.py flush [--to <recipient>]
  notify_email.py status
"""

import base64
import json
import mimetypes
import os
import smtplib
import subprocess
import sys
import time

SPOOL_DIR = os.environ.get("DOCREN_SPOOL_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "docren", "mail_spool"))
ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024  # conservative SMTP cap
DEFAULT_TO = os.environ.get("DOCREN_NOTIFY_TO", "")
HIMALAYA = os.environ.get("HIMALAYA_BIN", "himalaya")
ACCOUNT = os.environ.get("HIMALAYA_ACCOUNT", "")
FROM_ADDR = os.environ.get("DOCREN_NOTIFY_FROM", "")


def build_message(filename, meta, file_path=None, omit_note=None):
    from email.message import EmailMessage
    from email.utils import formatdate

    msg = EmailMessage()
    if FROM_ADDR:
        msg["From"] = FROM_ADDR
    msg["To"] = meta.get("to", DEFAULT_TO)
    msg["Subject"] = f"docren - {filename}"
    msg["Date"] = formatdate(localtime=True)
    msg["X-Docren-Notification"] = "true"

    lines = [
        "Processed document:",
        f"  Filename : {filename}",
        f"  Date     : {meta.get('date', 'NA')}",
        f"  Issuer   : {meta.get('issuer', 'NA')}",
        f"  Doc No.  : {meta.get('number', 'NA')}",
        f"  Desc     : {meta.get('desc', 'NA')}",
        f"  Sorted   : {meta.get('sorted_path', file_path or 'NA')}",
    ]
    if omit_note:
        lines.append("")
        lines.append(f"NOTE: {omit_note}")
    msg.set_content("\n".join(lines))

    if file_path and not omit_note:
        mime, _ = mimetypes.guess_type(file_path)
        if mime is None:
            mime = "application/pdf"
        with open(file_path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype=mime.split("/")[0],
                           subtype=mime.split("/")[1], filename=filename)
        # Belt-and-suspenders for clients that name attachments ONLY from the
        # Content-Type `name=` param (Outlook/Exchange and some webmail/mobile
        # clients fall back to "Untitled Attachment NNNNN" without it).
        for part in msg.iter_attachments():
            part.set_param("name", filename)
    return msg


def smtp_send(msg):
    """Send via himalaya CLI (owns SMTP creds). Returns (ok, error)."""
    raw = msg.as_string()
    try:
        proc = subprocess.run(
            [HIMALAYA, "message", "send"] +
            (["--account", ACCOUNT] if ACCOUNT else []),
            input=raw, capture_output=True, text=True, timeout=120,
        )
    except Exception as e:  # timeout, binary missing...
        return False, f"himalaya invocation failed: {e}"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()[:500]
    return True, ""


def spool(filename, meta, file_path):
    os.makedirs(SPOOL_DIR, exist_ok=True)
    entry = {
        "queued_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "filename": filename,
        "file_path": os.path.abspath(file_path),
        "meta": meta,
        "attempts": 0,
        "last_error": "",
    }
    name = f"{int(time.time()*1000)}-{base64.urlsafe_b64encode(filename.encode()).decode()[:40]}.json"
    p = os.path.join(SPOOL_DIR, name)
    with open(p, "w") as f:
        json.dump(entry, f, indent=2)
    return p


def send_one(filename, meta, file_path, spool_only=False):
    """Returns dict {status: sent|spooled, ...}."""
    omit_note = None
    if file_path:
        try:
            size = os.path.getsize(file_path)
        except OSError as e:
            return {"status": "error", "error": f"file missing: {e}"}
        if size > ATTACHMENT_MAX_BYTES:
            omit_note = (f"Attachment omitted: file is {size/1048576:.1f} MB, "
                         f"over the {ATTACHMENT_MAX_BYTES//1048576} MB email cap. "
                         f"It is safe in sorted/.")

    if spool_only:
        p = spool(filename, meta, file_path or "")
        return {"status": "spooled", "spool_path": p}

    msg = build_message(filename, meta, file_path, omit_note)
    ok, err = smtp_send(msg)
    if ok:
        return {"status": "sent", "attachment": "included" if not omit_note else "omitted-size"}
    p = spool(filename, meta, file_path or "")
    with open(p) as f:
        entry = json.load(f)
    entry["attempts"] += 1
    entry["last_error"] = err
    with open(p, "w") as f:
        json.dump(entry, f, indent=2)
    return {"status": "spooled", "spool_path": p, "error": err}


def flush():
    if not os.path.isdir(SPOOL_DIR):
        return {"flushed": 0, "sent": 0, "remaining": 0, "results": []}
    results = []
    sent = 0
    for name in sorted(os.listdir(SPOOL_DIR)):
        if not name.endswith(".json"):
            continue
        p = os.path.join(SPOOL_DIR, name)
        try:
            with open(p) as f:
                entry = json.load(f)
        except Exception as e:
            results.append({"entry": name, "status": "error", "error": str(e)})
            continue
        fp = entry.get("file_path")
        if fp and not os.path.exists(fp):
            results.append({"entry": name, "status": "error",
                            "error": f"spooled file no longer exists: {fp}"})
            continue
        msg = build_message(entry["filename"], entry.get("meta", {}), fp)
        ok, err = smtp_send(msg)
        if ok:
            os.remove(p)
            sent += 1
            results.append({"entry": name, "status": "sent"})
        else:
            entry["attempts"] = entry.get("attempts", 0) + 1
            entry["last_error"] = err
            with open(p, "w") as f:
                json.dump(entry, f, indent=2)
            results.append({"entry": name, "status": "still-spooled", "error": err})
    remaining = len([n for n in os.listdir(SPOOL_DIR) if n.endswith(".json")])
    return {"flushed": len(results), "sent": sent, "remaining": remaining,
            "results": results}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("send", "flush", "status"):
        print(__doc__)
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "flush":
        print(json.dumps(flush(), indent=2))
        return

    if cmd == "status":
        if os.path.isdir(SPOOL_DIR):
            n = len([x for x in os.listdir(SPOOL_DIR) if x.endswith(".json")])
        else:
            n = 0
        print(json.dumps({"spooled": n, "spool_dir": SPOOL_DIR}))
        return

    # send
    args = sys.argv[2:]
    opts = {}
    i = 0
    while i < len(args):
        k = args[i].lstrip("-").replace("-", "_")
        v = args[i + 1]
        opts[k] = v
        i += 2

    file_path = opts.get("file")
    filename = os.path.basename(file_path) if file_path else opts.get("filename")
    if not filename:
        print("error: --file or --filename required", file=sys.stderr)
        sys.exit(2)

    meta = {
        "date": opts.get("date", "NA"),
        "issuer": opts.get("issuer", "NA"),
        "number": opts.get("number", "NA"),
        "desc": opts.get("desc", "NA"),
        "sorted_path": opts.get("sorted_path", file_path),
        "to": opts.get("to", DEFAULT_TO),
    }
    if not meta["to"]:
        print("error: no recipient -- set DOCREN_NOTIFY_TO or pass --to", file=sys.stderr)
        sys.exit(2)
    result = send_one(filename, meta, file_path,
                      spool_only=bool(opts.get("spool_only")))
    print(json.dumps(result, indent=2))
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
