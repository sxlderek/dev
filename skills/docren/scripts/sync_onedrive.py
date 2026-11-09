#!/usr/bin/env python3
"""docren OneDrive pipeline — rclone edition (replaces the ms-365 MCP server).

Directed, stateless copy/move. Deliberately NOT `rclone bisync`: docren is a
one-way ingest -> process -> egress pipeline, and bisync's state cache aborts
with "changes exceed safety threshold" when a batch renames and deletes at once.

Subcommands, in pipeline order:

    pull                  copy pending top-level docs from remote /docren -> staging
    link ORIGINAL RENAMED record original -> renamed mapping (written during processing)
    push                  copy local sorted/ -> remote /docren/sorted/
    verify                compare remote /docren/sorted against local sorted by name+size
    clean                 delete remote /docren originals whose renamed copy is VERIFIED
    status                read-only: remote pending, remote sorted, local dirs

Safety contract: `clean` refuses to delete anything not proven by a prior
`verify` run plus an explicit `link`. An uploader's OK is a self-report; the
remote listing is the only evidence.

Usage:
    python3 sync_onedrive.py pull
    python3 sync_onedrive.py link "scan_0001.pdf" "20260131 acme 1234567 Jan 2026.pdf"
    python3 sync_onedrive.py push
    python3 sync_onedrive.py verify     # must report 0 missing before clean
    python3 sync_onedrive.py clean

Environment:
    RCLONE_REMOTE       rclone remote name   (default: onedrive)
    RCLONE_DOCREN_ROOT  remote folder path   (default: docren)
    DOCREN_STAGING      local ingest dir     (default: ~/.cache/docren/staging)
    DOCREN_SORTED       local processed dir  (default: ~/.cache/docren/sorted)
"""
import os
import sys
import json
import subprocess

REMOTE = os.environ.get("RCLONE_REMOTE", "onedrive")
ROOT = os.environ.get("RCLONE_DOCREN_ROOT", "docren").strip("/")
BASE = os.environ.get("DOCREN_WORK",
    os.path.join(os.path.expanduser("~"), ".cache", "docren"))
STAGING = os.environ.get("DOCREN_STAGING", os.path.join(BASE, "staging"))
SORTED = os.environ.get("DOCREN_SORTED", os.path.join(BASE, "sorted"))

MANIFEST = os.path.join(BASE, "manifest.json")
VERIFY_FILE = os.path.join(BASE, "verify_report.json")

DOC_GLOB = "*.{pdf,docx,doc,jpg,jpeg,png,tif,tiff,PDF,DOCX,DOC,JPG,JPEG,PNG,TIF,TIFF}"
DOC_EXT = (".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tif", ".tiff")


# --------------------------------------------------------------------------- helpers

def rclone(*args, check=True, timeout=900):
    proc = subprocess.run(["rclone"] + list(args), capture_output=True, text=True,
                          timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"rclone {' '.join(args)} rc={proc.returncode}\n"
                           f"{proc.stderr.strip()[:800]}")
    return proc.returncode, proc.stdout, proc.stderr


def preflight():
    rc, out, _ = rclone("listremotes", check=False, timeout=60)
    if rc != 0:
        sys.exit("[-] rclone not runnable — check `rclone version` and PATH")
    names = [r.rstrip(":") for r in out.split()]
    if REMOTE not in names:
        sys.exit(f"[-] rclone remote '{REMOTE}' not configured "
                 f"(have: {names or 'none'}).\n"
                 f"    See references/onedrive-rclone-access.md for the auth steps.")
    rc, _, err = rclone("lsjson", f"{REMOTE}:", "--max-depth", "1", check=False, timeout=120)
    if rc != 0:
        sys.exit(f"[-] remote '{REMOTE}' unreachable: {err.strip()[:400]}")


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return {"originals": {}}


def save_manifest(m):
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w") as f:
        json.dump(m, f, indent=2)


def remote_pending():
    _, out, _ = rclone("lsjson", f"{REMOTE}:{ROOT}", "--files-only",
                       "--no-mimetype", "--no-modtime", timeout=300)
    items = json.loads(out or "[]")
    return [i for i in items if i["Name"].lower().endswith(DOC_EXT)]


def remote_sorted():
    _, out, _ = rclone("lsjson", f"{REMOTE}:{ROOT}/sorted", "--files-only",
                       "--no-mimetype", timeout=300)
    return {i["Name"]: i.get("Size", -1) for i in json.loads(out or "[]")}


def local_sorted():
    if not os.path.isdir(SORTED):
        return {}
    return {f: os.path.getsize(os.path.join(SORTED, f))
            for f in os.listdir(SORTED)
            if os.path.isfile(os.path.join(SORTED, f)) and f.lower().endswith(DOC_EXT)}


def listdir_files(d):
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))


# ------------------------------------------------------------------------- commands

def cmd_pull():
    os.makedirs(STAGING, exist_ok=True)
    pending = remote_pending()
    if not pending:
        print(f"[+] No pending documents in {REMOTE}:{ROOT}.")
        return
    print(f"[*] {len(pending)} pending document(s) in {REMOTE}:{ROOT}")
    rclone("copy", f"{REMOTE}:{ROOT}", STAGING,
           "--max-depth", "1", "--include", DOC_GLOB,
           "--ignore-existing", "--transfers", "4", "--retries", "3",
           "--stats", "0")

    m = load_manifest()
    for f in listdir_files(STAGING):
        m["originals"].setdefault(f, None)
    save_manifest(m)

    staged = listdir_files(STAGING)
    print(f"[+] Staged {len(staged)} file(s) in {STAGING}")
    for f in staged:
        print(f"    {f}\t{os.path.getsize(os.path.join(STAGING, f))} bytes")
    print(f"[i] Next: vision-rename + ocrmypdf each staged file into {SORTED}, then "
          f"`link <original> <renamed>` for each pair.")


