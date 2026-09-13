"""Native TallyPrime field names, grouped by object type.

Kept in one module, separate from request-building and parsing logic, so
that when a field name is confirmed wrong (or missing) against a real
TallyPrime installation, fixing it means editing a list here rather than
hunting through request-building code.

Each object lists the fields this project *requests* via ``FETCH`` and the
*candidate* names :func:`tallyprime_mcp.tally.xml_parser.field_text` will
accept when reading the response, since Tally has used more than one name
for some concepts (e.g. plain closing balance vs. the ``CLOSINGBALANCE``
computed field) across versions/report contexts.
"""

from __future__ import annotations

LEDGER_FETCH_FIELDS: list[str] = [
    "NAME",
    "PARENT",
    "OPENINGBALANCE",
    "CLOSINGBALANCE",
    "ISBILLWISEON",
    "ISCOSTCENTRESON",
    "LEDGERPHONE",
    "LEDGERMOBILE",
    "EMAIL",
    "GSTIN",
]

GROUP_FETCH_FIELDS: list[str] = [
    "NAME",
    "PARENT",
    "ISDEEMEDPOSITIVE",
    "ISREVENUE",
]

VOUCHER_FETCH_FIELDS: list[str] = [
    "DATE",
    "VOUCHERNUMBER",
    "VOUCHERTYPENAME",
    "PARTYLEDGERNAME",
    "NARRATION",
    "REFERENCE",
    "AMOUNT",
]

STOCK_ITEM_FETCH_FIELDS: list[str] = [
    "NAME",
    "PARENT",
    "BASEUNITS",
    "OPENINGBALANCE",
    "OPENINGVALUE",
    "CLOSINGBALANCE",
    "CLOSINGVALUE",
]

# Standard TallyPrime *primary* groups. These names are part of Tally's
# built-in chart-of-accounts taxonomy (documented, public product behaviour)
# and are used only to classify a ledger's ultimate parent group as
# belonging to the Balance Sheet or the Profit & Loss statement — this is
# static accounting-software knowledge, not a guess about any specific
# user's data.
BALANCE_SHEET_PRIMARY_GROUPS: set[str] = {
    "Capital Account",
    "Loans (Liability)",
    "Current Liabilities",
    "Fixed Assets",
    "Investments",
    "Current Assets",
    "Branch / Divisions",
    "Misc. Expenses (ASSET)",
    "Suspense A/c",
}

PROFIT_AND_LOSS_PRIMARY_GROUPS: set[str] = {
    "Sales Accounts",
    "Purchase Accounts",
    "Direct Incomes",
    "Indirect Incomes",
    "Direct Expenses",
    "Indirect Expenses",
}

# Groups conventionally shown as "asset side" / debit-natured for display
# purposes, used only for sign presentation, not for any authoritative
# accounting determination.
ASSET_SIDE_GROUPS: set[str] = {
    "Fixed Assets",
    "Investments",
    "Current Assets",
    "Misc. Expenses (ASSET)",
    "Branch / Divisions",
}
