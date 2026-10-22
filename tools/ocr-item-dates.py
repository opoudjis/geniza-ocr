#!/usr/bin/env python3
r"""ocr-item-dates — when each book was written or published, and so its kind (PRIMARY / SECONDARY), with the evidence.

    tools/ocr-item-dates.py --out geniza/ocr/runs/OCR-ITEM-DATES.tsv

WHY (2026-10-09: the editor ruled that anything written before 1914 is primary, that being the actual distinction; that
Zakrzewski is an exception, secondary by genre, and that this exception before 1914 be applied very explicitly; that
dating is crucial for the dowse; and that the date must therefore be findable). One row per item of the item table that is not a
periodical, and per periodical row with no year of its own (the rest are dated by their issues). `tools/ocr-item-table.py` reads this file into its `written` and
`kind` columns, so the date is found where every other fact about a file is.

HOW, strongest evidence first; the first that gives a year wins:
  ruled      a year or kind ruled by the editor (RULED below, quoted)
  table      the item table's own `year` (from the file name or a check)
  name       a year in the file name
  imprint    a year on the first 4 or the last PDF page on a line with an imprint word (©, Copyright, ISBN, eldonis,
             eldonejo, presejo, Verlag, Druck, Imprimerie …; not a city alone): the LATEST such year
  page       a year alone on a title page line (first 4 PDF pages): the latest
  none       nothing found: for a look
A part of a work filed in pieces (ENCYCL_ / ANTOL_ / COUVERTURE parts) takes the year its parts agree on.
KIND: written in 1914 or before → PRIMARY, 1915 or later → SECONDARY, except where RULED names it (1914 INCLUSIVE: the
editor ruled on 2026-10-10, 18:1x, that the limit for Esperanto be 1914 inclusive, and that for Ido it stay 1931
exclusive; the rule had been «before 1914»). WRITTEN, not published,
decides (the editor ruled on 2026-10-09, 14:1x, that pieces written, not published, before the cutoff are primary; no separate ruling).
For Idists the cutoff is 1931, the relaunch of Progreso (the editor deferred this at 14:1x): NOT YET
applied. A year found is a year of
PUBLICATION; a later edition of earlier writing (letters, documents, records) is flagged «documents?» for a ruling,
since the rule is the date of WRITING.
WRITE-SET: --out only, refused if it exists (choose a new name; the item table reads the newest).
"""
import os, re, sys, glob, argparse, importlib.util, collections, csv

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, os.path.join(HERE, p)); m = importlib.util.module_from_spec(s)
    a = sys.argv; sys.argv = [a[0]]; s.loader.exec_module(m); sys.argv = a; return m

