#!/usr/bin/env python3
"""Which pages of a source a dowse reads: the forewords of dictionaries, the non-literary parts of literary magazines
(2026-10-20; the editor).

    tools/dowse-page-scope.py profile TEXT [--first N] [--last M]
    tools/dowse-page-scope.py literary SOURCE --texts GLOB [--date D] [--write]

THE SCOPE FILE, dowse/<source>/scope.tsv: one text a line, «<text stem> TAB <pages in scope> TAB <why>», the pages as
«1-4,120-122» (PDF pages; «all» for the whole text, «none» for none). `dowse-brief-fill.py --propose-ranges` then
proposes readers over those pages only (never a range across a page out of scope), and its coverage check asks every
page in scope read once and no page out of scope read. A text the file does not name is read whole.

profile: the pages of one text, a line each (PDF page, words, the share of its lines that look like dictionary
entries, its first line), the first N and last M pages (default 25 and 10), to choose a dictionary's front and back
matter by eye; the scope file for it is then written by hand, with the reason. Reads the text only; writes nothing.

literary: a magazine whose volumes carry a contents table («TABELO DE LA ENHAVO», La Revuo 1906–1912) is scoped piece
by piece: the table's sections Literaturo (Tradukoj, Originaloj), Teatraĵoj, Poezioj and Muziko are out; everything else
(Diversaĵoj, Bibliografio, Gazetoj, Ĵurnaloj, Kroniko, Internacia Vivo …), the front files (the volume's «.0» files: its
title, contents, covers) and every page the tool cannot place are in. A page's printed number is read from its running
head and fitted to the PDF page by the offset most of the issue's pages agree on; the page is given to the piece whose
first page is the last at or before it. A page goes out only when its piece is out AND a running head beside it (its
own or a neighbour's) shares a word with that piece's title, so that a lost page number in the table never takes an
in-scope page out with it. A volume with no contents table is read whole (listed). Writes, with --write, create-only:
dowse/<source>/scope.tsv and dowse/<source>/SCOPE-REVIEW-<date>.md (every volume's out pieces by section, the titles
that name the movement flagged for a look, the pages and words in and out). Without --write it prints the totals only.
Ezri, 2026-10-20."""
import glob, os, re, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

OUT_SECTIONS = {"LITERATURO", "TEATRAĴOJ", "TEATRAJOJ", "POEZIOJ", "MUZIKO"}
IN_SECTIONS = {"DIVERSAĴOJ", "DIVERSAJOJ", "BIBLIOGRAFIO", "GAZETOJ", "ĴURNALOJ", "JURNALOJ", "KRONIKO", "INTERNACIA VIVO",
               "POŜTKARTOJ KAJ DIVERSAĴOJ", "OFICIALA PARTO", "LIBROJ"}
SUB = {"TRADUKOJ", "ORIGINALOJ", "ORIGINALAĴOJ", "ORIGINALAJOJ"}
# titles of out pieces that name the movement: listed for a look (a parody, a polemic, a hagiography is in)
MOVEMENT = re.compile(r"esperant|zamenhof|kongres|samidean|verda|ido\b|idist|reform|lingvo internacia|internacia lingvo|"
                      r"volap|delegacio|akademi|komitat|gazet|propagand|movad|stelo", re.I)

def pages(path):
    """-> [(PDF page, text)]"""
    t = open(path, encoding="utf-8").read()
    ps = re.split(r"^=== page (\d+) ===[ \t]*$", t, flags=re.M)
    return [(int(ps[i]), ps[i + 1]) for i in range(1, len(ps) - 1, 2)]

def entry_share(txt):
    """The share of a page's lines that look like dictionary entries: a headword then a comma, a dash or a gloss mark
    within the first two words («abaisser, mallevi»; «abrikot-o, абрикос»; «akr-a, острый»)."""
    ls = [l.strip() for l in txt.split("\n") if len(l.strip()) > 3]
    if not ls: return 0.0
    hit = sum(1 for l in ls if re.match(r"^[\w’'/-]{2,25}[,;:]\s", l) or re.match(r"^[a-zĉĝĥĵŝŭ]+[-/'’][a-zĉĝĥĵŝŭ]{1,3}\b", l))
    return hit / len(ls)

