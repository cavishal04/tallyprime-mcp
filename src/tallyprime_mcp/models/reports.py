from __future__ import annotations

from pydantic import BaseModel, Field


class TrialBalanceLine(BaseModel):
    ledger: str
    group: str | None = None
    debit: float = 0.0
    credit: float = 0.0


class TrialBalance(BaseModel):
    company: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    lines: list[TrialBalanceLine] = Field(default_factory=list)
    total_debit: float = 0.0
    total_credit: float = 0.0


class StatementGroup(BaseModel):
    """One classification group (e.g. 'Direct Incomes') within a P&L or
    Balance Sheet, with the ledgers rolled up under it."""

    group: str
    amount: float = 0.0
    ledgers: list[TrialBalanceLine] = Field(default_factory=list)


class ProfitAndLoss(BaseModel):
    company: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    income_groups: list[StatementGroup] = Field(default_factory=list)
    expense_groups: list[StatementGroup] = Field(default_factory=list)
    total_income: float = 0.0
    total_expense: float = 0.0
    net_profit: float = 0.0


class BalanceSheet(BaseModel):
    company: str | None = None
    as_of_date: str | None = None
    asset_groups: list[StatementGroup] = Field(default_factory=list)
    liability_groups: list[StatementGroup] = Field(default_factory=list)
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    difference: float = Field(
        default=0.0,
        description="total_assets - total_liabilities. Non-zero commonly indicates the "
        "current period's profit/loss has not been separately classified into a "
        "'Profit & Loss A/c' style balancing ledger by this simplified computation; "
        "see docs/tools.md.",
    )


class PartyOutstanding(BaseModel):
    party: str
    balance: float = 0.0
    overdue_by_days: int | None = None


class ReceivablesReport(BaseModel):
    company: str | None = None
    as_of_date: str | None = None
    parties: list[PartyOutstanding] = Field(default_factory=list)
    total_receivable: float = 0.0


class PayablesReport(BaseModel):
    company: str | None = None
    as_of_date: str | None = None
    parties: list[PartyOutstanding] = Field(default_factory=list)
    total_payable: float = 0.0
