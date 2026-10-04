#!/usr/bin/env python3
r"""ocr-g1-faint — re-test the pages G1 cleared as BLANK, for FAINT print.

    tools/ocr-g1-faint.py --g1 <G1 report .md.json> --pdfs <list> --out <new dir> [--only pages.tsv]

WHY (G5 re-sample, 2026-09-30). Two of 40 pages G1 had cleared as blank were full pages of print
(*mondo1928* p.265, *oge.5* p.64). G1's ink test, when a page's tones are not clearly split into
print and paper, counts only pixels darker than mid-grey (≤ 128). Their print is grey 160–185 on
paper at ~198, so it scored 0.15% and 0.75% «ink» against the 1% bar. An ABSOLUTE darkness test
cannot see faint print; this tool measures ink RELATIVE TO THE LOCAL PAPER.

WHAT IT DOES, per cleared page (the image the conversion read, by `ocr_page_images`):
  1. crops to the paper (G1's stage 1, unchanged);
  2. estimates the paper at every point (max filter + blur over a wide window) and counts as ink
     each pixel ≥ 25 grey levels darker than its own paper; lines of type = bands of inked rows;
  3. divides the image by its paper (flat-field), stretches the contrast, and runs Tesseract
     (--psm 4, the corpus language, 2× upscale) on the result;
  4. counts REAL words (3+ letters, in any lexicon of `tools/lexicons/`).
VERDICT: READ if Tesseract gives a real reading (≥ 10 tokens of 4+ letters, ≥ 60% of them in ONE
lexicon); UNREAD otherwise. UNREAD is NOT «blank»: the calibration (the 40 judged g1-blank pages of
the G5 re-sample, 2026-09-30) had a printed page (oge.5 p.64, faint, low-resolution) that no
preprocessing let Tesseract read. UNREAD pages are triaged by rel_ink for a LOOK, against quota.
A raw real-word count (union of lexicons) is recorded but decides nothing: junk hits it.

WRITE-SET: only under --out, which must not exist yet: RESULTS.tsv, and <corpus>/page-NNNN.faint.txt
for every page with ≥ 2 real words. It never touches the OCR trees; installing a reading is a
separate, later step.
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, importlib.util
import concurrent.futures as fut
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ocr_page_images import page_images
_s = importlib.util.spec_from_file_location("g1", os.path.join(HERE, "ocr-g1-ink.py"))
g1 = importlib.util.module_from_spec(_s); _s.loader.exec_module(g1)

LEX = {os.path.basename(f_)[:-4]: {x.strip().lower() for x in open(f_, encoding="utf-8", errors="ignore") if x.strip()}
       for f_ in glob.glob(os.path.join(HERE, "lexicons", "*.txt"))}
LEXW = set().union(*LEX.values())
RW = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
W4 = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def paper_crop(im):
    """G1's stage 1: the bounding box of the bright region (board vs page)."""
    small = im.copy(); small.thumbnail((900, 900))
    w, h = small.size; px = np.asarray(small)
    hist = np.bincount(px.ravel(), minlength=256).tolist()
    t1 = g1._otsu(hist, px.size)
    cols = np.where((px[::4, :] > t1).sum(0) > (h / 4) * .5)[0]
    rows = np.where((px[:, ::4] > t1).sum(1) > (w / 4) * .5)[0]
    if len(cols) < w * .15 or len(rows) < h * .15:
        return None
    sx, sy = im.size[0] / w, im.size[1] / h
    return im.crop((int(cols[0] * sx), int(rows[0] * sy), int((cols[-1] + 1) * sx), int((rows[-1] + 1) * sy)))


