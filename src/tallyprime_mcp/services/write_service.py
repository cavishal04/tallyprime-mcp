"""Validates, previews, and executes write operations against TallyPrime.

Every ``prepare_*`` method checks the write-permission gate, validates the
request against the live company (ledgers/groups must exist, vouchers must
balance), builds the exact import XML, and parks it in the
:class:`~tallyprime_mcp.security.confirmation.ConfirmationStore`. Nothing is
sent to Tally until :meth:`WriteService.confirm` is called with the
returned ``confirmation_id``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from tallyprime_mcp.models.write import VoucherEntry, WritePreview, WriteResult
from tallyprime_mcp.security import audit
from tallyprime_mcp.security.confirmation import ConfirmationStore, PendingConfirmation
from tallyprime_mcp.security.permissions import WritePermission
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyCompanyNotFoundError, TallyError, ValidationError
from tallyprime_mcp.tally.xml_builder import (
    DEBIT,
    LedgerEntryLine,
    build_import_request,
    build_ledger_element,
    build_voucher_element,
)

_MAX_TEXT = 1000


class WriteService:
    def __init__(
        self, client: TallyClient, store: ConfirmationStore, permission: WritePermission
    ) -> None:
        self._client = client
        self._store = store
        self._permission = permission

    # -- helpers ---------------------------------------------------------------

    def _require_permission(self, operation: str) -> None:
        result = self._permission.check(operation)
        if not result.allowed:
            audit.log_permission_denied(operation, result.reason)
            raise ValidationError(result.reason)

    def _resolve_company(self, company: str | None) -> str:
        """Writes never fall back to "whatever company is active in Tally":
        the target must be explicit or configured, and currently loaded."""
        resolved = (company or self._client.settings.default_company or "").strip()
        if not resolved:
            raise ValidationError(
                "A company is required for writes. Pass `company` or set TALLY_DEFAULT_COMPANY.",
            )
        loaded = {c.name for c in self._client.list_companies() if c.name}
        if resolved not in loaded:
            raise TallyCompanyNotFoundError(
                f"Company {resolved!r} is not currently loaded in TallyPrime.",
                detail=f"Companies currently loaded: {', '.join(sorted(loaded)) or '(none)'}",
            )
        return resolved

    @staticmethod
    def _clean_text(value: str | None, field_name: str) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > _MAX_TEXT:
            raise ValidationError(f"{field_name} must be at most {_MAX_TEXT} characters.")
        return value or None

    def _park(
        self, operation: str, company: str, summary: str, request_xml: bytes, details: dict
    ) -> WritePreview:
        pending = self._store.add(
            PendingConfirmation(
                operation=operation,
                summary=summary,
                company=company,
                request_xml=request_xml,
                proposed_payload=details,
            )
        )
        audit.log_write(
            operation, company=company, confirmation_id=pending.confirmation_id, outcome="proposed"
        )
        return WritePreview(
            confirmation_id=pending.confirmation_id,
            operation=operation,
            company=company,
            summary=summary,
            details=details,
            expires_at=pending.expires_at.isoformat() if pending.expires_at else "",
        )

    # -- create_ledger -----------------------------------------------------------

    def prepare_create_ledger(
        self,
        name: str,
        parent_group: str,
        company: str | None = None,
        opening_balance: Decimal | None = None,
        opening_balance_side: str = DEBIT,
    ) -> WritePreview:
        operation = "create_ledger"
        self._require_permission(operation)
        name = self._clean_text(name, "name") or ""
        parent_group = self._clean_text(parent_group, "parent_group") or ""
        if not name or not parent_group:
            raise ValidationError("Both name and parent_group are required.")
        if opening_balance is not None and opening_balance < 0:
            raise ValidationError("opening_balance must be positive; use opening_balance_side.")
        if opening_balance_side not in {"debit", "credit"}:
            raise ValidationError("opening_balance_side must be 'debit' or 'credit'.")

        company = self._resolve_company(company)
        existing = {r.name for r in self._client.list_ledgers(company) if r.name}
        if name in existing:
            raise ValidationError(f"A ledger named {name!r} already exists in {company!r}.")
        groups = {r.name for r in self._client.list_groups(company) if r.name}
        if parent_group not in groups:
            raise ValidationError(
                f"Group {parent_group!r} does not exist in {company!r}.",
                detail=f"Available groups: {', '.join(sorted(groups))}",
            )

        request_xml = build_import_request(
            "All Masters",
            company,
            [build_ledger_element(name, parent_group, opening_balance, opening_balance_side)],
        )
        summary = f"Create ledger {name!r} under {parent_group!r} in {company!r}"
        if opening_balance:
            summary += f" with opening balance {opening_balance:.2f} {opening_balance_side.title()}"
        details = {
            "name": name,
            "parent_group": parent_group,
            "opening_balance": float(opening_balance or 0),
            "opening_balance_side": opening_balance_side,
        }
        return self._park(operation, company, summary, request_xml, details)

    # -- create_voucher ------------------------------------------------------------

    def prepare_create_voucher(
        self,
        voucher_type: str,
        voucher_date: date,
        entries: list[VoucherEntry],
        company: str | None = None,
        narration: str | None = None,
        voucher_number: str | None = None,
        reference: str | None = None,
        party_ledger: str | None = None,
    ) -> WritePreview:
        operation = "create_voucher"
        self._require_permission(operation)
        voucher_type = self._clean_text(voucher_type, "voucher_type") or ""
        if not voucher_type:
            raise ValidationError("voucher_type is required, e.g. 'Payment', 'Receipt', 'Journal'.")
        narration = self._clean_text(narration, "narration")
        voucher_number = self._clean_text(voucher_number, "voucher_number")
        reference = self._clean_text(reference, "reference")
        party_ledger = self._clean_text(party_ledger, "party_ledger")

        if len(entries) < 2:
            raise ValidationError("A voucher needs at least two entries (one debit, one credit).")
        debit_total = sum((e.amount for e in entries if e.side == "debit"), Decimal(0))
        credit_total = sum((e.amount for e in entries if e.side == "credit"), Decimal(0))
        if not debit_total or not credit_total:
            raise ValidationError("A voucher needs at least one debit and one credit entry.")
        if debit_total != credit_total:
            raise ValidationError(
                f"Voucher does not balance: debits {debit_total:.2f} != credits {credit_total:.2f}.",
            )

        company = self._resolve_company(company)
        known = {r.name for r in self._client.list_ledgers(company) if r.name}
        referenced = {e.ledger for e in entries} | ({party_ledger} if party_ledger else set())
        missing = sorted(referenced - known)
        if missing:
            raise ValidationError(
                f"Ledger(s) not found in {company!r}: {', '.join(missing)}.",
                detail="Ledger names must match TallyPrime exactly. Use list_ledgers to check, "
                "or create_ledger to add them first.",
            )

        lines = [LedgerEntryLine(e.ledger, e.amount, e.side) for e in entries]
        request_xml = build_import_request(
            "Vouchers",
            company,
            [
                build_voucher_element(
                    voucher_type,
                    voucher_date,
                    lines,
                    narration=narration,
                    voucher_number=voucher_number,
                    reference=reference,
                    party_ledger=party_ledger,
                )
            ],
        )
        summary = (
            f"Create {voucher_type} voucher dated {voucher_date.isoformat()} in {company!r} "
            f"for {debit_total:.2f}"
        )
        details = {
            "voucher_type": voucher_type,
            "date": voucher_date.isoformat(),
            "voucher_number": voucher_number,
            "reference": reference,
            "party_ledger": party_ledger,
            "narration": narration,
            "entries": [
                {"ledger": e.ledger, "side": e.side, "amount": float(e.amount)} for e in entries
            ],
            "total": float(debit_total),
        }
        return self._park(operation, company, summary, request_xml, details)

    # -- confirm / cancel ------------------------------------------------------------

    def confirm(self, confirmation_id: str) -> WriteResult:
        pending = self._store.pop(confirmation_id)
        # Re-check: the server's mode can't change at runtime today, but the
        # gate is cheap and keeps "every write passes the gate" literally true.
        self._require_permission(pending.operation)
        try:
            result = self._client.import_data(pending.request_xml)
        except TallyError as exc:
            audit.log_write(
                pending.operation,
                company=pending.company,
                confirmation_id=confirmation_id,
                outcome="failed",
                detail=exc.detail or exc.message,
            )
            raise
        audit.log_write(
            pending.operation,
            company=pending.company,
            confirmation_id=confirmation_id,
            outcome="committed",
        )
        return WriteResult(
            confirmation_id=confirmation_id,
            operation=pending.operation,
            company=pending.company,
            status="committed",
            summary=pending.summary,
            created=result.created,
            altered=result.altered,
            tally_voucher_id=result.last_voucher_id,
            tally_master_id=result.last_master_id,
        )

    def cancel(self, confirmation_id: str) -> dict[str, str]:
        pending = self._store.pop(confirmation_id)
        audit.log_write(
            pending.operation,
            company=pending.company,
            confirmation_id=confirmation_id,
            outcome="cancelled",
        )
        return {
            "confirmation_id": confirmation_id,
            "status": "cancelled",
            "summary": pending.summary,
        }
