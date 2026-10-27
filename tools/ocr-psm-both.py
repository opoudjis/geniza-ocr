#!/usr/bin/env python3
r"""ocr-psm-both — read EVERY page in both segmentation modes, so the mode is adjudicated per page.

    tools/ocr-psm-both.py --pdfs <list of pdf paths> --root <ocr root> [--jobs 12]

WHY EVERY PAGE AND NOT JUST THE LISTS (the editor ruled, 2026-09-25, that the default change to what
the measurement had proven). 194 unambiguously PROSE pages were read in both modes on the same extracted image:

    psm 4 wins    43  (22%)          median lexical hit-rate   psm6 90.7%
    psm 6 wins    26  (13%)                                    psm4 90.4%
    tie          125  (64%)

Two measures pointing opposite ways is not «psm 4 is better». It is **neither mode dominates, on
prose exactly as on lists** — so a default is the error, whichever default it is. That is the same
finding the render mode, the resolution and the language model each produced this week, and it is
the fourth time the answer has been «stop choosing for the corpus, measure the page».

The argument this replaces was mine and it was wrong: that `--psm 4` is the list mode and would
therefore damage prose. It does not. The inference came from the marginal list pages and did not
transfer, which is what happens when a plausible mechanism is preferred to a measurement.

THE SPEED THAT MAKES IT AFFORDABLE. Extracting the whole document in ONE `pdfimages` call is
**0.007 s/page** — 425 pages in 2.8 seconds — against ~0.4 s/page when each page is extracted by
its own call, because a per-page call re-parses the whole PDF to reach one page. That is a
fiftyfold difference and it is the reason reading every page twice is a short job rather than an
overnight one.

NON-DESTRUCTIVE. Writes `page-NNNN.psm4.txt` beside the existing `page-NNNN.txt`; adjudication
and reassembly are separate steps (`ocr-psm-adjudicate.py`, `ocr-rebuild-combined.py`), so the
choosing is visible and reversible rather than baked into the conversion.
"""
import os, re, sys, glob, argparse, subprocess, tempfile, shutil, time, threading
import concurrent.futures as fut
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cupel_progress import write_new as _write   # run sheet rule 0 (2026-10-23): temp file then rename, so a run killed
                                                 # mid-write never leaves a half-written file that a restart would skip
from ocr_page_images import page_images, render_page


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", required=True, help="file of PDF paths, one per line")
    ap.add_argument("--root", required=True)
    ap.add_argument("--lang", default="epo")
    ap.add_argument("--jobs", type=int, default=3, help="threads per file")
    ap.add_argument("--files", type=int, default=6, help="files at once")
    a = ap.parse_args()

    pdfs = [l.strip() for l in open(a.pdfs, encoding="utf-8") if l.strip()]
    t0 = time.time()
    tally = {"files": 0, "pages": 0}
    lock = threading.Lock()

    def do_file(pdf):
        stem = os.path.splitext(os.path.basename(pdf))[0]
        d = os.path.join(a.root, stem)
        if not os.path.isdir(d):
            return 0
        todo = []
        for f in sorted(glob.glob(os.path.join(d, "page-*.txt"))):
            # BASE pages only — `page-NNNN.txt`. The glob also matches `.psm4.txt` and the text-mask
            # re-reads `.hr.txt` / `.hr.psm4.txt`, which are readings, not pages.
            m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
            if not m or os.path.exists(f[:-len(".txt")] + ".psm4.txt"):
                continue
            todo.append((int(m.group(1)), f))
        if not todo:
            return 0
        work = tempfile.mkdtemp()
        n_done = 0
        try:
            # ONE extraction call for the whole document — see the speed note above — but the
            # image per page is chosen by the CONVERSION's rule (ocr_page_images), never «the first
            # image extracted»: on a multi-image page that was a fragment, and psm 4 was then
            # compared with psm 6 on different images (fixed 2026-09-25).
            byn = page_images(pdf, work, jobs=a.jobs, pages=[n for n, _ in todo])

            def one(job):
                n, f = job
                img = byn.get(n)
                if not img:
                    return None
                def read(im):
                    return subprocess.run(["tesseract", im, "stdout", "-l", a.lang, "--psm", "4",
                                           "--oem", "1"], capture_output=True, text=True).stdout or ""
                t = read(img)
                # The conversion's safety net, mirrored: if this reading is far below the stored
                # one, the stored one was probably RESCUED by rendering — so render and re-read,
                # and psm 4 gets the same image psm 6 had.
                if len(t) < 0.25 * os.path.getsize(f):
                    alt = render_page(pdf, work, n)
                    if alt:
                        t2 = read(alt)
                        if len(t2) > len(t):
                            t = t2
                _write(f[:-len(".txt")] + ".psm4.txt", t, True)
                return n
            with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
                n_done = sum(1 for r in pool.map(one, todo) if r is not None)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        with lock:
            tally["files"] += 1; tally["pages"] += n_done
            if tally["files"] % 25 == 0:
                el = time.time() - t0
                print(f"  {tally['files']} items · {tally['pages']:,} pages · {el/60:.1f} min "
                      f"({tally['pages']/max(el,1):.1f} pages/s)", file=sys.stderr, flush=True)
        return n_done

    # ⚡ FILES IN PARALLEL (2026-09-26). One file at a time left the machine idle on small
    # rendered issues — *Esperanto Triumfonta*, 4 pages at 600 ppi, 4 renders and nothing else:
    # 53 pages in 10 minutes. The conversion was parallel across files; this step was not.
    with fut.ThreadPoolExecutor(max_workers=a.files) as pool:
        list(pool.map(do_file, pdfs))
    el = time.time() - t0
    print(f"done · {tally['pages']:,} pages read at --psm 4 in {el/60:.1f} min "
          f"({tally['pages']/max(el,1):.1f} pages/s)", file=sys.stderr)


if __name__ == "__main__":
    main()
