#!/usr/bin/env python3
"""ocr-dowse — the «dowse» query (plan item W5): find names (or, with --stem, theme words) in the geniza corpus, each
item searched in the text its signed line prescribes, and say for every item what a silence may claim.

TWO WAYS TO RUN IT (the editor ruled on 2026-10-06 12:3x–12:4x that the roster against one run is how it has been run
and is the primary search; the one-name-over-the-corpus way is kept for others who may want it):

    ROSTER × RUN (the primary way): every name of a roster against the items of one journal run
    tools/ocr-dowse.py --roster <names file> --items "<pattern>[,<pattern>…]" --write <new record.md>

    ONE NAME × THE WHOLE CORPUS
    tools/ocr-dowse.py "<form>" ["<form>" …] --write <new record.md>

A roster file has one person per line: their forms separated by « | » («Eroŝenko | Eroshenko | Ерошенко»); a line
starting «#» is a comment. On the command line, every argument is one form of ONE name. An item is a hit for a person
if any of their forms is found. --items takes item-name patterns (shell style: «LEsperantiste.1907.*», «larevuo.*»),
comma-separated, or @file with one pattern per line. Reads only; writes two new files (refused if either exists): the
record (.md) and every hit before any exclusion (.hits.tsv).

WHAT IT SEARCHES, per item of the CURRENT ledger (named in the status record, an internal record, not published):
  - the text its SIGNED line names (the signed acceptance-line files, internal records, not published; the union; where
    an item has lines in two files, the later file's line holds): the search text `ocr-rendersearch/<item>.txt`, or for
    SPECIAL HANDLING the every-reading text `ocr-rendersearch-all/<item>.txt`;
  - an item with no signed line: its search text, and its every-reading text where one exists (presence only);
  - always, where they exist, its texts in another alphabet: `ocr-rendersearch-rus/`, `-hye/`, `-kat/`.
HOW: tools/ocr_index.py — each text is indexed ONCE (every word form with its pages, the parts of hyphenated words,
adjacent pairs, line-end fragments), and every name is matched against the index by the name search's own rules
(tools/ocr-name-search.py; the index gives exactly what find() gives, checked by tools/ocr-index-check.py). --stem: a
theme word, matched as a folded PREFIX of a word, no fuzziness.
NO CAP on the search: every item is searched and every hit kept. THE RECORD sorts hits by tier (exact · near ·
confusion · translit · small caps and run-ins · join), counts PAGES as well as hits (an every-reading text holds a
printed name once per reading), gives each matched form its corpus count (the lexicon) and, up to --where-max hits of a
form (default: ALL in the roster way, 10 over the whole corpus), WHERE it is; and, for each silent item, what its
silence may claim. Every hit is a CANDIDATE until confirmed on the page image.

READING AN ITEM, per person (the editor's rule of 2026-10-06 17:3x, in docs/SEARCHING.md, that the tiers are not walked
down until something turns up): the item's STRONGEST tier decides. Exact, near or confusion: a candidate. Translit hits in an
alphabet the person was given no form in (Latin forms only, hits in Cyrillic; or Cyrillic forms only, hits in Latin —
symmetric, the editor 2026-10-06 18:2x): UNDERSPECIFIED, wherever the reading stopped — give the form in that alphabet
and search again; the item is neither present nor silent until then. Translit first for a person given both
alphabets: CONFIRM — almost certainly noise, but neither present nor silent until judged (a «confirmed» page, a form
set aside, or a cutoff above translit; the editor ruled on 2026-10-06 18:3x to err on the side of caution and ask for
confirmation). Small caps and run-ins,
or join: PRESUMED NOISE, counted as no hit unless a page is confirmed, with its page count shown (0 · 0 · 0 · 1 is
worth reading; hundreds are not pursued by default). Tiers below the person's cutoff are not read at all.

JUDGEMENTS (--judgements FILE), one line per person, fields separated by « | », all but the person optional:
    Bein | stop: exact | exclude: кап, кат | exclude-as-read: kabe | confirmed: RuslandaEsperantisto1907.1 p.20 | why: …
«stop» is the tier the reading stopped at (default: join, i.e. every tier, by the rule above); «exclude» and
«exclude-as-read» act for THAT person only (--exclude and --exclude-as-read act for everyone); a «confirmed» page makes
its item present whatever its tier. The record prints each person's judgement, and their silences follow their cutoff;
the silent counts at the exact-only and up-to-confusion cutoffs are given beside it.
"""
import argparse, collections, datetime, fnmatch, glob, importlib.util, os, random, re, resource, sys, unicodedata
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
sys.path.insert(0, HERE)
import cupel_workers as CW   # the core dial: one slot per worker task while geniza/ocr/CORE-DIAL exists
S = os.path.join(G, "sources")
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)
sys.path.insert(0, HERE)
import ocr_index as IX  # noqa: E402
import born_digital_lines as BDL  # noqa: E402  (the born-digital lists and texts, 2026-10-10)
import corpus_locks as CL  # noqa: E402  (the dowse's lock against Miles's chain, 2026-10-26: geniza/ocr/locks/)
_BDSEC = {}   # born-digital item → {¶: section}, filled in main(); its hits cite «¶ N», not a PDF page
_BDPAGED = {}   # a PAGED born-digital item (a typed PDF, «pages: pdf») → its PDF pages; searched and cited like an OCR text


# MODERN METADATA (2026-10-10; the editor noted that modern initial metadata recurs and that each source may differ in
# how much of it there is, and approved the proposal): the pages and ¶ of a later hand (ÖNB cover sheets, the
# Tekstaro's headers, Google and archive.org pages), from the newest geniza/ocr/runs/OCR-MODERN-METADATA-*.tsv
# (tools/ocr-modern-metadata.py). Their hits stay in the hits table (column «metadata»), are reported apart, and are
# left out of the reading and of silences.
def modern_metadata():
    c = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-MODERN-METADATA-*.tsv")))
    out = {}
    for l in (open(c[-1], encoding="utf-8") if c else []):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 4 and not l.startswith("#") and x[0] != "item" and x[2].isdigit():
            out[(x[0], int(x[2]))] = x[3]
    return out, (os.path.basename(c[-1]) if c else None)


# THE DATE CHECK (2026-10-10, under the same approval; a wider net, from an internal record of 2026-10-10, not published):
# a person's birth year from their profile, the EARLIEST of: a fact line whose text opens with «born»/«naskiĝis» (its
# date is the birth); «born»/«naskiĝis» with a year in the line; life dates «(1891–1967)» right after the person's
# own name. The earliest, so that a stray year can only under-flag. A presence in an item written before that year is
# flagged in the record, to be read: a modern note the metadata table missed, an OCR misreading, or a namesake.
_BIRTH = {}
_B1 = re.compile(r"\*\*(1[5-9]\d\d|20[0-2]\d)[^*]*\*\*\s*·\s*(?:born|naskiĝis)\b", re.I)
_B2 = re.compile(r"\b(?:born|naskiĝis)\b[^.;«»|]{0,30}?\b(1[5-9]\d\d|20[0-2]\d)\b", re.I)


def birth_year(label):
    if label in _BIRTH: return _BIRTH[label]
    f = os.path.join(G, "profiles", label + ".md"); ys = []
    if os.path.exists(f):
        t = open(f, encoding="utf-8").read()
        m = re.match(r"# (.+?) —", t); name = m.group(1) if m else ""
        sur = re.split(r"[\s(]", name.strip())[0].strip(",") if name else ""
        for l in t.splitlines():
            if not l.startswith("- $$$"): continue
            ys += [int(y) for y in _B1.findall(l)] + [int(y) for y in _B2.findall(l)]
            if sur and len(sur) > 2:
                ys += [int(y) for y in re.findall(re.escape(sur) + r"[^()]{0,30}?\((1[5-9]\d\d|20[0-2]\d)\s*[–-]", l, re.I)]
    _BIRTH[label] = min(ys) if ys else None
    return _BIRTH[label]


def pl(item, page):
    """«item p.N», or «item ¶ N» for a born-digital item (its «pages» are paragraphs), with the scan's PDF page where a
    page map gives one: «item ¶ N (PDF P of <scan>)» (2026-10-10 22:23, on the editor's 21:1x ruling that the page
    number always comes through; the citations already carried it, the short «where» lists did not)."""
    if item in _BDSEC:
        bp = bd_pdf(item, page)
        return f"{item} ¶ {page}" + (f" ({bp})" if bp else "")
    return f"{item} p.{page}"


def read_text(f):
    """a searched text: as filed, or, for a born-digital text, with each paragraph as a «page» (¶ N)."""
    t = open(f, encoding="utf-8", errors="ignore").read()
    return BDL.paged(t) if BDL.is_bd_text(f) and not BDL.PAGE.search(t) else t   # a paged typed PDF keeps its pages


_PMAP = {}
def bd_pdf(item, para):
    """«PDF 287 of <scan>» for a born-digital ¶ (tools/bd-page-map.py, ocr/page-maps/<item>.tsv; the editor ruled on
    2026-10-10 21:1x that the page number must always come through, even though an epub is born digital), with the map's
    status where it is not «placed»; "" where the item has no map or the ¶ no page."""
    if item not in _PMAP:
        d = os.path.join(G, "ocr", "page-maps"); m, scan = {}, ""
        for l in (open(os.path.join(d, "SUMMARY.tsv"), encoding="utf-8") if os.path.exists(os.path.join(d, "SUMMARY.tsv")) else []):
            x = l.rstrip("\n").split("\t")
            if x[0] == item and len(x) > 1: scan = x[1]
        f = os.path.join(d, item + ".tsv")
        for l in (open(f, encoding="utf-8") if os.path.exists(f) else []):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 4 and x[0].isdigit(): m[int(x[0])] = (x[2], x[3])
        _PMAP[item] = (m, scan)
    m, scan = _PMAP[item]
    pg, st = m.get(int(para), ("", ""))
    if not pg:
        return ""
    return f"PDF {pg}" + (f" of {scan}" if scan else "") + ("" if st == "placed" else f" ({st})")

STRONG = ("exact", "near", "confusion")
SCRR = "small caps and run-ins"  # tier 5, named by both its contents (the editor 2026-10-06 18:0x; was «other»)
TIERS = ("exact", "near", "confusion", "translit", SCRR, "join", "stem")
_CYR = re.compile("[а-яёѣіѳѵ]")


def read_judgements(path):
    """person → {stop, exclude, exclude-as-read, confirmed, why} (see the module docstring)."""
    out = {}
    for l in (open(path, encoding="utf-8") if path else []):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        x = [p.strip() for p in l.split(" | ")]
        j = {"stop": "join", "exclude": "", "exclude-as-read": "", "confirmed": "", "assign": "", "not": "",
             "ambiguous": "", "default": "", "why": ""}
        for f in x[1:]:
            k, _, v = f.partition(":")
            if k.strip() not in j:
                sys.exit(f"judgements: unknown field «{k.strip()}» in: {l}")
            j[k.strip()] = v.strip()
        if j["stop"] == "other":
            j["stop"] = SCRR
        if j["stop"] not in TIERS[:6]:
            sys.exit(f"judgements: stop must be one of {', '.join(TIERS[:6])}: {l}")
        for k in ("confirmed", "assign", "not", "ambiguous"):
            j[k] = {(m.group(1), int(m.group(2))) for m in re.finditer(r"(\S+) p\.?\s*(\d+)", j[k])}
        out[x[0]] = j
    return out


def reading(pages_by_tier, confirmed, stop, missing_script):
    """one person in one item: what the item says, by its strongest tier at or above the cutoff (module docstring).
    UNDERSPECIFIED: translit hits in an alphabet the person was not given any form in (Latin forms only and Cyrillic
    hits, or the reverse; the editor ruled on 2026-10-06 18:2x that this is a request to respecify), wherever the reading
    stopped. Translit first for a person given both alphabets: CONFIRM — almost certainly noise, but not presumed so
    (the editor ruled on 2026-10-06 18:3x to err on the side of caution and ask for confirmation)."""
    if confirmed:
        return "confirmed on the image"
    hit = [t for t in TIERS[:TIERS.index(stop) + 1] if pages_by_tier.get(t)]
    if not hit:
        return "underspecified" if missing_script else "silent"
    b = hit[0]
    if b in ("exact", "near", "confusion"):
        return "candidate" if b != "exact" else "exact"
    if b == "translit":
        return "underspecified" if missing_script else "confirm"
    return "presumed noise"


def current_ledger():
    st = open(os.path.join(G, "OCR-STATUS.md"), encoding="utf-8").read()
    return os.path.join(G, "ocr", "runs", re.search(r"`(OCR-ABSENCE-LEDGER-[^`]+\.tsv)`", st).group(1))


def signed_lines():
    """item → (file, line fields); later files win (their names sort by date). A `WITHDRAWN:` line (2026-10-07,
    `ocr-acceptance-lines.py --withdraw`, on the editor's signature) cancels the item's earlier line: it is then unsigned."""
    out = {}
    # in geniza/ocr/lines/ since 2026-10-10 (the top level still read during the move); ordered by file name, whichever folder
    for f in sorted(glob.glob(os.path.join(G, "ocr", "lines", "OCR-ACCEPTANCE-LINES-*SIGNED*.txt")) +
                    glob.glob(os.path.join(G, "OCR-ACCEPTANCE-LINES-*SIGNED*.txt")), key=os.path.basename):
        here = {}
        for l in open(f, encoding="utf-8"):
            if l.startswith("ACCEPTED: "):
                x = [p.strip() for p in l[len("ACCEPTED: "):].rstrip("\n").split(" | ")]
                here.setdefault(x[0], []).append(x)
            elif l.startswith("WITHDRAWN: "):
                out.pop(l[len("WITHDRAWN: "):].split(" | ")[0].strip(), None)
        # SEGMENTS (2026-10-09): a file may sign an item in several lines, one per scoped stretch (cupel batch 1's
        # Li kaj Ni and Waringhien: two each). Until today only the last was kept, so their first stretches were unseen.
        # The latest file that signs an item holds ALL its lines; line[1] is the first, line[2] the list of all.
        for it, xs in here.items():
            out[it] = (os.path.basename(f), xs[0], xs)
    return out


# SILENCE COVER (2026-10-09, approved by the editor, all three parts, on a scope proposal (an internal record,
# 2026-10-09, not published), recast; the editor at 12:3x urged it, as the problem was about to arise). A signed line's
# conditions, read into the PDF pages
# over which a silence counts: the SCOPE range (or «SCOPE: only …» with its scan pages), less the pages its exceptions
# name (advertisement, LOST and MINOR pages); a PART page stays in, with its note; «NOT IN SCAN» names printed pages the
# scan lacks, so the text is not whole. Every other condition (a side or script, SECONDARY, «search every reading») is
# kept as printed and named «read by hand».
_PAGE_EXCL = re.compile(r"^(?:mundane ADVERTISEMENT page\(s\)|LOST|MINOR) p\.([\d,]+)")


def _ranges(ps):
    out, run = [], []
    for p in sorted(ps):
        if run and p == run[-1] + 1: run.append(p)
        else:
            if run: out.append(run)
            run = [p]
    if run: out.append(run)
    return ", ".join(f"{r[0]}–{r[-1]}" if len(r) > 1 else f"{r[0]}" for r in out)


def silence_cover(line):
    """Every segment of a line (signed_lines()[item]); one segment is the common case."""
    xs = line[2] if len(line) > 2 else [line[1]]
    if len(xs) == 1:
        return _cover_one(line[0], xs[0])
    parts = [_cover_one(line[0], x) for x in xs]
    n = next((c["n"] for c in parts if c["n"]), None)
    pages = set().union(*(c["pages"] for c in parts))
    gaps = [g for c in parts for g in c["gaps"]]
    whole = bool(n) and len(pages) == n and not gaps
    desc = (f"silent over all {n} PDF pages" if whole else f"silent over {len(pages)} of {n} PDF pages, in "
            f"{len(parts)} segments: ") + " | ".join(f"[{c['seg']}] {c['desc']}" for c in parts)
    return {"n": n, "pages": pages, "whole": whole, "gaps": gaps,
            "kept": [k for c in parts for k in c["kept"]], "excl": [e for c in parts for e in c["excl"]],
            "hand": [h for c in parts for h in c["hand"]], "kind": [k for c in parts for k in c["kind"]], "desc": desc}


