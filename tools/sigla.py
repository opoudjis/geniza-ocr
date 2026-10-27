"""The sigla: the register (profiles/SIGLA.tsv) and the place rules (profiles/SIGLA-PLACES.tsv), read for
tools/fact-labels.py and tools/sigla-propose.py (2026-10-24; the editor).

    head(key) -> (the label's head, «AmEsp 1910.3»; the work's entry; why there is none)"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SIGLA, PLACES = os.path.join(G, "profiles", "SIGLA.tsv"), os.path.join(G, "profiles", "SIGLA-PLACES.tsv")
ORD = {w: i for i, w in enumerate(["unua", "dua", "tria", "kvara", "kvina", "sesa", "sepa", "oka", "naŭa", "deka"], 1)}

def rows(path):
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8") if not l.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]

_S = None
def load():
    """[(match, row, [(pattern, template)])], every row of the register with its place rules, signed or not."""
    global _S
    if _S is None:
        pl = {}
        for r in rows(PLACES): pl.setdefault(r["siglum"], []).append((re.compile(r["pattern"]), r["template"]))
        _S = [(re.compile(r["match"]), r, pl.get(r["siglum"], [])) for r in rows(SIGLA)]
    return _S

def helpers(s):
    s = re.sub(r"\{int:0*(\d+)\}", r"\1", s)
    s = re.sub(r"\{ord:([^}]*)\}", lambda m: str(ORD.get(m.group(1), m.group(1))), s)
    s = re.sub(r"\{up:([^}]*)\}", lambda m: m.group(1).upper(), s)
    return re.sub(r"\{cap:([^}]*)\}", lambda m: "-".join(w.capitalize() for w in m.group(1).split("-")), s)

def place(key, rules):
    """The place a work's rules give a key: (text, joined), or None where the work has rules and none matches."""
    if not rules: return ("", False)
    for rx, t in rules:
        m = rx.search(key)
        if m:
            p = helpers(m.expand(t))
            return (p[1:], True) if p.startswith("~") else (p, False)
    return None

def head(key):
    for rx, r, rules in load():
        if not rx.search(key): continue
        if r.get("status") != "signed": return None, r.get("entry", ""), f"siglum {r['siglum']} not signed"
        p = place(key, rules)
        if p is None: return None, r.get("entry", ""), f"no place rule of {r['siglum']} matches"
        txt, joined = p
        return r["siglum"] + (txt if joined else (" " + txt if txt else "")), r.get("entry", ""), ""
    return None, "", "no siglum"

# THE ONLINE LOCATION (2026-10-25, the editor
#): from the item table's «origin» (OCR-ITEM-TABLE.tsv): the URL it gives (archive.org, BitArkivo); an
# ANNO title code, as ANNO's page of that title and year; a born-digital text, its source page's address (born_digital_url). None
# where the origin records no location (the ÖNB issues the editor downloaded one by one).
_T = None
def table():
    """item key -> its row of the item table (keys NFC: the congress books' items are NFD)."""
    global _T
    if _T is None:
        import unicodedata
        _T = {}
        for r in rows(os.path.join(G, "OCR-ITEM-TABLE.tsv")):
            if r.get("key"): _T[unicodedata.normalize("NFC", r["key"].strip())] = r
    return _T

def href(u):
    """A URL as a link target: spaces, brackets and quotes percent-encoded, the rest kept (the editor, 2026-10-25, on
    Drezen 1931's temerov link; Markdown ends a link at a space or a bracket)."""
    from urllib.parse import quote
    return quote(u, safe=":/?&=%#~+@!$,;'*-._")

