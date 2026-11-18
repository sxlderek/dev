#!/usr/bin/env python3
"""Bridge: Hermes CLI -> hermes-ispconfig toolset (compiled dist/, zero npm deps).

Usage:
  isp.py --list                   List all available tools (incl. bridge extras)
  isp.py <tool> [key=value ...]   Run one tool
  isp.py isp_client_inventory client_id=N
                                  Per-client service inventory (bridge extra:
                                  ONE login, sweeps every service class, matches
                                  ownership client-side by sys_groupid)

Params: key=value pairs; value parsed as JSON if possible (numbers, true/false,
{...}, [...]) otherwise kept as string. Example:
  isp.py isp_site_get primary_id=1
  isp.py isp_dns_record_add type=A zone_id=5 name=www data=1.2.3.4

Config comes from <skill_dir>/.env (ISPCONFIG_API_URL / USER / PASS / SERVER_ID /
VERIFY_SSL / READ_ONLY). Secrets are never printed by this script.

Client-creation defaults (isp_client_add / isp_provision_site): contact_name and
company_name to the client name, email to <client-name>@example.com, country to HK,
language to en, customer_no to a random 6-char lowercase-alphanumeric code whose
FIRST CHARACTER IS A LETTER, deduped against existing clients (unchecked random
only if the dedup lookups fail), password to a random 16-char alphanumeric string
ALSO STARTING WITH A LETTER (printed once to stderr on
creation — server credentials are never printed; generated CLIENT passwords are,
by design), and
limits + web_php_options/ssh_chroot/template_master merged live from the panel's
"Default" client template (the remote API IGNORES template_id on client_add — verified
empirically — so the bridge copies the template's fields itself). Explicitly
passed params always win over defaults.
"""
import json
import os
import secrets
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


# --- Client-creation defaults (standing user directive) -----------------------

DEFAULT_EMAIL_DOMAIN = "example.com"   # -> <client-name>@example.com
DEFAULT_COUNTRY = "HK"
DEFAULT_LANGUAGE = "en"                # tform-mandatory; not carried by client templates
DEFAULT_TEMPLATE_NAME = "Default"      # limits source; template_id ignored by API
CUSTOMER_NO_POOL = "abcdefghijklmnopqrstuvwxyz0123456789"  # lower-case (directive)
CUSTOMER_NO_LEN = 6
CUSTOMER_NO_FIRST_ALPHA = True  # directive: first char must be a letter

# Password directive (2026-11-18): 16-char ALPHANUMERIC, first char must be a
# LETTER (mixed case now allowed — resolves the earlier lower-only conflict).
# Server still enforces min length 10 + strength >= 4 ("Strong"): with 2+
# character classes the validator needs points >= 4, guaranteed by mixing cases
# + digits (variety 3, lower=2pts at 16 chars -> strength 5).
PASSWORD_POOL = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PASSWORD_LEN = 16


def gen_password() -> str:
    """16-char alphanumeric password, first char a letter (directive 2026-11-18).

    Mixed case + digits guarantee validator strength 4+ (lowercase body scores
    2 points at 16 chars, 3 varieties -> strength 5).
    """
    chars = [secrets.choice("".join(
        c for c in PASSWORD_POOL if c.isalpha()))]
    chars += [secrets.choice(PASSWORD_POOL) for _ in range(PASSWORD_LEN - 1)]
    return "".join(chars)

# Fields copied from the Default template into client_add. Whitelist = fields
# empirically verified API-writable (probe 2026-11-18: passing the full template
# tripped err_invalid_option x3 on non-writable template bookkeeping fields).
TEMPLATE_LIMIT_FIELDS = [
    "limit_traffic_quota", "limit_web_quota", "limit_web_domain",
    "limit_maildomain", "limit_mailbox", "limit_mailalias",
    "limit_mailaliasdomain", "limit_mailforward", "limit_mailcatchall",
    "limit_mailrouting", "limit_mail_wblist", "limit_mailfilter",
    "limit_fetchmail", "limit_mailquota", "limit_spamfilter_wblist",
    "limit_spamfilter_user", "limit_spamfilter_policy", "limit_cgi",
    "limit_ssi", "limit_perl", "limit_ruby", "limit_python",
    "limit_hterror", "limit_wildcard", "limit_ssl", "limit_mail_backup",
]

