---
name: selfcheck
description: System health diagnostic tool checking availability of required CLI tools, media libraries (ffmpeg, ImageMagick), and workspace hygiene.
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
---

# Selfcheck Skill

Comprehensive system health and tool diagnostic skill to verify that required system utilities, media encoders, network tools, and runtime binaries are working properly.

## When to Use

- After environment setup, container rebuild, or system provisioning.
- When media processing, document conversion, or network lookup commands fail.
- Periodically as a maintenance check or scheduled cron diagnostic.

## Tool Inventory Checked

The skill verifies the presence and executable status of core utilities:

1. **Network & Web:** `curl`, `ping`, `nslookup`, `whois`, `nmap`
2. **Media & Conversion:** `ffmpeg`, `magick` / `convert` (ImageMagick), `pandoc`

## Usage

Run the selfcheck script directly:

```bash
python3 scripts/selfcheck.py
```

### Script Execution on Windows
On Windows, `scripts/selfcheck.py` automatically uses `creationflags=subprocess.CREATE_NO_WINDOW` to prevent command prompt popups when executing background processes.

## Example Output

```text
============================================================
SYSTEM HEALTH & TOOL SELFCHECK
============================================================

TOOL INVENTORY:
  - curl         : ✅ Present (/usr/bin/curl)
  - ffmpeg       : ✅ Present (/usr/bin/ffmpeg)
  - magick       : ✅ Present (/usr/bin/magick)
  - ping         : ✅ Present (/bin/ping)
  - nslookup     : ✅ Present (/usr/bin/nslookup)
  - whois        : ✅ Present (/usr/bin/whois)
  - nmap         : ✅ Present (/usr/bin/nmap)
  - pandoc       : ✅ Present (/usr/bin/pandoc)

TOOL VERSIONS:
  - ffmpeg       : ffmpeg version 6.0
  - imagemagick  : Version: ImageMagick 7.1.1
  - pandoc       : pandoc 3.1.3

WORKSPACE HYGIENE:
  - Temp Clean   : Removed 0 stale files

============================================================
SUMMARY: ✅ All required tools present and verified.
============================================================
```

## Auto-Repair & Installation Guidance

If a tool is reported as `❌ Missing`, install it via your system package manager:

- **Ubuntu / Debian:**
  ```bash
  sudo apt-get update && sudo apt-get install -y curl ffmpeg imagemagick iputils-ping dnsutils whois nmap pandoc
  ```
- **macOS (Homebrew):**
  ```bash
  brew install curl ffmpeg imagemagick whois nmap pandoc
  ```
- **Windows (Scoop):**
  ```powershell
  scoop install curl ffmpeg imagemagick whois nmap pandoc
  ```
