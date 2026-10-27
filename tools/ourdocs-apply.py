#!/usr/bin/env python3
"""The our-documents pass, its last step by tool: write a reader's return into the file it rewrote (the dowse runbook,
D6, point 1; first used 2026-10-20 on the Henry Jacob file, 71 lines, after the Beauchemin test's 24 lines were applied
by hand).

    tools/ourdocs-apply.py RETURN.md TARGET.md [--write]   (sections «### l. N»)
    tools/ourdocs-apply.py RETURN.md [--write]             (sections «### FILE.md l. N», each file of profiles/by-source)
    tools/ourdocs-apply.py --repair FILE.md ... [--write]  (the repairs on files already written, and «facts-kinds: 4»)

The return has a section a line, «### l. N» (N the line's number in TARGET), then «- ANSTATAŬIGU» and the new lines
(«- $$$ …»), or «- FORIGU (…)», or «- SAMA (…)». Without --write it prints what it would do and the repairs; with
--write it rewrites TARGET (the file is tracked: `git diff` shows the change).

Repairs, each printed: a «samnomo» kind misused for a relative's act («{samnomo: JACOB Hermann; +fondo: …}» →
«{fondo: …}»: samnomo is for namesakes kept apart); « · » inside the voice field (after the themes), which the harvest
reads as a field separator (→ «; »); « · » between numbers in the fact («0 · 0 · 0» → «0, 0, 0»); «&amp;» → «&».
Refused: a section whose line N is not a fact line of TARGET, or a new line without «$$$». Ezri, 2026-10-20."""
import os, re, sys

# theme tags only ([B], [BIO], [X2], [LINGUISTICS]): a bracketed anchor such as «[sen ankro: …]» is not the themes
# field, and taking it for one turned the field separators after it into «;» (the Michaux line, 2026-10-20)
THEMES = re.compile(r" · ((?:\[[A-Z][A-Z0-9]*\])+) · ")

def kun_kaj(m):
    """«kun: A, B kaj C» → «kun: A kaj B kaj C»: the harvest splits a «kun:» list on «kaj» only (the facts-writing
    template, «kun «kaj» inter ili»), so a name before a comma got no copy (the pass of 2026-10-20, eight readers)."""
    return "kun: " + " kaj ".join(x.strip() for x in re.split(r",\s*|\s+kaj\s+", m.group(1)) if x.strip())

def repair(l, notes):
    o = l
    # a list with a qualifier, «LEMAIRE (René, Épernay)», is left alone: its comma is not a separator
    l = re.sub(r"kun: ([^;}()]*,[^;}()]*)(?=[;}])", kun_kaj, l, count=1) if l.startswith("- $$$") else l
    l = re.sub(r"\{samnomo: [^;}]*; \+", "{", l)
    l = l.replace("&amp;", "&")
    l = re.sub(r"(\d) · (\d)", r"\1, \2", l)
    m = THEMES.search(l)
    if m:
        head, tail = l[:m.end()], l[m.end():]
        l = head + tail.replace(" · ", "; ")
    if l != o: notes.append(f"repaired: {o[:90]}…")
    return l

def parse(ret, only=None):
    """Sections «### l. N» (one file) or «### FILE.md l. N» (a group): {file or None: {N: section}}."""
    secs, cur = {}, None
    for x in open(ret, encoding="utf-8").read().split("\n"):
        m = re.match(r"^### (?:`?([\w.\-…]+\.md)`? )?l\. (\d+)\b", x)
        if m:
            f = m.group(1)
            if f and "…" in f:  # a reader's shortened name («waringhien-…-fold-2026-09-19.md», group 07, 2026-10-20)
                a, b = f.split("…", 1)
                hits = [g for g in os.listdir(BS) if g.startswith(a) and g.endswith(b)]
                if len(hits) != 1: sys.exit(f"{ret}: «{f}» names {len(hits)} files, not one: {hits[:5]}")
                f = hits[0]
            cur = (f, int(m.group(2)))
            secs.setdefault(f, {})[cur[1]] = {"verdict": None, "lines": []}; continue
        if cur is None: continue
        if x.startswith("## ") or x.startswith("---"): cur = None; continue
        s = secs[cur[0]][cur[1]]
        v = re.match(r"^- (ANSTATAŬIGU|FORIGU|SAMA)\b", x)
        if v and s["verdict"] is None: s["verdict"] = v.group(1); continue
        if x.startswith("- $$$"): s["lines"].append(x)
    return secs

