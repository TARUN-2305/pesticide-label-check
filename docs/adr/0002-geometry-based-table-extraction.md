# ADR-002: Deterministic, geometry-based table extraction

Status: proposed (2026-11-13)

## Context
The data spike of 2026-11-13 over both PDFs found the following:
- **Born-digital tables.** Both PDFs were exported from Microsoft Word, and pdfplumber finds a table on 106 of the 108 insecticide pages.
- **Rows split into a varying number of cells.** Merged or split cells produce rows of **4 to 15 cells** for 6 logical columns.
- **No common column grid.** Column x-positions differ between tables (83 distinct edge signatures in the single-product section).
- **Products continue across pages.** 68 of 107 insecticide pages start with a data row, not a product heading.
- **The document's own index has wrong page numbers.** It is 1 to 3 pages off.

## Decision
1. Use **pdfplumber** cell geometry.
2. For each table, derive **column bands** from that table's header row, or else from its most common full-width row.
3. Assign each cell to a band by the x-centre of the cell. Concatenate the cells that fall in the same band.
4. Carry the section, product and crop context across rows and pages with an explicit state machine.
5. Detect sections from the heading text, never from the printed index.
6. Rows that cannot be mapped become **anomalies** in a report. They are never dropped silently and never guessed.

## Alternatives considered
| Option | Why not |
|---|---|
| Layout text (`pdftotext -layout`) and regexes | Multi-line cells interleave. Column alignment is visual, not structural. |
| Camelot / Tabula | Similar lattice detection, plus a Java (Tabula) or Ghostscript dependency. No advantage on Word exports. |
| LLM / vision extraction | Not deterministic. It can invent or transpose numbers, which is unacceptable for doses and waiting periods. |

## Consequences
- **Plus:** the output is deterministic and every value traces to a cell bounding box on a page.
- **Minus:** the code is tied to the layout. A new edition may need new rules, but the anomaly budget makes that visible instead of silent.
