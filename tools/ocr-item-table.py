#!/usr/bin/env python3
r"""ocr-item-table — which title, volume, year, issue and date each corpus file is (the item table).

    tools/ocr-item-table.py --pdfs <full PDF list> --out <geniza>/OCR-ITEM-TABLE-<date>.tsv

WHY (a proposal on citable hits, «The item table»: an internal record, 2026-10-08, not published; approved by the
editor 2026-10-08 10:5x). A dowse hit names only the file and the PDF page; a citation needs title, volume, year, issue
and printed page. This is the first half (the file → issue); the page map is the second. The table is also to be
shared with Kapis of BitArkivo as a finding tool, keyed by the BPEAPE number (the editor ruled that the finding tool
needs the BPEAPE id).

WHAT IT TAKES FROM A FILE'S NAME, and only what the name makes certain:
  A  the structured names (BitArkivo / archive.org style): Title_YYYY[_YYYY][_vNN|_jNN][_nNNN[-NNN…]][_mon[-mon][DD]]
     → year, volume (v = volume, j = jaro), issue, month(s), day.            e.g. AmerikaEsperantisto_1910_v08_n03_okt
  D  a date in the name: Title_YYYYMMDD                                       e.g. MezhdunarodnyjJazyk_19260315
  B  the dotted names: Title.YYYY[.label]: the year; the label is kept AS FILED, because in some titles it is the
     month (LEsperantiste.1907.5 = May 1907) and in others the issue number (KatalunaEsperantisto.1916.69-70), and
     the name alone does not say which. A title's meaning is entered in DOTTED only once checked; until then the
     row says «label as filed».
  N  ANNO's names: ANNO_<code>_<year><4 digits>: the year, the digits as filed, the title code.
  Y  a four-digit year anywhere (books and one-offs); the rest of the name after it kept as filed.
  Second copies («.N»): the COPIES list, or flagged for checking.
  -  nothing.
Titles are grouped by `ocr-page-sequence.py`'s own `title_of()`, so the table and the page map agree on what a
title is. Display titles, BPEAPE numbers and origins come from checked lists and fetch records; pagination and the first page
of text from the page map (ocr/runs/OCR-PAGE-MAP.tsv); a column is left empty, never guessed, where none says.

WRITE-SET: --out only: the fixed name geniza/OCR-ITEM-TABLE.tsv, replaced only when the current version is committed
(tools/ocr_replace_guard.py; approved by the editor, 2026-10-08), after a difference report, losses first.
--assign-keys writes ONLY geniza/OCR-ITEM-KEYS.tsv, by appending rows (never rewriting one); --keys-preview writes nothing.

KEYS AND CITATIONS (2026-10-16, an assistant's request, approved by the editor): the columns «key» and «citation», at the end.
    tools/ocr-item-table.py --pdfs <list> --out x --keys-preview 30    # what the unkeyed items would get
    tools/ocr-item-table.py --pdfs <list> --out x --assign-keys        # pin them
    tools/ocr-item-table.py --pdfs <list> --out <geniza>/OCR-ITEM-TABLE.tsv   # refuses while an item has no key
"""
import os, re, sys, glob, argparse, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("pageseq", os.path.join(HERE, "ocr-page-sequence.py"))
_ps = importlib.util.module_from_spec(_s); _argv = sys.argv; sys.argv = [_argv[0]]; _s.loader.exec_module(_ps); sys.argv = _argv

MON = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
       "okt": 10, "oct": 10, "nov": 11, "dec": 12}
A = re.compile(r"_(1[89]\d\d|20\d\d)(?:_(1[89]\d\d|20\d\d))?(?:_([vj])(\d+))?(?:_n(\d+(?:-\d+)*))?"
               r"(?:_([a-z]{3})(?:-([a-z]{3}))?(\d{1,2})?)?(?:_(.+))?$", re.I)
D = re.compile(r"_((?:1[89]|20)\d\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")
B = re.compile(r"[._ ](1[89]\d\d|20\d\d)(?:\.(.+))?$")
Y = re.compile(r"(?<!\d)(1[89]\d\d|20[0-2]\d)(?!\d)")

# Second copies of an issue, named with a «.N» ending (the editor's convention, 2026-10-07): the copy marker is not
# part of the issue's label. Named here, not guessed, because in a dotted name «.1» can also be a label
# («Lingvo Internacia 1909.0.1»). Each entry: (the item it is a copy of, where the copy is from).
COPIES = {
    "LEsperantiste.1907.5.1": ("LEsperantiste.1907.5", "Gallica, ark bpt6k6356494m (cupel4)"),
    "Esperanto-UEA_1912_n136_dec20.1": ("Esperanto-UEA_1912_n136_dec20", "ÖNB / ANNO e0f (cupel5)"),
}
# ANNO's own file names: ANNO_<title code>_<year><four digits> (the four digits kept as filed: not yet checked
# whether they are an issue number or ANNO's sequence).
ANNO = re.compile(r"^ANNO_([a-z0-9]{3})_(1[89]\d\d|20\d\d)(\d{4})$", re.I)

