# Claude Desktop Setup

1. Make sure `tallyprime-mcp` is installed and `tallyprime-mcp --version`
   works from a terminal (see [../../docs/installation.md](../../docs/installation.md)
   if not).

2. Open Claude Desktop's configuration file:

   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux:** `~/.config/Claude/claude_desktop_config.json`

   (Claude Desktop's own documentation is authoritative on the exact path
   for your version/platform — it has changed before and may again.)

3. Add (or merge) the `tallyprime` entry from
   [claude_desktop_config.json](claude_desktop_config.json) in this folder
   into the `mcpServers` object. If the file doesn't exist yet, you can use
   that file's contents as-is.

4. If `tallyprime-mcp` isn't on your system PATH (e.g. it's installed in a
   virtual environment), replace `"command": "tallyprime-mcp"` with the
   **full path** to the executable, e.g.:

   ```json
   "command": "C:\\Users\\you\\tallyprime-mcp\\.venv\\Scripts\\tallyprime-mcp.exe"
   ```

   or on macOS/Linux:

   ```json
   "command": "/home/you/tallyprime-mcp/.venv/bin/tallyprime-mcp"
   ```

5. **Fully quit and reopen** Claude Desktop (not just close the window).

6. Ask Claude something like "what TallyPrime tools do you have?" to
   confirm it picked up the new server.

## Troubleshooting

Claude Desktop has a "Developer" section in Settings with an option to
view MCP server logs — check there first if the tools don't appear. Common
causes: a JSON syntax error in the config file (missing comma, etc.), or
the `command` path being wrong.
