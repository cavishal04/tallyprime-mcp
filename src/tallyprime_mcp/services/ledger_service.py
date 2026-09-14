from __future__ import annotations

from datetime import date

from tallyprime_mcp.models.ledger import Ledger, LedgerDetail
from tallyprime_mcp.services.voucher_service import VoucherService
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyRequestError
from tallyprime_mcp.tally.xml_parser import TallyRecord, field_amount, field_text


def ledger_from_record(record: TallyRecord) -> Ledger:
    return Ledger(
        name=record.name or field_text(record, "NAME"),
        group=field_text(record, "PARENT") or None,
        opening_balance=field_amount(record, "OPENINGBALANCE"),
        closing_balance=field_amount(record, "CLOSINGBALANCE"),
        email=field_text(record, "EMAIL") or None,
        gstin=field_text(record, "GSTIN") or None,
    )


class LedgerService:
    def __init__(self, client: TallyClient) -> None:
        self._client = client
        self._vouchers = VoucherService(client)

    def list_ledgers(self, company: str | None = None, search: str | None = None) -> list[Ledger]:
        records = self._client.list_ledgers(company=company)
        ledgers = [ledger_from_record(r) for r in records if (r.name or field_text(r, "NAME"))]
        if search:
            needle = search.lower()
            ledgers = [
                ledger
                for ledger in ledgers
                if needle in ledger.name.lower() or (ledger.group and needle in ledger.group.lower())
            ]
        return ledgers

    def get_ledger(
        self,
        ledger_name: str,
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> LedgerDetail:
        record, voucher_records = self._client.get_ledger(
            ledger_name, company=company, from_date=from_date, to_date=to_date
        )
        if record is None:
            raise TallyRequestError(
                f"Ledger {ledger_name!r} was not found.",
                detail="Check the exact spelling/case used in TallyPrime, or call "
                "list_ledgers to search.",
            )
        ledger = ledger_from_record(record)
        vouchers = [self._vouchers.to_voucher(v) for v in voucher_records]
        total_debit = sum(v.amount for v in vouchers if v.amount > 0)
        total_credit = sum(-v.amount for v in vouchers if v.amount < 0)
        return LedgerDetail(
            ledger=ledger,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            vouchers=vouchers,
            total_debit=total_debit,
            total_credit=total_credit,
        )
