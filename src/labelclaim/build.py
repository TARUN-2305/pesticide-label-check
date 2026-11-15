"""Build orchestration and CLI (L1 §4.1, §9; L2 §11): sources -> extract -> normalise -> validate -> register.

python -m labelclaim.build fetch   [--offline]
python -m labelclaim.build run     [--release] [--offline] [--out build/]
python -m labelclaim.build audit   [--register build/register.sqlite]
python -m labelclaim.build lexicon-draft --what crops|pests|ingredients --out PATH
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

from labelclaim.corrections import Applied, Correction, apply_corrections, covered, load_corrections
from labelclaim.errors import AnomalyBudgetExceeded, LabelClaimError, SourceIntegrityError
from labelclaim.extract.assemble import assemble
from labelclaim.extract.model import Anomaly, Col, UseRow
from labelclaim.extract.pages import Reextractor, read_document
from labelclaim.normalize.generic import GenericTerm, expand, load_generic
from labelclaim.normalize.headings import parse_heading
from labelclaim.normalize.ingredients import Variants, draft_variants, load_variants, write_variants
from labelclaim.normalize.lexicon import CropLexicon, key, load_crops, write_draft
from labelclaim.normalize.pests import IGNORE, PestLexicon, draft_pests, load_pests, pest_phrases, write_pests
from labelclaim.normalize.quantities import parse_quantity, wait_days
from labelclaim.register.writer import open_readonly, write
from labelclaim.restrictions import Restriction, parse_restrictions
from labelclaim.sources import DEFAULT_CACHE, SourceDocument, ensure_cached, load_manifest
from labelclaim.validate import (
    check_digits,
    check_duplicates,
    check_incomplete,
    check_provenance,
    check_sections,
)

REPO = Path(__file__).resolve().parents[2]
CODE_VERSION = "0.2.0"  # schema v4: reviewed corrections (ADR-007); v3 general names; v2 L2 §11
Rows = dict[str, list[tuple[Any, ...]]]
Extracted = tuple[
    list[tuple[SourceDocument, UseRow]],
    list[Restriction],
    list[Anomaly],
    int,
    dict[str, dict[str, Any]],
    Applied,
]


@dataclass(frozen=True)
class Lexicons:
    crops: CropLexicon
    pests: PestLexicon
    variants: Variants
    generic: tuple[GenericTerm, ...] = ()

    @classmethod
    def load(cls, directory: Path) -> Lexicons:
        crops = directory / "crops.csv"
        pests = directory / "pests.csv"
        return cls(
            load_crops(crops) if crops.exists() else CropLexicon(()),
            load_pests(pests) if pests.exists() else PestLexicon(()),
            load_variants(directory / "ingredients.csv"),
            load_generic(directory / "generic_terms.csv"),
        )

    def unreviewed(self) -> dict[str, int]:
        return {
            "crops": len(self.crops.unreviewed),
            "pests": len(self.pests.unreviewed),
            "ingredients": len(self.variants.unreviewed),
            "generic_terms": sum(1 for t in self.generic if not t.reviewed_by),
        }


@dataclass
class BuildResult:
    build_hash: str
    uses: int
    products: int
    restrictions: int
    anomalies: Counter[str]
    unallowed: list[Anomaly]
    unreviewed: dict[str, int]
    unreviewed_allowlist: int
    corrections_applied: int
    unreviewed_corrections: int
    provenance_checked: int
    seconds: float
    per_document: dict[str, dict[str, Any]] = field(default_factory=dict)


def _allowlist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = tomllib.loads(path.read_text(encoding="utf-8")).get("allow", [])
    return [e for e in entries if isinstance(e, dict)]


def _allowed(a: Anomaly, allow: list[dict[str, Any]]) -> bool:
    """An entry allows (code, doc, page); with a `detail`, only the anomaly with exactly that text."""
    return any(
        e.get("code") == a.code
        and e.get("doc") == a.doc_id
        and e.get("page") == a.page
        and e.get("detail", a.detail) == a.detail
        for e in allow
    )


def release_blockers(
    unallowed: int, unreviewed: dict[str, int], unreviewed_allow: int, unreviewed_fix: int
) -> list[str]:
    """Why a release build must refuse (I8, ADR-006, ADR-007); empty when it may proceed."""
    out = []
    if unallowed:
        out.append(f"{unallowed} anomalies not allow-listed or corrected")
    if any(unreviewed.values()):
        out.append(f"unreviewed lexicon rows {unreviewed}")
    if unreviewed_allow:
        out.append(f"{unreviewed_allow} unreviewed allow-list entries")
    if unreviewed_fix:
        out.append(f"{unreviewed_fix} unreviewed corrections")
    return out


def extract_all(
    docs: tuple[SourceDocument, ...], cache: Path, *, offline: bool, corrections: tuple[Correction, ...] = ()
) -> Extracted:
    """Extract and validate every source document (the build plane up to normalisation).

    I3 (provenance) is checked on the extractor's own output, before reviewed corrections are applied:
    it tests the extractor, and a corrected field is by definition not what the boxes hold (ADR-007)."""
    uses_all: list[tuple[SourceDocument, UseRow]] = []
    restrictions: list[Restriction] = []
    anomalies: list[Anomaly] = []
    provenance = 0
    per_document: dict[str, dict[str, Any]] = {}
    applied: Applied = {}
    for doc in docs:
        path = ensure_cached(doc, cache, offline=offline)
        if doc.kind == "restrictions":
            restrictions = parse_restrictions(read_document(path, doc.id))
            per_document[doc.id] = {"restrictions": len(restrictions)}
            continue
        assembly = assemble(doc.id, read_document(path, doc.id))
        with Reextractor(path) as reader:
            provenance += check_provenance(assembly.uses, reader.text)
        corrected, done = apply_corrections(doc.id, assembly.uses, corrections)
        applied |= done
        uses, dupes = check_duplicates(doc.id, corrected)
        anomalies += assembly.anomalies + dupes
        anomalies += check_incomplete(doc.id, uses)
        anomalies += check_sections(doc.id, doc.kind, dict(doc.expected_sections), uses)
        uses_all += [(doc, u) for u in uses]
        per_document[doc.id] = {
            "uses": len(uses),
            "products": len(assembly.products),
            "kinds": dict(assembly.kinds),
            "corrections": len(done),
        }
    return uses_all, restrictions, anomalies, provenance, per_document, applied


def run(
    sources: Path,
    lexicon_dir: Path,
    out_dir: Path,
    *,
    release: bool = False,
    offline: bool = False,
    cache: Path = DEFAULT_CACHE,
    allowlist: Path | None = None,
    corrections_file: Path | None = None,
) -> BuildResult:
    started = time.perf_counter()
    docs = load_manifest(sources)
    lexicons = Lexicons.load(lexicon_dir)
    allow = _allowlist(allowlist or sources.parent / "anomaly_allowlist.toml")
    corrections = load_corrections(corrections_file or sources.parent / "corrections.toml")
    uses, restrictions, anomalies, provenance, per_document, applied = extract_all(
        docs, cache, offline=offline, corrections=corrections
    )
    tables, name_anomalies = build_tables(docs, uses, restrictions, lexicons)
    ordered = sorted(
        anomalies + name_anomalies, key=lambda a: (a.doc_id, a.page, a.table, a.row, a.code, a.detail)
    )

    def ok(a: Anomaly) -> bool:
        return _allowed(a, allow) or covered(a, corrections, applied)

    tables["anomaly"] = [
        (i, a.code, a.doc_id, a.page, a.table, a.row, a.detail, int(ok(a)))
        for i, a in enumerate(ordered, start=1)
    ]
    unallowed = [a for a in ordered if not ok(a)]
    unreviewed = lexicons.unreviewed()
    unreviewed_allow = sum(1 for e in allow if not str(e.get("reviewed_by", "")).strip())
    unreviewed_fix = sum(1 for c in corrections if not c.reviewed)
    blockers = release_blockers(len(unallowed), unreviewed, unreviewed_allow, unreviewed_fix)
    if release and blockers:
        raise AnomalyBudgetExceeded("release build refused: " + "; ".join(blockers))
    out_dir.mkdir(parents=True, exist_ok=True)
    info = {
        "code_version": CODE_VERSION,
        "sources": json.dumps({d.id: d.sha256 for d in docs}, sort_keys=True),
        "release": str(release).lower(),
    }
    build_hash = write(out_dir / "register.sqlite", tables, info)
    result = BuildResult(
        build_hash=build_hash,
        uses=len(uses),
        products=len(tables["product"]),
        restrictions=len(restrictions),
        anomalies=Counter(a.code for a in ordered),
        unallowed=unallowed,
        unreviewed=unreviewed,
        unreviewed_allowlist=unreviewed_allow,
        corrections_applied=len(applied),
        unreviewed_corrections=unreviewed_fix,
        provenance_checked=provenance,
        seconds=round(time.perf_counter() - started, 2),
        per_document=per_document,
    )
    listing = [asdict(a) | {"allowed": ok(a)} for a in ordered]
    (out_dir / "anomalies.json").write_text(
        json.dumps(listing, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {k: v for k, v in asdict(result).items() if k not in ("unallowed", "seconds")}
    manifest["anomalies"] = dict(sorted(result.anomalies.items()))
    (out_dir / "build_manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def build_tables(
    docs: tuple[SourceDocument, ...],
    uses: list[tuple[SourceDocument, UseRow]],
    restrictions: list[Restriction],
    lexicons: Lexicons,
) -> tuple[Rows, list[Anomaly]]:
    """Rows for every table, in canonical order with IDs assigned in that order; plus name anomalies."""
    names = (
        "source_document", "ingredient", "ingredient_variant", "product", "product_ingredient", "crop",
        "crop_alias", "pest", "pest_alias", "use_record", "use_record_crop", "use_record_pest",
        "generic_member", "restriction", "anomaly",
    )  # fmt: skip
    tables: Rows = {name: [] for name in names}
    for d in sorted(docs, key=lambda d: d.id):
        tables["source_document"].append((d.id, d.kind, d.url, d.sha256, d.register_date, d.pages))

    ordered = sorted(uses, key=lambda du: (du[0].id, du[1].rows))
    products: dict[tuple[str, int, str, tuple[float, ...]], tuple[int, UseRow]] = {}
    displays: dict[str, str] = {}
    for doc, use in ordered:
        p = use.product
        pkey = (doc.id, p.page, p.text, p.bbox)
        if pkey not in products:
            products[pkey] = (len(products) + 1, use)
            for ing in parse_heading(p.text).ingredients:
                displays.setdefault(lexicons.variants.canonical(ing.name), ing.name)
    for r in restrictions:
        displays.setdefault(lexicons.variants.canonical(r.name_raw), r.name_raw)
    ingredient_ids = {k: i for i, k in enumerate(sorted(displays), start=1)}
    tables["ingredient"] = [(i, k, displays[k]) for k, i in ingredient_ids.items()]
    tables["ingredient_variant"] = sorted(
        {(r.variant, r.canonical, r.reviewed_by) for r in lexicons.variants.rows}
    )
    for (doc_id, page, text, bbox), (pid, use) in products.items():
        heading = parse_heading(text)
        notes = json.dumps(list(use.product.notes), ensure_ascii=False)
        section = use.product.section.value
        tables["product"].append(
            (
                pid,
                doc_id,
                section,
                text,
                heading.formulation,
                heading.status,
                notes,
                page,
                json.dumps(list(bbox)),
            )
        )
        for pos, ing in enumerate(heading.ingredients):
            iid = ingredient_ids[lexicons.variants.canonical(ing.name)]
            tables["product_ingredient"].append((pid, pos, iid, ing.conc, ing.unit, ing.basis))

    _name_tables(tables, lexicons)

    unknown: list[Anomaly] = [
        Anomaly("LEXICON_RULE_COLLISION", f"lexicon:{kind}", 0, 0, 0, f"{mk}: {', '.join(ids)}")
        for kind, collisions in (
            ("crops", lexicons.crops.collisions()),
            ("pests", lexicons.pests.collisions()),
        )
        for mk, ids in collisions
    ]  # two IDs that are one name under match_key must be merged by review first (L2 §13.2)
    crop_names = {cid: display for cid, display, _ in tables["crop"]}
    members, missing = expand(lexicons.generic, crop_names, dict(tables["pest"]))
    tables["generic_member"] = members
    unknown += [Anomaly("GENERIC_MEMBER_UNKNOWN", "lexicon:generic", 0, 0, 0, m) for m in missing]
    for uid, (doc, use) in enumerate(ordered, start=1):
        f = use.fields
        page, tbl, row = use.rows[0]
        crop_ids = sorted({e.canonical_id for e in lexicons.crops.resolve(f[Col.CROP].text)})
        if not crop_ids:
            unknown.append(Anomaly("UNKNOWN_CROP", doc.id, page, tbl, row, f[Col.CROP].text))
        tables["use_record_crop"] += [(uid, cid) for cid in crop_ids]
        for phrase in pest_phrases(f[Col.PEST].text):
            if lexicons.pests.ignored(phrase):
                continue
            ids = lexicons.pests.ids(phrase)
            if not ids:
                unknown.append(Anomaly("UNKNOWN_PEST", doc.id, page, tbl, row, phrase))
            tables["use_record_pest"] += [(uid, pid, phrase) for pid in ids]
        tables["use_record"].append(_use_row(uid, products[(doc.id, *_pkey(use))][0], use))
    tables["use_record_pest"] = sorted(set(tables["use_record_pest"]))
    for rid, r in enumerate(sorted(restrictions, key=lambda r: (r.status, r.key, r.page)), start=1):
        canonical = lexicons.variants.canonical(r.name_raw)
        tables["restriction"].append((rid, canonical, r.name_raw, r.status, r.detail_raw, r.page))
    return tables, unknown


def _name_tables(tables: Rows, lexicons: Lexicons) -> None:
    """crop, crop_alias, pest, pest_alias from the reviewed lexicons (ignored phrases are not pests)."""
    crops: dict[str, tuple[str, str]] = {}
    for e in lexicons.crops.entries:
        crops.setdefault(e.canonical_id, (e.display_en, e.category))
        tables["crop_alias"].append((key(e.alias), e.lang, e.canonical_id, e.reviewed_by))
    tables["crop"] = [(cid, display, cat) for cid, (display, cat) in sorted(crops.items())]
    tables["crop_alias"] = sorted(set(tables["crop_alias"]))
    pests: dict[str, str] = {}
    for pe in lexicons.pests.entries:
        if pe.canonical_id == IGNORE:
            continue
        pests.setdefault(pe.canonical_id, pe.display_en)
        tables["pest_alias"].append((pe.alias, pe.canonical_id, pe.reviewed_by))
    tables["pest"] = sorted(pests.items())
    tables["pest_alias"] = sorted(set(tables["pest_alias"]))


def _pkey(use: UseRow) -> tuple[int, str, tuple[float, ...]]:
    return use.product.page, use.product.text, use.product.bbox


def _use_row(uid: int, pid: int, use: UseRow) -> tuple[Any, ...]:
    f = use.fields
    quantities = {c: parse_quantity(f[c].text) for c in (Col.DOSE_AI, Col.DOSE_FORM, Col.DILUTION, Col.WAIT)}
    for q in quantities.values():
        check_digits(q)
    days = wait_days(f[Col.WAIT].text)
    provenance = {
        "rows": [list(r) for r in use.rows],
        "fields": {
            c.name: {
                "source": fl.source,
                "boxes": [[pg, list(b)] for pg, b in fl.bboxes],
                "origin": list(fl.origin) if fl.origin else None,
                "span_of": fl.span_of.name if fl.span_of else None,
            }
            for c, fl in f.items()
        },
    }
    return (
        uid, pid, f[Col.CROP].text, f[Col.PEST].text, f[Col.DOSE_AI].text, f[Col.DOSE_FORM].text,
        f[Col.DILUTION].text, f[Col.WAIT].text, _q(quantities[Col.DOSE_AI]), _q(quantities[Col.DOSE_FORM]),
        _q(quantities[Col.DILUTION]), days[0] if days else None, days[1] if days else None, use.page_first,
        use.page_last, json.dumps(provenance, ensure_ascii=False, sort_keys=True),
        json.dumps(list(use.notes), ensure_ascii=False),
        json.dumps([{"id": i, "field": f, "before": b} for i, f, b in use.corrections], ensure_ascii=False),
    )  # fmt: skip


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
            "uses_with_a_crop": one("SELECT count(DISTINCT use_record_id) FROM use_record_crop"),
            "uses_with_several_crops": one(
                "SELECT count(*) FROM (SELECT use_record_id FROM use_record_crop"
                " GROUP BY 1 HAVING count(*) > 1)"
            ),
            "uses_with_a_pest": one("SELECT count(DISTINCT use_record_id) FROM use_record_pest"),
            "crops": one("SELECT count(*) FROM crop"),
            "pests": one("SELECT count(*) FROM pest"),
            "products": one("SELECT count(*) FROM product"),
            "products_parsed": one("SELECT count(*) FROM product WHERE parse_status='parsed'"),
            "ingredients": one("SELECT count(*) FROM ingredient"),
            "restrictions": one("SELECT count(*) FROM restriction"),
            "restricted_ingredients_in_products": one(
                "SELECT count(DISTINCT i.key) FROM ingredient i"
                " JOIN restriction r ON r.ingredient_key = i.key "
                "JOIN product_ingredient pi ON pi.ingredient_id = i.id"
            ),
            "anomalies": dict(
                conn.execute("SELECT code, count(*) FROM anomaly GROUP BY code ORDER BY code").fetchall()
            ),
            "anomalies_not_allowed": one("SELECT count(*) FROM anomaly WHERE allowed = 0"),
        }
    finally:
        conn.close()


def draft_lexicon(what: str, sources: Path, cache: Path, out: Path, *, offline: bool) -> str:
    uses, restrictions, *_ = extract_all(load_manifest(sources), cache, offline=offline)
    if what == "crops":
        return f"{write_draft([u.fields[Col.CROP].text for _, u in uses], out)} crop strings -> {out}"
    if what == "pests":
        rows = draft_pests([u.fields[Col.PEST].text for _, u in uses])
        write_pests(rows, out)
        human = len({r.alias for r in rows if not r.reviewed_by})
        return f"{len(rows)} pest rows ({human} phrases need a human) -> {out}"
    names = [i.name for _, u in uses for i in parse_heading(u.product.text).ingredients]
    pairs = draft_variants(names + [r.name_raw for r in restrictions])
    write_variants(pairs, out)
    return f"{len(pairs)} ingredient variant candidates -> {out}"


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
            p.add_argument("--what", choices=("crops", "pests", "ingredients"), default="crops")
            p.add_argument("--out", type=Path, required=True)
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
            summary |= {"seconds": result.seconds, "unallowed": [asdict(x) for x in result.unallowed][:20]}
            print(json.dumps(summary, indent=1, ensure_ascii=False))
        elif args.cmd == "audit":
            print(json.dumps(audit(args.register), indent=1))
        elif args.cmd == "lexicon-draft":
            if args.out.exists():
                print(
                    f"refusing to overwrite {args.out}: a draft never replaces a reviewed file",
                    file=sys.stderr,
                )
                return 2
            print(draft_lexicon(args.what, args.sources, args.cache, args.out, offline=args.offline))
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
