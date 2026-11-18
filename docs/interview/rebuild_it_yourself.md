# Rebuild it yourself: six exercises

The fastest way to *own* a system is to rebuild its core ideas from scratch, then compare your version with the real code.

Each exercise below has five parts:
- a goal;
- a size, so you can plan an evening;
- a starting point;
- a check that tells you it works;
- where the real version lives.

Do them in a scratch folder, not in the repo. All of them run with Python 3.12 and need nothing beyond the project's dependencies.

---

## 1. Read one table page by position *(extraction)*

**Goal:** from one real register page, produce rows of (crop, pest, dose a.i., dose of product, water, waiting period).

**Size:** 2–3 hours.

**Start:**
1. Open the cached insecticide PDF; `ensure_cached` in `src/labelclaim/sources.py` shows where it is.
2. `pdfplumber.open(path).pages[19]` is printed page 20.
3. Get `page.extract_words()` and the table's vertical lines. Make column bands from the line x-positions. Put each word in the band its *centre* falls in.

**Check:** you get the three Maize rows of page 20 that `test_ins_p20_merged_crop_dilution_and_waiting_period` expects ("Fall Army Worm", 1.8, 3, …).

**Then compare** with `extract/geometry.py` and `extract/assemble.py`. Notice what you didn't handle: a crop merged across rows, a value spanning two columns, a page break.

## 2. Names that match the way people type *(the lexicon)*

**Goal:** a `match_key(text)` and a resolver with these properties:
- "White fly", "Whiteflies" and "whitefly" are one name;
- "Tomato/Chilli" names two crops;
- an unknown word returns "did you mean" suggestions, never a silent match.

**Size:** 1–2 hours.

**Start:** lower-case the text, drop punctuation and spaces, and fold plurals (-ies → -y, -s → nothing, but not -ss). Build a dict from key to the set of IDs.

**Check:** your function agrees with `normalize/lexicon.py` on these inputs:
- "Whiteflies"
- "Pests: aphids"
- "Rice (Paddy)"
- "glass"

**Stretch:** add Kannada case endings, accepting the stem only if it is an exact name. Compare with `Names.kannada_stem`.

## 3. The decision function *(the engine)*

**Goal:** `lookup(product, crop, pest)` over a small in-memory table, returning exactly one outcome: APPROVED, NOT_APPROVED_FOR_CROP, NOT_APPROVED_FOR_PEST, UNKNOWN_PRODUCT, UNKNOWN_CROP, UNKNOWN_PEST or AMBIGUOUS.

**Size:** 2 hours.

**Start:** decide the *order* of checks first: product, then crop, then pest, then the product's rows on the crop. Write the 7 outcomes as tests before writing the code.

**Check:**
- (Chlorantraniliprole 18.5% SC, tomato, fruit borer) is APPROVED;
- the same product on tomato for stem borer is NOT_APPROVED_FOR_PEST;
- on cotton, it is NOT_APPROVED_FOR_CROP;
- **stretch:** "borer" gives AMBIGUOUS, offering fruit borer.

Use `tests/registerkit.py`'s rows as your data.

**Then compare** with `Engine._on_crop`.

## 4. A tool-calling loop with a fake model *(the assistant)*

**Goal:** the shape of the assistant loop, without a network.
1. Send the question and two tool definitions.
2. Read the tool call.
3. Run your Exercise 3 lookup.
4. Send the result back.
5. Get the reply.

**Size:** 2 hours.

**Start:** copy the idea of `Script` in `tests/test_assistant.py`: a fake client that returns scripted replies and records what it was sent. Write the OpenAI-style messages yourself:

```text
system   the rules
user     the question
assistant  with tool_calls
tool     the result as JSON
```

**Check:** your recorded messages have the same roles, in the same order, as `test_earlier_turns_go_to_the_model_as_a_conversation` expects.

**Stretch:** call Groq for real with `httpx` (your key comes from `~/.config/labelclaim/env`; never print it).

## 5. The number verifier *(the safety core)*

**Goal:** `verify(reply, allowed) -> list of numbers not allowed`.

**Size:** 2–3 hours.

**Start:**
- find numbers with a regex;
- handle ranges ("500–1000"), decimals, fractions ("3½") and number words ("seven");
- compare them as `Decimal`, so "07.70" = "7.7".

**Check:** with the allowed set {30, 150, 500, 3}:
- "30 g a.i. (150) in 500 L; wait 3 days" passes;
- "use 999 ml" fails on 999;
- "seven days" fails on 7.

**Then compare** with `assistant/verify.py`. Then try to fool your verifier with words. That is exactly why fix E and the planned claim checker exist.

## 6. One guard, built test-first *(fix A)*

**Goal:** when the question names exactly one crop by an exact lexicon name, and the model's crop is different and not written in the question, use the question's crop.

**Size:** 2 hours.

**Start:** write these tests first:
1. the "bende" / brinjal case;
2. "kitna gram" (a unit, not chickpea);
3. "cotton aphids on golbheda" (a crop word inside the pest);
4. "tamatar ya rice" (two crops: leave the model's choice).

Then write the code.

**Check:** all 4 pass. Then break your own code in 3 ways and see which test fails each time; that is mutation testing by hand.

**Then compare** with `Assistant._users_crop` and the FA-M1…M12 mutants in `tools/mutants.py`.

---

## After the six

You will have rebuilt:
- extraction by position;
- name matching;
- the closed-outcome engine;
- the tool loop;
- the verifier;
- one guard.

That is every idea in the system. What remains in the real repo is the *rigour around* those ideas: provenance re-reads, release gates, recorded evaluations and replays, and mutation testing. The [decisions and stories](decisions_and_stories.md) file explains why each one exists.
