#!/usr/bin/env bash
# Runs the same checks as CI, locally. See docs/development.md.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> ruff check"
ruff check src tests

echo "==> pytest (unit tests; integration tests are skipped unless"
echo "    TALLYPRIME_MCP_RUN_INTEGRATION=1 is set)"
pytest --cov=src/tallyprime_mcp --cov-report=term-missing

echo "==> build package"
python -m build

echo "All checks passed."
