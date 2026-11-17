"""Lexicon loaders and draft writers (L1 §6, ADR-006): a malformed lexicon must fail the build, loudly.

Written to close the NFR-6 coverage gaps (2026-11-18): each test checks behaviour a broken data file would
hit, not just lines."""

from __future__ import annotations

from pathlib import Path

import pytest

from labelclaim.normalize.generic import GenericTerm, load_generic, members
from labelclaim.normalize.ingredients import Variant, load_variants, write_variants
from labelclaim.normalize.lexicon import load_crops, suggest, write_draft
from labelclaim.normalize.pests import PestEntry, _split_suggestion, load_pests, write_pests


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- general names ------------------------------------------------------------------------------------


def test_a_list_rule_names_its_members_directly() -> None:
    term = GenericTerm("gourd", "crop", "list:ridgegourd;bitter_gourd;", "t")
    assert members(term, {}) == ("bitter_gourd", "ridgegourd")


def test_an_unknown_members_rule_is_rejected() -> None:
    with pytest.raises(ValueError, match="'head:' or 'list:'"):
        members(GenericTerm("blight", "pest", "fuzzy:blight", "t"), {})


def test_general_terms_file_missing_header_or_bad_kind_fails(tmp_path: Path) -> None:
    assert load_generic(tmp_path / "absent.csv") == ()
    with pytest.raises(ValueError, match="header"):
        load_generic(write(tmp_path, "a.csv", "term,kind\nblight,pest\n"))
    with pytest.raises(ValueError, match="kind 'weed'"):
        load_generic(write(tmp_path, "b.csv", "term,kind,members_rule,reviewed_by\nx,weed,head:x,t\n"))


# --- crops ----------------------------------------------------------------------------------------------


CROP_HEADER = "canonical_id,display_en,alias,lang,category,reviewed_by\n"


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("tomato,tomato,Tomato,en,vegetable,t\n", "category 'vegetable'"),
        ("Tomato!,tomato,Tomato,en,crop,t\n", "canonical_id"),
    ],
)
def test_a_bad_crop_row_fails_with_its_line(tmp_path: Path, row: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_crops(write(tmp_path, "crops.csv", CROP_HEADER + row))


def test_a_crop_file_with_a_wrong_header_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="header"):
        load_crops(write(tmp_path, "crops.csv", "id,alias\ntomato,Tomato\n"))


@pytest.mark.parametrize(
    ("register_text", "category"),
    [
        ("Stored grain", "storage"),
        ("Wooden structures in buildings", "structure"),
        ("Public health", "non_crop"),
        ("Tomato", "crop"),
    ],
)
def test_draft_suggestions_sort_register_strings_into_categories(register_text: str, category: str) -> None:
    assert suggest(register_text)[1] == category


def test_a_written_draft_loads_back_as_unreviewed(tmp_path: Path) -> None:
    path = tmp_path / "draft.csv"
    assert write_draft(["Tomato", "tomato ", "Bitter gourd"], path) == 2  # one key per distinct string
    lexicon = load_crops(path)
    assert {e.canonical_id for e in lexicon.unreviewed} == {"tomato", "bitter_gourd"}


# --- pests ---------------------------------------------------------------------------------------------


def test_a_pest_and_phrase_is_split_unless_it_names_one_pest() -> None:
    assert _split_suggestion("shoot and fruit borer") == ["shoot and fruit borer"]
    assert _split_suggestion("aphids and jassids") == ["aphids", "jassids"]


def test_pest_file_errors_and_round_trip(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="header"):
        load_pests(write(tmp_path, "a.csv", "id,alias\n"))
    with pytest.raises(ValueError, match="canonical_id"):
        load_pests(
            write(tmp_path, "b.csv", "canonical_id,display_en,alias,lang,reviewed_by\nBad Id,x,x,en,t\n")
        )
    path = tmp_path / "pests.csv"
    write_pests([PestEntry("whitefly", "whitefly", "white fly", "en", "t")], path)
    assert load_pests(path).ids("White fly") == ("whitefly",)


# --- ingredient variants -----------------------------------------------------------------------------


def test_variant_file_errors_and_round_trip(tmp_path: Path) -> None:
    assert load_variants(tmp_path / "absent.csv").unreviewed == ()
    with pytest.raises(ValueError, match="header"):
        load_variants(write(tmp_path, "a.csv", "from,to\n"))
    path = tmp_path / "ingredients.csv"
    write_variants([Variant("chlorpyriphos", "chlorpyrifos", "")], path)
    assert [v.variant for v in load_variants(path).unreviewed] == ["chlorpyriphos"]
