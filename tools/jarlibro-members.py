#!/usr/bin/env python3
"""The members' lists of the *Tutmonda Jarlibro Esperantista* 1904–1910, part B (runbook D4c; 2026-10-29, the editor,
after Miles's re-cut at the gutters, `tools/ocr-gutter-cut.py`, so each column reads top to bottom): the entries read by
tool, country by country and town by town, «Dubois H., lernanto en la supra lernejo de komerco, 73, av. de la République.»

    tools/jarlibro-members.py inspect [--years 1906,1907]
    tools/jarlibro-members.py extract --hits HITS.tsv --tag TAG [--years 1904,1905] [--show PDF] [--write]

inspect: each volume's pages outside the societies' part (tools/directory-extract.py PARTS), with the number of lines that
open an entry, the runs of member pages, and the headings found on them (countries in capitals, towns). Writes nothing.

extract (parser b, 2026-10-30; the editor, the order of 19:3x): the members by town of 1904–1907
(RUNS, the main runs inspect finds), country by country («BULGARUJO») and town by town («Dellys (Alger).», «Guyotville.»),
one entry a paragraph, the surname first: «Ganĉef Petko, metalfandisto.», «Ganĉeva (Fi» R.), ul. Cerkoviŝtna, 1408.». A
town heading: a line of its own, «Town (Region).» or one word; of two to five words only where the gazetteer finds it in
the printed country (an entry with no comma, «Kovacef Georgi.», is no town); a bracket with a title and forename
(«Meyer (F0 Clémence).») is a person. An entry becomes lines only as in directory-extract.py: a strong hit (HITS, the name
search over these pages) on the printed surname, borne out by the profile (the heading's town, the initials or the
forename); else held, into the review. Lines: {aperoj: Tutmonda Jarlibro Esperantista YEAR}; {loĝado: ‹town›}, the address
where printed; {profesio: …} for an occupation in Esperanto. Dated by the yearbook's year. Writes, with --write, refusing to
overwrite: dowse/tutmonda-jarlibro-esperantista/facts-return-TAG-members.md, members-TAG.tsv, MEMBERS-REVIEW-TAG.md. Ezri."""
import argparse, collections, csv, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("dx", os.path.join(ROOT, "tools", "directory-extract.py"))
DX = importlib.util.module_from_spec(spec); spec.loader.exec_module(DX)
spec = importlib.util.spec_from_file_location("oj", os.path.join(ROOT, "tools", "oficiala-jarlibro-extract.py"))
OJ = importlib.util.module_from_spec(spec); spec.loader.exec_module(OJ)
GZ = OJ.GZ
csv.field_size_limit(sys.maxsize)

