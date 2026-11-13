"""Build orchestration and CLI (L1 §4.1, §9): sources -> extract -> normalise -> validate -> register.

python -m labelclaim.build fetch   [--offline]
python -m labelclaim.build run     [--release] [--offline] [--out build/]
python -m labelclaim.build audit   [--register build/register.sqlite]
python -m labelclaim.build lexicon-draft [--out data/lexicon/crops.draft.csv]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from labelclaim import __doc__ as _pkg_doc  # noqa: F401 - keep the package importable for -m
from labelclaim.errors import AnomalyBudgetExceeded, LabelClaimError, SourceIntegrityError
from labelclaim.extract.assemble import assemble
from labelclaim.extract.model import Anomaly, Col, UseRow
from labelclaim.extract.pages import Reextractor, read_document
from labelclaim.normalize.headings import parse_heading
from labelclaim.normalize.lexicon import CropLexicon, key, load_crops, split_pests, write_draft
from labelclaim.normalize.quantities import parse_quantity, wait_days
from labelclaim.register.writer import open_readonly, write
from labelclaim.restrictions import parse_restrictions
from labelclaim.sources import DEFAULT_CACHE, SourceDocument, ensure_cached, load_manifest
from labelclaim.validate import (
    check_digits,
    check_duplicates,
    check_incomplete,
    check_provenance,
    check_sections,
)

REPO = Path(__file__).resolve().parents[2]
CODE_VERSION = "0.0.1"


@dataclass
class BuildResult:
    build_hash: str
    uses: int
    products: int
    restrictions: int
    anomalies: Counter[str]
    unallowed: list[Anomaly]
    unreviewed_lexicon: int
    unreviewed_allowlist: int
    provenance_checked: int
    seconds: float
    per_document: dict[str, dict[str, Any]] = field(default_factory=dict)


def _allowlist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = data.get("allow", [])
    return [e for e in entries if isinstance(e, dict)]


def _allowed(a: Anomaly, allow: list[dict[str, Any]]) -> bool:
    return any(
        e.get("code") == a.code and e.get("doc") == a.doc_id and e.get("page") == a.page for e in allow
    )


def run(
    sources: Path,
    lexicon_dir: Path,
    out_dir: Path,
    *,
    release: bool = False,
    offline: bool = False,
    cache: Path = DEFAULT_CACHE,
    allowlist: Path | None = None,
) -> BuildResult:
    started = time.perf_counter()
    docs = load_manifest(sources)
    crops_path = lexicon_dir / "crops.csv"
    lexicon = load_crops(crops_path) if crops_path.exists() else CropLexicon(())
    allow = _allowlist(allowlist or sources.parent / "anomaly_allowlist.toml")
    anomalies: list[Anomaly] = []
    all_uses: list[tuple[SourceDocument, UseRow]] = []
    restrictions = []
    provenance = 0
    per_document: dict[str, dict[str, Any]] = {}
    for doc in docs:
        path = ensure_cached(doc, cache, offline=offline)
        if doc.kind == "restrictions":
            restrictions = parse_restrictions(read_document(path, doc.id))
            per_document[doc.id] = {"restrictions": len(restrictions)}
            continue
        assembly = assemble(doc.id, read_document(path, doc.id))
        uses, dupes = check_duplicates(doc.id, assembly.uses)
        anomalies += assembly.anomalies + dupes
        anomalies += check_incomplete(doc.id, uses)
        anomalies += check_sections(doc.id, doc.kind, dict(doc.expected_sections), uses)
        with Reextractor(path) as reader:
            provenance += check_provenance(uses, reader.text)
        all_uses += [(doc, u) for u in uses]
        per_document[doc.id] = {
            "uses": len(uses),
            "products": len(assembly.products),
            "kinds": dict(assembly.kinds),
        }

    tables, crop_unknown = _tables(docs, all_uses, restrictions, lexicon, anomalies, allow)
    anomalies += crop_unknown
    for a in crop_unknown:  # crop anomalies were found while building tables; record them too
        tables["anomaly"].append(
            (
                len(tables["anomaly"]) + 1,
                a.code,
                a.doc_id,
                a.page,
                a.table,
                a.row,
                a.detail,
                int(_allowed(a, allow)),
            )
        )
    unallowed = [a for a in anomalies if not _allowed(a, allow)]
    unreviewed_allow = sum(1 for e in allow if not str(e.get("reviewed_by", "")).strip())
    if release and (unallowed or lexicon.unreviewed or unreviewed_allow):
        raise AnomalyBudgetExceeded(
            f"release build refused: {len(unallowed)} anomalies not allow-listed, "
            f"{len(lexicon.unreviewed)} unreviewed lexicon rows, "
            f"{unreviewed_allow} unreviewed allow-list entries"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {
        "code_version": CODE_VERSION,
        "sources": json.dumps({d.id: d.sha256 for d in docs}, sort_keys=True),
        "release": str(release).lower(),
    }
    build_hash = write(out_dir / "register.sqlite", tables, info)
    result = BuildResult(
        build_hash=build_hash,
        uses=len(all_uses),
        products=len(tables["product"]),
        restrictions=len(restrictions),
        anomalies=Counter(a.code for a in anomalies),
        unallowed=unallowed,
        unreviewed_lexicon=len(lexicon.unreviewed),
        unreviewed_allowlist=unreviewed_allow,
        provenance_checked=provenance,
        seconds=round(time.perf_counter() - started, 2),
        per_document=per_document,
    )
    (out_dir / "anomalies.json").write_text(
        json.dumps(
            [asdict(a) | {"allowed": _allowed(a, allow)} for a in anomalies], indent=1, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {k: v for k, v in asdict(result).items() if k not in ("unallowed", "seconds")}
    manifest["anomalies"] = dict(sorted(result.anomalies.items()))
    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _tables(
    docs: tuple[SourceDocument, ...],
    uses: list[tuple[SourceDocument, UseRow]],
    restrictions: list[Any],
    lexicon: CropLexicon,
    anomalies: list[Anomaly],
    allow: list[dict[str, Any]],
) -> tuple[dict[str, list[tuple[Any, ...]]], list[Anomaly]]:
    """Rows for every table, in canonical order with IDs assigned in that order."""
    tables: dict[str, list[tuple[Any, ...]]] = {name: [] for name in (
        "source_document", "ingredient", "product", "product_ingredient", "crop", "crop_alias", "use_record",
        "use_record_pest", "restriction", "anomaly")}  # fmt: skip
    for d in sorted(docs, key=lambda d: d.id):
        tables["source_document"].append((d.id, d.kind, d.url, d.sha256, d.register_date, d.pages))

    product_ids: dict[tuple[str, int, str, tuple[float, ...]], int] = {}
    ingredients: dict[str, str] = {}
    ordered = sorted(uses, key=lambda du: (du[0].id, du[1].rows))
    for doc, use in ordered:
        p = use.product
        pkey = (doc.id, p.page, p.text, p.bbox)
        if pkey not in product_ids:
            product_ids[pkey] = len(product_ids) + 1
            heading = parse_heading(p.text)
            for ing in heading.ingredients:
                ingredients.setdefault(ing.key, ing.name)
    ingredient_ids = {k: i for i, k in enumerate(sorted(ingredients), start=1)}
    tables["ingredient"] = [(i, k, ingredients[k]) for k, i in ingredient_ids.items()]
    for (doc_id, page, text, bbox), pid in product_ids.items():
        heading = parse_heading(text)
        section = next(
            u.product.section.value
            for d, u in ordered
            if (d.id, u.product.page, u.product.text, u.product.bbox) == (doc_id, page, text, bbox)
        )
        notes = next(
            u.product.notes
            for d, u in ordered
            if (d.id, u.product.page, u.product.text, u.product.bbox) == (doc_id, page, text, bbox)
        )
        tables["product"].append(
            (
                pid,
                doc_id,
                section,
                text,
                heading.formulation,
                heading.status,
                json.dumps(list(notes), ensure_ascii=False),
                page,
                json.dumps(list(bbox)),
            )
        )
        for pos, ing in enumerate(heading.ingredients):
            tables["product_ingredient"].append(
                (pid, pos, ingredient_ids[ing.key], ing.conc, ing.unit, ing.basis)
            )

    crops: dict[str, tuple[str, str]] = {}
    for e in lexicon.entries:
        crops.setdefault(e.canonical_id, (e.display_en, e.category))
        tables["crop_alias"].append((key(e.alias), e.lang, e.canonical_id, e.reviewed_by))
    tables["crop"] = [(cid, display, cat) for cid, (display, cat) in sorted(crops.items())]
    tables["crop_alias"] = sorted(set(tables["crop_alias"]))

    unknown: list[Anomaly] = []
    for uid, (doc, use) in enumerate(ordered, start=1):
        f = use.fields
        matches = {e.canonical_id for e in lexicon.resolve(f[Col.CROP].text)}
        crop_id = matches.pop() if len(matches) == 1 else None
        if crop_id is None:
            page, table, row = use.rows[0]
            unknown.append(Anomaly("UNKNOWN_CROP", doc.id, page, table, row, f[Col.CROP].text))
        quantities = {
            c: parse_quantity(f[c].text) for c in (Col.DOSE_AI, Col.DOSE_FORM, Col.DILUTION, Col.WAIT)
        }
        for q in quantities.values():
            check_digits(q)
        days = wait_days(f[Col.WAIT].text)
        provenance = {
            "rows": [list(r) for r in use.rows],
            "fields": {c.name: {"source": fl.source, "boxes": [[pg, list(b)] for pg, b in fl.bboxes],
                                "origin": list(fl.origin) if fl.origin else None,
                                "span_of": fl.span_of.name if fl.span_of else None} for c, fl in f.items()},
        }  # fmt: skip
        p = use.product
        tables["use_record"].append((
            uid, product_ids[(doc.id, p.page, p.text, p.bbox)], crop_id, f[Col.CROP].text, f[Col.PEST].text,
            f[Col.DOSE_AI].text, f[Col.DOSE_FORM].text, f[Col.DILUTION].text, f[Col.WAIT].text,
            _q(quantities[Col.DOSE_AI]), _q(quantities[Col.DOSE_FORM]), _q(quantities[Col.DILUTION]),
            days[0] if days else None, days[1] if days else None, use.page_first, use.page_last,
            json.dumps(provenance, ensure_ascii=False, sort_keys=True),
            json.dumps(list(use.notes), ensure_ascii=False),
        ))  # fmt: skip
        for pest in split_pests(f[Col.PEST].text):
            tables["use_record_pest"].append((uid, pest))
    tables["use_record_pest"] = sorted(set(tables["use_record_pest"]))
    for rid, r in enumerate(sorted(restrictions, key=lambda r: (r.status, r.key, r.page)), start=1):
        tables["restriction"].append((rid, r.key, r.name_raw, r.status, r.detail_raw, r.page))
    for aid, a in enumerate(
        sorted(anomalies, key=lambda a: (a.doc_id, a.page, a.table, a.row, a.code)), start=1
    ):
        tables["anomaly"].append(
            (aid, a.code, a.doc_id, a.page, a.table, a.row, a.detail, int(_allowed(a, allow)))
        )
    return tables, unknown


def _q(q: Any) -> str:
    return json.dumps(
        {"kind": q.kind, "lo": list(q.lo), "hi": list(q.hi), "unit": q.unit, "status": q.status}
    )


def audit(register: Path) -> dict[str, Any]:
    conn = open_readonly(register)

    def one(sql: str) -> Any:
        return conn.execute(sql).fetchone()[0]

    try:
        return {
            "build_hash": one("SELECT value FROM build_info WHERE key='build_hash'"),
            "uses": one("SELECT count(*) FROM use_record"),
            "uses_with_crop_id": one("SELECT count(*) FROM use_record WHERE crop_id IS NOT NULL"),
            "products": one("SELECT count(*) FROM product"),
            "products_parsed": one("SELECT count(*) FROM product WHERE parse_status='parsed'"),
            "ingredients": one("SELECT count(*) FROM ingredient"),
            "restrictions": one("SELECT count(*) FROM restriction"),
            "anomalies": dict(
                conn.execute("SELECT code, count(*) FROM anomaly GROUP BY code ORDER BY code").fetchall()
            ),
            "anomalies_not_allowed": one("SELECT count(*) FROM anomaly WHERE allowed = 0"),
        }
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m labelclaim.build")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "run", "lexicon-draft"):
        p = sub.add_parser(name)
        p.add_argument("--sources", type=Path, default=REPO / "data" / "sources.toml")
        p.add_argument("--offline", action="store_true")
        p.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
        if name == "run":
            p.add_argument("--lexicon", type=Path, default=REPO / "data" / "lexicon")
            p.add_argument("--out", type=Path, default=REPO / "build")
            p.add_argument("--release", action="store_true")
        if name == "lexicon-draft":
            p.add_argument("--out", type=Path, default=REPO / "data" / "lexicon" / "crops.draft.csv")
    a = sub.add_parser("audit")
    a.add_argument("--register", type=Path, default=REPO / "build" / "register.sqlite")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "fetch":
            for doc in load_manifest(args.sources):
                print(doc.id, ensure_cached(doc, args.cache, offline=args.offline))
        elif args.cmd == "run":
            result = run(
                args.sources,
                args.lexicon,
                args.out,
                release=args.release,
                offline=args.offline,
                cache=args.cache,
            )
            summary = json.loads((args.out / "build_manifest.json").read_text(encoding="utf-8"))
            summary |= {"seconds": result.seconds, "unallowed": [asdict(a) for a in result.unallowed][:20]}
            print(json.dumps(summary, indent=1, ensure_ascii=False))
        elif args.cmd == "audit":
            print(json.dumps(audit(args.register), indent=1))
        elif args.cmd == "lexicon-draft":
            crops = []
            for doc in load_manifest(args.sources):
                if doc.kind != "restrictions":
                    path = ensure_cached(doc, args.cache, offline=args.offline)
                    crops += [
                        u.fields[Col.CROP].text for u in assemble(doc.id, read_document(path, doc.id)).uses
                    ]
            print(
                f"{write_draft(crops, args.out)} distinct crop strings -> {args.out} (reviewed_by is empty)"
            )
    except SourceIntegrityError as exc:
        print(f"integrity error: {exc}", file=sys.stderr)
        return 3
    except AnomalyBudgetExceeded as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except LabelClaimError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