_WD = None
def web_downloads():
    """file stem (NFC), and its key form (lower case, «_» and «.» as «-»), -> the first URL of its note in
    sources/_WEB-DOWNLOADS.tsv (a bare «domain/path» given https://)."""
    global _WD
    if _WD is None:
        import unicodedata
        _WD = {}
        url = re.compile(r"(?:https?://|\b(?=[a-z0-9.-]+\.[a-z]{2,}/))[^\s»«,;)>\]`]+")
        for l in open(os.path.join(G, "sources", "_WEB-DOWNLOADS.tsv"), encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) < 4 or f[0] == "path": continue
            m = url.search(f[3])
            if not m: continue
            u = m.group(0).rstrip(".")
            if not u.startswith("http"): u = "https://" + u
            stem = unicodedata.normalize("NFC", os.path.splitext(os.path.basename(f[0]))[0])
            for s in (stem, re.sub(r"[_.]", "-", stem.lower())): _WD.setdefault(s, u)
    return _WD

_FILES = None
def saved_url(key):
    """The first URL in the first ten lines of a saved note named by the key under sources/web-*/ (the pasted BAnQ and
    FamilySearch notes give theirs on line 5 or 7), or None."""
    global _FILES
    if _FILES is None:
        _FILES = {}
        for d in os.listdir(os.path.join(G, "sources")):
            p = os.path.join(G, "sources", d)
            if d.startswith("web-") and os.path.isdir(p):
                for f in os.listdir(p):
                    if f.endswith((".md", ".txt")): _FILES.setdefault(os.path.splitext(f)[0], os.path.join(p, f))
    p = _FILES.get(key)
    if not p: return None
    for i, x in enumerate(open(p, encoding="utf-8", errors="replace")):
        m = re.search(r"https?://[^\s»«,;)>\]`]+", x)
        if m: return m.group(0).rstrip(".")
        if i >= 9: return None

_LOC, _WORKS = None, None
def registers():
    """(item key -> URL, from the generated profiles/ONLINE-LOCATIONS.tsv; siglum -> [(match, url, where)], from the hand
    profiles/SIGLA-ONLINE.tsv), each empty where its file is missing."""
    global _LOC, _WORKS
    if _LOC is None:
        import unicodedata
        p = os.path.join(G, "profiles", "ONLINE-LOCATIONS.tsv")
        _LOC = {unicodedata.normalize("NFC", r["key"]): r["url"] for r in rows(p)} if os.path.exists(p) else {}
        _WORKS = {}
        p = os.path.join(G, "profiles", "SIGLA-ONLINE.tsv")
        for r in (rows(p) if os.path.exists(p) else []):
            _WORKS.setdefault(r["siglum"], []).append((r.get("match", ""), r["url"], r.get("where", "")))
    return _LOC, _WORKS

def online(key, sig=None):
    """The item's own online location, or None: the generated register; a work row of SIGLA-ONLINE.tsv for the item
    (its pattern matching the key, or the whole work's row where it has a {year} to fill); the item table's origin.
    SIG, the item's siglum where the caller knows it."""
    import unicodedata
    loc, works = registers()
    k = unicodedata.normalize("NFC", key)
    if k in loc: return loc[k]
    r = table().get(k)
    if sig is None: sig = next((row["siglum"] for rx, row, _ in load() if rx.search(k)), None)
    own = [(m, u) for m, u, _w in works.get(sig, []) if u.startswith("http")]   # «vidu:X» is the page's cross-reference only
    for m, u in own:
        if m and re.search(m, k): return u
    for m, u in own:
        if not m and "{year}" in u and r and r.get("year"): return u.replace("{year}", r["year"])
    for m, u in own:
        if not m and "{year}" not in u: return u   # the whole work's one location (a book, a site)
    if not r: return web_downloads().get(k) or saved_url(k)   # a saved page with no item row (the Beauchemin web sources)
    o = r.get("origin", "")
    m = re.search(r"https?://[^\s»«,;)]+", o)
    if m: return m.group(0).rstrip(".")
    m = re.search(r"ANNO, title code (\w+)", o)
    if m: return f"https://anno.onb.ac.at/cgi-content/anno-plus?aid={m.group(1)}" + (f"&datum={r['year']}" if r.get("year") else "")
    # A BORN-DIGITAL TEXT (2026-10-25; the editor
    #): never the first URL inside the text, which is one of its references; its source page, from the
    # born-digital spec (ocr/method/born-digital-spec-*.tsv, the «source» column), and that page's own address: its
    # note in sources/_WEB-DOWNLOADS.tsv, else its <link rel="canonical"> or og:url
    if o.startswith("born-digital"): return born_digital_url(r["item"])
    return None

