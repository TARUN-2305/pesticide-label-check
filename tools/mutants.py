"""Mutation checks (L1 §12 and the M1 implementation notes). Each mutant is applied to the source,
the named tests are run, and the mutant must turn at least one of them red. Predictions are fixed here
before running. Usage: uv run python tools/mutants.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "labelclaim"
MUTANTS = [
    # id, file, original, mutant, tests, predicted
    ("M1 left edge instead of centre", "extract/geometry.py",
     "owner = _band_of((cell.bbox[0] + cell.bbox[2]) / 2, bands)", "owner = _band_of(cell.bbox[0], bands)",
     ["tests/test_extract.py", "-m", "corpus or not corpus"], "survives (cells start on band edges; equivalent here)"),
    ("M2 covered cell read as empty (no merge inheritance)", "extract/assemble.py",
     "            if not row.covered(col):\n                carried.discard(col)",
     "            if True:\n                carried.discard(col)",
     ["tests/test_extract.py::test_merged_crop_and_values_inherited_within_table"], "killed"),
    ("M3 product reset at a page break", "extract/assemble.py",
     "        self._flush_loose()\n        self._page_has_table = False",
     "        self._flush_loose()\n        self._page_has_table = False\n        self.product = None",
     ["tests/test_golden_pages.py::test_ins_p67_68_value_split_by_the_page_break", "-m", "corpus"], "killed"),
    ("M4 parser invents the upper bound", "normalize/quantities.py",
     "return Quantity(raw, \"range\", (float(tokens[0]),), (float(tokens[1]),), unit, tokens, \"parsed\")",
     "return Quantity(raw, \"range\", (float(tokens[0]),), (float(tokens[0]) * 2,), unit, tokens, \"parsed\")",
     ["tests/test_quantities.py"], "killed"),
    ("M5 provenance re-check skipped", "validate.py",
     "    checked = 0\n    for use in uses:", "    checked = 0\n    return 1\n    for use in uses:",
     ["tests/test_register_validate.py::test_provenance_recheck_passes_and_catches_a_planted_mismatch"], "killed"),
    ("M7 mid-table continuation rule removed", "extract/assemble.py",
     "            if kind in (RowKind.DATA, RowKind.UNMAPPED) and content_started and self._continues_last(row):",
     "            if False:",
     ["tests/test_golden_pages.py::test_fun_p76_dose_range_split_over_grid_rows", "-m", "corpus"], "killed"),
    ("M8 full-row check at table start removed", "extract/assemble.py",
     "            elif kind is RowKind.CONTINUATION and self._is_full_row(row):",
     "            elif False:",
     ["tests/test_golden_pages.py::test_fun_p38_39_pest_split_by_page_break_with_a_second_application", "-m",
      "corpus"], "killed"),
    ("M9 sliver cells counted in signatures", "extract/geometry.py",
     "return [c for c in row.cells if c is not None and (c.text or c.bbox[2] - c.bbox[0] >= SLIVER)]",
     "return [c for c in row.cells if c is not None]",
     ["tests/test_golden_pages.py::test_only_reviewed_anomalies_remain", "-m", "corpus"], "killed"),
    ("M10 note-like full-width cells taken as products", "extract/classify.py",
     "        if looks_like_note(text):\n            return RowKind.NOTE",
     "        if NOTE.match(text):\n            return RowKind.NOTE",
     ["tests/test_extract.py"], "survives (no synthetic case for a colon/sentence note; see results)"),
]  # fmt: skip


def run(tests: list[str]) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *tests], cwd=ROOT, capture_output=True, check=False
    )
    return proc.returncode == 0


def main() -> int:
    rows = []
    for mid, rel, original, mutant, tests, predicted in MUTANTS:
        path = SRC / rel
        source = path.read_text(encoding="utf-8")
        if source.count(original) != 1:
            rows.append((mid, predicted, "NOT APPLIED (pattern not found exactly once)"))
            continue
        path.write_text(source.replace(original, mutant), encoding="utf-8")
        try:
            outcome = "survived" if run(tests) else "killed"
        finally:
            path.write_text(source, encoding="utf-8")
        rows.append((mid, predicted, outcome))
    print("| Mutant | Predicted | Outcome |\n|---|---|---|")
    for mid, predicted, outcome in rows:
        print(f"| {mid} | {predicted} | {outcome} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