# THE MEMBERS' RUNS (2026-10-30, `inspect`: the runs of 8 entries a page or more, the main one of each volume; the short
# runs before them, «ADRESARO DE LA ESPERANTISTOJ» with full forenames, are another list, not read here)
RUNS = {1904: (57, 235), 1905: (69, 289), 1906: (95, 379), 1907: (69, 107)}
RUNHEAD = re.compile(r"TUTMONDA|JARLIBRO|ADRESARO|ESPERANTIST")
# a town heading: the town, a region in brackets, a period, the margin's junk; no comma outside the bracket, no figure
TOWNH = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-Ž][\wÀ-ž'’.-]*(?:[ -][\wÀ-ž'’.-]+){0,4}?)\s*(?:\((?P<reg>[^()]{1,40})\))?\s*\.?[\s;:|\]\[.'’]{0,4}$")
# a bracket naming a person, not a region: a title or initials first («(Fi» R.)», «(F0 Clémence)», «(Fin Alice)», «(D' X)»)
PERSONB = re.compile(r"^\W{0,2}(?:F\W{0,3}[a-z0-9]{0,3}\W{0,3}(?:\s|$)|Fi|Fino|Fin|Sino|S-ro|S-ino|D['’r]|Dro|Mme|Mlle|Mrs|Miss|Mr|[A-ZÀ-Ž]\.\s"
                     # … or a clergyman's title in Esperanto or French («Requin (abato).»: the re-check of 2026-11-01c, line 21)
                     r"|(?i:abato|pastro|patro|frato|kanoniko|vikario|abbé|curé|chanoine|père|frère)\b"
                     # … or a misread F-ino / S-ino before a forename («Lebrun (Ki Jeanne)», «(Sie Olga)», «(So Ramona)»: 1904
                     # PDF 100, Langres's members after it filed under «Lebrun»), or a noble title («(Cte Jean)»); not any
                     # short word («(gub Lomzynska)», «(bij Brugge)» are regions)
                     # («(King County)» a region: two letters at most after the F, S or K, the OCR's marks apart)
                     r"|[FSK][a-z]{0,2}[0-9!\"'’»°*]{0,3}\s+[A-ZÀ-Ž][a-zà-ž]{2,}\W{0,2}$|(?:Cte|Ctesse|Vte|Vtesse|Mis|Bon|Bonne)\.?\s+[A-ZÀ-Ž])")
# … or an initial in it («Bedouet (S!»e Ch.).», 1905 PDF 72); a region is a name («(Alger.)», «(Constantine)»)
PERSONI = re.compile(r"(?:^|\s)[A-ZÀ-Ž][a-zà-ž]{0,2}\.(?:\s|$)")
# Sinjorino in the bracket, as the OCR reads it («(S° René)», «(Si"o)», «(Siw)», «(S!no)», «(Sino)», «(S-ino)», «(Mme)»)
WIFE = re.compile(r"\(\s*(?:S(?:-?ino\b|i[a-z]?(?=[\W\d])|[!°»\"”'’])|Mme\b|Mrs\b|Madame\b|Señora\b|Sra\b)")
# … but a province's initials are a region («Saint-Hugues (P. Q.).», «Saint-Hyacinthe (P.Q. "e», 1905 PDF 213: both
# taken for a person's, so Beauparlant stayed in Québec; the accuracy check of 2026-11-01)
# (the Q read as a zero, «Saint-Hyacinthe (P. 0.).»: the re-check of 2026-11-01c, line 36, Beauparlant under Saint-Hugues)
# (… and the Distrito Federal's, «Mexico (D. F.).», 1906 PDF 293)
REGABBR = re.compile(r"\s*(?:P\.?\s?[Q0]|N\.?\s?[BSÉ]|N\.?-[BÉ]|B\.?\s?C|S\.?-et-[OM]|S\.?\s?et\s?[OM]|D\.\s?F)\.?\s*")
# (the margin's junk after it only, a letter or two in small at most: «Veitzler (NS! A.», 1905 PDF 226, is a person's)
# (… or a Mexican state's, «Paso del Maĉo (Ver. Gub...», 1906 PDF 293)
UNCLOSED = re.compile(r"^(?P<head>[^()]+\()(?P<reg>(?:P\.?\s?[Q0]|N\.?\s?[BSÉ]|N\.?-[BÉ]|B\.?\s?C|S\.?-et-[OM]|[A-ZÀ-Ž][\wÀ-ž]*\.?\s[GC]ub)\.?)[^()A-Za-z]{0,4}[a-z]{0,2}[^()A-Za-z]{0,2}$")
# an entry ending on a street's abbreviation has its street on the next line
STREETEND = re.compile(r"(?:^|[\s,])(?:r|av|bd|boul|str|pl|ul|ch|rte|route|rue|via|calle|dom)\.?$", re.I)
# … unless the street's name stands before it, English-wise («Woodzell W. H., komercisto, 36, Beatrice av.», 1904 PDF 149:
# the next entry, «Woolland (Fi C.), Mount Drake», taken into his address; the accuracy check of 2026-11-01)
def street_open(s):
    m = STREETEND.search(s)
    return bool(m) and not re.search(r"[A-ZÀ-Ž][a-zà-ž]{2,}", s[:m.start()].rsplit(",", 1)[-1])
# … or on a street's preposition («Berger, …, 110, r. de» / «Preize.», 1905 PDF 175: the street taken for a town)
PREPEND = re.compile(r"(?:^|\s)(?:de|du|des|de la|de l['’]|d['’]|à|au|aux)$")
# the margin's junk after an entry's closing mark, of either case («… r. de la Pierre. XU», «… Sophie). LED», 1905 PDF 175)
MARGIN = re.compile(r"(?<=[.,)!?:])(?:\s+[^\s.,]{1,3}){1,3}$")
# … and after a heading's period, figures among it («Troyes. ; 1 |», «Troussencourt (Oise). 14»)
HEADJUNK = re.compile(r"\.[\s;:|\]\[.'’\d]{1,6}$")
# a street the entries name («24, r. Gustave-Courbet»): a heading of that name in the same town, where the gazetteer finds
# no town of it, is the address run on («Kalb, …» / «Gustave-Courbet.», 1905 PDF 158; «Chanzy. s kig», 1906 PDF 157)
STREETNAME = re.compile(r"(?:^|[\s,])(?:r|rue|bd|boul|av|pl|quai|cours|allée|chemin|impasse|place|route|str|ul|road|street)\.?\s+"
                        r"(?:de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+|d['’])?([A-ZÀ-Ž][\wÀ-ž'’-]+(?:[ -][A-ZÀ-Ž][\wÀ-ž'’-]+){0,2})")
# … and a heading ending on a street's word is no town («Mistersamuelsgatan», run p's sample)
STREETWORD = re.compile(r"(?:gatan|gata|gade|gasse|straße|strasse|str|vej|vägen|ulica|road|street|lane|rue)\.?$", re.I)
COUNTRYW = re.compile(r"(?:UJO|IO|ANDO|ONO|IKO|ALO|ILO|AĴO|LANDO|RESPUBLIKO|INSULOJ|AMERIKO|AFRIKO|AZIO|EŬROPO|OCEANIO|USONO|KANADO)\b")
DEST = os.path.join(DX.G, "dowse", "tutmonda-jarlibro-esperantista")
_TOWN = {}
RAW = {}   # (year, line) → a town heading's line as read, for --towns

# THE COUNTRY HEADINGS (2026-10-30, `--countries`: of 334 headings in capitals, a third misread, cut short or the page's
# running head): a heading is a country by the gazetteer's own mending (`pcountry`: as printed, or one letter off), else
# by a known country's key it begins or ends («Ancujo» Francujo, «MAROKUJ» Maroko, «JAPA» Japanujo), the country in
# force first; a heading that names none is the margin's or the running head's, and the country in force stands
KNOWN = sorted(set(GZ.CKEYS) | set(GZ.EMPIRE))
NAMED = {"austr": "Aŭstrio", "rus": "Rusio", "german": "Germanio", "hungar": "Hungario", "turk": "Turkio", "brit": "Britio",
         "pol": "Pollando", "austrohungar": "Aŭstrio-Hungario"}
# the period's names the keys do not meet, and the headings read only by the towns under them (each checked by the first
# towns `--countries` prints after it)
PERIOD = {"granda britanujo": "Britio", "granda britujo": "Britio", "britanujo": "Britio", "hinujo": "Ĉinio", "hindo hinujo": "Vjetnamio",
          "hindo hinuio": "Vjetnamio", "luxembourg": "Luksemburgio", "nova zelando": "Nov-Zelando", "nova kaledonio": "Francio",
          "transvaalo": "Sud-Afriko", "kanariaj insuloj": "Hispanio", "anariaj insuloj": "Hispanio", "islas canarias": "Hispanio", "porto ricco": "Porto-Riko",
          "philippines": "Filipinoj", "filipinaj insuloj": "Filipinoj", "holandujo": "Nederlando", "holanda": "Nederlando",
          "svisujo": "Svislando", "persujo": "Irano", "bohemujo": "Ĉeĥio", "belga kongo": "",
          # cut short («MAROKUJ(», 1905 PDF 215; «MAROKUJ», 1904 PDF 164: Ceuta's members kept Malta)
          "marokuj": "Maroko"}
# (year, line) → the country: misread past mending, named by the towns that follow
BYLINE = {(1904, 7220): "Aŭstralio", (1904, 8448): "Brazilo", (1904, 23687): "Hispanio", (1904, 24355): "Hungario",
          (1904, 26102): "Filipinoj", (1905, 9736): "Aŭstralio", (1905, 13166): "Bulgario", (1905, 14985): "Francio",
          (1905, 33056): "Hispanio", (1905, 48161): "Svislando", (1905, 48484): "Sud-Afriko", (1906, 17426): "Filipinoj",
          (1906, 26056): "Francio", (1906, 43046): "Hindio", (1906, 47041): "Japanio", (1906, 62677): "",
          (1907, 17239): "Hispanio", (1907, 17459): "Nederlando", (1907, 17603): "Rumanio", (1907, 18160): "Turkio",
          (1907, 18245): "Nov-Zelando", (1905, 30062): "Germanio", (1905, 36968): "Rusio", (1907, 16942): "Germanio",
          (1904, 26941): False, (1907, 17072): False,
          # cut to three letters, below the rule's floor
          (1904, 11439): "Danio", (1904, 36990): "Svislando", (1906, 61555): "Svedio", (1907, 13814): "Danio", (1907, 17571): "Rumanio",
          # mended to the wrong country by the rule («TRAN» Irano, the towns Johannesburg, Pretoria; «CIAN» Ĉinio, the towns
          # Saigon, Mytho; «BELGA» of Belga Kongo); False: no heading at all, the country in force stands
          (1905, 48470): "Sud-Afriko", (1906, 42969): "Vjetnamio", (1905, 32952): "Vjetnamio", (1904, 8378): "",
          (1904, 33109): False, (1907, 14429): False, (1904, 31202): False, (1905, 16074): False,
          # the margin's small letters after it, or past reading («I MEKSIKUJO pe |», «MEKSIKUJO i |», «a MARNKIIN
          # /MAaRAC,;: i»): Mexico's members kept Morocco or Malta (the fourth re-check of 2026-11-01); read though not
          # in capitals
          (1905, 36082): "Meksiko", (1906, 48137): "Maroko", (1906, 48148): "Meksiko",
          # «AŬSTRIO j»: Austria's 723 members kept Australia; «AŬST» over Jamaica and San Salvador, the columns run
          # together, no country; 1906's run opens in Austria-Hungary's one list under the running head only
          # («AUSTRIO-HUNGARUJO 51 1», PDF 95: 490 entries without a country), named as its PDF 101 on
          (1905, 9759): "Aŭstrio", (1905, 9724): "", (1906, 10922): "Aŭstrio",
          # THE COUNTRY SURVEY OF 2026-11-01 (the editor): the bold headings past reading, found
          # where a run's towns are another country's by eo.wikipedia («BELUUJU», «HOLANNITNO», «DULLUUJU», «LI DANUJO I»,
          # «FINLANUUJU H», «GFKMANUJU», «HISPANUTIO», «EGE PERDO», «FUNIU», «QWIGITTN», «j TINTIZIN», «UNU1ULLAJ DIALUJ
          # AMEHKIHKAJ», «KIMNMNANUUJU», «| SVENTIN», «| NOVA Z»), each checked by the towns after it
          (1904, 8555): "Belgio", (1904, 11525): "Finnlando", (1904, 24071): "Nederlando", (1904, 24810): "Kanado",
          (1904, 37359): "Usono", (1905, 14766): "Finnlando", (1905, 34513): "Hungario", (1905, 34726): "Italio",
          (1905, 36799): "Porto-Riko", (1905, 36819): "Portugalio", (1905, 46893): "Svedio", (1906, 13411): "Belgio",
          (1906, 15515): "Bulgario", (1906, 17143): "Danio", (1906, 17435): "Finnlando", (1906, 37426): "Germanio",
          (1906, 43350): "Hispanio", (1906, 48671): "Peruo", (1906, 48899): "Portugalio", (1906, 61976): "Svislando",
          (1906, 62738): "Tunizio", (1906, 62852): "Usono", (1907, 12180): "Argentino", (1907, 12569): "Meksiko",
          (1907, 12582): "Usono", (1907, 13508): "Belgio", (1907, 13861): "Francio", (1907, 17828): "Svedio",
          (1907, 18221): "Nov-Zelando",
          # … and the running heads over the last towns of the country before («LUXEMBOURG — BULGARUJO 55» over Belgium's
          # Virton and Ypres, «HUNGARUJO 135» over Holland's Rotterdam, «HOLANDUJO 99» over Spain's Elche), the stray
          # «p HOLA» over Spain's Valgañon: no heading
          (1904, 10044): False, (1904, 24238): False, (1907, 17321): False, (1905, 34260): False, (1906, 15515): False}
# (year, line) → the country from that line on, the line itself read as ever: where the columns ran together and the
# country begins at a town, its heading elsewhere (1906 PDF 121: «… BULGARUJO» among Brazil's last towns, Bulgaria from
# Boĵuriŝte; PDF 282: Holland's last towns after the Canaries, from Rhenen)
COUNTRY_AT = {(1906, 15580): "Bulgario", (1906, 46420): "Nederlando"}
CONTINENT = re.compile(r"^(?:afriko|ameriko|azio|azia|eŭropo|europo|oceanio|sud ameriko|suda ameriko|okcidenta afriko)$")
# THE RUNNING HEAD, the page's countries and its number («BULGARUJO 81», «MALTA — MAROKUJO — MEKSIKUJO 189», «GEKMANUJO ;
# 191 l»), in the plain type the OCR reads where it garbles the bold headings («DULLUUJU», «FINLANUUJU H»)
RUNNING = re.compile(r"^\W{0,4}(?:\d{2,3}\s+)?(?P<names>[A-ZÀ-ŽĈĜĤĴŜŬ][A-ZÀ-ŽĈĜĤĴŜŬ() —–-]{3,60}?)[\s;:,.|]*\d{2,3}\b.{0,12}$")
# the empire's head names its lands' countries too
WITHIN = {"Aŭstrio-Hungario": {"Aŭstrio", "Hungario"}}

def running_countries(t):
    """The countries a running head names, in order; a name mended only where its first two letters are the country's
    («MANUJO», GERMANUJO cut, is not Danio), or a period name («GRANDA BRITUJO»)."""
    m = RUNNING.match(t)
    if not m: return []
    out = []
    for x in re.split(r"\s+[—–-]\s+", m.group("names")):
        # (the margin's letters before it left off: «F SVEDUJO 347», 1906 PDF 361)
        h = re.sub(r"^(?:[A-ZÀ-ŽĈĜĤĴŜŬ]{1,2}\s+)+(?=[A-ZÀ-ŽĈĜĤĴŜŬ]{4})", "", re.sub(r"[^A-ZÀ-ŽĈĜĤĴŜŬ -]", "", x).strip())
        c = country_of(h, "") if len(h.replace(" ", "")) >= 4 else None
        if c and (GZ.fold(h) in PERIOD or GZ.fold(h)[:2] == GZ.fold(c)[:2]): out.append(c)
    return out

def country_of(h, current):
    """The country a heading names, or None (not a country's heading: the one in force stands)."""
    words = GZ.fold(h).split()
    for n in (3, 2, 1):
        w = " ".join(words[:n])
        if len(words) < n or not w: continue
        if w in PERIOD: return PERIOD[w]
        if CONTINENT.match(w): return ""
        # a key of three letters is mended to too many («HIS» Islando, «KAJ» Tajlando, «HILO» Ĉilio in France), unless the
        # word printed is whole («RUSUJO», «DANUJO»: their keys «rus», «dan»; run s missed them all)
        if len(GZ.ckey(w).replace(" ", "")) < 4 and len(w.replace(" ", "")) < 5: continue
        c = GZ.pcountry(w)
        if c: return GZ.CKEYS.get(GZ.ckey(c)) or NAMED.get(GZ.ckey(c), c)
    k = GZ.ckey(words[0]) if words else ""
    if len(k) < 4: return None
    cur = GZ.ckey(current)
    hit = [x for x in KNOWN if len(x) >= 3 and (x.startswith(k) or x.endswith(k))]
    if cur in hit: return current
    if len(hit) == 1: return GZ.CKEYS.get(hit[0]) or NAMED.get(hit[0], "")
    return None

def is_town(t, reg, country):
    """Whether a heading-shaped line names a town (see the docstring); cached."""
    # (a bracket ending on a particle is a person's: «Migno (Eugene de).», 1907 PDF 213, taken for a town)
    # (… but one ending on «Gub.», the OCR's «Cub.», is a Mexican state's, though «Gub.» and «Ver.» look like initials:
    # «Puebla (Puebla Gub.).», «Orizaba (Ver. Gub.).», 1906 PDF 293, all refused, their members kept Jalapa; the fourth
    # re-check of 2026-11-01)
    if reg is not None and re.search(r"(?:^|[\s.])[GC]ub\.?\s*$", reg): return True
    if reg is not None: return bool(REGABBR.fullmatch(reg)) or (not PERSONB.match(reg) and not PERSONI.search(reg)
                                                                and not re.search(r"(?:^|\s)(?:de|d['’]|du|von|van|la|le)\s*$", reg))
    # three letters only where the gazetteer knows the town (Ham, Ath, Hjo; run r's sample: «Jul.» taken for one)
    if len(t.split()) == 1: return len(re.sub(r"\W", "", t)) >= 4 or (len(re.sub(r"\W", "", t)) == 3 and gz_known(t, country))
    return gz_known(t, country)

def gz_known(t, country):
    """Whether the gazetteer finds a place of that form in that country; cached."""
    k = (t, country)
    if k not in _TOWN: _TOWN[k] = bool(GZ.resolve(t, country)[0])
    return _TOWN[k]

def entries(item, a, b):
    """[{pdf, line, country, town, region, text}] of the members' run, wrapped lines joined; and the headings read."""
    pages = DX.page_lines(item)
    y = int(re.search(r"_(\d{4})0005$", item).group(1))
    out, heads, country, town, region, cur, gap, town_at, doubt, pend = [], [], "", "", "", None, True, 0, False, None
    for p in range(a, b + 1):
        for ix, (n, l) in enumerate(join_regions(pages.get(p, []))):
            s = l.strip()
            if not s: gap = True; continue
            t = DX.lead(s)
            was_gap, gap = gap, False
            # a running head at the page's top naming countries, none of them the one in force, puts its first in force:
            # the bold heading was past reading, its members kept the country before (1906 «BULGARUJO 81» over Bulgaria's
            # members filed under Brazil, «SERBUJO — SIRIO 315» over Sweden's under Serbia; the country survey of 2026-11-01)
            # (not at once: a head names the countries that begin on its page, so the page may open with the last towns
            # of the country before, «HUNGARUJO 135» over Rotterdam; the head's country waits for the first town on the
            # page the gazetteer holds in it and not in the country in force; the town in force is kept either way.
            # Measured against the extraction before, 2026-11-01: 640 entries put right, 3 wrong; a town unknown to
            # both, «Valgañon», no longer switches)
            if pend and pend[1] != p: pend = None
            if (y, n) in COUNTRY_AT: country, pend = COUNTRY_AT[(y, n)], None
            if ix <= 4 and (y, n) not in BYLINE:
                rc = running_countries(t)
                if rc:
                    if country not in rc and not any(country in WITHIN.get(x, ()) for x in rc):
                        pend = (rc[0], p)
                        heads.append((p, n, "country", f"{rc[0]} ← «{t}» (the running head)"))
                    continue
            if RUNHEAD.search(t) or OJ.junk(t): continue
            c = re.sub(r"[^A-ZÀ-ŽĈĜĤĴŜŬ -]", "", t).strip()
            # a country's heading has a country's word (run n: the margin's «Cr Rts As Ets» taken for one), or is a line in
            # capitals that names a country (see country_of); the margin's junk and the page's number after it left off
            # («\ BRITUJO. 241 À», the running head, 1906 PDF 255)
            tc = HEADJUNK.sub(".", MARGIN.sub("", t))
            if (y, n) in BYLINE or tc.upper() == tc and len(c.replace(" ", "")) >= 3 and not re.search(r"\d", tc):
                cw = COUNTRYW.search(c) and len(c.replace(" ", "")) >= 4
                new = BYLINE[(y, n)] if (y, n) in BYLINE else country_of(c, country)
                # a line in capitals naming no country is the margin's or the running head's, never a town (the sample of
                # run p: «VIN», «BRITUJO» taken for towns)
                # … but one with a country's word ends the town in force, the country named or not («(ANARIAJ INSULOJ)»,
                # 1906 PDF 282: Rodriguez of the Canaries kept Zwijndrecht's town; the accuracy check of 2026-11-01)
                # (a strong word only: «IO» and the like in the margin's junk ended Lyon's town on 1904 PDF 113)
                if new is None and re.search(r"(?:UJO|LANDO|INSULOJ)\b", c): town, region, town_at, doubt = "", "", len(out), False
                if new is False or new is None: cur = None; continue
                if new is not None:
                    cur = None
                    # (a heading in brackets ends the town though it names the country in force: «(ANARIAJ INSULOJ)»
                    # under «ISLAS CANARIAS», which the re-cut column order put above the Dutch towns, 1906 PDF 282)
                    if new == country and tc.lstrip(" \\|").startswith("("): town, region, town_at, doubt = "", "", len(out), False
                    if new == country: continue
                    country, town, region, town_at, doubt, pend = new, "", "", len(out), False, None; heads.append((p, n, "country", f"{new or '(kontinento)'} ← «{c}»")); continue
            # A LINE AFTER AN ENTRY NOT ENDED is its address run on, never a heading (the first look, 1905 PDF 72: «Hinglais,
            # …, 28, route» / «de Sétif.», «Kopf, …, 6, r.» / «Caraman.» taken for towns): the entry's text without its
            # closing mark at all, or ending on a hyphen or a street's abbreviation; a final comma is often the OCR's period
            # («Sie, kapitano-kasisto 3° zouaves,» / «Serriĉre Komiso, …»), so a comma leaves it to the next line's shape
            # the margin's junk after the period left off first («…, r. des Carmes. i |», 1905 PDF 173, the sample of run
            # m: Legrand's entry took in Lamaignère's and Lavigne's)
            raw = cur["text"].rstrip(" ;|]'’\"”") if cur is not None else ""
            unmargined = MARGIN.sub("", raw)
            tail = re.sub(r"(?:\s+[^\w\s]*[a-z0-9]{0,2}[^\w\s]*)+$", "", unmargined) if cur is not None else ""
            # the street's abbreviation read on the line as it stands, before the junk is left off (run n: «r.» left off
            # as junk, so «Larrey.», the end of an address, became a town; «…, 39, r. AJ» / «Sĉpastopol.», 1905 PDF 175)
            # (a street's abbreviation after its name ends the entry, though the junk-trimming takes it off the tail:
            # «…, 36, Beatrice av.», Woodzell)
            shut = cur is not None and bool(STREETEND.search(raw)) and not street_open(raw)
            open_ = cur is not None and not shut and (not re.search(r"[.,)!?:]$", tail) or tail.endswith("-") or street_open(raw)
                                         or street_open(unmargined) or street_open(tail) or bool(PREPEND.search(raw)))
            # a heading with the margin's letters after it too («Trélon (Nord). ki», «Trignac (Loire-Inférieure). Vi»)
            th = HEADJUNK.sub(".", MARGIN.sub("", t))
            uc = UNCLOSED.match(th)
            if uc: th = f"{uc.group('head')}{uc.group('reg')})."
            # A HEADING «Town (Region).» AFTER AN ENTRY NOT ENDED, the town the gazetteer's in the country in force, ends it
            # («Brodeur (F0 Georgina), C/o Bagot» / «Saint-Hyacinthe (P.Q. "e», 1905 PDF 213: the heading taken into her
            # address, so Beauparlant stayed at Saint-Hugues); never after a hyphen, a street's word or preposition
            if open_ and not tail.endswith("-") and not street_open(raw) and not PREPEND.search(raw):
                mo = TOWNH.match(th)
                if mo and mo.group("reg") is not None and is_town(mo.group("town").strip(" ."), mo.group("reg"), country) \
                        and (gz_known(mo.group("town").strip(" ."), country) or REGABBR.fullmatch(mo.group("reg"))):
                    open_ = False
            m = TOWNH.match(th) if not open_ else None
            cand = m.group("town").strip(" .") if m else ""
            if m and m.group("reg") is None and (STREETWORD.search(cand) or (
                    GZ.fold(cand) in {GZ.fold(s) for e in out[town_at:] for s in STREETNAME.findall(e["text"])}
                    and not gz_known(cand, country))):
                if cur is not None: cur["text"] += " " + t
                continue
            # A HEADING WITHOUT A BRACKET STRAIGHT AFTER AN ENTRY, no blank line between, is that entry's address run on:
            # headings stand after a blank line («| Pantin (Seine).», «| Paris.»), and «…, 54, r. La-Fontaine, gr» /
            # «Auteuil. x», «…, 19, r. des Fossĉ:» / «St-Jacques.» took Paris's members to «Auteuil» and «St-Jacques» (the
            # second re-check of 2026-11-01, 14 «ne» of 25 for the towns; the editor)
            # (only after an entry left on a comma, a colon or a hyphen, the word alone: entries printed without blank lines
            # between, «Saltikov S. K.» / «Tupikin E. K.», are the next entry's)
            # (… or on a street's word or a preposition with its name to come: «10-12, pl.» / «St-Martin.», «104, bd de» /
            # «Courcelles.», «clos» / «St-Martin.»: the third re-check of 2026-11-01, Paris under «Courcelles-le-Roi»)
            # (… and on a saint's word, a blank line between or not: «…, 1° San 4» / ⟨blank⟩ / «Miguel. “I», 1905 PDF 216,
            # Puebla's members put under «Miguel»; the fourth re-check of 2026-11-01)
            if (m and m.group("reg") is None and cur is not None and len(cand.split()) == 1
                    and (not was_gap and (re.search(r"[,:\-]\s*$", re.sub(r"(?:\s+[^\w\s]*[a-z]{0,2}[^\w\s]*)+$", "", MARGIN.sub("", cur["text"].rstrip(" ;|]'’\"”"))))
                         or re.search(r"\b(?:pl|bd|r|av|rue|clos|faub|quai|chemin|cours|place|de|du|des|la|le|aux?)\.?\s*(?:[A-Z]\.|\W{0,3}[a-z]{0,2}\.?)?\s*$",
                                      MARGIN.sub("", cur["text"].rstrip(" ;|]'’\"”"))))
                         # (the word whole, never «St»: «…, 56, High St.», «…, Snargate Str.» end their streets, and
                         # «Benassi Sante.» is a forename; each took the next heading in, Derby, Droylsden, Firenze)
                         or re.search(r"\b(?:San|Santa|Santo|Saint|Sainte)\b(?:\s+\W{0,3}[a-z0-9]{0,2}\.?)?\s*$",
                                      MARGIN.sub("", cur["text"].rstrip(" ;|]'’\"”"))))):
                cur["text"] += " " + t
                continue
            if m and "," not in (th[:m.start("reg")] if m.group("reg") is not None else th) and not re.search(r"\d", th) \
                    and is_town(cand, m.group("reg"), country):
                # the margin's dash or bar after the town left off («Alger -», 1904 PDF 57)
                # the margin's capitals before the town left off («KI Beckenham», «LD Mulhouse», «Ê Biskra»; run p's
                # sample: Howard «borne out» by the town «KI»)
                # A WORD ALONE OF WHICH THE GAZETTEER HOLDS NO TOWN, in the country in force or in any, is a doubtful town:
                # the address's last word on its own line («…, Majstvi, 18,» / «Polk.», «…, dom» / «Smidta.»), a member
                # printed by the surname only (Cloez … / «Dalbert.» / Decote …), or a real town eo.wikipedia lacks
                # (Kettering, Hudiksvall). Its members keep their lines, without the town: dropping such headings took
                # hundreds of real towns with them, their members then given the town before (2026-10-30, three rules tried)
                if pend and not gz_known(cand, country) and gz_known(cand, pend[0]):
                    country, pend = pend[0], None
                    heads.append((p, n, "country", f"{country} ← the running head, at «{cand}»"))
                doubt = m.group("reg") is None and len(cand.split()) == 1 and not gz_known(cand, country) and not town_anywhere(cand)
                town = re.sub(r"^[A-ZÀ-Ž]{1,2}\s+(?=[A-ZÀ-Ž][a-zà-ž])", "", m.group("town").strip(" .-—|"))
                region, cur, town_at = (m.group("reg") or "").strip(), None, len(out)
                RAW[(y, n)] = th
                heads.append((p, n, "town", town + (f" ({region})" if region else ""))); continue
            # an entry begins after a blank line, or where the one before has ended («Bautheac P., notairia skribisto,»
            # runs on only when it ends in a comma or hyphen), or with the surname-and-comma shape
            starts = (was_gap or cur is None or ENTRY.match(t) or not cur["text"].rstrip().endswith((",", "-"))) and not open_
            if cur is not None and not starts or (cur is not None and t[:1].islower()):
                cur["text"] = (cur["text"][:-1] + t) if cur["text"].endswith("-") and t[:1].islower() else cur["text"] + " " + t
                continue
            cur = {"pdf": p, "line": n, "country": country, "town": town, "region": region, "text": t, "doubt": doubt}
            out.append(cur)
    return out, heads

def join_regions(rows):
    """A page's (line, text) with a heading's region broken over two lines joined: «Laguna del Carmen (Kampeĉa» / «Gub.).»
    → one line (1906 PDF 293: each half read as an entry, the members kept the town before; the fourth re-check of 2026-11-01)."""
    out, skip = [], False
    for i, (n, l) in enumerate(rows):
        if skip: skip = False; continue
        if i + 1 < len(rows) and l.count("(") > l.count(")") \
                and re.fullmatch(r"\W{0,2}[GC]ub\.{0,3}\s*\)?\s*\.?(?:\s+\S{1,3})?\s*", rows[i + 1][1].strip()):
            out.append((n, l.rstrip() + " " + rows[i + 1][1].strip())); skip = True
        else: out.append((n, l))
    return out

def town_anywhere(t):
    """Whether the gazetteer holds a town of this printed form in any country, by the form alone (no stem: «Polk», «Skopina»
    met towns by their stems); cached. The country is not asked: where a country's heading is misread the one in force is
    wrong (1906: Thun looked for in Sweden), and a test by it would take real towns for junk."""
    k = ("*", t)
    if k not in _TOWN:
        if GZ._IX is None: GZ.resolve(t, "")
        ix, f = GZ._IX, GZ.norm(t)
        _TOWN[k] = any(ix.places[x].get("town") for x in {**ix.by.get(f, {}), **ix.by.get(GZ.loose(f), {})})
    return _TOWN[k]

def parse(text):
    """(surname, the rest of the name, the chunks after it) of an entry: «Ganĉeva (Fi» R.), ul. …» → (Ganĉeva, (Fi» R.), [ul. …])."""
    t = re.sub(r"^[\W\d]{0,3}\s*", "", text).rstrip(" .;")
    # an initial's period doubled, the comma after it read as a period («Charpentier H.. profesoro de la kolegio»)
    t = re.sub(r"(?<=\b[A-ZÀ-Ž])\.\.\s", "., ", t, count=1)
    # … and a semicolon for the comma after the name («Reeve C. w. T0; Effingham road Leo.», run r's sample)
    head, _, rest = re.sub(r";", ",", t, count=1).partition(",") if ";" in t.split(",")[0] else t.partition(",")
    m = re.match(r"([A-ZÀ-Ž][\wÀ-ž'’-]+(?:[ -](?:de|van|von|la|le|du|da|di|del)\s+[A-ZÀ-Ž][\wÀ-ž'’-]+)?)\s*(.*)$", head.strip())
    if not m: return "", head.strip(), [c.strip() for c in rest.split(",") if c.strip()]
    return m.group(1), m.group(2).strip(), [c.strip() for c in rest.split(",") if c.strip()]

def bare(s):
    """A name's letters only, folded: «garcia-oltra», «Garcia Oltra» → «garciaoltra»."""
    return re.sub(r"[\W_]", "", DX.norm(s))

def join(hits, item, p, surname, given, town):
    """(label, verdict, how, candidates): a strong hit on the surname, borne out by the profile."""
    ph = hits.get((item, p), {})
    cands = {pp: tier for pp, tier in ph.get(DX.norm(surname), {}).items()} if len(DX.norm(surname)) >= 3 else {}
    # the search's «exact» is a roster name with the surname as one of its parts: the whole name only (the sample of run
    # p: «Martin A.» of Thiers went to SAINT-MARTIN, «Salvador Pérez» to SALVADOR FERRER)
    cands = {pp: ("parto" if t == "exact" and DX.norm(pp) != DX.norm(surname) else t) for pp, t in cands.items()}
    # … unless the surname and the next word make the roster name whole: a double surname («Garcia Oltra Santiago» is
    # GARCIA-OLTRA, not GARCIA borne out by «Santiago», run u's check)
    nxt = re.match(r"[A-ZÀ-Ž][\wÀ-ž'’-]+", given.strip("( "))
    whole = [pp for pp in cands if nxt and bare(pp) == bare(surname + nxt.group(0))]
    if whole: cands = {whole[0]: "exact"}
    name = f"{surname}, {given}" if given else surname
    borne = {pp: DX.borne_out(pp, name, surname, town) for pp in cands}
    # a name that is the town's own bears out nothing by the town («Flavigny (Abbaye de)» at Flavigny, run q's sample)
    if DX.norm(surname) == DX.norm(town): borne = {pp: ("" if b.startswith("la urbo") else b) for pp, b in borne.items()}
    # an entry printed with a full forename is not borne out by its initials alone («Miss Linda M. Bicknell» by «M.»,
    # which a French profile prints for «Monsieur»: the Annuaire's run e)
    full = bool(re.search(r"(?:^|\s)[A-ZÀ-Ž][a-zà-ž]{2,}", given))
    if full: borne = {pp: ("" if b.startswith("la inicialoj") else b) for pp, b in borne.items()}
    ok = [pp for pp, b in borne.items() if b]
    # several borne out by the town alone (a capital's namesakes: the Annuaire's Paris, run d): the one the forename or
    # initials bear out, where only one does (the initials not for a full forename here either)
    if len(ok) > 1:
        alt = {pp: DX.borne_out(pp, name, surname, "") for pp in ok}
        if full: alt = {pp: ("" if b.startswith("la inicialoj") else b) for pp, b in alt.items()}
        # (never a single initial: «M. Carpente» of Calais, «M.» a French profile's «Monsieur»; the Tutmonda's run v)
        alt = {pp: ("" if re.fullmatch(r"la inicialoj \S+", b) else b) for pp, b in alt.items()}
        strong = [pp for pp, b in alt.items() if b]
        if len(strong) == 1: ok, borne[strong[0]] = strong, alt[strong[0]]
    label = ok[0] if len(ok) == 1 else ""
    pr = DX.profile(label) if label else None
    verdict = ("ne en la nomaro" if not cands else "held: du personoj" if len(ok) > 1 else "held: nur la familia nomo" if not ok
               else "held: profilo ambigua" if not pr or "ambigu" in pr[1].split("\n", 1)[0].lower() or label.endswith("ambiguous")
               else f"held: {cands[label]} formo" if cands[label] != "exact" else "line")
    return (label if verdict == "line" else ""), verdict, borne.get(label, ""), "; ".join(f"{pp} ({cands[pp]}; {borne[pp] or '—'})" for pp in cands)

def town_key(town, country, region):
    """(the key's town, the sentence's town, the note) by the gazetteer, else as printed."""
    if len(DX.norm(town)) < 4: return town, town, ""
    if GZ._IX is None: GZ.resolve(town, country)   # builds the index once
    # the region printed in the bracket confirms the town; a form read by OCR may be mended by one confusion
    t, _w = GZ._IX.resolve(town, country, region, ocr=True)
    if not t: return town, town, ""
    eo = GZ._IX.places[t]["esperanto"]
    shown = f"{eo} ({town})" if GZ.fold(town) != GZ.fold(eo) else eo
    return eo, shown, f"; ⟦la urbo: «{town}» = {eo}, eo.wikipedia «{t}»⟧"

# THE POLISH ADDRESS BOOK (2026-10-30, the editor, parser (b)'s first dialect): *Adresaro de Polaj Esperantistoj por
# 1909* (Brzostowski, Varsovio; dowse/DIRECTORY-SURVEY-2026-10-29-analysis.md). Town headings in capitals, over one or two
# lines, the region and the country in the bracket: «KALISZ (Pollando—Rusujo).», «JEKATERINOSŁAW (Rus-» / «lando).»,
# «JÓZWIN per Kleczew, gub» / «Kaliska (Pollando—Rusujo).»; a society's heading («FILIO DE POLA ESPERANTISTA SOCIETO.»)
# and its committee in one paragraph, the forename first («Prezidanto: D-ro … Aleksander Danziger …»), not read (runbook
# D4c, «Not built yet»); «MEMBROJ ORDINARAJ.» and the members after it; an entry the surname first, ended by its period,
# wrapped with hyphens («Beatus Adolf, dentisto, str. War-» / «szawska 14.»), «(str. ? № ?)» where the address is unknown.
# a society's heading anywhere in the line («KRAKOVA SOCIETO „ESPERANTO"», «POLA STUDENTA SOCIETO „OGNIWO"»: run a took
# them for towns, Loth «borne out» by «Studenta»)
POLSOC = re.compile(r"\b(?:FILIO|SOCIETO|GRUPO|KLUBO|KOMITATO|RONDETO|UNUIĜO)\b")
# a title after the forename ends it («Wrzosek Adam D-ro med. Priv Docento …», «Dybowski Benedykt Prof. D-ro, …»)
POLTITLE = re.compile(r"\s+(?:D-ro|Dro|Prof\.|Prof-o|Prof|Inĝ\.|Mag\.|Kand\.|Pastro|Abato|Kapitano)\b.*$")
NOADDR = re.compile(r"\s*\(str\.\s*\?\s*№\s*\?\)\.?")

# THE COMMITTEES (2026-10-31; the editor: the yearbooks' items left to do, to be
# done): a committee's officers, the forename first, as entries of their own, the text put in the book's
# entry shape so the join is the members' («Mieczysław Kaus Towarowa 7.» → «Kaus Mieczysław, Towarowa 7.»); one line,
# {ofico: ‹office›, ‹body›}, as directory-extract.py writes the Tutmonda's officers
OFFICES = [("prezidanto", r"Prezidanto"), ("vicprezidanto", r"Vic-?prezidanto"), ("sekretario", r"Sekretario"),
           ("vicsekretario", r"Vic-?sekretario"), ("kasisto", r"Kasisto"), ("bibliotekisto", r"Bibliotekisto"),
           ("komitatano", r"Komitatanoj?"), ("revizoro", r"Revizoroj?"), ("ano de la instruista komisio", r"La Instruista Komisio"),
           # (2026-10-31, item 7: offices not known ran on into the officer before them, Kraków's «Vickasisto», «Mastrinoj»)
           ("vickasisto", r"Vic-?kasisto"), ("mastro", r"Mastro"), ("mastrino", r"Mastrinoj?"),
           ("konsul-agento", r"Konsul-?Agento"), ("anstataŭanto", r"Anstataŭantoj?"),
           ("ano de la revizia komisio", r"Komisio Revizia,?|Revizia Komisio")]
OFFICE_RE = re.compile(r"(?:^|(?<=[\s.;]))(" + "|".join(p for _, p in OFFICES) + r")\s*[:.]")
PTITLES = re.compile(r"^(?:(?:D-ro|Dro|Prof\.|Prof-o|Inĝ\.|Mag\.|Pastro|S-ro|S-ino|F-ino|de|Filoz\.|med\.|Excmo,?|Sr\.|S-ro\.|D[.,]|»|v|\d)\s*)+")

def office_of(label):
    return next(o for o, p in OFFICES if re.fullmatch(p, label))

def officers_pola(para, body):
    """[(office, the entry's text)] of a Polish committee paragraph («Prezidanto: D-ro … Aleksander Danziger …»)."""
    marks = list(OFFICE_RE.finditer(para))
    out = []
    for i, m in enumerate(marks):
        seg = para[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(para)].strip(" .;,")
        # the persons apart by semicolons, or by a comma after an address's number and before «Forename Surname,» (2026-10-31,
        # item 7: Kalisz's Instruista Komisio, «Mieczysław Kaus, Direktanto, Towarowa 7, Włodzimierz Dobrowolski, Nowa 6,
        # Helena Kaus, Towarowa 7; …»; not after a street's name, «Aleja Józefiny, dom p. Rudzkiego»)
        # (and by «kaj» before a name: «Hilary Ostrowski kaj D-ro Józef Szawelski», Siedlce)
        for person in re.split(r"\s*;\s*|(?<=\d),\s*(?=[A-ZÀ-Ž][a-zà-ž]+\s+[A-ZÀ-Ž][\wÀ-ž'’-]+,)"
                               r"|\s+kaj\s+(?=(?:D-ro\s+|Prof\.\s+)?[A-ZÀ-Ž][a-zà-ž]+\s+[A-ZÀ-Ž])", seg):
            person = PTITLES.sub("", person.strip())
            # the occupation before the name («teknika bierfarejestro, Izydor Sercarz, Nadrzeczna 1», Będzin): after it
            o = re.match(r"([a-zĉĝĥĵŝŭà-ž][^,]*),\s*(?=[A-ZÀ-Ž])(.+)$", person)
            if o: person = PTITLES.sub("", o.group(2)) + ", " + o.group(1)
            # a forename's initial («S. Guttmann», «Iz. Jawitz»)
            w = re.match(r"([A-ZÀ-Ž][\wÀ-ž'’-]+|[A-ZÀ-Ž][a-zà-ž]{0,2}\.)\s*([A-ZÀ-Ž][\wÀ-ž'’-]+)(.*)$", person)
            if not w: continue
            office, rest = office_of(m.group(1)), (w.group(3) or "").strip(" ,")
            # the committee's own office after the name («Mieczysław Kaus, Direktanto, …»)
            d = re.match(r"(Direktanto|Vicdirektanto|Sekretario|Kasisto)\b[,.]?\s*", rest)
            if d and office.startswith("ano de la "): office, rest = d.group(1).lower() + office[3:], rest[d.end():]
            out.append((office, f"{w.group(2)} {w.group(1)}, {rest}".rstrip(" ,") + "."))
    return out

def officers_hisp(block):
    """[(office, the entry's text)] of a Spanish group's officers («Prezidanto. D. Antonio Mayo. Sekretario. » Ramón
    Gabernet.—Presbítero.»), the forename first, put in the book's shape: «Gabernet, Ramón.—Presbítero.»."""
    marks = list(OFFICE_RE.finditer(block))
    out = []
    for i, m in enumerate(marks):
        seg = block[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(block)].strip(" .;,")
        seg = PTITLES.sub("", re.sub(r"^(?:[»>v\d.,\s]|Excmo|Sr\.|S-ro\.?|D\s?[.,])+", "", seg)).strip()
        # the name ends at its dash, comma or period («Antonio Mayo. ie Sekretario.»: the margin's letters after it)
        name = re.split(r"\s*(?:\.?\s*—|,|\.\s)\s*", seg, maxsplit=1)[0]
        rest = seg[len(name):].strip(" .,—")
        # a forename's abbreviation is no surname («Juan Bta. Pelayo», Juan Bautista)
        ws = [w for i, w in enumerate(name.strip(" .").split()) if not (i and re.fullmatch(r"[A-ZÀ-Ž][a-zà-ž]{0,3}\.", w))]
        if len(ws) >= 2 and ws[0][:1].isupper():
            item = (office_of(m.group(1)), f"{' '.join(ws[1:])}, {ws[0]}.—{rest}".rstrip("—") + ".")
            # the OCR's line printed twice («Sekretario. » Ramón Gabernet» on two lines, Solsona)
            if not any(o == item[0] and t.split(",")[0] == item[1].split(",")[0] for o, t in out): out.append(item)
    return out

def pola_head(h):
    """(town, region, country, the heading as read) of a town heading: «KALISZ (Pollando—Rusujo).» → (Kalisz, Pollando,
    Rusio, …); the country the bracket's last part, as the gazetteer reads it."""
    m = re.match(r"^(.+?)(?:,|\s+per\s|\s*\(|\.$)", h)
    br = re.search(r"\(([^()]*)\)", h)
    parts = [x.strip() for x in re.split(r"\s*[—–]\s*", br.group(1))] if br else []
    # a second form after «=» left off («ŁÓDŹ=LODZ», «MIŁOSŁAW = MILOSLAV»)
    town = (m.group(1) if m else h).split("=")[0].strip(" .").title()
    c = GZ.pcountry(parts[-1]) if parts else ""
    country = (GZ.CKEYS.get(GZ.ckey(c)) or NAMED.get(GZ.ckey(c), c)) if c else (parts[-1] if parts else "")
    return town, (parts[0] if len(parts) > 1 else ""), country, (f"{town} ({', '.join(parts)})" if parts else town)

def entries_pola(item, a, b):
    """[{pdf, line, country, town, region, text, doubt}] of the Polish address book, PDF pages a–b; and the headings."""
    pages = DX.page_lines(item)
    # committee: 0 the members, 1 after a society's heading, 2 inside its committee paragraph
    out, heads, country, town, region, cur, head, committee = [], [], "", "", "", None, None, 0
    soc, para = "", None
    def ended(t): return t.rstrip().endswith(".") or bool(re.search(r"\(str\.\s*\?\s*№\s*\?\)$", t.rstrip()))
    def joined(x, t): return (x[:-1] + t) if x.endswith("-") and t[:1].islower() else x + " " + t
    def flush():
        # the committee's officers as entries of their own (see OFFICES)
        for office, text in officers_pola(para["text"], soc):
            out.append({"pdf": para["p"], "line": para["n"], "country": country, "town": town, "region": region, "text": text,
                        "doubt": False, "office": office, "body": f"{soc} en {town}" if town and town.lower() not in soc.lower() else soc})
    for p in range(a, b + 1):
        for n, l in pages.get(p, []):
            s = l.strip()
            # the committee is one paragraph, opening on an office and ended by a blank line; after a society's heading
            # any other line is a member (Pola Studenta Societo „Ogniwo": its members follow its heading, run b lost them)
            if not s:
                if committee == 2: committee = 0; flush(); para = None
                continue
            if re.fullmatch(r"\d{1,3}", s): continue
            if committee == 1:
                committee = 2 if re.match(r"(?:Prezidanto|Vicprezidanto|Sekretario|Kasisto|Komitatanoj|Estraro|Direktanto|Vicdirektanto)\b", s) else 0
                if committee == 2: para = {"text": s, "p": p, "n": n}; continue
            if committee == 2: para["text"] = joined(para["text"], s); continue
            # (the form before «=»: «BĘDZIN=Bendzin, gub. Piotrkowska …» was no heading, its members put in Berlin's)
            first = s.split()[0].split("=")[0].strip(",.(")
            # a heading opens in capitals after an entry ended; it runs on until a line ends in its period
            if head is None and (cur is None or ended(cur["text"])) and len(first) >= 3 and first.isupper():
                cur = None
                if s.startswith("MEMBROJ"): committee = 0; continue
                if POLSOC.search(s.upper()):
                    # the body's name in title case, its small words small («Filio de Pola Esperantista Societo»)
                    soc = " ".join(w.lower() if i and w.lower() in ("de", "la", "kaj", "en", "por", "al") else w.capitalize()
                                   for i, w in enumerate(s.strip(" .").split()))
                    committee = 1; continue
                committee, head = 0, {"text": s, "p": p, "n": n}
            elif head is not None:
                head["text"] = joined(head["text"], s)
            if head is not None:
                if not s.endswith("."): continue
                town, region, country, label = pola_head(head["text"])
                heads.append((head["p"], head["n"], "town", label)); head = None; continue
            if cur is not None and not ended(cur["text"]) and not (ENTRY.match(s) and not cur["text"].endswith("-")):
                cur["text"] = joined(cur["text"], s); continue
            cur = {"pdf": p, "line": n, "country": country, "town": town, "region": region, "text": s, "doubt": False}
            out.append(cur)
    if para is not None: flush()
    # «Piątkowska Helena—lia edzino» («his wife», after her husband's entry): the note out of the forename
    for e in out: e["text"] = re.sub(r"\s*[—–]\s*(?=(?:lia|ŝia|ilia)\b)", ", ", NOADDR.sub("", e["text"]).strip())
    return out, heads

# THE HISPANA JARLIBRO 1906 (2026-10-31, the editor, parser (b)'s second dialect; Jimeno, Valencia): the groups'
# officers first (PDF 33–34, «Prezidanto. … Sekretario. …», not read: runbook D4c, «Not built yet»), then «Hispana
# Esperantistaro», PDF 35–76: the provinces in normal case («Alicante»; an entry straight after it lives in its capital),
# the towns in capitals («VILLARROBLEDO»), an entry the surnames whole before the comma, then the forename, then occupation
# and street after dashes: «Martínez Jiménez, José.—Cura Párroco.», «Biaggi Alcázar, Luis.—Sargento.—Regimiento …». The
# OCR reads é as «ĉ» («Josĉ», «Mĉdico»: Spanish has no ĉ) and doubles dashes («—-Industrial»); the margin's letters open lines.
PROVINCES = {GZ.fold(p): p for p in (
    "Álava Albacete Alicante Almería Ávila Badajoz Baleares Barcelona Burgos Cáceres Cádiz Canarias Castellón Córdoba "
    "Coruña Cuenca Gerona Granada Guadalajara Guipúzcoa Huelva Huesca Jaén León Lérida Logroño Lugo Madrid Málaga Murcia "
    "Navarra Orense Oviedo Palencia Pontevedra Salamanca Santander Segovia Sevilla Soria Tarragona Teruel Toledo Valencia "
    "Valladolid Vizcaya Zamora Zaragoza").split() + ["Ciudad Real"]}
CAPITAL = {"Álava": "Vitoria", "Vizcaya": "Bilbao", "Guipúzcoa": "San Sebastián", "Navarra": "Pamplona", "Coruña": "La Coruña",
           "Baleares": "Palma", "Canarias": "Las Palmas"}
HTITLE = re.compile(r"^(?:R\.\s*P\.|D\s?\.|Dña\.|Sra\.|Srt\S?\.|Sr\.|Doña|Don)\s*")
# an entry's first line: the surnames, a comma, a forename, then the dash («Sierra, Ramón.—Comerciante.»); a street's
# run-on («Pedro, 5.») has no dash
HENTRY = re.compile(r"^[A-ZÀ-Ž][\wÀ-ž'’-]+(?:\s+(?:de\s+|del\s+|y\s+|la\s+)?[A-ZÀ-Ž][\wÀ-ž'’-]+){0,3}\s*,\s*(?:[A-ZÀ-Ž][\wÀ-ž.]*\s*){1,4}[.,]?\s*—")
# a first word that is no surname of its own, for the fallback to the first surname («San Antonio Angel Molina, Juan»)
HPART = {"san", "santa", "de", "del", "la", "las", "los", "y"}

def hisp_clean(s):
    """A line of the Hispana: the margin's letters at its head left off, é for «ĉ», one dash for doubled ones."""
    s = re.sub(r"^(?:[^\wÀ-ž«(]+|[\wÀ-ž]\b[^\wÀ-ž«(]*|\|\w\b)\s+(?=\S)", "", s.strip())
    s = s.replace("ĉ", "é").replace("Ĉ", "É")
    return re.sub(r"\s*(?:—|--)[—-]*\s*", "—", s)

def entries_hisp(item, a, b):
    """[{pdf, line, country, town, region, text, doubt}] of the Hispana Jarlibro's persons, PDF pages a–b; the headings."""
    pages = DX.page_lines(item)
    out, heads, town, region, cur = [], [], "", "", None
    # the groups' officers before «Hispana Esperantistaro» (PDF 33–34): a group by its town and year, «Murcia (1902)»,
    # «Manresa (Barcelona) (1904)»; its officers' lines run on to the next group
    groups, block = a <= 34, None
    # (the margin's junk before it: «ŝ : Coruiia (1905)», run c's groups put Coruña's officers under Solsona)
    GROUPH = re.compile(r"([A-ZÀ-Ž][a-zà-ž][\wÀ-ž'’ -]*?)\s*(?:\(([^()\d]+)\))?\s*\((\d{4})\)")
    def flush():
        for office, text in officers_hisp(block["text"]):
            out.append({"pdf": block["p"], "line": block["n"], "country": "Hispanio", "town": block["town"], "region": block["region"],
                        "text": text, "doubt": False, "office": office, "body": f"esperantista grupo en {block['town']}"})
    def ended(t): return bool(re.search(r"\.$", MARGIN.sub("", t.rstrip(" >|X"))))
    for p in range(a, b + 1):
        pl = pages.get(p, [])
        for k_, (n, l) in enumerate(pl):
            s = hisp_clean(l)
            nxt = next((hisp_clean(x) for _m, x in pl[k_ + 1:] if hisp_clean(x)), "")
            if groups:
                if s.startswith("Hispana Esperantistaro"):
                    if block: flush()
                    groups, block = False, None; continue
                g = GROUPH.search(s)
                if g and g.start() > 8: g = None
                if g:
                    if block: flush()
                    # ñ read as «ii» («Coruiia»)
                    block = {"town": g.group(1).strip().replace("iia", "ña"), "region": (g.group(2) or "").strip(), "text": "", "p": p, "n": n}
                    heads.append((p, n, "town", f"{block['town']} (grupo, {g.group(3)})")); continue
                if block and s: block["text"] = (block["text"][:-1] + s) if block["text"].endswith("-") else (block["text"] + " " + s).strip()
                continue
            if not s or re.fullmatch(r"[\W\d]{1,4}|\w{1,2}", s) or s.startswith("Hispana Esperantistaro"): continue
            # a heading's margin junk and figures after it left off («Valencia . i», «PUEBLA DE ALMORADIEL 4»: run a took
            # the second for a town and missed the first, so Valencia's members went to Puebla)
            plain = re.sub(r"(?:[\s.]+(?:[^\s.]{1,2}|\d+))+$", "", s).strip(" .")
            # a heading stands even after an entry left open by a comma («Calvo, …, Comandante de Infanteria,» / «Gerona»)
            if "—" not in s and "," not in s and not re.search(r"\d", plain):
                if GZ.fold(plain) in PROVINCES:
                    region = PROVINCES[GZ.fold(plain)]; town = CAPITAL.get(region, region); cur = None
                    heads.append((p, n, "town", f"{town} ({region})")); continue
                letters = re.sub(r"[^A-Za-zÀ-ž]", "", plain)
                if len(letters) >= 3 and sum(c.isupper() for c in letters) >= 0.7 * len(letters):
                    town = " ".join(w.lower() if i and w.lower() in ("de", "del", "la", "las", "los", "y") else w.title()
                                    for i, w in enumerate(plain.split()))
                    cur = None; heads.append((p, n, "town", f"{town} ({region})")); continue
                # … or in small letters, as the pages read again by vision print them («Figueras», «Solsona»: 2026-11-01,
                # Dalí and Colell lost, «Solsona Colell» read as a surname), after an ended entry, a town the gazetteer
                # knows in Spain (not «San …», «Santa …»: «San Antonio» / «Angel Molina, Juan.», a name run over two
                # lines), or after a blank line with an entry at once after it («Solsona» / «Colell, Pedro.», «Sallent»:
                # towns the gazetteer lacks); never a line ending on a stop («Jiménez Luis.», «Ruiz Antonio.», persons
                # without the comma; «Santa Eulalia.», an address run on)
                blank = k_ == 0 or pl[k_ - 1][0] < n - 1 or not pl[k_ - 1][1].strip()
                gzk = gz_known(plain, "Hispanio")
                if (len(plain.split()) <= 3 and len(letters) >= 4 and "." not in plain and not s.rstrip().endswith(".")
                        and (cur is None or ended(cur["text"])) and all(w[:1].isupper() or w.lower() in HPART for w in plain.split())
                        and ((gzk and not re.match(r"(?:San|Santa|Santo)\b", plain))
                             or (blank and gzk)
                             # (no blank needed where an entry follows and the line is no «San …»: «Cardona», «Berga»; the
                             # re-check of 2026-11-01c, lines 3 and 4)
                             or (not re.match(r"(?:San|Santa|Santo)\b", plain)
                                 and re.match(r"^[A-ZÀ-Ž][\wÀ-ž'’ -]{1,40},\s*(?:[A-ZÀ-Ž]|R\.\s*P\.)", nxt)))):
                    town = " ".join(w.lower() if i and w.lower() in HPART else w.title() for i, w in enumerate(plain.split()))
                    cur = None; heads.append((p, n, "town", f"{town} ({region})")); continue
            # an entry's own shape opens a new one even after a comma («…, Hotel La Cartagenera,» / «Sierra, Ramón.—…»)
            if cur is not None and not ended(cur["text"]) and not (HENTRY.match(s) and not cur["text"].endswith("-")):
                cur["text"] = (cur["text"][:-1] + s) if cur["text"].endswith("-") and s[:1].islower() else cur["text"] + " " + s
                continue
            cur = {"pdf": p, "line": n, "country": "Hispanio", "town": town, "region": region, "text": s, "doubt": False}
            out.append(cur)
    return out, heads

def parse_hisp(text):
    """(the surnames, the forename, the chunks after them): «Martínez Jiménez, José.—Cura Párroco.» → (Martínez Jiménez,
    José, [Cura Párroco]); a period for the comma («Barcos Oses. Pablo —Industrial.»), or none («Ruiz Antonio.»)."""
    head, _, rest = text.partition("—")
    head = head.strip(" .;")
    if "," in head: sur, _, given = head.partition(",")
    elif re.search(r"\.\s+[A-ZÀ-Ž]", head): sur, _, given = head.partition(". ")
    # («Tobella y Casteltort.»: two surnames joined by «y», no forename)
    elif " y " in head: sur, given = head, ""
    else: ws = head.split(); sur, given = (" ".join(ws[:-1]), ws[-1]) if len(ws) > 1 else (head, "")
    # the forename ends at its period («Gimeno, R. P. Vicente. Pías. Pias.», the dash lost)
    given = HTITLE.sub("", given.strip(" .,")).split(". ")[0]
    return sur.strip(" .,"), given, [c.strip(" .,;") for c in rest.split("—") if c.strip(" .,;")]

# THE ANNUAIRE 1901 (2026-10-31, the jarlibroj to-dos): the *Annuaire* of the Société pour la propagation de l'Esperanto,
# French and Esperanto (dowse/DIRECTORY-SURVEY-2026-10-29-analysis.md), its members PDF 35–84: countries «AUTRICHE
# (AŬSTRUJO)», towns «Leoben (Styrie) :», an entry a category sign that carries over to the entries after it («pr.»
# propagandanto, «ad.» adepto, «ap.» aprobanto: the book's own key, l. 248–258), a title, the name forename first, then
# the address and the I.K.E. number: «ad. M. Rudolf Sperl, pens . K.-K. Beamter (I. K. E. 16).»; the margin's junk
# before the sign («Mead. M. Joseph Rhodes», «amad. Miss Linda M. Bicknell», «+ ad.»)
ACAT = {"pr": "propagandanto", "ad": "adepto", "ap": "aprobanto"}
ASIGN = re.compile(r"(?:^|[^a-z])(pr|ad|ap)\s*\.\s+(?=(?:M|Mme|Mlle|Mie|Miss|Mrs|Mr|Dr|D-ro|[A-ZÀ-Ž])\b)")
ATITLE = re.compile(r"(?:^|\s)(?:M|Mme|Mne|Mlle|Mie|Miss|Mrs|Mr|Dr|D-ro|Docteur|Abbé|Rév\.|R\.\s*P)\.?\s+(?=[A-ZÀ-Ž])")
ACOUNTRY = re.compile(r"^[A-ZÀ-Ž'’ .ÇÉ-]{3,}\s*\(\s*([A-ZÀ-ŽĈĜĤĴŜŬ'’ .-]{3,}?)\s*\)")
APERIOD = {"angluj": "Britio", "alsac": "Francio", "unuigitaj statoj": "Usono", "monark": "Monako", "silio": "Ĉilio", "hinuj": "Ĉinio",
           "holland": "Nederlando", "finland": "Finnlando", "taluj": "Italio"}

def entries_annu(item, a, b):
    """[{pdf, line, country, town, region, text, doubt, cat, ike}] of the Annuaire's members, PDF pages a–b; the headings."""
    pages = DX.page_lines(item)
    out, heads, country, town, region, cur, cat = [], [], "", "", "", None, ""
    def ended(t): return bool(re.search(r"\.\s*$", MARGIN.sub("", t.rstrip(" |"))))
    # a page read as one line (l. 2634, 2764: «— 31 — Ornans (Doubs) : ad. M. Midoz, … Pantin (Seine): : ad. M. … Paris :
    # …», run b put Paris's members under Orléans): cut at the entries' bars, before a heading, after its colon, and
    # before a sign or title after a period
    CUT = re.compile(r"\s+\|\s+|(?<=[.)])\s+(?=[A-ZÀ-Ž][\wÀ-ž'’ -]{1,40}(?:\s*\([^()]{2,30}\))?\s*:\s)|(?<=:)\s+(?=(?:pr|ad|ap)\s*\.)|(?<=\s:)\s+(?=[A-ZÀ-Ž])"
                     r"|(?<=\.)(?<!pr\.)(?<!ad\.)(?<!ap\.)\s+(?=(?:pr|ad|ap)\s*\.\s|(?:M|Mme|Mlle|Miss)\.?\s+[A-ZÀ-Ž])")
    # (every line, not only the long ones: «Crema : + pr. Docteur Daniele Marignoni», a heading and an entry in one)
    def lines_of(p):
        for n, l in pages.get(p, []):
            for part in CUT.split(re.sub(r"^\s*—\s*\d+\s*—\s*", "", l)): yield n, part
    for p in range(a, b + 1):
        for n, l in lines_of(p):
            s = l.strip()
            if not s or re.fullmatch(r"[\W\d]{1,4}|\w{1,2}", s): continue
            # (the margin's bar before a country: «| ITAUE (TALUJO)», ITALIE, Clarence Bicknell's)
            cm = ACOUNTRY.match(re.sub(r"^[\s'|.:+\-–—]+", "", s))
            if cm:
                k = GZ.fold(cm.group(1)).replace("ujo", "uj")
                c = next((v for kk, v in APERIOD.items() if k.startswith(kk)), None) or country_of(cm.group(1), country) or cm.group(1).title()
                country, town, region, cur, cat = c, "", "", None, ""
                heads.append((p, n, "country", f"{c} ← «{s}»")); continue
            # the list begins at its first country (run a: the committee's «Assesseurs» taken for a town, Bourlet borne
            # out by it)
            if not country: continue
            body = re.sub(r"^[\s'|.:+\-–—]+", "", s)
            # a line in capitals is a country misread or nothing, never a town («ITAUE», ITALIE, run a)
            if len(body) >= 4 and body.upper() == body and re.search(r"[A-Z]{4}", body):
                c = country_of(re.sub(r"[^A-ZÀ-ŽĈĜĤĴŜŬ -]", "", body), country)
                if c is not None and c != country: country, town, region, cur, cat = c, "", "", None, ""; heads.append((p, n, "country", f"{c} ← «{body}»"))
                elif c is None: town, cur = "", None
                continue
            # a town: «Town (Region) :», or «Town (Region)» with its colon on the next line; never a wrapped line ending
            # in a bracket («… Conseil héraldique de France . ).», run a)
            # (the margin's junk after the colon: «Bordighera : | «pr.»)
            # (and «Town, près Other :»: «Vaumarcus, près Neufchâtel :», PDF 84, refused for its comma, so Borel stayed
            # at Nyon; the accuracy check of 2026-11-01: the town the part before the comma)
            tm = re.match(r"^([A-ZÀ-Ž][^,:]{1,70}?)(?:,\s*(?:près|pres|par|bei|near|lez|lès)\s+[^,:]{2,40})?\s*:\s*[:|\-\s«»]*(?:\S{0,4})$", body) or (re.match(r"^([A-ZÀ-Ž][^,:().]{1,50}\([^()]{2,30}\))\s*$", body) if not ASIGN.search(body) and not ATITLE.search(body) else None)
            if tm and not ATITLE.search(tm.group(1)):
                h = tm.group(1).strip()
                rm = re.search(r"\(([^()]+)\)\s*$", h)
                town, region = (h[:rm.start()].strip(" ,"), rm.group(1)) if rm else (h, "")
                town = re.sub(r",\s*(?:gub|per|p\.).*$", "", town).strip()
                cur, cat = None, ""
                heads.append((p, n, "town", h)); continue
            sm = ASIGN.search(body)
            if sm and sm.start() > 10: sm = None
            ti = ATITLE.search(body)
            if ti and ti.start() > 10: ti = None
            if sm or ti:
                if sm: cat = ACAT[sm.group(1)]
                start = sm.end() if sm else ti.start()
                rest = body[start:].strip()
                cur = {"pdf": p, "line": n, "country": country, "town": town, "region": region, "raw": rest, "doubt": False, "cat": cat}
                out.append(cur); continue
            if cur is not None and not ended(cur["raw"]):
                cur["raw"] = (cur["raw"][:-1] + body) if cur["raw"].endswith("-") and body[:1].islower() else cur["raw"] + " " + body
    for e in out:
        raw = e["raw"]
        ik = re.search(r"\(\s*[IJ1l]\.?\s*[KΚ]\.?\s*[EΕ]\.?\s*(\d+)\s*\)", raw)
        e["ike"] = ik.group(1) if ik else ""
        raw = re.sub(r"\(\s*[IJ1l]\.?\s*[KΚ]\.?\s*[EΕ]\.?[^)]*\)", "", raw)
        raw = ATITLE.sub(" ", " " + raw, count=1).strip()
        # a title after «M.» («M. l'abbé Solis», «M. le docteur Joly», run a)
        raw = re.sub(r"^(?:l['’]\s*abbé|labbé|le\s+(?:docteur|Dr|professeur|comte|baron|capitaine|commandant|général|lieutenant|pasteur))\s+", "", raw)
        name, _, rest = raw.partition(",")
        ws = [w for w in name.strip(" .").split() if w not in ("fils", "père", "aîné", "jeune")]
        # (kept beside the name, which it tells from the father's: «Ferdinand Dumas fils», PDF 43; 2026-11-01)
        e["suffix"] = " ".join(w for w in name.strip(" .").split() if w in ("fils", "père", "aîné", "jeune"))
        # the surname the last word, with its particles («Paul de Lagarde»)
        i = len(ws) - 1
        while i > 0 and ws[i - 1].lower() in ("de", "du", "van", "von", "la", "le", "d'"): i -= 1
        sur, given = " ".join(ws[i:]), " ".join(ws[:i])
        e["text"] = f"{sur} {given}, {rest.strip()}".replace(" ,", ",").strip(" ,") if sur else raw
    return out, heads

# THE FLAT LISTS (2026-10-31, the jarlibroj to-dos; dowse/DIRECTORY-SURVEY-2026-10-29-analysis.md): no headings, the
# town and country inside the entry. T.E.K.A., the *Jarlibro de Tutmonda Esperantista Kuracista Asocio*: 1909 «D-ro
# Brinitzer, Eugen, dermatologo, Schulterblatt 139, Altona, Elbe (Germanujo). 585,», 1910 «Hertz, M., laringologo, str.
# Prozna 14, Varsovio. Rp.» (a country code, no key found), the margin's line numbers and letters at the head of a line
# («44 ka Heryng, …», «; 215 Heuls, …»). The Boulogne congress-goers 1905: «Brande Josĉphine, 63, rue Faidherbe.», a hotel
# or a home town («Barrell Alice, Spalding (England).»)
TCODE = {"r": "Rusio", "rp": "Rusio", "g": "Germanio", "f": "Francio", "hu": "Hungario", "svi": "Svislando", "u": "Usono",
         "u s": "Usono", "au": "Aŭstrio", "aŭ": "Aŭstrio", "hind": "Hindio", "hi": "Hispanio", "rum": "Rumanio", "it": "Italio",
         "bel": "Belgio", "b": "Belgio", "a": "Britio", "angl": "Britio", "hol": "Nederlando", "sv": "Svedio", "nor": "Norvegio",
         "dan": "Danio", "bul": "Bulgario", "serb": "Serbio", "tur": "Turkio", "gr": "Grekio", "port": "Portugalio", "mex": "Meksiko"}
NAMESTART = re.compile(r"(?:D-ro\s+|Prof\.\s+|Dr\.?\s+)?([A-ZÀ-Ž][\wÀ-ž'’-]+(?:\s+(?:de|van|von|la|le)\s+[A-ZÀ-Ž][\wÀ-ž'’-]+)?)[,.]\s*(?=[A-ZÀ-Ž])")

# (Boulogne's: the surname, the forename or initials, then the comma: «Brande Joséphine, 63, …»)
BSTART = re.compile(r"(?:Mlle|Mme|Dr|M\.)?\s*[A-ZÀ-Ž][\wÀ-ž'’-]+\.?\s+(?:[A-ZÀ-Ž][\wÀ-ž.'’-]*\s*){1,3},")

# (T.E.K.A. 1910's: the surname and its comma, then a capital)
TSTART = re.compile(r"[A-ZÀ-Ž][\wÀ-ž'’-]+(?:\s+(?:de|van|von|la|le)\s+[A-ZÀ-Ž][\wÀ-ž'’-]+)?,\s*(?=[A-ZÀ-Ž])")

def flat_start(s, pat=NAMESTART):
    """The index where an entry opens in a line after the margin's junk, or None."""
    m = pat.search(s)
    return m.start() if m and m.start() <= 12 else None

def tbare(c):
    """A town's chunk without its postal letters («London W», «London S. E.»), for the gazetteer's test; a town the OCR
    split closed up («Lon don W», 1910 PDF 27, Johnston's)."""
    c = re.sub(r"\s+(?:[A-Z]\.?\s*){1,3}$", "", c).strip()
    # (the junk after its period: «Dublin. dr. ĵ S-», Fleming's, 1910 PDF 24)
    if ". " in c and not town_anywhere(c) and town_anywhere(c.split(". ")[0]): c = c.split(". ")[0]
    if " " in c and not town_anywhere(c) and re.fullmatch(r"[A-ZÀ-Ž][a-zà-ž]+(?: [a-zà-ž]+)+", c) and town_anywhere(c.replace(" ", "")): c = c.replace(" ", "")
    return c

def entries_teka(item, a, b, year):
    """[{pdf, line, country, town, region, text, doubt, aligo}] of a T.E.K.A. yearbook's members; no headings."""
    pages = DX.page_lines(item)
    out, cur = [], None
    def ended(t):
        t = t.rstrip(" ,;:|")
        return bool(re.search(r"\)\.?\s*\d*[.,]?$", t)) if year == 1909 else bool(re.search(r"[.]\s*[A-ZÀ-Ž][\w. ]{0,5}\.?\s*\d?$", t))
    for p in range(a, b + 1):
        for n, l in pages.get(p, []):
            s = l.strip()
            if not s or re.fullmatch(r"[\W\d]{1,6}|\w{1,2}", s): continue
            # 1910: an entry opens at every «Surname, Name» line unless the line before ends in a hyphen (its run-on lines
            # never take that shape: «Rp.», «SOViO. Rp.»; the junk after a code, «Wilno. hI» / «dd.», ran Leon Zamenhof's
            # entry into the one before); 1909's run-on lines begin with a town and a comma, so there an entry must end first
            i = flat_start(s, TSTART) if year == 1910 else flat_start(s)
            if i is not None and (cur is None or (not cur["raw"].rstrip().endswith("-") if year == 1910 else ended(cur["raw"]))):
                cur = {"pdf": p, "line": n, "raw": s[i:], "doubt": False, "aligo": "Tutmonda Esperantista Kuracista Asocio"}
                out.append(cur); continue
            if cur is not None and not ended(cur["raw"]):
                s = re.sub(r"^[|;:]+\s*", "", s)   # the margin's bar before a run-on («Var-» / «| SOViO»)
                cur["raw"] = (cur["raw"][:-1] + s) if cur["raw"].endswith("-") and s[:1].isalpha() else cur["raw"] + " " + s
    keep = []
    for e in out:
        raw = re.sub(r"^(?:D-ro|Dr\.?|Prof\.)\s+", "", e["raw"]).strip()
        # a brace for a bracket, the margin's junk at the end («Varsovio {Poluio). 6, :»: the country lost, so «Leon»,
        # Zamenhof's brother's forename, became the town and bore out Ludwik's profile; run a)
        raw = re.sub(r"[\s,:;|.]+$", "", raw.replace("{", "(").replace("}", ")")) + "."
        if year == 1909:
            cm = re.search(r"\(([^()]{2,25})\)\.?\s*\d*[.,]?\s*$", raw)
            country = (GZ.CKEYS.get(GZ.ckey(GZ.pcountry(cm.group(1)))) or GZ.pcountry(cm.group(1)) or "") if cm else ""
            if cm and not country and re.match(r"U\.?\s*S", cm.group(1)): country = "Usono"
            body = raw[:cm.start()] if cm else raw
        else:
            # (the margin's junk after the code: «Varsovio. ; Rp ĥi»)
            cm = re.search(r"[.]\s*[;:|]?\s*([A-ZÀ-Ž][\w. ]{0,5}?)\.?\s*(?:\d|[^\s.]{1,3})?\s*\.?$", raw)
            country = TCODE.get(GZ.fold(cm.group(1)).strip(), "") if cm else ""
            body = raw[:cm.start()] if cm else raw
        chunks = [c.strip(" .") for c in body.split(",") if c.strip(" .")]
        if len(chunks) < 2: continue
        # (more than seven chunks: entries run together, the town and address another's: «Vesoux, …, Paris, Beaune
        # (C0te d'Or.) F. Vignalon, …, Vasiljevskij Ostrov», 1910 PDF 41; 2026-11-01)
        if len(chunks) > 7: continue
        sur, given = chunks[0], ""
        # (a period inside the forename's chunk ends it: «Kerr, Eugene. Shenvood Hotel, Baltimore», 1909, the hotel
        # read as his name; the accuracy check of 2026-11-01)
        pm = re.match(r"^([A-ZÀ-Ž][a-zà-ž]{2,})\.\s+([A-ZÀ-Ž].*)$", chunks[1])
        if pm: chunks = [chunks[0], pm.group(1), pm.group(2)] + chunks[2:]
        # the forename: initials, or a word that is no town («Broeckaert, Maagziekten» a specialty, «Buchmann, Dirlewang» a town)
        g1 = chunks[1]
        # (refused as a town only where no later chunk is one: «Zamenhof, Leon, …, Varsovio», «Whitaker, Sydney, Liverpool»;
        # a town's postal letters left off for the test: «Johnston, George, …, London W», George taken for his town, 1909)
        later_town = any(town_anywhere(tbare(c)) for c in chunks[2:] if not re.search(r"\d", c))
        if re.fullmatch(r"(?:[A-ZÀ-Ž][\wÀ-ž'’.-]*\s*){1,3}", g1) and not re.search(r"\d", g1) \
                and (re.fullmatch(r"(?:[A-ZÀ-Ž]\.?\s*-?){1,4}", g1) or not town_anywhere(g1) or later_town) \
                and not re.search(r"(?:ziekten|logo|isto|ologie)$", g1): given = g1; rest = chunks[2:]
        else: rest = chunks[1:]
        # the town: the last chunk that is a town by its form (never a region: «Bayern», «Finistere»); else the last chunk,
        # if short, with no figure and no state's abbreviation («Pa», «Mich», «Md»; «Bismarckplaco 12», the imprint's)
        last = rest[-1] if rest else ""
        # (a region by its marker is no town: «Galit, Kostrom. gub.», Kostroma taken for Galič; the re-check of 2026-11-01c):
        # it is taken off its chunk, the town looked for in what is left («Sterlitamak. Ufim. gub» → Sterlitamak;
        # «Miedzyrzec, Siedl gub» → Miedzyrzec, the last chunk then), the chunk itself kept in the address
        # (a district too, «Mirgorods uj», «Aleksandrijsk. uj»: the ujezd's name no town)
        REGSUF = r"[\s.,]*(?:[A-ZÀ-Ž][\wÀ-ž]*[.)]?\s*)?\b(?:gub|gubernio|obl|prov|dep|distr|uj|ujezd|uezd)\.?\s*;?$"
        bare_ = {c: (re.sub(REGSUF, "", c, flags=re.I).strip(" .)") if re.search(REGSUF, c, re.I) else c) for c in rest}
        region = lambda c: not bare_.get(c, c)
        if any(bare_[c] != c for c in rest):
            keep_ = rest; rest = [bare_[c] for c in rest if bare_[c]]
            last = rest[-1] if rest else ""
        else: keep_ = None
        fallback = last if last and last[:1].isupper() and not re.search(r"\d", last) and len(last.split()) <= 3 and len(re.sub(r"\W", "", last)) > 4 and not region(last) else ""
        # (never a chunk opening in small letters, the next entry's: «Dublin ni Odessa», Fleming's, 1910 PDF 24)
        tchunk = next((c for c in reversed(rest) if c[:1].isupper() and not re.search(r"\d", c) and not region(c) and len(re.sub(r"\W", "", tbare(c))) > 3 and town_anywhere(tbare(c))), None)
        town = tbare(tchunk) if tchunk else fallback
        rest = [c for c in rest if c != (tchunk or fallback)]
        if keep_ is not None: rest = [c for c in keep_ if bare_[c] != (tchunk or fallback)]   # the regions back in the address
        # «Surname, Town, Region.» with no figure: the middle the town («Roblot, Charenton, Seine», 1909, Charenton taken
        # for his forename; the accuracy check of 2026-11-01)
        if len(chunks) == 3 and given and not re.search(r"\d", given + re.sub(r"[.\s]*\d+[.,]?\s*$", "", chunks[2])) and town_anywhere(tbare(given)) and re.fullmatch(r"[A-ZÀ-Ž][a-zà-ž'’-]{3,}(?:-[\wÀ-ž'’-]+)*", given):
            town, rest, given = tbare(given), [chunks[2]], ""
        # (the margin's letter or two before a town: «Kn Moskvo», 1910)
        km = re.match(r"^[A-ZÀ-Ž][a-z]?\s+([A-ZÀ-Ž][\wÀ-ž'’-]{3,}.*)$", town)
        if km and town_anywhere(tbare(km.group(1))) and not town_anywhere(tbare(town)): town = km.group(1)
        # a town broken at its hyphen with the margin's bar between («Var- | SOViO»), and its capitals mixed
        town = re.sub(r"-\s*\|?\s*(?=[A-Za-zÀ-ž])", "", town) if re.search(r"[a-z]-\s*\|?\s*[A-Za-z]", town) else town
        town = town[:1] + town[1:].lower() if re.search(r"[a-z][A-Z]{2,}", town) else town
        town = re.sub(r"\s+(?:[A-Z]\.?\s*){1,3}$", "", town).strip()
        # (the margin's junk after the town's period: «Moskvo. k», «Varsovio. ) up», 1910; 2026-11-01)
        town = re.sub(r"\.\s+[^A-Za-zÀ-ž]*[a-z]{0,3}[^A-Za-zÀ-ž]*$", "", town).strip()
        # (initials alone are no town: «S. E», London's South-East)
        if re.fullmatch(r"(?:[A-Z]\.?\s*)+", town): town = ""
        e.update({"country": country, "town": town, "region": "", "text": f"{sur} {given}, {', '.join(c for c in rest if c != town)}".replace(" ,", ",").strip(" ,")})
        keep.append(e)
    return keep, []

def entries_boul(item, a, b):
    """[{…, kongreso}] of the Boulogne congress-goers 1905; a home town where printed, else the congress's town."""
    pages = DX.page_lines(item)
    out, cur, began = [], None, False
    for p in range(a, b + 1):
        for n, l in pages.get(p, []):
            s = l.strip().replace("ĉ", "é").replace("MIle", "Mlle").rstrip(" J|")
            if not s or re.fullmatch(r"[\W\d]{1,6}|\w{1,2}", s): continue
            # (the surname and its comma too: «Brande, Antoinette, 63, …», «Bastoul, Hotel Dervaux»)
            i = flat_start(s, BSTART)
            if i is None: i = flat_start(s)
            # one entry a line: an entry's shape opens a new one unless the line before ends in a hyphen («…, J», «…. k»
            # the margin's junk after an entry, which ran Brande, Brunet, Bastoul and Bonnet together)
            if i is not None and (cur is None or not cur["raw"].rstrip().endswith("-")):
                began = True
                cur = {"pdf": p, "line": n, "raw": s[i:], "doubt": False}
                out.append(cur); continue
            if began and cur is not None and not cur["raw"].rstrip().endswith("."):
                cur["raw"] = (cur["raw"][:-1] + s) if cur["raw"].endswith("-") and s[:1].islower() else cur["raw"] + " " + s
    for e in out:
        raw = e["raw"].replace("Huet. Horace", "Huet Horace")
        hm = re.search(r"([A-ZÀ-Ž][\wÀ-ž'’ -]{2,30}?)\s*\(([^()]{2,30})\)\.?\s*$", raw)
        home = hm.group(1).strip() if hm and not re.search(r"\d", hm.group(1)) and (gz_known(hm.group(1).strip(), hm.group(2)) or town_anywhere(hm.group(1).strip())) else ""
        # … or «de X» («Brunet Ch., de Bordeaux, Hotel Dervaux»)
        dm = re.search(r"(?:^|,\s*)de\s+([A-ZÀ-Ž][\wÀ-ž'’-]+)", raw)
        if not home and dm and town_anywhere(dm.group(1)): home, hm = dm.group(1), None
        # … or a place as the entry's last chunk («…, London.», «…, villa Aimée, Le Portel.», «…, Paris.»: the accuracy
        # check of 2026-11-01 found them all «ĉe Boulogne-sur-Mer»); never a hotel's or a street's chunk
        if not home:
            lc = raw.rstrip(" .").rsplit(",", 1)
            lt = lc[1].strip() if len(lc) == 2 else ""
            if lt and lt[:1].isupper() and not re.search(r"\d|[Hh][oô]tel|\b(?:rue|r\.|place|pl\.|bd|av|quai|villa|chez)\b", lt, re.I) \
                    and len(lt.split()) <= 3 and town_anywhere(lt) and GZ.fold(lt) not in ("boulogne", "boulogne-sur-mer", "boulogne sur mer"):
                home, hm = lt, None
        e.update({"country": (GZ.pcountry(hm.group(2)) or "") if home and hm else "", "town": home or "Boulogne-sur-Mer", "region": "", "text": raw,
                  "kongreso": "Boulogne-sur-Mer 1905", "nojointown": not home})
    return out, []

# THE RUSSIAN ADDRESS BOOK 1914 (2026-10-31, the jarlibroj to-dos; *Ruslanda Adresaro II.*, part 1, П. И. Колышко,
# Petersburg, April 1914; born-digital, sources/born-digital-text/reu-adresar_ru_1914.txt): a paragraph a town, «Молога
# Ярославской губ. Романов Дмитрий Иванович (гимназист), Набережная.», the persons of a town after «;» or on lines of
# their own; surname, forename, patronymic, the occupation in brackets, the address. The roster is in one alphabet
# (runbook D1), so the name search cannot read it: each surname is spelt as the movement spelt Russian names in
# Esperanto (the Tutmonda's «Ŝirjaev», «Evstifejev») and looked up among the roster's labels, accents folded
CYR = dict(zip("абвгдезиклмнопрстуфцыэ", "abvgdeziklmnoprstufcie"), ж="ĵ", й="j", х="ĥ", ч="ĉ", ш="ŝ", щ="ŝĉ", ъ="", ь="",
           ё="jo", ю="ju", я="ja", і="i", ѣ="e", ѳ="f")
def translit(s):
    out = []
    for i, ch in enumerate(s):
        lo = ch.lower()
        t = CYR.get(lo, ch)
        # «е» after a vowel or at a word's start stays «e» (Evstifejev: «Евстифеев»), as the Tutmonda prints it
        if lo == "е" and i and s[i - 1].lower() in "аеиоуыэюяё": t = "je"
        # the soft sign before «е», «и» is «j» («Васильевич» Vasiljeviĉ, «Никитьевна» Nikitjevna); before «ё», «ю», «я»
        # their own «j» stands
        if lo == "ь" and i + 1 < len(s) and s[i + 1].lower() in "еи": t = "j"
        out.append(t.capitalize() if ch.isupper() and t else t)
    return "".join(out)
# (the type may be left out where a governorate or oblast follows: «Владивосток Приморской обл.»; run a took the town
# and its oblast for a person)
RTOWN = re.compile(r"^(?P<town>[А-ЯЁ][\w-]*(?:[\s-][А-ЯЁ][\w-]*)??)\s+(?:(?P<typ>г\.|с\.|село|ст\.|станица|станция|пос\.|посад|п\.\s*отд\.|д\.|дер\.|деревня|м\.|местечко|рудник|завод)\s*,?\s*)?"
                   r"(?P<gub>(?:[А-ЯЁ][\w.-]*\s+(?:губ|обл|у|уезда)[.\w]*\s*,?\s*){0,3})")
RPERSON = re.compile(r"^\s*(?P<sur>[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)\s+(?P<fore>[А-ЯЁ][а-яё]+)(?:\s+(?P<pat>[А-ЯЁ][а-яё]+(?:вич|вна|ична|ич|на)))?\b")

def entries_rus(path):
    """[{pdf, line, country, town, region, text, orig, doubt}] of the Russian address book; the headings."""
    out, heads, town, region = [], [], "", ""
    with open(path, encoding="utf-8") as fh: lines = [l.rstrip("\n") for l in fh]
    for n, l in enumerate(lines, 1):
        s = l.strip()
        if not s: continue
        m = RTOWN.match(s)
        if m and (m.group("typ") or m.group("gub").strip()) and RPERSON.match(s[m.end():]):
            town, region = translit(m.group("town")), translit(m.group("gub").strip(" ,."))
            heads.append((1, n, "town", f"{town} ({region})" if region else town)); s = s[m.end():]
        elif not RPERSON.match(s): continue
        for part in re.split(r";\s*", s):
            pm = RPERSON.match(part)
            if not pm: continue
            sur, fore, pat = translit(pm.group("sur")), translit(pm.group("fore")), translit(pm.group("pat") or "")
            occ = re.search(r"\(([^()]+)\)", part)
            rest = part[pm.end():]
            addr = re.sub(r"\([^()]*\)", "", rest).strip(" ,.;")
            text = f"{sur} {fore}{' ' + pat if pat else ''}, {translit(addr)}".strip(" ,") + "."
            out.append({"pdf": 1, "line": n, "country": "Rusio", "town": town, "region": region, "text": text, "orig": part.strip(),
                        "doubt": False, "occ_ru": occ.group(1) if occ else ""})
    return out, heads

# THE TUTMONDA'S OTHER MEMBER LISTS (2026-10-31; Ezri's list, item 5, the editor): 1907's members printed under each
# group (PDF 111–348, «: Grupanoj :» and the towns in capitals, «ANTOING,» / «Bottger Charles, korespondisto.»), and
# 1908–1910's «Internacia Korespondado» (country by country, the town opening its first entry: «Arles (B.-du-R.). Gilles
# Noël, terkulturisto, 18, r. Lagoy.», the next entries of the town without it). The reprinted Adresaro runs before them
# («ADRESARO DE LA ESPERANTISTOJ», the forenames in full) are not read, as settled for 1904–1907.
GRUP_RUNS = {1907: (111, 348)}
KOR_RUNS = {1908: (181, 192), 1909: (198, 221), 1910: (218, 249)}
GRUPANOJ = re.compile(r"Grupanoj", re.I)
# a group's own heading and officers end its members («fondita en Februaro 1903. — S. s., …», «— Pr., …»)
GROUPEND = re.compile(r"\bfondita\b|—\s*(?:Pr|Sek|Kas|S\.\s*s|J\.\s*k)\b|\bPrezidanto\b|\bSekretario\b")
CAPTOWN = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-ŽĈĜĤĴŜŬ][A-ZÀ-ŽĈĜĤĴŜŬ'’ -]{2,40}?)\s*(?:\((?P<reg>[^()]{1,40})\))?\s*[.,]?\W{0,3}$")
KORTOWN = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-Ž][\wÀ-ž'’-]*(?:[ -][\wÀ-ž'’-]+){0,4}?)\s*(?:\((?P<reg>[^()]{1,40})\))?\.\s+(?P<rest>[A-ZÀ-Ž].*)$")
KORHEAD = re.compile(r"INTERNACIA|KORESPONDADO")

