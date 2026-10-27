#!/usr/bin/env python3
"""The recall sample: a second reader on a random share of a source's pages, against the stage readers (the editor,
2026-10-14, on dowsing twice; Ezri's counter-proposal, a recall sample per source).

    tools/dowse-recall.py sections <source> [--stage-date D]
    tools/dowse-recall.py prep <source> <tag> --ranges LO-HI[,LO-HI] [--stage-date D]
    tools/dowse-recall.py compare <source> <tag> [--stage-date D]

prep: whole chapters or sections, given as --ranges (no random pages: the editor, 2026-10-14; this docstring said
 until 2026-10-15), and writes dowse/<source>/recall-<tag>.md: the pages and the prompt for the
second reader (for a numbered text, write «¶» in the prompt by hand: it prints «PDF»), who reads the stage brief (facts-brief-<stage-date>.md) on those pages only.
Its return is filed as dowse/<source>/recall-return-<tag>.md.
compare: the stage lines on those pages (facts-return-<stage-date>-*.md) against the second reader's. A line of one
counts as found by the other when a line for the same person on the same page shares three or more words of the anchor
or half the words of the fact. Prints both readers' lines, the matches, the stage's miss rate (the share of the second
reader's facts the stage lacks), the Lincoln–Petersen estimate of the facts on those pages (n1 × n2 / m), and the
lines each missed. Writes nothing. Ezri, 2026-10-14."""
import argparse, glob, importlib.util, json, math, os, random, re, sys
from collections import defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
STOP = set("la de en kaj al li lia sia ke por kun estis estas el pri ne sed ĉe kiu kiuj tiu oni ĝi ili mi da per sur kiel ankaŭ post antaŭ jam nur".split())
W = lambda s: {w for w in re.findall(r"\w+", s.lower()) if w not in STOP and len(w) > 2}

def brief_texts(D, stage_date):
    t = open(os.path.join(D, f"facts-brief-{stage_date}.md"), encoding="utf-8").read()
    return sorted(set(re.findall(r"(/[^\s`]+?/sources/(?:ocr-preferred|born-digital-text|ocr-work)/[^`\n]+?\.txt)", t)))

def reader_ranges(bt):
    """Each reader's range from a brief's «La legiloj», PDF pages or paragraphs, a single unit allowed (2026-10-15, the
    Fable review 7: «1: ¶ 19–20 · 2: ¶ 31» was skipped)."""
    return [(int(n), int(lo), int(hi or lo)) for n, lo, hi in
            re.findall(r"(\d+): (?:PDF|¶) (\d+)(?:\s*[–-]\s*(\d+))?", re.split(r"## La leg(?:iloj|antoj)", bt)[-1])]   # «legantoj» in the briefs before 2026-10-22

def chapters(text):
    """The chapters of a text: a heading line (capitals, no digits) that later recurs as a running head with a page
    number marks a chapter's first page; in a text without running heads, the first line in capitals on a page (rougher:
    check the list against the text). -> [(first, last, heading)]. (The editor, 2026-10-14.)"""
    t = open(text, encoding="utf-8").read(); p, heads, seen = 0, [], set()
    lines = []
    for l in t.split("\n"):
        m = re.match(r"=== page (\d+) ===", l)
        if m: p = int(m.group(1)); continue
        lines.append((p, l.strip()))
    caps = lambda s: 6 <= len(s) <= 80 and re.fullmatch(r"[A-ZĈĜĤĴŜŬÀ-ÞĀ-ſ ,.:;–\-—«»']+", s) and sum(c.isalpha() for c in s) >= 5
    running = {re.sub(r"^\d+\s+|\s+\d+$", "", s) for _, s in lines if re.search(r"^\d+\s+\S|\S\s+\d+$", s)}
    for pg, s in lines:
        if caps(s) and not re.search(r"\d", s) and s in running and s not in seen: heads.append((pg, s)); seen.add(s)
    if not heads:   # no running heads (Waringhien, Li kaj ni, Manders): every line in capitals, the first on its page
        for pg, s in lines:
            if caps(s) and not re.search(r"\d", s) and (not heads or heads[-1][0] != pg): heads.append((pg, s))
    last = max(pg for pg, _ in lines) if lines else 0
    return [(pg, (heads[i + 1][0] - 1 if i + 1 < len(heads) else last), h) for i, (pg, h) in enumerate(heads)]

