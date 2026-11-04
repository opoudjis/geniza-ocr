#!/usr/bin/env python3
"""Zamenhof's *Adresaro*, series I–XXIX (1889–1908), read by tool (runbook D4c; 2026-10-29, the editor: the survey's order,
the entries' order accepted): every numbered entry of the Wikisource transcription (sources/born-digital-text/
adresaro-*.txt; never an OCR copy: the *Tutmonda Jarlibro*'s reprinted sections are skipped, as the editor asked),
joined to the roster where the profile bears the identification out, as part A of the *Tutmonda Jarlibro* was.

    tools/adresaro-extract.py --hits HITS.tsv --tag TAG [--write] [--show N]

HITS: the strong name search over the series (`ocr-dowse.py --strong-only`; a born-digital text is searched paragraph by
paragraph, so a hit's «page» is the entry's ¶). The entry's formats (the survey, `dowse/DIRECTORY-SURVEY-2026-10-29-
analysis.md`):
  A, series I (1889):          «3. Abolenski, W. W., doktoro. S. Peterburg, … R.»                 name first, one number
  B, series II–XV (1892–1893): «1797. 1797. Bartels, Gustav, Kaufmann. Mannheim, L. 18, 4. Germanujo. [W. H. Trompeter.]»
  C, series XVI (1893):        «3001. 3001. AFRIKO. Alĝerujo. Alger: Aug. Renard, professeur …-[L. de Beaufront].»
  D/E, series XVII–XXIX:       «4661. 4661. Abo, Finnlando, Rusujo. - Fredsgatan Nr. 1. - Uno Hahnson (kontoristo).»
                               «9268. 9268. PARIS, Francujo, 13, r. Claude-Bernard. - G. Boutelant.»
A person on the roster, borne out by the profile (the town, the initials or the forename), gets:
  {aperoj: Adresaro de Zamenhof, n-ro N}   the entry itself (the kind «aperoj»: «eroj de Adresaro»)
  {loĝado: TOWN}                           the town, with the address where one is printed
  {profesio: …}                            the occupation, where one is printed
and the collector in brackets («[W. H. Trompeter.]»), if on the roster and borne out by initials or forename:
  {propagando: NAME, Adresaro n-ro N}       the recruiter's activity (the editor, 2026-10-29: a collector's work is
                                           movement activity, a line of its own)
Dated by the series' year (⟦la jaro de la serio de la Adresaro⟧). The transcription's own marks («!» inside a word, «?»,
«^^me^^» superscripts) are taken out of names and towns. Writes, with --write, in dowse/zamenhof-adresaro/:
  facts-return-TAG-adresaro.md  (the lines, for the assembler), adresaro-TAG.tsv (every entry parsed, with the verdict),
  ADRESARO-REVIEW-TAG.md (the counts, the held). It refuses to overwrite any of them. Without --write it prints the counts.
Ezri."""
import argparse, collections, csv, glob, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "dowse", "zamenhof-adresaro")
BD = os.path.join(G, "sources", "born-digital-text")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import born_digital_lines as BDL  # noqa: E402
import gazetteer as GZ  # noqa: E402
spec = importlib.util.spec_from_file_location("dx", os.path.join(ROOT, "tools", "directory-extract.py"))
DX = importlib.util.module_from_spec(spec); spec.loader.exec_module(DX)

ENTRY = re.compile(r"^(\d+)\.\s+(?:(\d+)!?\.\s+)?(.*)$", re.S)
SECTION = re.compile(r"Serio\s+([IVXL]+)(?:\s+(?:Peco|Parto)\s+\d+)?\s*\((\d{4})\)")
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}
def roman(s):
    v = [ROMAN[c] for c in s]
    return sum(-x if i + 1 < len(v) and x < v[i + 1] else x for i, x in enumerate(v))

TITLES = re.compile(r"^(?:(?:Doktoro|D\^*ro\^*|Dro|Profesoro|Prof\.|Princino|Princo|Grafo|Grafino|Baronino|Barono|Pastro|Kapitano|"
                    r"Leŭtenanto|S-?ro|S-?ino|F\^*ino\^*|Fino|Sinjoro|Sinjorino|Fraŭlino|Mr\.?|Mrs\.?|Miss|M\.|Mme|Mlle|Herr|Frau|"
                    r"Fräulein|Pani|Panna|Pan|Don|Doña|Sr\.|Sra\.)\s+)+")
