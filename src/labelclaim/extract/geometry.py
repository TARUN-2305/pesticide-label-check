"""Column bands and cell-to-band assignment (L1 §5.3, ADR-002).

Bands are derived per *block*: the rows between two full-width rows (product headings) of one table.
Implementation note (M1 audit, 2026-11-13): one pdfplumber table can hold several products whose Word
column widths differ (insecticide p. 8), so per-table bands mis-assign whole blocks.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from labelclaim.extract.model import Cell, Col, RawRow, RawTable

Bands = tuple[float, ...]  # 7 x-edges -> 6 bands
GRID = 2.0  # pt: edges are compared on a 2 pt grid
OUTER_TOLERANCE = 6.0  # pt: a block may inherit bands when its outer edges match within this
FULL_WIDTH = 0.9  # a heading row covers at least this fraction of the table width
SPAN_SHARE = 0.5  # a cell spans a band when it covers at least this share of the band's width


def _q(x: float) -> float:
    return round(x / GRID) * GRID


@dataclass(frozen=True)
class BandedRow:
    table: RawTable
    index: int
    bands: dict[Col, tuple[Cell, ...]]  # cells whose x-centre lies in each band; () = no own cell
    spans: dict[Col, Cell]  # band with no own cell -> the cell of this row that spans across it
    full_width: Cell | None  # a heading-like row (section title, product heading, note)
    outside: tuple[Cell, ...]  # cells whose centre lies outside every band
    absent: frozenset[Col] = frozenset()  # zero-width bands: the layout has no such column

    @property
    def row(self) -> RawRow:
        return self.table.rows[self.index]

    def text(self, col: Col) -> str:
        return " ".join(c.text for c in self.bands[col] if c.text)

    def covered(self, col: Col) -> bool:
        """True when this row has no cell of its own in `col` (a vertical or horizontal merge)."""
        return not self.bands[col]

    def nonempty_cells(self) -> tuple[Cell, ...]:
        return tuple(c for c in self.row.cells if c is not None and c.text)

    def spanning(self) -> tuple[Cell, ...]:
        """Cells of this row that span more than one band."""
        seen: list[Cell] = []
        for cell in self.spans.values():
            if cell not in seen:
                seen.append(cell)
        return tuple(seen)


def heading_cell(table: RawTable, index: int) -> Cell | None:
    """The text cell of a heading-like row: at most 2 cells, one with text (the leftmost), together
    spanning >= 90 % of the table (e.g. fungicide p. 13 'Flutriafol 23% w/w SC' + an empty cell)."""
    present = [c for c in table.rows[index].cells if c is not None]
    texts = [c for c in present if c.text]
    width = table.bbox[2] - table.bbox[0]
    if not (1 <= len(present) <= 2 and len(texts) == 1 and width > 0):
        return None
    extent = max(c.bbox[2] for c in present) - min(c.bbox[0] for c in present)
    leftmost = min(present, key=lambda c: c.bbox[0])
    return texts[0] if extent >= FULL_WIDTH * width and texts[0] is leftmost else None


SLIVER = 8.0  # pt: an empty cell narrower than this is an artefact of misaligned lines (fungicide p. 77)


def _full_cells(row: RawRow) -> list[Cell]:
    return [c for c in row.cells if c is not None and (c.text or c.bbox[2] - c.bbox[0] >= SLIVER)]


def _pad(bands: Bands | None) -> Bands | None:
    return None if bands is None else (*bands, bands[-1])


def _modal(table: RawTable, rows: range, width: int, min_rows: int = 1) -> Bands | None:
    """The modal x-edge signature of full rows with `width` cells (slivers ignored), if it occurs in at
    least `min_rows` rows. A full row starts in the first grid column and reaches the table's right edge."""
    counts: Counter[Bands] = Counter()
    first_seen: dict[Bands, int] = {}
    exact: dict[Bands, Bands] = {}  # rounded signature -> the unrounded edges of its first row
    for i in rows:
        row = table.rows[i]
        cells = _full_cells(row)
        if len(cells) != width or row.cells[0] is None:
            continue
        if (
            abs(cells[0].bbox[0] - table.bbox[0]) > OUTER_TOLERANCE
            or abs(cells[-1].bbox[2] - table.bbox[2]) > OUTER_TOLERANCE
        ):
            continue
        sig = (*(_q(c.bbox[0]) for c in cells), _q(cells[-1].bbox[2]))
        if list(sig) != sorted(set(sig)):  # edges must strictly increase
            continue
        counts[sig] += 1
        if sig not in first_seen:
            first_seen[sig] = i
            exact[sig] = (*(c.bbox[0] for c in cells), cells[-1].bbox[2])
    if not counts:
        return None
    best = max(counts, key=lambda s: (counts[s], -first_seen[s]))
    return exact[best] if counts[best] >= min_rows else None


