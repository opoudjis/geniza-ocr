#!/usr/bin/env python3
r"""ocr-absence-ledger — WHICH CORPORA ADMIT WHICH FINDINGS. Generated from tool outputs only.

    tools/ocr-absence-ledger.py --gate <OCR-GATE-….md.json> --g1 <OCR-GATE-G1-….md.json> --out <stem>

WHY (the editor, 2026-09-27 14:32, found that track was not being kept, and that there should be
apparatus that keeps it). The first presence/absence classification was assembled by hand from files of different ages,
and overstated: it counted G1 as clean for corpora whose G1 result was four gates old or missing.
This tool derives it mechanically and REFUSES stale inputs.

THE RULE (restated from an internal record, 2026-09-24, not published; not changed): presence stands over any corpus;
an absence finding is admissible only over a corpus that passes all four gate checks and is handed
over with a signed ACCEPTED line. THIS TOOL SIGNS NOTHING (the editor ruled at 14:34 that nothing was
to be signed off yet); it says what could be signed and what stands in the way.

CLASSES
  ABSENCE-ADMISSIBLE      passes G2–G4 (the gate's own rule) and G1 is clean on the current text
  WITH EXCEPTIONS         the same, but named pages or scripts are excluded from absence findings:
                          MINOR G1 pages (≤ 3 lines of masthead/caption/date missing, image sort);
                          a LOST page with a residual gap; Russian (bi-script pages) and Georgian /
                          Armenian text — PRESENCE ONLY, the Esperanto text gated alone
                          (`ocr-accept.py --script-segregated`, editor 2026-09-27 14:40); or, for a
                          PART exception (BLOCK_NOT_READ), only the named block on the page: the rest of
                          the page stays in (approved by the editor, 2026-10-08 02:4x)
  PENDING                 no valid verdict yet: G1 pages UNTESTED, G1-flagged pages NOT YET SORTED by
                          the image check, or the text is newer than the gate / G1 result (STALE)
  PRESENCE ONLY           fails G4, too short to score, or unscoreable
Corpora in `geniza/OCR-NOT-CORPUS.tsv` (scaffolding) are not counted at all.

G1 PAGE VERDICTS come from the image sorts (`OCR-G1-SORT-*.md` + `OCR-G1-SORT-KEY-*.tsv`), matched
by (corpus, page). A LOST page is cleared by the editor's hand-keyed text (`page-NNNN.hand.txt` /
`.hand-add.txt`) or a ruled re-read listed as complete in RESOLVED_LOST below; otherwise it stays an
exception. A flagged page with no sort verdict is UNSORTED and makes the corpus PENDING.

CAVEATS carried from 2026-09-27: the Esperanto text of bi-script pages is gated on the strict clean
(`page-NNNN.eo-gate.txt`), which can understate but not flatter; an ABSENCE search must still run over
the FULL Esperanto text, never the clean files.

WRITES <out>.tsv (one row per corpus) and prints the tally.
"""
import os, re, sys, glob, json, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_text_languages as TL   # the language table (2026-10-03)
GENIZA = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
ROOT = os.path.join(GENIZA, "sources", "ocr-rendersearch")
# LOST pages re-read on the editor's rulings and found complete apart from ordinary OCR slips
# (an internal record, 2026-09-26, not published); the one with a residual gap is NOT listed here.
RESOLVED_LOST = {("C1 Capitanucci Carlevaro - Guida ragionata agli strumenti diagnostici e terapeutici ADC del disturbo da gioco d'azardo 2004", 160),
                 ("Danlando", 107), ("InternaciaMedicino.1911.1", 12), ("kongresa.libro.08", 93)}
