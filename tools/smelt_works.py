#!/usr/bin/env python3
r"""smelt_works.py — «Verkoj laŭ la fontoj», a person's works as the frozen profile's lines record them, by tool (the
editor, 2026-10-30 12:2x; to Ezri's answer, a list of the works the sources mention, not a bibliography). No tokens.

The lines of the kind «verko» (wrote, translated, edited or signed a work; ocr/method/EVENT-KINDS-PROPOSAL-2026-10-13.md),
the main kind or a second («+verko: …»), grouped by the work's title as the kind's object gives it: case, accents, the
article and the punctuation folded, a tail «, traduko el X» or «, de X» read as the work translated from X. Each work: the
title in its most frequent form, «el X» where a line says so, the co-authors («kun: …»), the date of its first mention,
and every line, by L (tools/fact-labels.py writes them as labels). By the first mention's date; undated last. The same
work under two titles stays two entries («Ivano», later «Ludilo de sorto»); several works on one line stay one entry.

    import smelt_works; smelt_works.section(prof_lines, name) -> the section's lines (tools/smelt-s4-view.py)
Ezri, 2026-10-30."""
import re, sys, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FL
import smelt_inputs as SI

FROM = [re.compile(r"(?:traduko|tradukita|trad\.)\s+(?:el|de)\s+([^,;()«»]+)", re.I),
        re.compile(r"»\s+de\s+([^,;()«»]+)"), re.compile(r",\s*de\s+([^,;()«»]+)$"), re.compile(r"\(el\s+([^)]+)\)")]

def clean(obj, tr_line=False):
    """(title, translated from, a translation) of a «verko» object: the title inside «…» where the object quotes it
    («Boris Godunov» de Puŝkin, traduko, «Biblioteko» …: Boris Godunov), the tails «, traduko (el X)», «, de X», «(traduko
    el X)» read off (Devjatnin, the first run, 2026-10-30: «Demono, traduko», «Demono (traduko el Lermontov)», «Demono» de
    Lermontov, traduko» as four works)."""
    o = obj.strip()
    tr = tr_line or "traduk" in SI.fold(o)   # tr_line: the whole line's object says so, for one of its works
    # «traduko de «Boris Godunov», «traduko de Demono de Lermontov»: the work after the word
    o2 = re.sub(r"^(?:traduko|tradukoj)\s+(?:de|el)\s+", "", o)
    m = re.match(r"^«?([^«»]+?)»", o2) if "»" in o2 else None
    t = m.group(1) if m else o2.strip("«»“”\"' ")
    frm = next((x.group(1).strip() for rx in FROM[:1] + FROM[2:] for x in [rx.search(o)] if x), "")
    if m and not frm: frm = next((x.group(1).strip() for x in [FROM[1].search(o2)] if x), "")
    t = re.sub(r"\s*\((?:traduko|tradukita|el)\b[^)]*\)", "", t)
    t = re.sub(r",\s*(?:traduko|tradukita|trad\.|de\s).*$", "", t).strip(" ,«»")
    if tr:   # a translation's author after the title: «Demono (Lermontov)», «Boris Godunov de Puŝkin»
        a = re.search(r"\s*(?:\(([A-ZĈĜĤĴŜŬ][^)]*)\)|\s+de\s+([A-ZĈĜĤĴŜŬ][\w'-]+))$", t)
        if a: frm = frm or (a.group(1) or a.group(2)); t = t[:a.start()].strip()
    if frm and t and SI.fold(frm) == SI.fold(t): frm = ""
    return t, frm, bool(frm) or tr

