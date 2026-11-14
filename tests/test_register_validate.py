"""L1 §10 `register`, `validate`, `lexicon`, `restrictions`: each invariant fires on a planted defect."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from labelclaim.build import Lexicons, build_tables
from labelclaim.errors import ProvenanceError
from labelclaim.extract.model import Col, Field, ProductHeading, Section, TextLine, UseRow
from labelclaim.normalize.ingredients import Variants
from labelclaim.normalize.lexicon import CropEntry, CropLexicon, key, load_crops, split_pests, suggest
from labelclaim.normalize.pests import PestEntry, PestLexicon
from labelclaim.normalize.quantities import Quantity
from labelclaim.register.writer import canonical_hash, open_readonly, write
from labelclaim.restrictions import parse_restrictions
from labelclaim.sources import SourceDocument
from labelclaim.validate import (
    check_digits,
    check_duplicates,
    check_incomplete,
    check_provenance,
    check_sections,
)
from tests.tablekit import make_table

PRODUCT = ProductHeading("doc", Section.INSECTICIDE_SINGLE, "X 5% EC", 3, (36.0, 0.0, 567.0, 10.0))
BOX = (36.0, 100.0, 135.0, 121.0)
PEST_BOX = (135.0, 100.0, 290.0, 121.0)


def use(crop: str = "Rice", pest: str = "Hopper", page: int = 3, row: int = 2) -> UseRow:
    fields = {c: Field("", (), "cell") for c in Col}
    fields[Col.CROP] = Field(crop, ((page, BOX),), "cell")
    fields[Col.PEST] = Field(pest, ((page, PEST_BOX),), "cell")
    return UseRow(PRODUCT, fields, ((page, 0, row),))


# --- register ---------------------------------------------------------------------------------------


def test_same_rows_in_any_insert_order_give_the_same_hash(tmp_path: Path) -> None:
    rows = [(1, "a", "A"), (2, "b", "B"), (3, "c", "C")]
    h1 = write(tmp_path / "1.sqlite", {"ingredient": rows}, {"x": "1"})
    h2 = write(tmp_path / "2.sqlite", {"ingredient": list(reversed(rows))}, {"x": "2"})
    assert h1 == h2  # build_info (dates, flags) is excluded from the canonical dump
    h3 = write(tmp_path / "3.sqlite", {"ingredient": rows[:2]}, {"x": "1"})
    assert h3 != h1


def test_register_is_opened_read_only(tmp_path: Path) -> None:
    path = tmp_path / "r.sqlite"
    build_hash = write(path, {"ingredient": [(1, "a", "A")]}, {})
    conn = open_readonly(path)
    assert conn.execute("SELECT value FROM build_info WHERE key='build_hash'").fetchone()[0] == build_hash
    assert canonical_hash(conn) == build_hash
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO ingredient VALUES (2, 'b', 'B')")
    conn.close()


# --- validate ---------------------------------------------------------------------------------------


def test_provenance_recheck_passes_and_catches_a_planted_mismatch() -> None:
    page_text = {(3, BOX): "Rice", (3, PEST_BOX): "Hopper"}
    assert check_provenance([use()], lambda page, box: page_text.get((page, box), "")) == 2
    with pytest.raises(ProvenanceError):
        check_provenance([use(crop="Wheat")], lambda page, box: page_text.get((page, box), ""))


def test_incomplete_and_duplicate_rows_become_anomalies() -> None:
    assert [a.detail for a in check_incomplete("doc", [use(pest="")])] == ["PEST is empty"]
    kept, dupes = check_duplicates("doc", [use(row=2), use(row=3), use(pest="Aphid", row=4)])
    assert len(kept) == 2
    assert [(a.code, a.row) for a in dupes] == [("DUPLICATE_ROW", 3)]


def test_section_drift_is_reported() -> None:
    assert check_sections("doc", "insecticide", {"agri_single": (3, 3)}, [use()]) == []
    drift = check_sections("doc", "insecticide", {"agri_single": (10, 20)}, [use()])
    assert [a.code for a in drift] == ["SECTION_DRIFT"]


def test_digit_invariant_violation_is_a_bug() -> None:
    check_digits(Quantity("1.8", "value", (1.8,), (1.8,), None, ("1.8",), "parsed"))
    with pytest.raises(ProvenanceError):
        check_digits(Quantity("1.8", "value", (2.0,), (2.0,), None, ("2.0",), "parsed"))


# --- lexicon ----------------------------------------------------------------------------------------


def test_key_normalisation() -> None:
    assert key("  Chilli` ") == key("chilli") == "chilli"
    assert key("Cabbage & Cauliflower") == "cabbage and cauliflower"
    assert key("Apple*") == "apple"


def test_suggestions_are_suggestions() -> None:
    assert suggest("Paddy (Rice)") == ("rice", "crop")
    assert suggest("Stored grain") == ("stored_grain", "storage")
    assert suggest("Plywood") == ("plywood", "structure")


def test_lexicon_rejects_bad_rows_and_reports_unreviewed(tmp_path: Path) -> None:
    good = tmp_path / "crops.csv"
    good.write_text(
        "canonical_id,display_en,alias,lang,category,reviewed_by\n"
        "rice,rice,Paddy,en,crop,tarun\nrice,rice,Rice (Paddy),en,crop,\n"
    )
    lexicon = load_crops(good)
    assert [e.canonical_id for e in lexicon.resolve("paddy")] == ["rice"]
    assert len(lexicon.unreviewed) == 1
    bad = tmp_path / "bad.csv"
    bad.write_text("canonical_id,display_en,alias,lang,category,reviewed_by\nRice!,rice,Paddy,en,crop,x\n")
    with pytest.raises(ValueError, match="canonical_id"):
        load_crops(bad)


def test_split_pests() -> None:
    assert split_pests("Thrips, Aphid & White fly") == ("thrips", "aphid", "white fly")
    assert split_pests("Red spider mites (Tetranychus urticae)") == ("red spider mites",)


# --- restrictions -----------------------------------------------------------------------------------


def test_restrictions_sections_and_details() -> None:
    edges3 = (36.0, 80.0, 130.0, 560.0)
    banned = make_table(
        [
            ["A.", "Pesticides Banned for manufacture, import and use.", ""],
            [None, "1.", "Alachlor ( S.O. 3951 (E), dated 08.08.2018)"],
            [
                "B.",
                "Pesticide / Pesticide formulations banned for use but continued to manufacture for export",
                "",
            ],
            [None, "1.", "Captafol 80% Powder ( S.O. 679 (E) dated 17th July 2001)"],
        ],
        edges=edges3,
        page=1,
    )
    restricted = make_table(
        [
            ["S. No.", "Name of Pesticides", "Details of Restrictions"],
            ["4.", "Chlorpyriphos", "Chlorpyriphos is banned for use in Ber, Citrus and Tobacco."],
            ["7.", "DDT", "Use of DDT in Agriculture is withdrawn."],  # the word must not switch the section
        ],
        edges=edges3,
        page=4,
    )
    title = TextLine("r", 4, 50.0, "III. PESTICIDES RESTRICTED FOR USE IN THE COUNTRY")
    found = parse_restrictions([(1, [banned]), (4, [title, restricted])])
    assert [(r.key, r.status) for r in found] == [
        ("alachlor", "banned"),
        ("captafol 80% powder", "banned_for_use"),
        ("chlorpyriphos", "restricted"),
        ("ddt", "restricted"),
    ]
    assert found[0].detail_raw == "S.O. 3951 (E), dated 08.08.2018"
    assert found[2].detail_raw.startswith("Chlorpyriphos is banned for use in Ber")


# --- build tables (L2 §11 A1/A2) --------------------------------------------------------------------


def test_build_tables_links_a_use_to_every_crop_and_pest_its_names_map_to(tmp_path: Path) -> None:
    doc = SourceDocument("ins", "insecticide", "https://x/ins.pdf", "0" * 64, "2026-09-30", 1)
    lexicons = Lexicons(
        CropLexicon(
            (
                CropEntry("tomato", "tomato", "Tomato/Chilli", "en", "crop", "t"),
                CropEntry("chilli", "chilli", "Tomato/Chilli", "en", "crop", "t"),
            )
        ),
        PestLexicon(
            (
                PestEntry("early_blight", "early blight", "early and late blight", "en", "t"),
                PestEntry("late_blight", "late blight", "early and late blight", "en", "t"),
            )
        ),
        Variants(()),
    )
    tables, unknown = build_tables(
        (doc,), [(doc, use(crop="Tomato/Chilli", pest="Early & late blight"))], [], lexicons
    )
    assert unknown == []
    assert sorted(c for _, c in tables["use_record_crop"]) == ["chilli", "tomato"]
    assert sorted(p for _, p, _ in tables["use_record_pest"]) == ["early_blight", "late_blight"]
    _, unknown = build_tables((doc,), [(doc, use(crop="Okra", pest="Mealybug"))], [], lexicons)
    assert sorted(a.code for a in unknown) == ["UNKNOWN_CROP", "UNKNOWN_PEST"]
