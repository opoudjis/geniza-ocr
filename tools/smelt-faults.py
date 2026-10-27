#!/usr/bin/env python3
"""Smelt: the line faults the episode readers report, gathered across people into one document, with how each is fixed
(the editor, 2026-10-17 12:2x).

    tools/smelt-faults.py <tag> --list            the faults with their ids, for triage (nothing written)
    tools/smelt-faults.py <tag> [--replace]       writes smelt/FAULTS-<tag>.md

Reads «## 5. La faŭltoj de la linioj» of every smelt/<stem>/S3-RETURN-<tag>.md (one fault a top-level «- » item, its
indented lines with it); the id is <stem>-F<n> in order. The triage is smelt/FAULTS-TRIAGE-<tag>.tsv, written by Ezri:
    id <TAB> pattern <TAB> route <TAB> the problem, in English <TAB> the fix <TAB> state
route: «tool» (a fix in a tool, for every source), «line» (a DECISIONS row or a fact line, one source), «editor» (not
obvious; to the editor only if it blocks work, the rule of 2026-10-17 12:3x), «none» (no fault on checking).
The document groups the faults by pattern, the tool patterns first; under each fault the problem and the fix in English,
the reader's own words, and the lines it cites in full, in code spans (the Markdown preview reads «$$$» as mathematics).
A fault with no triage row is listed at the end as «not triaged». Ezri, 2026-10-17."""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
S = os.path.join(G, "smelt")
REF = re.compile(r"\bL(\d+)(?:\s*[–-]\s*L?(\d+))?")
ROUTES = ["tool", "line", "editor", "none"]

def refs(text):
    out = []
    for m in REF.finditer(text):
        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
        if b - a > 10: continue
        out += [n for n in range(a, b + 1) if n not in out]
    return out

def code(l):
    m = re.match(r"^(.*?)((?:  ⟵ `[^`]+`)?)$", l)
    return f"`` {m.group(1)} ``{m.group(2)}"

def faults(tag):
    """The S3 readers' faults (section 5, ids F‹n›) and the S4 writers' (part (4), «Malklaraĵoj kaj faŭltoj de la
    profilo; proponoj por la registro», ids B‹n›; the editor, 2026-10-17)."""
    out = []
    for stem in sorted(os.listdir(S)):
        p3 = os.path.join(S, stem, f"S3-RETURN-{tag}.md")
        if not os.path.exists(p3): continue
        prof = open(os.path.join(S, stem, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
        line = {i + 1: l[2:] for i, l in enumerate(prof) if l.startswith("- $$$")}
        # «## 5.» or «## (5)», «## 4.» or «## (4)»: the writers use both (2026-10-17u: the S4 returns «## 4.», which the
        # test for «## (4)» alone would have passed over, every writer's fault lost without a word)
        for p, start, letter in ((p3, lambda l: re.match(r"^## \(?5[.)]", l), "F"),
                                 (os.path.join(S, stem, f"S4-RETURN-{tag}.md"), lambda l: re.match(r"^## \(?4[.)]", l), "B")):
            if not os.path.exists(p): continue
            on, cur, n = False, None, 0
            for l in open(p, encoding="utf-8").read().split("\n"):
                if start(l): on = True; continue
                if on and (l.startswith("## ") or l.startswith("Fino")): break
                if not on: continue
                mi = re.match(r"^(?:- |\d+\. )", l)   # a list item, bulleted or numbered (Couturat's register proposals)
                if mi:
                    n += 1; cur = {"id": f"{stem}-{letter}{n}", "stem": stem, "text": [l[mi.end():]], "line": line,
                                   "file": os.path.basename(p)}; out.append(cur)
                elif l.startswith("#"):
                    cur = None                           # a sub-heading («### Proponoj por la registro») ends the item
                elif cur and l.strip() and not l.startswith("**"):
                    cur["text"].append(l.strip())
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1: sys.exit(__doc__)
    tag = args[0]
    fs = faults(tag)
    if "--list" in sys.argv:
        for f in fs: print(f["id"], "·", " ".join(f["text"]))
        return
    tp = os.path.join(S, f"FAULTS-TRIAGE-{tag}.tsv")
    tri = {}
    if os.path.exists(tp):
        for r in csv.reader(open(tp, encoding="utf-8"), delimiter="\t"):
            if not r or r[0].startswith("#"): continue
            if len(r) != 6 or r[2] not in ROUTES: sys.exit(f"refusing: a triage row not of six fields or of an unknown route: {r}")
            tri[r[0]] = dict(zip(["id", "pattern", "route", "problem", "fix", "state"], r))
    ids = {f["id"] for f in fs}
    stray = [i for i in tri if i not in ids]
    if stray: sys.exit(f"refusing: triage rows for no fault: {', '.join(stray)}")
    pats = {}
    for f in fs:
        t = tri.get(f["id"])
        key = (ROUTES.index(t["route"]), t["pattern"]) if t else (9, "not triaged")
        pats.setdefault(key, []).append(f)
    people = sorted({f["stem"] for f in fs})
    cnt = {r: sum(1 for f in fs if f["id"] in tri and tri[f["id"]]["route"] == r) for r in ROUTES}
    out = [f"# The line faults the resmelt found ({tag})", "",
           f"`[tools/smelt-faults.py from the episode readers' fault lists (section 5 of smelt/‹person›/S3-RETURN-{tag}.md) "
           f"and the triage smelt/FAULTS-TRIAGE-{tag}.tsv. Every fault, grouped by its pattern, with the problem and the fix in "
           f"English, the reader's words and the lines in full.]`", "",
           f"**{len(fs)} faults, {len(people)} people** ({', '.join(people)}). "
           f"**Fixed in a tool, for every source: {cnt['tool']}. Fixed in one source's lines: {cnt['line']}. "
           f"Not obvious: {cnt['editor']}. No fault on checking: {cnt['none']}. Not triaged: {len(fs) - len(tri)}.**", "",
           "Nothing here asks for a decision. A fault that is not obvious and blocks work comes to the editor on its own, "
           "with its context (the rule of 2026-10-17 12:3x).", "", "## The patterns", "",
           "| route | pattern | faults | done |", "|---|---|---|---|"]
    for (ri, pat), lst in sorted(pats.items()):
        done = sum(1 for f in lst if tri.get(f["id"], {}).get("state", "").startswith("done"))
        out.append(f"| {ROUTES[ri] if ri < 9 else '—'} | {pat} | {len(lst)} | {done} |")
    out.append("")
    for (ri, pat), lst in sorted(pats.items()):
        out += [f"## {pat} ({ROUTES[ri] if ri < 9 else 'not triaged'}; {len(lst)})", ""]
        for f in lst:
            t = tri.get(f["id"])
            out.append(f"### {f['id']}" + (f" · {t['state']}" if t else ""))
            out.append("")
            if t: out += [f"- **The problem:** {t['problem']}", f"- **The fix:** {t['fix']}"]
            out.append(f"- **The reader's words** (smelt/{f['stem']}/{f['file']}): {' '.join(f['text'])}")
            for n in refs(" ".join(f["text"])):
                out.append(f"  - L{n} · " + (code(f["line"][n]) if n in f["line"] else "(not a fact line of the frozen profile)"))
            out.append("")
    path = os.path.join(S, f"FAULTS-{tag}.md")
    with open(path, "w" if "--replace" in sys.argv else "x", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip("\n") + "\n")
    print(f"{os.path.relpath(path, ROOT)}: {len(fs)} faults, triaged {len(tri)}")

if __name__ == "__main__":
    main()
