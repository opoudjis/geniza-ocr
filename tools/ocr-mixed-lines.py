#!/usr/bin/env python3
r"""ocr-mixed-lines — MIXED Russian + Esperanto pages, line by line, in both directions.

    tools/ocr-mixed-lines.py <root> --pdfs <list> [--jobs 12] [--rule gated|share|count]

WHY (2026-09-26, approved by the editor). `ocr-russian-pages.py` swaps a page WHOLE to the Russian reading.
On a mixed page that costs the Esperanto parts (blind look: a Kovno masthead and an Esperanto verse
came out as Cyrillic), and a mixed page that was NOT swapped keeps its Russian lines as Latin-letter
junk (10 of the 16 non-GOOD pages among the still-failing corpora in the auxlang look).

HOW. Two readings of the SAME image in the SAME mode (psm 6): the base Esperanto reading already on
disk (`page-NNNN.txt`, stage 1) and the Russian one (`page-NNNN.rus.txt`, made here where missing,
through the same image rule). Probe, 22 mixed pages: all 22 had exactly the same line count. For each
line the Russian line is taken if it has MORE recognised Russian words (pre-1918 letters folded:
ѣ→е, і→и, ѳ→ф, ѵ→и, final ъ dropped) than the Esperanto line has words recognised by our Latin-script
lists; otherwise the Esperanto line stays. A page whose two readings do not have the same number of
lines is left alone (`aligned: false`).

The Russian list only DETECTS (it recognises ~1 in 4 pre-1918 words; the editor's 2026-09-23 ruling
that pre-reform Russian is unscoreable stands).

RULE «share» (the default since 2026-09-27, the editor's choice of option a). The first rule above («count», kept as
`--rule count`) FAILED its blind look (an internal record, 2026-09-27, not published: current text better 29, line by
line 8, same 7; Cyrillic lines never GOOD): Latin-letter junk from Cyrillic hits the seven Latin lists
often enough to out-count a Russian list that misses pre-1918 words. Rule «share» takes the Russian
line when the Russian reading of the line is >= 60% Cyrillic letters AND under half of the Esperanto
line's 3+-letter words are in the Latin lists (lines with 2+ such words). Measured over the 249,135
such lines: the share is two-humped with a trough at 0.3-0.5 (9,570 and 8,588 lines against 22,348
at 0.5-0.6 and 75,792 at 0.9-1.0). The Russian list is no use as a second test (29,304 of those
75,792 well-recognised Esperanto lines have a «recognised» Russian word in their Russian reading).
Lines with fewer than 2 such words (headings, numbers, fragments) follow the nearest judged line
above, else below, else stay Esperanto.

RULE «gated» (the default since 2026-09-27, the editor's choice of option i; «share» kept as `--rule share`). «share»
improved but did not clearly pass its blind look (an internal record, 2026-09-27, not published: line by line 23,
current 15, same 6; Cyrillic GOOD 17 vs 11, Latin GOOD 8 vs 30): the Russian model writes Cyrillic for
ANY text, so on poorly read Esperanto and Ido pages with no Russian at all it took lines as Russian.
«gated» first asks whether the PAGE has Russian: at least 0.14 of the 3+-letter words of the page's
whole Russian reading must be in the Russian list (folded); below that, no line is taken. Measured
on both looks' 88 pages: 0.04-0.20 on the 10 without Cyrillic (9 under 0.14), 0.04-0.46 on the 78
with Cyrillic (73 at 0.14 or over). Then «share» decides line by line.

Writes per corpus: `page-NNNN.mixed.txt` for every aligned page that takes at least one Russian line,
and `MIXED.json` (per page: lines, Russian lines taken, recognised words before and after).
Scope: corpora with a `RUSSIAN.json` (i.e. with at least one Russian candidate page).
"""
import os, re, sys, json, glob, argparse, subprocess, tempfile, shutil, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images

LATIN = ("esperanto", "ido", "occidental", "french", "german", "polish", "czech")
W = re.compile(r"[^\W\d_]{3,}")
CYR = re.compile(r"[а-яёѣіѳѵ]")
FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
_L = {}


def lists():
    if not _L:
        lat = set()
        for n in LATIN:
            lat |= {w.strip().lower() for w in open(os.path.join(HERE, "lexicons", n + ".txt"),
                                                    encoding="utf-8", errors="ignore") if w.strip()}
        _L["lat"] = lat
        _L["ru"] = {w.strip().lower() for w in open(os.path.join(HERE, "lexicons", "russian_post1918.txt"),
                                                    encoding="utf-8") if w.strip()}
    return _L["lat"], _L["ru"]


def lat_score(line, lat):
    return sum(1 for m in W.finditer(line) if m.group(0).lower() in lat)


def ru_score(line, ru):
    return sum(1 for m in W.finditer(line)
               if CYR.search(m.group(0).lower()) and re.sub(r"ъ$", "", m.group(0).lower().translate(FOLD)) in ru)


LET = re.compile(r"[^\W\d_]")


