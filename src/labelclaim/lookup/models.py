"""Query and answer types (L2 §5). Every raw field is the register's text: copied as extracted (ADR-004), or,
where `ApprovedUse.corrected` names it, read from the page by a reviewed correction (ADR-007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

MAX_TEXT = 120
MAX_PRODUCT = 200  # the longest register heading is 166 characters (with its bracketed notes)
DISCLAIMER = (
    "From the CIB&RC register 'Major Uses of Pesticides', which is compiled for guidance and not for legal "
    "purposes. An approved use is a registered label claim, not a recommendation to spray. "
    "Follow the product label and your agriculture officer."
)


class Outcome(StrEnum):
    APPROVED = "APPROVED"
    NOT_APPROVED_FOR_CROP = "NOT_APPROVED_FOR_CROP"
    NOT_APPROVED_FOR_PEST = "NOT_APPROVED_FOR_PEST"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    UNKNOWN_CROP = "UNKNOWN_CROP"
    UNKNOWN_PEST = "UNKNOWN_PEST"  # L2 §11 change: the crop-level rows go to `alternatives`, never to `uses`
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class Query:
    crop: str
    product: str | None = None
    ingredient: str | None = None
    pest: str | None = None

    def __post_init__(self) -> None:
        if (self.product is None) == (self.ingredient is None):
            raise ValueError("give exactly one of product or ingredient")
        for name in ("crop", "product", "ingredient", "pest"):
            value = getattr(self, name)
            limit = MAX_PRODUCT if name == "product" else MAX_TEXT
            if value is not None and not (0 < len(value.strip()) <= limit):
                raise ValueError(f"{name} must be 1-{limit} characters")


@dataclass(frozen=True)
class Suggestion:
    id: str
    display: str
    score: float


@dataclass(frozen=True)
class Citation:
    document_id: str
    register_date: str
    page_first: int
    page_last: int
    url: str


@dataclass(frozen=True)
class ApprovedUse:
    use_id: int
    product_heading: str
    crop_raw: str
    pest_raw: str
    dose_ai_raw: str
    dose_form_raw: str
    dilution_raw: str
    wait_raw: str
    wait_days: tuple[int, int] | None
    citation: Citation
    corrected: tuple[str, ...] = ()  # fields whose text a reviewed correction read from the page (ADR-007)


@dataclass(frozen=True)
class RestrictionNote:
    ingredient: str
    status: str
    detail_raw: str
    page: int
    names_the_crop: bool = False  # the restriction text names the crop asked about (threat model T12)


@dataclass(frozen=True)
class Option:
    """One reading of a general name (L2 §13.5): which crop or pest, and what the answer is for it."""

    kind: Literal["crop", "pest"]
    id: str
    display: str
    outcome: Outcome
    use_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class RegisterInfo:
    build_hash: str
    dates: dict[str, str]
    release: bool


@dataclass(frozen=True)
class Answer:
    outcome: Outcome
    register: RegisterInfo
    uses: tuple[ApprovedUse, ...] = ()
    alternatives: tuple[ApprovedUse, ...] = ()
    approved_crops: tuple[str, ...] = ()
    approved_pests: tuple[str, ...] = ()
    suggestions: dict[str, tuple[Suggestion, ...]] = field(default_factory=dict)
    restrictions: tuple[RestrictionNote, ...] = ()
    options: tuple[Option, ...] = ()  # set when the query used a general name ("blight", "gourd")
    disclaimer: str = DISCLAIMER

    @property
    def conflict(self) -> bool:
        """The register lists the use, but a banned/restricted entry names this crop (or bans the ingredient).
        Clients must show this before anything else (threat model T12)."""
        return any(
            r.names_the_crop or r.status in ("banned", "banned_for_use", "withdrawn")
            for r in self.restrictions
        )


Status = Literal["exact", "ambiguous", "unknown", "generic"]  # generic: L2 §13.5
