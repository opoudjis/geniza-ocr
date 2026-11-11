#!/usr/bin/env python3
"""fold-by-line.py: write approved folds of one head into another, line by line, as DECISIONS «name» rows in each line's
source (the class D folds of 2026-11-07 and the class A review's Part 2 of 2026-11-08 were written so by Ezri's scratch
scripts write_folds.py and a_part2_write.py; made a tool 2026-11-08 on the editor's ruling).

    python3 tools/fold-by-line.py PAIRS.tsv --note NOTE --ruling TEXT [--write]

PAIRS.tsv: a header «fold<TAB>keep», then one approved pair a row: the garbled or pen-name head, the head it goes into.
Only the lines that pair the two heads in today's `profiles/build/SAME-ACT-PAIRS-LATEST.tsv` (written by
`tools/same_act.py --write` after each harvest) are folded, never the folded head's other lines: each is found in its
by-source facts file by its head and its exact fact text, and gets a row (locator: item and page; phrase: the fact's first
words; kind «name»; value: the kept head as its profile's title gives it; the ruling; the note). A pair with no line
today, a line found more or fewer than once, or a source without a dowse/<source>/DECISIONS.tsv is reported, not
written. Rows already present are not written twice.

Without --write it prints the plan and writes nothing. With --write it appends to existing DECISIONS.tsv files only.
Then: `tools/reassemble-sources.py --sinter-tag NOTE`, one harvest alone, and each folded line checked under its head."""
import argparse, collections, csv, importlib.util, os, re, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
csv.field_size_limit(10**8)

def plain(t): return "".join(c for c in unicodedata.normalize("NFD", t.upper()) if unicodedata.category(c) != "Mn")
def base(h): return plain(re.sub(r"\s*\(.*", "", h)).strip()
def slug(h): return re.sub(r"[^a-z0-9]+", "-", base(h).lower()).strip("-")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs"); ap.add_argument("--note", required=True); ap.add_argument("--ruling", required=True)
    ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    s = importlib.util.spec_from_file_location("same_act", os.path.join(ROOT, "tools", "same_act.py"))
    SA = importlib.util.module_from_spec(s); s.loader.exec_module(SA)
    PAIRS = [(r["fold"].strip(), r["keep"].strip()) for r in csv.DictReader(open(a.pairs, encoding="utf-8"), delimiter="\t")]
    R = list(csv.DictReader(open(os.path.join(G, "profiles", "build", "SAME-ACT-PAIRS-LATEST.tsv"), encoding="utf-8"), delimiter="\t"))
    cache = {}
    def lines(src):
        if src not in cache:
            p = os.path.join(G, "profiles", "by-source", f"{src}-dowse.md")
            cache[src] = [l.rstrip("\n") for l in open(p, encoding="utf-8")] if os.path.exists(p) else []
        return cache[src]
    rows, plan, report = collections.defaultdict(list), [], []
    for f, k in PAIRS:
        pf = os.path.join(G, "profiles", f"{slug(k)}.md")
        if not os.path.exists(pf): report.append((f, k, "no profile for the kept head")); continue
        title = re.match(r"# (.+?) — ", open(pf, encoding="utf-8").readline()).group(1).replace(", ambigua", "")
        hits = [r for r in R if {base(r["head_a"]), base(r["head_b"])} == {plain(f), plain(k)}]
        if not hits: report.append((f, k, "no pair today")); continue
        for r in hits:
            side = "a" if base(r["head_a"]) == plain(f) else "b"
            src, fa, head = r[f"source_{side}"], r[f"fact_{side}"], r[f"head_{side}"]
            m = [l for l in lines(src) if l.startswith(f"- $$$ {head} $$$") and SA.fact(l) == fa]
            if len(m) != 1: report.append((f, k, f"{len(m)} exact lines in {src}")); continue
            if not os.path.exists(os.path.join(G, "dowse", src, "DECISIONS.tsv")): report.append((f, k, f"no dowse/{src}/DECISIONS.tsv")); continue
            parts = m[0].split(" · ")
            loc = next((x for x in parts if re.search(r", (PDF \d+|¶ ?\d+)", x)), "").split("; ")[0]
            loc = re.sub(r", l\. \d+.*", "", re.sub(r"\s*\(prese[^)]*\)", "", loc)).strip()
            ff = re.sub(r"^\*\*\([^)]*\)\*\* ", "", parts[2] if parts[1].startswith("{") else parts[1])
            phrase = re.sub(r"\s+\S*$", "", ff[:40]) if len(ff) > 40 else ff
            row = (loc, phrase, "name", title)
            if row not in rows[src]: rows[src].append(row); plan.append((title, head, src, loc, phrase))
    print(f"{len(PAIRS)} pairs: {len(plan)} lines to fold in {len(rows)} sources; {len(report)} reported")
    for p in plan: print(f"  {p[0]} ← {p[1]} | {p[2]} | {p[3]} | {p[4]}")
    for x in report: print("  NOT WRITTEN:", x)
    if not a.write: return
    n = 0
    for src, rr in rows.items():
        p = os.path.join(G, "dowse", src, "DECISIONS.tsv")
        old = open(p, encoding="utf-8").read(); assert old.endswith("\n"), p
        with open(p, "a", encoding="utf-8") as fh:
            for r in rr:
                if "\t".join(r[:3]) in old: print("  already present:", src, r[:2]); continue
                fh.write("\t".join(r) + f"\t{a.ruling}\t{a.note}\n"); n += 1
    print("rows written:", n)

if __name__ == "__main__":
    main()