def cyr_share(line):
    letters = LET.findall(line)
    return sum(1 for c in letters if CYR.search(c.lower())) / len(letters) if letters else 0


def pick_share(el, rl, lat):
    """Rule «share»: None = too short to judge, then filled from the nearest judged line."""
    pick = []
    for a, b in zip(el, rl):
        ws = [m.group(0).lower() for m in W.finditer(a)]
        if len(ws) < 2:
            pick.append(None)
        else:
            pick.append(cyr_share(b) >= 0.6 and sum(w in lat for w in ws) / len(ws) < 0.5)
    for i in range(len(pick)):
        if pick[i] is None:
            near = [pick[j] for j in range(i - 1, -1, -1) if pick[j] is not None][:1] or \
                   [pick[j] for j in range(i + 1, len(pick)) if pick[j] is not None][:1] or [False]
            pick[i] = near[0]
    return pick


def do_corpus(job):
    stem, pdf, root, rule = job
    lat, ru = lists()
    d = os.path.join(root, stem)
    base = {}
    for f in glob.glob(os.path.join(d, "page-*.txt")):
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m:
            base[int(m.group(1))] = f
    need = [n for n in base if not os.path.exists(os.path.join(d, f"page-{n:04d}.rus.txt"))]
    work = tempfile.mkdtemp()
    try:
        if need:
            imgs = page_images(pdf, work, jobs=4, pages=sorted(need))
            for n in need:
                if imgs.get(n):
                    t = subprocess.run(["tesseract", imgs[n], "-", "-l", "rus", "--psm", "6"],
                                       capture_output=True, text=True).stdout
                    open(os.path.join(d, f"page-{n:04d}.rus.txt"), "w", encoding="utf-8").write(t)
        out = []
        for n in sorted(base):
            rp = os.path.join(d, f"page-{n:04d}.rus.txt")
            if not os.path.exists(rp):
                continue
            el = [l for l in open(base[n], encoding="utf-8", errors="ignore").read().split("\n") if l.strip()]
            rl = [l for l in open(rp, encoding="utf-8", errors="ignore").read().split("\n") if l.strip()]
            if len(el) != len(rl):
                out.append({"page": n, "aligned": False, "lines": [len(el), len(rl)]}); continue
            if rule == "count":
                pick = [ru_score(b, ru) > lat_score(a, lat) for a, b in zip(el, rl)]
            else:
                pick = pick_share(el, rl, lat)
                if rule == "gated":
                    ws = [m.group(0) for m in W.finditer("\n".join(rl))]
                    if not ws or ru_score("\n".join(rl), ru) / len(ws) < 0.14:
                        pick = [False] * len(pick)
            k = sum(pick)
            rec_eo = sum(lat_score(a, lat) for a in el)
            rec_ru = sum(ru_score(b, ru) for b in rl)
            rec_mx = sum(ru_score(b, ru) if p else lat_score(a, lat) for a, b, p in zip(el, rl, pick))
            mp = os.path.join(d, f"page-{n:04d}.mixed.txt")
            if k:
                open(mp, "w", encoding="utf-8").write(
                    "\n".join(b if p else a for a, b, p in zip(el, rl, pick)) + "\n")
            elif os.path.exists(mp):
                os.remove(mp)  # left by an earlier rule
            out.append({"page": n, "aligned": True, "lines": len(el), "ru_lines": k,
                        "recognised_eo": rec_eo, "recognised_ru": rec_ru, "recognised_mixed": rec_mx})
        json.dump({"rule": "count — per line: Russian if more recognised Russian (folded) words than recognised "
                           "Latin-list words; aligned pages only" if rule == "count" else
                           ("gated — only on pages whose Russian reading has >= 0.14 of its 3+-letter words in the "
                            "Russian list; then " if rule == "gated" else "") + "share — per line: Russian if the Russian reading is >= 60% Cyrillic and under half "
                           "of the Esperanto line's 3+-letter words are in the Latin lists; lines with < 2 such "
                           "words follow the nearest judged line; aligned pages only", "pages": out},
                  open(os.path.join(d, "MIXED.json"), "w", encoding="utf-8"), indent=1)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return stem, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--rule", choices=("gated", "share", "count"), default="gated")
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    jobs = [(os.path.basename(os.path.dirname(f)), pdfs[os.path.basename(os.path.dirname(f))], a.root, a.rule)
            for f in sorted(glob.glob(os.path.join(a.root, "*", "RUSSIAN.json")))
            if os.path.basename(os.path.dirname(f)) in pdfs]
    print(f"{len(jobs)} corpora in scope", flush=True)
    t = collections.Counter()
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for stem, out in ex.map(do_corpus, jobs):
            for r in out:
                t["pages"] += 1
                if not r["aligned"]:
                    t["not aligned"] += 1
                elif r["ru_lines"] >= 3:
                    t["3+ Russian lines"] += 1
                elif r["ru_lines"]:
                    t["1-2 Russian lines"] += 1
                else:
                    t["no Russian line"] += 1
    print(" · ".join(f"{k} {v}" for k, v in t.most_common()))


if __name__ == "__main__":
    main()