def _ended(t):
    return bool(re.search(r"[.)!?]$", MARGIN.sub("", t.rstrip(" ;|]'’\"”"))))

def _add(out, cur, p, n, t, gap, base):
    """An entry begun, or the line run on into the one before: as entries() does, more simply."""
    if cur is not None and not gap and not (ENTRY.match(t) and _ended(cur["text"])):
        cur["text"] = (cur["text"][:-1] + t) if cur["text"].endswith("-") and t[:1].islower() else cur["text"] + " " + t
        return cur
    cur = dict(base, pdf=p, line=n, text=t, doubt=False)
    out.append(cur)
    return cur

def entries_grup(item, a, b):
    """[{pdf, line, country, town, region, text, section}] of 1907's «Grupanoj» sections; the headings read."""
    pages = DX.page_lines(item)
    # each section's group, the last above it as the societies parser reads them: its town the members' own until a
    # town heading says otherwise (half the members had none: those of the group's own town)
    groups = sorted((g["line"], g) for g in DX.entries(pages, [(a, b)], False))
    out, heads, country, town, region, cur, gap, on, sec, gtown = [], [], "", "", "", None, True, False, "inter la grupanoj", ""
    for p in range(a, b + 1):
        for n, l in pages.get(p, []):
            s = l.strip()
            if not s: gap = True; continue
            t = DX.lead(s); was_gap, gap = gap, False
            if RUNHEAD.search(t) or OJ.junk(t): continue
            if GRUPANOJ.search(t):
                g = next((g for ln, g in reversed(groups) if ln < n), None)
                on, region, cur = True, "", None
                town = (g or {}).get("town") or ""
                # only a town the gazetteer knows («Tie» for Warsaw's society, the sample of tag g: Zamenhof «ĉe Tie»)
                if town and not (gz_known(town, country) or town_anywhere(town)): town = ""
                gtown = town
                name = re.sub(r"\s+", " ", (g or {}).get("group") or "").strip(" ,;.|")
                sec = f"inter la grupanoj de {name}" if name else "inter la grupanoj"
                heads.append((p, n, "grupanoj", f"{name or '?'} / {town or '?'}")); continue
            c = re.sub(r"[^A-ZÀ-ŽĈĜĤĴŜŬ -]", "", t).strip()
            if t.upper() == t and len(c.replace(" ", "")) >= 3 and not re.search(r"\d", t):
                new = country_of(c, country)
                if new:
                    if new != country: country = new; heads.append((p, n, "country", new))
                    cur = None; continue
            if not on: continue
            if GROUPEND.search(t): on, cur = False, None; continue
            # a town in capitals, one letter or two misread small («ANvERS (Antverpen).», PDF 160)
            m = re.match(r"^\W{0,3}(?P<town>[A-ZÀ-ŽĈĜĤĴŜŬ][\wÀ-ž'’ -]{2,40}?)\s*(?:\((?P<reg>[^()]{1,40})\))?\s*[.,]?\W{0,3}$", t)
            lt = re.sub(r"[^A-Za-zÀ-ž]", "", m.group("town")) if m else ""
            if m and len(lt) >= 3 and sum(ch.isupper() for ch in lt) >= 0.75 * len(lt) and "," not in m.group("town"):
                town, region, cur = m.group("town").strip(" .,-").title(), (m.group("reg") or "").strip(), None
                # «TIE» («there»): back to the group's own town after a member from elsewhere (Warsaw's society, PDF 311:
                # «ABlumental …, Pinsk (Rusujo).» / «TIE» / «Blumental …, Marszalkowska, 77.»)
                if town.lower() == "tie": town = gtown
                heads.append((p, n, "town", town)); continue
            # … or in small letters with its region, after an entry ended, a town of the gazetteer's («Sèvres (Seine-et-
            # Oise).», PDF 222: Benoit's household kept SENLIS above it; the accuracy check of 2026-11-01)
            mt = TOWNH.match(HEADJUNK.sub(".", MARGIN.sub("", t)))
            if mt and mt.group("reg") is not None and (cur is None or _ended(cur["text"])) and "," not in mt.group("town") \
                    and not re.search(r"\d", t) and is_town(mt.group("town").strip(" ."), mt.group("reg"), country) \
                    and (gz_known(mt.group("town").strip(" ."), country) or REGABBR.fullmatch(mt.group("reg"))):
                town, region, cur = mt.group("town").strip(" .,-"), mt.group("reg").strip(), None
                heads.append((p, n, "town", town)); continue
            cur = _add(out, cur, p, n, t, was_gap, {"country": country, "town": town, "region": region, "section": sec})
    return out, heads

