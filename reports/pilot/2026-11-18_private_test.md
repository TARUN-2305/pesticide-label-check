# First private test: findings (2026-11-18, evening)

**Who and how:** the user and ChatGPT tested the app in the browser pane, in test mode (`--pilot-log`). The log, `pilot/pilot.jsonl`, is kept on this machine only (gitignored): 38 records, 25 questions and 13 ratings. ChatGPT's QA report numbers its tests 1–18. Each claim below was checked against the log record and the release register `285c851f…`. Feedback notes are cut at 300 characters, the page's limit, so some reasons are partial.

## The report's claims, checked

| Test (log #) | Claim | Checked | Cause | Fix |
|---|---|---|---|---|
| 1 (#1, #3) | **False negative:** Hexaconazole 5% EC is registered for tikka on groundnut (p. 14), but the app said "not listed for this pest" | **True** | The pest lexicon has three IDs for one disease: `tikka`, `tikka_disease`, `tikka_leaf_spot`. The row uses `tikka_leaf_spot`; "tikka" resolves to `tikka`. A scan finds **396 pest pairs** on a shared crop where one name's words lie inside the other's. Many are different pests (aphid vs mustard aphid); some are the same (anthracnose vs anthracnose disease) | **Engine:** when the answer would be "not listed for this pest", but the product's own rows on this crop name a pest containing the asked words, answer AMBIGUOUS and list them ("listed for *Tikka leaf spot*: is that your pest?"). **Lexicon:** merge the tikka IDs, after review |
| 18 (#36–#38) | **Wrong crop:** asked about brinjal, answered about tomato | **True, and my bug** | The page joins a reply to a clarifying question. The earlier question was joined **twice** (#37), and then a **new, unrelated question** was joined to it (#38), so the model took "tomato" from the old text. "badnekayi" (a spelling of brinjal) is also not in the lexicon | Join only short replies (an answer to "which crop?"), never a full new question or a repeat; add a "New question" button |
| 6 (#12) | **Contradiction:** "Warning: a ban or restriction applies … Approved: Mancozeb 75% WP on Jowar" | **True** | The restriction list says "Mancozeb is banned for use on Guava, **Jowar** and Tapioca (S.O. 4294(E), 3 Oct 2023)". The register (30.09.2026) still prints the claim. The headline template puts "Approved" after a short warning | When a restriction names the asked crop as banned, the headline says **banned on this crop** first, and that the register still prints the claim, with both sources |
| 8 (#16) | "aalugaddeyalli" (in potato) not recognised | **True** | The Kannada locative "-yalli" is joined to the word; the lexicon has "aalugadde" | A reviewed list of Kannada case endings (-ge, -kke, -alli, -yalli, -nalli, -dalli, -ige, -ina…), stripped only when what remains is an exact crop name |
| 13 (#25–#27) | Irrelevant restrictions; incomplete alternatives | **True** | The Mancozeb ban on guava, jowar and tapioca is shown for tomato. Of **20** approved alternatives for tomato late blight, the page and the model saw 5, in alphabetical order. **Mancozeb 75% WP, which is approved for tomato late blight, was not among them**, though it is the user's own ingredient in another formulation | Show only restrictions that name the asked crop (others under a smaller "other restrictions on this ingredient"); same-ingredient alternatives first; the page lists all |
| 15 (#30) | A herbicide is reported as "product not found" | **True** | Only the insecticide and fungicide registers are loaded; the fallback text "See the suggestions and options in the answer." is unhelpful | Say plainly that herbicides are not covered yet when the question is about weeds or the ingredient is a known herbicide; replace that fallback text |
| 16 (#32, #34) | Brand-name reply needs farmer-friendly wording | **True** | "Roundup" has no strength or code. The second attempt was blocked and fell back to the same unhelpful text | For a name with no strength or code: "this looks like a brand name; type the name printed under it, with its % and code" |
| 17 (#36) | A symptom ("brown spots on leaves") is answered with "which product?" | **Partly** | The app cannot diagnose from symptoms, by design. But it also cannot list the registered options for a crop and disease when no product is named, which the requirements' extension-worker persona asks for | Say it cannot diagnose and ask for the disease name; then list the register's approved options for that crop and disease (a new "options" query) |
| 7 (#14, #15) | "Wet slurry treatment" shown under "Days before harvest" | **True** (wording) | That cell holds notes for seed treatments | Label it "Waiting period (as printed)" |

## Found in the log, not in the report

| Log # | What | Why it matters |
|---|---|---|
| #8 | "early blight **and** late blight": the model left the pest out, and fix A3 skipped the 5-word phrase, so the answer was crop-wide. It was correct here only because both are approved | A3's 4-word limit lets a two-disease question widen. Better: split "X and Y" into two pest checks |
| #16 | For an unknown crop, the reply still talked about the Mancozeb ban on guava, jowar and tapioca | The same irrelevant-restriction issue as test 13 |
| #28 | Crop-level "Approved: Mancozeb 35% SC on Tomato": the headline does not say for which diseases | A crop-level yes should name the registered pests in the headline |

## Order of fixes (safety first)

1. **Test 6:** a crop-specific ban must lead the headline. Never "Approved" first.
2. **Test 18:** the conversation joining (my bug).
3. **Test 1:** near-name options instead of a false "not listed"; merge the tikka IDs.
4. **Test 13:** relevant restrictions only; same-ingredient alternatives first; show all alternatives.
5. **Test 8:** Kannada case endings.
6. **Messages:** herbicides, brand names, symptoms (with an options query), the unknown-product fallback, and the waiting-period label.

Each fix gets tests and mutants, and a replay on the recorded suites and this log, before a fresh private test.
