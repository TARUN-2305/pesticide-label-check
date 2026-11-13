# LLD L1: Register extraction (milestone M1)

Version 0.1 (2026-11-13). Status: **designed, not implemented**. The tests (§10), predictions (§11) and mutation checks (§12) are fixed here, before any code. Implements FR-1 to FR-4 and NFR-1, NFR-2 and NFR-9. Decisions: ADR-001, 002, 004, 006.

## 1. Inputs, observed on 2026-11-13

| Document | URL (ppqs.gov.in/sites/default/files/…) | Pages | SHA-256 (prefix) | In scope |
|---|---|---|---|---|
| Insecticides MUP "UPTO 30.09.2026" | `MUP (insecticide)  30.09.2026.pdf` | 108 | `e0aaa082` | Agricultural Use (p. 2–53), Combination Product (p. 54–87) |
| Fungicides MUP "UPTO 30/09/2026" | `Fungicide MUP  as on 30.09.2026.pdf` | 91 | `e6a539cf` | Single products (p. 2–44), Combinations (p. 45–91) |
| Banned / refused / restricted list (31.10.26) | `list_of_pesticides_which_are_banned…(31.10.26).pdf` | 6 | `f7e061b5` | All of it (for the restriction flag) |

Page ranges are **observed**, not taken from the documents' own indexes. The indexes are wrong:
- Insecticide: the index says combinations start on p. 53 and public health on p. 85. They actually start on p. 54 and p. 88.
- Fungicide: the index says combinations start on p. 42. They actually start on p. 45.

Out of scope in M1: public health, household, locust, bio-pesticides, herbicides and plant growth regulators. They can be added later as further sources with the same pipeline.

## 2. Facts from the data spike that the design depends on

All figures come from pdfplumber **0.11.4** (a throwaway spike environment) over all pages. The project lock resolved **0.11.10**, so the golden-page tests re-establish F1–F6 under the locked version before any other M1 code.

| # | Fact | Design consequence |
|---|---|---|
| F1 | 106 of 108 insecticide pages have exactly 1 table. Fungicide pages have 1 to 5. | Process every table on a page, top to bottom |
| F2 | Rows have 4 to 15 cells, for 6 logical columns. Insecticide: 1,119 rows with 6 cells and 1,000+ with 7–15. | Map cells to logical columns by **geometry** (§5.3), not by index |
| F3 | Column x-edges differ between tables (83 distinct signatures in one section) | Derive the bands **per table** |
| F4 | A vertically merged cell appears as one bounding box spanning several rows, with `None` in the rows below it. An empty cell is `""`. | `None` means "covered by a merge, inherit from the anchor". `""` means "the register left it blank". |
| F5 | Product headings are one cell spanning the full width, with every other cell `None` | Classify a full-width single cell as a heading candidate |
| F6 | 68 of 107 insecticide pages start with a data row | Carry the product and crop context across pages |
| F7 | Some rows hold non-crop uses ("Stored grain", "Godowns", "Public health"), and some notes ("➢ For non-agricultural use: …") | Give each crop a `category`. Store notes against the product. |
| F8 | The value formats are heterogeneous (ADR-004) | Raw text plus a best-effort typed parse with a status |

## 3. Module layout

```text
src/labelclaim/
  sources.py          # manifest, fetch, verify, cache
  extract/
    geometry.py       # Cell, Row, Table types; band derivation; cell→band mapping
    pages.py          # pdfplumber adapter (the ONLY module importing pdfplumber)
    classify.py       # row classification rules
    assemble.py       # cross-page state machine → UseRow
  normalize/
    headings.py       # product heading grammar → Product
    quantities.py     # quantity grammar → Quantity
    lexicon.py        # alias tables, canonicalisation
  validate.py         # invariants, provenance re-check, anomaly budget
  register/
    schema.sql        # DDL (§7)
    writer.py         # deterministic writer + canonical dump
    reader.py         # read-only access (used by L2)
  build.py            # orchestration + CLI (`python -m labelclaim.build`)
```

