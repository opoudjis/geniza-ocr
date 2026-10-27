#!/usr/bin/env python3
r"""ocr-ads-candidates — find the pages that are MUNDANE ADVERTISEMENTS, for the editor to rule on, title by title.

    tools/ocr-ads-candidates.py --ledger <tsv> --root <ocr-rendersearch> --out <new .md> [--min-score 6]

WHY (editor 2026-10-02 10:0x; failure map row 9). Ad layouts cut and garble names (G5 final: britaesperantisto 1911 n080 p.7). Mundane
advertisement pages are to become a named exception — but only after the editor has seen the candidates. This tool
EXCLUDES NOTHING: it writes a list.

HOW (text only, the page's search text). Per page, per 100 words:
- TRADE signals: an ads heading (Anoncoj, Reklamoj, Anonco, Annonces, Anzeigen, Advertisements), prices and currencies,
  trade verbs and nouns (liveras, vendas, aĉetu, firmo, magazeno, fabriko, hotelo, restoracio, telefono …), street
  addresses;
- BOOK signals: libro/libroj, eldonejo, librejo, eldonis, tradukis, verkis, gazeto, revuo, abonu/abono, presejo,
  Novaj libroj …
A page is a candidate when TRADE ≥ --min-score and BOOK < TRADE / 3. Items in ADMISSIBLE, SPECIAL HANDLING and WITH
EXCEPTIONS only (the classes where absence claims are made). Output: per title, the candidate pages with their scores and
the first words of each, most-scored first. WRITE-SET: --out only (must not exist).
"""
import os, re, sys, csv, argparse, collections

# FRENCH AND DUTCH added 2026-10-11 (the editor, cupel8 C11: «can it pls add words in the major langs of publication in our
# corpus, dutch and french here?»): La Belga Sonorilo's ads are mostly French or Dutch; the Esperanto-only lists found 0 of
# its 2,323 pages. Each list gains the French and Dutch words for the same thing; the test itself is unchanged.
TRADE = re.compile(r"\b(anoncoj?|reklamoj?|annonces?|anzeigen?|advertisements?|prezo|prezoj|frankoj?|fr\.|ŝil\.|ŝilingoj?|"
                   r"pencoj?|markoj?|mk\.|rubloj?|kopekoj?|kr\.|liveras|vendas|vendejo|aĉetu|aĉetas|firmo|magazeno|"
                   r"fabriko|fabrikejo|hotelo|restoracio|telefono|tel\.|garantiita|rabato|katalogo|senpage|kvalito|"
                   r"réclames?|prix|francs?|centimes?|vend|vendons|vente|livraison|maison|magasins?|fabrique|fabricant|hôtel|"
                   r"restaurant|téléphone|garanti|garantie|catalogue|qualité|marchand|négociant|"
                   r"advertenties?|prijs|prijzen|gulden|guldens|fl\.|verkoop|verkrijgbaar|winkel|magazijn|fabriek|telefoon|"
                   r"gewaarborgd|catalogus|kwaliteit|koopman)\b|[£$€]\s?\d", re.I)
# PRICE and SELL must both be present: commerce, not a list of names with addresses (first pass 10:05: street words made
# the 1905 congress lists «ads» — the opposite of what may be excluded)
PRICE = re.compile(r"\b(prezo|prezoj|frankoj?|fr\.|ŝil\.|ŝilingoj?|pencoj?|markoj?|mk\.|rubloj?|kopekoj?|kr\.|guldenoj?|"
                   r"prix|francs?|centimes?|prijs|prijzen|gulden|guldens|fl\.|cents?)\b|[£$€]\s?\d", re.I)
SELL = re.compile(r"\b(liveras|vendas|vendejo|aĉetu|aĉetas|firmo|magazeno|fabriko|fabrikejo|hotelo|restoracio|rabato|garantiita|katalogo|"
                  r"vend|vendons|vente|maison|magasins?|fabrique|fabricant|hôtel|restaurant|garanti|garantie|catalogue|marchand|"
                  r"négociant|verkoop|verkrijgbaar|winkel|magazijn|fabriek|gewaarborgd|catalogus|koopman)\b", re.I)
