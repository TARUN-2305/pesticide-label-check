# E3 query suite: lookup correctness

Written 2026-11-14, **before the first run**. Plan: [evaluation plan, E3](../../docs/evaluation_plan.md).

## Files

| File | What |
|---|---|
| `candidates.jsonl` | Every query written in the session (181) |
| `queries.jsonl` | The 150-query suite, drawn by `tools/e3.py select` (seed 20261114) |
| `extra.jsonl` | The 31 candidates not drawn. They are run and reported separately, never mixed into the 150 |

SHA-256 at the time of writing (before any run):
- `candidates.jsonl`: `164a27a99be381df3245ed6dd366bd7bdb8a517d14aa5c08498c0a26232861a5`
- `queries.jsonl`: `6bf8bf3f53e618f24536c353568b29cbe8a8c514245890a8044019787c98cc13`
- `extra.jsonl`: `989d020cd8b2da3ed673d32039cdb7aaf48a6d377efc55d0647cfd39fd7b8f29`

## How the queries were written

**Labeller:** the assistant (Claude), 2026-11-14. The labeller has seen the code and the lexicon files earlier in the project, so this is not a blind labelling. To limit that, no query was run, and no lexicon file was opened, while writing.

1. **Pages.** 30 pages were drawn with `random.Random(20261114)`: 8 from insecticide single-ingredient pages 3–53, 7 from insecticide combination pages 55–88, 8 from fungicide single pages 3–44 and 7 from fungicide combination pages 46–91.
2. **Text source.** Each page's text came from poppler's `pdftotext -layout`, a different tool from the extractor (pdfplumber). Every product block was read to its end, across page breaks. A product's heading was searched in both registers, to find every block it appears in.
   - **Correction (after the first run):** this search was **not** done for every product. Pyriofenone 18 % SC (fungicide p. 35) and the Chlorantraniliprole + Tebuconazole + Clothianidin GR product (insecticide p. 64) each have a second entry that I missed.
   - The run found both. The two labels were corrected with the page text quoted in [`reports/E3/report.md`](../../reports/E3/report.md), and each corrected item has a `correction` field.
   - After the correction: `queries.jsonl` is `56989722…`, `extra.jsonl` is `aad03be9…`, `candidates.jsonl` is `01332672…`. The hashes below are the ones the first run used.
3. **Page-written pools:**
   - APPROVED: 82 candidates.
   - NOT_APPROVED_FOR_CROP: 31. The crop does not occur in any of the product's blocks.
   - NOT_APPROVED_FOR_PEST: 26, at most one per page. The crop is approved, but no row on that crop names the pest.
   - Sampling: the 60 / 30 / 20 the plan fixes were drawn from these pools with the same seed.
4. **Fixed strata,** checked by a case-insensitive search of all page text:
   - **UNKNOWN_PRODUCT** (10): herbicides, brands, a misspelling, a concentration or formulation that is not registered, and banned chemicals.
   - **UNKNOWN_CROP** (10): crops that occur nowhere in the register, including 3 misspellings.
   - **AMBIGUOUS** (10): a crop or pest name that covers several register entries, *where the answer differs between them*. Example: "blight" on potato for Mancozeb 75 % WG, which is approved for late blight but not early blight.
   - **Restriction overlay** (10): products whose ingredient is on the banned/restricted list, written from the register page plus the list. Five of them collide: the register approves a use that the list bans.
5. **Expected rows.** These are page descriptions, not IDs: document, page, heading, crop text and pest text as printed, plus the number of rows `n` they should match. `tools/e3.py` maps them to use-record IDs through the stored raw text. A description that matches a different number of rows is reported as a problem.
6. **Spelling variants and Indian-English names** are deliberate:
   - crops: bhindi / ladies finger, brinjal / eggplant, paddy / rice, bajra / pearl millet, ragi / finger millet, jowar / sorghum, urad / black gram, bengal gram / chickpea, pigeon pea / red gram, corn / maize;
   - spellings: "copper sulfate", "diamondback moth", "mealybug", "white fly";
   - formatting: no hyphen, lower case, ingredients in reverse order;
   - the register's own typos: "Ccumber", "Sheath Bight", "leaf minor".

### Interpretations (stated before the run)

- **Ingredient level** (L2 Q2, §11 A4): an ingredient text names an *ingredient set*. "mancozeb" means the single-ingredient mancozeb products, not mixtures that contain mancozeb.
- **Restrictions** are expected on every answer whose product resolves, including `UNKNOWN_CROP` and `AMBIGUOUS` answers. An unknown product carries none (L2 §4 overlay).
- **`conflict`** is expected `true` only where the list names the queried crop. That is the L2 rule; a category such as "vegetables" does not count.

## Predictions (before the first run)

| ID | Prediction |
|---|---|
| Q-P2 (L2 §9) | Outcome accuracy ≥ 98 % on the first run. |
| E3-P1 | My forecast now, knowing the design: **80–92 %**, so I expect Q-P2 to be **wrong**. Two reasons: (a) the engine returns AMBIGUOUS only when an alias is shared, so I expect ≤ 3 of the 10 AMBIGUOUS cases right; (b) some Indian-English names and spelling variants will be missing from the lexicon. |
| E3-P2 | 0 safety-critical errors (APPROVED where the expectation is NOT_APPROVED_*). |
| E3-P3 | All 5 expected conflicts are flagged, and no other answer sets `conflict`. |
| E3-P4 | ≥ 95 % of row descriptions match exactly `n` rows. |
| E3-P5 | Among APPROVED-expected queries answered APPROVED, row precision ≥ 0.98 and recall ≥ 0.95. |
| Q-P3 (L2 §9) | At least one case exposes a lexicon gap. My forecast: **≥ 3**. |

Misses are classified after the run as one of: labelling error (mine), lexicon gap, extraction error, engine or design gap. A labelling error is corrected only with the page evidence quoted, and the first-run numbers are kept as they were.

## E3b: a fresh suite after the L2 §13 fixes (written 2026-11-15, before its first run)

The 150 queries above were used to design the §13 fixes, so a re-run on them is not an independent measure. **E3b** is.

- **Pages:** 10 new pages, drawn with `random.Random(20261115)` from the same four sections, excluding the 30 E3 pages:
  - insecticide p. 4, 25, 41, 84, 86;
  - fungicide p. 13, 14, 31, 60, 78.
- **Method:** the same as E3 (poppler text; blocks read to their end; every heading searched in both registers), with the same labeller.
- **File:** `e3b.jsonl`, 60 queries, SHA-256 `047394ac01b6730114a0f59e9af20cbb9128b4a672871b6abf10a27e78059acd`.
- **Strata:**
  - APPROVED 30, NOT_APPROVED_FOR_CROP 15, NOT_APPROVED_FOR_PEST 11;
  - AMBIGUOUS 4: general names whose other forms are registered on the crop for other products, checked in the page text.
- **Not covered:** the unknown-name and restriction strata are not repeated (E3 covered them). An unprompted reading choice is one known risk: E3b-05 asks "shoot and fruit borer" where the page prints "Fruit & Shoot Borer".

| ID | Prediction (before the run) |
|---|---|
| E3b-P1 (= L2 G-P4) | ≥ 57 / 60 (95 %) outcomes right |
| E3b-P2 | 0 safety-critical errors |
| E3b-P3 | E3b-05 is the most likely miss: the reversed word order is a different pest name unless the lexicon merged it |
