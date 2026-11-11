#!/usr/bin/env python3
r"""smelt_inputs.py — what a smelt reader reads, made smaller and whole by tool (Fable's proposals,
geniza/ocr/method/SMELT-OPTIMISATION-PROPOSALS-2026-10-30.md; the editor, 2026-10-30 12:2x–12:3x: ruled by the editor). No tokens; nothing a reader must know
is left out.

- register(text, out): proposal 1. The names register cut to the rows whose names stand in the reader's own text (case,
  accents and points folded, each name's words sought whole), the long columns «source» and «note» left out, a column
  «atestita» from NAMES-REGISTER-EVIDENCE.tsv (so that file is not read), and under the rows an index of every row's
  names, «name → main form», so a reader proposing a row sees that one exists (the mitigation).
- short(n, line, label, u): proposal 2, a profile line in the short form: the L (and proposal 3's U, for a line that is
  a single-line group), date, kind, fact, anchor, the fact label for the locator («LEsp 1901.3:191a»; a line with no
  label keeps its locator), voice and its labels; the head, the themes and the dowse file left out. A line without a
  kind (formats 2 and 3) stays whole.
- sources(nums, prof, label): proposal 4, the brief's sources line on the reader's own lines, by siglum with the
  register's entry, one a line, most lines first; it is also the legend of the short form's sigla.
- for_reader(path): proposal 5, a file the Read tool returns whole: a file over CUT characters is written again for the
  reader in parts cut at a line, <stem>-read-1.md, -2 …, each naming the next; the whole file stays as it is for the
  tools. (Bourlet's S4 part-1 writer, 2026-10-30: S4-LINES, 205,643 characters, came back to its line 91 and was read on
  in five slices; its S3 return came back to line 190 of 305.)
- SHORT_S3, SHORT_S4: the short form's sentence for the two templates' «La formo de linio» (drafted by Ezri; approved by the editor), put in by smelt-compress.py and smelt-periods.py in place of the full form's.

    python3 tools/smelt_inputs.py check-register <stem> <tag>     # proposal 1's check: the rows the writers used, kept?

Ezri, 2026-10-30."""
import csv, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import factline as FL
import sigla
G = os.path.join(os.path.dirname(HERE), "published", "heterophony-resources", "geniza")
REG = os.path.join(G, "profiles", "NAMES-REGISTER.tsv")
EVID = os.path.join(G, "profiles", "NAMES-REGISTER-EVIDENCE.tsv")
CUT = 30000   # characters a reader's file may hold to come back whole from one Read (Bourlet's writer: ~38,000 came back)

# THE SHORT FORM'S SENTENCES, in place of the templates' full form (the S4 template's «La formo de linio» sentence, the
# S3 template's «Novaj linioj» sentence); the rest of each paragraph (the voice, the doubts, the labels) stands
# THE COMMONEST VOICE LABELS AS CODES (2026-11-10; the editor's to Fable's proposal 4, and
#): their count in Schneeberger's, Bourlet's and De Beaufront's profiles
VOICE_CODES = (("⟦la dato de la numero⟧", "zzzdn"), ("⟦la jaro laŭ la numero⟧", "zzzjn"), ("sen fontindiko", "zzzsf"))
VOICE_KEY = (" **La mallongigoj en la etikedoj de la voĉo:** «zzzsf» = sen fontindiko; «zzzdn» = ⟦la dato de la numero⟧ (la "
             "dato de la linio estas tiu de la numero de la gazeto, ne nepre tiu de la okazo); «zzzjn» = ⟦la jaro laŭ la numero⟧. "
             "Ne skribu ilin en via teksto")
SHORT_FORM = ("`L‹n› (U‹n›) · dato · {speco: objekto} · fakto · ankro · siglo · voĉo (etikedoj)`, la mallonga formo de la ilo "
              "(2026-10-30): **L‹n›** estas la numero de la linio en la tuta frosta profilo, per kiu vi citas ĝin; **(U‹n›)** staras "
              "nur ĉe linio, kiu estas unuopa grupo de la ilo; la **ankro** estas la vortoj de la fonto mem; la **siglo** "
              "(«LEsp 1901.3:191a») nomas la fonton: la verkon (la listo de la fontoj donas ĝian titolon), la jaron kaj la "
              "numeron, la presitan paĝon kaj la literon de la linio sur ĝi. Linio, kies fonto ankoraŭ ne havas siglon, portas "
              "sian lokindikon. La nomo de la persono, la temoj kaj la dosiero de la dowse estas forlasitaj. En via teksto nomu "
              "fonton per ĝia titolo, ne per ĝia siglo." + VOICE_KEY)
