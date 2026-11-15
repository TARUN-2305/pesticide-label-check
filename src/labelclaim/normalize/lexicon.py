"""Name keys and the reviewed crop lexicon (L1 §6.3, ADR-006).

`key()` is THE normalisation shared by the build and the lookup (L2 imports it), so the two planes can
never disagree on what counts as the same name.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

CATEGORIES = ("crop", "storage", "structure", "non_crop")


def key(text: str) -> str:
    """NFC, casefold, drop ` and ', '&' -> 'and', unify dashes, collapse whitespace, trim punctuation."""
    text = unicodedata.normalize("NFC", text).casefold()
    text = text.replace("`", "").replace("'", "").replace("’", "").replace("&", " and ")
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.;:-*")  # trailing "*" is a footnote marker ("Apple*")


_LABEL = re.compile(r"^(?:pests?|diseases?|insects?)\s*:\s*")


def match_key(text: str) -> str:
    """The key two crop or pest names must share to be the same name (L2 §13.2): `key()`, then no leading
    label ("Pests:"), no spaces, hyphens or punctuation, and a plural ending folded ("-ies" -> "-y",
    "-s" -> "" but not "-ss"). "White fly", "Whiteflies" and "whitefly" are one name by rule; two lexicon
    IDs that collide under it must be merged by review before a release (LEXICON_RULE_COLLISION)."""
    k = re.sub(r"[\W_]+", "", _LABEL.sub("", key(text)))
    if len(k) > 4 and k.endswith("ies"):
        return k[:-3] + "y"
    if len(k) > 3 and k.endswith("s") and not k.endswith("ss"):
        return k[:-1]
    return k


def rule_collisions(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, tuple[str, ...]]]:
    """(match key, the IDs involved) wherever aliases that are equal under `match_key` but written
    differently map to different ID sets. An alias that deliberately maps to several IDs ("Cabbage &
    Cauliflower") is not a collision on its own."""
    by_alias: dict[str, set[str]] = {}
    for alias, target in pairs:
        by_alias.setdefault(key(alias), set()).add(target)
    groups: dict[str, dict[str, frozenset[str]]] = {}
    for alias, targets in by_alias.items():
        groups.setdefault(match_key(alias), {})[alias] = frozenset(targets)
    return [
        (mk, tuple(sorted(set().union(*sets.values()))))
        for mk, sets in sorted(groups.items())
        if len(set(sets.values())) > 1
    ]


@dataclass(frozen=True)
class CropEntry:
    canonical_id: str
    display_en: str
    alias: str  # as written (register string or user name)
    lang: str
    category: str
    reviewed_by: str


@dataclass(frozen=True)
class CropLexicon:
    entries: tuple[CropEntry, ...]

    @cached_property
    def _by_match_key(self) -> dict[str, tuple[CropEntry, ...]]:
        index: dict[str, list[CropEntry]] = {}
        for e in self.entries:
            index.setdefault(match_key(e.alias), []).append(e)
        return {k: tuple(v) for k, v in index.items()}

    def resolve(self, text: str) -> tuple[CropEntry, ...]:
        return self._by_match_key.get(match_key(text), ())

    def collisions(self) -> list[tuple[str, tuple[str, ...]]]:
        return rule_collisions((e.alias, e.canonical_id) for e in self.entries)

    @property
    def unreviewed(self) -> tuple[CropEntry, ...]:
        return tuple(e for e in self.entries if not e.reviewed_by.strip())


FIELDS = ("canonical_id", "display_en", "alias", "lang", "category", "reviewed_by")


def load_crops(path: Path) -> CropLexicon:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    entries = []
    for i, row in enumerate(rows, start=2):
        if tuple(row) != FIELDS:
            raise ValueError(f"{path}: header must be {','.join(FIELDS)}")
        if row["category"] not in CATEGORIES:
            raise ValueError(f"{path}:{i}: category {row['category']!r} not in {CATEGORIES}")
        if not re.fullmatch(r"[a-z0-9_]+", row["canonical_id"]):
            raise ValueError(f"{path}:{i}: canonical_id must be [a-z0-9_]+")
        entries.append(CropEntry(**{f: row[f].strip() for f in FIELDS}))
    return CropLexicon(tuple(entries))


# --- draft generation: SUGGESTIONS for a human reviewer, never treated as reviewed ---------------------
_SYNONYMS = {
    "paddy": "rice", "transplanted paddy": "rice", "transplanted rice": "rice", "direct seeded rice": "rice",
    "chilly": "chilli", "chili": "chilli", "chillies": "chilli", "chilies": "chilli",
    "bhindi": "okra", "bhindi (okra)": "okra", "okra (bhindi)": "okra", "lady finger": "okra",
    "brinjal": "brinjal", "egg plant": "brinjal",
    "bengal gram": "chickpea", "chick pea": "chickpea", "gram": "chickpea",
    "red gram": "pigeonpea", "pigeon pea": "pigeonpea", "black gram": "blackgram", "green gram": "greengram",
    "bittergourd": "bitter_gourd", "barely": "barley", "ground nut": "groundnut", "soyabean": "soybean",
    "cabbage and cauliflower": "cabbage_cauliflower", "sugar cane": "sugarcane",
}  # fmt: skip
_STORAGE = re.compile(r"stored|godown|grain|warehouse|milled|commodit|flour|seed store", re.I)
_STRUCTURE = re.compile(r"building|wood|premises|plywood|veneer|furniture|ship|railway|structure", re.I)
_NON_CROP = re.compile(r"public health|non.?crop|burrow|residential|poultry|indoor|outdoor|field rat", re.I)


def suggest(register_crop: str) -> tuple[str, str]:
    """(canonical_id, category) suggestion for a register crop string."""
    k = key(register_crop)
    base = _SYNONYMS.get(k) or _SYNONYMS.get(key(re.sub(r"\(.*?\)", " ", k))) or re.sub(r"\(.*?\)", " ", k)
    canonical = re.sub(r"[^a-z0-9]+", "_", key(base)).strip("_") or "unknown"
    if _STORAGE.search(register_crop):
        category = "storage"
    elif _STRUCTURE.search(register_crop):
        category = "structure"
    elif _NON_CROP.search(register_crop):
        category = "non_crop"
    else:
        category = "crop"
    return canonical, category


def write_draft(register_crops: list[str], path: Path) -> int:
    """Write a draft lexicon (reviewed_by empty) for every distinct register crop string."""
    seen: dict[str, str] = {}
    for crop in register_crops:
        seen.setdefault(key(crop), crop)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDS)
        for k in sorted(seen):
            canonical, category = suggest(seen[k])
            writer.writerow([canonical, canonical.replace("_", " "), seen[k], "en", category, ""])
    return len(seen)


def split_pests(text: str) -> tuple[str, ...]:
    """Split a register pest cell into pest name keys; scientific names in brackets are dropped from the
    key (they stay in the raw text). Used for pest matching until a reviewed pest lexicon exists (M2)."""
    plain = re.sub(r"\([^()]*\)", " ", text)
    parts = re.split(r",|;|/|\band\b|&|\n", plain, flags=re.I)
    keys = [key(p) for p in parts]
    return tuple(dict.fromkeys(k for k in keys if k and re.search(r"[a-z]", k)))
