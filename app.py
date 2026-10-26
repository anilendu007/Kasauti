import os, json, datetime as dt, streamlit as st, pandas as pd
try: os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception: pass
import engine as E

st.set_page_config(page_title="Kasauti", page_icon="🪙", layout="wide")
E.init()
ICON = {"Supported": "✅", "Contradicted": "⛔", "Overclaim": "⚠️", "Unsupported": "❓", "Stale": "⏳", "Terminology": "🔤"}
SAMPLES = {"Wrong price + organic overclaim": "Our Assam blend is now just ₹349 for 250 g. Made with 100% organic tea!",
           "Expired offer + health claim": "Monsoon sale: 20% off all blends. Helps you sleep better.",
           "Clean draft": "The 250 g Assam blend is ₹399, made with certified organic leaves.",
           "Brand-name typo": "Try MasalaMornings tea today."}
st.session_state.setdefault("draft", ""); st.session_state.setdefault("res", None)

with st.sidebar:
    st.header("Kasauti")
    role = st.radio("Acting as", ["Creator", "Reviewer", "Admin"], help="Creators check and submit. Reviewers decide. Admins also edit facts.")
    st.caption("Demo brand: Masala Mornings (fictional). The AI never approves anything; a person always decides.")
    st.caption("Offline mode is on unless a Gemini key is set. Verdicts come from code, not the model.")
    if st.button("Reset demo data"):
        E.init(reset=True); st.session_state.clear(); st.rerun()

def show(results):
    for r in results:
        with st.container(border=True):
            st.markdown(f"**{ICON[r['verdict']]} {r['verdict']}** · “{r['claim']}”")
            st.write(r["why"])
            if r["evidence"]: st.caption(f"Source ({r['rule']}): “{r['evidence']}”")
            if r["fix"]: st.info(f"Suggestion: {r['fix']}" + (f"\n\nRewrite: “{r['fixed']}”" if r["fixed"] else ""))

def setdraft(t): st.session_state.draft = t; st.session_state.res = E.check(t)
def fixall(): st.session_state.draft = E.apply_fixes(st.session_state.draft, st.session_state.res); st.session_state.res = E.check(st.session_state.draft)

st.title("Kasauti: every brand claim keeps a receipt")
t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Check a draft", "2 · Review queue", "3 · Facts", "4 · Impact of a change", "5 · Insights", "6 · Audit log"])

with t1:
    st.write("Paste a draft, or try a sample. Each claim gets a verdict, the source line behind it, and a suggested fix.")
    cols = st.columns(len(SAMPLES))
    for c, (n, t) in zip(cols, SAMPLES.items()): c.button(n, on_click=setdraft, args=(t,), use_container_width=True)
    st.text_area("Draft", key="draft", height=130)
    if st.button("Check draft", type="primary"): st.session_state.res = E.check(st.session_state.draft)
    res = st.session_state.res
    if res is not None:
        if not res: st.success("No checkable claims found.")
        show(res)
        if any(r["fixed"] for r in res): st.button("Apply suggested fixes", on_click=fixall)
        blocked = any(r["verdict"] == "Contradicted" for r in res)
        if blocked: st.error("A contradicted claim blocks submission. Fix it first.")
        title = st.text_input("Title for the review queue", "Untitled draft")
        if st.button("Submit for review", disabled=blocked or not st.session_state.draft.strip()):
            E.submit(title, st.session_state.draft, res, role); st.success("Submitted. Switch to Reviewer to decide.")

with t2:
    if role == "Creator": st.info("Switch to Reviewer in the sidebar to review submissions.")
    else:
        pend = E.q("select * from assets where status='pending' order by id")
        if not pend: st.success("Nothing is waiting for review.")
        for a in pend:
            f = json.loads(a["findings"]); need = any(r["verdict"] != "Supported" for r in f)
            with st.expander(f"#{a['id']} · {a['title']}", expanded=True):
                st.write(a["text"]); show(f)
                note = st.text_input("Reviewer comment" + (" (required: unresolved findings)" if need else ""), key=f"n{a['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Approve", key=f"a{a['id']}", type="primary"):
                    if need and not note: st.error("Add a comment to approve with unresolved findings.")
                    else: E.approve(a["id"], role, note); st.rerun()
                if c2.button("Reject", key=f"r{a['id']}"): E.reject(a["id"], role, note); st.rerun()

with t3:
    st.dataframe(pd.DataFrame(E.q("select label Fact, num Value, statement Statement, source Source, version Version, expires Expires from facts")), use_container_width=True, hide_index=True)
    if role != "Admin": st.info("Switch to Admin to add or edit facts. Each edit saves a new version.")
    else:
        facts = E.q("select * from facts"); pick = st.selectbox("Fact to edit", facts, format_func=lambda f: f["label"])
        val = st.number_input("New value (price or percent)", value=float(pick["num"] or 0), key=f"v{pick['id']}")
        if st.button("Save new version") and pick["num"] is not None:
            n = E.update_fact(pick["id"], val, None, role); st.success(f"Saved. {n} approved asset(s) now need review. Open tab 4.")
        with st.expander("Add a new fact"):
            with st.form("addfact", clear_on_submit=True):
                lab = st.text_input("Fact name", placeholder="Darjeeling 100 g price")
                kind = st.selectbox("Type", ["Price", "Offer (percent)", "Certification or other rule"])
                nv = st.number_input("Value (price or percent; leave 0 for other rules)", min_value=0.0, value=0.0)
                stmt = st.text_area("Approved statement (the source line)", placeholder="The 100 g Darjeeling blend costs ₹250.")
                src = st.text_input("Source document", placeholder="Price list v3")
                exp = st.date_input("Valid until", value=dt.date(2027, 3, 31))
                kw = st.text_input("Words a claim would use, comma separated", placeholder="darjeeling, 100g")
                if st.form_submit_button("Add fact"):
                    err = E.add_fact(lab, {"Price": "price", "Offer (percent)": "offer"}.get(kind, "scope"), nv, stmt, src, exp.isoformat(), kw, role)
                    if err: st.error(err)
                    else: st.success("Fact added. New drafts are now checked against it.")

with t4:
    b = E.blast()
    if not b: st.success("Every approved asset matches the current facts.")
    for x in b:
        with st.container(border=True):
            st.markdown(f"**⏳ {x['title']}** needs re-review"); st.write(" ".join(x["why"]))
            c1, c2 = st.columns(2); c1.caption("Current text"); c1.write(x["text"]); c2.caption("Suggested text"); c2.write(x["new"])
            if x["new"] == x["text"]: st.warning("No automatic fix: edit this asset by hand.")
            elif role != "Creator" and st.button("Apply fix and re-approve", key=f"b{x['aid']}"): E.reapprove(x["aid"], role); st.rerun()

with t5:
    v, rules, ov = E.stats()
    if v: st.subheader("Verdicts so far"); st.bar_chart(pd.DataFrame(v).set_index("verdict"))
    if rules: st.subheader("Rules that get flagged most"); st.dataframe(pd.DataFrame(rules), hide_index=True)
    st.subheader("Rules reviewers override"); st.caption("A rule that creators trip and reviewers keep overriding may be unclear.")
    st.dataframe(pd.DataFrame(ov), hide_index=True) if ov else st.write("No overrides yet.")

with t6:
    st.dataframe(pd.DataFrame(E.q("select * from audit order by rowid desc")), use_container_width=True, hide_index=True)
