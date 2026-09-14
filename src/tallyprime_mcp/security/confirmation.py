"""Scaffolding for the confirmation step a future write operation would need
before it is allowed to execute against TallyPrime.

Not wired into anything yet — no write tools exist in this release. This
module defines the *shape* the confirmation workflow will take so future
contributors implementing e.g. ``create_payment`` build to a consistent
pattern rather than inventing bespoke flows per tool. See
:mod:`tallyprime_mcp.security.permissions` for the surrounding gate and
``docs/security.md`` for the design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class PendingConfirmation:
    """A proposed write action awaiting explicit user confirmation.

    The intended flow: a future write tool builds one of these, returns it
    to the MCP client describing exactly what would be created/changed, and
    performs the actual Tally write only on a second, explicit call that
    references ``confirmation_id`` (e.g. a ``confirm_action`` tool). This
    server does not execute anything from the mere existence of a
    ``PendingConfirmation`` object.
    """

    confirmation_id: str = field(default_factory=lambda: str(uuid4()))
    operation: str = ""
    summary: str = ""
    proposed_payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    confirmed: bool = False
