"""Cross-page assembly state machine: section -> product -> use rows (L1 §5.5).

Implementation notes from the M1 audit of the real register (2026-11-13), each covered by a test:
- A row split by a page or table break continues in the first content row of the next table (or in
  unruled text at the top of the next page); it is appended to the previous use row.
- Inside a table, a row with no crop text whose own value cells are empty, or whose value texts finish a
  value left unfinished on the row above ("136 (12 + 124) –"), is the rest of that row (fungicide p. 76).
- A cell covered by a merge that started on the previous page stays carried for the rest of the table.
- Unruled rows (text lines outside any table, fungicide p. 15) are rebuilt from their words, using the
  current bands, as one virtual row. Lines after a footnote marker ('*') on a page are footnotes.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from labelclaim.extract.classify import NOTE, classify_row, heading_like, looks_like_note, section_of
from labelclaim.extract.geometry import OUTER_TOLERANCE, BandedRow, Bands, band_row, heading_cell, row_bands
from labelclaim.extract.model import (
    VALUE_COLS,
    Anomaly,
    BBox,
    Col,
    Field,
    PageItem,
    ProductHeading,
    RawRow,
    RawTable,
    RowKind,
    RowRef,
    Section,
    TextLine,
    UseRow,
)

_PAGE_NUMBER = re.compile(r"\d{1,3}\.?|➢")
_UNFINISHED = re.compile(r"(?:[–\-+(,/&]|\bto|\band|\bor)\s*$", re.IGNORECASE)
MERGE_TOLERANCE = 1.0  # pt
VIRTUAL_TABLE = -1  # table index used in RowRefs of rows rebuilt from unruled text


def unfinished(text: str) -> bool:
    """A value that visibly continues on the next line or row: a trailing operator or an open bracket."""
    return bool(_UNFINISHED.search(text)) or text.count("(") > text.count(")")


def _continues(previous: str, text: str) -> bool:
    return unfinished(previous) or text.startswith("(") or text[:1].islower()


@dataclass
class _Builder:
    product: ProductHeading
    fields: dict[Col, Field]
    rows: list[RowRef]
    notes: list[str] = field(default_factory=list)


@dataclass
class Assembly:
    uses: list[UseRow]
    products: list[ProductHeading]
    anomalies: list[Anomaly]
    kinds: Counter[str]


class Assembler:
    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        self.section: Section | None = None
        self.product: ProductHeading | None = None
        self.product_notes: dict[int, list[str]] = {}
        self.last: _Builder | None = None
        self.bands: Bands | None = None
        self.builders: list[_Builder] = []
        self.products: list[ProductHeading] = []
        self.anomalies: list[Anomaly] = []
        self.kinds: Counter[str] = Counter()
        self._loose: list[TextLine] = []
        self._continued: dict[RowRef, _Builder] = {}  # continuation row -> the use it was appended to
        self._page_has_table = False
        self._footnotes = False
        self._virtual = 0

    @property
    def in_scope(self) -> bool:
        return self.section is not None and self.section is not Section.OUT_OF_SCOPE

    def _anomaly(self, code: str, page: int, table: int, row: int, detail: str) -> None:
        self.anomalies.append(Anomaly(code, self.doc_id, page, table, row, detail[:200]))

    def _set_section(self, section: Section) -> None:
        self.section, self.product, self.last = section, None, None

    def _set_product(self, text: str, page: int, bbox: BBox) -> None:
        if self.section is None:  # pragma: no cover - callers check in_scope first
            raise RuntimeError("product heading outside any section")
        self.product = ProductHeading(self.doc_id, self.section, text, page, bbox)
        self.products.append(self.product)
        self.last = None

    def _note(self, text: str) -> None:
        if self.last is not None:
            self.last.notes.append(text)
        elif self.product is not None:
            self.product_notes.setdefault(len(self.products) - 1, []).append(text)

    def _same_product(self) -> bool:
        return self.last is not None and self.last.product is self.product

    # -- pages and text outside tables ---------------------------------------------------------------
    def end_page(self) -> None:
        self._flush_loose()
        self._page_has_table = False
        self._footnotes = False

    def feed_line(self, line: TextLine) -> None:
        section = section_of(line.text)
        if section is not None:
            self._flush_loose()
            self._set_section(section)
            return
        if not self.in_scope or _PAGE_NUMBER.fullmatch(line.text):
            return
        if line.text.startswith("*"):
            self._footnotes = True
        if self._footnotes or NOTE.match(line.text):
            self._flush_loose()
            self._note(line.text)
        elif heading_like(line.text):
            self._flush_loose()
            self._set_product(line.text, line.page, (0.0, line.top, 0.0, line.top))
        else:
            self._loose.append(line)

    def _flush_loose(self) -> None:
        """Rebuild buffered unruled lines as one virtual row in the current bands."""
        lines, self._loose = self._loose, []
        if not lines:
            return
        page = lines[0].page
        words = tuple(w for line in lines for w in line.words)
        bands = self.bands
        x0 = min((w.bbox[0] for w in words), default=0.0)
        x1 = max((w.bbox[2] for w in words), default=0.0)
        if (
            not words
            or bands is None
            or self.product is None
            or x0 < bands[0] - OUTER_TOLERANCE
            or x1 > bands[-1] + OUTER_TOLERANCE
        ):
            for line in lines:
                self._anomaly("TEXT_OUTSIDE_TABLE", page, VIRTUAL_TABLE, -1, line.text)
            return
        top, bottom = min(w.bbox[1] for w in words), max(w.bbox[3] for w in words)
        self._virtual += 1
        table = RawTable(
            self.doc_id,
            page,
            VIRTUAL_TABLE,
            (bands[0], top, bands[-1], bottom),
            (RawRow(words, (x0, top, x1, bottom)),),
        )
        row = band_row(table, 0, bands)
        ref = (page, VIRTUAL_TABLE, self._virtual)
        if not self._page_has_table and self._same_product():
            self.kinds["unruled_continuation"] += 1
            self._continue(row, ref)
        elif row.text(Col.CROP) and any(row.text(c) for c in VALUE_COLS):
            self.kinds["unruled_data"] += 1
            self._data(row, ref, [], at_table_start=False)
        elif self._continues_last(row):
            self.kinds["unruled_continuation"] += 1
            self._continue(row, ref)
        else:
            for line in lines:
                self._anomaly("TEXT_OUTSIDE_TABLE", page, VIRTUAL_TABLE, -1, line.text)

    # -- tables -------------------------------------------------------------------------------------
    def feed_table(self, table: RawTable) -> None:
        self._flush_loose()
        self._page_has_table = True
        per_row, inherited = row_bands(table, self.bands)
        if inherited and self.in_scope:
            self._anomaly(
                "BANDS_INHERITED", table.page, table.index, -1, "a block without full rows; previous bands"
            )
        seen: list[BandedRow] = []
        carried: set[Col] = set()
        content_started = False
        for i, bands in enumerate(per_row):
            if bands is None:
                self._unbanded_row(table, i)
                continue
            self.bands = bands
            row = band_row(table, i, bands)
            kind = classify_row(row, continuation_allowed=not content_started)
            if kind is RowKind.SECTION:
                section = section_of(row.full_width.text) if row.full_width is not None else None
                if section is None:  # pragma: no cover - classify_row guarantees it
                    raise RuntimeError("SECTION row without a section title")
                self._set_section(section)
                content_started = True
                continue
            if not self.in_scope:
                continue
            if kind in (RowKind.DATA, RowKind.UNMAPPED) and content_started and self._continues_last(row):
                kind = RowKind.CONTINUATION
            elif kind is RowKind.CONTINUATION and self._is_full_row(row):
                kind = RowKind.DATA  # a new row with a visually blank crop at the top of a table (p. 8)
            self.kinds[kind.value] += 1
            ref = (table.page, table.index, i)
            if kind in (RowKind.BLANK, RowKind.HEADER):
                pass
            elif kind is RowKind.PRODUCT:
                cell = row.full_width or row.nonempty_cells()[0]  # a heading cell may stop short (p. 59)
                self._set_product(cell.text, table.page, cell.bbox)
                content_started = True
            elif kind is RowKind.NOTE:
                self._note(" ".join(c.text for c in row.nonempty_cells()))
                content_started = True
            elif kind is RowKind.CONTINUATION:
                self._continue(row, ref)
                content_started = True
            elif kind is RowKind.DATA:
                carried = self._data(row, ref, seen, at_table_start=not content_started, carried=carried)
                content_started = True
            else:
                texts = " | ".join(c.text for c in row.nonempty_cells())
                self._anomaly("UNMAPPED_ROW", table.page, table.index, i, texts)
            seen.append(row)

    def _unbanded_row(self, table: RawTable, i: int) -> None:
        """A row in a block with no usable bands: only a heading-like row can be read."""
        cell = heading_cell(table, i)
        if cell is not None:
            section = section_of(cell.text)
            if section is not None:
                self._set_section(section)
            elif self.in_scope and looks_like_note(cell.text):
                self._note(cell.text)
            elif self.in_scope:
                self._set_product(cell.text, table.page, cell.bbox)
        elif self.in_scope and any(c is not None and c.text for c in table.rows[i].cells):
            texts = " | ".join(c.text for c in table.rows[i].cells if c is not None and c.text)
            self._anomaly("UNMAPPED_TABLE", table.page, table.index, i, texts)

    def _continues_last(self, row: BandedRow) -> bool:
        """No crop text, and either every own value cell is empty (but not every value is merged from
        above), or every value text continues the last row's value: it finishes a value left unfinished
        there, or starts with '(' or a lower-case letter ('(depending upon tree size)', fungicide p. 54)."""
        if not self._same_product() or self.last is None or row.text(Col.CROP):
            return False
        if (
            row.text(Col.PEST)
            and not self.last.fields[Col.PEST].text
            and not any(row.text(c) for c in VALUE_COLS)
        ):
            return (
                True  # the last row's pest cell was empty: its text sits one grid row lower (fungicide p. 81)
            )
        own = [c for c in VALUE_COLS if not row.covered(c)]
        texted = [c for c in own if row.text(c)]
        if not texted:
            return bool(own) and bool(row.text(Col.PEST))
        last = self.last
        return all(_continues(last.fields[c].text, row.text(c)) for c in texted)

    def _is_full_row(self, row: BandedRow) -> bool:
        """At least two value cells hold numbers that do not just continue the last row's values."""
        last = self.last
        fresh = [
            c
            for c in VALUE_COLS
            if re.search(r"\d", row.text(c))
            and not (last is not None and _continues(last.fields[c].text, row.text(c)))
        ]
        return len(fresh) >= 2

    def _continue(self, row: BandedRow, ref: RowRef) -> None:
        if self.last is None or not self._same_product():
            self._anomaly("ORPHAN_CONTINUATION", *ref, " | ".join(c.text for c in row.nonempty_cells()))
            return
        self._continued[ref] = self.last
        for col in Col:
            text = row.text(col)
            if not text:
                continue
            old = self.last.fields[col]
            boxes = tuple((ref[0], c.bbox) for c in row.bands[col] if c.text)
            joined = f"{old.text} {text}" if old.text else text
            self.last.fields[col] = Field(joined, old.bboxes + boxes, old.source, old.origin, old.span_of)
        self.last.rows.append(ref)

    def _data(
        self,
        row: BandedRow,
        ref: RowRef,
        seen: list[BandedRow],
        *,
        at_table_start: bool,
        carried: set[Col] | None = None,
    ) -> set[Col]:
        """Emit one use row. Returns the columns still carried from the previous page in this table."""
        carried = set(carried or ())
        if self.product is None:
            self._anomaly("ORPHAN_ROW", *ref, " | ".join(c.text for c in row.nonempty_cells()))
            return carried
        if row.outside:
            self._anomaly("BAND_OVERFLOW", *ref, " | ".join(c.text for c in row.outside))
        same_product = self._same_product()
        fields: dict[Col, Field] = {}
        for col in Col:
            if col in row.absent:
                fields[col] = Field("", (), "absent")
                continue
            if not row.covered(col):
                carried.discard(col)
                text = row.text(col)
                if col is Col.CROP and text == "":
                    if not same_product or self.last is None:
                        self._anomaly("INCOMPLETE_ROW", *ref, "empty crop with no row above")
                        return carried
                    prev = self.last.fields[Col.CROP]
                    fields[col] = Field(prev.text, prev.bboxes, "blank", self.last.rows[0])
                    continue
                if col is Col.PEST and fields[Col.CROP].source == "blank" and self.last is not None:
                    fields[col] = self._blank_row_pest(row, ref)
                    continue
                fields[col] = Field(text, tuple((ref[0], c.bbox) for c in row.bands[col] if c.text), "cell")
                continue
            spanner = row.spans.get(col)
            if spanner is not None:
                owner = next(c for c in Col if spanner in row.bands[c])
                fields[col] = Field("", ((ref[0], spanner.bbox),), "spanned", ref, owner)
                continue
            anchor = _find_anchor(seen, row, col)
            target = self._continued.get(anchor.origin) if anchor is not None and anchor.origin else None
            if target is not None and target.product is self.product:
                # the merged cell started on the previous page (insecticide p. 15, fungicide p. 75): its
                # top part here is only the tail of a value already completed on the use it continues
                prev = target.fields[col]
                fields[col] = Field(prev.text, prev.bboxes, "carried", target.rows[0], prev.span_of)
            elif anchor is not None:
                fields[col] = anchor
            elif (at_table_start or col in carried) and same_product and self.last is not None:
                prev = self.last.fields[col]
                fields[col] = Field(prev.text, prev.bboxes, "carried", self.last.rows[0], prev.span_of)
                carried.add(col)
            else:
                self._anomaly("DANGLING_MERGE", *ref, f"{col.name} covered with no anchor")
                fields[col] = Field("", (), "cell")
        builder = _Builder(self.product, fields, [ref])
        self.builders.append(builder)
        self.last = builder
        return carried

    def _blank_row_pest(self, row: BandedRow, ref: RowRef) -> Field:
        """Pest of a row whose crop cell is blank ('same as above'): an empty pest is the same pest; a pest
        that finishes the last row's unfinished pest is appended to it and shared (fungicide p. 38/39:
        one pest split by the page break, with a second application method on the next page)."""
        assert self.last is not None  # noqa: S101 - caller checks
        prev = self.last.fields[Col.PEST]
        text = row.text(Col.PEST)
        own = tuple((ref[0], c.bbox) for c in row.bands[Col.PEST] if c.text)
        if not text:
            return Field(prev.text, prev.bboxes, "blank", self.last.rows[0])
        if unfinished(prev.text):
            joined = Field(f"{prev.text} {text}", prev.bboxes + own, prev.source, prev.origin)
            self.last.fields[Col.PEST] = joined
            self.last.rows.append(ref)
            return Field(joined.text, joined.bboxes, "blank", self.last.rows[0])
        return Field(text, own, "cell")

    def finish(self) -> Assembly:
        self._flush_loose()
        notes = self.product_notes
        products = [
            ProductHeading(p.doc_id, p.section, p.text, p.page, p.bbox, tuple(notes.get(i, ())))
            for i, p in enumerate(self.products)
        ]
        remap = {id(old): new for old, new in zip(self.products, products, strict=True)}
        uses = [
            UseRow(remap[id(b.product)], dict(b.fields), tuple(b.rows), tuple(b.notes)) for b in self.builders
        ]
        return Assembly(uses, products, list(self.anomalies), self.kinds)


def _find_anchor(seen: list[BandedRow], row: BandedRow, col: Col) -> Field | None:
    """The cell in band `col` of an earlier row of this table whose box vertically covers `row` (F4)."""
    top, bottom = row.row.bbox[1], row.row.bbox[3]
    for earlier in reversed(seen):
        for cell in earlier.bands[col]:
            if cell.bbox[1] <= top + MERGE_TOLERANCE and cell.bbox[3] >= bottom - MERGE_TOLERANCE:
                ref = (earlier.table.page, earlier.table.index, earlier.index)
                return Field(cell.text, ((ref[0], cell.bbox),), "merged", ref)
    return None


def assemble(doc_id: str, pages: Iterable[tuple[int, list[PageItem]]]) -> Assembly:
    assembler = Assembler(doc_id)
    for _page, items in pages:
        for item in items:
            if isinstance(item, TextLine):
                assembler.feed_line(item)
            else:
                assembler.feed_table(item)
        assembler.end_page()
    return assembler.finish()