# BPEAPE (the editor ruled on 2026-10-08 that the finding tool needs the BPEAPE id, and confirmed that BitArkivo uses
# its numbers). By NAME PATTERN, not by title key (a key can mix files: «esperanto» holds La Esperantisto 1889–93 and Esperanto2017).
# Each matched on 2026-10-08 against the BPEAPE entries list: the entry's place and years against the files' years
# (search worksheets: an internal record, 2026-10-08, not published).
# (pattern, n-ro, display title, what was checked)
BPEAPE = [
    (r"^Esperanto-UEA_", 3376, "Esperanto (UEA)", "Céret, then Genève; the UEA organ; files 1905–1916"),
    (r"^Lingvo Internacia ", 9003, "Lingvo Internacia", "Upsala from Dec 1895, later Paris; files 1895–1914"),
    (r"^LEsperantiste\.", 3286, "L’Espérantiste", "SPPE monthly (de Beaufront); its Aldono is n-ro 3287; files 1898–1914"),
    (r"^larevuo\.", 11631, "La Revuo", "international literary monthly (Bourlet); files 1906–1913"),
    (r"^britaesperantisto_", 1184, "The British Esperantist", "BEA organ, London; supplements are n-roj 296, 9105, 12629; files 1905–1916"),
    (r"^AmerikaEsperantisto_", 381, "Amerika Esperantisto", "AENA, from Oct 1906 (Oct–Dec 1906 also as n-ro 382); files 1906–1916"),
    (r"^(juna\.esperantisto\.|JunaEsperantisto\.)", 7352, "Juna Esperantisto", "Genève 1903–05, Paris Oct 1905–Jul 1914; files 1904–1914"),
    (r"^ondodeesperanto\.", 10574, "La Ondo de Esperanto", "Saĥarov's Russian organ; files 1909–1917"),
    (r"^belgaesperantisto", 852, "Belga Esperantisto", "Antwerpen, first period Nov 1908–1914; files 1908–1914"),
    (r"^KatalunaEsperantisto\.", 7758, "Kataluna Esperantisto", "KEF organ, first epoch Sabadell; files 1910–1916"),
    (r"^KovnoEsperanto[._]", 8397, "Kovno-Esperanto", "Kovno, Nov 1911–Jun 1914; the 1911 nos. 1–4 may be its forerunner, n-ro 1637 (check)"),
    (r"^InternaciaSciencaRevuo_", 6775, "Internacia Scienca Revuo", "organ of the Internacia Scienca Oficejo, Paris; files 1904 (the year's volume, ÖNB, cupel18c), 1906–1911"),
    (r"^BohemaRevuoEsperantista_", 2389, "Ĉasopis Českých Esperantistů (Bohema Revuo Esperantista)", "B.U.E. monthly, Praha (Kühnl); files 1907–1914"),
    (r"^bohemaesperantisto[._]", 1036, "Bohema Esperantisto", "Praha; the entry names a second epoch Oct 1908–1914; files from 1903 (first epoch: check)"),
    (r"^EsperantoTriumfonta\.", 4199, "Esperanto Triumfonta", "weekly, first series; files 1921–1922"),
    (r"^MezhdunarodnyjJazyk_", 9401, "Meĵdunarodnij Jazik", "the S.E.U. Central Committee's organ; files 1925–1936"),
    (r"^TraLaMondo\.", 12966, "Tra la Mondo", "Capé's illustrated monthly, Meudon/Orléans; files 1905–1908"),
    (r"^lamarto\.", 9272, "La Marto", "first series Nov 1910–1914; files 1910–1914"),
    (r"^LaEsperoSvenska\.", 4295, "La Espero (Svenska Esperanto-Tidningen)", "Gävle, founded 1913; files 1913–1916"),
    (r"^Esperanto[. ]18\d\d", 3319, "La Esperantisto", "Nürnberg (Schalke from 1892), Sep 1889–Jun 1895; files Esperanto.1889–1893"),
    (r"^LaSunoHispana\.", 12569, "La Suno Hispana", "Valencia/Murcia groups' organ; files 1903–1910"),
    (r"^VochoDeKuracistoj\.", 13957, "Voĉo de l’ Kuracistoj", "TEKA organ, Lwów, Jan 1909–1912 (page 1 of 1909.1 agrees); files 1909–1911"),
    (r"^RuslandaEsperantisto", 11829, "Ruslanda Esperantisto", "«Espero», St Petersburg, first series from Apr 1905; files 1905–1910"),
    (r"^BultenoTEKS", 1832, "Bulteno de T.E.K.S.", "All-Russian Esperanto medical society, Moskva Jun 1911–1914 (a duplicate entry, n-ro 1822); files 1911–1914"),
    (r"^InternaciaSociaRevuo\.", 6786, "Internacia Socia Revuo", "«Paco-Libereco», Genève/Paris; files 1907–1913"),
    (r"^belgasonorilo", 865, "La Belga Sonorilo", "Bruxelles/Brugge Sep 1902–Aug 1908, then in Ido under the same title to Jul 1914; files 1902–1912"),
    (r"^JEN\.", 7255, "Jen", "humorous paper, Barcelona, Jul 1909–May 1910; files 1909–1910"),
    (r"^KaukazaEsperantisto\.", 7793, "Kaŭkaza Esperantisto", "Tiflis, Mar 1910–1912; files 1910"),
    (r"^GentoEsperanto\.", 5061, "Gento-Esperanto", "Gent, Jan 1913–1914; files 1913–1914"),
    (r"^BelgaKatoliko\.", 860, "Belga Katoliko", "B.K.L.E., Arendonk, May 1911–1914; files 1911–1913"),
    (r"^oge\.\d", 10482, "Oficiala Gazeto Esperantista", "organ of the Centra Oficejo and the Lingva Komitato; files oge.1–8"),
    (r"^tutmonda\.espero\.", 13120, "Tutmonda Espero", "Catalan bilingual monthly (subtitled Kataluna Esperantisto to Apr 1910); files 1908–1914"),
    (r"^RigaStelo_", 11692, "Riga Stelo", "Russian–Esperanto monthly, Riga; files 1910–1911"),
    (r"^EstlandaEsperantisto\.", 4336, "Estlanda Esperantisto", "Revel group's monthly; files 1908"),
    (r"^jbc\.bj\.uj\.edu\.pl\.NDIGCZAS0(43693|43884)_", 10933, "Pola Esperantisto",
     "the Jagiellonian Library's two runs: 043693 = the Lvov society's bimonthly from Oct 1906 (page 1; the early issues also as «Esperantysta Polski», n-ro 4271), 043884 = from Nov 1908 (page 1); every file names the title"),
    (r"^dlibra\.kul\.pl\.", 5074, "Germana Esperantisto (Der Deutsche Esperantist)",
     "Berlin, Jan 1905–1935; the Lublin library's files (the archive.org fetch of the title); every file names the title"),
    (r"^EsperoKleriga\.", 4288, "Espero (St Petersburg)",
     "monthly of the kleriga ligo and «Vestnik Znanja» (V. V. Bitner), Feb–Dec 1908; page 1 of 1908.1 agrees"),
    (r"^(IpI|IPI)[-_ ]", 6240, "Informilo por Interlingvistoj",
     "ACI, Warszawa, later with the CED (page 1 of IpI_125: «Informilo por Interlingvistoj … Eldonas … (CED)»); in Esperanto"),
    # The congress books and gazettes (2026-10-08 16:0x, approved by the editor): one entry per congress,
    # each searched by place and year. `kongresa.libro.NN` = the book of the NNth Universal Congress (the sources
    # inventory, an internal record, not published, lists congresses 1, 3, 4, 6, 7, 8, 9, 14). n-ro None: the title is given, the number was searched for and not found.
    (r"^kongresa\.libro\.01$", 8145, "Kongresa Libro (1st UK, Boulogne-sur-Mer 1905)", "«Kongresa Libro (I-a Kongreso de Esperanto). Boulogne-sur-Mer (FR), 1905»"),
    (r"^kongresa\.libro\.03$", None, "Kongresa Libro (3rd UK, Cambridge 1907)", "no entry found (searched: Kongresa Libro/Gazeto/Kuriero/Bulteno with Cambridge and 1907)"),
    (r"^kongresa\.libro\.04$", None, "Kongresa Libro (4th UK, Dresden 1908)", "no book entry found (the gazette is n-ro 8126)"),
    (r"^kongresa\.libro\.06$", None, "Kongresa Libro (6th UK, Washington 1910)", "no entry found (searched by place and year)"),
    (r"^kongresa\.libro\.07$", None, "Kongresa Libro (7th UK, Antwerp 1911)", "no book entry found (the gazette is n-ro 8121)"),
    (r"^kongresa\.libro\.08$", 8156, "Kongresa Libro (8th UK, Kraków 1912)", "«Kongresa Libro. [8-a Universala Kongreso de Esperanto]. Kraków (AT/PL), 11-18 de aŭg. 1912, 88 p.»"),
    (r"^kongresa\.libro\.09$", None, "Kongresa Libro (9th UK, Bern 1913)", "no book entry found (the gazette is n-ro 10523)"),
    (r"^kongresa\.libro\.14$", None, "Kongresa Libro (14th UK, Genève 1922)", "no entry found (searched by place and year)"),
    (r"^KK_1908_", 8126, "Kongresa Gazeto (4th UK, Dresden 1908)", "«Dresden (DE), 16-22 aŭg. 1908 … Entute 6 kajeroj»; the file holds nos. 1–6"),
    (r"^KK_1911_", 8121, "Kongresa Gazeto (7th UK, Antwerp 1911)", "«Antwerpen (BE), aŭg. 1911 … 6 n-roj»; the file holds nos. 1–6; also entered as n-ro 5011 (5 n-roj)"),
    (r"^KK_1913_", 10523, "Oficiala Kongresa Gazeto (9th UK, Bern 1913)", "«Bern (CH), 1913-aŭg. 25-31 … Entute 7 kajeroj (laŭ Stojan nur 6)»; the file holds nos. 1–6"),
    (r"^KK_1914_", 5008, "Gazeto de la Deka Kongreso (10th UK, Paris 1914, not held)", "«Paris (FR), jan.-aŭg. 1914, 8 p. … 8 kajeroj»; the file holds nos. 1–8"),
    (r"^oficiala_aldono_", None, "Oficiala Aldono al Universala Vortaro (the Lingva Komitato / Akademio)", "a book series of official word-list supplements, not a periodical: outside BPEAPE's scope (page 1 of 5a: «KVINA OFICIALA ALDONO AL UNIVERSALA VORTARO»)"),
    # The small BitArkivo journals (2026-10-08 16:3x, for the share with Kapis of BitArkivo, journals only): each against place and years
    (r"^FinnaEsperantisto\.", 4667, "Finna Esperantisto", "Helsinki, from 1907 (Ilarejo Esperantista); files 1907"),
    (r"^ParisEsperanto\.", 10753, "Paris-Esperanto", "the Paris group's monthly bulletin; files 1908–1910"),
    (r"^NordaGazeto\.", 10143, "Norda Gazeto", "the Nord-franca federation's bulletin, Saint-Omer; files 1912–1914"),
    (r"^LaBelaMondo\.", 840, "La Bela Mondo", "illustrated monthly, Dresden, Jul 1908–Jul 1909; files v1 1908, v2 1909"),
    (r"^GazetoHispana\.", 5017, "Gazeto Hispana", "the Hispana Societo's monthly, San Fernando (Cádiz); files 1911"),
    (r"^EsperantoRuslando\.", 3464, "Esperanto (Russia)", "«la unua rusa-Esperanta gazeto eldonita en Rusujo», permitted 1904; files 1905"),
    (r"^EsperantisteCatholique\.", 3292, "L’Espérantiste Catholique", "the French Catholic monthly (an Illustré variant is n-ro 3291); files 1910"),
    (r"^UniversalaJhurnalo_", 13231, "Universala Ĵurnalo", "Ruslanda Esperantista Ligo, St Petersburg, 1910–Apr 1911; file n01, Apr 1911"),
    (r"^TheEsperantist\.", 3189, "The Esperantist", "«la unua Brituja esperantista gazeto», London; the file named «1903-1904.v1» holds vols. 1 AND 2: vol. 1 Nov 1903–Dec 1904, PDF pages 11–268; vol. 2, the whole of 1905, «VOL. II» title page at PDF page 269, issues to PDF page 500 (2026-10-10)"),
    (r"^BulletinSectionPropagandeLigueBelge\.", 1282, "Bulletin de la Section de Propagande de la Ligue Belge", "Brugge, 1914; file 1914.1"),
    (r"^EsperantoEtCroixRouge\.", 3672, "Esperanto et Croix-Rouge", "bulletin of the Société Française Esperanto-Croix-Rouge; file 1910.1"),
    (r"^InternaciaMedicino\.", 6714, "Internacia Medicino", "TEKA's monthly, Dresden, Jan–Feb 1911, 2 n-roj; file 1911.1"),
    (r"^LaDekSepa\.", 2549, "La Dek-Sepa", "the bulletin of the Paris group's 17th-arrondissement section; file 1914, April"),
    (r"^KK_1912_", 8088, "Kongresa Bulteno (8th UK, Kraków 1912)", "daily during the congress, 11–17 Aug 1912, 5 issues; the file holds nos. 1–5"),
    # cupel17 (signed 2026-10-23; Ezri's request through the editor, 14:3x: titles before any is dowsed), matched by Miles
    # against bpeape-entries.tsv: the entry's place and years against the files' years
    (r"^ANNO_e7a_", 541, "Antaŭen Esperantistoj", "Lima, Perua Esperanto Societo (Villaréal); first epoch Jul 1903–Jun 1910, second Jul 1913–1916; files 1903–1914"),
    (r"^ANNO_e0d_", 2465, "Ĉirkaŭ la Mondo / Rund um die Welt", "Prague-Weinberge, Wolfenbüttel, Dresden (Schramm, Lederer), Sep 1909–1914; files 1909–1914"),
    (r"^ANNO_e1w_", 11946, "Scienca Gazeto", "Paris, the ISAE organ (Verax), Jan 1912–Jul/Aug 1914; files 1912–1914"),
    (r"^ANNO_e1v_", 11745, "Rondiranto", "Plovdiv, Klubo «Stelo» (Oreŝkov), Feb 1902–1904/05, bilingual; the same paper is also BPEAPE 11740; files 1902–1904"),
    (r"^ANNO_e0h_", 2549, "La Dek-Sepa", "the bulletin of the Paris group's 17th-arrondissement section, Dec 1910–Jul 1914; files 1910–1914"),
    (r"^ANNO_e5e_", 11027, "Portugala Revuo", "Porto, Esperantista Grupo de Porto; first series Mar–Jul 1909, second Jan 1913–Jul 1914; files 1909, 1913–1914"),
    (r"^ANNO_e6g_", 8972, "Lingua Internationale", "Bruxelles (Meysmans), monthly 1911–1912, 12 n-roj; files 1911–1912"),
    (r"^ONB_e1n_", 13819, "Vespera Horo / Abendstunde", "Huttwil, Bern, weekly organ for German Switzerland, Apr–Sep 1910; files 1910"),
    # cupel18a (signed 2026-10-24), matched by Miles against bpeape-entries.tsv: the entry's place and years against the
    # files' years
    (r"^ANNO_e5a_", 12675, "Svisa Espero", "Genève, the Svisa Esperanto-Societo's organ, first series Jan 1903–1920; files 1904–1916"),
    (r"^ANNO_e3s_", 4818, "Franca Esperantisto", "Paris (de Ménil, Grosjean-Maupin), first series Dec 1908–Dec 1912; files 1908–1912"),
    (r"^ANNO_e4h_", 1231, "Bulgara Esperantisto", "Sofia, printed in Pleven, Jan–Jul 1907, 3 n-roj, mostly in Bulgarian (not the 1919– organ, 1232); files 1907"),
    (r"^esperanta\.stelo$", 3153, "Esperanta Stelo", "Buenos Aires, the organ of the Esperanto group «Casal Català», Jan 1912–1914, cyclostyled by hand; the 1912 file, our transcription by vision (born-digital)"),
    # cupel18c (signed 2026-10-27), matched by Miles against bpeape-entries.tsv, the entry's place and years against the files'
    (r"^ANNO_e7p_", 2512, "Danubo", "Bucureşti, the Romanian and Bulgarian Esperantists' monthly (Robin), Oct 1910–Jul 1912, 19 numbers; files 1910–1912"),
    (r"^ANNO_e7s_", 7031, "Itala Esperantisto", "the Federazione Esperantista Italiana's bilingual monthly, Palermo, Genova, Milano, Jul–Aug 1910–Aug 1914; files 1911–1914"),
    (r"^ANNO_e1k_", 5787, "Informaj Raportoj", "Wien, the organ of the Verband der deutschsprachigen Esperanto-Gruppen in Österreich, Mar 1908–Dec 1910; files 1908–1910"),
    (r"^ANNO_e7i_", 7186, "Jarlibro de Tutmonda Esperantista Kuracista Asocio (T.E.K.A.)", "Kötzschenbroda 1909, Dresden 1910 (Thalwitzer), the doctors' association's yearbook; files 1909–1910"),
    (r"^117C5F54_pdf_1-76$", 10472, "Oficiala Bulteno de TEKA", "Paris, Aug 1911–Jul 1914, 8 numbers (Dor); the ÖNB file 1911–1912 (117C5F54)"),
    (r"^ANNO_e7r_", 11713, "Roma Esperantisto", "Roma, the Società Esperantista Romana's bilingual monthly (Giambene), from Jan 1907; files 1908"),
    (r"^ANNO_e6w_", 12441, "Stelo Kataluna", "Barcelona and Igualada, Jan–Jun 1908, 6 numbers; files 1908"),
    (r"^ONB_e3k_", 3488, "Esperanto, L'", "S. Vito al Tagliamento (Paolet), the Cattedra Italiana di Esperanto's fortnightly, first period Jan 1913–Dec 1922 (ÖNB files it as «Itala Esperanto-revuo»); files 1913–1914"),
    (r"^ANNO_e4d_", 13128, "Tutmonda Jarlibro Esperantista", "Paris (Hachette), with Zamenhof's address lists, first series 1904–1910 (the Aldono of 1913–14 is n-ro 288); files 1904–1910"),
]

