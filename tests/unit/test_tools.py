from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.mcp.tools import register_tools
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyConnectionError
from tests.unit.fakes import FakeTallyConnection


def _call(mcp: FastMCP, name: str, **arguments: object) -> object:
    _content_blocks, structured = asyncio.run(mcp.call_tool(name, arguments))
    # FastMCP wraps list/scalar tool results as {"result": ...}; dict-returning
    # tools come back as the dict itself. Unwrap consistently for assertions.
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return structured["result"]
    return structured


@pytest.fixture
def mcp_app(settings: TallySettings) -> FastMCP:
    client = TallyClient(settings, connection=FakeTallyConnection())
    app = FastMCP(name="test-tallyprime-mcp")
    register_tools(app, client)
    return app


def test_test_connection_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "test_connection")
    assert result["connected"] is True


def test_list_companies_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "list_companies")
    names = {c["name"] for c in result}
    assert "Acme Traders Pvt Ltd" in names


def test_list_ledgers_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "list_ledgers")
    assert len(result) == 8


def test_get_ledger_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_ledger", ledger_name="ABC Limited")
    assert result["ledger"]["name"] == "ABC Limited"


def test_get_ledger_tool_not_found_raises_clean_tool_error(mcp_app: FastMCP) -> None:
    with pytest.raises(ToolError) as exc_info:
        _call(mcp_app, "get_ledger", ledger_name="Nope")
    # The message must be clean/human-readable, not a Python traceback.
    assert "Traceback" not in str(exc_info.value)
    assert "not found" in str(exc_info.value).lower() or "not found" in str(exc_info.value)


def test_search_vouchers_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "search_vouchers", voucher_type="Receipt")
    assert len(result) == 1


def test_invalid_date_raises_clean_validation_error(mcp_app: FastMCP) -> None:
    with pytest.raises(ToolError) as exc_info:
        _call(mcp_app, "search_vouchers", from_date="not-a-date")
    assert "Traceback" not in str(exc_info.value)
    assert "invalid" in str(exc_info.value).lower()


def test_get_trial_balance_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_trial_balance")
    assert result["total_debit"] == result["total_credit"]


def test_get_profit_and_loss_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_profit_and_loss")
    assert result["net_profit"] == result["total_income"] - result["total_expense"]


def test_get_balance_sheet_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_balance_sheet")
    assert "asset_groups" in result
    assert "liability_groups" in result


def test_get_receivables_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_receivables")
    assert result["total_receivable"] == 250000.0


def test_get_payables_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_payables")
    assert result["total_payable"] == 180000.0


def test_list_stock_items_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "list_stock_items")
    assert len(result) == 2


def test_get_stock_summary_tool(mcp_app: FastMCP) -> None:
    result = _call(mcp_app, "get_stock_summary")
    assert result["total_closing_value"] == 120000.0


def test_get_voucher_tool_not_found(mcp_app: FastMCP) -> None:
    with pytest.raises(ToolError):
        _call(mcp_app, "get_voucher", voucher_identifier="NOPE")


def test_connection_error_becomes_clean_tool_error(settings: TallySettings) -> None:
    client = TallyClient(settings, connection=FakeTallyConnection(fail_with=TallyConnectionError("down")))
    app = FastMCP(name="test-tallyprime-mcp-2")
    register_tools(app, client)
    with pytest.raises(ToolError) as exc_info:
        _call(app, "list_companies")
    assert "Traceback" not in str(exc_info.value)
    assert "down" in str(exc_info.value)


def test_raw_xml_debug_tool_not_registered_by_default(mcp_app: FastMCP) -> None:
    tools = asyncio.run(mcp_app.list_tools())
    names = {t.name for t in tools}
    assert "debug_raw_xml" not in names


def test_raw_xml_debug_tool_registered_when_enabled(settings: TallySettings) -> None:
    enabled_settings = settings.model_copy(update={"expose_raw_xml_tool": True})
    client = TallyClient(enabled_settings, connection=FakeTallyConnection())
    app = FastMCP(name="test-tallyprime-mcp-3")
    register_tools(app, client)
    tools = asyncio.run(app.list_tools())
    names = {t.name for t in tools}
    assert "debug_raw_xml" in names


def test_all_tools_are_read_only_no_write_tool_registered(mcp_app: FastMCP) -> None:
    tools = asyncio.run(mcp_app.list_tools())
    names = {t.name for t in tools}
    forbidden_prefixes = ("create_", "update_", "delete_", "modify_", "execute_")
    for name in names:
        for prefix in forbidden_prefixes:
            assert not name.startswith(prefix), f"Unexpected write-shaped tool: {name}"
