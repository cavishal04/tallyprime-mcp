# Cursor Setup

1. Make sure `tallyprime-mcp` is installed and working from a terminal
   (`tallyprime-mcp --version`) — see
   [../../docs/installation.md](../../docs/installation.md) if not.

2. In Cursor, open (or create) an MCP configuration file. Cursor supports
   both a **project-level** config (`.cursor/mcp.json` inside your
   project) and a **global** one — check Cursor's own current
   documentation for the exact location, as this has moved between
   versions.

3. Merge the contents of [mcp.json](mcp.json) in this folder into that
   file's `mcpServers` object.

4. If `tallyprime-mcp` isn't on your system PATH, use the full path to the
   executable instead of the bare command name — same as the Claude
   Desktop instructions in [../claude/README.md](../claude/README.md#step-4).

5. Reload/restart Cursor, then check its MCP settings panel to confirm the
   `tallyprime` server shows as connected.

## Troubleshooting

Cursor's Settings → MCP panel typically shows connection status and any
startup error per server — check there first. The most common issue is the
`command` path being wrong or `tallyprime-mcp` not being installed for the
same Python/user environment Cursor is running as.
