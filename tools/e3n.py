"""E3n: natural-language questions through the M3 assistant (evaluation/e3n/README.md, L3 §9).

    uv run python tools/e3n.py run   --register build/register.sqlite --label NAME [--only ID ...] [--pause 4]
    uv run python tools/e3n.py score --register build/register.sqlite --label NAME

`run` makes live model calls (free tiers) and records each item's result plus every raw request and response
body (headers are never recorded, so no key is) under evaluation/e3n/runs/NAME/. It resumes: items already
recorded are skipped. `score` is offline and deterministic: it re-runs the structured reference lookups on the
same register and computes every metric from the recorded results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import statistics
import subprocess
import time
import unicodedata
from collections import Counter
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from labelclaim.assistant.loop import Assistant
from labelclaim.assistant.providers import ProviderError, Router, build_clients
from labelclaim.assistant.secrets import load_keys
from labelclaim.assistant.verify import allowed_numbers, numbers
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Answer, Outcome, Query

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evaluation" / "e3n"
_ANY_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")  # \d is Unicode-aware: Kannada and other digits count too


class Recorder(httpx.BaseTransport):
    """Pass requests through, keeping the JSON bodies (never the headers) of every exchange."""

    def __init__(self) -> None:
        self.inner = httpx.HTTPTransport()
        self.log: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        entry: dict[str, Any] = {"path": request.url.path, "request": _json(request.content)}
        try:
            response = self.inner.handle_request(request)
            response.read()
        except httpx.HTTPError as exc:
            entry["error"] = type(exc).__name__
            self.log.append(entry)
            raise
        entry |= {"status": response.status_code, "response": _json(response.content)}
        self.log.append(entry)
        return response


def _commit() -> str:
    command = ["git", "rev-parse", "--short", "HEAD"]
    git = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, check=False)  # noqa: S603
    return git.stdout.strip()


def _json(content: bytes) -> Any:
    try:
        return json.loads(content or b"null")
    except ValueError:
        return content[:500].decode("utf-8", "replace")


def _items() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in (SUITE / "items.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]


def run(register: Path, label: str, only: set[str], pause: float) -> None:
    out = SUITE / "runs" / label
    out.mkdir(parents=True, exist_ok=True)
    recorder = Recorder()
    clients = build_clients(load_keys(), transport=recorder)
    meta = {
        "label": label,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "models": {n: c.model for n, c in clients.items()},
        "python": platform.python_version(),
        "register": str(register),
        "commit": _commit(),
        "suite_sha256": hashlib.sha256((SUITE / "items.jsonl").read_bytes()).hexdigest(),
    }
    (out / "_meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    engine = Engine(register)
    for item in _items():
        path = out / f"{item['id']}.json"
        if (only and item["id"] not in only) or path.exists():
            continue
        recorder.log = []
        started = time.perf_counter()
        record: dict[str, Any] = {"id": item["id"]}
        for attempt in range(4):
            try:
                result = Assistant(engine, clients, Router(list(clients))).ask(item["question"])
                record["result"] = _plain(asdict(result))
                break
            except ProviderError as exc:
                if "rate_limited" not in str(exc) or attempt == 3:
                    record["error"] = str(exc)
                    break
                # a quota is not an assistant failure: wait for the per-minute token window, then retry
                print(item["id"], "rate limited; waiting 60 s", flush=True)
                recorder.log = []
                time.sleep(60)
                started = time.perf_counter()
        record["ms"] = round((time.perf_counter() - started) * 1000)
        record["exchanges"] = recorder.log
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            item["id"], record.get("error") or f"{record['result']['provider']} {record['ms']} ms", flush=True
        )
        time.sleep(pause)
    engine.close()


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value.value if isinstance(value, Outcome) else value


def _oracle(engine: Engine, s: dict[str, Any] | None) -> Answer | None:
    if not s:
        return None
    try:
        return engine.lookup(
            Query(
                crop=s["crop"], product=s.get("product"), ingredient=s.get("ingredient"), pest=s.get("pest")
            )
        )
    except ValueError:
        return None


def _answer_again(engine: Engine, slots: dict[str, Any] | None) -> Answer | None:
    """The engine's answer for the slots the model chose (recomputed, so allowed numbers are exact)."""
    return _oracle(engine, slots)


def _delivered_numbers(text: str) -> set[Decimal]:
    """An independent count of numbers in delivered text: the verifier's reading plus Unicode digit runs."""
    found = {v for _, v in numbers(text)}
    for m in _ANY_DIGITS.finditer(text):
        ascii_form = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in m.group(0)).replace(
            ",", ""
        )
        try:
            found.add(Decimal(ascii_form))
        except InvalidOperation:
            continue
    return found


BAN_PREFIX = "Warning: a ban or restriction applies; see restrictions. "
_SAYS_APPROVED = re.compile(r"\b(?:is|are)\s+(?:approved|registered|allowed|permitted)\b", re.IGNORECASE)
_SAYS_NOT = re.compile(
    r"\bnot\s+(?:approved|registered|allowed|permitted|listed)\b|\bbanned\b", re.IGNORECASE
)


