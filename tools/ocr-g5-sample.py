#!/usr/bin/env python3
r"""ocr-g5-sample — G5, THE VERDICT-CLASS AUDIT: build the blind sample, then score the judges' returns per class.

    tools/ocr-g5-sample.py build --ledger <tsv> --g1 <json> --out <dir> [--n 40] [--seed S]
    tools/ocr-g5-sample.py file  --out <dir> --batch b01 --table <file holding one judge's table>
    tools/ocr-g5-sample.py score --out <dir> --returns <file with the judges' tables>

Approved by the editor, 2026-09-28 22:08 (the proposal: an internal record, 2026-09-28, not published). Every automated
verdict class — including the classes that CLEAR a page — gets its own blind sample of N pages. All pages are shuffled
together into batches of 20; a judge never learns a page's class. ONE brief for every page: coverage (NOTHING / MINOR
/ LOST), orientation (UPRIGHT / ROTATED), Russian printed (NONE / SOME / MUCH), and up to 10 printed personal names.
The SCORE step reads each class against ITS verdict:
  g1-blank       contradicted if the judge finds print the text misses (MINOR or LOST)
  g1-plate       contradicted if LOST
  g1-unread      (a flagging class: its rate is measured, not barred)
  g1-untested    (measured)
  rot-upright    contradicted if ROTATED
  rot-reread     contradicted if LOST (the image is rotated by definition)
  ru-rejected    contradicted if Russian MUCH
  ru-accepted    contradicted if Russian NONE
  ledger-*       NAME RECALL: each name the judge lists is searched with tools/ocr-name-search.py in the text(s)
                 of the class's absence side; a page is contradicted if two or more of its names are not found.
  ledger-eo-side (2026-10-13: the editor decided that their Esperanto side be admitted on name recall, through a G5
                 sample of their own, and approved trying option 1): the pages of the WITH EXCEPTIONS items admitted on the «RUSSIAN side only» (the
                 bi-script runs whose Esperanto side fails G4 on the Russian read as Latin junk), scored on their
                 ESPERANTO side: does the Esperanto search text find the names? Drawn only when --classes names it.
                 Bi-script pages only (with `page-NNNN.eo-gate.txt`); runs of 1914 or before apart, as
                 ledger-eo-side-primary (2026-10-13 20:3x, after a first draw of mostly wholly Russian pages).
                 (An internal record, 2026-10-13, not published: the name look.)
A clearing class passes if at most 1 of its N pages is contradicted (the proposal's bar).
"""
import os, re, sys, json, glob, random, argparse, subprocess, statistics, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
R = os.path.join(G, "sources", "ocr-rendersearch"); RR = os.path.join(G, "sources", "ocr-rendersearch-rus")
RA = os.path.join(G, "sources", "ocr-rendersearch-all")   # every reading on disk, SPECIAL HANDLING items (2026-10-02)
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)
CLEARING = {"g1-blank", "g1-plate", "rot-upright", "rot-reread", "ru-rejected", "ru-accepted",
            "ledger-admissible", "ledger-both", "ledger-eo", "ledger-ru", "ledger-short", "ledger-special", "ledger-exceptions",
            "ledger-eo-side", "ledger-eo-side-primary"}


def pages(path):
    if not os.path.exists(path): return {}
    t = open(path, encoding="utf-8", errors="ignore").read()
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def excluded(exc):
    ex = set()
    for m in re.finditer(r"(?:LOST|MINOR|ADVERTISEMENT page\(s\)) p\.([\d,]+)", exc):   # ad pages: ruling of 2026-10-02
        ex |= {int(x) for x in m.group(1).split(",") if x}
    return ex


def silent_pages(c):
    d = os.path.join(R, c); sz = {}
    for f in glob.glob(os.path.join(d, "page-*.txt")):
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m: sz[int(m.group(1))] = os.path.getsize(f)
    if len(sz) < 3: return []
    med = statistics.median(sz.values())
    return [n for n, s in sz.items() if med and s < med * .25]


