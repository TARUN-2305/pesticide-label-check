# E1 golden set: extraction accuracy (2026-11-15)

**Plan:** `docs/evaluation_plan.md` E1. **Sampler:** `tools/e1.py select` (seed 20261116), drawn from the release register `d86befe7…`.

**Sample:** 120 use rows in four strata:

| Stratum | Rows |
|---|---|
| insecticide single | 35 |
| insecticide combination | 25 |
| fungicide single | 35 |
| fungicide combination | 25 |

Each stratum has at least 5 merged-crop rows, 3 page-break rows and 3 free-text rows (`sample.jsonl`).

**Deviation from the plan:** the plan adds "the deliberately chosen hard pages". Those pages are already covered by the 22 golden rows in `tests/test_golden_pages.py`, so all 120 rows here are random.

## Labelling

- **Labeller:** Claude (the assistant), disclosed. The labeller has seen the code.
- **Labels (`labels.jsonl`)** are typed from `images/E1-nnn.png`. Each image is the product heading, then the row's page strip at 150 dpi, with the row's own cells outlined in red. The sampler writes no extracted text, and the labeller does not query the register before labelling.
- **Transcription rules:**
  - text is typed as printed;
  - line breaks inside a cell become one space;
  - a value printed once for several rows (a merged cell) is given to each row;
  - an empty cell is `""`;
  - `page` is the row's first page.
- **The second labelling of 30 rows, a deviation:** the plan said the user would re-label 30. The user delegated it ("can you handle the relabelling yourself?"). The check pass (`labels_check.jsonl`, items E1-001…E1-120 every 4th) is typed by the same labeller from a *different reader*: poppler `pdftotext -layout`, the text layer, not the image.
  - **It is not independent human judgment.** It measures transcription consistency between two ways of reading the page.
  - Disagreements are adjudicated against the page image and the text layer.

## Predictions (written before any label was typed)

| ID | Prediction |
|---|---|
| E1-P1 | Field accuracy ≥ 99 % on the first run (P6 in L1 §11). **My forecast: 98–99.5 %**, because my own transcription errors also count as misses until they are adjudicated |
| E1-P2 | Row accuracy ≥ 97 % after adjudication; first-run row accuracy 90–97 % |
| E1-P3 | At least 2 of the first-run misses are my labelling errors (dashes, italics, line-wrap spaces), as in E3 |
| E1-P4 | Extractor errors that survive adjudication: 0–3, mostly in free-text or page-break rows |
| E1-P5 | Image-vs-text-layer agreement on the 30 rows: ≥ 98 % of fields |
