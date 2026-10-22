#!/usr/bin/env python3
r"""cupel-look-slices — RUNBOOK.md C2: a look's images cut into N even slices, one per reader.

    python3 tools/cupel-look-slices.py --batch <batch dir> --n <readers> [--suffix=-overlap] [--items <a,b,…|@file>]
                                          [--out <new dir>]

Folded into tools/ 2026-10-13 (on the editor's approval of folding in the recurring scratchpad scripts) from cupel10's
`cupel10-c2-slices.py` and `cupel10-c2-overlap-slices.py` (an internal record, 2026-10-13, not published).
Every <batch>/<stem><suffix>/look/*.png (KEY.tsv never listed), items in name order, images in number order, cut into
N slices as even as possible (sizes differ by at most 1). Without --suffix: the first builds' looks (the cut look);
with --suffix=-overlap (the «=» is needed: the value starts with «-»): the overlap builds' (the overlap look). --items: only those items (stems, without the suffix).
WRITES only the new folder --out (default <batch>/look-returns, or <batch>/look-returns<suffix>; refuses an existing
one): SLICE-kk.list (one absolute path a line) and SLICES.tsv (slice, image, stem). Prints each slice's size and its
first and last image (relative to the batch), and the total.
"""
import argparse, glob, os, sys


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batch", required=True); ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--suffix", default=""); ap.add_argument("--items"); ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or os.path.join(a.batch, "look-returns" + a.suffix)
    if os.path.exists(out):
        sys.exit(f"refusing: {out} exists")
    want = None
    if a.items:
        want = ({l.strip() for l in open(a.items[1:], encoding="utf-8") if l.strip()} if a.items.startswith("@")
                else {x.strip() for x in a.items.split(",") if x.strip()})
    imgs = []
    for d in sorted(glob.glob(os.path.join(a.batch, "*" + a.suffix, "look"))):
        stem = os.path.basename(os.path.dirname(d))
        base = stem[:-len(a.suffix)] if a.suffix and stem.endswith(a.suffix) else stem
        if a.suffix and not stem.endswith(a.suffix):
            continue
        if want is not None and base not in want:
            continue
        imgs += [(stem, p) for p in sorted(glob.glob(os.path.join(d, "*.png")))]
    if not imgs:
        sys.exit("no look images found")
    q, r = divmod(len(imgs), a.n)
    os.makedirs(out)
    rows, i = ["slice\timage\tstem"], 0
    for k in range(1, a.n + 1):
        part = imgs[i:i + q + (1 if k <= r else 0)]
        i += len(part)
        with open(os.path.join(out, f"SLICE-{k:02d}.list"), "x") as f:
            f.write("".join(p + "\n" for _, p in part))
        rows += [f"{k:02d}\t{p}\t{s}" for s, p in part]
        if part:
            print(k, len(part), os.path.relpath(part[0][1], a.batch), "…", os.path.relpath(part[-1][1], a.batch))
    with open(os.path.join(out, "SLICES.tsv"), "x") as f:
        f.write("\n".join(rows) + "\n")
    print("total", len(imgs), "items", len({s for s, _ in imgs}))


if __name__ == "__main__":
    main()
