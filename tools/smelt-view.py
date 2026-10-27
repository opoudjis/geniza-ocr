#!/usr/bin/env python3
"""Smelt: a reading copy of an episode return, every item followed by its lines in full (the editor, 2026-10-15).

    tools/smelt-view.py <stem> <tag> [--replace]

Reads smelt/<stem>/S3-RETURN-<tag>.md and PROFILE-FROZEN-<tag>.md; writes smelt/<stem>/S3-VIEW-<tag>.md (create-only;
--replace remakes it, a derived copy and nothing else).
- an episode (E<n>:) is followed by the statements of its groups and by the lines it cites, in full;
- a group (G<n>:) by its lines in full;
- a row of the candidates' table (K, N, «mia») becomes a list item, followed by its lines in full and the statement of
  the group it points to;
- any other line that cites lines (the lines in no group, the faults) by those lines in full;
- the single-line groups the tool wrote (S3-SINGLES-<tag>.md, 2026-10-16), at the end, each with its line, those the
  reader merged («kunigita kun U…») marked; an episode's U groups are shown under it with its G groups.
An item a reader broke over several lines is joined, the breaks written \\n (the editor). Every line is shown whole, its source and locator included
(the editor). The return itself is not changed. Ezri, 2026-10-15."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from line_fields import fields
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
REF = re.compile(r"\bL(\d+)(?:\s*[–-]\s*L?(\d+))?")
ITEM = re.compile(r"^(?:- )?\**([EG])(\d+)\**(?: \([^)]*\))?:")  # 2026-10-19: «- E301:», «G2001 (nova; …):» (19c) were missed

def refs(text):
    out = []
    for m in REF.finditer(text):
        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else a
        if b - a > 10: continue   # a span («L7–L353», the whole profile), not a citation
        for n in range(a, b + 1):
            if n not in out: out.append(n)
    return out

def main():
    args = [x for x in sys.argv[1:] if x != "--replace"]
    if len(args) != 2: sys.exit(__doc__)
    stem, tag = args
    d = os.path.join(G, "smelt", stem)
    ret = open(os.path.join(d, f"S3-RETURN-{tag}.md"), encoding="utf-8").read().split("\n")
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
    line = {i + 1: l[2:] for i, l in enumerate(prof) if l.startswith("- $$$")}
    # blocks: an E or G item runs to the next item, heading or table row; its lines are joined with \n
    blocks, cur = [], None
    for l in ret:
        if ITEM.match(l) or l.startswith("#") or l.startswith("|") or l.startswith("`["):   # `[…]`: a filing note
            if cur: blocks.append(cur)
            cur = ["item" if ITEM.match(l) else "other", [l]]
            if not ITEM.match(l): blocks.append(cur); cur = None
        elif cur and cur[0] == "item":
            cur[1].append(l)
        else:
            blocks.append(["other", [l]])
    if cur: blocks.append(cur)
    texts = []
    for kind, ls in blocks:
        if kind == "item":
            ls = [x for x in ls]
            while ls and not ls[-1].strip(): ls.pop()
            texts.append(("item", "\\n".join(x.strip() for x in ls if x.strip())))
        else:
            texts.append(("other", ls[0]))
    stmt = {}
    for kind, t in texts:
        m = ITEM.match(t)
        if kind == "item" and m and m.group(1) == "G":
            stmt[int(m.group(2))] = t
    # the single-line groups the tool wrote (S3-SINGLES-<tag>.md, 2026-10-16): «U<n>: fact — L.. · atestantoj: 1»
    sp = os.path.join(d, f"S3-SINGLES-{tag}.md")
    ustmt = {int(m.group(1)): l for l in (open(sp, encoding="utf-8").read().split("\n") if os.path.exists(sp) else [])
             if (m := re.match(r"^U(\d+):", l))}
    merged = {int(u) for kind, t in texts if kind == "item" and ITEM.match(t) and ITEM.match(t).group(1) == "G"
              for u in re.findall(r"kunigita kun U(\d+)", t)}
    def show(ns, pad="  "):
        return [f"{pad}- L{n} · {line[n]}" if n in line else f"{pad}- L{n} · (not a fact line of the frozen profile)" for n in ns]
    out = [f"# S3 reading copy: {stem} ({tag})", "",
           f"`[tools/smelt-view.py from S3-RETURN-{tag}.md and PROFILE-FROZEN-{tag}.md: every item followed by its lines in "
           f"full (L = the line's number in the frozen profile). Made for reading and adjudication; the return is the record.]`", ""]
    missing = 0
    for kind, t in texts:
        if kind == "item":
            m = ITEM.match(t); out.append(t)
            if m.group(1) == "E":
                head_ = t.split(" · cirkonstancoj")[0]
                gs = [int(x) for x in re.findall(r"\bG(\d+)", head_)]
                us = [int(x) for x in re.findall(r"\bU(\d+)", head_)]
                if gs or us: out += ["  - grupoj:"] + [f"    - {stmt.get(g, f'G{g}: (not in the return)')}" for g in gs] + \
                                    [f"    - {ustmt.get(u, f'U{u}: (not in S3-SINGLES)')}" for u in us]
                ls = refs(t.split(" · cirkonstancoj", 1)[1]) if " · cirkonstancoj" in t else refs(t)
                if ls: out += ["  - linioj:"] + show(ls, "    ")
            else:
                out += show(refs(t))
            missing += sum(1 for n in refs(t) if n not in line)
            out.append("")
        elif t.startswith("|"):
            cells = [c.strip() for c in t.strip().strip("|").split("|")]
            if not refs(t) or set("".join(cells)) <= set("-: "): continue   # the header and the rule
            out.append("- **" + cells[0] + "** · " + " · ".join(cells[1:]))
            out += show(refs(t))
            out += [f"  - → {stmt[int(g)]}" for g in re.findall(r"→ G(\d+)", t) if int(g) in stmt]
            out.append("")
        elif refs(t) and not t.startswith("#"):
            out.append(t); out += show(refs(t)); out.append("")
        elif t.startswith("## 3."):   # the table becomes a list
            out += [t, ""]
        else:
            out.append(t)
    if ustmt:
        out += ["", f"## The single-line groups, written by the tool ({len(ustmt)}; {len(merged)} merged by the reader)", ""]
        for u, s in sorted(ustmt.items()):
            out.append(s + (" · (merged by the reader: see the G that names it)" if u in merged else ""))
            out += show(refs(s)); out.append("")
    chk, counts = checks(d, tag, texts, stmt, ustmt, line)
    out[4:4] = chk
    out = [code(l) for l in out]
    path = os.path.join(d, f"S3-VIEW-{tag}.md")
    with open(path, "w" if "--replace" in sys.argv else "x", encoding="utf-8") as f:   # a derived copy: --replace remakes it
        f.write("\n".join(out).rstrip("\n") + "\n")
    print(f"{os.path.relpath(path, ROOT)}: {sum(1 for k, t in texts if k == 'item')} items" + (f"; {missing} cited lines not in the profile" if missing else "")
          + "; checks: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

def code(l):
    """A cited dowse line in a code span, so that «$$$» is not read as mathematics by the Markdown preview (the editor,
    2026-10-17 12:2x). The line's own
    file pointer («  ⟵ `x-dowse.md`») stays outside the span."""
    if "$$$" not in l or "`` " in l: return l
    m = re.match(r"^(\s*(?:- )?(?:L\d+ · )?)(.*?)((?:  ⟵ `[^`]+`)?)$", l)
    return f"{m.group(1)}`` {m.group(2)} ``{m.group(3)}"

# THE CHECKS ON A RETURN (2026-10-16; the smelt runbook, S3, the «Not built yet» paragraphs of that day; the editor).
# By tool, for the editor and the resmelt, never for a reader. A line's years: every year in its date field, a guess's too
# («[sen dato; divene ≥ 1907, ≤ 1985 …]»), not the page numbers
YEAR = re.compile(r"\b(1[6-9]\d\d|20\d\d)\b")
def years_of(l):
    m = re.search(r"\$\$\$(?: *\([^)]*\))? \*\*(.+?)\*\* ·", "- " + l)
    if not m or "ĝenerala" in m.group(1): return None
    ys = [int(y) for y in YEAR.findall(re.sub(r"laŭ la paĝoj? [\d, ]+", "", m.group(1)))]
    return (min(ys), max(ys)) if ys else None

def kind_of(l):
    m = re.search(r"\*\* · \{([^:}]+)", l)
    return m.group(1).strip() if m else ""

def span_of(field):
    """An episode's date field -> (first year, last year): «post X» runs on, «antaŭ X»/«ĝis X» runs back."""
    ys = [int(y) for y in YEAR.findall(field)]
    if not ys: return None
    lo, hi = min(ys), max(ys)
    f = field.strip().lower()
    if f.startswith("post") or re.search(r"ĝis (?:la|sia) morto|kaj poste", f): hi = 9999   # «1877 ĝis la morto»
    if f.startswith("antaŭ") or f.startswith("ĝis"): lo = 0
    return lo, hi

