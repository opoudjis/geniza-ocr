#!/usr/bin/env python3
"""ocr-copy-align.py — two copies of one work, lined up by PRINTED page: which copy holds each page, and how well.

    python3 tools/ocr-copy-align.py --label <name> \
        --a-root <folder of item folders> --a-items <regex> --b-root <folder> --b-items <regex> \
        --out <new .tsv> --md <new .md>

WHY (2026-10-10, the editor on the copies policy, RUNBOOK.md § 2 rule 15: if there are gaps of either coverage or
quality between the two runs, two-copy triangulation is required; if on the other hand the two runs are of identical
quality, one run is deleted. On this tool, the editor expected the question to come up again, wanted it settled, and
had it scheduled next). Privat's two copies were lined up by hand on one fixed page offset.
Most pairs are harder: La Belga Sonorilo's ÖNB copy is two-year
bindings, its other copy one file per issue. A text match alone cannot settle it (tools/ocr-copy-coverage.py: OCR noise
leaves a third of the pages «unmatched»).

HOW.
1. PRINTED NUMBERS: each copy's pages through the page map of tools/ocr-page-sequence.py (its `map` mode, pointed at the
   copy's own folder: the same local-anchor rules as the corpus page map), into <out>.map-a.tsv and <out>.map-b.tsv.
2. VOLUMES: a copy's items in natural order; a new volume starts where the printed numbering falls back (by more than
   20) from one numbered page to the next, within an item or between items.
3. PAIRING: a volume of A is paired with the volume of B whose pages share most five-word runs with A's pages printed
   with the SAME number (the anchors; a run found on more than 3 pages is boilerplate and ignored). A volume with no
   anchor stays unpaired: reported, not guessed.
4. PER PRINTED PAGE of each pair (from the lowest to the highest number either copy prints there): A's item and PDF page,
   B's, and each one's word score (tools/ocr-flip-check.py's: the share of words of 3+ letters found in the lexicons of
   tools/lexicons/), read from each copy's main page reading (page-NNNN.txt) so the two are judged alike.
   Verdict: BOTH, A ONLY, B ONLY, or NEITHER (a number inside the range neither copy maps: a lost leaf in both, or a
   number the map could not read — a lead for a look).
   QUALITY: a page held by both whose scores differ by QGAP or more is a QUALITY GAP; «absence quality» is a score of
   ABAR or more on that page (the gate's bar of 65, read per page: a lead, not the gate).
Reads only. WRITE-SET: --out, --md, and the two maps beside --out; refuses any that exists.
"""
import argparse, collections, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QGAP, ABAR, K, SHARE = 0.15, 0.65, 5, 0.80


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def page_map(PS, root, items, out):
    PS.R = os.path.abspath(root)
    a = argparse.Namespace(out=out, items=items, n=60)
    PS.page_map(a)
    rows = collections.defaultdict(dict)
    for l in open(out, encoding="utf-8"):
        if l.startswith("#") or l.startswith("item\t"):
            continue
        x = l.rstrip("\n").split("\t")
        if len(x) >= 3:   # «7», or a spread's «2–3» (two printed pages on one PDF page), or empty
            m = re.fullmatch(r"(\d+)(?:[–-](\d+))?", x[2].strip())
            rows[x[0]][int(x[1])] = (list(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1)) if m else [])
    return rows


def texts(root, item):
    d = os.path.join(root, item); out = {}
    for f in os.listdir(d) if os.path.isdir(d) else []:
        m = re.fullmatch(r"page-(\d+)\.txt", f)
        if m:
            out[int(m.group(1))] = open(os.path.join(d, f), encoding="utf-8", errors="ignore").read()
    return out


def runs_of(t):
    w = [x for x in re.findall(r"[a-zà-öø-ÿĉĝĥĵŝŭ]+", t.lower()) if len(x) > 1]
    return {" ".join(w[j:j + K]) for j in range(len(w) - K + 1)}


def words4(t):
    return {w for w in re.findall(r"[a-zà-öø-ÿĉĝĥĵŝŭ]{4,}", t.lower())}


def volumes(PS, rows):
    """[(volume no., [(item, pdf page, printed)])] in natural item order; a fall-back of > 20 starts a new volume."""
    vols, cur, last = [], [], None
    for it in sorted(rows, key=lambda c: (PS.natural(c), c)):
        for p in sorted(rows[it]):
            ns = rows[it][p] or [None]
            for n in ns:
                if n is not None and last is not None and n < last - 20:
                    vols.append(cur); cur = []
                cur.append((it, p, n))
                if n is not None:
                    last = n
    if cur:
        vols.append(cur)
    return list(enumerate(vols, 1))