def profile(path, first, last):
    ps = pages(path)
    print(f"{os.path.relpath(path, G)}: {len(ps)} pages")
    show = ps[:first] + ([None] if len(ps) > first + last else []) + ps[max(first, len(ps) - last):]
    for x in show:
        if x is None: print("   …"); continue
        n, t = x
        fl = next((l.strip() for l in t.split("\n") if l.strip()), "")
        print(f"  PDF {n:>4} · {len(t.split()):>5} words · entries {entry_share(t):.0%} · {fl[:70]}")

def head_lines(txt):
    return [l.strip() for l in txt.split("\n") if l.strip()][:2]

def printed_number(txt):
    for l in head_lines(txt):
        m = re.match(r"^\D{0,3}(\d{1,3})\b", l) or re.search(r"\b(\d{1,3})\D{0,4}$", l)
        if m: return int(m.group(1))
    return None

# words that never take a page out: the movement's own (a piece about it is in) and the magazine's
NEVER = {"revuo", "esper", "lingv", "inter", "nacia", "kongr", "zamen", "samid", "movad", "grupo", "verda", "stelo"}

def words_of(s):
    return {w[:5] for w in re.findall(r"[a-zĉĝĥĵŝŭA-ZĈĜĤĴŜŬ]{4,}", s.lower())} - NEVER

def running_head(txt):
    """The page's running head: the uppercase words of its first line (La Revuo prints «MARTA 203», «202 LA REVUO»)."""
    fl = next((l.strip() for l in txt.split("\n") if l.strip()), "")
    return {w[:5].lower() for w in re.findall(r"\b[A-ZĈĜĤĴŜŬÉ']{4,}\b", fl)} - NEVER

IN_HEAD = {w[:5].lower() for s in IN_SECTIONS for w in s.split() if len(w) >= 4} - {"inter", "parto"}

def parse_toc(path):
    """-> [(first printed page, section, title)], one per installment, sorted by page."""
    sec, out, last = None, [], ""
    for l in open(path, encoding="utf-8").read().split("\n"):
        s = l.strip().strip(".").strip()
        up = re.sub(r"\s+", " ", s)
        if up and up == up.upper() and re.fullmatch(r"[A-ZĈĜĤĴŜŬÉ' ,.-]{4,40}", up):
            if up in SUB or up.startswith("TABELO") or "LA REVUO" in up: continue
            sec = up; last = ""; continue
        # the bibliography, music, press and chronicle sections run their entries together, «Title, de X (284). — …»
        br = re.findall(r"([^—()]{3,}?)\s*\((\d{1,3}(?:\s*,\s*\d{1,3})*)\)", s) if sec else []
        if br:
            for title, ns in br:
                for p in re.findall(r"\d{1,3}", ns):
                    out.append((int(p), sec, title.strip(" .—")))
            continue
        m = re.search(r"(\d{1,3}(?:\s*[,.]\s*\d{1,3})*)[\s.,;:]*$", s)
        if not sec or not s: continue
        head = s[:m.start()] if m else s
        if re.search(r"[A-Za-zĉĝĥĵŝŭ]{3}", head):
            last = re.sub(r"[ .]{3,}", " ", head).strip(" .,:")   # a title; its pages may follow on the next line
        if m and last:
            for p in re.findall(r"\d{1,3}", m.group(1)):
                if int(p) > 0: out.append((int(p), sec, last))
    return sorted(set(out))

SHOW = None   # --show STEM: every page of the texts whose name holds STEM, with its piece and head (a check)
SHOW_UNPLACED, UNPLACED_MIN = False, 4   # --unplaced prints them
UNPLACED = Counter()   # (volume, running-head words) of pages kept in because their head names no piece of the contents
OUT_HEADS = set()      # head words ruled out by hand, per volume: dowse/<source>/scope-heads-out.txt, «volume TAB word TAB why»

