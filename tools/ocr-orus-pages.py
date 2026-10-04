#!/usr/bin/env python3
r"""ocr-orus-pages — read every page that has a Russian reading again with the PRE-REFORM model `orus`.

    tools/ocr-orus-pages.py <root> --pdfs <list> [--jobs 12] [--only =a,b,c]

WHY (the editor's ruling of 2026-09-28 10:47 adopting the old-letter rule). A blind look of 40 pages (an internal
record, 2026-09-28, not published) found `orus` (pre-reform Russian, fine-tuned on *Iskra* 1900–05; provenance `tools/tessdata-extra/SOURCE.md`) better
than the stock `rus` on all 36 pre-reform pages, `rus` better on modern/Soviet Russian. The rule that reproduced the
judges 39/39: use the `orus` reading where it has >= 10 words with ѣ/і/ѳ/ѵ, else the `rus` reading — applied by
`tools/ocr_russian_reading.py`, never by overwriting.
WHAT. For every `page-NNNN.rus.txt`, the same page image (the route `ocr-russian-pages.py` uses) is read with
`tesseract -l orus --psm 6` → `page-NNNN.orus.txt` beside it. Pages already read are skipped. Writes nothing else.
"""
import os, re, sys, glob, argparse, subprocess, tempfile, shutil, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images


def do_corpus(job):
    stem, pdf, root, pages = job
    d = os.path.join(root, stem); work = tempfile.mkdtemp(); n_done = 0
    try:
        imgs = page_images(pdf, work, jobs=2, pages=sorted(pages))
        for n in sorted(pages):
            img = imgs.get(n)
            if not img:
                continue
            txt = subprocess.run(["tesseract", img, "-", "-l", "orus", "--psm", "6"], capture_output=True, text=True).stdout
            open(os.path.join(d, f"page-{n:04d}.orus.txt"), "w", encoding="utf-8").write(txt); n_done += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return stem, n_done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--jobs", type=int, default=12); ap.add_argument("--only", default=None)
    a = ap.parse_args()
    only = set(a.only.lstrip("=").split(",")) if a.only else None
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    todo = collections.defaultdict(set)
    for f in glob.glob(os.path.join(a.root, "*", "page-*.rus.txt")):
        stem = os.path.basename(os.path.dirname(f))
        if stem not in pdfs or (only and stem not in only):
            continue
        n = int(re.search(r"page-(\d+)\.rus\.txt", f).group(1))
        if not os.path.exists(f[:-len(".rus.txt")] + ".orus.txt"):
            todo[stem].add(n)
    jobs = [(s, pdfs[s], a.root, p) for s, p in todo.items()]
    print(f"{sum(len(p) for p in todo.values())} pages in {len(jobs)} items to read with orus", flush=True)
    done = 0
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for stem, n in ex.map(do_corpus, jobs):
            done += n
    print(f"read {done} pages with orus")


if __name__ == "__main__":
    main()
