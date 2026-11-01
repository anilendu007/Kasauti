import os, re, glob, json, time, uuid, tempfile, datetime as dt, streamlit as st, pandas as pd
try: os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception: pass
import engine as E

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

def setdraft(t): bind(); st.session_state.draft = t; st.session_state.res = E.check(t)
def fixall(): bind(); st.session_state.draft = E.apply_fixes(st.session_state.draft, st.session_state.res); st.session_state.res = E.check(st.session_state.draft)

st.title("Kasauti: every brand claim keeps a receipt")
with st.container(border=True):
    st.markdown("**Start here (2 minutes).** Kasauti checks marketing text against a brand’s approved facts *before* it is published, then keeps watching it *after*.")
    c = st.columns(4)
    c[0].markdown("**1. Check**\n\nTab 1: tap a sample, or paste your own text, then press *Check draft*.")
    c[1].markdown("**2. Review**\n\nSubmit the draft, open tab 2 and approve it. That saves a receipt for each claim.")
    c[2].markdown("**3. Change a fact**\n\nTab 3: edit a fact, or add facts about your own product.")
    c[3].markdown("**4. See the impact**\n\nTab 4 lists every approved asset the change made wrong, and re-checks it.")
    st.caption(f"You are acting as ‘{role}’. The default role can do every step, so no switching is needed.")
if st.session_state.get("flash"): st.success(st.session_state.pop("flash"))

t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Check a draft", "2 · Review queue", "3 · Facts", "4 · Impact of a change", "5 · Insights", "6 · Audit log"])

with t1:
    st.write("Paste a draft, or try a sample. Each claim gets a verdict, the source line behind it, and a suggested fix.")
    with st.expander("What Kasauti checks today"):
        st.markdown("- Prices (₹, Rs, rupees) and percentage offers, against the approved facts, including expiry dates\n- Certification scope, such as ‘100% organic’ when only the leaves are certified\n- Health claims and absolute words (best, guaranteed, 100%) that have no evidence on file\n- Brand-name spelling\n- Any fact you add in tab 3, for example a delivery policy or the price of another product\n\nSentences with no numbers, prices, offers or claim words are skipped. English only for now.")
    cols = st.columns(len(SAMPLES))
    for col, (n, t) in zip(cols, SAMPLES.items()): col.button(n, on_click=setdraft, args=(t,), use_container_width=True)
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
