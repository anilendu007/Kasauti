"""Kasauti engine: facts with versions, claim verdicts (code, not the model), receipts, blast radius."""
import sqlite3, re, json, os, datetime as dt
DB = os.environ.get("KASAUTI_DB", "kasauti.db")
TODAY = lambda: dt.date.today().isoformat()
ABS = r"(?:\b(?:best|guaranteed?|only|purest|completely|totally|always|never)\b|100\s?%|\bno\.?\s?1\b)"
HEALTH = r"\b(?:cures?|clinically proven|detox\w*|helps? (?:you )?sleep|lose weight|boosts? immunity|anti-?aging)\b"
CLAIM = re.compile(r"[₹%]|\bRs\.?|\d|organic|offer|sale|\boff\b|" + ABS + "|" + HEALTH, re.I)
SCHEMA = """create table if not exists facts(id integer primary key, key text, label text, kind text, num real, statement text, source text, version integer, expires text);
create table if not exists fact_hist(fact_id int, version int, num real, statement text, ts text);
create table if not exists assets(id integer primary key, title text, text text, status text, findings text, note text, ts text);
create table if not exists receipts(asset_id int, claim text, fact_id int, fact_version int, verdict text);
create table if not exists audit(ts text, actor text, action text, detail text);
create table if not exists terms(bad text, good text);
create table if not exists checks(ts text, verdict text, rule text);"""

def run(sql, a=()):
    c = sqlite3.connect(DB)
    try:
        cur = c.execute(sql, a); c.commit(); return cur.lastrowid
    finally: c.close()

def q(sql, a=()):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    try: return [dict(r) for r in c.execute(sql, a).fetchall()]
    finally: c.close()

def log(actor, action, detail=""): run("insert into audit values(?,?,?,?)", (dt.datetime.now().isoformat(" ", "seconds"), actor, action, detail))

def init(reset=False):
    if reset and os.path.exists(DB): os.remove(DB)
    c = sqlite3.connect(DB); c.executescript(SCHEMA); c.close()
    if q("select count(*) n from facts")[0]["n"]: return
    F = [("price 250g assam blend tea", "250 g Assam blend price", "price", 399, "The 250 g Assam blend costs ₹399 from 1 October 2026.", "Price list v3", "2027-03-31"),
         ("organic leaves certified", "Organic certification", "scope", None, "The tea leaves are certified organic. Packaging and flavourings are not covered by the certificate.", "Organic certificate OC-118", "2027-03-31"),
         ("monsoon sale offer discount off", "Monsoon sale", "offer", 20, "Monsoon sale: 20% off all blends until 30 September 2026.", "Campaign brief, Aug 2026", "2026-09-30"),
         ("festive offer discount diwali off", "Festive offer", "offer", 15, "Festive offer: 15% off all blends until 15 November 2026.", "Campaign brief, Oct 2026", "2026-11-15"),
         ("free delivery orders above", "Free delivery", "scope", None, "Free delivery on orders above ₹499 across India.", "Shipping policy", "2027-03-31")]
    for i, f in enumerate(F, 1):
        run("insert into facts values(?,?,?,?,?,?,?,1,?)", (i, f[0], f[1], f[2], f[3], f[4], f[5], f[6]))
        run("insert into fact_hist values(?,1,?,?,?)", (i, f[3], f[4], TODAY()))
    for b, g in [("MasalaMornings", "Masala Mornings"), ("Masala Morning(?!s)", "Masala Mornings"), ("Masla Mornings", "Masala Mornings")]:
        run("insert into terms values(?,?)", (b, g))
    for t, x in [("Instagram caption", "Fresh Assam in every cup. The 250 g Assam blend is ₹399 and tastes bold."),
                 ("Website banner", "Our 250 g Assam blend: ₹399. Brewed bold."),
                 ("Email: new arrivals", "Meet the Assam blend: 250 g for ₹399."),
                 ("WhatsApp broadcast", "Chai time! Grab the 250 g Assam blend at ₹399."),
                 ("Blog intro", "Our leaves are certified organic; packaging and flavourings are not.")]:
        aid = submit(t, x, check(x), "seed"); approve(aid, "seed")

def norm(s): return re.sub(r"(\d)\s+g\b", r"\1g", s.lower())
def toks(s): return set(re.findall(r"[a-z0-9]+", norm(s)))

def find(claim, facts, kind=None, minscore=1):
    t, best, top = toks(claim), None, 0
    for f in facts:
        if kind and f["kind"] != kind: continue
        sc = len(t & toks(f["key"])) + (2 if f["num"] and str(int(f["num"])) in t else 0)
        if sc > top: best, top = f, sc
    return best if top >= minscore else None

