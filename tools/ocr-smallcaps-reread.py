#!/usr/bin/env python3
r"""ocr-smallcaps-reread — re-read the pages that carry SMALL CAPITALS at up to 3× size, for SEARCH only.

    tools/ocr-smallcaps-reread.py --preferred <ocr-preferred tree> --root <search tree> --pdfs <list> --gate <gate json>
                                  --out <new manifest dir> [--min 3] [--jobs 6]

WHY (G5 re-sample 2026-09-30; failure-map row 5b). Names set in small capitals are misread past finding: «BRÉON» →
«Bnéow», «H. HODLER» → «H. Hopren». Small capitals are cut at lower-case height, so at scan resolution each letter is
a few pixels tall. A 3× Tesseract re-read recovered 1 name in 4 in the trial. The editor judged on 2026-09-30 (22:5x)
that a Tesseract re-read of a corpus dense with small caps is reasonable.

WHICH PAGES: small caps cannot be marked name by name (a misread small-caps name often looks like an ordinary word),
but the PAGES that set them carry TELLTALE misreadings — mixed-case tokens such as «HauGG», «BRéoN», «DELAGRAvE»,
«IvAN». Both G5 small-caps pages carry them (espero.pacifista.1905 p.350: «PoLJAsxij», «IvAN», «MALFELIĈULO»;
progreso4 p.805: «DELAGRAvE», «BeaurrONT», «BeauFRONT»). A page with at least --min (3) telltales in its PREFERRED
reading is re-read. 6,348 of 114,986 pages qualified on 2026-09-30 (an upper bound: all-caps headings also trip it).

WHAT: the image the conversion read (`ocr_page_images`), enlarged ×3 (long side capped at 5,000 px), read by Tesseract
`--psm 4` in the corpus's language (epo; ido for Ido corpora; occidental items with epo). The result is written as
`page-NNNN.sc3x.txt` beside the page, ONLY where no such file exists; tools/ocr-rebuild-combined.py adds it to the
SEARCH text (never the preferred reading). WRITE-SET: those new files, and <out>/MANIFEST.tsv (new folder).
"""
import os, re, sys, json, glob, argparse, tempfile, shutil, subprocess
import concurrent.futures as fut
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cupel_progress as CP   # run sheet rule 0 (2026-10-23): each page written whole (temp file, then renamed); pages that
                              # have their .sc3x.txt are skipped, so a run started again (with a NEW --out) resumes
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ocr_page_images import page_images
# WIDENED 2026-10-08 (approved by the editor; proposal (a) of an internal record, 2026-10-08, not published; failure map R17): the second
# form may END in up to two lower-case letters («PRivAr» for PRIVAT, cupel5 PDF page 1, was not counted). Measured on all
# 118,469 preferred pages: pages with >= 3 telltales 8,560 -> 9,051; it only adds matches. Applies from the next batch on
# (the tool reads only the --pdfs it is given); the older pages are not re-read.
TELL = re.compile(r"\b[A-ZÀ-Ž][a-zà-ž]+[A-ZÀ-Ž]{2,}[a-zà-ž]*\b|\b[A-ZÀ-Ž]{2,}[a-zà-ž]{1,2}[A-ZÀ-Ž]+[a-zà-ž]{0,2}\b")
LANG = {"ido": "ido+epo", "esperanto": "epo", "occidental": "epo", "english": "eng+epo"}


