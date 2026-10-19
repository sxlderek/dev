#!/usr/bin/env python3
"""Cleanup worker: sleeps for N seconds, then deletes specified file from local disk and GitHub PicX repo."""
import sys, time, os, subprocess

def main():
    if len(sys.argv) < 3:
        print("Usage: cleanup_screenshot.py <delay_seconds> <local_file_path> [github_image_path]", file=sys.stderr)
        sys.exit(1)

    try:
        delay = int(sys.argv[1])
    except ValueError:
        delay = 900
    local_path = sys.argv[2]
    github_path = sys.argv[3] if len(sys.argv) > 3 else None

    time.sleep(delay)

    # 1. Delete local file
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
    except Exception as e:
        print(f"Error deleting local file: {e}", file=sys.stderr)

    # 2. Delete GitHub file via picx.py
    if github_path:
        try:
            picx_candidates = [
                "skills/picx/scripts/picx.py",
                "skills/picx/scripts/picx.py",
                "/workspace/hermes-repo/skills/picx/scripts/picx.py",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "productivity/picx/scripts/picx.py"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "picx/scripts/picx.py"),
            ]
            picx_script = next((p for p in picx_candidates if os.path.exists(p)), picx_candidates[0])
            cmd = [sys.executable, picx_script, "delete", github_path]
            subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            print(f"Error deleting from GitHub: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
