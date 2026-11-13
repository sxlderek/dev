#!/usr/bin/env python3
"""Email the blood pressure CSV database after a new record is logged.

Config comes from real environment variables first, then the skill-local
.env file next to this skill's root. See .env.example for every key.

Sending uses a Himalaya-style mail CLI:
    <BP_MAIL_CLI> message send --account <BP_MAIL_ACCOUNT>
with the RFC822 message piped on stdin (no positional arg).
"""
import csv
import os
import subprocess
import sys
import zipfile
from email.message import EmailMessage
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def load_env() -> dict:
    cfg = {}
    env_file = SKILL_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    cfg.update({k: v for k, v in os.environ.items() if k.startswith("BP_")})
    return cfg


def main() -> int:
    cfg = load_env()
    csv_path = Path(cfg.get("BP_CSV_PATH") or (SKILL_DIR / "data" / "blood_pressure_log.csv")).expanduser()
    mail_to = cfg.get("BP_MAIL_TO")
    if not mail_to:
        print("BP_MAIL_TO is not set (env or skill .env)", file=sys.stderr)
        return 1
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    latest = rows[-1] if rows else None

    body_lines = ["Blood pressure database attached (CSV).", f"Records: {len(rows)}"]
    if latest:
        body_lines.append(
            "Latest: {date} {time} - {systolic_mmhg}/{diastolic_mmhg} mmHg, "
            "pulse {pulse_bpm} bpm".format(**latest)
        )
    body = "\n".join(body_lines) + "\n"

    msg = EmailMessage()
    if cfg.get("BP_MAIL_FROM"):
        msg["From"] = cfg["BP_MAIL_FROM"]
    msg["To"] = mail_to
    msg["Subject"] = cfg.get("BP_MAIL_SUBJECT") or "blood-pressure database"
    msg.set_content(body)

    threshold = int(cfg.get("BP_ZIP_THRESHOLD_KB") or 500) * 1024
    data = csv_path.read_bytes()
    if len(data) > threshold:
        zip_path = csv_path.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(csv_path, arcname=csv_path.name)
        payload = zip_path.read_bytes()
        maintype, subtype, filename = "application", "zip", zip_path.name
    else:
        payload = data
        maintype, subtype, filename = "text", "csv", csv_path.name

    msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    # Receiving clients that name attachments only from Content-Type name=
    # need it alongside Content-Disposition filename=.
    for part in msg.iter_attachments():
        part.set_param("name", filename, header="Content-Type")

    cmd = [cfg.get("BP_MAIL_CLI") or "himalaya", "message", "send"]
    if cfg.get("BP_MAIL_ACCOUNT"):
        cmd += ["--account", cfg["BP_MAIL_ACCOUNT"]]
    result = subprocess.run(cmd, input=msg.as_bytes(), capture_output=True)
    sys.stdout.write(result.stdout.decode(errors="replace"))
    sys.stderr.write(result.stderr.decode(errors="replace"))
    if result.returncode != 0:
        print("SEND FAILED", file=sys.stderr)
        return result.returncode
    print(f"Sent {filename} ({len(payload)} bytes) to {mail_to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
