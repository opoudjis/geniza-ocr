#!/usr/bin/env python3
"""The gazetteer: the authority file for places (the editor, 2026-10-29 14:2x: town garblings resolved, Tŭbingen as
Tübingen, by a gazetteer with national-language and Esperanto entries, from the Esperanto Wikipedia on disk). One row a place: its Esperanto name, its national-language names, its
country, the Wikidata id where a source gives one, and every form our sources print for it, so that a tool files a person
under one place however the print or the OCR spells it.

    tools/gazetteer.py eowiki --dump EOWIKI-…-pages-articles.xml.bz2 [--limit N]
    tools/gazetteer.py build --tag TAG [--write]
    tools/gazetteer.py look FORM [--country COUNTRY]

eowiki: one pass over eo.wikipedia's dump (sources/web-2026-10-14-scope-register/, the dump of 2026-10-01) into
profiles/gazetteer/: EOWIKI-PLACES-‹date›.tsv, every article in a category of places («Urboj en …», «Komunumoj de …»,
«Vilaĝoj …») or with a place's infobox: the title (the Esperanto name), the national-language names from the lead
(«'''Tubingo''' (germane ''Tübingen'')») and the infobox («originala nomo = …»), the country (from the categories, else the
lead's first link to a country), the categories; EOWIKI-REDIRECTS-‹date›.tsv, every redirect (the other forms: «Tübingen»
→ «Tubingo»). Written as it reads, with a .progress file; create-only.

build: the places our sources print, joined to eo.wikipedia's: (1) Zamenhof's Adresaro, the Wikisource transcription's
towns, a place a Wikidata id (u=Q…, so the transcription's own forms of one place stand together); (2) the Oficiala
Jarlibro 1911–1914's town lines («Aachen (Germanujo, Rheinland)»). A printed form is joined to an article where it folds
(accents off, the OCR's commonest confusions undone: «ii» for «ü», «rn» for «m») to the title, a national-language name
or a redirect of ONE article in the same country (Manchester in Anglujo is not Manchester in Usono; the period's states
held as the modern ones they cover: Rusujo is Russia, Poland, Finland, the Baltic and the Caucasus); else it stands as a
place of its own, unjoined, for the review. Writes profiles/gazetteer/GAZETTEER-TAG.tsv (one row a place),
GAZETTEER-FORMS-TAG.tsv (one row a printed form, its country and id, and the place it joins: what the directories' tools
read, `forms(TAG)`) and GAZETTEER-REVIEW-TAG.md, create-only; without --write the counts.

look: the place a form resolves to, and why (for the directories' tools: `resolve()` is importable). Ezri, 2026-10-29."""
import argparse, bz2, collections, csv, glob, importlib.util, os, re, sys, time, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "profiles", "gazetteer")
csv.field_size_limit(sys.maxsize)

# THE COUNTRIES, eo.wikipedia's modern names; a country's key is its name folded, its ending off («Germanio», «Germanujo»
# → «german»), so the period's names meet the modern ones
COUNTRIES = ("Germanio Francio Rusio Pollando Aŭstrio Hungario Ĉeĥio Slovakio Italio Hispanio Portugalio Britio Anglio "
             "Skotlando Kimrio Irlando Nederlando Belgio Luksemburgio Svislando Danio Svedio Norvegio Finnlando Islando "
             "Estonio Latvio Litovio Belorusio Ukrainio Moldavio Rumanio Bulgario Serbio Kroatio Slovenio Montenegro "
             "Albanio Grekio Turkio Kipro Malto Kartvelio Armenio Azerbajĝano Kazaĥio Uzbekio Turkmenio Kirgizio Taĝikio "
             "Usono Kanado Meksiko Kubo Brazilo Argentino Ĉilio Urugvajo Paragvajo Peruo Bolivio Ekvadoro Kolombio "
             "Venezuelo Aŭstralio Japanio Ĉinio Hindio Egiptio Alĝerio Tunizio Maroko Israelo Libano Sirio Irano "
             "Filipinoj Indonezio Vjetnamio Koreio Monako Andoro Liĥtenŝtejno Vatikano Gibraltaro Kostariko Gvatemalo "
             "Panamo Haitio Jamajko Madagaskaro Senegalo Tajlando Birmo").split() + ["Unuiĝinta Reĝlando", "Nov-Zelando",
             "Sud-Afriko", "Nord-Makedonio", "Bosnio kaj Hercegovino", "Sud-Koreio", "Nord-Irlando", "Porto-Riko"]
# (keys as fold() leaves them: a hyphen is a space)
ALIAS = {"unuiginta reg": "brit", "angl": "brit", "skot": "brit", "kimr": "brit", "nord irl": "brit", "granda brit": "brit",
         "hol": "nederl", "usa": "uson", "u s a": "uson", "bohem": "ceh", "morav": "ceh", "sud kore": "kore"}
# the period's states, as the modern countries they held (a printed «Rusujo» meets a town now in Poland)
EMPIRE = {"rus": {"rus", "pol", "finn", "eston", "latv", "litov", "belorus", "ukrain", "moldav", "kartvel", "armen",
                  "azerbajgan", "kazah", "uzbek", "turkmen", "kirgiz", "tagik"},
          "austr": {"austr", "ceh", "pol", "ukrain", "sloven", "kroat", "ital", "ruman", "bosnio kaj hercegovin", "montenegr"},
          "hungar": {"hungar", "slovak", "ruman", "kroat", "serb", "ukrain", "austr"},
          "austrohungar": {"austr", "ceh", "pol", "ukrain", "sloven", "kroat", "ital", "ruman", "bosnio kaj hercegovin",
                           "montenegr", "hungar", "slovak", "serb"},
          "german": {"german", "pol", "franc", "rus", "litov", "dan"},
          "turk": {"turk", "grek", "bulgar", "israel", "sir", "liban", "nord makedon", "alban", "egipt", "kipr"},
          "brit": {"brit", "irl"}, "pol": {"pol", "ukrain", "belorus", "litov"}, "galic": {"pol", "ukrain"},
          "finn": {"finn", "rus"}, "kauzaz": {"kartvel", "armen", "azerbajgan", "rus"}, "siber": {"rus"}, "kaukaz": {"kartvel", "armen", "azerbajgan", "rus"},
          "alzac": {"franc"}, "loren": {"franc"}, "dan": {"dan", "island"}, "sved": {"sved"}, "norveg": {"norveg"}}

def fold(s):
    """Accents off, lower case, the letters NFD keeps whole spelled out, punctuation a space."""
    s = s.replace("ß", "ss").replace("ł", "l").replace("Ł", "l").replace("ø", "o").replace("Ø", "o").replace("æ", "ae").replace("œ", "oe")
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def loose(k):
    """The OCR's commonest confusions in a town's name undone (tools/ocr-name-search-confusions.tsv: «ü» read «ii» half the
    time; «rn» for «m», «cl» for «d», «vv» for «w»), both sides alike."""
    for a, b in (("ii", "u"), ("rn", "m"), ("cl", "d"), ("vv", "w"), ("0", "o"), ("1", "l")): k = k.replace(a, b)
    return k

