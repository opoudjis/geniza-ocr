#!/usr/bin/env python3
"""smelt-marks.py — how many gaps and conjectures each biography carries, smelt by smelt (2026-10-22; the editor).

    python3 tools/smelt-marks.py [STEM ...]

Reads part (1) of every joined biography, smelt/<stem>/S4-RETURN-<tag>.md (not the parts, the abstracts, the copies
before a polish or a new abstract), and counts its marks: ⚫️ (truo, a gap in the sources read), ◊? (konjekto, «eble»),
∴ (konkludo), «(=» (kalkulo), ❓; with the sections, the words and the citations, and the gaps and conjectures per
thousand words, since a longer biography has more of both. Writes smelt/MARKS-TRACKER.tsv, all stems and tags, rewritten
whole at each run (it is derived; the returns are the record); prints the rows of the stems asked, or of all. Run by
tools/smelt-s4-view.py after each view. Ezri, 2026-10-22."""
import glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "published", "heterophony-resources", "geniza", "smelt")
COLS = ["stem", "tag", "sections", "words", "citations", "truo ⚫️", "eble ◊?", "konkludo ∴", "kalkulo =", "❓",
        "truo / 1000 words", "eble / 1000 words"]

def part1(t):
    ls = t.split("\n")
    a = next((i for i, l in enumerate(ls) if l.startswith("## 1.")), None)
    if a is None: return None
    b = next((i for i, l in enumerate(ls) if i > a and re.match(r"^## \d", l)), len(ls))
    return "\n".join(ls[a:b])

def row(stem, tag, t):
    w = len(re.sub(r"\[L[^\]]*\]", "", t).split())
    tr, eb = t.count("⚫"), t.count("◊?")
    return [stem, tag, len(re.findall(r"^### \d+\.", t, re.M)), w, len(re.findall(r"\[L\d", t)) + sum(x.count(",") for x in re.findall(r"\[L\d[^\]]*\]", t)),
            tr, eb, t.count("∴"), len(re.findall(r"\(=", t)), t.count("❓"),
            f"{1000 * tr / w:.1f}" if w else "", f"{1000 * eb / w:.1f}" if w else ""]

def main():
    want = set(sys.argv[1:])
    rows = []
    for f in sorted(glob.glob(os.path.join(S, "*", "S4-RETURN-*.md"))):
        m = re.match(r"S4-RETURN-(\d{4}-\d\d-\d\d[a-z0-9]*)\.md$", os.path.basename(f))
        if not m: continue                       # the parts (-p3), abstracts (-ps), copies (-unpolished, -abstract1)
        t = part1(open(f, encoding="utf-8").read())
        if t: rows.append(row(os.path.basename(os.path.dirname(f)), m.group(1), t))
    with open(os.path.join(S, "MARKS-TRACKER.tsv"), "w", encoding="utf-8") as fh:
        fh.write("# The marks of each biography, smelt by smelt: tools/smelt-marks.py, rewritten at each run (the editor, 2026-10-22).\n")
        fh.write("\t".join(COLS) + "\n" + "".join("\t".join(map(str, r)) + "\n" for r in rows))
    for r in rows:
        if not want or r[0] in want: print("  ".join(f"{c}: {v}" for c, v in zip(COLS, r) if c not in ("kalkulo =",)))
    print(f"smelt/MARKS-TRACKER.tsv: {len(rows)} biographies")

if __name__ == "__main__":
    main()
