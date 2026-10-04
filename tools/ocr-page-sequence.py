#!/usr/bin/env python3
r"""ocr-page-sequence — does the SCAN hold every printed page? Printed page numbers against scan order.

    tools/ocr-page-sequence.py scan --out <tsv> [--items <regex>]        # per item: verdict + evidence
    tools/ocr-page-sequence.py simulate --n 100 [--seed 1]                # validation: drop an inner page, must be found
    tools/ocr-page-sequence.py simulate-last --n 100 [--seed 1]           # validation: drop an issue's LAST page

WHY (approved by the editor 2026-09-29, after Kapis of BitArkivo asked whether the AI had also been told to check, by
reading the page numbers, whether any pages were missing). Every earlier check asks whether each SCANNED page was read well. None asks whether the scan holds
every PRINTED page. A leaf never scanned is invisible to every OCR check, and an absence claim would silently cover
it. Kapis finds such gaps in practice (*La Suda Kruco* 1931 n128 and 1934 n163 each lack their last page).
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
   scan pages than that mode is flagged.
VERDICT per item: GAP only where the numbering steps UP and never back (a step up and a step back is misread or
irregular numbering: LEAD, for a look); COMPLETE (the numbering followed from the first pages to the last — within 1 scan page of each end,
over at least half the pages — and no gap), GAP (the evidence), PARTLY-VERIFIED (no gap seen, but the numbering could
not be followed over the whole item: a loss outside the followed span would be invisible — these stretches go to the
vision read of the page-number strip, Kapis's method), CANT-TELL (too few readable numbers).
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
            nxt = next((t for t in scans[i + 1:] if nums[t]), None)
            if nxt is not None and cand[0] in {n - nxt for n in nums[nxt]}:
                seq.append((s, cand[0])); prev = cand[0]
        if seq and "span" not in res:
            res["span"] = (seq[0][0], seq[-1][0], len(seq))   # the first family followed: its first and last page
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
    res["first_printed"] = scans[0] + main; res["last_printed"] = scans[-1] + main; res["offset"] = main
    # COMPLETE only if the numbering was FOLLOWED from the item's first pages to its last (within 1 scan page of
    # each end); otherwise the pages outside the followed span are UNVERIFIED — a loss there could not be seen.
    sp = res.get("span")
    if res["gaps"] and res["repeats"]:
        # a step up AND a step back: misread or irregular numbering, not a demonstrated loss — a lead for a look
        res["verdict"] = "LEAD"
    elif res["gaps"]:
        res["verdict"] = "GAP"
    elif sp and sp[0] <= scans[0] + 1 and sp[1] >= scans[-1] - 1 and sp[2] >= 0.5 * len(scans):
        res["verdict"] = "COMPLETE"
    else:
        res["verdict"] = "PARTLY-VERIFIED"
        res["unverified"] = (f"scan {scans[0]}–{sp[0] - 1}, {sp[1] + 1}–{scans[-1]}" if sp else "all")
    return res


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
        rows[c] = analyse({s: numbers_of(t) for s, t in pg.items()})
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
    # page counts: titles whose issues mostly share a page count
    counts = collections.defaultdict(list)
    for c, r in rows.items():
        counts[title_of(c)].append((c, r["scan_pages"]))
    for t, cl in counts.items():
        if len(cl) < 5:
            continue
        mode, k = collections.Counter(n for _, n in cl).most_common(1)[0]
        if k >= 0.6 * len(cl):
            for c, n in cl:
                if n < mode:
                    rows[c]["short_issue"] = {"pages": n, "title_mode": mode}
    with open(a.out, "w") as f:
        f.write("corpus\tverdict\tscan_pages\tnumbered\toffset\tfirst_printed\tlast_printed\tevidence\n")
        for c, r in sorted(rows.items()):
            ev = []
            for g in r["gaps"]:
                ev.append(f"GAP {g['count']} page(s) missing between printed {g['between'][0]} and {g['between'][1]} (scan {g['after_scan']}–{g['before_scan']})")
            for g in r["repeats"]:
                ev.append(f"REPEAT/RESTART step {g['step']} between scan {g['after_scan']} and {g['before_scan']}")
            for g in r.get("join_gaps", []):
                ev.append(f"JOIN printed {g['printed_missing'][0]}–{g['printed_missing'][-1]} missing before {g['next']}")
            if "short_issue" in r:
                ev.append(f"SHORT {r['short_issue']['pages']} pages against the title's usual {r['short_issue']['title_mode']}")
            v = r["verdict"]
            if v == "COMPLETE" and ev:
                v = "LEAD"
            f.write(f"{c}\t{v}\t{r['scan_pages']}\t{r['numbered']}\t{r.get('offset','')}\t{r.get('first_printed','')}\t{r.get('last_printed','')}\t{' · '.join(ev)}\n")
    vc = collections.Counter()
    for c, r in rows.items():
        v = r["verdict"]
        if v == "COMPLETE" and (r["repeats"] or r.get("join_gaps") or r.get("short_issue")):
            v = "LEAD"
        vc[v] += 1
    print(f"{len(rows)} items ·", dict(vc), f"· join gaps {len(joins)} · short issues {sum('short_issue' in r for r in rows.values())}")


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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("scan", "simulate", "simulate-last"))
    ap.add_argument("--out"); ap.add_argument("--items"); ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--preferred", action="store_true", help="read each page's PREFERRED reading (ocr-preferred/)")
    a = ap.parse_args()
    PREFERRED = a.preferred
    {"scan": scan, "simulate": simulate, "simulate-last": simulate_last}[a.mode](a)
