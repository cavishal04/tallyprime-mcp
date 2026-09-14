# Generic MCP Client Setup

TallyPrime MCP is a standard MCP server communicating over **stdio** — it
doesn't do anything client-specific. Any MCP client that can launch a local
command and speak the MCP stdio transport should work.

## What your client needs to know

| Setting | Value |
|---|---|
| Transport | stdio |
| Command | `tallyprime-mcp` (or the full path to that executable if it's not on PATH) |
| Arguments | none required |
| Environment variables | Optional `TALLY_*` overrides — see [../../docs/configuration.md](../../docs/configuration.md) |
| Working directory | Not important — configuration comes from environment variables or an explicit `.env` file in whatever directory you choose to launch it from |

## Minimal manual test (no MCP client at all)

You can sanity-check the server manually without any MCP client, using the
low-level MCP stdio protocol, by piping a JSON-RPC `initialize` request into
it:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-test","version":"0"}}}' | tallyprime-mcp
```

You should see a JSON-RPC response describing the server's capabilities.
This is mostly useful for confirming the executable itself starts and
speaks MCP correctly, independent of any particular client's configuration
format.

## Writing your own client config

If your MCP client uses a JSON config format similar to Claude
Desktop/Cursor's `mcpServers` object, the entries in
[../claude/claude_desktop_config.json](../claude/claude_desktop_config.json)
or [../cursor/mcp.json](../cursor/mcp.json) are good starting templates —
the shape (`command`, `args`, `env`) is common across many MCP clients even
when the surrounding file structure differs.
