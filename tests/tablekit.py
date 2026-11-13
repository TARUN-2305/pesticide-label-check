"""Build synthetic RawTables from a compact grid spec (no PDF needed).

A spec row is a list of entries, one per grid column:
  "text"                 a 1x1 cell
  None                   a grid position covered by a merge (pdfplumber yields None)
  ("text", w, h)         a cell spanning w columns and h rows (covered positions must be None)
"""

from __future__ import annotations

from labelclaim.extract.model import Cell, RawRow, RawTable

Entry = str | tuple[str, int, int] | None
EDGES = (36.0, 135.0, 290.0, 378.0, 448.0, 520.0, 567.0)  # the insecticide p. 20 geometry
ROW_H = 21.0


def make_table(
    spec: list[list[Entry]],
    *,
    edges: tuple[float, ...] = EDGES,
    page: int = 20,
    index: int = 0,
    top: float = 100.0,
    doc_id: str = "doc",
) -> RawTable:
    rows: list[RawRow] = []
    for r, entries in enumerate(spec):
        cells: list[Cell | None] = []
        y0 = top + r * ROW_H
        for c, entry in enumerate(entries):
            if entry is None:
                cells.append(None)
                continue
            text, w, h = (entry, 1, 1) if isinstance(entry, str) else entry
            cells.append(Cell(text, (edges[c], y0, edges[c + w], y0 + h * ROW_H)))
        present = [x for x in cells if x is not None]
        bbox = (
            (min(x.bbox[0] for x in present), y0, max(x.bbox[2] for x in present), y0 + ROW_H)
            if present
            else (edges[0], y0, edges[-1], y0 + ROW_H)
        )
        rows.append(RawRow(tuple(cells), bbox))
    table_bbox = (edges[0], top, edges[-1], top + len(spec) * ROW_H)
    return RawTable(doc_id, page, index, table_bbox, tuple(rows))


def heading(text: str) -> list[Entry]:
    return [(text, 6, 1), None, None, None, None, None]
