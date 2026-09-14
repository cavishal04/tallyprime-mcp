from __future__ import annotations

from pydantic import BaseModel, Field


class Voucher(BaseModel):
    """A single accounting voucher (invoice, receipt, payment, journal, ...)."""

    date: str | None = Field(default=None, description="ISO YYYY-MM-DD if Tally's date could be parsed.")
    voucher_number: str | None = None
    voucher_type: str | None = None
    party: str | None = None
    amount: float = 0.0
    narration: str | None = None
    reference: str | None = None
