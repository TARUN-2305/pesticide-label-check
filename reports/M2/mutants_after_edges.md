| Mutant | Predicted | Outcome |
|---|---|---|
| M1 left edge instead of centre | survives (cells start on band edges; equivalent here) | killed |
| M2 covered cell read as empty (no merge inheritance) | killed | killed |
| M3 product reset at a page break | killed | killed |
| M4 parser invents the upper bound | killed | killed |
| M5 provenance re-check skipped | killed | killed |
| M7 mid-table continuation rule removed | killed | killed |
| M8 full-row check at table start removed | killed | killed |
| M9 sliver cells counted in signatures | killed | killed |
| M10 note-like full-width cells taken as products | survives (no synthetic case for a colon/sentence note; see results) | killed |
| L2-M1 top fuzzy suggestion used as a match | killed | killed |
| L2-M2 APPROVED when the pest filter empties the rows | killed | killed |
| L2-M3 restriction overlay dropped | killed | killed |
| L2-M4 query text leaks into the access log | killed | killed |
| L2-M5 pest phrases split on 'and' again | killed | killed |
| L2-M6 ingredient lists matched in order | killed | killed |
| L2-M7 multi-crop use linked to its first crop only | killed | killed |
| L2-M8 restriction never names the crop | killed | killed |
| G-M1 APPROVED when only some options are approved | killed | killed |
| G-M2 options not filtered by crop | killed | killed |
| G-M3 no plural fold in match_key | killed | killed |
| G-M4 first of two spelling-family matches taken | killed | killed |
| G-M5 the register's own general claim ignored | killed | killed |
| G-M6 rule collisions not reported | killed | killed |
| E-M1 straddle threshold too tight | killed | killed |
| E-M2 text in no cell ignored | killed | killed |
| E-M3 defects never reach the assembler | killed | killed |
| E-M4 a correction matching 0 rows is skipped | killed | killed |
| E-M5 a correction covers anomalies on any row | killed | killed |
| E-M6 unreviewed corrections do not block a release | survived on the first run (no test covered the gate); killed after test_release_blockers_* | killed |