S4_FULL = "`- $$$ NOMO $$$ (kvalifiko) **dato** · {speco: objekto} · fakto · ankro · lokindiko · [temoj] · voĉo (etikedoj)`; pli malnovaj linioj sen la speca kampo."
SHORT_S4 = SHORT_FORM + "; pli malnovaj linioj, sen la speca kampo, staras en sia plena formo."
S3_FULL = "Novaj linioj: `- $$$ NOMO $$$ (kvalifiko) **dato** · {speco: objekto} · fakto · ankro · lokindiko · [temoj] · voĉo (etikedoj)`."
SHORT_S3 = "Novaj linioj: " + SHORT_FORM + "."

def fold(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().replace(".", "")

WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
STOP = {"esperanto", "grupo", "societo", "societe", "society", "group", "pour", "born", "same", "kaj", "esperantista",
        "esperantiste", "internacia", "lingvo", "langue", "ocr", "with", "from", "the", "der", "die", "das", "des", "von", "und"}

def _cores(field):
    """A name field's forms: the text before its first «(», and each bracket's text («SFPE (SPPE)»: SFPE, SPPE)."""
    f = (field or "").strip()
    out = [f.split("(")[0]] + re.findall(r"\(([^()]*)\)", f)
    return [c.strip(" ;,") for c in out if c.strip(" ;,")]

def _sig(core):
    """A form's telling words: four letters or more, or capitals («UEA», «SFPE»), not common words, a hyphened or
    elided word by its parts («Boulogne-sur-Mer»: boulogne; the check of 2026-10-30, Bourlet part 1); a form of common
    words only («Lingvo Internacia») by those."""
    ws = [p for w in WORD.findall(core) for p in re.split(r"['’-]", w)]
    big = [w for w in ws if len(w) >= 4 or (w.isupper() and len(w) >= 2)]
    return {fold(w) for w in big if fold(w) not in STOP} or {fold(w) for w in big}

def _text_words(text):
    t = fold(text)
    ws = set(WORD.findall(t))
    ws |= {p for w in ws for p in re.split(r"['’-]", w)}
    # the umlaut written out («Schaefer» for «SCHÄFER», Devjatnin's part 3, the check of 2026-10-30)
    ws |= {re.sub(r"([aou])e", r"\1", w) for w in ws}
    # an Esperanto word's endings («la klubon Progreso», «Esperon»: Bourlet's part 5, the same check)
    return ws | {re.sub(r"([aoe])(?:jn|j|n)$", r"\1", w) for w in ws}

def rows():
    lines = [l.rstrip("\n") for l in open(REG, encoding="utf-8") if not l.startswith("#")]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]

HALF = None   # None: every telling word of a form; True: half of them (a test, 2026-10-30)

def kept(text):
    """The register's rows whose names stand in the text: some form of the name, the same_as or the main form with at
    least half its telling words present («Klubo Progreso» by «Progreso»; the check of 2026-10-30, Bourlet part 5). A
    row too many costs a line; a row missing costs a name's main form and a mark."""
    tw = _text_words(text)
    out = []
    for r in rows():
        forms = [s for fld in ("name", "same_as", "main_form") for s in map(_sig, _cores(r.get(fld)))]
        if any(s and (s <= tw if HALF is None else 2 * len(s & tw) >= len(s)) for s in forms): out.append(r)
    return out

