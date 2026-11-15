"""L1 §16 `edges`: text that runs across a table's drawn cell lines, on synthetic glyphs.

The real cases (insecticide p. 25, 55, 80; fungicide p. 60, 73, 77, 82, 84): reports/E1/edge_audit.md."""

from __future__ import annotations

from labelclaim.extract.edges import Glyph, classify_run, defects, runs

SIZE = 11.0
W = 5.0  # glyph width
CELLS = [(100.0, 0.0, 200.0, 50.0), (200.0, 0.0, 300.0, 50.0)]  # two cells; the line between is at x 200


def word(text: str, x0: float, top: float = 10.0, step: float = W) -> list[Glyph]:
    return [Glyph(ch, x0 + i * step, x0 + i * step + W, top, top + SIZE, SIZE) for i, ch in enumerate(text)]


def test_a_word_cut_by_a_cell_line_is_a_straddle() -> None:
    # fungicide p. 60: "infestans)" ends 8 pt right of the line, so "s)" lands in the dose cell
    glyphs = word("infestans)", 160.0)  # 160 .. 210: the line at 200 falls between "n" and "s"
    found = defects(glyphs, CELLS)
    assert [(d.kind, d.text) for d in found] == [("straddle", "infestans)")]


def test_two_cells_texts_with_padding_between_are_not_a_defect() -> None:
    glyphs = word("Paddy", 170.0) + word("500", 204.0)  # ends at 195; the next text starts 9 pt later
    assert defects(glyphs, CELLS) == []


def test_text_flush_against_the_line_is_adjacent_not_a_straddle() -> None:
    # fungicide p. 49: the dose text starts 0.2 pt after the line, the pest text ends 1.9 pt before it
    glyphs = word("leafspot", 158.1) + word("124", 200.2)  # gap 2.1 pt: wider than any letter spacing
    run = runs(glyphs)[0]
    assert classify_run(run, CELLS)[0] == "adjacent"
    assert defects(glyphs, CELLS) == []


def test_the_straddle_threshold_sits_between_letter_spacing_and_padding() -> None:
    tight = word("ab", 194.0, step=5.3)  # "a" 194-199, "b" 199.3-204.3: centres either side of x 200
    loose = word("ab", 194.0, step=5.7)  # gap 0.7 pt: the closest real pair of separate texts
    assert classify_run(runs(tight)[0], CELLS)[0] == "straddle"
    assert classify_run(runs(loose)[0], CELLS)[0] == "adjacent"


def test_a_glyph_in_no_cell_is_an_orphan() -> None:
    # insecticide p. 25: the crop cell "Cotton" has no drawn top border, so pdfplumber found no cell
    glyphs = word("Cotton", 40.0)
    found = defects(glyphs, CELLS)
    assert [(d.kind, d.text) for d in found] == [("orphan", "Cotton")]


def test_glyphs_drawn_over_each_other_are_an_overlap() -> None:
    # fungicide p. 82: "Blast" and "10" interleaved, stored as "B 1l0as0t"
    glyphs = word("Blast", 210.0) + word("10", 211.0)
    found = defects(glyphs, CELLS)
    assert [d.kind for d in found] == ["overlap"]


def test_runs_split_at_wide_gaps_and_by_line() -> None:
    glyphs = word("ab", 110.0) + word("cd", 130.0) + word("ef", 110.0, top=30.0)
    assert ["".join(g.text for g in r) for r in runs(glyphs)] == ["ab", "cd", "ef"]


def test_a_defect_records_its_vertical_extent_for_row_lookup() -> None:
    (d,) = defects(word("Cotton", 40.0, top=88.0), [*CELLS, (100.0, 50.0, 200.0, 100.0)])
    assert (d.top, d.bottom) == (88.0, 99.0)
