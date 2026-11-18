"""A small, hand-written register (schema v4) for engine and API tests, written through the real writer.
The second block (L2 §13) adds general names: blights on potato, leaf spots on sorghum, three gourds."""

from __future__ import annotations

import json
from pathlib import Path

from labelclaim.register.writer import write

Q = json.dumps({"kind": "value", "lo": [], "hi": [], "unit": None, "status": "parsed"})
PROV = json.dumps({"rows": [[1, 0, 1]], "fields": {}})
CORRECTED = json.dumps([{"id": "C-T1", "field": "PEST", "before": "Fruit borer)"}])  # ADR-007

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
# L2 §13 fixture: general names, the matching rule and the ingredient spelling fold
USES_G = [
    (9, 6, "Potato", "Late blight", "1500", "2000", "500", "5", 5, 5, 40),
    (10, 7, "Potato", "Late blight, Early blight", "1500", "2000", "750", "-", None, None, 41),
    (11, 7, "Sorghum", "Leafspot", "1500", "2000", "750", "-", None, None, 41),
    (12, 8, "Sorghum", "Red leaf spot", "1500", "2000", "750", "-", None, None, 42),
    (13, 9, "Bitter gourd", "Thrips", "90", "900", "500", "5", 5, 5, 19),
    (14, 9, "Ridgegourd", "Thrips", "90", "900", "500", "5", 5, 5, 19),
    (15, 10, "Bitter gourd", "Thrips", "75", "167", "500", "3", 3, 3, 50),
    (16, 10, "Ridgegourd", "Thrips", "75", "167", "500", "3", 3, 3, 50),
    (17, 10, "Bottle gourd", "Thrips", "75", "167", "500", "3", 3, 3, 50),
    (18, 11, "Potato", "Aphids", "25", "125", "500", "21", 21, 21, 36),
    (19, 11, "Rice", "Whiteflies", "25", "125", "500", "21", 21, 21, 36),
    (20, 12, "Grape", "Powdery mildew", "0.22%", "-", "-", "-", None, None, 17),
    (21, 13, "Grape", "Powdery mildew", "2000", "2500", "750", "-", None, None, 35),
    (22, 14, "Grape", "Powdery mildew", "2000", "2500", "-", "-", None, None, 35),
    (23, 7, "Cotton", "Bacterial blight", "1500", "2000", "750", "-", None, None, 41),
    # pilot fix 4: a potato early-blight row for Sulphur 80% WP, after Mancozeb 75% WP's row 10 by number
    (24, 13, "Potato", "Early blight", "2000", "2500", "750", "-", None, None, 35),
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
            (7, "mancozeb", "Mancozeb"), (8, "zineb", "Zineb"), (9, "cyantraniliprole", "Cyantraniliprole"),
            (10, "spinosad", "Spinosad"), (11, "imidacloprid", "Imidacloprid"), (12, "limesulphur", "Lime Sulphur"),
            (13, "sulphur", "Sulphur"), (14, "sulfur", "Sulfur"),
        ],
        "ingredient_variant": [("chlorpyrifos", "chlorpyriphos", "tarun")],
        "product": [
            (1, "ins", "insecticide_single", "Chlorantraniliprole 18.5% SC", "SC", "parsed", "[]", 10, "[]"),
            (2, "ins", "insecticide_single", "Chlorpyriphos 20% EC", "EC", "parsed", "[]", 20, "[]"),
            (3, "ins", "insecticide_combination", "Buprofezin 22% + Fipronil 2% SC", "SC", "parsed", "[]", 60, "[]"),
            (4, "ins", "insecticide_single", "Monocrotophos 36% SL", "SL", "parsed", "[]", 30, "[]"),
            (5, "ins", "insecticide_single", "Chlorantraniliprole 0.4% GR", "GR", "parsed", "[]", 12, "[]"),
            (6, "ins", "fungicide_single", "Mancozeb 75% WG", "WG", "parsed", "[]", 40, "[]"),
            (7, "ins", "fungicide_single", "Mancozeb 75% WP", "WP", "parsed", "[]", 41, "[]"),
            (8, "ins", "fungicide_single", "Zineb 75% WP", "WP", "parsed", "[]", 42, "[]"),
            (9, "ins", "insecticide_single", "Cyantraniliprole 10.26% OD", "OD", "parsed", "[]", 19, "[]"),
            (10, "ins", "insecticide_single", "Spinosad 45% SC", "SC", "parsed", "[]", 50, "[]"),
            (11, "ins", "insecticide_single", "Imidacloprid 17.8% SL", "SL", "parsed", "[]", 36, "[]"),
            (12, "ins", "fungicide_single", "Lime Sulphur 22% SC", "SC", "parsed", "[]", 17, "[]"),
            (13, "ins", "fungicide_single", "Sulphur 80% WP", "WP", "parsed", "[]", 35, "[]"),
            (14, "ins", "fungicide_single", "Sulfur 85% DP", "DP", "parsed", "[]", 35, "[]"),
        ],
        "product_ingredient": [
            (1, 0, 1, 18.5, "%", None),
            (2, 0, 2, 20.0, "%", None),
            (3, 0, 4, 22.0, "%", None),
            (3, 1, 5, 2.0, "%", None),
            (4, 0, 6, 36.0, "%", None),
            (5, 0, 1, 0.4, "%", None),
            (6, 0, 7, 75.0, "%", None), (7, 0, 7, 75.0, "%", None), (8, 0, 8, 75.0, "%", None),
            (9, 0, 9, 10.26, "%", None), (10, 0, 10, 45.0, "%", None), (11, 0, 11, 17.8, "%", None),
            (12, 0, 12, 22.0, "%", None), (13, 0, 13, 80.0, "%", None), (14, 0, 14, 85.0, "%", None),
        ],
        "crop": [(c, c.replace("_", " "), "crop") for c in (
            "bitter_gourd", "bottle_gourd", "brinjal", "chickpea", "chilli", "citrus", "cotton", "grape", "potato",
            "rice", "ridgegourd", "sorghum", "sugarcane", "tomato")],
        "crop_alias": [
            ("brinjal", "en", "brinjal", "t"), ("egg plant", "en", "brinjal", "t"), ("chilli", "en", "chilli", "t"),
            ("chillies", "en", "chilli", "t"), ("cotton", "en", "cotton", "t"), ("rice", "en", "rice", "t"),
            ("paddy", "en", "rice", "t"), ("rice (paddy)", "en", "rice", "t"), ("tomato", "en", "tomato", "t"),
            ("tomato/chilli", "en", "tomato", "t"), ("tomato/chilli", "en", "chilli", "t"), ("citrus", "en", "citrus", "t"),
            ("potato", "en", "potato", "t"), ("sorghum", "en", "sorghum", "t"), ("jowar", "en", "sorghum", "t"),
            ("bitter gourd", "en", "bitter_gourd", "t"), ("ridgegourd", "en", "ridgegourd", "t"),
            ("bottle gourd", "en", "bottle_gourd", "t"), ("grape", "en", "grape", "t"),
            # fix A: local names, and a crop alias that is also a unit word
            ("tamatar", "hi", "tomato", "t"), ("bhatta", "kn", "rice", "t"), ("hari mirch", "hi", "chilli", "t"),
            ("gram", "en", "chickpea", "t"),
            ("kabbu", "kn", "sugarcane", "t"),  # pilot fix 5: a noun ending in -u ("kabbige" = to sugarcane)
        ],
        "pest": [(p, p.replace("_", " ")) for p in (
            "aphid", "bacterial_blight", "blight", "brown_plant_hopper", "early_blight", "fruit_borer", "jassid",
            "late_blight", "leaf_spot", "powdery_mildew", "red_leaf_spot", "stem_borer", "thrips", "whitefly",
            "borer")],
        "pest_alias": [
            ("aphid", "aphid", "t"), ("aphids", "aphid", "rule:plural"), ("brown plant hopper", "brown_plant_hopper", "t"),
            ("bph", "brown_plant_hopper", "t"), ("fruit borer", "fruit_borer", "t"), ("jassid", "jassid", "t"),
            ("jassids", "jassid", "rule:plural"), ("stem borer", "stem_borer", "t"),
            ("late blight", "late_blight", "t"), ("early blight", "early_blight", "t"), ("blight", "blight", "t"),
            ("bacterial blight", "bacterial_blight", "t"), ("leafspot", "leaf_spot", "t"),
            ("red leaf spot", "red_leaf_spot", "t"), ("thrips", "thrips", "t"), ("whiteflies", "whitefly", "t"),
            ("powdery mildew", "powdery_mildew", "t"),
            ("borer", "borer", "t"),  # pilot fix 3: a shorter name that rows on tomato contain ("fruit borer")
        ],
        "use_record": [
            (uid, pid, crop, pest, ai, form, dil, wait, Q, Q, Q, lo, hi, page, page, PROV, "[]",
             CORRECTED if uid == 1 else "[]")
            for uid, pid, crop, pest, ai, form, dil, wait, lo, hi, page in USES + USES_G
        ],
        "use_record_crop": [(1, "tomato"), (2, "rice"), (3, "cotton"), (4, "rice"), (5, "cotton"), (6, "chilli"),
                            (6, "tomato"), (7, "rice"), (8, "citrus"), (9, "potato"), (10, "potato"),
                            (11, "sorghum"), (12, "sorghum"), (13, "bitter_gourd"), (14, "ridgegourd"),
                            (15, "bitter_gourd"), (16, "ridgegourd"), (17, "bottle_gourd"), (18, "potato"),
                            (19, "rice"), (20, "grape"), (21, "grape"), (22, "grape"), (23, "cotton"),
                            (24, "potato")],
        "use_record_pest": [(1, "fruit_borer", "fruit borer"), (2, "stem_borer", "stem borer"), (3, "aphid", "aphids"),
                            (4, "brown_plant_hopper", "brown plant hopper"), (5, "jassid", "jassids"),
                            (6, "jassid", "jassids"), (7, "stem_borer", "stem borer"),
                            (9, "late_blight", "late blight"), (10, "late_blight", "late blight"),
                            (10, "early_blight", "early blight"), (11, "leaf_spot", "leafspot"),
                            (12, "red_leaf_spot", "red leaf spot"), (13, "thrips", "thrips"), (14, "thrips", "thrips"),
                            (15, "thrips", "thrips"), (16, "thrips", "thrips"), (17, "thrips", "thrips"),
                            (18, "aphid", "aphids"), (19, "whitefly", "whiteflies"),
                            (20, "powdery_mildew", "powdery mildew"), (21, "powdery_mildew", "powdery mildew"),
                            (22, "powdery_mildew", "powdery mildew"), (23, "bacterial_blight", "bacterial blight"),
                            (24, "early_blight", "early blight")],
        "generic_member": [
            ("blight", "pest", "bacterial_blight"), ("blight", "pest", "blight"), ("blight", "pest", "early_blight"),
            ("blight", "pest", "late_blight"), ("leafspot", "pest", "leaf_spot"), ("leafspot", "pest", "red_leaf_spot"),
            ("gourd", "crop", "bitter_gourd"), ("gourd", "crop", "bottle_gourd"), ("gourd", "crop", "ridgegourd"),
        ],
        "restriction": [
            (1, "chlorpyriphos", "Chlorpyriphos", "restricted", "Chlorpyriphos is banned for use in Ber, Citrus and Tobacco.", 4),
            (2, "monocrotophos", "Monocrotophos", "restricted", "Monocrotophos is banned for use on vegetables.", 6),
            (3, "spinosad", "Spinosad", "restricted", "Spinosad is banned for use on Ridgegourd.", 7),
        ],
    }  # fmt: skip
    return write(path, tables, {"release": "false"})