def register(text, out):
    """Proposal 1: the cut register for one reader, written to `out`; (path, rows kept, rows in all)."""
    ev = {(r.get("name", ""), r.get("same_as", "")) for r in csv.DictReader(open(EVID, encoding="utf-8"), delimiter="\t")}
    rs, allr = kept(text), rows()
    cols = ["name", "same_as", "main_form", "relation", "from", "to", "status"]
    body = [f"# La registro de nomoj, nur la vicoj pri la nomoj de via parto ({len(rs)} el {len(allr)})",
            f"`[tools/smelt_inputs.py: the rows of profiles/NAMES-REGISTER.tsv whose names stand in this reader's lines; «source» "
            f"and «note» left out; «atestita»: «jes» where the corpus states the row (NAMES-REGISTER-EVIDENCE.tsv). The whole "
            f"register is on disk for Ezri, who checks every proposed row against it (smelt_inputs.py check-proposals).]`", "",
            "\t".join(cols + ["atestita"])]
    body += ["\t".join([r.get(c, "") for c in cols] + ["jes" if (r.get("name", ""), r.get("same_as", "")) in ev else ""]) for r in rs]
    # THE INDEX OF EVERY ROW'S NAMES, OUT (2026-11-10; the editor's to Fable's proposal 1, ocr/method/SMELT-OPTIMISE-
    # FABLE-2026-11-10.md: about 29,000 characters the same for every legilo, the mitigation of 2026-10-30): a proposed row
    # that exists already is found by check_proposals() on the returns instead
    open(out, "w", encoding="utf-8").write("\n".join(body) + "\n")
    return out, len(rs), len(allr)

