# Kasauti: every brand claim keeps a receipt
Inkloom AI Brand Governance Challenge, Round 2. Python, Streamlit, SQLite.

**Core path:** paste a draft, each claim gets a verdict (Supported, Contradicted, Overclaim, Unsupported, Stale) with the source line quoted, apply a suggested fix, submit, a reviewer approves, receipts link every approved claim to a fact version. Add or edit a fact (tab 3, Admin) and tab 4 lists every approved asset that is now out of date, with a suggested fix.

Run: `pip install -r requirements.txt && streamlit run app.py`. Tests: `pip install pytest && pytest`.
Deploy: push to a public GitHub repo, then Streamlit Community Cloud > New app > `app.py`.
Optional: add `GEMINI_API_KEY` in the app's Secrets. Without it the app runs fully offline.

## How it works
- Claims are split from the draft (Gemini if a key is set, else a rule-based splitter). LLM claims must appear word for word in the draft or are discarded.
- Verdicts come from plain code: price and percent comparison, expiry dates, claim-strength rules, scope of certification. The model never decides.
- SQLite stores versioned facts (`facts`, `fact_hist`), `receipts`, `assets`, `audit`.
- Blast radius = one join between receipts and facts where the fact version moved on or expired.

## Disclosures
Demo brand and data are fictional. Code was written with AI assistance (Claude) and reviewed by the participant. No templates. Round 3 improvements: Hindi/Hinglish translation drift, live-page scan, reviewer feedback loop.
