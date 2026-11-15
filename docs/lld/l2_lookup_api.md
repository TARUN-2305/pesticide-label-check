# LLD L2: Lookup engine and HTTP API (milestone M2)

Version 0.1 (2026-11-13). Status: **designed, not implemented**. It depends on the L1 register. Implements FR-5, FR-6 and NFR-3. Decisions: ADR-001, 003, 004, 006.

## 1. Questions it answers

| # | Question | Example |
|---|---|---|
| Q1 | Is product P approved on crop C (for pest X)? Dose, dilution, waiting period? | "Chlorantraniliprole 18.5% SC on tomato for fruit borer" |
| Q2 | Ingredient-level: which registered formulations of I are approved on C? | "chlorpyrifos on brinjal" |
| Q3 | What does the register approve for crop C against pest X? | "tomato, fruit borer: what's approved?" |

Q3 is also what `NOT_APPROVED_*` answers include, so that a "no" is never a dead end.

## 2. Module layout

```text
src/labelclaim/
  register/reader.py   # read-only connection, typed row mappers
  lookup/
    names.py           # resolve(text, kind) -> Resolution
    engine.py          # lookup(query) -> Answer (pure function of reader + query)
    models.py          # Query, Resolution, Answer, Outcome, Citation (dataclasses)
  api/
    app.py             # FastAPI factory; settings; middleware
    schemas.py         # Pydantic v2 request/response models (the public contract)
    errors.py          # error envelope, exception handlers
    __main__.py        # `python -m labelclaim.api --register build/register.sqlite`
```

`engine` has no FastAPI import. The API is a thin adapter around it, and the M3 tool layer calls the same `lookup` function.

## 3. Name resolution (`names.py`)

```python
@dataclass(frozen=True)
class Resolution:
    kind: Literal["product", "ingredient", "crop", "pest"]
    status: Literal["exact", "ambiguous", "unknown"]
    ids: tuple[str | int, ...]                 # exactly one when status == "exact"
    suggestions: tuple[Suggestion, ...]        # (id, display, score), at most 5, score-sorted
```

1. **Key normalisation:** the same function as the build (L1 §6.3), shared by import so the two planes can never drift.
2. **Exact alias match.** One ID gives `exact`. More than one ID (an alias shared by two crops) gives `ambiguous`.
3. **Products:** the user's text is parsed with the L1 heading grammar.
   - If it parses into ingredients + concentration + formulation, match on all three.
   - If it parses into ingredients only, the query becomes ingredient-level (Q2).
   - Brand names are **not** in the register. M2 returns `unknown` with the hint "type the chemical name printed on the label". Mapping brands to ingredients is a separate, sourced dataset and out of M2's scope.
4. **No exact match:** compute fuzzy candidates with the normalised Levenshtein ratio over the alias keys (`rapidfuzz`, MIT licence). Candidates scoring ≥ 0.85 become `suggestions` and the status is `unknown`. **No fuzzy candidate is ever used to answer** (ADR-006).

## 4. Matching and outcome selection (`engine.py`)

Input: `Query(product_text | ingredient_text, crop_text, pest_text | None)`.

```text
r_crop = resolve(crop);  r_prod = resolve(product or ingredient);  r_pest = resolve(pest) if pest
if r_prod.unknown                      -> UNKNOWN_PRODUCT (+suggestions)
if r_crop.unknown                      -> UNKNOWN_CROP    (+suggestions)
if any ambiguous                       -> AMBIGUOUS       (+the candidate sets)
rows = use_record ⋈ product where product ∈ r_prod.ids and crop_id = r_crop.id
if not rows                            -> NOT_APPROVED_FOR_CROP
                                          + crops this product IS approved on (sorted)
                                          + Q3 list for (crop, pest) if pest given
if pest given:
   rows_p = rows where use_record_pest contains r_pest.id
   if not rows_p                       -> NOT_APPROVED_FOR_PEST
                                          + pests this product IS approved for on this crop
                                          + Q3 list for (crop, pest)
   rows = rows_p
                                       -> APPROVED(rows)
overlay: if any ingredient of the product has a restriction -> flag BANNED_OR_RESTRICTED (+ raw detail)
```

**`Outcome` is a closed enum.** The API schema enumerates it, so clients must handle every case.

**Pest matching** uses the per-row pest IDs from L1. A row listing "Thrips, Aphid, White fly" matches each of the three.

