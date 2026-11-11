#!/usr/bin/env python3
r"""smelt-compress.py — the episodes' mechanical part by tool: a person's chronology compressed, and the reader's share
left for a reader (step 2 of geniza/ocr/method/SMELT-EFFICIENCY-PROPOSAL-2026-10-29.md, points 1–4; approved by the editor, 2026-10-30). No tokens.

    python3 tools/smelt-compress.py <stem> <tag> [--target 150] [--span-gap 3] [--skip-unkinded] [--dry-run]

Run after `smelt-s2-prep.py <tag> <stem>=<NAME> --episodes`, on its PROFILE-FROZEN-<tag>.md and S3-INPUT-<tag>.md: the
tool's G and U keep their numbers, every line its L. Writes, create-only, in smelt/<stem>/:
  - S3-COMPRESSED-<tag>.md, the chronology, in periods:
      G…  an agreeing group's statement (point 1): its best line's fact (the most precise date; a source of the fact's
          own time first), its other dates, its places counted (one item and page once; a ⟦kopio el …⟧ copy and a
          «derivita ↤» line not counted, non vidimus);
      S…  a span (point 2): the groups and single lines of one office, profession or residence (ofico, profesio, loĝado;
          the object to its second comma, the act «elektita», «reelektita» left out) over successive years, cut where
          the attested years are more than --span-gap apart; each end with its lines;
      R…  a routine kind summarised (point 3): aperoj, registro, anonco, one line per object, its years and lines;
      U…  a single line, as S3-SINGLES states it;
      → … a pointer to an item of the reader's share, at its date, so the chronology misses nothing;
    the periods (point 4) cut between years at about --target lines, earlier at a gap of five years or more without a
    line or at a turn (a joining or leaving of Esperanto, Ido, Volapük), once the period has a third of --target;
    the items with no usable year last, «sen uzebla dato»;
  - S3-INPUT-<tag>-reader.md, «the reader's share» (called «the residue» until 2026-10-30; the editor), in S3-INPUT's form: the groups and single lines of judgements (juĝo,
    interpreto, historiografio), the relational kinds (renkonto, konflikto, interkonsento, influo, rilato) and «alia»;
    a group holding a refuted claim; a group whose dates differ with one «ĉirkaŭ» (proksimumas or not); the candidates
    (K); the nominations outside the span kinds (N); the lines in no group of the tool and the edition notes.
  - with --brief, S3-BRIEF-<tag>-reader.md: S3-BRIEF-<tag>.md (smelt-s2-prep.py) with the reader's share as its input,
    the compressed chronology in place of the singles, and a paragraph telling the reader what the tool has written
    (to read only, cited by its numbers); as smelt-periods.py derives its parts' briefs. For the pilot (step 3).
The classes are those of tools/smelt-count.py (step 1).
Ezri, 2026-10-30."""
import argparse, importlib.util, itertools, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import date_vocab
import factline as FL
import smelt_pieces   # the readers write their reports in pieces (the pilot, 2026-10-30: three cut off at their output limit)
import smelt_inputs as SI   # Fable's proposals 1, 2, 4, 5: the short form, the cut register, files whole in one Read (2026-10-30)
G_ = os.path.join(os.path.dirname(HERE), "published", "heterophony-resources", "geniza")

def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = saved
    return m
SP = _load("sp", "smelt-periods.py")      # line_year(), source_year(): placing a line, and its source's year

JUDGE = {"juĝo", "interpreto", "historiografio"}
REL = {"renkonto", "konflikto", "interkonsento", "influo", "rilato"}
SPAN = {"ofico", "profesio", "loĝado"}
ROUTINE = {"aperoj", "registro", "anonco"}
TURN = re.compile(r"^\{(?:aliĝo|foriro):\s*(?:Esperanto|Ido|Volapük)\b", re.I)
ITEM = re.compile(r"^- \*\*([GUKN])(\d+)\*\* · (.*?): (.*)$")
REF = re.compile(r"\bL(\d+)\b")


def parse_input(path):
    """S3-INPUT -> (items {(letter, n): (kinds text, [L], line)}, loose [L], editions [L])."""
    items, loose, ed, sec = {}, [], [], ""
    for l in open(path, encoding="utf-8").read().split("\n"):
        if l.startswith("## "): sec = l; continue
        m = ITEM.match(l)
        if m: items[(m.group(1), int(m.group(2)))] = (m.group(3), [int(x) for x in REF.findall(m.group(4))], l)
        elif sec.startswith("## The lines in no group"): loose += [int(x) for x in REF.findall(l)]
        elif sec.startswith("## The edition notes"): ed += [int(x) for x in REF.findall(l)]
    return items, loose, ed


def date_of(f):
    d = (f or {}).get("date", "").strip()
    if not d or "sen dato" in d or "ĝenerala" in d: return None
    try: x = date_vocab.parse(d)
    except ValueError: return None
    return None if x.kind in ("none", "general") else x


def width(d):
    import datetime
    if not d or not d.lo or not d.hi: return 10 ** 8
    return (datetime.date.fromisoformat(d.hi) - datetime.date.fromisoformat(d.lo)).days


PLACE = re.compile(r"^([\w.-]+), (?:PDF|¶|p\.|pĝ|l\.)\s*([^\s,;)]+)")
def place(f):
    """(item, page) of a line, None for a copy or a derived line (they are no witness)."""
    o = FL.ours(" · ".join((f["kind"], f["fact"], f["voice"])))
    if "⟦kopio el" in f["fact"] + f["voice"] or "derivita" in o: return None
    m = PLACE.match(f["locator"])
    return (m.group(1), m.group(2)) if m else (f["locator"][:60], "")


