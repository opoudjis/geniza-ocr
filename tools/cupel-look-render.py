#!/usr/bin/env python3
r"""cupel-look-render — the page images a look shows, with their key.

    python3 tools/cupel-look-render.py ranges --pdfs <PDF list> --out <new dir> <name>:<stem>:<first>-<last>:<dpi> …
    python3 tools/cupel-look-render.py orus --root <$R> --pdfs <PDF list> --out <new dir> --n <N> --seed <S> <stem> …

Folded into tools/ 2026-10-13 (on the editor's approval of folding the recurring scratchpad scripts) from cupel10's
`cupel10-gap-look.py` (ranges) and `cupel10-orus-look.py` (orus).

ranges   RUNBOOK.md C6.4.1, the neighbour look (A.5) and any look at named PDF pages: for each spec, every PDF page in
         first–last is rendered from the item's PDF on the list (pdftoppm, grey, at the spec's dpi) to
         <out>/<name>-pNNNN.png; <out>/KEY.tsv (image, name, item, PDF page, dpi).
orus     RUNBOOK.md C6.2, the orus look (A.9): for each item, the pages the old-letter rule sends to `orus`
         (tools/ocr_russian_reading.py russian_reading_path); a sample of N in all, shared out by each item's count
         (rounding settled on the largest pool), random with --seed; each rendered at 150 dpi grey to <out>/NN.png,
         numbered in a shuffled order (blind: no item name in an image's name); <out>/KEY.tsv (image, item, PDF page,
         the reading chosen), for the checker only, never shown to a reader.
WRITES only the new folder --out (refuses an existing one). pdftoppm is called with an argument list (no shell).
"""
import argparse, glob, os, random, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pdfs_of(lst):
    return {os.path.basename(l.strip())[:-4]: l.strip() for l in open(lst, encoding="utf-8") if l.strip()}


def render(pdf, p, dpi, base):
    r = subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-singlefile", "-f", str(p), "-l", str(p), pdf, base],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(base + ".png"):
        sys.exit(f"render failed: {pdf} p.{p}: {r.stderr[-200:]}")


def ranges(a):
    pdf = pdfs_of(a.pdfs)
    os.makedirs(a.out)
    key = ["image\tname\titem\tpdf_page\tdpi"]
    for spec in a.specs:
        name, stem, rng, dpi = spec.split(":")
        lo, hi = (int(x) for x in rng.split("-"))
        for p in range(lo, hi + 1):
            img = f"{name}-p{p:04d}"
            render(pdf[stem], p, dpi, os.path.join(a.out, img))
            key.append(f"{img}.png\t{name}\t{stem}\t{p}\t{dpi}")
        print(spec, hi - lo + 1)
    with open(os.path.join(a.out, "KEY.tsv"), "x", encoding="utf-8") as f:
        f.write("\n".join(key) + "\n")
    print(len(key) - 1, "images →", a.out)


def orus(a):
    sys.path.insert(0, HERE)
    import ocr_russian_reading as RR
    pdf = pdfs_of(a.pdfs)
    pool = {}
    for s in a.items:
        fs = sorted(glob.glob(os.path.join(a.root, s, "page-*.rus.txt")))
        pool[s] = [int(re.search(r"page-(\d+)\.rus\.txt$", f).group(1)) for f in fs
                   if os.path.exists(f.replace(".rus.txt", ".orus.txt")) and (RR.russian_reading_path(f) or "").endswith(".orus.txt")]
    tot = sum(len(v) for v in pool.values())
    if not tot:
        sys.exit("no orus pages in these items")
    rng = random.Random(a.seed)
    share = {s: round(a.n * len(v) / tot) for s, v in pool.items()}
    while sum(share.values()) != a.n:   # settle rounding on the largest pool
        big = max(pool, key=lambda s: len(pool[s]))
        share[big] += 1 if sum(share.values()) < a.n else -1
    picks = [(s, p) for s in a.items for p in sorted(rng.sample(pool[s], min(share[s], len(pool[s]))))]
    rng.shuffle(picks)
    os.makedirs(a.out)
    key = ["image\titem\tpdf_page\tchosen"]
    for i, (s, p) in enumerate(picks, 1):
        render(pdf[s], p, 150, os.path.join(a.out, f"{i:02d}"))
        key.append(f"{i:02d}.png\t{s}\t{p}\torus")
    with open(os.path.join(a.out, "KEY.tsv"), "x", encoding="utf-8") as f:
        f.write("\n".join(key) + "\n")
    print("pool", {s: len(v) for s, v in pool.items()}, "· sample", {s: share[s] for s in a.items}, "·", len(picks),
          "images →", a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("ranges"); r.add_argument("--pdfs", required=True); r.add_argument("--out", required=True)
    r.add_argument("specs", nargs="+", help="<name>:<stem>:<first>-<last>:<dpi>")
    o = sub.add_parser("orus"); o.add_argument("--root", required=True); o.add_argument("--pdfs", required=True)
    o.add_argument("--out", required=True); o.add_argument("--n", type=int, required=True)
    o.add_argument("--seed", type=int, required=True); o.add_argument("items", nargs="+")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    ranges(a) if a.mode == "ranges" else orus(a)


if __name__ == "__main__":
    main()
