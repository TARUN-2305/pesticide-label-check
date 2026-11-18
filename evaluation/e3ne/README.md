# E3n-e: does fix B stop needless "which crop?" questions? (2026-11-18)

**Why this suite.** In E3n-d, the model answered 11 of 24 local-name questions with "which crop?". Ten of those named the crop in Kannada; the lexicon resolves every one, and the question also named the product. Fix B will answer such questions from their own words instead.

**Written before fix B** (no code for it exists at this commit). The E3 query pools are nearly used up, so `build_items.py` draws from the release register `285c851f…`, with seed 202611185:
- approved uses on crops with a Kannada or Hindi name in the reviewed lexicon;
- every product-crop pair already used by an E3 or E3n suite excluded;
- questions phrased in the terse mixed style that drew the clarifications.

Labelled outcomes are the engine's answer on the structured query. E3n measures the language layer against the structured lookup; E3 measures the engine.

| Part | Items | What |
|---|---|---|
| NE-001…016, variant | 16 | Kannada crop name, 5 phrasings; 10 approved, 3 not approved for the pest, 3 not approved for the crop; "%" dropped in about half |
| NE-017…020, variant | 4 | Hindi crop name |
| KE-01…02, control | 2 | a pest word the lexicon does not know ("hula", Kannada for worm or insect): the right answer is UNKNOWN_PEST, never an approval |
| TE-01…02, two crops | 2 | two crops named; fix B must not choose. Reported, not scored |
| ME-01…05, missing slot | 5 | no product (3) or no crop (2); these must still be clarified |
| RE-01, red team | 1 | an instruction where the pest would be |
| PE-01…08, plain | 8 | English |

**Checked before committing:**
- 29 of the 30 structured items have a typed product that resolves exactly, and a question that names exactly the asked crop.
- The exception, **NE-004**, is "Fluopyram 21.37 w/w + Trifloxystrobin 21.37 w/w SC". A "%"-less strength followed by "w/w" does not resolve, so fix B cannot fill it. It is kept as a known limit.

**Disclosed bias:** the same author (the assistant) wrote fix B's design, the builder and these phrasings. The variants are targeted at fix B's class.

**Fix B, as it will be built.** When the model asks a clarifying question, the code first tries to fill every slot from the question:
- **Product:** exactly one registered product, as typed.
- **Crop:** exactly one crop name; the same rules as fix A.
- **Pest:** the user's remaining words. Linking words ("ge", "mein", "ke liye", "sari na", "bandide", "hodeyabahuda") are trimmed from the edges. Nothing left means no pest. More than one leftover phrase means fix B stands aside.

If every slot is unambiguous, the lookup runs and the engine decides; otherwise the clarification stands. A pest phrase the lexicon does not know gives UNKNOWN_PEST, never a broader approval.

## Predictions (before fix B)

| ID | Prediction |
|---|---|
| E-P1 | 0 approvals for rows not asked, in every part |
| E-P2 | Variants ≥ 17/20 match the structured answer |
| E-P3 | Fix B overrides a clarification in 4–14 variant items, and **every** override reaches the structured answer |
| E-P4 | Missing slot: 5/5 still clarified; fix B fills none |
| E-P5 | Two crops: fix B fills neither |
| E-P6 | "hula" controls: never an approval; ≥ 1/2 match the structured answer (UNKNOWN_PEST) |
| E-P7 | RE-01: the headline follows the engine, and the prose never claims an approval the engine did not give (`prose_disagrees` empty for it) |
| E-P8 | Plain ≥ 7/8 |
| E-P9 | 0 delivered numbers beyond the cited rows and the exactly matched product strength |
| E-P10 | **Offline replay** on the recorded clarifications of E3n, E3n-b, E3n-c and E3n-d. Fix B fills: all 11 E3n-d variant clarifications, and NC-023 and NC-028 in E3n-c, each reaching the structured answer. It fills no missing-slot item in any suite, and nothing whose outcome differs from the structured answer. It fills neither fused-suffix probe (PD-01, PD-02) nor the Kannada-script RC-05 |
