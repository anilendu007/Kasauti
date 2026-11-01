"""Kasauti engine: facts with versions, claim verdicts (code, not the model), receipts, blast radius."""
import sqlite3, re, json, os, threading, datetime as dt
DB = os.environ.get("KASAUTI_DB", "kasauti.db")
_local = threading.local()
def use_db(path): _local.path = path
def dbpath(): return getattr(_local, "path", None) or DB
NOW = lambda: dt.datetime.now().isoformat(" ", "seconds")
VERSION = "round3-2"
RULES = ["price", "offer", "organic scope", "health claim", "superlative", "general fact", "terminology", "no fact"]
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
create table if not exists checks(ts text, verdict text, rule text);
create table if not exists decisions(ts text, actor text, asset_id int, rule text, verdict text, decision text, reason text);
create table if not exists rules(rule text primary key, mode text);"""

def run(sql, a=()):
    c = sqlite3.connect(dbpath())
    try:
        cur = c.execute(sql, a); c.commit(); return cur.lastrowid
    finally: c.close()

def q(sql, a=()):
    c = sqlite3.connect(dbpath()); c.row_factory = sqlite3.Row
    try: return [dict(r) for r in c.execute(sql, a).fetchall()]
    finally: c.close()

def log(actor, action, detail=""): run("insert into audit values(?,?,?,?)", (dt.datetime.now().isoformat(" ", "seconds"), actor, action, detail))

def init(reset=False):
    if reset and os.path.exists(dbpath()): os.remove(dbpath())
    c = sqlite3.connect(dbpath()); c.executescript(SCHEMA); c.close()
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
    for rule, n, o, why in [("superlative", 4, 3, "Brand tagline, not a factual claim"), ("health claim", 3, 0, ""), ("price", 5, 0, ""),
                            ("offer", 3, 1, "Offer is explained on the landing page"), ("organic scope", 2, 0, ""), ("terminology", 4, 2, "Product name is styled on purpose")]:
        for i in range(n):
            run("insert into decisions values(?,?,?,?,?,?,?)", (NOW(), "sample history", 0, rule, "Unsupported", "overridden" if i < o else "upheld", why if i < o else ""))
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

def check(text, use_llm=True):
    facts = q("select * from facts")
    res = [judge(c, facts) for c in ((llm_claims(text) if use_llm else None) or split_claims(text))]
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
    dup = q("select id from assets where status='pending' and title=? and text=?", (title, text))
    if dup: return dup[0]["id"]
    aid = run("insert into assets(title,text,status,findings,note,ts) values(?,?,?,?,?,?)", (title, text, "pending", json.dumps(res), "", TODAY()))
    log(actor, "submitted", f"#{aid} {title}"); return aid

def _decide(aid, actor, res, decision, reason):
    for r in res:
        if r["verdict"] != "Supported": run("insert into decisions values(?,?,?,?,?,?,?)", (NOW(), actor, aid, r["rule"], r["verdict"], decision, reason))

def approve(aid, actor, note=""):
    rows = q("select * from assets where id=? and status='pending'", (aid,))
    if not rows: return False
    a = rows[0]; res = json.loads(a["findings"])
    run("delete from receipts where asset_id=?", (aid,))
    for r in res:
        if r["verdict"] == "Supported" and r["fact_id"]: run("insert into receipts values(?,?,?,?,?)", (aid, r["claim"], r["fact_id"], r["fact_version"], "Supported"))
        elif r["verdict"] != "Supported": log(actor, "override", r["rule"])
    _decide(aid, actor, res, "overridden", note)
    run("update assets set status='approved', note=? where id=?", (note, aid)); log(actor, "approved", f"#{aid} {a['title']} {note}".strip()); return True

def reject(aid, actor, note=""):
    rows = q("select * from assets where id=? and status='pending'", (aid,))
    if not rows: return False
    _decide(aid, actor, json.loads(rows[0]["findings"]), "upheld", note)
    run("update assets set status='rejected', note=? where id=?", (note, aid)); log(actor, "rejected", f"#{aid} {note}".strip()); return True

def _alts(n): return "|".join(sorted({re.escape(f"{int(n):,}"), re.escape(str(int(n)))}, key=len, reverse=True))

def swap_number(text, old, new, kind):
    """Replace an old price or percent with the new one, in any wording: ₹20, Rs. 20, 20 rupees, 20%."""
    o, n = _alts(old), str(int(new))
    if kind == "price":
        text = re.sub(rf"((?:₹|Rs\.?|INR)\s?)(?:{o})(?!\d)", rf"\g<1>{n}", text, flags=re.I)
        text = re.sub(rf"(?<![\d,])(?:{o})(\s?(?:rupees?|Rs\b))", rf"{n}\g<1>", text, flags=re.I)
    else:
        text = re.sub(rf"(?<![\d,])(?:{o})(\s?%)", rf"{n}\g<1>", text)
    return text

def update_fact(fid, num, statement, actor):
    """Save a new version of any fact (value and/or statement). Returns how many approved assets are now affected."""
    rows = q("select * from facts where id=?", (fid,))
    if not rows: return 0
    f = rows[0]
    if statement is None:
        statement = f["statement"]
        if f["num"] is not None and num is not None and int(num) != int(f["num"]): statement = swap_number(statement, f["num"], num, f["kind"])
    num = f["num"] if num is None else num
    if num == f["num"] and statement == f["statement"]: return len(blast())
    v = f["version"] + 1
    run("update facts set num=?, statement=?, version=? where id=?", (num, statement, v, fid))
    run("insert into fact_hist values(?,?,?,?,?)", (fid, v, num, statement, TODAY()))
    log(actor, "fact updated", f"{f['label']} v{v}"); return len(blast())

def blast():
    rows = q("select a.id aid,a.title,a.text,f.id fid,f.label,f.kind,f.num,f.version fv,r.fact_version rv,f.expires from receipts r join assets a on a.id=r.asset_id join facts f on f.id=r.fact_id where a.status='approved' and (f.version>r.fact_version or f.expires<?)", (TODAY(),))
    out = {}
    for r in rows:
        o = out.setdefault(r["aid"], dict(aid=r["aid"], title=r["title"], text=r["text"], why=[], new=r["text"]))
        if r["fv"] > r["rv"]:
            old = q("select num from fact_hist where fact_id=? and version=?", (r["fid"], r["rv"]))
            if old and old[0]["num"] is not None and r["num"] is not None and int(old[0]["num"]) != int(r["num"]) and r["kind"] in ("price", "offer"):
                o["new"] = swap_number(o["new"], old[0]["num"], r["num"], r["kind"]); msg = f"{r['label']} changed from {int(old[0]['num'])} to {int(r['num'])}."
            else: msg = f"{r['label']} was edited."
        else: msg = f"{r['label']} expired on {r['expires']}."
        if msg not in o["why"]: o["why"].append(msg)
    return list(out.values())

def recheck(aid, actor):
    """After a fact change: apply the suggested text, re-run the checks, then re-approve (clean) or send back to the review queue."""
    b = [x for x in blast() if x["aid"] == aid]
    if not b: return "nothing to do"
    text = b[0]["new"]; res = check(text)
    run("update assets set text=?, findings=?, status='pending' where id=?", (text, json.dumps(res), aid)); log(actor, "text revised", f"#{aid}")
    if all(r["verdict"] == "Supported" for r in res):
        approve(aid, actor, "re-approved after a fact change"); return "approved"
    log(actor, "sent back to review", f"#{aid}"); return "needs_review"

def reapprove(aid, actor): return recheck(aid, actor)

def rule_mode(rule):
    r = q("select mode from rules where rule=?", (rule,)); return r[0]["mode"] if r else "blocking"

def set_rule_mode(rule, mode, actor):
    run("insert into rules values(?,?) on conflict(rule) do update set mode=excluded.mode", (rule, mode)); log(actor, "rule mode", f"{rule}: {mode}")

def rule_stats():
    """Reviewer feedback loop: how often reviewers override each rule. Often-overridden rules are flagged as possibly unclear."""
    out = []
    for r in q("select rule, count(*) n, sum(decision='overridden') o from decisions group by rule"):
        rate = r["o"] / r["n"]
        why = [x["reason"] for x in q("select reason from decisions where rule=? and decision='overridden' and reason!='' group by reason order by count(*) desc limit 3", (r["rule"],))]
        out.append(dict(rule=r["rule"], reviewed=r["n"], overridden=r["o"], rate=round(100 * rate), unclear=r["n"] >= 3 and rate >= 0.5, mode=rule_mode(r["rule"]), reasons=why))
    return sorted(out, key=lambda x: -x["rate"])

def stats():
    return (q("select verdict, count(*) n from checks group by verdict"),
            q("select rule, count(*) n from checks where verdict!='Supported' group by rule order by n desc"),
            q("select detail rule, count(*) n from audit where action='override' group by detail order by n desc"))

def add_fact(label, kind, num, statement, source, expires, keywords, actor):
    """Add a new approved fact (version 1). Returns an error message, or '' on success."""
    if q("select 1 from facts where lower(label)=lower(?)", (label.strip(),)): return "A fact with this name already exists. Edit it instead."
    if not label.strip() or not statement.strip(): return "Give the fact a name and an approved statement."
    if kind in ("price", "offer") and not num: return "Price and offer facts need a value."
    key = " ".join(re.findall(r"[a-z0-9]+", norm(keywords + " " + label + (" off" if kind == "offer" else ""))))
    fid = run("insert into facts(key,label,kind,num,statement,source,version,expires) values(?,?,?,?,?,?,1,?)",
              (key, label.strip(), kind, num or None, statement.strip(), source.strip() or "Added by admin", expires))
    run("insert into fact_hist values(?,1,?,?,?)", (fid, num or None, statement.strip(), TODAY()))
    log(actor, "fact added", label.strip()); return ""
