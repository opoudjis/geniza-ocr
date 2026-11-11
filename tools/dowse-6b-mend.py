#!/usr/bin/env python3
"""The 6b format faults of many sources mended at once by «replace_lines» in each source's facts-config.json (2026-11-11;
the chain harvest-2026-11-11a stopped at its first source's 6b, and 448 faults in 16 of its 36 sources were found and mended
in one pass; first a scratch script, lost in a session crash, made a tool after it; the dress runbook: fixes go in the
settings, never into the returns).

    tools/dowse-6b-mend.py SOURCE@TAG … [--issue-rule SOURCE …] [--default-label SOURCE=LABEL …]
                           [--label SOURCE:RETURN:LINE=LABEL …] [--show N] [--write]

1. The check: `file-return.py --fixes --lines` over each source's returns (the returns of agents-TAG.tsv), read-only; the
   faults gathered, each with its line as the assembler sees it.
2. The mend, by rule, on the reader's line; the new line then taken through the assembler's own expand_lean, form_repair and
   cited_line (as the assembler does before it applies an entry); the key is the old line's head (name, date, kind, fact) as
   the assembler sees it, unique in its return, else the whole line:
   - the voice made one field: the marks first (✅ 📣 📄, then ⚠ ❓), then one bracket of the labels and notes;
     «✅ (sendependa) refutas: X» → «✅ (sendependa; refutas: X)»; a bare «derivita ↤ …» given «📣»;
   - THE INDEPENDENCE LABEL of a secondary source's line: --issue-rule SOURCE applies the editor's ruling of 2026-11-11 for a
     periodical's issues classed SECONDARY (the second option, chosen: «sendependa» for the reports of the issue's own time, «sen
     fontindiko» for a later issue's retrospective lines): «sendependa» when the line is dated by its issue («[n]»), or its
     year is within two of the issue's (the issue's year read from the locator's item), or it is undated in an issue of 1920
     or before, or it is a judgement, an interpretation or historiography; else «sen fontindiko». --default-label
     SOURCE=LABEL for a source's own default (the 1886 journals' «sendependa», the precedent of 2026-11-01); --label for one
     line by eye; otherwise «sen fontindiko»;
   - the locators: a voice written before «l. K» put after it; «(prese) l. K», the printed page empty, the bare «l. K»;
     --locator SOURCE:RETURN:LINE=LOC for a line whose locator is known (a reader's own correction note); a note's locator «(prese M, noto K)» or «(prese M) noto K»
     given its item key and PDF page when the source's offset is known (--note-pdf SOURCE=OFFSET, PDF = printed + OFFSET);
     a note line with no voice given «📣 (derivita ↤ ‹the note's citation›)» for a work, else «📣 (sen fontindiko)»;
   - the kind field: a date written after the kind put before it; no date: the year of a birth or death from the fact,
     else «[sen dato]»; a date's own words moved into the voice's notes; «**[prese N]** **[n]**» → «**[n]**»;
   - table markup («colspan="2"|») out of an anchor; a second kind not on the list («+demisio») dropped, the fact keeping it.
   A fault no rule mends is listed, for a hand fix.
3. --write: each source's facts-config.json written first if absent (`dowse-facts-assemble.py --first-config TAG`), then
   the entries appended to its «replace_lines» with a «_replace_note». Without --write, the counts and the label tallies,
   and with --show N, N new lines a source. Then run the check again (step 1 alone: no --write, the faults left).
Writes only with --write: the sources' facts-config.json. Ezri."""
import argparse, collections, importlib.util, json, os, re, subprocess, sys
from pathlib import Path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
T = os.path.join(ROOT, "tools")

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = saved
    return m

MARK = "✅📣📄⚠❓"
def groups_of(v):
    out, bare, depth, cur = [], "", 0, ""
    for ch in v:
        if ch == "(":
            if depth: cur += ch
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            if depth: cur += ch
            else: out.append(cur.strip()); cur = ""
        elif depth: cur += ch
        else: bare += ch
    return out, bare

def voice(v, label=None):
    gs, bare = groups_of(v)
    marks = [c for c in bare if c in MARK]
    text = re.sub(r"\s+", " ", re.sub(f"[{MARK}]", " ", bare)).strip(" ;,")
    prim = [c for c in marks if c in "✅📣📄"][:1] or ["📣"]
    sec = [c for c in "⚠❓" if c in marks]
    items = [x for x in [text] + gs if x]
    have = any(re.match(r"(sendependa|derivita|sen fontindiko)\b", x) for x in items)
    if label and not have: items = [label] + items
    return " ".join(prim + sec) + (f" ({'; '.join(items)})" if items else "")

