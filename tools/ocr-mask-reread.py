#!/usr/bin/env python3
r"""ocr-mask-reread — re-read pages stored as a low-ppi colour layer + a sharp text MASK, at the
mask's resolution.

    tools/ocr-mask-reread.py --pdfs <list> [--pdfs <list> …] --root <ocr root> [--cap 400] [--jobs 6]

⊕ ALSO (2026-09-26): IMAGE-FREE pages that the conversion rendered below 250 ppi — it borrowed the
median ppi of the document's pictures — are re-read at 300. Same `.hr` files: «re-read at a better
resolution than the conversion used». 231 PDFs · 9,429 pages when found.

THE FAULT (found 2026-09-25). Some PDFs (mixed-raster: Kraków JBC, *Tra la Mondo*, *Internacia
Socia Revuo*, *Gento Esperanto*, *Belga Katoliko* …) store a page as colour layers at 100–173 ppi
plus a 1-bit JBIG2 text mask at 240–900 ppi. `ocr-pages.py` counts only `image` rows in
`pdfimages -list`, so it rendered those pages at the COLOUR layer's ppi — *Gento Esperanto* at
100 ppi against a 300 ppi mask. Census: 163 PDFs · 3,355 pages. (A first census said 291; it was
fooled by the small logo mask on ÖNB cover sheets. Only a FULL-PAGE mask counts — width ≥ 1000.)

MEASURED, old ppi → mask ppi, 3 pp. each: *Tra la Mondo* contents 1,771 → 11,184 chars ·
*Gento* 69.3 → 72.1% · Kraków at 900 ppi 65.6 → 63.7% · *Revuo* p.11 214 → 1,019 chars.
Better or level everywhere below 900 ppi: **capped at 400** (approved by the editor, 2026-09-25).
The cap rests on one 900 ppi sample and is provisional.

NON-DESTRUCTIVE, like the psm 4 re-read: writes `page-NNNN.hr.txt` (psm 6) and
`page-NNNN.hr.psm4.txt` beside the existing readings; `ocr-psm-adjudicate.py` then chooses per
page among all four, and `ocr-rebuild-combined.py` assembles. A page already re-read is skipped.
"""
import os, re, sys, glob, argparse, subprocess, tempfile, shutil, collections, time
import concurrent.futures as fut
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cupel_progress import write_new as _write   # run sheet rule 0 (2026-10-23): temp file then rename, so a run killed
                                                 # mid-write never leaves a half-written file that a restart would skip

os.environ.setdefault("OMP_THREAD_LIMIT", "1")


def mask_pages(pdf):
    """page -> render ppi, for pages whose full-page mask out-resolves their colour images."""
    per = collections.defaultdict(lambda: {"img": [], "mask": []})
    out = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True).stdout
    for line in out.splitlines()[2:]:
        f = line.split()
        if len(f) < 15 or not f[0].isdigit():
            continue
        try:
            w, ppi = int(f[3]), int(f[12])
        except ValueError:
            continue
        per[int(f[0])]["img" if f[2] == "image" else "mask"].append((w, ppi))
    pages = {}
    for p, v in per.items():
        big = [m[1] for m in v["mask"] if m[0] >= 1000]
        if big and v["img"] and max(big) > max(i[1] for i in v["img"]) * 1.2:
            pages[p] = max(big)
    # AND IMAGE-FREE PAGES RENDERED TOO LOW (2026-09-26, approved by the editor). The
    # conversion rendered a page with no image at the median ppi of the document's PICTURES; below
    # 250 that starved Tesseract (*Recenzo* p.9: 0 chars at 43 ppi, 1,432 at 300). Re-read at 300.
    ppis = sorted(i[1] for v in per.values() for i in v["img"] if i[1])
    if ppis:
        native = ppis[len(ppis) // 2]
        if native < 250:
            n = _pages(pdf)
            for p in range(1, n + 1):
                if not per.get(p, {}).get("img") and p not in pages:
                    pages[p] = 300
    return pages


def _pages(pdf):
    m = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True,
                                                     text=True).stdout)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", action="append", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cap", type=int, default=400)
    ap.add_argument("--lang", default="epo")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()

    pdfs = list(dict.fromkeys(l.strip() for L in a.pdfs for l in open(L, encoding="utf-8")
                              if l.strip()))
    with fut.ThreadPoolExecutor(max_workers=12) as pool:
        found = [(pdf, mp) for pdf, mp in zip(pdfs, pool.map(mask_pages, pdfs)) if mp]
    total = sum(len(mp) for _, mp in found)
    print(f"{len(found)} PDFs · {total:,} text-mask pages · cap {a.cap} ppi", file=sys.stderr,
          flush=True)

    t0, done = time.time(), 0
    for pdf, mp in found:
        stem = os.path.splitext(os.path.basename(pdf))[0]
        d = os.path.join(a.root, stem)
        os.makedirs(d, exist_ok=True)
        todo = [(p, min(r, a.cap)) for p, r in sorted(mp.items())
                if not os.path.exists(os.path.join(d, f"page-{p:04d}.hr.psm4.txt"))]
        if not todo:
            continue
        work = tempfile.mkdtemp()

        def one(job):
            p, r = job
            b = os.path.join(work, f"h{p:05d}")
            subprocess.run(["pdftoppm", "-r", str(r), "-png", "-f", str(p), "-l", str(p), pdf, b],
                           capture_output=True)
            hit = glob.glob(b + "*.png")
            if not hit:
                return 0
            for psm, suf in (("6", ".hr.txt"), ("4", ".hr.psm4.txt")):
                t = subprocess.run(["tesseract", hit[0], "stdout", "-l", a.lang, "--psm", psm,
                                    "--oem", "1"], capture_output=True, text=True).stdout or ""
                _write(os.path.join(d, f"page-{p:04d}{suf}"), t, True)
            os.remove(hit[0])
            return 1
        try:
            with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
                done += sum(pool.map(one, todo))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        el = time.time() - t0
        print(f"  {stem[:50]:<52} {len(todo):>4} pp · {done:,}/{total:,} · {el/60:.1f} min",
              file=sys.stderr, flush=True)
    print(f"done · {done:,} pages re-read at mask resolution in {(time.time()-t0)/60:.1f} min",
          file=sys.stderr)


if __name__ == "__main__":
    main()
