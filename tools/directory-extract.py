#!/usr/bin/env python3
"""The directory extractor (runbook D4c; 2026-10-27, the editor): the entries of an address book or directory read by tool, not by legiloj, and
written as fact lines for the persons already on the roster only.

    tools/directory-extract.py jarlibro-societies --hits HITS.tsv --tag TAG [--years 1904,1906] [--write]

jarlibro-societies: the groups-and-societies part of the *Tutmonda Jarlibro Esperantista* 1904–1910 (ÖNB ANNO e4d; the
members' lists, read across their columns by the OCR, wait for Miles's re-cut at the gutters). Each group: its name and
town, and its officers as printed («— Pr., W. H. Woodcock, esq. Sek., S. G. Throssell, Holy Bank, Latchford»; from 1908
«Prez. : … — Sek. : …», the U. E. A. delegate and the consul beside the group). An officer becomes a line only when:
  - a strong hit of the name search (HITS, `ocr-dowse.py --strong-only` over the seven volumes) on that page falls inside
    the printed name, so the person is on the roster; and
  - the person's profile bears the identification out: the group's town, or the printed initials or forename before the
    surname. A hit with neither, or with two roster persons borne out, is held, listed in the review, and makes no line.
Lines per officer: {ofico: ‹role›, ‹group›}; {loĝado: ‹town›} where an address is printed with the name; {profesio: …}
where an Esperanto occupation is. Dated by the volume's year (⟦la jaro de la jarlibro⟧). Writes, with --write:
  dowse/tutmonda-jarlibro-esperantista/facts-return-TAG-societies.md   (the lines, in the full form: for the assembler)
  dowse/tutmonda-jarlibro-esperantista/societies-TAG.tsv               (every officer parsed, with the verdict)
  dowse/tutmonda-jarlibro-esperantista/SOCIETIES-REVIEW-TAG.md         (the counts, the held, a sample of each kind)
It refuses to overwrite any of them. Without --write it prints the counts. Ezri."""
import argparse, collections, csv, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "dowse", "tutmonda-jarlibro-esperantista")
PROFILES = os.path.join(G, "profiles")
csv.field_size_limit(sys.maxsize)

# THE SOCIETIES' PAGES (2026-10-27, the pages with «fondita» in runs; the members' pages have none): each volume's runs
PARTS = {1904: [(5, 20), (237, 239)], 1905: [(3, 24), (303, 306)], 1906: [(5, 41), (393, 397)], 1907: [(111, 348)],
         1908: [(59, 176), (193, 193)], 1909: [(55, 188), (238, 238)], 1910: [(9, 213)]}
ITEM = "ANNO_e4d_{y}0005"
KEY = "tutmonda-jarlibro-esperantista-{y}-anno-0005"

# «fondita» as the OCR prints it: londita, Iondita, ondita, &ondita, ©ndita, fondira, fondila, o1fondita
FOND = re.compile(r"(?<![a-zĉĝĥĵŝŭ])[fFlLI1©&]?[oO0©]?n[dl][il1][tlr]a\b")
GROUPHEAD = re.compile(r"^\W{0,3}(?:G\.\s?E\.|E\.\s?G\.|E\.\s?K\.|K\.\s?E\.|Esperanta\s+(?:Klubo|Grupo|Societo)|Klubo|Societo|Grupo)(?!\w).{0,60}\ben\s+[A-ZÀ-Ž]")
PLACEHEAD = re.compile(r"^\W{0,3}[A-ZÀ-Ž][\wÀ-ž'’-]+(?:[ -][\wÀ-ž'’-]+){0,3}\s*\.?$")
# the officers' marks, first match wins at a place (so «Pr. kaj Sek.» before «Pr.», «Hon. pr.» before «Pr.»); each must be
# followed by its stop («.», «,», «:», «;»), so «Pr» inside «Königsberg-i.-Pr.» and a surname «Sek…» are not taken
ROLES = [("honora prezidanto", r"Hon(?:ora)?[^\w\s]{0,3}\s*[pP]r(?:ez(?:idanto)?)?"),
         ("prezidanto kaj sekretario", r"Pr(?:ez)?\.?\s*(?:kaj\s*|-)[Ss]ek(?:r)?"),
         ("ĝenerala sekretario", r"Sek(?:r)?\.?\s*generala"),
         ("vicprezidanto", r"V[iaĉe][cĉe]\s*-?\s*p(?:r(?:ez)?)?"),
         ("sekretario kaj kasisto", r"Sek(?:r)?\.?\s*-?\s*[Kk]as(?:isto)?"),
         ("prezidanto", r"(?<![-\w])Pr(?:ez(?:idanto)?)?"),
         ("helpanta sekretario", r"Helpanta\s+sek"),
         ("deputata sekretario", r"Deputata-?\s*Sek"),
         ("sekretariino", r"Sekretariino"),
         ("honora sekretario", r"Hon\.?\s*Sek"),
         ("sekretario", r"(?<![-\w])(?:I{1,2}\.\s*)?Sek(?:r|retario)?"),
         ("kasisto", r"(?<![-\w])Kas(?:isto)?"),
         ("bibliotekisto", r"Bibliotekisto"),
         ("korespondanto", r"korespondanto"),
         ("delegito de U. E. A.", r"Delegito\s*\(?U\.?\s*E\.?\s*A\.?\)?"),
         ("konsula agento", r"Konsul-?\s*Agento"),
         ("konsulo", r"Konsulo"),
         ("komitatano", r"Aliaj\s+[Kk]omitatanoj")]
