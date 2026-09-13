"""High-level TallyPrime client: turns typed requests into TallyRecord lists.

This layer knows *what* to ask Tally for (which native object types and
fields) but returns loosely-typed :class:`~tallyprime_mcp.tally.xml_parser.TallyRecord`
data rather than the project's own Pydantic domain models — that mapping
lives in :mod:`tallyprime_mcp.services`, which keeps "talk to Tally" and
"shape data for the MCP tool response" separate and independently testable.
"""

from __future__ import annotations

from datetime import date

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.logging_config import get_logger
from tallyprime_mcp.tally import field_maps
from tallyprime_mcp.tally.connection import TallyConnection
from tallyprime_mcp.tally.exceptions import TallyCompanyNotFoundError, TallyRequestError
from tallyprime_mcp.tally.xml_builder import StaticVariables, build_collection_request
from tallyprime_mcp.tally.xml_parser import (
    TallyRecord,
    check_for_tally_error,
    extract_records,
    parse_xml,
)

logger = get_logger("tally.client")


class TallyClient:
    """Synchronous client for TallyPrime's local HTTP-XML gateway.

    All methods are read-only: none of them can create, alter, or delete
    Tally data. See :mod:`tallyprime_mcp.security.permissions` for the
    (currently trivial, always-deny) write-permission gate that any future
    write method would have to pass through.
    """

    def __init__(self, settings: TallySettings, connection: TallyConnection | None = None) -> None:
        self._settings = settings
        self._connection = connection or TallyConnection(settings)
        self._owns_connection = connection is None

    @property
    def settings(self) -> TallySettings:
        return self._settings

    def close(self) -> None:
        if self._owns_connection:
            self._connection.close()

    def __enter__(self) -> TallyClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- internal helpers --------------------------------------------------

    def _collection(
        self,
        *,
        collection_name: str,
        native_type: str,
        fetch_fields: list[str],
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        extra_static_vars: dict[str, str] | None = None,
    ) -> list[TallyRecord]:
        static_vars = StaticVariables(
            current_company=company or self._settings.default_company,
            from_date=from_date,
            to_date=to_date,
            extra=extra_static_vars or {},
        )
        request = build_collection_request(
            collection_name=collection_name,
            native_type=native_type,
            fetch_fields=fetch_fields,
            static_variables=static_vars,
        )
        response = self._connection.send(request)
        root = parse_xml(response.raw_bytes)
        check_for_tally_error(root)
        records = extract_records(root, native_type)
        if not records and company:
            # A request scoped to a company that isn't loaded typically comes
            # back with zero records rather than a distinct Tally error, so
            # we double-check company existence to give a clearer message.
            self._verify_company_loaded(company)
        return records

    def _verify_company_loaded(self, company: str) -> None:
        companies = {c.name for c in self.list_companies() if c.name}
        if companies and company not in companies:
            raise TallyCompanyNotFoundError(
                f"Company {company!r} is not currently loaded in TallyPrime.",
                detail=f"Companies currently loaded: {', '.join(sorted(companies)) or '(none)'}",
            )

    # -- connection ----------------------------------------------------------

    def test_connection(self) -> tuple[bool, str]:
        """Check whether TallyPrime is reachable and speaking XML.

        Returns ``(ok, message)`` — this never raises for the "Tally isn't
        reachable" case itself so callers can present a clean status without
        a stack of exception handling, but transport-level surprises (e.g. a
        proxy returning an unrelated 200 OK of garbage) still raise via the
        normal exception path from :func:`parse_xml`.
        """
        try:
            self.list_companies()
        except TallyRequestError as exc:
            return False, f"TallyPrime responded but reported an error: {exc.message}"
        except Exception as exc:  # noqa: BLE001 - surfaced as a clean status message
            from tallyprime_mcp.tally.exceptions import TallyError

            if isinstance(exc, TallyError):
                return False, exc.message
            raise
        return True, f"Connected to TallyPrime at {self._settings.base_url}."

    # -- companies -------------------------------------------------------------

    def list_companies(self) -> list[TallyRecord]:
        return self._collection(
            collection_name="MCPCompanyList",
            native_type="Company",
            fetch_fields=["NAME", "STARTINGFROM", "BOOKSFROM"],
        )

    # -- ledgers ---------------------------------------------------------------

    def list_ledgers(self, company: str | None = None) -> list[TallyRecord]:
        return self._collection(
            collection_name="MCPLedgerList",
            native_type="Ledger",
            fetch_fields=field_maps.LEDGER_FETCH_FIELDS,
            company=company,
        )

    def get_ledger(
        self,
        ledger_name: str,
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[TallyRecord | None, list[TallyRecord]]:
        """Return ``(ledger_master_record, vouchers_in_range)``.

        TallyPrime's per-ledger transaction view is normally driven by a
        "Ledger Vouchers" report rather than a flat collection, so
        transactions are fetched here via the voucher collection filtered
        to this ledger, which is the more robust cross-version approach.
        """
        ledgers = self._collection(
            collection_name="MCPLedgerDetail",
            native_type="Ledger",
            fetch_fields=field_maps.LEDGER_FETCH_FIELDS,
            company=company,
        )
        ledger = next((r for r in ledgers if r.name == ledger_name), None)
        vouchers = self.search_vouchers(
            company=company,
            from_date=from_date,
            to_date=to_date,
            ledger=ledger_name,
        )
        return ledger, vouchers

    # -- vouchers ------------------------------------------------------------

    def search_vouchers(
        self,
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        voucher_type: str | None = None,
        ledger: str | None = None,
        search_term: str | None = None,
        limit: int | None = None,
    ) -> list[TallyRecord]:
        records = self._collection(
            collection_name="MCPVoucherSearch",
            native_type="Voucher",
            fetch_fields=field_maps.VOUCHER_FETCH_FIELDS,
            company=company,
            from_date=from_date,
            to_date=to_date,
        )

        def matches(record: TallyRecord) -> bool:
            if voucher_type and record.fields.get("VOUCHERTYPENAME", "").lower() != voucher_type.lower():
                return False
            if ledger and ledger.lower() not in record.fields.get("PARTYLEDGERNAME", "").lower():
                return False
            if search_term:
                haystack = " ".join(record.fields.values()).lower()
                if search_term.lower() not in haystack:
                    return False
            return True

        filtered = [r for r in records if matches(r)]
        effective_limit = limit or self._settings.default_voucher_limit
        return filtered[:effective_limit]

    def get_voucher(self, voucher_identifier: str, company: str | None = None) -> TallyRecord | None:
        records = self._collection(
            collection_name="MCPVoucherLookup",
            native_type="Voucher",
            fetch_fields=field_maps.VOUCHER_FETCH_FIELDS,
            company=company,
        )
        for record in records:
            if record.fields.get("VOUCHERNUMBER") == voucher_identifier:
                return record
        return None

    # -- ledgers/groups for reports -------------------------------------------

    def list_groups(self, company: str | None = None) -> list[TallyRecord]:
        return self._collection(
            collection_name="MCPGroupList",
            native_type="Group",
            fetch_fields=field_maps.GROUP_FETCH_FIELDS,
            company=company,
        )

    # -- stock -----------------------------------------------------------------

    def list_stock_items(self, company: str | None = None, search: str | None = None) -> list[TallyRecord]:
        records = self._collection(
            collection_name="MCPStockItemList",
            native_type="StockItem",
            fetch_fields=field_maps.STOCK_ITEM_FETCH_FIELDS,
            company=company,
        )
        if search:
            records = [r for r in records if search.lower() in (r.name or "").lower()]
        return records
