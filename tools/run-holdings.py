#!/usr/bin/env python3
r"""run-holdings — every periodical run in the corpus, by its files' names: the years and issue numbers we hold, the
years missing inside the run's span, and the numbers that skip. A census of LEADS for the lacunae register, not of
lacunae: a lead is settled on the mastheads (double numbers, a run that ceased, a year never published).

    python3 tools/run-holdings.py --list <full PDF list> [--min-files 3] > geniza/ocr/runs/RUN-HOLDINGS-<date>.md
    python3 tools/run-holdings.py --list <full PDF list> --mastheads > geniza/ocr/runs/RUN-HOLDINGS-<date>-mastheads.md
        (--mastheads: for each lead, the files either side of the gap and what their first pages' OCR says of number,
        volume and date: the evidence to settle the lead on, text only)

WHY (2026-10-16). The lacunae register (`geniza/ocr/method/LACUNAE.tsv`) was seeded only from the page-sequence
checks, which compare the files we hold; a whole year missing has no neighbours to compare. The editor

HOW. A file's name gives its run, year and number by the corpus's naming schemes: `ANNO_<code>_<YYYY><NNNN>` (the run
is the folder, e.g. `EsperoKatolika-onb`; the number from ANNO's file number: e4a-style 0101…0199, 1100… = n-ri 1…;
e1t-style 0051…0062 = the months), `<Run>_<YYYY>[_v<V>]_n<NN>…` (Lublin, BitArkivo), `<name>.<YYYY>.<N>[…]`
(`LEsperantiste.1899.7`, `larevuo.1906.17`), and `<name>…<YYYY>…` (a year only). Runs are grouped by the name before
the year (case and punctuation folded). A range in the name (`.8-9`, `_n11-12`) counts as all its numbers. A run of fewer than --min-files files is skipped (books, singletons). For
each run: the span (first and last year), the years held with their numbers, the years MISSING inside the span, and,
within a year, the numbers that skip (1 … the highest held), or, where the numbers run on across years, the skips in
the running sequence. Only the name is read: no masthead, so a double number (13–14) shows as a skip, and a run named
two ways is two runs.
"""
import argparse, os, re, collections

PATS = [
    ("anno", re.compile(r"^ANNO_(?P<code>[a-z0-9]+)_(?P<y>1[89]\d\d)(?P<n>\d{4})(?:\.\d+)?$")),
    ("run_n", re.compile(r"^(?P<run>.+?)[_.-](?P<y>1[89]\d\d)(?:[_.-]v\d+)?[_.-]n0*(?P<n>\d{1,4})(?:[-–](?:n)?0*(?P<n2>\d{1,4}))?(?:\D.*)?$", re.I)),
    ("dot", re.compile(r"^(?P<run>.+?)\.(?P<y>1[89]\d\d)\.0*(?P<n>\d{1,3})(?:[-–]0*(?P<n2>\d{1,3}))?(?:\D.*)?$")),
    ("year", re.compile(r"^(?P<run>.*?\D)(?P<y>1[89]\d\d)(?:\D.*)?$")),
]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse(path):
    stem = os.path.basename(path)[:-4] if path.endswith(".pdf") else os.path.basename(path)
    folder = os.path.basename(os.path.dirname(path))
    for kind, rx in PATS:
        m = rx.match(stem)
        if not m:
            continue
        y = int(m.group("y"))
        if kind == "anno":
            n = int(m.group("n"))
            idx = n - 1000 if n >= 1000 else n % 100
            return (folder if folder.endswith("-onb") else "ANNO_" + m.group("code")), y, idx, stem
        run = m.group("run").rstrip("_.- ")
        n = int(m.group("n")) if "n" in m.groupdict() and m.group("n") else None
        n2 = int(m.group("n2")) if "n2" in m.groupdict() and m.group("n2") else None
        if n is not None and n2 is not None and n < n2 <= n + 12:
            return run, y, list(range(n, n2 + 1)), stem          # a double (or larger) number: 8-9
        return run, y, n, stem
    return None


STEMPATH = {}
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza", "sources")
MAST = re.compile(r"(?i)\b(?:N[-.ºo°r]*\.? ?\d{1,3}(?: ?[-–/] ?\d{1,3})?|No\.? ?\d{1,3}(?: ?[-–/] ?\d{1,3})?|"
                  r"(?:Jaro|Jarkolekto|Ann[ée]e|Jahrgang|Jaargang|Vol(?:ume|\.)?|Rocz(?:nik)?|Ročník|Anno|Año|Aŭ) ?[IVXLC\d]+[a-z.]*|"
                  r"(?:Januaro|Februaro|Marto|Aprilo|Majo|Junio|Julio|Aŭgusto|Septembro|Oktobro|Novembro|Decembro|"
                  r"janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|"
                  r"January|February|March|April|May|June|July|August|September|October|November|December|"
                  r"Januar|Februar|März|Juli|Oktober|Dezember|Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|"
                  r"Settembre|Ottobre|Dicembre|Enero|Febrero|Abril|Mayo|Junio|Julio|Septiembre|Octubre|Noviembre|Diciembre)"
                  r"[ ,.]{0,3}(?:1[89]\d\d)?)\b")