# tform-mandatory fields on client_add (2026-11-18 server: contact_error_empty /
# language_error_empty / web_php_options_notempty / ssh_chroot_notempty).
# web_php_options + ssh_chroot are carried by the Default template; the rest get
# static defaults in apply_client_defaults.
TEMPLATE_MANDATORY_FIELDS = ["web_php_options", "ssh_chroot"]


def fetch_client_defaults_bundle(config: dict) -> dict:
    """One node run (one login): Default-template fields + a unique customer_no.

    Returns {} on hard failure (node error / unparseable output) so client_add
    still proceeds with explicit params + required base fields; customer_no then
    falls back to an unchecked random draw in apply_client_defaults. Internal
    debug keys (prefixed __) are stripped by callers before use.
    """
    runner = r"""
const path = require("path");
const crypto = require("crypto");
const { ISPConfigClient } = require(path.join(process.env.DIST_PATH, "client.js"));
async function main() {
  const c = new ISPConfigClient(JSON.parse(process.env.CONFIG_JSON));
  await c.login();
  const out = {};
  // Default-template fields (limits + web_php_options/ssh_chroot/template_master)
  try {
    const rows = await c.call("client_templates_get_all", {});
    const tpl = (rows || []).find(t => t.template_name === process.env.TPL_NAME);
    if (tpl) {
      const fields = JSON.parse(process.env.TPL_FIELDS);
      for (const f of fields) if (tpl[f] !== undefined && tpl[f] !== null) out[f] = tpl[f];
      if (tpl.template_id !== undefined && tpl.template_id !== null) out.template_master = tpl.template_id;
    }
  } catch (e) { /* template failure -> caller degrades to email/country-only */ }
  // Unique customer_no: 6 chars from lowercase+digits, deduped against existing
  // clients. client_get_all returns BARE ID STRINGS on this server (verified),
  // so fetch each client via client_get for its customer_no.
  // client_get_by_customer_no signals "not found" as a remote_fault
  // ("There is no user account for this customer number.") — that fault means
  // the code is FREE, not that the method is unavailable.
  // Directive: 6 chars lower-case alphanumeric, FIRST CHAR MUST BE A LETTER.
  const pool = "abcdefghijklmnopqrstuvwxyz0123456789";
  const alpha = "abcdefghijklmnopqrstuvwxyz";
  const gen = () => alpha[crypto.randomBytes(1)[0] % alpha.length] +
    Array.from(crypto.randomBytes(5)).map(b => pool[b % pool.length]).join("");
  const taken = new Set();
  let listOk = true, lookupOk = false;
  try {
    const ids = await c.call("client_get_all", {});
    for (const row of ids || []) {
      const cid = typeof row === "object" && row !== null ? row.client_id : row;
      try {
        const full = await c.call("client_get", { client_id: cid });
        if (full && full.customer_no) taken.add(String(full.customer_no).toLowerCase());
      } catch (e) { /* skip unreadable client */ }
    }
  } catch (e) { listOk = false; }
  let code = gen(), tries = 0;
  while (tries < 50) {
    if (taken.has(code)) { code = gen(); tries++; continue; }
    try {
      await c.call("client_get_by_customer_no", { customer_no: code });
      code = gen(); tries++;  // no fault thrown => account exists => collision
    } catch (e) {
      if (/no user account/i.test((e && e.message) || "")) lookupOk = true; // code free
      break;  // free (or method unusable) -> accept this draw
    }
  }
  out.customer_no = code;
  out.__dedup_list = listOk ? "1" : "0";
  out.__dedup_lookup = lookupOk ? "1" : "0";
  out.__existing = Array.from(taken).join(",");
  console.log(JSON.stringify(out));
  process.exit(0);
}
main().catch(e => { console.error(e.message); process.exit(1); });
"""
    proc = subprocess.run(
        ["node", "-e", runner],
        env={**os.environ,
             "CONFIG_JSON": json.dumps(config),
             "DIST_PATH": DIST,
             "TPL_NAME": DEFAULT_TEMPLATE_NAME,
             "TPL_FIELDS": json.dumps(TEMPLATE_LIMIT_FIELDS + TEMPLATE_MANDATORY_FIELDS)},
        capture_output=True, text=True, timeout=90,
    )
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout.strip() or "{}")
    except (json.JSONDecodeError, ValueError):
        return {}