ROLE = re.compile("(?:" + "|".join(f"(?P<r{i}>{p})" for i, (_, p) in enumerate(ROLES)) + r")(?:\s*[.,:;])+\s*")
# the titles before a name, left out of it
TITLE = re.compile(r"^(?:(?:D['’'”»°o9?]*\s*r?o?\.?|Dr\.?|Dro|med\.|Prof\.?|Rev\.?|pastro|S-?ro|Sro|Sino|Sinjoro|F[i'’”\"]?[nrw]?[o9»”]?|"
                   r"Fino|Firo|Fiw|Siro|Kol\.?|Col\.?|Lt\.?|Lieut\.?|lieut\.-colonel|Sir|Hon\.?|D\.|R\. P\.|Kapitano)\s+)+")
OCC = re.compile(r"^(?:[a-zĉĝĥĵŝŭ][a-zĉĝĥĵŝŭ-]*(?:isto|ero|oro|anto|into|ulo|iko|estro|ano|ario|ento)|pastro|advokato|notario|"
                 r"instruisto|studento|lernanto|oficisto|kuracisto|presbitero|eksoficiro)(?:\s+(?:de|en|ĉe|el)\s+[^,.;]{1,40})?$")
ADDR = re.compile(r"\d|\w(?:str|strasse|straße|gatan|gade|weg|gasse|platz|ulica|utca)\b|\b(?:str|street|rd|road|rue|place|avenue|ave|ter|terrace|square|lane|ul|ulica|platz|gasse|weg|calle|"
                  r"plaza|via|straat|laan|boul|bd)\b\.?", re.I)
STREET = re.compile(ADDR.pattern.split("|", 1)[1], re.I)
DEGREE = re.compile(r"^(?:esq|B\.\s?A|M\.\s?A|L\.\s?L\.\s?D|C\.\s?I\.\s?E|F\.\s?R\.\s?P\.\s?S|D\.\s?lit|A\.\s?C\.\s?P|F\.\s?B\.\s?E\.\s?A|\[[PS]\]?|\(?[PS]\)?)\.?$", re.I)
STOPW = {"esq", "kaj", "de", "la", "en", "ĉe", "of", "the", "and", "von", "van", "der", "den", "le", "du", "des", "y"}

def page_lines(item):
    """{pdf page: [(line number in the text, line)]} of the item's preferred text."""
    out, p = {}, None
    with open(os.path.join(G, "sources", "ocr-preferred", item + ".txt"), encoding="utf-8") as fh:
        for n, l in enumerate(fh, 1):
            m = re.match(r"=== page (\d+) ===", l)
            if m: p = int(m.group(1)); out[p] = []; continue
            if p is not None: out[p].append((n, l.rstrip("\n")))
    return out

def norm(w):
    return re.sub(r"[^\wĉĝĥĵŝŭ'-]", "", w.lower()).strip("'-")

def entries(pages, runs, late=False):
    """The groups in the pages: [{pdf, line, group, town, body: [(n, text)]}], a group from its «fondita» line to the
    next group's heading. The heading: the line's text before «fondita», else the last non-empty line above it."""
    seq = [(p, n, t) for a, b in runs for p in range(a, b + 1) for n, t in pages.get(p, [])]
    starts = []
    for i, (p, n, t) in enumerate(seq):
        m = FOND.search(t)
        if not m or m.start() > 90:
            # a group's name with no «fondita» the OCR could read below it («G. E. Fajrero en Rusĉuk (Roustchouk),» /
            # «pon la 159 Ae februaro 1903», 1904 PDF 9): its name starts it all the same, or its officers go to the
            # group above
            if GROUPHEAD.match(t.strip()) and not any(FOND.search(seq[x][2]) for x in range(i, min(i + 3, len(seq)))):
                starts.append((i, i, t.strip(" ,;|")))
            continue
        head = lead(t[:m.start()].strip(" ,;|"))
        j = i
        if len(re.sub(r"[^A-Za-zÀ-ž]", "", head)) < 4:
            j = i - 1
            while j >= 0 and len(seq[j][2].strip()) < 4: j -= 1
            head = seq[j][2].strip(" ,;|") if j >= 0 else ""
        # a name over two lines («Societo Esperanto por ellernado kaj dissemado de Esperanto» / «inter Angleparolantaj
        # popoloj,»): the line above joins it when this one starts in lower case
        if head[:1].islower() and j > 0:
            x = j - 1
            while x >= 0 and not seq[x][2].strip(): x -= 1
            if x >= 0: head = seq[x][2].strip(" ,;|") + " " + head; j = x
        starts.append((j, i, head))
    # FROM 1908 THE TOWN HEADS ITS GROUPS, on a line of its own («Brighton» / «(Sussex).»), and the U. E. A. delegate and the
    # consul stand under it, before or after the group: a town's heading ends the group above, and opens the body of the
    # first group under it
    # the heading with the margin's junk taken off both ends («Paisley I», «| Preston. 3», «iu Oldham. E», 1908); a line in
    # capitals is a running head or a country, never a town
    place = {x: re.sub(r"(?:\s+(?:[^\w\s]+|\d+|[A-Za-z]|[A-Z]{2,3}))+\s*$", "", lead(t.strip())) for x, (p, n, t) in enumerate(seq)} if late else {}
    heads = [x for x, (p, n, t) in enumerate(seq) if late and PLACEHEAD.match(place[x]) and not FOND.search(t)
             and not ROLE.search(t) and len(place[x].split()) <= 4 and not place[x].isupper() and not ADDR.search(place[x])] if late else []
    out = []
    for k, (j, i, head) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(seq)
        town, b0 = "", i
        if late:
            ph = [x for x in heads if x < j]
            nx = [x for x in heads if x > i]
            if nx: end = min(end, nx[0])
            # only the first group under a heading takes its town: a second may be under a heading the OCR lost («Reading»,
            # 1908 PDF 100, ran into the line above, and its society took Putney), so it takes none
            if ph and (k == 0 or ph[-1] > starts[k - 1][1]):
                town = re.sub(r"[^\wÀ-ž' -]", "", place[ph[-1]]).strip(); b0 = ph[-1] + 1
        body = [(seq[x][0], seq[x][1], seq[x][2]) for x in range(b0, end)]
        ht = head_town(head)
        if ht: town = ht
        out.append({"pdf": seq[i][0], "line": seq[i][1], "group": re.sub(r"\s+", " ", head), "town": town, "body": body})
    # THE SIGNALS, for each officer's own group and town (2026-10-27, the accuracy check: 9 of 40 lines named the group or
    # town of the block the officer was parsed into, not his own: Beale under the London club, not its Forest-Gate branch;
    # Paal under Omsk, not Pernov): every group's heading, and every town's heading, by its place in the pages; a town's
    # heading in capitals that is no country nor running head («FOREST-GATE», a branch) counts in every volume
    # a town with a word under three letters is the margin's junk («Mej aj Machhlipith», «Si p Lj», 1909 PDF 80, 84), not a town
    towns = [(x, re.sub(r"[^\wÀ-ž' -]", "", place[x]).strip()) for x in heads
             if all(len(w) >= 3 or (k and w.lower() in PARTICLES | {"on", "am", "in"}) for k, w in enumerate(re.sub(r"[^\wÀ-ž' -]", "", place[x]).split()))]
    for x, (p, n, t) in enumerate(seq):
        c = lead(t.strip()).strip(" .,:;|—-")
        if c.isupper() and 1 <= len(c.split()) <= 3 and len(re.sub(r"\W", "", c)) >= 4 and not COUNTRY.search(c):
            towns.append((x, c.title()))
    sig = {"idx": {(p, n): x for x, (p, n, t) in enumerate(seq)}, "groups": [(j, head, head_town(head)) for j, i, head in starts],
           "towns": sorted(towns)}
    for e in out: e["sig"] = sig
    return out

