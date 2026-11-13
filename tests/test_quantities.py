"""L1 §10 `quantities`: observed formats (table-driven) and the never-invent-a-number property."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from labelclaim.normalize.quantities import parse_quantity, wait_days

CASES = [
    ("500", "value", (500.0,), (500.0,), None),
    ("1.8", "value", (1.8,), (1.8,), None),
    ("07", "value", (7.0,), (7.0,), None),
    ("500 – 600", "range", (500.0,), (600.0,), None),
    ("12.6-18.6", "range", (12.6,), (18.6,), None),
    ("750-1000 Lt", "range", (750.0,), (1000.0,), "l"),
    ("2.25 to 2.5 Kg", "range", (2.25,), (2.5,), "kg"),
    ("110 + 15", "sum", (110.0, 15.0), (110.0, 15.0), None),
    ("0.36+0.57+1.44", "sum", (0.36, 0.57, 1.44), (0.36, 0.57, 1.44), None),
    ("594 + 59.4 – 621 + 62.1", "sum_range", (594.0, 59.4), (621.0, 62.1), None),
    ("0.005%", "value", (0.005,), (0.005,), "%"),
    ("0.06%-0.1%", "range", (0.06,), (0.1,), "%"),
    ("562.5 g", "value", (562.5,), (562.5,), "g"),
    ("500gm", "value", (500.0,), (500.0,), "g"),
    ("1000 ml", "value", (1000.0,), (1000.0,), "ml"),
    ("07 days", "value", (7.0,), (7.0,), "days"),
]


@pytest.mark.parametrize(("raw", "kind", "lo", "hi", "unit"), CASES)
def test_observed_formats(
    raw: str, kind: str, lo: tuple[float, ...], hi: tuple[float, ...], unit: str | None
) -> None:
    q = parse_quantity(raw)
    assert (q.kind, q.lo, q.hi, q.unit, q.status) == (kind, lo, hi, unit, "parsed")


@pytest.mark.parametrize("raw", ["NA", "N.A.", "-", "–", "", "Nil", "Not applicable"])
def test_not_applicable_tokens(raw: str) -> None:
    q = parse_quantity(raw)
    assert (q.kind, q.status, q.lo) == ("na", "parsed", ())


@pytest.mark.parametrize(
    "raw",
    [
        "As required depending upon crop Stage and plant protection equipment used",
        "1.8 g a i/kg seed",
        "0.10% or100 Gram in 100lit. Of water",
        "Partial-1 hour. Full-(6-8) hour.",
    ],
)
def test_free_text_is_kept_unparsed(raw: str) -> None:
    q = parse_quantity(raw)
    assert (q.kind, q.status, q.lo, q.hi) == ("text", "unparsed", (), ())
    assert q.raw == raw


def test_wait_days() -> None:
    assert wait_days("21") == (21, 21)
    assert wait_days("07 days") == (7, 7)
    assert wait_days("3-5") == (3, 5)
    assert wait_days("NA") is None
    assert wait_days("used as seed dresser") is None
    assert wait_days("0.5") is None  # not a whole number of days: not guessed


@given(st.text(alphabet=st.sampled_from(list("0123456789.,+-–% toNAgmlkLdays ")), max_size=30))
def test_never_raises_and_never_invents_a_number(raw: str) -> None:
    q = parse_quantity(raw)
    assert q.raw == raw
    for token in q.tokens:
        assert token in raw  # every number used was read from the raw text ...
    numbers = [*q.lo, *q.hi]
    assert all(any(float(t) == n for t in q.tokens) for n in numbers)  # ... and is one of those tokens
    assert len(q.lo) == len(q.hi)


@given(st.from_regex(r"[0-9]{1,4}(\.[0-9]{1,2})?", fullmatch=True))
def test_plain_numbers_round_trip(raw: str) -> None:
    q = parse_quantity(raw)
    assert q.kind == "value"
    assert q.lo == (float(raw),)
    assert re.fullmatch(r"\d+(\.\d+)?", q.tokens[0])
