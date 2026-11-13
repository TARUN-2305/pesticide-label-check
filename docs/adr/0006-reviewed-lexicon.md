# ADR-006: Names resolve through a reviewed lexicon; fuzzy matching only suggests

Status: proposed (2026-11-13)

## Context
- **The register spells names inconsistently.** The spike found 142 distinct crop strings, including "chili", "chilli", "chilies", "chilli`", "barely" (meaning barley), and "bittergourd" vs "bitter gourd".
- **Users say names in local ways.** They use Kannada names, Hindi names ("bhindi"), and common pest names.

## Decision
- Keep `data/lexicon/crops.csv` and `pests.csv` (columns `canonical_id, alias, language, source, reviewed_by`). They are versioned in git and their hash goes into the build manifest.
- During the build, every register crop or pest string must map to a canonical ID. Any that does not becomes an anomaly.
- At query time, the system resolves an exact alias (case-folded, Unicode NFC, whitespace-collapsed) first. If there is none, fuzzy matching (normalised Levenshtein, threshold fixed in L2) returns **suggestions only**, and the outcome is `AMBIGUOUS` or `UNKNOWN_*`.

## Consequences
- Wrong silent mappings ("chickpea" taken as "cowpea") cannot happen.
- Curating the lexicon is manual work. It is limited to about 140 crop strings plus the pests, and every addition is a reviewed diff.
