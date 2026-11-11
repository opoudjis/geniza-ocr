#!/usr/bin/env python3
"""The pages to reread for the roster bug: every page where the bug left a person off the readers' roster, the name search
found that person's name exactly on the page, and the returns have no fact about them from that page (the editor,
2026-11-09 22:4x; Ezri's promise: one list, by a
mechanical rule, erring towards rereading).

    tools/roster-cut-pages.py [SOURCE …] [--date YYYY-MM-DD] [--write]

THE BUG (2026-11-09 21:3x, fixed 21:43): dowse-reader-roster.py and dowse-brief-fill.py read the hits TSVs at csv's default
quoting, a «"» in an OCR reading swallowing the rows after it; the people found only in those rows were left off the
rosters. The brief's list rule («skribu fakton el ili nur pri persono de via nomaro») then kept the readers from writing
those people's list entries (Miles, ocr/method/ROSTER-CUT-RECALL-2026-11-09.md).

THE RULE, per hits file (dowse/<source>/record-<tag>-strong.hits.tsv) with returns (the briefs built on its side files,
as tools/roster-cut-recall.py finds them): a person is CUT where csv's default reading of the file never saw them at the
«exact» tier and the plain reading did; each (item, PDF page) where a cut person has an «exact» hit is LISTED unless a
return line located on that item and page has a head holding the person's surname (the label's last part, folded to a-z,
3 letters or more). Where that is uncertain the page is listed. Each page: its words (whitespace tokens of the page in the
text the hits name, by its «=== page N ===» markers), and whether the returns have any line on it at all («read»: a page
with none may have been outside the readers' scope).

The cost: about 10 points of the week a million words (the dowse runbook's rule of thumb; never below the legiloj's floor,
LEGILO-COSTS.tsv), given per source and in all.

Without --write it prints a line a hits file. --write writes dowse/ROSTER-CUT-PAGES-<date>.md (by source, in plain words)
and .tsv (one row a page), create-only. Read-only otherwise. Ezri, 2026-11-10."""
import argparse, collections, csv, datetime, glob, importlib.util, io, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "dowse")
csv.field_size_limit(sys.maxsize)
spec = importlib.util.spec_from_file_location("rcr", os.path.join(ROOT, "tools", "roster-cut-recall.py"))
RCR = importlib.util.module_from_spec(spec); spec.loader.exec_module(RCR)
fold = RCR.fold
spec = importlib.util.spec_from_file_location("asm", os.path.join(ROOT, "tools", "dowse-facts-assemble.py"))
ASM = importlib.util.module_from_spec(spec); spec.loader.exec_module(ASM)
OUT = set()   # the scope register's «out» names, folded as dowse-reader-roster.py's out-list folds them
_reg = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
for _l in (open(_reg, encoding="utf-8") if os.path.exists(_reg) else []):
    _x = _l.rstrip("\n").split("\t"); _x += [""] * (8 - len(_x))
    if not _l.startswith("#") and _x[0] != "name" and _x[4] == "out": OUT.add(re.sub(r" \(.*\)| de$", "", _x[0]).lower())
def is_out(person):
    x = person.lower()
    return any(o == x or o in x.split("-") or o.replace(" ", "-") == x for o in OUT)
