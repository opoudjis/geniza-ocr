#!/usr/bin/env python3
r"""smelt-throughlines.py — the people a biography's subject lived with or against across the years, with their own
lives beside his, so that the writer sees the relation whole (2026-10-22; the editor, on De Beaufront's last 27 years
in the households of Jehan Guérard and Henriette Trioux née Guérard, scattered over four sections and lost in the
abstract and the gist
).

    tools/smelt-throughlines.py <stem> <tag>            the list and the legilo's brief
    tools/smelt-throughlines.py <stem> <tag> --insert   its section into the joined biography
    tools/smelt-throughlines.py <stem> <tag> --check    the loss check: every throughline in the abstract and the gist

A throughline is a person (grouped by surname: a family) named in the kind field of the subject's lines (the NOMO in
capitals the dowse writes there) who has a profile of their own, with at least 3 lines, falling in at least 3 of the
smelt's periods or spanning at least 10 years; the 15 with the longest span. For each: the subject's lines about them
(L-numbers, the frozen profile's line numbers, so the biography cites them as it cites every line), at most 30, spread
over the years; and up to 25 lines of their own profile within the subject's lifetime that do not name the subject (their
births, marriages, work, homes), cited by their locator.

Writes (create-only): smelt/<stem>/THROUGHLINES-<tag>.md (the list) and S4-BRIEF-<tag>-pt.md (one legilo; its return
S4-RETURN-<tag>-pt.md: (1) one section «Rilatoj tra la jaroj» for «La persono», (2) one sentence a throughline, for the
abstract and the gist, which `smelt-periods.py --s4-summary` and `--s4-gist` then require). --insert puts the section in
S4-RETURN-<tag>.md as the last numbered section (the return before it kept as S4-RETURN-<tag>-before-pt.md). --check
lists each throughline's surname found or missing in the abstract and in S4-GIST-<tag>*.md, the newest. Ezri, 2026-10-22."""
import collections, glob, os, re, sys, unicodedata
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
spec = importlib.util.spec_from_file_location("sp", os.path.join(ROOT, "tools", "smelt-periods.py"))
SP = importlib.util.module_from_spec(spec); spec.loader.exec_module(SP)

def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def caps(field):
    """The NOMO runs of a kind field: words in capitals, joined («DE BEAUFRONT», «SAINT-MARTIN»), with a qualifier."""
    out, run = [], []
    # a hyphen or an apostrophe inside a name keeps it whole («SAINT-MARTIN», not «SAINT» and «MARTIN», 2026-10-22)
    toks = re.findall(r"[^\W\d_](?:[^\W\d_]|['’\-](?=[^\W\d_]))*|\([^)]*\)|\S", field)
    for i, t in enumerate(toks + [""]):
        if len(t) > 1 and t.replace("-", "").replace("'", "").isupper() and t[0].isalpha():
            run.append(t); continue
        if run:
            q = t[1:-1] if t.startswith("(") and t.endswith(")") else ""
            out.append((" ".join(run), q)); run = []
    return out

def year(l):
    m = re.search(r"\*\*[^*]*?\b(1[5-9]\d\d|20\d\d)\b", l)
    return int(m.group(1)) if m else None

def kind_field(l):
    m = re.search(r" · (\{[^}]*\})", l)
    return m.group(1) if m else ""

def profile(d, tag):
    p = os.path.join(d, f"PROFILE-FROZEN-{tag}.md")
    return open(p, encoding="utf-8").read().split("\n")