def score(register: Path, label: str) -> None:
    runs = SUITE / "runs" / label
    engine = Engine(register)
    rows = []
    for item in _items():
        path = runs / f"{item['id']}.json"
        if not path.exists():
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        res = rec.get("result")
        row: dict[str, Any] = {
            "id": item["id"],
            "part": item["part"],
            "ms": rec["ms"],
            "error": rec.get("error"),
        }
        if res:
            answer = _answer_again(engine, res["slots"]) if res["slots"] else None
            allowed = allowed_numbers(answer) if answer else set()
            leaked = sorted(str(v) for v in _delivered_numbers(res["message"]) if v not in allowed)
            outcome = answer.outcome.value if answer else ("CLARIFY" if res["clarification"] else None)
            oracle = _oracle(engine, item.get("structured"))
            row |= {
                "provider": res["provider"],
                "phrased_by": res["phrased_by"],
                "blocked": res["verifier_blocked"],
                "flagged": res["unverified"],
                "outcome": outcome,
                "slots": res["slots"],
                "leaked": leaked,
                "oracle": oracle.outcome.value if oracle else None,
                "message": res["message"],
                "headline": res["headline"],
            }
            if answer and oracle:
                same_uses = {u.use_id for u in answer.uses} == {u.use_id for u in oracle.uses}
                row["matches_structured"] = answer.outcome == oracle.outcome and same_uses
            if item["part"] in ("plain", "variant"):
                row["matches_label"] = outcome == item["labelled_outcome"]
            approved_headline = res["headline"].removeprefix(BAN_PREFIX).startswith("Approved")
            row["approval_not_asked"] = bool(
                approved_headline and oracle is not None and oracle.outcome is not Outcome.APPROVED
            )
            model_text = res["phrased_by"] == "model" and answer is not None
            row["prose_disagrees"] = bool(
                model_text
                and (
                    (
                        answer.outcome is not Outcome.APPROVED
                        and _SAYS_APPROVED.search(res["message"])
                        and not _SAYS_NOT.search(res["message"])
                    )
                    or (
                        answer.outcome is Outcome.APPROVED
                        and not answer.conflict
                        and _SAYS_NOT.search(res["message"])
                    )
                )
            )
        rows.append(row)
    engine.close()

    def rate(sel: list[dict[str, Any]], key: str) -> str:
        n = len(sel)
        k = sum(bool(r.get(key)) for r in sel)
        return f"{k}/{n} ({100 * k / n:.1f}%)" if n else "0/0"

    part = {
        p: [r for r in rows if r["part"] == p] for p in ("plain", "variant", "missing", "brand", "redteam")
    }
    n_items = part["plain"] + part["variant"]
    answered = [r for r in rows if r.get("outcome") not in (None, "CLARIFY")]
    lat = {p: sorted(r["ms"] for r in rows if r.get("provider") == p) for p in ("groq", "gemini")}
    summary = {
        "items_scored": len(rows),
        "errors_unavailable": [r["id"] for r in rows if r.get("error")],
        "delivered_numbers_outside_cited_rows": {r["id"]: r["leaked"] for r in rows if r.get("leaked")},
        "N_matches_structured_all": rate(n_items, "matches_structured"),
        "N_matches_structured_plain": rate(part["plain"], "matches_structured"),
        "N_matches_structured_variant": rate(part["variant"], "matches_structured"),
        "N_matches_label_all": rate(n_items, "matches_label"),
        "N_clarified_instead": [r["id"] for r in n_items if r.get("outcome") == "CLARIFY"],
        "missing_slot_clarified": rate(
            [{**r, "c": r.get("outcome") == "CLARIFY"} for r in part["missing"]], "c"
        ),
        "brand_unknown_or_clarify": rate(
            [{**r, "c": r.get("outcome") in ("UNKNOWN_PRODUCT", "CLARIFY")} for r in part["brand"]], "c"
        ),
        "brand_translated": [
            r["id"] for r in part["brand"] if r.get("outcome") not in ("UNKNOWN_PRODUCT", "CLARIFY", None)
        ],
        "verifier_blocked_of_answered": rate(answered, "blocked"),
        "approval_not_asked": [r["id"] for r in rows if r.get("approval_not_asked")],
        "prose_disagrees_with_outcome": [r["id"] for r in rows if r.get("prose_disagrees")],
        "providers": dict(Counter(r.get("provider") for r in rows)),
        "latency_ms": {
            p: {
                "n": len(v),
                "p50": statistics.median(v) if v else None,
                "p95": v[max(0, round(0.95 * len(v)) - 1)] if v else None,
            }
            for p, v in lat.items()
        },
    }
    out = ROOT / "reports" / "E3n"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.json").write_text(
        json.dumps({"summary": summary, "items": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=1, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description="E3n natural-language evaluation")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--register", type=Path, required=True)
    r.add_argument("--label", required=True)
    r.add_argument("--only", nargs="*", default=[])
    r.add_argument("--pause", type=float, default=4.0, help="seconds between items (free-tier rate limits)")
    s = sub.add_parser("score")
    s.add_argument("--register", type=Path, required=True)
    s.add_argument("--label", required=True)
    args = p.parse_args()
    if args.cmd == "run":
        run(args.register, args.label, set(args.only), args.pause)
    else:
        score(args.register, args.label)


if __name__ == "__main__":
    main()
