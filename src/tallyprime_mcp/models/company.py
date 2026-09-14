from __future__ import annotations

from pydantic import BaseModel, Field


class Company(BaseModel):
    """A company loaded/available in TallyPrime."""

    name: str = Field(description="Company name as recorded in TallyPrime.")
    financial_year_from: str | None = Field(
        default=None, description="Start date of the current books, ISO YYYY-MM-DD if known."
    )
    books_from: str | None = Field(
        default=None, description="Books-maintained-from date, ISO YYYY-MM-DD if known."
    )


class ConnectionStatus(BaseModel):
    """Result of :meth:`tallyprime_mcp.tally.client.TallyClient.test_connection`."""

    connected: bool
    message: str
    host: str
    port: int