def prep(a):
    D = os.path.join(G, "dowse", a.source); out = os.path.join(D, f"recall-{a.tag}.md")
    if os.path.exists(out): sys.exit(f"refusing: {out} exists")
    texts = brief_texts(D, a.stage_date)
    pages = sorted({int(x) for t in texts for x in re.findall(r"=== page (\d+) ===", open(t, encoding="utf-8").read())})
    if not a.ranges: sys.exit("give --ranges of whole chapters or sections (no random pages: the editor, 2026-10-14); see «sections»")
    pick = sorted({p for r in a.ranges.split(",") for p in range(int(r.split("-")[0]), int(r.split("-")[1]) + 1)})
    brief = os.path.join(D, f"facts-brief-{a.stage_date}.md")
    prompt = (f"Legu la briefon ĉe {brief} kaj sekvu ĝin ĝis la fino. Viaj paĝoj: nur PDF {', '.join(map(str, pick))} "
              "(ignoru la dividon en la sekcio «La legiloj»; legu ĉiun el ĉi tiuj paĝoj tute).")
    open(out, "w", encoding="utf-8").write(
        f"# The recall sample of {a.source} ({a.tag})\n\n`[tools/dowse-recall.py prep: {len(pick)} of {len(pages)} PDF pages, "
        f"whole chapters or sections {a.ranges}; the second reader reads the stage brief facts-brief-{a.stage_date}.md on these "
        f"pages only; its return goes to dowse/{a.source}/recall-return-{a.tag}.md.]`\n\n"
        f"pages: {', '.join(map(str, pick))}\n\n## The prompt\n\n{prompt}\n")
    print(f"{a.source}: {len(pick)} of {len(pages)} pages → {os.path.relpath(out, G)}\n{prompt}")

