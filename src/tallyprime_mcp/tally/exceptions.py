"""Custom exception hierarchy for TallyPrime integration.

Every exception carries a short, human-readable ``message`` suitable for
showing directly to an end user (or an AI assistant relaying it), and may
carry additional structured ``detail`` for logs. Raw Python stack traces are
never sent to MCP clients — see :mod:`tallyprime_mcp.mcp.tools` for where
these are caught and translated into MCP tool errors.
"""

from __future__ import annotations


class TallyError(Exception):
    """Base class for all TallyPrime-integration errors."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class TallyConnectionError(TallyError):
    """Raised when TallyPrime cannot be reached at all (connection refused,
    DNS failure, network unreachable, etc.)."""


class TallyTimeoutError(TallyError):
    """Raised when a request to TallyPrime did not complete within the
    configured timeout."""


class TallyXMLParseError(TallyError):
    """Raised when TallyPrime's response could not be parsed as valid XML,
    or did not match the expected structure for the request that was made."""


class TallyCompanyNotFoundError(TallyError):
    """Raised when the requested company is not loaded/available in Tally."""


class TallyRequestError(TallyError):
    """Raised when TallyPrime accepted the HTTP request but reported an
    application-level error (e.g. invalid request, unknown report/collection,
    a report that requires a TDL definition Tally doesn't have, etc.)."""


class TallyResponseTooLargeError(TallyError):
    """Raised when TallyPrime's response exceeds the configured size limit."""


class ValidationError(TallyError):
    """Raised when caller-supplied parameters fail validation before a
    request is ever sent to TallyPrime."""