COUNTRY = re.compile(r"(?:UJO|IO|ANDO|IKO|AJO|ARIO|ALO|ILO)\b|ESPERANT|TUTMONDA|JARLIBRO|SOCIET|ADRESARO|REGISTRO|KOMITAT|"
                     r"INSTITUCI|ASOCI|GRUPOJ|SOCIETOJ|AMERIKO|EŬROPO|EUROPO|AZIO|AFRIKO|OCEANIO|MALTA|KANADA|USONO|TRANSVAAL")

def head_town(head):
    """The town a group's heading names: «G. E. en Warrington», or a town before the group on its line («Pernov. E.G.»)."""
    m = re.search(r"\ben\.?\s+([A-ZÀ-Ž][\w'’.-]+(?:[\s-]+(?:on|in|i\.|am|upon|de|del|la|le|sur|les)?[\s-]*[A-ZÀ-Ž][\w'’.-]+)*)", head)
    if m: return m.group(1).strip(" .,")
    m = re.match(r"^\W*([A-ZÀ-Ž][\wÀ-ž'’-]+(?:[ -][A-ZÀ-Ž][\wÀ-ž'’-]+)?)(?:\s*\([^)]{2,30}\))?\.\s*(?:E\.\s?G|G\.\s?E|E\.\s?K|K\.\s?E|Esp|Soc|Grup|Klub)", head)
    return m.group(1) if m else ""

def resolve(sig, p, n, role):
    """(group, town, far) for the officer on page P, line N: the nearest group heading above his line, and the nearest
    town heading; a town heading below the group's means a branch or a group whose name the OCR lost: «grupo en ‹town›».
    The U. E. A. delegate and the consul belong to the town, not to a group."""
    x = sig["idx"].get((p, n))
    if x is None: return "", "", True
    gs = [g for g in sig["groups"] if g[0] <= x]
    ts = [t for t in sig["towns"] if t[0] <= x]
    g, t = (gs[-1] if gs else None), (ts[-1] if ts else None)
    prev = gs[-2][0] if len(gs) > 1 else -1
    if role in ("delegito de U. E. A.", "konsulo", "konsula agento"):
        # (the second accuracy check, 2026-10-27: Mills under Reading, not Rhos; Gustafsson under Elizavetpol, not
        # Helsinki; the town heading the OCR missed, the one above taken): only a town heading a few lines above
        town = t[1] if t and x - t[0] <= 4 else ""
        return ("Universala Esperanto-Asocio" if town else ""), town, not town
    if not g or x - g[0] > 10: return (g[1] if g else ""), "", True
    if t and t[0] > g[0]: return "grupo", t[1], False
    # a town heading far above the group's line is another town's, its own heading lost (Gustafsson of «La Polusstelo»,
    # Helsinki, took Bjelostok): six lines at most
    town = g[2] or (t[1] if t and prev < t[0] <= g[0] and g[0] - t[0] <= 6 else "")
    return g[1], town, False