# Outside BPEAPE: the editor ruled on 2026-10-08 11:5x that Helvetia is Occidental, and that Ido, Novial and Occidental
# will not be represented in BPEAPE. Named titles first, each with its evidence; then, for any other unmatched item, the language table's primary
# language (its first) if Ido, Occidental or Novial. Not the language table alone: it reads Mondo (Stockholm, Ido) as
# Esperanto. The column then says «none: <why>», so a search for «none:» finds them all.
OUTSIDE = [
    (r"^ANNO_e1e_", "Occidental (Helvetia: masthead «HELVETIA», 1932; decided by the editor, 2026-10-08)"),
    (r"^mondo\d{4}$", "Ido (Mondo, Stockholm: page 1 of mondo1912, «revuo por la linguo internaciona Ido»)"),
    (r"^ido\.\d{4}", "Ido (the title)"),
    (r"^Ido_Saluto_", "Ido (the title)"),
    (r"^posta[-_]mundi[-_]", "an inter-IAL newsletter (page 1 of posta_mundi_32: «Jurnal inter IAL», 2020)"),
]
LANG_OUTSIDE = {"ido": "Ido", "occidental": "Occidental", "novial": "Novial", "latino-sine-flexione": "Latino sine flexione"}
# A TITLE FOR A RUN BPEAPE DOES NOT NAME (2026-10-24, the editor 22:2x on La Genizo's OSR page, its list of the signed
# periodicals built from this table's titles: the item table has no titles for some runs, which needs fixing, and he
# asked whether 74 checked periodicals were all). By the title_key; only where no BPEAPE row gave a title, and no
# BPEAPE number is set or implied. The Volapük and Ido runs (outside BPEAPE) and runs BPEAPE has but no row matches yet.
TITLE_BY_KEY = {
    "anno_e2s": "Volapükabled", "levolapuk": "Le Volapük", "kosmopolan": "Kosmopolan", "el_volapuk": "El Volapük",
    "cogabled": "Cogabled", "mulapenad_nebolitik": "Mulapenad nebolitik", "nuns_blefik": "Nuns blefik",
    "nunel_valemik": "Nunel valemik", "volapukisten": "Volapükisten", "vp_monthly_boston": "The Volapük Monthly",
    "vpaflen_jveizik": "Volapükaflen jveizik", "vpaklubs": "Vpaklubs", "sionsharfe": "Sionsharfe",
    "labelgasonorilo": "La Belga Sonorilo", "anno_e4a": "Espero Katolika", "esperokatolika": "Espero Katolika",
    "anno_e1t": "Nederlanda Katoliko", "anno_e3g": "Brazila Esperantisto", "bultenoliberapenso": "Bulteno de Libera Penso",
    "liberapenso": "Libera Penso", "scholaetvita": "Schola et Vita", "anno_e1e": "Helvetia", "anno_e0g": "Kosmoglott",
    "mondo": "Mondo", "ido_saluto": "Ido-Saluto", "ido-saluto": "Ido-Saluto", "suisian.idisto": "Suisian Idisto",
    "romanal": "Romanal", "esperantista_movado": "Esperantista Movado", "espero.pacifista": "Espero Pacifista",
    "oficialajarlibro": "Oficiala Jarlibro", "lingvo.internacia.literatura.aldono": "Lingvo Internacia: Literatura Aldono",
    "esperantouea": "Esperanto (UEA)", "lalumo": "La Lumo", "lesperanto": "L’Esperanto",
    "the australian esperantist": "The Australian Esperantist",
    # the editor 22:4x (signed 2026-10-02)
    "novialiste": "Novialiste",
}
TITLE_BY_ITEM = [   # (2026-10-24 23:0x) the Volapük runs of cupel15–16 filed by volume, named as the source register names them
    (r"^nogan_vpik_yelod", "Nogan volapükik"), (r"^volaspodel", "Volaspodel"), (r"^vpan_nolik_", "Volapükan nolik"),
    (r"^nunal[._]nulik", "Nunal nulik"), (r"^jveizapot", "Jveizapot"), (r"^volapükan\.melopik|^volapukan\.melopik", "Volapükan Melopik"),
    (r"^rund_um_die_welt_y\d", "Rund um die Welt (Volapük)"), (r"^mittheilungen_", "Mittheilungen der Weltsprache-Vereine"),
    (r"^vom_guten_das_beste", "Vom Guten das Beste"), (r"^vpagased_lostanik", "Volapükagased lostanik"),
    (r"^vpabled_talik|^Volapukabled_talik", "Volapükabled tälik"), (r"^volapuk_journal_london", "Volapük Journal"),
    (r"^kosmopolan_contents", "Kosmopolan"), (r"^vpaflen_jveizik", "Volapükaflen jveizik"),
]

# ORIGIN (as the proposal on citable hits asks, an internal record, 2026-10-08, not published: the source's own names,
# not only ours): where a file came from, only as a record states it.
# The archive.org fetches keep a per-folder `_INDEX.md` (file · archive.org identifier · date …); a corpus PDF is named by
# its identifier, so a stem found there is an archive.org item. The index's own header says when the uploads are
# Bitarkivo.org's. ANNO files carry ANNO's title code; the second copies name their source (COPIES).
SOURCES = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources")


# Origins stated once for a whole run, where no per-file record exists; quoted from the record that states them.
ORIGIN_STATED = [
    (r"^RuslandaEsperantisto1905\.2$", "archive.org / Bitarkivo (sources/_INVENTORY.md, Ruslanda Esperantisto: «1905.2 from archive.org/bitarkivo»)"),
    (r"^RuslandaEsperantisto1910\.(1|2-3)$", "Bitarkivo, tempa.bitarkivo.org JPEG spreads, assembled 2026-09-12 (sources/_INVENTORY.md; the downloads kept as sources/ruslanda_esperantisto_1910_n_*_pbf.zip)"),
    (r"^(Lingvo Internacia |LEsperantiste\.|larevuo\.|juna\.esperantisto\.|ondodeesperanto\.|lamarto\.|RuslandaEsperantisto)",
     "ÖNB, downloaded issue by issue by the editor (2026-10-08: all of them from ÖNB, each downloaded by the editor); per-issue URLs not recorded"),
    (r"^EsperantoTriumfonta\.", "Bitarkivo, tempa.bitarkivo.org (sources/_INVENTORY.md: «from `tempa.bitarkivo.org`, named `EsperantoTriumfonta.<yyyy>.<nnn>.pdf`»; Bitarkivo's own file names not recorded)"),
    (r"^MezhdunarodnyjJazyk_", "BitArkivo / ÖNB, fetched by the editor 2026-10-03 (geniza-source-register-2026-08-31.md, «the Soviet Esperanto press»)"),
]


PAGE_MAP = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "ocr", "runs", "OCR-PAGE-MAP.tsv")


def from_page_map():
    """item → (first_text_page, pagination), from the page map (2026-10-08). first_text_page: the first PDF page that is
    neither front matter nor a digitiser's sheet (ruling 2: where the item would physically paginate from).
    pagination: «volume» when the item's first arabic printed number (read or extrapolated) is above 1 (it continues a
    numbering from earlier issues), «issue» when it is 1, empty when the map gives no arabic number."""
    out = {}
    if not os.path.exists(PAGE_MAP): return out
    by = {}
    for l in open(PAGE_MAP, encoding="utf-8"):
        if l.startswith("#") or l.startswith("item\t"): continue
        x = l.rstrip("\n").split("\t")
        if len(x) >= 4: by.setdefault(x[0], []).append((int(x[1]), x[2], x[3]))
    for c, rs in by.items():
        rs.sort()
        ftp = next((s for s, n, src in rs if src not in ("front", "skipped")), "")
        first = next((int(re.match(r"\d+", n).group()) for s, n, src in rs
                      if src in ("read", "iss", "vol", "count") and re.match(r"\d+", n or "")), None)
        pag = "" if first is None else ("volume" if first > 1 else "issue")
        out[c] = (str(ftp), pag)
    return out