**Unknown pest:** the answer degrades to crop level (all approved rows on the crop) with `pest_status = "unknown"` and suggestions. It never claims the pest is covered.

## 5. Answer model

```python
@dataclass(frozen=True)
class Citation:
    document_id: str; register_date: str; page_first: int; page_last: int
    bboxes: tuple[BBox, ...]; url: str                  # url = official PDF + "#page=N"

@dataclass(frozen=True)
class ApprovedUse:
    product_heading: str; crop: str; pest_raw: str; application_note: str | None
    dose_ai_raw: str; dose_form_raw: str; dilution_raw: str; wait_raw: str   # ADR-004: shown verbatim
    wait_days: tuple[int, int] | None                                        # parsed, for sorting/filtering only
    citation: Citation

@dataclass(frozen=True)
class Answer:
    outcome: Outcome; restriction: Restriction | None
    uses: tuple[ApprovedUse, ...]                 # APPROVED only
    alternatives: tuple[ApprovedUse, ...]         # Q3 list on NOT_APPROVED_*
    approved_crops: tuple[str, ...]; approved_pests: tuple[str, ...]
    suggestions: Mapping[str, tuple[Suggestion, ...]]
    register: RegisterInfo                        # date(s), build_hash
    disclaimer: str                               # fixed text (requirements §7)
```

**Invariant (property-tested):** for every `ApprovedUse` in an answer, each raw field equals the stored raw field of the cited `use_record`. Nothing in the engine creates or edits text.

## 6. HTTP API (`/v1`)

| Method and path | Body / params | Response | Notes |
|---|---|---|---|
| `GET /v1/register` | — | `RegisterInfo` (documents, dates, `build_hash`, counts) | cacheable |
| `POST /v1/lookup` | `{product?: str, ingredient?: str, crop: str, pest?: str}` (exactly one of product or ingredient) | `Answer` | the main endpoint |
| `GET /v1/products?q=` | `q` of 2–80 characters | ≤ 20 `{id, heading, ingredients, formulation}` | autocomplete |
| `GET /v1/crops?q=` | `q` of 1–60 characters | ≤ 20 `{id, display, aliases}` | autocomplete |
| `GET /v1/pests?q=&crop=` | | ≤ 20 | optionally restricted to a crop |
| `GET /healthz` | — | `{status, build_hash}` | liveness and readiness (the register is opened at startup) |

**Contract rules:**
- **Inputs:** Pydantic models with `extra="forbid"`; maximum string length 120; text must be printable (NFC). Anything else gets a 422 inside the error envelope.
- **Errors:** `{"error": {"code": "...", "message": "...", "request_id": "..."}}`, the same shape for 404, 405, 422 and 500.
- **Lookups are not errors:** a lookup that finds nothing is a **200** with an outcome. `UNKNOWN_PRODUCT` is an answer, not a failure.
- **OpenAPI:** the spec is exported to `openapi.json`. A test fails when the exported file is stale, as in Porter's R6.

**Middleware:**
- a request ID;
- a structured access log that records the outcome, never the query text (NFR-5);
- an in-process token-bucket rate limit (60 requests/min per IP; configurable);
- CORS restricted to the configured web origin;
- `Cache-Control` on `GET /v1/register`.

**Concurrency:**
- SQLite is opened read-only and immutable, with one connection per worker thread (`check_same_thread=False` is not used).
- Routes are sync, so FastAPI's thread pool handles them, as in Porter's R6.
- There is no shared mutable state except the rate limiter, which takes a lock.

## 7. Performance

| Metric | Target (NFR-3) | Method |
|---|---|---|
| `lookup()` in-process p50 / p95 | ≤ 2 ms / ≤ 20 ms | 1,000 queries from the E3 suite, 5 runs, warm cache; report each run's p50/p95 and the median across runs |
| `POST /v1/lookup` over HTTP | p95 ≤ 100 ms | uvicorn, 1 worker, local client, the same suite |

Indexes: `use_by_crop`, `use_by_product`, and the primary keys of the alias tables.

## 8. Tests (written before the implementation)

