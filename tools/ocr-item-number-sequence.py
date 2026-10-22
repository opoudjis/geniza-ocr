#!/usr/bin/env python3
r"""ocr-item-number-sequence — missing leaves in a run that numbers its ITEMS, not its pages, by the numbers our readings hold.

    python3 tools/ocr-item-number-sequence.py --items <ITEMS.txt> --prefix <stem prefix> --out <report.md> [--tsv <issues.tsv>]

WHY (2026-10-17, cupel15). Schleyer's *Volapükabled* numbers every item of the paper, one running count across the whole
run («1816.», «1817.» … «1830.» in 1890 file 52; «4707» in 1903), and prints no page numbers that the page-sequence
check (`tools/ocr-page-sequence.py`) can follow: 261 of its 313 files came out CANT-TELL. At 21:2x the editor, choosing
between an ends look of every issue and this check, chose to try this check.

HOW. For each issue of the run (the stems with --prefix, in name order: ANNO's file numbers follow the year's order) and
each page (`page-NNNN.txt`, `.psm4.txt`, `.tl.txt` where present), every number of 2–4 digits that opens a line or
follows «§», with a full stop after it, or one of 3–5 digits in brackets (the form from 1897: «(3778)»), is a
candidate; a candidate equal to the issue's year (± 2) is dropped (datelines
such as «1890.»). The run's item numbers are then the longest strictly increasing chain through the candidates, in page
order (patience sorting): OCR noise and stray numbers fall out of it, the running count stays. The report gives, per
issue, its pages, the first and last item number it holds and the count found; and the LEADS:
  - BREAK: between consecutive issues, the next issue's first number more than GAP above the last one's last
    (an issue or a leaf missing between them);
  - JUMP: inside an issue, between consecutive pages, a rise of more than GAP (a leaf missing inside it);
  - SILENT: a page with no number on the chain (a plate, an advertisement page, a blank, or a page read badly).
GAP is the larger of 25 and three times the run's median rise per page. A lead is a lead, not a loss: each goes to a
look before anything is ruled. WRITES only --out (and --tsv).
"""
import os, re, sys, glob, bisect, argparse, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
CAND = re.compile(r"(?:^|§)\W{0,3}(\d{2,4})\.(?=\s|$)|\((\d{3,5})\)", re.M)   # «1817.» to 1896; «(3778)» from 1897


def pages_of(stem):
    d = os.path.join(R, stem)
    out = {}
    for f in glob.glob(os.path.join(d, "page-*.txt")):
        m = re.search(r"page-(\d+)\.(txt|psm4\.txt|tl\.txt)$", f)
        if m:
            out.setdefault(int(m.group(1)), []).append(f)
    return dict(sorted(out.items()))


def year_of(stem):
    m = re.search(r"_(1[89]\d\d)\d{4}", stem)
    return int(m.group(1)) if m else None


def lis(seq):
    """longest strictly increasing subsequence of (value, tag) by value; returns the chosen tags"""
    tails, tidx, prev = [], [], [None] * len(seq)
    for i, (v, _) in enumerate(seq):
        k = bisect.bisect_left(tails, v)
        if k == len(tails):
            tails.append(v); tidx.append(i)
        else:
            tails[k] = v; tidx[k] = i
        prev[i] = tidx[k - 1] if k else None
    out, i = [], tidx[-1] if tidx else None
    while i is not None:
        out.append(i); i = prev[i]
    return [seq[j] for j in reversed(out)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--items", required=True); ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--tsv")
    a = ap.parse_args()
    for p in (a.out, a.tsv):
        if p and os.path.exists(p):
            sys.exit(f"exists: {p}")
    stems = sorted(l.strip() for l in open(a.items, encoding="utf-8") if l.strip().startswith(a.prefix))
    seq = []                                   # (number, (stem, page))
    pages = {}
    for s in stems:
        y = year_of(s); pages[s] = list(pages_of(s))
        for p, fs in pages_of(s).items():
            nums = set()
            for f in fs:
                for m in CAND.finditer(open(f, encoding="utf-8", errors="ignore").read()):
                    n = int(m.group(1) or m.group(2))
                    if y and abs(n - y) <= 2:
                        continue
                    nums.add(n)
            # within a page the order is not trusted (columns): the page's numbers enter the chain in rising order
            seq += [(n, (s, p)) for n in sorted(nums)]
    chain = lis(seq)
    on = {}
    for n, (s, p) in chain:
        on.setdefault((s, p), []).append(n)
    rises = []
    prev = None
    for s in stems:
        for p in pages[s]:
            ns = on.get((s, p))
            if ns:
                if prev is not None:
                    rises.append(ns[0] - prev)
                prev = ns[-1]
    med = statistics.median(rises) if rises else 0
    GAP = max(25, 3 * med)
    rows, leads, last = [], [], None
    for s in stems:
        nums = [n for p in pages[s] for n in on.get((s, p), [])]
        first, lst = (nums[0], nums[-1]) if nums else (None, None)
        silent = [p for p in pages[s] if not on.get((s, p))]
        rows.append((s, len(pages[s]), first, lst, len(nums), ",".join(map(str, silent))))
        if first is not None and last is not None and first - last[1] > GAP:
            leads.append(f"- **BREAK** between `{last[0]}` (last item {last[1]}) and `{s}` (first item {first}): {first - last[1] - 1} numbers missing")
        pv = None
        for p in pages[s]:
            ns = on.get((s, p))
            if ns:
                if pv is not None and ns[0] - pv[1] > GAP:
                    leads.append(f"- **JUMP** in `{s}` between PDF page {pv[0]} (item {pv[1]}) and PDF page {p} (item {ns[0]}): {ns[0] - pv[1] - 1} numbers missing")
                pv = (p, ns[-1])
        if silent:
            leads.append(f"- SILENT in `{s}`: PDF page(s) {', '.join(map(str, silent))} carry no number on the chain")
        if nums:
            last = (s, lst)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"# Item-number sequence: `{a.prefix}*`, {len(stems)} issues\n\nBy `tools/ocr-item-number-sequence.py` from the readings in `sources/ocr-rendersearch/`. "
                f"{len(chain):,} numbers on the chain; median rise per page {med}; GAP {GAP}. Leads are for a look, not rulings.\n\n## Leads\n\n")
        f.write("\n".join(l for l in leads if not l.startswith("- SILENT")) or "none")
        f.write("\n\n## Silent pages\n\n" + ("\n".join(l for l in leads if l.startswith("- SILENT")) or "none") + "\n\n## Issues\n\n| issue | PDF pages | first item | last item | numbers found | silent pages |\n|---|---|---|---|---|---|\n")
        f.writelines(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |\n" for r in rows)
    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as f:
            f.write("issue\tpdf_pages\tfirst_item\tlast_item\tnumbers\tsilent_pages\n")
            f.writelines("\t".join(map(str, r)) + "\n" for r in rows)
    b = sum(l.startswith("- **BREAK") for l in leads); j = sum(l.startswith("- **JUMP") for l in leads)
    print(f"{len(stems)} issues · {len(chain):,} numbers on the chain · median rise {med} · GAP {GAP} · BREAK {b} · JUMP {j} · "
          f"issues with silent pages {sum(1 for r in rows if r[5])} → {a.out}")


if __name__ == "__main__":
    main()
