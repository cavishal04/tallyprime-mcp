"""Permission gate for Tally *write* operations.

Nothing in this release calls this module for anything, because no write
tool is registered (see ``docs/security.md`` and ``README.md#roadmap``).
It exists now so the intended future workflow is concrete and reviewable
rather than a paragraph of prose:

    AI requests a write (e.g. create_payment)
        -> WritePermission.check() must return allowed=True
        -> the proposed transaction is shown to the user (not executed)
        -> the user explicitly confirms (security.confirmation)
        -> only then does a (not-yet-implemented) write path call Tally
        -> the outcome is recorded via security.audit

Design intent for the eventual write tools:

* ``TallySettings.read_only`` must be ``False`` (never the default).
* Each write tool declares the minimum fields it needs; extra/unknown
  fields are rejected rather than passed through.
* A generic "run this Tally XML" escape hatch is never provided — see
  README "Roadmap" for why.
"""

from __future__ import annotations

from dataclasses import dataclass

from tallyprime_mcp.config import TallySettings


@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    reason: str


class WritePermission:
    """Gate that every future write operation must consult before touching
    Tally. In this release it always denies, because no write capability
    has shipped yet — this is intentional, not a placeholder bug.
    """

    def __init__(self, settings: TallySettings) -> None:
        self._settings = settings

    def check(self, operation: str) -> PermissionResult:
        if self._settings.read_only:
            return PermissionResult(
                allowed=False,
                reason=(
                    f"'{operation}' is a write operation. TallyPrime MCP v0.1 is "
                    "read-only by design and does not implement any write operations "
                    "yet, regardless of TALLY_READ_ONLY. See the project roadmap."
                ),
            )
        # No write operations are implemented in this release even if a
        # future config flag flips read_only to False; this branch is a
        # deliberate hard stop, not a bypass.
        return PermissionResult(
            allowed=False,
            reason=f"'{operation}' is not implemented in this release.",
        )
