# The builder's handbook: Pesticide label-claim check

This folder is for the person who built the project: you. It has two goals:
- you can explain any part, and defend every decision, in an interview;
- if asked, you could rebuild the core yourself.

Read it in this order:

| File | What it gives you | Time |
|---|---|---|
| **This page** | The pitch at three lengths, what is done and not done, the numbers | 10 min |
| [how_it_works.md](how_it_works.md) | The whole system, stage by stage: what each part does, why, where the code is, and which test proves it | 45 min |
| [decisions_and_stories.md](decisions_and_stories.md) | The decisions you will be challenged on, and the real failures you found and fixed. These make the best interview answers | 30 min |
| [practice_questions.md](practice_questions.md) | Questions from easy to hard, with answers, for self-study | 30 min |
| [rebuild_it_yourself.md](rebuild_it_yourself.md) | Six small exercises that rebuild the core ideas from scratch, each checked against the real code | a few evenings |

Older notes are still accurate for their own milestones: `../interview_notes/` (M0, M1, M3) and `reports/pesticide_label_check_interview_brief.md` in the workspace (17 Nov). This folder supersedes them where they differ.

---

## The pitch

**30 seconds.**
> "Dealers and farmers in India ask one question all the time: is this pesticide approved for this crop and pest, at what dose, and how long before harvest? The official answer is in a 200-page government register, as PDF tables. I turned that register into a checked database where every row links back to its page. A lookup engine answers from that database alone. On top sits an LLM assistant that understands questions typed in English, Kannada or Hindi. The rule I built everything around: **the language model reads the question and words the reply, but the register decides the answer**, and code checks that no number or claim reaches the user unless the register printed it."

**2 minutes:** add the three hard parts.
1. **Getting the data out.** The register is a Word-to-PDF export: tables continue across pages, cells span columns, and one table can hold two products with different column widths. I extracted by position, not by text. Every one of about 14,000 values is re-read from its box in the PDF on every build, and a human reviews every anomaly before a release.
2. **Names.** Farmers say "bende", "bhatta", "aalugaddeyalli". I built a reviewed lexicon (382 crop names, 1,235 pest names) with deterministic matching, and fuzzy matches are only ever suggested.
3. **Trusting an LLM in a safety domain.** The model calls one lookup tool and phrases the result. The headline is a template from the engine's outcome. A verifier blocks any dose or waiting period not in the cited rows. Deterministic guards catch the model's mistakes: translating "bende" (okra) to brinjal, dropping the pest, asking needless questions.

**5 minutes:** add how you know it works.
- **Tests:** 379 automated tests, and 89 "mutants" (deliberately broken versions of the code), every one caught.
- **Engine accuracy:** 150/150 on hand-written queries (E3).
- **Language layer:** eight live test sets, each written *before* the fix it measures, with my predictions written down first, including the wrong ones.
- **A private test** with a real user found six problems. I fixed them in safety order. A replay of every earlier test through the new code moved 49 answers to the right one and none away from it.

**The one sentence to end on:**
> "A pesticide checker must be more afraid of a wrong approval than of saying 'I don't know', and every design choice follows from that."

---

## Is it finished? (say this before you are asked)

| Part | State |
|---|---|
| Register extraction, lexicons, release gate (M1) | **Done, tested, measured.** E1b: 99.36 % of fields, 96.6 % of rows (target 97 %, missed by one row) |
| Lookup engine and HTTP API (M2) | **Done, tested, measured.** E3: 150/150, 31/31, 59/60 (E3b-28, a near-name case, is now offered as an option rather than a false "no") |
| Assistant: tool calling, verifier, guards (M3) | **Done, tested, evaluated live.** Fixes A, A2, A3, B and E are all built from measured failures |
| Phone-friendly web app (M6) | **Built and browser-tested.** One private test with the user and ChatGPT (25 questions); its 6 issues are fixed |
| Evaluation on real farmer questions (M4) | **On hold:** the data.gov.in API returned 502 on every try |
| Voice in Kannada (M5) | **On hold, by decision:** chemical names are far harder to hear than to type |
| Public link | **Waiting for PPQS's reply** to a permission email (their website policy requires it) |
| Open items | A reviewed lexicon release (merge the three "tikka" IDs; add spellings like "badnekayi", "gulab"); an "options" query (what is approved for a crop and disease); splitting "X and Y" pests; a Kannada wording guard |

The honest headline: **the core system is complete and defended by evidence; the real-world rollout is not.**

---

## Numbers you can quote (each has a source you can open)

| Claim | Number | Where it comes from |
|---|---|---|
| Register size (release `285c851f…`) | 2,297 approved uses; 659 products; 296 ingredients; 120 crops; 563 pests; 97 restrictions | `build/register.sqlite`, `build_info` |
| Names | 382 crop aliases, 1,235 pest aliases, all reviewed | `data/lexicon/` |
| Extraction accuracy | 99.36 % of fields; 96.6 % of rows (57/59) | `reports/E1/report.md` |
| Lookup speed | in-process p50 0.12 ms, p95 0.16 ms; over HTTP p50 1.5 ms, p95 2.3 ms | `docs/lld/l2_lookup_api.md` §12.5 |
| Engine correctness | E3 150/150; extra 31/31; E3b 59/60 | `reports/E3/` |
| Language layer, first live suite | 61.1 % of questions reached the structured answer | `reports/E3n/first_run.md` |
| After the first six fixes (fresh suite) | 80.4 % (90 % when typed plainly) | `reports/E3nb/first_run.md` |
| Fix B live | turned needless "which crop?" questions into correct answers: 5/5 (E3n-e), 12/12 (E3n-f) | `reports/E3ne/`, `reports/E3nf/` |
| Safety | 0 doses or waiting periods outside the cited rows in any suite | every `reports/E3n*/first_run.json` |
| Replay of 352 recorded model calls through the final code | 49 answers move to the right one, 0 away | `evaluation/e3ne/replay_understanding.py` |
| Tests and mutants | 379 tests; 89/89 mutants killed | `tools/ci.sh`, `reports/M3/mutants_2026-11-19.md` |
| Size | about 5,400 lines of Python, 3,900 of tests; 43 commits | `git log` |

**Be precise in the interview:**
- "80 %" was measured on *my own* question sets, not on real farmers. Say so.
- The engine's 150/150 is on hand-written queries whose expected answers were labelled from the page images.
- Latency is on one laptop (localhost).
