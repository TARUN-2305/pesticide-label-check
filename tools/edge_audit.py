"""Audit text that crosses the register tables' drawn cell lines (L1 §16; report: reports/E1/edge_audit.md).

Uses the extractor's own detector (`labelclaim.extract.edges`), and also lists the `adjacent` runs (two
cells' texts that merely sit close) so the threshold can be checked against the closest real pair.

    uv run python tools/edge_audit.py --out reports/E1/edge_audit.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from labelclaim.extract.edges import OVERLAP, RUN_GAP, STRADDLE_GAP, Glyph, classify_run, runs
from labelclaim.sources import DEFAULT_CACHE, load_manifest


def _outer_tables(page: Any) -> list[Any]:
    """Tables not nested inside another table (as the extractor drops them, pages.py)."""
    found = page.find_tables()
    boxes = [tuple(t.bbox) for t in found]

    def inside(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
        return a != b and a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1

    return [t for t, box in zip(found, boxes, strict=True) if not any(inside(box, o) for o in boxes)]


def audit_page(doc: str, number: int, page: Any, in_scope: bool) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    total = 0
    for table in _outer_tables(page):
        x0, top, x1, bottom = table.bbox
        cells = [tuple(c) for c in table.cells]
        glyphs = [
            Glyph(c["text"], c["x0"], c["x1"], c["top"], c["bottom"], c["size"])
            for c in page.chars
            if x0 <= (c["x0"] + c["x1"]) / 2 <= x1 and top <= (c["top"] + c["bottom"]) / 2 <= bottom
        ]
        total += len(glyphs)
        for run in runs(glyphs):
            kind, cut = classify_run(run, cells)
            if kind is None:
                continue
            pieces: list[list[str]] = []
            for g in run:
                o = g.owner(cells)
                k = "none" if o is None else f"x{cells[o][0]:.0f}-{cells[o][2]:.0f}"
                if pieces and pieces[-1][0] == k:
                    pieces[-1][1] += g.text
                else:
                    pieces.append([k, g.text])
            out.append({
                "doc": doc, "page": number, "top": round(run[0].top, 1), "kind": kind, "cut_gap": cut,
                "in_scope": in_scope, "text": "".join(g.text for g in run), "pieces": pieces,
            })  # fmt: skip
    return out, total


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit text that crosses table cell lines")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    crossings: list[dict[str, Any]] = []
    total = 0
    for doc in (d for d in load_manifest(Path("data/sources.toml")) if d.kind != "restrictions"):
        spans = list(doc.expected_sections.values())
        with pdfplumber.open(DEFAULT_CACHE / f"{doc.sha256}.pdf") as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                found, n = audit_page(doc.id, number, page, any(lo <= number <= hi for lo, hi in spans))
                crossings += found
                total += n
    cuts = [
        c["cut_gap"] for c in crossings if c["kind"] in ("straddle", "adjacent") and c["cut_gap"] is not None
    ]
    summary = {
        "table_chars": total,
        "reported_runs": len(crossings),
        "by_kind": dict(Counter(c["kind"] for c in crossings)),
        "by_kind_in_scope": dict(Counter(c["kind"] for c in crossings if c["in_scope"])),
        "straddles_by_threshold_pt": {str(t): sum(g < t for g in cuts) for t in (0.25, 0.5, 1.0, 2.0)},
        "closest_adjacent_pt": min(
            (c["cut_gap"] for c in crossings if c["kind"] == "adjacent"), default=None
        ),
        "pages": len({(c["doc"], c["page"]) for c in crossings}),
    }
    thresholds = {"run_gap_em": RUN_GAP, "straddle_gap_pt": STRADDLE_GAP, "overlap_share": OVERLAP}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(thresholds | {"summary": summary, "crossings": crossings}, indent=1, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
