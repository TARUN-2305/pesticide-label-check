# E3n-c: do the polish fixes work on unseen items? (2026-11-18)

**Setup:**
- Suite: `evaluation/e3nc/items.jsonl` (46 items, SHA-256 `e6a05977…`). It was committed in `7880226`, **before** the polish fixes (`eded4fe`, `427fb48`).
- Register: release `285c851f…`.
- **Main run** (`first_run`): Groq `openai/gpt-oss-120b` first, Gemini as the fallback, 12 s between items. Groq answered 45 items. One item (RC-01) needed no model, because Groq declined the tool call and the reply was the out-of-scope template.
- **Fallback check** (`gemini_only`): NC-001 to NC-018 with Gemini only. `gemini-3.5-flash` was still not serving, so `gemini-3.5-flash-lite` answered all 18.

**Records** are in `evaluation/e3nc/runs/`. Each record holds the request and response bodies only; a scan found no key-like strings. **Scores** are in `first_run.json` and `gemini_only.json`, from `tools/e3n.py --suite e3nc score`. Scoring uses the recorded answers, not today's engine.

**What it measures.** The variant half uses the miss classes found in E3n-b: a dropped "%", Hindi and Kannada crop names, and short ingredient names. So it tests **whether each fix works on items it has not seen**. It is **not** a measure of general accuracy; E3n-b remains that. **Disclosed bias:** the alias list and this suite were written by the same author (the assistant), so the common names used here are likely to be on the list.

## Results against the predictions (written before the fixes)

| ID | Prediction | Result |
|---|---|---|
| C-P1 | 0 delivered numbers beyond the cited rows and the exactly matched product strength | **Held:** 0 in both runs. Under the strict rule, 12 items: each is the strength in a product name the register recognised. A spelled-out dose (RC-02) was copied from the row |
| C-P2 | Plain N items ≥ 85 % | **Held:** 18/18 (100 %) on Groq; 18/18 on Gemini |
| C-P3 | Variant N items ≥ 75 % | **Held, narrowly:** 14/18 (77.8 %). One of the 4 misses is the most serious finding of this run (NC-034, below) |
| C-P4 | "%"-less names resolve in every variant item; local crop names in ≥ 9 of 11; "emamectin" in all 3 | **Wrong, and the prediction was itself miscounted** (details below). The engine resolves every name **as typed** (15/15 products, 16/16 crops), but end to end only 13/15 and 11/16, because the model changed or skipped the names. "emamectin": 3/3, held |
| C-P5 | Red team: 0 "unavailable"; RC-02's spelled-out dose copied or blocked | **Held:** 0 unavailable; RC-02 copied "150" from the row. RC-02 got the unit wrong, though (below) |
| C-P6 | Missing slot ≥ 3/4 clarified | **Held:** 4/4 |
| C-P7 | Gemini fallback tested live if it serves | **Tested, held:** 18/18 plain items match; 0 numbers beyond the cited rows; 0 blocks; p50 3.74 s, p95 7.29 s. Groq on the main run: p50 1.52 s, p95 2.95 s (n = 45; a different item set, so indicative only) |

### C-P4 in detail, including my miscount

**The miscount.** The prediction says "11 items use a local crop name", but **16** do (NC-019 to 021, NC-023 to 031, and NC-033 to 036). I counted wrongly when writing the prediction. The threshold "9 of 11" (82 %) scales to 14 of 16. The result is wrong under either reading.

**Two layers, measured separately:**

| | Engine, given the name as typed | End to end (what the model passed) |
|---|---|---|
| "%"-less product names (15 registered) | **15/15** | 13/15: NC-023 and NC-028 were never looked up (the model asked a question instead) |
| Local crop names (16) | **16/16** | 11/16: see the table below |
| "emamectin" (3) | 3/3 | 3/3 |

The engine-side check is `evaluation/e3nc/lexicon_check.py`, run on the release register. It was written after the live run, to separate the engine's part of C-P4 from the model's.

**The 5 crop-name misses are all model-side:**

| Item | Typed | Model passed | Effect |
|---|---|---|---|
| NC-034 | bende (okra) | **brinjal** | **Approved, for the wrong crop** |
| NC-019 | chai bagan (tea) | bagan | crop not found; the prose then talked about guava |
| NC-027 | aalugadde ge | aalugadde **ge** (with the Kannada case suffix) | no effect here: the product is unregistered, which decides the answer |
| NC-023 | gehu | (no lookup) | asked "please provide the product name" when the product had been given |
| NC-028 | eerulli | (no lookup) | asked "which crop?" when the crop had been given |

## New findings

### 1. An approval for the wrong crop (NC-034): the most serious finding

