#!/usr/bin/env python3
"""Fact labels that show the source, AUTH-DATE:PAGE/PARA (ocr/method/FACT-LABELS-PROPOSAL-2026-10-15.md; the editor,
2026-10-15; 2026-10-17 23:3x, on the biographies still citing L-numbers; to the plan, and
).

    tools/fact-labels.py <stem> <tag>

A display layer: the readers keep citing L-numbers, the numbers of the frozen profile they read; this tool shows each
line by its label. The label: the work's siglum (since 2026-10-24 the signed sigla, profiles/SIGLA.tsv, with the place
within the work by profiles/SIGLA-PLACES.tsv, «AmEsp 1910.3», through tools/sigla.py, by the item key of the line's
locator; a work with no signed siglum gets no label, «?», and is listed with the rule's proposal for the editor's sign-off:
no code is coined here any more, the editor), the place
(the printed page, by the locator's «prese» and the page map, since 2026-10-25: see printed(); the ¶ or the line) and a letter, the line's order among all the lines of its dowse file at that
item and place, every person together (a, b, … z, aa, ab …). A copy («⟦kopio el X⟧») is found in the dowse file as its
original and so carries the original's label: one witness, visibly. The line is found in its dowse file by its anchor
and locator, else by the start of its fact; one found in neither (a line the dowse has since changed: the label is good
for one dowse, the editor, 2026-10-15) gets its place and «?».

Writes, in smelt/<stem>/: LABELS-<tag>.tsv (L, label, the dowse file); PROFILE-LABELLED-<tag>.md (the frozen profile,
each fact line headed «LABEL : L‹n› :»); and, where the biography exists, S4-LABELLED-<tag>.md (S4-VIEW-<tag>.md, or
the return, with every L-number written as its label, and «Referencoj» appended: each work code it cites with its full
entry, from OCR-ITEM-TABLE.tsv's citation). Derived copies, rewritten at each run. Ezri, 2026-10-17."""
import collections, csv, importlib.util, os, re, sys
import sigla
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
# THE PLACE OF PUBLICATION IN ESPERANTO (the editor, 2026-11-11, of «Progreso (Paris; la organo de Ido)»: «Parizo» expected: a place
# of publication in a citation is given in Esperanto unless it is part of a title, a general rule
# of the references, which the others follow): a reference entry's place, by smelt/LOKNOMOJ-REFERENCOJ.tsv (the
# gazetteer's forms), where it stands as a place («(Paris», «; Paris», «. Paris:»), never inside a title (*…*) or a link
_EO_PLACES = None


def eo_places(s):
    global _EO_PLACES
    if _EO_PLACES is None:
        p = os.path.join(G, "smelt", "LOKNOMOJ-REFERENCOJ.tsv")
        rows = [l.split("\t") for l in open(p, encoding="utf-8").read().split("\n")[1:] if l.strip()] if os.path.exists(p) else []
        _EO_PLACES = [(re.compile(rf"(?:(?<=\()|(?<=[.;,] )){re.escape(w)}(?=[;:,.)\s]|$)"), e) for w, e, *_ in sorted(rows, key=lambda r: -len(r[0]))]
    parts = re.split(r"(\*\*[^*\n]+\*\*|\*[^*\n]+\*|<[^>\n]+>|https?://\S+)", s or "")   # bold first, or its stars pair with an italic's
    for i in range(0, len(parts), 2):
        for rx, e in _EO_PLACES: parts[i] = rx.sub(e, parts[i])
    return "".join(parts)


LOC = re.compile(r"^\s*([\w.-]+), (?:PDF (\d+)(?: \(prese ([^)]*)\))?|¶ ?(\d+)|l\. ?(\d+)|p\. ?(\d+))")   # «p. N» (2026-11-10): a printed page with no scan, a web transcription of a printed journal (Cosmogl)   # «l. N»: a saved web page's line (2026-10-19)

# THE PRINTED PAGE, NEVER THE PDF PAGE (2026-10-25, the editor, on the sigla page
#). The place of a scanned page, in this order: the
# number the legilo read on the page («(prese 17)»); the page map (geniza/ocr/runs/OCR-PAGE-MAP.tsv, tools/ocr-page-
# sequence.py map): its number as read; «∴15», extrapolated (from the issue's or the volume's pagination, or by the legilo);
# «[15]», counted (an item that prints no numbers at all); the legilo's word for a page with no number («[kovrilo]», «[interna kovrilo]»); and only
# where none of these is to be had, «{14}» (was «[PDF 14]» to 2026-11-09). A paragraph of a typed text «¶12», a saved web page's line «l.40».
_MAP, _KEYITEM = None, None
MANKAS = "siglo mankas"   # a line whose source has no siglum yet (the editor, 2026-11-09)
NUM = re.compile(r"[0-9]+(?:[–-][0-9]+)?|[ivxlcdm]+|[IVXLCDM]+")

