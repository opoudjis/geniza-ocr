#!/usr/bin/env python3
"""Smelt S2: the reader check of the fact groups, its input and brief (the editor, 2026-10-14; the runbook,
ocr/method/SMELT-RUNBOOK-2026-10-13.md, S2).

    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... [--kinds k1,k2] [--max 14] [--seed N]
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --episodes [--kinded-only]     smelt S3 (below)
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --episodes --refresh-singles   S3's input and singles remade, return filed
    tools/smelt-s2-prep.py <tag> <stem>=<NAME> ... --biography                    smelt S4, on the tag's S3 return

For each person: the groups of tools/fact-groups.py --match entity (two or more lines), every group of three or more and
a seeded sample of the pairs up to --max, or, with --kinds, every group of those kinds; and every nominated date error;
each with its full lines. Writes smelt/<stem>/S2-CHECK-INPUT-<tag>.md and S2-CHECK-BRIEF-<tag>.md (the brief from
ocr/method/SMELT-S2-CHECK-BRIEF-TEMPLATE-EO-2026-10-14.md); a tag whose return is filed is refused. The person's
profile is frozen as smelt/<stem>/PROFILE-FROZEN-<tag>.md if not already. Then a file-reader per brief, its return filed
as S2-CHECK-RETURN-<tag>.md. Ezri, 2026-10-14."""
import argparse, csv, importlib.util, os, random, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("people", nargs="+")
    ap.add_argument("--kinds", default=""); ap.add_argument("--max", type=int, default=14); ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--episodes", action="store_true", help="smelt S3: every group, candidate and nomination, by the frozen profile's line numbers, and the episode brief")
    ap.add_argument("--kinded-only", action="store_true", help="with --episodes: freeze only the profile lines from a dowse file (the new dowse; until 2026-10-15, lines with an event kind)")
    ap.add_argument("--biography", action="store_true", help="smelt S4: the biography brief, from the tag's frozen profile and episode return")
    ap.add_argument("--as", dest="as_tag", help="with --biography: name the brief (and so its return) for this tag instead")
    ap.add_argument("--refresh-singles", action="store_true", help="with --episodes: rewrite S3-INPUT and S3-SINGLES of a tag whose return is filed (the brief untouched; the old files kept as …-as-read.md); refused if a U number's kind and object would change")
    # default None, not 0: «--sizes 0» ran the S2 prep for every person named and froze their profiles (2026-10-17)
    ap.add_argument("--sizes", type=int, default=None, help="read-only: rank people by their lines from dowse files (what --kinded-only freezes); print the top N, the spread, the rank of each person named, and candidates for a small test (20–40 lines from 3+ sources); writes nothing")
    ap.add_argument("--source", default="", help="with --sizes: rank by the lines from this one dowse file (e.g. ruslanda-esperantisto-dowse.md) and mark who has a smelt folder already (the editor, 2026-10-17)")
    a = ap.parse_args()
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

def s4_body(stem, name, frozen, profilo, ret, singles):
    """The S4 brief from the template, filled: (text, the sources line, the profile's line count). The sources are
    counted on the whole frozen profile; {profilo} may be another file (a period's excerpt, tools/smelt-periods.py --s4)."""
    tpl = open(os.path.join(G, "ocr", "method", "BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md"), encoding="utf-8").read()
    body = "## La briefo" + tpl.split("## La briefo", 1)[1]
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
    fontoj = "; ".join(f"{k} ({v} linioj)" for k, v in sorted(srcs.items(), key=lambda x: -x[1]))
    b = (body.replace("{persono}", name).replace("{profilo}", profilo).replace("{epizodoj}", ret)
             .replace("{unuopaj}", singles or "(neniu: la epizoda legilo skribis ĉiujn grupojn)")
             .replace("{registro}", os.path.join(G, "profiles", "NAMES-REGISTER.tsv")).replace("{fontoj}", fontoj or "(neniu trovita)")
             # the rows the corpus attests (tools/register-evidence.py, 2026-10-17: ∴, not ◊?)
             .replace("{atesto}", os.path.join(G, "profiles", "NAMES-REGISTER-EVIDENCE.tsv")))
    return b, fontoj, total

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
        for f in (frozen, ret):
            if not os.path.exists(f): sys.exit(f"refusing: {os.path.relpath(f, G)} is missing")
        exists = [f for f in (out, os.path.join(d, f"S4-RETURN-{btag}.md")) if os.path.exists(f)]
        sp = os.path.join(d, f"S3-SINGLES-{a.tag}.md")
        b, fontoj, total = s4_body(stem, name, frozen, frozen, ret, sp if os.path.exists(sp) else None)
        if exists:   # refused after the list, so a refused run shows it (a dry test on a run already briefed)
            sys.exit(f"refusing: {os.path.relpath(exists[0], G)} exists; the sources it would list ({total} lines): {fontoj}")
        head = (f"# La biografio de {name} (smelt S4, {a.tag})\n\n`[tools/smelt-s2-prep.py --biography, from "
                f"ocr/method/BIOGRAPHY-BRIEF-TEMPLATE-EO-2026-10-14.md on PROFILE-FROZEN-{a.tag}.md and S3-RETURN-{a.tag}.md.]`\n\n")
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
        cands = [c for c in fg.CANDIDATES if c[0] == name]
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
        ed = [n for n in rest if "diferenco inter la kopioj" in prof[n - 1] or "**2018+2019**" in prof[n - 1]]
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
        for k, (who, kind, key, x, y) in enumerate(cands, 1):
            out.append(f"- **K{k}** · {kind} / {key}: {', '.join(L(r) for r in x)}  ≈  {', '.join(L(r) for r in y)}")
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