def officers(e):
    """The officers of a group: [(role, printed segment, pdf, line)], each segment from its mark to the next mark, a dash or
    the end; the committee's other members split at «;»."""
    text, where = "", []
    for p, n, t in e["body"]:
        t = t.strip()
        if not t: text += "\n"; where.append((len(text), p, n)); continue
        where.append((len(text), p, n))
        text = (text[:-1] + t) if text.endswith("-") and t[:1].islower() else (text + (" " if text and not text.endswith("\n") else "") + t)
    def at(i):
        w = [x for x in where if x[0] <= i]
        return w[-1][1:] if w else (e["pdf"], e["line"])
    marks = [(m.start(), m.end(), ROLES[int(next(k for k, v in m.groupdict().items() if v is not None)[1:])][0]) for m in ROLE.finditer(text)]
    out, branch = [], ""
    for k, (s, en, role) in enumerate(marks):
        # A BRANCH NAMED INLINE (1904 PDF 16: «Grupetoj en London'o, filioj de E. Klubo : — FOREST-GATE. Pr., Motteau.
        # Sek., J. Beale, 74, Claremont road. — HAMPSTEAD. Sek., N.»; the accuracy check 2026-10-27, line 10): a «— CAPITALS.»
        # before a mark puts the officers after it in that branch, until the next
        bm = re.findall(r"—\s*([A-ZĈĜĤĴŜŬ][A-ZĈĜĤĴŜŬ'’ -]{3,}?)\s*[.,]", text[(marks[k - 1][1] if k else 0):s])
        if bm and not COUNTRY.search(bm[-1]): branch = bm[-1].strip().title()
        stop = marks[k + 1][0] if k + 1 < len(marks) else len(text)
        seg = text[en:stop]
        # the last officer of a group runs on into what follows: cut at a blank line, a country's heading in capitals
        # («GRANDA BRITUJO»), or past 140 characters at the last comma
        # … and at the next group's name («… Lucas- Leclin Charles, 11, r. du Change. kE. G. (S. F. P. E.)», 1908 PDF 129)
        seg = re.split(r"\s—|—\s|\n|\s(?=[A-ZĈĜĤĴŜŬ]{5,}\b)|\s(?=Grupanoj\b)|[\s,]\W{0,2}\w{0,2}\W?\s?(?=(?:G\.\s?E\.|E\.\s?G\.|E\.\s?K\.|K\.\s?E\.)[\s,])", seg)[0].strip(" .,;:|")
        if len(seg) > 140: seg = seg[:140].rsplit(",", 1)[0]
        p, n = at(s)
        # several holders of one office at «;» («Vicprez. : Delseriĉs, inspektoro …; Morel, ekskolegiestro», 1908 PDF 109)
        parts = [x.strip() for x in seg.split(";")]
        for x in parts:
            if not x: continue
            # THE ANCHOR FROM THE MARK'S OWN PLACE (2026-10-27: taken by searching the line for the mark's text, Cart's line
            # in 1908 PDF 107 quoted Nicollet's, the same «Vicprez. :» standing earlier on it); a committee member's from his name
            a0 = s if x is parts[0] else max(text.find(x, en), s)
            anc = " ".join(text[a0:].split()[:max(6, min(len(x.split()) + 2, 12))])
            out.append((role, x, p, n, anc, branch))
    return out

def split_name(seg):
    """(name, rest chunks): the name is the first comma chunk, with the next one if the first is a surname alone and the
    next only initials («Barakof, P. Iv., instruisto»); titles left out."""
    ch = [c.strip() for c in lead(seg.replace("\n", " ")).split(",")]
    name = TITLE.sub("", ch[0]).strip()
    rest = ch[1:]
    if rest and len(name.split()) == 1 and re.fullmatch(r"(?:[A-ZÀ-Ž][a-z]{0,2}\.\s*-?){1,3}", rest[0]):
        name = name + ", " + rest[0]; rest = rest[1:]
    # a house number run on to the name with no comma («Edouard Steckel 186, r. Michel-Bizot»)
    m = re.match(r"(.*?[A-Za-zÀ-ž.)])\s+(\d+\w?)$", name)
    if m: name = m.group(1); rest = [m.group(2)] + rest
    return name, [r for r in rest if r]

def clean_name(name):
    """The name as the fact says it: the OCR's junk tokens left out («P"9 0. Grady» → «Grady», «1V. H. Hobson» → «H. Hobson»)."""
    ws = [w for w in name.split() if not re.search(r"[\"”»°?\d!|€$]|^['’]|['’]$", w)]
    s = " ".join(ws).strip(" ,.;:(")
    # the surname first, with a comma («Geddes, H. R», «Barakof, P. Iv.»): in the usual order
    m = re.fullmatch(r"([^,]+),\s*((?:[A-ZÀ-Ž][a-z]{0,2}\.?\s*)+)", s)
    return f"{m.group(2).strip()} {m.group(1).strip()}" if m else s

PARTICLES = {"de", "van", "von", "le", "la", "del", "du", "der", "den", "ten", "ter", "di", "da", "des", "dos"}

def surname_tokens(name):
    """The words of a printed name that may be the surname: those in capitals («Gabriel CHAVET»); else the first of
    «SURNAME (Forename)» and «Surname, A. B.»; else the last, with a particle before it («J. de Haan»). The forename is
    never matched: «Gabriel» joined Chavet to GARIEL (2026-10-27, the first run)."""
    toks = [t.strip(".,;:()") for t in re.sub(r"[(),]", " ", name).split()]
    toks = [t for t in toks if t]
    caps = [t for t in toks if len(t) >= 3 and t.isupper()]
    if caps: return caps
    if "(" in name or "," in name: return toks[:1]
    words = [t for t in toks if not re.fullmatch(r"[A-ZÀ-Ž][a-zà-ž]{0,2}\.?|[A-ZÀ-Ž]{1,2}", t)]
    if not words: return []
    out = words[-1:]
    if len(words) > 1 and words[-2].lower() in PARTICLES: out = words[-2:]
    return out

_PROF = {}
def profile(label):
    if label not in _PROF:
        p = os.path.join(PROFILES, label + ".md")
        if not os.path.exists(p): _PROF[label] = None
        else:
            t = open(p, encoding="utf-8").read()
            # THE NAME AS ITS LINES WRITE IT, the commonest «$$$ NAME $$$ (qualifier)» of the profile; not the page's
            # heading, which for some is a description («EDUARD KÜHNL (PRAGUE; REDAKTORO OF ČASOPIS …)», the sample 2026-10-27)
            heads = collections.Counter(m.group(1).strip() + (f" $$$ ({m.group(2)})" if m.group(2) else "")
                                        for m in re.finditer(r"^- \$\$\$ (.+?) \$\$\$(?: \(([^)]{1,60})\))?", t, re.M))
            hp = heads.most_common(1)[0][0] if heads else label.upper()
            if "$$$" not in hp: hp += " $$$"
            _PROF[label] = (hp.replace(" $$$ (", " (").replace(" $$$", ""), t, hp)
    return _PROF[label]

