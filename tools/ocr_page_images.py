r"""ocr_page_images — the page image a tool must read is the one the CONVERSION read.

    from ocr_page_images import page_images
    imgs = page_images(pdf, workdir, jobs=8)      # {page number: image path}

WHY THIS EXISTS (2026-09-25). `ocr-psm-both.py` and `ocr-g1-ink.py` each took «the first image
`pdfimages` extracts for the page». On a page stored as several images — plates, montages, split
scans, and the colour-layer + text-mask PDFs — that is a FRAGMENT: *Progreso* 5 p.533 read 369
characters from its first image against 1,425 from the page. So the psm 4 re-read compared a
fragment with a page, and the ink test tested a fragment.

The choice is made here, by the SAME rule `ocr-pages.py` uses (its own `image_table`, imported,
  not copied): one stored image → extract it byte-for-byte; none or several → render the page at
  the document's median native ppi. Two readings of a page are only comparable if they are
  readings of the same image.
"""
import os, re, glob, shutil, subprocess, importlib.util
import concurrent.futures as fut

# ONE THREAD PER TESSERACT (2026-09-25). We parallelise across PAGES; Tesseract by default
# also spawns a thread per core inside each process, so 4 files × 5 pages × 18 threads drove
# the load to 218 on 18 cores. Set before any tesseract subprocess is launched.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

_HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("ocr_pages", os.path.join(_HERE, "ocr-pages.py"))
_op = importlib.util.module_from_spec(_s)
_s.loader.exec_module(_op)


