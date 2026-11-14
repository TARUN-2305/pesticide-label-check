"""Pest phrases and the pest lexicon (L2 §11 A2; ADR-006 as amended there).

A register pest cell is split into *phrases* on , ; / and newlines only. Whether "X and Y" is one pest
("shoot and fruit borer") or two ("early and late blight") is a lexicon decision, made by a human.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from labelclaim.normalize.lexicon import key

FIELDS = ("canonical_id", "display_en", "alias", "lang", "reviewed_by")
RULES = ("rule:identity", "rule:plural", "rule:split-known")
# a single plant-part word before "and" means one pest of both parts ("shoot and fruit borer")
_PLANT_PARTS = {
    "shoot", "fruit", "leaf", "stem", "root", "collar", "neck", "pod", "boll", "flower", "bud", "top", "seed",
    "seedling", "head", "panicle", "grain", "twig", "branch", "bark", "tuber", "foliage",
}  # fmt: skip


def pest_phrases(text: str) -> tuple[str, ...]:
    plain = re.sub(r"\([^()]*\)", " ", text)
    parts = re.split(r"[,;/\n]", plain)
    keys = [key(p) for p in parts]
    return tuple(dict.fromkeys(k for k in keys if k and re.search(r"[a-z]", k)))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key(text)).strip("_") or "unknown"


@dataclass(frozen=True)
class PestEntry:
    canonical_id: str
    display_en: str
    alias: str
    lang: str
    reviewed_by: str


def draft_pests(cells: Iterable[str]) -> list[PestEntry]:
    """Suggested lexicon rows for every phrase in `cells`. Rule rows are marked reviewed by their rule;
    rows for phrases containing "and" are suggestions with reviewed_by empty (a human decides)."""
    phrases = sorted({p for cell in cells for p in pest_phrases(cell)})
    present = set(phrases)
    rows: list[PestEntry] = []
    for phrase in phrases:
        if " and " in f" {phrase} ":
            halves = [h.strip() for h in phrase.split(" and ")]
            one_pest = " " not in halves[0] and halves[0] in _PLANT_PARTS  # "shoot and fruit borer"
            if len(halves) == 2 and not one_pest and all(h in present for h in halves):
                # both halves are register pest names themselves: "aphid and white fly" -> aphid, white fly
                for half in halves:
                    name = _singular(half, present)
                    rows.append(PestEntry(slug(name), name, phrase, "en", "rule:split-known"))
                continue
            for canonical in _split_suggestion(phrase):
                rows.append(PestEntry(slug(canonical), canonical, phrase, "en", ""))
        elif phrase.endswith("s") and phrase[:-1] in present and not phrase.endswith("ss"):
            rows.append(PestEntry(slug(phrase[:-1]), phrase[:-1], phrase, "en", "rule:plural"))
        else:
            rows.append(PestEntry(slug(phrase), phrase, phrase, "en", "rule:identity"))
    return rows


def _singular(phrase: str, present: set[str]) -> str:
    return (
        phrase[:-1]
        if phrase.endswith("s") and not phrase.endswith("ss") and phrase[:-1] in present
        else phrase
    )


def _split_suggestion(phrase: str) -> list[str]:
    left, _, right = phrase.partition(" and ")
    if " " not in left and left in _PLANT_PARTS:
        return [phrase]  # "shoot and fruit borer": one pest
    words = right.split()
    if " " not in left and len(words) >= 2:
        return [
            f"{left} {' '.join(words[1:])}",
            right,
        ]  # "early and late blight" -> early blight, late blight
    return [p.strip() for p in phrase.split(" and ") if p.strip()]


@dataclass(frozen=True)
class PestLexicon:
    entries: tuple[PestEntry, ...]

    def ids(self, text: str) -> tuple[str, ...]:
        k = key(text)
        return tuple(dict.fromkeys(e.canonical_id for e in self.entries if e.alias == k))

    @property
    def unreviewed(self) -> tuple[PestEntry, ...]:
        return tuple(e for e in self.entries if not e.reviewed_by.strip())


def load_pests(path: Path) -> PestLexicon:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: header must be {','.join(FIELDS)}")
        entries = []
        for i, row in enumerate(reader, start=2):
            if not re.fullmatch(r"[a-z0-9_]+", row["canonical_id"]):
                raise ValueError(f"{path}:{i}: canonical_id must be [a-z0-9_]+")
            entries.append(PestEntry(**{f: (row[f] or "").strip() for f in FIELDS}))
    return PestLexicon(
        tuple(PestEntry(e.canonical_id, e.display_en, key(e.alias), e.lang, e.reviewed_by) for e in entries)
    )


def write_pests(rows: list[PestEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDS)
        for r in sorted(rows, key=lambda r: (r.alias, r.canonical_id)):
            writer.writerow([r.canonical_id, r.display_en, r.alias, r.lang, r.reviewed_by])