def compare(a):
    D = os.path.join(G, "dowse", a.source)
    spec = importlib.util.spec_from_file_location("hf", os.path.join(ROOT, "tools", "harvest-facts.py")); hf = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(hf); sys.argv = saved
    pick = {int(x) for x in re.search(r"^pages: (.*)$", open(os.path.join(D, f"recall-{a.tag}.md"), encoding="utf-8").read(), re.M).group(1).split(", ")}
    def lines_of(paths, extra=()):
        out = []
        for l in [l for p in paths for l in open(p, encoding="utf-8")] + list(extra):
                if not l.startswith("- $$$"): continue
                l3, k = hf.take_kind(l.rstrip("\n")); r, e = hf.parse(hf.to2(l3))
                if e: continue
                m = re.search(r"(?:PDF|¶) (\d+)", r[3])
                if not m or int(m.group(1)) not in pick: continue
                out.append((hf.slug(hf.canon(r[0])), int(m.group(1)), W(hf.anchor_of(r[2])), W(r[2]), l.rstrip("\n")))
        return out
    # the stage is what the facts file holds: the readers' returns and the restored lines (aligned) of the settings
    restore = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8")).get("restore", [])
    s1 = lines_of(sorted(glob.glob(os.path.join(D, f"facts-return-{a.stage_date}-*.md"))), restore)
    s2 = lines_of([os.path.join(D, f"recall-return-{a.tag}.md")])
    # people out of scope by the register count on neither side (a brief's out-list may predate their rows: Neves 2026-10-14,
    # Baghy, Juste, Kalocsay written by the second reader, dropped from the stage)
    OUT = hf.scope_out()
    def ins(x):
        m = re.match(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))?", x[4])
        return not (m and hf.out_of_scope(hf.canon(m.group(1)), m.group(2), OUT))
    gone = sum(1 for x in s1 + s2 if not ins(x))
    s1 = [x for x in s1 if ins(x)]; s2 = [x for x in s2 if ins(x)]
    if gone: print(f"  ({gone} lines on people out of scope by the register left out of both sides)")
    def found(x, others):
        return any(x[0] == y[0] and x[1] == y[1] and (len(x[2] & y[2]) >= 3 or len(x[3] & y[3]) >= max(3, 0.5 * len(x[3]))) for y in others)
    m1 = [x for x in s1 if found(x, s2)]; m2 = [x for x in s2 if found(x, s1)]
    n1, n2, m = len(s1), len(s2), max(1, min(len(m1), len(m2)))
    print(f"{a.source}, recall {a.tag}, PDF {sorted(pick)}")
    print(f"  stage readers {n1} lines, second reader {n2}; found by the other: stage {len(m1)} of {n1}, second {len(m2)} of {n2}")
    print(f"  the stage's miss rate (the second reader's facts it lacks): {1 - len(m2) / n2:.0%}" if n2 else "  no second-reader lines")
    print(f"  the second reader's miss rate: {1 - len(m1) / n1:.0%}" if n1 else "  no stage lines")
    if n1 and n2: print(f"  Lincoln–Petersen estimate of the facts on these pages: {n1 * n2 / m:.0f} (both readers together found {n1 + n2 - m})")
    # by the stage reader's range (the editor, 2026-10-14
    #): the brief's «La legiloj» gives each reader's pages
    bt = open(os.path.join(D, f"facts-brief-{a.stage_date}.md"), encoding="utf-8").read()
    ranges = reader_ranges(bt)
    if ranges:
        print("  by the stage reader's range (pages in its range: stage lines / second reader's lines / of those, found by the stage):")
        for n, lo, hi in ranges:
            pg = {p for p in pick if lo <= p <= hi}
            if not pg: continue
            a1 = [x for x in s1 if x[1] in pg]; a2 = [x for x in s2 if x[1] in pg]; f2 = [x for x in a2 if x in m2]
            print(f"    reader {n}, PDF {lo}–{hi} ({hi - lo + 1} pages), sampled {sorted(pg)}: {len(a1)} / {len(a2)} / {len(f2)}"
                  + (f"  (the stage has {len(f2) / len(a2):.0%} of the second reader's)" if a2 else ""))
    print("  missed by the stage:"); [print("   ", x[4][:200]) for x in s2 if x not in m2]
    print("  missed by the second reader:"); [print("   ", x[4][:200]) for x in s1 if x not in m1]

def stage_parts(D, stage):
    """The stage's parts, from its agents file (one row a part since the grouped readers of 2026-10-20)."""
    ap = os.path.join(D, f"agents-{stage}.tsv")
    if not os.path.exists(ap): sys.exit(f"refusing: no {os.path.relpath(ap, ROOT)}")
    return sorted({int(m.group(1)) for l in open(ap, encoding="utf-8") for m in [re.search(rf"facts-return-{re.escape(stage)}-(\d+)\.md", l)] if m})

