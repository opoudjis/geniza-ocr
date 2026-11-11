#!/usr/bin/env python3
"""The smeltees' page: who gets a biography, and why (2026-10-27; the editor). Writes published/genizo/pages/biografatoj.md (in geniza/prosopografio/
until 2026-10-30, the editor: every site page's source in the one place), in Esperanto, for the Prosopografio pages (Miles publishes: the site is his).

    tools/smeltee-list.py [--dry-run]

The page is a template: its title, preface and criteria are written by hand; the tool fills only its two marked blocks
(ESPERANTISTOJ, IDISTOJ), at each run (after a harvest, like the siglaro), and refuses a page without the marks. From:
  - the Esperanto list: the bingo card, `geniza/bingo-card/bingo-card-v0.3*.csv` (the 106 portraits of the Schuck album, its
    supplement of 21, the Lingva Komitato before 1909 not in those, 21); the editor, 2026-10-25;
  - the Ido list: the three-part rule (IDO-APPARATUS-QUESTIONS-2026-10-25.md § 5; the editor 2026-10-27): (a) Idists who joined by 1918, from `profiles/SCOPE-REGISTER.tsv` (in or provisional; io.wikipedia's candidates
    not yet folded in counted apart); (b) the Academy, the Delegation's committee and the Uniono's committees 1908–1918,
    and (c) the national federations' presidents and secretaries 1908–1918, both from *Progreso*'s dowse, once it is in
    (the lines of kind «ofico» whose object names those bodies);
  - the smelt's scope (the smelt runbook S0 4a): Esperantists who joined before 1908, Idists who joined in or before 1918;
  - each person's profile (`profiles/<stem>.md`, its count of facts) and smelt folder (`smelt/<stem>/`: an S4 file, the
    biography written). Ezri."""
import argparse, csv, glob, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
OUT = os.path.join(ROOT, "published", "genizo", "pages", "biografatoj.md")   # «biografatoj», not «fandotoj» (the editor, 2026-10-27)
csv.field_size_limit(sys.maxsize)