**Rules:**
- Only `extract/pages.py` imports pdfplumber, so everything else is testable with synthetic geometry.
- Pure functions everywhere except `sources.py` (network and disk) and `register/writer.py` (disk).

## 4. Data types (frozen dataclasses; mypy strict)

```python
BBox = tuple[float, float, float, float]          # x0, top, x1, bottom (PDF points, top-left origin)

@dataclass(frozen=True)
class Cell:            text: str; bbox: BBox
@dataclass(frozen=True)
class RawRow:          cells: tuple[Cell | None, ...]; top: float; bottom: float   # None = covered by a merge (F4)
@dataclass(frozen=True)
class RawTable:        doc: str; page: int; index: int; bbox: BBox; rows: tuple[RawRow, ...]

class Col(Enum):       CROP, PEST, DOSE_AI, DOSE_FORM, DILUTION, WAIT
@dataclass(frozen=True)
class Field:           text: str; bboxes: tuple[BBox, ...]; inherited_from_row: int | None
@dataclass(frozen=True)
class BandedRow:       page: int; table: int; row: int; fields: Mapping[Col, Field]; kind: RowKind

class RowKind(Enum):   HEADER, SECTION, PRODUCT, DATA, CONTINUATION, NOTE, BLANK, UNMAPPED

@dataclass(frozen=True)
class UseRow:          section: Section; product_heading: Field; fields: Mapping[Col, Field]
                       source: Provenance            # doc sha256, page(s), row ids
@dataclass(frozen=True)
class Anomaly:         code: str; doc: str; page: int; table: int; row: int; detail: str
```

## 5. Algorithms

### 5.1 Fetch and verify (`sources.py`)

`data/sources.toml` lists one entry per document:

```toml
[[document]]
id = "mup_insecticide_2026-09-30"
kind = "insecticide"           # insecticide | fungicide | restrictions
url = "https://ppqs.gov.in/sites/default/files/MUP%20%28insecticide%29%20%2030.09.2026.pdf"
sha256 = "e0aaa0826d1134361ccba09ae649dbbda442ef8773c35af70e14282fe4d6ced1"
register_date = "2026-09-30"
expected_sections = { agri_single = [2, 53], agri_combination = [54, 87] }   # cross-check only
```

1. **Cache.** Files are cached at `~/.cache/labelclaim/<sha256>.pdf`.
2. **Fetch.** On a miss, fetch over HTTPS (timeout 60 s, 3 retries with backoff), write to a temporary file, verify the hash, then rename atomically. A hash mismatch raises `SourceIntegrityError` and keeps nothing.
3. **Offline.** `--offline` never touches the network and fails on a cache miss.

### 5.2 Page adapter (`pages.py`)

Settings: `page.find_tables()` with the default lattice settings.

For each table, row and cell:
- `Cell.text` = the characters inside the cell bbox, extracted with `page.within_bbox(bbox).extract_text()`. Whitespace is collapsed and newlines become spaces.
- **Unicode NFC** normalisation; the soft hyphen (U+00AD) is removed.

Tables are ordered by `top`, then `x0`.

### 5.3 Column bands (`geometry.py`)

Goal: map each cell to one of 6 logical columns.

1. **Candidate rows.** These are the rows of this table whose non-`None` cells number exactly 6 (F2), plus header rows (classified in §5.4).
2. **Bands.** Take the **most common x-edge signature** among the candidates, with edges rounded to 2 pt. Its 6 intervals `[x_i, x_{i+1})` are the bands.
   - If the table has no candidate row, inherit the bands of the previous table in the same section when its outer edges match within 6 pt.
   - Otherwise every row of the table becomes an `UNMAPPED` anomaly.
3. **Assignment.** A cell goes to the band containing its **x-centre**. Several cells in one band are concatenated left to right with a single space.
4. **Overflow.** A cell whose centre lies outside every band, or a band receiving a cell wider than 1.5× the band, raises `BAND_OVERFLOW`, unless the cell is a full-width single cell (a heading).

Complexity: O(cells) per table, with a sort per row. The whole build is I/O and pdfminer-bound (prediction P3).

### 5.4 Row classification (`classify.py`)

