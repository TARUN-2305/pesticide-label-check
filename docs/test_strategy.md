# Test strategy

Version 0.1 (2026-11-13).

## Principles

1. **Tests are written before the code they test.** The case lists are in each LLD (L1 §10, L2 §8).
2. **No test asserts a constant for its own sake.** Every test protects a behaviour listed in an LLD. Each LLD names the mutants its tests must kill.
3. **Real data is opt-in and pinned by hash.** Unit tests never touch the network.

## Levels

| Level | Scope | Marker | Runs |
|---|---|---|---|
| Unit | pure functions over synthetic geometry and strings | (none) | every commit, under 10 s |
| Property | parsers and engine invariants (hypothesis, `derandomize=True` in CI for reproducibility; a random seed locally) | (none) | every commit |
| Golden pages | hand-labelled expected rows for named real pages | `corpus` | CI (PDFs fetched by hash) |
| Integration | API over a fixture register (`TestClient`), plus the OpenAPI freshness check | (none) | every commit |
| Evaluation | E1–E3 suites against the real register | `corpus` | CI, plus release |
| Performance | latency measurements written to `reports/perf/` | `perf` | manual, recorded with the environment |
| Mutation | the mutants listed in each LLD, applied one at a time; each must turn at least one test red | script `tools/mutants.py` | at the end of each milestone, reported in the LLD's results section |

## Quality gates (CI and `tools/ci.sh`)

1. `ruff check` and `ruff format --check`
2. `mypy --strict src/`
3. `pytest` (unit, property, integration) with branch coverage. The gate is ≥ 90 % for `extract`, `normalize` and `lookup`. This is a floor, not a goal; uncovered branches are reviewed.
4. `pytest -m corpus` (golden pages and evaluation suites) once the cache holds the PDFs
5. `python -m labelclaim.build run --release`: no anomaly outside the allow-list; the canonical dump hash is reported
6. **Determinism:** run the build twice with different `PYTHONHASHSEED` values; the dump hashes must be equal

## Flakiness

- **Concurrency is minimal by design:** the register is read-only and only the rate limiter is shared. Its test runs 20 times in CI, as in Porter's lesson (Phase 1 verification rule 2).
- **No sleeps in tests:** time is injected (a clock function) for the rate limiter and the fetch retries.
