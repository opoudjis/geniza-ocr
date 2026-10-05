#!/usr/bin/env python3
"""What Tesseract does to accented Latin letters and to Cyrillic letters, measured against a ground truth, priced as
the name search sees it (on the editor's request of 2026-10-05 that every accented Latin letter in the corpus, and
Cyrillic, be covered, for a usable hand-over instrument; the search's digit map was empirical, not a survey).

GROUND TRUTH, two kinds, reported apart:
  vision — pages transcribed by an AI vision model (page-NNNN.vision.txt): old print, Latin mostly;
  born   — pages of born-digital PDFs whose own text layer is the preferred reading (PREFERRED.tsv «tl-born…»;
           page-NNNN.tl.txt): exact text, but modern print, so it under-states old-print damage.
OCR compared: Latin letters against the block reading page-NNNN.txt (the commonest main text); Cyrillic letters
against the Russian readings page-NNNN.rus.txt (modern-spelling model) and page-NNNN.orus.txt (pre-reform model).
METHOD: per page, the truth and the OCR are split into words and aligned (difflib); each truth word with a target
letter is paired with its OCR word when the two are close (similarity ≥ 0.5), and aligned letter by letter. For
each target letter: what the OCR wrote in its place («» = dropped). COST: the edit distance, AFTER the search's
fold (tools/ocr-name-search.py), between the letter and what was written: 0 = the search sees no difference;
1 = uses up the whole allowance of a name of up to 6 letters; 2+ = loses any name of up to 6 letters by itself.

    tools/ocr-accent-survey.py --tsv <new.tsv> --write <new.md> [--jobs 8]     (reads only; refuses existing files)
"""
import argparse, collections, difflib, glob, importlib.util, os, re, sys, unicodedata
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)

WORD = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*|\d+")


def kind(ch):
    """'latin' for a non-ASCII Latin letter, 'cyrillic' for a Cyrillic letter, else None."""
    if not ch.isalpha():
        return None
    n = unicodedata.name(ch, "")
    if n.startswith("LATIN") and ord(ch) > 127:
        return "latin"
    if n.startswith("CYRILLIC"):
        return "cyrillic"
    return None


def pages():
    """(truth file, source) for every vision page and every born-digital preferred text-layer page."""
    for f in glob.glob(os.path.join(R, "*", "page-*.vision.txt")):
        yield f, "vision"
    for p in glob.glob(os.path.join(R, "*", "PREFERRED.tsv")):
        d = os.path.dirname(p)
        for l in open(p, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) > 1 and x[1].startswith("tl-born") and x[0].isdigit():
                f = os.path.join(d, f"page-{int(x[0]):04d}.tl.txt")
                if os.path.exists(f):
                    yield f, "born"


