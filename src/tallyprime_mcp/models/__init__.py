"""Pydantic domain models returned by TallyPrime MCP tools.

These are the shapes AI clients actually see — plain, consistently-named
JSON, never raw Tally XML tags, with amounts as numbers (not formatted
strings) and dates as ISO ``YYYY-MM-DD`` strings.
"""

from __future__ import annotations

from tallyprime_mcp.models.company import Company, ConnectionStatus
from tallyprime_mcp.models.inventory import StockItem, StockSummary
from tallyprime_mcp.models.ledger import Ledger, LedgerDetail
from tallyprime_mcp.models.reports import (
    BalanceSheet,
    PayablesReport,
    ProfitAndLoss,
    ReceivablesReport,
    TrialBalance,
    TrialBalanceLine,
)
from tallyprime_mcp.models.voucher import Voucher

__all__ = [
    "Company",
    "ConnectionStatus",
    "Ledger",
    "LedgerDetail",
    "Voucher",
    "StockItem",
    "StockSummary",
    "TrialBalance",
    "TrialBalanceLine",
    "ProfitAndLoss",
    "BalanceSheet",
    "ReceivablesReport",
    "PayablesReport",
]
