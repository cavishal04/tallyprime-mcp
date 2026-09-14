from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import fromstring

from tallyprime_mcp.tally.connection import TallyResponse
from tests.conftest import load_fixture

_TYPE_TO_FIXTURE = {
    "Company": "companies_response.xml",
    "Ledger": "ledgers_response.xml",
    "Voucher": "vouchers_response.xml",
    "Group": "groups_response.xml",
    "StockItem": "stock_items_response.xml",
}


@dataclass
class FakeTallyConnection:
    """A test double standing in for TallyConnection: instead of making an
    HTTP call, it inspects the outgoing request XML for its <TYPE> element
    (set by build_collection_request's inner COLLECTION/TYPE) and returns
    the matching mock fixture. This lets TallyClient/service-layer tests
    exercise the full request -> parse -> model pipeline without any real
    or mocked network call.
    """

    sent_requests: list[bytes] = field(default_factory=list)
    fail_with: Exception | None = None

    def send(self, xml_body: bytes) -> TallyResponse:
        self.sent_requests.append(xml_body)
        if self.fail_with is not None:
            raise self.fail_with
        root = fromstring(xml_body)
        collection = root.find(".//COLLECTION")
        native_type = collection.findtext("TYPE") if collection is not None else None
        fixture_name = _TYPE_TO_FIXTURE.get(native_type or "")
        if fixture_name is None:
            raise AssertionError(f"FakeTallyConnection has no fixture for native type {native_type!r}")
        return TallyResponse(raw_bytes=load_fixture(fixture_name), elapsed_ms=1.0, status_code=200)

    def close(self) -> None:  # pragma: no cover - trivial
        pass