def cmd_link():
    if len(sys.argv) != 4:
        sys.exit("usage: sync_onedrive.py link <original-filename> <renamed-filename>")
    orig, new = sys.argv[2], sys.argv[3]
    if not os.path.exists(os.path.join(SORTED, new)):
        sys.exit(f"[-] {new} does not exist in {SORTED} — process it first.")
    m = load_manifest()
    m["originals"][orig] = new
    save_manifest(m)
    print(f"[+] linked {orig} -> {new}")


def cmd_push():
    os.makedirs(SORTED, exist_ok=True)
    local = local_sorted()
    if not local:
        sys.exit(f"[-] Nothing to push: {SORTED} has no documents.")
    print(f"[*] Pushing {len(local)} file(s) -> {REMOTE}:{ROOT}/sorted/")
    rclone("copy", SORTED, f"{REMOTE}:{ROOT}/sorted",
           "--checksum", "--transfers", "4", "--retries", "3",
           "--low-level-retries", "10", "--stats", "10s", "--stats-one-line", "-v")
    print("[+] push finished — that is a SELF-REPORT. Run `verify` before trusting it.")


def cmd_verify():
    remote, local = remote_sorted(), local_sorted()

    missing, mismatch, ok = [], [], []
    for name, size in local.items():
        if name not in remote:
            missing.append(name)
        elif remote[name] != size:
            mismatch.append({"name": name, "local": size, "remote": remote[name]})
        else:
            ok.append(name)

    report = {
        "remote": f"{REMOTE}:{ROOT}/sorted",
        "local_count": len(local),
        "remote_count": len(remote),
        "verified": sorted(ok),
        "missing_remote": missing,
        "size_mismatch": mismatch,
    }
    os.makedirs(BASE, exist_ok=True)
    with open(VERIFY_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"[*] local  sorted/: {len(local)} file(s)")
    print(f"[*] remote sorted/: {len(remote)} file(s)")
    print(f"[+] verified       : {len(ok)}")
    for label, rows in (("MISSING on remote", missing), ("SIZE MISMATCH", mismatch)):
        if rows:
            print(f"[-] {label} ({len(rows)}):")
            for r in rows:
                if isinstance(r, dict):
                    print(f"    {r['name']}  local={r['local']} remote={r['remote']}")
                else:
                    print(f"    {r}")
    print(f"[i] report -> {VERIFY_FILE}")
    if missing or mismatch:
        print("[-] Do NOT run `clean`: an unverified upload means the remote copy "
              "does not exist and the local file may be the only one.")
        sys.exit(1)
    print("[+] Every local file is present on the remote with a matching byte size.")


def cmd_clean():
    if not os.path.exists(VERIFY_FILE):
        sys.exit(f"[-] No verify report at {VERIFY_FILE} — run `verify` first.")
    with open(VERIFY_FILE) as f:
        report = json.load(f)
    if report.get("missing_remote") or report.get("size_mismatch"):
        sys.exit("[-] Last verify reported missing/mismatched files — refusing to clean.")
    verified = set(report.get("verified") or [])
    if not verified:
        sys.exit("[-] Verify report lists no verified files — refusing to clean.")

    m = load_manifest()
    originals = m.get("originals", {})
    pending = remote_pending()
    if not pending:
        print(f"[+] No pending documents in {REMOTE}:{ROOT} — nothing to clean.")
        return

    removed, kept = [], []
    for item in pending:
        name = item["Name"]
        renamed = originals.get(name)
        if not renamed:
            kept.append((name, "no link recorded (original never processed/renamed)"))
        elif renamed not in verified:
            kept.append((name, f"renamed copy '{renamed}' not verified on remote"))
        elif not os.path.exists(os.path.join(SORTED, renamed)):
            kept.append((name, f"renamed copy '{renamed}' missing locally"))
        else:
            rc, _, err = rclone("deletefile", f"{REMOTE}:{ROOT}/{name}",
                                check=False, timeout=180)
            if rc == 0:
                removed.append(name)
                originals[name] = renamed
            else:
                kept.append((name, f"delete failed: {err.strip()[:120]}"))

    save_manifest(m)
    print(f"[+] Removed {len(removed)} original(s) from {REMOTE}:{ROOT}")
    for n in removed:
        print(f"    - {n}")
    if kept:
        print(f"[!] Kept {len(kept)} original(s):")
        for n, why in kept:
            print(f"    = {n}  ({why})")


def cmd_status():
    pending = remote_pending()
    print(f"remote {REMOTE}:{ROOT}           -> {len(pending)} pending doc(s)")
    for i in pending:
        print(f"    {i['Name']}\t{i.get('Size', '?')} bytes")
    print(f"remote {REMOTE}:{ROOT}/sorted/   -> {len(remote_sorted())} file(s)")
    print(f"local  {SORTED}  -> {len(local_sorted())} file(s)")
    print(f"local  {STAGING}  -> {len(listdir_files(STAGING))} file(s)")


COMMANDS = {"pull": cmd_pull, "link": cmd_link, "push": cmd_push,
            "verify": cmd_verify, "clean": cmd_clean, "status": cmd_status}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    preflight()
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
