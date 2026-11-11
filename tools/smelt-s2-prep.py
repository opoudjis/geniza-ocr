#!/usr/bin/env python3
"""Smelt S2: the reader check of the fact groups, its input and brief (the editor, 2026-10-14; the runbook,
ocr/method/SMELT-RUNBOOK-2026-10-13.md, S2).

    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... [--kinds k1,k2] [--max 14] [--seed N]
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --episodes [--kinded-only]     smelt S3 (below)
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --episodes --refresh-singles   S3's input and singles remade, return filed
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --biography                    smelt S4, on the tag's S3 return
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --biography --straight         smelt S4 for 10–19 kinded lines, no S3 reader
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --samnomuloj                   «Samnomuloj» for a biography written without it
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --gist                         the gist of a biography by one writer

For each person: the groups of tools/fact-groups.py --match entity (two or more lines), every group of three or more and
a seeded sample of the pairs up to --max, or, with --kinds, every group of those kinds; and every nominated date error;
each with its full lines. Writes smelt/<stem>/S2-CHECK-INPUT-<tag>.md and S2-CHECK-BRIEF-<tag>.md (the brief from
ocr/method/SMELT-S2-CHECK-BRIEF-TEMPLATE-EO-2026-10-14.md); a tag whose return is filed is refused. The person's
profile is frozen as smelt/<stem>/PROFILE-FROZEN-<tag>.md if not already. Then a file-reader per brief, its return filed
as S2-CHECK-RETURN-<tag>.md. Ezri, 2026-10-14."""
import argparse, csv, importlib.util, os, random, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FLN   # a line's own fields, the source's words left out (2026-10-28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("people", nargs="+")
    ap.add_argument("--kinds", default=""); ap.add_argument("--max", type=int, default=14); ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--episodes", action="store_true", help="smelt S3: every group, candidate and nomination, by the frozen profile's line numbers, and the episode brief")
    ap.add_argument("--qualifier", help="with --episodes, one person: freeze only the head's lines under «**(Q)**», a namesake's")
    ap.add_argument("--kinded-only", action="store_true", help="with --episodes: freeze only the profile lines from a dowse file (the new dowse; until 2026-10-15, lines with an event kind)")
    ap.add_argument("--biography", action="store_true", help="smelt S4: the biography brief, from the tag's frozen profile and episode return")
    ap.add_argument("--as", dest="as_tag", help="with --biography: name the brief (and so its return) for this tag instead")
    # the runbook's «Open» 8 (2026-10-17: 10–19 lines, the biography reader straight from the frozen profile), unbuilt until
    # 2026-11-09 (the editor; Emeric, 13 kinded lines, the first smelt)
    ap.add_argument("--straight", action="store_true", help="with --biography: a profile of 10–19 kinded lines straight to S4, no episode reader: the compressed route's S3-COMPRESSED-<tag>.md and S3-INPUT-<tag>-reader.md (smelt-compress.py --skip-unkinded, no reader) stand in for the episodes; refused at 20 or more kinded lines, under 10, or where S3-RETURN-<tag>.md exists")
    ap.add_argument("--refresh-singles", action="store_true", help="with --episodes: rewrite S3-INPUT and S3-SINGLES of a tag whose return is filed (the brief untouched; the old files kept as …-as-read.md); refused if a U number's kind and object would change")
    # default None, not 0: «--sizes 0» ran the S2 prep for every person named and froze their profiles (2026-10-17)
    ap.add_argument("--sizes", type=int, default=None, help="read-only: rank people by their lines from dowse files (what --kinded-only freezes); print the top N, the spread, the rank of each person named, and candidates for a small test (20–40 lines from 3+ sources); writes nothing")
    ap.add_argument("--source", default="", help="with --sizes: rank by the lines from this one dowse file (e.g. ruslanda-esperantisto-dowse.md) and mark who has a smelt folder already (the editor, 2026-10-17)")
    ap.add_argument("--samnomuloj", action="store_true", help="the second route (2026-11-09): SAMNOMULOJ-<tag>.md and S4-SAMNOMULOJ-BRIEF-<tag>.md for one small writer, for a biography written without «Samnomuloj» (or after the periods route's --s4-join); smelt-s4-view.py merges the return into «Nomoj»")
    ap.add_argument("--gist", action="store_true", help="the gist for a biography by one writer (2026-11-09): S4-GIST-BRIEF-<tag>.md for one small writer, who writes S4-GIST-<tag>.md; the periods route has its own (smelt-periods.py --s4-gist)")
    a = ap.parse_args()
    if a.samnomuloj:
        return sam_brief(a)
    if a.gist:
        return gist_brief(a)
    if a.sizes is not None:
        return sizes(a)
    if a.biography:
        return biography(a)
    csv.field_size_limit(sys.maxsize)
    spec = importlib.util.spec_from_file_location("fg", os.path.join(ROOT, "tools", "fact-groups.py")); fg = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(fg); sys.argv = saved
    corpus = [(r["person"], r["file"], r["year"], r["kind"], r["line"]) for r in csv.DictReader(open(fg.LIST, encoding="utf-8"), delimiter="\t") if r.get("kind")]
    tpl = open(os.path.join(G, "ocr", "method", "SMELT-S2-CHECK-BRIEF-TEMPLATE-EO-2026-10-14.md"), encoding="utf-8").read()
    kinds = {k for k in a.kinds.split(",") if k}
    if a.episodes:
        return episodes(a, fg, corpus)
    for p in a.people:
        stem, _, name = p.partition("=")
        d = os.path.join(G, "smelt", stem); os.makedirs(d, exist_ok=True)
        if os.path.exists(os.path.join(d, f"S2-CHECK-RETURN-{a.tag}.md")): sys.exit(f"refusing: {stem} S2-CHECK-RETURN-{a.tag}.md exists")
        frozen = os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md")
        if not os.path.exists(frozen): shutil.copyfile(os.path.join(G, "profiles", f"{stem}.md"), frozen)
        rows = [r for r in corpus if r[0] == name]
        gs, noms = fg.groups_entity(rows, corpus)
        gs = [g for g in gs if len(g[3]) >= 2]
        if kinds:
            pick = [g for g in gs if g[1] in kinds]; how = f"every group of the kinds {', '.join(sorted(kinds))}"
        else:
            big = [g for g in gs if len(g[3]) >= 3]; pairs = [g for g in gs if len(g[3]) == 2]
            random.Random(a.seed).shuffle(pairs); pick = big + pairs[:max(0, a.max - len(big))]
            how = f"{len(big)} of three or more lines (all), {len(pick) - len(big)} pairs of {len(pairs)} drawn by seed {a.seed}"
        out = [f"# S2: the groups of {name} to check ({a.tag})", "",
               f"`[tools/smelt-s2-prep.py from tools/fact-groups.py --match entity: {len(gs)} groups of two or more; here {how}; {len(noms)} nominated date errors.]`", ""]
        for k, (who, kind, key, rs) in enumerate(pick, 1):
            out += [f"## G{k} · {kind} / {key} · {len(rs)} lines", ""] + [f"{j}. {r[4]}  ⟵ `{r[1]}`" for j, r in enumerate(rs, 1)] + [""]
        for k, (who, kind, key, grp, r) in enumerate(noms, 1):
            out += [f"## N{k} · nominated date error · {kind} / {key}", "", "The group:"] + [f"- {x[4]}  ⟵ `{x[1]}`" for x in grp] + ["", "The line nominated:", f"- {r[4]}  ⟵ `{r[1]}`", ""]
        inp = os.path.join(d, f"S2-CHECK-INPUT-{a.tag}.md")
        open(inp, "w", encoding="utf-8").write("\n".join(out) + "\n")
        extra = ("**Ĉi-foje** nur la rilataj specoj (renkonto, konflikto, interkonsento, influo): ĉu ĉiu grupo estas unu okazo? "
                 "Malsama priskribo de la sama okazo ne faras alian okazon; alia kaŭzo, alia letero aŭ alia jaro faras.") if kinds else ""
        brief = (tpl.replace("{name}", name).replace("{tag}", a.tag).replace("{input}", inp).replace("{profile}", frozen)
                    .replace("{ng}", str(len(pick))).replace("{nn}", str(len(noms))).replace("{extra}", extra))
        open(os.path.join(d, f"S2-CHECK-BRIEF-{a.tag}.md"), "w", encoding="utf-8").write(brief)
        print(f"{stem}: {len(pick)} groups, {len(noms)} nominations → S2-CHECK-BRIEF-{a.tag}.md")

