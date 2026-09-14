from __future__ import annotations

from pydantic import BaseModel, Field


class StockItem(BaseModel):
    """A stock (inventory) item master record."""

    name: str
    group: str | None = None
    base_unit: str | None = None
    opening_qty: float = 0.0
    opening_value: float = 0.0
    closing_qty: float = 0.0
    closing_value: float = 0.0


class StockSummary(BaseModel):
    """Aggregate stock position for a company over a date range."""

    from_date: str | None = None
    to_date: str | None = None
    items: list[StockItem] = Field(default_factory=list)
    total_closing_value: float = 0.0
