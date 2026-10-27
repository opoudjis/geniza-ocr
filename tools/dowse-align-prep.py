#!/usr/bin/env python3
"""The alignment pass for restored lines: its inputs and briefs (the editor, 2026-10-14 10:0x, 10:1x: a line the new reading
already gives is dropped). The runbook, D6, point 8.

    tools/dowse-align-prep.py <date> <source>[@K][:parts] ... [--tag T]   (@K: only the restored lines from number K on;
                                                                           --tag: the files named for T, the returns of <date>)

For each source: the restored lines of dowse/<source>/facts-config.json («restore»), numbered 1…n, grouped by their
first PDF page; each page's section gives once the new readers' lines (facts-return-<date>-*.md) on the pages its
restored lines cite, then the restored lines. Split into parts (about 70 lines a reader, fewer where pages are dense;
the numbering continues across parts). Writes dowse/<source>/align-input-<date>[-k].md and align-brief-<date>[-k].md,
the brief from ocr/method/DOWSE-TEMPLATE-ALIGN-BRIEF-EO-2026-10-14.md. A part whose return is filed is refused.
Then a file-reader per brief, its return filed as align-return-<date>[-k].md, then tools/dowse-align-apply.py.
Ezri, 2026-10-14."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def pages(l):   # a PDF page, or a paragraph of an unpaged text (2026-10-15, the Fable review 7)
    return sorted(set(re.findall(r"(?:PDF|¶) (\d+)", l.split(" · [")[0])), key=int)

# BY ITEM AND PAGE (2026-10-26, the first page redowse, 2026-10-25r): pages() alone groups the 40 issues of
# L'Espérantiste that share a PDF number, and shows a restored line the new lines of every issue with that number
LOC = re.compile(r"(?:^|; | · )([^·;]+?), (?:PDF|¶) (\d+)\b")
def ipages(l):
    return {(m.group(1).strip(), m.group(2)) for m in LOC.finditer(l.split(" · [")[0])}

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    date, args = sys.argv[1], sys.argv[2:]
    tagbase = date   # «--tag T»: the files are named for T, the returns read are still those of <date> (2026-10-15)
    dry = "--dry-run" in args; args = [a for a in args if a != "--dry-run"]   # the parts and their sizes, nothing written
    if "--tag" in args:
        i = args.index("--tag"); tagbase = args[i + 1]; args = args[:i] + args[i + 2:]
    tpl = open(os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-ALIGN-BRIEF-EO-2026-10-14.md"), encoding="utf-8").read()
    tpl = tpl.split("## La briefo", 1)[1]
    kl = open(os.path.join(G, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md"), encoding="utf-8").read().split("\n")
    la = next(i for i, l in enumerate(kl, 1) if l.startswith("## The list in force"))   # found by its heading (the
    lb = next((i for i, l in enumerate(kl, 1) if i > la and l.startswith("## ")), len(kl) + 1) - 1   # Fable review 18)
    tpl = tpl.replace("liniojn 15 ĝis 64", f"liniojn {la} ĝis {lb}")
    for a in args:
        # «<source>@K»: only the restored lines from number K on (2026-10-15: the lines added after an alignment, e.g.
        # from the missing-facts report, without re-reading those already aligned); the numbering is kept
        ma = re.fullmatch(r"([^:@]+)(?:@(\d+))?(?::(\d+))?", a)
        s, frm, parts = ma.group(1), int(ma.group(2) or 1), int(ma.group(3) or 1)
        D = os.path.join(G, "dowse", s)
        rest = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8")).get("restore")
        if not rest:   # 2026-10-15, the Fable review 2: an empty «restore» aligned nothing, unseen
            sys.exit(f"refusing: {s} has no «restore» lines; write them first: tools/dowse-compare-runs.py {s} --old HEAD --write-restore (D6c step 8)")
        new = [l.rstrip("\n") for f in sorted(os.listdir(D)) if f.startswith(f"facts-return-{date}-")
               for l in open(os.path.join(D, f), encoding="utf-8") if l.startswith("- $$$")]
        if not new: sys.exit(f"refusing: no facts-return-{date}-*.md in dowse/{s}/")
        # THE LEAN RETURNS (2026-10-26): from 2026-10-18 a reader writes «(prese M) l. K», which the assembler expands to
        # «item, PDF N (prese M), l. K»; read raw, such lines cite no page, so no new line was shown (the 2026-10-25r
        # page redowse: 0 of 6 sources). Where any return line is lean, the new lines are the assembled facts file's
        # (profiles/by-source/<source>-dowse.md, the restored lines left out), which carry the full locator.
        if any(not ipages(l) for l in new):
            rs = set(rest)
            new = [l.rstrip("\n") for l in open(os.path.join(G, "profiles", "by-source", f"{s}-dowse.md"), encoding="utf-8")
                   if l.startswith("- $$$") and l.rstrip("\n") not in rs]
        brief0 = f"facts-brief-{date}.md" if os.path.exists(os.path.join(D, f"facts-brief-{date}.md")) else \
            sorted(f for f in os.listdir(D) if f.startswith("facts-brief-"))[-1]
        # every brief of the date (2026-10-26: a grouped brief, facts-brief-<date>-gA-B.md, names only its parts' texts; one
        # brief gave OGE's aligner oge.4 alone for lines on five volumes)
        briefs = [f for f in os.listdir(D) if re.fullmatch(rf"facts-brief-{re.escape(date)}(?:-g?\d+(?:-\d+)?)?\.md", f)] or [brief0]
        texts = sorted(set(t for b in briefs for t in re.findall(r"sources/(?:ocr-preferred|born-digital-text|ocr-work)/[^`\n]+?\.txt", open(os.path.join(D, b), encoding="utf-8").read())))
        numbered = list(enumerate(rest, 1))[frm - 1:]
        if not numbered: sys.exit(f"refusing: {s} has no restored lines from number {frm} on")
        # sized before written (P1 of DOWSE-THROUGHPUT-PROPOSAL-2026-10-17.md, the editor): every part is built
        # in memory first; with no «:parts» the number of parts rises until each input is under CAP characters, with
        # «:parts» a part over CAP refuses the source; nothing is written until all its parts fit (2026-10-17: three
        # sources' inputs written at 268,000–404,000 characters and rebuilt by hand)
        CAP = 200_000
        auto = ma.group(3) is None
        while True:
            built = build(s, D, date, tagbase, tpl, rest, numbered, parts, new, texts)
            big = [(t, n) for t, _, _, n, _ in built if n > CAP]
            if not big: break
            if not auto or parts >= len(numbered):
                sys.exit(f"refusing: {s}: " + ", ".join(f"{t} {n} characters" for t, n in big) + f" (over {CAP}); give more parts")
            parts += 1
        for tag, body, brief, n, stats in built:
            if not dry:
                open(os.path.join(D, f"align-input-{tag}.md"), "w", encoding="utf-8").write(body)
                open(os.path.join(D, f"align-brief-{tag}.md"), "w", encoding="utf-8").write(brief)
            print(s, tag, stats, "(dry run: not written)" if dry else "")

def build(s, D, date, tagbase, tpl, rest, numbered, parts, new, texts):
    """The parts of one source's alignment input, in memory: [(tag, input, brief, characters, the line printed)]."""
    built, size = [], -(-len(numbered) // parts)
    if True:
        for k in range(parts):
            chunk = numbered[k * size:(k + 1) * size]
            if not chunk: continue
            tag = tagbase if parts == 1 else f"{tagbase}-{k + 1}"
            if os.path.exists(os.path.join(D, f"align-return-{tag}.md")): sys.exit(f"refusing: align-return-{tag}.md exists, so its input stands")
            bypage = {}
            for n, l in chunk: bypage.setdefault(min(ipages(l), default=("", "0"), key=lambda x: (x[0], int(x[1]))), []).append((n, l))
            nrange = f"{chunk[0][0]}–{chunk[-1][0]}"
            out = [f"# La restarigitaj linioj de {s}, por la ĝisdatigo ({tag})", "",
                   f"`[La linioj {nrange} el {len(rest)} en «restore» de dowse/{s}/facts-config.json, laŭ paĝo; ĉe ĉiu paĝo unufoje la linioj de la nova legado ({date}) sur la paĝoj, kiujn ili citas.]`", ""]
            shown = 0
            for p in sorted(bypage, key=lambda x: (x[0], int(x[1]))):
                pg = set(x for _, l in bypage[p] for x in ipages(l))
                same = [x for x in new if ipages(x) & pg]; shown += len(same)
                out += [f"## {p[0]}, PDF {p[1]}", "", f"**La nova legado sur {'; '.join(f'{i}, PDF {q}' for i, q in sorted(pg, key=lambda x: (x[0], int(x[1]))))}** ({len(same)}):"]
                out += [f"- {x[2:]}" for x in same] + ["", "**La restarigitaj linioj:**", ""]
                out += [f"### {n}\n\n{l}\n" for n, l in bypage[p]]
            brief = (f"# La briefo por la ĝisdatigo de la restarigitaj linioj: {s} ({tag})\n\n"
                     f"`[Ezri, el la ŝablono ocr/method/DOWSE-TEMPLATE-ALIGN-BRIEF-EO-2026-10-14.md; la linioj {nrange}.]`\n"
                     + tpl.replace("align-input-{dato}", f"align-input-{tag}").replace("{fonto}", s).replace("{dato}", date)
                          .replace("La {n} linioj sube", f"La {len(chunk)} linioj (numeroj {nrange})").replace("{n}", str(len(chunk)))
                          .replace("{teksto}", " kaj ".join(f"`{os.path.join(G, t)}`" for t in texts)))
            body = "\n".join(out) + "\n"
            built.append((tag, body, brief, len(body), f"lines {nrange}, {len(bypage)} pages, {shown} new lines shown, {len(body)} characters"))
    return built

if __name__ == "__main__":
    main()
