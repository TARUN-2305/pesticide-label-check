# L4: the phone-friendly web app (M6, FR-10)

**Status:** designed 2026-11-18, before any web code.

## 1. What it is for

A dealer at a busy counter, on a phone, asks "is this approved, at what dose, how many days before harvest?" and gets the register's answer with its page, in a few seconds (requirements §2, US-1 to US-5).

**Not:**
- an account system;
- a history of questions (NFR-5: nothing personal stored);
- advice ("recommended" never appears; NFR-4);
- voice (M5).

## 2. Screens (one page, two tabs)

| Tab | Input | Calls | Shows |
|---|---|---|---|
| **Ask** (default) | one free-text box, in any language, as people type it | `POST /v1/ask` | the template headline first, then the model's message; any clarifying question appears as a question with the box kept |
| **Check** | product, crop and optional pest, each with suggestions | `GET /v1/products`, `/v1/crops`, `/v1/pests`, then `POST /v1/lookup` | the same answer card, with no model involved |

**Check works when the models do not.** If `/v1/ask` answers 503, the page says so and opens Check.

**The answer card, top to bottom:**
1. a ban or restriction warning, if any (US-4);
2. the headline (the engine's outcome, never the model's);
3. the message;
4. each cited row: crop, pest, dose a.i., dose of product, dilution and waiting period **as printed** (NFR-4), with page and document;
5. a link to the official PDF page (the citation URL);
6. for "not approved": what the register does approve (US-2);
7. "Register as on <date>" (US-5) and the disclaimer (§7 of the requirements).

## 3. Decisions

