#!/usr/bin/env python3
"""ocr-duplicate-pages — pages scanned twice inside one file: find them, take the second copy out of the readings.

    python3 tools/ocr-duplicate-pages.py find --items <ITEMS.txt> --out <new .tsv> [--min-words 40] [--min-share 0.6]
    python3 tools/ocr-duplicate-pages.py withdraw [--list <DUPLICATE-PAGES.tsv>] [--dry]
    python3 tools/ocr-duplicate-pages.py check [--list <DUPLICATE-PAGES.tsv>]
    python3 tools/ocr-duplicate-pages.py settle --found <find .tsv> --pages ITEM:P,P,… [ITEM:…] --status kept|withdrawn --ruling "<paraphrase>"
    python3 tools/ocr-duplicate-pages.py blocks --found <find .tsv> --out <new .md>
    python3 tools/ocr-duplicate-pages.py library --items <ITEMS.txt> [--dry] [--ruling "<paraphrase>"]

WHY (cupel19c C6.4.1, 2026-10-30). The page-number checks found files that hold pages twice: twelve *Kroata
Esperantisto* files of 1909–1910 hold their whole issue twice (ÖNB scanned two copies into one file), *Dana
Esperantisto* 1911 no. 59 its pp. 45–50 twice, each part of the Ido *Nuva adresaro dokumentizita* one page again
under a colour card. Their words counted twice in the corpus. The run sheet deleted a duplicate FILE (the editor,
2026-10-20); nothing took out a duplicate PAGE. The editor, 2026-10-30 10:0x: the duplicate pages taken out, the means
built.

FIND. Per item, the base reading of each page (`page-NNNN.txt`), its words of four letters or more, lower-cased, as a
set; every pair of pages with at least --min-words such words each whose sets share at least --min-share of their
union (Jaccard; the Kroata second copies 0.72–1.00, unrelated pages under 0.1) is a candidate: the later page the copy,
the earlier the one kept. A pair sharing less, but with at least --min-contained of the shorter page's words in the
other, is one too, the SHORTER page the copy: a page scanned again half under a colour card (the Ido parts' PDF 13–14,
0.63–0.86), or a neighbour's edge caught in the margin of a cover (the civil servants' list PDF 2, 0.75). A copy
matching several pages keeps the strongest; a kept page that is itself a copy is followed back to the page kept. Two pages that really were printed twice (an
advertisement page repeated in a bound year) are candidates too: the operator settles each on the printed numbers and
the layout before it goes into the list. WRITES --out only (refused if it exists).

WITHDRAW. Each row of the list whose status is «withdrawn» (columns: item, page, same_as, printed, share, words,
found_by, ruling, status, date): every `page-NNNN.*` of that page in `sources/ocr-rendersearch/<item>/` is moved to
`sources/ocr-withdrawn-pages/<item>/` (a second time, after a re-read: to `…/<item>/again-<YYYYMMDD-HHMMSS>/`), and
empty `page-NNNN.txt` and `page-NNNN.psm4.txt` are left where they were, so the page reads as a blank leaf and every
tool that walks the pages finds it; its section of `<item>.txt` keeps its «=== page N ===» line and loses its text, and so
does its section of `sources/ocr-preferred/<item>.txt` where the item has one (the text the dowse, the word counts and the
harvest read: the first whole-corpus withdrawal, 2026-10-30, left 50 pages, 21,883 words, there). The PDF page numbers hold
throughout; a PDF/A built later gives a withdrawn page its readings from the store, or none (run sheet C6.4.1, not built).
Run again after any re-read of a listed item: the chain does (`tools/ocr-chain.sh`, its step «withdrawn», before the
rebuild). Pages already withdrawn are left as they are. The G1 ink test, the gate, the G1 sort and the G5 sample skip
the listed pages (`tools/ocr_withdrawn.py`), so an empty page with ink is not taken for a page we failed to read.

LIBRARY PAGES (2026-11-03; the editor: a library's cover sheet left out): `withdraw` and
`check` read `geniza/ocr/method/LIBRARY-PAGES.tsv` too (the same columns, `same_as` empty), unless --list names one list.
`library --items <ITEMS.txt> [--dry] [--ruling "<paraphrase>"]` finds them: an item's first three and last two pages,
by the markers of `tools/ocr-modern-metadata.py` and the forms found 2026-11-03 (ÖNB's cover sheet, Google's notice in
English or French, Gallica's cover and terms pages, BSB's cover, an Internet Archive notice page with no other text),
pages already listed left out; printed with their opening words; without --dry, appended to LIBRARY-PAGES.tsv as
«withdrawn» (the operator reads the --dry list first). Then `withdraw` and `check`.

CHECK. Every listed page: no text left in its readings, in `<item>.txt` or in `ocr-preferred/<item>.txt`; the kept page not itself withdrawn. Exit 1
otherwise.

SETTLE. Appends the named candidates of a `find` output to the list, with the status and ruling given: «withdrawn»
(then run withdraw and check), or «kept», a candidate ruled not to go (the editor, 2026-10-30 11:5x, on the corpus
review: matter printed more than once in a bound volume stays, advertisements above all, and so does a source scanned
twice on purpose for triangulation; only a second scan of the same leaf goes). `--pages ITEM:all` takes every candidate
of the item. A page already listed is left as it is. Withdraw reads only «withdrawn» rows.

BLOCKS. The review of class B (a block of three or more copies at one distance, the printed numbers not read), one row
a block, the pages already listed (kept or withdrawn) left out. A block whose kept pages are copied at another distance
too is set apart as recurring matter (a wrapper or an advertisement sheet repeated through a bound volume: the editor's
(b), kept); the rest are the possible second scans. Scores under 0.8, share or contained, are marked: the editor found
them the doubtful ones.
"""
import argparse, csv, datetime, importlib.util, os, re, shutil, sys

