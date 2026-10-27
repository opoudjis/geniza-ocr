#!/usr/bin/env python3
r"""dowse-input-list — the dowse's input list, less the doubles, with the scope rows for Ezri's scope files.

    python3 tools/dowse-input-list.py --ledger <OCR-ABSENCE-LEDGER-….tsv> --out <prefix>

WHY (2026-10-20; the editor 16:2x,, on geniza/ocr/method/DOWSE-DOUBLES-METHOD-PROPOSAL-2026-10-20.md with
his kind 0). Ezri's base (agreed 2026-10-18): every item of the CURRENT ledger,
signed or presence only, plus the SIGNED born-digital texts, «less OCR/born-digital doubles, bound volumes and strays».
This tool takes the doubles out that the COPIES table of tools/ocr-dowse.py has ruled, and only those:

  kind 3, one text scanned and typed: for a COPIES entry whose `same_text` group holds its `whole_in` copy, every OTHER
          copy in that group is left out over its stretch (a scan's PDF pages; a typed text whole). The `whole_in` copy
          is read. Copies outside the group (other editions, translations: kind 0) are never left out.
  kind 0, two texts of one work: nothing left out; listed so the harvest can merge the facts (two locators).
  kind 1, one text in two copies: nothing left out (the page skip waits until a pair is ruled triangulated, Ezri
          2026-10-20); a triangulated pair is listed as a candidate, the per-page choice not built.
  kind 2, a copy kept off: deleted from the corpus since 2026-10-20 15:4x; any still on the ledger as «a second copy
          kept off» (PRESENCE_ONLY_NAMED) is left out whole.

Undeclared doubles (the census, ocr/runs/DOWSE-DOUBLES-CENSUS-*.tsv) are NOT taken out: they are read as now until each
pair is ruled into COPIES. Nothing leaves silently: every left-out stretch is in <prefix>-LEFT-OUT.tsv with the entry
that left it out.

WRITES (refuses existing files):
  <prefix>-LIST.tsv      one row per item read: tree (ocr / born-digital) · item · pages read («all», or «1-4,120-122»
                         for a scan with stretches left out) · pages in all · why
  <prefix>-LEFT-OUT.tsv  one row per stretch left out: item · stretch · kind · the COPIES entry · the copy read instead
  <prefix>-SCOPE-ROWS.tsv for Ezri's dowse/<source>/scope.tsv (her form, 2026-10-20: «‹text stem› TAB ‹PDF pages in
                         scope› TAB ‹why›», pages kept, «all» or «none»): one row per item with anything left out
  <prefix>-COPIES.tsv    every COPIES entry: kind (0 / 1 / 3), its copies, which are one text, whether triangulated
Reads only: the ledger, tools/ocr-dowse.py (COPIES, and PRESENCE_ONLY_NAMED of tools/ocr-absence-ledger.py), the
signed born-digital lists (tools/born_digital_lines.py).
"""
import argparse, importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def ranges(pages):
    """sorted page numbers → «1-4,120-122»"""
    out, start, prev = [], None, None
    for p in pages:
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"{start}-{prev}" if prev > start else f"{start}"); start = prev = p
    if start is not None:
        out.append(f"{start}-{prev}" if prev > start else f"{start}")
    return ",".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ledger", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    outs = {k: f"{a.out}-{k}.tsv" for k in ("LIST", "LEFT-OUT", "SCOPE-ROWS", "COPIES")}
    for p in outs.values():
        if os.path.exists(p):
            sys.exit(f"exists: {p}")
    D = load("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
    L = load("ocr_absence_ledger", os.path.join(HERE, "ocr-absence-ledger.py"))
    B = load("born_digital_lines", os.path.join(HERE, "born_digital_lines.py"))

    ocr = {}
    for l in open(a.ledger, encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if l.startswith("#") or len(f) < 4 or f[0] == "corpus":
            continue
        ocr[f[0]] = (int(f[1]) if f[1].isdigit() else 0, f[3])
    bd = B.lists("signed")

    left = {}          # item → [(lo, hi) or None (whole), kind, entry, read instead]
    kept_off = {c for c, why in L.PRESENCE_ONLY_NAMED.items() if "second copy kept off" in why}
    for c in sorted(kept_off & set(ocr)):
        left.setdefault(c, []).append((None, "2", "PRESENCE_ONLY_NAMED: a second copy kept off", "the kept copy"))
    crows = []
    for w in D.COPIES:
        groups = w.get("same_text") or []
        whole = w.get("whole_in")
        tri = bool(w.get("triangulated"))
        g = next((set(x) for x in groups if whole in x), None)
        if whole and g:
            kind = "3"
            for it, rng, rank in w["copies"]:
                if it == whole or it not in g:
                    continue
                left.setdefault(it, []).append((rng, "3", w["work"], whole))
        elif groups:
            kind = "1"
        else:
            kind = "0"
        crows.append((w["work"], kind, "; ".join(f"{it}{f' PDF {r[0]}–{r[1]}' if r else ''}" for it, r, _ in w["copies"]),
                      " | ".join(" + ".join(x) for x in groups) or "none (each copy its own text)",
                      w.get("triangulated") or "", w.get("texts_checked", "")))

    with open(outs["LEFT-OUT"], "w", encoding="utf-8") as o:
        o.write("item\tstretch\tkind\tCOPIES entry\tread instead\n")
        for it in sorted(left):
            for rng, kind, entry, instead in left[it]:
                o.write(f"{it}\t{'whole' if rng is None else f'PDF {rng[0]}-{rng[1]}'}\t{kind}\t{entry}\t{instead}\n")
    scope, nread = [], 0
    with open(outs["LIST"], "w", encoding="utf-8") as o:
        o.write("tree\titem\tpages read\tpages in all\twhy\n")
        for tree, items in (("ocr", ocr), ("born-digital", bd)):
            for it in sorted(items):
                n = items[it][0] if tree == "ocr" else 0
                out = left.get(it, [])
                if any(r is None for r, *_ in out):
                    why = "; ".join(f"left out whole, kind {k}: {e} (read instead: {i})" for r, k, e, i in out if r is None)
                    scope.append((it, "none", why)); continue
                if out:
                    gone = {p for (lo, hi), *_ in out for p in range(lo, hi + 1)}
                    keep = [p for p in range(1, n + 1) if p not in gone]
                    pr = ranges(keep) or "none"
                    why = "; ".join(f"PDF {lo}–{hi} left out, kind {k}: {e} (read instead: {i})" for (lo, hi), k, e, i in out)
                    scope.append((it, pr, why))
                else:
                    pr, why = "all", (f"ledger {items[it][1]}" if tree == "ocr" else f"signed born-digital ({items[it].get('class', '')})")
                o.write(f"{tree}\t{it}\t{pr}\t{n or ''}\t{why}\n"); nread += 1
    with open(outs["SCOPE-ROWS"], "w", encoding="utf-8") as o:
        o.write("# for dowse/<source>/scope.tsv: «text stem TAB PDF pages in scope (kept) TAB why»\n")
        for it, pr, why in scope:
            o.write(f"{it}\t{pr}\t{why}\n")
    with open(outs["COPIES"], "w", encoding="utf-8") as o:
        o.write("work\tkind\tcopies\tone text\ttriangulated\ttexts checked\n")
        for r in crows:
            o.write("\t".join(r) + "\n")
    k = {x: sum(1 for r in crows if r[1] == x) for x in "013"}
    print(f"read: {nread} items ({len(ocr)} OCR on the ledger, {len(bd)} signed born-digital, less {len(scope)} with "
          f"something left out of which {sum(1 for _, p, _ in scope if p == 'none')} whole); COPIES: kind 0 {k['0']}, "
          f"kind 1 {k['1']}, kind 3 {k['3']} → {', '.join(outs.values())}")


if __name__ == "__main__":
    main()
