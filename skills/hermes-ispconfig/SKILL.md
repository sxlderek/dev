---
name: hermes-ispconfig
description: "Manage ISPConfig servers via Remote JSON API: sites, DNS, mail, databases, SSL, cron, backups, one-command site provisioning."
---

# hermes-ispconfig

Vendored fork of https://github.com/elvatis/openclaw-ispconfig v2026.8.1 (MIT —
LICENSE included). TypeScript sources (`src/`) live in this skill, so rebuilds
never touch the upstream repo. Runs as a CLI bridge skill: the compiled toolset
(`dist/`, zero npm runtime deps) is driven by `scripts/isp.py`.

## When to use

Anything on an ISPConfig server via its Remote API: list clients/sites/DNS/mail/DBs,
check SSL/quota/backups, create or delete records, provision a complete site in one
command.

## Usage

```bash
SKILL=<SKILL_DIR>   # this skill's directory
python3 $SKILL/scripts/isp.py --list                # all 292 tool names
python3 $SKILL/scripts/isp.py <tool> [key=value ...]
python3 $SKILL/scripts/isp.py isp_client_inventory client_id=N   # bridge extra
```

- Param values parse as JSON when possible (numbers, `true`/`false`, `{...}`, `[...]`),
  otherwise stay raw strings. Examples:
  - `isp.py isp_site_get primary_id=1`
  - `isp.py isp_dns_record_add zone_id=5 type=A name=www data=1.2.3.4`
  - `isp.py isp_provision_site domain=example.com clientName="John Doe" clientEmail=<EMAIL>`
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
- `dist/index.js` requires `../openclaw.plugin.json` — keep the manifest
  filename; it must sit next to `dist/` in the skill dir.

## Client-creation defaults (standing user directive)

`isp_client_add` and `isp_provision_site` fill automatically unless overridden:

- **contact_name** → the client name (tform-mandatory: `contact_error_empty` without it)
- **company_name** → the client name
- **email** → `<client-name>@example.com` (sanitized local part; explicit `email` wins)
- **country** → `HK` (explicit `country` / `clientCountry` wins)
- **customer_no** → random 6-char **lowercase**-alphanumeric code whose **first
  character must be a letter**, deduped against existing
  clients before use. Server quirks (both verified live): `client_get_all` returns
  BARE ID STRINGS (no customer_nos) → snapshot fetches each client via `client_get`;
  `client_get_by_customer_no` signals "code free" by throwing remote_fault
  `There is no user account for this customer number.` → treat that fault as
  not-found, not as method-unavailable. Up to 50 tries, crypto-random in node.
  If both dedup channels fail the bridge still creates the client with an unchecked
  random code and prints a `defaults_warning` to stderr — re-check uniqueness manually
  then. Explicit `customer_no` wins, no dedup run in that case.
- **password** → auto-generated 16-char **alphanumeric, first character must be a
  letter**,
  printed ONCE to stderr as `{"generated_client_password": "..."}` on successful
  creation. Format context: ISPConfig's validator
  (`interface/lib/classes/validate_password.inc.php`) gives lowercase chars ZERO
  strength points and caps <3-character-class passwords at strength 3 ("Good")
  regardless of length — most servers require min length 10 + strength 4 ("Strong").
  The mixed-case alphanumeric pool naturally satisfies this (3 varieties,
  lowercase body = 2 points at 16 chars → strength 5). Explicit `password` wins;
  strength still enforced server-side on explicit values too.
- **language** → `en` (tform-mandatory: `language_error_empty` without it)
- **web_php_options** → `no,php-fpm` and **ssh_chroot** → `jailkit`, from the Default
  template (tform-mandatory on many servers: `web_php_options_notempty` /
  `ssh_chroot_notempty` without them)
- **limits + template_master** → merged live from the panel's **"Default" client template**
  (`client_templates_get_all`, 26 whitelisted limit fields). The remote API **ignores
  `template_id` on client_add** (verified empirically: client came back
  `template_master=0`, all limits 0) — the panel UI applies templates, the API does
  not, so the bridge copies the fields itself.
- `isp_provision_site` can't inject fields into its internal client_add → after a
  successful provisioning the bridge applies country, customer_no, template limits
  AND a generated password via a nested-params `client_update` (best-effort,
  `created.client_id` from the result); the generated password is printed once to
  stderr on success, a `defaults_warning` if that update fails.
- Template fetch + customer_no dedup run in **one node pass** (one extra login per
  client_add, preflight-guarded). If it fails: names/email/country/language/password
  (static + generated) still apply, but template limits, web_php_options and
  ssh_chroot are MISSING — on servers where tform REJECTS the create
  (`web_php_options_notempty` / `ssh_chroot_notempty`), pass
  `web_php_options='["php-fpm"]' ssh_chroot=jailkit` explicitly to create anyway.
- Passing the FULL template field set verbatim trips `err_invalid_option` x3
  (non-writable template bookkeeping fields) — that's why the whitelist exists.

## Ask-don't-guess on writes (standing directive)