def parts_prep(a):
    """parts (2026-10-23; the editor): the recall sample of a batch read in parts (many texts,
    grouped readers, one brief a group, which «prep» cannot take). Whole parts drawn with a seed, 2% of the stage's parts,
    at least 2 and at most 8 (--n to set it); each re-read blind by a second legilo on a brief of its own, filled by
    dowse-brief-fill.py from the stage's own side files (--side-date), its return written in pieces as the stage's was."""
    D = os.path.join(G, "dowse", a.source); rtag = a.tag or f"{a.stage_date}r"
    out = os.path.join(D, f"recall-{rtag}.md")
    if os.path.exists(out): sys.exit(f"refusing: {os.path.relpath(out, ROOT)} exists")
    ps = stage_parts(D, a.stage_date)
    n = a.n or min(8, max(2, round(len(ps) * 0.02)))
    pick = sorted(random.Random(f"{a.source}|{a.stage_date}|recall").sample(ps, min(n, len(ps))))
    cmd = [sys.executable, os.path.join(ROOT, "tools", "dowse-brief-fill.py"), a.source, rtag, "--per-reader", "--write-returns",
           "--only", ",".join(map(str, pick)), "--side-date", a.side_date or a.stage_date,
           "--partial", f"the recall sample (the runbook, step 11): a second reading of parts {','.join(map(str, pick))}, blind to the first"]
    import subprocess
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode: sys.exit(f"refusing: the brief filler stopped:\n{(p.stdout + p.stderr)[-1500:]}")
    readers = [{"label": f"geniza/dowse/{a.source}/facts-return-{rtag}-{k}.md", "agentType": "file-reader-writer",
                "prompt": f"Legu la briefon ĉe {D}/facts-brief-{rtag}-{k}.md kaj sekvu ĝin ĝis la fino."} for k in pick]
    open(out, "x", encoding="utf-8").write(
        f"# The recall sample of {a.source} ({rtag})\n\n`[tools/dowse-recall.py parts: {len(pick)} of the {len(ps)} parts of the "
        f"stage {a.stage_date}, drawn with the seed «{a.source}|{a.stage_date}|recall»; each re-read blind on its own brief "
        f"(facts-brief-{rtag}-N.md); compared by `dowse-recall.py parts-compare {a.source} {rtag} --stage-date {a.stage_date}`.]`\n\n"
        f"parts: {', '.join(map(str, pick))}\n\n## The readers\n\n```\n{json.dumps(readers, ensure_ascii=False)}\n```\n")
    print(f"{a.source}: parts {', '.join(map(str, pick))} of {len(ps)} → {os.path.relpath(out, G)}")
    if a.json: print(json.dumps(readers, ensure_ascii=False))

