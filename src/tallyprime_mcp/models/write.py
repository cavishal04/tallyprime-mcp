from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class VoucherEntry(BaseModel):
    """One debit or credit line of a voucher."""

    model_config = ConfigDict(extra="forbid")

    ledger: str = Field(min_length=1, description="Exact ledger name as it appears in TallyPrime.")
    amount: Decimal = Field(
        gt=0, decimal_places=2, description="Positive amount, at most 2 decimals."
    )
    side: Literal["debit", "credit"]


class WritePreview(BaseModel):
    """Returned by a write tool: what *would* be written. Nothing has been
    sent to TallyPrime yet."""

    confirmation_id: str
    operation: str
    company: str
    summary: str
    details: dict[str, Any]
    expires_at: str
    status: str = "pending_confirmation"
    next_step: str = (
        "Show this preview to the user. Only after they explicitly approve it, call "
        "confirm_write with this confirmation_id. Call cancel_write to discard it."
    )


class WriteResult(BaseModel):
    """Outcome of a confirmed write."""

    confirmation_id: str
    operation: str
    company: str
    status: str
    summary: str
    created: int = 0
    altered: int = 0
    tally_voucher_id: str | None = None
    tally_master_id: str | None = None
