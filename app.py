import os, re, io, csv, glob, json, time, uuid, tempfile, datetime as dt, streamlit as st, pandas as pd
try: os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception: pass
import engine as E, drift as D, scan as S, docs as Dx, a11y as A
from collections import Counter

st.set_page_config(page_title="Kasauti", page_icon="🪙", layout="wide")

# Every visitor gets a private demo database, kept across refreshes through the page address (?s=...).
if "sid" not in st.session_state:
    sid = str(st.query_params.get("s", ""))
    sid = sid if re.fullmatch(r"[0-9a-f]{10}", sid) else uuid.uuid4().hex[:10]
    st.query_params["s"] = sid; st.session_state.sid = sid
    for f in glob.glob(os.path.join(tempfile.gettempdir(), "kasauti_*.db")):
        try:
            if time.time() - os.path.getmtime(f) > 3 * 86400: os.remove(f)
        except OSError: pass
DBP = os.path.join(tempfile.gettempdir(), f"kasauti_{st.session_state.sid}.db")
def bind(): E.use_db(DBP)
bind(); E.init()

ICON = {"Supported": "✅", "Contradicted": "⛔", "Overclaim": "⚠️", "Unsupported": "❓", "Stale": "⏳", "Terminology": "🔤"}
SAMPLES = {"Wrong price + organic overclaim": "Our Assam blend is now just ₹349 for 250 g. Made with 100% organic tea!",
           "Expired offer + health claim": "Monsoon sale: 20% off all blends. Helps you sleep better.",
           "Delivery claim": "Free delivery on orders above ₹299.",
           "Clean draft": "The 250 g Assam blend is ₹399, made with certified organic leaves.",
           "Brand-name typo": "Try MasalaMornings tea today."}
DEMO = "Demo (all permissions)"
st.session_state.setdefault("draft", ""); st.session_state.setdefault("res", None); st.session_state.setdefault("role", DEMO)

def safe(fn, *a):
    try: return fn(*a)
    except Exception as e:
        st.error(f"Something went wrong ({type(e).__name__}). Press Reset demo data in the sidebar and try again."); return None

with st.sidebar:
    st.header("Kasauti")
    role = st.radio("Acting as", [DEMO, "Creator", "Reviewer", "Admin"], key="role", help="Demo can do every step. Creators check and submit, Reviewers decide, Admins edit facts and rules.")
    st.caption("Demo brand: Masala Mornings (fictional). The AI never approves anything; a person always decides.")
    st.caption("Your demo data is private to your browser session and survives a refresh. Offline mode is on unless a Gemini key is set.")
    st.caption(f"Build: {getattr(E, 'VERSION', 'old')}")
    if st.button("Reset demo data"):
        bind(); E.init(reset=True); st.session_state.pop("res", None); st.session_state.draft = ""; st.rerun()
can_review = role != "Creator"; can_admin = role in ("Admin", DEMO)

def show(results):
    for r in results:
        with st.container(border=True):
            st.markdown(f"**{ICON[r['verdict']]} {r['verdict']}** · “{r['claim']}”")
            st.write(r["why"])
            if r["evidence"]: st.caption(f"Source ({r['rule']}): “{r['evidence']}”")
            if r["fix"]: st.info(f"Suggestion: {r['fix']}" + (f"\n\nRewrite: “{r['fixed']}”" if r["fixed"] else ""))

def load_doc():
    bind(); f = st.session_state.get("upl")
    if f is None: return
    try:
        text = Dx.extract_text(f.name, f.getvalue()).strip()
        if not text: st.session_state.upl_msg = "No text could be read from that file."; return
        st.session_state.draft = text[:5000]; st.session_state.res = E.check(st.session_state.draft)
        st.session_state.upl_msg = f"Loaded {min(len(text), 5000):,} characters from {f.name}" + (" (the rest was cut: drafts are limited to 5,000 characters)." if len(text) > 5000 else ".")
    except Dx.DocError as e: st.session_state.upl_msg = str(e)
    except Exception: st.session_state.upl_msg = "That file could not be read."

def setdraft(t): bind(); st.session_state.draft = t; st.session_state.res = E.check(t)
def fixall(): bind(); st.session_state.draft = E.apply_fixes(st.session_state.draft, st.session_state.res); st.session_state.res = E.check(st.session_state.draft)

