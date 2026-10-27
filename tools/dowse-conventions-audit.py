#!/usr/bin/env python3
r"""dowse-conventions-audit.py — the audit of the conventions of the dowse files, built from the live code and files.

Renamed 2026-10-22 from dowse-conventions-key.py (the editor): what
it writes is an audit, the code's rules and the files' usage, for finding drift; the key for a reader is a separate,
hand-written page, geniza/prosopografio/sxlosilo.md (moved 2026-10-24 from ocr/method/DOWSE-CONVENTIONS-KEY-2026-10-22.md
into the prosopography's documentation folder, for the editor's review before publication).

Why (2026-10-22; the editor). The conventions of a dowse line (its fields, the
date vocabulary, the plan mark, the kinds, the themes, the voice, our ⟦…⟧ notes, the marks only the profiles show) are
spread over tools/date_vocab.py, tools/dowse-facts-assemble.py, tools/harvest-facts.py, the lean brief template and
the kinds list. This tool reads them where they live, so the audit is as current as the code: the date forms are the
vocabulary's own test cases, parsed now; the rules are the regular expressions and string literals of the tools; the
meanings of the fields are the brief's own words; every section counts what the dowse files actually hold.

    python3 tools/dowse-conventions-audit.py [--out FILE]

Write-set: --out only (default geniza/ocr/method/DOWSE-CONVENTIONS-AUDIT-‹today›.md), a new file: it refuses to
overwrite. Rerun it after a change of convention; never edit the audit by hand. (Ezri, 2026-10-22)"""
import argparse, ast, collections, csv, datetime, glob, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEN = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
sys.path.insert(0, HERE)
import date_vocab


