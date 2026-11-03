# Kasauti: every brand claim keeps a receipt

A brand-governance prototype for the Inkloom AI challenge. It checks marketing content against a brand's approved facts **before** publishing, explains every finding with the source line behind it, lets a human decide, and keeps watching **after** publishing: when a fact changes or expires, it lists every approved asset that is now out of date and re-checks it.

**Live app:** https://kasauti-chihrrcxd3zeqsxz8t7g2e.streamlit.app/?s=af666affa5#kasauti-every-brand-claim-keeps-a-receipt  ·  **Repository:** https://github.com/anilendu007/Kasauti

## Try it in two minutes (no login needed)

The demo account is already active. There is no sign-in and no password: the default role, *Demo (all permissions)*, can do every step. The demo brand, Masala Mornings, is fictional. Every visitor gets a private copy of the data, so nobody spoils anyone else's demo. Press **Reset demo data** in the sidebar to start fresh.

1. **Tab 1:** tap *Wrong price + organic overclaim*, press *Apply suggested fixes*, then *Submit for review*. You can also paste your own text or upload a `.txt`, `.md`, `.docx` or `.pdf`.
2. **Tab 2:** approve it. Each supported claim now has a receipt linking it to the fact and fact version behind it.
3. **Tab 3:** edit the 250 g Assam price, or add facts about your own product. **Tab 4:** see which approved assets the change made wrong, then re-check them.
4. **The three Round 3 improvements:** tab 5 (reviewer feedback loop), tab 7 (translation drift, tap a sample pair), tab 8 (live page scan, press the sample page button).
5. **Also:** tab 9 (accessibility checks), tab 10 (import and export), tab 6 (audit log and revision history).

## What it does

| Feature | Status | Notes |
|---|---|---|
| Source-of-truth facts with versions and expiry dates | Done | Add, edit, import from CSV, export; every edit saves a new version |
| Claim checker: Supported, Contradicted, Overclaim, Unsupported, Stale, plus Terminology | Done | Rule-based; limits listed below |
| Explanations, quoted source line, suggested rewrites | Done | Rewrites are only applied when the user clicks |
| Review workflow: roles, comments, approve or reject, audit log | Done | Roles are a demo switch, not a login |
| Receipts and blast radius, with re-check | Done | An edited fact sends affected assets back to the review queue if they no longer fit |
| Revision history | Done | Every version of an asset with the words that changed (tab 6) |
| Glossary editing | Done | Wrong or banned forms and their approved forms (tab 3) |
| Governance insights | Done | Verdict counts, flagged rules, override rates |
| **Improvement 1:** reviewer feedback loop | Done | Override rate per rule, "possibly unclear" flag, blocking or advisory mode |
| **Improvement 2:** Hindi and Hinglish translation drift | Done | Word-list based; see accuracy below |
| **Improvement 3:** live page scan | Done | Static public pages; a paste option covers blocked pages |
| Accessibility checks | Partial | Readability, colour contrast, page HTML basics. No image analysis |
| Document import | Done | `.txt`, `.md`, `.docx`; `.pdf` is best effort (text PDFs, needs `pypdf`) |
| Import and export | Done | Facts CSV, claim receipts CSV, findings CSV, brand pack JSON |
| Visual brand checks on images (logo, palette) | Not built | On the roadmap |
| Real accounts and a permanent database | Not built | Brand packs let you save and restore data instead |

## How it works

1. A draft is split into claims (Gemini if a key is set, otherwise a rule-based splitter; a model-supplied claim must appear word for word in the draft or it is discarded).
2. Each claim is matched to approved facts by shared keywords, with extra weight when the number matches.
3. **Plain code decides the verdict:** prices and percentages are compared (₹, Rs, rupees), expiry dates are checked, absolute words such as "100%" or "guaranteed" are tested against what the fact actually covers, and figures are compared against the approved line. The model never decides.
4. When unsure, the checker fails closed: a claim that names an approved price without a figure it can verify is marked Unsupported, not Supported.
5. A person reviews and decides. Approval stores a receipt (claim, fact id, fact version). A fact edit or expiry is found by one join between receipts and facts.

```
Draft / document / page ──► claim splitter ──► fact matcher ──► verdict engine (code) ──► review queue ──► receipts
                                                      ▲                                       │               │
                                                      └───────────── SQLite: facts, history, assets, audit ◄──┘
                                                                  fact edited ──► blast radius ──► re-check
```

**Data (SQLite):** `facts`, `fact_hist` (every version), `assets`, `revisions`, `receipts`, `audit`, `terms` (glossary), `rules` (blocking or advisory), `decisions` (feedback loop), `checks`. Each visitor's database is a separate temporary file, kept across a refresh through the page address.

