# Contributing to TallyPrime MCP

Thank you for considering a contribution! This project especially benefits from people who have a **real TallyPrime installation** to test against, since the maintainers' own development environment does not have one — see [README.md#testing](README.md#testing).

## Ways to contribute

- **Verify/fix XML field names or response shapes** against a real TallyPrime instance. This is currently the single most valuable kind of contribution — see "Good first issues" below.
- **New MCP tools** for reports/data not yet covered (cost centres, godowns, GST reports, ...).
- **New parsers** for report shapes this project doesn't handle yet.
- **Tests** — more mock fixtures covering edge cases (empty companies, unusual ledger hierarchies, multi-currency, etc.).
- **Documentation** — especially the non-technical installation guide; if something confused you as a new user, it will confuse others.
- **Client integrations** — configuration examples/docs for MCP clients beyond Claude Desktop and Cursor.

## Development setup

```bash
git clone https://github.com/cavishal04/tallyprime-mcp.git
cd tallyprime-mcp
python -m venv .venv
source .venv/bin/activate  # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

Run the checks the same way CI does:

```bash
ruff check src tests
pytest --cov=src/tallyprime_mcp
```

If you have TallyPrime available locally:

```bash
TALLYPRIME_MCP_RUN_INTEGRATION=1 pytest tests/integration -v
```

## Adding a new Tally report / MCP tool

1. **Confirm the request/response shape.** Check TallyPrime's own developer documentation (linked in `tally/xml_builder.py`'s module docstring) or, ideally, capture a real request/response from your own TallyPrime instance. Never guess a field name and present it as verified — if you can't confirm it, say so in a code comment, the same way the existing code does.
2. **Add fetch fields** to `tally/field_maps.py` if you're adding a new native Tally field.
3. **Add a method** to `tally/client.py` that builds the request and returns `TallyRecord` objects — don't put Pydantic modeling logic here.
4. **Add/extend a Pydantic model** in `models/` for the clean, typed shape the tool will return.
5. **Add/extend a service** in `services/` that maps `TallyRecord` → your model.
6. **Register the tool** in `mcp/tools.py`, following the existing pattern: a docstring MCP clients will show to the AI, a `@_guarded(...)` decorator, and `.model_dump()` on the way out.
7. **Add a mock XML fixture** under `tests/fixtures/xml/` and unit tests at each layer (parser, client, service, tool). Label fixtures clearly as mocks if they aren't captured from a real Tally instance.
8. **Update `docs/tools.md`** with the new tool's parameters and any caveats.

## Adding a new parser / fixing a field name

If you've confirmed against a real TallyPrime that a field name in `tally/field_maps.py` is wrong or incomplete for your version:

1. Open an issue or PR stating the TallyPrime version you tested against.
2. Add the correct field name as an *additional* candidate (via `field_text(record, "OLD_NAME", "NEW_NAME")`) rather than replacing it outright, unless you're confident the old name was simply wrong everywhere — this keeps the fix from silently breaking a different Tally version that did use the old name.
3. Add a test fixture demonstrating the corrected shape.

## Good first issues

Look for issues labeled [`good-first-issue`](https://github.com/cavishal04/tallyprime-mcp/labels/good-first-issue). If none are open, these are always welcome:

- Verifying any single tool's XML shape against a real Tally instance and reporting back (even just a comment on the relevant field-map entry) is valuable, self-contained, and doesn't require deep Python knowledge.
- Improving error messages — if a `TallyError` message ever confused you, it can probably be clearer.
- Expanding `docs/installation.md` for a platform/scenario it doesn't currently cover well.

## Code style

- Python 3.11+, full type hints, [Ruff](https://docs.astral.sh/ruff/) for linting (`ruff check src tests`).
- Keep functions small and single-purpose; prefer composing small functions in `services/` over branching logic in `mcp/tools.py`.
- Docstrings on every public function/class — future contributors (including future you) will thank you.
- No global mutable state. Configuration flows through `TallySettings`, not module-level constants.

## Pull requests

- Reference the issue you're addressing, if any.
- Include tests. A PR that adds behavior without a test covering it will likely be asked to add one before merge.
- Run `ruff check` and `pytest` locally before opening the PR — CI runs the same checks and will fail on the same issues.
- Keep PRs focused; a PR that does one thing is much easier to review than one that refactors three unrelated modules at once.

## Reporting bugs / requesting features

Please use the issue templates in `.github/ISSUE_TEMPLATE/`. For security vulnerabilities, see [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Code of Conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it.
