"""E3n-c, C-P4 engine side: do the names resolve *as the user typed them*, whatever the model passed?

Run: uv run python evaluation/e3nc/lexicon_check.py build/register.sqlite
Written 2026-11-18, after the live run, to separate the engine's part of C-P4 from the model's.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from labelclaim.lookup.names import Names

HERE = Path(__file__).parent

# the local crop name in each variant question, and the %-less product text, copied from items.jsonl
TYPED_CROP = {
    "NC-019": "chai bagan", "NC-020": "kapas", "NC-021": "chai bagan", "NC-023": "gehu", "NC-024": "aloo",
    "NC-025": "angoor", "NC-026": "tamatar", "NC-027": "aalugadde", "NC-028": "eerulli", "NC-029": "mirchi",
    "NC-030": "drakshi", "NC-031": "patta gobhi", "NC-033": "menasinakayi", "NC-034": "bende",
    "NC-035": "makka", "NC-036": "bhatta",
}  # fmt: skip
# NC-021 and NC-027 name unregistered products; NC-032 states g/l, so it has no "%" to drop
TYPED_PRODUCT = {
    "NC-019": "mancozeb 63 + carbendazim 12 WP", "NC-020": "gossyplure 4 RTU", "NC-022": "carbendazim 50 WP",
    "NC-023": "carbendazim 1.92 + mancozeb 10.08 GR", "NC-024": "difenoconazole 10 + mancozeb 50 WDG",
    "NC-025": "lambda cyhalothrin 4.9 CS", "NC-026": "metiram 55 + pyraclostrobin 5 WG",
    "NC-028": "tebuconazole 25.9 EC", "NC-029": "nitenpyram 25 SP", "NC-030": "hexaconazole 5 SC",
    "NC-031": "metaflumizone 22 SC", "NC-033": "emamectin 1.1 + diafenthiuron 30 SC",
    "NC-034": "emamectin 5 SG", "NC-035": "emamectin 5 + lufenuron 40 WG",
    "NC-036": "cyantraniliprole 10.26 OD",
}  # fmt: skip


def main(register: str) -> None:
    names = Names(sqlite3.connect(f"file:{register}?mode=ro", uri=True))
    items = {}
    for line in (HERE / "items.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        items[item["id"]] = item
    crops = 0
    for i, text in TYPED_CROP.items():
        got, want = names.crop(text), names.crop(items[i]["structured"]["crop"])
        good = got.status == "exact" and got.ids == want.ids
        crops += good
        print(i, repr(text), got.status, got.ids, "want", want.ids, "OK" if good else "NO")
    products = 0
    for i, text in TYPED_PRODUCT.items():
        got = names.product(text, ingredient_level=False)
        want = names.product(items[i]["structured"]["product"], ingredient_level=False)
        good = got.status == "exact" and got.product_ids == want.product_ids
        products += good
        print(i, repr(text), got.status, got.product_ids, "OK" if good else "NO")
    print(f"crop names as typed: {crops}/{len(TYPED_CROP)}")
    print(f"products as typed: {products}/{len(TYPED_PRODUCT)}")


if __name__ == "__main__":
    main(sys.argv[1])
