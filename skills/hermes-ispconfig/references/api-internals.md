# ISPConfig Remote API internals (from ispconfig/ispconfig3-dev-docs + live probing)

Source: github.com/ispconfig/ispconfig3-dev-docs (beta-3-3-fixes branch docs), read 2026-11-17.

## Architecture: three front-ends, one method registry

- Endpoint directory: `interface/web/remote/` (live server serves `remote/json.php`).
- `ISPConfigRemotingHandlerBase` loads all remoting classes (`remoting_*.inc.php` plus module
  remoting libs) and registers their public methods into one method table.
- Three handlers dispatch from that table:
  - SOAP (`soap_handler`): legacy, dynamic `__call` dispatch.
  - REST (`rest_handler`): HTTP-verb routed, API versioning.
  - JSON (`json_handler`): what this server exposes (`remote/json.php?method` + JSON body).
- Client-visible method names are `{class}_{method}` from the remoting classes, e.g.
  `server_get_all`, `sites_web_domain_get`, `dns_soa_add`, `client_get`. Our bridge's `isp_*`
  tool names are plugin-level aliases mapped onto these real names.
- Every method takes `$session_id` as its first argument (except login).

## Auth and session model

- `login($username, $password)` returns a session id; the session is stored in the
  `remote_session` table with remote_ip, remote_port, tstamp, session_state and — critically —
  `remote_functions`: a per-session whitelist of allowed methods, copied from the remote user's
  configured function checkboxes in the panel (System → Remote Users).
- Consequence: even with valid credentials, calling a method not enabled for the remote user
  fails with a permission error. Check the user's function list before debugging anything else.
- Sessions have an idle timeout (`remoting.session_timeout`). Clients may reuse a session_id
  until expiry instead of re-logging-in per call.
- `logout` invalidates the session.

## Brute-force protection

- Every login attempt is logged to `attempts_login` (ip, username, error, success, login_time).
- Repeated failures from one IP trigger throttling (empirically on this server: ~10 failures
  in a rolling 5 min → lockout). This is why the bridge preflight makes exactly ONE login
  attempt and aborts on failure — never loop logins on auth failure.

## Parameter validation is tform-driven

- `remoting_lib` reuses the panel's tform form definitions to validate API params. So for
  `*_add`/`*_update` methods, the `params` keys must match the record's `.tform.php` field
  names, and validation errors come from the form validators. Field definitions:
  see the tform docs (form-field-settings, validators, datasources) in the dev-docs repo.

## What the dev-docs repo does NOT contain

No wire protocol (endpoints, request encoding), no full method catalog. For those: the source
tree (`interface/lib/classes/remoting*.inc.php`) and the official ISPConfig remote-API docs.