def survey(job):
    truth_f, src = job
    stem = re.sub(r"\.(vision|tl)\.txt$", "", truth_f)
    truth = open(truth_f, encoding="utf-8", errors="ignore").read()
    out = collections.Counter()  # (src, reading, letter, written) -> n
    tw = [w for w in WORD.findall(unicodedata.normalize("NFC", truth))]
    if not any(kind(c) for w in tw for c in w):
        return out
    for reading, script in ((".txt", "latin"), (".rus.txt", "cyrillic"), (".orus.txt", "cyrillic")):
        f = stem + reading
        if not os.path.exists(f):
            continue
        ow = WORD.findall(unicodedata.normalize("NFC", open(f, encoding="utf-8", errors="ignore").read()))
        sm = difflib.SequenceMatcher(None, [w.lower() for w in tw], [w.lower() for w in ow], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            pairs = list(zip(range(i1, i2), range(j1, j2))) if op in ("equal", "replace") else []
            for i, j in pairs:
                t, o = tw[i].lower(), ow[j].lower()
                if not any(kind(c) == script for c in t):
                    continue
                if op == "replace" and difflib.SequenceMatcher(None, t, o).ratio() < 0.5:
                    continue
                cm = difflib.SequenceMatcher(None, t, o, autojunk=False)
                for cop, a1, a2, b1, b2 in cm.get_opcodes():
                    seg = t[a1:a2]
                    for k, ch in enumerate(seg):
                        if kind(ch) != script:
                            continue
                        if cop == "equal":
                            w = ch
                        elif cop == "delete":
                            w = ""
                        elif a2 - a1 == 1:  # one truth letter replaced by the whole OCR run (ü → ii)
                            w = o[b1:b2]
                        else:               # several letters replaced: pair by position where lengths agree
                            w = o[b1 + k] if (b2 - b1) == (a2 - a1) else o[b1:b2]
                        out[(src, reading, ch, w)] += 1
    return out


def cost(letter, written):
    a, b = NS.fold(letter), NS.fold(written)
    return NS.edits(a, b, 9)


PRINT = {"vision": "old", "born": "modern"}


def confusions(table, out, min_share=0.02, min_n=5, min_share_drop=0.05):
    """From a survey table, the CONFUSIONS the name search tries (approved by the editor, 2026-10-05): per letter, each
    thing OCR wrote in its place that the fold does not absorb (cost ≥ 1), seen ≥ min_n times and ≥ min_share of that
    letter's occurrences (a dropped letter: ≥ min_share_drop), kept apart by print: old (vision truth) and modern
    (born-digital truth)."""
    rows = [l.rstrip("\n").split("\t") for l in open(table, encoding="utf-8") if not l.startswith("#")][1:]
    keep = collections.defaultdict(lambda: [0, 0])  # (print, letter, written) -> [count, letter_total]
    tot = collections.Counter()
    for src, reading, ch, w, m, n, c in rows:
        tot[(src, reading, ch)] = int(n)
    for src, reading, ch, w, m, n, c in rows:
        m, n = int(m), int(n)
        c = cost(ch, w)  # re-priced with the CURRENT fold of tools/ocr-name-search.py, not the one the survey ran with
        if c < 1 or m < min_n or m / n < (min_share_drop if w == "" else min_share):
            continue
        k = (PRINT[src], ch, w)  # Cyrillic is counted in two readings (rus, orus): keep the one with the larger share
        if m / n > (keep[k][0] / keep[k][1] if keep[k][1] else 0):
            keep[k] = [m, n]
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-accent-survey.py --confusions from {os.path.basename(table)}: what OCR writes "
                f"in place of a letter, that the search's fold does not absorb (seen ≥ {min_n} times and ≥ "
                f"{min_share:.0%} of the letter, a dropped letter ≥ {min_share_drop:.0%}). Read by tools/ocr-name-search.py. "
                f"Do not hand-edit — re-run it.\n")
        f.write("print\tletter\twritten\tcount\tletter_total\tshare\n")
        for (pr, ch, w), (m, n) in sorted(keep.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1][0])):
            f.write(f"{pr}\t{ch}\t{w}\t{m}\t{n}\t{m / n:.3f}\n")
    print(f"{len(keep)} confusions → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv"); ap.add_argument("--write")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--from-table", help="derive --confusions from an existing survey table (no new survey)")
    ap.add_argument("--confusions", help="write the confusions table the name search reads (refuses an existing file)")
    a = ap.parse_args()
    for p in (a.tsv, a.write, a.confusions):
        if p and os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    if a.from_table:
        if not a.confusions:
            sys.exit("--from-table needs --confusions")
        return confusions(a.from_table, a.confusions)
    if not (a.tsv and a.write):
        sys.exit("a survey needs --tsv and --write")
    jobs = list(pages())
    tot = collections.Counter()
    with Pool(a.jobs) as pool:
        for c in pool.imap_unordered(survey, jobs, chunksize=20):
            tot.update(c)
    # per (src, script-reading, letter)
    by = collections.defaultdict(collections.Counter)
    for (src, reading, ch, w), n in tot.items():
        by[(src, reading, ch)][w] += n
    rows = []
    for (src, reading, ch), c in by.items():
        n = sum(c.values())
        for w, m in c.most_common():
            rows.append((src, reading, ch, w, m, n, cost(ch, w)))
    rows.sort(key=lambda r: (r[0], r[1], -r[5], r[2], -r[4]))
    with open(a.tsv, "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-accent-survey.py over {len(jobs)} ground-truth pages. Do not hand-edit.\n")
        f.write("truth\treading\tletter\twritten\tcount\tletter_total\tcost_after_fold\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    # report: per letter, the share the search sees as correct (cost 0), and every mangling costing 2+ (≥ 3 times)
    L = ["# What OCR does to accented and Cyrillic letters — the survey", "",
         f"`[GENERATED by tools/ocr-accent-survey.py, {len(jobs)} ground-truth pages ({sum(1 for j in jobs if j[1] == 'vision')} "
         f"vision, {sum(1 for j in jobs if j[1] == 'born')} born-digital). Do not hand-edit. Full table: {os.path.basename(a.tsv)}. "
         f"Cost = edits left after the search's fold: 0 the search sees nothing wrong; 1 the whole allowance of a name of "
         f"up to 6 letters; 2+ loses such a name by itself.]`", ""]
    for src in ("vision", "born"):
        for reading in (".txt", ".rus.txt", ".orus.txt"):
            keys = sorted([k for k in by if k[0] == src and k[1] == reading], key=lambda k: -sum(by[k].values()))
            if not keys:
                continue
            L += [f"## {src} truth · OCR reading `page-NNNN{reading}`", "",
                  "| letter | seen | cost 0 | cost 1 | cost 2+ | commonest manglings (written · times · cost) |",
                  "|---|---:|---:|---:|---:|---|"]
            for k in keys:
                c = by[k]; n = sum(c.values())
                if n < 20:
                    continue
                cs = collections.Counter()
                for w, m in c.items():
                    cs[min(cost(k[2], w), 2)] += m
                bad = [(w, m, cost(k[2], w)) for w, m in c.most_common() if cost(k[2], w) > 0][:6]
                L.append(f"| {k[2]} | {n} | {100 * cs[0] / n:.1f}% | {100 * cs[1] / n:.1f}% | {100 * cs[2] / n:.1f}% | "
                         + " · ".join(f"«{w}» {m} ({c_})" for w, m, c_ in bad) + " |")
            L.append("")
    L += ["## Manglings costing 2 or more edits, seen 3 times or more", "",
          "| truth | reading | letter | written | times | of | cost |", "|---|---|---|---|---:|---:|---:|"]
    L += [f"| {r[0]} | {r[1]} | {r[2]} | «{r[3]}» | {r[4]} | {r[5]} | {r[6]} |" for r in
          sorted(rows, key=lambda r: -r[4]) if r[6] >= 2 and r[4] >= 3]
    open(a.write, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"{len(jobs)} pages → {a.tsv}, {a.write}")


if __name__ == "__main__":
    main()
