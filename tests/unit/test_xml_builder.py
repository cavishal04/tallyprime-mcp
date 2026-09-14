from __future__ import annotations

from datetime import date
from xml.etree.ElementTree import fromstring

from tallyprime_mcp.tally.xml_builder import (
    StaticVariables,
    build_collection_request,
    build_connection_check_request,
    build_report_export_request,
    format_tally_date,
)


def test_format_tally_date() -> None:
    assert format_tally_date(date(2026, 4, 1)) == "20260401"
    assert format_tally_date(date(2026, 12, 31)) == "20261231"


def test_collection_request_structure() -> None:
    raw = build_collection_request(
        collection_name="MyCollection",
        native_type="Ledger",
        fetch_fields=["NAME", "PARENT"],
        static_variables=StaticVariables(current_company="Acme Traders"),
    )
    root = fromstring(raw)
    assert root.tag == "ENVELOPE"

    header = root.find("HEADER")
    assert header is not None
    assert header.findtext("VERSION") == "1"
    assert header.findtext("TALLYREQUEST") == "Export"
    assert header.findtext("TYPE") == "Collection"
    assert header.findtext("ID") == "MyCollection"

    collection = root.find(".//COLLECTION")
    assert collection is not None
    assert collection.attrib["NAME"] == "MyCollection"
    assert collection.findtext("TYPE") == "Ledger"
    assert collection.findtext("FETCH") == "NAME, PARENT"

    static_vars = root.find(".//STATICVARIABLES")
    assert static_vars is not None
    assert static_vars.findtext("SVCURRENTCOMPANY") == "Acme Traders"


def test_collection_request_with_date_range() -> None:
    raw = build_collection_request(
        collection_name="Vouchers",
        native_type="Voucher",
        fetch_fields=["DATE", "AMOUNT"],
        static_variables=StaticVariables(from_date=date(2026, 4, 1), to_date=date(2026, 6, 30)),
    )
    root = fromstring(raw)
    static_vars = root.find(".//STATICVARIABLES")
    assert static_vars.findtext("SVFROMDATE") == "20260401"
    assert static_vars.findtext("SVTODATE") == "20260630"


def test_report_export_request_structure() -> None:
    raw = build_report_export_request("Trial Balance")
    root = fromstring(raw)
    header = root.find("HEADER")
    assert header.findtext("TYPE") == "Data"
    assert header.findtext("ID") == "Trial Balance"


def test_connection_check_request_is_lightweight() -> None:
    raw = build_connection_check_request()
    root = fromstring(raw)
    collection = root.find(".//COLLECTION")
    assert collection.findtext("TYPE") == "Company"
    assert collection.findtext("FETCH") == "NAME"


def test_request_bytes_are_utf8_declared() -> None:
    raw = build_connection_check_request()
    assert raw.startswith(b"<?xml")
    assert b"utf-8" in raw.lower()


def test_xml_injection_is_escaped_by_serializer() -> None:
    """Values that look like XML/markup must come out escaped, not injected
    as raw markup — this is what protects against XML injection via
    ledger/voucher names containing `<`, `&`, etc."""
    raw = build_collection_request(
        collection_name="Test",
        native_type="Ledger",
        fetch_fields=["NAME"],
        static_variables=StaticVariables(current_company="</ENVELOPE><EVIL>hi</EVIL><ENVELOPE>"),
    )
    # Must still be well-formed XML with a single root, i.e. injection failed.
    root = fromstring(raw)
    assert root.tag == "ENVELOPE"
    assert root.find(".//EVIL") is None
    static_vars = root.find(".//STATICVARIABLES")
    assert "EVIL" in static_vars.findtext("SVCURRENTCOMPANY")