| Decision | Why | Alternative rejected |
|---|---|---|
| Plain HTML, CSS and JavaScript modules in `web/`, served by the same FastAPI app; **no npm, no build step** | One container. Nothing to lock or audit beyond the Python dependencies (NFR-7). A page under 50 KB loads on a slow phone connection | React or Vite: a toolchain and hundreds of packages for two forms |
| All API text goes into the page with `textContent`, never `innerHTML` | Model text and register text are data. This is what stops script injection (T-new below) | Sanitising HTML: more code, and one bug is enough |
| A Content-Security-Policy of `default-src 'self'`; no inline script, no external fonts or CDNs | Defence in depth, plus offline-friendly caching | — |
| UI labels in English and Kannada; answers in the language the model replies in (Ask), template English (Check) | M5 owns full Kannada. The Kannada labels are drafted by the assistant and **need the user's review** before the pilot | Machine-translating register text: that would put unreviewed words next to official ones |
| A daily cap on `/v1/ask` (default 800 a day, below Groq's free 1,000), on top of the existing per-minute bucket | A public link must not exhaust the free key. Over the cap, the page says so and offers Check | No cap: one script could use up the day's quota |
| Accessibility: real `<label>`s, an `aria-live` region for the answer, `lang` on Kannada text, 44 px tap targets, contrast ≥ 4.5:1 | Many users read on small, dim screens | — |

## 4. Threats added (threat model)

| ID | Threat | Control | Test |
|---|---|---|---|
| T-W1 | Script in a model reply or a register cell is run in the page | `textContent` only; CSP | an API test that the CSP header is set; a browser check with a reply containing `<img onerror>` |
| T-W2 | The public link uses up the free model quota | the daily cap, the per-minute bucket, and Check as the fallback | a unit test of the cap |
| T-W3 | A user takes the page for official advice | the disclaimer on every answer; "as printed" wording; the official PDF link | a browser check |

## 5. Deployment (after local tests pass)

**The container:**
- `python:3.12-slim`, the locked dependencies, and `register.sqlite` baked in;
- read-only, port from `$PORT`;
- the keys come from the host's secret settings (`load_keys` already prefers environment variables), never the image.

**Host:** a free tier that runs a container, for example Hugging Face Spaces (Docker). You create the account and add the two secrets; I never see the keys.

**Gate before a public link:** check the PPQS website's copyright or reuse policy for the register PDFs and the data derived from them, and record it. Until then, the link is shared privately.

## 6. Testing

- **API tests:** the static mount, the CSP header, and the daily cap (a fake clock), plus 404s for paths outside `web/`.
- **In the browser** (the built-in browser, at phone width 375 px):
  - both tabs;
  - a clarifying question;
  - a 503 fallback to Check;
  - a reply containing markup, shown as text;
  - Kannada labels rendering;
  - no horizontal scroll.
- **Measured, with predictions written first:** page weight (prediction ≤ 50 KB uncompressed), and time to the first answer on this machine (Check p95 ≤ 200 ms; Ask is dominated by the model, about 2–3 s).

## 7. How to explain it in an interview

"The web app is deliberately boring. The safety lives in the engine and the verifier, so the page's job is to show the register's answer without changing it. That means no HTML from the server, ever; the official text next to every parsed number; and a model-free fallback, so the page still answers when the free tier runs out."

## 8. Built and checked (2026-11-18)

**Files:**
- `web/index.html`, `web/app.js`, `web/i18n.js`, `web/style.css`: 16.3 KB in all (prediction ≤ 50 KB, held);
- the API serves them at `/` (`Settings.web_dir`, `--web`).

**API changes:**
- `/v1/lookup` now returns `headline`, the same template `/v1/ask` uses (`LookupOut`);
- a daily cap on `/v1/ask` (`DailyCap`, `--ask-per-day`, default 800);
- the CSP and security headers on everything except `/docs` and `/redoc`;
- proxy headers are trusted only with `--behind-proxy`, because a direct client could forge `X-Forwarded-For`.

**Tests:** `tests/test_web.py`, 7 tests: files and headers; the error envelope next to the page; nothing served outside `web/`; no HTML-insertion calls in the script; the headline; the daily cap per UTC day.

**In the built-in browser at 375 × 812, with no model configured:**

| Check | Result |
|---|---|
| Ask with no model | the "not available" notice, and the page switched to Check |
| Check: "Emamectin benzoate 5% SG", "bende", "shoot and fruit borer" | "Approved … Okra (Bhindi) … (p. 25)", with the row as printed, the page, the official-PDF link and the disclaimer |
| Kannada labels | render; the user switched to Kannada during the test |
| Crop `<img src=x onerror=alert(1)>` | shown as text; 0 image elements created |
| Horizontal scroll | none (scroll width 375 = viewport width) |
| Console | only the expected 503 from Ask with no model; no CSP violations |

**Latency, measured** (this machine, over HTTP on localhost, `--no-model` server, 50 `POST /v1/lookup` across 5 queries, all 200):
- p50 1.3 ms, p95 2.1 ms, max 2.7 ms;
- the page: p50 2.0 ms.

The prediction was Check p95 ≤ 200 ms: held, by a wide margin. A real phone network adds its own delay; this measures the server only.

**Copyright gate checked** (2026-11-18, https://ppqs.gov.in/website-policy, "Copyright policy"):
- PPQS material may be reproduced free of charge **after permission by email**, reproduced accurately, not in a misleading context, and with the source acknowledged;
- linking needs no permission, but pages must open in a new window (the page does this).

So a public link waits on PPQS's reply. **The user sent the permission email on 2026-11-18** (to the Web Information Manager listed on the contact page); there is no reply yet. The policy names no address; the site's only printed contact is the Web Information Manager on https://ppqs.gov.in/contactus.

**Ask with the model, in the browser** (375 px; Groq; 3 questions, all from the test suites):

| Check | Result |
|---|---|
| "godhi ge Isopyrazam 11.5% + Difenoconazole 11.5% SC sari na?", with no language sent (the API default) | the right answer ("Not listed … on godhi"), but **the reply came in Marathi**; and the model's no-break spaces (U+202F) stopped the line wrapping, so it ran past the screen edge |
| The same question, page in Kannada, after the fixes | a Kannada reply, wrapped. The model wrote the product name in Kannada script although told not to; the numbers stayed exact |
| "bende ge white fly bandide, Oxydemeton-methyl 25 EC hodeyabahuda?", page in English | "Approved: Oxydemeton-methyl 25 % EC on Bhindi (Okra) for whitefly … (p. 41)"; an English reply; no overflow; no console errors |

**Fixes from this check:**
- `/v1/ask` takes `lang` ("en" or "kn"), and the page sends the language picker's value. Without `lang`, the reply follows the question, so earlier test runs stay comparable.
- `overflow-wrap: anywhere` on the answer text.
- The page's files are sent with `cache-control: no-cache`. A stale stylesheet hid the CSS fix until the browser revalidated.

**A clarifying question now continues the conversation** (found 2026-11-18). `/v1/ask` is stateless, so the reply "Tomato" used to arrive without the product. The page now joins the reply to the question that drew the clarification, and shows "Your question so far".

Checked in the browser:
- "Mancozeb 75% WP sari na?" drew "which crop?" (in Kannada);
- the reply "aalugadde late blight" was joined to it;
- the answer was "Approved: Mancozeb 75% WP on Potato for late blight … (p. 18)".

Markdown bold marks (`**`) in model text are now dropped on the page.

**Found in that Kannada reply** ("750 L ಜಲದಲ್ಲಿ ಕಲೆಹಾಕಿ", "mix in 750 L of water"): **the advice-wording guard knows only English words**, so an instruction in Kannada passes. This goes to M5, together with the Kannada-script lexicon.

**Not done yet:**
- the container;
- the copyright check;
- (done 2026-11-18) the Kannada labels were reviewed by the user, a Kannada speaker: "Yes Kannada is fine".
