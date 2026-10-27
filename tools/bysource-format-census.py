#!/usr/bin/env python3
"""The facts files not yet in facts format 4, sorted by the way they would be brought up (the editor, 2026-10-15 to the census; approved, to the split by kind and the map of the
roster runs).

    tools/bysource-format-census.py [--out FILE] [--map FILE]

The runbook's D8 ruling: «Older roster-run facts files are reconciled and retired source by source, at that source's
dowse; scout-made files are never touched by a dowse». So the files fall in two kinds: the roster runs (a name with
«roster»), which a dowse retires, and the scout-made files, which stay. For each file: its facts format (the
«facts-format: N» header the harvest reads, or «none»), its fact lines, and, line by line, the sources its locator
cites, matched as tools/harvest-coverage.py matches them (a normalised filename stem of a file under geniza/sources/,
jespersen/ or apparatus-tsv/ found in the line's fields between the fact and the confidence). A cited source is in the
dowse corpus when it lies under one of the text folders (ocr-preferred, ocr, ocr-rendersearch, born-digital-text,
archive-org-ido, ocr-work), outside it otherwise (web saves, extracts, scans); a line that names no file stem (a source
cited by its title only) is «uncited» here, which is not proof that it has no source. The corpus sources are grouped
into dowse-inventory units as tools/dowse-inventory.py groups items. Prints the counts; --out writes the report and
--map the roster runs' file → unit table (TSV, a seed for the hand check), both create-only. Ezri, 2026-10-15."""
import argparse, csv, glob, importlib.util, os, re, sys
from collections import defaultdict, Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
FMT = re.compile(r"^\W*facts-format:\s*(\d)\b")
ROSTER = re.compile(r"roster", re.I)       # the September roster runs: the only old files a dowse retires (runbook D8)
CORPUS = ("ocr-preferred/", "ocr/", "ocr-rendersearch/", "born-digital-text/", "archive-org-ido/")
# source folders cited by locators that are corpus sources under another name (checked by hand, 2026-10-15): two units
# of the inventory, and two born-digital texts made after it (ocr/method/born-digital-spec-adresaro-wikisource-2026-10-11.tsv,
# born-digital-spec-historio-ru-2026-10-10.tsv)
ALIAS = {"oge-rolls": "oge", "ede-1933-articles": "enciklopedio_de_esperanto",
         "adresaro-wikisource": "adresaro-wikisource (born-digital, after the inventory)",
         "historio-ru": "historio-ru (born-digital, after the inventory)"}

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(ROOT, "tools", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def citer():
    """-> cite(line): the source stems a fact line's locator names, as tools/harvest-coverage.py matches them, or None
    for a line its fact pattern does not read."""
    hc = load("harvest-coverage")
    srcs = hc.sources()
    # the corpus: a key with a text file under one of the text folders (harvest-coverage keeps only the first file of a
    # key, often the scan: «BritaEsperantisto/….pdf» for a run whose OCR is in ocr-preferred/)
    corpus = {}
    for d in CORPUS:
        for p in glob.glob(os.path.join(G, "sources", d, "**", "*.txt"), recursive=True):
            stem = re.sub(r"[_-]?(djvu|ocr|extracted|embedded|raw)$", "", os.path.splitext(os.path.relpath(p, os.path.join(G, "sources")))[0], flags=re.I)
            stem = re.sub(r"/(page-?\d+|img\d+)$", "", stem, flags=re.I)
            corpus.setdefault(hc.key(os.path.basename(stem)), stem)
    idx = defaultdict(list)
    for k, v in srcs.items(): idx[k[:6]].append((k, corpus.get(k) or v[0]))
    def cite(line):
        m = hc.FACT.match(line.rstrip())
        if not m: return None
        parts = [x.strip() for x in m.group("rest").split(" · ")]
        if len(parts) < 4: return set()
        f = hc.key(" · ".join(parts[1:-2]))
        return {stem for i in range(max(0, len(f) - 5)) for k, stem in idx.get(f[i:i + 6], ()) if f.startswith(k, i)}
    return cite

def unit_of_stem(inv, table, stem):
    """A cited corpus stem's dowse-inventory unit (the OCR item table's title_key, else the run key; a born-digital text
    by its work), as tools/dowse-inventory.py groups items."""
    item = os.path.basename(stem)
    if table.get(item): return inv.unit_of(table[item])
    if stem.startswith("born-digital-text/"): return "bd-" + inv.bd_unit(item)
    return inv.run_key(item)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out"); ap.add_argument("--map"); a = ap.parse_args()
    for p in (a.out, a.map):
        if p and os.path.exists(p): sys.exit(f"{p} exists: not overwritten")
    inv = load("dowse-inventory")
    table = {}
    for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        table[r["item"]] = r.get("title_key") or ""; inv.KEYS.add(r.get("title_key") or "")
    units = {r["key"]: r for r in csv.DictReader(open(os.path.join(G, "ocr", "method", "DOWSE-INVENTORY-2026-10-10.tsv"), encoding="utf-8"), delimiter="\t")}
    cite = citer()
    files = []
    for p in sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*.md"))):
        lines = open(p, encoding="utf-8").read().split("\n")
        m = next((FMT.match(l) for l in lines[:15] if FMT.match(l)), None)
        fmt = m.group(1) if m else "none"
        cls, us, outs = Counter(), Counter(), Counter()
        for l in lines:
            if not l.startswith("- $$$ "): continue
            st = cite(l) or set()
            corp = {unit_of_stem(inv, table, s) for s in st if s.startswith(CORPUS)}
            # a scan folder named as an inventory unit is that unit («BritaEsperantisto/…» → britaesperantisto)
            corp |= {inv.fold(s.split("/")[0]) for s in st if "/" in s and inv.fold(s.split("/")[0]) in units}
            corp |= {ALIAS[s.split("/")[0]] for s in st if s.split("/")[0] in ALIAS}
            if corp:
                cls["corpus"] += 1
                for u in corp: us[u] += 1
            elif st:
                cls["outside"] += 1
                for s in st: outs[s.split("/")[0]] += 1
            else: cls["uncited"] += 1
        files.append(dict(file=os.path.basename(p), fmt=fmt, kind="roster run" if ROSTER.search(os.path.basename(p)) else "scout-made",
                          lines=sum(cls.values()), cls=cls, units=us, outside=outs))
    old = [f for f in files if f["fmt"] != "4"]
    def tot(fs, c=None): return sum(f["cls"][c] if c else f["lines"] for f in fs)
    print(f"{len(files)} facts files; {len(files) - len(old)} in format 4; {len(old)} not, {tot(old)} fact lines")
    for kind in ("roster run", "scout-made"):
        fs = [f for f in old if f["kind"] == kind]
        print(f"  {kind}: {len(fs)} files, {tot(fs)} lines: citing a corpus text {tot(fs, 'corpus')}, citing only sources outside the corpus "
              f"{tot(fs, 'outside')}, no file cited {tot(fs, 'uncited')}")
    outside = Counter()
    for f in old: outside.update(f["outside"])
    print("  sources outside the corpus, by the folder cited (lines): " + ", ".join(f"{k} {v}" for k, v in outside.most_common(12)))
    by_unit = defaultdict(lambda: Counter())
    for f in old:
        for u, n in f["units"].items(): by_unit[u][f["kind"]] += n
    order = sorted(by_unit.items(), key=lambda kv: -(kv[1]["roster run"] + kv[1]["scout-made"]))
    print("  the first units by old-format lines citing them (roster / scout): " + "; ".join(f"{u} {c['roster run']}/{c['scout-made']}" for u, c in order[:12]))
    if a.map:
        with open(a.map, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(["file", "lines", "lines citing a corpus text", "units by lines (from the citations)", "outside the corpus", "no file cited", "the source (hand-checked)", "note"])
            for f in [f for f in files if f["kind"] == "roster run"]:
                w.writerow([f["file"], f["lines"], f["cls"]["corpus"], "; ".join(f"{u} {n}" for u, n in f["units"].most_common()),
                            "; ".join(f"{k} {n}" for k, n in f["outside"].most_common()), f["cls"]["uncited"], "", ""])
        print(f"wrote {os.path.relpath(a.map, ROOT)}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("# The facts files not in format 4: the census (2026-10-15)\n\n"
                     "*`[GENERATED by tools/bysource-format-census.py. Do not hand-edit: re-run it. The sources are those a line's locator cites by file stem (tools/harvest-coverage.py's match); a source cited by title only reads as «no file cited». The runbook's D8: a dowse retires the roster runs only; the scout-made files stay.]`*\n\n")
            fh.write(f"**{len(files)} files; {len(files) - len(old)} in format 4; {len(old)} not, {tot(old)} fact lines.**\n\n| kind | files | lines | citing a corpus text | citing only sources outside the corpus | no file cited |\n|---|---|---|---|---|---|\n")
            for kind in ("roster run", "scout-made"):
                fs = [f for f in old if f["kind"] == kind]
                fh.write(f"| {kind} | {len(fs)} | {tot(fs)} | {tot(fs, 'corpus')} | {tot(fs, 'outside')} | {tot(fs, 'uncited')} |\n")
            fh.write("\n**Sources outside the corpus, by the folder cited (lines):** " + ", ".join(f"`{k}` {v}" for k, v in outside.most_common()) + "\n\n")
            fh.write("## The units, by the old-format lines citing them\n\n| unit | title | pages | in the inventory | roster-run lines | scout-made lines |\n|---|---|---|---|---|---|\n")
            for u, c in order:
                r = units.get(u, {})
                fh.write(f"| {u} | {r.get('title', '')} | {r.get('pages', '')} | {'yes' if r else 'no'} | {c['roster run']} | {c['scout-made']} |\n")
            fh.write("\n## The files\n\n| file | kind | format | lines | corpus | outside | no file cited | units (lines) |\n|---|---|---|---|---|---|---|---|\n")
            for f in sorted(old, key=lambda f: (f["kind"], -f["lines"])):
                fh.write(f"| {f['file']} | {f['kind']} | {f['fmt']} | {f['lines']} | {f['cls']['corpus']} | {f['cls']['outside']} | {f['cls']['uncited']} | "
                         + "; ".join(f"{u} {n}" for u, n in f["units"].most_common(6)) + " |\n")
        print(f"wrote {os.path.relpath(a.out, ROOT)}")

if __name__ == "__main__":
    main()