def measure(img_path, lang, work, tag):
    im = Image.open(img_path).convert("L")
    pg = paper_crop(im)
    if pg is None:
        return None
    w, h = pg.size
    # the PAPER at every point: max filter + blur over several line heights, computed on a 1/8 copy
    # (a full-size 61-px max filter cost ~30 s a page; paper varies slowly, so nothing is lost)
    sm = pg.resize((max(w // 8, 1), max(h // 8, 1)), Image.BILINEAR)
    k = max(3, (min(w, h) // 320) | 1)
    bg = sm.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.GaussianBlur(k)).resize((w, h), Image.BILINEAR)
    a, b = np.asarray(pg, dtype=np.float32), np.maximum(np.asarray(bg, dtype=np.float32), 1)
    dark = (b - a) >= 25
    ink = float(dark.mean())
    rows = dark.mean(1) > 0.03
    bands, run = 0, 0
    for on in list(rows) + [False]:
        if on: run += 1
        else: bands += run >= 2; run = 0
    flat = np.clip(a / b * 255, 0, 255)
    lo = np.percentile(flat, 1)
    flat = np.clip((flat - lo) / max(255 - lo, 1) * 255, 0, 255).astype(np.uint8)
    # enlarge SMALL scans (faint low-resolution pages read better at 2×), but cap the long side at 3,600 px:
    # a blind 2× of a 300-dpi scan made Tesseract take 30–85 s a page on noise (first full run, 20:14)
    sc = min(2.0, 3600 / max(w, h))
    f = Image.fromarray(flat)
    if abs(sc - 1) > .05: f = f.resize((int(w * sc), int(h * sc)), Image.LANCZOS)
    p = os.path.join(work, tag + ".png"); f.save(p)
    try:
        txt = subprocess.run(["tesseract", p, "-", "-l", lang, "--psm", "4"], capture_output=True, text=True, timeout=90).stdout
    except subprocess.TimeoutExpired:
        txt = ""                                             # recorded as UNREAD (0 tokens), never as blank
    real = sum(1 for x in RW.findall(txt) if x.lower() in LEXW)
    # a READING, not junk: the share of 4+-letter tokens in the ONE best lexicon. Junk hits the union of
    # 20 lexicons often (calibration 20:25: junk 0.30–0.39, the one true faint page read, oge.4 p.346, 0.79)
    t4 = W4.findall(txt)
    share, blex = max(((sum(1 for x in t4 if x.lower() in s) / max(len(t4), 1)), k) for k, s in LEX.items())
    return ink, bands, len(RW.findall(txt)), real, len(t4), share, blex, txt


def lang_of(stem):
    return "rus+epo" if re.search(r"(?i)rus|kaukaz|ruska", stem) else "epo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g1", required=True); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"--out {a.out} exists: this tool writes only into a NEW folder")
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    only = {}   # a TAB file «corpus<TAB>page» — corpus names can contain commas and spaces
    for x in (open(a.only, encoding="utf-8") if a.only else []):
        f = x.rstrip("\n").split("\t")
        if len(f) >= 2 and f[1].strip().isdigit(): only.setdefault(f[0], set()).add(int(f[1]))
    jobs = []
    for r in json.load(open(a.g1)):
        c = r.get("corpus"); bl = r.get("blank_pages") or []
        if only: bl = [p for p in bl if p in only.get(c, ())]
        if bl and c in pdfs: jobs.append((c, pdfs[c], bl))
    os.makedirs(a.out)
    out = open(os.path.join(a.out, "RESULTS.tsv"), "w", encoding="utf-8")
    out.write("corpus\tpage\trel_ink\tbands\twords\treal_words\twords4\tbest_share\tbest_lexicon\tverdict\n")
    tally = {"READ": 0, "UNREAD": 0, "UNTESTED": 0}

    def corpus(job):
        c, pdf, bl = job
        work = tempfile.mkdtemp(); rows = []
        try:
            imgs = page_images(pdf, work, jobs=2, pages=bl)
            for n in bl:
                m = measure(imgs[n], lang_of(c), work, f"p{n}") if n in imgs else None
                if m is None:
                    rows.append((c, n, "", "", "", "", "", "", "", "UNTESTED", "")); continue
                ink, bands, words, real, n4, share, blex, txt = m
                # READ = Tesseract gives a real reading; the rest are NOT decided here. rel_ink and bands are
                # recorded for the triage (bands alone never mean print: show-through gives up to 23)
                v = "READ" if n4 >= 10 and share >= 0.6 else "UNREAD"
                rows.append((c, n, f"{ink:.4f}", bands, words, real, n4, f"{share:.2f}", blex, v, txt if real >= 2 else ""))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return rows

    with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for rows in pool.map(corpus, jobs):
            for c, n, ink, bands, words, real, n4, share, blex, v, txt in rows:
                out.write(f"{c}\t{n}\t{ink}\t{bands}\t{words}\t{real}\t{n4}\t{share}\t{blex}\t{v}\n"); tally[v] += 1
                if txt:
                    d = os.path.join(a.out, c); os.makedirs(d, exist_ok=True)
                    open(os.path.join(d, f"page-{n:04d}.faint.txt"), "w", encoding="utf-8").write(txt)
            out.flush()
    out.close()
    print(sum(tally.values()), "pages ·", tally)


if __name__ == "__main__":
    main()
