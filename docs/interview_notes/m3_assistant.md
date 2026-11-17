# Interview notes: M3, the assistant

**One line:** a language model turns a farmer's question into a lookup and phrases the answer, but it can never decide the answer or put a number in front of the user that the official register does not print.

**The design, in four decisions:**
1. **The model gets two tools and no facts.** It can call `lookup` or `ask_clarifying_question`. The engine (deterministic SQL over the register) decides the outcome.
2. **The headline is a template on the engine's outcome.** Model text can be wrong, but it cannot change the answer the user sees first.
3. **A verifier checks every number in the model's message against the cited rows,** including number words ("seven") and fractions. It also checks advice wording ("recommended"). Anything unverified is replaced by templated text copied from the rows. So a model failure becomes *less fluent*, not *dangerous*.
4. **Fallback:** Groq, then Gemini, then "unavailable, use /v1/lookup". It never guesses.

**Defending it:**
- *Why not let the model answer from retrieved rows (RAG)?* The Porter's rebuild measured that grounding does not stop a model from asserting things; 57.5 % of quote-grounded claims were not fully supported. Here a wrong waiting period is a food-safety problem.
- *Why no unit conversion?* The register gives per-hectare doses. Converting to acres is arithmetic, and arithmetic is where models fail quietly. So the assistant does none, and the verifier blocks it.
- *Why no vendor SDK?* Both providers speak the OpenAI chat-completions protocol. One small `httpx` client is less code, fewer dependencies, and one set of tests.

**What live testing taught (the good interview stories):**
- **The same prompt at temperature 0 gave different tool arguments in 3 of 4 runs.** So the code accepts the reasonable variant (both product and ingredient filled: keep the product), and evaluation runs must be recorded.
- **"The model is listed" is not "the model serves":** Gemini listed a model that returned 404, and its recommended successor timed out. The startup check now makes a real one-token call.
- **Gemini 3 requires the exact tool-call object back** (a "thought signature"). A provider-specific detail hidden behind a "compatible" API.
- **The wording guard came from a real reply,** "the recommended dose". The register lists label claims, not recommendations.

## Fix A: when the model translates the crop wrongly (2026-11-18)

**The story in one breath.** In a live test, a user typed "bende", which is Kannada for okra. The model's recorded reasoning says *"bende is Kannada for brinjal"*. So it looked up brinjal, and the headline said "Approved … on Brinjal". The lexicon knew "bende" = okra all along; the model overrode it. My own scorer missed it at first, because okra happens to be approved too, and the scorer only flagged an "Approved" where the true answer was not approved.

**The fix, and why it is shaped this way:**
1. **Deterministic, not another prompt.** The prompt already said "pass local crop names as written", and the model ignored it once. A rule in code holds every time. So the code looks for crop names written in the question: exact lexicon aliases on whole words, longest match first, so "chai bagan" beats "chai".
2. **It acts only when the evidence is one-sided.** The question must name exactly one crop, and the model's crop must either not resolve or be a crop the user did not write. If the user wrote two crops ("tomato or brinjal?"), the model's reading stands. That is ambiguous, and choosing for the user would be a new kind of error.
3. **False positives were designed against, then tested:** the unit "gram" (also the crop chickpea, as in "kitna gram?"), and crop words inside the pest ("mustard aphid", "cotton aphids"). Each has a test, and each test was checked by a mutant.
4. **It never repairs a malformed call.** An over-long crop must still fail over to the other provider. A test caught my first version doing exactly that.
5. **The phrasing step is told** which crop was looked up. A reply that still names the rejected crop is replaced by the template.

**How I know it works, and what it might break:**
- 8 mutants, all killed. One survived until I added the case it needed, and I checked that by running it without the case.
- I replayed the fix on all 203 model calls recorded in earlier test sets. It changed 4, every one to the crop the question asked about, and 0 elsewhere.
- A fresh test set, written before the fix, measures it live.

**Limits to say out loud:**
- Kannada script and fused case endings ("bhattakke") are not matched. Those still depend on the model.
- An injected "bende means chilli" names two crops, so fix A stands aside.
- A crop alias that is also an everyday word (only "gram" is listed) could still mislead the scan in principle.