STREETW = re.compile(r"\b(?:ul|ulica|str|strasse|straße|gasse|gatan|gade|rue|r|av|avenue|bd|boul|place|pl|road|rd|street|st|lane|"
                     r"square|sq|terrace|ter|plaza|calle|via|straat|laan|d|dom|kv|N|Nr|N-o|No|n°)\b\.?", re.I)
NOTPLACE = re.compile(r"(?:^|\s)(?:gub|obl|okr|uezd|dep|prov|distr|kanton|ĉerez|per|poĉt|otd|selo|st)\.?$", re.I)

def clean(s):
    """The transcription's marks out: «Szabadsá!gtér» → «Szabadságtér», «Ze?rkwach» → «Zerkwach», «^^me^^» → «me»."""
    return re.sub(r"\s+", " ", re.sub(r"[!?]|\^+", "", s)).strip()

def collector(body):
    """(body without its bracket, the collector as printed or '') from a final «[…]»; a journal or group in quotes is no
    person («["Espero".]», «["Almanaĥ Jablonskago".]»)."""
    m = re.search(r"\s*-?\s*\[([^\]]+)\]\.?\s*$", body)
    if not m: return body, ""
    c = m.group(1).strip(" .")
    return body[:m.start()].rstrip(" .-"), ("" if re.search(r"[\"„“”«»]", c) else c)

