"""Read-only MCP resources exposed by the TallyPrime MCP server.

Resources are for context an AI client might want to load ambiently (e.g.
"what companies exist") without an explicit tool call. They carry the same
read-only guarantee as the tools in :mod:`tallyprime_mcp.mcp.tools`.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from tallyprime_mcp.services.company_service import CompanyService
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyError


def register_resources(mcp: FastMCP, client: TallyClient) -> None:
    company_service = CompanyService(client)

    @mcp.resource("tally://companies")
    def companies_resource() -> str:
        """Companies currently loaded/available in TallyPrime, as JSON."""
        try:
            companies = company_service.list_companies()
        except TallyError as exc:
            return json.dumps({"error": exc.message})
        return json.dumps([c.model_dump() for c in companies], indent=2)

    @mcp.resource("tally://config")
    def config_resource() -> str:
        """The server's current (non-secret) connection configuration, as JSON.

        No credentials are exposed here because none are currently
        configurable — TallyPrime's local HTTP-XML gateway does not require
        authentication for local connections in the setups this project
        targets. See docs/security.md.
        """
        settings = client.settings
        return json.dumps(
            {
                "host": settings.host,
                "port": settings.port,
                "base_url": settings.base_url,
                "read_only": settings.read_only,
                "default_company": settings.default_company,
                "timeout_seconds": settings.timeout_seconds,
            },
            indent=2,
        )
