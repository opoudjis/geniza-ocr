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
import csv, importlib.util, os, re, sys
import sigla
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
LOC = re.compile(r"^\s*([A-Za-z0-9._-]+), (?:PDF (\d+)(?: \(prese ([^)]*)\))?|¶ ?(\d+)|l\. ?(\d+))")   # «l. N»: a saved web page's line (2026-10-19)

# THE PRINTED PAGE, NEVER THE PDF PAGE (2026-10-25, the editor, on the sigla page
#). The place of a scanned page, in this order: the
# number the legilo read on the page («(prese 17)»); the page map (geniza/ocr/runs/OCR-PAGE-MAP.tsv, tools/ocr-page-
# sequence.py map): its number as read; «∴15», extrapolated (from the issue's or the volume's pagination, or by the legilo);
# «[15]», counted (an item that prints no numbers at all); the legilo's word for a page with no number («[kovrilo]», «[interna kovrilo]»); and only
# where none of these is to be had, «[PDF 14]». A paragraph of a typed text «¶12», a saved web page's line «l.40».
_MAP, _KEYITEM = None, None
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
        return f"[{n}]" if src == "count" else f"∴{n}"
    m = re.fullmatch(r"\[(\d+)\]", w) or re.match(r"(\d+)\s*(?:\?|, kalkulita)", w)
    if m: return f"∴{m.group(1)}"
    if re.search(r"kovrilo|titolpaĝo|aldono", w): return f"[{w}]"
    return f"[PDF {pdf}]"

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
        m = LOC.match(p)
        if m:
            if m.group(2): return m.group(1), printed(m.group(1), int(m.group(2)), m.group(3))
            return m.group(1), f"¶{m.group(4)}" if m.group(4) else f"l.{m.group(5)}"
    o = old_locator(l)
    return (o[0], printed(o[0], int(o[1]))) if o else None

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
        _PAGES[p] = [int(m.group(1)) if (m := re.match(r"=== page (\d+) ===", x)) else None for x in open(p, encoding="utf-8", errors="replace")]
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
    missing = [(k, work(k)[2]) for k in keys if not work(k)[0]]
    if missing:
        print(f"{len(missing)} item keys with no label (a row for SIGLA.tsv or SIGLA-PLACES.tsv, then the editor's sign-off): "
              + "; ".join(f"{k} ({why}; the rule's siglum {rule(k)})" if why == "no siglum" else f"{k} ({why})" for k, why in missing))
    files, label, miss, nocode = {}, {}, [], {}
    for i, l in enumerate(prof, 1):
        if not l.startswith("- $$$"): continue
        fm = re.search(r"⟵ `([^`]+)`", l); loc = locator(l)
        if not fm or not loc: label[i] = ("?", fm.group(1) if fm else ""); continue
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
        code, _, why = work(loc[0])
        if not code: nocode[loc[0]] = why; label[i] = (f"{loc[0]}:{loc[1]}?", f); continue
        a, ft = anchor(l), fact(l)[:40]
        hit = next((x for x in files[f] if x[0] == loc and a and x[1] == a), None) \
              or next((x for x in files[f] if x[0] == loc and ft and x[2] == ft), None)
        if not hit: miss.append(i)
        label[i] = (f"{code}:{loc[1]}{hit[3] if hit else '?'}", f)
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
        if not lb.endswith("?"): continue
        l = prof[i - 1]; loc = locator(l)
        why = ("no locator of the form ‹item›, PDF N / ¶ N / l. N" if not loc else
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
    txt = re.sub(r"\bL(\d+)\b", lambda m: label.get(int(m.group(1)), (m.group(0),))[0], txt)
    # the works cited: the heads of the labels the biography now shows («AmEsp 1910.3», «Joss98»), each with its item key
    keys = {}
    for i, (lb, f) in label.items():
        loc = locator(prof[i - 1])
        if loc and not lb.endswith("?") and lb in txt: keys.setdefault(lb.rsplit(":", 1)[0], loc[0])
    cited = sorted(keys, key=lambda c: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", c)])   # 1906.2 before 1906.10
    rows = {}
    for r in csv.DictReader((x for x in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
        for k in {r.get("item", ""), (r.get("key") or "").strip()} - {""}: rows[k] = r
    ref = ["", "## Referencoj", "",
           # one definition a line, the term in bold (the editor, 2026-10-25 11:4x, via Miles)
           "Kiel legi la ŝlosilojn (la litero validas por unu dowse; la siglo por ĉiam):", "",
           "- **Korĵ05:120a**: la verko Korĵ05 (sube), ĝia presita paĝo 120, kaj la unua linio de la dowse sur ĝi (a, b, c … "
           "laŭ ilia ordo, ĉiuj personoj kune).",
           "- **AmEsp 1910.3:14a**: ĉe gazeto la jaro kaj la numero post la siglo: *Amerika Esperantisto*, 1910, n-ro 3, "
           "presita paĝo 14, la unua linio.",
           "- **∴15**: paĝo, kies numero ne legeblas; la numero eltirita el la paĝigo de la numero aŭ de la volumo.",
           "- **[15]**: paĝo de verko, kiu presas neniujn numerojn, nombrita.",
           "- **[kovrilo]**: la kovrilo.",
           "- **[PDF 14]**: la 14-a paĝo de la skanaĵo.",
           "- **¶12**: alineo de tajpita teksto.",
           "- **l.40**: linio de konservita retpaĝo.",
           "- **?** post la loko: la linio ne plu troviĝas en la dowse en tiu formo.",
           "- **‹ligilo›** post verko: la citita numero rete, kie ĝi estas rete.", ""]
    for c in cited:
        k = keys[c]; r = rows.get(k, {})
        _, entry, _w = work(k)
        cit = (r.get("citation") or "").strip()
        if not cit:
            cit = render(entry, k, c, r) if entry else (f"*{r['title']}* {r.get('year', '')}" + (f", n-ro {r['label_as_filed']}" if r.get("label_as_filed") else "") + "." if r.get("title") else "")
        u = sigla.online(k)   # the item's online location (2026-10-25, the editor)
        ref.append(f"- **{c}**: {cit or k}" + (f" <{sigla.href(u)}>" if u else ""))
    lp = os.path.join(d, f"S4-LABELLED-{tag}.md")
    # the references follow the biography (part (1)), before the report's parts (2)–(4) (the editor, 2026-10-20
    # they stood at the very end, after the report)
    m = re.search(r"^## 2\.", txt, re.M)
    body = (txt[:m.start()].rstrip() + "\n" + "\n".join(ref) + "\n\n" + txt[m.start():].rstrip()) if m else (txt.rstrip() + "\n" + "\n".join(ref))
    open(lp, "w", encoding="utf-8").write(
        f"`[tools/fact-labels.py: {os.path.basename(bio)} with each L-number written as its fact label (LABELS-{tag}.tsv); the "
        f"listing by label: PROFILE-LABELLED-{tag}.md.]`\n\n" + body + "\n")
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
