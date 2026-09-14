# Configuration Reference

TallyPrime MCP is configured entirely through environment variables (or a
`.env` file in the current working directory — copy [.env.example](../.env.example)
to `.env` and edit it). There is no separate config file format and nothing
is ever hard-coded in source.

All variables are prefixed `TALLY_`.

## Connection

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_HOST` | string | `127.0.0.1` | Hostname/IP of TallyPrime's HTTP-XML gateway. Keep this at `127.0.0.1` unless you understand the implications in [SECURITY.md](../SECURITY.md). |
| `TALLY_PORT` | integer, 1–65535 | `9000` | TallyPrime's gateway port. |
| `TALLY_SCHEME` | `http` \| `https` | `http` | TallyPrime's own gateway is plain HTTP; only set this to `https` if you've put your own TLS-terminating reverse proxy in front of it. |
| `TALLY_TIMEOUT_SECONDS` | float > 0 | `30` | Total timeout per request to Tally. |
| `TALLY_CONNECT_TIMEOUT_SECONDS` | float > 0 | `5` | TCP connect timeout. |

## Default company

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_DEFAULT_COMPANY` | string | *(unset)* | Used when a tool call doesn't specify `company`. Leave unset to require every call to name a company explicitly. |

## Safety

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_READ_ONLY` | bool | `true` | Always effectively `true` in this release — see [SECURITY.md](../SECURITY.md#write-operations--deliberately-not-implemented). Reserved for future use once write operations exist. |

## Limits (defence in depth)

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_MAX_RESPONSE_BYTES` | int > 0 | `26214400` (25 MiB) | Response streaming aborts past this size. |
| `TALLY_MAX_REQUEST_BYTES` | int > 0 | `1048576` (1 MiB) | Outgoing requests larger than this are rejected before any network call. |
| `TALLY_DEFAULT_VOUCHER_LIMIT` | int, 1–5000 | `100` | Used by `search_vouchers` when the caller doesn't pass `limit`. |

## Logging

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_LOG_LEVEL` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR`\|`CRITICAL` | `INFO` | |
| `TALLY_LOG_DIR` | path | *(unset — stderr only)* | If set, logs also go to a rotating file (`tallyprime-mcp.log`, 5 MiB × 5 backups) in this directory. |
| `TALLY_LOG_JSON` | bool | `false` | Emit structured JSON log lines instead of plain text. |

## Debug

| Variable | Type | Default | Notes |
|---|---|---|---|
| `TALLY_EXPOSE_RAW_XML_TOOL` | bool | `false` | Registers a debug-only `debug_raw_xml` tool. See [SECURITY.md](../SECURITY.md#known-limitations) before enabling. |

## Checking your effective configuration

```bash
tallyprime-mcp config
```

prints the resolved configuration (after environment variables/`.env` are
applied) as JSON. No secrets are ever included in this output, because none
are currently configurable — see [SECURITY.md](../SECURITY.md#no-authentication-between-this-server-and-tallyprime).
