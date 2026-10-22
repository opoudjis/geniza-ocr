r"""ocr-scope-g4 — the gate's G4, scored on a scope row's OWN pages (the scope check, RUNBOOK.md C10).

    tools/ocr-scope-g4.py --root <$R> --gate <OCR-GATE-<suffix>-segregated.md.json> --scope <scope.tsv> [<scope.tsv> …]
                          [--out <new .md>]

WHY (on 2026-10-13 the editor asked why dictionary bodies were being scanned at all, since the measurement is to be made on
the portion of the text that is in scope; then approved going ahead with options 3, 1 and 2 at once). A scope file narrows the pages a signed line covers, but
the gate judges the WHOLE item: a scoped line inherited the class and G4 of pages it does not cover. Measured over the
191 scope rows signed by 2026-10-13 (an internal record, 2026-10-13, not published): no row affected, because
until then scoped items were even in quality; from cupel10 on, many items are scoped to a few pages (the belletristic
rule), where it bites (the short Bitner dictionary: its front matter would carry its word lists' failing Esperanto side).

HOW. For each scope row (item ⇥ lo-hi ⇥ kind [⇥ label]), the gate's own rule (`tools/ocr-accept.py`), on the row's PDF
pages only: the pages the gate scores (`pages_of`, script-segregated), each page of ≥ 60 words that is not mostly
Cyrillic, its word-list hit rate with the gate's page-local credit for the item's second languages and the planned
languages, the median. The item's main and second languages and its list pages are the gate's own record. Bar: 65 with
list pages, else 75. A self-check first: the whole item recomputed must equal the gate's G4 (it stops if not).
Verdicts per row: PASS (at or over the bar), UNDER (under it while its item passes: worse than the ledger judged, for
the editor before signing), UNDER-AS-ITEM (under it, and so is its item: the ledger's class and conditions already
answer for it, e.g. a bi-script item admitted on its Russian side only), TOO SHORT (no page of 60 words in the row: the
gate's «too short to score», neither pass nor fail), NO LIST (the item's language has no word list: unscoreable, as in
the gate). The Esperanto-side score only: a row of Russian text is judged by the ledger's Russian-only side. Also `scoped_g4(...)`, used by `tools/ocr-acceptance-lines.py --scope`.
READS ONLY. WRITE-SET: --out alone (a new file, refused if it exists); without --out, the table to stdout.
"""
import argparse, importlib.util, json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ocr_accept", os.path.join(HERE, "ocr-accept.py"))
A = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(A)
PLANNED = [n for n in ("esperanto", "ido", "occidental") if A.lex(n)]


def page_hits(root, g):
    """Per page the gate's hit rate, for one gate record g; None if the item's language has no word list."""
    prim = A.lex(g["primary"]) if g.get("primary") else None
    if not prim:
        return None
    sec = [(s["lang"], A.lex(s["lang"])) for s in g.get("all_seconds") or [] if A.lex(s["lang"])]
    sec += [(n, A.lex(n)) for n in PLANNED if n != g["primary"]]
    # the gate's DECLARED SECOND LANGUAGES (2026-10-17, the editor's choice of option 1), as in ocr-accept.py; without them the self-check
    # failed on cupel15's Volapükabled (66.99 against the gate's 70.80, 2026-10-18)
    for n in sorted(A.TL.languages(g["corpus"]) or ()):
        if n != g["primary"] and n not in A.TL.NONLATIN and A.lex(n) and n not in {m for m, _ in sec}:
            sec.append((n, A.lex(n)))
    out = {}
    for p, t in A.pages_of(os.path.join(root, g["corpus"]), True).items():
        toks = [m.group(0).lower() for m in A.WORD.finditer(t)]
        if len(toks) < 60 or sum(1 for x in toks if A.CYRILLIC.search(x)) >= 0.5 * len(toks):
            continue
        types = {m.group(0).lower() for m in A.WORD4.finditer(t)}
        here = [L for n, L in sec if sum(1 for w in types if w in L and w not in prim) >= 10]
        out[p] = 100 * sum(1 for x in toks if x in prim or any(x in L for L in here)) / len(toks)
    return out


def scoped_g4(root, g, lo, hi, _cache={}):
    """(verdict, scoped G4 or None, pages scored, bar) for pages lo–hi of the item of gate record g."""
    c = g["corpus"]
    if c not in _cache:
        h = page_hits(root, g)
        if h:
            whole = statistics.median(h.values())
            if abs(whole - g["g4"]) > 0.05:
                sys.exit(f"self-check failed: {c} recomputed G4 {whole:.2f}, the gate's {g['g4']:.2f}")
        _cache[c] = h
    h = _cache[c]
    bar = 65 if g.get("list_pages") else 75
    if h is None:
        return "NO LIST", None, 0, bar
    sc = [v for p, v in h.items() if lo <= p <= hi]
    if not sc:
        return "TOO SHORT", None, 0, bar
    s = statistics.median(sc)
    if s >= bar:
        return "PASS", s, len(sc), bar
    # UNDER only where the row is worse than what the ledger judged: the item passes, its scoped pages do not. Where the
    # item is under too, the ledger's class and conditions already answer for it (a bi-script item admitted on its
    # Russian side only, say): UNDER-AS-ITEM, the line kept as the ledger has it (found on cupel10's draft scope, the
    # Kronstadt issues, 2026-10-13).
    return ("UNDER" if g["g4"] >= bar else "UNDER-AS-ITEM"), s, len(sc), bar


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True); ap.add_argument("--gate", required=True)
    ap.add_argument("--scope", nargs="+", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    if a.out and os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    gate = {r["corpus"]: r for r in json.load(open(a.gate))}
    lines, n = [], {}
    for f in a.scope:
        for l in open(f, encoding="utf-8"):
            c = l.rstrip("\n").split("\t")
            if l.startswith("#") or len(c) < 3 or "-" not in c[1]:
                continue
            item, rng, kind, lab = c[0], c[1], c[2], (c[3] if len(c) > 3 else "")
            if item not in gate:
                v, s, k, bar, g4 = "NOT IN GATE", None, 0, "", ""
            else:
                lo, hi = map(int, rng.split("-"))
                v, s, k, bar = scoped_g4(a.root, gate[item], lo, hi)
                g4 = f"{gate[item]['g4']:.1f}"
            n[v] = n.get(v, 0) + 1
            lines.append(f"| {os.path.basename(f)} | {item} | {rng}{' — ' + lab if lab else ''} | {kind} | "
                         f"{('%.1f' % s) if s is not None else '—'} ({k} pp) | {g4} | {bar} | **{v}** |")
    txt = ("| scope file | item | PDF pages | kind | scoped G4 (pages scored) | item G4 | bar | verdict |\n"
           "|---|---|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n")
    summary = " · ".join(f"{k} {v}" for k, v in sorted(n.items()))
    if a.out:
        with open(a.out, "x", encoding="utf-8") as fh:
            fh.write(f"# Scope check (tools/ocr-scope-g4.py): {summary}\n\nGate `{os.path.basename(a.gate)}`.\n\n" + txt)
        print(f"{len(lines)} rows · {summary} → {a.out}")
    else:
        print(txt); print(summary)


if __name__ == "__main__":
    main()