def archive_ids():
    """stem → origin text, from the fetch records under sources/: (1) tempa.bitarkivo.org indexes (our file · Bitarkivo's
    own file name; the URL from the header's pattern); (2) archive.org indexes (our file · the item's identifier; the
    uploader Bitarkivo.org when the header says so); (3) identifier lists (IDENTIFIERS*.txt, one archive.org identifier
    a line; uploader not stated)."""
    import glob as _g
    out = {}
    for f in _g.glob(os.path.join(SOURCES, "**", "_INDEX*.md"), recursive=True):
        txt = open(f, encoding="utf-8", errors="ignore").read()
        rel = os.path.relpath(f, SOURCES); head = txt[:1500]
        tm = re.search(r"(https://tempa\.bitarkivo\.org/[^\s`<]*?)<original name>", head)
        if re.search(r"^\|\s*identifier\s*\|", txt, re.M | re.I):      # tools/ia-fetch-title.py's layout: identifier first
            for m in re.finditer(r"^\|\s*`([A-Za-z0-9._-]+)`\s*\|", txt, re.M):
                out.setdefault(m.group(1), f"archive.org: «{m.group(1)}», https://archive.org/details/{m.group(1)} (sources/{rel})")
            continue
        for m in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|", txt, re.M):
            ours = re.sub(r"\.(pdf|txt)$", "", m.group(1)); theirs = m.group(2)
            if tm:
                out.setdefault(ours, f"Bitarkivo, tempa.bitarkivo.org: «{theirs}», {tm.group(1)}{theirs} (sources/{rel})")
            else:
                who = "Bitarkivo.org upload on archive.org" if re.search(r"bitarkivo", head, re.I) else "archive.org"
                o = f"{who}: «{theirs}», https://archive.org/details/{theirs} (sources/{rel})"
                out.setdefault(theirs, o); out.setdefault(ours, o)
    for f in _g.glob(os.path.join(SOURCES, "**", "IDENTIFIERS*.txt"), recursive=True):
        rel = os.path.relpath(f, SOURCES)
        for l in open(f, encoding="utf-8", errors="ignore"):
            x = l.strip().split()[0] if l.strip() else ""
            if re.fullmatch(r"[A-Za-z0-9._-]+", x):
                out.setdefault(x, f"archive.org: «{x}», https://archive.org/details/{x} (identifier list sources/{rel})")
    return out
LANG_TABLES = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")


def primary_languages():
    import glob as _g
    tabs = sorted(_g.glob(os.path.join(LANG_TABLES, "OCR-TEXT-LANGUAGES-20*.tsv")))
    out = {}
    if not tabs: return out, None
    for l in open(tabs[-1], encoding="utf-8"):
        if l.startswith("#"): continue
        x = l.rstrip("\n").split("\t")
        if len(x) >= 2 and x[1]: out[x[0]] = x[1].split(",")[0]
    return out, os.path.basename(tabs[-1])

# A dotted title's label, once checked: "month" or "issue". Empty until each is checked against a cover or a
# catalogue; each entry to say how it was checked.
# A dotted label that names no issue, with the issue its masthead prints (stem → (issue, month, why)); the file keeps its
# name (renaming a source is the editor's ruling), the row says what it is.
LABEL_READ = {
    "EsperantoRuslando.1905.sennumera": ("1-2", "1", "the label «sennumera» (unnumbered) is the file's: its masthead reads N-ro 1–2, January 1905; "
                                         "a second copy of EsperantoRuslando.1905.1-2 (COPIES in tools/ocr-dowse.py; Ezri, 2026-10-24)"),
}
DOTTED = {   # "month", "month+issue" (numbered by month: «N-ro» = the month, seen), "issue" or "part" (a 50-page part of a volume, as the ÖNB split it); checked 2026-10-08 by Miles: page 1 of three files per title (geniza/sources/ocr-work/item-table-draft-2026-10-08/DOTTED-LABEL-CHECK-1.txt)
    "juna.esperantisto": "month+issue", # 1907.08, 1909.12, 1912.03: the cover's month (and its N-ro) = the label
    "ondodeesperanto": "month",         # 1911.01, 1912.11, 1914.05: the cover's month = the label
    "gentoesperanto": "month",          # 1913.3, .6, .11: the cover's month = the label
    "junaesperantisto": "month",        # 1911.3, .6, .10: the cover's month = the label
    "vochodekuracistoj": "month+issue", # 1909.8, 1910.4, 1911.1: «Nro» and the month both = the label (a monthly numbered by month)
    "esperanto": "month+issue",         # La Esperantisto 1891.1, 1891.10: «Nro» and the month = the label (only its dotted files are numeric)
    "esperantotriumfonta": "issue",     # labels 039–090 (a weekly): issue numbers
    "katalunaesperantisto": "issue",    # 1911.15 prints «N-ro 15»; labels run past 12
    "esperantoruslando": "issue",       # 1905.1-2 prints «N-ro 1–2», January 1905 (Miles 2026-10-24, Ezri's request; the run's two files)
    "kovnoesperanto": "issue",          # labels 13–36: issue numbers
    "lasunohispana": "issue",           # labels 1–78: issue numbers
    "kaukazaesperantisto": "issue",     # labels to 14 within 1910 (a semi-monthly): issue numbers
    # checked 2026-10-08 15:4x (approved by the editor), from each year's labels and the page map's printed ranges:
    "lesperantiste": "month+issue",     # 1–12 every year with a summer double (8-9 or 7-8) every year; May 1907 = «n° 5 (110)»
    "lamarto": "month",                 # 1910 holds only 11 and 12, and the paper began in Nov 1910 (BPEAPE n-ro 9272)
    "lingvo internacia": "part",        # the files are 50-page parts of the year's volume, printed ranges continuous
    "larevuo": "part",                  #   (1–50, 51–100 … 551–576): the ÖNB's split, not issues; «0», «0.1» and the
                                        #   high numbers are the volume's other matter, kept as filed
}

COLS = ["item", "title_key", "title", "bpeape", "volume", "year", "issue", "month", "day", "date",
        "label_as_filed", "parsed_by", "pagination", "first_text_page", "origin", "notes",
        # 2026-10-09 (the editor ruled that anything written before 1914 is primary, that this must be findable, and
        # that the year of authoring of the witness is crucial): the year of writing, what it rests on, and the kind by the rule. Books from
        # the newest geniza/ocr/runs/OCR-ITEM-DATES-*.tsv (tools/ocr-item-dates.py); periodical issues from their own year.
        "written", "written_from", "kind",
        # 2026-10-16 (an assistant's request, approved by the editor, who ruled that the keys list should include the
        # full citation rather than proliferate sources of truth): the item's KEY, a slug without spaces
        # that locators carry, pinned in OCR-ITEM-KEYS.tsv so it never changes on a re-run; and its CITATION, Chicago
        # author-date, from CITATIONS below. Added at the END so that readers of the table by column position are unchanged.
        "key", "citation"]

# THE KEYS (2026-10-16). geniza/OCR-ITEM-KEYS.tsv: item → key, one row an item, ONLY EVER ADDED TO (--assign-keys).
# A key once written is never recomputed: the slug rule may change, the key does not. The rule for a new item: the
# name folded to ASCII lower case, every run of other characters one «-», never shortened (a cut at 64 characters
# dropped the very part that told two issues apart: «… Esperantista Unio 1» and «… 2»); a key already taken gets
# «-2», «-3» … (by the items' sorted order). KEY_PINNED: a chosen key, used instead of the rule when the item is first
# keyed (for example «neves-parnaso-2018»); it does nothing to an item already keyed.
KEYS_TSV = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "OCR-ITEM-KEYS.tsv")
KEY_PINNED = {
    "Esperanto ed Ido_diferanta voyi adsur Parnaso": "neves-parnaso-ido-2018",
    "Esperanto kaj Ido_malsamaj vojoj sur Parnason": "neves-parnaso-eo-2019",
    # Neves's 35 comments on Trevor Steele's video lecture «La krizo de Ido» (2022), the Esperanto text and its Ido
    # translation (archive.org 35-komentoj-de-neves, 35-komenti-da-neves)
    "35_komentoj_de_Neves": "neves-steele-2022-35-komentoj-eo",
    "35_komenti_da_Neves": "neves-steele-2022-35-komenti-io",
}
# Parts named only by their number (2026-10-16: they would otherwise get keys that do not name their work): the work's name
# before the rule's slug. (pattern on the item, prefix)
KEY_PINNED_PREFIX = [
    # files 00–44 from www.plansprachen.ch: one book, Andreas Künzli, «Universalaj Lingvoj en
    # Svislando» (La Chaux-de-Fonds, 2006) (a folder map, an internal record, 2026-09-03, not published)
    # (05-07_ENCYCL_INTRO_div too: «the rest of Parto 1», five introductory essays, one from 1985 reprinted; 2026-10-16)
    (r"^\d\d(-\d\d)?_(COUVERTURE|ENCYC?L|ANTOL)", "kunzli-2006-"),
]


def slug(stem):
    import unicodedata
    s = unicodedata.normalize("NFKD", stem).lower()     # lower case after NFKD: «№» decomposes to «No»
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for a_, b_ in (("ß", "ss"), ("ø", "o"), ("æ", "ae"), ("œ", "oe"), ("ł", "l"), ("đ", "d")):
        s = s.replace(a_, b_)
    s = "".join(CYR.get(ch, ch) for ch in s)        # Cyrillic transliterated, not dropped («№ 1» alone was left of one name)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s or re.search(r"[^a-z0-9-]", s):
        import hashlib
        s = "item-" + hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
    return s


