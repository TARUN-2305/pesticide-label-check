"""Name resolution (L2 §3, ADR-006): exact aliases resolve; fuzzy matches only become suggestions."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from labelclaim.extract.classify import FORMULATIONS
from labelclaim.lookup.models import Status, Suggestion
from labelclaim.normalize.headings import parse_heading
from labelclaim.normalize.ingredients import compact, spelling_family
from labelclaim.normalize.lexicon import key, match_key

SUGGEST_CUTOFF = 85.0
MAX_SUGGESTIONS = 5


@dataclass(frozen=True)
class Resolution:
    status: Status
    ids: tuple[str, ...]
    suggestions: tuple[Suggestion, ...] = ()


@dataclass(frozen=True)
class ProductResolution:
    status: Status
    product_ids: tuple[int, ...]
    ingredient_keys: tuple[str, ...]
    suggestions: tuple[Suggestion, ...] = ()


class Names:
    """In-memory alias indexes loaded once from the read-only register (a few thousand rows)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.crop_display = dict(conn.execute("SELECT id, display_en FROM crop").fetchall())
        self.pest_display = dict(conn.execute("SELECT id, display_en FROM pest").fetchall())
        self.crop_alias = _index(conn.execute("SELECT alias_key, crop_id FROM crop_alias").fetchall())
        for cid, display in self.crop_display.items():
            self.crop_alias[key(display)].add(cid)
        self.pest_alias = _index(conn.execute("SELECT alias_key, pest_id FROM pest_alias").fetchall())
        for pid, display in self.pest_display.items():
            self.pest_alias[key(display)].add(pid)
        # resolution goes through match_key (L2 §13.2); the key-based indexes above serve autocomplete
        # and the restriction-text check, which need the words as written
        self.crop_match = _rekey(self.crop_alias)
        self.pest_match = _rekey(self.pest_alias)
        self.generic: dict[tuple[str, str], tuple[str, ...]] = {}
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'generic_member'").fetchone():
            grouped: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
            for term, kind, member in conn.execute("SELECT term_key, kind, member_id FROM generic_member"):
                grouped[(kind, term)].append(member)
            self.generic = {k: tuple(sorted(v)) for k, v in grouped.items()}
        self.variant: dict[str, str] = {
            str(v): str(c) for v, c in conn.execute("SELECT variant, canonical FROM ingredient_variant")
        }
        self.ingredient = {k: (i, d) for i, k, d in conn.execute("SELECT id, key, display FROM ingredient")}
        families: defaultdict[str, list[str]] = defaultdict(list)
        for k in self.ingredient:
            families[spelling_family(k)].append(k)
        self.family = {f: tuple(ks) for f, ks in families.items()}
        products: dict[int, list[tuple[int, float | None]]] = defaultdict(list)
        for pid, iid, conc in conn.execute(
            "SELECT product_id, ingredient_id, conc_value FROM product_ingredient"
        ):
            products[pid].append((iid, conc))
        self.product_ingredients = {pid: tuple(sorted(v)) for pid, v in products.items()}
        self.formulation = dict(conn.execute("SELECT id, formulation FROM product").fetchall())
        self.heading = dict(conn.execute("SELECT id, heading_raw FROM product").fetchall())

    # -- crops and pests ---------------------------------------------------------------------------
    def crop(self, text: str) -> Resolution:
        members = self.generic.get(("crop", match_key(text)))
        if members:
            return Resolution("generic", members)
        return _resolve(text, self.crop_match, self.crop_display)

    def crop_mentions(self, text: str) -> list[tuple[str, tuple[str, ...]]]:
        """Crop names written in free text, as (the words as written, crop IDs): exact aliases only, matched
        on whole words, longest first, never overlapping ("chai bagan" wins over "chai"). Fix A (E3n-c NC-034)
        uses it to see which crop the user typed. Deterministic, never fuzzy (ADR-006)."""
        return [(text[start:end], ids) for start, end, ids in self.crop_spans(text)]

    def crop_spans(self, text: str) -> list[tuple[int, int, tuple[str, ...]]]:
        """`crop_mentions` with positions, as (start, end, crop IDs)."""
        words = list(_WORD.finditer(text))
        found: list[tuple[int, int, tuple[str, ...]]] = []
        i = 0
        while i < len(words):
            for n in range(min(MAX_ALIAS_WORDS, len(words) - i), 0, -1):
                start, end = words[i].start(), words[i + n - 1].end()
                ids = self.crop_match.get(match_key(text[start:end]))
                if ids:
                    found.append((start, end, tuple(sorted(ids))))
                    i += n
                    break
            else:
                i += 1
        return found

    def crop_words(self, crop_ids: tuple[str, ...]) -> set[str]:
        """Single-word aliases of these crops ("ber", "citrus"), to spot them in restriction text."""
        wanted = set(crop_ids)
        return {
            alias
            for alias, ids in self.crop_alias.items()
            if ids & wanted and " " not in alias and len(alias) > 2
        }

    def pest(self, text: str) -> Resolution:
        members = self.generic.get(("pest", match_key(text)))
        if members:
            return Resolution("generic", members)
        return _resolve(text, self.pest_match, self.pest_display)

    # -- products --------------------------------------------------------------------------------------
    def ingredient_key(self, name: str) -> str:
        """Compact key, then the reviewed variants, then the spelling fold when it has exactly one registered
        match ("copper sulfate" -> "coppersulphate"; L2 §13.4). The fold is deterministic, not fuzzy."""
        k = compact(name)
        k = self.variant.get(k, k)
        if k not in self.ingredient:
            same = self.family.get(spelling_family(k), ())
            if len(same) == 1:
                return same[0]
            if (folded := unique_prefix(k, self.ingredient)) is not None:  # "emamectin" (polish round)
                return folded
        return k

    def product(self, text: str, *, ingredient_level: bool) -> ProductResolution:
        """Ingredient sets match as sets (L2 §11 A4); a full heading also pins concentration and form.
        A strength typed without "%" ("Malathion 50 EC") is read as a percentage (E3n fix 1)."""
        heading = parse_heading(text)
        if not ingredient_level and heading.status != "parsed":
            retry = with_percent(text)
            if retry != text and parse_heading(retry).status == "parsed":
                text, heading = retry, parse_heading(retry)
        names = (
            [p.strip() for p in text.split("+")]
            if ingredient_level
            else [i.name for i in heading.ingredients]
        )
        keys = tuple(self.ingredient_key(n) for n in names if n)
        missing = [k for k in keys if k not in self.ingredient]
        if not keys or missing:
            return ProductResolution(
                "unknown", (), keys, self._ingredient_suggestions(missing or [compact(text)])
            )
        wanted = {self.ingredient[k][0] for k in keys}
        candidates = [pid for pid, ings in self.product_ingredients.items() if {i for i, _ in ings} == wanted]
        if not ingredient_level and heading.status == "parsed":
            concs = {self.ingredient[self.ingredient_key(i.name)][0]: i.conc for i in heading.ingredients}
            exact = [
                pid
                for pid in candidates
                if self.formulation.get(pid) == heading.formulation
                and all(_same(c, concs.get(i)) for i, c in self.product_ingredients[pid])
            ]
            if candidates and not exact:  # these ingredients are registered, but not this formulation
                return ProductResolution("unknown", (), keys, self._product_suggestions(candidates))
            candidates = exact
        if not candidates:
            return ProductResolution("unknown", (), keys, self._product_suggestions(self._containing(wanted)))
        return ProductResolution("exact", tuple(sorted(candidates)), keys)

    def _containing(self, wanted: set[int]) -> list[int]:
        return [pid for pid, ings in self.product_ingredients.items() if wanted & {i for i, _ in ings}]

    def _product_suggestions(self, pids: list[int]) -> tuple[Suggestion, ...]:
        return tuple(Suggestion(str(p), self.heading[p], 100.0) for p in sorted(pids)[:MAX_SUGGESTIONS])

    def _ingredient_suggestions(self, keys: list[str]) -> tuple[Suggestion, ...]:
        out: list[Suggestion] = []
        for k in keys:
            for match, score, _ in process.extract(
                k,
                list(self.ingredient),
                scorer=fuzz.ratio,
                score_cutoff=SUGGEST_CUTOFF,
                limit=MAX_SUGGESTIONS,
            ):
                out.append(Suggestion(match, self.ingredient[match][1], round(float(score), 1)))
        return tuple(out[:MAX_SUGGESTIONS])


