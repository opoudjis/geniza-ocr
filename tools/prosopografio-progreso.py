#!/usr/bin/env python3
r"""prosopografio-progreso — the progress figures of the Prosopografio page, filled from the project's files.

    python3 tools/prosopografio-progreso.py [--dry-run]

WHY (the editor, 2026-10-31 11:3x). The page's list of figures (date; cupel: words, primary and
secondary sources, sources recognised and to be recognised; dowse: sources read and to be read; smelt: biographies of
Esperantists and Idists written and to be written) is filled between the marks
«<!-- PROGRESO: … -->» and «<!-- /PROGRESO -->» of published/genizo/pages/prosopografio.md; the editor's sentence
before them is his. Run on request (Miles), then the page pushed on his word. Miles.

THE UNITS, as the read-sources page counts them (the editor 2026-10-31 12:0x, on): a «fonto» is a run or work
(one siglum), an «ero» one item of the corpus (an issue, a volume, a book).
THE FIGURES:
  cupel   words: everything signed, OCR and born-digital, as `tools/ocr-words-in.py` counts it (its own functions:
          the signed lines as the dowse reads them, each line's scope; the born-digital signed lists), in millions;
          primary / secondary: the signed items by kind (an OCR item PRIMARY if any of its lines is, else SECONDARY;
          a line naming no kind takes the item table's; born-digital items by the item table or the dates file);
          recognised: every signed item; to be recognised: the PRESENCE ONLY items of the CURRENT ledger (named in
          geniza/OCR-STATUS.md) and the files of the census rows marked «QUEUED» (geniza/ocr/method/CENSUS-LEFT-OUT.tsv,
          each glob expanded, files on the full PDF list left out). Each counted by runs, the items in brackets: an item's
          run is run_of() (its siglum, else its title, else its title key); a run is to be recognised (or, below, to be
          read) only when none of its items is.
  dowse   read: the sources and items of the read-sources page (published/genizo/pages/legitaj-fontoj.md, its line
          «**N fontoj, N eroj …**» and «Ankoraŭ ne listigitaj: N fontoj …», which `tools/dowse-done.py` writes), taken
          from the page so that the two agree; to be read: the signed items not in geniza/dowse/DOWSED-ITEMS-LATEST.tsv
          (read by either method). Mentions: the rows of geniza/profiles/build/FACTS-LIST.tsv (one a person a fact line, as
          `tools/harvest-facts.py` last wrote it); fact groups: `tools/fact-groups.py`'s own grouping of them (--match
          entity, every group, a fact told once a group of one; the lines without a kind are not grouped) (the editor
          2026-10-31 11:5x).
          About two minutes.
  smelt   written / to be written: the two headings of published/genizo/pages/biografatoj.md («La esperantistoj (N;
          biografio verkita: K)», «La idistoj (…)»), which `tools/smeltee-list.py` writes, less the rows marked «ne fandota»
          (Zamenhof; the editor 2026-10-31 11:3x).
Numbers as the read-sources page writes them, thousands by a space (1 042), millions with a decimal comma (78,4 milionoj).
WRITE-SET: published/genizo/pages/prosopografio.md, between its marks only (refused without them); --dry-run prints.
"""
import argparse, csv, datetime, glob, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
PAGE = os.path.join(ROOT, "published", "genizo", "pages", "prosopografio.md")
BIO = os.path.join(ROOT, "published", "genizo", "pages", "biografatoj.md")
MARK = re.compile(r"(<!-- PROGRESO:[^>]*-->\n)(.*?)(<!-- /PROGRESO -->)", re.S)


def _mod(name, file):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def n(x):
    return f"{x:,}".replace(",", " ")


_RUN = None
def run_of(item):
    """the run an item belongs to (the editor 2026-10-31 12:0x; to the definition, the runs, with the items
    in brackets): its siglum (profiles/SIGLA.tsv, by the item table's key, signed or not), else the item table's title, else
    its title key (`ocr-page-sequence.py`'s title_of(), which the item table groups by)"""
    global _RUN
    if _RUN is None:
        sys.path.insert(0, HERE); import sigla
        f = open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8"); f.readline()   # its «# GENERATED» line
        argv = sys.argv; sys.argv = [argv[0]]; ps = _mod("pageseq", "ocr-page-sequence.py"); sys.argv = argv
        _RUN = ({r["item"]: r for r in csv.DictReader(f, delimiter="\t")}, sigla.load(), ps.title_of)
    table, S, title_of = _RUN
    r = table.get(item, {})
    s = next((row["siglum"] for rx, row, _ in S if r.get("key") and rx.search(r["key"])), None)
    return ("siglum", s) if s else ("title", r["title"]) if r.get("title") else ("key", r.get("title_key") or title_of(item))


