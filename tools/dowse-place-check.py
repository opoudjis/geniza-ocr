#!/usr/bin/env python3
"""Does a legilo read its last part thinner than its first? (2026-11-05; the editor, on tier 1's recall sample)

    tools/dowse-place-check.py [SOURCE ...] [--write]

Lines per 1,000 words by a part's place in its legilo, from the stage's group briefs (facts-brief-TAG-gA-B.md), the pages files and the
returns; a recall tag («…r», «…r2») is no stage. No legilo, no text under sources/. Each source: its legiloj of three parts or more,
first and last part, and the ratio. Flag: under 0.8 at 10 legiloj or more (with fewer the ratio is mostly the texts').
It cannot see a legilo thin in all its parts: only a second reader can (dowse-recall.py parts-compare).
No source named: all, and the two corpus lines. --write: profiles/build/PLACE-RATIOS-LATEST.md. Exit 0 whatever it flags."""
import argparse, collections, glob, os, re, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
FLAG, MIN_LEGILOJ = 0.8, 10

def legiloj(source):
    """[(tag, [(words, lines) by place])], a legilo whose parts all have a pages file and a return."""
    D = os.path.join(G, "dowse", source); out = []
    for b in glob.glob(os.path.join(D, "facts-brief-*-g*-*.md")):
        m = re.search(r"facts-brief-(.+)-g(\d+)-(\d+)\.md$", b)
        if not m or re.search(r"r\d*$", m.group(1)): continue
        tag, a, z, vals = m.group(1), int(m.group(2)), int(m.group(3)), []
        for k in range(a, z + 1):
            pf, rf = os.path.join(D, f"facts-pages-{tag}-{k}.txt"), os.path.join(D, f"facts-return-{tag}-{k}.md")
            if not (os.path.exists(pf) and os.path.exists(rf)): vals = None; break
            vals.append((len(open(pf, encoding="utf-8", errors="replace").read().split()),
                         sum(1 for l in open(rf, encoding="utf-8", errors="replace") if l.startswith("- $$$"))))
        if vals and all(v[0] > 300 for v in vals): out.append((tag, vals))
    return out

def check(source):
    """(legiloj, first, last, ratio, flagged) over the source's legiloj of three parts or more; None if it has none."""
    ls = [v for _t, v in legiloj(source) if len(v) >= 3]
    if not ls: return None
    w1, n1 = sum(v[0][0] for v in ls), sum(v[0][1] for v in ls); wz, nz = sum(v[-1][0] for v in ls), sum(v[-1][1] for v in ls)
    a, z = 1000 * n1 / max(1, w1), 1000 * nz / max(1, wz)
    r = z / a if a else 0
    return len(ls), a, z, r, r < FLAG and len(ls) >= MIN_LEGILOJ

def line(source, c):
    return (f"- {source}: {c[0]} legiloj of three parts or more; lines a 1,000 words, first part {c[1]:.1f}, last {c[2]:.1f}; last against first {c[3]:.2f}"
            + (f"  **FLAGGED: under {FLAG} at {MIN_LEGILOJ} legiloj or more; the recall sample to 4 parts (runbook, step 11)**" if c[4] else ""))

def recall(source):
    """(first's lines, second's, the first lacks %, the second lacks %, ratio, parts) over all the source's recall comparisons; None if it has none."""
    n1 = n2 = m1 = m2 = parts = 0
    for f in glob.glob(os.path.join(G, "dowse", source, "recall-compare-*.md")):
        t = open(f, encoding="utf-8").read()
        m = re.search(r"stage readers:\*\* (\d+) lines; \*\*the second:\*\* (\d+); matched (\d+) / (\d+)", t)
        if not m: continue
        a, b, c, d = map(int, m.groups()); n1 += a; n2 += b; m1 += c; m2 += d; parts += len(re.findall(r"^- part \d+:", t, re.M))
    if not n1 or not n2: return None
    return n1, n2, 100 * (n2 - m2) / n2, 100 * (n1 - m1) / n1, n2 / n1, parts

def need_table(names):
    """Item (1) of the editor's list, 2026-11-05: which three-part readings to redowse at one part. The table, by source: needs one, wants more parts, no measure."""
    rows = []
    for s in names:
        n_parts = len(glob.glob(os.path.join(G, "dowse", s, "facts-pages-*.txt")))
        c, r = check(s), recall(s)
        if not c and not r: continue
        one = bool(r and r[1] >= 50 and r[4] >= 1.25 and r[2] >= 2 * max(r[3], 1))
        verdict = ("THIN: a redowse to cost" if one and r[5] >= 4 else "one-sided on few parts: more parts" if one
                   else "the place check flags it: more parts" if c and c[4] else "no recall yet: a sample" if not r else "within noise")
        rows.append((verdict, s, r, c))
    order = ["THIN", "one-sided", "the place", "no recall", "within"]
    rows.sort(key=lambda x: (next(i for i, o in enumerate(order) if x[0].startswith(o)), -(x[2][4] if x[2] else 0)))
    out = ["## Which readings need a redowse at one part", "", "| source | verdict | the first lacks | the second lacks | ratio | parts read twice | place, last/first |", "|---|---|---|---|---|---|---|"]
    for v, s, r, c in rows:
        out.append(f"| {s} | {v} | " + (f"{r[2]:.0f}% | {r[3]:.0f}% | {r[4]:.2f} | {r[5]} | " if r else "– | – | – | 0 | ") + (f"{c[3]:.2f} |" if c else "– |"))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("sources", nargs="*"); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    names = a.sources or sorted(os.path.basename(d.rstrip("/")) for d in glob.glob(os.path.join(G, "dowse", "*/")))
    rows = [(s, c) for s in names for c in [check(s)] if c]
    rows.sort(key=lambda x: x[1][3])
    out = [line(s, c) for s, c in rows]
    if a.write: out = need_table(names) + ["", "## Lines by place, source by source", ""] + out
    if not a.sources:
        places = collections.defaultdict(lambda: [0, 0])
        for s in names:
            for _t, v in legiloj(s):
                if len(v) == 3:
                    for i, (w, n) in enumerate(v): places[i][0] += w; places[i][1] += n
        if places: out = [f"**Three parts a legilo, the corpus, lines a 1,000 words by place:** " + ", ".join(f"{1000 * places[i][1] / max(1, places[i][0]):.1f}" for i in sorted(places)) + ".",
                          f"**Last part against first, the median over {len(rows)} sources:** {statistics.median(c[3] for _s, c in rows):.2f}; flagged {sum(1 for _s, c in rows if c[4])}.", ""] + out
    print("\n".join(out) if out else "no legiloj of three parts or more")
    if a.write:
        p = os.path.join(G, "profiles", "build", "PLACE-RATIOS-LATEST.md")
        open(p, "w", encoding="utf-8").write("# Lines by a part's place in its legilo\n\n**GENERATED by `tools/dowse-place-check.py --write`. Do not edit.**\n\n" + "\n".join(out) + "\n")
        print(f"wrote {os.path.relpath(p, ROOT)}")

if __name__ == "__main__":
    main()
