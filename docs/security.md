# Security (operational notes)

This page covers day-to-day operational security guidance. For the full
threat model and vulnerability reporting process, see
[SECURITY.md](../SECURITY.md) at the repository root.

## Recommended deployment

Run `tallyprime-mcp` on the **same machine** as TallyPrime, with
`TALLY_HOST=127.0.0.1` (the default). This keeps all traffic between the
server and TallyPrime on the local loopback interface, which never touches
your network.

## If you must run TallyPrime MCP on a different machine from TallyPrime

This is **not the recommended setup**, but if you have a reason to do it
(e.g. TallyPrime runs on a dedicated accounting workstation and you want to
query it from elsewhere on your LAN):

1. TallyPrime's gateway has no built-in authentication — anything that can
   reach the configured host/port can talk to it. Restrict this at the
   network layer: firewall rules limiting the Tally machine's port to only
   the specific IP running TallyPrime MCP, or a VPN/private network segment.
2. Consider a TLS-terminating reverse proxy in front of TallyPrime's
   gateway if the traffic crosses any network segment you don't fully
   trust, and set `TALLY_SCHEME=https` pointing at the proxy.
3. Understand that TallyPrime MCP itself adds no authentication of its own
   between itself and Tally — it's a transparent bridge for whatever
   trust already exists between the two hosts.

## What to check if you're reviewing this project for use in your organization

- **No write capability exists.** Confirm this yourself: search the
  codebase for tool names starting with `create_`, `update_`, or
  `delete_` — there are none registered in `mcp/tools.py`, and
  `security/permissions.py`'s `WritePermission.check()` always returns
  `allowed=False`.
- **No network calls beyond TallyPrime.** The only outbound HTTP calls in
  this codebase are in `tally/connection.py`, targeting the configured
  `TALLY_HOST:TALLY_PORT`. There's no telemetry, update-checker, or
  analytics code anywhere in this project.
- **No dependency does anything unexpected.** Dependencies are limited to
  `mcp` (the official SDK), `httpx`, `pydantic`/`pydantic-settings`, and
  `defusedxml` — see `pyproject.toml`. No dependency has network access
  beyond what `httpx` is explicitly asked to do.
- **Logging redaction** is defensive, not load-bearing today — there are
  no credentials in this project's current configuration surface to leak.
  It's there so it doesn't have to be added later under time pressure once
  an authenticated Tally deployment or a write-operation credential shows
  up.

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md#reporting-a-vulnerability) — please use
GitHub's private vulnerability reporting rather than a public issue.
