#!/usr/bin/env python3
"""Smelt S5, step 4: the fix reader for the line faults (the smelt runbook, S5; the editor, 2026-10-17 16:5x).

    tools/smelt-fix.py --prep <tag>     one brief a source, smelt/FIX-BRIEF-<tag>-<source>.md, and FIX-KEYS-<tag>.tsv
    tools/smelt-fix.py --apply <tag>    the filed returns, smelt/FIX-RETURN-<tag>-<source>.md, into each source's settings

--prep: every fault of smelt/FAULTS-TRIAGE-<tag>.tsv routed «line» and still «to do»; for each, the lines it cites
(L‹n› of smelt/<stem>/PROFILE-FROZEN-<tag>.md), traced to the reader's own line in the source's returns (a copy,
«⟦kopio el X⟧», to the line it was copied from), keyed by a piece of its fact that only that line holds; grouped by the
source, each brief with the fault, the fix wanted and the lines in full, and the source text to reread the page in (a
fault is fixed from the page, never from the line alone). A line that cannot be keyed is listed in the brief's head and
left out. --apply: each return's verdicts, line by line: ANSTATAŬIGU (the first new line replaces the old,
«replace_lines» [key, line, return]; any further line, a split, goes to «extra_lines»), FORIGU (the line is the sum of
others or no fact: «drop_keys»), SAMA (no change). Writes dowse/<source>/facts-config.json (the settings, tracked by
git) and prints what it wrote; then reassemble the source and harvest. Create-only for the briefs; --apply refuses a
return already applied (the settings record «s5_applied»). Ezri, 2026-10-17."""
import csv, importlib.util, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
S = os.path.join(G, "smelt")
REF = re.compile(r"\bL(\d+)\b")

