"""Deterministic wording (L3 §4): the headline always, and the details when the model's message is blocked
or unavailable. Every value is copied from the engine's answer; nothing is computed."""

from __future__ import annotations

from labelclaim.lookup.models import Answer, ApprovedUse, Outcome

CLARIFY = {
    "product": "Which product or active ingredient is it? Please type the name as printed on the label.",
    "crop": "Which crop is it for?",
    "pest": "Which pest or disease is it for?",
    "which_product": "Which product exactly? Please type the name as printed on the label.",
}
COLUMN_UNITS = (
    "Register column units (from its table header): dose_ai is grams of active ingredient per hectare; "
    "dose_form is grams or ml of product per hectare; dilution is litres of water per hectare; wait is the "
    "waiting period in days before harvest. A cell that states its own unit (for example per kg seed) "
    "overrides this."
)


def headline(
    answer: Answer, product: str, crop: str, pest: str | None, *, by_ingredient: bool = False
) -> str:
    """The first line the user reads, from the engine's outcome. An ingredient-level approval says to check
    the formulation (E3n fix 6): another formulation of the same ingredient may be the one that is listed."""
    use = answer.uses[0] if answer.uses else None
    warn = "Warning: a ban or restriction applies; see restrictions. " if answer.conflict else ""
    for_pest = f" for {pest}" if pest else ""
    if answer.outcome is Outcome.APPROVED and answer.conflict and use is not None:
        # Pilot test 6 (2026-11-18): "Warning ... Approved: Mancozeb 75% WP on Jowar" read as a yes, although
        # a 2023 order bans Mancozeb on jowar. The order comes first; the register's older claim second (T12).
        return _restricted_headline(answer, use, for_pest)
    text = {
        Outcome.APPROVED: (
            (f"Approved for a product containing {product}: " if by_ingredient else "Approved: ")
            + f"{use.product_heading} on {use.crop_raw}{for_pest} is listed in the register "
            + f"(p. {use.citation.page_first})"
            + ("; check that it is the formulation you have." if by_ingredient else ".")
            if use
            else "Approved."
        ),
        Outcome.NOT_APPROVED_FOR_CROP: f"Not listed: the register has no use of {product} on {crop}.",
        Outcome.NOT_APPROVED_FOR_PEST: (
            f"Not listed for this pest: {product} is registered on {crop}, but not{for_pest}."
        ),
        Outcome.UNKNOWN_PRODUCT: f"Product not found in the register: {product}.",
        Outcome.UNKNOWN_CROP: f"Crop not found in the register: {crop}.",
        Outcome.UNKNOWN_PEST: f"Pest not found in the register: {pest}.",
        Outcome.AMBIGUOUS: "More than one match; please choose one of the options.",
    }[answer.outcome]
    return warn + text


TOTAL_BANS = ("banned", "banned_for_use", "withdrawn")


def _restricted_headline(answer: Answer, use: ApprovedUse, for_pest: str) -> str:
    applying = [r for r in answer.restrictions if r.names_the_crop or r.status in TOTAL_BANS]
    r = applying[0]
    if r.status in TOTAL_BANS:
        label = "Banned"
    elif r.names_the_crop and "ban" in r.detail_raw.lower():
        label = "Banned on this crop"
    else:
        label = "Restricted"
    detail = " ".join(r.detail_raw.split())
    return (
        f"{label}: {detail} (banned and restricted list, p. {r.page}). The register still lists "
        f"{use.product_heading} on {use.crop_raw}{for_pest} (p. {use.citation.page_first}), "
        "but the order above applies."
    )


def _row(use: ApprovedUse) -> str:
    return (
        f"{use.product_heading} on {use.crop_raw} for {use.pest_raw}: a.i. {use.dose_ai_raw}; formulation "
        f"{use.dose_form_raw}; water {use.dilution_raw}; waiting period {use.wait_raw} "
        f"(as printed, p. {use.citation.page_first})."
    )


def details(answer: Answer) -> str:
    """The cited rows as printed, for a blocked or missing model message."""
    if answer.uses:
        return " ".join(_row(u) for u in answer.uses[:3])
    if answer.alternatives:
        return "Listed instead: " + " ".join(_row(u) for u in answer.alternatives[:3])
    return "See the suggestions and options in the answer."
