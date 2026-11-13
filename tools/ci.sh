#!/usr/bin/env bash
# Quality gates (docs/test_strategy.md). Usage: tools/ci.sh [--corpus]
set -euo pipefail
cd "$(dirname "$0")/.."
UV="${UV:-uv}"
"$UV" sync --locked
"$UV" run ruff check .
"$UV" run ruff format --check .
"$UV" run mypy
"$UV" run pytest --cov --cov-branch --cov-report=term-missing
if [[ "${1:-}" == "--corpus" ]]; then
  "$UV" run pytest -m corpus
fi