def load_faults(tag):
    spec = importlib.util.spec_from_file_location("sf", os.path.join(ROOT, "tools", "smelt-faults.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return {f["id"]: f for f in m.faults(tag)}

def fields(l):
    """A profile line -> (fact, anchor, locator, source file, copied-from or None)."""
    ps = l.split(" · ")
    src = (re.search(r"⟵ `([^`]+)`", l) or [None, ""])[1]
    copy = (re.search(r"⟦kopio el ([^⟧]+)⟧", l) or [None, None])[1]
    loc = next((p for p in ps if re.search(r", (?:PDF|¶) \d", p)), "")
    fact = re.sub(r"^\*\*\([^)]*\)\*\* ", "", ps[2]) if len(ps) > 4 else ""
    anchor = ps[3] if len(ps) > 4 else ""
    return fact, anchor, loc, src, copy

def raw_lines(source):
    D = os.path.join(G, "dowse", source)
    cfg = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8"))
    out = []
    for r in cfg["returns"]:
        out += [(r, l.rstrip("\n")) for l in open(os.path.join(D, r), encoding="utf-8") if l.startswith("- $$$")]
    for part in ("extra_lines", "restore"):
        out += [(part, l) for l in cfg.get(part, []) if l.startswith("- $$$")]
    return out

def key_for(fact, anchor, raws):
    """The shortest piece of the fact (or of the anchor) that one raw line alone holds: (key, return) or (None, None)."""
    for text in (fact, anchor.replace("‹", "«").replace("›", "»"), anchor):
        for n in (60, 45, 30):
            k = text[:n].strip()
            if len(k) < 20: continue
            hits = [(r, l) for r, l in raws if k in l]
            if len(hits) == 1: return k, hits[0][0]
    return None, None

def prep(tag):
    faults = load_faults(tag)
    tri = [r for r in csv.reader(open(os.path.join(S, f"FAULTS-TRIAGE-{tag}.tsv"), encoding="utf-8"), delimiter="\t")
           if r and not r[0].startswith("#") and len(r) == 6 and r[2] == "line" and r[5].startswith("to do")]
    by_src, keys, unkeyed, rawc = {}, [], [], {}
    for fid, pat, route, problem, fix, state in tri:
        f = faults.get(fid)
        if not f: continue
        for n in dict.fromkeys(int(x) for x in REF.findall(" ".join(f["text"]))):
            l = f["line"].get(n)
            if not l: continue
            fact, anchor, loc, srcfile, copy = fields(l)
            source = srcfile.replace("-dowse.md", "")
            if not os.path.exists(os.path.join(G, "dowse", source, "facts-config.json")):
                unkeyed.append((fid, n, f"no settings for {srcfile} (an older file, fixed by hand)")); continue
            raws = rawc.setdefault(source, raw_lines(source))
            k, ret = key_for(fact, anchor, raws)
            if not k: unkeyed.append((fid, n, "no piece of the fact found in one reader's line alone")); continue
            keys.append((fid, f["stem"], n, source, ret, k))
            by_src.setdefault(source, {}).setdefault(fid, (pat, problem, fix, f, []))[4].append((n, l, loc, copy))
    if not by_src: sys.exit("nothing to prepare: no «line» fault still «to do» could be keyed")
    kp = os.path.join(S, f"FIX-KEYS-{tag}.tsv")
    # «--again» (the runbook's P5: no raw removal): this tool rewrites its own briefs and keys, only while git does not
    # track them and no return is filed for the tag
    again = "--again" in sys.argv
    import subprocess
    def blocked(p):
        if not os.path.exists(p): return None
        if not again: return "exists"
        if subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", os.path.relpath(p, ROOT)], capture_output=True).returncode == 0: return "is tracked"
        return None
    if any(f.startswith(f"FIX-RETURN-{tag}-") for f in os.listdir(S)): sys.exit("refusing: a return of this tag is filed")
    for p in [kp] + [os.path.join(S, f"FIX-BRIEF-{tag}-{s}.md") for s in by_src]:
        why = blocked(p)
        if why: sys.exit(f"refusing: {os.path.relpath(p, ROOT)} {why}" + ("" if again else " (--again rewrites this tool's own files)"))
    with open(kp, "w", encoding="utf-8") as fh:
        fh.write("fault\tperson\tL\tsource\treturn\tkey\n" + "".join("\t".join(map(str, k)) + "\n" for k in keys))
    tpl_line = "`- $$$ NOMO $$$ (kvalifiko) **dato** · {speco: objekto} · fakto · ankro · lokindiko · [?] · voĉo (etikedoj)`"
    for source, items in by_src.items():
        cfg = json.load(open(os.path.join(G, "dowse", source, "brief-config.json"), encoding="utf-8"))
        texts = " kaj ".join(f"`{os.path.join(G, x)}`" for x in cfg["texts"])
        out = [f"# La ripara legado (smelt S5): {source} ({tag})", "",
               f"`[tools/smelt-fix.py --prep {tag}: {sum(len(v[4]) for v in items.values())} linioj de {len(items)} faŭltoj, kiujn la legiloj de smelt trovis kaj Ezri juĝis riparendaj en la linioj (smelt/FAULTS-TRIAGE-{tag}.tsv). La smelt-gvidlibro, S5, paŝo 4.]`", "",
               "## La briefo", "",
               "Vi riparas faktoliniojn de esplora projekto pri la historio de la internaciaj helplingvoj. Uzu nur la ilon Read. Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn, skribu neniujn dosierojn. Via fina mesaĝo estas via raporto. Skribu ĝin en Esperanto.",
               "",
               f"**La fonto:** {cfg['source']}. La teksto: {texts}. Por ĉiu linio **relegu la paĝon** de ĝia lokindiko en la teksto (la paĝoj estas markitaj «=== page N ===» aŭ «=== ¶ N ===»): riparu laŭ la paĝo, neniam nur laŭ la linio.",
               f"**La specoj de fakto:** `{os.path.join(G, 'ocr', 'method', 'EVENT-KINDS-PROPOSAL-2026-10-13.md')}`, la sekcio «The list in force». **La formo de linio:** {tpl_line}, kiel en `{os.path.join(G, 'ocr', 'method', 'DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-13.md')}`, «La linio»; la ankro ses aŭ pli da vortoj de la paĝo, laŭvorte; la lokindiko kiel en la malnova linio.",
               "",
               "**Por ĉiu faŭlto** sube: la problemo kaj la riparo, kiun la triado proponas (en la angla), kaj la linioj. Por ĉiu linio decidu unu el tri:",
               "- **ANSTATAŬIGU:** skribu la ĝustan linion, aŭ, por linio, kiu diras du faktojn, la du (aŭ pli) liniojn, ĉiun plena kaj staranta sola. La kapon (NOMO) lasu, kiel en la malnova linio, krom se la faŭlto estas ĝuste ĝi.",
               "- **FORIGU:** la linio estas la sumo de aliaj linioj aŭ ne estas fakto; diru, kiuj linioj jam diras ĝin.",
               "- **SAMA:** la paĝo montras, ke la linio estas ĝusta; diru kial.",
               "Linio, kiu venas el kopio (⟦kopio el NOMO⟧), estas riparata en sia originalo: skribu la linion sub la originala kapo (NOMO de la kopio-marko).",
               "**La aliaj linioj de la sama paĝo** estas listigitaj sub ĉiu faŭlto, ĉiuj personoj: antaŭ ol dividi aŭ reskribi linion, kontrolu, ke neniu el ili jam diras la fakton, eĉ sub alia persono; se jes, FORIGU (aŭ ne skribu la duan linion) kaj nomu ĝin.",
               "",
               "**La formo de la raporto:**", "", "```", "### bourlet-F1", "- L8: ANSTATAŬIGU", "- $$$ BOURLET $$$ **…** · {…} · … · … · … · [?] · 📣 (…)", "- $$$ BOURLET $$$ **…** · {…} · … · … · … · [?] · 📣 (…)", "- L9: FORIGU (= L12 kaj L13)", "- L10: SAMA (la paĝo diras …)", "```", "",
               f"Fine, en du paŝoj: (1) la tuta raporto kiel unu mesaĝo; (2) en la sama mesaĝo, post la raporto, legu `{os.path.join(G, 'dowse', '_FINO.txt')}` kaj respondu nur per la linio, kiun ĝi petas.",
               "", "## La faŭltoj", ""]
        # the source's other lines at the same item and place, every person (2026-10-18, the editor; Li kaj
        # ni's doubles 40 → 44: a reader splitting De Beaufront's L188 and L189 wrote again two doubts of Zamenhof the page
        # already had under ZAMENHOF, which its brief did not show)
        fp = os.path.join(G, "profiles", "by-source", f"{source}-dowse.md")
        src_lines = [x.rstrip("\n") for x in open(fp, encoding="utf-8") if x.startswith("- $$$")] if os.path.exists(fp) else []
        place = lambda s: (m.group(1), m.group(2)) if (m := re.search(r"([A-Za-z0-9._-]+), (?:PDF|¶) ?(\d+)", s)) else None
        for fid, (pat, problem, fix, f, ls) in items.items():
            out += [f"### {fid} · {pat}", "", f"- **La problemo:** {problem}", f"- **La riparo proponita:** {fix}", f"- **La vortoj de la smelt-legilo:** {' '.join(f['text'])}"]
            seen_places, own = [], set()
            for n, l, loc, copy in ls:
                out.append(f"- **L{n}**{f' (kopio el {copy})' if copy else ''}: `` {(l[2:] if l.startswith('- ') else l).split('  ⟵ ')[0]} ``")  # 2026-10-19: l may come without «- » (both fix readers saw «$ NOMO $$$»)
                own.add(fields(l)[0][:40])
                p = place(loc)
                if p and p not in seen_places: seen_places.append(p)
            others = [x for x in src_lines if place(x) in seen_places and fields(x)[0][:40] not in own]
            if others:
                out.append(f"- **La aliaj linioj de la sama paĝo** ({len(others)}{', la unuaj 15' if len(others) > 15 else ''}; nur por legi):")
                out += [f"  - `` {x[2:]} ``" for x in others[:15]]
            out.append("")
        un = [u for u in unkeyed]
        if un:
            out[3:3] = ["`[Ne ŝlositaj, ellasitaj: " + "; ".join(f"{a} L{b}: {c}" for a, b, c in un) + "]`", ""]
        with open(os.path.join(S, f"FIX-BRIEF-{tag}-{source}.md"), "w", encoding="utf-8") as fh: fh.write("\n".join(out) + "\n")
        print(f"FIX-BRIEF-{tag}-{source}.md: {len(items)} faults, {sum(len(v[4]) for v in items.values())} lines")
    if unkeyed: print(f"not keyed, left out ({len(unkeyed)}): " + "; ".join(f"{a} L{b}" for a, b, c in unkeyed))

def reader_form(l):
    """A fix reader's line in the readers' form: the profile's date guess off («[sen dato; divene …]» → «[sen dato]»:
    the harvest makes the guess), the profile's own marks off (a trailing «⟦kontribuo: …⟧», which the harvest adds, and
    «⟵ `file`»). 2026-10-17: the fix readers copy the profile's line, guess and all."""
    l = re.sub(r"\*\*\[sen dato;[^\]]*\]\*\*", "**[sen dato]**", l)
    l = re.sub(r"\s*⟵ `[^`]+`\s*$", "", l)
    l = re.sub(r"\)\s*⟦kontribuo: [^⟧]+⟧\s*$", ")", l)
    # the locator's items as the readers write them, the file names (the profile shows the keys, «neves-parnaso-ido-2018,
    # PDF 33»; DECISIONS and the settings match the file names, and the assembler writes the keys last: 2026-10-17, two
    # dedupe rows missed the fix readers' Neves lines)
    if not KEY2ITEM:
        for r in csv.DictReader((x for x in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not x.startswith("#")), delimiter="\t"):
            if (r.get("key") or "").strip() and r["key"].strip() != r["item"]: KEY2ITEM[r["key"].strip()] = r["item"]
    for k, item in KEY2ITEM.items():
        l = re.sub(rf"(?<=· ){re.escape(k)}(?=, (?:PDF|¶) )", item, l)
        l = re.sub(rf"(?<=; ){re.escape(k)}(?=, (?:PDF|¶) )", item, l)
    return l.rstrip()

KEY2ITEM = {}

def reader_form_unkeyed(l):
    """A line compared without its locators' items, so a split line written with keys matches its file-name form."""
    return re.sub(r"· [^·;]+?, (PDF|¶) ", r"· \1 ", re.sub(r"; [^·;]+?, (PDF|¶) ", r"; \1 ", l))

def apply(tag):
    keys = {}
    for r in csv.DictReader(open(os.path.join(S, f"FIX-KEYS-{tag}.tsv"), encoding="utf-8"), delimiter="\t"):
        keys[(r["fault"], int(r["L"]))] = r
    by_src, applied_ids = {}, set()
    for (fid, n), r in keys.items(): by_src.setdefault(r["source"], []).append((fid, n, r))
    for source in sorted(by_src):
        rp = os.path.join(S, f"FIX-RETURN-{tag}-{source}.md")
        if not os.path.exists(rp): print(f"{source}: no return filed"); continue
        cp = os.path.join(G, "dowse", source, "facts-config.json"); cfg = json.load(open(cp, encoding="utf-8"))
        # «--again»: a return applied before is read again, and only what the settings do not hold yet is added (a
        # verdict the parser missed the first time); nothing is added twice
        if tag in cfg.get("s5_applied", []) and "--again" not in sys.argv: print(f"{source}: already applied"); continue
        fid, n, verdict, new, done = None, None, None, [], []
        def flush():
            if fid is None or n is None: return
            k = keys.get((fid, n))
            if not k: done.append(f"  {fid} L{n}: NOT KEYED, skipped"); return
            if verdict == "ANSTATAŬIGU" and new:
                entry = [k["key"], new[0], k["return"]]
                if entry in cfg.setdefault("replace_lines", []): return
                # an entry of this key and return written before (an earlier form of the same line) is replaced
                old = [e for e in cfg["replace_lines"] if e[0] == k["key"] and len(e) > 2 and e[2] == k["return"]]
                cfg["replace_lines"] = [e for e in cfg["replace_lines"] if e not in old] + [entry]
                if old and len(new) > 1:   # the split's second line in its earlier form goes too
                    olds = {reader_form_unkeyed(x) for x in new[1:]}
                    cfg["extra_lines"] = [x for x in cfg.get("extra_lines", []) if reader_form_unkeyed(x) not in olds]
                cfg.setdefault("extra_lines", []).extend(x for x in new[1:] if x not in cfg["extra_lines"])
                done.append(f"  {fid} L{n}: replaced" + (f", +{len(new) - 1} split" if len(new) > 1 else ""))
            elif verdict == "FORIGU":
                if k["key"] in cfg.setdefault("drop_keys", []): return
                cfg["drop_keys"].append(k["key"]); done.append(f"  {fid} L{n}: dropped")
            elif verdict == "SAMA": done.append(f"  {fid} L{n}: same")
            else: done.append(f"  {fid} L{n}: no verdict read ({verdict}, {len(new)} lines)")
        for l in open(rp, encoding="utf-8").read().split("\n"):
            m = re.match(r"^###\s+(\S+)", l)
            if m: flush(); fid, n, verdict, new = m.group(1), None, None, []; continue
            # «- L86 (kopio el BOIRAC, …): ANSTATAŬIGU» too (2026-10-17: two readers put a note before the colon)
            m = re.match(r"^- L(\d+)(?:\s*\([^)]*\))?:\s*(ANSTATAŬIGU|FORIGU|SAMA)", l)
            if m: flush(); n, verdict, new = int(m.group(1)), m.group(2), []; continue
            if l.startswith("- $$$") and verdict == "ANSTATAŬIGU": new.append(reader_form(l))
        flush()
        if tag not in cfg.setdefault("s5_applied", []): cfg["s5_applied"].append(tag)
        json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{source}: {len(done)} verdicts into {os.path.relpath(cp, ROOT)}"); print("\n".join(done))
        applied_ids.update(i for i, _n, _r in by_src[source])
    # the triage's state: a «line» fault whose lines were all read is done by the fix reader
    tp = os.path.join(S, f"FAULTS-TRIAGE-{tag}.tsv")
    rows = open(tp, encoding="utf-8").read().split("\n")
    stamp = __import__("datetime").datetime.now().strftime("%H:%M")[:-1] + "x"
    out = []
    for r in rows:
        c = r.split("\t")
        if len(c) == 6 and c[0] in applied_ids and c[2] == "line" and c[5].startswith("to do"):
            c[5] = f"done {stamp} (the S5 fix reader, smelt/FIX-RETURN-{tag}-‹source›.md)"
        out.append("\t".join(c))
    open(tp, "w", encoding="utf-8").write("\n".join(out))

if __name__ == "__main__":
    if "--prep" in sys.argv: prep(sys.argv[sys.argv.index("--prep") + 1])
    elif "--apply" in sys.argv: apply(sys.argv[sys.argv.index("--apply") + 1])
    else: sys.exit(__doc__)
