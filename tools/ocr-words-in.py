#!/usr/bin/env python3
r"""ocr-words-in — words in: how many words the signed pages hold, and how many a round's signed file added (RUNBOOK.md C13).

    tools/ocr-words-in.py --round <the round's signed file name, e.g. OCR-ACCEPTANCE-LINES-2026-10-13-SIGNED-cupel10.txt>
                          [--items <the round's ITEMS.txt>]

WHY (the editor asked on 2026-10-13 for a report, at the end of each cupel round, of how many words are now in and how
many the round added). WHAT, counted twice, with every signed file and without the round's file, so the difference is what the
round added:
  (1) the words on SIGNED pages: the signed lines as the dowse reads them (`tools/ocr-dowse.py` signed_lines(): the
      union of the signed acceptance-line files (internal records, not published), the later file holding all of an item's lines, a
      WITHDRAWN line dropping it); each line's pages its SCOPE range, or the whole item where it has none (the lines
      signed before the scope files); split by the line's kind: PRIMARY, SECONDARY (from its SCOPE condition), or
      UNSCOPED (no kind given). Exception pages inside a range are counted (they are signed, with conditions).
  (2) the born-digital signed lists (Tekstaro, web saves, typed texts), by kind, and everything signed together;
  (3) apart, the PRESENCE ONLY items of the current ledger (counted separately, as the editor ruled on 2026-10-14); nothing else
      (pages outside a scope, texts not in the ledger: not mentioned at all, by the same ruling); and, with --items, the round's items.
Words: whitespace-separated tokens holding a letter, in each page's PREFERRED reading (`ocr-preferred/<item>.txt`,
the one reading per page), else the search text (`ocr-rendersearch/<item>.txt`), else
`born-digital-text/<item>.txt`. A count of what is held, not of what is read correctly.
READS ONLY; prints the table.
"""
import argparse, glob, importlib.util, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
S = os.path.join(G, "sources")
_sp = importlib.util.spec_from_file_location("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
D = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(D)
_sb = importlib.util.spec_from_file_location("born_digital_lines", os.path.join(HERE, "born_digital_lines.py"))
BDL = importlib.util.module_from_spec(_sb); _sb.loader.exec_module(BDL)
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
LETTER = re.compile(r"[^\W\d_]")
SCOPE = re.compile(r"SCOPE: absence admissible on pages (\d+)–(\d+) only")
_cache = {}


def page_words(item):
    if item not in _cache:
        for tree in ("ocr-preferred", "ocr-rendersearch", "born-digital-text"):
            f = os.path.join(S, tree, item + ".txt")
            if os.path.exists(f):
                parts = PAGE.split(open(f, encoding="utf-8", errors="ignore").read())
                pg = ({int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)} if len(parts) > 1
                      else {0: parts[0]})
                _cache[item] = {p: sum(1 for w in t.split() if LETTER.search(w)) for p, t in pg.items()}
                break
        else:
            _cache[item] = None
    return _cache[item]


def signed_words(signed):
    tot, missing = {"PRIMARY": 0, "SECONDARY": 0, "UNSCOPED": 0}, []
    for item, (_, _, lines) in signed.items():
        pw = page_words(item)
        if pw is None:
            missing.append(item); continue
        for x in lines:
            cond = " | ".join(x)
            m = SCOPE.search(cond)
            kind = ("PRIMARY" if "; PRIMARY" in cond else "SECONDARY" if "SECONDARY LITERATURE" in cond else "UNSCOPED")
            tot[kind] += sum(n for p, n in pw.items() if not m or int(m.group(1)) <= p <= int(m.group(2)))
    return tot, missing


def bd_kinds():
    """item → PRIMARY / SECONDARY for the born-digital items, as the dowse takes it (`tools/ocr-dowse.py`, BORN-DIGITAL
    ITEMS): the item table's kind, else the latest `ocr/runs/OCR-ITEM-DATES-*.tsv`, column 4."""
    it0, _ = D.citation_tables()
    dts = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-ITEM-DATES-*.tsv")))
    kinds = {x[0]: x[3] for x in (l.rstrip("\n").split("\t") for l in (open(dts[-1], encoding="utf-8") if dts else []))
             if len(x) > 3 and not x[0].startswith("#")}
    return lambda it: (it0.get(it, {}) or {}).get("kind") or kinds.get(it, "")


