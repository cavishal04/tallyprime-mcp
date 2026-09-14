from __future__ import annotations

from tallyprime_mcp.models.company import Company, ConnectionStatus
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.xml_parser import field_text, parse_tally_date


class CompanyService:
    def __init__(self, client: TallyClient) -> None:
        self._client = client

    def test_connection(self) -> ConnectionStatus:
        ok, message = self._client.test_connection()
        settings = self._client.settings
        return ConnectionStatus(connected=ok, message=message, host=settings.host, port=settings.port)

    def list_companies(self) -> list[Company]:
        records = self._client.list_companies()
        companies: list[Company] = []
        for record in records:
            name = record.name or field_text(record, "NAME")
            if not name:
                continue
            companies.append(
                Company(
                    name=name,
                    financial_year_from=parse_tally_date(field_text(record, "STARTINGFROM")),
                    books_from=parse_tally_date(field_text(record, "BOOKSFROM")),
                )
            )
        return companies
