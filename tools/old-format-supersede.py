#!/usr/bin/env python3
"""old-format-supersede.py — the old-format fact lines that a format-4 dowse has read again, taken out of the harvest's
scope by a register, never by editing the old files (the editor, 2026-10-30 16:4x, on the format 2 and 3 dowses of
September: not kept and ported, but left out of scope; Ezri's
reply, drop by page and not by title, keep what no format-4 dowse read, one recall check first: agreed 16:5x).

An old line is one of a file in `profiles/by-source/` that is neither a `-dowse.md` file nor marked format 4. Its source
field is read for the items and pages it cites:
  - a locator in the ruled form (`<item>, PDF N`, `<item>, ¶ N`);
  - a text file's name (`RuslandaEsperantisto1905.3-4.txt l.1820`, `…zakrzewski-historio-1913.txt:5945`), its
    September name resolved to today's item through OCR-ITEM-TABLE.tsv, by the name itself, its key, or the name folded
    (lower case, letters and digits only, no leading zeros: «AmerikaEsperantisto.1907.v2n3» is
    «AmerikaEsperantisto_1907_v02_n03_mar»); the line number gives the page through the «=== page N ===» marks of the
    text it was read from (`sources/ocr/<name>.txt`), a «PDF N» written beside it gives it directly, else the line has
    no page;
  - «same file l.N»: the item of the line before it in the same file;
  - an Adresaro row («Adresaro Serio XVII …, no. 3790»): the zamenhof-adresaro dowse's items of that series;
  - where none of these gives a page, the places written in the line itself (tag 2026-10-31j): a roster run's «at
    mondo1927 p89», a roll's «oge.1 p322», «at <text> l.N», «…/<item>/page-0137.txt».
A dowse counts when its `profiles/by-source/<dowse>-dowse.md` exists (so a source still being read, as UEA's w2,
supersedes nothing yet). It covers an item its `brief-config*.json` texts name, or its dowse file cites; a page, when a
reader's range for that item holds it (all of the item where the line has no page, or the readers give no ranges).

Each cited item and page, then:
  - superseded: covered, and a format-4 line for the same person (the harvest's canon) cites that item and page (any
    page of the item where the line has none): the twin;
  - kept, no twin: covered, but no format-4 line for the person there (the recall check: the lost-lines path; kept in
    scope, listed for review);
  - kept, not read again: no assembled dowse covers it, or the item is not resolved.
A line is superseded only when every item it cites is.

Usage:
  old-format-supersede.py                 the counts, nothing written
  old-format-supersede.py --write --tag T profiles/SUPERSEDED-LINES-T.tsv (read by harvest-facts.py, the newest tag)
                                          and profiles/build/SUPERSEDED-LINES-T.md; refuses if either exists
To undo: move the register out of profiles/; the harvest then reads every old line again.
"""
import os, re, sys, csv, json, glob, collections, importlib.util

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
_sp = importlib.util.spec_from_file_location("harvest_facts", os.path.join(TOOLS, "harvest-facts.py"))
H = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(H)
GEN, SRC = H.GEN, H.SRC

F4 = re.compile(r"^\W*facts-(?:format|kinds):\s*4\b")
PAGE = re.compile(r"^=== page (\d+) ===\s*$")
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}
# September names that folding does not reach (the agreed plan, 2026-10-30: the Zakrzewski files sorted to their
# format-4 dowses by tool)
SEPTEMBER = {"zakrzewski-historio-1913": "Zakrzewski - Historio de Esperanto, 1913"}

def fold(s):
    return re.sub(r"(?<!\d)0+(?=\d)", "", re.sub(r"[^a-z0-9]", "", s.lower()))

def roman(r):
    n = 0
    for a, b in zip(r, r[1:] + " "): n += -ROMAN[a] if ROMAN.get(b, 0) > ROMAN[a] else ROMAN[a]
    return n