MINSHARE = 0.01
def bare(s):
    """Lower case, each letter's accent off, the length kept (positions in it are positions in s)."""
    return "".join((unicodedata.normalize("NFD", c)[0] if c.isalpha() else c).lower()[:1] or c for c in s)

def register():
    """The OCR confusions register (tools/ocr-confusions.py, the latest geniza/ocr/method/OCR-CONFUSIONS-‹date›.tsv), old
    print: [(written, letter, case, share, count)], the commonest first; [] if none is built (the editor, 2026-10-29: the
    OCR-only towns and those the gazetteer does not find, for which the confusions register is needed)."""
    ps = sorted(glob.glob(os.path.join(G, "ocr", "method", "OCR-CONFUSIONS-2*.tsv")))
    if not ps: return [], ""
    rows = [r for r in csv.DictReader((l for l in open(ps[-1], encoding="utf-8") if not l.startswith("#")), delimiter="\t")
            if r["print"] == "old" and r["written"] and float(r["share"]) >= MINSHARE]
    # rows alike once the accents are off (the gazetteer folds them) stand as the commonest of them («G» for «C», 232
    # times, not «G» for «Ç», 11: the first diff named the rarer)
    best = {}
    for r in rows:
        k = (bare(r["written"]), bare(r["letter"]), r["case"])
        if k not in best or int(r["count"]) > int(best[k]["count"]): best[k] = r
    return sorted([(r["written"], r["letter"], r["case"], float(r["share"]), int(r["count"])) for r in best.values()], key=lambda x: -x[3]), os.path.basename(ps[-1])

def emended(form):
    """The printed form with ONE measured confusion undone, each way the register allows: [(form, «w» for «l», share)].
    A capital's confusion only at a word's first letter («Gette» → «Cette»), a small letter's elsewhere."""
    out, bf = [], bare(form)
    for w, l, case, share, n in REG:
        # accent-blind, as the gazetteer folds («Gernigov» meets the register's Ĉ read as Ĝ)
        for m in re.finditer(re.escape(bare(w)), bf):
            s = m.start(); first = s == 0 or not form[s - 1].isalpha()
            if (case == "upper") != (first and form[s].isupper()): continue
            new = l.upper() if case == "upper" else l
            out.append((form[:s] + new + form[m.end():], f"«{form[s:m.end()]}» for «{new}»", share))
    return out
REG, REGNAME = register()

def ckey(name):
    """A country's key: «Germanujo», «Germanio» → «german»; «U. S. A.», «Usono» → «uson»."""
    k = fold(name)
    if not k: return ""
    # the dual monarchy printed whole («Aŭstrujo-Hungarujo»: the fourth build read it as Hungarujo alone, so Praha went to
    # a Slovak village)
    if "austr" in k and "hungar" in k: return "austrohungar"
    k = ALIAS.get(k, k)
    if k in ("uson", "usono", "u s a", "usa"): return "uson"
    k = re.sub(r"(?:landujo|lando|ujo|io|o)$", "", k).strip()
    return ALIAS.get(k, k)

CKEYS = {ckey(c): c for c in COUNTRIES}
# the lands whose own town names end in a vowel that tells two towns apart (Bozzolo, Bozzole): no stem there
VOWELLANDS = {ckey(c) for c in ("Italio", "Hispanio", "Portugalio", "Brazilo")}

OVERSEAS = re.compile(r"\b(?:Gvadelupo|Martiniko|Franca Gvajano|Gujano|Reunio|Majoto)\b")

# the OCR's misreadings of a country seen in the re-cut 1913–1914 that are more than a letter off («lkusujo»)
OCRC = {"kus": "rus", "lus": "rus", "lkus": "rus", "ikus": "rus", "llus": "rus", "pers": "iran"}

def pcountry(c):
    """A printed country as one the tool knows: as printed; else mended where the OCR misread it by a letter («Kusujo»,
    «lusujo» Rusujo, «Franeujo» Francujo, «llispanujo» Hispanujo: the re-cut 1913–1914); else '' (unread: no country)."""
    k = ckey(c)
    if not k or k in CKEYS or k in EMPIRE: return c if k else ""
    k2 = OCRC.get(k, re.sub(r"^ll", "h", k).replace("rn", "m"))
    known = set(CKEYS) | set(EMPIRE)
    if k2 in known: return CKEYS.get(k2) or c
    def near(a, b):
        if abs(len(a) - len(b)) > 1 or len(a) < 3: return False
        if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) == 1
        s, l = sorted((a, b), key=len)
        return any(l[:i] + l[i + 1:] == s for i in range(len(l)))
    hit = [x for x in known if near(k2, x)]
    if len(hit) == 1: return CKEYS.get(hit[0]) or {"austr": "Aŭstrio", "rus": "Rusio", "german": "Germanio", "hungar": "Hungario", "turk": "Turkio", "brit": "Britio", "pol": "Pollando"}.get(hit[0], "")
    return ""

def same_country(printed, modern):
    """A printed country (the period's) and an article's (the modern) meet: equal keys, or the modern among the state's."""
    p, m = ckey(printed), ckey(modern)
    if not p or not m: return None
    return p == m or m in EMPIRE.get(p, ())

# ------------------------------------------------------------------ eowiki
# a category of places, the word anywhere in it (the second full pass: «Federaciaj urboj de Rusio» missed, so
# Sankt-Peterburgo with it)
PLACECAT = re.compile(r"\b(?:Urboj|Urbetoj|Urbegoj|Komunumoj|Vilaĝoj|Lokoj|Ĉefurboj|Havenurboj|Municipoj|Setlejoj|Ĝminoj|"
                      r"Kantonoj|Distriktoj|Grafujoj|Provincoj|Regionoj|Departementoj|Landoj|Urbopartoj|Kvartaloj)\b", re.I)
# the lead says what the article is («… estas la dua plej granda urbo de Rusio»)
PLACELEAD = re.compile(r"\bestas\b[^.]{0,80}?\b(?:urbo|urbego|urbeto|komunumo|vilaĝo|havenurbo|ĉefurbo|municipo|setlejo|"
                       r"kvartalo|urboparto|distrikto|provinco|regiono|departemento|lando|ŝtato|insulo|kantono|gubernio)\b")