# Corpora the editor ruled PRESENCE ONLY whatever their OCR (the editor ruled on 2026-09-27 that Posta Mundi be kept
# in, but presence only, as secondary).
PRESENCE_ONLY_DECLARED = re.compile(r"posta[-_ ]?mundi")
# Named items ruled PRESENCE ONLY, whatever their OCR; the ruling is the reason given, ahead of any gate
# failure, because the editor has ruled the failure not worth fixing.
PRESENCE_ONLY_NAMED = {
    # cupel18c C11: G5 failed on Internacia Scienca Revuo 1904 alone (8 of 40 contradicted, every LOST page this volume's:
    # its two columns read in alternating blocks); the editor 2026-10-27 13:1x «sign without revuo, then focus on gutter
    # cut, and have it address both ezri and revuo»: presence only until the gutter cut (run sheet C7c.2b) re-reads it and
    # G5 passes on it
    "InternaciaSciencaRevuo_1904": "held out of cupel18c's signature: G5 failed on its pages, its columns read out of order, until the gutter cut re-reads it (editor's ruling, 2026-10-27)",
    # cupel16 C13, rule 15 (ocr/runs/CUPEL16-RULE15-SECOND-COPIES-2026-10-20.md): temerov's 37-page extract of Couturat–Leau
    # 1903 (the Volapük chapter), wholly within archive.org's copy and no better read; the editor 2026-10-20 14:4x
    # cupel16 C13, rule 15: temerov's Dutch Volapükabled 1884–85, page for page the same run as ÖNB's `volapükabled`
    # (cupel15, signed), no gap of coverage or quality; the editor ruled on 2026-10-20 15:1x that ÖNB's be kept
    # cupel16, the doubles census (an internal record, 2026-10-20, not published): the Mittheilungen of the Vienna Volapük
    # society 1887 twice in temerov's scans, the same eight pages; kept: `mittheilungen_wwv_1887_brefik` (G4 84.0 against
    # 81.9); removal of the duplicate approved by the editor, 2026-10-20 15:3x
    # Künzli's Svisa Enciklopedio Planlingva (2006): two of his website's separate reposts of encyclopedia articles, each
    # wholly in the numbered series; the name test PASS (an internal record, 2026-10-20, not published); the
    # withdrawals approved by the editor, 2026-10-20 16:5x
    # Juna Esperantisto 1911 held twice: the 16-page run kept off whole, the 20-page run (juna.esperantisto.1911.*, with the
    # wrappers) kept; the name test finds every roster name of the 16-page run in the 20-page one (an internal record, 2026-10-20, not published);
    # the editor ruled on 2026-10-20 18:5x that the 16-page run be deleted, the one name difference being noise
    'JunaEsperantisto.1911.1': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.2': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.3': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.4': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.5': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.6': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.7': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.8-9': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.10': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.11': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    'JunaEsperantisto.1911.12': "a second copy kept off: the 16-page run of Juna Esperantisto 1911, within juna.esperantisto.1911.* (rule 15; editor's ruling, 2026-10-20)",
    # The name test's group A, the last four (an internal record, 2026-10-20, not published, A 1, 2, 11, 18: every page paired,
    # every roster name found on the matching pages of the copy kept); approved by the editor, 2026-10-20 19:1x
    "LaSunoHispana.1906.25": "a second copy kept off: within LaSunoHispana.1906.jarkolekto-27-28, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "li_defectes_inacceptabil_de_interlingua_gode.adoc._a4._screen": "a second copy kept off: the same text as li_defectes_inacceptabil_de_interlingua_gode.adoc._a4._print, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "A4 Juste Red Carlevaro - Idala foliumi 2019": "a second copy kept off: the same text as Idala foliumi, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "belgaesperantisto.idx": "a second copy kept off: the same text as BelgaEsperantisto_1909_Indekso, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "ENCYCL_ESPERANTO_C": "a second copy kept off: wholly within 13_ENCYCL_ESPERANTO_C-D-E, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "svisa_gazetaro": "a second copy kept off: the same text as 17_ENCYCL_ESPERANTO_G, the name test passed (rule 15; editor's ruling, 2026-10-20)",
    "mittheilungen_wwv_wien_1887": "a second copy kept off: page for page the same as mittheilungen_wwv_1887_brefik, no quality gap (rule 15; editor's ruling, 2026-10-20)",
    "vpabled_nedanik_haastert_1884-85": "a second copy kept off: page for page within volapükabled (ÖNB), no quality gap (rule 15; editor's ruling, 2026-10-20)",
    "couturat_leau_histoire_1903": "a second copy kept off: wholly within histoiredelalang00coutuoft, no quality gap (rule 15; editor's ruling, 2026-10-20)",
    "Diskuto pri 'garsono' en Progreso 1913-1914": "a second copy kept off: a one-page archive.org extract of the Garsono discussion, which progreso6 (PDF 653, printed VI p. 533) and progreso7 (PDF 135 and 240, printed VII pp. 99 and 204) hold whole (rule 15; the editor 2026-10-25, by Ezri: to be deleted)",
    # 2026-10-26, rule 15 (the editor; Ezri 11:2x «You can withdraw louiscouturat at cupel18b's chain»): the
    # OCR reading of ido-vivo's Word-made PDF of de Beaufront's Doktoro Louis Couturat (1923), now the signed born-digital
    # item beaufront-1923-doktoro-louis-couturat (its typed text; ocr/lines/BORN-DIGITAL-LINES-2026-10-26-SIGNED-beaufront-couturat.txt)
    "louiscouturat": "a second copy kept off: the OCR reading of a typed PDF whose own text is the signed born-digital item beaufront-1923-doktoro-louis-couturat (rule 15; the editor 2026-10-26)",
    "EsperantoRuslando.1905.sennumera":"a second copy kept off: page for page the same issue (N-ro 1–2, January 1905) as EsperantoRuslando.1905.1-2, which reads better on every page, Esperanto and Russian (rule 15; editor's ruling, 2026-10-24)",
    # editor 2026-09-28 01:06: «we don't need dictionaries for the prosopography. deem these secondary,
    # not pressing to fix these at all.»
    "matematikal": "secondary — a two-language dictionary (editor's ruling, 2026-09-28)",
    "rusalibrovortaro": "secondary — a two-language dictionary (editor's ruling, 2026-09-28)",
    "ukraina": "secondary — a two-language dictionary (editor's ruling, 2026-09-28)",
    # the editor ruled on 2026-09-28 08:55 that korokanti, a songbook, be presence only (Ido; fails its list bar as Ido, 59.4)
    "korokanti": "secondary — an Ido songbook (editor's ruling, 2026-09-28)",
    # the editor ruled on 2026-09-28 17:27 that it is irrelevant to the venture and be moved to secondary (Selimi, Tirana 2004)
    "Albana_Esperanto-lernolibro_2004": "secondary — irrelevant to the venture (editor's ruling, 2026-09-28)",
    # the editor ruled on 2026-09-28 17:28 that Sundiala be secondary (Ido devotional readings, undated)
    "sundiala": "secondary — Ido devotional readings (editor's ruling, 2026-09-28)",
    # the editor ruled on 2026-09-28 17:29 that latviana is secondary, only its intro page being of any relevance, as a
    # potted history that says very little
    # the editor approved secondary for these, 2026-09-28 17:38
    "vivo": "secondary — a modern Ido life of Jesus in pictures, 2004 (editor's ruling, 2026-09-28)",
    "nordamuziko": "secondary — a modern Ido poem (Glebo Malcev, Kiev 2004) (editor's ruling, 2026-09-28)",
    "latviana":"secondary — a 1966 Latvian Ido course; only its intro page (a brief potted history) relevant (editor's ruling, 2026-09-28)",
    # the editor recalled on 2026-09-28 01:06 that the Greek had already been given up (Greek nuked 2026-09-27 16:22)
    "HelenaEsperantisto.1947.143": "Greek text — presence only (editor's ruling, 2026-09-27/28)",
    # on 1947.142 (Greek, like 1947.143), approved by the editor, 2026-09-28 17:23
    "HelenaEsperantisto.1947.142": "Greek text — presence only (editor's ruling, 2026-09-27/28)",
    # the editor, 2026-10-07 09:51 (signing cupel4), ruled that the copy with no pages missing replace the ÖNB copy; at 10:0x
    # chose to replace outright, not keep both; then ruled that the ÖNB copy not be removed, as it may have been cited, but
    # only withdrawn: the ÖNB scan stays in the corpus, its signed line withdrawn (ocr-acceptance-lines.py --withdraw)
    "LEsperantiste.1907.5": "superseded by the complete Gallica copy LEsperantiste.1907.5.1 (this ÖNB scan lacks printed pp. 110–111); kept, as it may have been cited, its signed line withdrawn (editor's ruling, 2026-10-07)",
    # the editor 2026-10-07 13:5x on the 7 unclear leads chose (a) (a second copy first, then replace, as for May 1907); 19:01 signed
    # the ÖNB copy (cupel5); 19:5x approved ruling this archive.org copy presence only and withdrawing its line
    "Esperanto-UEA_1912_n136_dec20": "superseded by the complete ÖNB copy Esperanto-UEA_1912_n136_dec20.1 (this archive.org scan ends at printed p. 352, lacking pp. 353–356); kept, as it may have been cited, its signed line withdrawn (editor's ruling, 2026-10-07)",
}
RESIDUAL_LOST = {("oficiala_aldono_4a", 1): "«PARIS» lost, edge speckle"}
# FALSE BI-SCRIPT MARKS: pages the Russian pass marked bi-script that carry NO Russian on the image. The mark is ignored
# (the page's files are left in place). Each entry is a page someone has seen; none is inferred from a word count.
FALSE_BISCRIPT = {
    # the editor ruled on 2026-10-01 00:44 that there is no Russian in Mondo, the mark coming from poor-quality OCR, having
    # seen the page directly — p.7, an Ido page (the cover), Roman script throughout; the editor saw it
    # 2026-09-30 and found p. 7 perfectly legible and wholly in Roman script
    ("mondo1924", 7): "Ido cover, Roman script; the Russian model read it as junk Cyrillic",
    # approved by the editor, 2026-10-01 00:45 (E-D by image, scoped to the marked pages only): blind script check of
    # the 25 marked pages (an internal record, 2026-10-01, not published; batches z01–z05). SCRIPT NONE on these
    # 11; the other 14 (13 La Ondo mastheads, the 2020 book's Unua Libro facsimile) DO carry Russian and keep their mark.
    ("mondo1925", 71): "Ido cover, Latin script only",
    ("mondo1925", 78): "Ido congress programme and list, Latin script only",
    ("BK-I-GhP-2014-09-28", 19): "contents page, Latin script only",
    ("EO Adam Zakrzewski - Esperanta-Pola kaj Esperanta-Litova bibliografio 1887-1912", 69): "Polish name index, Latin script only",
    ("Omagxe-2", 43): "bibliography entries, Latin script only",
    ("Omagxe-3", 130): "romanised haiku list, Latin script only",
    ("VochoDeKuracistoj.1909.11", 14): "full-page advertisement, Latin script only",
    ("jbc.bj.uj.edu.pl.NDIGCZAS043693_1910_011_012", 9): "sheet music, Latin script only",
    ("46083", 1): "cover of Pola Esperantisto 1959, Latin script only",
    ("46083", 20): "sheet music, Latin script only",
    # E3 of the review (editor 2026-10-01 11:5x–13:2x): the «Russian» on these pages is Latin text read as Cyrillic
    # («Езрегапіа» = Esperanta); the real text is in search (congress pp. 22, 57 and Progreso p. 743 transcribed by vision,
    # batch y01). IpI 71 p.38 carries one real Cyrillic place name (Ростов-на-Дону), treated as incidental (the editor
    # accepted the verdict). The 2020 book's p.40 is real Russian, but a facsimile ILLUSTRATION of the 1887 Unua Libro: the
    # editor ruled it an illustration, not a legitimate exception.
    ("71", 38): "contents list, Latin read as Cyrillic; one Cyrillic place name, incidental",
    ("kongresa.libro.14", 22): "photo page with captions (vision y01)", ("kongresa.libro.14", 55): "travel notes, Latin",
    ("kongresa.libro.14", 57): "programme table printed sideways (vision y01)", ("kongresa.libro.14", 108): "UEA statistics, Latin",
    ("Progreso_-_2a_yaro", 496): "Ido prose", ("Progreso_-_2a_yaro", 497): "Ido prose",
    ("Progreso_-_2a_yaro", 743): "grammatical table printed sideways (vision y01)", ("Progreso_-_2a_yaro", 961): "Ido prose",
    # the editor confirmed on 2026-10-01 14:2x that Estlanda 1908.6 has no Cyrillic, only Estonian fraktur; the vision
    # transcription of p.8 (batch k04) is 562 words of Esperanto prose with no Cyrillic
    ("EstlandaEsperantisto.1908.6", 8): "Esperanto prose with Estonian fraktur; no Cyrillic (editor; vision k04)",
    ("dokumen.pub_esperanto-and-languages-of-internationalism-in-revolutionary-russia-2020055613-2020055614-9781350160651-"
     "9781350160668-9781350160675-1350160652", 40): "facsimile of the 1887 Unua Libro: an illustration (editor's ruling)",
}
# NAME LISTS ARE JUDGED BY A NAME CHECK ON THE IMAGES, NOT BY G4 (approved by the editor, 2026-10-01 00:02; the editor had
# proposed on 2026-09-30 23:3x that name lists not be subject to G5 now — the test holding them back was G4). G4 counts real words,
# and names and addresses are not in the word lists, so a well-read roster fails it. An item listed here passed the check
# of an internal record (2026-10-01, not published): every text page's image compared with its search text by a blind checker,
# the names marked unfindable re-run through tools/ocr-name-search.py, and every empty page seen on the image
# (vision batches q01–q10: all blank). A G4 fail is then cleared; any other reason still counts.
NAMELIST_CHECKED = {
    # cupel18b, Tutmonda Jarlibro Esperantista 1904–1909, directories of Esperantists and societies, PRESENCE ONLY on G4
    # alone (54–61); the editor 2026-10-26 16:5x (C10: whole-item PRIMARY, lines if C11's name check clears
    # them): a G5 of their pages on name recall (sources/cupel-batch-18b/g5-lists/, seed 2610262, class ledger-presence-g4):
    # 40 pages, 0 contradicted, 383/385 names found, none LOST
    "ANNO_e4d_19040005": "the yearbook's directories (1904); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 19/20 on this volume's 2 pages",
    "ANNO_e4d_19050005": "the yearbook's directories (1905); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 70/70 on this volume's 7 pages",
    "ANNO_e4d_19060005": "the yearbook's directories (1906); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 110/111 on this volume's 12 pages",
    "ANNO_e4d_19070005": "the yearbook's directories (1907); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 130/130 on this volume's 13 pages",
    "ANNO_e4d_19080005": "the yearbook's directories (1908); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 14/14 on this volume's 2 pages",
    "ANNO_e4d_19090005": "the yearbook's directories (1909); G5 on name recall 2026-10-26: 383/385 names found over 1904–1909, 40/40 on this volume's 4 pages",
    # cupel18a, Svisa Espero's December issues with the society's members' list (the editor 2026-10-24 15:1x: «we have precedent
    # for admitting name lists on name recall, right. ok»): a G5 of their pages on name recall
    # (sources/cupel-batch-18a/g5-lists/, seed 2410244, class ledger-presence-g4): 40 pages, 0 contradicted, 369/369 names found
    "ANNO_e5a_19060112": "the S. E. S. members' list (1906, 277 lines in Esperanto form); G5 on name recall 2026-10-24: 369/369 names found over both issues",
    "ANNO_e5a_19070112": "the S. E. S. members' list (1907, in French form); G5 on name recall 2026-10-24: 369/369 names found over both issues",
    "Nomaro de la kongresanoj 1905": "631 names on 33 text pages, 1 unfindable (p.7 «M. Fichot (Auxerre)»); 32 empty pages blank",
    "Adresaro de la kongresanoj en Boulogne-sur-Mer 1905": "365 names on 20 text pages, 0 unfindable by the search; empty pages blank",
    # approved by the editor, 2026-10-01 00:28, for the three below (checks recorded in an internal record, 2026-09-30, not published;
    # batches u01–u05, m02–m03)
    "44_ENCYCL_NOMINDEKSO": "about 552 names on 13 pages, all findable",
    "Adresaro de UK-anoj 1905": "about 723 names on 8 text pages (p.11 read by vision, low confidence), 2 unfindable of 3 flagged "
                                "(p.12 «Hayes C F»; p.15 «Reddon», «Secrétinat»); empty pages blank",
    "Lingvo Internacia 1901.5": "about 300 names on 7 pages, 2 unfindable (p.1 «Isaac Mautner», «L. Dudicourt»: split by junk from "
                                "the other column); p.1 sent to vision 2026-10-01",
    # approved by the editor, 2026-10-01 00:41: the La Revuo title and contents pages. Their OCR lost the small-capitals names
    # (checks m01–m02, w01–w05: about 1,170 names, 55 flagged); every page was then TRANSCRIBED by vision (x01–x07),
    # and all 55 lost names are found in the transcriptions by tools/ocr-name-search.py.
    "larevuo.1908.0": "contents page transcribed by vision; lost names found in the transcription",
    "larevuo.1908.0.1": "4 contents pages transcribed by vision; lost names found in the transcription",
    "larevuo.1911.0": "title page transcribed by vision; lost names found in the transcription",
    "larevuo.1912.0.2": "25 pages transcribed by vision; 33 of 33 lost names found in the transcription",
    "larevuo.1913.0": "2 contents pages transcribed by vision; lost names found in the transcription",
}
# 2026-09-29: covers of The Esperantist 1903–04 whose small type (contents, the Hon. Secs.' names and addresses, the
# correspondence register) the SOURCE SCAN does not resolve: 150 ppi, dark. Vision at 200 dpi and lightened 3x tiles
# both read under a tenth of it (an internal record, 2026-09-29, not published; vision6). A source-quality loss, not an
# OCR one: only a better scan can close it.
# 12 of the 14 were then closed from the Bitarkivo epub transcriptions of the same issues (made from Google's scans):
# the cover matter or advertisement segment filed as the page text. Two have no epub counterpart
# (p.50, a vol. I no. 2–3 page; p.495, a late-1905 advertisement page) and stay, as the editor ruled (ads and contents
# pages may be given up on, and treated as exceptions).
for _p in (50, 495):
    RESIDUAL_LOST[("TheEsperantist.1903-1904.v1", _p)] = "advertisements; small type unreadable in the source scan (150 ppi, dark), no epub counterpart"

