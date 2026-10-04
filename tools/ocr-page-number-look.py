#!/usr/bin/env python3
r"""ocr-page-number-look — Kapis's method: crop the page-number strips and have them READ BY VISION, not Tesseract.

    tools/ocr-page-number-look.py build --seq <OCR-PAGE-SEQUENCE-….tsv> --pdfs <list> --out <dir> [--what leads]
    tools/ocr-page-number-look.py judge --out <dir> --returns <file>      # compare the numbers read with scan order

WHY (a method suggested by Kapis of BitArkivo, 2026-09-29 00:03: crop out the part of the page that shows the page
numbers, and read only that by LLM vision, not by Tesseract; editor 00:49: the leads looked at now, then periodicals'
edges). The page-sequence
check (`ocr-page-sequence.py`) reads page numbers from the OCR, and where the OCR misread or dropped them it can only
flag a LEAD or leave a stretch unverified. A vision read of just the head and foot strip of each page settles it.
BUILD (--what leads): for every GAP, the scan pages from the last well-numbered page before it to the first after it;
for every JOIN, the last two pages of the issue and the first two of the next. Each page becomes ONE image: its top
and bottom strips (14% each, the whole width), stacked, from a 110-dpi render (which honours /Rotate). Batches of
about 24 strips. The checker is told only that the strips are consecutive scanned pages and asked to read the printed
page number on each; it is NOT told what gap is suspected (blind).
JUDGE: reads the checker's table (| NNN | printed number or NONE |) and, per lead, says whether the printed numbers
of the pages either side leave a gap: CONFIRMED (numbers read, and they skip), REFUTED (numbers run on), UNREADABLE.
"""
import os, re, sys, glob, argparse, subprocess, tempfile, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))


def leads(seq):
    out = []   # (lead id, corpus, [scan pages], kind, detail)
    items = {}
    for l in list(open(seq, encoding="utf-8"))[1:]:
        f = l.rstrip("\n").split("\t")
        items[f[0]] = f
    for c, f in items.items():
        ev = f[7]
        for m in re.finditer(r"GAP (\d+) page\(s\) missing between printed (\d+) and (\d+) \(scan (\d+)–(\d+)\)", ev):
            if f[1] != "GAP":
                continue
            a, b = int(m.group(4)), int(m.group(5))
            pages = list(range(a, b + 1)) if b - a <= 5 else [a, a + 1, b - 1, b]
            out.append((f"G{len(out)+1:03d}", [(c, p) for p in pages], "GAP", f"{m.group(1)} missing between printed {m.group(2)} and {m.group(3)}"))
        for m in re.finditer(r"JOIN printed (\d+)–(\d+) missing before (\S.*?)(?: · |$)", ev):
            nxt = m.group(3).strip()
            last = int(f[2])
            pages = [(c, last - 1), (c, last), (nxt, 1), (nxt, 2)]
            out.append((f"J{len(out)+1:03d}", pages, "JOIN", f"printed {m.group(1)}–{m.group(2)} missing before {nxt}"))
    return out


def strip_image(pdf, p, dst, work):
    from PIL import Image
    b = os.path.join(work, f"s{p:05d}")
    subprocess.run(["pdftoppm", "-r", "110", "-png", "-singlefile", "-f", str(p), "-l", str(p), pdf, b], capture_output=True)
    if not os.path.exists(b + ".png"):
        return False
    im = Image.open(b + ".png"); w, h = im.size; k = int(h * 0.14)
    top, bot = im.crop((0, 0, w, k)), im.crop((0, h - k, w, h))
    out = Image.new("RGB", (w, 2 * k + 12), "white"); out.paste(top, (0, 0)); out.paste(bot, (0, k + 12))
    out.save(dst); return True