HON = re.compile(r"\b(s-ro|sro|s-ino|sino|f-ino|fino|d-ro|dro|mr|mrs|miss|mme|mlle|mm|herr|frau|hr|fr|dhr|mevr|mej|m)\.?(?=\s)", re.I)
BOOK = re.compile(r"\b(libro|libroj|libron|librojn|eldonejo|librejo|eldonis|eldono|tradukis|traduko|verkis|verko|verkoj|"
                  r"gazeto|gazetoj|revuo|abonu|abono|abonantoj|presejo|vortaro|lernolibro|novaj libroj|poemoj|romano|"
                  r"livres?|librairie|éditeur|édition|revue|journal|abonnement|dictionnaire|manuel|"
                  r"boek|boeken|boekhandel|uitgever|uitgave|tijdschrift|woordenboek|leerboek)\b", re.I)


def pages(path):
    if not os.path.exists(path): return {}
    t = open(path, encoding="utf-8", errors="ignore").read()
    p = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return {int(a): b for a, b in zip(p[1::2], p[2::2])}


def title_of(c):
    return re.sub(r"[._-]?\d{4}.*$", "", c) or c


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ledger", required=True); ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--min-score", type=float, default=6)
    ap.add_argument("--covers-only", action="store_true", help="only the first 2 and last 3 pages of each item")
    ap.add_argument("--max-hon", type=float, default=2.0, help="honorifics per 100 words above which a page is a name list")
    ap.add_argument("--min-sell", type=int, default=2)
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists")
    L = [l for l in open(a.ledger, encoding="utf-8") if not l.startswith("#")]
    live = [r["corpus"] for r in csv.DictReader(L, delimiter="\t") if r["class"] in ("ABSENCE-ADMISSIBLE", "SPECIAL HANDLING", "WITH EXCEPTIONS")]
    by = collections.defaultdict(list); scanned = 0
    for c in live:
        pg_all = pages(os.path.join(a.root, c + ".txt"))
        for p, t in pg_all.items():
            w = len(t.split())
            if w < 30: continue
            scanned += 1
            tr = 100 * len(TRADE.findall(t)) / w; bk = 100 * len(BOOK.findall(t)) / w
            n_pg = len(pg_all)
            cover = p <= 2 or p > n_pg - 3   # the editor: ads are predictable, on the inside covers
            if a.covers_only and not cover: continue
            hon = 100 * len(HON.findall(t)) / w   # a NAME LIST is not an ad (2 Oct: Brita Esperantisto's wrapper carries the affiliated-societies lists)
            if tr >= a.min_score and bk < tr / 3 and hon < a.max_hon and len(SELL.findall(t)) >= a.min_sell and PRICE.search(t):
                by[title_of(c)].append((tr, bk, c, p, " ".join(t.split())[:140]))
    n = sum(len(v) for v in by.values())
    o = [f"# Advertisement-page candidates — for the editor's ruling", "",
         f"`[GENERATED by tools/ocr-ads-candidates.py from {os.path.basename(a.ledger)}; text only; EXCLUDES NOTHING. The editor 2026-10-02 10:0x: mundane advertisements only, not announcements of books by well-known Esperantists. Pages scanned: {scanned}; candidates: {n} in {len(by)} titles (trade score ≥ {a.min_score} per 100 words, book score under a third of it).]`", "",
         "| title | candidate pages | example (item, page, trade/book per 100 words, first words) |", "|---|---:|---|"]
    for ti, v in sorted(by.items(), key=lambda x: -len(x[1])):
        v.sort(key=lambda x: -x[0]); tr, bk, c, p, head = v[0]
        o.append(f"| {ti} | {len(v)} | {c} p.{p} ({tr:.0f}/{bk:.0f}): {head.replace('|', '¦')} |")
    o += ["", "## All candidates, by title", ""]
    for ti, v in sorted(by.items(), key=lambda x: -len(x[1])):
        o.append(f"### {ti} ({len(v)})"); o.append("")
        for tr, bk, c, p, head in v: o.append(f"- {c} p.{p} — {tr:.0f}/{bk:.0f} — {head.replace('|', '¦')}")
        o.append("")
    open(a.out, "x", encoding="utf-8").write("\n".join(o) + "\n")
    print(f"{scanned} pages scanned; {n} candidates in {len(by)} titles → {a.out}")


if __name__ == "__main__":
    main()
