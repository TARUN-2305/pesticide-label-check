# E1b: a fresh extraction sample after the L1 §17 fix (2026-11-15)

**Why:** E1 found one defect, split pest cells, and the fix (L1 §17) was designed from E1's rows. Its 100 % on the same 120 rows is therefore not a measurement. E1b measures the fix on rows nobody has looked at.

**Sample:**
- `tools/e1.py select --seed 20261117 --scale 0.5 --prefix E1b --exclude evaluation/e1/sample.jsonl`;
- drawn from release `7c93bd89…`;
- 60 rows (insecticide single 18, insecticide combination 12/13, fungicide single 18, fungicide combination 12/13), each stratum with ≥ 5 merged-crop, ≥ 3 page-break and ≥ 3 free-text rows;
- no raw row of E1 is drawn again.

**Labelling:** the same method, rules and labeller as E1 (`evaluation/e1/README.md`): typed from the page images before any comparison, with the first-run file frozen. There is no second pass this time; disagreements are adjudicated against the text layer.

## Predictions (written before the sample was drawn)

| ID | Prediction |
|---|---|
| E1b-P1 | Field accuracy (8 fields) after adjudication ≥ 99 % |
| E1b-P2 | Row accuracy after adjudication ≥ 97 %, the target E1 missed. My forecast: 95–100 %; one residual from a split I know of (use 1006 class) or another non-geometric defect is plausible |
| E1b-P3 | 0 split-pest-cell errors in the sample |
| E1b-P4 | 1–3 of my own labelling errors on the first run |

**Minimums not met (pool exhausted):**
- insecticide single has 2 page-break rows, because only 2 remain after excluding E1's rows (5 in the register);
- fungicide combination has 4 merged-crop rows, which is all the register has after the fix (E1's count of 6 included split fragments that are now joined).

## Results

See [`reports/E1/report.md`](../../reports/E1/report.md), section "After the L1 §17 fix". Labels were frozen before the run (SHA-256 `d321b248…`). Adjudicated: 99.36 % of fields, 96.6 % of rows.
