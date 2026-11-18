# Practice questions, with answers

For self-study: cover the answer, say yours out loud, then compare. Each group goes from the opening question to the deep follow-up an interviewer might ask next.

## The system

**Q1. In one minute, what does it do and why is it hard?**
It answers "is this pesticide approved for this crop and pest, at what dose and waiting period" from India's official register, citing the page. It is hard because:
- the source is PDF tables that break every simple extraction rule;
- people name crops and pests in three languages;
- an LLM in the loop must never be the source of a fact.

**Q2. Walk me through one question end to end.**
"bende fruit borer Emamectin benzoate 5% SG":
1. The model calls `lookup` with product, crop and pest.
2. Guards compare its reading with the typed words. Fix A makes sure "bende" is looked up, not a translation.
3. The engine resolves bende to okra and finds the product's okra rows for fruit and shoot borer, so the outcome is APPROVED, with the row on p. 25.
4. The template headline is built from that outcome.
5. The model writes a short reply, and the verifier checks every number against the row.
6. The page shows the headline, the reply, the row as printed, and a link to the PDF page.

**Q3. What happens if the model is down?**
- Groq fails, so the router tries the first Gemini model that answers.
- If both fail, `/v1/ask` returns 503, the page says so, and it opens the **Check** tab: product, crop and pest go straight to the engine, with no model.

The register answer never depends on a model.

## Data and extraction

**Q4. How do you know the extraction is right?**
Four layers:
1. golden rows typed from page *images* (hard pages: 8, 20, 38/39, 51, 60, 67/68, 76);
2. re-reading every stored value from its box on every build;
3. invariants that turn surprises into reviewed anomalies;
4. mutation tests that prove those tests catch the bugs I would expect.

Measured: E1b reached 99.36 % of fields and 96.6 % of rows, one row short of the 97 % target, and I say that.

**Q5. What was the hardest extraction bug?**
Values continuing across a page break: a merged cell whose text is on the previous page arrives as an empty anchor. *Follow-up: how did you find it?* Golden pages, where the expected values were typed from images, so they disagreed with the extractor.

**Q6. Why keep the raw text if you parse the quantities?**
The user must see what the government printed: "As required depending upon crop stage", "Wet slurry treatment". Parsing helps matching, but the raw text is the authority (ADR-004).

## Names

**Q7. Why is "tikka" hard?**
The lexicon has three IDs (`tikka`, `tikka_disease`, `tikka_leaf_spot`) for what a farmer calls one disease, so an exact lookup said "not listed".
- **The fix:** near names. If the product's rows name a pest containing every asked word, the answer becomes a question: "listed for Tikka leaf spot. Is that your pest?"
- **Follow-up: why not merge them automatically?** Because "aphid" vs "mustard aphid" passes the same test and is *not* the same pest. A merge needs a human; an option needs only the user's confirmation.

**Q8. How do you handle "aalugaddeyalli"?**
A short list of Kannada case endings (-yalli, -alli, -kke, -ige, -ge…) is dropped only when what remains is an exact crop name, with -u restored for "maavige" → "maavu". It is deterministic and never fuzzy. 13 of 14 natural forms resolve on the real register.

## The LLM layer

**Q9. What exactly is the LLM allowed to do?**
- **Allowed:** read the question (choose `lookup` or ask one clarifying question) and phrase the engine's result in 1–3 sentences.
- **Not allowed:** decide the outcome, the headline, or any number that is not in the cited rows; use advice words; claim that the user's crop is another crop.

**Q10. How does the number verifier work, and how could it be fooled?**
It extracts every number in the reply (digits, ranges, fractions, number words, Kannada digits) and checks that each one is in the set of numbers allowed by the cited rows. The one extra allowance is the product's own strength, and only if it equals the register's canonical strength (the FR-7 amendment).
- **How it could be fooled:** a wrong *word* with no number ("approved for psylla *and mites*"), or an instruction in Kannada ("mix in 750 L of water", where 750 is in the row).
- **The planned answer:** a second-pass claim check.

