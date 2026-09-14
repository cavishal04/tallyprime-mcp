from __future__ import annotations

import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.mcp.prompts import register_prompts
from tallyprime_mcp.mcp.resources import register_resources
from tallyprime_mcp.server import build_server
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyConnectionError
from tests.unit.fakes import FakeTallyConnection


@pytest.fixture
def mcp_app(settings: TallySettings) -> tuple[FastMCP, TallyClient]:
    client = TallyClient(settings, connection=FakeTallyConnection())
    app = FastMCP(name="test-resources")
    register_resources(app, client)
    register_prompts(app)
    return app, client


def test_companies_resource(mcp_app: tuple[FastMCP, TallyClient]) -> None:
    app, _client = mcp_app
    resources = asyncio.run(app.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "tally://companies" in uris


def test_config_resource_has_no_secrets(mcp_app: tuple[FastMCP, TallyClient]) -> None:
    app, client = mcp_app
    result = asyncio.run(app.read_resource("tally://config"))
    text = result[0].content
    payload = json.loads(text)
    assert payload["host"] == client.settings.host
    assert "password" not in text.lower()
    assert "secret" not in text.lower()


def test_companies_resource_reports_clean_error_on_failure(settings: TallySettings) -> None:
    client = TallyClient(settings, connection=FakeTallyConnection(fail_with=TallyConnectionError("down")))
    app = FastMCP(name="test-resources-2")
    register_resources(app, client)
    result = asyncio.run(app.read_resource("tally://companies"))
    payload = json.loads(result[0].content)
    assert "down" in payload["error"]


def test_prompts_registered(mcp_app: tuple[FastMCP, TallyClient]) -> None:
    app, _client = mcp_app
    prompts = asyncio.run(app.list_prompts())
    names = {p.name for p in prompts}
    assert {"trial_balance_report", "cash_position_check", "ledger_statement"} <= names


def test_build_server_registers_all_expected_surfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TALLY_HOST", "127.0.0.1")
    monkeypatch.setenv("TALLY_PORT", "9000")
    mcp, client = build_server()
    try:
        tools = asyncio.run(mcp.list_tools())
        resources = asyncio.run(mcp.list_resources())
        prompts = asyncio.run(mcp.list_prompts())
        assert len(tools) == 13
        assert len(resources) == 2
        assert len(prompts) == 3
    finally:
        client.close()
