#!/usr/bin/env python3
"""The name search with two confusion tables, scored on every G5 sample's judged names (the editor, 2026-10-29: whether
the name search, the absence instrument, moves from the 2026-10-05 accent table to the OCR confusions register;
Ezri proposed scoring G5's name recall with both tables before deciding, and the editor agreed; OCR errors are told
apart by their share of the letter, not their count).

For every G5 sample (a folder with KEY.tsv and RETURNS.md under geniza/sources/) and every ledger page the judges named
persons on: each name searched in the page's texts as `ocr-g5-sample.py score` searches them (the class's absence side),
once with each table. RECALL: names found. FALSE HITS (a proxy): the names judged on the NEXT ledger page of the sample,
not judged on this one, searched in this page — a hit is most likely a false one. Each name found by one table only is
listed with the word it matched, and the confusion that made the match, by the register's SHARE of its letter (bands
≥ 20%, 5–20%, 1–5%, under 1%), never by its count.

    tools/ocr-confusions-g5.py --new <register.tsv> --write <new.md> [--jobs N]

Reads only; writes only --write (create-only). Ezri, 2026-10-29."""
import argparse, collections, csv, difflib, glob, importlib.util, os, re, sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
JUDGE = re.compile(r"\|\s*(\d{3})\s*\|\s*(NOTHING|MINOR|LOST)\s*\|\s*(UPRIGHT|ROTATED)\s*\|\s*(NONE|SOME|MUCH)\s*\|([^|]*)\|")
CYR = re.compile("[а-яёѣі]")
BANDS = ((0.20, "≥ 20%"), (0.05, "5–20%"), (0.01, "1–5%"), (0.0, "under 1%"))
NEW = None


def load(path=None):
    s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    if path:
        m.CONF = m._confusions(path)
    return m


OLD_NS = NEW_NS = None


def init(new):
    global OLD_NS, NEW_NS
    OLD_NS, NEW_NS = load(), load(new)


def pages(d):
    """[(sample, nn, class, texts, claimed names)] for the ledger pages of one sample."""
    key = {}
    for l in open(os.path.join(d, "KEY.tsv"), encoding="utf-8", errors="ignore"):
        f = l.rstrip("\n").split("\t")
        if len(f) > 5:
            key[f[0]] = f
    J = {}
    for l in open(os.path.join(d, "RETURNS.md"), encoding="utf-8", errors="ignore"):
        m = JUDGE.match(l)
        if m:
            J[m.group(1)] = [n.strip() for n in m.group(5).split(";") if n.strip() and n.strip() != "-"]
    out = []
    for nn in sorted(key):
        k = key[nn]
        if nn not in J or not k[2].startswith("ledger-") or not J[nn]:
            continue
        cls, side = k[2], k[5]
        sub = os.path.join(d, k[1])
        fs = ((".esperanto-text.txt", ".russian-text.txt", ".all-readings.txt") if cls == "ledger-special" else
              (".esperanto-text.txt",) if side == "eo" else (".russian-text.txt",) if side == "ru" else
              (".esperanto-text.txt", ".russian-text.txt"))
        texts = [os.path.join(sub, nn + f) for f in fs if os.path.exists(os.path.join(sub, nn + f))]
        claimed = [n for n in J[nn] if not ((side == "eo" and CYR.search(n.lower())) or (side == "ru" and not CYR.search(n.lower())))]
        if texts and claimed:
            out.append((os.path.relpath(d, G), nn, cls, k[3], k[4], texts, claimed))
    return out


def hit(ns, name, texts):
    for t in texts:
        h = ns.find(name, t)
        if h:
            return h[0][1]
    return None


def job(p):
    sample, nn, cls, corpus, page, files, claimed, others = p
    texts = [open(f, encoding="utf-8", errors="ignore").read() for f in files]
    r = {"claimed": len(claimed), "old": 0, "new": 0, "gain": [], "loss": [], "xn": 0, "xold": 0, "xnew": 0, "xgain": []}
    where = f"{sample} {nn} ({corpus} PDF {page})"
    for n in claimed:
        a, b = hit(OLD_NS, n, texts), hit(NEW_NS, n, texts)
        r["old"] += bool(a); r["new"] += bool(b)
        if b and not a: r["gain"].append((n, b, where))
        if a and not b: r["loss"].append((n, a, where))
    low = {c.lower() for c in claimed}
    for n in others:
        if n.lower() in low:
            continue
        r["xn"] += 1
        a, b = hit(OLD_NS, n, texts), hit(NEW_NS, n, texts)
        r["xold"] += bool(a); r["xnew"] += bool(b)
        if b and not a: r["xgain"].append((n, b, where))
    return r


