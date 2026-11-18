"""Deterministic wording (L3 §4): the headline always, and the details when the model's message is blocked
or unavailable. Every value is copied from the engine's answer; nothing is computed."""

from __future__ import annotations

from labelclaim.lookup.models import Answer, ApprovedUse, Outcome

CLARIFY = {
    # pilot test 17: a symptom ("brown spots on the leaves") is not a pest name; choosing a product is advice
    "product": "Which product is it? Please type the name printed on the label, with its % and code. "
    "I can't recommend a product or name a disease from its symptoms.",
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
        Outcome.UNKNOWN_PRODUCT: _unknown_product(product, pest),
        Outcome.UNKNOWN_CROP: f"Crop not found in the register: {crop}.",
        Outcome.UNKNOWN_PEST: f"Pest not found in the register: {pest}.",
        Outcome.AMBIGUOUS: _ambiguous(answer, pest),
    }[answer.outcome]
    return warn + text


# pilot tests 15-16: a herbicide is not "missing" from the register, it is outside it. A reviewed list of
# common herbicide ingredients, and weed words in the pest slot, say so plainly.
HERBICIDES = frozenset({
    "glyphosate", "glufosinate", "paraquat", "atrazine", "pendimethalin", "butachlor", "pretilachlor",
    "oxyfluorfen", "metribuzin", "imazethapyr", "quizalofop", "fenoxaprop", "metsulfuron", "bispyribac",
    "bensulfuron", "trifluralin", "diuron", "propanil", "clodinafop", "sulfosulfuron", "cyhalofop",
    "halosulfuron", "topramezone", "tembotrione", "2,4-d", "2,4 d", "2-4-d", "anilofos", "oxadiargyl",
})  # fmt: skip
WEED_WORDS = frozenset({"weed", "weeds", "kale", "kalegalu", "grass", "herbicide", "kharpatwar"})


def _unknown_product(product: str, pest: str | None) -> str:
    words = product.lower().split()
    if (
        (words and words[0] in HERBICIDES)
        or product.lower() in HERBICIDES
        or (pest and set(pest.lower().split()) & WEED_WORDS)
    ):
        return (
            f"Not covered: {product} is a weed killer (herbicide) question. This checker covers the "
            "insecticide and fungicide registers only, so it cannot say whether this use is approved."
        )
    if not any(ch.isdigit() for ch in product):
        return (
            f"'{product}' looks like a brand or a short name. The register lists products by the name "
            "printed under the brand, with its % and code (for example 'Mancozeb 75% WP'): please type that."
        )
    return f"Product not found in the register: {product}. Please check the name, % and code on the label."


def _ambiguous(answer: Answer, pest: str | None) -> str:
    """Pilot fix 3: when every option is an approved pest of this product (a near name such as "Tikka leaf
    spot" for "tikka"), say so, and ask; otherwise the general wording."""
    pests = [o for o in answer.options if o.kind == "pest"]
    if pest and pests and all(o.outcome is Outcome.APPROVED for o in pests):
        names = ", ".join(o.display for o in pests)
        return f"Not listed under '{pest}', but listed for: {names}. Is that your pest?"
    return "More than one match; please choose one of the options."


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
    return (
        ""  # pilot tests 15-16: no rows, so the headline says it all ("See the suggestions ..." said nothing)
    )
