"""Builds XML requests for TallyPrime's local HTTP-XML gateway.

Reference / verification notes
-------------------------------
TallyPrime's XML interface always wraps requests in the structure below —
this part is confirmed against Tally Solutions' own developer documentation
(https://help.tallysolutions.com/integration-with-tallyprime/ and
https://help.tallysolutions.com/xml-integration/)::

    <ENVELOPE>
      <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>...</TYPE>
        <ID>...</ID>
      </HEADER>
      <BODY>
        <DESC>
          <STATICVARIABLES>...</STATICVARIABLES>
          <TDL>...</TDL>
        </DESC>
      </BODY>
    </ENVELOPE>

Two request styles are used by this project, both documented Tally
integration patterns:

* **Canned report export** (``TYPE=Data``, ``ID=<report name>``) — used for
  Tally's built-in reports such as "Trial Balance". This is the pattern shown
  in Tally Solutions' own "Case Study I" developer reference.
* **Collection export** (``TYPE=Collection``) — used to fetch a list of
  objects (ledgers, vouchers, stock items, ...) of a given native Tally
  object ``TYPE`` (e.g. ``Ledger``, ``Voucher``, ``StockItem``) with an
  explicit ``FETCH`` field list. This is the standard, widely-documented
  approach for reading master/transaction data via a lightweight inline TDL
  ``COLLECTION`` definition, and is the pattern this project prefers for new
  reports because it does not require redefining Tally's on-screen report
  layout.

IMPORTANT — accuracy disclaimer
--------------------------------
The exact set of field names available on each native Tally object (e.g.
whether a given release exposes ``CLOSINGBALANCE`` vs. ``CLBALANCE`` for a
ledger) can vary between TallyPrime releases and has **not** been verified
against a live TallyPrime instance in this development environment (see
README/CHANGELOG "Testing" sections). Field lists are intentionally kept in
one place per object type (:mod:`tallyprime_mcp.tally.field_maps`, referenced
from the service layer) so they can be corrected without touching this
module's structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring

_XML_VERSION_HEADER = "1"


def format_tally_date(value: date) -> str:
    """Format a date the way TallyPrime's ``SVFROMDATE``/``SVTODATE`` static
    variables expect it: ``YYYYMMDD`` with no separators.

    This is the conventional format used throughout Tally's XML/TDL
    ecosystem for date-typed static variables. Verify against your
    TallyPrime version if reports appear to ignore the date range.
    """
    return value.strftime("%Y%m%d")


@dataclass
class StaticVariables:
    """Common ``STATICVARIABLES`` used across most requests."""

    current_company: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    export_format: str = "$$SysName:XML"
    extra: dict[str, str] = field(default_factory=dict)

    def to_element(self) -> Element:
        el = Element("STATICVARIABLES")
        SubElement(el, "SVEXPORTFORMAT").text = self.export_format
        if self.current_company:
            SubElement(el, "SVCURRENTCOMPANY").text = self.current_company
        if self.from_date:
            SubElement(el, "SVFROMDATE").text = format_tally_date(self.from_date)
        if self.to_date:
            SubElement(el, "SVTODATE").text = format_tally_date(self.to_date)
        for key, value in self.extra.items():
            SubElement(el, key).text = value
        return el


def _envelope_skeleton(tally_request: str, type_: str, id_: str) -> tuple[Element, Element]:
    """Build the ``<ENVELOPE><HEADER>...</HEADER><BODY><DESC>`` skeleton
    common to every request, returning ``(envelope, desc)`` so callers can
    attach their own body content under ``desc``.
    """
    envelope = Element("ENVELOPE")
    header = SubElement(envelope, "HEADER")
    SubElement(header, "VERSION").text = _XML_VERSION_HEADER
    SubElement(header, "TALLYREQUEST").text = tally_request
    SubElement(header, "TYPE").text = type_
    SubElement(header, "ID").text = id_

    body = SubElement(envelope, "BODY")
    desc = SubElement(body, "DESC")
    return envelope, desc


def build_report_export_request(
    report_id: str,
    static_variables: StaticVariables | None = None,
) -> bytes:
    """Build a ``TYPE=Data`` export request for one of TallyPrime's built-in
    canned reports (e.g. ``"Trial Balance"``).
    """
    envelope, desc = _envelope_skeleton("Export", "Data", report_id)
    desc.append((static_variables or StaticVariables()).to_element())
    return _serialize(envelope)


def build_collection_request(
    collection_name: str,
    native_type: str,
    fetch_fields: list[str],
    *,
    static_variables: StaticVariables | None = None,
    filters: list[str] | None = None,
) -> bytes:
    """Build a ``TYPE=Collection`` export request.

    Parameters
    ----------
    collection_name:
        Arbitrary name for the inline TDL collection (does not need to match
        any existing Tally report name).
    native_type:
        Tally's internal object type to enumerate, e.g. ``Ledger``,
        ``Voucher``, ``StockItem``, ``Group``, ``CostCentre``.
    fetch_fields:
        Native Tally field names to include in each returned record.
    filters:
        Optional named TDL ``SYSTEM: Formula`` style filter expressions to
        add as ``<FILTER>`` references in the collection. Advanced usage —
        left empty by default.
    """
    envelope, desc = _envelope_skeleton("Export", "Collection", collection_name)
    desc.append((static_variables or StaticVariables()).to_element())

    tdl = SubElement(desc, "TDL")
    tdl_message = SubElement(tdl, "TDLMESSAGE")
    collection = SubElement(
        tdl_message,
        "COLLECTION",
        attrib={"NAME": collection_name, "ISMODIFY": "No"},
    )
    SubElement(collection, "TYPE").text = native_type
    if fetch_fields:
        SubElement(collection, "FETCH").text = ", ".join(fetch_fields)
    if filters:
        SubElement(collection, "FILTER").text = ", ".join(filters)

    return _serialize(envelope)


def build_connection_check_request() -> bytes:
    """A minimal, side-effect-free request used purely to verify that
    TallyPrime is up and speaking its XML protocol.

    Requests the built-in "List of Companies" collection with a single
    field — this touches no specific company's data and works even if no
    company is loaded, which makes it a good liveness probe.
    """
    return build_collection_request(
        collection_name="MCPConnectionCheck",
        native_type="Company",
        fetch_fields=["NAME"],
    )


def _serialize(envelope: Element) -> bytes:
    return tostring(envelope, encoding="utf-8", xml_declaration=True)
