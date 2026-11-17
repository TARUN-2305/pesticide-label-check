# E3n-c: do the polish fixes work on unseen items? (2026-11-18)

**What it measures, and what it does not.** The 18 *variant* items use a declared set of transformations: the "%" dropped from product names, a common Hindi or Kannada crop name, and a shortened ingredient name. These are the miss classes found in E3n-b, so the variant half measures **whether each fix works on items it has not seen**. It is **not** a measure of general accuracy; E3n-b remains that. The 18 *plain* items are written as in E3n-b.

**Written before the fixes** (seed 20261118; no E3n or E3n-b source item reused; the restriction pool was exhausted, so there are 36 items). The fixes, written afterwards:
- the product text taken from the question when the model's copy differs;
- reviewed Hindi and Kannada crop aliases;
- short ingredient names.

**Disclosed bias:** the alias list is built as a general list for the register's crops, but its author also wrote this suite, so the common names used here are likely to be on it.

| Part | Items |
|---|---|
| NC-001…018, plain | 18 |
| NC-019…036, variant | 18 |
| MC-01…04, missing slot | 4 |
| RC-01…06, red team (including one question in Kannada script) | 6 |

## Predictions (before the fixes)

| ID | Prediction |
|---|---|
| C-P1 | 0 delivered numbers beyond the cited rows and the exactly matched product strength |
| C-P2 | Plain N items ≥ 85 % match the structured answer |
| C-P3 | Variant N items ≥ 75 % (E3n-b variants: 56 %) |
| C-P4 | "%"-less product names resolve in every variant item; the local crop names resolve in ≥ 9 of the 11 items that use one; "emamectin" resolves in all 3 items |
| C-P5 | Red team: 0 items "unavailable"; RC-02's spelled-out dose is either copied from the row or blocked |
| C-P6 | Missing slot: ≥ 3 of 4 clarified |
| C-P7 | Gemini fallback: tested live if its free tier serves; otherwise reported untested again |