def entries(prof):
    """[(title, from, co-authors, first date, [L])], from the frozen profile's lines (a list, line n at prof[n - 1])."""
    works = defaultdict(lambda: {"forms": Counter(), "from": Counter(), "kun": [], "dates": [], "L": []})
    for n, l in enumerate(prof, 1):
        if not l.startswith("- $$$"): continue
        f = FL.fields(l)
        if not f or "verko:" not in f["kind"]: continue
        parts = [p.strip() for p in f["kind"].strip("{}").split(";")]
        obj = next((p.split(":", 1)[1].strip() for p in parts if p.lstrip("+").startswith("verko:")), "")
        if not obj: continue
        kun = next((p.split(":", 1)[1].strip() for p in parts if p.startswith("kun:")), "")
        # ANOTHER'S WORK THAT NAMES THEM (the editor, 2026-10-30, on Midthus's obituaries as his works
        #): the harvest copies a line to every person its kind names in capitals,
        # the kind unchanged (harvest-facts.py), so Ekland's «verko: nekrologo de MIDTHUS»
        # reaches Midthus as «⟦kopio el EKLAND⟧». A co-author's copy names the person copied from in «kun:»; a copy that
        # does not is a work about them, not by them, and stays out of the list
        src = re.search(r"⟦kopio el ([^⟧(]+?)\s*(?:\(|⟧)", l)
        if src and SI.fold(src.group(1).strip()) not in SI.fold(kun): continue
        if any(p.startswith("far:") for p in parts): continue   # the harvest's mark since 2026-10-30, the same case
        # several works on one line, each closed by its author's bracket: «Hero kaj Leandro (Schiller) kaj Ruslan kaj
        # Ludmilo, traduko el Puŝkin» is two works (the editor, 2026-10-30, with «Hero kaj
        # Leandro» of another line); a «kaj» inside a title («Hero kaj Leandro») does not split
        segs = []
        for s in re.split(r"(?<=\))\s*(?:,|\bkaj\b)\s+", obj):
            # a bracket in a list of persons is no work's author: «kun portretoj de ZAMENHOF, TROMPETER (W. H.), DE
            # BEAUFRONT, LEMAIRE (René), MÉRAY kaj BOURLET» is one work (Bourlet's works reader, 2026-10-30, had to merge
            # the five pieces back); a piece opening with a surname in capitals stays with the one before
            if segs and re.match(r"(?:(?:DE|VAN|VON|LE|LA)\s+)?[A-ZĈĜĤĴŜŬÀ-Ý]{3,}\b", s): segs[-1] += ", " + s
            elif s.strip(): segs.append(s)
        _, frm_all, tr_all = clean(obj)
        for i, seg in enumerate(segs):
            base, frm, tr = clean(seg, tr_all)
            if len(segs) > 1 and not re.search(r"\([^)]*\)\s*$", seg.strip()):
                frm = frm_all if i == len(segs) - 1 else frm
            # the key: the title before its first comma («Edziĝo, komedio», «Edziĝo»), case, accents, the article folded
            key = re.sub(r"\b(?:la|l)\b", " ", re.sub(r"[^\w\s]", " ", SI.fold(base.split(",")[0])))
            key = re.sub(r"\s+", " ", key).strip()
            if not key: continue
            w = works[key]
            w["forms"][base] += 1
            if frm: w["from"][frm] += 1
            if tr: w["tr"] = True
            if kun and kun not in w["kun"]: w["kun"].append(kun)
            if f["date"]: w["dates"].append(f["date"])
            w["L"].append(n)
    def first(ds):
        dated = sorted(d for d in ds if re.match(r"\d{4}", d))
        return dated[0] if dated else ""
    out = [(w["forms"].most_common(1)[0][0], (w["from"].most_common(1)[0][0] if w["from"] else ("—" if w.get("tr") else "")), w["kun"], first(w["dates"]), w["L"], k, [])
           for k, w in works.items()]
    return sorted(out, key=lambda e: (e[3] == "", e[3], SI.fold(e[0])))

# THE WORKS READER (the editor, 2026-10-30,
# on joining a work's titles): the tool joins a work only under one folded title, so «Ruslano kaj Ludmilo», «Ruslan kaj
# Ludmilo» and stay three. A reader is given the tool's numbered list, never the lines, and names the
# numbers that are one work; the tool joins them, every line kept. For every person with a work (the editor, 2026-10-30,
# on Ezri's proposals of more than 20 works, or of two or more: even one).
MIN = 0
# SPLITTING (the editor, 2026-10-30, on Ezri's
# proposal: approved): «- 4 ÷ Sarantio | Libera homo | Maristoj | Husaro · why», each part words of
# the title as the list gives it (the tool refuses a part that is not), each part with all the entry's lines; a part
# merges as «4a», «4b», … The four persons read before splitting have a second pass, «-b», for the splits only.
MERGE = re.compile(r"^\s*[-*]?\s*(◊\?\s*)?(\d+[a-z]?(?:\s*=\s*\d+[a-z]?)+)\s*·\s*(.*?)\s*$", re.M)
SPLIT = re.compile(r"^\s*[-*]?\s*(◊\?\s*)?(\d+)\s*÷\s*(.+?)\s*·\s*(.*?)\s*$", re.M)

def files(d, tag, ps=""):
    return (os.path.join(d, f"WORKS-BRIEF-{tag}{ps}.md"), os.path.join(d, f"WORKS-LIST-{tag}.tsv"), os.path.join(d, f"WORKS-RETURN-{tag}{ps}.md"))