st.title("Kasauti: every brand claim keeps a receipt")
if getattr(E, "VERSION", "") != "round3-3": st.error("engine.py in your GitHub repository is out of date. Upload the latest engine.py, then reboot the app.")
with st.container(border=True):
    st.markdown("**Start here (2 minutes).** Kasauti checks marketing text against a brand’s approved facts *before* it is published, then keeps watching it *after*.")
    c = st.columns(4)
    c[0].markdown("**1. Check**\n\nTab 1: tap a sample, or paste your own text, then press *Check draft*.")
    c[1].markdown("**2. Review**\n\nSubmit the draft, open tab 2 and approve it. That saves a receipt for each claim.")
    c[2].markdown("**3. Change a fact**\n\nTab 3: edit a fact, or add facts about your own product.")
    c[3].markdown("**4. See the impact**\n\nTab 4 lists every approved asset the change made wrong, and re-checks it.")
    st.caption(f"You are acting as ‘{role}’. The default role can do every step, so no switching is needed. Also try tab 7 (translation drift) and tab 8 (live page scan).")
if st.session_state.get("flash"): st.success(st.session_state.pop("flash"))

t1, t2, t3, t4, t5, t6, t7, t8, t9, t10 = st.tabs(["1 · Check a draft", "2 · Review queue", "3 · Facts", "4 · Impact of a change", "5 · Insights", "6 · Audit log", "7 · Translation drift", "8 · Live page scan", "9 · Accessibility", "10 · Import / Export"])

with t1:
    st.write("Paste a draft, or try a sample. Each claim gets a verdict, the source line behind it, and a suggested fix.")
    with st.expander("What Kasauti checks today"):
        st.markdown("- Prices (₹, Rs, rupees) and percentage offers, against the approved facts, including expiry dates\n- Certification scope, such as ‘100% organic’ when only the leaves are certified\n- Health claims and absolute words (best, guaranteed, 100%) that have no evidence on file\n- Brand-name spelling\n- Any fact you add in tab 3, for example a delivery policy or the price of another product\n\nSentences with no numbers, prices, offers or claim words are skipped. English only for now.")
    cols = st.columns(len(SAMPLES))
    for col, (n, t) in zip(cols, SAMPLES.items()): col.button(n, on_click=setdraft, args=(t,), use_container_width=True)
    st.file_uploader("Or upload a document to check (.txt, .md, .docx, .pdf)", type=["txt", "md", "docx", "pdf"], key="upl", on_change=load_doc)
    if st.session_state.get("upl_msg"): st.caption(st.session_state.upl_msg)
    st.text_area("Draft (type or paste your own text here)", key="draft", height=130, max_chars=5000)
    if st.button("Check draft", type="primary"):
        if not st.session_state.draft.strip(): st.warning("Paste or type some text first."); st.session_state.res = None
        else: st.session_state.res = safe(E.check, st.session_state.draft)
    res = st.session_state.res
    if res is not None:
        if not res: st.success("No checkable claims found in this text.")
        if res and all(r["verdict"] == "Unsupported" for r in res):
            st.warning("Nothing on file covers this text. That is the right result for a product Kasauti has no facts about. Add its facts in tab 3 (Add a new fact), then check again.")
        show(res)
        if res: st.download_button("Download these findings (CSV)", pd.DataFrame(res)[["verdict", "claim", "why", "evidence", "fix", "rule"]].to_csv(index=False).encode("utf-8-sig"), "kasauti_findings.csv", "text/csv")
        if any(r["fixed"] for r in res): st.button("Apply suggested fixes", on_click=fixall)
        blocked = any(r["verdict"] == "Contradicted" and E.rule_mode(r["rule"]) == "blocking" for r in res)
        if blocked: st.error("A contradicted claim blocks submission. Apply the suggested fix or edit the text first.")
        title = st.text_input("Title for the review queue", "Untitled draft")
        if st.button("Submit for review", disabled=blocked or not st.session_state.draft.strip()):
            n0 = len(E.q("select id from assets where status='pending'")); E.submit(title.strip() or "Untitled draft", st.session_state.draft, res, role)
            if len(E.q("select id from assets where status='pending'")) == n0: st.info("This draft is already waiting in the review queue.")
            else: st.success("Submitted. Next: open tab 2 · Review queue and approve it.")

