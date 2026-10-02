from __future__ import annotations

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.security.permissions import WritePermission


def test_write_denied_when_read_only(settings: TallySettings) -> None:
    perm = WritePermission(settings)
    result = perm.check("create_voucher")
    assert result.allowed is False
    assert "read-only" in result.reason.lower()


def test_read_only_is_the_default() -> None:
    assert TallySettings().read_only is True


def test_supported_write_allowed_when_writes_enabled(settings: TallySettings) -> None:
    perm = WritePermission(settings.model_copy(update={"read_only": False}))
    assert perm.check("create_voucher").allowed is True
    assert perm.check("create_ledger").allowed is True


def test_unknown_write_denied_even_when_writes_enabled(settings: TallySettings) -> None:
    perm = WritePermission(settings.model_copy(update={"read_only": False}))
    for operation in ("delete_voucher", "alter_ledger", "execute_xml"):
        assert perm.check(operation).allowed is False