| Group | Tests |
|---|---|
| `names` | exact alias; shared alias → ambiguous; fuzzy suggestion never resolves; key normalisation identical to the build's (an import-identity test) |
| `engine` | a table of about 40 hand-written cases over a **fixture register** (a small SQLite file built from synthetic rows), covering every `Outcome`, the restriction overlay, pest degradation and ingredient-level queries |
| properties | raw fields are copied verbatim; `NOT_APPROVED_*` answers never contain `uses`; outcomes are always enum members |
| `api` | the contract for each endpoint; the error envelope for 404/405/422/500; the rate limit returns 429 with the envelope; no query text in the logs (log capture); the OpenAPI export is fresh |
| corpus (`-m corpus`) | the E3 query suite (evaluation plan) against the real register |
| performance (`-m perf`, opt-in) | the §7 measurements, written to `reports/perf/` with an environment record |

## 9. Predictions

| ID | Prediction |
|---|---|
| Q-P1 | In-process `lookup()` p95 ≤ 5 ms (target 20) on `ENV-NATIVE-1` |
| Q-P2 | On the E3 suite, the outcome is right for ≥ 98 % of cases on the first run |
| Q-P3 | At least one E3 case exposes a lexicon gap (a crop alias missing), found and fixed through a reviewed lexicon diff, not a code change |

## 10. Mutation checks

| Mutant | Expected killer |
|---|---|
| Apply the top fuzzy suggestion as a match | the `names` fuzzy-never-resolves test |
| Return `APPROVED` when the pest filter empties the rows | the `engine` `NOT_APPROVED_FOR_PEST` case |
| Drop the restriction overlay | the `engine` banned-ingredient case |
| Log the request body | the API log-capture test |

## 11. Design addendum before M2 code (2026-11-13)

M1's results and the user's crop review changed four inputs to this LLD. The changes below are designed before any M2 code; §§1–10 stand except where noted.

### 11.1 Facts that force the changes (measured on the release register `672590d0…`)

| # | Fact | Consequence |
|---|---|---|
| G1 | Some register crop strings name several crops or a crop plus a method: "Tomato/Chilli es", "Beans (Cowpea, moong, Urd)", "Citrus, Rubber, Paddy (Rice), Tea, Vegetables", "Grapes (Soil drench)" (about 40 crop IDs) | A use must be able to belong to **several** crops (A1) |
| G2 | 694 distinct pest keys over 4,304 (use, pest) pairs. Splitting on "and" is wrong: "Shoot and fruit borer" became a pest named "shoot" (40 uses), and "Leaf and neck blast" is one disease, while "Early and late blight" is two | Do not split on "and" / "&"; a reviewed pest lexicon decides (A2) |
| G3 | Ingredient spellings differ between documents ("Aluminum" / "Aluminium" Phosphide; "Chlorpyriphos" in the restriction list) | A reviewed ingredient-variant list, so the restriction overlay cannot silently miss (A3) |
| G4 | The crop string itself carries the method ("Grapes (Soil drench)"), and it is always shown raw (ADR-004) | Mapping it to the plain crop loses no information |

### 11.2 Changes

- **A1. Many-to-many crops (schema v2).**
  - `crop_alias` may list the same alias under several `crop_id`s.
  - The build writes `use_record_crop(use_record_id, crop_id)`, and `use_record.crop_id` is removed.
  - An alias with zero matches is `UNKNOWN_CROP`.
  - Proposed re-mappings for the about 40 multi-crop and crop+method aliases go to the **user for review** as a short list. The user's reviewed rows are not changed without that review.
- **A2. Pest lexicon `data/lexicon/pests.csv`.** It has the same columns as the crop lexicon, with no `category`.
  - **Phrases:** the pest cell is split on `,` `;` `/` and newlines only. Bracketed scientific names are removed from the key, not from the raw text.
  - **Mapping:** each phrase maps to one or more canonical pests (e.g. "early and late blight" → `early_blight`, `late_blight`).
  - **Rows needing no human:** two documented, tested rules mark such rows `reviewed_by = "rule:identity"` or `"rule:plural"`:
    - **identity:** a phrase with no "and" / "&" maps to itself;
    - **plural:** a phrase ending in "s" maps to its singular when the singular also occurs in the register. "thrips" stays "thrips" because no "thrip" occurs.
  - **Everything else needs a human reviewer.** Release builds refuse on unreviewed rows and on `UNKNOWN_PEST`.
  - This is an amendment to ADR-006: rule-reviewed rows count as reviewed because the rules are code-reviewed and tested.