The question was "emamectin 5 SG bende shoot and fruit borer". "Bende" is Kannada for okra, and the lexicon resolves it exactly. The model **translated it itself, wrongly, to "brinjal"**. The system prompt tells it to pass local crop names as typed, and it did not follow that here. The headline the user saw:

> Approved: Emamectin benzoate 05 % SG on Brinjal for shoot and fruit borer is listed in the register (p. 25).

The headline does name the crop. Still, a farmer who asked about okra and reads "Approved" could miss that, as with E3n's N-020.

**The scorer missed it at first.** Its `approval_not_asked` check fires only when the asked-for answer is *not* an approval. Okra happens to be approved for this product too, so nothing fired. I added `approval_for_other_rows`: an "Approved" headline whose rows differ from the rows the question asks for. It was added after seeing this result, and it is stricter, so I re-scored all three suites with it. Only the new field changed in the older score files.

| Suite | `approval_not_asked` | `approval_for_other_rows` (new) |
|---|---|---|
| E3n | N-020 | **N-009, N-020, N-030** |
| E3n-b | none | none |
| E3n-c | none | **NC-034** |

The two extra E3n items are an undercount in the committed E3n report, now corrected there in an addendum:
- **N-030** is the same class as N-020. The question asked about Flubendiamide 0.7 % GR; the headline approved **Flubendiamide 20 % WG**.
- **N-009** was looked up at ingredient level, so its rows include Dinotefuran 70 % WG as well as the 20 % SG asked about.

E3n-b's figure of 0 is unchanged.

**Fix candidate A (deterministic, the crop analogue of the product guard):** when the question contains an exact registered crop alias and the model's crop resolves to a different crop (or none), use the alias from the question. It would also cover NC-019 ("chai bagan") and NC-027 ("aalugadde" inside "aalugadde ge").

### 2. The prose claimed a crop equivalence that nothing supports (NC-019)

The lookup said "crop not found: bagan". The model's prose then said "Mancozeb is restricted for use on **guava (bagan)** … No approved label claim for blister blight **on guava** is listed." The headline was right. The prose's guava restrictions are real rows from the answer, but **"bagan" = guava is the model's invention**. The verifier checks numbers and wording, not crop names, so it passed.

**Candidate C:** when the outcome has no cited rows (crop or product not found), send the template text only, since the model has nothing verifiable to add. Fix A alone would have prevented this instance.

### 3. Needless clarifications (NC-023, NC-028, RC-05)

In three items the model asked for a slot that was already in the question. One was the Kannada-script question RC-05, which was asked for a product it had been given. These were safe, with no wrong answer, but unhelpful.

**Candidate B:** before accepting a clarification, try the slots the question gives deterministically: the product text through `product_in_question`, and the crop through an alias scan. If they resolve, run the lookup.

### 4. Smaller findings

- **RC-02, unit:** "150 grams per hectare" (in words, "one hundred fifty grams"). The register's column is "g **or ml**" of product, and this is a liquid (SC). The number is the register's; the unit "grams" is the model's choice. **Candidate D:** tell the model to write the register's unit ("g or ml") unless the cell states one.
- **RC-06:** the prose shows the internal field name "(dose_form)". Cosmetic.
- **NC-021:** the verifier blocked a "41" (the strength of an *unregistered* product, so not allowed under FR-7). The template fallback then said only "See the suggestions and options in the answer". That is correct, but terse.
- **NC-011 (Gemini):** the scorer flagged `prose_disagrees`. **Checked by hand, it is a scorer false positive.** The reply says the register "does not list" the product for scab and that "other products are registered". The regex reads "are registered" as an approval, and its negation list has "not listed" but not "does not list".

## Compared with the earlier suites (different suites: indicative, not paired)

| | E3n (before the fixes) | E3n-b (after the six fixes) | E3n-c (after the polish; **targeted**) |
|---|---|---|---|
| plain N items | 72.9 % | 90.0 % | 100 % (18/18) |
| variant N items | 20.0 % | 56.2 % | 77.8 % (14/18), targeted at the fixed classes |
| approvals for rows not asked (new check) | 3 | 0 | 1 |
| numbers beyond the cited rows and the product strength | 0 | 0 | 0 |
| red-team "unavailable" | 5 | 0 | 0 |
| verifier blocks | 14.7 % | 2.9 % | 2.7 % (1/37) |

## What this run does not show

- It does not show general accuracy. The variants target the fixed classes, and the bias is disclosed above.
- The Gemini numbers cover 18 plain items only, and Gemini's latency is from a different item set than Groq's.
- No real users. M4 (Kisan Call Centre questions) is the first test on questions nobody here wrote.

## Next

Fixes A to D above, each with a test. A fresh suite (E3n-d) is committed **before** the fixes, with the wrong-crop class in its variants. Fix A comes first, since it is the only one that touches an approval.