def apply_client_defaults(params: dict, config: dict) -> tuple:
    """Fill names, email, country, language, customer_no, password, template limits.

    Returns (params, generated_password); generated_password is None when the
    caller supplied an explicit password.
    """
    import re as _re
    name = (params.get("username") or params.get("contact_name")
            or params.get("company_name") or "client")
    local = _re.sub(r"[^a-z0-9._-]", "", str(name).lower()) or "client"
    params.setdefault("contact_name", str(name))          # tform-mandatory
    params.setdefault("company_name", str(name))
    params.setdefault("email", f"{local}@{DEFAULT_EMAIL_DOMAIN}")
    params.setdefault("country", DEFAULT_COUNTRY)
    params.setdefault("language", DEFAULT_LANGUAGE)       # tform-mandatory
    gen_pw = None
    if "password" not in params:  # explicit password always wins
        gen_pw = gen_password()
        params["password"] = gen_pw
    bundle = fetch_client_defaults_bundle(config)
    for k, v in bundle.items():
        if not k.startswith("__"):
            params.setdefault(k, v)
    if "customer_no" not in params:  # bundle fetch failed -> unchecked random
        # Directive: first char must be a letter
        params["customer_no"] = (
            secrets.choice("".join(c for c in CUSTOMER_NO_POOL if c.isalpha()))
            + "".join(secrets.choice(CUSTOMER_NO_POOL)
                      for _ in range(CUSTOMER_NO_LEN - 1))
        )
    return params, gen_pw


# --- Per-client inventory (bridge extra) --------------------------------------

