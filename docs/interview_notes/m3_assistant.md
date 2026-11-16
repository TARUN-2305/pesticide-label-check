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
