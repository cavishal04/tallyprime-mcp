from __future__ import annotations

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.security.permissions import WritePermission


def test_write_denied_when_read_only(settings: TallySettings) -> None:
    perm = WritePermission(settings)
    result = perm.check("create_payment")
    assert result.allowed is False
    assert "read-only" in result.reason.lower()


def test_write_still_denied_even_if_read_only_flag_flipped(settings: TallySettings) -> None:
    """No write tool is implemented yet, so even a hypothetical
    misconfiguration (read_only=False) must not open a write path."""
    not_read_only = settings.model_copy(update={"read_only": False})
    perm = WritePermission(not_read_only)
    result = perm.check("create_payment")
    assert result.allowed is False
