#!/usr/bin/env python3
r"""ocr-russian-pages — find the pages that are Cyrillic misread as Latin, read them with the Russian
model, and decide PAGE BY PAGE whether the Russian reading replaces the chosen one.

    tools/ocr-russian-pages.py <root> --pdfs <list> [--jobs 12] [--dry-run]

WHY A SEPARATE TOOL, NOT `ocr-second-model.py --lang rus` (approved by the editor, 2026-09-26):
  - The second model is chosen per corpus by the gate's language detection, which reads the
    Esperanto OCR. Cyrillic read with the Esperanto model comes out as Latin letters, so it can
    never match a Russian word list: Russian corpora are never flagged. Detection must read the
    page with the Russian model first.
  - The second model MERGES word by word, keeping words its lists recognise. The Russian list
    (`ru.dic`) is post-1918 only; the venture's Russian-era material is pre-1918 (ѣ, і, ѳ, ѵ, final
    ъ). Even with the old letters folded to modern ones it recognises only 21–38% of real Russian
    words (probe of 44 pages, 2026-09-26). A merge would leave Latin junk wherever a Russian word is
    not in the list. So a Russian page takes the Russian reading WHOLE.

THE PAGE RULE:
  candidate — the chosen reading has ≥ 30 words (3+ letters), under 30% of them are recognised by
              any list we hold (Esperanto, Ido, Occidental and ten others), and under 30% are
              already Cyrillic (a page read from its own Cyrillic text layer is left alone);
  accept    — the Russian reading, read from the same page image, is ≥ 90% Cyrillic words, and
              ≥ 15% of them are in the Russian list after folding pre-1918 spelling
              (ѣ→е, і→и, ѳ→ф, ѵ→и, final ъ dropped). The probe separated real Russian (20–38%) from
              non-Russian pages forced through the Russian model (6–9%).

The Russian list only DETECTS here. It never SCORES: the editor's ruling of 2026-09-23 stands
(pre-reform Russian is declared unscoreable; `tools/lexicons/hunspell/SOURCE.md`).

Writes, per corpus: `page-NNNN.rus.txt` (the Russian reading) and `RUSSIAN.json` (every candidate
page, its counts, and its verdict). `ocr-rebuild-combined.py` puts an ACCEPTED page's Russian reading
into the combined text — once a blind look has confirmed the rule.

NOT COVERED: mixed pages (Esperanto with Russian passages). The Esperanto reading recognises too
much of such a page for it to be a candidate, so its Russian stays garbled.
"""
import os, re, sys, json, glob, argparse, subprocess, tempfile, shutil, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_text_languages as TL   # the language table (2026-10-03)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images

LISTS = ("esperanto", "ido", "occidental", "french", "german", "italian", "spanish", "catalan",
         "dutch", "danish", "swedish", "czech", "polish")
W = re.compile(r"[^\W\d_]{3,}")
CYR = re.compile(r"[а-яёѣіѳѵ]")
FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
CAND_HIT, CAND_CYR, MIN_WORDS = 0.30, 0.30, 30
ACC_CYR, ACC_RU = 0.90, 0.15


def load(name):
    return {w.strip().lower() for w in open(os.path.join(HERE, "lexicons", name + ".txt"),
                                            encoding="utf-8", errors="ignore") if w.strip()}


def fold(w):
    return re.sub(r"ъ$", "", w.translate(FOLD))


def pages_of(comb):
    t = open(comb, encoding="utf-8", errors="ignore").read()
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def candidates(text, known):
    toks = [m.group(0).lower() for m in W.finditer(text)]
    if len(toks) < MIN_WORDS:
        return None
    hit = sum(1 for t in toks if t in known) / len(toks)
    cyr = sum(1 for t in toks if CYR.search(t)) / len(toks)
    return (hit, cyr, len(toks)) if hit < CAND_HIT and cyr < CAND_CYR else None