Rules are applied in this order. The first match wins.

| Kind | Rule |
|---|---|
| `BLANK` | No non-empty text in any cell |
| `HEADER` | The joined text matches `/waiting|dosage|common name|a\.?\s?i\.?|formulation|dilution/i` and contains no digit outside a header word |
| `SECTION` | A single full-width cell matching a known section title (`Agricultural Use`, `Combination Product`, `Fungicides single product…`, `Fungicides Combination Uses`, `PUBLIC HEALTH USE`, `HOUSEHOLD`) |
| `NOTE` | A single cell starting with `➢`, `Note`, `*`, or `For non-agricultural use` |
| `PRODUCT` | A single full-width cell that matches the **heading grammar** (§6.1) |
| `DATA` | At least one value band (`DOSE_AI`, `DOSE_FORM`, `DILUTION`, `WAIT`) is non-empty, or is `None` with an anchor (an inherited merge) |
| `CONTINUATION` | Only `CROP` and/or `PEST` text, no value bands, and the previous emitted row (possibly on the previous page) was `DATA` |
| `UNMAPPED` | Anything else. It becomes an anomaly. |

Section titles are also matched in the page's free text above the table: some section titles are paragraphs, not table rows.

### 5.5 Assembly state machine (`assemble.py`)

State: `section`, `product`, `last_data_row`, `crop_anchor` (the field and bbox of the last crop cell).

| Event | Precondition | Action |
|---|---|---|
| `SECTION(s)` | — | `section = s`; `product = None`; `crop_anchor = None` |
| `PRODUCT(h)` | `section` is in scope | `product = h`; `crop_anchor = None` |
| `DATA(r)` | `product` is set | Emit a `UseRow`. Fill `None` cells from their merge anchor. A `CROP` that is `None` or empty takes `crop_anchor` when the anchor's bbox vertically contains `r` **or** `r` directly continues a merged crop across a page break. Update `crop_anchor` and `last_data_row`. |
| `DATA(r)` | `product` is not set | Anomaly `ORPHAN_ROW` |
| `CONTINUATION(r)` | `last_data_row` is set | Append the text to the previous row's `CROP` / `PEST` fields (cross-page merge) and record both provenances |
| `NOTE(n)` | `product` is set | Attach the note to the product |
| `HEADER`, `BLANK` | — | Ignore (headers re-derive nothing; bands are per table) |
| Out-of-scope section | — | Skip rows until the next in-scope `SECTION` |

**Merge anchor rule (F4):** a `None` cell in row *r*, band *c*, takes the value of the cell in band *c* whose bbox satisfies `top ≤ r.top` and `bottom ≥ r.bottom` (± 1 pt). If there is none, raise anomaly `DANGLING_MERGE`.

### 5.6 Determinism

- No sets are iterated without sorting.
- Rows are ordered by `(doc, page, table, row)`.
- Floats are rounded to 2 dp in the provenance.
- The canonical dump is JSON with sorted keys, `ensure_ascii=False` and `\n` line endings. Its SHA-256 is the `build_hash`.

## 6. Normalisation

### 6.1 Product heading grammar (`headings.py`)

```text
heading      := ingredient ( "+" ingredient )* formulation? note*
ingredient   := name conc?
name         := letters/digits/-/,/' sequence (e.g. "Beta-cyfluthrin", "Lambda-cyhalothrin")
conc         := number ( "%" | "% w/w" | "% w/v" | "% W/W" | "% W/V" )
formulation  := CIPAC code from an allow-list (EC SC WG WP GR SL CS OD FS DP WDG ZC SE EW DC SP ME SG WS GB CG DS EC/…)
note         := "(" text ")"          # e.g. "(Import only)", "(Cyclaniliprole 10.0% W/V DC)"
number       := digits ( "." digits )?   # tolerates the stray space observed in "22. 0%"
```

Output: `Product(ingredients=((name_norm, conc_value, conc_basis),…), formulation, notes, raw)`. The name is normalised by case-folding, collapsing hyphens and spaces, and an ingredient alias table (e.g. "Aluminum" = "Aluminium").

