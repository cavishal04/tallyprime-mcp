from __future__ import annotations

import httpx
import pytest
import respx

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.tally.connection import TallyConnection
from tallyprime_mcp.tally.exceptions import (
    TallyConnectionError,
    TallyRequestError,
    TallyResponseTooLargeError,
    TallyTimeoutError,
)
from tests.conftest import load_fixture


@respx.mock
def test_send_success(settings: TallySettings) -> None:
    fixture = load_fixture("companies_response.xml")
    respx.post(settings.base_url).mock(return_value=httpx.Response(200, content=fixture))

    with TallyConnection(settings) as conn:
        response = conn.send(b"<ENVELOPE/>")
    assert response.raw_bytes == fixture
    assert response.status_code == 200


@respx.mock
def test_send_connection_refused(settings: TallySettings) -> None:
    respx.post(settings.base_url).mock(side_effect=httpx.ConnectError("refused"))
    with TallyConnection(settings) as conn, pytest.raises(TallyConnectionError):
        conn.send(b"<ENVELOPE/>")


@respx.mock
def test_send_timeout(settings: TallySettings) -> None:
    respx.post(settings.base_url).mock(side_effect=httpx.ReadTimeout("timed out"))
    with TallyConnection(settings) as conn, pytest.raises(TallyTimeoutError):
        conn.send(b"<ENVELOPE/>")


@respx.mock
def test_send_http_500(settings: TallySettings) -> None:
    respx.post(settings.base_url).mock(return_value=httpx.Response(500, content=b"oops"))
    with TallyConnection(settings) as conn, pytest.raises(TallyRequestError):
        conn.send(b"<ENVELOPE/>")


@respx.mock
def test_send_http_400(settings: TallySettings) -> None:
    respx.post(settings.base_url).mock(return_value=httpx.Response(400, content=b"bad request"))
    with TallyConnection(settings) as conn, pytest.raises(TallyRequestError):
        conn.send(b"<ENVELOPE/>")


def test_send_oversized_request_rejected_before_network_call(settings: TallySettings) -> None:
    tiny_settings = settings.model_copy(update={"max_request_bytes": 10})
    with TallyConnection(tiny_settings) as conn, pytest.raises(TallyRequestError, match="oversized"):
        conn.send(b"x" * 100)


@respx.mock
def test_send_oversized_response_rejected(settings: TallySettings) -> None:
    tiny_settings = settings.model_copy(update={"max_response_bytes": 10})
    respx.post(tiny_settings.base_url).mock(return_value=httpx.Response(200, content=b"y" * 1000))
    with TallyConnection(tiny_settings) as conn, pytest.raises(TallyResponseTooLargeError):
        conn.send(b"<ENVELOPE/>")
