#!/usr/bin/env python3
r"""ocr-text-languages-table — THE LANGUAGE TABLE: every language each text prints, every script, with its evidence.

    tools/ocr-text-languages-table.py <evidence.tsv> <look-evidence.tsv> --out <tsv>
    e.g. (from geniza/) ../../../tools/ocr-text-languages-table.py OCR-TEXT-LANGUAGES-EVIDENCE-2026-10-03.tsv \
         OCR-TEXT-LANGUAGES-LOOK-EVIDENCE-2026-10-03.tsv --out OCR-TEXT-LANGUAGES-2026-10-03.tsv

WHY. On 2026-10-03 (18:1x–18:2x) the editor asked for a table mapping texts to the languages they contain, which should
have acted as a filter, with Russian, Greek, Georgian and Armenian entries; it must track ALL languages, and the
other-script languages (Ukrainian, Georgian, Armenian, Greek) were to be done at once. The gate's `all_seconds` held Latin-script languages only, so the
28 Sep Cyrillic chain (keyed on script detection alone) read Greek, Ido and Latin headings as Russian.
SCRIPT and LANGUAGE are separate fields (the editor queried the Hebrew at 18:16: *Posta Mundi* 20 prints Ido in Hebrew letters).

SOURCES, per language, in the `evidence` column:
  gate      the gate's primary language and `all_seconds` (Latin script; detected or declared)
  look:N    N pages where a blind look (26 Sep – 1 Oct) saw it (OCR-TEXT-LANGUAGES-LOOK-EVIDENCE; report beside it)
  auth:N    N pages whose authoritative readings (hand, vision, text layer) print its script / its marker letters
  lex:N     N pages whose Russian-model reading has >= 15 Russian-list words (Russian only)
  mask      the item's MASK-KATHYE.json (Georgian/Armenian masking, 27 Sep)
  ruling    an editor's ruling (ocr-absence-ledger.py PRESENCE_ONLY_NAMED: Greek)
RULES (non-Latin): russian ⇐ look, or lex >= 5, or lex >= 1 with Cyrillic in an authoritative reading, or pre-reform /
ы э letters in one; ukrainian ⇐ look, or є ї ґ; belarusian ⇐ look, or ў; greek ⇐ look, auth, or ruling; georgian,
armenian ⇐ look, auth, or mask. A language on weaker evidence is listed with `?` and the row is flagged DOUBT.
FLAGS: RUS-READ-NO-RUSSIAN = the item has Russian-model readings on disk but the table gives it no Cyrillic language:
those readings are junk and must not reach the Russian companion, the ledger's bi-script label, or any rule.
READS ONLY. WRITE-SET: the --out TSV alone, refused if it exists.
"""
import os, re, sys, csv, argparse, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_OF = {"russian": "cyrillic", "ukrainian": "cyrillic", "belarusian": "cyrillic", "serbian-or-macedonian": "cyrillic",
             "bulgarian": "cyrillic", "russian-cited": "cyrillic", "cyrillic-cited": "cyrillic", "serbian-cited": "cyrillic",
             "cyrillic": "cyrillic", "cyrillic-unspecified": "cyrillic", "greek": "greek", "greek-polytonic": "greek",
             "georgian": "georgian", "armenian": "armenian", "hebrew": "hebrew", "japanese": "japanese",
             "arabic-script": "arabic", "chinese-script": "han", "korean": "hangul", "other-script": "other"}
# «-cited» = a few names, titles or quoted words in another language (< CITED distinct Cyrillic words of 4+ letters in the
# authoritative readings). The script is printed, the text is not in that language: a cited language NEVER licenses a
# model run, a search file of its own or a bi-script label.
CITED = 30
CITED_SHARE = 0.05   # a non-Cyrillic script on fewer than 5% of an item's pages is cited (BK 2015: Greek on 4 of 392)
# DECLARED languages (a new item, e.g. a cupel batch, before any reading of it can show its scripts): item-name prefix →
# (languages, provenance). Added to the item's row with «declared» as evidence. The Russian reader refuses an item not in
# the table, so a batch's languages are declared here at intake and the table rebuilt before its Russian passes.
DECLARED = {"korzhenkov-historio-2005": (("esperanto", "russian-cited"),
                                        "cupel3, C1 look 2026-10-06 (Esperanto running text throughout; Russian only in the "
                                        "imprint of the contents page and a title on p. 10); decided by the editor, 2026-10-06"),
            "LEsperantiste.1907.5.1": (("esperanto", "french"),
                                       "cupel4, C1 look 2026-10-07 (the Gallica copy of L'Espérantiste May 1907: French and "
                                       "Esperanto running text, Latin script only, as the ÖNB copy LEsperantiste.1907.5); "
                                       "decided by the editor, 2026-10-07"),
            "Esperanto-UEA_1912_n136_dec20.1": (("esperanto",),
                                                "cupel5, C1 look 2026-10-07 (the ÖNB copy of Esperanto (UEA) 20 Dec 1912: "
                                                "Esperanto running text, Latin script only; other languages only in names and "
                                                "addresses, as the archive.org copy Esperanto-UEA_1912_n136_dec20); "
                                                "decided by the editor, 2026-10-07"),
            "reu-bofron-esenco-1906": (("russian", "esperanto-cited"),
                                       "cupel7, C1 look 2026-10-10 (Esenco kaj estonteco in Russian, 1906: Russian running text "
                                       "in the pre-reform spelling; Esperanto only in cited words and endings); editor 2026-10-10 "
                                       "17:5x «the rest stand as is»"),
            "reu-pola-adresaro-1909": (("esperanto", "polish-cited"),
                                       "cupel7, C1 look 2026-10-10 (Pola adresaro 1909: Esperanto running text; Polish in names and "
                                       "addresses); decided by the editor, 2026-10-10"),
            "reu-esperanto-lernolibro-1893": (("russian", "esperanto"),
                                       "cupel7, C1 look 2026-10-10 (Esperanto lernolibro 1893: Russian explanations and Esperanto "
                                       "texts and word lists, both running text); decided by the editor, 2026-10-10"),
            "katalogo_1912": (("esperanto", "russian"),
                              "cupel7, C1 look 2026-10-10 (the 1912 catalogue: Esperanto book titles; Russian in the price "
                              "heading and Russian titles); editor ruled on 2026-10-10 that in 1912 the presence of Russian will not "
                              "just be incidental, so it is both languages"),
            "privat-historio-1927-vol2": (("esperanto",),
                                          "cupel6, C1 look 2026-10-08 (Privat, Historio de la lingvo Esperanto, vol. 2, "
                                          "1927: Esperanto running text, Latin script only; other languages only in names "
                                          "and titles); decided by the editor, 2026-10-09")}
# The editor's rulings on a look's unnamed Cyrillic etc.: item-name prefix → (from, to, provenance)
#   (to None = the entry is dropped: the ruling says the language is not there)
# cupel8, La Belga Sonorilo, the per-issue run (archive.org, 1902–1914): declared by year, as the ÖNB bound volumes' rows
# have them. 1911 and 1912 by issue: a year prefix would also catch the three gated «.bitarkivo» copies of 1911 n-roj
# 139, 143 and 1912 n-ro 155 (byte-identical files, outside the batch). «…_1912_n158_nov» covers its «_suplemento».
_BS_WHY = ("cupel8, C1 look 2026-10-10 (La Belga Sonorilo: Esperanto and French running text throughout, e.g. Lemaire "
           "in French, 1914; Dutch in 1902–1905; Ido running text from 1908, e.g. «Idala transskribo», 1914; as the "
           "ÖNB volumes' rows); decided by the editor, 2026-10-10")
DECLARED.update({f"LaBelgaSonorilo_{y}": (("esperanto", "french", "dutch"), _BS_WHY) for y in range(1902, 1906)})
DECLARED.update({f"LaBelgaSonorilo_{y}": (("esperanto", "french"), _BS_WHY) for y in (1906, 1907)})
DECLARED.update({f"LaBelgaSonorilo_{y}": (("esperanto", "french", "ido"), _BS_WHY) for y in (1908, 1909, 1910, 1913, 1914)})
DECLARED.update({f"LaBelgaSonorilo_{s}": (("esperanto", "french", "ido"), _BS_WHY) for s in (
    "1911_n138_jan", "1911_n139_jan", "1911_n140_mar", "1911_n141_apr", "1911_n142_maj", "1911_n144_jul-aug",
    "1911_n145_sep", "1911_n146_okt", "1911_n147_nov", "1911_n148_dec", "1912_n149_jan", "1912_n150_feb",
    "1912_n151_mar", "1912_n152_apr", "1912_n153_maj", "1912_n154_jun", "1912_n156_aug", "1912_n157_sep",
    "1912_n158_nov")})
