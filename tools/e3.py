"""E3: lookup correctness on queries written from the register pages (docs/evaluation_plan.md, E3).

    uv run python tools/e3.py select   # candidates.jsonl -> queries.jsonl (the 150) + extra.jsonl (seeded)
    uv run python tools/e3.py run --register build/release2/register.sqlite --label first_run

`run` resolves each expected row from its page description (document, page, heading, crop and pest text
as printed), runs the engine once per query, and writes every item's result to reports/E3/<label>.json.
It never changes a query or an expectation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query
from labelclaim.normalize.ingredients import compact
from labelclaim.register.writer import open_readonly

REPO = Path(__file__).resolve().parents[1]
SUITE = REPO / "evaluation" / "e3"
SEED = 20261114
STRATA = {  # evaluation plan E3, fixed before any run
    "APPROVED": 60,
    "NOT_APPROVED_FOR_CROP": 30,
    "NOT_APPROVED_FOR_PEST": 20,
    "UNKNOWN_PRODUCT": 10,
    "UNKNOWN_CROP": 10,
    "AMBIGUOUS": 10,
    "restriction overlay": 10,
}
SAMPLED = ("APPROVED", "NOT_APPROVED_FOR_CROP", "NOT_APPROVED_FOR_PEST")
NOT_APPROVED = ("NOT_APPROVED_FOR_CROP", "NOT_APPROVED_FOR_PEST")


def norm(text: str) -> str:
    return " ".join(text.split()).casefold()


# -- selection ---------------------------------------------------------------------------------------------
def select(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The 150-query suite: a seeded sample from each page-written pool, the fixed strata whole.
    Everything not drawn goes to the extra set, which is run and reported separately."""
    rng = random.Random(SEED)
    core: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []
    for pool, size in STRATA.items():
        items = [c for c in candidates if c["pool"] == pool]
        if pool in SAMPLED:
            chosen = set(rng.sample(range(len(items)), size))
        else:
            if len(items) != size:
                raise SystemExit(f"{pool}: {len(items)} candidates, the plan fixes {size}")
            chosen = set(range(size))
        for i, item in enumerate(items):
            (core if i in chosen else extra).append(item)
    extra += [c for c in candidates if c["pool"] == "extra"]
    for i, item in enumerate(core, 1):
        item["id"] = f"E3-{i:03d}"
    for i, item in enumerate(extra, 1):
        item["id"] = f"X-{i:02d}"
    return core, extra


# -- evaluation --------------------------------------------------------------------------------------------
def resolve_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> tuple[set[int], list[str]]:
    """Use-record ids for page descriptions. A description must match exactly `n` rows; any other count is
    reported as a problem (an extraction or labelling error), never silently accepted."""
    ids: set[int] = set()
    problems: list[str] = []
    for desc in rows:
        found = [
            uid
            for uid, heading, crop, pest in conn.execute(
                "SELECT u.id, p.heading_raw, u.crop_raw, u.pest_raw FROM use_record u "
                "JOIN product p ON p.id = u.product_id JOIN source_document d ON d.id = p.document_id "
                "WHERE d.kind = ? AND u.page_first = ?",
                (desc["doc"], desc["page"]),
            )
            if norm(heading).startswith(norm(desc["heading"]))
            and norm(crop).startswith(norm(desc["crop"]))
            and ("pest" not in desc or norm(desc["pest"]) in norm(pest))
        ]
        if len(found) != desc["n"]:
            where = f"{desc['doc']} p.{desc['page']} {desc['crop']}/{desc.get('pest')}"
            problems.append(f"{where}: {len(found)} rows")
        ids.update(found)
    return ids, problems