def parse(series, body):
    """{name, surname, town, address, occupation, collector} of one entry's text (after its numbers)."""
    body, coll = collector(body)
    out = {"name": "", "surname": "", "town": "", "address": "", "occupation": "", "collector": coll}
    if series == 16 and ":" in body:   # C: continent. country. Town: name, occupation
        place, _, rest = body.partition(":")
        out["town"] = clean(place.split(".")[-1].strip())
        ch = [c.strip() for c in rest.split(",")]
        out["name"] = clean(TITLES.sub("", ch[0]).strip(" .-")); out["occupation"] = ", ".join(ch[1:]).strip(" .-")
        out["surname"] = (DX.surname_tokens(out["name"]) or [""])[-1]
        return out
    segs = [s.strip() for s in re.split(r"\s+-\s+|\.\s*-\s+", body) if s.strip()]
    if series >= 17 and len(segs) >= 2:   # D/E: place first, the name in the last segment
        place, name_seg, mid = segs[0], segs[-1], segs[1:-1]
        pc = [c.strip() for c in place.split(",")]
        # a town in capitals ended by a full stop, its region after («RIBARROJA. Valencia, Hispanujo»)
        t0 = re.split(r"(?<=[A-ZÀ-Ž]{2})\.\s+", pc[0])[0].strip(" .")
        out["town"] = clean(t0).title() if t0.isupper() else clean(t0)
        # E: the address after the country in the place segment, from its first number or street on («PARIS, Francujo,
        # 13, r. Claude-Bernard»; «…, Rusujo, 14, Gruzinskij polk»)
        i0 = next((i for i, c in enumerate(pc[1:], 1) if re.search(r"\d", c) or STREETW.search(c)), None)
        tail = pc[i0:] if i0 else []
        out["address"] = ", ".join([clean(t) for t in tail] + [clean(m) for m in mid]).strip(" .")
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*\.?$", name_seg)   # D: «Uno Hahnson (kontoristo)»
        if m and not re.match(r"^[A-ZÀ-Ž]", m.group(2)): name_seg, occ = m.group(1), m.group(2)
        else:
            ch = [c.strip() for c in name_seg.split(",")]
            name_seg, occ = ch[0], ", ".join(ch[1:])
        nm = clean(TITLES.sub("", re.sub(r"\s*\([^)]*\)", lambda x: " " + x.group(0).strip("() ") + " ", name_seg)).strip(" .-"))
        out["name"], out["occupation"] = re.sub(r"\s+", " ", nm), clean(occ).strip(" .;")
        out["surname"] = (DX.surname_tokens(out["name"]) or [""])[-1]
        return out
    # A/B: «Surname, Forenames[, occupation]. place…» — the name part ends at the first «. » after a word of two letters or
    # more (so «W. W.,» does not end it)
    m = re.match(r"^([^,.]+),\s*(.*)$", body)
    if not m: return out
    sur, rest = m.group(1).strip(), m.group(2)
    end = next((x.end() for x in re.finditer(r"([\wÀ-ž'’^-]{2,})\.\s+", rest)), None)
    namepart, place = (rest[:end], rest[end:]) if end else (rest, "")
    # an initial, then the street at once («Alterman, M. Moskovskaja ul. N-o 23.»): the name ends at the initial
    m2 = re.search(r"\.\s+(?=[A-ZÀ-Ž][\wÀ-ž'’-]*\s+(?:ul|str|ulica|strasse|gasse|gatan|rue|r|road|street|pl|place|prosp)\b)", namepart)
    if m2: namepart, place = namepart[:m2.start() + 1], namepart[m2.end():] + place
    # … and initials, then any word of three letters or more («Orlov, N. Gimnaziĉeski Pansion. Rjazan.», «Kofman, I.
    # Targonsk, gub. Minsk»: the accuracy check of 2026-11-01, lines 17 and 29): the name ends at the initials, the last
    # of two or more left to the place where it is the town's («Bikov, N. I. S. Peterburg») or a station's («Ĉajkovski, J.
    # St. Sinelnikovo»); an «S.» or «M.» before another town is an initial («Cionson, N. S. Lida»: the marks, 31 to 18).
    # Of the 347 such entries whose name Wikisource marks, 330 agree; the marks run into the town in 4 («Dahlgren, G.
    # Lidköping»), a forename is lost in 1 («Gurien, S. Joseph»). Series I's governorate then no longer takes the town
    # (268 towns: «Averbuch, M. Pruĵani, gub. Grodno», Grodno before), nor «gub» the occupation
    m3 = re.match(r"^((?:[A-ZÀ-Ž][a-zà-ž]?\.\s*)+?)(?=[A-ZÀ-Ž][\wÀ-ž'’-]{2,})", namepart)
    if m3:
        ini = m3.group(1)
        t3 = re.match(r"^(.*\.\s*)(St\.\s*|S\.\s*)$", ini)
        if t3 and re.search(r"[A-ZÀ-Ž]", t3.group(1)) and (t3.group(2).startswith("St") or namepart[len(ini):].startswith("Peterburg")):
            ini = t3.group(1)
        namepart, place = ini, namepart[len(ini):] + place
    ch = [c.strip(" .") for c in namepart.split(",")]
    out["name"] = clean(f"{sur}, {ch[0]}") if ch and ch[0] else clean(sur)
    if m3 and re.search(r"\b[A-ZÀ-Ž][a-zà-ž]?$", out["name"]): out["name"] += "."   # the initial's own stop kept
    out["occupation"] = clean(", ".join(c for c in ch[1:] if c))
    out["surname"] = clean(sur)
    # the place: country last; the town the last chunk before it that is a place word, not a street, a house or a
    # governorate's name after «gub.»
    # a chunk ends at «. » after a word of two letters or a number («L. 18, 4. Germanujo»), not after an initial («S. Peterburg»)
    # nor after a saint's abbreviation («St. Louis»: the second accuracy check, 2026-10-29, towns cut to «St.»)
    pch = [c.strip() for c in re.split(r"(?:(?<=[\wÀ-ž'’^-]{2})(?<!\bSt)(?<!\bSte)(?<!\bSv)|(?<=\d))\.\s+", place.strip(" .")) if c.strip()]
    # A, the town run on to the initials («Nejman, M. Bobrujsk. R.», «Henriclundquist?, G. Ystad. S.»): only the country
    # letters were left for the place (the first assembly, 2026-10-29: «{loĝado: R}»); the town is the name part's last
    # word that is no initial
    if series == 1 and len(pch) == 1 and len(re.sub(r"\W", "", pch[0])) <= 3:
        ws = (ch[0] if ch else "").split()
        if len(ws) >= 2 and not re.fullmatch(r"[A-ZÀ-Ž][a-zà-ž]{0,2}\.", ws[-1]):
            out["town"] = clean(ws[-1]).strip(" .,")
            out["name"] = clean(f"{sur}, {' '.join(ws[:-1])}")
            return out
    if series == 1 and pch:   # A: «Rtiŝĉevo, gub. Saratov. R.»: the town first, the country letters last
        # … or the street first, the town after («Demonget, A. Boulevard de Clichy N. 8. Paris. F.»; 2026-11-01)
        k = next((i for i, c in enumerate(pch[:-1]) if not (re.search(r"\d", c.split(",")[0]) or STREETW.search(c.split(",")[0]))), 0)
        out["town"] = clean(pch[k].split(",")[0])
        out["address"] = clean(", ".join(pch[:k] + pch[k].split(",")[1:] + pch[k + 1:-1])).strip(" ,")
        return out
    body_ch = pch[:-1] if len(pch) > 1 else pch
    town, ti = "", None
    for i, c in enumerate(body_ch):
        first = c.split(",")[0].strip()
        if re.search(r"\d", first) or STREETW.search(first) or len(re.sub(r"\W", "", first)) < 3: continue
        if i and NOTPLACE.search(body_ch[i - 1]): continue
        # a street with its house after it («Bolŝaja Morskaja, dom Ĵigalkina»), a school or a bank, the railway's «dor.»
        # («ĵel. dor.»): no town (2026-11-01: Pavlenko filed at Bolŝaja Morskaja, Semenov at «dor»)
        if any(re.match(r"(?:dom|d)\b\.?", p.strip()) for p in c.split(",")[1:]): continue
        if re.search(r"Uĉiliŝĉe|Seminari|Gimnazi|Pansion|\bBank\b|Biuro", first) or (i and re.search(r"ĵel\.?$", body_ch[i - 1])): continue
        if re.fullmatch(r"(?:ĵel|dor|dorogi)\.?", first): continue
        town, ti = first, i
    out["town"] = clean(town)
    if ti is not None:
        out["address"] = clean(", ".join([c for j, c in enumerate(body_ch) if j != ti] + body_ch[ti].split(",")[1:])).strip(" ,.")
    return out