def main():
    ap = argparse.ArgumentParser()
    for k in ("label", "a-root", "a-items", "b-root", "b-items", "out", "md"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    ma, mb = a.out + ".map-a.tsv", a.out + ".map-b.tsv"
    for p in (a.out, a.md, ma, mb):
        if os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    PS = load("ps", "ocr-page-sequence.py"); FC = load("fc", "ocr-flip-check.py")
    lex = FC.lexicon()
    A, B = page_map(PS, a.a_root, a.a_items, ma), page_map(PS, a.b_root, a.b_items, mb)
    TA = {it: texts(a.a_root, it) for it in A}; TB = {it: texts(a.b_root, it) for it in B}
    VA, VB = volumes(PS, A), volumes(PS, B)
    # anchors: same printed number, shared five-word runs
    idx = collections.defaultdict(set)
    for vb, pages in VB:
        for it, p, n in pages:
            if n is not None:
                for r in runs_of(TB[it].get(p, "")):
                    idx[r].add((vb, n))
    pair = {}
    for va, pages in VA:
        votes = collections.Counter()
        for it, p, n in pages:
            if n is None:
                continue
            for r in runs_of(TA[it].get(p, "")):
                hits = idx.get(r, ())
                if 0 < len(hits) <= 3:
                    for vb, nb in hits:
                        if nb == n:
                            votes[vb] += 1
        if votes:
            pair[va] = votes.most_common(1)[0]
    rows, summ = [], []
    vbmap = dict(VB); vamap = dict(VA)
    by_b = collections.defaultdict(list)   # a B volume ← every A piece paired to it (A's numbering may break into pieces)
    for va, (vb, votes) in pair.items():
        by_b[vb].append((va, votes))
    for vb, pieces in sorted(by_b.items()):
        pa = {}
        for va, _ in sorted(pieces):
            for it, p, n in vamap[va]:
                if n is not None and n not in pa:
                    pa[n] = (it, p)
        pb = {n: (it, p) for it, p, n in vbmap[vb] if n is not None}
        lo, hi = min(list(pa) + list(pb)), max(list(pa) + list(pb))
        # pages whose number the map could not read, kept by their text: a page «only» in one copy may be one of these
        ua = [(it, p) for va, _ in pieces for it, p, n in vamap[va] if n is None]
        ub = [(it, p) for it, p, n in vbmap[vb] if n is None]
        RA = {k: runs_of(TA[k[0]].get(k[1], "")) for k in ua}; RB = {k: runs_of(TB[k[0]].get(k[1], "")) for k in ub}
        def by_text(runs, pool):
            if len(runs) < 20:
                return None
            best = max(pool.items(), key=lambda kv: len(runs & kv[1]), default=None)
            return best[0] if best and len(runs & best[1]) >= 0.2 * len(runs) else None
        c = collections.Counter()
        for n in range(lo, hi + 1):
            if n in pb and n not in pa:
                m = by_text(runs_of(TB[pb[n][0]].get(pb[n][1], "")), RA)
                if m: pa[n] = m; c["matched by text"] += 1
            if n in pa and n not in pb:
                m = by_text(runs_of(TA[pa[n][0]].get(pa[n][1], "")), RB)
                if m: pb[n] = m; c["matched by text"] += 1
            sa = FC.score(TA[pa[n][0]].get(pa[n][1], ""), lex)[0] if n in pa else None
            sb = FC.score(TB[pb[n][0]].get(pb[n][1], ""), lex)[0] if n in pb else None
            v = "BOTH" if (sa is not None and sb is not None) else "A ONLY" if sa is not None else "B ONLY" if sb is not None else "NEITHER"
            q = ""
            if v == "BOTH" and abs(sa - sb) >= QGAP:
                q = "QUALITY GAP: " + ("A better" if sa > sb else "B better")
            if v == "BOTH":
                # word share both ways (4+ letters), as the Privat hand check measured it; a spread is compared with all
                # the other copy's pages that hold its printed numbers
                ka, kb = pa[n], pb[n]
                na_ = [m for m, k in pa.items() if k == ka]; nb_ = [m for m, k in pb.items() if k == kb]
                span_ = set(na_) | set(nb_)
                wa = set()
                for k in {pa[x] for x in span_ if x in pa}: wa |= words4(TA[k[0]].get(k[1], ""))
                wb = set()
                for k in {pb[x] for x in span_ if x in pb}: wb |= words4(TB[k[0]].get(k[1], ""))
                if len(wa) >= 30 and len(wb) >= 30:
                    aib, bia = len(wa & wb) / len(wa), len(wa & wb) / len(wb)
                    if min(aib, bia) < SHARE:
                        q = (q + "; " if q else "") + f"DISAGREE: A in B {aib:.2f}, B in A {bia:.2f} (look: which copy lost text)"
                        c["disagree"] += 1
            ab = [x for x, sc in (("A", sa), ("B", sb)) if sc is not None and sc >= ABAR]
            c[v] += 1; c["quality gap"] += bool(q); c["no copy at absence quality"] += (not ab and v != "NEITHER")
            rows.append(["+".join(str(x) for x, _ in sorted(pieces)), str(vb), str(n), pa.get(n, ("", ""))[0], str(pa.get(n, ("", ""))[1]),
                         "" if sa is None else f"{sa:.2f}", pb.get(n, ("", ""))[0], str(pb.get(n, ("", ""))[1]),
                         "" if sb is None else f"{sb:.2f}", v, q, "+".join(ab) or "-"])
        allpa = [x for va, _ in sorted(pieces) for x in vamap[va]]
        summ.append(("+".join(str(x) for x, _ in sorted(pieces)), vb, allpa, vbmap[vb], c,
                     f"{len(pieces)} A piece(s), {sum(v for _, v in pieces)} anchors; printed {lo}–{hi}"))
    for va, pages in VA:
        if va not in pair:
            summ.append((str(va), None, pages, [], collections.Counter(), "A piece UNPAIRED (no anchor)"))
    paired_b = {s[1] for s in summ if s[1]}
    # A PAGE PAIRED TWICE (2026-10-20; added on the editor's decision at 18:0x, out of an abundance of caution, to prevent
    # recurrence): on Volaspodel, archive.org's PDF 73 (printed 168) was also paired under a misread number «60» with a page of temerov's
    # that shared only an advertisement block. A copy's PDF page under two printed numbers is flagged in every row it
    # holds, so no row of the pair counts as agreeing (a triangulation takes only rows with no flag).
    for col in ((3, 4), (6, 7)):
        seen = collections.defaultdict(list)
        for r in rows:
            if r[col[0]] and r[9] == "BOTH":
                seen[(r[col[0]], r[col[1]])].append(r)
        for (it, pg), rs in seen.items():
            if len({r[2] for r in rs}) > 1:
                for r in rs:
                    flag = f"PAGE PAIRED TWICE: {it} PDF {pg} under printed {', '.join(sorted({x[2] for x in rs}, key=int))} (a misread number: look)"
                    r[10] = (r[10] + "; " if r[10] else "") + flag
    with open(a.out, "x", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-copy-align.py ({a.label}): A = {a.a_items} in {a.a_root}; B = {a.b_items} in {a.b_root}. "
                f"One row per printed page of each paired volume. Scores: share of words in the lexicons; QUALITY GAP at a difference "
                f"of {QGAP}; absence quality {ABAR}. NEITHER = a number in range that neither copy maps: a lead for a look.\n")
        f.write("vol_a\tvol_b\tprinted\ta_item\ta_pdf_page\ta_score\tb_item\tb_pdf_page\tb_score\tverdict\tquality\tat_absence_quality\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    L = [f"# Two copies lined up by printed page: {a.label}\n",
         f"`[generated by tools/ocr-copy-align.py; table {os.path.basename(a.out)}; maps {os.path.basename(ma)}, {os.path.basename(mb)}]`\n",
         f"A: `{a.a_items}` in `{a.a_root}` ({len(A)} items, {len(VA)} volumes by the numbering). B: `{a.b_items}` in `{a.b_root}` ({len(B)} items, {len(VB)} volumes).\n",
         "Leads, not findings: a NEITHER page or an unmapped number may be a misread number; each needs a look before it is called a gap.\n",
         "| A vol | its items | B vol | its items | pairing | BOTH | of which by text | A ONLY | B ONLY | NEITHER | score gaps | DISAGREE (word share < 0.80) | no copy at absence quality |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for va, vb, pa, pb, c, how in summ:
        ia = sorted({x[0] for x in pa}); ib = sorted({x[0] for x in pb})
        L.append(f"| {va} | {ia[0]}{' … ' + ia[-1] if len(ia) > 1 else ''} | {vb or '—'} | {(ib[0] + (' … ' + ib[-1] if len(ib) > 1 else '')) if ib else '—'} | {how} | "
                 f"{c['BOTH']} | {c['matched by text']} | {c['A ONLY']} | {c['B ONLY']} | {c['NEITHER']} | {c['quality gap']} | {c['disagree']} | {c['no copy at absence quality']} |")
    for vb, pb in VB:
        if vb not in paired_b:
            ib = sorted({x[0] for x in pb})
            L.append(f"| — | — | {vb} | {ib[0]}{' … ' + ib[-1] if len(ib) > 1 else ''} | UNPAIRED: no A volume anchors to it (B only, or A lacks it) | | {len(pb)} pages | | | | |")
    open(a.md, "x", encoding="utf-8").write("\n".join(L) + "\n")
    tot = collections.Counter(r[9] for r in rows)
    print(f"{len(rows)} printed pages in {len(pair)} paired volumes (A {len(VA)}, B {len(VB)}); " +
          ", ".join(f"{k} {v}" for k, v in tot.most_common()) + f" → {a.out}, {a.md}")


if __name__ == "__main__":
    main()