def bd_words(rows, kind_of):
    """words of born-digital list rows, by kind: each row's text (`born_digital_lines.text_path`), its scope where the
    list gives «sections N–M», page markers of typed PDFs left out."""
    tot, missing = {"PRIMARY": 0, "SECONDARY": 0, "kind not known": 0}, []
    for it, b in rows.items():
        tp = BDL.text_path(b)
        if not os.path.isfile(tp):
            missing.append(it); continue
        t = open(tp, encoding="utf-8", errors="ignore").read()
        ms = re.fullmatch(r"sections? (\d+)(?:[–-](\d+))?", (b.get("scope") or "whole").strip())
        if ms and not BDL.is_paged(b):
            lo, hi = int(ms.group(1)), int(ms.group(2) or ms.group(1))
            t = "\n".join(x for _, sec, x in BDL.blocks(t) if lo <= sec <= hi)
        n = sum(1 for w in PAGE.sub(" ", t).split() if LETTER.search(w))
        k = kind_of(it)
        tot[k if k in ("PRIMARY", "SECONDARY") else "kind not known"] += n
    return tot, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--round", required=True); ap.add_argument("--items")
    a = ap.parse_args()
    files = [os.path.basename(f) for f in glob.glob(os.path.join(G, "ocr", "lines", "OCR-ACCEPTANCE-LINES-*SIGNED*.txt"))]
    if a.round not in files:
        raise SystemExit(f"--round {a.round} is not a signed file in geniza/ocr/lines/")
    after = D.signed_lines()
    real_glob = D.glob.glob
    D.glob.glob = lambda p: [f for f in real_glob(p) if os.path.basename(f) != a.round]   # the same reader, less the round
    try:
        before = D.signed_lines()
    finally:
        D.glob.glob = real_glob
    (ta, ma), (tb, mb) = signed_words(after), signed_words(before)
    print("| signed pages, words | before the round | after | added |\n|---|---:|---:|---:|")
    for k in ("PRIMARY", "SECONDARY", "UNSCOPED"):
        print(f"| {k} | {tb[k]:,} | {ta[k]:,} | {ta[k] - tb[k]:+,} |")
    print(f"| **all signed** | {sum(tb.values()):,} | {sum(ta.values()):,} | {sum(ta.values()) - sum(tb.values()):+,} |")
    print(f"\nsigned items: {len(before)} before, {len(after)} after; with no text found: {sorted(set(ma))}")
    # BORN-DIGITAL TOO (the editor ruled on 2026-10-14 11:3x that the corpus must include what is used from the
    # Tekstaro and the born-digital sources). Until then only the OCR acceptance lines were counted. The dowse
    # searches the SIGNED born-digital lists too (`born_digital_lines.lists("signed")`): the Tekstaro selections, the
    # web saves, the typed texts. Their words, by kind, beside the OCR count; the corpus total counts every listed one.
    kind_of = bd_kinds()
    bds, bdm = bd_words(BDL.lists("signed"), kind_of)
    print("\n| born-digital signed lists (Tekstaro, web saves, typed texts), words | |\n|---|---:|")
    for k, v in bds.items():
        print(f"| {k} | {v:,} |")
    print(f"| **all born-digital signed** | {sum(bds.values()):,} |")
    print(f"born-digital signed items: {len(BDL.lists('signed'))}; with no text found: {sorted(bdm)}")
    print(f"\n**everything signed, OCR and born-digital: {sum(ta.values()) + sum(bds.values()):,} words** "
          f"(PRIMARY {ta['PRIMARY'] + bds['PRIMARY']:,}, SECONDARY {ta['SECONDARY'] + bds['SECONDARY']:,}, "
          f"OCR lines without a kind {ta['UNSCOPED']:,}, born-digital of unknown kind {bds['kind not known']:,})")
    # PRESENCE ONLY APART; NOTHING ELSE (the editor ruled on 2026-10-14 11:5x that PRESENCE ONLY items are counted
    # separately, and that pages outside a signed item's scope and texts not in the ledger are not mentioned at all). So no
    # «corpus, signed or not» total: the signed count above, and beside it the PRESENCE ONLY items of the CURRENT ledger
    # (named in the status record, an internal record, not published), whole, which the presence search reads but no absence line covers.
    cur = re.search(r"the ledger \(classes per item\) \| `(OCR-ABSENCE-LEDGER-[^`]+\.tsv)`",
                    open(os.path.join(G, "OCR-STATUS.md"), encoding="utf-8").read())
    if not cur:
        raise SystemExit("OCR-STATUS.md names no current ledger")
    pres = [x[0] for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(G, "ocr", "runs", cur.group(1)), encoding="utf-8"))
            if len(x) > 3 and not x[0].startswith("#") and x[3] == "PRESENCE ONLY"]
    pw_ = sum(sum((page_words(i) or {}).values()) for i in pres)
    print(f"PRESENCE ONLY ({cur.group(1)}): {len(pres)} items, {pw_:,} words (searched for presence; no absence line)")
    if a.items:
        its = [l.strip() for l in open(a.items, encoding="utf-8") if l.strip()]
        print(f"the round's {len(its)} items, whole, signed or not: "
              f"{sum(sum((page_words(i) or {}).values()) for i in its):,} words")


if __name__ == "__main__":
    main()