# 2026-09-30: PRINTED PAGES NOT IN THE SCAN AT ALL — found by the page-number check and confirmed by a look at the
# neighbouring pages (text visibly interrupted across the gap). Not a lost scan page, so not in RESIDUAL_LOST: the page
# was never scanned. The source of record, with the second-copy check for each, is an internal register (not published), § 2
# (and the look itself: an internal record, 2026-09-29, not published). Omitted blank backs are NOT listed
# (nothing lost, the editor's rule); whole missing issues are series-level gaps, recorded in the register, not here.
NOT_IN_SCAN = {
    "LEsperantiste.1907.5": "printed pp. 110–111 (= 370–371) not in the scan; the text breaks off across the gap; the second copy is LEsperantiste.1907.5.1 (Gallica, complete; decided by the editor, 2026-10-07)",
    "RuslandaEsperantisto1907.5-6": "printed pp. 16–17 not in the scan (the country news jumps from Lapland to Finland); Bitarkivo's scan no longer on archive.org",
    "bohemaesperantisto_1909_j03_n07_apr": "printed pp. 107–116 (end of III,7 and start of III,8) and 127–128 not in the scan; no second copy (ANNO 1909 is Oct–Dec only)",
    "bohemaesperantisto_1909_j03_n08_maj": "printed pp. 127–128 not in the scan (this file holds the same III,8 pages as …n07_apr); no second copy",
    "britaesperantisto_1911_n080_aug": "printed p. 155 not in the scan; the ANNO copy lacks the same leaf",
    "polonalernolibro": "printed pp. 19, 33, 35 not in the scan (the exercise pages ĆWICZENIE 6, 13, 14)",
    "AmerikaEsperantisto_1908_v03_n05_jun": "printed pp. 87–88 not in the scan — text or a plate, unclear; no second copy (ANNO goes May → July 1908)",
    # the editor ruled on 2026-10-09 12:4x that once the two witnesses are found between them to cover the entire text at absence
    # quality, absence in them counts as absence of the entire item (confirmed: absence across the two together); all 3 approved
    "338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat": "vol. 2 printed pp. 44–45 (after PDF page 74) and 80–81 (after PDF page 91) not in the scan; PDF pages 51–63 repeat 38–50; the second witness of vol. 2, privat-historio-1927-vol2 (signed cupel6), holds them",
    # cupel10, the editor 2026-10-13 13:1x approved the check and options (a) and (c) (the neighbour look: the text runs on across the gap in
    # every column; the REU ZIP holds the same 23 images; no Espero 1908 in BitArkivo's export of 2026-10-09 or ANNO's lists)
    "poemo_pri_la_militiro_de_igor_1908": "printed p. 4 not in the scan (the end of the introduction, the list of the poem's translations, and part of the poem); no second copy found; scope at C10 to the pages that survive",
    # cupel10, the editor 2026-10-13 13:2x judged it a missing scan and chose (a) and (c): 23 images for 24 attested pages (the last page
    # printed 24, with the imprint); p. 11 is the front of the leaf whose back, p. 12, is in the scan
    "esperantista_movado_1921_n_1_2": "printed p. 11 not in the scan (a missing scan, probably town news: 23 images for 24 attested pages; p. 10 ends «На Дону», p. 12 opens «По Сибири.»); no second copy (REU only; BitArkivo lists the title with no issues)",
    # cupel10, the editor 2026-10-13 13:3x approved (b) then (a): p. 15 seen at full resolution
    "esperantista_movado_1920_n_2": "printed p. 16, the issue's last page, not in the scan (15 images; n-roj 1 and 3 have 16; p. 15's right column breaks off mid-sentence, «Celo au' helpilo?»: «…Por ili Esperanto», and no printer's line); no second copy (REU only)",
    # cupel10, the editor 2026-10-13 13:3x chose (a)
    # cupel15, approved by the editor 2026-10-17 22:0x (the neighbour look, an internal record, 2026-10-17, not published, L06):
    # p. 91 ends a piece, p. 168 opens mid-story; the reader cannot tell how much is missing (pp. 90–91 an English lesson series)
    "volaspodelamont00unkngoog": "printed pp. between 91 and 168 not in the scan (PDF 72 = p. 91 ends a piece; PDF 73 = p. 168 opens mid-story, the end of a piece signed «E. D. FRENCH.»; how many pages, the look cannot tell); whole issues absent too, recorded in LACUNAE.tsv (Yelüp 3 Nüm 2; Nüm 5 likely); temerov's volaspodel_y3_1892-93 and _y4_1893-94 to be matched at cupel16's C0",
    "informilo_c_k_seu__1926_27__nn9_12": "printed pp. 367–368 (one leaf) not in the scan, text or blank unclear (114 images for printed 303–416 and two covers; p. 366 ends a piece; the next image, by sequence 369, opens the self-teacher section «ХОЧУ ЗНАТЬ ЭСПЕРАНТО» and a new gathering, signature «5»); no second copy (REU only)",
}