def pages_of(path):
    if not os.path.exists(path): return {}
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + open(path, encoding="utf-8", errors="ignore").read())
    return {int(a): b for a, b in zip(parts[1::2], parts[2::2])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preferred", required=True); ap.add_argument("--root", required=True)
    ap.add_argument("--pdfs", required=True); ap.add_argument("--gate", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=6)
    # OFICIALA GAZETO (the editor ruled on 2026-10-02, 10:0x, that it has to be done even if only partial): --corpora selects items
    # by name (regex); with --min 0 every page is read; --render-dpi N renders the page with pdftoppm at N dpi instead of
    # enlarging the image the conversion read (600 dpi recovered about half of the G5-missed Gazeto names).
    ap.add_argument("--corpora", default=None); ap.add_argument("--render-dpi", type=int, default=0)
    ap.add_argument("--progress", help="rule 0: rewrite this PROGRESS.txt every minute")
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: this tool writes its manifest only into a NEW folder")
    avail = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout.split()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    gate = {r["corpus"]: r.get("primary") or "esperanto" for r in json.load(open(a.gate))}
    jobs = []
    for c, prim in sorted(gate.items()):
        if c not in pdfs: continue
        if a.corpora and not re.search(a.corpora, c): continue
        P = [p for p, t in pages_of(os.path.join(a.preferred, c + ".txt")).items() if len(TELL.findall(t)) >= a.min
             and not os.path.exists(os.path.join(a.root, c, f"page-{p:04d}.sc3x.txt"))]
        if P:
            lang = LANG.get(prim, "epo")
            if not all(x in avail for x in lang.split("+")): lang = "epo"
            jobs.append((c, pdfs[c], P, lang))
    os.makedirs(a.out)
    man = open(os.path.join(a.out, "MANIFEST.tsv"), "w", encoding="utf-8")
    man.write("corpus\tpage\tlang\tscale\twords\tstatus\n")
    print(sum(len(j[2]) for j in jobs), "pages in", len(jobs), "corpora", flush=True)

    def corpus(job):
        c, pdf, P, lang = job
        work = tempfile.mkdtemp(); rows = []
        try:
            # one page at a time with --render-dpi (2 Oct: rendering a whole 400-page volume at 600 dpi first wrote nothing
            # for an hour); otherwise the images the conversion read, extracted together as before
            # M4.4 (2026-10-02): each render is KEPT in the page-image cache, <cache>/<item>/page-NNNN-<dpi>dpi.png (the layout of
            # tools/ocr-rus-fullpage.py), and reused; and the dict now STORES what it renders — before, `p in im` rendered a
            # page and `im[p]` rendered it again.
            cache_dir = os.path.join(os.environ.get("OCR_PAGE_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                     "published", "heterophony-resources", "geniza", "sources", "page-image-cache.noindex")), c)
            class Lazy(dict):
                def __missing__(self, p):
                    cf = os.path.join(cache_dir, f"page-{p:04d}-{a.render_dpi}dpi.png")
                    if os.path.exists(cf):
                        self[p] = cf; return cf
                    subprocess.run(["pdftoppm", "-r", str(a.render_dpi), "-f", str(p), "-l", str(p), "-gray", "-png", pdf,
                                    os.path.join(work, f"r{p}")], capture_output=True, timeout=300)
                    g = sorted(glob.glob(os.path.join(work, f"r{p}*.png")))
                    if not g: raise KeyError(p)
                    if shutil.disk_usage(work).free > 50 * 2 ** 30:          # the disk guard of tools/ocr_page_images.py
                        os.makedirs(cache_dir, exist_ok=True); shutil.move(g[-1], cf); self[p] = cf; return cf
                    self[p] = g[-1]; return g[-1]
                def __contains__(self, p):
                    try: self[p]; return True
                    except KeyError: return False
            im = Lazy() if a.render_dpi else page_images(pdf, work, jobs=2, pages=P)
            for p in P:
                dst = os.path.join(a.root, c, f"page-{p:04d}.sc3x.txt")
                if p not in im: rows.append((c, p, lang, "", "", "no image")); continue
                if os.path.exists(dst): rows.append((c, p, lang, "", "", "exists")); continue
                g = Image.open(im[p]).convert("L"); w, h = g.size
                sc = 1.0 if a.render_dpi else min(3.0, 5000 / max(w, h))
                if sc > 1.05: g = g.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
                f = os.path.join(work, f"p{p}.png"); g.save(f)
                if a.render_dpi:
                    for x in glob.glob(os.path.join(work, f"r{p}*.png")): os.remove(x)
                try:
                    t = subprocess.run(["tesseract", f, "-", "-l", lang, "--psm", "4"], capture_output=True,
                                       text=True, timeout=240).stdout
                except subprocess.TimeoutExpired:
                    rows.append((c, p, lang, f"{sc:.2f}", "", "timeout")); continue
                if t.strip():
                    CP.write_new(dst, t, True)
                rows.append((c, p, lang, f"{sc:.2f}", len(t.split()), "written" if t.strip() else "empty"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return rows

    done = 0
    P = CP.Progress(a.progress, "C7b.2 small capitals", sum(len(j[2]) for j in jobs), chunk=50) if a.progress else None
    with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for rows in pool.map(corpus, jobs):
            for r in rows: man.write("\t".join(map(str, r)) + "\n")
            man.flush(); done += len(rows)
            if P: P.tick(len(rows))
            print(done, "pages done", flush=True)
    man.close(); print("done")
    if P: P.finish(f"{done} pages")


if __name__ == "__main__":
    main()
