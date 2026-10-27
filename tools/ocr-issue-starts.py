#!/usr/bin/env python3
r"""ocr-issue-starts — where each issue begins inside a volume the ÖNB delivered in 50-page parts.

    tools/ocr-issue-starts.py --out geniza/ocr/runs/OCR-ISSUE-STARTS.tsv

WHY (2026-10-08; the editor confirmed that issues span across those PDF bundles, then set the order 1, 3, and 2 only
on the editor's further word: this is 3). *Lingvo Internacia* and *La Revuo* are held as 50-page parts of each year's volume (tools/
ocr-item-table.py, DOTTED «part»), so a file names no issue. The page map gives each page's printed number in the
volume; this table gives the printed page on which each issue starts, so a citation can add the issue.

HOW. Per title, its own marker, read from the first three and last two lines of every page (a general «n° N» would
also catch the Esperanto word «ni»):
  Lingvo Internacia  the masthead «N-ro N» (seen on each issue's first page: 1905 issues start every 24 printed pages)
  La Revuo           the printer's signature «LA REVUO, n° N» at the foot of an issue's first page (read as «ni 2»,
                     «N' 3», «n? 24»)
The printed page comes from the page map (ocr/runs/OCR-PAGE-MAP.tsv). Per volume (title and year), the readings are
put in printed-page order and only the longest run in which the issue number rises with the page is kept (a misread
«30» for 10 falls out); then a start is kept only if its distance from the last kept start fits the volume's usual
issue length (a misread «19» for 12 falls out). Each kept issue's start = the first printed page it was read on.

WRITE-SET: --out only: a fixed name, replaced only when the current version is committed (tools/ocr_replace_guard.py),
after a difference report, losses first. Read-only otherwise.
"""
import os, re, sys, glob, argparse, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ocr_replace_guard as RG
_s = importlib.util.spec_from_file_location("pageseq", os.path.join(HERE, "ocr-page-sequence.py"))
PS = importlib.util.module_from_spec(_s); _argv = sys.argv; sys.argv = [_argv[0]]; _s.loader.exec_module(PS); sys.argv = _argv
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
PAGE_MAP = os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv")

TITLES = {   # item-name prefix → (title key, the marker's pattern; group 1 = the issue number)
    "Lingvo Internacia ": ("lingvo internacia", re.compile(r"N-?r[o0]\.?\s*(\d{1,3})\b")),
    "larevuo.": ("larevuo", re.compile(r"REVUO[,.]?\s*[nN]\S{0,2}\s*(\d{1,3})\b")),
}

# WHOLE VOLUMES (2026-10-27, Ezri, before the Progreso dowse: «could you add Progreso to … OCR-ISSUE-STARTS.tsv …, its
# own heading pattern? The texts are whole volumes, and without the map the facts can't be dated by their monthly issue»):
# a title held as one file per volume, its items named here with the year its volume (yaro) begins. Progreso numbers
# its issues straight through the volumes; from the second yaro each issue opens with «No 25. Marto 1910» above its
# «KONTENAJO» (read on the first four lines of the page). The first yaro's issues open with the masthead and a contents
# box only, no issue line: none is found there. Pages are ordered by PDF page (the page map gives no printed number on
# many pages of volumes 4–6); a start on a page the map gives no printed number is found but not written (the table's
# readers need the printed page).
MONTHS = r"(?:Marto|Aprilo|Mayo|Majo|Junio|Julio|Agosto|Augusto|Septembro|Oktobro|Novembro|Decembro|Januaro|Februaro)"
VOLUMES = {   # title key → (the items and their volumes' first years, the marker's pattern; group 1 = the issue number)
    "progreso": ({"progreso1": "1908", "Progreso_-_2a_yaro": "1909", "progreso3": "1910", "progreso4": "1911",
                  "progreso5": "1912", "progreso6": "1913", "progreso7": "1914"},
                 re.compile(r"N[o0°º]\.?\s*(\d{1,3})\s*[.,:;]*\s*(?:[—-]\s*)?" + MONTHS, re.I)),
}


