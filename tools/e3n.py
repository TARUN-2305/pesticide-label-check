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
from labelclaim.assistant.verify import numbers
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Answer, Outcome, Query

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evaluation" / "e3n"  # --suite e3nb switches to evaluation/e3nb
# Unicode \d, so Kannada digits count too
_ANY_DIGITS = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?(?![\d¼½¾⅓⅔⅛⅜⅝⅞])")
# (a digit run before a vulgar fraction is one number, "3½"; the verifier reads it whole. Fixed 2026-11-18
# after E3n-e NE-008 was counted as "3"; every suite re-scored.)


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


def run(register: Path, label: str, only: set[str], pause: float, providers: tuple[str, ...] = ()) -> None:
    out = SUITE / "runs" / label
    out.mkdir(parents=True, exist_ok=True)
    recorder = Recorder()
    clients = build_clients(load_keys(), transport=recorder)
    if providers:  # e.g. --providers gemini: test the fallback on its own
        clients = {n: c for n, c in clients.items() if n in providers}
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


def _allowed_from_record(shown: dict[str, Any]) -> set[Decimal]:
    """allowed_numbers() over the recorded answer: rows, alternatives, restrictions and register dates."""
    texts = list(shown["register"]["dates"].values())
    for u in (*shown["uses"], *shown["alternatives"]):
        texts += [u["product_heading"], u["crop_raw"], u["pest_raw"], u["dose_ai_raw"], u["dose_form_raw"],
                  u["dilution_raw"], u["wait_raw"], u["citation"]["register_date"],
                  str(u["citation"]["page_first"]), str(u["citation"]["page_last"])]  # fmt: skip
    for r in shown["restrictions"]:
        texts += [r["ingredient"], r["detail_raw"], str(r["page"])]
    return {v for t in texts for _, v in numbers(t)}


def _canonical_strengths(engine: Engine, typed: str) -> set[Decimal]:
    """Typed numbers that equal a strength in the canonical heading the typed name resolves to."""
    resolved = engine.names.product(typed, ingredient_level=False)
    if not typed or resolved.status != "exact":
        return set()
    canonical = {v for pid in resolved.product_ids for _, v in numbers(engine.names.heading[pid])}
    return {v for _, v in numbers(typed)} & canonical


