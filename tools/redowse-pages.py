#!/usr/bin/env python3
"""The selective redowse of recupelled pages, R1 and R2 (ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md; dowse runbook
D8, the third kind; the editor, 2026-10-25 15:5x).

    tools/redowse-pages.py measure [--date YYYY-MM-DD] [--notice RN-…] [--write]
    tools/redowse-pages.py prep MEASURE.tsv TAG [--source …] [--write]
    tools/redowse-pages.py search TAG [--hits HITS.tsv] [--write]     (R2 for search-only notices: search_only())
    tools/redowse-pages.py merge MEASURE.tsv TAG [--source …]         (R5's config lines, printed: merge())
    tools/redowse-pages.py lost TAG [--write]                         (R5's step 8 on the harvest's missing lines: step8())
    tools/redowse-pages.py status [--notice RN-…] [--tag TAG] --set TEXT [--write]   (R7, «Ezri's status»: status())

R1, triage: each notice of ocr/RECUPEL-NOTICES.tsv whose «Ezri's status» is empty or «pending», its item mapped to the
dowsed sources whose brief-config.json «texts» list it. «no dowse yet» where no dowsed source reads it; «whole redowse
scheduled» where the source is in dowse/REDOWSE-SCHEDULED.tsv; «read by the dowse» where every changed page, as the
readers were given it (dowse/<source>/facts-pages-*.txt), is the current text already; else the pages go to R2.

R2, measure, page by page, the text the dowse read (the readers' pages; for a page no reader was given, the superseded
copy) against the current preferred text:
- the committed lines on the page (profiles/by-source/<source>-dowse.md, the locator's item under its name or key);
- their anchors sought in the new page (folded, letters and digits only): an anchor not found sends the page to R4;
- the persons of the full roster (dowse/ROSTER-FULL-CROSS-ARC-*.txt, the latest; keys of 4 letters or more) found on
  the old page and on the new: a person gained or lost sends the page to R4. This stands in for the proposal's «name
  search on the changed pages, compared with dowse-diff.py», which is not built: a word match on the roster's search
  keys, with no OCR tolerance, which is what a recupelled page should no longer need;
- a page with lines whose anchors all stand and no person gained or lost gets R3 only (the re-pin); a page with no
  lines and no person, nothing.
The lines after the item's first changed page are counted too: R3 re-pins them (their «l. N» moves).

Without --write it prints the summary. --write writes dowse/REDOWSE-PAGES-MEASURE-<date>.md (by source, page by page,
the persons and the lost anchors named) and .tsv, create-only. It writes nothing else: the notice file is Miles's, and
the status column is set once a page is redowsed (R7). Ezri, 2026-10-25."""
import argparse, csv, glob, importlib.util, json, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
NOTICES = os.path.join(G, "ocr", "RECUPEL-NOTICES.tsv")
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
ACTS = ("R4 re-read", "R3 re-pin only", "nothing", "read by the dowse")

spec = importlib.util.spec_from_file_location("harvest_facts", os.path.join(ROOT, "tools", "harvest-facts.py"))
HF = importlib.util.module_from_spec(spec); spec.loader.exec_module(HF)
spec = importlib.util.spec_from_file_location("dowse_undated", os.path.join(ROOT, "tools", "dowse-undated.py"))
DU = importlib.util.module_from_spec(spec); spec.loader.exec_module(DU)

def fold(s):
    """lower case, no accents, letters and digits only (an anchor across a line break or a re-cut hyphen still matches)."""
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))

def names(s):
    """the page's capitalised words, folded (a roster key matched against every word took common words for persons:
    every page of the first run, 2026-10-25, came out «R4»)."""
    return {fold(w) for w in re.findall(r"\b[A-ZÀ-ÞĈĜĤĴŜŬ][\wĉĝĥĵŝŭ'-]{3,}", s)}

W = lambda s: {w.lower() for w in re.findall(r"[\wĉĝĥĵŝŭĈĜĤĴŜŬéèêàâôûç]{4,}", s)}
def anchor_stands(anchor, page):
    """R3's test, as repin-copy.py --dowse makes it: the anchor's words of four letters or more covered at half or more
    by the page's (the whole page here, not a window: a measure, not the re-pin); an anchor of fewer than three such
    words only if it stands whole, folded."""
    want = W(anchor)
    if len(want) < 3: return bool(fold(anchor)) and fold(anchor) in fold(page)
    return len(want & W(page)) / len(want) >= 0.5

def read_pages(src):
    """-> {(item, PDF page): the text the dowse's readers were given}, from dowse/<source>/facts-pages-*.txt («=== teksto:
    ‹item› ===», then «=== page N ===»); the later file wins. The OGE notices of round 1b showed why the superseded copy's
    date will not do: the copy was kept at 12:09, the briefs built at 12:49, the new text written at 16:02."""
    out = {}
    for f in sorted(glob.glob(os.path.join(G, "dowse", src, "facts-pages-*.txt")), key=os.path.getmtime):
        t = open(f, encoding="utf-8", errors="replace").read()
        for blk in re.split(r"^=== teksto: ", t, flags=re.M)[1:]:
            item, _, body = blk.partition(" ===\n")
            for p, x in pages_of(body).items(): out[(item.strip(), p)] = x
    return out