class Items:
    """Today's items, and the September names resolved to them."""
    def __init__(self):
        rows = list(csv.DictReader((l for l in open(os.path.join(GEN, "OCR-ITEM-TABLE.tsv"), encoding="utf-8")
                                    if not l.startswith("#")), delimiter="\t"))
        self.names = {r["item"] for r in rows}
        self.keys = {r["key"].strip(): r["item"] for r in rows if (r.get("key") or "").strip()}
        self.folded = collections.defaultdict(set)
        for n in self.names: self.folded[fold(n)].add(n)
        self.fk = sorted(self.folded)
        self.cache = {}
    def resolve(self, name):
        if name in self.cache: return self.cache[name]
        out = None
        if name in self.names: out = name
        elif name in self.keys: out = self.keys[name]
        elif name in SEPTEMBER: out = SEPTEMBER[name]
        else:
            f = fold(name)
            if len(f) >= 6:
                c = self.folded.get(f, set())
                if not c:   # the September name a prefix of today's, ending where a letter follows («…v2n3» of «…v2n3mar»)
                    c = {n for k in self.fk if k.startswith(f) and not k[len(f):len(f) + 1].isdigit() for n in self.folded[k]}
                if len(c) == 1: out = next(iter(c))
        self.cache[name] = out
        return out

_marks = {}
def page_of(name, line, given_path=None):
    """The PDF page of line `line` in the text `name` was read from: its «=== page N ===» marks."""
    cands = [os.path.join(GEN, "sources", "ocr", name + ".txt")]
    if given_path: cands.insert(0, os.path.join(GEN, given_path))
    for p in cands:
        if not os.path.isfile(p): continue
        if p not in _marks:
            _marks[p] = [(i, int(m.group(1))) for i, l in enumerate(open(p, encoding="utf-8", errors="replace"), 1)
                         for m in [PAGE.match(l)] if m]
        pg = None
        for i, n in _marks[p]:
            if i > line: break
            pg = n
        return pg
    return None

TXT = re.compile(r"\.txt\b")
AFTER_LINE = re.compile(r"^`?\)?\s*(?::\s*|,?\s*(?:ll?\.|L|lines?)\s*)(\d+)")
AFTER_PDF = re.compile(r"^[^;·]{0,40}?\bPDF\s*(\d+)")
SERIO = re.compile(r"Adresaro Serio ([IVXL]+)\b")

def cited(src, items, last, adresaro):
    """[(item or None, page or None, the name as written)] for a source field; `last` is the previous line's
    (item, name, path) in the file, for «same file»."""
    out = []
    ms = H.locators(src)
    if ms:
        for m in ms:
            it = m.group("item").strip(); it = items.keys.get(it, it)
            out.append((it if it in items.names else items.resolve(it), int(m.group("pdf")) if m.group("pdf") else None, it))
        return out
    for t in TXT.finditer(src):
        pre = src[:t.start()]
        cut = max(pre.rfind(c) for c in "`(;«/")
        cand = pre[cut + 1:].strip().lstrip("…").strip()
        path = None
        mp = re.search(r"((?:sources|ocr)/[^`\s;()]*)$", pre)
        if mp: path = mp.group(1) + ".txt"
        words, it, nm = cand.split(), None, cand.split()[-1] if cand.split() else ""
        for k in range(min(6, len(words)), 0, -1):
            nm = " ".join(words[-k:])
            it = items.resolve(nm)
            if it: break
        # the OGE rolls, «sources/oge-rolls/3-0332-nomaro-….txt»: volume 3 (item oge.3), from PDF page 332 on, so no page
        # (2026-10-31: SCHOUKA's Lingva Komitato lines)
        orl = re.search(r"oge-rolls/(\d)-\d{4}-[\w-]*$", pre)
        if not it and orl:
            out.append((items.resolve(f"oge.{orl.group(1)}"), None, nm)); continue
        mr = re.fullmatch(r"(.*?)(\d+)[–-](\d+)", words[-1] if words else "")
        if not it and mr and int(mr.group(2)) < int(mr.group(3)) <= int(mr.group(2)) + 40:
            # a roster run over a range of texts («over sources/ocr/progreso1–7.txt»): the items of the range, no page
            rng = tuple(i for i in (items.resolve(f"{mr.group(1)}{k}") for k in range(int(mr.group(2)), int(mr.group(3)) + 1)) if i)
            if rng: out.append((rng, None, words[-1])); continue
        rest = src[t.end():]
        ml, mpdf, pg = AFTER_LINE.match(rest), AFTER_PDF.match(rest), None
        if mpdf: pg = int(mpdf.group(1))
        elif ml: pg = page_of(nm, int(ml.group(1)), path)
        out.append((it, pg, nm))
    if not out and re.search(r"\bsame file\b", src) and last:
        ml = re.search(r"(?:ll?\.|L)\s*(\d+)", src)
        it, nm, path = last
        out.append((it, page_of(nm, int(ml.group(1)), path) if ml else None, nm))
    if not out:
        ms = SERIO.search(src)
        if ms:
            n = roman(ms.group(1))
            its = sorted(i for i in adresaro if re.search(rf"-serio-0*{n}(?:\D|$)", items_key(items, i)))
            out.append((tuple(its) or None, None, "Adresaro Serio " + ms.group(1)))
    if all(o[0] is None for o in out):
        # a key or a text's name with neither «.txt» nor a locator's form («oge.2 p55–59», «belgaSonorilo.1912»,
        # «LaEsperoSvenska.1914.6»; 2026-10-31, the editor: 1,391 lines of tag h cited a held item so, SCHOUKA's
        # profile among them): the item, no page (its «p» is not known to be the PDF's)
        for t in re.findall(r"[A-Za-z][\w-]*(?:\.\w+)+", src):
            t = t.rstrip(".")
            it = next((i for c in (t, t.replace(".", "-")) for i in [items.resolve(c)] if i), None)
            if it and all(o[0] != it for o in out): out.append((it, None, t))
        found = [o for o in out if o[0] is not None]
        if found: out = found
    return out

