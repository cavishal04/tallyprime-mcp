"""Configuration for TallyPrime MCP.

Settings are loaded from (in order of increasing priority):

1. Built-in defaults (safe for a typical local TallyPrime install).
2. A ``.env`` file in the current working directory, if present.
3. Environment variables (``TALLY_*``).

No credentials, ports, company names, or machine-specific paths are
hard-coded anywhere else in the codebase — they all flow through this
module so behaviour stays configurable and auditable in one place.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TallySettings(BaseSettings):
    """Runtime configuration for the TallyPrime MCP server.

    All fields can be set via environment variables with the ``TALLY_``
    prefix (e.g. ``TALLY_HOST``, ``TALLY_PORT``) or via a ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="TALLY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Connection -----------------------------------------------------
    host: str = Field(
        default="127.0.0.1",
        description="Hostname/IP where TallyPrime's HTTP-XML gateway is listening.",
    )
    port: int = Field(
        default=9000,
        ge=1,
        le=65535,
        description="Port TallyPrime's HTTP-XML gateway is listening on.",
    )
    scheme: str = Field(
        default="http",
        description="URL scheme used to reach TallyPrime (http, or https if you have "
        "put a TLS-terminating proxy in front of Tally yourself).",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Timeout, in seconds, for each request made to TallyPrime.",
    )
    connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Timeout, in seconds, for establishing the TCP connection to TallyPrime.",
    )

    # --- Default company --------------------------------------------------
    default_company: str | None = Field(
        default=None,
        description="Company name to use when a tool call does not specify one explicitly. "
        "Never hard-code this in source; set it per-deployment via TALLY_DEFAULT_COMPANY.",
    )

    # --- Safety -----------------------------------------------------------
    read_only: bool = Field(
        default=True,
        description="When true (the default and, in this release, the only supported mode), "
        "no MCP tool that could modify TallyPrime data is registered or callable.",
    )

    # --- Request limits (defence in depth) --------------------------------
    max_response_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        description="Maximum size, in bytes, of a response TallyPrime is allowed to send back "
        "before the client aborts the request.",
    )
    max_request_bytes: int = Field(
        default=1 * 1024 * 1024,
        gt=0,
        description="Maximum size, in bytes, of an XML request this server will send to Tally.",
    )
    default_voucher_limit: int = Field(
        default=100,
        gt=0,
        le=5000,
        description="Default maximum number of vouchers returned by search_vouchers when the "
        "caller does not specify a limit.",
    )

    # --- Logging ------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Python logging level name.")
    log_dir: Path | None = Field(
        default=None,
        description="Directory to write rotating log files to. If unset, logs go to stderr only.",
    )
    log_json: bool = Field(
        default=False, description="Emit logs as structured JSON lines instead of plain text."
    )

    # --- Debug ---------------------------------------------------------------
    expose_raw_xml_tool: bool = Field(
        default=False,
        description="If true, register a debug-only tool that returns raw TallyPrime XML for a "
        "given request kind. Intended for development/troubleshooting only — never enable this "
        "on a machine an untrusted AI agent has broad access to, since raw XML may echo internal "
        "field names/structure beyond the sanitized tool outputs.",
    )

    @field_validator("scheme")
    @classmethod
    def _validate_scheme(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"http", "https"}:
            raise ValueError("scheme must be 'http' or 'https'")
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        value = value.upper().strip()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value not in valid:
            raise ValueError(f"log_level must be one of {sorted(valid)}")
        return value

    @property
    def base_url(self) -> str:
        """Base URL of the TallyPrime HTTP-XML gateway."""
        return f"{self.scheme}://{self.host}:{self.port}"


def load_settings() -> TallySettings:
    """Load settings from environment/``.env``. Kept as a function (rather than a
    module-level singleton) so tests can construct isolated settings instances."""
    return TallySettings()
