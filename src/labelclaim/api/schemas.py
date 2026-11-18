"""The public contract (Pydantic v2). Exported to openapi.json; a test fails when that file is stale."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from labelclaim.lookup.models import MAX_PRODUCT, MAX_TEXT, Outcome

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)]
ProductText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PRODUCT)]


class LookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crop: Text
    product: ProductText | None = None
    ingredient: Text | None = None
    pest: Text | None = None

    @model_validator(mode="after")
    def exactly_one_product_or_ingredient(self) -> Self:
        if (self.product is None) == (self.ingredient is None):
            raise ValueError("give exactly one of product or ingredient")
        return self


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CitationOut(Out):
    document_id: str
    register_date: str
    page_first: int
    page_last: int
    url: str


class UseOut(Out):
    use_id: int
    product_heading: str
    crop_raw: str
    pest_raw: str
    dose_ai_raw: str
    dose_form_raw: str
    dilution_raw: str
    wait_raw: str
    wait_days: tuple[int, int] | None
    citation: CitationOut
    corrected: list[str] = Field(
        default_factory=list,
        description="Fields the extractor misread; a reviewed correction read them from the page (ADR-007)",
    )


class RestrictionOut(Out):
    ingredient: str
    status: str
    detail_raw: str
    page: int
    names_the_crop: bool


class SuggestionOut(Out):
    id: str
    display: str
    score: float


class OptionOut(Out):
    """One reading of a general name ("blight" -> early blight, late blight) and its own outcome."""

    kind: str
    id: str
    display: str
    outcome: Outcome
    use_ids: list[int]


class RegisterOut(Out):
    build_hash: str
    dates: dict[str, str]
    release: bool


class AnswerOut(Out):
    outcome: Outcome
    conflict: bool
    uses: list[UseOut]
    alternatives: list[UseOut]
    approved_crops: list[str]
    approved_pests: list[str]
    suggestions: dict[str, list[SuggestionOut]]
    restrictions: list[RestrictionOut]
    options: list[OptionOut]
    register_: RegisterOut = Field(validation_alias="register", serialization_alias="register")
    disclaimer: str


class LookupOut(AnswerOut):
    """L4: /v1/lookup's answer plus the same template headline /v1/ask shows (one source of wording)."""

    headline: str


class FeedbackRequest(BaseModel):
    """L4 §9: a tester's rating of one answer, tied to it by the answer's x-request-id."""

    model_config = ConfigDict(extra="forbid")
    request_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
    rating: Literal["up", "down"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""


class PilotOut(BaseModel):
    logging: bool


class Turn(BaseModel):
    """One earlier turn of a short conversation (pilot fix 2): the user's question and the app's clarifying
    question. The assistant drops an "assistant" turn that is not a short question without numbers."""

    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    lang: Literal["en", "kn"] | None = None  # L4: the reply language; None follows the question
    history: Annotated[list[Turn], Field(max_length=4)] = []  # pilot fix 2: the turns before this question


class ClarificationOut(BaseModel):
    question: str
    missing: str


class AskOut(BaseModel):
    """L3 §4. `headline` is a template on the engine's outcome; `message` is model-written and
    number-verified, or templated when `phrased_by` is "template". `answer` is exactly what /v1/lookup
    returns."""

    headline: str
    message: str
    answer: AnswerOut | None
    slots: dict[str, str | None] | None
    clarification: ClarificationOut | None
    provider: str
    phrased_by: str
    verifier_blocked: bool


class NameOut(BaseModel):
    id: str
    display: str


class ProductOut(BaseModel):
    id: int
    heading: str


class HealthOut(BaseModel):
    status: str
    build_hash: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorOut(BaseModel):
    error: ErrorBody
