#!/usr/bin/env python3
"""The *Oficiala Jarlibro* of U. E. A. read by tool (runbook D4c; the directory survey's group 5, 2026-10-29; the editor,
2026-10-29 13:4x: the yearbook parsers a priority, the Oficiala the first, the trial for the Tutmonda).

    tools/oficiala-jarlibro-extract.py --hits HITS.tsv --tag TAG [--years 1911,1912] [--show PDF] [--write]

The address book of the delegates («ADRESARO DE LA DELEGITOJ, VICDELEGITOJ, SUBDELEGITOJ KAJ ESPERANTO-OFICEJOJ»), town
by town: a town line «Abbeville (Francujo, Somme).» (from 1912 with the population, «Aachen (Germanujo, Rheinland),
160,000.»), then one line a person, «D : D^ro Claude NEUILLIÈS, kuracisto, 8, rue des Cordeliers.», wrapped lines joined;
the consul letters («K. J. V. [21]»), the guide-sheet mark («g.») and the offices («E.-O : Librejo …») make no line.
A person becomes lines only as in directory-extract.py: an exact strong hit (HITS, the name search over the directories)
on the printed surname, borne out by the profile (the town, the initials or the forename); else held, into the review.
Lines: {ofico: delegito / vicdelegito / subdelegito de U. E. A., ‹town›}; {loĝado: ‹town›} with the printed address;
{profesio: …} for an Esperanto occupation. Dated by the list's own date («Ordigita ĝis la 15ª novembro 1910» in 1911).

1913 and 1914 ran the two printed columns into one line (1913 PDF 55–95, 1914 PDF 59–102) until Miles's re-cut at the
gutter (2026-10-29 14:3x); they are read from it. Writes, with --write, refusing to overwrite:
  dowse/oficiala-jarlibro/facts-return-TAG-delegitoj.md   (the lines, for the assembler)
  dowse/oficiala-jarlibro/delegitoj-TAG.tsv               (every person line parsed, with its verdict)
  dowse/oficiala-jarlibro/DELEGITOJ-REVIEW-TAG.md         (the counts, the held, the lines the parse did not know)
Without --write it prints the counts. Ezri, 2026-10-29."""
import argparse, collections, csv, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "dowse", "oficiala-jarlibro")
spec = importlib.util.spec_from_file_location("dx", os.path.join(ROOT, "tools", "directory-extract.py"))
DX = importlib.util.module_from_spec(spec); spec.loader.exec_module(DX)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gazetteer as GZ  # noqa: E402
csv.field_size_limit(sys.maxsize)

# THE DELEGATES' PAGES (2026-10-29, from the key «MALLONGIGOJ» to the last town) and the date each list gives itself
VOLS = {1911: ("OficialaJarlibro.1911", 60, 120, "1910-11-15", "Ordigita ĝis la 15ª novembro 1910"),
        1912: ("OficialaJarlibro_1912_kul43114", 79, 146, "1911-11-15", "Ordigita ĝis la 15ª novembro 1911"),
        # re-cut at the gutter (Miles, 2026-10-29 14:3x, chain cupel19b-4, notices RN-2026-10-29-53 and -54)
        1913: ("OficialaJarlibro.1913", 55, 95, "1913-01-01", "Ordigita ĝis la 1ª januaro 1913"),
        1914: ("OficialaJarlibro.1914", 59, 102, "1913-12-15", "Ordigita ĝis la 15 decembro 1913")}
# the items' keys, as every locator names them (OCR-ITEM-KEYS.tsv: «oficialajarlibro-1912-kul43114»)
KEYS = {r["item"]: r["key"] for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-KEYS.tsv"), encoding="utf-8")
                                                      if not l.startswith("#")), delimiter="\t")}
RECUT = {}   # the volumes whose columns still run together: none since the re-cut of 2026-10-29
# THE PAGES THE RE-CUT LEFT RUN TOGETHER (the accuracy check of 2026-11-01, lines 3, 4 and 24: Smiley's address took the
# next town line «Arĥangelsk (Rusujo …)», Stanyan's the delegate of Münster): the cut at the gutter kept 39 of 1913's
# pages and 38 of 1914's (RN-2026-10-29-53, -54), and the others still read across both columns. A delegates' column runs
# about 40 characters a line; a page with more than 12% of its lines over 75 characters is held whole (1913 PDF 60, 64;
# 1914 PDF 61, 62, 75, 82, 85 score 0.16–0.54, every other page 0.09 or less), and its last town is not carried on
MIXED = 0.12

def mixed(lines):
    ls = [l for _n, l in lines if len(l.strip()) >= 20]
    return bool(ls) and sum(len(l) > 75 for l in ls) / len(ls) > MIXED

def mixed_pages(item, a, b):
    pages = DX.page_lines(item)
    return {p for p in range(a, b + 1) if mixed(pages.get(p, []))}