def module(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = argv
    return m


def src(fn): return open(os.path.join(HERE, fn), encoding="utf-8").read()


def test_cases():
    """date_vocab._test's «cases» and «bad», read from its source (they are the vocabulary's own examples)."""
    tree = ast.parse(src("date_vocab.py"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_test")
    cases, bad = {}, []
    for st in fn.body:
        if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
            if st.targets[0].id == "cases": cases = ast.literal_eval(st.value)
            if st.targets[0].id == "bad": bad = ast.literal_eval(st.value)
    return cases, bad


def date_form(d):
    """The form of a date field, for the census."""
    d = d.strip()
    rules = [("☞ (a plan)", r".*☞$"), ("[sen dato]", r"\[sen dato\]"), ("[ĝenerala]", r"\[ĝenerala\]"),
             ("[n] (the issue's date, before expansion)", r"\[n\]"), ("dum aŭ antaŭ …", r"dum aŭ antaŭ "),
             ("dum aŭ post …", r"dum aŭ post "), ("dum … (an event)", r"dum "), ("antaŭ …", r"antaŭ "), ("post …", r"post "),
             ("ekde …", r"ekde "), ("ĝis …", r"ĝis "), ("de … ĝis …", r"de .+ ĝis "), ("inter … kaj …", r"inter .+ kaj "),
             ("ĉirkaŭ …", r"ĉirkaŭ "), ("verŝajne …", r"verŝajne "), ("fine de …", r"fine de "), ("komence de …", r"komence de "),
             ("meze de …", r"meze de "), ("la …aj jaroj", r"la \d+aj jaroj"), ("… m.s. (old style)", r".* m\.s\.$"),
             ("several copies (2018+2019)", r"\d{4}(?:\+\d{4})+$"), ("a day", r"\d{4}-\d\d-\d\d$"),
             ("a month", r"\d{4}-\d\d$"), ("a year", r"\d{4}$")]
    for name, rx in rules:
        if re.match(rx, d): return name
    return "other"


def main():
    ap = argparse.ArgumentParser()
    today = datetime.date.today().isoformat()
    ap.add_argument("--out", default=os.path.join(GEN, "ocr", "method", f"DOWSE-CONVENTIONS-AUDIT-{today}.md"))
    a = ap.parse_args()
    if os.path.exists(a.out): sys.exit(f"dowse-conventions-audit:{a.out} exists; not overwriting it (give --out)")
    hf = module("harvest_facts", "harvest-facts.py")
    asm = module("dowse_facts_assemble", "dowse-facts-assemble.py")
    hsrc, asrc = src("harvest-facts.py"), src("dowse-facts-assemble.py")

    files = sorted(glob.glob(os.path.join(GEN, "profiles", "by-source", "*-dowse.md")))
    lines = [l.rstrip("\n") for f in files for l in open(f, encoding="utf-8") if l.startswith("- $$$")]
    dates, kinds, themes, marks, labels, notes = (collections.Counter() for _ in range(6))
    other = []
    for l in lines:
        ps = l.split(" · ")
        md = re.search(r"\*\*([^*]+)\*\*", ps[0])
        if md:
            dates[date_form(md.group(1))] += 1
            if date_form(md.group(1)) == "other" and len(other) < 15: other.append(md.group(1).strip())
        mk = re.match(r"\{([^:;}]+)", ps[1]) if len(ps) > 1 else None
        if mk: kinds[mk.group(1).strip()] += 1
        for t in re.findall(r"\[([A-Z?]+)\]", ps[-2] if len(ps) > 2 else ""): themes[t] += 1
        v = ps[-1]
        for m_ in "✅📣📄⚠❓⛔": marks[m_] += v.count(m_)
        for lab, rx in (("sendependa", r"\bsendependa\b"), ("derivita ↤ …", r"\bderivita\b"), ("refutas: …", r"\brefutas:"),
                        ("sen fontindiko", r"\bsen fontindiko\b"), ("(refutita aserto), in the fact", r"\(refutita aserto\)"),
                        ("⟳ atestanto: … (a witness line)", r"⟳ atestanto:")):
            if re.search(rx, l): labels[lab] += 1
        for n in re.findall(r"⟦([^⟧]*)⟧", v):
            head = re.split(r"[:,;]| \d| «", n.strip(), maxsplit=1)[0].strip()
            if len(re.sub(r"\W", "", head)) < 2: head = n.strip()[:30]    # «⟦— …⟧», «⟦«x» …⟧»: show the note's start
            notes[(head[:40], bool(asm.TOOL_NOTE.match("⟦" + n + "⟧")))] += 1

    T = os.path.join(GEN, "ocr", "method", "DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-18-LEAN.md")
    tpl = open(T, encoding="utf-8").read()
    out = [f"# The dowse conventions: the audit ({today})", "",
           f"**GENERATED by `tools/dowse-conventions-audit.py`from the live code and files; do not edit by hand, rerun it.** "
           f"Read: `tools/date_vocab.py` (its own test cases), `tools/dowse-facts-assemble.py`, `tools/harvest-facts.py`, "
           f"the lean brief template (`ocr/method/{os.path.basename(T)}`), the kinds in force "
           f"(`ocr/method/EVENT-KINDS-PROPOSAL-2026-10-13.md`), `profiles/ISSUE-DATES.tsv`, `profiles/EVENT-CALENDAR.tsv`, "
           f"and the {len(files)} dowse files of `profiles/by-source/` ({len(lines):,} lines), whose usage every count below is.", ""]

    # 1. the line
    out += ["## 1. The line, as the readers are told to write it", "",
            "From the lean brief template, «La linio» (the readers' own words, in Esperanto):", ""]
    m = re.search(r"\*\*La linio:\*\*\n\n(`[^`]+`)\n\n(.*?)\n\n\*\*La raporto", tpl, re.S)
    if m:
        out += [m.group(1), ""]
        for b in re.findall(r"^- \*\*([^*]+)\*\*(.*)$", m.group(2), re.M):
            out.append(f"- **{b[0]}**{b[1][:420]}{'…' if len(b[1]) > 420 else ''}")
    mt = re.search(r"\*\*La iloj kontrolas la formon kaj plenigas la reston\.\*\* (.*?)\n", tpl)
    if mt: out += ["", f"What the tools add after the reading (the template): «{mt.group(1)}»"]
    out.append("")

    # 2. dates
    cases, bad = test_cases()
    out += ["## 2. The date field", "", "The vocabulary's own test cases (`date_vocab._test`), each parsed now; «kind» and «EDTF» are what the parser returns.", "",
            "| Written | Kind | EDTF | Parses as tested |", "|---|---|---|---|"]
    for f, (k, e) in cases.items():
        try: d = date_vocab.parse(f); ok = (d.kind, d.edtf) == (k, e); got = (d.kind, d.edtf)
        except ValueError: ok, got = False, ("refused", "")
        out.append(f"| `{f}` | {got[0]} | {got[1] or '—'} | {'yes' if ok else 'NO: expected ' + k + ' ' + e} |")
    out += ["", "Refused: " + ", ".join(f"`{b}`" for b in bad) + ".", "",
            "The forms in the dowse files now:", "", "| Form | Lines |", "|---|---|"]
    out += [f"| {k} | {v:,} |" for k, v in dates.most_common()]
    if other: out += ["", "«Other», the first examples: " + "; ".join(f"`{o}`" for o in other) + "."]
    out.append("")

    # 3. plans
    rx_plan = re.search(r're\.search\(r"(\\bplanit[^"]*)", kind\)', asrc)
    rx_end = re.search(r'ended = re\.search\(r"([^"]+)", kind\)', asrc)
    rx_bound = re.search(r'bounded = re\.match\(r"([^"]+)", dv\)', asrc)
    st_lits = sorted(set(re.findall(r'st = f?"((?:realigita|malsukcesis|prokrastita|ne konfirmita|la evento okazis)[^"{]*)', hsrc)))
    act = sorted(set(re.findall(r'"(propono|anonco)"', hsrc)))
    out += ["## 3. Plans (☞) and their statuses", "",
            f"- **☞** (`date_vocab.PLANNED` = «{date_vocab.PLANNED}»): the assembler adds it where the kind matches `{rx_plan.group(1) if rx_plan else '?'}`, "
            f"not where it matches `{rx_end.group(1) if rx_end else '?'}` (given up, put off, failed), nor where the date matches `{rx_bound.group(1) if rx_bound else '?'}` (bounded from above).",
            "- **⟦anoncita ‹date›⟧** in the voice: the issue's date by its masthead (or `profiles/ISSUE-DATES.tsv`); «, laŭ la enhavo» where the issue prints no month and its contents date it.",
            "- A plan dated by its issue alone becomes «dum aŭ post ‹the announcement›☞».",
            f"- In the profiles only: the act is shown again at its ⟦anoncita⟧ date, its voice opening «la {' / la '.join(act)} de plano, ☞ …»; the plan carries «· stato: …», one of: "
            + "; ".join(f"«{s.strip()}»" for s in st_lits) + ".", ""]

    # 4. kinds
    kl = hf.kind_list()
    out += ["## 4. Kinds", "", f"The list in force ({len(kl)} kinds), with the lines whose first kind it is:", "",
            "| Kind | Lines |", "|---|---|"]
    out += [f"| {k} | {kinds.get(k, 0):,} |" for k in sorted(kl, key=lambda k: -kinds.get(k, 0))]
    off = {k: v for k, v in kinds.items() if k not in kl}
    if off: out += ["", "Not on the list (older formats, or faults the check reports): " + ", ".join(f"{k} {v}" for k, v in sorted(off.items(), key=lambda x: -x[1])[:25]) + "."]
    out.append("")

    # 5. themes
    tsrc = re.search(r"def themes\(fact\):\n(.*?)\n    return", asrc, re.S)
    trules = re.findall(r're\.search\(r"([^"]+)"[^\n]*\n(?:\s*r"[^"]*"[^\n]*\n)*\s*t\.append\("([A-Z?]+)"\)', tsrc.group(1)) if tsrc else []
    out += ["## 5. Themes", "", "The codes in the dowse files, and the assembler's rule for each where it assigns one (`themes()`; a reader's own code is kept):", "",
            "| Code | Lines | The assembler's rule (its pattern, cut) |", "|---|---|---|"]
    rule = {c: p for p, c in trules}
    out += [f"| [{t}] | {n:,} | {('`' + rule[t][:90] + '`') if t in rule else '—'} |" for t, n in themes.most_common()]
    out.append("")

    # 6. voice
    mv = re.search(r"^- \*\*voĉo:\*\*(.*)$", tpl, re.M)
    out += ["## 6. Voice", "", f"The template: «{mv.group(1).strip()[:700]}…»" if mv else "", "",
            "| Mark | Count |", "|---|---|"]
    out += [f"| {k} | {v:,} |" for k, v in marks.most_common() if v]
    out += ["", "| Label | Lines |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in labels.most_common()]
    out.append("")

    # 7. notes
    out += ["## 7. Our notes ⟦…⟧", "",
            "A note in ⟦…⟧ is the project's, never the reader's or the source's. The tool's own notes are written again at every "
            f"reassembly (the assembler's `TOOL_NOTE`: `{asm.TOOL_NOTE.pattern}`) and never registered in `INTERVENTIONS.tsv`; "
            "every other note is ours and kept there, by the key of its line. By the note's first words:", "",
            "| Note begins | Whose | Count |", "|---|---|---|"]
    out += [f"| ⟦{h}… | {'the tool' if tool else 'ours'} | {n:,} |" for (h, tool), n in notes.most_common(60)]
    out += ["", f"({len(notes)} distinct beginnings; the 60 commonest shown.)", ""]

    # 8. issue dates and the calendar
    basis = collections.Counter()
    p = os.path.join(GEN, "profiles", "ISSUE-DATES.tsv")
    for r in csv.reader(open(p, encoding="utf-8"), delimiter="\t"):
        if len(r) > 3 and not r[0].startswith("#") and r[0] != "item": basis[r[3]] += 1
    dated = []
    for cp in sorted(glob.glob(os.path.join(GEN, "dowse", "*", "brief-config.json"))):
        c = open(cp, encoding="utf-8").read()
        if '"dating"' in c or '"masthead"' in c or '"issue_start"' in c: dated.append(os.path.basename(os.path.dirname(cp)))
    cal = [l.rstrip("\n").split("\t") for l in open(os.path.join(GEN, "profiles", "EVENT-CALENDAR.tsv"), encoding="utf-8")
           if not l.startswith("#") and not l.startswith("event\t") and l.strip()]
    out += ["## 8. Issue dates and the calendar", "",
            f"- **An issue's date** is its masthead's: first `profiles/ISSUE-DATES.tsv`, for the issues no pattern reads ({sum(basis.values())} rows: "
            + ", ".join(f"«{k}» {v}" for k, v in basis.items()) + f"), then the masthead patterns of the sources with «dating» or «journal» settings ({', '.join(dated)}), "
            "and only then an item's name.",
            f"- **The calendar** (`profiles/EVENT-CALENDAR.tsv`, {len(cal)} events; «ne okazis»: "
            + (", ".join(f"{r[0]} {r[2]}" for r in cal if len(r) > 5 and r[5].strip() == "ne okazis") or "none") + "): in the profiles a congress dated "
            "by its year alone shows «[la kongreso: ‹days›, laŭ la kalendaro]», or «[la kongreso planita: ‹days›, ne okazis, laŭ la kalendaro]».", ""]

    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"dowse-conventions-audit:{len(lines):,} lines of {len(files)} dowse files → {os.path.relpath(a.out, ROOT)}")


if __name__ == "__main__":
    main()
