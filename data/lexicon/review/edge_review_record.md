# Review record: edge-audit corrections (2026-11-15)

**Delegation:** the user wrote in chat, "You review dude. I allow you to review them". Every row below is signed `Claude (delegated by Tarun, 2026-11-15)`, never as the user.

**What was reviewed:**
- the 12 entries in `data/corrections.toml`;
- 2 allow entries in `data/anomaly_allowlist.toml`;
- 4 rows added to `data/lexicon/pests.csv`;
- the removal of the crop row `paddy_sheath` (which the user had signed on 2026-11-13).

**Method:** each entry was compared with three sources:
- the extractor's text;
- poppler `pdftotext -layout` (an independent reader of the text layer);
- the rendered page image (`reports/E1/rows/*.png`, 110 dpi).

## Decisions

| Entry | Rendered page agrees? | Decision |
|---|---|---|
| C-01, C-02 (ins. p. 25, Cotton) | Yes: "Cotton" spans both rows | accept |
| C-03 (ins. p. 55, comma after "tabaci)") | Partly: the pest cell is clipped at the column line, so the comma and the ends of "Amrasca" and "Aphid" are hidden. The text layer has them | accept: the comma separates two pests, and the text layer is what the author typed |
| C-04 (ins. p. 80, ")" after "frugiperda") | Partly: the bracket is clipped, as in C-03 | accept, same reason |
| C-05 (fung. p. 60, "infestans) and", "Alternaria") | Yes: the text visibly overflows into the dose cell | accept |
| C-06 (fung. p. 60, Paddy / Sheath Blight) | The page prints "Paddy Sheath" in the crop column and "Blight" in the pest column | accept: "Paddy Sheath" is not a crop, and sheath blight is a paddy disease (the same page lists it for Paddy at line 25) |
| C-07, C-08 (fung. p. 73, Corn) | Yes: one row, "Northern leaf blight, Southern leaf blight" | accept |
| C-09, C-10 (fung. p. 77, Mango) | Yes: one row; "0.33+15" printed in the a.i. cell | accept. This supersedes the earlier allow-list reason "left empty, not guessed": the value is printed, only its cell has no borders |
| C-11 (fung. p. 82, "Leaf Blast", dose 100 + 70 + 50) | **No** for "Blast": it is in the text layer but hidden under the dose cell; the page shows "Sheath Blight, Leaf" | accept, as a judgment: "Leaf" alone is not a disease, the text layer is the author's input, and leaf blast is a standard paddy target for a hexaconazole mixture. Flagged in the entry's evidence |
| C-12 (fung. p. 84, closing bracket) | Yes: visible overflow | accept |
| allow: CELL_STRADDLE fung. p. 76 | The stored "Alternaria" and "153 (13.5 + 139.5)" match the page (cut gap 0.34 pt: the detector's false positive) | accept |
| allow: CELL_OVERLAP ins. p. 84 | The stored "Aphid (Aphis gossypi)" matches the page | accept |
| pests: "tomato late blight and early blight" → late_blight, early_blight | The two diseases named in C-05 | accept |
| pests: "northern leaf blight" → turcicum_leaf_blight; "southern leaf blight" → maydis_leaf_blight | The register itself (use 969) gives *Exserohilum turcicum* and *Bipolaris maydis* for the two corn leaf blights | accept |
| crops: remove `paddy_sheath` | The only use (731) is corrected by C-06 | accept |

**Not decided here, left open:** `turcicum_blight` and `turcicum_leaf_blight` are two IDs for one disease. Merging them is a lexicon change for the next review.