with t2:
    if not can_review: st.info("Creators cannot review. Switch to Demo or Reviewer in the sidebar.")
    else:
        pend = E.q("select * from assets where status='pending' order by id")
        if not pend: st.success("Nothing is waiting for review. Submit a draft in tab 1 first.")
        for a in pend:
            f = json.loads(a["findings"]); need = any(r["verdict"] != "Supported" for r in f)
            with st.expander(f"#{a['id']} · {a['title']}", expanded=True):
                st.write(a["text"]); show(f)
                note = st.text_input("Reviewer comment" + (" (required: unresolved findings)" if need else ""), key=f"n{a['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Approve", key=f"a{a['id']}", type="primary"):
                    if need and not note.strip(): st.error("Add a comment to approve with unresolved findings.")
                    else:
                        st.session_state.flash = "Approved, and receipts saved. Next: open tab 3, change a fact, then see tab 4." if E.approve(a["id"], role, note.strip()) else "That draft was already decided."; st.rerun()
                if c2.button("Reject", key=f"r{a['id']}"):
                    E.reject(a["id"], role, note.strip()); st.session_state.flash = "Rejected."; st.rerun()

with t3:
    st.dataframe(pd.DataFrame(E.q("select label Fact, num Value, statement Statement, source Source, version Version, expires Expires from facts")), use_container_width=True, hide_index=True)
    if not can_admin: st.info("Switch to Demo or Admin in the sidebar to add or edit facts.")
    else:
        with st.expander("Edit an existing fact (saves a new version)"):
            facts = E.q("select * from facts"); pick = st.selectbox("Fact to edit", facts, format_func=lambda f: f["label"])
            k = f"{pick['id']}v{pick['version']}"
            stmt = st.text_area("Approved statement", value=pick["statement"], key=f"st{k}")
            val = st.number_input("Value (price or percent)", value=float(pick["num"]), key=f"v{k}") if pick["num"] is not None else None
            if st.button("Save new version"):
                if not stmt.strip(): st.error("The statement cannot be empty.")
                else:
                    changed = stmt.strip() != pick["statement"]
                    n = E.update_fact(pick["id"], val, stmt.strip() if changed else None, role)
                    st.success(f"Saved. {n} approved asset(s) now need review. Open tab 4." if n else "Saved. No approved asset relied on this fact.")
        with st.expander("Add a new fact (to check your own product)", expanded=True):
            with st.form("addfact", clear_on_submit=True):
                lab = st.text_input("Fact name", placeholder="Zip hoodie price")
                kind = st.selectbox("Type", ["Price", "Offer (percent)", "Certification or other rule"])
                nv = st.number_input("Value (price or percent; leave 0 for other rules)", min_value=0.0, value=0.0)
                stm = st.text_area("Approved statement (the source line)", placeholder="Our zip hoodie costs ₹1,499.")
                src = st.text_input("Source document", placeholder="Price list")
                exp = st.date_input("Valid until", value=dt.date(2027, 3, 31))
                kw = st.text_input("Words a claim would use, comma separated", placeholder="hoodie, zip")
                if st.form_submit_button("Add fact"):
                    err = E.add_fact(lab, {"Price": "price", "Offer (percent)": "offer"}.get(kind, "scope"), nv, stm, src, exp.isoformat(), kw, role)
                    if err: st.error(err)
                    else: st.success("Fact added. Go to tab 1 and check a draft about it.")
        with st.expander("Glossary: wrong spellings and approved terms"):
            gl = E.terms()
            if gl: st.dataframe(pd.DataFrame(gl)[["wrong", "good"]].rename(columns={"wrong": "Wrong or banned form", "good": "Approved form"}), hide_index=True, use_container_width=True)
            with st.form("addterm", clear_on_submit=True):
                w = st.text_input("Wrong or banned form", placeholder="Masla Mornings"); g = st.text_input("Approved form", placeholder="Masala Mornings")
                if st.form_submit_button("Add to glossary"):
                    err = E.add_term(w, g, role)
                    if err: st.error(err)
                    else: st.success("Added. Drafts are now checked for it.")
            if gl:
                rm = st.selectbox("Remove an entry", gl, format_func=lambda t: f"{t['wrong']} → {t['good']}")
                if st.button("Remove entry"): E.del_term(rm["id"], role); st.rerun()

