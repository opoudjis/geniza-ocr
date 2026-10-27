#!/usr/bin/env python3
r"""ocr-pages — convert a scanned PDF by EXTRACTING its page images, not by re-rendering them.

    tools/ocr-pages.py <file.pdf> --out <dir> [--lang epo] [--psm 6] [--jobs 12]
    tools/ocr-pages.py <file.pdf> --out <dir> --probe        # report how the pages are stored

WHY EXTRACT RATHER THAN RENDER — MEASURED 2026-09-24, AND IT IS THE LARGEST SINGLE FINDING
OF THE WEEK.

A scanned PDF does not *contain a page* that must be drawn; it contains a PHOTOGRAPH that was
pasted onto a page. Every conversion this venture has run rasterised that page at a fixed
300 dpi — and the embedded photograph in `ludovikito Historieto` is **1600×1175 at 100 ppi**.
So every page was UPSCALED THREEFOLD: two-thirds of the pixels handed to tesseract were
interpolated, invented from the pixels beside them.

    pdftoppm -r 300     28.6 s/page          ← what we always did
    pdftoppm -r 130      7.2 s/page
    pdfimages -png       4.4 s/page
    pdfimages -j         0.06 s/page  ⇐  and the OCR of it is BETTER

**A hundredfold on time, and a better reading.** The upscaling was not merely wasted work: it
is what destroyed `Adresaro 1905` p.23 — the Z tail of an attendee list, Van Dieren to Zimdars,
which returned 52 characters at 300 dpi and 918 at 130. Interpolation artefacts at 3× turned
clean letterpress into something the engine could not resolve, and 130 dpi survived only by
being accidentally nearer the native size.

**THERE IS ONE CORRECT RESOLUTION — THE IMAGE'S OWN — AND EVERYTHING ABOVE IT IS INVENTION.**
The four-variant render search written an hour earlier was solving the wrong problem: it was
searching for the least-damaging way to upscale. This supersedes it.

WHAT IT DOES:
  1. `pdfimages -list` — how is each page actually stored, and at what native resolution?
  2. Pages holding exactly ONE image are EXTRACTED byte-for-byte (`pdfimages -j`), untouched.
  3. Pages holding none (born-digital text) or several (plates, montages, split scans) fall
     back to `pdftoppm` — scans with several images at the document's own median native ppi, never at
     a fixed 300; IMAGE-FREE pages at 300 (TEXT_PPI), since they have no native resolution (2026-09-26).
  4. OCR runs in parallel over the extracted images.

THE FALLBACK IS NOT A FAILURE, IT IS A DIFFERENT KIND OF PAGE, and the probe reports the mix
so it is never a silent assumption. A born-digital PDF has no embedded page image at all and
must be rendered; a page split across two images must be composited, and this tool renders it
rather than guessing at the join.
"""
import os, re, sys, glob, json, shutil, argparse, subprocess, tempfile, collections
import concurrent.futures as fut
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cupel_progress import write_new as _write   # run sheet rule 0 (2026-10-23): temp file then rename, so a run killed
                                                 # mid-write never leaves a half-written file that a restart would skip


# ⚡ ONE THREAD PER TESSERACT (2026-09-25). We parallelise across PAGES; Tesseract by default
# also spawns a thread per core inside each process, so 4 files × 5 pages × 18 threads drove
# the load to 218 on 18 cores. Set before any tesseract subprocess is launched.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
TEXT_PPI = 300   # render resolution for image-free (born-digital) pages

def pdf_pages(pdf):
    o = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", o, re.M)
    return int(m.group(1)) if m else 0


def page_rotations(pdf):
    """page -> its /Rotate (90, 180, 270), for the pages that carry one.

    WHY (2026-09-28, G5; the editor flagged the upside-down reading). A PDF page may DISPLAY its stored image
    turned: the page's /Rotate. `pdfimages` extracts the image as stored, un-turned; `pdftoppm` renders the page as a
    reader sees it. So every extracted page carrying a /Rotate was read sideways or upside down — *Voĉo de
    Kuracistoj* 1909.8 p.9 (/Rotate 180): all its readings reverse-order gibberish, nine names lost — while every
    rendered look (the image sorts, G5) showed it upright. 697 pages in 49 items carry one. A turned page is
    therefore always RENDERED (at the native ppi, so nothing is upscaled), never extracted."""
    n = pdf_pages(pdf)
    if not n:
        return {}
    o = subprocess.run(["pdfinfo", "-f", "1", "-l", str(n), pdf], capture_output=True, text=True).stdout
    return {int(a): int(b) for a, b in re.findall(r"^Page\s+(\d+) rot:\s+(\d+)", o, re.M) if int(b) % 360}