A heading that the grammar cannot parse raises anomaly `HEADING_UNPARSED`. The product is still kept, with `parse_status = unparsed`, so its rows are not lost.

### 6.2 Quantity grammar (`quantities.py`)

```text
quantity := na | term ( "+" term )*  ( ("to" | "-" | "–") term ( "+" term )* )?
term     := number unit?  | number "%" | number "/" "L"
na       := "NA" | "N.A." | "-" | "–" | "Nil" | ""
unit     := g | gm | kg | ml | L | Ltr | litre | days | hrs ...
```

Output: `Quantity(kind ∈ {value, range, sum, sum_range, percent, per_litre, na, text}, lo, hi, unit, parts)` and `parse_status`.

**Safety invariant (tested as a property):** every digit sequence in the parsed output appears in the raw text. The parser never computes or invents a number.

### 6.3 Lexicon (`lexicon.py`; ADR-006)

Files: `data/lexicon/crops.csv` and `pests.csv`, with columns `canonical_id, display_en, alias, lang, category, reviewed_by`.

- **Crop category** is one of `crop`, `storage`, `structure`, `non_crop`.
- **Key normalisation:** NFC → casefold → strip punctuation `` ` `` and `'` → collapse whitespace → "&" becomes "and".
- **Bootstrapping:** the first lexicon is generated from the distinct register strings (about 140 crops) as a draft. A human then reviews it, and only reviewed rows count. Rows with an empty `reviewed_by` field fail the build.
- **Pest text:** it is split on `,`, `;`, ` and `, ` & `. A parenthesised scientific name (e.g. "(Tetranychus urticae)") is kept as `scientific_name`. Application notes ("Foliar Application", "Seed Treatment", "soil drench") are extracted into `application_note`.

## 7. Register schema (`register/schema.sql`)

```sql
PRAGMA user_version = 1;
CREATE TABLE build_info      (key TEXT PRIMARY KEY, value TEXT NOT NULL);           -- build_hash, code_version, lexicon_hash, built_at (excluded from dump)
CREATE TABLE source_document (id TEXT PRIMARY KEY, kind TEXT NOT NULL, url TEXT NOT NULL,
                              sha256 TEXT NOT NULL, register_date TEXT NOT NULL, pages INTEGER NOT NULL);
CREATE TABLE ingredient      (id INTEGER PRIMARY KEY, name_norm TEXT UNIQUE NOT NULL, display TEXT NOT NULL);
CREATE TABLE product         (id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES source_document,
                              heading_raw TEXT NOT NULL, formulation TEXT, parse_status TEXT NOT NULL,
                              notes TEXT, page INTEGER NOT NULL, bbox TEXT NOT NULL);
CREATE TABLE product_ingredient (product_id INTEGER REFERENCES product, ingredient_id INTEGER REFERENCES ingredient,
                              conc_value REAL, conc_basis TEXT, position INTEGER NOT NULL,
                              PRIMARY KEY (product_id, position));
CREATE TABLE crop            (id TEXT PRIMARY KEY, display_en TEXT NOT NULL, category TEXT NOT NULL);
CREATE TABLE crop_alias      (alias_norm TEXT NOT NULL, lang TEXT NOT NULL, crop_id TEXT NOT NULL REFERENCES crop,
                              PRIMARY KEY (alias_norm, crop_id));
CREATE TABLE pest            (id TEXT PRIMARY KEY, display_en TEXT NOT NULL, scientific_name TEXT);
CREATE TABLE pest_alias      (alias_norm TEXT NOT NULL, lang TEXT NOT NULL, pest_id TEXT NOT NULL REFERENCES pest,
                              PRIMARY KEY (alias_norm, pest_id));
CREATE TABLE use_record      (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES product,
                              crop_id TEXT NOT NULL REFERENCES crop,
                              crop_raw TEXT NOT NULL, pest_raw TEXT NOT NULL, application_note TEXT,
                              dose_ai_raw TEXT NOT NULL, dose_form_raw TEXT NOT NULL,
                              dilution_raw TEXT NOT NULL, wait_raw TEXT NOT NULL,
                              dose_ai_json TEXT, dose_form_json TEXT, dilution_json TEXT, wait_json TEXT,
                              page_first INTEGER NOT NULL, page_last INTEGER NOT NULL, provenance_json TEXT NOT NULL);
CREATE TABLE use_record_pest (use_record_id INTEGER REFERENCES use_record, pest_id TEXT REFERENCES pest,
                              PRIMARY KEY (use_record_id, pest_id));
CREATE TABLE restriction     (ingredient_id INTEGER REFERENCES ingredient, status TEXT NOT NULL,   -- banned | refused | restricted
                              detail_raw TEXT NOT NULL, page INTEGER NOT NULL);
CREATE INDEX use_by_crop    ON use_record(crop_id);
CREATE INDEX use_by_product ON use_record(product_id);
```

