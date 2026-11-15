"""Text that crosses a table's drawn cell lines (L1 §16; measured in reports/E1/edge_audit.md).

pdfplumber gives each character to the cell that holds its centre. The register's tables are drawn by a word
processor whose text sometimes runs past a column line ("infestans)" on fungicide p. 60 ends 8 pt past it,
so "s)" lands in the dose cell), sits in a cell with no drawn borders (insecticide p. 25, "Cotton"), or is
drawn over other text (fungicide p. 82). None of these is repaired here: each becomes a defect, then an
anomaly, which a reviewed correction (ADR-007) or allow-list entry must cover before a release.

Pure functions over glyphs, so the thresholds are unit-tested without a PDF.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from labelclaim.extract.model import BBox, EdgeDefect

RUN_GAP = 0.45  # x font size: a word space is ~0.25 em; the padding between two cells is >= 0.7 em here
STRADDLE_GAP = 0.5  # pt: real straddles measured -0.12..+0.05; closest pair of separate texts 0.70
OVERLAP = 0.5  # two glyphs overlap when they share more than this fraction of the narrower one's width

Kind = Literal["orphan", "overlap", "straddle", "adjacent"]


@dataclass(frozen=True)
class Glyph:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float

    def owner(self, cells: Sequence[BBox]) -> int | None:
        """The cell holding this glyph's centre, as pdfplumber decides (first match)."""
        hm, vm = (self.x0 + self.x1) / 2, (self.top + self.bottom) / 2
        for i, (x0, top, x1, bottom) in enumerate(cells):
            if x0 <= hm < x1 and top <= vm < bottom:
                return i
        return None


def runs(glyphs: Sequence[Glyph]) -> list[list[Glyph]]:
    """Glyphs grouped by line (`top` to the nearest point, as measured), then split at gaps wider than
    RUN_GAP em: one run is one stretch of text a reader would read without a column break."""
    lines: dict[float, list[Glyph]] = {}
    for g in glyphs:
        if not g.text.isspace():
            lines.setdefault(round(g.top), []).append(g)
    out: list[list[Glyph]] = []
    for top in sorted(lines):
        line = sorted(lines[top], key=lambda g: g.x0)
        run = [line[0]]
        for g in line[1:]:
            if g.x0 - run[-1].x1 > RUN_GAP * g.size:
                out.append(run)
                run = []
            run.append(g)
        out.append(run)
    return out


def _overlapping(run: Sequence[Glyph]) -> bool:
    for a, b in itertools.pairwise(run):
        narrower = min(a.x1 - a.x0, b.x1 - b.x0)
        if narrower > 0 and a.x1 - b.x0 > OVERLAP * narrower:
            return True
    return False


def classify_run(run: Sequence[Glyph], cells: Sequence[BBox]) -> tuple[Kind | None, float | None]:
    """(kind, tightest cut gap) for one run; kind None when the run lies in one cell and is clean."""
    owners = [g.owner(cells) for g in run]
    gaps = [b.x0 - a.x1 for a, b, oa, ob in zip(run, run[1:], owners, owners[1:], strict=False) if oa != ob]
    cut = round(min(gaps), 2) if gaps else None
    if None in owners:
        return "orphan", cut
    if _overlapping(run):
        return "overlap", cut
    if cut is None:
        return None, None
    return ("straddle" if cut < STRADDLE_GAP else "adjacent"), cut


def defects(glyphs: Sequence[Glyph], cells: Sequence[BBox]) -> list[EdgeDefect]:
    """Every orphan, overlap and straddle run among `glyphs` (the glyphs inside one table)."""
    out: list[EdgeDefect] = []
    for run in runs(glyphs):
        kind, cut = classify_run(run, cells)
        if kind is None or kind == "adjacent":
            continue
        text = "".join(g.text for g in run)
        out.append(EdgeDefect(kind, text, min(g.top for g in run), max(g.bottom for g in run), cut))
    return out