CAT = re.compile(r"\[\[\s*Kategorio\s*:\s*([^\]|]+)")
# a town, not a region: a tie between same-named articles goes to the town
TOWNCAT = re.compile(r"\b(?:Urboj|Urbetoj|Urbegoj|Komunumoj|Vilaĝoj|Ĉefurboj|Havenurboj|Municipoj|Setlejoj|Ĝminoj|Urbopartoj|Kvartaloj)\b", re.I)
# the same, said at once: «estas [la] [up to four words] urbo», no comma or clause between (read when the index loads)
_W = r"(?:la\s+|unu\s+el\s+la\s+)?(?:[\wĉĝĥĵŝŭ-]+\s+){0,4}?"
STRICTLEAD = re.compile(r"\bestas\s+" + _W + r"(?:urbo|urbego|urbeto|komunumo|vilaĝo|havenurbo|ĉefurbo|municipo|setlejo|kvartalo|"
                        r"urboparto|distrikto|provinco|regiono|departemento|lando|ŝtato|insulo|kantono|gubernio)\b")
STRICTTOWN = re.compile(r"\bestas\s+" + _W + r"(?:urbo|urbego|urbeto|komunumo|vilaĝo|havenurbo|ĉefurbo|municipo|setlejo)\b")
TOWNLEAD = re.compile(r"\bestas\b[^.]{0,80}?\b(?:urbo|urbego|urbeto|komunumo|vilaĝo|havenurbo|ĉefurbo|municipo|setlejo)\b")
PLACEBOX = re.compile(r"\{\{\s*(?:Informkesto\s+)?(?:[\w-]+\s+)?(?:urbo|komunumo|loko|vilaĝo|municipo|urbeto)\b", re.I)
NATBOX = re.compile(r"\|\s*([\w -]*(?:originala|loka|oficiala|nacia|indiĝena|nacilingva)[\w -]*nomo[\w -]*|nomo[\w -]*(?:originala|loka|oficiala|nacia|indiĝena))\s*=\s*([^|\n}]+)", re.I)
# the lead's national names: «(germane ''Tübingen'')», «([[pola lingvo|pole]]: ''Łódź'')», «(france Lille, nederlande Rijsel)»
NATLEAD = re.compile(r"(?:\[\[[^\]|]*\|)?\b([a-zĉĝĥĵŝŭ]{3,}e)(?:\]\])?\s*:?\s*(?:'{2,3}|[\"“„])([^'\"“”„\[\]()|;=]{2,60}?)(?:'{2,3}|[\"”“])")
REDIRECT = re.compile(r"^\s*#\s*(?:ALIDIREKT\w*|REDIRECT)\s*\[\[\s*([^\]|#]+)", re.I)

def strip_wiki(s):
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"<[^>]+>|'{2,}|\{\{[^{}]*\}\}", "", s).strip(" ,.:;")

