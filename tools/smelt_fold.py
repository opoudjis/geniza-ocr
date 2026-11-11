#!/usr/bin/env python3
"""smelt_fold.py — the sale notices folded for the biography's writers (the editor, 2026-11-10;
to building it before Devjatnin's run: approved).

A sale notice is an «anonco» line whose statement says that a work is sold, announced or offered (vendata, anoncita, havebla,
a price …) and says nothing of a claim, a conflict, an editing or a first meeting (aserto, laŭ, refut-, konflikt-, redakci-,
«kun la helpo», kritik-, «kontraŭ», ekkon-, «unua fojo»): such a line stays a line. The notices of one work (the kind's
object) in one writer's lines become one line, which lists every L, so each can still be cited, the years they span, and one
of them as the example. Measured 2026-11-10 (the scratch measure and a look at 45 of De Beaufront's notices: 42 plain notices,
3 not, which the rule keeps): De Beaufront 1,299 of 1,548 notices into 141 lines, Devjatnin 206 into 71, Couturat 349 into 53.

The first stage needs no fold: tools/smelt-compress.py already states the routine kinds (anonco among them) as one R item each.
Used by tools/smelt-periods.py --s4 on each part's S4-LINES. Ezri, 2026-11-10."""
import re
from collections import OrderedDict
import factline as FL

SALE = re.compile(r"(?i)\b(vendat|vendiĝ|vendas|anoncit|anoncat|anoncas|havebla|ofertat|ofertas|katalog|je \d|fr\.|frank|cendoj|prezo)")
NOT = re.compile(r"(?i)(aserto|\blaŭ\b|refut|konflikt|redakci|kun la helpo|kritik|kontraŭ\b|ekkon|unua fojo)")
OBJ = re.compile(r"^\{anonco: ([^}]*)\}")


def title(line):
    """the work a sale notice is of, or None for any other line"""
    f = FL.fields(line)
    if not f or not f["kind"]: return None
    m = OBJ.match(f["kind"])
    if not m or not SALE.search(f["fact"]) or NOT.search(f["fact"]): return None
    return re.sub(r"\W+", " ", m.group(1).lower()).strip()[:60]


def fold(ns, line_of):
    """ns in order -> entries in order: ("line", n), or ("fold", work, [n, …]) at its first line; a work with one notice stays a line"""
    by = OrderedDict()
    for n in ns:
        t = title(line_of(n))
        if t: by.setdefault(t, []).append(n)
    first = {v[0]: (k, v) for k, v in by.items() if len(v) > 1}
    folded = {n for k, v in by.items() if len(v) > 1 for n in v}
    out = []
    for n in ns:
        if n in first: out.append(("fold",) + first[n])
        elif n not in folded: out.append(("line", n))
    return out


# TWO COPIES, ONE LINE (2026-11-10; the editor's to Fable's proposal 8): a fact the two copies of one work gave twice (the
# same label less its letter, the same date, kind and fact) one line listing both L; a line with no label, or a copy across
# heads («⟦kopio el»), stays a line
DOUBLES = False   # off (2026-11-10): on Schneeberger 13 lines of 2,185, and it took two issues of Ruslanda Esperantisto, «1907.4» and «1907.5-6», page 25, for two copies

def doubles(entries, line_of, label):
    """entries of fold() -> the same, a double's lines as ("double", [n, …]) at its first"""
    key = {}
    words = lambda s: set(re.findall(r"\w{3,}", s.lower()))
    for e in entries:
        if e[0] != "line": continue
        n = e[1]; f = FL.fields(line_of(n)); lb = (label or {}).get(n)
        if not f or not f["kind"] or not lb or lb.endswith("?") or ":" not in lb or "⟦kopio el" in f["voice"] + f["fact"]: continue
        # the work's siglum, the printed page less the line's letter: the two copies' labels differ in the issue's form
        k = (lb.split(" ")[0].split(":")[0], re.sub(r"[a-z]+$", "", lb.rsplit(":", 1)[1]), f["date"],
             re.sub(r"[^\w ]+", " ", f["kind"].lower()).split())
        key.setdefault(str(k), []).append(n)
    groups = {}
    for v in key.values():
        if len(v) < 2: continue
        w0 = words(FL.fields(line_of(v[0]))["fact"])
        same = [v[0]] + [n for n in v[1:] if (lambda w: w0 and w and len(w0 & w) * 2 >= min(len(w0), len(w)))(words(FL.fields(line_of(n))["fact"]))]
        if len(same) > 1: groups[same[0]] = same
    inner = {n for v in groups.values() for n in v[1:]}
    out = []
    for e in entries:
        if e[0] == "line" and e[1] in groups: out.append(("double", groups[e[1]]))
        elif not (e[0] == "line" and e[1] in inner): out.append(e)
    return out


def folded_line(ns, line_of):
    """one line for a work's notices: every L, the years, the kind as the first notice gives it, and the first notice's statement"""
    f = FL.fields(line_of(ns[0]))
    ys = sorted({y for n in ns for y in re.findall(r"\b1[89]\d\d\b|\b20[0-2]\d\b", (FL.fields(line_of(n)) or {}).get("date", ""))})
    span = f"{ys[0]}–{ys[-1]}" if len(ys) > 1 else (ys[0] if ys else "—")
    return (", ".join(f"L{n}" for n in ns) + f" (faldite de ilo: {len(ns)} anoncoj pri vendo de la sama verko): " + span + " · "
            + f["kind"] + " · ekz.: " + f["fact"])