def _cover_one(fname, x):
    """→ dict: n (PDF pages of the item), pages (the PDF pages a silence covers), whole (all pages, the text complete),
    gaps (printed pages not in the scan), kept (PART notes), excl (excluded pages, with why), hand (conditions not about
    pages, to be read by hand), and desc, the one-line account the record prints."""
    m = re.search(r"of (\d+)$", x[1]) or re.match(r"(\d+) pp", x[1])
    n = int(m.group(1)) if m else None
    cond = x[4].replace("conditions: ", "")
    pages = set(range(1, n + 1)) if n else set()
    gaps, kept, excl, hand, kind, label = [], [], [], [], [], []
    if cond != "none":
        for part in re.split(r";\s+(?=[A-Z0-9])", cond):
            part = re.sub(r";\s*none$", "", part)   # «PRIMARY; none»: the line tool's empty exception list
            m1 = re.match(r"SCOPE: absence admissible on pages (\d+)–(\d+) only(?: \(\d+ pp\))?(?: — (.+))?", part)
            m2 = re.search(r"scan pp\. (\d+)–(\d+)", part) if part.startswith("SCOPE: only") else None
            m3 = _PAGE_EXCL.match(part)
            if m1:
                pages &= set(range(int(m1.group(1)), int(m1.group(2)) + 1))
                if m1.group(3): label.append(m1.group(3))
            elif m2:
                pages &= set(range(int(m2.group(1)), int(m2.group(2)) + 1)); hand.append(part)
            elif m3:
                ps = {int(v) for v in m3.group(1).split(",") if v}; pages -= ps
                excl.append(f"PDF p. {_ranges(ps)} ({part.split(' p.')[0].lower()})")
            elif part.startswith("NOT IN SCAN:"):
                gaps.append(part[len("NOT IN SCAN: "):])
            elif part.startswith("PART p."):
                kept.append(part)
            elif part.strip() in ("none", ""):
                continue
            elif part.startswith(("PRIMARY", "SECONDARY LITERATURE")):
                kind.append(part.strip())
            else:
                hand.append(part)
    whole = bool(n) and len(pages) == n and not gaps
    u = "paragraphs" if x[1].lstrip().startswith("¶") else "PDF pages"   # a born-digital text: ¶ N; a paged typed PDF: PDF pages
    if not n:
        desc = "its page count not read from the line: read the conditions by hand"
    elif whole:
        desc = f"silent over all {n} {u}"
    else:
        desc = f"silent over {u} {_ranges(pages)} ({len(pages)} of {n})" if pages else f"no {u[:-1]} admissible of {n}"
    if excl: desc += "; excluded: " + "; ".join(excl)
    if gaps: desc += "; NOT IN THE SCAN: " + "; ".join(gaps)
    if kept: desc += "; " + "; ".join(kept)
    if kind: desc += "; kind: " + "; ".join(kind)
    if hand: desc += "; read by hand: " + "; ".join(hand)
    seg = (_ranges(pages) if pages else "-") + (f" {label[0]}" if label else "")
    return {"n": n, "pages": pages, "whole": whole, "gaps": gaps, "kept": kept, "excl": excl, "hand": hand,
            "kind": kind, "desc": desc, "seg": seg}


