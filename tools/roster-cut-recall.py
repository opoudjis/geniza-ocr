#!/usr/bin/env python3
"""roster-cut-recall.py: did the roster bug cost lines? (Miles, 2026-11-09; the editor.)

    tools/roster-cut-recall.py [SOURCE …] [--out REPORT.md]

THE BUG (found 2026-11-09 21:3x, fixed by Ezri 21:43): tools/dowse-reader-roster.py and tools/dowse-brief-fill.py read a
source's hits file (dowse/<source>/record-<tag>*.hits.tsv) at csv's default quoting, so a «"» in an OCR reading swallowed
the rows after it, and the people found only in those rows were left off the legiloj' rosters and «out» lists. Ezri's
count: 141 of 162 strong hits files read short, every dowse since 2026-10-17.

THE TEST: the brief tells a legilo to write every person in scope on its pages, on the roster or not («kiel presite»), so
a cut person should still get lines, under the name as printed. For each hits file: the people found at the «exact» tier,
split into those the buggy reading kept and those it cut; for each group, the share with a head in the returns of the
briefs built on that hits file (a brief's third line names «the side files of <tag>»). If the cut share is not clearly
below the kept share, the readers read the cut people anyway, and what is owed is the dress (heads and scope), not a
redowse. Flag «SHORT» where the cut share is below 0.75 × the kept share with at least 20 cut people; «weak» where the
returns have fewer than 30 heads.

THE MATCH is rough: a person counts as having a head where a segment of their profile stem (4 letters or more) is a word
of a head, folded to a-z («mac-kenzie» → «kenzie»; «skeel-giorling» → «skeel», «giorling»). The cut rows are those after
an OCR quote, so they lean to the later pages of a file: the two groups are not equal samples, and the rates are
indicative.

With no SOURCE, every folder under geniza/dowse/ with a hits file. Read-only on the repo; --out writes one report,
create-only. Prints one line per hits file. Run time: the hits files are read twice; the largest take a minute or more."""
import argparse, csv, glob, io, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "published", "heterophony-resources", "geniza", "dowse")
csv.field_size_limit(sys.maxsize)
HEAD = re.compile(r"\$\$\$ (.+?) \$\$\$")
SIDE = re.compile(r"the side files of (\S+?)[;\]\s]")


def fold(s):
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode())


def exact_people(path):
    """The «exact» people as the buggy reading saw them (csv's default quoting) and as the file holds them (plain
    tab-split, as tools/redowse-pages.py's read_tsv reads)."""
    text = "".join(l for l in open(path, encoding="utf-8", errors="replace") if not l.startswith("#"))
    buggy = {r["person"] for r in csv.DictReader(io.StringIO(text), delimiter="\t") if r.get("tier") == "exact"}
    rows = text.split("\n")
    head = rows[0].split("\t")
    pi, ti = head.index("person"), head.index("tier")
    whole = set()
    for l in rows[1:]:
        f = l.split("\t")
        if len(f) > ti and f[ti] == "exact": whole.add(f[pi])
    return buggy & whole, whole - buggy


def return_tags(src, htag):
    """The tags of the briefs built on this hits file's side files."""
    tags = set()
    for b in glob.glob(os.path.join(D, src, "facts-brief-*.md")):
        try: third = open(b, encoding="utf-8", errors="replace").read(3000).split("\n")[2]
        except IndexError: continue
        m = SIDE.search(third + " ")
        t = re.match(r"facts-brief-(.+?)-(?:g\d+-\d+|\d+)\.md$", os.path.basename(b))
        if m and t and m.group(1) == htag: tags.add(t.group(1))
    return sorted(tags)


def heads(src, tags):
    """The folded words of every head in the tags' returns: the joined returns, or a part's pieces where it has none."""
    words, n = set(), 0
    for t in tags:
        fs = glob.glob(os.path.join(D, src, f"facts-return-{t}-*.md"))
        joined = {f for f in fs if re.fullmatch(rf"facts-return-{re.escape(t)}-\d+\.md", os.path.basename(f))}
        pieces = {f for f in fs if re.fullmatch(rf"facts-return-{re.escape(t)}-(\d+)-p\d+\.md", os.path.basename(f))
                  and os.path.join(D, src, f"facts-return-{t}-{re.match(r'.*-(\d+)-p', os.path.basename(f)).group(1)}.md") not in joined}
        for f in joined | pieces:
            n += 1
            for m in HEAD.finditer(open(f, encoding="utf-8", errors="replace").read()):
                words.update(fold(w) for w in re.split(r"[\s\-()]+", m.group(1)) if w)
    return words, n


def has_head(person, words):
    return any(len(fold(s)) >= 4 and fold(s) in words for s in person.split("-"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sources", nargs="*")
    ap.add_argument("--out", help="a report (markdown), create-only")
    a = ap.parse_args()
    srcs = a.sources or sorted(d for d in os.listdir(D) if glob.glob(os.path.join(D, d, "record-*hits.tsv")))
    rows = []
    for s in srcs:
        for hp in sorted(glob.glob(os.path.join(D, s, "record-*hits.tsv"))):
            m = re.match(r"record-(.+?)(?:-strong)?\.hits\.tsv$", os.path.basename(hp))
            htag = m.group(1) if m else ""
            tags = return_tags(s, htag)
            if not tags: continue
            kept, cut = exact_people(hp)
            words, nret = heads(s, tags)
            if not nret: continue
            kh, ch = sum(has_head(p, words) for p in kept), sum(has_head(p, words) for p in cut)
            ks, cs = kh / len(kept) if kept else 0, ch / len(cut) if cut else 0
            flag = "SHORT" if len(cut) >= 20 and cs < 0.75 * ks else ""
            if len(words) < 30: flag = (flag + " weak").strip()
            rows.append((s, htag, "+".join(tags), nret, len(words), len(kept), kh, ks, len(cut), ch, cs, flag))
            print(f"{s}\t{htag}\treturns {'+'.join(tags)} ({nret})\tkept {len(kept)}: {kh} ({ks:.0%})\tcut {len(cut)}: {ch} ({cs:.0%})\t{flag}", flush=True)
    short = [r for r in rows if "SHORT" in r[11]]
    print(f"{len(rows)} hits files with returns; {sum(1 for r in rows if r[8])} with people cut; {len(short)} SHORT")
    if a.out:
        out = ["# Did the roster bug cost lines? (tools/roster-cut-recall.py)", "",
               f"{len(rows)} hits files with returns; {sum(1 for r in rows if r[8])} with people cut at the «exact» tier; "
               f"**{len(short)} SHORT** (the cut people's share with a head below 0.75 × the kept people's, 20 cut or more). "
               "The match is rough and the groups are not equal samples (the tool's docstring).", "",
               "| source | hits tag | returns (tags, files) | heads | kept: with a head | cut: with a head | flag |",
               "|---|---|---|---|---|---|---|"]
        for r in rows:
            out.append(f"| {r[0]} | {r[1]} | {r[2]} ({r[3]}) | {r[4]} | {r[5]}: {r[6]} ({r[7]:.0%}) | {r[8]}: {r[9]} ({r[10]:.0%}) | {r[11]} |")
        with open(a.out, "x", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
        print("wrote", a.out)


if __name__ == "__main__":
    main()