def entries():
    """[(item, ¶, series, year, number, text)] over every series file, in order."""
    out = []
    for f in sorted(glob.glob(os.path.join(BD, "adresaro-*.txt"))):
        item = os.path.basename(f)[:-4]
        series, year = 0, 0
        for para, sec, text in BDL.blocks(open(f, encoding="utf-8").read()):
            t = text.strip()
            m = SECTION.search(t)
            if m and t.startswith("==="): series, year = roman(m.group(1)), int(m.group(2)); continue
            m = ENTRY.match(t)
            if m and series: out.append((item, para, series, year, int(m.group(1)), re.sub(r"\s+", " ", m.group(3))))
    return out

WIKI = os.path.join(G, "sources", "adresaro-wikisource")
def wiki():
    """{(item, number): (the starred parts, the town's Wikidata id)} from the Wikisource wikitext (2026-10-29: the
    transcription marks the name and the town with «*…*» and gives the town's Wikidata item, u=Q…; the plain texts in
    born-digital-text/ lost both): «{{Adresaro|1795. *Alterman, M.* Moskovskaja ul. N-o 23. *Nikolajev*, gub. Ĥerson. …
    |n=1795|s=8|…|u=Q41572|v=}}»."""
    items = {}
    for f in glob.glob(os.path.join(BD, "adresaro-*.txt")):
        m = re.match(r"adresaro-\d{4}-serio-(\d\d)(?:-(\d))?$", os.path.basename(f)[:-4])
        if m: items[(int(m.group(1)), int(m.group(2) or 0))] = os.path.basename(f)[:-4]
    out = {}
    for p in glob.glob(os.path.join(WIKI, "Serio_*.wikitext")):
        m = re.match(r"Serio_([IVXL]+)(?:_(?:Parto|Peco)_(\d))?\.wikitext$", os.path.basename(p))
        item = items.get((roman(m.group(1)), int(m.group(2) or 0))) if m else None
        if not item: continue
        # one template at a time: a template without the usual fields let the match run on into the next (5 of them;
        # 2026-10-31, entry 4029 Chaufoureaux named «Solomon Sluckij» of Elisavetgrad, 4028's starred parts)
        for e in re.finditer(r"\{\{Adresaro\|((?:(?!\{\{).)*?)\|n=(\d+)\|s=\d*\|p=[^|]*\|l=[^|]*\|r=[^|]*\|u=([^|]*)\|", open(p, encoding="utf-8").read(), re.S):
            out[(item, int(e.group(2)))] = (re.findall(r"\*([^*]+)\*", e.group(1)), e.group(3))
    return out