_C9_OK = "decided by the editor, 2026-10-12 (the four declarations spelled out)"
DECLARED.update({
    "zakrzewski-historja-1906": (("polish", "esperanto"),
                                 "cupel9, C1 look 2026-10-12 (Polish prose with Esperanto quoted, frame 45; the grammar "
                                 "section, DjVu pp. 15–27, sets out Esperanto: profiles/by-source/zakrzewski-three-works-2026-09-05.md); " + _C9_OK),
    "Esperanto-UEA_1913_n152_aug24": (("esperanto",),
                                      "cupel9, C1 look 2026-10-12 (PDF pages 1, 13, 26: Esperanto throughout, with Kongresa "
                                      "Gazeto n-ro 4 of 27 Aug 1913); " + _C9_OK),
    "hvorostin_cara_cenzuro_1972": (("esperanto",),
                                    "cupel9, C1 look 2026-10-12 (PDF pages 1, 10, 20: Esperanto typescript; the Russian archive "
                                    "references are in Latin letters, no Cyrillic); " + _C9_OK),
    "gasparikova-pollak-1987-interhelpo": (("slovak",),
                                           "cupel9, C1 look 2026-10-12 (PDF page 12, printed 627: Slovak prose); the word list "
                                           "tools/lexicons/slovak.txt built the same day (on the editor's request); " + _C9_OK),
})
# cupel10 (the Sidorov scans): the 26 declarations spelled out in an internal record (2026-10-13, not published)
_C10_OK = "decided by the editor, 2026-10-13 (the 26 declarations spelled out)"
_C10 = lambda seen: f"cupel10, C1 look 2026-10-13 ({seen}); " + _C10_OK
_C10_KRON = _C10("Esperantista Movado, Kronstadt: Esperanto and post-1918 Russian running text; the Esperanto typed with "
                 "apostrophes for the hats")
_C10_BITNER = _C10("Esperanto headwords, old-spelling Russian glosses")
DECLARED.update({
    "devjatnin_verkaro_libro_1_1906": (("esperanto",), _C10("Esperanto verse and drama throughout")),
    "devjatnin_plena_verkaro_libro_3_1908": (("esperanto", "russian-cited"),
                                             _C10("Esperanto throughout; Russian only in the printer's imprint and the "
                                                  "publisher's list")),
    "devjatnin_artista_biblioteko_internacia_n_1_1910": (("esperanto",), _C10("Esperanto drama throughout")),
    "krilov_fabloj_1910": (("esperanto", "russian-cited"), _C10("Esperanto verse; Russian only in the imprint and a stamp")),
    "durer_albumo_1911": (("esperanto", "german-cited"),
                          _C10("front matter only, the editor's ruling: the Esperanto «Antaŭparolo»; German in the imprint")),
    "tiflisano_poemaro_1911": (("esperanto",), _C10("Esperanto verse")),
    "drezen_pri_terminaro_1935": (("esperanto",), _C10("Esperanto prose, tables, footnotes")),
    "laborista_esperanta_movado_anta_la_mondmilito": (("esperanto",), _C10("De Bruin 1936: Esperanto prose and documents")),
    "ora_jarlibro_de_uea_1937": (("esperanto",), _C10("Esperanto lists and tables")),
    "maimon_la_kashita_vivo_de_zamenhof_1978": (("esperanto",),
                                                _C10("Esperanto prose and name index; Cyrillic only in handwritten pencil notes")),
    "ludovikito_senlegenda_biografio_de_zamenhof_1982": (("esperanto",), _C10("Esperanto typescript, all lower case")),
    "jankowski_esperanto_mono_2000": (("esperanto",), _C10("Esperanto prose")),
    "haupenthal_pri_la_start_kondichoj_2013": (("esperanto", "german-cited"),
                                               _C10("Esperanto prose; German titles cited in the references")),
    **{s: (("esperanto", "russian"), _C10_KRON) for s in (
        "esperantista_movado_1920_n_1", "esperantista_movado_1920_n_2", "esperantista_movado_1920_n_3",
        "esperantista_movado_1921_n_1_2", "esperantista_movado_1921_n_3")},
    "rugha_esperantisto_1921_1": (("esperanto", "russian"),
                                  _C10("Ruĝa Esperantisto 1921: Esperanto in the h-system, Russian running text")),
    "informilo_c_k_seu__1926_27__nn9_12": (("russian", "esperanto"), _C10("Russian main text, Esperanto sections")),
    "poemo_pri_la_militiro_de_igor_1908": (("esperanto", "russian"),
                                           _C10("parallel columns, Esperanto and old-spelling Russian")),
    "eo_ru_vortaro_1908": (("esperanto", "russian"), _C10_BITNER),
    "plena_eo_ru_vortaro_1908": (("esperanto", "russian"), _C10_BITNER),
    "belousov_eroshenko_amiko_de_lusin_1975": (("russian",), _C10("Russian running text")),
    "belousov_eroshenko_pioniro_1985": (("russian",), _C10("Russian running text")),
    "vivis_vojaghis_verkis_2015": (("esperanto", "japanese-cited"),
                                   _C10("the Esperanto part, printed pp. 2–47; the Japanese part, printed pp. 53–99, out of "
                                        "scope by the editor's ruling (option a)")),
})
# cupel11 (Brazila Esperantisto 1907–1918, ANNO's 55 issues and BitArkivo's July 1907): one declaration for the run
_C11 = ("cupel11, C1 look 2026-10-14 (168 pages, the first, middle and last of each of the 56 issues, four readers: "
        "Esperanto and Portuguese running text throughout, Portuguese in parallel columns («Frazaro»), verse, prose, notices "
        "and advertisements; French and English in short passages only, under the 5% bar); editor 2026-10-14 01:1x "
        "«make portuguese happen» (the declaration spelled out: esperanto main, portuguese second; the Esperanto word list "
        "scores it; Portuguese credited through tools/lexicons/portuguese.txt, built the same night; no Russian pass)")
DECLARED.update({
    "ANNO_e3g_": (("esperanto", "portuguese"), _C11),
    "brazilaesperantisto_1907_j01_n4_jul_600ppp": (("esperanto", "portuguese"), _C11),
})
# cupel13 (the 18 with no other copy known: Lublin's PDFs, rendered whole, and Esperanta Rubriko from archive.org)
_C13_OK = ("decided by the editor, 2026-10-14 (the declarations spelled out per item: languages in order, the main first; the "
           "evidence; the effect: which word list scores it, which second-language passes it licenses)")
_C13 = lambda seen: f"cupel13, C1 look 2026-10-14 ({seen}); " + _C13_OK
DECLARED.update({
    "VIjfJaarEsperantoInNederland_1909_kul46590": (("dutch", "esperanto"), _C13("Dutch prose; Dutch 40% of its words, not counting words also Esperanto")),
    "Krytyka_1912_R14Cz2_": (("polish", "esperanto-cited"), _C13("Polish prose; Polish 43% (the congress pieces Lublin's catalogue names are not in these issues,")),
    "LEsperanto_1914_kul": (("esperanto", "italian"), _C13("Esperanto and Italian glossaries, notes and an Italian article; Italian 7–27%; Portuguese and Latin cited on one page each")),
    "LaEsperantisto_1910_n12_kul44805": (("esperanto", "german"), _C13("Fritz Stephan's monthly: Esperanto, German advertisements; German 9%")),
    "FotoRevuoInternacia_1906_n01_kul47247": (("esperanto", "french"), _C13("Esperanto and French in parallel columns; French 13%")),
    "esperantarubriko_1910-1911_n01-30": (("esperanto", "spanish", "catalan"), _C13("the Esperanto column of La Publicidad (Barcelona), Spanish and Catalan running text")),
    "LaJubileaKongresoDeEsperanto_1912_kul46721": (("esperanto",), _C13("Esperanto, 91%")),
    "JubileaUniversalaKongresoEsperanti_1912_kul47031": (("esperanto",), _C13("an album, Esperanto captions and lists")),
    "OraLibroDeLaEsperantoMovado_1887_kul46892": (("esperanto",), _C13("Esperanto, 93%")),
    "OficialaJarlibro_1912_kul43114": (("esperanto",), _C13("Esperanto, delegate lists")),
    "AntauenKunKredoLiteraturaJarlibroD_1911_kul46752.part": (("esperanto",), _C13("the cut: front matter and Dobrzański's two pieces, Esperanto")),
})
_C12_OK = ("decided by the editor, 2026-10-15 (the declarations spelled out per journal: languages in order, the main first; the "
           "measure; the effect: the Esperanto list scores both, Dutch licenses the Dutch second-model pass, not --main)")
