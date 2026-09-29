#!/usr/bin/env bash
set -euo pipefail
VENV="<HOME>/.openclaw/workspace/.venv-idocr"
source "$VENV/bin/activate"
python3 "<HOME>/.openclaw/workspace/skills/id-ocr/scripts/extract_id_photo_fullface.py" "$@"