def listed(lp):
    """{n: (key, title)}, the list as the readers had it."""
    return {int(r[0]): (r[1], r[2]) for r in (l.split("\t") for l in open(lp, encoding="utf-8").read().splitlines()[1:]) if r[0].isdigit()}

def merges(d, tag):
    """([(keys, reason)], [(keys, reason)] uncertain, [problems], [(key, parts, reason)] splits) from WORKS-RETURN-<tag>.md
    and its second pass -b, the numbers read through WORKS-LIST-<tag>.tsv (the list as the reader had it), so a later
    change to the list's order cannot move a merge."""
    _, lp, rp = files(d, tag)
    rps = [p for p in (rp, files(d, tag, "-b")[2]) if os.path.exists(p)]
    if not rps: return [], [], [], []
    L = listed(lp)
    texts = [open(p, encoding="utf-8").read() for p in rps]
    sure, unsure, bad, splits, seen, parts_of = [], [], [], [], set(), {}
    for t in texts:
        for m in SPLIT.finditer(t):
            n, parts = int(m.group(2)), [p.strip(" «»") for p in m.group(3).split("|") if p.strip(" «»")]
            if n not in L: bad.append(f"{n} ÷: a number not in the list"); continue
            if n in parts_of: bad.append(f"{n} ÷: split twice"); continue
            if len(parts) < 2: bad.append(f"{n} ÷: fewer than two parts"); continue
            if any(SI.fold(p) not in SI.fold(L[n][1]) for p in parts): bad.append(f"{n} ÷ {' | '.join(parts)}: a part not in the title «{L[n][1]}»"); continue
            if m.group(1): unsure.append(([L[n][0]], f"÷ {' | '.join(parts)} · {m.group(4)}")); continue
            parts_of[n] = parts; splits.append((L[n][0], parts, m.group(4)))
    def ref(x):
        n, a = int(re.match(r"\d+", x).group()), x.lstrip("0123456789")
        if n not in L: return None
        if a: return f"{L[n][0]}#{a}" if n in parts_of and ord(a) - 97 < len(parts_of[n]) else None
        return None if n in parts_of else L[n][0]   # a split entry is named by its parts
    for t in texts:
        for m in MERGE.finditer(t):
            xs = re.findall(r"\d+[a-z]?", m.group(2))
            ks = [ref(x) for x in xs]
            if None in ks: bad.append(f"{m.group(2)}: a number not in the list, or a split entry named whole"); continue
            # an uncertain merge joins nothing, so it may name a number a merge has («- ◊? 27 = 28», the editor's ruling)
            if m.group(1): unsure.append((ks, m.group(3))); continue
            if seen & set(xs):
                # a part joining a merge already made («- 53 = 4b», the second pass): the group grows, its head stays
                hit = [g for g in sure if set(g[0]) & set(ks)]
                if m.group(1) or len(hit) != 1: bad.append(f"{m.group(2)}: a number already in another merge"); continue
                hit[0][0].extend(k for k in ks if k not in hit[0][0]); seen |= set(xs); continue
            seen |= set(xs)
            (unsure if m.group(1) else sure).append((ks, m.group(3)))
    return sure, unsure, bad, splits

def joined(es, sure, splits=()):
    """The entries with each split made several (each part with the entry's lines, date and co-authors), then each merge
    made one: the first number's title, the others' titles as «ankaŭ», the lines and the co-authors of all, the earliest
    date."""
    by = {e[5]: e for e in es}
    for k, parts, _ in splits:
        if k not in by: continue
        e = by.pop(k)
        for i, p in enumerate(parts):
            pk = f"{k}#{chr(97 + i)}"
            by[pk] = (p, e[1], e[2], e[3], e[4], pk, [])
    gone = set()
    for keys, _ in sure:
        ks = [k for k in keys if k in by]
        if len(ks) < 2: continue
        h = by[ks[0]]
        ds = sorted(by[k][3] for k in ks if by[k][3])
        frm = h[1] if h[1] not in ("", "—") else next((by[k][1] for k in ks if by[k][1] not in ("", "—")), h[1] or next((by[k][1] for k in ks if by[k][1]), ""))
        by[ks[0]] = (h[0], frm, list(dict.fromkeys(x for k in ks for x in by[k][2])), ds[0] if ds else "",
                     sorted(set(n for k in ks for n in by[k][4])), h[5], h[6] + [by[k][0] for k in ks[1:]])
        gone |= set(ks[1:])
    out = [e for k, e in by.items() if k not in gone]
    return sorted(out, key=lambda e: (e[3] == "", e[3], SI.fold(e[0])))

