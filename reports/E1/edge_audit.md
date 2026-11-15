# Text at cell edges: audit (2026-11-15)

**Why:** E3-018 (a lost comma) and E3b-27 (fungicide p. 60) suggested that text at table-cell edges is dropped or put in the wrong cell. This audit measures how often, before any fix.

**Environment:** `ENV-NATIVE-1`, pdfplumber as locked in `uv.lock`, release register `916f131a…`. Tool: [`tools/edge_audit.py`](../../tools/edge_audit.py). Raw output: [`edge_audit.json`](edge_audit.json).

## Predictions (written before the run)

| ID | Prediction | Result |
|---|---|---|
| EA-P1 | The lost characters have their centre just outside their own cell | **Held**, for 8 of 12 hits. The tool also found 2 other mechanisms: text drawn over other text, and text in no cell at all |
| EA-P2 | Fewer than 0.1 % of table characters are affected | **Held:** about 70 characters in 221,386 |
| EA-P3 | Tens of cells across both registers are affected | **Wrong, too high:** 12 detector hits plus 1 found by the lexicon. They affect **13 use rows** |
| EA-P4 | "Paddy Sheath / B light" is a different mechanism: a column line drawn through a word | **Wrong.** The PDF itself places "Sheath" in the crop column with clean margins. No geometric rule can see it |

## Method

pdfplumber assigns each character to the cell that holds its centre. The tool groups each text line's characters into *runs*. A gap wider than 0.45 em ends a run, so a word space stays inside a run but the padding between two cells does not.

A run is reported if any of these holds:
- its characters fall in two or more cells;
- any of its characters falls in no cell;
- its glyphs overlap one another.

Each report is classified:

| Kind | Test | Meaning |
|---|---|---|
| `orphan` | a character inside the table falls in no cell | that cell has no drawn borders; its text is lost |
| `overlap` | two glyphs share more than half of the narrower one's width | two texts are drawn on top of each other |
| `straddle` | the tightest cut between two cells is under 0.5 pt | a cell line cuts a word: letter spacing, not padding |
| `adjacent` | anything else | two cells' texts that merely sit close (not an error) |

**Threshold check.** All 8 real straddles have cut gaps between −0.12 and +0.05 pt. The one false positive is at 0.34 pt. The closest `adjacent` pair is at 0.70 pt. Straddle counts at 0.25 / 0.5 / 1.0 / 2.0 pt are 8 / 9 / 10 / 11, so 0.5 pt sits in the gap. The detector is meant to be generous: a false positive costs one review line, while a miss costs a wrong row.

## Results

The first prototype reported 53 runs on 32 pages. The detector as built into the extractor (`extract/edges.py`, which drops space glyphs before forming runs) reports 32 runs on 23 pages. **Both find the same 12 defects** in the agricultural sections; only the count of harmless `adjacent` runs differs. With the prototype's counts, in the agricultural sections:
- 39 are `adjacent` (not errors);
- 2 are `orphan`;
- 8 are `straddle`;
- 2 are `overlap`.

Each non-adjacent hit was checked against `pdftotext -layout` (poppler, an independent reader).

