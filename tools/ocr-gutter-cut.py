#!/usr/bin/env python3
r"""ocr-gutter-cut — the run sheet's C7c.2b: pages printed in columns cut at their gutters, band by band, each column read
top to bottom (2026-10-27).

    python3 tools/ocr-gutter-cut.py <root> --pdfs <full list> --list <item⇥page tsv> --lang <tesseract langs>
            --journal <run dir>/GUTTER.journal.jsonl --progress <run dir>/PROGRESS.txt [--jobs 7] [--dry] [--look <dir>]

WHY. Ezri, 2026-10-27, on the *Tutmonda Jarlibro Esperantista*: its members' lists in two or three columns are read
across the columns line by line, «so neither a tool nor a reader can tell whose entry a line is» (the editor);
the editor 11:3x: the cut a standard C7c step once its blind look passes; then cupel18c's G5 failed on
*Internacia Scienca Revuo* 1904 (8 of 40 contradicted, every LOST page that volume's: two columns under a heading, a
full-width heading, two columns again, the upper columns read in alternating blocks), and the editor. C7c.2's `page_gutters()` (tools/ocr-reocr-best.py) finds no gutter on these scans: it counts
the grey ground and the scan border as ink.

HOW, per page:
  0. THE IMAGE: the one the conversion read (tools/ocr_page_images.py), not a new rendering.
  1. THE PAPER: the columns and rows whose median grey is light (the black scan border dropped).
  2. THE GUTTERS (`sources/ocr-work/jarlibro-gutters-2026-10-27/NOTES.md`, try 8: ten of ten trial pages): ink is print
     darker than 0.85 × Otsu's threshold (Otsu itself on faint pages, median ink under 0.04); a column profile over the
     text rows, smoothed; columns over half ink in the outer 15% (the scan border) trimmed; the text block from 2% to
     98% of the ink; for 4, 3, then 2 columns, the deepest valley within 8% of the block's width of each even split, kept
     only if under half the median ink; the largest count that passes. Where none passes, the page turned by −1.5° …
     +1.5° and tried again (a 12% window), the turn whose cuts are deepest kept.
  3. THE BANDS: each slice of the page (about 1% of its height) CROSSES unless, near each cut, it has a clear gap (± max(6, width/300) px of a
     cut): a heading, a title, a line set across the page. Lines that cross make full-width bands; the rest column bands
     (a column band of one line counts as full width). Bands split half-way between their lines.
  4. THE READING: a full-width band read whole (psm 6), a column band column by column, left first (psm 4); the bands in
     page order. Written as `page-NNNN.gutter.txt` only where the page has 2+ columns and the reading is no worse than
     the page's current one (5+-letter share not lower by more than 0.02, 5+-letter words at least 0.8 of it), or holds
     half as many 5+-letter words again with half of them known (a garbled current reading), as the
     other C7c re-reads. The rebuild prefers it to `.cols`/`.blocks` (tools/ocr-rebuild-combined.py).
Rule 0: each page's file written whole (temp, then rename) as it finishes, then its record journaled; the same command
again skips the journaled pages; PROGRESS.txt every minute. --dry writes no page file (the journal still records the cuts).
--look <dir>: for every page cut, a small image with the cuts (red) and the full-width bands (blue), for a look.
WRITE-SET: `<root>/<item>/page-NNNN.gutter.txt` (not --dry); --journal; --progress and its .log; --look's PNGs.
"""
import os, re, sys, argparse, subprocess, tempfile, shutil, importlib.util, unicodedata, statistics
import concurrent.futures as fut
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cupel_progress as CP
import ocr_page_images as PI
_s = importlib.util.spec_from_file_location("reocr", os.path.join(HERE, "ocr-reocr-best.py"))
RB = importlib.util.module_from_spec(_s); _argv = sys.argv; sys.argv = [_argv[0]]; _s.loader.exec_module(RB); sys.argv = _argv
Image.MAX_IMAGE_PIXELS = None
DEEP = 0.5


def otsu(g):
    h = np.bincount(g.ravel(), minlength=256).astype(float); p = h / h.sum()
    w = np.cumsum(p); mu = np.cumsum(p * np.arange(256)); mt = mu[-1]
    s = (mt * w - mu) ** 2 / (w * (1 - w) + 1e-12); return int(np.nanargmax(s))


def page_box(g):
    col = np.median(g, axis=0); row = np.median(g, axis=1)
    thr = (np.percentile(g, 95) + np.percentile(g, 5)) / 2
    xs = np.where(col > thr)[0]; ys = np.where(row > thr)[0]
    if not len(xs) or not len(ys): return 0, g.shape[1] - 1, 0, g.shape[0] - 1
    return xs.min(), xs.max(), ys.min(), ys.max()