| File | Role |
|---|---|
| `app.py` | Streamlit interface (ten tabs) |
| `engine.py` | Facts, claim checker, receipts, blast radius, feedback loop, import and export |
| `drift.py` | Translation drift check |
| `scan.py` | Live page fetch and scan |
| `docs.py` | Reads uploaded documents |
| `a11y.py` | Readability, contrast and HTML checks |
| `test_engine.py`, `run_tests.py` | Automated tests and the test-log script |
| `run_eval.py`, `eval/` | Labelled examples and the accuracy measurement |

**Stack:** Python, Streamlit, SQLite and the standard library. Streamlit gives a clickable product quickly; SQLite needs no setup; the engine is separate from the interface so the interface can be replaced. Gemini is optional. `pypdf` is used only for PDF upload.

## Testing and measured results

- **Automated tests:** 24 tests, each run in two orders (48 runs), all passing. Run `python run_tests.py` to regenerate `TEST_LOG.md`.
- **Claim checker accuracy** (`python run_eval.py`, labels in `eval/claims_eval.csv`, written before running): 33 labelled drafts, every verdict correct on 31 (94%). Of 27 planted problems, 25 were flagged correctly (93%). False alarms: 1. False assurances (a bad claim marked Supported): 0.
- **Translation drift accuracy** (`eval/drift_eval.csv`): 22 labelled pairs. Drift caught in 9 of 11 cases (82%); false alarms: 1.
- **What the evaluation found and we fixed:** "Rs." was split as a sentence end, and "fully organic packaging" was wrongly marked Supported.
- **Misses we know about:** Devanagari claims are not understood by the claim checker; a claim with no number and no claim words ("Free delivery on all orders") is skipped; the drift word list misses some phrases ("sau pratishat", "lajawab") and treats "Three" versus "3" as different figures. All are listed in `EVAL_RESULTS.md`.
- **Reliability checks built in:** private database per visitor, empty and oversized input handled, repeated clicks do nothing twice, duplicate facts rejected, page scans limited to public addresses with a timeout and size cap, friendly messages for every failure.
- **Not done yet:** structured testing with outside users.

## Privacy, security and responsible design

- No accounts and no personal data are collected. Demo data is fictional.
- Offline mode is the default. If a Gemini key is set, only the draft text is sent to the model. Keys belong in Streamlit secrets, never in the repository.
- The AI never approves anything. Low confidence goes to a human, and every override is logged with its reason.
- The page scanner reads public `http` and `https` pages only, refuses private and internal addresses (including after redirects), respects `robots.txt`, and caps time and size.
- Findings always show their source line, so a reviewer can check them.
- The interface uses text labels beside icons and colours. It has not had a formal accessibility audit.

## Limits

Claim detection covers prices, percentage offers, certification scope, health words, absolute words, added facts and brand-name spelling. Sentences with none of these are skipped. English only for claims; translation drift is a word list, not a translation model. The scan cannot read pages that need a sign-in or draw their content with JavaScript (Streamlit apps included). Free hosting does not keep data across restarts, so export a brand pack.

## Changes from the original plan

- The live scan uses Python's standard library instead of requests and BeautifulSoup.
- Each visitor gets a private database, and the default demo role has every permission, so judges need no login.
- Translation drift uses a claim-strength word list with figure and hedge checks.
- Visual checks on images and real authentication were not built. Accessibility is limited to readability, contrast and HTML basics.
- Added after Round 2: revision history, glossary editing, import and export, document upload, and the accessibility tab.

## Roadmap

1. Brand checks on images (logo use, palette) with a vision model.
2. Real accounts, roles and a hosted database.
3. More languages and a better translation-drift model.
4. Plug-ins for Google Docs, Notion and Canva, and a browser extension.
5. Scheduled monitoring of live pages with alerts.
6. Rule packs for food, health and finance, starting with ASCI and CCPA claim requirements.

## Run it yourself

Needs Python 3.10 or newer.

```
git clone https://github.com/anilendu007/Kasauti.git
cd Kasauti
pip install -r requirements.txt
python -m streamlit run app.py
```

Tests: `python run_tests.py`. Evaluation: `python run_eval.py`. Deploy: push to GitHub, then create an app on Streamlit Community Cloud with `app.py` as the main file.

## Disclosures

Partial code were written with AI assistance (Claude). No templates were used, and no code from earlier projects was reused. The demo brand and all sample data are fictional. Libraries: Streamlit, pandas, pypdf (optional) and requests (optional, for Gemini).
