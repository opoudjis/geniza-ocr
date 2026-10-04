"""ocr_text_languages — ask THE LANGUAGE TABLE which languages and scripts a text prints (import, not run).

    import ocr_text_languages as TL
    TL.nonlatin(item)        # licensed non-Latin languages, e.g. {"russian"}, {"greek"}, set() — or None if not in the table
    TL.cyrillic(item)        # licensed Cyrillic languages (russian, ukrainian, bulgarian, belarusian), or None
    TL.label(item)           # «Greek», «Russian/Ukrainian», … for the ledger's bi-script note

WHY (the editor's ruling, 2026-10-03): a table mapping texts to the languages they contain should have acted as a
filter. The 28 Sep Cyrillic chain read 220 items with the Russian model by script detection alone; Greek, Ido,
Estonian Fraktur and Latin headings came out as «Russian» in the companion, the gate's bi-script scoring and the
ledger's label. From 3 Oct every pass that reads or labels a non-Latin script asks this module first.
LICENSED = listed in the table without «-cited» and without «?». A cited language (a few names or titles) never
licenses a model run, a search file or a bi-script label. NOT IN THE TABLE (a new item before the table is rebuilt):
None — the caller decides; the Russian reader refuses such items (rebuild the table first, RUNBOOK.md).
The table: the newest `geniza/OCR-TEXT-LANGUAGES-YYYY-MM-DD[x].tsv`, or the path in env OCR_LANG_TABLE.
"""
import os, re, glob, csv

HERE = os.path.dirname(os.path.abspath(__file__))
GENIZA = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
NAME = re.compile(r"OCR-TEXT-LANGUAGES-\d{4}-\d{2}-\d{2}[a-z]?\.tsv$")
CYRILLIC = {"russian", "ukrainian", "bulgarian", "belarusian", "serbian-or-macedonian"}
NONLATIN = CYRILLIC | {"greek", "greek-polytonic", "georgian", "armenian", "hebrew", "japanese",
                       "arabic-script", "chinese-script", "korean", "other-script"}   # 2026-10-04: by negotiation (C6.5)
_T = {}


def path():
    p = os.environ.get("OCR_LANG_TABLE")
    if p:
        return p
    c = sorted(f for f in glob.glob(os.path.join(GENIZA, "OCR-TEXT-LANGUAGES-*.tsv")) if NAME.search(f))
    if not c:
        raise SystemExit("no language table (geniza/OCR-TEXT-LANGUAGES-<date>.tsv): build it first "
                         "(tools/ocr-text-languages.py, then tools/ocr-text-languages-table.py)")
    return c[-1]


def _table():
    if "t" not in _T:
        _T["path"] = path()
        _T["t"] = {r["item"]: [x for x in r["languages"].split(",") if x]
                   for r in csv.DictReader((l for l in open(_T["path"], encoding="utf-8") if not l.startswith("#")),
                                           delimiter="\t")}
    return _T["t"]


def languages(item):
    """Every licensed language of the item (cited and doubtful ones left out), or None if not in the table."""
    t = _table()
    return None if item not in t else {x for x in t[item] if not x.endswith("-cited") and not x.endswith("?")}


def nonlatin(item):
    L = languages(item)
    return None if L is None else L & NONLATIN


def cyrillic(item):
    L = languages(item)
    return None if L is None else L & CYRILLIC


def label(item):
    n = nonlatin(item)
    return "/".join(sorted(x.capitalize() for x in n)) if n else ""