def sizes(a):
    """Profile sizes for choosing smelt tests (the editor, 2026-10-16): by lines from dowse files, the lines a smelt
    with --kinded-only freezes; people the scope register has out (entities too) left out. Reads only."""
    # by profile file, as the harvest wrote them: a surname of two people is already split there by qualifier (the first
    # version counted FACTS-LIST by bare surname and so «mixed» René and Charles Lemaire, whose profiles are apart)
    from collections import Counter, defaultdict
    n, allc, srcs, one = Counter(), Counter(), defaultdict(set), Counter()
    pdir = os.path.join(G, "profiles")
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".md") or fn.isupper() or fn.startswith("ENTITY"): continue
        txt = open(os.path.join(pdir, fn), encoding="utf-8").read()
        if "Ekster la amplekso laŭ la registro de amplekso" in txt[:3000]: continue      # out of scope, entities too
        w = fn[:-3]
        for l in txt.split("\n"):
            if not l.startswith("- $$$"): continue
            allc[w] += 1
            m = re.search(r"⟵ `([^`]*-dowse\.md)`", l)
            if m:
                n[w] += 1; srcs[w].add(m.group(1))
                if m.group(1) == a.source: one[w] += 1
    if a.source:
        sm = os.path.join(G, "smelt")
        old = lambda w: os.path.isdir(os.path.join(sm, w))
        ppl = sorted(((c, w) for w, c in one.items()), reverse=True)
        print(f"people with lines from {a.source}, in scope: {len(ppl)}; lines: {sum(one.values())}")
        asc = sorted(c for c, _ in ppl)
        if asc: print("median, 75th, 90th, 99th percentile: " + ", ".join(str(asc[min(len(asc) - 1, int(len(asc) * q))]) for q in (0.5, 0.75, 0.9, 0.99)))
        for i, (c, w) in enumerate(ppl[:a.sizes], 1):
            print(f"{i:4}. {w}: {c} from it; {n[w]} dowse lines, {len(srcs[w])} dowse files{' · smelt folder already' if old(w) else ''}")
        print("with a smelt folder already: " + ", ".join(f"{w} ({c} from it)" for c, w in ppl if old(w)))
        return
    ppl = sorted(((c, w) for w, c in n.items()), reverse=True)
    print(f"people with dowse lines, in scope: {len(ppl)}; lines: {sum(c for c, _ in ppl)}")
    asc = sorted(c for c, _ in ppl)
    qs = [asc[min(len(asc) - 1, int(len(asc) * q))] for q in (0.5, 0.75, 0.9, 0.99)] if asc else []
    print("median, 75th, 90th, 99th percentile: " + ", ".join(map(str, qs)))
    for i, (c, w) in enumerate(ppl[:a.sizes], 1):
        print(f"{i:4}. {w}: {c} dowse lines, {len(srcs[w])} dowse files, {allc[w]} lines in all")
    for p in a.people:
        name = p.partition("=")[2] or p
        rk = next((i for i, (c, w) in enumerate(ppl, 1) if w == name), None)
        print(f"{name}: rank {rk} of {len(ppl)}, {n.get(name, 0)} dowse lines" if rk else f"{name}: not found among people with dowse lines")
    small = [(c, w) for c, w in ppl if 20 <= c <= 40 and len(srcs[w]) >= 3]
    print(f"small-test candidates (20–40 dowse lines, 3+ dowse files): {len(small)}")
    for c, w in small[:25]:
        print(f"      {w}: {c} lines, {len(srcs[w])} files: {', '.join(sorted(f[:-9] for f in srcs[w]))}")

def s4_body(stem, name, frozen, profilo, ret, singles, short=False, fontoj_block=None, registro=None, on_lines=False):
    """The S4 brief from the template, filled: (text, the sources line, the profile's line count). The sources are
    counted on the whole frozen profile; {profilo} may be another file (a period's excerpt, tools/smelt-periods.py --s4).
    Fable's proposals (2026-10-30; tools/smelt_inputs.py): short, the excerpt is in the short form, and the template's
    line-form sentence says so; fontoj_block, the sources line on the reader's own lines, by siglum, in place of the
    whole profile's; registro, the register cut to the part's names, its «atestita» column in place of the evidence
    file; on_lines, the single-line groups' U numbers stand on the excerpt's lines, and no singles file is named."""
    tpl = open(os.path.join(G, "ocr", "method", "BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md"), encoding="utf-8").read()
    body = "## La briefo" + tpl.split("## La briefo", 1)[1]
    import smelt_inputs as SI
    if short:
        if SI.S4_FULL not in body: sys.exit("refusing: the S4 template's line-form sentence has changed; smelt_inputs.S4_FULL")
        body = body.replace(SI.S4_FULL, SI.SHORT_S4, 1)
    if on_lines:
        if "(`{unuopaj}`)" not in body: sys.exit("refusing: the S4 template has no «(`{unuopaj}`)»")
        body = body.replace("(`{unuopaj}`)", "(ĉiu linio de la eltiraĵo de la profilo, kiu estas unuopa grupo, portas sian "
                                              "U-numeron post la L-numero: «L88 (U39)»)", 1)
    ATESTO = "(`{atesto}`: la vicoj de la registro kun la linioj de la korpuso, kiuj ilin diras)"
    if registro:
        if ATESTO not in body: sys.exit("refusing: the S4 template's sentence on {atesto} has changed")
        body = body.replace(ATESTO, "(«jes» en la kolumno «atestita» de la registro: la korpuso diras la vicon)", 1)
    # the sources, each line counted once (2026-10-16, Devjatnin: Neves's 12 of 32 lines left out, his item name holding
    # spaces; the editor to the two fixes): the source from the line's own file
    # («⟵ `neves-parnaso-dowse.md`»), the item's name from the locator only as its label; and every line must be
    # counted, else the brief is refused, naming the lines
    srcs, label, total, loose = {}, {}, 0, []
    for i, l in enumerate(open(frozen, encoding="utf-8"), 1):
        if not l.startswith("- $$$"): continue
        total += 1
        fm = re.search(r"⟵ `([^`]+)`", l)
        im = re.search(r" · ([^·]+?), (?:PDF|¶|p\.|pĝ|l\.)", l)
        if not fm: loose.append(f"L{i}"); continue
        # each work by its item, not each dowse file by its first item (2026-10-18, de-beaufront-B9: neves-steele-2022
        # missing from the list, its lines counted under the Neves dowse file's first item, Parnaso)
        # the item key from the locator field only (a fact holding «, p.» is not one), a periodical's issues
        # («ruslandaesperantisto1906-9») counted under its title
        lm = re.search(r" · ([A-Za-z0-9._-]+), (?:PDF|¶) ?\d", l)
        k = lm.group(1) if lm else fm.group(1)
        pm = re.match(r"^([a-z]+)\d{4}(?:[-.][\d-]+)?$", k)
        if pm: k = pm.group(1)
        srcs[k] = srcs.get(k, 0) + 1
    if loose or sum(srcs.values()) != total:
        sys.exit(f"refusing: {stem} {len(loose)} of {total} profile lines have no source file ({', '.join(loose[:20])})")
    srcs = {label.get(k, re.sub(r"(-dowse)?\.md$", "", k)): v for k, v in srcs.items()}
    fontoj = fontoj_block or "; ".join(f"{k} ({v} linioj)" for k, v in sorted(srcs.items(), key=lambda x: -x[1]))
    b = (body.replace("{persono}", name).replace("{profilo}", profilo).replace("{epizodoj}", ret)
             .replace("{unuopaj}", singles or "(neniu: la epizoda legilo skribis ĉiujn grupojn)")
             .replace("{registro}", registro or os.path.join(G, "profiles", "NAMES-REGISTER.tsv")).replace("{fontoj}", fontoj or "(neniu trovita)")
             # the rows the corpus attests (tools/register-evidence.py, 2026-10-17: ∴, not ◊?)
             .replace("{atesto}", os.path.join(G, "profiles", "NAMES-REGISTER-EVIDENCE.tsv")))
    return b, fontoj, total