def cupel():
    W = _mod("ocr_words_in", "ocr-words-in.py")
    W._KIND = W.bd_kinds()
    signed = W.D.signed_lines()
    ocr, _ = W.signed_words(signed)
    kind_of = W.bd_kinds()
    bdrows = W.BDL.lists("signed")
    bd, _ = W.bd_words(bdrows, kind_of)
    words = sum(ocr.values()) + sum(bd.values())
    prim = sec = 0
    for item, (_, _, lines) in signed.items():
        conds = [" | ".join(x) for x in lines]
        k = ("PRIMARY" if any("; PRIMARY" in c for c in conds) else
             "SECONDARY" if any("SECONDARY LITERATURE" in c for c in conds) else W._KIND(item))
        prim += k == "PRIMARY"; sec += k == "SECONDARY"
    for it in bdrows:
        k = kind_of(it)
        prim += k == "PRIMARY"; sec += k == "SECONDARY"
    recognised = set(signed) | set(bdrows)
    status = open(os.path.join(G, "OCR-STATUS.md"), encoding="utf-8").read()
    cur = re.search(r"the ledger \(classes per item\) \| `(OCR-ABSENCE-LEDGER-[^`]+\.tsv)`", status)
    pres = [x[0] for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(G, "ocr", "runs", cur.group(1)), encoding="utf-8"))
            if len(x) > 3 and not x[0].startswith("#") and x[3] == "PRESENCE ONLY"]
    full = re.search(r"\| `(sources/OCR-PDF-LIST-[^`]+\.txt)` \(", status)
    listed = {os.path.realpath(os.path.join(ROOT, l.strip())) if not os.path.isabs(l.strip()) else os.path.realpath(l.strip())
              for l in open(os.path.join(G, full.group(1)), encoding="utf-8") if l.strip()}
    queued = set()
    for l in open(os.path.join(G, "ocr", "method", "CENSUS-LEFT-OUT.tsv"), encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if len(x) > 1 and not x[0].startswith("#") and x[1].startswith("QUEUED"):
            for f in glob.glob(os.path.join(ROOT, "published", "heterophony-resources", x[0])):
                if os.path.isfile(f) and os.path.realpath(f) not in listed:
                    queued.add(os.path.realpath(f))
    runs = {run_of(i) for i in recognised}
    left = set(pres) | {os.path.splitext(os.path.basename(f))[0] for f in queued}
    return {"words": words, "prim": prim, "sec": sec, "recognised": recognised, "pres": len(pres), "queued": len(queued),
            "ledger": cur.group(1), "runs": len(runs), "left_runs": len({run_of(i) for i in left} - runs)}


def dowse(recognised):
    p = os.path.join(G, "dowse", "DOWSED-ITEMS-LATEST.tsv")
    done = {x[0] for x in (l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8"))
            if x and x[0] and not x[0].startswith("#") and x[0] != "item"}
    t = open(os.path.join(ROOT, "published", "genizo", "pages", "legitaj-fontoj.md"), encoding="utf-8").read()
    m = re.search(r"\*\*([\d ]+) fontoj, ([\d ]+) eroj \(", t)
    if not m:
        raise SystemExit("legitaj-fontoj.md: no line «**N fontoj, N eroj (…»")
    old = re.search(r"Ankoraŭ ne listigitaj: (\d+) fontoj", t)
    # THE PAGE BY STAGE (Ezri, 2026-11-11: one table a stage; its first line is now the sinter table's alone). The sources
    # read but not yet folded in are the dowse table's line «**N fontoj, N eroj.**», counted beside them (Miles, 2026-11-11;
    # the editor)
    dw = re.search(r"## Etapo dowse[^\n]*\n+\*\*([\d ]+) fontoj, ([\d ]+) eroj\.", t)
    num = lambda s: int(s.replace(" ", ""))
    toread = recognised - done
    torun = {run_of(i) for i in toread} - {run_of(i) for i in done}   # a run none of whose items is read yet
    return (num(m.group(1)), num(m.group(2)), int(old.group(1)) if old else 0, len(toread), len(torun),
            (num(dw.group(1)), num(dw.group(2))) if dw else None)


def mentions():
    F = _mod("fact_groups", "fact-groups.py")
    rows, n = [], 0
    for r in csv.DictReader(open(F.LIST, encoding="utf-8"), delimiter="\t"):
        n += 1
        if r.get("kind"): rows.append((r["person"], r["file"], r["year"], r["kind"], r["line"]))
    groups, _ = F.groups_entity(rows, rows)
    # the groups of one mention apart (the editor 2026-10-31 12:2x: the groups of one source and those of
    # more than one mention counted apart)
    return n, len(groups), sum(1 for g in groups if len(g[3]) == 1)


def smelt():
    t = open(BIO, encoding="utf-8").read()
    out = {}
    for who in ("esperantistoj", "idistoj"):
        m = re.search(rf"^## La {who} \(([\d,]+); biografio verkita: ([\d,]+)\)", t, re.M)
        if not m:
            raise SystemExit(f"biografatoj.md: no heading «## La {who} (N; biografio verkita: K)»")
        tot, done = (int(g.replace(",", "")) for g in m.groups())
        # a row marked «ne fandota» (Zamenhof) is not a biography to write (the editor 2026-10-31 11:3x)
        start = m.end()
        end = t.find("\n## ", start)
        skip = len(re.findall(r"^\|[^\n]*\| ne fandota \|\s*$", t[start:end if end > 0 else len(t)], re.M))
        out[who] = (done, tot - done - skip)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    page = open(PAGE, encoding="utf-8").read()
    m = MARK.search(page)
    if not m:
        raise SystemExit(f"{PAGE}: no «<!-- PROGRESO: … -->» … «<!-- /PROGRESO -->» marks")
    c = cupel()
    runs, read, older, toread, torun, dw = dowse(c["recognised"])
    men, fg, fg1 = mentions()
    s = smelt()
    mil = f"{c['words'] / 1e6:.1f}".replace(".", ",")
    block = (f"* Dato: {datetime.date.today().isoformat()}\n"
             f"* cupel:\n"
             f"  * {mil} milionoj da vortoj rekonitaj, {n(c['prim'])} primaraj eroj (numeroj, volumoj, libroj), {n(c['sec'])} sekundaraj\n"
             f"  * {n(c['runs'])} fontoj rekonitaj ({n(len(c['recognised']))} eroj), {n(c['left_runs'])} fontoj rekonotaj "
             f"({n(c['pres'] + c['queued'])} eroj)\n"
             f"* dowse:\n"
             + (f"  * {n(runs)} fontoj legitaj kaj kunfanditaj ({n(read)} eroj), {n(dw[0])} legitaj, ankoraŭ ne kunfanditaj "
                f"({n(dw[1])} eroj), {n(torun)} fontoj legotaj ({n(toread)} eroj)" if dw else
                f"  * {n(runs)} fontoj legitaj ({n(read)} eroj), {n(torun)} fontoj legotaj ({n(toread)} eroj)")
             + (f"; krome {n(older)} fontoj legitaj per la pli frua metodo aŭ relegotaj" if older else "") + "\n"
             f"  * {n(men)} mencioj eltiritaj, grupigitaj en {n(fg)} faktogrupoj: {n(fg1)} en unu fonto, "
             f"{n(fg - fg1)} de pli ol unu mencio\n"
             f"* smelt:\n"
             f"  * {n(s['esperantistoj'][0])} biografioj de esperantistoj kompilitaj, {n(s['esperantistoj'][1])} kompilotaj\n"
             f"  * {n(s['idistoj'][0])} biografioj de idistoj kompilitaj, {n(s['idistoj'][1])} kompilotaj\n")
    print(block)
    print(f"(words {c['words']:,}; to be recognised: PRESENCE ONLY {c['pres']} on {c['ledger']}, QUEUED census files {c['queued']})",
          file=sys.stderr)
    if not a.dry_run:
        open(PAGE, "w", encoding="utf-8").write(page[:m.start(2)] + block + page[m.end(2):])
        print(f"→ {PAGE}", file=sys.stderr)


if __name__ == "__main__":
    main()
