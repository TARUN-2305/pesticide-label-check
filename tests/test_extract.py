"""L1 §10 `geometry`, `classify`, `assemble` over synthetic geometry.

The real pages are covered by test_golden_pages.py."""

from __future__ import annotations

import dataclasses

from labelclaim.extract.assemble import assemble
from labelclaim.extract.classify import classify_row, heading_like, section_of
from labelclaim.extract.geometry import band_row, row_bands
from labelclaim.extract.model import Col, EdgeDefect, PageItem, RowKind, Section, TextLine
from tests.tablekit import EDGES, heading, make_table

SECTION_ROW = heading("Agricultural Use")
HEADER_1 = ["Crop", "Common Name of the pest", ("Dosage/ha", 3, 1), None, None, "Waiting Period (days)"]
HEADER_2 = ["", "", "a.i (gm)", "Formulation (gm/ml)", "Dilution in Water (Liter)", ""]

# --- geometry ---------------------------------------------------------------------------------------


def test_bands_from_modal_six_cell_signature() -> None:
    table = make_table([heading("Abamectin 01.90 % EC"), ["Rose", "Mites", "1", "2", "500", "3"]])
    bands, inherited = row_bands(table, None)
    assert bands == [EDGES, EDGES]
    assert not inherited


def test_bands_inherited_only_when_outer_edges_match() -> None:
    lone = make_table([heading("Acequinocyl 15% w/v SC"), [None, ("note", 5, 1), None, None, None, None]])
    assert row_bands(lone, EDGES) == ([EDGES, EDGES], True)
    shifted_edges = (80.0, 135.0, 290.0, 378.0, 448.0, 520.0, 567.0)
    shifted = make_table(
        [heading("X 5% EC"), [None, ("note", 5, 1), None, None, None, None]], edges=shifted_edges
    )
    assert row_bands(shifted, EDGES) == ([EDGES, None], False)


def test_each_product_block_gets_its_own_bands() -> None:
    # insecticide p. 8: one pdfplumber table, two products with different column widths
    other = (36.0, 190.0, 329.0, 374.0, 473.0, 536.0, 567.0)
    first = make_table([heading("A 1% EC"), ["Residential", "Field rat", "0.005", "-", "-", "-"]])
    second = make_table(
        [heading("Bromadiolone 0.005% CB"), ["Paddy (Rice)", "Field rat", "0.005", "-", "-", "-"]],
        edges=other,
    )
    table = make_table([])
    combined = type(table)("doc", 8, 0, (36.0, 100.0, 567.0, 200.0), first.rows + second.rows)
    bands, _ = row_bands(combined, None)
    assert bands[1] == EDGES
    assert bands[3] == other
    assert band_row(combined, 3, other).text(Col.CROP) == "Paddy (Rice)"


def test_cells_assigned_by_centre_and_concatenated_left_to_right() -> None:
    # 7 cells: the a.i. column is split in two (a misaligned inner line), both halves land in DOSE_AI
    edges7 = (36.0, 135.0, 290.0, 330.0, 378.0, 448.0, 520.0, 567.0)
    table = make_table(
        [["Rice", "Brown plant hopper", "110", "+ 15", "500", "400", "32"], ["A", "B", "1", "2", "3", "4"]],
        edges=edges7,
    )
    row = band_row(table, 0, EDGES)
    assert row.text(Col.DOSE_AI) == "110 + 15"
    assert row.text(Col.WAIT) == "32"
    assert row.spans == {}
    assert row.outside == ()


def test_spanning_cell_owns_its_centre_band_and_spans_the_other() -> None:
    # fungicide p. 20: "2.0" is one cell across the formulation and dilution columns
    table = make_table([["Chilli", "Damping Off", "0.64", ("2.0", 2, 1), None, "used as seed dresser"]])
    row = band_row(table, 0, EDGES)
    assert row.text(Col.DOSE_FORM) == "2.0"
    assert row.covered(Col.DILUTION)
    assert row.spans[Col.DILUTION].text == "2.0"


def test_heading_rows_including_a_split_heading_cell() -> None:
    table = make_table(
        [
            heading("Abamectin 01.90 % EC"),
            ["Flutriafol 23% w/w SC", ("", 5, 1), None, None, None, None],  # fungicide p. 13
            [None, ("(Apply first spray during flush)", 5, 1), None, None, None, None],
        ]
    )
    assert band_row(table, 0, EDGES).full_width is not None
    split = band_row(table, 1, EDGES).full_width
    assert split is not None
    assert split.text == "Flutriafol 23% w/w SC"
    note = band_row(table, 2, EDGES)
    assert note.full_width is None
    assert len(note.spanning()) == 1


