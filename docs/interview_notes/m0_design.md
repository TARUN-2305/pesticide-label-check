# Interview note: M0 design

Read this after the LLDs. Each answer is something you should be able to say in your own words, and defend.

## The 30-second pitch

> "At a pesticide shop, farmers ask whether a product is approved for their crop, at what dose, and how long to wait before harvest. The legal answer is in a 200-page government PDF that nobody reads at the counter. I turned that register into a checked, versioned dataset and built a lookup that answers from it only, with the page and row cited. When there's no approved use, it says so and shows what *is* approved. Language models only interpret the question and phrase the answer; a verifier blocks any number that isn't in the cited row."

## Questions you should expect, and the core of each answer

| Question | Core of the answer | Where it is decided |
|---|---|---|
| Why not just RAG over the PDF? | A dose is a fact, not a summary. In Porter's I measured that 57.5 % of claims grounded in verbatim quotes still weren't fully supported, so grounding doesn't guarantee truth. Here the facts come from a deterministic lookup, and the model can't add numbers. | ADR-003 |
| Why SQLite, when Porter's used Postgres? | No concurrent writers. The data changes a few times a year and is read-only when served. A file baked into the image makes a deploy atomic and every answer reproducible. Postgres would be ops cost with no benefit. | ADR-001 |
| How do you extract tables reliably? | Positions, not text. The data showed rows with 4 to 15 cells for 6 columns, and column edges that differ per table. So I derive column bands per table and assign each cell by its x-centre. A merged cell shows up as `None` below its anchor, and I inherit its value explicitly. | ADR-002, L1 §5 |
| What happens when your rules fail? | The row becomes an anomaly in a report. It is never dropped or guessed. A release build fails unless every anomaly is reviewed and allow-listed with a reason. | L1 §8 |
| How do you know the extraction is right? | A stratified golden set of 120 rows typed from the page images, part of it re-labelled by a second person, with a target fixed in advance. Every stored value is re-extracted from its bounding box (the provenance check). Mutation tests show the tests catch the bugs I'd expect. | Evaluation E1, L1 §10–12 |
| Why not fuzzy-match names automatically? | A silent wrong match ("chickpea" read as "cowpea") produces a confident wrong "yes". Fuzzy matching only suggests, and aliases come from a reviewed list. | ADR-006 |
| What's the most dangerous failure? | Telling someone a use is approved when it isn't. It's measured separately in E3 and must be zero. The banned list always overrides. | E3, threat model T4/T12 |
| How would you handle a new edition? | Update the manifest hash and rebuild. The section check flags layout changes. The build diffs the two editions. | NFR-9, L1 I5 |

## Concepts this milestone uses (study links)

- **Design, API contracts, error envelopes:** `study/modules/SE1_design_oop_patterns_api.md`
- **Test levels, property tests, mutation testing:** `study/modules/SE2_testing_review_debugging.md`
- **Build, CI, lockfiles, reproducibility:** `study/modules/SE3_build_ci_git_tooling.md`
- **Requirements, traceability, integration:** `study/modules/SE4_requirements_integration_agile_ai.md`
- **Hash maps for the alias index; the cost of the lookup indexes:** `study/modules/DSA2_hashing_trees_heaps_tries.md`
- **Read-only files, atomic rename, page cache:** `study/modules/OS7_filesystems_io.md`
