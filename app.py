import os, json, datetime as dt, streamlit as st, pandas as pd
try: os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception: pass
import engine as E

st.set_page_config(page_title="Kasauti", page_icon="🪙", layout="wide")
E.init()
ICON = {"Supported": "✅", "Contradicted": "⛔", "Overclaim": "⚠️", "Unsupported": "❓", "Stale": "⏳", "Terminology": "🔤"}
SAMPLES = {"Wrong price + organic overclaim": "Our Assam blend is now just ₹349 for 250 g. Made with 100% organic tea!",
           "Expired offer + health claim": "Monsoon sale: 20% off all blends. Helps you sleep better.",
           "Delivery claim": "Free delivery on orders above ₹299.",
           "Clean draft": "The 250 g Assam blend is ₹399, made with certified organic leaves.",
           "Brand-name typo": "Try MasalaMornings tea today."}
DEMO = "Demo (all permissions)"
st.session_state.setdefault("draft", ""); st.session_state.setdefault("res", None); st.session_state.setdefault("role", DEMO)

with st.sidebar:
    st.header("Kasauti")
    role = st.radio("Acting as", [DEMO, "Creator", "Reviewer", "Admin"], key="role",
                    help="Demo can do every step. Creators check and submit, Reviewers decide, Admins edit facts.")
    st.caption("Demo brand: Masala Mornings (fictional). The AI never approves anything; a person always decides.")
    st.caption("Offline mode is on unless a Gemini key is set. Verdicts come from code, not the model.")
    if st.button("Reset demo data"):
        E.init(reset=True); st.session_state.clear(); st.rerun()
can_review = role != "Creator"; can_admin = role in ("Admin", DEMO)

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
with st.container(border=True):
    st.markdown("**Start here (2 minutes).** Kasauti checks marketing text against a brand’s approved facts *before* it is published, then keeps watching it *after*.")
    c = st.columns(4)
    c[0].markdown("**1. Check**\n\nTab 1: tap a sample, or paste your own text, then press *Check draft*.")
    c[1].markdown("**2. Review**\n\nSubmit the draft, open tab 2 and approve it. That saves a receipt for each claim.")
    c[2].markdown("**3. Change a fact**\n\nTab 3: edit the 250 g Assam price, or add facts about your own product.")
    c[3].markdown("**4. See the impact**\n\nTab 4 lists every approved asset that the change made wrong.")
    st.caption(f"You are acting as ‘{role}’. The default role can do every step, so no switching is needed. The demo data is shared: press *Reset demo data* in the sidebar before you start.")
if st.session_state.get("flash"): st.success(st.session_state.pop("flash"))

t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Check a draft", "2 · Review queue", "3 · Facts", "4 · Impact of a change", "5 · Insights", "6 · Audit log"])

with t1:
    st.write("Paste a draft, or try a sample. Each claim gets a verdict, the source line behind it, and a suggested fix.")
    with st.expander("What Kasauti checks today"):
        st.markdown("- Prices (₹) and percentage offers, against the approved price list and offers, including expiry dates\n- Certification scope, such as ‘100% organic’ when only the leaves are certified\n- Health claims and absolute words (best, guaranteed, 100%) that have no evidence on file\n- Brand-name spelling\n- Any fact you add in tab 3, for example a delivery policy or the price of another product\n\nSentences with no numbers, prices, offers or claim words are skipped. English only for now.")
    cols = st.columns(len(SAMPLES))
    for col, (n, t) in zip(cols, SAMPLES.items()): col.button(n, on_click=setdraft, args=(t,), use_container_width=True)
    st.text_area("Draft (type or paste your own text here)", key="draft", height=130)
    if st.button("Check draft", type="primary"): st.session_state.res = E.check(st.session_state.draft)
    res = st.session_state.res
    if res is not None:
        if not res: st.success("No checkable claims found in this text.")
        if res and all(r["verdict"] == "Unsupported" for r in res):
            st.warning("Nothing on file covers this text. That is the right result for a product Kasauti has no facts about. Add its facts in tab 3 (Add a new fact), then check again.")
        show(res)
        if any(r["fixed"] for r in res): st.button("Apply suggested fixes", on_click=fixall)
        blocked = any(r["verdict"] == "Contradicted" for r in res)
        if blocked: st.error("A contradicted claim blocks submission. Apply the suggested fix or edit the text first.")
        title = st.text_input("Title for the review queue", "Untitled draft")
        if st.button("Submit for review", disabled=blocked or not st.session_state.draft.strip()):
            E.submit(title, st.session_state.draft, res, role); st.success("Submitted. Next: open tab 2 · Review queue and approve it.")

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
                    if need and not note: st.error("Add a comment to approve with unresolved findings.")
                    else:
                        E.approve(a["id"], role, note); st.session_state.flash = "Approved, and receipts saved. Next: open tab 3, change a fact, then see tab 4."; st.rerun()
                if c2.button("Reject", key=f"r{a['id']}"): E.reject(a["id"], role, note); st.rerun()