def split_claims(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+|,\s+(?=made with|and |with )", text.strip())
    return [p.strip() for p in parts if p.strip() and CLAIM.search(p)]

def llm_claims(text):
    """Optional: Gemini splits text into claims. Any failure returns None and the offline splitter is used."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return None
    try:
        import requests
        body = {"contents": [{"parts": [{"text": "Split this marketing text into separate factual claims (prices, offers, certifications, health or superlative claims). Return only a JSON list of strings copied word for word from the text.\n\n" + text}]}]}
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent", params={"key": key}, json=body, timeout=12)
        out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        lst = json.loads(re.sub(r"```(?:json)?", "", out).strip())
        return [s for s in lst if s in text] or None   # quote guard: a claim must appear word for word in the draft
    except Exception:
        return None

def judge(claim, facts):
    def R(v, why, f=None, fix=None, fixed=None, rule=""):
        return dict(claim=claim, verdict=v, why=why, fact_id=f["id"] if f else None, fact_version=f["version"] if f else None,
                    evidence=f["statement"] if f else None, fix=fix, fixed=fixed, rule=rule)
    today = TODAY()
    m = re.search(r"(?:₹|Rs\.?|INR)\s?(\d[\d,]*)|(\d[\d,]*)\s?(?:rupees?|Rs\b\.?|₹)", claim, re.I)
    p = re.search(r"(\d+)\s?%", claim)
    f = find(claim, facts, "price") if m else None
    if f:
        if f["expires"] < today: return R("Stale", f"The price fact expired on {f['expires']}.", f, "Update the price fact first.", rule="price")
        amt = int((m.group(1) or m.group(2)).replace(",", ""))
        if amt == f["num"]: return R("Supported", "Matches the approved price.", f, rule="price")
        return R("Contradicted", f"The draft says ₹{amt}; the approved price is ₹{int(f['num'])}.", f, "Use the approved price.", claim.replace(m.group(0), f"₹{int(f['num'])}"), "price")
    if p and re.search(r"\boff\b|sale|offer|discount", claim, re.I):
        f = find(claim, facts, "offer")
        if not f: return R("Unsupported", "No approved offer covers this claim.", rule="offer")
        if f["expires"] < today: return R("Stale", f"This offer ended on {f['expires']}.", f, "Remove the line, or add a current offer to the facts.", rule="offer")
        if int(p.group(1)) != f["num"]: return R("Contradicted", f"The draft says {p.group(1)}%; the approved offer is {int(f['num'])}%.", f, "Use the approved discount.", claim.replace(p.group(0), f"{int(f['num'])}%"), "offer")
        return R("Supported", "Matches the approved offer.", f, rule="offer")
    if re.search(HEALTH, claim, re.I):
        return R("Unsupported", "Health claims need evidence, and none is on file.", fix="Remove it, or add the evidence to the facts.", rule="health claim")
    if "organic" in claim.lower():
        f = find(claim, facts, "scope")
        if f and re.search(ABS, claim, re.I) and "not covered" in f["statement"]:
            fx = re.sub(r"(?i)(made with )?100\s?%\s*organic( tea)?", "made with certified organic leaves", claim)
            return R("Overclaim", "The certificate covers the leaves only, not the whole product.", f, "Say what is certified: ‘made with certified organic leaves’.", fx if fx != claim else None, "organic scope")
        if f: return R("Supported", "Consistent with the organic certificate.", f, rule="organic scope")
    f = find(claim, facts, None, 2)
    if f:
        if f["expires"] < today: return R("Stale", f"This fact expired on {f['expires']}.", f, "Update the fact first.", rule="general fact")
        extra = set(re.findall(r"\d+", claim.replace(",", ""))) - set(re.findall(r"\d+", f["statement"].replace(",", "")))
        if extra: return R("Contradicted", f"The figures ({', '.join(sorted(extra))}) differ from the approved line.", f, "Use the figures in the approved fact.", rule="general fact")
        return R("Supported", "Consistent with an approved fact.", f, rule="general fact")
    if re.search(ABS, claim, re.I):
        return R("Unsupported", "Absolute or superlative claim with no supporting fact.", fix="Soften it or add evidence.", rule="superlative")
    return R("Unsupported", "No approved fact covers this claim.", rule="no fact")

def check(text):
    facts = q("select * from facts")
    res = [judge(c, facts) for c in (llm_claims(text) or split_claims(text))]
    seen = set()
    for t in q("select * from terms"):
        for m in re.finditer(t["bad"], text):
            if m.group(0) not in seen:
                seen.add(m.group(0))
                res.append(dict(claim=m.group(0), verdict="Terminology", why=f"The brand name should read ‘{t['good']}’.", fact_id=None, fact_version=None, evidence=None, fix=t["good"], fixed=t["good"], rule="terminology"))
    for r in res: run("insert into checks values(?,?,?)", (dt.datetime.now().isoformat(" ", "seconds"), r["verdict"], r["rule"]))
    return res

def apply_fixes(text, res):
    for r in res:
        if r.get("fixed") and r["claim"] in text: text = text.replace(r["claim"], r["fixed"], 1)
    return text

def submit(title, text, res, actor):
    aid = run("insert into assets(title,text,status,findings,note,ts) values(?,?,?,?,?,?)", (title, text, "pending", json.dumps(res), "", TODAY()))
    log(actor, "submitted", f"#{aid} {title}"); return aid

def approve(aid, actor, note=""):
    a = q("select * from assets where id=?", (aid,))[0]
    run("delete from receipts where asset_id=?", (aid,))
    for r in json.loads(a["findings"]):
        if r["verdict"] == "Supported" and r["fact_id"]:
            run("insert into receipts values(?,?,?,?,?)", (aid, r["claim"], r["fact_id"], r["fact_version"], "Supported"))
        elif r["verdict"] != "Supported":
            log(actor, "override", r["rule"])
    run("update assets set status='approved', note=? where id=?", (note, aid)); log(actor, "approved", f"#{aid} {a['title']} {note}".strip())

def reject(aid, actor, note=""):
    run("update assets set status='rejected', note=? where id=?", (note, aid)); log(actor, "rejected", f"#{aid} {note}".strip())

def update_fact(fid, num, statement, actor):
    f = q("select * from facts where id=?", (fid,))[0]; v = f["version"] + 1
    if statement is None: statement = re.sub(r"₹\d+", f"₹{int(num)}", f["statement"]) if f["kind"] == "price" else f["statement"]
    run("update facts set num=?, statement=?, version=? where id=?", (num, statement, v, fid))
    run("insert into fact_hist values(?,?,?,?,?)", (fid, v, num, statement, TODAY()))
    log(actor, "fact updated", f"{f['label']} v{v}"); return len(blast())

def blast():
    rows = q("select a.id aid,a.title,a.text,f.id fid,f.label,f.kind,f.num,f.version fv,r.fact_version rv,f.expires from receipts r join assets a on a.id=r.asset_id join facts f on f.id=r.fact_id where a.status='approved' and (f.version>r.fact_version or f.expires<?)", (TODAY(),))
    out = {}
    for r in rows:
        o = out.setdefault(r["aid"], dict(aid=r["aid"], title=r["title"], text=r["text"], why=[], new=r["text"]))
        if r["fv"] > r["rv"] and r["num"] is not None:
            old = q("select num from fact_hist where fact_id=? and version=?", (r["fid"], r["rv"]))[0]["num"]
            pat, rep = (f"₹{int(old)}", f"₹{int(r['num'])}") if r["kind"] == "price" else (f"{int(old)}%", f"{int(r['num'])}%")
            o["new"] = o["new"].replace(pat, rep); o["why"].append(f"{r['label']} changed from {int(old)} to {int(r['num'])}.")
        elif r["fv"] > r["rv"]: o["why"].append(f"{r['label']} was edited.")
        else: o["why"].append(f"{r['label']} expired on {r['expires']}.")
    return list(out.values())

def reapprove(aid, actor):
    b = [x for x in blast() if x["aid"] == aid][0]; res = check(b["new"])
    run("update assets set text=?, findings=? where id=?", (b["new"], json.dumps(res), aid)); log(actor, "text revised", f"#{aid}")
    approve(aid, actor, "re-approved after a fact change")

def stats():
    return (q("select verdict, count(*) n from checks group by verdict"),
            q("select rule, count(*) n from checks where verdict!='Supported' group by rule order by n desc"),
            q("select detail rule, count(*) n from audit where action='override' group by detail order by n desc"))

def add_fact(label, kind, num, statement, source, expires, keywords, actor):
    """Add a new approved fact (version 1). Returns an error message, or '' on success."""
    if not label.strip() or not statement.strip(): return "Give the fact a name and an approved statement."
    if kind in ("price", "offer") and not num: return "Price and offer facts need a value."
    key = " ".join(re.findall(r"[a-z0-9]+", norm(keywords + " " + label + (" off" if kind == "offer" else ""))))
    fid = run("insert into facts(key,label,kind,num,statement,source,version,expires) values(?,?,?,?,?,?,1,?)",
              (key, label.strip(), kind, num or None, statement.strip(), source.strip() or "Added by admin", expires))
    run("insert into fact_hist values(?,1,?,?,?)", (fid, num or None, statement.strip(), TODAY()))
    log(actor, "fact added", label.strip()); return ""
