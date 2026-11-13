# Evaluation plan

Version 0.1 (2026-11-13). Each target is fixed **before** the measurement. A miss is reported as a miss, with its cause; the target is never edited afterwards. Nothing here has been measured yet.

## E1: Extraction accuracy (M1)

| Item | Definition |
|---|---|
| Golden set | **120 use rows**, stratified: <br>• insecticide single (35), insecticide combination (25), fungicide single (35), fungicide combination (25) <br>• within each stratum, at least 5 merged-crop rows, at least 3 page-break rows, and at least 3 rows with free-text values <br>• rows sampled with a fixed seed from `use_record` IDs, plus the deliberately chosen hard pages listed in L1 §10 |
| Labelling | Each expected row is typed from the **rendered page image** (`pdftoppm -r 150`), not from the extractor's output. The labeller is disclosed as the assistant. **The user independently re-labels 30 of the 120.** Agreement is reported as field-level exact match, and disagreements are adjudicated against the page image. |
| Metric | Field-level exact match after whitespace collapse, over the 8 fields (product heading, crop, pest, 4 values, page). Row-level: all 8 match. |
| Target | Field accuracy ≥ 99 %. Row accuracy ≥ 97 %. Every miss is classified (band, merge, continuation, classification, parse). |
| Artifacts | `evaluation/golden/e1.jsonl` (with labeller and date), `reports/E1/results.json`, `reports/E1/report.md` |

## E2: Coverage and anomalies (M1)

| Metric | Target |
|---|---|
| In-scope DATA rows mapped without anomaly | ≥ 97 % (L1 P1) |
| Anomalies remaining after review | 0 not on the reviewed allow-list. Every allow-list entry has a reason. |
| Reconciliation | For each section, the rows extracted vs an independent count from `pdftotext -layout` plus a waiting-period-column heuristic. A difference > 2 % is investigated. |

## E3: Lookup correctness (M2)

| Item | Definition |
|---|---|
| Query suite | **150 queries** written from the register pages (not from the code), stratified by expected outcome: <br>• APPROVED 60 <br>• NOT_APPROVED_FOR_CROP 30 <br>• NOT_APPROVED_FOR_PEST 20 <br>• UNKNOWN_PRODUCT 10, UNKNOWN_CROP 10, AMBIGUOUS 10 <br>• restriction overlay 10 <br>Includes spelling variants and Indian-English names (bhindi, brinjal/eggplant, paddy/rice). |
| Metric | Outcome accuracy. For APPROVED: the set of returned `use_record` IDs equals the expected set (precision and recall reported). |
| Target | Outcome accuracy ≥ 98 %. Zero answers of APPROVED where the expected outcome is NOT_APPROVED (the safety-critical error, reported separately). |

## E4: Real farmer questions (M4; needs the data.gov.in key)

1. **Sample:** Kisan Call Centre transcripts from Karnataka (or nationwide if Karnataka is sparse), pesticide-related queries, a random sample of 200 with a fixed seed.
2. **Gold answers:** written from the register by a labeller (disclosed). The user re-labels 40.
3. **Metrics:**
   - slot extraction (product/ingredient, crop, pest)
   - outcome accuracy
   - **the unverified-number rate** (target 0)
   - clarification rate
4. **Side analysis:** how often the recorded KCC answer names a use the register does **not** approve. This is reported with care, as an observation about one dataset, not an accusation.

## E5: Speech (M5)

Defined in the M5 LLD:
- word error rate on about 150 recorded Kannada and English questions (speakers consent);
- end-to-end outcome accuracy;
- p50/p95 latency for Bhashini vs a self-hosted model.

## Reporting rules (from Porter's)

- Every result file records the environment (OS, CPU, Python, package lock hash), the command, the input hashes, the date and the raw per-item outputs.
- Small samples are labelled "pilot", with confidence intervals (bootstrap, 95 %) where a rate is reported.
- Predictions (L1 §11, L2 §9) are compared with results in a section titled "Predictions vs results", including the wrong ones.
