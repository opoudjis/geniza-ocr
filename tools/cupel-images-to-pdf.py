#!/usr/bin/env python3
r"""cupel-images-to-pdf — cupel step C1: a placed scan's TIFFs → single pages (split at the gutter) → one lossless PDF.

    tools/cupel-images-to-pdf.py --stem <item> --out <new folder> [--look-all | --look N] <tiff> [<tiff> …]

WHY (the editor's decision D1, 2026-10-03 00:1x: option (b), which had been working fine; option (a) had been used only for
Kapis, as his requirement; see RUNBOOK.md). The scans are two-page spreads; the converter reads one PDF page per printed
page, so page references and the missing-leaf check match the book.

WHAT. The TIFFs are read in the order given, every frame in order (a multi-page TIFF is a batch of spreads). A frame wider
than 1.15 × its height is a spread: it is cut at the FOLD — among the columns with no print (under 1% dark pixels), the darkest (the binding
shadow), smoothed over 15 px — into a left and a right page. Two passes: each
spread's own guess in the middle 40% of the width; then, since the book barely moves on the glass, each spread searched
within 200 px of the item's median confident guess (a blank page would otherwise draw the cut; logged as MOVED). A narrower frame is one page. Nothing is deskewed or cropped. Writes, into --out (a NEW folder):
  <stem>.pdf               the pages in order, lossless (img2pdf; the scan's dpi kept)
  pages/page-NNNN.png      every page image, KEPT (the standing rule: never discard page images)
  SPLIT.tsv                frame · source · page(s) · fold x · width · the fold's ink share (print at the cut; ≥ 0.01 = no print-free column found)
  look/NN.png              with --look N: N spreads, the doubtful first, each with a red line at the cut (with --overlap:
                           two lines, the two pages' inner edges) — for a blind judge (checked BEFORE any OCR)
"""
import os, sys, argparse, subprocess
import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None


