from __future__ import annotations

import pytest
from pydantic import ValidationError

from tallyprime_mcp.config import TallySettings


def test_defaults() -> None:
    settings = TallySettings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000
    assert settings.read_only is True
    assert settings.base_url == "http://127.0.0.1:9000"


def test_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TALLY_HOST", "192.168.1.50")
    monkeypatch.setenv("TALLY_PORT", "9999")
    settings = TallySettings(_env_file=None)
    assert settings.host == "192.168.1.50"
    assert settings.port == 9999
    assert settings.base_url == "http://192.168.1.50:9999"


def test_invalid_scheme_rejected() -> None:
    with pytest.raises(ValidationError):
        TallySettings(scheme="ftp", _env_file=None)


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        TallySettings(log_level="VERBOSE", _env_file=None)


def test_invalid_port_rejected() -> None:
    with pytest.raises(ValidationError):
        TallySettings(port=0, _env_file=None)
    with pytest.raises(ValidationError):
        TallySettings(port=70000, _env_file=None)


def test_no_credentials_fields_exist() -> None:
    """Regression guard: this project must never grow a hard-coded-credential
    field. Any password/secret/token field name should be rejected in review,
    not quietly added here."""
    field_names = set(TallySettings.model_fields.keys())
    forbidden_substrings = ("password", "secret", "apikey", "api_key")
    for name in field_names:
        for forbidden in forbidden_substrings:
            assert forbidden not in name.lower(), f"Unexpected credential-like field: {name}"
