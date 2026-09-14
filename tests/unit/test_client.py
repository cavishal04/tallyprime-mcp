from __future__ import annotations

from datetime import date

import pytest

from tallyprime_mcp.config import TallySettings
from tallyprime_mcp.tally.client import TallyClient
from tallyprime_mcp.tally.exceptions import TallyConnectionError
from tests.unit.fakes import FakeTallyConnection


@pytest.fixture
def client(settings: TallySettings) -> TallyClient:
    return TallyClient(settings, connection=FakeTallyConnection())


def test_test_connection_success(client: TallyClient) -> None:
    ok, message = client.test_connection()
    assert ok is True
    assert "Connected" in message


def test_test_connection_failure(settings: TallySettings) -> None:
    fake = FakeTallyConnection(fail_with=TallyConnectionError("nope"))
    client = TallyClient(settings, connection=fake)
    ok, message = client.test_connection()
    assert ok is False
    assert "nope" in message


def test_list_companies(client: TallyClient) -> None:
    companies = client.list_companies()
    assert {c.name for c in companies} == {"Acme Traders Pvt Ltd", "Beta Exports LLP"}


def test_list_ledgers(client: TallyClient) -> None:
    ledgers = client.list_ledgers()
    assert len(ledgers) == 8
    names = {ledger.name for ledger in ledgers}
    assert "HDFC Bank" in names


def test_get_ledger_found(client: TallyClient) -> None:
    ledger, vouchers = client.get_ledger("ABC Limited")
    assert ledger is not None
    assert ledger.name == "ABC Limited"
    assert len(vouchers) >= 1


def test_get_ledger_not_found(client: TallyClient) -> None:
    ledger, _vouchers = client.get_ledger("Does Not Exist Ltd")
    assert ledger is None


def test_search_vouchers_filters_by_type(client: TallyClient) -> None:
    receipts = client.search_vouchers(voucher_type="Receipt")
    assert len(receipts) == 1
    assert receipts[0].fields["VOUCHERNUMBER"] == "RV-001"


def test_search_vouchers_filters_by_ledger(client: TallyClient) -> None:
    results = client.search_vouchers(ledger="ABC")
    assert len(results) == 2


def test_search_vouchers_respects_limit(client: TallyClient) -> None:
    results = client.search_vouchers(limit=1)
    assert len(results) == 1


def test_search_vouchers_search_term(client: TallyClient) -> None:
    results = client.search_vouchers(search_term="supplier")
    assert len(results) == 1
    assert results[0].fields["VOUCHERNUMBER"] == "PV-014"


def test_get_voucher_found(client: TallyClient) -> None:
    voucher = client.get_voucher("SA-102")
    assert voucher is not None
    assert voucher.fields["PARTYLEDGERNAME"] == "ABC Limited"


def test_get_voucher_not_found(client: TallyClient) -> None:
    assert client.get_voucher("DOES-NOT-EXIST") is None


def test_list_groups(client: TallyClient) -> None:
    groups = client.list_groups()
    names = {g.name for g in groups}
    assert "Current Assets" in names


def test_list_stock_items(client: TallyClient) -> None:
    items = client.list_stock_items()
    assert len(items) == 2


def test_list_stock_items_search(client: TallyClient) -> None:
    items = client.list_stock_items(search="widget a")
    assert len(items) == 1
    assert items[0].name == "Widget A"


def test_date_range_passed_through_to_request(client: TallyClient, settings: TallySettings) -> None:
    fake = client._connection  # noqa: SLF001 - test introspection
    client.search_vouchers(from_date=date(2026, 4, 1), to_date=date(2026, 6, 30))
    assert any(b"20260401" in req and b"20260630" in req for req in fake.sent_requests)
