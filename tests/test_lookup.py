"""L2 §8 `names` / `engine` over a fixture register (cases written before the engine)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Outcome, Query
from labelclaim.register.writer import open_readonly
from tests.registerkit import USES, build_fixture


@pytest.fixture(scope="module")
def engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    path = tmp_path_factory.mktemp("reg") / "register.sqlite"
    build_fixture(path)
    eng = Engine(path)
    yield eng
    eng.close()


def ids(answer_uses: tuple[object, ...]) -> list[int]:
    return sorted(u.use_id for u in answer_uses)  # type: ignore[attr-defined]


def test_approved_product_crop_pest(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorantraniliprole 18.5% SC", crop="tomato", pest="fruit borer"))
    assert a.outcome is Outcome.APPROVED
    assert ids(a.uses) == [1]
    use = a.uses[0]
    assert (use.dose_ai_raw, use.dose_form_raw, use.dilution_raw, use.wait_raw) == ("30", "150", "500", "3")
    assert use.citation.page_first == 10
    assert use.citation.register_date == "2026-09-30"
    assert "not for legal purposes" in a.disclaimer


def test_ingredient_level_returns_every_formulation(engine: Engine) -> None:
    a = engine.lookup(Query(ingredient="chlorantraniliprole", crop="rice"))
    assert a.outcome is Outcome.APPROVED
    assert ids(a.uses) == [2, 7]


def test_concentration_and_formulation_narrow_the_product(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorantraniliprole 0.4% GR", crop="Paddy"))
    assert ids(a.uses) == [7]


def test_combination_matches_as_a_set(engine: Engine) -> None:
    a = engine.lookup(Query(product="Fipronil 2% + Buprofezin 22% SC", crop="rice", pest="BPH"))
    assert a.outcome is Outcome.APPROVED
    assert ids(a.uses) == [4]


def test_not_approved_for_crop_lists_the_crops_it_is_approved_on(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorpyriphos 20% EC", crop="tomato", pest="fruit borer"))
    assert a.outcome is Outcome.NOT_APPROVED_FOR_CROP
    assert a.uses == ()
    assert a.approved_crops == ("citrus", "cotton")  # the fixture gained a citrus row for the conflict test
    assert ids(a.alternatives) == [1]  # what IS approved on tomato for fruit borer


def test_not_approved_for_pest_lists_the_pests_it_is_approved_for(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorantraniliprole 18.5% SC", crop="tomato", pest="aphids"))
    assert a.outcome is Outcome.NOT_APPROVED_FOR_PEST
    assert a.uses == ()
    assert a.approved_pests == ("fruit borer", "jassid")
    assert a.alternatives == ()


def test_multi_crop_use_is_found_from_either_crop(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorantraniliprole 18.5% SC", crop="chillies", pest="jassid"))
    assert a.outcome is Outcome.APPROVED
    assert ids(a.uses) == [6]


def test_unknown_product_gets_suggestions_but_never_an_answer(engine: Engine) -> None:
    a = engine.lookup(Query(ingredient="chlorantranilprole", crop="tomato"))
    assert a.outcome is Outcome.UNKNOWN_PRODUCT
    assert a.uses == ()
    assert [s.display for s in a.suggestions["product"]][:1] == ["Chlorantraniliprole"]


def test_unknown_crop_gets_suggestions(engine: Engine) -> None:
    a = engine.lookup(Query(ingredient="chlorantraniliprole", crop="tomatto"))
    assert a.outcome is Outcome.UNKNOWN_CROP
    assert [s.id for s in a.suggestions["crop"]][:1] == ["tomato"]


def test_unknown_pest_never_claims_the_pest_is_covered(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorantraniliprole 18.5% SC", crop="tomato", pest="mealybug"))
    assert a.outcome is Outcome.UNKNOWN_PEST
    assert a.uses == ()
    assert ids(a.alternatives) == [1, 6]  # everything approved for this product on the crop, shown as such


def test_alias_mapping_to_two_crops_is_ambiguous(engine: Engine) -> None:
    a = engine.lookup(Query(ingredient="chlorantraniliprole", crop="Tomato/Chilli"))
    assert a.outcome is Outcome.AMBIGUOUS
    assert sorted(s.id for s in a.suggestions["crop"]) == ["chilli", "tomato"]


def test_spelling_variant_and_restriction_overlay(engine: Engine) -> None:
    a = engine.lookup(Query(product="Chlorpyrifos 20% EC", crop="cotton", pest="aphid"))
    assert a.outcome is Outcome.APPROVED
    assert ids(a.uses) == [3]
    assert [(r.ingredient, r.status) for r in a.restrictions] == [("Chlorpyriphos", "restricted")]
    assert a.restrictions[0].detail_raw.startswith("Chlorpyriphos is banned for use in Ber")


def test_restriction_overlay_on_a_not_approved_answer_too(engine: Engine) -> None:
    a = engine.lookup(Query(ingredient="monocrotophos", crop="tomato"))
    assert a.outcome is Outcome.NOT_APPROVED_FOR_CROP
    assert [r.status for r in a.restrictions] == ["restricted"]


def test_raw_fields_are_copied_verbatim(engine: Engine, tmp_path: Path) -> None:
    raw = {u[0]: u for u in USES}
    for q in (
        Query(ingredient="chlorantraniliprole", crop="rice"),
        Query(product="Buprofezin 22% + Fipronil 2% SC", crop="rice"),
    ):
        for use in engine.lookup(q).uses:
            row = raw[use.use_id]
            assert (
                use.crop_raw,
                use.pest_raw,
                use.dose_ai_raw,
                use.dose_form_raw,
                use.dilution_raw,
                use.wait_raw,
            ) == row[2:8]


def test_query_needs_exactly_one_of_product_or_ingredient() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        Query(product="X 5% EC", ingredient="x", crop="rice")
    with pytest.raises(ValueError, match="exactly one"):
        Query(crop="rice")


def test_register_info(engine: Engine) -> None:
    info = engine.register_info()
    assert info.dates == {"ins": "2026-09-30"}
    assert len(info.build_hash) == 64


def test_engine_opens_the_register_read_only(tmp_path: Path) -> None:
    path = tmp_path / "r.sqlite"
    build_fixture(path)
    conn = open_readonly(path)
    with pytest.raises(Exception, match=r"readonly|read-only"):
        conn.execute("DELETE FROM use_record")
    conn.close()


def test_register_use_that_a_restriction_names_is_a_conflict(engine: Engine) -> None:
    # real case: the 30.09.2026 register lists Chlorpyriphos on Ber; the restriction list bans it on Ber
    a = engine.lookup(Query(product="Chlorpyriphos 20% EC", crop="citrus"))
    assert a.outcome is Outcome.APPROVED  # the register's own claim is reported as it is ...
    assert a.restrictions[0].names_the_crop
    assert a.conflict  # ... but flagged, so a client shows the restriction first
    cotton = engine.lookup(Query(product="Chlorpyriphos 20% EC", crop="cotton", pest="aphid"))
    assert not cotton.restrictions[0].names_the_crop
    assert not cotton.conflict