# --- classify ---------------------------------------------------------------------------------------


def kind(spec: list[list[object]], row: int, *, continuation_allowed: bool = False) -> RowKind:
    table = make_table(spec)  # type: ignore[arg-type]
    return classify_row(band_row(table, row, EDGES), continuation_allowed=continuation_allowed)


def test_classification_rules() -> None:
    data = ["Maize", "Fall Army Worm", "1.8", "3", "-", "NA"]
    assert kind([SECTION_ROW, data], 0) is RowKind.SECTION
    assert kind([heading("Abamectin 01.90 % EC"), data], 0) is RowKind.PRODUCT  # digits, still a heading
    assert kind([heading("➢ For non- agricultural use: protect buildings"), data], 0) is RowKind.NOTE
    assert kind([HEADER_1, HEADER_2, data], 0) is RowKind.HEADER
    assert kind([HEADER_1, HEADER_2, data], 1) is RowKind.HEADER
    assert kind([data], 0) is RowKind.DATA
    assert kind([["", "", "", "", "", ""], data], 0) is RowKind.BLANK
    assert (
        kind([[None, ("(Apply first spray during flush)", 5, 1), None, None, None, None], data], 0)
        is RowKind.NOTE
    )
    assert kind([["Potato", "Aphids:", "", "", "", ""], data], 0) is RowKind.UNMAPPED


def test_values_from_merges_still_data() -> None:
    spec = [
        [("Maize", 1, 2), "Fall Army Worm", "1.8", "3", ("-", 1, 2), ("NA", 1, 2)],
        [None, "Stem Borer", None, None, None, None],
    ]
    assert kind(spec, 1) is RowKind.DATA


def test_continuation_only_at_the_top_of_a_table() -> None:
    split = ["", "partellus)", "", "", "Dresser", ""]  # insecticide p. 15: a row split by the page break
    assert kind([split], 0, continuation_allowed=True) is RowKind.CONTINUATION
    assert kind([split], 0, continuation_allowed=False) is RowKind.DATA


def test_section_and_heading_text_lines() -> None:
    assert section_of("2. Fungicides Combination Uses") is Section.FUNGICIDE_COMBINATION
    assert section_of("2. Fungicides combination uses (Page No. – 42 to 79)") is None  # the index line
    assert heading_like("Tebuconazole 15% + Zineb 57% WDG")
    assert heading_like("Cyclobutrifluram 38.4% w/w SC (Import only)")
    assert not heading_like("Tomato Early blight 0.10% 0.20%or As required 5")


# --- assemble ---------------------------------------------------------------------------------------


def run(*items: PageItem) -> tuple[list[dict[Col, str]], list[str]]:
    pages: dict[int, list[PageItem]] = {}
    for item in items:
        pages.setdefault(item.page, []).append(item)
    result = assemble("doc", sorted(pages.items()))
    rows = [{c: f.text for c, f in u.fields.items()} for u in result.uses]
    return rows, [a.code for a in result.anomalies]


def test_merged_crop_and_values_inherited_within_table() -> None:
    # insecticide p. 20: Maize spans 3 rows; Dilution and Waiting Period span the same 3 rows
    table = make_table(
        [
            SECTION_ROW,
            heading("Cyantraniliprole 48% w/w FS"),
            [("Maize", 1, 3), "Fall Army Worm", "1.8", "3", ("-", 1, 3), ("NA", 1, 3)],
            [None, "Stem Borer", "1.2", "2", None, None],
            [None, "Cut Worm", "1.2", "2", None, None],
        ]
    )
    rows, anomalies = run(table)
    assert anomalies == []
    assert [r[Col.PEST] for r in rows] == ["Fall Army Worm", "Stem Borer", "Cut Worm"]
    assert {r[Col.CROP] for r in rows} == {"Maize"}
    assert [r[Col.WAIT] for r in rows] == ["NA", "NA", "NA"]
    assert [r[Col.DOSE_AI] for r in rows] == ["1.8", "1.2", "1.2"]


def test_page_break_continuation_appends_to_previous_row() -> None:
    first = make_table(
        [
            SECTION_ROW,
            heading("Abamectin 01.90 % EC"),
            ["Cabbage", "Diamond back moth (Plutella", "25", "125", "500", "1"],
        ],
        page=7,
    )
    second = make_table(
        [["", "xylostella)", "", "", "", ""], ["Chilli", "Mites", "5", "10", "500", "3"]], page=8
    )
    result = assemble("doc", [(7, [first]), (8, [second])])
    assert [u.fields[Col.PEST].text for u in result.uses] == [
        "Diamond back moth (Plutella xylostella)",
        "Mites",
    ]
    assert result.uses[0].page_last == 8