def rising(seq):
    """the longest subsequence of (printed, issue) in printed order whose issue numbers strictly rise"""
    best = [[x] for x in seq]
    for i in range(len(seq)):
        for j in range(i):
            if seq[j][1] < seq[i][1] and seq[j][0] < seq[i][0] and len(best[j]) + 1 > len(best[i]):
                best[i] = best[j] + [seq[i]]
    return max(best, key=len) if best else []


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    why = RG.may_replace(a.out)
    if why: sys.exit(why)
    PM = {}
    for l in open(PAGE_MAP, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if len(x) > 3 and x[1].isdigit() and x[3] in ("read", "iss") and re.fullmatch(r"\d+", x[2] or ""):
            PM[(x[0], int(x[1]))] = int(x[2])
    rows, stats = [], collections.Counter()
    for pre, (key, pat) in TITLES.items():
        items = sorted({c for (c, _) in PM if c.startswith(pre)})
        byvol = collections.defaultdict(list)
        for c in items:
            m = re.match(re.escape(pre) + r"(\d{4})\.(\d+)$", c)
            if not m: continue                                   # «0», «0.1»: the volume's other matter
            pg = PS.item_pages(c)
            for p in sorted(pg):
                if (c, p) not in PM: continue
                lines = [l for l in re.split(r"[\n\x0c]", PS.VIEWER.sub("", pg[p])) if l.strip()]
                for l in lines[:3] + lines[-2:]:
                    for n in pat.findall(l):
                        byvol[m.group(1)].append((PM[(c, p)], int(n), c, p, l.strip()[:80]))
        for yr, seq in sorted(byvol.items()):
            seq.sort()
            first = {}
            for x in rising([(s[0], s[1]) for s in seq]):
                first.setdefault(x[1], x[0])
            # SPACING (2026-10-08: La Revuo 1906 «19» on printed 529, a misread 12): the volume's usual issue length, from
            # starts of consecutive numbers; a start is kept only if the pages since the last kept start fit the issues
            # claimed (within 30 % and 4 pages)
            ks = sorted(first.items())
            spans = sorted(pb - pa for (na, pa), (nb, pb) in zip(ks, ks[1:]) if nb - na == 1)
            if spans:
                med = spans[len(spans) // 2]; kept = [ks[0]]
                for n, pr in ks[1:]:
                    n0, p0 = kept[-1]
                    if abs((pr - p0) - (n - n0) * med) <= 0.3 * (n - n0) * med + 4: kept.append((n, pr))
                stats[key + " dropped by spacing"] += len(ks) - len(kept)
                first = dict(kept)
            for n, pr in sorted(first.items()):
                src = next(s for s in seq if s[0] == pr and s[1] == n)
                rows.append((key, yr, n, pr, src[2], src[3], src[4])); stats[key] += 1
            stats[key + " readings dropped"] += len(seq) - len(first)
    for key, (vols, pat) in VOLUMES.items():
        for c, yr in vols.items():
            # every reading on disk of each page (`page-NNNN.txt`, `.psm4.txt`, …): the issue line, set in display type, often
            # survives in one reading only (2026-10-27: 16 of Progreso's issue lines were in the psm 4 reading alone)
            seq = []
            for f in sorted(glob.glob(os.path.join(G, "sources", "ocr-rendersearch", c, "page-*.txt"))):
                p = int(re.search(r"page-(\d+)\.", os.path.basename(f)).group(1))
                lines = [l for l in re.split(r"[\n\x0c]", PS.VIEWER.sub("", open(f, encoding="utf-8", errors="ignore").read())) if l.strip()]
                for l in lines[:4]:
                    for n in pat.findall(l):
                        seq.append((p, int(n), l.strip()[:80]))
            seq = sorted(set(seq))
            # the volume's own issues only: Progreso's yaro k holds Nos 12(k-1)+1 … 12k (one a month, March to February),
            # so a number quoted in the text («No 8 … 1904», «No 15») or misread cannot anchor the spacing test
            k = list(vols).index(c) + 1                          # the yaro: the items are listed in volume order
            seq = [s for s in seq if 12 * (k - 1) < s[1] <= 12 * k]
            seq.sort()
            first = {}
            for x in rising([(s[0], s[1]) for s in seq]):
                first.setdefault(x[1], x[0])
            ks = sorted(first.items())
            spans = sorted(pb - pa for (na, pa), (nb, pb) in zip(ks, ks[1:]) if nb - na == 1)
            if spans:
                med = spans[len(spans) // 2]; kept = [ks[0]]
                for n, p in ks[1:]:
                    n0, p0 = kept[-1]
                    if abs((p - p0) - (n - n0) * med) <= 0.3 * (n - n0) * med + 4: kept.append((n, p))
                stats[key + " dropped by spacing"] += len(ks) - len(kept)
                first = dict(kept)
            for n, p in sorted(first.items()):
                src = next(s for s in seq if s[0] == p and s[1] == n)
                # only a start with a printed page: the table's readers map printed pages to issues (tools/ocr-dowse.py,
                # citation_tables: an empty first_printed stopped it, 2026-10-27 13:4x)
                if (c, p) not in PM:
                    stats[key + " found without a printed page (not written)"] += 1; continue
                rows.append((key, yr, n, PM[(c, p)], c, p, src[2])); stats[key] += 1
            stats[key + " readings dropped"] += len(seq) - len(first)
    new = a.out + ".new"
    with open(new, "w", encoding="utf-8") as f:
        f.write("# GENERATED by tools/ocr-issue-starts.py from ocr/runs/OCR-PAGE-MAP.tsv and the readings. Do not hand-edit — "
                "re-run it. An issue starts on first_printed; it runs to the next issue's start.\n")
        f.write("title_key\tvolume_year\tissue\tfirst_printed\titem\tpdf_page\tread_as\n")
        for r in rows: f.write("\t".join(map(str, r)) + "\n")
    print("\n".join(RG.report(a.out, new, ("title_key", "volume_year", "issue"), ("first_printed", "item", "pdf_page"))))
    os.replace(new, a.out)
    print(f"{len(rows)} issue starts → {a.out}; " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))


if __name__ == "__main__":
    main()
