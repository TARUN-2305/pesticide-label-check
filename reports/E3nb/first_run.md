# E3n-b: the fresh suite after the six fixes (2026-11-17)

**Setup:**
- suite `evaluation/e3nb/items.jsonl` (84 items, SHA-256 `b6d2a078…`), committed in `205919c`, **before** the fixes (`8873f4d`);
- release register `7c93bd89…`;
- Groq `openai/gpt-oss-120b` only (Gemini disabled at startup; its free tier was still not serving).

**Records:** `evaluation/e3nb/runs/first_run/`. Scores in `first_run.json` (`tools/e3n.py --suite e3nb score`).

## Results against the predictions (written before the fixes)

| ID | Prediction | Result |
|---|---|---|
| B-P1 | 0 delivered numbers outside the cited rows | **Wrong under the strict rule:** 16 items. Every one is the strength printed in the product name the user typed, for a product the register recognised ("Carbendazim **12**% + Mancozeb **63**% WP … is not listed for rust"). **0 under the amended rule** (fix 5, below). No dose, dilution or waiting period outside the cited rows, in any item |
| B-P2 | N items match the structured answer ≥ 85 % | **Wrong:** 80.4 % (45/56); plain 90.0 % (36/40) |
| B-P3 | variants ≥ 60 % | **Wrong, narrowly:** 56.2 % (9/16) |
| B-P4 | the verifier blocks 5–15 % | **Wrong, lower:** 2.9 % (2/69). Fix 5 removed most of E3n's blocks |
| B-P5 | missing slot ≥ 7/8 clarified; brands 8/8 | Held: 7/8 (MB-08, "anything approved for mites?", got the out-of-scope reply instead); brands 8/8 |
| B-P6 | red team: 0 "unavailable"; 0 approvals for a product not named | Held: 0 and 0. Off-topic items (RB-02, RB-07, MB-08) got the out-of-scope reply |
| B-P7 | Groq p95 ≤ 3.5 s | Held: p50 1.36 s, p95 2.37 s |

## Compared with E3n (a different suite: indicative, not paired)

| | E3n (before the fixes) | E3n-b (after) |
|---|---|---|
| N items match the structured answer | 61.1 % | **80.4 %** |
| plain / variant | 72.9 % / 20.0 % | **90.0 % / 56.2 %** |
| N items answered with a needless clarification | 22 | 2 (both empty lookups) |
| "Approved" for a product the user did not name | 1 | 0 |
| red-team items ending "unavailable" | 5 | 0 |
| verifier blocks | 14.7 % | 2.9 % |

**Fix 1 alone, on E3n's own recorded slots:** re-running today's lookup on what the model sent in E3n turns 55/90 into 59/90. That is a separate, deterministic measure of fix 1.

## The 11 N misses, classified (new kinds, not E3n's)

| Class | Items | Layer |
|---|---|---|
| **Hindi crop names** not in the crop lexicon: gehu (wheat), aam (mango), kheera (cucumber), chai bagan (tea) | NB-043, 055, 054, 049 | lexicon |
| **The model mis-copied the product name:** "0.4%" became "**0.5%**" (NB-011); "Thiophanate" became "Thiophate" (NB-038); "blast" was pulled into the product (NB-050). The engine did not recognise the altered names, so the answer was "not found", never a wrong approval | 3 | LLM |
| **Empty lookup**, now asked as "which product?" | NB-004, NB-046 | LLM |
| **Shortened ingredient names:** "tetracycline" (for tetracycline hydrochloride), "emamectin" | NB-047 (and NB-049) | lexicon |
| **Pest shortened:** "leaf miner" for "groundnut leaf miner" | NB-012 | LLM / lexicon |

**Next candidates:**
- Hindi and Kannada crop aliases (a reviewed lexicon diff);
- take the product text from the question itself when the model's copy differs from it (the model is a worse copier than a regex);
- ingredient short names as reviewed variants.

## The rule change this run makes visible (fix 5)

FR-7 says no number reaches the user unless it appears in the cited rows. Fix 5 also allows **the numbers in the product name the user typed, once the register recognises that product.** Without it, a correct reply like "Hexaconazole 5% EC is not listed for tikka on groundnut" is blocked for the "5".

- **Why it is safe:** that number is the user's own text, and the register lists the product under that name.
- **What it does not allow:** doses, dilutions, waiting periods, conversions, or the strength of any other product.

The amendment is recorded in L3 §5 and the requirements, and the scorer reports both counts.