def read_keys():
    """item → key, reading the rows in order. A RENAME row (third column: the old name; --rename) moves the old name's
    key to the new name, so a renamed file keeps its key and every locator that carries it (2026-10-16)."""
    out = {}
    if os.path.exists(KEYS_TSV):
        for l in open(KEYS_TSV, encoding="utf-8"):
            if l.startswith("#") or l.startswith("item\t") or not l.strip(): continue
            x = l.rstrip("\n").split("\t")
            it, k = x[0], x[1]
            if len(x) > 2 and x[2]:
                if out.get(x[2]) != k:
                    sys.exit(f"refusing: OCR-ITEM-KEYS.tsv renames {x[2]} to {it} with key {k}, but {x[2]} has key {out.get(x[2])}")
                del out[x[2]]
            out[it] = k
    return out


# NO OPAQUE KEYS (the editor ruled on 2026-10-16 23:1x, on «anno-e4a-19130193», that opaque keys are not accepted and
# that the journal's actual name must be found). A file named by a library's code or number gets its work's name first.
# ANNO's title codes, each as its run is named in our records and on its mastheads (the sources inventory, an internal record, not published):
ANNO_TITLES = {
    "e4a": "espero-katolika", "e1t": "nederlanda-katoliko", "e1e": "helvetia", "e0g": "kosmoglott",
    "e0f": "esperanto-uea", "e7d": "fervoja-esperantisto", "e5c": "internacia-pedagogia-revuo", "e2a": "the-esperantist",
    "e1c": "pola-esperantisto", "e1a": "germana-esperantisto", "e2s": "volapukabled", "e0a": "la-esperantisto",
    # ANNO files the run as one title; its 1907 mastheads read «BRAZILA REVUO ESPERANTISTA», later «BRAZILA ESPERANTISTO»
    "e3g": "brazila-esperantisto",
    # cupel17 (signed 2026-10-23), the codes as Ezri matched them by their mastheads (relayed 2026-10-23 14:3x); e0d is
    # the Esperanto paper «Ĉirkaŭ la mondo» (Schramm), German title «Rund um die Welt», not Schleyer's Volapük paper
    "e7a": "antauen-esperantistoj", "e0d": "cirkau-la-mondo", "e1w": "scienca-gazeto", "e1v": "rondiranto",
    "e0h": "la-deksepa", "e5e": "portugala-revuo", "e6g": "lingua-internationale",
    # cupel18a (signed 2026-10-24), by the mastheads seen at its C1
    "e5a": "svisa-espero", "e3s": "franca-esperantisto", "e4h": "bulgara-esperantisto",
    # cupel18b (signed 2026-10-26), by the title pages and running heads seen at its C1 and C6 looks
    "e4d": "tutmonda-jarlibro-esperantista",
    # cupel18c (signed 2026-10-27), by the mastheads and title pages seen at its C1 and C6 looks
    "e7p": "danubo", "e7s": "itala-esperantisto", "e1k": "informaj-raportoj", "e7i": "teka-jarlibro",
    "e7r": "roma-esperantisto", "e6w": "stelo-kataluna",
}
# By the folder the PDF is in (relative to geniza/sources/): the work all its files belong to.
FOLDER_PREFIX = {
    "ipi": "informilo-por-interlingvistoj-",              # «Informilo por Interlingvistoj», by issue number
    "pola-esperantisto": "pola-esperantisto-",            # Lublin's 1957–1960 issues, by edition number
    "archive-org-ido/astro_idista_1": "astro-idista-",
    "archive-org-ido/ido_vivo_3_1988": "ido-vivo-",
    "archive-org-ido/posta-mundi-40": "posta-mundi-", "archive-org-ido/posta-mundi-41": "posta-mundi-",
    "archive-org-ido/originala-verkaro": "originala-verkaro-",
    "berlina-komentario": "berlina-komentario-",          # Pabst's «Berlina Komentario»: only its own parts (BK…, HV…), below
    "pioniroj-de-esperanto/2018-06-13-biografio-pri-kazimierz-bein": "pioniroj-bein-",
}
# By name, each read from the file's first page or its record (2026-10-16):
KEY_PINNED.update({
    "117C5F54_pdf_1-76": "oficiala-bulteno-de-teka-1911-1912-onb-117c5f54",          # _INVENTORY: the Oficiala Bulteno de T.E.K.A. 1911–1912 (ÖNB 117C5F54)
    "10B83C47_pdf_1-291": "cart-vocabulaire-francais-esperanto-1907-onb-10b83c47",   # _INVENTORY: Cart's dictionary, 5th ed. 1907 (ÖNB 10B83C47)
    "LM_1931-07c": "literatura-mondo-1931-07c",                                      # _INVENTORY: Literatura Mondo, the Kabe item
    "mat_0769-3206_1994_num_34_1_402776": "panteleiev-1994-materiaux-histoire-34",   # _INVENTORY: Panteleiev, Matériaux … 34 (1994), Persée
    "LLZ-Bio-En": "korzhenkov-2009-zamenhof-life-works-ideas-en",                    # p. 1: Korzhenkov, «Zamenhof: The Life, Works, and Ideas …», tr. Richmond, ESF 2009
    "agi": "kauling-agi-dil-apostoli",                                               # p. 1: «Agi dil Apostoli … tradukita da L. Kauling» (ido-vivo.info)
    "kgd": "beaufront-kompleta-gramatiko-detaloza-ido",                              # p. 1: «Kompleta gramatiko detaloza di la linguo internaciona Ido da L. de Beaufront»
    "t3": "ido-societo-hispana-rakonteti-e-fabli-1",                                 # p. 1: «rakonteti e fabli … unesma tomo», Ido-Societo Hispana
    # the name's «Ă–» is a mis-decoded «Ö»: a second copy of plansprachen-kunzli/Esperanto_Immaterielles_Kulturerbe_Österreich.pdf
    "Esperanto_Immaterielles_Kulturerbe_Ă–sterreich": "esperanto-immaterielles-kulturerbe-osterreich-plansprachen-ch-copy",
    # KongresaKuriero/KK_*: the congress papers, by their BPEAPE titles (BPEAPE above)
    "KK_1908_gazeto_n01-06": "kongresa-gazeto-1908-dresden-n01-06",
    "KK_1911_kongresagazeto_n01-06": "kongresa-gazeto-1911-antwerp-n01-06",
    "KK_1912_Krakovo_KongresaBulteno_n1-5": "kongresa-bulteno-1912-krakow-n1-5",
    "KK_1913_kongresagazeto_n01-06": "oficiala-kongresa-gazeto-1913-bern-n01-06",
    "KK_1914_Gazeto_n1-8": "gazeto-de-la-deka-kongreso-1914-paris-n1-8",
    "Lo-328demo": "la-ondo-de-esperanto-328-demo",        # La Ondo de Esperanto, a demo issue
    "UN_75jara": "kunzli-2020-un-75-jara",                # p. 1: «UN 75-jara … De Andreas Künzli»; the UN's 75th year, 2020
})
CYR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґў",
               ["a","b","v","g","d","e","e","zh","z","i","i","k","l","m","n","o","p","r","s","t","u","f","kh","ts","ch","sh",
                "shch","","y","","e","iu","ia","i","i","ie","g","u"]))


def work_key(it, folder):
    """the key from the work's name, for a name that does not carry it; None when the rule's slug will do"""
    m = re.match(r"^ANNO_([a-z0-9]{3})_(1[89]\d\d|20\d\d)(\d{4})(?:[. ]\(?(\d+)\)?)?$", it)
    if m:
        t = ANNO_TITLES.get(m.group(1))
        if t: return f"{t}-{m.group(2)}-anno-{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
    m = re.match(r"^ONB_e1n_(1[89]\d\d)(\d\d)(\d\d)$", it)  # cupel17: Vespera Horo / Abendstunde 1910, ÖNB, by date
    if m: return f"vespera-horo-{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^ONB_e3k_(1[89]\d\d)(\d\d)(\d\d)$", it)  # cupel18c: L'Esperanto (S. Vito al Tagliamento), ÖNB's «Itala Esperanto-revuo», by date
    if m: return f"l-esperanto-s-vito-{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"^jbc\.bj\.uj\.edu\.pl\.NDIGCZAS(\d+)_(.+)$", it)
    if m: return f"pola-esperantisto-jbc-{m.group(1)}-{slug(m.group(2))}"
    m = re.match(r"^dlibra\.kul\.pl\.(\d+)$", it)
    if m: return f"germana-esperantisto-kul-{m.group(1)}"
    if it in ISSUES_READ:                                   # Pola Esperantisto 1957–1960, read by hand
        y, iss, _, _ = ISSUES_READ[it]; return f"pola-esperantisto-{y}-n{slug(iss)}-{it}"
    m = re.match(r"^ipi-(\d+)$", it)
    if m: return f"informilo-por-interlingvistoj-{m.group(1)}"
    pre = FOLDER_PREFIX.get(folder)
    if folder == "berlina-komentario" and not re.match(r"^(BK|BKB|HV)[ _-]", it):
        pre = None                                          # the folder's other files (Oficiala Aldono, dictionaries) name themselves
    if pre and not slug(it).startswith(pre.rstrip("-")):
        sl = slug(it)
        if pre.startswith("informilo"): sl = re.sub(r"^ipi-?", "", sl)   # «IpI126» → informilo-por-interlingvistoj-126
        return pre + sl
    return None


def new_keys(items, have, folders=None):
    """keys for the items not yet keyed: the pinned key, else the work's name, else the rule; never a key already taken"""
    folders = folders or {}
    taken = set(have.values()); out = {}
    for it in items:
        if it in have or it in out: continue
        base = KEY_PINNED.get(it) or next((p + slug(it) for rx, p in KEY_PINNED_PREFIX if re.search(rx, it)), None) \
            or work_key(it, folders.get(it, "")) or slug(it); k = base; n = 2
        while k in taken:
            k = f"{base}-{n}"; n += 1
        taken.add(k); out[it] = k
    return out