def _same(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) < 1e-6


def _index(rows: list[tuple[str, str]]) -> defaultdict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)
    for alias, target in rows:
        index[alias].add(target)
    return index


def _rekey(aliases: dict[str, set[str]]) -> defaultdict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)
    for alias, targets in aliases.items():
        index[match_key(alias)].update(targets)
    return index


def _resolve(text: str, aliases: dict[str, set[str]], display: dict[str, str]) -> Resolution:
    k = match_key(text)
    ids = tuple(sorted(aliases.get(k, ())))
    if len(ids) == 1:
        return Resolution("exact", ids)
    if len(ids) > 1:
        return Resolution("ambiguous", ids, tuple(Suggestion(i, display[i], 100.0) for i in ids))
    suggestions: dict[str, Suggestion] = {}
    for alias, score, _ in process.extract(
        k, list(aliases), scorer=fuzz.ratio, score_cutoff=SUGGEST_CUTOFF, limit=MAX_SUGGESTIONS * 2
    ):
        for target in sorted(aliases[alias]):
            if target not in suggestions:
                suggestions[target] = Suggestion(target, display[target], round(float(score), 1))
    ranked = sorted(suggestions.values(), key=lambda s: (-s.score, s.id))
    return Resolution("unknown", (), tuple(ranked[:MAX_SUGGESTIONS]))