def entries_kor(item, a, b):
    """[{pdf, line, country, town, region, text, section}] of the «Internacia Korespondado» list; the headings read."""
    pages = DX.page_lines(item)
    out, heads, country, town, region, cur, gap = [], [], "", "", "", None, True
    for p in range(a, b + 1):
        for n, l in pages.get(p, []):
            s = l.strip()
            if not s: gap = True; continue
            t = DX.lead(s); was_gap, gap = gap, False
            if RUNHEAD.search(t) or KORHEAD.search(t) or OJ.junk(t): continue
            c = re.sub(r"[^A-ZÀ-ŽĈĜĤĴŜŬ -]", "", t).strip()
            if t.upper() == t and len(c.replace(" ", "")) >= 3 and not re.search(r"\d", t):
                new = country_of(c, country)
                if new and new != country: country, town, region = new, "", ""; heads.append((p, n, "country", new))
                cur = None; continue
            m = KORTOWN.match(t)
            if m and (cur is None or _ended(cur["text"]) or was_gap) and is_town(m.group("town").strip(), m.group("reg"), country):
                town, region = m.group("town").strip(), (m.group("reg") or "").strip()
                heads.append((p, n, "town", town + (f" ({region})" if region else "")))
                cur = _add(out, None, p, n, m.group("rest"), True, {"country": country, "town": town, "region": region, "section": "en la Internacia Korespondado"})
                continue
            cur = _add(out, cur, p, n, t, was_gap, {"country": country, "town": town, "region": region, "section": "en la Internacia Korespondado"})
    return out, heads