# the town line, its brackets as the OCR leaves them (the first run, 2026-10-29: «Bath (Anglujo, Wilts..», «Bendzin
# (Rusujo, Polujo".», «Biel (Bienne! (Svisujo).», «Funchal [Madeira] ; (Portugalujo).»), and a person's line run on to it
# («Annonay (Francujo, Ardeche).D : G. Grimaud, …»)
TOWN = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-Ž][^():;]{1,45}?)\s*[(\[]\s*(?P<where>[^:;]{2,70}?)\s*[)\].!\"”'’,]*\s*[.,]?\s*(?:[\d.,]{4,}\.?)?\s*(?:\[\d+\])?\W{0,3}(?P<run>(?:VD|SD|D)\s*\.?\s*[:;].*)?$")
# the re-cut 1913–1914 (2026-10-29): the opening bracket misread («Châtellerault |l'rancujo, Vienne).», «Hildesheim
# “Germanujo, Hannover), 55,000.»), the country word kept
TOWN3 = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-Ž][\wÀ-ž'’. -]{1,40}?)\s*[|{(\[“\"„]\s*l?'?(?P<where>[^:;\d()]*?(?:ujo|io|ono|ando|Ameriko)\b[^:;\d()]{0,50}?)\s*[)\]]\.?$")
# a population after the bracket («…, Hannover), 55,000.», «…, Piotr. gub.), 296,00.»), left out before the town is read
POPTAIL = re.compile(r"(?<=[)\]])\s*[,.]?\s*\d[\d.,]{2,}\.?\s*$")
# any line with a country word and a closing bracket that no town pattern read: the town is cleared
COUNTRYISH = re.compile(r"[A-Za-zÀ-ž](?:ujo|lando|Usono)\b[^:]{0,40}[)\]]\.?\s*$")
# a line that should be a town line and is not read as one: the town is cleared, and the persons after it held, not
# filed under the town before (the first run: Bath's and Biel's persons would have gone to Barcelona's and Bielefeld's)
TOWNISH = re.compile(r"^\W{0,3}[A-ZÀ-Ž][\wÀ-ž'’ .-]{2,40}[(\[]\s*[A-ZÀ-Ž]")
# a town line whose opening bracket the OCR lost («Hamburg Germanujo).», «Lodz Kusujo, Piotr. gub.).», «Rilsk “Rusujo,
# Kurska gub.).»): the town is what stands before the country, a word in -ujo, -io, -ando, -ono
TOWN2 = re.compile(r"^\W{0,3}(?P<town>[A-ZÀ-Ž][\wÀ-ž'’. -]{1,40}?)\s+[\"“'’]?(?P<where>[A-ZÀ-Ža-z][a-zà-ž]+(?:ujo|io|ando|ono)\b[^:;\d]{0,50})$")
# the population in brackets after it («(Granda Berlino : 3,703,000).», «[Seine : 3,849,000].») and a page number run on
# before it («— 97 Potsdam (…)»), left out before the town is read
POP = re.compile(r"\s*[(\[][^()\[\]]*\d[^()\[\]]*[)\]]\.?\s*$")
PAGENO = re.compile(r"^[—=\-.\s]*\d{1,3}\s*[—=\-.]*\s+(?=[A-ZÀ-Ž][^:]*[(\[])")
# the role code before its colon, the OCR's marks between («D ':», «D) :», «D::», «D ;», «D-:»), and its misreadings
# («I) :», «/);», «Do:», «/J :», «P :» for D, «VI) :», «VO):», «VU:» for VD, «SO):», «SI):», «S D :», «Sp :» for SD);
# «». =» in 1911's key is the plain Delegito. A code is at most four marks, all of them from the misreadings seen
ROLE = re.compile(r"^\W{0,3}(?P<code>VD|SD|D|S\s?D|S\s?p|[DVSIJTPZ/7\[\])il1o'’.-]{1,4})\s*[.'’)\"»-]{0,3}\s*[:;]{1,2}\s*(?P<rest>[^:]{3,}.*)$")
ROLE2 = re.compile(r"^\W{0,3}(?P<code>VD|SD|Do)\s+(?P<rest>[A-ZÀ-Ž].+)$")
# «D : J. BLANC» read as «D.J. BLANC», «DA. ANDREEVSKI», «D . J. GULINSKI»: the code and the initial run together
ROLE3 = re.compile(r"^\W{0,3}D\s?\.?\s?(?P<ini>[A-Z])\.\s*(?P<rest>[A-ZÀ-Ž][\wÀ-ž'’-]{2,}.*)$")
OFFICE = re.compile(r"^\W{0,3}[EKHB1]\s*[.\-~]{0,3}\s*[O0]\b|^\W{0,3}[\"“”'’*]+\s*\d?\s*[:;]")
CONSULTAIL = re.compile(r"(?:(?<=[\s.])(?:[TKVJSLMG]|Ug|g)\s*\.(?=\s|$|[A-Z]))+\s*(?:\[\d+\])?\s*$|\s*\[\d+\]\s*$")
# an office in a society, printed where the occupation stands («sekretario N. S. E.»: the check of 2026-10-29, line 10)
SOCOFFICE = re.compile(r"^(?:prezidanto|vicprezidanto|sekretario|kasisto|direktoro|redaktoro)\b.*\b[A-Z]\.\s*[A-Z]\.")
BOX = re.compile(r"\b(?:P\.?\s?O\.?\s*Box|Box|G\.\s?P\.\s?O|Poŝtkesto|Caixa|Casilla|Apartado)\b", re.I)
ROLES = {"D": "delegito de U. E. A.", "DV": "delegito de U. E. A.", "VD": "vicdelegito de U. E. A.", "SD": "subdelegito de U. E. A."}

def code_of(c):
    c = re.sub(r"\s", "", c)
    return "VD" if c.startswith("V") else "SD" if c[:1] in "SZ" else "D"

def junk(s):
    """The consul letters («K. J. V. [21]», «K. VA J. M.g.»), the guide-sheet mark («g.»), the page numbers («— 54 —»,
    «= 44 =») and stray marks: no word of three letters or more."""
    return all(len(w) <= 2 for w in re.findall(r"[A-Za-zÀ-ž]+", s))

def clean(s):
    """The 1912 text's superscripts («D^ro», «S^ino», «C^o») and 1911's «®» as plain letters and a space."""
    return re.sub(r"\s+", " ", s.replace("^", "").replace("®", " ")).strip()

def occupation(r):
    """An occupation in Esperanto, as the lists print it after the name: in lower case, no figure or street word, its noun
    in -o in the first two words («kuracisto», «kolegia profesoro», «direktoro de lernejo en …»), a workplace in -ejo not
    («telegrafa oficejo»), a word in another language not («kammerkontoret»)."""
    r = r.strip(" .;:")
    ws = r.split()
    if not ws or not r[:1].islower() or re.search(r"\d", r) or DX.STREET.search(r) or len(ws) > 7: return False
    return any(w.endswith("o") and not w.endswith("ejo") and len(w) >= 4 for w in ws[:2])

def parse(item, a, b):
    """[(pdf, line no., town, where, code, text)] for each person line, wrapped lines joined; and the lines not known."""
    pages = DX.page_lines(item)
    out, unknown, town, where = [], [], "", ""
    for p in range(a, b + 1):
        if p > a and mixed(pages.get(p - 1, [])): town, where = "", ""
        for n, l in pages.get(p, []):
            s = clean(l)
            if not s or junk(s): continue
            t = POPTAIL.sub("", POP.sub("", PAGENO.sub("", s)))
            # a colon before the town's bracket («Balaton: (Usono, Minnesota).»: the second accuracy check, 2026-10-29,
            # line 1, PETERSON filed under Balakovo, the town before)
            t = re.sub(r"^(\W{0,3}[A-ZÀ-Ž][^():;]{1,45}?)\s*:\s*(?=[(\[])", r"\1 ", t)
            m = TOWN.match(t)
            if m and not ROLE.match(s):
                town, where = m.group("town").strip(" ,."), m.group("where").strip(" ,.)]")
                if not m.group("run"): continue
                s = m.group("run")
            if OFFICE.match(s): out.append([p, n, town, where, "E.-O", s]); continue
            m = ROLE.match(s) or ROLE2.match(s)
            if m:
                out.append([p, n, town, where, code_of(m.group("code")), m.group("rest").strip()]); continue
            m = ROLE3.match(s)
            if m:
                out.append([p, n, town, where, "D", f"{m.group('ini')}. {m.group('rest').strip()}"]); continue
            # THE CODE CARRIED OVER (the editor, 2026-10-29, of «E.-L. KEARNEY, 33, Oakhill Rd. Putney. S. W.»): in the big
            # towns the sub-delegates after the first are printed without «SD :» (1912 London PDF 113, Paris PDF 123,
            # Sydney PDF 137), one a line under the town: a line with a surname in capitals and a comma, after a person
            # of the same town, takes that person's code
            if (out and out[-1][2] == town and town and out[-1][4] != "E.-O" and n - out[-1][1] <= 3
                    and re.match(r"^\W{0,3}(?:[FS]\^?-?ino\s+|S\^?-?ro\s+|D\^?-?ro\s+)?(?:[A-ZÀ-Ž][\wà-ž.'’-]*\s+){0,3}[A-ZÀ-Ž]{3,}[A-ZÀ-Ž'’ -]*,", s)):
                out.append([p, n, town, where, out[-1][4], s]); continue
            m = TOWN2.match(t)
            if m and re.search(r"\)\.?$", t):
                town, where = m.group("town").strip(" ,.\"“'’"), m.group("where").strip(" ,.)]"); continue
            # a wrapped line: the person's address run on («… Hendrik Pontop-» / «pidansgade.»)
            if out and out[-1][0] == p and n - out[-1][1] <= 3 and not out[-1][5].endswith("."):
                out[-1][5] = (out[-1][5][:-1] if out[-1][5].endswith("-") else out[-1][5] + " ") + s; continue
            if out and out[-1][0] == p and n - out[-1][1] <= 3 and re.match(r"^[a-zà-ž\d]|^Str\b", s):
                out[-1][5] = out[-1][5] + " " + s; continue
            m = TOWN2.match(t)
            if m:
                town, where = m.group("town").strip(" ,.\"“'’"), m.group("where").strip(" ,.)]"); continue
            m = TOWN3.match(t)
            if m:
                town, where = m.group("town").strip(" ,.\"“'’"), m.group("where").strip(" ,.)]'"); continue
            if COUNTRYISH.search(t) and ":" not in t:
                town, where = "", ""; unknown.append((p, n, s + "   [the town cleared]")); continue
            if TOWNISH.match(t) and ":" not in t and not re.search(r"\d", t):
                town, where = "", ""; unknown.append((p, n, s + "   [the town cleared]")); continue
            unknown.append((p, n, s))
    return out, unknown

