#!/usr/bin/env python3
r"""ocr-ads-distinct — advertisement-page candidates by the number of DIFFERENT selling words on a page (RUNBOOK.md C11).

    python3 tools/ocr-ads-distinct.py --root <$R> --items <batch-dir>/columns-items.json --out <batch-dir>/ADS-DISTINCT.tsv
        [--min 5] [--langs esperanto,german,…] [--specs <min>]

WHY (2026-10-18; on the editor's asking whether they could be done now, of what RUNBOOK.md listed as not built yet). `tools/ocr-ads-candidates.py`
tests a density of trade words and finds nothing where ads sit in long or garbled page texts (cupel8: 0 of 149;
docs/FAILURE-MAP.md R22), so C11 counts instead the DIFFERENT selling words per page, in the batch's languages, 5 or more whatever the
page's length. Done by hand at cupel8, 11, 13, 14 and 15; this is that count. Cupel15 (Volapük and German): 233 pages
with 5 or more, 53 with 8 or more, the editor ruling the look at 8.

WHAT: for each page of the items' current text (`<item>.txt`, «=== page N ===»), the selling words of the named languages
found on it (whole words, case-folded). Writes --out (refused if it exists): item, page, count, the words; prints how many
pages reach 5 … 10, so the cut can be put to the editor where the count is large. With --specs N it also prints the
render specs for the pages at N or more, shuffled with a fixed seed, for `tools/cupel-look-render.py ranges`
(`aNNN:<stem>:<page>-<page>:150`). WRITES only --out.
"""
import argparse, json, os, random, re, sys, unicodedata

SELL = {
    "esperanto": "prezo prezoj frankoj franko vendas vendejo aĉetu aĉetas librejo senpage rabato katalogo afranke liveras "
                 "firmo magazeno fabriko hotelo restoracio garantiita mendu mendo kostas",
    "volapuk": "selön selob selom selons selol selöl remön remolöd remolsöd suäm suämot suämots suämi mak maks lifab lifabs "
               "nunod nunods",
    "german": "preis preise mark pfennig pf kaufen verkaufen verkauf bestellen bestellung bestellungen abonnement buchhandlung "
              "buchhandlungen erhältlich liefert lieferung katalog gratis franko rabatt firma fabrik portofrei nachnahme fl kr",
    "french": "prix franc francs fr frs vente achat envoi franco catalogue librairie abonnement maison remise",
    "english": "price prices sale sold order orders free postage catalogue shilling shillings pence dollars cents",
    "dutch": "prijs verkrijgbaar gulden boekhandel franco",
    "italian": "prezzo lire vendita libreria",
    "spanish": "precio pesetas venta librería",
    "catalan": "preu pessetes venda llibreria",
    "polish": "cena koron kopiejek sprzedaż księgarnia",
}
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def pages(root, item):
    p = os.path.join(root, item + ".txt")
    t = open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p) else ""
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True); ap.add_argument("--items", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--min", type=int, default=5)
    ap.add_argument("--langs", default=",".join(SELL))
    ap.add_argument("--specs", type=int); ap.add_argument("--seed", type=int, default=181015)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    words = set()
    for l in a.langs.split(","):
        if l not in SELL:
            sys.exit(f"no selling words for {l}: {', '.join(SELL)}")
        words |= set(SELL[l].split())
    items = [unicodedata.normalize("NFC", i) for i in json.load(open(a.items, encoding="utf-8"))]
    rows = []
    for it in items:
        for n, t in pages(a.root, it).items():
            hit = {w.lower() for w in WORD.findall(t)} & words
            if len(hit) >= a.min:
                rows.append((it, n, len(hit), sorted(hit)))
    rows.sort(key=lambda r: (-r[2], r[0], r[1]))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("item\tpage\tcount\twords\n")
        f.writelines(f"{it}\t{n}\t{k}\t{' '.join(w)}\n" for it, n, k, w in rows)
    print(f"{len(rows)} pages in {len({r[0] for r in rows})} items with {a.min}+ different selling words → {a.out}")
    for k in range(a.min, a.min + 6):
        print(f"  {k}+: {sum(1 for r in rows if r[2] >= k)} pages, {len({r[0] for r in rows if r[2] >= k})} items")
    if a.specs:
        sel = [r for r in rows if r[2] >= a.specs]
        random.Random(a.seed).shuffle(sel)
        print(" ".join(f"a{i:03d}:{r[0]}:{r[1]}-{r[1]}:150" for i, r in enumerate(sel, 1)))


if __name__ == "__main__":
    main()