_C12 = lambda seen: f"cupel12, C1 look 2026-10-15 ({seen}); " + _C12_OK
DECLARED.update({
    "ANNO_e1t_": (("esperanto", "dutch"), _C12("Nederlanda Katoliko 1910–1915, ÖNB: Dutch running text in every issue looked at "
                                              "(mastheads, articles, the official part, parallel columns, advertisements); Dutch "
                                              "7.8–37.4% of the words, median 20.2%, not counting words also Esperanto")),
    "ANNO_e4a_": (("esperanto",), _C12("Espero Katolika 1903–1914, ÖNB: Esperanto running text; Latin, French, German, Italian, "
                                      "Hungarian, English, Dutch cited only, none above 1.3%")),
    "EsperoKatolika_1907_n49_kul44785": (("esperanto",), _C12("Espero Katolika 1907/08 n-ro 49, Lublin's, the issue Vienna lacks")),
    "EsperoKatolika_1909_n56_kul45291.part": (("esperanto",), _C12("Espero Katolika 1909, printed pp. 212-213, Lublin's PDF pp. 32-33: the leaf Vienna's ANNO_e4a_19090157 lacks (LACUNAE.tsv; decided by the editor, 2026-10-16)")),
})
_C14_OK = ("decided by the editor, 2026-10-17 (the declarations spelled out per run: languages in order, the main first; the "
           "evidence, the C1 look of 2026-10-16, three pages an item; the effect, the list that scores it and the passes licensed)")
_C14 = lambda seen: f"cupel14, C1 look 2026-10-16 ({seen}); " + _C14_OK
DECLARED.update({
    # Latino sine flexione, its own name and list since 2026-10-17 05:1x (the editor chose option b and approved it: tools/lexicons/latino-sine-
    # flexione.txt by tools/build-lsf-lexicon.py; an internal record, 2026-10-17, not published). Before that, «occidental»
    # by the editor's ruling of 2026-10-12 as a naturalistic proxy (option (a) at C5.2), which could not tell it from Esperanto
    "ScholaEtVita_": (("latino-sine-flexione",), _C14("Schola et Vita 1926–1934, Lublin: Latino sine flexione, Peano's Interlingua; "
                                                     "Latin, Italian, French, English cited only") + "; the language's own list, decided by the editor, 2026-10-17"),
    "ANNO_e0g_": (("occidental",), _C14("Kosmoglott 1922–1926, ÖNB, and the c. 1972 plan of the run: Occidental; one 1926 article "
                                       "«Skribat in Medial», about 20 lines, cited only")),
    # Kosmoglott 1922 (the volume, joined): Russian too, found by G5 2026-10-17, not by the C1 look. The judge of PDF 48
    # (g5/b01/010) saw Russian MUCH and the names Карлейль, Чешихин В. Е., Кофман А., Юшманов Н.; no reading of ours had
    # any Cyrillic (ÖNB's text layer neither). The longer key wins at the main-language step, so Occidental stays main.
    "ANNO_e0g_19220005": (("occidental", "russian"), "cupel14, G5 2026-10-17 (b01/010, PDF 48: Russian MUCH, Cyrillic "
                          "names); the editor ruled on 2026-10-17 that this must be recognised, given the names; "
                          "Russian added to Kosmoglott 1922"),
    "PorEKontre_1938": (("ido", "french-cited"), _C14("Por e Kontre 1938 n-ro 1, Lublin: Ido, typewritten")),
    "io-cited-progreso-326-2002": (("ido", "french-cited"), _C14("Progreso 326, 2002: Ido; French, Spanish, English titles cited")),
    "BultenoLiberaPenso.": (("esperanto",), _C14("Bulteno de Libera Penso 1908–1913, BitArkivo's images: Esperanto")),
    "EsperoKatolika_1912_kul44787": (("esperanto",), _C14("Espero Katolika January 1912 (n-ro 81), Lublin, the issue ANNO lacks")),
    "EsperoKatolika_1912_kul44792": (("esperanto",), _C14("Espero Katolika June 1912 (n-ro 86), Lublin, the issue ANNO lacks")),
    "LaSpritulo_1909": (("esperanto",), _C14("La Spritulo 1909 n-ro 7, Lublin: Esperanto")),
    "aymonier-ferter.pri.esperanto": (("esperanto", "french-cited", "ido-cited"), _C14("Aymonier, Pri Esperanto (tr. Ferter), the editor's scan: Esperanto; Ido and French words cited")),
    "wilson.third.esperanto.congress": (("english", "esperanto-cited"), _C14("Wilson, the Third Esperanto Congress, the editor's scan: English running text; Esperanto cited")),
    "samuel.interhelpo": (("russian",), _C14("Samuel, «Интергельпо» (Moscow 1935): Russian, Cyrillic; no international language")),
})
_C15_OK = ("decided by the editor, 2026-10-17 (the declarations spelled out per item: languages in order, the main first; the "
           "evidence, the C1 look of 2026-10-17, 37 pages by three readers, cupel-batch-15/c1-look-reader{1,2,3}.txt; the effect, the "
           "list that scores it and the passes licensed)")
