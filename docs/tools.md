# Tools Reference

All tools below are **read-only** unless listed under
[Write tools](#write-tools-opt-in), which only exist when
`TALLY_READ_ONLY=false`. Dates are always ISO format `YYYY-MM-DD`. `company` is optional
on every tool if `TALLY_DEFAULT_COMPANY` is configured; otherwise it's
required (call `list_companies` first if you don't know the exact name).

## test_connection

Checks whether TallyPrime is reachable and responding.

**Parameters:** none.

**Returns:** `{connected: bool, message: str, host: str, port: int}`

Use this first whenever another tool fails unexpectedly — it isolates
"Tally isn't reachable at all" from "Tally is reachable but this specific
request failed."

## list_companies

Lists companies currently **loaded/open** in TallyPrime (not all companies
that exist on disk — see [tally-setup.md](tally-setup.md#multiple-companies)).

**Parameters:** none.

**Returns:** list of `{name, financial_year_from, books_from}`.

## list_ledgers

**Parameters:** `company` (optional), `search` (optional substring filter
on ledger or group name).

**Returns:** list of `{name, group, opening_balance, closing_balance, email, gstin}`.

Sign convention: positive = debit balance, negative = credit balance.

## get_ledger

**Parameters:** `ledger_name` (required, exact name), `company` (optional),
`from_date`, `to_date` (optional).

**Returns:** `{ledger, from_date, to_date, vouchers, total_debit, total_credit}`.

Transactions are found via the voucher collection filtered to this ledger's
party name — see "Design note: get_ledger's transaction list" below.

## search_vouchers

**Parameters:** `company`, `from_date`, `to_date`, `voucher_type` (exact
match, e.g. `"Receipt"`, `"Payment"`, `"Sales"`), `ledger` (substring match
against party ledger), `search_term` (substring match against all fields),
`limit` (default `TALLY_DEFAULT_VOUCHER_LIMIT`, currently 100).

**Returns:** list of `{date, voucher_number, voucher_type, party, amount, narration, reference}`.

## get_voucher

**Parameters:** `voucher_identifier` (voucher number), `company` (optional).

**Returns:** a single voucher, same shape as above. Raises if not found.

## get_trial_balance

**Parameters:** `company`, `from_date`, `to_date` (currently informational
only — see "Design note" below).

**Returns:** `{company, from_date, to_date, lines: [{ledger, group, debit, credit}], total_debit, total_credit}`.

`total_debit` should always equal `total_credit` for a company with
consistent books — if it doesn't, that's worth investigating (or reporting
as a bug here).

## get_profit_and_loss

**Parameters:** `company`, `from_date`, `to_date` (informational only).

**Returns:** `{company, from_date, to_date, income_groups, expense_groups, total_income, total_expense, net_profit}`,
where each group is `{group, amount, ledgers}`.

## get_balance_sheet

**Parameters:** `company`, `as_of_date` (informational only).

**Returns:** `{company, as_of_date, asset_groups, liability_groups, total_assets, total_liabilities, difference}`.

`difference` (assets − liabilities) will commonly be **non-zero** — see
"Design note" below for why, and don't treat it as a bug by itself.

## get_receivables / get_payables

**Parameters:** `company`, `as_of_date` (informational only).

**Returns:** `{company, as_of_date, parties: [{party, balance, overdue_by_days}], total_receivable}` (or `total_payable`).

`overdue_by_days` is currently always `null` — bill-wise due-date tracking
isn't implemented yet (see Roadmap in the README).

## list_stock_items / get_stock_summary

**Parameters:** `company`, `search` (list_stock_items only), `from_date`/`to_date` (get_stock_summary, informational only).

**Returns:** stock items with `{name, group, base_unit, opening_qty, opening_value, closing_qty, closing_value}`,
or an aggregate summary.

---

## Design note: how the financial statements are computed

TallyPrime's own "Trial Balance" / "Profit & Loss" / "Balance Sheet"
**canned reports** have on-screen-layout-specific XML export shapes that
vary by report configuration and TallyPrime version. This project's
development environment did not have a licensed TallyPrime installation to
capture and verify those exact shapes against (see README "Testing").

Rather than hard-code a guessed field layout for those canned reports and
risk silently wrong numbers, `get_trial_balance`, `get_profit_and_loss`,
and `get_balance_sheet` are **computed** by this project from two things
built on the well-documented, stable `Collection` export pattern (see
`tally/xml_builder.py`):

1. every ledger's closing balance, and
2. the ledger-group hierarchy, walked up to TallyPrime's fixed set of
   standard primary groups (`tally/field_maps.py`).

This is a textbook-correct way to derive these three statements from a
chart of accounts, and it's resilient to canned-report layout differences
across TallyPrime versions. It is, however, a **simplification**:

- **Date ranges are currently informational only.** Ledger closing
  balances reflect TallyPrime's *current* state, not a reconstruction as
  of a specific historical date. A true point-in-time trial balance would
  need to replay vouchers up to `to_date`, which isn't implemented yet.
- **Balance Sheet's `difference` will often be non-zero.** A textbook
  balance sheet balances only once the current period's P&L is closed
  into a balancing "Profit & Loss A/c" equity line — this simplified
  computation does not perform that closing entry. `difference` is
  reported explicitly (rather than hidden) so it's visible, not silently
  wrong.
- **Schedule-style sub-groupings** (e.g. India's Schedule III balance
  sheet format) aren't reproduced — ledgers are grouped only by their
  ultimate standard primary group.

If you have a real TallyPrime installation and want to help replace this
with a verified canned-report export, see
[CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-new-tally-report--mcp-tool).

## Design note: get_ledger's transaction list

TallyPrime's per-ledger "Ledger Vouchers" view is normally its own report
type. Rather than depend on that report's specific export shape (same
verification gap as above), `get_ledger` fetches vouchers via the general
voucher collection and filters by party ledger name client-side. This
means a voucher will only show up in a ledger's statement if that ledger
is recorded as the voucher's `PARTYLEDGERNAME` — multi-ledger journal
entries that touch a ledger without it being the "party" may not appear.
This is a known gap tracked for improvement.

## Write tools (opt-in)

Registered only when `TALLY_READ_ONLY=false`. Every write is two-step:
`create_*` returns a preview and writes nothing; `confirm_write` performs
it. Writes require an explicit company (`company` or
`TALLY_DEFAULT_COMPANY`), which must be loaded in TallyPrime.

### create_ledger

**Parameters:** `name`, `parent_group`, `company`, `opening_balance`
(optional, positive), `opening_balance_side` (`"debit"` | `"credit"`,
default `"debit"`).

Rejected if the ledger already exists or the group doesn't.

### create_voucher

**Parameters:** `voucher_type` (e.g. `"Payment"`, `"Receipt"`, `"Journal"`,
`"Contra"`, `"Sales"`, `"Purchase"`), `date` (`YYYY-MM-DD`), `entries`
(two or more `{ledger, side, amount}`), `company`, `narration`,
`voucher_number`, `reference`, `party_ledger` — all optional except the
first three.

Debits must equal credits, and every ledger must already exist. Vouchers
are created in Accounting Voucher View; inventory lines (stock items,
quantities, rates) aren't supported yet.

### Preview response

`{confirmation_id, operation, company, summary, details, expires_at, status: "pending_confirmation", next_step}`

### confirm_write

**Parameters:** `confirmation_id`.

**Returns:** `{confirmation_id, operation, company, status: "committed", summary, created, altered, tally_voucher_id, tally_master_id}`.
Fails with Tally's own error text (e.g. an unknown voucher type) if Tally
rejects the import. Each id works once and expires after
`TALLY_WRITE_CONFIRMATION_TTL_SECONDS`.

### cancel_write

**Parameters:** `confirmation_id`. Discards the proposal; nothing is sent.

> **Verify against a live instance:** the import XML follows Tally's
> documented `Import Data` format (debits as negative `AMOUNT` with
> `ISDEEMEDPOSITIVE=Yes`), but like the read side it hasn't yet been run
> against a real TallyPrime. Try it on a test company first.
