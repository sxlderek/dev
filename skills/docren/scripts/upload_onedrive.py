#!/usr/bin/env python3
"""Upload a local dir into a remote folder via rclone, then verify by listing.

Replaces the old stdio-driven ms-365 MCP uploader. rclone streams native bytes
(no base64 in the agent context, no JSON-RPC pipe), handles chunked uploads and
Graph throttling, and is stateless — no daemon to keep alive.

Usage:
    python3 upload_onedrive.py <local-dir> [remote-subpath]

    remote-subpath defaults to "docren/sorted" (relative to the rclone remote).
Example:
    python3 upload_onedrive.py ~/.cache/docren/sorted
    python3 upload_onedrive.py ./out "docren/sorted"

Env: RCLONE_REMOTE (default: onedrive)

Exit 0 only when every local file is present remotely with a matching byte size.
The uploader's own OK is a self-report — the remote listing is the proof.
"""
import json
import os
import subprocess
import sys

REMOTE = os.environ.get("RCLONE_REMOTE", "onedrive")
DEFAULT_SUBPATH = "docren/sorted"


def rclone(*args, check=True, timeout=900):
    proc = subprocess.run(["rclone"] + list(args), capture_output=True, text=True,
                          timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"rclone {' '.join(args)} rc={proc.returncode}\n"
                           f"{proc.stderr.strip()[:800]}")
    return proc


def remote_listing(remote_path):
    p = rclone("lsjson", remote_path, "--files-only", "--no-mimetype", timeout=300)
    return {i["Name"]: i.get("Size", -1) for i in json.loads(p.stdout or "[]")}


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    src = sys.argv[1]
    sub = (sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SUBPATH).strip("/")
    dest = f"{REMOTE}:{sub}"

    if not os.path.isdir(src):
        sys.exit(f"[-] not a directory: {src}")
    files = {f: os.path.getsize(os.path.join(src, f))
             for f in os.listdir(src) if os.path.isfile(os.path.join(src, f))}
    if not files:
        sys.exit(f"[-] nothing to upload: {src} is empty")

    print(f"[*] {len(files)} file(s) -> {dest}")
    rclone("copy", src, dest, "--checksum", "--transfers", "4",
           "--retries", "3", "--low-level-retries", "10",
           "--stats", "10s", "--stats-one-line", "-v")

    print("[*] verifying against the remote listing...")
    remote = remote_listing(dest)
    bad = 0
    for name, size in sorted(files.items()):
        rsize = remote.get(name)
        if rsize is None:
            print(f"ERR {name}  local={size}  MISSING on remote")
            bad += 1
        elif rsize != size:
            print(f"ERR {name}  local={size}  remote={rsize}  SIZE MISMATCH")
            bad += 1
        else:
            print(f"OK  {name}  {size} bytes")

    if bad:
        print(f"[-] {bad} file(s) failed verification — do NOT delete the local copies")
        sys.exit(1)
    print(f"[+] all {len(files)} file(s) verified present on {dest}")


if __name__ == "__main__":
    main()
