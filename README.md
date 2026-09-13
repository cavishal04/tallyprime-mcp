# TallyPrime MCP

**Read-only [MCP](https://modelcontextprotocol.io) server that lets AI assistants (Claude Desktop, Cursor, and other MCP clients) query a TallyPrime installation running on your own computer.**

Everything stays local: this server talks to TallyPrime's HTTP-XML gateway on `127.0.0.1`, and it never sends your accounting data to any server operated by this project.

> **Status: v0.1.0, early alpha.** The XML request/response shapes are built from TallyPrime's own published integration documentation, but have **not yet been verified against a real, running TallyPrime installation** in this project's own development environment. See [Testing](#testing) below for exactly what has and hasn't been confirmed, and please [open an issue](https://github.com/cavishal04/tallyprime-mcp/issues) with your TallyPrime version if something doesn't match.

---

## Features

- **13 read-only tools** covering companies, ledgers, vouchers, trial balance, P&L, balance sheet, receivables, payables, and stock/inventory.
- **Nothing can write to Tally.** There is no `execute_tally_xml`-style escape hatch, and no tool can create, edit, or delete anything — see [Security](#security).
- **Runs entirely on your machine.** No cloud account, no API keys, no external server.
- **Clean, typed, consistent JSON** — never raw Tally XML tag soup — with amounts as numbers and dates as `YYYY-MM-DD`.
- **Configurable, not hard-coded.** Host, port, timeouts, default company, and limits are all environment-variable driven.

## Architecture

```mermaid
flowchart LR
    A[AI Client<br/>Claude Desktop / Cursor / etc.] -->|MCP protocol, stdio| B[TallyPrime MCP Server]
    B -->|Local HTTP + XML| C[TallyPrime<br/>HTTP-XML Gateway]
    C --> D[(Local Accounting Data)]
```

The server is organized as:

```
tallyprime_mcp/
├── tally/       # HTTP transport, XML request building/parsing, custom exceptions
├── models/      # Pydantic response shapes (Company, Ledger, Voucher, reports, ...)
├── services/    # Maps raw Tally data onto the models above
├── security/    # Write-permission gate (deny-by-default), audit logging
├── mcp/         # MCP tool / resource / prompt registration
├── server.py    # Wires it all together into a FastMCP app
└── cli.py       # `tallyprime-mcp` command-line entry point
```

## Requirements

- **TallyPrime**, running on Windows (the normal deployment target — Linux/macOS work for *development* of this server, but TallyPrime itself is a Windows product), with the HTTP-XML gateway enabled and a company loaded.
- **Python 3.11+**
- This server and TallyPrime should run on the same machine, or at least the same trusted local network — see [Security](#security) before doing the latter.

## Installation

**If you've never used Python before:** see [docs/installation.md](docs/installation.md) for a step-by-step, no-assumptions walkthrough.

**If you're comfortable with Python:**

```bash
pip install tallyprime-mcp
```

or, from source:

```bash
git clone https://github.com/cavishal04/tallyprime-mcp.git
cd tallyprime-mcp
pip install -e ".[dev]"
```

## TallyPrime configuration

You need TallyPrime's HTTP-XML gateway switched on and listening (default `9000`) with the company you want to query open. Exact menu paths vary by TallyPrime release — see [docs/tally-setup.md](docs/tally-setup.md) for current instructions and screenshots-in-words.

## Running the server

```bash
tallyprime-mcp
```

This starts the MCP server over stdio, which is what Claude Desktop, Cursor, and similar clients expect for a locally-run tool. You won't see much on screen — that's expected; it's waiting for an MCP client to connect.

Check connectivity first if you're not sure Tally is reachable:

```bash
tallyprime-mcp test-connection
```

## Configuration

All configuration is via environment variables (or a `.env` file in the working directory — see [.env.example](.env.example)):

| Variable | Default | Meaning |
|---|---|---|
| `TALLY_HOST` | `127.0.0.1` | Where TallyPrime's HTTP-XML gateway is listening |
| `TALLY_PORT` | `9000` | Gateway port |
| `TALLY_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `TALLY_DEFAULT_COMPANY` | *(none)* | Company to use when a tool call doesn't specify one |
| `TALLY_READ_ONLY` | `true` | Always `true` in this release — see [Security](#security) |
| `TALLY_LOG_LEVEL` | `INFO` | Python logging level |
| `TALLY_LOG_DIR` | *(none — stderr only)* | Directory for rotating log files |

Full list: [docs/configuration.md](docs/configuration.md).

## MCP client configuration

- **Claude Desktop** — [examples/claude](examples/claude)
- **Cursor** — [examples/cursor](examples/cursor)
- **Any other MCP client** — [examples/generic](examples/generic)

Full walkthrough: [docs/mcp-clients.md](docs/mcp-clients.md).

## Available tools

| Tool | Purpose |
|---|---|
| `test_connection` | Check TallyPrime is reachable |
| `list_companies` | List loaded companies |
| `list_ledgers` | List ledgers with balances |
| `get_ledger` | One ledger's master data + transactions in a date range |
| `search_vouchers` | Search vouchers by date/type/party/text |
| `get_voucher` | One voucher by number |
| `get_trial_balance` | Every ledger's debit/credit closing balance |
| `get_profit_and_loss` | Simplified P&L by primary group |
| `get_balance_sheet` | Simplified Balance Sheet by primary group |
| `get_receivables` | Outstanding Sundry Debtors |
| `get_payables` | Outstanding Sundry Creditors |
| `list_stock_items` | Inventory items with quantities/values |
| `get_stock_summary` | Aggregate stock position |

Full parameter reference: [docs/tools.md](docs/tools.md) (this is also where the trial-balance/P&L/balance-sheet **design tradeoffs** are explained — read it before relying on those three for anything important).

## Example AI interaction

> **User:** "Show me the trial balance for April 2026."
>
> **AI:** *calls `get_trial_balance(from_date="2026-04-01", to_date="2026-04-30")`*
>
> **TallyPrime MCP:** queries the local TallyPrime installation, returns structured ledger balances
>
> **AI:** "Here's the trial balance — total debits and credits both come to ₹18,42,000. The largest debit balances are HDFC Bank (₹6,10,000) and..."

## Security

Read [SECURITY.md](SECURITY.md) for the full threat model. In short:

- Every tool is **read-only**. No tool can create, modify, or delete Tally data.
- There is **no generic XML-execution tool**.
- The server binds to `127.0.0.1` by default and is never meant to be exposed to the internet.
- All input is validated (dates, limits, request size) before being sent to Tally.
- Nothing is logged that shouldn't be (see `logging_config.py`'s redaction filter).

## Privacy

- TallyPrime MCP runs **entirely on your computer**. There is no cloud backend.
- This project's maintainers do not receive, store, or have access to your accounting data, in any form.
- **This is distinct from your AI client's own privacy policy.** Once TallyPrime MCP hands data to your AI assistant (Claude Desktop, Cursor, etc.) inside your local MCP session, that data is subject to *that product's* privacy practices, not this project's — check your AI client's documentation for how it handles data sent to it.

## Development

```bash
git clone https://github.com/cavishal04/tallyprime-mcp.git
cd tallyprime-mcp
pip install -e ".[dev]"
ruff check src tests
pytest
```

See [docs/development.md](docs/development.md) for the full contributor setup.

## Testing

- **Unit tests** (98 at last count) run against hand-built mock XML fixtures shaped to match TallyPrime's documented request/response patterns — they verify this project's own request-building, parsing, and business logic, but **do not** verify that a real TallyPrime installation responds exactly this way.
- **Integration tests** (`tests/integration/`) are written to run against a real, locally-running TallyPrime instance, but are **skipped by default** (including in CI) because no TallyPrime installation was available in this project's development environment. Run them yourself with `TALLYPRIME_MCP_RUN_INTEGRATION=1 pytest tests/integration -v` once you have TallyPrime open locally, and please report back via an issue with what did/didn't work for your version.

If you *do* have TallyPrime available and something in `tools.md`'s "verify against a live instance" notes turns out wrong, a bug report (or PR) with the corrected field name is one of the most valuable contributions you can make right now.

## Contributing

Contributions are very welcome — see [CONTRIBUTING.md](CONTRIBUTING.md), especially if you have a real TallyPrime installation to test against. [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) applies to all project spaces.

## Roadmap

- [ ] Verify all XML field names against a real TallyPrime installation (multiple versions)
- [ ] Write operations (`create_payment`, `create_receipt`, `create_sales_voucher`, ...), gated behind the confirmation workflow already scaffolded in `security/confirmation.py` — **not started**, and will not ship without explicit user confirmation per write
- [ ] Cost centre / godown-aware reporting
- [ ] GST-specific reports
- [ ] Optional local caching layer for large ledgers

## License

Apache License 2.0 — see [LICENSE](LICENSE). Apache-2.0 was chosen (over MIT) for its explicit patent grant, which feels appropriate for a project that talks to commercial accounting software and may attract contributions from companies as well as individuals.

This project contains no TallyPrime source code and no copied Tally Solutions documentation — only original code written against publicly available integration documentation.

---

*TallyPrime is a product of Tally Solutions Pvt. Ltd. This is an independent, community open-source project and is not affiliated with, endorsed by, or sponsored by Tally Solutions.*