def test_covered_crop_at_page_top_is_carried_from_previous_page() -> None:
    first = make_table(
        [
            SECTION_ROW,
            heading("Abamectin 01.90 % EC"),
            ["Bhindi (Okra)", "Shoot & fruit borer", "10", "400", "500", "01"],
        ],
        page=22,
    )
    second = make_table([[None, "Jassid", "10", "400.0", "400 – 600", "01"]], page=23)
    result = assemble("doc", [(22, [first]), (23, [second])])
    assert [u.fields[Col.CROP].text for u in result.uses] == ["Bhindi (Okra)", "Bhindi (Okra)"]
    assert result.uses[1].fields[Col.CROP].source == "carried"


def test_blank_crop_mid_table_means_same_crop_and_is_marked() -> None:
    table = make_table(
        [
            SECTION_ROW,
            heading("X 5% EC"),
            ["Paddy", "Stem borer", "1", "2", "3", "4"],
            ["", "Leaf folder", "5", "6", "7", "8"],
        ]
    )
    result = assemble("doc", [(5, [table])])
    assert [u.fields[Col.CROP].text for u in result.uses] == ["Paddy", "Paddy"]
    assert result.uses[1].fields[Col.CROP].source == "blank"


def test_rows_before_any_product_are_orphans() -> None:
    _, anomalies = run(make_table([SECTION_ROW, ["Rice", "Hopper", "1", "2", "3", "4"]]))
    assert anomalies == ["ORPHAN_ROW"]


def test_out_of_scope_section_is_skipped_until_next_in_scope_section() -> None:
    table = make_table(
        [
            heading("PUBLIC HEALTH USE"),
            heading("Temephos 50% EC"),
            ["Public health", "Mosquito", "1", "2", "3", "4"],
            heading("Combination Product"),
            heading("A 1% + B 2% SC"),
            ["Rice", "Hopper", "1", "2", "3", "4"],
        ]
    )
    result = assemble("doc", [(88, [table])])
    assert [u.fields[Col.CROP].text for u in result.uses] == ["Rice"]
    assert result.uses[0].product.section is Section.INSECTICIDE_COMBINATION


def test_heading_as_text_line_and_stray_text_is_an_anomaly() -> None:
    table1 = make_table([heading("2. Fungicides Combination Uses")], page=87)
    line = TextLine("doc", 87, 400.0, "Tebuconazole 15% + Zineb 57% WDG")
    stray = TextLine("doc", 87, 420.0, "Tomato Early blight 0.10% 0.20%or As required 5")
    table2 = make_table([["Groundnut", "Leaf spot", "1", "2", "3", "4"]], page=87, index=1, top=450.0)
    result = assemble("doc", [(87, [table1, line, stray, table2])])
    assert [u.product.text for u in result.uses] == ["Tebuconazole 15% + Zineb 57% WDG"]
    assert [a.code for a in result.anomalies] == ["TEXT_OUTSIDE_TABLE"]


def test_covered_value_mid_table_without_anchor_is_dangling() -> None:
    table = make_table(
        [
            SECTION_ROW,
            heading("X 5% EC"),
            ["Paddy", "Stem borer", "1", "2", "3", "4"],
            ["Wheat", "Aphid", "5", "6", None, "8"],
        ]
    )
    _, anomalies = run(table)
    assert anomalies == ["DANGLING_MERGE"]


def test_notes_attach_to_the_product_or_last_row() -> None:
    table = make_table(
        [
            SECTION_ROW,
            heading("X 5% EC"),
            heading("➢ For non- agricultural use: termites"),
            ["Paddy", "Stem borer", "1", "2", "3", "4"],
            [None, ("(Apply at flush)", 5, 1), None, None, None, None],
        ]
    )
    result = assemble("doc", [(5, [table])])
    assert result.products[0].notes == ("➢ For non- agricultural use: termites",)
    assert result.uses[0].notes == ("(Apply at flush)",)