def literary(source, texts_glob, date, write):
    D = os.path.join(G, "dowse", source)
    hp = os.path.join(D, "scope-heads-out.txt")
    if os.path.exists(hp):
        OUT_HEADS.update((l.split("\t")[0].strip(), l.split("\t")[1].strip().lower()[:5]) for l in open(hp, encoding="utf-8")
                         if l.strip() and not l.startswith("#") and l.count("\t") >= 1)
    files = sorted(glob.glob(os.path.join(G, texts_glob)))
    if not files: sys.exit(f"no texts match {texts_glob}")
    vols = {}
    for f in files:
        m = re.search(r"\.(\d{4})\.", os.path.basename(f))
        vols.setdefault(m.group(1) if m else os.path.basename(f), []).append(f)
    rows, review, tot = [], [], Counter()
    for v, fs in sorted(vols.items()):
        if tot: print(f"  {pv}: in {tot['in'] - pin:,}, out {tot['out'] - pout:,}; contents entries {nt}; texts read whole {nwhole}")
        pv, pin, pout, nwhole = v, tot["in"], tot["out"], 0
        front = [f for f in fs if re.search(r"\.0(\.\d+)?\.txt$", f)]
        toc_f = next((f for f in front if "TABELO DE LA ENHAVO" in open(f, encoding="utf-8").read()), None)
        toc = parse_toc(toc_f) if toc_f else []; nt = len(toc)
        review.append(f"\n## {v}\n")
        if not toc:
            review.append("No contents table found: the volume is read whole.\n")
        for f in fs:
            st = os.path.basename(f)[:-4]; ps = pages(f)
            w = sum(len(t.split()) for _n, t in ps)
            if f in front or not toc:
                rows.append((st, "all", "front matter" if f in front else "no contents table")); tot["in"] += w; continue
            nums = [(n, printed_number(t)) for n, t in ps]
            offs = Counter(p - n for n, p in nums if p is not None)
            off, agree = offs.most_common(1)[0] if offs else (None, 0)
            if off is None or agree < max(3, len(ps) // 4):
                rows.append((st, "all", "printed pages not found")); tot["in"] += w; nwhole += 1
                review.append(f"- `{st}`: printed page numbers not found ({agree} of {len(ps)} pages agree): read whole.\n"); continue
            starts = [s for s, _sec, _t in toc]
            heads = {n: " ".join(head_lines(t)) for n, t in ps}
            rheads = {n: running_head(t) for n, t in ps}
            # THE RUNNING HEADS DECIDE (the contents' page numbers are too often lost to the OCR to place a piece): a page
            # whose head names an out piece of the volume better than any in piece is out; a head naming an in-scope
            # section, or an in piece, keeps it in; a page with no head word (an even page, «LA REVUO») is out only
            # when a neighbour is out and neither is in
            dec, why = {}, {}
            for n, _t in ps:
                own = rheads.get(n, set())
                if not own: dec[n] = None; continue
                if own & IN_HEAD: dec[n] = "in"; continue
                need = 1   # one word of five letters in common, the movement's words excepted (NEVER)
                bo = max(((len(own & words_of(t_)), (s_, sec_, t_)) for s_, sec_, t_ in toc if sec_ in OUT_SECTIONS), default=(0, None))
                bi = max(((len(own & words_of(t_)), (s_, sec_, t_)) for s_, sec_, t_ in toc if sec_ not in OUT_SECTIONS), default=(0, None))
                ruled = {w for w in own if (v, w) in OUT_HEADS}
                if ruled: dec[n], why[n] = "out", (0, "RULED BY HEAD", " ".join(sorted(ruled))); continue
                if bo[0] >= need and bo[0] > bi[0]: dec[n], why[n] = "out", bo[1]
                else:
                    dec[n] = "in"
                    if not bi[0]: UNPLACED[(v, " ".join(sorted(own)))] += 1
            inp, outp = [], Counter()
            for n, t in ps:
                d = dec[n]
                if d is None:
                    nb = [dec.get(n - 1), dec.get(n + 1)]
                    d = "out" if "out" in nb and "in" not in nb else "in"
                    if d == "out": why[n] = why.get(n - 1) or why.get(n + 1)
                if d == "out":
                    outp[why[n]] += 1; tot["out"] += len(t.split())
                else:
                    inp.append(n); tot["in"] += len(t.split())
            spans = []
            for n in inp:
                if spans and n == spans[-1][1] + 1: spans[-1][1] = n
                else: spans.append([n, n])
            rows.append((st, ",".join(f"{a}-{b}" if a != b else f"{a}" for a, b in spans) or "none",
                         f"offset {off:+d} ({agree} of {len(ps)} pages); {sum(outp.values())} pages of literature out"))
            if SHOW and SHOW in st:
                for n, t in ps:
                    w_ = why.get(n)
                    print(f"  {st} PDF {n} p{n + off} {'IN ' if n in inp else 'OUT'} · {w_[1][:10] + ' · ' + w_[2][:40] if w_ else '-'} · head «{heads[n][:50]}» {sorted(rheads[n])}")
            if outp:
                review.append(f"- `{st}` (printed = PDF {off:+d}): out: " + "; ".join(
                    f"{'**⟶ look:** ' if MOVEMENT.search(t_) else ''}{sec.title()}, {t_} (p. {s}, {c} PDF p.)" for (s, sec, t_), c in sorted(outp.items())) + "\n")
    print(f"  {pv}: in {tot['in'] - pin:,}, out {tot['out'] - pout:,}; contents entries {nt}; texts read whole {nwhole}")
    print(f"{source}: {len(files)} texts in {len(vols)} volumes; words in {tot['in']:,}, out {tot['out']:,} "
          f"({100 * tot['out'] / max(1, tot['in'] + tot['out']):.0f}% out)")
    unpl = sorted(((c, v, h) for (v, h), c in UNPLACED.items() if c >= UNPLACED_MIN), reverse=True)
    review.append("\n## Running heads that name no piece of the contents (kept in)\n\n"
                  f"Heads on {UNPLACED_MIN} or more pages; a literary one goes out by a line in scope-heads-out.txt.\n\n"
                  + "".join(f"- {v}: «{h}», {c} pages\n" for c, v, h in unpl))
    if SHOW_UNPLACED:
        for c, v, h in unpl: print(f"  unplaced {v}: «{h}» {c} pages")
    if not write:
        print("(dry run: --write writes scope.tsv and the review)"); return
    os.makedirs(D, exist_ok=True)
    sp, rp = os.path.join(D, "scope.tsv"), os.path.join(D, f"SCOPE-REVIEW-{date}.md")
    for p in (sp, rp):
        if os.path.exists(p): sys.exit(f"refusing: {os.path.relpath(p, ROOT)} exists")
    with open(sp, "x", encoding="utf-8") as fh:
        fh.write("# text\tpages in scope\twhy (tools/dowse-page-scope.py literary, " + date + ")\n")
        fh.write("\n".join("\t".join(r) for r in rows) + "\n")
    with open(rp, "x", encoding="utf-8") as fh:
        fh.write(f"# {source}: the pages in scope, {date}\n\n`[Ezri, by tools/dowse-page-scope.py literary; the editor, 2026-10-20: "
                 "kept in scope only where it relates directly to Esperanto; belles lettres in only if about the movement (parody, "
                 "polemic, hagiography). Out: the contents table's Literaturo, Teatraĵoj, Poezioj, Muziko; in: the rest, the front "
                 f"files and every page not placed.]`\n\nWords in scope {tot['in']:,}; out {tot['out']:,}. "
                 "Titles marked «⟶ look» name the movement: in if parody, polemic or hagiography (a line in scope.tsv by hand).\n"
                 + "".join(review))
    print(f"wrote {os.path.relpath(sp, ROOT)} and {os.path.relpath(rp, ROOT)}")

REPLACE = False

def copies(source, work, align, write):
    """copies SOURCE --work TEXT --align TSV [--write] (2026-10-20; the doubles method, kind 1, Ezri's part: «the page skip
    for kind 1 once a pair is triangulated»; Miles, relayed: test on Privat vol. 2, then Volaspodel): for a COPIES work
    whose copies are one text (one same_text group) and which the editor ruled triangulated, the pages read once instead of
    twice. ALIGN is tools/ocr-copy-align.py's table (one row per printed page). A printed page is read once only when
    both copies hold it (BOTH), with no quality flag (QUALITY GAP, DISAGREE) and both at absence quality (A+B): from the
    copy COPIES lists first (its primary), throughout. A PDF page of the other copy is left out only when
    every printed page on it is so read in the other copy; a page only one copy holds, a flagged page, and every page the
    table does not name stay in both. Writes the two copies' rows into dowse/<source>/scope.tsv (a new file, or rows
    added for texts it does not yet name; refused for a text it names). Without --write prints what it would write."""
    import ast, csv as _csv
    src = open(os.path.join(ROOT, "tools", "ocr-dowse.py"), encoding="utf-8").read()
    COP = next(ast.literal_eval(n.value) for n in ast.parse(src).body
               if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "COPIES" for t in n.targets))
    hits = [e for e in COP if work.lower() in e["work"].lower()]
    if len(hits) != 1: sys.exit(f"refusing: {len(hits)} COPIES works match «{work}»")
    e = hits[0]
    if not e.get("triangulated"): sys.exit(f"refusing: «{e['work']}» is not ruled triangulated (COPIES «triangulated» is empty)")
    rows = [r for r in _csv.DictReader((l for l in open(align, encoding="utf-8") if not l.startswith("#")), delimiter="\t")]
    items = sorted({r["a_item"] for r in rows if r["a_item"]} | {r["b_item"] for r in rows if r["b_item"]})
    if not any(set(items) <= set(g) for g in e.get("same_text", [])):
        sys.exit(f"refusing: the copies {items} are not one same_text group of «{e['work']}» (kind 0 never skips a page)")
    order = [c[0] for c in e["copies"]]
    # A COPY THAT SCANS PAGES TWICE (COPIES «repeats», Miles 2026-10-20 17:3x: the Scribd Privat's PDF 51–63 = 38–50,
    # n = n−13): a repeat counts as its original page; of the two, one is read: the repeat where it reads better (a fifth
    # element listing those repeat pages, or the note's «better on PDF a, b, c and d»), else the original
    twin, prefer = {}, set()   # (item, repeat page) -> original page; (item, page) read in place of its twin
    for rp in e.get("repeats", []):
        it_, (r1, r2), (o1, _o2), note = rp[0], rp[1], rp[2], rp[3]
        for k in range(r2 - r1 + 1): twin[(it_, r1 + k)] = o1 + k
        better = rp[4] if len(rp) > 4 else [int(x) for x in re.findall(r"\d+", (re.search(r"better on PDF ([\d, and]+)", note) or [None, ""])[1])]
        prefer |= {(it_, p) for p in better}
    canon = lambda x: (x[0], twin.get(x, x[1])) if x else x
    TRI = {tuple(t) for t in e["triangulated_pages"]} if e.get("triangulated_pages") else None
    if TRI is not None: TRI |= {(t[2], t[3], t[0], t[1]) for t in list(TRI)}   # either copy as A
    need, done_elsewhere, read_once = {}, {}, Counter()   # (item, pdf) -> printed pages on it that need it / are read in the other
    for r in rows:
        a = canon((r["a_item"], int(r["a_pdf_page"]))) if r["a_item"] and r["a_pdf_page"] else None
        b = canon((r["b_item"], int(r["b_pdf_page"]))) if r["b_item"] and r["b_pdf_page"] else None
        safe = r["verdict"] == "BOTH" and not r["quality"].strip() and r["at_absence_quality"].strip() == "A+B" and a and b
        # THE RULING'S OWN PAGES (COPIES «triangulated_pages», 2026-10-20, Volaspodel: «only the 87 agreeing shared
        # pages»): where the entry lists them, a pair outside the list is read in both, whatever the table says
        if safe and TRI is not None:
            safe = (r["a_item"], int(r["a_pdf_page"]), r["b_item"], int(r["b_pdf_page"])) in TRI
        if safe:
            # one copy throughout, the one COPIES ranks first, not the better score page by page (the scores differ by
            # noise, 0.89 against 0.95, and the reading would scatter over both copies)
            keep, drop = (a, b) if order.index(a[0]) < order.index(b[0]) else (b, a)
            need.setdefault(keep, set()).add(r["printed"]); done_elsewhere.setdefault(drop, set()).add(r["printed"])
            read_once[keep[0]] += 1
        else:
            for x in (a, b):
                if x: need.setdefault(x, set()).add(r["printed"])
    dropped = {k for k in done_elsewhere if k not in need}
    out_rows, total = [], {}
    for it in items:
        path = next((os.path.join(G, "sources", sub, it + ".txt") for sub in ("ocr-preferred", "born-digital-text")
                     if os.path.exists(os.path.join(G, "sources", sub, it + ".txt"))), None)
        if not path: sys.exit(f"no text for {it}")
        allp = [n for n, _t in pages(path)]
        orig_of = {r_: o_ for (i_, r_), o_ in twin.items() if i_ == it}
        rep_of = {o_: r_ for r_, o_ in orig_of.items()}
        def kept(n):
            o = orig_of.get(n, n)                       # the page it stands for
            if (it, o) in dropped: return False         # read in the other copy
            if o in rep_of:                             # a page scanned twice: one of the two
                use_rep = (it, rep_of[o]) in prefer
                return n == (rep_of[o] if use_rep else o)
            return True
        keep = [n for n in allp if kept(n)]
        spans = []
        for n in keep:
            if spans and n == spans[-1][1] + 1: spans[-1][1] = n
            else: spans.append([n, n])
        out_rows.append((it, ",".join(f"{x}-{y}" if x != y else f"{x}" for x, y in spans) or "none",
                         f"kind 1, {e['work']}: {len(allp) - len(keep)} PDF pages left out, each of their printed pages read in the other copy"
                         + (f" or in its repeat ({len(orig_of)} pages scanned twice, COPIES «repeats»; the repeat read on {sorted(p for i_, p in prefer if i_ == it)})" if orig_of else "") + " "
                         f"(BOTH, no quality flag, A+B; read in the copy COPIES ranks first; {os.path.basename(align)}); triangulated: {e['triangulated'][:60]}"))
        total[it] = (len(allp), len(allp) - len(keep))
    for it, (n, d) in total.items(): print(f"  {it}: {n} PDF pages, {d} left out")
    print(f"  printed pages read once, by copy: " + "; ".join(f"{k} {v}" for k, v in read_once.items()))
    print(f"  printed pages not read once (flagged, outside the ruling, or in one copy only): {len({p for ps in need.values() for p in ps}) - sum(read_once.values())}")
    if not write:
        for r in out_rows: print("  " + "\t".join(r))
        print("(dry run: --write to write)"); return
    D = os.path.join(G, "dowse", source); os.makedirs(D, exist_ok=True)
    sp = os.path.join(D, "scope.tsv")
    have = set()
    if os.path.exists(sp):
        have = {l.split("\t")[0] for l in open(sp, encoding="utf-8") if l.strip() and not l.startswith("#")}
        clash = [r[0] for r in out_rows if r[0] in have]
        if clash and REPLACE:
            # --replace: this tool's own rows for these texts rewritten (a row written by hand is never replaced)
            old = open(sp, encoding="utf-8").read().split("\n")
            hand = [l for l in old if l.split("\t")[0] in clash and "kind 1," not in l]
            if hand: sys.exit(f"refusing: {os.path.relpath(sp, ROOT)} has hand-written rows for {[l.split(chr(9))[0] for l in hand]}")
            with open(sp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(l for l in old if l.split("\t")[0] not in clash).rstrip("\n") + "\n")
            have -= set(clash)
        elif clash: sys.exit(f"refusing: {os.path.relpath(sp, ROOT)} already names {clash} (--replace rewrites this tool's own rows)")
    new_file = not os.path.exists(sp)
    with open(sp, "x" if new_file else "a", encoding="utf-8") as fh:
        if new_file: fh.write("# text\tpages in scope\twhy (tools/dowse-page-scope.py)\n")
        fh.write("\n".join("\t".join(r) for r in out_rows) + "\n")
    print(f"wrote {len(out_rows)} rows to {os.path.relpath(sp, ROOT)}")

def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "copies" and "--work" in a and "--align" in a:
        global REPLACE
        REPLACE = "--replace" in a
        al = a[a.index("--align") + 1]
        return copies(a[1], a[a.index("--work") + 1], al if os.path.isabs(al) else os.path.join(G, al), "--write" in a)
    if len(a) >= 2 and a[0] == "profile":
        f = int(a[a.index("--first") + 1]) if "--first" in a else 25
        l = int(a[a.index("--last") + 1]) if "--last" in a else 10
        p = a[1] if os.path.isabs(a[1]) else os.path.join(G, a[1])
        return profile(p, f, l)
    if len(a) >= 2 and a[0] == "literary" and "--texts" in a:
        d = a[a.index("--date") + 1] if "--date" in a else __import__("datetime").date.today().isoformat()
        global SHOW, SHOW_UNPLACED
        SHOW = a[a.index("--show") + 1] if "--show" in a else None
        SHOW_UNPLACED = "--unplaced" in a
        return literary(a[1], a[a.index("--texts") + 1], d, "--write" in a)
    sys.exit(__doc__)

if __name__ == "__main__":
    main()