_C15 = lambda seen: f"cupel15, C1 look 2026-10-17 ({seen}); " + _C15_OK
DECLARED.update({
    # Volapük (Schleyer's): scored on tools/lexicons/volapuk.txt with the compound analyser (tools/volapuk_analyser.py)
    "ANNO_e2s_": (("volapuk", "german"), _C15("Volapükabled zenodik/lezenodik 1881–1906, ÖNB: Volapük, and German in parallel columns (Fraktur in 1881, Schleyer's reformed spelling from 1883); French, Italian, English, Spanish, Latin, Greek, Cyrillic cited")),
    "jveizapot": (("volapuk", "german"), _C15("Jveizapot (Swiss), ÖNB: Volapük and German in parallel columns")),
    "kosmopolan": (("volapuk", "english"), _C15("Kosmopolan, ÖNB: Volapük and English in parallel columns")),
    "volaspodelamont00unkngoog": (("volapuk", "english"), _C15("Volaspodel (US), archive.org: Volapük; English running text (Sprague's lessons)")),
    "volapükan.melopik": (("volapuk", "english-cited", "german-cited"), _C15("Volapükan Melopik (US), ÖNB: Volapük; English and German titles cited")),
    "nunal.nulik": (("volapuk", "italian"), _C15("Nunal nulik (Milan 1890–91), ÖNB: Volapük and Italian")),
    "Volapukabled_talik_1889_n19": (("volapuk", "italian"), _C15("Volapükabled tälik 1889 n-ro 19, BSB: Volapük and Italian")),
    "volapükabled": (("volapuk", "dutch"), _C15("Volapükabled, in en over de wereldtaal 1884–85, ÖNB: Volapük and Dutch in parallel columns")),
    "levolapuk.": (("volapuk", "french"), _C15("Le Volapük (Paris 1886–89), Gallica: Volapük and French")),
    "einstein-weltsprachliche-zeit-und-streitfragen-1889": (("german", "volapuk-cited", "esperanto-cited"), _C15("Einstein, Weltsprachliche Zeit- und Streitfragen (1889), Google/archive.org: German; Volapük and Esperanto cited")),
})
_C16_OK = ("decided by the editor, 2026-10-18 (the declarations spelled out per title in geniza/ocr/runs/CUPEL16-C5-DECLARATIONS-PROPOSAL-2026-10-18.md: languages in order, the main first; the evidence, the C1 look of 2026-10-18, 73 pages by six readers, cupel-batch-16/c1-look/RETURN-reader1–6.md; the effect, the list that scores it and the passes licensed)")
_C16 = lambda seen: f"cupel16, C1 look 2026-10-18 ({seen}); " + _C16_OK
DECLARED.update({
    # cupel16: temerov's Volapük scans (periodicals 1886–99, pamphlets and books 1884–1931, Sionsharfe 1878–80 in part)
    "bukalised_literata_1889": (("german", "volapuk-cited"), _C16("Bukalised literata volapükik (1889), a bibliography: C1 reader 1: German book list, Volapük titles cited; handwritten additions")),
    "cogabled_": (("volapuk",), _C16("Cogabled (Munich, 1886–90), the comic paper: C1 reader 1: Volapük; Fraktur in headings only")),
    "couturat_leau_histoire_": (("french", "volapuk-cited", "esperanto-cited"), _C16("Couturat and Leau, Histoire de la langue universelle (1903; 1907, four parts): C1 reader 1: French; Volapük cited; small capitals")),
    "drezen_historio_mondolingvo_1931": (("esperanto", "german-cited"), _C16("Drezen, Historio de la mondolingvo (1931): C1 reader 1: Esperanto; German titles cited")),
    "drezen_za_vseobshchim_yazykom_1928": (("russian", "esperanto-cited", "volapuk-cited"), _C16("Drezen, Za vseobshchim yazykom (1928): C1 reader 1: Russian (Cyrillic); Latin-script titles cited")),
    "einstein_examen_critique_1889": (("french", "esperanto-cited", "volapuk-cited"), _C16("Einstein, Examen critique du volapük … L'Internacia du Dr Espéranto (1889): C1 reader 1: French; Esperanto cited")),
    "el_volapuk_": (("spanish", "volapuk"), _C16("El Volapük (Barcelona/Madrid, 1886–91): C1 reader 1: Spanish; Volapük headings; a teaching journal")),
    "feyerabend_weltspracheschwindel_1888": (("german",), _C16("Feyerabend, Der Weltsprache-Schwindel (1888): C1 reader 1: German in Fraktur throughout")),
    "gross_dokums_lecif_deut_1888": (("volapuk",), _C16("Dokums lecif (1888): C1 reader 1: Volapük")),
    "gutensohn_abwehr_1888": (("german", "volapuk-cited"), _C16("Gutensohn, Abwehr (1888): C1 reader 1: German (Antiqua); Volapük cited")),
    "hain_is_vp_progressing_1889": (("english",), _C16("Hain, Is Volapük progressing? (1889): C1 reader 2: English")),
    "kausch_lised_vpanas_1901": (("volapuk",), _C16("Kausch, Lised Volapükanas (1901), a list of Volapükists: C1 reader 2: Volapük list of names; faint print")),
    "Kerkhoffs_Dictionaire_1887.front": (("french", "volapuk-cited"), _C16("Kerkhoffs's dictionary (1887), front matter: C1 reader 1: French; Volapük cited")),
    "kniele_einstein_linguo_internacia_1890": (("german", "esperanto-cited", "volapuk-cited"), _C16("Kniele on Einstein's «La linguo internacia» (1890): C1 reader 2: German; Esperanto cited")),
    "kosmopolan_": (("volapuk", "english"), _C16("Kosmopolan (1891–98, issues and the 1898 contents): C1 reader 2: English and Volapük in parallel columns (as cupel15's ÖNB kosmopolan)")),
    "lott_ist_volapuk_die_beste_1888": (("german",), _C16("Lott, Ist Volapük die beste … (1888): C1 reader 2: German, part in Fraktur; a five-language word table")),
    "low_reflexionen_berlin_1888": (("german", "volapuk-cited"), _C16("Löw, Reflexionen (Berlin 1888): C1 reader 2: German (Antiqua)")),
    "mittheilungen_": (("german",), _C16("Mittheilungen of the Vienna and other Weltsprache societies (1887–88): C1 reader 2: German")),
    "mln_v2_1887_schele_de_vere": (("english",), _C16("Schele de Vere in Modern Language Notes (1887): C1 reader 2: English")),
    "mulapenad_nebolitik_": (("volapuk",), _C16("Mulapenad nebolitik (1886–90): C1 reader 2: Volapük; German and Latin cited")),
    "muller_phantom_1888": (("german",), _C16("Müller, Das Phantom … (1888): C1 reader 3: German in Fraktur throughout")),
    "nar_v146_1888_bell": (("english",), _C16("Bell in the North American Review (1888): C1 reader 3: English")),
    "nature_v38_1888_scientific_value": (("english",), _C16("Nature 38 (1888), on Volapük's scientific value: C1 reader 3: English")),
    "nogan_vpik_": (("volapuk", "dutch"), _C16("Nogan volapükik plo Beljän e Nedän (1887–92): C1 reader 3: Volapük; Dutch, German and French running text in advertisements")),
    "nov_": (("russian", "volapuk-cited"), _C16("Russian press items on Volapük (Novosti and others): C1 reader 3: Russian, pre-reform spelling (Cyrillic)")),
    "nunal_nulik_": (("volapuk", "italian"), _C16("Nunal nulik (Milan 1890–92), temerov's copies: C1 reader 3: Italian with Volapük (as cupel15's ÖNB nunal.nulik)")),
    "nunel_valemik_": (("english", "volapuk"), _C16("Nunel valemik (1888–89): C1 reader 3: English with Volapük running text")),
    "nuns_blefik_": (("volapuk", "dutch"), _C16("Nuns blefik (1893–95): C1 reader 3: Volapük; Dutch notices")),
    "nurnberger_presse_": (("german",), _C16("Nürnberger Presse, 1884 (the first Volapük meeting): C1 reader 3: German (Antiqua)")),
    "pietzker_zur_kritik_1889": (("german",), _C16("Pietzker, Zur Kritik des Volapük (1889): C1 reader 4: German (Antiqua)")),
    "romer_vp_und_professoren_1888_bsb": (("german",), _C16("Romer, Volapük und die Professoren (1888): C1 reader 4: German in Fraktur throughout")),
    "rund_um_die_welt_haupenthal_nachwort": (("german",), _C16("Haupenthal's afterword to the Rund um die Welt reprint (modern): C1 reader 4: German")),
    "rund_um_die_welt_y": (("german", "volapuk"), _C16("Rund um die Welt (1888–92): C1 reader 4: German with Volapük running text")),
    "scheyrer_concurrenten_1888_onb": (("german",), _C16("Scheyrer, Die Concurrenten des Volapük (1888): C1 reader 4: German (Antiqua)")),
    "schuchardt_auf_anlass_1888": (("german",), _C16("Schuchardt, Auf Anlass des Volapüks (1888): C1 reader 4: German, italic")),
    "science_v11_1888_bell": (("english",), _C16("Bell in Science 11 (1888): C1 reader 4: English")),
    "siegismund_verzeichniss_1888": (("german", "volapuk-cited"), _C16("Siegismund's catalogue of Volapük books (1888): C1 reader 4: German")),
    "sionsharfe_": (("german", "volapuk"), _C16("Sionsharfe 1878–80, the Volapük and world-alphabet pages: the 1879–80 German reading; the editor's two rulings")),
    "spodel_vpik_hamburg": (("volapuk", "german"), _C16("Spodel volapükik (Hamburg): C1 reader 4: Volapük and German as running text")),
    "steiner_drei_weltsprach-systeme_1889": (("german", "esperanto-cited"), _C16("Steiner, Die drei Weltsprach-Systeme (1889): C1 reader 4: German in Fraktur; Esperanto cited")),
    "tapuk_1896": (("german",), _C16("Tapuk (1896): C1 reader 4: German")),
    "timapenad_dan_novegan_1889": (("danish", "volapuk"), _C16("Timapenad volapükik plo Dän e Norgän (1889): C1 reader 5: Danish; Volapük cited on that page (a Volapük journal)")),
    "volapuk_journal_london_1888": (("english", "volapuk"), _C16("The Volapük Journal (London 1888): C1 reader 5: English; Volapük cited")),
    "volapukisten_": (("swedish", "volapuk"), _C16("Volapükisten (Stockholm 1888–89): C1 reader 5: Swedish and Volapük running text")),
    "volaspodel_": (("volapuk", "english"), _C16("Volaspodel (1888–94), temerov's copies: C1 reader 5: English with Volapük running text (as cupel15's archive.org copy)")),
    "volkswohl_weltsprachliches_": (("german",), _C16("Das Volkswohl, its Weltsprache section (1898–99): C1 reader 5: German in Fraktur throughout")),
    "vom_guten_das_beste_1897-99": (("german", "volapuk-cited"), _C16("Vom Guten das Beste (1897–99): C1 reader 5: German")),
    "vp_monthly_boston_": (("english", "volapuk"), _C16("The Volapük Monthly (Boston): C1 reader 5: English and Volapük running text")),
    "vpabled_nedanik_haastert_1884-85": (("volapuk", "dutch"), _C16("The Dutch Volapükabled 1884–85, temerov's copy: C1 reader 5: Dutch and Volapük in parallel (as cupel15's volapükabled)")),
    "vpabled_talik_1888": (("volapuk", "italian"), _C16("Volapükabled tälik 1888: C1 reader 5: Italian and Volapük running text")),
    "vpaflen_jveizik_": (("volapuk", "german", "french"), _C16("Volapükaflen jveizik (= Jveizapot), temerov's copies: C1 reader 5: German, French and Volapük running text (as cupel15's jveizapot: Volapük, German)")),
    "vpagased_lostanik_1891": (("volapuk",), _C16("Volapükagased lostänik (1891): C1 reader 5: Volapük")),
    "vpaklubs_": (("volapuk",), _C16("Volapükaklubs (1888–89): C1 reader 5: Volapük")),
    "vpan_nolik_": (("volapuk", "german"), _C16("Volapükan nolik (1888–90): C1 reader 5: Volapük; German advertisements")),
    "wesen_zweck_ziel_vortrag": (("german",), _C16("Wesen, Zweck und Ziel (a lecture): C1 reader 6: German")),
    "zamponi_einfuhrung_1904": (("german",), _C16("Zamponi, Zur Frage der Einführung … (1904): C1 reader 6: German")),
    # cupel16b, confirmed by the editor 2026-10-19 11:0x (by analogy with the confirmed rows: the 1907 Couturat–Leau; Drezen's Esperanto works)
    "histoiredelalang00coutuoft": (("french", "volapuk-cited", "esperanto-cited"), "cupel16b, Couturat and Leau, Histoire de la langue universelle, 1st ed. 1903, archive.org (Toronto): French; Volapük and Esperanto cited, as the 2nd ed. 1907 (cupel16, C1 reader 1); decided by the editor, 2026-10-19"),
    "drezen-zamenhof-1929": (("esperanto",), "cupel16b, Drezen, Zamenhof (1929), archive.org's mirror of Lublin's copy: Esperanto (the title page; SAT's bioideologia studo); decided by the editor, 2026-10-19"),
})
_C17_OK = ("decided by the editor, 2026-10-21 (the declarations spelled out per run in geniza/ocr/runs/CUPEL17-C5-DECLARATIONS-PROPOSAL-2026-10-21.md: languages in order, the main first; the evidence, the C1 look of 2026-10-20, nine pages, cupel-batch-17/c1-look/, and the function words of each run's new reading; the effect, the list that scores it and the passes licensed)")
_C17 = lambda seen: f"cupel17, C1 look 2026-10-20 ({seen}); " + _C17_OK
DECLARED.update({
    # cupel17: the first third of the ÖNB slice (ANNO), eight runs
    "ANNO_e7a_": (("esperanto", "spanish"), _C17("Antaŭen Esperantistoj (Lima, 1903–14): Esperanto; Spanish running text throughout")),
    "ANNO_e1w_": (("esperanto",), _C17("Scienca Gazeto (1912–14): Esperanto, two columns")),
    "ANNO_e0d_": (("german", "esperanto"), _C17("Rund um die Welt (the Esperanto paper, 1909–14): German beside Esperanto in parallel columns, Antiqua")),
    "ANNO_e0h_": (("esperanto", "french"), _C17("La Deksepa (Paris, 1910–14): Esperanto; French mastheads and notices")),
    "ANNO_e5e_": (("esperanto", "portuguese"), _C17("Portugala Revuo (1909–14): Esperanto and Portuguese")),
    "ANNO_e1v_": (("esperanto", "bulgarian"), _C17("Rondiranto (1902–04): Esperanto beside Bulgarian in pre-reform Cyrillic; the Bulgarian-only route of 2026-10-17 (orus, scored against the Bulgarian list through the old spelling)")),
    # Lingua Internationale RE-DECLARED 2026-10-23 (the editor: it looked half French and half
    # Latino sine flexione, to be found out; approved): scored against the word lists, 71 of 84 pages in four
    # 1911 issues read best as Latino sine flexione, 12 as French; the cupel17 C1 look (1911 PDF 10) had seen a French page.
    "ANNO_e6g_": (("latino-sine-flexione", "french"), _C17("Lingua Internationale (1911–12): mostly Latino sine flexione (Peano's Interlingua), with French articles; Latin quoted; re-declared 2026-10-23 from the word-list scores (71 of 84 pages Latino sine flexione)")),
    "ONB_e1n_": (("esperanto", "german"), _C17("Vespera Horo / Abendstunde (1910): Esperanto and German in parallel columns")),
})
_C18A_OK = ("editor 2026-10-23 16:2x (the declarations spelled out per title in geniza/ocr/runs/CUPEL18A-C5-DECLARATIONS-PROPOSAL-2026-10-23.md: languages in order, the main first; the evidence, the C1 look of 2026-10-23, ten pages, cupel-batch-18a/c1-look/, and the page check ocr/runs/OCR-PAGE-LANGUAGES-2026-10-23-cupel18a.md; the effect, the list that scores it and the passes licensed)")
_C18A = lambda seen: f"cupel18a, C1 look 2026-10-23 ({seen}); " + _C18A_OK
DECLARED.update({
    # cupel18a: Svisa Espero, Franca Esperantisto, Bulgara Esperantisto (ÖNB/ANNO) and three Ido-era books (archive.org)
    "ANNO_e5a_": (("esperanto", "german", "french"), _C18A("Svisa Espero (1903–16): Esperanto, with German and French running text in the group reports; pages won 1,394 / 134 / 42 of 1,573")),
    "ANNO_e3s_": (("esperanto", "french"), _C18A("Franca Esperantisto (1908–12): two columns, French notices beside Esperanto; pages won 692 / 331 of 1,023")),
    "ANNO_e4h_": (("esperanto", "bulgarian"), _C18A("Bulgara Esperantisto (1907): Esperanto beside Bulgarian in pre-reform Cyrillic; the Bulgarian-only route (orus), as for Rondiranto")),
    "couturat_pour_la_langue_internationale_1906": (("french",), _C18A("Couturat, Pour la langue internationale, 4th ed. 1906: French throughout, 30 of 30 pages")),
    "talmey_filologiala_temi_1923": (("ido", "english-cited"), _C18A("Talmey, Filologiala temi (1923): Ido, 40 of 45 pages; English only in the trilingual grammatical key, PDF pp. 4–5")),
    "schrey_federn_koresteno.part": (("ido",), _C18A("Schrey and Federn, Koresteno (1932), the title and pp. 13, 15, 16: Ido")),
})
_C18B_OK = ("editor 2026-10-26 11:3x (the declarations spelled out per volume in geniza/ocr/runs/CUPEL18B-C5-DECLARATIONS-PROPOSAL-2026-10-26.md: "
            "the languages in order, the main first; the evidence, the C1 look of 2026-10-26 and the page languages; the effect)")