_SPEC = None
def born_digital_url(item):
    global _SPEC
    if _SPEC is None:
        import glob
        _SPEC = {}
        for sp in sorted(glob.glob(os.path.join(G, "ocr", "method", "born-digital-spec-*.tsv"))):
            for l in open(sp, encoding="utf-8"):
                f = l.rstrip("\n").split("\t")
                if len(f) > 1 and not l.startswith("#"): _SPEC[f[0]] = f[1].split("#")[0]   # the later spec holds
    src = _SPEC.get(item)
    if not src: return None
    p = os.path.join(ROOT, src) if src.startswith("published/") else os.path.join(G, src)
    stem = os.path.splitext(os.path.basename(p))[0]
    import unicodedata
    u = web_downloads().get(unicodedata.normalize("NFC", stem))
    if u: return u
    if os.path.isfile(p) and p.endswith(".txt"):   # our transcription of a record: its header line names the record
        first = open(p, encoding="utf-8", errors="replace").readline()
        if first.startswith("[Transcription"):
            m = re.search(r"https?://[^\s»«,;)>\]]+", first)
            if m: return m.group(0).rstrip(".")
        return None
    if os.path.isfile(p) and p.endswith((".html", ".htm")):
        t = open(p, encoding="utf-8", errors="replace").read(200000)
        m = (re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', t, re.I)
             or re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical', t, re.I)
             or re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)', t, re.I))
        if m and m.group(1).startswith("http"): return m.group(1)
    return None

def work_online(rx, siglum=None):
    """A work's online locations: the whole work's rows of SIGLA-ONLINE.tsv first (an ANNO title without its year), then
    from its items' (the keys its «match» takes), [(where, URL, items)]: one link a holder not already given, BitArkivo's
    folder, archive.org's search on the items' common name (the item's own page when one)."""
    from collections import defaultdict
    _, works = registers()
    out, hosts = [], set()
    for m, u, w in works.get(siglum, []):
        if m: continue
        if u.startswith("vidu:"):   # a cross-reference to another siglum's location (the editor)
            t = next((x for mm, x, _ in works.get(u[5:], []) if not mm and x.startswith("http")), "")
            out.append((w, t, 0)); continue
        u = re.sub(r"[&?]datum=\{year\}", "", u)
        out.append((w, u, 0)); hosts.add(re.sub(r"^https?://(?:www\.)?([^/]+).*", r"\1", u))
    by = defaultdict(list)
    for k in table():
        if rx.search(k):
            u = online(k, siglum or "")
            if u: by[re.sub(r"^https?://(?:www\.)?([^/]+).*", r"\1", u)].append(u)   # one site with or without «www.»
    for h in hosts: by.pop(h, None)
    for host, us in sorted(by.items()):
        if host == "data.onb.ac.at":
            out.append(("ÖNB", us[0], len(us)) if len(us) == 1 else ("ÖNB, ĉiu volumo aparte", us[0], len(us)))
        elif host == "anno.onb.ac.at":
            codes = sorted({re.search(r"aid=(\w+)", u).group(1) for u in us})
            out += [("ANNO (ÖNB)", f"https://anno.onb.ac.at/cgi-content/anno-plus?aid={c}", sum(1 for u in us if f"aid={c}" in u)) for c in codes]
        elif host == "archive.org" and len(us) > 1:
            ids = [u.rstrip("/").split("/")[-1] for u in us]
            pre = os.path.commonprefix(ids)
            pre = re.sub(r"[^A-Za-z]*$", "", pre) or pre
            out.append(("archive.org", f"https://archive.org/search?query=identifier%3A{pre}%2A", len(us)) if len(pre) >= 4
                       else ("archive.org", us[0], len(us)))
        elif len(us) > 1:
            out.append((host, os.path.commonprefix(us).rsplit("/", 1)[0] + "/", len(us)))
        else:
            out.append((host, us[0], 1))
    return out