with t4:
    b = E.blast()
    if not b: st.success("Every approved asset matches the current facts. Edit a fact in tab 3 to see this tab fill up.")
    for x in b:
        with st.container(border=True):
            st.markdown(f"**⏳ {x['title']}** needs re-review"); st.write(" ".join(x["why"]))
            c1, c2 = st.columns(2); c1.caption("Current text"); c1.write(x["text"]); c2.caption("Suggested text"); c2.write(x["new"])
            if x["new"] == x["text"]: st.caption("No wording change is suggested. Re-checking tests the text against the new fact; if it no longer fits, it goes back to the review queue.")
            if can_review and st.button("Apply fix and re-check" if x["new"] != x["text"] else "Re-check against the new fact", key=f"b{x['aid']}"):
                out = E.recheck(x["aid"], role)
                st.session_state.flash = "Re-checked and approved with new receipts." if out == "approved" else "It no longer fits the facts, so it is back in tab 2 for a reviewer." if out == "needs_review" else "Nothing to do."; st.rerun()

with t5:
    st.subheader("Reviewer feedback loop")
    st.caption("Each time a reviewer approves despite a finding (an override) or rejects because of it (upheld), the rule is scored. Rules that reviewers override often are flagged as possibly unclear. The table includes sample history from the demo brand so it is never empty.")
    rs = E.rule_stats()
    st.dataframe(pd.DataFrame([{"Rule": s["rule"], "Reviewed": s["reviewed"], "Overridden": s["overridden"], "Override rate": f"{s['rate']}%", "Status": "⚠️ possibly unclear" if s["unclear"] else "ok", "Mode": s["mode"]} for s in rs]), use_container_width=True, hide_index=True)
    for s in rs:
        if s["unclear"]: st.warning(f"**{s['rule']}**: reviewers override this {s['rate']}% of the time" + (f". Reasons given: {'; '.join(s['reasons'])}." if s["reasons"] else ".") + " Consider rewording the guideline, or make the rule advisory.")
    if can_admin:
        c1, c2, c3 = st.columns([2, 2, 1]); pr = c1.selectbox("Rule", E.RULES); pm = c2.radio("Mode", ["blocking", "advisory"], horizontal=True, index=0 if E.rule_mode(pr) == "blocking" else 1, key=f"m{pr}")
        if c3.button("Save mode"): E.set_rule_mode(pr, pm, role); st.success(f"{pr} is now {pm}: " + ("a contradicted claim blocks submission." if pm == "blocking" else "it warns but does not block.")); st.rerun()
    else: st.caption("Switch to Demo or Admin to change a rule between blocking and advisory.")
    v, rules, ov = E.stats()
    if v: st.subheader("Verdicts so far"); st.bar_chart(pd.DataFrame(v).set_index("verdict"))

with t6:
    st.dataframe(pd.DataFrame(E.q("select * from audit order by rowid desc")), use_container_width=True, hide_index=True)
    st.subheader("Asset history")
    al = E.q("select id, title, status from assets order by id desc")
    if al:
        pk = st.selectbox("Asset", al, format_func=lambda x: f"#{x['id']} · {x['title']} ({x['status']})")
        prev = None
        for h in E.history(pk["id"]):
            with st.container(border=True):
                st.markdown(f"**Version {h['rev']}** · {h['ts']} · {h['actor']} · {h['reason']}"); st.write(h["text"])
                if prev is not None and E.changes(prev, h["text"]): st.caption("Changed: " + "; ".join(E.changes(prev, h["text"])))
            prev = h["text"]

PAIRS = {"Guarantee added": ("Can help reduce hair fall.", "Yeh tel hair fall pakka rokta hai."),
         "Figures changed": ("Up to 20% off on all blends.", "Sabhi blends par 30% off."),
         "Hindi: ‘best’ added": ("A good choice for tea lovers.", "चाय प्रेमियों के लिए सबसे अच्छी पसंद।"),
         "Consistent pair": ("Our Assam blend is made with certified organic leaves.", "Hamari Assam chai certified organic patton se bani hai.")}
def setpair(e, t): st.session_state.en = e; st.session_state.tr = t; st.session_state.dres = D.check_drift(e, t)
st.session_state.setdefault("en", ""); st.session_state.setdefault("tr", "")

