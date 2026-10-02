"""Permission gate for Tally *write* operations.

Every write goes through this flow:

    AI proposes a write (e.g. create_voucher)
        -> WritePermission.check() must return allowed=True
        -> the proposed change is validated and returned as a preview,
           NOT executed (security.confirmation stores it)
        -> the user explicitly approves; confirm_write(confirmation_id)
        -> WritePermission.check() is consulted again, then Tally is called
        -> the outcome is recorded via security.audit

Design rules:

* ``TallySettings.read_only`` must be ``False`` (never the default).
* Only the operations in :data:`WRITE_OPERATIONS` can ever be allowed.
  Each declares the minimum fields it needs; extra/unknown fields are
  rejected rather than passed through.
* A generic "run this Tally XML" escape hatch is never provided.
* Nothing alters or deletes existing Tally data — only creation is supported.
"""

from __future__ import annotations

from dataclasses import dataclass

from tallyprime_mcp.config import TallySettings

WRITE_OPERATIONS = frozenset({"create_ledger", "create_voucher"})


@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    reason: str


class WritePermission:
    """Gate that every write operation must consult before touching Tally."""

    def __init__(self, settings: TallySettings) -> None:
        self._settings = settings

    def check(self, operation: str) -> PermissionResult:
        if self._settings.read_only:
            return PermissionResult(
                allowed=False,
                reason=(
                    f"'{operation}' is a write operation, and this server is running in "
                    "read-only mode. Set TALLY_READ_ONLY=false to enable writes."
                ),
            )
        if operation not in WRITE_OPERATIONS:
            return PermissionResult(
                allowed=False,
                reason=f"'{operation}' is not a supported write operation.",
            )
        return PermissionResult(allowed=True, reason="")
