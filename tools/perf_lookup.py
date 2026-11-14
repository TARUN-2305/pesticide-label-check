"""L2 §7 latency: 1,000 lookups in-process and over HTTP (uvicorn on localhost), 5 runs each.

Queries are sampled with a fixed seed from the register itself: (product heading, crop) pairs that exist,
the same with a pest, and pairs with a crop the product is not approved on. Usage:
    uv run python tools/perf_lookup.py build/m2dev/register.sqlite reports/M2/perf.json
"""

from __future__ import annotations

import json
import platform
import random
import socket
import statistics
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from labelclaim.api.app import Settings, create_app
from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query
from labelclaim.register.writer import open_readonly

N, RUNS, SEED = 1000, 5, 20261114


def sample(register: Path) -> list[Query]:
    conn = open_readonly(register)
    rows = conn.execute(
        "SELECT p.heading_raw, c.crop_id, pe.display_en FROM use_record u JOIN product p ON p.id = u.product_id "
        "JOIN use_record_crop c ON c.use_record_id = u.id LEFT JOIN use_record_pest x ON x.use_record_id = u.id "
        "LEFT JOIN pest pe ON pe.id = x.pest_id ORDER BY u.id, c.crop_id, pe.id"
    ).fetchall()
    crops = [r[0] for r in conn.execute("SELECT display_en FROM crop ORDER BY id")]
    conn.close()
    rng = random.Random(SEED)
    out = []
    for i in range(N):
        heading, crop, pest = rng.choice(rows)
        kind = i % 3
        if kind == 0:
            out.append(Query(product=heading, crop=crop))
        elif kind == 1:
            out.append(Query(product=heading, crop=crop, pest=pest if pest and len(pest) <= 120 else "aphid"))
        else:
            out.append(Query(product=heading, crop=rng.choice(crops)))
    return out


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    register, out = Path(sys.argv[1]), Path(sys.argv[2])
    queries = sample(register)
    engine = Engine(register)
    inproc = []
    for _ in range(RUNS):
        times = []
        for q in queries:
            t0 = time.perf_counter()
            engine.lookup(q)
            times.append((time.perf_counter() - t0) * 1000)
        inproc.append(
            {"p50": pct(times, 50), "p95": pct(times, 95), "p99": pct(times, 99), "max": max(times)}
        )
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(Settings(register=register, rate_per_minute=10**9)),
                                           host="127.0.0.1", port=port, log_level="warning"))  # fmt: skip
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    http = []
    with httpx.Client(base_url=f"http://127.0.0.1:{port}") as client:
        for q in queries[:50]:
            client.post("/v1/lookup", json={k: v for k, v in vars(q).items() if v is not None})  # warm-up
        for _ in range(RUNS):
            times = []
            for q in queries:
                body = {k: v for k, v in vars(q).items() if v is not None}
                t0 = time.perf_counter()
                r = client.post("/v1/lookup", json=body)
                times.append((time.perf_counter() - t0) * 1000)
                assert r.status_code == 200, r.text
            http.append(
                {"p50": pct(times, 50), "p95": pct(times, 95), "p99": pct(times, 99), "max": max(times)}
            )
    server.should_exit = True
    thread.join(timeout=10)
    result = {
        "environment": {"python": platform.python_version(), "machine": platform.processor() or platform.machine(),
                        "system": f"{platform.system()} {platform.release()}"},
        "register": str(register), "queries": N, "runs": RUNS, "seed": SEED,
        "in_process_ms": inproc, "http_ms": http,
        "median_of_runs": {
            "in_process_p50": statistics.median(r["p50"] for r in inproc),
            "in_process_p95": statistics.median(r["p95"] for r in inproc),
            "http_p50": statistics.median(r["p50"] for r in http),
            "http_p95": statistics.median(r["p95"] for r in http),
        },
    }  # fmt: skip
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["median_of_runs"], indent=1))


if __name__ == "__main__":
    main()