def register(path):
    reg = {}
    for r in csv.DictReader((l for l in open(path, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        k = (r["letter"], r["written"])
        reg[k] = max(reg.get(k, 0.0), float(r["share"]))
    return reg


def cause(reg, name, word):
    """The register's confusion that best explains name → word, and its share: the largest share among the letter
    changes between the two (lower case, accents kept)."""
    a = max(re.findall(r"[^\W\d_]+", name.lower()) or [name.lower()], key=len)
    b = re.sub(r"[^\w]", "", word.lower())
    best = ("", 0.0)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        pairs = [(a[i1:i2], b[j1:j2])] + ([(a[i1 + k], b[j1 + k]) for k in range(i2 - i1)] if i2 - i1 == j2 - j1 else [])
        for x, y in pairs:
            s = reg.get((x, y), 0.0)
            if s > best[1]:
                best = (f"«{y}» for «{x}»", s)
    return best


def band(s):
    return next(b for t, b in BANDS if s >= t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", required=True); ap.add_argument("--write", required=True)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    a = ap.parse_args()
    if os.path.exists(a.write):
        sys.exit(f"refusing: {a.write} exists")
    samples = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(G, "sources", "**", "RETURNS.md"), recursive=True)
                     if os.path.exists(os.path.join(os.path.dirname(p), "KEY.tsv")) and "/archive/" not in p)
    jobs = []
    for d in samples:
        ps = pages(d)
        for i, p in enumerate(ps):
            nxt = ps[(i + 1) % len(ps)][6] if len(ps) > 1 else []
            jobs.append(p + (nxt,))
    with Pool(a.jobs, initializer=init, initargs=(a.new,)) as pool:
        res = pool.map(job, jobs, chunksize=4)
    reg = register(a.new)
    T = collections.Counter()
    gains, losses, xgains = [], [], []
    for r in res:
        for k in ("claimed", "old", "new", "xn", "xold", "xnew"):
            T[k] += r[k]
        gains += r["gain"]; losses += r["loss"]; xgains += r["xgain"]
    pct = lambda x, n: f"{100 * x / max(n, 1):.1f}%"
    L = ["# The name search with two confusion tables, on every G5 sample", "",
         f"`[GENERATED by tools/ocr-confusions-g5.py. Do not hand-edit. Old: tools/ocr-name-search-confusions.tsv (the "
         f"2026-10-05 accent table); new: {os.path.relpath(a.new, os.path.join(HERE, '..'))}. {len(samples)} samples, "
         f"{len(jobs)} ledger pages with judged names, searched as ocr-g5-sample.py score searches them (the class's "
         f"absence side). The samples' texts are as they stood when each was drawn.]`", "",
         "| | old table | new register |", "|---|---:|---:|",
         f"| judged names found (of {T['claimed']}) | {T['old']} ({pct(T['old'], T['claimed'])}) | {T['new']} ({pct(T['new'], T['claimed'])}) |",
         f"| another page's names found (of {T['xn']}; most likely false hits) | {T['xold']} ({pct(T['xold'], T['xn'])}) | {T['xnew']} ({pct(T['xnew'], T['xn'])}) |",
         "", "## Judged names found by the new register only, by the share of the confusion that made the match", ""]
    for title, rows in (("found by the new register only", gains), ("another page's names hit by the new register only (false hits)", xgains)):
        by = collections.defaultdict(list)
        for n, w, where in rows:
            c, s = cause(reg, n, w)
            by[band(s)].append((n, w, c, s, where))
        L += [f"### {title}: {len(rows)}", "", "| share band | names |", "|---|---:|"]
        L += [f"| {b} | {len(by[b])} |" for _, b in BANDS]
        L.append("")
        for _, b in BANDS:
            for n, w, c, s, where in sorted(by[b], key=lambda x: -x[3]):
                L.append(f"- [{b}] «{n}» matched «{w}» · {c or 'no register row explains it'}{f' ({100 * s:.1f}%)' if s else ''} · {where}")
        L.append("")
    L += [f"## Judged names found by the old table only: {len(losses)}", ""]
    L += [f"- «{n}» matched «{w}» · {where}" for n, w, where in losses]
    open(a.write, "x", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"{len(jobs)} pages; found old {T['old']}/{T['claimed']}, new {T['new']}/{T['claimed']}; false-hit proxy old "
          f"{T['xold']}/{T['xn']}, new {T['xnew']}/{T['xn']}; {len(gains)} gained, {len(losses)} lost → {a.write}")


if __name__ == "__main__":
    main()
