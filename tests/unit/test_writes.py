from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from xml.etree.ElementTree import fromstring

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.mcp.tools import register_tools
from tallyprime_mcp.security.confirmation import ConfirmationStore, PendingConfirmation
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyRequestError, TallyXMLParseError, ValidationError
from tallyprime_mcp.tally.xml_builder import (
    LedgerEntryLine,
    build_import_request,
    build_ledger_element,
    build_voucher_element,
)
from tallyprime_mcp.tally.xml_parser import parse_import_result, parse_xml
from tests.conftest import load_fixture
from tests.unit.fakes import FakeTallyConnection

COMPANY = "Acme Traders Pvt Ltd"
WRITE_TOOLS = {"create_ledger", "create_voucher", "confirm_write", "cancel_write"}
RENT = [
    {"ledger": "Office Rent", "side": "debit", "amount": 5000},
    {"ledger": "HDFC Bank", "side": "credit", "amount": 5000},
]


def _call(mcp: FastMCP, tool: str, /, **arguments: object) -> object:
    _content, structured = asyncio.run(mcp.call_tool(tool, arguments))
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return structured["result"]
    return structured


def _tool_names(mcp: FastMCP) -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}


@pytest.fixture
def fake() -> FakeTallyConnection:
    return FakeTallyConnection()


@pytest.fixture
def write_app(settings: TallySettings, fake: FakeTallyConnection) -> FastMCP:
    writable = settings.model_copy(update={"read_only": False, "default_company": COMPANY})
    app = FastMCP(name="test-writes")
    register_tools(app, TallyClient(writable, connection=fake))
    return app


# -- registration --------------------------------------------------------------


def test_write_tools_absent_in_read_only_mode(settings: TallySettings) -> None:
    app = FastMCP(name="ro")
    register_tools(app, TallyClient(settings, connection=FakeTallyConnection()))
    assert not WRITE_TOOLS & _tool_names(app)


def test_write_tools_present_when_enabled(write_app: FastMCP) -> None:
    assert _tool_names(write_app) >= WRITE_TOOLS


def test_confirm_write_is_not_annotated_read_only(write_app: FastMCP) -> None:
    tools = {t.name: t for t in asyncio.run(write_app.list_tools())}
    assert tools["confirm_write"].annotations.readOnlyHint is False
    assert tools["create_voucher"].annotations.readOnlyHint is True


# -- two-step flow -------------------------------------------------------------


def test_create_voucher_previews_without_writing(
    write_app: FastMCP, fake: FakeTallyConnection
) -> None:
    preview = _call(
        write_app, "create_voucher", voucher_type="Payment", date="2026-04-01", entries=RENT
    )
    assert preview["status"] == "pending_confirmation"
    assert preview["company"] == COMPANY
    assert preview["details"]["total"] == 5000.0
    assert fake.import_requests == []


def test_confirm_sends_exactly_the_previewed_voucher(
    write_app: FastMCP, fake: FakeTallyConnection
) -> None:
    preview = _call(
        write_app,
        "create_voucher",
        voucher_type="Payment",
        date="2026-04-01",
        entries=RENT,
        narration="April rent",
    )
    result = _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])
    assert result["status"] == "committed"
    assert result["tally_voucher_id"] == "4521"

    assert len(fake.import_requests) == 1
    root = fromstring(fake.import_requests[0])
    assert root.findtext(".//REPORTNAME") == "Vouchers"
    assert root.findtext(".//SVCURRENTCOMPANY") == COMPANY
    voucher = root.find(".//VOUCHER")
    assert voucher.get("VCHTYPE") == "Payment"
    assert voucher.findtext("DATE") == "20260401"
    assert voucher.findtext("NARRATION") == "April rent"
    lines = {
        line.findtext("LEDGERNAME"): (line.findtext("ISDEEMEDPOSITIVE"), line.findtext("AMOUNT"))
        for line in voucher.findall("ALLLEDGERENTRIES.LIST")
    }
    assert lines == {"Office Rent": ("Yes", "-5000.00"), "HDFC Bank": ("No", "5000.00")}


def test_confirmation_is_single_use(write_app: FastMCP, fake: FakeTallyConnection) -> None:
    preview = _call(
        write_app, "create_voucher", voucher_type="Payment", date="2026-04-01", entries=RENT
    )
    _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])
    with pytest.raises(ToolError, match="No pending write"):
        _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])
    assert len(fake.import_requests) == 1


def test_cancel_discards_pending_write(write_app: FastMCP, fake: FakeTallyConnection) -> None:
    preview = _call(
        write_app, "create_voucher", voucher_type="Payment", date="2026-04-01", entries=RENT
    )
    assert (
        _call(write_app, "cancel_write", confirmation_id=preview["confirmation_id"])["status"]
        == "cancelled"
    )
    with pytest.raises(ToolError):
        _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])
    assert fake.import_requests == []


def test_confirm_surfaces_tally_rejection(write_app: FastMCP, fake: FakeTallyConnection) -> None:
    fake.import_fixture = "import_error_response.xml"
    preview = _call(
        write_app, "create_voucher", voucher_type="Payment", date="2026-04-01", entries=RENT
    )
    with pytest.raises(ToolError, match="rejected"):
        _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])