import ocr_withdrawn as WD

G = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published",
                                  "heterophony-resources", "geniza"))
R = os.path.join(G, "sources", "ocr-rendersearch")
STORE = os.path.join(G, "sources", "ocr-withdrawn-pages")
PREF = os.path.join(G, "sources", "ocr-preferred")
COLS = ["item", "page", "same_as", "printed", "share", "words", "found_by", "ruling", "status", "date"]
WORD = re.compile(r"[^\W\d_]{4,}")


def words(path):
    try:
        return set(w.lower() for w in WORD.findall(open(path, encoding="utf-8", errors="replace").read()))
    except OSError:
        return set()


def find(a):
    if os.path.exists(a.out): sys.exit(f"exists: {a.out}")
    items = [l.strip() for l in open(a.items, encoding="utf-8") if l.strip()]
    out = []
    # written item by item, a progress line every 250 items (a whole-corpus run, 2026-10-30: 14.8 million pairs)
    fo = open(a.out, "w", encoding="utf-8")
    fo.write("item\tpage\tsame_as\tprinted\tshare\tcontained\thow\twords\n"); fo.flush()
    for k, stem in enumerate(items, 1):
        if k % 250 == 0: print(f"{k}/{len(items)} items · {len(out)} candidates", file=sys.stderr, flush=True)
        n0 = len(out)
        d = os.path.join(a.root, stem)
        if not os.path.isdir(d): continue
        pg = {}
        for f in os.listdir(d):
            m = re.fullmatch(r"page-(\d+)\.txt", f)
            if m: pg[int(m.group(1))] = words(os.path.join(d, f))
        nums = sorted(n for n in pg if len(pg[n]) >= a.min_words)
        copy = {}   # copy page → (kept page, share, contained, how)
        for j in nums:
            for i in nums:
                if i >= j: break
                inter = len(pg[i] & pg[j])
                s = inter / (len(pg[i]) + len(pg[j]) - inter); c = inter / min(len(pg[i]), len(pg[j]))
                if s >= a.min_share: cp, kp, how = j, i, "share"
                elif c >= a.min_contained: cp, kp, how = (i, j, "contained") if len(pg[i]) < len(pg[j]) else (j, i, "contained")
                else: continue
                if cp not in copy or (s, c) > copy[cp][1:3]: copy[cp] = (kp, s, c, how)
        # a ring (a copy of b, b of c, c of a: the share and the containment rules can point round; the first corpus
        # run, 2026-10-30, looped on one) is broken at its earliest page, which is kept
        for cp in sorted(copy):
            if cp not in copy: continue
            seen, kp = [cp], copy[cp][0]
            while kp in copy and kp not in seen: seen.append(kp); kp = copy[kp][0]
            if kp in seen: del copy[min(seen[seen.index(kp):])]
        for cp in sorted(copy):
            kp, s, c, how = copy[cp]
            seen = {cp}
            while kp in copy and kp not in seen: seen.add(kp); kp = copy[kp][0]   # the kept page itself a copy: back to the one kept
            out.append([stem, cp, kp, "", f"{s:.2f}", f"{c:.2f}", how, f"{len(pg[kp])}/{len(pg[cp])}"])
        fo.writelines("\t".join(map(str, r)) + "\n" for r in out[n0:]); fo.flush()
    fo.close()
    print(f"{len(items)} items · {len(out)} candidate pages in {len({r[0] for r in out})} items → {a.out}")


