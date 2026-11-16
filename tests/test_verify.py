"""L3 §5: the number verifier. Pure; no model, no network."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from labelclaim.assistant.verify import allowed_numbers, numbers, verify, verify_clarification, wording
from labelclaim.lookup.models import Answer, ApprovedUse, Citation, Outcome, RegisterInfo, RestrictionNote

CITE = Citation("mup_insecticide_2026-09-30", "2026-09-30", 64, 64, "https://example.invalid#page=64")
USE = ApprovedUse(
    use_id=1, product_heading="Chlorantraniliprole 18.5% SC", crop_raw="Tomato", pest_raw="Fruit borer",
    dose_ai_raw="30", dose_form_raw="150", dilution_raw="500 - 1000", wait_raw="03", wait_days=(3, 3),
    citation=CITE,
)  # fmt: skip
ANSWER = Answer(Outcome.APPROVED, RegisterInfo("h", {"ins": "2026-09-30"}, True), uses=(USE,))


def values(text: str) -> list[Decimal]:
    return [v for _, v in numbers(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30 g a.i. per hectare", ["30"]),
        ("dilute in 500 - 1000 litres", ["500", "1000"]),
        ("dose 60–75 + 40-50", ["60", "75", "40", "50"]),
        ("18.5% SC", ["18.5"]),
        ("wait 03 days", ["3"]),
        ("1,000 litres", ["1000"]),
        ("Aphid, 25 and 30", ["25", "30"]),
        ("3½-4 months", ["3.5", "4"]),
        ("½ litre", ["0.5"]),
        ("the 30.09.2026 register", ["30", "9", "2026"]),
        ("wait five days", ["5"]),
        ("twenty five grams", ["25"]),
        ("a hundred litres and half a kilo", ["100", "0.5"]),
        ("spray twice", ["2"]),
        ("no numbers here", []),
    ],
)
def test_numbers_are_extracted_as_values(text: str, expected: list[str]) -> None:
    assert values(text) == [Decimal(e) for e in expected]


def test_allowed_numbers_come_from_the_cited_rows_heading_pages_and_date() -> None:
    allowed = allowed_numbers(ANSWER)
    assert {Decimal(x) for x in ("18.5", "30", "150", "500", "1000", "3", "64", "2026", "9")} <= allowed
    assert Decimal("2") not in allowed


def test_a_message_restating_cited_numbers_passes() -> None:
    message = (
        "Yes. Chlorantraniliprole 18.5% SC: 30 g a.i. (150 ml) per hectare in 500-1000 L water; wait 3 days."
    )
    assert verify(message, allowed_numbers(ANSWER)).ok


@pytest.mark.parametrize(
    ("message", "bad"),
    [
        ("For your 2 acres use 60 ml.", ["2", "60"]),  # the user's number, and a computed dose
        ("Use 0.15 litre per hectare.", ["0.15"]),  # a unit conversion of 150 ml
        ("Wait seven days before picking.", ["seven"]),  # a number word not in the rows
        ("Wait 5 days.", ["5"]),
    ],
)
def test_a_number_not_in_the_cited_rows_blocks_the_message(message: str, bad: list[str]) -> None:
    verdict = verify(message, allowed_numbers(ANSWER))
    assert not verdict.ok
    assert list(verdict.unverified) == bad


def test_alternatives_and_restriction_notes_are_cited_too() -> None:
    alt = ApprovedUse(2, "Spinosad 45% SC", "Tomato", "Fruit borer", "73", "160", "500", "1", (1, 1), CITE)
    note = RestrictionNote("Spinosad", "restricted", "Not for use on Ridgegourd after 2019", 4)
    answer = Answer(Outcome.NOT_APPROVED_FOR_PEST, ANSWER.register, alternatives=(alt,), restrictions=(note,))
    assert verify(
        "Spinosad 45% SC is approved at 73 g; a 2019 restriction applies.", allowed_numbers(answer)
    ).ok


def test_a_clarifying_question_may_not_contain_numbers() -> None:
    assert verify_clarification("Which crop are you spraying?").ok
    assert not verify_clarification("Is it the 18.5% SC or the 0.4% GR?").ok


@given(st.sampled_from(sorted(allowed_numbers(ANSWER))))
def test_any_allowed_number_written_as_digits_passes(value: Decimal) -> None:
    assert verify(f"The register lists {value} here.", allowed_numbers(ANSWER)).ok


@pytest.mark.parametrize(
    ("message", "bad"),
    [
        ("The recommended dose is 30 g.", ("recommended",)),
        ("It is safe to spray.", ("safe",)),
        ("We guarantee results.", ("guarantee",)),
        ("The register lists 30 g a.i. per hectare.", ()),
    ],
)
def test_wording_that_turns_a_label_claim_into_advice_is_flagged(message: str, bad: tuple[str, ...]) -> None:
    assert wording(message) == bad
