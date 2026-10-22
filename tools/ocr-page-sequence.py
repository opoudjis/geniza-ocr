#!/usr/bin/env python3
r"""ocr-page-sequence — does the SCAN hold every printed page? Printed page numbers against scan order.

    tools/ocr-page-sequence.py scan --out <tsv> [--items <regex>]        # per item: verdict + evidence
    tools/ocr-page-sequence.py simulate --n 100 [--seed 1]                # validation: drop an inner page, must be found
    tools/ocr-page-sequence.py simulate-last --n 100 [--seed 1]           # validation: drop an issue's LAST page

WHY (approved by the editor, 2026-09-29, after Kapis of BitArkivo asked whether the AI had also been told to check
whether any pages were missing by reading the page numbers). Every earlier check asks whether each SCANNED page was
read well. None asks whether the scan holds every PRINTED page. A leaf never scanned is invisible to every OCR check,
and an absence claim would silently cover it. Kapis finds such gaps in practice (*La Suda Kruco* 1931 n128 and 1934
n163 each lack their last page).
HOW:
1. NUMBERS. From each page's first two and last two non-empty lines, every token that is a number of 1–4 digits
   (OCR's l/I/O/o inside a digit token folded to 1/0), 1–3000; «(3)» kept as a number too — many journals print
   both a volume page and an issue page («210 (2)»).
2. FAMILIES. For a number n on scan page s the OFFSET is n − s. A numbering family is an offset carried by at least
   3 pages and 20% of the numbered pages. A journal with volume and issue pagination has two families.
3. WITHIN AN ITEM. Where a family's offset steps UP from o to o′ between two runs of at least 2 pages each, printed
   pages o′ − o are missing between them (a lost leaf is 2). A step DOWN is a repeat or a restart (a duplicated
   scan, or two issues bound together). A step must be seen in the pages either side, not inferred from one page.
4. ACROSS ISSUES (the lost LAST page, which leaves no jump inside the item). Items of one title, in order, whose
   dominant family is a VOLUME pagination (offset > 0 somewhere in the run): issue k's inferred last printed page
   (its last scan page + offset) should be one less than issue k+1's inferred first printed page. A shortfall of 1–8
   is pages missing at the join; larger is a missing issue or a volume break, reported, not called a loss.
5. PAGE COUNTS (Kapis's second test). Titles whose issues mostly have the same page count: an issue with fewer
   scan pages than that mode is flagged. Since 2026-10-07 also PER YEAR (a title whose page count changed over the
   years never reaches the mode as a whole); the per-year test only adds flags («SHORT … that year»).
6. THE COUNT JOIN (2026-10-07, after Kapis's La Suda Kruco 1934 n163 slipped through tests 1–5). A short issue whose own
   numbers are too few to follow is CANT-TELL and so out of test 4; but the neighbouring issues of its year bound it:
   it should have (next's first printed − previous's last printed − 1) pages. A neighbour that is itself CANT-TELL
   counts if ≥ 2 of its pages agree on one offset. A shortfall of 1–8 pages is evidence «COUNT …» and the item a LEAD.
   Tested on BitArkivo's 1934 n162–164 (n163: 3 PDF pages where 4 belong) and the corpus (1 COUNT lead: JEN 1909.5).
7. THE ODD COUNT (2026-10-13, on the editor's ruling that an odd number of pages is always suspect for a missing page;
   option 2a approved by the editor). An issue
   of a run (a year in its name, its title 3+ items) whose PDF page count, less the digitiser's sheets (ÖNB «Umfang:»,
   Gallica, Persée), is odd: evidence «ODD …», and a COMPLETE or CANT-TELL item a LEAD. Exempt: bound volumes (over
   ODD_MAX pages), items read as spreads, the one-sided titles of ONE_SIDED. Measured first on 40 odd issues
   (an internal record, 2026-10-13, not published): the leads were wrapper pages (The British Esperantist).
VERDICT per item: GAP only where the numbering steps UP and never back (a step up and a step back is misread or
irregular numbering: LEAD, for a look); COMPLETE (the numbering followed from the first pages to the last — within 1 scan page of each end,
over at least half the pages — and no gap), GAP (the evidence), PARTLY-VERIFIED (no gap seen, but the numbering could
not be followed over the whole item: a loss outside the followed span would be invisible — these stretches go to the
vision read of the page-number strip, Kapis's method; the last column, unverified_pdf_pages, names them in PDF pages,
2026-10-07), CANT-TELL (too few readable numbers).
Reads the OCR only. A flagged gap is a lead for an image look, not yet a finding.
"""
import os, re, sys, glob, json, random, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
_FOLD = str.maketrans({"l": "1", "I": "1", "O": "0", "o": "0"})
TOK = re.compile(r"^[(\[{«»\"'„“”*·.,:;—–-]*([\dlIoO]{1,4})[)\]}«»\"'„“”*·.,:;—–-]*$")


def numbers_of(text):
    lines = [l for l in re.split(r"[\n\x0c]", text) if l.strip()]
    edge = lines[:2] + lines[-2:] if len(lines) > 4 else lines
    out = set()
    for l in edge:
        for t in l.split():
            m = TOK.match(t)
            if m and re.search(r"\d", m.group(1)):
                v = int(m.group(1).translate(_FOLD))
                if 1 <= v <= 3000:
                    out.add(v)
    return out


PREFERRED = False   # --preferred (2026-09-30): read each page's PREFERRED reading (vision, hand, ruled, emended born-digital
                    # layer …; `ocr-preferred/<corpus>.txt`) instead of the base psm 6 reading. The first run read only
                    # `page-NNNN.txt`, so page numbers a vision transcription has since read were invisible to it.