def span_key(kind_field, kind):
    """{ofico: prezidanto, Grupo X, elektita} -> «ofico / prezidanto, Grupo X»: the act left out. The part of the given
    kind, the main one or a second («+ofico: …»): a line can sit in S3-INPUT under its second kind."""
    for part in kind_field.strip("{}").split(";"):
        k, _, obj = part.strip().lstrip("+").partition(":")
        if k.strip() == kind:
            parts = [p.strip() for p in obj.split(",")]
            return f"{kind} / {', '.join(parts[:2]).strip()}"
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stem"); ap.add_argument("tag")
    ap.add_argument("--target", type=int, default=150); ap.add_argument("--span-gap", type=int, default=3)
    ap.add_argument("--skip-unkinded", action="store_true",
                    help="leave out the lines without a kind (formats 2 and 3, the September roster runs' hand files), counted (the editor, 2026-10-30)")
    ap.add_argument("--brief", action="store_true", help="also write S3-BRIEF-<tag>-reader.md from S3-BRIEF-<tag>.md")
    ap.add_argument("--split-s4", action="store_true", help="after the S3 return is filed: cut it into the period parts smelt-periods.py --s4 reads")
    ap.add_argument("--s4-months", default="", help="with --split-s4: Y:N,… the part of year Y alone cut into N pieces by month (2026-11-10)")
    ap.add_argument("--s4-target", type=int, default=300, help="with --split-s4: about this many profile lines a part")
    ap.add_argument("--s3-parts", action="store_true", help="after the plain run: the reader's share in period parts, one reader each (a share too large for one reader)")
    ap.add_argument("--s3-target", type=int, default=150,
                    help="with --s3-parts: a part closes once its share reaches this many lines, so it ends above it by up to one period (200 until Bourlet: parts of 265 and 273 lines cut off, 239 not)")
    ap.add_argument("--into", type=int, default=2, help="with --resplit on a one-year part: the number of pieces, cut between months (2026-11-10)")
    ap.add_argument("--resplit", metavar="K", help="with --s3-parts: part K re-run in two (its reader cut off), the other parts standing; remove its four files first")
    ap.add_argument("--s3-general", action="store_true", help="after the period parts' returns: their episode titles into part g's brief")
    ap.add_argument("--s3-join", action="store_true", help="after part g's return: the parts' returns joined as S3-RETURN-<tag>.md")
    ap.add_argument("--retag", metavar="OLD", help="a before-and-after test: the frozen profile and smelt-s2-prep.py's S3 files of tag OLD copied as this tag's, the tag in them changed, so the tool's groups and U are the same")
    ap.add_argument("--retag-returns", action="store_true", help="with --retag: the S3 returns and the S4 parts' S3 files too (a test of S4 alone)")
    ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    d = os.path.join(G_, "smelt", a.stem)
    if a.retag: return retag(d, a)
    if a.split_s4: return split_s4(d, a)
    if a.s3_parts: return s3_parts(d, a)
    if a.s3_general: return s3_general(d, a)
    if a.s3_join: return s3_join(d, a)
    outc, outr = os.path.join(d, f"S3-COMPRESSED-{a.tag}.md"), os.path.join(d, f"S3-INPUT-{a.tag}-reader.md")
    outb = os.path.join(d, f"S3-BRIEF-{a.tag}-reader.md")
    # with --brief, an existing compression and share are kept if the run would write the same text (put() below): the
    # brief after a plain run (Devjatnin 2026-11-10, a share of 234 lines, under the 240 of --s3-parts)
    for f in ((outc, outr) if not a.brief else ()) + ((outb,) if a.brief else ()):
        if os.path.exists(f) and not a.dry_run: sys.exit(f"smelt-compress: {f} exists; not overwriting it")

    def put(f, text):
        if os.path.exists(f):
            if open(f, encoding="utf-8").read() != text: sys.exit(f"smelt-compress: {f} exists and differs; not overwriting it")
            print(f"(kept, the same text: {os.path.basename(f)})"); return
        open(f, "x", encoding="utf-8").write(text)
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md"), encoding="utf-8").read().split("\n")
    F = {i + 1: FL.fields(l) for i, l in enumerate(prof) if l.startswith("- $$$")}
    Y = {n: SP.line_year(prof[n - 1]) for n in F}
    items, loose, ed = parse_input(os.path.join(d, f"S3-INPUT-{a.tag}.md"))
    skipped = []
    if a.skip_unkinded:
        skipped = [n for n in loose if not (F.get(n) or {}).get("kind")]
        loose = [n for n in loose if n not in set(skipped)]
        for n in skipped: F.pop(n, None)
    refuted = lambda n: "(refutita aserto)" in FL.ours(prof[n - 1])

    def approx(ns):
        ds = [date_of(F.get(n)) for n in ns]; ds = [x for x in ds if x]
        return len({x.edtf for x in ds}) > 1 and any(x.approx for x in ds)

    # the residue, and the rest by class
    residue, span_items, routine_items, statements, singles, unfound = [], defaultdict(list), defaultdict(list), [], [], []
    for (L_, n), (kinds, ns, line) in sorted(items.items(), key=lambda x: ("GUKN".index(x[0][0]), x[0][1])):
        k = kinds.split(" / ")[0].strip()
        if not ns: unfound.append(line); continue      # «L?»: smelt-s2-prep found no profile line for it
        if L_ == "K": residue.append(((L_, n), "candidate")); continue
        if L_ == "N":
            if k not in SPAN | ROUTINE: residue.append(((L_, n), "nomination"))
            continue
        why = ("judgement" if k in JUDGE else "relational" if k in REL else "alia" if k == "alia"
               else "refuted" if any(refuted(x) for x in ns) else "approx" if L_ == "G" and approx(ns) else None)
        if why: residue.append(((L_, n), why)); continue
        if k in SPAN: span_items[(span_key(F[ns[0]]["kind"], k) if F.get(ns[0]) else None) or kinds].append((L_, n))
        elif k in ROUTINE: routine_items[kinds].append((L_, n))
        elif L_ == "G": statements.append((L_, n))
        else: singles.append((L_, n))

    def best(ns):
        """The statement's line: the most precise date, then a source of the fact's own time, then the first."""
        def key(n):
            dt, sy, y = date_of(F.get(n)), SP.source_year(prof[n - 1]), Y.get(n)
            return (width(dt), 0 if (sy and y and abs(sy - y) <= 1) else 1, n)
        return min(ns, key=key)

    def places(ns):
        return len({p for p in (place(F[n]) for n in ns if F.get(n)) if p})

    entries = []           # (year or None, text, lines it covers)
    sk = 0
    for key, its in sorted(span_items.items()):
        by_year = defaultdict(list)
        undated = []
        seen_n = set()     # a line in two items of one span (a group and a single under its second kind) counts once
        for it in its:
            for n in items[it][1]:
                if n in seen_n: continue
                seen_n.add(n); (by_year[Y[n]] if Y.get(n) else undated).append(n)
        years = sorted(by_year)
        runs, cur = [], []
        for y in years:
            if cur and y - cur[-1] > a.span_gap: runs.append(cur); cur = []
            cur.append(y)
        if cur: runs.append(cur)
        if not runs: runs = [[]]
        for i, run in enumerate(runs):
            ns = [n for y in run for n in by_year[y]] + (undated if i == 0 else [])
            ids = sorted({f"{x[0]}{x[1]}" for x in its if set(items[x][1]) & set(ns)}, key=lambda s: (s[0], int(s[1:])))
            # a span of one item and one year is no span (Beauchemin, the first run: 101 «spans», most one office line):
            # it stays the statement or single line it is
            if len(ids) == 1 and len(run) <= 1:
                it = next(x for x in its if f"{x[0]}{x[1]}" == ids[0])
                (statements if it[0] == "G" else singles).append(it); continue
            sk += 1
            f0 = F[best([n for n in by_year[run[0]]] if run else ns)]
            when = (f"{run[0]}–{run[-1]}" if run and run[0] != run[-1] else str(run[0]) if run else "sen dato")
            txt = (f"- **S{sk}** · {when} · {key}" + (f" (atestita: {', '.join(map(str, run))})" if len(run) > 1 else "")
                   + f" · unue: {f0['fact']} — {len(ns)} linioj, {places(ns)} lokoj ({', '.join(ids)}): {', '.join(f'L{n}' for n in ns)}")
            entries.append((run[0] if run else None, txt, ns))
    for it in statements:      # after the spans, which hand back the items that make no span
        kinds, ns, _ = items[it]
        b = best(ns); f = F[b]
        others = sorted({F[n]["date"] for n in ns if F.get(n) and F[n]["date"] != f["date"]})
        txt = (f"- **G{it[1]}** · {f['date']} · {f['kind']} · {f['fact']}" + (f" (ankaŭ: {', '.join(others)})" if others else "")
               + f" — {len(ns)} linioj, {places(ns)} lokoj: {', '.join(f'L{n}' for n in ns)}")
        entries.append((min((Y[n] for n in ns if Y.get(n)), default=None), txt, ns))
    for rk, (key, its) in enumerate(sorted(routine_items.items()), 1):
        ns = [n for it in its for n in items[it][1]]
        ys = sorted({Y[n] for n in ns if Y.get(n)})
        f0 = F[best(ns)]
        txt = (f"- **R{rk}** · {', '.join(map(str, ys)) or 'sen dato'} · {key} · ekz.: {f0['fact']} — {len(ns)} linioj, "
               f"{places(ns)} lokoj: {', '.join(f'L{n}' for n in ns)}")
        entries.append((ys[0] if ys else None, txt, ns))
    # a single under a line's second kind whose line a group already states (Guillaume, the pilot: G2 and U30 both L7):
    # not repeated
    in_groups = {n for it in statements for n in items[it][1]}
    for it in singles:
        ns = items[it][1]
        if ns[0] in in_groups: continue
        f = F.get(ns[0]) or {"date": "?", "kind": "", "fact": prof[ns[0] - 1][:120]}
        entries.append((Y.get(ns[0]), f"- **U{it[1]}** · {f['date']} · {f['kind']} · {f['fact']} — L{ns[0]}", ns))
    for it, why in residue:
        ns = items[it][1]
        entries.append((min((Y[n] for n in ns if Y.get(n)), default=None),
                        f"- → **{it[0]}{it[1]}** ({why}) · {items[it][0]}: al la leganto, {', '.join(f'L{n}' for n in ns)}", ns))
    rl = sorted(set(loose) | set(ed))
    for n in rl:
        f = F.get(n) or {"date": "?"}
        entries.append((Y.get(n), f"- → **L{n}** (sen grupo) · {f['date']}: al la leganto", [n]))

    # periods (point 4)
    dated = sorted((e for e in entries if e[0] is not None), key=lambda e: (e[0], e[1]))
    turn_years = {Y[n] for n in F if Y.get(n) and TURN.match(F[n]["kind"] or "")}
    periods, cur, cnt, last = [], [], 0, None
    for e in dated:
        y = e[0]
        # a gap or a turn cuts only a period of a third of --target (Beauchemin, the first run: 16 periods for 555 lines,
        # «1869–1869 (1 linioj)»)
        if cur and y != last and (cnt >= a.target or ((y - last >= 5 or y in turn_years) and cnt >= a.target // 3)):
            periods.append(cur); cur, cnt = [], 0
        cur.append(e); cnt += len(e[2]); last = y
    if cur: periods.append(cur)
    undated_e = [e for e in entries if e[0] is None]

    nlines = len(F)
    res_lines = sorted({n for it, _ in residue for n in items[it][1]} | set(rl))
    covered = {n for e in entries for n in e[2]}
    stats = (f"{nlines} lines in the profile; the chronology {len(entries)} items ({len(statements)} statements, {sk} spans, "
             f"{len(routine_items)} routine summaries, {len(singles)} single lines, {len(residue) + len(rl)} pointers to the reader's share); "
             f"the reader's share {len(res_lines)} lines ({len(res_lines) / max(nlines, 1):.0%}); {nlines - len(covered)} lines in no item"
             + (f"; {len(unfound)} items of S3-INPUT without a profile line («L?»), left out" if unfound else "")
             + (f"; {len(skipped)} lines without a kind left out (--skip-unkinded)" if skipped else ""))
    print(f"{a.stem} {a.tag}: {stats}; {len(periods)} periods" + (" (dry run)" if a.dry_run else ""))
    if a.dry_run: return
    out = [f"# S3, compressed by tool: {a.stem} ({a.tag})", "",
           f"`[tools/smelt-compress.py from S3-INPUT-{a.tag}.md and PROFILE-FROZEN-{a.tag}.md: {stats}. G = an agreeing group's "
           f"statement, S = a span, R = a routine kind, U = a single line, → = an item for the reader, in S3-INPUT-{a.tag}-reader.md. "
           f"«lokoj»: places counted, a copy and a derived line not. L = the line's number in PROFILE-FROZEN-{a.tag}.md.]`"]
    for p in periods:
        out += ["", f"## {p[0][0]}–{p[-1][0]} ({sum(len(e[2]) for e in p)} linioj)", ""] + [e[1] for e in p]
    if undated_e:
        out += ["", f"## Sen uzebla dato ({sum(len(e[2]) for e in undated_e)} linioj)", ""] + [e[1] for e in sorted(undated_e, key=lambda e: e[1])]
    put(outc, "\n".join(out) + "\n")
    # the reader's share, in S3-INPUT's form, so that the S3 brief can name it in place of the whole input
    R = [f"# S3: the reader's share of {a.stem} ({a.tag})", "",
         f"`[tools/smelt-compress.py: the items the tool does not state, {len(res_lines)} lines of {nlines}; the rest is stated in "
         f"S3-COMPRESSED-{a.tag}.md, to read only. L = the line's number in PROFILE-FROZEN-{a.tag}.md.]`"]
    # THE GROUPS AND SINGLE LINES BY THEIR POINTERS ONLY (2026-11-10, Fable's proposal 7, the editor's ruling): the
    # chronology's «→» line gives each with its kind, object and every L; the candidates and nominations stay, their
    # structure (the sides, the group against the line) being only here
    R += ["", "*La grupoj G kaj la unuopaj linioj U de via parto: en la kronologio, ĉiu kun «→», sia speco, sia objekto kaj siaj L.*"]
    for title, letters in (("## The candidates (relational lines that may be one occasion)", "K"), ("## The nominations (possible date errors)", "N")):
        R += ["", title, ""] + [f"{items[it][2]}  ⟦{why}⟧" for it, why in residue if it[0] == letters]
    R += ["", f"## The lines in no group of the tool ({len(loose)}: «alia», «samnomo», a date it cannot read, or no kind; group them yourself)", "",
          ", ".join(f"L{n}" for n in loose) or "(none)"]
    if ed: R += ["", f"## The edition notes ({len(ed)})", "", ", ".join(f"L{n}" for n in ed)]
    put(outr, "\n".join(R) + "\n")
    print(f"→ {os.path.relpath(outc, G_)}, {os.path.relpath(outr, G_)}")
    if not a.brief: return
    # THE READER'S BRIEF (step 3, the pilot; the editor, 2026-10-30): the S3
    # brief smelt-s2-prep.py wrote, its input the reader's share, its singles the compressed chronology, and one
    # paragraph, as smelt-periods.py derives its parts' briefs
    bp = os.path.join(d, f"S3-BRIEF-{a.tag}.md"); brief = open(bp, encoding="utf-8").read()
    # every file the brief names whole in one Read (Fable's proposal 5, tools/smelt_inputs.py): a long one in the reader's parts
    chron = SI.paths(SI.for_reader(outc))
    for old in (f"S3-INPUT-{a.tag}.md", f"S3-SINGLES-{a.tag}.md"):
        if os.path.join(d, old) not in brief: sys.exit(f"refusing: S3-BRIEF-{a.tag}.md does not name {old}")
    b = brief.replace(os.path.join(d, f"S3-INPUT-{a.tag}.md"), SI.paths(SI.for_reader(outr))).replace(os.path.join(d, f"S3-SINGLES-{a.tag}.md"), chron)
    # THE PROFILE AS AN EXCERPT (the pilot, Midthus: the reader read the whole frozen profile besides its share and the
    # chronology, 132,529 tokens for 122 lines, more a line than the old route): only the lines of the reader's share,
    # each headed by its L, as smelt-periods.py gives its S4 parts; the chronology states the others. Since 2026-10-30 in
    # the short form, with its sigla, and the register cut to the share's and the chronology's names (Fable's proposals
    # 1, 2, 4)
    fz = os.path.join(d, f"PROFILE-FROZEN-{a.tag}.md")
    ex = os.path.join(d, f"PROFILE-EXCERPT-{a.tag}-reader.md")
    if fz in b:
        if os.path.exists(ex): sys.exit(f"refusing: {os.path.basename(ex)} exists")
        ex_lines = excerpt(d, a.tag, prof, res_lines)
        open(ex, "x", encoding="utf-8").write(
            f"# The lines of the reader's share of {a.stem} ({a.tag})\n\n`[tools/smelt-compress.py --brief: {len(res_lines)} of {nlines} "
            f"lines of PROFILE-FROZEN-{a.tag}.md, each headed by its L, in the short form (tools/smelt_inputs.py), the sigla first; "
            f"the others are stated in S3-COMPRESSED-{a.tag}.md.]`\n\n" + ex_lines + "\n")
        b = b.replace(fz, SI.paths(SI.for_reader(ex)))
        b = short_brief(b, d, a.tag, ex_lines + "\n" + open(outc, encoding="utf-8").read(), f"NAMES-REGISTER-{a.tag}-reader.tsv")
    para = reader_para(chron, "la tutan vivon")
    b = b.replace("\nFinu la mesaĝon per la linio", para + "\nFinu la mesaĝon per la linio", 1)
    if para not in b: sys.exit(f"refusing: S3-BRIEF-{a.tag}.md has no closing line «Finu la mesaĝon per la linio»")
    b = b.replace("Ĝi donas, kun L-numeroj: ", "Ĝi donas, kun L-numeroj (la grupoj G kaj la unuopaj linioj U de via parto ne staras en ĝi, sed en la kronologio, ĉiu kun «→», sia speco, sia objekto kaj siaj L): ", 1)
    b = smelt_pieces.add(b, os.path.join(d, f"S3-RETURN-{a.tag}.md"))
    open(outb, "x", encoding="utf-8").write(b)
    print(f"→ {os.path.relpath(outb, G_)}")


def reader_para(outc, scope):
    """The paragraph that tells the share's reader what the tool wrote (the brief of --brief and of --s3-parts)."""
    return ("\n\n**Via enigo estas nur la parto por la legilo** (la propono `ocr/method/SMELT-EFFICIENCY-PROPOSAL-2026-10-29.md`, "
            "la piloto). La ilo `smelt-compress.py` jam skribis la ceteron de la profilo en la kronologio "
            f"`{outc}`, laŭ dato kaj en periodoj: la grupojn, kies linioj konsentas (G…, kun la plej preciza linio kiel aserto), "
            "la daŭrojn de ofico, profesio kaj loĝado (S…), la rutinajn specojn resumitajn (R…: aperoj, registroj, anoncoj) kaj "
            "la unuopajn liniojn (U…). En ĝi «→» montras, ĉe ĝia dato, ĉiun eron de via enigo. **La kronologion legu nur por "
            "legi:** ne reskribu ĝiajn erojn kaj ne metu ilin en novajn grupojn; citu ilin per iliaj numeroj (G…, S…, R…, U…) "
            f"en viaj epizodoj, kiel la U-ojn antaŭe. Viaj epizodoj kovras {scope}, el viaj grupoj kaj el la eroj de la "
            "kronologio. **La profilo estas eltiraĵo:** nur la linioj de via parto, ĉiu kun sia L-numero antaŭe; la aliajn "
            "liniojn la kronologio jam diras, kun iliaj L-numeroj, kaj vi ne bezonas legi ilin. La linioj sen speco (formatoj 2 "
            "kaj 3) estas forlasitaj en ĉi tiu provo.\n")


def retag(d, a):
    """A before-and-after test on the same inputs (the editor, 2026-10-30): PROFILE-FROZEN, S3-INPUT, S3-SINGLES and S3-BRIEF of tag --retag copied as tag a.tag,
    every «OLD» in them written as the new tag, create-only; the corpus may have changed since, so smelt-s2-prep.py is
    not run again. Then the plain run of this tool on the new tag."""
    fs = [f"PROFILE-FROZEN-{{}}.md", f"S3-INPUT-{{}}.md", f"S3-SINGLES-{{}}.md", f"S3-BRIEF-{{}}.md"]
    if a.retag_returns:   # the S4 test on the same episodes: the S3 returns and their parts too, so only S4's inputs change
        fs += [f"S3-COMPRESSED-{{}}.md", f"S3-RETURN-{{}}.md"] + [f.replace(a.retag, "{}") for f in sorted(os.listdir(d))
               if re.fullmatch(rf"S3-(?:INPUT|RETURN)-{re.escape(a.retag)}-p(?:\d+|g)\.md", f)]
    for f in fs:
        src, dst = os.path.join(d, f.format(a.retag)), os.path.join(d, f.format(a.tag))
        if not os.path.exists(src): sys.exit(f"refusing: {os.path.basename(src)} is missing")
        if os.path.exists(dst): sys.exit(f"refusing: {os.path.basename(dst)} exists")
    for f in fs:
        t = open(os.path.join(d, f.format(a.retag)), encoding="utf-8").read()
        open(os.path.join(d, f.format(a.tag)), "x", encoding="utf-8").write(t.replace(a.retag, a.tag))
        print(f"{f.format(a.tag)}: from {f.format(a.retag)}, {t.count(a.retag)} mentions of the tag changed")


def excerpt(d, tag, prof, nums):
    """The share's lines in the short form, under the sigla they cite (Fable's proposals 2 and 4, tools/smelt_inputs.py)."""
    label = SI.labels(d, tag)
    return ("## La fontoj de ĉi tiuj linioj, laŭ siglo\n" + SI.sources(nums, lambda n: prof[n - 1], label) + "\n\n## La linioj\n\n"
            + "\n".join(SI.short(n, prof[n - 1], label.get(n)) for n in nums))


def short_brief(b, d, tag, text, regname):
    """An S3 reader's brief told of the short form, and given the register cut to the names of its text (Fable's
    proposals 1 and 2; the editor, 2026-10-30)."""
    if SI.S3_FULL not in b: sys.exit("refusing: the S3 brief's line-form sentence has changed; smelt_inputs.S3_FULL")
    full = os.path.join(G_, "profiles", "NAMES-REGISTER.tsv")
    if full not in b: sys.exit("refusing: the S3 brief does not name profiles/NAMES-REGISTER.tsv")
    rp, nk, na = SI.register(text, os.path.join(d, regname))
    print(f"  {regname}: {nk} of {na} rows")
    return b.replace(SI.S3_FULL, SI.SHORT_S3, 1).replace(full, rp)


# S3 IN PERIODS ON THE COMPRESSED ROUTE (the pilot, 2026-10-30: Bourlet's share, 781 lines, too large for one reader; the
# editor). After the plain run (S3-COMPRESSED and the reader's share written): the chronology's periods
# joined to about --s3-target lines of the share a part; each part's reader gets the share's items whose pointer «→» falls
# in its periods, only those periods of the chronology, and an excerpt of its share's lines; the items with no usable date
# go to a last reader, part g, which is given the period parts' episode titles (--s3-general) so that it writes «vidu E…»
# and not the same episode twice; --s3-join joins the returns as S3-RETURN-<tag>.md, as smelt-periods.py --join does, for
# --split-s4. Writes, create-only: S3-INPUT-<tag>-reader-p<k>.md, S3-COMPRESSED-<tag>-p<k>.md,
# PROFILE-EXCERPT-<tag>-reader-p<k>.md, S3-BRIEF-<tag>-reader-p<k>.md; the returns are S3-RETURN-<tag>-reader-p<k>.md (not
# -p<k>, which --split-s4 writes). The episodes are numbered by part as smelt-periods.py numbers them: E101 … for part 1,
# E901 … for g; new groups G1001 …, G9001 ….
PTR = re.compile(r"^- → \*\*(?:([GUKN])(\d+)|L(\d+))\*\*(?: \(([^)]*)\))?")
GEN_MARK = "(skribitaj de `--s3-general`, post la revenoj de la periodoj)\n"
MONTHS = {}   # a one-year part cut between months (--resplit): its key → which months it reads

def s3_parts(d, a):
    rd = lambda f: open(os.path.join(d, f), encoding="utf-8").read()
    prof = rd(f"PROFILE-FROZEN-{a.tag}.md").split("\n")
    items, loose, ed = parse_input(os.path.join(d, f"S3-INPUT-{a.tag}.md"))
    if max((n for (L_, n) in items if L_ == "G"), default=0) > 1000:
        sys.exit("refusing: the tool's groups run past G1000, into the parts' numbers for new groups")
    brief = rd(f"S3-BRIEF-{a.tag}.md")
    # the chronology's periods, each with its heading, its lines and the share's lines its pointers carry
    per, cur = [], None
    for l in rd(f"S3-COMPRESSED-{a.tag}.md").split("\n"):
        m = re.match(r"^## (\d{4})–(\d{4}) \(", l)
        if m: cur = [int(m.group(1)), int(m.group(2)), [l, ""], []]; per.append(cur); continue
        if l.startswith("## Sen uzebla dato"): cur = ["g", None, [l, ""], []]; per.append(cur); continue
        if cur is None or not l.startswith("- "): continue
        cur[2].append(l)
        m = PTR.match(l)
        if m: cur[3].append(((m.group(1), int(m.group(2))), m.group(4) or "") if m.group(1) else (("L", int(m.group(3))), ""))
    share = lambda ptrs: sorted({n for it, _ in ptrs for n in ([it[1]] if it[0] == "L" else items[it][1])})
    def joined(ps):
        acc = [ps[0][0], ps[-1][1], [], [], list(ps)]
        for p in ps: acc[2] += p[2] + [""]; acc[3] += p[3]
        return acc
    groups, cur_g = [], None
    for p in per:
        if p[0] == "g": continue
        if cur_g is None or len(share([x for q in cur_g for x in q[3]])) >= a.s3_target: cur_g = []; groups.append(cur_g)
        cur_g.append(p)
    # a last part of under a third of the target joins the one before (Bourlet, the first dry run: 1914–2005, 29 lines)
    if len(groups) > 1 and len(share([x for q in groups[-1] for x in q[3]])) < a.s3_target // 3:
        # the pop first, then the join (2026-11-10, Schneeberger: «groups[-2] += groups.pop()» read the index before the
        # pop and wrote after it, so the joined part replaced the first: parts 1 and 2 both 1909–2026, 1875–1908 lost)
        last = groups.pop(); groups[-1] += last
    parts = [joined(ps) for ps in groups]
    g = next((p for p in per if p[0] == "g"), None)
    if g: parts.append(["g", None, g[2], g[3], [g]])
    keys = [str(i) for i in range(1, len(parts) + (0 if g else 1))] + (["g"] if g else [])
    if a.resplit:
        # A PART RE-RUN IN TWO (Bourlet, part 1, 1866–1905: its reader cut off at its output limit and resumed, refused;
        # the editor's ruling of 2026-10-15): its periods cut where the share reaches half; the first half keeps the key,
        # the second takes the next free number (its episodes E{100k+1} …); the other parts stand
        if a.resplit not in keys or a.resplit == "g": sys.exit(f"refusing: no dated part {a.resplit}")
        # cut line by line, at a year boundary, not by period (Bourlet, part 3: 1911–1913 is one period of the
        # chronology, so a cut by periods gave 244 and 29 lines): each line's year from its own date, a pointer's from
        # its lines; a period cut in two keeps its lines in order under its heading, marked with the half's years
        ps = parts[keys.index(a.resplit)][4]
        Yl = {}
        def year_of(l):
            m = PTR.match(l)
            if m:
                ns = [int(m.group(3))] if m.group(3) else items[(m.group(1), int(m.group(2)))][1]
                ys_ = [y for y in (Yl.setdefault(n, SP.line_year(prof[n - 1])) for n in ns) if y]
                return min(ys_) if ys_ else None
            m = re.search(r"\*\* · (1[6-9]\d\d|20\d\d)", l)
            return int(m.group(1)) if m else None
        def ptr_of(l):
            m = PTR.match(l)
            if not m: return None
            return ((m.group(1), int(m.group(2))), m.group(4) or "") if m.group(1) else (("L", int(m.group(3))), "")
        rows = [(q[2][0], l) for q in ps for l in q[2] if l.startswith("- ")]
        ys, last = [], None
        for _, l in rows:
            y = year_of(l); last = y if y else last; ys.append(last)
        # rows before the first dated one take its year (2026-11-10, De Beaufront's 1903: leading rows with no year made a
        # boundary of «None» to 1903 and a piece with no years, IndexError)
        first = next((y for y in ys if y), None)
        ys = [y if y else first for y in ys]
        # the year boundary whose larger half is smallest (Bourlet, part 3: his death year, 1913, holds most of the
        # share, so the first boundary past half, 1914, gave 244 and 29 lines)
        pt = [ptr_of(l) for _, l in rows]
        size = lambda rs: len(share([p for p in rs if p]))
        bounds = [j for j in range(1, len(rows)) if ys[j] != ys[j - 1]]
        mlabels = None
        if bounds:
            if a.into != 2: sys.exit("refusing: --into above 2 only for a one-year part, cut between months")
            cuts = [min(bounds, key=lambda j: max(size(pt[:j]), size(pt[j:])))]
        else:
            # A ONE-YEAR PART CUT BETWEEN MONTHS (2026-11-10, De Beaufront: 1905, 1907 and 1908 parts of one year each,
            # 346, 325 and 567 lines of the share; the editor): each row's month from its own date, a pointer's from
            # its lines' earliest; the cut at the month whose larger half is smallest; the rows with the year and no
            # month go to the first half; the order within each half kept
            def month_of(l):
                m = PTR.match(l)
                if m:
                    ns = [int(m.group(3))] if m.group(3) else items[(m.group(1), int(m.group(2)))][1]
                    ms = [int(x.group(1)) for n in ns for x in [re.search(r"\*\*\d{4}-(\d\d)", prof[n - 1])] if x]
                    return min(ms) if ms else 0
                x = re.search(r"\*\* · \d{4}-(\d\d)", l)
                return int(x.group(1)) if x else 0
            mo = [month_of(l) for _, l in rows]
            cands_m = sorted({x for x in mo if x > 1})
            if not cands_m: sys.exit(f"refusing: part {a.resplit} is one year with no months to cut between")
            # --into N: N pieces, the N-1 cut months whose largest piece is smallest (De Beaufront's 1908, 567 lines)
            if a.into - 1 > len(cands_m): sys.exit(f"refusing: part {a.resplit} has too few months for {a.into} pieces")
            def split(Ms):
                edges = [0] + list(Ms) + [13]
                return [[i for i in range(len(rows)) if (mo[i] or 1) >= max(edges[j], 1) and (mo[i] or 1) < edges[j + 1]] for j in range(len(edges) - 1)]
            Ms = min(itertools.combinations(cands_m, a.into - 1), key=lambda Ms: max(size([pt[i] for i in s]) for s in split(Ms)))
            segs = split(Ms)
            order = [i for s in segs for i in s]
            rows, ys, pt = [rows[i] for i in order], [ys[i] for i in order], [pt[i] for i in order]
            cuts = list(itertools.accumulate(len(s) for s in segs))[:-1]
            edges = [1] + list(Ms) + [13]
            mlabels = [f"monatoj {edges[j]}–{edges[j + 1] - 1}" + (" kaj tiuj sen monato" if j == 0 else "") for j in range(len(segs))]
            print(f"part {a.resplit} is one year: cut before months {', '.join(map(str, Ms))}")
        def half_part(rs, yy):
            yy = [y for y in yy if y]
            chron, head = [], None
            for h, l in rs:
                if h != head: chron += ([""] if chron else []) + [f"{h} — el ĝi: {yy[0]}–{yy[-1]}", ""]; head = h
                chron.append(l)
            return [yy[0], yy[-1], chron, [p for p in (ptr_of(l) for _, l in rs) if p], []]
        b_ = [0] + cuts + [len(rows)]
        hs = [half_part(rows[b_[j]:b_[j + 1]], ys[b_[j]:b_[j + 1]]) for j in range(len(b_) - 1)]
        # the pieces keep the part's ends (the parts are cut between years)
        hs[0][0], hs[-1][1] = parts[keys.index(a.resplit)][0], parts[keys.index(a.resplit)][1]
        # the next numbers free on disk too: a second part re-run must not take the first one's new number
        on_disk = [int(m.group(1)) for f in os.listdir(d) for m in [re.fullmatch(rf"S3-BRIEF-{re.escape(a.tag)}-reader-p(\d+)\.md", f)] if m]
        top = max([int(k) for k in keys if k != "g"] + on_disk)
        news = [str(top + j) for j in range(1, len(hs))]
        for new in news:
            if os.path.exists(os.path.join(d, f"S3-RETURN-{a.tag}-reader-p{new}.md")): sys.exit(f"refusing: S3-RETURN-{a.tag}-reader-p{new}.md exists")
        parts, keys = hs, [a.resplit] + news
        if mlabels: MONTHS.update(zip(keys, mlabels))
    names = lambda k: [f"S3-INPUT-{a.tag}-reader-p{k}.md", f"S3-COMPRESSED-{a.tag}-p{k}.md",
                       f"PROFILE-EXCERPT-{a.tag}-reader-p{k}.md", f"S3-BRIEF-{a.tag}-reader-p{k}.md"]
    for k in keys:
        for f in names(k):
            if os.path.exists(os.path.join(d, f)) and not a.dry_run: sys.exit(f"refusing: {f} exists")
    total = sum(1 for l in prof if l.startswith("- $$$"))
    for k, (lo, hi, chron, ptrs, _) in zip(keys, parts):
        fi, fc, fe, fb = (os.path.join(d, f) for f in names(k))
        ns = share(ptrs)
        what = (f"the period {lo}–{hi}" + (f" ({MONTHS[k]})" if k in MONTHS else "")) if k != "g" else "the items with no usable date"
        print(f"part {k}: {what}, {len(ptrs)} items of the share, {len(ns)} lines, "
              f"{sum(1 for l in chron if l.startswith('- '))} chronology items" + (" (dry run)" if a.dry_run else ""))
        if a.dry_run: continue
        R = [f"# S3: the reader's share of {a.stem} ({a.tag}), part {k}: {what}", "",
             f"`[tools/smelt-compress.py --s3-parts: {len(ns)} lines of the share, of {total}; the rest of the part is stated in "
             f"S3-COMPRESSED-{a.tag}-p{k}.md, to read only. L = the line's number in PROFILE-FROZEN-{a.tag}.md.]`"]
        R += ["", "*La grupoj G kaj la unuopaj linioj U de via parto: en la kronologio, ĉiu kun «→», sia speco, sia objekto kaj siaj L.*"]
        for title, letters in (("## The candidates (relational lines that may be one occasion)", "K"), ("## The nominations (possible date errors)", "N")):
            R += ["", title, ""] + [f"{items[it][2]}  ⟦{why}⟧" for it, why in ptrs if it[0] == letters]
        lo_ = [it[1] for it, _ in ptrs if it[0] == "L" and it[1] not in set(ed)]
        ed_ = [it[1] for it, _ in ptrs if it[0] == "L" and it[1] in set(ed)]
        R += ["", f"## The lines in no group of the tool ({len(lo_)}: «alia», «samnomo», a date it cannot read, or no kind; group them yourself)", "",
              ", ".join(f"L{n}" for n in lo_) or "(none)"]
        if ed_: R += ["", f"## The edition notes ({len(ed_)})", "", ", ".join(f"L{n}" for n in ed_)]
        open(fi, "x", encoding="utf-8").write("\n".join(R) + "\n")
        open(fc, "x", encoding="utf-8").write("\n".join(
            [f"# S3, compressed by tool: {a.stem} ({a.tag}), part {k}: {what}", "",
             f"`[tools/smelt-compress.py --s3-parts, cut from S3-COMPRESSED-{a.tag}.md: only this part's periods. G = an agreeing "
             f"group's statement, S = a span, R = a routine kind, U = a single line, → = an item for the reader, in "
             f"S3-INPUT-{a.tag}-reader-p{k}.md. L = the line's number in PROFILE-FROZEN-{a.tag}.md.]`", ""] + chron) + "\n")
        ex_lines = excerpt(d, a.tag, prof, ns)
        open(fe, "x", encoding="utf-8").write(
            f"# The lines of the reader's share of {a.stem} ({a.tag}), part {k}\n\n`[tools/smelt-compress.py --s3-parts: {len(ns)} of "
            f"{total} lines of PROFILE-FROZEN-{a.tag}.md, each headed by its L, in the short form (tools/smelt_inputs.py), the sigla "
            f"first; the others are stated in the chronology.]`\n\n" + ex_lines + "\n")
        b = brief
        # every file whole in one Read, the lines in the short form, the register cut to the part's names (Fable's
        # proposals 1, 2, 4, 5; 2026-10-30)
        for old, new in ((f"S3-INPUT-{a.tag}.md", fi), (f"S3-SINGLES-{a.tag}.md", fc), (f"PROFILE-FROZEN-{a.tag}.md", fe)):
            p = os.path.join(d, old)
            if p not in b: sys.exit(f"refusing: S3-BRIEF-{a.tag}.md does not name {old}")
            b = b.replace(p, SI.paths(SI.for_reader(new)))
        b = short_brief(b, d, a.tag, ex_lines + "\n" + "\n".join(chron), f"NAMES-REGISTER-{a.tag}-reader-p{k}.tsv")
        if k == "g":
            per_para = (f"\n\n**Via parto: la eroj sen uzebla dato** (la profilo estas tro granda por unu legilo, do ĝia parto "
                        f"por la legilo estas legata en periodoj; la smelt-gvidlibro, S3, «A reader's limit»). Vi legas laste nur la "
                        f"erojn sen uzebla dato («[ĝenerala]», «[sen dato]» sen diveno). La daŭraj iras en temajn erojn, laŭ la "
                        f"regulo pri «[ĝenerala]». Ago, kies daton vi povas konkludi el aliaj linioj (∴), iras en la epizodon de sia "
                        f"periodo per «vidu E…» kaj la ∴-dato; se neniu epizodo taŭgas, skribu propran, kun la ∴-dato. La epizodoj "
                        f"de la periodoj, jam skribitaj de aliaj legiloj, estas listigitaj sube: kie via ero apartenas al unu el "
                        f"ili, skribu «vidu E…», ne reskribu ĝin. **Numerado:** viaj epizodoj de E901, viaj novaj grupoj de G9001; "
                        f"la grupoj de la ilo (G…), la unuopaj U kaj la eroj de la kronologio tenas siajn numerojn.\n\n"
                        f"**La epizodoj de la periodoj:** {GEN_MARK}")
            scope = "la erojn sen dato"
        else:
            ki = int(k)
            per_para = (f"\n\n**Via parto: la periodo {lo}–{hi}" + (f", {MONTHS[k]}; la aliajn monatojn de {lo} legas alia legilo" if k in MONTHS else "")
                        + f"** (la profilo estas tro granda por unu legilo, do ĝia parto por "
                        f"la legilo estas legata en periodoj; la smelt-gvidlibro, S3, «A reader's limit»). Via enigo donas nur la "
                        f"erojn, kies «→» falas en la periodoj {lo}–{hi} de la kronologio, kaj via kronologio nur tiujn periodojn; "
                        f"la aliajn periodojn legas aliaj legiloj, kaj la erojn sen uzebla dato fina legilo. Daŭron, kiu "
                        f"komenciĝis en via periodo, rekonstruu ĝis ĝia fino, kiel viaj linioj permesas; daŭron, kiu komenciĝis "
                        f"antaŭe, ne. **Numerado:** viaj epizodoj de E{100 * ki + 1}, viaj novaj grupoj de G{1000 * ki + 1}; la "
                        f"grupoj de la ilo (G…), la unuopaj U kaj la eroj de la kronologio tenas siajn numerojn.\n")
            scope = f"vian periodon, {lo}–{hi}"
        para = reader_para(SI.paths(SI.for_reader(fc)), scope) + per_para
        b = b.replace("\nFinu la mesaĝon per la linio", para + "\nFinu la mesaĝon per la linio", 1)
        if para not in b: sys.exit(f"refusing: S3-BRIEF-{a.tag}.md has no closing line «Finu la mesaĝon per la linio»")
        b = b.replace("Ĝi donas, kun L-numeroj: ", "Ĝi donas, kun L-numeroj (la grupoj G kaj la unuopaj linioj U de via parto ne staras en ĝi, sed en la kronologio, ĉiu kun «→», sia speco, sia objekto kaj siaj L): ", 1)
        b = smelt_pieces.add(b, os.path.join(d, f"S3-RETURN-{a.tag}-reader-p{k}.md"))
        open(fb, "x", encoding="utf-8").write(b)


def reader_parts(d, tag):
    return sorted((f for f in os.listdir(d) if re.fullmatch(rf"S3-RETURN-{re.escape(tag)}-reader-p\d+\.md", f)),
                  key=lambda f: int(re.search(r"-p(\d+)\.md$", f).group(1)))

def s3_general(d, a):
    briefs = [f for f in os.listdir(d) if re.fullmatch(rf"S3-BRIEF-{re.escape(a.tag)}-reader-p\d+\.md", f)]
    rets = reader_parts(d, a.tag)
    if len(rets) != len(briefs): sys.exit(f"refusing: {len(rets)} period returns filed of {len(briefs)}")
    heads = [l.split(" · ")[0] + " · " + (l.split(" · ")[1] if " · " in l else "")
             for f in rets for l in open(os.path.join(d, f), encoding="utf-8") if re.match(r"^(?:- )?\**E\d+\**(?: \([^)]*\))?:", l)]
    p = os.path.join(d, f"S3-BRIEF-{a.tag}-reader-pg.md"); b = open(p, encoding="utf-8").read()
    if GEN_MARK not in b: sys.exit("refusing: part g's brief has its episode list already")
    open(p, "w", encoding="utf-8").write(b.replace(GEN_MARK, "\n" + "\n".join(f"- {h.strip().removeprefix('- ')}" for h in heads) + "\n"))
    print(f"S3-BRIEF-{a.tag}-reader-pg.md: {len(heads)} episode titles from {len(rets)} period returns")

def s3_join(d, a):
    files = reader_parts(d, a.tag)
    g = f"S3-RETURN-{a.tag}-reader-pg.md"
    if os.path.exists(os.path.join(d, f"S3-BRIEF-{a.tag}-reader-pg.md")) and not os.path.exists(os.path.join(d, g)):
        sys.exit(f"refusing: {g} is not filed")
    SP.join(d, a.tag, files + ([g] if os.path.exists(os.path.join(d, g)) else []), "smelt-compress.py --s3-join")


# S4 IN PERIODS ON THE COMPRESSED ROUTE (the pilot, 2026-10-30: Beauchemin's single S4 writer cut off at its output limit,
# 446,620 tokens, refused; the editor, periods first). The one S3 return is cut into the parts smelt-periods.py --s4
# reads: the chronology's periods joined to about --s4-target lines a part; each episode to the part of its first year,
# an undated or general one to part g; each group to the parts whose episodes cite it, an uncited one to g; parts 3–5 of
# the return (candidates, lines, faults) to g; and each part's chronology items, read-only, as a part 6, so that
# smelt-periods.py --s4 puts their lines in the part's excerpt. Writes S3-INPUT-<tag>-p<k>.md (its first line the period,
# as smelt-periods.py's span() reads it) and S3-RETURN-<tag>-p<k>.md, create-only; then smelt-periods.py --s4, --s4-summary
# and --s4-join as for a period run.
EP = re.compile(r"^(?:- )?\**E(\d+)\**: ")
GR = re.compile(r"^(?:- )?\**G(\d+)\**: ")

def split_s4(d, a):
    rd = lambda f: open(os.path.join(d, f), encoding="utf-8").read()
    ret = rd(f"S3-RETURN-{a.tag}.md").split("\n")
    secs, cur = {k: [] for k in "12345"}, None
    for l in ret:
        m = re.match(r"^## ([1-5])\.", l)
        if m: cur = m.group(1); continue
        if l.startswith("Fino:"): continue
        if cur: secs[cur].append(l)
    def blocks(lines, pat):
        out, b = [], None
        for l in lines:
            if pat.match(l): b = [l]; out.append(b)
            elif b is not None: b.append(l)
        return out
    eps, grs = blocks(secs["1"], EP), blocks(secs["2"], GR)
    # the chronology's periods
    per, cur_p = [], None
    for l in rd(f"S3-COMPRESSED-{a.tag}.md").split("\n"):
        m = re.match(r"^## (\d{4})–(\d{4}) \((\d+) linioj\)", l)
        if m: cur_p = [int(m.group(1)), int(m.group(2)), int(m.group(3)), []]; per.append(cur_p); continue
        if l.startswith("## Sen uzebla dato"): cur_p = ["g", None, 0, []]; per.append(cur_p); continue
        if cur_p is not None and l.startswith("- "): cur_p[3].append(l)
    parts, acc = [], None
    for p in per:
        if p[0] == "g": continue
        if acc is None or acc[2] >= a.s4_target: acc = [p[0], p[1], 0, []]; parts.append(acc)
        acc[1] = p[1]; acc[2] += p[2]; acc[3] += p[3]
    gen = next((p[3] for p in per if p[0] == "g"), [])
    def ep_date(e):
        f = e[0].split(" · ")
        return f[1] if len(f) > 1 else ""
    def ep_year(e):
        dt = ep_date(e)
        y = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", dt)
        if not y or "ĝenerala" in dt or dt.strip() in ("—", "-"): return None
        return int(y.group(1))
    # A ONE-YEAR PART CUT BETWEEN MONTHS (2026-11-10, De Beaufront's writers: 1907 and 1908 to read 546,000 and 634,000
    # characters, above Bourlet's largest, 548,000; the editor): --s4-months Y:N,… cuts the part
    # that is year Y alone into N pieces; an episode goes by the month of its date, a chronology item by its own date's
    # month or else its lines' earliest; no month, the first piece; the cut months those whose largest piece (episodes and
    # chronology, in characters) is smallest. A piece is a part of its own, numbered in order, its months in its heading.
    prof = rd(f"PROFILE-FROZEN-{a.tag}.md").split("\n")
    def l_month(n, y):
        x = re.search(rf"\*\*{y}-(\d\d)", prof[n - 1]) if 0 < n <= len(prof) else None
        return int(x.group(1)) if x else 0
    def text_month(s, y, own):
        x = re.search(rf"\b{y}-(\d\d)\b", own)
        if x: return int(x.group(1))
        ms = [m for m in (l_month(int(n), y) for n in re.findall(r"\bL(\d+)\b", s)) if m]
        return min(ms) if ms else 0
    ep_month = lambda e, y: text_month(e[0], y, ep_date(e))
    ch_month = lambda l, y: text_month(l, y, (re.search(r"\*\* · ([^·]*)·", l) or [None, ""])[1])
    if a.s4_months:
        import itertools
        want = {int(y): int(n) for y, n in (x.split(":") for x in a.s4_months.split(","))}
        new_parts = []
        for p in parts:
            y = p[0]
            if y not in want or p[1] != y or want[y] < 2:
                new_parts.append(p); continue
            eps_y = [e for e in eps if ep_year(e) == y]
            size = defaultdict(int)
            for e in eps_y: size[max(ep_month(e, y), 1)] += len("\n".join(e))
            for l in p[3]: size[max(ch_month(l, y), 1)] += len(l)
            cands_m = sorted(m for m in size if m > 1)
            if want[y] - 1 > len(cands_m): sys.exit(f"refusing: {y} has too few months for {want[y]} pieces")
            def pieces(Ms):
                ed = [1] + list(Ms) + [13]
                return [(ed[j], ed[j + 1] - 1) for j in range(len(ed) - 1)]
            Ms = min(itertools.combinations(cands_m, want[y] - 1),
                     key=lambda Ms: max(sum(v for m, v in size.items() if lo <= m <= hi) for lo, hi in pieces(Ms)))
            for lo, hi in pieces(Ms):
                ch = [l for l in p[3] if lo <= max(ch_month(l, y), 1) <= hi]
                new_parts.append([y, y, round(p[2] * len(ch) / max(len(p[3]), 1)), ch, (lo, hi)])
            print(f"{y}: cut into {want[y]} pieces, before months {', '.join(map(str, Ms))}")
        parts = new_parts
    def part_of(e):
        y = ep_year(e)
        if y is None: return "g"
        ks = [i for i, p in enumerate(parts, 1) if p[0] <= y]
        if not ks: return "1"
        if len(parts[ks[-1] - 1]) > 4 and parts[ks[-1] - 1][0] == y:
            m = max(ep_month(e, y), 1)
            for i, q in enumerate(parts, 1):
                if q[0] == y and len(q) > 4 and q[4][0] <= m <= q[4][1]: return str(i)
        return str(ks[-1])
    by_part = defaultdict(list)
    for e in eps: by_part[part_of(e)].append(e)
    keys = [str(i) for i in range(1, len(parts) + 1)] + ["g"]
    cites = {k: set(re.findall(r"\bG(\d+)\b", "\n".join("\n".join(e) for e in by_part[k]))) for k in keys}
    g_of = {k: [] for k in keys}
    for g in grs:
        n = GR.match(g[0]).group(1)
        ks = [k for k in keys if n in cites[k]] or ["g"]
        for k in ks: g_of[k].append(g)
    mo = lambda i: (f" (monatoj {parts[i][4][0]}–{parts[i][4][1]}" + (" kaj tiuj sen monato" if parts[i][4][0] == 1 else "") + ")"
                    if i < len(parts) and len(parts[i]) > 4 else "")
    if a.dry_run:
        for i, k in enumerate(keys):
            chron = parts[i][3] if k != "g" else gen
            what = f"the period {parts[i][0]}–{parts[i][1]}{mo(i)}" if k != "g" else "the lines with no usable date"
            print(f"part {k}: {what}, {len(by_part[k])} episodes, {len(g_of[k])} groups, {len(chron)} chronology items, "
                  f"{sum(len(chr(10).join(e)) for e in by_part[k]) + sum(len(l) for l in chron)} characters of episodes and chronology (dry run)")
        return
    for k in keys:
        for f in (f"S3-INPUT-{a.tag}-p{k}.md", f"S3-RETURN-{a.tag}-p{k}.md"):
            if os.path.exists(os.path.join(d, f)): sys.exit(f"refusing: {f} exists")
    # an episode running past its part's period cites items of another period (Devjatnin E37, the Parkurbo 1912–1914, in
    # part 3, citing S and R items of 1913–1914): those items join the part's chronology, so their lines reach its excerpt
    item_of = {}
    for p in per:
        for l in p[3]:
            m = re.match(r"^- \*\*([GSRU]\d+)\*\*", l)
            if m: item_of.setdefault(m.group(1), l)
    for i, k in enumerate(keys):
        lo, hi, n, chron = (parts[i][0], parts[i][1], parts[i][2], list(parts[i][3])) if k != "g" else (None, None, 0, list(gen))
        lo_hi_mo = mo(i) if k != "g" else ""
        own = {m.group(1) for l in chron for m in [re.match(r"^- \*\*([GSRU]\d+)\*\*", l)] if m}
        cited = re.findall(r"\b([GSRU]\d+)\b", "\n".join("\n".join(e) for e in by_part[k] + g_of[k]))
        extra = [item_of[c] for c in dict.fromkeys(cited) if c in item_of and c not in own]
        if extra: chron += ["", "*Kaj la eroj de aliaj periodoj, kiujn la epizodoj de ĉi tiu parto citas:*", ""] + extra
        what = f"the period {lo}–{hi}{lo_hi_mo}" if k != "g" else "the lines with no usable date"
        # THE SINGLE LINES ONCE (2026-11-10, Fable's proposal 2, the editor's ruling): a tool's U line was in section 6 and
        # again, with its own fact, on its S4-LINES head («L42 (U372)»); it goes here, where smelt-periods.py --s4 reads it
        # for the part's lines and no writer is given it
        uch = [l for l in chron if re.match(r"^- \*\*U\d+\*\*", l)]
        chron = [l for l in chron if l not in set(uch)]
        open(os.path.join(d, f"S3-INPUT-{a.tag}-p{k}.md"), "x", encoding="utf-8").write(
            f"# S3, part {k} of {a.stem} ({a.tag}): {what}\n\n`[tools/smelt-compress.py --split-s4: no reader read this part; "
            f"it is cut from S3-RETURN-{a.tag}.md for the biography in periods (smelt-periods.py --s4). Below, the tool's "
            f"{len(uch)} single lines (U) of the part's chronology, for the part's lines; no writer reads this file.]`\n\n"
            + "\n".join(uch) + "\n")
        body = [f"# S3, part {k} of {a.stem} ({a.tag}): {what}", "",
                f"`[tools/smelt-compress.py --split-s4, from S3-RETURN-{a.tag}.md and S3-COMPRESSED-{a.tag}.md: {len(by_part[k])} episodes, "
                f"{len(g_of[k])} groups, {len(chron)} items of the chronology.]`", "", "## 1. La epizodoj", ""]
        for e in by_part[k]: body += [x for x in e if x.strip()] + [""]
        body += ["## 2. La grupoj", ""]
        for g in g_of[k]: body += [x for x in g if x.strip()] + [""]
        for s, t in (("3", "La kandidatoj kaj la nomumoj"), ("4", "La linioj en neniu grupo"), ("5", "La difektoj de la linioj")):
            body += [f"## {s}. {t}", ""] + ([x for x in secs[s] if x.strip()] if k == "g" else ["(en la parto g)"]) + [""]
        body += ["## 6. La kronologio de la ilo, nur por legi", "",
                 "*La eroj de la ilo (`smelt-compress.py`) por ĉi tiu parto: G grupo, S daŭro, R rutina speco, U unuopa linio, "
                 "→ ero de la epizoda legilo. La epizodoj supre citas ilin per iliaj numeroj; iliaj linioj estas en via eltiraĵo. "
                 "La unuopaj linioj U ne estas ĉi tie: ĉiu staras en via dosiero de linioj, kun sia U-numero.*", ""]
        body += chron + ["", f"Fino: {len(by_part[k])} epizodoj, {len(g_of[k])} grupoj."]
        open(os.path.join(d, f"S3-RETURN-{a.tag}-p{k}.md"), "x", encoding="utf-8").write("\n".join(body) + "\n")
        print(f"part {k}: {what}, {len(by_part[k])} episodes, {len(g_of[k])} groups, {len(chron)} chronology items" + (f", about {n} lines" if n else ""))


if __name__ == "__main__":
    main()
