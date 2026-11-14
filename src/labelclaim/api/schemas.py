"""The public contract (Pydantic v2). Exported to openapi.json; a test fails when that file is stale."""

from __future__ import annotations

from typing import Annotated, Self

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
    register_: RegisterOut = Field(validation_alias="register", serialization_alias="register")
    disclaimer: str


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
