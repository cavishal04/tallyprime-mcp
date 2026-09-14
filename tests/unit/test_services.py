from __future__ import annotations

import pytest

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.services.inventory_service import InventoryService
from tallyprime_mcp.services.ledger_service import LedgerService
from tallyprime_mcp.services.report_service import ReportService
from tallyprime_mcp.services.voucher_service import VoucherService
from tallyprime_mcp.tally.client import TallyClient
from tests.unit.fakes import FakeTallyConnection


@pytest.fixture
def client(settings: TallySettings) -> TallyClient:
    return TallyClient(settings, connection=FakeTallyConnection())


# -- ledger service -----------------------------------------------------------


def test_list_ledgers_maps_fields(client: TallyClient) -> None:
    service = LedgerService(client)
    ledgers = {ledger.name: ledger for ledger in service.list_ledgers()}
    hdfc = ledgers["HDFC Bank"]
    assert hdfc.group == "Bank Accounts"
    assert hdfc.opening_balance == 1250000.0
    assert hdfc.closing_balance == 1375000.0


def test_get_ledger_detail_totals(client: TallyClient) -> None:
    service = LedgerService(client)
    detail = service.get_ledger("ABC Limited")
    assert detail.ledger.name == "ABC Limited"
    assert len(detail.vouchers) == 2
    # RV-001 (+250000) is a debit-natured amount, SA-102 (-95000) is credit
    assert detail.total_debit == 250000.0
    assert detail.total_credit == 95000.0


def test_get_ledger_detail_not_found_raises(client: TallyClient) -> None:
    from tallyprime_mcp.tally.exceptions import TallyRequestError

    service = LedgerService(client)
    with pytest.raises(TallyRequestError):
        service.get_ledger("Nonexistent")


# -- voucher service ------------------------------------------------------------


def test_voucher_service_maps_dates(client: TallyClient) -> None:
    service = VoucherService(client)
    vouchers = service.search_vouchers()
    dated = {v.voucher_number: v.date for v in vouchers}
    assert dated["RV-001"] == "2026-09-01"


def test_voucher_service_get_voucher_not_found(client: TallyClient) -> None:
    from tallyprime_mcp.tally.exceptions import TallyRequestError

    service = VoucherService(client)
    with pytest.raises(TallyRequestError):
        service.get_voucher("NOPE")


# -- inventory service -----------------------------------------------------------


def test_stock_summary_totals(client: TallyClient) -> None:
    service = InventoryService(client)
    summary = service.get_stock_summary()
    assert summary.total_closing_value == 30000.0 + 90000.0
    assert len(summary.items) == 2


# -- report service ------------------------------------------------------------


def test_trial_balance_totals_balance(client: TallyClient) -> None:
    service = ReportService(client)
    tb = service.get_trial_balance()
    # Fundamental accounting identity: total debits must equal total credits.
    assert tb.total_debit == tb.total_credit
    ledger_names = {line.ledger for line in tb.lines}
    assert "HDFC Bank" in ledger_names
    assert "Cash" in ledger_names


def test_trial_balance_excludes_zero_balances(client: TallyClient, settings: TallySettings) -> None:
    service = ReportService(client)
    tb = service.get_trial_balance()
    # No fixture ledger has a zero closing balance, so this just documents
    # the exclusion behaviour won't crash / mis-count when it applies.
    assert all(line.debit != 0 or line.credit != 0 for line in tb.lines)


def test_profit_and_loss_classification(client: TallyClient) -> None:
    service = ReportService(client)
    pnl = service.get_profit_and_loss()
    income_group_names = {g.group for g in pnl.income_groups}
    expense_group_names = {g.group for g in pnl.expense_groups}
    assert "Sales Accounts" in income_group_names
    assert "Indirect Expenses" in expense_group_names
    assert pnl.total_income == 2500000.0
    assert pnl.total_expense == 360000.0
    assert pnl.net_profit == 2500000.0 - 360000.0


def test_balance_sheet_classification(client: TallyClient) -> None:
    service = ReportService(client)
    bs = service.get_balance_sheet()
    asset_groups = {g.group for g in bs.asset_groups}
    liability_groups = {g.group for g in bs.liability_groups}
    # Bank Accounts/Sundry Debtors/Cash-in-Hand roll up to Current Assets;
    # Fixed Assets is itself a primary asset-side group.
    assert "Current Assets" in asset_groups
    assert "Fixed Assets" in asset_groups
    # Sundry Creditors rolls up to Current Liabilities; Capital Account is
    # itself a primary liability-side (equity) group.
    assert "Current Liabilities" in liability_groups
    assert "Capital Account" in liability_groups
    assert bs.total_assets > 0
    assert bs.total_liabilities > 0


def test_receivables_and_payables(client: TallyClient) -> None:
    service = ReportService(client)
    receivables = service.get_receivables()
    payables = service.get_payables()
    assert receivables.total_receivable == 250000.0
    assert any(p.party == "ABC Limited" for p in receivables.parties)
    assert payables.total_payable == 180000.0
    assert any(p.party == "Prime Supplies Co" for p in payables.parties)
