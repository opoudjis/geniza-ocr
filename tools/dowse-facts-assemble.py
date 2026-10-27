#!/usr/bin/env python3
"""dowse-facts-assemble.py: write a source's dowse facts file from its facts readers' returns (runbook D6).

The editor, 2026-10-11 12:4x,: what the Korĵenkov pilot did by a one-off script becomes a tool, with each
source's own decisions kept in a settings file in its dowse folder, committed with the dowse, so that a facts file can be
rebuilt exactly and its scope and spelling decisions stay on record.

    tools/dowse-facts-assemble.py <source> [--replace] [--dry-run]

reads   geniza/dowse/<source>/facts-config.json and the returns it names (in that folder); not «…settings.json»,
        because the sandbox protects every file of that name (Miles, 2026-10-11);
writes  geniza/profiles/by-source/<source>-dowse.md.

It refuses to write over an existing facts file unless --replace is given, and then only if git holds that file with no
uncommitted change (a reissue: the old file stays in git, runbook D8). Then run tools/harvest-facts.py --check and the
harvest, and work the missing-facts report, as D6 (11) says.

The steps, the same for every source:
  1. collect every fact line («- $$$ …») of the returns, in the order the settings list them; «replace_lines»
     [[string, new line]] replaces a reader's line containing the string by a corrected line, given whole;
  2. names: «names» maps a reader's NAME to the profiles' spelling; «rename» maps (NAME, qualifier) to a new NAME and
     qualifier (e.g. JACOB (Hans) → HANS JACOB); «qualifiers» rewrites (NAME, qualifier) after the name map
     (an empty new qualifier removes it);
  3. scope: a NAME in «drop» is left out, for reasons other than scope, e.g. a garbled OCR name held for the page
     image (the reasons go in the log; the returns keep the lines). Scope is decided by the scope register alone
     (profiles/SCOPE-REGISTER.tsv; the editor, 2026-10-14 11:3x to the consolidation; the per-source
     «out_of_scope» setting is retired and refused). A line headed by someone the register has out is left out, with one
     exception (the editor, 11:0x): if its «kun:» names someone in scope, it passes to the
     first person in scope, the rest staying in «kun:». People out of scope (or in «drop») are taken out of every «kun:»
     list, so that the harvest copies the line to no one out of scope. A register row with a qualifier («MORRIS (Alice
     V.)») applies only to lines with that qualifier; an unqualified row, to the surname;
  4. «quote_fixes»: [old, new] replacements in the fact text (quotations lengthened after harvest --check);
  5. locators: «locator_fixes» [[regex, replacement]] rewrite the locator first (a reader who shortened the item
     names, Neves 2026-10-11); «pages» {return: [first, last]} keeps a return's lines only on its own pages (overlapping
     readers), save lines containing a string in «keep_lines»; a page range «PDF 53–54 (prese 52–53)» takes its first page (the harvester takes no ranges);
  6. dates: «3 jul 1889» → 1889-07-03, «feb 1885» → 1885-02; other forms kept as written;
  7. themes: a line whose theme field is «[?]» gets themes by keyword (the legend of SCOUT-THEMES-BY-SIDE-2026-09-10.md
     § 1: [A] Russia and France in one fact, [B] Ido and reform, [G] offices and bodies, [BIO] the life and works,
     [X] afterlife and persecution; [G] when nothing matches). Rough: check a sample. A theme the reader gave is kept;
  8. «restore»: whole lines added as given (facts of an earlier file the readers did not reproduce);
  9. sorted by page (PDF N or ¶ N), returns before restored lines on the same page; «header» first.

Settings (JSON): item, returns [file names], header (text, «facts-format: 2» within it), names {}, rename
[[NAME, qual, NEW, newqual]], qualifiers [[NAME, qual, newqual]], drop [], out_of_scope [], quote_fixes [[old, new]], locator_fixes
[[regex, replacement]], replace_lines [[string, line]], restore [lines].
(Ezri, 2026-10-11)"""
import argparse, collections, csv, glob, json, os, re, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
MON = dict(jan="01", feb="02", mar="03", apr="04", maj="05", jun="06", jul="07", aŭg="08", sep="09", okt="10", nov="11", dec="12")
LINE = re.compile(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))? (.*)$")
KUNP = re.compile(r"^(.+?)(?:\s*\(([^)]*)\))?$")

