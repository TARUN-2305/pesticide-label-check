# ADR-007: Reviewed corrections of misread rows

Status: accepted (2026-11-15). The first 12 entries were reviewed under the user's delegation; see `data/lexicon/review/edge_review_record.md`

## Context
The edge audit (`reports/E1/edge_audit.md`) found 13 use rows that the extractor misread because the register's own layout is broken. The causes:
- text running past a column line;
- cells with no drawn borders;
- glyphs drawn over other text;
- a pest name placed in the crop column.

One row gave a wrong crop (Brinjal for Cotton). The others gave unmatchable pest names or unparsed doses. The mechanisms differ, and there are only 8–13 cases, so no geometric rule can fix them all without being fitted to them.

## Decision
- **Detect, don't repair, in the extractor** (`extract/edges.py`, L1 §16). Each orphan, overlap or straddle becomes a `CELL_*` anomaly on its row.
- **Correct through `data/corrections.toml`.** Each entry names the row by its extracted text (`match`) and gives the page's text (`set`, or `drop` for a row split in two). It records the evidence and a reviewer. An entry must match exactly one row, or the build fails, so a re-issued register cannot be silently "corrected".
- **Keep I3 (provenance) on the extractor's own output.** It is checked before corrections are applied.
- **Show corrections.** A corrected field has `source = "corrected"` and keeps its page boxes. `use_record.corrected_json` records the id, the field and the text before. Every answer lists those fields in `corrected`.
- **Gate the release.** An uncovered `CELL_*` anomaly, or an unreviewed correction, refuses the build.

## Consequences
- This amends ADR-004: a `*_raw` field is the register's text either as extracted, or, where `corrected` names it, as read from the page by a reviewer. It is never paraphrased.
- Corrections are tied to one edition of the register. A new edition re-runs the audit, and stale entries fail loudly.
- A reviewer must sometimes judge. C-11 keeps a word that is in the PDF's text but hidden on the rendered page; its evidence says so.
