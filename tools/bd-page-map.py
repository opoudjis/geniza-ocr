#!/usr/bin/env python3
"""bd-page-map — for a born-digital text that is a copy of a scanned work, the PDF page of the scan on which each of its
paragraphs (¶ N) falls, so that a hit found only in the born-digital text still carries a page a reader can check.

WHY (2026-10-10): the editor, on The Esperantist 1903–04, held both as Project Gutenberg e-books and as a scan
; then approved to a paragraph-to-page
map for each typed issue; then
(geniza/QUEUE.md, under the ARCHIVE.ORG OCR ruling).

HOW: ¶ numbers are the dowse's own (born_digital_lines.blocks: every non-blank block, headings included). The scan's
text is its search text, sources/ocr-rendersearch/<item>.txt. Both are reduced to bare letters (accents dropped,
lower case), and every 24-letter run of a paragraph (every 4th letter) is looked up among the scan's pages: the same
matching that placed the born-digital texts in their scans for the copies table. Pass 1 uses only runs found on one page
of the whole scan; the pages so found fix the stretch (unless one is given). Pass 2 counts every run inside the stretch,
so a run repeated elsewhere (an advertisement in every issue) is settled by the stretch, not by a guess.

Status of each ¶, never guessed:
  placed     its runs fall on one page, or on a run of consecutive pages («34–35»: it crosses a page break)
  conflict   its runs fall on pages that are not consecutive; all of them listed
  unplaced   none of its runs was found (OCR too poor there, or the passage is not in the scan, such as a transcriber's note)
  short      under 24 letters, so nothing to look up
Both texts run in the same order, and three steps use that:
  - a placed ¶ that would go back a page against the longest never-decreasing run of placed ¶ is «out of order» and
    becomes unplaced (the note keeps where it was found);
  placed (by order)  repeated text (a grammar synopsis reprinted in every issue), matched only on the pages between its
             placed neighbours, or within 8 pages beyond the one neighbour it has;
  bracketed (unplaced|short)  lies between its placed neighbours' pages: one page where both are on it, else «13–14».
The note gives, for every ¶ not placed by its own text, its neighbours' pages.

    tools/bd-page-map.py --copies                     every born-digital ↔ scan pair in ocr-dowse.py's COPIES table
    tools/bd-page-map.py <bd-item> <scan-item> [N-M]  one pair, the scan's stretch optional

Writes geniza/ocr/page-maps/<bd-item>.tsv (one per born-digital item; rebuilt each run, since it is derived from fixed
texts) and geniza/ocr/page-maps/SUMMARY.tsv. Nothing else.
"""
import os, re, sys, unicodedata, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import born_digital_lines as BDL  # noqa: E402
G = BDL.G
SCANS = os.path.join(G, "sources", "ocr-rendersearch")
OUT = os.path.join(G, "ocr", "page-maps")
W, STEP = 24, 4

