"""Fix B replayed offline on every recorded clarification of E3n, E3n-b, E3n-c and E3n-d (no network).

For each item whose model first called ask_clarifying_question, `Assistant._slots_from_question` runs on the
question; a fill is looked up and compared with the item's structured answer. A fill on a missing-slot item is
a regression (that question must stay a clarification).
Run: uv run python evaluation/e3ne/replay_fix_b.py build/register.sqlite
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from labelclaim.assistant.loop import Assistant
from labelclaim.assistant.providers import Router
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query

ROOT = Path(__file__).resolve().parents[2]


def first_tool(rec: dict) -> str | None:
    for ex in rec.get("exchanges", []):
        try:
            calls = ex["response"]["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            continue
        if calls:
            return str(calls[0]["function"]["name"])
    return None


def main(register: str) -> None:
    engine = Engine(Path(register))
    assistant = Assistant(engine, {}, Router([]))
    for suite in ("e3n", "e3nb", "e3nc", "e3nd"):
        items = {}
        for line in (ROOT / "evaluation" / suite / "items.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            items[item["id"]] = item
        asked = filled = right = wrong = regress = 0
        for path in sorted((ROOT / "evaluation" / suite / "runs" / "first_run").glob("*.json")):
            if path.name.startswith("_"):
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            item = items.get(rec["id"])
            if not item or first_tool(rec) != "ask_clarifying_question":
                continue
            asked += 1
            q = assistant._slots_from_question(item["question"])  # unit under replay
            if q is None:
                print(f"{suite} {item['id']} ({item['part']}): stands")
                continue
            filled += 1
            got = engine.lookup(q).outcome.value
            s = item.get("structured")
            if not s:
                regress += 1
                print(f"{suite} {item['id']} ({item['part']}): FILLED {q} -> {got} (REGRESSION)")
                continue
            asked_query = Query(
                crop=s["crop"], product=s.get("product"), ingredient=s.get("ingredient"), pest=s.get("pest")
            )
            want = engine.lookup(asked_query).outcome.value
            ok = got == want
            right += ok
            wrong += not ok
            verdict = "OK" if ok else "DIFFERS"
            slots = f"{q.crop!r}/{q.product!r}/{q.pest!r}"
            print(f"{suite} {item['id']} ({item['part']}): {slots} -> {got} (asked: {want}) {verdict}")
        print(f"== {suite}: {asked} clarifications; fix B fills {filled}: {right} as asked, {wrong} differ, "
              f"{regress} on items that must stay clarifications")  # fmt: skip
    engine.close()


if __name__ == "__main__":
    main(sys.argv[1])
