"""Live-page scan: fetch a public web page, pull out its claims and run the same checker on them. Standard library only."""
import re, socket, ipaddress, urllib.request, urllib.parse, urllib.error, urllib.robotparser
from html.parser import HTMLParser
import engine as E
MAX_BYTES = 1_500_000
HEAD = {"User-Agent": "KasautiBot/1.0 (+https://github.com/anilendu007/Kasauti)"}
SAMPLE_HTML = """<html><head><title>Masala Mornings</title><style>.a{color:red}</style><script>var x = 1;</script></head><body>
<nav>Home Shop About</nav><h1>Masala Mornings Assam Blend</h1>
<p>Our Assam blend, 250 g, now just ₹349.</p><p>Our 250 g Assam blend: ₹399.</p><p>Made with 100% organic tea.</p>
<p>Monsoon sale: 20% off all blends.</p><p>Festive offer: 15% off all blends.</p><p>Free delivery on orders above ₹299.</p>
<p>Helps you sleep better.</p><p>Try MasalaMornings today.</p></body></html>"""

class ScanError(Exception): pass

class _Text(HTMLParser):
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article", "header", "footer", "td", "th", "ul", "ol", "table"}
    SKIP = {"script", "style", "noscript", "svg", "head", "template"}
    def __init__(self): super().__init__(convert_charrefs=True); self.out, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP: self.skip += 1
        elif tag in self.BLOCK: self.out.append("\n")
    def handle_endtag(self, tag):
        if tag in self.SKIP: self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK: self.out.append("\n")
    def handle_data(self, d):
        if not self.skip: self.out.append(d)

def html_to_text(html):
    p = _Text(); p.feed(html or ""); p.close()
    return "\n".join(l for l in (re.sub(r"\s+", " ", x).strip() for x in "".join(p.out).split("\n")) if l)

def _check_public(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname: raise ScanError("Enter a full web address that starts with http:// or https://.")
    try: infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError): raise ScanError("Could not find that website. Check the address.")
    for i in infos:
        ip = ipaddress.ip_address(i[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ScanError("That address points to a private or internal network, which Kasauti does not scan.")

class _Safe(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_public(newurl); return super().redirect_request(req, fp, code, msg, headers, newurl)

def _robots_ok(url, opener):
    p = urllib.parse.urlparse(url)
    try:
        with opener.open(urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers=HEAD), timeout=5) as r: lines = r.read(200000).decode("utf-8", "replace").splitlines()
    except Exception: return True
    rp = urllib.robotparser.RobotFileParser(); rp.parse(lines); return rp.can_fetch("KasautiBot", url)

def fetch(url):
    url = (url or "").strip()
    if not url: raise ScanError("Enter a web address first.")
    if " " in url: raise ScanError("A web address cannot contain spaces.")
    if "://" not in url: url = "https://" + url
    if (urllib.parse.urlparse(url).hostname or "").endswith(("streamlit.app", "streamlit.io")):
        raise ScanError("Streamlit apps draw their content with JavaScript behind a sign-in redirect, so a simple page reader sees only an empty shell. Scan a regular web page instead, or paste the page text below.")
    _check_public(url)
    opener = urllib.request.build_opener(_Safe())
    try:
        if not _robots_ok(url, opener): raise ScanError("The site’s robots.txt asks automated tools not to read this page, so Kasauti skipped it.")
        with opener.open(urllib.request.Request(url, headers=HEAD), timeout=10) as r:
            ctype = r.headers.get_content_type()
            if ctype not in ("text/html", "application/xhtml+xml", "text/plain"): raise ScanError(f"That address is not a web page (it returned {ctype}).")
            data = r.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES: raise ScanError("That page is too large to scan.")
            return data.decode(r.headers.get_content_charset() or "utf-8", "replace")
    except ScanError: raise
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400: raise ScanError(f"The site redirected the request ({e.code}), usually to a sign-in or cookie page. Kasauti only reads open pages. Paste the page text below instead.")
        raise ScanError(f"The site answered with an error ({e.code}). It may block automated tools. Paste the page text below instead.")
    except (urllib.error.URLError, OSError, ValueError): raise ScanError("Could not reach that page (it may be offline, slow or blocking automated tools). Try the sample page instead.")

def scan_html(html):
    text = html_to_text(html)[:20000]
    try: results = E.check(text, use_llm=False)[:60]
    except TypeError: results = E.check(text)[:60]   # an older engine.py without the use_llm option
    for r in results:
        a = E.q("select a.title from receipts r join assets a on a.id=r.asset_id where r.claim=? and a.status='approved'", (r["claim"],))
        r["approved_as"] = a[0]["title"] if a else None
    return {"chars": len(text), "results": results}

def scan_url(url): return scan_html(fetch(url))
