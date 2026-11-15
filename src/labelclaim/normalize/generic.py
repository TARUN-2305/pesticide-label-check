"""General names (L2 §13.5): "blight", "mildew", "gourd". A reviewed table says which register names each
one covers; the engine then answers with options, never with a guess."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from labelclaim.normalize.lexicon import match_key

FIELDS = ("term", "kind", "members_rule", "reviewed_by")
KINDS = ("crop", "pest")


@dataclass(frozen=True)
class GenericTerm:
    term: str
    kind: str
    members_rule: str  # "head:<term>" (pests whose name ends with the term) or "list:<id>;<id>;..."
    reviewed_by: str


def _words(text: str) -> list[str]:
    return [match_key(w) for w in re.split(r"[\s\-]+", text) if match_key(w)]


def members(term: GenericTerm, names: Mapping[str, str]) -> tuple[str, ...]:
    """Member IDs among `names` (id -> display name) for one term."""
    if term.members_rule.startswith("list:"):
        return tuple(sorted(i for i in term.members_rule[5:].split(";") if i))
    if not term.members_rule.startswith("head:"):
        raise ValueError(f"members_rule must start with 'head:' or 'list:', got {term.members_rule!r}")
    head = _words(term.members_rule[5:])
    return tuple(sorted(i for i, display in names.items() if _words(display)[-len(head) :] == head))


def expand(
    terms: Iterable[GenericTerm], crops: Mapping[str, str], pests: Mapping[str, str]
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """generic_member rows (term match key, kind, member id) and the list IDs that do not exist."""
    rows: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for t in terms:
        names = crops if t.kind == "crop" else pests
        for member in members(t, names):
            if member in names:
                rows.append((match_key(t.term), t.kind, member))
            else:
                missing.append(f"{t.term}: {member}")
    return sorted(set(rows)), missing


def load_generic(path: Path) -> tuple[GenericTerm, ...]:
    if not path.exists():
        return ()
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: header must be {','.join(FIELDS)}")
        terms = tuple(GenericTerm(*((r[f] or "").strip() for f in FIELDS)) for r in reader)
    for t in terms:
        if t.kind not in KINDS:
            raise ValueError(f"{path}: kind {t.kind!r} not in {KINDS}")
    return terms