def _slug(h):
    """A head's profile file name (the harvest's): the qualifier dropped, accents folded, «MAC KENZIE» → mac-kenzie."""
    import unicodedata
    h = re.sub(r"\s*\(.*", "", h)
    h = "".join(c for c in unicodedata.normalize("NFD", h.upper()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")

def _moved_away(name):
    """The lines the sinter moved one by one from this head to another (the editor, 2026-11-09 14:4x): each dowse folder's DECISIONS.tsv «name» or «qualifier» row
    (locator · phrase · kind · value) gives the line and its new head; the readers' returns (dowse/<source>/facts-return-*.md,
    the joined ones, not the -pN pieces) give the head the reader wrote, the line matched as the assembler matches it (the
    locator in the line, the phrase in the line). Returns [(new head, the return's line, the ruling, the source)] for the
    lines a reader wrote under this head and a row moved to another head, or split off under a qualifier. Lines moved INTO
    this head (variant spellings) are not namesakes and are left out."""
    import glob
    global _ASM
    if _ASM is None:   # the assembler's own expand_lean and locator forms: a return's lean «(prese M) l. K» → the full locator
        spec = importlib.util.spec_from_file_location("dfa", os.path.join(ROOT, "tools", "dowse-facts-assemble.py"))
        _ASM = importlib.util.module_from_spec(spec); spec.loader.exec_module(_ASM)
        _ASM.form_repair("- $$$ X $$$")
    HF = _ASM._HF
    def forms(dl):   # the row's locator by key and by the file's name (the assembler's _other_form), each also without «, l. N»
        alt = dl
        for n_, k_ in HF.unsafe_names().items():
            if dl.startswith(n_ + ","): alt = k_ + dl[len(n_):]; break
        else:
            it = dl.split(",")[0].strip(); rest = dl[len(dl.split(",")[0]):]
            k_ = HF.item_key(it)
            alt = k_ + rest if k_ != it else ((HF.key_names().get(it) or it) + rest if HF.key_names().get(it) else dl)
        full = {dl, alt}
        return full, {re.sub(r", l\. ?\d+\s*$", "", x) for x in full}
    me, out, seen = _slug(name), [], set()
    for dp in sorted(glob.glob(os.path.join(G, "dowse", "*", "DECISIONS.tsv"))):
        D = os.path.dirname(dp)
        rows = []
        for x in open(dp, encoding="utf-8"):
            r = x.rstrip("\n").split("\t")
            if x.startswith("#") or len(r) < 4 or r[0] == "locator" or r[2] not in ("name", "qualifier"): continue
            if r[2] == "name" and _slug(r[3]) == me: continue                 # moved into this head: the same man
            rows.append(r + [""] * (5 - len(r)) + [forms(r[0])])
        if not rows: continue
        rets = sorted(glob.glob(os.path.join(D, "facts-return-*.md")))
        joined = set(rets)
        rets = [p for p in rets if not (re.search(r"-p\d+\.md$", p) and re.sub(r"-p\d+\.md$", ".md", p) in joined)]
        for p in rets:
            for l in open(p, encoding="utf-8"):
                m = re.match(r"- \$\$\$ (.+?) \$\$\$", l)
                if not m or _slug(m.group(1)) != me: continue
                l = _ASM.expand_lean(D, os.path.basename(p), l.rstrip("\n"))
                for r in rows:
                    full, page = r[-1]
                    if r[1] in l and (any(x in l for x in full) or any(x in l for x in page)):
                        if r[2] == "qualifier" and _slug(r[3]) != me: continue    # a qualifier row of another head
                        k = l.strip()
                        if k in seen:   # one line, two rows (a qualifier, then a name): the name row's head stands
                            if r[2] == "name": out = [(r[3] if x[1] == k[2:] else x[0],) + x[1:] for x in out]
                            continue
                        seen.add(k); out.append((r[3], k[2:], r[4], os.path.basename(D)))
    return out
_ASM = None

SAM_ANCHOR = "la baptan nomon, la formojn de la fontoj kaj ĉiun pseŭdonimon, ankaŭ tiun, kiu jam staras en alia sekcio."

def samnomuloj(stem, name, frozen, d, btag, b):
    """THE NAMESAKES (the editor, 2026-11-09 14:3x): writes
    smelt/<stem>/SAMNOMULOJ-<tag>.md and asks the writer, in the brief, for «Samnomuloj» under «Nomoj», one line a namesake.
    Gathered, no tokens: (1) the frozen profile's {samnomo} lines; (2) its lines by qualifier («**(Math.)**»), every
    qualifier with its count and L numbers, the subject's own among them, for the writer to tell apart; (3) the heads of
    profiles/FOLD-RULINGS.tsv ruled «two» beside this head, and those this head's lines were folded away to («same», a =
    this head, b another: the sinter's split, Lambert DELVAUX from DERVAUX), each with up to 8 lines of its own profile;
    (4) the lines the sinter moved one by one to another head (_moved_away: DECISIONS.tsv joined to the readers' returns).
    Refused if the template's «Nomoj» sentence has changed."""
    if SAM_ANCHOR not in b: sys.exit("refusing: the S4 brief has no «Nomoj» sentence to follow with the namesakes' paragraph (SAM_ANCHOR)")
    sp = sam_file(stem, name, frozen, d, btag)
    import smelt_inputs as SI
    para = (f"\n\n**Samnomuloj** (la redaktoro, 2026-11-09: sub «Nomoj» subsekcio pri la samnomuloj, de kiuj la dovado devas distingi la temojn; "
            f"por ĉiu nur unu linio: priskribo, antaŭnomo, urboj, profesio): en la sekcio «Nomoj» (se ĝi "
            f"mankas, skribu ĝin, antaŭ «Kie troviĝas la fontoj»), fine, la subsekcio «**Samnomuloj**»: " + SAM_RULE.format(name=name) +
            f" La enigo: `{SI.paths(SI.for_reader(sp))}` " + SAM_INPUT + " Linio de la profilo, kiu estas pri samnomulo, ne iras en la "
            f"biografion: nomu ĝin en la raporto (4).")
    return b.replace(SAM_ANCHOR, SAM_ANCHOR + para, 1)

SAM_RULE = ("unu linio por ĉiu persono, de kiu la fakt-eltirado devis distingi {name}: la nomo kiel presita, la antaŭnomo, la urboj, la profesio, "
            "kaj kio lin distingas, kun la citaĵo (L-numero por linio de la profilo; por alia kapo, la kapo kaj ĝia fonto). Ne listigu lin mem "
            "nek lian familion, kiun la biografio jam nomas; se neniu restas, skribu «Neniuj samnomuloj en la fakt-eltirado.»")
SAM_INPUT = ("(la linioj «samnomo»; la kvalifikoj de la profilo, el kiuj vi elektas tiujn, kiuj ne estas li; la kapoj apartigitaj de la "
             "fandado; la linioj, kiujn la fandado movis unu post unu al alia kapo, ĉiu sub sia nova kapo).")

def sam_brief(a):
    """THE SECOND ROUTE (the editor, 2026-11-09 14:5x): «Samnomuloj» for a
    biography written without it (Emeric, batch 1, Collinson) or on the periods route (after smelt-periods.py --s4-join):
    SAMNOMULOJ-<tag>.md as for the brief, and S4-SAMNOMULOJ-BRIEF-<tag>.md for one small writer (file-reader-writer), who
    writes S4-SAMNOMULOJ-<tag>.md, the subsection alone; smelt-s4-view.py puts it at the end of «Nomoj». Refuses where the
    return is missing, already holds «Samnomuloj», or the brief or its return exists."""
    import smelt_inputs as SI
    for p in a.people:
        stem, _, name = p.partition("=")
        d = os.path.join(G, "smelt", stem)
        frozen, ret = os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md"), os.path.join(d, f"S4-RETURN-{a.tag}.md")
        for f in (frozen, ret):
            if not os.path.exists(f): sys.exit(f"refusing: {os.path.relpath(f, G)} is missing")
        if "Samnomuloj" in open(ret, encoding="utf-8").read(): sys.exit(f"refusing: {stem}'s S4-RETURN-{a.tag}.md already has «Samnomuloj»")
        bp, op = os.path.join(d, f"S4-SAMNOMULOJ-BRIEF-{a.tag}.md"), os.path.join(d, f"S4-SAMNOMULOJ-{a.tag}.md")
        for f in (bp, op):
            if os.path.exists(f): sys.exit(f"refusing: {os.path.relpath(f, G)} exists")
        sp = sam_file(stem, name, frozen, d, a.tag)
        if open(sp, encoding="utf-8").read().count("(neniu)") == 4:   # nothing gathered: no writer, the line by tool
            with open(op, "x", encoding="utf-8") as fh:
                fh.write("**Samnomuloj**\n\nNeniuj samnomuloj en la fakt-eltirado.\n\nFino: 0 samnomuloj.\n")
            print(f"{stem}: nothing gathered → S4-SAMNOMULOJ-{a.tag}.md by tool («Neniuj samnomuloj en la fakt-eltirado.»), no brief"); continue
        brief = (f"# La samnomuloj de {name} (smelt S4, {a.tag})\n\n`[tools/smelt-s2-prep.py --samnomuloj: the second route, for a biography "
                 f"written without «Samnomuloj»; smelt-s4-view.py puts the return at the end of «Nomoj».]`\n\n## La briefo\n\n"
                 f"La biografio de {name} estas jam skribita: `{SI.paths(SI.for_reader(ret))}`. Legu ĝin por scii, kiu li estas, sed ne "
                 f"reverku ĝin. Al ĝi mankas la subsekcio «Samnomuloj» de la sekcio «Nomoj» (la redaktoro, 2026-11-09: sub «Nomoj» subsekcio pri "
                 f"la samnomuloj, de kiuj la dovado devas distingi la temojn; por ĉiu nur unu linio: priskribo, "
                 f"antaŭnomo, urboj, profesio). Skribu nur ĝin: " + SAM_RULE.format(name=name) + f"\n\nLa enigo: `{SI.paths(SI.for_reader(sp))}` "
                 + SAM_INPUT + f" La L-numeroj estas tiuj de la profilo `{frozen}`: legu de ĝi nur la liniojn, kiujn vi bezonas (la "
                 f"parametroj offset kaj limit de Read).\n\nLa formo: la unua linio «**Samnomuloj**», malplena linio, tiam unu ero de listo "
                 f"por ĉiu: «- **‹la nomo kiel presita›** (‹antaŭnomo›; ‹urboj›; ‹profesio›): ‹kio lin distingas› (‹citaĵo›).» Esperante, "
                 f"kiel la biografio. Kio estas necerta (ĉu li aŭ alia), diru tion per «◊?» en la linio.\n\nSkribu per Write la dosieron "
                 f"`{op}`, tutan, unufoje. Via fina mesaĝo estas nur la linio «Fino: ‹N› samnomuloj.»\n")
        with open(bp, "x", encoding="utf-8") as fh: fh.write(brief)
        print(f"{stem}: → S4-SAMNOMULOJ-BRIEF-{a.tag}.md; launch (file-reader-writer): Read the brief {bp} and carry out the task it gives, "
              f"section «La briefo». Your final message is the line the brief asks for.")

GIST_END = ("Kie troviĝas la fontoj", "Verkoj laŭ la fontoj", "La malfermitaj konfliktoj", "Notoj pri malgravaj malkongruoj", "Nomoj",
            "La nomoj", "Samnomuloj", "Enhavo", "Aldonoj")

def gist_brief(a):
    """THE GIST FOR ONE WRITER (the editor, 2026-11-09 15:1x; the periods
    route's own, smelt-periods.py --s4-gist, 2026-10-22): from S4-RETURN-<tag>.md's
    part (1), the abstract and the biography's sections (not the names, the sources, the works, the conflicts, the
    discrepancies), the line citations taken out, in the three parts of tools/smelt_parts.py, for one small writer
    (file-reader-writer), who writes S4-GIST-<tag>.md beside the biography. Refuses where the return is missing, where
    S4-RETURN-<tag>-p* parts exist (the periods route: smelt-periods.py --s4-gist), or the brief or the gist exists."""
    import smelt_parts
    for p in a.people:
        stem, _, name = p.partition("=")
        d = os.path.join(G, "smelt", stem)
        ret = os.path.join(d, f"S4-RETURN-{a.tag}.md")
        if not os.path.exists(ret): sys.exit(f"refusing: {os.path.relpath(ret, G)} is missing")
        if any(re.fullmatch(rf"S4-RETURN-{re.escape(a.tag)}-p\w+\.md", f) for f in os.listdir(d)):
            sys.exit(f"refusing: {stem} was written in periods; its gist is smelt-periods.py {stem} {a.tag} --s4-gist")
        bp, op = os.path.join(d, f"S4-GIST-BRIEF-{a.tag}.md"), os.path.join(d, f"S4-GIST-{a.tag}.md")
        for f in (bp, op):
            if os.path.exists(f): sys.exit(f"refusing: {os.path.relpath(f, G)} exists")
        lines = open(ret, encoding="utf-8").read().split("\n")
        s = next((i for i, l in enumerate(lines) if l.startswith("## 1.")), None)
        if s is None: sys.exit(f"refusing: {stem}'s return has no «## 1.»")
        e = next((i for i, l in enumerate(lines) if i > s and re.match(r"^## \d", l)), len(lines))
        secs, cur = [("Resumo", [])], None
        for l in lines[s + 1:e]:
            m = re.match(r"^#{3,4} (?:\d+\. )?(.+?)\s*$", l)
            if m: secs.append((m.group(1), [])); continue
            if l.startswith("#"): continue
            if "⚫️: truo" in l: continue    # the marks' legend (2026-11-09, Süssmuth: it made a second «La resumo»)
            secs[-1][1].append(l)
        clean = lambda t: re.sub(r"\s*\[(?:L\d|vd\. fontoj)[^\]]*\]", "", t).strip()
        # end matter, «La» or not, any case (2026-11-09, Barthel: the writer's «5. Malfermitaj konfliktoj» went into the gist)
        lan = lambda t: re.sub(r"^la\s+", "", t.strip().lower())
        endish = lambda t: any(lan(t).startswith(lan(x)) for x in GIST_END)
        keep = [(t, clean("\n".join(ls))) for t, ls in secs if not endish(t) and clean("\n".join(ls))]
        dy = smelt_parts.death_year(d, a.tag)
        yr = lambda t: re.search(r"\b(1[5-9]\d\d|20\d\d)\b", t)
        last = max((i for i, (t, _) in enumerate(keep) if t != "Resumo" and yr(t)), default=-1)
        body, cur = [], None
        for i, (t, x) in enumerate(keep):
            if t == "Resumo": body += ["### La resumo", "", x, ""]; continue
            pt = smelt_parts.part_any(t, dy) if yr(t) else (cur if isinstance(cur, int) and i < last else (0 if i < last else 2))
            if pt != cur: cur = pt; body += [f"### {smelt_parts.TITLES[pt]}", ""]
            body += [f"#### {t}", "", x, ""]
        words = len(re.findall(r"\w+", "\n".join(x for _, x in keep)))
        brief = (f"# La skiza biografio de {name} (smelt S4, {a.tag}, por ne-fakuloj)\n\n`[tools/smelt-s2-prep.py --gist: the abstract and "
                 f"the sections of S4-RETURN-{a.tag}.md, part (1), without the names, sources, works, conflicts and discrepancies, the line "
                 f"citations taken out, in the parts of tools/smelt_parts.py.]`\n\n## La briefo\n\n"
                 f"Vi verkas skizan biografion por esplora projekto pri la historio de la internaciaj helplingvoj. Legu nur ĉi tiun "
                 f"briefon: ne rulu ŝelajn komandojn, ne faru retajn serĉojn. Skribu en Esperanto.\n\nSube estas la plena biografio de "
                 f"{name} ({words} vortoj), ĝia resumo kaj ĝiaj sekcioj, en ĝiaj partoj. **Verku el ĝi unu fluan biografion por "
                 f"legantoj, kiuj ne estas fakuloj:** prozo, ne listo; la partoj kiel titoloj `## …` (`## La vivo`, `## Post la morto`, "
                 f"`## La persono`, nur tiuj, kiuj estas sube); alineoj laŭ la temo. Por la legebleco vi rajtas preterlasi detalojn "
                 f"(nomojn de malgravaj personoj, titolojn de artikoloj, numerojn, adresojn), sed ne aldonu ion, kio ne estas sube, kaj "
                 f"ne ŝanĝu ĝian sencon. Kunigu, kio ripetiĝas. Sen niaj markoj (=, ∴, ◊?, ⚫️): kie la biografio dubas aŭ diras, ke la "
                 f"fontoj malkonsentas aŭ silentas, diru tion per vortoj («eble», «laŭ Jossinet», «la fontoj ne diras»). Titoloj de "
                 f"libroj kaj gazetoj kursive. Proksimume triono de la longo de la biografio, ne pli ol 600 vortoj.\n\n"
                 f"**La dosiero:** skribu per Write `{op}`, tutan, unufoje: la unua linio «# La skiza biografio de ‹lia plena nomo, kiel "
                 f"la resumo ĝin donas, ne «{name}»›», malplena "
                 f"linio, tiam la biografio de la unua titolo `##`, kaj fine la linio «Fino.». Via fina mesaĝo estas nur «Fino.»\n\n"
                 f"## La biografio\n\n" + "\n".join(body) + "\n")
        with open(bp, "x", encoding="utf-8") as fh: fh.write(brief)
        print(f"{stem}: {len(keep) - 1} sections and the abstract, {words} words, the death {dy or 'not in the profile'} → S4-GIST-BRIEF-{a.tag}.md;"
              f" launch (file-reader-writer): Read the brief {bp} and carry out the task it gives, section «La briefo». Your final message"
              f" is the line the brief asks for.")

def sam_file(stem, name, frozen, d, btag):
    """The namesakes' input, SAMNOMULOJ-<tag>.md (create-only), for the brief's paragraph or the second route."""
    me = _slug(name)
    prof = open(frozen, encoding="utf-8").read().split("\n")
    lines = [(i, l) for i, l in enumerate(prof, 1) if l.startswith("- $$$")]
    sam = [(i, l) for i, l in lines if re.search(r" · \{samnomo", l)]
    quals = {}
    for i, l in lines:
        m = re.search(r"\*\*\(([^)]*)\)\*\*", l)
        if m: quals.setdefault(m.group(1), []).append(i)
    other = []
    for l in open(os.path.join(G, "profiles", "FOLD-RULINGS.tsv"), encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        f = l.rstrip("\n").split("\t")
        if len(f) < 3: continue
        x, y, v = _slug(f[0]), _slug(f[1]), f[2]
        if v == "two" and me in (x, y): other.append((y if x == me else x, f"«two», {f[3] if len(f) > 3 else ''} {f[4] if len(f) > 4 else ''}".strip()))
        elif v == "same" and x == me and y != me: other.append((y, f"lines of {f[0]} folded to {f[1]} («same», {f[4] if len(f) > 4 else ''}): a namesake split off"))
    out = [f"# Samnomuloj de {name} ({btag})", "",
           "`[tools/smelt-s2-prep.py --biography: the namesakes the dowse told the subject from, gathered by tool; the writer's input for"
           " «Samnomuloj» under «Nomoj».]`", "",
           f"## 1. La linioj de la profilo kun la speco «samnomo» ({len(sam)})", ""]
    out += [f"- L{i}: {l[2:]}" for i, l in sam] or ["(neniu)"]
    out += ["", f"## 2. La kvalifikoj de la profilo ({len(quals)}): ĉiu kun siaj linioj; unu aŭ pluraj estas la persono mem", ""]
    out += [f"- «{q}»: {len(ns)} linioj, " + ", ".join(f"L{n}" for n in ns) for q, ns in sorted(quals.items(), key=lambda x: -len(x[1]))] or ["(neniu)"]
    # THE HEAD'S OTHER PEOPLE, LEFT OUT OF A FREEZE BY QUALIFIER (2026-11-10): each with its count and three of its lines
    fz = open(frozen, encoding="utf-8").read() if os.path.exists(frozen) else ""
    if "**Smelt: nur la " in fz[:3000] and os.path.exists(os.path.join(G, "profiles", f"{stem}.md")):
        full = [l for l in open(os.path.join(G, "profiles", f"{stem}.md"), encoding="utf-8").read().split("\n") if l.startswith("- $$$")]
        keepset = {l for l in fz.split("\n") if l.startswith("- $$$")}
        byq = {}
        for l in full:
            if l in keepset: continue
            m = re.search(r"\*\*\(([^)]*)\)\*\*", l); byq.setdefault(m.group(1) if m else "sen kvalifiko", []).append(l)
        out += ["", f"## 2b. La aliaj personoj de la kapo, forlasitaj de la frosto laŭ kvalifiko ({len(byq)}): ili NE estas la persono", ""]
        for q, ls in sorted(byq.items(), key=lambda x: -len(x[1])):
            out += [f"### «{q}» ({len(ls)} linioj en profiles/{stem}.md)", ""] + [f"- {re.sub(r'  ⟵ `[^`]*`$', '', l[2:])[:420]}" for l in ls[:3]] + [""]
    out += ["", f"## 3. Aliaj kapoj, kiujn la fandado (sinter) apartigis de ĉi tiu ({len(other)})", ""]
    if not other: out.append("(neniu)")
    for s, why in other:
        p = os.path.join(G, "profiles", f"{s}.md")
        ol = [l for l in open(p, encoding="utf-8").read().split("\n") if l.startswith("- $$$")] if os.path.exists(p) else []
        out += [f"### {s} ({why}; {len(ol)} linioj en profiles/{s}.md{', ne trovita' if not os.path.exists(p) else ''})", ""]
        out += [f"- {re.sub(r'  ⟵ `[^`]*`$', '', l[2:])[:420]}" for l in ol[:8]] + ([f"- … ({len(ol) - 8} pliaj)"] if len(ol) > 8 else []) + [""]
    moved = _moved_away(name)
    heads = {}
    for v, l, why, src in moved: heads.setdefault(v, []).append((l, why, src))
    out += [f"## 4. Linioj, kiujn la fandado movis unu post unu de ĉi tiu kapo al alia ({len(moved)} linioj, {len(heads)} kapoj; DECISIONS.tsv)", ""]
    if not heads: out.append("(neniu)")
    for v, ls in sorted(heads.items(), key=lambda x: -len(x[1])):
        out += [f"### → {v} ({len(ls)} linioj)", ""]
        out += [f"- {l[:420]} ⟵ `{src}` · *{why[:160]}*" for l, why, src in ls[:8]] + ([f"- … ({len(ls) - 8} pliaj)"] if len(ls) > 8 else []) + [""]
    sp = os.path.join(d, f"SAMNOMULOJ-{btag}.md")
    with open(sp, "x", encoding="utf-8") as fh: fh.write("\n".join(out) + "\n")
    print(f"{stem}: samnomuloj: {len(sam)} «samnomo» lines, {len(quals)} qualifiers, {len(other)} heads apart, {len(moved)} lines moved away"
          f" to {len(heads)} heads → SAMNOMULOJ-{btag}.md")
    return sp

def biography(a):
    """Smelt S4 (the runbook, S4; 2026-10-15, the Fable review 17: the brief had been filled by hand): for each person, the
    brief from ocr/method/BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md on smelt/<stem>/PROFILE-FROZEN-<tag>.md and
    S3-RETURN-<tag>.md, with the profile's sources and their line counts. Writes S4-BRIEF-<tag>.md; refuses when the
    episode return is missing, or the brief or its return exists."""
    for p in a.people:
        stem, _, name = p.partition("=")
        d = os.path.join(G, "smelt", stem)
        frozen, ret = os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md"), os.path.join(d, f"S3-RETURN-{a.tag}.md")
        # «--as T»: a second biography from the same episodes, its files named for T (2026-10-17: Bourlet rewritten
        # under the day's template changes, the register's evidence, the notes, «dubindikoj», to test them)
        btag = a.as_tag or a.tag
        out = os.path.join(d, f"S4-BRIEF-{btag}.md")
        if a.straight:   # no episodes: the reader's share, unread, in their place (the help of --straight)
            if os.path.exists(ret): sys.exit(f"refusing: --straight, but {os.path.relpath(ret, G)} exists; use the full route")
            if not os.path.exists(os.path.join(d, f"S3-COMPRESSED-{a.tag}.md")):
                sys.exit(f"refusing: --straight needs smelt/{stem}/S3-COMPRESSED-{a.tag}.md (smelt-compress.py {stem} {a.tag} --skip-unkinded)")
            if not os.path.exists(frozen): sys.exit(f"refusing: {os.path.relpath(frozen, G)} is missing")
            nk = sum(1 for l in open(frozen, encoding="utf-8") if l.startswith("- $$$") and re.search(r" · \{(?!samnomo)[^}]", l))
            if not 10 <= nk <= 19: sys.exit(f"refusing: --straight is for 10–19 kinded lines (the runbook, «Open» 8); {stem} has {nk}")
            ret = os.path.join(d, f"S3-INPUT-{a.tag}-reader.md")
        for f in (frozen, ret):
            if not os.path.exists(f): sys.exit(f"refusing: {os.path.relpath(f, G)} is missing")
        exists = [f for f in (out, os.path.join(d, f"S4-RETURN-{btag}.md")) if os.path.exists(f)]
        sp = os.path.join(d, f"S3-SINGLES-{a.tag}.md")
        # THE COMPRESSED ROUTE (the smelt pilot, 2026-10-30; tools/smelt-compress.py): where the tag has a compressed
        # chronology, it stands in place of the singles, and one paragraph says what it holds
        cp = os.path.join(d, f"S3-COMPRESSED-{a.tag}.md")
        if os.path.exists(cp):
            # FABLE'S PROPOSALS 1, 2, 4, 5 on the single writer (2026-10-30; tools/smelt_inputs.py): the profile in the
            # short form (S4-LINES-<tag>.md), the sources by siglum, the register cut to the names, every file whole in one Read
            import smelt_inputs as SI
            label = SI.labels(d, a.tag)
            prof = open(frozen, encoding="utf-8").read().split("\n")
            nums = [i + 1 for i, l in enumerate(prof) if l.startswith("- $$$")]
            body = [SI.short(n, prof[n - 1], label.get(n)) for n in nums]
            lp = os.path.join(d, f"S4-LINES-{btag}.md")
            open(lp, "w", encoding="utf-8").write(
                f"# S4 of {stem} ({a.tag}): the profile's lines\n\n`[tools/smelt-s2-prep.py --biography: the {len(nums)} lines of "
                f"PROFILE-FROZEN-{a.tag}.md, each headed by its L, in the short form (tools/smelt_inputs.py).]`\n\n" + "\n".join(body) + "\n")
            rp, _, _ = SI.register("\n".join(body) + "\n" + open(ret, encoding="utf-8").read(), os.path.join(d, f"NAMES-REGISTER-{btag}.tsv"))
            b, fontoj, total = s4_body(stem, name, frozen, SI.paths(SI.for_reader(lp)), SI.paths(SI.for_reader(ret)), SI.paths(SI.for_reader(cp)),
                                       short=True, fontoj_block=SI.sources(nums, lambda n: prof[n - 1], label), registro=rp)
        else:
            b, fontoj, total = s4_body(stem, name, frozen, frozen, ret, sp if os.path.exists(sp) else None)
        if os.path.exists(cp):
            anchor = f"La fontoj de la profilo kaj iliaj jaroj: {fontoj}."
            if anchor not in b: sys.exit(f"refusing: {stem} the brief has no sources line to follow with the compressed route's paragraph")
            if a.straight:
                b = b.replace(anchor, anchor + (
                    f"\n\n**Rekte al la biografio** (profilo de 10–19 linioj kun speco; la regularo de la fandado, «Open» 8). Neniu "
                    f"epizoda legilo legis ĉi tiun profilon: ne estas epizodoj (E…) nek grupoj de legilo. La fonto (1a) estas la kronologio "
                    f"de la ilo `smelt-compress.py`, `{SI.paths(SI.for_reader(cp))}`: la grupoj, kies linioj konsentas (G…), la daŭroj (S…), "
                    f"la rutinaj specoj resumitaj (R…) kaj la unuopaj linioj (U…). La dosiero nomita kiel la epizodoj, "
                    f"`{SI.paths(SI.for_reader(ret))}`, estas la parto, kiun la ilo ne skribas (juĝoj, rilatoj, malsamoj), ne legita de "
                    f"iu legilo: legu ĝiajn liniojn mem. Skribu la biografion rekte el ambaŭ, citante la liniojn per iliaj L; ne citu "
                    f"epizodojn, kaj en la raporto (2) diru «neniuj epizodoj» anstataŭ listo. La linioj sen speco (formatoj 2 kaj 3) "
                    f"estas forlasitaj."), 1)
            else: b = b.replace(anchor, anchor + (
                f"\n\n**La kunpremita vojo** (la piloto de `ocr/method/SMELT-EFFICIENCY-PROPOSAL-2026-10-29.md`). La fonto (1a) "
                f"estas ĉi tie la kronologio de la ilo `smelt-compress.py`, `{SI.paths(SI.for_reader(cp))}`, laŭ dato kaj en periodoj: la grupoj, kies "
                f"linioj konsentas (G…, kun la plej preciza linio kiel aserto kaj la nombro de lokoj), la daŭroj de ofico, profesio "
                f"kaj loĝado (S…), la rutinaj specoj resumitaj (R…), kaj la unuopaj linioj (U…). La epizoda legilo legis nur la "
                f"parton, kiun la ilo ne povas skribi (juĝoj, rilatoj, malsamoj), kaj ĝiaj epizodoj citas la erojn de la kronologio "
                f"per iliaj numeroj. Skribu la biografion el la epizodoj kaj la kronologio kune; la linioj sen speco (formatoj 2 "
                f"kaj 3) estas forlasitaj en ĉi tiu provo."), 1)
        if exists:   # refused after the list, so a refused run shows it (a dry test on a run already briefed)
            sys.exit(f"refusing: {os.path.relpath(exists[0], G)} exists; the sources it would list ({total} lines): {fontoj}")
        b = samnomuloj(stem, name, frozen, d, btag, b)
        head = (f"# La biografio de {name} (smelt S4, {a.tag})\n\n`[tools/smelt-s2-prep.py --biography, from "
                f"ocr/method/BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md on PROFILE-FROZEN-{a.tag}.md and "
                + (f"S3-COMPRESSED-{a.tag}.md with S3-INPUT-{a.tag}-reader.md (--straight: no episode reader).]`\n\n" if a.straight else f"S3-RETURN-{a.tag}.md.]`\n\n"))
        if os.path.exists(cp):   # the writer writes in pieces (smelt_pieces.py; the pilot, 2026-10-30), as smelt-periods.py's do
            import smelt_pieces
            b = smelt_pieces.add(b, os.path.join(d, f"S4-RETURN-{btag}.md"))
        with open(out, "x", encoding="utf-8") as f: f.write(head + b)
        print(f"{stem}: {len(fontoj.split('; ')) if fontoj else 0} sources → S4-BRIEF-{btag}.md")

def episodes(a, fg, corpus):
    """Smelt S3 (the runbook, S3): for each person, every group of two or more, every candidate and every nomination,
    each line cited by its number in the frozen profile (L), and the episode brief from
    ocr/method/SMELT-S3-EPISODE-BRIEF-TEMPLATE-EO-2026-10-14.md. Writes smelt/<stem>/S3-INPUT-<tag>.md and
    S3-BRIEF-<tag>.md; a tag whose return is filed is refused."""
    tpl = open(os.path.join(G, "ocr", "method", "SMELT-S3-EPISODE-BRIEF-TEMPLATE-EO-2026-10-14.md"), encoding="utf-8").read()
    for p in a.people:
        stem, _, name = p.partition("=")
        d = os.path.join(G, "smelt", stem); os.makedirs(d, exist_ok=True)
        if os.path.exists(os.path.join(d, f"S3-RETURN-{a.tag}.md")) and not a.refresh_singles: sys.exit(f"refusing: {stem} S3-RETURN-{a.tag}.md exists")
        frozen = os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md")
        if os.path.exists(frozen) and a.kinded_only and "**Smelt: only the" not in open(frozen, encoding="utf-8").read(3000):
            # 2026-10-15, the Fable review 13: S2 with the same tag had frozen the whole profile, and S3 would read it
            sys.exit(f"refusing: {os.path.basename(frozen)} holds the whole profile, not the new dowse's lines; use a new tag")
        if a.qualifier and os.path.exists(frozen) and open(frozen, encoding="utf-8").read() == open(os.path.join(G, "profiles", f"{stem}.md"), encoding="utf-8").read():
            os.replace(frozen, frozen + ".plain-copy")   # a plain copy of the profile, set aside, refrozen below
        if not os.path.exists(frozen) and a.qualifier:
            # ONE PERSON OF A SHARED HEAD (2026-11-10; the editor; the pilot refused Guillaume
            # 2026-10-30, his head holding several people): only the lines under the qualifier, the rest named in the header
            if len(a.people) != 1: sys.exit("refusing: --qualifier freezes one person a run")
            import collections
            src = open(os.path.join(G, "profiles", f"{stem}.md"), encoding="utf-8").read().split("\n")
            mark = f"**({a.qualifier})**"
            has = (lambda l: mark in l) if a.qualifier != "-" else (lambda l: not re.search(r"\*\*\([^)]*\)\*\*", l))
            q = lambda l: (re.search(r"\*\*\(([^)]*)\)\*\*", l) or [None, "sen kvalifiko"])[1]
            left = collections.Counter(q(l) for l in src if l.startswith("- $$$") and not has(l))
            keep = [l for l in src if not l.startswith("- $$$") or has(l)]
            n = sum(1 for l in keep if l.startswith("- $$$"))
            keep.insert(3, f"**Smelt: nur la {n} linioj " + (f"de ({a.qualifier})" if a.qualifier != "-" else "sen kvalifiko") + " estas ĉi tie; la samnomuloj de la kapo, forlasitaj: "
                           + "; ".join(f"({k}) {v}" for k, v in left.most_common()) + ".**")
            open(frozen, "w", encoding="utf-8").write("\n".join(keep))
        if not os.path.exists(frozen):
            if a.kinded_only:   # only the lines of the new dowse (the editor, 2026-10-14: only the facts of the new dowse corpus): a line from a dowse file, «⟵ `…-dowse.md`». Not «a line with an event
                # kind», the test until 2026-10-15, which cut the Somme records (a dowse file still in format 3) and with
                # them the Guérards (the editor)
                src = open(os.path.join(G, "profiles", f"{stem}.md"), encoding="utf-8").read().split("\n")
                keep = [l for l in src if not l.startswith("- $$$") or re.search(r"⟵ `[^`]*-dowse\.md`", l)]
                n = sum(1 for l in keep if l.startswith("- $$$"))
                keep.insert(3, f"**Smelt: only the {n} lines of the new dowse (from a dowse file) are kept here.**")
                open(frozen, "w", encoding="utf-8").write("\n".join(keep))
            else:
                shutil.copyfile(os.path.join(G, "profiles", f"{stem}.md"), frozen)
        prof = open(frozen, encoding="utf-8").read().split("\n")
        used, cache = set(), {}
        def L(r):   # the frozen profile's line number of a row: the facts list holds the line without its kind and with
            # the anchor in «» after the fact, so match on the fact's start, the anchor's start and the locator; and never
            # give two rows one line (2026-10-16, the reader's fault 1: rows sharing a locator and a source all took the
            # first line's number)
            key = (r[1], r[2], r[4])
            if key in cache: return cache[key]
            ps = r[4].split(" · ")
            if len(ps) < 3: return "L?"
            fact_anchor = ps[1].rsplit(" «", 1)
            fact = fact_anchor[0][:60]
            anchor = fact_anchor[1].rstrip("»")[:40] if len(fact_anchor) > 1 else ""
            loc = ps[2]
            hits = [i + 1 for i, l in enumerate(prof) if l.startswith("- $$$") and fact in l and loc in l and (not anchor or anchor in l)]
            free = [h for h in hits if h not in used] or hits
            cache[key] = f"L{free[0]}" if free else "L?"
            if free: used.add(free[0])
            return cache[key]
        rows = [r for r in corpus if r[0] == name]
        # with --kinded-only, the dowse files' rows only, as the frozen profile keeps (2026-10-22: since hand files
        # carry kinds too, format 4 since 2026-10-19, De Beaufront's groups took 48 hand-file rows the freeze had left
        # out, and the input showed 56 «L?»)
        if a.kinded_only: rows = [r for r in rows if r[1].endswith("-dowse.md")]
        allg, noms = fg.groups_entity(rows, corpus)
        gs = [g for g in allg if len(g[3]) >= 2]
        # THE SINGLE-LINE GROUPS, WRITTEN BY THE TOOL (the smelt runbook, S3, «A reader's limit», the first lever; built
        # 2026-10-16, the editor): a line whose kind and object no other line shares is a group of one, stated by its
        # own fact; the reader does not restate it, only merges it where it belongs and uses it in the episodes
        # one U per line: a line single under its kind and under its second kind («+…») was written twice (2026-10-16,
        # the S3 comparison: U1/U15, U2/U4 … eight pairs, each one line); now one U, both kinds named
        singles, seen = [], {}
        for g in allg:
            if len(g[3]) != 1: continue
            k = (g[3][0][1], g[3][0][4])
            if k in seen: seen[k][1].append(f"{g[1]} / {g[2] or '-'}"); continue
            seen[k] = (g, [f"{g[1]} / {g[2] or '-'}"]); singles.append(seen[k])
        def fact_of(r):   # the fact without the anchor, which follows it as the last «…» (the reader's fault 2: cut at the first «)
            ps = r[4].split(" · ")
            return ps[1].rsplit(" «", 1)[0].strip() if len(ps) > 1 else r[4]
        # THE CANDIDATES BY OBJECT AND YEAR (2026-11-10; the editor's to Fable's proposal 3, ocr/method/SMELT-OPTIMISE-
        # FABLE-2026-11-10.md: fact-groups.py pairs every two relational items of one object, Schneeberger's Ostwald 59 pairs,
        # Bourlet's Zamenhof 398): a pair whose two sides are both dated and share no year is dropped, by the brief's own rule
        # «alia jaro faras alian okazon»; the rest are joined object by object into connected sets, one K a set
        def yrs(side): return set(y for r in side for y in re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", r[2] or ""))
        pairs = [c for c in fg.CANDIDATES if c[0] == name]
        kept = [c for c in pairs if not (yrs(c[3]) and yrs(c[4]) and not (yrs(c[3]) & yrs(c[4])))]
        k_dropped = len(pairs) - len(kept)
        buck, side_of = {}, {}
        for who, kind, key, x, y in kept:
            yx, yy = yrs(x), yrs(y)
            yr = min(yx & yy) if (yx and yy) else min(yx or yy) if (yx or yy) else "sen dato"
            for s in (x, y):
                sid = tuple(id(r) for r in s); side_of[sid] = s
                lst = buck.setdefault((kind, key, yr), [])
                if sid not in lst: lst.append(sid)
        cands = [(name, kind, key, [side_of[s] for s in ss]) for (kind, key, yr), ss in buck.items()]
        cands.sort(key=lambda c: (c[1], c[2], min(yrs(c[3][0]) or {"9999"})))
        out = [f"# S3: the groups, candidates and nominations of {name} ({a.tag})", "",
               f"`[tools/smelt-s2-prep.py --episodes, from tools/fact-groups.py --match entity: {len(gs)} groups of two or more, "
               f"{len(singles)} single lines (U, written by the tool), {len(cands)} candidates, {len(noms)} nominations; L = the line's number in {os.path.basename(frozen)}. "
               f"{sum(1 for l in prof if l.startswith('- $$$'))} lines in the profile, {len(rows)} with a kind.]`", "", "## The groups", ""]
        for k, (who, kind, key, rs) in enumerate(gs, 1):
            out.append(f"- **G{k}** · {kind} / {key or '-'}: {', '.join(L(r) for r in rs)}")
        out += ["", "## The single lines (U: groups of one line, written by the tool; not to be restated)", ""]
        sing = []
        for k, ((who, kind, key, rs), ks) in enumerate(singles, 1):
            out.append(f"- **U{k}** · {'; +'.join(ks)}: {L(rs[0])}")
            sing.append(f"U{k}: {fact_of(rs[0])} — {L(rs[0])}")   # no witness count (2026-10-16: the reader gives the standing, the tool shows the places)
        # the lines the tool places in no group («alia» and «samnomo», which it never groups; a date it cannot read): listed
        # for the reader, who groups them as it groups the lines without a kind (the reader's fault 3, 2026-10-16)
        placed = {int(x) for l in out for x in re.findall(r"\bL(\d+)", l)}
        rest = [i + 1 for i, l in enumerate(prof) if l.startswith("- $$$") and i + 1 not in placed]
        # THE EDITION NOTES (2026-10-17, the resmelt's faults T4: Neves's «(diferenco inter la kopioj)» lines, dated
        # «2018+2019», kinded as the fact they touch, fell into no group, and the readers took them for facts): listed
        # apart, each to be attached to the group of the fact it touches as «malsamas inter la eldonoj: …», never a
        # group or an episode of its own (the S3 template, rule 2)
        ed = [n for n in rest if "diferenco inter la kopioj" in FLN.ours(prof[n - 1]) or "**2018+2019**" in prof[n - 1]]   # audit 38
        rest = [n for n in rest if n not in ed]
        out += ["", f"## The lines in no group of the tool ({len(rest)}: «alia», «samnomo», a date it cannot read, or no kind; group them yourself)", "",
                ", ".join(f"L{n}" for n in rest) or "(none)"]
        if ed:
            out += ["", f"## The edition notes ({len(ed)}: how two editions of one source differ about a fact; attach each to that fact's group as «malsamas inter la eldonoj: …», never a group or an episode of its own)", "",
                    ", ".join(f"L{n}" for n in ed)]
        sp = os.path.join(d, f"S3-SINGLES-{a.tag}.md")
        inp = os.path.join(d, f"S3-INPUT-{a.tag}.md")
        if a.refresh_singles:   # the filed return cites U by number (2026-10-16, after the reader's faults 1–3): the
            # numbering must be the one the reader read, so compare each U's kind and object with the input as read
            if not os.path.exists(inp): sys.exit(f"refusing: {stem} S3-INPUT-{a.tag}.md is missing; nothing to refresh")
            old = {m.group(1): m.group(2) for m in re.finditer(r"^- \*\*U(\d+)\*\* · (.*?): L", open(inp, encoding="utf-8").read(), re.M)}
            new = {m.group(1): m.group(2) for l in out for m in [re.match(r"- \*\*U(\d+)\*\* · (.*?): L", l)] if m}
            if old != new:
                bad = sorted((set(old.items()) ^ set(new.items())), key=lambda x: int(x[0]))[:5]
                sys.exit(f"refusing: {stem} the U numbering differs from S3-INPUT-{a.tag}.md ({len(old)} then, {len(new)} now; first: {bad})")
            for f in (inp, sp):
                keep = f[:-3] + "-as-read.md"
                if os.path.exists(f) and not os.path.exists(keep): shutil.copyfile(f, keep)
        open(sp, "w", encoding="utf-8").write(
            f"# The single-line groups of {name} ({a.tag})\n\n`[tools/smelt-s2-prep.py --episodes: each line whose kind and object no other "
            f"line of the profile shares, as a group of one, stated by its own fact; the episode reader merges those that belong to a "
            f"group («kunigita kun U…» in its return) and leaves the rest as they are. L = the line's number in {os.path.basename(frozen)}.]`\n\n"
            + "\n".join(sing) + "\n")
        out += ["", "## The candidates (relational lines that may be one occasion)", ""]
        if k_dropped: out.append(f"`[the tool: {k_dropped} pairs of {len(pairs)} dropped, their two sides of different years («alia jaro faras alian okazon»); "
                                 f"the rest joined by object and year into {len(cands)} candidates, each member a group or a line, apart by «≈»]`")
        for k, (who, kind, key, sides) in enumerate(cands, 1):
            out.append(f"- **K{k}** · {kind} / {key}: " + "  ≈  ".join(", ".join(L(r) for r in s) for s in sides))
        out += ["", "## The nominations (possible date errors)", ""]
        for k, (who, kind, key, grp, r) in enumerate(noms, 1):
            out.append(f"- **N{k}** · {kind} / {key}: the group {', '.join(L(x) for x in grp)}; the line {L(r)}")
        open(inp, "w", encoding="utf-8").write("\n".join(out) + "\n")
        miss = sum(l.count("L?") for l in out)
        if a.refresh_singles:
            print(f"{stem}: refreshed S3-INPUT-{a.tag}.md and S3-SINGLES-{a.tag}.md, {len(singles)} single lines, U numbering unchanged; "
                  f"{len(rest)} lines in no group of the tool" + (f"; {miss} lines not found in the profile" if miss else ""))
            continue
        brief = (tpl.replace("{persono}", name).replace("{tag}", a.tag).replace("{profilo}", frozen).replace("{enigo}", inp)
                    .replace("{unuopaj}", sp).replace("{registro}", os.path.join(G, "profiles", "NAMES-REGISTER.tsv")))
        open(os.path.join(d, f"S3-BRIEF-{a.tag}.md"), "w", encoding="utf-8").write(brief)
        print(f"{stem}: {len(gs)} groups, {len(singles)} single lines (S3-SINGLES-{a.tag}.md), {len(cands)} candidates, {len(noms)} nominations → S3-BRIEF-{a.tag}.md" + (f"; {miss} lines not found in the profile" if miss else ""))


if __name__ == "__main__":
    main()
