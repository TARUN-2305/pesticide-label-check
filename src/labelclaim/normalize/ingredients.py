"""Ingredient spelling variants (L2 §11 A3): 'aluminum' vs 'aluminium', 'chlorpyrifos' vs 'chlorpyriphos'.
The restriction overlay joins on ingredient keys, so a silent spelling mismatch would hide a ban."""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from labelclaim.normalize.headings import ingredient_key

FIELDS = ("variant", "canonical", "reviewed_by")
THRESHOLD = 85.0  # catches "chlorpyrifos"/"chlorpyriphos" (88); also catches look-alikes, hence review


@dataclass(frozen=True)
class Variant:
    variant: str
    canonical: str
    reviewed_by: str


def compact(name: str) -> str:
    """The match key: ingredient_key without spaces and hyphens, so "lambda-cyhalothrin",
    "lambda cyhalothrin" and "thiophanatemethyl"/"thiophanate-methyl" are equal by rule, not by review."""
    return re.sub(r"[\s\-]+", "", ingredient_key(name))


def draft_variants(keys: Iterable[str], threshold: float = THRESHOLD) -> list[Variant]:
    """Candidate pairs of near-identical compact keys (ratio >= threshold, not equal). The spelling seen
    more often is suggested as canonical (ties: longer, then alphabetical); a human confirms each pair.
    `keys` may repeat: repetitions are the frequency."""
    counts = Counter(compact(k) for k in keys if k)
    unique = sorted(counts)
    pairs = []
    for i, a in enumerate(unique):
        for b in unique[i + 1 :]:
            if fuzz.ratio(a, b) >= threshold:
                canonical, variant = sorted((a, b), key=lambda s: (-counts[s], -len(s), s))
                pairs.append(Variant(variant, canonical, ""))
    return pairs


@dataclass(frozen=True)
class Variants:
    rows: tuple[Variant, ...]

    def canonical(self, name: str) -> str:
        """The compact match key, mapped through the variant list."""
        k = compact(name)
        for row in self.rows:
            if row.variant == k:
                return row.canonical
        return k

    @property
    def unreviewed(self) -> tuple[Variant, ...]:
        return tuple(r for r in self.rows if not r.reviewed_by.strip())


def load_variants(path: Path) -> Variants:
    if not path.exists():
        return Variants(())
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"{path}: header must be {','.join(FIELDS)}")
        rows = [
            Variant(compact(r["variant"]), compact(r["canonical"]), (r["reviewed_by"] or "").strip())
            for r in reader
        ]
    return Variants(tuple(rows))


def write_variants(rows: list[Variant], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDS)
        for r in rows:
            writer.writerow([r.variant, r.canonical, r.reviewed_by])
