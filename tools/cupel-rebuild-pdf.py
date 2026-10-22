#!/usr/bin/env python3
r"""cupel-rebuild-pdf — a build's PDF rebuilt with some frames replaced: re-cut, or left unsplit.

    python3 tools/cupel-rebuild-pdf.py --build <build dir> --out <new dir> --stem <stem>
           [--replace <frame>=<re-cut build dir> …] [--unsplit <frame>,<frame>… --scans <the item's placed-scan folder>]
           [--why "<the editor's ruling, quoted>"] [--build-label "overlap build"]

Folded into tools/ 2026-10-13 (approved by the editor, who agreed to folding the recurring scratchpad scripts) from two of
cupel10's scratch scripts, one for --replace (Ludovikito's frame 135, re-cut alone with --overlap 120, the editor's choice of option 2, re-split) and
one for --unsplit (the Ora Jarlibro's one-page sideways tables, frames 175–179, the editor's choice of option 1a).
Reads the build's SPLIT.tsv (frame, source, pages) and pages/. For each frame, in order: --replace, ALL of
<re-cut build>/pages/page-*.png in order; --unsplit, the frame's own source image (SPLIT.tsv's source, a file name in --scans: the item's own scan folder),
whole; otherwise the build's own pages for it. WRITES only the new folder --out (refuses an existing one): <stem>.pdf
(img2pdf, lossless, as tools/cupel-images-to-pdf.py writes it) and MAP.tsv (PDF page, frame, file, how: «re-cut
(<why>)», «unsplit (<why>)» or the build label). Prints each replaced frame and the page count.
"""
import argparse, glob, os, subprocess, sys


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", required=True); ap.add_argument("--out", required=True); ap.add_argument("--stem", required=True)
    ap.add_argument("--replace", nargs="*", default=[], help="<frame>=<re-cut build dir>")
    ap.add_argument("--unsplit", help="frames to put in whole, comma-separated"); ap.add_argument("--scans")
    ap.add_argument("--why", default="the editor's ruling"); ap.add_argument("--build-label", default="overlap build")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    repl = {int(k): v for k, v in (x.split("=") for x in a.replace)}
    uns = {int(x) for x in a.unsplit.split(",")} if a.unsplit else set()
    if uns and not a.scans:
        sys.exit("--unsplit needs --scans")
    if uns & set(repl):
        sys.exit(f"a frame both replaced and unsplit: {sorted(uns & set(repl))}")
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(a.build, "SPLIT.tsv"), encoding="utf-8")][1:]
    pages, mp = [], ["pdf_page\tframe\tfile\thow"]
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    os.makedirs(a.out)
    for r in rows:
        frame, src = int(r[0]), r[1].split("#")[0]
        fidx = int(r[1].split("#")[1]) if "#" in r[1] else 0     # the frame WITHIN a multi-page TIFF (SPLIT.tsv «file.tif#5»)
        lo, hi = (int(x) for x in r[2].split("-"))
        if frame in repl:
            new = sorted(glob.glob(os.path.join(repl[frame], "pages", "page-*.png")))
            if not new:
                sys.exit(f"no pages in {repl[frame]}")
            print(f"frame {frame}: build pages {lo}-{hi} → {len(new)} pages from {repl[frame]}")
            for f in new:
                pages.append(f); mp.append(f"{len(pages)}\t{frame}\t{f}\tre-cut ({a.why})")
        elif frame in uns:
            f = os.path.join(a.scans, src)
            if not os.path.exists(f):
                sys.exit(f"missing {f}")
            # 2026-10-16 fix (the editor confirmed it was a bug and approved the fix): the whole TIFF used to go to img2pdf, which took its
            # FIRST frame: Wilson's frame 27 (SKM_…130.tif#5, the back cover) came out as #0, the front cover. A
            # multi-page TIFF's frame is now saved alone, losslessly, in the new folder, and that file is used.
            from PIL import Image
            im = Image.open(f)
            if getattr(im, "n_frames", 1) > 1 or fidx:
                im.seek(fidx)
                one = os.path.join(a.out, f"unsplit-frame-{frame:04d}.png")
                im.save(one)
                f = one
            print(f"frame {frame}: build pages {lo}-{hi} → unsplit {src}#{fidx}")
            pages.append(f); mp.append(f"{len(pages)}\t{frame}\t{f}\tunsplit ({a.why})")
        else:
            for p in range(lo, hi + 1):
                f = os.path.join(a.build, "pages", f"page-{p:04d}.png")
                if not os.path.exists(f):
                    sys.exit(f"missing {f}")
                pages.append(f); mp.append(f"{len(pages)}\t{frame}\t{f}\t{a.build_label}")
    missing = (set(repl) | uns) - {int(r[0]) for r in rows}
    if missing:
        sys.exit(f"frames not in the build: {sorted(missing)}")
    r = subprocess.run(["img2pdf", *pages, "-o", os.path.join(a.out, a.stem + ".pdf")], capture_output=True, text=True)
    if r.returncode:
        sys.exit("img2pdf failed: " + r.stderr[-400:])
    with open(os.path.join(a.out, "MAP.tsv"), "x", encoding="utf-8") as f:
        f.write("\n".join(mp) + "\n")
    print(len(rows), "frames ·", len(pages), "pages →", os.path.join(a.out, a.stem + ".pdf"))


if __name__ == "__main__":
    main()