def borne_out(label, name, surname_tok, town):
    """How the profile bears the identification out: «la urbo X», «la inicialoj …», «la persona nomo …», or ''."""
    pr = profile(label)
    if not pr: return ""
    t = pr[1]
    if town and len(town) >= 4 and re.search(r"(?<!\w)" + re.escape(town.split()[0]) + r"(?!\w)", t, re.I):
        return f"la urbo {town.split()[0]}"
    before = name.split(surname_tok)[0] if surname_tok in name else ""
    if "," in name: before = name.split(",", 1)[1]
    ini = re.findall(r"\b([A-ZÀ-Ž])[a-z]{0,2}\.", before)
    if ini:
        pat = r"\b" + r"\.?\s*-?\s*".join(ini) + r"\.?\s*-?\s*" + re.escape(surname_tok)
        if re.search(pat, t, re.I): return "la inicialoj " + " ".join(i + "." for i in ini)
    for w in re.findall(r"\b([A-ZÀ-Ž][a-zà-ž]{2,})\b", before):
        if w.lower() not in STOPW and re.search(r"\b" + re.escape(w) + r"\b.{0,30}" + re.escape(surname_tok), t, re.I | re.S):
            return f"la persona nomo {w}"
    return ""

def load_hits(path):
    """{(item, pdf): {normalised word as read: {person}}}, strong tiers only."""
    h = collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(path, encoding="utf-8") as fh:
        rows = csv.reader((l for l in fh if not l.startswith("#")), delimiter="\t")
        hd = next(rows); ix = {k: i for i, k in enumerate(hd)}
        for r in rows:
            if len(r) < len(hd) or r[ix["tier"]] not in ("exact", "near", "confusion") or not r[ix["page"]].isdigit(): continue
            d = h[(r[ix["item"]], int(r[ix["page"]]))][norm(r[ix["as_read"]])]
            if d.get(r[ix["person"]]) != "exact": d[r[ix["person"]]] = r[ix["tier"]]
    return h

def anchor(pages, p, n, mark, seg):
    """Six words or more from the page, from the officer's mark on: the line's own words, then the next lines'."""
    ls = [t for m, t in pages[p] if m >= n]
    txt = " ".join(ls)
    i = txt.find(mark)
    ws = (txt[i:] if i >= 0 else txt).split()
    seg_w = len(seg.split())
    return " ".join(ws[:max(6, min(seg_w + 2, 12))])

# THE COMMITTEES (1910 only, PDF 11–17; the inspection 2026-10-27: no other volume prints them): the Akademio's officers
# and members, the Lingva Komitato's members by language («Nomaro de ĉiuj anoj la 1ᵃ de Januaro 1910»), the Konstanta
# Komitato de la Kongresoj; one member a line, «SURNAME (Forename), address (Country)»
COMM = {1910: (11, 17)}
SECTIONS = [(re.compile(r"Anoj de la Esperantista Akademio"), "Esperantista Akademio", "akademiano", ""),
            (re.compile(r"AKADEMIANOJ"), "Esperantista Akademio", "", ""),
            (re.compile(r"LINGVA KOMITATANOJ"), "Lingva Komitato", "komitatano", "1910-01-01"),
            (re.compile(r"KONSTANTA KOMITATO DE LA KONGRESOJ"), "Konstanta Komitato de la Kongresoj", "", ""),
            (re.compile(r"Anoj por la (\w+)\.? Kongreso"), "Konstanta Komitato de la Kongresoj", "ano por la {0} Kongreso", "")]
OFFICE = re.compile(r"^\W{0,4}(Honora Prezidanto|Prezidanto|Vicprezidantoj?|Ĝenerala Sekretario|Sekretario-Adjunkto por \w+|"
                    r"Gramatiko|Komuna Vortaro|Teknika Vortaro|Internaj aferoj)\s*:\s*(.*)$")
COMMISSION = {"Gramatiko": "gramatiko", "Komuna Vortaro": "la komuna vortaro", "Teknika Vortaro": "la teknika vortaro", "Internaj aferoj": "la internaj aferoj"}
LISTED = re.compile(r"^\W{0,4}(?P<name>[^,;:]{2,60}?)\s*[,.]\s*(?P<addr>.+)$")
COMMSTOP = re.compile(r"Regularo de la Kongresoj")

def committees(pages, y):
    """The committee members: [{pdf, line, grp, role, seg, town, date}]."""
    if y not in COMM: return []
    a, b = COMM[y]
    out, grp, role, date, sub, pending = [], "", "", "", "", None
    for p in range(a, b + 1):
        for n, t in pages.get(p, []):
            s = lead(t.strip())
            if COMMSTOP.search(s): return out
            sec = next(((r, g, ro, d, r.search(s)) for r, g, ro, d in SECTIONS if r.search(s)), None)
            if sec:
                grp, role, date, sub, pending = sec[1], sec[2].format(*sec[4].groups()), sec[3], "", None
                continue
            m = re.match(r"^\W{0,3}([A-ZÀ-Ž][a-zà-ž]+)\s+lingvo\s*[.,]?", s)
            if m and grp == "Lingva Komitato": sub = f" ({m.group(1).lower()} lingvo)"; continue
            m = OFFICE.match(s)
            if m:
                r = m.group(1)
                r = (f"direktoro de la komisiono pri {COMMISSION[r]}" if r in COMMISSION else
                     "vicprezidanto" if r.startswith("Vicprez") else r.lower().replace("ameriko", "Ameriko"))
                rest = m.group(2).strip(" ;:,|")
                if len(rest) < 4: pending = r; continue
                for x in rest.split(";"):
                    if x.strip(): out.append({"pdf": p, "line": n, "grp": grp, "role": r, "seg": x.strip(), "date": date})
                pending = None; continue
            if pending:
                for x in s.split(";"):
                    if x.strip(" |"): out.append({"pdf": p, "line": n, "grp": grp, "role": pending, "seg": x.strip(" |"), "date": date})
                pending = None; continue
            m = LISTED.match(s)
            if m and role and (re.search(r"[A-ZÀ-Ž]{3}", m.group("name")) or "(" in m.group("name")) and len(m.group("name").split()) <= 6:
                out.append({"pdf": p, "line": n, "grp": grp + sub, "role": role, "seg": s.strip(" |;"), "date": date})
    return out