IDs are assigned in canonical order, so the same inputs always produce the same IDs.

## 8. Validation (`validate.py`)

| Invariant | On failure |
|---|---|
| I1. Every source hash matches the manifest | abort |
| I2. Every `use_record` has a product, a crop ID and a non-empty `pest_raw` | anomaly `INCOMPLETE_ROW` |
| I3. **Provenance re-check:** re-extracting the text inside each stored bbox reproduces the stored raw text | abort (a bug, not data) |
| I4. Every register crop and pest string resolves through reviewed lexicon rows | anomaly `UNKNOWN_CROP` / `UNKNOWN_PEST` |
| I5. The observed section page ranges equal the manifest's `expected_sections` | anomaly `SECTION_DRIFT` (warns of a new edition layout) |
| I6. No two `use_record`s are identical in (product, crop, pest_raw, all values) | anomaly `DUPLICATE_ROW` (kept once) |
| I7. Every quantity parse keeps the digit invariant (§6.2) | abort |
| I8. **Anomaly budget:** anomalies not on `data/anomaly_allowlist.toml` (each entry has a reason and a reviewer) must be ≤ 0 for a release build | abort the release build; dev builds warn |

## 9. CLI and errors

```text
python -m labelclaim.build fetch   --sources data/sources.toml [--offline]
python -m labelclaim.build run     --sources data/sources.toml --lexicon data/lexicon --out build/ [--release]
python -m labelclaim.build audit   --register build/register.sqlite      # stats + anomaly summary
python -m labelclaim.build lexicon-draft --out data/lexicon/draft/       # bootstrap aliases for review
```

**Exit codes:** 0 OK, 2 usage, 3 integrity (hash or provenance), 4 anomaly budget exceeded.

**Exceptions:** `SourceIntegrityError`, `ProvenanceError`, `AnomalyBudgetExceeded`, all subclasses of `LabelClaimError`.

## 10. Tests (written before the implementation)

| Group | Tests | Data |
|---|---|---|
| `sources` | hash mismatch leaves no file; cache hit makes no network call (the fetcher is injected); `--offline` miss fails; atomic rename | local HTTP server fixture |
| `geometry` | bands from the modal 6-cell signature; x-centre assignment; concatenation order; overflow anomaly; inheriting bands from the previous table | synthetic `RawTable`s |
| `classify` | one case per `RowKind`, including the tricky ones: a heading containing digits ("Abamectin 01.90 % EC") is `PRODUCT`, not `DATA`; a header with "a.i (gm)" | synthetic rows |
| `assemble` | page-break continuation; merged crop across 3 rows (the p. 20 Maize case); a merged WAIT/DILUTION inherited; an orphan row; an out-of-scope section skipped; a note attached | synthetic, then **golden pages** |
| `headings` | 30 real headings from both documents (including "Buprofezin 22. 0% + …", "Cyclaniliprole 9.3% W/W DC (…)", "(Import only)") → expected structure; unparsable → `unparsed` | table-driven |
| `quantities` | table-driven over observed formats; **hypothesis** properties: never raises, the digit invariant, `na` tokens | generated |
| `lexicon` | normalisation key; unreviewed row fails; unknown string → anomaly | small CSVs |
| `validate` | each invariant fires on a planted defect | fixtures |
| `register` | schema applied; **two builds → identical canonical dump hash**; read-only open rejects writes | temp dirs |
| **golden pages** (`-m corpus`) | Insecticide p. 2, 20, 53/54 (section boundary), 60 (combination, 10 cells), 84/85 (page-break continuation); fungicide p. 2, 44/45, 84 (seed-treatment free text). Expected `UseRow`s are written by hand from the rendered page images. | the real PDFs (by hash) |