BS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "published", "heterophony-resources", "geniza", "profiles", "by-source")

def repair_files(files):
    """--repair FILE.md ...: the repairs on every fact line of files already written, and the «facts-kinds: 4» line
    (the editor, 2026-10-19) where the head has neither it nor «facts-format:», put after the title; without it the
    harvest reads no kinds and writes no copies, so a line removed as the double of a «kun:» line lost that person's
    fact (the pass of 2026-10-20). Without --write it prints what it would do."""
    rc = 0
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(BS, f)
        L = open(p, encoding="utf-8").read().split("\n")
        notes = []
        out = [repair(x, notes) if x.startswith("- $$$") else x for x in L]
        head = any(re.match(r"^\W*facts-(kinds|format):", x) for x in out[:20])
        if not head:
            out = out[:1] + ["", "facts-kinds: 4"] + out[1:]
        print(f"{os.path.basename(p)}: {len(notes)} lines repaired" + ("" if head else "; «facts-kinds: 4» added"))
        for x in notes[:10]: print("  " + x)
        if "--write" in sys.argv and (notes or not head):
            open(p, "w", encoding="utf-8").write("\n".join(out))
    return rc

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--repair" in sys.argv: sys.exit(repair_files(a))
    if len(a) not in (1, 2): sys.exit(__doc__)
    allsecs = parse(a[0])
    if len(a) == 2:
        jobs = [(a[1], allsecs.get(None, {}) or allsecs.get(os.path.basename(a[1]), {}))]
    else:
        jobs = [(os.path.join(BS, f), s) for f, s in allsecs.items() if f]
    rc = 0
    for tgt, secs in jobs:
        rc |= apply_one(tgt, secs)
    sys.exit(rc)

def apply_one(tgt, secs):
    L = open(tgt, encoding="utf-8").read().split("\n")
    notes, bad = [], []
    out, counts = [], {"ANSTATAŬIGU": 0, "FORIGU": 0, "SAMA": 0, "new lines": 0}
    for n, x in enumerate(L, 1):
        s = secs.get(n)
        if not s:
            out.append(x); continue
        if not x.startswith("- $$$"):
            bad.append(f"l. {n} is not a fact line: {x[:80]}"); out.append(x); continue
        v = s["verdict"]
        if v == "ANSTATAŬIGU" and s["lines"]:
            new = [repair(y, notes) for y in s["lines"]]
            out += new; counts["ANSTATAŬIGU"] += 1; counts["new lines"] += len(new)
        elif v == "FORIGU":
            counts["FORIGU"] += 1
        else:
            out.append(x); counts["SAMA" if v == "SAMA" else "SAMA"] += 1
            if v not in ("SAMA",): notes.append(f"l. {n}: verdict {v} without lines, kept")
    missing = [n for n in secs if n > len(L)]
    bad += [f"l. {n} beyond the file" for n in missing]
    print(f"{os.path.basename(tgt)}: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f"; {len(notes)} notes")
    for x in notes[:40]: print("  " + x)
    if bad:
        for x in bad: print("  REFUSED: " + x)
        return 1
    if "--write" in sys.argv:
        open(tgt, "w", encoding="utf-8").write("\n".join(out))
        print(f"wrote {tgt}")
    return 0

if __name__ == "__main__":
    main()
