import os, sys, tempfile
os.environ["KASAUTI_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import engine as E
E.init()

def test_price_contradicted():
    r = E.check("Now just ₹349 for 250 g.")[0]
    assert r["verdict"] == "Contradicted" and "₹399" in r["evidence"] and "₹399" in r["fixed"]
def test_overclaim():
    assert E.check("Made with 100% organic tea!")[0]["verdict"] == "Overclaim"
def test_stale_and_health():
    assert [r["verdict"] for r in E.check("Monsoon sale: 20% off all blends. Helps you sleep better.")] == ["Stale", "Unsupported"]
def test_supported():
    assert all(r["verdict"] == "Supported" for r in E.check("The 250 g Assam blend is ₹399, made with certified organic leaves."))
def test_terminology_fix():
    r = E.check("Try MasalaMornings tea")[0]
    assert r["verdict"] == "Terminology" and E.apply_fixes("Try MasalaMornings tea", [r]) == "Try Masala Mornings tea"
def test_blast_radius():
    E.init(reset=True)
    assert E.blast() == []
    E.update_fact(1, 429, None, "admin"); b = E.blast()
    assert len(b) == 4 and all("₹429" in x["new"] for x in b)
    E.reapprove(b[0]["aid"], "reviewer"); assert len(E.blast()) == 3
    E.init(reset=True)

def test_add_fact_price_and_general():
    E.init(reset=True)
    assert E.add_fact("Darjeeling 100 g price", "price", 250, "The 100 g Darjeeling blend costs ₹250.", "Price list", "2027-03-31", "darjeeling, 100g", "admin") == ""
    assert E.check("Darjeeling 100 g for just ₹199.")[0]["verdict"] == "Contradicted"
    assert E.check("Darjeeling 100 g is ₹250.")[0]["verdict"] == "Supported"
    E.add_fact("Free delivery", "scope", None, "Free delivery on orders above ₹499 across India.", "Policy", "2027-03-31", "free delivery orders", "admin")
    assert E.check("Free delivery on orders above ₹499.")[0]["verdict"] == "Supported"
    assert E.check("Free delivery on orders above ₹299.")[0]["verdict"] == "Contradicted"
    assert E.add_fact("", "scope", None, "x", "", "2027-03-31", "", "admin") != ""
    E.init(reset=True)

def test_rupees_wording():
    E.init(reset=True)
    E.add_fact("Maggie price", "price", 20, "Our Maggie costs 20 rupees per packet.", "Price List", "2027-03-30", "maggie, packet", "admin")
    assert E.check("Our brand Maggie is for 20 rupees per packet. It is very delicious.")[0]["verdict"] == "Supported"
    r = E.check("Our brand Maggie is for 25 rupees per packet.")[0]
    assert r["verdict"] == "Contradicted" and "₹20" in r["fixed"]
    E.init(reset=True)

def test_added_fact_edit_and_recheck():
    E.init(reset=True)
    E.add_fact("Maggie price", "price", 20, "Our Maggie costs 20 rupees per packet.", "Price List", "2027-03-30", "maggie, packet", "admin")
    txt = "Our brand Maggie is for 20 rupees per packet."
    aid = E.submit("Maggie post", txt, E.check(txt), "creator"); assert E.approve(aid, "reviewer")
    assert E.approve(aid, "reviewer") is False
    fid = E.q("select id from facts where label='Maggie price'")[0]["id"]
    assert E.update_fact(fid, 25, None, "admin") == 1
    assert "25 rupees" in [x for x in E.blast() if x["aid"] == aid][0]["new"]
    assert E.recheck(aid, "reviewer") == "approved" and not [x for x in E.blast() if x["aid"] == aid]
    E.init(reset=True)
def test_rule_fact_edit_goes_back_to_review():
    E.init(reset=True)
    txt = "Free delivery on orders above ₹499."
    aid = E.submit("d", txt, E.check(txt), "c"); E.approve(aid, "r")
    E.update_fact(5, None, "Free delivery on orders above ₹799 across India.", "admin")
    assert [x["aid"] for x in E.blast()] == [aid]
    assert E.recheck(aid, "r") == "needs_review" and E.q("select status from assets where id=?", (aid,))[0]["status"] == "pending"
    E.init(reset=True)
def test_swap_number_formats():
    assert E.swap_number("Only ₹1,499 or Rs. 1499 or 1499 rupees", 1499, 1799, "price") == "Only ₹1799 or Rs. 1799 or 1799 rupees"
    assert E.swap_number("Get 20% off, not 120%", 20, 25, "offer") == "Get 25% off, not 120%"
def test_robustness():
    E.init(reset=True)
    assert E.check("") == [] and E.check("   \n ") == []
    r = E.check("Sale!!! ₹₹₹ 100% ??? 💥")
    assert isinstance(r, list)
    a = E.submit("x", "Helps you sleep better.", E.check("Helps you sleep better."), "c"); assert E.submit("x", "Helps you sleep better.", [], "c") == a
    assert E.add_fact("250 g Assam blend price", "price", 1, "x", "", "2027-01-01", "", "a") != ""
    assert E.reject(999, "r") is False and E.approve(999, "r") is False
def test_feedback_loop():
    E.init(reset=True)
    for i in range(3):
        t = "Helps you sleep better."; aid = E.submit(f"p{i}", t, E.check(t), "c"); assert E.approve(aid, "r", "Not a medical claim")
    h = [x for x in E.rule_stats() if x["rule"] == "health claim"][0]
    assert h["overridden"] >= 3 and h["unclear"] and "Not a medical claim" in h["reasons"]
    E.set_rule_mode("price", "advisory", "admin"); assert E.rule_mode("price") == "advisory" and E.rule_mode("offer") == "blocking"
    E.init(reset=True)
def test_private_databases():
    import tempfile; p = os.path.join(tempfile.mkdtemp(), "visitor.db")
    E.use_db(p); E.init(); E.update_fact(1, 999, None, "a"); assert E.q("select num from facts where id=1")[0]["num"] == 999
    E.use_db(None); assert E.q("select num from facts where id=1")[0]["num"] == 399

def test_drift():
    import drift as D
    r = D.check_drift("Can help reduce hair fall.", "Yeh tel hair fall pakka rokta hai.")
    assert r["verdict"] == "Drift" and any(i["term"] == "pakka" for i in r["issues"]) and "madad kar sakta hai" in r["fixed"]
    assert D.check_drift("Up to 20% off on all blends.", "Sabhi blends par 30% off.")["verdict"] == "Drift"
    assert D.check_drift("A good choice for tea lovers.", "चाय प्रेमियों के लिए सबसे अच्छी पसंद।")["verdict"] == "Drift"
    assert D.check_drift("Made with certified organic leaves.", "Certified organic patton se bani chai.")["verdict"] == "Consistent"
    assert D.check_drift("Best tea.", "Sabse accha chai.")["verdict"] == "Consistent"
    assert D.check_drift("Can help with sleep.", "Neend mein madad kar sakta hai.")["verdict"] == "Consistent"
    assert D.check_drift("", "x")["verdict"] == "Empty"
def test_scan_sample_and_safety():
    import scan as S
    E.init(reset=True)
    out = S.scan_html(S.SAMPLE_HTML); v = [r["verdict"] for r in out["results"]]
    for want in ("Contradicted", "Overclaim", "Stale", "Unsupported", "Terminology"): assert want in v
    assert any(r["verdict"] == "Supported" and r["approved_as"] == "Website banner" for r in out["results"])
    for bad in ["", "ftp://example.com", "http://localhost:8501", "http://127.0.0.1/", "http://192.168.1.1/", "http://nonexistent.invalid/", "two words"]:
        try: S.fetch(bad); assert False, bad
        except S.ScanError: pass
    assert "x=1" not in S.html_to_text("<p>a 100% organic</p><script>x=1</script>") and "100% organic" in S.html_to_text("<p>a 100% organic</p>")
    assert S.scan_html("")["results"] == []
    E.init(reset=True)

def test_scan_messages_and_paste():
    import scan as S
    try: S.fetch("https://kasauti.streamlit.app"); assert False
    except S.ScanError as e: assert "JavaScript" in str(e)
    E.init(reset=True)
    assert S.scan_html("Our Assam blend: now ₹349.")["results"][0]["verdict"] == "Contradicted"
    assert E.VERSION == "round3-4"
    E.init(reset=True)

def test_price_without_figure_fails_closed():
    E.init(reset=True)
    assert E.check("Only three hundred and forty nine rupees for 250 g Assam blend")[0]["verdict"] == "Unsupported"
def test_revision_history():
    E.init(reset=True)
    aid = E.submit("Banner", "Our 250 g Assam blend: ₹399.", E.check("Our 250 g Assam blend: ₹399."), "c"); E.approve(aid, "r")
    E.update_fact(1, 429, None, "a"); E.recheck(aid, "r")
    h = E.history(aid); assert [x["rev"] for x in h] == [1, 2] and "₹429." in " ".join(E.changes(h[0]["text"], h[1]["text"]))
    E.init(reset=True)
def test_glossary_editing():
    E.init(reset=True)
    assert E.add_term("Masala Morning Tea", "Masala Mornings tea", "a") == "" and E.add_term("Masala Morning Tea", "x", "a") != "" and E.add_term("", "x", "a") != ""
    assert any(r["verdict"] == "Terminology" and r["claim"] == "Masala Morning Tea" for r in E.check("Try Masala Morning Tea today"))
    E.del_term([t for t in E.terms() if t["wrong"] == "Masala Morning Tea"][0]["id"], "a")
    assert not any(r["claim"] == "Masala Morning Tea" for r in E.check("Try Masala Morning Tea today"))
    E.init(reset=True)
def test_import_export_and_pack():
    E.init(reset=True)
    rows = [{"fact": "Hoodie price", "type": "price", "value": "1499", "statement": "Our hoodie costs ₹1499.", "source": "List", "expires": "2027-03-31", "keywords": "hoodie"},
            {"fact": "Bad row", "type": "nonsense", "value": "", "statement": "x", "source": "", "expires": "2027-03-31", "keywords": ""},
            {"fact": "Bad date", "type": "rule", "value": "", "statement": "x", "source": "", "expires": "31/03/2027", "keywords": ""},
            {"fact": "Returns", "type": "rule", "value": "", "statement": "Returns within 7 days.", "source": "", "expires": "", "keywords": "returns"}]
    assert E.import_facts(rows, "a")[0:2] == (2, 0) and len(E.import_facts(rows, "a")[2]) == 2
    assert E.check("Our hoodie is just ₹999.")[0]["verdict"] == "Contradicted"
    E.set_rule_mode("offer", "advisory", "a"); pack = E.pack_json(); E.init(reset=True)
    added, skipped, errs = E.load_pack(pack, "a")
    assert (added, skipped, errs) == (2, 5, []) and E.rule_mode("offer") == "advisory" and E.check("Our hoodie is just ₹999.")[0]["verdict"] == "Contradicted"
    assert E.load_pack("not json", "a")[2] and E.load_pack('{"app": "other"}', "a")[2]
    assert len(E.receipts_rows()) >= 4
    E.init(reset=True)
def test_document_import():
    import io, zipfile, docs as Dx
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z: z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Now just ₹349.</w:t></w:r></w:p><w:p><w:r><w:t>Made with 100% organic tea.</w:t></w:r></w:p></w:body></w:document>')
    t = Dx.extract_text("draft.docx", buf.getvalue()); assert "₹349" in t and t.count("\n") == 1
    assert "hello" in Dx.extract_text("a.txt", b"hello")
    for name, data in [("a.exe", b"x"), ("bad.docx", b"not a zip")]:
        try: Dx.extract_text(name, data); assert False
        except Dx.DocError: pass
def test_accessibility_lite():
    import a11y as A, scan as S
    assert A.contrast("#000000", "#FFFFFF")["ratio"] == 21.0 and A.contrast("#777777", "#FFFFFF")["aa_normal"] is False and A.contrast("#1F2A44", "#FAF6EC")["aa_normal"] is True
    r = A.readability("BUY TODAY!!! This is a very long sentence " + "word " * 30 + "end.")
    assert any("All-capital" in i for i in r["issues"]) and any("Long sentence" in i for i in r["issues"]) and any("Repeated" in i for i in r["issues"])
    assert len(A.html_issues('<html><body><img src="a.jpg"><a href="/x">click here</a></body></html>')["issues"]) == 4
    assert A.html_issues('<html lang="en"><head><title>T</title></head><body><img src="a.jpg" alt="Tea"></body></html>')["issues"] == []
    try: A.contrast("zzz", "#fff"); assert False
    except ValueError: pass
    E.init(reset=True); assert any("alt" in i for i in S.scan_html(S.SAMPLE_HTML)["a11y"]["issues"]); E.init(reset=True)

def test_rs_abbreviation_and_packaging():
    E.init(reset=True)
    assert [r["verdict"] for r in E.check("Assam blend, 250 g, Rs. 399/-")] == ["Supported"]
    assert E.check("Our packaging is fully organic and compostable.")[0]["verdict"] == "Overclaim"
    assert E.check("Our leaves are certified organic; packaging and flavourings are not.")[0]["verdict"] == "Supported"
    E.init(reset=True)