def build(stem, tag):
    d = os.path.join(G, "smelt", stem)
    lines = profile(d, tag)
    head = next(re.match(r"- \$\$\$ (.+?) \$\$\$", l).group(1) for l in lines if l.startswith("- $$$"))
    spans = [(k, SP.span(d, tag, k)) for k in SP.part_keys(d, tag) if k != "g"]
    spans = [(k, (int(a), int(b))) for k, s in spans if s for a, b in [s]]
    life = [year(l) for l in lines if re.search(r"\{(?:naskiĝo|morto)\b", kind_field(l)) and year(l)]
    lo, hi = (min(life), max(life)) if life else (None, None)
    ents = collections.defaultdict(list)
    for n, l in enumerate(lines, 1):
        if not l.startswith("- $$$"): continue
        for name, q in caps(kind_field(l)):
            if name == head or not os.path.exists(os.path.join(G, "profiles", f"{slug(name)}.md")): continue
            ents[name].append((n, year(l), q, l))
    rows = []
    for name, ls in ents.items():
        # the years of his life only: a historian's line of 1998 is not a year of the relation (the first run ranked
        # Waringhien 1855–1998 first and left the Guérards, 1911–1935, out of the 15)
        ys = sorted({y for _, y, _, _ in ls if y and (not lo or lo <= y <= hi)})
        if len([1 for _, y, _, _ in ls if y in ys]) < 3 or not ys: continue
        per = {k for y in ys for k, (a, b) in spans if a <= y <= b}
        if len(per) >= 3 or ys[-1] - ys[0] >= 10: rows.append((ys[-1] - ys[0], len(per), name, ls, ys))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
    return d, head, lines, (lo, hi), rows[:20], len(rows)

def spread(ls, k):
    if len(ls) <= k: return ls
    step = len(ls) / k
    return [ls[int(i * step)] for i in range(k)]

def theirs(name, head, lo, hi, family):
    """Their own lines; where the subject's lines name members of the family («GUÉRARD (Jehan)»), only the lines that
    carry a member's name, «**(Henriette)**», since a surname's profile can hold a homonym (GUÉRARD: the Grivesnes family
    and A. L. Guérard of Stanford, 2026-10-22)."""
    out = []
    for l in open(os.path.join(G, "profiles", f"{slug(name)}.md"), encoding="utf-8"):
        l = l.rstrip("\n")
        if not l.startswith("- $$$") or head in l: continue
        if family and not re.search(r"\*\*\([^)]+\)\*\*", l): continue
        y = year(l)
        if y and lo and hi and not (lo - 30 <= y <= hi): continue
        out.append(l)
    pri = lambda l: (0 if re.search(r"\{(?:naskiĝo|morto|familio|profesio|loĝado|ofico)\b", kind_field(l)) else 1, year(l) or 9999)
    return sorted(out, key=pri)[:15]

def cut(l, n=450):
    return l if len(l) <= n else l[:n] + " …"

