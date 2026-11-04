#!/usr/bin/env python3
"""THE PAGES OF ANOTHER MOVEMENT'S PRESS THAT BEAR ON OURS (Ezri, 2026-11-02; built from the Volapük journals' scope, the
editor's assent to dowsing the Volapük press by its mentions of Esperanto, then to leaving out the pages that name
Esperanto but no Esperantist; made a tool on the editor's word). A source whose items are mostly about something else (the Volapük press) is dowsed
only on its pages that mention Esperanto in a way the prosopography can use, one page either side. Two steps:

  scan SOURCE OUT.tsv
      every page of the source's items (dowse/SOURCE/scope.tsv's first column; the preferred text, else the
      rendersearch one) that names Esperanto (ESP) with no ZAMENHOF in its window (the page and one either side), with
      the person-shapes found within 500 characters of each mention (a title or an initial before a capitalised word, a
      Volapük genitive «Lott'a», «söla X», «fa Dl. X Y»; SKIP's words not counted) and the text round the mentions, for
      reading. «Dr. Esperanto», «söl Esperanto», «Esperanto's» are Zamenhof and counted as a person. Writes OUT.tsv
      (create-only): item, page, shapes, snippets.

  build SOURCE --names NAMES.tsv --scan SCAN.tsv --out OUT.tsv [--old OLD.tsv] [--rescue ITEM:PAGE …]
        [--skip-name NAME …] [--note TEXT] [--diff]
      the scope, in scope.tsv's form («item TAB pages TAB why»; `dowse-brief-fill.py`'s scope_of reads it): a page
      stays when it names one of NAMES.tsv's people (name TAB forms «|» TAB evidence TAB common: a common surname, 1,
      needs its forename, an initial or a three-letter abbreviation beside it, in either order; «von», «de» are no
      forename), or names Esperanto with ZAMENHOF in its window, or with a person-shape found by the scan, or is rescued
      by hand (--rescue, a page read and found to bear on it); each with one page either side. --skip-name leaves a
      person of NAMES.tsv out (the editor's ruling that they do not matter: Lederer and Sprague in the Volapük
      press). First it rebuilds the old rule (every Esperanto page, every named page) and compares it with OLD.tsv
      (default dowse/SOURCE/scope.tsv); --diff lists the differences and stops. Prints pages, words and the dowse's cost
      in points (10 a million words). Writes OUT.tsv (create-only); the dowser moves it to scope.tsv, keeping the old one
      under a dated name.

The patterns are the Volapük press's (German, French, Volapük, Italian, English, Swedish titles and forms); another
movement's press needs SHAPES and SKIP looked at first. Reads only, but for OUT.tsv."""
import argparse, collections, os, re, sys

G = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza")
ESP = re.compile(r"esperant|[sz]amenho[fv]|lingvo internacia|lingwe internazia|\bdr\.? esperanto|langue internationale du dr"
                 r"|weltsprache des dr", re.I)
ZAM = re.compile(r"[sz]amenho[fv]", re.I)
U, L = "A-ZÀ-ŽÄÖÜ", "a-zà-žäöüß"
SHAPES = re.compile(rf"\b(?:söl|Söl|jiöl|Jiöl|Herrn?|Hrn?|Dr|Prof|Mr|Mrs|Mme|Mlle|M|Frau|Frl|Sr|Sig|Signor|Monsieur|Pastor"
                    rf"|Pfarrer|Lehrer)\.?\s+(?:[{U}]\.\s*)*[{U}][{L}]{{2,}}"
                    rf"|\b[{U}]\.\s?(?:[{U}]\.\s?)*[{U}][{L}]{{2,}}"
                    rf"|\b[{U}][{L}]{{3,}}[’']a\b"
                    rf"|\bs[öo]l(?:a|e|i|is|as)\s+(?:[{U}]\.\s*)*[{U}][{L}]{{2,}}"
                    rf"|\b[{U}][{L}]{{2,}}\s+(?:[{U}]\.\s?){{1,3}}(?=[\s,;:)“”\"]|$)"
                    rf"|\b[Ff]a\s+(?:d[il]\.\s+)?[{U}][{L}]{{2,}}\s+[{U}][{L}]{{2,}}")