def blank_combined(stem, n, root, dry, preferred=False):
    """Empties page n's section of <stem>.txt (the search text under root, or with preferred the PREFERRED text in
    ocr-preferred/, which the dowse, the word counts and the harvest read); True if it held text."""
    p = os.path.join(PREF if preferred else root, f"{stem}.txt")
    if not os.path.exists(p): return False
    t = open(p, encoding="utf-8", errors="replace").read()
    parts = re.split(r"(?m)^(=== page \d+ ===)$", t)
    changed = False
    for k in range(1, len(parts) - 1, 2):
        if parts[k] == f"=== page {n} ===" and parts[k + 1].strip():
            parts[k + 1] = "\n\n"; changed = True
    if changed and not dry:
        keep = os.path.join(STORE, stem, f"{'preferred-' if preferred else ''}{stem}.txt.before-{datetime.datetime.now():%Y%m%d-%H%M%S}")
        os.makedirs(os.path.dirname(keep), exist_ok=True); shutil.copy2(p, keep)   # the assembly as it was
        with open(p, "w", encoding="utf-8") as f: f.write("".join(parts))
    return changed


def withdraw(a):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    moved = blanked = pblanked = 0
    for stem, pages in sorted(WD.table(a.list).items()):
        d = os.path.join(a.root, stem)
        if not os.path.isdir(d): print(f"no reading folder: {stem}"); continue
        for n in sorted(pages):
            pre = f"page-{n:04d}."; stubs = {pre + "txt", pre + "psm4.txt"}
            files = sorted(f for f in os.listdir(d) if f.startswith(pre))
            live = [f for f in files if not (f in stubs and os.path.getsize(os.path.join(d, f)) == 0)]
            if live:
                store = os.path.join(a.store, stem)
                if any(os.path.exists(os.path.join(store, f)) for f in live): store = os.path.join(store, f"again-{stamp}")
                print(f"{stem} PDF {n}: {len(live)} file(s) → {os.path.relpath(store, G)}")
                if not a.dry:
                    os.makedirs(store, exist_ok=True)
                    for f in live: shutil.move(os.path.join(d, f), os.path.join(store, f))
                    for f in stubs & set(files): open(os.path.join(d, f), "w").close()
                moved += 1
            if blank_combined(stem, n, a.root, a.dry): blanked += 1
            if blank_combined(stem, n, a.root, a.dry, preferred=True): pblanked += 1
    print(f"{'(dry) ' if a.dry else ''}{moved} page(s) withdrawn now, {blanked} section(s) of the combined texts emptied, "
          f"{pblanked} of the PREFERRED texts")


def check(a):
    bad = []
    t = WD.table(a.list)
    for stem, pages in sorted(t.items()):
        d = os.path.join(a.root, stem)
        secs = {}
        for name, comb in ((f"{stem}.txt", os.path.join(a.root, f"{stem}.txt")), (f"ocr-preferred/{stem}.txt", os.path.join(PREF, f"{stem}.txt"))):
            if os.path.exists(comb):
                parts = re.split(r"(?m)^=== page (\d+) ===$", open(comb, encoding="utf-8", errors="replace").read())
                secs[name] = {int(parts[k]): parts[k + 1] for k in range(1, len(parts) - 1, 2)}
        for n, keep in sorted(pages.items()):
            pre = f"page-{n:04d}."
            full = [f for f in (os.listdir(d) if os.path.isdir(d) else []) if f.startswith(pre)
                    and os.path.getsize(os.path.join(d, f)) > 0]
            if full: bad.append(f"{stem} PDF {n}: text left in {', '.join(sorted(full))}")
            for name, sec in secs.items():
                if sec.get(n, "").strip(): bad.append(f"{stem} PDF {n}: text left in {name}")
            if keep is not None and keep in pages: bad.append(f"{stem} PDF {n}: its kept page {keep} is withdrawn too")
    n = sum(len(p) for p in t.values())
    print(f"{n} page(s) listed in {len(t)} item(s); {len(bad)} fault(s)")
    for b in bad: print("  " + b)
    sys.exit(1 if bad else 0)