- **A3. Ingredient variants `data/lexicon/ingredients.csv`** (`variant, canonical, reviewed_by`).
  - The draft pairs come from a fuzzy comparison of all ingredient and restriction keys (ratio ≥ 0.9), and are human-reviewed.
  - They are applied in `ingredient_key()` during the build (products and restrictions) and in the lookup.
- **A4. Product matching.** The user's product text is parsed with the heading grammar.
  - If it parses with concentration and formulation, all three must match.
  - With ingredients only, the lookup is ingredient-level (Q2).
  - Ingredient sets match as **sets** (order-free), so "Fipronil + Buprofezin" finds "Buprofezin … + Fipronil …".

### 11.3 Additional predictions

| ID | Prediction |
|---|---|
| Q-P4 | 694 pest keys become ≤ 450 canonical pests after the rules and review |
| Q-P5 | ≥ 70 % of pest-lexicon rows are rule-reviewed, so the user reviews ≤ 30 % |
| Q-P6 | The ingredient-variant draft has ≤ 20 candidate pairs, and the user accepts ≥ 1 that changes the restriction overlay for at least one product |

### 11.4 Additional mutation checks

| Mutant | Expected killer |
|---|---|
| Split pest phrases on " and " again | a `split` test with "Shoot and fruit borer" |
| Match ingredient lists in order instead of as sets | the engine test for a reversed combination |
| Map a multi-crop use only to its first crop | the engine test for "Tomato/Chilli" found by "chilli" |

## 12. Results so far (2026-11-14)

**Environment:** `ENV-NATIVE-1` (Linux 7.0, Intel i3-1220P, Python 3.12.16). In §12.1–12.4 the register is the dev build `build/m2dev`. It uses the **unreviewed** pest and ingredient drafts, so it is not a release build. §12.5 is the release build after the user's review.

### 12.1 What was built

| Part | Files | Tests |
|---|---|---|
| Pest phrases, pest lexicon rules, ingredient variants | `normalize/pests.py`, `normalize/ingredients.py` | `test_pests_ingredients.py` (7) |
| Schema v2 | `use_record_crop`, `pest`, `pest_alias`, `use_record_pest(pest_id, phrase)`, `ingredient_variant`; build wiring in `build.py` | `test_register_validate.py` (build-tables case) |
| Lookup engine | `lookup/{models,names,engine}.py` | `test_lookup.py` (18) over a hand-written fixture register |
| HTTP API | `api/{app,schemas,ratelimit,__main__}.py`; `openapi.json` committed and checked for freshness | `test_api.py` (17) |

### 12.2 Changes found while building (each with a test)

| # | Change | Why |
|---|---|---|
| R1 | Header detection: header phrases include "name of insect pest", "infestation", "requirement", "spray solution"; unit digits ("m2") are allowed | Insecticide p. 23: two header rows had become use rows with crop "Name Of Insect Pest". Uses fell from 2,376 to 2,374 |
| R2 | The plant-part check runs **before** the split-known rule | "Shoot and fruit borer" had been split into "shoot" + "fruit borer" because both also occur alone |
| R3 | New outcome `UNKNOWN_PEST`; the crop-level rows go in `alternatives`, never in `uses` | §4 had said the answer "degrades" without naming an outcome; `uses` must only ever hold rows that match everything asked |
| R4 | `RestrictionNote.names_the_crop` and `Answer.conflict` | **A real conflict in the official data.** The 30.09.2026 register lists Chlorpyriphos 20 % EC on Ber (p. 16), while the restrictions list says "Chlorpyriphos is banned for use in Ber, Citrus and Tobacco". The answer reports the register's claim *and* sets `conflict = true`, so a client shows the restriction first (threat T12) |
| R5 | The `product` field allows up to 200 characters | The longest register heading is 166 characters (with bracketed notes) |
| R6 | Engines open their SQLite connection with `check_same_thread=False` | Each engine is still used by one thread only; only the shutdown close happens from another thread |
| R7 | Ingredient keys are *compact* (spaces and hyphens removed), and the canonical spelling is the more frequent one | "lambda-cyhalothrin" vs "lambda cyhalothrin" needs no review; a typo ("thaimethoxam") can never become canonical |

### 12.3 Measurements