def load_hits(path, items):
    """directory-extract.py's load_hits, these items only (the directories' search, 1.5 GB, holds every directory); PATH
    may name several hits files, comma-separated (1913–1914 searched again after the re-cut, 2026-10-29): a later file's
    items replace an earlier file's hits on them (the old run-together reading kept out)."""
    h = collections.defaultdict(lambda: collections.defaultdict(dict))
    keys = tuple(f"\t{i}\t" for i in items)
    for one in path.split(","):
        hh = load_one(one, keys, collections.defaultdict(lambda: collections.defaultdict(dict)))
        mine = {k[0] for k in hh}
        for k in [k for k in h if k[0] in mine]: del h[k]
        h.update(hh)
    return h

def load_one(path, keys, h):
    with open(path, encoding="utf-8") as fh:
        rows = csv.reader((l for l in fh if l.startswith("person\titem\t") or any(k in l[:300] for k in keys)), delimiter="\t", quoting=csv.QUOTE_NONE)   # 2026-11-10: the roster bug
        hd = next(rows); ix = {k: i for i, k in enumerate(hd)}
        for r in rows:
            if len(r) < len(hd) or r[ix["tier"]] not in ("exact", "near", "confusion") or not r[ix["page"]].isdigit(): continue
            d = h[(r[ix["item"]], int(r[ix["page"]]))][DX.norm(r[ix["as_read"]])]
            if d.get(r[ix["person"]]) != "exact": d[r[ix["person"]]] = r[ix["tier"]]
    return h

def join(hits, item, p, name, town):
    """(label, verdict, how, candidates): as adresaro-extract.py's join."""
    ph = hits.get((item, p), {})
    cands, tiers = {}, {}
    for w in DX.surname_tokens(name):
        for person, tier in ph.get(DX.norm(w), {}).items():
            if len(DX.norm(w)) >= 3: cands.setdefault(person, w); tiers.setdefault(person, tier)
    borne = {pp: DX.borne_out(pp, name, w, town) for pp, w in cands.items()}
    ok = [pp for pp, b in borne.items() if b]
    label = ok[0] if len(ok) == 1 else ""
    pr = DX.profile(label) if label else None
    verdict = ("ne en la nomaro" if not cands else "held: du personoj" if len(ok) > 1 else "held: nur la familia nomo" if not ok
               else "held: profilo ambigua" if not pr or "ambigu" in pr[1].split("\n", 1)[0].lower() or label.endswith("ambiguous")
               else f"held: {tiers[label]} formo" if tiers[label] != "exact" else "line")
    return (label if verdict == "line" else ""), verdict, borne.get(label, ""), "; ".join(f"{pp} ({tiers[pp]}; {borne[pp] or '—'})" for pp in cands)

# THE ESPERANTIAJ ENTREPRENOJ (parser a2; 2026-10-30, the editor: the yearbooks themselves prepared
# with the parsers, all four in the editor's order): the societies that joined U. E. A. as Entreprenoj, «Town. — Group. — P. : NAME ;
# S. : NAME ; K. : NAME. Adr. : …», their officers by the section's own key («P. = prezidanto. S. = sekretario. K. =
# kasisto. Dir. = Direktoro. Pos. = Posedanto.»), from the key to the heading «KOMERCAJ ENTREPRENOJ». 1911 prints its
# associations with no key nor section headings, after the delegates' index of towns (PDF 127, «Pri la Esperantiaj
# Asocioj vidu § 9, 14 de la Statuto.», the runbook's note at D4c), and no date of its own: dated by the yearbook's year.
# Else dated by the closing date the section gives itself
ENTR = {1911: (127, 134, "1911", None),
        1912: (154, 169, "1911-12-10", "kiuj aliĝis kiel Esperantiaj Entreprenoj antaŭ la 10 decembro 1911"),
        1913: (100, 112, "1913-01-01", "kiuj aliĝis kiel Esperantiaj Entreprenoj antaŭ la 1 januaro 1913"),
        1914: (107, 123, "1913-12-01", "kiuj aliĝis kiel Esperantiaj Entreprenoj antaŭ la 1 decembro 1913")}
# the volumes whose Entreprenoj still run two printed pages together (Miles's re-cut of 2026-10-29 took the delegates only)
# (1914 PDF 108–123 read two printed pages across one line, until Miles's re-cut at the gutter, chain
# 2026-10-30-cupel19c-2, RN-2026-10-31-2: every page's share of wide lines 0.00 after it, 0.24–0.57 before)
ENTR_RECUT = {}
STOPE = re.compile(r"KOMERCAJ\s+ENTREPRENOJ")
# a heading of kind «» pauses the reading until the next (1911's preface to the Entreprenoj, PDF 129)
KINDS = [(re.compile(r"Pri la Esperantiaj Asocioj"), "esperantia asocio"), (re.compile(r"Pri la Esperantiaj Entreprenoj"), ""),
         (re.compile(r"^\W{0,4}ESPERANTISTAJ\s+ORGANIZ"), "esperantista organizaĵo"), (re.compile(r"FAKAJ\s+SOCIETOJ"), "faka societo"), (re.compile(r"PROPAGANDAJ\s+ORGANIZ"), "propaganda organizaĵo"),
         (re.compile(r"^\W{0,4}GAZETOJ\b"), "gazeto"), (re.compile(r"NEESPERANTISTAJ\s+ORGANIZ"), "neesperantista organizaĵo")]