def write_list(stem, tag):
    d, head, lines, (lo, hi), rows, n_all = build(stem, tag)
    out, items = [f"# The throughlines of {head} (smelt, {tag})", "",
                  f"`[tools/smelt-throughlines.py: the people named in the kind field of the subject's lines, with a profile of their own, "
                  f"at least 3 lines, in at least 3 periods or over at least 10 years; {len(rows)} of {n_all} shown, by span. Life {lo}–{hi}.]`", ""], []
    for span_, per, name, ls, ys in rows:
        quals = sorted({q for _, _, q, _ in ls if q})
        out += [f"## {name}" + (f" ({', '.join(quals)})" if quals else "") + f": {len(ls)} lines, {ys[0]}–{ys[-1]}, {per} periods", ""]
        his = spread(ls, 20)
        out += [f"- L{n}: {cut(l[2:])}" for n, _, _, l in his]
        # his lines about the places of the relation, which need not name the family (2026-10-22: Jossinet's «27 jaroj
        # en la bieno La Folie», L9, names the farm, not the Guérards, and the first run missed it)
        places = {p.strip() for _, _, _, l in ls for p in re.findall(r"loĝado: ([^,;}]+)", kind_field(l))}
        places = {p for p in places if len(p) > 3}
        seen = {n for n, _, _, _ in ls}
        at = [(n, l) for n, l in enumerate(lines, 1) if l.startswith("- $$$") and n not in seen
              and any(p in l for p in places)][:10]
        if at:
            out += ["", f"His other lines at the same places ({', '.join(sorted(places))}):", ""] + [f"- L{n}: {cut(l[2:])}" for n, l in at]
        th = theirs(name, head, lo, hi, bool(quals))
        if th:
            out += ["", f"Their own lines ({len(th)}):", ""] + [f"- {cut(l[2:])}" for l in th]
        out.append("")
        items.append(name)
    mode = "w" if "--replace" in sys.argv else "x"    # --replace: remake this tool's own two files
    open(os.path.join(d, f"THROUGHLINES-{tag}.md"), mode, encoding="utf-8").write("\n".join(out) + "\n")
    name = re.match(r"# La biografio de (.*) \(smelt S4", open(os.path.join(d, f"S4-RETURN-{tag}.md"), encoding="utf-8").readline())
    name = name.group(1) if name else head
    brief = [f"# La rilatoj tra la jaroj de {name} (smelt S4, {tag}, la parto t)", "",
             f"`[tools/smelt-throughlines.py: THROUGHLINES-{tag}.md, {len(rows)} throughlines.]`", "", "## La briefo", "",
             f"Vi estas legilo de esplora projekto pri la historio de la internaciaj helplingvoj. Legu nur ĉi tiun briefon kaj la "
             f"dosieron sube; ne rulu ŝelajn komandojn, ne faru retajn serĉojn, ne skribu dosierojn. Via fina mesaĝo estas via raporto. "
             f"Skribu en Esperanto.", "",
             f"La biografio de {name} estas verkita laŭ periodoj, kaj tial rilato, kiu daŭris tra multaj jaroj, estas disŝirita "
             f"inter multaj sekcioj; en la resumoj ĝi perdiĝas. La dosiero `{os.path.join(d, f'THROUGHLINES-{tag}.md')}` donas por "
             f"ĉiu el {len(rows)} personoj aŭ familioj, kiujn {name} renkontis tra la jaroj, liajn liniojn pri ili (kun ilia numero "
             f"L…) kaj iliajn proprajn liniojn el ilia propra profilo (iliaj naskiĝoj, edziĝoj, laboroj, loĝejoj), kun ilia lokindiko.", "",
             f"**Via tasko:** legu la tutan dosieron. Por ĉiu rilato, kiu diras ion pri la vivo de {name}, kion neniu periodo sola "
             f"montras (longa kunvivado, protekto, amikeco aŭ malamikeco tra jardekoj, la homoj, ĉe kiuj li vivis aŭ laboris), "
             f"verku mallongan alineon: la rilato kiel unu ĉeno laŭ la tempo, kun la datoj. Kunigu, kion la linioj de la du flankoj "
             f"montras kune (ekzemple la naskiĝojn de la infanoj de familio kaj la jarojn, kiam li loĝis kaj instruis ĉe ĝi). "
             f"Preterlasu la rilatojn, kiujn ĉiu periodo jam rakontas tute (ekzemple Zamenhof, se ĝi estas nur la fono de ĉio). "
             f"Ĉiu frazo citas siajn liniojn: [L…] por liaj linioj, [NOMO: lokindiko] por iliaj, ekzemple [GUÉRARD: "
             f"acte-de-naissance-fr-grivesnes-guerard, ¶ 2]. Nenio, kio ne estas en la linioj. Konkludon marku per ∴, konjekton "
             f"per ◊? (ekzemple, ke du homoj de la sama nomo kaj vilaĝo estas gefratoj, aŭ ke la infanoj de la domo estis liaj "
             f"lernantoj, kiam neniu linio diras tion), truon per «⚫️: …». Tekston en alia lingvo sekvu ĝia traduko inter rektaj "
             f"krampoj; titolojn de libroj kaj gazetoj kursive.", "",
             f"**La raporto, en du partoj:**", "",
             f"`## 1. La sekcio`: la titolo `### Rilatoj tra la jaroj`, kursiva resumo de du aŭ tri frazoj, poste la alineoj, po unu "
             f"por rilato, kun titolo `**NOMO.**` en ĝia komenco.", "",
             f"`## 2. La fadenoj por la resumo`: por ĉiu rilato, kiun vi skribis, unu frazo sen citaĵoj, kiu diras ĝian kernon "
             f"(«Liajn lastajn 27 jarojn li vivis ĉe la familio Guérard …»), kiel listero `- NOMO: …`.", "",
             f"Poste la linio «Fino.»"]
    open(os.path.join(d, f"S4-BRIEF-{tag}-pt.md"), mode, encoding="utf-8").write("\n".join(brief) + "\n")
    print(f"THROUGHLINES-{tag}.md and S4-BRIEF-{tag}-pt.md: {len(rows)} of {n_all} throughlines: " + ", ".join(
        f"{r[2]} {r[4][0]}–{r[4][-1]}" for r in rows))

