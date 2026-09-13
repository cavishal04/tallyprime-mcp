"""Low-level HTTP transport to TallyPrime's local XML gateway.

This module is intentionally "dumb": it knows how to POST XML bytes to
Tally and get XML bytes back, with timeouts and size limits, and to turn
transport-level failures into the project's own exception types. It knows
nothing about what any particular request means — that's the job of
:mod:`tallyprime_mcp.tally.xml_builder`/``xml_parser`` and
:mod:`tallyprime_mcp.tally.client`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.logging_config import get_logger
from tallyprime_mcp.tally.exceptions import (
    TallyConnectionError,
    TallyRequestError,
    TallyResponseTooLargeError,
    TallyTimeoutError,
)

logger = get_logger("tally.connection")

_TALLY_HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
}


@dataclass
class TallyResponse:
    raw_bytes: bytes
    elapsed_ms: float
    status_code: int


class TallyConnection:
    """Handles raw HTTP POSTs to TallyPrime with limits, timeouts, and
    consistent error translation. Safe to reuse across many requests; not
    safe to share across threads without external locking (mirrors
    :class:`httpx.Client`'s own thread-safety contract).
    """

    def __init__(self, settings: TallySettings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(
                timeout=settings.timeout_seconds,
                connect=settings.connect_timeout_seconds,
            ),
            # TallyPrime's HTTP-XML gateway is a plain local server; we
            # never want this client silently following a redirect to some
            # other host.
            follow_redirects=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> TallyConnection:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def send(self, xml_body: bytes) -> TallyResponse:
        """POST ``xml_body`` to TallyPrime and return the raw response.

        Raises
        ------
        TallyRequestError
            If the request body exceeds the configured maximum size.
        TallyConnectionError
            If TallyPrime cannot be reached at all.
        TallyTimeoutError
            If the request does not complete within the configured timeout.
        TallyResponseTooLargeError
            If TallyPrime's response exceeds the configured maximum size.
        """
        if len(xml_body) > self._settings.max_request_bytes:
            raise TallyRequestError(
                "Refusing to send an oversized request to TallyPrime.",
                detail=f"{len(xml_body)} bytes exceeds the configured limit of "
                f"{self._settings.max_request_bytes} bytes.",
            )

        url = self._settings.base_url
        started = time.monotonic()
        try:
            with self._client.stream(
                "POST", url, content=xml_body, headers=_TALLY_HEADERS
            ) as response:
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._settings.max_response_bytes:
                        raise TallyResponseTooLargeError(
                            "TallyPrime's response exceeded the configured size limit.",
                            detail=f"Aborted after {total} bytes "
                            f"(limit {self._settings.max_response_bytes}).",
                        )
                    chunks.append(chunk)
                status_code = response.status_code
        except httpx.ConnectError as exc:
            raise TallyConnectionError(
                f"Could not connect to TallyPrime at {url}.",
                detail="Connection refused or host unreachable. Confirm TallyPrime is "
                "running, a company is loaded, and the HTTP-XML gateway "
                "(Help > Settings > Connectivity, or F1 > Settings) is enabled on the "
                "configured host/port.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise TallyTimeoutError(
                f"Request to TallyPrime at {url} timed out after "
                f"{self._settings.timeout_seconds}s.",
                detail="TallyPrime may be busy (e.g. a modal dialog open on screen) or the "
                "requested report/company may be large. Consider narrowing the date "
                "range or increasing TALLY_TIMEOUT_SECONDS.",
            ) from exc
        except TallyResponseTooLargeError:
            raise
        except httpx.HTTPError as exc:
            raise TallyConnectionError(
                f"Unexpected network error talking to TallyPrime at {url}.",
                detail=str(exc),
            ) from exc

        elapsed_ms = (time.monotonic() - started) * 1000
        raw = b"".join(chunks)

        if status_code >= 500:
            raise TallyRequestError(
                f"TallyPrime returned HTTP {status_code}.",
                detail="TallyPrime's gateway reported an internal error for this request.",
            )
        if status_code >= 400:
            raise TallyRequestError(
                f"TallyPrime returned HTTP {status_code}.",
                detail="The request was rejected before Tally attempted to process the XML.",
            )

        logger.debug(
            "tally_request_completed",
            extra={"duration_ms": round(elapsed_ms, 1), "status": status_code},
        )
        return TallyResponse(raw_bytes=raw, elapsed_ms=elapsed_ms, status_code=status_code)