_BARE_STRENGTH = re.compile(
    rf"(?<![\d.])(\d+(?:\.\d+)?)(?!\s*(?:%|g\s*/|gm?\b|ml\b|kg\b|l\b))(?=\s*(?:\+|$|w/[wv]\b|(?:{FORMULATIONS})\b))",
    re.IGNORECASE,
)


MIN_PREFIX = 6
MAX_ALIAS_WORDS = 4  # the longest crop alias a question would contain ("musukina jola", "rice (paddy)")
# a run of letters; Indic blocks are listed because their vowel signs are not letters to `re`
_WORD = re.compile(r"(?:[^\W\d_]|[ऀ-෿])+")


def written_in(text: str, phrase: str) -> bool:
    """True when `phrase` appears in `text` as whole words, compared by `match_key` ("Brinjal" in "on
    brinjal?"; not "pea" in "appear")."""
    target = match_key(phrase)
    if not target:
        return False
    words = list(_WORD.finditer(text))
    longest = max(MAX_ALIAS_WORDS, len(_WORD.findall(phrase)))
    for i in range(len(words)):
        for n in range(1, min(longest, len(words) - i) + 1):
            if match_key(text[words[i].start() : words[i + n - 1].end()]) == target:
                return True
    return False


def unique_prefix(key: str, keys: Iterable[str]) -> str | None:
    """A short ingredient name ("emamectin", "tetracycline") folds to the one registered ingredient it begins,
    if exactly one does and it has at least MIN_PREFIX letters. Deterministic, never fuzzy: two candidates
    ("copper" -> oxychloride, hydroxide, sulphate) mean no fold (ADR-006)."""
    if len(key) < MIN_PREFIX:
        return None
    found = [k for k in keys if k.startswith(key) and k != key]
    return found[0] if len(found) == 1 else None


def with_percent(text: str) -> str:
    """'Malathion 50 EC' -> 'Malathion 50% EC'; '75wp' -> '75% wp'. A number already followed by a unit is
    left alone, so g/l strengths never change. Query side only: the register's own headings are never
    rewritten."""
    out = _BARE_STRENGTH.sub(lambda m: m.group(1) + "% ", text)
    return " ".join(out.split())