On ANY add / change / delete operation (`*_add`, `*_update`, `*_delete`,
`isp_provision_site`): if the user did not specify a MANDATORY field and no standing
default covers it (the Client-creation defaults above are explicit user directives —
they count as specified), STOP and ask the user for the missing values. Never invent
values (emails, quotas, IPs, passwords, domains, ids) to fill mandatory gaps.

- Identifiers count as mandatory: ambiguous target (no id given, or a name/domain
  matching several records) → ask which record before writing or deleting. Deletes
  additionally need explicit confirmation per Safety.
- A tform rejection wall (`*_error_empty` / `*_notempty`) IS the server's list of
  missing mandatory fields — report the listed fields and ask for values; do not
  silently retry with guessed ones.
- Examples: "create client acme-web" → OK, proceed (username given, standing defaults
  cover the rest). "create a site foo.com" → ASK which client_id and quotas unless
  stated. `isp_provision_site domain=foo.com` → ASK for clientName (mandatory for
  provisioning, no default exists for it).

## Tool families (292 total — `isp.py --list`)

- **Inventory (bridge extra)**: `isp_client_inventory client_id=N` — ONE login,
  sweeps every service class server-side, attributes rows to the client (direct
  `client_id` column match, or group→username via the WORKING
  `client_get_groupid`). Reports per-class server totals, attributed rows,
  group map, DNS records inside client-owned zones, and per-class errors
  (classes degrade individually, never abort the sweep). Also works as a safe
  existence probe (`client_not_found` for nonexistent ids) and as a pre-delete
  dependency check — a zero-count summary proves nothing cascades.
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

## Nested-params gotcha (all `*_update` tools)

Upstream `_update` tools forward args verbatim to the API signature
`(session, <id-arg>, params)` — updates need a **nested `params` JSON object**,
not flat fields. Flat fields are silently ignored (returns `0`, no error).

```
# WRONG (no-op, exit 0):   isp_client_update client_id=5 country=HK
# RIGHT:                   isp_client_update client_id=5 'params={"country":"HK"}'
#                          isp_site_update primary_id=139 'params={"active":"y"}'
#                          isp_cron_update primary_id=2  'params={"active":"n"}'
```

The id arg (`client_id`/`primary_id`) stays top-level; everything changing goes
inside `params={...}` (JSON, may contain spaces if single-quoted). `*_add` tools
wrap flat fields into `params` internally — only `*_update` needs the nested form.
Verified live: flat form returns `0` and changes nothing; nested form returns
`1` and the record changes.

**Updating a NONEXISTENT id** does NOT return a clean "not found" — it merges the
patch onto an empty record and fails tform validation with a wall of
`*_error_empty` / `usertheme_snytax_incorrect` errors. That wall on a plain
single-field update means the target record is gone; run `client_get_all` to
confirm before assuming a bug.

## Client passwords (readback trap)

- `client_get` and every other API read **never** expose password fields (hashes are
  hidden server-side) — an `*_update` that returns `1` with an empty readback is NOT
  evidence of failure. The only honest verification is a real panel login as that
  client. Exact procedure (verified live): GET `/login/` once to establish a
  session, then POST to `https://panel.example.com:8080/login/` with form fields
  `username`, `password`, `s_mod=login`, `s_pg=index` — NOT `username_s`/`password_s`
  or a guessed csrf field; wrong field names silently re-render the login page with
  status 200 and masquerade as a failed login. Success = **302** (Location
  `../index.php`): treat the 302 itself as the verdict and do not follow it — the
  Location is relative and naive string concatenation onto the base URL produces a
  malformed host; if you must follow, `urljoin`. Failure re-renders the login page
  with 200. One attempt, then GET `/logout.php`.
- Verification recipe for any client-creation change: probe create →
  `isp_client_get` readback → panel login with the generated password → delete the
  probe. The login is the only password proof; the readback proves everything else.
- The bridge auto-generates client passwords (see defaults above). A bare
  `isp_client_add username=X` creates a fully-provisioned client including password.
  Password strength is enforced by the API even on remote calls — pure lowercase
  alphanumeric is rejected with a "strength of Strong" error; see the scoring math
  in the defaults section.

## Safety

- Write tools change live hosting config. Confirm with the user before **destructive**
  calls (`*_delete`, `isp_client_delete_everything`, `isp_site_delete`, DNS zone deletion).
- **Ask-don't-guess on writes** (standing directive): unspecified mandatory fields on
  any add/change/delete → ask the user instead of guessing; see that section above.
- `ISPCONFIG_READ_ONLY=true` in `.env` blocks every write tool (vendored guard).
  The vendored toolset also supports an `allowedOperations` whitelist; not wired
  through this bridge.
- Keep `ISPCONFIG_VERIFY_SSL=true` unless the panel cert is self-signed and you accept
  the MITM risk.
- The bridge has a **login preflight** (one attempt, abort on auth failure) — never call
  `isp_methods_list` on a box whose creds aren't verified yet: the vendored
  toolset's probe mode retries a fresh login per known method and WILL trip the
  server's brute-force guard
  (10 failures / rolling 5-min window → `login_failure_limit`).

## Rebuild (self-contained — vendored sources)

