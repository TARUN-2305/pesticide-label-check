"""Row classification (L1 §5.4). Rules are applied in order; the first match wins."""

from __future__ import annotations

import re

from labelclaim.extract.geometry import BandedRow
from labelclaim.extract.model import VALUE_COLS, Col, RowKind, Section

_SECTIONS: tuple[tuple[re.Pattern[str], Section], ...] = (
    (re.compile(r"agricultural use"), Section.INSECTICIDE_SINGLE),
    (re.compile(r"combination product"), Section.INSECTICIDE_COMBINATION),
    (re.compile(r"(?:1\.\s*)?fungicides single product formulations? use\.?"), Section.FUNGICIDE_SINGLE),
    (re.compile(r"(?:2\.\s*)?fungicides combination uses?\.?"), Section.FUNGICIDE_COMBINATION),
    (re.compile(r"public health use"), Section.OUT_OF_SCOPE),
    (re.compile(r"household insecticides?"), Section.OUT_OF_SCOPE),
    (re.compile(r"recommended chemicals by fao for locust control"), Section.OUT_OF_SCOPE),
)
NOTE = re.compile(r"^(?:➢|\*|note\b|for non-? ?agricultural use)", re.IGNORECASE)
_SENTENCE = re.compile(r"\b(?:is|are|will|shall|should|recommended|calculated|applied)\b", re.IGNORECASE)


def looks_like_note(text: str) -> bool:
    """A full-width cell that is an explanation, not a product heading: a note marker, a leading symbol
    ('^', ','), a colon ('Sugarcane: 6.25 lit/ha.'), or a sentence verb ('... is a manufacturing
    concentrate ...'). Found in the M1 audit: such cells had been taken as products (with no rows)."""
    stripped = text.strip()
    return bool(
        NOTE.match(stripped)
        or (stripped and not (stripped[0].isalnum() or stripped[0] == "("))
        or ":" in stripped
        or _SENTENCE.search(stripped)
    )


_HEADER_WORD = re.compile(r"(?i)\b(?:crop|common name|dosage|formulation|dilution|waiting|a\.\s?i\b)")
FORMULATIONS = (
    "EC|SC|WG|WP|WDG|WSG|GR|G|SL|CS|OD|FS|DP|DS|ZC|SE|EW|DC|SP|ME|SG|WS|GB|CG|DF|EO|ULV|UL|SO|ST|TB|"
    "CB|RB|BB|FU|GE|MC|PA|PC|TC|TK|SU|WT|LS|AF|AL|KN|HN|XL|P|D|DT|WDP|ES|OS|FF|RTU|L|EW/SE|"
    "Tablets?|Pellets?|Granules?|Dust|Powder|Paste|Cake|Bait|Block Bait|Gel|Conc"
)
_HEADING_TAIL = re.compile(rf"\b(?:{FORMULATIONS})\b\.?\s*(?:\([^)]*\)\s*)*$")


def section_of(text: str) -> Section | None:
    key = " ".join(text.lower().split())
    for pattern, section in _SECTIONS:
        if pattern.fullmatch(key):
            return section
    return None


def heading_like(text: str) -> bool:
    """A text line outside any table that reads like a product heading (ingredient ... % ... formulation)."""
    return bool(re.match(r"[A-Za-z]", text) and "%" in text and _HEADING_TAIL.search(text))


def is_header(texts: list[str]) -> bool:
    joined = " ".join(texts)
    return len({m.group(0).lower() for m in _HEADER_WORD.finditer(joined)}) >= 2 and not re.search(
        r"\d", joined
    )


def classify_row(row: BandedRow, *, continuation_allowed: bool) -> RowKind:  # noqa: PLR0911 (a rule list)
    """Classify one banded row. `continuation_allowed` is true only for the first content row of the first
    table on a page (rows split by a page break continue there)."""
    cells = row.nonempty_cells()
    if not cells:
        return RowKind.BLANK
    if row.full_width is not None:
        text = row.full_width.text
        if section_of(text) is not None:
            return RowKind.SECTION
        if looks_like_note(text):
            return RowKind.NOTE
        return RowKind.PRODUCT
    if is_header([c.text for c in cells]):
        return RowKind.HEADER
    if len(cells) == 1 and cells[0] in row.spanning():
        return RowKind.NOTE  # one cell spanning several columns: an explanatory note inside the table
    if continuation_allowed and (
        (row.bands[Col.CROP] and row.text(Col.CROP) == "") or not any(row.text(c) for c in VALUE_COLS)
    ):
        return RowKind.CONTINUATION  # the rest of a row split by a page (or table) break
    if any(row.text(c) for c in VALUE_COLS):
        return RowKind.DATA
    if all(row.covered(c) for c in VALUE_COLS) and row.text(Col.PEST):
        return RowKind.DATA  # every value comes from vertical merges above (or across the page break)
    return RowKind.UNMAPPED
