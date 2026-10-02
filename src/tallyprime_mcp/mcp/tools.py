"""Registers TallyPrime MCP's tools on a FastMCP server instance.

The read-only tools are always registered. The write tools
(``create_ledger``, ``create_voucher``, ``confirm_write``, ``cancel_write``)
are registered only when ``TALLY_READ_ONLY=false``, and every write is
two-step: the create tool returns a preview, and nothing reaches Tally until
``confirm_write`` is called. No tool can alter or delete existing data, and
there is deliberately no generic "execute arbitrary Tally XML" tool — see
``docs/security.md``.

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
from decimal import Decimal
from typing import Any, Literal, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from tallyprime_mcp.logging_config import get_logger
from tallyprime_mcp.models.write import VoucherEntry
from tallyprime_mcp.security import audit
from tallyprime_mcp.security.confirmation import ConfirmationStore
from tallyprime_mcp.security.permissions import WritePermission
from tallyprime_mcp.services.company_service import CompanyService
from tallyprime_mcp.services.inventory_service import InventoryService
from tallyprime_mcp.services.ledger_service import LedgerService
from tallyprime_mcp.services.report_service import ReportService
from tallyprime_mcp.services.voucher_service import VoucherService
from tallyprime_mcp.services.write_service import WriteService
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
    """Register every read-only tool on ``mcp`` using the shared ``client``,
    plus the write tools if the server is not in read-only mode."""

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

    if not client.settings.read_only:
        _register_write_tools(mcp, client)

    if client.settings.expose_raw_xml_tool:
        _register_debug_raw_xml_tool(mcp, client)


_PROPOSE = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
_COMMIT = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)


def _register_write_tools(mcp: FastMCP, client: TallyClient) -> None:
    """Registers the two-step write tools. Only called when
    ``TALLY_READ_ONLY=false``."""
    write_service = WriteService(
        client,
        ConfirmationStore(client.settings.write_confirmation_ttl_seconds),
        WritePermission(client.settings),
    )

    @mcp.tool(annotations=_PROPOSE)
    @_guarded("create_ledger")
    def create_ledger(
        name: str,
        parent_group: str,
        company: str | None = None,
        opening_balance: Decimal | None = None,
        opening_balance_side: Literal["debit", "credit"] = "debit",
    ) -> dict[str, Any]:
        """PROPOSE creating a new ledger in TallyPrime. This does NOT write
        anything: it validates the request and returns a preview with a
        confirmation_id. Show the preview to the user, and only call
        confirm_write after they explicitly approve it.

        Args:
            name: New ledger name. Must not already exist.
            parent_group: Existing group to create it under, e.g.
                "Sundry Debtors", "Sundry Creditors", "Bank Accounts",
                "Indirect Expenses".
            company: Company name. If omitted, uses the configured default.
                Required for writes if no default is configured.
            opening_balance: Optional positive opening balance.
            opening_balance_side: "debit" or "credit" for the opening balance.
        """
        return write_service.prepare_create_ledger(
            name,
            parent_group,
            company=company,
            opening_balance=opening_balance,
            opening_balance_side=opening_balance_side,
        ).model_dump()

    @mcp.tool(annotations=_PROPOSE)
    @_guarded("create_voucher")
    def create_voucher(
        voucher_type: str,
        date: str,
        entries: list[VoucherEntry],
        company: str | None = None,
        narration: str | None = None,
        voucher_number: str | None = None,
        reference: str | None = None,
        party_ledger: str | None = None,
    ) -> dict[str, Any]:
        """PROPOSE creating an accounting voucher (Payment, Receipt, Journal,
        Contra, or Sales/Purchase in accounting mode) in TallyPrime. This does
        NOT write anything: it validates the request and returns a preview
        with a confirmation_id. Show the preview to the user, and only call
        confirm_write after they explicitly approve it.

        Debits must equal credits. Example — pay 5,000 rent from the bank:
        entries=[{"ledger": "Office Rent", "side": "debit", "amount": 5000},
                 {"ledger": "HDFC Bank", "side": "credit", "amount": 5000}]

        Args:
            voucher_type: Voucher type name as it exists in Tally, e.g.
                "Payment", "Receipt", "Journal", "Contra", "Sales", "Purchase".
            date: Voucher date, ISO format YYYY-MM-DD.
            entries: Two or more {ledger, side ("debit"/"credit"), amount}
                lines. All ledgers must already exist.
            company: Company name. If omitted, uses the configured default.
                Required for writes if no default is configured.
            narration: Optional narration.
            voucher_number: Optional voucher number (Tally auto-numbers if
                omitted and the voucher type is set to automatic numbering).
            reference: Optional reference (e.g. bill or cheque number).
            party_ledger: Optional party ledger (must also exist).
        """
        parsed_date = _parse_date(date, "date")
        if parsed_date is None:
            raise ValidationError("date is required (YYYY-MM-DD).")
        return write_service.prepare_create_voucher(
            voucher_type,
            parsed_date,
            entries,
            company=company,
            narration=narration,
            voucher_number=voucher_number,
            reference=reference,
            party_ledger=party_ledger,
        ).model_dump()

    @mcp.tool(annotations=_COMMIT)
    @_guarded("confirm_write")
    def confirm_write(confirmation_id: str) -> dict[str, Any]:
        """WRITE to TallyPrime: execute a previously proposed create_ledger or
        create_voucher. Only call this after the user has seen the preview
        and explicitly approved it in the conversation. Each
        confirmation_id can be used once and expires after a few minutes.

        Args:
            confirmation_id: The id returned by create_ledger/create_voucher.
        """
        return write_service.confirm(confirmation_id).model_dump()

    @mcp.tool(annotations=_PROPOSE)
    @_guarded("cancel_write")
    def cancel_write(confirmation_id: str) -> dict[str, Any]:
        """Discard a proposed write without sending anything to TallyPrime.

        Args:
            confirmation_id: The id returned by create_ledger/create_voucher.
        """
        return write_service.cancel(confirmation_id)


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
