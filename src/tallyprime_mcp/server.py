"""TallyPrime MCP server application.

Builds a :class:`~mcp.server.fastmcp.FastMCP` instance, wires up the shared
:class:`~tallyprime_mcp.tally.client.TallyClient`, registers all read-only
tools/resources/prompts, and runs the server over stdio (the transport
every current MCP desktop client — Claude Desktop, Cursor, etc. — expects
for locally-run servers).
"""

from __future__ import annotations

from tallyprime_mcp import __version__
from tallyprime_mcp.config import TallySettings, load_settings
from tallyprime_mcp.logging_config import configure_logging, get_logger
from tallyprime_mcp.mcp.prompts import register_prompts
from tallyprime_mcp.mcp.resources import register_resources
from tallyprime_mcp.mcp.tools import register_tools
from tallyprime_mcp.tally.client import TallyClient

logger = get_logger("server")

_INSTRUCTIONS = """\
TallyPrime MCP gives you read-only access to a local TallyPrime installation.

- All data comes from TallyPrime running on the user's own computer. Nothing
  is sent to any third-party server operated by this project.
- Every tool here is read-only. There is no tool that can create, modify, or
  delete anything in Tally.
- If a company isn't specified and a default company is configured on the
  server, that default is used; otherwise pass an explicit company name
  (call list_companies first if you don't know it).
- Dates are always ISO format: YYYY-MM-DD.
- If any tool call fails unexpectedly, call test_connection first to check
  whether TallyPrime is reachable at all.
"""


def build_server(settings: TallySettings | None = None) -> tuple["FastMCP", TallyClient]:  # noqa: F821
    """Construct (but do not run) the FastMCP app and its backing TallyClient.

    Split out from :func:`main` so tests can build a server against an
    injected/mocked :class:`TallyClient` without going through stdio.
    """
    from mcp.server.fastmcp import FastMCP

    settings = settings or load_settings()
    configure_logging(level=settings.log_level, log_dir=settings.log_dir, json_lines=settings.log_json)
    logger.info(f"tallyprime-mcp v{__version__} starting up (read_only={settings.read_only})")

    client = TallyClient(settings)

    mcp = FastMCP(
        name="tallyprime-mcp",
        instructions=_INSTRUCTIONS,
    )
    register_tools(mcp, client)
    register_resources(mcp, client)
    register_prompts(mcp)

    logger.info(f"Registered tools; TallyPrime target: {settings.base_url}")
    return mcp, client


def main() -> None:
    mcp, client = build_server()
    try:
        mcp.run()
    finally:
        client.close()
        logger.info("tallyprime-mcp shut down")


if __name__ == "__main__":
    main()
