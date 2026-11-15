"""E1: extraction accuracy on a stratified random golden set (docs/evaluation_plan.md, E1).

    uv run python tools/e1.py select --register build/register.sqlite   # sample + page images, no field text
    uv run python tools/e1.py run --register build/register.sqlite \
        --labels evaluation/e1/labels.jsonl --label NAME
    uv run python tools/e1.py agree evaluation/e1/labels.jsonl evaluation/e1/labels_check.jsonl

`select` writes only what a labeller needs to find the row (page, the row outlined on the page image), never
the extracted text, so labels are typed from the page and not copied from the extractor.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image, ImageDraw

from labelclaim.sources import DEFAULT_CACHE, load_manifest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "e1"
SEED = 20261116
STRATA = {
    "insecticide_single": 35,
    "insecticide_combination": 25,
    "fungicide_single": 35,
    "fungicide_combination": 25,
}
MINIMUMS = (("merged", 5), ("page_break", 3), ("free_text", 3))  # per stratum (evaluation plan)
FIELDS = ("product", "crop", "pest", "dose_ai", "dose_form", "dilution", "wait", "page")
DPI = 150
_WS = re.compile(r"\s+")


def _rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    sql = """SELECT u.id, p.section, p.document_id, u.page_first, u.page_last, u.provenance_json,
                    u.dose_ai_json, u.dose_form_json, u.dilution_json, u.wait_raw, u.wait_lo,
                    p.page, p.bbox_json
             FROM use_record u JOIN product p ON p.id = u.product_id ORDER BY u.id"""
    out = []
    for uid, section, doc, first, last, prov, ai, form, dil, wait, wait_lo, ppage, pbox in conn.execute(sql):
        fields = json.loads(prov)["fields"]
        unparsed = any(
            json.loads(q)["status"] != "parsed" and json.loads(q)["kind"] != "empty" for q in (ai, form, dil)
        )
        out.append({
            "use_id": uid, "stratum": section, "doc": doc, "page_first": first, "page_last": last,
            "fields": fields, "fields_rows": json.loads(prov)["rows"], "product_page": ppage,
            "product_bbox": json.loads(pbox),
            "merged": fields["CROP"]["source"] in ("merged", "carried", "blank"),
            "page_break": last != first,
            "free_text": unparsed or (bool(wait.strip()) and wait_lo is None),
        })  # fmt: skip
    return out


def select(
    register: Path,
    out: Path = OUT,
    seed: int = SEED,
    scale: float = 1.0,
    prefix: str = "E1",
    exclude: tuple[Path, ...] = (),
) -> None:
    """Sample rows; `exclude` lists earlier samples whose raw rows must not be drawn again (E1b)."""
    rng = random.Random(seed)
    taken = {(x["doc"], *x["row_ref"]) for path in exclude for x in _load(path).values()}
    rows = _rows(sqlite3.connect(register))
    chosen: list[dict[str, Any]] = []
    for stratum, full in STRATA.items():
        size = round(full * scale)
        pool = [r for r in rows if r["stratum"] == stratum and (r["doc"], *r["fields_rows"][0]) not in taken]
        rng.shuffle(pool)
        picked: list[dict[str, Any]] = []
        for tag, need in MINIMUMS:
            have = sum(r[tag] for r in picked)
            picked += [r for r in pool if r[tag] and r not in picked][: max(0, need - have)]
        picked += [r for r in pool if r not in picked][: size - len(picked)]
        chosen += sorted(picked, key=lambda r: r["use_id"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(exist_ok=True)
    docs = {d.id: DEFAULT_CACHE / f"{d.sha256}.pdf" for d in load_manifest(ROOT / "data" / "sources.toml")}
    pdfs = {k: pdfplumber.open(v) for k, v in docs.items() if k in {r["doc"] for r in chosen}}
    lines = []
    for n, r in enumerate(chosen, start=1):
        item = f"{prefix}-{n:03d}"
        _render(pdfs[r["doc"]], r, out / "images" / f"{item}.png")
        tags = [t for t, _ in MINIMUMS if r[t]]
        lines.append({"item": item, "use_id": r["use_id"], "row_ref": r["fields_rows"][0],
                      "stratum": r["stratum"], "doc": r["doc"], "page_first": r["page_first"],
                      "page_last": r["page_last"], "tags": tags})  # fmt: skip
    (out / "sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    counts = Counter(x["stratum"] for x in lines)
    tags = Counter((x["stratum"], t) for x in lines for t in x["tags"])
    print(
        json.dumps(
            {
                "seed": seed,
                "items": len(lines),
                "strata": counts,
                "tags": {f"{s}:{t}": c for (s, t), c in sorted(tags.items())},
            },
            indent=1,
        )
    )


def _strip(page: Any, top: float, bottom: float, mark: tuple[float, float] | None) -> Image.Image:
    top, bottom = max(0.0, top), min(float(page.height), bottom)
    img = page.crop((0, top, page.width, bottom)).to_image(resolution=DPI).original.convert("RGB")
    if mark is not None:
        s = DPI / 72
        ImageDraw.Draw(img).rectangle(
            (2, (mark[0] - top) * s, img.width - 3, (mark[1] - top) * s), outline=(220, 0, 0), width=3
        )
    return img


def _render(pdf: Any, r: dict[str, Any], path: Path) -> None:
    """The product heading strip, then each page's strip of the row with the row's own cells outlined."""
    strips = []
    hp = pdf.pages[r["product_page"] - 1]
    b = r["product_bbox"]
    strips.append(_strip(hp, b[1] - 3, b[3] + 3, None))
    for page_no in sorted({pg for f in r["fields"].values() for pg, _ in f["boxes"]}):
        boxes = [bb for f in r["fields"].values() for pg, bb in f["boxes"] if pg == page_no]
        own = [  # the row's own pest and value cells: a merged crop cell would cover several rows
            bb
            for col, f in r["fields"].items()
            if col != "CROP" and f["source"] == "cell"
            for pg, bb in f["boxes"]
            if pg == page_no
        ]
        anchor = own or boxes
        mark = (min(x[1] for x in anchor), max(x[3] for x in anchor))
        strips.append(
            _strip(pdf.pages[page_no - 1], min(x[1] for x in boxes) - 18, max(x[3] for x in boxes) + 18, mark)
        )
    width = max(s.width for s in strips)
    canvas = Image.new("RGB", (width, sum(s.height for s in strips) + 8 * len(strips)), "white")
    y = 0
    for s in strips:
        canvas.paste(s, (0, y))
        y += s.height + 8
    canvas.save(path)


def norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _register_rows(register: Path, sample: dict[str, dict[str, Any]]) -> dict[str, dict[str, str] | None]:
    """Each sampled row's use in `register`, found by the raw row it was drawn from (doc, page, table, row),
    not by use id: ids change when a rebuild joins or drops rows. A row joined into another use maps to it."""
    conn = sqlite3.connect(register)
    sql = """SELECT p.document_id, u.provenance_json, p.heading_raw, u.crop_raw, u.pest_raw, u.dose_ai_raw,
                    u.dose_form_raw, u.dilution_raw, u.wait_raw, u.page_first
             FROM use_record u JOIN product p ON p.id = u.product_id"""
    where: dict[tuple[str, int, int, int], dict[str, str]] = {}
    for doc, prov, *values in conn.execute(sql):
        for ref in json.loads(prov)["rows"]:
            where[(doc, *ref)] = dict(zip(FIELDS, map(str, values), strict=True))
    out: dict[str, dict[str, str] | None] = {}
    for item, s in sample.items():
        page, table, row = s["row_ref"]
        # a grid row that is now blank (its only cell was nested in the cell above, L1 §17) belongs to the use
        # of the nearest row above it in the same table
        hits = (where.get((s["doc"], page, table, r)) for r in range(row, -1, -1))
        out[item] = next((h for h in hits if h is not None), None)
    return out


def _load(path: Path) -> dict[str, dict[str, Any]]:
    return {x["item"]: x for x in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if x}


def run(register: Path, labels_path: Path, label: str, sample_path: Path = OUT / "sample.jsonl") -> None:
    sample = _load(sample_path)
    labels = _load(labels_path)
    missing = sorted(set(sample) - set(labels))
    if missing:
        raise SystemExit(f"{len(missing)} items have no label, e.g. {missing[:3]}")
    got = _register_rows(register, sample)
    results = []
    for item, s in sample.items():
        expected = labels[item]["expected"]
        actual = got[item]
        wrong = [f for f in FIELDS if actual is None or norm(str(expected[f])) != norm(actual[f])]
        results.append({"item": item, "use_id": s["use_id"], "stratum": s["stratum"], "wrong": wrong,
                        "expected": expected, "actual": actual})  # fmt: skip
    scored = [r for r in results if labels[r["item"]].get("layout", "standard") == "standard"]
    n = len(scored)
    ok = Counter(f for r in scored for f in FIELDS if f not in r["wrong"])
    row_fields = [
        f for f in FIELDS if f != "page"
    ]  # `page` is correct by construction (the image was cut there)
    summary = {
        "items": len(results),
        "scored_standard_layout": n,
        "non_standard_layout": [r["item"] for r in results if r not in scored],
        "field_accuracy_8": round(sum(ok.values()) / (n * len(FIELDS)), 4),
        "field_accuracy_7": round(sum(ok[f] for f in row_fields) / (n * len(row_fields)), 4),
        "row_accuracy": round(sum(not r["wrong"] for r in scored) / n, 4),
        "per_field": {f: ok[f] for f in FIELDS},
        "rows_wrong": [r["item"] for r in scored if r["wrong"]],
    }
    out = ROOT / "reports" / "E1" / f"{label}.json"
    payload = {"register": str(register), "labels": str(labels_path), "summary": summary, "results": results}
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for r in scored:
        for f in r["wrong"]:
            print(
                f"{r['item']} {f:9} exp {norm(str(r['expected'][f]))!r}\n"
                f"{'':14} got {norm(r['actual'][f]) if r['actual'] else None!r}"
            )


def agree(first: Path, second: Path) -> None:
    a, b = _load(first), _load(second)
    common = sorted(set(a) & set(b))
    pairs = [
        (i, f) for i in common for f in FIELDS if f in b[i]["expected"]
    ]  # the check pass types row fields only
    diffs = [(i, f, a[i]["expected"][f], b[i]["expected"][f]) for i, f in pairs
             if norm(str(a[i]["expected"][f])) != norm(str(b[i]["expected"][f]))]  # fmt: skip
    print(json.dumps({"items": len(common), "fields": len(pairs), "field_disagreements": len(diffs),
                      "agreement": round(1 - len(diffs) / len(pairs), 4)}, indent=1))  # fmt: skip
    for d in diffs:
        print(*d, sep=" | ")


def main() -> None:
    p = argparse.ArgumentParser(description="E1 extraction accuracy")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--register", type=Path, required=True)
    s.add_argument("--out", type=Path, default=OUT)
    s.add_argument("--seed", type=int, default=SEED)
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--prefix", default="E1")
    s.add_argument("--exclude", type=Path, nargs="*", default=[])
    r = sub.add_parser("run")
    r.add_argument("--register", type=Path, required=True)
    r.add_argument("--labels", type=Path, required=True)
    r.add_argument("--label", required=True)
    r.add_argument("--sample", type=Path, default=OUT / "sample.jsonl")
    g = sub.add_parser("agree")
    g.add_argument("first", type=Path)
    g.add_argument("second", type=Path)
    args = p.parse_args()
    if args.cmd == "select":
        select(args.register, args.out, args.seed, args.scale, args.prefix, tuple(args.exclude))
    elif args.cmd == "run":
        run(args.register, args.labels, args.label, args.sample)
    else:
        agree(args.first, args.second)


if __name__ == "__main__":
    main()
