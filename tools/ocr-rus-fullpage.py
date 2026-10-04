#!/usr/bin/env python3
r"""ocr-rus-fullpage — re-read the Russian of every page that has a Russian reading, from a FULL-PAGE render.

    tools/ocr-rus-fullpage.py --root <ocr-rendersearch> --pdfs <list> --out <new manifest dir> [--jobs 4] [--dpi 300]

WHY (approved by the editor on 2026-10-02, as too much was at stake; G5 final re-sample). On two SPECIAL HANDLING pages the
Russian names the judges saw were missing from the Russian reading, and a fresh 300 dpi full-page read recovered three
of the four (RigaStelo 1911 n05-06 p.26; RuslandaEsperantisto1909.1 p.34). Earlier readings were sometimes taken from
an image the PDF embeds rather than the page (the photo fault of 1 Oct: an internal record, 2026-09-30, not published, E6).

WHAT. For every item with a `RUSSIAN.json`, every page with a `page-NNNN.rus.txt`: render the page with pdftoppm at --dpi
(greyscale), read it with Tesseract `--psm 4` in the model the old-letter rule chooses for that page (`orus` if
`ocr_russian_reading` picks the orus reading, else `rus`), and write `page-NNNN.rusfull.txt` ONLY WHERE NONE EXISTS.
`tools/ocr-rus-companion.py` then keeps whichever reading holds more real Russian words. WRITE-SET: the new rusfull
files, and <out>/MANIFEST.tsv (a new folder).
"""
import os, re, sys, glob, argparse, tempfile, shutil, subprocess
import concurrent.futures as fut
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, ".."); sys.path.insert(0, HERE)
import ocr_russian_reading as RR


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", required=True); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--cache", default=os.path.join(ROOT, "published", "heterophony-resources", "geniza", "sources", "page-image-cache.noindex"),
                    help="where page renders are KEPT for reuse (gitignored images)")
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: the manifest goes only into a NEW folder")
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: (l.strip() if l.strip().startswith("/") else os.path.join(ROOT, l.strip()))
            for l in open(a.pdfs) if l.strip()}
    jobs = []
    for rj in sorted(glob.glob(os.path.join(a.root, "*", "RUSSIAN.json"))):
        d = os.path.dirname(rj); c = os.path.basename(d)
        if c not in pdfs: continue
        for f in sorted(glob.glob(os.path.join(d, "page-*.rus.txt"))):
            p = int(re.search(r"page-(\d+)\.rus\.txt", f).group(1)); dst = os.path.join(d, f"page-{p:04d}.rusfull.txt")
            if os.path.exists(dst): continue
            ch = RR.russian_reading_path(f) or f
            jobs.append((c, pdfs[c], p, "orus" if ch.endswith(".orus.txt") else "rus", dst))
    os.makedirs(a.out); man = open(os.path.join(a.out, "MANIFEST.tsv"), "w", encoding="utf-8")
    man.write("corpus\tpage\tmodel\twords\tstatus\n"); print(len(jobs), "pages", flush=True)

    def one(j):
        c, pdf, p, model, dst = j; w = tempfile.mkdtemp()
        try:
            # PAGE-IMAGE CACHE (the editor asked on 2026-10-02 that extracted page images not be discarded, so that this
            # work need not be repeated): the render is KEPT at <cache>/<item>/page-NNNN-<dpi>dpi.png and reused by any later pass.
            cdir = os.path.join(a.cache, c); cf = os.path.join(cdir, f"page-{p:04d}-{a.dpi}dpi.png")
            if not os.path.exists(cf):
                os.makedirs(cdir, exist_ok=True)
                subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", str(p), "-l", str(p), "-gray", "-png", pdf, os.path.join(w, "r")],
                               capture_output=True, timeout=300)
                g = sorted(glob.glob(os.path.join(w, "r*.png")))
                if g: shutil.move(g[-1], cf)
            im = [cf] if os.path.exists(cf) else []
            if not im: return (c, p, model, "", "no image")
            try:
                t = subprocess.run(["tesseract", im[-1], "-", "-l", model, "--psm", "4"], capture_output=True, text=True, timeout=300).stdout
            except subprocess.TimeoutExpired:
                return (c, p, model, "", "timeout")
            if t.strip() and not os.path.exists(dst): open(dst, "w", encoding="utf-8").write(t)
            return (c, p, model, len(t.split()), "written" if t.strip() else "empty")
        finally:
            shutil.rmtree(w, ignore_errors=True)

    done = 0
    with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for r in pool.map(one, jobs):
            man.write("\t".join(map(str, r)) + "\n"); man.flush(); done += 1
            if done % 100 == 0: print(done, "pages done", flush=True)
    man.close(); print("done", done)


if __name__ == "__main__":
    main()