def roster_hits(item):
    """The name search's hits, for a book in another alphabet: every roster label by its search key, accents folded,
    on the book's one page («exact»)."""
    by = collections.defaultdict(dict)
    with open(os.path.join(DX.G, "dowse", "ROSTER-FULL-CROSS-ARC-2026-10-29.txt"), encoding="utf-8") as fh:
        for l in fh:
            if l.startswith("#") or not l.strip(): continue
            label, _, key = l.strip().partition(" | ")
            by[DX.norm(key or label)][label] = "exact"
    return {(item, 1): by}

def judge(a, hits, item, e, bparse):
    """(surname, the rest of the name, the chunks, label, verdict, how, candidates) of one entry."""
    sur, given, rest = bparse(e["text"])
    tm = POLTITLE.search(given) if a.book == "pola-1909" else None
    if tm: given, rest = given[:tm.start()].strip(), [given[tm.start():].strip()] + rest
    label, how, cands = "", "", ""
    # a surname that is a particle is no name read («San Antonio», a line of «San Antonio Angel Molina, Juan» cut off)
    if not sur or (a.book == "hispana-1906" and sur.lower() in HPART): verdict = "held: la nomo ne legebla"
    # A WIFE PRINTED BY HER HUSBAND'S NAME («Benoit (S° René)», «Glénat (Sie)», «Caby (S!no)»: Sinjorino; 1907 PDF 222,
    # Mrs Benoit's address went to René BENOIT; the accuracy check of 2026-11-01): never joined to his profile
    elif WIFE.match(given.strip()): verdict = "held: sinjorino (edzino)"
    # a firm, its partners after «et» («Dupuis et Lussier, advokatoj», «Spineux et Cie»: the samples of p and q)
    elif re.match(r"^(?:et|&|kaj|and|und|y|e|u\.)\s", given): verdict = "held: firmao"
    elif not e["town"]: verdict = "held: sen urbo"
    # a doubtful town bears nothing out (Garcia «borne out» by «Vicente», run t's sample)
    else:
        # (nor the congress's town, which half the roster's profiles name: Boulogne)
        label, verdict, how, cands = join(hits, item, e["pdf"], sur, given, "" if e["doubt"] or e.get("nojointown") else e["town"])
        # two Spanish surnames not a roster name whole: the first, the father's, as the roster names a Spaniard (the
        # first surname alone is common, so only the town bears it out: a forename as common as José proved nothing for
        # GARCIA, the Hispana's run a; and never a particle: «San Antonio …» went to ŜAN)
        if a.book == "hispana-1906" and verdict == "ne en la nomaro" and len(sur.split()) > 1 and sur.split()[0].lower() not in HPART:
            label, verdict, how, cands = join(hits, item, e["pdf"], sur.split()[0], "", e["town"])
            if label and not how.startswith("la urbo"): label, verdict = "", "held: nur la familia nomo"
    return sur, given, rest, label, verdict, how, cands