def marked(e, W, item, n, s, t):
    """THE NAME AND THE TOWN AS THE TRANSCRIPTION MARKS THEM, where it does, into the parse e of the entry t: name first to
    series XV, the town first from XVI (series XVI, format C, «Rusujo. Milin, Ĉernigovskoj gub: Evlampia Sereda.»: the
    accuracy check of 2026-10-29 found «la nomon de Milin», name and town swapped), the name the last marked part there
    (a post town marked too: «*Nickelsdorf* p. *Grünhayn*, Ostpr.: *Ad. Ebner*», 87 entries with three); only the marked
    parts the entry's own text carries (2026-10-31: a template whose number is not the text's, «Abesgus, Josif» on
    Alŝfan's entry 1960). The parse keeps the occupation, the address and the collector. Also read by tools/gazetteer.py
    and tools/old-format-port.py."""
    st, q = W.get((item, n), ([], ""))
    own = clean(t)
    st = [clean(x).strip(" ,.") for x in st if clean(x).strip(" ,.") and clean(x).strip(" ,.") in own]
    if len(st) >= 2 or (st and s >= 16):
        # of three marked parts or more, the name the one that shares words with the parse's name (a town marked after
        # it: «VJATKA … Vladimir Ivanoviĉ Ogorodnikov … PUSTOPOLJE»), else the second
        pw = set(e["name"].lower().split())
        nm1 = max(st[1:], key=lambda x: (len(pw & set(x.lower().split())), -st.index(x))) if len(st) > 2 else st[-1]
        nm, tw = (nm1 if len(st) > 1 else e["name"], st[0]) if s >= 16 else (st[0], st[1] if len(st) > 1 else e["town"])
        e["name"], e["town"] = TITLES.sub("", nm).strip(), (tw.title() if tw.isupper() else tw)
        e["surname"] = (re.split(r",", e["name"])[0].split() or [""])[-1] if s < 17 and "," in e["name"] else (DX.surname_tokens(e["name"]) or [""])[-1]
    e["qid"] = q
    return e

def load_hits(path):
    """directory-extract.py's load_hits, the Adresaro's items only: the search over every directory at once wrote 11.3M hits
    (1.5 GB, 2026-10-29), most of them the Jarlibroj's."""
    h = collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(path, encoding="utf-8") as fh:
        rows = csv.reader((l for l in fh if "\tadresaro-" in l[:120] or l.startswith("person\t")), delimiter="\t")
        hd = next(rows); ix = {k: i for i, k in enumerate(hd)}
        for r in rows:
            if len(r) < len(hd) or r[ix["tier"]] not in ("exact", "near", "confusion") or not r[ix["page"]].isdigit(): continue
            d = h[(r[ix["item"]], int(r[ix["page"]]))][DX.norm(r[ix["as_read"]])]
            if d.get(r[ix["person"]]) != "exact": d[r[ix["person"]]] = r[ix["tier"]]
    return h

def join(hits, item, para, name, surname, town):
    """(label, verdict, how, candidates) for a name in an entry: as directory-extract.py's officers."""
    ph = hits.get((item, para), {})
    cands, tiers = {}, {}
    for w in [surname] + [t for t in DX.surname_tokens(name) if t != surname]:
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

DNOTE = "⟦la jaro de la serio de la Adresaro⟧"

def anchor(t):
    """An entry under six words («Nejman, M. Bobrujsk. R.») padded to six with ⟨fino⟩, the harvest's own mark for a text that
    short (the editor, 2026-10-14); the first assembly, 2026-10-29: 1,437 lines with no anchor of six. A «[…]» (the
    collector) counts as no word: the harvest takes square brackets for our own insertions (the second assembly:
    «Fredberg, Ebba, s-rino. Mellerud. Svedujo. [J. Fredberg.]», five words)."""
    aw = t.split()[:12]
    nw = len(re.sub(r"\[[^\]]*\]", " ", " ".join(aw)).split())
    return " ".join(aw + ["⟨fino⟩"] * max(0, 6 - nw))

