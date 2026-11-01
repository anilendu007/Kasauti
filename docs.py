"""Read text from an uploaded document: .txt, .md, .docx (standard library) and .pdf (needs the optional pypdf package)."""
import io, zipfile
import xml.etree.ElementTree as ET
MAX_BYTES = 5_000_000
class DocError(Exception): pass

def extract_text(name, data):
    ext = (name or "").lower().rsplit(".", 1)[-1]
    if len(data) > MAX_BYTES: raise DocError("That file is larger than 5 MB.")
    if ext in ("txt", "md"): return data.decode("utf-8", "replace")
    if ext == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if z.getinfo("word/document.xml").file_size > 20_000_000: raise DocError("That document is too large to read.")
                root = ET.fromstring(z.read("word/document.xml"))
        except DocError: raise
        except Exception: raise DocError("That does not look like a valid .docx file.")
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paras = ["".join(t.text or "" for t in p.iter(ns + "t")) for p in root.iter(ns + "p")]
        return "\n".join(x for x in paras if x.strip())
    if ext == "pdf":
        try: from pypdf import PdfReader
        except ImportError: raise DocError("PDF reading is not installed on this server. Save the text as .txt or .docx, or paste it.")
        try: return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:30])
        except Exception: raise DocError("That PDF could not be read (it may be scanned or protected).")
    raise DocError("Upload a .txt, .md, .docx or .pdf file.")
