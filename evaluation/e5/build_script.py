# ruff: noqa: E501, S311  (a one-off builder: a data table, a reproducible draw)
"""Build the E5 recording script (M5, speech), 2026-11-18. Run once:
    uv run python evaluation/e5/build_script.py build/register.sqlite

Each line is something a dealer or farmer could say, tied to a structured query on the release register, so a
recording can be scored twice: speech-to-text against the line (word error rate), and the whole pipeline
against the register's answer. The Kannada lines use natural case endings and some Kannada pest names on
purpose: the lexicon knows crop names only in Latin letters today, and these lines measure what M5 must add.
The Kannada wording was drafted by the assistant; the speaker (a Kannada speaker) may correct a line before
reading it, and records the change.
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from labelclaim.lookup.engine import Engine
from labelclaim.lookup.models import Query

HERE = Path(__file__).parent
SEED = 202611187

# crop id -> (Kannada, dative "to/for", locative "in", English as a farmer would say it)
CROPS = {
    "okra": ("ಬೆಂಡೆಕಾಯಿ", "ಬೆಂಡೆಕಾಯಿಗೆ", "ಬೆಂಡೆಕಾಯಿಯಲ್ಲಿ", "bhindi"),
    "brinjal": ("ಬದನೆಕಾಯಿ", "ಬದನೆಕಾಯಿಗೆ", "ಬದನೆಕಾಯಿಯಲ್ಲಿ", "brinjal"),
    "tomato": ("ಟೊಮೆಟೊ", "ಟೊಮೆಟೊಗೆ", "ಟೊಮೆಟೊದಲ್ಲಿ", "tomato"),
    "rice": ("ಭತ್ತ", "ಭತ್ತಕ್ಕೆ", "ಭತ್ತದಲ್ಲಿ", "paddy"),
    "cotton": ("ಹತ್ತಿ", "ಹತ್ತಿಗೆ", "ಹತ್ತಿಯಲ್ಲಿ", "cotton"),
    "chilli": ("ಮೆಣಸಿನಕಾಯಿ", "ಮೆಣಸಿನಕಾಯಿಗೆ", "ಮೆಣಸಿನಕಾಯಿಯಲ್ಲಿ", "chilli"),
    "onion": ("ಈರುಳ್ಳಿ", "ಈರುಳ್ಳಿಗೆ", "ಈರುಳ್ಳಿಯಲ್ಲಿ", "onion"),
    "potato": ("ಆಲೂಗಡ್ಡೆ", "ಆಲೂಗಡ್ಡೆಗೆ", "ಆಲೂಗಡ್ಡೆಯಲ್ಲಿ", "potato"),
    "mango": ("ಮಾವು", "ಮಾವಿಗೆ", "ಮಾವಿನಲ್ಲಿ", "mango"),
    "grape": ("ದ್ರಾಕ್ಷಿ", "ದ್ರಾಕ್ಷಿಗೆ", "ದ್ರಾಕ್ಷಿಯಲ್ಲಿ", "grapes"),
    "pigeonpea": ("ತೊಗರಿ", "ತೊಗರಿಗೆ", "ತೊಗರಿಯಲ್ಲಿ", "tur"),
    "chickpea": ("ಕಡಲೆ", "ಕಡಲೆಗೆ", "ಕಡಲೆಯಲ್ಲಿ", "chana"),
    "groundnut": ("ಶೇಂಗಾ", "ಶೇಂಗಾಕ್ಕೆ", "ಶೇಂಗಾದಲ್ಲಿ", "groundnut"),
    "maize": ("ಮೆಕ್ಕೆಜೋಳ", "ಮೆಕ್ಕೆಜೋಳಕ್ಕೆ", "ಮೆಕ್ಕೆಜೋಳದಲ್ಲಿ", "maize"),
    "cabbage": ("ಎಲೆಕೋಸು", "ಎಲೆಕೋಸಿಗೆ", "ಎಲೆಕೋಸಿನಲ್ಲಿ", "cabbage"),
    "cauliflower": ("ಹೂಕೋಸು", "ಹೂಕೋಸಿಗೆ", "ಹೂಕೋಸಿನಲ್ಲಿ", "cauliflower"),
    "banana": ("ಬಾಳೆ", "ಬಾಳೆಗೆ", "ಬಾಳೆಯಲ್ಲಿ", "banana"),
    "coconut": ("ತೆಂಗು", "ತೆಂಗಿಗೆ", "ತೆಂಗಿನಲ್ಲಿ", "coconut"),
    "pomegranate": ("ದಾಳಿಂಬೆ", "ದಾಳಿಂಬೆಗೆ", "ದಾಳಿಂಬೆಯಲ್ಲಿ", "pomegranate"),
    "sugarcane": ("ಕಬ್ಬು", "ಕಬ್ಬಿಗೆ", "ಕಬ್ಬಿನಲ್ಲಿ", "sugarcane"),
    "wheat": ("ಗೋಧಿ", "ಗೋಧಿಗೆ", "ಗೋಧಿಯಲ್ಲಿ", "wheat"),
    "ragi": ("ರಾಗಿ", "ರಾಗಿಗೆ", "ರಾಗಿಯಲ್ಲಿ", "ragi"),
    "cucumber": ("ಸೌತೆಕಾಯಿ", "ಸೌತೆಕಾಯಿಗೆ", "ಸೌತೆಕಾಯಿಯಲ್ಲಿ", "cucumber"),
    "blackgram": ("ಉದ್ದು", "ಉದ್ದಿಗೆ", "ಉದ್ದಿನಲ್ಲಿ", "urad"),
    "greengram": ("ಹೆಸರು", "ಹೆಸರಿಗೆ", "ಹೆಸರಿನಲ್ಲಿ", "moong"),
    "sorghum": ("ಜೋಳ", "ಜೋಳಕ್ಕೆ", "ಜೋಳದಲ್ಲಿ", "jowar"),
    "cardamom": ("ಏಲಕ್ಕಿ", "ಏಲಕ್ಕಿಗೆ", "ಏಲಕ್ಕಿಯಲ್ಲಿ", "cardamom"),
}
# register pest phrase (lower case) -> a common Kannada name; used for about half the lines that have one
PESTS_KN = {
    "fruit borer": "ಕಾಯಿ ಕೊರಕ", "shoot and fruit borer": "ಕುಡಿ ಮತ್ತು ಕಾಯಿ ಕೊರಕ", "whitefly": "ಬಿಳಿ ನೊಣ",
    "white fly": "ಬಿಳಿ ನೊಣ", "aphids": "ಸಸ್ಯ ಹೇನು", "aphid": "ಸಸ್ಯ ಹೇನು", "stem borer": "ಕಾಂಡ ಕೊರಕ",
    "powdery mildew": "ಬೂದಿ ರೋಗ", "termites": "ಗೆದ್ದಲು", "termite": "ಗೆದ್ದಲು", "pod borer": "ಕಾಯಿ ಕೊರಕ",
}  # fmt: skip

KANNADA = [  # (template, uses a pest)
    ("{dat} {pest} ಬಂದಿದೆ, {product} ಹೊಡೆಯಬಹುದಾ?", True),
    ("{product} ಅನ್ನು {loc} {pest} ಗೆ ಬಳಸಬಹುದಾ?", True),
    ("{loc} {pest} ಜಾಸ್ತಿ ಆಗಿದೆ, {product} ಸರಿ ನಾ?", True),
    ("{product} ಹೊಡೆದ ಮೇಲೆ {nom} ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು?", False),
    ("{dat} {product} ಎಷ್ಟು ಹಾಕಬೇಕು?", False),
    ("{product} {dat} ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ?", False),
]
ENGLISH = [
    ("Can I spray {product} on {en} for {pest}?", True),
    ("How many days after spraying {product} can I harvest {en}?", False),
    ("Is {product} registered for {pest} in {en}?", True),
]


def spoken(heading: str) -> str:
    """The product as a dealer would read the label aloud: the printed heading without bracketed notes such as
    "(Seed treatment)", spacing tidied."""
    import re  # noqa: PLC0415

    return " ".join(re.sub(r"\([^)]*\)", " ", heading).replace("%", "% ").split()).replace(" %", "%")


def main(register: str) -> None:
    rng = random.Random(SEED)
    engine = Engine(Path(register))
    conn = sqlite3.connect(f"file:{register}?mode=ro", uri=True)
    rows = conn.execute(
        """SELECT p.heading_raw, uc.crop_id, MIN(up.phrase)
           FROM use_record u JOIN product p ON p.id = u.product_id
           JOIN use_record_crop uc ON uc.use_record_id = u.id JOIN use_record_pest up ON up.use_record_id = u.id
           WHERE p.parse_status = 'parsed'
           GROUP BY u.id HAVING COUNT(DISTINCT uc.crop_id) = 1 AND COUNT(DISTINCT up.phrase) = 1"""
    ).fetchall()
    by_crop: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for heading, crop, phrase in rows:
        if (
            crop in CROPS
            and len(phrase.split()) <= 3
            and phrase.replace(" ", "").isalpha()
            and len(heading) <= 60
        ):
            by_crop[crop].append((heading, phrase.lower()))
    crops = sorted(c for c in by_crop if len(by_crop[c]) >= 2)

    def outcome(crop: str, product: str, pest: str | None) -> str:
        return engine.lookup(Query(crop=crop, product=product, pest=pest)).outcome.value

    lines: list[dict] = []

    def add(line_id: str, lang: str, text: str, crop: str, product: str, pest: str | None, kind: str) -> None:
        lines.append({"id": line_id, "lang": lang, "kind": kind, "text": text,
                      "structured": {"product": product, "ingredient": None, "crop": crop, "pest": pest},
                      "register_outcome": outcome(crop, product, pest)})  # fmt: skip

    plan = [0] * 12 + [1] * 8 + [2] * 8 + [3] * 8 + [4] * 6 + [5] * 8  # 50 Kannada lines
    rng.shuffle(plan)
    for n, which in enumerate(plan, 1):
        template, with_pest = KANNADA[which]
        crop = rng.choice(crops)
        heading, phrase = rng.choice(by_crop[crop])
        if which == 5 and rng.random() < 0.4:  # some "is it registered" lines ask about a crop it is not on
            other = rng.choice([c for c in crops if c != crop])
            if outcome(other, heading, None) == "NOT_APPROVED_FOR_CROP":
                crop = other
        nom, dat, loc, _en = CROPS[crop]
        said_pest = PESTS_KN.get(phrase, phrase) if rng.random() < 0.5 else phrase
        text = template.format(nom=nom, dat=dat, loc=loc, pest=said_pest, product=spoken(heading))
        add(f"KN-{n:02d}", "kn", text, crop, heading, phrase if with_pest else None, "single")
    for n in range(1, 11):  # 10 English lines
        template, with_pest = ENGLISH[(n - 1) % len(ENGLISH)]
        crop = rng.choice(crops)
        heading, phrase = rng.choice(by_crop[crop])
        text = template.format(product=spoken(heading), en=CROPS[crop][3], pest=phrase)
        add(f"EN-{n:02d}", "en", text, crop, heading, phrase if with_pest else None, "single")
    for n in range(1, 6):  # 5 two-turn conversations: the follow-up keeps the product, changes the crop
        crop = rng.choice(crops)
        heading, phrase = rng.choice(by_crop[crop])
        other = rng.choice([c for c in crops if c != crop])
        first = KANNADA[0][0].format(
            dat=CROPS[crop][1], pest=PESTS_KN.get(phrase, phrase), product=spoken(heading)
        )
        add(f"FU-{n:02d}a", "kn", first, crop, heading, phrase, "turn 1")
        add(f"FU-{n:02d}b", "kn", f"ಮತ್ತೆ {CROPS[other][1]}?", other, heading, phrase, "turn 2 (follow-up)")
    (HERE / "script.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8"
    )
    print(len(lines), "lines")
    engine.close()


if __name__ == "__main__":
    main(sys.argv[1])