_C18B = lambda seen: f"cupel18b, C1 look 2026-10-26 ({seen}); " + _C18B_OK
DECLARED.update({
    # cupel18b: Tutmonda Jarlibro Esperantista 1904–1910 (ÖNB/ANNO), directories of societies and Esperantists
    "ANNO_e4d_19040005": (("esperanto", "french"), _C18B("Tutmonda Jarlibro 1904: Esperanto entries, French in their descriptions; pages won 217 / 16 of 242")),
    "ANNO_e4d_19050005": (("esperanto", "french"), _C18B("Tutmonda Jarlibro 1905: pages won Esperanto 375, French 22 of 414")),
    "ANNO_e4d_19060005": (("esperanto", "french"), _C18B("Tutmonda Jarlibro 1906: pages won Esperanto 482, French 34, Spanish 15 of 543")),
    "ANNO_e4d_19070005": (("esperanto", "french"), _C18B("Tutmonda Jarlibro 1907: pages won Esperanto 386, French 41 of 454")),
    "ANNO_e4d_19080005": (("esperanto",), _C18B("Tutmonda Jarlibro 1908: pages won Esperanto 207 of 215, French 2")),
    "ANNO_e4d_19090005": (("esperanto",), _C18B("Tutmonda Jarlibro 1909: pages won Esperanto 237 of 248, French 4")),
    "ANNO_e4d_19100005": (("esperanto",), _C18B("Tutmonda Jarlibro 1910: pages won Esperanto 222 of 237, French 6")),
})
_C18C_OK = ("editor 2026-10-26 22:2x (the declarations spelled out per title in geniza/ocr/runs/CUPEL18C-C5-DECLARATIONS-PROPOSAL-2026-10-26.md: "
            "the languages in order, the main first; the evidence, the C1 look of 2026-10-26 and the page languages; the effect)")
