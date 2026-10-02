"""Two-step confirmation for write operations.

A write tool never talks to Tally directly. It validates its input, builds
the exact XML that *would* be sent, and stores it here as a
:class:`PendingConfirmation`, returning the ``confirmation_id`` and a
human-readable preview. Only a second, explicit ``confirm_write`` call with
that id sends the stored XML — byte-for-byte what was previewed, so nothing
can change between the preview the user approved and the write.

Pending confirmations are in-memory, single-use, and expire after
``TALLY_WRITE_CONFIRMATION_TTL_SECONDS``; restarting the server discards them.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from tallyprime_mcp.tally.exceptions import ValidationError


@dataclass
class PendingConfirmation:
    """A proposed write action awaiting explicit user confirmation."""

    operation: str
    summary: str
    company: str
    request_xml: bytes
    proposed_payload: dict[str, Any] = field(default_factory=dict)
    confirmation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


class ConfirmationStore:
    """Thread-safe, in-memory store of pending writes."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._pending: dict[str, PendingConfirmation] = {}
        self._lock = threading.Lock()

    def add(self, pending: PendingConfirmation) -> PendingConfirmation:
        pending.expires_at = pending.created_at + self._ttl
        with self._lock:
            self._purge_expired()
            self._pending[pending.confirmation_id] = pending
        return pending

    def pop(self, confirmation_id: str) -> PendingConfirmation:
        """Remove and return a pending write. Raises :class:`ValidationError`
        if the id is unknown, already used, or expired."""
        with self._lock:
            self._purge_expired()
            pending = self._pending.pop(confirmation_id, None)
        if pending is None:
            raise ValidationError(
                f"No pending write with confirmation_id {confirmation_id!r}.",
                detail="It may have already been confirmed or cancelled, expired, or the "
                "server restarted. Propose the write again.",
            )
        return pending

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        for key in [k for k, p in self._pending.items() if p.expires_at and p.expires_at <= now]:
            del self._pending[key]
