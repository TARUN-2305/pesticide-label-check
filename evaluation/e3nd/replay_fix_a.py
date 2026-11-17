"""Fix A replayed offline on every recorded model call of E3n, E3n-b and E3n-c (no network).

For each recorded item, the question and the crop and pest the model first passed go through
`Assistant._users_crop`; every change is printed with the structured crop the item asks about.
Run: uv run python evaluation/e3nd/replay_fix_a.py build/register.sqlite
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from labelclaim.assistant.loop import Assistant
from labelclaim.assistant.providers import Router
from labelclaim.lookup.engine import Engine

ROOT = Path(__file__).resolve().parents[2]


def first_lookup(rec: dict) -> dict | None:
    for ex in rec.get("exchanges", []):
        try:
            calls = ex["response"]["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            continue
        for c in calls:
            if c.get("function", {}).get("name") == "lookup":
                return json.loads(c["function"]["arguments"])
    return None


def main(register: str) -> None:
    engine = Engine(Path(register))
    assistant = Assistant(engine, {}, Router([]))
    for suite in ("e3n", "e3nb", "e3nc"):
        items = {}
        for line in (ROOT / "evaluation" / suite / "items.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            items[item["id"]] = item
        calls = changed = right = 0
        for path in sorted((ROOT / "evaluation" / suite / "runs" / "first_run").glob("*.json")):
            if path.name.startswith("_"):
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            args = first_lookup(rec)
            item = items.get(rec["id"])
            if not args or not item or not args.get("crop"):
                continue
            calls += 1
            crop = str(args["crop"]).strip()
            pest = (str(args["pest"]).strip() or None) if args.get("pest") else None
            used = assistant._users_crop(item["question"], crop, pest)  # the unit under replay
            if used != crop:
                changed += 1
                want = (item.get("structured") or {}).get("crop")
                ok = bool(want) and engine.names.crop(used).ids == engine.names.crop(want).ids
                right += ok
                verdict = "OK" if ok else "WRONG"
                print(f"{suite} {rec['id']}: {crop!r} -> {used!r} (asked: {want!r}) {verdict}")
        print(f"{suite}: {calls} recorded lookup calls; fix A changes {changed}; {right} to the asked crop")
    engine.close()


if __name__ == "__main__":
    main(sys.argv[1])
