"""Product heading grammar (L1 §6.1): ingredients with concentrations, formulation code, notes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from labelclaim.extract.classify import FORMULATIONS

Status = Literal["parsed", "partial", "unparsed"]
_NOTE = re.compile(r"\(([^()]*)\)")
_FORMULATION = re.compile(rf"\b({FORMULATIONS})\b\.?\s*$", re.IGNORECASE)
_TRAILING_BASIS = re.compile(r"\s*\b(w/w|w/v)\s*$", re.IGNORECASE)
_INGREDIENT = re.compile(
    r"^(?P<name>[^\d%]*?[A-Za-z][^%]*?)\s*"
    r"(?P<conc>\d+(?:\s*\.\s*\d+)?)\s*(?P<pre>[wm]\s*/\s*[wvm]\s*)?(?P<unit>%|g\s*/\s*l\b|g/ltr\b)\s*"
    r"(?P<basis>[wm]\s*/\s*[wvm])?"
    r"\s*(?:min(?:imum)?\.?)?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Ingredient:
    name: str  # as printed
    key: str  # case-folded, whitespace-collapsed (the join key with the restrictions list)
    conc: float | None
    unit: str | None  # "%" or "g/l"
    basis: str | None  # "w/w", "w/v" or None


@dataclass(frozen=True)
class Heading:
    raw: str
    ingredients: tuple[Ingredient, ...]
    formulation: str | None
    notes: tuple[str, ...]
    status: Status


def ingredient_key(name: str) -> str:
    return " ".join(name.casefold().replace("–", "-").split()).strip(" ,.-")


def parse_heading(text: str) -> Heading:
    """Parse without guessing: anything the grammar cannot read is left out and lowers `status`."""
    notes = tuple(" ".join(n.split()) for n in _NOTE.findall(text))
    body = " ".join(_NOTE.sub(" ", text).split())
    body = re.sub(r"\b([A-Z])\.([A-Z])\b", r"\1\2", body)  # "G.R" -> "GR"
    trailing_basis = None
    if m := _TRAILING_BASIS.search(body):  # "Kasugamycin 6 % + Thifluzamide 26% SC w/v"
        trailing_basis = m.group(1).lower()
        body = body[: m.start()]
    formulation = None
    if m := _FORMULATION.search(body):
        formulation = m.group(1).upper()
        body = body[: m.start()].strip()
    ingredients: list[Ingredient] = []
    parsed = 0
    for part in (p.strip() for p in body.split("+")):
        if not part:
            continue
        m = _INGREDIENT.match(part)
        if m is None:
            ingredients.append(Ingredient(part, ingredient_key(part), None, None, None))
            continue
        parsed += 1
        unit = "%" if m.group("unit") == "%" else "g/l"
        basis = m.group("basis") or m.group("pre")
        basis = re.sub(r"\s+", "", basis).lower() if basis else trailing_basis
        name = m.group("name").strip()
        conc = float(re.sub(r"\s+", "", m.group("conc")))
        ingredients.append(Ingredient(name, ingredient_key(name), conc, unit, basis))
    if (
        parsed == 0
        and len(notes) == 1
        and "%" in notes[0]
        and not body.replace(formulation or "", "").strip()
    ):
        # "(Streptomycin Sulphate 90% + Tetracycline Hydrochloride 10%) SP": the brackets hold the ingredients
        inner = parse_heading(f"{notes[0]} {formulation or ''}".strip())
        return Heading(text, inner.ingredients, formulation, (), inner.status)
    if not ingredients or parsed == 0:
        status: Status = "unparsed"
    elif parsed == len(ingredients) and formulation is not None:
        status = "parsed"
    else:
        status = "partial"
    return Heading(text, tuple(ingredients), formulation, notes, status)
