#!/usr/bin/env python3
r"""ocr-g1-sort-build — batches for the G1 IMAGE SORT: the pages the ink test flagged or could not decide.

    tools/ocr-g1-sort-build.py --g1 <G1 report .md.json> --pdfs <list> --out <scratch-dir> --tag <date>

The G1 ink test (`tools/ocr-g1-ink.py`) can only say «ink with line structure and too little text» or
nothing at all: on dark scans, photographs and white-on-dark covers it finds no paper and gives no
verdict («untested»). Both kinds go to a person or a vision checker, blind, as on 2026-09-26
(an internal record, 2026-09-26, not published): each page's IMAGE beside its FINAL text, sorted NOTHING / MINOR /
LOST. Pages already carrying a verdict in an earlier sort (`OCR-G1-SORT-KEY-*.tsv`) are not re-sent.

WRITES <out>/bNN/NNN.png + NNN.txt (batches of 20), <out>/KEY.tsv (NNN, batch, corpus, page, reason).
The key is copied to `geniza/ocr/runs/OCR-G1-SORT-KEY-<tag>.tsv` once the sort is filed.
"""
import os, re, sys, glob, json, argparse, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
GENIZA = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
ROOT = os.path.join(GENIZA, "sources", "ocr-rendersearch")


def done_before():
    seen = set()
    for k in glob.glob(os.path.join(GENIZA, "ocr", "runs", "OCR-G1-SORT-KEY-*.tsv")):
        for l in open(k, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) >= 4:
                seen.add((f[2], int(f[3])))
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--g1", required=True); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--list", default=None, help="TSV corpus<TAB>page: extra pages (e.g. re-read LOST pages), reason «reread»")
    ap.add_argument("--force", action="store_true", help="send --list pages even if an earlier sort has a verdict (a re-read may have fixed them)")
    ap.add_argument("--gate", default=None, help="gate json: every page of a TOO-SHORT-TO-SCORE item is added (the editor's ruling, 2026-09-27: an image check)")
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    seen = done_before(); todo = []
    for r in (json.load(open(a.g1)) if a.g1 != "-" else []):
        for p in r.get("untested_pages", []):
            if (r["corpus"], p) not in seen: todo.append((r["corpus"], p, "undecided"))
        for p in r.get("pages", []):
            if (r["corpus"], p) not in seen: todo.append((r["corpus"], p, "flagged"))
    if a.list:
        for l in open(a.list, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) >= 2 and (a.force or (f[0], int(f[1])) not in seen):
                todo.append((f[0], int(f[1]), "reread"))
    if a.g1 == "-":
        pass
    if a.gate:
        for r in json.load(open(a.gate)):
            if r["g4"] == -2.0:
                d = os.path.join(ROOT, r["corpus"])
                for f in glob.glob(os.path.join(d, "page-*.txt")):
                    m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
                    if m and (r["corpus"], int(m.group(1))) not in seen:
                        todo.append((r["corpus"], int(m.group(1)), "too-short"))
    first = {}
    for c, p, why in todo:
        first.setdefault((c, p), why)   # a page listed twice keeps its first reason
    todo = sorted((c, p, w) for (c, p), w in first.items())
    os.makedirs(a.out, exist_ok=True); key = []
    cache = {}
    for i, (c, p, why) in enumerate(sorted(todo), 1):
        b = f"b{(i - 1) // 20 + 1:02d}"; n = f"{i:03d}"; bd = os.path.join(a.out, b); os.makedirs(bd, exist_ok=True)
        subprocess.run(["pdftoppm", "-r", "110", "-png", "-singlefile", "-f", str(p), "-l", str(p), pdfs[c],
                        os.path.join(bd, n)], capture_output=True)
        if c not in cache:
            t = open(os.path.join(ROOT, c + ".txt"), encoding="utf-8", errors="ignore").read() if os.path.exists(os.path.join(ROOT, c + ".txt")) else ""
            parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t); cache = {c: dict(zip(map(int, parts[1::2]), parts[2::2]))}
        open(os.path.join(bd, n + ".txt"), "w", encoding="utf-8").write(cache[c].get(p, ""))
        key.append((n, b, c, p, why))
    with open(os.path.join(a.out, "KEY.tsv"), "w", encoding="utf-8") as f:
        for k in key: f.write("\t".join(map(str, k)) + "\n")
    kinds = {w: sum(1 for k in key if k[4] == w) for w in ("undecided", "flagged", "too-short", "reread")}
    print(f"{len(key)} pages in {len({k[1] for k in key})} batches {kinds}; already sorted and skipped: {len(seen)}")


if __name__ == "__main__":
    main()
