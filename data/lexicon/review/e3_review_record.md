# Review record: E3 lexicon and design decisions (2026-11-14)

## Who decided

The user delegated this review in chat on 2026-11-14: *"I say you do research and review yourself, I approve"*.

- **Reviewer:** the assistant (Claude).
- **Signature:** lexicon rows changed by this review are signed `Claude (delegated by Tarun, 2026-11-14)`. That is not the user's own signature.
- **Reversible:** every change can be undone row by row. The files are `e3_pest_merges.csv`, `e3_crop_aliases.csv` and `e3_generic_terms.csv`, each with its `decision` column.

## Decisions (L2 §13.7)

| ID | Decision | Note |
|---|---|---|
| D1 | **Accepted:** the matching rule, and its 37 `rule:match-key` merges | Every group was read; all are spacing, hyphen, plural or label variants of one name |
| D2 | **Accepted 27, rejected 3** of the `review` rows | Rejected: phytophthora foot rot vs root rot; flea beetle vs leaf beetle; "saw drug store beetle" (two pests joined, an extraction issue) |
| D3 | **Accepted** all 23 crop aliases | Sources below; "Bhendi" is unsourced (my own knowledge) |
| D4 | **Accepted** the 11 general terms, one changed | "millet" now includes **sorghum** |
| D5 | **Accepted** "all options approved → APPROVED, naming the forms", with one refinement | See below |
| D6 | **Accepted** the ingredient spelling fold at query time | — |

### Refinement to D5, made during this review

**The case.** Sometimes the register itself makes the general claim. On jowar, the Mancozeb 75 % WP row reads "Leafspot", the plain general name. A user asking "leaf spot" there is asking exactly what the register says.

**What was wrong with the draft.** The draft rule would have answered AMBIGUOUS, because the jowar options also include "red leaf spot". The draft therefore treated the register's own general entry as just one more option.

**The rule now.** If this product's rows on the crop list the general entry itself (the pest whose name *is* the term), the answer is APPROVED. The uses then cover every approved option, and the options are listed.

I found this while checking D5 against E3-147, an existing E3 query. So it is a fix informed by the suite, and the fresh E3b suite is what measures it fairly.

## Sources checked (accessed 2026-11-14)

| Name(s) | Finding | Source |
|---|---|---|
| urad, urd → black gram | Black gram, *Vigna mungo* | [TNAU Agritech: Blackgram](https://agritech.tnau.ac.in/agriculture/pulses_blackgram.html); "urad or urd bean" in a non-official deck ([slideshare](https://de.slideshare.net/SUDHIRYADAV134/blackgram)) |
| tur, toor, arhar → pigeon pea (red gram) | "red gram, tur or arhar", *Cajanus cajan*; regional names Tur and Arhar | [Vikaspedia: pigeon pea](https://en.vikaspedia.in/viewcontent/agriculture/crop-production/package-of-practices/pulses/pigeon-pea?lgn=en); [MoEF&CC/IIPR biology document](https://bangladeshbiosafety.org/wp-content/uploads/2017/06/Biology_of_cajanus_cajan_pigeon_pea_In.pdf) |
| gingelly, til, sesame → sesamum | TNAU files sesame (*Sesamum indicum*) under "gingelly"; USDA germplasm records give the vernacular name "Til" | [TNAU Agritech: Sesame](https://agritech.tnau.ac.in/agriculture/2/oilseeds_gingelly.html); [USDA GRIN PI book](https://www.ars-grin.gov/npgs/pi_books/scans/156/pi156_097.pdf) |
| guar → cluster bean | "popularly known as Guar in India" | [Vikaspedia: cluster bean](https://en.vikaspedia.in/agriculture/crop-production/package-of-practices/vegetables-1/cluster-bean) |
| bhindi, ladies finger → okra | Common names "Ladies Finger, Okra, Bhindi" | [Vikaspedia: bhindi (okra)](https://en.vikaspedia.in/viewcontent/agriculture/crop-production/package-of-practices/vegetables-1/bhindi-okra) |
| baingan, eggplant → brinjal | "baingan (Hindi), badane (Kannada)" | [Vikaspedia: brinjal](https://en.vikaspedia.in/viewcontent/agriculture/crop-production/package-of-practices/vegetables-1/brinjal) |
| millet = pearl millet, finger millet, sorghum, small millets | Sorghum and pearl millet are the "major millets"; finger millet is listed with them or on its own | [ICAR Indian Farming](https://epubs.icar.org.in/index.php/IndFarm/article/download/132588/49113/348447); [PIB](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2023/mar/doc2023318173501.pdf); [Vikaspedia: millets](https://en.vikaspedia.in/viewcontent/health/nutrition/nutritive-value-of-foods/nutritive-value-of-cereals-and-millets/millets-natural-fortified-cereals?lgn=en) |
| blast (leaf, neck, node, collar, panicle) | One disease with several forms, so "blast" is a general term with its forms as members, and "rice blast" / "blast disease" are the same disease | [TNAU Agritech: rice blast](https://agritech.tnau.ac.in/crop_protection/rice_diseases/rice_1.html); [review, PMC8804147](https://pmc.ncbi.nlm.nih.gov/articles/PMC8804147) |

**Not sourced (my own knowledge, kept because each is a plain spelling or translation):**
- "Bhendi" (a spelling of bhindi);
- "Shimla mirch" (capsicum);
- "Chana" (chickpea);
- "Mung bean" (green gram);
- "Peanut" (groundnut);
- "Aubergine" (brinjal);
- the pest typo merges, each of which is a misspelling of a name printed elsewhere in the same register.
