#!/usr/bin/env python3
"""The facts readers' brief of a source, filled from the template (made a tool 2026-10-14, so that a stage runs on
approved tools: the editor,; the runbook, D6).

    tools/dowse-brief-fill.py <source> <date> [--stage TEXT]       write dowse/<source>/facts-brief-<date>.md
    tools/dowse-brief-fill.py <source> --config-from <brief.md>    write dowse/<source>/brief-config.json from a brief

The template: ocr/method/DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-18-LEAN.md (from 2026-10-22; a template whose
header says it is SUPERSEDED is refused). The settings, dowse/<source>/brief-config.json:
  source     «Aleksander Korĵenkov, *Historio de Esperanto* (Kaliningrado: Sezonoj, 2005), 130 PDF-paĝoj»
  texts      [paths under geniza/, e.g. «sources/ocr-preferred/korzhenkov-historio-2005.txt»]
  pages      how printed and PDF pages relate (one sentence), or «»
  copyright  true or false
  item       the item key of the locators
  readers    «1: PDF 1–26 (…) · 2: PDF 27–32 (…)»
  extra      «**Por ĉi tiu fonto:** …», or «»
  list       [15, 64]: the lines of «The list in force» the readers read
The «out» list comes from dowse/<source>/out-list-<date>.md (tools/dowse-reader-roster.py --out-list), the roster from
dowse/<source>/roster-reader-<date>.txt if it exists, else roster.txt; the namesakes from dowse/<source>/candidates-<date>.md
or candidates.md (tools/dowse-candidates.py; required from 2026-10-15). Refuses to overwrite. Ezri, 2026-10-14."""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus_locks as CL  # noqa: E402  (the dowse's lock against Miles's chain, 2026-10-26: geniza/ocr/locks/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
# THE LEAN BRIEF BY DEFAULT (2026-10-22; the editor
#): every batch since 2026-10-20 read the
# lean template, given by --template; the 2026-10-13 one, still the default until now, had its readers write «[sen
# dato]» where the issue dates the line (Amerika Esperantisto's 9,689 lines guessed «ĉ. … laŭ la numero» at the harvest)
TPL = os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-18-LEAN.md")

def refuse_superseded(path):
    """A template whose header (before its first «## ») says «SUPERSEDED … by ‹file›.md» for the fact readers is refused,
    naming the file that replaces it."""
    head = open(path, encoding="utf-8").read().split("\n## ", 1)[0]
    m = re.search(r"SUPERSEDED\b[^\n]*?\bby `?([\w.-]+\.md)`?", head)
    if m: sys.exit(f"refusing: {os.path.basename(path)} is superseded (its header): use {m.group(1)}, the default, or --template {m.group(1)}")

def config_from(brief):
    t = open(brief, encoding="utf-8").read()
    src = re.search(r"^\*\*La fonto:\*\* (.*?)\. La teksto", t, re.M)
    texts = re.findall(r"geniza/(sources/(?:ocr-preferred|born-digital-text)/[^`\n]+?\.txt)", t)
    lines = t.split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("**La fonto:**"))
    pages = next((l for l in lines[i + 1:i + 5] if l and not l.startswith("/") and not l.startswith("**") and "kopirajto" not in l), "")
    item = re.search(r"· (\S+), PDF N", t)
    # «## La legiloj» since 2026-10-22 (the editor), «## La legantoj» in the briefs before it
    readers = re.split(r"## La leg(?:iloj|antoj)", t, maxsplit=1)[1].strip() if re.search(r"## La leg(?:iloj|antoj)", t) else ""
    extra = re.search(r"^(\*\*Por ĉi tiu fonto:\*\*.*)$", t, re.M)
    lr = re.search(r"legu nur la liniojn (\d+) ĝis (\d+)", t)
    return {"source": src.group(1) if src else "", "texts": sorted(set(texts), key=texts.index), "pages": pages.strip(),
            "copyright": "sub kopirajto" in t, "item": item.group(1) if item else "", "readers": readers,
            "extra": extra.group(1) if extra else "", "list": [int(lr.group(1)), int(lr.group(2))] if lr else [15, 64]}

