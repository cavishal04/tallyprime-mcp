from __future__ import annotations

from datetime import date

from tallyprime_mcp.models.voucher import Voucher
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyRequestError
from tallyprime_mcp.tally.xml_parser import TallyRecord, field_amount, field_text, parse_tally_date


class VoucherService:
    def __init__(self, client: TallyClient) -> None:
        self._client = client

    def to_voucher(self, record: TallyRecord) -> Voucher:
        return Voucher(
            date=parse_tally_date(field_text(record, "DATE")),
            voucher_number=field_text(record, "VOUCHERNUMBER") or None,
            voucher_type=field_text(record, "VOUCHERTYPENAME") or None,
            party=field_text(record, "PARTYLEDGERNAME") or None,
            amount=field_amount(record, "AMOUNT"),
            narration=field_text(record, "NARRATION") or None,
            reference=field_text(record, "REFERENCE") or None,
        )

    def search_vouchers(
        self,
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        voucher_type: str | None = None,
        ledger: str | None = None,
        search_term: str | None = None,
        limit: int | None = None,
    ) -> list[Voucher]:
        records = self._client.search_vouchers(
            company=company,
            from_date=from_date,
            to_date=to_date,
            voucher_type=voucher_type,
            ledger=ledger,
            search_term=search_term,
            limit=limit,
        )
        return [self.to_voucher(r) for r in records]

    def get_voucher(self, voucher_identifier: str, company: str | None = None) -> Voucher:
        record = self._client.get_voucher(voucher_identifier, company=company)
        if record is None:
            raise TallyRequestError(
                f"Voucher {voucher_identifier!r} was not found.",
                detail="Check the voucher number and try search_vouchers to locate it.",
            )
        return self.to_voucher(record)