def letters(s):
    return re.sub(r"[^a-z]", "", "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c)))

def scan_pages(item):
    t = open(os.path.join(SCANS, item + ".txt"), encoding="utf-8", errors="ignore").read()
    return {int(n): letters(b) for n, b in re.findall(r"(?ms)^=== page (\d+) ===\n(.*?)(?=^=== page \d+ ===|\Z)", t)}

def index(pages):
    one, many = {}, {}
    for p, s in pages.items():
        for i in range(len(s) - W + 1):
            h = hash(s[i:i + W])
            if h in many: many[h].add(p)
            elif h in one and one[h] != p: many[h] = {one.pop(h), p}
            elif h not in one: one[h] = p
    return one, many

def runs(s):
    return [hash(s[i:i + W]) for i in range(0, len(s) - W + 1, STEP)]

def consecutive(ps):
    return all(b - a == 1 for a, b in zip(ps, ps[1:]))

def fmt(ps):
    return str(ps[0]) if len(ps) == 1 else f"{ps[0]}–{ps[-1]}"

def map_pair(bd, scan, stretch=None):
    text = open(BDL.text_path(BDL.lists("proposed")[bd]), encoding="utf-8").read()
    blocks = BDL.blocks(text)
    pages = scan_pages(scan)
    one, many = index(pages)
    rs = [runs(letters(b)) for _, _, b in blocks]
    if stretch == "whole": stretch = (min(pages), max(pages))
    if stretch is None:                       # pass 1: runs found on one page of the whole scan fix the stretch
        found = sorted({one[h] for r in rs for h in r if h in one})
        if not found: return blocks, [["unplaced", [], 0, len(r), "nothing found in the scan"] for r in rs], None
        # the stretch: the cluster of pages (gaps of up to 3 pages allowed) holding the most uniquely placed runs, so a
        # stray hit far off is ignored
        n = {}
        for r in rs:
            for h in r:
                if h in one: n[one[h]] = n.get(one[h], 0) + 1
        clusters, cur = [], [found[0]]
        for p in found[1:]:
            if p - cur[-1] > 3: clusters.append(cur); cur = [p]
            else: cur.append(p)
        clusters.append(cur)
        best = max(clusters, key=lambda c: sum(n[p] for p in c))
        stretch = (best[0], best[-1])
    lo, hi = stretch

    def count(r, ok):
        """pages (within ok) on which the runs of r fall; a run counts only where it falls on one such page."""
        cnt = {}
        for h in r:
            ps = [p for p in ([one[h]] if h in one else many.get(h, ())) if ok(p)]
            if len(ps) == 1: cnt[ps[0]] = cnt.get(ps[0], 0) + 1
        return cnt

    def choose(cnt, r):
        ps = sorted(p for p, c in cnt.items() if c >= 2 or len(r) <= 3 or len(cnt) == 1)
        return ps or sorted(cnt)

    res = []                                    # [status, pages, runs found, runs, note]
    for r in rs:                                # pass 2: every run, counted only on pages inside the stretch
        if not r: res.append(["short", [], 0, 0, ""]); continue
        cnt = count(r, lambda p: lo <= p <= hi)
        if not cnt: res.append(["unplaced", [], 0, len(r), ""]); continue
        ps = choose(cnt, r)
        res.append(["placed" if consecutive(ps) else "conflict", ps, sum(cnt.values()), len(r), ""])

    # order: both texts run in the same order, so the placed ¶ must never go back a page. The longest run of placed ¶
    # whose pages never decrease is kept; any other placed ¶ is «out of order» (its pages kept in the note) and unplaced.
    idx = [i for i, x in enumerate(res) if x[0] == "placed"]
    best, prevp = [1] * len(idx), [-1] * len(idx)
    for a in range(len(idx)):
        for b in range(a):
            if res[idx[b]][1][-1] <= res[idx[a]][1][0] and best[b] + 1 > best[a]: best[a], prevp[a] = best[b] + 1, b
    keep, a = set(), (max(range(len(idx)), key=lambda k: best[k]) if idx else -1)
    while a >= 0: keep.add(idx[a]); a = prevp[a]
    for i in idx:
        if i not in keep: res[i] = ["unplaced", [], res[i][2], res[i][3], "out of order: found on PDF " + fmt(res[i][1])]

    def neighbours(i):
        prev = next((res[j][1] for j in range(i - 1, -1, -1) if res[j][0].startswith("placed")), None)
        nxt = next((res[j][1] for j in range(i + 1, len(res)) if res[j][0].startswith("placed")), None)
        return prev, nxt

    # repeated text (a grammar synopsis reprinted in every issue): its runs fall on many pages of the scan, so it is
    # matched only on the pages between its placed neighbours, or within 8 pages beyond the one neighbour it has.
    for i, x in enumerate(res):
        if x[0] != "unplaced" or not x[3]: continue
        prev, nxt = neighbours(i)
        if prev is None and nxt is None: continue
        a = prev[-1] if prev else nxt[0] - 8
        b = nxt[0] if nxt else prev[-1] + 8
        cnt = count(rs[i], lambda p: a <= p <= b)
        if cnt:
            ps = choose(cnt, rs[i])
            if consecutive(ps) and sum(cnt.values()) >= 2:
                res[i] = ["placed (by order)", ps, sum(cnt.values()), x[3], (x[4] + "; " if x[4] else "") + f"matched within PDF {a}–{b}"]

    # what is left lies between its placed neighbours' pages: «bracketed», one page where both neighbours are on it
    for i, x in enumerate(res):
        if x[0] not in ("short", "unplaced"): continue
        prev, nxt = neighbours(i)
        x[4] = (x[4] + "; " if x[4] else "") + f"between {prev[-1] if prev else '?'} and {nxt[0] if nxt else '?'}"
        if prev and nxt and prev[-1] <= nxt[0]:
            res[i] = ["bracketed (" + x[0] + ")", [prev[-1]] if prev[-1] == nxt[0] else [prev[-1], nxt[0]], x[2], x[3], x[4]]
    return blocks, res, stretch

def write(bd, scan, blocks, res, stretch):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, bd + ".tsv"), "w", encoding="utf-8") as f:
        f.write(f"# {bd}: the PDF page of {scan} (sources/ocr-rendersearch) for each ¶; written by tools/bd-page-map.py. "
                f"Stretch PDF {fmt(list(stretch)) if stretch else 'none found'}. Runs: {W} letters, every {STEP}th.\n")
        f.write("para\tsection\tpdf_pages\tstatus\truns_found\truns\tnote\topening\n")
        for (n, sec, b), (st, ps, k, t, note) in zip(blocks, res):
            opening = re.sub(r"[\t\n]", " ", b[:40])
            f.write(f"{n}\t{sec}\t{fmt(ps) if ps else ''}\t{st}\t{k}\t{t}\t{note}\t{opening}\n")
    K = ("placed", "bracketed", "conflict", "unplaced", "short")
    c = {s: sum(1 for x in res if x[0].startswith(s)) for s in K}
    return [bd, scan, fmt(list(stretch)) if stretch else "", str(len(res))] + [str(c[s]) for s in K]