INVENTORY_RUNNER = r"""
const path = require("path");
const { ISPConfigClient } = require(path.join(process.env.DIST_PATH, "client.js"));
function fail(code, msg) { console.error(JSON.stringify({ error: code, message: msg })); process.exit(1); }
async function main() {
  const c = new ISPConfigClient(JSON.parse(process.env.CONFIG_JSON));
  try { await c.login(); } catch (e) { fail("auth_error", "login failed: " + e.message); }
  const sid = Number(process.env.SERVER_ID);
  const target = Number(process.env.CLIENT_ID);
  const out = { tool: "isp_client_inventory", client_id: target, server_id: sid,
                client: null, groups: {}, services: {}, errors: {}, notes: [] };

  // 0. target must exist (clean error, never a tform validation wall)
  let cli;
  try { cli = await c.call("client_get", { client_id: target }); }
  catch (e) { fail("client_lookup_error", e.message); }
  if (!cli || !cli.username)
    fail("client_not_found", "client_id " + target + " does not exist");
  out.client = { username: cli.username, contact_name: cli.contact_name,
                 customer_no: cli.customer_no,
                 record_sys_groupid: cli.sys_groupid,
                 _note: "client.sys_groupid is UNRELIABLE (API-created clients can claim the admin group); ownership below is resolved via client_get_by_groupid" };

  // 1. server-wide sweep, ONE login, every service class; *_get with primary_id
  //    as OBJECT of column filters = WHERE clause (verified pattern). Some
  //    classes return false (not []) when empty — normalize.
  async function sweep(label, method, filter, pick) {
    try {
      const r = await c.call(method, { primary_id: filter });
      const rows = Array.isArray(r) ? r : (r && typeof r === "object" ? [r] : []);
      out.services[label] = { method, filter, server_total: rows.length, rows: rows.map(pick) };
    } catch (e) { out.errors[label] = { method, error: String(e.message).slice(0, 160) }; }
  }
  const OWN = r => ({ gid: r.sys_groupid, uid: r.sys_userid, active: r.active,
                      cid: r.client_id === undefined ? null : String(r.client_id) });
  const F = { server_id: sid };
  await sweep("web_domains", "sites_web_domain_get", F,
    r => ({ id: r.domain_id, domain: r.domain, ...OWN(r) }));
  await sweep("web_subdomains", "sites_web_subdomain_get", F,
    r => ({ id: r.subdomain_id, domain: r.domain, ...OWN(r) }));
  await sweep("web_aliasdomains", "sites_web_aliasdomain_get", F,
    r => ({ id: r.aliasdomain_id, domain: r.domain, ...OWN(r) }));
  await sweep("vhost_subdomains", "sites_web_vhost_subdomain_get", F,
    r => ({ id: r.subdomain_id, domain: r.domain, ...OWN(r) }));
  await sweep("databases", "sites_database_get", F,
    r => ({ id: r.database_id, name: r.database_name, ...OWN(r) }));
  await sweep("ftp_users", "sites_ftp_user_get", F,
    r => ({ id: r.ftp_user_id, username: r.username, ...OWN(r) }));
  await sweep("shell_users", "sites_shell_user_get", F,
    r => ({ id: r.shell_user_id, username: r.username, ...OWN(r) }));
  await sweep("webdav_users", "sites_webdav_user_get", F,
    r => ({ id: r.webdav_user_id, username: r.username, dir: r.dir, ...OWN(r) }));
  await sweep("mail_domains", "mail_domain_get", F,
    r => ({ id: r.maildomain_id, domain: r.domain, ...OWN(r) }));
  await sweep("mailboxes", "mail_user_get", F,
    r => ({ id: r.mailuser_id, email: r.email, ...OWN(r) }));
  await sweep("mail_aliases", "mail_alias_get", F,
    r => ({ id: r.mail_alias_id, source: r.source, destination: r.destination, ...OWN(r) }));
  await sweep("mail_forwards", "mail_forward_get", F,
    r => ({ id: r.forward_id, source: r.source, destination: r.destination, ...OWN(r) }));
  await sweep("mail_catchalls", "mail_catchall_get", F,
    r => ({ id: r.catchall_id, domain: r.domain, destination: r.destination, ...OWN(r) }));
  await sweep("mail_mailinglists", "mail_mailinglist_get", F,
    r => ({ id: r.mailinglist_id, email: r.email, ...OWN(r) }));
  await sweep("mail_fetchmail", "mail_fetchmail_get", F,
    r => ({ id: r.fetchmail_id, source: r.mailsource, destination: r.destination, ...OWN(r) }));
  await sweep("mail_spamfilter_users", "mail_spamfilter_user_get", F,
    r => ({ id: r.spamfilter_user_id, email: r.email, ...OWN(r) }));
  // wblist: there is no mail_wblist_get on this server; the registered
  // read methods are mail_whitelist_get / mail_blacklist_get (registry-
  // verified). Neither table carries server_id -> empty filter.
  await sweep("mail_whitelist", "mail_whitelist_get", {},
    r => ({ id: r.whitelist_id ?? r.id, email: r.email ?? r.pattern, ...OWN(r) }));
  await sweep("mail_blacklist", "mail_blacklist_get", {},
    r => ({ id: r.blacklist_id ?? r.id, email: r.email ?? r.pattern, ...OWN(r) }));
  await sweep("domains_module", "domains_domain_get", {},
    r => ({ id: r.domain_id, domain: r.domain, ...OWN(r) }));
  await sweep("dns_zones", "dns_zone_get", F,
    r => ({ id: r.id, zone: r.origin, ...OWN(r) }));
  // crons: primary_id filter is REJECTED by sites_cron_get; cron_id is the
  // reflection-suggested key (documented untested — tested here for the first time)
  try {
    const r = await c.call("sites_cron_get", { cron_id: F });
    const rows = Array.isArray(r) ? r : (r && typeof r === "object" ? [r] : []);
    out.services.cron_jobs = { method: "sites_cron_get", filter: "cron_id", server_total: rows.length,
      rows: rows.map(r => ({ id: r.cron_id, cmd: String(r.command || "").slice(0, 60), ...OWN(r) })) };
    out.notes.push("cron enumeration: cron_id object-filter WORKED (first verified use)");
  } catch (e) {
    out.errors.cron_jobs = { method: "sites_cron_get (cron_id filter)", error: String(e.message).slice(0, 160) };
    out.notes.push("cron enumeration failed with the cron_id object filter; crons not enumerable on this server");
  }

  // 2. group -> owning-username map. client_get_by_groupid is BROKEN on this
  //    server (remote_fault "There is no client for this group ID" even for a
  //    group that definitely belongs to a client — verified live 2026-11-19),
  //    so resolve in the WORKING direction instead: per client,
  //    client_get_groupid(client_id) -> its sys_groupid (verified live).
  //    Groups with no client (admin gid 1) are simply absent from the map.
  const ids = await c.call("client_get_all", {});
  for (const row of ids || []) {
    const cid = typeof row === "object" && row !== null ? row.client_id : row;
    try {
      const full = await c.call("client_get", { client_id: Number(cid) });
      let gid = null;
      try { gid = await c.call("client_get_groupid", { client_id: Number(cid) }); } catch (e) {}
      if (gid !== null && gid !== undefined) out.groups[String(gid)] = full && full.username ? full.username : null;
    } catch (e) { /* skip unreadable client */ }
  }

  // 3. attribute: direct client_id column match OR resolved group -> username
  const mine = gid => out.groups[String(gid)] === cli.username;
  const summary = {};
  for (const k of Object.keys(out.services)) {
    const rows = out.services[k].rows
      .filter(r => r.cid === String(target) || mine(r.gid));
    out.services[k].client_rows = rows;
    summary[k] = rows.length;
  }
  out.summary = summary;

  // 4. DNS records inside client-owned zones (zones are parent objects);
  //    dns_record_get does NOT exist — the registered method is
  //    dns_rr_get_all_by_zone(zone_id) (verified against the live registry)
  out.dns_records = [];
  for (const z of (out.services.dns_zones && out.services.dns_zones.client_rows) || []) {
    try {
      const rr = await c.call("dns_rr_get_all_by_zone", { zone_id: Number(z.id) });
      const rows = Array.isArray(rr) ? rr : (rr && typeof rr === "object" ? [rr] : []);
      out.dns_records.push({ zone: z.zone, zone_id: z.id, count: rows.length,
        records: rows.map(r => ({ id: r.id, name: r.name, type: r.type, data: String(r.data || "").slice(0, 40) })) });
    } catch (e) {
      out.dns_records.push({ zone: z.zone, zone_id: z.id, error: String(e.message).slice(0, 120) });
    }
  }

  console.log(JSON.stringify(out, null, 2));
}
main().catch(e => fail("error", e.message));
"""