# words a shape catches that are no person: the language names, places, and Volapük words in capitals
SKIP = re.compile(r"schleyer|volap|esperant|pasiling|spelin|lingvo|zentral|anglo|peterburg|französisch|lovepol|epenob|ruhr\b"
                  r"|agata|praktisch|plofeda|löpatidela|cifa\b|tidüps|darmstadt|blankenberghe|bordeaux|zuid", re.I)
# Esperanto named as a man is Zamenhof («Dr. Esperanto», «söl Esperanto», «Esperanto's preface», «de Esperanto»)
PSEUD = re.compile(r"(?:\bdr|\bs[öo]l|\bsig|\bherr|\bmr|\bdi)\.?\s+„?esperant|esperanto[’']s\b|\bd[e’']\s?„?esperanto\b", re.I)


def scope_rows(path):
    """scope.tsv's rows: item → set of pages (empty for «none»)."""
    rows = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        it, pages = l.rstrip("\n").split("\t")[:2]
        rows[it] = set() if pages == "none" else {q for part in pages.split(",")
                                                  for q in range(int(part.split("-")[0]), int(part.split("-")[-1]) + 1)}
    return rows


def pages_of(it):
    """The item's text by page («=== page N ===»), or None when it has no text."""
    for d in ("sources/ocr-preferred/", "sources/ocr-rendersearch/"):
        p = os.path.join(G, d, it + ".txt")
        if os.path.exists(p): break
    else:
        return None
    pg, cur = collections.defaultdict(list), 1
    for l in open(p, encoding="utf-8", errors="replace"):
        m = re.match(r"=== page (\d+) ===", l)
        if m: cur = int(m.group(1)); continue
        pg[cur].append(l)
    return {k: "".join(v) for k, v in pg.items()}


def scan(a):
    assert not os.path.exists(a.out), f"refusing: {a.out} exists"
    rows = []
    for it in scope_rows(os.path.join(G, "dowse", a.source, "scope.tsv")):
        pg = pages_of(it)
        if pg is None: continue
        for n, t in sorted(pg.items()):
            if not ESP.search(t) or any(ZAM.search(pg.get(q, "")) for q in (n - 1, n, n + 1)): continue
            shapes, snips = [], []
            for m in ESP.finditer(t):
                lo, hi = max(0, m.start() - 500), m.end() + 500
                snips.append(t[max(0, m.start() - 200):m.end() + 200])
                shapes += [s.group(0) for s in SHAPES.finditer(t[lo:hi]) if not SKIP.search(s.group(0))]
            shapes = list(dict.fromkeys(re.sub(r"\s+", " ", s) for s in shapes))
            if PSEUD.search(t): shapes.insert(0, "ZAMENHOF as Dr. Esperanto")
            rows.append((it, str(n), "; ".join(shapes), " ‖ ".join(snips[:3]).replace("\n", " ").replace("\t", " ")))
    with open(a.out, "x", encoding="utf-8") as f:
        f.write("item\tpage\tshapes\tsnippets\n")
        for r in rows: f.write("\t".join(r) + "\n")
    print(len(rows), "pages;", sum(1 for r in rows if not r[2]), "with no shape near a mention →", a.out)


def name_patterns(path, skip):
    out = []
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or l.startswith("name\t") or not l.strip(): continue
        name, forms, _ev, common = l.rstrip("\n").split("\t")[:4]
        if name in skip: continue
        fn = [w for w in name.split()[:-1] if w[:1].isupper()]      # not «von»: «Wahl von» is no forename
        sur = "|".join(re.escape(f) for f in forms.split("|"))
        if common == "1" and fn:
            given = "|".join([re.escape(f) for f in fn] + [re.escape(f[0]) + r"\." for f in fn]
                             + [re.escape(f[:3]) + r"\." for f in fn if len(f) > 3])
            out.append(re.compile(rf"(?:\b(?:{given})\s+(?:[A-ZÀ-Ž]\.\s*)*(?:{sur})\b|\b(?:{sur}),?\s+(?:{given})(?![\wà-ž]))"))
        else:
            out.append(re.compile(rf"\b(?:{sur})\b"))
    return out


def ranges(s):
    s = sorted(s); out = []; a = b = s[0]
    for q in s[1:]:
        if q == b + 1: b = q
        else: out.append(f"{a}-{b}" if b > a else f"{a}"); a = b = q
    out.append(f"{a}-{b}" if b > a else f"{a}")
    return ",".join(out)


