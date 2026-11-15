"""ADR-007 / L1 §16: reviewed corrections of rows the extractor misread."""

from __future__ import annotations

from pathlib import Path

import pytest

from labelclaim.corrections import CorrectionError, apply_corrections, covered, load_corrections
from labelclaim.extract.model import Anomaly, Col, Field, ProductHeading, Section, UseRow

DOC = "mup_insecticide_2026-09-30"
PRODUCT = ProductHeading(
    DOC, Section.INSECTICIDE_SINGLE, "DIMPROPYRIDAZ 120 g/l SL", 24, (0.0, 0.0, 1.0, 1.0)
)


def use(crop: str, pest: str, wait: str, row: int, page: int = 25) -> UseRow:
    texts = {Col.CROP: crop, Col.PEST: pest, Col.DOSE_AI: "108 – 120", Col.DOSE_FORM: "900 – 1000",
             Col.DILUTION: "500", Col.WAIT: wait}  # fmt: skip
    fields = {c: Field(t, ((page, (0.0, 0.0, 1.0, 1.0)),), "cell") for c, t in texts.items()}
    return UseRow(PRODUCT, fields, ((page, 0, row),))


USES = [
    use("Brinjal", "White fly", "3", 0, page=24),
    use("Brinjal", "White fly", "31", 0),
    use("X", "Y", "1", 1),
]

EVIDENCE = "evidence = \"pdftotext -layout p. 25: 'Cotton ... White fly 108 – 120 900 – 1000 500 31'\""
TOML = """
[[correct]]
id = "C-01"
doc = "mup_insecticide_2026-09-30"
page = 25
product = "DIMPROPYRIDAZ 120 g/l SL"
match = { crop = "Brinjal", pest = "White fly", wait = "31" }
set = { crop = "Cotton" }
covers = ["CELL_ORPHAN"]
@EVIDENCE@
reviewed_by = "Tarun"
""".replace("@EVIDENCE@", EVIDENCE)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "corrections.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_correction_sets_the_field_and_records_what_it_replaced(tmp_path: Path) -> None:
    corrections = load_corrections(write(tmp_path, TOML))
    out, applied = apply_corrections(DOC, USES, corrections)
    fixed = out[1]
    assert fixed.fields[Col.CROP].text == "Cotton"
    assert fixed.fields[Col.CROP].source == "corrected"
    assert fixed.fields[Col.CROP].bboxes == USES[1].fields[Col.CROP].bboxes  # the page area is kept
    assert fixed.corrections == (("C-01", "CROP", "Brinjal"),)
    assert out[0] == USES[0]  # the p. 24 Brinjal row has wait 3: untouched
    assert out[2] == USES[2]
    assert applied == {"C-01": ((25, 0, 0),)}


def test_a_drop_correction_removes_the_row(tmp_path: Path) -> None:
    text = TOML.replace('set = { crop = "Cotton" }', "drop = true")
    out, _ = apply_corrections(DOC, USES, load_corrections(write(tmp_path, text)))
    assert len(out) == 2
    assert USES[1] not in out


def test_a_stale_correction_fails_the_build(tmp_path: Path) -> None:
    # a new register edition changed the row: the correction no longer describes what the extractor reads
    text = TOML.replace('wait = "31"', 'wait = "30"')
    with pytest.raises(CorrectionError, match=r"C-01.*matches 0"):
        apply_corrections(DOC, USES, load_corrections(write(tmp_path, text)))


def test_an_ambiguous_correction_fails_the_build(tmp_path: Path) -> None:
    text = TOML.replace(', wait = "31"', "")
    with pytest.raises(CorrectionError, match=r"C-01.*matches 2"):
        apply_corrections(
            DOC, [*USES, use("Brinjal", "White fly", "7", 2)], load_corrections(write(tmp_path, text))
        )


def test_corrections_for_other_documents_are_ignored(tmp_path: Path) -> None:
    out, applied = apply_corrections("other_doc", USES, load_corrections(write(tmp_path, TOML)))
    assert out == USES
    assert applied == {}


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('set = { crop = "Cotton" }', 'set = { colour = "x" }', "unknown field"),
        ('set = { crop = "Cotton" }', "", "exactly one of set or drop"),
        ('set = { crop = "Cotton" }', 'set = { crop = "Cotton" }\ndrop = true', "exactly one of set or drop"),
        (EVIDENCE, 'evidence = ""', "evidence"),
        ('match = { crop = "Brinjal", pest = "White fly", wait = "31" }', "match = {}", "match"),
    ],
)
def test_malformed_corrections_are_rejected(tmp_path: Path, old: str, new: str, message: str) -> None:
    text = TOML.replace(old, new)
    with pytest.raises(CorrectionError, match=message):
        load_corrections(write(tmp_path, text))


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(CorrectionError, match="duplicate"):
        load_corrections(write(tmp_path, TOML + TOML))


def test_unreviewed_corrections_are_counted(tmp_path: Path) -> None:
    corrections = load_corrections(write(tmp_path, TOML.replace('"Tarun"', '""')))
    assert [c.id for c in corrections if not c.reviewed] == ["C-01"]


def test_a_correction_covers_only_its_codes_on_its_rows(tmp_path: Path) -> None:
    corrections = load_corrections(write(tmp_path, TOML))
    applied = {"C-01": ((25, 0, 0),)}
    assert covered(Anomaly("CELL_ORPHAN", DOC, 25, 0, 0, "Cotton"), corrections, applied)
    assert not covered(Anomaly("CELL_ORPHAN", DOC, 25, 0, 1, "Cotton"), corrections, applied)  # another row
    assert not covered(Anomaly("CELL_STRADDLE", DOC, 25, 0, 0, "x"), corrections, applied)  # another code


def test_a_missing_file_means_no_corrections(tmp_path: Path) -> None:
    assert load_corrections(tmp_path / "absent.toml") == ()