def pages(path):
    """-> {PDF page: its text} of a text with «=== page N ===» heads."""
    return pages_of(open(path, encoding="utf-8", errors="replace").read())

def pages_of(t):
    heads = list(PAGE.finditer(t))
    return {int(m.group(1)): t[m.end():(heads[i + 1].start() if i + 1 < len(heads) else len(t))] for i, m in enumerate(heads)}

def roster_keys():
    p = sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")))[-1]
    keys = set()
    for l in open(p, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        k = l.split("|")[-1].strip()
        if " " not in k and len(k) >= 4: keys.add(fold(k))
    return p, keys

def sources_by_item():
    """item -> [(source, its latest stage brief's mtime)] for the dowsed sources (a facts file in profiles/by-source)."""
    out = {}
    for bc in glob.glob(os.path.join(G, "dowse", "*", "brief-config.json")):
        D = os.path.dirname(bc); src = os.path.basename(D)
        if not os.path.exists(os.path.join(G, "profiles", "by-source", f"{src}-dowse.md")): continue
        briefs = glob.glob(os.path.join(D, "facts-brief-*.md"))
        if not briefs: continue
        bt = max(os.path.getmtime(b) for b in briefs)
        for t in json.load(open(bc, encoding="utf-8")).get("texts", []):
            out.setdefault(os.path.basename(t)[:-4], []).append((src, bt))
    return out

def scheduled():
    p = os.path.join(G, "dowse", "REDOWSE-SCHEDULED.tsv")
    if not os.path.exists(p): return set()
    return {r[0] for r in csv.reader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t") if r and r[0] != "source"}

def page_list(s):
    out = []
    for x in re.split(r"[,\s]+", s.strip()):
        if re.fullmatch(r"\d+-\d+", x): a, b = map(int, x.split("-")); out += range(a, b + 1)
        elif x.isdigit(): out.append(int(x))
    return out

_facts, _read, _pref = {}, {}, {}
def facts(src):
    if src not in _facts:
        _facts[src] = [l for l in open(os.path.join(G, "profiles", "by-source", f"{src}-dowse.md"), encoding="utf-8").read().split("\n")
                       if l.startswith("- $$$")]
    return _facts[src]

def item_lines(src, item):
    """-> [(PDF page, anchor, line)] of the source's lines whose locator cites the item, under its name or its key."""
    stems = {item, HF.item_key(item)}
    rx = re.compile(r"(?:^|; )(?:" + "|".join(re.escape(s) for s in stems) + r"), PDF (\d+)\b")
    out = []
    for l in facts(src):
        fl = DU.fields(l)
        if not fl: continue
        for m in rx.finditer(fl[2]):
            out.append((int(m.group(1)), fl[1], l))
    return out

def measure(a):
    rows = [r for r in csv.DictReader((l for l in open(NOTICES, encoding="utf-8") if not l.startswith("#")), delimiter="\t")]
    rows = [r for r in rows if (r.get("Ezri's status") or "").strip() in ("", "pending") and (not a.notice or r["notice"] in a.notice)]
    by_item, sched = sources_by_item(), scheduled()
    rpath, keys = roster_keys()
    out, triage = [], []
    for r in rows:
        item, kind, sup = r["item"], r["kind"], (r.get("superseded text") or "").strip()
        srcs = by_item.get(item, [])
        if not srcs: triage.append((r["notice"], item, "", "no dowse yet")); continue
        for src, bt in srcs:
            if src in sched: triage.append((r["notice"], item, src, "whole redowse scheduled")); continue
            if kind == "search-only reading added" or not sup:
                triage.append((r["notice"], item, src, "search-only: R2 by the name search, not built")); continue
            sp = os.path.join(G, sup)
            if not os.path.exists(sp): triage.append((r["notice"], item, src, f"superseded copy missing: {sup}")); continue
            new_p = os.path.join(G, "sources", "ocr-preferred", item + ".txt")
            if src not in _read: _read[src] = read_pages(src)
            old, new, was_read = pages(sp), pages(new_p), _read[src]
            lines = item_lines(src, item)
            chg = page_list(r["PDF pages changed"])
            # the page as the readers had it, else (a page no reader was given) the superseded copy's
            olds = {p: was_read.get((item, p), old.get(p, "")) for p in chg}
            if chg and all(fold(olds[p]) == fold(new.get(p, "")) for p in chg):
                triage.append((r["notice"], item, src, "read by the dowse")); continue
            first = min(chg) if chg else 0
            after = sum(1 for p, _a, _l in lines if p > first)
            triage.append((r["notice"], item, src, f"R2: {len(chg)} pages; {after} lines after PDF {first} to re-pin"))
            for p in chg:
                o, n = olds[p], new.get(p, "")
                if fold(o) == fold(n): act, on, lost_anchor, gained, lost = "read by the dowse", [], [], [], []
                else:
                    on = [(an, l) for pp, an, l in lines if pp == p]
                    lost_anchor = [(an, l) for an, l in on if not anchor_stands(an.strip("«»"), n)]
                    ow, nw = names(o) & keys, names(n) & keys
                    gained, lost = sorted(nw - ow), sorted(ow - nw)
                    if lost_anchor or gained or lost: act = "R4 re-read"
                    elif on: act = "R3 re-pin only"
                    else: act = "nothing"
                out.append(dict(notice=r["notice"], source=src, item=item, page=p, lines=len(on), anchors_lost=len(lost_anchor),
                                gained=gained, lost=lost, action=act, lost_lines=[l for _a, l in lost_anchor],
                                read=(item, p) in was_read))
    return rows, triage, out, rpath

def prep(a):
    """R4's inputs, source by source, from a measure's table (the pages marked «R4 re-read»): dowse/<source>/
    redowse-items-<tag>.txt (the items, for the name search's --items @file) and redowse-readers-<tag>.txt (one legilo
    a page, «N: `item` PDF p–p», for dowse-brief-fill.py --readers-file), create-only; prints each page's lines in the
    new text (P1: 80 a legilo, at most 100) and the commands of steps 1, 2 and 4 for the tag."""
    rows = [r for r in csv.DictReader(open(a.measure, encoding="utf-8"), delimiter="\t") if r["action"] == "R4 re-read"]
    lex = sorted(glob.glob(os.path.join(G, "sources", "ocr-work", "ocr-lexicon-*.tsv")))[-1]
    rpath, _k = roster_keys()
    by = {}
    for r in rows: by.setdefault(r["source"], []).append((r["item"], int(r["PDF page"]), r["notice"]))
    for src, pp in sorted(by.items()):
        if a.source and src not in a.source: continue
        D = os.path.join(G, "dowse", src)
        ip, rp = os.path.join(D, f"redowse-items-{a.tag}.txt"), os.path.join(D, f"redowse-readers-{a.tag}.txt")
        for p in (ip, rp):
            if os.path.exists(p): sys.exit(f"{os.path.relpath(p, ROOT)} exists: not overwritten (use a new tag)")
        seen = list(dict.fromkeys((i, p) for i, p, _n in pp))
        items = list(dict.fromkeys(i for i, _p in seen))
        over = []
        for i, p in seen:
            n = len(pages(os.path.join(G, "sources", "ocr-preferred", i + ".txt")).get(p, "").strip("\n").split("\n"))
            if n > 100: over.append(f"{i} PDF {p}: {n} lines")
        readers = " · ".join(f"{k}: `{i}` PDF {p}–{p}" for k, (i, p) in enumerate(seen, 1)) + "."
        if a.write:
            open(ip, "x", encoding="utf-8").write("\n".join(items) + "\n")
            open(rp, "x", encoding="utf-8").write(readers + "\n")
        print(f"{src}: {len(seen)} pages, {len(items)} items; notices {', '.join(sorted({n for _i, _p, n in pp}))}"
              + (f"; OVER 100 LINES: {'; '.join(over)}" if over else ""))
        if a.write:
            T = os.path.join(ROOT, "tools")
            print(f"  wrote {os.path.relpath(ip, ROOT)} and {os.path.relpath(rp, ROOT)}")
            print(f"  python3 {T}/ocr-dowse.py --roster {rpath} --items @{ip} --lexicon {lex} --strong-only --mode shared --write {D}/record-{a.tag}-strong.md")
            print(f"  python3 {T}/dowse-reader-roster.py {src} {rpath} {D}/record-{a.tag}-strong.hits.tsv --date {a.tag} --out-list")
            print(f"  python3 {T}/dowse-candidates.py {src} --date {a.tag}")
            print(f"  python3 {T}/dowse-brief-fill.py {src} {a.tag} --readers-file {rp} --partial \"the selective redowse of the pages recupelled ({a.tag})\" --per-reader --write-returns --group 3")
    if not a.write: print("(dry run: --write writes the two files a source)")

def merge(a):
    """R5's inputs, source by source, from a measure's (or a search's) table and the tag's joined returns: prints the
    lines to add at the end of facts-config.json's «returns» (dowse/<source>/facts-return-<tag>-N.md, the pieces left
    out) and the «redowsed_pages» key that follows it ([{notice, item, pages, tag}], one entry a notice and item), in
    the config's own form (json indent 1), for an Edit by hand: the config is a hand file, never rewritten by a tool.
    Refuses a source whose returns are fewer than its readers (redowse-readers-<tag>.txt)."""
    rows = [r for r in read_tsv(a.measure) if r["action"] == "R4 re-read"]
    by = {}
    for r in rows: by.setdefault(r["source"], {}).setdefault((r["notice"], r["item"]), set()).add(int(r["PDF page"]))
    for src, ee in sorted(by.items()):
        if a.source and src not in a.source: continue
        D = os.path.join(G, "dowse", src)
        rets = sorted((os.path.basename(p) for p in glob.glob(os.path.join(D, f"facts-return-{glob.escape(a.tag)}-*.md"))
                       if re.search(rf"-{re.escape(a.tag)}-\d+\.md$", p)), key=lambda p: int(re.search(r"-(\d+)\.md$", p).group(1)))
        rr = open(os.path.join(D, f"redowse-readers-{a.tag}.txt"), encoding="utf-8").read()
        nread = len(re.findall(r"`[^`]+` PDF \d+–", rr))
        if len(rets) < nread: print(f"{src}: REFUSED, {len(rets)} returns for {nread} readers"); continue
        S = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8"))
        add = [r for r in rets if r not in S["returns"]]
        have = {(e["notice"], e["item"], e["tag"]) for e in S.get("redowsed_pages", [])}
        rp = [dict(notice=n, item=i, pages=sorted(pp), tag=a.tag) for (n, i), pp in sorted(ee.items()) if (n, i, a.tag) not in have]
        print(f"=== {src}: {len(add)} returns to add after {S['returns'][-1]!r}; {len(rp)} «redowsed_pages» entries, "
              f"{sum(len(e['pages']) for e in rp)} pages" + ("; the key exists: add the entries to it" if "redowsed_pages" in S else ""))
        if not a.write:
            print("\n".join(f'  "{r}",' for r in add))
            print(' "redowsed_pages": ' + "\n".join(" " + l if k else l for k, l in enumerate(json.dumps(rp, ensure_ascii=False, indent=1).split("\n"))) + ",")
            continue
        # --write (2026-10-26, the s4 batch: 1,546 lines for 15 configs, too many to place by hand): the returns appended,
        # the entries appended to «redowsed_pages» (the key made after «returns» if missing); only where the config
        # re-dumps byte for byte as it stands (json indent 1), so nothing of the hand file is reformatted
        cp = os.path.join(D, "facts-config.json"); old = open(cp, encoding="utf-8").read()
        dump = lambda o: json.dumps(o, ensure_ascii=False, indent=1) + ("\n" if old.endswith("\n") else "")
        if dump(S) != old: print(f"  {src}: REFUSED --write, the config does not re-dump as it stands (place by hand)"); continue
        S["returns"] += add
        if "redowsed_pages" in S: S["redowsed_pages"] += rp
        else: S = {k2: v for k, v in S.items() for k2, v in ([(k, v), ("redowsed_pages", rp)] if k == "returns" else [(k, v)])}
        open(cp, "w", encoding="utf-8").write(dump(S))
        print(f"  {src}: wrote {len(add)} returns and {len(rp)} entries to {os.path.relpath(cp, ROOT)}")

LOC = re.compile(r"(?:^|; | · )([^·;]+?), PDF (\d+)\b")
HEAD = re.compile(r"^- \$\$\$ (.+?) \$\$\$")

def step8(a):
    """R5's step 8, what the new reading lost (2026-10-26: the first harvest after the 2026-10-25r merge, 1,052
    «missing» and 41 profiles gone): the harvest matches a line by its passage, and a re-read page's passage is a new
    text, so a superseded line that the new reading has in other words counts as missing. This reads the missing lines
    of profiles/build/MISSING-FACTS-LATEST.md and sorts them, source by source: on a redowsed page («redowsed_pages»)
    with its person (the head) still on that page in the current facts file: «re-read, person kept»; with the person no
    longer on the page: «person lost on the page», the step 10 candidates (the lines to restore, «restore»); off the
    redowsed pages: «not a redowsed page», a fault of another kind. --write writes dowse/REDOWSE-LOST-<tag>.md (the lost
    and off-page lines in full), create-only."""
    rep = os.path.join(G, "profiles", "build", "MISSING-FACTS-LATEST.md")
    by, src = {}, None
    for l in open(rep, encoding="utf-8"):
        m = re.match(r"^### (.+?)-dowse\.md — \d+", l)
        if m: src = m.group(1); continue
        if l.startswith("## ") and src: src = None
        if src and l.startswith("- - $$$"): by.setdefault(src, []).append(l[2:].rstrip("\n"))
    out, L = {}, [f"# The selective redowse: what the new reading lost (R5, step 8), {a.tag}", "",
                  f"*Generated by `tools/redowse-pages.py lost {a.tag} --write` from `profiles/build/MISSING-FACTS-LATEST.md` "
                  f"and the current facts files. «Person lost on the page»: the head's name is on no current line citing that "
                  f"page; these are the lines for step 10 (restore). «Re-read, person kept» lines are not listed: the new "
                  f"reading has the person there, in other words.*", ""]
    for s, ll in sorted(by.items()):
        cfg = os.path.join(G, "dowse", s, "facts-config.json")
        rp = set()
        if os.path.exists(cfg):
            for e in json.load(open(cfg, encoding="utf-8")).get("redowsed_pages", []):
                rp |= {(HF.item_key(e["item"]), int(p)) for p in e["pages"]}
        now = {}
        for l in facts(s):
            h = HEAD.match(l)
            if h:
                for m in LOC.finditer(l): now.setdefault((HF.item_key(m.group(1).strip()), int(m.group(2))), set()).add(h.group(1))
        sort = {"re-read, person kept": [], "person lost on the page": [], "not a redowsed page": []}
        for l in ll:
            h = HEAD.match(l)
            pp = {(HF.item_key(m.group(1).strip()), int(m.group(2))) for m in LOC.finditer(l)}
            if not pp & rp: sort["not a redowsed page"].append(l)
            elif h and any(h.group(1) in now.get(p, ()) for p in pp & rp): sort["re-read, person kept"].append(l)
            else: sort["person lost on the page"].append(l)
        out[s] = sort
        print(f"  {s}: " + ", ".join(f"{len(v)} {k}" for k, v in sort.items()))
        L += [f"## {s}", "", ", ".join(f"{len(v)} {k}" for k, v in sort.items()), ""]
        for k in ("person lost on the page", "not a redowsed page"):
            if sort[k]: L += [f"### {k}", ""] + [f"- {x}" for x in sort[k]] + [""]
    tot = {k: sum(len(o[k]) for o in out.values()) for k in ("re-read, person kept", "person lost on the page", "not a redowsed page")}
    print("total: " + ", ".join(f"{v} {k}" for k, v in tot.items()))
    if not a.write: print("(dry run: --write writes dowse/REDOWSE-LOST-<tag>.md)"); return
    md = os.path.join(G, "dowse", f"REDOWSE-LOST-{a.tag}.md")
    if os.path.exists(md): sys.exit(f"{os.path.relpath(md, ROOT)} exists: not overwritten (use a new tag)")
    open(md, "x", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(md, ROOT)}")

def status(a):
    """R7, the status column (Ezri's, in Miles's ocr/RECUPEL-NOTICES.tsv): «Ezri's status» set to --set on the notices
    named (--notice) or listed in the «redowsed_pages» of a tag (--tag, every dowsed source's facts-config). Only that
    column of those rows changes; a row whose status is already another is refused, the file then untouched."""
    want = set(a.notice or [])
    if a.measure:   # the notices a measure's R1 triage gave this status («no dowse yet»: Miles, 2026-10-26 02:1x, «clearer than empty»)
        want |= {c[1].strip() for c in (l.split("|") for l in open(a.measure, encoding="utf-8"))
                 if len(c) > 4 and c[4].strip() == a.triage}
    if a.tag:
        for cfg in glob.glob(os.path.join(G, "dowse", "*", "facts-config.json")):
            want |= {e["notice"] for e in json.load(open(cfg, encoding="utf-8")).get("redowsed_pages", []) if e.get("tag") == a.tag}
    L = open(NOTICES, encoding="utf-8").read().split("\n")
    head = next(l for l in L if l and not l.startswith("#")).split("\t"); k = head.index("Ezri's status")
    out, done, clash = [], [], []
    for l in L:
        c = l.split("\t")
        if c and c[0] in want and len(c) > 1:
            c += [""] * (len(head) - len(c))
            if c[k].strip() not in ("", "pending", a.set): clash.append(f"{c[0]}: {c[k]!r}")
            c[k] = a.set; done.append(c[0]); l = "\t".join(c)
        out.append(l)
    missing = sorted(want - set(done))
    print(f"{len(done)} notices set to «{a.set}»" + (f"; not in the file: {', '.join(missing)}" if missing else ""))
    if clash: sys.exit("refusing, a status already set: " + "; ".join(clash))
    if a.write: open(NOTICES, "w", encoding="utf-8").write("\n".join(out)); print(f"wrote {os.path.relpath(NOTICES, ROOT)}")
    else: print("(dry run: --write writes the notice file)")

def read_tsv(p):
    """rows as dicts, plain tab-split (as dowse-diff.py reads hits tables: a CSV reader stops at a field over 131,072
    characters, and its quoting lost 26 hits of the Jamin run to a stray «"» in an OCR word)."""
    head = None
    for l in open(p, encoding="utf-8", errors="replace"):
        if l.startswith("#") or not l.strip(): continue
        c = l.rstrip("\n").split("\t")
        if head is None: head = c; continue
        yield dict(zip(head, c + [""] * (len(head) - len(c))))

def search_only(a):
    """R2 for «search-only reading added» (Miles, 2026-10-25 19:3x: small capitals round 1 on the rest of the corpus,
    2,043 notices): the preferred text is unchanged, the search text gains the snippets, so the measure is the name
    search's, not the page's words. Without --hits: dowse/redowse-search-items-<tag>.txt (the items of the notices on
    dowsed sources, escaped for --items' fnmatch), create-only, and the one name search over them all. With --hits (that
    search's .hits.tsv): the persons hit on each notice page against every hit the source's earlier searches made there
    (dowse/<source>/record-*.hits.tsv; a redowse tag's only on the pages its readers were given, redowse-readers-<tag>.txt,
    since its search ran over whole items); a person gained sends the page to R4, the form the search read named.
    --write writes dowse/REDOWSE-SEARCH-<tag>.md and .tsv (the columns prep reads), create-only."""
    rows = [r for r in read_tsv(NOTICES) if (r.get("Ezri's status") or "").strip() in ("", "pending")]
    by_item, sched = sources_by_item(), scheduled()
    want = {}
    for r in rows:
        if r["kind"] != "search-only reading added" and (r.get("superseded text") or "").strip(): continue
        for src, _bt in by_item.get(r["item"], []):
            if src in sched: continue
            for p in page_list(r["PDF pages changed"]): want.setdefault((src, r["item"]), {})[p] = r["notice"]
    items = sorted({i for _s, i in want})
    if not a.hits:
        ip = os.path.join(G, "dowse", f"redowse-search-items-{a.tag}.txt")
        print(f"{sum(len(v) for v in want.values())} notice pages on {len(items)} items of {len({s for s, _i in want})} dowsed sources")
        if not a.write: print("(dry run: --write writes the items file and prints the search)"); return
        if os.path.exists(ip): sys.exit(f"{os.path.relpath(ip, ROOT)} exists: not overwritten (use a new tag)")
        open(ip, "x", encoding="utf-8").write("\n".join(glob.escape(i) for i in items) + "\n")
        rpath, _k = roster_keys()
        lex = sorted(glob.glob(os.path.join(G, "sources", "ocr-work", "ocr-lexicon-*.tsv")))[-1]
        print(f"wrote {os.path.relpath(ip, ROOT)}\n  python3 {ROOT}/tools/ocr-dowse.py --roster {rpath} --items @{ip} --lexicon {lex} "
              f"--strong-only --mode shared --write {G}/dowse/REDOWSE-SEARCH-{a.tag}-strong.md")
        return
    # only the notice pages' hits are kept as the table is read (2026-10-26: the 2026-10-25s search wrote 18.4 million
    # hits, 2.7 GB, for 1,645 notice pages)
    wp = {(i, p) for (_s, i), pp in want.items() for p in pp}
    new = {}
    for h in read_tsv(a.hits):
        if h["page"].isdigit() and (h["item"], int(h["page"])) in wp:
            # --tight (2026-10-26, s3's 639 pages an upper bound; the editor): the «exact» tier only, the
            # «near» and «confusion» matches of a small-capital snippet being where a namesake or a common word comes in
            if a.tight and h.get("tier") != "exact": continue
            new.setdefault((h["item"], int(h["page"])), {}).setdefault(h["person"], h["as_read"])
    # --tight: a person who already has a fact citing the page is not gained (the legilo read the whole page and found them)
    onpage = {}
    if a.tight:
        for src in sorted({s for s, _i in want}):
            fp = os.path.join(G, "profiles", "by-source", f"{src}-dowse.md")
            for l in open(fp, encoding="utf-8", errors="replace"):
                m = re.match(r"^- \$\$\$ (.+?) \$\$\$", l)
                if not m: continue
                for x in re.finditer(r"(?:^|; | · )([^·;]+?), PDF (\d+)\b", l):
                    onpage.setdefault((src, x.group(1).strip(), int(x.group(2))), set()).add(fold(m.group(1)))
    old = {}
    for src in sorted({s for s, _i in want}):
        mine = {i for s, i in want if s == src}
        seen = old.setdefault(src, set())
        for f in glob.glob(os.path.join(G, "dowse", src, "record-*.hits.tsv")):
            if os.path.abspath(f) == os.path.abspath(a.hits): continue
            m = re.match(r"record-(.+?)(?:-strong)?\.hits\.tsv$", os.path.basename(f))
            rr = os.path.join(G, "dowse", src, f"redowse-readers-{m.group(1)}.txt") if m else ""
            given = ({(i, int(p)) for i, p in re.findall(r"`([^`]+)` PDF (\d+)–", open(rr, encoding="utf-8").read())}
                     if rr and os.path.exists(rr) else None)
            for h in read_tsv(f):
                if h["item"] in mine and h["page"].isdigit() and (h["item"], int(h["page"])) in wp and (given is None or (h["item"], int(h["page"])) in given):
                    seen.add((h["item"], int(h["page"]), h["person"]))
    out = []
    for (src, item), pp in sorted(want.items()):
        for p, notice in sorted(pp.items()):
            hit = new.get((item, p), {})
            before = {x for i, pg, x in old[src] if i == item and pg == p}
            # BY THE SNIPPETS (2026-10-26, the first run: 91,869 persons «gained» on 122 pages of Amerika Esperantisto, the
            # earlier searches having run on smaller rosters; Oficiala Gazeto, searched on this roster, 0): a person counts
            # as gained only where the form the search read is in the page's snippet reading
            # (sources/ocr-rendersearch/<item>/page-NNNN.names.txt), the reading the notice added
            sp = os.path.join(G, "sources", "ocr-rendersearch", item, f"page-{p:04d}.names.txt")
            snip = fold(open(sp, encoding="utf-8", errors="replace").read()) if os.path.exists(sp) else ""
            raw = sorted(set(hit) - before)
            # and NOT in the page's preferred text, the text the legilo was given (the snippets list every name on the
            # page, so a name already legible there passed the first test: 941 pages of 1,645)
            pp_ = os.path.join(G, "sources", "ocr-preferred", item + ".txt")
            if pp_ not in _pref: _pref[pp_] = {k: fold(v) for k, v in pages(pp_).items()} if os.path.exists(pp_) else {}
            prefp = _pref[pp_].get(p, "")
            gained = [x for x in raw if fold(hit[x]) and fold(hit[x]) in snip and fold(hit[x]) not in prefp]
            if a.tight:
                faced = onpage.get((src, HF.item_key(item), p), set())
                gained = [x for x in gained if fold(x) not in faced]
            out.append(dict(notice=notice, source=src, item=item, page=p, before=len(before), raw=len(raw),
                            gained=[f"{x} «{hit[x]}»" for x in gained], action="R4 re-read" if gained else "nothing"))
    from collections import Counter
    by = Counter((o["source"], o["action"]) for o in out)
    print(f"{len(out)} notice pages: " + "; ".join(f"{v} {k}" for k, v in Counter(o["action"] for o in out).most_common()))
    for src in sorted({o["source"] for o in out}):
        print(f"  {src}: {by[(src, 'R4 re-read')]} R4 re-read, {by[(src, 'nothing')]} nothing; "
              f"{sum(len(o['gained']) for o in out if o['source'] == src)} persons gained by the snippets "
              f"(of {sum(o['raw'] for o in out if o['source'] == src)} new to the page's hits)")
    if not a.write: print("(dry run: --write writes dowse/REDOWSE-SEARCH-<tag>.md and .tsv)"); return
    md, tsv = (os.path.join(G, "dowse", f"REDOWSE-SEARCH-{a.tag}{x}") for x in (".md", ".tsv"))
    for p in (md, tsv):
        if os.path.exists(p): sys.exit(f"{os.path.relpath(p, ROOT)} exists: not overwritten (use a new tag)")
    with open(tsv, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["notice", "source", "item", "PDF page", "persons before", "persons gained", "action"])
        for o in out: w.writerow([o["notice"], o["source"], o["item"], o["page"], o["before"], "; ".join(o["gained"]), o["action"]])
    L = [f"# The selective redowse: search-only notices (R2), {a.tag}", "",
         f"*Generated by `tools/redowse-pages.py search {a.tag} --hits {os.path.relpath(a.hits, G)}{' --tight' if a.tight else ''} --write`"
         f"{' (the «exact» tier only; a person with a fact citing the page not counted)' if a.tight else ''}: the persons the name "
         f"search finds on each page of the «search-only reading added» notices (and those with no superseded copy), against "
         f"every hit the source's earlier searches made on that page. A person gained sends the page to R4; the form is as "
         f"the search read it, in «».*", ""]
    for src in sorted({o["source"] for o in out}):
        L += [f"## {src}", "", f"{by[(src, 'R4 re-read')]} R4 re-read, {by[(src, 'nothing')]} nothing", "",
              "| notice | item | PDF | before | gained | action |", "|---|---|---|---|---|---|"]
        L += [f"| {o['notice']} | {o['item']} | {o['page']} | {o['before']} | {'; '.join(o['gained'])} | {o['action']} |"
              for o in out if o["source"] == src]
        L.append("")
    open(md, "x", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(md, ROOT)} and {os.path.relpath(tsv, ROOT)}")

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prep"); p.add_argument("measure"); p.add_argument("tag"); p.add_argument("--source", nargs="*")
    p.add_argument("--write", action="store_true")
    m = sp.add_parser("measure"); m.add_argument("--date"); m.add_argument("--notice", nargs="*"); m.add_argument("--write", action="store_true")
    m.add_argument("--show", type=int, default=0, help="print the first N pages in full")
    s = sp.add_parser("search"); s.add_argument("tag"); s.add_argument("--hits"); s.add_argument("--write", action="store_true")
    s.add_argument("--tight", action="store_true", help="the «exact» tier only, and not a person with a fact citing the page (2026-10-26)")
    g = sp.add_parser("merge"); g.add_argument("measure"); g.add_argument("tag"); g.add_argument("--source", nargs="*")
    g.add_argument("--write", action="store_true", help="append the returns and entries to each facts-config.json (only one that re-dumps as it stands)")
    o = sp.add_parser("lost"); o.add_argument("tag"); o.add_argument("--write", action="store_true")
    t = sp.add_parser("status"); t.add_argument("--notice", nargs="*"); t.add_argument("--tag"); t.add_argument("--set", required=True)
    t.add_argument("--measure", help="a measure's .md: the notices its triage table gives --triage"); t.add_argument("--triage", default="no dowse yet")
    t.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.cmd == "prep": return prep(a)
    if a.cmd == "merge": return merge(a)
    if a.cmd == "lost": return step8(a)
    if a.cmd == "status": return status(a)
    if a.cmd == "search": return search_only(a)
    rows, triage, out, rpath = measure(a)
    from collections import Counter
    print(f"{len(rows)} notices standing; triage: " + "; ".join(f"{v} {k}" for k, v in Counter(t[3].split(':')[0] for t in triage).most_common()))
    by = Counter((o["source"], o["action"]) for o in out)
    for src in sorted({o["source"] for o in out}):
        print(f"  {src}: " + ", ".join(f"{by[(src, k)]} {k}" for k in ACTS if by[(src, k)])
              + f"; {sum(o['lines'] for o in out if o['source'] == src)} lines on the pages")
    for o in out[:a.show]:
        print(f"  {o['source']} {o['item']} PDF {o['page']} (read: {o['read']}): {o['lines']} lines, {o['anchors_lost']} anchors lost; "
              f"gained {', '.join(o['gained'][:8])}; lost {', '.join(o['lost'][:8])} → {o['action']}")
    if not a.write: print("(dry run: --write --date D writes dowse/REDOWSE-PAGES-MEASURE-D.md and .tsv)"); return
    if not a.date: sys.exit("--write needs --date")
    md, tsv = (os.path.join(G, "dowse", f"REDOWSE-PAGES-MEASURE-{a.date}{x}") for x in (".md", ".tsv"))
    for p in (md, tsv):
        if os.path.exists(p): sys.exit(f"{os.path.relpath(p, ROOT)} exists: not overwritten (use a new date)")
    with open(tsv, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["notice", "source", "item", "PDF page", "lines", "anchors lost", "persons gained", "persons lost", "action"])
        for o in out:
            w.writerow([o["notice"], o["source"], o["item"], o["page"], o["lines"], o["anchors_lost"], ", ".join(o["gained"]), ", ".join(o["lost"]), o["action"]])
    L = [f"# The selective redowse: the measure (R1–R2), {a.date}", "",
         f"*Generated by `tools/redowse-pages.py measure --write --date {a.date}` from `ocr/RECUPEL-NOTICES.tsv` (the notices whose "
         f"«Ezri's status» is empty or «pending»), the superseded copies and the current preferred texts, the facts files, and the roster "
         f"`{os.path.relpath(rpath, G)}`. Protocol: `ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md`. The persons are the roster's search "
         f"keys found as words on the page (four letters or more, no OCR tolerance), standing in for the name search by page, not built.*", "",
         "## R1, the triage", ""]
    for k, v in Counter(t[3].split(":")[0] for t in triage).most_common(): L.append(f"- **{k}**: {v}")
    L += ["", "| notice | item | source | status |", "|---|---|---|---|"]
    L += [f"| {n} | {i} | {s} | {st} |" for n, i, s, st in triage]
    L += ["", "## R2, page by page", ""]
    for src in sorted({o["source"] for o in out}):
        oo = [o for o in out if o["source"] == src]
        L += [f"### {src}", "", ", ".join(f"{by[(src, k)]} {k}" for k in ACTS if by[(src, k)]), "",
              "| notice | item | PDF | lines | anchors lost | gained | lost | action |", "|---|---|---|---|---|---|---|---|"]
        for o in oo:
            L.append(f"| {o['notice']} | {o['item']} | {o['page']} | {o['lines']} | {o['anchors_lost']} | {', '.join(o['gained'])} | {', '.join(o['lost'])} | {o['action']} |")
        lost = [(o, l) for o in oo for l in o["lost_lines"]]
        if lost:
            L += ["", "The lines whose anchor the new page does not hold:", ""]
            L += [f"- {o['item']}, PDF {o['page']}: {l[2:]}" for o, l in lost]
        L.append("")
    open(md, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(md, ROOT)} and {os.path.relpath(tsv, ROOT)}")

if __name__ == "__main__":
    main()
