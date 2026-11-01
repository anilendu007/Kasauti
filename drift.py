"""Translation drift: does a Hindi or Hinglish line claim more than the approved English line?
A claim-strength word list (English, Hinglish in Latin script, Devanagari) plus figure and hedge checks."""
import re
CONCEPTS = {  # concept: (strong terms, (softer Hinglish, softer Hindi))
    "guarantee": (["guaranteed", "guarantee", "pakka", "pakki", "gaarantee", "garanti", "पक्का", "पक्की", "गारंटी"], ("madad kar sakta hai", "मदद कर सकता है")),
    "best": (["best", "no.1", "no. 1", "number 1", "number one", "sabse accha", "sabse acha", "sabse achha", "sabse best", "sabse behtar", "सबसे अच्छा", "सबसे अच्छी", "सबसे अच्छे", "सबसे बेहतर", "नंबर 1", "नंबर वन"], ("ek behtar vikalp", "एक बेहतर विकल्प")),
    "total": (["100%", "completely", "totally", "entirely", "ekdum", "bilkul", "poori tarah", "एकदम", "बिल्कुल", "पूरी तरह"], ("kaafi had tak", "काफी हद तक")),
    "always/never": (["always", "never", "hamesha", "kabhi nahi", "हमेशा", "कभी नहीं"], ("aksar", "अक्सर")),
    "only": (["only", "sirf", "keval", "सिर्फ", "केवल"], ("mukhya roop se", "मुख्य रूप से")),
    "cure": (["cure", "cures", "cured", "theek karta", "theek kar deta", "ilaaj", "इलाज", "ठीक करता", "ठीक कर देता"], ("rahat de sakta hai", "राहत दे सकता है")),
    "pure": (["pure", "purest", "shuddh", "खालिस", "शुद्ध"], ("prakritik tatvon se bana", "प्राकृतिक तत्वों से बना")),
}
HEDGES = ["may", "might", "can help", "helps", "up to", "designed to", "aims to", "one of", "sakta hai", "sakti hai", "sakte hain", "madad", "shayad", "tak", "सकता", "सकती", "सकते", "मदद", "शायद", "तक"]
DIG = str.maketrans("०१२३४५६७८९", "0123456789")

def _find(text, term):
    if re.search(r"[a-z0-9%.]", term):   # Latin script or digits: whole-word match
        end = "" if term[-1] in "%." else r"(?![a-z0-9])"
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}{end}", text)
    return re.search(re.escape(term), text)   # Devanagari: plain substring

def _hits(text):
    t, out = re.sub(r"(\d)\s+%", r"\1%", text.lower()), {}
    for c, (terms, _) in CONCEPTS.items():
        for term in terms:
            if _find(t, term): out.setdefault(c, []).append(term)
    return out

def _nums(text): return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text.translate(DIG))}
def _hedge(text): return any(_find(text.lower(), h) for h in HEDGES)

def check_drift(english, translation):
    en, tr = (english or "").strip(), (translation or "").strip()
    if not en or not tr: return {"verdict": "Empty", "issues": [], "fixed": None}
    hen, htr, issues = _hits(en), _hits(tr), []
    for c, terms in htr.items():
        if c not in hen:
            term = terms[0]; soft = CONCEPTS[c][1][0 if re.search(r"[a-z]", term) else 1]
            issues.append(dict(kind="Stronger claim", term=term, why=f"The translation uses ‘{term}’ ({c}), which the English line does not claim.", fix=f"Soften it, for example to ‘{soft}’.", soft=soft))
    ne, nt = _nums(en), _nums(tr)
    if ne != nt:
        issues.append(dict(kind="Figures differ", term=", ".join(sorted(ne ^ nt)), why=f"The figures do not match: the English has {sorted(ne) or 'none'}, the translation has {sorted(nt) or 'none'}.", fix="Use the same figures as the approved English line.", soft=None))
    if not any(i["kind"] == "Stronger claim" for i in issues) and _hedge(en) and not _hedge(tr):
        issues.append(dict(kind="Hedge dropped", term="", why="The English line is hedged (for example ‘can help’ or ‘up to’), but the translation states it as a plain fact.", fix="Add the same hedge, for example ‘sakta hai’ or ‘सकता है’.", soft=None))
    fixed = tr
    for i in issues:
        if i["soft"]: fixed = re.sub(re.escape(i["term"]), i["soft"], fixed, flags=re.I)
    return {"verdict": "Drift" if issues else "Consistent", "issues": issues, "fixed": fixed if fixed != tr else None}