def _map():
    global _MAP, _KEYITEM
    if _MAP is None:
        import unicodedata
        _MAP = {}
        for r in csv.DictReader((x for x in open(os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
            if r.get("pdf_page", "").isdigit(): _MAP[(unicodedata.normalize("NFC", r["item"]), int(r["pdf_page"]))] = r
        _KEYITEM = {k: unicodedata.normalize("NFC", r["item"]) for k, r in sigla.table().items()}
    return _MAP

def printed(key, pdf, prese=None):
    """The place a label gives a scanned page: the printed page, as above."""
    # THE TWO INFERRED FORMS (2026-10-25; Miles: the editor's forms of 8 Oct keep «n (extrap. from iss.)» and «n
    # (counted)» apart, «counted» for items that print no numbers at all; the editor: «[15] for counted pages, ∴15 for
    # extrapolated»): a page map's «count» is «[15]»; its «iss» and «vol», and a number the legilo inferred, «∴15»
    w = (prese or "").strip()
    if NUM.fullmatch(w): return w
    r = _map().get((_KEYITEM.get(key, key), pdf))
    if r and NUM.fullmatch((r.get("printed") or "").strip()):
        n, src = r["printed"].strip(), r.get("source")
        if src == "read" and not w: return n
        # «≈15», not «∴15» (2026-10-27; the editor): «∴» is the
        # biographies' mark for «concluded from the lines», one sign with two meanings in the key; the page keeps «≈»
        return f"[{n}]" if src == "count" else f"≈{n}"
    m = re.fullmatch(r"\[(\d+)\]", w) or re.match(r"(\d+)\s*(?:\?|, kalkulita)", w)
    if m: return f"≈{m.group(1)}"
    if re.search(r"kovrilo|titolpaĝo|aldono", w): return f"[{w}]"
    return f"{{{pdf}}}"   # «{14}», the editor 2026-11-09

def work(key):
    """The label's head for an item key («AmEsp 1910.3»), the work's entry, and why there is none."""
    return sigla.head(key)

def rule(key):
    """The rule's siglum for a work with none, a proposal for SIGLA.tsv (tools/sigla-propose.py's rule)."""
    sp = importlib.util.spec_from_file_location("sigla_propose", os.path.join(ROOT, "tools", "sigla-propose.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m.rule(key)

def locator(l):
    """(item key, place) of a fact line's first locator field, or None; an old roster or fold line's locator by text
    file (`old_locator`) when no field has the item form."""
    for p in l.split(" · "):
        # AN ABSENCE OR A SWEEP (2026-11-10; the editor, on the Belga Sonorilo sweep: as with the absence sweeps
        # already ruled on, the source cited with no particular issue): «absence:SIGLA[,SIGLA] [extent]» or
        # «sweep:…», the sigla of the works searched and the extent searched (years), no page and no letter
        am = re.fullmatch(r"\s*(?:absence|sweep):([\w.,\-]+)(?:\s+(.+?))?\s*", p)
        if am: return "absence:" + am.group(1), (am.group(2) or "").strip()
        m = LOC.match(p)
        # «p. N» only after a key with a letter (2026-11-10: «1899, p. …» in a field of lesperantiste-dowse.md read as key «1899»)
        if m and m.group(6) and not re.search(r"[A-Za-z]", m.group(1)): m = None
        if m:
            if m.group(2): return m.group(1), printed(m.group(1), int(m.group(2)), m.group(3))
            if m.group(6): return m.group(1), m.group(6)
            return m.group(1), f"¶{m.group(4)}" if m.group(4) else f"l.{m.group(5)}"
    pl = path_locator(l)
    if pl: return pl
    o = old_locator(l)
    if o: return (o[0], printed(o[0], int(o[1])))
    b = bare_locator(l)
    if b: return b
    # A VOLUME WITH NO PAGE (2026-11-10; the editor to «BelgSon 1912v» for «belgasonorilo-1912», «la paĝo ne troviĝis»):
    # a field that is an item key alone, its work signed, labelled by the siglum and place only
    for p in l.split(" · ")[2:]:
        k = p.strip()
        if re.fullmatch(r"[A-Za-z][\w.\-]*", k) and len(k) > 6 and work(k)[0]: return "volume:" + k, ""
    return None

# THE FILE-PATH LOCATORS (2026-11-09; the hand dowses' «sources/<dir>/…/<file> l.N (…)», which held 13 labelled copies; the
# editor): an item's file (its stem in the item table, less «.embedded», «_djvu», «_text»; or its key form, lower case
# with «-», taken by a siglum's match) at its printed page: the parenthesis's «prese p. N», else the PDF page by the file's
# «=== page N ===» markers or form feeds, through printed(); a saved page that is no item, its stem as key, «l.N»; an item's
# file with no page to be had gives no locator, never «l.N» for a printed work (2026-10-25: always the printed page
# number), and its line stays «siglo mankas»
PATHLOC = re.compile(r"sources/(.+?\.(?:txt|wikitext|md|html?))\s+l\.\s?(\d+)(?:\s*\(([^)]*)\))?")

BARELOC = re.compile(r"(?<![/\w.-])([\w.-]+\.txt)\s+l\.\s?(\d+)")

def bare_locator(l):
    """A bare file name and line, «EsperantoTriumfonta.1921.064.embedded.txt l.146» (the late-periodicals lookup, 2026-09-14):
    the first in the line, read as a path locator with the file found by its stem; tried last, after the old locators."""
    m = BARELOC.search(l)
    if not m: return None
    name, n = m.group(1), int(m.group(2))
    hp = _hand_pages().get((name, n))
    if hp: return hp
    stem = name[:-4]; ss = (stem, re.sub(r"(?:\.embedded|_djvu|_text)$", "", stem))
    items = _items(); key = next((items[s] for s in ss if s in items), None)
    if key is None:
        for s in ss:
            kf = re.sub(r"[_. ]+", "-", s.lower())
            if any(rx.search(kf) and rules and sigla.place(kf, rules) for rx, _r, rules in sigla.load()): key = kf; break
    if key is None: return None
    pg = _page_of_line(stem, n)
    return (key, printed(key, pg)) if pg else None

_HP = None
def _hand_pages():
    """(file under sources/, line) -> (item key, place), from profiles/LOCATOR-PAGES.tsv: the printed pages found by hand
    for lines cited through a text file with no page markers."""
    global _HP
    if _HP is None:
        _HP, p = {}, os.path.join(G, "profiles", "LOCATOR-PAGES.tsv")
        for r in (csv.DictReader((x for x in open(p, encoding="utf-8") if not x.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE) if os.path.exists(p) else []):
            _HP[(r["file"], int(r["line"]))] = (r["key"], r["place"])
    return _HP

def path_locator(l):
    for (f, _n), v in _hand_pages().items():   # a line whose locator is prose, by its words (LOCATOR-PAGES «text:»)
        if f.startswith("text:") and f[5:] in l: return v
    for p in l.split(" · "):
        m = PATHLOC.search(p)
        if not m: continue
        path, n, par = m.group(1), int(m.group(2)), m.group(3) or ""
        hp = _hand_pages().get((path, n))
        if hp: return hp   # the page found by hand (profiles/LOCATOR-PAGES.tsv)
        stem = os.path.splitext(os.path.basename(path))[0]
        items, key = _items(), None
        ss = (stem, re.sub(r"(?:\.embedded|_djvu|_text)$", "", stem))
        key = next((items[s] for s in ss if s in items), None)
        if key is None:
            for s in ss:
                kf = re.sub(r"[_. ]+", "-", s.lower())
                if any(rx.search(kf) and rules and sigla.place(kf, rules) for rx, _r, rules in sigla.load()): key = kf; break
        pm = re.search(r"prese (?:p\. ?)?([0-9]+|[ivxlcdm]+)\b", par)
        if key is None:
            return stem, pm.group(1) if pm else f"l.{n}"   # a saved page; a printed book saved as text at its page
        if pm: return key, pm.group(1)
        pg = _page_of_line(stem, n, os.path.join(G, "sources", path))
        if pg: return key, printed(key, pg)
        if (sigla.table().get(key) or {}).get("origin", "").startswith("born-digital"): return key, f"l.{n}"   # a saved page with an item row
        if not path.endswith(".txt"): return key, f"l.{n}"   # a saved page (wikitext, html, md) a siglum's match takes
        return None
    return None

# THE OLD LINES' LOCATORS (2026-10-20, the editor; 100 of Beauchemin's 275 lines had no label
# in 19c, the old roster and fold lines, whose locators name a text file and a line or page, not an item): the text file's
# stem is an item of OCR-ITEM-TABLE.tsv («LEsperantiste.1901.7-8», «Lingvo Internacia 1901.3», «progreso7», «oge.3»), its
# key the work code's; the place, the PDF page: from the line number in the text file by its «=== page N ===» markers,
# else the page the locator writes («p.13», «scan p.26», «p342», «page-0026»).
_ITEMS, _TXT = None, None

def _items():
    global _ITEMS
    if _ITEMS is None:
        _ITEMS = {}
        for r in csv.DictReader((x for x in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
            if r.get("item") and r.get("key"): _ITEMS[r["item"].strip()] = r["key"].strip()
    return _ITEMS

def _txt(item):
    global _TXT
    if _TXT is None:
        _TXT = {}
        for root, _, fs in os.walk(os.path.join(G, "sources")):
            for f in fs:
                if f.endswith(".txt") and (f[:-4] not in _TXT or os.sep + "ocr" + os.sep in os.path.join(root, f).replace(os.path.join(G, "sources"), "")[:5]):
                    _TXT[f[:-4]] = os.path.join(root, f)   # sources/ocr/ first: the OCR the old runs read
    return _TXT.get(item)

_PAGES = {}
def _page_of_line(item, n, path=None):
    p = path if path and os.path.exists(path) else _txt(item)   # the file the locator names, if it names one (oge.3 in ocr-oge/)
    if not p: return None
    if p not in _PAGES:
        xs = open(p, encoding="utf-8", errors="replace").read().split("\n")
        _PAGES[p] = [int(m.group(1)) if (m := re.match(r"=== page (\d+) ===", x)) else None for x in xs]
        if not any(_PAGES[p]) and any("\f" in x for x in xs):   # a text with form feeds, one a page (pdftotext)
            pg, marks = 1, []
            for x in xs:
                marks.append(pg); pg += x.count("\f")
            _PAGES[p] = marks
    marks = _PAGES[p]
    if not any(marks) or n < 1 or n > len(marks): return None
    return next((m for m in reversed(marks[:n]) if m), None)

def old_locator(l):
    items = _items()
    ps = l.split(" · ")
    for p in ps[2:]:
        m = re.search(r"([A-Za-z][\w.\-]*?)(?:\.arb)?/page-(\d+)", p)
        if m and m.group(1) in items: return items[m.group(1)], str(int(m.group(2)))
        cands = re.findall(r"([A-Za-z][\w .\-]*?)\.(?:arb\.)?txt", p) + re.findall(r"\b([A-Za-z][A-Za-z]*\.?\d+(?:[.\-]\d+)*)\b", p)
        for c in cands:
            c = c.strip().split("/")[-1]
            words = c.split(" ")
            item = next((" ".join(words[i:]) for i in range(len(words)) if " ".join(words[i:]) in items), None)
            if not item: continue
            after = p[p.find(c) + len(c):]
            # the page the locator writes first (the line numbers are those of the OCR the old run read, which a later
            # OCR renumbers: Lingvo Internacia 1901.2 l.1778 is p.16 in sources/ocr/, p.31 by another copy's markers)
            pm = re.search(r"(?:scan |PDF )?\bp\.?\s?(\d+)", after)
            page = int(pm.group(1)) if pm else None
            if page is None:
                ln = re.match(r"(?:\.(?:arb\.)?txt)?(?:`)?\s*(?::|ll?\.\s?|L)(\d+)", after)
                pth = re.search(r"(sources/[^`\s:]+?\.txt)", p)
                page = _page_of_line(item, int(ln.group(1)), os.path.join(G, pth.group(1)) if pth else None) if ln else None
            if page is not None: return items[item], str(page)
    return None

def anchor(l):
    ps = l.split(" · ")
    return ps[3].strip() if len(ps) > 4 else ""

def fact(l):
    ps = l.split(" · ")
    return re.sub(r"^\*\*\([^)]*\)\*\* ", "", ps[2]).strip() if len(ps) > 4 else ""

def letters(n):
    s = ""
    while True:
        s = chr(97 + n % 26) + s; n = n // 26 - 1
        if n < 0: return s

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2: sys.exit(__doc__)
    stem, tag = args
    d = os.path.join(G, "smelt", stem)
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
    # THE SIGLA FIRST (2026-10-19, the editor
    # since
    # 2026-10-24 the signed sigla, never a code coined here): every item key the profile's lines name with no signed
    # siglum, or none its work's place rules match, is listed with the rule's siglum, for a row in SIGLA.tsv and the
    # editor's sign-off; its lines get «?» until then.
    if "--add-codes" in sys.argv:
        sys.exit("refused: --add-codes is retired (2026-10-24, the editor); "
                 "propose the work's row in profiles/SIGLA.tsv, check it with tools/sigla-propose.py, and have it signed")
    keys = sorted({locator(l)[0] for l in prof if l.startswith("- $$$") and locator(l)})
    missing = [(k, work(k)[2]) for k in keys if not k.startswith(("absence:", "volume:")) and not work(k)[0]]
    nolocs = [i for i, l in enumerate(prof, 1) if l.startswith("- $$$") and not locator(l)]
    if nolocs: print(f"{len(nolocs)} lines with no locator the tool reads, «siglo mankas» (mend each in its dowse file): "
                     + ", ".join(f"L{i}" for i in nolocs[:40]) + (" …" if len(nolocs) > 40 else ""))   # an absence's sigla are checked line by line
    if missing:
        print(f"{len(missing)} item keys with no label (a row for SIGLA.tsv or SIGLA-PLACES.tsv, then the editor's sign-off): "
              + "; ".join(f"{k} ({why}; the rule's siglum {rule(k)})" if why == "no siglum" else f"{k} ({why})" for k, why in missing))
    files, label, miss, nocode = {}, {}, [], {}
    unres_i = set()   # the lines with «siglo mankas» or a place with no letter, for LABELS-UNRESOLVED
    disp = {}         # L-number → the label as the biography's copy shows it, the letter as a subscript
    absent = {}       # L-number → the sigla of an absence line (2026-11-10)
    SIGNED = {r["siglum"]: r for r in sigla.rows(sigla.SIGLA) if r.get("status") == "signed"}
    for i, l in enumerate(prof, 1):
        if not l.startswith("- $$$"): continue
        fm = re.search(r"⟵ `([^`]+)`", l); loc = locator(l)
        if not fm or not loc: label[i] = (MANKAS, fm.group(1) if fm else ""); unres_i.add(i); continue
        f = fm.group(1)
        if f not in files:   # the dowse file: each line's (item, place) and its letter there, in the file's order
            seen, idx = {}, []
            for x in open(os.path.join(G, "profiles", "by-source", f), encoding="utf-8"):
                if not x.startswith("- $$$"): continue
                lx = locator(x)
                if not lx: continue
                n = seen.get(lx, 0); seen[lx] = n + 1
                idx.append((lx, anchor(x), fact(x)[:40], letters(n)))
            files[f] = idx
        if loc[0].startswith("volume:"):
            label[i] = (work(loc[0][7:])[0], f); unres_i.add(i); continue   # a difekto to remedy (the editor, 2026-11-10)
        if loc[0].startswith("absence:"):   # an absence: the sigla and the extent searched, no page, no letter (2026-11-10)
            sigs = loc[0][8:].split(","); bad = [s for s in sigs if s not in SIGNED]
            if bad: nocode[loc[0]] = "siglum " + ", ".join(bad) + " not signed"; label[i] = (MANKAS, f); unres_i.add(i); continue
            label[i] = (", ".join(sigs) + (", " + loc[1] if loc[1] else ""), f); absent[i] = sigs; continue
        code, _, why = work(loc[0])
        if not code: nocode[loc[0]] = why; label[i] = (MANKAS, f); unres_i.add(i); continue
        a, ft = anchor(l), fact(l)[:40]
        hit = next((x for x in files[f] if x[0] == loc and a and x[1] == a), None) \
              or next((x for x in files[f] if x[0] == loc and ft and x[2] == ft), None)
        if not hit: miss.append(i); unres_i.add(i)
        label[i] = (f"{code}:{loc[1]}{hit[3] if hit else ''}", f)
        if hit and hit[3]: disp[i] = f"{code}:{loc[1]}<sub>{hit[3]}</sub>"   # the copy's form, the letter apart
    with open(os.path.join(d, f"LABELS-{tag}.tsv"), "w", encoding="utf-8") as fh:
        fh.write("L\tlabel\tdowse file\n" + "".join(f"L{i}\t{lb}\t{f}\n" for i, (lb, f) in sorted(label.items())))
    out = [f"{label[i][0]} : L{i} : {l[2:]}" if i in label else l for i, l in enumerate(prof, 1)]
    head = (f"`[tools/fact-labels.py: PROFILE-FROZEN-{tag}.md, each fact line headed by its label and its L-number; the label "
            f"AUTH-DATE:PAGE/PARA and the line's letter on that page or paragraph of its dowse file, all persons together.]`")
    out.insert(1, "\n" + head)
    open(os.path.join(d, f"PROFILE-LABELLED-{tag}.md"), "w", encoding="utf-8").write("\n".join(out))
    print(f"{stem} {tag}: {len(label)} lines labelled; {len(miss)} found in no dowse line (place and «?»)"
          + (f"; no label for {', '.join(sorted(nocode))}" if nocode else ""))
    # THEN THE «?» LEFT, each with its reason, for resolving (2026-10-19): no locator the tool reads (an old roster or
    # fold line, a locator by file path); no work code; or the line not found in its dowse file by anchor or fact.
    unres = []
    for i, (lb, f) in sorted(label.items()):
        if i not in unres_i: continue
        l = prof[i - 1]; loc = locator(l)
        why = ("no locator of the form ‹item›, PDF N / ¶ N / l. N" if not loc else
               "DIFEKTO por estonta riparo: volumo sen paĝo (la paĝo ne troviĝis); trovu la paĝon kaj skribu ĝin en la dowse" if loc[0].startswith("volume:") else
               f"no label: {nocode[loc[0]]}" if loc[0] in nocode else "not found in its dowse file by anchor or by fact")
        unres.append(f"- L{i} · {f} · {why} · `{l[2:160]}`")
    up = os.path.join(d, f"LABELS-UNRESOLVED-{tag}.md")
    open(up, "w", encoding="utf-8").write(
        f"# The «?» labels left, {stem} {tag}\n\n`[tools/fact-labels.py, after the codes: each line whose label ends in «?», "
        f"with the reason. {len(unres)} of {len(label)}.]`\n\n" + "\n".join(unres) + "\n")
    print(f"  {os.path.basename(up)}: {len(unres)} «?» left")
    bio = next((os.path.join(d, f) for f in (f"S4-VIEW-{tag}.md", f"S4-RETURN-{tag}.md") if os.path.exists(os.path.join(d, f))), None)
    if not bio: return
    txt = open(bio, encoding="utf-8").read()
    # NO LABELLED COPY WITH A SOURCE THAT HAS NO SIGNED SIGLUM (2026-11-09; the editor: a «?» for a reference with no siglum yet
    # must never happen: no siglum is used before it is signed, and no «?»
    # should have reached the biographies): where the biography cites a line labelled «siglo mankas», the
    # labelled copy is not written; in its place a notice in Esperanto naming each such line's source, for a siglum to be
    # proposed in profiles/SIGLA.tsv and signed; the run says so and exits non-zero
    # only the lines the biography itself cites, its part 1, not those its report names in parts 2-4, the lines not used
    # and the difektoj (2026-11-10, De Beaufront's L10137, our own remark in the Schuck roster, named in part 2 as not used
    # and in part 4 as a line with no siglum; the editor): the hold would be circular
    cited = re.split(r"(?m)^## 2\. ", txt, maxsplit=1)[0]
    held = sorted(i for i, (lb, _) in label.items() if lb == MANKAS and re.search(rf"\bL{i}\b", cited))
    if held:
        lp = os.path.join(d, f"S4-LABELLED-{tag}.md")
        srcs = collections.Counter(label[i][1] for i in held)
        open(lp, "w", encoding="utf-8").write(
            f"# Tenita: la etikedita kopio de {stem} ({tag})\n\n`[tools/fact-labels.py: ne skribita, ĉar la biografio citas "
            f"{len(held)} liniojn, kies fonto ankoraŭ ne havas subskribitan siglon; ili estas en LABELS-UNRESOLVED-{tag}.md. "
            f"Unue la sigloj proponitaj en profiles/SIGLA.tsv kaj subskribitaj, poste denove smelt-s4-view.py --replace.]`\n\n"
            + "\n".join(f"- `{f}`: {n} linioj (" + ", ".join(f"L{i}" for i in held if label[i][1] == f) + ")" for f, n in srcs.most_common()) + "\n")
        print(f"  HELD: S4-LABELLED-{tag}.md not written: {len(held)} cited lines whose source has no signed siglum: "
              + "; ".join(f"{f} {n}" for f, n in srcs.most_common()))
        sys.exit(3)
    txt = re.sub(r"\bL(\d+)\b", lambda m: disp.get(int(m.group(1))) or label.get(int(m.group(1)), (m.group(0),))[0], txt)
    # the works cited: the heads of the labels the biography now shows («AmEsp 1910.3», «Joss1998»), each with its item key
    keys = {}
    for i, (lb, f) in label.items():
        loc = locator(prof[i - 1])
        if i in absent: continue
        if loc and lb != MANKAS and (disp.get(i) or lb) in txt: keys.setdefault(lb.rsplit(":", 1)[0], loc[0])
    cited = sorted(keys, key=lambda c: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", c)])   # 1906.2 before 1906.10
    rows = {}
    for r in csv.DictReader((x for x in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
        for k in {r.get("item", ""), (r.get("key") or "").strip()} - {""}: rows[k] = r
    # the key: one definition a paragraph, the term in bold, flush left, not a list, so that it stays apart from the references'
    # own list (the editor, 2026-10-25 11:4x, via Miles; 2026-11-11: the key to reading the references, and the references,
    # not one bulleted list; the key's entries flush left; the PDF sets it small)
    ref = ["", "## Referencoj", "",
           "Kiel legi la ŝlosilojn (la litero validas por unu fakt-eltirado; la siglo por ĉiam):", "",
           "**Korĵ2005:120<sub>a</sub>**: la verko Korĵ2005 (sube), ĝia presita paĝo 120, kaj la unua linio de la fakt-eltirado sur ĝi (a, b, c … "
           "laŭ ilia ordo, ĉiuj personoj kune).", "",
           "**AmEsp 1910.3:14<sub>a</sub>**: ĉe gazeto la jaro kaj la numero post la siglo: *Amerika Esperantisto*, 1910, n-ro 3, "
           "presita paĝo 14, la unua linio.", "",
           "**≈15**: paĝo, kies numero ne legeblas; la numero eltirita el la paĝigo de la numero aŭ de la volumo.", "",
           "**[15]**: paĝo de verko, kiu presas neniujn numerojn, nombrita.", "",
           "**[kovrilo]**: la kovrilo.", "",
           "**{14}**: la 14-a paĝo de la skanaĵo, ne presita numero.", "",
           "**¶12**: alineo de tajpita teksto.", "",
           "**l.40**: linio de konservita retpaĝo.", "",
           "**siglo mankas**: la fonto de la linio ankoraŭ ne havas siglon.", "",
           "**Korĵ2005:120** sen litero: la linio ne plu troviĝas en la fakt-eltirado en tiu formo.", "",
           "**‹ligilo›** post verko: la citita numero rete, kie ĝi estas rete.", ""]
    def one(c):
        k = keys[c]; r = rows.get(k, {})
        _, entry, _w = work(k)
        cit = (r.get("citation") or "").strip()
        if not cit:
            cit = render(entry, k, c, r) if entry else (f"*{r['title']}* {r.get('year', '')}" + (f", n-ro {r['label_as_filed']}" if r.get("label_as_filed") else "") + "." if r.get("title") else "")
        cit = eo_places(cit)
        u = sigla.online(k)   # the item's online location (2026-10-25, the editor)
        return (cit or k) + (f" <{sigla.href(u)}>" if u else "")
    # ONE SIGLUM, ONE ENTRY (2026-11-09 23:5x, the editor: in the references the links may be a nested list under the
    # journal, the journal itself one siglum): a siglum cited at places («AmEsp 1910.3», «EoWikip Laurén») is
    # listed once with its entry, its places nested under it, each with its citation and link; a book with no place as before
    groups = {}
    for c in cited:
        sig, _, place = c.partition(" ")
        groups.setdefault(sig, []).append((place, c))
    for i, sigs in absent.items():   # an absence's sigla, each listed once with its entry
        if label[i][0] in txt:
            for s in sigs: groups.setdefault(s, [("", None)])
    for sig, ps in groups.items():
        if ps == [("", None)]:
            ref.append(f"- **{sig}**: {SIGNED[sig].get('entry', sig)}"); continue
        if len(ps) == 1 and not ps[0][0]:
            ref.append(f"- **{sig}**: {one(ps[0][1])}"); continue
        ref.append(f"- **{sig}**: {work(keys[ps[0][1]])[1] or sig}")
        for place, c in ps:
            k = keys[c]; own = (rows.get(k, {}).get("citation") or "").strip(); u = sigla.online(k)
            ref.append(f"  - **{place or c}**" + (f": {own}" if own else "") + (f" <{sigla.href(u)}>" if u else ""))
    ref = [eo_places(l) for l in ref]   # every entry's place of publication in Esperanto, whatever path made the entry
    # OUR OWN DOCUMENTS BY TITLE (the editor, 2026-11-11: our own documents, several sigla in a row, need
    # their titles given, the sigla alone being opaque): each GZ-‹code› entry its document's title, smelt/GZ-TITOLOJ.tsv
    gz = os.path.join(G, "smelt", "GZ-TITOLOJ.tsv")
    if os.path.exists(gz):
        tt = {r[0]: r[1] for r in (l.split("\t") for l in open(gz, encoding="utf-8").read().split("\n")[1:] if l.strip())}
        ref = [re.sub(r"^(- \*\*(GZ-\w+)\*\*: )la laboraj dokumentoj de La Genizo \(GZ: niaj propraj, ne fonto\)",
                      lambda m: m.group(1) + (re.sub(r"^(.*?)(?:, (\d{4}-\d\d-\d\d))?$", lambda k: f"«{k.group(1)}»" + (f", {k.group(2)}" if k.group(2) else ""), tt[m.group(2)])
                                              + ", laboraĵo de La Genizo (nia propra dokumento, ne fonto)" if m.group(2) in tt else m.group(0)[len(m.group(1)):]), l)
               for l in ref]
    # A LIST'S LABELS GROUPED BY WORK (Fable's proposal 10; the editor, 2026-10-30), after «Referencoj» has
    # found its works: «[LEsp 1901.6:225a, LEsp 1902.2:19b, LInt 1902.1:40a]» → «[LEsp 1901.6:225a, 1902.2:19b; LInt
    # 1902.1:40a]», the siglum once for a run of its labels
    import smelt_inputs as SI
    # THE ORDER AND THE RUNS (the editor, 2026-11-11: citations by year, then within a year
    # by siglum; a semicolon parts the runs of sigla; within a siglum only volume and page, a repeated volume still printed;
    # so «X Y:Z;X Y:W; A B:C» becomes «X Y:Z, Y:W; A B:C», and «X:Y; X: Z; A: B» becomes «X: Y, Z; A; B»): the labels of one bracket, however the writer
    # separated them, sorted by the year of their item (the item table's, else a year in the siglum, else last), then by siglum,
    # then by their place in the work; a label twice once; each run of one siglum its first label whole, the rest without the
    # siglum («OGE 1:182o, 1:183d»; «UnivKong4:≈30m, 31j»), the runs joined by «; »
    def year_of(x):
        """the item table's year of the label's item; else a year in the label's head («Joss1998», «AmEsp 1908.3»); else one in
        the item's key («annuaire-1901»); else last"""
        head = re.sub(r"<[^>]+>", "", x).rsplit(":", 1)[0]
        k = keys.get(head, "")
        entry = (SI.siglum_of(x) or ("", ""))[1] or ""   # last, the siglum's entry («… Annuaire …, 1901»)
        # a volume with no year in the table («Progr 3»): the earliest year of the profile's lines it labels (a periodical's
        # lines dated by its issues), before the item's key and the siglum's entry («Progreso … 1908–» would date every volume 1908)
        for s in ((rows.get(k, {}).get("year") or "").strip(), head, str(head_year.get(head, "")), k, entry):
            m = re.search(r"(1[5-9]\d\d|20[0-2]\d)", s)
            if m: return int(m.group(1))
        return 9999
    # the place in the work, compared as numbers, the marks of a guessed or counted page («≈», «{}», «[]») set aside
    nat = lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", re.sub(r"<[^>]+>|[≈{}\[\]]", "", s))]
    head_year = {}
    for i, (lb, f) in label.items():
        dm = re.search(r"\*\*(?:[^*\d]*)(1[5-9]\d\d|20[0-2]\d)", prof[i - 1]) if 0 < i <= len(prof) else None
        if dm: h = lb.rsplit(":", 1)[0]; head_year[h] = min(head_year.get(h, 9999), int(dm.group(1)))
    def place_key(rest):
        """a label's place, its volume first, then a roman-numbered page (front matter, «3:IV») before the numbered ones (the
        editor, 2026-11-11, to)"""
        r = re.sub(r"<sub>[^<]*</sub>|<[^>]+>", "", rest)   # the line's letter off, so that «IV<sub>n</sub>» reads «IV»
        before, colon, page = r.rpartition(":")
        if not colon: return (nat(r), 1, [])
        rm = re.match(r"([IVXLCivxlc]+)(?![A-Za-z])", page)
        return (nat(before), 0 if rm else 1, nat(page))
    def unit(x, s):
        """what a run shares: the siglum where a space parts it from its place («OGE 1:182» → «OGE»: «1:183» repeats the
        volume); else all before the page («UnivKong4:≈30», «Adr:¶189»: the rest only the page)"""
        return s if x[len(s):].startswith(" ") else x.rsplit(":", 1)[0]
    def group(m):
        items = re.split(r"[;,] ", m.group(1))
        sig = [SI.siglum_of(x) for x in items]
        # only a list of labels, every item one; any other bracket as written
        if not all(sig): return m.group(0)
        seen, rows_ = set(), []
        for x, s in zip(items, sig):
            if x in seen: continue
            u = unit(x, s[0])
            seen.add(x); rows_.append((year_of(x), u, place_key(x[len(u):]), x))
        rows_.sort(key=lambda t: t[:3])
        out, last = [], None
        for _, s, _, x in rows_:
            if s == last:
                rest = x[len(s):]
                out[-1] += ", " + (rest[1:] if rest[:1] in (" ", ":") else rest); continue
            out.append(x); last = s
        return "[" + "; ".join(out) + "]"
    # a label may hold brackets of its own («LEsp 1912.1:[interna kovrilo]ah», «[15]»): the list's brackets matched around them,
    # else the whole list stayed ungrouped (the editor, 2026-11-11, of Beauchemin's 31-label list: citations side by side
    # usually drop the repeated siglum, and here they had not)
    txt = re.sub(r"\[((?:[^\[\]\n]|\[[^\[\]\n]*\])+)\]", group, txt)
    lp = os.path.join(d, f"S4-LABELLED-{tag}.md")
    # the references follow the biography (part (1)), before the report's parts (2)–(4) (the editor, 2026-10-20
    # they stood at the very end, after the report)
    m = re.search(r"^## 2\.", txt, re.M)
    body = (txt[:m.start()].rstrip() + "\n" + "\n".join(ref) + "\n\n" + txt[m.start():].rstrip()) if m else (txt.rstrip() + "\n" + "\n".join(ref))
    open(lp, "w", encoding="utf-8").write(
        # in Esperanto, as the copy is (the editor, 2026-11-09: the tool notes at the head of each copy, approved)
        f"`[tools/fact-labels.py: {os.path.basename(bio)}, ĉiu L-numero skribita kiel ĝia fakta etikedo (LABELS-{tag}.tsv); la "
        f"listo laŭ etikedo: PROFILE-LABELLED-{tag}.md.]`\n\n" + body + "\n")
    print(f"  {os.path.basename(lp)}: {len(cited)} works cited")

def render(entry, key, code, row):
    """A work code's entry in WORK-CODES.tsv written as a citation of this item: the notes on how the code is made («the date
    of the issue as the code», «the year and the issue as the code» …) replaced by the item's own date, year or number
    (2026-10-20: «*Amerika Esperantisto* 1907. West Newton), the year and the issue as the code.» in Beauchemin's references)."""
    date = re.search(r"(1[89]\d\d|20\d\d)-(\d\d)-(\d\d)", key)
    year = re.search(r"(1[89]\d\d|20\d\d)", key)
    num = (row.get("label_as_filed") or "").strip() or (re.search(r"(\d+)\D*$", code).group(1) if re.search(r"\d", code) else "")
    e = re.sub(r"\b1[89]xx, ", "", entry)
    e = re.sub(r",? ?the piece as the code", f", {num}", e)
    e = re.sub(r",? ?the year and the issue as the code", f", {year.group(1) if year else ''}, n-ro {num}", e)
    e = re.sub(r",? ?the date of the issue as the code", f", {date.group(0) if date else ''}", e)
    e = re.sub(r",? ?the year as the code", f", {year.group(1) if year else ''}", e)
    e = re.sub(r",? ?the (?:number|issue) as the code", f", n-ro {num}", e)
    e = re.sub(r",? ?the volume as the code", f", vol. {num}", e)
    e = re.sub(r" ?\(its number in the code\)", f" n-ro {num}", e)
    # the sigla's entries (2026-10-24): how the label writes the place, which the label itself now shows
    e = re.sub(r",? ?(?:the year and the (?:issue|number)|the issue's date(?: as the place)?|the (?:number|volume|year) as the place|"
               r"the year|the date of the issue)(?=[;.,]|$)", "", e)
    e = re.sub(r",? ?the (?:article|page|file page|memorial|game)[^;.,]* in the label", "", e)
    return re.sub(r",\s*,", ",", e).strip()

if __name__ == "__main__":
    main()