def build(a):
    random.seed(a.seed)
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: (l.strip() if l.strip().startswith("/") else os.path.join(ROOT, l.strip()))
            for l in open(a.pdfs) if l.strip()}
    rows = [l.rstrip("\n").split("\t") for l in open(a.ledger, encoding="utf-8") if not l.startswith("#")][1:]
    live = {r[0]: r for r in rows if r[3] in ("ABSENCE-ADMISSIBLE", "SPECIAL HANDLING", "WITH EXCEPTIONS")}
    # --items (cupel, 2026-10-03): sample only a batch's NEW items — one sample across the batch (the editor decided that
    # a batch's new additions be sampled together, for a more global sample). Comma-separated stems, or @file with one stem per line.
    if a.items:
        want_i = set([x.strip() for x in open(a.items[1:], encoding="utf-8").read().splitlines() if x.strip()]) if a.items.startswith("@") else set(a.items.split(","))
        miss = want_i - set(r[0] for r in rows)
        if miss: sys.exit(f"--items not in the ledger: {sorted(miss)}")
        live = {c: r for c, r in live.items() if c in want_i}
    # --scope <tsv> (cupel batch 1, 2026-10-03): only the pages an item's absence lines will cover (item · pages · kind)
    allowed = None
    if a.scope:
        allowed = collections.defaultdict(set)
        for f in (l.rstrip("\n").split("\t") for l in open(a.scope, encoding="utf-8") if l.strip() and not l.startswith("#")):
            if f[0] != "item": lo_, hi_ = map(int, f[1].split("-")); allowed[f[0]] |= set(range(lo_, hi_ + 1))
        live = {c: r for c, r in live.items() if c in allowed}
    g1 = json.load(open(a.g1))
    pool = collections.defaultdict(list)
    for r in g1:
        c = r["corpus"]
        if c not in live: continue
        bl, un, ut = set(r.get("blank_pages", [])), set(r.get("pages", [])), set(r.get("untested_pages", []))
        pool["g1-blank"] += [(c, p, "eo") for p in bl]; pool["g1-unread"] += [(c, p, "eo") for p in un]
        pool["g1-untested"] += [(c, p, "eo") for p in ut]
        pool["g1-plate"] += [(c, p, "eo") for p in silent_pages(c) if p not in bl | un | ut]
    rot = os.path.join(G, "ocr", "method", "OCR-ROTATION-CHECK-2026-09-28.md")
    for l in open(rot, encoding="utf-8"):
        m = re.match(r"\| (\S+) \| (\d+) \|.*\| KEPT", l)
        if m and m.group(1) in live: pool["rot-reread"].append((m.group(1), int(m.group(2)), "eo"))
    osd = os.path.join(a.scratch, "rot-osd.tsv") if a.scratch else None
    if osd and os.path.exists(osd):
        for f in (l.rstrip("\n").split("\t") for l in list(open(osd))[1:]):
            if f[0] in live and f[3] in ("0", ""): pool["rot-upright"].append((f[0], int(f[1]), "eo"))
    for lj in glob.glob(os.path.join(R, "*", "page-*.layout.json")):
        c = os.path.basename(os.path.dirname(lj))
        if c not in live: continue
        rec = json.load(open(lj)); p = rec["page"]
        pool["ru-rejected" if rec.get("skipped") == "page gate" else "ru-accepted" if rec.get("ru_lines", 0) >= 3 else "_"].append((c, p, "eo"))
    for c, r in live.items():
        t = r[6]; ex = excluded(t); pg = pages(os.path.join(R, c + ".txt"))
        if a.classes_2610:
            # THE CLASSES OF LEDGER 10-01a (the editor's review of 2026-10-01; an internal record, 2026-09-30, not published):
            # ledger-admissible (search the main text) · ledger-special (SPECIAL HANDLING: nothing excluded, search BOTH
            # readings) · ledger-exceptions (WITH EXCEPTIONS: off the excluded pages, on the side the item admits).
            # A SCOPE note limits an item to its scan pages (the Moret article; the Interhelpo piece).
            sc = re.search(r"scan pp\. (\d+)–(\d+)", t)
            scope = range(int(sc.group(1)), int(sc.group(2)) + 1) if t.startswith("SCOPE:") and sc else None
            kh = set()
            for f in glob.glob(os.path.join(R, c, "page-*.kathye.json")):   # Georgian/Armenian pages: presence only
                j = json.load(open(f))
                if j.get("kat_blocks") or j.get("hye_blocks"): kh.add(int(re.search(r"page-(\d+)", f).group(1)))
            if r[3] == "ABSENCE-ADMISSIBLE": cls, side = "ledger-admissible", "eo"
            elif r[3] == "SPECIAL HANDLING": cls, side = "ledger-special", "both"
            else:
                cls = "ledger-exceptions"
                side = ("ru" if "RUSSIAN side only" in t else
                        "eo" if ("ESPERANTO side only" in t or "Russian/Armenian/Georgian PRESENCE ONLY" in t) else "both")
            pool[cls] += [(c, p, side) for p, x in pg.items() if p not in ex and p not in kh
                          and (scope is None or p in scope) and (allowed is None or p in allowed[c]) and len(x.split()) >= 80]
            # the same pages, judged on their ESPERANTO side (docstring); only the bi-script items, whose Esperanto side the
            # gate failed («Esperanto-only <G4> FAILS»): a wholly Russian item has no Esperanto side to admit
            # Second draw (2026-10-13 20:3x, approved by the editor; the first drew mostly wholly Russian pages, 7 of 40 with a
            # Latin name to test): only the BI-SCRIPT pages (the gate's Esperanto extract `page-NNNN.eo-gate.txt` exists),
            # and the runs of 1914 or before (PRIMARY by the date rule) in a class of their own, ledger-eo-side-primary,
            # so the item-weighted draw does not give Kovno Esperanto one page in 40.
            if cls == "ledger-exceptions" and side == "ru" and re.search(r"Esperanto-only [\d.]+ FAILS", t):
                y = re.search(r"(18\d\d|19\d\d)", c)
                k = "ledger-eo-side-primary" if y and int(y.group(1)) <= 1914 else "ledger-eo-side"
                pool[k] += [(c, p, "eo") for p, x in pg.items() if p not in ex and p not in kh
                            and (scope is None or p in scope) and (allowed is None or p in allowed[c])
                            and len(x.split()) >= 80 and os.path.exists(os.path.join(R, c, f"page-{p:04d}.eo-gate.txt"))]
            continue
        cls, side = (("ledger-admissible", "eo") if r[3] == "ABSENCE-ADMISSIBLE" else
                     ("ledger-ru", "ru") if "SPECIAL HANDLING" in t else ("ledger-both", "both") if "both sides pass" in t else
                     ("ledger-eo", "eo") if "ESPERANTO side only" in t else ("ledger-short", "eo") if "IMAGE CHECK" in t else (None, None))
        if cls:
            pool[cls] += [(c, p, side) for p, x in pg.items() if p not in ex and len(x.split()) >= 80]
    # THE RE-SAMPLE (2026-09-30, approved by the editor): only the classes named (--classes), and FRESH pages, avoiding every page of
    # an earlier sample (--avoid <its KEY.tsv>). A class with no more pages than N (rot-reread: 5 in all) is re-judged whole,
    # since there is nothing fresh to draw; the point is then whether its pages have been fixed.
    want = set(a.classes.split(",")) if a.classes else None
    avoid = ({(f[3], int(f[4])) for af in a.avoid.split(",") for f in (l.rstrip("\n").split("\t") for l in open(af)) if len(f) > 4}
             if a.avoid else set())
    picked = []
    for cls, cand in pool.items():
        if cls == "_" or (want and cls not in want): continue
        cand = sorted(set(cand))
        if len(cand) > a.n:
            cand = [x for x in cand if (x[0], x[1]) not in avoid]
        random.shuffle(cand)
        # at most 3 pages from one item, so a class sample is not one item — EXCEPT for a cupel batch (--items), whose
        # sample is meant to range over all the batch's pages (min(40, all pages); editor's D2, 2026-10-03)
        per = collections.Counter(); take = []; cap = a.n if (a.items or a.scope) else 3
        for x in cand:
            if per[x[0]] < cap: take.append(x); per[x[0]] += 1
            if len(take) >= a.n: break
        picked += [(cls, *x) for x in take]
    random.shuffle(picked)
    os.makedirs(a.out, exist_ok=True); key = []
    for i, (cls, c, p, side) in enumerate(picked, 1):
        b = f"b{(i - 1) // 20 + 1:02d}"; d = os.path.join(a.out, b); os.makedirs(d, exist_ok=True); nn = f"{i:03d}"
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", "-f", str(p), "-l", str(p), pdfs[c], os.path.join(d, nn)], capture_output=True)
        open(os.path.join(d, nn + ".esperanto-text.txt"), "w", encoding="utf-8").write(pages(os.path.join(R, c + ".txt")).get(p, ""))
        ru = pages(os.path.join(RR, c + ".txt")).get(p)
        if ru: open(os.path.join(d, nn + ".russian-text.txt"), "w", encoding="utf-8").write(ru)
        # SPECIAL HANDLING searches EVERY reading on disk (the editor's choice of 2026-10-02 22:5x): the scorer searches this file
        # for ledger-special. Not named in the judges' brief, so a judge never reads it.
        if cls == "ledger-special":
            al = pages(os.path.join(RA, c + ".txt")).get(p)
            if al: open(os.path.join(d, nn + ".all-readings.txt"), "w", encoding="utf-8").write(al)
        key.append(f"{nn}\t{b}\t{cls}\t{c}\t{p}\t{side}")
    open(os.path.join(a.out, "KEY.tsv"), "w").write("\n".join(key) + "\n")
    print(len(key), "pages ·", dict(collections.Counter(k.split("\t")[2] for k in key)))


