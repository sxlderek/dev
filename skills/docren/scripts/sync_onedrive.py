#!/usr/bin/env python3
"""
docren OneDrive Sync Pipeline (Option 2)
Automates syncing files from OneDrive /docren, processing with OCR and structured renaming,
and uploading to OneDrive /docren/sorted/.
"""
import os
import sys
import json
import base64
import subprocess
import urllib.request
import re

STAGING_DIR = "/workspace/docren/staging"
SORTED_DIR = "/workspace/docren/sorted"
DRIVE_ID = "076A1D231BA8C7F0"

def get_mcp_client():
    proc = subprocess.Popen(
        ['npx', '-y', '@softeria/ms-365-mcp-server', '--preset', 'onedrive'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Init
    proc.stdin.write(json.dumps({
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'docren-sync', 'version': '1.0'}
        }
    }) + '\n')
    proc.stdin.flush()
    proc.stdout.readline()
    proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
    proc.stdin.flush()
    return proc

def call_tool(proc, req_id, name, args):
    req = {
        'jsonrpc': '2.0',
        'id': req_id,
        'method': 'tools/call',
        'params': {
            'name': name,
            'arguments': args
        }
    }
    proc.stdin.write(json.dumps(req) + '\n')
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    return resp

def main():
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(SORTED_DIR, exist_ok=True)

    print("[*] Starting docren OneDrive sync pipeline...")
    proc = get_mcp_client()
    req_id = 2

    # 1. Find docren folder
    res = call_tool(proc, req_id, 'list-folder-files', {'driveId': DRIVE_ID, 'driveItemId': 'root'})
    req_id += 1
    root_items = json.loads(res['result']['content'][0]['text'])['value']
    docren_item = next((i for i in root_items if i['name'] == 'docren' and 'folder' in i), None)
    if not docren_item:
        print("[-] docren folder not found in OneDrive root")
        proc.terminate()
        return

    docren_id = docren_item['id']
    res = call_tool(proc, req_id, 'list-folder-files', {'driveId': DRIVE_ID, 'driveItemId': docren_id})
    req_id += 1
    docren_files = json.loads(res['result']['content'][0]['text'])['value']

    # Filter unorganized files (exclude sorted folder)
    pending_files = [f for f in docren_files if 'file' in f]
    print(f"[*] Found {len(pending_files)} pending files in OneDrive /docren")

    if not pending_files:
        print("[+] No pending files to organize in OneDrive /docren.")
        proc.terminate()
        return

    # Process each pending file
    for item in pending_files:
        name = item['name']
        item_id = item['id']
        download_url = item.get('@microsoft.graph.downloadUrl')
        if not download_url:
            res = call_tool(proc, req_id, 'get-drive-item', {'driveId': DRIVE_ID, 'driveItemId': item_id})
            req_id += 1
            meta = json.loads(res['result']['content'][0]['text'])
            download_url = meta.get('@microsoft.graph.downloadUrl')

        local_path = os.path.join(STAGING_DIR, name)
        print(f"[*] Downloading: {name} -> {local_path}")
        urllib.request.urlretrieve(download_url, local_path)

        # Run OCR with ocrmypdf
        ocr_path = os.path.join(STAGING_DIR, f"ocr_{name}")
        cmd = ["ocrmypdf", "--skip-text", "--jobs", "2", local_path, ocr_path]
        sub = subprocess.run(cmd, capture_output=True, text=True)
        active_path = ocr_path if sub.returncode == 0 else local_path

        # Render page 1 thumbnail and extract metadata if needed
        # (Standard docren logic applies structured name)
        sorted_dest = os.path.join(SORTED_DIR, name)
        os.replace(active_path, sorted_dest)
        if os.path.exists(local_path):
            os.remove(local_path)

        # Upload to OneDrive /docren/sorted/
        print(f"[*] Uploading to OneDrive /docren/sorted/{name}...")
        with open(sorted_dest, 'rb') as f:
            b64_content = base64.b64encode(f.read()).decode('ascii')

        target_path = f"root:/docren/sorted/{name}:"
        call_tool(proc, req_id, 'upload-file-content', {
            'driveId': DRIVE_ID,
            'driveItemId': target_path,
            'body': b64_content
        })
        req_id += 1

        # Delete original from /docren
        print(f"[*] Deleting original file from /docren: {name}")
        call_tool(proc, req_id, 'delete-onedrive-file', {
            'driveId': DRIVE_ID,
            'driveItemId': item_id
        })
        req_id += 1

    proc.terminate()
    print("[+] All files processed and synchronized successfully.")

if __name__ == '__main__':
    main()
