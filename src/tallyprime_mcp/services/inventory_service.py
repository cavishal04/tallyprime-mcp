from __future__ import annotations

from datetime import date

from tallyprime_mcp.models.inventory import StockItem, StockSummary
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.xml_parser import TallyRecord, field_amount, field_text


def _to_stock_item(record: TallyRecord) -> StockItem:
    return StockItem(
        name=record.name or field_text(record, "NAME"),
        group=field_text(record, "PARENT") or None,
        base_unit=field_text(record, "BASEUNITS") or None,
        opening_qty=field_amount(record, "OPENINGBALANCE"),
        opening_value=field_amount(record, "OPENINGVALUE"),
        closing_qty=field_amount(record, "CLOSINGBALANCE"),
        closing_value=field_amount(record, "CLOSINGVALUE"),
    )


class InventoryService:
    def __init__(self, client: TallyClient) -> None:
        self._client = client

    def list_stock_items(self, company: str | None = None, search: str | None = None) -> list[StockItem]:
        records = self._client.list_stock_items(company=company, search=search)
        return [_to_stock_item(r) for r in records if (r.name or field_text(r, "NAME"))]

    def get_stock_summary(
        self,
        company: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> StockSummary:
        items = self.list_stock_items(company=company)
        return StockSummary(
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            items=items,
            total_closing_value=sum(item.closing_value for item in items),
        )
