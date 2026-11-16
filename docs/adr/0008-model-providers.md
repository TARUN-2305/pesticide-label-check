# ADR-008: Model providers, Groq first and Gemini as fallback, both on free tiers

Status: accepted (2026-11-15); the user chose "Groq, Gemini fallback".

## Context
- **NFR-8:** the cost is ₹0 by default, and any paid API needs the user's permission. The user already has Groq and Gemini keys from the Porter's project.
- **The model's job is small** (ADR-003): pick one of two tools and fill four short strings, then phrase a short reply. That needs reliable tool calling more than a frontier model.
- **Free tiers are limited and can change.**
  - Groq publishes exact limits only per account (console limits page).
  - Google calls the Gemini free tier "best-effort" and "highly unstable" (developer-forum statement by Google staff).
- **Both speak the OpenAI chat-completions protocol:** Groq natively, Gemini through its OpenAI-compatibility endpoint.

## Decision
- **Primary: Groq**, model `openai/gpt-oss-120b`. Groq lists it for tool use and for strict structured outputs (constrained decoding), which keeps tool arguments schema-valid.
- **Fallback: Gemini**, model `gemini-3.5-flash`.
  - **Changed 2026-11-15 after live checks:** `gemini-2.5-flash`, the docs' "stable" model, is listed but answers 404 "no longer available to new users", and the model that error recommends, `gemini-3.8-flash`, timed out at 60 s.
  - **Gemini 3 requires its own tool-call object to be echoed back** (thought signature).
  - The startup check makes one tiny real call, because being listed is not proof that a model serves.
- **One small `httpx` client for both.** No vendor SDKs: fewer dependencies (NFR-7), and the same request and response code is tested once.
- **Models are configuration.** They are checked against each provider's `/models` list at startup, so a renamed or retired model disables that provider and the build does not quietly use something else.
- **When both fail,** the assistant says so (503) and points to the structured `/v1/lookup`. It never guesses.

## Consequences
- **Plus:** ₹0, two independent providers, and no vendor lock-in in the code. Swapping a model is a config change, which is then re-measured with E3n.
- **Minus:** throughput is capped by free-tier limits, so evaluation runs are throttled and recorded for offline re-scoring. Gemini's free tier may shrink without notice.
- **Not chosen:**
  - a local Ollama model: slower on this laptop, and weaker at tool calling;
  - the paid Claude API: it needs a budget the user has not given.

  Either can be added later as another `ChatClient` base URL.

## Sources (accessed 2026-11-15)
- Groq tool use: <https://console.groq.com/docs/tool-use/overview>
- Groq structured outputs (strict mode models): <https://console.groq.com/docs/structured-outputs>
- Groq rate limits: <https://console.groq.com/docs/rate-limits>
- Gemini function calling: <https://ai.google.dev/gemini-api/docs/function-calling>
- Gemini OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- Gemini 2.5 Flash (stable): <https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash>
- Gemini rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
