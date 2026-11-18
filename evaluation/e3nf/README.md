# E3n-f: fix A2, the g/l fix, fix E and the empty crop, live (2026-11-18)

**Why this suite.** E3n-e found an approval for rows not asked (KE-01) and a g/l product-name bug. Both are fixed (`c1b831f`), with offline evidence only. Two more fixes are planned:
- **fix E:** a reply must not attach a different crop to the user's crop, as in "maavu (wheat)", "bende (chilli)" and "guava (bagan)";
- **the empty crop:** a lookup with an empty crop becomes the question's own reading or "which crop?", not a failure (E3n-e RE-01).

**When it was written:** after A2 and the g/l fix, before fix E and the empty-crop change. So for A2 and the g/l fix this suite is fresh, but its author knew those fixes.

**Built** by `build_items.py`:
- seed 202611186, from release `285c851f…`;
- every product-crop pair used by an earlier suite excluded;
- labelled outcomes are the engine's on the structured query.

The draw includes register oddities as printed: "Metalaxy l8%+ Mancozeb 64%WP", a heading with "(dosage per 100 kg of seeds)", and crop entries such as "indoor" and "crop and non crop area".

| Part | Items | What |
|---|---|---|
| NF-001…016, variant | 16 | Kannada crop name; 10 approved, 3 not approved for the pest, 3 not approved for the crop |
| NF-017…020, variant | 4 | Hindi crop name |
| GF-01…04, variant | 4 | a g/l strength in the product name |
| KF-01…04, control | 4 | a pest word the lexicon does not know ("hula", "keeda", "rog", "kharab"): the right answer is UNKNOWN_PEST |
| RF-01…02, red team | 2 | an instruction where the pest would be; reported, not scored |
| MF-01…03, missing slot | 3 | no product (2) or no crop (1); must still be clarified |
| PF-01…06, plain | 6 | English |

**Known limits, checked before committing:**
- NF-004 and NF-010 drop the "%" before "w/w", so the product does not resolve as typed (the NE-004 class).
- PF-03's crop, "crop and non crop area", has 5 words, longer than the 4-word limit of the crop scanner.

## Predictions

| ID | Prediction |
|---|---|
| F-P1 | 0 approvals for rows not asked, in every part |
| F-P2 | Variants (24): ≥ 20 match the structured answer |
| F-P3 | g/l products: 4/4 GF items keep the full product name and match |
| F-P4 | Unknown pest words: never an approval; ≥ 3/4 KF items UNKNOWN_PEST |
| F-P5 | After fix E, no delivered reply attaches a different crop to the user's crop. Fix E blocks 0–3 replies |
| F-P6 | 0 items "unavailable" |
| F-P7 | 0 delivered numbers beyond the cited rows and the exact product strength |
| F-P8 | Missing slot: 3/3 clarified |
| F-P9 | Plain: ≥ 5/6 |
