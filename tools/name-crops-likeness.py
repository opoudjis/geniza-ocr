#!/usr/bin/env python3
"""name-crops-likeness — a snippet run's vision returns against Tesseract's words, by sheet (2026-11-03).

    python3 tools/name-crops-likeness.py <run dir> [--low N]

WHY (run sheet C7b.2a: the check before `ocr-name-crops.py file`; cupel20a and cupel20b's were measured by hand, cupel19c's
not at first; the editor, 2026-11-03 10:5x to keeping it as a tool). A sheet whose
readings share almost nothing with Tesseract's words may have been read against the wrong ids; a low snippet is a lead,
most often a page where Tesseract read noise and the reader read sense.
WHAT. For each id of <run dir>/returns/*.txt (sNNNNN⇥text), its KEY.tsv row (id, sheet, item, page, box, tesseract):
difflib's ratio of the two texts in lower case; «NOT SEEN» left out. Prints each sheet's count, mean and median, the
whole run's mean and its count under 0.30, then the N lowest snippets (default 12) with both texts. On cupel20b's run
it gives 0.51, 0.45, 0.41 by sheet (the hand measure of 2026-11-02: 0.50, 0.46, 0.41); cupel19c's 0.82 in all.
WRITE-SET: none; it prints only.
"""
import argparse, collections, difflib, glob, os, statistics

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--low", type=int, default=12)
a = ap.parse_args()
key = {}
for l in open(os.path.join(a.dir, "KEY.tsv"), encoding="utf-8"):
    x = l.rstrip("\n").split("\t")
    if x[0] != "id" and len(x) >= 6:
        key[x[0]] = (x[1], x[2], x[3], x[5])
by, low = collections.defaultdict(list), []
for f in sorted(glob.glob(os.path.join(a.dir, "returns", "*.txt"))):
    for l in open(f, encoding="utf-8"):
        x = l.rstrip("\n").split("\t", 1)
        if len(x) < 2 or x[0] not in key or x[1].strip() == "NOT SEEN":
            continue
        sheet, item, page, tess = key[x[0]]
        r = difflib.SequenceMatcher(None, tess.lower(), x[1].lower()).ratio()
        by[sheet].append(r)
        low.append((r, x[0], item, page, tess, x[1]))
for s in sorted(by):
    print(f"{s}: {len(by[s])} snippets, mean likeness {statistics.mean(by[s]):.2f}, median {statistics.median(by[s]):.2f}")
allr = [r for v in by.values() for r in v]
if allr:
    print(f"all: {len(allr)}, mean {statistics.mean(allr):.2f}; under 0.30: {sum(r < 0.3 for r in allr)}")
for r, i, item, page, tess, v in sorted(low)[:a.low]:
    print(f"{r:.2f}\t{i}\t{item} PDF {page}\tTESS «{tess[:60]}»\tVISION «{v[:60]}»")