LANGT = re.compile(r"\{\{\s*(?:lang|lingvo|Lang|Lingvo)(?:-|\s*\|\s*)([a-z]{2,3})\s*\|\s*([^{}|]+?)\s*(?:\|[^{}]*)?\}\}")
def lead(text):
    """The article's first paragraph after the templates (the bold title and its brackets); a language template's name
    kept as «de: ''Tübingen''» (the trial pass, 2026-10-29: the names in {{lang|de|…}} were lost with the templates)."""
    t = LANGT.sub(lambda m: f"{m.group(1)}lingve ''{m.group(2)}''", text[:30000])
    # the notes and the comments out, and the templates innermost first (the first full pass: Stutgarto's PIV notes and
    # Jalto's nested infobox read as its lead, so Stutgarto «in Hispanio», Barcelono «in Usono»)
    t = re.sub(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", "", t, flags=re.S)
    while True:
        t2 = re.sub(r"\{\{[^{}]*\}\}", "", t)
        if t2 == t: break
        t = t2
    i = t.find("'''")
    return t[i:i + 900] if i >= 0 else ""

def lead_country(ld):
    """The country the lead names most, a noun twice an adjective («en suda Usono», «la usona ŝtato», «franca komunumo»;
    the trial pass took the first link: Bufalo in Kanado, Aŭstrio in Germanio; the second, adjectives alike, put Sankt-
    Peterburgo of Florido in Meksiko by «la Meksika Golfo»); a tie to the first named."""
    k = fold(strip_wiki(ld))
    c = collections.Counter(); first = {}
    for m in re.finditer(r"\b([a-z-]+?)(ujo|lando|io|o|a|aj|an|ajn)\b", k):
        ck = ALIAS.get(m.group(1), m.group(1))
        if ck in CKEYS and len(ck) >= 3: c[ck] += 1 if m.group(2).startswith("a") else 2; first.setdefault(ck, m.start())
    if not c: return ""
    top = max(c.values())
    return CKEYS[min((ck for ck in c if c[ck] == top), key=lambda ck: first[ck])]

def eowiki(a):
    import xml.etree.ElementTree as ET
    date = re.search(r"(\d{8})", os.path.basename(a.dump)).group(1)
    outs = {k: os.path.join(D, f"EOWIKI-{k}-{date}.tsv") for k in ("PLACES", "REDIRECTS")}
    if a.limit: outs = {k: v.replace(".tsv", f"-limit{a.limit}.tsv") for k, v in outs.items()}
    if any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    os.makedirs(D, exist_ok=True)
    prog = outs["PLACES"] + ".progress"
    fp, fr = open(outs["PLACES"] + ".partial", "x", encoding="utf-8"), open(outs["REDIRECTS"] + ".partial", "x", encoding="utf-8")
    wp, wr = csv.writer(fp, delimiter="\t", lineterminator="\n"), csv.writer(fr, delimiter="\t", lineterminator="\n")
    wp.writerow(["title", "esperanto", "natlang", "bold", "country", "lead country", "town", "categories", "lead", "revid", "pageid"]); wr.writerow(["from", "to"])
    n = places = reds = 0; t0 = last = time.time()
    for ev, el in ET.iterparse(bz2.open(a.dump), events=("end",)):
        if not el.tag.endswith("}page"): continue
        n += 1
        ns = el.find("{*}ns"); title = el.find("{*}title"); rev = el.find("{*}revision")
        text = (rev.find("{*}text").text or "") if rev is not None and rev.find("{*}text") is not None else ""
        if ns is not None and ns.text == "0" and text:
            m = REDIRECT.match(text)
            if m: wr.writerow([title.text, m.group(1).strip()]); reds += 1
            else:
                cats = [c.strip() for c in CAT.findall(text)]
                pc = [c for c in cats if PLACECAT.search(c)]
                # the lead read only where the raw text's start could say so (a cheap test first: the pass reads 815,000 pages)
                ld = lead(text) if not pc and PLACELEAD.search(text[:6000]) else None
                if pc or PLACEBOX.search(text[:3000]) or PLACELEAD.search(strip_wiki(ld or "")[:300]):
                    ld = ld if ld is not None else lead(text)
                    nat = [f"{l}: {strip_wiki(v)}" for l, v in NATLEAD.findall(ld[:400])]
                    nat += [f"{k.strip()}: {strip_wiki(v)}" for k, v in NATBOX.findall(text[:6000]) if strip_wiki(v)]
                    country = next((CKEYS[ckey(w)] for c in cats for w in re.findall(r"\b(?:en|de)\s+(?:la\s+)?(.+)$", c) if ckey(w) in CKEYS), "")
                    bold = [strip_wiki(b) for b in re.findall(r"'''(.+?)'''", ld[:400]) if re.match(r"^[^\W\d_]", strip_wiki(b)) and not re.search(r"[()]", b)]
                    wp.writerow([title.text, re.sub(r"\s*\([^)]*\)$", "", title.text), " | ".join(dict.fromkeys(nat)), " | ".join(dict.fromkeys(bold)), country,
                                 lead_country(ld), "1" if any(TOWNCAT.search(c) for c in pc) or TOWNLEAD.search(strip_wiki(ld)[:300]) else "", " | ".join(cats[:10]),
                                 re.sub(r"\s+", " ", strip_wiki(ld))[:240], rev.find("{*}id").text, el.find("{*}id").text])
                    places += 1
        el.clear()
        if time.time() - last > 60:
            last = time.time(); fp.flush(); fr.flush()
            with open(prog, "w", encoding="utf-8") as fh: fh.write(f"{time.strftime('%H:%M:%S')} {n} pages, {places} places, {reds} redirects, {int(last - t0)} s\n")
        if a.limit and n >= a.limit: break
    fp.close(); fr.close()
    for k, p in outs.items(): os.rename(p + ".partial", p)
    with open(prog, "w", encoding="utf-8") as fh: fh.write(f"{time.strftime('%H:%M:%S')} DONE {n} pages, {places} places, {reds} redirects, {int(time.time() - t0)} s\n")
    print(f"{n} pages, {places} places, {reds} redirects; wrote " + ", ".join(os.path.relpath(p, ROOT) for p in outs.values()))

# ------------------------------------------------------------------ the index of forms
def latest(kind):
    fs = sorted(f for f in glob.glob(os.path.join(D, f"EOWIKI-{kind}-*.tsv")) if "-limit" not in f)
    return fs[-1] if fs else None

DISAMBIG = re.compile(r"\bestas (?:la )?nomo (?:de|por)\b|\bpovas (?:signifi|esti|rilati)\b|\bestas (?:pluraj|diversaj|kelkaj) ")
LANGADV = set("germane france angle itale hispane pole ruse ĉeĥe hungare nederlande svede dane norvege finne portugale rumane "
              "litove latve estone ukraine beloruse slovake slovene kroate serbe bulgare greke turke katalune eŭske okcitane "
              "bretone kimre irlande skote latine arabe hebree jide japane ĉine koree hinde perse romanĉe frise flandre valone "
              "oficiale loke dialekte historie malnove antaŭe arpitane gaskone normande pikarde korsike sarde friule ladine "
              "sorabe kaŝube silezie bavare ŝvabe alzace luksemburge islande feroe gaele maltane albane makedone bosne".split())

SAINT = re.compile(r"^(?:s|st|ste|sankt|sankta|saint|sainte|san|santa|santo|sao|sv|sveti|sw|swiety)\s+")
def norm(form):
    """fold(), and a saint's town alike however printed («S. Peterburg», «St. Peterburg», «Sankt-Peterburgo»)."""
    return SAINT.sub("s ", fold(form))

def stem(k):
    """A key's Esperanto ending off, so the period's forms meet the Esperanto titles («Moskva» Moskvo, «Kazan» Kazano,
    «Jalta» Jalto): the last vowel of the last word, a, o or e."""
    return re.sub(r"(?<=[a-z]{3})[aoe]$", "", k)

class Index:
    """eo.wikipedia's places by their folded forms: the title, the bold forms of the lead, the national names, the
    redirects to them; and by the forms' stems, a looser key tried last."""
    def __init__(self):
        self.places, self.by, self.st = {}, collections.defaultdict(dict), collections.defaultdict(dict)
        # the stems of the forms that had an ending to lose («Romo», «Moskva»), not of a bare national name («Saint-Claud»)
        self.stv = collections.defaultdict(dict)
        p = latest("PLACES")
        if not p: sys.exit("no EOWIKI-PLACES file: run `gazetteer.py eowiki` first")
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
            # an article the lead alone let in must say it at once («estas [la] [dua plej granda] urbo»; the third pass let
            # in Moskvo-rivero by «estas rivero en Rusio, kiu fluas tra la urbo Moskvo»): no comma before the word
            # the lead's first «estas» only (the river Moskvo-rivero: «… la enfluo estas ĉe urbo Kolomna»)
            i = r["lead"].find("estas ")
            first = r["lead"][i:300] if 0 <= i < 300 else ""
            strict = STRICTLEAD.match(first)
            if not any(PLACECAT.search(c) for c in r["categories"].split(" | ")) and PLACELEAD.search(r["lead"][:300]) and not strict: continue
            if r.get("town") and not any(TOWNCAT.search(c) for c in r["categories"].split(" | ")) and not STRICTTOWN.match(first): r["town"] = ""
            # THE GAZETTEER'S OWN CHECK, build 2026-10-29h (Ezri's reading of its sample of 40): a disambiguation page
            # («Hrádek estas nomo por urbo kaj por pluraj setlejoj», «Praha», «Péronne») and a country («Mexico» to Meksiko,
            # not Meksikurbo) are no town
            if DISAMBIG.search(r["lead"][:300]) or len(re.findall(r"(?:^|\s)\*\s?[A-ZÀ-Ž]", r["lead"])) >= 2 or any("partigil" in c for c in r["categories"].split(" | ")): continue
            if r["title"] in COUNTRIES or any(re.match(r"(?:Landoj|Ŝtatoj) ", c) for c in r["categories"].split(" | ")): continue
            self.places[r["title"]] = r
            self.add(r["esperanto"], r["title"], 3)
            for b in filter(None, r.get("bold", "").split(" | ")): self.add(b, r["title"], 2)
            # a national name only after a language word or in the infobox's name fields (the check: «Gland» went to
            # Vullierens, whose lead names it in italics)
            for nv in filter(None, r["natlang"].split(" | ")):
                lab, v = (nv.split(": ", 1) + [""])[:2]
                if not (lab.endswith("lingve") or lab in LANGADV or "nomo" in lab): continue
                for part in re.split(r"\s*(?:,|/| aŭ )\s*", v): self.add(part, r["title"], 1)
        for r in csv.DictReader(open(latest("REDIRECTS"), encoding="utf-8"), delimiter="\t"):
            if r["to"] in self.places:
                # a redirect whose form the article never shows is weak (the check: eo.wikipedia's «Gland» → Vullierens)
                f = re.sub(r"\s*\([^)]*\)$", "", r["from"]); to = self.places[r["to"]]
                shown = fold(f) in fold(to["title"] + " " + to["lead"] + " " + to.get("bold", "") + " " + to["natlang"])
                self.add(f, r["to"], 3 if shown else 1)
        # THE COUNTRY: the categories' («Urboj de Germanio»); else the region's, whose article has one («Municipoj de
        # Gipusko» → Gipusko → Hispanio; the first full pass put Donostio in Francio from its lead), twice over; else the
        # lead's
        byname = {r["esperanto"]: r for r in self.places.values()}
        for _ in range(2):
            for r in self.places.values():
                if r["country"]: continue
                for c in filter(None, r["categories"].split(" | ")):
                    m = re.search(r"\b(?:en|de)\s+(?:la\s+)?(.+)$", c)
                    reg = m and (self.places.get(m.group(1)) or byname.get(m.group(1)))
                    # the region's country from its categories or its lead, before the town's own lead (the check: Praha
                    # (Teksaso), whose lead names its Czech settlers, read as in Ĉeĥio; Teksaso's lead says Usono)
                    rc = reg and reg is not r and (reg["country"] or reg.get("lead country"))
                    if rc: r["country"] = rc; break
        for r in self.places.values():
            r["strong"] = bool(r["country"])
            if not r["country"]: r["country"] = r.get("lead country", "")
        # EACH ARTICLE'S WIKIDATA ID (the editor, 2026-10-29: Wikidata ids wherever they apply): from
        # eo.wikipedia's page-properties dump (sources/web-2026-10-29-gazetteer/), by page id
        pp = sorted(glob.glob(os.path.join(G, "sources", "web-2026-10-29-gazetteer", "eowiki-*-page_props.sql.gz")))
        ids = {r["pageid"]: r for r in self.places.values() if r.get("pageid")}
        if pp and ids:
            import gzip
            for line in gzip.open(pp[-1], "rt", encoding="utf-8", errors="replace"):
                for pid, q in re.findall(r"\((\d+),'wikibase_item','(Q\d+)'", line):
                    if pid in ids: ids[pid]["wikidata"] = q
    def add(self, form, title, strength):
        """A form of an article, with how strongly it names it: 3 its title or a redirect, 2 a bold form of its lead, 1 a
        national name in its lead or infobox (the third build held «Breslau» between Vroclavo, whose redirect it is,
        and Brzeg and Świdnica, whose leads name it)."""
        k = norm(form)
        if len(k) >= 2:
            # the stems of every form (build m's two narrower rules, the title alone and the Esperanto -o alone, lost 29
            # and 52 good joins: Varno Varna, Plovdivo Plovdiv, Batum Batumo); the second check's «Bozzolo» → Bozzole
            # is stopped in resolve1 by the country instead
            keys = [(self.by, k), (self.by, loose(k)), (self.st, stem(k)), (self.st, stem(loose(k)))]
            keys += [(self.stv, stem(x)) for x in (k, loose(k)) if stem(x) != x]
            for idx, key in keys:
                idx[key][title] = max(idx[key].get(title, 0), strength)
    def natname(self, title, printed=""):
        """The place's national name: of the article's national names and the lead's bold forms, the one the print
        matches («Tŭbingen» → Tübingen); else the infobox's official name; else the first bold form not the Esperanto."""
        r = self.places[title]
        nat = [(nv.split(": ", 1)[0], nv.split(": ", 1)[-1]) for nv in filter(None, r["natlang"].split(" | "))]
        # the title first (an article under the national name, «Tübingen», gave «Tubingeno» from its bold forms)
        forms = [r["esperanto"]] + [v for _, v in nat] + [b for b in filter(None, r.get("bold", "").split(" | "))]
        k = loose(norm(printed)) if printed else None
        for f in forms:
            if k and (loose(norm(f)) == k or stem(loose(norm(f))) == stem(k)): return f
        off = [v for l, v in nat if re.search(r"oficiala|loka|originala", l)]
        if off: return off[0]
        other = [b for b in filter(None, r.get("bold", "").split(" | ")) if norm(b) != norm(r["esperanto"])]
        return other[0] if other else ""
    def prefer(self, ts, strength):
        """Of same-named articles, the one the form names most strongly, if one; else the one town of plain title among
        those (eo.wikipedia's own main article: «Prostějov», not «Prostějov (Žumberk)»; «Amiens», not Pikardio)."""
        top = max(strength[t] for t in ts)
        ts = [t for t in ts if strength[t] == top]
        if len(ts) == 1: return ts[0]
        best = [t for t in ts if "(" not in t and self.places[t].get("town")]
        return best[0] if len(best) == 1 else None
    def confirmed(self, t, region):
        """An article whose title says which of its name it is («Tournon (Savoie)») only where the print says so too: a
        word of the printed region in its title or lead (the check: «Tournon» (Francujo) went to the Savoie one, the
        Ardèche one the likelier)."""
        if "(" not in t: return True
        hay = fold(t + " " + self.places[t].get("lead", "")[:240])
        return any(len(w) >= 3 and re.search(rf"\b{re.escape(w)}", hay) for w in fold(region).split())
    def resolve(self, form, country="", region="", ocr=False):
        """(title, how) for a printed form: one article of that form in that country; else (None, why). For a form read
        by OCR (`ocr`) that finds no town, with a country printed: the form with one confusion of the OCR register undone,
        where exactly one town in that country is found so (never for a typed transcription: the Adresaro's Wikisource)."""
        t, w = self.resolve1(form, country)
        # only where the country is read, and the emended form taken as it stands or by its stem, the fixed confusions
        # of loose() not added on (build m's first diff: «Thorn» → Thum by ü and rn → m; «Batum», «Saigon», «Sunne» under
        # an unread country to Batam, Saugon, Sanne)
        # never a form that is itself a place's name anywhere: the print is right, the place not a town or not in that
        # country (2026-10-31: «Auteuil», Parizo's quarter, mended to Anteuil; «Port», Port (Ain)'s name, to Pori in Finland)
        named = bool(self.by.get(norm(form)))
        if ocr and pcountry(country) and REG and not named and not (t and self.places[t].get("town")):
            found = {}
            for f2, what, share in emended(form):
                t2, w2 = self.resolve1(f2, country, strict=True)
                # in the printed country itself, never an article of unknown country («Goole» → Bronckhorst)
                if t2 and self.places[t2].get("town") and same_country(pcountry(country), self.places[t2]["country"]): found.setdefault(t2, (what, share))
            if len(found) == 1:
                t2, (what, share) = next(iter(found.items()))
                t, w = t2, f"the form with the OCR's {what} undone (register {REGNAME}, {100 * share:.1f}% of the letter), in {pcountry(country)}"
            elif len(found) > 1 and not t:
                w = f"{w}; the OCR register gives {len(found)} towns: " + "; ".join(sorted(found)[:5])
        # a title's bracket that only tells the metropole's town from an overseas namesake needs no region printed
        if t and "the metropole's" not in w and not self.confirmed(t, region):
            return None, f"held: «{t}», the print does not say which {self.places[t]['esperanto']}"
        return t, w
    def resolve1(self, form, country="", strict=False):
        """A town first: an answer that is no town (a river, a region) is kept only if no later key finds a town (the
        fourth build: eo.wikipedia's redirect «Moskva» is the river's, so «Moskva» went to Moskvo-rivero, not Moskvo)."""
        k = norm(form)
        # a scrap of the address taken for a town («gub» of «gub. Saratov» went to Ĝubao in South Sudan by its stem): a form
        # of four letters at least, and the stems only where a country is printed
        if len(k.replace(" ", "")) < 4: return None, "too short to be a town"
        country = pcountry(country)
        why, fallback = "not in eo.wikipedia", None
        levels = [(self.by, k, "the form"), (self.by, loose(k), "the form, OCR confusions undone")]
        # in a land whose own names end in vowels, a form ending in a vowel meets by its stem only an Esperanto title in
        # -o («Barcelone», «Zaragoza» → Barcelono, Zaragozo): there the vowel of a national name tells two towns apart
        # (the second check: «Bozzolo» (Italujo) went to Bozzole)
        vl = country and re.search(r"[aeo]$", k) and ckey(country) in VOWELLANDS
        # a printed «-e» is no Esperanto ending: its stem meets only a form that had one («Rome» Romo), never a bare national
        # name (2026-10-31: «Saint-Claude» went to Saint-Claud, and «Uriage», mended to «Uriaçe», to Huriel by its «Uriac»)
        st = self.stv if k.endswith("e") else self.st
        if country:
            levels += [(st, stem(k), "the form's stem"), (st, stem(loose(k)), "the form's stem, OCR confusions undone")]
        if strict: levels = [l for l in levels if "undone" not in l[2]]
        for idx, key, how in levels:
            cands = idx.get(key, {})
            # the stem of the title itself («Campo» met Ponferado by the stem of another of its forms)
            if vl and idx is st: cands = {t: s for t, s in cands.items() if self.places[t]["esperanto"].endswith("o") and key in (stem(norm(self.places[t]["esperanto"])), stem(loose(norm(self.places[t]["esperanto"]))))}
            if not cands: continue
            t, w = self.pick(cands, country, how)
            if t and self.places[t].get("town"): return t, w
            if t and not fallback: fallback = (t, w)
            if not t and not fallback: why = w
        return fallback or (None, why)
    def pick(self, cands, country, how):
        if country:
            ok = [t for t in cands if same_country(country, self.places[t]["country"])]
            # a country from the categories or the region before one from the lead alone (the check: Praha (Teksaso), its
            # lead naming its Czech settlers, against Prago, «Urboj de Ĉeĥio»)
            strong = [t for t in ok if self.places[t].get("strong")]
            if strong: ok = strong
            # the period's France is the metropole: of a tie under a printed France, never the overseas department's
            # (2026-10-31: «Saint-Claude» held between the Jura's and Guadeloupe's)
            home = [t for t in ok if not OVERSEAS.search(self.places[t]["categories"])]
            if ckey(country) == "franc" and home and len(home) < len(ok):
                if len(home) == 1: return home[0], f"{how}, in {country}, the metropole's of {len(ok)}"
                ok = home
            if len(ok) == 1: return ok[0], f"{how}, in {country}"
            if len(ok) > 1:
                t = self.prefer(ok, cands)
                if t: return t, f"{how}, in {country}, the main article of {len(ok)}"
                return None, f"ambiguous in {country}: " + "; ".join(sorted(ok)[:5])
            unk = [t for t in cands if not self.places[t]["country"]]
            if len(unk) == 1 and len(cands) == 1: return unk[0], f"{how}, the article's country unknown"
            return None, f"not in {country}: " + "; ".join(sorted(cands)[:5])
        if len(cands) == 1: return next(iter(cands)), f"{how}, no country printed"
        # no country: only eo.wikipedia's main article, the one town of plain title, never the strongest form (the fourth
        # build: «Odessa» under an unread country went to Odessa (Teksaso), titled so, not to Odeso)
        best = [t for t in cands if "(" not in t and self.places[t].get("town")]
        if len(best) == 1: return best[0], f"{how}, no country printed, the main article of {len(cands)}"
        return None, "ambiguous, no country printed: " + "; ".join(sorted(cands)[:5])

def forms(tag):
    """{(source, printed form, printed country, Wikidata id): row} from GAZETTEER-FORMS-TAG.tsv: the build's join of every
    printed form, as the directories' tools read it (so a tool's towns follow one named build)."""
    p = os.path.join(D, f"GAZETTEER-FORMS-{tag}.tsv")
    return {(r["source"], r["printed form"], r["printed country"], r["wikidata"]): r for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t")}

def town_line(r, printed):
    """(the key's town, the sentence's town, the voice's note) for a joined form: the Esperanto name in the key, the
    national name beside it in the sentence where it differs («Akeno (Aachen)»), eo.wikipedia's article named."""
    eo, nat = r["esperanto"], r["national name"]
    shown = f"{eo} ({nat})" if nat and fold(nat) != fold(eo) else eo
    note = f"⟦la urbo: «{printed}» = {eo}, eo.wikipedia «{r['article']}»{', Wikidata ' + r['wikidata'] if r['wikidata'] else ''}⟧"
    return eo, shown, note

_IX = None
def resolve(form, country=""):
    global _IX
    if _IX is None: _IX = Index()
    return _IX.resolve(form, country)

# ------------------------------------------------------------------ the seeds
# a country word, hyphened ones whole («Aŭstro-Hungarujo»: the fifth build read «Hungarujo», so Praha went to Slovakia)
CW = re.compile(r"\b([A-ZĈĜĤĴŜŬ][\wĉĝĥĵŝŭ-]*?(?:ujo|lando|io|ono|ado|ilo|ujoj))\b|(U\.\s*S\.\s*A)")
def printed_country(text):
    """The country an Adresaro entry prints: its last country word («Abo, Finnlando, Rusujo.» → Rusujo)."""
    ws = [m.group(1) or "Usono" for m in CW.finditer(text) if ckey(m.group(1) or "Usono") in CKEYS or ckey(m.group(1) or "") in EMPIRE]
    return ws[-1] if ws else ""

def mod(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def seeds():
    """[(source, form, printed country, region, Wikidata id, locator)] from the Adresaro and the Oficiala Jarlibro."""
    out = []
    AX = mod("ax", "adresaro-extract.py"); W = AX.wiki()
    for item, para, s, y, n, t in AX.entries():
        e = AX.marked(AX.parse(s, t), W, item, n, s, t)
        if e["town"]: out.append(("Adr", e["town"], printed_country(t), "", e.get("qid", ""), f"{item}, ¶ {para}"))
    OX = mod("ox", "oficiala-jarlibro-extract.py")
    for y, (item, pa, pb, _d, _p) in OX.VOLS.items():
        rows, _u = OX.parse(item, pa, pb)
        seen = set()
        for p, n, town, where, code, _t in rows:
            if town and (town, where) not in seen:
                seen.add((town, where)); w = [x.strip() for x in where.split(",")]
                out.append(("OfJ", town, w[0], ", ".join(w[1:]), "", f"{OX.KEYS[item]}, PDF {p}, l. {n}"))
    return out

# the seeds read by OCR (the Oficiala Jarlibro); the Adresaro's are Wikisource's typed transcription
OCRSRC = {"OfJ"}

def provenance(q, t, ar):
    """The row's provenance, by reliability (the editor, 2026-10-29: Wikidata, then Wikipedia, then the corpus,
as degrees of reliability): `wikidata` where a curated source gives the id (the Adresaro's Wikisource transcription) and
    the joined article has it too, or no article was joined; `wikipedia` where only an eo.wikipedia article was matched
    (its id from the article); `corpus` where only our sources' printed forms stand; `conflict` where the source's id and
    the article's differ (for the review)."""
    aq = ar.get("wikidata", "") if t else ""
    if q and t and aq and q != aq: return "conflict"
    if q: return "wikidata"
    return "wikipedia" if t else "corpus"

def build(a):
    outs = {k: os.path.join(D, f) for k, f in (("tsv", f"GAZETTEER-{a.tag}.tsv"), ("forms", f"GAZETTEER-FORMS-{a.tag}.tsv"), ("rev", f"GAZETTEER-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    ix = Index(); S = seeds(); cnt = collections.Counter()
    # the Adresaro's forms of one Wikidata id stand together: the id's place is the article most of its forms resolve to
    byq = collections.defaultdict(list)
    for s in S:
        if s[4]: byq[s[4]].append(s)
    qplace, qconflict = {}, {}
    for q, ss in byq.items():
        votes = collections.Counter()
        for src, form, c, region, _q, _l in ss:
            t, _why = ix.resolve(form, c, region, ocr=src in OCRSRC)
            if t: votes[t] += 1
        if votes:
            qplace[q] = votes.most_common(1)[0][0]
            if len(votes) > 1: qconflict[q] = votes
    places = collections.OrderedDict()   # key → {title, forms Counter, countries, regions, qids, sources, first locator}
    unjoined = collections.defaultdict(lambda: {"n": 0, "loc": "", "why": ""})
    formrows = {}   # (source, form, printed country, Wikidata id) → the row the extractors read
    for src, form, c, region, q, loc in S:
        cnt[f"{src} forms"] += 1
        # an id's place only where the form's printed country agrees (the second build gave «S. Peterburg» (Rusujo) the
        # Florida town its unprinted forms had found)
        qok = q in qplace and same_country(pcountry(c), ix.places[qplace[q]]["country"]) is not False
        t, why = (qplace[q], "the Wikidata id's other forms") if qok else ix.resolve(form, c, region, ocr=src in OCRSRC)
        if qok and ix.resolve(form, c, region, ocr=src in OCRSRC)[0] == qplace[q]: why = "the form and its Wikidata id"
        if (src, form, c, q) not in formrows:
            ar = ix.places.get(t, {}) if t else {}
            formrows[(src, form, c, q)] = [src, form, c, q, t or "", ar.get("esperanto", ""), ix.natname(t, form) if t else "", ar.get("country", ""), why, region, loc,
                                           ar.get("wikidata", ""), provenance(q, t, ar)]
        if not t:
            cnt[f"{src} unjoined"] += 1
            u = unjoined[(form, c, q)]; u["n"] += 1; u["loc"] = u["loc"] or loc; u["why"] = why
            key = f"{q}" if q else f"{fold(form)} -- {ckey(c)}"
        else:
            cnt[f"{src} joined"] += 1; key = t
        p = places.setdefault(key, {"title": t or "", "forms": collections.Counter(), "countries": collections.Counter(),
                                    "regions": collections.Counter(), "qids": collections.Counter(), "sources": collections.Counter(), "loc": loc, "why": collections.Counter()})
        p["forms"][form] += 1; p["sources"][src] += 1; p["why"][why] += 1
        if c: p["countries"][c] += 1
        if region: p["regions"][region] += 1
        if q: p["qids"][q] += 1
    cnt["places"] = len(places); cnt["joined to eo.wikipedia"] = sum(1 for p in places.values() if p["title"])
    cnt["Wikidata ids"] = len(byq); cnt["ids whose forms disagree"] = len(qconflict)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    with open(outs["tsv"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["place", "esperanto", "national name", "national names", "country", "wikidata", "printed forms", "printed countries", "regions", "sources", "joined by", "first seen", "provenance"])
        for key, p in sorted(places.items(), key=lambda kv: fold(kv[1]["title"] or kv[0])):
            ar = ix.places.get(p["title"], {})
            fm = lambda c: "; ".join(f"{k} ×{v}" for k, v in c.most_common())
            # the place's id: the source's where it gives one, else the joined article's (2026-10-30: build m left 1,924
            # joined places without the id their forms already carried); its provenance by the forms' rule
            q = " ".join(q for q, _ in p["qids"].most_common())
            w.writerow([key, ar.get("esperanto", ""), ix.natname(p["title"], p["forms"].most_common(1)[0][0]) if p["title"] else "",
                        ar.get("natlang", ""), ar.get("country", ""), q or ar.get("wikidata", ""),
                        fm(p["forms"]), fm(p["countries"]), fm(p["regions"]), fm(p["sources"]), fm(p["why"]), p["loc"],
                        provenance(p["qids"].most_common(1)[0][0] if p["qids"] else "", p["title"], ar)])
    with open(outs["forms"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["source", "printed form", "printed country", "wikidata", "article", "esperanto", "national name", "country", "joined by", "region", "first seen",
                    "article's wikidata", "provenance"])
        w.writerows(formrows.values())
    with open(outs["rev"], "x", encoding="utf-8") as fh:
        fh.write(f"# The gazetteer, {a.tag}\n\n`[GENERATED by tools/gazetteer.py build. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". The places: `{os.path.basename(outs['tsv'])}`; eo.wikipedia: `{os.path.basename(latest('PLACES'))}`.\n\n")
        fh.write(f"## Wikidata ids whose forms resolve to more than one article: {len(qconflict)}\n\n")
        for q, v in sorted(qconflict.items(), key=lambda kv: -sum(kv[1].values())):
            fh.write(f"- {q}: " + "; ".join(f"{t} ×{n}" for t, n in v.most_common()) + "\n")
        uj = sorted(unjoined.items(), key=lambda kv: -kv[1]["n"])
        fh.write(f"\n## Printed forms joined to no article: {len(uj)} forms, {sum(u['n'] for _, u in uj)} entries\n\n")
        for (form, c, q), u in uj: fh.write(f"- «{form}» ({c or '?'}{', ' + q if q else ''}) ×{u['n']} · {u['why']} · {u['loc']}\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

def sample(a):
    """The accuracy check of a build's joins (runbook D4c: a tool's output is checked by a legilo): N joined forms, half
    from the weaker routes (the stem, the main article, no country printed), half from the rest, each with the article's
    lead; the brief inside the file. Writes profiles/gazetteer/ACCURACY-SAMPLE-TAG.md, create-only."""
    import random
    out = os.path.join(D, f"ACCURACY-SAMPLE-{a.tag}.md")
    if os.path.exists(out): sys.exit(f"refusing to overwrite: {out}")
    rows = [r for r in forms(a.tag).values() if r["article"]]
    weak = [r for r in rows if re.search(r"stem|main article|no country|country unknown", r["joined by"])]
    rest = [r for r in rows if r not in weak]
    rnd = random.Random(a.seed)
    pick = rnd.sample(weak, min(len(weak), a.n // 2)) + rnd.sample(rest, a.n - min(len(weak), a.n // 2))
    ix = Index()
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The gazetteer's accuracy check, build {a.tag}\n\n`[GENERATED by tools/gazetteer.py sample --tag {a.tag} --n {a.n} --seed {a.seed}. Do not hand-edit.]`\n\n")
        fh.write(f"{len(pick)} joins of {len(rows)} (weaker routes {len(weak)}): {min(len(weak), a.n // 2)} of the weaker, the rest of the others.\n\n")
        fh.write("## La briefo, kiel donita al la legilo\n\n"
                 "Vi kontrolas, ĉu ilo ĝuste identigis urbojn. Por ĉiu ero sube: la urbo kiel presita en malnova adresaro "
                 "(1889–1914), kun la lando kaj regiono kiel presitaj (la landoj de tiu tempo: Rusujo, Aŭstrujo, Germanujo …, "
                 "ofte kun eraroj de la optika legado), kaj la artikolo de Vikipedio en Esperanto, al kiu la ilo ĝin ligis "
                 "(titolo, lando hodiaŭa, la komenco de la artikolo). Juĝu nur el tio, kio estas skribita ĉi tie, kaj el via "
                 "scio pri geografio; legu neniun alian dosieron.\n\n"
                 "Por ĉiu ero skribu unu linion: «N. jes» (la sama loko), «N. ne — kial» (alia loko: samnoma urbo en alia "
                 "lando, regiono anstataŭ urbo, rivero …), aŭ «N. eble — kial» (ne decideble el tio). Poste unu linio "
                 "«Resumo: X jes, Y ne, Z eble.» kaj la lasta linio «Fino: N eroj.»\n\n## La eroj\n\n")
        for i, r in enumerate(pick, 1):
            ar = ix.places.get(r["article"], {})
            fh.write(f"{i}. **«{r['printed form']}»** · lando presita: {r['printed country'] or '—'}{' · regiono: ' + r['region'] if r.get('region') else ''}"
                     f"{' · Vikidatumoj ' + r['wikidata'] if r['wikidata'] else ''} · fonto: {r['source']}, {r.get('first seen', '')}\n"
                     f"   → **{r['article']}** ({ar.get('country') or 'lando nekonata'}): «{ar.get('lead', '')[:240]}»\n"
                     f"   (ligita per: {r['joined by']})\n")
    print(f"wrote {os.path.relpath(out, ROOT)}: {len(pick)} joins")

def diff(a):
    """Two builds' joins compared, form by form (after a tool fix, what the fix lost as well as what it gained): writes
    profiles/gazetteer/GAZETTEER-DIFF-OLD-NEW.md, create-only; the counts on screen."""
    out = os.path.join(D, f"GAZETTEER-DIFF-{a.old}-{a.new}.md")
    if os.path.exists(out): sys.exit(f"refusing: {out} exists")
    A, B = forms(a.old), forms(a.new)
    kinds = collections.defaultdict(list)
    for k in sorted(set(A) | set(B), key=lambda k: (k[0], fold(k[1]))):
        x, y = A.get(k, {}).get("article", ""), B.get(k, {}).get("article", "")
        if x == y: continue
        kind = "lost" if x and not y else "gained" if y and not x else "changed"
        kinds[(k[0], kind)].append((k, x, y, (B.get(k) or A.get(k))))
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The gazetteer, {a.old} against {a.new}\n\n`[GENERATED by tools/gazetteer.py diff. Do not hand-edit — re-run it.]`\n\n")
        for (src, kind), rows in sorted(kinds.items()):
            fh.write(f"## {src}, {kind}: {len(rows)}\n\n")
            for (s, form, c, q), x, y, r in rows:
                why_new = B.get((s, form, c, q), {}).get("joined by", "")
                fh.write(f"- «{form}» ({c or '?'}{', ' + q if q else ''}): {x or '—'} → {y or '—'} · {why_new} · {r.get('first seen', '')}\n")
            fh.write("\n")
    print(", ".join(f"{s} {k} {len(v)}" for (s, k), v in sorted(kinds.items())), "→", os.path.relpath(out, ROOT))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("--tag", required=True); s.add_argument("--n", type=int, default=40); s.add_argument("--seed", type=int, default=1)
    e = sub.add_parser("eowiki"); e.add_argument("--dump", required=True); e.add_argument("--limit", type=int)
    b = sub.add_parser("build"); b.add_argument("--tag", required=True); b.add_argument("--write", action="store_true")
    l = sub.add_parser("look"); l.add_argument("form"); l.add_argument("--country", default="")
    d = sub.add_parser("diff"); d.add_argument("--old", required=True); d.add_argument("--new", required=True)
    a = ap.parse_args()
    if a.cmd == "eowiki": eowiki(a)
    elif a.cmd == "build": build(a)
    elif a.cmd == "diff": diff(a)
    elif a.cmd == "sample": sample(a)
    else:
        t, why = resolve(a.form, a.country)
        print(f"«{a.form}» ({a.country or 'no country'}) → {t or '—'} · {why}")
        if t:
            r = _IX.places[t]; print(f"   esperanto {r['esperanto']} · natlang {r['natlang'] or '—'} · country {r['country'] or '?'} · {r['lead'][:160]}")

if __name__ == "__main__":
    main()
