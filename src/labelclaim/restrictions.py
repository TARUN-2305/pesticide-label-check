"""Banned / refused / restricted pesticides list (FR-5 overlay; threat model T12)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from labelclaim.extract.model import PageItem, RawTable
from labelclaim.normalize.headings import ingredient_key

Status = Literal["banned", "banned_for_use", "withdrawn", "refused", "restricted"]
_SECTION: tuple[tuple[re.Pattern[str], Status], ...] = (
    (re.compile(r"banned for use but continued to manufacture for export", re.I), "banned_for_use"),
    (re.compile(r"banned for manufacture, import and use", re.I), "banned"),
    (re.compile(r"withdrawn", re.I), "withdrawn"),
)


@dataclass(frozen=True)
class Restriction:
    key: str  # ingredient_key of the name without its bracketed reference
    name_raw: str
    status: Status
    detail_raw: str
    page: int


def _split_name(text: str) -> tuple[str, str]:
    """'Alachlor ( S.O. 3951 (E), dated 08.08.2018)' -> ('Alachlor', 'S.O. 3951 (E), dated 08.08.2018')."""
    m = re.match(r"^(.*?)\s*\((?=\s*(?:s\.?\s?o|ad-|banned|g\.s\.r))(.*)\)\s*\**$", text, re.I)
    return (m.group(1).strip(), m.group(2).strip()) if m else (text.rstrip("*").strip(), "")


def parse_restrictions(pages: Iterable[tuple[int, list[PageItem]]]) -> list[Restriction]:
    out: list[Restriction] = []
    status: Status | None = None
    for page, items in pages:
        for item in items:
            text = item.text if not isinstance(item, RawTable) else ""
            if re.search(r"refused registration", text, re.I):
                status = "refused"
            elif re.search(r"restricted for use", text, re.I):
                status = "restricted"
            if not isinstance(item, RawTable):
                continue
            for row in item.rows:
                cells = [c.text for c in row.cells if c is not None]
                joined = " ".join(cells)
                numbered = [i for i, c in enumerate(cells) if re.fullmatch(r"\d+\.?", c)]
                if not numbered:  # only label rows switch the section; details may say "withdrawn"
                    for pattern, section in _SECTION:
                        if pattern.search(joined):
                            status = section
                    if re.search(r"name of pesticides", joined, re.I):
                        status = "restricted" if len(cells) >= 3 else "refused"
                    continue
                if status is None:
                    continue
                rest = [c for c in cells[numbered[0] + 1 :] if c]
                if not rest:
                    continue
                name, ref = _split_name(rest[0])
                detail = " ".join(rest[1:]) if status == "restricted" else ref
                out.append(
                    Restriction(ingredient_key(re.sub(r"\(.*?\)", "", name)), name, status, detail, page)
                )
    return out