ROW = re.compile(r"\|\s*(\d{3})\s*\|\s*(NOTHING|MINOR|LOST)\s*\|\s*(UPRIGHT|ROTATED)\s*\|\s*(NONE|SOME|MUCH)\s*\|([^|]*)\|")


def file_returns(a):
    # FILE A JUDGE'S RETURN (M4.3, 2026-10-02: done by hand until then). The judge's table, verbatim, is appended to
    # <out>/RETURNS.md under «## <batch> (filed HH:MM)». Refused if the batch is already filed, or if the rows are not
    # exactly the batch's pages in KEY.tsv — so a return can be neither lost nor filed twice.
    import datetime
    key = [l.rstrip("\n").split("\t") for l in open(os.path.join(a.out, "KEY.tsv")) if l.strip()]
    want = {k[0] for k in key if k[1] == a.batch}
    if not want: sys.exit(f"no pages of batch {a.batch} in KEY.tsv")
    table = open(a.table, encoding="utf-8").read().strip()
    got = [m.group(1) for m in (ROW.match(l.strip()) for l in table.split("\n")) if m]
    if set(got) != want or len(got) != len(want):
        sys.exit(f"rows do not match batch {a.batch}: missing {sorted(want - set(got))}, extra {sorted(set(got) - want)}, "
                 f"{len(got)} rows for {len(want)} pages — nothing filed")
    rp = os.path.join(a.out, "RETURNS.md")
    old = open(rp, encoding="utf-8").read() if os.path.exists(rp) else (
        f"# G5 — the judges' returns, verbatim ({datetime.date.today()})\n\nBrief: `BRIEF.md`. Key: `KEY.tsv`. "
        "One blind judge per batch (Read tool only).\n")
    if re.search(rf"^## {re.escape(a.batch)} \(", old, re.M): sys.exit(f"batch {a.batch} is already filed — nothing filed")
    open(rp, "w", encoding="utf-8").write(old.rstrip("\n") + f"\n\n## {a.batch} (filed {datetime.datetime.now():%H:%M})\n\n{table}\n")
    print(f"filed {a.batch}: {len(got)} rows → {rp}")