_C18C = lambda seen: f"cupel18c, C1 look 2026-10-26 ({seen}); " + _C18C_OK
DECLARED.update({
    # cupel18c: the rest of the cupel18 slice (ÖNB/ANNO) and de Beaufront's Louis Couturat (1914)
    "ANNO_e7p_": (("esperanto",), _C18C("Danubo 1910–12: pages won Esperanto 642 of 642; Romanian, Bulgarian only in names")),
    "InternaciaSciencaRevuo_1904": (("esperanto",), _C18C("Internacia Scienca Revuo 1904: pages won Esperanto 431 of 440; French, German, English cited")),
    "ONB_e3k_": (("italian", "esperanto"), _C18C("Itala Esperanto-Revuo 1913–14: pages won Italian 210, Esperanto 138 of 354; Italian the main in 34 of 37 issues, three tied")),
    "ANNO_e7s_": (("italian", "esperanto"), _C18C("Itala Esperantisto 1911–14: pages won Italian 244, Esperanto 99 of 344; Italian the main in every issue")),
    "ANNO_e1k_": (("esperanto", "german"), _C18C("Informaj Raportoj 1908–10: pages won Esperanto 201, German 27 of 228")),
    "ANNO_e7i_": (("esperanto",), _C18C("the TEKA Jarlibro 1909–10: pages won Esperanto 178 of 178")),
    "117C5F54_pdf_1-76": (("esperanto",), _C18C("the Oficiala Bulteno de T.E.K.A. 1911–12: pages won Esperanto 73 of 73; French cited")),
    "ANNO_e7r_": (("esperanto", "italian"), _C18C("Roma Esperantisto 1908: parallel columns; pages won Esperanto 118, Italian 47 of 165")),
    "ANNO_e6w_": (("esperanto", "spanish"), _C18C("Stelo Kataluna 1908: parallel columns; pages won Esperanto 89, Spanish 11 of 100; Catalan cited")),
    "beaufront.couturat.1914": (("ido", "french"), _C18C("de Beaufront, Louis Couturat (Paris 1914): Ido and French on facing pages; pages won Ido 6, French 5 of 11")),
    # outside the batch, put with it: the Coulommiers memorial volume (signed 2026-10-02), «esperanto, french» from the gate before
    "Louis Couturat_1868-1914": (("french", "ido"), "the text French with Ido passages (no «estas», «kaj» in 28,220 words; «esas», «qua»); page languages 2026-10-26 22:2x: French 64, Ido 3 of 67; " + _C18C_OK),
})
RULED = {"StSl2017_XIV": (("arabic-script",), None,
                          "decided by the editor, 2026-10-04: the PDF text layer garbles a transliteration "
                          "font on 98 pages into shifted Latin and Arabic letters and digits — not Arabic"),
         "ondodeesperanto.": (("cyrillic-unspecified", "russian?", "cyrillic?", "cyrillic-cited"), "russian",
                              "decided by the editor, 2026-10-03"),
         "mondo": (("russian?", "cyrillic?", "cyrillic-unspecified"), None,
                   "decided by the editor, 2026-10-01"),
         "mondo1930-1931": (("occidental",), "novial", "the gate has no Novial model and reports Occidental (Novial «me/lo/vud/sal» against Occidental «yo/it/quel», 2026-10-10 17:4x); decided by the editor, 2026-10-10, confirmed that the language table say Novial for these three"),
         "mondo1932": (("occidental",), "novial", "the gate has no Novial model and reports Occidental (Novial «me/lo/vud/sal» against Occidental «yo/it/quel», 2026-10-10 17:4x); decided by the editor, 2026-10-10, confirmed that the language table say Novial for these three"),
         "reu-bofron-esenco-1906": (("esperanto",), None, "the declaration holds over the gate, whose «esperanto» is read on the Latin-script text alone of a Russian book (the cupel7-3 gate, 2026-10-10 22:2x); decided by the editor, 2026-10-10"),
         "reu-pola-adresaro-1909": (("polish",), None, "the declaration holds over the gate: Polish in names and addresses only (C1 look, 2026-10-10); decided by the editor, 2026-10-10"),
         "NOVIALISTE.": (("occidental",), "novial", "the gate has no Novial model and reports Occidental (Novial «me/lo/vud/sal» against Occidental «yo/it/quel», 2026-10-10 17:4x); decided by the editor, 2026-10-10, confirmed that the language table say Novial for these three")}
# cupel17 Before C0 (2026-10-20 21:5x): the rebuilt table added «esperanto» from the gate to four Russian cupel16 items; the editor kept them as confirmed
RULED.update({
    "drezen_za_vseobshchim_yazykom_1928": (("esperanto",), None, "editor 2026-10-20 21:5x, on the language table rebuilt from the cupel16-6 gate: these four Russian items, signed 2026-10-20 13:35 on their Russian side, stay Russian only; the gate reads their few Latin-script titles as Esperanto"),
    "nov_bulgakov_vp": (("esperanto",), None, "editor 2026-10-20 21:5x, on the language table rebuilt from the cupel16-6 gate: these four Russian items, signed 2026-10-20 13:35 on their Russian side, stay Russian only; the gate reads their few Latin-script titles as Esperanto"),
    "nov_gruzintsev_vp": (("esperanto",), None, "editor 2026-10-20 21:5x, on the language table rebuilt from the cupel16-6 gate: these four Russian items, signed 2026-10-20 13:35 on their Russian side, stay Russian only; the gate reads their few Latin-script titles as Esperanto"),
    "nov_anonsy_knig_bika": (("esperanto",), None, "editor 2026-10-20 21:5x, on the language table rebuilt from the cupel16-6 gate: these four Russian items, signed 2026-10-20 13:35 on their Russian side, stay Russian only; the gate reads their few Latin-script titles as Esperanto"),
    # cupel17 C7 (2026-10-23): the table rebuilt for the Lingua Internationale re-declaration added «russian» to Rondiranto
    "ANNO_e1v_": (("russian", "russian?"), None, "editor 2026-10-23, on the language table rebuilt after cupel17's chain: Rondiranto's pre-reform Bulgarian, read with the Russian model, gives Russian-list words on 8 of 12 pages (lex); it stays Esperanto and Bulgarian, the Bulgarian-only route"),
})
# cupel18c C5 (2026-10-26 22:2x): the Coulommiers volume's «esperanto» came from the gate and the look of 2026-09-26/10-03
# («French, with Esperanto examples»): the examples are Ido; the editor confirmed «french, ido» (on
# geniza/ocr/runs/CUPEL18C-C5-DECLARATIONS-PROPOSAL-2026-10-26.md)
RULED.update({
    "Louis Couturat_1868-1914": (("esperanto",), None, "editor 2026-10-26 22:2x («french, ido»): the look's «Esperanto examples» are Ido (no «estas», «kaj» in 28,220 words; «esas», «qua»)"),
})
NOT_A_LANGUAGE = re.compile(r"-(names|addresses|romanised|lacinka|show-through)$|^(not-stated|not-verifiable|latin-only|"
                            r"latin-unspecified|examples-several-languages|auxlang-.*|ipa|languages_seen)$")
ALIAS = {"occidental-interlingue": "occidental", "russian-name": None}


def norm(s):
    return re.sub(r"[^0-9a-zа-я]", "", s.lower())


def rows(path):
    return list(csv.DictReader((l for l in open(path, encoding="utf-8") if not l.startswith("#")), delimiter="\t"))


