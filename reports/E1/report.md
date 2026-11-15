# E1 report: extraction accuracy (2026-11-15)

**Environment:** `ENV-NATIVE-1`. Release register `d86befe7…`. The method, labelling rules and predictions were written before any label: [`evaluation/e1/README.md`](../../evaluation/e1/README.md).

**Inputs:**
- sample: `evaluation/e1/sample.jsonl` (seed 20261116);
- labels: `labels.jsonl` (frozen before the run, SHA-256 `170400fe…`), `labels_check.jsonl` (30 rows, text layer), `labels_adjudicated.jsonl`.

**Raw results:** `first_run.json`, `adjudicated.json`.

## Results

| Measure | First run | Adjudicated | Target |
|---|---|---|---|
| Field accuracy, 8 fields (as planned) | 98.92 % | **99.35 %** | ≥ 99 %: missed on the first run, met after adjudication |
| Field accuracy, 7 row fields (no `page`) | 98.77 % | 99.26 % | — |
| Row accuracy (all 8 fields) | 91.4 % (106/116) | **94.8 % (110/116)** | ≥ 97 %: **missed** |

**Scope of the scores:**
- 116 of 120 rows are scored.
- **4 rows are not scored, a scope finding:** their tables do not fit the 6-column schema.
  - E1-002, E1-018, E1-019: fumigation tables with 5–7 columns (exposure time, ppm).
  - E1-016: a public-health table (mosquitoes, bed bugs; mg a.i./m²) inside an agricultural section.

  All four are in the register as if they were crop rows.
- **`page`** is correct by construction, because the image was cut from that page. That is why the 7-field figure is also given.

**Check pass:** the image labels and the text-layer labels agree on 179 of 180 fields (99.4 %). The same labeller typed both, from different readers, so this is not an independent human check.

### Every first-run miss, classified

| Class | Rows | What happened |
|---|---|---|
| **My labelling error** (4, plus 1 caught in the check pass) | E1-025, 029, 042: a space glyph exists in the text layer but looked absent in the image. E1-037: I broke my own line-break rule. E1-016: I wrote "Periplaneta" where the page prints "Periplanata" | adjudicated against the glyph stream; the first-run file is unchanged |
| **Extraction: split pest cell** (6) | E1-098, 107, 108, 113, 119, 120 | the pest cell has internal horizontal lines. pdfplumber yields extra grid rows, and the extractor makes each line a **use row of its own**: only the pest cell is its own, and the crop and all four values are merged from the row above. Both rows then hold a fragment ("Early blight, and" / "Septoria leaf spot"; "capsici) Choanephora B") |

All six split rows share that signature. The release register has **77 rows** with it (3.2 % of 2,372; E1: 6 of 116 = 5.2 %). Some may be legitimate: separate pests that share merged values, where the lookup outcome would be the same. Many are visibly fragments ("mildew", "(Rhizoctonia", "disease, Leaf").

**Effect:** a pest split mid-name cannot be matched, so the lookup says "not approved for this pest" where the page approves it. This is the safe direction, but wrong. No dose, crop or waiting period was wrong in any scored row.

**Other observations (no field error):**
- E1-074: the register's own pest cell holds a product name.
- E1-105: the page itself prints doubled values.
- E1-091: a page-break row prints a second (drone) application.

## Predictions vs results

| ID | Prediction | Result |
|---|---|---|
| E1-P1 | field accuracy ≥ 99 % on the first run; my forecast 98–99.5 % | **Target missed** (98.92 %); forecast held |
| E1-P2 | row accuracy ≥ 97 % after adjudication; first run 90–97 % | **Missed** (94.8 %); first-run forecast held (91.4 %) |
| E1-P3 | ≥ 2 first-run misses are my labelling errors | Held: 4, plus 1 caught by the check pass |
| E1-P4 | 0–3 extractor errors survive, mostly free-text or page-break rows | **Wrong:** 6, all one mechanism (split pest cells), none of them free-text or page-break |
| E1-P5 | image-vs-text-layer agreement ≥ 98 % | Held: 99.4 % |

## What this does and does not show

- **It shows:** on 116 random rows, every crop, dose, dilution and waiting period matches the page after adjudication. The remaining error is in pest text, and it has one cause.
- **It does not show** accuracy on the 4 non-standard layouts, which are not scored. Nor is it an independent human check: the labeller is the assistant, who has seen the code and made 5 transcription errors in 120 rows.
- **Next:** a fix for split pest cells (join a pest-only row into the row its merges come from). It needs a design decision, because joining two legitimate separate pests without a separator would create a joined pest ID. After it: a fresh E1 sample to measure the fix.

## After the L1 §17 fix (2026-11-15)

**Fix:** [L1 §17](../../docs/lld/l1_register_extraction.md). Release `7c93bd89…`.

- **The same 120 rows:** 100 % of fields and rows (`l17_same_120.json`). **Not a measurement:** the fix was designed from these rows.
  - To score across rebuilds, `tools/e1.py` now keys each row on its raw position (doc, page, table, row), not on the use id, which changes when rows are joined.
  - The old release re-scored with the new key gives exactly the old numbers.
- **The register:** pest-only rows went from 77 to 2.
- **Fresh E1b** (60 rows, seed 20261117, no E1 row redrawn; [`evaluation/e1b/README.md`](../../evaluation/e1b/README.md)):

| | First run | Adjudicated | Target |
|---|---|---|---|
| Field accuracy (8) | 98.73 % | **99.36 %** | ≥ 99 %: met |
| Row accuracy | 91.5 % (54/59) | **96.6 % (57/59)** | ≥ 97 %: **missed by one row** |

**E1b details:**
- 1 row was not scored: a rodenticide table, a non-crop layout.
- 3 first-run misses were my labelling errors: space glyphs that looked absent in the image.
- 2 are extraction errors, both split rows the §17 rule deliberately leaves alone:
  - E1b-053: the line carries the end of a dose value;
  - E1b-060: the known full-width residual.

**What E1b does and does not show:** scored on the pre-fix release, E1b gives the same numbers. None of its 60 rows was one of the ~75 joined rows (about 2 would be expected), so **E1b measures the residual error after the fix, not the fix itself.** The fix's effect is the register-wide count, 77 → 2.

**Predictions:**

| ID | Prediction | Result |
|---|---|---|
| E1b-P1 | fields ≥ 99 % | Held: 99.36 % |
| E1b-P2 | rows ≥ 97 %; forecast 95–100 % | Target missed (96.6 %); forecast held |
| E1b-P3 | 0 split-pest-cell errors | **Wrong:** 2, both of the sub-kinds the rule leaves alone |
| E1b-P4 | 1–3 labelling errors | Held: 3 |
