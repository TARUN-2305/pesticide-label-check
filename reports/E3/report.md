# E3 report: lookup correctness (2026-11-14)

**Environment:** `ENV-NATIVE-1` (Linux 7.0, Intel i3-1220P, Python 3.12.16). The suite, method and predictions were written **before the first run**: [`evaluation/e3/README.md`](../../evaluation/e3/README.md). Raw per-query results are in the JSON files next to this report.

## Runs

| Run | Register | Suite | Outcome right | 95 % CI (bootstrap) | Safety-critical |
|---|---|---|---|---|---|
| `first_run` | release `ea931038…` | as written (`6bf8bf3f…`) | **122 / 150 (81.3 %)** | 74.7–87.3 % | **1** (E3-086) |
| `after_heading_fix` | release `5e5f2de1…` (extraction fix below) | as written | 123 / 150 (82.0 %) | 75.3–88.0 % | 0 |
| `adjudicated_queries` | `5e5f2de1…` | 1 label corrected (`56989722…`) | 123 / 150 (82.0 %) | 75.3–88.0 % | 0 |
| `adjudicated_extra` | `5e5f2de1…` | the 31 extras, 1 label corrected | 30 / 31 | 90.3–100 % | 0 |

**The first run is the result for Q-P2.** Later runs measure fixes; they do not replace it.

By stratum (first run → adjudicated): APPROVED 46 → 46 of 60; NOT_APPROVED_FOR_CROP 29 → 30 of 30; NOT_APPROVED_FOR_PEST 19 of 20; UNKNOWN_PRODUCT 10 of 10; UNKNOWN_CROP 10 of 10; **AMBIGUOUS 0 of 10**; restriction overlay 8 of 10.

Other measures (adjudicated):

| Measure | Result |
|---|---|
| Row descriptions that matched exactly `n` rows | 100 % (0 problems in any run) |
| APPROVED rows, where the answer was APPROVED (53 queries) | precision 1.00, recall 1.00 (first run: precision 0.984, because of my label E3-042) |
| APPROVED rows over all 69 APPROVED-expected queries | recall 0.79: the 16 wrong outcomes return no rows |
| Restriction notes as expected | 149 / 150. The miss is E3-053: an unknown product carries no notes |
| `conflict` as expected | 150 / 150. All 5 collisions are flagged; no false flags |

## The safety-critical error and its fix

**E3-086.** The query was "Chlorothalonil 40% + Thiophanate methyl 35% WDG" on rice. Expected: not approved. Got: **APPROVED**, citing a Paddy row on fungicide p. 59.

- **What the page shows:** that Paddy row belongs to the *next* product, "Chlorantraniliprole 0.64% + Tebuconazole 3% + Clothianidin 1.92% GR".
- **Cause, an extraction error:** that heading's table cell stops mid-table (x 72–417 of 72–582), so it was not "full width". The classifier filed it as a note of the row above, and the Paddy row was credited to the previous product.
- **Scope:** a search of the release register for notes that read like headings found **4 such headings**: fungicide p. 59, 83 and 85 (two). Between them they had **6 use rows credited to the wrong product**. On p. 83 and 85 the heading cell sits after an empty 6–8 pt sliver cell.
- **Fix** (`extract/classify.py`): a single spanning cell is a product heading when it reads like a heading, is not note-like, and nothing to its left is merged down from the row above.
- **Tests** (`tests/test_extract.py`):
  - the p. 59 case, written first and seen to fail;
  - the sliver case, written after the fix (from the raw cells);
  - an indented heading-like note that stays a note.
- **Result:** the release build now has 659 products (was 655) and still 2,374 use rows. The search finds 0 heading-like notes.

## Every other miss, classified

| Class | Queries | What happens | Fix needs |
|---|---|---|---|
| **Crop alias missing** | E3-002 "ladies finger", E3-005 and E3-010 "bhindi", E3-048 "urad", E3-050 "finger millet"; extra X-06 "eggplant" | UNKNOWN_CROP. The register itself writes "Okra (Bhindi)", yet "bhindi" alone is not an alias | a reviewed crop-lexicon diff (your signature) |
| **One pest, several IDs** | E3-043 blast / "Blast Disease"; E3-045 and E3-147 leaf spot / "Leafspot"; E3-148 whitefly / "Whiteflies"; E3-055 sheath blight / "Sheath Bight" (register typo); E3-016 groundnut leaf miner / "leaf minor" (register typo); E3-015 "diamondback moth"; E3-022 and E3-092 "mealybug"; E3-035 "Pests: Brown Plant Hopper" (a label kept in the phrase) | NOT_APPROVED_FOR_PEST or UNKNOWN_PEST although the row approves it. The `rule:identity` drafts made every distinct spelling its own pest. This is why Q-P4 came out at 627 pests | a rule (keys equal after removing spaces and hyphens, `-ies` → `-y` plurals, labels such as "Pests:" stripped), plus a reviewed list of typos and synonyms |
| **Lost separator in the raw text** | E3-018 "whitefly" on chilli (insecticide p. 55) | The stored cell reads "Whitefly (Bemisia tabaci) Thrips", but poppler shows a comma after "tabaci)". The comma is probably just outside the cell's box. 6 pest rows hold merged phrases of this kind | extraction investigation (characters at cell edges) |
| **Ingredient spelling at query time** | E3-053 "Copper sulfate" | UNKNOWN_PRODUCT. The variants table holds only spellings found in the register | a rule: fold the user's text with `spelling_family` when it matches exactly one registered ingredient |
| **Generic names (design gap)** | all 10 AMBIGUOUS: "blight", "mildew", "rust", "mite", "plant hopper" → NOT_APPROVED_FOR_PEST; "borer" → UNKNOWN_PEST; "gourd", "millet" → UNKNOWN_CROP | The engine returns AMBIGUOUS only when one alias is shared by several IDs. A generic name either is its own pest ("blight" occurs in the register) or is unknown. **7 of 10 give a misleading "not approved for this pest"** when a specific form is approved; the answer does list the approved pests | a design addendum: a reviewed table of generic names → specific IDs, and an AMBIGUOUS answer that says which ones are approved on the crop |
| **My labelling errors** | E3-042 (Pyriofenone is also on fungicide p. 35); extra X-17 (the Chlorantraniliprole GR product is also on insecticide p. 64) | The suite README said every product heading was searched in both registers. **It was not done for every product.** The run found both cases | labels corrected with the page text quoted (below) |

