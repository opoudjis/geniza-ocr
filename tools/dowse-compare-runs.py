#!/usr/bin/env python3
"""A redowse against the run before it: the old facts file's lines the new readers did not reproduce (made a tool
2026-10-14 from the stage-1 helper cmp_src.py).

    tools/dowse-compare-runs.py <source> [--old REV] [--show 30]

Old: profiles/by-source/<source>-dowse.md at git revision REV (default HEAD). New: the returns listed in
dowse/<source>/facts-config.json, with the copies the harvest would make. An old line counts as reproduced when a new
line for the same person on the same page shares three or more words of the anchor, or half the words of the fact.
Prints the counts and the unmatched lines, by person. Writes nothing, unless --write-restore: then the unmatched old
lines go whole into the settings' «restore», for the alignment pass (the runbook, D6 point 8). Ezri, 2026-10-14."""
import argparse, collections, glob, importlib.util, json, os, re, subprocess, sys
from collections import defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join("published", "heterophony-resources", "geniza")
STOP = set("la de en kaj al li lia sia ke por kun estis estas el pri ne sed ĉe kiu kiuj tiu oni ĝi ili mi da per sur kiel ankaŭ post antaŭ jam nur".split())
W = lambda s: {w for w in re.findall(r"\w+", s.lower()) if w not in STOP and len(w) > 2}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--old", default="HEAD"); ap.add_argument("--show", type=int, default=30)
    ap.add_argument("--additions", action="store_true", help="probe B: the old lines' additions of ours, and how many no new line carries")
    ap.add_argument("--write-restore", action="store_true", help="add the unmatched old lines, whole, to the settings' «restore» (then align them: D6 point 8)")
    ap.add_argument("--date-losses", metavar="DATE", help="write dowse/<source>/date-losses-DATE.md: old dated lines the facts file now gives undated, with the old date proposed")
    ap.add_argument("--write-date-decisions", metavar="DATE", help="add those proposed dates to dowse/<source>/DECISIONS.tsv as date rows (after the editor has seen the list)")
    ap.add_argument("--missing", metavar="DATE", help="work this source's lines of the harvest's missing-facts report: write dowse/<source>/missing-DATE.md, the unexplained first")
    ap.add_argument("--strict", type=float, default=0, metavar="F", help="probe: a match also needs this share of the old line's fact words in the new line")
    ap.add_argument("--probe", nargs=2, metavar=("OLD", "NEW"), help="compare two sets of returns in dowse/<source>/ (globs, e.g. 'facts-return-2026-10-17-?.md' 'facts-return-2026-10-17pb-*.md'): the old lines the new set does not reproduce; writes nothing")
    ap.add_argument("--restore-missing", metavar="DATE", help="add the unexplained lines of dowse/<source>/missing-DATE.md to «restore», for an alignment of those lines only")
    ap.add_argument("--clear-restore", action="store_true", help="empty the settings' «restore» (the lines --write-restore added), e.g. after a wrong comparison; the count is printed")
    a = ap.parse_args()
    os.chdir(ROOT)
    if a.clear_restore:   # 2026-10-17: --write-restore's 960 lines of a comparison that had skipped the raw lines unparsed
        cp = f"{G}/dowse/{a.source}/facts-config.json"; cfg = json.load(open(cp, encoding="utf-8"))
        n = len(cfg.get("restore", []))
        cfg["restore"] = []
        json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"«restore» emptied in {cp}: {n} lines taken out"); return
    spec = importlib.util.spec_from_file_location("hf", "tools/harvest-facts.py"); hf = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(hf); sys.argv = saved
    raw = {}
    def rows(lines, copies):
        people, now, tocopy = defaultdict(list), [], []; hf.KINDS.clear(); raw.clear()
        for line in lines:
            if not line.startswith("- $$$"): continue
            # the readers' lines repaired as the assembler repairs them (2026-10-17: without it, the raw lines of
            # Ruslanda Esperantisto's returns, dates in words and notes where the themes go, failed to parse and were
            # skipped unseen, so 960 of the committed file's 1,112 lines counted as lost and went into «restore»)
            line = hf.form_repair(line.rstrip("\n"))
            l, k = hf.take_kind(line); l = hf.to2(l); r, e = hf.parse(l)
            if e: continue
            who = hf.canon(r[0]); people[who].append(r[1:] + ("x",)); raw[(who, len(people[who]) - 1)] = line.rstrip("\n")
            if k: hf.KINDS[("x", r[3], r[2], hf.slug(who))] = k; tocopy.append(("x", who, len(people[who]) - 1, k, l))
        if copies:
            corpus = set()
            for f in glob.glob(G + "/profiles/by-source/*.md"):
                for l in open(f, encoding="utf-8", errors="replace"):
                    m = re.match(r"- \$\$\$ (.+?) \$\$\$", l)
                    if m: corpus.add(hf.canon(m.group(1)))
            for w in corpus: people.setdefault(w, [])
            hf.copies(people, tocopy, now)
        out = []
        for w, rs in people.items():
            for i, r in enumerate(rs):
                m = re.search(r"(PDF \d+|¶ \d+)", r[2]); loc = m.group(1) if m else "?"
                out.append((hf.slug(w), loc, W(hf.anchor_of(r[1])), W(r[1]), r[1][:160], r[0], raw.get((w, i), ""), r[2], hf.anchor_of(r[1])))
        return out
    old_txt = subprocess.run(["git", "show", f"{a.old}:{G}/profiles/by-source/{a.source}-dowse.md"], capture_output=True, text=True).stdout.split("\n")
    cfg = json.load(open(f"{G}/dowse/{a.source}/facts-config.json", encoding="utf-8"))
    new_txt = [l for r in cfg["returns"] for l in open(f"{G}/dowse/{a.source}/{r}", encoding="utf-8")] + cfg.get("restore", [])
    if a.probe:   # P2 of DOWSE-THROUGHPUT-PROPOSAL-2026-10-17.md: two sets of returns on the same pages, the baseline as «old»
        def pick(g):
            # the lean brief's lines expanded from each return's own pages file first (2026-10-18, the DeepSeek test:
            # «(prese M) l. K» names no page until harvest-facts.py's expand_lean has read the pages file)
            out = []
            for f in sorted(glob.glob(f"{G}/dowse/{a.source}/{g}")):
                mr = re.fullmatch(r"facts-return-(.+)-(\d+)\.md", os.path.basename(f))
                pf = f"{G}/dowse/{a.source}/facts-pages-{mr.group(1)}-{mr.group(2)}.txt" if mr else ""
                pages = open(pf, encoding="utf-8").read().split("\n") if pf and os.path.exists(pf) else None
                out += [hf.expand_lean(l.rstrip("\n"), pages, "") + "\n" if pages and l.startswith("- $$$") else l for l in open(f, encoding="utf-8")]
            return out
        old_txt, new_txt = pick(a.probe[0]), pick(a.probe[1])
        # the two form faults of the cut brief (P2(a)), repaired as the assembler would: a bare «[sen dato]» or
        # «[ĝenerala]» date made bold, and a missing themes field «[?]» put back before the voice
        def form(l):
            if not l.startswith("- $$$"): return l
            l = re.sub(r"^(- \$\$\$ .+? \$\$\$(?: \([^)]*\))?) (\[(?:sen dato|ĝenerala)[^\]]*\]) · ", r"\1 **\2** · ", l)
            if not re.search(r" · (?:\[[^\]]*\])+ · [✅📣📄]", l): l = re.sub(r" · ([✅📣📄])", r" · [?] · \1", l, count=1)
            return l
        new_txt = [form(l) for l in new_txt]
        print(f"probe: old {a.probe[0]} ({sum(1 for l in old_txt if l.startswith('- $$$'))} lines), "
              f"new {a.probe[1]} ({sum(1 for l in new_txt if l.startswith('- $$$'))} lines)")
    old, new = rows(old_txt, False), rows(new_txt, True)
    by = defaultdict(list)
    for n in new: by[(n[0], n[1])].append(n)
    # an old line is matched only if the new line says the same (shared anchor or fact words), with a date no less precise
    # and every person of the old line's «kun:» (ocr/method/ALIGN-JAM-RULE-PROPOSAL-2026-10-14.md, A narrowed: «ok»)
    import unicodedata
    def fold(s): return "".join(c for c in unicodedata.normalize("NFD", s.upper()) if unicodedata.category(c) != "Mn")
    def prec(d):
        m = re.search(r"\b(1[5-9]\d\d|20\d\d)(-\d\d)?(-\d\d)?", d or "")
        return 0 if not m else 1 + bool(m.group(2)) + bool(m.group(3))
    def kun(raw):
        m = re.search(r"kun: ([^};]*)", raw or "")
        return [fold(re.sub(r"\s*\(.*?\)", "", x)).strip() for x in m.group(1).split(" kaj ")] if m else []
    STRICT = a.strict
    def same(o, n):
        if not (len(o[2] & n[2]) >= 3 or len(o[3] & n[3]) >= max(3, 0.5 * len(o[3]))): return False
        if prec(n[5]) < prec(o[5]): return False
        if STRICT and len(o[3] & n[3]) < STRICT * len(o[3]): return False   # --strict F: probe, 2026-10-15
        nr = fold(n[6] or n[4])
        return all(k in nr for k in kun(o[6]) if k)
    if a.restore_missing:
        # the unexplained lines of dowse/<source>/missing-DATE.md («NOT FOUND», «UNREAD»: a copy is written back in the
        # line form, «$$$ NAME $$$ (qualifier)») into «restore», for an alignment of those lines only (align-prep «@K»)
        mp = f"{G}/dowse/{a.source}/missing-{a.restore_missing}.md"
        sec, add = "", []
        for l in open(mp, encoding="utf-8"):
            if l.startswith("## "): sec = l
            elif l.startswith("- missing: ") and ("NOT FOUND" in sec or "UNREAD" in sec):
                add.append(re.sub(r"^- \$\$\$ (.+?) \((.+?)\) \$\$\$", r"- $$$ \1 $$$ (\2)", l[len("- missing: "):].rstrip("\n")))
        cp = f"{G}/dowse/{a.source}/facts-config.json"; have = cfg.get("restore", [])
        add = [x for x in dict.fromkeys(add) if x not in have]
        k = len(have) + 1
        cfg["restore"] = have + add
        json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(add)} lines added to «restore» in {cp}, numbers {k}–{k + len(add) - 1}: align them with tools/dowse-align-prep.py <date> {a.source}@{k}")
        return
    if a.missing:
        # the harvest's missing-facts report, worked by tool (the editor, 2026-10-15): each missing line of this
        # source is looked for in the facts file as it stands (with the harvest's copies): the same fact for the same
        # person on the same page (shared words, the date and the kind aside), or under another person on that page (a
        # rename, a «kun:» copy); then in the alignment returns («JAM», «NOMO»); then the scope register. The rest is
        # listed first, for the editor. Writes dowse/<source>/missing-<DATE>.md, create-only.
        rp = f"{G}/dowse/{a.source}/missing-{a.missing}.md"
        if os.path.exists(rp): sys.exit(f"{rp} exists: not overwritten")
        rep = open(f"{G}/profiles/build/MISSING-FACTS-LATEST.md", encoding="utf-8").read().split("\n")
        mine, on = [], False
        for l in rep:
            if l.startswith("### "): on = l[4:].startswith(f"{a.source}-dowse.md")
            elif on and l.startswith("- - $$$"): mine.append(l[2:])
        ms = rows(mine, False)
        cur = rows(open(f"{G}/profiles/by-source/{a.source}-dowse.md", encoding="utf-8").read().split("\n"), True)
        cby = defaultdict(list)
        for c in cur: cby[c[1]].append(c)
        def words_same(o, n): return len(o[2] & n[2]) >= 3 or len(o[3] & n[3]) >= max(3, 0.5 * len(o[3]))
        jam, nomo = [], []
        for f in sorted(glob.glob(f"{G}/dowse/{a.source}/align-return-*.md")):
            for l in open(f, encoding="utf-8"):
                mj = re.match(r"\s*\d+\.\s*JAM:\s*(.+)", l)
                if mj: jam.append((W(re.sub(r"\$\$\$.*?\$\$\$|\*\*[^*]*\*\*|\{[^}]*\}", " ", mj.group(1))), os.path.basename(f), mj.group(1).strip()[:120]))
                mn = re.match(r"\s*\d+\.\s*NOMO:\s*(.+)", l)
                if mn: nomo.append((mn.group(1).split(";")[0].strip(), os.path.basename(f), mn.group(1).strip()[:160]))
        sp = importlib.util.spec_from_file_location("dfa", "tools/dowse-facts-assemble.py"); dfa = importlib.util.module_from_spec(sp); sp.loader.exec_module(dfa)
        reg = dfa.register_out()
        out = defaultdict(list)
        for m in ms:
            raw = m[6] or m[4]
            same = [c for c in cby.get(m[1], []) if c[0] == m[0] and words_same(m, c)]
            other = [c for c in cby.get(m[1], []) if c[0] != m[0] and words_same(m, c)]
            hd = re.match(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))?", raw)
            jm = [j for j in jam if j[0] and len(j[0] & m[3]) >= max(3, 0.7 * len(j[0]))]
            nm = [n for n in nomo if hd and dfa.fold(hd.group(1)) in dfa.fold(n[0].split("=")[0])]
            if same: out["the same fact now, same person"].append((raw, same[0][6] or same[0][4]))
            elif other: out["the same fact now, under another person"].append((raw, other[0][6] or other[0][4]))
            elif jm: out["«JAM» in the alignment"].append((raw, f"{jm[0][1]}: JAM: {jm[0][2]}"))
            elif nm: out["«NOMO» in the alignment"].append((raw, f"{nm[0][1]}: NOMO: {nm[0][2]}"))
            elif hd and dfa.is_out(hd.group(1), hd.group(2) or "", reg): out["out of scope by the register"].append((raw, ""))
            else: out["NOT FOUND: for the editor"].append((raw, ""))
        seen = {m[6] for m in ms}                   # a line the harvest's parser cannot read is listed, never lost
        for l in mine:
            if l not in seen: out["UNREAD by the parser: for the editor"].append((l, ""))
        ms = ms + [None] * len(out["UNREAD by the parser: for the editor"])
        order = ["UNREAD by the parser: for the editor", "NOT FOUND: for the editor", "out of scope by the register", "«NOMO» in the alignment", "«JAM» in the alignment",
                 "the same fact now, under another person", "the same fact now, same person"]
        txt = [f"# The missing facts of {a.source}, worked ({a.missing})", "",
               f"`[Ezri, tools/dowse-compare-runs.py {a.source} --missing {a.missing}: the lines of profiles/build/MISSING-FACTS-LATEST.md for this source, "
               "looked for in the facts file as it stands, the alignment returns and the scope register.]`", ""]
        for k in order:
            if not out[k]: continue
            txt += [f"## {k}: {len(out[k])}", ""]
            for raw, why in out[k]: txt += [f"- missing: {raw}"] + ([f"  - {why}"] if why else []) + [""]
        open(rp, "w", encoding="utf-8").write("\n".join(txt) + "\n")
        print(f"{a.source}: {len(ms)} missing; " + "; ".join(f"{k} {len(out[k])}" for k in order if out[k]) + f"\nwrote {rp}")
        return
    if a.date_losses or a.write_date_decisions:
        # dates the redowse lost (the editor, 2026-10-15):
        # an old dated line whose fact the facts file as it stands gives only undated (an aligner's «JAM» drops the
        # dated old line for the undated new one). The old date is proposed as a DECISIONS date row, keyed on the new
        # line's full locator and anchor; written only with --write-date-decisions, after the editor has seen the list
        cur_txt = open(f"{G}/profiles/by-source/{a.source}-dowse.md", encoding="utf-8").read().split("\n")
        cur = rows(cur_txt, False); cby = defaultdict(list)
        for c in cur: cby[(c[0], c[1])].append(c)
        def kind_of(raw): m = re.search(r"\*\* · \{\s*([^:};]+)", raw or ""); return m.group(1).strip() if m else ""
        # the same fact: shared words AND the same event kind (a «renkonto» is not an «aliĝo» because the words overlap)
        def words_same(o, n): return (len(o[2] & n[2]) >= 3 or len(o[3] & n[3]) >= max(3, 0.5 * len(o[3]))) and kind_of(o[6]) == kind_of(n[6])
        saying = {d for _, d, _ in cfg.get("saying_dates", [])}
        props = defaultdict(list)                   # the undated current line -> the old dates for it
        for o in old:
            if not prec(o[5]): continue
            # an «interpreto» the old run dated by its saying is undated now by the signed rule (dated by the act
            # interpreted, 2026-10-14 «A»): not a loss
            if kind_of(o[6]) == "interpreto" and o[5].replace("*", "").strip() in saying: continue
            cands = [c for c in cby.get((o[0], o[1]), []) if words_same(o, c)]
            if not cands or any(prec(c[5]) >= prec(o[5]) for c in cands): continue
            und = [c for c in cands if (c[5] or "").replace("*", "").strip() == "[sen dato]"]
            # … or dated less precisely within the same year (2026-10-17, Jossinet's redowse: «1888» now where the old
            # line had «inter 1888-03 kaj 1888-06»; restored whole, such lines came back as duplicates; the editor
            # to carrying the dates before the restore)
            yr = lambda d: (re.search(r"\b(1[5-9]\d\d|20\d\d)", d or "") or [None])[0] if re.search(r"\b(1[5-9]\d\d|20\d\d)", d or "") else None
            if not und:
                und = [c for c in cands if 0 < prec(c[5]) < prec(o[5]) and yr(c[5]) and yr(c[5]) == yr(o[5])]
            if und:
                best = max(und, key=lambda c: len(o[2] & c[2]) + len(o[3] & c[3]))
                props[(best[0], best[7], best[8], best[6])].append((o[5].replace("*", "").strip(), o[6]))
        dt = a.date_losses or a.write_date_decisions
        rowsout, review = [], [f"# Dates lost in the redowse: {a.source} ({dt})", "",
            f"`[Ezri, tools/dowse-compare-runs.py {a.source} --old {a.old} --date-losses {dt}: old lines with a date whose fact "
            "the facts file as it stands gives undated. One date: proposed as a DECISIONS date row. Two or more: listed, not proposed.]`", ""]
        one = sum(1 for v in props.values() if len({d for d, _ in v}) == 1)
        for (who, loc, anc, rawc), v in sorted(props.items(), key=lambda x: x[0][1]):
            ds = sorted({d for d, _ in v})
            review += [f"- now: {rawc}", *[f"  - old ({d}): {r}" for d, r in v],
                       f"  - {'PROPOSED: ' + ds[0] if len(ds) == 1 else 'NOT PROPOSED, the old dates differ: ' + ', '.join(ds)}", ""]
            if len(ds) == 1 and anc:
                # the locator's items under their file names, the form DECISIONS rows match before the assembler writes
                # keys (2026-10-17: Neves's ten rows, keyed «neves-parnaso-ido-2018, PDF 12», matched no line)
                loc = "; ".join(hf.key_names().get(p.split(",")[0].strip(), p.split(",")[0].strip()) + p[len(p.split(",")[0]):]
                                for p in loc.split("; "))
                rowsout.append("\t".join([loc, anc, "date", ds[0], f"the old reading's date ({a.old}), carried {dt} (the editor's word on the list)", "tools/dowse-compare-runs.py --date-losses"]))
        print(f"{a.source}: {len(props)} undated lines whose old match had a date; {one} with one old date (proposed), {len(props) - one} with differing dates")
        rp = f"{G}/dowse/{a.source}/date-losses-{dt}.md"
        if a.date_losses:
            if os.path.exists(rp): sys.exit(f"{rp} exists: not overwritten")
            open(rp, "w", encoding="utf-8").write("\n".join(review) + "\n"); print(f"wrote {rp}")
        if a.write_date_decisions:
            dp = f"{G}/dowse/{a.source}/DECISIONS.tsv"
            have = open(dp, encoding="utf-8").read() if os.path.exists(dp) else "locator\tphrase\tkind\tvalue\truling\tnote\n"
            add = [r for r in rowsout if "\t".join(r.split("\t")[:2]) not in have]
            open(dp, "w", encoding="utf-8").write(have.rstrip("\n") + "\n" + "\n".join(add) + ("\n" if add else ""))
            print(f"{len(add)} date rows added to {dp}")
        return
    miss = [o for o in old if not any(same(o, n) for n in by.get((o[0], o[1]), []))]
    print(f"{a.source}: old {len(old)}, new with copies {len(new)}, unmatched {len(miss)}; by person {collections.Counter(m[0] for m in miss).most_common(8)}")
    for m in miss[:a.show]: print(f"  {m[0]} | {m[1]} | {m[5]} | {m[4]}")
    if a.additions:
        # probe B of ocr/method/ALIGN-JAM-RULE-PROPOSAL-2026-10-14.md: the old lines' additions of ours (in the labels'
        # bracket: «pruvo:», identifications, corrections, computed dates), and whether a new line on the same page for
        # the same person carries them; an addition counts as carried when half its content words are in that new line
        PAT = re.compile(r"pruvo:|identig|korektit|kalkulit|ne kontrolita|verŝajne|OCR", re.I)
        def adds(rawline):
            m = re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$", rawline)
            return [s.strip() for s in re.split(r";\s*", m.group(1)) if PAT.search(s)] if m else []
        newraw = defaultdict(list)
        for n in new: newraw[(n[0], n[1])].append(n[6] or n[4])
        tot = lost = 0; per = collections.Counter(); shown = 0
        for o in old:
            ad = adds(o[6])
            if not ad: continue
            cands = newraw.get((o[0], o[1]), [])
            for s in ad:
                tot += 1
                w = W(s)
                if not w or any(len(w & W(c)) >= max(1, 0.5 * len(w)) for c in cands): continue
                lost += 1; per[o[0]] += 1
                if shown < a.show: print(f"  LOST {o[0]} | {o[1]} | {s[:150]}"); shown += 1
        print(f"{a.source}: additions of ours in the old lines {tot}; not carried by a new line for the same person and page {lost}; by person {per.most_common(8)}")
    if a.write_restore:
        # the old lines the new run lacks, whole, into the settings' «restore», for the alignment pass (D6 point 8),
        # which keeps them or drops them as already given (JAM)
        cp = f"{G}/dowse/{a.source}/facts-config.json"
        have = set(cfg.get("restore", []))
        add = [m[6] for m in miss if m[6] and m[6] not in have]
        cfg["restore"] = cfg.get("restore", []) + add
        json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{len(add)} old lines added to «restore» in {cp}")

if __name__ == "__main__":
    main()