def section(prof, name, sure=(), splits=(), unsure=()):
    raw = entries(prof)
    es = joined(raw, sure, splits)
    if not es: return []
    # an uncertain merge shown as the conjecture it is (the editor, 2026-10-30, on Beauchemin's untitled «traduko»
    # merged into «La luphomo» on its month alone): «◊? eble la sama verko
    # kiel «…»» on every entry of the group but the first; an uncertain split «◊? eble pluraj verkoj»
    head = {}
    t_of = {e[5]: e[0] for e in raw + es}
    for ks, why in unsure:
        if why.startswith("÷"): head[ks[0]] = None; continue
        for k in ks[1:]: head.setdefault(k, t_of.get(ks[0], ks[0]))
    def eble(k):
        if k not in head: return []
        return ["◊? eble pluraj verkoj"] if head[k] is None else [f"◊? eble la sama verko kiel «{head[k]}»"]
    out = ["## Verkoj laŭ la fontoj", "",
           f"*La verkoj, kiujn la legitaj fontoj de La Genizo mencias kiel verkitajn, tradukitajn, redaktitajn aŭ subskribitajn de "
           f"{name}, laŭ la dato de la unua mencio: listo de ilo el la linioj de la profilo, ne kompleta bibliografio. La sama verko "
           f"sub du titoloj restas du eroj" + (", krom kie legilo trovis ilin la sama verko («ankaŭ»)" if sure else "") + ".*", ""]
    for t, frm, kun, d, ls, key, also in es:
        extra = "; ".join(x for x in ([("traduko" if frm == "—" else f"traduko el {frm}")] if frm else []) + [f"kun {k}" for k in kun]
                          + ([f"ankaŭ {', '.join(f'«{a}»' for a in dict.fromkeys(also))}"] if also else []) + eble(key))
        out.append(f"- **{t}**" + (f" ({extra})" if extra else "") + f": {'unue ' + d if d else 'sen dato'} [{', '.join(f'L{n}' for n in ls)}]")
    return out + [""]

BRIEF = """# La verkoj de {name}: la samaj verkoj sub pluraj titoloj ({tag})

`[Ezri, per tools/smelt_works.py brief {stem} {tag}: {n} verkoj el {nl} linioj de PROFILE-FROZEN-{tag}.md. La ilo kunigas verkon nur sub unu titolo; «Ruslan» kaj «Ruslano» ĝi lasas du.]`

## La briefo

Sube staras numerita listo de la verkoj, kiujn la legitaj fontoj de La Genizo mencias kiel verkitajn, tradukitajn, redaktitajn aŭ subskribitajn de {name}. Ilo faris ĝin el la linioj de la profilo: ĝi kunigis la erojn kun la sama titolo, sed ne tiujn, kies titolo estas alie skribita, kaj ĝi lasis en unu ero plurajn verkojn nomitajn en unu linio. {task}

Ĉe ĉiu ero: la titolo, kiel la fontoj ĝin plej ofte skribas; «traduko el X», kie linio diras, el kies verko ĝi estas tradukita; «kun Y», la kunaŭtoroj; la dato de la unua mencio; la nombro de linioj.
{rules}
Vi ne ŝanĝas titolojn, datojn nek liniojn: la ilo kunigas kaj dividas ilin. Vi nur nomas la numerojn kaj, ĉe divido, la partojn.

## La raporto

Skribu la novan dosieron `{ret}`, kun unu linio por ĉiu {lines}:
{report}
Via fina mesaĝo estas unu linio: `{final}`.
{done}
## La listo

{items}
"""

MERGE_RULES = """
Kunfandu du aŭ pli da eroj, kiam la listo mem montras, ke ili estas unu verko:
- alia literumo aŭ transskribo de la sama titolo (Ruslan / Ruslano; Boris / Boriso);
- la sama titolo en alia lingvo (la originala titolo kaj ĝia Esperanta traduko), kun la sama aŭtoro de la originalo, kie la listo nomas ĝin;
- la titolo kun aŭ sen subtitolo, ĝenro aŭ nomo de la aŭtoro («Edziĝo» / «Edziĝo, komedio»; «Demono» / «Demono de Lermontov»);
- preseraro aŭ eraro de la OCR en la titolo.

Ne kunfandu:
- du malsamajn verkojn de la sama aŭtoro aŭ kun similaj titoloj;
- parton kaj la tuton (unu poemo, unu akto aŭ unu ĉapitro, kaj la verko aŭ la kolekto);
- du titolojn de unu verko, kiam nur via scio, ne la listo, diras tion: tian kunfandon skribu kiel necertan.
"""