def parts_compare(a):
    """parts-compare: the stage's lines of each sampled part against the second legilo's, part by part. A line counts as
    found by the other when a line of the same person in the same part shares three or more words of the anchor or half
    the words of the fact (the rule of «compare»; the page is the part here, as a lean line names no PDF page). Prints
    and writes dowse/<source>/recall-compare-<tag>.md: both counts, the matches, the stage's miss rate, Lincoln–Petersen."""
    D = os.path.join(G, "dowse", a.source)
    rp = os.path.join(D, f"recall-compare-{a.tag}.md")
    if os.path.exists(rp): sys.exit(f"refusing: {os.path.relpath(rp, ROOT)} exists")
    pick = [int(x) for x in re.search(r"^parts: (.*)$", open(os.path.join(D, f"recall-{a.tag}.md"), encoding="utf-8").read(), re.M).group(1).split(", ")]
    spec = importlib.util.spec_from_file_location("hf", os.path.join(ROOT, "tools", "harvest-facts.py")); hf = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(hf); sys.argv = saved
    def lines_of(p):
        out = []
        for l in (open(p, encoding="utf-8") if os.path.exists(p) else []):
            m = re.match(r"- \$\$\$ (.+?) \$\$\$", l)
            if not m: continue
            ps = l.rstrip("\n").split(" · ")
            fact = ps[2] if len(ps) > 3 and ps[1].startswith("{") else (ps[1] if len(ps) > 1 else "")
            anchor = ps[3] if len(ps) > 4 and ps[1].startswith("{") else (ps[2] if len(ps) > 2 else "")
            out.append((hf.slug(hf.canon(m.group(1))), W(anchor), W(fact), l.rstrip("\n")))
        return out
    def found(x, others):
        return any(x[0] == y[0] and (len(x[1] & y[1]) >= 3 or len(x[2] & y[2]) >= max(3, 0.5 * len(x[2]))) for y in others)
    rep, N1, N2, M1, M2 = [], 0, 0, 0, 0
    miss = []
    for k in pick:
        s1 = lines_of(os.path.join(D, f"facts-return-{a.stage_date}-{k}.md")); s2 = lines_of(os.path.join(D, f"facts-return-{a.tag}-{k}.md"))
        m1 = [x for x in s1 if found(x, s2)]; m2 = [x for x in s2 if found(x, s1)]
        N1 += len(s1); N2 += len(s2); M1 += len(m1); M2 += len(m2)
        rep.append(f"- part {k}: stage {len(s1)} lines, second {len(s2)}; the second's found by the stage {len(m2)}, the stage's found by the second {len(m1)}")
        miss += [f"  - part {k}, the stage lacks: {x[3]}" for x in s2 if not found(x, s1)]
    m = max(1, min(M1, M2))
    est = N1 * N2 / m if N1 and N2 else 0
    head = [f"# The recall comparison of {a.source} ({a.tag})", "",
            f"`[tools/dowse-recall.py parts-compare: parts {', '.join(map(str, pick))}; the stage {a.stage_date} against the second reading.]`", "",
            f"**The stage readers:** {N1} lines; **the second:** {N2}; matched {M1} / {M2}.",
            f"**The stage's miss rate** (the second's lines the stage lacks): {100 * (N2 - M2) / N2:.0f}%." if N2 else "**The stage's miss rate:** no second lines.",
            f"**Lincoln–Petersen** (the facts on these parts): about {est:.0f}; the stage holds {100 * N1 / est:.0f}% of them." if est else "", ""]
    text = "\n".join(head + rep + ["", "## The lines the stage lacks", ""] + (miss or ["(none)"])) + "\n"
    open(rp, "x", encoding="utf-8").write(text)
    for l in head:
        if l.startswith("**"): print(l)
    print(f"wrote {os.path.relpath(rp, ROOT)}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["sections", "prep", "compare", "parts", "parts-compare"]); ap.add_argument("source"); ap.add_argument("tag", nargs="?", default="")
    ap.add_argument("--n", type=int, default=0, help="parts: how many parts to draw (default 2%% of the stage's, 2 to 8)")
    ap.add_argument("--side-date", default="", help="parts: the date of the stage's roster, «out» list and namesakes, where it differs from the stage's tag (Ruslanda Esperantisto: stage 2026-10-17c, side files 2026-10-17)")
    ap.add_argument("--json", action="store_true", help="parts: print the readers' {label, prompt, agentType} for carney-readers.js")
    ap.add_argument("--ranges", help="whole chapters or sections, «45-50,70-79»"); ap.add_argument("--stage-date", default="2026-10-14")
    ap.add_argument("--write", action="store_true", help="compare: the full report to dowse/<source>/recall-compare-<tag>.md "
                    "(create-only), only the rates on screen; so no shell redirect is needed (the editor, 2026-10-15)")
    a = ap.parse_args()
    if a.mode == "parts": return parts_prep(a)
    if a.mode == "parts-compare": return parts_compare(a)
    if a.mode == "compare" and a.write:
        import contextlib, io
        rp = os.path.join(G, "dowse", a.source, f"recall-compare-{a.tag}.md")
        if os.path.exists(rp): sys.exit(f"{rp} exists: not overwritten")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): compare(a)
        open(rp, "w", encoding="utf-8").write(buf.getvalue())
        for l in buf.getvalue().split("\n"):
            if re.search(r"stage readers|miss rate|Lincoln", l): print(l)
        print(f"wrote {os.path.relpath(rp, ROOT)}"); return
    if a.mode == "sections":
        D = os.path.join(G, "dowse", a.source)
        bp = os.path.join(D, f"facts-brief-{a.stage_date}.md")   # a source's first brief has no stage brief yet (the Fable review 20)
        bt = open(bp, encoding="utf-8").read() if os.path.exists(bp) else ""
        ranges = reader_ranges(bt)
        texts = brief_texts(D, a.stage_date) if bt else [os.path.join(G, x) for x in json.load(open(os.path.join(D, "brief-config.json"), encoding="utf-8"))["texts"]]
        for t in texts:
            print(os.path.basename(t))
            for lo, hi, h in chapters(t):
                rd = next((f"stage reader {n}, {rhi - rlo + 1} pages" for n, rlo, rhi in ranges if rlo <= lo <= rhi), "")
                print(f"  PDF {lo}–{hi} ({hi - lo + 1} pp) {h}  [{rd}]")
        return
    prep(a) if a.mode == "prep" else compare(a)

if __name__ == "__main__":
    main()
