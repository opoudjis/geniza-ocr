#!/usr/bin/env python3
"""ocr-index-check — does the index (tools/ocr_index.py) give EXACTLY what the name search gives? Before dowse uses
the index, every hit of find(name, page) and of match(name, index) must agree, as a multiset, page by page.

    tools/ocr-index-check.py [--texts 24] [--names 120] [--seed 7] [--jobs 8]

Texts: a random sample of search texts and Russian texts, plus every-reading texts. Names: the names the blind G5
judges read on the filed samples (Latin and Cyrillic), plus fixed hard cases. Prints every disagreement; exit 1 if any.
Reads only; writes nothing.
"""
import argparse, collections, glob, importlib.util, os, random, re, sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources")
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)
import ocr_index as IX  # noqa: E402  (beside this file)

HARD = ["Méray", "Müller", "Kühnl", "Постниковъ", "Zamenhof", "Applebaum", "Bréon", "Hodler", "Kabe", "Бейнъ",
        "Grosjean-Maupin", "Asnes", "Lebedev", "Яковъ Бородкинъ / Jakov Borodkin", "Iglauer", "Döhler"]


def judged_names():
    out = set()
    for r in glob.glob(os.path.join(S, "ocr-work", "ocr-scratch-*", "g5*", "RETURNS.md")):
        for l in open(r, encoding="utf-8"):
            m = re.match(r"\|\s*\d{3}\s*\|\s*(?:NOTHING|MINOR|LOST)\s*\|[^|]*\|[^|]*\|([^|]*)\|", l)
            if m:
                out |= {n.strip() for n in m.group(1).split(";") if len(n.strip()) > 2 and n.strip() != "-"}
    return sorted(out)


def check(job):
    f, names = job
    text = open(f, encoding="utf-8", errors="ignore").read()
    idx = IX.build(text)
    pg = IX.pages(text)
    bad = []
    for n in names:
        a = collections.Counter((p, how, r) for p, pt in pg for how, r in NS.find(n, pt))
        b = collections.Counter(IX.match(n, idx))
        if a != b:
            bad.append((os.path.relpath(f, S), n, sorted((a - b).items())[:3], sorted((b - a).items())[:3]))
    return len(names), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--texts", type=int, default=24); ap.add_argument("--names", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    pool_t = sorted(glob.glob(os.path.join(S, "ocr-rendersearch", "*.txt")))
    texts = rnd.sample(pool_t, a.texts)
    texts += rnd.sample(sorted(glob.glob(os.path.join(S, "ocr-rendersearch-rus", "*.txt"))), max(2, a.texts // 4))
    texts += rnd.sample(sorted(glob.glob(os.path.join(S, "ocr-rendersearch-all", "*.txt"))), max(2, a.texts // 6))
    names = HARD + rnd.sample(judged_names(), a.names)
    tot, bad = 0, []
    with Pool(a.jobs) as pool:
        for n, b in pool.imap_unordered(check, [(t, names) for t in texts]):
            tot += n; bad += b
    for f, n, only_find, only_index in bad:
        print(f"DIFF  {f} · «{n}»\n   find only: {only_find}\n   index only: {only_index}")
    print(f"{len(texts)} texts × {len(names)} names = {tot} comparisons · {len(bad)} disagreements")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