# COPIES OF ONE WORK (2026-10-09; renamed from WITNESSES 2026-10-10, in the terms then agreed: a *copy*, ekzemplero, is
# the same work held more than once, and a fact found in several copies is ONE source with several locators; a *witness*,
# atestanto, is a different work attesting the same fact, which this table is not). The editor ruled on 2026-10-09 12:4x
# that the point of triangulation is that, once the two witnesses are shown between them to cover the entire text at
# absence quality, absence in either becomes absence of the entire item; at 13:0x, that the secondary witness to a text
# is a separate matter of triangulation; and on 2026-10-10 05:1x, on copies across born-digital texts and scans, that
# they are a desired step. Each copy: the item, the stretch of it that holds the work (PDF pages, or ¶ for a born-digital text;
# None = the whole item), and its rank. «triangulated» is the editor's ruling on a page-by-page coverage check;
# «whole_in» names a copy signed whole on its own (a born-digital text): silence in every copy searched, that one among
# them, is then absence for the whole work with no triangulation needed. The born-digital ↔ scan stretches were found by
# content (2026-10-10: each text's paragraphs looked up in the scan's OCR, 24-letter windows; kept where 77–100% of a
# text's paragraphs fall in one unbroken run of PDF pages); a stretch's first and last page may share a page with the
# works on either side.
# «same_text» (the editor 2026-10-20 16:2x, approving kind 0 of a method proposal (an internal record, 2026-10-20, not
# published), noting the real possibility that two copies differ in content as different editions, and that the same
# applies to translations): the
# groups of copies that hold ONE text (one edition or printing, scanned or typed twice). A copy in no group is a text of
# its own (another edition, a translation, or not yet checked: «when in doubt, kind 0»). Only copies in one group may
# ever have pages read once instead of twice, and only once the pair is ruled triangulated; across groups, never.
COPIES = [
    {"work": "Privat, Historio de la lingvo Esperanto, vol. 2: La movado 1900–1927 (1927)", "repeats": [("338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat", (51, 63), (38, 50), "the Scribd copy scans PDF 38–50 twice: PDF 51–63 are the same pages again, one for one (PDF n = PDF n−13; 53–54 near blank in both); checked 2026-10-20 17:3x by four-word runs shared page to page; the repeat reads a little better on PDF 51, 52, 57 and 63 (word-list share 0.91, 0.98, 0.91, 0.96 against 0.87, 0.91, 0.84, 0.92)", (51, 52, 57, 63))], "same_text": [['privat-historio-1927-vol2', '338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat']],
     "copies": [("privat-historio-1927-vol2", None, "primary"),
                ("338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat", (40, 150), "secondary")],
     "triangulated": "decided by the editor, 2026-10-09, on the coverage check (every printed page of "
                     "vol. 2 held by at least one admissible witness; geniza/sources/ocr-work/privat-triangulation-2026-10-09/)",
     "note": "the old copy lacks printed pp. 44–45 and 80–81; the REU copy is weak at the gutter on printed pp. 36–37, "
             "40–41, 68–69, 82–83, 164–165"},
    {"work": "Zamenhof, Originala Verkaro, ed. Dietterle (1929)", "same_text": [['OV pli eta 2', 'tekstaro-originala-verkaro']],
     "copies": [("OV pli eta 2", None, "scan, the whole book"),
                ("tekstaro-originala-verkaro", None, "born-digital, the Tekstaro's selection (it leaves out what the Tekstaro holds apart)")],
     "whole_in": "OV pli eta 2", "triangulated": ""},
    {"work": "Zamenhof, Aldono al la Dua Libro (1888)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: Warsaw 1888, from ÖNB's scan, with -AM forms put for the original -AN: another edition than OV 1929 (kind 0)",
     "copies": [("tekstaro-aldono-dua-libro", None, "born-digital"), ("OV pli eta 2", (31, 42), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-aldono-dua-libro", "triangulated": ""},
    {"work": "Zamenhof, Fundamento de Esperanto: Antaŭparolo (1905)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: Marmande 1968 (Esperantaj Francaj Eldonoj): another edition (kind 0)",
     "copies": [("tekstaro-fundamenta-antauparolo", None, "born-digital"), ("OV pli eta 2", (45, 49), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-fundamenta-antauparolo", "triangulated": ""},
    {"work": "La Esperantisto, the texts held in the Tekstaro (1889–1895)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: the journal itself, 1889–1895: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-la-esperantisto", None, "born-digital"), ("OV pli eta 2", (67, 71), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-la-esperantisto", "triangulated": ""},
    {"work": "Zamenhof, Esenco kaj estonteco de la ideo de lingvo internacia (1898/1900)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: UEA, Rotterdam 1968: another edition than OV 1929; the Russian copies translations (kind 0)",
     "copies": [("tekstaro-esenco-kaj-estonteco", None, "born-digital"), ("OV pli eta 2", (278, 314), "scan, in Originala Verkaro 1929"),
                ("reu-bofron-esenco-1906", None, "scan, the Russian translation, Kharkov 1906"),
                ("reu-borfon_esenco_kaj_futuro_1909", None, "typed, the Russian translation, Irkutsk 1909, with Perrot's preface, his list of periodicals and two poems by Devjatnin (his own: they show in the one-copy list)")],
     "whole_in": "tekstaro-esenco-kaj-estonteco", "triangulated": "", "note": "Russian copies added: decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only"},
    {"work": "Zamenhof, Dogmoj de Hilelismo (1906)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1906, the first edition: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-dogmoj-de-hilelismo", None, "born-digital"), ("OV pli eta 2", (315, 323), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-dogmoj-de-hilelismo", "triangulated": ""},
    {"work": "Zamenhof, Homaranismo (1906)", "same_text": [['tekstaro-homaranismo-1906', 'OV pli eta 2']], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: Ferdinand Hirt & Sohn, Leipzig 1929, that is Originala Verkaro itself: the Tekstaro text and the OV scan one text; the Russian version a translation (kind 0 against both)",
     "copies": [("tekstaro-homaranismo-1906", None, "born-digital"), ("OV pli eta 2", (316, 330), "scan, in Originala Verkaro 1929"),
                ("reu-homaranizm_1906", None, "typed, the Russian version, St Petersburg 1906")],
     "whole_in": "tekstaro-homaranismo-1906", "triangulated": "", "note": "Russian copy added: decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only"},
    {"work": "Zamenhof, Aldono al la Dogmoj de Hilelismo (1906)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1906: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-aldono-al-la-dogmoj-de-hilelismo", None, "born-digital"), ("OV pli eta 2", (323, 323), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-aldono-al-la-dogmoj-de-hilelismo", "triangulated": ""},
    {"work": "Zamenhof, Pri la homaranismo (1906)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1906: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-pri-la-homaranismo", None, "born-digital"), ("OV pli eta 2", (331, 337), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-pri-la-homaranismo", "triangulated": ""},
    {"work": "Zamenhof, Nefermita letero al s-ro de Beaufront (1906)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1906: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-nefermita-letero-al-beaufront", None, "born-digital"), ("OV pli eta 2", (338, 340), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-nefermita-letero-al-beaufront", "triangulated": ""},
    {"work": "Zamenhof, Deklaracio pri Homaranismo (1913)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: Madrid 1913 (Homaro): the first edition, not OV 1929's text (kind 0)",
     "copies": [("tekstaro-homaranismo-1913", None, "born-digital"), ("OV pli eta 2", (341, 345), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-homaranismo-1913", "triangulated": ""},
    {"work": "Zamenhof, Gentoj kaj lingvo internacia (1911)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1911, from ÖNB's scan: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-gentoj-kaj-lingvo-internacia", None, "born-digital"), ("OV pli eta 2", (347, 355), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-gentoj-kaj-lingvo-internacia", "triangulated": ""},
    {"work": "Zamenhof, Post la granda milito (1914/15)", "same_text": [], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: 1915 and A. Paolet, S. Vito al Tagliamento 1922: not OV 1929's text (kind 0)",
     "copies": [("tekstaro-post-la-granda-milito", None, "born-digital"), ("OV pli eta 2", (356, 359), "scan, in Originala Verkaro 1929")],
     "whole_in": "tekstaro-post-la-granda-milito", "triangulated": ""},
    {"work": "Zamenhof, the congress speeches (1904–1913)", "same_text": [['tekstaro-paroladoj-de-zamenhof', 'OV pli eta 2']], "texts_checked": "checked 2026-10-20 16:3x, by the Tekstaro text's own «Eldonado:» line: Ferdinand Hirt & Sohn, Leipzig 1929 (OV): the Tekstaro text and the OV scan one text; the Russian copy a translation (kind 0)",
     "copies": [("tekstaro-paroladoj-de-zamenhof", None, "born-digital"), ("OV pli eta 2", (361, 415), "scan, in Originala Verkaro 1929"),
                ("reu-zamenhofaj_paroladoj", None, "typed, the speeches in Russian (two in Esperanto), Sidorov collection")],
     "whole_in": "tekstaro-paroladoj-de-zamenhof", "triangulated": "", "note": "Russian copy added: decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only"},
    {"work": "Dyer, The Problem of an International Auxiliary Language and its Solution in Ido (1923)", "same_text": [['dyer-problem-ido-1923', 'Problem Of An International Auxiliary Language, The - Luther H. Dyer']], "texts_checked": "checked 2026-10-20 16:3x, by text: 82% of the typed text's five-word runs found in the scan's OCR, the preface word for word: one text",
     "copies": [("dyer-problem-ido-1923", None, "born-digital, the typed web edition (61,103 words)"),
                ("Problem Of An International Auxiliary Language, The - Luther H. Dyer", None, "scan (66,448 words of OCR)")],
     "whole_in": "dyer-problem-ido-1923", "triangulated": "",
     "note": "paired 2026-10-10 18:3x, as decided by the editor (both copies dated 1922–23, PRIMARY by the topic ruling)"},
    {"work": "The Esperantist, vol. 1 no. 1", "same_text": [['theesperantist-pg-1903-v1n01', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n01", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (11, 29), "scan, PDF pages 11–29")],
     "whole_in": "theesperantist-pg-1903-v1n01", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 2", "same_text": [['theesperantist-pg-1903-v1n02', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n02", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (31, 48), "scan, PDF pages 31–48")],
     "whole_in": "theesperantist-pg-1903-v1n02", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 3", "same_text": [['theesperantist-pg-1903-v1n03', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n03", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (49, 66), "scan, PDF pages 49–66")],
     "whole_in": "theesperantist-pg-1903-v1n03", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 4", "same_text": [['theesperantist-pg-1903-v1n04', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n04", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (67, 84), "scan, PDF pages 67–84")],
     "whole_in": "theesperantist-pg-1903-v1n04", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 5", "same_text": [['theesperantist-pg-1903-v1n05', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n05", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (86, 108), "scan, PDF pages 86–108")],
     "whole_in": "theesperantist-pg-1903-v1n05", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 6", "same_text": [['theesperantist-pg-1903-v1n06', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n06", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (109, 126), "scan, PDF pages 109–126")],
     "whole_in": "theesperantist-pg-1903-v1n06", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 7", "same_text": [['theesperantist-pg-1903-v1n07', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n07", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (127, 144), "scan, PDF pages 127–144")],
     "whole_in": "theesperantist-pg-1903-v1n07", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 8", "same_text": [['theesperantist-pg-1903-v1n08', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n08", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (145, 162), "scan, PDF pages 145–162")],
     "whole_in": "theesperantist-pg-1903-v1n08", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 9", "same_text": [['theesperantist-pg-1903-v1n09', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n09", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (163, 180), "scan, PDF pages 163–180")],
     "whole_in": "theesperantist-pg-1903-v1n09", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 10", "same_text": [['theesperantist-pg-1903-v1n10', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n10", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (181, 198), "scan, PDF pages 181–198")],
     "whole_in": "theesperantist-pg-1903-v1n10", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 11", "same_text": [['theesperantist-pg-1903-v1n11', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n11", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (199, 216), "scan, PDF pages 199–216")],
     "whole_in": "theesperantist-pg-1903-v1n11", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 12", "same_text": [['theesperantist-pg-1903-v1n12', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n12", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (217, 231), "scan, PDF pages 217–231")],
     "whole_in": "theesperantist-pg-1903-v1n12", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 13", "same_text": [['theesperantist-pg-1903-v1n13', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n13", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (233, 249), "scan, PDF pages 233–249")],
     "whole_in": "theesperantist-pg-1903-v1n13", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 1 no. 14", "same_text": [['theesperantist-pg-1903-v1n14', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1903-v1n14", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (251, 268), "scan, PDF pages 251–268")],
     "whole_in": "theesperantist-pg-1903-v1n14", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 1", "same_text": [['theesperantist-pg-1905-v2n01', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n01", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (271, 290), "scan, PDF pages 271–290")],
     "whole_in": "theesperantist-pg-1905-v2n01", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 2", "same_text": [['theesperantist-pg-1905-v2n02', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n02", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (291, 308), "scan, PDF pages 291–308")],
     "whole_in": "theesperantist-pg-1905-v2n02", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 3", "same_text": [['theesperantist-pg-1905-v2n03', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n03", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (309, 325), "scan, PDF pages 309–325")],
     "whole_in": "theesperantist-pg-1905-v2n03", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 4", "same_text": [['theesperantist-pg-1905-v2n04', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n04", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (327, 350), "scan, PDF pages 327–350")],
     "whole_in": "theesperantist-pg-1905-v2n04", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 5", "same_text": [['theesperantist-pg-1905-v2n05', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n05", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (351, 368), "scan, PDF pages 351–368")],
     "whole_in": "theesperantist-pg-1905-v2n05", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 6", "same_text": [['theesperantist-pg-1905-v2n06', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n06", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (369, 386), "scan, PDF pages 369–386")],
     "whole_in": "theesperantist-pg-1905-v2n06", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 7", "same_text": [['theesperantist-pg-1905-v2n07', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n07", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (387, 404), "scan, PDF pages 387–404")],
     "whole_in": "theesperantist-pg-1905-v2n07", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 8", "same_text": [['theesperantist-pg-1905-v2n08', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n08", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (405, 422), "scan, PDF pages 405–422")],
     "whole_in": "theesperantist-pg-1905-v2n08", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 9", "same_text": [['theesperantist-pg-1905-v2n09', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n09", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (423, 440), "scan, PDF pages 423–440")],
     "whole_in": "theesperantist-pg-1905-v2n09", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 10", "same_text": [['theesperantist-pg-1905-v2n10', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n10", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (441, 458), "scan, PDF pages 441–458")],
     "whole_in": "theesperantist-pg-1905-v2n10", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 11", "same_text": [['theesperantist-pg-1905-v2n11', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n11", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (459, 476), "scan, PDF pages 459–476")],
     "whole_in": "theesperantist-pg-1905-v2n11", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "The Esperantist, vol. 2 no. 12", "same_text": [['theesperantist-pg-1905-v2n12', 'TheEsperantist.1903-1904.v1']],
     "copies": [("theesperantist-pg-1905-v2n12", None, "typed, Project Gutenberg e-book"), ("TheEsperantist.1903-1904.v1", (477, 493), "scan, PDF pages 477–493")],
     "whole_in": "theesperantist-pg-1905-v2n12", "triangulated": "", "note": "decided by the editor, 2026-10-10: the Gutenberg e-books enter as copies of the scan; page ranges from the page maps"},
    {"work": "Couturat, Jespersen, Lorenz, Ostwald, Pfaundler, Weltsprache und Wissenschaft (1909)", "same_text": [],
     "copies": [("Weltsprache und Wissenschaft", None, "scan, the German original, Jena 1909"),
                ("reu-internacia_lingvo_kaj_scienco_1910", None, "typed, the Russian translation by Chakhotin, Odessa 1910, with his preface")],
     "whole_in": "Weltsprache und Wissenschaft", "triangulated": "", "note": "decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only"},
    {"work": "Ĥvorostin, Cara cenzuro kaj Esperanto (Scienca Revuo 1972)", "same_text": [],
     "copies": [("hvorostin_cara_cenzuro_1972", None, "scan, the Esperanto original (queued for the cupel: no hits until it is in)"),
                ("reu-hvorostin_cara_cenzuro_ru_1994", None, "typed, the Russian translation, Litova Stelo 1994")],
     "whole_in": "hvorostin_cara_cenzuro_1972", "triangulated": "", "note": "decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only"},
    {"work": "Patlanj, Поездка В. Я. Ерошенко в Англию (2013)", "same_text": [],
     "copies": [("reu-patlanj_vojagho_de_eroshenko_2013", None, "typed, the Russian original, Belgorod 2013"),
                ("reu-patlanj_eroshenko_en_anglio", None, "typed, Sidorov's Esperanto translation, 2014")],
     "whole_in": "reu-patlanj_vojagho_de_eroshenko_2013", "triangulated": "", "note": "decided by the editor, 2026-10-10: translations are copies, copies-table entries only; a translator's additions show in the record's list of people found in one copy only. Not entered: the 1920 Russian Declaration (its 1905 original is held only as the Akademio's web page, no dowse item); Belousov 1975 and 1985 (their Russian scans come with the Sidorov scan batch); Sakharov 1907 (only part a copy)"},
    {"work": 'Kosmopolan (Sydney), 1891–1898', "same_text": [['kosmopolan', 'kosmopolan_1891_01', 'kosmopolan_1891_03', 'kosmopolan_1892_04', 'kosmopolan_1892_06', 'kosmopolan_1895_20', 'kosmopolan_1895_21', 'kosmopolan_1895_23', 'kosmopolan_1895_24', 'kosmopolan_1895_25', 'kosmopolan_1896_26', 'kosmopolan_1896_27', 'kosmopolan_1896_28', 'kosmopolan_1896_29', 'kosmopolan_1896_30', 'kosmopolan_1896_31', 'kosmopolan_1897_32', 'kosmopolan_1897_34', 'kosmopolan_1897_35', 'kosmopolan_1897_36', 'kosmopolan_1897_37', 'kosmopolan_contents_1898']],
     "copies": [('kosmopolan', None, 'ÖNB, the run as bound (cupel15)'),
                ('kosmopolan_1891_01', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1891_03', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1892_04', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1892_06', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1895_20', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1895_21', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1895_23', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1895_24', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1895_25', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_26', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_27', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_28', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_29', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_30', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1896_31', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1897_32', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1897_34', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1897_35', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1897_36', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_1897_37', None, "temerov's scan, one issue (cupel16)"),
                ('kosmopolan_contents_1898', None, "temerov's scan, one issue (cupel16)")],
     "triangulated": "", "note": "decided by the editor, 2026-10-20 (cupel16 C13, rule 15: ocr/runs/CUPEL16-RULE15-SECOND-COPIES-2026-10-20.md; both copies kept, each holding pages the other lacks); not triangulated: neither copy holds Nos 7–19, 22 or 33 (LACUNAE.tsv), so a silence counts only over each copy's own pages"},
    {"work": 'Nunal nulik, 1890–1892', "same_text": [['nunal.nulik', 'nunal_nulik_1890_n1-2', 'nunal_nulik_onb_1890-92']],
     "copies": [('nunal.nulik', None, 'ÖNB (cupel15)'),
                ('nunal_nulik_1890_n1-2', None, "temerov's scan (cupel16)"),
                ('nunal_nulik_onb_1890-92', None, "temerov's scan (cupel16)")],
     "triangulated": "", "note": 'decided by the editor, 2026-10-20 (cupel16 C13, rule 15: ocr/runs/CUPEL16-RULE15-SECOND-COPIES-2026-10-20.md; both copies kept, each holding pages the other lacks); not triangulated: the pairing by printed page left a run of 21 pp unpaired'},
    {"work": 'Volaspodel, 1888–1894', "same_text": [['volaspodelamont00unkngoog', 'volaspodel_1888-89', 'volaspodel_y3_1892-93', 'volaspodel_y4_1893-94']],
     "copies": [('volaspodelamont00unkngoog', None, "archive.org, Google's scan (cupel15)"),
                ('volaspodel_1888-89', None, "temerov's scan (cupel16)"),
                ('volaspodel_y3_1892-93', None, "temerov's scan (cupel16)"),
                ('volaspodel_y4_1893-94', None, "temerov's scan (cupel16)")],
     "triangulated": "decided by the editor, 2026-10-20: triangulated over the agreeing shared pages ONLY (87 at the ruling; 85 since 18:0x, when the alignment's new «page paired twice» flag took out archive.org PDF 17 and PDF 89, each paired under several printed numbers) (BOTH, no quality flag, both copies at absence quality, ocr/runs/OCR-COPY-ALIGN-2026-10-20-volaspodel.tsv), listed in «triangulated_pages» as (archive.org item, PDF, temerov item, PDF); NOT the 18 flagged shared pages, the pages only temerov's scans hold, or the unpaired 1888–89 volumes",
     "pairing_errors": [("volaspodelamont00unkngoog", 17, "paired under printed 8, 20 and 140 (the alignment rerun 18:0x with the «page paired twice» flag): one page, several temerov partners sharing a recurring block; taken out of triangulated_pages"), ("volaspodelamont00unkngoog", 89, "paired under printed 16, 48 and 56: as PDF 17; taken out of triangulated_pages"), ("volaspodelamont00unkngoog", 73, "printed «60» in OCR-COPY-ALIGN-2026-10-20-volaspodel.tsv is a misread number: this page is printed 168 (paired there with volaspodel_y3_1892-93 PDF 172; the rerun shows it paired under printed 60, 92, 108, 124, 156 and 168 in all); its «60» partner, temerov's PDF 64, is a back page of advertisements sharing only the Huebsch advertisement block; no page of its own (checked 2026-10-20 18:0x; the editor)"), ("volaspodelamont00unkngoog", 52, "printed «71»: no text shared with any page of temerov's yelüp 3; an archive.org-only page"), ("volaspodelamont00unkngoog", 53, "printed «72»: as «71»")],
     "triangulated_pages": [('volaspodelamont00unkngoog', 10, 'volaspodel_y3_1892-93', 5), ('volaspodelamont00unkngoog', 11, 'volaspodel_y3_1892-93', 6), ('volaspodelamont00unkngoog', 12, 'volaspodel_y3_1892-93', 7), ('volaspodelamont00unkngoog', 13, 'volaspodel_y3_1892-93', 8), ('volaspodelamont00unkngoog', 14, 'volaspodel_y3_1892-93', 9), ('volaspodelamont00unkngoog', 15, 'volaspodel_y3_1892-93', 10), ('volaspodelamont00unkngoog', 16, 'volaspodel_y3_1892-93', 11), ('volaspodelamont00unkngoog', 18, 'volaspodel_y3_1892-93', 25), ('volaspodelamont00unkngoog', 19, 'volaspodel_y3_1892-93', 26), ('volaspodelamont00unkngoog', 20, 'volaspodel_y3_1892-93', 27), ('volaspodelamont00unkngoog', 21, 'volaspodel_y3_1892-93', 28), ('volaspodelamont00unkngoog', 22, 'volaspodel_y3_1892-93', 29), ('volaspodelamont00unkngoog', 23, 'volaspodel_y3_1892-93', 30), ('volaspodelamont00unkngoog', 24, 'volaspodel_y3_1892-93', 31), ('volaspodelamont00unkngoog', 25, 'volaspodel_y3_1892-93', 32), ('volaspodelamont00unkngoog', 26, 'volaspodel_y3_1892-93', 33), ('volaspodelamont00unkngoog', 27, 'volaspodel_y3_1892-93', 34), ('volaspodelamont00unkngoog', 28, 'volaspodel_y3_1892-93', 35), ('volaspodelamont00unkngoog', 29, 'volaspodel_y3_1892-93', 36), ('volaspodelamont00unkngoog', 30, 'volaspodel_y3_1892-93', 37), ('volaspodelamont00unkngoog', 31, 'volaspodel_y3_1892-93', 38), ('volaspodelamont00unkngoog', 32, 'volaspodel_y3_1892-93', 39), ('volaspodelamont00unkngoog', 33, 'volaspodel_y3_1892-93', 40), ('volaspodelamont00unkngoog', 34, 'volaspodel_y3_1892-93', 41), ('volaspodelamont00unkngoog', 35, 'volaspodel_y3_1892-93', 42), ('volaspodelamont00unkngoog', 36, 'volaspodel_y3_1892-93', 43), ('volaspodelamont00unkngoog', 37, 'volaspodel_y3_1892-93', 44), ('volaspodelamont00unkngoog', 38, 'volaspodel_y3_1892-93', 45), ('volaspodelamont00unkngoog', 39, 'volaspodel_y3_1892-93', 46), ('volaspodelamont00unkngoog', 40, 'volaspodel_y3_1892-93', 47), ('volaspodelamont00unkngoog', 41, 'volaspodel_y3_1892-93', 48), ('volaspodelamont00unkngoog', 42, 'volaspodel_y3_1892-93', 65), ('volaspodelamont00unkngoog', 43, 'volaspodel_y3_1892-93', 66), ('volaspodelamont00unkngoog', 44, 'volaspodel_y3_1892-93', 67), ('volaspodelamont00unkngoog', 45, 'volaspodel_y3_1892-93', 68), ('volaspodelamont00unkngoog', 46, 'volaspodel_y3_1892-93', 69), ('volaspodelamont00unkngoog', 49, 'volaspodel_y3_1892-93', 72), ('volaspodelamont00unkngoog', 50, 'volaspodel_y3_1892-93', 73), ('volaspodelamont00unkngoog', 51, 'volaspodel_y3_1892-93', 74), ('volaspodelamont00unkngoog', 54, 'volaspodel_y3_1892-93', 77), ('volaspodelamont00unkngoog', 55, 'volaspodel_y3_1892-93', 78), ('volaspodelamont00unkngoog', 56, 'volaspodel_y3_1892-93', 79), ('volaspodelamont00unkngoog', 57, 'volaspodel_y3_1892-93', 80), ('volaspodelamont00unkngoog', 58, 'volaspodel_y3_1892-93', 81), ('volaspodelamont00unkngoog', 59, 'volaspodel_y3_1892-93', 82), ('volaspodelamont00unkngoog', 60, 'volaspodel_y3_1892-93', 83), ('volaspodelamont00unkngoog', 61, 'volaspodel_y3_1892-93', 84), ('volaspodelamont00unkngoog', 62, 'volaspodel_y3_1892-93', 85), ('volaspodelamont00unkngoog', 63, 'volaspodel_y3_1892-93', 86), ('volaspodelamont00unkngoog', 64, 'volaspodel_y3_1892-93', 87), ('volaspodelamont00unkngoog', 65, 'volaspodel_y3_1892-93', 88), ('volaspodelamont00unkngoog', 66, 'volaspodel_y3_1892-93', 89), ('volaspodelamont00unkngoog', 67, 'volaspodel_y3_1892-93', 90), ('volaspodelamont00unkngoog', 68, 'volaspodel_y3_1892-93', 91), ('volaspodelamont00unkngoog', 69, 'volaspodel_y3_1892-93', 92), ('volaspodelamont00unkngoog', 70, 'volaspodel_y3_1892-93', 93), ('volaspodelamont00unkngoog', 71, 'volaspodel_y3_1892-93', 94), ('volaspodelamont00unkngoog', 72, 'volaspodel_y3_1892-93', 95), ('volaspodelamont00unkngoog', 90, 'volaspodel_y4_1893-94', 18), ('volaspodelamont00unkngoog', 91, 'volaspodel_y4_1893-94', 19), ('volaspodelamont00unkngoog', 92, 'volaspodel_y4_1893-94', 20), ('volaspodelamont00unkngoog', 93, 'volaspodel_y4_1893-94', 21), ('volaspodelamont00unkngoog', 94, 'volaspodel_y4_1893-94', 22), ('volaspodelamont00unkngoog', 95, 'volaspodel_y4_1893-94', 23), ('volaspodelamont00unkngoog', 96, 'volaspodel_y4_1893-94', 24), ('volaspodelamont00unkngoog', 97, 'volaspodel_y4_1893-94', 25), ('volaspodelamont00unkngoog', 98, 'volaspodel_y4_1893-94', 26), ('volaspodelamont00unkngoog', 99, 'volaspodel_y4_1893-94', 27), ('volaspodelamont00unkngoog', 100, 'volaspodel_y4_1893-94', 28), ('volaspodelamont00unkngoog', 101, 'volaspodel_y4_1893-94', 29), ('volaspodelamont00unkngoog', 102, 'volaspodel_y4_1893-94', 30), ('volaspodelamont00unkngoog', 103, 'volaspodel_y4_1893-94', 31), ('volaspodelamont00unkngoog', 105, 'volaspodel_y4_1893-94', 33), ('volaspodelamont00unkngoog', 75, 'volaspodel_y4_1893-94', 35), ('volaspodelamont00unkngoog', 76, 'volaspodel_y4_1893-94', 36), ('volaspodelamont00unkngoog', 77, 'volaspodel_y4_1893-94', 37), ('volaspodelamont00unkngoog', 78, 'volaspodel_y4_1893-94', 38), ('volaspodelamont00unkngoog', 79, 'volaspodel_y4_1893-94', 39), ('volaspodelamont00unkngoog', 80, 'volaspodel_y4_1893-94', 40), ('volaspodelamont00unkngoog', 81, 'volaspodel_y4_1893-94', 41), ('volaspodelamont00unkngoog', 83, 'volaspodel_y4_1893-94', 43), ('volaspodelamont00unkngoog', 84, 'volaspodel_y4_1893-94', 44), ('volaspodelamont00unkngoog', 85, 'volaspodel_y4_1893-94', 45), ('volaspodelamont00unkngoog', 86, 'volaspodel_y4_1893-94', 46), ('volaspodelamont00unkngoog', 87, 'volaspodel_y4_1893-94', 47)],
     "note": "decided by the editor, 2026-10-20 (cupel16 C13, rule 15: ocr/runs/CUPEL16-RULE15-SECOND-COPIES-2026-10-20.md; both copies kept, each holding pages the other lacks); temerov's yelüp 3 fills archive.org's three lacunae"},
    {"work": 'Enciklopedio de Esperanto (Budapest 1933)', "same_text": [['ENCIKLOPEDIO_DE_ESPERANTO_1933_', 'ede-1933-eventoj-1', 'ede-1933-eventoj-a', 'ede-1933-eventoj-aldon', 'ede-1933-eventoj-b', 'ede-1933-eventoj-c', 'ede-1933-eventoj-cx', 'ede-1933-eventoj-d', 'ede-1933-eventoj-e', 'ede-1933-eventoj-f', 'ede-1933-eventoj-g', 'ede-1933-eventoj-h', 'ede-1933-eventoj-i', 'ede-1933-eventoj-j', 'ede-1933-eventoj-k', 'ede-1933-eventoj-l', 'ede-1933-eventoj-m', 'ede-1933-eventoj-n', 'ede-1933-eventoj-o', 'ede-1933-eventoj-p', 'ede-1933-eventoj-q', 'ede-1933-eventoj-r', 'ede-1933-eventoj-s', 'ede-1933-eventoj-sx', 'ede-1933-eventoj-t', 'ede-1933-eventoj-u', 'ede-1933-eventoj-v', 'ede-1933-eventoj-w', 'ede-1933-eventoj-y', 'ede-1933-eventoj-z']], "texts_checked": "checked 2026-10-20 16:5x: one text, the 1933 edition transcribed; the name test (tools/ocr-copy-name-test.py, ocr/runs/OCR-COPY-NAME-TEST-2026-10-20-ede-1933.md) finds every one of the scan's 1,062 roster names in eventoj.hu; the scan's preferred reading 350,712 words, eventoj.hu 347,978",
     "copies": [('ENCIKLOPEDIO_DE_ESPERANTO_1933_', None, 'scan, the 1933 edition (lacks the Do–Dz signature, PDF 185/186)'),
                ('ede-1933-eventoj-1', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-a', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-aldon', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-b', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-c', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-cx', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-d', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-e', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-f', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-g', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-h', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-i', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-j', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-k', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-l', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-m', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-n', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-o', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-p', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-q', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-r', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-s', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-sx', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-t', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-u', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-v', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-w', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-y', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter'),
                ('ede-1933-eventoj-z', None, 'typed, the eventoj.hu HTML edition (M. Malovec 2004), one letter')],
     "triangulated": "", "note": 'decided by the editor, 2026-10-20: a strong candidate for kind 2 (the PDF to go), after testing. The eventoj.hu edition was fetched 2026-09-13 for the Do–Dz signature the scan lacks (sources/ede-1933-eventoj/_INDEX.md)'},
    {"work": "Neves, the 35 comments on Trevor Steele's «La krizo de Ido» (YouTube, 23 Feb 2022)", "same_text": [], "texts_checked": 'checked 2026-10-20 17:2x, by their first pages: the Ido file «Hike me prizentas Ido-tradukuro da me ipsa»; the Esperanto file names the Ido translation at archive.org: two texts (kind 0)',
     "copies": [('35_komentoj_de_Neves', None, 'Esperanto, the original (archive.org)'),
                ('35_komenti_da_Neves', None, "Ido, Neves's own translation (archive.org)")],
     "triangulated": "", "note": "decided by the editor, 2026-10-20 (kind 0: the author's own texts in two languages; both read whole, facts merged, never a page skipped)"},
    {"work": 'Neves, Esperanto kaj Ido: malsamaj vojoj sur Parnason / Esperanto ed Ido: diferanta voyi adsur Parnaso', "same_text": [], "texts_checked": 'checked 2026-10-20 17:2x, by their title pages: the Ido version 2018 (Sudo), the Esperanto 2019 (Drako): two texts (kind 0)',
     "copies": [('Esperanto kaj Ido_malsamaj vojoj sur Parnason', None, 'Esperanto, Eldonejo Drako 2019'),
                ('Esperanto ed Ido_diferanta voyi adsur Parnaso', None, 'Ido, Editerio Sudo 2018')],
     "triangulated": "", "note": "decided by the editor, 2026-10-20 (kind 0: the author's own texts in two languages; both read whole, facts merged, never a page skipped)"},
    {"work": 'La Belga Sonorilo (Bruges, 1902–1914)', "same_text": [['LaBelgaSonorilo_1902_n001_sep', 'LaBelgaSonorilo_1902_n002_okt', 'LaBelgaSonorilo_1902_n003_nov', 'LaBelgaSonorilo_1902_n004_dec', 'LaBelgaSonorilo_1903_n005_jan', 'LaBelgaSonorilo_1903_n006_feb', 'LaBelgaSonorilo_1903_n007_mar', 'LaBelgaSonorilo_1903_n008_apr', 'LaBelgaSonorilo_1903_n009_maj', 'LaBelgaSonorilo_1903_n010_jun', 'LaBelgaSonorilo_1903_n011_jul', 'LaBelgaSonorilo_1903_n012_aug', 'LaBelgaSonorilo_1903_n013_sep', 'LaBelgaSonorilo_1903_n014_okt', 'LaBelgaSonorilo_1903_n015_nov', 'LaBelgaSonorilo_1903_n016_dec', 'LaBelgaSonorilo_1904_n017_jan', 'LaBelgaSonorilo_1904_n018_feb', 'LaBelgaSonorilo_1904_n019_mar', 'LaBelgaSonorilo_1904_n020_apr', 'LaBelgaSonorilo_1904_n021_maj', 'LaBelgaSonorilo_1904_n022_jun', 'LaBelgaSonorilo_1904_n023_jul', 'LaBelgaSonorilo_1904_n024_aug', 'LaBelgaSonorilo_1904_n025_sep', 'LaBelgaSonorilo_1904_n026_okt', 'LaBelgaSonorilo_1904_n027_nov', 'LaBelgaSonorilo_1904_n028_dec', 'LaBelgaSonorilo_1905_n029_jan', 'LaBelgaSonorilo_1905_n030_feb', 'LaBelgaSonorilo_1905_n031_mar', 'LaBelgaSonorilo_1905_n032_apr', 'LaBelgaSonorilo_1905_n033_maj', 'LaBelgaSonorilo_1905_n034_jun', 'LaBelgaSonorilo_1905_n035_jul', 'LaBelgaSonorilo_1905_n036_aug', 'LaBelgaSonorilo_1905_n037_sep', 'LaBelgaSonorilo_1905_n038_okt', 'LaBelgaSonorilo_1905_n039_nov', 'LaBelgaSonorilo_1905_n040_dec', 'LaBelgaSonorilo_1906_n041_jan', 'LaBelgaSonorilo_1906_n042_feb', 'LaBelgaSonorilo_1906_n043_mar', 'LaBelgaSonorilo_1906_n044_apr', 'LaBelgaSonorilo_1906_n045_maj', 'LaBelgaSonorilo_1906_n046_jun', 'LaBelgaSonorilo_1906_n047_jul', 'LaBelgaSonorilo_1906_n048-049_sep', 'LaBelgaSonorilo_1906_n050_okt', 'LaBelgaSonorilo_1906_n051_nov', 'LaBelgaSonorilo_1906_n052_dec', 'LaBelgaSonorilo_1907_n053_jan', 'LaBelgaSonorilo_1907_n054_jan', 'LaBelgaSonorilo_1907_n055_feb', 'LaBelgaSonorilo_1907_n056_feb', 'LaBelgaSonorilo_1907_n057_mar', 'LaBelgaSonorilo_1907_n058_mar', 'LaBelgaSonorilo_1907_n059_apr', 'LaBelgaSonorilo_1907_n060_apr', 'LaBelgaSonorilo_1907_n061_maj', 'LaBelgaSonorilo_1907_n062_maj', 'LaBelgaSonorilo_1907_n063_jun', 'LaBelgaSonorilo_1907_n064_jun', 'LaBelgaSonorilo_1907_n065_jul', 'LaBelgaSonorilo_1907_n066_jul', 'LaBelgaSonorilo_1907_n067_aug', 'LaBelgaSonorilo_1907_n068_sep', 'LaBelgaSonorilo_1907_n069_okt', 'LaBelgaSonorilo_1907_n070_okt', 'LaBelgaSonorilo_1907_n071_nov', 'LaBelgaSonorilo_1907_n072_nov', 'LaBelgaSonorilo_1907_n073_dec', 'LaBelgaSonorilo_1907_n074_dec', 'LaBelgaSonorilo_1908_n075_jan', 'LaBelgaSonorilo_1908_n076_jan', 'LaBelgaSonorilo_1908_n077_feb', 'LaBelgaSonorilo_1908_n078_feb', 'LaBelgaSonorilo_1908_n079_mar', 'LaBelgaSonorilo_1908_n080_mar', 'LaBelgaSonorilo_1908_n081_mar', 'LaBelgaSonorilo_1908_n082_apr', 'LaBelgaSonorilo_1908_n083_apr', 'LaBelgaSonorilo_1908_n084_maj', 'LaBelgaSonorilo_1908_n085_maj', 'LaBelgaSonorilo_1908_n086_maj', 'LaBelgaSonorilo_1908_n087_jun', 'LaBelgaSonorilo_1908_n088_jun', 'LaBelgaSonorilo_1908_n089_jul', 'LaBelgaSonorilo_1908_n090_jul', 'LaBelgaSonorilo_1908_n091_aug', 'LaBelgaSonorilo_1908_n092_sep', 'LaBelgaSonorilo_1908_n093_okt', 'LaBelgaSonorilo_1908_n094_okt', 'LaBelgaSonorilo_1908_n095_nov', 'LaBelgaSonorilo_1908_n096_nov', 'LaBelgaSonorilo_1908_n097_dec', 'LaBelgaSonorilo_1908_n098_dec', 'LaBelgaSonorilo_1909_n099_jan', 'LaBelgaSonorilo_1909_n100_jan', 'LaBelgaSonorilo_1909_n101_feb', 'LaBelgaSonorilo_1909_n102_feb', 'LaBelgaSonorilo_1909_n103_mar', 'LaBelgaSonorilo_1909_n104_mar', 'LaBelgaSonorilo_1909_n105_apr', 'LaBelgaSonorilo_1909_n106_apr', 'LaBelgaSonorilo_1909_n107_maj', 'LaBelgaSonorilo_1909_n108_maj', 'LaBelgaSonorilo_1909_n109_jun', 'LaBelgaSonorilo_1909_n110_jun', 'LaBelgaSonorilo_1909_n111_jul', 'LaBelgaSonorilo_1909_n112_jul', 'LaBelgaSonorilo_1909_n113_aug', 'LaBelgaSonorilo_1909_n114_sep', 'LaBelgaSonorilo_1909_n115_okt', 'LaBelgaSonorilo_1909_n116_okt', 'LaBelgaSonorilo_1909_n117_nov', 'LaBelgaSonorilo_1909_n118_nov', 'LaBelgaSonorilo_1909_n120_dec', 'LaBelgaSonorilo_1910_n121_jan', 'LaBelgaSonorilo_1910_n122_jan', 'LaBelgaSonorilo_1910_n123_feb', 'LaBelgaSonorilo_1910_n124_mar', 'LaBelgaSonorilo_1910_n125_mar', 'LaBelgaSonorilo_1910_n126_apr', 'LaBelgaSonorilo_1910_n127_apr', 'LaBelgaSonorilo_1910_n128_maj', 'LaBelgaSonorilo_1910_n129_jun', 'LaBelgaSonorilo_1910_n130_jun', 'LaBelgaSonorilo_1910_n131_jul', 'LaBelgaSonorilo_1910_n132_jul', 'LaBelgaSonorilo_1910_n133_aug', 'LaBelgaSonorilo_1910_n134_sep', 'LaBelgaSonorilo_1910_n135_okt', 'LaBelgaSonorilo_1910_n136_nov', 'LaBelgaSonorilo_1910_n137_dec', 'LaBelgaSonorilo_1911_n138_jan', 'LaBelgaSonorilo_1911_n139_feb.bitarkivo', 'LaBelgaSonorilo_1911_n139_jan', 'LaBelgaSonorilo_1911_n140_mar', 'LaBelgaSonorilo_1911_n141_apr', 'LaBelgaSonorilo_1911_n142_maj', 'LaBelgaSonorilo_1911_n143_jun.bitarkivo', 'LaBelgaSonorilo_1911_n144_jul-aug', 'LaBelgaSonorilo_1911_n145_sep', 'LaBelgaSonorilo_1911_n146_okt', 'LaBelgaSonorilo_1911_n147_nov', 'LaBelgaSonorilo_1911_n148_dec', 'LaBelgaSonorilo_1912_n149_jan', 'LaBelgaSonorilo_1912_n150_feb', 'LaBelgaSonorilo_1912_n151_mar', 'LaBelgaSonorilo_1912_n152_apr', 'LaBelgaSonorilo_1912_n153_maj', 'LaBelgaSonorilo_1912_n154_jun', 'LaBelgaSonorilo_1912_n155_jul.bitarkivo', 'LaBelgaSonorilo_1912_n156_aug', 'LaBelgaSonorilo_1912_n157_sep', 'LaBelgaSonorilo_1912_n158_nov', 'LaBelgaSonorilo_1912_n158_nov_suplemento', 'LaBelgaSonorilo_1913_n159_jan', 'LaBelgaSonorilo_1913_n160_mar', 'LaBelgaSonorilo_1913_n161_maj', 'LaBelgaSonorilo_1913_n162_jul', 'LaBelgaSonorilo_1913_n163_sep', 'LaBelgaSonorilo_1913_n164_nov', 'LaBelgaSonorilo_1914_n165_jan', 'LaBelgaSonorilo_1914_n166_mar', 'LaBelgaSonorilo_1914_n167_maj', 'LaBelgaSonorilo_1914_n168_jul', 'belgaSonorilo.1902', 'belgaSonorilo.1904', 'belgaSonorilo.1906', 'belgaSonorilo.1907', 'belgaSonorilo.1908', 'belgaSonorilo.1910', 'belgaSonorilo.1910.1', 'belgaSonorilo.1912', 'belgasonorilo.1909.5', 'belgasonorilo.1911.11', 'belgasonorilo.1911.5', 'belgasonorilo.1911.7', 'belgasonorilo.1912.11', 'belgasonorilo.1912.5', 'belgasonorilo.1912.6', 'belgasonorilo.1912.8']], "texts_checked": 'one printing in several copies: the ÖNB volumes and single issues, the per-issue run, three BitArkivo issues (rule 15, cupel8, 2026-10-11: both kept; the name test of 2026-10-20, ocr/runs/NAME-TESTS-2026-10-20-RESULT.md: each copy holds pages, wrappers, index pages and readings of names the other lacks)',
     "copies": [('LaBelgaSonorilo_1902_n001_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1902_n002_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1902_n003_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1902_n004_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n005_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n006_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n007_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n008_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n009_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n010_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n011_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n012_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n013_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n014_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n015_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1903_n016_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n017_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n018_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n019_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n020_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n021_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n022_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n023_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n024_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n025_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n026_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n027_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1904_n028_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n029_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n030_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n031_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n032_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n033_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n034_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n035_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n036_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n037_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n038_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n039_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1905_n040_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n041_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n042_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n043_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n044_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n045_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n046_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n047_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n048-049_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n050_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n051_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1906_n052_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n053_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n054_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n055_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n056_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n057_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n058_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n059_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n060_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n061_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n062_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n063_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n064_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n065_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n066_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n067_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n068_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n069_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n070_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n071_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n072_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n073_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1907_n074_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n075_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n076_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n077_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n078_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n079_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n080_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n081_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n082_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n083_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n084_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n085_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n086_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n087_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n088_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n089_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n090_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n091_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n092_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n093_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n094_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n095_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n096_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n097_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1908_n098_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n099_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n100_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n101_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n102_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n103_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n104_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n105_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n106_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n107_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n108_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n109_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n110_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n111_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n112_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n113_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n114_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n115_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n116_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n117_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n118_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1909_n120_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n121_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n122_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n123_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n124_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n125_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n126_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n127_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n128_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n129_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n130_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n131_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n132_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n133_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n134_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n135_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n136_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1910_n137_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n138_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n139_feb.bitarkivo', None, 'BitArkivo, a single issue'),
                ('LaBelgaSonorilo_1911_n139_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n140_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n141_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n142_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n143_jun.bitarkivo', None, 'BitArkivo, a single issue'),
                ('LaBelgaSonorilo_1911_n144_jul-aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n145_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n146_okt', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n147_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1911_n148_dec', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n149_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n150_feb', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n151_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n152_apr', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n153_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n154_jun', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n155_jul.bitarkivo', None, 'BitArkivo, a single issue'),
                ('LaBelgaSonorilo_1912_n156_aug', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n157_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n158_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1912_n158_nov_suplemento', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n159_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n160_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n161_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n162_jul', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n163_sep', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1913_n164_nov', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1914_n165_jan', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1914_n166_mar', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1914_n167_maj', None, 'archive.org per-issue run (cupel8)'),
                ('LaBelgaSonorilo_1914_n168_jul', None, 'archive.org per-issue run (cupel8)'),
                ('belgaSonorilo.1902', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1904', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1906', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1907', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1908', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1910', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1910.1', None, 'ÖNB, a bound volume'),
                ('belgaSonorilo.1912', None, 'ÖNB, a bound volume'),
                ('belgasonorilo.1909.5', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1911.11', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1911.5', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1911.7', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1912.11', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1912.5', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1912.6', None, 'ÖNB, a single issue'),
                ('belgasonorilo.1912.8', None, 'ÖNB, a single issue')],
     "triangulated": "", "note": "the editor 2026-10-20 18:4x: every copy kept and read; no copy deleted; no page skipped (not triangulated)"},
    # Ezri's request through the editor, 2026-10-24 00:4x («Two items in the OCR item table look like one issue scanned
    # twice … which copy reads better»); checked by Miles 00:5x (ocr/runs/OCR-COPY-ALIGN-2026-10-24-esperanto-ruslando-1905.md)
    {"work": "Esperanto (St Petersburg, ed. Ostrovskij), 1905, N-ro 1–2 (January)", "same_text": [['EsperantoRuslando.1905.1-2', 'EsperantoRuslando.1905.sennumera']],
     "copies": [('EsperantoRuslando.1905.1-2', None, "the better copy: 600 ppi, no text layer; the gate's Esperanto side 84.4, Russian side 70.7 (25 pp)"),
                ('EsperantoRuslando.1905.sennumera', None, "133-ppi JPX with a noise text layer (ScanSoft OmniPage 16); Esperanto 72.4, Russian 54.8 (23 pp); its name «sennumera» is the file's, its masthead reads N-ro 1–2")],
     "triangulated": "", "note": "one issue, the same printing as far as the pages show: same mastheads, same pages in the same order, the same lines on the same printed pages; printed 1–26 paired, every page in BOTH; the alignment's word shares DISAGREE (< 0.80) on 24 of 26 pages, which is OCR noise in the Cyrillic; the alignment's «other copy better on the cover» was a mispairing (failure map R58): PDF n against PDF n, …1905.1-2 is better on every page, Esperanto and Russian. WITHDRAWN: the editor 2026-10-24 01:17 (ocr/lines/OCR-ACCEPTANCE-LINES-2026-10-24-SIGNED-withdraw-esperanto-ruslando-sennumera.txt); Ezri re-pinned her 243 lines to …1905.1-2 (relayed 2026-10-24 03:0x); …sennumera\'s readings deleted 03:05, off sources/OCR-PDF-LIST-2026-10-24-cupel18a-b.txt; the scan kept."},
]
WITNESSES = COPIES   # the old name, kept for anything that imports it


def born_digital():
    """{(item, PDF page)} whose text layer is born-digital (ocr-text-layer-*/tl-kind.tsv, the newest): the layer
    IS the printed text, so a hit there needs no image check (the editor ruled on 2026-10-06 20:0x that where the corpus
    is born digital, this confirmation is not needed at all)."""
    c = sorted(glob.glob(os.path.join(S, "ocr-text-layer-*", "tl-kind.tsv")))
    out = set()
    for l in (open(c[-1], encoding="utf-8") if c else []):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 3 and x[2] == "born-digital" and x[1].isdigit():
            out.add((x[0], int(x[1])))
    return out


_CITE = {}


def citation_tables():
    """(item → item-table row, (item, PDF page) → page-map row) from the fixed tables (2026-10-08:
    geniza/OCR-ITEM-TABLE.tsv by tools/ocr-item-table.py, geniza/ocr/runs/OCR-PAGE-MAP.tsv by ocr-page-sequence.py map).
    Empty when a table is missing: the dowse runs as before, without citations."""
    if _CITE: return _CITE["items"], _CITE["pages"]
    def rows(path):
        if not os.path.exists(path): return []
        head, out = None, []
        for l in open(path, encoding="utf-8"):
            if l.startswith("#"): continue
            x = l.rstrip("\n").split("\t")
            if head is None: head = x; continue
            out.append(dict(zip(head, x)))
        return out
    _CITE["items"] = {r["item"]: r for r in rows(os.path.join(G, "OCR-ITEM-TABLE.tsv"))}
    _CITE["pages"] = {(r["item"], int(r["pdf_page"])): r for r in rows(os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv"))}
    st = collections.defaultdict(list)
    for r in rows(os.path.join(G, "ocr", "runs", "OCR-ISSUE-STARTS.tsv")):
        st[(r["title_key"], r["volume_year"])].append((int(r["first_printed"]), int(r["issue"])))
    _CITE["starts"] = {k: sorted(v) for k, v in st.items()}
    return _CITE["items"], _CITE["pages"]


def issue_from_starts(ir, printed):
    """the issue a printed page falls in, for a volume held in parts (Lingvo Internacia, La Revuo: no issue in the file
    name), from ocr/runs/OCR-ISSUE-STARTS.tsv (tools/ocr-issue-starts.py; approved by the editor, 2026-10-08).
    Only where it is safe: the page is at or after issue n's known start and before issue n+1's known start; or n is the
    volume's last known start and the page is within one usual issue length of it. Otherwise «» (an unread start between
    two known ones leaves the pages between them without an issue, rather than give them the wrong one)."""
    citation_tables()
    ss = _CITE.get("starts", {}).get((ir.get("title_key", ""), ir.get("year", "")), [])
    m = re.match(r"(\d+)", printed or "")
    if len(ss) < 2 or not m: return ""
    p = int(m.group(1))
    spans = sorted(pb - pa for (pa, na), (pb, nb) in zip(ss, ss[1:]) if nb - na == 1)
    if not spans: return ""
    med = spans[len(spans) // 2]
    for i, (fp, n) in enumerate(ss):
        if fp > p: break
        nxt = ss[i + 1] if i + 1 < len(ss) else None
        if nxt and p < nxt[0]: return str(n) if nxt[1] == n + 1 else ""
        if not nxt: return str(n) if p < fp + med else ""
    return ""



_PDATES = {}
def page_date(item, page):
    """(year, issue, month) of the issue a PDF page belongs to, where a page-to-issue source dates it (the newest
    ocr/runs/OCR-PAGE-DATES-*.tsv, tools/ocr-page-dates.py; 2026-10-10 22:05, on the editor's observation that this had
    happened often: a file holding several years must not date every fact by its one year); None otherwise."""
    if not _PDATES:
        fs = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-PAGE-DATES-*.tsv")))
        _PDATES["_"] = {}
        for l in (open(fs[-1], encoding="utf-8") if fs else []):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 5 and x[1].isdigit():
                _PDATES["_"][(x[0], int(x[1]))] = (x[2], x[3], x[4])
    return _PDATES["_"].get((item, int(page)))

def cite(item, page):
    """«*Title* vol. 8 (1910), n-ro 3 (1910-10), p. 43 (extrap. from iss.) [PDF p. 5]», as far as the tables know."""
    IT, PM = citation_tables()
    r, m = IT.get(item, {}), PM.get((item, int(page)), {})
    t = f"*{r['title']}*" if r.get("title") else f"`{item}`"
    vol = r.get("volume", ""); vol = (vol if vol.startswith("jaro") else f"vol. {vol}") if vol else ""
    yr = r.get("year", ""); iss = r.get("issue", ""); lab = r.get("label_as_filed", ""); dt = r.get("date", "")
    pd_ = page_date(item, page)
    if pd_:   # the page's own issue, for a file holding several (OCR-PAGE-DATES)
        yr, iss, dt = pd_[0], pd_[1], (f"{pd_[0]}, {pd_[2]}" if pd_[2] else "")
    bits = [t] + ([vol] if vol else []) + ([f"({yr})"] if yr else [])
    s = " ".join(bits)
    src, disp = m.get("source", ""), m.get("printed_display", "")
    fs = "" if iss else issue_from_starts(r, disp)
    if iss: s += f", n-ro {iss}" + (" (the page's issue)" if pd_ else "")
    elif fs: s += f", n-ro {fs} (from the issue starts)"
    elif lab and r.get("parsed_by") in ("B", "N", "Y"): s += f", [{lab} as filed]"
    if dt: s += f" ({dt})"
    if item in _BDSEC:
        bp = bd_pdf(item, page)
        return f"{s}, ¶ {page} (section {_BDSEC[item].get(int(page), '?')}{', ' + bp if bp else ''}) [born-digital]"
    if item in _BDPAGED and not disp:   # a typed PDF without a page-map row: its printed page is its PDF page (22:05)
        return f"{s}, p. {page} [PDF p. {page}; a typed PDF]"
    pg = {"front": "front matter", "skipped": "a digitiser's sheet", "?": "p. ?"}.get(src) or (f"p. {disp}" if disp else "p. ?")
    return f"{s}, {pg} [PDF p. {page}]"


def lexicon(path):
    """folded form → occurrences in the corpus (tools/ocr-corpus-lexicon.py)."""
    if not path:
        c = sorted(glob.glob(os.path.join(S, "ocr-work", "ocr-lexicon-*.tsv")))
        path = c[-1] if c else None
    out = {}
    if path:
        for l in open(path, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 2 and x[1].isdigit():
                out[x[0]] = int(x[1])
    return out


def tier(how, form, targets, stem):
    """the kind of match, strongest first (TIERS)."""
    if stem:
        return "stem"
    if not how.startswith("word"):
        return "join"
    if "measured OCR confusion" in how:
        return "confusion"
    if form in targets:
        return "exact"
    for tg in targets:
        if bool(_CYR.search(form)) == bool(_CYR.search(tg)):
            cap = 1 if len(tg) <= 6 else 2
            if NS.edits(form, tg, cap) <= cap or (_CYR.search(tg) and NS.stem_close(form, tg, cap)):
                return "near"
    if any(bool(_CYR.search(form)) != bool(_CYR.search(tg)) for tg in targets):
        return "translit"
    return SCRR


def stem_match(stems, text):
    return [(p, "stem", r) for p, pt in IX.pages(text) for r in NS.normalise(pt).split()
            if any(NS.fold(r).startswith(s) for s in stems)]


def search_item(job):
    """one item: {person: [(text, page, how, as read)]} for every person of the roster."""
    item, files, people, stem, strong = job
    out = collections.defaultdict(list)
    size = [0, 0]  # pages, words searched (for the record's timing line)
    for f in files:
        text = read_text(f)
        rel = os.path.relpath(f, S)
        size[0] += len(IX.pages(text)); size[1] += len(text.split())
        if stem:
            for label, forms in people:
                out[label] += [(rel, p, how, r) for p, how, r in stem_match([NS.fold(x) for x in forms], text)]
            continue
        idx = IX.build(text, words_only=strong)
        for label, forms in people:
            for fm in forms:
                hs = [(rel, p, how, r) for p, how, r in IX.match(fm, idx)]
                out[label] += strong_hits(hs, forms) if strong else hs
    out["\0size"] = size
    return item, dict(out)


# ONE INDEX OVER ALL THE ITEMS (2026-10-17; approved by the editor): the issues of a periodical share most of
# their words, and each issue's own index compared every person against them anew (Ruslanda Esperantisto, 32 issues).
# The items' indexes are merged into one, each entry keyed (item, text, page); each worker builds it once and takes a
# share of the roster, so every person is compared once against the source's distinct forms. ocr_index.match() is
# unchanged: it uses the page only as a key, so the hits and the rule that a name's second form is tried only on pages
# its first form did not hit are as before, page by page of each item.
_UNION = None
_STRONG = False
# THE STRONG SEARCH KEEPS ITS STRONG TIERS ONLY (2026-10-24; the editor): La Ondo de Esperanto's strong
# search wrote 11.8 GB of hits, nearly all «translit», a short Latin name against a Russian word at two edits («pugh»
# against «пеш», «fey» against «день»), a tier tools/dowse-reader-roster.py, the strong search's one reader, never takes
# (its STRONG: exact, near, confusion). The matching is unchanged (ocr_index.match(), the rule that a name's second form
# is tried only on pages its first did not hit): only the hits of the other tiers are dropped in the workers, before
# they are gathered or written, so the readers' roster is the same.
STRONG_TIERS = {"exact", "near", "confusion"}


def strong_hits(hs, forms):
    tg = {NS.fold(max(re.findall(r"[^\W\d_]+", f), key=len)) for f in forms}
    return [h for h in hs if tier(h[-2], NS.fold(re.sub(r"\s*…\s*", "", h[-1]).replace(" ", "")), tg, False) in STRONG_TIERS]


def build_union(ujobs):
    U = IX.Index()
    base = 0
    for item, files, strong in ujobs:
        for f in files:
            text = read_text(f)
            rel = os.path.relpath(f, S)
            idx = IX.build(text, words_only=strong)
            for form, lst in idx.words.items():
                U.words[form] += [((item, rel, p), r) for p, r in lst]
            for form, lst in idx.pairs.items():
                U.pairs[form] += [((item, rel, p), r) for p, r in lst]
            for form, lst in idx.parts.items():
                U.parts[form] += [((item, rel, p), occ + base, k, t, r) for p, occ, k, t, r in lst]
            U.splits += [((item, rel, p), t, r, nxt) for p, t, r, nxt in idx.splits]
            base += 10 ** 9                       # occurrence numbers stay unique across the texts
    return U.bucket()


def _union_init(ujobs):
    global _UNION, _STRONG
    _UNION = build_union(ujobs)
    _STRONG = any(strong for _it, _f, strong in ujobs)


def search_people(chunk):
    """a share of the roster against the union index: {person: [((item, text, page), how, as read)]}."""
    out = {label: [h for fm in forms for h in IX.match(fm, _UNION)] for label, forms in chunk}
    if _STRONG: out = {label: strong_hits(out[label], forms) for label, forms in chunk}
    return out


def search_people_slotted(chunk):
    with CW.slot():
        return search_people(chunk)


def search_item_slotted(job):
    with CW.slot():
        return search_item(job)


def read_roster(path):
    """[(label, forms)], {label: [first names and initials]}, {label: {titles, folded}}. A line may end
    « || first: Joseph, Jos., J., Józef || titles: S-ro, M., Sergent »: the person's first names and initials, and the
    titles they can carry, for people who share a surname (the label then carries the first first name)."""
    people, firsts, titles = [], {}, {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l and not l.startswith("#"):
            parts = l.split(" || ")
            forms = [x.strip() for x in parts[0].split(" | ") if x.strip()]
            fs, ts = [], []
            for part in parts[1:]:
                k, _, v = part.partition(":")
                vals = [x.strip() for x in v.split(",") if x.strip()]
                if k.strip() == "first":
                    fs = vals
                elif k.strip() == "titles":
                    ts = vals
                else:
                    sys.exit(f"roster: unknown field «{k.strip()}» in: {l}")
            label = forms[0] + (f" ({fs[0]})" if fs else "")
            if label in {p[0] for p in people}:
                sys.exit(f"roster: two lines with the label «{label}»; give first names (« || first: … »)")
            people.append((label, forms))
            if fs:
                firsts[label] = fs
            if ts:
                titles[label] = {_bare(t) for t in ts if _bare(t)}
    return people, firsts, titles


# SAME SURNAME, DIFFERENT PEOPLE (the editor ruled on 2026-10-06 19:5x that the instances of a surname are first
# told apart by first name or initial, then the remainder resolved by contextual reading, a residue remaining for
# arbitration). Each hit
# of a shared surname is sorted by the words beside it: before it («L. L. Zamenhof», «Joseph Jamin»), or after it when
# nothing precedes («Jamin, Jos.», «Заменгофъ Л. Л.»). Titles end the run and decide nothing (both Zamenhofs were doctors).
TITLES = {NS.fold(x) for x in ("dro", "d-ro", "sro", "s-ro", "sino", "s-ino", "fino", "f-ino", "s", "m", "mr", "mrs",
          "mme", "mlle", "dr", "prof", "profesoro", "doktoro", "sinjoro", "sinjorino", "fraŭlino", "herr", "frau",
          "monsieur", "madame", "г", "гнъ", "г-нъ", "гжа", "г-жа", "д-ръ", "дръ", "докторъ", "профессоръ", "la", "de",
          # the French doctor's title as the OCR reads it (second dry run: «D'», «D"», «Dre», «D°», «Docteur»), and
          # other words that sit before a name in a list
          "d", "dre", "do", "docteur", "doct", "mm", "messieurs", "mmes", "abbe", "pere", "sr", "le", "les", "et",
          "kaj", "und", "von", "van")}


def _bare(tok):
    return NS.fold(re.sub(r"[^\w]", "", tok))


def _initial(tok):
    # with its full stop («и», «в», «с» are Russian words), or the stop misread as a comma («L,»)
    return bool(re.fullmatch(r"[^\W\d_][.,],?", tok))


def _abbrev_of(b, name):
    """«jos» of «joseph», «leop» (or «lcop», one letter misread) of «leopold»: three letters or more."""
    return len(b) >= 3 and len(b) < len(name) and (name.startswith(b) or (len(b) >= 4 and NS.edits(b, name[:len(b)], 1) <= 1))


# plural titles: the hit is ALL of the people who share the surname («MM. Jamin», «S-oj Jamin», «al la fratoj Zamenhof»)
# — but only those of them who can carry the plural's singular («fratoj», «MM.» are the men; «Mmes» the women); a
# person with no titles listed is not ruled out; «gesinjoroj» (men and women) is everyone
_MALE, _FEMALE = {"sro", "sinjoro", "m", "monsieur", "mr", "herr", "г", "гнъ"}, {"sino", "sinjorino", "mme", "madame", "frau", "гжа"}
PLURAL = {NS.fold(k): v for k, v in (("mm", _MALE), ("messieurs", _MALE), ("soj", _MALE), ("sroj", _MALE),
                                      ("sinjoroj", _MALE), ("fratoj", _MALE), ("fratojn", _MALE), ("frères", _MALE),
                                      ("gg", _MALE), ("гг", _MALE), ("mmes", _FEMALE), ("sinoj", _FEMALE),
                                      ("gesinjoroj", None), ("gesroj", None))}


FUNCTION = {NS.fold(x) for x in ("la", "de", "le", "les", "et", "kaj", "und", "von", "van")}  # end a run; not titles
# REAL titles: only these (and the titles on the roster's lines) narrow who a hit can be. The OCR's fragments of a
# title («S°», «Sr»», «S“)» for a superscript S-ro; «Do», «D'o» for D-ro) end a run but are not read as a title, so they
# never overrule a first name (second dry run: «S° Léopold Jamin», «Sr» Jos. Jamin»)
REAL = {_bare(x) for x in ("S-ro", "Sinjoro", "S-ino", "Sinjorino", "F-ino", "Fraŭlino", "M.", "Monsieur", "Mme",
        "Madame", "Mlle", "Mademoiselle", "Mr", "Mrs", "Miss", "Herr", "Frau", "Fräulein", "Dr", "D-ro", "Doktoro",
        "Docteur", "Prof.", "Profesoro", "Professeur", "Sergent", "Serĝento", "Lieutenant", "Leŭtenanto",
        "Sous-lieutenant", "Kapitano", "Capitaine", "Kolonelo", "Colonel", "Komandanto", "Commandant", "Abbé", "Pastro",
        "Г.", "Г-нъ", "Г-жа", "Д-ръ", "Докторъ", "Профессоръ")}


def sort_hit(toks, i, group, firsts, titles=None):
    """the hit at toks[i] (a shared surname): ('assigned', label) · ('all', [labels]) · ('ambiguous', [labels]) ·
    ('titled', title) · ('unlisted', word) · ('bare', None). TITLES DECIDE BY CONTEXT (the editor ruled on 2026-10-06
    21:1x that whether a title decides anyone is contextual, and that establishing the context means establishing the
    attributes titles would disambiguate on; built 21:1x, approved by the editor): the titles each person can carry are on their roster
    line; a title just before the name (or before its initials) keeps only the people who can carry it — «F-ino L.
    Zamenhof» is Lidja, «Sergent Jamin» Léopold — and a person with no titles listed is not ruled out by one. A bare hit
    whose title fits nobody is «titled»: no default takes it, unless the default person can carry that title."""
    titles = titles or {}
    names = {_bare(w) for lab in group for f in firsts.get(lab, ()) for w in f.split() if len(_bare(w)) > 1}
    known = TITLES | set(PLURAL) | {t for lab in group for t in titles.get(lab, ())}

    def namelike(t):
        b = _bare(t)
        return bool(b) and b not in known and (_initial(t) or b in names or any(_abbrev_of(b, n) for n in names) or
                                               (len(b) >= 5 and any(NS.edits(b, n, 1) <= 1 for n in names if len(n) >= 5)))
    run, j = [], i - 1
    while j >= 0 and namelike(toks[j]):
        run.insert(0, toks[j]); j -= 1
    tpos = j
    if not run and (toks[i].endswith(",") or (i + 1 < len(toks) and _initial(toks[i + 1]))):
        k = i + 1
        while k < len(toks) and namelike(toks[k]):
            run.append(toks[k]); k += 1
    real = (REAL | {t for lab in group for t in titles.get(lab, ())}) | set(PLURAL)
    title = _bare(toks[tpos]) if tpos >= 0 and _bare(toks[tpos]) in real - FUNCTION else None
    if title in PLURAL:
        sing = PLURAL[title]
        return ("all", [c for c in group if sing is None or c not in titles or titles[c] & sing])

    def fit(cands):
        return [c for c in cands if c not in titles or title in titles[c]] if title else list(cands)
    if not run:
        if title:
            who = [c for c in group if title in titles.get(c, ())]
            if len(who) == 1:
                return ("assigned", who[0])
            if not who and any(c in titles for c in group):
                return ("titled", toks[tpos])
            return ("bare", None)
        prev = toks[i - 1] if i > 0 else ""
        if prev[:1].isupper() and _bare(prev) and _bare(prev) not in known and not _initial(prev):
            return ("unlisted", prev)
        return ("bare", None)
    full = [_bare(t) for t in run if len(_bare(t)) > 1]
    if full:
        who = [lab for lab in group if any(
            any(_bare(w) == b or _abbrev_of(b, _bare(w)) or (len(b) >= 5 and NS.edits(b, _bare(w), 1) <= 1) for b in full)
            for f in firsts.get(lab, ()) for w in f.split())]
    else:
        seq = [_bare(t) for t in run]
        who = [lab for lab in group if any([_bare(w)[:1] for w in f.split()][:len(seq)] == seq
                                           for f in firsts.get(lab, ()))]
    narrowed = fit(who)
    if len(narrowed) == 1:
        return ("assigned", narrowed[0])
    if narrowed:
        return ("ambiguous", narrowed)
    if who:
        return ("titled", toks[tpos])  # the initials fit, the title fits none of them
    return ("unlisted", " ".join(run))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms", nargs="*", help="the forms of ONE name (the one-name way)")
    ap.add_argument("--roster", help="a roster file: one person per line, forms separated by « | »")
    ap.add_argument("--items", help="item-name patterns, comma-separated, or @file (default: every item)")
    ap.add_argument("--write", required=True)
    ap.add_argument("--stem", action="store_true", help="theme words: folded prefix match, no fuzziness")
    ap.add_argument("--ledger", default=None, help="default: the CURRENT ledger named in the status record (an internal record, not published)")
    ap.add_argument("--lexicon", default=None, help="default: the newest ocr-work/ocr-lexicon-*.tsv")
    ap.add_argument("--exclude", default="", help="forms judged noise, comma-separated (as read; folded here)")
    ap.add_argument("--exclude-as-read", default="", help="spellings judged noise EXACTLY as printed, case and accents "
                    "kept, punctuation ignored, comma-separated (e.g. «kabe» to set aside lowercase hits of a name that is "
                    "also a word)")
    ap.add_argument("--judgements", default=None, help="a judgement file: per person, the tier reading stopped at, "
                    "forms set aside, pages confirmed, why (see the module docstring)")
    ap.add_argument("--from-hits", default=None, help="rebuild the record from a saved <record>.hits.tsv, no search")
    ap.add_argument("--where-max", type=int, default=None,
                    help="list the places of a form with at most this many hits (default: all with --items, else 10)")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--mode", choices=("solo", "shared"), default=None,
                    help="the worker count by the editor's two modes (2026-10-14: 40%% of cores when running alongside "
                         "a parallelised cupel, 80%% of cores when running solo), from tools/cupel_workers.py; overrides --jobs")
    ap.add_argument("--profile", type=int, default=0, metavar="N",
                    help="measure only: search the first item for the first N people in this process under cProfile, "
                         "print the 20 costliest functions, write nothing")
    ap.add_argument("--per-item", action="store_true",
                    help="the old way: each item its own index (one index over all items is the default from 2026-10-17)")
    ap.add_argument("--strong-only", action="store_true",
                    help="single words only (the tiers exact, near, confusion that the readers' roster takes; no joins): "
                         "for tools/dowse-reader-roster.py at scale; NOT a presence record, its silences say nothing")
    ap.add_argument("--born-digital", choices=("signed", "proposed", "none"), default="signed",
                    help="the born-digital lists searched beside the ledger: SIGNED only (default), PROPOSED too (a "
                         "test: their silences are labelled «proposed, not signed»), or none")
    a = ap.parse_args()
    if a.mode:                                   # the same count the cupel uses (cupel_workers.total)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from cupel_workers import total as _workers
        a.jobs = _workers(a.mode)
        print(f"mode {a.mode}: {a.jobs} worker processes", file=sys.stderr)
    people, firsts, titles = (read_roster(a.roster) if a.roster
                              else (([(a.forms[0], a.forms)] if a.forms else []), {}, {}))
    if not people:
        sys.exit("give the forms of a name, or --roster")
    hits_tsv = re.sub(r"\.md$", "", a.write) + ".hits.tsv"
    sur_tsv = re.sub(r"\.md$", "", a.write) + ".surnames.tsv"
    for p in (a.write, sur_tsv) + (() if a.from_hits else (hits_tsv,)):
        if os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    where_max = a.where_max if a.where_max is not None else (10 ** 9 if a.items else 10)
    ledger = a.ledger or current_ledger()
    led = [x for x in (l.rstrip("\n").split("\t") for l in open(ledger, encoding="utf-8")) if x and not x[0].startswith("#")]
    rows = {x[0]: dict(zip(led[0], x)) for x in led[1:]}
    bdl = {} if a.born_digital == "none" else BDL.lists(a.born_digital)
    if a.items:
        pats = ([l.strip() for l in open(a.items[1:], encoding="utf-8") if l.strip()] if a.items.startswith("@")
                else [p.strip() for p in a.items.split(",") if p.strip()])
        rows = {k: v for k, v in rows.items() if any(fnmatch.fnmatch(k, p) for p in pats)}
        bdl = {k: v for k, v in bdl.items() if any(fnmatch.fnmatch(k, p) for p in pats)}
        if not rows and not bdl:
            sys.exit(f"no ledger or born-digital item matches {pats}")
    signed = signed_lines()
    # BORN-DIGITAL ITEMS (2026-10-10; as agreed in review, an internal record, 2026-10-09, not published): searched in
    # their normalised text as given (no OCR readings, no gate), each paragraph a «page» (¶ N); their silences are
    # reported like a signed item's, from a line built out of the list row: class, scope and the kind from the item table
    IT0, _ = citation_tables()
    if not IT0.get(next(iter(bdl), ""), {}).get("kind") and bdl:
        dts = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-ITEM-DATES-*.tsv")))
        kinds = {x[0]: x[3] for x in (l.rstrip("\n").split("\t") for l in (open(dts[-1], encoding="utf-8") if dts else []))
                 if len(x) > 3 and not x[0].startswith("#")}
    else:
        kinds = {}
    for it, b in bdl.items():
        if it in rows:
            sys.exit(f"born-digital item {it} is also a ledger item")
        tp = BDL.text_path(b)
        txt_ = open(tp, encoding="utf-8").read()
        if BDL.is_paged(b):   # a typed PDF: its PDF pages, as for an OCR text
            ps_ = BDL.page_numbers(txt_)
            if not ps_:
                sys.exit(f"{it}: its list row says «pages: pdf» but its text has no «=== page N ===» marker")
            _BDPAGED[it] = set(ps_); n = max(ps_)
        else:
            bl = BDL.blocks(txt_)
            _BDSEC[it] = {n: sec for n, sec, _ in bl}
            n = len(bl)
        kind = IT0.get(it, {}).get("kind") or kinds.get(it, "")
        conds = [{"PRIMARY": "PRIMARY", "SECONDARY": "SECONDARY LITERATURE"}.get(kind, f"kind not yet known")]
        sc = b.get("scope", "whole").strip()
        ms = re.fullmatch(r"sections? (\d+)(?:[–-](\d+))?", sc)
        if ms and it in _BDSEC:
            lo, hi = int(ms.group(1)), int(ms.group(2) or ms.group(1))
            ps = [q for q, sec in _BDSEC[it].items() if lo <= sec <= hi]
            if ps: conds.insert(0, f"SCOPE: absence admissible on pages {min(ps)}–{max(ps)} only — {sc}")
        elif sc != "whole":
            conds.append(f"scope «{sc}»")
        status = "" if b["file"].find("-SIGNED-") >= 0 else " (proposed, not signed)"
        x = [it, (f"pp. 1–{n} of {n}" if it in _BDPAGED else f"¶ 1–{n} of {n}"),
             f"{b.get('class', '')}{status} · born-digital" + (" (a typed PDF, by PDF page)" if it in _BDPAGED else ""), f"search {b.get('path', '')}",
             "conditions: " + "; ".join(conds)]
        signed[it] = (b["file"], x, [x])
        rows[it] = {"corpus": it, "class": b.get("class", "")}
    pdfl = sorted(f for f in glob.glob(os.path.join(S, "OCR-PDF-LIST-*.txt")) if not f.endswith("-NEW.txt"))[-1]
    pdf = {os.path.splitext(os.path.basename(p))[0]: p for p in (l.strip() for l in open(pdfl)) if p}
    t0 = datetime.datetime.now()
    res = {}  # item -> {person: [(text, page, how, as read)]}
    if a.from_hits:
        res = {it: collections.defaultdict(list) for it in rows}
        for l in open(a.from_hits, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 8 and x[0] != "person" and not x[0].startswith("#") and x[1] in res:   # >= 8: the citation columns follow (2026-10-08)
                res[x[1]][x[0]].append((x[3], int(x[4]), x[5], x[6]))
    else:
        jobs = []
        for it in rows:
            if it in bdl:
                jobs.append((it, [BDL.text_path(bdl[it])], people, a.stem, a.strong_only)); continue
            line = signed.get(it)
            allr = os.path.join(S, "ocr-rendersearch-all", it + ".txt")
            files = ([allr] if line and "ocr-rendersearch-all" in line[1][3] else
                     [os.path.join(S, "ocr-rendersearch", it + ".txt")] + ([allr] if not line else []))
            files += [os.path.join(S, f"ocr-rendersearch-{c}", it + ".txt") for c in ("rus", "hye", "kat")]
            jobs.append((it, [f for f in files if os.path.exists(f)], people, a.stem, a.strong_only))
        # one item a task (2026-10-17): with chunksize 4, the 32 issues of Ruslanda Esperantisto made 8 tasks for 14
        # workers, six idle and each busy one working four issues in turn; the largest items first, so none is left last
        jobs.sort(key=lambda j: -sum(os.path.getsize(f) for f in j[1]))
        if a.profile:                             # 2026-10-17: where a search's time goes, before changing it further
            import cProfile, pstats
            it, files, _, stem_, strong = jobs[-1]
            pr = cProfile.Profile(); pr.enable()
            search_item((it, files, people[:a.profile], stem_, strong))
            pr.disable()
            pstats.Stats(pr).sort_stats("tottime").print_stats(20)
            sys.exit(0)
        if len(jobs) > 1 and not a.stem and not a.per_item:
            ujobs = [(it, files, strong) for it, files, _, _, strong in jobs]
            n = max(1, min(len(people), a.jobs * 8))  # shares of the roster, small enough to keep every worker busy
            chunks = [people[i::n] for i in range(n)]
            res = {it: {label: [] for label, _ in people} for it, *_ in jobs}   # roster order, as search_item keys them
            with Pool(a.jobs, initializer=_union_init, initargs=(ujobs,)) as pool:
                for part in pool.imap_unordered(search_people_slotted, chunks):
                    for label, hs in part.items():
                        for (it, rel, p), how, r in hs:
                            res[it][label].append((rel, p, how, r))
            for it, files, *_ in jobs:            # the record's size line, as search_item counts it
                size = [0, 0]
                for f in files:
                    text = read_text(f)
                    size[0] += len(IX.pages(text)); size[1] += len(text.split())
                order = {os.path.relpath(f, S): k for k, f in enumerate(files)}
                for label in res[it]:                 # text by text, as search_item lists them (a stable sort)
                    res[it][label].sort(key=lambda h: order[h[0]])
                res[it]["\0size"] = size
        else:
            with Pool(a.jobs) as pool:
                res = dict(pool.imap_unordered(search_item_slotted, jobs, chunksize=1))
    secs = (datetime.datetime.now() - t0).seconds
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_utime
    sizes = [v.pop("\0size") for v in res.values() if "\0size" in v]
    n_pages, n_words = sum(x[0] for x in sizes), sum(x[1] for x in sizes)
    lex = lexicon(a.lexicon)
    BD = born_digital() | {(it, q) for it in _BDSEC for q in _BDSEC[it]} | {(it, q) for it in _BDPAGED for q in _BDPAGED[it]}   # a born-digital text needs no image check
    META, meta_table = modern_metadata()
    excl = {NS.fold(x) for x in a.exclude.split(",") if x.strip()}
    spell = lambda r: re.sub(r"[^\w]", "", unicodedata.normalize("NFC", r))  # as printed: case and accents kept
    excl_ar = {spell(x) for x in a.exclude_as_read.split(",") if x.strip()}
    tg_of = {label: {NS.fold(max(re.findall(r"[^\W\d_]+", f), key=len)) for f in forms} for label, forms in people}
    formof = lambda r: NS.fold(re.sub(r"\s*…\s*", "", r).replace(" ", ""))
    if not a.from_hits:
        with open(hits_tsv, "w", encoding="utf-8") as fh:
            fh.write(f"# GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}: every hit, before any exclusion. "
                     "Column «printed» is in the page map's forms, not always digits: «352», «352 (extrap. from iss.)», "
                     "«352 (extrap. from vol.)», «3 (counted)», a range «140–141», a roman «iv», «front» (before printed page 1), "
                     "«skipped» (a digitiser's sheet), «?» (not given); take the leading number where digits are needed. "
                     "Column «issue»: the issue as the file is named; «12 (from the issue starts)» for a volume held in parts, from "
                     "ocr/runs/OCR-ISSUE-STARTS.tsv; otherwise the part of the name as filed (e.g. «part 3»), which is not an issue.\n")
            # the citation columns (2026-10-08) come LAST, so readers of columns 1–8 by position are unchanged
            # «locator» (2026-10-10) comes last for the same reason: for a born-digital item, «page» is the ¶ number and
            # «locator» reads «¶ N, section M»; empty for every OCR item
            # «metadata» (2026-10-10), last: the kind of modern metadata the hit's page or ¶ is (OCR-MODERN-METADATA), else empty
            # «page_year», «page_issue» (2026-10-10), last: the year and issue of the issue the hit's PDF page belongs to,
            # where OCR-PAGE-DATES dates it (a file holding several years); empty otherwise, when «year» stands
            fh.write("person\titem\ttier\ttext\tpage\thow\tas_read\tform\ttitle\tvolume\tyear\tissue\tprinted\tlocator\tmetadata\tpage_year\tpage_issue\n")
            IT, PM = citation_tables()
            for it in sorted(res):
                ir = IT.get(it, {})
                for label, hs in sorted(res[it].items()):
                    for f, p, how, r in hs:
                        pm = PM.get((it, int(p)), {})
                        fh.write(f"{label}\t{it}\t{tier(how, formof(r), tg_of[label], a.stem)}\t{f}\t{p}\t{how}\t{r}\t{formof(r)}"
                                 f"\t{ir.get('title', '')}\t{ir.get('volume', '')}\t{ir.get('year', '')}\t{ir.get('issue', '') or (lambda x: f'{x} (from the issue starts)' if x else '')(issue_from_starts(ir, pm.get('printed_display', ''))) or ir.get('label_as_filed', '')}"
                                 f"\t{pm.get('printed_display', '') or {'front': 'front', 'skipped': 'skipped'}.get(pm.get('source', ''), '')}"
                                 f"\t{(f'¶ {p}, section {_BDSEC[it].get(int(p), chr(63))}' + ((', ' + bd_pdf(it, p)) if bd_pdf(it, p) else '') if it in _BDSEC else '')}"
                                 f"\t{META.get((it, int(p)), '')}"
                                 f"\t{(page_date(it, p) or ('', ''))[0]}\t{(page_date(it, p) or ('', ''))[1]}\n")
    # modern metadata: its hits leave the reading here (they stay in the hits table, marked), and are reported apart
    MH = collections.defaultdict(list)   # person -> [(item, page, kind, as read)]
    DIS = []                             # copy disagreements: (person, work, present in, silent in)
    for it in res:
        for label in list(res[it]):
            keep = []
            for h in res[it][label]:
                k = META.get((it, int(h[1])))
                (MH[label].append((it, int(h[1]), k, h[3])) if k else keep.append(h))
            res[it][label] = keep
    # per person: tiered hits, after exclusions (everyone's, then the person's own judgement)
    J = read_judgements(a.judgements)
    unknown = sorted(set(J) - {label for label, _ in people})
    if unknown:
        sys.exit(f"judgements name people not on the roster: {', '.join(unknown)}")
    jx = {label: ({NS.fold(x) for x in J[label]["exclude"].split(",") if x.strip()},
                  {spell(x) for x in J[label]["exclude-as-read"].split(",") if x.strip()}) for label in J}
    T = collections.defaultdict(list)  # person -> [(tier, item, text, page, how, as read, form)]
    excluded = collections.Counter()
    excluded_p = collections.defaultdict(collections.Counter)  # person -> their own exclusions' hits
    # people who share a surname, with first names given: their hits are sorted by first name (sort_hit)
    grp = {la: tuple(lb for lb, _ in people if lb in firsts and tg_of[lb] & tg_of[la]) for la, _ in people if la in firsts}
    grp = {la: g for la, g in grp.items() if len(g) > 1}
    unsorted = sorted({la for la, _ in people for lb, _ in people
                       if la != lb and tg_of[la] & tg_of[lb] and (la not in grp or lb not in grp)})
    assign_of = {la: (J[la]["assign"] if la in J else set()) for la, _ in people}
    # «not»: pages where the shared surname, unsorted by first name, is shown NOT to be this person (another word, or a
    # namesake: Paul Jamin of Dijon, «boulevard Jamin» in Reims); a page all of them disown is not residue
    not_of = {la: (J[la]["not"] if la in J else set()) for la, _ in people}
    # DEFAULT ATTRIBUTION (the editor ruled on 2026-10-06 20:0x that defaults are risky but reasonable, that default
    # attributions are still to be kept apart, and that they may be vetted if the scale is tractable): «default: yes» on one person of
    # a shared surname gives them its bare hits, and the ambiguous ones whose initial they share — kept apart from the
    # hits sorted by first name («by default»), never making anyone else silent, and listed for vetting
    dflt = {}
    for la, g in grp.items():
        if la in J and J[la]["default"].lower() in ("yes", "y", "true"):
            if g in dflt:
                sys.exit(f"judgements: two defaults for one surname: {dflt[g]}, {la}")
            dflt[g] = la
    def default_takes(s, d):
        """a default takes a bare hit, an ambiguous one it is among, and a titled one only if it can carry the title"""
        return (s[0] == "bare" or (s[0] == "ambiguous" and d in s[1])
                or (s[0] == "titled" and (d not in titles or _bare(s[1]) in titles[d])))
    TD = collections.defaultdict(list)     # person -> their hits BY DEFAULT [(tier, item, text, page, how, as read, form, context)]
    _pg, _sorted, kseen = {}, {}, collections.Counter()
    SORT = collections.defaultdict(dict)   # group -> {hit key: (sort, tier, context)}
    RES_T = collections.defaultdict(set)   # (group, item) -> tiers of its unresolved (residue) hits

    def page_toks(f, p):
        if f not in _pg:
            txt = read_text(os.path.join(S, f))
            _pg[f] = {q: NS.normalise(t).split() for q, t in IX.pages(txt)}
        return _pg[f].get(p, [])

    def sort_of(it, f, p, how, r, k, g):
        key = (g, it, f, p, how, r, k)
        if key not in _sorted:
            toks = page_toks(f, p)
            if how.startswith("two words joined"):
                pos = [i for i in range(len(toks) - 1) if toks[i] + " " + toks[i + 1] == r]
            elif how.startswith(("word", "part of")):
                pos = [i for i, t in enumerate(toks) if t == r]
            else:
                pos = []
            if not pos:
                _sorted[key] = (("bare", None), f"«{r}» (context not read: {how.split(' (')[0]})")
            else:
                i = pos[min(k, len(pos) - 1)]
                ctx = " ".join(toks[max(0, i - 5):i] + [f"**{toks[i]}**"] + toks[i + 1:i + 6])
                _sorted[key] = (sort_hit(toks, i, g, firsts, titles), ctx)
        return _sorted[key]
    # FIXED ORDER (2026-10-08): a run fills «res» in the order the worker processes finish (imap_unordered), a rebuild
    # (--from-hits) in item order; everything below that keeps first-come order (form tables, their shown spelling,
    # the shared-surname sort) then differed between a run and its rebuild, and between two runs (found
    # 2026-10-08 15:2x). Items and people are walked in sorted order; each person's hits keep the order the hits
    # table records, which is the same on both paths.
    for it in sorted(res):
        per = res[it]
        for label in sorted(per):
            hs = per[label]
            own, own_ar = jx.get(label, (set(), set()))
            for f, p, how, r in hs:
                fm = formof(r)
                if fm in excl:
                    excluded[fm] += 1; continue
                if spell(r) in excl_ar:
                    excluded["as read: " + spell(r)] += 1; continue
                if fm in own:
                    excluded_p[label][fm] += 1; continue
                if spell(r) in own_ar:
                    excluded_p[label]["as read: " + spell(r)] += 1; continue
                t_ = tier(how, fm, tg_of[label], a.stem)
                if label in grp:
                    g = grp[label]
                    k = kseen[(label, it, f, p, r)]; kseen[(label, it, f, p, r)] += 1
                    s, ctx = sort_of(it, f, p, how, r, k, g)
                    SORT[g][(it, f, p, how, r, k)] = (s, t_, ctx)
                    decided = s[0] in ("assigned", "all")
                    mine = (s == ("assigned", label) or (s[0] == "all" and label in s[1])
                            or (not decided and (it, p) in assign_of[label] and (it, p) not in not_of[label]))
                    if not mine:
                        unres = (not decided and not any((it, p) in assign_of[o] for o in g)
                                 and (it, p) not in not_of[label] and not all((it, p) in not_of[o] for o in g))
                        if unres and t_ in STRONG and dflt.get(g) == label and default_takes(s, label):
                            TD[label].append((t_, it, f, p, how, r, fm, ctx)); continue
                        # the residue holds only unresolved hits of the strong tiers: a weak hit nobody can claim is
                        # presumed noise anyway (the rule that the tiers are not walked down)
                        if unres and t_ in STRONG:
                            RES_T[(g, it)].add(t_)
                        continue
                T[label].append((t_, it, f, p, how, r, fm))
    # per person and item: the pages of each tier, and what the item says (reading())
    PT = {label: collections.defaultdict(lambda: collections.defaultdict(set)) for label, _ in people}
    TS = collections.defaultdict(set)  # (person, item) -> alphabets of its translit hits
    for label, hs in T.items():
        for h in hs:
            PT[label][h[1]][h[0]].add(h[3])
            if h[0] == "translit":
                TS[(label, h[1])].add("cyr" if _CYR.search(h[6]) else "lat")
    PTD = collections.defaultdict(lambda: collections.defaultdict(set))  # person -> item -> tiers of default hits
    for label, hs in TD.items():
        for h in hs:
            PTD[label][h[1]].add(h[0])
    stop_of = {label: (J[label]["stop"] if label in J else "join") for label, _ in people}
    conf_of = {label: (J[label]["confirmed"] if label in J else set()) for label, _ in people}
    given = {label: {"cyr" if _CYR.search(f.lower()) else "lat" for f in forms} for label, forms in people}

    def read_item(label, it, stop=None):
        if a.stem:
            return "present" if PT[label].get(it) else "silent"
        rd = reading(PT[label].get(it, {}), any(c[0] == it for c in conf_of[label]), stop or stop_of[label],
                     bool(TS[(label, it)] - given[label]))
        if rd in ("silent", "presumed noise") and any(
                TIERS.index(t) <= TIERS.index(stop or stop_of[label]) for t in PTD[label].get(it, ())):
            return "by default"  # present only through the default attribution: kept apart, to be vetted
        if label in grp and rd in ("silent", "presumed noise") and any(
                TIERS.index(t) <= TIERS.index(stop or stop_of[label]) for t in RES_T[(grp[label], it)]):
            return "residue"  # the shared surname is there, unresolved: neither present nor silent
        return rd
    roster_way = len(people) > 1 or bool(a.items)
    L = [f"# dowse: {people[0][0] if len(people) == 1 else f'{len(people)} people'}"
         + (f" × {len(rows)} items ({a.items})" if a.items else " × the whole corpus") + (" (theme stems)" if a.stem else ""), "",
         f"`[GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}, in {secs} s. Ledger "
         f"{os.path.basename(ledger)}; signed files: the union of OCR-ACCEPTANCE-LINES-*-SIGNED*.txt (later holds). "
         f"Searched {len(rows)} items, uncapped. Every hit: `{os.path.basename(a.from_hits or hits_tsv)}`. Every hit is a "
         f"CANDIDATE until confirmed on the page image. Do not hand-edit — re-run it."
         + (" STRONG TIERS ONLY (--strong-only): single words, no joins, for the readers' roster; NOT a presence record, "
            "its silences say nothing." if getattr(a, "strong_only", False) else "") + "]`", "",
         (f"**Size and time:** {len(rows):,} items, {n_pages:,} pages, {n_words:,} words searched (each text counted once, "
          f"the texts in other alphabets included), {len(people):,} people; {secs:,} s wall-clock, {cpu:,.0f} s CPU, "
          f"{a.jobs} processes, on the machine described in METHOD.md." if not a.from_hits else
          "**Rebuilt from a saved hits table:** no search was run."), ""]
    if excl or excl_ar:
        L += ["**Excluded as judged noise** (--exclude, --exclude-as-read; their hits do not count, so an item hit only by "
              "them is silent): " + ", ".join([f"«{k}» ({excluded[k]} hits)" for k in sorted(excl)]
              + [f"«{k}» exactly as printed ({excluded['as read: ' + k]} hits)" for k in sorted(excl_ar)]), ""]
    if roster_way:
        L += ["## Summary: pages per person, by tier, and what the items say", "",
              "PAGES, not hits (a page with the name twice, or in two readings, counts once). «read to»: the person's "
              "cutoff (the judgement file; default every tier). Items, by their strongest tier at or above the cutoff: "
              "exact or candidate (near, confusion); underspecified (translit hits in an alphabet the person was given "
              "no form in: give that form and search again); confirm (translit first, both alphabets given: almost "
              "certainly noise, to be judged); presumed noise (small caps and run-ins, or join, only); silent. "
              "Underspecified and confirm items are neither present nor silent; presumed noise counts as silent unless "
              "a page is confirmed.", "",
              "| person | " + " | ".join(TIERS[:6]) + " | read to | exact or candidate | present by default "
              "| underspecified | confirm | shared-surname residue | presumed noise | silent | silent or noise, signed: "
              "whole | silent or noise, signed: in part |",
              "|---|" + "---:|" * 6 + "---|" + "---:|" * 9]
        for label, forms in people:
            pg = {t: sum(len(PT[label][it].get(t, ())) for it in PT[label]) for t in TIERS[:6]}
            rd = collections.Counter(read_item(label, it) for it in rows)
            sil_s = [it for it in rows if it in signed and read_item(label, it) in ("silent", "presumed noise")]
            ss_w = sum(1 for it in sil_s if silence_cover(signed[it])["whole"]); ss_p = len(sil_s) - ss_w
            L.append(f"| {label} | " + " | ".join(str(pg[t]) for t in TIERS[:6]) + f" | {stop_of[label]} | "
                     f"{rd['exact'] + rd['candidate'] + rd['confirmed on the image']} | {rd['by default']} | {rd['underspecified']} | "
                     f"{rd['confirm']} | {rd['residue']} | {rd['presumed noise']} | {rd['silent']} | {ss_w} | {ss_p} |")
        L.append("")
    if unsorted:
        L += ["**Not sorted by first name:** " + ", ".join(unsorted) + " share a surname with someone on the roster "
              "but have no first names given (« || first: … » on their roster line), so the same hits count for each.", ""]
    # SAME SURNAME, DIFFERENT PEOPLE: each group's hits as sorted, and the residue for the editor's arbitration
    with open(sur_tsv, "w", encoding="utf-8") if grp else open(os.devnull, "w") as fs_:
        fs_.write(f"# GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}: every hit of a shared "
                  "surname, as sorted by first name; «resolved by» names a judgement-file «assign».\n")
        fs_.write("group\titem\tpage\ttier\tsorted\tto\tresolved by\tcontext\ttext\n")
        for g in sorted(set(grp.values())):
            S_ = SORT[g]
            n = collections.Counter()
            resid = []
            for (it, f, p, how, r, k), (s, t_, ctx) in sorted(S_.items()):
                decided = s[0] in ("assigned", "all")
                by = [o for o in g if (it, p) in assign_of[o]] if not decided else []
                if not by and not decided and all((it, p) in not_of[o] for o in g):
                    by = ["not any of them («not»)"]
                d = dflt.get(g)
                if not by and d and t_ in STRONG and not decided and default_takes(s, d):
                    by = [f"default: {d}"]
                    n[f"{s[0]}, by default to {d}"] += 1
                else:
                    n[s[1] if s[0] == "assigned" else ("all of them (a plural title)" if s[0] == "all" else s[0])] += 1
                if not decided and not by and t_ in STRONG:
                    resid.append((it, p, t_, s, ctx))
                who = (s[1] if s[0] == "assigned" else (", ".join(s[1]) if s[0] in ("ambiguous", "all") else (s[1] or "")))
                fs_.write(f"{' · '.join(g)}\t{it}\t{p}\t{t_}\t{s[0]}\t{who}\t{', '.join(by)}\t{ctx}\t{f}\n")
            L += [f"## Shared surname: {' · '.join(g)}", "",
                  "Every hit of the surname, sorted by the words beside it (a first name, or an initial only one of "
                  "them has, or a title only one of them can carry; a plural title is all of them). Ambiguous (an "
                  "initial or title they share), titled (a title none of them carries), unlisted (another first name) "
                  "and bare hits go to contextual reading; a page so resolved is given to its person with «assign» in "
                  "the judgement file. What remains is the RESIDUE, for the editor's arbitration: an item where the "
                  "surname is only in the residue is neither present nor silent for any of them.", "",
                  "| sorted | hits |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in sorted(n.items(), key=lambda kv: (-kv[1], str(kv[0])))]
            L += ["", f"### Residue: {len(resid)} hits on {len({(x[0], x[1]) for x in resid})} pages "
                  "(every sorted hit, with its context: `" + os.path.basename(sur_tsv) + "`)", ""]
            if resid:
                # «ambiguous» in the judgement file: the editor ruled the page undecidable from this text (the editor
                # 2026-10-06 20:3x: an ambiguous datum; the disambiguation, if any, comes from another source)
                amb = {k for o in g for k in (J[o]["ambiguous"] if o in J else set())}
                L += ["| item p. PDF page | tier | sorted | arbitration | context |", "|---|---|---|---|---|"]
                for it, p, t_, s, ctx in resid[:where_max]:
                    lab = s[0] + (f": {', '.join(s[1])}" if s[0] == "ambiguous" else (f": «{s[1]}»" if s[1] else ""))
                    arb = "ruled ambiguous" if (it, p) in amb else "awaiting"
                    L.append(f"| {pl(it, p)} | {t_} | {lab} | {arb} | {ctx.replace('|', '/')} |")
                if len(resid) > where_max:
                    L.append(f"| … | | | {len(resid) - where_max} more: see `{os.path.basename(sur_tsv)}` |")
            L.append("")
    for label, forms in people:
        hs = T[label]
        L += [f"## {label}" + (f" (forms: {' · '.join(forms)})" if len(forms) > 1 else ""), ""]
        if label in J:
            j = J[label]
            L += [f"**Judgement** (`{os.path.basename(a.judgements)}`): read to **{j['stop']}**"
                  + (f"; set aside for this person: " + ", ".join(f"«{k}» ({n} hits)" for k, n in sorted(excluded_p[label].items()))
                     if excluded_p[label] else "")
                  + (f"; confirmed on the image: " + ", ".join(f"{pl(i, p)}" for i, p in sorted(j["confirmed"])) if j["confirmed"] else "")
                  + (f"; shared-surname pages assigned by reading: " + ", ".join(f"{pl(i, p)}" for i, p in sorted(j["assign"])) if j["assign"] else "")
                  + (f"; shared-surname pages shown not to be this person: {len(j['not'])}" if j["not"] else "")
                  + ("; DEFAULT for the shared surname (its bare and shared-initial hits, kept apart)" if label in dflt.values() else "")
                  + (f". Why: {j['why']}" if j["why"] else ""), ""]
        by_t = collections.defaultdict(list)
        for h in hs:
            by_t[h[0]].append(h)
        L += ["| tier | hits | pages | items |", "|---|---:|---:|---:|"] + [
            f"| {t} | {len(by_t[t])} | {len({(h[1], h[3]) for h in by_t[t]})} | {len({h[1] for h in by_t[t]})} |"
            for t in TIERS if by_t[t]]
        for t in TIERS:
            if not by_t[t]:
                continue
            forms_m = collections.defaultdict(list)
            for h in by_t[t]:
                # the exact tier is shown by spelling AS PRINTED (Kabe · KABE · kabe), so the reader sees capitals,
                # accents lost or kept, and lowercase hits that may be another word (editor 2026-10-06 14:1x)
                forms_m[spell(h[5]) if t == "exact" else h[6]].append(h)
            L += ["", f"### {label} · {t}" + (" (by spelling as printed)" if t == "exact" else ""), "",
                  "| form as read | in the corpus (lexicon) | hits | pages | items | where (item p. PDF page) |",
                  "|---|---:|---:|---:|---:|---|"]
            # ties broken by the form, and the spelling shown chosen by count, then alphabetically: never by which hit
            # came first, so a run and its rebuild print the same table (2026-10-08)
            for fm, v in sorted(forms_m.items(), key=lambda kv: (-len({(h[1], h[3]) for h in kv[1]}), kv[0])):
                places = sorted({(h[1], h[3]) for h in v})
                where = ("; ".join(f"{pl(i, p)}" for i, p in places) if len(places) <= where_max
                         else f"{len(places)} pages: see the hits table")
                shown = fm if t == "exact" else min(collections.Counter(h[5] for h in v).items(),
                                                   key=lambda kv: (-kv[1], kv[0]))[0]
                L.append(f"| «{shown}» | {lex.get(v[0][6], '—')} | {len(v)} | {len(places)} | {len({h[1] for h in v})} | {where} |")
        # per item: pages per tier, and what the item says for this person (items with any hit only)
        if not a.stem and PT[label]:
            L += ["", f"### {label} · by item: pages per tier, and what the item says (read to {stop_of[label]})", "",
                  "| item | " + " | ".join(TIERS[:6]) + " | the item says |", "|---|" + "---:|" * 6 + "---|"]
            for it in sorted(PT[label]):
                r = read_item(label, it)
                note = {"underspecified": "underspecified: give the form in the other alphabet and search again",
                        "confirm": "confirm: translit only (both alphabets searched); almost certainly noise",
                        "presumed noise": "presumed noise: counted as no hit unless a page is confirmed"}.get(r, r)
                L.append(f"| {it} | " + " | ".join(str(len(PT[label][it].get(t, ()))) for t in TIERS[:6]) + f" | {note} |")
        # D4, TO CHECK ON THE PAGE IMAGE (the editor 2026-10-06 20:0x asked for a practical limit, and approved this one):
        # per tier read, born-digital pages need no check; the OCR pages are listed in full up to 40, else a blind sample
        # of 40 (fixed seed), and the tier stands or falls by it; one confirmed page makes an item present; quotations
        # are always read on the image (D8); silences need none
        if not a.stem and hs:
            L += ["", f"### {label} · to check on the page image (D4: every OCR page up to 40 per tier, else a blind "
                  f"sample of 40; born-digital pages need no check)", "",
                  "| tier | pages | born-digital (no check) | already confirmed | to check | pages to check (item p. PDF page) |",
                  "|---|---:|---:|---:|---:|---|"]
            for t in TIERS[:TIERS.index(stop_of[label]) + 1]:
                pgs = sorted({(h[1], h[3]) for h in hs if h[0] == t})
                if not pgs:
                    continue
                bd = [k for k in pgs if k in BD]
                done = [k for k in pgs if k in conf_of[label]]
                left = [k for k in pgs if k not in BD and k not in conf_of[label]]
                chk = left if len(left) <= 40 else sorted(random.Random(label + t).sample(left, 40))
                L.append(f"| {t} | {len(pgs)} | {len(bd)} | {len(done)} | {len(chk)}"
                         + ("" if chk is left else f" (sample of {len(left)})") + " | "
                         + "; ".join(f"{pl(i, q)}" for i, q in chk) + " |")
        # hits BY DEFAULT (a shared surname's bare or shared-initial hits), apart, with a vetting list: every page up
        # to 40, else a blind sample of 40 drawn by a fixed seed (the venture's sample size for visual checks)
        if TD.get(label):
            pg_d = {}
            for h in sorted(TD[label]):
                pg_d.setdefault((h[1], h[3]), h)
            keys = sorted(pg_d)
            vet = keys if len(keys) <= 40 else sorted(random.Random(label).sample(keys, 40))
            L += ["", f"### {label} · BY DEFAULT: {len(TD[label])} hits on {len(keys)} pages in "
                  f"{len({k[0] for k in keys})} items (bare or shared-initial hits of the surname, attributed by the "
                  f"judgement file's «default»; kept apart from the hits sorted by first name)", "",
                  f"To vet: {'every page' if vet is keys else 'a blind sample of 40 pages (fixed seed)'}; a page that is "
                  f"another person's goes to them with «assign» in the judgement file.", "",
                  "| item p. PDF page | tier | context |", "|---|---|---|"]
            L += [f"| {pl(k[0], k[1])} | {pg_d[k][0]} | {pg_d[k][7].replace('|', '/')} |" for k in vet]
        # what each silent item may claim, for this person, at their cutoff (presumed noise counts as silent)
        hit_items = {it for it in rows if read_item(label, it) not in ("silent", "presumed noise")}
        if MH.get(label):
            mh = sorted(set(MH[label]))
            L += ["", f"### {label} · hits on modern metadata, not counted ({len(mh)}; {meta_table})", ""] + [
                f"- {pl(it, p)} ({k}): «{r}»" for it, p, k, r in mh[:40]] + (
                [f"- … and {len(mh) - 40} more, in the hits table (column «metadata»)"] if len(mh) > 40 else [])
        by = birth_year(label)
        if by:
            IT_, _ = citation_tables()
            odd = []
            for it in sorted(hit_items):
                if read_item(label, it) not in STRONG: continue
                w = re.match(r"(\d{4})", IT_.get(it, {}).get("written", "") or "")
                if w and int(w.group(1)) < by:
                    odd.append((it, int(w.group(1))))
            if odd:
                L += ["", f"### {label} · implausible by date, to read (born {by} by the profile; present in items "
                          f"written earlier)", ""] + [f"- {it}: written {w}" for it, w in odd]
        under = sorted(it for it in rows if read_item(label, it) == "underspecified")
        tocon = sorted(it for it in rows if read_item(label, it) == "confirm")
        resid_items = sorted(it for it in rows if read_item(label, it) == "residue")
        groups = collections.defaultdict(list)
        for it in sorted(rows):
            if it in hit_items:
                continue
            line = signed.get(it)
            if not line:
                groups["not signed: the silence says nothing"].append(it)
            else:
                cv = silence_cover(line)
                key = f"signed {line[1][2].split(' · ')[0]}, silent " + ("over the WHOLE item" if cv["whole"] else "IN PART")
                groups[key].append(it if cv["whole"] and not (cv["hand"] or cv["kind"] or cv["kept"])
                                   else f"{it} — {cv['desc']} ({line[0]})")
        L += ["", f"### {label} · no hit: {len(rows) - len(hit_items)} items, by what their silence may claim", ""]
        if not a.stem:
            sil = lambda stop: sum(1 for it in rows if read_item(label, it, stop) in ("silent", "presumed noise"))
            L += [f"Read to **{stop_of[label]}**; an item whose only hits are small caps and run-ins, or join, counts as "
                  f"no hit unless a page is confirmed. At other cutoffs: silent with the exact tier only, "
                  f"{sil('exact')}; up to confusion, {sil('confusion')}; by the rule over every tier, {sil('join')}.", ""]
        for g in sorted(groups):
            L += [f"- **{g}: {len(groups[g])}**"] + [f"  - {x}" for x in groups[g]]
        if under:
            L += [f"- **underspecified, neither present nor silent until the form in the other alphabet is searched: "
                  f"{len(under)}**"] + [f"  - {x}" for x in under]
        if tocon:
            L += [f"- **confirm (translit only, both alphabets searched): neither present nor silent until judged — a "
                  f"confirmed page, a form set aside, or a cutoff above translit: {len(tocon)}**"] + [f"  - {x}" for x in tocon]
        if resid_items:
            L += [f"- **shared-surname residue: the surname is there, but not shown to be this person; neither present "
                  f"nor silent until resolved (judgement «assign») or arbitrated: {len(resid_items)}**"]
            L += [f"  - {x}" for x in resid_items]
        wl = []
        for w in COPIES:
            ws = [(it, rng, rank) for it, rng, rank in w["copies"] if it in rows]
            if not ws:
                continue
            said = []
            for it, rng, rank in ws:
                if rng is None:
                    rd = read_item(label, it)
                else:
                    sub = {tt: {p for p in ps if rng[0] <= p <= rng[1]} for tt, ps in PT[label].get(it, {}).items()}
                    rd = reading({tt: ps for tt, ps in sub.items() if ps}, any(c[0] == it for c in conf_of[label]),
                                 stop_of[label], bool(TS[(label, it)] - given[label]))
                said.append((it, rng, rank, rd))
            quiet = all(rd in ("silent", "presumed noise") for *_, rd in said)
            whole = w.get("whole_in") in {it for it, *_ in said}
            if not quiet:
                verdict = "PRESENT or unresolved in a copy: " + "; ".join(f"{it} ({rank}): {rd}" for it, _, rank, rd in said)
            elif whole:
                verdict = (f"silent in every copy searched, among them {w['whole_in']}, signed whole on its own: ABSENCE "
                           "FOR THE WHOLE WORK" + ("" if len(said) == len(w["copies"]) else " (not every copy was searched)"))
            elif len(said) < len(w["copies"]):
                verdict = "silent in the copies searched; not every copy was searched in this run"
            elif w["triangulated"]:
                verdict = f"silent in every copy: ABSENCE FOR THE WHOLE WORK (triangulated: {w['triangulated']})"
            else:
                verdict = ("silent in every copy; NOT YET TRIANGULATED: each silence counts only over its own "
                           "copy's pages (see the items above)")
            # COPY DISAGREEMENTS (2026-10-10; the editor at 17:0x, on translations as copies: versions can diverge in
            # small and noteworthy places, but that is expected to be the exception, not the rule): a person present in one copy
            # (a strong tier) and silent in another is where a divergence, or a copy's own added material, shows
            strong = [it for it, _, _, rd in said if rd in STRONG]
            silent = [it for it, _, _, rd in said if rd in ("silent", "presumed noise")]
            if strong and silent:
                verdict += (f"; COPIES DISAGREE, to read: present in {', '.join(strong)}, silent in {', '.join(silent)} "
                            "(a divergence, a copy's added material, an OCR loss, or a stretch edge)")
                DIS.append((label, w["work"], tuple(strong), tuple(silent)))
            unit = lambda it: "¶" if it in _BDSEC else "PDF pages"
            wl += [f"- **{w['work']}**: {verdict}"] + [
                f"  - {it} ({rank}{f', {unit(it)} {rng[0]}–{rng[1]}' if rng else ''}): {rd}" for it, rng, rank, rd in said] + (
                [f"  - {w['note']}"] if w.get("note") else [])
        if wl:
            L += ["", f"### {label} · works held in more than one copy (COPIES)", ""] + wl
        L.append("")
    hit_any = sorted({h[1] for v in T.values() for h in v})
    IT, PM = citation_tables()
    if IT or PM:
        pages_cited = sorted({(h[1], int(h[3])) for v in T.values() for h in v}, key=lambda k: (k[0], k[1]))
        L += ["## Citations of the pages (from the item table and the page map; «extrap.» and «counted» as ruled 2026-10-08)", "",
              "| item p. PDF page | citation |", "|---|---|"]
        L += [f"| {pl(it, p)} | {cite(it, p)} |" for it, p in pages_cited]
        L.append("")
    L += ["## The PDFs, to confirm hits on (pages are PDF pages, not printed ones)", ""]
    L += [f"- {it}: `{os.path.relpath(pdf[it], S) if it in pdf and pdf[it].startswith(S) else pdf.get(it, '?')}`" for it in hit_any]
    if DIS:   # every copy disagreement in one place, to be read (each is also in the person's COPIES section)
        L += ["", f"## Copy disagreements, to read ({len(DIS)})", "",
              "A person present in one copy of a work and silent in another: a divergence between versions, a copy's own "
              "added material, an OCR loss, or a stretch's edge page. Read each before a fact or a silence rests on it.", "",
              "| person | work | present in | silent in |", "|---|---|---|---|"] + [
              f"| {la} | {wk} | {', '.join(p)} | {', '.join(q)} |" for la, wk, p, q in DIS]
    open(a.write, "w", encoding="utf-8").write("\n".join(L) + "\n")
    n = sum(len(v) for v in T.values())
    print(f"{len(people)} people × {len(rows)} items · {n} hits ({secs} s) → {a.write}" + ("" if a.from_hits else f" + {hits_tsv}"))


if __name__ == "__main__":
    # THE DOWSE'S LOCK (2026-10-26; Miles's test chain rebuilt the search text under the redowse search of 2026-10-25s,
    # 23:38: the editor,): dowse-<pid>.lock for the run, refused while the chain holds
    # the corpus (tools/corpus_locks.py, its holder named); released however the run ends.
    with CL.held("dowse"):
        main()
