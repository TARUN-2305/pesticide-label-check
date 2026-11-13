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
