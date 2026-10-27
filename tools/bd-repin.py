#!/usr/bin/env python3
"""The re-pin of a hand facts file onto its born-digital texts once they are fixed and signed (the light pathway: the
dowse runbook, D0 point 3, and D8; Miles, 2026-10-26 01:0x, the Beauchemin texts signed; the editor).

    tools/bd-repin.py <facts file> --report <out.md> [--apply]

For each fact line (format 4's line form: … · fact · anchor · locator · [themes] · confidence), each locator part
«‹item›, ¶ N», «‹item›, l. N[–M]» or «‹item›, PDF N[ (prese M)][, …]», a part without its item («¶ 7» after «; »)
taking the item before it:
- an UNPAGED text (sources/born-digital-text/‹item›.txt, no «=== page N ===»): its paragraphs as the harvest counts
  them (blocks between blank lines, headings included). The anchor's segments (split at «…» and «⟨fino⟩»; folded:
  letters and digits only, case and accents off) are sought in them; the paragraph holding them all becomes «¶ N»; where
  they fall in several paragraphs, each paragraph is cited, in order, with the item repeated («‹item›, ¶ 3; ‹item›,
  ¶ 7»); «l. N–M» becomes «¶ N» the same way. Not found: the line is listed, its locator left.
- a PAGED text (a transcription or a typed PDF, «=== page N ===»; or a corpus item's preferred text): the anchor is
  checked on its page, nothing changed; not found: listed.
- an item that is neither: listed («no text»).
--report writes the lines changed, the ambiguous and the not found, create-only. --apply rewrites the facts file's
locators in place (a hand file under git: the commit before is its undo) and nothing else; without it nothing but the
report is written. Ezri, 2026-10-26."""
import argparse, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
PART = re.compile(r"^(?:(?P<item>[^,·;]+?), )?(?P<kind>¶|l\.|PDF) ?(?P<n>\d+)(?:[–-]\d+)?(?P<rest>.*)$")
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)

def fold(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))

def segments(anchor):
    return [fold(x) for x in re.split(r"…|\.\.\.|⟨fino⟩", anchor) if len(fold(x)) >= 4]

_texts = {}
def text(item):
    """-> ("paras", [folded paragraph]) | ("pages", {N: folded page}) | (None, None)."""
    if item not in _texts:
        b = os.path.join(G, "sources", "born-digital-text", item + ".txt")
        p = os.path.join(G, "sources", "ocr-preferred", item + ".txt")
        f = b if os.path.exists(b) else p if os.path.exists(p) else None
        if not f: _texts[item] = (None, None)
        else:
            t = open(f, encoding="utf-8").read()
            hs = list(PAGE.finditer(t))
            if hs: _texts[item] = ("pages", {int(m.group(1)): fold(t[m.end():(hs[i + 1].start() if i + 1 < len(hs) else len(t))]) for i, m in enumerate(hs)})
            else: _texts[item] = ("paras", [fold(x) for x in t.split("\n\n") if x.strip()])
    return _texts[item]

def line_of(item, para, seg):
    """The text file's line (from 1) in paragraph ¶ para where the folded segment begins, else the paragraph's first."""
    t = open(os.path.join(G, "sources", "born-digital-text", item + ".txt"), encoding="utf-8").read().split("\n")
    n, start, prev_blank = 0, None, True
    for i, l in enumerate(t, 1):
        if l.strip() and prev_blank: n += 1
        prev_blank = not l.strip()
        if n == para and l.strip():
            start = start or i
            if seg[:16] and seg[:16] in fold(l): return i
        elif n > para: break
    return start or 1

def suggest(item, anchor, k2n):
    """For an anchor not found: the paragraph or page of the raw text that shares most of its words of four letters or
    more, and the passage there from the first shared word on (about 260 characters), for the anchor to be set by hand."""
    name = k2n.get(item, item)
    b = os.path.join(G, "sources", "born-digital-text", name + ".txt")
    p = os.path.join(G, "sources", "ocr-preferred", name + ".txt")
    f = b if os.path.exists(b) else p
    t = open(f, encoding="utf-8").read()
    hs = list(PAGE.finditer(t))
    blocks = ([(f"PDF {m.group(1)}", t[m.end():(hs[i + 1].start() if i + 1 < len(hs) else len(t))]) for i, m in enumerate(hs)] if hs
              else [(f"¶ {i + 1}", x) for i, x in enumerate(y for y in t.split("\n\n") if y.strip())])
    want = [w for w in re.findall(r"\w{4,}", anchor.lower())]
    best = max(blocks, key=lambda x: sum(1 for w in set(want) if w in x[1].lower()), default=None)
    if not best: return "(no text)"
    low = best[1].lower(); at = min((low.find(w) for w in want if w in low), default=0)
    return f"{best[0]}: «{' '.join(best[1][max(0, at - 40):at + 260].split())}»"