def item_pages(c):
    d = os.path.join(R, c); pg = {}
    for f in glob.glob(os.path.join(d, "page-*.txt")):
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m:
            pg[int(m.group(1))] = open(f, encoding="utf-8", errors="ignore").read()
    pf = os.path.join(os.path.dirname(R), "ocr-preferred", c + ".txt")
    if PREFERRED and os.path.exists(pf):
        parts = re.split(r"\n=== page (\d+) ===\n", "\n" + open(pf, encoding="utf-8", errors="ignore").read())
        for n_, t_ in zip(parts[1::2], parts[2::2]):
            if t_.strip():
                pg[int(n_)] = t_
    return pg


def analyse(nums):
    """nums: {scan page: set(numbers)} → dict with families, gaps, repeats, first/last printed."""
    scans = sorted(nums)
    numbered = [s for s in scans if nums[s]]
    off = collections.Counter(n - s for s in scans for n in nums[s])
    fams = [o for o, k in off.most_common() if k >= 3 and k >= 0.2 * max(1, len(numbered))]
    res = {"scan_pages": len(scans), "numbered": len(numbered), "families": fams, "gaps": [], "repeats": []}
    if not fams:
        res["verdict"] = "CANT-TELL"; return res
    # per page, which offsets it supports (restricted to offsets near a family, to follow a family through a step)
    for fam in fams[:3]:
        # follow ONE family through the item, page to page: on each page take the number whose offset is NEAREST the
        # previous page's (within −4…+10 of it: a gap steps up, a repeat steps back); skip the page if two are equally
        # near. So a page printing both a volume and an issue page («210 (2)»), a date, or an issue number does not
        # break the run, and a misread number («27» → «21») is simply skipped.
        # A CHANGE of offset is taken only when the NEXT numbered page confirms it: a real gap is followed by pages
        # that continue from it, a stray number («6» on page 1, a date) is not — so it cannot hijack the tracking.
        seq, prev = [], fam
        for i, s in enumerate(scans):
            offs = {n - s for n in nums[s]}
            if prev in offs:
                seq.append((s, prev)); continue
            cand = sorted((o for o in offs if -4 <= o - prev <= 10), key=lambda o: (abs(o - prev), o))
            if not cand:
                continue
            # the NEXT page with a number NEAR the run (in the same −4…+10 window) confirms; a page whose only numbers
            # are noise («1», «50», «100», a date) is skipped, not taken as a refusal. (2026-10-16: on
            # ANNO_e4a_19090157 «211» PDF 31 → «214» PDF 32 was refused because PDF 33 read only «1 50 100», and a
            # lost leaf, printed 212–213, went unseen; the editor asked why the check had not picked up the missing
            # leaf and required that it not recur.)
            nxt = next((t for t in scans[i + 1:] if any(-4 <= (n - t) - prev <= 10 for n in nums[t])), None)
            if nxt is not None and cand[0] in {n - nxt for n in nums[nxt]}:
                seq.append((s, cand[0])); prev = cand[0]
        if seq and "span" not in res:
            res["span"] = (seq[0][0], seq[-1][0], len(seq))   # the first family followed: its first and last page
            res["_seq"] = seq
        runs = []
        for s, o in seq:
            if runs and runs[-1][1] == o:
                runs[-1][2].append(s)
            else:
                runs.append([s, o, [s]])
        # a run of ONE page counts only when it sits exactly on a family's offset (a misread rarely lands there)
        runs = [r for r in runs if len(r[2]) >= 2 or r[1] in fams]
        for x, y in zip(runs, runs[1:]):
            d = y[1] - x[1]
            lo, hi = x[2][-1] + x[1], y[2][0] + y[1]      # last well-read printed page before, first after
            if d > 0:
                g = {"family": fam, "after_scan": x[2][-1], "before_scan": y[2][0], "count": d,
                     "between": (lo, hi), "printed_missing": list(range(lo + 1, hi))}
                if not any(z["between"] == g["between"] for z in res["gaps"]):
                    res["gaps"].append(g)
            elif d < 0:
                res["repeats"].append({"family": fam, "after_scan": x[2][-1], "before_scan": y[2][0], "step": d})
    # the VOLUME pagination, if there is one, is the family with the largest offset; it is what joins issues
    main = max(fams[:3]) if max(fams[:3]) > 0 else fams[0]
    res["offset"] = main
    # first/last printed: the offset FOLLOWED at each end of the item, not one family projected over the whole item
    # (2026-10-16: «printed 3–10» for ANNO_e4a_19050121, which runs unnumbered 1, then 2–8: the largest family was
    # noise; the editor found these printed page numbers incorrect and asked for a diagnosis). Still a projection at
    # the ends past the last number read: the TSV's evidence column and `reconcile` give the numbers actually read.
    fseq = res.get("_seq") or []
    o_first = fseq[0][1] if fseq else main
    o_last = fseq[-1][1] if fseq else main
    res["first_printed"] = scans[0] + o_first; res["last_printed"] = scans[-1] + o_last
    # COMPLETE only if the numbering was FOLLOWED from the item's first pages to its last (within 1 scan page of
    # each end); otherwise the pages outside the followed span are UNVERIFIED — a loss there could not be seen.
    sp = res.get("span")
    if res["gaps"] and res["repeats"] or res["repeats"]:
        # a step up AND a step back: misread or irregular numbering, not a demonstrated loss — a lead for a look.
        # A step BACK alone is a lead too (2026-10-16: it used to pass as COMPLETE).
        res["verdict"] = "LEAD"
    elif res["gaps"]:
        res["verdict"] = "GAP"
    elif sp and sp[0] <= scans[0] + 1 and sp[1] >= scans[-1] - 1 and sp[2] >= 0.5 * len(scans):
        res["verdict"] = "COMPLETE"
    else:
        res["verdict"] = "PARTLY-VERIFIED"
        res["unverified"] = unverified_pages(scans, sp)
    return res


