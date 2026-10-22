#!/usr/bin/env python3
r"""ocr-reocr-best — RE-OCR poor scans: find, per item, the render/threshold/layout that reads best.

    tools/ocr-reocr-best.py probe <root> --pdfs <list> --items <json list> --out <probe.json> [--jobs 12]
    tools/ocr-reocr-best.py run   <root> --pdfs <list> --probe <probe.json> [--min-gain 5] [--jobs 12]
    tools/ocr-reocr-best.py pages <root> --pdfs <list> --list <corpus<TAB>page tsv> [--jobs 12]
PAGES mode (approved by the editor, 2026-09-27): single pages — the LOST pages of the image sorts. Every variant is
tried on the page and the best is kept only if it scores higher than the page as it stands (a LOST page
often scores nothing, so any real reading wins); the rest go to vision transcription.

WHY (the editor decided on 2026-09-27, 15:35, that the poor scans be re-read by OCR). 53 items (679 pp) fail G4 on scan quality —
not on language, not Russian, not rosters (an internal record, 2026-09-27, not published; family G + the 7
failing Ido items). The pipeline already tried 300 ppi and psm 4/6; these are the untried levers.

PROBE: 3 evenly spaced pages per item (all if fewer), each read with every VARIANT:
  v400      400 ppi grey, psm 6
  v400s     400 ppi grey, psm 6, Sauvola adaptive threshold (`-c thresholding_method=2`) — faint/uneven ink
  v400s4    400 ppi grey, psm 4, Sauvola — columns and lists
  vfrk      400 ppi grey, psm 6, `frk+epo` — FRAKTUR items only (Estlanda Esperantisto, Idowoti, Volapükabled 1881–82)
(VOLAPUK items: `deu` in place of `epo+eng`, and `frk+deu`.)
Score = median over the sample of the share of 2+-letter words in the item's own lexicon (Esperanto, or
Ido for Ido items, or Volapük and German together for VOLAPUK items) — the gate's G4 idea, on the sample. The CURRENT text's pages are scored the same way.
RUN: an item is re-read in full with its best variant only if that beats the current text by >= min-gain
points on the sample; then, PAGE BY PAGE, the re-read is kept only where it scores higher than the
current page. Writes `page-NNNN.reocr.txt` BESIDE the existing files and `REOCR.json`; replaces nothing.
Base language `epo+eng` as the render-search pipeline (`ocr-pdf.sh` default).
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, statistics, collections, unicodedata
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cupel_progress as CP
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
LEXDIR = os.path.join(HERE, "lexicons")
W = re.compile(r"[^\W\d_]{2,}")
_L = {}
FRAKTUR = ("EstlandaEsperantisto", "Idowoti",
           # cupel15 (the editor ruled on 2026-10-17, 23:1x, that this needs no confirmation): Volapükabled 1881–82, its German
           # column in Fraktur (C1: 1881 file 51, p. 4 and the title page; Antiqua from 1883)
           "ANNO_e2s_1881", "ANNO_e2s_1882",
           # cupel16 (2026-10-19; C1 look 2026-10-18, an internal record, not published): German running text in
           # Fraktur: Feyerabend 1888, Müller 1888, Romer 1888, Steiner 1889, Das Volkswohl 1898–99 (whole pages), Lott 1888 (the
           # German column); Sionsharfe 1878–80 (the quick German reading of 2026-10-18 read its Fraktur as noise)
           "feyerabend_weltspracheschwindel_1888", "muller_phantom_1888", "romer_vp_und_professoren_1888_bsb",
           "steiner_drei_weltsprach-systeme_1889", "volkswohl_weltsprachliches_", "lott_ist_volapuk_die_beste_1888", "sionsharfe_")
# VOLAPÜK items (2026-10-17): scored against the Volapük list with German beside it, read with the German model (it has
# ä ö ü; it reads Volapükabled about 0.05 better than the Esperanto one, an internal record, 2026-10-17, not published)
VOLAPUK = ("ANNO_e2s_",
           # cupel16 (2026-10-19), the Volapük-main items of temerov's scans (declared; confirmed by the editor, 2026-10-18 23:0x)
           "cogabled_", "gross_dokums_lecif_deut_1888", "kausch_lised_vpanas_1901", "kosmopolan_", "mulapenad_nebolitik_",
           "nogan_vpik_", "nunal_nulik_", "nuns_blefik_", "spodel_vpik_hamburg", "volaspodel_", "vpabled_nedanik_haastert_1884-85",
           "vpabled_talik_1888", "vpaflen_jveizik_", "vpagased_lostanik_1891", "vpaklubs_", "vpan_nolik_",
           # and its German-main pamphlets and papers on Volapük: the same treatment (read with `deu`, Fraktur with `frk+deu`,
           # scored on Volapük and German together, German carrying the score), since this tool scores no German list alone
           "bukalised_literata_1889", "feyerabend_weltspracheschwindel_1888", "gutensohn_abwehr_1888",
           "kniele_einstein_linguo_internacia_1890", "lott_ist_volapuk_die_beste_1888", "low_reflexionen_berlin_1888",
           "mittheilungen_", "muller_phantom_1888", "nurnberger_presse_", "pietzker_zur_kritik_1889",
           "romer_vp_und_professoren_1888_bsb", "rund_um_die_welt_haupenthal_nachwort", "rund_um_die_welt_y",
           "scheyrer_concurrenten_1888_onb", "schuchardt_auf_anlass_1888", "siegismund_verzeichniss_1888", "sionsharfe_",
           "steiner_drei_weltsprach-systeme_1889", "tapuk_1896", "volkswohl_weltsprachliches_", "vom_guten_das_beste_1897-99",
           "wesen_zweck_ziel_vortrag", "zamponi_einfuhrung_1904")
IDO = ("posta_mundi", "matematikal", "nordamuziko", "rusalibrovortaro", "ukraina", "Idomarcho", "Idowoti",
       "sundiala", "vivo", "latviana")


def lex(name):
    if name not in _L:
        # «a+b» (2026-10-17): the union of two lists, for a text in two languages
        _L[name] = set().union(*({w.strip().lower() for w in open(os.path.join(LEXDIR, n + ".txt"), encoding="utf-8", errors="ignore") if w.strip()}
                                 for n in name.split("+")))
    return _L[name]


def score(text, lexname):
    ws = [w.lower() for w in W.findall(text)]
    return 100.0 * sum(w in lex(lexname) for w in ws) / len(ws) if len(ws) >= 20 else None


def lexname(item):
    if any(item.startswith(p) for p in VOLAPUK):
        return "volapuk+german"
    return "ido" if any(item.startswith(p) or p in item for p in IDO) else "esperanto"


def variants(item):
    base = "deu" if any(item.startswith(p) for p in VOLAPUK) else "epo+eng"
    v = {"v400": (400, "6", False, base), "v400s": (400, "6", True, base), "v400s4": (400, "4", True, base)}
    if any(item.startswith(p) for p in FRAKTUR):
        v["vfrk"] = (400, "6", False, "frk+deu" if base == "deu" else "frk+epo")
    return v


def read_page(pdf, n, spec, work):
    dpi, psm, sauvola, lang = spec
    stem = os.path.join(work, f"r{n}-{dpi}")
    if not glob.glob(stem + "*.png"):
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), pdf, stem], capture_output=True)
    img = stem + ".png"
    if not os.path.exists(img):
        return ""
    cmd = ["tesseract", img, "-", "-l", lang, "--psm", psm] + (["-c", "thresholding_method=2"] if sauvola else [])
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def current_pages(root, item):
    p = os.path.join(root, item + ".txt")
    t = open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p) else ""
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def probe_item(job):
    root, item, pdf = job
    cur = current_pages(root, item); ln = lexname(item)
    pages = sorted(p for p, t in cur.items() if len(W.findall(t)) >= 20) or sorted(cur)
    sample = pages if len(pages) <= 3 else [pages[len(pages) // 6], pages[len(pages) // 2], pages[5 * len(pages) // 6]]
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        res = {"item": item, "lexicon": ln, "sample": sample,
               "current": statistics.median([s for s in (score(cur.get(p, ""), ln) for p in sample) if s is not None] or [0])}
        for name, spec in variants(item).items():
            sc = [score(read_page(pdf, p, spec, work), ln) for p in sample]
            sc = [s for s in sc if s is not None]
            res[name] = statistics.median(sc) if sc else 0
        best = max((k for k in res if k.startswith("v")), key=lambda k: res[k])
        res["best"] = best; res["gain"] = round(res[best] - res["current"], 1)
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_page(job):
    root, item, pdf, n, spec, ln = job
    d = os.path.join(root, item); work = tempfile.mkdtemp(prefix="reocr-")
    try:
        t = read_page(pdf, n, spec, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return item, n, t


def page_all_variants(job):
    root, item, pdf, n = job
    ln = lexname(item); work = tempfile.mkdtemp(prefix="reocr-")
    try:
        best = (None, None, "")
        for name, spec in variants(item).items():
            t = read_page(pdf, n, spec, work); sc = score(t, ln)
            if sc is not None and (best[1] is None or sc > best[1]):
                best = (name, sc, t)
        return item, n, best
    finally:
        shutil.rmtree(work, ignore_errors=True)


# COLUMNS (2026-10-18, cupel15 C11; the editor decided at 03:5x that psm 3 be measured first, then its re-read): G5 failed on the multi-column
# pages, read straight across their columns by psm 4 and 6 (failure map R41). psm 3 (Tesseract's own layout analysis) reads
# them column by column: on the 21 LOST pages of the sample, lines across a column rule 29% → 0%, the share of 5+-letter
# words in the lists 0.751 → 0.833 (an internal record, 2026-10-18, not published). A page whose text
# crosses columns (≥ CROSS_MIN of its lines) is read so; the reading is KEPT only where its 5+-letter share is not lower
# (by more than 0.01), it crosses less, and it holds at least 0.8 of the current 5+-letter words (a failed read, e.g. 2 words,
# is refused). Written as `page-NNNN.cols.txt` beside the others (the C7a `.reocr.txt` untouched); ocr-rebuild-combined.py
# ranks it above `.reocr.txt`. COLUMNS.json per item records every page tried.
CROSS = re.compile(r"\w.{2,}\|.{2,}\w")
W5 = re.compile(r"[^\W\d_]{5,}")
CROSS_MIN = 0.10
_C = {}


def cross_share(t):
    ln = [l for l in t.split("\n") if l.strip()]
    return sum(1 for l in ln if CROSS.search(l)) / len(ln) if ln else 0.0


def score5(t):
    if "L" not in _C:
        import volapuk_analyser as VA
        _C["V"] = VA.VolapukWords()
        _C["L"] = set().union(*({w.strip().lower() for w in open(os.path.join(LEXDIR, n + ".txt"), encoding="utf-8", errors="ignore") if w.strip()}
                                 for n in ("german", "english", "italian", "french", "dutch", "esperanto")))
    ws = [w.lower() for w in W5.findall(t)]
    return (sum(1 for w in ws if w in _C["V"] or w in _C["L"]) / len(ws), len(ws)) if ws else (None, 0)


def columns_page(job):
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        t = read_page(pdf, n, (400, "3", False, "deu"), work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (s0, w0), (s1, w1) = score5(cur), score5(t)
    c0, c1 = cross_share(cur), cross_share(t)
    keep = s1 is not None and (s0 is None or s1 >= s0 - 0.01) and c1 < c0 and w1 >= 0.8 * w0
    return item, n, t, {"page": n, "share5_old": s0, "share5_new": s1, "words5_old": w0, "words5_new": w1,
                        "cross_old": round(c0, 3), "cross_new": round(c1, 3), "kept": keep}


# COLUMNS, ROUND 2 (2026-10-18; the editor decided at 10:0x to loosen the tolerance, cut the page and look, after G5b failed on 6 LOST pages, 4 of them refused
# by round 1): the pages round 1 refused are read again with psm 3 and kept within a tolerance of 0.02 (round 1: 0.01); where
# psm 3 still fails, the page is CUT into columns at the gutters of its image (vertical bands in the middle 10-90% of the
# width, at least 1% of the page wide, inked on under 3% of rows once printed rules are set aside, with ink on both sides on
# at least 60% of text rows: the test of ocr-layout-mixed.py's gutter(), on the whole page), each strip read at psm 6, and
# the strips joined left to right. The same tests decide (5+-letter share not lower by more than 0.02, crossing less, words
# >= 0.8). COLUMNS.json gains a "round2" list beside "pages". THE CUT IS NOT USED (the editor decided at 10:1x to loosen the tolerance and chain on to G5c:
# it found a gutter on 1 of the 6 LOST pages, show-through and noise defeating the ink profile); page_gutters() and
# cut_read() stay for a later layout cut. Pages round 1 never tried (two columns with no printed rule) are read at psm 3
# and kept where the 5+-letter share is not lower by more than 0.02 and the 5+-letter words >= 0.9.
TOL2 = 0.02


def page_gutters(img):
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    a = np.asarray(Image.open(img).convert("L")) < 128
    rows = a.any(axis=1)
    if not rows.any():
        return []
    a = a[rows]
    frac = a.mean(axis=0)
    rule = frac >= 0.5
    for d in range(1, 4):
        rule = rule | np.roll(rule, d) | np.roll(rule, -d)
    frac = np.where(rule, 0.0, frac)
    w = a.shape[1]; lo, hi, minw = int(0.1 * w), int(0.9 * w), max(12, int(0.01 * w))
    cuts, run, start = [], 0, 0
    for x in range(lo, hi + 1):
        if x < hi and frac[x] < 0.03:
            if run == 0:
                start = x
            run += 1
        else:
            if run >= minw or (run >= 12 and rule[start:start + run].any()):
                g = start + run // 2
                both = a[:, :start].any(axis=1) & a[:, start + run:].any(axis=1)
                if both.mean() >= 0.6:
                    cuts.append(g)
            run = 0
    return cuts


def cut_read(pdf, n, work):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    read_page(pdf, n, (400, "6", False, "deu"), work)          # renders the page image (and reads it whole, unused)
    img = os.path.join(work, f"r{n}-400.png")
    if not os.path.exists(img):
        return "", 0
    cuts = page_gutters(img)
    if not cuts:
        return "", 0
    im = Image.open(img); W_ = im.size[0]; xs = [0] + cuts + [W_]; out = []
    for i in range(len(xs) - 1):
        sp = os.path.join(work, f"strip{i}.png"); im.crop((xs[i], 0, xs[i + 1], im.size[1])).save(sp)
        out.append(subprocess.run(["tesseract", sp, "-", "-l", "deu", "--psm", "6"], capture_output=True, text=True).stdout)
    return "\n".join(out), len(cuts)


def round2_untried(job):
    """a page round 1 did not try (no «|» rules read): multi-column by its IMAGE (a gutter), psm 3 then the cut, kept if
    the 5+-letter share is not lower by more than TOL2 and the 5+-letter words >= 0.9 of the current (no crossing to
    measure). The look of 2026-10-18 (an internal record, not published): Nunal nulik PDF 14 and Melopik PDF 66, two columns with no
    printed rule, about 20 lines lost each."""
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        rec = {"page": n, "untried": True}
        s0, w0 = score5(cur); rec.update({"share5_old": s0, "words5_old": w0})
        ok = lambda s1, w1: s1 is not None and (s0 is None or s1 >= s0 - TOL2) and w1 >= 0.9 * w0
        t3 = read_page(pdf, n, (400, "3", False, "deu"), work); s3, w3 = score5(t3)
        rec["psm3"] = {"share5": s3, "words5": w3}
        if ok(s3, w3):
            rec["kept"] = "psm3"; return item, n, t3, rec
        rec["kept"] = False; return item, n, "", rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


def round2_page(job):
    if len(job) == 6:
        return round2_untried(job[:5])
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        (s0, w0), c0 = score5(cur), cross_share(cur)
        ok = lambda s1, w1, c1: s1 is not None and (s0 is None or s1 >= s0 - TOL2) and c1 < c0 and w1 >= 0.8 * w0
        t3 = read_page(pdf, n, (400, "3", False, "deu"), work); (s3, w3), c3 = score5(t3), cross_share(t3)
        rec = {"page": n, "share5_old": s0, "words5_old": w0, "cross_old": round(c0, 3),
               "psm3": {"share5": s3, "words5": w3, "cross": round(c3, 3)}}
        if ok(s3, w3, c3):
            rec["kept"] = "psm3"; return item, n, t3, rec
        rec["kept"] = False; return item, n, "", rec
    finally:
        shutil.rmtree(work, ignore_errors=True)


# FRAKTUR PAGES (2026-10-18, cupel15; G5c found a German page in Fraktur, 1904 file 62 PDF 31, its names read by no model,
# and the editor ruled at 12:1x that cases left open must be resolved): a page whose text shows the long-s
# misreadings of Fraktur read by an Antiqua model (MARKS: «fich», «ift», «jondern», «fehr», «Profeffor» …; 72 pages of
# cupel15 with 3 or more) is read with `frk+deu` at psm 4 and psm 6; the better (fewer marks, then the higher 5+-letter
# share) is KEPT where the marks fall by half or more, the 5+-letter share is not lower by more than 0.02 and the 5+-letter
# words are >= 0.8 of the current. Written as `page-NNNN.frk.txt`; ocr-rebuild-combined.py ranks it above `.cols.txt`.
# FRAKTUR.json per item records every page tried. The list: --list <TSV item⇥page>.
MARKS = re.compile(r"\b(fich|ift|jich|jondern|fondern|fehr|jehr|fchon|jchon|felbft|jelbft|dafs|Gefellfchaft|befonders|bejonders|"
                   r"fowie|jowie|jein|jeine|jeiner|Profeffor|Brofeffor|müffen|laffen|wiffen|Waffer|unfere?r?|unjere?r?|"
                   r"diefe[rnms]?|dieje[rnms]?|fie|jie|fein|feine|feiner|alfo|aljo|Fchleyer)\b")


def fraktur_page(job):
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        m0, (s0, w0) = len(MARKS.findall(cur)), score5(cur)
        best = None
        for psm in ("4", "6"):
            t = read_page(pdf, n, (400, psm, False, "frk+deu"), work)
            m1, (s1, w1) = len(MARKS.findall(t)), score5(t)
            cand = (m1, -(s1 or 0), psm, t, s1, w1)
            if best is None or cand[:2] < best[:2]:
                best = cand
        m1, _, psm, t, s1, w1 = best
        keep = s1 is not None and m1 <= m0 / 2 and (s0 is None or s1 >= s0 - 0.02) and w1 >= 0.8 * w0
        return item, n, t, {"page": n, "psm": psm, "marks_old": m0, "marks_new": m1, "share5_old": s0, "share5_new": s1,
                            "words5_old": w0, "words5_new": w1, "kept": keep}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# SECOND READINGS BESIDE THE CHOSEN ONE (2026-10-18, after cupel15 was signed; the editor decided at 12:5x to keep both readings): the pages
# whose Fraktur re-read (FRAKTUR.json) or psm 3 re-read (COLUMNS.json, round 2) was REFUSED are read again the same way and
# the reading filed as `page-NNNN.frk-add.txt` / `page-NNNN.cols-add.txt`, which ocr-rebuild-combined.py APPENDS to the
# SEARCH text (never the preferred), as a boosted reading is: a German name in Fraktur, or a phrase in column order, is then
# found beside what the chosen reading holds. A reading with no 5+-letter words is not filed. ADDS.json per item.
def add_page(job):
    root, item, pdf, n, kind, psm = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        lang = "frk+deu" if kind == "frk" else "deu"
        t = read_page(pdf, n, (400, psm, False, lang), work)
        return item, n, kind, t, score5(t.replace("ſ", "s"))[1]
    finally:
        shutil.rmtree(work, ignore_errors=True)


# PAGES THAT READ EMPTY (2026-10-18; `RUNBOOK.md` C7c.5; built when the editor asked whether what it listed as not yet built could be done now): the
# pages where round 2's psm 3 read nothing (COLUMNS.json), sorted by the INK of the page (100 dpi grey; the share of pixels
# under 110 inside a 5% margin) and the 3+-letter words of the current text: BLANK (ink < 0.04 and < 30 words: nothing to
# do, G1's ink test covers them), DARK (ink > 0.7: coloured covers, boards), LIGHT (the rest). A LIGHT page is read with
# psm 3 and Sauvola (`thresholding_method=2`, deu, 400 ppi) and filed as `page-NNNN.cols-add.txt` where it holds at least
# 20 words and 0.8 of the current text's (cupel15: 7 pages of 1904 file 62); a DARK page, and a LIGHT one Sauvola cannot
# read, goes to the look: rendered at 150 dpi beside its current text into --look (NNN.png, NNN.txt, KEY.tsv) for one
# blind reader (A.7 with the caps' lines, the paper's colour asked). --out: the batch's TSV of every page and what was done.
def empty_page(job):
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        stem = os.path.join(work, "p100")
        subprocess.run(["pdftoppm", "-r", "100", "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), pdf, stem], capture_output=True)
        g = np.asarray(Image.open(stem + ".png").convert("L")).astype(float); H, W_ = g.shape
        ink = float((g[int(.05 * H):int(.95 * H), int(.05 * W_):int(.95 * W_)] < 110).mean())
        w0 = len(re.findall(r"[^\W\d_]{3,}", cur))
        kind = "blank" if ink < 0.04 and w0 < 30 else "dark" if ink > 0.7 else "light"
        rec = {"item": item, "page": n, "ink": round(ink, 3), "words": w0, "kind": kind, "action": "none"}
        if kind == "light":
            stem4 = os.path.join(work, "p400")
            subprocess.run(["pdftoppm", "-r", "400", "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), pdf, stem4], capture_output=True)
            t = subprocess.run(["tesseract", stem4 + ".png", "-", "-l", "deu", "--psm", "3", "-c", "thresholding_method=2"],
                               capture_output=True, text=True).stdout
            w1 = len(re.findall(r"[^\W\d_]{3,}", t)); rec["sauvola_words"] = w1
            if w1 >= 20 and w1 >= 0.8 * w0:
                rec["action"] = "sauvola-add"; return rec, t
        if kind != "blank":
            rec["action"] = "look"
        return rec, ""
    finally:
        shutil.rmtree(work, ignore_errors=True)


# THE LAYOUT CUT BY TESSERACT'S OWN BLOCKS (2026-10-18; built when the editor asked whether what `RUNBOOK.md` listed as not yet
# built could be done now): psm 3 is run for its LAYOUT only (`tsv`: the level-2 block boxes), each block is cropped (8 px margin) from the
# 400 ppi page and read alone at psm 6 (`deu`), and the blocks are joined in Tesseract's order. Where psm 3's own reading
# crossed columns or dropped words, its block boxes may still be right. Kept as `page-NNNN.blocks.txt` by the round-2 rule
# (5+-letter share not lower by more than 0.02, crossing less, 5+-letter words >= 0.8 of the chosen reading); ranked by the
# rebuild with `.cols`. --dry measures only (writes nothing). The list: --list <TSV item⇥page>.
def block_read(pdf, n, work):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    stem = os.path.join(work, f"b{n}-400")
    subprocess.run(["pdftoppm", "-r", "400", "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), pdf, stem], capture_output=True)
    img = stem + ".png"
    if not os.path.exists(img):
        return "", 0
    tsv = subprocess.run(["tesseract", img, "-", "-l", "deu", "--psm", "3", "tsv"], capture_output=True, text=True).stdout
    boxes = []
    for l in tsv.split("\n")[1:]:
        f = l.split("\t")
        if len(f) >= 11 and f[0] == "2":
            x, y, w, h = map(int, f[6:10])
            if w > 20 and h > 20:
                boxes.append((int(f[2]), x, y, w, h))
    if not boxes:
        return "", 0
    im = Image.open(img); W_, H_ = im.size; out = []
    for i, (_, x, y, w, h) in enumerate(sorted(boxes)):
        bp = os.path.join(work, f"blk{i}.png")
        im.crop((max(0, x - 8), max(0, y - 8), min(W_, x + w + 8), min(H_, y + h + 8))).save(bp)
        out.append(subprocess.run(["tesseract", bp, "-", "-l", "deu", "--psm", "6"], capture_output=True, text=True).stdout)
    return "\n".join(out), len(boxes)


def blocks_page(job):
    root, item, pdf, n, cur = job
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        (s0, w0), c0 = score5(cur), cross_share(cur)
        t, k = block_read(pdf, n, work)
        (s1, w1), c1 = score5(t), cross_share(t)
        keep = bool(k) and s1 is not None and (s0 is None or s1 >= s0 - TOL2) and c1 < c0 and w1 >= 0.8 * w0
        return item, n, t, {"page": n, "blocks": k, "share5_old": s0, "share5_new": s1, "words5_old": w0, "words5_new": w1,
                            "cross_old": round(c0, 3), "cross_new": round(c1, 3), "kept": keep}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# SAVE AS YOU GO, RESUME, REPORT (2026-10-22, rule 0 of `RUNBOOK.md`; the editor required at 14:1x that outputs be saved
# incrementally so that a run can be recovered): the blocks, fraktur, adds and empties modes take --journal <jsonl> and
# --progress <PROGRESS.txt>. Each page's files are written as the page finishes (cupel_progress.write_new: temp, then
# rename), then its record is journaled; started again with the same --journal, the pages in it are skipped and the
# per-item JSON and the summary line are built from the journal at the end, so a killed run loses only the pages in flight.
def run_journaled(a, fn, jobs, key, step, handle):
    J = CP.Journal(a.journal) if a.journal and not a.dry else None
    todo = [j for j in jobs if not J or key(j) not in J.done]
    P = CP.Progress(a.progress, step, len(jobs), len(jobs) - len(todo), a.chunk) if a.progress else None
    recs = list(J.recs) if J else []
    with fut.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for f in fut.as_completed([ex.submit(fn, j) for j in todo]):
            k, rec = handle(f.result(), J.resuming if J else False)
            if J:
                J.add(k, rec)
            recs.append(rec)
            if P:
                P.tick()
    return recs, P


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("probe", "run", "pages", "columns", "columns2", "fraktur", "adds", "frkcands", "empties", "blocks")); ap.add_argument("root")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--look")
    ap.add_argument("--list")
    ap.add_argument("--pdfs", required=True); ap.add_argument("--items"); ap.add_argument("--out"); ap.add_argument("--probe")
    ap.add_argument("--min-gain", type=float, default=5.0); ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--journal"); ap.add_argument("--progress"); ap.add_argument("--chunk", type=int, default=100)
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    if a.mode == "probe":
        items = [i for i in json.load(open(a.items)) if i in pdfs]
        with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = list(ex.map(probe_item, [(a.root, i, pdfs[i]) for i in items]))
        json.dump(res, open(a.out, "w"), indent=1)
        for r in sorted(res, key=lambda r: -r["gain"]):
            print(f"{r['item'][:40]:40} {r['lexicon']:9} current {r['current']:5.1f}  " +
                  "  ".join(f"{k} {r[k]:5.1f}" for k in r if k.startswith("v")) + f"  → {r['best']} {r['gain']:+.1f}")
        return
    if a.mode == "blocks":
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        jobs = []
        for it, pg in (l.rstrip("\n").split("\t")[:2] for l in open(a.list, encoding="utf-8") if l.strip()):
            it = unicodedata.normalize("NFC", it); n = int(pg)
            base = os.path.join(a.root, it, f"page-{n:04d}")
            src = next((base + x for x in (".frk.txt", ".cols.txt", ".reocr.txt", ".txt") if os.path.exists(base + x)), None)
            if it in pdfn and src:
                if not a.dry and os.path.exists(os.path.join(a.root, it, "BLOCKS.json")):
                    sys.exit(f"exists: {it}/BLOCKS.json")
                jobs.append((a.root, it, pdfn[it], n, open(src, encoding="utf-8", errors="ignore").read()))
        def handle(res, resuming):
            item, n, t, rec = res
            if rec["kept"] and not a.dry:
                CP.write_new(os.path.join(a.root, item, f"page-{n:04d}.blocks.txt"), t, resuming)
            return (item, n), dict(rec, item=item)
        rr, P = run_journaled(a, blocks_page, jobs, lambda j: (j[1], j[3]), "C7c.2a blocks", handle)
        recs = collections.defaultdict(list)
        for r in rr:
            recs[r["item"]].append({k: v for k, v in r.items() if k != "item"})
        if not a.dry:
            for item, v in recs.items():
                json.dump({"mode": "blocks (psm 3 layout, each block psm 6, deu, 400 ppi)", "pages": sorted(v, key=lambda r: r["page"])},
                          open(os.path.join(a.root, item, "BLOCKS.json"), "w"), indent=1)
        kept = sum(1 for r in rr if r["kept"])
        md = lambda k: statistics.median(r[k] for r in rr if r[k] is not None) if rr else None
        line = (f"blocks{' (dry)' if a.dry else ''}: {len(rr)} pages · kept {kept} · median share5 {md('share5_old')} → {md('share5_new')} · "
                f"words5 {md('words5_old')} → {md('words5_new')} · crossing {md('cross_old')} → {md('cross_new')} · no blocks {sum(1 for r in rr if not r['blocks'])}")
        if P:
            P.finish(line)
        print(line)
        return
    if a.mode == "empties":
        if not a.out or os.path.exists(a.out) or not a.look or os.path.exists(a.look):
            sys.exit(f"--out and --look needed, and new: {a.out} {a.look}")
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        jobs = []
        for it in (unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))):
            cj = os.path.join(a.root, it, "COLUMNS.json")
            if it not in pdfn or not os.path.exists(cj):
                continue
            for r in json.load(open(cj)).get("round2", []):
                if not r["kept"] and (r.get("psm3") or {}).get("share5") is None:
                    # the page's CHOSEN reading alone, not the search text (which may hold second readings already:
                    # the first test on cupel15 counted them and sent 15 light pages to the look instead of filing them)
                    base = os.path.join(a.root, it, f"page-{r['page']:04d}")
                    src = next((base + x for x in (".frk.txt", ".cols.txt", ".reocr.txt", ".txt") if os.path.exists(base + x)), None)
                    if src:
                        jobs.append((a.root, it, pdfn[it], r["page"], open(src, encoding="utf-8", errors="ignore").read()))
        def handle(res, resuming):
            r, t = res
            if r["action"] == "sauvola-add":
                p = os.path.join(a.root, r["item"], f"page-{r['page']:04d}.cols-add.txt")
                if os.path.exists(p) and not resuming:
                    r["action"] = "sauvola (cols-add exists, not written)"
                else:
                    CP.write_new(p, t, resuming)
            return (r["item"], r["page"]), r
        rr, P = run_journaled(a, empty_page, jobs, lambda j: (j[1], j[3]), "C7c.5 empties", handle)
        res = [(r, "") for r in rr]
        look = [r for r, _ in res if r["action"] == "look"]
        if look:
            os.makedirs(a.look); key = []
            for i, r in enumerate(look, 1):
                nn = f"{i:03d}"
                subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", "-f", str(r["page"]), "-l", str(r["page"]),
                                pdfn[r["item"]], os.path.join(a.look, nn)], capture_output=True)
                shutil.copy(os.path.join(a.root, r["item"], f"page-{r['page']:04d}.txt"), os.path.join(a.look, nn + ".txt"))
                key.append(f"{nn}\t{r['item']}\t{r['page']}\t{r['kind']}\n")
            open(os.path.join(a.look, "KEY.tsv"), "w", encoding="utf-8").write("".join(key))
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("item\tpage\tink\twords\tkind\taction\tsauvola_words\n")
            f.writelines(f"{r['item']}\t{r['page']}\t{r['ink']}\t{r['words']}\t{r['kind']}\t{r['action']}\t{r.get('sauvola_words', '')}\n"
                         for r, _ in sorted(res, key=lambda x: (x[0]["item"], x[0]["page"])))
        k = collections.Counter(r["kind"] for r, _ in res); act = collections.Counter(r["action"] for r, _ in res)
        line = f"empties: {len(res)} pages · {dict(k)} · {dict(act)} · look: {len(look)} → {a.look if look else '(none)'}"
        if P:
            P.finish(line)
        print(line)
        return
    if a.mode == "frkcands":
        # the FRAKTUR candidates (2026-10-18; `RUNBOOK.md` C7c): every page of the --items whose current text holds 3 or more
        # long-s misreadings (MARKS), written as the --list TSV the `fraktur` mode reads; --out names it, refused if it exists
        if not a.out or os.path.exists(a.out):
            sys.exit(f"--out needed, and new: {a.out}")
        rows = []
        for it in (unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))):
            for n, t in current_pages(a.root, it).items():
                k = len(MARKS.findall(t))
                if k >= 3:
                    rows.append((it, n, k))
        open(a.out, "w", encoding="utf-8").write("".join(f"{it}\t{n}\n" for it, n, _ in sorted(rows)))
        print(f"frkcands: {len(rows)} pages in {len({r[0] for r in rows})} items → {a.out}")
        return
    if a.mode == "adds":
        items = [unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))]
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        jobs = []
        for it in items:
            if it not in pdfn:
                continue
            if os.path.exists(os.path.join(a.root, it, "ADDS.json")):
                sys.exit(f"exists: {it}/ADDS.json")
            fj, cj = os.path.join(a.root, it, "FRAKTUR.json"), os.path.join(a.root, it, "COLUMNS.json")
            if os.path.exists(fj):
                jobs += [(a.root, it, pdfn[it], r["page"], "frk", r["psm"]) for r in json.load(open(fj))["pages"] if not r["kept"]]
            if os.path.exists(cj):
                jobs += [(a.root, it, pdfn[it], r["page"], "cols", "3") for r in json.load(open(cj)).get("round2", [])
                         if not r["kept"] and (r.get("psm3") or {}).get("words5")]
        def handle(res, resuming):
            item, n, kind, t, w5 = res
            if w5:
                CP.write_new(os.path.join(a.root, item, f"page-{n:04d}.{kind}-add.txt"), t, resuming)
            return (item, n, kind), {"item": item, "page": n, "kind": kind, "words5": w5, "filed": bool(w5)}
        rr, P = run_journaled(a, add_page, jobs, lambda j: (j[1], j[3], j[4]), "C7c.4 adds", handle)
        filed, recs = collections.Counter(r["kind"] for r in rr if r["filed"]), collections.defaultdict(list)
        for r in rr:
            recs[r["item"]].append({k: v for k, v in r.items() if k != "item"})
        for item, v in recs.items():
            json.dump({"mode": "second readings beside the chosen one (frk-add, cols-add)", "pages": sorted(v, key=lambda r: (r["page"], r["kind"]))},
                      open(os.path.join(a.root, item, "ADDS.json"), "w"), indent=1)
        line = f"adds: {len(jobs)} pages in {len(recs)} items · filed frk-add {filed['frk']} · cols-add {filed['cols']}"
        if P:
            P.finish(line)
        print(line)
        return
    if a.mode == "fraktur":
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        want = [l.rstrip("\n").split("\t")[:2] for l in open(a.list, encoding="utf-8") if l.strip()]
        jobs = []
        for it, pg in want:
            it = unicodedata.normalize("NFC", it); n = int(pg)
            if os.path.exists(os.path.join(a.root, it, "FRAKTUR.json")):
                sys.exit(f"exists: {it}/FRAKTUR.json")
            cur = current_pages(a.root, it).get(n)
            if it in pdfn and cur is not None:
                jobs.append((a.root, it, pdfn[it], n, cur))
        def handle(res, resuming):
            item, n, t, rec = res
            if rec["kept"]:
                CP.write_new(os.path.join(a.root, item, f"page-{n:04d}.frk.txt"), t, resuming)
            return (item, n), dict(rec, item=item)
        rr, P = run_journaled(a, fraktur_page, jobs, lambda j: (j[1], j[3]), "C7c.3 fraktur", handle)
        recs = collections.defaultdict(list)
        for r in rr:
            recs[r["item"]].append({k: v for k, v in r.items() if k != "item"})
        for item, v in recs.items():
            json.dump({"mode": "fraktur (frk+deu, psm 4 and 6, 400 ppi)", "pages": sorted(v, key=lambda r: r["page"])},
                      open(os.path.join(a.root, item, "FRAKTUR.json"), "w"), indent=1)
        line = f"fraktur: {len(jobs)} pages in {len(recs)} items · kept {sum(1 for r in rr if r['kept'])}"
        if P:
            P.finish(line)
        print(line)
        return
    if a.mode == "columns2":
        items = [unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))]
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        jobs, recs_all = [], {}
        for it in items:
            cj = os.path.join(a.root, it, "COLUMNS.json")
            if it not in pdfn:
                continue
            rec = json.load(open(cj)) if os.path.exists(cj) else {"mode": "columns (round 2 only)", "pages": []}
            recs_all[it] = rec
            if "round2" in rec:
                sys.exit(f"round 2 done already: {it}/COLUMNS.json")
            cur = current_pages(a.root, it); tried = {r["page"] for r in rec["pages"]}
            for r in rec["pages"]:
                if not r["kept"] and r["page"] in cur:
                    jobs.append((a.root, it, pdfn[it], r["page"], cur[r["page"]]))
            for n, t in cur.items():
                if n not in tried and not os.path.exists(os.path.join(a.root, it, f"page-{n:04d}.cols.txt")):
                    jobs.append((a.root, it, pdfn[it], n, t, "untried"))
        kept, out = collections.Counter(), collections.defaultdict(list)
        with fut.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            for item, n, t, rec in ex.map(round2_page, jobs):
                out[item].append(rec)
                if rec["kept"]:
                    p = os.path.join(a.root, item, f"page-{n:04d}.cols.txt")
                    if os.path.exists(p):
                        sys.exit(f"exists: {p}")
                    open(p, "w", encoding="utf-8").write(t); kept[rec["kept"]] += 1
        for item, rr in out.items():
            rec = recs_all[item]; rec["round2"] = sorted(rr, key=lambda r: r["page"])
            json.dump(rec, open(os.path.join(a.root, item, "COLUMNS.json"), "w"), indent=1)
        un = sum(1 for j in jobs if len(j) == 6)
        ku = sum(1 for rr in out.values() for r in rr if r.get("untried") and r["kept"])
        print(f"round 2: {len(jobs)} pages ({len(jobs) - un} refused in round 1, {un} untried) · kept psm3 {kept['psm3']} "
              f"({kept['psm3'] - ku} refused before, {ku} untried) · not kept {len(jobs) - sum(kept.values())}")
        return
    if a.mode == "columns":
        items = [unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))]
        pdfn = {unicodedata.normalize("NFC", k): v for k, v in pdfs.items()}
        jobs = []
        for it in items:
            if it not in pdfn:
                continue
            for n, t in current_pages(a.root, it).items():
                if cross_share(t) >= CROSS_MIN:
                    jobs.append((a.root, it, pdfn[it], n, t))
        for it in {j[1] for j in jobs}:
            if os.path.exists(os.path.join(a.root, it, "COLUMNS.json")):
                sys.exit(f"exists: {it}/COLUMNS.json")
        kept, recs = 0, collections.defaultdict(list)
        with fut.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            for item, n, t, rec in ex.map(columns_page, jobs):
                recs[item].append(rec)
                if rec["kept"]:
                    open(os.path.join(a.root, item, f"page-{n:04d}.cols.txt"), "w", encoding="utf-8").write(t); kept += 1
        for item, rr in recs.items():
            json.dump({"mode": "columns (psm 3, deu, 400 ppi)", "pages": sorted(rr, key=lambda r: r["page"])},
                      open(os.path.join(a.root, item, "COLUMNS.json"), "w"), indent=1)
        print(f"{len(jobs)} pages crossing columns in {len(recs)} items · psm 3 kept on {kept}")
        return
    if a.mode == "pages":
        want = [l.rstrip("\n").split("\t")[:2] for l in open(a.list, encoding="utf-8") if l.strip()]
        jobs = [(a.root, c, pdfs[c], int(p)) for c, p in want if c in pdfs]
        kept, recs = 0, collections.defaultdict(list)
        with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for item, n, (name, new, t) in ex.map(page_all_variants, jobs):
                old = score(current_pages(a.root, item).get(n, ""), lexname(item))
                keep = new is not None and (old is None or new > old)
                recs[item].append({"page": n, "variant": name, "new": new, "old": old, "kept": keep})
                if keep:
                    open(os.path.join(a.root, item, f"page-{n:04d}.reocr.txt"), "w", encoding="utf-8").write(t); kept += 1
        for item, rr in recs.items():
            json.dump({"mode": "pages (LOST pages)", "pages": rr}, open(os.path.join(a.root, item, "REOCR-PAGES.json"), "w"), indent=1)
        print(f"{len(jobs)} pages · re-read kept on {kept} · the rest for vision")
        return
    probe = json.load(open(a.probe)); jobs = []
    for r in probe:
        if r["gain"] < a.min_gain:
            continue
        spec = variants(r["item"])[r["best"]]
        for p in current_pages(a.root, r["item"]):
            jobs.append((a.root, r["item"], pdfs[r["item"]], p, spec, r["lexicon"]))
    kept = collections.Counter(); recs = collections.defaultdict(list)
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for item, n, t in ex.map(run_page, jobs, chunksize=2):
            ln = lexname(item); cur = current_pages(a.root, item).get(n, "")
            new, old = score(t, ln), score(cur, ln)
            keep = new is not None and (old is None or new > old)
            recs[item].append({"page": n, "new": new, "old": old, "kept": keep})
            p = os.path.join(a.root, item, f"page-{n:04d}.reocr.txt")
            if keep:
                open(p, "w", encoding="utf-8").write(t); kept[item] += 1
            elif os.path.exists(p):
                os.remove(p)
    for item, rr in recs.items():
        best = next(r for r in probe if r["item"] == item)
        json.dump({"variant": best["best"], "spec": list(variants(item)[best["best"]]), "pages": rr},
                  open(os.path.join(a.root, item, "REOCR.json"), "w"), indent=1)
    print(f"{len(recs)} items re-read · pages kept {sum(kept.values())} of {len(jobs)}")


if __name__ == "__main__":
    main()
