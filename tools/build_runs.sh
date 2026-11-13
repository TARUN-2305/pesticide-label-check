#!/usr/bin/env bash
# P3 + determinism: 5 full builds from the cache, each with a different PYTHONHASHSEED; record time and hash.
set -euo pipefail
cd "$(dirname "$0")/.."
UV="${UV:-uv}"
out=reports/M1/build_runs.csv
echo "run,pythonhashseed,seconds,build_hash,uses,anomalies" > "$out"
for i in 1 2 3 4 5; do
  seed=$((i * 7919))
  PYTHONHASHSEED=$seed "$UV" run python -m labelclaim.build run --offline --out "build/run$i" > "build/run$i.log"
  python3 -c "import json,sys; d=json.load(open('build/run$i.log')); print(f\"$i,$seed,{d['seconds']},{d['build_hash']},{d['uses']},{sum(d['anomalies'].values())}\")" >> "$out"
done
cat "$out"
