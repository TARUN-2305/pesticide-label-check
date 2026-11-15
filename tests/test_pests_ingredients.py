"""L2 §11 A2/A3: pest phrases, the pest lexicon rules, ingredient variants (tests written before the code)."""

from __future__ import annotations

from pathlib import Path

import pytest

from labelclaim.normalize.generic import GenericTerm, expand
from labelclaim.normalize.ingredients import Variants, draft_variants, load_variants
from labelclaim.normalize.lexicon import match_key, rule_collisions
from labelclaim.normalize.pests import PestLexicon, draft_pests, load_pests, pest_phrases


def test_phrases_split_on_commas_not_on_and() -> None:
    assert pest_phrases("Shoot and fruit borer (Leucinodes orbonalis)") == ("shoot and fruit borer",)
    assert pest_phrases("Thrips, Aphid & White fly") == ("thrips", "aphid and white fly")
    assert pest_phrases("Red spider mites (Tetranychus urticae); Leaf miner") == (
        "red spider mites",
        "leaf miner",
    )
    assert pest_phrases("Stem borer/ Leaf folder") == ("stem borer", "leaf folder")
    assert pest_phrases("") == ()


def test_split_known_rule_only_when_both_halves_are_register_pests() -> None:
    rows = [
        r
        for r in draft_pests(["Aphids", "White fly", "Aphids and White fly"])
        if r.alias == "aphids and white fly"
    ]
    assert sorted((r.canonical_id, r.reviewed_by) for r in rows) == [
        ("aphids", "rule:split-known"),
        ("white_fly", "rule:split-known"),
    ]


def test_draft_rules_identity_plural_and_human_review() -> None:
    rows = {
        r.alias: r
        for r in draft_pests(["Aphids, Aphid", "Thrips", "Early and late blight", "Shoot and fruit borer"])
    }
    assert (rows["aphid"].canonical_id, rows["aphid"].reviewed_by) == ("aphid", "rule:identity")
    assert (rows["aphids"].canonical_id, rows["aphids"].reviewed_by) == ("aphid", "rule:plural")
    assert (rows["thrips"].canonical_id, rows["thrips"].reviewed_by) == (
        "thrips",
        "rule:identity",
    )  # no "thrip"
    # phrases with "and" are suggestions for a human, never auto-reviewed
    blight = [r for r in draft_pests(["Early and late blight"]) if r.alias == "early and late blight"]
    assert sorted(r.canonical_id for r in blight) == ["early_blight", "late_blight"]
    assert all(r.reviewed_by == "" for r in blight)
    borer = [r for r in draft_pests(["Shoot and fruit borer"]) if r.alias == "shoot and fruit borer"]
    assert [(r.canonical_id, r.reviewed_by) for r in borer] == [("shoot_and_fruit_borer", "")]


def test_pest_lexicon_resolves_many_to_many(tmp_path: Path) -> None:
    path = tmp_path / "pests.csv"
    path.write_text(
        "canonical_id,display_en,alias,lang,reviewed_by\n"
        "early_blight,early blight,early and late blight,en,tarun\n"
        "late_blight,late blight,early and late blight,en,tarun\n"
        "aphid,aphid,aphids,en,rule:plural\n"
        "jassid,jassid,jassids,en,\n"
    )
    lexicon = load_pests(path)
    assert isinstance(lexicon, PestLexicon)
    assert lexicon.ids("Early & late blight") == ("early_blight", "late_blight")
    assert lexicon.ids("APHIDS") == ("aphid",)
    assert lexicon.ids("mealybug") == ()
    assert [r.alias for r in lexicon.unreviewed] == ["jassids"]


def test_variants_draft_and_apply(tmp_path: Path) -> None:
    keys = [
        *["aluminium phosphide", "aluminum phosphide", "aluminum phosphide"],
        *["chlorpyriphos", "chlorpyrifos", "chlorpyrifos", "fipronil"],
        *["lambda-cyhalothrin", "lambda cyhalothrin", "thiamethoxam", "thiamethoxam", "thaimethoxam"],
    ]
    pairs = draft_variants(keys)
    assert {(p.variant, p.canonical) for p in pairs} == {
        (
            "aluminiumphosphide",
            "aluminumphosphide",
        ),  # the more frequent spelling is suggested; a human decides
        ("chlorpyriphos", "chlorpyrifos"),
        ("thaimethoxam", "thiamethoxam"),  # a typo never wins: frequency, not length
    }  # lambda-cyhalothrin = lambda cyhalothrin by the compact rule: no pair, no review
    assert all(p.reviewed_by == "" for p in pairs)
    path = tmp_path / "ingredients.csv"
    path.write_text(
        "variant,canonical,reviewed_by\n"
        "aluminum phosphide,aluminium phosphide,tarun\n"
        "chlorpyrifos,chlorpyriphos,\n"
    )
    variants = load_variants(path)
    assert isinstance(variants, Variants)
    assert variants.canonical("Aluminum Phosphide") == "aluminiumphosphide"
    assert (
        variants.canonical("chlorpyrifos") == "chlorpyriphos"
    )  # dev builds apply drafts; release refuses them
    assert variants.canonical("Lambda-Cyhalothrin") == variants.canonical("lambda cyhalothrin")
    assert len(variants.unreviewed) == 1
    (tmp_path / "bad.csv").write_text("a,b\n")
    with pytest.raises(ValueError, match="header"):
        load_variants(tmp_path / "bad.csv")


