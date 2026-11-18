"""Matching and outcome selection (L2 §4, §11). A pure function of the read-only register and the query."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from labelclaim.lookup.models import (
    Answer,
    ApprovedUse,
    Citation,
    Option,
    Outcome,
    Query,
    RegisterInfo,
    RestrictionNote,
    Suggestion,
)
from labelclaim.lookup.names import Names, ProductResolution, Resolution
from labelclaim.normalize.ingredients import spelling_family
from labelclaim.normalize.lexicon import key, match_key
from labelclaim.register.writer import open_readonly

MAX_ALTERNATIVES = 20
CORRECTED_FIELD = {
    "CROP": "crop_raw", "PEST": "pest_raw", "DOSE_AI": "dose_ai_raw", "DOSE_FORM": "dose_form_raw",
    "DILUTION": "dilution_raw", "WAIT": "wait_raw",
}  # fmt: skip
_USE_SQL = """
SELECT u.id, p.heading_raw, u.crop_raw, u.pest_raw, u.dose_ai_raw, u.dose_form_raw, u.dilution_raw,
       u.wait_raw,
       u.wait_lo, u.wait_hi, u.page_first, u.page_last, d.id, d.register_date, d.url, u.corrected_json
FROM use_record u JOIN product p ON p.id = u.product_id JOIN source_document d ON d.id = p.document_id
WHERE u.id IN ({ids}) ORDER BY u.id
"""


class Engine:
    def __init__(self, register: Path) -> None:
        # one Engine per thread (api.app.Engines); only shutdown closes it from another thread
        self._conn: sqlite3.Connection = open_readonly(register, same_thread=False)
        self.names = Names(self._conn)
        self._family_of = {i: spelling_family(k) for k, (i, _) in self.names.ingredient.items()}
        info = dict(self._conn.execute("SELECT key, value FROM build_info").fetchall())
        dates = dict(
            self._conn.execute("SELECT id, register_date FROM source_document WHERE kind != 'restrictions'")
        )
        self._info = RegisterInfo(info["build_hash"], dates, info.get("release") == "true")

    def close(self) -> None:
        self._conn.close()

    def register_info(self) -> RegisterInfo:
        return self._info

    # -- the one public question ------------------------------------------------------------------
    def lookup(self, q: Query) -> Answer:
        text = q.product if q.product is not None else q.ingredient
        assert text is not None  # noqa: S101 - Query guarantees exactly one
        product = self.names.product(text, ingredient_level=q.ingredient is not None)
        if product.status != "exact":
            return Answer(Outcome.UNKNOWN_PRODUCT, self._info, suggestions={"product": product.suggestions})
        crop = self.names.crop(q.crop)
        if crop.status == "generic":
            return self._general_crop(product, crop.ids, q.pest)
        restrictions = self._restrictions(product.ingredient_keys, crop.ids if crop.status == "exact" else ())
        if crop.status == "unknown":
            return self._answer(Outcome.UNKNOWN_CROP, restrictions, suggestions={"crop": crop.suggestions})
        if crop.status == "ambiguous":
            return self._answer(Outcome.AMBIGUOUS, restrictions, suggestions={"crop": crop.suggestions})
        return self._on_crop(product, crop.ids[0], q.pest, restrictions)

    def _on_crop(  # one return per outcome, in L2 §4 order
        self,
        product: ProductResolution,
        crop_id: str,
        pest_text: str | None,
        restrictions: tuple[RestrictionNote, ...],
    ) -> Answer:
        rows = self._uses(product.product_ids, crop_id)
        pest: Resolution | None = None
        pest_id: str | None = None
        if pest_text is not None:
            pest = self.names.pest(pest_text)
            if pest.status == "unknown":
                return self._answer(
                    Outcome.UNKNOWN_PEST,
                    restrictions,
                    alternatives=rows,
                    suggestions={"pest": pest.suggestions},
                )
            if pest.status == "ambiguous":
                return self._answer(Outcome.AMBIGUOUS, restrictions, suggestions={"pest": pest.suggestions})
            if pest.status == "exact":
                pest_id = pest.ids[0]
        if not rows:
            return self._answer(
                Outcome.NOT_APPROVED_FOR_CROP,
                restrictions,
                approved_crops=self._crops_of(product.product_ids),
                alternatives=self._uses_for(crop_id, pest_id, product.product_ids) if pest_id else [],
            )
        if pest is not None and pest.status == "generic":
            assert pest_text is not None  # noqa: S101 - set together with pest
            return self._general_pest(rows, crop_id, pest.ids, match_key(pest_text), restrictions)
        if pest_id is not None:
            with_pest = [u for u in rows if pest_id in self._pests_of(u)]
            if not with_pest:
                # Pilot test 1: "tikka" is one lexicon ID and the row's "Tikka leaf spot" another, so the
                # answer was a false "not listed". A row whose pest name contains every asked word is offered
                # as an option to confirm, never approved silently (ADR-006).
                near = self._near_names(rows, pest_id)
                return (
                    self._near_answer(near, restrictions)
                    if near
                    else self._answer(
                        Outcome.NOT_APPROVED_FOR_PEST,
                        restrictions,
                        approved_pests=self._pest_names(rows),
                        alternatives=self._uses_for(crop_id, pest_id, product.product_ids),
                    )
                )
            rows = with_pest
        return self._answer(Outcome.APPROVED, restrictions, uses=rows)

    # -- general names (L2 §13.5) -------------------------------------------------------------------
    def _general_pest(
        self,
        rows: list[int],
        crop_id: str,
        members: tuple[str, ...],
        term: str,
        restrictions: tuple[RestrictionNote, ...],
    ) -> Answer:
        """Options are the members registered on this crop (any product). APPROVED only if this product's
        rows make the general claim itself, or cover every option; NOT_APPROVED only if they cover none."""
        registered = self.pest_ids_on((crop_id,))
        options = [m for m in members if m in registered]
        pests_of = {u: self._pests_of(u) for u in rows}
        covered = {m: [u for u in rows if m in pests_of[u]] for m in options}
        approved = {m for m in options if covered[m]}
        general = next((m for m in options if match_key(self.names.pest_display[m]) == term), None)
        listed = tuple(
            Option(
                "pest",
                m,
                self.names.pest_display[m],
                Outcome.APPROVED if covered[m] else Outcome.NOT_APPROVED_FOR_PEST,
                tuple(covered[m]),
            )
            for m in options
        )
        if options and (general in approved or approved == set(options)):
            uses = sorted({u for m in approved for u in covered[m]})
            return self._answer(Outcome.APPROVED, restrictions, uses=uses, options=listed)
        if not approved:
            return self._answer(
                Outcome.NOT_APPROVED_FOR_PEST,
                restrictions,
                approved_pests=self._pest_names(rows),
                options=listed,
            )
        choices = tuple(Suggestion(o.id, o.display, 100.0) for o in listed)
        return self._answer(Outcome.AMBIGUOUS, restrictions, options=listed, suggestions={"pest": choices})

    def _general_crop(self, product: ProductResolution, members: tuple[str, ...], pest: str | None) -> Answer:
        """The query once per member crop. One shared outcome is the answer; otherwise AMBIGUOUS with each
        crop's outcome. A restriction naming any member crop sets `conflict` (the conservative choice)."""
        per = [(c, self._on_crop(product, c, pest, ())) for c in members]
        restrictions = self._restrictions(product.ingredient_keys, members)
        listed = tuple(
            Option("crop", c, self.names.crop_display[c], a.outcome, tuple(u.use_id for u in a.uses))
            for c, a in per
        )
        outcomes = {a.outcome for _, a in per}
        if len(outcomes) == 1:
            first = per[0][1]
            return self._answer(
                first.outcome,
                restrictions,
                uses=sorted({u.use_id for _, a in per for u in a.uses}),
                approved_crops=first.approved_crops,
                approved_pests=tuple(sorted({p for _, a in per for p in a.approved_pests})),
                suggestions=first.suggestions,
                options=listed,
            )
        choices = tuple(Suggestion(o.id, o.display, 100.0) for o in listed)
        return self._answer(Outcome.AMBIGUOUS, restrictions, options=listed, suggestions={"crop": choices})

    def _near_answer(
        self, near: list[tuple[str, list[int]]], restrictions: tuple[RestrictionNote, ...]
    ) -> Answer:
        listed = tuple(
            Option("pest", p, self.names.pest_display[p], Outcome.APPROVED, tuple(us)) for p, us in near
        )
        choices = tuple(Suggestion(o.id, o.display, 100.0) for o in listed)
        return self._answer(Outcome.AMBIGUOUS, restrictions, options=listed, suggestions={"pest": choices})

    def _near_names(self, rows: list[int], pest_id: str) -> list[tuple[str, list[int]]]:
        """This product's pests on this crop whose names contain every word of the asked pest's name (pilot
        fix 3), with their rows. Words like "and" and "disease" do not count."""
        asked = _name_words(self.names.pest_display[pest_id])
        if not asked:
            return []
        found: dict[str, list[int]] = {}
        for u in rows:
            for p in self._pests_of(u):
                if p != pest_id and asked < _name_words(self.names.pest_display[p]):
                    found.setdefault(p, []).append(u)
        return sorted(found.items())

    # -- helpers ---------------------------------------------------------------------------------------
    def _answer(
        self,
        outcome: Outcome,
        restrictions: tuple[RestrictionNote, ...],
        *,
        uses: list[int] | None = None,
        alternatives: list[int] | None = None,
        approved_crops: tuple[str, ...] = (),
        approved_pests: tuple[str, ...] = (),
        suggestions: dict[str, tuple[Suggestion, ...]] | None = None,
        options: tuple[Option, ...] = (),
    ) -> Answer:
        return Answer(
            outcome,
            self._info,
            uses=self._materialise(uses or []),
            alternatives=self._materialise((alternatives or [])[:MAX_ALTERNATIVES]),
            approved_crops=approved_crops,
            approved_pests=approved_pests,
            suggestions=suggestions or {},
            restrictions=restrictions,
            options=options,
        )

    def _uses(self, product_ids: tuple[int, ...], crop_id: str) -> list[int]:
        marks = ",".join("?" * len(product_ids))
        sql = (
            f"SELECT u.id FROM use_record u JOIN use_record_crop c ON c.use_record_id = u.id "  # noqa: S608
            f"WHERE c.crop_id = ? AND u.product_id IN ({marks}) ORDER BY u.id"
        )
        return [r[0] for r in self._conn.execute(sql, (crop_id, *product_ids))]

    def _uses_for(self, crop_id: str, pest_id: str | None, asked: tuple[int, ...] = ()) -> list[int]:
        """Approved uses for this crop and pest, the asked product's own ingredients first (pilot fix 4: for
        Mancozeb 75% WG on tomato, Mancozeb 75% WP is the most useful alternative, and it had been cut off by
        the cap of 20 after an order by row number)."""
        if pest_id is None:
            return []
        sql = (
            "SELECT DISTINCT u.id, u.product_id FROM use_record u "
            "JOIN use_record_crop c ON c.use_record_id = u.id "
            "JOIN use_record_pest p ON p.use_record_id = u.id "
            "WHERE c.crop_id = ? AND p.pest_id = ? ORDER BY u.id"
        )
        rows = self._conn.execute(sql, (crop_id, pest_id)).fetchall()
        wanted = {f for pid in asked for f in self._families(pid)}

        def rank(row: tuple[int, int]) -> tuple[int, int]:
            have = self._families(row[1])
            return (0 if have == wanted else 1 if have & wanted else 2, row[0])

        return [uid for uid, _ in sorted(rows, key=rank)]

    def _families(self, product_id: int) -> set[str]:
        """The product's ingredients by spelling family ("sulphur" = "sulfur", L2 §13.4)."""
        return {self._family_of[i] for i, _ in self.names.product_ingredients.get(product_id, ())}

    def pest_ids_on(self, crop_ids: tuple[str, ...]) -> set[str]:
        """Pests with at least one registered use on any of these crops (for the pest autocomplete)."""
        if not crop_ids:
            return set()
        marks = ",".join("?" * len(crop_ids))
        sql = (
            "SELECT DISTINCT p.pest_id FROM use_record_pest p JOIN use_record_crop c "  # noqa: S608
            f"ON c.use_record_id = p.use_record_id WHERE c.crop_id IN ({marks})"
        )
        return {r[0] for r in self._conn.execute(sql, crop_ids)}

    def _pests_of(self, use_id: int) -> set[str]:
        return {
            r[0]
            for r in self._conn.execute(
                "SELECT pest_id FROM use_record_pest WHERE use_record_id = ?", (use_id,)
            )
        }

    def _pest_names(self, use_ids: list[int]) -> tuple[str, ...]:
        ids = {p for u in use_ids for p in self._pests_of(u)}
        return tuple(sorted(self.names.pest_display[p] for p in ids))

    def _crops_of(self, product_ids: tuple[int, ...]) -> tuple[str, ...]:
        marks = ",".join("?" * len(product_ids))
        sql = (
            f"SELECT DISTINCT c.crop_id FROM use_record u JOIN use_record_crop c ON c.use_record_id = u.id "  # noqa: S608
            f"WHERE u.product_id IN ({marks})"
        )
        return tuple(sorted(self.names.crop_display[r[0]] for r in self._conn.execute(sql, product_ids)))

    def _restrictions(
        self, ingredient_keys: tuple[str, ...], crop_ids: tuple[str, ...]
    ) -> tuple[RestrictionNote, ...]:
        if not ingredient_keys:
            return ()
        marks = ",".join("?" * len(ingredient_keys))
        sql = (
            f"SELECT name_raw, status, detail_raw, page FROM restriction WHERE ingredient_key IN ({marks}) "  # noqa: S608
            "ORDER BY status, name_raw, page"
        )
        names = self.names.crop_words(crop_ids)
        notes = []
        for name, status, detail, page in self._conn.execute(sql, ingredient_keys):
            words = set(key(detail).replace(",", " ").replace(".", " ").split())
            notes.append(RestrictionNote(name, status, detail, page, bool(names & words)))
        return tuple(notes)

    def _materialise(self, use_ids: list[int]) -> tuple[ApprovedUse, ...]:
        if not use_ids:
            return ()
        rows = self._conn.execute(_USE_SQL.format(ids=",".join("?" * len(use_ids))), use_ids).fetchall()
        order = {uid: n for n, uid in enumerate(use_ids)}  # keep the caller's order (pilot fix 4)
        rows.sort(key=lambda r: order[r[0]])
        out = []
        for uid, heading, crop, pest, ai, form, dil, wait, lo, hi, first, last, doc, date, url, fixed in rows:
            citation = Citation(doc, date, first, last, f"{url}#page={first}")
            days = (lo, hi) if lo is not None and hi is not None else None
            corrected = tuple(sorted({CORRECTED_FIELD[c["field"]] for c in json.loads(fixed)}))
            out.append(ApprovedUse(uid, heading, crop, pest, ai, form, dil, wait, days, citation, corrected))
        return tuple(out)


def to_json(answer: Answer) -> str:
    """A stable JSON rendering, used by the CLI and tests (the API has its own Pydantic schema)."""
    from dataclasses import asdict  # noqa: PLC0415 - only needed here

    return json.dumps(asdict(answer), ensure_ascii=False, sort_keys=True)


_NOT_NAME_WORDS = frozenset({"and", "or", "of", "the", "disease", "diseases", "pest", "pests"})


def _name_words(name: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z]+", name.lower())) - _NOT_NAME_WORDS
