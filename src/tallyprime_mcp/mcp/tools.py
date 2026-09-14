"""Registers TallyPrime MCP's read-only tools on a FastMCP server instance.

Every tool in this module is read-only: none of them can create, alter, or
delete anything in TallyPrime. There is deliberately no generic
"execute arbitrary Tally XML" tool — see ``docs/security.md``.

Error handling contract: each tool catches
:class:`tallyprime_mcp.tally.exceptions.TallyError` and lets it propagate
with its clean, user-facing ``message`` — FastMCP turns that into an
``isError`` tool result without a Python stack trace. The full exception
(with traceback) is logged locally first. Any *other*, unexpected exception
is logged with a traceback and re-raised as a generic
:class:`~mcp.server.fastmcp.exceptions.ToolError` so internal details never
leak to the client either.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from tallyprime_mcp.logging_config import get_logger
from tallyprime_mcp.security import audit
from tallyprime_mcp.services.company_service import CompanyService
from tallyprime_mcp.services.inventory_service import InventoryService
from tallyprime_mcp.services.ledger_service import LedgerService
from tallyprime_mcp.services.report_service import ReportService
from tallyprime_mcp.services.voucher_service import VoucherService
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyError, ValidationError
from tallyprime_mcp.tally.xml_builder import (
    build_connection_check_request,  # noqa: F401 (re-export for tests)
)

logger = get_logger("mcp.tools")

F = TypeVar("F", bound=Callable[..., Any])


def _parse_date(value: str | None, field_name: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid {field_name} {value!r}: expected ISO format YYYY-MM-DD.",
        ) from exc


def _guarded(tool_name: str) -> Callable[[F], F]:
    """Decorator applied to every tool function: logs invocation/duration,
    translates known TallyError subclasses into clean tool errors, and
    prevents any other exception from leaking a raw traceback to the client.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.monotonic()
            company = kwargs.get("company")
            try:
                result = func(*args, **kwargs)
                audit.log_tool_invocation(tool_name, company=company, allowed=True)
                return result
            except TallyError as exc:
                logger.warning(
                    f"{tool_name} failed: {exc.message}",
                    extra={"tool": tool_name, "company": company},
                )
                if exc.detail:
                    logger.debug(f"{tool_name} error detail: {exc.detail}")
                raise ToolError(exc.message) from exc
            except Exception as exc:  # noqa: BLE001 - last line of defence
                logger.exception(f"{tool_name} raised an unexpected error")
                raise ToolError(
                    "An unexpected internal error occurred. Details were written to the "
                    "local log; no data was sent anywhere external."
                ) from exc
            finally:
                duration_ms = round((time.monotonic() - started) * 1000, 1)
                logger.info(
                    f"{tool_name} completed in {duration_ms}ms",
                    extra={"tool": tool_name, "duration_ms": duration_ms, "company": company},
                )

        return wrapper  # type: ignore[return-value]

    return decorator


