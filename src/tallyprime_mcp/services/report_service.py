"""Builds financial reports (trial balance, P&L, balance sheet, receivables,
payables) from ledger and group master data.

Design decision — why these reports are computed rather than exported
-----------------------------------------------------------------------
TallyPrime's own "Trial Balance"/"Profit & Loss"/"Balance Sheet" *canned
reports* have on-screen-layout-specific XML export shapes (nested
``DSPACCNAME``/``DSPCLDRAMT``-style display fields) that differ across
report configurations and TallyPrime versions, and could not be verified
against a live TallyPrime instance while building this project (see
README "Testing" section). Rather than hard-coding a guessed field layout
for those canned reports and risking silently-wrong numbers, this service
computes each statement itself from two things that *are* built on the
well-documented, stable ``Collection`` export pattern (see
:mod:`tallyprime_mcp.tally.xml_builder`):

* every ledger's closing balance (``get all ledgers``), and
* the ledger-group hierarchy (``get all groups``), classified against
  TallyPrime's fixed, documented set of standard primary groups
  (:mod:`tallyprime_mcp.tally.field_maps`).

This is a standard, textbook-correct way to derive a trial balance and a
(simplified) P&L/Balance Sheet from a chart of accounts, and it keeps the
implementation resilient to TallyPrime version differences in canned-report
export layout. It is, however, a *simplification*: it will not reproduce
schedule-style groupings, ratio analysis, or Tally-specific report
customisations a user may have configured on-screen. See ``docs/tools.md``
for details and for how to extend this once verified against a live Tally
instance.
"""

from __future__ import annotations

from datetime import date

from tallyprime_mcp.models.reports import (
    BalanceSheet,
    PartyOutstanding,
    PayablesReport,
    ProfitAndLoss,
    ReceivablesReport,
    StatementGroup,
    TrialBalance,
    TrialBalanceLine,
)
from tallyprime_mcp.services.ledger_service import ledger_from_record
from tallyprime_mcp.tally import field_maps
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.xml_parser import TallyRecord, field_text

_RECEIVABLE_GROUPS = {"sundry debtors"}
_PAYABLE_GROUPS = {"sundry creditors"}