# THE CITATIONS (2026-10-16): item → the reference, Chicago author-date, as a reference list gives it. Each from the
# item's own title page (the OCR of its first pages, said which) or, for a transcription, the record its header names;
# a field the source does not give is left out, never supplied from memory. A periodical's issues are not here yet.
CITATIONS = {
    # title page, PDF pp. 2–3 (OCR): «Aleksander Korĵenkov HISTORIO DE ESPERANTO Serio Scio Volumo 5»; the series list:
    # «5. Koĵenkov A. Historio de Esperanto Kaliningrado, 2005»; no publisher on these pages
    "korzhenkov-historio-2005": "Korĵenkov, Aleksander. 2005. *Historio de Esperanto*. Serio Scio 5. Kaliningrado.",
    # title page, PDF p. 2 (OCR): «GASTON WARINGHIEN LINGVO KAJ VIVO ESPERANTOLOGIAJ ESEOJ J. REGULO - ELDONISTO - LA LAGUNA MCMLIX»
    "waringhien-lingvo-kaj-vivo-1959": "Waringhien, Gaston. 1959. *Lingvo kaj vivo: Esperantologiaj eseoj*. La Laguna: J. Régulo.",
    # title page, PDF p. 2 (OCR): «Dro W. MANDERS INTERLINGVISTIKO KAJ ESPERANTOLOGIO J. MUUSSES ELDONISTO - PURMEREND MCML»
    "manders-1950": "Manders, W. 1950. *Interlingvistiko kaj esperantologio*. Purmerend: J. Muusses.",
    # title page and imprint, PDF pp. 1–3 (OCR): «Editerio Sudo Espinho, Portugal duesma edituro decembro 2018»;
    # «Unesma edituro: novembro di 2018 Duesma edituro: decembro di 2018»
    "Esperanto ed Ido_diferanta voyi adsur Parnaso": "Neves, Gonçalo. 2018. *Esperanto ed Ido: diferanta voyi adsur "
        "Parnaso; komparanta studiuro pri la developeso di Esperanto ed Ido kom poeziala lingui*. 2nd ed. Espinho: Editerio Sudo.",
    # title page, PDF pp. 1–2 (OCR): «Reviziita, pliampleksigita kaj ĝisdatigita eldono Eldonejo Drako Espinho, Portugalio junio 2019»
    "Esperanto kaj Ido_malsamaj vojoj sur Parnason": "Neves, Gonçalo. 2019. *Esperanto kaj Ido: malsamaj vojoj sur "
        "Parnason; kompara studo pri la disvolviĝo de Esperanto kaj Ido kiel poeziaj lingvoj*. Rev. and enl. ed. Espinho: Eldonejo Drako.",
    # the text's own head: «Artikolo reprodukita el "Franca Esperantisto" Junio 1998, n-ro 498, pp. 42-48»; what we hold
    # is the aleph.com.br reproduction in the Wayback Machine's capture of 3 May 2006, saved 2026-10-08
    "jossinet-1998-beaufront": "Jossinet, Roland. 1998. “La franca savinto de Esperanto: Louis de Beaufront.” "
        "*Franca Esperantisto*, no. 498 (June): 42–48. Reproduced at http://www.aleph.com.br/kce/historio-12-beaufront.htm; "
        "archived 3 May 2006, http://web.archive.org/web/20060503145938/http://www.aleph.com.br/kce/historio-12-beaufront.htm; "
        "saved 8 October 2026.",
    # the transcription's header, from the book: «Krestomatio de Esperanta Literaturo: tekstoj, dataro, bibliografio,
    # vol. I (Budapest: Tankönyvkiadó, 1979)»
    "szerdahelyi-krestomatio-1979": "Szerdahelyi, István. 1979. *Krestomatio de Esperanta literaturo: tekstoj, dataro, "
        "bibliografio*. Vol. 1. Budapest: Tankönyvkiadó.",
    # NOT the title page: our scan is the editor's selection of chapters (printed pp. 287 ff.) and holds no title page;
    # editor, place and publisher are «to be added from the book» (the sources inventory, an internal record, 2026-10-03, not published). Title and year only.
    "li-kaj-ni-1985": "*Li kaj Ni*. 1985.",
    # The Somme records (archival: archive, register, commune, year of the register; 2026-10-16): each from its
    # transcription's header, with the archive's URL. The series (cote) is not in
    # our records, so it is left out
    "ad80-grivesnes-liste-electorale-1912": "Archives départementales de la Somme. Liste électorale, Grivesnes, 1912. https://archives.somme.fr/ark:/58483/rtxh1b9j0572/2a0c1d3b-0707-41c9-9d03-fd53399ffc29.",
    "ad80-grivesnes-liste-electorale-1919": "Archives départementales de la Somme. Liste électorale, Grivesnes, 1919. https://archives.somme.fr/ark:/58483/bxc8kfnl391m/849a043a-cd7d-497a-9aa3-07e7dfe9380e.",
    "ad80-grivesnes-liste-electorale-1920": "Archives départementales de la Somme. Liste électorale, Grivesnes, 1920. https://archives.somme.fr/ark:/58483/zm4kh5w8j6fq/a0824877-1da1-44d3-9603-5390a2cecb34.",
    "ad80-grivesnes-recensement-1911": "Archives départementales de la Somme. Recensement de population, Grivesnes, 1911. https://archives.somme.fr/ark:/58483/f60j2wx9qtg8/313b135c-7028-4fa1-8718-22b81a17494a.",
    "ad80-grivesnes-recensement-1921": "Archives départementales de la Somme. Recensement de population, Grivesnes, 1921. https://archives.somme.fr/ark:/58483/65n7w4qz8ts9/1aa75318-3246-4c1d-b4d9-fe8ba5b14cca.",
    "ad80-grivesnes-recensement-1926": "Archives départementales de la Somme. Recensement de population, Grivesnes, 1926. https://archives.somme.fr/ark:/58483/tx2m3vk6ndrc/d529dd2f-ec4c-4445-8b3a-59954530a94b.",
    "ad80-grivesnes-recensement-1931": "Archives départementales de la Somme. Recensement de population, Grivesnes, March 1931. https://archives.somme.fr/ark:/58483/9bts160lmxw2/27653d14-699d-482f-b0af-a8abee35ef86.",
    "ad80-marestmontiers-recensement-1926": "Archives départementales de la Somme. Recensement de population, Marestmontiers, 1926. https://archives.somme.fr/ark:/58483/x0d1685ptgr7/b236e98e-c1ca-4742-99b6-582df14850b9.",
    "ad80-marestmontiers-recensement-1931": "Archives départementales de la Somme. Recensement de population, Marestmontiers, 1931. https://archives.somme.fr/ark:/58483/lsb1zrpdqn93/ba076f76-10be-4386-9c1d-7ae7f351bbe4.",
    "ad80-thezy-glimont-recensement-1926": "Archives départementales de la Somme. Recensement de population, Thézy-Glimont, 1926. https://archives.somme.fr/ark:/58483/8zdb7pk43mv5/ca9d59bf-dcdd-4ce8-805b-308900d668f0.",
    "ad80-thezy-glimont-recensement-1931": "Archives départementales de la Somme. Recensement de population, Thézy-Glimont, 1931. https://archives.somme.fr/ark:/58483/9rgsjqk4zv1l/764e1288-7c58-432a-8151-3d6d914fcf83.",
    # indexes of civil records, not the registers (the headers): the site and its page, as saved 2026-10-08
    # (no page title given in the headers: described, not titled)
    "acte-de-naissance-fr-grivesnes-guerard": "Acte-de-naissance.fr. n.d. Index of births, Grivesnes. Accessed 8 October 2026. https://www.acte-de-naissance.fr/acte-de-naissance-grivesnes.",
    "acte-deces-fr-famille-guerard": "Acte-deces.fr. n.d. Index of deaths, Guérard family. Accessed 8 October 2026. https://www.acte-deces.fr/recherche-deces-famille-guerard.",
    # the header: «the death record of Louis de Beaufront, Thézy-Glimont, January 1935, reproduced in SAT-Amikaro's 2014
    # dossier on de Beaufront (document 7 …)»; the page that posts the dossier, saved 2026-10-08:
    # «Sep dokumentoj pri la identeco
    # de Bofronto», posted 27 April 2014. A record reproduced, so the record first, then where.
    "sat-amikaro-2014-bofronto-mortakto": "Death record of Louis de Beaufront, Thézy-Glimont, January 1935. Reproduced "
        "as document 7 in SAT-Amikaro, “Sep dokumentoj pri la identeco de Bofronto,” 27 April 2014, "
        "https://www.sat-amikaro.org/sep-dokumentoj-pri-la-identeco-de-bofronto.",
}


# Pola Esperantisto, the renewed series 1957–1960, filed by number only: year, issue and months READ from each issue's
# whole OCR (masthead «N-RO … — JARO … — 19..»), or placed in the run where the masthead is illegible (said so). The
# editor ruled on 2026-10-09 17:0x that the Pola Esperantisto dates are needed, since they are cited for the work on Kabe.
SPAN_READ = {   # stem → (years, volumes, what was read); the file's own name would give less
    "TheEsperantist.1903-1904.v1": ("1903–1905", "1–2", "holds vols. 1 AND 2: vol. 1 Nov 1903–Dec 1904, PDF pages 11–268; "
                                    "vol. 2, the whole of 1905, «VOL. II» title page at PDF page 269, issues to PDF page 500 "
                                    "(read 2026-10-10)"),
}
# A book or article whose file name carries a year that is not its own (life dates in a title), its year read from the
# text (2026-10-11 02:28: the life dates in its file name had apparently been read as its year; checked).
YEAR_READ = {   # stem → (year, what was read)
    "Contribution_of_A_Jakstas-Dambrauskas_1860-1938_to": ("2017", "PDF page 1: «Advances in Historical Studies, 2017, 6, "
        "1-17» · «Banionis, J. (2017)»; 1860-1938 are A. Jakštas-Dambrauskas's life dates (read 2026-10-11)"),
}
ISSUES_READ = {
    "46027": ("1957", "1", "Sept–Oct", "masthead «N-RO 1 — JARO 32 [37] — 1957»; first issue of the renewed series; Zamenhof commemoration of 14 Apr 1957"),
    "46028": ("1957", "2", "Nov–Dec", "masthead «N-RO 2 — JARO 37 — 1957»"),
    "46029": ("1958", "1", "Jan–Feb", "masthead «N-RO 1 — JARO 38 — 1958»"),
    "46030": ("1958", "2", "Mar–Apr", "masthead year illegible («MARTO -APRILO»); reprints La Verda Vojo «(marto — aprilo 1958)»; placed in the run"),
    "46031": ("1958", "3", "May–Jun", "masthead year illegible; announces the 44th UK «next year in Poland» (Warsaw 1959); placed in the run"),
    "46033": ("1958", "4", "Jul–Aug", "masthead illegible («JULIO ~ AŬGUSTO»); prints the speech of 3.VIII.1958 at the Mainz UK; before n-ro 5/6 of 1958; placed in the run"),
    "46034": ("1958", "5/6", "Sept–Dec", "masthead «N-RO 5/6 – JARO 38 – 1958»"),
    "46083": ("1959", "1-2", "Jan–Apr", "masthead «N-RO 1-2 — JARO 39 — 1959»"),
    "46084": ("1959", "3-4", "May–Aug", "masthead «N-RO 3 — 4 JARO 39 — 1959»"),
    "46086": ("1959", "5", "Sept–Oct", "masthead «N-RO 5, JARO 39 — 1959»"),
    "46090": ("1959", "6", "Nov–Dec", "masthead «N-RO 6, JARO 39 — 1959»"),
    "46092": ("1960", "1", "", "masthead year not printed; «the past year … the 44th UK in Warsaw» (1959); placed in the run"),
}