def person_lines(e, t, s, y, n, item, para, hp, conf, gz, cnt):
    """The entry's lines for its registrant, written under hp («NAME $$$ (qualifier)») with the voice conf. Also read by
    tools/old-format-port.py adresaro (the September lines ported, 2026-10-31)."""
    lines, loc, anc = [], f"{item}, ¶ {para}", anchor(t)
    shown = DX.clean_name(e["name"]) or e["name"]
    # a wife entered under her husband's initials («S^ino^ W. Fison»: the check of 2026-10-29, the title lost, so the
    # line read as W. Fison himself): the title kept, and the identification marked ❓
    if re.search(r"\b(?:S\^?ino\^?|S-ino|Sinjorino|s-rino)\b", t) and not any(len(w.strip(".,")) >= 3 for w in shown.split()[:-1]):
        shown = "S-ino " + shown; conf = conf.replace("📣 (", "📣 ❓ (", 1)
    lines.append(f"- $$$ {hp} **{y}** · {{aperoj: Adresaro de Zamenhof, n-ro {n}}} · {shown} aperas en la Adresaro de Zamenhof, serio {s}, n-ro {n}. · {anc} · {loc} · [?] · {conf}")
    if e["town"]:
        ad = e["address"].strip("() ")   # an address printed in brackets («(ug. Kuzneckoj ul. …)»), once only
        where = f" ({ad})" if ad else ""
        # THE TOWN BY THE GAZETTEER (the editor, 2026-10-29: a gazetteer, with national-language
        # and Esperanto entries): the Esperanto name in the key, the national name beside it; unjoined, as printed
        g = gz.get(("Adr", e["town"], GZ.printed_country(t), e.get("qid", "")))
        if g and g["article"]:
            tk, tshown, tnote = GZ.town_line(g, e["town"]); cnt["towns by the gazetteer"] += 1
        else:
            tk = tshown = e["town"]; tnote = f"⟦la urbo: Wikidata {e['qid']}⟧" if e.get("qid") else ""
        # the address after a comma where the town has its national name in brackets («Akeno (Aachen), …»)
        if ad and "(" in tshown: where = f", {ad}"
        lines.append(f"- $$$ {hp} **{y}** · {{loĝado: {tk}}} · {shown} loĝas en {tshown}{where}. · {anc} · {loc} · [?] · {conf[:-1] + f'; {tnote})' if tnote else conf}")
    # a degree or letters after the name is no occupation («Walter Dexter, R. B. A.»)
    # a chunk with a verb is no occupation («lernanto, kolektas poŝtkartojn kun vidaĵoj»: the check of 2026-10-29,
    # «estas kolektas»): the occupation is the chunks without one
    occ = ", ".join(c for c in e["occupation"].split(", ") if not re.search(r"\b\w+(?:as|is|os)\b", c))
    if occ and len(occ) <= 80 and not re.fullmatch(r"(?:[A-Z]\.\s*){1,5}[A-Z]?\.?", occ.strip()):
        lines.append(f"- $$$ {hp} **{y}** · {{profesio: {occ}}} · {shown} estas {occ}. · {anc} · {loc} · [?] · {conf}")
    return lines

