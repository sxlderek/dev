---
name: cli-install
description: Generate verified Windows PowerShell installation scripts.
---

# cli-install

Generate a single, streamlined PowerShell script for Windows 10/11 x64 to deploy a software package.

## Procedure
1. Ask user for a software package name if not provided.
2. Research official documentation to determine primary vendor-recommended distribution method.
3. Dynamically resolve Downloads directory via registry:
   ```powershell
   $regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
   $regVal = '{374DE290-123F-4565-9164-39C4925E467B}'
   $downloads = [System.Environment]::ExpandEnvironmentVariables((Get-ItemPropertyValue -Path $regPath -Name $regVal))
   ```
4. Output strictly ONE path:
   - (a) winget install
   - (b) choco install
   - (c) dra CLI direct release
   - (d) native CLI commands
   - (e) download to Downloads + manual steps
5. Output all executable code in a single markdown codeblock.