def unverified_pages(scans, sp):
    """The PDF pages (page-NNNN numbers, NOT printed page numbers) outside the stretch the numbering was followed over,
    for the look that settles a PARTLY-VERIFIED item (cupel C6.4.1; docs/FAILURE-MAP.md R14). sp = (first, last, pages followed)."""
    if not sp:
        return "all (no stretch followed)"
    out = []
    for lo, hi in ((scans[0], sp[0] - 1), (sp[1] + 1, scans[-1])):
        if lo <= hi:
            out.append(f"{lo}" if lo == hi else f"{lo}–{hi}")
    head = ", ".join(out) if out else "none at the ends"
    return f"PDF pages {head} (followed PDF pages {sp[0]}–{sp[1]}, numbers read on {sp[2]} of {len(scans)})"


ODD_MAX = 150                 # test 7: more PDF pages than this is a bound volume (the issues inside hide their parity)
ONE_SIDED = {"anno_e1e"}      # test 7: titles printed on one side (ANNO_e1e = Helvetia, the Occidental typescript, 1928–34)
_SHEET = re.compile(r"Umfang:|Österreichische Nationalbibliothek|gallica|bnf\.fr|Conditions d.utilisation|persee\.fr|Persée",
                    re.I)


def digitiser_sheets(first_pages):
    """How many of an item's first pages are a digitiser's own sheet (ÖNB, Gallica's two, Persée), counted from the front."""
    k = 0
    for t in first_pages:
        if _SHEET.search(t) and len(t.split()) < 400:
            k += 1
        else:
            break
    return k


def title_of(c):
    m = re.match(r"(.+?)(?:[._ -]?\d{4}|[._]\d)", c)
    return (m.group(1) if m else c).lower()


def natural(c):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", c)]


def year_of(c):
    m = re.search(r"(1[89]\d\d|20[0-2]\d)", c)
    return m.group(1) if m else None


