#!/usr/bin/env python3
r"""kapis-share-tables — the finding tables for Kapis (BitArkivo): which issue each file is, and its printed pages.

    tools/kapis-share-tables.py --out published/heterophony-resources/correspondence/kapis/attachments-<date>-trovilo

WHY (queue item 29; OCR-CITABLE-HITS-PROPOSAL-2026-10-08.md, «Shared with Kapis»; the editor 2026-10-08).

WHAT (metadata only: no text, no page images; nothing internal):
  TROVILO-EROJ.tsv     the item table, one row per file that is Bitarkivo's or a POTENTIAL Bitarkivo holding (ÖNB,
                       archive.org, Lublin, Gallica), periodicals only, no books (the editor 2026-10-08), with a `holding` column saying which: title, BPEAPE number, volume, year, issue, month, day, date,
                       the label as filed, pagination, first page of text, origin (Bitarkivo's own file name and URL,
                       the archive.org identifier, ÖNB, Gallica). Our internal notes and local paths are left out.
  TROVILO-PAGHOJ.tsv   the page map, for those same files: file · PDF page · printed page (in the forms ruled 2026-10-08) · what it rests on.
  TROVILO-NUMEROJ.tsv  where each issue starts inside the ÖNB volume parts (Lingvo Internacia, La Revuo).
Read from the committed tables (geniza/OCR-ITEM-TABLE.tsv, geniza/ocr/runs/OCR-PAGE-MAP.tsv, …/OCR-ISSUE-STARTS.tsv).
WRITE-SET: the three files in --out, a NEW folder (refused if it exists). The Esperanto note beside them is written by
hand, not by this tool.
"""
import os, re, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")


def rows(path):
    head, out = None, []
    for l in open(path, encoding="utf-8"):
        if l.startswith("#"): continue
        x = l.rstrip("\n").split("\t")
        if head is None: head = x; continue
        out.append(dict(zip(head, x)))
    return out


def clean_origin(o):
    o = re.sub(r"\s*\((?:identifier list )?sources/[^)]*\)", "", o)      # our local paths
    o = re.sub(r"\s*\(the editor [^)]*\)", "", o)                       # our internal rulings
    o = re.sub(r",?\s*fetched by the editor \d{4}-\d\d-\d\d", "", o)          # who fetched, when
    o = re.sub(r"\s*\(\d{4}-\d\d-\d\d[^)]*\)", "", o)                     # a dated note quoting a ruling
    o = re.sub(r"\s*\(cupel\d+\)", "", o)                                    # our batch names
    o = re.sub(r"\s*\([\w./-]+\.md\b[^)]*\)", "", o)                       # a citation of our own files
    o = o.replace("downloaded issue by issue by the editor", "downloaded issue by issue")
    o = re.sub(r";\s*per-issue URLs not recorded", " (per-issue URLs not recorded)", o)
    return o.strip()


def holding(item, origin):
    """the editor 2026-10-08 → «BitArkivo», or a potential holding by source, or None (left out)."""
    o = origin.lower()
    if "bitarkivo" in o: return "BitArkivo"
    if "önb" in o or "anno" in o: return "potential: ÖNB"
    if item.startswith("dlibra.kul.pl."): return "potential: Lublin (KUL digital library, via archive.org)"
    if item.startswith("jbc.bj.uj.edu.pl."): return "potential: Jagiellonian Library (via archive.org)"
    if "archive.org" in o: return "potential: archive.org"
    if "gallica" in o: return "potential: Gallica"          # the editor
    return None


NAMED_PERIODICALS = re.compile(r"^(ANNO_e1e_|mondo\d{4}$|ido\.\d{4}|Ido_Saluto_|posta[-_]mundi[-_]|progreso\d)")


def periodical(r, runs):
    """the editor 2026-10-08. A journal: a BPEAPE number (not a congress BOOK), a named periodical outside
    BPEAPE (Helvetia, Mondo of Stockholm, the Ido papers, Posta Mundi, Progreso, whose volumes are filed progreso1,
    progreso3 … without a separator), or a title held as a run of two or more files. Anything else is a book."""
    if r.get("title", "").startswith("Kongresa Libro") or r.get("bpeape") in ("not a periodical", "not found"): return False
    if re.match(r"\d", r.get("bpeape", "")): return True
    if NAMED_PERIODICALS.match(r["item"]): return True
    if re.search(r"jarlibro|kalendaro|epigrami", r["item"], re.I): return False      # yearbooks, almanacs, books
    if r.get("issue") or r.get("volume") or re.search(r"_n\d|\.v\d|\.\d+$|\.(januaro|februaro|marto|aprilo|majo|junio|julio|augusto|septembro|oktobro|novembro|decembro)\b", r["item"], re.I):
        return True                                                                  # a single issue of a journal
    return runs.get(r.get("title_key", ""), 0) >= 2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: choose a new name")
    items = rows(os.path.join(G, "OCR-ITEM-TABLE.tsv"))
    pages = rows(os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv"))
    starts = rows(os.path.join(G, "ocr", "runs", "OCR-ISSUE-STARTS.tsv"))
    os.makedirs(a.out)
    cols = ["item", "holding", "title", "bpeape", "volume", "year", "issue", "month", "day", "date", "label_as_filed", "pagination",
            "first_text_page", "origin"]
    theirs = set()
    import collections
    runs = collections.Counter(r.get("title_key", "") for r in items)
    dropped_books = collections.Counter()
    with open(os.path.join(a.out, "TROVILO-EROJ.tsv"), "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in items:
            r = dict(r); r["origin"] = clean_origin(r.get("origin", ""))
            r["bpeape"] = re.sub(r"\s*\(.*", "", r.get("bpeape", ""))
            r["holding"] = holding(r["item"], r["origin"])
            if not r["holding"]: continue   # BitArkivo's and its potential holdings only (the editor 2026-10-08, twice)
            if not periodical(r, runs):
                dropped_books[r.get("title") or r["item"]] += 1; continue
            theirs.add(r["item"])
            f.write("\t".join(r.get(k, "") for k in cols) + "\n")
    n = 0
    with open(os.path.join(a.out, "TROVILO-PAGHOJ.tsv"), "w", encoding="utf-8") as f:
        f.write("item\tpdf_page\tprinted\tsource\n")
        for r in pages:
            if r["item"] in theirs:
                f.write(f"{r['item']}\t{r['pdf_page']}\t{r['printed_display']}\t{r['source']}\n"); n += 1
    with open(os.path.join(a.out, "TROVILO-NUMEROJ.tsv"), "w", encoding="utf-8") as f:
        f.write("title\tvolume_year\tissue\tfirst_printed\titem\tpdf_page\n")
        for r in starts:
            f.write(f"{r['title_key']}\t{r['volume_year']}\t{r['issue']}\t{r['first_printed']}\t{r['item']}\t{r['pdf_page']}\n")
    hc = collections.Counter(holding(r["item"], clean_origin(r.get("origin", ""))) for r in items if r["item"] in theirs)
    print(f"{len(theirs)} items (of {len(items)}): " + ", ".join(f"{k} {v}" for k, v in hc.most_common() if k)
          + f"; {n} pages; {len(starts)} issue starts → {a.out}")
    print(f"left out as books ({sum(dropped_books.values())}): " + "; ".join(f"{k} ×{v}" if v > 1 else k for k, v in dropped_books.most_common()))


if __name__ == "__main__":
    main()
