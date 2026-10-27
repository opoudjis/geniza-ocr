#!/usr/bin/env python3
r"""anno-pieces — the ÖNB/ANNO download pieces of one volume: renamed, then joined per volume.

    tools/anno-pieces.py rename <folder>                  # «X (n).pdf» → «X_part<n+1>.pdf»; writes <folder>/RENAMES-<date>.tsv
    tools/anno-pieces.py join <folder> --out <dir>        # X.pdf + X_part2.pdf … → <dir>/X.pdf (qpdf), one per volume

WHY (cupel17 C0, 2026-10-20, the editor; cupel18b C0, 2026-10-24 20:5x, approved): ANNO
serves a long volume in 50-page parts, and a browser saves them as «X.pdf», «X (1).pdf», «X (2).pdf» …: «X (n).pdf» is
the (n+1)th part, the unsuffixed X.pdf part 1. Names with spaces break the shell steps, and the volume is one item.
CHECKS: rename refuses a target that exists; join refuses an output that exists, a gap in the part numbers, and a
part other than the last that is not 50 pages (the order would then be in doubt).
WRITE-SET: rename: the renamed files (mv in place) and <folder>/RENAMES-<date>.tsv (create-only); join: <dir>/X.pdf
for each volume with parts (create-only). Nothing is deleted.
"""
import argparse, datetime, os, re, subprocess, sys

QPDF = "/opt/homebrew/bin/qpdf"
PDFINFO = "/opt/homebrew/bin/pdfinfo"
BROWSER = re.compile(r"^(?P<x>.+) \((?P<n>\d+)\)\.pdf$")
PART = re.compile(r"^(?P<x>.+)_part(?P<n>\d+)\.pdf$")


def pages(f):
    out = subprocess.run([PDFINFO, f], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def rename(folder):
    todo = []
    for f in sorted(os.listdir(folder)):
        m = BROWSER.match(f)
        if m:
            todo.append((f, f"{m['x']}_part{int(m['n']) + 1}.pdf"))
    if not todo: sys.exit("no «X (n).pdf» pieces in " + folder)
    bad = [new for _, new in todo if os.path.exists(os.path.join(folder, new))]
    if bad: sys.exit(f"refusing: targets exist: {bad[:3]}")
    log = os.path.join(folder, f"RENAMES-{datetime.date.today()}.tsv")
    if os.path.exists(log): sys.exit(f"refusing: {log} exists")
    with open(log, "w", encoding="utf-8") as w:
        w.write("# the browser-copy names of the ÖNB/ANNO downloads, renamed by tools/anno-pieces.py: «X (n).pdf» = the "
                "(n+1)th 50-page part of X → «X_part<n+1>.pdf»; the unsuffixed X.pdf is part 1\nold\tnew\n")
        for old, new in todo:
            os.rename(os.path.join(folder, old), os.path.join(folder, new))
            w.write(f"{old}\t{new}\n")
    print(f"{len(todo)} pieces renamed → {log}")


def join(folder, out):
    vols = {}
    for f in os.listdir(folder):
        m = PART.match(f)
        if m: vols.setdefault(m["x"], []).append(int(m["n"]))
    if not vols: sys.exit("no «X_part<n>.pdf» pieces in " + folder)
    os.makedirs(out, exist_ok=True)
    for x in sorted(vols):
        ns = sorted(vols[x])
        if ns != list(range(2, ns[-1] + 1)): sys.exit(f"refusing: {x}: parts {ns}, a gap")
        files = [os.path.join(folder, x + ".pdf")] + [os.path.join(folder, f"{x}_part{n}.pdf") for n in ns]
        if not os.path.exists(files[0]): sys.exit(f"refusing: {x}.pdf (part 1) missing")
        pp = [pages(f) for f in files]
        if any(p != 50 for p in pp[:-1]): sys.exit(f"refusing: {x}: parts' pages {pp}; all but the last should be 50")
        dst = os.path.join(out, x + ".pdf")
        if os.path.exists(dst): sys.exit(f"refusing: {dst} exists")
        subprocess.run([QPDF, "--empty", "--pages", *files, "--", dst], check=True)
        got = pages(dst)
        if got != sum(pp): sys.exit(f"{dst}: {got} pages, the parts {sum(pp)}")
        print(f"{x}: {len(files)} parts, {got} pp → {dst}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rename", "join"]); ap.add_argument("folder"); ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "rename": rename(a.folder)
    else:
        if not a.out: sys.exit("join needs --out")
        join(a.folder, a.out)