def build(a):
    if not a.diff: assert not os.path.exists(a.out), f"refusing: {a.out} exists"
    names = name_patterns(a.names, set(a.skip_name))
    old = scope_rows(a.old or os.path.join(G, "dowse", a.source, "scope.tsv"))
    shaped = {(r[0], int(r[1])) for r in (l.rstrip("\n").split("\t") for l in open(a.scan, encoding="utf-8"))
              if r[0] != "item" and len(r) > 2 and r[2]}
    rescue = {(r.rsplit(":", 1)[0], int(r.rsplit(":", 1)[1])) for r in a.rescue}
    tok, esp, zam, named = {}, set(), set(), set()
    for it in old:
        pg = pages_of(it)
        if pg is None: continue
        for n, t in pg.items():
            k = (it, n); tok[k] = len(t.split())
            if ESP.search(t): esp.add(k)
            if ZAM.search(t): zam.add(k)
            if any(rx.search(t) for rx in names): named.add(k)
    win = lambda k: [(k[0], q) for q in (k[1] - 1, k[1], k[1] + 1) if (k[0], q) in tok]
    spread = lambda s: {w for k in s for w in win(k)}
    was = spread(esp) | spread(named)
    oldset = {(it, q) for it, s in old.items() for q in s}
    print(f"old rule rebuilt: {len(was):,} pages; the old scope: {len(oldset):,}; only rebuilt {len(was - oldset)}, "
          f"only the old scope {len(oldset - was)}")
    if a.diff:
        for k in sorted(was - oldset): print("  only rebuilt:", k, "esp" if k in esp else "", "named" if k in named else "")
        for k in sorted(oldset - was): print("  only the old scope:", k)
        return
    keep = {k for k in esp if any(x in zam for x in win(k)) or k in shaped or k in rescue}
    print(f"Esperanto pages {len(esp)}: kept {len(keep)} (Zamenhof in the window "
          f"{sum(1 for k in esp if any(x in zam for x in win(k)))}, a person near {len(keep & shaped)}, rescued by hand "
          f"{len(keep & rescue)}), dropped {len(esp - keep)}")
    ke, kn = spread(keep), spread(named); now = ke | kn
    tw, tn = sum(tok[k] for k in was), sum(tok[k] for k in now)
    print(f"pages {len(was):,} → {len(now):,}; words {tw:,} → {tn:,}; points {tw / 1e6 * 10:.2f} → {tn / 1e6 * 10:.2f}")
    with open(a.out, "x", encoding="utf-8") as f:
        f.write(f"# {a.source}: the pages in scope, by tools/dowse-mention-scope.py build: the pages naming Zamenhof (also as "
                f"«Dr. Esperanto»), the pages naming Esperanto with a person named near the mention ({os.path.basename(a.scan)}"
                f"{', and ' + str(len(rescue)) + ' read by hand' if rescue else ''}), the pages naming one of the people of "
                f"{os.path.basename(a.names)} (a common surname with its forename or initial); one page either side."
                f"{' ' + a.note if a.note else ''} Generated; regenerate rather than edit.\n")
        for it in old:
            s = {q for (i, q) in now if i == it}
            if not s: f.write(f"{it}\tnone\tno Esperanto with a person, no one of the list\n"); continue
            why = " + ".join(w for w, c in (("Esperanto named", any(i == it for (i, _q) in ke)),
                                            ("a person of the list named", any(i == it for (i, _q) in kn))) if c)
            f.write(f"{it}\t{ranges(s)}\t{why}, one page either side\n")
    print("→", a.out)


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
s1 = sub.add_parser("scan"); s1.add_argument("source"); s1.add_argument("out")
s2 = sub.add_parser("build"); s2.add_argument("source")
s2.add_argument("--names", required=True); s2.add_argument("--scan", required=True); s2.add_argument("--out", required=True)
s2.add_argument("--old"); s2.add_argument("--rescue", nargs="*", default=[]); s2.add_argument("--skip-name", nargs="*", default=[])
s2.add_argument("--note", default=""); s2.add_argument("--diff", action="store_true")
a = ap.parse_args()
scan(a) if a.cmd == "scan" else build(a)
