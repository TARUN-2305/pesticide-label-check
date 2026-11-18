"""Every recorded first model call of E3n..E3n-e, replayed through today's `Assistant._understand`.

No network.

The recorded tool call is fed back as the model's reply; the resulting lookup (or clarification) is compared
with what the item recorded, and with the item's structured answer. Prints only items whose outcome changes.
Run: uv run python evaluation/e3ne/replay_understanding.py build/register.sqlite
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from labelclaim.assistant.loop import SYSTEM, Assistant
from labelclaim.assistant.providers import ChatReply, ProviderError, Router, ToolCall
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query

ROOT = Path(__file__).resolve().parents[2]
SUITES = ("e3n", "e3nb", "e3nc", "e3nd", "e3ne")


class Recorded:
    name, model = "recorded", "recorded"

    def __init__(self, call: ToolCall) -> None:
        self.call = call

    def chat(self, *_: Any, **__: Any) -> ChatReply:
        return ChatReply(None, self.call, 0, 0, 0.0)


def first_call(rec: dict) -> ToolCall | None:
    for ex in rec.get("exchanges", []):
        try:
            calls = ex["response"]["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            continue
        if calls:
            fn = calls[0]["function"]
            return ToolCall(calls[0].get("id", "c"), fn["name"], json.loads(fn["arguments"] or "{}"))
    return None


def outcome_of(engine: Engine, assistant: Assistant, question: str, call: ToolCall) -> str:
    assistant.clients = {"recorded": Recorded(call)}
    try:
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
        understood = assistant._understand("recorded", messages)  # the unit under replay
    except ProviderError:
        return "FAILS_OVER"
    if understood.clarification is not None:
        return "CLARIFY"
    assert understood.query is not None  # noqa: S101
    return engine.lookup(understood.query).outcome.value


def main(register: str) -> None:
    engine = Engine(Path(register))
    assistant = Assistant(engine, {}, Router(["recorded"]))
    for suite in SUITES:
        items = {}
        for line in (ROOT / "evaluation" / suite / "items.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            items[item["id"]] = item
        n = changed = better = worse = 0
        for path in sorted((ROOT / "evaluation" / suite / "runs" / "first_run").glob("*.json")):
            if path.name.startswith("_"):
                continue
            rec = json.loads(path.read_text(encoding="utf-8"))
            item, call = items.get(rec["id"]), first_call(rec)
            if not item or call is None:
                continue
            n += 1
            res = rec.get("result") or {}
            before = (res.get("answer") or {}).get("outcome") or (
                "CLARIFY" if res.get("clarification") else "FAILS_OVER"
            )
            after = outcome_of(engine, assistant, item["question"], call)
            if after == before:
                continue
            changed += 1
            s = item.get("structured")
            want = None
            if s:
                asked = Query(crop=s["crop"], product=s.get("product"), ingredient=s.get("ingredient"),
                              pest=s.get("pest"))  # fmt: skip
                want = engine.lookup(asked).outcome.value
            verdict = "better" if after == want else ("worse" if before == want else "other")
            better += verdict == "better"
            worse += verdict == "worse"
            print(f"{suite} {item['id']} ({item['part']}): {before} -> {after} (asked: {want}) {verdict}")
        summary = f"{changed} change: {better} to the asked answer, {worse} away from it"
        print(f"== {suite}: {n} recorded calls; {summary}")
    engine.close()


if __name__ == "__main__":
    main(sys.argv[1])
