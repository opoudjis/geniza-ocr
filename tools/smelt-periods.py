#!/usr/bin/env python3
"""Smelt S3 in periods, for a profile too large for one episode reader (the smelt runbook, S3, «A reader's limit», the
second lever; the editor, 2026-10-17 12:3x).

    tools/smelt-periods.py <stem> <tag> [--target 150] [--dry-run]   the period inputs and briefs
    tools/smelt-periods.py <stem> <tag> --general                   the last part's brief, after the period returns
    tools/smelt-periods.py <stem> <tag> --join                      the parts' returns joined as S3-RETURN-<tag>.md

Run after `smelt-s2-prep.py <tag> <stem>=<NAME> --episodes --kinded-only`, on its S3-INPUT, S3-SINGLES and S3-BRIEF.
The design agreed 2026-10-16 (the runbook, S3): the tool's groups are formed over the whole profile first and never cut;
each item (G, U, K, N) goes to the period of its earliest dated line (a guess counts: «divene ≥ 1920»); a line in no
group, to the period of its own date; periods are cut between years, at about --target lines each. Each period's reader
also sees, read-only, the lines of other periods dated within a year of its edges or inside it (a span that began
before): it cites them as circumstances, never groups them, never opens an episode with them. Items with no usable date
(«[ĝenerala]», «[sen dato]» without a guess) go to a general part, read last, with the period readers' episode titles
(--general). Numbers: part k numbers its episodes from E(100k+1) and its new groups from G(1000k+1); the general part
from E901 and G9001; the tool's G and U keep theirs. Writes S3-INPUT-<tag>-p<k>.md, S3-BRIEF-<tag>-p<k>.md (k = 1…,
and «g»); refuses a part whose return is filed. --join writes S3-RETURN-<tag>.md, create-only, each of the five
sections the parts' in order, so that smelt-view.py and the S4 brief read it as one return. Ezri, 2026-10-17."""
import argparse, os, re, sys
import smelt_parts    # the three parts, for --s4-gist (2026-10-22)
ROOT =os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
YEAR = re.compile(r"\b(1[6-9]\d\d|20\d\d)\b")
ITEM = re.compile(r"^- \*\*([GUKN])(\d+)\*\*")
REF = re.compile(r"\bL(\d+)\b")

_SRC = {}
def source_year(l):
    """The year of the line's source, from the harvest's own source_info (cached)."""
    if not _SRC:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hf", os.path.join(ROOT, "tools", "harvest-facts.py"))
        m = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]
        try: spec.loader.exec_module(m)
        finally: sys.argv = saved
        _SRC["hf"] = m
    ps = l.split(" · ")
    loc = next((p for p in ps if re.search(r", (?:PDF|¶|p\.) ?\d", p)), "")
    try: return _SRC["hf"].source_info(loc)[1] if loc else None
    except Exception: return None