def rows(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t" if path.endswith(".tsv") else ","))

def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def profile(stem):
    """(head, facts) of profiles/<stem>.md, or None."""
    p = os.path.join(G, "profiles", stem + ".md")
    if not os.path.exists(p): return None
    t = open(p, encoding="utf-8").read(4000)
    h = re.match(r"# (.+?) — ", t); n = re.search(r"\*\*(\d[\d,]*) faktoj", t)
    return (h.group(1) if h else stem.upper(), int(n.group(1).replace(",", "")) if n else 0)

# Austria-Hungary: -ujo for both halves (the editor 2026-10-27; the 1904 Jarlibro prints «AUSTRUJO-HUNGARUJO»)
COUNTRIES = {"Austria-Hungary": "Aŭstrujo-Hungarujo", "Belgium": "Belgujo", "Brazil": "Brazilo", "Britain": "Britujo",
             "Bulgaria": "Bulgarujo", "Canada": "Kanado", "Chile": "Ĉilio", "Denmark": "Danujo", "Finland": "Finnlando",
             "France": "Francujo", "Germany": "Germanujo", "Greece": "Grekujo", "Iceland": "Islando", "India": "Hindujo",
             "Italy": "Italujo", "Japan": "Japanujo", "Malta (Brit.)": "Malto (brita)", "Mexico": "Meksiko",
             "Netherlands": "Nederlando", "Norway": "Norvegujo", "Persia": "Persujo", "Peru": "Peruo", "Portugal": "Portugalujo",
             "Russia": "Rusujo", "Spain": "Hispanujo", "Sweden": "Svedujo", "Switzerland": "Svisujo", "USA": "Usono",
             "Caucasus": "Kaŭkazo", "Crimea": "Krimeo", "Estonia": "Estonujo", "Lithuania": "Litovujo", "Poland": "Polujo",
             "Ukraine": "Ukrainujo"}

def country(c):
    """The card's country in Esperanto («Russia (Poland)» → «Rusujo (Polujo)»); a name not in the table as it stands."""
    m = re.fullmatch(r"(.+?)(?: \((.+)\))?", c.strip())
    if not m or not c.strip(): return c
    if c.strip() in COUNTRIES: return COUNTRIES[c.strip()]
    a, b = m.group(1), m.group(2)
    return COUNTRIES.get(a, a) + (f" ({COUNTRIES.get(b, b)})" if b else "")

def smelt_state(stem):
    d = os.path.join(G, "smelt", stem)
    if not os.path.isdir(d): return "atendas"
    fs = os.listdir(d)
    if any(f.startswith("S4-") or re.search(r"-s4\.tsv$", f) for f in fs): return "**biografio verkita**"
    return "komencita"

NOT_SMELTED = {"zamenhof"}   # on the list, no biography (the editor, 2026-10-29 13:0x; below)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    eo, seen = [], set()
    # THE CARD OF THE RELEASE (Miles, 2026-11-11, the prosopography 0.1; the editor): the v0.3 tables
    # lacked McKenzie (added to the Lingva Komitato list later) and kept three stems the smelt renamed, so the page counted
    # 33 biographies of the release's 37. The card is 1.0.0, aligned with the prosopography 0.1; its stem column still
    # has the old three, mapped here to the profile and smelt stems.
    CARD, RENAMED = "1.0.0", {"morin": "anselmo-morin", "atanasov": "georgi-atanasov", "cederblad": "thisell"}
    for f, part in ((f"bingo-card-v{CARD}.csv", "la albumo de Schuck"), (f"bingo-card-v{CARD}-supplement.csv", "la suplemento"),
                    (f"bingo-card-v{CARD}-lk1905.csv", "la Lingva Komitato antaŭ 1909")):
        for r in rows(os.path.join(G, "bingo-card", f)):
            st = (r.get("stem") or "").strip()
            st = RENAMED.get(st, st)
            if not st or st in seen: continue
            seen.add(st)
            pr = profile(st)
            ido = "🟦" in (r.get("tags_in_sequence") or "")
            # ZAMENHOF IS NOT SMELTED (the editor, 2026-10-29 13:0x
            #): 18,745 facts, a fifth of the whole list's; listed, his
            # profile and fact files published as everyone's, no biography
            state = "ne fandota" if st in NOT_SMELTED else smelt_state(st)
            eo.append((pr[0] if pr else st.upper(), r.get("country", ""), part, pr[1] if pr else 0, state, ido, st))
    # the Ido list, part (a): the register's Idists in or provisional who joined by 1918 (or whose date is not known)
    io, uncertain, undated = [], 0, 0
    for r in rows(os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")):
        if "Ido" not in (r.get("movement") or "") or r.get("verdict") not in ("in", "provisional"): continue
        j = (r.get("joined_io") or "").strip()
        y = re.search(r"(1[89]\d\d)", j)
        if y and int(y.group(1)) > 1918 and not j.startswith("≤"): continue
        # AN IDIST WITHOUT A JOINING DATE WAITS FOR ONE (the editor, 2026-10-27 15:2x, option b, on Miles's report of living
        # Idists from io.wikipedia listed as provisional pre-1919 ones: Suprayan, Takata, Walesch, Gasper): counted, not listed
        if not j: undated += 1; continue
        if j.startswith("≤") and y and int(y.group(1)) > 1918: uncertain += 1
        st = slug(r["name"].split(" (")[0]) if not profile(slug(r["name"])) else slug(r["name"])
        pr = profile(st)
        # 🟩 an Esperantist before (the editor): the register's
        # movement or its Esperanto joining date, or the person on the Esperanto list
        was_eo = st in seen or "Esperanto" in (r.get("movement") or "") or bool((r.get("joined_eo") or "").strip())
        io.append((r["name"], j or "?", r["verdict"], pr[1] if pr else 0, smelt_state(st), was_eo))
    # ONE PERSON, TWO REGISTER ROWS (Miles, 2026-10-27 15:1x: JESPERSEN and JESPERSEN (Otto), MATEJKA and MATEJKA
    # (Alphonse)): a bare name and a qualified one of the same surname are one person, kept once, the row with a joining
    # date (else the one in scope) winning; two qualified names (JACOB (Heinz), JACOB (Max)) are two people
    bysur = {}
    for x in io: bysur.setdefault(x[0].split(" (")[0], []).append(x)
    io = []
    for sur, xs in bysur.items():
        bare = [x for x in xs if " (" not in x[0]]
        if bare and len(xs) > 1:
            best = sorted(xs, key=lambda x: (x[1] == "?", x[2] != "in", " (" not in x[0]))[0]
            io.append(best); io.extend(x for x in xs if x not in bare and x is not best and len(bare) == 0)
        else: io.extend(xs)
    iow = os.path.join(G, "profiles", "SCOPE-REGISTER-CANDIDATES-IOWIKI-2026-10-14.tsv")
    n_iow = len(rows(iow)) if os.path.exists(iow) else 0
    # parts (b) and (c): Progreso's office lines, once its facts file exists
    prog = os.path.join(G, "profiles", "by-source", "progreso-dowse.md")
    offices = {}
    if os.path.exists(prog):
        for l in open(prog, encoding="utf-8"):
            m = re.match(r"- \$\$\$ (.+?) \$\$\$.*?\{ofico: ([^};+]*)", l)
            if not m: continue
            o = m.group(2).strip(); lo = o.lower(); role = lo.split(",")[0]
            # (b) THE RULE AS WRITTEN (2026-10-27, the first fill took 310: the Akademio de Esperanto, Idiom Neutral's
            # academy, every society's delegate to the Delegation, every Uniono member): the Ido Academy, the Delegation's
            # committee and permanent commission, the Uniono's committees; (c) the presidents, vice-presidents and
            # secretaries of the national federations and unions
            # (the Delegation's committee dropped, the editor 2026-10-27 17:3x: Boirac sat on it and was never an Idist)
            b = ((re.search(r"akademi", lo) and not re.search(r"esperant|lingu universal|neutral|scienc|medicin", lo))
                 or (re.search(r"komitat|direktant", lo) and re.search(r"unio", lo) and not re.search(r"delegitar", lo)))
            c = (re.match(r"(?:vic)?prezidant|(?:ĝenerala )?sekretari", role) and re.search(r"federaci|federuro|unio", lo)
                 and not re.search(r"sacerdot|laborist|amik|esperant", lo))
            if b or c: offices.setdefault(m.group(1), o)
    done_eo = sum(1 for x in eo if x[4].startswith("**")); done_io = sum(1 for x in io if x[4].startswith("**"))
    # THE PAGE IS A TEMPLATE (2026-10-27; the editor
    #): the title, preface and criteria are written by hand in the page; the tool fills only the blocks
    # between <!-- ESPERANTISTOJ: … --> … <!-- /ESPERANTISTOJ --> and <!-- IDISTOJ: … --> … <!-- /IDISTOJ -->, as
    # tools/genizo-osr-list.py does for osr-korpuso.md. Countries in Esperanto (the editor
    #), the -ujo forms the site already uses
    L = []
    L.append(f"## La esperantistoj ({len(eo)}; biografio verkita: {done_eo})\n")
    L.append("| persono | lando | el | faktoj | biografio |\n|---|---|---|---:|---|")
    for h, c, part, n, s, ido, st in sorted(eo, key=lambda x: x[0]):
        L.append(f"| {h}{' 🟦' if ido else ''} | {country(c)} | {part} | {n:,} | {s} |")
    blocks = {"ESPERANTISTOJ": "\n".join(L)}
    L = []
    L.append(f"## La idistoj ({len(io)}; biografio verkita: {done_io})\n")
    nprov = sum(1 for x in io if x[2] == "provisional")
    L.append(f"**(a) Laŭ la registro de amplekso:** {len(io)} idistoj, kiuj aliĝis antaŭ 1919 ({uncertain} el ili kun nur supra limo post 1918, kiel «≤ 1920», provizore). **{undated} pliaj idistoj de la registro ankoraŭ ne havas konatan daton de aliĝo**, multaj el ili el io.wikipedia kaj modernaj: ili atendas ekster la tabelo, ĝis la legado de la idistaj gazetoj donos al ili daton antaŭ 1919. La idistoj de io.wikipedia ({n_iow} kandidatoj) ankoraŭ ne estas plene enmetitaj en la registron.\n")
    L.append("| persono | aliĝis al Ido | stato en la registro | faktoj | biografio |\n|---|---|---|---:|---|")
    for name, j, v, n, s, was_eo in sorted(io, key=lambda x: x[0]):
        L.append(f"| {name}{' 🟩' if was_eo else ''} | {j} | {'en la amplekso' if v == 'in' else 'provizore'} | {n:,} | {s} |")
    L.append("")
    # the Esperantists of the bingo card who went to Ido (Couturat, De Beaufront, Schneeberger…): the register has them as
    # Esperantists, their move to Ido on the card (🟦)
    went = sorted((x for x in eo if x[5]), key=lambda x: x[0])
    L.append(f"**Kaj la pioniroj de Esperanto, kiuj transiris al Ido** ({len(went)}, en la listo de la esperantistoj kun 🟦): " +
             ", ".join(f"{h}{' (biografio verkita)' if s.startswith('**') else ''}" for h, c, part, n, s, ido, st in went) + ".\n")
    # NOT SHOWN UNTIL THE NAMES ARE RECONCILED (the editor, 2026-10-27 17:3x
    # Progreso's heads include the OCR's forms, BOCCACX, BOCRACX … BORRACK for one man, and are not yet joined to
    # the profiles or to the Esperantists' list): the count only
    L.append("**(b) kaj (c) La Akademio, la komitatoj de la Uniono kaj la federacioj:** " + (
        f"{len(offices)} personoj el *Progreso*; la listo estos montrata, kiam iliaj nomoj estos kontrolitaj kontraŭ la profiloj.\n"
        if offices else "venos el *Progreso*, kiam ĝia legado estos finita.\n"))
    blocks["IDISTOJ"] = "\n".join(L).rstrip()
    pg = old = open(OUT, encoding="utf-8").read()
    for tag, body in blocks.items():
        m = re.search(rf"(<!-- {tag}:[^\n]*-->\n)(.*?)(<!-- /{tag} -->)", pg, re.S)
        if not m: sys.exit(f"{os.path.relpath(OUT, ROOT)}: no <!-- {tag}: … --> … <!-- /{tag} --> marks")
        pg = pg[:m.start(2)] + body + "\n" + pg[m.end(2):]
    import page_date   # «_Aktualigita: …_», the day the lists last changed (2026-10-31)
    pg = page_date.stamp(old, pg)
    if a.dry_run:
        print(f"Esperanto {len(eo)} (written {done_eo}); Ido (a) {len(io)} (written {done_io}); (b)/(c) {len(offices)}"); return
    with open(OUT, "w", encoding="utf-8") as fh: fh.write(pg)
    print(f"filled {os.path.relpath(OUT, ROOT)}: Esperanto {len(eo)} (written {done_eo}); Ido (a) {len(io)} (written {done_io}); (b)/(c) {len(offices)}")

if __name__ == "__main__":
    main()