**Q11. The model translated "bende" to brinjal. Why not fix the prompt?**
The prompt already said not to. A prompt shifts probabilities; a rule plus a test guarantees behaviour. *Follow-up: what can go wrong with your rule?* The unit "gram" is also a crop (chickpea), and crop words appear inside pest names ("mustard aphid"). Both have guards, tests and mutants.

**Q12. What does "never wider than the question" mean?**
A repair may narrow an answer or ask a question; it may never turn "is it approved for X on Y?" into "it's approved on Y".
- **Where it came from:** two failures. Fix A dropped a pest word; the model left the pest out.
- **The rules:** an unknown pest phrase gives "pest not found"; a short leftover phrase becomes the pest; a long one is treated as an instruction.

**Q13. How do follow-up questions work if the API is stateless?**
The page sends up to 4 earlier turns as chat turns. The model can then tell "aalugadde late blight" (an answer to "which crop?") from a new question. The deterministic checks read only the latest message.
- **The trap I fell into first:** joining the texts. A new brinjal question was read together with an old tomato one.

**Q14. How do you stop prompt injection?**
The only tool reads. The answer is the engine's, the headline is a template, and numbers and words are verified. Fake "assistant" turns from the client are dropped unless they look like the app's own short questions.

## Evaluation

**Q15. Your accuracy went from 61 % to 80 %. Is that real?**
- It is on *different* question sets, so it is indicative, not a paired comparison.
- Each set was committed **before** the fixes it measured, with predictions written first.
- The questions were written by me, which is a bias I disclose; the private test with a real user is the first independent measure.

**Q16. What is mutation testing, and what did it find?**
Deliberately break the code in a specific way and check that a test fails (89 mutants). It found:
- a test that had silently stopped testing the exact-strength rule after a later change;
- a mutant that had not run for two days;
- a red test suite that made new mutants *look* caught.

So the tool now checks the baseline and fails on any mutant it cannot apply.

**Q17. Why score from the recorded answers?**
Re-running today's code to score yesterday's run moved a committed number from 61.1 % to 65.6 %. Records make a number reproducible, and they make replays possible: running every past model call through new code to see what a fix changes. 352 calls were replayed: 49 better, 0 worse.

## Engineering and operations

**Q18. How would you deploy it?**
- **The container:** a slim Python image, locked dependencies, the release register baked in, a non-root user, read-only. Keys come from the host's secrets.
- **Private tests:** run from the laptop through a temporary link.
- **Behind a proxy:** the per-client limit needs `X-Forwarded-For`, which a client can forge, so the global daily cap is what protects the model quota.

**Q19. What does a request cost?**
A lookup costs nothing measurable (0.16 ms). An Ask is 1–2 model calls on free tiers, and the daily cap of 800 keeps it under Groq's 1,000 a day. At scale: cache repeated questions, and use the Check path when a question is already structured.

**Q20. What is not finished, and why?**
- **Real farmer questions (M4):** the government API returned 502 on every try.
- **Voice (M5):** on hold, because chemical names defeat speech-to-text.
- **The public link:** waiting for the publisher's permission.
- **A lexicon release:** the tikka merge and new spellings.
- **An "options" query and a Kannada wording guard.**

## Deep follow-ups

**Q21. Two official sources disagree. What do you show?**
Both, with the safer one first. A 2023 order bans Mancozeb on jowar, but the 2026 register still prints the claim. The headline says "Banned on this crop: <order>", then that the register still prints it.

**Q22. If you had a month more?**
1. The claim checker (a second LLM pass, verified against the rows).
2. Constrained name choices by the model from the register's own names.
3. A lexicon release.
4. The options query.
5. A real pilot with a dealer, with consent and logging.

**Q23. What would break first at 100× the traffic?**
The model quota, not the engine. Options: caching, paid tiers within a budget, and making structured Check the default path.