def line_year(l):
    """The year that places a profile line in a period: its date, or the lower end of its guess; None for «[ĝenerala]»,
    no year, an upper bound alone («≤ 1998»: it places nothing), or a page guess that is only the source's own year
    (2026-10-17, De Beaufront part 3: Jossinet's lines on 1890s acts guessed «≤ 1998», «ĉ. 1998 laŭ la paĝo» from his own
    judgements dated 1998 beside them, and so read in the period 1959–2022)."""
    m = re.match(r"^- \$\$\$ .*? \$\$\$(?: \([^)]*\))? (.*?) · ", l)
    if not m or "ĝenerala" in m.group(1): return None
    d = m.group(1)
    if "divene" in d:
        lo = [int(y) for y in re.findall(r"(?:≥|ĉ\.)\s*(\d{4})", d)]
        bare = re.search(r"divene (\d{4})\b", d)
        if bare: lo.append(int(bare.group(1)))
        if not lo: return None
        if "laŭ la paĝo" in d and set(int(y) for y in YEAR.findall(d)) == {source_year(l)}: return None
        return min(lo)
    ys = [int(y) for y in YEAR.findall(d)]
    return min(ys) if ys else None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stem"); ap.add_argument("tag")
    ap.add_argument("--target", type=int, default=150); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--general", action="store_true"); ap.add_argument("--join", action="store_true")
    ap.add_argument("--bounds", help="the periods as «1855-1904,1905-1950,…», to keep an earlier split")
    ap.add_argument("--only", help="write only these parts («3,g»): the others stand as read")
    ap.add_argument("--s4", action="store_true", help="S4 in periods: a writer's brief for each part, after all the parts' S3 returns")
    ap.add_argument("--name", help="with --s4: the person as the biography names them («Louis de Beaufront»)")
    ap.add_argument("--s4-summary", action="store_true", help="the brief for the abstract, from the sections' summaries, after the parts' S4 returns")
    ap.add_argument("--s4-join", action="store_true", help="the parts' S4 returns and the abstract joined as S4-RETURN-<tag>.md")
    ap.add_argument("--again", action="store_true", help="with --s4-summary: a second abstract's brief, -ps2, where the first is filed")
    ap.add_argument("--s4-abstract", action="store_true", help="the second abstract (-ps2) in place of the first in S4-RETURN-<tag>.md")
    ap.add_argument("--s4-gist", action="store_true", help="the brief for the gist biography, from the sections' summaries in their parts")
    a = ap.parse_args()
    d = os.path.join(G, "smelt", a.stem)
    if a.s4:
        if not a.name: sys.exit("refusing: --s4 needs --name")
        return s4(d, a.stem, a.tag, a.name)
    if a.s4_summary: return s4_summary(d, a.tag, a.again)
    if a.s4_abstract: return s4_abstract(d, a.tag)
    if a.s4_gist: return s4_gist(d, a.tag)
    if a.s4_join: return s4_join(d, a.tag)
    if a.join: return join(d, a.tag)
    if a.general: return general(d, a.tag)
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md"), encoding="utf-8").read().split("\n")
    year = {i + 1: line_year(l) for i, l in enumerate(prof) if l.startswith("- $$$")}
    inp = open(os.path.join(d, f"S3-INPUT-{a.tag}.md"), encoding="utf-8").read().split("\n")
    brief = open(os.path.join(d, f"S3-BRIEF-{a.tag}.md"), encoding="utf-8").read()
    items, loose, sec = [], [], ""
    for l in inp:
        if l.startswith("## "): sec = l
        m = ITEM.match(l)
        if m: items.append((sec, l, [int(x) for x in REF.findall(l)]))
        elif sec.startswith("## The lines in no group") and REF.search(l): loose += [int(x) for x in REF.findall(l)]
    # each item's year: its earliest dated line; a loose line, its own
    units = [(min((year[n] for n in ns if year.get(n)), default=None), sec, l, ns) for sec, l, ns in items]
    units += [(year.get(n), "## The lines in no group", f"L{n}", [n]) for n in loose]
    dated = sorted((u for u in units if u[0] is not None), key=lambda u: u[0])
    undated = [u for u in units if u[0] is None]
    # periods cut between years, at about --target lines
    years = sorted({u[0] for u in dated}); per_year = {y: set() for y in years}
    for u in dated: per_year[u[0]].update(u[3])
    periods, cur, n = [], [], 0
    for y in years:
        if cur and n + len(per_year[y]) > a.target: periods.append((cur[0], cur[-1])); cur, n = [], 0
        cur.append(y); n += len(per_year[y])
    if cur: periods.append((cur[0], cur[-1]))
    if a.bounds:   # the periods of an earlier split, kept (a part re-split while the others stand)
        periods = [tuple(int(x) for x in b.split("-")) for b in a.bounds.split(",")]
        lost = [u for u in dated if not any(lo <= u[0] <= hi for lo, hi in periods)]
        if lost: sys.exit(f"refusing: {len(lost)} items fall in no period of --bounds (first: {lost[0][2][:80]})")
    parts = [(str(k), lo, hi, [u for u in dated if lo <= u[0] <= hi]) for k, (lo, hi) in enumerate(periods, 1)]
    parts.append(("g", None, None, undated))
    total = len(year)
    only = set(a.only.split(",")) if a.only else None
    for k, lo, hi, us in parts:
        if only and k not in only:   # a part that stands: its items must be the same as when it was written
            p = os.path.join(d, f"S3-INPUT-{a.tag}-p{k}.md")
            had = {l for l in open(p, encoding="utf-8").read().split("\n") if l.startswith("- ")} if os.path.exists(p) else set()
            now_ = {u[2] if u[2].startswith("- ") else f"- {u[2]}" for u in us}
            if now_ - had: sys.exit(f"refusing: part {k} would gain {len(now_ - had)} items it was not given (first: {sorted(now_ - had)[0][:80]}); it cannot stand")
            print(f"part {k}: stands ({len(had - now_)} of its items now go elsewhere)"); continue
        if os.path.exists(os.path.join(d, f"S3-RETURN-{a.tag}-p{k}.md")): sys.exit(f"refusing: S3-RETURN-{a.tag}-p{k}.md is filed")
        own = sorted({x for u in us for x in u[3]})
        ro = [] if k == "g" else sorted(x for x, y in year.items() if y is not None and lo - 1 <= y <= hi + 1 and x not in own)
        out = [f"# S3, part {k} of {a.stem} ({a.tag}): " + (f"the period {lo}–{hi}" if lo else "the lines with no usable date"), "",
               f"`[tools/smelt-periods.py from S3-INPUT-{a.tag}.md: {len(us)} items, {len(own)} lines of {total}; "
               f"{len(ro)} lines of the neighbouring periods to read only. L = the line's number in PROFILE-FROZEN-{a.tag}.md.]`", ""]
        last = None
        for u in us:
            if u[1] != last: out += ["", u[1], ""]; last = u[1]
            out.append(u[2] if u[2].startswith("- ") else f"- {u[2]}")
        out += ["", "## The lines to read only (another period's; cite them as circumstances, never group them)", "",
                ", ".join(f"L{x}" for x in ro) or "(none)"]
        if k == "g":
            para = (f"\n\n**Via parto: la linioj sen uzebla dato** (la smelt-gvidlibro, S3, «A reader's limit», la dua levilo; la "
                    f"redaktoro, 2026-10-17: «build reading by periods»). La profilo estas tro granda por unu legilo, do ĝi estas "
                    f"legata en periodoj; vi legas laste nur la erojn sen uzebla dato («[ĝenerala]», «[sen dato]» sen diveno, diveno "
                    f"nur «≤ …», aŭ diveno laŭ la paĝo, kiu estas nur la jaro de la fonto mem). La daŭraj iras en temajn erojn, laŭ "
                    f"la regulo pri «[ĝenerala]». Ago, kies dato vi povas konkludi el aliaj linioj (∴), iras en la epizodon de "
                    f"sia periodo per «vidu E…» kaj la ∴-dato; se neniu epizodo taŭgas, skribu propran, kun la ∴-dato. La epizodoj de la periodoj, jam skribitaj de aliaj "
                    f"legiloj, estas listigitaj sube: kie via ero apartenas al unu el ili, skribu «vidu E…», ne reskribu ĝin. "
                    f"**Numerado:** viaj epizodoj de E901, viaj novaj grupoj de G9001; la grupoj de la ilo (G…) kaj la unuopaj U "
                    f"tenas siajn numerojn.\n\n**La epizodoj de la periodoj:** (skribitaj de `--general`, post la revenoj de la periodoj)\n")
        else:
            ki = int(k)
            para = (f"\n\n**Via parto: la periodo {lo}–{hi}** (la smelt-gvidlibro, S3, «A reader's limit», la dua levilo; la "
                    f"redaktoro, 2026-10-17: «build reading by periods»). La profilo estas tro granda por unu legilo, do ĝi estas "
                    f"legata en periodoj. Via enigo donas nur la grupojn, kandidatojn, nomumojn kaj unuopajn U, kies plej frua "
                    f"datita linio falas en {lo}–{hi}, kaj la liniojn sen grupo de tiuj jaroj; la aliajn periodojn legas aliaj "
                    f"legiloj, kaj la erojn sen uzebla dato fina legilo. **Nur por legi:** la linioj sub «The lines to read only» "
                    f"de via enigo apartenas al alia periodo (ĝis unu jaro de viaj limoj): citu ilin kiel cirkonstancojn, sed ne "
                    f"metu ilin en grupon kaj ne komencu epizodon per ili. Daŭron, kiu komenciĝis en via periodo, rekonstruu ĝis "
                    f"ĝia fino, kiel la linioj permesas; daŭron, kiu komenciĝis antaŭe, ne. **Numerado:** viaj epizodoj de "
                    f"E{100 * ki + 1}, viaj novaj grupoj de G{1000 * ki + 1}; la grupoj de la ilo (G…) kaj la unuopaj U tenas siajn "
                    f"numerojn.\n")
        b = brief.replace(f"S3-INPUT-{a.tag}.md", f"S3-INPUT-{a.tag}-p{k}.md")
        if b == brief: sys.exit(f"refusing: S3-BRIEF-{a.tag}.md does not name S3-INPUT-{a.tag}.md")
        b = b.replace("\nFinu la mesaĝon per la linio", para + "\nFinu la mesaĝon per la linio", 1)
        print(f"part {k}: " + (f"{lo}–{hi}" if lo else "no usable date") + f", {len(us)} items, {len(own)} lines, {len(ro)} to read only" + (" (dry run)" if a.dry_run else ""))
        if a.dry_run: continue
        open(os.path.join(d, f"S3-INPUT-{a.tag}-p{k}.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
        open(os.path.join(d, f"S3-BRIEF-{a.tag}-p{k}.md"), "w", encoding="utf-8").write(b)

def period_parts(d, tag):
    return sorted((f for f in os.listdir(d) if re.fullmatch(rf"S3-RETURN-{re.escape(tag)}-p\d+\.md", f)), key=lambda f: int(re.search(r"-p(\d+)\.md$", f).group(1)))

def general(d, tag):
    briefs = sorted(f for f in os.listdir(d) if re.fullmatch(rf"S3-BRIEF-{re.escape(tag)}-p\d+\.md", f))
    rets = period_parts(d, tag)
    if len(rets) != len(briefs): sys.exit(f"refusing: {len(rets)} period returns filed of {len(briefs)}")
    heads = [l.split(" · ")[0] + " · " + (l.split(" · ")[1] if " · " in l else "")
             for f in rets for l in open(os.path.join(d, f), encoding="utf-8") if re.match(r"^(?:- )?\**E\d+\**(?: \([^)]*\))?:", l)]  # 2026-10-19: «- E301:» (19c p3) was missed
    p = os.path.join(d, f"S3-BRIEF-{tag}-pg.md"); b = open(p, encoding="utf-8").read()
    mark = "(skribitaj de `--general`, post la revenoj de la periodoj)\n"
    if mark not in b: sys.exit("refusing: the general brief has its episode list already")
    open(p, "w", encoding="utf-8").write(b.replace(mark, "\n" + "\n".join(f"- {h.strip().removeprefix('- ')}" for h in heads) + "\n"))
    print(f"S3-BRIEF-{tag}-pg.md: {len(heads)} episode titles from {len(rets)} period returns")

def join(d, tag):
    out_p = os.path.join(d, f"S3-RETURN-{tag}.md")
    if os.path.exists(out_p): sys.exit(f"refusing: S3-RETURN-{tag}.md exists")
    files = period_parts(d, tag) + ([f"S3-RETURN-{tag}-pg.md"] if os.path.exists(os.path.join(d, f"S3-RETURN-{tag}-pg.md")) else [])
    if not files: sys.exit("refusing: no part returns filed")
    secs, pre, ne, ng = {k: [] for k in "12345"}, [], 0, 0
    for f in files:
        cur = None
        for l in open(os.path.join(d, f), encoding="utf-8").read().split("\n"):
            m = re.match(r"^## ([1-5])\.", l)
            if m: cur = m.group(1); continue
            if l.startswith("Fino:"):
                mm = re.search(r"(\d+) epizodoj, (\d+) grupoj", l)
                if mm: ne += int(mm.group(1)); ng += int(mm.group(2))
                continue
            if cur: secs[cur].append(l)
            elif l.strip() and not l.startswith("# "): pre.append(l)
    names = {"1": "La epizodoj", "2": "La grupoj", "3": "La kandidatoj kaj la nomumoj", "4": "La linioj en neniu grupo", "5": "La faŭltoj de la linioj"}
    body = [f"# S3, joined from {len(files)} parts ({', '.join(files)})", "", "`[tools/smelt-periods.py --join]`", ""] + pre
    for k in "12345":
        body += ["", f"## {k}. {names[k]}", ""] + [l for l in secs[k] if l.strip()]
    body += ["", f"Fino: {ne} epizodoj, {ng} grupoj."]
    with open(out_p, "x", encoding="utf-8") as fh: fh.write("\n".join(body) + "\n")
    print(f"S3-RETURN-{tag}.md: {len(files)} parts, {ne} episodes, {ng} groups")

# S4 in periods (the runbook, S3, «A reader's limit»: «S4 in periods too, one writer per period from the joined S3, then
# the summary from the period summaries»; the editor, 2026-10-17 22:2x).
# Each part's writer reads only its part's S3 return and an excerpt of the profile and of the single-line groups (the
# lines its S3 input and return cite), so that no writer reads the whole profile; the undated part writes the thematic
# sections and «Kie troviĝas la fontoj» from every part's «La arkivo»; a last reader writes the abstract from the sections'
# summaries; --s4-join puts them together in the form of one S4 return, for smelt-s4-view.py, smelt-view.py and S5.
FORM_TAIL = ("poste `### La malfermitaj konfliktoj` kaj `### Notoj pri malgravaj malkongruoj`, nur pri via parto, kun «—» se "
             "malplenaj; poste `## 2. Epizodoj kaj linioj ne uzitaj, kaj kial` (kun `### Juĝoj ne uzitaj`), `## 3. Foriroj de la "
             "grupoj aŭ epizodoj, kaj kial`, `## 4. Malklaraĵoj kaj faŭltoj de la profilo; proponoj por la registro`; kaj la "
             "linio «Fino.».")
EXCERPT = ("**Via profilo estas eltiraĵo:** nur la linioj, kiujn via parto citas, ĉiu kun sia L-numero antaŭe, la numero en la "
           "tuta frosta profilo; citu per tiuj numeroj. Same la unuopaj grupoj: nur tiuj, kiujn via parto citas.")

def part_keys(d, tag):
    """The parts as S3 briefed them: 1…n, then g."""
    ks = [re.search(r"-p(\d+)\.md$", f).group(1) for f in os.listdir(d) if re.fullmatch(rf"S3-BRIEF-{re.escape(tag)}-p\d+\.md", f)]
    return sorted(ks, key=int) + ["g"]

def span(d, tag, k):
    m = re.search(r"the period (\d+)–(\d+)", open(os.path.join(d, f"S3-INPUT-{tag}-p{k}.md"), encoding="utf-8").readline())
    return (m.group(1), m.group(2)) if m else None

def s4(d, stem, tag, name):
    rd = lambda f: open(os.path.join(d, f), encoding="utf-8").read()
    ks = part_keys(d, tag)
    miss = [k for k in ks if not os.path.exists(os.path.join(d, f"S3-RETURN-{tag}-p{k}.md"))]
    if miss: sys.exit(f"refusing: the S3 returns of parts {', '.join(miss)} are not filed")
    frozen = os.path.join(d, f"PROFILE-FROZEN-{tag}.md")
    lines = {i + 1: l for i, l in enumerate(rd(f"PROFILE-FROZEN-{tag}.md").split("\n")) if l.startswith("- $$$")}
    singles = {int(m.group(1)): l for l in rd(f"S3-SINGLES-{tag}.md").split("\n") for m in [re.match(r"^U(\d+): ", l)] if m}
    arkivo = [(k, l.strip()) for k in ks for l in rd(f"S3-RETURN-{tag}-p{k}.md").split("\n") if re.match(r"^(?:- )?\**E\d+\**: La arkivo\b", l)]
    # the lines of every item and episode by its number, from the whole S3 input and all the parts' returns: a part that
    # names a tool group («G4») or another part's episode («vidu E228») gets its lines too (2026-10-17u, De Beaufront
    # B52, B53: G4 of «La arkivo» and E228, E216 came without their lines)
    by_id = {}
    for l in rd(f"S3-INPUT-{tag}.md").split("\n") + [x for k in ks for x in rd(f"S3-RETURN-{tag}-p{k}.md").split("\n")]:
        m = re.match(r"^(?:- )?\**([GUKNE]\d+)\**[:·\s]", l)
        if m: by_id.setdefault(m.group(1), set()).update(int(x) for x in REF.findall(l))
    import importlib.util
    spec = importlib.util.spec_from_file_location("s2", os.path.join(ROOT, "tools", "smelt-s2-prep.py"))
    s2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s2)
    for k in ks:
        if os.path.exists(os.path.join(d, f"S4-RETURN-{tag}-p{k}.md")): sys.exit(f"refusing: S4-RETURN-{tag}-p{k}.md is filed")
        ret = f"S3-RETURN-{tag}-p{k}.md"
        text = rd(ret) + "\n" + rd(f"S3-INPUT-{tag}-p{k}.md") + ("\n" + "\n".join(l for _, l in arkivo) if k == "g" else "")
        us = sorted({int(x) for x in re.findall(r"\bU(\d+)\b", text) if int(x) in singles})
        named = {n for i in re.findall(r"\b([GKNE]\d+)\b", text) for n in by_id.get(i, ())}
        ls = sorted({int(x) for x in REF.findall(text + "\n" + "\n".join(singles[u] for u in us)) if int(x) in lines} | (named & set(lines)))
        sp = span(d, tag, k) if k != "g" else None
        what = f"the period {sp[0]}–{sp[1]}" if sp else "the lines with no usable date, and every part's «La arkivo»"
        lp, up = os.path.join(d, f"S4-LINES-{tag}-p{k}.md"), os.path.join(d, f"S4-SINGLES-{tag}-p{k}.md")
        open(lp, "w", encoding="utf-8").write(
            f"# S4, part {k} of {stem} ({tag}): the profile's lines for {what}\n\n`[tools/smelt-periods.py --s4: the {len(ls)} lines "
            f"of PROFILE-FROZEN-{tag}.md that S3-INPUT-{tag}-p{k}.md and {ret} cite, directly or by their single-line groups; "
            f"each headed by its L, its number in the whole frozen profile.]`\n\n" + "\n".join(f"L{n}: {lines[n]}" for n in ls) + "\n")
        open(up, "w", encoding="utf-8").write(
            f"# S4, part {k} of {stem} ({tag}): the single-line groups it cites\n\n`[tools/smelt-periods.py --s4, from "
            f"S3-SINGLES-{tag}.md: {len(us)} of {len(singles)}.]`\n\n" + "\n".join(singles[u] for u in us) + "\n")
        b, _, _ = s2.s4_body(stem, name, frozen, lp, os.path.join(d, ret), up)
        why = "(la smelt-gvidlibro, S4 en periodoj; la redaktoro, 2026-10-17)"
        if sp:
            para = (f"\n\n**Via parto: la periodo {sp[0]}–{sp[1]}** {why}. La biografio estas tro granda por unu verkanto, do ĝi estas "
                    f"verkata en partoj: vi verkas nur la sekciojn de la periodo {sp[0]}–{sp[1]}, el la epizodoj kaj grupoj de via "
                    f"parto. Aliaj verkantoj verkas la aliajn periodojn kaj la temajn sekciojn (la eroj sen uzebla dato, kun «Kie "
                    f"troviĝas la fontoj»); la ĝenerala resumo estas verkata poste, el la resumoj de la sekcioj. {EXCERPT} Linio, kiun "
                    f"via epizoda legilo havis «nur por legi», estas cirkonstanco, ne fakto de via sekcio. **Ne verku** la ĝeneralan "
                    f"resumon, la linion de ŝlosilo, nek «Kie troviĝas la fontoj». **Ĉiu sekcio komenciĝas per sia resumo de la "
                    f"periodo** (la biografio estas longa). **La formo de via raporto, ĝuste ĉi tiu, ĉar ilo kunmetas la partojn:** "
                    f"`## 1. La biografio de la periodo`; por ĉiu sekcio `### Titolo (jaroj)`, sen numero, kun la kursiva resumo, la "
                    f"alineoj kaj la notoj; {FORM_TAIL}")
        else:
            para = (f"\n\n**Via parto: la temaj sekcioj** {why}. La biografio estas tro granda por unu verkanto, do ĝi estas verkata "
                    f"en partoj: aliaj verkantoj verkas la sekciojn de la periodoj; vi verkas (a) la temajn sekciojn, el la epizodoj kaj "
                    f"grupoj de via parto, la eroj sen uzebla dato (laŭ la regulo pri «[ĝenerala]»: portreto, deveno, verkoj kaj "
                    f"similaj), kaj (b) la sekcion «Kie troviĝas la fontoj», el ĉiuj eroj «La arkivo» de la partoj, listigitaj sube. "
                    f"Kie via epizodo diras «vidu E…» de alia periodo, la fakto apartenas al tiu periodo: ne reverku ĝin. La ĝenerala "
                    f"resumo estas verkata poste, el la resumoj de la sekcioj. {EXCERPT} **Ne verku** la ĝeneralan resumon nek la linion "
                    f"de ŝlosilo. **Ĉiu tema sekcio komenciĝas per sia kursiva resumo**, kiel la sekcioj de la periodoj. **La formo de "
                    f"via raporto, ĝuste ĉi tiu, ĉar ilo kunmetas la partojn:** `## 1. La temaj sekcioj`; por ĉiu sekcio `### Titolo`, "
                    f"sen numero, kun la kursiva resumo, la alineoj kaj la notoj; poste `### Kie troviĝas la fontoj`; {FORM_TAIL}"
                    f"\n\n**La eroj «La arkivo» de la partoj:**\n\n" + "\n".join(f"- (parto {pk}) {l}" for pk, l in arkivo))
        if "\n**La raporto:**" not in b: sys.exit("refusing: the S4 template has no «**La raporto:**»")
        b = b.replace("\n**La raporto:**", para + "\n\n**La raporto:**", 1)
        head = (f"# La biografio de {name} (smelt S4, {tag}, part {k})\n\n`[tools/smelt-periods.py --s4, from "
                f"ocr/method/BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md on {ret}, S4-LINES-{tag}-p{k}.md and S4-SINGLES-{tag}-p{k}.md.]`\n\n")
        open(os.path.join(d, f"S4-BRIEF-{tag}-p{k}.md"), "w", encoding="utf-8").write(head + b)
        print(f"part {k}: {what}; {len(ls)} lines, {len(us)} single-line groups → S4-BRIEF-{tag}-p{k}.md")

def s4_parse(text):
    """A part's S4 return in pieces: its sections [(title, lines)], and the blocks for the joined return."""
    out = {k: [] for k in ("secs", "kie", "conf", "disc", "r2", "jug", "r3", "r4", "stray")}
    top, cur = None, None
    for l in text.split("\n"):
        m = re.match(r"^## \(?([1-4])[.)]", l)   # «## 4.» or «## (4)»: the writers use both
        if m: top = m.group(1); cur = {"1": "stray", "2": "r2", "3": "r3", "4": "r4"}[top]; continue
        if top is None or l.strip() == "Fino.": continue
        h = re.match(r"^### (?:\d+\.\s*)?(.*?)\s*$", l)
        if h and top == "1":
            t = h.group(1)
            cur = {"Kie troviĝas la fontoj": "kie", "La malfermitaj konfliktoj": "conf", "Notoj pri malgravaj malkongruoj": "disc"}.get(t)
            if not cur: out["secs"].append((t, [])); cur = "sec"
            continue
        if h and top == "2" and h.group(1).startswith("Juĝoj ne uzitaj"): cur = "jug"; continue
        if cur == "sec": out["secs"][-1][1].append(l)
        else: out[cur].append(l)
    return out

def trim(ls):
    while ls and not ls[0].strip(): ls = ls[1:]
    while ls and not ls[-1].strip(): ls = ls[:-1]
    return [] if [l.strip() for l in ls] == ["—"] else ls

def section_summaries(d, tag):
    """(name, part keys, [(section title, its italic summary)]) in the biography's order."""
    ks = part_keys(d, tag)
    miss = [k for k in ks if not os.path.exists(os.path.join(d, f"S4-RETURN-{tag}-p{k}.md"))]
    if miss: sys.exit(f"refusing: the S4 returns of parts {', '.join(miss)} are not filed")
    name = re.match(r"# La biografio de (.*) \(smelt S4", open(os.path.join(d, f"S4-BRIEF-{tag}-p{ks[0]}.md"), encoding="utf-8").readline()).group(1)
    secs = []
    for k in ks:
        for t, ls in s4_parse(open(os.path.join(d, f"S4-RETURN-{tag}-p{k}.md"), encoding="utf-8").read())["secs"]:
            secs.append((t, next((l.strip() for l in ls if re.match(r"^\*[^*].*\*$", l.strip())), None)))
    return name, ks, secs

def threads(d, tag, what):
    """The throughlines' sentences (S4-RETURN-<tag>-pt.md, part 2, tools/smelt-throughlines.py), which the abstract and
    the gist must carry (2026-10-22, the editor); none before that return is filed."""
    p = os.path.join(d, f"S4-RETURN-{tag}-pt.md")
    if not os.path.exists(p): return []
    t = open(p, encoding="utf-8").read()
    m = re.search(r"## 2\.[^\n]*\n(.*?)(?=\nFino\.|\Z)", t, re.S)
    ls = [l.strip() for l in (m.group(1) if m else "").split("\n") if l.strip().startswith("- ")]
    return ["", f"## La fadenoj tra la jaroj, kiujn {what} nepre portu", "",
            f"Ĉi tiuj rilatoj daŭris tra multaj jaroj, kaj neniu sekcio sola montras ilin. **Ĉiu el ili aperu en {what}**, "
            f"mallonge, en sia loko. Ili venas el la sekcio «Rilatoj tra la jaroj» de la biografio, kie ĉiu fakto estas citita, "
            f"do iliaj faktoj validas kiel tiuj de la resumoj (2026-10-22: legilo, kiu tenis ilin ekster la resumoj, preterlasis "
            f"ilin):", ""] + ls

def s4_summary(d, tag, again=False):
    """The abstract's brief. Up to about 300 words since 2026-10-22 (the editor; it was about 100). --again: a second
    abstract, S4-BRIEF-<tag>-ps2.md, where the first is filed; --s4-abstract puts it into the joined return."""
    name, ks, secs = section_summaries(d, tag)
    items = [f"- **{t}:** {it or '(sen resumo)'}" for t, it in secs]
    sfx = next(f"ps{n}" for n in range(2, 99) if not os.path.exists(os.path.join(d, f"S4-BRIEF-{tag}-ps{n}.md"))) if again else "ps"
    out = os.path.join(d, f"S4-BRIEF-{tag}-{sfx}.md")
    if os.path.exists(os.path.join(d, f"S4-RETURN-{tag}-{sfx}.md")): sys.exit(f"refusing: S4-RETURN-{tag}-{sfx}.md is filed")
    if again and not os.path.exists(os.path.join(d, f"S4-RETURN-{tag}-ps.md")): sys.exit("refusing: --again, but no first abstract is filed")
    items += threads(d, tag, "la resumo")
    open(out, "x" if again else "w", encoding="utf-8").write(
        f"# La resumo de la biografio de {name} (smelt S4, {tag}, la fina parto)\n\n`[tools/smelt-periods.py --s4-summary: the "
        f"sections' summaries of S4-RETURN-{tag}-p{', -p'.join(ks)}.]`\n\n## La briefo\n\nVi verkas la resumon de biografio por esplora "
        f"projekto pri la historio de la internaciaj helplingvoj. Legu nur ĉi tiun briefon: ne rulu ŝelajn komandojn, ne faru "
        f"retajn serĉojn, ne skribu dosierojn. Via fina mesaĝo estas via raporto. Skribu en Esperanto.\n\nLa biografio de {name} "
        f"estas verkita en partoj, po unu sekcio por ĉiu periodo de la vivo kaj kelkaj temaj sekcioj; ĉiu sekcio komenciĝas per "
        f"resumo de du aŭ tri frazoj. Sube estas tiuj resumoj, laŭ la ordo de la biografio. **Verku el ili la resumon de la tuta "
        f"biografio:** ĝis ĉ. 300 vortoj, en unu ĝis tri alineoj: kiu la persono estis, la ĉefaj okazoj de la vivo laŭ ilia "
        f"ordo, kaj ĝia rolo en la temoj de la projekto; sen citaĵoj de linioj; nenio, kio ne estas en la resumoj sube; ĉiu "
        f"alineo tute kursiva, inter `*…*`, sen etikedo. Niaj markoj (=, ∴, ◊?) kaj la dubindikoj de la resumoj restas, kie vi "
        f"transprenas ilian aserton.\n\n**La raporto:** nur la alineoj, poste la linio «Fino.»\n\n## La resumoj de la sekcioj\n\n"
        + "\n".join(items) + "\n")
    print(f"S4-BRIEF-{tag}-{sfx}.md: {len(items)} sections' summaries")

def s4_abstract(d, tag):
    """The second abstract (S4-RETURN-<tag>-ps2.md) in place of the first under «### Resumo» of the joined return, which
    is kept first as S4-RETURN-<tag>-abstract1.md; nothing else changes, so a polish already applied stands."""
    p = os.path.join(d, f"S4-RETURN-{tag}.md")
    ns = sorted(int(m.group(1)) for f in os.listdir(d) for m in [re.fullmatch(rf"S4-RETURN-{re.escape(tag)}-ps(\d+)\.md", f)] if m)
    if not ns: sys.exit(f"refusing: no S4-RETURN-{tag}-ps2.md (or later) is filed")
    q = os.path.join(d, f"S4-RETURN-{tag}-ps{ns[-1]}.md")    # the newest abstract
    t = open(p, encoding="utf-8").read()
    # only what stands before «Fino.»: a legilo's note after it is not the abstract (2026-10-22, Beauchemin's ps3)
    new = [l for l in open(q, encoding="utf-8").read().split("\nFino.")[0].split("\n") if l.strip() and not l.startswith(("#", "`["))]
    m = re.search(r"(### Resumo\n\n)(.*?)(\n\n### )", t, re.S)
    if not m: sys.exit("refusing: no «### Resumo» block followed by a section")
    keep = next(f"S4-RETURN-{tag}-abstract{n}.md" for n in range(1, 99) if not os.path.exists(os.path.join(d, f"S4-RETURN-{tag}-abstract{n}.md")))
    with open(os.path.join(d, keep), "x", encoding="utf-8") as fh: fh.write(t)
    open(p, "w", encoding="utf-8").write(t[:m.start(2)] + "\n\n".join(new) + t[m.end(2):])
    print(f"S4-RETURN-{tag}.md: the abstract {len(m.group(2).split())} → {sum(len(l.split()) for l in new)} words, "
          f"from {os.path.basename(q)} (the return before it: {keep})")

def s4_gist(d, tag):
    """The brief for the gist biography (2026-10-22; the editor): the sections' summaries in the three
    parts of tools/smelt_parts.py, for one legilo, its return filed as S4-GIST-<tag>.md beside the full biography."""
    name, ks, secs = section_summaries(d, tag)
    dy = smelt_parts.death_year(d, tag)
    sfx = next(s for s in ["gist"] + [f"gist{n}" for n in range(2, 99)] if not os.path.exists(os.path.join(d, f"S4-BRIEF-{tag}-{s}.md")))
    out = os.path.join(d, f"S4-BRIEF-{tag}-{sfx}.md")
    groups, cur = [], None
    for t, it in secs:
        p = smelt_parts.part_of(t, dy)
        if p != cur: cur = p; groups.append(f"\n### {smelt_parts.TITLES[p]}\n")
        groups.append(f"- **{t}:** {it or '(sen resumo)'}")
    with open(out, "x", encoding="utf-8") as fh: fh.write(
        f"# La mallonga biografio de {name} (smelt S4, {tag}, por ne-fakuloj)\n\n`[tools/smelt-periods.py --s4-gist: the "
        f"sections' summaries of S4-RETURN-{tag}-p{', -p'.join(ks)}, in the parts of tools/smelt_parts.py.]`\n\n## La briefo\n\n"
        f"Vi verkas mallongan biografion por esplora projekto pri la historio de la internaciaj helplingvoj. Legu nur ĉi tiun "
        f"briefon: ne rulu ŝelajn komandojn, ne faru retajn serĉojn, ne skribu dosierojn. Via fina mesaĝo estas via raporto. "
        f"Skribu en Esperanto.\n\nLa plena biografio de {name} havas multajn sekciojn, ĉiu kun resumo de du aŭ tri frazoj. Sube "
        f"estas tiuj resumoj, laŭ la ordo de la biografio kaj en ĝiaj partoj. **Verku el ili unu fluan biografion por legantoj, "
        f"kiuj ne estas fakuloj:** prozo, ne listo; la tri partoj kiel titoloj `## …` (`## La vivo`, `## Post la morto`, `## La "
        f"persono`, nur tiuj, kiuj estas sube); alineoj laŭ la temo. Por la legebleco vi rajtas preterlasi detalojn de la resumoj "
        f"(nomojn de malgravaj personoj, titolojn de artikoloj, numerojn), sed ne aldonu ion, kio ne estas en ili, kaj ne ŝanĝu "
        f"ilian sencon. Kunigu, kio ripetiĝas. Sen citaĵoj de linioj kaj sen niaj markoj (=, ∴, ◊?, ⚫️): kie resumo dubas aŭ diras, "
        f"ke la fontoj malkonsentas, diru tion per vortoj («eble», «laŭ Jossinet», «la fontoj ne diras»). Titoloj de libroj kaj "
        f"gazetoj kursive. Proksimume duono de la longo de la resumoj sube.\n\n**La raporto:** nur la biografio, de la unua "
        f"titolo `##`, poste la linio «Fino.»\n\n## La resumoj de la sekcioj\n" + "\n".join(groups + threads(d, tag, "la biografio")) + "\n")
    print(f"S4-BRIEF-{tag}-{sfx}.md: {len(secs)} sections' summaries, the death {dy or 'not in the profile'}"
          + (", with the throughlines" if threads(d, tag, "") else ""))

def s4_join(d, tag):
    ks = part_keys(d, tag)
    out_p = os.path.join(d, f"S4-RETURN-{tag}.md")
    if os.path.exists(out_p): sys.exit(f"refusing: S4-RETURN-{tag}.md exists")
    files = [f"S4-RETURN-{tag}-p{k}.md" for k in ks] + [f"S4-RETURN-{tag}-ps.md"]
    miss = [f for f in files if not os.path.exists(os.path.join(d, f))]
    if miss: sys.exit(f"refusing: not filed: {', '.join(miss)}")
    rd = lambda f: open(os.path.join(d, f), encoding="utf-8").read()
    name = re.match(r"# La biografio de (.*) \(smelt S4", rd(f"S4-BRIEF-{tag}-p{ks[0]}.md").split("\n")[0]).group(1)
    parts = [(k, s4_parse(rd(f"S4-RETURN-{tag}-p{k}.md"))) for k in ks]
    label = lambda k: f"**Parto {k}" + (" ({}–{})".format(*span(d, tag, k)) if k != "g" else " (la temaj sekcioj)") + ":**"
    summ = [l for l in rd(f"S4-RETURN-{tag}-ps.md").split("\nFino.")[0].split("\n") if l.strip() and not l.startswith(("#", "`["))]
    body = [f"# La biografio de {name} (smelt S4, {tag})", "", f"`[tools/smelt-periods.py --s4-join: {', '.join(files)}]`", "",
            "## 1. La resumo kaj la biografio", "", "= kalkulite · ∴ konkludite · ◊? konjektite · ⚫️: truo en la legitaj fontoj",
            "", "### Resumo", ""] + summ
    n = 0
    for k, p in parts:
        for t, ls in p["secs"]:
            n += 1; body += ["", f"### {n}. {t}", ""] + trim(ls)
    for key, title in (("kie", "### Kie troviĝas la fontoj"), ("conf", "### La malfermitaj konfliktoj"), ("disc", "### Notoj pri malgravaj malkongruoj"),
                       ("r2", "## 2. Epizodoj kaj linioj ne uzitaj, kaj kial"), ("jug", "### Juĝoj ne uzitaj"),
                       ("r3", "## 3. Foriroj de la grupoj aŭ epizodoj, kaj kial"), ("r4", "## 4. Malklaraĵoj kaj faŭltoj de la profilo; proponoj por la registro")):
        body += ["", title, ""]
        got = [(k, trim(p[key])) for k, p in parts if trim(p[key])]
        if not got: body.append("—")
        for k, ls in got:
            body += ([label(k), ""] if key not in ("kie",) else []) + ls + [""]
    stray = sum(len(trim(p["stray"])) for _, p in parts)
    body += ["", "Fino."]
    with open(out_p, "x", encoding="utf-8") as fh: fh.write("\n".join(body) + "\n")
    print(f"S4-RETURN-{tag}.md: {len(parts)} parts, {n} sections" + (f"; {stray} lines before a part's first section left out" if stray else ""))

if __name__ == "__main__":
    main()
