from __future__ import annotations

from pydantic import BaseModel, Field

from tallyprime_mcp.models.voucher import Voucher


class Ledger(BaseModel):
    """A ledger master record."""

    name: str
    group: str | None = Field(default=None, description="Parent ledger group name.")
    opening_balance: float = Field(default=0.0, description="Positive = debit, negative = credit.")
    closing_balance: float = Field(default=0.0, description="Positive = debit, negative = credit.")
    email: str | None = None
    gstin: str | None = None


class LedgerDetail(BaseModel):
    """A ledger with its transactions in a given date range."""

    ledger: Ledger
    from_date: str | None = None
    to_date: str | None = None
    vouchers: list[Voucher] = Field(default_factory=list)
    total_debit: float = 0.0
    total_credit: float = 0.0
