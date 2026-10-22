#!/usr/bin/env python3
"""ocr-modern-metadata.py — which pages (or, in a born-digital text, which ¶) are a later hand's metadata, not the work.

    python3 tools/ocr-modern-metadata.py --out geniza/ocr/runs/OCR-MODERN-METADATA-<date>.tsv

WHY (2026-10-10; at 05:4x the editor asked that the dowse be confirmed to do the same for the initial ÖNB metadata in
journal PDFs, modern initial metadata being a recurring thing and each source possibly differing in its extent, and
approved going ahead on the proposal). The test dowse of Esenco (Tekstaro) found Ludovikito and Nylén «present» in the 1898 text: both were in
the Tekstaro's own header. Every ÖNB scan opens with a cover sheet, and the dowse searched it like a page. A name in
such metadata is a modern catalogue's or digitiser's, not the source's: tools/ocr-dowse.py reads this table, keeps
those hits apart, and leaves those pages out of the reading and of silences.

WHAT, each source by its own markers, its extent measured in the item (never assumed):
- «ÖNB cover sheet»: a page among an item's first 3 and last 2 holding at least two of the ÖNB sheet's field words
  (Nationalbibliothek, Zitierlink, Signatur:, Umfang:, data.onb, Ort:, Jahr:): one word alone may be running text.
- «Google front matter»: a page with Google's preface («digital copy of a book», «Google Book Search»); the
  «Digitized by Google» footer on a page of text is a line, not a metadata page, and is left.
- «archive.org stamp»: a page among the first 3 and last 2 with «Internet Archive» or «archive.org» and «Digitized».
- «Tekstaro header» (born-digital): ¶ 2 to the block «Kreis la Esperantan tekston: …», which ends every Tekstaro header
  read on 2026-10-10, then any field or note lines after it up to the next heading or body text; where a text has no
  «Kreis» block, the run of title headings and the Tekstaro's own field lines (Verkis:, Eldonado:, «La bazan tekston …»)
  from ¶ 2 to the first block that is neither. ¶ 1, the work's title, is kept as text.
- «BHS reissuer's note» (born-digital): the Biblioteko Hippolyte Sebert's (arkivo.esperanto-france.org) own captions,
  introductions, page navigation and dated notes inside its typed reissues of period documents. They have no common
  marker the converter can see (the «Jen elektronika reeldono» note is one of several forms), so each stretch was read
  and is listed in BHS below (2026-10-10 18:2x, asked for by the born-digital list's notes). Two bhs- items are the
  library's own writing throughout (the Boulogne 1905 essay of 2015, the description of a 1910 membership card): they
  are dated as modern texts in tools/ocr-item-dates.py, not blanked here.
Library ownership stamps are NOT metadata in this sense: they belong to the copy, often of the period.

Searches the search texts (sources/ocr-rendersearch/<item>.txt) and the born-digital texts of the signed and proposed
lists. WRITE-SET: --out only (refuses an existing file). Re-run after a re-read or a new list.
"""
import argparse, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ocr_index as IX  # noqa: E402
import born_digital_lines as BDL  # noqa: E402

G = BDL.G
S = os.path.join(G, "sources")
ONB = [re.compile(x, re.I | re.M) for x in (r"Nationalbibliothek", r"Zitierlink", r"Signatur\s*:", r"Umfang\s*:",
                                              r"data\.onb", r"^\s*Ort\s*:", r"^\s*Jahr\s*:")]
GOOGLE = re.compile(r"digital copy of a book|Google Book Search|books\.google", re.I)
ARCH = re.compile(r"(Internet Archive|archive\.org)", re.I)
DIGI = re.compile(r"digiti[sz]ed", re.I)
TEK_FIELD = re.compile(r"^(Verkis|El|Eldono|Eldonado|Grandeco|Paĝoj?|Numero|Proksimuma verkojaro[^:]{0,20}|Kreis la Esperantan "
                       r"tekston|Tradukis|Redaktis|Editoris|Ilustris|Prilaboris|Kompilis)\s*:|^(La bazan tekston|La tekston|"
                       r"La skanitajn tekstobildojn|La origina teksto enhavas|En tiu ĉi (verko|versio)|Tiu ĉi kolekto|"
                       r"Ĉi tiu kolekto|Aperas ĉi tie|Laŭ la Fundamenta Krestomatio|Verŝajne verkita|(Ĉi tiu|Tiu ĉi|Tio ĉi) (elektronika )?"
                       r"versio|Tio ĉi estas nur|La lasta parto de la teksto)")


def scanned(item, path):
    pg = IX.pages(open(path, encoding="utf-8", errors="ignore").read())
    if not pg:
        return []
    look = pg[:3] + [x for x in pg[-2:] if x not in pg[:3]]
    out = []
    for p, t in look:
        k = sum(1 for rx in ONB if rx.search(t))
        if k >= 2:
            out.append((p, "ÖNB cover sheet", f"{k} ÖNB field words"))
        elif ARCH.search(t) and DIGI.search(t):
            out.append((p, "archive.org stamp", "«Internet Archive/archive.org» with «digitized»"))
    for p, t in pg:
        if GOOGLE.search(t):
            out.append((p, "Google front matter", "Google's preface"))
    return out