def scan(a):
    items = sorted(os.path.basename(d) for d in glob.glob(os.path.join(R, "*")) if os.path.isdir(d))
    if a.items:
        items = [c for c in items if re.search(a.items, c)]
    rows = {}
    for c in items:
        pg = item_pages(c)
        if not pg:
            continue
        nums_c = {s: numbers_of(t) for s, t in pg.items()}
        rows[c] = analyse(nums_c)
        # for test 7 (ODD): the digitiser's sheets at the front, and pages printing two consecutive numbers (spreads)
        rows[c]["_sheets"] = digitiser_sheets([pg[s] for s in sorted(pg)[:2]])
        rows[c]["_spreads"] = sum(1 for ns in nums_c.values() if any(n + 1 in ns for n in ns))
    # across issues: consecutive items of one title with a volume pagination
    bytitle = collections.defaultdict(list)
    for c, r in rows.items():
        if r["verdict"] != "CANT-TELL":
            bytitle[title_of(c)].append(c)
    joins = []
    for t, cs in bytitle.items():
        # consecutive issues OF ONE YEAR, in the order their names give (natural sort), and only where the second
        # continues the first's pagination: sorting a whole title by page number paired different years' volumes
        cs = sorted(cs, key=natural)
        for x, y in zip(cs, cs[1:]):
            rx, ry = rows[x], rows[y]
            if year_of(x) is None or year_of(x) != year_of(y):
                continue
            if rx["offset"] <= 0 and ry["offset"] <= 0:
                continue   # issues numbered from 1: no volume pagination to join
            if ry["first_printed"] <= rx["last_printed"]:
                continue   # not a continuation (a new volume, or out of order)
            short = ry["first_printed"] - rx["last_printed"] - 1
            if 1 <= short <= 8:
                joins.append((x, y, short, rx["last_printed"], ry["first_printed"]))
                rx.setdefault("join_gaps", []).append({"next": y, "printed_missing": list(range(rx["last_printed"] + 1, ry["first_printed"]))})
    # THE COUNT JOIN (2026-10-07; Kapis's La Suda Kruco 1934 n163, which the join above missed). A short issue whose own
    # numbers are too few to follow is CANT-TELL, and so left out of the join; yet its neighbours' printed ranges say
    # how many pages it should have: (next's first printed) − (previous's last printed) − 1. A neighbour that is itself
    # CANT-TELL may still give a WEAK range: an offset into the volume pagination read on ≥ 2 of its pages (n164: printed
    # 131 and 132 on PDF pages 3 and 4, offset 128). Only CANT-TELL issues are tested here: the others have the join.
    def known(c):
        r = rows[c]
        if r["verdict"] != "CANT-TELL" and r.get("offset", 0) > 0:
            return r["first_printed"], r["last_printed"]
        nums = {s: numbers_of(t) for s, t in item_pages(c).items()}
        off = collections.Counter(n - s for s, ns in nums.items() for n in ns if n - s > 0)
        if off:
            o, k = off.most_common(1)[0]
            if k >= 2 and (len(off) == 1 or off.most_common(2)[1][1] < k):
                ss = sorted(nums)
                return ss[0] + o, ss[-1] + o
        return None
    byt = collections.defaultdict(list)
    for c in rows:
        byt[title_of(c)].append(c)
    count_joins = 0
    for t, cs in byt.items():
        cs = sorted(cs, key=natural)
        for x, y, z in zip(cs, cs[1:], cs[2:]):
            if rows[y]["verdict"] != "CANT-TELL" or year_of(x) is None or not (year_of(x) == year_of(y) == year_of(z)):
                continue
            kx, kz = known(x), known(z)
            if not kx or not kz or kz[0] <= kx[1]:
                continue
            expected = kz[0] - kx[1] - 1
            if 1 <= expected - rows[y]["scan_pages"] <= 8:
                rows[y]["count_gap"] = {"expected": expected, "has": rows[y]["scan_pages"], "after": kx[1], "before": kz[0],
                                        "prev": x, "next": z}
                count_joins += 1
    # page counts: titles whose issues mostly share a page count. Since 2026-10-07 also PER YEAR (a title whose page
    # count changed over the years, La Suda Kruco 8 pages in 1931 and 4 in 1934, never reaches the 60% mode as a whole);
    # the per-year test only ADDS flags, so nothing the title-wide test finds is lost.
    def short_flags(groups, label):
        for t, cl in groups.items():
            if len(cl) < 5:
                continue
            mode, k = collections.Counter(n for _, n in cl).most_common(1)[0]
            if k >= 0.6 * len(cl):
                for c, n in cl:
                    if n < mode and "short_issue" not in rows[c]:
                        rows[c]["short_issue"] = {"pages": n, "title_mode": mode, "over": label}
    counts, counts_y = collections.defaultdict(list), collections.defaultdict(list)
    for c, r in rows.items():
        counts[title_of(c)].append((c, r["scan_pages"]))
        if year_of(c):
            counts_y[(title_of(c), year_of(c))].append((c, r["scan_pages"]))
    short_flags(counts, "title")
    short_flags(counts_y, "year")
    # 7. THE ODD COUNT (2026-10-13, on the editor's ruling that an odd number of pages is always suspect for a missing
    # page, option 2a approved; measured first (an internal record, 2026-10-13, not published): on 40 odd issues flagged
    # by no other test, 6 lacked wrapper
    # pages, 33 were innocent). Printed sheets have two sides, so an ISSUE OF A RUN (a year in its name, its title 3+ items)
    # with an odd page count likely lacks a page: a lead. The digitiser's own sheets are SUBTRACTED first (ÖNB «Umfang:»,
    # Gallica, Persée); EXEMPT: bound volumes (more than ODD_MAX PDF pages: the issues inside hide their parity), items
    # read as spreads (2+ pages printing two consecutive numbers: one PDF page holds two printed pages), and the
    # one-sided typescripts of ONE_SIDED (a cover, pages printed on one side, a blank back). Books and born-digital
    # texts are not tested (an offprint ends on a recto: no leaf lost).
    for t, cs in byt.items():
        if len(cs) < 3 or t in ONE_SIDED:
            continue
        for c in cs:
            r = rows[c]; n = r["scan_pages"] - r["_sheets"]
            # spreads: two consecutive numbers on at least 30% of the numbered pages (Internacia Socia Revuo: nearly all);
            # not «2 pages», which a numbered list at a page's edge also gives (The British Esperantist's F.K.I. entries)
            spread = r["_spreads"] >= max(2, 0.3 * r["numbered"])
            if year_of(c) and r["scan_pages"] <= ODD_MAX and not spread and n % 2:
                r["odd"] = {"pages": r["scan_pages"], "sheets": r["_sheets"]}
    with open(a.out, "w") as f:
        # unverified_pdf_pages (added 2026-10-07, docs/FAILURE-MAP.md R14): for PARTLY-VERIFIED, the PDF pages outside the followed
        # stretch, in PDF page numbers. It is the LAST column, so readers that take columns 1–8 by position are unchanged.
        f.write("corpus\tverdict\tscan_pages\tnumbered\toffset\tfirst_printed\tlast_printed\tevidence\tunverified_pdf_pages\n")
        for c, r in sorted(rows.items()):
            ev = []
            for g in r["gaps"]:
                ev.append(f"GAP {g['count']} page(s) missing between printed {g['between'][0]} and {g['between'][1]} (scan {g['after_scan']}–{g['before_scan']})")
            for g in r["repeats"]:
                ev.append(f"REPEAT/RESTART step {g['step']} between scan {g['after_scan']} and {g['before_scan']}")
            for g in r.get("join_gaps", []):
                ev.append(f"JOIN printed {g['printed_missing'][0]}–{g['printed_missing'][-1]} missing before {g['next']}")
            if "short_issue" in r:
                over = " that year" if r["short_issue"].get("over") == "year" else ""
                ev.append(f"SHORT {r['short_issue']['pages']} pages against the title's usual {r['short_issue']['title_mode']}{over}")
            if "count_gap" in r:
                g = r["count_gap"]
                ev.append(f"COUNT {g['expected'] - g['has']} page(s) short: {g['has']} PDF pages where the neighbours leave "
                          f"{g['expected']} (printed {g['after'] + 1}–{g['before'] - 1}, between {g['prev']} and {g['next']})")
            if "odd" in r:
                o = r["odd"]
                ev.append(f"ODD {o['pages']} PDF pages" + (f" ({o['pages'] - o['sheets']} without the digitiser's sheet)" if o["sheets"] else "")
                          + ": a page likely missing (in the sample, wrapper pages)")
            v = r["verdict"]
            if v in ("COMPLETE", "CANT-TELL") and ("count_gap" in r or "odd" in r or (v == "COMPLETE" and ev)):
                v = "LEAD"
            f.write(f"{c}\t{v}\t{r['scan_pages']}\t{r['numbered']}\t{r.get('offset','')}\t{r.get('first_printed','')}\t{r.get('last_printed','')}\t{' · '.join(ev)}\t{r.get('unverified', '') if v == 'PARTLY-VERIFIED' else ''}\n")
    vc = collections.Counter()
    for c, r in rows.items():
        v = r["verdict"]
        if v == "COMPLETE" and (r["repeats"] or r.get("join_gaps") or r.get("short_issue") or r.get("count_gap") or r.get("odd")):
            v = "LEAD"
        if v == "CANT-TELL" and (r.get("count_gap") or r.get("odd")):
            v = "LEAD"
        vc[v] += 1
    print(f"{len(rows)} items ·", dict(vc), f"· join gaps {len(joins)} · count joins {count_joins} · short issues {sum('short_issue' in r for r in rows.values())}"
          f" · odd issues {sum('odd' in r for r in rows.values())}")


