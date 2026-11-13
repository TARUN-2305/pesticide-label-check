"""Quantity grammar (L1 §6.2, ADR-004). The parser never computes or invents a number: every value it
returns is one of the numeric tokens read from the raw text (property-tested). Anything else is 'text'."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal["value", "range", "sum", "sum_range", "na", "text"]
_NA = {"", "na", "n.a.", "n.a", "-", "–", "—", "nil", "not applicable"}
_UNITS = {
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g", "kg": "kg", "ml": "ml", "l": "l", "lt": "l",
    "ltr": "l", "lit": "l", "litre": "l", "liter": "l", "%": "%", "day": "days", "days": "days",
}  # fmt: skip
_NUM = r"\d+(?:\.\d+)?"
_UNIT = r"(?:%|gms?|grams?|g|kg|ml|ltr|lit(?:re|er)?|lt|l|days?)"
_TERM = rf"(?P<n>{_NUM})\s*(?P<u>{_UNIT})?\.?"
_SUM = rf"{_NUM}\s*{_UNIT}?\s*(?:\+\s*{_NUM}\s*{_UNIT}?\s*)+"
_SEP = r"\s*(?:-|–|to)\s*"


@dataclass(frozen=True)
class Quantity:
    raw: str
    kind: Kind
    lo: tuple[float, ...]  # one entry per summand ("110 + 15" -> (110, 15)); () for na / text
    hi: tuple[float, ...]
    unit: str | None
    tokens: tuple[str, ...]  # the numeric tokens read from `raw`, in order
    status: Literal["parsed", "unparsed"]


def _unit(found: list[str]) -> str | None:
    units = {_UNITS[u.lower()] for u in found if u}
    return units.pop() if len(units) == 1 else None


def _terms(text: str) -> tuple[tuple[str, ...], list[str]]:
    matches = list(re.finditer(rf"({_NUM})\s*({_UNIT})?", text, re.IGNORECASE))
    return tuple(m.group(1) for m in matches), [m.group(2) or "" for m in matches]


def parse_quantity(raw: str) -> Quantity:
    text = " ".join(raw.split())
    if text.lower() in _NA:
        return Quantity(raw, "na", (), (), None, (), "parsed")
    flags = re.IGNORECASE
    if re.fullmatch(_TERM, text, flags):
        tokens, units = _terms(text)
        return Quantity(
            raw, "value", (float(tokens[0]),), (float(tokens[0]),), _unit(units), tokens, "parsed"
        )
    if m := re.fullmatch(rf"({_NUM})\s*({_UNIT})?{_SEP}({_NUM})\s*({_UNIT})?\.?", text, flags):
        tokens = (m.group(1), m.group(3))
        unit = _unit([m.group(2) or "", m.group(4) or ""])
        return Quantity(raw, "range", (float(tokens[0]),), (float(tokens[1]),), unit, tokens, "parsed")
    if re.fullmatch(_SUM, text, flags):
        tokens, units = _terms(text)
        values = tuple(float(t) for t in tokens)
        return Quantity(raw, "sum", values, values, _unit(units), tokens, "parsed")
    if m := re.fullmatch(rf"({_SUM}){_SEP}({_SUM})", text, flags):
        lo_tokens, lo_units = _terms(m.group(1))
        hi_tokens, hi_units = _terms(m.group(2))
        if len(lo_tokens) == len(hi_tokens):
            return Quantity(
                raw,
                "sum_range",
                tuple(float(t) for t in lo_tokens),
                tuple(float(t) for t in hi_tokens),
                _unit(lo_units + hi_units),
                lo_tokens + hi_tokens,
                "parsed",
            )
    return Quantity(raw, "text", (), (), None, (), "unparsed")


def wait_days(raw: str) -> tuple[int, int] | None:
    """Waiting period in whole days, for sorting and filtering only (the raw text is what users see)."""
    q = parse_quantity(raw)
    if q.kind not in ("value", "range") or q.unit not in (None, "days"):
        return None
    lo, hi = q.lo[0], q.hi[0]
    if lo != int(lo) or hi != int(hi):
        return None
    return int(lo), int(hi)
