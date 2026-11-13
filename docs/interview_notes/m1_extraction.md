# Interview note: M1, register extraction

## The story in 45 seconds

> "The register is a 200-page Word-to-PDF export. I first profiled every page instead of guessing, and the data broke my design three times:
> - one PDF table can hold products with different column widths;
> - cells span two columns;
> - rows continue across page breaks, and even outside the ruled table.
>
> Each time, the fix was a small, named rule with a test built from that real page, so 'it works' always meant 'it works on page 76 and here's the test'.
>
> Every one of the ~14,000 stored values is re-read from its box in the PDF on every build. I verified 22 hard rows against images of the pages. The build is reproducible to the byte across hash seeds, and a release build refuses to run until a human has reviewed every anomaly and every crop alias."

## Decisions you should be able to defend

| Decision | Why | Evidence |
|---|---|---|
| Positions, not text | Rows have 4–15 cells for 6 columns; text alignment is visual only | L1 §2 F2–F3; `test_cells_assigned_by_centre…` |
| Bands per product block, not per table | Insecticide p. 8: one table, two products, different widths. Per-table bands put the crop in the pest column | `test_each_product_block_gets_its_own_bands`; golden p. 8 |
| A cell across two columns belongs to the leftmost; the other column is "spanned" (empty, marked) | Fungicide p. 20: "2.0" covers formulation and dilution. Copying it would invent a dilution value | `test_spanned_value_is_not_duplicated…`; golden p. 20 |
| `None` ≠ `""` | pdfplumber gives `None` for a grid position covered by a merge, `""` for a real empty cell. That difference is what tells "same as above" apart from "blank" | L1 F4; p. 20 Maize test |
| Continuation rules are about *unfinished* values | "136 (12 + 124) –" ends with a dash, so the next row's "153 (13.5 + 139.5)" finishes it; a row with fresh numbers in ≥ 2 columns is a new row | golden p. 76, p. 38/39 |
| Unknown layout ⇒ anomaly, not a guess | The rodenticide table on p. 7 has 3–4 different columns; mapping it to crop/pest/dose would produce plausible nonsense | `UNMAPPED_TABLE` p. 7 on the allow-list, with a reason |
| Two labels corrected only with evidence | The image read "Indianhouse"; the PDF's characters are "Indian house" (a space with negative width). I checked the characters before changing the expectation, and wrote down why | `test_golden_pages.py` docstring |

## Questions to expect

- *"How do you know the extraction is right?"* Four layers:
  1. golden rows typed from page images;
  2. a provenance re-check of every value on every build;
  3. invariants that turn data problems into anomalies;
  4. mutation tests that prove the tests catch the bugs I'd expect.

  Then be honest: the 120-row stratified golden set and the independent re-labelling are not done yet.
- *"What was the hardest bug?"* Tables continuing across pages: a merged cell whose text sits on the previous page arrives on the new page as an empty anchor. The fix takes the completed value from the use row that the continuation was appended to (insecticide p. 15, fungicide p. 75).
- *"Why is it slower than you'd like?"* About 40 s per build. Nearly all of it is pdfplumber table detection plus the provenance re-check. That's fine for a batch job that runs a few times a year; I measured it rather than optimising blindly.

## Study links

- **Geometry and intervals; sorting and bisect** (the re-extractor indexes characters by vertical midpoint): `study/modules/DSA4_sorting_searching_dp.md`
- **Testing levels, property tests, mutation testing:** `study/modules/SE2_testing_review_debugging.md`
- **Determinism, lockfiles, CI:** `study/modules/SE3_build_ci_git_tooling.md`
