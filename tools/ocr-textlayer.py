#!/usr/bin/env python3
r"""ocr-textlayer — the PDF's OWN text layer, as one more reading of each page.

    tools/ocr-textlayer.py --pdfs <list> [--pdfs <list> …] --root <ocr root> [--jobs 12]

WHY (2026-09-26). 453 PDFs carry a real text layer on pages with no image (23,001 pages; 161
born-digital throughout — *Enciklopedio de Esperanto* 1933, BPEAPE, the BK congress documents),
and scanned PDFs from libraries often carry the library's own OCR under the image. The pipeline
rendered and OCR'd all of it and never looked at the text already there.

BUT IT IS NOT GROUND TRUTH — the editor ruled on 2026-09-26 that the PDFs' own existing text is OCR-derived
and already compromised, so just another image. A library's text layer is someone else's OCR, and
a born-digital font without a Unicode map mangles ĉ/ĝ/ŝ. So the text layer does NOT replace
anything: it is written as `page-NNNN.tl.txt` and COMPETES in `ocr-psm-adjudicate.py` under the
same rule as every other reading (entries → recognised words → psm 6 holds).

One `pdftotext` call per document, split on the form feed it puts between pages. A page whose layer
holds fewer than 20 non-space characters gets no file (an empty layer is not a reading).
Re-runnable: a page that already has `.tl.txt` is skipped.
"""
import os, re, sys, argparse, subprocess
import concurrent.futures as fut
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cupel_progress import write_new as _write   # run sheet rule 0 (2026-10-23): temp file then rename, so a run killed
                                                 # mid-write never leaves a half-written file that a restart would skip


def one(job):
    pdf, root = job
    stem = os.path.splitext(os.path.basename(pdf))[0]
    d = os.path.join(root, stem)
    if not os.path.isdir(d):
        return 0
    out = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf, "-"], capture_output=True,
                         text=True, errors="ignore").stdout
    n = 0
    for i, page in enumerate(out.split("\f"), 1):
        if len(re.sub(r"\s", "", page)) < 20:
            continue
        if not os.path.exists(os.path.join(d, f"page-{i:04d}.txt")):
            continue                 # no such page in the conversion (a trailing form feed)
        tl = os.path.join(d, f"page-{i:04d}.tl.txt")
        if os.path.exists(tl):
            continue
        _write(tl, page, True)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", action="append", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    pdfs = list(dict.fromkeys(l.strip() for L in a.pdfs for l in open(L, encoding="utf-8")
                              if l.strip()))
    with fut.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        counts = list(pool.map(one, [(p, a.root) for p in pdfs]))
    print(f"{len(pdfs)} PDFs · {sum(1 for c in counts if c)} with a text layer · "
          f"{sum(counts):,} page readings written (.tl.txt)", file=sys.stderr)


if __name__ == "__main__":
    main()
