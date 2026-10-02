"""Security controls: the write-permission gate, the two-step confirmation
workflow every write must pass through, and audit logging.

Writes are disabled unless ``TALLY_READ_ONLY=false`` — see
:mod:`tallyprime_mcp.security.permissions` and ``docs/security.md``.
"""

from __future__ import annotations