def simulate(a):
    """Take items the check calls COMPLETE with good numbering, drop one inner scan page (renumbering the rest), and
    require a GAP of exactly that printed page. Also drop the LAST page, which only the join test can see."""
    random.seed(a.seed)
    items = sorted(os.path.basename(d) for d in glob.glob(os.path.join(R, "*")) if os.path.isdir(d))
    random.shuffle(items)
    tried = found = wrong = 0
    for c in items:
        pg = item_pages(c)
        if len(pg) < 8:
            continue
        nums = {s: numbers_of(t) for s, t in pg.items()}
        base = analyse(nums)
        if base["verdict"] != "COMPLETE" or base["numbered"] < 0.7 * base["scan_pages"]:
            continue
        scans = sorted(nums)
        k = random.choice(scans[2:-2])
        dropped = {}
        for s in scans:
            if s < k: dropped[s] = nums[s]
            elif s > k: dropped[s - 1] = nums[s]
        r = analyse(dropped)
        want = k + base["offset"]
        hit = any(want in g["printed_missing"] for g in r["gaps"])
        tried += 1; found += hit
        wrong += (not hit) and r["verdict"] == "COMPLETE"
        if tried >= a.n:
            break
    print(f"inner-page drops: {tried} items · the dropped printed page found in {found} ({100*found/max(1,tried):.0f}%) · "
          f"called COMPLETE though a page was dropped: {wrong}")


def simulate_last(a):
    """Kapis's case: an issue whose LAST page is lost. Inside the item nothing jumps; only the join with the next
    issue (volume pagination) can show it. Drop the last scan page of a COMPLETE issue that has a COMPLETE successor
    in a volume-paginated run, and require the join to report the lost printed page."""
    random.seed(a.seed)
    items = sorted(os.path.basename(d) for d in glob.glob(os.path.join(R, "*")) if os.path.isdir(d))
    rows = {}
    for c in items:
        pg = item_pages(c)
        if len(pg) >= 4:
            rows[c] = (pg, analyse({s: numbers_of(t) for s, t in pg.items()}))
    bytitle = collections.defaultdict(list)
    for c, (pg, r) in rows.items():
        if r["verdict"] == "COMPLETE" and r["offset"] > 0:
            bytitle[title_of(c)].append(c)
    pairs = []
    for tl, cs in bytitle.items():
        cs = sorted(cs, key=natural)
        pairs += [(x, y) for x, y in zip(cs, cs[1:]) if year_of(x) and year_of(x) == year_of(y)
                  and rows[y][1]["first_printed"] == rows[x][1]["last_printed"] + 1]
    random.shuffle(pairs)
    tried = found = 0
    for x, y in pairs[:a.n]:
        pg, _ = rows[x]
        last = max(pg)
        r = analyse({s: numbers_of(t) for s, t in pg.items() if s != last})
        want = last + rows[x][1]["offset"]
        short = rows[y][1]["first_printed"] - r.get("last_printed", 0) - 1
        hit = r["verdict"] != "CANT-TELL" and 1 <= short <= 8 and r["last_printed"] + 1 <= want < rows[y][1]["first_printed"]
        tried += 1; found += hit
    print(f"last-page drops: {tried} issue pairs joined by volume pagination · the lost last page found at the join in {found} ({100*found/max(1,tried):.0f}%)")


# THE PAGE MAP (2026-10-08; a proposal (an internal record, 2026-10-08, not published), approved by the editor with
# rulings that morning). One row per item and PDF page: the printed page, and what it rests on, written as the editor ruled:
#   read   «352»                       the number read on this page equals the item's offset applied to it
#   iss    «352 (extrap. from iss.)»   not read here; from this item's own numbers (its offset)
#   vol    «352 (extrap. from vol.)»   the item's own numbers too few; from the neighbouring issues' printed ranges, in a
#                                      title numbered through the volume, only where the page count fits exactly
#   count  «3 (counted)»               the item prints no numbers anywhere, nor does its title: counted from the first
#                                      page of text (FIRST_TEXT: pages before it are «skipped»)
#   front  «»                          before printed page 1 (the offset puts it at 0 or below): unnumbered front matter
#   ?      «?»                         not given: at a break (gap, step up and back), or a too-short issue (COUNT), or no
#                                      anchor; extrapolation never crosses a break
# Read-only; writes --out: the fixed name geniza/ocr/runs/OCR-PAGE-MAP.tsv, replaced only when the current version is
# committed (tools/ocr_replace_guard.py, approved by the editor, 2026-10-08), after a difference report, losses first.
# The ÖNB viewer's footer «Seite 271 von 368» rises by one a page, so its number reads as a perfect pagination
# (check 2b, 2026-10-08: blank pages «read», Lingvo Internacia 1907.1 PDF page 41 mapped 41 where the page prints 11).
VIEWER = re.compile(r"(?im)^.*\bS[eo][il1I|]te\s*\d+\s*v[o0a]n\s*\d+.*$")
FIRST_TEXT = {"LEsperantiste.1907.5.1": 3}   # Gallica's PDF pages 1–2 are its title and conditions sheets
# Items SEEN to print no page numbers (ruling 2 counts them from the first page of text). Only by a look: «no number read»
# is not «none printed» (check 2: a born-digital book whose text omits its folios). item → how it was seen.
COUNTED = {
    'Anatole-Francetri-rakonti': "seen to print no page number: PDF pages 1, 5, 9 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'EsperantoTriumfonta.1921.053': "seen to print no page number: PDF pages 1, 3, 4 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'EsperantoTriumfonta.1922.068': "seen to print no page number: PDF pages 1, 3, 4 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'KatalunaEsperantisto.1912.23-literaturakonkurso': "seen to print no page number: PDF pages 1, 3, 4 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'KatalunaEsperantisto.1914.50-suplemento': "seen to print no page number: PDF pages 1, 3, 4 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'LA_SAPONBULO': "seen to print no page number: PDF pages 1, 9, 16 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'Lingvo Internacia 1903.0': "seen to print no page number: PDF pages 1 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'Lingvo Internacia 1908.13': "seen to print no page number: PDF pages 1, 2 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'Recenzo_pri_Universalaj_Lingvoj_en_Svislando': "seen to print no page number: PDF pages 1, 5, 9 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'Tago_gazetara_libereco': "seen to print no page number: PDF pages 1, 2 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'larevuo.1906.13': "seen to print no page number: PDF pages 1 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'larevuo.1907.0': "seen to print no page number: PDF pages 1 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'nordamuziko': "seen to print no page number: PDF pages 1 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
    'ondodeesperanto.1912.00': "seen to print no page number: PDF pages 1, 2 (look 2026-10-08, sources/ocr-work/page-map-unread-look-2026-10-08/)",
}
# Items whose offset was SEEN by a look where the reading has no page numbers (a born-digital text without its folios).
# item → (offset: printed = PDF page + offset, how it was seen)
OFFSET_SEEN = {c: (-2, "check 2 of the page map, 2026-10-08: 38 sampled pages all print PDF page − 2")
               for c in ("B8 Carlevaro et alii - Bibliografio di Ido 3ma ed 2020", "Bibliografio di Ido 3ma ed 2020")}
