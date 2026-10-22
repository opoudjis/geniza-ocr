#!/usr/bin/env python3
r"""ocr-page-sequence-reconcile — the page numbers the OCR followed and the page numbers the readers saw, as ONE
sequence per item: every jump inside an issue, and every break between consecutive issues, as a lead.

    tools/ocr-page-sequence-reconcile.py --items <batch>/ITEMS.txt --returns '<batch>/ends-look/RETURN-*.md' \
        [--exclude 'RETURN-reader06.md,RETURN-reader13.md'] > <batch>/ends-look/RECONCILE.md

WHY (2026-10-16, cupel12). `ocr-page-sequence.py` followed the OCR's numbers and sent the stretches it could not
follow to the ends look; the readers there read the printed numbers, but nothing compared them with the OCR's. So a
lost leaf in `ANNO_e4a_19090157` (printed 211 on PDF 31, 214 on PDF 32) went unseen, and the tool's projected ranges
(«printed 3–10» for an issue running 1–8) reached the editor as if read. The editor asked why the check had not
picked up the missing leaf, observed that it was not finding page numbers in the right place, and required that
the work then in hand ensure this does not recur. `RUNBOOK.md`'s C6.4.1 runs this after the ends look, before anything goes to the editor.

HOW. Per item: the numbers the OCR's followed run read (`ocr-page-sequence.py`'s own analysis, pages where the number
was read on the run) and the readers' Arabic printed numbers (a reader's number wins over the OCR's on the same page;
a disagreement is listed). Sorted by PDF page, each point's offset (printed − PDF page):
  JUMP UP    the offset rises between two points: printed pages missing between them (a lost leaf) — or a misread;
  STEP DOWN  the offset falls: more PDF pages than printed ones (a plate, an insert, a repeat) — or a misread;
  STRAY      one point off its two agreeing neighbours: a misread, set aside (listed).
Between issues of one run (the same name up to the date), in name order: the last number read in one and the first
in the next; a BREAK when the next starts more than 3 above the last (an unnumbered first text page and an
unnumbered last page explain up to 2), and not at a volume's restart (first number ≤ 3); a MISSING-FILE where the
ANNO file numbers skip. Every lead names its PDF pages and the numbers ACTUALLY READ; nothing here is projected.
"""
import argparse, glob, importlib.util, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("ps", os.path.join(HERE, "ocr-page-sequence.py"))
ps = importlib.util.module_from_spec(_s); _s.loader.exec_module(ps)


ROMAN = re.compile(r"^\s*\(?[IVXLC]+\b")


def reader_numbers(paths):
    """{item: {PDF page: Arabic printed number}}, and {item: {PDF pages the reader saw with a ROMAN number}}."""
    out = defaultdict(dict); roman = defaultdict(set)
    for f in paths:
        for l in open(f, encoding="utf-8", errors="ignore"):
            c = [x.strip() for x in l.strip().strip("|").split("|")]
            if len(c) < 3:
                continue
            m = re.search(r"([A-Za-z][\w.-]+)\s*/\s*(?:PDF\s*)?p\.?\s*0*(\d{1,4})\b", c[0])
            n = re.match(r"^\s*(\d{1,4})\b", c[1])
            if m and n:
                out[m.group(1)][int(m.group(2))] = int(n.group(1))
            elif m and ROMAN.match(c[1]):
                roman[m.group(1)].add(int(m.group(2)))
    return out, roman


def issue_index(code):
    """ANNO's file number → the issue's place in the run: e4a 0101…0199 = n-ri 1…99, 1100… = 100…; e1t 0051…0062 = the
    months (the run restarts each year)."""
    n = int(code)
    return n - 1000 if n >= 1000 else n % 100


def ocr_points(c):
    pg = ps.item_pages(c)
    nums = {k: ps.numbers_of(v) for k, v in pg.items()}
    r = ps.analyse(nums)
    return {s: s + o for s, o in (r.get("_seq") or [])}, len(pg)