def row_bands(table: RawTable, previous: Bands | None) -> tuple[list[Bands | None], bool]:
    """Bands for every row of each block (rows between heading rows), in this order of preference:
    1. the block's 6-cell signature; 2. the table's 6-cell signature; 3. `previous`, when the outer edges
    match and every cell edge of the block aligns with it (fungicide p. 20: every row has one cell
    spanning two columns, so no row has 6 cells; the 3-column rodenticide table on insecticide p. 7 does
    not align); 4. the block's, then the table's, 5-cell signature seen in >= 2 rows (a layout with no
    waiting-period column, insecticide p. 51; WAIT becomes a zero-width band).
    Returns (per-row bands, whether any block used `previous`)."""
    n = len(table.rows)
    everything = range(n)
    table6 = _modal(table, everything, 6)
    table5 = _pad(_modal(table, everything, 5, min_rows=2))
    result: list[Bands | None] = [None] * n
    inherited = False
    current = previous
    start = 0
    for end in [*(i for i in range(n) if heading_cell(table, i) is not None), n]:
        block = range(start, end)
        bands = _modal(table, block, 6) or table6
        if (
            bands is None
            and current is not None
            and _outer_match(current, table)
            and all(aligned(table, i, current) for i in block)
        ):
            bands = current
            inherited = inherited or any(_has_text(table, i) for i in block)
        if bands is None:
            bands = _pad(_modal(table, block, 5, min_rows=2)) or table5
        for i in block:
            result[i] = bands
        if end < n:
            result[end] = bands or current  # the heading row itself only needs the outer edges
        current = bands or current
        start = end + 1
    return result, inherited


def _outer_match(bands: Bands | None, table: RawTable) -> bool:
    return (
        bands is not None
        and abs(bands[0] - table.bbox[0]) <= OUTER_TOLERANCE
        and abs(bands[-1] - table.bbox[2]) <= OUTER_TOLERANCE
    )


def _has_text(table: RawTable, i: int) -> bool:
    return any(c is not None and c.text for c in table.rows[i].cells)


def band_row(table: RawTable, index: int, bands: Bands) -> BandedRow:
    """Assign each cell to the band containing its x-centre; record bands it spans without owning."""
    absent = frozenset(col for col in Col if bands[col + 1] - bands[col] <= 0)
    head = heading_cell(table, index)
    if head is not None:
        return BandedRow(table, index, dict.fromkeys(Col, ()), {}, head, (), absent)
    present = sorted(
        (c for c in table.rows[index].cells if c is not None), key=lambda c: (round(c.bbox[1]), c.bbox[0])
    )
    assigned: dict[Col, list[Cell]] = {col: [] for col in Col}
    covers: dict[Col, Cell] = {}
    outside: list[Cell] = []
    for cell in present:
        spanned = [col for col in Col if _share(cell, bands, col) >= SPAN_SHARE]
        if len(spanned) >= 2:  # a cell across several columns belongs to the leftmost (reading order)
            assigned[spanned[0]].append(cell)
            for col in spanned[1:]:
                covers.setdefault(col, cell)
            continue
        owner = _band_of((cell.bbox[0] + cell.bbox[2]) / 2, bands)
        if owner is None:
            outside.append(cell)
        else:
            assigned[owner].append(cell)
    spans = {col: cell for col, cell in covers.items() if not assigned[col]}
    return BandedRow(
        table, index, {c: tuple(v) for c, v in assigned.items()}, spans, None, tuple(outside), absent
    )


def aligned(table: RawTable, index: int, bands: Bands, tol: float = OUTER_TOLERANCE) -> bool:
    """True when every cell edge of the row lies near a band edge (used for blocks with inherited bands)."""
    for cell in _full_cells(table.rows[index]):
        for x in (cell.bbox[0], cell.bbox[2]):
            if min(abs(x - e) for e in bands) > tol:
                return False
    return True


def _share(cell: Cell, bands: Bands, col: Col) -> float:
    lo, hi = bands[col], bands[col + 1]
    if hi <= lo:
        return 0.0
    return max(0.0, min(cell.bbox[2], hi) - max(cell.bbox[0], lo)) / (hi - lo)


def _band_of(x: float, bands: Bands) -> Col | None:
    if x < bands[0] - GRID or x > bands[-1] + GRID:
        return None
    for i in range(len(bands) - 1):
        if x < bands[i + 1]:
            return Col(i)
    return max((Col(i) for i in range(len(bands) - 1) if bands[i + 1] > bands[i]), default=None)
