# Pesticide label-claim check

**What it does:** answers *"Is this pesticide approved for this crop and pest? At what dose, and how many days before harvest?"* from India's official register, *Major Uses of Pesticides* (CIB&RC, PPQS). It cites the exact page and row. When there is no approved use, it says so and shows what *is* approved.

**For:** agri-input dealers, farmers and extension workers. Kannada and English, by text and later by voice.

**Status (2026-11-15):** M0 design reviewed and approved. **M1 (register extraction) and M2 (lookup engine and HTTP API) are implemented and tested.** The crop, pest and ingredient lexicons and the anomaly allow-list are human-reviewed, and the *release* build passes: 2,374 approved-use rows, each with a page citation. An edge audit found 13 rows the extractor misread (one with a wrong crop); they are now detected, and corrected through a reviewed file ([ADR-007](docs/adr/0007-reviewed-corrections.md)). The corrections were reviewed under the user's delegation, and the release build passes (`d86befe7…`). E1 (120 random rows, labelled from page images) found one defect, split pest cells. After the fix (L1 §17), the register's pest-only rows went from 77 to 2, and a fresh E1b sample of 60 rows scores **99.36 % of fields and 96.6 % of rows** (target 97 %, missed by one row; [report](reports/E1/report.md)). There is no app yet.

| Milestone | Scope | State |
|---|---|---|
| M0 | Requirements, architecture, ADRs, LLDs, evaluation, tests, threats | designed, approved |
| M1 | Register extraction (L1) | implemented, tested; edge defects detected and corrected ([audit](reports/E1/edge_audit.md)); corrections reviewed, release verified; E1 golden set partly done |
| M2 | Lookup engine and HTTP API (L2) | implemented, tested, measured; release build verified ([L2 §12.5](docs/lld/l2_lookup_api.md)). E3: 122/150 on the first run (target 98 % **not met**); after the reviewed L2 §13 fixes, **58/60 on a fresh suite** with 0 false approvals ([report](reports/E3/report.md)) |
| M3 | Tool-calling layer + number verifier | implemented, tested; evaluated: on a fresh suite of 84 questions, **80.4 %** of answerable questions reach the same answer as a structured lookup (90 % when typed plainly), and no dose or waiting period outside the cited rows was ever delivered ([E3n](reports/E3n/first_run.md), [E3n-b](reports/E3nb/first_run.md)) |
| M4 | Evaluation on Kisan Call Centre questions | planned |
| M5 | Kannada, speech in and out | planned |
| M6 | Web app and pilot | planned |

## Design documents

- [Requirements](docs/requirements.md)
- [Architecture (HLD)](docs/architecture.md) and [decision records](docs/adr/)
- [L1: register extraction](docs/lld/l1_register_extraction.md)
- [L2: lookup engine and API](docs/lld/l2_lookup_api.md)
- [Evaluation plan](docs/evaluation_plan.md), [test strategy](docs/test_strategy.md), [threat model](docs/threat_model.md)
- Interview notes: [M0 design](docs/interview_notes/m0_design.md), [M1 extraction](docs/interview_notes/m1_extraction.md)
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
