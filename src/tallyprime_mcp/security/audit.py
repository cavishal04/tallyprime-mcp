"""Local, append-only audit logging for security-relevant events.

This writes through the standard logging pipeline configured in
:mod:`tallyprime_mcp.logging_config` (so it is subject to the same secret
redaction and never leaves the machine) but at a dedicated logger name so it
can be filtered/routed to its own file independently of ordinary debug
output if an operator wants that.
"""

from __future__ import annotations

from tallyprime_mcp.logging_config import get_logger

_audit_logger = get_logger("audit")


def log_tool_invocation(tool_name: str, *, company: str | None, allowed: bool, reason: str = "") -> None:
    _audit_logger.info(
        "tool_invocation",
        extra={"tool": tool_name, "company": company, "status": "allowed" if allowed else "denied"},
    )
    if not allowed and reason:
        _audit_logger.warning(f"tool_invocation_denied: {tool_name}: {reason}")


def log_connection_attempt(*, ok: bool, detail: str = "") -> None:
    _audit_logger.info(
        "connection_attempt",
        extra={"event": "connection_attempt", "status": "ok" if ok else "failed"},
    )
    if not ok and detail:
        _audit_logger.info(f"connection_attempt_detail: {detail}")


def log_permission_denied(operation: str, reason: str) -> None:
    _audit_logger.warning(f"permission_denied: {operation}: {reason}")
