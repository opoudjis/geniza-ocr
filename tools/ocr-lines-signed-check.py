#!/usr/bin/env python3
"""ocr-lines-signed-check — a signed acceptance-lines file against the proposal it was made from (2026-11-03).

    python3 tools/ocr-lines-signed-check.py <PROPOSED file> <SIGNED file>

WHY (run sheet C12: «the signed lines are the proposed ones, less their prefix and signature field»; its box-free check
was «Not built yet»: the shell form, `diff <(grep …) <(grep …)`, asks for approval; the build queue's item (4), board
2026-10-25; done by hand at cupel20b's C12 and the bi-script search fix, 2026-11-03; the editor 10:5x).
WHAT. Each file's lines that are not comments, less the prefix («PROPOSED-ACCEPTED: » / «ACCEPTED: », and the WITHDRAWN
forms) and the last « | »-field (the signature or «UNSIGNED — awaiting the editor»), compared in order. Prints the two
counts and IDENTICAL, or each line that differs (the first 10) and exits 1. Also checks that every signed line carries
one and the same signature. Reads only; WRITE-SET: none.
"""
import re, sys

PRE = re.compile(r"^(PROPOSED-ACCEPTED|ACCEPTED|PROPOSED-WITHDRAWN|WITHDRAWN): ")


def body(path):
    out, sigs = [], set()
    for l in open(path, encoding="utf-8"):
        l = l.rstrip("\n")
        if not l.strip() or l.startswith("#"):
            continue
        m = PRE.match(l)
        if not m:
            sys.exit(f"{path}: a line with no known prefix: {l[:80]}")
        rest = l[m.end():]
        head, _, sig = rest.rpartition(" | ")
        out.append((m.group(1).replace("PROPOSED-", ""), head)); sigs.add(sig)
    return out, sigs


if len(sys.argv) != 3:
    sys.exit(__doc__)
p, _ = body(sys.argv[1])
s, sigs = body(sys.argv[2])
print(f"proposed {len(p)} lines, signed {len(s)} lines; signatures in the signed file: {len(sigs)}")
bad = [(i, a, b) for i, (a, b) in enumerate(zip(p, s), 1) if a != b]
if len(p) != len(s):
    print(f"COUNTS DIFFER: {len(p)} against {len(s)}")
if len(sigs) != 1:
    print("MORE THAN ONE SIGNATURE: " + " || ".join(sorted(x[:80] for x in sigs)))
for i, a, b in bad[:10]:
    print(f"line {i} differs:\n  proposed: {a[0]}: {a[1][:200]}\n  signed:   {b[0]}: {b[1][:200]}")
if bad or len(p) != len(s) or len(sigs) != 1:
    sys.exit(1)
print("IDENTICAL, less prefix and signature")