Corpus tests need the PDFs in the cache and are opt-in (`-m corpus`), as in Porter's. CI fetches them by hash.

## 11. Predictions (written before any M1 code)

| ID | Prediction | How it is checked |
|---|---|---|
| P1 | ≥ 97 % of in-scope DATA rows map to 6 bands without an anomaly | `audit` stats |
| P2 | The total of distinct anomalies before any allow-listing is between 20 and 120 | `anomalies.json` |
| P3 | A full build from cached PDFs takes < 60 s on `ENV-NATIVE-1` (5 runs; median reported) | timing log |
| P4 | 142 raw crop strings → 95 to 120 canonical crops after review | lexicon stats |
| P5 | ≥ 95 % of product headings parse fully | `audit` stats |
| P6 | Golden-set field accuracy (E1) ≥ 99 % on the first full run | evaluation E1 |

## 12. Mutation checks (each predicted before running)

| Mutant | Expected killer |
|---|---|
| Assign a cell by its left edge instead of its centre | a `geometry` test with an overlapping wide cell |
| Treat a `None` cell like `""` (no merge inheritance) | the `assemble` p. 20 Maize test |
| Reset `product` at a page break | the golden p. 84/85 test |
| Drop the digit check in `quantities` | the hypothesis digit-invariant property |
| Skip the provenance re-check (I3) | the `validate` planted-defect test |
| Iterate a `set` when assigning IDs | the two-builds-identical test (PYTHONHASHSEED varied) |

## 13. Interview angle

See `docs/interview_notes/m0_design.md`.

The short version: *"Tables in government PDFs are a geometry problem, not a text problem. I mapped cells to columns by position per table, treated merged cells explicitly, and made every value traceable to a box on a page. Anything the rules couldn't handle became a reviewed anomaly instead of a guess."*

## 14. Implementation notes: where the real data changed the design (2026-11-13)

Each change was forced by a page of the real register and is covered by a test from that page. These are deviations from §5–§6 above, recorded instead of silently edited.

| # | Change | Forced by | Test |
|---|---|---|---|
| D1 | Bands are derived per **block** (rows between full-width headings), with fallbacks in this order: the block's 6-cell signature → the table's → the previous bands if every cell edge aligns → a 5-cell signature (≥ 2 rows) | Insecticide p. 8: two products in one table with different widths. Insecticide p. 7: a 3-column layout must *not* inherit. Insecticide p. 51: a genuine 5-column seed-treatment layout | `test_each_product_block…`; golden p. 8, p. 51 |
| D2 | A cell covering ≥ 50 % of two or more bands belongs to the **leftmost**. The other bands get `source="spanned"`, empty text and `span_of` | Fungicide p. 20: "2.0" across formulation and dilution | `test_spanned_value_…`; golden p. 20 |
| D3 | Empty cells narrower than 8 pt ("slivers") are ignored when building signatures | Fungicide p. 77 | mutant M9 |
| D4 | A 5-column layout gives a zero-width WAIT band; those fields are `source="absent"` | Insecticide p. 51 | golden p. 51 |
| D5 | Tables nested inside another table's box are dropped (their characters belong to the enclosing cell) | Fungicide p. 68 | the anomaly list (golden) |
| D6 | Text lines outside tables are rebuilt from their **words** as one virtual row, in the current bands. At the top of a page they continue the last row. Lines after a `*` footnote marker are notes | Fungicide p. 15/16; insecticide p. 67–69 | golden p. 15/16, p. 67/68 |
| D7 | Continuation rules: <br>• at the top of a table: crop `""` or no value text, **unless** ≥ 2 value cells hold fresh numbers; <br>• mid-table: no crop text, and the value texts finish an *unfinished* value (trailing `– + ( , and or to`, or an open bracket), or start with `(` or lower case; <br>• pest-only rows; <br>• a pest one grid row below an empty pest cell | Fungicide p. 8, 38/39, 54, 76, 81 | golden p. 38/39, 54, 76; synthetic tests |
| D8 | A crop cell left blank in a data row means "same as above" (`source="blank"`). Its pest is shared too when that pest was split by the page break | Fungicide p. 38/39 (the drone row) | golden p. 38/39 |
| D9 | Covered cells at the top of a table, and for the rest of that table, are carried from the previous page. A merge anchor that is itself a continuation row yields the **completed** value of the use it was appended to | Insecticide p. 15, p. 25; fungicide p. 75 | `test_merged_cell_started_on_previous_page…` |
| D10 | Full-width cells that read like notes (a leading symbol, a colon, a sentence verb) are notes, not products | 7 such cells had become products with 0 rows | mutant M10 (survived; see §15) |
| D11 | **Pests:** split into keys (`split_pests`); a reviewed pest lexicon is deferred to M2. **Crops:** a draft lexicon of 197 strings is generated with `reviewed_by` empty. Release builds refuse until a human reviews it | Scope and review effort | `test_lexicon_…`; release gate |
| D12 | Types live in `extract/model.py` rather than `geometry.py` | Several modules share them | — |
| D13 | **Process deviation.** The `sources` and `normalize` tests were written before their code. For `extract`, the code was written first and the tests straight after, from the §10 list. The real-data rules D1–D10 each got their test right after the audit found the page | Honesty record | — |