def test_create_ledger_flow(write_app: FastMCP, fake: FakeTallyConnection) -> None:
    preview = _call(
        write_app,
        "create_ledger",
        name="XYZ Traders",
        parent_group="Sundry Debtors",
        opening_balance=1200.5,
    )
    assert "XYZ Traders" in preview["summary"]
    _call(write_app, "confirm_write", confirmation_id=preview["confirmation_id"])
    ledger = fromstring(fake.import_requests[0]).find(".//LEDGER")
    assert ledger.get("ACTION") == "Create"
    assert ledger.findtext("PARENT") == "Sundry Debtors"
    assert ledger.findtext("OPENINGBALANCE") == "-1200.50"


# -- validation (nothing is proposed, nothing is sent) ---------------------------


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"entries": [RENT[0], {**RENT[1], "amount": 4000}]},
            "does not balance",
        ),
        ({"entries": [RENT[0]]}, "at least two"),
        (
            {"entries": [RENT[0], {**RENT[1], "ledger": "Nonexistent Bank"}]},
            "not found",
        ),
        ({"company": "Some Other Co"}, "not currently loaded"),
        ({"date": "01-04-2026"}, "YYYY-MM-DD"),
        ({"entries": [RENT[0], {**RENT[1], "amount": -5000}]}, "greater than 0"),
    ],
)
def test_invalid_vouchers_rejected(
    write_app: FastMCP, fake: FakeTallyConnection, arguments: dict, message: str
) -> None:
    base = {"voucher_type": "Payment", "date": "2026-04-01", "entries": RENT}
    with pytest.raises(Exception, match=message):
        _call(write_app, "create_voucher", **{**base, **arguments})
    assert fake.import_requests == []


def test_duplicate_ledger_rejected(write_app: FastMCP) -> None:
    with pytest.raises(ToolError, match="already exists"):
        _call(write_app, "create_ledger", name="Cash", parent_group="Cash-in-Hand")


def test_unknown_group_rejected(write_app: FastMCP) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        _call(write_app, "create_ledger", name="New Ledger", parent_group="Made Up Group")


def test_company_required_without_default(settings: TallySettings) -> None:
    app = FastMCP(name="no-default")
    writable = settings.model_copy(update={"read_only": False})
    register_tools(app, TallyClient(writable, connection=FakeTallyConnection()))
    with pytest.raises(ToolError, match="company is required"):
        _call(app, "create_voucher", voucher_type="Payment", date="2026-04-01", entries=RENT)


# -- confirmation store ------------------------------------------------------------


def test_expired_confirmation_cannot_be_used() -> None:
    store = ConfirmationStore(ttl_seconds=1)
    pending = store.add(PendingConfirmation("create_voucher", "s", COMPANY, b"<x/>"))
    pending.expires_at = pending.created_at  # force expiry
    with pytest.raises(ValidationError):
        store.pop(pending.confirmation_id)


# -- XML builder / parser ----------------------------------------------------------


def test_import_request_shape() -> None:
    xml = build_import_request(
        "All Masters", COMPANY, [build_ledger_element("A", "Capital Account")]
    )
    root = fromstring(xml)
    assert root.findtext("HEADER/TALLYREQUEST") == "Import Data"
    assert root.findtext("BODY/IMPORTDATA/REQUESTDESC/REPORTNAME") == "All Masters"
    assert root.find("BODY/IMPORTDATA/REQUESTDATA/TALLYMESSAGE/LEDGER") is not None


def test_voucher_text_is_escaped() -> None:
    voucher = build_voucher_element(
        "Journal",
        date(2026, 4, 1),
        [
            LedgerEntryLine("A & B", Decimal("1"), "debit"),
            LedgerEntryLine("C", Decimal("1"), "credit"),
        ],
        narration="</NARRATION><DELETE/>",
    )
    xml = build_import_request("Vouchers", COMPANY, [voucher])
    root = fromstring(xml)
    assert root.find(".//DELETE") is None
    assert root.findtext(".//NARRATION") == "</NARRATION><DELETE/>"


def test_parse_import_success() -> None:
    result = parse_import_result(parse_xml(load_fixture("import_success_response.xml")))
    assert result.created == 1
    assert result.last_voucher_id == "4521"


def test_parse_import_error() -> None:
    with pytest.raises(TallyRequestError) as exc_info:
        parse_import_result(parse_xml(load_fixture("import_error_response.xml")))
    assert "totals do not match" in exc_info.value.detail


def test_parse_import_nothing_created() -> None:
    with pytest.raises(TallyRequestError, match="did not create"):
        parse_import_result(
            parse_xml(b"<RESPONSE><CREATED>0</CREATED><IGNORED>1</IGNORED></RESPONSE>")
        )


def test_parse_import_unrecognised() -> None:
    with pytest.raises(TallyXMLParseError):
        parse_import_result(parse_xml(b"<ENVELOPE><BODY/></ENVELOPE>"))