PIECES = re.compile(r"Esperanto[ .](189[2-5])\.(\d)")   # La Esperantisto 1892–1895 (ÖNB), filed as 50-page pieces


def parse(stem):
    r = {k: "" for k in COLS}
    r["item"] = stem; r["title_key"] = _ps.title_of(stem)
    if stem in COPIES:
        of, where = COPIES[stem]
        q = parse(of); q["item"] = stem; q["notes"] = f"second copy of {of} ({where})"; return q
    if stem in ISSUES_READ:
        y, iss, months, ev = ISSUES_READ[stem]
        r.update(title="Pola Esperantisto", year=y, issue=iss, parsed_by="R",
                 notes=f"Pola Esperantisto {y}, n-ro {iss}" + (f", {months}" if months else "") + f": read 2026-10-09 ({ev})")
        return r
    if stem in SPAN_READ:   # a file whose name understates what it holds, read by hand
        y, vol, ev = SPAN_READ[stem]
        r.update(year=y, volume=vol, parsed_by="R", notes=ev)
        return r
    if stem in YEAR_READ:   # a file whose name carries someone's life dates, not its own year
        y, ev = YEAR_READ[stem]
        r.update(year=y, parsed_by="R", notes=ev)
        return r
    m = PIECES.fullmatch(stem)
    if m:   # a download piece of a year's volume, not an issue
        r.update(year=m.group(1), label_as_filed=f"piece {m.group(2)}", parsed_by="Y",
                 notes="a piece of the year's volume as downloaded from the ÖNB, not an issue: every piece is 50 PDF pages, "
                       "the year's last shorter (checked 2026-10-09; the single issues of 1889–1891 are 2–16 pages)")
        return r
    m = ANNO.match(stem)
    if m:
        r.update(year=m.group(2), label_as_filed=m.group(3), parsed_by="N", notes=f"ANNO title code {m.group(1)}")
        return r
    m = D.search(stem)
    if m:
        r.update(year=m.group(1), month=str(int(m.group(2))), day=str(int(m.group(3))),
                 date=f"{m.group(1)}-{m.group(2)}-{m.group(3)}", parsed_by="D"); return r
    mc = re.fullmatch(r"(.+_(?:1[89]|20)\d\d_.+?)\.(\d)", stem)
    if mc and A.search(mc.group(1)):
        q = parse(mc.group(1)); q["item"] = stem
        q["notes"] = "; ".join(x for x in (q["notes"], f"«.{mc.group(2)}»: a further copy of {mc.group(1)} (not in COPIES: check)") if x)
        return q
    m = A.search(stem)
    if m and (m.group(3) or m.group(5) or m.group(6) or (m.group(2) and m.group(9) and m.group(9).isdigit())):
        y1, y2, vk, vn, iss, m1, m2, day, rest = m.groups()
        r["year"] = y1 + (f"–{y2}" if y2 else "")
        if vn: r["volume"] = ("jaro " if vk.lower() == "j" else "") + str(int(vn))
        if iss: r["issue"] = "-".join(str(int(x)) for x in iss.split("-"))
        mm = [MON.get(x.lower()) for x in (m1, m2) if x]
        if mm and all(mm):
            r["month"] = "-".join(map(str, mm))
            if day and len(mm) == 1:
                r["day"] = str(int(day)); r["date"] = f"{y1}-{mm[0]:02d}-{int(day):02d}"
        elif m1:
            rest = "_".join(x for x in (m1 + (f"-{m2}" if m2 else "") + (day or ""), rest) if x)
        if rest: r["label_as_filed"] = rest
        r["parsed_by"] = "A"; return r
    m = B.search(stem)
    if m:
        r["year"] = m.group(1)
        lab = m.group(2) or ""
        meaning = DOTTED.get(r["title_key"])
        if lab and meaning in ("month", "month+issue") and re.fullmatch(r"\d{1,2}(-\d{1,2})*", lab):
            r["month"] = "-".join(str(int(x)) for x in lab.split("-"))
            if meaning == "month+issue":   # «N-ro» = the month, seen on the covers (2026-10-08, a redowse: Jamin's
                r["issue"] = r["month"]     # issue column was empty)
        elif lab and meaning == "part" and re.fullmatch(r"[1-9]\d*", lab):
            r["label_as_filed"] = f"part {lab}"
            r["notes"] = "; ".join(x for x in (r["notes"], "a 50-page part of the year's volume as the ÖNB delivered it, not an issue") if x)
        elif lab and meaning == "issue" and re.fullmatch(r"\d+(-\d+)*", lab):
            r["issue"] = "-".join(str(int(x)) for x in lab.split("-"))
        elif stem in LABEL_READ:               # a label that is not the issue, read from the masthead (2026-10-24)
            r["issue"], r["month"], why = LABEL_READ[stem]
            r["label_as_filed"] = lab
            r["notes"] = "; ".join(x for x in (r["notes"], why) if x)
        elif lab:
            r["label_as_filed"] = lab
        r["parsed_by"] = "B"; return r
    m = Y.search(stem)
    if m:
        r["year"] = m.group(1); r["parsed_by"] = "Y"
        rest = stem[m.end():].strip("._- ")
        if rest: r["label_as_filed"] = rest
        return r
    r["parsed_by"] = "-"; return r


BPEAPE_TSV = os.path.join(HERE, "..", "published", "heterophony-resources", "bpeape-proofreading", "sources", "derived",
                          "bpeape-entries.tsv")


