"""Reviewed corrections of rows the extractor misread (ADR-007, L1 §16).

The extractor reads the register's geometry. In a few places that geometry is wrong: text runs past a
column line, a cell has no drawn borders, or two texts are drawn over each other (reports/E1/edge_audit.md).
No rule fixes all of them without being fitted to them, so each case is corrected by a reviewed entry in
`data/corrections.toml`:

    [[correct]]
    id = "C-01"
    doc = "mup_insecticide_2026-09-30"
    page = 25                          # the row's first page
    product = "DIMPROPYRIDAZ 120 g/l SL"
    match = { crop = "Brinjal", pest = "White fly", wait = "31" }   # the extracted text, before
    set = { crop = "Cotton" }          # or: drop = true (a row the extractor split in two)
    covers = ["CELL_ORPHAN"]           # anomaly codes this entry resolves, on the matched row only
    evidence = "pdftotext -layout p. 25: ..."
    reviewed_by = "..."

An entry must match exactly one extracted row. When the register is re-issued and the row changes, the
entry matches none and the build fails: a correction never silently applies to text it was not written for.
"""

from __future__ import annotations

import dataclasses
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labelclaim.errors import CorrectionError
from labelclaim.extract.model import Anomaly, Col, Field, RowRef, UseRow

FIELDS: Mapping[str, Col] = {
    "crop": Col.CROP, "pest": Col.PEST, "dose_ai": Col.DOSE_AI, "dose_form": Col.DOSE_FORM,
    "dilution": Col.DILUTION, "wait": Col.WAIT,
}  # fmt: skip
Applied = dict[str, tuple[RowRef, ...]]  # correction id -> raw rows of the use it matched


@dataclass(frozen=True)
class Correction:
    id: str
    doc: str
    page: int
    product: str
    match: Mapping[Col, str]
    set: Mapping[Col, str]
    drop: bool
    covers: tuple[str, ...]
    evidence: str
    reviewed_by: str

    @property
    def reviewed(self) -> bool:
        return bool(self.reviewed_by.strip())

    def matches(self, use: UseRow) -> bool:
        return (
            use.product.doc_id == self.doc
            and use.page_first == self.page
            and use.product.text == self.product
            and all(use.fields[col].text == text for col, text in self.match.items())
        )


def _columns(where: str, raw: Any) -> dict[Col, str]:
    if not isinstance(raw, dict):
        raise CorrectionError(f"{where} must be a table")
    out: dict[Col, str] = {}
    for name, text in raw.items():
        if name not in FIELDS:
            raise CorrectionError(f"{where}: unknown field {name!r} (one of {', '.join(FIELDS)})")
        if not isinstance(text, str):
            raise CorrectionError(f"{where}.{name} must be a string")
        out[FIELDS[name]] = text
    return out


def _parse(entry: Any) -> Correction:
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        raise CorrectionError(f"every [[correct]] entry needs a string id: {entry!r}")
    cid = entry["id"]
    match = _columns(f"{cid}.match", entry.get("match", {}))
    if not match:
        raise CorrectionError(f"{cid}: match must name at least one field")
    has_set, drop = "set" in entry, entry.get("drop", False) is True
    if has_set == drop:
        raise CorrectionError(f"{cid}: give exactly one of set or drop")
    evidence = entry.get("evidence", "")
    if not isinstance(evidence, str) or not evidence.strip():
        raise CorrectionError(f"{cid}: evidence (the page text the correction is read from) is required")
    try:
        return Correction(
            id=cid,
            doc=str(entry["doc"]),
            page=int(entry["page"]),
            product=str(entry["product"]),
            match=match,
            set=_columns(f"{cid}.set", entry["set"]) if has_set else {},
            drop=drop,
            covers=tuple(str(c) for c in entry.get("covers", [])),
            evidence=evidence,
            reviewed_by=str(entry.get("reviewed_by", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorrectionError(f"{cid}: missing or malformed doc, page or product ({exc})") from exc


def load_corrections(path: Path) -> tuple[Correction, ...]:
    if not path.exists():
        return ()
    entries = tomllib.loads(path.read_text(encoding="utf-8")).get("correct", [])
    corrections = tuple(_parse(e) for e in entries)
    ids = [c.id for c in corrections]
    if dupes := sorted({i for i in ids if ids.count(i) > 1}):
        raise CorrectionError(f"duplicate correction ids: {', '.join(dupes)}")
    return corrections


def _apply(use: UseRow, c: Correction) -> UseRow:
    fields = dict(use.fields)
    before = []
    for col, text in c.set.items():
        old = fields[col]
        fields[col] = Field(text, old.bboxes, "corrected", old.origin, old.span_of)
        before.append((c.id, col.name, old.text))
    return dataclasses.replace(use, fields=fields, corrections=use.corrections + tuple(before))


def apply_corrections(
    doc_id: str, uses: Sequence[UseRow], corrections: Iterable[Correction]
) -> tuple[list[UseRow], Applied]:
    """Apply every correction for `doc_id`. Each must match exactly one row, else CorrectionError."""
    out = list(uses)
    dropped: set[int] = set()
    applied: Applied = {}
    for c in (c for c in corrections if c.doc == doc_id):
        hits = [i for i, u in enumerate(out) if i not in dropped and c.matches(u)]
        if len(hits) != 1:
            raise CorrectionError(
                f"{c.id} ({c.doc} p. {c.page}, {c.product!r}) matches {len(hits)} rows; it must match 1. "
                "If the register was re-issued, re-check the row and update the entry."
            )
        (i,) = hits
        applied[c.id] = out[i].rows
        if c.drop:
            dropped.add(i)
        else:
            out[i] = _apply(out[i], c)
    return [u for i, u in enumerate(out) if i not in dropped], applied


def covered(a: Anomaly, corrections: Iterable[Correction], applied: Applied) -> bool:
    """True when a correction lists `a.code` and was applied to the use row that `a` sits on."""
    ref = (a.page, a.table, a.row)
    return any(a.code in c.covers and a.doc_id == c.doc and ref in applied.get(c.id, ()) for c in corrections)
