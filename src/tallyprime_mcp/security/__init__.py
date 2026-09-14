"""Security controls: permission gating, confirmation workflow scaffolding
for future write operations, and audit logging.

Nothing in this package currently allows a write to happen — see
:mod:`tallyprime_mcp.security.permissions` for the always-deny gate that any
future write tool must pass through, and ``docs/security.md`` for the full
threat model.
"""

from __future__ import annotations
