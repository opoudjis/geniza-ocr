#!/usr/bin/env python3
"""Smelt S4: a reading copy of a biography, in the form the S4 template now asks for (the editor, 2026-10-17), for the biographies written before
the template said so. The return is the record and is not changed.

    tools/smelt-s4-view.py <stem> <tag> [--replace]

Reads smelt/<stem>/S4-RETURN-<tag>.md; writes smelt/<stem>/S4-VIEW-<tag>.md (create-only; --replace remakes it):
- the abstract under «### Resumo» is italic (the editor, 17:4x);
- a period summary labelled «*Resumo de la periodo.* …» or «*Resumo.* …» becomes one italic paragraph, unlabelled;
- a note marker «[3]» (digits only, so never «[L3]») becomes a superscript «³»;
- a notes paragraph «**Notoj.** [1] … [2] …» becomes «**Notoj.**» and a numbered list, one note an item.
Ezri, 2026-10-17."""
import os, re, sys
import smelt_parts    # the three parts and the ToC (2026-10-22)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

def reopen(par):
    """An italic summary paragraph with titles set back in roman (the template: `*… en* La Lumo *…*`): markdown reopens
    the italics only after a space, so punctuation after a title («Canadien*;») broke the rest of the paragraph (the
    editor, 2026-10-20). The punctuation stays roman, the italics reopen after it; spaces
    move outside the asterisks; an empty italic run is dropped."""
    if not (par.startswith("*") and par.endswith("*")) or par.startswith("**") or par.count("*") < 4: return par
    segs, out = par[1:-1].split("*"), ""
    for k, s in enumerate(segs):
        if k % 2:
            out += s; continue
        if k:
            m = re.match(r"[;:,.!?)»]+", s)
            if m: out += m.group(0); s = s[m.end():]
        lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", s, re.S).groups()
        out += lead + (f"*{core}*" if core else "") + trail
    return out

def tidy(text):
    out, abstract = [], False
    for l in text.split("\n"):
        if l.startswith("#"):
            abstract = l.strip() == "### Resumo"
        elif abstract and l.strip():
            body = l.strip()
            out.append(body if body.startswith("*") and body.endswith("*") else f"*{body}*"); continue
        m = re.match(r"^\*(?:Resumo de la periodo|Resumo)\.\*\s*(.+)$", l)
        if m:
            body = m.group(1).strip()
            out.append(body if body.startswith("*") and body.endswith("*") else f"*{body}*"); continue
        m = re.match(r"^\*\*Notoj\.\*\*\s*(.*)$", l)
        if m:
            nums = re.findall(r"\[(\d+)\]", m.group(1))
            texts = [x for x in re.split(r"\[\d+\]\s*", m.group(1)) if x.strip()]
            out += ["**Notoj.**", ""] + [f"{n}. {t.strip()}" for n, t in zip(nums, texts)]
            continue
        out.append(re.sub(r"(?<![L\w])\[(\d{1,2})\]", lambda mm: mm.group(1).translate(SUP), l))
    return "\n".join(reopen(l) for l in out)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2: sys.exit(__doc__)
    stem, tag = args
    d = os.path.join(G, "smelt", stem)
    src = open(os.path.join(d, f"S4-RETURN-{tag}.md"), encoding="utf-8").read()
    p = os.path.join(d, f"S4-VIEW-{tag}.md")
    head = (f"`[tools/smelt-s4-view.py from S4-RETURN-{tag}.md: the period summaries in italics, the notes as superscripts and a "
            f"numbered list; the three parts and the table of contents (tools/smelt_parts.py). The return is the record.]`\n\n")
    dy = smelt_parts.death_year(d, tag)
    out = smelt_parts.structure(tidy(src), dy)
    with open(p, "w" if "--replace" in sys.argv else "x", encoding="utf-8") as fh:
        fh.write(head + out)
    print(f"{os.path.relpath(p, ROOT)}: {len(re.findall(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', out))} note markers; the death {dy or 'not in the profile'}; "
          f"parts: {', '.join(l[4:] for l in out.split(chr(10)) if re.match(r'^### [IV]+\. ', l))}")
    # the gaps and conjectures, smelt by smelt (2026-10-22, the editor)
    import importlib.util
    spec = importlib.util.spec_from_file_location("smelt_marks", os.path.join(ROOT, "tools", "smelt-marks.py"))
    sm = importlib.util.module_from_spec(spec); spec.loader.exec_module(sm)
    sys.argv = [sys.argv[0], stem]; sm.main()

if __name__ == "__main__":
    main()
