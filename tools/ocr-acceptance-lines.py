#!/usr/bin/env python3
r"""ocr-acceptance-lines — the ACCEPTED lines, one per item, from an absence ledger.

    tools/ocr-acceptance-lines.py --ledger <ledger tsv> --out <new file> [--items <stems>|@file] [--signed "<signature>"]

WHY (M1 of an internal plan, 2026-10-01, not published; approved by the editor, 2026-10-02 23:0x). An item may be searched for
ABSENCE only if it carries an `ACCEPTED:` line; the acceptance readers treat that prefix as permission. So without
--signed the lines are written as `PROPOSED-ACCEPTED:`, which no reader takes up. With --signed (only on the editor's
word, after the editor signs the acceptance record) they are written as `ACCEPTED:` with the signature.

WHAT. One line per item the ledger classes ABSENCE-ADMISSIBLE, SPECIAL HANDLING or WITH EXCEPTIONS (PRESENCE ONLY items
get none: presence findings never needed a line). Fields: corpus | pages | class · G4 | the search the class requires |
the ledger's conditions, VERBATIM (exclusions, sides, scope) | source ledger | signature. WRITE-SET: --out only (refuses
an existing file).
"""
import os, re, sys, argparse, datetime

SEARCH = {"ABSENCE-ADMISSIBLE": "search sources/ocr-rendersearch/<item>.txt",
          "SPECIAL HANDLING": "search EVERY reading: sources/ocr-rendersearch-all/<item>.txt",
          "WITH EXCEPTIONS": "search sources/ocr-rendersearch/<item>.txt and, where present, sources/ocr-rendersearch-rus/<item>.txt, on the side and pages the conditions admit"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ledger", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--signed", help="the signature; ONLY on the editor's word")
    ap.add_argument("--g5", default="G5 2026-10-02", help="the G5 the lines rest on (a cupel batch: its own sample, e.g. «G5 2026-10-05 batch 1»)")
    ap.add_argument("--items", help="only these items (comma-separated stems, or @file): a cupel batch, written to its own "
                                    "new file (the editor's decision D3, 2026-10-03, for probity: the 2 Oct signed file is never edited)")
    # --scope <tsv> (cupel batch 1, editor 2026-10-03 01:5x–02:04): item · pages (e.g. 14-39) · kind (PRIMARY / SECONDARY).
    # One line PER ROW, its absence confined to those pages; a SECONDARY row adds the editor's condition. Items in the
    # ledger but without a row get no line (named on the console). Implies --items = the scope's items.
    ap.add_argument("--scope", help="a scope TSV: item, pages, kind — one scoped line per row")
    a = ap.parse_args()
    scope = None
    if a.scope:
        scope = [r for r in (l.rstrip("\n").split("\t") for l in open(a.scope, encoding="utf-8")
                             if l.strip() and not l.startswith("#")) if r[0] != "item"]
        bad = [r for r in scope if len(r) < 3 or r[2] not in ("PRIMARY", "SECONDARY") or not re.fullmatch(r"\d+-\d+", r[1])]
        if bad: sys.exit(f"bad scope rows: {bad}")
        if not a.items: a.items = ",".join(sorted({r[0] for r in scope}))
    want = (set([x.strip() for x in open(a.items[1:], encoding="utf-8").read().splitlines() if x.strip()]) if a.items.startswith("@") else set(a.items.split(","))) if a.items else None
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: write only to a NEW file")
    pre = "ACCEPTED:" if a.signed else "PROPOSED-ACCEPTED:"
    sig = a.signed or "UNSIGNED — awaiting the editor"
    led = os.path.basename(a.ledger)
    rows = [l.rstrip("\n").split("\t") for l in open(a.ledger, encoding="utf-8") if not l.startswith("#")][1:]
    out, n = [], {}
    for r in rows:
        r += [""] * (7 - len(r)); c, pages, g4, k = r[0], r[1], r[2], r[3]
        if k not in SEARCH: continue
        if want is not None and c not in want: continue
        cond = r[6].strip() or "none"
        if scope is None:
            out.append(f"{pre} {c} | {pages} pp | {k} · G4 {g4} | {SEARCH[k]} | conditions: {cond} | {led} · {a.g5} | {sig}")
            n[k] = n.get(k, 0) + 1
            continue
        for _, rng, kind in [s for s in scope if s[0] == c]:
            lo, hi = map(int, rng.split("-"))
            sc = f"SCOPE: absence admissible on pages {lo}–{hi} only ({hi - lo + 1} pp); {kind}"
            if kind == "SECONDARY":
                sc += " LITERATURE — absence here shows only that this work does not mention X; it is not evidence about the event"
            out.append(f"{pre} {c} | pp. {lo}–{hi} of {pages} | {k} · G4 {g4} | {SEARCH[k]} | conditions: {sc}; {cond} | {led} · {a.g5} | {sig}")
            n[kind] = n.get(kind, 0) + 1
    if want is not None:
        got = {l.split(" | ")[0].split(" ", 1)[1] for l in out}
        if want - got: print("NO LINE (PRESENCE ONLY, or not in the ledger):", sorted(want - got))
    hdr = (f"# GENERATED {datetime.date.today()} by tools/ocr-acceptance-lines.py from {led}"
           f"{' for the items ' + ', '.join(sorted(want)) if want else ''}. "
           f"{'SIGNED' if a.signed else 'NOT SIGNED: these are proposals; no item may be searched for absence on them'}. "
           f"Counts: {n}\n")
    open(a.out, "w", encoding="utf-8").write(hdr + "\n".join(out) + "\n")
    print(len(out), "lines ·", n, "→", a.out)


if __name__ == "__main__":
    main()
