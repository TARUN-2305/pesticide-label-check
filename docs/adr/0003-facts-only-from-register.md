# ADR-003: Facts only from the register; models interpret and phrase

Status: proposed (2026-11-13)

## Context
- **A wrong number causes real harm.** A wrong dose or waiting period can mean pesticide residue in food or worker poisoning.
- **The rebuild measured the risk.** In Porter's R4, 57.5 % of quote-grounded claims were still not fully supported. Grounding text does not stop a model from asserting things.

## Decision
- The lookup engine is deterministic and produces every fact.
- A language model (M3+) may only:
  1. turn a question into a structured `lookup` call, or ask a clarifying question;
  2. phrase the returned rows in the user's language.
- A **number verifier** extracts every numeral from the model's reply and checks it against the cited rows. Any numeral not found there blocks the reply. The system then falls back to a templated answer.

## Consequences
- **Plus:** the LLM's failure mode becomes "unhelpful", not "dangerous". The verifier is testable without a model.
- **Minus:** less fluent answers. A Kannada numeral and unit normaliser is needed before verification (M5).