def score(a):
    key = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(os.path.join(a.out, "KEY.tsv")) if l.strip()}
    J = {}
    for l in open(a.returns, encoding="utf-8"):
        m = re.match(r"\|\s*(\d{3})\s*\|\s*(NOTHING|MINOR|LOST)\s*\|\s*(UPRIGHT|ROTATED)\s*\|\s*(NONE|SOME|MUCH)\s*\|([^|]*)\|", l)
        if m: J[m.group(1)] = (m.group(2), m.group(3), m.group(4), [n.strip() for n in m.group(5).split(";") if n.strip() and n.strip() != "-"])
    res = collections.defaultdict(lambda: [0, 0, []])
    # pages whose text was CORRECTED after the judges saw it are not scored against the old text (tab file: corpus, page)
    drop = {(f[0], int(f[1])) for f in (l.split("\t") for l in open(a.exclude)) if len(f) > 1} if a.exclude else set()
    dropped = []
    for nn, k in key.items():
        if nn not in J: continue
        if (k[3], int(k[4])) in drop: dropped.append(f"{nn} {k[2]} {k[3]} p.{k[4]}"); continue
        cls, c, p, side = k[2], k[3], int(k[4]), k[5]; cov, orient, rus, names = J[nn]
        bad = False
        if cls == "g1-blank": bad = cov in ("MINOR", "LOST")
        elif cls == "g1-plate": bad = cov == "LOST"
        elif cls == "rot-upright": bad = orient == "ROTATED"
        # a re-read page IS rotated on the image — that is why it was re-read; only a lost reading contradicts it
        # (fixed 2026-09-28 after the G5 image checks: 213 and 329 were rotated and correctly read)
        elif cls == "rot-reread": bad = cov == "LOST"
        elif cls == "ru-rejected": bad = rus == "MUCH"
        elif cls == "ru-accepted": bad = rus == "NONE"
        elif cls.startswith("ledger-"):
            d = os.path.join(a.out, k[1])
            texts = [open(os.path.join(d, nn + f), encoding="utf-8", errors="ignore").read() for f in
                     ((".esperanto-text.txt", ".russian-text.txt", ".all-readings.txt") if cls == "ledger-special" else
                      (".esperanto-text.txt", ".russian-text.txt") if a.search_all else
                      (".esperanto-text.txt",) if side == "eo" else (".russian-text.txt",) if side == "ru" else (".esperanto-text.txt", ".russian-text.txt"))
                     if os.path.exists(os.path.join(d, nn + f))]
            cyr = lambda s: bool(re.search("[а-яёѣі]", s.lower()))
            # a name in the other script is not claimed of a one-side text, unless every text of the page is searched
            claimed = names if a.search_all else [n for n in names if not ((side == "eo" and cyr(n)) or (side == "ru" and not cyr(n)))]
            miss = [n for n in claimed if not any(NS.find(n, t) for t in texts)]
            bad = len(miss) >= 2
            res[cls][2].append((nn, len(claimed), len(miss), miss))
        res[cls][0] += 1; res[cls][1] += bad
    out = []
    for cls in sorted(res):
        n, b, det = res[cls]
        # THE BAR (editor 2026-09-30 15:15: at most 1 in 40; D2 of 2026-10-03, ruled per class on 2026-10-04 00:0x, the editor
        # accepting the recommendation on question 4): <= 1 contradicted page at 40 or more pages, 0 below 40 (a small class or batch may not spend the 1)
        verdict = ("PASS" if b <= (1 if n >= 40 else 0) else "FAIL") if cls in CLEARING else "measured"
        extra = ""
        if det:
            tn = sum(x[1] for x in det); tm = sum(x[2] for x in det)
            extra = f" · names {tn - tm}/{tn} found ({100 * (tn - tm) / max(tn, 1):.0f}%)"
        out.append(f"{cls:18} {n:3} pages · contradicted {b:3} ({100 * b / max(n, 1):4.1f}%) · {verdict}{extra}")
    print("\n".join(out))
    if dropped: print(f"excluded {len(dropped)} corrected page(s):", "; ".join(dropped))
    json.dump({k: {"n": v[0], "contradicted": v[1], "names": v[2]} for k, v in res.items()},
              open(os.path.join(a.out, "SCORE-all-texts.json" if a.search_all else "SCORE.json"), "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("build", "file", "score"))
    ap.add_argument("--ledger"); ap.add_argument("--g1"); ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--scratch", default=None); ap.add_argument("--returns"); ap.add_argument("--exclude")
    ap.add_argument("--pdfs", default="/tmp/par/every-pdf.txt", help="the PDF list (default: the 28 Sep run's)")
    ap.add_argument("--avoid", help="build: a previous sample's KEY.tsv; its pages are not drawn again")
    ap.add_argument("--classes", help="build: only these classes, comma-separated")
    ap.add_argument("--classes-2610", action="store_true", help="build: the ledger classes of 10-01a (admissible · special · exceptions)")
    ap.add_argument("--search-all", action="store_true", help="search EVERY text of the page (what a searcher does), not only the class's absence side")
    ap.add_argument("--items", help="build: only these items (comma-separated stems, or @file) — a cupel batch")
    ap.add_argument("--scope", help="build: a scope TSV (item · pages · kind): only those pages are drawn")
    ap.add_argument("--batch", help="file: the batch (b01 …) whose return this is")
    ap.add_argument("--table", help="file: a file holding the judge's table, verbatim")
    a = ap.parse_args()
    {"build": build, "file": file_returns, "score": score}[a.mode](a)