def masthead(stem):
    """what the first pages' OCR says of number, volume, date (preferred reading first)"""
    txt = ""
    pf = os.path.join(R, "ocr-preferred", stem + ".txt")
    if os.path.exists(pf):
        parts = re.split(r"\n=== page \d+ ===\n", "\n" + open(pf, encoding="utf-8", errors="ignore").read())
        txt = " ".join(parts[1:4])
    else:
        for i in (1, 2, 3):
            f = os.path.join(R, "ocr-rendersearch", stem, "page-%04d.txt" % i)
            if os.path.exists(f):
                txt += " " + open(f, encoding="utf-8", errors="ignore").read()
    hits = []
    for m in MAST.finditer(re.sub(r"\s+", " ", txt[:6000])):
        s = m.group(0).strip()
        if s and s not in hits:
            hits.append(s)
    return "; ".join(hits[:8]) or "(no OCR, or nothing read)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True)
    ap.add_argument("--min-files", type=int, default=3)
    ap.add_argument("--mastheads", action="store_true", help="for each lead, the neighbours' masthead strings")
    a = ap.parse_args()
    runs = collections.defaultdict(lambda: {"names": collections.Counter(), "items": []})
    paths = [l.strip() for l in open(a.list, encoding="utf-8") if l.strip()]
    # an ANNO file outside its run's -onb folder (a joined issue, cupel-batch-NN/joined/) goes to that run
    code_folder = {}
    for p in paths:
        m = PATS[0][1].match(os.path.basename(p)[:-4])
        f = os.path.basename(os.path.dirname(p))
        if m and f.endswith("-onb"):
            code_folder[m.group("code")] = f
    for p in paths:
        r = parse(p)
        m = PATS[0][1].match(os.path.basename(p)[:-4])
        if r and m and r[0].startswith("ANNO_") and m.group("code") in code_folder:
            r = (code_folder[m.group("code")],) + r[1:]
        if not r:
            continue
        run, y, n, stem = r
        k = norm(run)
        runs[k]["names"][run] += 1
        runs[k]["items"].append((y, n, stem))
        STEMPATH[stem] = p
    rows = []
    for k, v in runs.items():
        its = v["items"]
        if len(its) < a.min_files:
            continue
        name = v["names"].most_common(1)[0][0]
        years = sorted({y for y, _, _ in its})
        span = (years[0], years[-1])
        missing_years = [y for y in range(span[0], span[1] + 1) if y not in years]
        by = collections.defaultdict(set)
        for y, n, _ in its:
            if isinstance(n, list):
                by[y].update(n)
            elif n is not None:
                by[y].add(n)
        allnums = sorted(n for s in by.values() for n in s)
        running = len(by) > 1 and len(allnums) > 3 and min(min(s) for s in by.values() if s) > 0 and \
            all(min(by[y2]) > max(by[y1]) for y1, y2 in zip(sorted(by), sorted(by)[1:]) if by[y1] and by[y2])
        skips = []
        if running:
            s = sorted(set(allnums))
            skips = ["%d–%d" % (x + 1, z - 1) if z - x > 2 else str(x + 1) for x, z in zip(s, s[1:]) if z - x > 1]
        else:
            for y in sorted(by):
                s = sorted(by[y])
                gap = [n for n in range(1, s[-1] + 1) if n not in s] if s[-1] <= 31 else []
                if gap:
                    skips.append("%d: %s" % (y, ",".join(map(str, gap))))
        held = "; ".join("%d (%s)" % (y, ",".join(map(str, sorted(by[y]))) if by[y] else
                                       "%d ×%d" % (y, sum(1 for yy, _, _ in its if yy == y))) for y in years)
        rows.append((name, len(its), span, missing_years, skips, running, held))
    rows.sort(key=lambda r: (-(len(r[3]) + len(r[4])), r[0].lower()))
    if a.mastheads:
        print("# Run holdings: the mastheads either side of each lead\n")
        print("By `tools/run-holdings.py --mastheads`: for each run with a lead, every file in name order with what its "
              "first pages' OCR says of number, volume and date (the preferred reading where there is one). Settle "
              "each lead on these; an OCR string can be misread.\n")
        for name, n, span, my, sk, running, held in rows:
            if not my and not sk:
                continue
            k = norm(name)
            print("## %s (%d files, %d–%d): missing years %s; skips %s\n" % (name, n, span[0], span[1],
                  ", ".join(map(str, my)) or "—", "; ".join(sk) or "—"))
            for y, num, stem in sorted(runs[k]["items"], key=lambda x: (x[0], x[1] if isinstance(x[1], int) else (x[1][0] if x[1] else 0), x[2])):
                print("- %s | %s | %s" % (stem, y, masthead(stem)))
            print()
        return
    print("# Run holdings by file name — leads for the lacunae register\n")
    print("By `tools/run-holdings.py --list %s` (min files %d). Names only: settle each lead on the mastheads "
          "(double numbers, a run that ceased or paused, a year never published) before it becomes a LACUNAE row.\n"
          % (os.path.basename(a.list), a.min_files))
    print("| run (as named) | files | span | years MISSING in the span | numbers that skip | numbering | held |")
    print("|---|---|---|---|---|---|---|")
    for name, n, span, my, sk, running, held in rows:
        print("| %s | %d | %d–%d | %s | %s | %s | %s |" % (
            name, n, span[0], span[1], ", ".join(map(str, my)) or "—", "; ".join(sk) or "—",
            "running" if running else "by year", held))


if __name__ == "__main__":
    main()