def labels(d, tag):
    """L → fact label from LABELS-<tag>.tsv (tools/fact-labels.py), run first where it is missing."""
    p = os.path.join(d, f"LABELS-{tag}.tsv")
    if not os.path.exists(p):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fact_labels", os.path.join(HERE, "fact-labels.py"))
        fl = importlib.util.module_from_spec(spec); spec.loader.exec_module(fl)
        saved, sys.argv = sys.argv, ["fact-labels.py", os.path.basename(d), tag]
        try: fl.main()
        finally: sys.argv = saved
    return {int(r["L"][1:]): r["label"] for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t")}

def short(n, line, label=None, u=None):
    """Proposal 2: the line in the short form, headed «L‹n› (U‹n›):»."""
    f = FL.fields(line)
    if f is None or not f["kind"]: return f"L{n}" + (f" (U{u})" if u else "") + f": {line}"
    loc = label if label and not label.endswith("?") else f["locator"]
    voice = re.sub(r"\s*⟵ `[^`]*`\s*$", "", f["voice"]).strip()
    for full, code in VOICE_CODES: voice = voice.replace(full, code)
    date = (f"({f['qual']}) " if f["qual"] else "") + (f["date"] or "—")
    return f"L{n}" + (f" (U{u})" if u else "") + ": " + " · ".join([date, f["kind"], f["fact"], f["anchor"], loc] + ([voice] if voice else []))

_SIG = None
def siglum_of(label):
    """The siglum a label begins with, and its entry; None for a line with no label."""
    global _SIG
    if _SIG is None: _SIG = sorted(((r["siglum"], r.get("entry", "")) for r in sigla.rows(sigla.SIGLA) if r.get("status") == "signed"), key=lambda x: -len(x[0]))
    if not label or label.endswith("?"): return None
    return next(((s, e) for s, e in _SIG if label.startswith(s)), None)

def sources(nums, line_of, label):
    """Proposal 4: the reader's lines counted by work, by siglum with its entry; a line with no label by its item key.
    line_of(n): the frozen profile's line n."""
    from collections import Counter
    c, entry = Counter(), {}
    for n in nums:
        se = siglum_of(label.get(n))
        if se: c[se[0]] += 1; entry[se[0]] = se[1]; continue
        lm = re.search(r" · ([A-Za-z0-9._-]+), (?:PDF|¶|l\.) ?\d", line_of(n))
        k = lm.group(1) if lm else (re.search(r"⟵ `([^`]+)`", line_of(n)) or [None, "?"])[1]
        c[k] += 1
    return "\n" + "\n".join(f"- **{k}**" + (f", {entry[k]}" if entry.get(k) else " (sen siglo)") + f": {v} linioj" for k, v in c.most_common())

def for_reader(path):
    """Proposal 5: [path] where the file comes back whole from one Read; else the reader's parts, <stem>-read-<i>.md."""
    t = open(path, encoding="utf-8").read()
    if len(t) <= CUT: return [path]
    ls, parts, cur = t.split("\n"), [], []
    for l in ls:
        if cur and sum(len(x) + 1 for x in cur) + len(l) + 1 > CUT - 400: parts.append(cur); cur = []
        cur.append(l)
    if cur: parts.append(cur)
    stem = path[:-3]
    names = [f"{stem}-read-{i}.md" for i in range(1, len(parts) + 1)]
    for i, (p, ls_) in enumerate(zip(names, parts)):
        nxt = f" Daŭrigo: `{os.path.basename(names[i + 1])}`." if i + 1 < len(names) else " Ĉi tiu estas la lasta parto."
        head = f"`[tools/smelt_inputs.py: {os.path.basename(path)}, parto {i + 1} el {len(names)}, tranĉita ĉe linio, por ke unu Read redonu ĝin tutan.{nxt}]`\n\n"
        open(p, "w", encoding="utf-8").write(head + "\n".join(ls_) + "\n")
    return names

def paths(ps):
    """Several files in one backticked slot of a template («`{profilo}`»): «a`, `b`, `c»."""
    return "`, `".join(ps)

def check_register(stem, tag):
    """Proposal 1's check, no tokens: for each S4 part of a filed run, the register rows whose main form (or name) the
    part's return uses, and whether the cut register on the part's inputs keeps them."""
    d = os.path.join(G, "smelt", stem)
    ks = sorted(m.group(1) for f in os.listdir(d) for m in [re.fullmatch(rf"S4-LINES-{re.escape(tag)}-p(\w+)\.md", f)] if m)
    allr = rows()
    for k in ks:
        rd = lambda f: open(os.path.join(d, f), encoding="utf-8").read() if os.path.exists(os.path.join(d, f)) else ""
        text = rd(f"S4-LINES-{tag}-p{k}.md") + rd(f"S3-RETURN-{tag}-p{k}.md")
        ret = _text_words(rd(f"S4-RETURN-{tag}-p{k}.md"))
        # used: the main form or the name, before any bracket, every telling word in the return
        used = [r for r in allr if any(s and s <= ret for s in map(_sig, [c.split("(")[0] for c in (r.get("main_form"), r.get("name")) if c]))]
        keep = {(r.get("name"), r.get("same_as")) for r in kept(text)}
        miss = [r for r in used if (r.get("name"), r.get("same_as")) not in keep]
        print(f"part {k}: {len(keep)} rows kept of {len(allr)}; the return uses {len(used)}; missed {len(miss)}"
              + (": " + "; ".join((r.get("main_form") or r.get("name"))[:60] for r in miss) if miss else ""))

def check_proposals(stem, tag):
    """Proposal 1's other half (2026-11-10): the register proposals of every S4 return of a run (its section 4, the bold name
    of each «- **name** → …» line) against the register's rows, by the same telling words as kept(): a proposal whose name
    or target a row already holds is printed, for Ezri to strike; no tokens."""
    d = os.path.join(G, "smelt", stem)
    allr = rows()
    forms = [(r, [s for fld in ("name", "same_as", "main_form") for s in map(_sig, _cores(r.get(fld))) if s]) for r in allr]
    n = hit = 0
    for f in sorted(os.listdir(d)):
        if not re.fullmatch(rf"S4-RETURN-{re.escape(tag)}(-p\w+)?\.md", f): continue
        t = open(os.path.join(d, f), encoding="utf-8").read()
        m = re.search(r"^\**Proponoj por la registro\**.*?(?=^## |^\*\*[A-ZĈĜĤĴŜŬ]|\Z)", t, re.M | re.S)
        if not m: continue
        for l in m.group(0).split("\n")[1:]:
            pm = re.match(r"^- \*\*(.+?)\*\*\s*(?:→|=|:)\s*(.*)", l)
            if not pm or re.match(r"L\d", pm.group(1)): continue
            n += 1
            tw = _text_words(pm.group(1))
            have = [r for r, ss in forms if any(s <= tw for s in ss)]
            if have:
                hit += 1
                print(f"{f}: «{pm.group(1)[:60]}» may exist: " + "; ".join((r.get("name") or "")[:40] + " → " + (r.get("main_form") or r.get("same_as") or "")[:40] for r in have[:3]))
    print(f"{stem} {tag}: {n} proposals, {hit} that may exist already")

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "check-proposals": check_proposals(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "check-register": check_register(sys.argv[2], sys.argv[3])
    else: sys.exit(__doc__)