def native_ppi(pdf):
    ppis = sorted(i[2] for v in _op.image_table(pdf).values() for i in v if i[2])
    return ppis[len(ppis) // 2] if ppis else 300


def render_page(pdf, work, p, tag="alt"):
    """The conversion's SAFETY NET, reproduced: a page whose extracted image read far below its
    neighbours was re-read by RENDERING and the longer reading kept (ocr-pages.py step 3b). A tool
    re-reading that page must take the same route, or it compares a failed reading with a rescued
    one — *Progreso* 5 p.533: 357 characters extracted, 1,425 stored."""
    subprocess.run(["pdftoppm", "-r", str(native_ppi(pdf)), "-png", "-f", str(p), "-l", str(p),
                    pdf, os.path.join(work, f"{tag}{p:05d}")], capture_output=True)
    hit = glob.glob(os.path.join(work, f"{tag}{p:05d}*.png"))
    return hit[0] if hit else None


def _page_images_uncached(pdf, work, jobs=8, pages=None):
    tbl = _op.image_table(pdf)
    n = _op.pdf_pages(pdf)
    want = set(pages) if pages else set(range(1, n + 1))
    ppis = sorted(i[2] for v in tbl.values() for i in v if i[2])
    native = ppis[len(ppis) // 2] if ppis else 300
    # a page turned by /Rotate is rendered, never extracted (see ocr-pages.py `page_rotations`, 2026-09-28)
    rot = _op.page_rotations(pdf)
    one = {p for p in want if len(tbl.get(p, [])) == 1 and p not in rot}
    got = {}
    if one and len(one) * 10 >= n:
        # many pages wanted: ONE whole-document extraction is cheapest (0.007 s/page)
        subprocess.run(["pdfimages", "-j", "-p", pdf, os.path.join(work, "x")], capture_output=True)
        for f in glob.glob(os.path.join(work, "x-*")):
            m = re.match(r"x-(\d+)-\d+\.", os.path.basename(f))
            if m and int(m.group(1)) in one:
                got[int(m.group(1))] = f
    elif one:
        # A FEW pages wanted (the G1 case: a handful of silent pages in a 900-page volume):
        # extracting the whole document to test five pages was the slowest step. Per page instead.
        def extract(p):
            b = os.path.join(work, f"e{p:05d}")
            subprocess.run(["pdfimages", "-j", "-p", "-f", str(p), "-l", str(p), pdf, b],
                           capture_output=True)
            hit = glob.glob(b + "-*")
            return p, (hit[0] if hit else None)
        with fut.ThreadPoolExecutor(max_workers=jobs) as pool:
            for p, img in pool.map(extract, sorted(one)):
                if img:
                    got[p] = img

    def render(p):
        r = _op.TEXT_PPI if not tbl.get(p) else native   # image-free page: no native ppi
        subprocess.run(["pdftoppm", "-r", str(r), "-png", "-f", str(p), "-l", str(p),
                        pdf, os.path.join(work, f"r{p:05d}")], capture_output=True)
        hit = glob.glob(os.path.join(work, f"r{p:05d}*.png"))
        return p, (hit[0] if hit else None)
    with fut.ThreadPoolExecutor(max_workers=jobs) as pool:
        for p, img in pool.map(render, sorted(want - set(got))):
            if img:
                got[p] = img
    return got


# PAGE-IMAGE CACHE (M4.4, 2026-10-02; the editor asked that extracted page images not be discarded, so that this work
# need not be repeated). Every image this helper extracts or renders is KEPT at
#   <cache>/<item>/opi-<pdf size>-<pdf mtime>/page-NNNN.<ext>
# and reused by any later call for the same page. The folder is keyed to the PDF's size and modification time, so a
# replaced scan never gets a stale image. Callers see no change: cached images are COPIED into their working folder, as
# before, so a caller that deletes or alters its copies cannot touch the cache. Images stay gitignored (copyright scans
# stay local). OCR_PAGE_CACHE="" turns the cache off; OCR_PAGE_CACHE=<dir> moves it.
_CACHE = os.environ.get("OCR_PAGE_CACHE", os.path.join(_HERE, "..", "published", "heterophony-resources", "geniza",
                                                       "sources", "page-image-cache.noindex"))
_MIN_FREE = float(os.environ.get("OCR_PAGE_CACHE_MIN_FREE_GB", "50")) * 2 ** 30


def page_images(pdf, work, jobs=8, pages=None):
    if not _CACHE:
        return _page_images_uncached(pdf, work, jobs=jobs, pages=pages)
    st = os.stat(pdf); item = os.path.splitext(os.path.basename(pdf))[0]
    cdir = os.path.join(_CACHE, item, f"opi-{st.st_size}-{int(st.st_mtime)}")
    want = sorted(set(pages) if pages else range(1, _op.pdf_pages(pdf) + 1))
    have = {}
    if os.path.isdir(cdir):
        for f in os.listdir(cdir):
            m = re.fullmatch(r"page-(\d{4,5})\.(\w+)", f)
            if m: have[int(m.group(1))] = os.path.join(cdir, f)
    got = {}
    for p in want:
        if p in have:
            dst = os.path.join(work, f"c{p:05d}" + os.path.splitext(have[p])[1]); shutil.copyfile(have[p], dst); got[p] = dst
    miss = [p for p in want if p not in got]
    if miss:
        new = _page_images_uncached(pdf, work, jobs=jobs, pages=miss)
        # DISK GUARD: the disk stood at 95% full on 2 Oct (93 GiB free); the cache stops GROWING below _MIN_FREE free
        # (reads from it go on). Raise or lower with OCR_PAGE_CACHE_MIN_FREE_GB.
        if shutil.disk_usage(_CACHE if os.path.isdir(_CACHE) else os.path.dirname(_CACHE)).free < _MIN_FREE:
            return got | new
        os.makedirs(cdir, exist_ok=True)
        for p, f in new.items():
            got[p] = f
            ext = os.path.splitext(f)[1] or ".img"; final = os.path.join(cdir, f"page-{p:04d}{ext}")
            if not os.path.exists(final):
                tmp = final + f".tmp{os.getpid()}"; shutil.copyfile(f, tmp); os.replace(tmp, final)   # atomic: parallel runs
    return got
