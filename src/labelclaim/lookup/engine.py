"""Matching and outcome selection (L2 §4, §11). A pure function of the read-only register and the query."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from labelclaim.lookup.models import (
    Answer,
    ApprovedUse,
    Citation,
    Outcome,
    Query,
    RegisterInfo,
    RestrictionNote,
    Suggestion,
)
from labelclaim.lookup.names import Names
from labelclaim.normalize.lexicon import key
from labelclaim.register.writer import open_readonly

MAX_ALTERNATIVES = 20
_USE_SQL = """
SELECT u.id, p.heading_raw, u.crop_raw, u.pest_raw, u.dose_ai_raw, u.dose_form_raw, u.dilution_raw,
       u.wait_raw,
       u.wait_lo, u.wait_hi, u.page_first, u.page_last, d.id, d.register_date, d.url
FROM use_record u JOIN product p ON p.id = u.product_id JOIN source_document d ON d.id = p.document_id
WHERE u.id IN ({ids}) ORDER BY u.id
"""


class Engine:
    def __init__(self, register: Path) -> None:
        # one Engine per thread (api.app.Engines); only shutdown closes it from another thread
        self._conn: sqlite3.Connection = open_readonly(register, same_thread=False)
        self.names = Names(self._conn)
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
    def lookup(self, q: Query) -> Answer:  # noqa: PLR0911 - one return per outcome, in L2 §4 order
        text = q.product if q.product is not None else q.ingredient
        assert text is not None  # noqa: S101 - Query guarantees exactly one
        product = self.names.product(text, ingredient_level=q.ingredient is not None)
        if product.status != "exact":
            return Answer(Outcome.UNKNOWN_PRODUCT, self._info, suggestions={"product": product.suggestions})
        crop = self.names.crop(q.crop)
        restrictions = self._restrictions(product.ingredient_keys, crop.ids if crop.status == "exact" else ())
        if crop.status == "unknown":
            return self._answer(Outcome.UNKNOWN_CROP, restrictions, suggestions={"crop": crop.suggestions})
        if crop.status == "ambiguous":
            return self._answer(Outcome.AMBIGUOUS, restrictions, suggestions={"crop": crop.suggestions})
        crop_id = crop.ids[0]
        rows = self._uses(product.product_ids, crop_id)
        pest_id: str | None = None
        if q.pest is not None:
            pest = self.names.pest(q.pest)
            if pest.status == "unknown":
                return self._answer(
                    Outcome.UNKNOWN_PEST,
                    restrictions,
                    alternatives=rows,
                    suggestions={"pest": pest.suggestions},
                )
            if pest.status == "ambiguous":
                return self._answer(Outcome.AMBIGUOUS, restrictions, suggestions={"pest": pest.suggestions})
            pest_id = pest.ids[0]
        if not rows:
            return self._answer(
                Outcome.NOT_APPROVED_FOR_CROP,
                restrictions,
                approved_crops=self._crops_of(product.product_ids),
                alternatives=self._uses_for(crop_id, pest_id) if pest_id else [],
            )
        if pest_id is not None:
            with_pest = [u for u in rows if pest_id in self._pests_of(u)]
            if not with_pest:
                return self._answer(
                    Outcome.NOT_APPROVED_FOR_PEST,
                    restrictions,
                    approved_pests=self._pest_names(rows),
                    alternatives=self._uses_for(crop_id, pest_id),
                )
            rows = with_pest
        return self._answer(Outcome.APPROVED, restrictions, uses=rows)

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
        )

    def _uses(self, product_ids: tuple[int, ...], crop_id: str) -> list[int]:
        marks = ",".join("?" * len(product_ids))
        sql = (
            f"SELECT u.id FROM use_record u JOIN use_record_crop c ON c.use_record_id = u.id "  # noqa: S608
            f"WHERE c.crop_id = ? AND u.product_id IN ({marks}) ORDER BY u.id"
        )
        return [r[0] for r in self._conn.execute(sql, (crop_id, *product_ids))]

    def _uses_for(self, crop_id: str, pest_id: str | None) -> list[int]:
        if pest_id is None:
            return []
        sql = (
            "SELECT DISTINCT u.id FROM use_record u JOIN use_record_crop c ON c.use_record_id = u.id "
            "JOIN use_record_pest p ON p.use_record_id = u.id "
            "WHERE c.crop_id = ? AND p.pest_id = ? ORDER BY u.id"
        )
        return [r[0] for r in self._conn.execute(sql, (crop_id, pest_id))]

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
        out = []
        for uid, heading, crop, pest, ai, form, dil, wait, lo, hi, first, last, doc, date, url in rows:
            citation = Citation(doc, date, first, last, f"{url}#page={first}")
            days = (lo, hi) if lo is not None and hi is not None else None
            out.append(ApprovedUse(uid, heading, crop, pest, ai, form, dil, wait, days, citation))
        return tuple(out)


def to_json(answer: Answer) -> str:
    """A stable JSON rendering, used by the CLI and tests (the API has its own Pydantic schema)."""
    from dataclasses import asdict  # noqa: PLC0415 - only needed here

    return json.dumps(asdict(answer), ensure_ascii=False, sort_keys=True)