MAIN_CONFLICTS = []   # (item, the gate's first language, the declared main): Latin-script disagreements, for the editor


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evidence"); ap.add_argument("looks", nargs="+", help="look-evidence TSVs (the harvest, then later looks)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    ev = {r["item"]: r for r in rows(a.evidence)}
    byn = {norm(k): k for k in ev}
    s = importlib.util.spec_from_file_location("led", os.path.join(HERE, "ocr-absence-ledger.py"))
    led = importlib.util.module_from_spec(s); s.loader.exec_module(led)
    greek_ruled = {k for k, v in led.PRESENCE_ONLY_NAMED.items() if "Greek" in v}

    look = collections.defaultdict(lambda: collections.defaultdict(set))   # item → language → pages
    unmatched = collections.Counter()
    latin_only = collections.defaultdict(set)   # item → pages a look saw with NO non-Latin script (evidence of absence)
    for r in (x for f in a.looks for x in rows(f)):
        item = r["item"].strip()
        if item not in ev:
            item = byn.get(norm(item)) or next((k for n, k in byn.items() if norm(r["item"]) and n.startswith(norm(r["item"]))), None)
        if not item:
            unmatched[r["item"]] += 1; continue
        if "latin-only" in r["languages_seen"]:
            latin_only[item].add(r["pdf_page"])
        for lang in (x.strip() for x in r["languages_seen"].split(",")):
            lang = ALIAS.get(lang, lang)
            if lang and not NOT_A_LANGUAGE.search(lang):
                look[item][lang].add(r["pdf_page"])

    out = []
    MAIN_CONFLICTS.clear()
    n = lambda r, k: int(r.get(k) or 0)
    for item, r in sorted(ev.items()):
        L = collections.OrderedDict()   # language → [evidence]
        def add(lang, src):
            L.setdefault(lang, []).append(src)
        if r["primary"]:
            add(r["primary"], "gate")
        for x in filter(None, r["latin_seconds"].split(",")):
            add(x, "gate")
        for lang, pages in look[item].items():
            add(lang, f"look:{len(pages)}")
        for prefix, (langs_, why) in DECLARED.items():
            if item.startswith(prefix):
                for x in langs_:
                    add(x, f"declared:{why}")
        doubt, notes = [], []
        cyr, lex = n(r, "auth_cyrillic"), n(r, "rus_lex_pages")
        cw, rw, bg, uk = (n(r, k) for k in ("auth_cyr_words", "auth_ru_letter_words", "auth_bg_words", "auth_uk_words"))
        cited = cw < CITED   # a few Cyrillic names or titles in an otherwise Latin text
        # WHICH Cyrillic language (step 3, 2026-10-03 19:0x), by letters in the authoritative readings: є ї ґ Ukrainian;
        # ъ inside a word and no ы э ё Bulgarian; ы э ё Russian. The word-list share does not separate them.
        if uk >= 5 or n(r, "ukr"):
            add("ukrainian", f"auth:{max(uk, n(r, 'ukr'))}")
            ukl_ = n(r, "auth_uk_list_permille")
            if ukl_ > n(r, "auth_ru_list_permille"):
                L["ukrainian"].append(f"list:{ukl_}‰")
        bgl, ukl, rul = (n(r, f"auth_{k}_list_permille") for k in ("bg", "uk", "ru"))
        if bg >= 2 and not rw:
            add("bulgarian", f"auth-words:{bg}")
            if bgl > rul:
                L["bulgarian"].append(f"list:{bgl}‰ (ru {rul}‰)")
            else:
                doubt.append(f"Bulgarian letters but the Bulgarian list does not confirm ({bgl}‰ vs ru {rul}‰)")
        if n(r, "bel"):
            add("belarusian", f"auth:{n(r, 'bel')}")
        other_cyr = any(k in L for k in ("ukrainian", "bulgarian", "belarusian"))
        # lex alone needs >= 5 pages: *Mondo* 1924 has 2 such pages and no Russian (editor 2026-10-01 00:44, «There IS no
        # Russian in Mondo, that was poor quality OCR»; ocr-absence-ledger.py FALSE_BISCRIPT)
        # Beside Bulgarian, Ukrainian or Belarusian, the Russian model's word counts are not evidence of Russian: their words
        # overlap the Russian list (*Rondiranto*, cupel17, 2026-10-23: pre-reform Bulgarian, Russian-list words on 8 of 12
        # pages). Russian there needs its own letters (rw); the editor 2026-10-23.
        if "russian" in L:
            pass                                          # a look saw it
        elif other_cyr and lex and not rw:
            notes.append(f"Russian-list words on {lex} page(s) of the Russian-model reading not counted: "
                         f"{', '.join(k for k in ('bulgarian', 'ukrainian', 'belarusian') if k in L)} shown, whose words overlap the Russian list")
        elif lex >= 5:
            add("russian", f"lex:{lex}")
        elif cyr and (rw or (lex and not other_cyr)):
            add("russian-cited" if cited else "russian", f"auth-words:{rw}" if rw else f"lex:{lex}")
        elif cyr and not other_cyr:
            if cited:
                add("cyrillic-cited", f"auth-words:{cw}")
            else:
                add("cyrillic?", f"auth-words:{cw}"); doubt.append("Cyrillic, language not shown by its letters")
        elif lex and not cyr:
            # the language look of 3 Oct (an internal record, 2026-10-03, not published): where a blind look saw the item's pages and
            # NO non-Latin script, Russian-list words on 1–4 pages are junk (Estonian Fraktur, Polish, Esperanto)
            if latin_only[item] and not any(SCRIPT_OF.get(x) == "cyrillic" for x in look[item]):
                notes.append(f"Russian-list words on {lex} page(s) are junk: a blind look saw pages "
                             f"{','.join(sorted(latin_only[item], key=int))} with no non-Latin script")
            else:
                add("russian?", f"lex:{lex}"); doubt.append("Russian-list words on 1–4 pages of a Russian-model reading only")
        if n(r, "srp_mkd"):
            if n(r, "srp_mkd") <= 2:       # the editor asked for details, 19:0x: Sokolova, *Studia Slavica* — Russian linguistics
                add("serbian-cited", f"auth:{n(r, 'srp_mkd')}")   # citing Serbian words, letters and a Belić title
            else:
                add("serbian-or-macedonian?", f"auth:{n(r, 'srp_mkd')}"); doubt.append("ђ ј љ њ ћ џ ѓ ќ ѕ on 3+ pages")
        for prefix, (frms, to, why) in RULED.items():
            if item.startswith(prefix):
                for frm in frms:
                    if frm in L:
                        if to and to not in L:   # a rename keeps the language's place (2026-10-10: Mondo 1932's
                            # «occidental» → «novial» had moved to the end, making English its first language)
                            L = collections.OrderedDict((to if k == frm else k, (v + [f"ruling:{why}"] if k == frm else v))
                                                        for k, v in L.items())
                            continue
                        ev_ = L.pop(frm)
                        if to:
                            L.setdefault(to, []).extend(ev_ + [f"ruling:{why}"])
                        else:
                            notes.append(f"{frm} dropped by ruling: {why}")
                if to in L or not to:
                    doubt[:] = [d for d in doubt if not d.startswith(("Russian-list", "Cyrillic"))]
        if n(r, "auth_greek"):
            add("greek", f"auth:{n(r, 'auth_greek')}")
        if n(r, "auth_greek_polytonic"):
            add("greek-polytonic", f"auth:{n(r, 'auth_greek_polytonic')}")
        if item in greek_ruled:
            add("greek", "ruling")
        for k in ("georgian", "armenian"):
            if n(r, f"auth_{k}"):
                add(k, f"auth:{n(r, f'auth_{k}')}")
            if r["kathye_mask"]:
                add(k, "mask")
        if n(r, "auth_hebrew"):
            # the editor judged on 2026-10-03 19:0x that Hebrew script is likely Hebrew, but was not sure
            add("hebrew", f"auth:{n(r, 'auth_hebrew')}"); add("hebrew", "ruling:likely")
            notes.append("Hebrew per decided by the editor; Posta Mundi 20 p. 7 reads as Ido in Hebrew letters, "
                         "HV-13032018 p. 34 also prints Yiddish")
        # OTHER SCRIPTS, BY NEGOTIATION (the editor ruled on 2026-10-04 03:0x that other scripts are settled by negotiation:
        # Japanese, Arabic, Chinese and Greek are all possible, other Asian scripts unlikely but not ruled out; RUNBOOK.md C6.5): the
        # table records them so they can be put to the editor; running text (not cited) is flagged DOUBT for that.
        for col, lang in (("auth_arabic", "arabic-script"), ("auth_kana", "japanese"), ("auth_han", "chinese-script"),
                          ("auth_hangul", "korean"), ("auth_other_script", "other-script")):
            if n(r, col) and not (lang == "chinese-script" and n(r, "auth_kana")):   # han beside kana is Japanese
                add(lang, f"auth:{n(r, col)}")
        # the rulings again, for the entries just added (a ruling that DROPS a script, e.g. Studia Slavica's fake Arabic)
        for prefix, (frms, to, why) in RULED.items():
            if item.startswith(prefix) and to is None:
                for frm in frms:
                    if frm in L:
                        L.pop(frm); notes.append(f"{frm} dropped by ruling: {why}")
        # CITED, EVERY SCRIPT (approved by the editor 2026-10-03 19:5x, after the editor asked what BK-I-2015 is, why it has
        # Greek in it, and where the Japanese came from): Pabst's *Berlina Komentario* cites Greek etymons of the affixes
        # on 3–4 of 392 pages; *Ruslanda Esperantisto* 1910.1 prints one Japanese line in an advert. A script on < CITED_SHARE
        # of the item's pages, or seen by a look on one page with no reading of it, is CITED — unless a ruling, the mask
        # or a declaration stands behind it (the editor's judgement that Hebrew is likely names the language, not its extent).
        npg = max(n(r, "pages"), 1)
        for lang in list(L):
            base = lang.rstrip("?")
            scr = SCRIPT_OF.get(base)
            if scr in (None, "latin") or base.endswith("-cited") or base == "cyrillic-unspecified":
                continue
            ev_ = L[lang]
            if any(e.startswith(("mask", "declared")) or (e.startswith("ruling:") and "likely" not in e) for e in ev_):
                continue
            lp = max([int(e.split(":")[1]) for e in ev_ if re.fullmatch(r"look:\d+", e)] or [0])
            ap = (n(r, "auth_greek") + n(r, "auth_greek_polytonic") if scr == "greek" else
                  n(r, f"auth_{scr}") if scr in ("georgian", "armenian", "hebrew") else
                  max(n(r, "auth_kana"), n(r, "auth_han")) if scr == "japanese" else
                  n(r, {"arabic": "auth_arabic", "han": "auth_han", "hangul": "auth_hangul",
                        "other": "auth_other_script"}.get(scr, "")) if scr in ("arabic", "han", "hangul", "other") else 0)
            if scr == "cyrillic":          # Cyrillic keeps its own word rule above; here only the one-page look sighting
                if base == "russian":      # of a language with no reading behind it (*Ruslanda* 1906.8: one Ukrainian title)
                    continue
                # 21:2x: judged by PAGE SHARE like the other scripts (was: only a one-page look sighting, and Bulgarian was
                # looked up in the wrong column, srp_mkd, so it came out «cited» by accident). Pages that show the
                # language: its marker letters (ukr, bel), or for Bulgarian the pages with Cyrillic at all.
                ap = n(r, {"ukrainian": "ukr", "belarusian": "bel", "bulgarian": "auth_cyrillic"}.get(base, "srp_mkd"))
                cited_ = max(lp, ap) / npg < CITED_SHARE or (not ap and lp <= 1)
                label = f"share:{max(lp, ap)}/{npg}pp"
            elif ap:
                # the editor ruled on 2026-10-04 03:3x (Q1) that these are citations, the bar being the greater of 5% or 5 words: a script
                # with authoritative readings is CITED when its distinct words are fewer than the greater of 5% of the item's
                # distinct words, or 5 (short items cite a few names: IpI 130's Japanese, Posta Mundi 8's Chinese, 38's Telugu)
                col = {"greek": ("auth_greek_words",), "japanese": ("auth_kana_words", "auth_han_words"),
                       "han": ("auth_han_words",), "hangul": ("auth_hangul_words",), "other": ("auth_other_script_words",)
                       }.get(scr, (f"auth_{scr}_words",))
                words = sum(n(r, k) for k in col)
                cited_ = words < max(CITED_SHARE * n(r, "auth_all_words"), 5)
                label = f"words:{words}/{n(r, 'auth_all_words')}"
            else:   # seen by a look only: by page share, as before
                cited_ = lp / npg < CITED_SHARE or lp <= 1
                label = f"share:{lp}/{npg}pp"
            if cited_:
                L[f"{base}-cited"] = L.pop(lang) + [label]
                doubt[:] = [d for d in doubt if "Hebrew" not in d] if base == "hebrew" else doubt
                notes[:] = [x for x in notes if not x.startswith("Hebrew per")] if base == "hebrew" else notes
        for x in ("arabic-script", "japanese", "chinese-script", "korean", "other-script"):
            if x in L and not any(e.startswith(("ruling:", "declared:")) for e in L[x]):
                doubt.append(f"{x} as running text: by negotiation with the editor (cupel runbook C6.5)")
        if "cyrillic-unspecified" in L and not any(SCRIPT_OF.get(x.rstrip("?")) == "cyrillic" and x != "cyrillic-unspecified" for x in L):
            doubt.append("Cyrillic seen in a look, language not named")
        # THE DECLARED MAIN LANGUAGE, IN A NON-LATIN SCRIPT, LEADS (2026-10-14, the fix approved by the editor): the gate scores
        # Latin-script text only (mostly-Cyrillic pages skipped), so its «primary» for a Russian-main item comes from the
        # item's few Latin bits (Belousov 1975 and 1985, Informilo 1926–27: «esperanto» put ahead of the declared Russian).
        # Where the declared main is a Latin-script language and the gate disagrees (La Belga Sonorilo's Ido years:
        # declared esperanto, the gate ido), the gate MEASURED, so its order stands and the row is listed for the editor.
        decl = next((d for p, (d, _) in sorted(DECLARED.items(), key=lambda kv: -len(kv[0])) if item.startswith(p)), None)
        dmain = next((x for x in decl if not x.endswith("-cited")), None) if decl else None
        # Nor where the gate has no model for the declared main (Lingua Internationale, re-declared 2026-10-23 on the
        # editor's: Latino sine flexione, which the gate cannot report, so it said French).
        if dmain and dmain in L and next(iter(L)) != dmain:
            if SCRIPT_OF.get(dmain, "latin") != "latin":
                L.move_to_end(dmain, last=False)
                notes.append(f"the declared main language ({dmain}) leads: the gate cannot judge a {SCRIPT_OF[dmain]}-script item")
            elif dmain in ("latino-sine-flexione",):
                L.move_to_end(dmain, last=False)
                notes.append(f"the declared main language ({dmain}) leads: the gate has no model for it")
            else:
                MAIN_CONFLICTS.append((item, next(iter(L)), dmain))
        langs = [x for x in L if x != "cyrillic-unspecified" or len([y for y in L if SCRIPT_OF.get(y.rstrip('?')) == 'cyrillic']) == 1]
        scripts = sorted({SCRIPT_OF.get(x.rstrip("?"), SCRIPT_OF.get(x.rstrip("?").removesuffix("-cited"), "latin"))
                          for x in langs})   # a cited script is still PRINTED: it stays in the scripts column
        flags = []
        licensed = [x for x in langs if SCRIPT_OF.get(x.rstrip("?")) == "cyrillic" and not x.endswith("-cited")]
        if n(r, "rus_read_pages") and not licensed:
            flags.append(f"RUS-READ-NO-RUSSIAN ({n(r, 'rus_read_pages')} pages read"
                         + (", Cyrillic cited only)" if "cyrillic" in scripts else ")"))
        if doubt:
            flags.append("DOUBT: " + "; ".join(doubt))
        if notes:
            flags.append("NOTE: " + "; ".join(notes))
        out.append([item, ",".join(langs), ",".join(scripts),
                    "; ".join(f"{k}[{','.join(v)}]" for k, v in L.items()), " | ".join(flags)])

    with open(a.out, "w", encoding="utf-8") as o:
        o.write(f"# GENERATED by tools/ocr-text-languages-table.py from {os.path.basename(a.evidence)} + "
                f"{' + '.join(os.path.basename(f) for f in a.looks)} + the editor's rulings. THE FILTER: no pass reads a text with a language's "
                f"model, writes its search file, or labels it bi-script in it, unless this table lists that language.\n")
        o.write("item\tlanguages\tscripts\tevidence\tflags\n")
        for x in out:
            o.write("\t".join(x) + "\n")
    c = collections.Counter(s for x in out for s in x[2].split(","))
    print(f"{len(out)} items → {a.out}; scripts: {dict(c)}")
    if MAIN_CONFLICTS:
        print(f"declared main overruled by the gate (Latin script; for the editor): {len(MAIN_CONFLICTS)}")
        for it, g, d in MAIN_CONFLICTS:
            print(f"  {it}: gate {g}, declared {d}")
    print(f"RUS-READ-NO-RUSSIAN {sum('RUS-READ-NO-RUSSIAN' in x[4] for x in out)}; DOUBT {sum('DOUBT' in x[4] for x in out)}")
    if unmatched:
        print(f"look rows not matched to an item ({sum(unmatched.values())}): {dict(unmatched)}")


if __name__ == "__main__":
    main()