# a country's heading in capitals («5 AŬSTRIO-HUNGARUJO», «| a PELGUJO d»), no word in lower case of three letters
CHEAD = re.compile(r"\b([A-ZĈĜĤĴŜŬ][A-ZĈĜĤĴŜŬ-]{2,}(?:UJO|IO|ANDO|ONO|ADO))\b")
SUBHEAD = re.compile(r"^\W{0,4}(?:Lokaj\s+grupoj|Naciaj?\s+societoj?|Federacioj|Regionaj|Internaciaj)\b\W{0,8}\w{0,2}\W{0,4}$")
# a group's heading: «Lwow. — Societo Esperanto. P. : …», the town before the dash; or a society's name with no town,
# by its word for a body («Internacia Asocio de instruistoj. P. : Th. CART.»)
# the OCR's junk after the dash is passed over («Bourg-en-Bresse. — h Esperantista Grupo.», 1913 PDF 103); a town with a
# slash («Frankfurt a/M.»)
EHEAD = re.compile(r"^\W{0,4}(?P<town>[A-ZÀ-Ž][\wÀ-ž'’“”\" ./()-]{1,40}?)\s*[.,]?\s*[—–]+\s*(?:[a-z]{1,2}\s+|\W{1,3})?(?P<rest>[A-ZÀ-Ž«\"„].*)$")
# a group's heading the line-by-line read missed, inside an entry's text («… K. : X. Bourg. — Esperantista Grupo. P. : …»):
# the entry is split there
MIDHEAD = re.compile(r"(?<=[\s.;])(?P<town>[A-ZÀ-Ž][\wÀ-ž'’/-]{2,}(?:[ -](?:[A-ZÀ-Ž][\wÀ-ž'’/-]+|sur|en|am|on|upon|de|la|le|a/M)){0,3})\.\s*[—–]\s*\W{0,3}"
                     r"(?P<group>(?:[A-ZÀ-Ž][\wÀ-ž'’-]*\s+){0,3}(?:Esperant\w*|Grupo|Societo|Klubo|Unuiĝo|Asocio|Rondo|Rondeto|Ligo|Sekcio|Esperanto-\w+)\b[^—.]{0,60}?)(?=\.?\s*[—–]|\.\s)")
# the titles before a name, left out of it before the profile is asked (the first check, 2026-10-30: «Pro RICHARDSON» was
# borne out by «la persona nomo Pro», the priest's title misread, «Abato DELVAUX» by «Abato», «Kolonelo … ROBINSON»)
ETITLE = re.compile(r"^(?:(?:Pro|Pio|Pino|Pastro|Abato|Kolonelo|Kapitano|leŭtenanto|Leŭtenanto|Dv|Do|Dre|D['’]»?|Dr»?|Siuo|Sino|Fino|Fiw|Fiuo|"
                    r"S-ro|S»»|Sro|Fro|Prof\.?|Inĝ\.?|Rev\.?)\s+)+")
ORGW = re.compile(r"\b(?:Societo|Asocio|Ligo|Unuiĝo|Instituto|Klubo|Grupo|Federacio|Komitato|Rondeto|Rondo|Kolo|Esperantejo|Loĝio|"
                  r"Amikaro|Psikistaro|Propagandejo|Oficejo|Sekcio|Esperantistaro|Akademio|Union|Verein|Club|Society)\b", re.I)
TPART = {"de", "la", "le", "les", "sur", "am", "an", "on", "upon", "en", "di", "del", "der", "im", "i", "a"}
# the officers' marks, first match wins (so «V.-P.» before «P.», «S.-K.» before «S.»), each followed by its colon or the
# OCR's semicolon; the misreadings seen: «5.», «$.», «8.», «Ŝ.» for S.; «/).», «/..», «p.», «PP.», «DP.», «MP.» for P.;
# «D.» is no mark of the key (Direktoro is «Dir.»): read as P. misread or a director, the officer is held
EROLES = [("vicprezidanto", r"V\s?\.?\s?-?\s?P"), ("sekretario kaj kasisto", r"[SŜ5]\s?\.?\s?-?\s?K"),
          ("ĝenerala sekretario", r"Ĝen(?:erala|\.)\s*sekretario"), ("direktoro", r"Di[rv]"), ("posedanto", r"Pos"),
          ("redaktoro", r"Red"), ("komitatano", r"Komitatanoj"), ("jura konsilanto", r"Jura\s+konsilanto"),
          ("prezidanto", r"(?:[DM]?PP?|/\)|/\.|p)"), ("sekretario", r"[SŜ5$8]"), ("kasisto", r"[X']?K"), ("?", r"D")]
_ALT = "|".join(f"(?P<r{i}>{p})" for i, (_, p) in enumerate(EROLES))
OMARK = re.compile(r"(?:(?<=[\s;.,|—])|^)(?:" + _ALT + r")\s*[.,'’]{0,3}\s*[:;]\s*")
# a holder after «;» that begins with a mark whose colon the OCR lost («P.: DARNAUD ; 8. PONTE ;», 1913 PDF 104, Ponte
# the secretary): that mark's office; a holder after «;» with no mark at all is held, his office uncertain
PMARK = re.compile(r"^(?:" + _ALT + r")\s*[.,]\s*[»:]?\s*(?=\S)")
# what ends an officer's segment: the society's own fields («Adr. :», «Ejo :», «F. :», «M. :», «Kot. :», «Of. organo :»;
# the address's mark with no colon too, «K. : PILLAULT. Adr. 17, rue Lahire», 1913 PDF 104), a dash, or a sentence that
# is no name («. Societo por disvastigo …»)
TERM = re.compile(r"(?:(?<=[\s;.,|])|^)(?:[“\"„'’]?(?:Adr\b|Ad[»7y][.:]|tdr\b|fir\b)[.'!»”]{0,2}|(?:Ad\.-Ejo|Adv\.-ZEjo|E[jĵ]o|ĵo|F'?|7”|77|M|"
                  r"Kot\w*|Kol|Of|Oficiala\s+organo|Ollciala\s+organo|Organo|Celas|Programoj|Kursoj|Kluboj|Etato|Stato|Filio)\s*[.'!»”]{0,2}\s*[:;])|"
                  r"\s[—–]\s|\.\s+(?=[A-ZÀ-Ž][a-zà-ž]{1,}[,;]?\s+[a-zà-ž]{2,})")
# a group's name ends at its first sentence («Kolo Bosnia. Asocio de la Bosnia-Hercegovina …», «Centra Viena Esperantejo.
# Propagandejo kaj instruejo.»), not inside an abbreviation («(S. F. P. E.)»)
GSTOP = re.compile(r"\.\s+(?=[A-ZÀ-Ž][a-zà-ž])")

def ehead(s, kind=""):
    """(town, group, the offset of the group's end in S) for a group's heading line, else None. A journal's heading
    («Danubo. — Dir. : …») names the journal before the dash, not a town."""
    t = DX.lead(s)
    m = EHEAD.match(t)
    if m and kind == "gazeto" and not TERM.match(t):
        return "", m.group("town").strip(" .,"), m.start("rest"), t
    if m and not ORGW.search(m.group("town")) and all(w[:1].isupper() or w.lower() in TPART or w[:1] in "(" or "/" in w for w in m.group("town").split()):
        rest = m.group("rest")
        e = min([x.start() for x in (OMARK.search(rest), re.search(r"[\s.][—–]", rest), GSTOP.search(rest)) if x] or [len(rest)])
        # a quote mark the OCR set after the town («Paris XVII“. — Grupo Fundamentista …», 1913 PDF 104) left off
        return m.group("town").strip(" .,“”\"'’"), rest[:e].strip(" .,;|—"), len(t) - len(rest) + e, t
    if m and ORGW.search(m.group("town")):
        return "", GSTOP.split(m.group("town"))[0].strip(" .,"), m.end("town"), t
    mo = OMARK.search(t)
    name = t[:mo.start()] if mo else t
    if (t[:1].isupper() and ORGW.search(name) and not TERM.match(t) and len(name.split()) <= 14
            and (mo or name.rstrip().endswith((".", ":", ")")))):
        return "", GSTOP.split(name)[0].strip(" .,;:|"), len(name), t
    return None