RULED = {   # item → (year or None, kind or None, the ruling)
    # 2026-10-17, cupel14 C10 (the editor approved at 13:0x the three dates put to him, ruling Wilson contemporary and so primary):
    "ANNO_e0g_19220012": (1972, "SECONDARY", "not a 1922 issue but a typed plan of the run «Plan de aparition de Kosmoglott 1922–1926 e Cosmoglotta 1927–1972», c. 1972, signed F.L. (C1 look 2026-10-16); decided by the editor, 2026-10-16, kept as its own item, SECONDARY by date; 2026-10-17 «yes»"),
    "wilson.third.esperanto.congress": (1907, "PRIMARY", "Wilson's pamphlet on the Third Esperanto Congress, Cambridge 1907, undated in the tool's reading; decided by the editor, 2026-10-17"),
    "samuel.interhelpo": (1935, "SECONDARY", "the imprint (Moscow, «Дер Эмес», 1935; C1 look 2026-10-16), not the «1926» of a citation on PDF p. 4 that the tool read; decided by the editor, 2026-10-17"),
    "devjatnin-malhimno-postcard": (1921, "SECONDARY", "decided by the editor, 2026-10-17; c. 1921 by its "
                                    "postmark «14. 8. 2[.]» (as read 2026-10-16), not our transcription's 2026"),
    "Zakrzewski - Historio de Esperanto, 1913": (1913, "SECONDARY", "the editor ruled on 2026-10-09 that it is an "
                                                "exception: secondary by its genre, an exception before 1914 that "
                                                "is to be applied explicitly"),
    "Nova dokumento pri la rilato de Zamenhof al Volapuk": (None, "PRIMARY", "the editor ruled on 2026-10-09: primary, even "
                                                            "if it yields nothing"),
    "L_ido_et_l_espéranto_suite_à_l_histori": (1911, "PRIMARY", "decided by the editor, 2026-10-09"),
    "Esperanto_movado_kaj_homaj_rajtoj": (2016, "SECONDARY", "decided by the editor, 2026-10-09"),
    # the editor's rulings of 2026-10-09 16:5x, on the pre-1914 histories and studies (an internal record, 2026-10-09, not published):
    "Historio_kaj_teorio_de_Ido": (None, "PRIMARY", "decided by the editor, 2026-10-09"),
    "logika bazo de vortfarado en Esperanto": (None, "SECONDARY", "the editor ruled on 2026-10-09: Esperanto linguistics, "
                                                                  "secondary (with Couturat's Studyo)"),
    "STUDYO_PRI_LA_DERIVADO": (None, "SECONDARY", "decided by the editor, 2026-10-09 (with "
                                                  "de Saussure's Logika bazo)"),
    # translators' prefaces, items of their own (2026-10-10 17:1x: the editor ruled the three period ones PRIMARY);
    # their texts hold only the preface, so no header dates them
    "tekstaro-la-batalo-de-l-vivo-antauparolo": (None, "PRIMARY", "decided by the editor, 2026-10-10: "
        "PRIMARY (Zamenhof's preface, written for a re-edition after 1891; year to be looked up)"),
    "tekstaro-elektitaj-fabeloj-antauparolo": (1906, "PRIMARY", "Kabe's preface, signed «Varsovio, junio 1906»; the "
        "editor ruled on 2026-10-10: PRIMARY"),
    # The Somme records on De Beaufront (an internal record, 2026-10-12, not published). A rule was proposed, and the editor
    # adopted it on 2026-10-12, 00:4x, as consistent: civil records are PRIMARY by the record's own year, whatever the year (the 1915 and 1931
    # cutoffs are for movement writing); modern web indexes of civil records are SECONDARY (compilations, not the registers).
    **{f"ad80-{k}": (int(k[-4:]), "PRIMARY", "a civil record, our transcription; PRIMARY by the record's year (the editor "
        "2026-10-12 00:4x, the Somme records ruling)") for k in (
        "grivesnes-liste-electorale-1912", "grivesnes-liste-electorale-1919", "grivesnes-liste-electorale-1920",
        "grivesnes-recensement-1911", "grivesnes-recensement-1921", "grivesnes-recensement-1926", "grivesnes-recensement-1931",
        "marestmontiers-recensement-1926", "marestmontiers-recensement-1931", "thezy-glimont-recensement-1926",
        "thezy-glimont-recensement-1931")},
    "sat-amikaro-2014-bofronto-mortakto": (1935, "PRIMARY", "De Beaufront's death record (1935), our transcription of the "
        "record as published by SAT-Amikaro in 2014; PRIMARY by the record's year (the editor 2026-10-12 00:4x)"),
    "acte-de-naissance-fr-grivesnes-guerard": (None, "SECONDARY", "a modern web index of a civil record, not the register: "
        "SECONDARY (the editor 2026-10-12 00:4x, the Somme records ruling)"),
    "acte-deces-fr-famille-guerard": (None, "SECONDARY", "a modern web index of civil records, not the registers: SECONDARY "
        "(the editor 2026-10-12 00:4x, the Somme records ruling)"),
    "tekstaro-pola-antologio-antauparolo": (1905, "PRIMARY", "Th. Cart's preface, signed «En Parizo, la vesperon de la 12a "
        "de Marto 1905» (not the header's «Proksimuma tradukojaro: 1906»); the editor ruled on 2026-10-10: PRIMARY"),
    "tekstaro-kastelo-de-prelongo-antauvorto": (1957, "SECONDARY", "the foreword: «En 1957, okaze de la 50-jara jubileo», so "
        "1957 or later (2026-10-10)"),
    # the HISTORICAL ACCOUNTS RULING (the editor, 2026-10-10 17:4x): the rule of language is overridden when the text is
    # an historical account, as this one is; Dyer is indeed primary, as a contemporary history would be in any language;
    # for contemporary history, as opposed to propaganda, the witness is the point, not the language
    "dyer-problem-ido-1923": (1922, "PRIMARY", "Dyer, The Problem of an International Auxiliary Language and its Solution "
        "in Ido (1923), preface signed November 1922; PRIMARY by the editor's historical-accounts ruling, 2026-10-10 17:4x"),
    "witteryck-waarheid-esperanto-ido": (1913, None, "Witteryck, De waarheid over Esperanto en Ido / La vérité sur l'Esperanto "
        "et l'Ido, signed in the text «Januari 1913» (2026-10-10); PRIMARY by the date rule"),
    "tekstaro-post-la-granda-milito": (None, "PRIMARY", "the editor ruled on 2026-10-10, on Zamenhof's «Post la granda milito», "
                                                        "written 1914, that Zamenhof is an exception"),
    "Weltsprache und Wissenschaft": (None, "PRIMARY", "the editor ruled on 2026-10-09: primary, contemporary polemic and "
                                                      "history"),
    "LaJubileaKongresoDeEsperanto_1912_kul46721": (1912, "PRIMARY", "La Jubilea Kongreso de Esperanto (the 1912 congress; "
        "imprint «Copyright 1937 by J. Muusses – Purmerend»): the editor ruled on 2026-10-14: contemporary pieces, "
        "anthologised in 1937, so primary; no reason to think a page is missing"),
}
# Years from archive.org's own item records (on the editor's decision of 2026-10-09, 17:0x, to try these items again
# there), fetched 2026-10-09; taken only where the record is the same work and its «date» is not
# merely the upload date. item → (year or None, kind or None, identifier, what it rests on)
ARCHIVE_ORG = {
    "Nia metodo_text": (1909, None, "Nia_metodo", "«Pri nia metodo», date 1909-12"),
    "Rapport au comite_text": (1907, None, "rapport_au_comite", "«Rapport au Comité sur l'état présent de la question de …», date 1907-09-12"),
    "Nova Horizonti_text": (1919, None, "NovaHorizonti", "«Nova Horizonti», date 1919-01-01"),
    "The Artificial Language Movement": (1985, None, "artificiallangua0000larg", "«The artificial language movement», date 1985"),
    "Postcards, Translators and Esperanto Pioneers": (2025, None, "802820ed-a809-40a1-b4f1-0d6728949709", "«Postcards, Translators and Esperanto Pioneers: An Alternative History …», date 2025-11-13"),
    "Recenzo_pri_Universalaj_Lingvoj_en_Svislando": (2009, None, "recenzo-pri-universalaj-lingvoj-en-svisl", "«Recenzo pri “Universalaj Lingvoj en Svislando”», date 2009"),
    "Zaloda_auxiliara linguo da nekonocato": (2018, None, "zaloda_auxiliara_linguo_da_nekonocato", "«Zaloda: auxiliara linguo da nekonocato», date 2018"),
    "dementulo": (2017, None, "LaDementulo", "«La Dementulo da Khalil Gibran», date 2017-04-24"),
    "PostaMundi_43": (2024, None, "posta-mundi-43", "«Posta Mundi 43», date 2024-03-01 (also its upload date; it fits the run: n-ro 37 = Mar 2022, n-ro 48 = Jan 2026)"),
    "Posta Mundi #45": (None, "SECONDARY", "posta-mundi-45", "«Posta Mundi 45», no date; between n-ro 37 (Mar 2022) and n-ro 48 (Jan 2026), so SECONDARY"),
    "Naskigho kaj mallonga historio de Ido": (None, "SECONDARY", "naskigho_kaj_mallonga_historio_de_ido", "date 2021-12 = the upload date, not taken; a modern history of Ido (Neves), so SECONDARY"),
}
# Years found on the web and in the bibliographies we hold (the editor decided on 2026-10-09, 17:1x, that the web be used
# for these too, with source URLs given), for the books no reader could date. item → (year or None, kind or None, basis).
# Saved (an internal record, 2026-10-09, not published): Wikipedia, the ido-vivo.info list, the BitArkivo IpI listing.
WEB = {
    'agi': (1925, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Agi dil Apostoli, trad. L. Kauling, Thaon-les-Vosges 1925 (BKI 6); source https://www.ido-vivo.info/agi.pdf'),
    'franciskus': (1927, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Ségur, Vivo di Santa Franciskus de Sales, trad. L. Poitresse, Thaon-les-Vosges 1927 (BKI 16); source https://www.ido-vivo.info/franciskus.pdf'),
    'ioanna': (1926, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Poitresse, Vivo di Santa Ioanna Franciska de Chantal, Thaon-les-Vosges 1926 (BKI 13); source https://www.ido-vivo.info/ioanna.pdf'),
    'milvorti': (1939, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Jacob, Mil vorti Ido, 1st ed. 1939 (24 p.), 2nd ed. London 1966 (16 p.); ours has 13 PDF pages, probably the 1966 edition of the 1939 text; source https://www.ido-vivo.info/milvorti.pdf'),
    'katekizala': (1928, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Houillon, Katekizala exempli, 2ma kayero, Thaon-les-Vosges 1928, 22 p. (the 1ma kayero 1926, 19 p.); ours has 22 PDF pages; source https://www.ido-vivo.info/katekizala.pdf'),
    'quaradekfabli': (1928, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Houillon, Quaradek fabli, Thaon-les-Vosges 1928; source https://www.ido-vivo.info/quaradekfabli.pdf'),
    'sundiala': (1926, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Sundiala evangelii, s.d., tr. L. de Beaufront, announced in BFI n-ro 98–99, Nov–Dec 1926; so 1926 or earlier; source https://www.ido-vivo.info/sundiala.pdf'),
    'Idomarcho': (1930, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Versalles, Ido-marcho, 9 music sheets, /1930/ (after MK 1930); source https://www.ido-vivo.info/Idomarcho.pdf'),
    'grekaidokurso': (1973, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Nova docado-metodo di la auxiliara linguo «Ido», Athína 1973; source https://www.ido-vivo.info/grekaidokurso.pdf'),
    'idohistorio': (1987, None, "ido-vivo.info's list: Henry Jacob, Kontributaji a la studio di la historio di nia linguo (reproduced by Editerio Progreso 1987); Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): /Marcinelle/ 1987; source https://www.ido-vivo.info/idohistorio.pdf"),
    'novahorizonti': (1913, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Barral, Nova horizonti, Leipzig 1913; source https://www.ido-vivo.info/novahorizonti.pdf'),
    'Nova Horizonti_text': (1913, None, "Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Barral, Nova horizonti, Leipzig 1913 (archive.org's record says 1919-01-01, not taken; https://archive.org/details/NovaHorizonti)"),
    'hung': (1932, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Csatkai & Horovitz, Az Ido világnyelv kézi szótára, Magyar-Ido rész, Szombathely 1932 (our copy names the Szombathely printer, Martineum); not at ido-vivo.info (404)'),
    'Jivago': (2016, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Pasternak, Doktor Jivago, tr. J. Viol, /2016/; source https://www.ido-vivo.info/Jivago.pdf'),
    'KANSONIKRISTNASKALA': (2017, None, "ido-vivo.info's list: Kansoni Kristnaskala, tr. Tiberio Madonna (2017); source https://www.ido-vivo.info/KANSONIKRISTNASKALA.pdf"),
    'LA_SAPONBULO': (2017, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Madonna, La saponbulo, 1st ed. 2017; source https://www.ido-vivo.info/LA_SAPONBULO.pdf'),
    'Anatole-Francetri-rakonti': (2011, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Tri rakonti da Anatole France, tr. D. Weston, /2011/; source https://www.ido-vivo.info/Anatole-Francetri-rakonti.pdf'),
    'dudunsanydramati': (2014, None, 'Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …): Dunsany, Du dramati, tr. B. E. Drake, 2014; source https://www.ido-vivo.info/dudunsanydramati.pdf'),
    'Markusevangelio': (None, 'SECONDARY', "ido-vivo.info's list: tr. J. Viol from Schlachter's version of 2000, so written after 2000; source https://www.ido-vivo.info/Markusevangelio.pdf"),
    'Francarevoluciono': (None, 'SECONDARY', "ido-vivo.info's list: tr. Robert Pontnau (his books 2006–2007 in Carlevaro et alii, Bibliografio di Ido, 3ma ed. 2020 (geniza/sources/carlevaro/text/B8 …)); source https://www.ido-vivo.info/ (Francarevoluciono.pdf redirects)"),
    '31': (1999, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/)"),
    '33': (2000, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/)"),
    '40-41': (2002, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/); the index of 1992–2001"),
    '53': (2005, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/)"),
    '54': (2005, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/)"),
    '55': (2005, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/); its text: «ĉi-jare en Bulonjo»"),
    '57': (2006, None, "IpI by the run, four issues a year: our n-ro 39 = 4/2001, 42 = 3/2002, 75 = 4/2010, 76 = 1/2011, and BitArkivo's 1998 n024/n026, 1999 n029 (https://tempa.bitarkivo.org/gazetoj/InformiloPorInterlingvistikojIPI/)"),
    'Esperanto_Lenin_Stalin': (2016, None, "the file's own PDF creation date, 30 Mar 2016 (an author-made file)"),
    'Ferdinand_Hodler_bio': (2021, None, "the file's own PDF creation date, 20 Mar 2021 (an author-made file)"),
    'Kronologia_biografio_de_Hector_Hodler': (2020, None, "the file's own PDF creation date, 8 Mar 2020 (an author-made file)"),
    'Zamenhof_identeco': (2016, None, "the file's own PDF creation date, 3 Jan 2016 (an author-made file)"),
    'Zamenhof_prisilentado_judeco': (2020, None, "the file's own PDF creation date, 1 Aug 2020 (an author-made file)"),
    'Zamenhof_Volapuek_Schleyer100': (2012, None, "Künzli's bibliography (BIBLIOGRAFIO_SCHRIFTEN_KUENZLI): La Ondo de Esperanto, julio–aŭgusto, for Schleyer's centenary (d. 1912); the PDF made Jan 2013"),
    'Jugoslawien_Sprachpolitik': (2012, None, "the file's own PDF creation date, 29 Jun 2012 (an author-made file)"),
    'Rezension_Nissl_SprachenfrageEU': (2011, None, "the file's own PDF creation date, 6 Nov 2011 (an author-made file)"),
    'svisa_gazetaro': (2006, None, "the file's own PDF creation date, 7 Jun 2006 (an author-made file)"),
    'Recenzo_WalterZelazny': (2009, None, "the file's own PDF creation date, 3 May 2009 (an author-made file)"),
    'BIBLIOGRAFIO_SCHRIFTEN_KUENZLI': (2014, None, "the file's own PDF creation date, 22 Aug 2014 (an author-made file); it covers 1981–2014"),
    'Sonntagszeitung_082009': (2009, None, 'the file name (08/2009) and its PDF creation date, 23 Aug 2009'),
    'lg144.gobbo': (2009, None, 'La Gazeto n-ro 144, «31okt09» on its pages (the reader)'),
    'Barandovska_Latinidaj_planlingvoj': (2009, None, "the file's own PDF creation date, 4 May 2009 (an author-made file) (the AIS course itself may be earlier)"),
    'dokumen.pub_esperanto-and-languages-of-internationalism-in-revolutionary-russia-2020055613-2020055614-9781350160651-9781350160668-9781350160675-1350160652': (2021, None, "O'Keeffe, Bloomsbury 2021 (https://newbooksnetwork.com/esperanto-and-languages-of-internationalism-in-revolutionary-russia)"),
    'dokumen.pub_esperanto-language-literature-and-community-0791412539-9780791412534': (1992, None, 'Janton, ed./tr. Tonkin, SUNY Press, Dec 1992 (https://sunypress.edu/Books/E/Esperanto)'),
    'Esperanto sen mitoj - Ziko Marcus Sikosek': (None, 'SECONDARY', "the 2nd revised edition; the first edition 1999 (https://www.goodreads.com/author/show/1018889.Ziko_Marcus_Sikosek); the 2nd edition's year not found"),
    'Pioneers_of_internationalism_Esperanto_a': (2021, None, 'Alcalde, in Walker & Declercq (eds.), Multilingual Environments in the Great War, Bloomsbury 2021, pp. 44–57 (https://bitoteko.esperanto.es/xmlui/handle/11013/6776)'),
    'Kuznecov': (2005, None, "S. Kuznecov, in Sériot (ed.), Un paradigme perdu: la linguistique marriste, Cahiers de l'ILSL 20, 2005, pp. 143–159 (https://lwc1.benjamins.com/catalog/sihols.123.16mor, references)"),
    'pankhurst-delphos-future-of-international-language': (1927, None, 'Pankhurst, Delphos, London: Kegan Paul 1927, To-day and To-morrow series (https://pressto.amu.edu.pl/index.php/jki/article/view/18628)'),
    'Jürgensen-EG1': (1906, None, 'Jürgensen, Wörterbuch Esperanto-Deutsch, Berlin: Möller & Borel 1906 (https://archive.org/details/woerterbuch-juergensen; https://ci.nii.ac.jp/ncid/BA00868988)'),
    '338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat': (1923, None, "vol. 1's preface «Ĝenevo, januaro 1923» on its pages; vol. 2 «Genève, somero 1927»"),
    'Omagxe-5': (None, 'SECONDARY', 'it cites Esperanto 1962/65; the PDF made 31 Mar 2016'),
    'st-andrews-Aitken_OConnor_Chapter_AAM': (2020, None, "the file's own PDF creation date, 9 Mar 2020 (an author-made file) (an author's accepted manuscript)"),
    'csuohio-neural-correlates-dejavu-dissociation': (None, 'SECONDARY', 'a modern neuroscience paper on déjà vu; no date found'),
    'sokolova': (None, 'SECONDARY', 'publisher «Культурная революция», Moscow, a modern house; no date found'),
    'occidental-lang-Historie': (2020, None, "the file's own PDF creation date, 30 Jul 2020 (an author-made file)"),
    'li_defectes_inacceptabil_de_interlingua_gode.jpg': (None, 'SECONDARY', '«Interlingue-Servicie Winterthur Octobra 195[?]» on the sheet (the reader): the 1950s'),
    'IE-Munde11': (None, 'SECONDARY', 'an Occidental item, so written after 1922; no date found'),
    'oficiala_aldono_1a': (1909, None, "1OA 1909 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj); Kück's reproduction (PDF author Andreas Kueck, 2006)"),
    'oficiala_aldono_2a': (1919, None, '2OA 1919 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj)'),
    'oficiala_aldono_3a': (1921, None, '3OA 1921 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj)'),
    'oficiala_aldono_4a': (1929, None, '4OA 1929 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj)'),
    'oficiala_aldono_5a_6a': (1934, None, '5OA 1934, 6OA 1935 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj); the file holds both'),
    'oficiala_aldono_7a': (1958, None, '7OA 1958 (https://eo.wikipedia.org/wiki/Oficialaj_aldonoj)'),
}
import unicodedata as _ud
WEB = {_ud.normalize("NFC", k): v for k, v in WEB.items()}   # file names may be decomposed (macOS): look up in NFC
# Years read in a born-digital text where its first line misleads (2026-10-10 18:2x, from a reading of the Biblioteko Hippolyte
# Sebert reissues: a heading «Pri Camille Aymonier — 1866-1951» gives life dates, not the year of writing). item → (year, basis).
# Single articles cut from the Tekstaro's modern press (La Ondo, UEA's Esperanto 2002–2017, IKU, Monato), the
# press-selection list of 2026-10-10 (an internal record, not published): all written 1997–2018, so
# SECONDARY whatever the issue's year. NOT dated from the Tekstaro header, which gives the whole periodical's span.
PRESS = re.compile(r"^tekstaro-.+-s\d{4}$")
PRESS_EV = "an article of the Tekstaro's modern press, 1997–2018 (the press-selection list): SECONDARY; the header's span not taken"
# The Sidorov collection's typed texts (reu-<stem>, 2026-10-10 19:4x): REU's own catalogue entry gives the imprint, «…, 1913,
# 38 p.»; it is taken before the text's first line, which often names the period covered («Historio … (1887–1912)»).
# Read from the REU triage's ENTRIES.tsv (file stems → the entry); the year beside the page count, else the latest year
# that is not a print run («2000 экз.»).
def reu_years():
    p = os.path.join(G, "sources", "ocr-work", "reu-triage-2026-10-10", "ENTRIES.tsv")
    out = {}
    if not os.path.exists(p):
        return out
    Y = r"(?<!\d)(18[5-9]\d|19\d\d|20[0-2]\d)(?!\d)"
    for e in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
        d = e["description"]
        imp = [int(y) for y in re.findall(Y + r"\s*(?:г\.|g\.)?\s*[,.]?\s*\d+\s*(?:p\b|p\.|с\.|с\b|стр|paĝ|pp)", d)]
        run = {int(y) for y in re.findall(Y + r"\s*(?:ekz|экз)", d)}
        alls = [int(y) for y in re.findall(Y, d) if int(y) not in run]
        y = max(imp) if imp else (max(alls) if alls else None)
        for st in re.split(r"[|;, ]+", e["stems"]):
            if st and y:
                out["reu-" + st] = (y, f"REU's catalogue entry {e['n']}: «{d[:90]}»")
    return out
# Taken before the first line; kind by the rule. Where a text holds pieces of several years, its first piece's year, as for a
# volume spanning two years.
TEXT_READ = {
    "bhs-pri-aymonier": (1952, "¶ 4 «El Franca Esperantisto N° 123 — Januaro-Februaro 1952»: an obituary; ¶ 1's 1866-1951 are life dates"),
    "bhs-pri-deligny": (1933, "the pieces: Enciklopedio de Esperanto 1933 (¶ 35), Nordfranca Esperantisto March 1937 (¶ 16), the "
                              "typed translation of about 1976 with its biography (¶ 3); ¶ 1's 1864-1950 are life dates"),
    "bhs-bulonjo-1905-dokumentoj": (2015, "the library's own essay: ¶ 27 «Hodiaŭ (Julio 2015) en Lille … okazas la 100-a Kongreso», "
                                          "signed «E.B.H.S.» (¶ 28), then its comment on the 12 postcards; no 1905 text in it"),
    "bhs-eco-membrokarto": (2010, "the library's description of an unused 1910 membership card of the Grupo Esperantista Pariza "
                                  "(¶ 4–16, «Post cent jaroj, ĉi-tiu aliĝila karto restas la sola en nia arĥivo»): written about 2010"),
    "bhs-zamenhof-vizito-centra-oficejo": (1913, "Zamenhof's entry in the ECO's Ora libro, 15 August 1913 (¶ 7–9), with "
                                                 "Ferter-Cense's article of May–June 1917 (¶ 5)"),
    "bhs-eco-raporto-unua-kongreso": (1905, "Kajero 1-a de Esperantista Dokumentaro, the ECO's report of the first congress, 1905 "
                                            "(the list's notes: «the ECO report 1905»)"),
    "bhs-internacia-muzeo": (1910, "¶ 3 «— 1910 —», the brochure of the Brussels exhibition of 1910"),
    "bhs-deligny-mia-esperantista-vivo": (1943, "¶ 2 «Mia Esperantista Vivo (1900-1943)»: written 1943 or later"),
}
# Kongresa libro (ÖNB 701635-B): the file number is the Universal Congress's number (.03 prints «TRIA UNIVERSALA
# KONGRESO», .07 «Sepa Universala Kongreso», checked 2026-10-09 17:1x); the cover sheet's «Jahr: 1905» is the series'
# first year, not the book's. Congress years: 1–10 = 1905–1914, 11 = 1915, 12 = 1920, 13 = 1921, 14 = 1922.
KONGRESA = re.compile(r"kongresa\.libro\.(\d\d)")
UK_YEAR = {**{n: 1904 + n for n in range(1, 12)}, 12: 1920, 13: 1921, 14: 1922}
IMPRINT = re.compile(r"©|\(c\)\s*\d|copyright|isbn|eldonis|eldonejo|presejo|presis|verlag|druck(?:erei)?\b|imprimerie|imprimé|"
                     r"printed (?:by|in)|published by|tipografia|tipografio|nyomda|drukarnia", re.I)   # imprint words only (a city
                     # name alone caught running text: Neves's Parnaso «1906» from a bibliography, the run of 14:0x)
YEAR = re.compile(r"(?<![\d.,/])(18[5-9]\d|19\d\d|20[0-2]\d)(?![\d.,/])")
DOCS = re.compile(r"dokument|leter|korespond|protokol|raport|cirkuler|memora|oficiala|letters|briefe|correspondance", re.I)
PART = re.compile(r"^\d\d[A-Z]?(?:-\d\d)?_(?:ENCYCL|ANTOL|COUVERTURE)|^00_COUVERTURE")


# Rows a reader returned under a neighbour's number: (readers' folder, batch, row as returned) → the file it describes.
# Found 2026-10-09 by testing each row's year against its own excerpt file; each pair's quotes and year are in the other
# file and not in its own. The returns stay as filed; the fix is applied here.
ROW_FIXES = {("item-dates-2026-10-09", "b10", "369"): "370", ("item-dates-2026-10-09", "b10", "370"): "369",
             ("item-dates-2026-10-09-periodicals", "p02", "078"): "079", ("item-dates-2026-10-09-periodicals", "p02", "079"): "078",
             ("item-dates-2026-10-09-periodicals", "p04", "133"): "134", ("item-dates-2026-10-09-periodicals", "p04", "134"): "133",
             ("item-dates-2026-10-09-periodicals", "p04", "144"): "145", ("item-dates-2026-10-09-periodicals", "p04", "145"): "144"}


def reads(folder):
    """item → (published, written, work, title, evidence) from the readers' returns (KEY.tsv + b*.return.md, filed
    verbatim): Read-only readers of each item's first 4 and last PDF page (2026-10-09; the automatic imprint test was
    unsafe)."""
    if not folder or not os.path.isdir(folder): return {}
    key = {l.split("\t")[0]: l.rstrip("\n").split("\t")[2] for l in open(os.path.join(folder, "KEY.tsv"), encoding="utf-8")}
    out = {}
    fo = os.path.basename(os.path.normpath(folder))
    for f in sorted(glob.glob(os.path.join(folder, "*.return.md"))):
        batch = os.path.basename(f).split(".")[0]
        for l in open(f, encoding="utf-8"):
            m = re.match(r"\|\s*(\d{3})\s*\|(.*)", l)
            n = m and ROW_FIXES.get((fo, batch, m.group(1)), m.group(1))
            if m and n in key:
                c = [x.strip() for x in m.group(2).split("|")]
                out[key[n]] = (c + [""] * 5)[:5]
    return out


def first_year(s):
    m = re.search(r"(?<!\d)(1[5-9]\d\d|20[0-2]\d)(?!\d)", s or "")
    return int(m.group(1)) if m else None


# The Idists' cutoff (the editor ruled on 2026-10-09 that for Idists, as opposed to Esperantists, the cutoff is 1931, the
# relaunch of Progreso; at 17:0x, that a separate date cutoff be applied for Ido specifically, granting that there are
# problems (such items are primary for Idists, secondary for Esperantists before the schism) that cannot be adjudicated): an item whose primary language is Ido (the
# newest OCR-TEXT-LANGUAGES table) is PRIMARY if written before 1931; every other item in 1914 or before (cut 1915).
# THE OCCIDENTAL CUTOFF (the editor ruled on 2026-10-10, 17:3x, that the Idist rule, up to 1931, apply to Occidental as
# well): Occidental items too are PRIMARY if written before 1931.
# Born-digital Occidental texts are not in the language table, so they are named: Cosmoglotta and Kosmoglott.
OCC_BD = re.compile(r"^(cosmoglotta|kosmoglott)-")
# NOVIAL too (the editor confirmed on 2026-10-10, 17:5x, that the 1931 rule applies to Novial too): Novial items are PRIMARY
# if written before 1931. The language table records Novial for Mondo 1930–31, Mondo 1932 and Novialiste (its RULED,
# «occidental» → «novial», approved by the editor: the gate has no Novial model and reported Occidental).
NOVIAL = set()


def ido_items():
    """items under the 1931 cutoff: primary language Ido, Occidental, Novial or Latino sine flexione (the newest language table), and the named
    born-digital Occidental texts"""
    tabs = sorted(glob.glob(os.path.join(G, "OCR-TEXT-LANGUAGES-20*.tsv")))
    out = set()
    for l in (open(tabs[-1], encoding="utf-8") if tabs else []):
        x = l.rstrip("\n").split("\t")
        if not l.startswith("#") and len(x) > 1 and x[1].split(",")[0] in ("ido", "occidental", "novial", "latino-sine-flexione"): out.add(x[0])   # Peano's Interlingua: the 1931 cutoff as for Ido, Occidental and Novial (approved by the editor, 2026-10-11 03:1x)
    return (out - NOVIAL) | set(TOPIC)


# THE TOPIC RULING (the editor ruled on 2026-10-10, 18:2x, that a text ABOUT Ido, Occidental or Novial, in any language,
# takes the 1931 cutoff; at 18:3x the editor approved making the four below primary). Found by a title search of the items written
# 1915–1930; also three Ido texts whose language rows are empty (the gate gave no reading), so the language rule missed
# them. A magazine issue with an Ido polemic inside cannot be found by title.
TOPIC = {
    "Problem Of An International Auxiliary Language, The - Luther H. Dyer": "Dyer 1923, in English, about Ido",
    "extrakt": "Beaufront, Linguala studiuri (1927), in Ido",
    "lalibropriesther": "Kofman, La libro pri Esther (1925), in Ido",
    "Quar-Rakonti-da-Maupassant": "Maupassant, tr. Houillon (1926), in Ido",
    # THE 1931 RULE WIDENED (approved by the editor, 2026-10-11 11:18; the dowse runbook, an internal record, not
    # published): items written in Ido, Occidental, Novial or Latino sine flexione, or by
    # those movements about their language, before 1931, are PRIMARY; such items are named here by hand.
    "dyer-problem-ido-1923": "Dyer 1923, in English, about Ido (the born-digital copy of the scan above)",
    "jespersen-1928-an-international-language": "Jespersen, An International Language (1928), in English, about Novial",
}


ENCYCL = re.compile(r"ENCYCL|ENCYL_|^00_COUVERTURE")   # Künzli, Svisa Enciklopedio Planlingva, filed in pieces


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    ap.add_argument("--reads", action="append", default=[], help="a readers' folder (KEY.tsv, *.return.md); repeatable")
    a = ap.parse_args()
    R = {}
    for fo in a.reads: R.update(reads(fo))
    if os.path.exists(a.out): sys.exit(f"--out {a.out} exists: choose a new name")
    PS = _mod("ps", "ocr-page-sequence.py"); K = _mod("ks", "kapis-share-tables.py")
    rows = K.rows(os.path.join(G, "OCR-ITEM-TABLE.tsv"))
    # born-digital items (2026-10-10): rows of their own even before the item table has them; dated from the text's header
    sys.path.insert(0, HERE); import born_digital_lines as BDL
    BD = BDL.lists("proposed"); have = {r["item"] for r in rows}
    rows += [{"item": it, "title_key": it, "year": ""} for it in sorted(BD) if it not in have]
    runs = collections.Counter(r.get("title_key", "") for r in rows)
    out, stats = [], collections.Counter()
    IDO = ido_items(); REU = reu_years(); cut = lambda it: 1931 if (it in IDO or OCC_BD.match(it)) else 1915
    for r in rows:
        it = r["item"]
        # a periodical issue dated by its own year; one with none is read too; and one RULED (2026-10-17: a «1922» file of
        # Kosmoglott that is a c. 1972 plan of the run was skipped as dated by its year, so its ruling never applied)
        if K.periodical(r, runs) and r.get("year") and it not in RULED: continue
        y, how, ev = None, "none", ""
        if it in RULED and RULED[it][0]:
            y, how, ev = RULED[it][0], "ruled", RULED[it][2]
        elif r.get("year"):
            y, how, ev = int(r["year"]), "table", "the item table's year"
        else:
            m = YEAR.findall(it)
            if m: y, how, ev = int(m[-1]), "name", f"«{m[-1]}» in the file name"
        wr = None
        if PRESS.match(it) and it in BD:
            how, ev = "list", PRESS_EV
        elif it in BD and not (it in RULED and RULED[it][0]):
            hw, hp, hev = BDL.header_years(BDL.text_path(BD[it]))
            if hw or hp:
                y, how = (hw or hp), ("text header" if hw else "text header (edition)")
                ev = "the text's own header: " + "; ".join(f"«{x}»" for x in hev)
                if hw and hp and hp > hw: ev += f" (written {hw}, this edition {hp})"
            else:   # no Tekstaro header: the year in the text's first line (Cosmoglotta: «Cosmoglotta A 38 (jan-feb 1927)»)
                first = BDL.blocks(open(BDL.text_path(BD[it]), encoding="utf-8").read())[:1]
                # not a line that credits OUR transcription: its year is the transcriber's, not the text's (found 2026-10-16:
                # devjatnin-malhimno-postcard was dated 2026 by its text heading, but 2026 is our transcription; the card is c. 1921)
                if first and re.search(r"(?i)transcri(bed|ption)", first[0][2]): first = []
                m = BDL.YEAR.search(first[0][2]) if first else None
                if m:
                    y, how, ev = int(m.group(1)), "text heading", f"the text's first line: «{first[0][2][:90]}»"
            if it in REU:   # written no later than published: the earlier of REU's imprint and the file name's year
                ny = [int(v) for v in YEAR.findall(it)]
                y = min([REU[it][0]] + ny); how = "REU catalogue"   # a span in the name («1887_1888»): its first year
                ev = REU[it][1] + (f"; the file name's {min(ny)} is earlier" if ny and min(ny) < REU[it][0] else "")
            if it in TEXT_READ:
                y, how, ev = TEXT_READ[it][0], "text read", TEXT_READ[it][1]
        if y is None and ENCYCL.search(it):
            y, how, ev = 2006, "ruled", ("Künzli, Svisa Enciklopedio Planlingva, 2006 by its title pages («La Chaux-de-Fonds 2006»; "
                                         "«Imprimerie Messeiller, Neuchâtel (Suisse) 2006»); the editor ruled on 2026-10-09 that the date "
                                         "is recoverable")
        mk = KONGRESA.fullmatch(it)
        if mk and int(mk.group(1)) in UK_YEAR:   # before the reader: its catalogue year is the series' first year
            y, how, ev = UK_YEAR[int(mk.group(1))], "congress-number", (f"Kongresa libro of the {int(mk.group(1))}th Universal "
                         f"Congress (the file number; .03 and .07 print the congress's ordinal); not the ÖNB «Jahr: 1905»")
        itn = _ud.normalize("NFC", it)
        if y is None and itn in WEB:
            wy, _, wev = WEB[itn]; ev = wev
            if wy: y, how = wy, "web"
            else: how = "web-kind"
        if y is None and it in ARCHIVE_ORG and how != "web-kind":
            ay, _, ident, aev = ARCHIVE_ORG[it]
            ev = f"archive.org record https://archive.org/details/{ident}: {aev}"
            if ay: y, how = ay, "archive.org"
            else: how = "archive.org-kind"
        if it in R and how not in ("archive.org", "archive.org-kind", "congress-number", "web", "web-kind"):
            pub, w_, work, title, evr = R[it]
            wr = first_year(w_) if w_ and w_.upper() != "SAME" else None
            unknown = pub.upper().startswith("UNKNOWN")
            sig = re.search(r"Signatur:[^»]*?\d{6}-[A-Z]\.(?:[A-Z]+\.)?(\d{4})", evr)   # an ÖNB shelfmark ends in the volume's year
            if y is None and unknown and sig:
                y, how, ev = int(sig.group(1)), "read-catalogue", (f"{work}; {title}; {evr} (the shelfmark's year; the reader "
                                                                    f"left it «{pub}»; a library catalogue record, not the item)")
            elif y is None and first_year(pub) and not unknown:
                weak = " (a library catalogue record, not the item)" if re.search(r"ONB|catalogue|cover sheet|Jahr:|Signatur", pub + evr, re.I) else ""
                inf = re.search(r"inferred|worked out|from its own text|contents point", pub, re.I)
                y, how, ev = first_year(pub), "read" + ("-catalogue" if weak else "-inferred" if inf else ""), f"{work}; {title}; {pub}; {evr}{weak}"
            elif y is None:
                how, ev = "read-none", f"{work}; {title}; the reader: «{pub}», {evr}"
            if wr and y and wr > y: wr = None   # a «written» later than published is a later revision, not earlier writing
        if y is None and it not in R:
            pg = PS.item_pages(it)
            if pg:
                ks = sorted(pg); look = ks[:4] + ks[-1:]   # the title pages and the last page (colophon)
                imp, tit = [], []
                for p in look:
                    for l in pg[p].splitlines():
                        ys = [int(v) for v in YEAR.findall(l)]
                        if not ys: continue
                        if IMPRINT.search(l): imp.append((max(ys), p, l.strip()[:90]))
                        elif p in ks[:4] and len(l.strip()) <= 40: tit.append((max(ys), p, l.strip()[:90]))
                if imp:
                    y, p, l = max(imp); how, ev = "imprint", f"PDF p. {p}: «{l}»"
                elif tit:
                    y, p, l = max(tit); how, ev = "page", f"PDF p. {p}: «{l}»"
        yw = wr or y   # the editor's ruling: pieces written, not published, before the cutoff are primary
        kind = "SECONDARY" if (PRESS.match(it) and it in BD) else RULED[it][1] if it in RULED and RULED[it][1] else WEB[_ud.normalize("NFC", it)][1] if (_ud.normalize("NFC", it) in WEB and WEB[_ud.normalize("NFC", it)][1] and not yw) else ARCHIVE_ORG[it][1] if (it in ARCHIVE_ORG and ARCHIVE_ORG[it][1] and not yw) else (("PRIMARY" if yw < cut(it) else "SECONDARY") if yw else "")
        late = (it in IDO or OCC_BD.match(it)) and yw and 1915 <= yw < 1931 and not (it in RULED and RULED[it][1])
        if late: stats["ido-cutoff"] += 1
        flag = ("Ido/Occidental/Novial cutoff 1931" if late else "")
        flag = "; ".join(x for x in (flag, ("written earlier: %d" % wr) if wr else ("documents?" if (y and y >= 1915 and DOCS.search(it) and it not in RULED and it not in R) else "")) if x)
        if it in RULED and not RULED[it][0]: how, ev = "ruled", RULED[it][2] + (f"; {ev}" if ev else "")
        out.append([it, str(yw or ""), how, kind, flag, ev.replace("\t", " ").replace("\n", " ")]); stats[how] += 1
    # parts of one work: the year their parts agree on (most common), for parts with none
    parts = [o for o in out if PART.match(o[0])]
    agreed = collections.Counter(o[1] for o in parts if o[1])
    if agreed:
        yy = agreed.most_common(1)[0][0]
        for o in parts:
            if not o[1]:
                o[1], o[2], o[3] = yy, "part", ("PRIMARY" if int(yy) < cut(o[0]) else "SECONDARY")
                o[5] = f"a part of a work filed in pieces; its parts give {yy}"; stats["part"] += 1; stats["none"] -= 1
    # an undated periodical issue: its kind from its run's dated issues, when the whole run falls on one side of 1914
    # (a run = title keys equal in their letters, so «posta-mundi-39» joins «posta_mundi»; a key of digits only, from
    # numbered file names, is no run). The reader's own clue years come first.
    byit = {r["item"]: r for r in rows}
    rk = lambda r: re.sub(r"[^a-z]", "", (r.get("title_key") or "").lower())
    runyears = collections.defaultdict(list)
    for r in rows:
        if K.periodical(r, runs) and rk(r) and first_year(r.get("year")): runyears[rk(r)].append(first_year(r["year"]))
    for o in out:
        if o[1] and rk(byit[o[0]]): runyears[rk(byit[o[0]])].append(int(o[1]))
    for o in out:
        r = byit[o[0]]
        if o[1] or o[3] or not K.periodical(r, runs): continue
        clue = [int(v) for v in re.findall(r"(?<!\d)(1[5-9]\d\d|20[0-2]\d)(?!\d)", R.get(o[0], [""] * 5)[0] + " " + R.get(o[0], [""] * 5)[4])]
        c = cut(o[0])
        if clue and (min(clue) >= c or max(clue) < c):
            o[3] = "SECONDARY" if min(clue) >= c else "PRIMARY"
            o[4] = f"undated; kind from the reader's clue years, {min(clue)}–{max(clue)}"; stats["clue-kind"] += 1; continue
        ys = runyears.get(rk(r), [])
        if ys and (min(ys) >= c or max(ys) < c):
            o[3] = "SECONDARY" if min(ys) >= c else "PRIMARY"
            o[4] = f"undated; kind from its run's dated issues, {min(ys)}–{max(ys)}"; stats["run-kind"] += 1
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("# GENERATED by tools/ocr-item-dates.py. Do not hand-edit — re-run it (rulings go in its RULED table). "
                "written = a year of publication unless «ruled»; kind by the editor's rule: 1914 or before PRIMARY (Ido/Occidental/Novial items: before 1931), later "
                "SECONDARY, exceptions only as ruled; «documents?» = a later edition of what may be earlier writing.\n")
        f.write("item\twritten\tevidence\tkind\tflag\twhat it rests on\n")
        for o in sorted(out): f.write("\t".join(o) + "\n")
    print(f"{len(out)} items (books, and periodical issues with no year of their own) → {a.out}; " + ", ".join(f"{k} {v}" for k, v in stats.most_common()))


if __name__ == "__main__":
    main()
