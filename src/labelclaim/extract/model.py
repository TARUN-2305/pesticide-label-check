"""Data types shared by the extraction stages (L1 §4). All frozen; geometry in PDF points, top-left origin."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Literal

BBox = tuple[float, float, float, float]  # x0, top, x1, bottom


@dataclass(frozen=True)
class Cell:
    text: str
    bbox: BBox


@dataclass(frozen=True)
class RawRow:
    cells: tuple[Cell | None, ...]  # None = grid position covered by a merged cell (F4)
    bbox: BBox


@dataclass(frozen=True)
class EdgeDefect:
    """Text that crosses the table's drawn cell lines (L1 §16): "orphan" (in no cell), "overlap" (glyphs
    drawn over each other) or "straddle" (a cell line cuts a word). `text` has no spaces: the register's
    PDFs encode none."""

    kind: Literal["orphan", "overlap", "straddle"]
    text: str
    top: float
    bottom: float
    cut_gap: float | None  # pt across the tightest cut between two cells; None when there is no cut


@dataclass(frozen=True)
class RawTable:
    doc_id: str
    page: int
    index: int
    bbox: BBox
    rows: tuple[RawRow, ...]
    defects: tuple[EdgeDefect, ...] = ()


@dataclass(frozen=True)
class TextLine:
    """A line of page text outside every table, with its words (each a Cell) for unruled rows."""

    doc_id: str
    page: int
    top: float
    text: str
    words: tuple[Cell, ...] = ()


PageItem = RawTable | TextLine


class Col(IntEnum):
    CROP = 0
    PEST = 1
    DOSE_AI = 2
    DOSE_FORM = 3
    DILUTION = 4
    WAIT = 5


VALUE_COLS: tuple[Col, ...] = (Col.DOSE_AI, Col.DOSE_FORM, Col.DILUTION, Col.WAIT)

RowRef = tuple[int, int, int]  # page, table index, row index


@dataclass(frozen=True)
class Field:
    """One logical column value of a use row.

    source: "cell" (this row's own cells, possibly empty), "merged" (vertical-merge anchor in the same
    table), "carried" (covered cell at the top of a table: the merge continues from the previous page),
    "blank" (an explicitly empty crop cell read as 'same crop as above'), "spanned" (no own cell: a cell
    of this row whose x-centre is in band `span_of` spans across this column; text is "" by design, so a
    value printed once in the PDF is never duplicated into a second column), "absent" (the table's layout
    has no such column, e.g. no waiting-period column in the seed-treatment tables), "corrected" (a
    reviewed correction replaced the extracted text; `bboxes` still name the page area, ADR-007).
    """

    text: str
    bboxes: tuple[tuple[int, BBox], ...]  # (page, bbox) pairs the text was read from
    source: Literal["cell", "merged", "carried", "blank", "spanned", "absent", "corrected"]
    origin: RowRef | None = None
    span_of: Col | None = None


class Section(Enum):
    INSECTICIDE_SINGLE = "insecticide_single"
    INSECTICIDE_COMBINATION = "insecticide_combination"
    FUNGICIDE_SINGLE = "fungicide_single"
    FUNGICIDE_COMBINATION = "fungicide_combination"
    OUT_OF_SCOPE = "out_of_scope"


class RowKind(Enum):
    BLANK = "blank"
    HEADER = "header"
    SECTION = "section"
    NOTE = "note"
    PRODUCT = "product"
    DATA = "data"
    CONTINUATION = "continuation"
    UNMAPPED = "unmapped"


@dataclass(frozen=True)
class Anomaly:
    code: str
    doc_id: str
    page: int
    table: int
    row: int
    detail: str


@dataclass(frozen=True)
class ProductHeading:
    doc_id: str
    section: Section
    text: str
    page: int
    bbox: BBox
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class UseRow:
    product: ProductHeading
    fields: dict[Col, Field]
    rows: tuple[RowRef, ...]  # every raw row that contributed (the first is the data row)
    notes: tuple[str, ...] = ()
    corrections: tuple[tuple[str, str, str], ...] = ()  # (correction id, column name, text before), ADR-007

    @property
    def page_first(self) -> int:
        return self.rows[0][0]

    @property
    def page_last(self) -> int:
        return max(r[0] for r in self.rows)