def build(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ocr_page_images as OPI
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    L = leads(a.seq)
    os.makedirs(a.out, exist_ok=True)
    key, n, work = [], 0, tempfile.mkdtemp()
    try:
        for lid, pages, kind, detail in L:
            for c, p in pages:
                if c not in pdfs or p < 1:
                    continue
                n += 1; b = f"b{(n - 1) // 24 + 1:02d}"; os.makedirs(os.path.join(a.out, b), exist_ok=True)
                nn = f"{n:03d}"
                if strip_image(pdfs[c], p, os.path.join(a.out, b, nn + ".png"), work):
                    key.append(f"{nn}\t{b}\t{lid}\t{kind}\t{c}\t{p}\t{detail}")
                # KEEP THE PAGE IMAGE (the editor ruled 2026-10-04 13:2x that the images of these PDFs be kept too,
                # since they would otherwise have to be re-extracted if something later went wrong): the strip is cut from a 110 dpi
                # render made here and thrown away; the conversion's own image of the page goes into the page-image
                # cache (`ocr_page_images.py`; a no-op where it is cached already, or below the cache's disk guard).
                OPI.page_images(pdfs[c], work, jobs=1, pages=[p])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    open(os.path.join(a.out, "KEY.tsv"), "w").write("\n".join(key) + "\n")
    print(f"{len(L)} leads · {len(key)} strips · batches {len({k.split(chr(9))[1] for k in key})}")


def judge(a):
    key = [l.rstrip("\n").split("\t") for l in open(os.path.join(a.out, "KEY.tsv")) if l.strip()]
    got = {}
    for l in open(a.returns, encoding="utf-8"):
        m = re.match(r"\|\s*(\d{3})\s*\|\s*([^|]*?)\s*\|", l)
        if m:
            cell = re.sub(r"\(or \d+\)", "", m.group(2))          # «128 (or 123)»: take the reader's first choice
            v = re.findall(r"(?<![\dA-Za-z])\d{1,4}(?![\dA-Za-z])", cell); got[m.group(1)] = [int(x) for x in v]
    by = collections.defaultdict(list)
    for k in key:
        by[k[2]].append(k)
    res = collections.Counter(); lines = []
    for lid, ks in sorted(by.items()):
        kind, detail = ks[0][3], ks[0][6]
        seq = [(k[4], int(k[5]), got.get(k[0], [])) for k in ks]
        # the pages' printed numbers in scan order; a lead is REFUTED if consecutive pages of one item carry numbers
        # that run on (n, n+1) across the suspected gap, CONFIRMED if the numbers either side skip.
        # A page may print two numbers (volume and issue page: «58 / — 14 —»). Two consecutive read pages RUN ON if
        # ANY number of the first and ANY of the second differ by exactly the scan step; they SKIP if none runs on and
        # some pair steps ahead by 1–10 more than the scan step. Pages with no number (NONE, roman) are passed over.
        known = [(c, p, nums) for c, p, nums in seq if nums]
        verdict = "UNREADABLE"
        if len(known) >= 2:
            steps = []
            lastp = {}
            for c, p, _ in seq:
                lastp[c] = max(lastp.get(c, 0), p)
            for (c1, p1, n1), (c2, p2, n2) in zip(known, known[1:]):
                # across an issue boundary the step counts every scan page between the two READ pages: the rest of
                # the first issue after p1, and the second issue's pages up to p2 (its unnumbered masthead included)
                step = (p2 - p1) if c1 == c2 else (lastp[c1] - p1) + p2
                diffs = {b - a - step for a in n1 for b in n2}
                steps.append("run" if 0 in diffs else "skip" if any(1 <= d <= 10 for d in diffs) else "odd")
            # the verdict needs a tested pair that SPANS the suspected place: for a JOIN a pair across the two issues;
            # for a GAP a read page among the lead's first two AND one among its last two
            order = [(k[4], int(k[5])) for k in ks]
            kn = {(c, p) for c, p, _ in known}
            spans = (any(a[0] != b[0] for a, b in zip(known, known[1:])) if kind == "JOIN" else
                     bool(kn & set(order[:2])) and bool(kn & set(order[-2:])))
            verdict = ("UNREADABLE" if not spans else
                       "CONFIRMED" if "skip" in steps and "odd" not in steps else
                       "REFUTED" if all(s == "run" for s in steps) else "IRREGULAR")
        reads = [(c, p, "/".join(map(str, nums)) or "NONE") for c, p, nums in seq]
        res[verdict] += 1
        lines.append(f"| {lid} | {kind} | {ks[0][4]} | {detail} | {' '.join(f'{p}:{n}' for _, p, n in reads)} | {verdict} |")
    print("| lead | kind | item | suspected | scan:printed as read | verdict |\n|---|---|---|---|---|---|")
    print("\n".join(lines))
    print("\n" + " · ".join(f"{k} {v}" for k, v in res.items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("build", "judge"))
    ap.add_argument("--seq"); ap.add_argument("--pdfs"); ap.add_argument("--out", required=True)
    ap.add_argument("--what", default="leads"); ap.add_argument("--returns")
    a = ap.parse_args()
    build(a) if a.mode == "build" else judge(a)
