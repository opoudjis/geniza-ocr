#!/usr/bin/env python3
r"""ocr-acceptance-lines — the ACCEPTED lines, one per item, from an absence ledger.

    tools/ocr-acceptance-lines.py --ledger <ledger tsv> --out <new file> [--items <stems>|@file] [--signed "<signature>"]
                                  [--scope <tsv> --gate <gate .md.json> --root <$R>]

WHY (M1 of a write-ups plan (an internal record, 2026-10-01, not published); approved by the editor, 2026-10-02). An item may be searched for
ABSENCE only if it carries an `ACCEPTED:` line; the acceptance readers treat that prefix as permission. So without
--signed the lines are written as `PROPOSED-ACCEPTED:`, which no reader takes up. With --signed (only on the editor's
word, after the editor signs the acceptance record) they are written as `ACCEPTED:` with the signature.

WHAT. One line per item the ledger classes ABSENCE-ADMISSIBLE, SPECIAL HANDLING or WITH EXCEPTIONS (PRESENCE ONLY items
get none: presence findings never needed a line). Fields: corpus | pages | class · G4 | the search the class requires |
the ledger's conditions, VERBATIM (exclusions, sides, scope) | source ledger | signature. WRITE-SET: --out only (refuses
an existing file).

WITHDRAWAL (2026-10-07; option a, the editor's ruling that the complete Gallica copy LEsperantiste.1907.5.1 replace the
ÖNB copy LEsperantiste.1907.5). Readers take the union of the signed files, the later file holding, and an item searched for
absence is one with an `ACCEPTED:` line, whatever the ledger says now. So an item the editor withdraws needs a line that
cancels its earlier one: --withdraw <item>[,<item>…] writes `WITHDRAWN: <item> | <class> | <the ledger's reason, verbatim>
| <ledger> | <signature>` (`PROPOSED-WITHDRAWN:` without --signed). The item must already be PRESENCE ONLY in --ledger (the
ruling goes into the ledger tool first); else the tool refuses. `tools/ocr-dowse.py` (signed_lines) drops an item whose
latest line is WITHDRAWN.
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
    # Optional 4th column (2026-10-09): a label, the essay or part the row is (see below).
    # One line PER ROW, its absence confined to those pages; a SECONDARY row adds the editor's condition. Items in the
    # ledger but without a row get no line (named on the console). Implies --items = the scope's items.
    ap.add_argument("--scope", help="a scope TSV: item, pages, kind — one scoped line per row")
    # With --scope, --gate and --root (approved by the editor, 2026-10-13): each row's G4 is scored on its OWN
    # pages (tools/ocr-scope-g4.py, the gate's rule) and written into its line, «G4 <scoped> on pp. lo–hi (item <G4>)»;
    # a row UNDER the bar gets no line (named on the console, for the editor). Until then a scoped line carried its whole
    # item's G4, judged partly on pages it does not cover (measured over the 191 rows signed by then: none affected,
    # an internal record, 2026-10-13, not published).
    ap.add_argument("--gate", help="with --scope: the gate .md.json the ledger was built from")
    ap.add_argument("--root", help="with --scope: the readings root ($R)")
    ap.add_argument("--withdraw", help="items to WITHDRAW (comma-separated, or @file): each must be PRESENCE ONLY in --ledger")
    a = ap.parse_args()
    wd = None
    if a.withdraw:
        wd = (set(x.strip() for x in open(a.withdraw[1:], encoding="utf-8").read().splitlines() if x.strip())
              if a.withdraw.startswith("@") else set(x.strip() for x in a.withdraw.split(",") if x.strip()))
        if not a.items and not a.scope: a.items = "@/dev/null"   # a withdrawal alone writes no ACCEPTED line
    scope = None
    if a.scope:
        scope = [r for r in (l.rstrip("\n").split("\t") for l in open(a.scope, encoding="utf-8")
                             if l.strip() and not l.startswith("#")) if r[0] != "item"]
        bad = [r for r in scope if len(r) < 3 or r[2] not in ("PRIMARY", "SECONDARY") or not re.fullmatch(r"\d+-\d+", r[1])]
        if bad: sys.exit(f"bad scope rows: {bad}")
        if not a.items: a.items = ",".join(sorted({r[0] for r in scope}))
        if not (a.gate and a.root): sys.exit("--scope needs --gate and --root: each row's G4 is scored on its own pages")
        import importlib.util, json
        _sp = importlib.util.spec_from_file_location("ocr_scope_g4", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr-scope-g4.py"))
        SG = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(SG)
        gate = {r["corpus"]: r for r in json.load(open(a.gate))}
    under = []
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
        for s in [s for s in scope if s[0] == c]:
            rng, kind = s[1], s[2]
            # an optional 4th column, a LABEL (2026-10-09, on the editor's ruling for Li kaj Ni that the judgement of
            # absence there has to be made essay by essay): the essay or part the row is, written into its SCOPE as «— label», which
            # ocr-dowse.py reads as the segment's name; no «;» in a label (the conditions are split on it)
            lab = s[3].strip() if len(s) > 3 and s[3].strip() else ""
            if ";" in lab: sys.exit(f"a scope label may not hold «;»: {lab}")
            lo, hi = map(int, rng.split("-"))
            if c not in gate: sys.exit(f"{c} is not in the gate {a.gate}")
            v, sg4, npp, bar = SG.scoped_g4(a.root, gate[c], lo, hi)
            if v == "UNDER":
                under.append(f"{c} pp. {lo}–{hi}: G4 {sg4:.1f} on its own pages ({npp} scored), bar {bar} (item {g4})")
                continue
            g4f = (f"G4 {sg4:.1f} on pp. {lo}–{hi} ({npp} pp scored; item {g4})" if v in ("PASS", "UNDER-AS-ITEM")
                   else f"G4 {g4} (item; pp. {lo}–{hi} {'too short to score' if v == 'TOO SHORT' else 'unscoreable'})")
            sc = f"SCOPE: absence admissible on pages {lo}–{hi} only ({hi - lo + 1} pp)" + (f" — {lab}" if lab else "") + f"; {kind}"
            if kind == "SECONDARY":
                sc += " LITERATURE — absence here shows only that this work does not mention X; it is not evidence about the event"
            # an «Esperanto side» row of a bi-script item admitted on its other side only (failure map R64; approved by the editor
            # 2026-10-24 21:4x, `ocr-biscript-scope.py`): the row's own pages pass on the Esperanto side, so the
            # item's «… side only» clause would contradict the row; the row says which side it admits
            rcond = cond
            if lab.startswith("Esperanto side") and v == "PASS":
                rcond = re.sub(r"SPECIAL HANDLING \(bi-script\): (.*?) — absence admissible on the (\w+) side only",
                               lambda m: f"SPECIAL HANDLING (bi-script): item {m[1]}; on pp. {lo}–{hi} the Esperanto side "
                                         f"passes alone (G4 {sg4:.1f}, bar {bar}) — absence admissible on the ESPERANTO "
                                         f"side of pp. {lo}–{hi}; the {m[2]} side as the item's own line", cond)
            out.append(f"{pre} {c} | pp. {lo}–{hi} of {pages} | {k} · {g4f} | {SEARCH[k]} | conditions: {sc}; {rcond} | {led} · {a.g5} | {sig}")
            n[kind] = n.get(kind, 0) + 1
    if under:
        print("NO LINE, SCOPE UNDER THE BAR on its own pages (for the editor):\n  " + "\n  ".join(under))
    if want is not None:
        got = {l.split(" | ")[0].split(" ", 1)[1] for l in out}
        u = {x.split(" pp. ")[0] for x in under}
        if want - got - u: print("NO LINE (PRESENCE ONLY, or not in the ledger):", sorted(want - got - u))
    if wd:
        byc = {r[0]: r for r in rows}
        bad = sorted(c for c in wd if c not in byc or byc[c][3] != "PRESENCE ONLY")
        if bad: sys.exit(f"--withdraw refused: not PRESENCE ONLY in {led} (rule it in the ledger tool first): {bad}")
        wpre = "WITHDRAWN:" if a.signed else "PROPOSED-WITHDRAWN:"
        for c in sorted(wd):
            out.append(f"{wpre} {c} | PRESENCE ONLY | {byc[c][4].strip()} | {led} | {sig}")
            n["WITHDRAWN"] = n.get("WITHDRAWN", 0) + 1
    hdr = (f"# GENERATED {datetime.date.today()} by tools/ocr-acceptance-lines.py from {led}"
           f"{' for the items ' + ', '.join(sorted(want)) if want else ''}"
           f"{' withdrawing ' + ', '.join(sorted(wd)) if wd else ''}. "
           f"{'SIGNED' if a.signed else 'NOT SIGNED: these are proposals; no item may be searched for absence on them'}. "
           f"Counts: {n}\n")
    open(a.out, "w", encoding="utf-8").write(hdr + "\n".join(out) + "\n")
    print(len(out), "lines ·", n, "→", a.out)


if __name__ == "__main__":
    main()