KEY = {}
for _r in csv.DictReader((x for x in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
    if _r.get("item"): KEY[_r["item"].strip()] = (_r.get("key") or "").strip()
LOC = re.compile(r"([\w.\- ]+?), PDF (\d+)")
HEAD = re.compile(r"^- \$\$\$ (.+?) \$\$\$")


def hits(path):
    """(cut persons, {person: {(item, page, text)}} of their «exact» rows) for one hits file."""
    text = "".join(l for l in open(path, encoding="utf-8", errors="replace") if not l.startswith("#"))
    buggy = {r["person"] for r in csv.DictReader(io.StringIO(text), delimiter="\t") if r.get("tier") == "exact"}
    rows = text.split("\n"); head = rows[0].split("\t")
    ix = {k: head.index(k) for k in ("person", "tier", "item", "page", "text", "as_read")}
    whole, where = set(), collections.defaultdict(set)
    for l in rows[1:]:
        f = l.split("\t")
        if len(f) <= max(ix.values()) or f[ix["tier"]] != "exact": continue
        ar = f[ix["as_read"]].strip()
        if not ar or not ar[0].isupper(): continue   # a name is written with a capital: «konis», «majo», «noto» as words are not people (2026-11-10)
        whole.add(f[ix["person"]])
        where[f[ix["person"]]].add((f[ix["item"]], f[ix["page"]], f[ix["text"]]))
    cut = whole - buggy
    return cut, {p: where[p] for p in cut}


def return_lines(src, tags):
    """{(item, page): set of folded head words} over the tags' returns (joined, or a part's pieces where none is joined)."""
    out = collections.defaultdict(set)
    for t in tags:
        fs = glob.glob(os.path.join(D, src, f"facts-return-{t}-*.md"))
        joined = {f for f in fs if re.fullmatch(rf"facts-return-{re.escape(t)}-\d+\.md", os.path.basename(f))}
        pieces = {f for f in fs if re.fullmatch(rf"facts-return-{re.escape(t)}-(\d+)-p\d+\.md", os.path.basename(f))
                  and os.path.join(D, src, f"facts-return-{t}-{re.match(r'.*-(\d+)-p', os.path.basename(f)).group(1)}.md") not in joined}
        for f in joined | pieces:
            for l in open(f, encoding="utf-8", errors="replace"):
                m = HEAD.match(l)
                if not m: continue
                l = ASM.expand_lean(os.path.join(D, src), re.sub(r"-p\d+(\.md)$", r"\1", os.path.basename(f)), l.rstrip("\n"))
                words = {fold(w) for w in re.split(r"[\s\-()]+", m.group(1)) if w}
                for lm in LOC.finditer(l):
                    out[(lm.group(1).strip(), lm.group(2))] |= words
    return out


def surname(person):
    segs = [fold(s) for s in re.split(r"[\s\-]+", person) if fold(s)]
    return segs[-1] if segs and len(segs[-1]) >= 3 else (max(segs, key=len) if segs else "")


_W = {}
def words_on(textpath, page):
    p = os.path.join(G, "sources", textpath)
    if p not in _W:
        _W[p] = {}
        if os.path.exists(p):
            cur, n = None, 0
            for l in open(p, encoding="utf-8", errors="replace"):
                m = re.match(r"=== page (\d+) ===", l)
                if m:
                    if cur is not None: _W[p][cur] = n
                    cur, n = m.group(1), 0
                else: n += len(l.split())
            if cur is not None: _W[p][cur] = n
    return _W[p].get(page)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sources", nargs="*"); ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    srcs = a.sources or sorted(d for d in os.listdir(D) if glob.glob(os.path.join(D, d, "record-*-strong.hits.tsv")))
    rows, per, unread, frequent, outs = [], [], [], [], set()
    for s in srcs:
        runs, RL = [], collections.defaultdict(set)   # every run with returns, and their returns together
        for hp in sorted(glob.glob(os.path.join(D, s, "record-*-strong.hits.tsv"))):
            htag = re.match(r"record-(.+?)-strong\.hits\.tsv$", os.path.basename(hp)).group(1)
            tags = RCR.return_tags(s, htag)
            if not tags: continue
            cut, where = hits(hp)
            if not cut: continue
            rl = return_lines(s, tags)
            if not rl:
                unread.append((s, os.path.basename(hp))); print(f"{s}\t{os.path.basename(hp)}\tno returns yet: skipped", flush=True); continue
            for k, v in rl.items(): RL[k] |= v
            runs.append((os.path.basename(hp), tags, cut, where))
        if not runs: continue
        pages, txts, runs_of, ncut = collections.defaultdict(set), {}, collections.defaultdict(set), set()
        for hb, tags, cut, where in runs:
            ncut |= cut
            for p, locs in where.items():
                if is_out(p): outs.add((s, p)); continue
                if len({(i, pg) for i, pg, _ in locs}) > 15:   # a common word, or a name too frequent to take bare (2026-11-06's rule)
                    frequent.append((s, hb, p, len({(i, pg) for i, pg, _ in locs}))); continue
                sn = surname(p)
                for item, page, txt in locs:
                    got = RL.get((item, page), set()) | RL.get((KEY.get(item, ""), page), set())
                    if sn and sn in got: continue
                    pages[(item, page)].add(p); txts.setdefault((item, page), txt); runs_of[(item, page)].add(hb)
        n_w = 0
        for (item, page), ps in sorted(pages.items()):
            txt = txts[(item, page)]
            pref = os.path.join("ocr-preferred", item + ".txt")
            w = words_on(pref, page) if os.path.exists(os.path.join(G, "sources", pref)) else words_on(txt, page)
            n_w += w or 0
            rows.append((s, ", ".join(sorted(runs_of[(item, page)])), "", item, page, txt, w if w is not None else "",
                         "yes" if ((item, page) in RL or (KEY.get(item, ""), page) in RL) else "no", len(ps), "; ".join(sorted(ps))))
        per.append((s, f"{len(runs)} runs", len(ncut), len(pages), n_w))
        print(f"{s}\t{len(runs)} runs\tcut {len(ncut)}\tpages {len(pages)}\twords {n_w}", flush=True)
    W = sum(r[4] for r in per)
    print(f"in all: {sum(r[3] for r in per)} pages, {W} words, about {W / 1e6 * 10:.1f} points")
    if not a.write: return
    base = os.path.join(D, f"ROSTER-CUT-PAGES-{a.date}")
    with open(base + ".tsv", "x", encoding="utf-8") as f:
        f.write("source\thits file\treturn tags\titem\tPDF page\ttext\twords\tany line on the page\tcut persons\tthe persons\n")
        f.write("".join("\t".join(map(str, r)) + "\n" for r in rows))
    by = collections.defaultdict(list)
    for r in per: by[r[0]].append(r)
    L = [f"# The pages to reread for the roster bug ({a.date})", "",
         "Ezri, by tools/roster-cut-pages.py, for the editor. **The rule, the same for every page:** a page is listed when the bug left "
         "a person off the readers' name list, the name search found that person's name on that page exactly, and the readers' "
         "returns have no fact about that person from that page. Where it is not certain whether a fact is about the person, the "
         "page is listed: the list errs towards rereading.", "",
         f"**In all: {sum(r[3] for r in per)} pages, {W:,} words, about {W / 1e6 * 10:.1f} points of the week** (at about 10 points a "
         "million words; a launch is never below its readers' floor).", "",
         "«Lines on the page» says whether the returns have any fact at all from that page: a page with none may have been outside "
         "the readers' scope, and may need no reread. The pages themselves, one a row with the people each is for, are in the "
         f"table beside this file, ROSTER-CUT-PAGES-{a.date}.tsv.", "",
         "| source | dowse runs | people left off | pages to reread | of them with lines | words | points |", "|---|---|---|---|---|---|---|"]
    for s, rs in sorted(by.items(), key=lambda kv: -sum(r[4] for r in kv[1])):
        np_ = sum(r[3] for r in rs); nw = sum(r[4] for r in rs)
        wl = sum(1 for r in rows if r[0] == s and r[7] == "yes")
        L.append(f"| {s} | {rs[0][1].split()[0]} | {sum(r[2] for r in rs)} | {np_} | {wl} | {nw:,} | {nw / 1e6 * 10:.2f} |")
    L += ["", "Sources with no row here had no person left off, or no returns built on the bug's rosters.", "",
          f"**Out of scope, left out** ({len(outs)} person-and-source pairs): people the scope register has «out», for whom the readers rightly write no fact.", "",
          f"**Not yet read, so not listed** ({len(unread)} dowse runs: their briefs are built but no reader has returned): "
          + ("; ".join(f"{s} ({h})" for s, h in unread) or "none") + ".", "",
          f"**Names too frequent to take bare, left out** ({len(frequent)}): a person the bug left off whose name the search "
          "found on more than 15 pages of one dowse run, mostly a roster form that is also a common word («von», «man»); as "
          "the scope's rule of 2026-11-06, such a name counts only with its forename or initial, which this list cannot see. "
          "The twenty most frequent, for judgement: " + "; ".join(f"{p} ({n} pages, {s})" for s, h, p, n in sorted(frequent, key=lambda x: -x[3])[:20]) + "."]
    with open(base + ".md", "x", encoding="utf-8") as f: f.write("\n".join(L) + "\n")
    print("wrote", base + ".md", "and .tsv")


if __name__ == "__main__":
    main()