def gutter(g, near=None):
    # THE FOLD (blind look 1 on Manders, 2026-10-03, and the column profile of frame 7): left text ends ~1395, a white
    # inner margin 1400–1580 (varies least: version 1 cut there, 60–100 px short — 4 TOUCHES, 1 CUTS of 20), the binding
    # shadow 1600–1650 (darkest ~1630), the right page's text from ~1860. So: among the columns with NO PRINT (under 1%
    # dark pixels), the DARKEST — the binding shadow. If no column is free of print, the least-varying one.
    # near=None: the middle 40% of the width; near=x: within 200 px of x (the item's usual fold; a blank page or a
    # shadowless fold would otherwise draw the cut).
    a = np.asarray(g, dtype=np.float32)[::4]
    w = a.shape[1]
    lo, hi = (int(w * 0.3), int(w * 0.7)) if near is None else (max(0, near - 200), min(w, near + 200))
    b = a[:, lo:hi]; k = np.ones(15) / 15
    m = np.convolve(b.mean(axis=0), k, mode="same")[7:-7]
    ink = np.convolve((b < 128).mean(axis=0), k, mode="same")[7:-7]
    s = np.convolve(b.std(axis=0), k, mode="same")[7:-7]
    # GUTTER COLUMNS (look 4, Li kaj Ni, 2026-10-03: 14 / 5 / 1 — on flat scans with no shadow the darkest print-free column
    # lay against the letters' grey edges): little ink AND little variation top to bottom — a white margin, a shadow (std
    # 10–18, ink to 0.02 on Lingvo kaj Vivo) or a thin fold line all count; text (std 40+) does not.
    free = (ink < 0.03) & (s < 25)
    if not free.any():
        i = int(np.argmin(s)); return lo + 7 + i, float(ink[i])
    depth = float(np.median(m[free]) - m[free].min())
    if depth >= 15:                                   # a real binding shadow: its darkest point (Manders, Lingvo kaj Vivo)
        i = int(np.argmin(np.where(free, m, np.inf)))
    elif near is not None:                            # flat scan: the gutter column nearest the item's usual fold
        idx = np.where(free)[0]; i = int(idx[np.argmin(np.abs(idx + lo + 7 - near))])
    else:                                             # flat scan, first pass: the middle of the widest gutter run
        idx = np.where(free)[0]; runs = np.split(idx, np.where(np.diff(idx) > 1)[0] + 1)
        r = max(runs, key=len); i = int(r[len(r) // 2])
    return lo + 7 + i, float(ink[i])


def frames(path):
    im = Image.open(path); n = 0
    while True:
        try: im.seek(n)
        except EOFError: return
        yield n, im.copy(), im.info.get("dpi", (300, 300)); n += 1


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stem", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--look", type=int, default=0)
    ap.add_argument("--look-all", action="store_true", help="every spread to the look (the cupel rule since 2026-10-04)")
    # --overlap N (editor 2026-10-03 00:4x, for Li kaj Ni: its text curves into a narrow gutter near the head of the page,
    # so no straight cut clears it — two blind looks failed): each page keeps N px past the fold, so no letter is cut
    # off; the facing page's edge may leave a few stray letters (harmless for search).
    ap.add_argument("--overlap", type=int, default=0); ap.add_argument("tiffs", nargs="+")
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: write only into a NEW folder")
    os.makedirs(os.path.join(a.out, "pages")); log = ["frame\tsource\tpages\tgutter_x\twidth\tgutter_variation"]
    pages, spreads, dpi0, k = [], [], None, 0
    # FIRST PASS: each spread's own guess; the item's gutter = the median of the CONFIDENT guesses (variation < 0.1)
    first = {}
    for t in a.tiffs:
        for fi, im, dpi in frames(t):
            g = im.convert("L")
            if g.size[0] > 1.15 * g.size[1]: first[(t, fi)] = gutter(g)
    conf = [x for x, r in first.values() if r < 0.01] or [x for x, r in first.values()]
    med = int(np.median(conf)) if conf else None
    for t in a.tiffs:
        for fi, im, dpi in frames(t):
            k += 1; g = im.convert("L"); w, h = g.size; dpi0 = dpi0 or dpi
            if w > 1.15 * h:
                x, r = gutter(g, near=med); x1 = first[(t, fi)][0]
                o = a.overlap
                parts = [g.crop((0, 0, min(w, x + o), h)), g.crop((max(0, x - o), 0, w, h))]; spreads.append((k, g, x))
                if abs(x1 - x) > 150: r = f"{r:.3f} MOVED (first pass {x1})"
            else:
                x, r, parts = "", "", [g]
            p0 = len(pages) + 1
            for p in parts:
                f = os.path.join(a.out, "pages", f"page-{len(pages) + 1:04d}.png"); p.save(f, dpi=dpi); pages.append(f)
            log.append(f"{k}\t{os.path.basename(t)}#{fi}\t{p0}-{len(pages)}\t{x}\t{w}\t{r if isinstance(r, str) else f'{r:.3f}'}")
    open(os.path.join(a.out, "SPLIT.tsv"), "w").write("\n".join(log) + "\n")
    # the img2pdf COMMAND (Homebrew), lossless: PNG pages go in as they are, at the dpi stored in each PNG
    r = subprocess.run(["img2pdf", *pages, "-o", os.path.join(a.out, a.stem + ".pdf")], capture_output=True, text=True)
    if r.returncode: sys.exit("img2pdf failed: " + r.stderr[-400:])
    # --look-all (the editor ruled on 2026-10-04 01:3x against a blind look at cuts: too risky for content, unlike names; every
    # page must be looked at — not a blind sample of 40): EVERY spread goes to the look; the order is still shuffled
    if a.look_all:
        a.look = len(spreads)
    if a.look and spreads:
        # the look takes every DOUBTFUL spread first (MOVED, or print at the cut: ink share ≥ 0.01), then spreads evenly through the
        # item up to N; shuffled, so the judge cannot tell which were doubtful
        import random
        os.makedirs(os.path.join(a.out, "look")); n = min(a.look, len(spreads))
        doubt = [i for i, (k_, g, x) in enumerate(spreads) if "MOVED" in log[k_] or
                 (log[k_].split("\t")[5][:5].replace(".", "").isdigit() and float(log[k_].split("\t")[5].split()[0]) >= 0.01)]
        rest = [int(i) for i in np.linspace(0, len(spreads) - 1, n).round() if int(i) not in doubt]
        pick = (doubt + rest)[:n]; random.Random(7).shuffle(pick)
        for j, idx in enumerate(pick, 1):
            k_, g, x = spreads[idx]; c = g.convert("RGB"); d = ImageDraw.Draw(c)
            for xx in ([x] if not a.overlap else [x - a.overlap, x + a.overlap]):   # with --overlap: the two page edges
                d.line([(xx, 0), (xx, c.size[1])], fill=(255, 0, 0), width=6)
            w = 3 if n > 99 else 2   # 100+ spreads: three-digit names
            c.thumbnail((2400, 2400)); c.save(os.path.join(a.out, "look", f"{j:0{w}d}.png"))
            open(os.path.join(a.out, "look", "KEY.tsv"), "a").write(f"{j:0{w}d}\tframe {k_}\tgutter {x}\n")
    print(f"{k} frames · {len(spreads)} spreads split · {len(pages)} pages → {a.out}/{a.stem}.pdf")


if __name__ == "__main__":
    main()
