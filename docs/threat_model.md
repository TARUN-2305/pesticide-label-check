# Threat and failure model

Version 0.1 (2026-11-13). Status of all mitigations: **planned**.

## Assets

- **The correctness of each answer.** Doses and waiting periods affect health and food safety.
- **The users' trust.** One confident wrong answer outweighs many good ones.
- **Users' data** (from M5 on): voice recordings and questions.

## Failure and threat table

| # | Threat / failure | Impact | Likelihood | Mitigation | Verified by |
|---|---|---|---|---|---|
| T1 | Extraction maps a value to the wrong column or row | Wrong dose or waiting period shown | Medium (complex tables) | Geometry bands; merge anchors; provenance re-check (I3); golden set E1; **raw text shown with page link** | E1, L1 tests, mutants |
| T2 | A tampered or replaced source PDF | Wrong facts at scale | Low | SHA-256 manifest; build aborts on mismatch | `sources` tests |
| T3 | A stale register (a new edition is published) | Missing new approvals or bans | Medium | Every answer shows the register date. The manifest records the edition. A scheduled check compares the remote file hash and alerts (M6). | M6 |
| T4 | A fuzzy name match silently answers about the wrong crop or product | A "yes" for the wrong thing | Medium | Fuzzy matching only suggests (ADR-006); E3 cases | L2 tests |
| T5 | "Approved" is read as "recommended" | Over-use of pesticides | Medium | Fixed wording; the disclaimer on every answer; no ranking language ("best") | UI review in M6 |
| T6 | An LLM invents or alters a number (M3+) | A dangerous answer | High without controls | The number verifier blocks the reply and falls back to a template (ADR-003); E4 unverified-number rate = 0 | M3 tests, E4 |
| T7 | Prompt injection through user text (M3+) | The model breaks its rules | Medium | The model has only 2 tools, both read-only; its output passes the verifier. The register text is data, not instructions (it is never put in the system prompt as rules). | M3 red-team cases |
| T8 | Malformed or oversized input to the API | Crash or resource exhaustion | Medium | Pydantic limits; `extra="forbid"`; 120-character fields; rate limit; the error envelope | L2 API tests |
| T9 | Personal data leaks through the logs | Privacy breach | Low–Medium | Logs never hold the query text; voice is not stored (M5); pilot logging only with consent | log-capture test |
| T10 | Dependency compromise | Arbitrary code | Low | uv lock with hashes; `exclude-newer` 14 days; minimal dependencies | CI |
| T11 | Unavailable third parties (PPQS site, Bhashini) | No build, or no voice | Medium | The PDFs are cached by hash; building works offline; voice falls back to text | `--offline` test |
| T12 | A banned ingredient appears with an approval (an edition mismatch) | Recommends a banned product | Low | The restriction overlay always wins and is shown first | E3 restriction cases |

## Out of scope

- Attacks needing server compromise. The deployment hardening comes in the M6 LLD.
- Legal liability analysis. The tool states that it is guidance only, as the register does.
