"""A small, hand-written register (schema v2) for engine and API tests, written through the real writer."""

from __future__ import annotations

import json
from pathlib import Path

from labelclaim.register.writer import write

Q = json.dumps({"kind": "value", "lo": [], "hi": [], "unit": None, "status": "parsed"})
PROV = json.dumps({"rows": [[1, 0, 1]], "fields": {}})

# id, product, crop_raw, pest_raw, ai, form, dilution, wait, wait_lo, wait_hi, page
USES = [
    (1, 1, "Tomato", "Fruit borer (Helicoverpa armigera)", "30", "150", "500", "3", 3, 3, 10),
    (2, 1, "Rice", "Stem borer", "30", "150", "500", "15", 15, 15, 10),
    (3, 2, "Cotton", "Aphids", "200", "1000", "500", "15", 15, 15, 20),
    (4, 3, "Rice (Paddy)", "Brown plant hopper", "110 + 15", "500", "400 - 500", "32", 32, 32, 60),
    (5, 4, "Cotton", "Jassids", "400", "1100", "500", "15", 15, 15, 30),
    (6, 1, "Tomato/Chilli", "Jassids", "25", "125", "500", "5", 5, 5, 11),
    (7, 5, "Rice", "Stem borer", "40", "10 kg", "-", "NA", None, None, 12),
    (8, 2, "Citrus", "Leaf miner", "0.025%", "2.5 ml/l", "-", "-", None, None, 21),
]


def build_fixture(path: Path) -> str:
    tables = {
        "source_document": [("ins", "insecticide", "https://example.invalid/ins.pdf", "0" * 64, "2026-09-30", 100)],
        "ingredient": [
            (1, "chlorantraniliprole", "Chlorantraniliprole"),
            (2, "chlorpyriphos", "Chlorpyriphos"),
            (3, "cypermethrin", "Cypermethrin"),
            (4, "buprofezin", "Buprofezin"),
            (5, "fipronil", "Fipronil"),
            (6, "monocrotophos", "Monocrotophos"),
        ],
        "ingredient_variant": [("chlorpyrifos", "chlorpyriphos", "tarun")],
        "product": [
            (1, "ins", "insecticide_single", "Chlorantraniliprole 18.5% SC", "SC", "parsed", "[]", 10, "[]"),
            (2, "ins", "insecticide_single", "Chlorpyriphos 20% EC", "EC", "parsed", "[]", 20, "[]"),
            (3, "ins", "insecticide_combination", "Buprofezin 22% + Fipronil 2% SC", "SC", "parsed", "[]", 60, "[]"),
            (4, "ins", "insecticide_single", "Monocrotophos 36% SL", "SL", "parsed", "[]", 30, "[]"),
            (5, "ins", "insecticide_single", "Chlorantraniliprole 0.4% GR", "GR", "parsed", "[]", 12, "[]"),
        ],
        "product_ingredient": [
            (1, 0, 1, 18.5, "%", None),
            (2, 0, 2, 20.0, "%", None),
            (3, 0, 4, 22.0, "%", None),
            (3, 1, 5, 2.0, "%", None),
            (4, 0, 6, 36.0, "%", None),
            (5, 0, 1, 0.4, "%", None),
        ],
        "crop": [(c, c, "crop") for c in ("brinjal", "chilli", "citrus", "cotton", "rice", "tomato")],
        "crop_alias": [
            ("brinjal", "en", "brinjal", "t"), ("egg plant", "en", "brinjal", "t"), ("chilli", "en", "chilli", "t"),
            ("chillies", "en", "chilli", "t"), ("cotton", "en", "cotton", "t"), ("rice", "en", "rice", "t"),
            ("paddy", "en", "rice", "t"), ("rice (paddy)", "en", "rice", "t"), ("tomato", "en", "tomato", "t"),
            ("tomato/chilli", "en", "tomato", "t"), ("tomato/chilli", "en", "chilli", "t"), ("citrus", "en", "citrus", "t"),
        ],
        "pest": [(p, p.replace("_", " ")) for p in ("aphid", "brown_plant_hopper", "fruit_borer", "jassid", "stem_borer")],
        "pest_alias": [
            ("aphid", "aphid", "t"), ("aphids", "aphid", "rule:plural"), ("brown plant hopper", "brown_plant_hopper", "t"),
            ("bph", "brown_plant_hopper", "t"), ("fruit borer", "fruit_borer", "t"), ("jassid", "jassid", "t"),
            ("jassids", "jassid", "rule:plural"), ("stem borer", "stem_borer", "t"),
        ],
        "use_record": [
            (uid, pid, crop, pest, ai, form, dil, wait, Q, Q, Q, lo, hi, page, page, PROV, "[]")
            for uid, pid, crop, pest, ai, form, dil, wait, lo, hi, page in USES
        ],
        "use_record_crop": [(1, "tomato"), (2, "rice"), (3, "cotton"), (4, "rice"), (5, "cotton"), (6, "chilli"),
                            (6, "tomato"), (7, "rice"), (8, "citrus")],
        "use_record_pest": [(1, "fruit_borer", "fruit borer"), (2, "stem_borer", "stem borer"), (3, "aphid", "aphids"),
                            (4, "brown_plant_hopper", "brown plant hopper"), (5, "jassid", "jassids"),
                            (6, "jassid", "jassids"), (7, "stem_borer", "stem borer")],
        "restriction": [
            (1, "chlorpyriphos", "Chlorpyriphos", "restricted", "Chlorpyriphos is banned for use in Ber, Citrus and Tobacco.", 4),
            (2, "monocrotophos", "Monocrotophos", "restricted", "Monocrotophos is banned for use on vegetables.", 6),
        ],
    }  # fmt: skip
    return write(path, tables, {"release": "false"})
