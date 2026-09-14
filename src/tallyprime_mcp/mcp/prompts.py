"""Reusable MCP prompt templates for common TallyPrime questions.

These are convenience starting points for MCP clients that support prompt
templates — they don't do anything a user couldn't do by typing the
equivalent question, but they save typing for common report requests and
nudge the assistant toward calling the right tool with the right
parameters.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    @mcp.prompt()
    def trial_balance_report(company: str = "", from_date: str = "", to_date: str = "") -> str:
        """Ask for a trial balance for a company and date range."""
        scope = f" for {company}" if company else ""
        period = f" from {from_date} to {to_date}" if from_date and to_date else ""
        return (
            f"Get the trial balance{scope}{period} using the get_trial_balance tool, "
            "then summarise which ledgers have the largest debit and credit balances."
        )

    @mcp.prompt()
    def cash_position_check(company: str = "") -> str:
        """Ask for a quick summary of receivables vs payables."""
        scope = f" for {company}" if company else ""
        return (
            f"Using get_receivables and get_payables{scope}, summarise total amounts "
            "receivable and payable, and list the five largest outstanding parties on "
            "each side."
        )

    @mcp.prompt()
    def ledger_statement(ledger_name: str = "", company: str = "", from_date: str = "", to_date: str = "") -> str:
        """Ask for a specific ledger's statement over a date range."""
        scope = f" in {company}" if company else ""
        period = f" from {from_date} to {to_date}" if from_date and to_date else ""
        return (
            f"Get the ledger statement for '{ledger_name}'{scope}{period} using the "
            "get_ledger tool, then summarise the transactions and closing balance."
        )
