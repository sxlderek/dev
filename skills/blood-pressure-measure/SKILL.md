---
name: blood-pressure-measure
description: "Log home blood pressure readings to a CSV database, remind daily to measure, email the database after each new record, and generate summary reports on request."
version: 1.0.0
license: MIT
---

# blood-pressure-measure

Keeps a long-running CSV log of home blood-pressure readings. The user sends
a reading — usually a photo of the monitor display, or the three numbers in
chat — the agent records it, emails the updated database to a configured
address after every new record, and produces summary reports from the data
when asked.

## Files

- `scripts/send_bp_email.py` — emails the CSV database (zips it first when it
  exceeds the configured size threshold). Reads all config from the
  environment or this skill's `.env`.
- `.env` — live config, **chmod 600, never publish or quote its values**.
  `.env.example` documents every key.
- The CSV database itself lives wherever `BP_CSV_PATH` points (default
  `data/blood_pressure_log.csv` inside this skill directory). It is data, not
  part of the skill — never publish it.

## CSV format

```csv
date,time,systolic_mmhg,diastolic_mmhg,pulse_bpm,device,notes
2026-01-01,11:00,120,80,72,Example Monitor X1,First reading
```

- `date` / `time`: local date and time the measurement was taken (the time
  the user reports it, if they just took it).
- `device` and `notes` may be left empty when unknown.

## Configuration (.env)

| Key | Meaning | Default |
|---|---|---|
| `BP_CSV_PATH` | Path of the CSV database | `data/blood_pressure_log.csv` in this skill dir |
| `BP_MAIL_TO` | Recipient of the database email (required) | — |
| `BP_MAIL_FROM` | Sender address | mail CLI account default |
| `BP_MAIL_SUBJECT` | Subject of the database email | `blood-pressure database` |
| `BP_MAIL_CLI` | Mail CLI binary that accepts `message send --account <acct>` with the RFC822 message on stdin (Himalaya convention) | `himalaya` |
| `BP_MAIL_ACCOUNT` | Account name for the mail CLI | CLI default |
| `BP_ZIP_THRESHOLD_KB` | Zip the CSV before sending when it grows past this size | `500` |
| `BP_REMINDER_TIME` | Daily reminder time (local, 24h) | `11:00` |

## Setup (once)

1. Create the CSV with just the header row at `BP_CSV_PATH`.
2. Copy `.env.example` to `.env`, fill in the real values, `chmod 600 .env`.
3. Create a daily reminder at `BP_REMINDER_TIME` with the agent's scheduling
   tool: remind the user to take a blood-pressure measurement and to reply
   with the numbers or a photo of the monitor.

## Workflow

### Log a reading

1. Extract systolic, diastolic and pulse from the user's photo (vision) or
   message. Read the values back to the user if there is any doubt.
2. Append one row to the CSV with the local date/time.
3. Run the email step (below) — it is part of logging, not optional.
4. Confirm to the user: the values recorded and that the database was emailed.

### Email after every record (standing rule)

After each new record is successfully appended, run:

```bash
python3 scripts/send_bp_email.py
```

The script composes a short body (record count + latest reading), attaches
the CSV — or a `.zip` of it when the file exceeds `BP_ZIP_THRESHOLD_KB` — and
sends it to `BP_MAIL_TO` with subject `BP_MAIL_SUBJECT`. A failed send does
not undo the logged record; report the failure and retry on the next record.

### Reports (on request)

When the user asks for a report, read the CSV and summarize: period covered,
number of readings, average / min / max systolic, diastolic and pulse, and
the trend over time. Present facts only — a home log supports a conversation
with a clinician; do not diagnose, stage, or recommend medication changes.
Noting how averages compare with commonly used home targets (e.g. below
135/85 mmHg) is fine, labelled as general information.

## Notes

- One single reading proves little; technique, rest, caffeine and medication
  timing all move the numbers. Suggest resting 5 minutes and averaging 2–3
  readings when a value looks off, rather than reacting to an outlier.
- Health data is sensitive: the CSV stays local; the only copy that leaves
  the machine is the configured email to the user's own address.

## Portability

Needs: Python 3 (standard library only for the script) and a Himalaya-style
mail CLI (`himalaya` is the reference implementation). The reminder uses
whatever scheduling the host agent provides.