NOTES = {}   # (corpus, page) → the latest sort's note, for the short-item rule below


# SPECIAL HANDLING vs WITH EXCEPTIONS (editor 2026-10-01 11:3x–13:4x, the review of ledger 30q's 221 items,
# an internal record, 2026-09-30, not published). The editor found EXCEPTIONS misleading as a category where absence
# can be attained. So: SPECIAL HANDLING = nothing is excluded, but an absence claim must search a particular way (both the
# Esperanto text and the Russian reading, `ocr-rendersearch-rus/`; or the Russian reading alone). WITH EXCEPTIONS =
# part of the item is excluded (pages missing or unread, a script unread, one side failing). An item with both is
# WITH EXCEPTIONS, its handling notes kept. Short items cleared by the image check of every page → ADMISSIBLE (the editor
# judged W5 to be absence, and approved the 22 short image checks to admissible). The column keeps its old name.
MINOR_CLEARED = {
    # E2, the editor ruled at 11:5x that it is a sideways ESPERANTO and admissible — the only loss is the logo word
    ("LaSunoHispana.1904.5", 1),
}
RUSSIAN_DOMINANT = {
    # E4, the editor accepted the verdict at 13:2x: Russian items whose Esperanto side is next to nothing → search the
    # Russian reading; sokolova (the editor ruled at 13:2x that it is held for Yushmanov, with special handling)
    "BultenoTEKS.1911.1", "BultenoTEKS.1911.2", "BultenoTEKS.1912.3", "BultenoTEKS.1912.4", "BultenoTEKS.1912.5",
    "BultenoTEKS.1913.6", "BultenoTEKS.1913.7", "BultenoTEKS.1913.8", "BultenoTEKS.1914.9",
    "KovnoEsperanto.1911.1-4", "KovnoEsperanto.1912.10", "KovnoEsperanto.1912.13", "sokolova",
}
SCOPED = {
    # the editor ruled at 13:2x/13:3x that the item is held for the Moret article, and should move up to Accepted
    # specifically for that article: French∪Esperanto share about 85% on the article's pages
    "StSl2017_XIV": ("ABSENCE-ADMISSIBLE", "SCOPE: only S. Moret, «Langues internationales, alphabets et Révolution. Les "
                     "idées de N.V. Jušmanov» (printed pp. 275–292 = scan pp. 276–293); the rest of the volume is out of scope"),
    # E6, the editor ruled at 13:3x that it is held for the Interhelpo piece, and that Esperanto be dropped, as it is Russian
    "Вернуть Будущее. Альманах ШТАБА № 1": ("SPECIAL HANDLING", "SCOPE: only N. Andrianova, «Интергельпо — ностальгический "
                     "оптимизм» (scan pp. 161–180); search the RUSSIAN reading (ocr-rendersearch-rus/; pp. 162, 164, 167, 171, "
                     "174 re-read full-page 2026-10-01); the rest of the almanac is out of scope"),
}
ADS_EXCLUDED = {   # the editor ruled on 2026-10-02 11:1x that the 18 are unambiguous ads and can go (an internal record, 2026-10-02, not published; less oge.4 p.438, a book list)
    ('BelgaEsperantisto_1912_n049_nov', 34),
    ('BelgaEsperantisto_1913_n052_feb', 28),
    ('BelgaEsperantisto_1913_n055_maj', 32),
    ('BelgaEsperantisto_1913_n054_apr', 32),
    ('BelgaEsperantisto_1913_n058-059_aug-sep', 28),
    ('BelgaEsperantisto_1912_n050_dec', 32),
    ('BelgaEsperantisto_1913_n053_mar', 32),
    ('BelgaEsperantisto_1913_n057_jul', 32),
    ('BelgaEsperantisto_1913_n051_jan', 6),
    ('BelgaEsperantisto_1913_n056_jun', 32),
    ('kongresa.libro.04', 107),
    ('kongresa.libro.04', 102),
    ('kongresa.libro.04', 97),
    ('kongresa.libro.04', 100),
    ('kongresa.libro.09', 53),
    ('kongresa.libro.09', 187),
    ('kongresa.libro.07', 190),
    ('kongresa.libro.08', 91),
    # cupel8 (La Belga Sonorilo): the eight pages the blind look judged MUNDANE-AD (an internal record, 2026-10-11, not published:
    # the back page of n-roj 1-8, Sept 1902 - Apr 1903, tea, furs, printing machines, glue, pens); the editor 2026-10-12 00:4x,
    # on a proposal, ruled that the 8 mundane pages go (and agreed to 129 vision readings for the MIXED and NOTICE pages, which stay)
    ('LaBelgaSonorilo_1902_n001_sep', 18),
    ('LaBelgaSonorilo_1902_n002_okt', 16),
    ('LaBelgaSonorilo_1902_n003_nov', 12),
    ('LaBelgaSonorilo_1902_n004_dec', 12),
    ('LaBelgaSonorilo_1903_n005_jan', 12),
    ('LaBelgaSonorilo_1903_n006_feb', 16),
    ('LaBelgaSonorilo_1903_n007_mar', 16),
    ('LaBelgaSonorilo_1903_n008_apr', 12),
    # cupel13 (Oficiala Jarlibro 1912): the eight back-matter pages the blind look judged MUNDANE-AD
    # (an internal record, 2026-10-14, not published: the «L'Espero» watch, a soldering apparatus, whisky, a cheque bank and
    # cigarettes, a hotel, Nice firms, a sanatorium and trades, Cook's); the editor 2026-10-14 17:2x approved leaving those
    # 8 pages out of absence searching
    *(('OficialaJarlibro_1912_kul43114', p) for p in (185, 186, 187, 192, 193, 194, 199, 202)),
    # cupel14 (an internal record, 2026-10-17, not published): Wilson's pamphlet on the Third Congress,
    # its back pages of trade advertising (railways, steamers, duplicators, «Old Simon» whisky on the back cover); PDF 58, the
    # publisher's book list, kept as a notice; the editor ruled on 2026-10-17 13:3x that the ads be excluded
    *(('wilson.third.esperanto.congress', p) for p in (48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 59)),
    # cupel15 (an internal record, 2026-10-18, not published): Volapükabled 1886 file 60, printed p. 304, the one page of
    # the 53 looked at that is trade advertising only (an Apeldoorn estate, wines, a tailor, a spa, the «Volapük champagne»);
    # approved by the editor, 2026-10-18 03:4x
    ('ANNO_e2s_18860060', 4),
    # cupel16 (an internal record, 2026-10-20, not published): the seven pages of the 78 looked at that are trade advertising
    # but for one to three small Volapük notice boxes (soap, cigars, cough drops, sandals, parrots, Reclam's Universum);
    # the editor ruled on 2026-10-20 12:4x that all seven be excluded
    *(('volkswohl_weltsprachliches_1899', p) for p in (19, 30, 50)),
    *(('vom_guten_das_beste_1897-99', p) for p in (17, 29, 35, 60)),
    # cupel17 (ocr/runs/CUPEL-BATCH-17-ADLOOK-2026-10-23.md): Vespera Horo 1910, the two pages of the 8 looked at that are
    # trade advertising only (Swiss and German firms: mouthwash, bedding, tonics, prams, Ovomaltine, soap, corsets); the
    # editor 2026-10-23 13:0x
    *(('ONB_e1n_19100402', p) for p in (8, 9)),
    # cupel18a (ocr/runs/CUPEL-BATCH-18A-ADLOOK-2026-10-24.md): Svisa Espero 1911 file 104 PDF 20, the one page of the 13
    # looked at that is trade advertising only (Zurich alcohol-free restaurants and boarding house; the Kuz-Globo globe and
    # atlas, with an order form); the editor 2026-10-24 11:5x
    ('ANNO_e5a_19110104', 20),
}
# A PART exception (approved by the editor, 2026-10-08 02:4x, on a proposal, an internal record, 2026-10-08, not published, (b)): a block
# on a page that is not in the text, while the rest of the page is (cupel5: a hand-lettered advertisement among kept
# text, which ADS_EXCLUDED, being whole pages, could not name). (item, PDF page) → what is not in the text, each entry
# quoting the editor's ruling. The page stays in the search and in the scope; the item becomes WITH EXCEPTIONS and the
# signed line carries «PART p.N: …», which tools/ocr-dowse.py prints beside every silence on the item.
BLOCK_NOT_READ = {
    # cupel5, G5 2026-10-07: page judged LOST, the one loss this block; the editor chose (a) at 18:5x, as less bad than (b)
    # and (c), and at signing, 19:01, ruled that the final advertisement on the page breaches the name-recognition threshold
    # but is a mundane ad and not a historical priority; 2026-10-08 02:5x approved entering it here
    ("Esperanto-UEA_1912_n136_dec20.1", 16): "a mundane ad, the hand-lettered «Pelikan» ink advertisement (Günther Wagner, "
        "Hannover; printed page 356),",
}
# The bi-script items whose Esperanto side is admitted on name recall (the editor 2026-10-13 21:1x; the file's header
# names the G5): one stem per line, «#» lines a comment.
EO_NAME_RECALL = {l.strip() for l in open(os.path.join(GENIZA, "ocr", "method", "EO-SIDE-NAME-RECALL-2026-10-13.tsv"),
                                          encoding="utf-8") if l.strip() and not l.startswith("#")}

