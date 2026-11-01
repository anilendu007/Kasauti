"""Lightweight accessibility checks: colour contrast (WCAG), text readability, and the basics of a page's HTML."""
import re

def _lin(c): c /= 255; return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
def _rgb(h):
    h = (h or "").strip().lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h): raise ValueError("Use a colour like #1F2A44.")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def _lum(h): r, g, b = (_lin(x) for x in _rgb(h)); return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(fg, bg):
    hi, lo = sorted((_lum(fg), _lum(bg)), reverse=True); ratio = (hi + 0.05) / (lo + 0.05)
    return dict(ratio=round(ratio, 2), aa_normal=ratio >= 4.5, aa_large=ratio >= 3, aaa_normal=ratio >= 7)

def _syll(w): return max(1, len(re.findall(r"[aeiouy]+", w.lower())) - (1 if w.lower().endswith("e") and len(w) > 3 else 0))

def readability(text):
    words = re.findall(r"[A-Za-z']+", text or "")
    if not words: return None
    sents = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if s.strip()]; n = max(1, len(sents))
    score = 206.835 - 1.015 * (len(words) / n) - 84.6 * (sum(_syll(w) for w in words) / len(words))
    issues = [f"Long sentence ({len(s.split())} words): “{s[:70]}…”" for s in sents if len(s.split()) > 25]
    caps = sorted(set(re.findall(r"\b[A-Z]{4,}\b", text)))
    if caps: issues.append(f"All-capital words are harder to read, and some screen readers spell them out: {', '.join(caps[:5])}.")
    if re.search(r"[!?]{2,}", text): issues.append("Repeated ! or ? marks.")
    level = "very easy" if score >= 80 else "easy" if score >= 60 else "fairly difficult" if score >= 40 else "difficult"
    return dict(score=round(score), level=level, words=len(words), sentences=n, issues=issues)

def html_issues(html):
    html, out = html or "", []
    imgs = re.findall(r"<img\b[^>]*>", html, re.I); bad = [i for i in imgs if not re.search(r"\balt\s*=", i, re.I)]
    if bad: out.append(f"{len(bad)} image(s) have no alt text, so screen reader users get nothing.")
    if not re.search(r"<html[^>]*\blang\s*=", html, re.I): out.append("The page does not declare its language (<html lang=...>).")
    if not re.search(r"<title>\s*\S", html, re.I): out.append("The page has no title.")
    vague = re.findall(r">\s*(click here|read more|learn more|here)\s*</a>", html, re.I)
    if vague: out.append(f"{len(vague)} link(s) use vague text such as ‘click here’.")
    return dict(images=len(imgs), issues=out)