def head_split(raw):
    m = re.match(r"^(- \$\$\$ .+? \$\$\$(?: \([^)]*\))?)(.*)$", raw)
    pre, after = m.group(1), m.group(2)
    fields = after.split(" · ")
    return pre, fields[0], fields[1:]

SAYING = ("juĝo", "interpreto", "historiografio")
def issue_label(x):
    """the editor's ruling of 2026-11-11 for a periodical's SECONDARY issues: (label, why)"""
    loc = re.search(r", PDF \d+", x)
    item = x[:loc.start()].split(" · ")[-1] if loc else ""
    ys = re.findall(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", item)
    iy = int(ys[0]) if ys else None
    pre, d, rest = head_split(x)
    km = re.search(r"\{([^:}]+)", x); kind = km.group(1).strip() if km else ""
    if "[n]" in d: return "sendependa", "issue"
    dy = [int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", d)]
    if dy and iy: return ("sendependa", "near") if max(dy) >= iy - 2 else ("sen fontindiko", "earlier")
    if iy and iy <= 1920: return "sendependa", "undated-early"
    if kind in SAYING: return "sendependa", "saying"
    return "sen fontindiko", "undated-late"

def main_key(lines):
    c = collections.Counter(m.group(1) for l in lines for m in re.finditer(r"(?:^|· )([^·;]+?), PDF \d+", l))
    return c.most_common(1)[0][0] if c else ""

def mend(s, r, n, f, raw, assembled, a):
    why = []; label = None
    pre, d, rest = head_split(raw)
    if not d.strip() and rest and rest[0].startswith("{") and len(rest) > 1 and re.match(r"^\*\*.*\*\*$", rest[1].strip()):
        d, rest = " " + rest[1].strip(), [rest[0]] + rest[2:]; why.append("la dato antaŭ la speco")
    elif not d.strip() and rest and rest[0].startswith("{"):
        k = rest[0]; fact = rest[1] if len(rest) > 1 else ""; y = None
        if re.match(r"\{(naskiĝo|morto)", k):
            m = re.search(r"(?:naskiĝis|mortis)\b[^.]*?\ben (1[89]\d\d|20\d\d)\b", fact); y = m.group(1) if m else None
        d = f" **{y}**" if y else " **[sen dato]**"; why.append("la dato el la fakto" if y else "sen dato")
    note = None
    if re.match(r"^ \*\*\[prese \d+\]\*\* \*\*\[n\]\*\*$", d): d = " **[n]**"; why.append("«[prese N]» for la dato")
    m = re.match(r"^ (\*\*[^*]+\*\*)(?: (\*\*\[n\]\*\*))?\s*(.*)$", d)
    if m and m.group(3).strip():
        d = " " + m.group(1); note = f"la dato en la teksto: {m.group(3).strip()}"; why.append("la vortoj de la dato al la notoj")
    elif d.strip() and not d.strip().startswith("**"):
        note = f"la dato en la teksto: «{d.strip()}»"; d = " **[sen dato]**"; why.append("la vortoj de la dato al la notoj")
    if rest:
        m = re.match(r"^\{([^;}]+)((?:; \+[^;}]+)*)\}$", rest[0].strip())
        if m and m.group(2):
            known = a.kinds
            keep = [p for p in m.group(2).split("; +")[1:] if p.split(":")[0].strip() in known]
            if len(keep) < len(m.group(2).split("; +")[1:]):
                rest[0] = "{" + m.group(1) + "".join("; +" + p for p in keep) + "}"; why.append("dua speco ne en la listo for")
    if 'colspan="2"|' in raw:
        i = next(i for i, p in enumerate(rest) if 'colspan="2"|' in p)
        rest = rest[:i] + [rest[i].split("|", 1)[1]] + rest[i + 2:]; why.append("la tabela marko for el la ankro")
    for i, p in enumerate(rest):   # an empty printed page, «(prese) l. K»: the bare «l. K», as its neighbours (2026-11-11)
        if re.fullmatch(r"\(prese\) (l\. \d+)", p.strip()): rest[i] = p.strip()[len("(prese) "):]; why.append("«(prese)» malplena for")
    loc = a.locators.get((s, r, n))   # --locator: a locator known (the reader's own correction note), put before the voice
    if loc and rest and not any(re.search(r"(^| )l\. \d+$|, PDF \d+|, ¶ \d+", p.strip()) for p in rest[:-1]):
        rest = rest[:-1] + [loc, rest[-1]]; why.append(f"la lokindiko «{loc}» aldonita")
    if len(rest) >= 2 and re.match(r"^l\. \d+$", rest[-1].strip()) and rest[-2].strip()[:1] in MARK:
        rest[-2], rest[-1] = rest[-1], rest[-2]; why.append("la voĉo post «l. K»")
    key = main_key(assembled)
    off = a.note_pdf.get(s)
    for i, p in enumerate(rest):
        m = re.fullmatch(r"\(prese (\d+), noto (\d+)\)", p.strip()) or re.fullmatch(r"\(prese (\d+)\) noto (\d+)", p.strip())
        if m and off is not None and key:
            rest[i] = f"{key}, PDF {int(m.group(1)) + off} (prese {m.group(1)}), noto {m.group(2)}"; why.append("la lokindiko de la noto")
    if rest and re.search(r", PDF \d+ \(prese \d+\), noto \d+$", rest[-1]):
        anchor = rest[-2].strip().rstrip(".") if len(rest) >= 2 else ""
        lab = f"derivita ↤ {anchor}" if rest[0].startswith("{verko") and anchor else "sen fontindiko"
        rest.append(voice("📣", lab)); why.append("voĉo aldonita")
    if rest and rest[-1].strip()[:1] in MARK + "dsr":
        v = rest[-1]
        if re.match(r"^(derivita|sendependa|sen fontindiko|refutas:)", v.strip()): v = "📣 (" + v.strip() + ")"
        if "independence label" in f:
            lab = a.line_labels.get((s, r, n))
            if not lab and s in a.issue_rule: lab = issue_label(raw)[0]
            label = lab or a.defaults.get(s, "sen fontindiko"); why.append(f"«{label}»")
        nv = voice(v, label)
        if note: nv = nv[:-1] + f"; {note})" if nv.endswith(")") else nv + f" ({note})"
        if nv != rest[-1]:
            rest[-1] = nv
            if "independence label" not in f: why.append("la voĉo unu kampo")
    return pre + d + " · " + " · ".join(rest), why

def check(sources, FR):
    """the 6b check over each source@tag: [(source, return, line, fault)]"""
    out = []
    for s, t in sources:
        ag = os.path.join(G, "dowse", s, f"agents-{t}.tsv")
        rets = [os.path.basename(l.split("\t")[1].strip()) for l in open(ag, encoding="utf-8") if l.strip() and not l.startswith("#") and "\t" in l]
        p = subprocess.run([sys.executable, os.path.join(T, "file-return.py"), "--fixes", "--lines"] + [f"geniza/dowse/{s}/{r}" for r in rets],
                           capture_output=True, text=True, cwd=ROOT)
        cur = None; n0 = len(out)
        for l in (p.stdout + p.stderr).split("\n"):
            m = re.match(r"(facts-return-\S+\.md): \d+ format", l)
            if m: cur = m.group(1); continue
            m = re.match(r"\s+line (\d+): (.*?) · - \$\$\$", l)
            if m and cur: out.append((s, cur, m.group(1), m.group(2)))
        print(f"{s}@{t}: {len(rets)} returns, {len(out) - n0} faults", flush=True)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", metavar="SOURCE@TAG")
    ap.add_argument("--issue-rule", nargs="*", default=[], metavar="SOURCE")
    ap.add_argument("--default-label", nargs="*", default=[], metavar="SOURCE=LABEL")
    ap.add_argument("--label", nargs="*", default=[], metavar="SOURCE:RETURN:LINE=LABEL")
    ap.add_argument("--note-pdf", nargs="*", default=[], metavar="SOURCE=OFFSET")
    ap.add_argument("--locator", nargs="*", default=[], metavar="SOURCE:RETURN:LINE=LOCATOR")
    ap.add_argument("--show", type=int, default=0); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    a.issue_rule = set(a.issue_rule)
    a.defaults = dict(x.split("=", 1) for x in a.default_label)
    a.line_labels = {}
    for x in a.label:
        k, v = x.split("=", 1); s, r, n = k.split(":"); a.line_labels[(s, r, n)] = v
    a.note_pdf = {k: int(v) for k, v in (x.split("=", 1) for x in a.note_pdf)}
    a.locators = {}
    for x in a.locator:
        k, v = x.split("=", 1); s, r, n = k.split(":"); a.locators[(s, r, n)] = v
    srcs = [tuple(x.split("@", 1)) for x in a.sources]
    FR = load("fr", os.path.join(T, "file-return.py")); A = load("asm", os.path.join(T, "dowse-facts-assemble.py"))
    hf, kinds = FR._hf(); a.kinds = set(kinds) if not isinstance(kinds, dict) else set(kinds)
    faults = check(srcs, FR)
    cache = {}
    def assembled(s, r):
        if (s, r) not in cache:
            D = os.path.join(G, "dowse", s)
            cache[(s, r)] = [(raw, A.cited_line(D, r, A.form_repair(A.expand_lean(D, r, raw))))
                             for raw in open(os.path.join(D, r), encoding="utf-8").read().split("\n") if raw.startswith("- $$$")]
        return cache[(s, r)]
    by = collections.defaultdict(list); tally = collections.Counter(); labels = collections.Counter(); left = []
    for s, r, n, f in faults:
        D = os.path.join(G, "dowse", s)
        raw = open(os.path.join(D, r), encoding="utf-8").read().split("\n")[int(n) - 1]
        al = assembled(s, r)
        old = next((x for rw, x in al if rw == raw), None)
        if old is None: left.append((s, r, n, f, "line not found")); continue
        newraw, why = mend(s, r, n, f, raw, [x for _r, x in al], a)
        new = A.cited_line(D, r, A.form_repair(A.expand_lean(D, r, newraw)))
        l3, _k = hf.take_kind(hf.form_repair(new)); rec, w2 = hf.parse(hf.to2(l3)); w2 = w2 or hf.strict(rec, True)
        if new == old or w2: left.append((s, r, n, f, w2 or "unchanged")); continue
        pre, d, rest = head_split(old)
        key = pre + d + " · " + " · ".join(rest[:2])
        if sum(key in x for _r, x in al) != 1: key = old
        if sum(key in x for _r, x in al) != 1: left.append((s, r, n, f, "key not unique")); continue
        by[s].append([key, new, r, "; ".join(w for w in why if w)]); tally[s] += 1
        if "independence label" in f:
            labels[(s, next((w for w in why if w.startswith("«")), ""))] += 1
    print("mended:", dict(tally), "total", sum(tally.values()))
    print("labels:", {f"{k[0]} {k[1]}": v for k, v in labels.items()})
    print(f"left for a hand fix: {len(left)}")
    for x in left[:40]: print("  ", x[0], x[1], x[2], "|", x[3][:70], "|", x[4][:90])
    if a.show:
        for s, es in by.items():
            for k, nw, r, w in es[:a.show]: print(f"\n[{s} {r}] {w}\n  NEW {nw[-240:]}")
    if a.write:
        for s, es in by.items():
            t = dict(srcs)[s]; cp = os.path.join(G, "dowse", s, "facts-config.json")
            if not os.path.exists(cp):
                p = subprocess.run([sys.executable, os.path.join(T, "dowse-facts-assemble.py"), s, "--first-config", t], capture_output=True, text=True)
                print(s, (p.stdout or p.stderr).strip()[-200:])
            cfg = json.load(open(cp, encoding="utf-8"))
            have = {(e[0], e[2] if len(e) > 2 else "") for e in cfg.get("replace_lines", [])}
            add = [[k, nw, r] for k, nw, r, w in es if (k, r) not in have]
            cfg.setdefault("replace_lines", []).extend(add)
            cfg.setdefault("_replace_note", []).append(
                f"{__import__('datetime').date.today()}, Ezri: {len(add)} lines of the 6b format check mended by tools/dowse-6b-mend.py: "
                + "; ".join(sorted({w for _k, _n, _r, w in es}))[:900]
                + (" · the independence labels by the editor's ruling of 2026-11-11 on a periodical's SECONDARY issues (the second option)" if s in a.issue_rule else ""))
            json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"{s}: {len(add)} «replace_lines» added")

if __name__ == "__main__":
    main()
