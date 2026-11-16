"""Number verifier (L3 §5, ADR-003, FR-7). Pure: no model, no I/O.

Every number in a model-written message must appear in the rows the answer cites. Numbers are compared as
values ("05" = "5" = "5.0"), and number words count ("seven", "twenty five", "half"). There are no
conversions and no arithmetic: a number the register does not print is blocked, even when it is correct.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal

from labelclaim.lookup.models import Answer

_FRACTIONS = {
    "½": Decimal("0.5"),
    "¼": Decimal("0.25"),
    "¾": Decimal("0.75"),
    "⅓": Decimal(1) / 3,
    "⅔": Decimal(2) / 3,
}
_DATE = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
_DIGITS = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?([½¼¾⅓⅔])?|(?<!\d)([½¼¾⅓⅔])")
_WORD = re.compile(r"[A-Za-z]+")
_UNIT_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TEN_WORDS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_UNITS = {w: i for i, w in enumerate(_UNIT_WORDS)}
_TENS = {w: 10 * i for i, w in enumerate(_TEN_WORDS, 2)}
_SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100_000}
_SINGLE = {"half": Decimal("0.5"), "quarter": Decimal("0.25"), "twice": Decimal(2), "thrice": Decimal(3),
           "dozen": Decimal(12)}  # fmt: skip


@dataclass(frozen=True)
class Verdict:
    ok: bool
    unverified: tuple[str, ...] = ()  # the raw text of each number not found in the cited rows


def _digit_numbers(text: str) -> Iterator[tuple[int, str, Decimal]]:
    masked = text
    for m in _DATE.finditer(text):
        for g in range(1, 4):
            yield m.start(g), m.group(g), Decimal(m.group(g))
        masked = masked[: m.start()] + " " * (m.end() - m.start()) + masked[m.end() :]
    for m in _DIGITS.finditer(masked):
        whole, frac, vulgar, alone = m.groups()
        if alone:
            yield m.start(), alone, _FRACTIONS[alone]
            continue
        value = Decimal(whole.replace(",", "") + (f".{frac}" if frac else ""))
        if vulgar:
            value += _FRACTIONS[vulgar]
        yield m.start(), m.group(0), value


def _joins(word: str, following: str) -> bool:
    """'a' in 'a hundred', and 'and' in 'a hundred and five', continue a number without adding to it."""
    return (word in ("a", "an") and following in _SCALES) or (
        word == "and" and following in {*_UNITS, *_TENS}
    )


def _word_numbers(text: str) -> Iterator[tuple[int, str, Decimal]]:
    words = list(_WORD.finditer(text))
    i = 0
    while i < len(words):
        w = words[i].group(0).lower()
        nxt = words[i + 1].group(0).lower() if i + 1 < len(words) else ""
        if w in _SINGLE:
            yield words[i].start(), words[i].group(0), _SINGLE[w]
            i += 1
            continue
        if not (w in _UNITS or w in _TENS or (w in ("a", "an") and nxt in _SCALES) or w in _SCALES):
            i += 1
            continue
        start, total, current, j = words[i].start(), 0, 0, i
        while j < len(words):
            t = words[j].group(0).lower()
            if t in _UNITS or t in _TENS:
                current += _UNITS.get(t, 0) + _TENS.get(t, 0)
            elif t in _SCALES:
                if t == "hundred":
                    current = (current or 1) * 100
                else:
                    total, current = total + (current or 1) * _SCALES[t], 0
            elif not _joins(t, words[j + 1].group(0).lower() if j + 1 < len(words) else ""):
                break
            j += 1
        yield start, text[start : words[j - 1].end()], Decimal(total + current)
        i = j


def numbers(text: str) -> list[tuple[str, Decimal]]:
    """Every number in `text`, in reading order, as (raw text, value)."""
    found = sorted([*_digit_numbers(text), *_word_numbers(text)], key=lambda x: x[0])
    return [(raw, value) for _, raw, value in found]  # Decimal equality and hashing are by value


def _values(texts: Iterable[str]) -> set[Decimal]:
    return {v for t in texts for _, v in numbers(t)}


def allowed_numbers(answer: Answer) -> set[Decimal]:
    """Numbers the answer cites: every field of its rows and alternatives (with headings, pages and the
    register date), the restriction notes, and the register dates."""
    texts: list[str] = list(answer.register.dates.values())
    for use in (*answer.uses, *answer.alternatives):
        texts += [use.product_heading, use.crop_raw, use.pest_raw, use.dose_ai_raw, use.dose_form_raw,
                  use.dilution_raw, use.wait_raw, use.citation.register_date,
                  str(use.citation.page_first), str(use.citation.page_last)]  # fmt: skip
    for note in answer.restrictions:
        texts += [note.ingredient, note.detail_raw, str(note.page)]
    return _values(texts)


def verify(message: str, allowed: set[Decimal]) -> Verdict:
    bad = tuple(raw for raw, value in numbers(message) if value not in allowed)
    return Verdict(not bad, bad)


_ADVICE = re.compile(r"\b(?:recommend\w*|safe|guarantee\w*)\b", re.IGNORECASE)


def wording(message: str) -> tuple[str, ...]:
    """NFR-4: words that turn a registered label claim into advice ("recommended dose", "safe to spray")."""
    return tuple(m.group(0) for m in _ADVICE.finditer(message))


def verify_clarification(question: str) -> Verdict:
    """A clarifying question carries no facts, so it may carry no numbers at all."""
    found = tuple(raw for raw, _ in numbers(question))
    return Verdict(not found, found)
