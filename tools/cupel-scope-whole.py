#!/usr/bin/env python3
r"""cupel-scope-whole — a batch's scope file of whole-item rows, from the ledger (run sheet C10).

    python3 tools/cupel-scope-whole.py --ledger <ledger .tsv> --items <batch-dir>/ITEMS.txt --out <G>/ocr/runs/CUPEL-BATCH-<n>-SCOPE.tsv \
        [--secondary <regex> …] [--comment "<line>" …]

WHY. Where the editor rules whole-item lines (C10), the scope file is one row per batch item, `item⇥1-<pages>⇥kind`.
Cupel17's 277 rows were typed; the page counts belong to the ledger, so a tool takes them from there (the box-free
cupel, 2026-10-24, cupel18a's 159 rows).

WHAT. Every item of --items found in the ledger, except PRESENCE ONLY ones (no absence lines; named in a comment line):
`<item>⇥1-<pages>⇥PRIMARY`, or SECONDARY where the item matches a --secondary regex (re.search). --comment lines go first
(each prefixed «# »), then the excluded items, then the header row. An item of --items not in the ledger stops the tool.
WRITE-SET: --out only, a new file (refused if it exists). Prints the counts.
"""
import argparse, os, re, sys

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--ledger", required=True); ap.add_argument("--items", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--secondary", action="append", default=[]); ap.add_argument("--comment", action="append", default=[])
a = ap.parse_args()
if os.path.exists(a.out):
    sys.exit(f"exists: {a.out}")
led = {}
for l in open(a.ledger, encoding="utf-8"):
    if l.startswith("#") or l.startswith("corpus\t"):
        continue
    f = l.rstrip("\n").split("\t")
    led[f[0]] = (int(f[1]), f[3])
items = [l.strip() for l in open(a.items, encoding="utf-8") if l.strip()]
missing = [i for i in items if i not in led]
if missing:
    sys.exit(f"not in the ledger: {', '.join(missing)}")
out = [i for i in items if led[i][1] == "PRESENCE ONLY"]
rows, n = [], {"PRIMARY": 0, "SECONDARY": 0}
for i in items:
    if led[i][1] == "PRESENCE ONLY":
        continue
    kind = "SECONDARY" if any(re.search(r, i) for r in a.secondary) else "PRIMARY"
    n[kind] += 1
    rows.append(f"{i}\t1-{led[i][0]}\t{kind}\n")
head = [f"# {c}\n" for c in a.comment]
head.append(f"# Not here, PRESENCE ONLY on {os.path.basename(a.ledger)}: {', '.join(out) or 'none'}.\n")
head.append("# item\tpages\tkind\tlabel\n")
with open(a.out, "x", encoding="utf-8") as fh:
    fh.write("".join(head + rows))
print(f"{len(rows)} rows (PRIMARY {n['PRIMARY']}, SECONDARY {n['SECONDARY']}); left out PRESENCE ONLY {len(out)} → {a.out}")