KINDS = os.path.join(G, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md")

def list_range():
    """The lines of «The list in force», found by its heading at fill time (2026-10-15, the Fable review 18: a range
    fixed in each config would shift with any edit above it)."""
    ls = open(KINDS, encoding="utf-8").read().split("\n")
    a = next(i for i, l in enumerate(ls, 1) if l.startswith("## The list in force"))
    b = next((i for i, l in enumerate(ls, 1) if i > a and l.startswith("## ")), len(ls) + 1) - 1
    return a, b

def scope_of(s):
    """dowse/<source>/scope.tsv (tools/dowse-page-scope.py, 2026-10-20): {text stem: set of PDF pages in scope, or None
    for the whole text}; a text it does not name is read whole. «none» is the empty set."""
    p = os.path.join(G, "dowse", s, "scope.tsv"); out = {}
    if not os.path.exists(p): return out
    for l in open(p, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        stem, pages = l.rstrip("\n").split("\t")[:2]
        if pages == "all": out[stem] = None; continue
        got = set()
        for part in ([] if pages == "none" else pages.split(",")):
            a, _, b = part.partition("-"); got.update(range(int(a), int(b or a) + 1))
        out[stem] = got
    return out

def gaps(got, last, unit, where="", expect=None):
    """Gaps and overlaps of the ranges [(lo, hi, reader)] over units 1…last of one text; with EXPECT (the pages in
    scope, scope.tsv), every page of it read once and no page outside it read."""
    if expect is not None:
        faults, seen = [], set()
        for lo, hi, r in sorted(got):
            for u in range(lo, hi + 1):
                if u in seen: faults.append(f"{where}reader {r} overlaps at {unit} {u}")
                if u not in expect: faults.append(f"{where}reader {r} reads {unit} {u}, out of scope")
                seen.add(u)
        miss = sorted(expect - seen)
        if miss: faults.append(f"{where}{len(miss)} {unit} in scope have no reader (first {miss[0]})")
        return faults
    got = sorted(got); faults = []; nxt = 1
    for lo, hi, r in got:
        if lo > nxt: faults.append(f"{where}{unit} {nxt}–{lo - 1} has no reader")
        if lo < nxt: faults.append(f"{where}reader {r} overlaps the reader before it at {unit} {lo}")
        nxt = max(nxt, hi + 1)
        if unit == "PDF" and hi - lo + 1 > 20: print(f"  note: {where}reader {r} has {hi - lo + 1} pages, over the cap of about 15–20 (D6 point 7)")
    if last and nxt <= last: faults.append(f"{where}{unit} {nxt}–{last} has no reader")
    return faults

RANGES = {}   # reader -> [(text path under geniza/, first unit, last unit)], from the last coverage() call
SCOPE = {}    # the source's scope.tsv, for propose_ranges
# THE PAGES OF A SELECTIVE REDOWSE (2026-10-25, R4 of ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md): --readers-file
# FILE gives the «readers» for this run only (the recupelled pages, written by tools/redowse-pages.py), so the source's
# own brief-config.json keeps its whole-source ranges; its «reader_starts», numbered by those ranges, is not used
READERS_OVERRIDE = []

def load_config(D):
    c = json.load(open(os.path.join(D, "brief-config.json"), encoding="utf-8"))
    if READERS_OVERRIDE: c["readers"], c["reader_starts"] = READERS_OVERRIDE[0], {}
    return c

# A JOURNAL'S READERS GET WHOLE ISSUES, CUT ONLY WHERE AN ARTICLE BEGINS (2026-10-21; the editor, 2026-10-18 17:0x:
# 2026-10-21: the new cutting built first). brief-config.json «journal»: {"issue_start": REGEX}, the masthead line that opens an issue inside a file
# (every file's first page opens one anyway). Pages only: a cut falls between pages.
CONTINUED = re.compile(r"(?:da[uŭ]rigo|sekvo|fino)\s+(?:sur|en|ĉe)\s+(?:la\s+)?p(?:a[ĝg]o|\.)\s*\d+|continued\s+on\s+(?:page|p\.)\s*\d+"
                       r"|suite\s+(?:à\s+la\s+)?page\s*\d+|\((?:suite\s+)?voir\s+(?:la\s+lumo,?\s+)?pages?\s*[\d\-–, ]+\)|fortsetzung\s+(?:auf\s+)?s(?:eite|\.)\s*\d+", re.I)

def page_lines(t):
    """{page: [its lines]} of a text with «=== page N ===» markers."""
    pieces = re.split(r"^=== (?:page|¶) (\d+) ===[ \t]*$", t, flags=re.M)
    return {int(pieces[i]): pieces[i + 1].split("\n") for i in range(1, len(pieces) - 1, 2)}

def issue_starts(lines_by_page, rx, window=30):
    """The pages on whose first WINDOW lines (brief-config «journal» «issue_window», default 30) a masthead line (rx)
    stands; the first page always."""
    ps = sorted(lines_by_page)
    out = {ps[0]} if ps else set()
    if rx:
        r = re.compile(rx)
        out |= {p for p in ps if any(r.search(l) for l in lines_by_page[p][:window])}
    return out

RUNNING_HEAD = re.compile(r"ESPERANTIST|LA\s+LUMO|Pa[ĝgŝs]o\s*\d|Seite|Jahrgang|\bJaro\s+[IVXl1|]+|^\W*\d+\W*$", re.I)
FINITE = re.compile(r"\b\w{2,}(?:as|is|os|us)\b")    # an Esperanto finite verb: prose, not a heading
SIGNATURE = re.compile(r"^[—–-]?\s*(?:D-?r[o.]?\s+|S-r[oi]n?\s+|Prof\.\s+)?(?:[A-ZĈĜĤĴŜŬ]\.\s?){1,3}\s?[A-ZĈĜĤĴŜŬ][a-zĉĝĥĵŝŭäöüéèçàñ'\-]{2,}(?:\s*\([^)]*\))?\.?$")

def wordlike(l):
    """The share of a line's tokens that look like words (three letters or more with a vowel, not of mixed case):
    OCR noise («a TT rn ST PAT PT A E TAS») scores low."""
    toks = [re.sub(r"[^\wĉĝĥĵŝŭĈĜĤĴŜŬ'-]", "", w) for w in l.split()]
    toks = [w for w in toks if w]
    if not toks: return 0.0
    ok = sum(1 for w in toks if (len(w) >= 3 and re.search(r"[aeiouyŭàâéèêëîïôöùûüAEIOUYÀÂÉÈÊÎÔÖÙÛÜ]", w) and (w.islower() or w.isupper() or w[0].isupper() and w[1:].islower()))
             or w.lower() in ("la", "de", "el", "al", "en", "pri", "kaj", "da", "ĉe", "ĝis", "le", "et", "of", "the", "an", "a", "i", "e"))
    return ok / len(toks)

def headings(lines, rubric=None):
    """Where an article seems to begin on a page: [(index of the line, the line)]. An OCR page has no markup, so a
    heading is judged by its shape, tested 2026-10-21 on La Esperantisto (the first rule took OCR noise, running heads,
    a story's lines of dialogue and list entries for headings): a rubric of the journal (brief-config «journal»
    «rubric», «Nia afero.», «Bagateloj.»), or a line that is (1) short, under three-fifths of the page's usual line, or
    all capitals; (2) set off above by an empty line, the page's top or its running head; (3) followed by a line that
    does not continue a sentence (not lower case); (4) made of words, not noise (wordlike ≥ 0.75); and (5) not prose:
    no Esperanto finite verb (-as, -is, -os, -us), no quotation marks or dash at its start (dialogue), no comma (a list
    entry: «Uspenskaja, E. S., m-me.»), no second sentence («Hoko. Mi...»), not an arabic-numbered entry («12. …»), not
    a signature («L. Zamenhof.», which ends an article: see article_cuts), not a running head."""
    rub = re.compile(rubric, re.I) if rubric else None
    body = [(i, l.strip()) for i, l in enumerate(lines) if l.strip()]
    if not body: return []
    lens = sorted(len(l) for _i, l in body)
    usual = lens[len(lens) * 3 // 4] or 1
    out = []
    for k, (i, l) in enumerate(body):
        if RUNNING_HEAD.search(l) and k < 3: continue
        if rub and rub.match(l):
            out.append((i, l)); continue
        letters = [ch for ch in l if ch.isalpha()]
        if len(letters) < 4: continue
        caps = sum(ch.isupper() for ch in letters)
        allcaps = len(letters) >= 6 and caps >= len(letters) * 0.85
        if not (len(l) < usual * 0.6 or allcaps and len(l) < usual * 1.1): continue
        if not re.match(r"[A-ZĈĜĤĴŜŬÀ-ÞIVX]", l): continue    # a heading begins with a capital (not «efektivigado.»)
        top = k == 0 or (k <= 2 and all(RUNNING_HEAD.search(body[m][1]) or wordlike(body[m][1]) < 0.5 for m in range(k)))
        if not (top or not lines[i - 1].strip()): continue
        nxt = body[k + 1][1] if k + 1 < len(body) else ""
        if nxt[:1].islower(): continue
        if wordlike(l) < 0.75: continue
        if (FINITE.search(l) and not allcaps) or re.match(r"[«»„“\"'—–-]", l) or re.search(r"[«»„“]", l) or "," in l: continue
        if re.search(r"[.!?]\s+[A-ZĈĜĤĴŜŬ][a-zĉĝĥĵŝŭ]{2,}", l) or re.match(r"\d+\.", l) or SIGNATURE.match(l): continue
        if RUNNING_HEAD.search(l): continue
        out.append((i, l))
    return out

def article_cuts(lines_by_page, ps, rubric=None):
    """{page: ("top"|"mid", what marks it)}: a page whose first heading stands in its top fifth (after the running
    head), or whose page before ends with a signature in its bottom fifth (a signed article finished there), is a
    clean cut; a page with a heading lower down a fair one."""
    out = {}
    for n_, p in enumerate(ps):
        ls = lines_by_page.get(p, [])
        n = max(1, sum(1 for l in ls if l.strip()))
        h = headings(ls, rubric)
        prev = lines_by_page.get(ps[n_ - 1], []) if n_ else []
        pb = [l.strip() for l in prev if l.strip()]
        sig = next((l for l in pb[-max(3, len(pb) // 5):] if SIGNATURE.match(l)), None) if pb else None
        if h and sum(1 for l in ls[:h[0][0]] if l.strip()) <= max(3, n // 5):
            out[p] = ("top", h[0][1][:60])
        elif sig:
            out[p] = ("top", f"after the signature «{sig[:40]}» at the foot of PDF {ps[n_ - 1]}")
        elif h:
            out[p] = ("mid", h[0][1][:60])
    return out

def pages_files(texts, date):
    """EACH READER'S PAGES CUT OUT FOR IT (2026-10-17; the editor; the runbook review, lever 2): a reader of
    2026-10-15 searched the whole text for its pages (a Neves reader read lines 1–700, then 3700–3950 and 4200–4600) and
    re-read that context at every call. Each reader gets its own units, and the next one (a paragraph that runs on), in
    `facts-pages-<date>-<N>.txt`, every unit with its marker as in the text; a source of several texts gives each text's
    part under «=== teksto: <stem> ===». -> {file name: content}."""
    bypath = dict(texts)
    out = {}
    for r, parts in sorted(RANGES.items(), key=lambda x: int(x[0])):
        chunks = []
        for path, lo, hi in parts:
            t = bypath[path]
            pieces = re.split(r"^(=== (?:page|¶) \d+ ===)[ \t]*$", t, flags=re.M)
            units = {int(re.search(r"\d+", pieces[i]).group()): pieces[i] + pieces[i + 1] for i in range(1, len(pieces) - 1, 2)}
            last = max(units) if units else 0
            # the next unit only for pages, where a paragraph runs on; a paragraph («¶ N») ends in itself, and its
            # neighbour in the file would invite lines from the next reader's first paragraph (found 2026-10-17, Jossinet)
            nxt = 0 if re.search(r"^=== ¶ \d+ ===", t, re.M) else 1
            keep = [units[n] for n in range(lo, min(hi + nxt, last) + 1) if n in units]
            head = f"=== teksto: {os.path.basename(path)[:-4]} ===\n" if len(bypath) > 1 else ""
            chunks.append(head + "".join(keep).strip("\n") + "\n")
        out[f"facts-pages-{date}-{r}.txt"] = "\n".join(chunks)
    return out

def coverage(readers, texts, partial, scope=None):
    """The readers' ranges against the text (the Fable review 4: Korĵenkov's committed ranges left PDF 27–63 and
    119–130 unread, and nothing said so): refuses a gap, an overlap or a last unit short of the text's, unless --partial.
    texts: [(path, text)]. A source of SEVERAL TEXTS (2026-10-16 23:4x; the editor, on Neves's readers written per
    edition, which the check could not read) names its text in every range, «`<text stem>` PDF a–b», and each text is checked on its own: every
    page of every text read by exactly one reader; a range naming no text of the source, or a text no range names, refused."""
    joined = "\n".join(t for _p, t in texts)
    unit = "¶" if re.search(r"^=== ¶ \d+ ===", joined, re.M) else "PDF"
    lastof = lambda t: max([int(x) for x in re.findall(r"^=== (?:page|¶) (\d+) ===", t, re.M)] or [0])
    faults = []
    RANGES.clear()
    scope = scope or {}
    if len(texts) == 1:
        got = [(int(m.group(2)), int(m.group(3) or m.group(2)), m.group(1))
               # the text's name before the range is optional: --write-readers names it, a range written by hand need not
               for m in re.finditer(r"(\d+): (?:`[^`]+` )?(?:PDF|¶) (\d+)(?:\s*[–-]\s*(\d+))?", readers)]
        faults = gaps(got, lastof(joined), unit, expect=scope.get(os.path.basename(texts[0][0])[:-4]))
        for lo, hi, r in got: RANGES.setdefault(r, []).append((texts[0][0], lo, hi))
    else:
        stems = {os.path.basename(p)[:-4]: t for p, t in texts}
        per = {k: [] for k in stems}
        for entry in re.split(r"\s+·\s+", readers.strip()):
            mr = re.match(r"(\d+):", entry)
            if not mr: faults.append(f"a reader entry without its number: «{entry[:40]}…»"); continue
            for m in re.finditer(r"`([^`]+)` (?:PDF|¶) (\d+)(?:\s*[–-]\s*(\d+))?", entry):
                if m.group(1) not in stems: faults.append(f"reader {mr.group(1)} names «{m.group(1)}», not a text of this source"); continue
                per[m.group(1)].append((int(m.group(2)), int(m.group(3) or m.group(2)), mr.group(1)))
                RANGES.setdefault(mr.group(1), []).append((next(p for p, _t in texts if os.path.basename(p)[:-4] == m.group(1)),
                                                           int(m.group(2)), int(m.group(3) or m.group(2))))
        for k, t in stems.items():
            if scope.get(k, None) == set(): continue   # out of scope whole
            if not per[k]: faults.append(f"«{k}»: no reader names it"); continue
            faults += gaps(per[k], lastof(t), unit, where=f"«{k}» ", expect=scope.get(k))
    if faults and not partial:
        sys.exit("refusing, the readers do not cover the text: " + "; ".join(faults) + " (--partial «why» for a probe)")
    return unit, faults

def fill(s, date, stage, side, partial="", pdir=None):
    D = os.path.join(G, "dowse", s)
    pdir = pdir or D
    c = load_config(D)
    t = open(TPL, encoding="utf-8").read()
    body = t.split("## La briefo, kiel donita al ĉiu legilo (la paĝoj malsamas)", 1)[1]
    # the side files of step 2 and step 4, by their own date; never a silent fallback (the Fable review 5, 6)
    roster = os.path.join(D, f"roster-reader-{side}.txt"); cand = os.path.join(D, f"candidates-{side}.md")
    ol = os.path.join(D, f"out-list-{side}.md")
    for p, step in ((roster, "2, dowse-reader-roster.py"), (ol, "2, dowse-reader-roster.py --out-list"), (cand, "4, dowse-candidates.py --date")):
        if not os.path.exists(p): sys.exit(f"refusing: {os.path.relpath(p, G)} is missing (D6c step {step}; --side-date names their date)")
    outs = [l for l in open(ol, encoding="utf-8").read().split("\n") if l.startswith("- ")]
    texts = [(x, open(os.path.join(G, x), encoding="utf-8").read()) for x in c["texts"]]
    unit, faults = coverage(c["readers"], texts, partial, scope_of(s))
    la, lb = list_range()
    if c.get("list") and c["list"] != [la, lb]: print(f"  note: «The list in force» is lines {la}–{lb} now, not {c['list'][0]}–{c['list'][1]} as in the config")
    marker = ("La teksto, kun alineoj markitaj «=== ¶ N ===» (N = la alineo):" if unit == "¶"
              else "La teksto, kun paĝoj markitaj «=== page N ===» (N = la PDF-paĝo):")
    rep = [
        ("legu nur la liniojn {de} ĝis {ĝis} de la dosiero", f"legu nur la liniojn {la} ĝis {lb} de la dosiero"),
        ("{aŭtoro, *titolo* (loko: eldonejo, jaro)}, {N} PDF-paĝoj. La teksto, kun paĝoj markitaj «=== page N ===» (N = la PDF-paĝo), aŭ por tajpita teksto alineoj (¶):",
         f"{c['source']}. {marker}"),
        ("{absoluta vojo al sources/ocr-preferred/<ero>.txt aŭ sources/born-digital-text/<ero>.txt}", "\n".join(os.path.join(G, x) for x in c["texts"])
         + f"\n**Viaj paĝoj, eltranĉitaj por vi** (la runbook-revizio de 2026-10-17): `{os.path.join(pdir, f'facts-pages-{date}-')}N.txt`, kie N estas via numero; "
           "ĝi enhavas viajn paĝojn kun iliaj markoj, kaj la sekvan paĝon, por alineo, kiu daŭras. Legu tiun dosieron; la tutan tekston supre "
           "nur por noto, kiun viaj paĝoj citas, aŭ por kunteksto."),
        ("{Kiel rilatas presitaj kaj PDF-paĝoj, ekz. «la presita paĝo estas kutime la PDF-paĝo minus unu; kontrolu ĝin sur ĉiu paĝo, kie ĝi videblas».}", c["pages"]),
        ("**Viaj paĝoj:** PDF {de} ĝis {ĝis}. Legu ilin tute.\n", ""),
        ("{Se la fonto estas sub kopirajto:} ", "" if c["copyright"] else "\x00"),
        ("{absoluta vojo al dowse/<fonto>/roster.txt}", roster),
        ("{absoluta vojo al dowse/<fonto>/candidates.md}", cand),
        ("{ero}", c["item"]),
    ]
    for a, b in rep:
        if a not in body: sys.exit(f"the template has changed: «{a[:60]}…» not found")
        body = body.replace(a, b)
    if unit == "¶":   # an unpaged text: the line form and the locator by paragraph (the Fable review 7)
        body = body.replace(f"{c['item']}, PDF N (prese M)", f"{c['item']}, ¶ N")
    body = "\n".join(l for l in body.split("\n") if not l.startswith("\x00"))
    body = re.sub(r"^   \{La personoj «ekster» por ĉi tiu fonto:.*\}$", "\n".join(outs) if outs else "   (neniu el la registro troviĝis en la fonto)", body, flags=re.M)
    extra = c["extra"]
    # the lean template's locator is «(prese M) l. K» alone: a source's own sentence on the locator's item («**La
    # lokindiko nomas la numeron de via tasko** … `…, PDF N (prese M)`») contradicts it, and four of six readers of the
    # second lean probe wrote the item and the PDF page (2026-10-18t)
    if "(prese M) l. K" in t:
        extra = re.sub(r"\s*\*\*La lokindiko[^*]*\*\*.*?`[^`]*`\.", "", extra, flags=re.S)
    body = re.sub(r"## La legiloj\n\n\{Por ĉiu legilo:.*\}", (extra + "\n\n" if extra else "") + "## La legiloj\n\n" + c["readers"], body, flags=re.S)
    cover = (f" Partial on purpose ({partial}): " + "; ".join(faults) + "." if faults else "")
    head = (f"# {s}: la fakto-legado{' de ' + stage if stage else ''} ({date})\n\n"
            f"`[Ezri, {date}, per tools/dowse-brief-fill.py el la ŝablono {os.path.basename(TPL)} kaj dowse/{s}/brief-config.json; "
            f"the side files of {side}; «The list in force» lines {la}–{lb}.{cover}]`\n\n"
            "## La briefo, kiel donita al ĉiu legilo (la paĝoj malsamas)")
    return head + body

STARTS = []   # how each journal reader's range begins (journal_ranges), written as «reader_starts» with the readers

def journal_ranges(c, jr, target, write, lines_on):
    """The readers' ranges of a journal (brief-config «journal»; 2026-10-21, the editor). Its issues are the sections: whole issues packed into a reader up to the cap (a
    quarter over the target, twenty pages at most); an issue too long for one reader cut only where an article begins,
    each cut sought within three pages of where an equal share would put it, a page with a heading at its top first,
    then one with a heading lower down; with neither, the cut stays at the share and is marked «mid-article». Texts
    that are pieces of one volume («journal» «volume»: a pattern whose group 1 names the volume, e.g. La Esperantisto's
    yearly volumes in 50-page pieces) run on as one sequence of pages, so an issue that crosses from one piece into the
    next goes to one reader, its range written as «`piece A` PDF 45–50 + `piece B` PDF 1–3». Printed (unless WRITE),
    with how each reader's range begins; returns the ranges."""
    cap = target * 1.25
    vol = re.compile(jr["volume"]) if jr.get("volume") else None
    groups = []
    for x in c["texts"]:
        m = vol.search(os.path.basename(x)[:-4]) if vol else None
        if groups and m and groups[-1][0] == m.group(1): groups[-1][1].append(x)
        else: groups.append((m.group(1) if m else None, [x]))
    stat = {"readers": 0, "whole": 0, "issues": 0, "top": 0, "mid": 0, "forced": 0, "across": 0}
    allr = []
    for _key, xs in groups:
        seq, lbp = [], {}
        for x in xs:
            pl = page_lines(open(os.path.join(G, x), encoding="utf-8").read())
            for p in sorted(pl):
                lbp[len(seq)] = pl[p]; seq.append((x, p))
        if not seq: continue
        idx = list(range(len(seq)))
        starts = issue_starts(lbp, jr.get("issue_start"), jr.get("issue_window", 30))
        acuts = article_cuts(lbp, idx, jr.get("rubric"))
        L = [lines_on(x, p) for x, p in seq]
        name = lambda i: f"«{os.path.basename(seq[i][0])[:-4]}» PDF {seq[i][1]}"
        if not write:
            for i in idx:
                for l in lbp[i]:
                    if CONTINUED.search(l): print(f"  flag {name(i)}: «{l.strip()[:70]}» (a jump to another page: for the postprocessing pass)")
        cuts = sorted(starts)
        secs = [(cuts[n], cuts[n + 1] if n + 1 < len(cuts) else len(seq)) for n in range(len(cuts))]
        out, cur = [], None
        def flush():
            if cur: out.append([cur[0], cur[1], sum(L[cur[0]:cur[1]]), "whole issue" if cur[2] == 1 else "whole issues"])
        for a_, b_ in secs:
            n_ = sum(L[a_:b_])
            if n_ > cap or b_ - a_ > 20:
                flush(); cur = None; stat["issues"] += 1
                parts = max(2, -(-int(n_) // target), -(-(b_ - a_) // 20))
                bounds, prev, acc_, q = [(a_, "issue start", "")], a_, 0.0, a_
                for k_ in range(1, parts):
                    while q < b_ and acc_ + L[q] < n_ * k_ / parts: acc_ += L[q]; q += 1
                    ideal = q + 1          # the share is passed on page q: the next reader begins after it
                    lo, hi = prev + 1, b_ - 1
                    if lo > hi or ideal > hi + 1: break
                    near = [j for j in range(max(lo, ideal - 3), min(hi, ideal + 3) + 1) if j in acuts]
                    if near:
                        j = min(near, key=lambda j: (acuts[j][0] != "top", abs(j - ideal)))
                        bounds.append((j, acuts[j][0], acuts[j][1]))
                    else:
                        j = min(max(ideal, lo), hi); bounds.append((j, "forced", ""))
                    prev = j
                for m, (j, kind, h) in enumerate(bounds):
                    e = bounds[m + 1][0] if m + 1 < len(bounds) else b_
                    note = ("issue start" if kind == "issue start" else f"article start, top of page: «{h}»" if kind == "top"
                            else f"article start, mid-page: «{h}»" if kind == "mid" else "MID-ARTICLE: no heading within three pages")
                    if kind in stat: stat[kind] += 1
                    out.append([j, e, sum(L[j:e]), note])
            elif cur and sum(L[cur[0]:b_]) <= cap and b_ - cur[0] <= 20:
                cur = (cur[0], b_, cur[2] + 1)
            else:
                flush(); cur = (a_, b_, 1)
        flush()
        # a small reader (under a third of the target) joins a neighbour where the two stay within the cap; the
        # joined range keeps the earlier one's beginning
        k = 0
        while k < len(out):
            if out[k][2] < target / 3 and len(out) > 1:
                nb = [m for m in (k - 1, k + 1) if 0 <= m < len(out) and out[m][2] + out[k][2] <= cap
                      and max(out[m][1], out[k][1]) - min(out[m][0], out[k][0]) <= 20]
                if nb:
                    m = min(nb, key=lambda m: out[m][2]); lo_, hi_ = min(k, m), max(k, m)
                    out[lo_] = [out[lo_][0], out[hi_][1], out[lo_][2] + out[hi_][2], out[lo_][3]]; del out[hi_]
                    k = max(0, lo_ - 1); continue
            k += 1
        for i, e, acc, note in out:
            parts_ = []
            for n in range(i, e):
                x, p = seq[n]
                if parts_ and parts_[-1][0] == x: parts_[-1][2] = p
                else: parts_.append([x, p, p])
            r = " + ".join(f"`{os.path.basename(x)[:-4]}` PDF {a}–{b}" for x, a, b in parts_)
            allr.append(r); stat["readers"] += 1
            STARTS.append("whole" if note.startswith("whole") else "issue" if note == "issue start" else "top" if "top of page" in note
                          else "mid" if "mid-page" in note else "forced")
            if note.startswith("whole"): stat["whole"] += 1
            if len(parts_) > 1: stat["across"] += 1
            inside = [seq[n][1] for n in range(i + 1, e) if n in starts]
            if not write: print(f"  {len(allr)}: {r} · about {acc:.0f} lines · {e - i} PDF · {note}"
                                + (f" · an issue begins inside, on PDF {', '.join(map(str, inside))}" if inside else ""))
    print(f"\njournal cutting: {stat['readers']} readers; {stat['whole']} of whole issues; {stat['issues']} issues too long for one reader, "
          f"their later parts begun at an article on the top of a page {stat['top']}, mid-page {stat['mid']}, MID-ARTICLE {stat['forced']}; "
          f"{stat['across']} ranges across two pieces of a volume")
    return allr

RATE_FROM = [""]   # --rate-from SOURCE, for propose_ranges

def propose_ranges(s, target, write=False):
    """--propose-ranges (2026-10-17; the editor; the runbook review, lever 4):
    readers' ranges proposed for a source, printed, never written: each text's pages filled in order up to about TARGET
    lines a reader, the lines judged from the source's last dowse (its lines per page, by the first locator) or, on a
    page it has none for, from the page's words at the source's own rate of lines per word; a cut moved to a section's
    first page within three pages (the chapters as `dowse-recall.py sections` finds them, and numbered headings
    «3. …»), never past twenty pages. For a source of several texts each text is proposed on its own: which parts of
    two editions correspond stays a reading of the texts (as Neves's did). The coverage check still verifies the ranges."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("recall", os.path.join(ROOT, "tools", "dowse-recall.py"))
    rc = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(rc)
    finally: sys.argv = saved
    D = os.path.join(G, "dowse", s)
    c = load_config(D)
    SCOPE.clear(); SCOPE.update(scope_of(s))
    if SCOPE: print(f"  the scope: dowse/{s}/scope.tsv, {len(SCOPE)} texts named")
    df = os.path.join(G, "profiles", "by-source", f"{s}-dowse.md")
    per = {}
    # the facts file names an item by its key since 2026-10-17 (ruslandaesperantisto1905-1); the texts are by file name
    # (RuslandaEsperantisto1905.1): the key read back to the name, or no page matched and the rate fell to the guess
    k2n = {}
    it = os.path.join(G, "OCR-ITEM-TABLE.tsv")
    if os.path.exists(it):
        rows = [l.rstrip("\n").split("\t") for l in open(it, encoding="utf-8") if not l.startswith("#")]
        if rows and "key" in rows[0]:
            ki = rows[0].index("key")
            k2n = {r[ki]: r[0] for r in rows[1:] if len(r) > ki and r[ki]}
    for l in (open(df, encoding="utf-8").read().split("\n") if os.path.exists(df) else []):
        m = re.search(r" · ([^·;]+?), (?:PDF|¶) (\d+)", l) if l.startswith("- $$$") else None
        if m:
            k = (k2n.get(m.group(1).strip(), m.group(1).strip()), int(m.group(2)))
            per[k] = per.get(k, 0) + 1
    words, units = {}, {}
    for x in c["texts"]:
        t = open(os.path.join(G, x), encoding="utf-8").read()
        pieces = re.split(r"^=== (?:page|¶) (\d+) ===[ \t]*$", t, flags=re.M)
        units[x] = {int(pieces[i]): len(pieces[i + 1].split()) for i in range(1, len(pieces) - 1, 2)}
    stems = {x: os.path.basename(x)[:-4] for x in c["texts"]}
    seen_w = sum(w for x in c["texts"] for p, w in units[x].items() if per.get((stems[x], p)) or per.get((c["item"], p)) and x == c["texts"][0])
    seen_l = sum(per.values())
    rate = seen_l / seen_w if seen_w else None
    # --rate-from SOURCE (2026-10-23, Lingvo Internacia 1906–1914 in a folder of its own: with no dowse there, the guess of
    # a line per 40 words gave 42,089 lines and 630 ranges; the 1895–1905 dowse wrote about one per 61): another folder's
    # rate of lines per word, its facts file against its own texts, where this folder has none
    if rate is None and RATE_FROM[0]:
        o = RATE_FROM[0]
        oc = json.load(open(os.path.join(G, "dowse", o, "brief-config.json"), encoding="utf-8"))
        of = os.path.join(G, "profiles", "by-source", f"{o}-dowse.md")
        if not os.path.exists(of): sys.exit(f"refused: --rate-from {o}: no profiles/by-source/{o}-dowse.md")
        ol = sum(1 for l in open(of, encoding="utf-8") if l.startswith("- $$$"))
        ow = sum(len(open(os.path.join(G, x), encoding="utf-8").read().split()) for x in oc["texts"])
        rate = ol / ow if ow else None
        print(f"  the rate from {o}: {ol} lines on {ow} words")
    allr = []
    print(f"{s}: target about {target} lines a reader; the last dowse {seen_l} lines" + (f", {rate * 100:.1f} lines per 100 words" if rate else ", none: pages by words only"))
    jr = c.get("journal")
    for x in ([] if jr is not None else c["texts"]):
        starts = set()
        try: starts = {a for a, _b, _h in rc.chapters(os.path.join(G, x))}
        except Exception: pass
        t = open(os.path.join(G, x), encoding="utf-8").read(); pg = 0
        for l in t.split("\n"):
            mm = re.match(r"=== (?:page|¶) (\d+) ===", l)
            if mm: pg = int(mm.group(1)); continue
            if re.match(r"^\d{1,2}\.\s+[A-ZĈĜĤĴŜŬÀ-ÞL«'’][^.]{3,70}$", l.strip()): starts.add(pg)
        def lines_on(p):
            n = per.get((stems[x], p)) or (per.get((c["item"], p)) if x == c["texts"][0] else None)
            return n if n is not None else (units[x].get(p, 0) * rate if rate else units[x].get(p, 0) / 40)
        # WHOLE SECTIONS FIRST (the editor, 2026-10-14
        #): the text cut at its section starts; whole
        # sections packed into a reader up to a quarter over the target; only a section too big for one reader is
        # split, in parts of about the target, each such cut marked «mid-section: choose the paragraph»
        ps = sorted(units[x]); cap = target * 1.25
        # THE SCOPE (scope.tsv, tools/dowse-page-scope.py, 2026-10-20): only the pages in scope; each run of them a
        # section of its own, and no reader's range across a page out of scope
        sc = SCOPE.get(stems[x], None) if stems[x] in SCOPE else None
        if stems[x] in SCOPE and sc is not None:
            ps = [p for p in ps if p in sc]
            if not ps:
                if not write: print(f"\n«{stems[x]}»: out of scope whole"); continue
                continue
            starts |= {p for k, p in enumerate(ps) if k == 0 or ps[k - 1] != p - 1}
        whole = lambda i, j: ps[j - 1] - ps[i] == j - 1 - i   # ps[i:j] has no page out of scope inside it
        cuts = [k for k, p in enumerate(ps) if k == 0 or p in starts]
        secs = [(cuts[n], (cuts[n + 1] if n + 1 < len(cuts) else len(ps))) for n in range(len(cuts))]
        out, cur = [], None
        def flush():
            if cur: out.append((ps[cur[0]], ps[cur[1] - 1], sum(lines_on(p) for p in ps[cur[0]:cur[1]]), ""))
        for a_, b_ in secs:
            n_ = sum(lines_on(p) for p in ps[a_:b_])
            if n_ > cap or b_ - a_ > 20:
                flush(); cur = None
                parts = max(2, -(-int(n_) // target), -(-(b_ - a_) // 20))
                acc_, start, done = 0.0, a_, 0
                for q in range(a_, b_):
                    acc_ += lines_on(ps[q])
                    # cut where the running count passes the next equal share of the section
                    if done + 1 < parts and acc_ >= n_ * (done + 1) / parts and q + 1 < b_:
                        out.append((ps[start], ps[q], sum(lines_on(p) for p in ps[start:q + 1]), "mid-section: choose the paragraph"))
                        start, done = q + 1, done + 1
                out.append((ps[start], ps[b_ - 1], sum(lines_on(p) for p in ps[start:b_]), "mid-section: choose the paragraph"))
            elif cur and sum(lines_on(p) for p in ps[cur[0]:b_]) <= cap and b_ - cur[0] <= 20 and whole(cur[0], b_):
                cur = (cur[0], b_)
            else:
                flush(); cur = (a_, b_)
        flush()
        # a small reader (under a third of the target) joins a neighbour where the two stay within the cap
        k = 0
        while k < len(out):
            a, b, acc, note = out[k]
            if acc < target / 3 and len(out) > 1:
                nb = [m for m in (k - 1, k + 1) if 0 <= m < len(out) and out[m][2] + acc <= cap and (max(b, out[m][1]) - min(a, out[m][0]) + 1) <= 20
                      and all(p in ps for p in range(min(a, out[m][0]), max(b, out[m][1]) + 1))]
                if nb:
                    m = min(nb, key=lambda m: out[m][2]); a2, b2, acc2, note2 = out[m]
                    out[min(k, m)] = (min(a, a2), max(b, b2), acc + acc2, note or note2); del out[max(k, m)]
                    k = max(0, min(k, m) - 1); continue
            k += 1
        out = [(a, b, acc, f"{note}" if note else "", [p for p in ps if a <= p <= b and p in starts]) for a, b, acc, note in out]
        unit = "¶" if re.search(r"^=== ¶ \d+ ===", t, re.M) else "PDF"
        if not write: print(f"\n«{stems[x]}» ({len(ps)} {unit}; section starts on {', '.join(map(str, sorted(starts))) or 'none found'}):")
        for k, (a, b, acc, note, st) in enumerate(out, 1):
            if not write: print(f"  {k}: {unit} {a}–{b} · about {acc:.0f} lines · {b - a + 1} {unit}" + (f" · sections begin on {', '.join(map(str, st))}" if st else "")
                                + (f" · {note}" if note else ""))
            allr.append(f"`{stems[x]}` {unit} {a}–{b}")
    if jr is not None:
        allr = journal_ranges(c, jr, target, write,
                              lambda x, p: per.get((stems[x], p)) or (units[x].get(p, 0) * rate if rate else units[x].get(p, 0) / 40))
    if write:
        # --write-readers (2026-10-18; Amerika Esperantisto's 637 ranges, the editor): the proposal
        # written as the «readers» field, numbered through all the texts, for a periodical whose issues are whole texts
        # and whose cuts fall on pages either way; refused where the field is set, so a range chosen by hand is not lost
        if c.get("readers"): sys.exit(f"refusing: «readers» is set in {os.path.relpath(os.path.join(D, 'brief-config.json'), ROOT)}")
        c["readers"] = " · ".join(f"{n}: {r}" for n, r in enumerate(allr, 1)) + "."
        if jr is not None: c["reader_starts"] = {str(n): k for n, k in enumerate(STARTS, 1)}
        json.dump(c, open(os.path.join(D, "brief-config.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nwrote {len(allr)} readers to «readers» in {os.path.relpath(os.path.join(D, 'brief-config.json'), ROOT)}")
    return 0

def workflow_args(s, date):
    """--workflow-args SOURCE DATE (2026-10-18, Amerika Esperantisto's 637 readers): the readers' workflow's arguments,
    dowse/<source>/workflow-readers-<date>.json, in its compact form ({brief, dest, ranges}: tools/workflows/
    carney-readers.js), from the «readers» field, so no range is copied by hand into the Workflow call. Create-only;
    refuses a reader of several texts (the compact form names one) and a missing brief."""
    D = os.path.join(G, "dowse", s)
    c = load_config(D)
    brief = os.path.join(D, f"facts-brief-{date}.md")
    if not os.path.exists(brief): sys.exit(f"refusing: no brief {os.path.relpath(brief, ROOT)}")
    parts = [p.strip() for p in re.split(r"\s+·\s+", c.get("readers", "").rstrip(".")) if p.strip()]
    ranges = []
    for n, p in enumerate(parts, 1):
        m = re.fullmatch(r"(\d+): `([^`]+)` (?:PDF|¶) (\d+)–(\d+)", p)
        if not m or int(m.group(1)) != n: sys.exit(f"refusing: reader {n} is not one text's range: «{p}»")
        ranges.append(f"{m.group(2)} {m.group(3)}-{m.group(4)}")
    wp = os.path.join(D, f"workflow-readers-{date}.json")
    if os.path.exists(wp): sys.exit(f"refusing: {os.path.relpath(wp, ROOT)} exists")
    json.dump({"brief": brief, "dest": f"geniza/dowse/{s}/facts-return-{date}-", "ranges": ranges},
              open(wp, "x", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"wrote {len(ranges)} ranges to {os.path.relpath(wp, ROOT)}")
    return 0

def main():
    if "--readers-file" in sys.argv:
        i = sys.argv.index("--readers-file")
        READERS_OVERRIDE.append(open(sys.argv[i + 1], encoding="utf-8").read().strip())
        del sys.argv[i:i + 2]
        if "--workflow-args" not in sys.argv and "--partial" not in sys.argv:
            sys.exit("refusing: --readers-file needs --partial «why» (the pages are part of the text)")
    if "--workflow-args" in sys.argv:
        i = sys.argv.index("--workflow-args")
        return workflow_args(sys.argv[i + 1], sys.argv[i + 2])
    if "--propose-ranges" in sys.argv:
        i = sys.argv.index("--propose-ranges")
        # 80 lines a reader, up to 100 packed (2026-10-17, the editor
        # at 120, readers of about 170 lines ran out of output and were resumed,
        # Li kaj ni PDF 14–27 and Korĵenkov PDF 36–44)
        tg = int(sys.argv[sys.argv.index("--target") + 1]) if "--target" in sys.argv else 80
        if "--rate-from" in sys.argv: RATE_FROM[0] = sys.argv[sys.argv.index("--rate-from") + 1]
        return propose_ranges(sys.argv[i + 1], tg, "--write-readers" in sys.argv)
    ap = argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("date", nargs="?")
    ap.add_argument("--stage", default=""); ap.add_argument("--config-from"); ap.add_argument("--out")
    ap.add_argument("--side-date", default="", help="the date of the roster, «out» list and namesakes files (default: the brief's date)")
    ap.add_argument("--partial", default="", help="a probe on part of the text: the reason, written into the brief's header")
    ap.add_argument("--per-reader", action="store_true", help="one brief per reader (facts-brief-DATE-N.md): its own text, range, «out» people and roster")
    ap.add_argument("--only", default="", help="fill only these readers (N,N,…), a probe")
    # another template (2026-10-18, the probe of the lean brief: the issue-date default, the short locator, the default
    # voice, no themes field; the editor): a file under ocr/method/, with the same placeholders
    ap.add_argument("--template", default="", help="a template file name under ocr/method/ in place of the default")
    # readers that write their own returns, one or several parts each (2026-10-20, the probe of fewer, longer readers;
    # the editor; Write approved)
    ap.add_argument("--write-returns", action="store_true", help="with --per-reader: each reader writes each part's return with Write, in pieces of at most 40 lines (facts-return-DATE-N-pK.md, joined by dowse-file-returns.py; agent type file-reader-writer); its final message only «Fino: N linioj»")
    ap.add_argument("--group", type=int, default=1, help="with --write-returns: K consecutive readers' parts to one reader (facts-brief-DATE-gA-B.md)")
    a = ap.parse_args()
    if (a.write_returns or a.group > 1) and not a.per_reader: sys.exit("refusing: --write-returns and --group need --per-reader")
    if a.group > 1 and not a.write_returns: sys.exit("refusing: --group needs --write-returns (a reader of several parts writes each part's return)")
    if a.template:
        global TPL
        TPL = os.path.join(G, "ocr", "method", os.path.basename(a.template))
        if not os.path.exists(TPL): sys.exit(f"refusing: no template {TPL}")
    refuse_superseded(TPL)
    D = os.path.join(G, "dowse", a.source)
    if a.config_from:
        p = os.path.join(D, "brief-config.json")
        if os.path.exists(p): sys.exit(f"refusing: {p} exists")
        json.dump(config_from(a.config_from), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("wrote", p); return
    out = a.out or os.path.join(D, f"facts-brief-{a.date}.md")
    if os.path.exists(out): sys.exit(f"refusing: {out} exists")
    # the brief filled before the file is opened: a refusal inside fill() used to leave an empty brief behind, which the
    # next run then refused as existing (found 2026-10-16 23:3x, testing the reader texts before the redowse)
    pdir = os.path.dirname(os.path.abspath(out))
    only = {int(x) for x in a.only.split(",")} if a.only else None
    partial = a.partial or (f"a probe of readers {a.only}" if only else "")
    text = fill(a.source, a.date, a.stage, a.side_date or a.date, partial, pdir)
    c = load_config(D)
    pf = pages_files([(x, open(os.path.join(G, x), encoding="utf-8").read()) for x in c["texts"]], a.date)
    if only: pf = {n: b for n, b in pf.items() if int(n.rsplit("-", 1)[1][:-4]) in only}
    briefs = per_reader(a.source, a.date, a.side_date or a.date, c, text, only, pdir) if a.per_reader else {out: text}
    if a.write_returns:
        briefs = writer_briefs(briefs, a.source, a.date, a.group, pdir)
    clash = [n for n in list(pf) + list(briefs) if os.path.exists(os.path.join(pdir, n))]
    if clash: sys.exit(f"refusing: {', '.join(clash[:5])} exist in {pdir}")
    for p, body in briefs.items():
        open(os.path.join(pdir, p), "x", encoding="utf-8").write(body)
    print(f"wrote {len(briefs)} brief(s)" + (f", {min(len(b) for b in briefs.values()):,}–{max(len(b) for b in briefs.values()):,} characters each" if a.per_reader else f": {out}"))
    for n, body in pf.items():
        open(os.path.join(pdir, n), "x", encoding="utf-8").write(body)
    print(f"wrote {len(pf)} readers' page files ({', '.join(f'{n.rsplit('-', 1)[1][:-4]}: {len(b.split()):,} words' for n, b in pf.items())})")

def per_reader(s, date, side, c, text, only, pdir):
    """ONE BRIEF PER READER (2026-10-18; Amerika Esperantisto's batch took 45% of the editor's weekly quota, every one of
    637 readers reading the whole 111 KB brief, in six chunks, and the 2,254-name roster; the editor): each reader's brief, facts-brief-<date>-N.md, with only its own text, its own range in «La legiloj», the
    «out» people and a roster of the names the name search found on its pages (and the next page, as its page file),
    the roster written as roster-reader-<side>-N.txt beside it. The strong tiers of the source's hits file, as the
    whole roster. -> {file name: brief}; the roster files are written here (create-only)."""
    import csv as _csv
    D = os.path.join(G, "dowse", s)
    hp = sorted(glob.glob(os.path.join(D, f"record-{side}*.hits.tsv")))
    if not hp: sys.exit(f"refusing: no record-{side}*.hits.tsv in {os.path.relpath(D, ROOT)} for the readers' rosters")
    _csv.field_size_limit(sys.maxsize)
    onpage = {}
    with open(hp[0], encoding="utf-8") as fh:
        for r in _csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if r["tier"] in ("exact", "near", "confusion") and r["page"].isdigit():
                onpage.setdefault((r["item"], int(r["page"])), set()).add(r["person"])
    rl = [l.rstrip("\n") for l in open(os.path.join(D, f"roster-reader-{side}.txt"), encoding="utf-8")]
    rhead, rlines = [l for l in rl if l.startswith("#")], [l for l in rl if l.strip() and not l.startswith("#")]
    outs = [l for l in open(os.path.join(D, f"out-list-{side}.md"), encoding="utf-8").read().split("\n") if l.startswith("- ")]
    # a reader's range may run across two texts («`A` PDF 49–50 + `B` PDF 1–6», a journal's issue across two pieces of
    # its volume, 2026-10-21): the whole entry, not its first part
    parts = {int(n): p for n, p in re.findall(r"(\d+): (`[^`]+` (?:PDF|¶) \d+–\d+(?: \+ `[^`]+` (?:PDF|¶) \d+–\d+)*)", c["readers"])}
    joined = "\n".join(os.path.join(G, x) for x in c["texts"])
    full_roster = os.path.join(D, f"roster-reader-{side}.txt")
    out_block = "\n".join(outs) if outs else "   (neniu el la registro troviĝis en la fonto)"
    briefs = {}
    for n, ranges in sorted(RANGES.items(), key=lambda x: int(x[0])):
        n = int(n)
        if only and n not in only: continue
        found = set()
        for path, lo, hi in ranges:
            item = os.path.basename(path)[:-4]
            for pg in range(lo, hi + 2): found |= onpage.get((item, pg), set())
        mine = [l for l in rlines if l.split(" | ")[0].strip() in found]
        rp = os.path.join(pdir, f"roster-reader-{date}-{n}.txt")   # by the brief's tag: two probes of one side date do not collide
        if os.path.exists(rp): sys.exit(f"refusing: {os.path.relpath(rp, ROOT)} exists")
        open(rp, "x", encoding="utf-8").write("\n".join(rhead) + f"\n# Nur la personoj trovitaj sur viaj paĝoj (legilo {n}): {len(mine)} el {len(rlines)}.\n" + "\n".join(mine) + "\n")
        fl = {x.lower() for x in found}
        def hit(line):
            o = re.sub(r"^- \*\*([^*]+)\*\*.*$", r"\1", line); o = re.sub(r" \(.*\)| de$", "", o).lower()
            return any(o == x or o in x.split("-") or o.replace(" ", "-") == x for x in fl)
        mo = [l for l in outs if hit(l)]
        b = text.replace(joined, "\n".join(os.path.join(G, p) for p, _lo, _hi in ranges))
        b = b.replace(full_roster, rp).replace(out_block, "\n".join(mo) if mo else "   (neniu el la registro troviĝis sur viaj paĝoj)")
        b = b.replace("## La legiloj\n\n" + c["readers"], "## La legiloj\n\n" + f"{n}: {parts.get(n, '')}.")
        own = os.path.basename(ranges[0][0])[:-4]   # the line's example locator names the reader's own item
        b = b.replace(f"{c['item']}, PDF N (prese M)", f"{own}, PDF N (prese M)").replace(f"{c['item']}, ¶ N", f"{own}, ¶ N")
        briefs[f"facts-brief-{date}-{n}.md"] = b
    return briefs

PIECE = 40   # fact lines a piece: at about 520 output tokens a line (the second probe), some 2–3 minutes of writing

WRITE_TOOLS = ("Uzu nur la ilojn Read kaj Write (Write nur por viaj raportoj, kiel dirite sube). Rulu neniujn ŝelajn "
               "komandojn, faru neniujn retajn serĉojn. Skribu viajn raportojn en Esperanto.")

def writer_briefs(briefs, s, date, group, pdir):
    """--write-returns [--group K] (2026-10-20, the probe of fewer, longer readers): from the per-reader briefs, a brief
    for each run of K consecutive readers (K = 1: one reader, one part, as now, but writing its return): the rules once,
    the parts' texts, rosters (one union file, roster-reader-DATE-gA-B.txt) and «out» people merged, every part listed
    in «La legiloj», and the ending replaced: each part's page file read whole, its return written with Write to
    dowse/<source>/facts-return-DATE-N.md before the next part is read, the final message only «Fino: N linioj». A
    part's «l. K» stays its own page file's line, so the returns file, check and expand as one reader's each. The
    agent type is file-reader-writer (Read and Write only). Refuses a return that exists. -> {file name: brief}.
    IN PIECES (2026-10-20, the second probe, PROBE-2026-10-20rstu.md; the editor): a part's return is written
    as pieces of at most PIECE fact lines, facts-return-DATE-N-pK.md (K = 1, 2 …), each as soon as its lines are ready,
    the last piece of a part with the three sections after the lines. A grouped reader's ten-minute write of a dense part
    outlasted the cache (about five minutes), and the next call wrote the whole conversation again; a short write keeps
    each call inside it. `dowse-file-returns.py` joins the pieces into facts-return-DATE-N.md."""
    D = os.path.join(G, "dowse", s)
    ns = sorted(int(re.search(r"-(\d+)\.md$", k).group(1)) for k in briefs)
    for n in ns:
        rp = os.path.join(D, f"facts-return-{date}-{n}.md")
        if os.path.exists(rp): sys.exit(f"refusing: {os.path.relpath(rp, ROOT)} exists")
        pp = os.path.join(D, f"facts-return-{date}-{n}-p1.md")
        if os.path.exists(pp): sys.exit(f"refusing: {os.path.relpath(pp, ROOT)} exists")
    out = {}
    # A JOURNAL'S GROUPS FOLLOW ITS ARTICLES (2026-10-21): where brief-config.json records how each range begins
    # («reader_starts», journal_ranges), a group of K closes only before a range that begins at an issue or at the top
    # of a page with a heading; before one that begins mid-page or mid-article it takes one more (K + 1 at most), so
    # that the article runs on inside one reader, who reads the parts in order
    rs = load_config(D).get("reader_starts", {}) if group > 1 else {}
    chunks, cur = [], []
    for n in ns:
        if cur and (len(cur) >= group + 1 or len(cur) >= group and rs.get(str(n), "issue") in ("issue", "whole", "top")):
            chunks.append(cur); cur = []
        cur.append(n)
    if cur: chunks.append(cur)
    if rs:
        bad = [ch[-1] + 1 for ch in chunks[:-1] if rs.get(str(ch[-1] + 1)) in ("mid", "forced")]
        print(f"groups: {len(chunks)} readers for {len(ns)} parts; a group ends before a range that begins mid-page or mid-article {len(bad)} times"
              + (f" (parts {', '.join(map(str, bad[:20]))})" if bad else ""))
    for chunk in chunks:
        bs = [briefs[f"facts-brief-{date}-{n}.md"] for n in chunk]
        b = bs[0]
        # the texts: the absolute paths under the «La fonto» paragraph, from every part, in order
        texts = []
        for x in bs:
            texts += [l for l in x.split("\n") if re.match(r"^/\S+/sources/(ocr-preferred|born-digital-text)/\S+\.txt$", l) and l not in texts]
        old_texts = [l for l in b.split("\n") if re.match(r"^/\S+/sources/(ocr-preferred|born-digital-text)/\S+\.txt$", l)]
        if old_texts:
            b = b.replace("\n".join(old_texts), "\n".join(texts), 1)
        # the «out» people: the list lines between the scope register's paragraph and «La iloj», merged
        def outs(x):
            seg = x.split("**La personoj ekster la amplekso laŭ la registro**", 1)[1].split("**La iloj kontrolas", 1)[0]
            return [l for l in seg.split("\n") if l.startswith("- ") or l.startswith("   (neniu")]
        merged = []
        for x in bs:
            merged += [l for l in outs(x) if l.startswith("- ") and l not in merged]
        b = b.replace("\n".join(outs(b)), "\n".join(merged) if merged else "   (neniu el la registro troviĝis sur viaj paĝoj)", 1)
        # the roster: one file, the union of the parts' rosters (their headers once)
        if len(chunk) > 1:
            rps = [os.path.join(pdir, f"roster-reader-{date}-{n}.txt") for n in chunk]
            head, body = [], []
            for p in rps:
                for l in open(p, encoding="utf-8").read().split("\n"):
                    if l.startswith("#"):
                        if l not in head and not l.startswith("# Nur la personoj trovitaj"): head.append(l)
                    elif l.strip() and l not in body: body.append(l)
            up = os.path.join(pdir, f"roster-reader-{date}-g{chunk[0]}-{chunk[-1]}.txt")
            if os.path.exists(up): sys.exit(f"refusing: {os.path.relpath(up, ROOT)} exists")
            open(up, "x", encoding="utf-8").write("\n".join(head) + f"\n# Nur la personoj trovitaj sur viaj paĝoj (partoj {', '.join(map(str, chunk))}): {len(body)}.\n" + "\n".join(body) + "\n")
            b = b.replace(rps[0], up)
        # the tools, the page file sentence, the report and the ending
        b = re.sub(r"Uzu nur la ilon Read\..*?Skribu ĝin en Esperanto\.", WRITE_TOOLS, b, count=1, flags=re.S)
        b = b.replace("kie N estas via numero", "kie N estas la numero de la parto")
        rpath = os.path.join(D, f"facts-return-{date}-N-pK.md")
        k = len(chunk)
        new_end = (
            f"**Viaj partoj kaj la raportoj:** vi legas {'unu parton' if k == 1 else f'{k} partojn, unu post la alia, en la ordo de la sekcio «La legiloj»'}. "
            f"Por ĉiu parto: legu ĝian paĝ-dosieron (`facts-pages-{date}-N.txt`, N la numero de la parto) tute; skribu ĝian raporton "
            f"per la ilo Write **en pecoj**, al `{rpath}` (N la numero de la parto; K = 1, 2, 3 … la numero de la peco): "
            f"ĉiu peco havas ne pli ol {PIECE} liniojn de faktoj, la linioj de nur tiu parto, en la ordo de la paĝoj; skribu ĉiun pecon, "
            "tuj kiam ĝiaj linioj estas pretaj, kaj daŭrigu la legadon poste: neniam la tutan raporton de densa parto en unu skribo "
            "(longa skribo perdas la kaŝmemoron kaj kostas ĉion denove). La lasta peco de la parto havas post siaj linioj, aparte: "
            "(1) la personoj de la listo «ekster», kiujn vi preterlasis, kaj tiuj, kiujn vi trovis ekster la amplekso, "
            "kun paĝo kaj kialo; (2) lokoj, kie la OCR estas tro misa por legi fakton, unu linio ĉiu; (3) proponoj por la registro de nomoj"
            + (". Nur post tio legu la sekvan parton. La lokindiko `l. K` estas ĉiam la linio en la paĝ-dosiero de la sama parto" if k > 1 else "")
            + ". Skribu per Write nur tiujn dosierojn, ĉiun unufoje, kaj neniun alian.\n\n"
            "**Fine:** via fina mesaĝo estas nur unu linio, `Fino: X linioj` (X la sumo de la linioj, kiujn vi skribis); ne ripetu la raportojn en ĝi.")
        b = re.sub(r"\*\*La raporto:\*\*.*?\*\*Fine, en du paŝoj:\*\*[^\n]*", new_end.replace("\\", "\\\\"), b, count=1, flags=re.S)
        legiloj = []
        for x in bs:
            legiloj += [l for l in re.split(r"## La leg(?:iloj|antoj)", x, maxsplit=1)[1].strip().split("\n") if l.strip()]
        b = re.split(r"## La leg(?:iloj|antoj)", b, maxsplit=1)[0] + "## La legiloj\n\n" + "\n".join(legiloj) + "\n"
        if k > 1:
            b = b.replace("## La briefo, kiel donita al ĉiu legilo (la paĝoj malsamas)",
                          f"## La briefo, kiel donita al ĉiu legilo (la paĝoj malsamas; ĉi tiu legilo: {k} partoj)", 1)
        name = f"facts-brief-{date}-{chunk[0]}.md" if k == 1 else f"facts-brief-{date}-g{chunk[0]}-{chunk[-1]}.md"
        out[name] = b
    # the workflow's arguments (tools/workflows/carney-readers.js, the groups form), printed for the launch
    groups = [str(ch[0]) if len(ch) == 1 else f"{ch[0]}-{ch[-1]}" for ch in chunks]
    print("workflow args: " + json.dumps({"dir": D, "tag": date, "groups": groups}, ensure_ascii=False))
    return out

if __name__ == "__main__":
    # THE DOWSE'S LOCK (2026-10-26): the readers' page files are copied from the preferred texts, so the fill holds
    # dowse-<pid>.lock and is refused while Miles's chain holds the corpus (tools/corpus_locks.py).
    with CL.held("dowse"):
        main()