def series_key(c):
    m = re.match(r"(.*?)(?:_?(18|19|20)\d\d)", c)
    return m.group(1) if m else c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--items", required=True)
    ap.add_argument("--returns", required=True, help="glob of the ends-look return files")
    ap.add_argument("--exclude", default="", help="comma-separated return file names to leave out (superseded)")
    a = ap.parse_args()
    ex = {x.strip() for x in a.exclude.split(",") if x.strip()}
    rets = [f for f in sorted(glob.glob(a.returns)) if os.path.basename(f) not in ex]
    rd, roman = reader_numbers(rets)
    items = [l.strip() for l in open(a.items) if l.strip()]
    print("# Page-number reconcile: OCR's followed numbers and the readers' numbers\n")
    print("By `tools/ocr-page-sequence-reconcile.py`; returns: %s.\n" % ", ".join(os.path.basename(f) for f in rets))
    leads = []; ends = {}; disagree = []
    for c in items:
        oc, npages = ocr_points(c)
        pts = dict(oc); src = {s: "O" for s in oc}
        for s, n in rd.get(c, {}).items():
            if s in pts and pts[s] != n:
                disagree.append((c, s, pts[s], n))
            pts[s] = n; src[s] = "R" if s not in oc or oc[s] != n else "R+O"
        if not pts:
            ends[c] = None; continue
        seq = sorted(pts.items())
        offs = [n - s for s, n in seq]
        stray = set()
        for i in range(1, len(seq) - 1):
            if offs[i - 1] == offs[i + 1] != offs[i]:
                stray.add(i)
        clean = [(s, n, o) for i, ((s, n), o) in enumerate(zip(seq, offs)) if i not in stray]
        for (s1, n1, o1), (s2, n2, o2) in zip(clean, clean[1:]):
            # strength: both numbers read by a reader (R) = strong; a number only the OCR read (O) = weak
            st = "strong" if "R" in src[s1] and "R" in src[s2] else "weak (OCR number)"
            if o2 > o1:
                leads.append((c, "JUMP UP", st, "PDF %d = %d [%s] → PDF %d = %d [%s]: printed %d–%d not in the scan" % (
                    s1, n1, src[s1], s2, n2, src[s2], n1 + 1 + (s2 - s1 - 1), n2 - 1) if n2 - n1 - (s2 - s1) > 1 else
                    "PDF %d = %d [%s] → PDF %d = %d [%s]: printed %d not in the scan" % (s1, n1, src[s1], s2, n2, src[s2], n2 - 1)))
            elif o2 < o1:
                leads.append((c, "STEP DOWN", st, "PDF %d = %d [%s] → PDF %d = %d [%s]: %d PDF page(s) more than printed (plate, insert, repeat?)" % (
                    s1, n1, src[s1], s2, n2, src[s2], o1 - o2)))
        for i in sorted(stray):
            leads.append((c, "STRAY", "", "PDF %d read %d, its neighbours agree on another numbering: set aside" % seq[i]))
        ends[c] = (clean[0][:2], clean[-1][:2], npages) if clean else None
    # between issues
    by = defaultdict(list)
    for c in items:
        by[series_key(c)].append(c)
    for k, cs in by.items():
        cs.sort()
        for x, y in zip(cs, cs[1:]):
            mx = re.search(r"(\d{4})(\d{4})$", x); my = re.search(r"(\d{4})(\d{4})$", y)
            if mx and my:
                ix, iy = issue_index(mx.group(2)), issue_index(my.group(2))
                if (mx.group(1) == my.group(1) or iy > ix) and iy - ix > 1:
                    leads.append((y, "MISSING-FILE", "", "no file between %s and %s (%d issue(s))" % (x, y, iy - ix - 1)))
            if not ends.get(x) or not ends.get(y):
                continue
            (sx, nx) = ends[x][1]; (sy, ny) = ends[y][0]
            if ny <= 3:
                continue
            # the pages after the last number read in x and before the first in y can hold printed pages, except those
            # a reader saw with a ROMAN number (wrappers)
            room = sum(1 for s in range(sx + 1, ends[x][2] + 1) if s not in roman.get(x, ())) + \
                   sum(1 for s in range(1, sy) if s not in roman.get(y, ()))
            miss = ny - nx - 1 - room
            if miss > 0:
                leads.append((y, "BREAK", "", "%s: last number read %d on PDF %d of %d; %s: first number read %d on PDF %d; %d unread non-wrapper page(s) between: %d printed page(s) unaccounted for" % (
                    x, nx, sx, ends[x][2], y, ny, sy, room, miss)))
    print("## Leads (%d)\n" % len(leads))
    order = {"JUMP UP": 0, "BREAK": 1, "MISSING-FILE": 2, "STEP DOWN": 3, "STRAY": 4}
    leads.sort(key=lambda r: (order[r[1]], r[2] != "strong", r[0]))
    print("[R] read by a reader on the ends look; [O] read only in the OCR; [R+O] both.\n")
    print("| item | kind | strength | evidence (PDF pages and the numbers read on them) |\n|---|---|---|---|")
    for c, kind, st, ev in leads:
        print("| %s | %s | %s | %s |" % (c, kind, st, ev))
    print("\n## OCR and reader disagree on a page (%d; the reader's number used)\n" % len(disagree))
    for c, s, o, n in disagree:
        print("- %s PDF %d: OCR %d, reader %d" % (c, s, o, n))
    print("\n## Items with no number read by either (%d)\n" % sum(1 for v in ends.values() if v is None))
    print(", ".join(c for c, v in ends.items() if v is None) or "none")


if __name__ == "__main__":
    main()