If the crop, pest and ingredient fixes all land, 17 of the 27 remaining misses go. That would make about 140 / 150 (93 %). That is a forecast, not a measurement. Reaching the 98 % target needs the generic-name design as well.

### Label corrections (made after the first run)

- **E3-042:** fungicide p. 35 reads "Pyriofenone 18 % w/v SC / Grape / Powdery mildew / 108 / 600 / 750 / 5". The row was added to the expected set.
- **X-17:** insecticide p. 64 reads "Chlorantraniliprole 0.64% + Tebuconazole 3% + Clothianidin 1.92% GR / Paddy / Yellow Stem Borer and Sheath Blight / 40 + 187.5 + 120 / 6250 / NA / 46". The row was added to the expected set.

## Predictions vs results

| ID | Prediction | Result |
|---|---|---|
| Q-P2 | outcome ≥ 98 % on the first run | **Wrong:** 81.3 % |
| E3-P1 | 80–92 %, with ≤ 3 of 10 AMBIGUOUS right | Held: 81.3 % (near the bottom), 0 of 10 AMBIGUOUS |
| E3-P2 | 0 safety-critical errors | **Wrong:** 1 (E3-086, an extraction error). 0 after the fix |
| E3-P3 | all 5 collisions flagged, no false flags | Held: 150 / 150 |
| E3-P4 | ≥ 95 % of row descriptions match exactly | Held: 100 % |
| E3-P5 | precision ≥ 0.98, recall ≥ 0.95 when answered APPROVED | Held: 0.984 / 1.00 (first run) |
| Q-P3 | ≥ 1 lexicon gap; my forecast ≥ 3 | Held: 6 crop-alias queries, 10 pest-lexicon queries, 1 ingredient spelling. **Not yet fixed** through a reviewed diff |

## What this does and does not show

- **It shows:** on 150 queries written from 30 random pages and the restrictions list, every APPROVED answer cites exactly the rows the page shows. No answer approves a use the page does not show (after the extraction fix). Every register/restriction collision tested is flagged.
- **It does not show** accuracy on real farmers' wording (that is E4), or on the 70 pages that were not sampled. Each stratum is small (10–60 queries), so per-stratum rates are pilot-level. The labeller had seen the code, and two of my labels were wrong.
- **The extraction fix was found by E3, not E1.** The E1 golden set (120 rows) is still unfinished. A field-level E1 on random rows would have been the earlier place to catch it.

## After the L2 §13 fixes (2026-11-15)

**Review:** the user delegated the review in chat ("I say you do research and review yourself, I approve"). The decisions and sources are in [`data/lexicon/review/e3_review_record.md`](../../data/lexicon/review/e3_review_record.md).

**Built:**
- the matching rule;
- 64 pest merges, taking 627 pests to **563** (G-P1, ≤ 570: held);
- 23 crop aliases;
- 11 general terms;
- the ingredient spelling fold.

**Release register:** `916f131a…`, with 0 rule collisions. The same check reports 37 collisions on the old lexicon.

**Gate:**
- 166 unit and 11 golden tests pass;
- 23 of 23 mutation checks are killed. One of them, G-M3, survived at first; its test was then strengthened.

| Run | Suite | Outcome right | 95 % CI | Safety-critical |
|---|---|---|---|---|
| `g_fixes_queries` | the same 150 (they informed the fixes, so this is not independent) | **149 / 150** (99.3 %) | 98.0–100 % | 0 |
| `g_fixes_extra` | the 31 extras | 31 / 31 | — | 0 |
| **`e3b_first_run`** | **60 fresh queries from 10 new pages, written before the run** | **58 / 60 (96.7 %)** | 91.7–100 % | **0** |

- **On the 150:**
  - AMBIGUOUS is 10 / 10 (G-P3: held);
  - restriction notes and `conflict` are right on 150 / 150;
  - the one miss is E3-018 (the lost comma), as G-P2 predicted.
- **The two E3b misses** (not fixed, so E3b stays a fair measure):
  - **E3b-27, extraction:** on fungicide p. 60, "Paddy | Sheath Blight" was split at the wrong column boundary into crop "Paddy Sheath" and pest "B light". The same page's Cyazofamid row lost characters at a cell edge ("infestan", "Alternari").
    - Together with E3-018's comma, this is a pattern: **text at cell edges is dropped or put in the wrong cell.** It needs its own E1-style investigation.
    - It also exposes a bad crop ID, `paddy_sheath`, that the crop review accepted.
  - **E3b-28, lexicon:** "Scab Venturia inaequalis" has the scientific name without brackets, so the phrase became its own pest instead of "scab".
- **Predictions:**
  - E3b-P1 (≥ 57 / 60) and E3b-P2 (0 safety-critical): held.
  - E3b-P3 (E3b-05 would miss): **wrong**. It passed.
