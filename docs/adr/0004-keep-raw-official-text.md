# ADR-004: Keep and show the raw official text

Status: proposed (2026-11-13)

## Context
The register's values are very heterogeneous. In the 6-column rows of the insecticide register:
- **Waiting period:** a whole number in 586 cells; "NA" or "-" in 129; empty in 63; free text in 18 ("Partial-1 hour. Full-(6-8) hour.").
- **a.i. dose:** ranges, percentages ("0.00048-0.00096%"), per-litre values ("0.014/L") and per-tree dilutions.

## Decision
- Every `use_record` stores the raw text of each field exactly as extracted, plus an optional parsed `Quantity`. Each parse has a `parse_status` of `parsed`, `partial` or `unparsed`.
- The UI and the API always show the raw text. Parsed values are used only for comparison and filtering.

## Consequences
- Parsing never has to cover 100 % of cases to be safe.
- The answer can always be checked against the PDF by eye.