def _slot_repairs(rec: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    """Where the code overrode the model's reading: fix A (E3n-d) replaced the crop the model first passed;
    fix B (E3n-e) answered although the model asked a question."""
    model_crop = _model_crop(rec)
    used_crop = (res["slots"] or {}).get("crop")
    replaced = bool(model_crop and used_crop and model_crop != used_crop)
    return {
        "crop_replaced": replaced,
        "model_crop": model_crop,
        "clarification_overridden": (
            _first_tool(rec) == "ask_clarifying_question" and res["answer"] is not None
        ),
        "rejected_crop_in_prose": bool(
            replaced and res["phrased_by"] == "model" and _squash(str(model_crop)) in _squash(res["message"])
        ),
    }


def _first_tool(rec: dict[str, Any]) -> str | None:
    """The name of the first tool the model called, from the recorded response bodies."""
    for ex in rec.get("exchanges", []):
        try:
            calls = ex["response"]["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            continue
        if calls:
            return str(calls[0].get("function", {}).get("name"))
    return None


def _model_crop(rec: dict[str, Any]) -> str | None:
    """The crop in the model's first lookup call, from the recorded response body."""
    for ex in rec.get("exchanges", []):
        try:
            calls = ex["response"]["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            continue
        for call in calls:
            if call.get("function", {}).get("name") == "lookup":
                try:
                    crop = json.loads(call["function"]["arguments"]).get("crop")
                except (ValueError, AttributeError):
                    return None
                return str(crop).strip() if crop else None
    return None


def _squash(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def _conflict(shown: dict[str, Any]) -> bool:
    return any(
        r["names_the_crop"] or r["status"] in ("banned", "banned_for_use", "withdrawn")
        for r in shown["restrictions"]
    )


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
            shown = res["answer"]  # scored as recorded: what the user saw, not what today's code would return
            allowed = _allowed_from_record(shown) if shown else set()
            leaked = sorted(str(v) for v in _delivered_numbers(res["message"]) if v not in allowed)
            # L3 amendment (E3n fix 5): the user's own product strength, when the register knows the product
            typed = (res["slots"] or {}).get("product") or ""
            known = shown is not None and shown["outcome"] != "UNKNOWN_PRODUCT"
            strengths = _canonical_strengths(engine, typed) if known else set()  # exact matching (L3 §14)
            leaked_policy = sorted(x for x in leaked if Decimal(x) not in strengths)
            outcome = shown["outcome"] if shown else ("CLARIFY" if res["clarification"] else None)
            oracle = _oracle(engine, item.get("structured"))
            row |= {
                "provider": res["provider"],
                "phrased_by": res["phrased_by"],
                "blocked": res["verifier_blocked"],
                "flagged": res["unverified"],
                "outcome": outcome,
                "slots": res["slots"],
                "leaked": leaked,
                "leaked_beyond_product_name": leaked_policy,
                "oracle": oracle.outcome.value if oracle else None,
                "message": res["message"],
                "headline": res["headline"],
            }
            if shown and oracle:
                same_uses = {u["use_id"] for u in shown["uses"]} == {u.use_id for u in oracle.uses}
                row["matches_structured"] = shown["outcome"] == oracle.outcome.value and same_uses
            if item["part"] in ("plain", "variant", "control", "probe"):
                row["matches_label"] = outcome == item["labelled_outcome"]
            row |= _slot_repairs(rec, res)
            approved_headline = res["headline"].removeprefix(BAN_PREFIX).startswith("Approved")
            row["approval_not_asked"] = bool(
                approved_headline and oracle is not None and oracle.outcome is not Outcome.APPROVED
            )
            # Added 2026-11-18 after E3n-c NC-034 ("bende" = okra, sent as brinjal): the check above misses
            # an approval for the wrong crop when the asked crop happens to be approved too. This one compares
            # the approved rows shown with the rows the question asks for.
            row["approval_for_other_rows"] = bool(
                approved_headline and oracle is not None and row.get("matches_structured") is False
            )
            model_text = res["phrased_by"] == "model" and shown is not None
            approved, conflict = (
                bool(shown and shown["outcome"] == "APPROVED"),
                bool(shown and _conflict(shown)),
            )
            row["prose_disagrees"] = bool(
                model_text
                and (
                    (
                        not approved
                        and _SAYS_APPROVED.search(res["message"])
                        and not _SAYS_NOT.search(res["message"])
                    )
                    or (approved and not conflict and _SAYS_NOT.search(res["message"]))
                )
            )
        rows.append(row)
    engine.close()

    def rate(sel: list[dict[str, Any]], key: str) -> str:
        n = len(sel)
        k = sum(bool(r.get(key)) for r in sel)
        return f"{k}/{n} ({100 * k / n:.1f}%)" if n else "0/0"

    part = {
        p: [r for r in rows if r["part"] == p]
        for p in ("plain", "variant", "control", "probe", "twocrop", "missing", "brand", "redteam")
    }
    n_items = part["plain"] + part["variant"] + part["control"]  # control: E3n-d only
    answered = [r for r in rows if r.get("outcome") not in (None, "CLARIFY")]
    lat = {p: sorted(r["ms"] for r in rows if r.get("provider") == p) for p in ("groq", "gemini")}
    summary = {
        "items_scored": len(rows),
        "errors_unavailable": [r["id"] for r in rows if r.get("error")],
        "delivered_numbers_outside_cited_rows_strict": {
            r["id"]: r["leaked"] for r in rows if r.get("leaked")
        },
        "delivered_numbers_outside_cited_rows_and_product_name": {
            r["id"]: r["leaked_beyond_product_name"] for r in rows if r.get("leaked_beyond_product_name")
        },
        "N_matches_structured_all": rate(n_items, "matches_structured"),
        "N_matches_structured_plain": rate(part["plain"], "matches_structured"),
        "N_matches_structured_variant": rate(part["variant"], "matches_structured"),
        "N_matches_structured_control": rate(part["control"], "matches_structured"),
        "probe_matches_structured": rate(part["probe"], "matches_structured"),
        "crop_replaced": {r["id"]: r["model_crop"] for r in rows if r.get("crop_replaced")},
        "rejected_crop_in_prose": [r["id"] for r in rows if r.get("rejected_crop_in_prose")],
        "clarification_overridden": [r["id"] for r in rows if r.get("clarification_overridden")],
        "twocrop": {r["id"]: r.get("outcome") for r in part["twocrop"]},
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
        "approval_for_other_rows": [r["id"] for r in rows if r.get("approval_for_other_rows")],
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
    out = ROOT / "reports" / ("E3n" + SUITE.name.removeprefix("e3n"))  # one folder per suite: labels repeat
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
    r.add_argument("--providers", nargs="*", default=[], help="use only these providers, e.g. gemini")
    s = sub.add_parser("score")
    s.add_argument("--register", type=Path, required=True)
    s.add_argument("--label", required=True)
    p.add_argument(
        "--suite",
        default="e3n",
        choices=sorted(d.parent.name for d in (ROOT / "evaluation").glob("e3n*/items.jsonl")),
    )
    args = p.parse_args()
    global SUITE  # noqa: PLW0603 (one CLI switch for the whole run)
    SUITE = ROOT / "evaluation" / args.suite
    if args.cmd == "run":
        run(args.register, args.label, set(args.only), args.pause, tuple(args.providers))
    else:
        score(args.register, args.label)


if __name__ == "__main__":
    main()
