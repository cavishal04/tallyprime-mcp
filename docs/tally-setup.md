# TallyPrime Setup

TallyPrime MCP needs two things from TallyPrime itself:

1. A **company loaded** (open) in TallyPrime.
2. TallyPrime's **HTTP-XML gateway** switched on and listening on a known
   port (default `9000`).

> **Accuracy note:** the exact menu path for enabling the gateway has moved
> around between TallyPrime releases, and this project's own development
> environment did not have a licensed TallyPrime installation to verify
> against (see README "Testing"). The steps below reflect Tally Solutions'
> generally documented behaviour as of TallyPrime's XML/HTTP integration
> feature; if your version's menus differ, please open an issue (or better,
> a PR to this file) with the corrected path for your version.

## Enabling the gateway

In TallyPrime:

1. Open TallyPrime and load the company you want to query.
2. Go to **F1: Help > Settings > Connectivity** (older/alternate path:
   **Gateway of Tally > F12: Configure > Advanced Configuration**, or the
   **Client/Server configuration** screen depending on your release).
3. Look for a setting named something like:
   - **Enable ODBC** / **TallyPrime Server** — turn this **on**.
   - **Port** — note this number; it must match `TALLY_PORT` (default `9000`).
4. Save/accept the configuration screen.

You do not need to restart TallyPrime for most versions, but if
`tallyprime-mcp test-connection` still fails after enabling the gateway,
try restarting TallyPrime once.

## Verifying it's working from TallyPrime's side

Some TallyPrime versions show a small indicator or log entry when a
client connects to the gateway. If you're not sure the gateway is even
listening, you can check from the same machine using a browser: visiting
`http://127.0.0.1:9000` in a web browser while TallyPrime is running with
the gateway enabled should get *some* response (even an XML error page)
rather than "This site can't be reached" — the latter means the gateway
isn't listening on that port.

## Multiple companies

TallyPrime MCP's `list_companies` tool only sees companies that are
**currently loaded/open** in TallyPrime — it cannot see companies that
exist on disk but haven't been opened. If you work with multiple
companies, open the ones you want the AI assistant to be able to query
before starting a session.

## Firewall

If `tallyprime-mcp` and TallyPrime are running on the same machine (the
recommended, default setup), you generally shouldn't need any firewall
changes — traffic to `127.0.0.1` doesn't leave the machine or cross a
firewall boundary. If you've deliberately configured `TALLY_HOST` to point
at a different machine (see [SECURITY.md](../SECURITY.md) first), you'll
need to allow inbound traffic to the configured port on that machine's
firewall, scoped as narrowly as your network allows.

## Still not connecting?

Run:

```bash
tallyprime-mcp test-connection
```

and check the specific error message:

- **"Connection refused or host unreachable"** — TallyPrime isn't running,
  the gateway isn't enabled, or the port doesn't match.
- **A timeout** — TallyPrime may have a modal dialog open on screen
  (Tally can block on these), or is otherwise busy.
- **"TallyPrime returned HTTP 4xx/5xx"** — the gateway is up but rejected
  the request outright; this usually points to a Tally-side configuration
  issue rather than this project.

If none of that helps, please open an issue with your TallyPrime version
(Help > About in Tally) and the exact error message.