with t7:
    st.write("Paste an approved English line and its Hindi or Hinglish translation. Kasauti flags a translation that claims more than the English does: a stronger word, different figures, or a dropped hedge such as ‘can help’.")
    cols = st.columns(len(PAIRS))
    for col, (n, (e, t)) in zip(cols, PAIRS.items()): col.button(n, on_click=setpair, args=(e, t), use_container_width=True, key=f"pair{n}")
    st.text_area("Approved English line", key="en", height=80, max_chars=1000)
    st.text_area("Translation (Hindi in Devanagari, or Hinglish in English letters)", key="tr", height=80, max_chars=1000)
    if st.button("Check translation", type="primary"): st.session_state.dres = D.check_drift(st.session_state.en, st.session_state.tr)
    d = st.session_state.get("dres")
    if d:
        if d["verdict"] == "Empty": st.warning("Fill in both boxes first.")
        elif d["verdict"] == "Consistent": st.success("✅ Consistent: the translation does not claim more than the English line.")
        else:
            st.error(f"⚠️ Drift: the translation says more than the approved English line ({len(d['issues'])} issue(s)).")
            for i in d["issues"]:
                with st.container(border=True):
                    st.markdown(f"**{i['kind']}**" + (f" · ‘{i['term']}’" if i["term"] else "")); st.write(i["why"]); st.info(i["fix"])
            if d["fixed"]: st.caption("Suggested softer translation (check the grammar before using it):"); st.code(d["fixed"], language=None)
    st.caption("How it works: a word list of strong claims in English, Hinglish and Devanagari (guarantee, best, 100%, always, only, cure, pure), plus a figures check and a hedge check. It covers common phrases, not every way of saying them, so it supports a human translator rather than replacing one.")

with t8:
    st.write("Scan what a page says right now. Kasauti reads the page text, finds the claims and runs the same checks against your approved facts. It reads ordinary public web pages. It cannot read pages that need a sign-in or draw their content with JavaScript (Streamlit apps are one example), and it skips pages that ask automated tools to stay away.")
    st.text_input("Public web page address", key="scanurl", placeholder="https://example.com/product")
    def run_scan(kind, fn, *a):
        bind()
        with st.spinner("Reading the page..."):
            try: st.session_state.scan = (kind, fn(*a))
            except S.ScanError as e: st.session_state.scan = None; st.error(str(e))
            except Exception as e: st.session_state.scan = None; st.error(f"The scan failed ({type(e).__name__}: {e}). Try the sample page, or paste the page text below.")
    c1, c2 = st.columns(2)
    if c1.button("Scan this page", type="primary"): run_scan("page", S.scan_url, st.session_state.scanurl)
    if c2.button("Scan the sample page (works offline)"): run_scan("sample", S.scan_html, S.SAMPLE_HTML)
    st.text_area("Or paste the page text (or its HTML) here. Useful when a site blocks automated readers.", key="scanpaste", height=100, max_chars=20000)
    if st.button("Scan pasted text"):
        if not st.session_state.scanpaste.strip(): st.warning("Paste some text first.")
        else: run_scan("pasted", S.scan_html, st.session_state.scanpaste)
    sc = st.session_state.get("scan")
    if sc:
        kind, out = sc; res = out["results"]
        st.caption({"sample": "Showing the built-in sample page (fictional).", "pasted": "Scanned the text you pasted."}.get(kind, f"Scanned {out['chars']:,} characters of page text."))
        if kind == "page" and out["chars"] < 150: st.info("Kasauti could read very little text from this page. It may draw its content with JavaScript, which a simple reader cannot see. Paste the page text instead.")
        if out.get("a11y") and out["a11y"]["issues"]:
            with st.expander(f"Accessibility notes for this page ({len(out['a11y']['issues'])})", expanded=True):
                for i in out["a11y"]["issues"]: st.markdown(f"- {i}")
        if not res: st.info("No checkable claims were found.")
        else:
            cnt = Counter(r["verdict"] for r in res); m = st.columns(len(cnt))
            for col, (v, n) in zip(m, cnt.most_common()): col.metric(f"{ICON[v]} {v}", n)
            show(res)
            for r in res:
                if r.get("approved_as"): st.caption(f"“{r['claim']}” was approved before as ‘{r['approved_as']}’.")

