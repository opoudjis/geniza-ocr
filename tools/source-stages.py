#!/usr/bin/env python3
"""The stage every source has reached at a release of the prosopography (the publishing runbook, «The sources' stages at the
release»; the editor, 2026-11-11).

    source-stages.py snapshot VERSION DATE [--write]     the stage of every item now, recorded as VERSION's (dated DATE)
    source-stages.py show                                 the counts, item and source, of each stage at each version

An item's stage, the most advanced it has reached:
  sinter  its facts harvested into the profiles (dowse/DOWSED-ITEMS-LATEST.tsv, an item with a readers' tag);
  dowse   read by the readers, not yet harvested (a reader's page list in a dowse folder, «=== teksto: ITEM ===» in
          facts-pages-‹tag›-‹n›.txt, with that reader's return filed, facts-return-‹tag›-‹n›*.md);
  cupel   its text in the corpus (sources/ocr-preferred/ or born-digital-text/), not yet read;
  blank   in the item table (OCR-ITEM-TABLE.tsv), no text yet.
A source («unit»): the item's signed siglum (profiles/SIGLA.tsv), else its title key in the item table, else the item itself.
Writes dowse/ETAPOJ.tsv (item, unit, version, date, stage), adding VERSION's rows; refused if VERSION is there already.
tools/dowse-done.py reads it for the page of sources (published/genizo/pages/legitaj-fontoj.md): the column «Etapo» and one
table for each stage below sinter. Without --write, the counts only. No network. Ezri, 2026-11-11."""
import json, collections, csv, glob, os, re, sys
import sigla

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
OUT = os.path.join(G, "dowse", "ETAPOJ.tsv")
ORDER = ["blank", "cupel", "dowse", "sinter"]
csv.field_size_limit(sys.maxsize)


def table():
    rows = {}
    for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        rows[r["item"]] = r
    return rows


def unit_of(item, rows, cache={}):
    if item in cache: return cache[item]
    r = rows.get(item, {})
    key = (r.get("key") or "").strip() or item
    u = None
    for rx, row, _ in sigla.load():   # a pattern may name the item's key or the item itself («^ANNO_e1a_», GermEsp)
        # (and the item's name as a key: «reu-blanke_historio_de_laborista_movado_2008.numbered» for Blan2008, 2026-11-11)
        norm = re.sub(r"\.numbered$", "", item).replace("_", "-")
        if (rx.search(key) or rx.search(item) or rx.search(norm)) and row.get("status") == "signed": u = row["siglum"]; break
    cache[item] = u or (r.get("title_key") or "").strip() or item
    return cache[item]


def stages_now():
    rows = table()
    st = {it: "blank" for it in rows}
    for sub in ("ocr-preferred", "born-digital-text"):
        for f in glob.glob(os.path.join(G, "sources", sub, "*.txt")):
            st[os.path.basename(f)[:-4]] = "cupel"
    # the readers' reads: a reader's page list names its texts; it counts once that reader's return is filed
    for d in glob.glob(os.path.join(G, "dowse", "*")):
        if not os.path.isdir(d): continue
        names = set(os.listdir(d))
        # a return counts once filed whole (its pieces «-pK.md» joined by step 6): a piece alone may be one set aside
        # (2026-11-11: Germana Esperantisto's batch 28, its pieces left out at «ge», relaunched as «ge2»)
        done = {m.group(1) for n in names for m in [re.match(r"facts-return-(.+?-\d+)\.md$", n)] if m}
        for n in names:
            m = re.match(r"facts-pages-(.+?-\d+)\.txt$", n)
            if not m or m.group(1) not in done: continue
            seen = set()
            with open(os.path.join(d, n), encoding="utf-8", errors="replace") as fh:
                for l in fh:
                    t = re.match(r"=== teksto: (.+?) ===\s*$", l)
                    if t: seen.add(t.group(1))
            # a source of one text writes no «=== teksto:» header in its pages files (2026-11-11, Miles: Blanke 1985 and
            # 1999, Clark 1907, Drezen's three books and Blanke 2008 were taken for «cupel» in 0.1's snapshot): its
            # brief-config.json's texts, then
            if not seen and "brief-config.json" in names:
                try: tx = json.load(open(os.path.join(d, "brief-config.json"), encoding="utf-8")).get("texts", [])
                except ValueError: tx = []
                if isinstance(tx, str): tx = re.findall(r"'([^']+)'", tx)
                seen = {os.path.basename(x)[:-4] if x.endswith(".txt") else os.path.basename(x) for x in tx}
            for it in seen:
                if ORDER.index(st.get(it, "blank")) < ORDER.index("dowse"): st[it] = "dowse"
    dp = os.path.join(G, "dowse", "DOWSED-ITEMS-LATEST.tsv")
    for r in csv.DictReader((l for l in open(dp, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if (r.get("readers_tag") or "").strip(): st[r["item"]] = "sinter"
    return st, rows


def read_out():
    if not os.path.exists(OUT): return []
    return list(csv.DictReader(open(OUT, encoding="utf-8"), delimiter="\t"))


def history():
    """{item: [(version, stage), …]} in version order, and {item: unit} by the newest snapshot"""
    h, unit = collections.defaultdict(list), {}
    vkey = lambda v: [int(x) for x in re.findall(r"\d+", v)]
    for r in sorted(read_out(), key=lambda r: vkey(r["version"])):
        h[r["item"]].append((r["version"], r["stage"])); unit[r["item"]] = r["unit"]
    return h, unit


def etapo(items, h):
    """the column: each version and the stage the group's items had then (their least advanced), a stage given only when it
    changes, nothing after sinter («0.1 dowse 0.2 sinter»)"""
    vs = sorted({v for it in items for v, _ in h.get(it, [])}, key=lambda v: [int(x) for x in re.findall(r"\d+", v)])
    out, last = [], None
    for v in vs:
        ss = [s for it in items for vv, s in h.get(it, []) if vv == v]
        if not ss: continue
        s = min(ss, key=ORDER.index)
        if s != last: out.append(f"{v} {s}"); last = s
        if s == "sinter": break
    return " ".join(out)


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("snapshot", "show"): sys.exit(__doc__)
    if a[0] == "show":
        h, unit = history()
        for v in sorted({x for l in h.values() for x, _ in l}):
            c = collections.Counter(s for l in h.values() for x, s in l if x == v)
            u = collections.defaultdict(set)
            for it, l in h.items():
                for x, s in l:
                    if x == v: u[s].add(unit[it])
            print(v, {s: f"{c[s]} items, {len(u[s])} sources" for s in ORDER if c[s]})
        return
    if len(a) < 3: sys.exit("snapshot VERSION DATE [--write]")
    ver, date, write = a[1], a[2], "--write" in a
    if any(r["version"] == ver for r in read_out()): sys.exit(f"{ver} is already in {os.path.relpath(OUT, G)}")
    st, rows = stages_now()
    c = collections.Counter(st.values())
    us = collections.defaultdict(set)
    for it, s in st.items(): us[s].add(unit_of(it, rows))
    print(f"{ver} ({date}): " + "; ".join(f"{s} {c[s]:,} items in {len(us[s]):,} sources" for s in reversed(ORDER)))
    if not write: print("(the counts only; --write records them)"); return
    new = not os.path.exists(OUT)
    with open(OUT, "a", encoding="utf-8") as fh:
        if new: fh.write("item\tunit\tversion\tdate\tstage\n")
        for it in sorted(st): fh.write(f"{it}\t{unit_of(it, rows)}\t{ver}\t{date}\t{st[it]}\n")
    print("written", os.path.relpath(OUT, G))


if __name__ == "__main__":
    main()