def run_client_inventory(config: dict, client_id: int) -> int:
    """Bridge-extra: per-client service inventory. ONE login, sweeps every
    service class server-side, attributes rows client-side (direct client_id
    column match, or group -> username resolution via client_get_by_groupid —
    client.sys_groupid is unreliable and default_group is not exposed)."""
    proc = subprocess.run(
        ["node", "-e", INVENTORY_RUNNER],
        env={**os.environ,
             "CONFIG_JSON": json.dumps(config),
             "DIST_PATH": DIST,
             "SERVER_ID": str(config["serverId"]),
             "CLIENT_ID": str(client_id)},
        capture_output=True, text=True, timeout=240,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        print(proc.stderr.rstrip() or json.dumps({"error": "node_exit", "code": proc.returncode}),
              file=sys.stderr)
    return proc.returncode


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
    elif args[0] == "isp_client_inventory":
        # Bridge extra: not an upstream tool — its own runner, ONE login for the
        # whole sweep. client_id required (ask-don't-guess: no default).
        inv_args = args[1:]
        if not inv_args or not inv_args[0].startswith("client_id="):
            print(json.dumps({"error": "missing_param",
                              "expected": "isp_client_inventory client_id=N",
                              "note": "no default client_id is guessed; pass the id explicitly"}), file=sys.stderr)
            sys.exit(2)
        try:
            cid = int(str(inv_args[0].split("=", 1)[1]).strip())
        except ValueError:
            print(json.dumps({"error": "bad_param", "got": inv_args[0],
                              "expected": "client_id=<integer>"}), file=sys.stderr)
            sys.exit(2)
        # config is built later in main(); build it here (identical shape)
        cfg = {
            "apiUrl": env["ISPCONFIG_API_URL"],
            "username": env["ISPCONFIG_USER"],
            "password": env["ISPCONFIG_PASS"],
            "serverId": int(env.get("ISPCONFIG_SERVER_ID", "1") or 1),
            "readOnly": env.get("ISPCONFIG_READ_ONLY", "false").lower() == "true",
            "verifySsl": env.get("ISPCONFIG_VERIFY_SSL", "true").lower() == "true",
        }
        sys.exit(run_client_inventory(cfg, cid))
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

    post_apply_provision = False
    gen_pw = None
    if tool == "isp_client_add":
        params, gen_pw = apply_client_defaults(params, config)
    elif tool == "isp_provision_site":
        name = params.get("clientName") or params.get("domain") or "client"
        params.setdefault("clientEmail", f"{name}@{DEFAULT_EMAIL_DOMAIN}")
        # country, customer_no + template limits can't be injected into provision's
        # internal client_add; applied after success via client_update.
        post_apply_provision = True

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
    else:
        if gen_pw:  # auto-generated client password: printed once, by design
            print(json.dumps({"generated_client_password": gen_pw}), file=sys.stderr)
        if post_apply_provision:
            try:
                result = json.loads(proc.stdout)
                post_apply_provision_defaults(params, config, result)
            except (json.JSONDecodeError, ValueError):
                pass  # non-JSON output: skip defaults, provisioning result already printed
    sys.exit(proc.returncode)


def post_apply_provision_defaults(params: dict, config: dict, result: dict) -> None:
    """After isp_provision_site succeeds: apply country, customer_no, password + limits.

    Provision's internal client_add only passes company/contact/email, so the new
    client would otherwise sit at limit 0 with empty country. Best-effort: failures
    are reported but don't undo the provisioning itself.
    """
    cid = (result.get("created") or {}).get("client_id")
    if not cid:
        return
    updates = {k: v for k, v in fetch_client_defaults_bundle(config).items()
               if not k.startswith("__")}
    if params.get("clientCountry"):
        updates["country"] = params["clientCountry"]
    else:
        updates["country"] = DEFAULT_COUNTRY
    gen_pw = gen_password()
    updates["password"] = gen_pw
    # _update tools need the NESTED params form — flat fields are silently ignored
    # (returns 0, no error; see SKILL.md nested-params gotcha, verified live).
    params_json = json.dumps(updates)
    proc = subprocess.run(
        ["python3", os.path.abspath(__file__), "isp_client_update",
         f"client_id={cid}", f"params={params_json}"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode == 0:
        print(json.dumps({"generated_client_password": gen_pw}), file=sys.stderr)
    else:
        print(json.dumps({"defaults_warning": "provision post-pass client_update failed",
                          "stderr": proc.stderr[:300]}), file=sys.stderr)


if __name__ == "__main__":
    main()
