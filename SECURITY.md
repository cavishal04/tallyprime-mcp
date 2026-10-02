# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's [private vulnerability reporting](https://github.com/cavishal04/tallyprime-mcp/security/advisories/new) feature on this repository, or email the address listed in the repository's GitHub "Security" tab. Include:

- A description of the issue and its potential impact.
- Steps to reproduce (a minimal example is ideal).
- Your TallyPrime MCP version, Python version, and OS.

We aim to acknowledge reports within 5 business days. As a small community project we can't promise a fixed SLA for a patch, but we will keep you updated on progress.

## Threat model

### What this project is

TallyPrime MCP is a local bridge: it runs on the same machine as TallyPrime (or a machine on the same trusted network), accepts MCP protocol calls from an AI client over **stdio**, translates them into TallyPrime's local HTTP-XML protocol, and returns structured data.

### Trust boundaries

```
[AI Client] --(stdio, trusted local process)--> [TallyPrime MCP] --(HTTP, local network)--> [TallyPrime]
```

1. **AI client ↔ TallyPrime MCP**: communicates over stdio as a child process. We trust whatever MCP client the user has configured to launch this server, in the same way any locally-run CLI tool trusts its parent process. We do **not** trust the *content* an AI model chooses to put into tool call parameters — those are validated (see below) as if they came from an untrusted user, because an LLM can be manipulated by data it reads elsewhere into generating adversarial tool calls.
2. **TallyPrime MCP ↔ TallyPrime**: plain HTTP by default, matching TallyPrime's own local gateway, which does not support TLS or authentication out of the box. This is why the default host is `127.0.0.1` and why running this server such that it talks to a TallyPrime instance on a *different* machine is a deliberate, opt-in choice the operator makes by changing `TALLY_HOST` — see "Known limitations" below.

### What this project defends against

| Threat | Mitigation |
|---|---|
| Malicious/malformed tool-call parameters (dates, limits, free-text search) reaching Tally unchecked | All parameters are validated/parsed (e.g. `date.fromisoformat`) before being placed into an XML request. Invalid input raises a clean `ValidationError`, not a raw string interpolated into XML. |
| XML injection via ledger/company/search-term values | Requests are built with `xml.etree.ElementTree`, which escapes special characters (`<`, `&`, `"`, etc.) automatically — see `tests/unit/test_xml_builder.py::test_xml_injection_is_escaped_by_serializer`. |
| XML entity expansion / XML bombs in TallyPrime's response | Responses are parsed with `defusedxml` rather than the standard library's XML parser. |
| Unbounded memory use from a huge or malicious response | `TallyConnection` streams the response and aborts once `TALLY_MAX_RESPONSE_BYTES` is exceeded, rather than buffering unboundedly. |
| Oversized/abusive outgoing requests | `TallyConnection` rejects requests larger than `TALLY_MAX_REQUEST_BYTES` before making any network call. |
| Hung requests (Tally showing a blocking dialog, network issue) | Explicit connect and total timeouts on every request; no request can hang indefinitely. |
| An AI agent trying to modify/delete Tally data | Off by default: with `TALLY_READ_ONLY=true` no write tool is registered. When enabled, only *creating* ledgers and vouchers is possible, always via preview → `confirm_write`; nothing can alter or delete existing data. See "Write operations" below. |
| An AI agent trying to run arbitrary Tally XML/commands | There is no generic "execute this XML" tool. The optional `debug_raw_xml` tool (off by default, see below) can only issue the same fixed, read-only collection queries the normal tools already use — it cannot be given arbitrary XML or an arbitrary request type. |
| Leaking secrets/credentials into logs | The logging pipeline redacts anything matching common secret patterns (`password=`, `token:`, `api_key=`, etc.) before it's written anywhere. In practice this project has no credentials to leak today (see "No authentication" below), but the redaction stays in place defensively for whatever configuration surface comes later. |
| Leaking Python internals/stack traces to the AI client | Every MCP tool is wrapped so that known TallyPrime errors surface their clean, human-readable message, and any *unexpected* exception is logged locally (with full traceback) and reported to the client only as a generic internal-error message. |
| Accidentally sending accounting data to a third party | This project makes exactly one kind of outgoing network call: to the TallyPrime host/port you configured. There is no telemetry, no update-check phone-home, no analytics. |

### Write operations — opt-in, two-step

TallyPrime MCP is **read-only by default**. Writes are available only when the operator sets `TALLY_READ_ONLY=false`:

- With `read_only=true` (default), the write tools are not even registered, and `WritePermission.check()` denies every write.
- With `read_only=false`, `WritePermission.check()` allows only `create_ledger` and `create_voucher`. Alter, delete, cancel, and arbitrary-XML operations do not exist.
- `create_ledger` / `create_voucher` **never write**. They validate the request against the live company (company loaded, referenced ledgers/groups exist, ledger name not already taken, debits equal credits, text length limits), build the exact import XML, and park it in an in-memory store, returning a preview and a `confirmation_id`.
- Only `confirm_write(confirmation_id)` sends anything to Tally, and it sends the stored XML byte-for-byte, so what was previewed is what gets written. Confirmations are single-use, expire after `TALLY_WRITE_CONFIRMATION_TTL_SECONDS` (default 600), and are discarded on restart.
- Writes must target an explicit company (`company` argument or `TALLY_DEFAULT_COMPANY`); they never fall back to whichever company happens to be active in Tally.
- Every proposal, commit, failure, and cancellation is written to the local audit log (`tallyprime_mcp.audit`).
- All user-supplied text is placed into XML via `ElementTree`, which escapes it — narrations or names cannot inject extra XML elements.

**The limit of this design:** the confirmation step is a protocol between the server and the AI client. The server instructs the assistant to call `confirm_write` only after the user approves, and annotates `confirm_write` as a non-read-only tool so MCP clients prompt for it, but the server cannot itself verify that a human approved. Keep your MCP client's per-tool approval enabled for `confirm_write`, and only enable writes for assistants and companies you're comfortable with. Take a Tally backup before first use.

### No authentication between this server and TallyPrime

TallyPrime's local HTTP-XML gateway does not support authentication for local connections in the configurations this project targets. This means:

- **Anything else running on the same machine** that can reach `127.0.0.1:9000` can also talk to TallyPrime's gateway directly, with or without this project installed. This is a property of TallyPrime itself, not something introduced by TallyPrime MCP.
- If you point `TALLY_HOST` at a machine other than `localhost`, **anything on that network segment** that can reach the configured host/port can potentially interact with TallyPrime's gateway too. **We recommend against this** unless you have your own network-level access controls (firewall rules limiting the port to a specific source, a VPN, etc.) — TallyPrime MCP does not add authentication on your behalf.

### Known limitations

- No TLS between this server and TallyPrime (matches TallyPrime's own gateway; there's no encryption to add on top of a protocol that doesn't support it without a separate reverse proxy).
- No per-user access control within TallyPrime MCP itself — if the process can reach Tally, all enabled tools are available to whatever MCP client is talking to this server.
- The optional `debug_raw_xml` tool (disabled by default; enable with `TALLY_EXPOSE_RAW_XML_TOOL=true`) returns *unfiltered* XML for a small fixed set of request kinds, which could include more raw internal field names than the sanitized tool outputs. It's intended for local troubleshooting only — leave it off unless you're actively debugging a field-mapping issue.
- This project cannot audit or control what your MCP *client* does with the data once returned (see the Privacy section of the README).

### Supported versions

Only the latest released minor version receives security fixes while this project is pre-1.0. Once we reach 1.0 we'll adopt a more formal support window and document it here.