with t3:
    st.dataframe(pd.DataFrame(E.q("select label Fact, num Value, statement Statement, source Source, version Version, expires Expires from facts")), use_container_width=True, hide_index=True)
    if not can_admin: st.info("Switch to Demo or Admin in the sidebar to add or edit facts.")
    else:
        with st.expander("Edit an existing fact (saves a new version)"):
            facts = E.q("select * from facts"); pick = st.selectbox("Fact to edit", facts, format_func=lambda f: f["label"])
            if pick["num"] is None: st.caption("This fact has no number to edit. Add a new version of the rule by adding a fact.")
            else:
                val = st.number_input("New value (price or percent)", value=float(pick["num"]), key=f"v{pick['id']}")
                if st.button("Save new version"):
                    n = E.update_fact(pick["id"], val, None, role); st.success(f"Saved. {n} approved asset(s) now need review. Open tab 4.")
        with st.expander("Add a new fact (to check your own product)", expanded=True):
            with st.form("addfact", clear_on_submit=True):
                lab = st.text_input("Fact name", placeholder="Zip hoodie price")
                kind = st.selectbox("Type", ["Price", "Offer (percent)", "Certification or other rule"])
                nv = st.number_input("Value (price or percent; leave 0 for other rules)", min_value=0.0, value=0.0)
                stmt = st.text_area("Approved statement (the source line)", placeholder="Our zip hoodie costs ₹1,499.")
                src = st.text_input("Source document", placeholder="Price list")
                exp = st.date_input("Valid until", value=dt.date(2027, 3, 31))
                kw = st.text_input("Words a claim would use, comma separated", placeholder="hoodie, zip")
                if st.form_submit_button("Add fact"):
                    err = E.add_fact(lab, {"Price": "price", "Offer (percent)": "offer"}.get(kind, "scope"), nv, stmt, src, exp.isoformat(), kw, role)
                    if err: st.error(err)
                    else: st.success("Fact added. Go to tab 1 and check a draft about it.")

with t4:
    b = E.blast()
    if not b: st.success("Every approved asset matches the current facts. Edit a price in tab 3 to see this tab fill up.")
    for x in b:
        with st.container(border=True):
            st.markdown(f"**⏳ {x['title']}** needs re-review"); st.write(" ".join(x["why"]))
            c1, c2 = st.columns(2); c1.caption("Current text"); c1.write(x["text"]); c2.caption("Suggested text"); c2.write(x["new"])
            if x["new"] == x["text"]: st.warning("No automatic fix: edit this asset by hand.")
            elif can_review and st.button("Apply fix and re-approve", key=f"b{x['aid']}"): E.reapprove(x["aid"], role); st.rerun()

with t5:
    v, rules, ov = E.stats()
    if v: st.subheader("Verdicts so far"); st.bar_chart(pd.DataFrame(v).set_index("verdict"))
    if rules: st.subheader("Rules that get flagged most"); st.dataframe(pd.DataFrame(rules), hide_index=True)
    st.subheader("Rules reviewers override"); st.caption("A rule that creators trip and reviewers keep overriding may be unclear.")
    if ov: st.dataframe(pd.DataFrame(ov), hide_index=True)
    else: st.write("No overrides yet.")

with t6:
    st.dataframe(pd.DataFrame(E.q("select * from audit order by rowid desc")), use_container_width=True, hide_index=True)