def collector_line(e, t, s, y, n, item, para, hp, conf):
    """The entry's line for its collector, under hp with the voice conf. Dated «ĝis» the series' year: the name was sent
    before the series was printed, so the year is the latest the sending can be (the accuracy check of 2026-11-01, D
    «parte» on all seven such lines; the entry itself and the address stand in the series' year)."""
    nm = DX.clean_name(e["name"]) or e["name"]
    return (f"- $$$ {hp} **ĝis {y}** · {{propagando: {nm}, Adresaro n-ro {n}}} · "
            f"{e['collector']} sendis al la Adresaro de Zamenhof la nomon de {nm} (serio {s}, n-ro {n}). · "
            f"{anchor(t)} · {item}, ¶ {para} · [?] · {conf}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hits", required=True); ap.add_argument("--tag", required=True); ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, help="print the parse of the entry of this number, and stop")
    ap.add_argument("--gazetteer", help="the gazetteer build whose towns the lines take (profiles/gazetteer/GAZETTEER-FORMS-TAG.tsv)")
    a = ap.parse_args()
    gz = GZ.forms(a.gazetteer) if a.gazetteer else {}
    es = entries()
    if a.show:
        for item, para, s, y, n, t in es:
            if n == a.show: print(f"{item} ¶ {para} · serio {s} ({y}) · {t}\n   {parse(s, t)}")
        return
    outs = {k: os.path.join(D, f) for k, f in (("ret", f"facts-return-{a.tag}-adresaro.md"), ("tsv", f"adresaro-{a.tag}.tsv"), ("rev", f"ADRESARO-REVIEW-{a.tag}.md"))}
    if a.write and any(os.path.exists(p) for p in outs.values()): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs.values() if os.path.exists(p)))
    hits = load_hits(a.hits)
    W = wiki()
    rows, lines, cnt = [], [], collections.Counter()
    for item, para, s, y, n, t in es:
        DX.SELF_KEY = item   # this series' own tool lines bear nothing out (directory-extract.py borne_out, 2026-11-01)
        cnt["entries"] += 1
        e = marked(parse(s, t), W, item, n, s, t)
        if not e["surname"]: cnt["unparsed"] += 1; rows.append([item, para, s, y, n, t, "", "", "", "", "", "", "unparsed"]); continue
        label, verdict, how, cands = join(hits, item, para, e["name"], e["surname"], e["town"])
        cnt[verdict.split(":")[0]] += 1
        coll_label, coll_verdict = "", ""
        if e["collector"]:
            cnt["collectors"] += 1
            csur = (DX.surname_tokens(e["collector"]) or [""])[-1]
            coll_label, coll_verdict, chow, _ = join(hits, item, para, e["collector"], csur, "")
            cnt[f"collector {coll_verdict.split(':')[0]}"] += 1
        rows.append([item, para, s, y, n, t, e["name"], e["town"], e["address"], e["occupation"], e["collector"], cands, verdict + (f"; collector: {coll_verdict}" if e["collector"] else "")])
        if label:
            lines += person_lines(e, t, s, y, n, item, para, DX.profile(label)[2],
                                  f"📣 (sen fontindiko; {DNOTE}; ⟦identigo: {DX.profile(label)[0]}, laŭ {how} en la profilo⟧)", gz, cnt)
        if coll_label:
            lines.append(collector_line(e, t, s, y, n, item, para, DX.profile(coll_label)[2],
                                        f"📣 (sen fontindiko; {DNOTE}; ⟦identigo: {DX.profile(coll_label)[0]}, laŭ {chow} en la profilo⟧)"))
    cnt["lines"] = len(lines)
    print(", ".join(f"{k} {v}" for k, v in cnt.items()))
    if not a.write: return
    os.makedirs(D, exist_ok=True)
    with open(outs["tsv"], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["item", "para", "series", "year", "number", "entry", "name", "town", "address", "occupation", "collector", "roster hits (borne out by)", "verdict"]); w.writerows(rows)
    with open(outs["ret"], "x", encoding="utf-8") as fh:
        fh.write(f"# Return: facts-return-{a.tag}-adresaro.md\n\n`[Written by tools/adresaro-extract.py, {a.tag}, from the name search {os.path.basename(a.hits)}: Zamenhof's Adresaro, series I–XXIX, roster persons only, each borne out by the profile (runbook D4c). Not a legilo's return.]`\n\n")
        fh.write("\n".join(lines) + "\n")
    held = [r for r in rows if "held" in r[12]]
    with open(outs["rev"], "x", encoding="utf-8") as fh:
        fh.write(f"# Zamenhof's Adresaro, read by tool ({a.tag})\n\n`[GENERATED by tools/adresaro-extract.py. Do not hand-edit — re-run it.]`\n\n")
        fh.write("**Counts:** " + ", ".join(f"{k} {v}" for k, v in cnt.items()) + f". Every entry parsed: `{os.path.basename(outs['tsv'])}`; the lines: `{os.path.basename(outs['ret'])}`.\n\n")
        fh.write(f"## Held: {len(held)}\n\n")
        for r in held: fh.write(f"- `{r[0]}`, ¶ {r[1]} · n-ro {r[4]}: «{r[5][:160]}» · {r[11]} · {r[12]}\n")
    for p in outs.values(): print("wrote", os.path.relpath(p, ROOT))

if __name__ == "__main__":
    main()