| Measure | Result | Target / prediction |
|---|---|---|
| Ingredient-variant candidates | first draft 32; after the compact rule (R7), **19** | Q-P6: ≤ 20. **Wrong for the design as written, met after R7** |
| Pest phrases needing a human | **103 of about 920 (≈ 11 %)** | Q-P5: ≤ 30 %. Held |
| Canonical pests | **687** | Q-P4: ≤ 450. **Wrong** (too optimistic). Pending the human review, which may merge some |
| `lookup()` in-process, 5 runs × 1,000 queries | median p50 **0.12 ms**, p95 **0.16 ms** | target ≤ 20 ms; Q-P1: ≤ 5 ms. Held |
| `POST /v1/lookup` over HTTP (uvicorn, localhost), 5 × 1,000 | median p50 **1.5 ms**, p95 **2.3 ms** | target ≤ 100 ms. Held |
| Mutation checks (§10 and §11.4) | **8 of 8 killed**, as predicted | `reports/M2/mutants.md` |
| Tests | 147 unit, 11 golden; ruff and mypy --strict clean | — |
| Branch coverage (unit) | lookup 92–98 %, api 98–100 % (`__main__` untested), normalize 78–100 % | NFR-6 met for lookup and api, **not** for `normalize/lexicon.py` (78 %), `pests.py` / `ingredients.py` (87 %) or `build.py` |

Raw: `reports/M2/perf.json`, `reports/M2/mutants.md`.

### 12.4 Not done yet

- **E3 query suite** (150 queries written from the register pages): not built. Q-P2 and Q-P3 cannot be checked yet.
- ~~Human review of the pest phrases, ingredient pairs and crop re-mappings~~: done on 2026-11-14, see §12.5. (Commit `628e972` says the reviews were pending. That was wrong: they had been saved before that commit.)

### 12.5 Release build after the user's review (2026-11-14)

**Reviews applied** (all signed by the user, in the file or in chat):

- `data/lexicon/review/crops_multi_proposal.csv`: 30 of 31 re-mappings accepted, 1 rejected (the mosquito row). The crop lexicon now has **121** canonical crops.
- `data/lexicon/pests.csv`: the 103 phrases reviewed. Two more were decided in chat: "early and late" maps to early blight *and* late blight; "diseases viz" is not a pest (`_ignore`, R9).
- `data/lexicon/ingredients.csv`: 9 of the 19 drafted pairs kept. One more pair, sulfur = sulphur, came from R10 and was confirmed in chat ("Yes, same chemical").

**Changes found by the release gate** (each with a test in `test_pests_ingredients.py`):

| # | Change | Why |
|---|---|---|
| R8 | Pest phrases lose a leading or trailing "and" | The first release attempt refused with 29 `UNKNOWN_PEST`. The user had rightly deleted fragment rows such as "aphids and", which come from cells that end mid-list. The phrase rule now strips the dangling word, and 2 reviewed aliases were re-keyed. |
| R9 | A reviewed phrase can map to `_ignore` | "diseases viz" is a lead-in, not a pest. An `_ignore` phrase writes no `use_record_pest` row and raises no anomaly, and it is never a pest id or suggestion. |
| R10 | The ingredient draft also pairs keys with the same *spelling family* (ph~f, ae~e, oe~e, y~i, doubled letters) | "sulfur"/"sulphur" score 77, below the 85 cut-off, so the fuzzy pass missed them. Found by reading the release register's ingredient list. |

**Release register** (`build/release2`, `--release --offline`):

| Measure | Result |
|---|---|
| Build hash | `ea931038ba0c55cb…` (an earlier release the same day, before the sulfur pair, was `f35b7e8e…` with 297 ingredients) |
| Use rows | 2,374; all have a crop, 19 have several crops; 2,372 have a pest |
| Products, crops, pests, ingredients, restrictions | 655, 121, 627, 296, 97 |
| Anomalies | 10, all allow-listed (8 `UNMAPPED_TABLE`, 2 `DANGLING_MERGE`); 0 unreviewed lexicon or allow-list rows |
| Provenance | 14,116 fields re-read from their boxes |
| Build time | 34.9 s |
| Determinism | A second release build (`build/release3`) gave the same build hash, and its `register.sqlite` is byte-identical (SHA-256 `d483c74ff0ee36cd…` for both) |

**Predictions, final:**

- **Q-P4** (≤ 450 canonical pests): **wrong.** The review took 687 down to 627; the register simply names that many pests.
- **Q-P6**, second half (an accepted pair changes the restriction overlay for at least one product): **held.** 80 products contain a restricted ingredient. For **9 of them** the restriction is found *only* through a signed pair: 3 "Aluminum Phosphide" products (restriction: "Aluminium Phosphide") and 6 "Chlorpyrifos" products (restriction: "Chlorpyriphos"). Without the chlorpyrifos pair, the Ber conflict (R4) on "Chlorpyrifos 20 % EC" would be invisible.

