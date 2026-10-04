#!/usr/bin/env python3
r"""ocr-ledger-compare — every class move between two absence ledgers, as markdown (M4.3).

    tools/ocr-ledger-compare.py <old ledger tsv> <new ledger tsv> [> out.md]

WHY. After every chain the moves against the last ledger are recorded, each with its reason (the step that compares
it with the last ledger and records every class move). Used on 2 Oct for 10-01a → 10-02b (which exposed the
English code fault: 239 items to PRESENCE ONLY) and 10-01a → 10-02c (14 moves, all the ad ruling).

WHAT. Prints: a table of items and pages per class, before and after; every item that changed class, grouped by move,
with its pages, its G4 before and after and the new ledger's reason; and how many items kept their class but changed
notes. Paths are taken as given (absolute, or relative to the working directory). Writes nothing.
"""
import csv, sys, collections


def load(path):
    r = {}
    for row in csv.reader((l for l in open(path, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if row[0] == "corpus": continue
        row += [""] * (7 - len(row)); r[row[0]] = row
    return r


def tot(d):
    t = collections.defaultdict(lambda: [0, 0])
    for r in d.values(): t[r[3]][0] += 1; t[r[3]][1] += int(r[1] or 0)
    return t


def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    a, b = load(sys.argv[1]), load(sys.argv[2])
    ta, tb = tot(a), tot(b)
    print("| class | before items / pages | after items / pages |\n|---|---|---|")
    for k in sorted(set(ta) | set(tb)): print(f"| {k} | {ta[k][0]:,} / {ta[k][1]:,} | {tb[k][0]:,} / {tb[k][1]:,} |")
    moves = collections.defaultdict(list)
    for c in sorted(set(a) | set(b)):
        ka = a[c][3] if c in a else "(absent)"; kb = b[c][3] if c in b else "(absent)"
        if ka != kb: moves[(ka, kb)].append(c)
    print(f"\n{sum(map(len, moves.values()))} items moved")
    for (ka, kb), cs in sorted(moves.items(), key=lambda x: -len(x[1])):
        print(f"\n### {ka} → {kb} ({len(cs)})")
        for c in cs:
            r = b.get(c) or a.get(c)
            why = (r[4] or r[5] or r[6])[:160]
            g4a = a[c][2] if c in a else ""; g4b = b[c][2] if c in b else ""
            print(f"- {c} · {r[1]} pp · G4 {g4a} → {g4b} · {why}")
    chg = [c for c in set(a) & set(b) if a[c][3] == b[c][3] and (a[c][4:7] != b[c][4:7])]
    print(f"\n{len(chg)} items kept their class but changed notes")


if __name__ == "__main__":
    main()