def wide(lines):
    """The share of a page's text lines over 90 characters: a printed column holds about 70 (1913 PDF 104), two columns
    read across one line about twice that (1913 PDF 102–103, the first check, 2026-10-30: Bourges and Creusot on one line)."""
    ls = [l for _n, l in lines if len(l.strip()) >= 20]
    return sum(len(l) > 90 for l in ls) / len(ls) if ls else 0.0

# a page with more of its lines over 90 characters is two columns read across: not read. In 1912 and 1913 the gap is clean
# (every single-column page 0.00, every merged one 0.29 or more); 1914's spreads score 0.24 to 0.57, so 1914 is refused
# whole (ENTR_RECUT), not page by page
WIDE = 0.25

def entr_parse(item, a, b):
    """The Entreprenoj's officers: [(pdf, line, kind, country, group, town, head pdf, head line, role, segment, anchor)],
    each officer's group his entry's heading; the entries read, [(pdf, line, kind, country, group, town, officers)]; and
    the pages not read, their columns run together, {pdf: share of wide lines}."""
    pages = DX.page_lines(item)
    merged = {p: round(wide(pages.get(p, [])), 2) for p in range(a, b + 1) if wide(pages.get(p, [])) > WIDE}
    seq = [(p, n, clean(l)) for p in range(a, b + 1) for n, l in pages.get(p, [])]
    # from the range's start to the commercial firms; nothing is read before the first heading the tool knows (the key and
    # the section's preface before it; 1911 prints its key mid-way, PDF 129, between the Asocioj and the Entreprenoj)
    i1 = next((i for i, (p, n, s) in enumerate(seq) if STOPE.search(s)), len(seq))
    kind, country, ents, cur, gap = "", "", [], None, False
    for p, n, s in seq[:i1]:
        k = next((v for r, v in KINDS if r.search(s)), None)
        if k is not None: kind, country, cur = k, "", None; continue
        if p in merged: cur = None; continue
        if not s: gap = True; continue
        was_gap, gap = gap, False
        if not kind or junk(s): continue
        c = CHEAD.search(s)
        if c and not re.search(r"[a-zà-ž]{3,}", s): country, cur = c.group(1).title(), None; continue
        if SUBHEAD.match(s): cur = None; continue
        h = ehead(s, kind)
        # A JOURNAL'S HEADING with a comma or period after its title, no dash («Lingvo Internacia, monata organo …», 1912
        # PDF 167, the first check: Cart filed under the Germana Esperanto-Gazeto above): a title opening a line, its words
        # capitalised (particles apart), two of them or more, or one with «. —» after it («Esperanto. — Duonmonata …»);
        # never a field («Jarabono : 2 Sm.») nor a sentence («Semajna, tute esperanta gazeto»)
        mt = re.match(r"^\W{0,3}[\"„«]?(?P<t>[A-ZÀ-Ž][^.,—:;]{2,40}?)\s*(?P<p>[.,]\s*—|[.,—])", DX.lead(s)) if kind == "gazeto" and not h else None
        if mt and not TERM.match(DX.lead(s)):
            tw = mt.group("t").split()
            caps = all(w[:1].isupper() or w.lower() in TPART for w in tw) and sum(w[:1].isupper() for w in tw) >= (1 if "—" in mt.group("p") else 2)
            if caps: h = ("", mt.group("t").strip(), mt.end("t"), DX.lead(s))
        # A BODY'S NAME WITH NO WORD FOR A BODY, after a blank line, its fields on the line («Paix par le droit (Paco per la
        # Juro). Adr.: 13, faubourg Saint-», 1911 PDF 129, the check of 2026-10-30d: Ruyssen filed under the paragraph above)
        if not h and was_gap:
            t = DX.lead(s)
            f = min([x.start() for x in (TERM.search(t), OMARK.search(t)) if x] or [-1])
            if f > 0 and t[:1].isupper() and t[:f].rstrip().endswith((".", ").")) and 2 <= len(t[:f].split()) <= 14:
                h = ("", t[:f].strip(" .,;:|"), f, t)
        if h:
            town, group, off, t = h
            cur = {"pdf": p, "line": n, "kind": kind, "country": country, "group": group, "town": town, "text": t[off:], "where": [(0, p, n)]}
            ents.append(cur); continue
        if cur is None: continue
        cur["where"].append((len(cur["text"]) + 1, p, n))
        # a word broken at the line's end, a surname in capitals too («Sino RAS-» / «MUSSEN», 1912 PDF 157)
        broken = cur["text"].endswith("-") and (s[:1].islower() or (re.search(r"[A-ZĈĜĤĴŜŬ]{2}-$", cur["text"]) and s[:2].isupper()))
        cur["text"] = (cur["text"][:-1] + s) if broken else (cur["text"] + " " + s)
    # an entry with a missed heading inside it is split there (the first check, 2026-10-30: La Rochelle's officers under
    # Bourg-en-Bresse, 1913 PDF 103)
    split = []
    for e in ents:
        cuts = [m for m in MIDHEAD.finditer(e["text"]) if m.start() > 0]
        if not cuts: split.append(e); continue
        bounds = [0] + [m.start() for m in cuts] + [len(e["text"])]
        for k in range(len(bounds) - 1):
            a0, b0 = bounds[k], bounds[k + 1]
            if k == 0: town, group, t0 = e["town"], e["group"], 0
            else: m = cuts[k - 1]; town, group, t0 = m.group("town"), m.group("group").strip(" .,"), m.end() - a0
            w = [(x - a0, p, n) for x, p, n in e["where"] if a0 <= x < b0]
            w0 = [x for x in e["where"] if x[0] <= a0][-1]
            w = [(0, w0[1], w0[2])] + [x for x in w if x[0] > 0]
            split.append(dict(e, pdf=w[0][1], line=w[0][2], town=town, group=group, text=e["text"][a0:b0][t0:] if k else e["text"][a0:b0],
                              where=[(max(0, x - t0) if k else x, p, n) for x, p, n in w]))
    out, read = [], []
    for e in split:
        text, offs = e["text"], []
        ms = list(OMARK.finditer(text))
        for k, m in enumerate(ms):
            role = EROLES[int(next(g for g, v in m.groupdict().items() if v is not None)[1:])][0]
            stop = ms[k + 1].start() if k + 1 < len(ms) else len(text)
            tm = TERM.search(text, m.end(), stop)
            seg = text[m.end():tm.start() if tm else stop]
            # a colon left in the segment is the next mark's, the mark misread («S.: KLEINER : K. o SCnxwipro»); a period
            # and the margin's bar end the entry («E. ROBERT. | Kotizaĵoj : 4 Sm.»)
            seg = re.split(r"\s*:\s*|\.\s*\|\s", seg)[0].strip(" .,;:|")
            w = [x for x in e["where"] if x[0] <= m.start()]
            p, n = w[-1][1:] if w else (e["pdf"], e["line"])
            # several holders: at «;», and for the committee at «,» too («Komitatanoj : CHAIGNEAU, SCHRIEWER, J. DE NOGALES»)
            parts = [x.strip(" .,;:|") for x in seg.split(";")]
            if role == "komitatano": parts = [y.strip(" .") for x in parts for y in x.split(",")]
            for j, x in enumerate(parts):
                # the anchor from the holder's own words (the first check: Wolf's line quoted the committee's first names),
                # the mark's for the first holder
                a0 = m.start() if j == 0 else max(text.find(x, m.end()), m.start())
                anc = " ".join(text[a0:].split()[:max(6, min(len(x.split()) + 2, 12))])
                r = role
                if j and role != "komitatano":
                    pm = PMARK.match(x)
                    if pm: r = EROLES[int(next(g for g, v in pm.groupdict().items() if v is not None)[1:])][0]; x = x[pm.end():].strip(" .,;:|»")
                    else: r = "+" + role
                if len(re.sub(r"[^A-Za-zÀ-ž]", "", x)) >= 3:
                    out.append((p, n, e["kind"], e["country"], e["group"], e["town"], e["pdf"], e["line"], r, x, anc)); offs.append(r)
        read.append((e["pdf"], e["line"], e["kind"], e["country"], e["group"], e["town"], offs))
    return out, read, merged