# Items SEEN to be spread PDFs (two printed pages a sheet), mapped as ranges. Only by a look: detecting them from the
# numbers (pairs n, n+1) also took ordinary booklets. item → how it was seen.
# SEGMENTS (2026-10-09, approved by the editor): an item whose stretches are
# known from a look, named PDF page by PDF page; it overrides the anchors for that item only. Each row: (first PDF page,
# last PDF page, offset, kind, note). For a SPREADS item the offset gives the LEFT page (2 × PDF page + offset); kind is
# «iss» (read where the number is on the page, else extrapolated), or «front» / «?» with no number.
SEGMENTS = {"338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat": [
    # the old copy: both volumes in one PDF; the text layer's running heads and two looks (2026-10-08)
    (1, 5, -4, "iss", "vol. 1; before the first pair read (PDF 6), by the offset"),
    (6, 39, -4, "iss", "vol. 1"),
    (40, 43, None, "front", "vol. 2, front matter: half-title, title page, copyright and preface, contents (unnumbered)"),
    (44, 50, -80, "iss", "vol. 2"),
    (51, 52, -30, "iss", "vol. 1; a second scan of PDF pages 38–39"),
    (53, 56, None, "front", "vol. 2, front matter; a second scan of PDF pages 40–43"),
    (57, 63, -106, "iss", "vol. 2; a second scan of PDF pages 44–50"),
    (64, 74, -106, "iss", "vol. 2 (printed pp. 44–45 not in the scan, after PDF 74)"),
    (75, 91, -104, "iss", "vol. 2 (printed pp. 80–81 not in the scan, after PDF 91)"),
    (92, 150, -102, "iss", "vol. 2"),
],
    # the REU copy of vol. 2 (cupel6): its first three PDF pages are single pages, and the unnumbered [1], [2], [4], [6]
    # are not in the scan (the ends look, an internal record, not published); from PDF 4 = printed 8, offset 4
    "privat-historio-1927-vol2": [
    (1, 1, None, "front", "title page (printed [3]); [1], [2] and [4] not in the scan"),
    (2, 2, None, "front", "preface (printed [5]); [6] not in the scan"),
    (3, 3, 4, "iss", "contents, its first page (unnumbered [7])"),
    (4, 195, 4, "iss", ""),
]}

SPREADS = {"338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat":
           "check 2 of the page map, 2026-10-08 (b01/033): PDF page 121 shows printed pages 140 and 141"}


ROMAN_TOK = re.compile(r"^[(\[«\"'—–-]*([ivxl]{1,7}|[IVXL]{1,7})[)\]»\"'.,:;—–-]*$")