def keys():
    """item key -> file name, from OCR-ITEM-TABLE.tsv (a locator names the item by its key)."""
    import csv
    r = csv.reader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t")
    h = next(r); k = h.index("key")
    return {row[k]: row[0] for row in r if len(row) > k and row[k]}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("facts"); ap.add_argument("--report", required=True); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--suggest", action="store_true", help="give each anchor not found the nearest passage of its text")
    ap.add_argument("--anchors", help="a TSV: old anchor, new anchor (copied from the fixed text), [the item to cite first]")
    a = ap.parse_args()
    if os.path.exists(a.report): sys.exit(f"{a.report} exists: not overwritten")
    k2n = keys()
    # --anchors: old anchor TAB new anchor [TAB the item to cite first], each new anchor copied from the fixed text by
    # hand (2026-10-26: 45 Beauchemin anchors quoted from BAnQ's text layer, or across a page's table cells); a row
    # matching no line is reported
    swaps = {}
    for r in (open(a.anchors, encoding="utf-8").read().split("\n") if a.anchors else []):
        if r.strip() and not r.startswith("#"):
            c = r.split("\t"); swaps[c[0]] = (c[1], c[2].strip() if len(c) > 2 else "")
    used = set()
    L = open(a.facts, encoding="utf-8").read().split("\n")
    out, rep = [], {"changed": [], "several paragraphs": [], "not found": [], "checked on its page": 0, "no text": [], "unread": []}
    for l in L:
        if not l.startswith("- $$$"): out.append(l); continue
        f = l.split(" · ")
        # the locator: the first field from the fourth on whose every «;» part reads as a locator, the first naming an item
        idx = next((i for i in range(3, len(f)) if all(PART.match(p.strip()) for p in f[i].split(";"))
                    and (PART.match(f[i].split(";")[0].strip()).group("item") or "")), None)
        if idx is None: rep["unread"].append(l); out.append(l); continue
        if f[idx - 1] in swaps:
            used.add(f[idx - 1]); f[idx - 1], first = swaps[f[idx - 1]]
            if first:   # the item to cite first: its part moved to the front (the anchor is sought in the first locator)
                ps = [p.strip() for p in f[idx].split(";")]
                f[idx] = "; ".join(sorted(ps, key=lambda p: not p.startswith(first + ",")))
        anchor, segs = f[idx - 1], segments(f[idx - 1])
        short = len(anchor.split()) < 6
        new, item, ok = [], None, True
        for p in f[idx].split(";"):
            m = PART.match(p.strip()); item = (m.group("item") or item).strip()
            name = k2n.get(item, item)
            kind, (form, t) = m.group("kind"), text(name)
            if form is None: rep["no text"].append(l); new.append(p.strip()); ok = False; continue
            if form == "pages":
                pg = t.get(int(m.group("n")), "") if kind == "PDF" else ""
                if kind == "PDF" and segs and all(s in pg for s in segs): rep["checked on its page"] += 1
                else: rep["not found"].append(l); ok = False
                new.append(f"{item}, {kind} {m.group('n')}{m.group('rest')}")
                continue
            hits = [i + 1 for i, x in enumerate(t) if segs and all(s in x for s in segs)]
            if hits: paras = [hits[0]] if len(hits) == 1 or int(m.group("n")) not in hits else [int(m.group("n"))]
            else:   # the segments in several paragraphs, each in the first that holds it, in order
                each = [next((i + 1 for i, x in enumerate(t) if s in x), None) for s in segs]
                paras = sorted(set(each)) if segs and None not in each else []
                if paras: rep["several paragraphs"].append(l)
            if not paras:
                # a copy (a part after the first; the harvest checks the anchor in the first only) may give the passage
                # in other words, BAnQ's garbled layer beside a transcription: kept as written
                if new: new.append(p.strip()); continue
                rep["not found"].append(l); new.append(p.strip()); ok = False; continue
            for q in paras:
                # a short anchor (a table cell) passes the check on its cited line (harvest-facts.py, «cited»)
                loc = f"{item}, ¶ {q}" + (f", l. {line_of(name, q, segs[0])}" if short and segs else "")
                if loc not in new: new.append(loc)
        # the parts as rewritten; a part already naming its item and unchanged is kept as written
        nl = " · ".join(f[:idx] + ["; ".join(new)] + f[idx + 1:])
        if nl != l: rep["changed"].append((l, nl))
        out.append(nl)
    R = [f"# The re-pin of {os.path.relpath(a.facts, G)} onto its fixed texts ({'applied' if a.apply else 'proposed'})", "",
         f"*Generated by `tools/bd-repin.py`. {len(rep['changed'])} locators changed; {rep['checked on its page']} paged locators "
         f"checked on their page; {len(rep['several paragraphs'])} lines whose anchor spans paragraphs; {len(rep['not found'])} "
         f"lines whose anchor the fixed text does not hold (left as they were); {len(rep['no text'])} with no text; "
         f"{len(rep['unread'])} unread.*", ""]
    def sug(x):
        g = x.split(" · "); i = next((j for j in range(3, len(g)) if PART.match(g[j].split(";")[0].strip()) and PART.match(g[j].split(";")[0].strip()).group("item")), None)
        return suggest(PART.match(g[i].split(";")[0].strip()).group("item").strip(), g[i - 1], k2n) if i else ""
    R += ["## Not found (the anchor to be set from the fixed text by hand)", ""] + [f"- {x}\n  - nearest: {sug(x)}" if a.suggest else f"- {x}" for x in rep["not found"]] + [""]
    R += ["## No text", ""] + [f"- {x}" for x in rep["no text"]] + [""]
    R += ["## Unread", ""] + [f"- {x}" for x in rep["unread"]] + [""]
    R += ["## Changed", ""] + [f"- was: {o[2:]}\n  - now: {n[2:]}" for o, n in rep["changed"]] + [""]
    unused = [k for k in swaps if k not in used]
    if unused: R += ["## Anchor rows that matched no line", ""] + [f"- {k}" for k in unused] + [""]
    open(a.report, "x", encoding="utf-8").write("\n".join(R) + "\n")
    if unused: print(f"{len(unused)} anchor rows matched no line")
    print(R[2])
    if a.apply:
        open(a.facts, "w", encoding="utf-8").write("\n".join(out))
        print(f"applied to {os.path.relpath(a.facts, ROOT)}")

if __name__ == "__main__":
    main()