def fold(w):
    """A NAME as a key: diacritics, ligatures and case folded, the qualifier dropped (as the harvest's slugs)."""
    import unicodedata
    w = re.sub(r"\s*\(.*\)", "", w).replace("Œ", "OE").replace("œ", "oe").replace("Æ", "AE").replace("æ", "ae")
    f = "".join(c for c in unicodedata.normalize("NFD", w.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", f).strip("-")

def register_out():
    """The scope register's «out» people (profiles/SCOPE-REGISTER.tsv, proposed or confirmed): {(fold(NAME), qualifier
    or None)}. The register is the only scope list (the editor, 2026-10-14 11:3x to the consolidation)."""
    p = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
    if not os.path.exists(p): return set()
    rows = [l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8") if not l.startswith("#")]
    out = set()
    for r in rows[1:]:
        if len(r) > 4 and r[4] == "out":
            m = KUNP.match(r[0].strip()); out.add((fold(m.group(1)), (m.group(2) or "").strip().lower() or None))
    return out

def register_out_unconfirmed():
    """The «out» rows not confirmed by the editor, {(fold(NAME), qualifier or None): «plain» or «review»}: a row out by
    a plain rule («born 1901: cannot have joined before 1908», a stated late joining) needs no review (the editor, 2026-10-15); the others go to the
    session's sign-off. They act all the same (the editor)."""
    p = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
    if not os.path.exists(p): return {}
    res = {}
    for r in [l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8") if not l.startswith("#")][1:]:
        r += [""] * (8 - len(r))
        if r[4] != "out" or r[6] == "confirmed": continue
        m = KUNP.match(r[0].strip())
        def late(v, cut): y = re.search(r"\d{4}", v); return ("after" in v and str(cut) in v) or bool(y and int(y.group()) >= cut)
        plain = (re.match(r"born \d{4}: cannot have joined", r[7]) or late(r[2], 1908) or late(r[3], 1931)
                 or r[1] == "neither" or r[7].startswith(("mechanical, from the EdE", "moved from the per-source")))
        # out by a stated late joining, a birth date, the editor's own earlier per-source rulings, or the signed
        # mechanical fill: «plain», no review; anything else to the session's sign-off
        res[(fold(m.group(1)), (m.group(2) or "").strip().lower() or None)] = "plain" if plain else "review"
    return res

BARE = "\x00bare"   # a marker in the register set: the surname's bare lines are out by a qualified row
BARE_COVER = False

def bare_cover(reg):
    """The surnames whose one qualified «out» row also covers their bare lines (the editor, 2026-10-15): the venture knows no namesake for the surname: no entry in the harvest's
    PERSONS table, no default bearer in the names register, no other row for the surname in the scope register."""
    import ast
    src = open(os.path.join(ROOT, "tools", "harvest-facts.py"), encoding="utf-8").read()
    m = re.search(r"^PERSONS = (\{.*?^\})", src, re.M | re.S)
    names = {fold(k) for k in ast.literal_eval(re.sub(r"#[^\n]*", "", m.group(1)))} if m else set()
    np_ = os.path.join(G, "profiles", "NAMES-REGISTER.tsv")
    for r in (l.rstrip("\n").split("\t") for l in open(np_, encoding="utf-8") if not l.startswith("#")):
        if len(r) > 3 and "default bearer" in r[3]: names.add(fold(re.sub(r"\s*\(.*", "", r[0])))
    p = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
    rows = collections.Counter()
    for r in (l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8") if not l.startswith("#")):
        if r and r[0] != "name": rows[fold(KUNP.match(r[0].strip()).group(1))] += 1
    return {k for k, q in reg if q and k not in names and rows[k] == 1}

def is_out(name, q, reg):
    """Out by the register? An unqualified row puts the surname out; a qualified one only the lines with a qualifier
    that agrees (one begins the other: «Alice» and «Alice V.»), so one Zamenhof's row leaves the others in; with
    --bare-cover, a qualified row also takes the bare lines of a surname the venture knows no namesake for."""
    k, q = fold(name), (q or "").strip().lower()
    if (k, None) in reg: return True
    if not q and (k, BARE) in reg: return True
    return bool(q) and any(rk == k and rq and (q.startswith(rq) or rq.startswith(q)) for rk, rq in reg)

def kun_rotate(name, q, rest, out, names, head_out):
    """The «kun:» list of a line, rid of the people out of scope (out: a test (name, qualifier) -> bool); and, when the
    head is out of scope (head_out), the line passed to the first person left.
    -> (name, q, rest, what happened: None | "trimmed" | "rotated" | "all out")."""
    m = re.match(r"^(\*\*.*?\*\* · \{)([^}]*)(\}.*)$", rest)
    if not m: return name, q, rest, ("all out" if head_out else None)
    segs = [x.strip() for x in m.group(2).split(";")]
    ki = next((i for i, x in enumerate(segs) if x.startswith("kun:")), None)
    if ki is None: return name, q, rest, ("all out" if head_out else None)
    ppl = [x.strip() for x in re.split(r"\s+kaj\s+", segs[ki][4:].strip())]
    inn = [p for p in ppl if not out(names.get(KUNP.match(p).group(1), KUNP.match(p).group(1)), KUNP.match(p).group(2))]
    if head_out:
        if not inn: return name, q, rest, "all out"
        hm = KUNP.match(inn[0]); name, q = names.get(hm.group(1), hm.group(1)), hm.group(2) or ""; inn = inn[1:]
        what = "rotated"
    elif len(inn) == len(ppl): return name, q, rest, None
    else: what = "trimmed"
    segs = segs[:ki] + ([f"kun: {' kaj '.join(inn)}"] if inn else []) + segs[ki + 1:]
    return name, q, m.group(1) + "; ".join(segs) + m.group(3), what

def themes(fact):
    f = fact.lower()
    t = []
    if re.search(r"rusland|ruslanda|\brus[aoe]", f) and re.search(r"franci|francaj|franc[oa]j?\b", f):
        t.append("A")
    if re.search(r"\bido\b|idist|delegaci|reform|skism|adjuvanto|esperantido|romanal", f):
        t.append("B")
    # THE THEME RULING (the editor, 2026-10-12 00:3x, on THEME-RECOUNT-2026-10-12.md; QUEUE «PARKED: THEME-TAG
    # GRANULARITY»): [C] is now interlinguistics, the other languages (the old [C], acknowledging rivals, and [X], erasure,
    # are dropped as fact tags); [L] is the person's own language;
    # publishing leaves [G] and [V] for [ELD]; congresses stay in [G] (answer 00:3x: «Congresses stay in G»);
    # correspondence and archives are [KOM] («It's not Verko, it's not Aserto, it's Komunikis»); assertions and
    # judgements are [AS] («nomis is a claim, an aserto … as are judgements»)
    if re.search(r"volapük|volapuk|occidental|novial|interglossa|latino sine|idiom neutral|spokil|bolak|romanal|adjuvanto|"
                 r"interlingvist|helplingv|lingvoprojekt|projektoj? de internacia lingvo|propran projekton|artefarit|planlingv|universala lingvo|mondolingv|pasigrafi", f):
        t.append("C")
    if re.search(r"komitat|akademi|prezid|sekretari|oficejo|\bligo|ligon|societ|kongres|regularo|organiz|\buea\b|sfpe|\brel\b|estraro|asocio|voĉdon|grupo|delegit|aliĝis al la|aliĝo al la|konsul|cirkuler|statut|ick\b|kkk|unuiĝo", f):
        t.append("G")
    if re.search(r"gazet|revu[oa]|periodaĵ|redakt|eldonej|eldonist|eldonad|presej|hachette|kontrakt|abonant|abonoj|aboni", f):
        t.append("ELD")
    if re.search(r"leter|korespond|aŭtograf|arkiv|arĥiv|manuskript.*kolekt|kolekto de|skribis al|vizitis|renkont|interparol", f):
        t.append("KOM")
    if re.search(r"\(aserto pri|\(aproba aserto|\(malaproba aserto|\(refutita aserto|\basert|\bnomis\b|\bjuĝ|opini|kritik|"
                 r"laŭdis|laŭdo|laŭdi\b|riproĉ|taksis|konsideris|atestis|suspekt|akuzis|akuzo|mokis|kondamn", f):
        t.append("AS")
    # [KAR] characterisations and judgements made ABOUT the person, by a source or another person (the editor 2026-10-12
    # 00:4x: «About = separate tag»; «[KAR]»). Keywords catch only some; the dowse
    # reader marks the rest
    if re.search(r"humila|fanatik|diletant|malestim|ofend|kalumni|karakter|ambici|afabl|obstin|fiera?\b|modest|vant[ae]c|"
                 r"senkompat|perfidul|judaso|mitoman|honest|sincer|malfidel|timema|naiv|aroganc|talent|\bgeni[ao]|majstre|"   # \b: not «Ifigenio» (2026-10-12)
                 r"respektat|admirat|malamat|populara|nepopulara|influ[oa]\b|emocie|ideologie", f):
        t.append("KAR")
    # [L] the language itself, [V] the works, generously (the editor 2026-10-11
    #); [BIO] narrowed to the life ()
    if re.search(r"gramatik|elizi|akuzativ|ortografi|supersign|radik|sufiks|prefiks|afiks|prononc|akcent|\bstil|metrik|versfar|\brim[ao]|vortfar|derivad|kunmet|neologism|finaĵ|apostrof|\bliter(o|oj)\b|alfabet|vortprovizo|vortaro|sintaks|morfolog|fonetik|naturalism|vortteori|licenc|versoj|verso\b", f):
        t.append("L")
    if re.search(r"verk|traduk|kompil|bibliografi|aŭtor|poem|poezi|roman|rakont|vortaro|lernolibr|artikol|kajer|broŝur|\beseo|antologi|libro|recenz|publikigis|eldonis|himno|kanto|dramo", f):
        t.append("V")
    if re.search(r"\bnom(o|on|oj|ojn|formo)\b|nask|mort|vivdat|profesi|kuracist|okulkurac|studis|edzin|edziĝ|famili|fil(o|ino)\b|patr(o|ino)|fratin|frato|loĝis|ekloĝis|esperantistiĝ|eklernis|lernis|pseŭdonim|arest|ekzekut|ekzil|\bjud|hebre|instruisto|profesoro|filozof|kemiist|matematik|inĝenier|generalo|oficiro|advokat|pastro|pastoro|okulist|stenograf|student|komercist|ĵurnalist|honora legio|nobel|malsan|tomb|fum|vojaĝ|gimnazi|universitat|diplom|soldat|milit", f):
        t.append("BIO")
    return "".join(f"[{x}]" for x in (t or ["?"]))      # no match: «[?]», not a [G] fallback

QUOTE = re.compile(r"«([^«»]*(?:«[^»]*»[^«»]*)*)»")

def split_anchor(fact, least=6):
    """FACTS FORMAT 3 (the editor 2026-10-11): the anchor leaves the fact for its own field. The anchor is the last
    quotation of six or more words (the readers write it last); -> (fact without it, anchor) or (fact, None). A line
    that cites its text line («l. K», 2026-10-17) may have a shorter anchor (least=1): the line, not six words, then
    places it, where the OCR is too garbled for six."""
    # a quotation that is nothing but a bracketed passage is the source's own print, and its words count (2026-10-21;
    # the editor; harvest-facts.py's segments() the same: «[Gazeta eltranĉo, sendita de W. H. Trompeter.]»)
    def words(q):
        nb = re.sub(r"\[[^\]]*\]|…|\.\.\.", " ", q)
        return (nb if re.search(r"\w", nb.replace("⟨fino⟩", "")) else re.sub(r"[\[\]]|…|\.\.\.", " ", q)).split()
    ms = [m for m in QUOTE.finditer(fact) if len(words(m.group(1))) >= least]
    if not ms: return fact, None
    m = ms[-1]
    if fact[m.end():].strip(" .;,"):
        # the quotation is part of the sentence, not its tail (a difference line: «la ida diras «X», la esperanta «Y»; …»):
        # it stays in the fact and is copied to the anchor field (found 2026-10-11, the Kofman difference line)
        return fact, m.group(1)
    rest = (fact[:m.start()].rstrip().rstrip(":;,").rstrip() + " " + fact[m.end():].lstrip()).strip()
    rest = re.sub(r"\s{2,}", " ", rest).rstrip(":;,").rstrip()     # no «;» or «:» left dangling (K1, 2026-10-11)
    return rest, m.group(1)

PRUVO = re.compile(r"\s*\((nur en la (?:ida|esperanta) (?:eldono|versio)[^()]*(?:\([^()]*\)[^()]*)*)\)")

def mechanical(fact, conf):
    """The combined pass's mechanical changes (2026-10-11): «(bibliografio)» as a head marker (the editor); a single-copy note moves to «pruvo:» in the confidence field (the editor); «s.d.» in references (the editor)."""
    fact = re.sub(r"^(?:bibliografio|Bibliografio|bibliografia ero|Bibliografia ero)(?: \([^)]*\))?:\s*", "(bibliografio) ", fact)
    notes = [m.group(1) for m in PRUVO.finditer(fact)]
    if notes:
        fact = PRUVO.sub("", fact).strip()
        add = "; ".join(f"pruvo: {n}" for n in notes)
        conf = re.sub(r"\)\s*$", f"; {add})", conf) if conf.rstrip().endswith(")") else f"{conf} ({add})"
    conf = conf.replace("sen dato en la fonto", "s.d.")
    return fact, conf

def split_top(s, sep=";"):
    """Split at «sep» outside brackets, quotes and ⟦…⟧."""
    out, cur, d = [], "", 0
    for c in s:
        if c in "([«⟦": d += 1
        elif c in ")]»⟧": d = max(0, d - 1)
        if c == sep and d == 0: out.append(cur); cur = ""
        else: cur += c
    return out + [cur]

def bracket(conf):
    """Our additions in ⟦…⟧ (the editor, 2026-10-14; signed off approved, ocr/method/ALIGN-JAM-RULE-PROPOSAL-2026-10-14.md, B):
    in the labels' bracket, a «pruvo:», an identification, a correction, a computed date or an unchecked reading that a
    reader wrote unbracketed becomes «⟦pruvo: …⟧», «⟦identigo: …⟧», «⟦korektita: …⟧», «⟦kalkulite: …⟧», «⟦ne kontrolita:
    …⟧». The labels about the source itself (sendependa, derivita ↤, sen fontindiko, refutas, kopio el) stay outside."""
    if not re.search(r"\)\s*$", conf): return conf
    # every bracket of the field, each rewritten where it stands, not the span from the first «(» to the last «)»:
    # «(sendependa) ❓ (OCR …, kalkulita …)» (2026-10-18, the dowse fixes: Ruslanda Esperantisto's 80 additions outside
    # ⟦…⟧). The brackets are not joined: a first try joined them and lost the ❓ and between them on 28 lines.
    # Our ⟦…⟧ notes and the «…» quotes are hidden first: their brackets may nest deeper or not close («(TROMPETER
    # (Wilhelm Heinrich))», «(Reĝo Lear de Shakespeare,», the OCR's «SALato (Kaj Sue», «lll)aguHCcxiĤ»), and the first
    # tries lost labels and text to them; a field whose brackets still do not close is left as the reader wrote it.
    held = []
    def hide(mm): held.append(mm.group(0)); return f"\x00{len(held) - 1}\x00"
    def show(s):
        while "\x00" in s: s = re.sub(r"\x00(\d+)\x00", lambda mm: held[int(mm.group(1))], s)
        return s
    h = re.sub(r"«[^«»]*»", hide, re.sub(r"⟦[^⟧]*⟧", hide, conf))
    SRC_LABEL = re.compile(r"^(?:sendependa|derivita|sen fontindiko|refutas|kopio el|\(refutita)")
    def labels(g):
        out = []
        for s in split_top(g):
            t = s.strip()
            if not t or t.startswith("⟦"): out.append(t); continue
            if re.match(r"pruvo:\s*kalkulit", t): lab, body = "kalkulite", re.sub(r"^pruvo:\s*kalkulite?:?\s*", "", t)
            elif re.match(r"kalkulit\w*", t): lab, body = "kalkulite", re.sub(r"^kalkulit\w*[:,]?\s*", "", t)   # «kalkulita: …», «kalkulita jaro»
            elif re.search(r"identig", t) and not SRC_LABEL.match(t): lab, body = "identigo", re.sub(r"^pruvo:\s*", "", t)
            elif t.startswith("pruvo:"): lab, body = "pruvo", t[6:].strip()
            elif re.search(r"korektit", t) and not SRC_LABEL.match(t): lab, body = "korektita", t
            elif t.startswith("ne kontrolita"): lab, body = "ne kontrolita", re.sub(r"^ne kontrolita(?: sur la paĝobildo)?:?\s*", "", t)
            # a note of ours with its cue inside it («la dato de la numero, kalkulita»): wrapped whole, by its cue
            elif not SRC_LABEL.match(t) and (cue := re.search(r"kalkulit|pruvo:|nia identigo|ne kontrolita", t)):
                lab = {"k": "kalkulite", "p": "pruvo", "n": "identigo" if cue.group(0).startswith("nia") else "ne kontrolita"}[cue.group(0)[0]]
                body = t
            else: out.append(t); continue
            out.append(f"⟦{lab}: {body}⟧" if body else f"⟦{lab}⟧")
        return "; ".join(x for x in out if x)
    pieces, depth, start, last = [], 0, 0, 0
    for i, c in enumerate(h):
        if c == "(":
            if depth == 0: start = i
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0: return conf
            if depth == 0:
                pieces.append(show(h[last:start]) + "(" + labels(show(h[start + 1:i])) + ")"); last = i + 1
    if depth: return conf
    return "".join(pieces) + show(h[last:])

_PAGEMAP = {}
def cited_line(D, ret, line):
    """THE LINE A READER CITES (2026-10-17; the editor): the reader reads its own pages file (facts-pages-<tag>-<N>.txt, the units of the text copied whole, each with
    its «=== page N ===» marker), so its «l. K» counts that file's lines. It becomes the text's own line: the marker
    before K, found in the text, plus K's distance from it. A return with no pages file (a reader who read the whole
    text) cites the text's lines already: unchanged. A K the conversion cannot place is left out, so no wrong line
    stands; the tools then find the line by the anchor (tools/fact-lines.py)."""
    m = re.search(r"(, (?:PDF \d+(?: \(prese [^)]+\))?|¶ \d+)), l\. (\d+)\b", line)
    mr = re.fullmatch(r"facts-return-(.+)-(\d+)\.md", ret)
    if not m or not mr: return line
    pf = os.path.join(D, f"facts-pages-{mr.group(1)}-{mr.group(2)}.txt")
    if not os.path.exists(pf): return line
    if pf not in _PAGEMAP:
        pl = open(pf, encoding="utf-8").read().split("\n")
        _PAGEMAP[pf] = pl
    pl, k = _PAGEMAP[pf], int(m.group(2))
    marker, text, at = None, None, None
    for i in range(min(k, len(pl)) - 1, -1, -1):
        if marker is None and re.match(r"^=== (?:page|¶) \d+ ===", pl[i]): marker, at = pl[i].strip(), i + 1
        mt = re.match(r"^=== teksto: (.+?) ===", pl[i])
        if marker and mt: text = mt.group(1); break
    src = None
    if marker:
        cfgp = os.path.join(D, "brief-config.json")
        texts = json.load(open(cfgp, encoding="utf-8")).get("texts", []) if os.path.exists(cfgp) else []
        cand = [t for t in texts if text and os.path.basename(t)[:-4] == text] or texts[:1]
        if cand:
            tp = os.path.join(G, cand[0])
            if tp not in _PAGEMAP: _PAGEMAP[tp] = open(tp, encoding="utf-8").read().split("\n")
            tl = _PAGEMAP[tp]
            pos = next((j for j, x in enumerate(tl, 1) if x.strip() == marker), None)
            if pos: src = pos + (k - at)
    new = f"{m.group(1)}, l. {src}" if src else m.group(1)
    return line[:m.start()] + new + line[m.end():]

_FL, _FLT = None, {}
def place_line(loc, head, anchor):
    """(text line, «ankro» or «nomo») for a short anchor, by tools/fact-lines.py's own search, or None."""
    global _FL
    if _FL is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fact_lines", os.path.join(ROOT, "tools", "fact-lines.py"))
        _FL = importlib.util.module_from_spec(spec); spec.loader.exec_module(_FL)
        _FL.fid = _FL.load("fid", os.path.join(ROOT, "tools", "fact-ids.py"))
    m = re.match(r"^\s*(?P<item>[^,·]+?), PDF (?P<pdf>\d+)", loc)
    if not m: return None
    path = os.path.join(G, "sources", "ocr-preferred", m.group("item").strip() + ".txt")
    if not os.path.exists(path): return None
    if path not in _FLT: _FLT[path] = _FL.page_words(path, _FL.fid)
    pw, page = _FLT[path], int(m.group("pdf"))
    segs = [s for s in re.split(r"…|\.\.\.", anchor) if s.strip()]
    words = _FL.fid.norm(max(segs, key=lambda s: len(s.split())) if segs else anchor).split()
    ln = _FL.find_line(pw, page, words) if words else None
    if ln: return ln, "ankro"
    sur = _FL.fid.norm(head).split(); key = max(sur, key=len) if sur else ""
    hits = sorted({x for w, x in pw.get(page, []) if key and len(key) >= 4 and w == key})
    return (hits[0], "nomo") if len(hits) == 1 else None

def expand_lean(D, ret, line):
    """harvest-facts.py's expand_lean on a line of return RET, with the reader's pages file (facts-pages-<tag>-<N>.txt)
    and, for a source of one text, that text's item (2026-10-18, the lean brief)."""
    mr = re.fullmatch(r"facts-return-(.+)-(\d+)\.md", ret)
    # the lean locator, or its line before the printed page («l. 220 (prese 4)», La Esperantisto range 2, 2026-10-21:
    # harvest-facts.py's expand_lean reorders it, but this test had passed the line by unexpanded, and 16 were held back)
    if not mr or not re.search(r"\bl\. ?\d+(?: \(prese [^)]*\))?(?: · |$)", line): return line
    pf = os.path.join(D, f"facts-pages-{mr.group(1)}-{mr.group(2)}.txt")
    if not os.path.exists(pf): return line
    if pf not in _PAGEMAP: _PAGEMAP[pf] = open(pf, encoding="utf-8").read().split("\n")
    cfgp = os.path.join(D, "brief-config.json")
    texts = json.load(open(cfgp, encoding="utf-8")).get("texts", []) if os.path.exists(cfgp) else []
    form_repair("- $$$ X $$$")   # loads the harvest module
    return _HF.expand_lean(line, _PAGEMAP[pf], os.path.basename(texts[0])[:-4] if len(texts) == 1 else "")

def published_pages(run, step):
    """THE PUBLISHED SIGLA PAGE after every harvest (2026-10-25; the editor): the items' online
    locations rebuilt (tools/online-locations.py --again: a new source's items get theirs), then prosopografio/siglaro.md
    (tools/sigla-propose.py --page). Never a stop: a refusal (a signed siglum with no Esperanto entry in SIGLA-EO.tsv)
    or a fault is flagged in the summary line and left for the dowser; the dowse goes on."""
    T = os.path.join(ROOT, "tools")
    page = os.path.join(G, "prosopografio", "siglaro.md")
    before = open(page, encoding="utf-8").read() if os.path.exists(page) else ""
    run(f"{step}, the items' online locations", [os.path.join(T, "online-locations.py"), "--again"], ok=lambda out, code: True)
    run(f"{step}, the sigla page (prosopografio/siglaro.md)", [os.path.join(T, "sigla-propose.py"), "--page", page],
        ok=lambda out, code: True)
    # THE PUSH IS NOT HERE (2026-10-25; Miles: SITE.tsv row «siglaro», page 113, child of «prosopografio»; every push is
    # the editor's word): the step says whether the page changed, and a changed page is put to the editor for Miles's push
    after = open(page, encoding="utf-8").read() if os.path.exists(page) else ""
    print(f"{'NOTE' if after != before else 'ok '} {step}, the Siglaro {'CHANGED: ask the editor whether to push it (Miles: genizo-push.py siglaro)' if after != before else 'unchanged: nothing to push'}")

_HF = None
def form_repair(line):
    """The form faults the tools repair: harvest-facts.py's form_repair itself, which file-return.py's check uses too
    (2026-10-17 19:5x: this tool had kept its own copy of the first two repairs, so the two added for the Ruslanda
    Esperantisto pilot, a note where the themes go, reached the check but not the assembly, and 62 lines came out
    scrambled). One function, so the check and the assembly cannot drift apart."""
    global _HF
    if _HF is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hf_form", os.path.join(ROOT, "tools", "harvest-facts.py"))
        _HF = importlib.util.module_from_spec(spec)
        saved, sys.argv = sys.argv, ["x"]
        try: spec.loader.exec_module(_HF)
        finally: sys.argv = saved
    return _HF.form_repair(line)

SCOPE_SEG = re.compile(r"aliĝo ne datita|amplekso|esperantist|idist", re.I)
DOUBT = re.compile(r"\?|dub|necert|erar|eble|ŝajn|kontraŭdir|malĝust|refut", re.I)

def scope_off(conf, fact):
    """The scope note off the line (the editor, 2026-10-17 12:3x; to the fix, «approved»). Whether a person is in scope (rules 3 and 4 of the reading
    brief until that day: «⚠ kaj «pruvo: aliĝo ne datita»», «provizore en la amplekso, … kun la kialo en «pruvo:»») is a
    fact about the person, settled once, not a doubt about the line; and ⚠ means the source doubts. So every part of a
    ⟦pruvo⟧ about the scope (joining undated, «provizore en la amplekso», whether he was an Esperantist or an Idist) is
    taken off and returned, for dowse/<source>/SCOPE-NOTES.tsv and the profile's banner; ⚠ goes with it unless something
    left on the line still doubts (a «?», «dubo», «necerta», «eraro», «eble», «ŝajne», a refuted claim)."""
    # each ⟦pruvo: …⟧ found by its own brackets, not by splitting the labels at «;» (a correction quoting «(Reĝo Lear …,»
    # left a bracket open and hid the note, Waringhien, 2026-10-17)
    took = []
    def one(mp):
        segs = [x.strip() for x in split_top(mp.group(1))]
        took.extend(x for x in segs if x and SCOPE_SEG.search(x))
        keep = [x for x in segs if x and not SCOPE_SEG.search(x)]
        return f"⟦pruvo: {'; '.join(keep)}⟧" if keep else ""
    new = re.sub(r"⟦pruvo:\s*([^⟦⟧]*)⟧", one, conf)
    if not took: return conf, []
    while True:   # the empty places a removed note leaves («; ;», «; )», «( ;», «»), until none is left
        was = new
        new = re.sub(r";\s*;", ";", new); new = re.sub(r";\s*\)", ")", new); new = re.sub(r"\(\s*;\s*", "(", new)
        new = new.replace(" ()", "").replace("()", "")
        if new == was: break
    m = re.match(r"^(.*?)(\(.*\))?\s*$", new, re.S)
    head, rest = m.group(1), m.group(2) or ""
    # our own dating notes are no doubt of the source («la jaro de la fonto …: la eseo eble pli frua», «⟦interpretdato⟧»)
    cue = re.sub(r"⟦(?:pruvo: la jaro de la fonto|interpretdato)[^⟦⟧]*⟧", "", rest)
    if "⚠" in head and not DOUBT.search(cue) and not fact.lstrip().startswith("(refutita"):
        head = re.sub(r"\s*⚠", "", head)
    return f"{head.rstrip()} {rest}".rstrip(), took

def one_note_each(conf):
    """One of each of our notes on a line (2026-10-17, the resmelt's faults T1: Collinson L13 with four ⟦pruvo⟧ notes
    repeating each other, L14 «la dato laŭ PDF 11, la Preludo …» beside «la dato de la Preludo laŭ PDF 11»; the
    interventions register re-attaches a note the reader wrote again in other words). A ⟦label: …⟧ whose words all stand
    in another note of the same label on the line goes; the longer stays."""
    notes = re.findall(r"⟦([^⟦⟧:]+):?\s*([^⟦⟧]*)⟧", conf)
    if len(notes) < 2: return conf
    ws = [(lab, set(re.findall(r"\w{3,}", body.lower()))) for lab, body in notes]
    drop = set()
    for i, (li, wi) in enumerate(ws):
        for j, (lj, wj) in enumerate(ws):
            if i != j and j not in drop and li == lj and wi <= wj and (wi < wj or i > j): drop.add(i); break
    if not drop: return conf
    k = -1
    def keep(m):
        nonlocal k; k += 1
        return "" if k in drop else m.group(0)
    out = re.sub(r"⟦[^⟦⟧]*⟧", keep, conf)
    while True:
        was = out
        out = re.sub(r";\s*;", ";", out); out = re.sub(r";\s*\)", ")", out); out = re.sub(r"\(\s*;\s*", "(", out)
        if out == was: break
    return out

STOPW = set("la de en kaj al li lia sia ke por kun estis estas el pri ne sed ĉe kiu kiuj tiu oni ĝi ili mi da per sur kiel ankaŭ post antaŭ jam nur".split())
def words(s): return {w for w in re.findall(r"\w+", s.lower()) if w not in STOPW and len(w) > 2}
_ALIASES = None
def fold(s):
    """A name for matching: the harvest's alias table applied (WALRISAUN → WALTISBÜHL), diacritics folded."""
    global _ALIASES
    if _ALIASES is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hf_aliases", os.path.join(ROOT, "tools", "harvest-facts.py"))
        src = open(spec.origin, encoding="utf-8").read()
        m = re.search(r"^ALIASES = \{.*?^\}", src, re.M | re.S)
        _ALIASES = {}
        if m:
            ns = {}; exec(m.group(0), ns); _ALIASES = {k.upper(): v for k, v in ns["ALIASES"].items()}
    s = _ALIASES.get(s.strip().upper(), s.strip())
    return "".join(c for c in unicodedata.normalize("NFD", s.upper()) if unicodedata.category(c) != "Mn")

def who(line):
    """A line's person for the register: the NAME (alias applied, folded) and its qualifier («ZAMENHOF|Ida»)."""
    m = re.match(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))?", line)
    if not m: return None
    return fold(m.group(1)) + (f"|{fold(m.group(2))}" if m.group(2) else "")

def line_key(l):
    """THE LINE'S OWN KEY (2026-10-22; the editor): its head (name and qualifier, not the date), kind, fact, anchor and locator (items as
    their keys), whitespace folded, hashed; the date, the themes and the voice field left out, so a convention that
    changes them (☞, ⟦anoncita⟧, a label) leaves the key as it was. A reassembly from the same returns gives every line its
    old key back, and a note registered with it returns to that line and no other; only a line a redowse rewrote has a
    new key, and its notes go by the word rule as before."""
    import hashlib
    ps = l.split(" · ")
    if len(ps) < 6: return ""
    head = re.sub(r"\*\*[^*]*\*\*", "", ps[0])
    parts = [head, " · ".join(ps[1:-5]), ps[-5], ps[-4], to_keys(ps[-3])[0]]
    return hashlib.sha1(" | ".join(" ".join(p.split()) for p in parts).encode("utf-8")).hexdigest()[:16]

def keys_of(lines):
    """Each line's key, made unique where two lines share one (Neves's two Richardson lines, «la 1920aj jaroj» and «la
    1930aj jaroj», the same in all but the date): those take their date as well, without the plan's «☞» (2026-10-22)."""
    base = [line_key(l) for l in lines]
    n = collections.Counter(base)
    def date_of(l):
        m = re.search(r"\*\*([^*]*)\*\*", l.split(" · ")[0]); return (m.group(1) if m else "").replace("☞", "").strip()
    return [k + "|" + date_of(l) if k and n[k] > 1 else k for k, l in zip(base, lines)]

def intervention_rows(text, origin):
    """The ⟦…⟧ additions of a facts file's lines: [(NAME folded, page, anchor, fact words, addition, origin, line key)]."""
    out = []
    fl = [l for l in text.split("\n") if l.startswith("- $$$")]
    kk = dict(zip(range(len(fl)), keys_of(fl)))
    j = -1
    for l in text.split("\n"):
        if l.startswith("- $$$"): j += 1
        if not l.startswith("- $$$"): continue
        ps = l.split(" · ")
        if len(ps) < 6: continue
        nm = who(l)
        conf, anchor, fact = bracket(ps[-1]), ps[-4], ps[-5]
        for add in re.findall(r"⟦[^⟧]*⟧", conf):
            if TOOL_NOTE.match(add): continue    # the tool writes these again at each reassembly, from the issue's date
            if EMPTY_NOTE.fullmatch(add): continue   # a reader's empty placeholder, not a note
            out.append((nm, page(ps[-3]), anchor, " ".join(sorted(words(fact)))[:300], add, origin, kk[j]))
    return out

# THE TOOL'S OWN NOTES, never registered as ours (2026-10-22: a mined ⟦anoncita 1909⟧ stood beside the new
# ⟦anoncita inter 1909-05 kaj 1909-07, laŭ la enhavo⟧ once Ruslanda's issues were dated by the register)
# AN EMPTY NOTE, «⟦⟧» or «⟦—⟧» (2026-10-22, found by tools/dowse-conventions-audit.py: 3,003 in Amerika Esperantisto's
# file, the older brief's readers' placeholder in the themes field, carried into the voice): never a note, dropped
EMPTY_NOTE = re.compile(r"⟦\s*[—–-]?\s*⟧")
# Only the tool's exact forms: an older note of ours, «⟦anoncita en la numero de feb. 1911⟧», stays ours
_PMAP = None
CITED_PAGE = re.compile(r"\b(?:p\.|pp\.|paĝo|paĝoj|paĝon|paĝe)\s*(\d{1,4})\b")
INDEX_CUE = re.compile(r"(?i)indeks|tabel|enhav|la listo de|laŭ la tabelo")

def index_issue(loc, fact, anchor, dv, kind=""):
    """For the index rule above: (the new date, the note's words) or None. The page map is ocr/runs/OCR-PAGE-MAP.tsv
    (Miles's: item, PDF page, printed page), read once."""
    global _PMAP
    # an index entry records a work (the third run, 2026-10-27 08:5x: errata cite an earlier page too, «sur p. 75 … la
    # nomo Holme estas eraro», and their date is the erratum's)
    # («aperoj», a name's appearance in a list, is not a work: the Oficiala Gazeto's errata of oge-4 PDF 331)
    if not re.match(r"\{\s*(?:verko|traduko|artikolo|eldono)\b", kind or ""): return None
    ms = _HF.locators(loc)
    if not ms or not ms[0].group("pdf"): return None
    key = ms[0].group("item").strip(); pdf = int(ms[0].group("pdf"))
    own = re.search(r"\(prese (\d+)\)", loc)
    # an explicit «p. N» or «paĝo N» only: an anchor's last number was read as a page in the second run (2026-10-27
    # 08:4x), a house number («strada Decebal 5») or a price, so the Oficiala Gazeto's addresses took its June issues
    m = CITED_PAGE.search(fact) or CITED_PAGE.search(anchor or "")
    if not m: return None
    cue = (not own) or INDEX_CUE.search(fact)
    p = int(m.group(1))
    if not cue or (own and p >= int(own.group(1))): return None
    if _PMAP is None:
        _PMAP = {}
        with open(os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
                n = re.match(r"\s*(\d+)\s*$", r.get("printed") or "")
                if n and r.get("pdf_page", "").isdigit(): _PMAP.setdefault((r["item"], int(n.group(1))), int(r["pdf_page"]))
    # only a date to the month or day is an index's own (a year index's year is right: Lingvo Internacia's annual
    # index, 1906-0-1, lists that year's articles; the first run of 2026-10-27 weakened them to «dum aŭ antaŭ 1906»)
    if not re.match(r"1[6-9]\d\d-\d\d", dv): return None
    item = _HF.key_names().get(key, key)
    pdf2 = _PMAP.get((item, p))
    # only where the page map finds the cited page earlier in the same item, in an earlier issue: no fallback (the
    # first run's «dum aŭ antaŭ» caught an issue's own front contents, which cite its later pages: L'Espérantiste
    # 1898.4 PDF 1, Oficiala Gazeto oge-3 PDF 19, their issue's date right)
    if not pdf2 or pdf2 >= pdf: return None
    iss = _HF.issue_date(f"- $$$ X $$$ **x** · {{x}} · {key}, PDF {pdf2}")
    if not iss or not iss[1]: return None
    ann = _HF.issue_field(iss)
    return (ann, "laŭ la indekso") if ann and ann < dv[:len(ann)] else None

TOOL_NOTE = re.compile(r"⟦(?:anoncita (?:1[6-9]\d\d|inter |dum )|la dato de la numero(?:, laŭ la enhavo)?(?:, konkludita)?⟧|interpretdato\b"
                       r"|la jaro laŭ la numero⟧)")

_FID, _TXT, _NPAGE, _SID = None, {}, {}, {}
def _fid():
    """tools/fact-ids.py as a module: its normalising, sentence start and six words."""
    global _FID
    if _FID is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fact_ids", os.path.join(ROOT, "tools", "fact-ids.py"))
        _FID = importlib.util.module_from_spec(spec); spec.loader.exec_module(_FID)
    return _FID

def text_pages(path):
    """A text's pages as fact-ids reads them (running heads out, line-end hyphens joined), «=== ¶ N ===» too."""
    if path not in _TXT:
        F = _fid(); t = open(path, encoding="utf-8", errors="replace").read()
        parts = re.split(r"^=== (?:page|¶) (\d+) ===\s*$", t, flags=re.M); pages = {}
        for i in range(1, len(parts), 2):
            body = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", "\n".join(l for l in parts[i + 1].split("\n") if not F.HEADER.match(l)))
            pages[int(parts[i])] = body.split()
        _TXT[path] = pages
    return _TXT[path]

def sentence_id(path, pg, anchor):
    """THE FACT'S SENTENCE (T1, 2026-10-18; tools/fact-ids.py's id without the hash): the anchor found on its page or a
    neighbour (6, 5, 4, 3 words, from its first to its fourth word), and the sentence that holds it, as (its first page,
    its first six words normalised). None where the anchor is not found."""
    k = (path, pg, anchor)
    if k in _SID: return _SID[k]
    F, out, pages = _fid(), None, text_pages(path)
    def flat(p):
        if (path, p) not in _NPAGE:
            nw = [(w, i) for i, t in enumerate(pages.get(p) or []) for w in F.norm(t).split()]
            _NPAGE[(path, p)] = (nw, [w for w, _ in nw])
        return _NPAGE[(path, p)]
    for seg in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", anchor)):
        q = F.norm(seg).split()
        if len(q) < 3: continue
        for start in (0, 1, 2, 3):
            for n in (6, 5, 4, 3):
                sub = q[start:start + n]
                if len(sub) < n: continue
                for p in (pg, pg - 1, pg + 1):
                    nw, fl = flat(p)
                    j = next((j for j in range(len(fl) - n + 1) if fl[j:j + n] == sub), None)
                    if j is not None:
                        sp, sj = F.sentence_start(pages, p, nw[j][1])
                        out = (sp, F.six_words(pages, sp, sj)); break
                if out: break
            if out: break
        if out: break
    _SID[k] = out
    return out

_OFF = {}
def anchor_span(path, pg, anchor):
    """THE ANCHOR'S PLACE IN THE TEXT (T1, 2026-10-18; the editor): the anchor found on its page or a neighbour, as in sentence_id, -> (first word, word after
    the last), counted in words from the start of the text; None where it is not found."""
    F, pages = _fid(), text_pages(path)
    if path not in _OFF:
        off, n = {}, 0
        for p in sorted(pages): off[p] = n; n += len(pages[p])
        _OFF[path] = off
    def flat(p):
        if (path, p) not in _NPAGE:
            nw = [(w, i) for i, t in enumerate(pages.get(p) or []) for w in F.norm(t).split()]
            _NPAGE[(path, p)] = (nw, [w for w, _ in nw])
        return _NPAGE[(path, p)]
    for seg in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", anchor)):
        q = F.norm(seg).split()
        if len(q) < 3: continue
        for start in (0, 1, 2, 3):
            for n in (6, 5, 4, 3):
                sub = q[start:start + n]
                if len(sub) < n: continue
                for p in (pg, pg - 1, pg + 1):
                    nw, fl = flat(p)
                    j = next((j for j in range(len(fl) - n + 1) if fl[j:j + n] == sub), None)
                    if j is not None:
                        s = _OFF[path].get(p, 0) + nw[j][1] - start
                        return (s, s + len(q))
    return None

IV_ADJ, IV_WINDOW = 3, 60   # words: anchors this close are one place; the window of competing facts (≈ 5 lines)
IV_IDS, IV_PLACE, IV_COMPARE, IV_CMP = False, False, 0, []
IV_NOTE, IV_MOOT = False, [0]
IV_KEYED = [0, 0]   # notes placed by their line's key; older rows of the same note not placed again (2026-10-22)

def _years(s):
    """The years a date field or a note names, as (low, high) ranges."""
    ys = [int(y) for y in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", s)]
    if re.search(r"\b(?:de|inter)\s+1[6-9]\d\d\b.*\b(?:ĝis|kaj)\s+1[6-9]\d\d\b", s) and len(ys) >= 2: return [(ys[0], ys[1])]
    return [(y, y) for y in ys]

def note_choice(add, cands):
    """THE NOTE'S OWN WORDS (2026-10-18, Fable's review of T1, dowse/fable-review-2026-10-18/RETURN.md; the editor; a trial, --iv-note): among the person's lines on the page, by the note's kind first: a ⟦kalkulite⟧ goes to a
    dated line whose date the note does not already give (the computed result, not its input: Chavet's «20-jara en 1900»
    to the birth line, not the 1900 line); a dated ⟦pruvo⟧ («la jaro laŭ …», a year) to a dated line, one holding the
    note's year where there is one; an ⟦identigo⟧ naming someone in capitals to the line whose kind field names them.
    Then the note's words against each line's date, kind and fact; the old anchor and fact words (today's score) break a
    tie. -> (line index, share) or None (no word of the note on any line: today's rule stands)."""
    body = add.strip("⟦⟧"); lab = body.split(":", 1)[0].strip()
    # a scope note goes to SCOPE-NOTES.tsv by its person, whichever line carries it: today's rule stands
    if lab == "pruvo" and (lambda c: c[1] and "⟦" not in c[0])(scope_off(f"📣 ({add})", "")): return None
    def date_of(ps): m = re.search(r"\*\*([^*]+)\*\*", ps[0]); return m.group(1) if m else ""
    def dated(ps): d = date_of(ps); return bool(d) and "sen dato" not in d and "ĝenerala" not in d
    note_years = _years(body)
    pool = cands
    if lab == "kalkulite":
        d = [c for c in cands if dated(c[3])]
        res = [c for c in d if not any(a <= y <= b for (y, _y) in note_years for (a, b) in _years(date_of(c[3])))]
        pool = res or d or cands
    elif lab == "pruvo" and (note_years or re.search(r"\b(?:jaro|jaroj|tago|dato|datoj|monato)\b[^;]*\blaŭ\b", body)):
        d = [c for c in cands if dated(c[3])]
        if note_years:
            hold = [c for c in d if any(a <= y <= b for (y, _y) in note_years for (a, b) in _years(date_of(c[3])))]
            d = hold or d
        pool = d or cands
    elif lab == "identigo":
        names = set(re.findall(r"\b[A-ZĈĜĤĴŜŬ][A-ZĈĜĤĴŜŬ'-]{2,}\b", body))
        k = [c for c in cands if names and any(n in c[3][1] for n in names)]
        pool = k or cands
    nw = words(body)
    scored = [(len(nw & words(" ".join(c[3][:3]))), c[1], c[0], c[2]) for c in pool]
    top = max(scored)
    if top[0] == 0 and pool is cands: return None
    return top[2], top[3]
def apply_interventions(rows, regs, fixed=frozenset(), texts=()):
    """Re-attach each registered addition to the line it belongs to after a redowse: the same person (folded) and page,
    the most shared words of anchor and fact (at least three). -> (rows, attached, unmatched).
    T1 (2026-10-18, measured with --iv-report): no rule on shared words parts the right attachments from the wrong. A
    share threshold (half the anchor) refused 146 of Korĵenkov's; a right one shares none of its anchor (Jossinet's «la
    8-an de Januaro 1935, sama alineo», 0.00/0.50). Keeping notes off lines a fix rewrote sent them to the page's next line
    (the ¶ 12 notes onto the «Prof.» line, the 1932-10 note onto L436); retiring them lost 43 of Jossinet's, right ones
    among them. TRIED AND WITHDRAWN, 2026-10-18, --iv-ids (off by default; the editor, to the queue's): the note to the person's line whose anchor stands in the same sentence of the
    text as the registered anchor (fact-ids' sentence), the shared words choosing only among that sentence's lines; a note
    whose sentence no line has, every anchor found, finds no line; an anchor not found in the text, the word rule.
    Measured with --iv-compare against the word rule: the same line for 157 of Jossinet's 161 notes, 1,487 of Korĵenkov's
    1,633, 1,109 of Waringhien's 1,167. Where it differs it is right about as often as wrong (Chavet's «20-jara en 1900»
    to the birth line and Glatard's note right; De Beaufront's profession and Fruictier's «samtempe» wrong), and it loses
    2 + 41 + 28 notes the word rule had right (Zamenhof «ne venis», De Wahl's dates, Michaux's lost note mark): a
    redowse's reader anchors the same fact in another sentence, so an id from the anchor's sentence is no more stable
    across a redowse than the anchor's words. What would be: an id written on the line at its first dowse and carried
    through every redowse, which no reader can be asked to copy and no tool yet assigns; not designed. `fixed` is passed
    and unused."""
    attached, unmatched = [], []
    lines = [list(r) for r in rows]
    # BY THE LINE'S KEY FIRST (2026-10-22, line_key): a note registered with its line's key goes back to the line with
    # that key; the same note (person, page, words) from an older row is then not placed a second time elsewhere by the
    # word rule, which takes only what no key places
    by_key = {}
    for i, k in enumerate(keys_of([r[2] for r in lines])): by_key.setdefault(k, []).append(i)
    placed, rest = set(), []
    for reg in regs:
        nm, pg, anchor, fw, add, origin, lk = (tuple(reg) + ("",))[:7]
        hit = by_key.get(lk) if lk else None
        if hit and len(hit) == 1 and not add.startswith("⟦interpretdato"):
            i = hit[0]; placed.add((pg, add))   # by page and note: an older row may name another person (Neves, PDF 37)
            if add[1:-1].strip() in lines[i][2]: continue
            conf = lines[i][2].rsplit(" · ", 1)
            conf[1] = re.sub(r"\)\s*$", f"; {add})", conf[1]) if conf[1].rstrip().endswith(")") else f"{conf[1]} ({add})"
            lines[i][2] = " · ".join(conf); attached.append((lines[i][2][:160], add, anchor, origin, (1.0, 1.0), fw))
            IV_KEYED[0] += 1
        else: rest.append((nm, pg, anchor, fw, add, origin))
    regs = [r for r in rest if (r[1], r[4]) not in placed]
    IV_KEYED[1] += len(rest) - len(regs)
    paths = {}
    if texts:
        to_keys("")   # loads the item table
        inv = {}
        for t in texts:
            it = re.sub(r"\.numbered$", "", os.path.basename(t)[:-4]); inv[(_n2k or {}).get(it, it)] = os.path.join(G, t)
        paths = inv
    single = os.path.join(G, texts[0]) if len(texts) == 1 else None   # one text: every line's
    for nm, pg, anchor, fw, add, origin in regs:
        # MOOT NOTES (2026-10-18, Fable's review of T1, on the editor's ruling): an ⟦interpretdato⟧, which the assembler
        # writes itself, is not re-attached. Not the scope notes, which Fable also called moot: scope_off takes them off
        # the line but writes them to SCOPE-NOTES.tsv for the profile's banner; skipping them lost 61 of Korĵenkov's there
        if add.startswith("⟦interpretdato"):
            IV_MOOT[0] += 1; continue
        nmf = "|".join(fold(p) for p in nm.split("|"))   # a row written before the alias existed (WALRISAUN)
        best, score, share = None, 0, (0, 0)
        cands = []
        for i, r in enumerate(lines):
            if r[0] != pg or who(r[2]) != nmf: continue
            ps = r[2].split(" · ")
            aw, fws = words(anchor), set(fw.split())
            cand = (len(aw & words(ps[-4])) / len(aw) if aw else 0, len(fws & words(ps[-5])) / len(fws) if fws else 0)
            s = len(words(anchor) & words(ps[-4])) + len(set(fw.split()) & words(ps[-5]))
            cands.append((i, s, cand, ps))
            if s > score: best, score, share = i, s, cand
        word_best = best if best is not None and score >= 3 else None
        id_best, how, share_id = word_best, "words", share
        if IV_IDS and paths and cands:
            same, known = [], True
            for i, s, cand, ps in cands:
                path = paths.get(ps[-3].split(",")[0].strip()) or single
                sr = sentence_id(path, pg, anchor) if path else None
                sc = sentence_id(path, pg, ps[-4]) if path else None
                if sr is None or sc is None: known = False
                elif sr == sc: same.append((s, i, cand))
            if same: s, id_best, share_id = max(same); how = "sentence"
            elif known: id_best, how = None, "no line has its sentence"
        is_corr = add.startswith("⟦korektita")
        if (IV_PLACE or is_corr) and cands and (paths or single):
            # T1 by the anchor's place: the old anchor's place gives the window of competing facts; a line whose anchor
            # overlaps or adjoins it takes the note, the words breaking a tie; else the window's best by words (three at
            # least); else the word rule as before, so no note it places is lost. THE CORRECTION RULE IS THE DEFAULT
            # (2026-10-18, Fable's review: 3 right, 13 either, none wrong on Korĵenkov; the editor); the window
            # stays a trial (--iv-place: 8 right against 7 wrong, a coin toss)
            near, close = [], []
            for i, s, cand, ps in cands:
                path = paths.get(ps[-3].split(",")[0].strip()) or single
                r = anchor_span(path, pg, anchor) if path else None
                c = anchor_span(path, pg, ps[-4]) if path and r else None
                if not (r and c): continue
                gap = max(c[0] - r[1], r[0] - c[1], 0)
                if gap <= IV_ADJ: close.append((s, i, cand))
                elif gap <= IV_WINDOW: near.append((s, i, cand))
            # by the note's kind (measured 2026-10-18 02:0x on the three sources): a correction of the quoted text
            # («⟦korektita⟧») belongs to the line whose anchor holds that text, so the overlap decides (Langlet's
            # «Valdemar», Couturat's «Léopold», Cart's note mark, which the words had misplaced); a note about the fact
            # (a proof, a date) follows the fact's words within the window, since an old anchor can span two facts
            # (Fruictier's «samtempe», De Beaufront's profession, which the overlap had misplaced)
            win = close + near
            if is_corr and close: s, id_best, share_id = max(close); how = "a correction: the anchors overlap"
            elif IV_PLACE and win and max(win)[0] >= 3: s, id_best, share_id = max(win); how = "the window, by words"
        # the computed dates by default (2026-10-18, measured on Korĵenkov: 5 moves, 4 right, Chavet's «20-jara en 1900»
        # ×3 and Berthelot's «1905 − 23» to their birth lines, 1 either); the rest of the note rule a trial (--iv-note:
        # on Fable's own cases 6 right against 5 wrong, Fruictier ×3 and Mordka among the wrong)
        if (IV_NOTE or add.startswith("⟦kalkulite")) and cands and how != "a correction: the anchors overlap":
            pick = note_choice(add, cands)
            if pick is not None: id_best, share_id, how = pick[0], pick[1], "the note's own words"
        snap = lambda i: None if i is None else re.sub(r"^- \$\$\$ ", "", lines[i][2])[:200]
        IV_CMP.append((snap(word_best), snap(id_best), how, nm, pg, add, anchor, origin))
        best = id_best
        if how != "words" and id_best is not None: share = share_id
        if best is None: unmatched.append((nm, pg, add, origin)); continue
        if add[1:-1].strip() in lines[best][2]: continue
        conf = lines[best][2].rsplit(" · ", 1)
        conf[1] = re.sub(r"\)\s*$", f"; {add})", conf[1]) if conf[1].rstrip().endswith(")") else f"{conf[1]} ({add})"
        # the shares of the registered anchor's and fact's words the chosen line holds, for --iv-report (T1, 2026-10-18:
        # measured before any threshold is set)
        lines[best][2] = " · ".join(conf); attached.append((lines[best][2][:160], add, anchor, origin, share, fw))
    return [tuple(r) for r in lines], attached, unmatched

def page(line):
    m = re.search(r"(?:PDF|¶) (\d+)", line)
    return int(m.group(1)) if m else 0

_n2k = None
def to_keys(loc):
    """A locator field with each item's file name replaced by its key (OCR-ITEM-TABLE.tsv, «key»), several locators
    split at «;» as the harvest splits them. -> (the field, how many items were rewritten)."""
    global _n2k
    if _n2k is None:
        _n2k = {}
        with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
                if (r.get("key") or "").strip() and r["key"].strip() != r["item"]: _n2k[r["item"]] = r["key"].strip()
    parts, n = re.split(r"(\s*;\s*)(?=[^,;·]+, (?:PDF \d|¶ \d))", loc), 0
    for i in range(0, len(parts), 2):
        it = parts[i].split(",")[0].strip()
        if it in _n2k: parts[i] = _n2k[it] + parts[i][len(parts[i].split(",")[0]):]; n += 1
    return "".join(parts), n

def iso_date(date):
    dm = re.fullmatch(r"\*\*(?:(\d{1,2}) )?(jan|feb|mar|apr|maj|jun|jul|aŭg|sep|okt|nov|dec) (1[89]\d\d)\*\*", date)
    if not dm: return date
    return f"**{dm.group(3)}-{MON[dm.group(2)]}" + (f"-{int(dm.group(1)):02d}" if dm.group(1) else "") + "**"

def join_broken(lines, ret, joined):
    """A fact line a reader broke (the editor, 2026-10-15): a line straight after a fact line, with no blank between, that is indented
    or does not open a new item (a bullet, heading, table row or note), is joined to it, the break written as the two
    characters \\n. Before this the second half was dropped unseen. Each join is recorded in «joined»."""
    out, prev_fact = [], False
    for l in lines:
        s = l.rstrip("\n")
        cont = prev_fact and s.strip() and (s[:1].isspace() or not re.match(r"[-*#|`>]|\d+[.)]\s", s))
        if cont:
            out[-1] += "\\n" + s.strip(); joined.append((ret, out[-1][:90], s.strip()[:90])); continue
        out.append(s); prev_fact = s.startswith("- $$$")
    return out

def assemble(src, S=None):
    """-> (text, rows, dropped, bad, notes). S: the settings, read from the source's facts-config.json unless given (a
    caller testing fixes before they are written, tools/dowse-apply-fixes.py, 2026-10-12). notes: «spent» (fixes
    already in effect), «applied» [(line head, [(key, old), …])] and «dropped» [(raw line, why)], so that a fix that
    matches no line can be told apart from one whose line another fix changed or the assembly dropped."""
    D = os.path.join(G, "dowse", src)
    if S is None: S = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8"))
    notes = {"spent": [], "applied": [], "dropped": [], "dates": []}
    dp = os.path.join(D, "DECISIONS.tsv")     # locator · phrase · kind (date, qualifier, name) · value · ruling · note
    DECISIONS = [tuple(r[:4]) for r in (x.rstrip("\n").split("\t") for x in open(dp, encoding="utf-8")
                 if not x.startswith("#") and x.strip()) if r[0] != "locator" and len(r) >= 4] if os.path.exists(dp) else []
    # A RULING'S LOCATOR BY NAME OR BY KEY (2026-10-21): the lines carry the item's key since harvest-facts.py's
    # expand_lean writes it (the editor), while rows written before, or by --dedupe-rows from the
    # parsed lines, name the file («KK_1913_kongresagazeto_n01-06, PDF 15 …»: the gazette's one duplicate row matched no
    # line); each row is matched in both forms
    form_repair("- $$$ X $$$")   # loads the harvest module
    def _other_form(dl):
        for n, k in _HF.unsafe_names().items():
            if dl.startswith(n + ","): return k + dl[len(n):]
        it = dl.split(",")[0].strip(); rest = dl[len(dl.split(",")[0]):]
        k = _HF.item_key(it)
        if k != it: return k + rest
        n = _HF.key_names().get(it)
        return (n + rest) if n else dl
    DALT = [_other_form(d[0]) for d in DECISIONS]
    # A RULING ACROSS A RECUPEL (2026-10-25, OGE: Miles's vision pages rewrote 13 pages of five volumes after the
    # assembly, the text's line numbers after them moved, and 355 date rows written against the old «l. N» found no line):
    # where the whole locator no longer matches, the item, PDF page and printed page without the line, with the phrase
    DPAGE = [tuple(re.sub(r", l\. ?\d+\s*$", "", x) for x in (d[0], DALT[k])) for k, d in enumerate(DECISIONS)]
    names, drop = S.get("names", {}), set(S.get("drop", []))
    if S.get("out_of_scope"):
        sys.exit("«out_of_scope» is retired: scope is decided by profiles/SCOPE-REGISTER.tsv alone (the editor, 2026-10-14 11:3x)")
    REGOUT = register_out(); UNCONF = register_out_unconfirmed()
    if BARE_COVER:   # proposed 2026-10-15, on a dry run first
        REGOUT |= {(k, BARE) for k in bare_cover(REGOUT)}
    DROPK = {fold(x) for x in drop}
    OUT = lambda n, q: fold(n) in DROPK or is_out(n, q, REGOUT)   # who is not in scope, for «kun:» (step 3)
    rename = {(a, b): (c, d) for a, b, c, d in S.get("rename", [])}
    quals = {(a, b): c for a, b, c in S.get("qualifiers", [])}
    rows, dropped, bad, used = [], collections.Counter(), [], collections.Counter()
    # «extra_lines»: whole lines written after the readers (e.g. refuted claims, WHO IS REFUTED IS TRACKED, 2026-10-11),
    # processed exactly like the returns' lines (names, locators, themes), after them on the same page
    notes["joined"] = []
    sources = [(ret, join_broken(open(os.path.join(D, ret), encoding="utf-8").read().splitlines(), ret, notes["joined"]))
               for ret in S["returns"]]
    if S.get("extra_lines"): sources.append(("extra_lines", S["extra_lines"]))
    if S.get("restore"): sources.append(("restore", S["restore"]))   # restored lines now go through the same steps
    # THE PAGES A RECUPEL CHANGED, READ AGAIN (2026-10-25, R5 of ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md; the
    # editor): «redowsed_pages» [{notice, item, pages,
    # tag}]. A line of an earlier return on one of those (item, PDF N) is dropped, the new tag's reading standing in its
    # place; a line of the new tag's returns is kept only on its own pages (its reader was given the next page too, which
    # the earlier reading still holds). Hand lines («extra_lines», «restore») are kept either way. The lines of the
    # unchanged pages after them need no re-pin (R3): cited_line() places every «l. K» in the current text at each assembly
    RP = {}
    for e in S.get("redowsed_pages", []):
        for p in e["pages"]: RP.setdefault((_HF.item_key(e["item"]), int(p)), set()).add(e["tag"])
    RTAGS = {t for ts in RP.values() for t in ts}
    def rp_pages(l):
        return {(_HF.item_key(m.group(1).strip()), int(m.group(2))) for m in re.finditer(r"(?:^|; | · )([^·;]+?), PDF (\d+)\b", l)}
    notes["redowsed"] = collections.Counter()
    for n, (ret, lines) in enumerate(sources):
        rtag = next((t for t in RTAGS if ret.startswith(f"facts-return-{t}-")), None)
        for l in lines:
            if not l.startswith("- $$$"): continue
            l = expand_lean(D, ret, l.rstrip("\n"))   # the lean brief's «(prese M) l. K» → the full locator (2026-10-18)
            l = form_repair(l)                 # the cut brief's two form faults (2026-10-17)
            l = cited_line(D, ret, l)          # «l. K» of the reader's pages file → the text's own line (2026-10-17)
            if RP and ret not in ("extra_lines", "restore"):
                pg = rp_pages(l)
                if rtag and not any(rtag in RP.get(x, ()) for x in pg):
                    notes["redowsed"]["new reading, off its pages"] += 1; continue
                if not rtag and any(x in RP for x in pg):
                    notes["redowsed"]["earlier reading, superseded"] += 1; continue
                if rtag: notes["redowsed"]["new reading, kept"] += 1
            for rl in S.get("replace_lines", []):            # a reader's line corrected whole (the reason in the log),
                key, new = rl[0], rl[1]                      # for the return it names (2026-10-15, the Fable review 1:
                if key in l and (len(rl) < 3 or rl[2] == ret):   # an old entry would replace a new reader's line
                    l = new; used[("replace", key)] += 1     # that holds its key, unseen)
            m = LINE.match(l)
            if not m: bad.append(l); continue
            name, q, rest = m.group(1), m.group(2) or "", m.group(3)
            name, q = rename.get((name, q), (name, q))
            name = names.get(name, name)
            if name in drop: dropped[name] += 1; notes["dropped"].append((l, f"its name {name} is dropped")); continue
            was = name
            head_out = is_out(name, q, REGOUT)   # the register's «out» heads (the editor, 11:1x, on
            # Kalocsay: a fact drops out once each of its heads is out)
            name, q, rest, kw = kun_rotate(name, q, rest, OUT, names, head_out)
            if kw == "all out" or (head_out and kw is None):
                dropped[was] += 1; notes["dropped"].append((l, f"{was} is out of scope"))
                if BARE_COVER and not q and (fold(was), None) not in REGOUT and (fold(was), BARE) in REGOUT:
                    notes.setdefault("bare", collections.Counter())[was] += 1
                for k, why in UNCONF.items():   # out by a row the editor has not confirmed: listed (the editor)
                    if is_out(was, q, {k}): notes.setdefault("unconfirmed", collections.Counter())[(was, why)] += 1; break
                continue
            if kw: notes.setdefault("kun", []).append((was, name, kw, rest))
            # «drop_keys»: a single line left out by a piece of it (e.g. a difference between copies that is apparatus only,
            # the editor 2026-10-11); the returns keep it
            dk = next((k for k in S.get("drop_keys", []) if k in l), None)
            if dk: used[("drop", dk)] += 1; dropped["by key"] += 1; notes["dropped"].append((l, f"drop key «{dk}»")); continue
            q = quals.get((name, q), q)
            parts = rest.split(" · ")
            # FACTS FORMAT 4 (the editor 2026-10-13): the event kind, `{kind: object; +second}`, right after the date.
            # Taken off here and put back in the output line, so that every fix and key sees the line as before.
            kind = parts.pop(1) if len(parts) > 1 and re.fullmatch(r"\{[^{}]*\}", parts[1].strip()) else ""
            if len(parts) < 5: bad.append(l); continue
            # a format-4 line always has the anchor in its own field, even when its fact quotes a title of six words
            # («Societo por la Propagando de Esperanto», the Jossinet pilot, 2026-10-13)
            if len(parts) >= 6 and (kind or not split_anchor(" · ".join(parts[1:-4]))[1]):
                # a line written in format 3 (the anchor bare, fourth from the right): back to the format-2 shape
                anc = parts[-4].strip()       # an anchor field a reader wrote in «…» (the Fable review's finding 10,
                if anc.startswith("«") and anc.endswith("»"): anc = anc[1:-1]   # approved 2026-10-12): bare, as format 3 says
                anc = anc.replace("«", "‹").replace("»", "›")   # the source's own guillemets inside an anchor would break
                # the quotation parsing (Waringhien, 2026-10-14: «…de la «Deklaracio»); the page check ignores punctuation
                parts = [parts[0], f"{' · '.join(parts[1:-4])}: «{anc}»"] + parts[-3:]
            date, fact, loc, th, conf = parts[0], " · ".join(parts[1:-3]), parts[-3], parts[-2], parts[-1]
            fact = fact.replace(" · «", ": «")      # a reader who set the quotation off by « · » (the field separator)
            # the mechanical changes first, so later fixes see the text as the readers of the combined pass saw it
            fact, conf = mechanical(fact, conf)
            # «fact_fixes» the same mechanism for the fact's wording (EVERY FACTS LINE STANDS ALONE, 2026-10-11)
            applied = []
            for fx in S.get("quote_fixes", []) + S.get("fact_fixes", []):
                # [old, new], or [key, old, new]: only on the line containing the key (anywhere in the reader's line, e.g.
                # its quotation), for facts that are word for word alike (Jossinet's «same» lines); or in the fact as the
                # earlier fixes left it, since a later reader keys on the facts file as it stands (2026-10-12)
                key, a, b = fx if len(fx) == 3 else ("", fx[0], fx[1])
                # a «» inside a quotation is written ‹›, so a fix written from the reader's line («r. Jamin, np» Bein») is
                # looked for with ‹› read as «» (2026-10-17u: nine fixes of Ruslanda Esperantisto matched no line); the
                # marks are one character each, so the place found is the place replaced
                nq = lambda s: s.replace("‹", "«").replace("›", "»")
                a0 = a
                # a fix that lengthens a quoted anchor, «old» → new, written without the new text's guillemets (the
                # pilot's anchor fixes, 2026-10-17): the new text is the quotation, so it keeps them, inner marks as ‹›;
                # without them the line lost its anchor and the check held it back (Ayza, De Amicis, Bein … 2026-10-17u)
                if a.startswith("«") and a.endswith("»") and b and not b.startswith("«"):
                    b = "«" + b.strip().replace("«", "‹").replace("»", "›") + "»"
                if a not in fact and nq(a) in nq(fact):
                    i = nq(fact).index(nq(a)); a = fact[i:i + len(a)]
                if (key in l or key in fact) and a not in fact and key and b and b in fact:
                    # SPENT, not missed: the new text is there and the old is not, so another fix made this change first
                    # (the editor 2026-10-12,: three of 21 misses were this). Keyed fixes only.
                    used[(key, a0)] += 1; notes["spent"].append(f"SPENT (already in the line): {key} | {a}")
                    continue
                if (key in l or key in fact) and a in fact:
                    used[(key, a0)] += 1
                    applied.append((key, a0))
                    if a in b and b in fact: continue   # an addition the line already has (Korĵenkov 409, 2026-10-12)
                    fact = fact.replace(a, b)
                    fact, conf = mechanical(fact, conf)   # an earlier fix may bring back what the mechanical step tidies
            for a, b in S.get("locator_fixes", []): loc = re.sub(a, b, loc)   # e.g. a reader's short item names
            loc = re.sub(r"PDF (\d+)–\d+ \(prese (\d+)–\d*\)", r"PDF \1 (prese \2)", loc)
            loc = re.sub(r"PDF (\d+)–\d+$", r"PDF \1", loc)
            # readers whose pages overlap (Neves 2026-10-11): a return keeps only its own pages (first locator's PDF page),
            # except lines named in «keep_lines», the facts the other reader of those pages did not give
            if ret in S.get("pages", {}):
                lo, hi = S["pages"][ret]
                if not lo <= page(loc) <= hi and not any(k in l for k in S.get("keep_lines", [])):
                    dropped[f"{ret} outside its pages"] += 1; notes["dropped"].append((l, f"outside the pages of {ret}")); continue
            if "–" not in date: date = iso_date(date)
            # the line as the facts file shows it (format 3: «fact · anchor»), so a date or label key copied from the file
            # across the two fields finds its line (2026-10-12: two Li kaj ni lines, keys «…universelle* · Couturat, …»)
            f3, a3 = split_anchor(fact)
            view3 = f"{f3} · {a3}" if a3 else f3
            # «date_fixes» [key, old, new]: a guessed date for an undated line, marked «diveno» (GUESSED DATES, 2026-10-11);
            # only on the line whose fact contains the key
            for key, a, b in S.get("date_fixes", []):           # old «*»: whatever the date was
                # compared without italics: the file shows the date with its italics stripped (below), so a fix copied
                # from the file must still find a date an earlier fix wrote with them (2026-10-12, «*Dua Libro*»)
                if (key in fact or key in l or key in view3) and (date.replace("*", "") == a.replace("*", "") or a == "*"):
                    date = b; used[("date", key)] += 1
            # DECISIONS (the editor 2026-10-12
            # approved): dowse/<source>/
            # DECISIONS.tsv, the editor's line rulings keyed on the locator and a phrase of the SOURCE's text (anchor or
            # fact), so that they find their line whoever wrote it, after a redowse too; applied after the settings
            dup_drop = None
            pagekeys = set(re.findall(r"([\w.\-]+, PDF \d+(?: \([^)]*\))?), l\. ?\d+", loc)) if DECISIONS else set()
            for k, (dloc, phrase, dkind, value) in enumerate(DECISIONS):   # «dkind», not «kind»: that is the event kind (2026-10-13)
                if (dloc in loc or DALT[k] in loc or (pagekeys and (DPAGE[k][0] in pagekeys or DPAGE[k][1] in pagekeys))) \
                        and (phrase in view3 or phrase in l):
                    used[("decision", k)] += 1
                    # «duplicate» (2026-10-17; the editor to DEDUPE-PROPOSAL-2026-10-17.md, (b) 4): the poorer line
                    # of a pair the dedupe reader ruled one fact, keyed on its locator and a phrase of its own fact; the
                    # value names the line kept. Dropped, and listed with the other drops; a row that finds no line is
                    # reported with the unused rulings
                    if dkind == "duplicate": dup_drop = value
                    elif dkind == "date": date = f"**{value}**"
                    elif dkind == "qualifier":          # value «NAME (qualifier)»: only that person's lines
                        mq = re.fullmatch(r"(.+?) \((.+)\)", value)
                        if mq and mq.group(1) == name: q = mq.group(2)
                        else: used[("decision", k)] -= 1
                    elif dkind == "name": name = value
                    elif dkind == "object-qualifier":   # value «NAME → NAME (qualifier)», in the kind field's object and
                        # «kun:» (the editor, 2026-10-15; the Fable review 11: a ruling reached only the line's head)
                        mo = re.fullmatch(r"(.+?) → (.+)", value)
                        pat = r"(?<![\w-])" + re.escape(mo.group(1)) + r"(?![\w-])(?! \()" if mo else None
                        if mo and kind and re.search(pat, kind): kind = re.sub(pat, mo.group(2), kind)
                        else: used[("decision", k)] -= 1
            if dup_drop is not None:
                dropped["duplicate (DECISIONS)"] += 1; notes["dropped"].append((l, f"DECISIONS «duplicate», the line kept: {dup_drop[:80]}")); continue
            # an exact repeat of a line already taken, the reader's own text word for word (two readers of one page, or a
            # restored line the new reading wrote again): dropped by tool, no row and no review (2026-10-17, the editor:
            # 9 such pairs had no phrase to key a row on)
            norm = " ".join(l.split())
            if norm in notes.setdefault("seen_reader_lines", set()):
                dropped["exact repeat"] += 1; notes["dropped"].append((l, "an exact repeat of a line already taken")); continue
            notes["seen_reader_lines"].add(norm)
            # «saying_dates» [[locator piece, date, note]]: a judgement or claim of the source's own author left undated
            # takes the date of its saying, the source's (the writing template § 3: «alie [sen dato], kaj la projekto
            # datas ĝin laŭ la diro»; the editor, 2026-10-15, no redowse); «interpreto» keeps the act's date
            if date.replace("*", "").strip() == "[sen dato]" and re.match(r"\{\s*(juĝo|aserto)\b", kind) and conf.lstrip().startswith("✅"):
                sd = next((x for x in S.get("saying_dates", []) if x[0] in loc), None)
                if sd:
                    date = f"**{sd[1]}**"; notes.setdefault("saying", collections.Counter())[sd[1]] += 1
                    add = f"pruvo: la jaro de la fonto, {sd[2]}"   # the editor 13:0x (was «la dato de la diro»)
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
            # … and a «juĝo» of the source's own author that the reader dated by the matter judged (2026-10-17, the
            # resmelt's faults T8: Carlevaro 1985 dated 1914, Neves 2018 dated 1913 and 1900, Forster 1985 dated 1907; the
            # writing template: «juĝo» has the date of the saying) takes the source's year; the matter's date moves to the
            # labels, «⟦pruvo: la afero juĝata: 1914⟧». Only an earlier date: a judgement may be dated after its source
            # (a reprint) by a ruling, never before it
            elif re.match(r"\{\s*juĝo\b", kind) and conf.lstrip().startswith("✅"):
                sd = next((x for x in S.get("saying_dates", []) if x[0] in loc), None)
                my = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", date)
                sy = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", sd[1]) if sd else None
                # not where the reader gave the date a reason (an earlier essay, a dated letter in the book: «⟦pruvo: la
                # dato laŭ …⟧», «pli frua»), nor a contribution with its own date
                reasoned = re.search(r"la dato (?:laŭ|de la diro)|pli frua|kontribuo|la jaro de la fonto", conf)
                # and only a year the fact itself gives to the matter («… kondukis Zamenhof en 1881 al …»): an essay's
                # own date in a collection (Waringhien's 1947-03, 1958-06 in Lingvo kaj vivo) is a saying date, kept
                in_fact = my and re.search(rf"\b{my.group(1)}\b", fact)
                if sd and my and sy and int(my.group(1)) < int(sy.group(1)) and not reasoned and in_fact:
                    add = f"⟦pruvo: la afero juĝata: {date.replace('*', '').strip()}; la jaro de la fonto, {sd[2]}⟧"
                    date = f"**{sd[1]}**"; notes.setdefault("saying_moved", collections.Counter())[sd[1]] += 1
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
            # «⟦interpretdato: …⟧» (the editor on an undated «interpreto»;
            # probe approved; the name and the sign-off 13:0x, approved): the source's own «interpreto» keeps the act's date in
            # its date field and gains the date of the interpretation, the source's, beside it in the labels' bracket
            if re.match(r"\{\s*interpreto\b", kind) and conf.lstrip().startswith("✅"):
                sd = next((x for x in S.get("saying_dates", []) if x[0] in loc), None)
                if sd:
                    add = f"⟦interpretdato: {sd[1]}⟧"
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
                    notes.setdefault("interpretdato", collections.Counter())[sd[1]] += 1
            # … and an «interpreto» the source reports from another author with a year, «derivita ↤ Drezen 1931», takes
            # that author's year (T8, 2026-10-17r and 17u: Drezen's interpretation in Korĵenkov guessed «ĉ. 1898» by its
            # page, de-beaufront-F12; Waringhien's of 1948, F78); a year in the bracket's own notes is not the author's
            elif re.match(r"\{\s*interpreto\b", kind) and "interpretdato" not in conf:
                dm = re.search(r"derivita ↤ ([^;)⟦]*?)\b(1[6-9]\d\d|20\d\d)\b", conf)
                if dm:
                    add = f"⟦interpretdato: {dm.group(2)}, laŭ {dm.group(1).strip().rstrip(',')}⟧"
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
                    notes.setdefault("interpretdato_derived", collections.Counter())[dm.group(2)] += 1
            # A PLAN (2026-10-22; the editor
            # the date suffixed;
            # as second-order, in the voice; ☞)
            #: a line whose kind marks the plan («{…, planita}», the event kinds' rule 1) is dated by the day planned,
            # suffixed «☞»; a «☞» date gains the announcement's date, the issue's (by its masthead), as ⟦anoncita …⟧
            dv = date.replace("*", "").strip()
            # … but not a plan the line says was given up, put off, cancelled, refused or failed («{fondo: Ligo, planita,
            # forlasita}», Zakrzewski 1906: the date is the abandoning's, a real one; 10 such lines on 2026-10-22)
            ended = re.search(r"\b(?:forlasit|nuligit|rezignit|malakceptit|prokrastit|ĉesigit|rifuzit|ne realigit|malsukces)\w*", kind) \
                or re.search(r"\bvan[ae]\b", fact)   # «klopodis vane fondi» (the blind sample of 2026-10-22, item 24)
            # … nor a date that bounds the act from above («antaŭ 1906-09», «ĝis …»): the act («planis», «aliĝis»,
            # «decidis») came before the thing planned, and the date is the act's (the sample, items 8, 26, 40)
            bounded = re.match(r"(?:antaŭ|ĝis|dum aŭ antaŭ)\b", dv)
            # «planitaj», «planitan» too (13 lines, «{propagando: …, planitaj}»; the contents check of 2026-10-22)
            if re.search(r"\bplanit(?:a|aj|an|ajn)\b", kind) and not ended and not bounded and not dv.startswith("[") and not dv.endswith("☞"):
                dv += "☞"; date = f"**{dv}**"; notes.setdefault("planned", collections.Counter())["☞ by the kind"] += 1
            if dv.endswith("☞") and "⟦anoncita" not in conf:
                iss = _HF.issue_date(f"- $$$ X $$$ **x** · {{x}} · {loc}", day=True)
                if iss:
                    ann = _HF.issue_field(iss)
                    # an issue with no month on its masthead, dated by its contents (ISSUE-DATES.tsv, 2026-10-22)
                    add = f"⟦anoncita {ann}, laŭ la enhavo⟧" if len(iss) > 4 and iss[4] == "enhavo" else f"⟦anoncita {ann}⟧"
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
                    notes.setdefault("planned", collections.Counter())["⟦anoncita⟧"] += 1
                    # a plan whose date is only its issue's (an «[n]» line, ⟦la dato de la numero⟧): no day planned is
                    # known, only that it comes in or after the announcement (the editor, 2026-10-22)
                    # … and a plan the older brief's reader dated by its issue (the date exactly the issue's: the blind
                    # sample of 2026-10-22, 8 of 40; 139 lines in Amerika and Ruslanda Esperantisto), the same
                    # … and one dated by the issue's year alone where the issue's month is now known (the reader saw no
                    # month; Ruslanda 1909 no. 4, Bakradze, «1909☞» beside ⟦anoncita inter 1909-05 kaj 1909-07⟧)
                    yr_only = re.fullmatch(r"1[6-9]\d\d", dv[:-1]) and dv[:-1] == str(iss[0]) and iss[1]
                    if "la dato de la numero" in conf or dv[:-1] == ann or yr_only:
                        start = re.match(r"inter (\S+) kaj", ann)
                        dv = f"dum aŭ post {start.group(1) if start else ann}☞"; date = f"**{dv}**"
                        notes["planned"]["dum aŭ post the announcement"] += 1
            # A LINE FROM A VOLUME'S INDEX (2026-10-27; the editor, on the accuracy check of 2026-10-27: Espero
            # Pacifista 1905–1908 and Lingvo Internacia 1905's half-year table, 9 lines that carried the index's December):
            # a line dated by its issue (⟦la dato de la numero⟧) that reads as an index entry (its page unnumbered, its anchor
            # ending in a page number, or the fact naming the index or table) and cites an earlier printed page of the same
            # item takes the date of the issue that holds that page (the page map's PDF page, that page's masthead):
            # ⟦la dato de la numero, laŭ la indekso⟧; where the map or the masthead does not say, «dum aŭ antaŭ ‹the
            # index's issue›», ⟦…, laŭ la indekso, konkludita⟧. A DECISIONS row still wins (applied after)
            if "⟦la dato de la numero⟧" in conf and not dv.endswith("☞") and not dv.startswith(("dum aŭ", "antaŭ", "inter", "[")):
                nd = index_issue(loc, *split_anchor(fact), dv, kind)
                if nd:
                    dv, why = nd; date = f"**{dv}**"
                    conf = conf.replace("⟦la dato de la numero⟧", f"⟦la dato de la numero, {why}⟧")
                    notes.setdefault("planned", collections.Counter())[f"index entry: {why}"] += 1
            # «antaŭ X» where X is the issue's own day, month or (an issue dated by its year only) year: «mortis antaŭ la
            # numero de januaro 1908» is «by the issue», which includes the issue's month, so «dum aŭ antaŭ X» (the editor,
            # 2026-10-22: approved; the blind sample of «post» / «antaŭ», 6 of 40)
            if m_ant := re.fullmatch(r"antaŭ (\S+)", dv):
                iss = _HF.issue_date(f"- $$$ X $$$ **x** · {{x}} · {loc}", day=True)
                if iss:
                    bounds = set(re.findall(r"\d{4}(?:-\d\d){0,2}", _HF.issue_field(iss)))
                    bounds |= {b[:7] for b in bounds if len(b) == 10}
                    if m_ant.group(1) in bounds:
                        dv = f"dum aŭ antaŭ {m_ant.group(1)}"; date = f"**{dv}**"
                        notes.setdefault("planned", collections.Counter())["antaŭ the issue → dum aŭ antaŭ"] += 1
            # «[sen dato]» IN A PERIODICAL, once its undated pass and page look are done (facts-config «undated_by_issue»;
            # the editor, 2026-10-23
            #): the issue reports the act, so it
            # came by the issue, ⟦la dato de la numero, konkludita⟧; a plan, «dum aŭ post ‹the
            # issue›☞» with ⟦anoncita⟧. Character, origin, family, lifelong profession, names, health and childhood stay
            # undated; so does a line with a verb in the future and no plan's kind («verkis himnon, kiu aperos»: the
            # writing came before, the appearing after), listed for a look
            if S.get("undated_by_issue") and date.replace("*", "").strip() == "[sen dato]":
                iss = _HF.issue_date(f"- $$$ X $$$ **x** · {{x}} · {loc}", day=True)
                # the reader's own date words, before a ruling made them «[sen dato]» («en liaj infanaj jaroj», «baldaŭ»)
                raw = re.search(r"\*\*([^*]*)\*\*", l.split(" · ")[0]); raw = raw.group(1).strip() if raw else ""
                keep = re.match(r"\{\s*(?:karaktero|deveno|familio|profesio|nomo|samnomo|civito|sano)\b", kind) \
                    or re.search(r"\b(?:infan|knab|junaĝ|junec|naskiĝ|gimnaziano|liceano|juna studento)", f"{fact} {raw}", re.I) \
                    or re.search(r"\b(?:gimnazi|universitat|student|klaso de)", raw, re.I)   # a school in the fact is a place
                ahead = re.search(r"^(?:(?:tre|espereble|eble) )*baldaŭ$|venont|proksim|estont|\beble post", raw)
                plan = re.search(r"\bplanit(?:a|aj|an|ajn)\b", kind) and not re.search(
                    r"\b(?:forlasit|nuligit|rezignit|malakceptit|prokrastit|ĉesigit|rifuzit|ne realigit|malsukces)\w*", kind)
                bi = notes.setdefault("by_issue", collections.Counter())
                if not iss: bi["left: no issue date"] += 1; notes.setdefault("by_issue_nodate", []).append(loc)
                elif keep: bi["left: character, origin, childhood …"] += 1
                elif not plan and (re.search(r"\b[a-zĉĝĥĵŝŭ]{2,}os\b", fact) or ahead):
                    bi["left: a verb or a date ahead"] += 1; notes.setdefault("by_issue_future", []).append(l)
                else:
                    ann = _HF.issue_field(iss)
                    bounds = re.findall(r"\d{4}(?:-\d\d){0,2}", ann)
                    enh = ", laŭ la enhavo" if len(iss) > 4 and iss[4] == "enhavo" else ""
                    if plan:
                        dv, add = f"dum aŭ post {bounds[0]}☞", f"⟦anoncita {ann}{enh}⟧"; bi["dum aŭ post (a plan)"] += 1
                    else:
                        dv, add = f"dum aŭ antaŭ {bounds[-1]}", f"⟦la dato de la numero{enh}, konkludita⟧"; bi["dum aŭ antaŭ"] += 1
                    date = f"**{dv}**"
                    conf = conf.rstrip()[:-1] + f"; {add})" if conf.rstrip().endswith(")") else f"{conf.rstrip()} ({add})"
                    if raw and raw != "[sen dato]":
                        notes.setdefault("by_issue_words", collections.Counter())[f"{dv.split(' ')[2]}: {raw}"] += 1
            if EMPTY_NOTE.search(conf):          # «⟦⟧», «⟦—⟧»: dropped, with the «; » or the brackets they leave
                conf = re.sub(r"\(\s*\)", "", re.sub(r"\(\s*;\s*", "(", re.sub(r"\s*;?\s*" + EMPTY_NOTE.pattern, "", conf))).rstrip()
            notes["dates"].append((view3, l, date))
            if date.startswith("**") and date.endswith("**"):   # no italics inside the bold date field (the parser)
                date = "**" + date[2:-2].replace("*", "") + "**"
            if th.strip() in ("[?]", ""): th = themes(fact)
            # «label_fixes» [old, new] or [key, old, new]: the confidence/independence field, e.g. a derived source given
            # its author, year and title (A DERIVED SOURCE IS NAMED WITH AUTHOR AND DATE, 2026-10-11); with a key, only on
            # the line whose fact contains the key (one author's label can mean different works on different lines)
            whole = f"- $$$ {name} $$${f' ({q})' if q else ''} {date} · {fact}"   # a key may name the line's head too
            for fx in S.get("label_fixes", []):
                key, a, b = fx if len(fx) == 3 else ("", fx[0], fx[1])
                conf = conf.replace("sen dato en la fonto", "s.d.")
                if (key in whole or key in l or key in view3) and a in conf: conf = conf.replace(a, b); used[(key, a)] += 1
            conf = conf.replace("sen dato en la fonto", "s.d.")
            # «malamika atestanto» is not for the fact readers (the editor, 2026-10-13
            #): taken out wherever a return has it
            conf = re.sub(r"\s*;\s*(?:aserto de )?malamika atestanto(?=\s*[;)])", "", conf)
            conf = re.sub(r"(?<=\()(?:aserto de )?malamika atestanto\s*(?:;\s*|(?=\)))", "", conf).replace(" ()", "")
            # a drop key may name the line as an earlier fix reworded it
            dk = next((k for k in S.get("drop_keys", []) if k in fact), None)
            if dk: used[("drop", dk)] += 1; dropped["by key"] += 1; notes["dropped"].append((l, f"drop key «{dk}»")); continue
            fact0 = fact
            fact, anchor = split_anchor(fact, 1 if re.search(r", l\. \d+\b", loc) else 6)   # FACTS FORMAT 3: the anchor in its own field, bare
            longest = max((len(s.split()) for s in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", anchor or "")) if s.strip()), default=0)
            if (anchor is None or longest < 6) and not re.search(r", l\. \d+\b", loc):
                # A SHORT ANCHOR PLACED BY TOOL (2026-10-17; the editor): no part of six words (the
                # harvest's rule), so placed on the text line where it begins, or on the one line of its page with the
                # head's surname, and marked as the tool's
                f1, a1 = split_anchor(fact0, 1)
                ln = place_line(loc, name, a1) if a1 else None
                if ln:
                    fact, anchor, (lnum, how) = f1, a1, ln
                    loc = f"{loc}, l. {lnum}"
                    conf = conf.rstrip()[:-1] + f"; ⟦linio laŭ ilo: {how}⟧)" if conf.rstrip().endswith(")") else f"{conf.rstrip()} (⟦linio laŭ ilo: {how}⟧)"
                    notes["placed"] = notes.get("placed", 0) + 1
            if anchor is None: bad.append(f"NO ANCHOR OF SIX WORDS: {l[:150]}"); anchor = ""
            conf = bracket(conf)                         # our additions in ⟦…⟧ (2026-10-14)
            conf, sc = scope_off(conf, fact)
            if sc: notes.setdefault("scope", []).append((name, q or "", "; ".join(sc), loc, "⚠ kept" if "⚠" in conf.split("(")[0] else ""))
            # THE ITEM KEY IN EVERY LOCATOR (2026-10-17; the item-key reform, the editor;
            # «absolutely»; «proceed»): each locator's item, as the reader wrote it (the file name), becomes its key from
            # the item table (Miles's «key» column, 2026-10-16 23:21). Last of all, so that «locator_fixes», DECISIONS and
            # «saying_dates», keyed on the old locators, have all matched first; the interventions match by page
            loc, nk = to_keys(loc); notes["keyed"] = notes.get("keyed", 0) + nk
            rows.append((page(loc), n, f"- $$$ {name} $$${f' ({q})' if q else ''} {date} · {kind.strip() + ' · ' if kind else ''}{fact} · {anchor} · {loc} · {th} · {conf}"))
            notes["applied"].append((f"{name} {date} · {fact} · {anchor}", applied, l))
    # the register of interventions (dowse/<source>/INTERVENTIONS.tsv): our additions, re-attached after every redowse to
    # the line they belong to, as DECISIONS are; one that finds no line is reported (2026-10-14, the proposal's B)
    rp = os.path.join(D, "INTERVENTIONS.tsv")
    regs = [(tuple(x.split("\t")[:7]) + ("",))[:7] for x in open(rp, encoding="utf-8").read().split("\n")[1:] if x and not x.startswith("#")] if os.path.exists(rp) else []
    regs = [(a, int(b), c, d, e, f, g) for a, b, c, d, e, f, g in regs]   # g: the line's key (2026-10-22), «» in older rows
    def fact_of(l):
        ps = l.split(" · ")
        return (ps[2] if len(ps) > 2 and ps[1].lstrip().startswith("{") else ps[1] if len(ps) > 1 else "").strip()[:40]
    fixed = {fact_of(e[1]) for e in S.get("replace_lines", []) if isinstance(e, list) and len(e) > 1} \
          | {fact_of(e) for e in S.get("extra_lines", []) if isinstance(e, str)}
    bc = os.path.join(D, "brief-config.json")
    btexts = json.load(open(bc, encoding="utf-8")).get("texts", []) if os.path.exists(bc) else []
    rows, notes["iv_attached"], notes["iv_unmatched"] = apply_interventions(rows, regs, frozenset(fixed - {""}),
                                                                            btexts)   # always: the correction rule is the default (2026-10-18)
    # the scope notes once more, after the interventions: the register re-attaches a ⟦pruvo: aliĝo ne datita⟧ it holds
    # (2026-10-17: 559 of them came back on the first run)
    fixed = []
    for pg, n, row in rows:
        ps = row.split(" · ")
        ps[-1] = one_note_each(ps[-1]); row = " · ".join(ps)
        conf, sc = scope_off(ps[-1], row)
        if sc:
            mh = re.match(r"^- \$\$\$ (.*?) \$\$\$(?: \(([^)]*)\))?", row)
            notes.setdefault("scope", []).append((mh.group(1) if mh else "?", (mh.group(2) or "") if mh else "", "; ".join(sc),
                                                   ps[-3] if len(ps) > 3 else "", "⚠ kept" if "⚠" in conf.split("(")[0] else ""))
            row = " · ".join(ps[:-1] + [conf])
        fixed.append((pg, n, row))
    rows = fixed
    # A LINE THE CHECK REFUSES IS HELD BACK (2026-10-17, Ruslanda Esperantisto's 30 issues: 42 of 8,961 lines, a short
    # anchor on garbled OCR or fields out of order, and the harvest writes nothing while any one stands): each line is
    # put through the harvest's own check (format 4 → 3 → 2, parse, strict) and, if refused, listed with the unreadable
    # lines and left out of the facts file, so the rest goes on; another source's in-form lines are not touched
    # THE RENAME BEYOND THE HEAD (2026-10-17; the editor): a «rename»
    # [old, q, new, q] reached the line's head only, so «kun: VEJSBRUT» made copies under the old name and our fact text
    # kept the reader's spelling. Now the kind field (its NAMES, «kun:» among them) and the fact take the new name too,
    # whole words only, the NAME in capitals and the fact's word in its capitalised form; the anchor, the source's own
    # words, is never touched
    # … but only a rename of a bare NAME: one of a qualified head («ZAMENHOF», «patro» → ZAMENHOF-PATRO; «ADAM», «Z.»)
    # says nothing of the name's other bearers, and swapping it everywhere made every ZAMENHOF of Waringhien's kinds
    # ZAMENHOF-PATRO (2026-10-17u, found by the reassembly's diff, 519 lines); a target with a qualifier is written in the
    # kinds' form, «SCHMIDT (Christian)», and the fact text then left alone
    # … and the fact text keeps a number the writer signed with (2026-10-23, tools/adresaro-numbers.py: «Esperantisto 4686
    # laŭdas …» had become «Bicknell laŭdas …», and «subskribas nur per «Esperantisto 4686»» a false «per «Bicknell»»):
    # an old NAME with a digit in it is the source's own form, which the fact reports; the head and kinds take the new
    swaps = [(a, c + (f" ({d})" if d else ""), not d and not re.search(r"\d", a)) for (a, b), (c, d) in rename.items() if a and c and a != c and not b]
    if swaps:
        renamed = []
        for pg, n, row in rows:
            ps = row.split(" · ")
            if len(ps) >= 7 and ps[1].startswith("{"):
                for a_, c_, in_fact in swaps:
                    ps[1] = re.sub(rf"(?<![\w-]){re.escape(a_)}(?![\w-])", c_, ps[1])
                    if in_fact: ps[2] = re.sub(rf"(?<![\w-]){re.escape(a_.title())}(?![\w-])", c_.title(), ps[2])
                row = " · ".join(ps)
            renamed.append((pg, n, row))
        rows = renamed
    form_repair("- $$$ X $$$")                                   # loads the harvest module (_HF)
    held = []
    for r in rows:
        l = r[2]
        l2, _k = _HF.take_kind(l) if re.search(r"\*\* · \{[^{}]*\} · ", l) else (l, None)
        rec, err = _HF.parse(_HF.to2(l2))
        if not err: err = _HF.strict(rec, True)
        if err: held.append(r); bad.append(f"HELD BACK, THE CHECK REFUSES IT ({err[:70]}): {l[:120]}")
    if held:
        rows = [r for r in rows if r not in held]
        notes["held"] = len(held)
    rows.sort(key=lambda r: (r[0], r[1]))
    text = S["header"].rstrip("\n").replace("facts-format: 2", "facts-format: 3") + "\n\n" + "\n".join(r[2] for r in rows) + "\n"
    if any(re.search(r"\*\* · \{[^{}]*\} · ", r[2]) for r in rows):    # a line carries an event kind: format 4
        text = text.replace("facts-format: 3", "facts-format: 4", 1)
    def why(key, a):
        """Why a fix found nothing (2026-10-12): its line was dropped, or other fixes changed its line first."""
        for raw, r in notes["dropped"]:
            if (key and key in raw) or (not key and a and a in raw): return f" — its line was dropped by the assembly ({r})"
        for view, ap, raw in notes["applied"]:
            if key and (key in raw or key in view) and ap:
                return " — its line was changed first by: " + "; ".join(f"«{x[1][:60]}»" for x in ap)
        if key and any(key in raw or key in view for view, ap, raw in notes["applied"]):
            return " — the key finds its line, but the old text is not in it: copy it from the line as it stands"
        return ""
    notes["unmatched"] = []                     # (settings key, fix) for --prune-fixes
    for name in ("quote_fixes", "fact_fixes"):   # a fix that matched nothing is reported, never silent
        for fx in S.get(name, []):
            key, a = (fx[0], fx[1]) if len(fx) == 3 else ("", fx[0])
            if not used[(key, a)]: bad.append(f"FIX MATCHED NO LINE: {key} | {a}{why(key, a)}"); notes["unmatched"].append((name, fx))
    for fx in S.get("label_fixes", []):
        key, a = (fx[0], fx[1]) if len(fx) == 3 else ("", fx[0])
        if not used[(key, a)]: bad.append(f"LABEL FIX MATCHED NO LINE: {key} | {a}{why(key, a)}"); notes["unmatched"].append(("label_fixes", fx))
    def why_date(key, a):
        """A date fix that found nothing: its line dropped, or the line's date is not the one the fix expects."""
        w = why(key, a)
        if "dropped" in w: return w
        found = [d for view, raw, d in notes["dates"] if key in view or key in raw]
        return f" — its line's date is {found[0]}, not {a}" if found else w
    for key, a, b in S.get("date_fixes", []):
        if not used[("date", key)]: bad.append(f"DATE FIX MATCHED NO LINE: {key}{why_date(key, a)}")
    for k in S.get("drop_keys", []):
        if not used[("drop", k)]: bad.append(f"DROP KEY MATCHED NO LINE: {k}")
    for k, d in enumerate(DECISIONS):           # after a redowse: a ruling whose line is gone or reworded, to re-decide
        if not used[("decision", k)]: bad.append(f"DECISION MATCHED NO LINE: {' | '.join(d)}")
    notes["replace_unkeyed"] = []                # «replace_lines»: each names its return (2026-10-15)
    for rl in S.get("replace_lines", []):
        if len(rl) < 3 and not used[("replace", rl[0])]:
            bad.append(f"REPLACE_LINES MATCHED NO LINE: {rl[0][:80]}"); notes["unmatched"].append(("replace_lines", rl))
        elif len(rl) < 3:
            notes["replace_unkeyed"].append(rl[0]); bad.append(f"REPLACE_LINES NAMES NO RETURN: {rl[0][:80]} (--key-replace-lines)")
        elif rl[2] not in S["returns"] and not (rl[2] in ("extra_lines", "restore") and S.get(rl[2])):
            bad.append(f"REPLACE_LINES FOR A RETURN NOT ASSEMBLED: {rl[2]} | {rl[0][:60]}"); notes["unmatched"].append(("replace_lines", rl))
        elif not used[("replace", rl[0])]:
            bad.append(f"REPLACE_LINES MATCHED NO LINE: {rl[0][:80]}"); notes["unmatched"].append(("replace_lines", rl))
    return text, rows, dropped, bad, notes

def after_readers(source, tag, frm="", until=""):
    """--after-readers TAG (2026-10-17; the editor; the runbook review, lever 3): the steps 6–9 of D6c, which the
    main session ran as seven commands and read one by one, run in order as this tool's own acts, each output written whole
    to dowse/<source>/after-readers-<tag>.log and only a line of each printed. Stops at the first step that fails or
    refuses; the steps before it stand, and the run can be repeated from there by the step's own command (the log says
    which). The «returns» of facts-config.json are set from agents-<tag>.tsv (was an Edit by hand)."""
    D = os.path.join(G, "dowse", source)
    T = os.path.join(ROOT, "tools")
    agents = os.path.join(D, f"agents-{tag}.tsv")
    if not os.path.exists(agents): sys.exit(f"refusing: {os.path.relpath(agents, ROOT)} is missing (D6c step 5 records it)")
    rets = [os.path.basename(l.split("\t")[1].strip()) for l in open(agents, encoding="utf-8") if l.strip() and not l.startswith("#") and "\t" in l]
    logp = os.path.join(D, f"after-readers-{tag}{'-from-' + frm if frm else ''}.log")
    if os.path.exists(logp): sys.exit(f"refusing: {os.path.relpath(logp, ROOT)} exists (a run of this tag has been made; --from STEP resumes)")
    log = open(logp, "x", encoding="utf-8")
    state = {"on": not frm, "past": False}
    # --until STEP (2026-10-23; the editor, to assembling a batch's sources side by side and harvesting once): the
    # steps after STEP are skipped, so each source stops after its own files (8b), and one run `--from 9a` of the last
    # source harvests for all, then `--from 9c` of each other source writes its dedupe brief. The harvest rebuilds every
    # profile and the build files, so two at once would write over each other; the steps up to 8b write only the source's
    # own files (its facts-config.json, INTERVENTIONS.tsv, profiles/by-source/<source>-dowse.md, its log)
    def reached(name):
        if state["past"]:
            print(f"--  {name}: skipped (--until {until})"); return False
        if not state["on"] and name.split(",")[0] == frm: state["on"] = True
        if not state["on"]: print(f"--  {name}: skipped (--from {frm})")
        if state["on"] and until and name.split(",")[0] == until: state["past"] = True   # this step runs, the rest do not
        return state["on"]
    def run(name, args, ok=lambda out, code: code == 0, pick=lambda out: (out.strip().split("\n") or [""])[-1]):
        if not reached(name): return ""
        cmd = [sys.executable] + args
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = p.stdout + p.stderr
        log.write(f"## {name}\n\n$ {' '.join(cmd)}\n\n{out}\n\n"); log.flush()
        good = ok(out, p.returncode)
        print(f"{'ok ' if good else 'STOP'} {name}: {pick(out)[:220]}")
        if not good:
            print(f"  stopped; the whole output is in {os.path.relpath(logp, ROOT)}"); log.close(); sys.exit(1)
        return out
    me = os.path.abspath(__file__)
    # A FIRST DOWSE (P3, the editor 2026-10-17; built 2026-10-17 19:5x, on Ruslanda Esperantisto, which
    # stopped at 7a): with no committed facts file there is nothing to take interventions from, carry dates from or
    # compare with, so 7a and 8a–8b are skipped, as the runbook marks them «redowse only»
    rel = os.path.relpath(os.path.join(G, "profiles", "by-source", f"{source}-dowse.md"), ROOT)
    first = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", f"HEAD:{rel}"], capture_output=True).returncode != 0
    if first:
        log.write("## a first dowse: no committed facts file, so 7a and 8a–8b are skipped (P3)\n\n")
        print("--  a first dowse: 7a and 8a–8b skipped (P3)")
        real_run = run
        def run(name, args, **kw):
            if name.split(",")[0] in ("7a", "8a", "8a2", "8a3", "8", "8b"):
                reached(name); return ""
            return real_run(name, args, **kw)
    run("6, file the returns", [os.path.join(T, "dowse-file-returns.py"), agents],
        ok=lambda out, code: code == 0 and "refused" not in out,
        pick=lambda out: f"{out.count('already filed')} already filed, {out.count(': filed ')} filed now, {out.count(': joined ')} joined from pieces" + ("; REFUSED, see the log" if "refused" in out else ""))
    run("6b, the format check of the returns", [os.path.join(T, "file-return.py"), "--lines"] + [f"geniza/dowse/{source}/{r}" for r in rets],
        pick=lambda out: "; ".join(l for l in out.strip().split("\n") if "fault" in l)[:220])
    run("7a, interventions from the committed file", [me, source, "--interventions", "HEAD"])
    if reached("7b, the returns"):
        cp = os.path.join(D, "facts-config.json"); cfg = json.load(open(cp, encoding="utf-8"))
        old = cfg.get("returns", [])
        if old != rets:
            cfg["returns"] = rets
            json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        msg = f"«returns» set from {os.path.basename(agents)}: {len(old)} → {len(rets)}" + (" (unchanged)" if old == rets else "")
        log.write(f"## 7b, the returns\n\n{msg}\nwas: {old}\nnow: {rets}\n\n"); print(f"ok  7b, {msg}")
    run("7c, prune the fixes", [me, source, "--prune-fixes", tag])
    run("7d, extend the anchors", [os.path.join(T, "dowse-anchor-extend.py"), source])
    run("7e, assemble", [me, source, "--replace"],
        pick=lambda out: next((l for l in out.split("\n") if " lines; dropped " in l), "") + " · " + (out.strip().split("\n") or [""])[-1])
    # THE OLD DATES CARRIED BEFORE THE RESTORE (2026-10-17; the editor): in Jossinet's
    # redowse most restored lines came back only for their dates, the new lines undated or dated more vaguely, and the
    # facts then stood twice. The old date goes onto the new line as a DECISIONS date row first; only what is still
    # lost after the reassembly is restored
    run("8a, the dates the new reading lost", [os.path.join(T, "dowse-compare-runs.py"), source, "--old", "HEAD", "--date-losses", tag])
    run("8a2, those dates as DECISIONS rows", [os.path.join(T, "dowse-compare-runs.py"), source, "--old", "HEAD", "--write-date-decisions", tag])
    run("8a3, reassemble with them", [me, source, "--replace"],
        pick=lambda out: next((l for l in out.split("\n") if " lines; dropped " in l), ""))
    run("8, compare with the committed file", [os.path.join(T, "dowse-compare-runs.py"), source, "--old", "HEAD", "--show", "200"],
        pick=lambda out: next((l for l in out.split("\n") if l.strip()), ""))
    run("8b, the lost lines into «restore»", [os.path.join(T, "dowse-compare-runs.py"), source, "--old", "HEAD", "--write-restore"])
    if state["past"] and until in ("6", "6b", "7a", "7b", "7c", "7d", "7e", "8a", "8a2", "8a3", "8", "8b"):
        log.close()
        print(f"done up to {until}; every output in {os.path.relpath(logp, ROOT)}. Next, once every source of the batch is "
              f"this far: --after-readers {tag} --from 9a for one of them (the harvest, for all), then --from 9c for the others")
        return 0
    run("9a, the check", [os.path.join(T, "harvest-facts.py"), "--check", "--quiet"],
        ok=lambda out, code: code == 0, pick=lambda out: next((l for l in out.split("\n") if l.startswith("scanned")), ""))
    run("9b, the harvest", [os.path.join(T, "harvest-facts.py"), "--quiet"],
        pick=lambda out: next((l for l in out.split("\n") if l.startswith("missing-facts report")), (out.strip().split("\n") or [""])[-1]))
    # THE DOWSED LIST after every harvest (2026-10-24; the editor
    #): dowse/DOWSED-LATEST.md and DOWSED-ITEMS-LATEST.tsv
    run("9b2, the dowsed list", [os.path.join(T, "dowse-done.py")])
    published_pages(run, "9b3")
    # THE DEDUPE AS THE BATCH'S NEXT PHASE (P1's later phases, 2026-10-18, the dowse fixes): on a first dowse (no
    # alignment, «redowse only») the dedupe brief is written here and the next workflow's arguments with it, so the main
    # session launches the one dedupe reader and then runs --after-dedupe; a redowse aligns first (step 10)
    if first:
        run("9c, the dedupe brief", [os.path.join(T, "harvest-facts.py"), "--dedupe-brief", source, tag])
        wp = os.path.join(D, f"workflow-dedupe-{tag}.json")
        brief = os.path.join(D, f"dedupe-brief-{tag}.md")
        if os.path.exists(brief) and not os.path.exists(wp):
            json.dump({"readers": [{"label": f"geniza/dowse/{source}/dedupe-return-{tag}.md",
                                    "prompt": f"Read the brief {brief} and carry out the task it gives, section «La briefo». Your final message is the report it asks for."}]},
                      open(wp, "x", encoding="utf-8"), ensure_ascii=False, indent=1)
        log.close()
        print(f"done; every output in {os.path.relpath(logp, ROOT)}. Next: the Workflow tool, tools/workflows/carney-readers.js, "
              f"args from {os.path.relpath(wp, ROOT)}; then --after-dedupe {tag} <run id> [<the readers' run id> …]")
        return 0
    log.close()
    print(f"done; every output in {os.path.relpath(logp, ROOT)}. Next: D6c step 10 (the alignment), then the dedupe (D6 point 7)")
    return 0

def after_dedupe(source, tag, run_id, more_runs=(), frm=""):
    """--after-dedupe TAG RUN [RUN …] (P1's later phases and P4, P6; 2026-10-18, the dowse fixes): after the dedupe
    reader's workflow, its agents file and filing, the rows and their acceptance under P4 (no sample), the reassembly and
    the harvest, each as this tool's own act with its output in dowse/<source>/after-dedupe-<tag>.log; then the batch's
    one review document, dowse/<source>/BATCH-REVIEW-<tag>.md: the lines held back, the dedupe's verdicts with every
    uncertain pair in full, the source's fault rates, the build's missing facts, and the cost line of each run named
    (the dedupe's and, given, the readers')."""
    D = os.path.join(G, "dowse", source); T = os.path.join(ROOT, "tools"); me = os.path.abspath(__file__)
    logp = os.path.join(D, f"after-dedupe-{tag}{'-from-' + frm if frm else ''}.log")
    if os.path.exists(logp): sys.exit(f"refusing: {os.path.relpath(logp, ROOT)} exists" + ("" if frm else " (--from STEP resumes)"))
    # --from STEP (2026-10-23: The Esperantist stopped at d5 after d3–d4 had written its DECISIONS rows): the steps before
    # it are skipped, their outputs read back from the first run's log for the review document
    first_log = os.path.join(D, f"after-dedupe-{tag}.log")
    earlier = {}
    if frm and os.path.exists(first_log):
        for sec in open(first_log, encoding="utf-8").read().split("\n## ")[0:]:
            nm = sec.lstrip("# ").split("\n", 1)[0]
            earlier[nm] = sec.split("\n\n", 2)[2] if sec.count("\n\n") >= 2 else ""
    state = {"on": not frm}
    log = open(logp, "x", encoding="utf-8"); outs = {}
    def run(name, args, ok=lambda out, code: code == 0):
        if not state["on"] and name.split(",")[0] == frm: state["on"] = True
        if not state["on"]:
            print(f"--  {name}: skipped (--from {frm})"); outs[name] = earlier.get(name, ""); return outs[name]
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True); out = p.stdout + p.stderr
        log.write(f"## {name}\n\n$ {' '.join(args)}\n\n{out}\n\n"); log.flush(); outs[name] = out
        good = ok(out, p.returncode)
        print(f"{'ok ' if good else 'STOP'} {name}: {(out.strip().split(chr(10)) or [''])[-1][:200]}")
        if not good: log.close(); sys.exit(f"  stopped; the whole output is in {os.path.relpath(logp, ROOT)}")
        return out
    # one dedupe workflow for several sources (2026-10-21, the five-source batch): the first source's d1 writes every
    # source's agents-<run>.tsv, and the tool refuses the next time; this source's own file then stands
    mine = os.path.join(D, f"agents-{run_id}.tsv")
    run("d1, the agents file", [os.path.join(T, "workflow-agents.py"), run_id, "--write"],
        ok=lambda out, code: code == 0 or ("refused, nothing written: exists" in out and os.path.exists(mine)))
    run("d2, file the return", [os.path.join(T, "dowse-file-returns.py"), os.path.join(D, f"agents-{run_id}.tsv")],
        ok=lambda out, code: code == 0 and "refused" not in out)
    rows = run("d3, the dedupe rows", [os.path.join(T, "harvest-facts.py"), "--dedupe-rows", source, tag])
    run("d4, accepted under P4", [os.path.join(T, "harvest-facts.py"), "--dedupe-accept", tag,
                                  "the dowse runbook, P4: «I do not need to review the sample drops if they are of the quality you have shown me»",
                                  "--source", source])   # this source's rows only: another's of the same tag stay as they are
    asm = run("d5, reassemble", [me, source, "--replace"])
    hv = run("d6, the harvest", [os.path.join(T, "harvest-facts.py"), "--quiet"])
    run("d6b, the dowsed list", [os.path.join(T, "dowse-done.py")])   # after every harvest (2026-10-24)
    published_pages(run, "d6c")
    # THE UNDATED PASS AS THE BATCH'S NEXT PHASE (2026-10-18, the dowse fixes; the editor, to
    # the runbook's step 10c): its list and brief here, and the workflow's arguments for its one reader
    # the list a source's own (2026-10-24, L'Espérantiste: the shared UNDATED-2026-10-23.tsv, written the day before for
    # Lingvo Internacia 1906–1914 of the same tag, was not overwritten, and its prep found «nothing to read»)
    ul = os.path.join(G, "profiles", "build", f"UNDATED-{tag}-{source}.tsv")
    run("d7, the undated list", [os.path.join(T, "harvest-facts.py"), "--check", "--quiet", "--undated", ul])
    up = run("d8, the undated brief", [os.path.join(T, "dowse-undated.py"), "prep", source, tag, "--list", ul, "--split", str(UNDATED_CAP)])
    undated = undated_workflow(source, tag, up)
    # THE ACCURACY CHECK AS THE BATCH'S NEXT PHASE (2026-10-23; the editor
    # the runbook's step 11, skipped for every batch from 2026-10-16 to
    # 2026-10-22): the sample and the brief here, the reader's arguments in workflow-accuracy-<tag>.json, launched with the
    # undated readers on the editor's
    import datetime as _dt
    today = _dt.date.today().isoformat()
    run("d9, the accuracy sample", [os.path.join(T, "dowse-accuracy-prep.py"), source, "--date", today])
    acc = run("d10, the accuracy brief", [os.path.join(T, "dowse-accuracy-brief.py"), source, "--date", today, "--workflow"])
    aw = os.path.join(D, f"workflow-accuracy-{tag}.json")
    rd = next((json.loads(l) for l in acc.split("\n") if l.startswith("{")), None)
    if rd and not os.path.exists(aw):
        json.dump({"readers": [rd]}, open(aw, "x", encoding="utf-8"), ensure_ascii=False, indent=1)
    log.close()
    # the review document
    lines_n = next((l.split(" lines;")[0] for l in asm.split("\n") if " lines; dropped " in l), "?")
    held = [l.strip()[len("UNREADABLE: "):] for l in asm.split("\n") if l.strip().startswith("UNREADABLE:")]
    ret = os.path.join(D, f"dedupe-return-{tag}.md")
    unsure = [l.strip() for l in open(ret, encoding="utf-8")] if os.path.exists(ret) else []
    unsure = [l for l in unsure if re.search(r"\bnecerte\b", l) and not l.startswith(("Fino", "unu fakto"))]
    fr = open(os.path.join(G, "profiles", "build", "FAULT-RATES-LATEST.md"), encoding="utf-8").read().split("\n")
    head = next((l for l in fr if l.startswith("| type |")), "")
    col = [c.strip() for c in head.split("|")].index(source) if source in head else None
    rates = [(c[1].strip(), c[col].strip()) for l in fr if l.startswith("| ") and not l.startswith(("| type", "|---"))
             for c in [l.split("|")] if col and len(c) > col]
    missing = next((l for l in hv.split("\n") if l.startswith("missing-facts report")), "")
    costs = [subprocess.run([sys.executable, os.path.join(T, "workflow-agents.py"), r, "--cost"], capture_output=True, text=True).stdout.strip()
             for r in (run_id,) + tuple(more_runs)]
    doc = [f"# {source}: the batch's review document ({tag})", "",
           f"`[tools/dowse-facts-assemble.py --after-dedupe {tag}; the runbook, P4: one generated document for the editor, every item in full; its log {os.path.basename(logp)}.]`", "",
           f"**Lines:** {lines_n}. **The dedupe:** {(rows.strip().split(chr(10)) or [''])[-1]}. **The build:** {missing}", "",
           "## For the editor", "", "### The dedupe's uncertain pairs", ""] + ([f"- {u}" for u in unsure] or ["(none)"]) + [
           "", "## For the record", "", f"### The lines held back or unreadable ({len(held)})", ""] + ([f"- {h}" for h in held] or ["(none)"]) + [
           "", "### The source's fault rates", ""] + ([f"- {t}: {v}" for t, v in rates] or ["(not found)"]) + [
           "", "### The cost", ""] + [f"- {c}" for c in costs] + [
           "", "(the harness's own count, from the workflow's notification, is added by the main session; output tokens are exact)",
           "", "### The undated pass", "", f"- {undated}",
           "", "### The accuracy check", "", f"- the sample and brief of {today}; the reader's arguments in {os.path.basename(aw)}, launched with the undated readers"]
    bp = os.path.join(D, f"BATCH-REVIEW-{tag}.md")
    with open(bp, "x", encoding="utf-8") as fh: fh.write("\n".join(doc) + "\n")
    print(f"done; the review document {os.path.relpath(bp, ROOT)}. The undated pass: {undated}")
    return 0

UNDATED_CAP = 80   # lines a reader, as a reader's range (P1, «sized before written»)
def undated_workflow(source, tag, prep_out, page=False):
    """After `dowse-undated.py prep`: the workflow's arguments for its one reader, dowse/<source>/workflow-undated-<tag>.json
    (create-only), or why there is none. -> a line for the review document."""
    D = os.path.join(G, "dowse", source)
    if "nothing to read" in prep_out or "nothing for the page" in prep_out:
        return "nothing to read" + (" on the page" if page else "")
    m = re.search(r"(\d+) to read", prep_out) or re.search(r"(\d+) lines of \S+ sent to the page", prep_out)
    n = int(m.group(1)) if m else 0
    # the briefs prep wrote: one, or the parts of a list over a reader's cap (prep --split, 2026-10-18), one reader each
    parts = re.findall(r"undated-brief-(\S+?)\.md \((\d+) lines\)", prep_out)
    if not parts: return f"no brief written ({(prep_out.strip().split(chr(10)) or [''])[-1][:160]})"
    over = [t for t, k in parts if int(k) > UNDATED_CAP]
    if over: return f"{n} lines; parts over a reader's {UNDATED_CAP}: {', '.join(over)}; not launched"
    wp = os.path.join(D, f"workflow-undated-{tag}.json")
    if not os.path.exists(wp):
        json.dump({"readers": [{"label": f"geniza/dowse/{source}/undated-return-{t}.md",
                                "prompt": f"UNDATED-{source}-{t}. Read the brief at {os.path.join(D, f'undated-brief-{t}.md')} (the part after the line «---») and do exactly "
                                          "what it says. Read tool only. Your report is your final message, ending with the line «Fino: N linioj.»"} for t, _k in parts]},
                  open(wp, "x", encoding="utf-8"), ensure_ascii=False, indent=1)
    return (f"{n} lines{' for the page' if page else ''}, {len(parts)} reader{'s' if len(parts) > 1 else ''}: the Workflow tool, tools/workflows/carney-readers.js, args from "
            f"{os.path.relpath(wp, ROOT)}; then --after-undated {tag} <run id>")

def after_undated(source, tag, run_id):
    """--after-undated TAG RUN (2026-10-18): after the undated reader's workflow, its agents file, the filing, and
    `dowse-undated.py apply`'s dry run, whole, in dowse/<source>/after-undated-<tag>.log. Then it stops: the dowser checks
    each proposed date against the template's rules (the runbook, step 10c) and writes with `apply --write` and its
    --skip/--keep/--set; then --after-undated-written TAG."""
    D = os.path.join(G, "dowse", source); T = os.path.join(ROOT, "tools")
    logp = os.path.join(D, f"after-undated-{tag}.log")
    if os.path.exists(logp): sys.exit(f"refusing: {os.path.relpath(logp, ROOT)} exists")
    log = open(logp, "x", encoding="utf-8")
    def run(name, args, ok=lambda out, code: code == 0):
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True); out = p.stdout + p.stderr
        log.write(f"## {name}\n\n$ {' '.join(args)}\n\n{out}\n\n"); log.flush()
        good = ok(out, p.returncode)
        print(f"{'ok ' if good else 'STOP'} {name}: {(out.strip().split(chr(10)) or [''])[-1][:200]}")
        if not good: log.close(); sys.exit(f"  stopped; the whole output is in {os.path.relpath(logp, ROOT)}")
        return out
    mine = os.path.join(D, f"agents-{run_id}.tsv")     # one workflow for several sources, as at d1 (2026-10-21)
    run("u1, the agents file", [os.path.join(T, "workflow-agents.py"), run_id, "--write"],
        ok=lambda out, code: code == 0 or ("refused, nothing written: exists" in out and os.path.exists(mine)))
    run("u2, file the return", [os.path.join(T, "dowse-file-returns.py"), os.path.join(D, f"agents-{run_id}.tsv")],
        ok=lambda out, code: code == 0 and "refused" not in out)
    # each part's tag (prep --split: TAG-1, TAG-2 …), or the one tag
    tags = sorted((re.match(r"undated-input-(.+)\.tsv$", os.path.basename(p)).group(1)
                   for p in glob.glob(os.path.join(D, f"undated-input-{glob.escape(tag)}-*.tsv"))),
                  key=lambda t: int(t.rsplit("-", 1)[1]) if t.rsplit("-", 1)[1].isdigit() else 0) or [tag]
    out = "".join(run(f"u3, apply, a dry run ({t})", [os.path.join(T, "dowse-undated.py"), "apply", source, t]) for t in tags)
    log.close()
    n = f"date rows: {sum(int(x) for x in re.findall(r'^date rows: (\d+)', out, re.M))} in {len(tags)} part(s)"
    print(f"done; the dry run in {os.path.relpath(logp, ROOT)} ({n[:80]}). Next: check each DATO against the template's rules, "
          f"then dowse-undated.py apply {source} {tag} --write [--skip N] [--keep N --why …] [--set N=VALUE]; then --after-undated-written {tag}")
    return 0

def after_undated_written(source, tag):
    """--after-undated-written TAG (2026-10-18): after `apply --write`, the reassembly and the harvest; the facts file's
    changed lines against the date rows written (any other is the register's, an intervention's, or a row that took a line
    it should not have: the runbook, step 10c); the page look's brief (tag TAGp) and its workflow's arguments; and the
    undated pass's lines appended to the batch's review document, if there is one."""
    D = os.path.join(G, "dowse", source); T = os.path.join(ROOT, "tools"); me = os.path.abspath(__file__)
    logp = os.path.join(D, f"after-undated-written-{tag}.log")
    if os.path.exists(logp): sys.exit(f"refusing: {os.path.relpath(logp, ROOT)} exists")
    log = open(logp, "x", encoding="utf-8")
    def run(name, args, ok=lambda out, code: code == 0):
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True); out = p.stdout + p.stderr
        log.write(f"## {name}\n\n$ {' '.join(args)}\n\n{out}\n\n"); log.flush()
        good = ok(out, p.returncode)
        print(f"{'ok ' if good else 'STOP'} {name}: {(out.strip().split(chr(10)) or [''])[-1][:200]}")
        if not good: log.close(); sys.exit(f"  stopped; the whole output is in {os.path.relpath(logp, ROOT)}")
        return out
    prev = os.path.join(D, f"after-undated-{tag}.log")
    rows_n = sum(int(x) for x in re.findall(r"^date rows: (\d+)", open(prev, encoding="utf-8").read(), re.M)) if os.path.exists(prev) else None
    fp = os.path.join(G, "profiles", "by-source", f"{source}-dowse.md")
    before = collections.Counter(open(fp, encoding="utf-8").read().split("\n"))
    run("w1, reassemble", [me, source, "--replace"])
    run("w2, the harvest", [os.path.join(T, "harvest-facts.py"), "--quiet"])
    changed = sum((collections.Counter(open(fp, encoding="utf-8").read().split("\n")) - before).values())   # lines new or changed
    ul = os.path.join(G, "profiles", "build", f"UNDATED-{tag.rstrip('p')}-{source}.tsv")   # the source's own (d7), else the
    if not os.path.exists(ul): ul = os.path.join(G, "profiles", "build", f"UNDATED-{tag}.tsv")   # shared one of earlier runs
    if tag.endswith("p"):   # the page look's own run: no list of its own and no page look after it (2026-10-18)
        page = "none after the page look"
    else:
        # split at a reader's cap, as d8 splits the undated list (2026-10-25: La Belga Sonorilo's page look, 127 lines, was
        # written whole and «not launched»)
        up = run("w4, the page look's brief", [os.path.join(T, "dowse-undated.py"), "prep", source, f"{tag}p", "--page", "--list", ul,
                                               "--split", str(UNDATED_CAP)])
        page = undated_workflow(source, f"{tag}p", up, page=True)
    log.close()
    check = (f"{changed} lines of the facts file changed by the reassembly, against {rows_n} date rows"
             + ("" if rows_n is None or changed == rows_n else "  ⚠ the counts differ: see the runbook, step 10c"))
    bp = os.path.join(D, f"BATCH-REVIEW-{re.sub(r'p$', '', tag)}.md")
    if os.path.exists(bp):
        with open(bp, "a", encoding="utf-8") as fh: fh.write(f"- written ({tag}): {check}\n- the page look: {page}\n")
    print(f"done; {check}. The page look: {page}")
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("--replace", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune-fixes", metavar="TAG", help="after a redowse that replaced returns: move the quote, fact and label "
                    "fixes that match no line, and the «replace_lines» of returns no longer assembled or matching no line, "
                    "into «fixes_superseded_TAG» in the settings (kept, not applied), then stop")
    ap.add_argument("--again", action="store_true", help="with --interventions REV: rebuild an untracked register from REV "
                    "alone (refused for a tracked one)")
    ap.add_argument("--note-moves", type=int, nargs="?", const=20, default=0, metavar="N", help="the notes of ours each line "
                    "lost or gained against the committed facts file, by line key; the first N listed; writes nothing (2026-10-22)")
    ap.add_argument("--interventions", nargs="?", const="", metavar="REV", help="add the ⟦…⟧ additions of the assembled "
                    "lines (and, with REV, of the facts file at that git revision) to dowse/<source>/INTERVENTIONS.tsv, "
                    "new rows only, then stop; the next assembly re-attaches them")
    ap.add_argument("--show-interventions", type=int, default=0, metavar="N", help="print the first N re-attachments")
    ap.add_argument("--iv-report", type=int, default=0, metavar="N", help="T1: the re-attachments by the shares of the registered anchor and fact the chosen line holds, a histogram and the N weakest")
    ap.add_argument("--iv-ids", action="store_true", help="T1 TRIAL: re-attach each intervention by its anchor's sentence in the text (fact-ids), the words only within it")
    ap.add_argument("--iv-note", action="store_true", help="T1 TRIAL: a note by its own words and kind (Fable's rule, 2026-10-18)")
    ap.add_argument("--iv-compare-out", metavar="FILE", help="with --iv-compare: write the whole comparison, unshortened, to FILE (create-only)")
    ap.add_argument("--iv-place", action="store_true", help="T1: re-attach each intervention by its anchor's place in the text: an overlapping anchor, else the window's best by words, else the word rule")
    ap.add_argument("--iv-compare", type=int, default=0, metavar="N", help="T1: the sentence rule's choices against the word rule's, counted, and N of each kind of difference; use with --dry-run")
    ap.add_argument("--show-drops", action="store_true", help="print each line dropped as a duplicate or an exact repeat")
    ap.add_argument("--key-replace-lines", action="store_true", help="give each «replace_lines» entry that names no return "
                    "the one return whose text holds its key, in the settings; an entry found in none or several is printed, then stop")
    ap.add_argument("--bare-cover", action="store_true", help="a qualified «out» row also covers the bare lines of a surname with no namesake (proposed 2026-10-15)")
    ap.add_argument("--after-readers", metavar="TAG", help="D6c steps 6–9 in one command (2026-10-17): file the returns of "
                    "agents-TAG.tsv, register the interventions, set «returns», prune, extend anchors, assemble, compare, "
                    "check and harvest; a summary printed, every output in dowse/<source>/after-readers-TAG.log; stops at the first failure")
    ap.add_argument("--from", dest="frm", default="", metavar="STEP", help="with --after-readers: resume at a step (6, 6b, 7a, 7b, 7c, 7d, 7e, 8a, 8a2, 8a3, 8, 8b, 9a, 9b, 9b2, 9b3, 9c)")
    ap.add_argument("--until", default="", metavar="STEP", help="with --after-readers: stop after a step (8b: a batch's sources side by side, then one harvest; 2026-10-23)")
    ap.add_argument("--after-dedupe", nargs="+", metavar=("TAG", "RUN"), help="after the dedupe reader's workflow: TAG, its run id, "
                    "and any other run ids of the batch for the cost line: file, rows, accept (P4), reassemble, harvest, and the "
                    "batch's review document, dowse/<source>/BATCH-REVIEW-TAG.md, and the undated pass's brief and workflow arguments (2026-10-18)")
    ap.add_argument("--after-undated", nargs=2, metavar=("TAG", "RUN"), help="after the undated reader's workflow: file it and "
                    "run dowse-undated.py apply as a dry run, for the dowser's check (2026-10-18)")
    ap.add_argument("--after-undated-written", metavar="TAG", help="after dowse-undated.py apply --write: reassemble, harvest, "
                    "the changed lines against the date rows, the page look's brief (TAGp) and its workflow arguments (2026-10-18)")
    a = ap.parse_args()
    if a.after_undated: return after_undated(a.source, *a.after_undated)
    if a.after_undated_written: return after_undated_written(a.source, a.after_undated_written)
    if a.after_dedupe:
        if len(a.after_dedupe) < 2: sys.exit("refusing: --after-dedupe TAG RUN [RUN …]")
        return after_dedupe(a.source, a.after_dedupe[0], a.after_dedupe[1], a.after_dedupe[2:], a.frm)
    if a.after_readers: return after_readers(a.source, a.after_readers, a.frm, a.until)
    global BARE_COVER, IV_IDS, IV_PLACE, IV_COMPARE, IV_NOTE; BARE_COVER = a.bare_cover; IV_IDS = a.iv_ids; IV_PLACE = a.iv_place; IV_COMPARE = a.iv_compare; IV_NOTE = a.iv_note
    if a.key_replace_lines:   # 2026-10-15, the Fable review 1: an entry is applied only to the return it names
        D = os.path.join(G, "dowse", a.source); cp = os.path.join(D, "facts-config.json")
        cfg = json.load(open(cp, encoding="utf-8")); texts = {r: open(os.path.join(D, r), encoding="utf-8").read() for r in cfg["returns"]}
        for part in ("extra_lines", "restore"):    # the settings' own lines are assembled as these two «returns»
            if cfg.get(part): texts[part] = "\n".join(cfg[part])
        done, left = 0, []
        for rl in cfg.get("replace_lines", []):
            if len(rl) >= 3: continue
            hits = [r for r, t in texts.items() if rl[0] in t]
            if len(hits) == 1: rl.append(hits[0]); done += 1
            else: left.append(f"  {len(hits)} returns hold «{rl[0][:70]}»: {', '.join(hits) or '-'}")
        if done: json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{done} «replace_lines» entries keyed to their return; {len(left)} left"); print("\n".join(left)); return
    if a.note_moves:
        # --note-moves (2026-10-22): the facts file against its committed version, line by line by line_key: the notes
        # of ours (⟦…⟧) each line lost or gained, leaving out those the assembler writes itself (⟦interpretdato⟧,
        # ⟦anoncita⟧, ⟦la dato de la numero⟧); and the lines found in only one of the two. Writes nothing
        rel = os.path.relpath(os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md"), ROOT)
        old = subprocess.run(["git", "-C", ROOT, "show", f"HEAD:{rel}"], capture_output=True, text=True).stdout
        cur = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        own = re.compile(r"⟦(?:interpretdato|anoncita|la dato de la numero|la jaro laŭ la numero⟧)")
        def notes_by_key(t):
            out, fl = {}, [l for l in t.split("\n") if l.startswith("- $$$")]
            for k, l in zip(keys_of(fl), fl): out.setdefault(k, []).append(sorted(n for n in re.findall(r"⟦[^⟧]*⟧", l) if not own.match(n)))
            return out
        o, c = notes_by_key(old), notes_by_key(cur)
        moved = [(k, x, y) for k in o.keys() & c.keys() for x, y in [(o[k], c[k])] if sorted(map(tuple, x)) != sorted(map(tuple, y))]
        print(f"{a.source}: {len(o.keys() & c.keys())} lines by key in both; {len(o.keys() - c.keys())} only in the committed file, "
              f"{len(c.keys() - o.keys())} only in the new; {len(moved)} lines whose notes changed")
        for k, x, y in moved[:a.note_moves]:
            lost = sorted(set(n for v in x for n in v) - set(n for v in y for n in v)); got = sorted(set(n for v in y for n in v) - set(n for v in x for n in v))
            print(f"  {k}: lost {lost[:3]} · gained {got[:3]}")
        return
    if a.interventions is not None:
        rp = os.path.join(G, "dowse", a.source, "INTERVENTIONS.tsv")
        # --again: the register rebuilt from the revision alone, refused for a register git tracks (P5: a tool rewrites only
        # its own untracked file); 2026-10-22, the registers first written that day from a file reassembled before the key
        tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", rp], capture_output=True).returncode == 0
        if a.again and tracked: sys.exit(f"refusing: {os.path.relpath(rp, ROOT)} is tracked by git (restore it from git instead)")
        have = open(rp, encoding="utf-8").read().split("\n") if os.path.exists(rp) and not a.again else [
            "\t".join(["name", "page", "anchor", "fact_words", "addition", "origin", "line_key"])]
        if have and have[0].startswith("name\t") and not have[0].rstrip().endswith("line_key"): have[0] = have[0].rstrip() + "\tline_key"
        keys = {tuple(x.split("\t")[:5]) for x in have[1:] if x}
        new = []
        if a.interventions:
            rel = os.path.relpath(os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md"), ROOT)
            old = subprocess.run(["git", "-C", ROOT, "show", f"{a.interventions}:{rel}"], capture_output=True, text=True).stdout
            new += intervention_rows(old, f"git {a.interventions}")
        cur = open(os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md"), encoding="utf-8").read()
        # the assembled file's notes only where the revision lacks that note on that page (2026-10-22): a note a
        # reassembly placed wrongly is not registered beside the revision's own
        at_rev = {(r[1], r[4]) for r in new}
        new += [r for r in intervention_rows(cur, "assembled") if (r[1], r[4]) not in at_rev]
        # an older row of the same note (the same five fields) gains the line's key it lacked (2026-10-22): the key of
        # the line the note stands on in the revision given (its first sighting here), so it returns to that line
        lk = {}
        for r in new: lk.setdefault(tuple(str(x) for x in r[:5]), r[6])
        filled = 0
        for j, x in enumerate(have[1:], 1):
            if not x: continue
            f = x.split("\t")
            k = tuple(f[:5])
            # the key from the revision given wins over one written before (a key made unique by its date since)
            if lk.get(k) and (len(f) < 7 or f[6] != lk[k]):
                f = (f + [""] * 7)[:6] + [lk[k]]; have[j] = "\t".join(f); filled += 1
        add = []
        for r in new:
            k = tuple(str(x) for x in r[:5])
            if k not in keys: keys.add(k); add.append("\t".join(str(x).replace("\t", " ") for x in r))
        open(rp, "w", encoding="utf-8").write("\n".join([x for x in have if x] + add) + "\n")
        print(f"{len(add)} interventions added to {os.path.relpath(rp, ROOT)} ({len(keys)} in all); {filled} older rows given their line's key"); return
    text, rows, dropped, bad, notes = assemble(a.source)
    if notes.get("iv_attached") or notes.get("iv_unmatched"):
        print(f"interventions: {len(notes['iv_attached'])} re-attached to a line that lacked them; {len(notes['iv_unmatched'])} found no line")
        if a.show_interventions:
            for line, add, anchor, origin, *_ in notes["iv_attached"][:a.show_interventions]:
                print(f"  ATTACHED {add[:100]}\n     from anchor «{anchor[:70]}» ({origin})\n     to {line}")
        if a.iv_report:   # T1: the shares of the registered anchor and fact the chosen line holds, the weakest first
            att = sorted(notes["iv_attached"], key=lambda x: x[4][0] + x[4][1])
            buckets = collections.Counter(min(9, int(10 * (x[4][0] + x[4][1]) / 2)) for x in att)
            print("  shares (anchor+fact)/2 by tenths: " + ", ".join(f"{b / 10:.1f}: {buckets[b]}" for b in sorted(buckets)))
            for line, add, anchor, origin, (sa, sf), fw in att[:a.iv_report]:
                print(f"  {sa:.2f}/{sf:.2f} {add[:90]}\n     registered anchor «{anchor[:80]}»; fact «{fw[:80]}»\n     to {line}")
        if not a.iv_compare:
            for nm, pg, add, origin in notes["iv_unmatched"][:40]: print(f"  INTERVENTION FOUND NO LINE: {nm} | PDF {pg} | {add[:120]} | {origin}")
    if a.iv_compare:   # T1: the sentence rule against the word rule, each registered note once
        kinds = collections.defaultdict(list)
        for wb, ib, how, nm, pg, add, anchor, origin in IV_CMP:
            k = ("same line" if wb == ib else "words: a line; sentence: none" if ib is None
                 else "words: none; sentence: a line" if wb is None else "a different line") + f" ({how})"
            kinds[k].append((wb, ib, nm, pg, add, anchor, origin))
        out_ = [f"T1 compare, {len(IV_CMP)} registered notes: " + "; ".join(f"{k} {len(v)}" for k, v in sorted(kinds.items()))]
        for k, v in sorted(kinds.items()):
            if k.startswith("same line"): continue
            out_.append(f"== {k}: {len(v)}")
            for wb, ib, nm, pg, add, anchor, origin in v[:a.iv_compare]:
                out_.append(f"  {nm} | PDF {pg} | {add} | {origin}\n     registered anchor «{anchor}»\n"
                            f"     today's rule (words) → {wb or '-'}\n     the new rule → {ib or '-'}")
        print("\n".join(x if len(x) < 2000 else x[:2000] for x in out_[:1]))
        if a.iv_compare_out:   # the whole comparison, unshortened, for a reader (2026-10-18: T1's window, to Fable)
            if os.path.exists(a.iv_compare_out): sys.exit(f"refusing: {a.iv_compare_out} exists")
            open(a.iv_compare_out, "x", encoding="utf-8").write("\n".join(out_) + "\n")
            print(f"wrote {a.iv_compare_out}")
        else:
            print("\n".join(out_[1:]))
    if a.prune_fixes:
        cp = os.path.join(G, "dowse", a.source, "facts-config.json"); cfg = json.load(open(cp, encoding="utf-8"))
        gone = notes["unmatched"]
        for name, fx in gone: cfg[name].remove(fx)
        if gone:
            cfg.setdefault(f"fixes_superseded_{a.prune_fixes}", []).extend([name, fx] for name, fx in gone)
            json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(gone)} fixes matching no line moved to «fixes_superseded_{a.prune_fixes}» in {os.path.relpath(cp, ROOT)}"); return
    for s in dict.fromkeys(notes["spent"]): print("  " + s[:200])
    if "--show-drops" in sys.argv:   # 2026-10-17: the duplicate and exact-repeat drops, each line whole, to check a row took only its line
        for l, why in notes["dropped"]:
            if "duplicate" in why or "exact repeat" in why: print(f"  DROPPED ({why[:60]}): {l}")
    out = os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md")
    tc = collections.Counter(x for r in rows for x in re.findall(r"\[(A|B|C|G|L|V|BIO|X|\?)\]", r[2].split(" · ")[-2]))
    print(f"{len(rows)} lines; dropped {dict(dropped)}; themes {dict(tc)}; unreadable lines {len(bad)}; "
          f"broken lines joined {len(notes['joined'])}; locator items written as their keys {notes.get('keyed', 0)}")
    for ret, head, tail in notes["joined"]: print(f"  JOINED in {ret}: «{head}» + «{tail}»")
    if notes.get("saying"): print("  dated by the saying («saying_dates»): " + ", ".join(f"{d} {n}" for d, n in sorted(notes["saying"].items())))
    if notes.get("saying_moved"):
        print("  the source's own «juĝo» dated by the matter, moved to the saying: " + ", ".join(f"{d} {n}" for d, n in sorted(notes["saying_moved"].items())))
    if notes.get("interpretdato"):
        print("  ⟦interpretdato⟧ on the source's own «interpreto»: " + ", ".join(f"{d} {n}" for d, n in sorted(notes["interpretdato"].items())))
    if notes.get("by_issue"):
        print("  «[sen dato]» by the issue («undated_by_issue»): " + ", ".join(f"{d} {n}" for d, n in sorted(notes["by_issue"].items())))
        for l in notes.get("by_issue_future", []): print(f"    LEFT, A VERB OR A DATE AHEAD: {l[:220]}")
        for w, n in notes.get("by_issue_words", collections.Counter()).most_common(): print(f"    from the words «{w}» ×{n}")
        nd = collections.Counter(notes.get("by_issue_nodate", []))
        if nd: print("    left, no issue date, at: " + "; ".join(f"{x} ×{n}" if n > 1 else x for x, n in nd.most_common(12)))
    if notes.get("interpretdato_derived"):
        print("  ⟦interpretdato⟧ on a derived author's «interpreto»: " + ", ".join(f"{d} {n}" for d, n in sorted(notes["interpretdato_derived"].items())))
    if notes.get("bare"): print("  NEWLY OUT BY --bare-cover (a qualified row, no namesake): " + ", ".join(f"{w} {n}" for w, n in sorted(notes["bare"].items())))
    elif BARE_COVER: print("  --bare-cover: no line newly out")
    uc = notes.get("unconfirmed")
    if uc:   # lines dropped on scope rows the editor has not confirmed (2026-10-15: «A … a failsafe for review»)
        rev = {w: n for (w, why), n in uc.items() if why == "review"}; brt = {w: n for (w, why), n in uc.items() if why == "plain"}
        if rev: print("  DROPPED ON UNCONFIRMED SCOPE ROWS, for the session's sign-off: " + ", ".join(f"{w} {n}" for w, n in sorted(rev.items())))
        if brt: print("  dropped on plain scope rows (a late joining or birth, no review needed): " + ", ".join(f"{w} {n}" for w, n in sorted(brt.items())))
    for b in bad: print("  UNREADABLE:", b[:200])
    k = notes.get("kun", [])
    if k:
        print(f"«kun:» and scope: {sum(1 for x in k if x[2] == 'rotated')} lines passed to a person in scope, "
              f"{sum(1 for x in k if x[2] == 'trimmed')} lists rid of someone out")
        for was, now, kw, rest in k:
            if kw == "rotated": print(f"  rotated: {was} → {now}: {re.search(r'\{[^}]*\}', rest).group(0)[:150]}")
    if not re.search(r"facts-format: [234]", text[:3000]): sys.exit("refusing: the header lacks «facts-format: 2», «3» or «4»")
    used_rl = sum(1 for rl in json.load(open(os.path.join(G, "dowse", a.source, "facts-config.json"), encoding="utf-8")).get("replace_lines", []))
    if used_rl: print(f"«replace_lines»: {used_rl} entries in the settings")
    if notes.get("redowsed"): print("«redowsed_pages»: " + "; ".join(f"{v} {k}" for k, v in notes["redowsed"].items()))
    sn = list(dict.fromkeys(notes.get("scope", [])))   # a line stripped before and after the interventions, once
    if sn:
        print(f"  scope notes taken off {len(sn)} lines ({sum(1 for x in sn if not x[4])} lost their ⚠ with them; "
              f"{sum(1 for x in sn if x[4])} keep a ⚠ for another doubt), for dowse/{a.source}/SCOPE-NOTES.tsv")
    if a.dry_run: return
    if sn:   # this tool's own output, remade on every assembly with the facts file
        open(os.path.join(G, "dowse", a.source, "SCOPE-NOTES.tsv"), "w", encoding="utf-8").write(
            "name\tqualifier\tthe scope note\tlocator\t⚠\n" + "".join("\t".join(x) + "\n" for x in sn))
    if notes.get("replace_unkeyed"):
        sys.exit(f"refusing: {len(notes['replace_unkeyed'])} «replace_lines» entries name no return (run --key-replace-lines)")
    if os.path.exists(out):
        if open(out, encoding="utf-8").read() == text: print("unchanged:", os.path.relpath(out, ROOT)); return
        if not a.replace: sys.exit(f"refusing to write over {os.path.relpath(out, ROOT)} without --replace")
        rel = os.path.relpath(out, ROOT)
        tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
        clean = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", "HEAD", "--", rel]).returncode == 0
        # a second pass over this tool's own output (same settings header) may overwrite it: git still holds the old file
        own = open(out, encoding="utf-8").read().startswith(text.split("\n\n- $$$")[0].rstrip("\n"))
        # a first dowse (P5, 2026-10-17 19:5x, Ruslanda Esperantisto): the file not yet in git, but this tool's own output
        # from the same settings, which rebuild it whole from the returns, may be rewritten by its own --replace
        if not ((tracked and (clean or own)) or (not tracked and own)):
            sys.exit(f"refusing: {rel} is not committed as it stands (commit it first; runbook D8)")
    open(out, "w", encoding="utf-8").write(text)
    print("wrote", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    main()