def test_a_heading_cell_that_stops_short_of_the_right_edge_starts_a_new_product() -> None:
    # Fungicide p. 59 (found by E3): the heading's cell ends mid-table (x 72-417 of 72-582), so it is
    # not full width. It had been kept as a note of the row above, and the Paddy row below was then
    # credited to the previous product, a false approval (E3-086).
    short = [("Chlorantraniliprole 0.64% + Tebuconazole 3% + Clothianidin 1.92% GR", 4, 1)] + [None] * 5
    table = make_table(
        [
            SECTION_ROW,
            heading("Chlorothalonil 40% + Thiophanate Methyl 35% WDG"),
            ["Groundnut", "Tikka, Rust", "600+525", "1500", "500", "27"],
            short,
            ["Paddy", "Yellow Stem Borer and Sheath Blight", "40+187.5+120", "6250", "-", "46"],
        ]
    )
    result = assemble("doc", [(59, [table])])
    assert [p.text for p in result.products] == [
        "Chlorothalonil 40% + Thiophanate Methyl 35% WDG",
        "Chlorantraniliprole 0.64% + Tebuconazole 3% + Clothianidin 1.92% GR",
    ]
    assert [u.product.text[:12] for u in result.uses] == ["Chlorothalon", "Chlorantrani"]
    assert result.uses[0].notes == ()


def test_a_heading_cell_after_an_empty_sliver_cell_is_a_product() -> None:
    # fungicide p. 83 and p. 85: an empty 6-8 pt cell sits left of the heading cell
    data = ["Chilli", "Anthracnose", "1", "2", "3", "4"]
    sliver = ["", ("Sedaxane 2.36% w/w + Fludioxonil 2.36% w/w FS", 3, 1), None, None, ("", 2, 1), None]
    assert kind([sliver, data], 0) is RowKind.PRODUCT


def test_a_heading_like_note_that_does_not_start_at_the_left_edge_stays_a_note() -> None:
    data = ["Paddy", "Stem borer", "1", "2", "3", "4"]
    indented = [None, ("Mix 0.5% solution of X 20% EC", 5, 1), None, None, None, None]
    assert kind([indented, data], 0) is RowKind.NOTE


def test_spanned_value_is_not_duplicated_and_not_an_anomaly() -> None:
    table = make_table(
        [
            SECTION_ROW,
            heading("Metalaxyl 35% WS"),
            ["Chilli", "Damping Off", "0.64", ("2.0", 2, 1), None, "seed dresser"],
            ["Pearl millet", "Downy mildew", "0.64", "2.0", "1.0", "76"],
        ]
    )
    result = assemble("doc", [(20, [table])])
    assert result.anomalies == []
    fields = result.uses[0].fields
    assert fields[Col.DOSE_FORM].text == "2.0"
    assert fields[Col.DILUTION].text == ""
    assert fields[Col.DILUTION].source == "spanned"
    assert fields[Col.DILUTION].span_of is Col.DOSE_FORM


def test_continuation_at_the_top_of_a_second_table_on_the_same_page() -> None:
    # fungicide p. 3: pdfplumber splits one Word table into two; the second starts with the rest of a row
    t0 = make_table(
        [SECTION_ROW, heading("X 5% WP"), ["Groundnut", "Tikka leaf", "1", "2", "3", "4"]], page=3
    )
    t1 = make_table(
        [["", "spot", "", "", "", ""], ["Rice", "Blast", "5", "6", "7", "8"]], page=3, index=1, top=400.0
    )
    result = assemble("doc", [(3, [t0, t1])])
    assert [u.fields[Col.PEST].text for u in result.uses] == ["Tikka leaf spot", "Blast"]
    assert result.anomalies == []


def test_continuation_after_a_new_product_is_an_orphan() -> None:
    t0 = make_table([SECTION_ROW, heading("X 5% WP"), ["Groundnut", "Tikka", "1", "2", "3", "4"]], page=3)
    t1 = make_table([heading("Y 2% EC"), ["", "spot", "", "", "", ""]], page=4)
    result = assemble("doc", [(3, [t0]), (4, [t1])])
    assert [a.code for a in result.anomalies] == ["UNMAPPED_ROW"]  # not appended across products
    assert result.uses[0].fields[Col.PEST].text == "Tikka"


def test_merged_cell_started_on_previous_page_takes_the_completed_value() -> None:
    # insecticide p. 14/15: "Seed" ends p. 14; the rest of the merged cell ("Dresser") and an empty crop
    # cell open p. 15 and also cover the next row
    first = make_table(
        [SECTION_ROW, heading("X 5% FS"), ["Maize", "Spotted Stemborer (Chilo", "40", "64", "Seed", "-"]],
        page=14,
    )
    second = make_table(
        [
            [("", 1, 2), "partellus)", "", "", ("Dresser", 1, 2), ("", 1, 2)],
            [None, "Fall army worm", "70", "112", None, None],
            ["Wheat", "Termite", "1", "2", "3", "4"],
        ],
        page=15,
    )
    result = assemble("doc", [(14, [first]), (15, [second])])
    assert result.anomalies == []
    fall = result.uses[1].fields
    assert fall[Col.CROP].text == "Maize"
    assert fall[Col.DILUTION].text == "Seed Dresser"
    assert fall[Col.CROP].source == "carried"