SPLIT_RULES = """
Dividu eron, kies titolo nomas plurajn verkojn («Sarantio, Libera homo, Maristoj, Husaro»: kvar poemoj). Ĉiu parto estas vortoj el la titolo, kiel ĝi staras en la listo, sen ŝanĝo (la ilo rifuzas parton, kiu ne staras en la titolo); ĉiu parto ricevas ĉiujn liniojn de la ero.

Ne dividu:
- unu verkon, kies titolo havas «kaj» aŭ komon («Hero kaj Leandro»; «Edziĝo, komedio»; «Fabeloj de I. A. Krilov»);
- priskribon de pluraj verkoj sen iliaj titoloj («tri tradukoj el Tolstoj», «diversaj versaĵoj»): ĝi restas unu ero.
"""

SPLIT_LINE = """
`- 4 ÷ Sarantio | Libera homo | Maristoj | Husaro · kial, per kelkaj vortoj`

La partoj laŭ la ordo de la titolo, apartigitaj per « | ». Necerta divido: `- ◊? 4 ÷ … · kial`; la ilo lasas la eron nedividita kaj montras ĝin al la redaktoro. Parto de dividita ero eniras kunfandon kiel 4a, 4b, … laŭ la ordo de la partoj (`- 57 = 4b · kial`); la dividitan eron mem ne plu nomu en kunfando.
"""

MERGE_LINE = """
`- 12 = 40 = 41 · kial, per kelkaj vortoj`

La unua numero estas la ero, kies titolo restas: la formo plej ofta en la Esperantaj fontoj aŭ, se tia ne estas, la plej plena. Necerta kunfando: `- ◊? 7 = 9 · kial`; la ilo lasas ĝin du eroj kaj montras ĝin al la redaktoro. Ĉiu numero aperas en unu kunfando plej multe.
"""

def item(i, e):
    t, frm, kun, d, ls = e[:5]
    extra = "; ".join(x for x in ([("traduko" if frm == "—" else f"traduko el {frm}")] if frm else []) + [f"kun {k}" for k in kun])
    return f"{i}. **{t}**" + (f" ({extra})" if extra else "") + f" · {'unue ' + d if d else 'sen dato'} · {len(ls)} {'linio' if len(ls) == 1 else 'linioj'}"