def register_tools(mcp: FastMCP, client: TallyClient) -> None:
    """Register every read-only tool on ``mcp`` using the shared ``client``."""

    company_service = CompanyService(client)
    ledger_service = LedgerService(client)
    voucher_service = VoucherService(client)
    report_service = ReportService(client)
    inventory_service = InventoryService(client)

    @mcp.tool()
    @_guarded("test_connection")
    def test_connection() -> dict[str, Any]:
        """Check whether TallyPrime is running and reachable at the configured
        host/port, and whether it responded with valid data. Use this first
        if any other tool call fails unexpectedly."""
        return company_service.test_connection().model_dump()

    @mcp.tool()
    @_guarded("list_companies")
    def list_companies() -> list[dict[str, Any]]:
        """List the companies currently loaded/available in TallyPrime."""
        return [c.model_dump() for c in company_service.list_companies()]

    @mcp.tool()
    @_guarded("list_ledgers")
    def list_ledgers(company: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        """List ledger accounts, with their group, opening balance, and closing
        balance.

        Args:
            company: Company name. If omitted, uses the server's configured
                default company (if any).
            search: Optional case-insensitive substring to filter ledger or
                group names by.
        """
        return [ledger.model_dump() for ledger in ledger_service.list_ledgers(company=company, search=search)]

    @mcp.tool()
    @_guarded("get_ledger")
    def get_ledger(
        ledger_name: str,
        company: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Get a ledger's master details plus its transactions (vouchers) in a
        date range.

        Args:
            ledger_name: Exact ledger name as it appears in TallyPrime.
            company: Company name. If omitted, uses the configured default.
            from_date: Start date, ISO format YYYY-MM-DD. Optional.
            to_date: End date, ISO format YYYY-MM-DD. Optional.
        """
        parsed_from = _parse_date(from_date, "from_date")
        parsed_to = _parse_date(to_date, "to_date")
        detail = ledger_service.get_ledger(
            ledger_name, company=company, from_date=parsed_from, to_date=parsed_to
        )
        return detail.model_dump()

    @mcp.tool()
    @_guarded("search_vouchers")
    def search_vouchers(
        company: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        voucher_type: str | None = None,
        ledger: str | None = None,
        search_term: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search accounting vouchers (invoices, receipts, payments, journals,
        ...) by date range, type, party ledger, or free-text term.

        Args:
            company: Company name. If omitted, uses the configured default.
            from_date: Start date, ISO format YYYY-MM-DD. Optional.
            to_date: End date, ISO format YYYY-MM-DD. Optional.
            voucher_type: Exact voucher type name, e.g. "Receipt", "Payment",
                "Sales". Optional.
            ledger: Substring to match against the voucher's party ledger.
                Optional.
            search_term: Free-text substring matched against all fields
                (narration, reference, etc). Optional.
            limit: Maximum number of vouchers to return. Defaults to the
                server's configured default (100 unless overridden).
        """
        parsed_from = _parse_date(from_date, "from_date")
        parsed_to = _parse_date(to_date, "to_date")
        vouchers = voucher_service.search_vouchers(
            company=company,
            from_date=parsed_from,
            to_date=parsed_to,
            voucher_type=voucher_type,
            ledger=ledger,
            search_term=search_term,
            limit=limit,
        )
        return [v.model_dump() for v in vouchers]

    @mcp.tool()
    @_guarded("get_voucher")
    def get_voucher(voucher_identifier: str, company: str | None = None) -> dict[str, Any]:
        """Get a single voucher by its voucher number.

        Args:
            voucher_identifier: The voucher number as it appears in TallyPrime.
            company: Company name. If omitted, uses the configured default.
        """
        return voucher_service.get_voucher(voucher_identifier, company=company).model_dump()

    @mcp.tool()
    @_guarded("get_trial_balance")
    def get_trial_balance(
        company: str | None = None, from_date: str | None = None, to_date: str | None = None
    ) -> dict[str, Any]:
        """Get a trial balance: every ledger with a non-zero closing balance,
        split into debit/credit columns, with totals.

        Args:
            company: Company name. If omitted, uses the configured default.
            from_date: Start date, ISO format YYYY-MM-DD. Currently informational
                only — closing balances reflect TallyPrime's current ledger
                state rather than a point-in-time reconstruction; see
                docs/tools.md.
            to_date: End date, ISO format YYYY-MM-DD. Same caveat as from_date.
        """
        parsed_from = _parse_date(from_date, "from_date")
        parsed_to = _parse_date(to_date, "to_date")
        return report_service.get_trial_balance(company=company, from_date=parsed_from, to_date=parsed_to).model_dump()

    @mcp.tool()
    @_guarded("get_profit_and_loss")
    def get_profit_and_loss(
        company: str | None = None, from_date: str | None = None, to_date: str | None = None
    ) -> dict[str, Any]:
        """Get a simplified Profit & Loss statement, grouping income and
        expense ledgers by their standard Tally primary group.

        Args:
            company: Company name. If omitted, uses the configured default.
            from_date: Start date, ISO format YYYY-MM-DD.
            to_date: End date, ISO format YYYY-MM-DD.
        """
        parsed_from = _parse_date(from_date, "from_date")
        parsed_to = _parse_date(to_date, "to_date")
        return report_service.get_profit_and_loss(
            company=company, from_date=parsed_from, to_date=parsed_to
        ).model_dump()

    @mcp.tool()
    @_guarded("get_balance_sheet")
    def get_balance_sheet(company: str | None = None, as_of_date: str | None = None) -> dict[str, Any]:
        """Get a simplified Balance Sheet, grouping asset and liability
        ledgers by their standard Tally primary group.

        Args:
            company: Company name. If omitted, uses the configured default.
            as_of_date: Date, ISO format YYYY-MM-DD. Currently informational
                only — see docs/tools.md.
        """
        parsed_date = _parse_date(as_of_date, "as_of_date")
        return report_service.get_balance_sheet(company=company, as_of_date=parsed_date).model_dump()

    @mcp.tool()
    @_guarded("get_receivables")
    def get_receivables(company: str | None = None, as_of_date: str | None = None) -> dict[str, Any]:
        """Get outstanding receivables: ledgers under 'Sundry Debtors' with a
        non-zero balance owed to the company.

        Args:
            company: Company name. If omitted, uses the configured default.
            as_of_date: Date, ISO format YYYY-MM-DD. Currently informational
                only — see docs/tools.md.
        """
        parsed_date = _parse_date(as_of_date, "as_of_date")
        return report_service.get_receivables(company=company, as_of_date=parsed_date).model_dump()

    @mcp.tool()
    @_guarded("get_payables")
    def get_payables(company: str | None = None, as_of_date: str | None = None) -> dict[str, Any]:
        """Get outstanding payables: ledgers under 'Sundry Creditors' with a
        non-zero balance owed by the company.

        Args:
            company: Company name. If omitted, uses the configured default.
            as_of_date: Date, ISO format YYYY-MM-DD. Currently informational
                only — see docs/tools.md.
        """
        parsed_date = _parse_date(as_of_date, "as_of_date")
        return report_service.get_payables(company=company, as_of_date=parsed_date).model_dump()

    @mcp.tool()
    @_guarded("list_stock_items")
    def list_stock_items(company: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
        """List stock (inventory) items with opening/closing quantity and value.

        Args:
            company: Company name. If omitted, uses the configured default.
            search: Optional case-insensitive substring to filter item names by.
        """
        return [item.model_dump() for item in inventory_service.list_stock_items(company=company, search=search)]

    @mcp.tool()
    @_guarded("get_stock_summary")
    def get_stock_summary(
        company: str | None = None, from_date: str | None = None, to_date: str | None = None
    ) -> dict[str, Any]:
        """Get an aggregate stock summary across all items for a company.

        Args:
            company: Company name. If omitted, uses the configured default.
            from_date: Start date, ISO format YYYY-MM-DD. Currently informational
                only — see docs/tools.md.
            to_date: End date, ISO format YYYY-MM-DD.
        """
        parsed_from = _parse_date(from_date, "from_date")
        parsed_to = _parse_date(to_date, "to_date")
        return inventory_service.get_stock_summary(
            company=company, from_date=parsed_from, to_date=parsed_to
        ).model_dump()

    if client.settings.expose_raw_xml_tool:
        _register_debug_raw_xml_tool(mcp, client)


def _register_debug_raw_xml_tool(mcp: FastMCP, client: TallyClient) -> None:
    """Registers a debug-only tool that returns raw TallyPrime XML for one of
    a fixed, known set of request kinds. Only registered when
    ``TALLY_EXPOSE_RAW_XML_TOOL=true`` is explicitly set — never on by
    default. This is NOT a generic XML execution tool: the set of requests
    it can make is fixed to the same read-only collection requests the
    normal tools already use.
    """
    from tallyprime_mcp.tally.xml_builder import build_collection_request
    from tallyprime_mcp.tally.xml_parser import parse_xml

    _KNOWN_KINDS = {"companies", "ledgers", "vouchers", "groups", "stock_items"}
    _KIND_TO_TYPE = {
        "companies": "Company",
        "ledgers": "Ledger",
        "vouchers": "Voucher",
        "groups": "Group",
        "stock_items": "StockItem",
    }

    @mcp.tool()
    @_guarded("debug_raw_xml")
    def debug_raw_xml(kind: str, company: str | None = None) -> dict[str, Any]:
        """[DEBUG ONLY — disabled by default] Return the raw TallyPrime XML
        response for a fixed, known read-only collection request. Intended
        for troubleshooting field-name mismatches, not for general use.

        Args:
            kind: One of "companies", "ledgers", "vouchers", "groups",
                "stock_items".
            company: Company name, if applicable.
        """
        if kind not in _KNOWN_KINDS:
            raise ValidationError(f"kind must be one of {sorted(_KNOWN_KINDS)}")
        native_type = _KIND_TO_TYPE[kind]
        request = build_collection_request(
            collection_name=f"MCPDebug{kind}",
            native_type=native_type,
            fetch_fields=["NAME"],
        )
        response = client._connection.send(request)  # noqa: SLF001 - debug tool, intentional
        root = parse_xml(response.raw_bytes)
        from xml.etree.ElementTree import tostring

        return {"kind": kind, "raw_xml": tostring(root, encoding="unicode")}