# THE PLACES WRITTEN IN THE LINE ITSELF, where its source field gives none (2026-10-31, before the port of the 864: 735
# of them had no page): a roster run's «FIRST … at mondo1927 p89 (N° 11) — «…»; LAST: … at mondo1932 p22» (the PDF page:
# 524 of 598 such quotations stand on it in today's text), a roll's «oge.1 p322» beside its file, a September text's
# «at AmerikaEsperantisto.1910.v8n4 l.3996», a page file's «…/belgaSonorilo.1910/page-0137.txt»
AT_P = re.compile(r"\b([A-Za-z][\w.-]*\d[\w.-]*?)(?:\.txt)?\s+p\.?\s?(\d+)\b")
AT_L = re.compile(r"\bat ([A-Za-z][\w.-]*\d[\w.-]*?) l\.\s?(\d+)\b")
AT_F = re.compile(r"/([A-Za-z][\w.-]+)/page-0*(\d+)\.txt\b")
def inline_cites(t, items):
    out = []
    for m in AT_P.finditer(t):
        it = items.resolve(m.group(1).rstrip("."))
        if it: out.append((it, int(m.group(2)), m.group(1)))
    for m in AT_L.finditer(t):
        it = items.resolve(m.group(1))
        if it: out.append((it, page_of(m.group(1), int(m.group(2))), m.group(1)))
    for m in AT_F.finditer(t):
        it = items.resolve(m.group(1))
        if it: out.append((it, int(m.group(2)), m.group(1)))
    return [o for k, o in enumerate(out) if o[1] is not None and o[:2] not in [x[:2] for x in out[:k]]]

def items_key(items, item):
    return next((k for k, n in items.keys.items() if n == item), item)

# --loose (2026-10-31; the editor, before the port's full run: more ways to match facts, since
# the problem will recur): what the lines kept without a twin would match by looser tests, counted, nothing written
LOOSE = None
F4S, F4K, F4T = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(list)
NAMES = re.compile(r"\b[A-ZÀ-ŽĈĜĤĴŜŬ][A-ZÀ-ŽĈĜĤĴŜŬ'’-]{2,}(?:[ -][A-ZÀ-ŽĈĜĤĴŜŬ][A-ZÀ-ŽĈĜĤĴŜŬ'’-]{2,})*")
def surname(who): return re.sub(r"\s*\(.*$", "", who).strip()

_ported = None
def ported():
    """{(by-source file, the line's text): ported / dropped} from every dowse/old-format-port/port-done-*.tsv."""
    global _ported
    if _ported is None:
        _ported = {}
        for p in sorted(glob.glob(os.path.join(GEN, "dowse", "old-format-port", "port-done-*.tsv"))):
            for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
                if r["status"] in ("ported", "dropped"): _ported[(r["file"], r["text"])] = r["status"]
    return _ported

