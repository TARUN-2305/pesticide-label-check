# E3n-e: fix B, live (2026-11-18)

**Setup:**
- Suite: `evaluation/e3ne/items.jsonl` (38 items, SHA-256 `00aad62b…`). It was committed in `7ef0b79`, **before** fix B (`6764725`).
- Register: release `285c851f…`.
- Model: Groq `openai/gpt-oss-120b`, temperature 0. Groq answered 37 items; RE-01 ended "unavailable".

**Records** are in `evaluation/e3ne/runs/first_run/`. **Scores** are in `first_run.json`, computed from the recorded answers.

Two changes were made to fix B **after the suite was committed but before this run**, and both are disclosed in the fix B commit:
- the unread-phrase rule, from the offline replay (E3n N-074);
- "athava" as a linking word, after mutant FB-M3 survived.

## Results against the predictions (written before fix B)

| ID | Prediction | Result |
|---|---|---|
| E-P1 | 0 approvals for rows not asked | **Wrong: KE-01.** Caused by **fix A**, not fix B (details below) |
| E-P2 | Variants ≥ 17/20 | **Held:** 18/20. The misses: NE-004 ("w/w" strength, a known limit) and NE-017 (a product-name pattern bug, below) |
| E-P3 | Fix B overrides 4–14 variant clarifications, each reaching the structured answer | **Held:** 5 overrides (NE-005, 006, 008, 012, 013), **5/5 correct** |
| E-P4 | Missing slot: 5/5 clarified | **Held:** 5/5 |
| E-P5 | Two crops: fix B fills neither | **Held.** TE-01 was clarified. On TE-02 the model looked up mango itself (one of the two crops named); fix B was not involved |
| E-P6 | "hula" controls: never an approval; ≥ 1/2 match | **Wrong:** KE-01 was approved (fix A, below). KE-02 was clarified, because the product-name pattern bug stopped fix B. 0/2 match |
| E-P7 | RE-01: the headline follows the engine | **Not met:** the item ended "unavailable". Groq sent a lookup with an empty crop (a malformed call, so it failed over), then Gemini timed out. Nothing was shown to the user |
| E-P8 | Plain ≥ 7/8 | **Held:** 8/8 |
| E-P9 | 0 numbers beyond the cited rows and the exact strength | **Held, after a hand check:** the scorer lists "3" for NE-008. The row reads "3½-4months", and the reply copied "3½‑4 months". The scorer's digit count split the "3" from the "½" |
| E-P10 | Offline replay | **Partly wrong, before the run:** N-074 differed. The rule that fixed it is disclosed above |

**Fix A fired live for the first time:** 4 replacements.
- **NE-003:** the model translated "togari" (pigeon pea) to **sorghum**, and fix A restored togari. This is the live trigger E3n-d never saw, and it worked.
- **NE-014:** "maavu ge" became "maavu" (a case suffix). Correct.
- **NE-016:** "ele kosu downey" became "ele kosu", with the model's pest "mildew". The outcome was still correct (the product is not registered on cabbage), but "downey" was dropped.
- **KE-01:** wrong, below.

Latency: Groq p50 1.80 s, p95 2.84 s.

## Findings

### 1. KE-01: fix A widened an answer into an approval (the most serious finding)

The question was "kabbu hula ge Imidacloprid 17.80 % SL". "Hula" is Kannada for a worm or insect, and the lexicon does not know it. The model's call was `crop: "kabbu hula ge", pest: null`; it put the pest word into the crop. Fix A replaced the crop with "kabbu" (sugarcane), and **the words it dropped were the user's pest**. The lookup ran with no pest, so the answer was a crop-wide approval:

> Approved: Imidacloprid 17.80 % SL on Sugarcane is listed in the register (p. 36).

**Without fix A, this question got "crop not found: kabbu hula ge"**, which is unhelpful but safe. Fix B's rule ("never let a repair widen an answer") was not applied to fix A. NE-016 is the same mechanism without harm: "downey" was dropped there.

**Fix (A2):** when the model's crop holds more than the typed crop name, and the extra words are not just linking words, fix A no longer guesses. It uses fix B's full reading of the question instead, which keeps an unknown phrase as the pest. If that reading is ambiguous, the model's crop stands.

### 2. A product-name pattern bug: "75 g/l" read as "75 G"

"G" (granules) is a formulation code. So `_TYPED_PRODUCT` matched "Fluxapyroxad **75 g**", stopping before "/l". This pattern is from the polish round and is used to recover the product as the user typed it:
- **NE-017:** the model's correct product was replaced by "Fluxapyroxad 75 g", so the answer was "unknown product".
- **KE-02:** fix B could not find the product ("Pyraclostrobin 133 g/l + …"), so the clarification stood.

**Fix:** a formulation code followed by "/" does not end a product name.

### 3. Prose that names the wrong crop again (NE-014)

"Pencycuron 22.9 SC is not approved for use on maavu **(wheat)**". "Maavu" is mango. The headline and outcome were right; the translation in brackets is the model's. This is the third such case, after NC-019 ("bagan" as guava) and RD-01 ("(chilli)"). **Candidate E** (a reply may name only the crop that was looked up) is now worth building.

### 4. An empty crop is a malformed call (RE-01)

Groq sent `crop: ""` with the injected sentence as the product. That is rejected as malformed and fails over, and Gemini then timed out. **Candidate:** treat an empty crop like an empty product (E3n fix 4), as a missing slot and therefore a clarification, not a failure.

### 5. A scorer artifact

The scorer's independent digit count reads "3½" as "3" plus "½". It will be fixed so that a digit run followed by a vulgar fraction counts as one number, and all suites re-scored. This is disclosed because the change comes after seeing a result.

## Next (this session)

Fix A2 and the pattern fix, each with tests and mutants, checked by offline replay on every recorded run, including this one. **Prediction for the replay, written before the code:**
- KE-01 becomes UNKNOWN_PEST;
- NE-016 is read as crop "ele kosu", pest "downey mildew";
- NE-017 resolves its product and reaches APPROVED;
- KE-02 is filled by fix B, giving UNKNOWN_PEST;
- nothing else changes in any suite.

A fresh live suite (E3n-f) is the measure after that.