COLUMN_RISK = {   # E5, the editor ruled at 13:3x that they be kept, with a note
    f"KaukazaEsperantisto.1910.{n}" for n in ("1", "2", "3", "5", "6", "7", "8", "9", "10-11", "12")}


def _ranges(ps):
    """[1, 2, 3, 7, 9, 10] → «1–3,7,9–10»"""
    out, ps = [], sorted(ps)
    i = 0
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[j] + 1:
            j += 1
        out.append(f"{ps[i]}–{ps[j]}" if j > i else str(ps[i]))
        i = j + 1
    return ",".join(out)


def reclassify(c, exc):
    """The class of an item that is neither PRESENCE ONLY nor PENDING, from its notes: (class, notes)."""
    if c in SCOPED:
        if any(bc == c for (bc, _) in BLOCK_NOT_READ):     # SCOPED returns before the notes: a PART entry would vanish
            sys.exit(f"BLOCK_NOT_READ names {c}, which is SCOPED: its PART note would be dropped; rule it into SCOPED's note")
        return SCOPED[c][0], [SCOPED[c][1]]
    notes = []
    for e in exc:
        if (c, 1) in MINOR_CLEARED and re.fullmatch(r"MINOR p\.1 .*", e):
            continue
        notes.append(e)
    handling, cleared, excluded = [], [], []
    for e in notes:
        if "Russian scored alone" in e or "both sides pass" in e or (c in RUSSIAN_DOMINANT and "RUSSIAN side only" in e) \
                or re.match(r"the Latin reading of \d+ Cyrillic page\(s\) p\.", e):
            handling.append(e)
        elif "cleared by the IMAGE CHECK" in e or e.startswith("NAME LIST checked on NAME RECALL"):
            cleared.append(e)
        elif re.fullmatch(r"\d+ bi-script page\(s\): [A-Za-z/-]+ PRESENCE ONLY; Esperanto gated alone", e) \
                and c in RUSSIAN_DOMINANT:
            handling.append(e)
        else:
            excluded.append(e)
    if c in RUSSIAN_DOMINANT:
        handling.append("RUSSIAN-DOMINANT: search the Russian reading (ocr-rendersearch-rus/); the Esperanto side is next to nothing")
    ads = sorted(p for (x, p) in ADS_EXCLUDED if x == c)
    if ads:
        excluded.append("mundane ADVERTISEMENT page(s) p." + ",".join(map(str, ads)) + ": excluded from absence claims (editor's ruling 2026-10-02)")
    if c in COLUMN_RISK and excluded:
        excluded.append("RISK: same paper and setting as 1910.4/.13/.14 (presence only for garbled columns on the G5 re-sample)")
    if excluded:
        return "WITH EXCEPTIONS", excluded + handling + cleared
    if handling:
        return "SPECIAL HANDLING", handling + cleared
    return "ABSENCE-ADMISSIBLE", cleared


