"""Mutation checks (L1 §12 and the M1 implementation notes). Each mutant is applied to the source,
the named tests are run, and the mutant must turn at least one of them red. Predictions are fixed here
before running. Usage: uv run python tools/mutants.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "labelclaim"
MUTANTS = [
    # id, file, original, mutant, tests, predicted
    ("M1 left edge instead of centre", "extract/geometry.py",
     "owner = _band_of((cell.bbox[0] + cell.bbox[2]) / 2, bands)", "owner = _band_of(cell.bbox[0], bands)",
     ["tests/test_extract.py", "-m", "corpus or not corpus"], "survives (cells start on band edges; equivalent here)"),
    ("M2 covered cell read as empty (no merge inheritance)", "extract/assemble.py",
     "            if not row.covered(col):\n                carried.discard(col)",
     "            if True:\n                carried.discard(col)",
     ["tests/test_extract.py::test_merged_crop_and_values_inherited_within_table"], "killed"),
    ("M3 product reset at a page break", "extract/assemble.py",
     "        self._flush_loose()\n        self._page_has_table = False",
     "        self._flush_loose()\n        self._page_has_table = False\n        self.product = None",
     ["tests/test_golden_pages.py::test_ins_p67_68_value_split_by_the_page_break", "-m", "corpus"], "killed"),
    ("M4 parser invents the upper bound", "normalize/quantities.py",
     "return Quantity(raw, \"range\", (float(tokens[0]),), (float(tokens[1]),), unit, tokens, \"parsed\")",
     "return Quantity(raw, \"range\", (float(tokens[0]),), (float(tokens[0]) * 2,), unit, tokens, \"parsed\")",
     ["tests/test_quantities.py"], "killed"),
    ("M5 provenance re-check skipped", "validate.py",
     "    checked = 0\n    for use in uses:", "    checked = 0\n    return 1\n    for use in uses:",
     ["tests/test_register_validate.py::test_provenance_recheck_passes_and_catches_a_planted_mismatch"], "killed"),
    ("M7 mid-table continuation rule removed", "extract/assemble.py",
     "        if kind in (RowKind.DATA, RowKind.UNMAPPED) and content_started and self._continues_last(row):",
     "        if False:",
     ["tests/test_golden_pages.py::test_fun_p76_dose_range_split_over_grid_rows", "-m", "corpus"], "killed"),
    ("M8 full-row check at table start removed", "extract/assemble.py",
     "        if kind is RowKind.CONTINUATION and self._is_full_row(row):",
     "        if False:",
     ["tests/test_golden_pages.py::test_fun_p38_39_pest_split_by_page_break_with_a_second_application", "-m",
      "corpus"], "killed"),
    ("M9 sliver cells counted in signatures", "extract/geometry.py",
     "return [c for c in row.cells if c is not None and (c.text or c.bbox[2] - c.bbox[0] >= SLIVER)]",
     "return [c for c in row.cells if c is not None]",
     ["tests/test_golden_pages.py::test_only_reviewed_anomalies_remain", "-m", "corpus"], "killed"),
    ("M10 note-like full-width cells taken as products", "extract/classify.py",
     "        if looks_like_note(text):\n            return RowKind.NOTE",
     "        if NOTE.match(text):\n            return RowKind.NOTE",
     ["tests/test_extract.py"], "survives (no synthetic case for a colon/sentence note; see results)"),
    # --- L2 (predictions written 2026-11-14, before running) ---
    ("L2-M1 top fuzzy suggestion used as a match", "lookup/names.py",
     '    return Resolution("unknown", (), tuple(ranked[:MAX_SUGGESTIONS]))',
     '    return Resolution("exact", (ranked[0].id,), ()) if ranked else Resolution("unknown", (), ())',
     ["tests/test_lookup.py"], "killed"),
    ("L2-M2 APPROVED when the pest filter empties the rows", "lookup/engine.py",
     "            if not with_pest:", "            if False:",
     ["tests/test_lookup.py::test_not_approved_for_pest_lists_the_pests_it_is_approved_for"], "killed"),
    ("L2-M3 restriction overlay dropped", "lookup/engine.py",
     "        if not ingredient_keys:\n            return ()", "        if True:\n            return ()",
     ["tests/test_lookup.py"], "killed"),
    ("L2-M4 query text leaks into the access log", "api/app.py",
     "lookup(query)\n        request.state.outcome = answer.outcome.value\n",
     "lookup(query)\n        request.state.outcome = body.model_dump_json()\n",
     ["tests/test_api.py::test_access_log_never_contains_the_query_text"],
     "killed (the pattern matched twice after /v1/ask was added in bd3a494, so it was NOT APPLIED until "
     "2026-11-18; pinned to the lookup endpoint)"),
    ("L2-M5 pest phrases split on 'and' again", "normalize/pests.py",
     'parts = re.split(r"[,;/\\n]", plain)', 'parts = re.split(r"[,;/\\n]|\\band\\b", plain)',
     ["tests/test_pests_ingredients.py"], "killed"),
    ("L2-M6 ingredient lists matched in order", "lookup/names.py",
     "if {i for i, _ in ings} == wanted]", "if [i for i, _ in ings] == [self.ingredient[k][0] for k in keys]]",
     ["tests/test_lookup.py::test_combination_matches_as_a_set"], "killed"),
    ("L2-M7 multi-crop use linked to its first crop only", "build.py",
     'tables["use_record_crop"] += [(uid, cid) for cid in crop_ids]',
     'tables["use_record_crop"] += [(uid, cid) for cid in crop_ids[:1]]',
     ["tests/test_register_validate.py"], "killed"),
    ("L2-M8 restriction never names the crop", "lookup/engine.py",
     "notes.append(RestrictionNote(name, status, detail, page, bool(names & words)))",
     "notes.append(RestrictionNote(name, status, detail, page, False))",
     ["tests/test_lookup.py::test_register_use_that_a_restriction_names_is_a_conflict"], "killed"),
    ("G-M1 APPROVED when only some options are approved", "lookup/engine.py",
     "if options and (general in approved or approved == set(options)):",
     "if options and (general in approved or bool(approved)):",
     ["tests/test_lookup.py::test_general_pest_with_some_options_approved_is_ambiguous"], "killed"),
    ("G-M2 options not filtered by crop", "lookup/engine.py",
     "options = [m for m in members if m in registered]", "options = list(members)",
     ["tests/test_lookup.py::test_general_pest_with_every_option_approved_is_approved_and_names_them"], "killed"),
    ("G-M3 no plural fold in match_key", "normalize/lexicon.py",
     '    if len(k) > 3 and k.endswith("s") and not k.endswith("ss"):\n        return k[:-1]\n',
     "",
     ["tests/test_lookup.py::test_spacing_plural_and_label_variants_resolve_to_one_name"], "killed"),
    ("G-M4 first of two spelling-family matches taken", "lookup/names.py",
     "            if len(same) == 1:", "            if len(same) >= 1:",
     ["tests/test_lookup.py::test_ingredient_spelling_fold_needs_exactly_one_match"], "killed"),
    ("G-M5 the register's own general claim ignored", "lookup/engine.py",
     "if options and (general in approved or approved == set(options)):",
     "if options and approved == set(options):",
     ["tests/test_lookup.py::test_the_registers_own_general_claim_wins"], "killed"),
    ("G-M6 rule collisions not reported", "build.py",
     '        for mk, ids in collisions\n', '        for mk, ids in collisions[:0]\n',
     ["tests/test_register_validate.py::test_two_lexicon_ids_that_are_one_name_by_rule_block_the_build"], "killed"),
    # L1 §16 / ADR-007 (edge defects and reviewed corrections), predictions written 2026-11-15 before the run
    ("E-M1 straddle threshold too tight", "extract/edges.py",
     'return ("straddle" if cut < STRADDLE_GAP else "adjacent"), cut', 'return ("straddle" if cut < 0.1 else "adjacent"), cut',
     ["tests/test_edges.py"], "killed"),
    ("E-M2 text in no cell ignored", "extract/edges.py",
     '    if None in owners:\n        return "orphan", cut', '    if False:\n        return "orphan", cut',
     ["tests/test_edges.py"], "killed"),
    ("E-M3 defects never reach the assembler", "extract/assemble.py",
     "self._edge_anomalies(table, i, defects.pop(i, []))", "self._edge_anomalies(table, i, [])",
     ["tests/test_extract.py"], "killed"),
    ("E-M4 a correction matching 0 rows is skipped", "corrections.py",
     "        if len(hits) != 1:\n", "        if len(hits) > 1:\n            pass\n        if not hits:\n            continue\n        if len(hits) != 1:\n",
     ["tests/test_corrections.py"], "killed"),
    ("E-M5 a correction covers anomalies on any row", "corrections.py",
     "and ref in applied.get(c.id, ())", "and (ref in applied.get(c.id, ()) or True)",
     ["tests/test_corrections.py"], "killed"),
    ("E-M6 unreviewed corrections do not block a release", "build.py",
     "    if unreviewed_fix:\n        out.append", "    if False:\n        out.append",
     ["tests/test_register_validate.py"],
     "survived on the first run (no test covered the gate); killed after test_release_blockers_*"),
    # L1 §17 (split pest cells), predictions written 2026-11-15 before the run
    ("E-M7 text-hugging cells not recognised", "extract/assemble.py",
     "hugs = right < self.bands[Col.PEST + 1] - HUG_MARGIN", "hugs = False",
     ["tests/test_extract.py"], "killed"),
    ("E-M8 nested cells kept", "extract/pages.py",
     "None if b is not None and any(o != b and _inside(b, o) for o in present) else b",
     "b", ["tests/test_extract.py"], "killed"),
    ("E-M9 a pest line joined whatever its merges' origin", "extract/assemble.py",
     "            if anchor is None or anchor.origin != last.rows[0]:\n                return False",
     "            if anchor is None:\n                return False",
     ["tests/test_extract.py"],
     "survived on the first run, as predicted; killed after test_a_pest_line_is_joined_only_to_the_use_its_merges_come_from"),
    # L3 (assistant), predictions written 2026-11-15 before the run
    ("A-M1 number words ignored by the verifier", "assistant/verify.py",
     "[*_digit_numbers(text), *_word_numbers(text)]", "[*_digit_numbers(text)]",
     ["tests/test_verify.py"], "killed"),
    ("A-M2 verifier result ignored", "assistant/loop.py",
     "flagged = verdict.unverified + wording(text)", "flagged = ()",
     ["tests/test_assistant.py"], "killed"),
    ("A-M6 advice wording not checked (NFR-4)", "assistant/loop.py",
     "flagged = verdict.unverified + wording(text)", "flagged = verdict.unverified",
     ["tests/test_assistant.py"], "killed"),
    ("A-M7 the provider's own tool call not echoed back", "assistant/loop.py",
     "call = understood.raw_call or {", "call = {",
     ["tests/test_assistant.py"], "killed"),
    ("A-M3 numbers allowed in a clarifying question", "assistant/loop.py",
     "if not asked or not verify_clarification(asked).ok:", "if not asked:",
     ["tests/test_assistant.py"], "killed"),
    ("A-M4 rate-limit cool-down ignored", "assistant/providers.py",
     "if self._until.get(name, 0.0) > self._clock():", "if False:",
     ["tests/test_providers.py"], "killed"),
    ("A-M5 the question text is logged", "assistant/loop.py",
     "        provider, understood = self.router.run(",
     "        LOG.info(question)\n        provider, understood = self.router.run(",
     ["tests/test_assistant.py"], "killed"),
    # E3n fixes (reports/E3n/first_run.md), predictions written 2026-11-17 before the run
    ("F-M1 no retry with % for a bare strength", "lookup/names.py",
     'if retry != text and parse_heading(retry).status == "parsed":', "if False:",
     ["tests/test_lookup.py"], "killed"),
    ("F-M2 a dropped formulation is not restored", "assistant/loop.py",
     "if ingredient and not product and (typed := product_in_question(", "if False and (typed := product_in_question(",
     ["tests/test_assistant.py"], "killed"),
    ("F-M3 a declined tool call becomes a 503 again", "assistant/loop.py",
     'if "declined" not in str(exc):', "if True:",
     ["tests/test_assistant.py"], "killed"),
    ("F-M4 the user's product-name numbers not allowed", "assistant/loop.py",
     "allowed = allowed_numbers(answer) | self._typed_strengths(query, answer)", "allowed = allowed_numbers(answer)",
     ["tests/test_assistant.py"], "killed"),
    ("F-M6 typed numbers allowed without exact strength matching", "assistant/loop.py",
     "return {v for _, v in numbers(query.product)} & canonical", "return {v for _, v in numbers(query.product)}",
     ["tests/test_assistant.py"],
     "killed; survived on 2026-11-18 (the polish-round guard had made its test skip the rule since eded4fe), "
     "killed again after the test was rephrased"),
    ("F-M5 an ingredient-level approval reads like a product approval", "assistant/templates.py",
     'if by_ingredient else "Approved: "', 'if False else "Approved: "',
     ["tests/test_assistant.py"], "killed"),
    # polish round, predictions written 2026-11-18 before the run
    ("P-M1 a short name shared by two ingredients folds anyway", "lookup/names.py",
     "return found[0] if len(found) == 1 else None", "return found[0] if found else None",
     ["tests/test_lookup.py"], "killed"),
    ("P-M2 a mis-copied strength is trusted", "assistant/loop.py",
     "if sorted(v for _, v in numbers(typed)) != sorted(v for _, v in numbers(product)):",
     "if False:", ["tests/test_assistant.py"],
     "survived on the first run (the test's mis-copy was not a registered product); killed after "
     "test_a_mis_copy_that_is_another_registered_product_still_takes_the_users_strength"),
    ("P-M3 a pest word dragged into the product is kept", "assistant/loop.py",
     "return typed if typed_ok and not model_ok else product", "return product",
     ["tests/test_assistant.py"], "killed"),
    # fix A (E3n-c NC-034); predictions written before running, 2026-11-18
    ("FA-M1 the user's typed crop never replaces the model's", "assistant/loop.py",
     "        return mentions[0][0]\n", "        return crop\n", ["tests/test_assistant.py"], "killed"),
    ("FA-M2 two crops in the question no longer keep the model's reading", "assistant/loop.py",
     "if len(typed) != 1:", "if not typed:", ["tests/test_assistant.py"],
     "survived without the 'egg plant ya tamatar' case (checked by running it); killed with it"),
    ("FA-M3 crop words inside the model's pest are counted", "assistant/loop.py",
     'text = re.sub(re.escape(pest), " ", question, flags=re.IGNORECASE) if pest else question',
     "text = question", ["tests/test_assistant.py"], "killed"),
    ("FA-M4 the unit word 'gram' counts as a crop", "assistant/loop.py",
     "names.crop_mentions(text) if match_key(s) not in NOT_CROPS]", "names.crop_mentions(text) if True]",
     ["tests/test_assistant.py"], "killed"),
    ("FA-M5 a different crop the user also wrote is replaced", "assistant/loop.py",
     "(set(model.ids) == typed or written_in(question, crop))", "set(model.ids) == typed",
     ["tests/test_assistant.py"], "killed"),
    ("FA-M6 a reply naming the rejected crop is delivered", "assistant/loop.py",
     "if rejected and written_in(text, rejected):", "if False:", ["tests/test_assistant.py"], "killed"),
    ("FA-M7 the tool result does not say which crop was looked up", "assistant/loop.py",
     'result["crop_looked_up"] = f"{query.crop} (as the user wrote it; not {rejected})"', "pass",
     ["tests/test_assistant.py"], "killed"),
    ("FA-M8 shortest alias first", "lookup/names.py",
     "for n in range(min(MAX_ALIAS_WORDS, len(words) - i), 0, -1):",
     "for n in range(1, min(MAX_ALIAS_WORDS, len(words) - i) + 1):", ["tests/test_assistant.py"], "killed"),
    # fix B (E3n-d "which crop?"); predictions written before running, 2026-11-18
    ("FB-M1 the clarifying question always stands", "assistant/loop.py",
     "        if filled is not None:\n            return _Understood(call.id, _slots(filled)",
     "        if False:\n            return _Understood(call.id, _slots(filled)", ["tests/test_assistant.py"], "killed"),
    ("FB-M2 two different products in the question are accepted", "assistant/loop.py",
     "if len({ids for _, _, ids in found}) != 1:", "if not found:", ["tests/test_assistant.py"], "killed"),
    ("FB-M3 two crops in the question are accepted", "assistant/loop.py",
     "if len({i for _, ids in mentions for i in ids}) != 1:  # no crop, or two crops",
     "if not mentions:  # no crop, or two crops", ["tests/test_assistant.py"],
     "survived on the first run (the leftover 'athava' made a second phrase, so the phrase rule caught it); "
     "killed after 'athava' became a linking word and the 'tamatar ya bhatta' case was added"),
    ("FB-M4 the first of two leftover phrases is taken as the pest", "assistant/loop.py",
     "if len(phrases) > 1:", "if False:", ["tests/test_assistant.py"], "killed"),
    ("FB-M5 linking words are not trimmed", "assistant/loop.py",
     "    while words and words[0].lower() in _EDGE_WORDS:\n        words.pop(0)\n",
     "", ["tests/test_assistant.py"], "killed"),
    ("FB-M6 an unknown pest is dropped, widening the answer to the whole crop", "assistant/loop.py",
     "pest=phrases[0] if phrases else None)", "pest=None)", ["tests/test_assistant.py"], "killed"),
    ("FB-M7 a malformed clarifying call is accepted", "assistant/loop.py",
     "if missing not in CLARIFY:  # a malformed call", "if False:  # a malformed call",
     ["tests/test_assistant.py"], "killed"),
    ("FB-M8 an unread pest phrase is dropped even when the crop has uses", "assistant/loop.py",
     "if self.engine.lookup(bare).outcome is Outcome.NOT_APPROVED_FOR_CROP:", "if True:",
     ["tests/test_assistant.py"], "killed"),
    ("FB-M9 an unread pest phrase is kept even when the crop has no uses", "assistant/loop.py",
     "                return bare\n", "                return query\n", ["tests/test_assistant.py"], "killed"),
    # after E3n-e (fix A2, the g/l pattern); predictions written before running, 2026-11-18
    ("FA-M9 extra words in the model's crop are dropped again", "assistant/loop.py",
     "if written_in(crop, users) and _trim(", "if False and _trim(",
     ["tests/test_assistant.py"], "killed"),
    ("FA-M10 an ambiguous question still replaces the model's crop", "assistant/loop.py",
     "            if filled is None:\n                return understood\n",
     "            if filled is None:\n                return dataclasses.replace(understood, "
     "query=dataclasses.replace(query, crop=users))\n", ["tests/test_assistant.py"], "killed"),
    ("P-M4 a code followed by '/' ends a product name", "assistant/loop.py",
     "(?:{FORMULATIONS})\\b(?!\\s*/)", "(?:{FORMULATIONS})\\b", ["tests/test_assistant.py"], "killed"),
    # fix E and the empty crop (after E3n-e); predictions written before running, 2026-11-18
    ("FE-M1 a reply equating two crops is delivered", "assistant/loop.py",
     "if (other := self._attached_crop(text, query.crop)) is not None:", "if (other := None) is not None:",
     ["tests/test_assistant.py"], "killed"),
    ("FE-M2 a comma joins two crop names into a claim", "assistant/loop.py",
     'r"\\s*(?:\\(|\\[|=|\\(\\s*i\\.e\\.,?)\\s*"', 'r"\\s*(?:\\(|\\[|=|,|\\(\\s*i\\.e\\.,?)\\s*"',
     ["tests/test_assistant.py"], "killed"),
    ("FE-M3 a bracket naming a crop that overlaps the user's is blocked", "assistant/loop.py",
     "if ours[0] != ours[1] and not (ids1 & ids2):", "if ours[0] != ours[1]:", ["tests/test_assistant.py"],
     "killed"),
    ("FE-M4 the user's own unrecognised crop word is not paired", "assistant/loop.py",
     "            if not any(s <= m.start() < e for s, e, _ in spans):", "            if False:",
     ["tests/test_assistant.py"], "killed"),
    ("EC-M1 an empty crop fails over again", "assistant/loop.py",
     "            if not crop:  # E3n-e RE-01", "            if False:  # E3n-e RE-01", ["tests/test_assistant.py"],
     "killed"),
    # fix A3 and the w/w strength (after E3n-f); predictions written before running, 2026-11-18
    ("FA-M11 the model's dropped pest is not restored", "assistant/loop.py",
     "        return self._never_wider(understood, user_text)", "        return understood",
     ["tests/test_assistant.py"], "killed"),
    ("FA-M12 a long instruction is taken as the pest", "assistant/loop.py",
     "or len(reading.pest.split()) > A3_MAX_PEST_WORDS:", ":", ["tests/test_assistant.py"], "killed"),
    ("L2-M9 w/w no longer ends a bare strength", "lookup/names.py",
     "(?:\\+|$|w/[wv]\\b|(?:{FORMULATIONS})\\b)", "(?:\\+|$|(?:{FORMULATIONS})\\b)",
     ["tests/test_lookup.py"], "killed"),
    # pilot fixes (after the first private test); predictions written before running, 2026-11-19
    ("PX-M1 a crop-specific ban no longer leads the headline", "assistant/templates.py",
     "if answer.outcome is Outcome.APPROVED and answer.conflict and use is not None:", "if False:",
     ["tests/test_assistant.py"], "killed"),
    ("PX-M2 an assistant turn with numbers is kept in the history", "assistant/loop.py",
     'elif role == "assistant" and len(text) <= 200 and verify_clarification(text).ok:', 'elif role == "assistant":',
     ["tests/test_assistant.py"], "killed"),
    ("PX-M3 earlier turns are not sent to the model", "assistant/loop.py",
     "            *_earlier_turns(history),\n", "", ["tests/test_assistant.py"], "killed"),
]  # fmt: skip


def run(tests: list[str]) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", *tests], cwd=ROOT, capture_output=True, check=False
    )
    return proc.returncode == 0


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    rows = []
    baseline: dict[tuple[str, ...], bool] = {}  # a red suite "kills" every mutant, so it must pass unmutated
    for mid, rel, original, mutant, tests, predicted in MUTANTS:
        if only and not mid.startswith(only):
            continue
        if tuple(tests) not in baseline:
            baseline[tuple(tests)] = run(tests)
        if not baseline[tuple(tests)]:
            rows.append((mid, predicted, "BASELINE FAILS (the tests are red without the mutant)"))
            continue
        path = SRC / rel
        source = path.read_text(encoding="utf-8")
        if source.count(original) != 1:
            rows.append((mid, predicted, "NOT APPLIED (pattern not found exactly once)"))
            continue
        path.write_text(source.replace(original, mutant), encoding="utf-8")
        try:
            outcome = "survived" if run(tests) else "killed"
        finally:
            path.write_text(source, encoding="utf-8")
        rows.append((mid, predicted, outcome))
    print("| Mutant | Predicted | Outcome |\n|---|---|---|")
    for mid, predicted, outcome in rows:
        print(f"| {mid} | {predicted} | {outcome} |")
    # A mutant whose pattern no longer matches tests nothing; L2-M4 went unnoticed for two days (2026-11-18)
    # (2026-11-18: a failing test once made five new mutants look killed; the baseline now catches that)
    unapplied = [mid for mid, _, outcome in rows if outcome.startswith(("NOT APPLIED", "BASELINE FAILS"))]
    if unapplied:
        print(f"ERROR: not applied: {', '.join(unapplied)}", file=sys.stderr)
    return 1 if unapplied else 0


if __name__ == "__main__":
    raise SystemExit(main())
