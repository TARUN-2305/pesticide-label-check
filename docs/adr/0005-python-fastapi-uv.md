# ADR-005: Python 3.12, FastAPI, uv (exclude-newer), ruff, mypy strict

Status: proposed (2026-11-13)

## Decision
- **Language:** Python 3.12 (as in Porter's, so one toolchain).
- **Packaging:** uv for dependency locking with hashes. `exclude-newer` is set to 14 days before the lock date, which enforces the "releases at least 2 weeks old" rule mechanically.
- **API:** FastAPI + Pydantic v2 (OpenAPI for free; the same patterns as Porter's R6).
- **PDF:** pdfplumber (pure Python, on top of pdfminer.six).
- **Quality:** ruff (lint and format), mypy `--strict` on `src/`, pytest + hypothesis (property tests for the parsers), coverage with branch measurement.

## Alternatives considered
- **Go or Rust for the API:** no measurable need. The latency budget (p95 ≤ 20 ms in-process) is met by indexed SQLite lookups.
- **Poetry:** uv is already installed (`~/.venvs/nokia-tools/bin/uv` 0.13.6) and used in Porter's.
