"""Build invariants (L1 §8). Data problems become anomalies; code bugs raise."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from labelclaim.errors import ProvenanceError
from labelclaim.extract.model import Anomaly, BBox, Col, Section, UseRow
from labelclaim.normalize.quantities import Quantity

ReadBox = Callable[[int, BBox], str]

SECTION_NAMES = {
    ("insecticide", "agri_single"): Section.INSECTICIDE_SINGLE,
    ("insecticide", "agri_combination"): Section.INSECTICIDE_COMBINATION,
    ("fungicide", "agri_single"): Section.FUNGICIDE_SINGLE,
    ("fungicide", "agri_combination"): Section.FUNGICIDE_COMBINATION,
}


def _norm(text: str) -> str:
    return " ".join(text.split())


def check_provenance(uses: Iterable[UseRow], read: ReadBox) -> int:
    """I3: every non-empty field's text equals the text re-read from its recorded boxes, in order."""
    checked = 0
    for use in uses:
        for col, field in use.fields.items():
            if field.source in ("spanned", "absent") or not field.text:
                continue
            again = " ".join(t for t in (read(page, box) for page, box in field.bboxes) if t)
            if _norm(again) != _norm(field.text):
                raise ProvenanceError(
                    f"{use.product.doc_id} rows {use.rows} {col.name}: "
                    f"stored {field.text!r} != re-read {again!r}"
                )
            checked += 1
    return checked


def check_incomplete(doc_id: str, uses: Iterable[UseRow]) -> list[Anomaly]:
    """I2: a use needs a crop and a pest text."""
    out = []
    for use in uses:
        page, table, row = use.rows[0]
        for col in (Col.CROP, Col.PEST):
            if not use.fields[col].text.strip():
                out.append(Anomaly("INCOMPLETE_ROW", doc_id, page, table, row, f"{col.name} is empty"))
    return out


def check_sections(
    doc_id: str, kind: str, expected: dict[str, tuple[int, int]], uses: list[UseRow]
) -> list[Anomaly]:
    """I5: the observed page span of each section equals the manifest's (a new edition's layout warning)."""
    out = []
    for name, (first, last) in expected.items():
        section = SECTION_NAMES.get((kind, name))
        pages = [p for u in uses if u.product.section is section for p in (u.page_first, u.page_last)]
        heads = [u.product.page for u in uses if u.product.section is section]
        observed = (min(heads + pages), max(pages)) if pages else None
        if observed is None or observed[0] < first or observed[1] > last or observed[0] > first + 1:
            out.append(
                Anomaly(
                    "SECTION_DRIFT", doc_id, first, -1, -1, f"{name}: expected {first}-{last}, saw {observed}"
                )
            )
    return out


def check_duplicates(doc_id: str, uses: list[UseRow]) -> tuple[list[UseRow], list[Anomaly]]:
    """I6: identical (product, all six fields) rows are kept once."""
    seen: set[tuple[str, ...]] = set()
    kept, out = [], []
    for use in uses:
        k = (use.product.text, str(use.product.page), *(_norm(use.fields[c].text) for c in Col))
        if k in seen:
            page, table, row = use.rows[0]
            out.append(Anomaly("DUPLICATE_ROW", doc_id, page, table, row, " | ".join(k[2:])))
            continue
        seen.add(k)
        kept.append(use)
    return kept, out


def check_digits(q: Quantity) -> None:
    """I7: the parser kept the never-invent-a-number invariant (a bug if not)."""
    for token in q.tokens:
        if token not in q.raw:
            raise ProvenanceError(f"quantity token {token!r} not in raw {q.raw!r}")