**Real queries on the release register:**

| Query | Answer |
|---|---|
| ingredient "trifloxystrobin + difenoconazole + sulphur", tomato, late blight | `APPROVED`, p. 89, wait 14 days |
| product "Chlorpyriphos 20% EC", ber | `APPROVED` with `conflict = true` (p. 16 vs the restrictions list) |
| ingredient "sulfur", grapes, powdery mildew | `APPROVED`, 3 products, p. 35 (the query spelling differs from the register's) |

**Gate:** `tools/ci.sh --corpus`: ruff, ruff format and mypy `--strict` are clean; 150 unit and 11 golden tests pass. Unit branch coverage is 83 % overall. It is still below 90 % for `normalize/lexicon.py` (78 %), `pests.py` (87 %), `ingredients.py` (88 %), `build.py` and `extract/pages.py` (the last two are covered by the corpus tests, not the unit tests).

**Still not done:**

- the E3 query suite;
- the coverage gaps above;
- 2 use rows whose pest cell holds only scientific names (no common name to map). They are reported, not guessed.

### 12.6 E3 query suite (2026-11-14)

The full report is [`reports/E3/report.md`](../../reports/E3/report.md). The suite, its method and the predictions were written before the first run: [`evaluation/e3/`](../../evaluation/e3/README.md).

- **First run (release `ea931038…`):** outcome right for **122 / 150 (81.3 %, 95 % CI 74.7–87.3 %)**. Q-P2 (≥ 98 %) is **wrong**.
  - **1 safety-critical error** (E3-086): a false APPROVED. My prediction of 0 was wrong.
- **The cause was extraction** (R11):
  - Four product headings whose table cells stop mid-table had been filed as notes, and 6 use rows were credited to the previous product.
  - Fixed in `extract/classify.py`, with tests. The release `5e5f2de1…` has 659 products and still 2,374 uses.
  - Re-run: 123 / 150, 0 safety-critical.
- **The remaining 27 misses:**
  - 6 crop aliases missing ("bhindi", "ladies finger", "urad", "finger millet"; extra: "eggplant");
  - 10 where one pest has several IDs (spacing, plurals, register typos, a "Pests:" label);
  - 1 comma lost at a cell edge in the raw text;
  - 1 ingredient spelling at query time ("sulfate");
  - all 10 AMBIGUOUS: generic names such as "blight", "mildew", "gourd" are answered NOT_APPROVED_FOR_PEST or UNKNOWN_*. This is a design gap.
- **Held:**
  - row precision and recall 1.00 when the answer is APPROVED;
  - `conflict` right on 150 / 150 (all 5 collisions flagged);
  - 100 % of row descriptions matched.
- **My labelling errors:** 2 (a second entry of the same product that I had not searched for). Corrected with page evidence; the first-run numbers are kept.
- **Q-P3 held** (lexicon gaps found). The lexicon and design fixes need the user's review and are **not done**.

## 13. Design addendum after E3 (2026-11-14): reviewed and implemented 2026-11-15

It answers the E3 misses (§12.6). The decisions in §13.7 were made by delegated review (`data/lexicon/review/e3_review_record.md`), which also added one refinement: **the register's own general claim wins**. Results are in §13.8.

### 13.1 Facts that force the changes

- **Duplicate pest IDs.** 627 pest IDs, and many are one pest written several ways. Whitefly alone has 4 IDs: `whitefly`, `white_fly`, `whiteflies`, `white_flies`. Others: `leaf_spot` / `leafspot`, `sheath_blight` / `sheath_bight`, `brown_plant_hopper` / `pests_brown_plant_hopper`.
  - **Cause:** `rule:identity` made every distinct spelling its own pest.
  - **Effect:** a query only matches rows that use the same spelling. In E3 that produced 10 false "not approved for this pest" or "unknown pest" answers.
- **Crop names.** Crop aliases are the register's raw strings. A user's own name for a crop ("bhindi", "urad", "eggplant") does not resolve, nor does a spacing variant ("ridge gourd" against "Ridgegourd", "cowpea" against "cow pea").
- **General names.** A general name ("blight", "mildew", "rust", "gourd") is either a pest of its own (the register prints "Blight" on some rows) or unknown. So it never gives AMBIGUOUS. 7 of the 10 E3 cases got a misleading NOT_APPROVED_FOR_PEST, although a specific form *is* approved.
- **Ingredient spelling.** A user's spelling of an ingredient ("copper sulfate") resolves only if that exact spelling occurs in the register.

### 13.2 One matching rule for crop and pest names (build and lookup)

- **The rule:** `match_key(text)` = `key(text)`; then drop a leading label ("pests:", "diseases:", "insects:"); then remove every non-alphanumeric character; then fold a plural ending ("-ies" → "-y"; "-s" → "", but not "-ss").
- **Where it applies:** in `normalize/lexicon.py`, used by the build and by `lookup/names.py`, so the two planes cannot drift (as with `ingredient_key`).
- **What the build does with it:**
  - It groups lexicon aliases by match key.
  - Two canonical IDs with the same match key raise a new anomaly, `LEXICON_RULE_COLLISION`, until the lexicon merges them. So the **release gate forces every merge to be reviewed**, and the rule never merges silently.
- **Measured on the current lexicons:**
  - pests: **34 groups, 37 IDs to merge** (`data/lexicon/review/e3_pest_merges.csv`, rows `rule:match-key`);
  - crops: **no collisions**. The rule makes "ridge gourd", "cowpea", "cluster bean", "black gram" and "pigeon pea" resolve.

### 13.3 Reviewed synonyms and typos

- **Pests:** 30 rows in `e3_pest_merges.csv` (basis `review`), each with a recommendation. Examples:
  - merge: "sheath bight" → sheath blight, "leaf minor" → leaf miner, "blast disease" → blast;
  - keep separate: phytophthora foot rot vs root rot, flea beetle vs leaf beetle.
- **Crops:** 23 aliases in `e3_crop_aliases.csv`, for example bhindi, ladies finger, urad, finger millet, eggplant, tur, chana, peanut, sesame.
- **Kannada names** come with M5, from a sourced list, not from this addendum.
- **Applying a decision:** the canonical IDs in `pests.csv` are re-pointed and the aliases added to `crops.csv`, signed with the user's name. A rejected row is recorded in the review file, so it is not proposed again.

### 13.4 Ingredient spelling at query time

- **The rule:** if the user's compact ingredient key is not registered, fold it with `spelling_family` (ph~f, ae~e, oe~e, y~i, doubled letters). If **exactly one** registered ingredient has the same family, use it. With 0 or ≥ 2 matches, the outcome stays UNKNOWN_PRODUCT with suggestions.
- **Why this is allowed:** this is a deterministic fold, the same function the build uses, not a fuzzy score. So ADR-006 ("no fuzzy candidate is used to answer") holds.

### 13.5 General names: options, not guesses

- **Data:** `data/lexicon/generic_terms.csv` (reviewed). Each row is a term, its kind (crop or pest), and its members, given either by a rule or as an explicit list:
  - the rule `head:<term>` means every pest whose name ends with the term, plus the term itself;
  - an explicit list is used where the rule does not fit (ragi is a millet, but its name does not end in "millet").
  - The build expands the members, writes `generic_member(term_key, kind, member_id)`, and lists each term's members in the build manifest for review.
- **Pest term**, once the product and the crop have resolved:
  1. *options* = the members with at least one register use on this crop (any product). A blight that never occurs on potato is not an option for potato.
  2. *approved* = the options this product has a row for, on this crop.
  3. The outcome:

| Case | Outcome | Answer carries |
|---|---|---|
| no options | NOT_APPROVED_FOR_PEST | approved pests on the crop (as today) |
| approved = none | NOT_APPROVED_FOR_PEST | `options`, each marked not approved |
| approved = some | **AMBIGUOUS** | `options`, each marked approved or not, with its rows |
| approved = all | APPROVED (decision D5) | the rows, plus `options` naming each form |

- **Crop term** ("gourd", "millet", "pepper"): run the rest of the query once per member crop.
  - If every member gives the same outcome, that is the answer, with `options` listed.
  - Otherwise the answer is AMBIGUOUS, each option carrying its own outcome.
  - `conflict` is true if it is true for any option (the conservative choice).
- **Answer model:** an additive field `options: tuple[Option, ...]`, where `Option` = (kind, id, display, outcome, use_ids). The API schema gains the same field, the version goes to 0.2.0, and `openapi.json` is regenerated.
- **Safety argument:** the engine never answers APPROVED unless *every* interpretation on that crop is approved. It never answers NOT_APPROVED unless *none* is. A partial match is always shown as a choice, with the evidence for each option.

### 13.6 Tests, mutation checks and predictions (written before code)

- **Tests (fixture register):**
  - "white fly", "Whiteflies" and "whitefly" resolve to one pest; "Pests: Brown plant hopper" resolves; "ridge gourd" resolves;
  - an unmerged rule collision makes the release build refuse;
  - a general pest term in each of the four cases above; a member that occurs only on another crop is not an option;
  - a general crop term with the same outcome for every member, and with different outcomes;
  - `conflict` when the restriction names one member crop;
  - "copper sulfate" resolves; a family match with 2 candidates stays unknown;
  - properties: AMBIGUOUS answers never fill `uses`; every row in `uses` belongs to an approved option.
- **Mutants, each with its expected killer:**
  - APPROVED when only some options are approved → the "some" case;
  - options not filtered by crop → the other-crop member;
  - no plural fold → "Whiteflies";
  - first of two spelling-family candidates taken → the 2-candidate test.
- **Predictions:**

| ID | Prediction |
|---|---|
| G-P1 | After the merges, 627 pests become **≤ 570** |
| G-P2 | Re-run of the same 150: **≥ 145 right** (96.7 %), 0 safety-critical, `conflict` 150 / 150. The expected remaining miss is E3-018 (the lost comma, an extraction issue) |
| G-P3 | AMBIGUOUS stratum ≥ 9 / 10 |
| G-P4 | **A fresh suite, E3b,** gets ≥ 95 %. E3b = 60 queries from 10 newly drawn pages (seed 20261115), written after the code and before its first run. This is the honest estimate, because the 150 were used to design these fixes |

### 13.7 Decisions for the user

| ID | Decision | My recommendation |
|---|---|---|
| D1 | Adopt the matching rule (§13.2), and with it the 37 `rule:match-key` merges as one block | yes |
| D2 | Each of the 30 `review` rows in `e3_pest_merges.csv` | as recommended per row (27 merge, 3 keep separate) |
| D3 | Each of the 23 rows in `e3_crop_aliases.csv` | accept all |
| D4 | Each general term in `e3_generic_terms.csv`, and its members | accept, and check the crop lists |
| D5 | When *every* option is approved: answer APPROVED and name the forms, or always answer AMBIGUOUS | APPROVED, naming the forms ("approved for early blight and late blight") |
| D6 | Ingredient spelling fold at query time (§13.4) | yes |

**Not in this addendum:** lost separators in raw cell text. The comma on insecticide p. 55, plus joined pest names such as `thrips_whitefly` and `alternaria_blight_powdery_mildew`, are extraction issues. They get their own investigation, with E1-style evidence.

### 13.8 Results (2026-11-15)

**What was built:**
- `normalize/lexicon.py`: `match_key` and `rule_collisions`;
- `normalize/generic.py`;
- schema v3 (`generic_member`);
- engine options for general crop and pest names;
- the `options` field in the API (0.2.0);
- the ingredient fold in `lookup/names.py`.

**Tests:**
- 8 engine tests and 1 API test, written before the code and seen to fail;
- 4 lexicon and build tests, written after the code.

**Register:** release `916f131a…`, with 563 pests (G-P1: held) and 0 rule collisions.

| Prediction | Result |
|---|---|
| G-P1: ≤ 570 pests | 563, held |
| G-P2: ≥ 145 / 150 on the same suite | 149 / 150, held (the miss is E3-018, as predicted) |
| G-P3: AMBIGUOUS ≥ 9 / 10 | 10 / 10, held |
| G-P4: fresh E3b ≥ 95 % | **58 / 60 (96.7 %, CI 91.7–100 %)**, held. 0 safety-critical |

**Mutation checks:** G-M1 to G-M6 are all killed. G-M3 first **survived**, because the plural test only used "-ies"; a "Ridgegourds" case was added. A full re-run kills 23 of 23 (`reports/M2/mutants_after_g.md`).

**Open:**
- text at cell edges is dropped or put in the wrong cell (E3-018, E3b-27);
- scientific names without brackets (E3b-28);
- the spurious crop ID `paddy_sheath`.