def profile(p, mult):
    # Otsu on the middle 80% of the paper only (2026-10-27, Internacia Scienca Revuo 1904: on the whole frame the black
    # border drew the threshold to 211, and the orange paper came out as ink, 28% of every row); the column profile is the
    # median of eight horizontal slices, so that a heading set across the gutter in one slice does not fill it
    # and then not Otsu at all: the Revuo's pure-white patches drew Otsu's split between paper and white (217, the paper's
    # median 185); ink is what is darker than the paper's median by more than half the way to its darkest 1% (40% of the
    # way for faint print, the second try)
    H, W = p.shape; c = p[int(.1 * H):int(.9 * H), int(.1 * W):int(.9 * W)]
    med, dark = np.median(c), np.percentile(c, 1)
    ink = p < med - (0.5 if mult < 1 else 0.4) * (med - dark); rows = ink.mean(axis=1) > 0.02; a = ink[rows]
    k = max(9, W // 150)
    if len(a) < 16: return ink, np.zeros(W)
    sl = [np.convolve(ink[r].mean(axis=0), np.ones(k) / k, "same") for r in np.array_split(np.where(rows)[0], 8)]
    return ink, np.median(np.array(sl), axis=0)


def find(g, ks=(4, 3, 2), tolf=0.08):
    """(k, cuts in page x, ink matrix of the paper, paper box) for a grey page array"""
    x0, x1, y0, y1 = page_box(g); p = g[y0:y1, x0:x1]
    ink, sm = profile(p, 0.85); W = len(sm)
    if W < 50: return 1, [], None, (x0, x1, y0, y1)
    if np.median(sm[int(.15 * W):int(.85 * W)]) < 0.04:
        ink, sm = profile(p, 1.0)
    edge = np.where(sm > 0.5)[0]; sm = sm.copy()
    le = edge[edge < 0.15 * W]; re_ = edge[edge > 0.85 * W]
    if len(le): sm[:le.max() + 1] = 0
    if len(re_): sm[re_.min():] = 0
    if sm.sum() <= 0: return 1, [], ink, (x0, x1, y0, y1)
    mass = np.cumsum(sm) / sm.sum(); lo = int(np.searchsorted(mass, 0.02)); hi = int(np.searchsorted(mass, 0.98))
    med = np.median(sm[lo:hi]) if hi > lo else 0; B = hi - lo; tol = int(tolf * B)
    if med <= 0 or B < 100: return 1, [], ink, (x0, x1, y0, y1)
    for k in ks:
        cuts = []
        for s in range(1, k):
            e = lo + s * B // k; a_, b_ = max(lo, e - tol), min(hi, e + tol)
            c = int(np.argmin(sm[a_:b_])) + a_
            if sm[c] >= DEEP * med: break
            cuts.append((c, round(float(sm[c] / med), 3)))
        else:
            return k, cuts, ink, (x0, x1, y0, y1)
    return 1, [], ink, (x0, x1, y0, y1)


def find_turned(img):
    """the page as found, or turned by up to 1.5° where no gutter is found unturned"""
    g = np.asarray(img).astype(np.uint8); k, cuts, ink, box = find(g)
    if k > 1: return 0.0, img, k, cuts, ink, box
    best = None
    for ang in (-1.5, -1.0, -0.75, -0.5, -0.25, 0.25, 0.5, 0.75, 1.0, 1.5):
        im2 = img.rotate(ang, fillcolor=255, resample=Image.BILINEAR)
        k2, c2, ink2, box2 = find(np.asarray(im2).astype(np.uint8), ks=(3, 2), tolf=0.12)
        if k2 > 1 and (best is None or max(v for _, v in c2) < best[0]):
            best = (max(v for _, v in c2), ang, im2, k2, c2, ink2, box2)
    return (best[1], best[2], best[3], best[4], best[5], best[6]) if best else (0.0, img, 1, [], ink, box)


def bands(ink, cuts, W):
    """[(y0, y1, «F» or «C»)] in paper rows: lines of print, crossing the gutter or not"""
    rows = ink.mean(axis=1) > 0.02                         # a row of print, not the speckle of a grey ground
    H = len(rows)
    # SLICES, not lines (2026-10-27, Revuo PDF 84, 356, 404 read across: at 125 ppi the space between lines is 2–3 rows,
    # so «lines» ran together into blocks, and one heading in a block crossing the gutter made the whole block full-width):
    # the page in slices of about 1% of its height; a slice with no print takes its neighbours' kind (below)
    wh = max(6, H // 100)
    lines = [(i, min(H, i + wh)) for i in range(0, H, wh) if rows[i:i + wh].any()]
    # a line is in columns where, within 3% of the width of each cut, it has a clear vertical gap at least W/120 wide
    # (2026-10-27, Revuo PDF 264: a lower section's gutter a few pixels off the page's cut, and its left lines running
    # near it, had made every line «crossing» against a fixed ± band around the cut)
    s, g = max(4, W * 3 // 100), max(4, W // 120); out = []
    def gap_near(a, b, c):
        col = ink[a:b, max(0, c - s):c + s].any(axis=0); run = best = 0
        for v in col:
            run = 0 if v else run + 1; best = max(best, run)
        return best >= g
    for a, b in lines:
        cross = not all(gap_near(a, b, c) for c, _ in cuts)
        out.append([a, b, "F" if cross else "C"])
    # a column band of one line is read whole
    for n in range(len(out)):
        if out[n][2] == "C" and (n == 0 or out[n - 1][2] == "F") and (n + 1 == len(out) or out[n + 1][2] == "F"):
            out[n][2] = "F"
    merged = []
    for a, b, t in out:
        if merged and merged[-1][2] == t: merged[-1][1] = b
        else: merged.append([a, b, t])
    for n in range(1, len(merged)):                       # split half-way between bands
        mid = (merged[n - 1][1] + merged[n][0]) // 2; merged[n - 1][1] = mid; merged[n][0] = mid
    if merged: merged[0][0] = 0; merged[-1][1] = H
    return merged


def band_cuts(ink, cuts, a, b, W):
    """each cut moved to the clearest column of this band's own ink within 3% of the width (its own gutter)"""
    s = max(4, W * 3 // 100); prof = ink[a:b].sum(axis=0); out = []
    for c, _ in cuts:
        lo, hi = max(1, c - s), min(W - 1, c + s); seg = prof[lo:hi]
        z = np.where(seg == seg.min())[0]                          # the middle of the clearest run
        out.append(int(lo + (z[0] + z[-1]) // 2) if len(z) else c)
    return out


def tess(img, psm, lang, work, name, up=1):
    # the crop on tesseract's standard input (inside the sandbox its image library cannot open a file in the temp folder);
    # enlarged where the scan is small, and framed in its own paper's grey: tesseract drops letters at a crop's edge, and a
    # WHITE frame round a grey paper made it read the paper as print («Empty page!!», 2026-10-27, Revuo 1904 PDF 107)
    import io
    from PIL import ImageOps
    if up > 1: img = img.resize((img.width * up, img.height * up), Image.LANCZOS)
    img = ImageOps.expand(img, border=20 * up, fill=int(np.median(np.asarray(img))))
    b = io.BytesIO(); img.save(b, format="PNG")
    return subprocess.run(["tesseract", "stdin", "-", "-l", lang, "--psm", str(psm)], input=b.getvalue(),
                          capture_output=True).stdout.decode("utf-8", "replace")


def cut_page(job):
    root, item, pdf, n, cur, lang, look = job
    work = tempfile.mkdtemp(prefix="gutter-")
    try:
        # the image the CONVERSION read (tools/ocr_page_images.py: one stored image extracted byte for byte, else the page
        # rendered at the document's native ppi): Internacia Scienca Revuo 1904's stored scans are 125 ppi, and the same
        # page rendered at 400 dpi read 5 words with tesseract (2026-10-27)
        im_path = PI.page_images(pdf, work, jobs=1, pages=[n]).get(n)
        if not im_path or not os.path.exists(im_path):
            return item, n, "", {"page": n, "k": 0, "kept": False, "why": "no image"}
        img = Image.open(im_path).convert("L")
        ang, img, k, cuts, ink, (x0, x1, y0, y1) = find_turned(img)
        rec = {"page": n, "k": k, "turn": ang, "cuts": [int(x0 + c) for c, _ in cuts], "depth": [v for _, v in cuts]}
        if k < 2:
            rec["kept"] = False; rec["why"] = "one column"; return item, n, "", rec
        W = x1 - x0; bs = bands(ink, cuts, W); rec["bands"] = [(int(a), int(b), t) for a, b, t in bs]
        parts = []; up = 2 if img.width < 1500 else 1             # a small scan (the Revuo 1904: 812 px) read at twice its size
        for i, (a, b, t) in enumerate(bs):
            ya, yb = y0 + a, y0 + b
            if t == "F":
                parts.append(tess(img.crop((x0, ya, x1, yb)), 6, lang, work, f"b{i}", up))
            else:
                xs = [0] + band_cuts(ink, cuts, a, b, W) + [W]
                for j in range(len(xs) - 1):
                    parts.append(tess(img.crop((x0 + xs[j], ya, x0 + xs[j + 1], yb)), 4, lang, work, f"b{i}c{j}", up))
        t = "\n".join(s.strip("\n") for s in parts if s.strip()) + "\n"
        (s0, w0), (s1, w1) = RB.score5(cur), RB.score5(t)
        rec.update({"share5_old": s0, "share5_new": s1, "words5_old": w0, "words5_new": w1})
        # kept where no worse, as the other C7c re-reads; and where it holds half as many 5+-letter words again and half of
        # them known (2026-10-27, Revuo 1904 PDF 424 and 429, 146 → 392 and 33 → 372 such words, refused on the first rule:
        # the share of a reading that short says nothing)
        rec["kept"] = bool(s1 is not None and ((s0 is None or s1 >= s0 - 0.02) and w1 >= 0.8 * w0
                                                or w1 >= 1.5 * w0 and s1 >= 0.5))
        if look and rec["kept"]:
            im = img.convert("RGB"); dr = ImageDraw.Draw(im)
            for a, b, tt in bs:
                if tt == "F": dr.rectangle([x0, y0 + a, x1, y0 + b], outline="blue", width=8)
            for c, _ in cuts:
                for a, b, tt in bs:
                    if tt == "C": dr.line([(x0 + c, y0 + a), (x0 + c, y0 + b)], fill="red", width=10)
            im.thumbnail((900, 1300)); im.save(os.path.join(look, f"{item}-p{n:04d}.png"))
        return item, n, t, rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--pdfs", required=True); ap.add_argument("--list", required=True)
    ap.add_argument("--lang", required=True); ap.add_argument("--journal", required=True); ap.add_argument("--progress", required=True)
    ap.add_argument("--jobs", type=int, default=7); ap.add_argument("--chunk", type=int, default=50)
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--look")
    a = ap.parse_args()
    if a.look: os.makedirs(a.look, exist_ok=True)
    pdfn = {unicodedata.normalize("NFC", os.path.splitext(os.path.basename(l.strip()))[0]): l.strip() for l in open(a.pdfs) if l.strip()}
    jobs = []
    for it, pg in (l.rstrip("\n").split("\t")[:2] for l in open(a.list, encoding="utf-8") if l.strip() and not l.startswith("#")):
        it = unicodedata.normalize("NFC", it); n = int(pg)
        base = os.path.join(a.root, it, f"page-{n:04d}")
        src = next((base + x for x in (".blocks.txt", ".cols.txt", ".reocr.txt", ".txt") if os.path.exists(base + x)), None)
        if it in pdfn and src:
            jobs.append((a.root, it, pdfn[it], n, open(src, encoding="utf-8", errors="ignore").read(), a.lang, a.look))
    J = CP.Journal(a.journal)
    todo = [j for j in jobs if (j[1], j[3]) not in J.done]
    P = CP.Progress(a.progress, "C7c.2b gutter cut", len(jobs), len(jobs) - len(todo), a.chunk)
    with fut.ThreadPoolExecutor(max_workers=a.jobs) as ex:      # threads, as ocr-reocr-best.py: the work is tesseract's
        for f in fut.as_completed([ex.submit(cut_page, j) for j in todo]):
            item, n, t, rec = f.result()
            if rec.get("kept") and not a.dry:
                CP.write_new(os.path.join(a.root, item, f"page-{n:04d}.gutter.txt"), t, J.resuming)
            J.add((item, n), dict(rec, item=item)); P.tick()
    rr = J.recs
    kept = [r for r in rr if r.get("kept")]
    ks = {k: sum(1 for r in rr if r.get("k") == k) for k in (1, 2, 3, 4)}
    md = lambda key: round(statistics.median(r[key] for r in kept if r.get(key) is not None), 3) if kept else None
    line = (f"gutter{' (dry)' if a.dry else ''}: {len(rr)} pages · columns found {{1: {ks[1]}, 2: {ks[2]}, 3: {ks[3]}, 4: {ks[4]}}} · "
            f"turned {sum(1 for r in rr if r.get('turn'))} · kept {len(kept)} · median share5 {md('share5_old')} → {md('share5_new')} · "
            f"words5 {md('words5_old')} → {md('words5_new')}")
    P.finish(line); print(line)


if __name__ == "__main__":
    main()
