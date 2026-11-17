# Pesticide label-claim check

**What it does:** answers *"Is this pesticide approved for this crop and pest? At what dose, and how many days before harvest?"* from India's official register, *Major Uses of Pesticides* (CIB&RC, PPQS). It cites the exact page and row. When there is no approved use, it says so and shows what *is* approved.

**For:** agri-input dealers, farmers and extension workers. Kannada and English, by text and later by voice.

**Status (2026-11-18):** M0 to M3 are implemented and tested. The register is a read-only SQLite file built offline from the official PDFs (release `285c851f…`: 2,297 approved-use rows, each with a page citation). The lookup engine and HTTP API answer from it deterministically (M2). The assistant (M3) lets a language model understand the question and phrase the reply, but every fact comes from the register, and a verifier blocks any dose, dilution or waiting period not in the cited rows. The latest live suite, E3n-c ([report](reports/E3nc/first_run.md)), found one approval for the wrong crop: the model translated a Kannada crop name itself. The deterministic guard for it is the next fix. There is no web app yet (M6).

| Milestone | Scope | State |
|---|---|---|
| M0 | Requirements, architecture, ADRs, LLDs, evaluation, tests, threats | designed, approved |
| M1 | Register extraction (L1) | implemented, tested; edge defects detected and corrected ([audit](reports/E1/edge_audit.md)); corrections reviewed, release verified; E1 golden set partly done |
| M2 | Lookup engine and HTTP API (L2) | implemented, tested, measured; release build verified ([L2 §12.5](docs/lld/l2_lookup_api.md)). E3: 122/150 on the first run (target 98 % **not met**); after the reviewed L2 §13 fixes, **58/60 on a fresh suite** with 0 false approvals ([report](reports/E3/report.md)) |
| M3 | Tool-calling layer + number verifier | implemented, tested; evaluated live on three suites ([E3n](reports/E3n/first_run.md), [E3n-b](reports/E3nb/first_run.md), [E3n-c](reports/E3nc/first_run.md)). On the fresh E3n-b, **80.4 %** of answerable questions reach the same answer as a structured lookup (90 % when typed plainly). No dose or waiting period outside the cited rows has been delivered in any suite. Open: one wrong-crop approval in E3n-c (fix A) |
| M4 | Evaluation on Kisan Call Centre questions | planned |
| M5 | Kannada, speech in and out | planned |
| M6 | Web app and pilot | planned |

## Design documents

- [Requirements](docs/requirements.md)
- [Architecture (HLD)](docs/architecture.md) and [decision records](docs/adr/)
- [L1: register extraction](docs/lld/l1_register_extraction.md)
- [L2: lookup engine and API](docs/lld/l2_lookup_api.md)
- [L3: assistant](docs/lld/l3_assistant.md)
- [Evaluation plan](docs/evaluation_plan.md), [test strategy](docs/test_strategy.md), [threat model](docs/threat_model.md)
- Interview notes: [M0 design](docs/interview_notes/m0_design.md), [M1 extraction](docs/interview_notes/m1_extraction.md), [M3 assistant](docs/interview_notes/m3_assistant.md)
- M1 results: [L1 §15](docs/lld/l1_register_extraction.md), [mutation checks](reports/M1/mutants.md), [build runs](reports/M1/build_runs.csv)

## Development

```bash
uv sync                                        # Python 3.12; locked; releases >= 14 days old only
tools/ci.sh                                    # ruff, mypy --strict, pytest with branch coverage
uv run python -m labelclaim.build fetch        # download the register PDFs, verified by SHA-256
uv run python -m labelclaim.build run          # dev build -> build/register.sqlite (+ anomalies, manifest)
uv run python -m labelclaim.build run --release  # refuses on any unreviewed lexicon row or unallowed anomaly
uv run python -m labelclaim.build audit        # counts from a built register
uv run pytest -m corpus                        # golden rows from the real register (needs the PDFs)
uv run python -m labelclaim.api                # http://127.0.0.1:8000/docs  (POST /v1/lookup)
```

## Data and disclaimer

- **Data:** the source PDFs are public documents of the Directorate of Plant Protection, Quarantine & Storage. They are pinned by SHA-256 in [`data/sources.toml`](data/sources.toml) and never committed.
- **Disclaimer:** the register describes itself as *"compiled on the basis of available information for guidance and not for legal purposes"*, and so is this tool. An "approved use" is a registered label claim, not a recommendation to spray. Follow the product label and your agriculture officer.
