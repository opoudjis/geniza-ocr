#!/usr/bin/env python3
r"""ocr-g1-ink — GATE CHECK G1. Is a silent page blank, or did we fail to read it?

    tools/ocr-g1-ink.py --pdfs <list> --root <ocr root> --write G1-REPORT.md

THE ONLY CHECK THAT LOOKS AT THE IMAGE, AND THE ONLY ONE THAT CAN ANSWER THIS QUESTION.
A page we failed to read and a page with nothing on it produce **the same output: nothing**. And
«nothing» is also what an absence finding looks like. Three different facts — *the page was
blank*, *we could not read the page*, *the name is not in this volume* — with one appearance in
the text. No lexical measure, no quality score and no page count can separate them, because they
are identical in the only material those instruments see.

So this one ignores the text entirely. It renders the page and asks whether there is INK on it,
arranged in the horizontal runs that lines of type make. Ink with line structure and no words:
**we did not read it**. No ink: the silence is real and an absence finding over it stands.

TWO THRESHOLDS, NOT ONE. ÖNB and most library scans are PHOTOGRAPHS OF A BOOK ON A DARK
BOARD. A single Otsu split separates BOARD from PAGE, not ink from paper, and reports a clean
leaf as «91% ink» — which is what the first version of this tool did. Stage 1 finds the paper by
taking the bounding box of the bright region; stage 2 splits ink from paper INSIDE that box,
which is the only place the question means anything.

AND THE CLASS IT CANNOT DECIDE. «Ink, but no line structure» is a plate, a stamp, an ornamental
title page or a cover. That is the right answer — there was nothing for OCR to find — but it is
not the same as blank, and it is reported separately rather than folded into either verdict.

THE INK CACHE (2026-10-15; the editor, 2026-10-14 18:2x, judged inordinate a chain that spent 15 of its 20 minutes
here to re-read one page). Every run used to extract and measure every silent page of the corpus again,
though the measure depends only on the PAGE IMAGE. Now each page's `ink_of()` result is kept, per corpus, in
`<stem>.json` under the ink cache directory (`CACHE` below), keyed by the PDF's size and modification time: a changed
or replaced PDF drops its corpus's cache. Only pages not in the cache are extracted and measured. The verdict is
still made fresh every run, from the cached measure and the CURRENT text (a page re-read since keeps its ink and is
judged on its new lines). `--no-cache` measures everything again (and rewrites the cache).
WRITE-SET: `--write` and `--write`.json, as before; the cache files, one per corpus with a silent page.
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, statistics, collections
import concurrent.futures as fut
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr_page_images import page_images


def _otsu(hist, tot):
    best, thr, s_all, wB, sB = -1.0, 128, sum(i * hist[i] for i in range(256)), 0, 0
    for t in range(256):
        wB += hist[t]
        if wB == 0 or wB == tot:
            continue
        sB += t * hist[t]
        mB, mF = sB / wB, (s_all - sB) / (tot - wB)
        var = wB * (tot - wB) * (mB - mF) ** 2
        if var > best:
            best, thr = var, t
    return thr


def ink_of(path, maxdim=900):
    try:
        im = Image.open(path).convert("L")
    except Exception:
        return None
    if max(im.size) > maxdim:
        im.thumbnail((maxdim, maxdim))
    w, h = im.size
    px = list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())
    if not px:
        return None
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    t1 = _otsu(hist, len(px))                    # stage 1: board vs page
    cols = [x for x in range(w) if sum(1 for y in range(0, h, 4) if px[y * w + x] > t1) > (h / 4) * .5]
    rows = [y for y in range(h) if sum(1 for x in range(0, w, 4) if px[y * w + x] > t1) > (w / 4) * .5]
    if len(cols) < w * .15 or len(rows) < h * .15:
        return None
    im = im.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
    w, h = im.size
    px = list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())
    hist = [0] * 256
    for v in px:
        hist[v] += 1
    t2 = _otsu(hist, len(px))                    # stage 2: ink vs paper, inside the page
    bright = sum(hist[t2 + 1:])
    paper = sum(v * hist[v] for v in range(t2 + 1, 256)) / max(bright, 1)
    if paper - t2 < 25:                          # no real bimodality: clean paper …
        # … UNLESS there is real ink. FIXED 2026-09-28 (the final audit's *La Ondo de Esperanto* 1910.02): on grey,
        # speckled JPEG scans Otsu inside the page splits the PAPER's own tones (t2 = 207, paper 231, diff 23.9), and
        # a page 12% dark with print was called clean paper — so G1 could call a TEXT page «blank». Now: clean paper
        # only if under 0.5% of the page is truly dark (below mid-grey and below t1); otherwise the ink is measured
        # at the lower threshold.
        tdark = min(t1, 128)
        if sum(hist[:tdark + 1]) / len(px) < 0.005:
            return 0.0, 0.0, 0
        t2 = tdark
    ink = sum(hist[:t2 + 1]) / len(px)
    inked = [sum(1 for v in px[y * w:(y + 1) * w] if v <= t2) / max(w, 1) > 0.03 for y in range(h)]
    # LINES OF TYPE = bands of inked rows at least 2 px tall. Tightly set lines can merge into
    # one band; that only ever UNDER-counts type, so it can pass a page that has text, never an
    # empty one.
    bands, run = 0, 0
    for on in inked + [False]:
        if on:
            run += 1
        else:
            bands += run >= 2
            run = 0
    return ink, sum(inked) / max(h, 1), bands


CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources",
                     "geniza", "sources", "ocr-work", "g1-ink-cache.noindex")


def _pdf_key(pdf):
    st = os.stat(pdf)
    return f"{st.st_size}:{int(st.st_mtime)}"


def _cache_load(stem, pdf):
    f = os.path.join(CACHE, stem + ".json")
    try:
        c = json.load(open(f, encoding="utf-8"))
        if c.get("pdf") == pdf and c.get("key") == _pdf_key(pdf):
            return {int(k): (tuple(v) if v is not None else None) for k, v in c["ink"].items()}
    except Exception:
        pass
    return {}


def _cache_save(stem, pdf, ink):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, stem + ".json")
    tmp = f + ".tmp"
    json.dump({"pdf": pdf, "key": _pdf_key(pdf), "ink": {str(k): v for k, v in sorted(ink.items())}},
              open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, f)


def test_corpus(job):
    """G1 for one corpus. Top-level so it can run in its own PROCESS: `ink_of` is pure-Python
    pixel counting, and threads cannot run it in parallel (the interpreter lock) — the first
    all-corpus run crawled for 74 minutes on one file at a time (2026-09-26)."""
    stem, pdf, root, jobs, use_cache = job
    d = os.path.join(root, stem)
    if not os.path.isdir(d):
        return None
    pages = {}
    for f in sorted(glob.glob(os.path.join(d, "page-*.txt"))):
        # BASE pages only: the glob also matches the .psm4 / .hr readings of each page
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m:
            pages[int(m.group(1))] = os.path.getsize(f)
    if len(pages) < 3:
        return None
    med = statistics.median(pages.values())
    silent = [n for n, s in pages.items() if med and s < med * .25]
    if not silent:
        return None
    cached = _cache_load(stem, pdf) if use_cache else {}
    todo = [n for n in silent if n not in cached]
    work = tempfile.mkdtemp()
    try:
        # The image the conversion read, by the conversion's rule — not «the first image
        # extracted», which on a multi-image page is a fragment (fixed 2026-09-25).
        byn = page_images(pdf, work, jobs=jobs, pages=todo) if todo else {}
        # A BORN-DIGITAL page (its words stored as text) that also stores ONE small picture — a
        # logo, a photo — is taken by the rule above to BE that picture, so the ink test measured
        # a logo against a page of text and flagged it (G1 sort 2026-09-26: items 231, 358). The
        # texts were never harmed (1,421 of 1,424 such pages carry ≥ 80% of their stored words).
        # So HERE ONLY: a silent page with a text layer of ≥ 20 words is rendered whole. On a
        # scanned page with an OCR'd text layer, rendering gives back the same scan: no harm.
        for n in todo:
            tl = os.path.join(d, f"page-{n:04d}.tl.txt")
            if os.path.exists(tl) and len(open(tl, encoding="utf-8", errors="ignore").read().split()) >= 20:
                subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", str(n), "-l", str(n), pdf,
                                os.path.join(work, f"g{n:05d}")], capture_output=True)
                hit = glob.glob(os.path.join(work, f"g{n:05d}*.png"))
                if hit:
                    byn[n] = hit[0]
        # NOTE (2026-09-27): «untested» is NOT a missing image. It is ink_of() returning None because no
        # bright PAPER region was found (dark scans, photographs, white-on-dark covers): the ink test
        # cannot decide those pages. A render fallback added on a wrong diagnosis was removed the same day.
        # Lines of TEXT per page, from the COMBINED text — the mosaic is what gets accepted.
        text_lines = {}
        comb = d.rstrip("/") + ".txt"
        if os.path.exists(comb):
            parts = re.split(r"\n=== page (\d+) ===\n", "\n" + open(comb, encoding="utf-8",
                                                                     errors="ignore").read())
            for pn, tx in zip(parts[1::2], parts[2::2]):
                text_lines[int(pn)] = sum(1 for l in tx.splitlines()
                                          if len(re.findall(r"[^\W\d_]", l)) >= 3)
        blank = plate = unread = untested = 0
        worst = []; undecided = []; blanks = []   # blank pages RECORDED from 2026-09-28: a cleared verdict must be auditable
        def one(n):
            img = byn.get(n)
            return (n, ink_of(img)) if img else (n, None)
        measured = dict(cached)
        with fut.ThreadPoolExecutor(max_workers=jobs) as pool:
            for n, r in pool.map(one, todo):
                measured[n] = r
        if todo:
            _cache_save(stem, pdf, measured)
        for n in silent:
            r = measured.get(n)
            if r is None:
                untested += 1; undecided.append(n)
            elif r[0] < 0.010:
                blank += 1; blanks.append(n)
            elif r[2] >= 3 and text_lines.get(n, 0) < 0.5 * r[2]:
                # REFINED 2026-09-26 (on the editor's instruction to refine, then look). «Silent» means under a
                # quarter of the median text, NOT none — so «ink in line structure» flagged
                # every correctly-read half page: all 15 *Progreso* volumes «failed». Unread
                # now means FEWER THAN HALF as many lines of text as lines of type. Calibrated
                # on those 93 pages: 73 pass (short pages), 20 remain, 8 of them near-empty.
                unread += 1; worst.append((n, r[0], r[2]))
            else:
                plate += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"corpus": stem, "silent": len(silent), "measured": len(todo), "blank": blank, "plate": plate,
            "unread": unread, "untested": untested,
            "pages": [w[0] for w in sorted(worst)],      # ALL flagged pages (the report table shows 12)
            "untested_pages": sorted(undecided),          # pages the ink test could not decide (2026-09-27)
            "blank_pages": sorted(blanks)}                # pages it CLEARED as blank (2026-09-28)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--write", default=None)
    ap.add_argument("--jobs", type=int, default=4, help="threads per corpus")
    ap.add_argument("--files", type=int, default=12, help="corpora at once, as processes")
    ap.add_argument("--no-cache", action="store_true", help="measure every silent page again (rewrites the cache)")
    a = ap.parse_args()

    pdfs = {}
    for l in open(a.pdfs, encoding="utf-8"):
        p = l.strip()
        if p:
            pdfs[os.path.splitext(os.path.basename(p))[0]] = p

    rows, totals = [], collections.Counter()
    jobs_ = [(stem, pdf, a.root, a.jobs, not a.no_cache) for stem, pdf in sorted(pdfs.items())]
    with fut.ProcessPoolExecutor(max_workers=a.files) as pool:
        for r in pool.map(test_corpus, jobs_, chunksize=4):
            if not r:
                continue
            for k in ("silent", "measured", "blank", "plate", "unread", "untested"):
                totals[k] += r[k]
            rows.append(r)
            if r["unread"]:
                print(f"  ⚠ {r['corpus'][:44]:<46} {r['unread']} unread of {r['silent']} silent",
                      flush=True)

    print(f"\n{totals['silent']:,} silent pages tested across {len(rows)} corpora "
          f"({totals['measured']:,} measured now, {totals['silent'] - totals['measured']:,} from the ink cache)")
    print(f"  genuinely BLANK            {totals['blank']:>6,}")
    print(f"  plate, cover, or short page {totals['plate']:>5,}   ink, but text accounts for its lines")
    print(f"  ⚠ INK WITH LINE STRUCTURE  {totals['unread']:>6,}   ← text we did not read")
    print(f"  untestable                 {totals['untested']:>6,}")
    bad = [r for r in rows if r["unread"]]
    print(f"\n  ⇒ {len(bad)} corpora FAIL G1; {len(rows)-len(bad)} pass it.")
    if a.write:
        w = ["# G1 — dead pages: is a silent page blank, or did we fail to read it?\n",
             "**GENERATED by `tools/ocr-g1-ink.py`.** The only gate check that looks at the IMAGE.\n",
             f"{totals['silent']:,} silent pages across {len(rows)} corpora · "
             f"**{totals['unread']:,} carry typeset lines our text does not account for**.\n",
             "⚠ A corpus with a non-zero `unread` column FAILS G1, and **no absence finding over "
             "it is admissible** until those pages are read.\n",
             "| corpus | silent | blank | plate / short page | ⚠ unread | pages |", "|---|---:|---:|---:|---:|---|"]
        for r in sorted(rows, key=lambda x: -x["unread"]):
            w.append(f"| `{r['corpus'][:42]}` | {r['silent']} | {r['blank']} | {r['plate']} "
                     f"| {'**'+str(r['unread'])+'**' if r['unread'] else '0'} "
                     f"| {', '.join(map(str, r['pages'][:12])) + (' …' if len(r['pages'])>12 else '') if r['pages'] else ''} |")
        open(a.write, "w", encoding="utf-8").write("\n".join(w) + "\n")
        json.dump(rows, open(a.write + ".json", "w", encoding="utf-8"), ensure_ascii=False)
        print(f"wrote {a.write}")


if __name__ == "__main__":
    main()
