"""born_digital_lines.py: the born-digital lists, read the same way by ocr-dowse.py, ocr-item-table.py and ocr-item-dates.py.

WHY (2026-10-10; the editor ruled on 2026-10-09, 12:2x, that the dowse has a larger scope than cupel and includes
born-digital material, all those texts being in the dowse's scope; agreed in an internal record, 2026-10-09, not published): texts
with no OCR, no ledger and no gate (the Tekstaro, archive.org text layers, web saves), searched as given, listed in
geniza/ocr/lines/BORN-DIGITAL-LINES-<date>-{PROPOSED,SIGNED}-<label>.txt (written by tools/born-digital-convert.py) and normalised
once into geniza/sources/born-digital-text/<item>.txt: one paragraph per block, blank lines between, headings as
«=== section N: <title> ===». Those texts are fixed once signed; the locator «¶ N» counts their non-blank blocks,
headings included, from 1.

Read-only: nothing here writes a file.
"""
import glob, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
LINES = os.path.join(G, "ocr", "lines")   # the BORN-DIGITAL-LINES and OCR-ACCEPTANCE-LINES files (from 2026-10-10)
SECTION = re.compile(r"^=== section (\d+): (.*) ===$")
# A typed PDF (a publisher's or author's text layer, not OCR) is PAGED (the editor's decision of 2026-10-10 21:56 to
# include option C too): its text carries «=== page N ===» at each PDF page break, and its list row says «pdf» in the «pages» column
# (otherwise «none»). The dowse then searches and cites it like an OCR text, by PDF page.
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)


def is_paged(row):
    return (row.get("pages") or "").strip().lower() == "pdf"


def page_numbers(text):
    return sorted({int(x) for x in PAGE.findall(text)})


def lists(which="signed"):
    """item → the list row (item, path, pages, scope, label, class) plus «file», the list it comes from. «signed»:
    SIGNED lists only (what the dowse searches by default); «proposed»: PROPOSED and SIGNED, a signed row winning;
    «all»: the same as «proposed». Within a status, a later file (by sorted name) wins per item."""
    pats = ["BORN-DIGITAL-LINES-*-SIGNED-*.txt"] if which == "signed" else \
           ["BORN-DIGITAL-LINES-*-PROPOSED-*.txt", "BORN-DIGITAL-LINES-*-SIGNED-*.txt"]
    out = {}
    for pat in pats:
        # the lists live in geniza/ocr/lines/ (moved there 2026-10-10 on the editor's word); the top level is still read
        # during the move. Ordered by file name, whichever folder, so «a later file wins» means the same as before.
        for f in sorted(glob.glob(os.path.join(LINES, pat)) + glob.glob(os.path.join(G, pat)), key=os.path.basename):
            head = None
            for l in open(f, encoding="utf-8"):
                if l.startswith("#") or not l.strip():
                    continue
                x = l.rstrip("\n").split("\t")
                if head is None:
                    head = x; continue
                r = dict(zip(head, x)); r["file"] = os.path.basename(f)
                out[r["item"]] = r
    return out


def text_path(row):
    """the text's path: the list's «path», relative to geniza (or to geniza/sources), else the default place."""
    p = row.get("path", "")
    cands = ([os.path.join(G, p), os.path.join(G, "sources", p)] if p else []) + \
            [os.path.join(G, "sources", "born-digital-text", row["item"] + ".txt")]
    return next((c for c in cands if os.path.isfile(c)), cands[-1])


def is_bd_text(path):
    return os.sep + "born-digital-text" + os.sep in path


def blocks(text):
    """[(¶ number, section number, block text)]: every non-blank block, headings included."""
    out, sec, n = [], 0, 0
    for b in re.split(r"\n\s*\n", text):
        b = b.strip()
        if not b:
            continue
        m = SECTION.match(b.splitlines()[0])
        if m:
            sec = int(m.group(1))
        n += 1
        out.append((n, sec, b))
    return out


def paged(text):
    """the text with each block as a «page» («=== page N ===», N = its ¶ number), for the OCR search's page splitter."""
    return "".join(f"=== page {n} ===\n{b}\n" for n, _, b in blocks(text))


def sections_of(text):
    """¶ number → section number."""
    return {n: s for n, s, _ in blocks(text)}


YEAR = re.compile(r"(1[5-9]\d\d|20[0-2]\d)")


def header_years(path, lines=60):
    """(written, published, the lines read) from a Tekstaro header: «Proksimuma verkojaro: 1898» (a range gives its first
    year) and «Eldonado: … 1968 …»; None where absent."""
    head = open(path, encoding="utf-8").read().splitlines()[:lines]
    w = p = None; ev = []
    for l in head:
        if w is None and l.startswith("Proksimuma verkojaro:"):
            m = YEAR.search(l); w = int(m.group(1)) if m else None; ev.append(l.strip())
        elif p is None and l.startswith("Eldonado:"):
            m = YEAR.search(l); p = int(m.group(1)) if m else None; ev.append(l.strip())
    return w, p, ev