def _roman(n):
    out = ""
    for k, sym in ((40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= k: out += sym; n -= k
    return out
ROMAN_VAL = {_roman(n): n for n in range(1, 41)}


def roman_runs(pg):
    """{PDF page: (value, read?)} for roman-numbered stretches (2026-10-08, on the editor's question whether roman
    numbers were tractable; a triage (an internal record, 2026-10-08, not published): 72 items in 25 titles, chiefly The British Esperantist's
    and L'Espérantiste's advertisement and wrapper pages, Progreso's and books' front matter). A roman token counts only
    on a short edge line (<= 3 tokens; else as the first or last token beside a running title), read from the TEXT
    before the I→1 folding, and only when two other pages within 4 agree on its sequence (the arabic rule)."""
    found = {}
    for p, t in pg.items():
        lines = [l for l in re.split(r"[\n\x0c]", VIEWER.sub("", t)) if l.strip()]
        edge = lines[:2] + lines[-2:] if len(lines) > 4 else lines
        for l in edge:
            toks = [x for x in l.split() if x not in ("|", "—", "–", "-")]
            if not toks: continue
            if len(toks) > 3:
                if not (ROMAN_TOK.match(toks[0]) or ROMAN_TOK.match(toks[-1])): continue
                toks = [toks[0], toks[-1]]
            for tok in toks:
                mm = ROMAN_TOK.match(tok)
                if mm and mm.group(1).lower() in ROMAN_VAL:
                    found.setdefault(p, set()).add(ROMAN_VAL[mm.group(1).lower()])
    ps = sorted(found); anch = {}
    for p in ps:
        for v in found[p]:
            if sum(1 for q in ps if q != p and abs(q - p) <= 4 and any((v - p) == (w - q) for w in found[q])) >= 2:
                anch[p] = v; break
    if len(anch) < 3: return {}
    out, A = {}, sorted(anch)
    for x, y in zip(A, A[1:]):          # fill between two anchors of one run (same offset, <= 4 apart)
        if y - x <= 4 and anch[y] - y == anch[x] - x:
            for s in range(x + 1, y): out[s] = (s + anch[x] - x, False)
    for s in A: out[s] = (anch[s], True)
    return out


def page_map(a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ocr_replace_guard as RG   # the fixed name geniza/ocr/runs/OCR-PAGE-MAP.tsv, replaced only when committed
    why = RG.may_replace(a.out)
    if why: sys.exit(why)
    final, a.out = a.out, a.out + ".new"
    items = sorted(os.path.basename(d) for d in glob.glob(os.path.join(R, "*")) if os.path.isdir(d))
    if a.items:
        items = [c for c in items if re.search(a.items, c)]
    NUMS, rows = {}, {}
    for c in items:
        pg = item_pages(c)
        if not pg: continue
        NUMS[c] = {s: numbers_of(VIEWER.sub("", t)) for s, t in pg.items()}
        rows[c] = analyse(NUMS[c])
    def weak(c):   # an offset read on >= 2 pages and dominant (the COUNT join's rule)
        off = collections.Counter(n - s for s, ns in NUMS[c].items() for n in ns)
        if off:
            o, k = off.most_common(1)[0]
            if k >= 2 and (len(off) == 1 or off.most_common(2)[1][1] < k):
                return o
        return None
    def span(c):
        r = rows[c]
        if r["verdict"] != "CANT-TELL" and r.get("offset", 0) > 0 and not r["gaps"] and not r["repeats"]:
            return r["first_printed"], r["last_printed"]
        return None
    byt = collections.defaultdict(list)
    for c in rows: byt[title_of(c)].append(c)
    titled_numbers = {t: any(rows[c]["numbered"] for c in cs) for t, cs in byt.items()}
    neighbours = {}
    for t, cs in byt.items():
        cs = sorted(cs, key=lambda c: (natural(c), c))
        for i, c in enumerate(cs):
            neighbours[c] = (cs[i - 1] if i else None, cs[i + 1] if i + 1 < len(cs) else None)
    stats = collections.Counter()
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("# GENERATED by tools/ocr-page-sequence.py map. Do not hand-edit — re-run it. PDF pages are the scan's order "
                "(page-NNNN); «printed» is written in the editor's forms (n · n (extrap. from iss.) · n (extrap. from vol.) · "
                "n (counted)); «?» = not given.\n")
        f.write("item\tpdf_page\tprinted\tsource\tprinted_display\tnote\n")
        for c in sorted(rows, key=lambda c: (natural(c), c)):
            r, nums = rows[c], NUMS[c]; scans = sorted(nums); out = {}
            # v2 (2026-10-08, after check 2: one offset per item failed on bound volumes, plates, spreads). LOCAL ANCHORS:
            # a number read on page s is an anchor when another page within 4 agrees on its offset. A page between two
            # anchors that agree gets their offset (iss); between anchors that differ, «?» (every change of offset is a
            # break). Spread PDFs (two printed pages a sheet: a pair n, n+1 stepping by 2) are mapped as ranges.
            spread = c in SPREADS
            hi_ = (r.get("offset") or 0) + scans[-1]
            if hi_ < 1500:   # years are not page numbers here: «1920» on one page and «1922» two pages on agree on an offset
                nums = {s: {n for n in ns if not 1850 <= n <= 2030} for s, ns in nums.items()}
            f_ = (lambda s, o: 2 * s + o) if spread else (lambda s, o: s + o)
            cand = {s: ({n - 2 * s for n in nums[s]} | {n - 1 - 2 * s for n in nums[s]} if spread else {n - s for n in nums[s]}) for s in scans}
            anch = {}
            for k, s in enumerate(scans):
                # two OTHER pages within 4 must agree (check 2b: one agreeing page let stray «1», «2», «6» on PDF pages
                # 1, 2, 6 of an issue read as its pagination, against the real offset 38)
                ok = {o for o in cand[s] if sum(1 for u in scans[max(0, k - 4):k + 5] if u != s and o in cand[u]) >= 2}
                if ok: anch[s] = ok
            chosen = {}
            for s, ok in anch.items():
                if len(ok) == 1: chosen[s] = next(iter(ok)); continue
                near = collections.Counter(o for u, oo in anch.items() if u != s and abs(u - s) <= 10 for o in oo if o in ok)
                glob_ = collections.Counter(o for oo in anch.values() for o in oo)   # the offset the whole item follows
                main_ = r.get("offset")   # the item's own pagination (analyse's volume family) wins where it is anchored
                chosen[s] = main_ if main_ in ok else max(ok, key=lambda o: (near[o], glob_[o], o))
            # SANDWICH (2026-10-08, a check of the Waringhien dowse: PDF pages 12–15 read a numbered list «1 2 3 4»,
            # four pages agreeing, so PDF 14 «3» where it prints 19): a run of <= 4 anchored pages whose offset differs
            # from the runs just before and just after it, when those two agree with each other, is not the pagination
            runs_ = []
            for s_ in sorted(chosen):
                if runs_ and runs_[-1][1] == chosen[s_]: runs_[-1][2].append(s_)
                else: runs_.append([s_, chosen[s_], [s_]])
            for i_ in range(1, len(runs_) - 1):
                pv, cur, nx = runs_[i_ - 1], runs_[i_], runs_[i_ + 1]
                if (len(cur[2]) <= 4 and pv[1] == nx[1] != cur[1] and abs(cur[1] - pv[1]) >= 5
                        and all(f_(s_, cur[1]) < 10 for s_ in cur[2])):   # only small numbers (list items, a chapter's
                                                                          # first line), with a large jump: the narrow rule
                    for s_ in cur[2]: chosen.pop(s_, None)
            A = sorted(chosen)
            if c in OFFSET_SEEN:
                o_, why_ = OFFSET_SEEN[c]
                for s in scans: out[s] = (s + o_, "iss", why_)
                A, chosen = [], {}
            single = (not spread and r["verdict"] != "CANT-TELL" and not r["gaps"] and not r["repeats"]
                      and (r["verdict"] == "COMPLETE" or len(r["families"]) == 1))
            if out:
                pass   # set above (OFFSET_SEEN)
            elif single:
                # ONE offset followed through the item with no break (analyse's COMPLETE, or a single family): that offset
                # throughout (check 2b: every failure was a GAP item, a several-family item or CANT-TELL; every ruled case
                # was one of these)
                o = r["offset"] if r["verdict"] == "COMPLETE" else r["families"][0]
                for s in scans: out[s] = (s + o, "read" if (s + o) in nums[s] else "iss", "")
            elif A:
                import bisect
                for s in scans:
                    if s in chosen:
                        out[s] = (f_(s, chosen[s]), "read", "spread" if spread else ""); continue
                    k = bisect.bisect_left(A, s)
                    b, a_ = (A[k - 1] if k else None), (A[k] if k < len(A) else None)
                    ob, oa = (chosen[b] if b is not None else None), (chosen[a_] if a_ is not None else None)
                    if ob is not None and oa is not None and ob != oa:
                        out[s] = (None, "?", f"the offset changes between PDF pages {b} and {a_}")
                    else:
                        out[s] = (f_(s, ob if ob is not None else oa), "iss", "spread" if spread else "")
            else:
                prv, nxt = neighbours.get(c, (None, None)); kp = span(prv) if prv else None; kn = span(nxt) if nxt else None
                yr = year_of(c)
                if kp and kn and yr and year_of(prv) == yr == year_of(nxt) and kn[0] - kp[1] - 1 == len(scans):
                    o = kp[1] + 1 - scans[0]
                    for s in scans: out[s] = (s + o, "vol", f"between {prv} and {nxt}")
                elif c in COUNTED:
                    ft = FIRST_TEXT.get(c, scans[0])
                    for s in scans:
                        out[s] = (s - ft + 1, "count", COUNTED[c]) if s >= ft else (None, "skipped", "before the first page of text")
                else:
                    why = "no page number read" if not r["numbered"] else "no two nearby pages agree on a number"
                    for s in scans: out[s] = (None, "?", why)
                    if not r["numbered"]: stats["items with no number read (candidates for a look)"] += 1
            if c in SEGMENTS:
                for s in scans:
                    for lo_, hi_s, off_, kind_, note_ in SEGMENTS[c]:
                        if lo_ <= s <= hi_s:
                            if off_ is None:
                                out[s] = (None, kind_, note_)
                            else:
                                n_ = 2 * s + off_ if spread else s + off_
                                rd_ = n_ in nums[s] or (spread and n_ + 1 in nums[s])
                                if n_ < 1:   # before printed page 1 (the rule below does not see a spread's range)
                                    out[s] = (None, "front", "before printed page 1; " + note_)
                                else:
                                    out[s] = (n_, "read" if rd_ else kind_, note_)
                            break
            if spread:
                out = {s: ((f"{n}–{n + 1}" if n is not None else None), src, note) for s, (n, src, note) in out.items()}
            rr = roman_runs(item_pages(c))
            if rr:
                lo, hi = min(rr), max(rr); off0 = rr[lo][0] - lo
                for s in scans:
                    if s in rr:
                        v, rd = rr[s]; out[s] = (_roman(v), "read" if rd else "iss", "roman")
                    elif s < lo and s + off0 >= 1 and out.get(s, (None, "?", ""))[1] != "read" \
                            and not any(out.get(u, (None, "", ""))[1] == "read" and out[u][2] != "roman" for u in range(s, lo)):
                        # back from the run's first anchor, to the item's first page (wrapper and advertisement pages
                        # come first), while no arabic number has been read on the way
                        out[s] = (_roman(s + off0), "iss", "roman")
                    elif lo <= s <= hi + 2 and out.get(s, (None, "?", ""))[1] == "iss":
                        out[s] = (None, "?", "between a roman and an arabic numbering")   # a break: neither extrapolates across
            for s in scans:
                n, src, note = out[s]
                if s < FIRST_TEXT.get(c, 0):   # a digitiser's sheets before the item itself (every branch)
                    n, src, note = None, "skipped", "before the first page of text (FIRST_TEXT)"
                if n is not None and not isinstance(n, str) and n < 1 and src in ("read", "iss", "vol"):
                    n, src, note = None, "front", "before printed page 1"
                disp = {"read": f"{n}", "iss": f"{n} (extrap. from iss.)", "vol": f"{n} (extrap. from vol.)",
                        "count": f"{n} (counted)"}.get(src, "?" if src == "?" else "")
                f.write(f"{c}\t{s}\t{'' if n is None else n}\t{src}\t{disp}\t{note}\n"); stats[src] += 1
    tot = sum(v for k, v in stats.items() if not k.startswith("items"))
    print("\n".join(RG.report(final, a.out, ("item", "pdf_page"), ("printed", "source", "printed_display"))))
    os.replace(a.out, final)
    print(f"{len(rows)} items, {tot} PDF pages → {final}; " + ", ".join(f"{k} {v} ({100*v/max(1,tot):.1f}%)" for k, v in stats.most_common()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("scan", "simulate", "simulate-last", "map"))
    ap.add_argument("--out"); ap.add_argument("--items"); ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--preferred", action="store_true", help="read each page's PREFERRED reading (ocr-preferred/)")
    a = ap.parse_args()
    PREFERRED = a.preferred
    {"scan": scan, "simulate": simulate, "simulate-last": simulate_last, "map": page_map}[a.mode](a)
