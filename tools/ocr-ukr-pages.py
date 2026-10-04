#!/usr/bin/env python3
r"""ocr-ukr-pages — read the SCANNED pages of the language table's Ukrainian texts with Tesseract's Ukrainian model.

    tools/ocr-ukr-pages.py <root> --pdfs <PDF list> [--jobs 6] [--dry]
    e.g. tools/ocr-ukr-pages.py published/heterophony-resources/geniza/sources/ocr-rendersearch \
         --pdfs published/heterophony-resources/geniza/sources/OCR-PDF-LIST-2026-10-03-cupel2.txt

WHY (the editor judged option (2) needed on 2026-10-03, and approved using the reading in the Cyrillic search file). The
Russian model is the wrong reader for Ukrainian (є ї ґ, and і is an ordinary Ukrainian letter: the editor noted that
Ukrainian has both і, the "decimal i", and и, the "octal i", so і is not a sign of pre-reform spelling). WHICH TEXTS: those the language table
(`tools/ocr_text_languages.py`) lists with Ukrainian — licensed, not cited. WHICH PAGES: only those whose preferred
reading is NOT the born-digital text layer (a born-digital layer already holds the printed Ukrainian). On 3 Oct that is
*ukraina* (the Ido grammar for Ukrainians, 23 scanned pages), *Ukraina Stelo* 2017 (3), *Studia Slavica* 2017 (67,
its non-born-digital pages). Bulgarian: no text prints it as text (both Bulgaria books cite it), so no `bul` pass.
HOW: the page image the conversion read (`ocr_page_images.page_images`), `tesseract -l ukr --psm 6`.
CONSUMER: `tools/ocr-rus-companion.py` writes the reading beside the Russian ones in the Cyrillic search file.
WRITE-SET: `<item>/page-NNNN.ukr.txt` only, never over an existing one.
"""
import os, re, sys, argparse, tempfile, subprocess
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_text_languages as TL
from ocr_page_images import page_images


def scanned_pages(d):
    # a NEW item (cupel, before its first chain) has no PREFERRED.tsv yet: it is a scan, so every page of it (2026-10-04,
    # the W3 review: RUNBOOK.md runs this before the first chain, beside the forced Russian reading)
    if not os.path.exists(os.path.join(d, "PREFERRED.tsv")):
        return sorted(int(m.group(1)) for m in (re.fullmatch(r"page-(\d{4})\.txt", f) for f in os.listdir(d)) if m)
    out = []
    for l in open(os.path.join(d, "PREFERRED.tsv"), encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if f and f[0].isdigit() and not f[1].startswith("tl-born"):
            out.append(int(f[0]))
    return out


def read(job):
    img, out = job
    r = subprocess.run(["tesseract", img, "stdout", "-l", "ukr", "--psm", "6"], capture_output=True)
    open(out, "w", encoding="utf-8").write(r.stdout.decode("utf-8", errors="replace"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    total = 0
    for item in sorted(os.listdir(a.root)):
        d = os.path.join(a.root, item)
        # an item folder with page readings — a NEW item has no PREFERRED.tsv before its first chain (fixed 2026-10-04 03:2x:
        # the cold dry run found this loop still skipped such items, so the earlier fix in scanned_pages never ran)
        if not (os.path.isfile(os.path.join(d, "PREFERRED.tsv")) or os.path.isfile(os.path.join(d, "page-0001.txt"))) \
                or "ukrainian" not in (TL.cyrillic(item) or set()):
            continue
        want = [p for p in scanned_pages(d) if not os.path.exists(os.path.join(d, f"page-{p:04d}.ukr.txt"))]
        print(f"  {item}: {len(want)} scanned page(s) to read with ukr")
        total += len(want)
        if a.dry or not want:
            continue
        with tempfile.TemporaryDirectory() as work:
            imgs = page_images(pdfs[item], work, jobs=a.jobs, pages=want)
            jobs = [(imgs[p], os.path.join(d, f"page-{p:04d}.ukr.txt")) for p in want if p in imgs]
            with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
                list(ex.map(read, jobs))
    print(f"{total} page(s){' (dry run)' if a.dry else ' read'} · table {os.path.basename(TL.path())}")


if __name__ == "__main__":
    main()
