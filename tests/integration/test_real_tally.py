"""Integration tests against a REAL, locally-running TallyPrime instance.

These are skipped by default and in CI, because no TallyPrime installation
is available in a standard CI runner or in this project's own development
environment (it was built/tested on Linux without a Windows+TallyPrime
machine available — see README/CHANGELOG "Testing" sections for exactly
what was and wasn't verified against real Tally).

To run these against your own TallyPrime:

    TALLYPRIME_MCP_RUN_INTEGRATION=1 pytest tests/integration -v

Before running, open TallyPrime, load a company, and enable the HTTP-XML
gateway (Help > Settings > Connectivity, or F1 > Settings, depending on
your TallyPrime version — consult docs/tally-setup.md).
"""

from __future__ import annotations

import os

import pytest

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.tally.client import TallyClient

pytestmark = pytest.mark.skipif(
    os.environ.get("TALLYPRIME_MCP_RUN_INTEGRATION") != "1",
    reason="Set TALLYPRIME_MCP_RUN_INTEGRATION=1 to run against a real, locally running TallyPrime.",
)


@pytest.fixture
def real_client() -> TallyClient:
    settings = TallySettings()
    with TallyClient(settings) as client:
        yield client


def test_real_connection(real_client: TallyClient) -> None:
    ok, message = real_client.test_connection()
    assert ok, message


def test_real_list_companies(real_client: TallyClient) -> None:
    companies = real_client.list_companies()
    assert len(companies) >= 1, (
        "No companies returned — is a company open/loaded in TallyPrime? "
        "This tool cannot see companies that exist on disk but aren't currently loaded."
    )


def test_real_list_ledgers(real_client: TallyClient) -> None:
    ledgers = real_client.list_ledgers()
    assert len(ledgers) >= 1, "Expected at least one ledger (every company has at least Cash)."