_GZT = {}
def gz_town(gz, town, country):
    """The gazetteer's row for a society's town: as the delegates look it up (the printed form and its country), else the
    one joined article of that printed form, whatever its country (the Entreprenoj print the country as a heading, not
    beside the town, and in another form: «AŬSTRIO-HUNGARUJO»)."""
    g = gz.get(("OfJ", town, country, ""))
    if g and g["article"]: return g
    if not _GZT:
        for (src, f, c, q), r in gz.items():
            if src == "OfJ" and r["article"]: _GZT.setdefault(f, []).append(r)
    rs = _GZT.get(town, [])
    # not found as printed: with one measured OCR confusion undone, as the gazetteer's own resolve does («Orlĉans» →
    # «Orléans», 1912 PDF 160)
    if not rs:
        for f, *_ in GZ.emended(town):
            rs = _GZT.get(f, [])
            if rs: break
    return rs[0] if len({r["article"] for r in rs}) == 1 else None

def entreprenoj(a, gz, years):
    """--part entreprenoj: the officers of the Esperantiaj Entreprenoj as fact lines, the delegates' join and gazetteer."""
    if a.show:
        for y in years:
            pa, pb, _d, _q = ENTR[y]
            out, read, merged = entr_parse(VOLS[y][0], pa, pb)
            print(f"{y}: pages not read, two columns run together (share of lines over 90 characters): " + (", ".join(f"PDF {p} ({s})" for p, s in merged.items()) or "none"))
            pl = DX.page_lines(VOLS[y][0])
            print(f"{y}: every page's share: " + ", ".join(f"{p} {wide(pl.get(p, [])):.2f}" for p in range(pa, pb + 1)))
            for p, n, kind, country, group, town, offs in read:
                if p == a.show: print(f"{y} PDF {p} l. {n} · {kind} · {country} · «{group}» · town «{town}» · {', '.join(offs) or 'no officer read'}")
            for r in out:
                if r[0] == a.show: print(f"   {r[8]}: «{r[9]}» · {DX.split_name(r[9])} [{r[10]}]")
        return
    if not (a.hits and a.tag): sys.exit("--hits and --tag are needed")
    outs = {k: os.path.join(D, f) for k, f in (("ret", f"facts-return-{a.tag}-entreprenoj.md"), ("tsv", f"entreprenoj-{a.tag}.tsv"), ("rev", f"ENTREPRENOJ-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    hits = load_hits(a.hits, [VOLS[y][0] for y in years])
    rows, lines, noofficer, notread, cnt = [], [], [], [], collections.Counter()
    for y in years:
        item = VOLS[y][0]
        DX.SELF_KEY = KEYS[item]   # this volume's own tool lines bear nothing out (borne_out, 2026-11-01)
        pa, pb, date, proof = ENTR[y]
        out, read, merged = entr_parse(item, pa, pb)
        notread += [f"{y} PDF {p} ({s})" for p, s in merged.items()]
        cnt["pages not read (columns run together)"] += len(merged)
        cnt["entries"] += len(read)
        noofficer += [(y,) + r[:6] for r in read if not r[6]]
        for p, n, kind, country, group, town, hp_, hl_, role, seg, anc in out:
            cnt["officers"] += 1
            # one holder or several at «,» («S.: L. DEMARGY,. J. AIZIERE»): every chunk a name, none an address
            # an initial's period read as a comma («M.-M, KOVALEVSKIJ», «S,-A. VENGEROV», 1912 PDF 167)
            seg = re.sub(r"\b([A-ZÀ-Ž]),(?=-[A-ZÀ-Ž]\.)", r"\1.", seg)
            seg = re.sub(r"\b([A-ZÀ-Ž]\.-[A-ZÀ-Ž]|[A-ZÀ-Ž]),\s*(?=[A-ZÀ-ŽĈĜĤĴŜŬ]{3})", r"\1. ", seg)
            ch = [c.strip(" .") for c in seg.split(",") if c.strip(" .")]
            namelike = lambda c: re.search(r"[A-ZÀ-Ž]{3}", c) and not re.search(r"\d", c) and not DX.STREET.search(c) and len(c.split()) <= 5
            holders = ch if role != "komitatano" and len(ch) > 1 and all(namelike(c) for c in ch) else [seg]
            for hs in holders:
                name, rest = DX.split_name(re.sub(r"[{}·]", "", hs))
                # the titles off, and the margin's junk after the name («J. JACOBS. ki ]», «Lamb. ). J. M. POELL»)
                name = ETITLE.sub("", name.strip(" »«\"“")).strip()
                name = re.sub(r"(?<!\S)[^\w\s]+(?!\S)", " ", name)
                name = re.sub(r"(?:\s+[a-zà-ž]{1,2})+\s*$", "", re.sub(r"\s+", " ", name)).strip(" .,;")
                rest = [re.sub(r"[{}·]", "", r) for r in rest if r.strip(" .")]
                g = gz_town(gz, town, country) if town else None
                if g: tk, tshown, tnote = GZ.town_line(g, town); tnote = f"; {tnote}"
                else: tk = tshown = town; tnote = ""
                # the name ends at its first sentence's period after a word («Grupo Esperantista. 2. : M-J, EvRor», 1911
                # PDF 132, a mark misread), never inside an abbreviation («(S. F. P. E.)»)
                gname = re.split(r"(?<=[a-zà-ž]{3})\.\s", re.sub(r"\s+", " ", re.sub(r"[{}·|]", "", group)))[0].strip(" .,;—-\"“„")
                # a guillemet left open or closed alone («« Esperanta Sekcio» »», «« Vestnik»)
                if gname.count("«") != gname.count("»"): gname = re.sub(r"\s+", " ", gname.replace("«", " ").replace("»", " ")).strip()
                # the OCR's marks inside a name («Tutruslanda ~= Kuracista Societo», run g)
                gname = re.sub(r"\s[~=|^]+(?=\s)", "", gname)
                # «two persons» in one entry («V.-P. KOROLENKO kaj M.-A. STAĤOVIĜ»): the first, the second left to the review
                if " kaj " in name: name = name.split(" kaj ")[0].strip()
                obj = gname if not town or f" en {town}" in f" {gname}" else f"{gname} en {tk}"
                if not re.search(r"[A-Za-zÀ-ž]{3}", gname): verdict, label, how, cands = "held: grupo sen nomo", "", "", ""
                # a town for the group's name, the name not read («estas prezidanto de la Bradford», run g: Bradford,
                # Bourges, Paris)
                elif len(gname.split()) <= 2 and (gz_town(gz, gname, country) or GZ.resolve(gname, country)[0]): verdict, label, how, cands = "held: grupo sen nomo", "", "", ""
                elif role == "?": verdict, label, how, cands = "held: la ofico ne legebla («D.»)", "", "", ""
                elif role.startswith("+"): verdict, label, how, cands = "held: la ofico ne certa (post «;», sen marko)", "", "", ""
                # far below his group's heading (the text's lines, blank ones too): a heading the parse missed between
                elif n - hl_ > 12: verdict, label, how, cands = "held: malproksime de la grupo", "", "", ""
                elif len(name.split()) > 6: verdict, label, how, cands = "held: la nomo ne legebla", "", "", ""
                else: label, verdict, how, cands = join(hits, item, p, name, town)
                cnt[verdict.split(" («")[0]] += 1
                rows.append([y, p, n, kind, country, gname, town, role, name, " | ".join(rest), cands, verdict])
                if not label: continue
                head, _t, hp = DX.profile(label)
                loc = f"{KEYS[item]}, PDF {p}, l. {n}"
                thin = how.startswith("la inicialoj") and len(how.split()) == 3
                dnote = f"⟦pruvo: «{proof}»⟧" if proof else "⟦la jaro de la jarlibro⟧"
                conf = f"📣{' ❓' if thin else ''} (sen fontindiko; {dnote}; ⟦identigo: {head}, laŭ {how} en la profilo⟧{tnote})"
                shown = DX.clean_name(name) or name
                # a title misread before the initials left off («Pmo Ĉ.-B. CLARK», «Div A. ŜESTAKOV», «Pre O. BUJWID»)
                shown = re.sub(r"^(?:[A-ZÀ-Ž][a-zà-ž]{0,3}|[A-Z]{2})\s+(?=[A-ZÀ-Ž]\.)", "", shown)
                de = obj if re.match(r"(?:La|The|Le|Die|Der|Het)\s", obj) else "la " + obj
                if tshown != tk: de = de.replace(f" en {tk}", f" en {tshown}")
                lines.append(f"- $$$ {hp} **{date}** · {{ofico: {role}, {obj}}} · {shown} estas {role} de {de}. · {anc} · {loc} · [G] · {conf}")
                addr = [r for r in rest if not occupation(r) and not DX.DEGREE.match(r.strip())
                        and (len(re.sub(r"[^A-Za-zÀ-ž0-9]", "", r)) >= 2 or re.fullmatch(r"\s*\d\s*", r))]   # as the delegates'
                if not any(re.search(r"\d", r) or DX.ADDR.search(r) for r in addr): addr = []
                at = DX.town_of(", ".join(addr)) if addr else ""
                if addr and at:
                    lines.append(f"- $$$ {hp} **{date}** · {{loĝado: {at}}} · {shown} loĝas ĉe {', '.join(addr).strip(' .;:|[')}. · {anc} · {loc} · [?] · {conf}")
                # (never a street: «Ch. BRUNET estas cours Victor-Hugo», run g)
                for o in [r.strip(" .;:") for r in rest if occupation(r) and not re.match(r"(?i)(?:cours|rue|r\.|bd|av|pl\.|place|quai|str|via|calle)\b", r.strip())]:
                    lines.append(f"- $$$ {hp} **{date}** · {{profesio: {o}}} · {shown} estas {o}. · {anc} · {loc} · [?] · {conf}")
    cnt["lines"] = len(lines)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    with open(outs["tsv"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["year", "pdf", "line", "kind", "country", "group", "town", "role", "name as printed", "the rest", "roster hits (borne out by)", "verdict"]); w.writerows(rows)
    with open(outs["ret"], "x", encoding="utf-8") as fh:
        fh.write(f"# Return: facts-return-{a.tag}-entreprenoj.md\n\n`[Written by tools/oficiala-jarlibro-extract.py --part entreprenoj, {a.tag}, from the name search {os.path.basename(a.hits)}: the officers of the Esperantiaj Entreprenoj (the societies that joined U. E. A.), {', '.join(map(str, years))}, roster persons only, each borne out by the profile (runbook D4c). Not a legilo's return.]`\n\n")
        fh.write("\n".join(lines) + "\n")
    held = [r for r in rows if r[11].startswith("held")]
    with open(outs["rev"], "x", encoding="utf-8") as fh:
        fh.write(f"# The Oficiala Jarlibro's Esperantiaj Entreprenoj, read by tool ({a.tag})\n\n`[GENERATED by tools/oficiala-jarlibro-extract.py --part entreprenoj. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". Every officer parsed: `{os.path.basename(outs['tsv'])}`; the lines: `{os.path.basename(outs['ret'])}`." + (" Not read yet, the columns run together: " + "; ".join(ENTR_RECUT.values()) + "." if ENTR_RECUT else "") + "\n\n")
        fh.write(f"## Pages not read, two columns read across one line: {len(notread)} (the share of lines over 90 characters; for the re-cut at the gutter)\n\n" + "".join(f"- {x}\n" for x in notread) + "\n")
        fh.write(f"## Held: {len(held)}\n\n")
        for r in held: fh.write(f"- {r[0]}, PDF {r[1]}, l. {r[2]} · {r[5]} ({r[6] or '?'}) · {r[7]}: «{r[8]}» · {r[10]} · {r[11]}\n")
        fh.write(f"\n## Entries with no officer read: {len(noofficer)}\n\n")
        for y, p, n, kind, country, group, town in noofficer: fh.write(f"- {y}, PDF {p}, l. {n} · {kind} · «{group[:120]}» ({town or '?'})\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hits"); ap.add_argument("--tag"); ap.add_argument("--write", action="store_true")
    ap.add_argument("--part", choices=["delegitoj", "entreprenoj"], default="delegitoj", help="the delegates' address book (the default), or the Esperantiaj Entreprenoj's officers")
    ap.add_argument("--years")
    ap.add_argument("--show", type=int, help="print the parse of this PDF page of each volume asked for, and stop")
    ap.add_argument("--gazetteer", help="the gazetteer build whose towns the lines take (profiles/gazetteer/GAZETTEER-FORMS-TAG.tsv)")
    a = ap.parse_args()
    gz = GZ.forms(a.gazetteer) if a.gazetteer else {}
    if a.part == "entreprenoj":
        years = [int(y) for y in a.years.split(",")] if a.years else [y for y in ENTR if y not in ENTR_RECUT]
        for y in years:
            # --show still measures a refused volume's pages (which want the re-cut), and writes nothing
            if y in ENTR_RECUT and not a.show: sys.exit(f"{y}: not read, its columns run together ({ENTR_RECUT[y]}): waits for the re-cut at the gutter")
            if y not in ENTR: sys.exit(f"{y}: prints no Esperantiaj Entreprenoj")
        return entreprenoj(a, gz, years)
    years = [int(y) for y in (a.years or ",".join(str(y) for y in VOLS)).split(",")]
    for y in years:
        if y in RECUT: sys.exit(f"{y}: not read, its columns run together ({RECUT[y]}): waits for the re-cut at the gutter")
        if y not in VOLS: sys.exit(f"{y}: no such volume")
    if a.show:
        for y in years:
            item = VOLS[y][0]
            out, unknown = parse(item, a.show, a.show)
            for p, n, town, where, code, t in out:
                name, rest = DX.split_name(t)
                print(f"{y} PDF {p} l. {n} · {town} ({where}) · {code} · «{name}» · {rest}")
            for p, n, s in unknown: print(f"{y} PDF {p} l. {n} · ?? «{s}»")
        return
    if not (a.hits and a.tag): sys.exit("--hits and --tag are needed")
    outs = {k: os.path.join(D, f) for k, f in (("ret", f"facts-return-{a.tag}-delegitoj.md"), ("tsv", f"delegitoj-{a.tag}.tsv"), ("rev", f"DELEGITOJ-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    hits = load_hits(a.hits, [VOLS[y][0] for y in years])
    rows, lines, unknowns, cnt = [], [], [], collections.Counter()
    for y in years:
        item, pa, pb, date, proof = VOLS[y]
        DX.SELF_KEY = KEYS[item]   # this volume's own tool lines bear nothing out (borne_out, 2026-11-01)
        out, unknown = parse(item, pa, pb)
        held_pages = mixed_pages(item, pa, pb)
        unknowns += [(y,) + u for u in unknown]
        cnt["unknown lines"] += len(unknown)
        for p, n, town, where, code, t in out:
            if code == "E.-O": cnt["offices"] += 1; continue
            cnt["persons"] += 1
            name, rest = DX.split_name(re.sub(r"[{}·]", "", t))
            # the consul letters and the members' count run on to the address («…, rue X. J. V.», «[19]»: the accuracy
            # check of 2026-10-29, lines 5 and 27), left out
            rest = [re.sub(r"[{}·]", "", r) for r in rest]
            if rest: rest[-1] = CONSULTAIL.sub("", rest[-1])
            rest = [r for r in rest if r.strip(" .")]
            if p in held_pages:
                cnt["held: kolumnoj kunfluintaj"] += 1; rows.append([y, p, n, town, code, name, " | ".join(rest), "", "held: kolumnoj kunfluintaj"]); continue
            if not town: cnt["held: sen urbo"] += 1; rows.append([y, p, n, "", code, name, " | ".join(rest), "", "held: sen urbo"]); continue
            label, verdict, how, cands = join(hits, item, p, name, town)
            cnt[verdict] += 1
            rows.append([y, p, n, town, code, name, " | ".join(rest), cands, verdict])
            if not label: continue
            head, _t, hp = DX.profile(label)
            role = ROLES[code]
            loc = f"{KEYS[item]}, PDF {p}, l. {n}"
            anc = " ".join(f"{code} : {t}".split()[:12])
            thin = how.startswith("la inicialoj") and len(how.split()) == 3
            # THE TOWN BY THE GAZETTEER (the editor, 2026-10-29: a gazetteer; Tŭbingen is Tübingen): the
            # Esperanto name in the key, the national name beside it in the sentence; unjoined, as printed
            g = gz.get(("OfJ", town, where.split(",")[0].strip(), ""))
            if g and g["article"]: tk, tshown, tnote = GZ.town_line(g, town); tnote = f"; {tnote}"; cnt["towns by the gazetteer"] += 1
            else: tk = tshown = town; tnote = ""
            conf = f"📣{' ❓' if thin else ''} (sen fontindiko; ⟦pruvo: «{proof}»⟧; ⟦identigo: {head}, laŭ {how} en la profilo⟧{tnote})"
            shown = DX.clean_name(name) or name
            lines.append(f"- $$$ {hp} **{date}** · {{ofico: {role}, {tk}}} · {shown} estas {role} en {tshown}. · {anc} · {loc} · [G] · {conf}")
            occ = [r.strip(" .;:") for r in rest if occupation(r)]
            # the address: every chunk after the name that is no occupation or degree, where any of them has a house number
            # or a street word (the first run cut «Van Ostadestraat, 94» to «94», the street word inside the word); a house
            # number of one figure kept («9, East Me. Millian str.», «Heros, 6, 4o»: the accuracy check of 2026-11-01, lines
            # 10 and 21)
            addr = [r for r in rest if not occupation(r) and not DX.DEGREE.match(r.strip())
                    and (len(re.sub(r"[^A-Za-zÀ-ž0-9]", "", r)) >= 2 or re.fullmatch(r"\s*\d\s*", r))]
            if not any(re.search(r"\d", r) or DX.ADDR.search(r) for r in addr): addr = []
            if addr:
                where_ = ", ".join(addr).strip(" .;:|[")
                # a post-office box is an address, not a dwelling (the check, line 14: «PO. Box, 883»)
                said = f"havas la poŝtan adreson {where_}" if BOX.search(where_) else f"loĝas ĉe {where_}"
                # the town with its national name in brackets after a comma, not in brackets again («(Liono (Lyon))»)
                tw = f", en {tshown}" if "(" in tshown else f" ({tshown})"
                lines.append(f"- $$$ {hp} **{date}** · {{loĝado: {tk}}} · {shown} {said}{tw}. · {anc} · {loc} · [?] · {conf}")
            for o in occ:
                if SOCOFFICE.match(o):
                    lines.append(f"- $$$ {hp} **{date}** · {{ofico: {o}}} · {shown} estas {o}. · {anc} · {loc} · [G] · {conf}"); continue
                lines.append(f"- $$$ {hp} **{date}** · {{profesio: {o}}} · {shown} estas {o}. · {anc} · {loc} · [?] · {conf}")
    cnt["lines"] = len(lines)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    os.makedirs(D, exist_ok=True)
    with open(outs["tsv"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["year", "pdf", "line", "town", "code", "name as printed", "the rest", "roster hits (borne out by)", "verdict"]); w.writerows(rows)
    with open(outs["ret"], "x", encoding="utf-8") as fh:
        fh.write(f"# Return: facts-return-{a.tag}-delegitoj.md\n\n`[Written by tools/oficiala-jarlibro-extract.py, {a.tag}, from the name search {os.path.basename(a.hits)}: the Oficiala Jarlibro's delegates, vice-delegates and sub-delegates, {', '.join(map(str, years))}, roster persons only, each borne out by the profile (runbook D4c). Not a legilo's return.]`\n\n")
        fh.write("\n".join(lines) + "\n")
    held = [r for r in rows if r[8].startswith("held")]
    with open(outs["rev"], "x", encoding="utf-8") as fh:
        fh.write(f"# The Oficiala Jarlibro's delegates, read by tool ({a.tag})\n\n`[GENERATED by tools/oficiala-jarlibro-extract.py. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". Every person line parsed: `{os.path.basename(outs['tsv'])}`; the lines: `{os.path.basename(outs['ret'])}`." + (" Not read yet, the columns run together: " + "; ".join(RECUT.values()) + "." if RECUT else "") + "\n\n")
        fh.write(f"## Held: {len(held)}\n\n")
        for r in held: fh.write(f"- {r[0]}, PDF {r[1]}, l. {r[2]} · {r[3] or '?'} · {r[4]}: «{r[5]}» · {r[7]} · {r[8]}\n")
        fh.write(f"\n## Lines the parse did not know: {len(unknowns)}\n\n")
        for y, p, n, s in unknowns: fh.write(f"- {y}, PDF {p}, l. {n}: «{s[:160]}»\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

if __name__ == "__main__":
    main()