def books(name, years):
    """[(year, item, key, entries(a, b), (a, b))] of a book, the title its lines name, its folder, its date note."""
    if name == "pola-1909":
        it = "reu-pola-adresaro-1909"
        return ([(1909, it, it, lambda a_, b_: entries_pola(it, a_, b_), (1, 65))], "Adresaro de Polaj Esperantistoj",
                os.path.join(DX.G, "dowse", "pola-adresaro-1909"), "la jaro de la adresaro", parse)
    if name == "ruslanda-1914":
        it = "reu-adresar_ru_1914"
        return ([(1914, it, "reu-adresar-ru-1914", lambda a_, b_: entries_rus(os.path.join(DX.G, "sources", "born-digital-text", it + ".txt")), (1, 1))],
                "Ruslanda Adresaro", os.path.join(DX.G, "dowse", "ruslanda-adresaro-1914"), "la jaro de la adresaro", parse)
    if name == "teka-1909-1910":
        return ([(1909, "ANNO_e7i_19090005", "teka-jarlibro-1909-anno-0005", lambda a_, b_: entries_teka("ANNO_e7i_19090005", a_, b_, 1909), (1, 97)),
                 (1910, "ANNO_e7i_19100005", "teka-jarlibro-1910-anno-0005", lambda a_, b_: entries_teka("ANNO_e7i_19100005", a_, b_, 1910), (1, 83))],
                "Jarlibro de Tutmonda Esperantista Kuracista Asocio", os.path.join(DX.G, "dowse", "teka-jarlibro"), "la jaro de la jarlibro", parse)
    if name == "boulogne-1905":
        it = "Adresaro de la kongresanoj en Boulogne-sur-Mer 1905"
        return ([(1905, it, "adresaro-de-la-kongresanoj-en-boulogne-sur-mer-1905", lambda a_, b_: entries_boul(it, a_, b_), (9, 29))],
                "Adresaro de la kongresanoj en Boulogne-sur-Mer", os.path.join(DX.G, "dowse", "boulogne-kongresanoj-1905"), "la jaro de la adresaro", parse)
    if name == "annuaire-1901":
        it = "Annuaire"
        return ([(1901, it, "annuaire", lambda a_, b_: entries_annu(it, a_, b_), (34, 85))], "Annuaire de la Société pour la propagation de l'Esperanto",
                os.path.join(DX.G, "dowse", "annuaire-1901"), "la jaro de la jarlibro", parse)
    if name == "hispana-1906":
        it = "HispanaJarlibro.1906"
        return ([(1906, it, "hispanajarlibro-1906", lambda a_, b_: entries_hisp(it, a_, b_), (33, 76))], "Hispana Jarlibro",
                os.path.join(DX.G, "dowse", "hispana-jarlibro-1906"), "la jaro de la jarlibro", parse_hisp)
    if name in ("tutmonda-grupanoj-1907", "tutmonda-korespondado"):
        runs, fn = (GRUP_RUNS, entries_grup) if name == "tutmonda-grupanoj-1907" else (KOR_RUNS, entries_kor)
        ys = [y for y in years if y in runs] or sorted(runs)
        return ([(y, DX.ITEM.format(y=y), DX.KEY.format(y=y), (lambda it: lambda a_, b_: fn(it, a_, b_))(DX.ITEM.format(y=y)), runs[y])
                 for y in ys], "Tutmonda Jarlibro Esperantista", DEST, "la jaro de la jarlibro", parse)
    return ([(y, DX.ITEM.format(y=y), DX.KEY.format(y=y), (lambda it: lambda a_, b_: entries(it, a_, b_))(DX.ITEM.format(y=y)), RUNS[y])
             for y in years], "Tutmonda Jarlibro Esperantista", DEST, "la jaro de la jarlibro", parse)