with t9:
    st.write("Basic accessibility checks: how easy text is to read, whether two colours have enough contrast, and whether a page's HTML has the basics. The live page scan in tab 8 also reports these for scanned pages.")
    st.subheader("Readability")
    rt = st.text_area("English text to check", key="rtext", height=100, max_chars=5000)
    if st.button("Check readability"):
        r = A.readability(rt)
        if not r: st.warning("Type some English text first.")
        else:
            st.metric("Reading ease (higher is easier)", f"{r['score']}/100 · {r['level']}"); st.caption(f"{r['words']} words in {r['sentences']} sentence(s).")
            for i in r["issues"]: st.warning(i)
            if not r["issues"]: st.success("No long sentences, shouting or repeated punctuation found.")
    st.subheader("Colour contrast")
    cc1, cc2 = st.columns(2); fg = cc1.color_picker("Text colour", "#1F2A44"); bg = cc2.color_picker("Background colour", "#FAF6EC")
    k = A.contrast(fg, bg); st.metric("Contrast ratio", f"{k['ratio']} : 1")
    st.write(("✅" if k["aa_normal"] else "❌") + " WCAG AA for normal text (needs 4.5)  \n" + ("✅" if k["aa_large"] else "❌") + " AA for large text (needs 3)  \n" + ("✅" if k["aaa_normal"] else "❌") + " AAA for normal text (needs 7)")
    st.subheader("Page HTML basics")
    hv = st.text_area("Paste a page's HTML", key="htmltxt", height=100, max_chars=20000)
    if st.button("Check HTML"):
        if not hv.strip(): st.warning("Paste some HTML first.")
        else:
            hr = A.html_issues(hv)
            for i in hr["issues"]: st.warning(i)
            if not hr["issues"]: st.success(f"No basic issues found ({hr['images']} image(s) checked).")

with t10:
    st.write("Take your brand's data with you. Free hosting does not keep data after a restart, so save a brand pack and load it back next time.")
    st.subheader("Export")
    e1, e2, e3 = st.columns(3)
    e1.download_button("Facts (CSV)", pd.DataFrame(E.facts_rows()).to_csv(index=False).encode("utf-8-sig"), "kasauti_facts.csv", "text/csv")
    e2.download_button("Claim receipts (CSV)", pd.DataFrame(E.receipts_rows(), columns=["asset", "claim", "fact", "version_used", "current_version", "status"]).to_csv(index=False).encode("utf-8-sig"), "kasauti_receipts.csv", "text/csv")
    e3.download_button("Brand pack (JSON)", E.pack_json().encode("utf-8"), "kasauti_brand_pack.json", "application/json")
    st.caption("The receipts file answers ‘prove it’: each approved claim, the fact behind it and the version used. The brand pack holds facts, glossary and rule modes.")
    st.subheader("Import")
    if not can_admin: st.info("Switch to Demo or Admin in the sidebar to import data.")
    else:
        pf = st.file_uploader("Brand pack (.json)", type=["json"], key="packfile")
        if pf and st.button("Import brand pack"):
            ad, sk, er = E.load_pack(pf.getvalue().decode("utf-8", "replace"), role)
            st.success(f"Added {ad} fact(s); {sk} already existed.") if not er else st.warning(f"Added {ad}, skipped {sk}.")
            for x in er[:10]: st.error(x)
        TEMPLATE = 'fact,type,value,statement,source,expires,keywords\nZip hoodie price,price,1499,Our zip hoodie costs ₹1499.,Price list,2027-03-31,"hoodie, zip"\nReturns policy,rule,,Returns are accepted within 7 days of delivery.,Policy,2027-03-31,"returns, refund"\n'
        st.download_button("Download the facts spreadsheet template (CSV)", TEMPLATE.encode("utf-8-sig"), "kasauti_facts_template.csv", "text/csv")
        cf = st.file_uploader("Facts spreadsheet (.csv)", type=["csv"], key="csvfile")
        if cf and st.button("Import facts"):
            try: rows = list(csv.DictReader(io.StringIO(cf.getvalue().decode("utf-8-sig", "replace"))))
            except Exception: rows = []; st.error("That file could not be read as a CSV.")
            if rows:
                ad, sk, er = E.import_facts(rows, role); st.success(f"Added {ad} fact(s); {sk} already existed.")
                for x in er[:10]: st.error(x)