```bash
cd <SKILL_DIR>
npm install --no-audit --no-fund   # devDeps only (typescript, vitest); runtime has zero deps
npm run build                      # tsc → dist/
```

Upstream updates are opt-in (the fork is unlinked): to absorb a change
deliberately, diff a fresh upstream clone against the vendored `src/`, port the
wanted hunks, rebuild. MIT attribution stays either way (LICENSE kept).

## Known wrapper bugs in the vendored toolset + raw-API workaround

`isp_client_list` and `isp_sites_list` in `dist/tools.js` are broken against some
ISPConfig servers:

- `isp_sites_list` with no params calls `fetchSites()` → `sites_web_domain_get` with
  **no primary_id** → API error "The ID must be either an integer or an array." Always
  pass a filter instead: `isp.py isp_sites_list 'primary_id={"server_id":1}'`.
- `isp_client_list` calls `client_get_all` (returns **only client_id strings** on
  some servers: `["1"]`), then `client_get {client_id}` per row — that part works, but its
  toNumber() guard silently drops rows on parse hiccups; totals may lie.
- `isp_client_get` requires `client_id=<n>`; passing `primary_id=` is rejected by
  the wrapper's own validation with a clean self-explanatory error before any API
  call. (Raw `client_get` is likewise client_id-keyed on some servers.)
- Reliable pattern (one login, raw calls): load `dist/client.js`,
  `new ISPConfigClient(cfg)`, `await c.login()` once, then
  `c.call("client_get_all", {})`, `c.call("sites_web_domain_get", {primary_id:{server_id:1}})`,
  `c.call("client_get", {client_id:N})` (the `primary_id` spelling FAILS for client_get;
  `client_id` works).
- `sites_web_domain_get` rows carry 90 fields; useful ones: domain_id, domain, active,
  subdomain, type, ip_address, document_root, system_user/system_group, hd_quota,
  traffic_quota, php, ssl, redirect_type.

### Global enumeration recipe (verified live)

There are NO server-side `*_get_all` methods for services on a typical ISPConfig
install (all rejected
`invalid_method` — only `client_get_all`, `client_templates_get_all`,
`dns_templatezone_get_all`, `server_get_all` exist), and the wrapper's per-client
listers are broken (`client_get_sites_by_user`, `sites_database_get_all_by_user`,
`mail_user_get_all_by_client` all return `[]` even for a client with 11 sites).
The reliable way to list EVERYTHING is singular `*_get` with `primary_id` as an
**OBJECT of column filters** — it becomes a WHERE clause:

```
c.call("sites_web_domain_get", { primary_id: { server_id: 1 } })   // ALL sites on server 1
c.call("mail_domain_get",     { primary_id: { sys_groupid: "16" } }) // ALL records of one client group
```

Traps (all verified live):
- `primary_id` as an ARRAY of id values does NOT work as a filter — every class
  silently returns 0 rows (it is not an id-list).
- Object keys are DB column names, values may be strings (`"16"` works).
- `sites_cron_get` rejects `primary_id` even as an integer array
  ("The ID must be either an integer or an array") — its filter key is
  **`cron_id`, and `{cron_id:{server_id:N}}` WORKS**.
- `client_get_by_groupid` is BROKEN server-side: remote_fault
  "There is no client for this group ID" even for a group that definitely
  belongs to a client. The reverse direction WORKS:
  `client_get_groupid {client_id:N}` → its sys_groupid. Resolve group
  ownership client→group, never group→client.
- DNS records: there is NO `dns_record_get` — the registered read method is
  **`dns_rr_get_all_by_zone {zone_id:N}`** (works, verified).
- Mail wblist: NO `mail_wblist_get`; registered reads are
  `mail_whitelist_get` / `mail_blacklist_get` (neither table has server_id →
  empty filter `{}`).
- **Ownership attribution**: `client_get.sys_groupid` is MISLEADING for API-created
  clients — a client can claim sys_groupid 1 (the admin group), yet its records
  live in a NEW auto-created group (e.g. sys_groupid 16). Attribute services
  by filtering each class on the client's RECORD group (found via one
  `{server_id: 1}` sweep + unique gid), never by client.sys_groupid.

## Verification status (as published)

- Reads verified end-to-end against a live ISPConfig 3.3dev server: auth, client/site
  listing, `isp_system_info` (full server config), 292 tools all load, per-client
  inventory sweep.
- **Writes verified live**: `isp_client_add` (full defaults incl. generated password,
  deduped customer_no — probe round-trip incl. panel login + delete),
  `isp_client_update` (nested `params`), `isp_client_get`, `isp_client_delete`.
- Raw `client_add` without the bridge needs these
  tform-mandatory fields beyond the wrapper's 3 (`company_name`, `contact_name`,
  `email`), else `language_error_empty / web_php_options_notempty / ssh_chroot_notempty`:
  `username`, `password`, `language=en`, `web_php_options=["php-fpm"]` (pass as JSON
  array string), `ssh_chroot`. The bridge auto-fills these plus Default-template
  limits (see Client-creation defaults); without it, new clients land at limit 0.
