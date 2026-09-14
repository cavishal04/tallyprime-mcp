from __future__ import annotations

from tallyprime_mcp.logging_config import redact_secrets


def test_redacts_password() -> None:
    assert "hunter2" not in redact_secrets("password=hunter2")
    assert "[REDACTED]" in redact_secrets("password=hunter2")


def test_redacts_token_and_api_key() -> None:
    assert "abc123" not in redact_secrets("token: abc123")
    assert "xyz" not in redact_secrets("api_key=xyz")


def test_leaves_ordinary_text_alone() -> None:
    message = "Connected to TallyPrime at http://127.0.0.1:9000"
    assert redact_secrets(message) == message