def review(a):
    """The editor's review of a `find` output (2026-10-30, the whole corpus: 3,169 candidates): each pair classed by
    the printed numbers the page map read (`ocr/runs/OCR-PAGE-MAP.tsv`, source «read») and by its pattern. A: the same
    printed number on both pages; B: a block, three or more copies at one distance (the *Kroata* second copies), the
    numbers not read; C: different printed numbers (matter printed twice, not a second scan); D: a single pair, the
    numbers not read (advertisements, covers, a list repeated; a page rescanned under a colour card is one too)."""
    if os.path.exists(a.out): sys.exit(f"exists: {a.out}")
    pm = {}
    for r in csv.DictReader((l for l in open(a.page_map, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r["source"] == "read" and r["printed"].strip().isdigit(): pm[(r["item"], int(r["pdf_page"]))] = int(r["printed"])
    rows = list(csv.DictReader(open(a.found, encoding="utf-8"), delimiter="\t"))
    off = {}
    for r in rows: off.setdefault((r["item"], int(r["page"]) - int(r["same_as"])), set()).add(int(r["page"]))
    def block(r):
        s = off[(r["item"], int(r["page"]) - int(r["same_as"]))]; p = int(r["page"]); n = 1; q = p - 1
        while q in s: n += 1; q -= 1
        q = p + 1
        while q in s: n += 1; q += 1
        return n
    def head(stem, p):
        f = os.path.join(a.root, stem, f"page-{p:04d}.txt")
        t = open(f, encoding="utf-8", errors="replace").read() if os.path.exists(f) else ""
        return re.sub(r"\s+", " ", t).strip()[:90].replace("|", "/")
    cls = {"A": [], "B": [], "C": [], "D": []}
    for r in rows:
        x, y = pm.get((r["item"], int(r["page"]))), pm.get((r["item"], int(r["same_as"])))
        r["pr"] = f"{x if x is not None else '?'} / {y if y is not None else '?'}"
        k = "A" if x is not None and x == y else "C" if x is not None and y is not None else "B" if block(r) >= 3 else "D"
        cls[k].append(r)
    title = {"A": "A — the same printed number on both pages: a second scan", "B": "B — a block of three or more copies at one distance, the numbers not read: a second scan, most likely",
             "C": "C — different printed numbers: matter printed twice, not a second scan", "D": "D — a single pair, the numbers not read: reprinted matter, most likely, or a page rescanned alone"}
    L = [f"# Pages scanned twice: the review of `{os.path.basename(a.found)}`", "",
         f"By `tools/ocr-duplicate-pages.py review`. {len(rows)} candidate pages in {len({r['item'] for r in rows})} items. PDF page = the order in the scan; «printed» = the page map's number as read (`?` not read), copy / kept. Share = Jaccard of the two pages' word sets; contained = the shorter page's words held in the other.", ""]
    L += [f"- **{title[k]}**: {len(v)} pages in {len({r['item'] for r in v})} items" for k, v in cls.items()] + [""]
    for k in "AB":
        L += [f"## {title[k]}", "", "| item | PDF copy = kept | printed | share · contained | copy begins | kept begins |", "|---|---|---|---|---|---|"]
        for r in sorted(cls[k], key=lambda r: (r["item"], int(r["page"]))):
            L.append(f"| `{r['item']}` | {r['page']} = {r['same_as']} | {r['pr']} | {r['share']} · {r['contained']} | {head(r['item'], int(r['page']))} | {head(r['item'], int(r['same_as']))} |")
        L.append("")
    for k in "CD":
        L += [f"## {title[k]}", "", "Every pair, by item; the first words of the first pair of each item.", ""]
        by = {}
        for r in cls[k]: by.setdefault(r["item"], []).append(r)
        for it in sorted(by):
            v = sorted(by[it], key=lambda r: int(r["page"])); r0 = v[0]
            L.append(f"- `{it}` ({len(v)}): " + ", ".join(f"{r['page']}={r['same_as']} ({r['share']}·{r['contained']})" for r in v)
                     + f". First: «{head(it, int(r0['page']))[:60]}» = «{head(it, int(r0['same_as']))[:60]}»")
        L.append("")
    with open(a.out, "w", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
    print(" · ".join(f"{k} {len(v)}" for k, v in cls.items()), f"→ {a.out}")


def settle(a):
    found = list(csv.DictReader(open(a.found, encoding="utf-8"), delimiter="\t"))
    have = {(r["item"].strip(), int(r["page"])) for r in WD.rows(a.list)}
    pm = {}
    for r in csv.DictReader((l for l in open(a.page_map, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r["source"] == "read": pm[(r["item"], int(r["pdf_page"]))] = r["printed"].strip()
    new, missing = [], []
    for spec in a.pages:
        stem, _, ps = spec.rpartition(":")
        cand = {int(r["page"]): r for r in found if r["item"] == stem}
        want = sorted(cand) if ps == "all" else [int(p) for p in ps.split(",")]
        for p in want:
            if p not in cand: missing.append(f"{stem} PDF {p}"); continue
            if (stem, p) in have: continue
            r = cand[p]
            new.append([stem, p, r["same_as"], pm.get((stem, p), ""), f"{r['how']} {r['share']}·{r['contained']}", r["words"],
                        f"tools/ocr-duplicate-pages.py find ({os.path.relpath(a.found, G)})", a.ruling, a.status,
                        datetime.date.today().isoformat()])
    if missing: sys.exit("not candidates in --found: " + "; ".join(missing))
    head = not os.path.exists(a.list)
    with open(a.list, "a", encoding="utf-8") as f:
        if head: f.write("\t".join(COLS) + "\n")
        f.writelines("\t".join(map(str, r)) + "\n" for r in new)
    print(f"{len(new)} row(s) «{a.status}» added to {os.path.relpath(a.list, G)}")


# LIBRARY PAGES (2026-11-03; the editor: a library's cover sheet left out). The markers of
# tools/ocr-modern-metadata.py (2026-10-10: ÖNB's field words, two at least; Google's preface; «Internet Archive» with
# «digitized»), and what the corpus-wide scan of 2026-11-03 found besides: Google's preface in French and its
# «reproduction of a library book» form, Gallica's cover and terms pages, BSB's cover. A Gallica, BSB or Internet Archive
# page counts only when short (its text the library's alone): a page of text carrying a footer stamp stays.
_MM = importlib.util.spec_from_file_location("ocr_modern_metadata", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                                 "ocr-modern-metadata.py"))
# Google's preface by its own words only: a books.google link in an article is no notice (IPI 107 p. 3, tested 2026-11-03)
GOOGLE2 = re.compile(r"digital copy of a book|copie num.rique d.un ouvrage|digitized\s+by\s+Google\s+as\s+part", re.I)
GALLICA_TERMS = re.compile(r"contenus accessibles sur le site Gallica|conditions d.utilisation", re.I)
# Gallica's cover sheet carries its logo word «Gallica»; a page of the book carries only its footer «Source gallica.bnf.fr»
# (Einstein 1889 p. 1, Zakrzewski 1913 p. 1: stay)
GALLICA = re.compile(r"(?<![\w./])Gallica(?![\w.])")
ONB_FIELD = re.compile(r"Zitierlink|Signatur\s*:|Umfang\s*:", re.I)
BSB = re.compile(r"Bayerische\s*Staats\s*Bibliothek|Digitali\w*\s*Zentrum|Digitale\s+Bibliothek", re.I)
SHORT = 60   # words of three letters or more


def library_kind(t, MM):
    n = len(re.findall(r"[^\W\d_]{3,}", t))
    # ÖNB: two field words AND a catalogue field; «Nationalbibliothek» on the shelf label of a volume's own photographed
    # cover, with the page footer's «data.onb», is two words but the source's page (58 such page 2s, tested 2026-11-03)
    if sum(1 for rx in MM.ONB if rx.search(t)) >= 2 and ONB_FIELD.search(t): return "ÖNB's cover sheet"
    if GOOGLE2.search(t): return "Google's notice"
    if GALLICA_TERMS.search(t) and GALLICA.search(t): return "Gallica's terms page"
    if n < SHORT and GALLICA.search(t) and len(t.strip().splitlines()) > 3: return "Gallica's cover sheet"
    if n < SHORT and BSB.search(t): return "BSB's cover sheet"
    if n < SHORT and MM.ARCH.search(t) and MM.DIGI.search(t): return "the Internet Archive's notice (its only text)"
    return ""


def library(a):
    try:
        MM = importlib.util.module_from_spec(_MM); _MM.loader.exec_module(MM)
    except Exception as e:
        sys.exit(f"cannot load tools/ocr-modern-metadata.py: {e}")
    items = [l.strip() for l in open(a.items, encoding="utf-8") if l.strip()]
    have = {(r["item"].strip(), int(r["page"])) for p in WD.LISTS for r in WD.rows(p)}
    new = []
    for stem in items:
        d = os.path.join(a.root, stem)
        if not os.path.isdir(d): continue
        nums = sorted({int(m.group(1)) for f in os.listdir(d) for m in [re.match(r"page-(\d+)\.txt$", f)] if m})
        for p in sorted(set(nums[:3] + nums[-2:])):
            if (stem, p) in have: continue
            t = "\n".join(open(os.path.join(d, f"page-{p:04d}{k}.txt"), encoding="utf-8", errors="replace").read()
                          for k in ("", ".tl", ".vision") if os.path.exists(os.path.join(d, f"page-{p:04d}{k}.txt")))
            kind = library_kind(t, MM)
            if kind:
                head = " / ".join(x.strip() for x in t.splitlines() if x.strip())[:110]
                new.append((stem, p, kind, len(re.findall(r"[^\W\d_]{3,}", t)), head))
    for stem, p, kind, n, head in new:
        print(f"{stem} PDF {p}: {kind} ({n} words) «{head}»")
    print(f"{'(dry) ' if a.dry else ''}{len(new)} library page(s) found in {len(items)} item(s), none listed before")
    if a.dry or not new: return
    if not a.ruling: sys.exit("library without --dry needs --ruling")
    with open(WD.LIBRARY, "a", encoding="utf-8") as f:
        f.writelines("\t".join(map(str, [stem, p, "", "", kind, n, "tools/ocr-duplicate-pages.py library (each read by the "
                     "operator before the run)", a.ruling, "withdrawn", datetime.date.today().isoformat()])) + "\n"
                     for stem, p, kind, n, _ in new)
    print(f"{len(new)} row(s) «withdrawn» added to {os.path.relpath(WD.LIBRARY, G)}; now withdraw and check")


def blocks(a):
    if os.path.exists(a.out): sys.exit(f"exists: {a.out}")
    pm = {}
    for r in csv.DictReader((l for l in open(a.page_map, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r["source"] == "read" and r["printed"].strip().isdigit(): pm[(r["item"], int(r["pdf_page"]))] = int(r["printed"])
    listed = {(r["item"].strip(), int(r["page"])): r["status"].strip() for r in WD.rows(a.list)}
    rows = list(csv.DictReader(open(a.found, encoding="utf-8"), delimiter="\t"))
    off = {}
    for r in rows: off.setdefault((r["item"], int(r["page"]) - int(r["same_as"])), set()).add(int(r["page"]))
    def run(r):   # the length of the run of copies at r's distance through r, as review's class B
        s = off[(r["item"], int(r["page"]) - int(r["same_as"]))]; p = int(r["page"]); n = 1; q = p - 1
        while q in s: n += 1; q -= 1
        q = p + 1
        while q in s: n += 1; q += 1
        return n
    def head(stem, p):
        f = os.path.join(a.root, stem, f"page-{p:04d}.txt")
        t = open(f, encoding="utf-8", errors="replace").read() if os.path.exists(f) else ""
        return re.sub(r"\s+", " ", t).strip()[:70].replace("|", "/")
    B, skipped = {}, {}
    for r in rows:
        k = (r["item"], int(r["page"]))
        x, y = pm.get(k), pm.get((r["item"], int(r["same_as"])))
        if x is not None and y is not None or run(r) < 3: continue   # class A or C, or not in a block
        if k in listed: skipped.setdefault(listed[k], set()).add(r["item"]); continue
        B.setdefault((r["item"], int(r["page"]) - int(r["same_as"])), []).append(r)
    kept_at = {}
    for (it, d), v in B.items():
        for r in v: kept_at.setdefault((it, int(r["same_as"])), set()).add(d)
    second, recur = [], []
    for (it, d), v in sorted(B.items(), key=lambda kv: (kv[0][0], min(int(r["page"]) for r in kv[1]))):
        v.sort(key=lambda r: int(r["page"]))
        again = sum(1 for r in v if len(kept_at[(it, int(r["same_as"]))]) > 1)
        (recur if again * 2 > len(v) else second).append((it, d, v))
    def line(it, d, v):
        lo = [r for r in v if float(r["share"]) < 0.8 or float(r["contained"]) < 0.8]
        sc = ", ".join(f"{r['page']}={r['same_as']} ({r['share']}·{r['contained']}{' ↓' if r in lo else ''})" for r in v)
        r0 = v[0]
        return (f"| `{it}` | {v[0]['page']}–{v[-1]['page']} = {v[0]['same_as']}–{v[-1]['same_as']} | {len(v)} | {len(lo)} | {sc} "
                f"| {head(it, int(r0['page']))} | {head(it, int(r0['same_as']))} |")
    th = ["| item | PDF copies = kept | pages | under .8 | each pair (share·contained; ↓ under .8) | first copy begins | its kept page begins |",
          "|---|---|---|---|---|---|---|"]
    L = [f"# Class B, block by block: the possible second scans in `{os.path.basename(a.found)}`", "",
         f"By `tools/ocr-duplicate-pages.py blocks`. Class B: three or more pages in a row copied at one distance, the printed numbers not read. PDF page = the order in the scan. Left out, already settled in `ocr/method/DUPLICATE-PAGES.tsv`: "
         + ("; ".join(f"{s}: " + ", ".join(f"`{i}`" for i in sorted(v)) for s, v in sorted(skipped.items())) or "none") + ".", "",
         f"- **Possible second scans** (one distance only): {sum(len(v) for _, _, v in second)} pages in {len(second)} blocks, {len({i for i, _, _ in second})} items",
         f"- **Recurring matter** (the kept pages copied at another distance too: a wrapper or advertisement sheet repeated through a bound volume; kept by the editor's ruling): {sum(len(v) for _, _, v in recur)} pages in {len(recur)} blocks, {len({i for i, _, _ in recur})} items", "",
         "## Possible second scans", ""] + th + [line(*b) for b in second] + ["",
         "## Recurring matter (set apart, kept)", ""] + th + [line(*b) for b in recur] + [""]
    with open(a.out, "w", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
    print(f"possible second scans {sum(len(v) for _, _, v in second)} pages / {len(second)} blocks · recurring "
          f"{sum(len(v) for _, _, v in recur)} / {len(recur)} · skipped {sum(len(v) for v in skipped.values())} item(s) → {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["find", "withdraw", "check", "review", "settle", "blocks", "library"])
    ap.add_argument("--pages", nargs="+"); ap.add_argument("--status", choices=["kept", "withdrawn"]); ap.add_argument("--ruling")
    ap.add_argument("--found"); ap.add_argument("--page-map", default=os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv"))
    ap.add_argument("--items"); ap.add_argument("--out")
    ap.add_argument("--min-words", type=int, default=40); ap.add_argument("--min-share", type=float, default=0.6)
    ap.add_argument("--min-contained", type=float, default=0.6)
    # --list: withdraw and check read both lists (duplicates and library pages, tools/ocr_withdrawn.py) unless one is named;
    # settle, review and blocks work on the duplicates list unless another is named
    ap.add_argument("--list", default=None); ap.add_argument("--root", default=R); ap.add_argument("--store", default=STORE)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd not in ("withdraw", "check") and not a.list: a.list = WD.LIST
    if a.cmd == "find":
        if not (a.items and a.out): sys.exit("find needs --items and --out")
        find(a)
    elif a.cmd == "review":
        if not (a.found and a.out): sys.exit("review needs --found and --out")
        review(a)
    elif a.cmd == "settle":
        if not (a.found and a.pages and a.status and a.ruling): sys.exit("settle needs --found, --pages, --status and --ruling")
        settle(a)
    elif a.cmd == "blocks":
        if not (a.found and a.out): sys.exit("blocks needs --found and --out")
        blocks(a)
    elif a.cmd == "library":
        if not a.items: sys.exit("library needs --items")
        library(a)
    elif a.cmd == "withdraw": withdraw(a)
    else: check(a)


if __name__ == "__main__":
    main()
