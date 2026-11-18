"""Fix E replayed offline on every delivered model reply of E3n..E3n-e: which replies equate the crop that was
looked up with another crop? Run: uv run python evaluation/e3nf/replay_fix_e.py build/register.sqlite"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from labelclaim.assistant.loop import Assistant
from labelclaim.assistant.providers import Router
from labelclaim.lookup.engine import Engine

ROOT = Path(__file__).resolve().parents[2]


def main(register: str) -> None:
    engine = Engine(Path(register))
    assistant = Assistant(engine, {}, Router([]))
    total = flagged = 0
    for suite in ("e3n", "e3nb", "e3nc", "e3nd", "e3ne"):
        for path in sorted((ROOT / "evaluation" / suite / "runs" / "first_run").glob("*.json")):
            if path.name.startswith("_"):
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            res = rec.get("result") or {}
            if res.get("phrased_by") != "model" or not res.get("slots"):
                continue
            total += 1
            other = assistant._attached_crop(res["message"], res["slots"]["crop"])  # the unit under replay
            if other is not None:
                flagged += 1
                print(f"{suite} {rec['id']}: crop {res['slots']['crop']!r}, reply attaches {other!r}")
                print(f"    {res['message'][:160]}")
    print(f"== {total} delivered model replies; fix E flags {flagged}")
    engine.close()


if __name__ == "__main__":
    main(sys.argv[1])
