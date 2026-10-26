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