def evaluate(engine: Engine, conn: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    expect = item["expect"]
    answer = engine.lookup(Query(**item["query"]))
    got = answer.outcome.value
    expected_ids, problems = resolve_rows(conn, expect["rows"])
    used = {u.use_id for u in answer.uses}
    restrictions = sorted({compact(r.ingredient) for r in answer.restrictions})
    wanted = sorted({compact(r) for r in expect["restrictions"]})
    result: dict[str, Any] = {
        "id": item["id"],
        "stratum": item["pool"],
        "query": item["query"],
        "expected": expect["outcome"],
        "got": got,
        "outcome_ok": got == expect["outcome"],
        "expected_use_ids": sorted(expected_ids),
        "got_use_ids": sorted(used),
        "rows_ok": used == expected_ids if expect["outcome"] == "APPROVED" else not used,
        "descriptor_problems": problems,
        "restrictions_expected": wanted,
        "restrictions_got": restrictions,
        "restrictions_ok": restrictions == wanted,
        "conflict_expected": expect["conflict"],
        "conflict_got": answer.conflict,
        "conflict_ok": answer.conflict == expect["conflict"],
        "safety_critical": got == "APPROVED" and expect["outcome"] in NOT_APPROVED,
        "missed_conflict": expect["conflict"] and not answer.conflict,
        "suggestions": {k: [s.display for s in v] for k, v in answer.suggestions.items()},
        "alternatives": len(answer.alternatives),
    }
    return result


def bootstrap_ci(flags: list[bool], rounds: int = 10_000) -> tuple[float, float]:
    rng = random.Random(SEED)
    n = len(flags)
    means = sorted(sum(rng.choices(flags, k=n)) / n for _ in range(rounds))
    return means[int(0.025 * rounds)], means[int(0.975 * rounds) - 1]


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by[r["stratum"]].append(r)
    approved = [r for r in results if r["expected"] == "APPROVED"]
    tp = sum(len(set(r["got_use_ids"]) & set(r["expected_use_ids"])) for r in approved)
    returned = sum(len(r["got_use_ids"]) for r in approved)
    expected = sum(len(r["expected_use_ids"]) for r in approved)
    flags = [r["outcome_ok"] for r in results]
    lo, hi = bootstrap_ci(flags) if flags else (0.0, 0.0)
    return {
        "n": len(results),
        "outcome_correct": sum(flags),
        "outcome_accuracy": round(sum(flags) / len(flags), 4) if flags else None,
        "outcome_accuracy_ci95": [round(lo, 4), round(hi, 4)],
        "by_stratum": {s: f"{sum(r['outcome_ok'] for r in rs)}/{len(rs)}" for s, rs in by.items()},
        "approved_rows": {
            "queries": len(approved),
            "exact_set": sum(r["rows_ok"] for r in approved),
            "precision": round(tp / returned, 4) if returned else None,
            "recall": round(tp / expected, 4) if expected else None,
        },
        "descriptor_problems": sum(bool(r["descriptor_problems"]) for r in results),
        "restrictions_ok": f"{sum(r['restrictions_ok'] for r in results)}/{len(results)}",
        "conflict_ok": f"{sum(r['conflict_ok'] for r in results)}/{len(results)}",
        "safety_critical": [r["id"] for r in results if r["safety_critical"]],
        "missed_conflicts": [r["id"] for r in results if r["missed_conflict"]],
        "confusion": dict(Counter(f"{r['expected']} -> {r['got']}" for r in results if not r["outcome_ok"])),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment() -> dict[str, str]:
    cpu = (
        next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            platform.processor(),
        )
        if Path("/proc/cpuinfo").exists()
        else platform.processor()
    )
    return {
        "os": platform.platform(),
        "cpu": cpu,
        "python": platform.python_version(),
        "uv_lock_sha256": sha256(REPO / "uv.lock"),
    }


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(items: list[dict[str, Any]], path: Path) -> None:
    path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("select")
    run = sub.add_parser("run")
    run.add_argument("--register", type=Path, required=True)
    run.add_argument("--label", required=True)
    run.add_argument("--suite", choices=("queries", "extra", "e3b"), default="queries")
    args = parser.parse_args(argv)

    if args.command == "select":
        core, extra = select(load(SUITE / "candidates.jsonl"))
        counts = Counter(i["pool"] for i in core)
        if dict(counts) != STRATA:
            raise SystemExit(f"strata {dict(counts)} != plan {STRATA}")
        write_jsonl(core, SUITE / "queries.jsonl")
        write_jsonl(extra, SUITE / "extra.jsonl")
        print(json.dumps({"queries": len(core), "extra": len(extra), "strata": counts}, indent=1))
        return 0

    suite = SUITE / f"{args.suite}.jsonl"
    items = load(suite)
    engine = Engine(args.register)
    conn = open_readonly(args.register)
    results = [evaluate(engine, conn, item) for item in items]
    info = engine.register_info()
    report = {
        "evaluation": "E3",
        "label": args.label,
        "suite": args.suite,
        "date_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": " ".join(["tools/e3.py", *argv]),
        "environment": environment(),
        "inputs": {
            "suite_sha256": sha256(suite),
            "register_sha256": sha256(args.register),
            "register_build_hash": info.build_hash,
            "register_release": info.release,
        },
        "summary": summarise(results),
        "results": results,
    }
    out = REPO / "reports" / "E3" / f"{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))
    for r in results:
        if not (r["outcome_ok"] and r["rows_ok"] and r["restrictions_ok"] and r["conflict_ok"]):
            print(
                f"{r['id']} {r['stratum']:<22} exp {r['expected']:<22} got {r['got']:<22} "
                f"rows {'ok' if r['rows_ok'] else 'X'} restr {'ok' if r['restrictions_ok'] else 'X'} "
                f"conflict {'ok' if r['conflict_ok'] else 'X'} {r['descriptor_problems'] or ''} {r['query']}"
            )
    engine.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