def sort_verdicts():
    v = {}
    for md in sorted(glob.glob(os.path.join(GENIZA, "ocr", "runs", "OCR-G1-SORT-*.md"))):
        tag = re.search(r"OCR-G1-SORT-(.+)\.md$", md).group(1)
        key = os.path.join(GENIZA, "ocr", "runs", f"OCR-G1-SORT-KEY-{tag}.tsv")
        if not os.path.exists(key):
            continue
        k = {l.split("\t")[0]: (l.split("\t")[2], int(l.split("\t")[3])) for l in open(key, encoding="utf-8") if l.strip()}
        for line in open(md, encoding="utf-8"):
            # 3 OR 4 digits: sort 2026-09-29b numbers its pages to 1751, and a 3-digit match silently skipped 1000+
            m = re.match(r"\| (\d{3,4}) \| (NOTHING|MINOR|LOST|SCRIPT) \|(.*)", line)
            if m and m.group(1) in k:
                v[k[m.group(1)]] = m.group(2); NOTES[k[m.group(1)]] = m.group(3)
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", required=True); ap.add_argument("--g1", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--pdfs", required=True, help="the PDF list G1 was run over: a corpus in it but absent from the G1 report had NO silent pages")
    ap.add_argument("--lift", action="append", default=[], help="build as if the editor's named PRESENCE ONLY ruling for this item "
                    "were lifted: for a TEST ledger only (an item held out until a re-read is sampled again, e.g. Internacia Scienca "
                    "Revuo 1904 after the gutter cut, 2026-10-27); the header says so; never the CURRENT ledger")
    a = ap.parse_args()
    gate = {r["corpus"]: r for r in json.load(open(a.gate))}
    g1 = {r["corpus"]: r for r in json.load(open(a.g1))}
    t_gate, t_g1 = os.path.getmtime(a.gate), os.path.getmtime(a.g1)
    notc = {l.split("\t")[0] for l in open(os.path.join(GENIZA, "OCR-NOT-CORPUS.tsv"), encoding="utf-8")
            if l.strip() and not l.startswith("#") and not l.startswith("corpus\t")}
    sv = sort_verdicts()
    g1_input = {os.path.splitext(os.path.basename(l.strip()))[0] for l in open(a.pdfs) if l.strip()}
    src = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    rows, cnt, pg = [], collections.Counter(), collections.Counter()
    for c, r in gate.items():
        if c in notc:
            continue
        d = os.path.join(ROOT, c); txt = d + ".txt"
        why, exc, pend = "", [], []
        if r["g4"] == -1.0: why = "unscoreable (all Cyrillic)"
        elif r["g4"] == -2.0: why = "too short to score"
        elif r["g2_pending"]:     # label the REAL cause (2026-09-27: 8 declared-Ido items read «fails G4» at G4 65–96)
            why = f"G2 pending — second-language pass not run ({', '.join(r['g2_pending'])}); G4 {r['g4']:.0f}"
        elif not (r["g3_ok"] and r["g4"] >= (65 if r["list_pages"] else 75)):
            why = f"fails G4 ({r['g4']:.0f})"
        if os.path.exists(txt) and os.path.getmtime(txt) > min(t_gate, t_g1):
            pend.append("STALE: text newer than the gate or G1 result — re-run them")
        gr = g1.get(c)
        if gr is None and c not in g1_input:
            pend.append("G1 never run on this corpus")
        # in G1's input but absent from its report: G1 found no silent page on the full text (the
        # gate's own «silent» can differ: with --script-segregated it counts on the cleaned text)
        if gr and gr.get("untested", 0) and not gr.get("untested_pages"):
            pend.append(f"G1 left {gr['untested']} page(s) untested (not listed — re-run G1)")
        # the sort verdicts apply to EVERY item, whether or not G1 reported it (G1 reports only items with silent pages)
        if True:
            gr = gr or {}
            minor, unsorted_, script = [], [], []
            g1_pages = set(gr.get("pages", [])) | set(gr.get("untested_pages", []))
            # FIXED 2026-09-29: EVERY sorted page of the item counts, not only the pages G1 flagged — a LOST or MINOR
            # verdict from any image look (the near-miss look, the audits) was silently ignored when G1 had not
            # flagged that page (*Esperanto* (UEA) 1906 n029 p.2, LOST, rose to ADMISSIBLE in ledger 28i).
            sorted_here = {p for (cc, p) in sv if cc == c}
            for p in sorted(g1_pages | sorted_here):
                vv = sv.get((c, p))
                if vv == "NOTHING":
                    continue
                if vv == "SCRIPT":          # only Russian/Georgian/Armenian unread — PRESENCE ONLY for that script
                    script.append(p); continue
                if vv == "MINOR":
                    minor.append(p)
                elif vv == "LOST":
                    if os.path.exists(os.path.join(d, f"page-{p:04d}.hand.txt")) or \
                       os.path.exists(os.path.join(d, f"page-{p:04d}.hand-add.txt")) or (c, p) in RESOLVED_LOST:
                        continue
                    exc.append(f"LOST p.{p} ({RESIDUAL_LOST.get((c, p), 'residual gap')})")
                elif p in g1_pages:
                    unsorted_.append(p)
            if script:
                exc.append("other-script text unread on p." + ",".join(map(str, sorted(script))) + ": PRESENCE ONLY for that script")
            if minor:
                exc.append("MINOR p." + ",".join(map(str, sorted(minor))) + " (≤ 3 lines of masthead/caption/date missing)")
            if unsorted_:
                pend.append(f"{len(unsorted_)} G1-flagged page(s) not yet image-sorted: p." + ",".join(map(str, sorted(unsorted_))))
        for (bc, bp), what in sorted(BLOCK_NOT_READ.items()):
            if bc == c:
                exc.append(f"PART p.{bp}: {what} is not in the text; the rest of the page is")
        if c in NOT_IN_SCAN:
            exc.append("NOT IN SCAN: " + NOT_IN_SCAN[c])
        nbi = len([f for f in glob.glob(os.path.join(d, "page-*.eo-gate.txt"))
                   if (c, int(re.search(r"page-(\d+)", os.path.basename(f)).group(1))) not in FALSE_BISCRIPT])
        # THE LANGUAGE TABLE (2026-10-03): a text it lists with no non-Latin language has no bi-script pages, whatever
        # clean files are on disk; the label names the scripts the table lists (*Helena Esperantisto*: Greek, not
        # «Russian/Armenian/Georgian»). Not in the table: the old label.
        nl = TL.nonlatin(c)
        if nl == set():
            nbi = 0
        if nbi:
            exc.append(f"{nbi} bi-script page(s): {TL.label(c) if nl else 'Russian/Armenian/Georgian'} PRESENCE ONLY; "
                       "Esperanto gated alone")
        nkh = sum(1 for f in glob.glob(os.path.join(d, "page-*.kathye.json"))
                  if (lambda j: j.get("kat_blocks") or j.get("hye_blocks"))(json.load(open(f))))
        if nkh:
            exc.append(f"Georgian/Armenian on {nkh} page(s): PRESENCE ONLY")
        if why == "too short to score":   # on the editor's ruling of 2026-09-27 15:35 for an image check — cleared if EVERY page passes it
            base = [int(m.group(1)) for f in glob.glob(os.path.join(d, "page-*.txt"))
                    for m in [re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))] if m]
            vs = [sv.get((c, p)) for p in base]
            if base and all(v in ("NOTHING", "MINOR", "SCRIPT") for v in vs):
                why = ""
                exc.append("too short for G4 — cleared by the IMAGE CHECK of every page")
                mn = [p for p, v in zip(base, vs) if v == "MINOR"]
                if mn:
                    exc.append("MINOR p." + ",".join(map(str, sorted(mn))))
            elif base and any(v is None for v in vs):
                why = ""; pend.append("too short for G4 — image check of its pages not complete")
        # SPECIAL HANDLING FOR BI-SCRIPT ITEMS (the editor ruled on 2026-09-28 09:55 that Esperanto-only and
        # Russian-only scores be shown, and that an item passing the threshold on one or the other goes into the
        # EXCEPTIONS category, as special handling). Esperanto-only = G4 on the segregated text (bar 75, or 65 with list pages);
        # Russian-only = `ru_only` from the gate (bar 40: an internal record, 2026-09-28, not published). An item
        # with Russian on it that fails on its Esperanto is admitted WITH EXCEPTIONS if its Russian passes —
        # absence then admissible ON THE RUSSIAN SIDE ONLY (search the Russian readings, ocr-rendersearch-rus/).
        ru = r.get("ru_only")
        if (nbi or r.get("cyrillic_pages")) and ru is not None:
            eo_bar = 65 if r["list_pages"] else 75
            eo_s = f"{r['g4']:.0f}" if r["g4"] >= 0 else "none (no Esperanto page to score)"
            if ru >= 40:   # the Russian is scored now: the bi-script note no longer calls it «presence only»
                # 2026-10-03 19:5x: the label is now the table's scripts («Russian», «Greek/Russian» …), not always
                # «Russian/Armenian/Georgian»; an exact-string replace missed every new label and 157 items fell from
                # SPECIAL HANDLING to WITH EXCEPTIONS (chain 2026-10-03-lang). Match any label; other scripts stay
                # presence only, named.
                def _scored(e):
                    m = re.fullmatch(r"(\d+ bi-script page\(s\): )([A-Za-z/-]+) PRESENCE ONLY; Esperanto gated alone", e)
                    if not m:
                        return e
                    rest = [x for x in m.group(2).split("/") if x not in ("Russian", "Ukrainian", "Bulgarian", "Belarusian")]
                    if m.group(2) == "Russian/Armenian/Georgian":
                        rest = []          # the old label, unchanged behaviour (not in the table)
                    if nkh:                # the mask's condition already says «Georgian/Armenian … PRESENCE ONLY»: not
                        rest = [x for x in rest if x not in ("Armenian", "Georgian")]   # restated (approved by the editor, 20:0x)
                    return (m.group(1) + "Esperanto gated alone; Russian scored alone"
                            + (f"; {'/'.join(rest)} PRESENCE ONLY" if rest else ""))
                exc[:] = [_scored(e) for e in exc]
            # a «G2 pending» on a language detected in Cyrillic junk (Bulteno TEKS 1914.9: «polish») counts
            # like a G4 failure here (the editor ruled on 2026-09-28 17:15 that both be fixed)
            if (why.startswith("fails G4") or why.startswith("unscoreable") or why.startswith("G2 pending")) and ru >= 40:
                if c in EO_NAME_RECALL:
                    # THE ESPERANTO SIDE ADMITTED ON NAME RECALL (the editor ruled on 2026-10-13 21:1x that the Esperanto
                    # of the 64 bilingual items be admitted): G4 fails on the Russian read as Latin junk, which the gate's strict extract keeps; the
                    # G5 of their Esperanto side passed (EO-SIDE-NAME-RECALL-2026-10-13.tsv, its header). «both sides pass»:
                    # handling, so SPECIAL HANDLING where nothing else is excluded (search every reading).
                    exc.append(f"SPECIAL HANDLING (bi-script): Esperanto-only {eo_s} fails G4 (bar {eo_bar}) on the Russian read as "
                               f"Latin junk, but its NAME RECALL passes (G5 2026-10-13, ocr/method/EO-SIDE-NAME-RECALL-2026-10-13.tsv) · "
                               f"Russian-only {ru:.0f} passes (bar 40, {r.get('ru_pages')} pp) — both sides pass: absence admissible only "
                               "if BOTH the Esperanto text AND the Russian reading (ocr-rendersearch-rus/) are searched")
                else:
                    exc.append(f"SPECIAL HANDLING (bi-script): Esperanto-only {eo_s} FAILS (bar {eo_bar}) · Russian-only {ru:.0f} passes (bar 40, {r.get('ru_pages')} pp) — absence admissible on the RUSSIAN side only")
                why = ""
            # CORRECTED 23:1x the same night: only where bi-script pages are at least a quarter of the item. Three of the
            # ten «Esperanto side only» items were there by ONE page each — *Mondo* 1924 p.7 (an Ido page the Russian model
            # read as junk Cyrillic), *Pola Esperantisto* 46083 p.20 (sheet music read as Cyrillic), *Ukraina Stelo* 2017
            # 3-4 p.52 (one real parallel Ukrainian poem) — not bilingual papers; they keep their standing.
            elif not why and ru < 40 and nbi * 4 >= int(r.get("pages") or 0):
                # ESPERANTO SIDE ONLY → PRESENCE ONLY (approved by the editor, 2026-09-30 23:0x). These are the bi-script items where
                # the Russian fails and only the Esperanto side passed G4 — the worst interleaving of the two scripts. The G5
                # re-sample (an internal record, 2026-09-30, not published; class ledger-eo) found 3 of 24 of their
                # Esperanto-side pages contradicted on the image (garbled columns; 89% of printed names found) against the
                # bar of at most 1 in 40, after every column remedy (layout re-read, garbage filter, per-script scoring,
                # Russian companion, old-letter model, second reading, vision). Was: WITH EXCEPTIONS, «absence admissible
                # on the ESPERANTO side only» (10 items, 450 pages at ledger 30p).
                why = (f"bi-script, Esperanto side only (Esperanto-only {eo_s} passes, Russian-only {ru:.0f} fails): the G5 re-sample "
                       f"found 3 of 24 Esperanto-side pages contradicted — presence only by the editor's ruling (2026-09-30)")
            elif not why and ru < 40:
                # E-L FIX (approved by the editor for Ukrainian Star, 2026-10-01 00:44): Russian fails, bi-script pages under a quarter —
                # the wording of ledger 30p restored; the 23:0x edit had sent these to the «both sides pass» text below
                exc.append(f"Esperanto-only {eo_s} passes (bar {eo_bar}) · Russian-only {ru:.0f} FAILS (bar 40, {r.get('ru_pages')} pp)"
                           " — absence admissible on the ESPERANTO side only")
            elif not why:
                # BOTH PASS → still WITH EXCEPTIONS (the editor ruled on 2026-09-28 17:15 that these be WITH EXCEPTIONS): an absence search
                # that forgot the Russian file would be unsafe
                exc.append(f"Esperanto-only {eo_s} passes (bar {eo_bar}) · Russian-only {ru:.0f} passes (bar 40, {r.get('ru_pages')} pp)"
                           " — both sides pass: absence admissible only if BOTH the Esperanto text AND the Russian reading (ocr-rendersearch-rus/) are searched")
            else:
                why += f" · Russian-only {ru:.0f} fails (bar 40)"
            # BULGARIAN (2026-10-17, approved by the editor): the gate scored this item's Cyrillic side against the Bulgarian list
            # (`cyr_side`, tools/cyrillic_lexicon.py); the same rules and bar, the conditions named for what was scored
            # UKRAINIAN (2026-10-18, approved by the editor): the same, against the Ukrainian list
            if r.get("cyr_side") in ("bulgarian", "ukrainian"):
                L = r["cyr_side"].capitalize()
                def _bg(e):
                    return (e.replace("Russian-only", f"{L}-only").replace("Russian scored alone", f"{L} scored alone")
                             .replace("the Russian reading (ocr-rendersearch-rus/)", f"the {L} reading (the Cyrillic search, ocr-rendersearch-rus/)")
                             .replace("RUSSIAN side only", f"{L.upper()} side only"))
                exc[:] = [_bg(e) for e in exc]
                why = _bg(why)
        # THE LATIN READING OF THE CYRILLIC PAGES (bi-script fix (d), the editor 2026-10-24 21:2x;
        # geniza/ocr/method/BISCRIPT-GATE-FIX-2026-10-24.md): the gate scored the Esperanto side without the pages the Russian
        # step accepted (`latin_po_pages`); their Latin reading is PRESENCE ONLY, never discarded. A handling note (it
        # excludes no page from the Russian side), and the item's absence claims search every reading (below), so a
        # Latin-script name printed inside the Cyrillic text is searched until the Latin readings join the search text
        # (point 1, with the small-capitals recupel: one redowse list).
        lpo = r.get("latin_po_pages") or []
        if lpo:
            exc.append(f"the Latin reading of {len(lpo)} Cyrillic page(s) p.{_ranges(lpo)}: PRESENCE ONLY, "
                       "the Esperanto side scored without them (editor's ruling 2026-10-24)")
        # A SHORT ITEM THAT FAILS G4 MAY BE CLEARED BY THE IMAGE CHECK — with a hard edge (approved by the editor,
        # 2026-09-28 01:57, on *oficiala aldono* 5a/6a: Esperanto glossed in six
        # languages, so G4 fails on structure, not on reading). ALL of: at most 4 pages, so every page was
        # seen; every page's latest sort verdict NOTHING; every note says the text is «well read», with no
        # «mostly» and no «garbled». Anything longer or less clean stays PRESENCE ONLY.
        if why.startswith("fails G4"):
            base = [int(m.group(1)) for f in glob.glob(os.path.join(d, "page-*.txt"))
                    for m in [re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))] if m]
            ns = [NOTES.get((c, p), "").lower() for p in base]
            if 1 <= len(base) <= 4 and all(sv.get((c, p)) == "NOTHING" for p in base) \
                    and all("well read" in n and "mostly" not in n and "garbled" not in n for n in ns):
                exc.append(f"{why} — cleared by the IMAGE CHECK of every page (≤ 4 pages, all NOTHING, well read; editor's ruling 2026-09-28)")
                why = ""
        if c in NAMELIST_CHECKED:   # a name list judged by the name check (above), and its line says so (the editor
            # 2026-10-24 20:3x, who asked that the earlier instance say so too); no «;» in
            # the note (the conditions are split on it)
            g4f = why.startswith("fails G4")
            exc.append("NAME LIST checked on NAME RECALL, by the images (" + NAMELIST_CHECKED[c].replace(";", ",") + ")"
                       + (f": {why}, cleared by the NAME CHECK" if g4f else "") + " (editor's ruling 2026-10-01)")
            if g4f: why = ""
        if not why and PRESENCE_ONLY_DECLARED.search((c + " " + src.get(c, "")).lower()):   # name OR folder («40» lives in posta-mundi-40/)
            why = "secondary — presence only by the editor's ruling (Posta Mundi, 2026-09-27)"
        if c in PRESENCE_ONLY_NAMED and c not in a.lift:
            why = PRESENCE_ONLY_NAMED[c] + (f" [gate: {why}]" if why else "")
        if why: k = "PRESENCE ONLY"
        elif pend: k = "PENDING"
        else: k, exc = reclassify(c, exc)
        if k == "SPECIAL HANDLING" or (k == "WITH EXCEPTIONS" and any(re.match(r"the Latin reading of \d+ Cyrillic", e) for e in exc)):
            # (2026-10-24, bi-script fix (d)): also a WITH EXCEPTIONS item with Cyrillic pages, so a Russian-side absence
            # claim reads their Latin reading too (Drezen 1928, Bulgara Esperantisto 1907)
            # editor 2026-10-02 22:5x: the absence search on these items
            # reads EVERY reading on disk (G5 on 10-02c: missed names were in psm4 / rus / rusfull, not in the text searched)
            exc = exc + ["SEARCH EVERY READING: an absence claim searches sources/ocr-rendersearch-all/<item>.txt "
                         "(every reading of each page, tools/ocr-search-all-readings.py)"]
        cnt[k] += 1; pg[k] += r["pages"]
        rows.append((c, r["pages"], round(r["g4"], 1) if r["g4"] >= 0 else "", k, why, "; ".join(pend), "; ".join(exc)))
    rows.sort(key=lambda x: (x[3], x[0].lower()))
    with open(a.out + ".tsv", "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-absence-ledger.py from {os.path.basename(a.gate)} + {os.path.basename(a.g1)}. Do not hand-edit — re-run it. SIGNS NOTHING.\n")
        if a.lift:
            f.write(f"# A TEST LEDGER, NEVER CURRENT: the editor's named PRESENCE ONLY ruling lifted for {', '.join(a.lift)}, to sample it again.\n")
        f.write("corpus\tpages\tG4\tclass\twhy presence only\twhy pending\texceptions (excluded from absence findings)\n")
        for x in rows:
            f.write("\t".join(map(str, x)) + "\n")
    for k in ("ABSENCE-ADMISSIBLE", "SPECIAL HANDLING", "WITH EXCEPTIONS", "PENDING", "PRESENCE ONLY"):
        print(f"{k:20} items {cnt[k]:5}  pages {pg[k]:7}")
    pc = collections.Counter()
    for x in rows:
        if x[3] == "PENDING":
            for part in x[5].split("; "):
                pc[re.sub(r"\d+", "N", part.split(":")[0])] += 1
    print("pending reasons:", dict(pc))


if __name__ == "__main__":
    main()
