from __future__ import annotations

from pathlib import Path

import pytest

from tallyprime_mcp.config import TallySettings

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "xml"


def load_fixture(name: str) -> bytes:
    """Load a mock XML fixture by filename (see FIXTURES_DIR).

    All fixtures under tests/fixtures/xml are hand-constructed mocks shaped
    to match this project's documented request/response patterns — none of
    them were captured from a real TallyPrime instance. See README/CHANGELOG
    "Testing" sections.
    """
    return (FIXTURES_DIR / name).read_bytes()


@pytest.fixture
def settings() -> TallySettings:
    return TallySettings(
        host="127.0.0.1",
        port=9000,
        default_company=None,
        timeout_seconds=5.0,
        connect_timeout_seconds=2.0,
    )