def test_plant_part_phrase_is_never_split_even_when_both_halves_exist() -> None:
    # found on the real register: "Shoot" and "Fruit borer" also occur alone, so split-known had fired
    rows = [
        r
        for r in draft_pests(["Shoot", "Fruit borer", "Shoot and fruit borer"])
        if r.alias == "shoot and fruit borer"
    ]
    assert [(r.canonical_id, r.reviewed_by) for r in rows] == [("shoot_and_fruit_borer", "")]


def test_dangling_and_left_by_a_comma_is_not_part_of_a_phrase() -> None:
    assert pest_phrases("Leaf spot, and Powdery mildew") == ("leaf spot", "powdery mildew")
    assert pest_phrases("Sheath blight and, Blast") == ("sheath blight", "blast")
    assert pest_phrases("Thrips, and") == ("thrips",)
    assert pest_phrases("Shoot and fruit borer") == ("shoot and fruit borer",)  # an inner "and" stays


def test_ignore_rows_mark_reviewed_non_pests(tmp_path: Path) -> None:
    path = tmp_path / "pests.csv"
    path.write_text(
        "canonical_id,display_en,alias,lang,reviewed_by\n_ignore,not a pest,diseases viz,en,tarun\n"
    )
    lexicon = load_pests(path)
    assert lexicon.ids("diseases viz") == ()
    assert lexicon.ignored("Diseases viz")
    assert not lexicon.ignored("thrips")


def test_spelling_families_are_candidates_even_below_the_fuzzy_threshold() -> None:
    pairs = draft_variants(["sulphur", "sulphur", "sulfur", "fipronil"])
    assert {(p.variant, p.canonical) for p in pairs} == {("sulfur", "sulphur")}


# --- L2 §13: the matching rule and general terms (written after the code; the engine tests came first) --
def test_match_key_ignores_spacing_hyphens_plurals_and_labels() -> None:
    assert {match_key(t) for t in ("White fly", "Whiteflies", "white-fly", "WHITEFLY")} == {"whitefly"}
    assert match_key("Pests: Brown Plant Hopper") == match_key("brown planthopper")
    assert match_key("Leafspot") == match_key("leaf spot")
    assert match_key("grass") == "grass"  # "-ss" is not a plural
    assert match_key("Bhindi (Okra)") == match_key("bhindi okra")


def test_a_rule_collision_is_reported_but_a_deliberate_multi_mapping_is_not() -> None:
    assert rule_collisions([("White fly", "white_fly"), ("Whiteflies", "whitefly")]) == [
        ("whitefly", ("white_fly", "whitefly"))
    ]
    assert rule_collisions([("White fly", "whitefly"), ("Whiteflies", "whitefly")]) == []
    shared = [("Cabbage & Cauliflower", "cabbage"), ("Cabbage & Cauliflower", "cauliflower")]
    assert rule_collisions(shared) == []


def test_general_term_members_by_head_noun_or_list() -> None:
    pests = {"late_blight": "late blight", "blight": "blight", "blight_spot": "blight spot", "rust": "rust"}
    crops = {"bitter_gourd": "bitter gourd", "ridgegourd": "ridgegourd"}
    terms = [
        GenericTerm("blight", "pest", "head:blight", "t"),
        GenericTerm("gourd", "crop", "list:bitter_gourd;ridgegourd;snake_gourd", "t"),
    ]
    rows, missing = expand(terms, crops, pests)
    assert ("blight", "pest", "late_blight") in rows
    assert ("blight", "pest", "blight") in rows
    assert ("blight", "pest", "blight_spot") not in rows  # the head noun is "spot"
    assert ("gourd", "crop", "ridgegourd") in rows
    assert missing == ["gourd: snake_gourd"]  # a listed ID that does not exist is reported, never kept