TITLECHUNK = re.compile(r"^(?:D-?r[oa]?|Dr|Dre|Prof|M-bro|Membro|stud)\b\.?")
STUDYRUN = re.compile(r"^(stud\.?(?:\s+(?:de|d['’])\s*[a-zà-žĉĝĥĵŝŭ]+)?)\s+([A-ZÀ-Ž]\S*.*\d.*)$")

MARKED = re.compile(r"\*\*\(([^)]{1,40})\)\*\*|^- \$\$\$ [^$]+\$\$\$ \(([^)]{1,60})\)")

def subject_forenames(label, firsts):
    """Of the forenames (folded) claiming a profile whose heading has none, the first three letters of the one the
    profile prints before its surname, in lines marking no other person, at least 3 times more than it marks it as
    another person's, where every other forename's score is at most a third of it (Leon ↔ Leono, Ludwik ↔ Ludoviko by
    their first three letters; RUIZ's Ramón 5 against Luis 2 stays held, a profile of two men)."""
    head, t, _hp = DX.profile(label)
    sur = GZ.fold(head)
    marks, plain = collections.Counter(), collections.Counter()
    for l in t.split("\n"):
        if not l.startswith("- $$$"): continue
        ms = [m.group(1) or m.group(2) for m in MARKED.finditer(l)]
        for s in ms:
            w = re.match(r"[A-Za-zÀ-ž]{3,}", s)
            if w: marks[GZ.fold(w.group(0))[:3]] += 1
        if ms: continue
        for m in re.finditer(r"\b([A-ZÀ-Ž][a-zà-ž]{2,})\s+(?:[A-Z]\.\s*)*([A-ZÀ-Ž][\wÀ-ž'’-]+)", l):
            if GZ.fold(m.group(2)) == sur: plain[GZ.fold(m.group(1))[:3]] += 1
    score = {f[:3]: plain[f[:3]] - marks[f[:3]] for f in firsts}
    best = max(score, key=score.get)
    if score[best] < 3 or any(s * 3 > score[best] for f, s in score.items() if f != best): return set()
    return {best}