REGIONS = {"mass", "maine", "surrey", "alaska", "sussex", "sussez", "kent", "lancashire", "yorkshire", "essex", "moravio",
           "bohemujo", "n. y", "ill", "ohio", "cal", "pa"}

def lead(s):
    """A line with the margin's OCR junk taken off its front («0 Honora Prezidanto», «ki Prezidanto», «5 BUTLER», «[A Alfonso»)."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"^(?:[^\w\s(]+|\(+(?=\S{1,2}\s)|\d+(?=\s)|[a-zĉĝĥĵŝŭ]{1,2}\d*(?=\s)|[A-Z](?=\s+[A-ZÀ-Ž][a-zà-ž]))\s*", "", s)
    return s

def town_of(addr):
    """The town of an address: its last comma chunk, the country in brackets dropped («Montreal (Kanado)» → Montreal), a
    county or state passed over («Bath Rd. Gamberley, Surrey» → Gamberley), a postal district left off («London N. W»)."""
    ch = [re.sub(r"\(.*", "", c).strip(" .;|:»ĵ") for c in addr.split(",")]
    ch = [c for c in ch if c]
    while len(ch) > 1 and ch[-1].lower().strip(". ") in REGIONS: ch.pop()
    if not ch: return ""
    t = re.sub(r"(?:\s+[NSEW]\.?(?:\s*[NSEW]\.?)?|\s+[A-Z]{1,2})$", "", ch[-1]).strip(" .")
    t = re.split(r"\.\s+(?=[A-ZÀ-Ž])", t)[-1]
    return t if re.match(r"[A-ZÀ-Ž][\wÀ-ž'’ .-]{2,40}$", t) and not re.search(r"\d", t) and t.lower() not in REGIONS else ""

def esp_group(g):
    # the OCR's junk before the abbreviation («Hu xxE.G», «Tu E. G», «IGI E. G.», 1909–1910)
    g = re.sub(r"^\W+", "", g)
    g = re.sub(r"^.{0,6}?(?=(?:G\.\s*E\.|E\.\s*G\.?)(?:\s|$|,))", "", g)
    return re.sub(r"^(?:G\.\s*E\.|E\.\s*G\.|G\s*-\s*E\.)\s*", lambda m: "Grupo Esperantista " if m.group(0).startswith("G") else "Esperanta Grupo ", g).strip(" ,.")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["jarlibro-societies"]); ap.add_argument("--hits", required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--years", default=",".join(map(str, PARTS))); ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, help="print the groups and officers parsed on this PDF page of the first year, and stop")
    ap.add_argument("--near-input", action="store_true", help="from societies-TAG.tsv, write near-input-TAG.md: each held near-form join with its page lines and the profile's lines on that surname, for one legilo (2026-10-27, the editor)")
    a = ap.parse_args()
    if a.near_input:
        out = os.path.join(D, f"near-input-{a.tag}.md")
        if os.path.exists(out): sys.exit(f"refusing to overwrite {out}")
        rows = [r for r in csv.reader(open(os.path.join(D, f"societies-{a.tag}.tsv"), encoding="utf-8"), delimiter="\t")][1:]
        rows = [r for r in rows if r[9] == "held: near formo"]
        cache, parts = {}, []
        for k, r in enumerate(rows, 1):
            y, p, n = int(r[0]), int(r[1]), int(r[2])
            if y not in cache: cache[y] = page_lines(ITEM.format(y=y))
            ctx = [t.strip() for m, t in cache[y].get(p, []) if n - 1 <= m <= n + 2 and t.strip()]
            cand = re.match(r"([^ ]+) \(near", r[8]).group(1) if re.match(r"([^ ]+) \(near", r[8]) else r[8].split(" (")[0]
            pr = profile(cand)
            plines = []
            if pr:
                for l in pr[1].split("\n"):
                    if l.startswith("- $$$"): plines.append(re.sub(r"\s+⟵.*", "", l)[:240])
                    if len(plines) >= 5: break
            parts.append(f"### {k}. {y}, PDF {p}, l. {n} · {r[5]} · {r[3]} ({r[4] or '?'})\n\n- presita nomo: «{r[6]}»; la resto: «{r[7]}»\n- la paĝo:\n"
                         + "".join(f"  > {c}\n" for c in ctx)
                         + f"- kandidato: **{pr[0] if pr else cand}** (profilo `profiles/{cand}.md`), ĝiaj unuaj linioj:\n"
                         + "".join(f"  - {l}\n" for l in plines) + "\n")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"# La proksimaj formoj de la Jarlibro ({a.tag}): {len(rows)} identigoj por juĝi\n\n`[GENERATED by tools/directory-extract.py --near-input. Do not hand-edit — re-run it.]`\n\n" + "".join(parts))
        print(f"{len(rows)} near-form joins → {os.path.relpath(out, ROOT)}")
        return
    if a.show:
        y = int(a.years.split(",")[0])
        for e in entries(page_lines(ITEM.format(y=y)), PARTS[y], y >= 1908):
            if e["pdf"] != a.show: continue
            print(f"## {esp_group(e['group'])} · town «{e['town']}» · l. {e['line']}")
            for role, seg, p, n, mark, branch in officers(e): print(f"   {role}{' (' + branch + ')' if branch else ''}: {split_name(seg)} [{mark}]")
        for c in committees(page_lines(ITEM.format(y=y)), y):
            if c["pdf"] == a.show: print(f"   {c['role']}, {c['grp']} {c['date']}: {split_name(c['seg'])} · town «{town_of(', '.join(split_name(c['seg'])[1]))}»")
        return
    outs = {k: os.path.join(D, f) for k, f in (("ret", f"facts-return-{a.tag}-societies.md"), ("tsv", f"societies-{a.tag}.tsv"), ("rev", f"SOCIETIES-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    hits = load_hits(a.hits)
    # THE NEAR FORMS' RULINGS (2026-10-27, the editor; three legiloj over near-input-TAG.md): «sama» lands the join,
    # its identification by the legilo's reason; «alia» and «necerta» stay held. Keyed by year, page, line and the printed
    # name, so a rerun's new order cannot misplace them
    near = {}
    ni = os.path.join(D, f"near-input-{a.tag}.md")
    if os.path.exists(ni):
        heads = {int(m.group(1)): (int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5))
                 for m in re.finditer(r"^### (\d+)\. (\d{4}), PDF (\d+), l\. (\d+) · .*\n\n- presita nomo: «(.*)»; la resto", open(ni, encoding="utf-8").read(), re.M)}
        for rp in sorted(glob.glob(os.path.join(D, f"near-return-{a.tag}-*.md"))):
            for m in re.finditer(r"^(\d+) · (sama|alia|necerta) · .*? · (.*)$", open(rp, encoding="utf-8").read(), re.M):
                # keyed by year, page and printed name, not line: a recupel shifts the lines (the gutter cut, 2026-10-27 14:5x)
                if int(m.group(1)) in heads:
                    y_, p_, n_, nm_ = heads[int(m.group(1))]
                    near[(y_, p_, nm_)] = (m.group(2), re.sub(r"[·⟦⟧{}]", "", m.group(3)).strip())
    rows, lines, cnt = [], [], collections.Counter()
    for y in map(int, a.years.split(",")):
        item, key = ITEM.format(y=y), KEY.format(y=y)
        pages = page_lines(item)
        recs = []   # (pdf, line, the body, its town, role, segment, the mark, date)
        for e in entries(pages, PARTS[y], y >= 1908):
            cnt["groups"] += 1
            grp = esp_group(e["group"])
            grp = grp if grp.startswith("The ") else "la " + grp
            for role, seg, p, n, mark, branch in officers(e):
                # his own group and town, by the nearest headings above his line; far from any group heading (a group
                # whose «fondita» the OCR lost: 1907 PDF 320, Schneeberger of Laufen under the Upsala club): held
                g, town, far = resolve(e["sig"], p, n, role)
                if branch and not g.startswith("Universala"): g, town = "grupo", branch
                if ROLE.search(g): g = ""
                if g == "Universala Esperanto-Asocio": role = "delegito" if role.startswith("delegito") else role
                g = esp_group(g) if g not in ("grupo", "Universala Esperanto-Asocio", "") else g
                g = "" if not g else g if g.startswith("The ") else "la " + g
                recs.append((p, n, g, town, role, seg, mark, "", False, far))
        for c in committees(pages, y):
            cnt["committee members"] += 1
            name, rest = split_name(c["seg"])
            recs.append((c["pdf"], c["line"], "la " + c["grp"], town_of(", ".join(rest)), c["role"], c["seg"], c["seg"].split()[0], c["date"], True, False))
        for p, n, grp, town, role, seg, mark, date, comm, far in recs:
            cnt["officers"] += 1
            name, rest = split_name(seg)
            ph = hits.get((item, p), {})
            cands, tiers = {}, {}
            for w in surname_tokens(name):
                for person, tier in ph.get(norm(w), {}).items():
                    if len(norm(w)) >= 3: cands.setdefault(person, w); tiers.setdefault(person, tier)
            borne = {pp: borne_out(pp, name, w, town) for pp, w in cands.items()}
            ok = [pp for pp, b in borne.items() if b]
            # THE GROUP AS THE OBJECT (2026-10-27, the first run's sample: from 1908 the names are generic or the OCR's
            # («Orense)», «Zi. HEA k Stiria Esperantista Societo»)): its codes in brackets left out, cut after its town
            # («… en Tirnovo. O.o., Rondiranto.J.k»), its town added where the name has none; a committee keeps its own
            # name; a group with neither a town nor «en X» is held, its office naming nothing
            # the line's own marks never inside a field («EG {IB E A; ‚ en Todmorden», 1909: the check refused it)
            base = lead(re.sub(r"\s*\([^)]*\)?|[{}·]", "", grp[3:] if grp.startswith("la ") else grp).strip(" ,.;:)"))
            name = re.sub(r"[{}·]", "", name); rest = [re.sub(r"[{}·]", "", r) for r in rest]
            m = re.match(r"(.*?\ben\s+[A-ZÀ-Ž][\wÀ-ž'’-]*(?:[\s-]+(?:on|in|am|upon|de|del|la|le|sur|les)?[\s-]*[A-ZÀ-Ž][\wÀ-ž'’-]*)*)", base)
            if m: base = m.group(1)
            obj = (base if comm or " en " in f" {base} " or (town and town in base) else
                   f"{base} en {town}" if town and len(re.sub(r"\W", "", base)) >= 4 else f"grupo en {town}" if town else "")
            label = ok[0] if len(ok) == 1 else ""
            verdict = ("ne en la nomaro" if not cands else "held: du personoj" if len(ok) > 1 else "held: nur la familia nomo" if not ok
                       else "held: la nomo ne legebla" if len(name.split()) > 5 else "held: grupo sen urbo" if not obj
                       else "held: malproksime de la grupo" if far
                       else "held: profilo ambigua" if "ambigu" in profile(label)[1].split("\n", 1)[0].lower() or label.endswith("ambiguous")
                       # a near or confusion form, not an exact one: «Backman» read as WICKMAN, «Branson» as ABRAMSON,
                       # «fusche» as FISCHER in the first run, each borne out by the town alone; the right ones (Zlatel,
                       # Luly) go to the review with them
                       else f"held: {tiers[label]} formo" if tiers[label] != "exact" else "line")
            ruled = near.get((y, p, name)) if verdict.endswith(" formo") else None
            if ruled and ruled[0] == "sama": verdict = "line"; borne[label] = f"la legilo de la proksimaj formoj: «{ruled[1]}»"
            elif ruled: verdict = f"held: {verdict[6:]}, {ruled[0]} laŭ la legilo"
            cnt[verdict.split(":")[0]] += 1
            if verdict != "line": label = ""
            rows.append([y, p, n, grp, town, role, name, " | ".join(rest), "; ".join(f"{pp} ({tiers[pp]}; {borne[pp] or '—'})" for pp in cands), verdict])
            if not label: continue
            head, _t, hp = profile(label)
            loc = f"{key}, PDF {p}, l. {n}"
            anc = mark if not comm else anchor(pages, p, n, mark, seg)
            dnote = "⟦pruvo: «Nomaro de ĉiuj anoj la 1ᵃ de Januaro 1910»⟧" if date else "⟦la jaro de la jarlibro⟧"
            # one initial alone bears an identification out only weakly: the line carries ❓
            thin = borne[label].startswith("la inicialoj") and len(borne[label].split()) == 3
            conf = f"📣{' ❓' if thin else ''} (sen fontindiko; {dnote}; ⟦identigo: {head}, laŭ {borne[label]}{'' if borne[label].startswith('la legilo') else ' en la profilo'}⟧)"
            d = date or str(y)
            shown = clean_name(name) or name
            de = obj if obj.startswith("The ") else "la " + obj
            # a consul's body is not printed (the third check, 2026-10-27, line 20: «La UEA estas aldono»): the town only
            if role in ("konsulo", "konsula agento"): obj, de = town, None
            lines.append(f"- $$$ {hp} **{d}** · {{ofico: {role}, {obj}}} · {shown} estas {role} {'de ' + de if de else 'en ' + obj}. · {anc} · {loc} · [G] · {conf}")
            occ = [r for r in rest if OCC.match(r.strip())]
            # the address: a committee member's line after his name throughout; a group officer's from its first chunk
            # that looks like one to the end («37, Surbrunnsgatan, Stockholm»), the occupations left out
            # (2026-10-27, the accuracy check: «Herderstr., 3» came out «3», the street not being taken for one): an officer
            # with any chunk like an address has the whole rest as his address, less occupations and degrees
            # (the second check: «Fenech, farmaciisto … kl! vi E. G., fondita» and «E. Kunz, drogisto … ĝi | 1» made
            # addresses; «ĉefa redaktoro» and «commis de direction des douanes» stood in them): the address begins at its
            # first street word or house number; a chunk in lower case without a street word is an occupation, and a
            # chunk with the next group's «E. G.» or «fondita», or under three letters, is no address
            def street(r): return bool(re.match(r"\s*\d+\w?\b", r)) or bool(STREET.search(r))
            first = next((i for i, r in enumerate(rest) if street(r)), None)
            addr = [r for r in (rest if comm else rest[first:] if first is not None else [])
                    if r not in occ and not DEGREE.match(r.strip()) and not FOND.search(r) and not re.search(r"[EG]\.\s?[GE]\.", r)
                    and len(re.sub(r"[^A-Za-zÀ-ž0-9]", "", r)) >= 2
                    and not (r.strip()[:1].islower() and not STREET.search(r))]
            # a house number alone, with nothing after it, is no address («ĝi | 1»)
            if not comm and not any(STREET.search(r) or re.match(r"\s*\d+\w?,?\s+\S", r) for r in addr) and len(addr) < 2: addr = []
            if addr and town:
                where = ", ".join(addr).strip(" .;:|[")
                lines.append(f"- $$$ {hp} **{d}** · {{loĝado: {town}}} · {shown} loĝas ĉe {where}{'' if town in where else ' (' + town + ')'}. · {anc} · {loc} · [?] · {conf}")
            for o in occ:
                lines.append(f"- $$$ {hp} **{d}** · {{profesio: {o}}} · {shown} estas {o}. · {anc} · {loc} · [?] · {conf}")
    cnt["lines"] = len(lines)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    with open(outs["tsv"], "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["year", "pdf", "line", "group", "town", "role", "name as printed", "the rest", "roster hits (borne out by)", "verdict"]); w.writerows(rows)
    with open(outs["ret"], "w", encoding="utf-8") as fh:
        fh.write(f"# Return: facts-return-{a.tag}-societies.md\n\n`[Written by tools/directory-extract.py jarlibro-societies, {a.tag}, from the name search {os.path.basename(a.hits)}: the officers of the groups and societies, roster persons only, each borne out by the profile (runbook D4c). Not a legilo's return.]`\n\n")
        fh.write("\n".join(lines) + "\n")
    held = [r for r in rows if r[9].startswith("held")]
    with open(outs["rev"], "w", encoding="utf-8") as fh:
        fh.write(f"# The Tutmonda Jarlibro's groups and societies, read by tool ({a.tag})\n\n`[GENERATED by tools/directory-extract.py jarlibro-societies. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". Every officer parsed: `{os.path.basename(outs['tsv'])}`; the lines: `{os.path.basename(outs['ret'])}`.\n\n")
        fh.write(f"## Held: {len(held)} (a roster surname, not borne out by the profile, or two persons borne out)\n\n")
        for r in held: fh.write(f"- {r[0]}, PDF {r[1]}, l. {r[2]} · {r[3]} ({r[4] or '?'}) · {r[5]}: «{r[6]}» · {r[8]} · {r[9]}\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

if __name__ == "__main__":
    main()