def test_pest_text_one_grid_row_below_its_values() -> None:
    # fungicide p. 81: the Cotton row's pest cell is empty; the pest sits in the next grid row
    table = make_table(
        [
            SECTION_ROW,
            heading("Pydiflumetofen 7% + Difenoconazole 12.5% SC"),
            [("Cotton", 1, 2), "", ("165 (90+75)", 1, 2), ("600", 1, 2), ("500", 1, 2), ("30", 1, 2)],
            [None, "Leaf spot, Boll rot", None, None, None, None],
        ]
    )
    result = assemble("doc", [(81, [table])])
    assert [
        (u.fields[Col.CROP].text, u.fields[Col.PEST].text, u.fields[Col.WAIT].text) for u in result.uses
    ] == [("Cotton", "Leaf spot, Boll rot", "30")]


# Added after mutation checks M1 and M10 survived (reports/M1/mutants.md): each test closes one gap.


def test_cell_starting_slightly_left_of_its_band_maps_by_centre() -> None:
    # a pest cell whose left edge sits 1.5 pt left of the band edge (misaligned grid line) is still PEST
    table = make_table([["Rice", "Hopper", "1", "2", "3", "4"]])
    shifted = type(table.rows[0].cells[1])("Hopper", (133.5, 100.0, 290.0, 121.0))
    row = type(table.rows[0])((table.rows[0].cells[0], shifted, *table.rows[0].cells[2:]), table.rows[0].bbox)
    table = type(table)(table.doc_id, table.page, table.index, table.bbox, (row,))
    assert band_row(table, 0, (36.0, 135.0, 290.0, 378.0, 448.0, 520.0, 567.0)).text(Col.PEST) == "Hopper"


def test_note_like_full_width_cells_are_notes_not_products() -> None:
    data = ["Sugarcane", "Termite", "1", "2", "3", "4"]
    assert kind([heading("Sugarcane: 6.25 lit/ha."), data], 0) is RowKind.NOTE
    assert (
        kind([heading("Lambda-cyhalothrin 22.8% CS is a manufacturing concentrate"), data], 0) is RowKind.NOTE
    )
    assert kind([heading("^ Calculated as 550 gm a.i./ha"), data], 0) is RowKind.NOTE
    assert (
        kind([heading("(Streptomycin Sulphate 90% + Tetracycline Hydrochloride 10%) SP"), data], 0)
        is RowKind.PRODUCT
    )


def test_header_block_with_unit_digits_is_a_header_not_data() -> None:
    # insecticide p. 23: a sub-table header read as data before the M2 audit
    row1 = ["Name Of Insect Pest", "Dosage", "", "", "", ""]
    row2 = [
        "Name Of Insect Pest",
        "Infestation",
        "Requirement mg a.i./m2",
        "Formulation (ml)/ litre water",
        "Spray solution (ml)/ m2",
        "",
    ]
    data = ["Mosquito", "High", "25", "0.1", "50", ""]
    assert kind([row1, data], 0) is RowKind.HEADER
    assert kind([row2, data], 0) is RowKind.HEADER
    assert kind([data], 0) is RowKind.DATA


def test_an_edge_defect_becomes_an_anomaly_on_the_row_it_sits_in() -> None:
    # insecticide p. 25: the crop text "Cotton" lies in no cell. Without this anomaly the row silently
    # took the crop of the row above (Brinjal), a wrong fact (reports/E1/edge_audit.md #2).
    table = make_table(
        [
            SECTION_ROW,
            heading("Dimpropyridaz 120 g/l SL"),
            ["Brinjal", "White fly", "108", "900", "500", "3"],
            ["", "White fly", "108", "900", "500", "31"],
        ]
    )
    row_top = table.rows[3].bbox[1]
    defect = EdgeDefect("orphan", "Cotton", row_top + 5.0, row_top + 16.0, None)
    table = dataclasses.replace(table, defects=(defect,))
    result = assemble("doc", [(25, [table])])
    assert [(a.code, a.row, a.detail) for a in result.anomalies if a.code.startswith("CELL_")] == [
        ("CELL_ORPHAN", 3, "Cotton")
    ]
