#!/usr/bin/env python3
"""A typed text with its paragraphs numbered, for readers who cite «¶ N» (2026-10-15: the Jossinet readers of 2026-10-13
read a numbered copy kept only in that session's scratchpad, so the global redowse had no text to cite by ¶).

    tools/text-paragraphs.py <text> <out> [--check <dowse facts file> --item <locator key>]

A paragraph is a run of non-empty lines; ¶ N is the N-th, marked «=== ¶ N ===» on a line of its own before it (the
Jossinet text: 47 paragraphs, one line each, «47 alineoj» as its brief says). <out> is written create-only. With
--check, every line of the facts file located «<item>, ¶ N» has its anchor looked for in ¶ N (spaces and case folded,
the end marker ⟨fino⟩ and «…» cut): the count found and the lines not found are printed, so the numbering is shown to
be the one the lines were read against. Ezri, 2026-10-15."""
import argparse, csv, os, re, sys

def paragraphs(text):
    out, cur = [], []
    for l in text.split("\n"):
        if l.strip(): cur.append(l.rstrip())
        elif cur: out.append("\n".join(cur)); cur = []
    if cur: out.append("\n".join(cur))
    return out

def norm(s): return " ".join(re.sub(r"⟨fino⟩|…|\.\.\.", " ", s).lower().split())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text"); ap.add_argument("out")
    ap.add_argument("--check", default=""); ap.add_argument("--item", default="")
    a = ap.parse_args()
    ps = paragraphs(open(a.text, encoding="utf-8").read())
    if a.check:
        if not a.item: sys.exit("--check needs --item")
        found, miss = 0, []
        # the item by its file name or by its key (2026-10-17, the item keys; OCR-ITEM-TABLE.tsv, «key»): lines
        # assembled after the keys carry the key, older ones the name
        names = {a.item}
        tp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "published", "heterophony-resources", "geniza", "OCR-ITEM-TABLE.tsv")
        if os.path.exists(tp):
            for r in csv.DictReader((x for x in open(tp, encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
                if a.item in (r["item"], (r.get("key") or "").strip()): names |= {r["item"], (r.get("key") or r["item"]).strip()}
        alt = "|".join(re.escape(x) for x in sorted(names, key=len, reverse=True))
        for l in open(a.check, encoding="utf-8"):
            if not l.startswith("- $$$"): continue
            m = re.search(rf"(?:{alt}), ¶ (\d+)", l)
            if not m: continue
            parts = l.split(" · ")
            loc_i = next((i for i, p in enumerate(parts) if any(x + ", ¶" in p for x in names)), None)
            if loc_i is None or loc_i < 1: continue
            anchor, n = parts[loc_i - 1], int(m.group(1))
            if 1 <= n <= len(ps) and norm(anchor) and norm(anchor) in norm(ps[n - 1]): found += 1
            else: miss.append(f"  ¶ {n}: «{anchor[:80]}»")
        print(f"{len(ps)} paragraphs; anchors found in their ¶: {found} of {found + len(miss)}")
        for x in miss[:30]: print(x)
        return
    with open(a.out, "x", encoding="utf-8") as f:
        f.write("\n\n".join(f"=== ¶ {i} ===\n{p}" for i, p in enumerate(ps, 1)) + "\n")
    print(f"{len(ps)} paragraphs → {a.out}")

if __name__ == "__main__":
    main()
