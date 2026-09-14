# MCP Client Configuration

TallyPrime MCP is a standard MCP server that communicates over **stdio**.
Any MCP-compatible client that can launch a local command should work with
it, though only the clients below have example configs in this repo.

The server does not hard-code any assumptions about which client is
launching it — the same `tallyprime-mcp` command works identically
regardless of client.

## Claude Desktop

See [../examples/claude/README.md](../examples/claude/README.md) and
[../examples/claude/claude_desktop_config.json](../examples/claude/claude_desktop_config.json).

Short version: add an entry under `mcpServers` in Claude Desktop's
configuration file pointing at the `tallyprime-mcp` command, then restart
Claude Desktop.

## Cursor

See [../examples/cursor/README.md](../examples/cursor/README.md) and
[../examples/cursor/mcp.json](../examples/cursor/mcp.json).

Cursor uses a very similar `mcpServers` JSON shape to Claude Desktop, in
a project- or user-level `mcp.json`.

## Any other MCP client

See [../examples/generic/README.md](../examples/generic/README.md).

In general, any MCP client needs to know:

- **Command:** `tallyprime-mcp` (or `python -m tallyprime_mcp.cli` if the
  `tallyprime-mcp` script isn't on the client's PATH).
- **Args:** none required by default.
- **Environment variables:** any `TALLY_*` overrides you want (see
  [configuration.md](configuration.md)) — most MCP client configs let you
  set environment variables per-server.
- **Transport:** stdio.

## Using a virtual environment

If you installed TallyPrime MCP into a virtual environment rather than
system-wide, point the client's "command" at the full path to that
venv's `tallyprime-mcp` executable (e.g.
`C:\path\to\.venv\Scripts\tallyprime-mcp.exe` on Windows, or
`/path/to/.venv/bin/tallyprime-mcp` on Linux/macOS) rather than relying on
PATH.

## Verifying the connection from the client side

After configuring your client and restarting it, ask your AI assistant
something simple like "what TallyPrime tools do you have access to?" or
"list my Tally companies". If it doesn't seem to have the tools available:

1. Confirm `tallyprime-mcp --version` works from the same command line/user
   account your MCP client runs as.
2. Check your client's logs for MCP server startup errors (most clients
   show these somewhere — Claude Desktop has a "View Logs" option in its
   Developer settings).
3. Confirm you fully restarted the client app, not just reloaded a window.
