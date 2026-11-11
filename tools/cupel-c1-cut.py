#!/usr/bin/env python3
r"""cupel-c1-cut — run sheet C1, an item used for some of its pages only: find the pages by their running heads, then cut.

    python3 tools/cupel-c1-cut.py heads --pdfs <PDF list> --items <stem,…|@file> --out <new dir> [--frac 0.10] [--dpi 50]
                                        [--per-sheet 24] [--jobs 4]
    python3 tools/cupel-c1-cut.py cut --pdfs <PDF list> --spec <tsv: stem⇥pages> --out <new dir> [--suffix .part]

WHY (the editor, 2026-10-28 23:1x, cupel19b: *Universo* is scoped to its front matter and its «El Esperantujo» pages,
the section that holds the movement material, Kabe's 1909 piece among it). The run sheet's C1 cut had no box-free call.
heads  renders the top strip (--frac of the height) of every page of each item, grey at --dpi, and stacks them,
       labelled «<stem> PDF <n>», --per-sheet to an image: <out>/sheet-NNN.png and <out>/KEY.tsv (sheet, row, stem,
       PDF page). The operator reads the running heads off the sheets (an own look, C1), not a reader.
cut    for each spec row, a new PDF of the named PDF pages only («1-2,40-47», in order): <out>/<stem><suffix>.pdf (qpdf),
       its page count checked against the spec; <out>/CUT.tsv (stem, pages, count, source).
WRITES only the new folder --out (refused if it exists); temporary renders in it are removed as each strip is taken.
"""
import argparse, concurrent.futures as cf, os, re, subprocess, sys, tempfile

PDFTOPPM, QPDF, PDFINFO = "/opt/homebrew/bin/pdftoppm", "/opt/homebrew/bin/qpdf", "/opt/homebrew/bin/pdfinfo"


def pdfs_of(lst):
    return {os.path.basename(l.strip())[:-4]: l.strip() for l in open(lst, encoding="utf-8") if l.strip()}


def npages(pdf):
    out = subprocess.run([PDFINFO, pdf], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def strip(job):
    pdf, p, dpi, frac, tmp = job
    from PIL import Image
    base = os.path.join(tmp, f"{abs(hash((pdf, p)))}")
    subprocess.run([PDFTOPPM, "-r", str(dpi), "-gray", "-png", "-singlefile", "-f", str(p), "-l", str(p), pdf, base],
                   check=True, capture_output=True)
    im = Image.open(base + ".png"); im.load(); os.remove(base + ".png")
    w, h = im.size
    return im.crop((0, 0, w, max(1, int(h * frac))))


def heads(a):
    from PIL import Image, ImageDraw
    pdfs = pdfs_of(a.pdfs)
    items = [l.strip() for l in open(a.items[1:], encoding="utf-8")] if a.items.startswith("@") else a.items.split(",")
    items = [i for i in items if i]
    missing = [i for i in items if i not in pdfs]
    if missing: sys.exit(f"not on the list: {missing[:5]}")
    os.makedirs(a.out)
    tmp = tempfile.mkdtemp(dir=a.out, prefix=".tmp-")
    jobs = [(i, p) for i in items for p in range(1, npages(pdfs[i]) + 1)]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        strips = list(ex.map(strip, [(pdfs[i], p, a.dpi, a.frac, tmp) for i, p in jobs]))
    os.rmdir(tmp)
    key = ["sheet\trow\tstem\tpdf_page"]
    lab = 150
    for s in range(0, len(jobs), a.per_sheet):
        chunk = list(zip(jobs[s:s + a.per_sheet], strips[s:s + a.per_sheet]))
        W = max(im.size[0] for _, im in chunk) + lab
        H = sum(im.size[1] + 4 for _, im in chunk)
        sheet = Image.new("L", (W, H), 255); d = ImageDraw.Draw(sheet); y = 0
        n = s // a.per_sheet + 1
        for r, ((i, p), im) in enumerate(chunk, 1):
            d.text((4, y + 4), f"{i[-8:]}\nPDF {p}", fill=0)
            sheet.paste(im, (lab, y)); y += im.size[1] + 4
            d.line((0, y - 2, W, y - 2), fill=128)
            key.append(f"sheet-{n:03d}\t{r}\t{i}\t{p}")
        sheet.save(os.path.join(a.out, f"sheet-{n:03d}.png"))
    open(os.path.join(a.out, "KEY.tsv"), "x", encoding="utf-8").write("\n".join(key) + "\n")
    print(f"{len(items)} items, {len(jobs)} pages → {(len(jobs) - 1) // a.per_sheet + 1} sheets in {a.out}")


def pages_of(spec):
    out = []
    for part in spec.split(","):
        lo, _, hi = part.strip().partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def cut(a):
    pdfs = pdfs_of(a.pdfs)
    rows = [l.rstrip("\n").split("\t") for l in open(a.spec, encoding="utf-8") if l.strip() and not l.startswith("#")]
    bad = [r[0] for r in rows if r[0] not in pdfs]
    if bad: sys.exit(f"not on the list: {bad[:5]}")
    os.makedirs(a.out)
    rec = ["stem\tpages\tcount\tsource"]
    for stem, spec in rows:
        want = pages_of(spec); n = npages(pdfs[stem])
        if not want or max(want) > n or len(set(want)) != len(want):
            sys.exit(f"{stem}: pages «{spec}» against {n} PDF pages")
        dst = os.path.join(a.out, stem + a.suffix + ".pdf")
        subprocess.run([QPDF, "--empty", "--pages", pdfs[stem], ",".join(map(str, want)), "--", dst], check=True)
        got = npages(dst)
        if got != len(want): sys.exit(f"{dst}: {got} pages, the spec {len(want)}")
        rec.append(f"{stem}\t{spec}\t{got}\t{pdfs[stem]}")
        print(f"{stem}: {got} of {n} pages → {os.path.basename(dst)}")
    open(os.path.join(a.out, "CUT.tsv"), "x", encoding="utf-8").write("\n".join(rec) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("heads", "cut")); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--items"); ap.add_argument("--spec")
    ap.add_argument("--frac", type=float, default=0.10); ap.add_argument("--dpi", type=int, default=50)
    ap.add_argument("--per-sheet", type=int, default=24); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--suffix", default=".part")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    heads(a) if a.mode == "heads" else cut(a)


if __name__ == "__main__":
    main()