def _group_parent_map(group_records: list[TallyRecord]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for record in group_records:
        name = record.name or field_text(record, "NAME")
        parent = field_text(record, "PARENT")
        if name:
            mapping[name] = parent
    return mapping


def _root_group(name: str | None, parent_map: dict[str, str], max_depth: int = 25) -> str | None:
    if not name:
        return None
    current = name
    seen: set[str] = set()
    for _ in range(max_depth):
        if current in seen:
            break  # defensive: cyclic parent chain should never happen, but never loop forever
        seen.add(current)
        parent = parent_map.get(current)
        if not parent:
            return current
        current = parent
    return current


class ReportService:
    def __init__(self, client: TallyClient) -> None:
        self._client = client

    def _ledgers_with_roots(self, company: str | None) -> list[tuple[TallyRecord, str | None]]:
        ledger_records = self._client.list_ledgers(company=company)
        group_records = self._client.list_groups(company=company)
        parent_map = _group_parent_map(group_records)
        out = []
        for record in ledger_records:
            group_name = field_text(record, "PARENT")
            root = _root_group(group_name, parent_map)
            out.append((record, root))
        return out

    # -- trial balance ---------------------------------------------------------

    def get_trial_balance(
        self, company: str | None = None, from_date: date | None = None, to_date: date | None = None
    ) -> TrialBalance:
        lines: list[TrialBalanceLine] = []
        total_debit = 0.0
        total_credit = 0.0
        for record in self._client.list_ledgers(company=company):
            ledger = ledger_from_record(record)
            debit = ledger.closing_balance if ledger.closing_balance > 0 else 0.0
            credit = -ledger.closing_balance if ledger.closing_balance < 0 else 0.0
            if debit == 0.0 and credit == 0.0:
                continue
            lines.append(TrialBalanceLine(ledger=ledger.name, group=ledger.group, debit=debit, credit=credit))
            total_debit += debit
            total_credit += credit
        return TrialBalance(
            company=company or self._client.settings.default_company,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            lines=sorted(lines, key=lambda line: line.ledger),
            total_debit=round(total_debit, 2),
            total_credit=round(total_credit, 2),
        )

    # -- profit and loss ---------------------------------------------------------

    def get_profit_and_loss(
        self, company: str | None = None, from_date: date | None = None, to_date: date | None = None
    ) -> ProfitAndLoss:
        income_by_group: dict[str, list[TrialBalanceLine]] = {}
        expense_by_group: dict[str, list[TrialBalanceLine]] = {}

        for record, root in self._ledgers_with_roots(company):
            if root not in field_maps.PROFIT_AND_LOSS_PRIMARY_GROUPS:
                continue
            ledger = ledger_from_record(record)
            amount = abs(ledger.closing_balance)
            line = TrialBalanceLine(
                ledger=ledger.name,
                group=ledger.group,
                debit=amount if ledger.closing_balance > 0 else 0.0,
                credit=amount if ledger.closing_balance < 0 else 0.0,
            )
            is_income = root in {"Sales Accounts", "Direct Incomes", "Indirect Incomes"}
            bucket = income_by_group if is_income else expense_by_group
            bucket.setdefault(root, []).append(line)

        income_groups = [
            StatementGroup(group=g, amount=round(sum(x.credit + x.debit for x in lines), 2), ledgers=lines)
            for g, lines in income_by_group.items()
        ]
        expense_groups = [
            StatementGroup(group=g, amount=round(sum(x.credit + x.debit for x in lines), 2), ledgers=lines)
            for g, lines in expense_by_group.items()
        ]
        total_income = round(sum(g.amount for g in income_groups), 2)
        total_expense = round(sum(g.amount for g in expense_groups), 2)
        return ProfitAndLoss(
            company=company or self._client.settings.default_company,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            income_groups=sorted(income_groups, key=lambda g: g.group),
            expense_groups=sorted(expense_groups, key=lambda g: g.group),
            total_income=total_income,
            total_expense=total_expense,
            net_profit=round(total_income - total_expense, 2),
        )

    # -- balance sheet -----------------------------------------------------------

    def get_balance_sheet(self, company: str | None = None, as_of_date: date | None = None) -> BalanceSheet:
        asset_by_group: dict[str, list[TrialBalanceLine]] = {}
        liability_by_group: dict[str, list[TrialBalanceLine]] = {}

        for record, root in self._ledgers_with_roots(company):
            if root not in field_maps.BALANCE_SHEET_PRIMARY_GROUPS:
                continue
            ledger = ledger_from_record(record)
            amount = abs(ledger.closing_balance)
            line = TrialBalanceLine(
                ledger=ledger.name,
                group=ledger.group,
                debit=amount if ledger.closing_balance > 0 else 0.0,
                credit=amount if ledger.closing_balance < 0 else 0.0,
            )
            bucket = asset_by_group if root in field_maps.ASSET_SIDE_GROUPS else liability_by_group
            bucket.setdefault(root, []).append(line)

        asset_groups = [
            StatementGroup(group=g, amount=round(sum(x.credit + x.debit for x in lines), 2), ledgers=lines)
            for g, lines in asset_by_group.items()
        ]
        liability_groups = [
            StatementGroup(group=g, amount=round(sum(x.credit + x.debit for x in lines), 2), ledgers=lines)
            for g, lines in liability_by_group.items()
        ]
        total_assets = round(sum(g.amount for g in asset_groups), 2)
        total_liabilities = round(sum(g.amount for g in liability_groups), 2)
        return BalanceSheet(
            company=company or self._client.settings.default_company,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
            asset_groups=sorted(asset_groups, key=lambda g: g.group),
            liability_groups=sorted(liability_groups, key=lambda g: g.group),
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            difference=round(total_assets - total_liabilities, 2),
        )

    # -- receivables / payables ---------------------------------------------------

    def _party_outstanding(self, company: str | None, group_names: set[str]) -> list[PartyOutstanding]:
        results: list[PartyOutstanding] = []
        for record, root in self._ledgers_with_roots(company):
            group = field_text(record, "PARENT")
            if (root or "").strip().lower() not in group_names and (group or "").strip().lower() not in group_names:
                continue
            ledger = ledger_from_record(record)
            if ledger.closing_balance == 0:
                continue
            results.append(PartyOutstanding(party=ledger.name, balance=ledger.closing_balance))
        return sorted(results, key=lambda p: p.party)

    def get_receivables(self, company: str | None = None, as_of_date: date | None = None) -> ReceivablesReport:
        parties = self._party_outstanding(company, _RECEIVABLE_GROUPS)
        return ReceivablesReport(
            company=company or self._client.settings.default_company,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
            parties=parties,
            total_receivable=round(sum(max(p.balance, 0.0) for p in parties), 2),
        )

    def get_payables(self, company: str | None = None, as_of_date: date | None = None) -> PayablesReport:
        parties = self._party_outstanding(company, _PAYABLE_GROUPS)
        return PayablesReport(
            company=company or self._client.settings.default_company,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
            parties=parties,
            total_payable=round(sum(max(-p.balance, 0.0) for p in parties), 2),
        )
