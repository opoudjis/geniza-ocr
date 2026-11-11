"""ocr_withdrawn — the pages taken out of the corpus's readings: a page scanned twice inside one file, its second copy.

    import ocr_withdrawn as WD;  WD.pages("ONB_e6e_19100120")  → {15, 16, …}

WHY (cupel19c, 2026-10-30; the editor 10:0x, on the pages scanned twice inside a file: take the duplicates out, and
build the means). Twelve *Kroata Esperantisto* files hold their issue twice, *Dana Esperantisto* 1911 no. 59 its
pp. 45–50 twice: their words counted twice. `tools/ocr-duplicate-pages.py withdraw` empties such a page's readings in
`sources/ocr-rendersearch/` (the originals kept in `sources/ocr-withdrawn-pages/`); an empty page then reads, to every
tool, as a blank leaf. Only the tools that take a page with ink and no text for a page we failed to read (the G1 ink
test, the gate's silent pages, the G1 sort, the G5 sample) need to know it was withdrawn: they call `pages()`.

The list is `geniza/ocr/method/DUPLICATE-PAGES.tsv`; a row counts when its status is «withdrawn».
A second list, `geniza/ocr/method/LIBRARY-PAGES.tsv` (2026-11-03; the editor, on a library's cover sheet: left out): the pages a library added to its scan
(ÖNB's cover sheet, Gallica's cover and terms pages, Google's notice, BSB's cover, the Internet Archive's notice leaf),
withdrawn the same way; the same columns, `same_as` empty, as there is no kept page. Both lists are read unless a
caller names one.

THE METADATA KEPT (2026-11-04; the editor, after six ÖNB items lost the year the dates tool read from the cover sheet,
«Jahr: 1890-1891»: the library's pages stay out of the data, but their metadata is retained and read): a tool that
takes a work's title, year or shelfmark from its first pages reads a withdrawn library page from the store with
`library_texts()`, never from the emptied page in the readings. Its callers: `ocr-item-dates.py` (the title-page
years) and `cupel-c0-checks.py` (the title check on pages 1–2, where an ÖNB cover sheet named *Ora libro*).
"""
import csv, os

_M = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published",
                                   "heterophony-resources", "geniza", "ocr", "method"))
STORE = os.path.normpath(os.path.join(_M, "..", "..", "sources", "ocr-withdrawn-pages"))
LIST = os.path.join(_M, "DUPLICATE-PAGES.tsv")
LIBRARY = os.path.join(_M, "LIBRARY-PAGES.tsv")
LISTS = (LIST, LIBRARY)
_TABLE = {}


def rows(path=LIST):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f, delimiter="\t") if (r.get("item") or "").strip()]


def table(path=None):
    """{item: {withdrawn PDF page: kept PDF page, or None for a library page}}, the rows whose status is «withdrawn»,
    of the list named, or of both lists when none is."""
    key = path or "*"
    if key not in _TABLE:
        t = {}
        for p in ((path,) if path else LISTS):
            for r in rows(p):
                if r.get("status", "").strip() == "withdrawn":
                    s = (r.get("same_as") or "").strip()
                    t.setdefault(r["item"].strip(), {})[int(r["page"])] = int(s) if s else None
        _TABLE[key] = t
    return _TABLE[key]


def pages(stem, path=None):
    return set(table(path).get(stem, {}))


def library_texts(stem):
    """{PDF page: its main reading as it stood before withdrawal} for the item's withdrawn LIBRARY pages (cover sheets
    and notices), read from the store (`sources/ocr-withdrawn-pages/<item>/page-NNNN.txt`); a page missing there is left
    out. Metadata only: never joined to the search or preferred text."""
    out = {}
    for p in sorted(pages(stem, LIBRARY)):
        f = os.path.join(STORE, stem, f"page-{p:04d}.txt")
        if os.path.exists(f):
            with open(f, encoding="utf-8", errors="ignore") as h:
                out[p] = h.read()
    return out