def main():
    """tools/smelt_works.py brief <stem> <tag> [--pass b]
            smelt/<stem>/WORKS-BRIEF-<tag>.md and WORKS-LIST-<tag>.tsv (create-only), for every person with a work: merges
            and splits; prints the reader's launch line. --pass b: WORKS-BRIEF-<tag>-b.md, for a person whose reader merged
            before splitting was built: the same list, the merges made shown, the splits asked (and a part's merges)
       tools/smelt_works.py check <stem> <tag>
            the readers' merges and splits, each with its titles, and what the list becomes"""
    a = [x for x in sys.argv[1:] if x not in ("--pass", "b")]
    ps = "-b" if "--pass" in sys.argv else ""
    if len(a) != 3 or a[0] not in ("brief", "check"): sys.exit(main.__doc__)
    cmd, stem, tag = a
    G = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "published", "heterophony-resources", "geniza")
    d = os.path.join(G, "smelt", stem)
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
    es = entries(prof)
    bp, lp, rp = files(d, tag, ps)
    if cmd == "brief":
        if len(es) <= MIN: print(f"{stem}: {len(es)} works, no reader"); return
        for p in (bp,) + (() if ps else (lp,)):
            if os.path.exists(p): sys.exit(f"{os.path.relpath(p, G)} exists: not overwritten")
        # the name as the biography gives it («# La biografio de Vasilij Devjatnin (smelt S4 …»), else the profile's head
        rt = os.path.join(d, f"S4-RETURN-{tag}.md")
        m = re.match(r"# La biografio de (.*?) \(smelt S4", open(rt, encoding="utf-8").read(300)) if os.path.exists(rt) else None
        nm = m.group(1) if m else re.sub(r"^#\s+|\s+—.*$", "", prof[0]).strip() or stem
        if ps:
            # the second pass keeps the first pass's numbers; an entry the tool no longer makes is left out, an entry with
            # no number stops it
            by = {e[5]: e for e in es}
            new = [e[0] for e in es if e[5] not in {k for k, _ in listed(lp).values()}]
            if new: sys.exit(f"{os.path.basename(lp)}: {len(new)} entries not in the first pass's list: " + "; ".join(new))
            numbered = [(n, by[k]) for n, (k, _) in listed(lp).items() if k in by]
            sure, _, _, _ = merges(d, tag)
            L = {k: (n, t) for n, (k, t) in listed(lp).items()}
            done = "\n## La faritaj kunfandoj\n\n" + ("\n".join("- " + " = ".join(f"{L[k][0]} «{L[k][1]}»" for k in ks) for ks, _ in sure) or "- neniu") + "\n"
            f = dict(task="Antaŭa legilo jam trovis la erojn, kiuj estas unu verko (sube, «La faritaj kunfandoj»); ne refaru ilin. Via tasko: "
                          "dividi la erojn, kiuj nomas plurajn verkojn, kaj kunfandi parton de dividita ero kun alia ero, kiam ili estas unu verko.",
                     rules=SPLIT_RULES + "\nPor la kunfando de parto validas tio ĉi:\n" + MERGE_RULES, lines="divido kaj ĉiu nova kunfando",
                     report=SPLIT_LINE + "\nNova kunfando, nur kun parto de dividita ero; parto, kiu aliĝas al farita kunfando, nomas unu ĝian numeron (`- 53 = 4b`):\n"
                            + MERGE_LINE + "\nSe estas neniu divido, skribu nur la linion `- neniu`.\n",
                     final="<K> dividoj, <N> kunfandoj, <M> necertaj", done=done)
        else:
            numbered = list(enumerate(es, 1))
            open(lp, "x", encoding="utf-8").write("n\tkey\ttitle\n" + "".join(f"{i}\t{e[5]}\t{e[0]}\n" for i, e in enumerate(es, 1)))
            f = dict(task="Via tasko: trovi la erojn, kiuj estas unu verko, kaj dividi la erojn, kiuj nomas plurajn verkojn.",
                     rules=MERGE_RULES + SPLIT_RULES, lines="kunfando kaj ĉiu divido",
                     report=MERGE_LINE + SPLIT_LINE + "\nSe estas nek kunfando nek divido, skribu nur la linion `- neniu`.\n",
                     final="<N> kunfandoj, <M> necertaj, <K> dividoj", done="")
        open(bp, "x", encoding="utf-8").write(BRIEF.format(name=nm, tag=tag, stem=stem, n=len(es), nl=sum(len(e[4]) for e in es), ret=rp,
                                                           items="\n".join(item(i, e) for i, e in numbered), **f))
        print(f"wrote {os.path.relpath(bp, G)} ({os.path.getsize(bp):,} bytes)" + ("" if ps else f" and {os.path.basename(lp)}") + f": {len(es)} works")
        print(f"launch (file-reader-writer): Read the brief {bp} and carry out the task it gives, section «La briefo». "
              f"Your final message is the line the brief asks for.")
        return
    sure, unsure, bad, splits = merges(d, tag)
    L = {k: (n, t) for n, (k, t) in listed(lp).items()}
    for k, parts, _ in splits:
        for i, p in enumerate(parts): L[f"{k}#{chr(97 + i)}"] = (f"{L[k][0]}{chr(97 + i)}", p)
    print(f"{os.path.relpath(files(d, tag)[2], G)} (and -b): {len(splits)} splits, {len(sure)} merges, {len(unsure)} uncertain, {len(bad)} refused")
    for k, parts, why in splits:
        print(f"  split: {L[k][0]} «{L[k][1]}» ÷ " + " | ".join(parts) + f" · {why}")
    for lab, ms in (("merge", sure), ("uncertain, left apart", unsure)):
        for keys, why in ms:
            print(f"  {lab}: " + " = ".join(f"{L.get(k, ('?', k))[0]} «{L.get(k, ('?', k))[1]}»" for k in keys) + f" · {why}")
    for b in bad: print(f"  refused: {b}")
    keys, now = {k for k, _ in listed(lp).values()}, {e[5] for e in es}
    print(f"the list: {len(es)} works, {len(joined(es, sure, splits))} after the splits and merges; against {os.path.basename(lp)}: "
          f"{len(keys - now)} numbers the tool no longer makes, {len(now - keys)} entries with no number")
    for n, (k, t) in listed(lp).items():
        if k not in now: print(f"  no longer made: {n} «{t}»")

if __name__ == "__main__":
    main()