## 15. Results (2026-11-13)

**Environment:** `ENV-NATIVE-1`
- Linux 7.0.0-43, Intel Core i3-1220P
- Python 3.12.16, pdfplumber 0.11.10
- `uv.lock` sha256 prefix `b379cd3f`

### 15.1 Tests (all run, not just written)

| Suite | Result |
|---|---|
| Unit + property (hypothesis) + synthetic | **104 passed** |
| Golden pages from the real PDFs (`-m corpus`) | **11 passed**: 22 rows typed from page images, on insecticide p. 8, 20, 51, 60, 67/68 and fungicide p. 15/16, 20, 38/39, 54, 76, plus the exact anomaly set |
| ruff, ruff format, mypy --strict | clean |
| Branch coverage, unit tests only | 73 % overall |
| Branch coverage, unit + corpus | `extract` 82–100 %, `normalize` 78–100 %, `build.py` 0 % (exercised by the 5 builds below, but not under coverage). **NFR-6 (≥ 90 %) is not met** for `normalize/lexicon.py` (78 %), `extract/pages.py` (82 %) or `build.py` |

### 15.2 Build: 5 runs from the cache, each with a different `PYTHONHASHSEED`

| Measure | Value |
|---|---|
| Use rows | **2,376** (insecticide 1,252; fungicide 1,124 after duplicate and merge handling) |
| Products | 655 (641 headings fully parsed = 97.9 %) |
| Ingredients | 230 |
| Restriction entries | 97: banned 50, banned for use 5, withdrawn 8, refused 18, restricted 16. These counts match the document's own numbering |
| Provenance re-check (I3) | **14,123 fields** re-read from their boxes: **0 mismatches** (a mismatch aborts the build). *Corrected 2026-11-13: first reported as 14,130, which came from an earlier build before fixes D9 and the fungicide p. 81 merge.* |
| Anomalies | 10, all on the allow-list: 8 `UNMAPPED_TABLE` (p. 7 non-crop layout), 2 `DANGLING_MERGE` (fungicide p. 77). The allow-list itself awaits a human `reviewed_by` |
| Build hash | `86953251…` **identical in all 5 runs** (seeds 7919 … 39595) |
| Wall time | median **40.82 s** (38.85, 39.16, 40.82, 41.20, 41.62) |
| Crop source of the use rows | cell 2,124 · merged 237 · carried 9 · blank 6 |

Raw: `reports/M1/build_runs.csv`, `build/run*/build_manifest.json`, `build/run*/anomalies.json`.

