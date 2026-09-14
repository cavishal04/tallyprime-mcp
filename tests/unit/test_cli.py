from __future__ import annotations

import json

import pytest

from tallyprime_mcp import __version__
from tallyprime_mcp.cli import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert __version__ in captured.out


def test_config_command_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["config"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["port"] == 9000
    assert payload["read_only"] is True
    # Never printed because it's never configurable in the first place.
    assert "password" not in captured.out.lower()


def test_test_connection_command_fails_cleanly_when_no_tally(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["test-connection"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
