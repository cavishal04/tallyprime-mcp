# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Opt-in write support, enabled with `TALLY_READ_ONLY=false` (default remains read-only). Adds `create_ledger` and `create_voucher` (accounting vouchers from balanced debit/credit lines), which only propose a change and return a preview, plus `confirm_write` and `cancel_write`.
- Writes are validated against the live company before preview (company loaded, ledgers/groups exist, no duplicate ledger, debits equal credits), are single-use and expire after `TALLY_WRITE_CONFIRMATION_TTL_SECONDS` (default 600), send exactly the previewed XML, and are audit-logged at every step.
- `Import Data` XML builders and an import-result parser that surfaces Tally's `LINEERROR`/error counters.

### Changed

- `WritePermission.check()` now allows `create_ledger` and `create_voucher` when `read_only` is false; every other operation is still denied.

## [0.1.0] - Unreleased

Initial alpha release.

### Added

- Read-only MCP server exposing 13 tools against a local TallyPrime installation: `test_connection`, `list_companies`, `list_ledgers`, `get_ledger`, `search_vouchers`, `get_voucher`, `get_trial_balance`, `get_profit_and_loss`, `get_balance_sheet`, `get_receivables`, `get_payables`, `list_stock_items`, `get_stock_summary`.
- Two MCP resources (`tally://companies`, `tally://config`) and three MCP prompt templates.
- TallyPrime HTTP-XML client built on the documented `Export`/`Collection` request pattern, with safe (`defusedxml`-based) response parsing.
- Pydantic-based configuration via environment variables / `.env`, with no hard-coded host, port, company, or credentials.
- Local-only structured logging with secret redaction.
- Deny-by-default write-permission gate and confirmation-workflow scaffolding for future write operations (no write operations are implemented in this release).
- `tallyprime-mcp` CLI (`run` [default], `test-connection`, `config`, `--version`).
- 98 unit tests against hand-built mock XML fixtures; integration test scaffolding for a real TallyPrime instance (skipped by default — see README "Testing").
- GitHub Actions CI (lint, test, build), issue templates, PR template.
- Full documentation set under `docs/`, plus example MCP client configs for Claude Desktop, Cursor, and generic clients.

### Known limitations (see README/SECURITY for detail)

- XML request/response field names for reports have not been verified against a real, running TallyPrime installation — see README "Testing".
- `get_trial_balance`, `get_profit_and_loss`, and `get_balance_sheet` are computed from ledger + group master data rather than exported from TallyPrime's own canned report XML, as a deliberate, documented design choice — see `docs/tools.md`.
- No write operations of any kind.

[0.1.0]: https://github.com/cavishal04/tallyprime-mcp/releases/tag/v0.1.0