def do_corpus(job):
    stem, pdf, root, pages, ru = job
    d = os.path.join(root, stem)
    work = tempfile.mkdtemp()
    out = []
    try:
        imgs = page_images(pdf, work, jobs=4, pages=sorted(pages))
        for n in sorted(pages):
            img = imgs.get(n)
            if not img:
                out.append({"page": n, **pages[n], "verdict": "no image"}); continue
            txt = subprocess.run(["tesseract", img, "-", "-l", "rus", "--psm", "6"],
                                 capture_output=True, text=True).stdout
            toks = [m.group(0).lower() for m in W.finditer(txt)]
            cyr = [t for t in toks if CYR.search(t)]
            cyr_share = len(cyr) / len(toks) if toks else 0
            ru_share = sum(1 for t in cyr if fold(t) in ru) / len(cyr) if cyr else 0
            ok = cyr_share >= ACC_CYR and ru_share >= ACC_RU
            # A FORCED page (--all-pages) that the candidate rule would not have chosen is MIXED: the
            # Russian model turns its Esperanto into Cyrillic too, so it can pass the accept rule (104 of 160
            # did, 2026-09-28) — and an accepted page is swapped WHOLE to Russian by the rebuild, losing the
            # Esperanto. Such a page is never «accept»: its Russian reading only feeds the segregation tools.
            if ok and not (pages[n].get("hit_before", 1) < CAND_HIT and pages[n].get("cyrillic_before", 1) < CAND_CYR):
                ok = None
            open(os.path.join(d, f"page-{n:04d}.rus.txt"), "w", encoding="utf-8").write(txt)
            out.append({"page": n, **pages[n], "rus_words": len(toks),
                        "rus_cyrillic": round(cyr_share, 3), "rus_recognised_folded": round(ru_share, 3),
                        "verdict": "accept" if ok else ("mixed (forced; never swapped)" if ok is None else "reject")})
        json.dump({"rule": {"candidate": f"hit<{CAND_HIT}, cyrillic<{CAND_CYR}, words>={MIN_WORDS}",
                            "accept": f"rus cyrillic>={ACC_CYR}, folded recognised>={ACC_RU}"},
                   "pages": out}, open(os.path.join(d, "RUSSIAN.json"), "w", encoding="utf-8"), indent=1)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return stem, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true", help="list candidates only; read nothing")
    ap.add_argument("--all-pages", default=None,
                    help="=a,b,c: EVERY page (of 30+ words) of these items is read with the Russian model — the MIXED "
                         "pages the candidate rule cannot see (the editor approved the suggested fix, 2026-09-28: Kovno "
                         "Esperanto, Ruslanda Esperantisto, …). The accept rule is unchanged, so a mixed page is "
                         "never swapped whole; its Russian reading feeds ocr-layout-mixed / ocr-garbage-filter.")
    a = ap.parse_args()
    force = set(a.all_pages.lstrip("=").split(",")) if a.all_pages else set()
    known = set()
    for n in LISTS:
        known |= load(n)
    ru = load("russian_post1918")
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip()
            for l in open(a.pdfs) if l.strip()}
    jobs = []
    for comb in sorted(glob.glob(os.path.join(a.root, "*.txt"))):
        stem = os.path.basename(comb)[:-4]
        if stem not in pdfs or not os.path.isdir(os.path.join(a.root, stem)):
            continue
        if force and stem not in force:
            continue
        # THE LANGUAGE TABLE FILTERS (2026-10-03): the Russian model reads only texts the table lists with a Cyrillic
        # language. Not in the table → refused: declare the item's languages (DECLARED in ocr-text-languages-table.py)
        # and rebuild the table first (the 28 Sep chain read 220 items by script detection alone).
        cy = TL.cyrillic(stem)
        if cy is None:
            sys.exit(f"refusing: {stem} is not in the language table {os.path.basename(TL.path())}: declare its "
                     "languages and rebuild the table first")
        if not cy:
            print(f"  skip {stem}: the language table lists no Cyrillic language"); continue
        cand = {}
        for n, tx in pages_of(comb).items():
            # the candidate test reads the page's OWN Esperanto reading where it exists, not the combined text: once a
            # rebuild has swapped an accepted page whole to Russian, the combined text no longer looks like Esperanto
            # with Cyrillic junk, and a re-run demoted 1,853 accepted pages to «mixed» (cupel batch 2, 2026-10-03; R9)
            own = os.path.join(a.root, stem, f"page-{n:04d}.txt")
            if os.path.exists(own):
                tx = open(own, encoding="utf-8", errors="ignore").read()
            c = candidates(tx, known)
            if stem in force and not c:
                toks = [m.group(0).lower() for m in W.finditer(tx)]
                if len(toks) >= MIN_WORDS:
                    c = (sum(1 for t in toks if t in known) / len(toks), sum(1 for t in toks if CYR.search(t)) / len(toks), len(toks))
            if c:
                cand[n] = {"hit_before": round(c[0], 3), "cyrillic_before": round(c[1], 3), "words_before": c[2]}
        if cand:
            jobs.append((stem, pdfs[stem], a.root, cand, ru))
    print(f"{sum(len(j[3]) for j in jobs)} candidate pages in {len(jobs)} corpora", flush=True)
    if a.dry_run:
        return
    tally = collections.Counter()
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for stem, out in ex.map(do_corpus, jobs):
            for r in out:
                tally[r["verdict"]] += 1
    print(" · ".join(f"{k} {v}" for k, v in tally.most_common()))


if __name__ == "__main__":
    main()
