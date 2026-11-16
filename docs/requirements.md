# Requirements: Pesticide label-claim check

Version 0.1 (2026-11-13), for review. Status of everything here: **planned**.

## 1. Purpose

At an agri-input shop, a farmer asks: *"Can I spray this on my tomato for fruit borer? How much, and when can I harvest?"*

The legal answer is in the government register *Major Uses of Pesticides* (CIB&RC, PPQS). That register is a 200-page English PDF that almost nobody at the counter reads. Off-label use is widespread, and unapproved uses have even been recommended by official bodies (PAN India field study; CropLife India).

This application answers that one question **from the register only**, cites the exact page and row, and says plainly when there is **no** approved use.

## 2. Users

| Persona | Context | What they need |
|---|---|---|
| **Dealer** (primary) | Licensed agri-input shop; phone; busy counter; English or Kannada | A fast, citable yes / no / dose / waiting period, to tell the farmer |
| **Farmer** | At the shop or at home; Kannada; may not read English | The same answer, in Kannada, by voice (M5) |
| **Extension worker** (KVK, agriculture department) | Advising many farmers | Correct answers, plus the full list of approved options for a crop–pest pair |

## 3. User stories and acceptance criteria

| ID | Story | Acceptance criteria |
|---|---|---|
| US-1 | As a dealer, I enter a product, a crop and (optionally) a pest, and see whether that use is approved | The outcome is one of the closed set in §4 FR-5. Every approved row shows dose (a.i. and formulation), dilution, waiting period, the **official text as printed**, the document, the page, and the register date. |
| US-2 | As a dealer, when a use is **not** approved, I see that clearly, and what the register **does** approve for that crop and pest | The answer never states or implies approval. It lists approved products for the crop–pest pair, or says "none in the register". |
| US-3 | As a dealer, I type names the way people say them ("chilli", "mirchi", "bhindi", brand-like text) | The system resolves names through a reviewed alias list. A fuzzy match is offered as "did you mean …?" and is **never applied silently**. |
| US-4 | As anyone, I am warned when an ingredient is banned or restricted | The banned/restricted list (dated 31.10.2026) overrides the answer with a visible warning. |
| US-5 | As anyone, I know how current the answer is | Every answer carries the register's "as on" date and the build's source hashes. |
| US-6 | As a farmer, I ask by voice in Kannada and hear the answer in Kannada (M5) | Defined in the M5 LLD. Not part of the first release. |

## 4. Functional requirements

| ID | Requirement | Milestone |
|---|---|---|
| FR-1 | Fetch the official register PDFs listed in a **source manifest** and verify each one's SHA-256 before use. A hash mismatch stops the build. | M1 |
| FR-2 | Extract every **agricultural-use** row of the insecticide and fungicide registers (single products and combinations) into structured records. Each record carries **provenance**: file hash, page, cell bounding boxes and the raw cell text. | M1 |
| FR-3 | Parse product headings into active ingredient(s), concentration(s) and formulation code. Parse doses, dilution and waiting period into structured quantities **where the text allows**. Always keep the raw text. | M1 |
| FR-4 | Normalise crop and pest names to canonical IDs through a versioned, reviewed lexicon. Unknown names are reported, never guessed. | M1 |
| FR-5 | A lookup returns exactly one outcome: `APPROVED`, `NOT_APPROVED_FOR_CROP`, `NOT_APPROVED_FOR_PEST`, `UNKNOWN_PRODUCT`, `UNKNOWN_CROP` or `AMBIGUOUS`. A `BANNED_OR_RESTRICTED` flag can be added to any of them. | M2 |
| FR-6 | An HTTP API (versioned, OpenAPI-documented) exposes lookup, name search and register metadata. | M2 |
| FR-7 | When a language model is used (M3+), **no number reaches the user unless it appears in the cited register row**. A verifier enforces this; violations are blocked and logged. *Amended 2026-11-17 (L3 §5): the numbers in the product name the user typed are also allowed, once the register recognises that product; never a dose, dilution, waiting period or conversion.* | M3 |
| FR-8 | Evaluation on real farmer questions (Kisan Call Centre transcripts) | M4 |
| FR-9 | Kannada text and voice input and output | M5 |
| FR-10 | Phone-friendly web app | M6 |

## 5. Non-functional requirements

| ID | Quality | Requirement (target fixed before measurement) |
|---|---|---|
| NFR-1 | Correctness | Extraction field accuracy ≥ 99 % on the golden set (§ evaluation plan E1). Zero numbers in answers that are not in the cited row. |
| NFR-2 | Reproducibility | The same sources, code and lexicon give a byte-identical canonical dump of the register. Every build records its input hashes. |
| NFR-3 | Latency | Lookup p95 ≤ 20 ms in-process and ≤ 100 ms over HTTP on this machine (M2, measured). Voice targets are set in M5. |
| NFR-4 | Safety | Raw official text is always shown next to parsed values. There is no "recommendation" wording. A disclaimer is on every answer (§7). |
| NFR-5 | Privacy | No personal data is stored by default. Audio is not retained (M5). Pilot logging happens only with consent. |
| NFR-6 | Maintainability | Typed Python (mypy strict on `src/`), lint-clean (ruff), tests before code, CI on every push. Branch coverage ≥ 90 % on `extract`, `normalize` and `lookup`. |
| NFR-7 | Supply chain | Dependencies are locked with hashes (uv) and restricted to releases at least 14 days old (`exclude-newer`). |
| NFR-8 | Cost | ₹0 by default. Any paid API needs the user's explicit permission. |
| NFR-9 | Updatability | A new register edition is ingested by updating the manifest and rerunning the build. The diff between editions is reported. |

## 6. Out of scope

- Pest or disease diagnosis (from text or photos).
- Recommending a product for a use that is not in the register.
- Shops, prices, brands' market availability.
- Fertilisers, bio-stimulants, and the non-agricultural sections (public health, household, locust).
- Legal advice.

## 7. Constraints and wording

- The register says of itself: *"compiled on the basis of available information for guidance and not for legal purposes."* Every answer must repeat this in substance, and say "follow the product label; ask your agriculture officer".
- "Approved use" means *a label claim registered under the Insecticides Act, 1968*. It is **not** a recommendation to spray.
- The register PDFs are public government documents. The repository stores their hashes and URLs, not the PDFs.

## 8. Traceability

| Requirement | Design | Tests / evidence |
|---|---|---|
| FR-1, FR-2, FR-3, FR-4, NFR-1, NFR-2 | `docs/lld/l1_register_extraction.md` | L1 §10 tests; evaluation E1 and E2 |
| FR-5, FR-6, NFR-3 | `docs/lld/l2_lookup_api.md` | L2 §8 tests; evaluation E3 |
| FR-7 to FR-10 | later LLDs (M3–M6) | evaluation E4 and E5 |
| NFR-4, NFR-5, NFR-7 | `docs/threat_model.md` | threat model checks |
