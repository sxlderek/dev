#!/usr/bin/env python3
"""
Portable Selfcheck Script for AI Agent Systems
Verifies required system CLI tools, runtime environment, and workspace hygiene.
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List


def run_command(cmd: List[str], timeout: int = 5, cwd: str = None) -> tuple[bool, str]:
    """Run a shell command safely without spawning visible console windows on Windows."""
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=creationflags
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as e:
        return False, str(e)


def check_required_tools(tools: List[str]) -> Dict[str, Any]:
    """Check availability and path of required system CLI tools."""
    results: Dict[str, Any] = {}
    for tool in tools:
        path = shutil.which(tool)
        results[tool] = {
            "exists": path is not None,
            "path": str(path) if path else "",
        }
    return results


def check_tool_versions() -> Dict[str, Any]:
    """Check versions of key media and document tools."""
    versions = {}
    # ffmpeg
    ok, out = run_command(["ffmpeg", "-version"])
    versions["ffmpeg"] = out.split("\n")[0] if ok and out else "Not available"

    # ImageMagick
    ok, out = run_command(["magick", "-version"])
    if not ok:
        ok, out = run_command(["convert", "-version"])
    versions["imagemagick"] = out.split("\n")[0] if ok and out else "Not available"

    # pandoc
    ok, out = run_command(["pandoc", "--version"])
    versions["pandoc"] = out.split("\n")[0] if ok and out else "Not available"

    return versions


def clean_temp_directory(temp_path: str, max_age_hours: int = 24) -> Dict[str, Any]:
    """Clean stale files in the specified temporary directory."""
    if not os.path.exists(temp_path):
        return {"status": "Directory does not exist", "removed": 0}

    count = 0
    now = datetime.now().timestamp()
    max_age_secs = max_age_hours * 3600

    try:
        for f in os.listdir(temp_path):
            fp = os.path.join(temp_path, f)
            if os.path.isfile(fp):
                if now - os.path.getmtime(fp) > max_age_secs:
                    os.remove(fp)
                    count += 1
        return {"status": f"Removed {count} stale files", "removed": count}
    except Exception as e:
        return {"status": f"Error: {e}", "removed": count}


def main():
    print("=" * 60)
    print("SYSTEM HEALTH & TOOL SELFCHECK")
    print("=" * 60)
    print()

    # Core required tools
    required = ["curl", "ffmpeg", "magick", "ping", "nslookup", "whois", "nmap", "pandoc"]
    tools_status = check_required_tools(required)
    tool_versions = check_tool_versions()

    print("TOOL INVENTORY:")
    missing = []
    for tool, info in tools_status.items():
        status = "✅ Present" if info["exists"] else "❌ Missing"
        if not info["exists"]:
            missing.append(tool)
        loc = f" ({info['path']})" if info["path"] else ""
        print(f"  - {tool:12} : {status}{loc}")

    print()
    print("TOOL VERSIONS:")
    for tool, ver in tool_versions.items():
        print(f"  - {tool:12} : {ver}")

    # Check workspace temp if present
    workspace_temp = os.environ.get("WORKSPACE_TEMP", "temp")
    if os.path.isdir(workspace_temp):
        print()
        print("WORKSPACE HYGIENE:")
        res = clean_temp_directory(workspace_temp, max_age_hours=24)
        print(f"  - Temp Clean   : {res['status']}")

    print()
    print("=" * 60)
    if missing:
        print(f"SUMMARY: ⚠️ Warning: {len(missing)} tool(s) missing: {', '.join(missing)}")
    else:
        print("SUMMARY: ✅ All required tools present and verified.")
    print("=" * 60)


if __name__ == "__main__":
    main()
