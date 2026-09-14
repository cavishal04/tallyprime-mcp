from __future__ import annotations

import pytest

from tallyprime_mcp.tally.exceptions import TallyRequestError, TallyXMLParseError
from tallyprime_mcp.tally.xml_parser import (
    check_for_tally_error,
    extract_records,
    field_amount,
    field_text,
    parse_tally_date,
    parse_xml,
)
from tests.conftest import load_fixture


def test_parse_xml_empty_raises() -> None:
    with pytest.raises(TallyXMLParseError):
        parse_xml(b"")


def test_parse_xml_malformed_raises() -> None:
    raw = load_fixture("malformed_response.xml")
    with pytest.raises(TallyXMLParseError):
        parse_xml(raw)


def test_check_for_tally_error_raises_on_lineerror() -> None:
    raw = load_fixture("error_response.xml")
    root = parse_xml(raw)
    with pytest.raises(TallyRequestError) as exc_info:
        check_for_tally_error(root)
    assert "Unknown collection" in (exc_info.value.detail or "")


def test_check_for_tally_error_passes_on_clean_response() -> None:
    raw = load_fixture("companies_response.xml")
    root = parse_xml(raw)
    check_for_tally_error(root)  # should not raise


def test_extract_records_companies() -> None:
    raw = load_fixture("companies_response.xml")
    root = parse_xml(raw)
    records = extract_records(root, "Company")
    assert len(records) == 2
    names = {r.name for r in records}
    assert names == {"Acme Traders Pvt Ltd", "Beta Exports LLP"}


def test_extract_records_is_case_insensitive_on_tag() -> None:
    raw = load_fixture("ledgers_response.xml")
    root = parse_xml(raw)
    upper = extract_records(root, "LEDGER")
    lower = extract_records(root, "ledger")
    assert len(upper) == len(lower) == 8


def test_field_text_tries_candidates_in_order() -> None:
    raw = load_fixture("ledgers_response.xml")
    root = parse_xml(raw)
    record = extract_records(root, "Ledger")[0]
    assert field_text(record, "DOES_NOT_EXIST", "PARENT") == "Bank Accounts"
    assert field_text(record, "DOES_NOT_EXIST", default="fallback") == "fallback"


def test_field_amount_plain_number() -> None:
    raw = load_fixture("ledgers_response.xml")
    root = parse_xml(raw)
    record = extract_records(root, "Ledger")[0]
    assert field_amount(record, "CLOSINGBALANCE") == 1375000.0


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1000", 1000.0),
        ("1,000.50", 1000.5),
        ("1000 Cr", -1000.0),
        ("1000 Dr", 1000.0),
        ("(1000)", -1000.0),
        ("", 0.0),
    ],
)
def test_field_amount_parsing_variants(raw: str, expected: float) -> None:
    from tallyprime_mcp.tally.xml_parser import TallyRecord

    record = TallyRecord(tag="LEDGER", name="X", fields={"AMOUNT": raw})
    assert field_amount(record, "AMOUNT") == expected


def test_field_amount_unparseable_raises() -> None:
    from tallyprime_mcp.tally.xml_parser import TallyRecord

    record = TallyRecord(tag="LEDGER", name="X", fields={"AMOUNT": "not-a-number"})
    with pytest.raises(TallyXMLParseError):
        field_amount(record, "AMOUNT")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("20260401", "2026-04-01"),
        ("", None),
        ("garbage", None),
        ("2026-04-01", None),  # already-formatted input is not accepted; documents the contract
    ],
)
def test_parse_tally_date(raw: str, expected: str | None) -> None:
    assert parse_tally_date(raw) == expected