### 15.3 Predictions (§11) against the results

| ID | Prediction | Result | Held? |
|---|---|---|---|
| P1 | ≥ 97 % of data rows map without an anomaly | As designed in §5 (per-table bands): **no**. The first audit had 140+ merge/overflow anomalies in the insecticide register alone. After D1–D10: 10 anomalies, 2 of which touch data rows (99.9 % of rows clean) | **wrong for the original design**, met after the deviations |
| P2 | 20–120 anomalies before allow-listing | **206** on the first audit (162 + 44) | **wrong** (too low) |
| P3 | Build < 60 s | median 40.8 s | held |
| P4 | 142 crop strings → 95–120 canonical | 197 distinct crop strings across *both* registers (142 was the insecticide spike only). The canonical count is **NOT MEASURED**: it needs the human review | not yet testable |
| P5 | ≥ 95 % of headings parse fully | first measurement **94.3 %** (miss); after adding formulation codes and the note rule (D10): **97.9 %** | **wrong at first**, met after the fix |
| P6 | E1 field accuracy ≥ 99 % | **NOT MEASURED**: the 120-row stratified golden set is not built. The 22 golden rows: on their first run, 1 extractor bug (the 5-column misfire on fungicide p. 20, fixed) and 2 labels of mine were wrong (corrected with character-level evidence; see `test_golden_pages.py`) | not yet testable |

### 15.4 Mutation checks (`tools/mutants.py`; predictions written in the script before running)

| Run | Killed | Survived | Notes |
|---|---|---|---|
| First | 6 | 2 (M1, M10), both **as predicted** | M3 was not applied (pattern not unique); fixed |
| After adding 2 gap tests | **9 of 9** | 0 | `test_cell_starting_slightly_left…`, `test_note_like_full_width_cells…` |

M6 (iterating a set when assigning IDs) is covered by the 5-seed determinism check, not by a unit test.

### 15.5 Not done in M1

- The E1 stratified golden set (120 rows), and the user's independent re-labelling of 30 rows.
- E2 reconciliation against an independent count.
- **Human review** of `data/lexicon/crops.csv` (197 rows) and of the 2 allow-list entries. Until then `--release` refuses, by design.
- A pest lexicon (D11; moved to M2).
- CI actions pinned to SHAs; no push has been made.

### 15.6 Release build after the user's review (2026-11-13)

**The user's review.** The user signed every row of `data/lexicon/crops.csv` and both allow-list entries (`reviewed_by = "Tarun"`):
- The review changed 23 canonical IDs (152 → **134** canonical crops). Examples: plurals merged; Jowar → sorghum; Bajra and Pearlmillet → pearl_millet; Corn → maize; Moong → greengram; the "Ccumber" typo → cucumber.
- The reviewed file arrived as `crops_reviewed.csv` with Windows line endings. The assistant copied it over `crops.csv` and normalised the line endings to LF; the content is unchanged.

**P4** predicted 95–120 canonical crops; the result is 134. **Wrong** (too low).

**The release build.**
- Command: `python -m labelclaim.build run --release --offline`, exit 0.
- Build hash `672590d0…`.
- 2,376 uses, all with a crop ID; 14,123 fields re-checked.
- 10 anomalies, all reviewed; 0 unreviewed lexicon rows or allow-list entries.
- 35.9 s.

**Inputs for M2.** These are observations; the assistant did not change any of the user's choices.
- **Crops and application methods mixed together.** Some register strings name several crops, or a crop plus a method, and were reviewed as one ID: "Tomato/Chilli es" → `tomato_chilli`, "Beans (Cowpea, moong, Urd)" → `cowpea_moong_urid`, "Grapes (Soil drench)" → `grapes_soil_drench`, "Tobacco (Nursery)" → `tobacco_nursery`. A lookup for "tomato" or "grape" would therefore miss those uses. M2 needs either a many-to-many use ↔ crop mapping or a split of the method into `application_note`.
- **A leftover empty alias.** `unknown` (alias "") came from an empty crop string in an early build. No current use has an empty crop, so the row is unused.