def pt_parts(d, tag):
    t = open(os.path.join(d, f"S4-RETURN-{tag}-pt.md"), encoding="utf-8").read()
    sec = re.search(r"## 1\.[^\n]*\n(.*?)(?=\n## 2\.)", t, re.S)
    thr = re.search(r"## 2\.[^\n]*\n(.*?)(?=\nFino\.|\Z)", t, re.S)
    return (sec.group(1).strip() if sec else ""), [l.strip()[2:] for l in (thr.group(1) if thr else "").split("\n") if l.strip().startswith("- ")]

def insert(stem, tag):
    d = os.path.join(G, "smelt", stem)
    p = os.path.join(d, f"S4-RETURN-{tag}.md")
    t = open(p, encoding="utf-8").read()
    sec, _ = pt_parts(d, tag)
    if not sec.startswith("### "): sys.exit("refusing: the return's part 1 has no «### …» section")
    nums = [int(x) for x in re.findall(r"^### (\d+)\. ", t, re.M)]
    sec = re.sub(r"^### ", f"### {max(nums) + 1}. ", sec, count=1)
    at = t.find("\n### Kie troviĝas la fontoj")
    if at < 0: sys.exit("refusing: no «### Kie troviĝas la fontoj» to insert before")
    open(os.path.join(d, f"S4-RETURN-{tag}-before-pt.md"), "x", encoding="utf-8").write(t)
    open(p, "w", encoding="utf-8").write(t[:at] + "\n\n" + sec + "\n" + t[at:])
    print(f"S4-RETURN-{tag}.md: section {max(nums) + 1} inserted, {len(re.findall(r'\[L', sec))} citations of his lines "
          f"(the return before it: S4-RETURN-{tag}-before-pt.md)")

def check(stem, tag):
    d = os.path.join(G, "smelt", stem)
    t = open(os.path.join(d, f"S4-RETURN-{tag}.md"), encoding="utf-8").read()
    ab = re.search(r"### Resumo\n\n(.*?)\n\n### ", t, re.S)
    ab = ab.group(1) if ab else ""
    gs = sorted(glob.glob(os.path.join(d, f"S4-GIST-{tag}*.md")), key=os.path.getmtime)
    gist = open(gs[-1], encoding="utf-8").read() if gs else ""
    _, thr = pt_parts(d, tag)
    norm = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    miss = 0
    for x in thr:
        name = x.split(":", 1)[0].strip()
        key = norm(name.split()[-1])
        a, g = key in norm(ab), key in norm(gist)
        miss += (not a) + (not g)
        print(f"{name}: abstract {'yes' if a else 'MISSING'}, gist {'yes' if g else 'MISSING'}" + (f" ({os.path.basename(gs[-1])})" if gs else ""))
    print(f"{stem} {tag}: {len(thr)} throughlines, {miss} missing")

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 2: sys.exit(__doc__)
    if "--insert" in sys.argv: insert(*a)
    elif "--check" in sys.argv: check(*a)
    else: write_list(*a)
