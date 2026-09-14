"""Structured, local-only logging for TallyPrime MCP.

Design goals (see SECURITY.md for the full threat model):

* Logs never leave the machine — there is no remote log sink in this project.
* Passwords/secrets are never logged. Since this server currently only makes
  unauthenticated local HTTP calls to TallyPrime there are no Tally credentials
  to redact, but the redaction filter is kept in place defensively for any
  future auth-bearing configuration, and because request/response bodies may
  contain incidental strings that look like secrets.
* Full accounting record contents are not logged; only metadata (tool name,
  duration, row counts, status) is logged at INFO. Response bodies are only
  logged at DEBUG, and even then are truncated.
"""

from __future__ import annotations

import contextlib
import json
import logging
import logging.handlers
import re
import sys
from pathlib import Path
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"(password\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*)(\S+)", re.IGNORECASE),
]

_REDACTED = "[REDACTED]"


def redact_secrets(message: str) -> str:
    """Best-effort redaction of anything that looks like a credential.

    This is defence in depth, not a guarantee: callers should still avoid
    passing secrets into log messages in the first place.
    """
    redacted = message
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: m.group(1) + _REDACTED, redacted)
    return redacted


class RedactingFilter(logging.Filter):
    """Logging filter that redacts secret-looking substrings from every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        with contextlib.suppress(Exception):  # logging must never raise
            record.msg = redact_secrets(str(record.msg))
        return True


class JsonFormatter(logging.Formatter):
    """Minimal structured JSON line formatter (no external dependency needed)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("tool", "duration_ms", "event", "company", "status"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    json_lines: bool = False,
) -> logging.Logger:
    """Configure the ``tallyprime_mcp`` logger tree.

    Logs go to stderr (so stdout stays clean for MCP's stdio transport) and,
    optionally, to a rotating local log file. There is no network log
    handler anywhere in this project.
    """
    logger = logging.getLogger("tallyprime_mcp")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter: logging.Formatter
    if json_lines:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(RedactingFilter())
    logger.addHandler(stream_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "tallyprime-mcp.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactingFilter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``tallyprime_mcp`` namespace."""
    return logging.getLogger(f"tallyprime_mcp.{name}")
