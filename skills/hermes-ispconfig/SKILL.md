---
name: hermes-ispconfig
description: "Manage ISPConfig servers via Remote JSON API: sites, DNS, mail, databases, SSL, cron, backups, one-command site provisioning."
---

# hermes-ispconfig

Upstream: https://github.com/elvatis/openclaw-ispconfig — an OpenClaw TypeScript plugin
(installed version 2026.8.1, MIT). Here it runs as a CLI bridge skill: the compiled
toolset (`dist/`, zero npm runtime deps) is driven by `scripts/isp.py` from any agent
or shell.

## When to use

Anything on an ISPConfig server via its Remote API: list clients/sites/DNS/mail/DBs,
check SSL/quota/backups, create or delete records, provision a complete site in one
command.

## Usage

```bash
SKILL=<SKILL_DIR>   # this skill's directory
python3 $SKILL/scripts/isp.py --list                # all 292 tool names
python3 $SKILL/scripts/isp.py <tool> [key=value ...]
```

- Param values parse as JSON when possible (numbers, `true`/`false`, `{...}`, `[...]`),
  otherwise stay raw strings. Examples:
  - `isp.py isp_site_get primary_id=1`
  - `isp.py isp_dns_record_add zone_id=5 type=A name=www data=1.2.3.4`
  - `isp.py isp_provision_site domain=example.com clientName="John Doe" clientEmail=john@example.com`
- Copy `.env.example` to `.env` inside the skill directory (chmod 600) and fill in:
  `ISPCONFIG_API_URL`, `ISPCONFIG_USER`, `ISPCONFIG_PASS`, `ISPCONFIG_SERVER_ID`
  (default 1), `ISPCONFIG_VERIFY_SSL` (default true), `ISPCONFIG_READ_ONLY`
  (default false → writes enabled).
- Secrets can come from any secrets store you sync into `.env`. If that store
  **quote-wraps** values (`K="v"`), strip the quotes when syncing or API calls 401
  with the literal quotes in the value.

## ISPConfig API internals

Auth model, `remote_session` whitelist, tform validation, `attempts_login`
brute-force guard, method registry: see
[references/api-internals.md](references/api-internals.md) — read it before
debugging auth or building raw API calls.

## Gotchas (verified against a live ISPConfig 3.3dev JSON API)

- **Endpoint must be the FULL JSON path.** `https://panel.example.com:8080/remote/json.php`,
  never a bare origin. A bare-origin POST hits the panel root, gets a 302 to the web
  UI, and the client reports `parse_error` with an empty body — that symptom means
  wrong URL, not bad TLS/headers.
- **Transport** (verified from ISPConfig source, `interface/lib/classes/json_handler.inc.php`):
  modern JSON API. Method name = first `$_GET` key (`json.php?login`), params = raw JSON
  body, keys reflection-mapped to the PHP method's parameter names. The legacy session
  `login.php` does not exist on newer installs (Apache 404).
- `dist/index.js` requires `../openclaw.plugin.json` — keep the upstream manifest
  filename; it must sit next to `dist/` in the skill dir.

## Tool families (292 total — `isp.py --list`)

- **Read**: `isp_methods_list`, `isp_system_info`, `isp_client_list/_get`,
  `isp_sites_list/_get`, `isp_domains_list`, `isp_dns_zone_list`,
  `isp_dns_record_list(zone_id=…)`, `isp_mail_domain_list`, `isp_mail_user_list`,
  `isp_db_list`, `isp_ssl_status`, `isp_quota_check(client_id=…)`, `isp_backup_list`,
  `isp_cron_list`, plus ~200 more incl. `isp_server_get_version`, `isp_traffic_get`.
- **Write**: `isp_client_add/_update/_delete`, `isp_site_add/_update/_delete`,
  `isp_dns_record_add/_update/_delete` (type=A/AAAA/MX/TXT/CNAME/SRV/CAA/NS/PTR),
  `isp_mail_domain_add`, `isp_mail_user_add/_delete`, `isp_db_add/_delete`,
  `isp_db_user_add`, `isp_shell_user_add`, `isp_ftp_user_add`, `isp_cron_add/_update/_delete`,
  and the full upstream phase-1..6 set (spamfilter, fetchmail, webdav, vhost subdomains…).
- **Provisioning**: `isp_provision_site domain=… clientName=… clientEmail=…`
  [optional: `serverIp`, `createMail` (default true), `createDb` (default true), `serverId`]
  → client + site (SSL + Let's Encrypt) + DNS zone + A/CNAME/SPF/DMARC records +
  `info@`/`admin@` mailboxes + DB user & database.

## Safety

- Write tools change live hosting config. Confirm with the user before **destructive**
  calls (`*_delete`, `isp_client_delete_everything`, `isp_site_delete`, DNS zone deletion).
- `ISPCONFIG_READ_ONLY=true` in `.env` blocks every write tool (upstream guard).
  Upstream also supports an `allowedOperations` whitelist; not wired through this bridge.
- Keep `ISPCONFIG_VERIFY_SSL=true` unless the panel cert is self-signed and you accept
  the MITM risk.
- The bridge has a **login preflight** (one attempt, abort on auth failure) — never call
  `isp_methods_list` on a box whose creds aren't verified yet: upstream probe mode
  retries a fresh login per known method and WILL trip the server's brute-force guard
  (10 failures / rolling 5-min window → `login_failure_limit`).

## Rebuild after upstream updates

```bash
git clone --depth 1 https://github.com/elvatis/openclaw-ispconfig && cd openclaw-ispconfig
npm install && npm run build
cp -r dist openclaw.plugin.json <SKILL_DIR>/
# (keep the upstream filename openclaw.plugin.json — dist/index.js hard-requires it)
```

## Known upstream wrapper bugs (verified 2026-11) + raw-API workaround

`isp_client_list` and `isp_sites_list` in `dist/tools.js` are broken against some
ISPConfig servers:

- `isp_sites_list` with no params calls `fetchSites()` → `sites_web_domain_get` with
  **no primary_id** → API error "The ID must be either an integer or an array." Always
  pass a filter instead: `isp.py isp_sites_list 'primary_id={"server_id":1}'`.
- `isp_client_list` calls `client_get_all` (returns **only client_id strings** on some
  servers: `["1"]`), then `client_get {client_id}` per row — that part works, but its
  toNumber() guard silently drops rows on parse hiccups; totals may lie.
- Reliable pattern (one login, raw calls): load `dist/client.js`,
  `new ISPConfigClient(cfg)`, `await c.login()` once, then
  `c.call("client_get_all", {})`, `c.call("sites_web_domain_get", {primary_id:{server_id:1}})`,
  `c.call("client_get", {client_id:N})` (the `primary_id` spelling FAILS for client_get;
  `client_id` works).
- `sites_web_domain_get` rows carry 90 fields; useful ones: domain_id, domain, active,
  subdomain, type, ip_address, document_root, system_user/system_group, hd_quota,
  traffic_quota, php, ssl, redirect_type.

## Verification status (as published)

- Reads verified end-to-end against a live ISPConfig 3.3dev server: auth, client/site
  listing, `isp_system_info` (full server config), 292 tools all load.
- Write tools never exercised at publish time — treat write outputs as unverified
  until your first successful write.
