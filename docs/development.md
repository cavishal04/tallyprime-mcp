# Development Guide

## Setup

```bash
git clone https://github.com/cavishal04/tallyprime-mcp.git
cd tallyprime-mcp
python -m venv .venv
source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

This installs the package in editable mode plus dev dependencies: `pytest`,
`pytest-asyncio`, `pytest-cov`, `respx` (HTTP mocking), and `ruff`.

## Project layout

See the architecture section of the [README](../README.md#architecture).
The layering rule of thumb:

- `tally/` — knows how to talk to TallyPrime's HTTP-XML protocol. Returns
  loosely-typed `TallyRecord` objects. No Pydantic here, no MCP here.
- `models/` — Pydantic shapes for what MCP tools actually return. No
  Tally-specific logic here.
- `services/` — maps `TallyRecord` → `models`. This is where business
  logic (like the trial balance / P&L / balance sheet computation) lives.
- `mcp/` — registers tools/resources/prompts on a `FastMCP` instance,
  translating parameters and catching errors. Thin — delegates to
  `services/` for anything non-trivial.
- `security/` — the write-permission gate and audit logging. Nothing here
  talks to Tally directly.

Keeping these separate means you can, for example, test the entire trial
balance computation (`tests/unit/test_services.py`) without spinning up
any MCP machinery, and test the MCP tool wiring (`tests/unit/test_tools.py`)
without needing real report-computation logic to be correct — a fake
connection returning canned fixtures is enough for both.

## Running checks locally

```bash
ruff check src tests          # lint
pytest                         # unit tests (fast, no network/Tally needed)
pytest --cov=src/tallyprime_mcp --cov-report=term-missing  # with coverage
python -m build                # verify the package builds
```

These are exactly what CI runs (`.github/workflows/ci.yml`) — if they pass
locally, CI should pass too.

## Running integration tests (requires real TallyPrime)

```bash
TALLYPRIME_MCP_RUN_INTEGRATION=1 pytest tests/integration -v
```

These are skipped otherwise (including in CI). See
[tests/integration/test_real_tally.py](../tests/integration/test_real_tally.py)
for what they check and why they're separated from the unit test suite.

## Adding a mock fixture

Fixtures live in `tests/fixtures/xml/`. Every fixture file should have a
comment at the top stating clearly that it's a hand-built mock (unless it
was genuinely captured from a real Tally instance, in which case say that
instead, and note the TallyPrime version it came from). See existing
fixtures for the format.

## Debugging a field-mapping issue against real Tally

If you have TallyPrime available and a tool's output looks wrong:

1. Temporarily set `TALLY_EXPOSE_RAW_XML_TOOL=true` and restart the server.
2. Call the new `debug_raw_xml` tool with the relevant `kind`
   (`companies`, `ledgers`, `vouchers`, `groups`, `stock_items`) to see
   exactly what TallyPrime returned.
3. Compare against the field names expected in `tally/field_maps.py` and
   the parsing logic in `services/`.
4. Fix the field map (adding the correct name as an additional candidate
   rather than replacing an existing one, unless you're sure it's simply
   wrong everywhere — see [CONTRIBUTING.md](../CONTRIBUTING.md)).
5. **Turn `TALLY_EXPOSE_RAW_XML_TOOL` back off** once done — see
   [SECURITY.md](../SECURITY.md#known-limitations).

## Releasing

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/tallyprime_mcp/__init__.py`.
2. Move the `[Unreleased]` section of `CHANGELOG.md` to a dated version
   heading and add a fresh `[Unreleased]` section above it.
3. Tag the release (`git tag vX.Y.Z`) — CI publishes on tag push (see the
   `publish` job in `.github/workflows/ci.yml`, currently commented out
   until the project has a PyPI trusted-publisher configured).
