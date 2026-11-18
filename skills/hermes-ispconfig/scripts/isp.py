#!/usr/bin/env python3
"""CLI bridge to the hermes-ispconfig toolset (compiled dist/, zero npm deps).

Usage:
  isp.py --list                   List all available tools
  isp.py <tool> [key=value ...]   Run one tool

Params: key=value pairs; value parsed as JSON if possible (numbers, true/false,
{...}, [...] otherwise kept as string). Example:
  isp.py isp_site_get primary_id=1
  isp.py isp_dns_record_add type=A zone_id=5 name=www data=1.2.3.4

Config comes from <skill_dir>/.env (ISPCONFIG_API_URL / USER / PASS / SERVER_ID /
VERIFY_SSL / READ_ONLY). Secrets are never printed by this script.
"""
import json
import os
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(SKILL_DIR, "dist")

RUNNER = r"""
const { buildToolset } = require(process.env.DIST_PATH);
const toolName = process.env.TOOL_NAME;
const params = JSON.parse(process.env.PARAMS_JSON || "{}");
const config = JSON.parse(process.env.CONFIG_JSON);
let tools;
try { tools = buildToolset(config); }
catch (e) { fail("config_error", e.message); }
if (toolName === "__list__") {
  console.log(JSON.stringify(tools.map(t => t.name), null, 2)); process.exit(0);
}
// Preflight: exactly ONE login attempt. Aborts on auth failure so a bad password
// can never trigger upstream's per-method login retry flood (server lockout).
async function main() {
  const path = require("path");
  const { ISPConfigClient } = require(path.join(process.env.DIST_PATH, "client.js"));
  const pre = new ISPConfigClient(config);
  try { await pre.login(); }
  catch (e) { fail(e.code || "auth_error", "login failed: " + e.message); }
  const tool = tools.find(t => t.name === toolName);
  if (!tool) fail("unknown_tool", toolName + " not found. Available: " + tools.map(t => t.name).join(", "));
  try {
    const r = await tool.run(params);
    console.log(JSON.stringify(r, null, 2)); process.exit(0);
  } catch (e) { fail(e.code || "error", e.message); }
}
main();
function fail(code, msg) { console.error(JSON.stringify({ error: code, message: msg })); process.exit(1); }
"""


def load_env() -> dict:
    env = {}
    p = os.path.join(SKILL_DIR, ".env")
    if os.path.exists(p):
        with open(p) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = load_env()
    missing = [k for k in ("ISPCONFIG_API_URL", "ISPCONFIG_USER", "ISPCONFIG_PASS") if not env.get(k)]
    if missing:
        print(json.dumps({"error": "missing_config", "keys": missing,
                          "fix": "create " + os.path.join(SKILL_DIR, ".env")}), file=sys.stderr)
        sys.exit(2)
    if not os.path.isdir(DIST):
        print(json.dumps({"error": "missing_dist", "path": DIST,
                          "fix": "npm install && npm run build in the repo, copy dist/ here"}), file=sys.stderr)
        sys.exit(2)

    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "--list":
        tool, rest = "__list__", []
    else:
        tool, rest = args[0], args[1:]

    params = {}
    for a in rest:
        if "=" not in a:
            print(json.dumps({"error": "bad_param", "got": a, "expected": "key=value"}), file=sys.stderr)
            sys.exit(2)
        k, v = a.split("=", 1)
        try:
            params[k] = json.loads(v)
        except (json.JSONDecodeError, ValueError):
            params[k] = v

    config = {
        "apiUrl": env["ISPCONFIG_API_URL"],
        "username": env["ISPCONFIG_USER"],
        "password": env["ISPCONFIG_PASS"],
        "serverId": int(env.get("ISPCONFIG_SERVER_ID", "1") or 1),
        "readOnly": env.get("ISPCONFIG_READ_ONLY", "false").lower() == "true",
        "verifySsl": env.get("ISPCONFIG_VERIFY_SSL", "true").lower() == "true",
    }

    proc = subprocess.run(
        ["node", "-e", RUNNER],
        env={**os.environ,
             "CONFIG_JSON": json.dumps(config),
             "DIST_PATH": DIST,
             "TOOL_NAME": tool,
             "PARAMS_JSON": json.dumps(params)},
        capture_output=True, text=True, timeout=90,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        print(proc.stderr.rstrip() or json.dumps({"error": "node_exit", "code": proc.returncode}),
              file=sys.stderr)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