def witness_keys(ls, line):
    """The tool's witnesses of a group (the editor): one per item and page; a copy is none; a line «derivita ↤ X»
    counts as X, and is none if X is the author of another line of the group; two works of one author are one."""
    # the fields from the shared reader (tools/line_fields.py, the harvest's own locator pattern; 2026-10-16, the editor:
    # approved to one shared reader in place of the patterns written here earlier that day)
    def author(l): return fields(l)["author"] or "?"
    def place(l):     # the item and its page or paragraph: lines from one place are one witness
        f = fields(l)
        return (f["item"], f["place"]) if f["item"] else None
    class _D:         # «derivita ↤ X», from the same reader
        @staticmethod
        def search(l):
            d = fields(l)["derived"]
            return type("M", (), {"group": lambda self, i=1: d})() if d else None
    DER = _D
    # copies are no witnesses; but a group made only of copies is shown by them (G26 of the De Beaufront return)
    own_ = [n for n in ls if line.get(n) and "kopio el" not in line[n]]
    units = {}
    for n in (own_ or [n for n in ls if line.get(n)]):
        units.setdefault(place(line[n]) or n, []).append(line[n])
    authors = {author(us[0]) for us in units.values()}
    # a place all of whose lines are derived («derivita ↤ X») is shown but not counted: we have not seen X (the editor,
    # 18:3x: ruled by the editor)
    keys, shown = [], []
    for p, us in units.items():
        ns = [n for n in ls if line.get(n, "") in us]
        lab = next((m for m in (DER.search(l) for l in us) if m), None)
        alld = all(DER.search(l) for l in us)
        where = f"{p[0]}, {p[1]}" if isinstance(p, tuple) else "?"
        shown.append(f"{where} ({', '.join(f'L{n}' for n in ns)})" + (f", derivita ↤ {lab.group(1).strip()}" if lab else "")
                     + (" — not counted, non vidimus" if alld else "") + (" (kopioj)" if not own_ else ""))
        if alld: continue
        k = author(us[0])                                              # two works of one author are one witness,
        c = re.search(r"⟦kontribuo: ([^⟧]+)⟧", us[0]) or re.search(r"\(kontribuo de ([^)]+)\)", us[0])   # the label from 2026-10-17
        if k not in [a for a, _ in keys]: keys.append((k, (p[0] if isinstance(p, tuple) else "?") + (f" ({c.group(1)})" if c else "")))
    return [it for _, it in keys], shown