def extract(a):
    years =[int(y) for y in a.years.split(",")] if a.years else sorted(RUNS)
    vols, title, dest, datenote, bparse = books(a.book, years)
    if a.show:
        for y, item, key, ent, rng in vols:
            es, heads = ent(a.show, a.show)
            for p, n, k, h in heads: print(f"{y} PDF {p} l. {n} · {k}: {h}")
            for e in es:
                sur, given, rest = bparse(e["text"])
                print(f"{y} PDF {e['pdf']} l. {e['line']} · {e['country']} / {e['town']} · «{sur}» «{given}» · {rest} [{e['text'][:70]}]")
        return
    if a.countries:
        for y, item, key, ent, rng in vols:
            _es, heads = ent(*rng)
            for i, (p, n, k, h) in enumerate(heads):
                # a town heading in capitals is a country's misread
                if k != "country" and not (h.upper() == h and len(re.sub(r"\W", "", h)) >= 3): continue
                after = [x[3] for x in heads[i + 1:] if x[2] == "town"][:3]
                print(f"{y} PDF {p} l. {n} · {h} → " + " | ".join(after))
        return
    if a.towns:
        for y, item, key, ent, rng in vols:
            es, heads = ent(*rng)
            under = collections.Counter((e["line"] > 0) and (e["country"], e["town"]) for e in es)
            for p, n, k, h in heads:
                if k != "town" or len(h.split()) != 1: continue
                cs = [c for (c, t) in under if t == h] or [""]
                known = gz_known(h, cs[0])
                print(f"{y}\tPDF {p}\tl. {n}\t{'known' if known else 'unknown'}\t{'period' if RAW.get((y, n), '').rstrip().endswith('.') else 'no-period'}\t{h}\t{RAW.get((y, n), '')}")
        return
    if not ((a.hits or a.book == "ruslanda-1914") and a.tag): sys.exit("--hits and --tag are needed")
    # (--outdir: the three files written there instead, a test of the tool itself; 2026-11-01)
    outs = {k: os.path.join(a.outdir or dest, f) for k, f in (("ret", f"facts-return-{a.tag}-members.md"), ("tsv", f"members-{a.tag}.tsv"), ("rev", f"MEMBERS-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    # (a book in another alphabet: the roster looked up directly, see roster_hits)
    hits = roster_hits(vols[0][1]) if a.book == "ruslanda-1914" else OJ.load_hits(a.hits, [v[1] for v in vols])
    rows, lines, allheads, cnt = [], [], [], collections.Counter()
    read = []
    for y, item, key, ent, rng in vols:
        es, heads = ent(*rng)
        read.append((y, item, key, es))
        allheads += [(y,) + h for h in heads]
        cnt["towns"] += sum(1 for h in heads if h[2] == "town")
        DX.SELF_KEY = key   # this volume's own tool lines bear nothing out (directory-extract.py borne_out, 2026-11-01)
        for e in es: e["j"] = judge(a, hits, item, e, bparse)
    # NAMESAKES IN ONE TOWN: entries of different forenames joined to one profile in one town by the town alone are held,
    # all of them (2026-10-31, the Hispana: «Gimeno, R. P. Vicente», «Gimeno Puchades, Miguel», «Gimeno Ventura, Felipe»
    # all went to GIMENO by Valencia)
    # (in one volume: across volumes the same person's forename is printed «H.» one year and «Henri» the next)
    byk = collections.defaultdict(set)
    for y, _i, _k, es in read:
        for e in es:
            sur, given, rest, label, verdict, how, cands = e["j"]
            if label and how.startswith("la urbo"): byk[(y, label, e["town"])].add(bare(given) or "?")
    clash = {k for k, gs in byk.items() if len(gs) > 1}
    # ONE PROFILE, SEVERAL FORENAMES IN ONE VOLUME, by any evidence (T.E.K.A. 1909: Ludwik, Leon, Aleksander and Henryk
    # Zamenhof all joined to ZAMENHOF, Ludwik's profile naming his brothers): only the entry whose forename stands in the
    # profile's own heading keeps the join, where exactly one does; else all are held
    byl = collections.defaultdict(list)
    for y, _i, _k, es in read:
        for e in es:
            sur, given, rest, label, verdict, how, cands = e["j"]
            if label and re.match(r"[A-ZÀ-Ž][a-zà-ž]{2,}", given.strip("( ")): byl[(y, label)].append(e)
    for (y, label), group in byl.items():
        firsts = {GZ.fold(re.match(r"[\wÀ-ž'’-]+", e["j"][1].strip("( ")).group(0)) for e in group}
        if len(firsts) < 2: continue
        head = GZ.fold(DX.profile(label)[0] or "")
        own = [e for e in group if re.search(r"\b" + re.escape(GZ.fold(re.match(r"[\wÀ-ž'’-]+", e["j"][1].strip("( ")).group(0))) + r"\b", head)]
        # a heading with no forename (ZAMENHOF): the subject's forename is the one the profile prints before the surname
        # unmarked more often than it marks it as another person's («**(Leono)**»); 2026-10-31, item 7: Ludwik 98 against
        # 19, Leon 117 against 293, Aleksander 4 against 8, Henryk 0 (counting forenames alone gave Leon the join)
        if not own and len(head.split()) == 1:
            subj = subject_forenames(label, firsts)
            if len(subj) == 1: own = [e for e in group if GZ.fold(re.match(r"[\wÀ-ž'’-]+", e["j"][1].strip("( ")).group(0))[:3] in subj]
        for e in group:
            if not (len(own) == 1 and e is own[0]):
                j = list(e["j"]); j[3], j[4] = "", "held: samnomuloj en la volumo"; e["j"] = tuple(j)
    for y, item, key, es in read:
        for e in es:
            cnt["entries"] += 1
            sur, given, rest, label, verdict, how, cands = e["j"]
            if label and how.startswith("la urbo") and (y, label, e["town"]) in clash: label, verdict = "", "held: samnomuloj en la urbo"
            cnt[verdict] += 1
            rows.append([y, e["pdf"], e["line"], e["country"], e["town"], sur, given, " | ".join(rest), cands, verdict])
            if not label: continue
            head, _t, hp = DX.profile(label)
            # a double surname joined whole: its second word is the surname's, not the forename's («Castillo Munoz»)
            nxt = re.match(r"[A-ZÀ-Ž][\wÀ-ž'’-]+", given.strip("( "))
            if nxt and bare(label) == bare(sur + nxt.group(0)) and bare(label) != bare(sur):
                sur, given = f"{sur} {nxt.group(0)}", given.replace(nxt.group(0), "", 1).strip()
            loc =f"{key}, PDF {e['pdf']}, l. {e['line']}"
            # (the anchor as printed: the Russian book's Cyrillic, not its transliteration)
            aw = e.get("orig", e["text"]).split()[:12]
            anc = " ".join(aw + ["⟨fino⟩"] * max(0, 6 - len(aw)))
            thin = how.startswith("la inicialoj") and len(how.split()) == 3
            tk, tshown, tnote = town_key(e["town"], e["country"], e["region"])
            # a doubtful town (see entries): no residence, no «ĉe», the doubt named
            if e["doubt"]: tnote = f"; ⟦la urbo ne certa: la kaplinio «{e['town']}», urbo nek de la loknomaro nek de eo.wikipedia⟧"; cnt["doubtful town"] += 1
            conf =f"📣{' ❓' if thin else ''} (sen fontindiko; ⟦{datenote}⟧; ⟦identigo: {head}, laŭ {how} en la profilo⟧{tnote})"
            shown = DX.clean_name(f"{sur}, {given}" if re.fullmatch(r"(?:[A-ZÀ-Ž][a-zà-ž]{0,2}\.\s*-?){1,3}", given) else f"{given} {sur}".strip()) or sur
            # (and the OCR's square brackets, «[ Dasqué P. Butel», «[Fo Renou»: a bracket after « · » opens the themes, so
            # the format check took four lines of 2026-10-31o for malformed; 2026-11-01)
            shown = re.sub(r"[()\[\]\"“”»«°'’]", "", shown).replace("  ", " ").strip()
            # a misread title before the forename left off («Fire M. Bernard», F^ino), and an initial's period restored
            # («L Dubost», «O. J Stenborg»: clean_name strips the last period)
            # (and in small letters: «fino Guérin», run p's sample; the title's own shapes only, so «Fred» stays)
            shown = re.sub(r"^(?:[Ff](?:ino|ine|ire|in|ie|i|e|o|0|uo|ue)?|Fi\S{0,2}|Siw|Sino|Simo|Siuo|S-ro|S-ino|So|Si|Sin|D|Dre|Dro|Pro|Pio|Mme|Mlle|Mrs|Miss)\s+(?=[A-ZÀ-Ž])", "", shown)
            # («Mlle», «Mme» inside the name, after the forename: «Germaine Mlle Dupont», Boulogne)
            shown = re.sub(r"\s+(?:Mlle|Mme|Mlles|Mmes)\b\.?", "", shown)
            shown = re.sub(r"\b([A-ZÀ-Ž])(?=\s+[A-ZÀ-Ž])", r"\1.", shown)
            if e.get("suffix"): shown += f" {e['suffix']}"
            # a committee's officer: the office alone, as directory-extract.py writes the Tutmonda's
            if e.get("office"):
                cnt["officers"] += 1
                lines.append(f"- $$$ {hp} **{y}** · {{ofico: {e['office']}, {e['body']}}} · {shown} estas {e['office']} de la {e['body']}. · {anc} · {loc} · [G] · {conf}")
                continue
            at = "" if e["doubt"] else f", ĉe {tshown}"
            sec = e.get("section", "")
            lines.append(f"- $$$ {hp} **{y}** · {{aperoj: {title} {y}{', ' + sec if sec else ''}}} · {shown} aperas en la *{title}* de {y}{' ' + sec if sec else ''}{at}. · {anc} · {loc} · [G] · {conf}")
            # the Annuaire's category, by the book's own key, and the I.K.E.'s number
            if e.get("cat"):
                lines.append(f"- $$$ {hp} **{y}** · {{aliĝo: Société pour la propagation de l'Esperanto, kiel {e['cat']}}} · {shown} estas {e['cat']} de la Société pour la propagation de l'Esperanto. · {anc} · {loc} · [G] · {conf}")
            if e.get("ike"):
                lines.append(f"- $$$ {hp} **{y}** · {{aliĝo: Internacia Korespondado Esperanta, n-ro {e['ike']}}} · {shown} estas ano de la Internacia Korespondado Esperanta (n-ro {e['ike']}). · {anc} · {loc} · [G] · {conf}")
            # T.E.K.A.'s membership; Boulogne's congress
            if e.get("aligo"):
                lines.append(f"- $$$ {hp} **{y}** · {{aliĝo: {e['aligo']}}} · {shown} estas ano de la {e['aligo']}. · {anc} · {loc} · [G] · {conf}")
            if e.get("kongreso"):
                lines.append(f"- $$$ {hp} **{y}** · {{kongreso: {e['kongreso']}}} · {shown} estis kongresano en {e['kongreso'].replace(' 1905', '')} en 1905. · {anc} · {loc} · [G] · {conf}")
            # A TITLE OR A STUDY BEFORE THE ADDRESS («D-ro, Grzybowska 15», «D-ro med. Priv Docento de Krakova Universitato,
            # str. Wielopole 8», «stud. de ĥemio Platterstr. 88», the Polish Adresaro; the accuracy check of 2026-11-01): a
            # title or a membership without a figure no part of the address; a study run into the street split from it
            rest = [x for r in rest for x in ((lambda m: [m.group(1), m.group(2)] if m else [r])(STUDYRUN.match(r.strip())))]
            occ = [r.strip(" .;:") for r in rest if OJ.occupation(r)]
            # (a house number of one figure kept, as in oficiala-jarlibro-extract.py: the check of 2026-11-01, its lines 10, 21)
            addr = [r for r in rest if not OJ.occupation(r) and not DX.DEGREE.match(r.strip())
                    and (len(re.sub(r"[^A-Za-zÀ-ž0-9]", "", r)) >= 2 or re.fullmatch(r"\s*\d\s*", r))
                    and not (TITLECHUNK.match(r.strip()) and not re.search(r"\d", r))]
            # … and an occupation in the book's own language before the address no part of it («Estudiante, calle …»,
            # «avocat, 12, r. …»: the Hispana's and the Annuaire's residence lines; the accuracy check of 2026-11-01): the
            # chunks before the first with a figure or a street's word, of three words at most or in small letters, left off;
            # a bare house number with no street after it follows its street («…, Ateneo de Madrid, Canillas, 4.»: Andreu,
            # the Annuaire), the street in capitals before it; not «architecte, 55, rue des Drapiers», «ingénieur, 12, quai …»
            first = next((i for i, r in enumerate(addr) if re.search(r"\d", r) or DX.ADDR.search(r)), None)
            if (first and re.fullmatch(r"\s*\d+\s*\.?\s*", addr[first]) and addr[first - 1].strip()[:1].isupper()
                    and not (first + 1 < len(addr) and (DX.ADDR.search(addr[first + 1]) or addr[first + 1].strip()[:1].islower())
                             and not re.match(r"\s*(?:pral|izq|der|dcha|bajo|entlo|piso)\b", addr[first + 1]))):   # «Bolsa, 6, pral.»
                first -= 1
            if first: addr = [r for i, r in enumerate(addr) if i >= first or (len(r.split()) > 3 and not r.strip()[:1].islower())]
            # (a figure alone no address: «Bousquet, helpanta profesoro ĉe la liceo, 2,», its street on a line not joined)
            # (the OCR's junk at the address's end and a stray letter before its number: «6, r. Caraman. ].», «i 132, Bd
            # Montparnasse. .y.»: the re-check of 2026-11-01c, lines 1 and 29)
            addr = [re.sub(r"^[a-z]\s+(?=\d)", "", r) for r in addr]
            if addr: addr[-1] = re.sub(r"(?:\s+(?:[\]\[|}{)(]+\.?|\.?[a-z]\.?|\.\w{1,2}\.))+\s*$", "", addr[-1])
            where = (f", {', '.join(addr).strip(' .;:|[')}" if addr and any(re.search(r"\d", r) or DX.ADDR.search(r) for r in addr)
                     and re.search(r"[A-Za-zÀ-ž]{3}|\bP\.\s?O\.\s?B\b", " ".join(addr)) else "")   # «Kamloops, P. O. B., 185»
            # (a congress-goer's hotel is no residence)
            if not e["doubt"] and not e.get("nojointown"):
                lines.append(f"- $$$ {hp} **{y}** · {{loĝado: {tk}}} · {shown} loĝas en {tshown}{where}. · {anc} · {loc} · [?] · {conf}")
            for o in occ:
                lines.append(f"- $$$ {hp} **{y}** · {{profesio: {o}}} · {shown} estas {o}. · {anc} · {loc} · [?] · {conf}")
    cnt["lines"] = len(lines)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    if a.outdir: os.makedirs(a.outdir, exist_ok=True)
    with open(outs["tsv"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["year", "pdf", "line", "country", "town", "surname", "the rest of the name", "the rest", "roster hits (borne out by)", "verdict"]); w.writerows(rows)
    with open(outs["ret"], "x", encoding="utf-8") as fh:
        src = f"the name search {os.path.basename(a.hits)}" if a.hits else "the roster's labels looked up directly (another alphabet: the surnames transliterated)"
        fh.write(f"# Return: facts-return-{a.tag}-members.md\n\n`[Written by tools/jarlibro-members.py extract, {a.tag}, from {src}: the members by town of the {title}, {', '.join(str(v[0]) for v in vols)}, roster persons only, each borne out by the profile (runbook D4c). Not a legilo's return.]`\n\n")
        fh.write("\n".join(lines) + "\n")
    held = [r for r in rows if r[9].startswith("held")]
    with open(outs["rev"], "x", encoding="utf-8") as fh:
        fh.write(f"# The members by town of the *{title}*, read by tool ({a.tag})\n\n`[GENERATED by tools/jarlibro-members.py extract. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". Every entry parsed: `{os.path.basename(outs['tsv'])}`; the lines: `{os.path.basename(outs['ret'])}`.\n\n")
        fh.write(f"## The headings read: {len(allheads)}\n\n" + "".join(f"- {y}, PDF {p}, l. {n} · {k}: {h}\n" for y, p, n, k, h in allheads))
        fh.write(f"\n## Held: {len(held)}\n\n")
        for r in held: fh.write(f"- {r[0]}, PDF {r[1]}, l. {r[2]} · {r[4] or '?'} ({r[3]}) · «{r[5]} {r[6]}» · {r[8]} · {r[9]}\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

# an entry's first line: the OCR's mark (the «véra esperantisto» asterisk from 1906, read «*», «“», «”» …), a surname,
# then initials, a forename or a title in brackets, then a comma: «Dubois G., 21, r. Beaubourg.», «Dumas (Fi° Louise), 6, …»
ENTRY = re.compile(r"^[\W\d]{0,3}\s*[A-ZÀ-Ž][\wÀ-ž'’-]+(?:[ -](?:de |van |von |la |le |du |da |di |del )?[A-ZÀ-Ž][\wÀ-ž'’-]+)?"
                   r"\s*(?:\([^)]{1,40}\)|(?:[A-ZÀ-Ž][a-zà-ž]{0,2}\.\s*){1,3}|[A-ZÀ-Ž][a-zà-ž]+(?:[ -][A-ZÀ-Ž][a-zà-ž]+)?)?\s*,")

def inspect(years):
    for y in years:
        pages = DX.page_lines(DX.ITEM.format(y=y))
        soc = {p for a, b in DX.PARTS[y] for p in range(a, b + 1)}
        counts = {p: sum(1 for n, t in ls if ENTRY.match(t.strip())) for p, ls in pages.items() if p not in soc}
        runs, cur = [], None
        for p in sorted(counts):
            if counts[p] >= 8:
                if cur and p == cur[1] + 1: cur[1] = p; cur[2] += counts[p]
                else: cur = [p, p, counts[p]]; runs.append(cur)
        print(f"## {y}: {len(pages)} pages; member runs (8 entries a page or more): "
              + ", ".join(f"PDF {a}–{b} ({n})" for a, b, n in runs))
        for a, b, n in runs:
            heads = []
            for p in range(a, b + 1):
                for m, t in pages.get(p, []):
                    c = DX.lead(t.strip()).strip(" .,:;|—-")
                    if c and not ENTRY.match(t.strip()) and len(c.split()) <= 3 and len(re.sub(r"\W", "", c)) >= 3 \
                            and (c.isupper() or re.match(r"^[A-ZÀ-Ž][a-zà-ž'’-]+(?:[ -][A-ZÀ-Ž]?[a-zà-ž'’-]+){0,2}\.?$", c)) \
                            and not re.search(r"\d", c):
                        heads.append(f"{p}:{c}")
            print(f"   PDF {a}–{b}: {len(heads)} heading candidates; first 40: " + " | ".join(heads[:40]))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["inspect", "extract"]); ap.add_argument("--years")
    ap.add_argument("--book", default="tutmonda", choices=["tutmonda", "tutmonda-grupanoj-1907", "tutmonda-korespondado", "pola-1909", "hispana-1906", "annuaire-1901", "teka-1909-1910", "boulogne-1905", "ruslanda-1914"], help="extract: the Tutmonda's members 1904–1907 (the default), the Polish address book 1909, or the Hispana Jarlibro 1906")
    ap.add_argument("--hits"); ap.add_argument("--tag"); ap.add_argument("--write", action="store_true")
    ap.add_argument("--outdir", help="extract --write: write the three files here instead (a test of the tool itself)")
    ap.add_argument("--show", type=int, help="extract: print the headings and entries of this PDF page of each year, and stop")
    ap.add_argument("--towns", action="store_true", help="extract: print each one-word town heading, whether the gazetteer knows it and whether it ends in a period, and stop")
    ap.add_argument("--countries", action="store_true", help="extract: print each country heading with the first three towns after it, and stop")
    a = ap.parse_args()
    if a.mode == "inspect": inspect([int(y) for y in (a.years or ",".join(map(str, DX.PARTS))).split(",")])
    if a.mode == "extract":
        a.years = a.years or ",".join(map(str, RUNS))
        extract(a)

if __name__ == "__main__":
    main()
