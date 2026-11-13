"""L1 §10 `headings`: real headings from both registers -> expected structure (typed from the text)."""

from __future__ import annotations

import pytest

from labelclaim.normalize.headings import parse_heading

CASES = [
    ("Abamectin 01.90 % EC", [("abamectin", 1.9, "%", None)], "EC", ()),
    ("Acequinocyl 15% w/v SC", [("acequinocyl", 15.0, "%", "w/v")], "SC", ()),
    ("Cyantraniliprole 48% w/w FS", [("cyantraniliprole", 48.0, "%", "w/w")], "FS", ()),
    ("Aluminium Phosphide 77.50 % GR", [("aluminium phosphide", 77.5, "%", None)], "GR", ()),
    ("Chlorfenapyr 240 g/L SC", [("chlorfenapyr", 240.0, "g/l", None)], "SC", ()),
    ("Cartap Hydrochloride 04 % Granules", [("cartap hydrochloride", 4.0, "%", None)], "GRANULES", ()),
    (
        "Cyclaniliprole 9.3% W/W DC (Cyclaniliprole 10.0% W/V DC)",
        [("cyclaniliprole", 9.3, "%", "w/w")],
        "DC",
        ("Cyclaniliprole 10.0% W/V DC",),
    ),
    (
        "Cyclobutrifluram 38.4% w/w SC (Import only)",
        [("cyclobutrifluram", 38.4, "%", "w/w")],
        "SC",
        ("Import only",),
    ),
    (
        "Buprofezin 22. 0% + Fipronil 2.0 % SC",
        [("buprofezin", 22.0, "%", None), ("fipronil", 2.0, "%", None)],
        "SC",
        (),
    ),
    (
        "Amisulbrom 5.21% w/w + Zoxamide 10.41% w/w SC",
        [("amisulbrom", 5.21, "%", "w/w"), ("zoxamide", 10.41, "%", "w/w")],
        "SC",
        (),
    ),
    (
        "Mefentrifluconazole 133 g/l + Fluxapyroxad 89 g/l + Pyraclostrobin 178 g/l SC",
        [
            ("mefentrifluconazole", 133.0, "g/l", None),
            ("fluxapyroxad", 89.0, "g/l", None),
            ("pyraclostrobin", 178.0, "g/l", None),
        ],
        "SC",
        (),
    ),
    (
        "Kasugamycin 6 % + Thifluzamide 26% SC w/v",
        [("kasugamycin", 6.0, "%", "w/v"), ("thifluzamide", 26.0, "%", "w/v")],
        "SC",
        (),
    ),
    (
        "METHOXYFENOZIDE 5% + CHLORPYRIPHOS 25% SE",
        [("methoxyfenozide", 5.0, "%", None), ("chlorpyriphos", 25.0, "%", None)],
        "SE",
        (),
    ),
    (
        "Chlorantraniliprole 09.30 % + Lambda-cyhalothrin 04.60 % ZC",
        [("chlorantraniliprole", 9.3, "%", None), ("lambda-cyhalothrin", 4.6, "%", None)],
        "ZC",
        (),
    ),
    (
        "Tebuconazole 15% + Zineb 57% WDG",
        [("tebuconazole", 15.0, "%", None), ("zineb", 57.0, "%", None)],
        "WDG",
        (),
    ),
    ("Thiamethoxam 30 % WS (Seed treatment)", [("thiamethoxam", 30.0, "%", None)], "WS", ("Seed treatment",)),
    ("Bromadiolone 00.005 % RB", [("bromadiolone", 0.005, "%", None)], "RB", ()),
    (
        "(Streptomycin Sulphate 90% + Tetracycline Hydrochloride 10%) SP",
        [("streptomycin sulphate", 90.0, "%", None), ("tetracycline hydrochloride", 10.0, "%", None)],
        "SP",
        (),
    ),
    ("Thiamethoxam 1.2% W/W G.R", [("thiamethoxam", 1.2, "%", "w/w")], "GR", ()),
    ("Novaluron 8.8 w/w % SC", [("novaluron", 8.8, "%", "w/w")], "SC", ()),
    ("Validamycin3%L", [("validamycin", 3.0, "%", None)], "L", ()),
]


@pytest.mark.parametrize(("text", "ingredients", "formulation", "notes"), CASES)
def test_real_headings(
    text: str, ingredients: list[tuple[str, float, str, str | None]], formulation: str, notes: tuple[str, ...]
) -> None:
    heading = parse_heading(text)
    assert heading.status == "parsed"
    assert [(i.key, i.conc, i.unit, i.basis) for i in heading.ingredients] == ingredients
    assert heading.formulation == formulation
    assert heading.notes == notes
    assert heading.raw == text


@pytest.mark.parametrize(
    ("text", "status"),
    [
        ("Neem oil", "unparsed"),  # no concentration, no formulation
        ("Azadirachtin 0.03% (300 ppm) w/w min", "partial"),  # no formulation code
        ("", "unparsed"),
    ],
)
def test_incomplete_headings_are_marked_not_guessed(text: str, status: str) -> None:
    heading = parse_heading(text)
    assert heading.status == status
    assert heading.raw == text