def image_table(pdf):
    """page -> list of (width, height, ppi) for the images stored on it."""
    o = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True).stdout
    per = collections.defaultdict(list)
    for line in o.splitlines()[2:]:
        f = line.split()
        if len(f) < 15 or not f[0].isdigit():
            continue
        # COLUMN ORDER, and getting it wrong is silent: the header is
        #   page num type width height color comp bpc enc interp object ID x-ppi y-ppi size ratio
        # so width is f[3] and x-ppi is f[12]. Reading f[2] as width parses the literal word
        # «image», raises, and every row is skipped — which makes a fully-scanned PDF report as
        # having NO embedded images and fall back to rendering all of it. Measured: that is the
        # difference between 0.06 s and 28.6 s a page.
        if f[2] != "image":
            continue
        try:
            per[int(f[0])].append((int(f[3]), int(f[4]), int(f[12])))
        except (ValueError, IndexError):
            continue
    return per


def ocr(img, lang, psm):
    r = subprocess.run(["tesseract", img, "stdout", "-l", lang, "--psm", str(psm), "--oem", "1"],
                       capture_output=True, text=True)
    return r.stdout or ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="epo")
    ap.add_argument("--psm", default="6")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 6))
    ap.add_argument("--probe", action="store_true", help="report the page storage and exit")
    a = ap.parse_args()

    n = pdf_pages(a.pdf)
    tbl = image_table(a.pdf)
    rot = page_rotations(a.pdf)
    # a page turned by /Rotate is never extracted: the stored image is not the page as displayed
    one = [p for p in range(1, n + 1) if len(tbl.get(p, [])) == 1 and p not in rot]
    none_ = [p for p in range(1, n + 1) if len(tbl.get(p, [])) == 0]
    many = [p for p in range(1, n + 1) if len(tbl.get(p, [])) > 1]
    ppis = [i[2] for v in tbl.values() for i in v if i[2]]
    ppis.sort()
    native = ppis[len(ppis) // 2] if ppis else 300
    print(f"{os.path.basename(a.pdf)}: {n} pages · {len(one)} single-image (EXTRACT) · "
          f"{len(many)} multi-image · {len(none_)} no image (RENDER) · {len(rot)} turned by /Rotate (RENDER) · native ppi {native}",
          file=sys.stderr)
    if a.probe:
        return

    stem = os.path.splitext(os.path.basename(a.pdf))[0]
    outdir = os.path.join(a.out, stem)
    os.makedirs(outdir, exist_ok=True)
    work = tempfile.mkdtemp()
    try:
        # ---- 1. EXTRACT the single-image pages, byte-for-byte, in ONE call.
        got = {}
        if one:
            subprocess.run(["pdfimages", "-j", "-p", a.pdf, os.path.join(work, "x")],
                           capture_output=True)
            # `-p` puts the PAGE NUMBER in the filename, which is what makes the mapping safe:
            # without it the images are numbered sequentially and a page with two images or none
            # silently shifts every page after it.
            for f in glob.glob(os.path.join(work, "x-*")):
                m = re.match(r"x-(\d+)-\d+\.", os.path.basename(f))
                if m and int(m.group(1)) in set(one):
                    got[int(m.group(1))] = f
        # ---- 2. RENDER the rest, at the document's OWN resolution.
        # ⚡ IN PARALLEL (2026-09-25). This loop was serial: on render-heavy files the machine sat
        # at ONE pdftoppm and ZERO tesseract on 18 cores, ~1 page/s. Same command, same ppi — the
        # output is byte-identical; only the scheduling changed.
        rest = [p for p in range(1, n + 1) if p not in got]

        def render(p):
            # AN IMAGE-FREE PAGE HAS NO NATIVE RESOLUTION (2026-09-26, approved by the
            # editor). Its text is drawn from fonts; «native» here was the median of the
            # document's PICTURES — logos, thumbnails — so *Recenzo pri Universalaj Lingvoj* p.9
            # was rendered at 43 ppi and read as 0 characters (1,432 at 300); *Bibliografio di
            # Ido* at 9 ppi. 107 PDFs / 4,328 pages below 150 ppi. Scans keep their own ppi.
            r = TEXT_PPI if not tbl.get(p) else native
            subprocess.run(["pdftoppm", "-r", str(r), "-png", "-f", str(p), "-l", str(p),
                            a.pdf, os.path.join(work, f"r{p:05d}")], capture_output=True)
            hit = glob.glob(os.path.join(work, f"r{p:05d}*.png"))
            return p, (hit[0] if hit else None)
        with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
            for p, img in pool.map(render, rest):
                if img:
                    got[p] = img

        # ---- 3. OCR in parallel.
        def do(p):
            return p, ocr(got[p], a.lang, a.psm)
        texts = {}
        with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
            for p, t in pool.map(do, sorted(got)):
                texts[p] = t

        # ---- 3b. ADAPTIVE FALLBACK — the one part that cannot be reasoned about in advance.
        # THERE IS NO SIGNATURE FOR WHEN A PAGE FAILS. Belga Sonorilo 1907 p.60 is the same
        # encoding, the same 173 ppi and the same size as its neighbours, and it is the one that
        # returns 59 characters where they return six thousand. Any predictor would be fitted to
        # the handful of cases seen on 2026-09-24.
        #   So this does not predict. It compares each page against THIS DOCUMENT'S OWN median
        # yield and re-reads the outliers by the other method. A page far below its neighbours is
        # either genuinely near-empty — in which case the second reading agrees and costs 0.3 s —
        # or it is a page we failed to read, which is the only kind of damage that leaves no
        # trace in the output.
        #   It runs in BOTH directions: extraction is not universally better either (p.200 read
        # 7,308 rendered against 7,090 native, ~3%), so a rendered page that under-performs is
        # retried by extraction on the same test.
        lens = sorted(len(t) for t in texts.values() if len(t) > 200)
        med = lens[len(lens) // 2] if lens else 0
        retried = 0
        if med:
            for p in sorted(texts):
                if len(texts[p]) >= med * 0.25:
                    continue
                alt = None
                if p in one:                       # was extracted → try rendering it
                    subprocess.run(["pdftoppm", "-r", str(native), "-png", "-f", str(p),
                                    "-l", str(p), a.pdf, os.path.join(work, f"alt{p:05d}")],
                                   capture_output=True)
                    hit = glob.glob(os.path.join(work, f"alt{p:05d}*.png"))
                    alt = hit[0] if hit else None
                elif p not in rot:                 # was rendered → try extracting it (never a turned page)
                    subprocess.run(["pdfimages", "-j", "-p", "-f", str(p), "-l", str(p), a.pdf,
                                    os.path.join(work, f"alx{p:05d}")], capture_output=True)
                    hit = glob.glob(os.path.join(work, f"alx{p:05d}*"))
                    alt = hit[0] if hit else None
                if not alt:
                    continue
                t2 = ocr(alt, a.lang, a.psm)
                if len(t2) > len(texts[p]):
                    texts[p] = t2
                    retried += 1
        for p, t in texts.items():
            _write(os.path.join(outdir, f"page-{p:04d}.txt"), t, True)
        done = [(p, len(t)) for p, t in texts.items()]
        if retried:
            print(f"  {retried} pages rescued by the other method", file=sys.stderr)
        # ---- 4. Combine with page markers, so a hit traces back to a page.
        combined = os.path.join(a.out, stem + ".txt")
        parts = []                # the combined file is the item's «done» mark (cupel-convert.sh skips an item that has it):
        for p in range(1, n + 1):  # written last and whole, never half
            q = os.path.join(outdir, f"page-{p:04d}.txt")
            if os.path.exists(q) and os.path.getsize(q):
                parts.append(f"\n=== page {p} ===\n")
                parts.append(open(q, encoding="utf-8", errors="ignore").read())
        _write(combined, "".join(parts), True)
        chars = sum(c for _, c in done)
        print(f"  {len(done)}/{n} pages · {chars:,} chars → {combined}", file=sys.stderr)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
