#!/usr/bin/env python3
r"""ocr-search-all-readings — for each SPECIAL HANDLING item, ONE searchable file holding EVERY reading on disk of each page.

    tools/ocr-search-all-readings.py --ledger <ledger tsv> --root <ocr-rendersearch> --out <new folder>

WHY (the editor chose option (a) on 2026-10-02, since that is why the extra readings are held). The G5 re-sample on a
ledger of 2026-10-02 (an internal record, not published) failed SPECIAL HANDLING at 2 / 40: on both failed pages (La Ondo de Esperanto 1913.05 p.10, 1913.011 p.28) the missed
names were in readings we hold — `psm4`, `rus`, `rusfull` — but not in the one or two readings the search read. Searching
the union of every reading on disk scored 0 / 40 on the same sample. This replaces moving
dense pages to presence-only with a principled rule: an absence claim on a SPECIAL HANDLING item searches every reading.

WHAT. For every item the ledger classes SPECIAL HANDLING, writes `<out>/<item>.txt` in the combined files' format
(`=== page N ===` blocks); each block is every `page-NNNN*.txt` in the item's folder (main text, psm4, rus, orus, rusfull,
layout, sc3x, eo-/ru-clean, text layer, second-language merges, vision), each headed `--- <kind> ---`, plus the page of
the Russian search file (`ocr-rendersearch-rus/<item>.txt`) if present. SEARCH ONLY: not a citation text, never a
reading of record. WRITE-SET: the new <out> folder only (refuses to write into an existing one). Re-run after any re-read.
"""
import os, re, sys, glob, argparse, collections


def pages(path):
    if not os.path.exists(path): return {}
    t = open(path, encoding="utf-8", errors="ignore").read()
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ledger", required=True); ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--classes", default="SPECIAL HANDLING")
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: write only into a NEW folder")
    want = set(a.classes.split(","))
    items = [r[0] for r in (l.rstrip("\n").split("\t") for l in open(a.ledger, encoding="utf-8") if not l.startswith("#"))
             if len(r) > 3 and r[3] in want]
    rus = os.path.join(os.path.dirname(os.path.abspath(a.root)), "ocr-rendersearch-rus")
    os.makedirs(a.out); n_items = n_pages = 0; kinds = collections.Counter()
    for c in items:
        d = os.path.join(a.root, c); by = collections.defaultdict(list)
        for f in glob.glob(os.path.join(d, "page-*.txt")):
            m = re.fullmatch(r"page-(\d+)(?:\.(.+))?\.txt", os.path.basename(f))
            if m: by[int(m.group(1))].append((m.group(2) or "main", f))
        rp = pages(os.path.join(rus, c + ".txt"))
        body = []
        for p in sorted(set(by) | set(rp)):
            blk = []
            for kind, f in sorted(by.get(p, []), key=lambda x: (x[0] != "main", x[0])):
                t = open(f, encoding="utf-8", errors="ignore").read().strip()
                if t: blk.append(f"--- {kind} ---\n{t}"); kinds[kind] += 1
            if rp.get(p, "").strip(): blk.append(f"--- russian-search ---\n{rp[p].strip()}"); kinds["russian-search"] += 1
            if blk: body.append(f"=== page {p} ===\n" + "\n".join(blk) + "\n")
        if body:
            open(os.path.join(a.out, c + ".txt"), "w", encoding="utf-8").write("\n" + "\n".join(body))
            n_items += 1; n_pages += len(body)
    print(f"{n_items} items · {n_pages} pages · every reading written to {a.out}")
    print("readings per kind:", dict(kinds.most_common()))


if __name__ == "__main__":
    main()
