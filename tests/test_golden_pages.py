"""Golden rows from the real register (L1 §10). Opt-in: `pytest -m corpus` (needs the PDFs in the cache).

Every expected value below was typed from a rendered image of the page region (pdftoppm -r 110), not
copied from the extractor's output. Labeller: the assistant (Claude), 2026-11-13. Line breaks inside a
cell are written as single spaces; comparison collapses whitespace only.

Two labels were corrected after a mismatch, with evidence (insecticide p. 8): the image reads
"Indianhouse rat" and "rat,Field", but the PDF's characters are "Indian house rat" and "rat, Field" (a
space character with a zero or negative gap, so invisible when rendered). Checked with pdfplumber's chars.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from labelclaim.extract.assemble import Assembly, assemble
from labelclaim.extract.model import Col, UseRow
from labelclaim.extract.pages import read_document
from labelclaim.sources import ensure_cached, load_manifest

pytestmark = pytest.mark.corpus
REPO = Path(__file__).resolve().parents[1]


@cache
def extracted(kind: str) -> Assembly:
    doc = next(d for d in load_manifest(REPO / "data" / "sources.toml") if d.kind == kind)
    return assemble(doc.id, read_document(ensure_cached(doc, offline=True), doc.id))


def norm(text: str) -> str:
    return " ".join(text.split())


def find(kind: str, page: int, crop: str, pest_prefix: str) -> list[UseRow]:
    return [
        u
        for u in extracted(kind).uses
        if u.page_first == page
        and norm(u.fields[Col.CROP].text) == crop
        and norm(u.fields[Col.PEST].text).startswith(pest_prefix)
    ]


def values(use: UseRow) -> tuple[str, ...]:
    return tuple(norm(use.fields[c].text) for c in Col)


def one(kind: str, page: int, crop: str, pest_prefix: str) -> UseRow:
    rows = find(kind, page, crop, pest_prefix)
    assert len(rows) == 1, f"{kind} p{page} {crop}/{pest_prefix}: {[values(r) for r in rows]}"
    return rows[0]


def test_ins_p20_merged_crop_dilution_and_waiting_period() -> None:
    expected = [
        ("Maize", "Fall Army Worm", "1.8", "3", "-", "NA"),
        ("Maize", "Stem Borer", "1.2", "2", "-", "NA"),
        ("Maize", "Cut Worm", "1.2", "2", "-", "NA"),
    ]
    for row in expected:
        use = one("insecticide", 20, row[0], row[1])
        assert values(use) == row
        assert use.product.text == "Cyantraniliprole 48% w/w FS"


def test_ins_p60_combination_table_with_split_grid() -> None:
    use = one(
        "insecticide", 60, "Rice", "Brown plant hopper, White backed plant hopper, Leaf Folder, Green Leaf"
    )
    assert values(use)[2:] == ("176", "800", "400", "15")


def test_ins_p67_68_value_split_by_the_page_break() -> None:
    use = one("insecticide", 67, "Cotton", "Thrips, Mites and Whitefly")
    assert use.product.text == "Diafenthiuron 40.1 % + Acetamiprid 3.9 % w/w WP"
    assert values(use)[2:] == ("(200.5 + 19.5 – (240.6 + 23.4)", "500 - 600", "500", "21")
    assert use.page_last == 68
    chilli = one("insecticide", 68, "Chilli", "Thrips, Mites and Whitefly")
    assert values(chilli)[2:] == ("(200.5 + 19.5 – (240.6 + 23.4)", "500 - 600", "500", "21")


def test_ins_p51_five_column_seed_treatment_layout() -> None:
    okra = one("insecticide", 51, "Okra (Bhindi)", "Jassids")
    assert values(okra)[2:5] == ("01.7", "5.7", "This is used as seed dresser")
    assert okra.fields[Col.WAIT].source == "absent"
    maize = [
        u for u in find("insecticide", 51, "Maize", "Aphids") if u.product.text == "Thiamethoxam 30 % FS"
    ]
    assert [values(u)[2:5] for u in maize] == [("1.8 g a i/kg seed", "6 ml/kg seed", "10-12 ml/kg seed")]
    cotton = one("insecticide", 51, "Cotton", "Aphids Jassids White fly and Thrips")
    assert values(cotton)[2:5] == ("2.4 - 3 g a i/kg seed", "8-10 ml/kg seed", "10-15 ml/kg seed")


def test_ins_p8_second_product_with_its_own_column_widths() -> None:
    (paddy,) = [
        u
        for u in find("insecticide", 8, "Paddy (Rice)", "Field Rat")
        if u.product.text == "Bromadiolone 00.005 % RB"
    ]
    assert values(paddy) == (
        "Paddy (Rice)",
        "Field Rat, Large Bandicota, Indian house rat",  # label corrected from the PDF's chars (see top)
        "0.005",
        "-",
        "-",
        "-",
    )
    (coconut,) = [
        u
        for u in find("insecticide", 8, "Coconut/ Bamboo", "Indian house rat")
        if u.product.text == "Bromadiolone 00.005 % RB"
    ]
    # label corrected from the PDF's chars: a space char sits after the comma (gap -0.11 pt, so invisible)
    assert values(coconut)[1:] == ("Indian house rat, Field Rat Large Bandicota", "0.005", "-", "-", "-")


def test_fun_p15_16_unruled_row_rebuilt_from_words() -> None:
    (tomato,) = [
        u for u in find("fungicide", 15, "Tomato", "Early blight") if u.product.text == "Kitazin 48% EC"
    ]
    assert values(tomato)[2:] == (
        "0.10% or100 Gram in 100lit. Of water",
        "0.20%or 200mlin 200lt. of water",
        "As required depending upon crop Stage and plant protection equipment used",
        "5",
    )
    rice = one("fungicide", 15, "Rice (Paddy)", "Blast, Sheath blight")
    assert values(rice)[5] == "15"


def test_fun_p38_39_pest_split_by_page_break_with_a_second_application() -> None:
    pest = "Leaf spots (Alternaria, Cercospora & Myrothecium)"
    knapsack = one("fungicide", 38, "Soybean", "Leaf spots")
    assert values(knapsack)[1:] == (pest, "215-258", "500-600", "500", "28")
    drone = one("fungicide", 39, "Soybean", "Leaf spots")
    assert values(drone)[1:] == (pest, "258", "600", "20 L (via Drone application)", "28")


def test_fun_p54_pest_and_dilution_split_over_grid_rows() -> None:
    use = one("fungicide", 54, "Pomegranate", "Cercospora Leaf")
    assert values(use)[1:] == (
        "Cercospora Leaf spot ,Alternaria Leaf spot and Anthracnose",
        "1.125 g/l",
        "1.5 g/l",
        "500 -750 L (depending upon tree size)",
        "07",
    )


def test_fun_p76_dose_range_split_over_grid_rows() -> None:
    tomato = one("fungicide", 76, "Tomato", "Late Blight, Early")
    assert values(tomato)[1:] == (
        "Late Blight, Early Blight, Powdery Mildew",
        "136 (12 + 124) – 153 (13.5 + 139.5)",
        "800-900",
        "500",
        "05",
    )
    cucumber = one("fungicide", 76, "Cucumber", "Downy Mildew")
    assert values(cucumber)[1:3] == (
        "Downy Mildew, Powdery Mildew and Alternaria Leaf Spots",
        "136 (12 + 124) – 153 (13.5 + 139.5)",
    )


def test_fun_p20_value_spanning_two_columns_is_not_duplicated() -> None:
    chilli = one("fungicide", 20, "Chilli", "Damping Off")
    assert values(chilli)[2:] == ("0.64", "2.0", "", "used as seed dresser")
    assert chilli.fields[Col.DILUTION].source == "spanned"
    millet = one("fungicide", 20, "Pearl millet", "Downey mildew")
    assert values(millet)[2:] == ("0.64", "2.0", "", "76")


def test_only_reviewed_anomalies_remain() -> None:
    """Exactly the anomalies seen and explained in the M1 audit; anything new fails here first."""
    ins = {(a.code, a.page) for a in extracted("insecticide").anomalies}
    fun = {(a.code, a.page) for a in extracted("fungicide").anomalies}
    # Text crossing cell lines (L1 §16, reports/E1/edge_audit.md): each is corrected or allowed by text.
    ins_edges = {("CELL_ORPHAN", 25), ("CELL_STRADDLE", 55), ("CELL_STRADDLE", 80), ("CELL_OVERLAP", 84)}
    fun_edges = {("CELL_STRADDLE", 60), ("CELL_STRADDLE", 73), ("CELL_STRADDLE", 76), ("CELL_ORPHAN", 77),
                 ("CELL_OVERLAP", 82), ("CELL_STRADDLE", 84)}  # fmt: skip
    assert ins == {("UNMAPPED_TABLE", 7)} | ins_edges  # p. 7: rodenticide table, a 3-4 column layout
    assert fun == {("DANGLING_MERGE", 77)} | fun_edges  # p. 77: the Mango a.i. cell has no borders (C-09)
    cell_hits = [
        a for k in ("insecticide", "fungicide") for a in extracted(k).anomalies if a.code[:5] == "CELL_"
    ]
    assert len(cell_hits) == 12