| # | Page | Kind | Stored in the release register | The page shows | Effect |
|---|---|---|---|---|---|
| 2 | ins. p. 25 | orphan | uses 1480–1481: crop **Brinjal**, wait 31 | crop **Cotton** (the cell has no top border, so it was taken as merged from the row above) | **Wrong crop.** Brinjal gets two waiting periods (3 and 31 days); Cotton gets a false "not approved". **No anomaly was raised.** |
| 3 | ins. p. 55 | straddle | use 2036: pest `…(Bemisia tabaci) Thrips…`, dose `518 ,` | `…(Bemisia tabaci), Thrips…`, dose 518 | joined pest `whitefly thrips` (E3-018); dose unparsed |
| 4 | ins. p. 80 | straddle | use 2280: pest `(Spodoptera frugiperda & Stem borer`, dose `) 78.75+13.50` | `(Spodoptera frugiperda) & Stem borer`, dose 78.75+13.50 | dose unparsed; pest key keeps an open bracket |
| 5 | ins. p. 84 | overlap | use 2323: `Aphid (Aphis gossypi)` | the same | **none** (glyphs touch; the text is right) |
| 29, 30 | fung. p. 60 | straddle | use 730: pest `…(Phytophthora infestan Early Blight (Alternari solani)`, dose `75+54 - 87.5+63 s) and a` | `…(Phytophthora infestans) and Early Blight (Alternaria solani)`, dose 75+54 – 87.5+63 | both pests fused into one ID; dose unparsed |
| — | fung. p. 60 | (lexicon) | use 731: crop `Paddy Sheath`, pest `B light` | crop Paddy, pest Sheath Blight | wrong crop ID `paddy_sheath`; Paddy / sheath blight missed (E3b-27) |
| 40, 41 | fung. p. 73 | straddle | uses 892–893: `N S orthern leaf blight,` / `outhern leaf bligh t` (two records) | one row: Corn, `Northern leaf blight, Southern leaf blight` | first letters taken by 8–9 pt sliver cells; both pests unmatchable |
| 44 | fung. p. 76 | straddle | uses 947–948: `Alternaria` / `153 (13.5 + 139.5)` | the same | **none** (the detector's false positive) |
| 45 | fung. p. 77 | orphan | uses 955–956: pest `Anthracnose &` and `Powdery Mildew` as two records; dose a.i. empty | one row: Mango, `Anthracnose & Powdery Mildew`, dose a.i. 0.33+15 | dose lost (a `DANGLING_MERGE` anomaly was raised and allowed); one row split in two |
| 47 | fung. p. 82 | overlap | use 1015: pest `Sheath Blight, Leaf`, dose `B 1l0as0t + 70 + 50` | pest `Sheath Blight, Leaf Blast`, dose 100 + 70 + 50 | the pest "leaf blast" became "leaf"; dose unparsed |
| 49 | fung. p. 84 | straddle | use 1032: dose a.i. `… Metalaxyl-M 0.011`, dose form `0.3 )` | `… Metalaxyl-M 0.011)`, 0.3 | dose form unparsed |

## What this shows

- **The parser failed closed on numbers.** All 6 contaminated dose cells are stored as `unparsed`, so the app would show no number rather than a wrong one. No wrong dose or waiting period came from a straddle.
- **The one wrong fact came from an orphan cell** (#2: Brinjal for Cotton), and the build raised **no anomaly** for it. The extractor took a borderless cell that holds text for a vertical merge. This is the most serious finding. E3 did not sample that page.
- **The other errors are wrong pest IDs.** Those give "not approved" answers where the page approves the use: the safe direction, but wrong.
- **The mechanisms are different:**
  - overflow past a column line;
  - sliver cells;
  - glyphs drawn over each other;
  - missing borders;
  - a pest name placed in the crop column.

  No single geometric rule fixes all of them. A rule tuned on 8 examples would also be fitted to those examples.

## What it does not show

- It sees only geometric defects. The "Paddy Sheath" row was found by the crop lexicon, not by this tool. Other non-geometric errors (a missing separator that is not near a cell line, for example) are what the E1 random-row golden set measures.
- It covers this edition of the register only. A new edition must be re-audited; the fix below makes that automatic.

## Decision (fix, next)

1. **Detect in the extractor:** the same four tests run on every table. Each orphan, overlap or straddle hit becomes an anomaly on its row, and the release build refuses an anomaly that is not covered.
2. **Correct through a reviewed file**, `data/corrections.toml`. Each entry gives:
   - the row's stored values *before* the correction;
   - the values *after*, taken from the page;
   - the poppler line as evidence;
   - a reviewer.

   A correction whose "before" no longer matches is stale, and the build fails.
3. **Corrected rows are marked in provenance**, so an answer can say that a field was corrected from the page text.
4. **Remove the crop ID `paddy_sheath`**, which the crop review accepted.

## Fix: built and measured (2026-11-15)

**Built** (ADR-007, L1 §16):
- the detector in the extractor;
- 12 corrections in [`data/corrections.toml`](../../data/corrections.toml) (10 set, 2 drop);
- 2 allow entries pinned to their exact text;
- 4 pest-lexicon rows for the names the corrections made readable;
- removal of the crop ID `paddy_sheath`.

Row images for review are in [`rows/`](rows/).

**Visual check:** every correction was compared with the rendered page (`rows/*.png`). Eleven match it as read. **C-11 is a judgment call:** "Leaf Blast" is in the PDF's text layer, but on the rendered page "Blast" is hidden under the dose cell, so a reader sees "Sheath Blight, Leaf". The entry says so.

**Predictions for the rebuild (written before it):**

| Prediction | Result |
|---|---|
| 2,372 uses (2 split rows dropped) | Held |
| all 12 `CELL_*` anomalies covered | Held: 0 uncovered anomalies |
| a few new unknown-pest names | Held: 3 (tomato late and early blight, northern and southern leaf blight). Now lexicon rows awaiting review |
| release refused only for unreviewed inputs | Held: 12 corrections, 2 allow entries, 4 pest rows |

**E3 on the corrected dev register** (`b5bd684e…`; predictions 150 / 31 / 59 were written before the run):

| Suite | Before (release `916f131a…`) | After | Note |
|---|---|---|---|
| E3, 150 queries | 149 / 150 | **150 / 150** | E3-018 fixed |
| extras, 31 | 31 / 31 | 31 / 31 | — |
| E3b, 60 | 58 / 60 | **59 / 60** | E3b-27 fixed. **Not independent:** E3b-27 led to this fix. The remaining miss, E3b-28, is a lexicon gap left unfixed on purpose |

Safety-critical errors stayed at 0 in every run.

**Gate:**
- 192 unit and 11 golden tests pass;
- ruff and mypy are clean;
- all 29 mutation checks are killed. E-M6 survived first, as predicted; a gate test was added.

**Found on the way, not fixed:**
- `turcicum_blight` and `turcicum_leaf_blight` are two IDs for one disease.
- Use 969's pest is one joined ID, `northern_corn_leaf_blight_southern_corn_leaf_blight`: the register prints the two names with no separator.

Both join the open list of joined pest IDs.

## Release (2026-11-15, after the review)

**Review:** delegated by the user ("I allow you to review them"); see [`edge_review_record.md`](../../data/lexicon/review/edge_review_record.md). Like C-11's hidden "Blast", C-03 and C-04 punctuation is clipped on the rendered page but present in the text layer.

**Release build** `d86befe7…`:
- 2,372 uses, 659 products, 12 corrections, 0 uncovered anomalies;
- **byte-identical on a second build.**

E3 on the release, matching the predictions written before the run:
- 150 / 150;
- extras 31 / 31;
- E3b 59 / 60;
- 0 safety-critical errors.

**End to end through the API:**
- Dimpropyridaz on Cotton for whitefly: **APPROVED**, wait 31, p. 25, `corrected: ["crop_raw"]` (before: not approved for the crop);
- on Brinjal: only its own row (wait 3, p. 24; before: two rows with waits of 3 and 31).