def copies_pairs():
    s = importlib.util.spec_from_file_location("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
    d = importlib.util.module_from_spec(s); s.loader.exec_module(d)
    bds = BDL.lists("proposed")
    pairs, skipped = [], []
    for c in d.COPIES:
        bd = [(i, st, r) for i, st, r in c["copies"] if i in bds]
        sc = [(i, st, r) for i, st, r in c["copies"] if i not in bds and os.path.isfile(os.path.join(SCANS, i + ".txt"))]
        for b in bd:
            for s_ in sc:
                # a translation cannot be matched by its letters: Russian against Esperanto, German against Russian
                if re.search(r"transl|Russian|German", b[2] + " " + s_[2]): skipped.append((b[0], s_[0])); continue
                pairs.append((b[0], s_[0], s_[1] or "whole"))   # None in the table: the work is the whole scan
    return pairs, skipped

def main():
    a = sys.argv[1:]
    if a == ["--copies"]:
        pairs, skipped = copies_pairs()
        for b, s in skipped: print(f"skipped (a translation): {b} ↔ {s}")
    elif len(a) in (2, 3):
        st = tuple(int(x) for x in a[2].split("-")) if len(a) == 3 else None
        pairs = [(a[0], a[1], st)]
    else:
        sys.exit(__doc__)
    rows = []
    for b, s, st in pairs:
        blocks, res, stretch = map_pair(b, s, st)
        rows.append(write(b, s, blocks, res, stretch))
        print("\t".join(rows[-1]))
    sp = os.path.join(OUT, "SUMMARY.tsv")
    old = {}
    if os.path.exists(sp):
        for l in open(sp, encoding="utf-8"):
            if not l.startswith(("#", "bd_item\t")): old[l.split("\t")[0]] = l.rstrip("\n").split("\t")
    for r in rows: old[r[0]] = r
    with open(sp, "w", encoding="utf-8") as f:
        f.write("# Paragraph-to-page maps, one row per born-digital item (tools/bd-page-map.py).\n")
        f.write("bd_item\tscan\tstretch\tparas\tplaced\tbracketed\tconflict\tunplaced\tshort\n")
        for k in sorted(old): f.write("\t".join(old[k]) + "\n")

if __name__ == "__main__":
    main()