def tekstaro(row):
    bl = BDL.blocks(open(BDL.text_path(row), encoding="utf-8").read())
    # the header ends at «Kreis la Esperantan tekston: …» (every Tekstaro header read on 2026-10-10 has it; free notes,
    # «Aperis unue en …», «Enestas ĉi tie …», source lists, may come before it), then runs on through field or note lines
    kre = next((n for n, _, t in bl[:80] if t.startswith("Kreis la Esperantan tekston")), None)
    if kre:
        run = [n for n, _, _ in bl if 1 < n <= kre]
        head = next((n for n, _, t in bl if n > kre and t.startswith("=== section")), None)
        if head and head - kre <= 8:   # the Tekstaro's notes after «Kreis», up to the work's first heading
            run += [n for n, _, _ in bl if kre < n < head]
        else:
            for n, sec, t in bl:
                if n <= kre: continue
                if t.startswith("=== section") or not TEK_FIELD.match(t): break
                run.append(n)
        return [(n, "Tekstaro header", "¶ 2 to «Kreis la Esperantan tekston» and the notes after it") for n in run]
    run, seen_field = [], False
    for n, sec, t in bl:
        if t.startswith("=== section"):
            if seen_field:
                break
            run.append(n); continue
        if TEK_FIELD.match(t):
            run.append(n); seen_field = True; continue
        # a short continuation of a field line (Esenco ¶ 4 «de la lingvo Esperanto», after «El: Fundamenta Krestomatio»)
        nxt = next((b for b in bl if b[0] == n + 1), None)
        if seen_field and len(t.split()) <= 6 and nxt and TEK_FIELD.match(nxt[2]):
            run.append(n); continue
        break
    run = [n for n in run if n > 1] if seen_field else []   # ¶ 1, the work's title heading, is kept as text
    return [(n, "Tekstaro header", "the Tekstaro's own field lines and notes") for n in run]


# item → [(first ¶, last ¶, the first ¶'s opening words, what it is)]; read 2026-10-10 in the texts of the signed web-saves list.
# The opening words are checked: a stretch whose first ¶ no longer starts so (the text re-converted) is reported, not marked.
BHS = {
    "bhs-internacia-muzeo": [(4, 17, "Prezento (1/5", "the library's page navigation and its presentation «Iometa antaŭlega "
                                                      "prezento, post cent jaroj» («Jen elektronika reeldono …»)")],
    "bhs-bulonjo-1905-zamenhof-portretoj": [(1, 6, "Lazaro Zamenhof, elpensinto", "the library's introduction and list of articles"),
                                            (90, 91, "[ 1 ] [Noto de 2015", "the library's notes «Noto de 2015», «Noto komplementa»"),
                                            (218, 219, "El la \"Ora Libro\"", "the library's caption of the PES Ora libro")],
    "bhs-bourlet-biografio-1914": [(2, 2, "Montri pli larĝan portreton", "the site's link to a larger portrait")],
    "bhs-bulonjo-1905-fruictier-raporto": [(1, 2, "Fotaĵo de la kovra paĝo", "the library's captions")],
    "bhs-eco-raporto-unua-kongreso": [(1, 2, "Fotaĵo de la kovra paĝo", "the library's captions")],
    "bhs-pri-aymonier": [(2, 4, "Jen unu malnova foto", "the library's introduction, its caption naming the people in a "
                                                        "photograph of 12 November 1911, and its source line")],
    "bhs-pri-deligny": [(2, 3, "Jen malnovaj artikoloj", "the library's introduction and source note")],
    "bhs-zamenhof-vizito-centra-oficejo": [(3, 4, "En artikolo de S-ino E. Ferter-Cense", "the library's framing and photo caption"),
                                           (6, 6, "La Oran libron ni ankaŭ trovis", "the library's framing")],
    "bhs-zamenhof-morto-1917-gazetaro": [(2, 2, "Voici une liste d'articles", "the library's introduction")],
    "bhs-vekigho-balkana-milito": [(81, 81, "[*] \"Ŝlosilo de Esperanto\"", "the library's footnote (it speaks of «ĝis la jaroj 1930»)")],
}


def bhs(item, row):
    bl = {n: t for n, _, t in BDL.blocks(open(BDL.text_path(row), encoding="utf-8").read())}
    out = []
    for a, b, start, what in BHS.get(item, []):
        if not bl.get(a, "").startswith(start):
            print(f"  {item}: ¶ {a} no longer starts «{start}»: stretch ¶ {a}–{b} NOT marked (re-read it)")
            continue
        out += [(n, "BHS reissuer's note", what) for n in range(a, b + 1) if n in bl]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    rows = []
    for f in sorted(glob.glob(os.path.join(S, "ocr-rendersearch", "*.txt"))):
        it = os.path.splitext(os.path.basename(f))[0]
        rows += [(it, "pdf", p, k, e) for p, k, e in scanned(it, f)]
    for it, r in sorted(BDL.lists("proposed").items()):
        rows += [(it, "¶", n, k, e) for n, k, e in tekstaro(r)]
        rows += [(it, "¶", n, k, e) for n, k, e in bhs(it, r)]
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("# GENERATED by tools/ocr-modern-metadata.py: pages (unit «pdf», PDF pages) and paragraphs (unit «¶», of a "
                 "born-digital text) that are a later hand's metadata, not the work; tools/ocr-dowse.py keeps their hits "
                 "apart and leaves them out of the reading and of silences. Do not hand-edit: re-run it.\n")
        fh.write("item\tunit\tpage\tkind\tevidence\n")
        for x in rows:
            fh.write("\t".join(str(v) for v in x) + "\n")
    from collections import Counter
    print(f"{len(rows)} rows, {len({r[0] for r in rows})} items → {a.out}; " +
          ", ".join(f"{k} {v}" for k, v in Counter(r[3] for r in rows).most_common()))


if __name__ == "__main__":
    main()
