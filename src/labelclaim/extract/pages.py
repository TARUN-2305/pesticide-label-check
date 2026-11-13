"""pdfplumber adapter: the only module that imports pdfplumber (L1 §3, §5.2)."""

from __future__ import annotations

import bisect
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pdfplumber
from pdfplumber.utils.text import extract_text

from labelclaim.extract.model import BBox, Cell, PageItem, RawRow, RawTable, TextLine

_WS = re.compile(r"\s+")


def clean(text: str | None) -> str:
    """NFC, drop soft hyphens, collapse all whitespace (newlines inside cells) to single spaces."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).replace("­", "")
    return _WS.sub(" ", text).strip()


def _bbox(raw: Any) -> BBox:
    x0, top, x1, bottom = raw
    return (round(float(x0), 2), round(float(top), 2), round(float(x1), 2), round(float(bottom), 2))


def _mid_in(obj: dict[str, Any], bbox: BBox) -> bool:
    v_mid = (obj["top"] + obj["bottom"]) / 2
    h_mid = (obj["x0"] + obj["x1"]) / 2
    return bool(bbox[0] <= h_mid < bbox[2] and bbox[1] <= v_mid < bbox[3])


def _inside(inner: BBox, outer: BBox, tol: float = 1.0) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def read_document(
    path: Path, doc_id: str, pages: range | None = None
) -> Iterator[tuple[int, list[PageItem]]]:
    """Yield (page_number, items): tables and the text lines outside them, ordered by `top`.

    Tables nested inside another table's box (lines drawn inside a cell, fungicide p. 68) are dropped:
    their characters already belong to the enclosing cell.
    """
    with pdfplumber.open(path) as pdf:
        numbers = pages if pages is not None else range(1, len(pdf.pages) + 1)
        for number in numbers:
            page = pdf.pages[number - 1]
            items: list[tuple[float, float, PageItem]] = []
            found = page.find_tables()
            boxes = [_bbox(t.bbox) for t in found]
            keep = [
                i
                for i, box in enumerate(boxes)
                if not any(j != i and _inside(box, other) and box != other for j, other in enumerate(boxes))
            ]
            table_boxes = [boxes[i] for i in keep]
            for index, i in enumerate(keep):
                table = found[i]
                texts = table.extract()
                rows = tuple(
                    RawRow(
                        cells=tuple(
                            None if cell is None else Cell(clean(text), _bbox(cell))
                            for cell, text in zip(row.cells, row_texts, strict=True)
                        ),
                        bbox=_bbox(row.bbox),
                    )
                    for row, row_texts in zip(table.rows, texts, strict=True)
                )
                box = boxes[i]
                items.append((box[1], box[0], RawTable(doc_id, number, index, box, rows)))

            def outside_tables(obj: dict[str, Any], tboxes: list[BBox] = table_boxes) -> bool:
                return obj.get("object_type") != "char" or not any(_mid_in(obj, b) for b in tboxes)

            outside = page.filter(outside_tables)
            for line in _lines(outside.extract_words()):
                text = clean(" ".join(w.text for w in line))
                if text:
                    top = min(w.bbox[1] for w in line)
                    x0 = min(w.bbox[0] for w in line)
                    items.append((top, x0, TextLine(doc_id, number, top, text, tuple(line))))
            items.sort(key=lambda item: (item[0], item[1]))
            yield number, [item for _, _, item in items]


def _lines(words: list[dict[str, Any]], tolerance: float = 3.0) -> list[list[Cell]]:
    """Group words into lines by `top` (within `tolerance` pt), each line ordered left to right."""
    lines: list[list[Cell]] = []
    for w in sorted(words, key=lambda w: (round(float(w["top"]), 1), float(w["x0"]))):
        cell = Cell(clean(w["text"]), _bbox((w["x0"], w["top"], w["x1"], w["bottom"])))
        if lines and abs(lines[-1][0].bbox[1] - cell.bbox[1]) <= tolerance:
            lines[-1].append(cell)
        else:
            lines.append([cell])
    return [sorted(line, key=lambda c: c.bbox[0]) for line in lines]


class Reextractor:
    """Re-derive cell text from page chars inside a bbox (invariant I3), with pdfplumber's midpoint rule.

    Chars are indexed per page by vertical midpoint, so each lookup is a bisect plus a short scan."""

    def __init__(self, path: Path) -> None:
        self._pdf = pdfplumber.open(path)
        self._pages: dict[int, tuple[list[float], list[dict[str, Any]]]] = {}

    def _index(self, page: int) -> tuple[list[float], list[dict[str, Any]]]:
        if page not in self._pages:
            chars = sorted(self._pdf.pages[page - 1].chars, key=lambda c: (c["top"] + c["bottom"]) / 2)
            self._pages[page] = ([(c["top"] + c["bottom"]) / 2 for c in chars], chars)
        return self._pages[page]

    def text(self, page: int, bbox: BBox) -> str:
        mids, chars = self._index(page)
        lo, hi = bisect.bisect_left(mids, bbox[1]), bisect.bisect_left(mids, bbox[3])
        inside = [c for c in chars[lo:hi] if _mid_in(c, bbox)]
        inside.sort(key=lambda c: (c["doctop"], c["x0"]))
        return clean(extract_text(inside)) if inside else ""

    def close(self) -> None:
        self._pdf.close()

    def __enter__(self) -> Reextractor:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