def readers_ranges(v, default_item):
    """(item, lo, hi) of a readers string: «1: `RuslandaEsperantisto1905.2` PDF 1–7 · 2: …» or «1: PDF 1–15 (…)»."""
    out = []
    for part in re.split(r" · ", v):
        m = re.search(r"(?:`([^`]+)`\s*)?PDF\s*(\d+)\s*[–-]\s*(\d+)", part)
        if m: out.append((m.group(1) or default_item, int(m.group(2)), int(m.group(3))))
    return out

def main():
    global LOOSE
    if "--loose" in sys.argv: LOOSE = collections.Counter()
    write = "--write" in sys.argv
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    if write and not tag: sys.exit("--write needs --tag T")
    items = Items()
    reg = os.path.join(GEN, "profiles", f"SUPERSEDED-LINES-{tag}.tsv") if tag else None
    rep = os.path.join(GEN, "profiles", "build", f"SUPERSEDED-LINES-{tag}.md") if tag else None
    if write:
        for p in (reg, rep):
            if os.path.exists(p): sys.exit(f"refused, nothing written: {os.path.relpath(p, GEN)} exists")

    # the format-4 lines: (person, item) -> pages (None for a ¶ locator), and the dowse files' items
    f4, f4loc, dowse_items, old_files = collections.defaultdict(set), {}, collections.defaultdict(set), []
    for f in sorted(glob.glob(os.path.join(SRC, "*.md"))):
        content = open(f, encoding="utf-8", errors="replace").read().split("\n")
        base = os.path.basename(f)
        is4 = base.endswith("-dowse.md") or any(F4.match(l) for l in content[:15])
        if not is4: old_files.append((base, content)); continue
        fmt3 = any(H.FORMAT3.match(l) for l in content[:15])
        for line in content:
            if not line.startswith("- $$$"): continue
            line, _k = H.take_kind(line)
            if fmt3: line = H.to2(line)
            rec, err = H.parse(line)
            if err: continue
            who = H.canon(rec[0])
            named = set(NAMES.findall(_k or ""))
            for m in H.locators(rec[3]) or []:
                it = m.group("item").strip(); it = items.keys.get(it, it)
                pg = int(m.group("pdf")) if m.group("pdf") else None
                f4[(who, it)].add(pg); f4loc.setdefault((who, it, pg), f"{base}: {rec[3][:80]}")
                # for --loose: the surname without its qualifier, the persons the kind names, the fact's words
                F4S[(surname(who), it)].add(pg)
                for x in named: F4K[(x, it)].add(pg)
                F4T[(it, pg)].append(rec[2])
                if base.endswith("-dowse.md"): dowse_items[base[:-len("-dowse.md")]].add(it)

    # what each assembled dowse covers: item -> [(dowse, ranges or None)]
    cover = collections.defaultdict(list)
    for d in sorted(dowse_items):
        texts, ranges = set(), collections.defaultdict(list)
        for cp in sorted(glob.glob(os.path.join(GEN, "dowse", d, "brief-config*.json"))):
            c = json.load(open(cp, encoding="utf-8"))
            ti = [os.path.basename(t)[:-4] for t in c.get("texts", []) if t.endswith(".txt")]
            ti = [items.keys.get(t, t) if t not in items.names else t for t in ti]
            texts |= set(ti)
            dflt = c.get("item") or (ti[0] if len(ti) == 1 else None)
            for k, v in c.items():
                if "readers" in k and isinstance(v, str):
                    for it, lo, hi in readers_ranges(v, dflt):
                        ranges[items.keys.get(it, it)].append((lo, hi))
        for it in texts | dowse_items[d]:
            cover[it].append((d, ranges.get(it) or None))
    adresaro = dowse_items.get("zamenhof-adresaro", set())

    rows, per_file, unresolved, uncovered = [], collections.Counter(), collections.Counter(), collections.Counter()
    tally = collections.Counter()
    for base, content in old_files:
        fmt3 = any(H.FORMAT3.match(l) for l in content[:15])
        last = None
        for n, raw in enumerate(content, 1):
            if not raw.startswith("- $$$"): continue
            rec, err = H.parse(H.to2(raw) if fmt3 else raw)
            if err: tally["unparsed"] += 1; continue
            who = H.canon(rec[0])
            cs = cited(rec[3], items, last, adresaro)
            if all(pg is None for _i, pg, _n in cs):
                cs = inline_cites(rec[2] + " · " + rec[3], items) or cs
            for it, pg, nm in cs:
                if isinstance(it, str):
                    mp = re.search(r"((?:sources|ocr)/[^`\s;()]*" + re.escape(nm) + r"\.txt)", rec[3])
                    last = (it, nm, mp.group(1) if mp else None)
            verdicts = []
            for it, pg, nm in cs:
                its = it if isinstance(it, tuple) else (it,) if it else ()
                if not its: unresolved[nm[:60]] += 1; verdicts.append(("kept, not read again", None, None, "")); continue
                hit = None
                for i in its:
                    for d, rg in cover.get(i, []):
                        if pg is None or rg is None or any(lo <= pg <= hi for lo, hi in rg): hit = (i, d); break
                    if hit: break
                if not hit:
                    uncovered[its[0][:60]] += 1; verdicts.append(("kept, not read again", its[0], None, "")); continue
                twin = None
                for i in its:
                    pages = f4.get((who, i), set())
                    if pages and (pg is None or pg in pages):
                        twin = f4loc.get((who, i, pg)) or f4loc.get((who, i, sorted(pages, key=lambda x: (x is None, x or 0))[0]))
                        break
                # THE TWO LOOSER TWINS (2026-10-31; the editor, of «page ±1» and «named in a kind»: the two
                # recommended, folded in at once): the same person on the page either side (a fact over a page's turn, a
                # September page counted otherwise); or a format-4 line on that page whose kind names the person, which
                # the harvest copies to him (copies for every person a kind names), so his profile has it
                if not twin and pg is not None:
                    for i in its:
                        near = sorted(p for p in f4.get((who, i), set()) if p is not None and abs(p - pg) == 1)
                        if near: twin = f"page ±1: {f4loc.get((who, i, near[0]))}"; break
                # (a person with a qualifier only by his own name: «ZAMENHOF (SOFIA)» is not the kind's «ZAMENHOF», who is
                # Ludwik; tag e's check lost her profile and Belmont's so)
                if not twin and surname(who) == who:
                    sur = surname(who)
                    for i in its:
                        kp = F4K.get((sur, i), set())
                        if kp and (pg is None or pg in kp): twin = f"named in a kind, {i}" + (f", PDF {pg}" if pg else ""); break
                if not twin and LOOSE is not None:
                    LOOSE["lines"] += 1
                    sur = surname(who)
                    def near(pages): return bool(pages) and (pg is None or any(p is not None and abs(p - pg) <= 1 for p in pages) or pg in pages)
                    ways = {
                        "page ±1": any(near(f4.get((who, i), set())) for i in its),
                        "surname, no qualifier": any((pg is None and F4S.get((sur, i))) or pg in F4S.get((sur, i), set()) for i in its),
                        "named in a kind": any((pg is None and F4K.get((sur, i))) or pg in F4K.get((sur, i), set()) for i in its),
                        "named in a fact": pg is not None and any(re.search(r"\b" + re.escape(sur.title()) + r"\b", t, re.I)
                                                                 for i in its for t in F4T.get((i, pg), [])),
                    }
                    for k, v in ways.items(): LOOSE[k] += v
                    LOOSE["any of the first three"] += any(list(ways.values())[:3])
                    LOOSE["any"] += any(ways.values())
                verdicts.append(("superseded" if twin else "kept, no twin", hit[0], hit[1], twin or ""))
            if not verdicts: verdicts = [("kept, not read again", None, None, "")]; unresolved["(no item cited)"] += 1
            status = "superseded" if all(v[0] == "superseded" for v in verdicts) else \
                     "kept, no twin" if any(v[0] == "kept, no twin" for v in verdicts) and all(v[0] != "kept, not read again" for v in verdicts) \
                     else "kept, not read again"
            # A LINE NO FORMAT-4 DOWSE HAS READ AGAIN is out of scope (the editor, 2026-10-31 11:3x:
            # only the 4,711 lines without a twin are in scope, to be brought to format 4)
            if status == "kept, not read again": status = "out of scope"
            # brought to format 4 by tools/old-format-port.py (its port-done-<tag>.tsv): ported, its new line in
            # profiles/by-source/old-format-port-<tag>.md, or dropped by the legilo with its reason
            pd = ported().get((base, raw.strip()))
            if status == "kept, no twin" and pd in ("ported", "dropped"): status = "ported" if pd == "ported" else "dropped by the port"
            tally[status] += 1; per_file[(base, status)] += 1
            # every line has its row (since tag 2026-10-31b: the lines kept are to be brought to format 4, the editor
            # 2026-10-31 11:1x: the editor's ruling, the lines brought to format 4, and so for
            # any old dowse left)
            seen = {"out of scope": "kept, not read again", "ported": "kept, no twin", "dropped by the port": "kept, no twin"}.get(status, status)
            v = next(v for v in verdicts if v[0] == seen) if status != "superseded" else verdicts[0]
            pg = next((p for (i, p, _n) in cs if i == v[1]), None)
            if v[1] is None:   # not read again: the first item the line cites, as resolved
                first = next((i for (i, _p, _n) in cs if i), None)
                v = (v[0], first[0] if isinstance(first, tuple) else first, None, "")
                pg = next((p for (i, p, _n) in cs if i), None)
            rows.append([base, str(n), who, v[1] or "", "" if pg is None else str(pg), v[2] or "", status, v[3], raw.strip()])

    total = sum(tally.values())
    print(f"{len(old_files)} old-format files, {total} lines: " + ", ".join(f"{k} {v}" for k, v in tally.most_common()))
    print(f"  {len(cover)} items covered by {len(dowse_items)} assembled dowses")
    print("  unresolved names, the commonest: " + "; ".join(f"{k} ({v})" for k, v in unresolved.most_common(12)))
    print("  resolved but not read again, the commonest: " + "; ".join(f"{k} ({v})" for k, v in uncovered.most_common(12)))
    if LOOSE is not None: print("  --loose, of the cited items kept without a twin: " + ", ".join(f"{k} {v}" for k, v in LOOSE.items()))
    if not write: return 0

    with open(reg, "x", encoding="utf-8", newline="") as fh:
        fh.write(f"# the old-format lines a format-4 dowse has read again (tools/old-format-supersede.py --tag {tag}); "
                 "harvest-facts.py leaves out the rows whose status is «superseded» or «out of scope» (read again by no "
                 "format-4 dowse); the «kept, no twin» rows stay in scope, to be brought to format 4. Key: file and the line's text.\n")
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["file", "line", "person", "item", "page", "dowse", "status", "twin", "text"])
        w.writerows(rows)
    files = sorted({b for b, _s in per_file})
    with open(rep, "x", encoding="utf-8") as fh:
        fh.write(f"# The old-format lines read again, tag {tag}\n\n"
                 f"By `tools/old-format-supersede.py --write --tag {tag}`; the register is `profiles/SUPERSEDED-LINES-{tag}.tsv`.\n\n"
                 f"{len(old_files)} old-format files, {total} lines: " + ", ".join(f"{k} {v}" for k, v in tally.most_common()) + ".\n\n"
                 "## By file\n\n| file | superseded | out of scope | kept, no twin | kept, not read again |\n|---|---|---|---|---|\n")
        for b in files:
            fh.write(f"| {b} | {per_file[(b, 'superseded')]} | {per_file[(b, 'out of scope')]} | {per_file[(b, 'kept, no twin')]} | {per_file[(b, 'kept, not read again')]} |\n")
        fh.write("\n## Names not resolved to an item (the commonest 60)\n\n")
        for k, v in unresolved.most_common(60): fh.write(f"- {k}: {v}\n")
        fh.write("\n## Items resolved but read by no assembled dowse (the commonest 60)\n\n")
        for k, v in uncovered.most_common(60): fh.write(f"- {k}: {v}\n")
    print(f"  wrote {os.path.relpath(reg, GEN)} ({len(rows)} rows) and {os.path.relpath(rep, GEN)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