def checks(d, tag, texts, stmt, ustmt, line):
    out, counts = ["## Checks by tool (for the editor and the resmelt; not for a reader)", ""], {}
    # (a) groups outside their episode's span. Only the groups an episode names (its facts), not the lines it cites as
    # circumstances, which the brief invites from any year («his later retelling»): a first try on all cited lines gave
    # 61 flags on the De Beaufront return, nearly all evidence and retellings, and missed the case it was built for (Cart's
    # 1904 judgement in a 1931–2022 episode). A group's years: its lines with a date, or a guess by the date of saying;
    # the profile's other guesses (by the source's year, by the page) are too wide to tell
    def gyears(ns):
        ys = []
        for n in ns:
            l = line.get(n, "")
            if re.search(r"\*\*\[sen dato; divene [^\]]*laŭ la (?:dato de la fonto|paĝo)", l): continue
            y = years_of(l)
            if y: ys += [y[0], y[1]]
        return (min(ys), max(ys)) if ys else None
    bad = []
    for kind, t in texts:
        m = ITEM.match(t)
        if kind != "item" or not m or m.group(1) != "E": continue
        f = t.split(" · ")
        sp = span_of(f[1]) if len(f) > 1 else None
        if not sp: continue
        head_ = t.split(" · cirkonstancoj")[0]
        for tag_, src in [("G", stmt), ("U", ustmt)]:
            for g in re.findall(rf"\b{tag_}(\d+)", head_):
                gt = src.get(int(g), "")
                gl = refs(gt.split(" — ", 1)[1] if " — " in gt else gt)
                # a judgement or an interpretation may stand outside the span of what it judges (the editor, 18:3x
                #); historiography too
                if gl and all(kind_of(line.get(n, "")) in ("juĝo", "interpreto", "historiografio") for n in gl): continue
                y = gyears(gl)
                if y and (y[1] < sp[0] - 1 or y[0] > sp[1] + 1):
                    bad.append(f"- E{m.group(2)} ({f[1].strip()}) names {tag_}{g}, dated {y[0]}{'' if y[0] == y[1] else '–' + str(y[1])}: {gt[:200]}")
    out += [f"**(a) Groups outside their episode's span** ({len(bad)}; a year of tolerance; the groups an episode names, not the lines it cites as circumstances):", ""] + (bad or ["(none)"]) + [""]
    counts["groups outside the span"] = len(bad)
    # (b) the witness count by tool, where it differs from the reader's
    diff = []
    for g, t in sorted(stmt.items()):
        ls = refs(t.split(" · ")[0] + " " + (t.split(" — ", 1)[1].split(" · ")[0] if " — " in t else ""))
        rm = re.search(r"atestantoj: (\d+)", t)
        ks, shown = witness_keys(ls, line)
        # a return with the reader's counts: the groups where they differ; without them (the template drops them): every
        # group resting on two places or more
        if (rm and int(rm.group(1)) != len(ks)) or (not rm and len(shown) >= 2):
            nd = sum(1 for s in shown if "non vidimus" in s)
            diff.append(f"- G{g}: " + (f"the reader counts {rm.group(1)}, " if rm else "") + f"the tool {len(ks)} seen ({', '.join(ks) or '—'})"
                        + (f" and {nd} derived" if nd else "") + "; "
                        f"the places it rests on ({len(shown)}): " + " · ".join(shown))
    out += [f"**(b) Witnesses: the places a group rests on** ({len(diff)}; one place = one item and page; copies left out; a place whose lines are all derived is shown, not counted (non vidimus); two works of one author count once; whether two places are one document, the tool cannot tell):", ""] + (diff or ["(none)"]) + [""]
    counts["witness counts differing"] = len(diff)
    # (c) the reader's hedged proposals, for the editor's rulings
    eb = [t for kind, t in texts if "⟦eble" in t or "◊?" in t]   # ◊? from 2026-10-16 evening (the editor)
    out += [f"**(c) The reader's proposals, ◊? (until 2026-10-16 ⟦eble: …⟧)** ({len(eb)}):", ""] + ([f"- {t[:300]}" for t in eb] or ["(none)"]) + [""]
    counts["⟦eble⟧"] = len(eb)
    # (d) lines neither the episodes nor the biography cite, nor list as unused (to be tested; the editor)
    s4 = os.path.join(d, f"S4-RETURN-{tag}.md")
    if os.path.exists(s4):
        cited = set(refs("\n".join(t for _, t in texts))) | set(refs(open(s4, encoding="utf-8").read()))
        used_u = {int(u) for _, t in texts for u in re.findall(r"\bU(\d+)", t)}
        cited |= {n for u in used_u for n in refs(ustmt.get(u, ""))}
        drop = [n for n in sorted(line) if n not in cited]
        out += [f"**(d) Lines dropped without a word** ({len(drop)}: cited by neither the episodes nor the biography, nor listed by either as unused):", ""] \
               + ([f"- L{n} · {line[n][:200]}" for n in drop] or ["(none)"]) + [""]
        counts["dropped without a word"] = len(drop)
    else:
        out += ["**(d) Lines dropped without a word:** not yet (no S4-RETURN for this tag).", ""]
    return out, counts

if __name__ == "__main__":
    main()
