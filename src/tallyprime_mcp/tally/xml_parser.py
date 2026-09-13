"""Parses XML responses returned by TallyPrime's HTTP-XML gateway.

Security note
--------------
Parsing uses :mod:`defusedxml` rather than the standard library's
``xml.etree.ElementTree`` for *parsing* untrusted input (Tally's response is
"trusted" in the sense that it comes from the user's own local software, but
treating it as untrusted anyway is cheap insurance against XML bombs,
external entity expansion, etc. — see SECURITY.md).

Accuracy note
-------------
TallyPrime's exact response nesting has some documented variation depending
on request TYPE and Tally version (e.g. plain local XML export responses are
commonly reported to return repeated object tags such as ``<LEDGER>...`` at
shallow nesting rather than always under ``BODY><DATA><COLLECTION>``). Rather
than hard-coding one exact nesting depth and silently returning nothing when
a real installation nests differently, :func:`extract_records` searches the
whole response tree for elements matching the requested tag. This trades a
small amount of theoretical precision for robustness against version-specific
nesting differences — treat it as a starting point to refine once tested
against a live TallyPrime instance, not as a guarantee of correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as safe_ET

from tallyprime_mcp.tally.exceptions import TallyRequestError, TallyXMLParseError


@dataclass
class TallyRecord:
    """A single flattened record extracted from a Tally response (e.g. one
    ledger, one voucher). ``fields`` maps upper-case native Tally field
    names to their raw string values. ``name`` is populated when the
    element carried a ``NAME`` attribute (true for most master objects).
    """

    tag: str
    name: str | None
    fields: dict[str, str]


def parse_xml(raw: bytes) -> Element:
    """Safely parse raw XML bytes into an :class:`~xml.etree.ElementTree.Element`.

    Raises :class:`TallyXMLParseError` on anything that isn't well-formed
    XML, rather than letting a low-level parser exception escape.
    """
    if not raw or not raw.strip():
        raise TallyXMLParseError(
            "TallyPrime returned an empty response.",
            detail="Empty body — Tally may be busy, no company may be loaded, or the "
            "request type/ID was not recognised.",
        )
    try:
        return safe_ET.fromstring(raw)
    except Exception as exc:  # defusedxml raises various ParseError subclasses
        raise TallyXMLParseError(
            "TallyPrime's response could not be parsed as XML.",
            detail=str(exc),
        ) from exc


def check_for_tally_error(root: Element) -> None:
    """Raise :class:`TallyRequestError` if the parsed response represents an
    application-level error rather than data.

    Two error shapes are handled, both documented/commonly observed in
    Tally's XML integration:

    * ``<ENVELOPE><LINEERROR>...</LINEERROR></ENVELOPE>`` — Tally's classic
      "could not process this request" shape for local XML export/import.
    * ``<ENVELOPE><HEADER><STATUS>0</STATUS></HEADER>...`` combined with a
      ``<MSG>``/``<MSG.LIST>`` in the body — used by some Tally XML flows to
      signal a structured failure status.
    """
    if root.tag.upper() != "ENVELOPE":
        raise TallyXMLParseError(
            f"Unexpected XML root element {root.tag!r}; expected <ENVELOPE>.",
        )

    line_error = root.find("LINEERROR")
    if line_error is not None and (line_error.text or "").strip():
        raise TallyRequestError(
            "TallyPrime rejected the request.",
            detail=line_error.text.strip(),
        )

    # Some flows nest one or more LINEERROR-like messages under BODY/DATA
    for msg in root.iter("MSG"):
        text = (msg.text or "").strip()
        if text:
            raise TallyRequestError("TallyPrime reported an error.", detail=text)

    for elem in root.iter():
        if elem.tag.upper() == "ERROR" and (elem.text or "").strip():
            raise TallyRequestError(
                "TallyPrime reported an error.",
                detail=elem.text.strip(),
            )


def extract_records(root: Element, tag: str) -> list[TallyRecord]:
    """Extract every element matching ``tag`` (case-insensitive) anywhere in
    the tree, flattening each into a :class:`TallyRecord`.
    """
    tag_upper = tag.upper()
    records: list[TallyRecord] = []
    for elem in root.iter():
        if elem.tag.upper() != tag_upper:
            continue
        fields: dict[str, str] = {}
        for child in elem:
            key = child.tag.upper()
            value = (child.text or "").strip()
            if key in fields:
                # Repeated field (e.g. multi-line narration/address) — join.
                fields[key] = f"{fields[key]}\n{value}"
            else:
                fields[key] = value
        name = elem.attrib.get("NAME") or elem.attrib.get("Name")
        records.append(TallyRecord(tag=elem.tag, name=name, fields=fields))
    return records


def extract_single(root: Element, tag: str) -> TallyRecord | None:
    """Convenience wrapper for responses expected to contain at most one
    record of ``tag``."""
    records = extract_records(root, tag)
    return records[0] if records else None


def field_text(record: TallyRecord, *candidates: str, default: str = "") -> str:
    """Look up the first present field among ``candidates`` (case-insensitive
    native Tally field names), since exact field names vary across Tally
    versions/report styles for the same logical value.
    """
    for candidate in candidates:
        value = record.fields.get(candidate.upper())
        if value:
            return value
    return default


def parse_tally_date(raw: str) -> str | None:
    """Convert a Tally ``YYYYMMDD`` date string into ISO ``YYYY-MM-DD``.

    Returns ``None`` (rather than raising) for empty/unrecognised input,
    since date fields are often blank on non-transactional records and a
    missing date shouldn't fail an entire report.
    """
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def field_amount(record: TallyRecord, *candidates: str) -> float:
    """Parse a Tally amount field into a float.

    Tally represents debit amounts as positive and credit amounts as
    negative (or vice versa depending on report configuration) using plain
    decimal strings, occasionally with thousands separators or a trailing
    ``Dr``/``Cr`` suffix. This helper strips known non-numeric decoration;
    if a real response uses a format not handled here, it will raise
    :class:`TallyXMLParseError` rather than silently returning ``0.0``, so
    the gap is visible instead of hidden.
    """
    raw = field_text(record, *candidates)
    if not raw:
        return 0.0
    cleaned = raw.replace(",", "").strip()
    sign = 1.0
    upper = cleaned.upper()
    if upper.endswith("CR"):
        sign = -1.0
        cleaned = cleaned[:-2].strip()
    elif upper.endswith("DR"):
        cleaned = cleaned[:-2].strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        sign *= -1.0
        cleaned = cleaned[1:-1]
    try:
        return sign * float(cleaned)
    except ValueError as exc:
        raise TallyXMLParseError(
            f"Could not parse Tally amount field {raw!r} as a number.",
        ) from exc