def _fold(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for a_, b_ in (("cx", "c"), ("gx", "g"), ("hx", "h"), ("jx", "j"), ("sx", "s"), ("ux", "u")):
        s = s.replace(a_, b_)
    return re.sub(r"[^a-z]", "", s)


def candidates(rows, out, minimum=2, top=8):
    """For each title with >= `minimum` items: the `top` BPEAPE entries most like it, by title likeness, with a bonus
    when the entry's stated years cover the title's years. A worksheet for a checker, never a match."""
    import difflib, collections
    E = []
    for l in open(BPEAPE_TSV, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 4 and x[0].isdigit():
            ti = x[2]
            forms = {_fold(ti)}
            m_ = re.match(r"(.+?),\s*(The|L[’']|La|Le|Les|El|Il|Der|Die|Das|De|Het)\s*$", ti)
            if m_: forms.add(_fold(m_.group(2) + m_.group(1)))
            for v in re.findall(r"Titolvarianto:\s*([^.;]+)", x[3]): forms.add(_fold(v))
            E.append((int(x[0]), ti, x[3], forms))
    by = collections.defaultdict(list)
    for r in rows: by[r["title_key"]].append(r)
    L = ["# BPEAPE candidates per title (worksheet; GENERATED by tools/ocr-item-table.py --bpeape-candidates). For a checker:",
         "# pick the entry that is the title, or none. Ranked by title likeness (also the article-first form and any Titolvarianto), + 0.5 when the entry's years cover ours, - 0.3 when they miss them.", ""]
    for key, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < minimum: continue
        ys = sorted({int(y) for r in rs for y in re.findall(r"1[89]\d\d|20\d\d", r["year"])})
        fk = _fold(key)
        sc = []
        for n, ti, body, ft in E:
            s = max(difflib.SequenceMatcher(None, fk, f_).ratio() for f_ in ft)
            if s < 0.45: continue
            ey = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", body[:400])]
            if ys and ey and min(ey) <= ys[0] + 1 and (max(ey) >= ys[-1] - 1 or re.search(r"\d{4}\s*-\s*[.,;)]", body[:400])):
                s += 0.5
            elif ys and ey and (min(ey) > ys[-1] + 2 or max(ey) < ys[0] - 2):
                s -= 0.3
            sc.append((s, n, ti, body))
        sc.sort(reverse=True)
        L.append(f"## {key}  ({len(rs)} files; years {ys[0] if ys else '?'}–{ys[-1] if ys else '?'}; e.g. "
                 + " · ".join(r["item"] for r in rs[:3]) + ")")
        for s, n, ti, body in sc[:top]:
            L.append(f"- n-ro {n} · {s:.2f} · {ti} — {body[:240]}")
        if not sc: L.append("- (no entry with a title like this)")
        L.append("")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(f"candidates for {sum(1 for k, rs in by.items() if len(rs) >= minimum)} titles → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--bpeape-candidates", action="store_true", help="write the BPEAPE worksheet to --out instead")
    ap.add_argument("--keys-preview", type=int, metavar="N", help="print the keys the unkeyed items would get (N samples "
                    "and every item whose key differs from its name); write nothing")
    ap.add_argument("--assign-keys", action="store_true", help="ADD the unkeyed items' keys to OCR-ITEM-KEYS.tsv; write nothing else")
    ap.add_argument("--rename", nargs=2, metavar=("OLD", "NEW"), help="a file renamed: ADD a row giving NEW the key of "
                    "OLD (run BEFORE --assign-keys, so the new name is not keyed afresh); write nothing else")
    a = ap.parse_args()
    if a.rename:
        old, new = a.rename; have = read_keys()
        if old not in have: sys.exit(f"refusing: {old} has no key")
        if new in have: sys.exit(f"refusing: {new} already has a key ({have[new]})")
        with open(KEYS_TSV, "a", encoding="utf-8") as f: f.write(f"{new}\t{have[old]}\t{old}\n")
        print(f"{old} → {new}: key {have[old]} kept"); return
    sys.path.insert(0, HERE)
    import ocr_replace_guard as RG   # the fixed name geniza/OCR-ITEM-TABLE.tsv, replaced only when committed
    why = None if (a.keys_preview is not None or a.assign_keys) else RG.may_replace(a.out)
    if why: sys.exit(why)
    stems = [os.path.splitext(os.path.basename(l.strip()))[0] for l in open(a.pdfs, encoding="utf-8") if l.strip()]
    rows = [parse(s) for s in sorted(set(stems), key=lambda s: (_ps.natural(s), s))]   # the name breaks ties: a fixed order
    # BORN-DIGITAL ITEMS (2026-10-10): a row each,
    # from the born-digital lists (proposed and signed), so that ocr-item-dates.py dates them and the kind has one source
    import born_digital_lines as BDL
    have = {r["item"] for r in rows}
    for it, b in sorted(BDL.lists("proposed").items()):
        if it in have:
            sys.exit(f"born-digital item {it} clashes with a corpus PDF of the same name")
        r = {k: "" for k in COLS}
        r.update(item=it, title_key=it, parsed_by="BD", origin=f"born-digital: {b.get('path', '')} ({b['file']})",
                 notes=f"born-digital text ({b.get('label', '')}), searched as given: no OCR, no ledger")
        rows.append(r)
    prim, lang_table = primary_languages()
    ids = archive_ids()
    pm = from_page_map()
    # THE SIGNED KIND WINS (2026-10-24, the editor 20:4x, on the kind column contradicting signed lines: «that isn't going
    # to take long, surely»). The date rule above knows 1914 / 1931 only, not a batch's scope rulings (cupel15: the
    # Volapük press before 1887 SECONDARY; modern afterwords SECONDARY). Where an item's signed lines all carry one kind,
    # that kind is the column's; the date rule's, if different, is named in written_from. Lines of both kinds (scoped
    # stretches): the date rule's kind stays, and the note says so.
    _sd = importlib.util.spec_from_file_location("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
    _D = importlib.util.module_from_spec(_sd); _sd.loader.exec_module(_D)
    signed_kind = {}
    for it, (sf, _, xs) in _D.signed_lines().items():
        ks = {"PRIMARY" if "; PRIMARY" in " | ".join(x) else "SECONDARY" if "SECONDARY LITERATURE" in " | ".join(x) else ""
              for x in xs}
        signed_kind[it] = (ks, sf)
    dt = {}
    dfs = sorted(glob.glob(os.path.join(os.path.dirname(PAGE_MAP), "OCR-ITEM-DATES-*.tsv")))
    for l in (open(dfs[-1], encoding="utf-8") if dfs else []):
        x = l.rstrip("\n").split("\t")
        if l.startswith("#") or x[0] == "item" or len(x) < 4: continue
        dt[x[0]] = x
    for r in rows:
        if r["item"] in dt and r["parsed_by"] != "R":   # an issue read by hand (ISSUES_READ) keeps its own year
            x = dt[r["item"]]
            r["written"], r["kind"] = x[1], x[3]
            r["written_from"] = x[2] + (f" ({x[4]})" if len(x) > 4 and x[4] else "")
        elif r["year"]:
            r["written"], r["written_from"] = r["year"], "the item's year"
            y0 = re.match(r"\d{4}", r["year"])   # a volume may span two years («1906–1907»): its first year
            cut = 1931 if prim.get(r["item"]) in ("ido", "occidental", "novial", "latino-sine-flexione") else 1915   # the Ido/Occidental/Novial cutoff, and Peano's Interlingua (approved by the editor, 2026-10-11 03:1x); Esperanto 1914 inclusive (2026-10-10 18:1x)
            r["kind"] = ("PRIMARY" if int(y0.group(0)) < cut else "SECONDARY") if y0 else ""
            if y0 and cut == 1931 and 1915 <= int(y0.group(0)) < 1931: r["written_from"] += " (Ido/Occidental/Novial cutoff 1931)"
        if r["item"] in signed_kind:
            ks, sf = signed_kind[r["item"]]
            if len(ks) == 1 and "" not in ks:
                k = next(iter(ks))
                if k != r["kind"]:
                    r["written_from"] = (r["written_from"] + "; " if r["written_from"] else "") + \
                        f"kind as signed ({sf})" + (f", the date rule gives {r['kind']}" if r["kind"] else "")
                    r["kind"] = k
            elif ks >= {"PRIMARY", "SECONDARY"}:
                r["written_from"] = (r["written_from"] + "; " if r["written_from"] else "") + \
                    f"signed in both kinds by scope ({sf})"
        if r["item"] in pm:
            r["first_text_page"], r["pagination"] = pm[r["item"]]
        if r["parsed_by"] == "BD":
            pass   # its origin is the list's
        elif r["item"] in ids:
            r["origin"] = ids[r["item"]]
        elif r["parsed_by"] == "N":
            r["origin"] = "ÖNB / ANNO, title code " + r["notes"].replace("ANNO title code ", "")
        elif r["item"] in COPIES:
            r["origin"] = COPIES[r["item"]][1]
        else:
            for pat, o in ORIGIN_STATED:
                if re.search(pat, r["item"]): r["origin"] = o; break
        if not r["title"] and r.get("title_key") in TITLE_BY_KEY:   # overridden below where a BPEAPE row matches
            r["title"] = TITLE_BY_KEY[r["title_key"]]
        if not r["title"]:   # runs filed volume by volume, whose title_key differs per volume: by the item's name
            for pat, t in TITLE_BY_ITEM:
                if re.search(pat, r["item"], re.I): r["title"] = t; break
        for pat, n, title, why in BPEAPE:
            if re.search(pat, r["item"], re.I):
                r["title"] = title
                if n is not None: r["bpeape"] = str(n)
                else:
                    r["bpeape"] = "not a periodical" if "not a periodical" in why else "not found"
                    r["notes"] = "; ".join(x for x in (r["notes"], "BPEAPE: " + why) if x)
                break
        if r["bpeape"]: continue
        for pat, why in OUTSIDE:
            if re.search(pat, r["item"], re.I):
                r["bpeape"] = "none: " + why.split(" (")[0]
                r["notes"] = "; ".join(x for x in (r["notes"], "outside BPEAPE: " + why) if x); break
        if not r["bpeape"] and prim.get(r["item"]) in LANG_OUTSIDE:
            lg = LANG_OUTSIDE[prim[r["item"]]]
            r["bpeape"] = f"none: {lg}"
            r["notes"] = "; ".join(x for x in (r["notes"], f"outside BPEAPE: {lg} by the language table ({lang_table})") if x)
    have = read_keys()
    SRC = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources")
    folders = {}
    for l in open(a.pdfs, encoding="utf-8"):
        if l.strip():
            st = os.path.splitext(os.path.basename(l.strip()))[0]
            folders.setdefault(st, os.path.relpath(os.path.dirname(os.path.realpath(l.strip())), os.path.realpath(SRC)))
    fresh = new_keys([r["item"] for r in rows], have, folders)
    if a.keys_preview is not None:
        import random
        rnd = random.Random(0); fr = sorted(fresh.items())
        print(f"{len(have)} items keyed; {len(fresh)} would be keyed now")
        for it, k in rnd.sample(fr, min(a.keys_preview, len(fr))):
            print(f"  {it}  →  {k}")
        odd = [(it, k) for it, k in fr if k != it]
        print(f"{len(odd)} whose key differs from the name (spaces, capitals, other characters, length, pinned):")
        for it, k in odd: print(f"  {it}  →  {k}")
        return
    if a.assign_keys:
        new = not os.path.exists(KEYS_TSV)
        with open(KEYS_TSV, "a", encoding="utf-8") as f:
            if new:
                f.write("# OCR-ITEM-KEYS.tsv: every item's key (tools/ocr-item-table.py --assign-keys). ONLY EVER ADDED TO: a key "
                        "once written is never changed, so that locators keep working; a renamed file keeps its key by a row naming its "
                        "old name in renamed_from (--rename). Never hand-edit.\nitem\tkey\trenamed_from\n")
            for it, k in sorted(fresh.items()): f.write(f"{it}\t{k}\n")
        print(f"added {len(fresh)} keys → {KEYS_TSV} ({len(have) + len(fresh)} in all)"); return
    if fresh:
        sys.exit(f"refusing: {len(fresh)} items have no key (e.g. {sorted(fresh)[:3]}); run --assign-keys first")
    if len(set(have.values())) != len(have):
        sys.exit("refusing: OCR-ITEM-KEYS.tsv gives one key to two items")
    for r in rows:
        r["key"] = have[r["item"]]; r["citation"] = CITATIONS.get(r["item"], "")
    miss = sorted(set(CITATIONS) - {r["item"] for r in rows})
    if miss: sys.exit(f"refusing: CITATIONS names items not in the table: {miss}")
    if a.bpeape_candidates:
        candidates(rows, a.out); return
    final, a.out = a.out, a.out + ".new"
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-item-table.py from {os.path.basename(a.pdfs)}. Do not hand-edit — re-run it. "
                "Empty columns are not yet filled, never guessed; «label_as_filed» = a part of the name whose meaning "
                "is not yet checked.\n")
        f.write("\t".join(COLS) + "\n")
        for r in rows: f.write("\t".join(r[k] for k in COLS) + "\n")
    print("\n".join(RG.report(final, a.out, ("item",), [k for k in COLS if k != "item"])))
    os.replace(a.out, final); a.out = final
    from collections import Counter
    c = Counter(r["parsed_by"] for r in rows)
    print(f"{len(rows)} items → {a.out}; parsed by: {dict(sorted(c.items()))}; "
          f"with an issue: {sum(1 for r in rows if r['issue'])}; with a month: {sum(1 for r in rows if r['month'])}; "
          f"label as filed: {sum(1 for r in rows if r['label_as_filed'])}; titles: {len(set(r['title_key'] for r in rows))}; "
          f"with a BPEAPE number: {sum(1 for r in rows if r['bpeape'][:1].isdigit())}; "
          f"outside BPEAPE: {sum(1 for r in rows if r['bpeape'].startswith('none:'))}; "
          f"pagination volume/issue: {sum(1 for r in rows if r['pagination']=='volume')}/{sum(1 for r in rows if r['pagination']=='issue')}; "
          f"with an origin: {sum(1 for r in rows if r['origin'])} (archive.org {sum(1 for r in rows if 'archive.org/details' in r['origin'])}, tempa.bitarkivo.org {sum(1 for r in rows if 'tempa.bitarkivo' in r['origin'])})")


if __name__ == "__main__":
    main()
