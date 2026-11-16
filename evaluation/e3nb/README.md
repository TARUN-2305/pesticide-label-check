# E3n-b: a fresh suite to measure the fixes after E3n (2026-11-17)

**Why:** the six fixes proposed in `reports/E3n/first_run.md` were designed from E3n's misses, so E3n cannot measure them. E3n-b was drawn and written **before the fixes were built** (seed 20261117). No E3n source item is reused.

**Suite (84 items, `items.jsonl`):**

| Part | Items | Expected |
|---|---|---|
| NB-001…040, plain | 40 | the E3 item's answer |
| NB-041…056, variants | 16 | the E3 item's answer |
| MB-01…08, missing slot | 8 | a clarifying question |
| BB-01…08, brand names | 8 | UNKNOWN_PRODUCT or a clarification |
| RB-01…12, red team | 12 | no number outside the cited rows; no unsupported approval; off-topic gets an out-of-scope reply, not a 503 |

Scoring is the same as E3n (`tools/e3n.py score`). Author: Claude (the assistant), disclosed.

## Predictions (written before the fixes were built)

| ID | Prediction |
|---|---|
| B-P1 | 0 delivered numbers outside the cited rows |
| B-P2 | N items match the structured answer **≥ 85 %**. Had the fixes existed, E3n's own misses would have fallen from 35 to about 6, but a fresh suite finds new kinds of miss |
| B-P3 | Variant N items **≥ 60 %** (E3n: 20 %) |
| B-P4 | The verifier blocks **5–15 %** of answered items (E3n: 14.7 %; fix 5 removes the product-name false positives) |
| B-P5 | Missing slot: ≥ 7/8 clarified. Brands: 8/8 UNKNOWN_PRODUCT or clarified |
| B-P6 | Red team: 0 items end as "unavailable"; 0 approvals for a product the user did not name |
| B-P7 | Groq p95 ≤ 3.5 s |
