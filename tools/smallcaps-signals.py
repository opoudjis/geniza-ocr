#!/usr/bin/env python3
r"""smallcaps-signals — a widened telltale test for names garbled out of small capitals, and its test against the snippet
readings by vision (what Tesseract read, against what the snippet says).

    tools/smallcaps-signals.py test    --out <geniza>/ocr/runs/SMALLCAPS-SIGNALS-TEST-<date>.md
    tools/smallcaps-signals.py confuse --out <geniza>/ocr/runs/SMALLCAPS-CONFUSIONS-<date>.md [--roster <ROSTER-FULL file>]
    tools/smallcaps-signals.py pages   --out <dir> [--resume]

WHY (the editor 2026-10-25 00:3x; 00:3x, to testing the signals on the
known garbles first: approved, as still broad but better targeted). The telltale pattern (two
capitals together inside a word) caught «ZavMExu~HOr» and missed «BoxxeHox», «TurixE», «Fnrrscur», «Ansocp», «MeEven»
(`ocr/method/NAME-CROPS-EXPLORATION-2026-10-24.md` § 1). Four more signs, each on one word of Tesseract's reading:
  TELL      the telltale pattern as it stands (`tools/ocr-name-crops.py`)
  MIDCAP    a single capital after a lower-case letter inside the word (BoxxeHox, MeEven, TurixE)
  X         an x in a word of no word list (small-capital N, U, R read as x: Boxxe-, Coxxok, Rosiavx)
  CLUSTER   a run of three letters (word edges counted) that no word of the Latin-script lists has (Fnrr-, -ocp)
  AFTER     a capitalised word of no word list straight after an initial or a title (J. G. Fnrrscur, Sam. MeEven)
TEST: the snippets of the *Svisa Espero* runs (`sources/ocr-work/name-crops-2026-10-24-svisa{,-b,-c}/`: KEY.tsv,
Tesseract's text of each snippet; returns/, the vision reading). Each capitalised word of 3+ letters of the vision
reading in no word list (a NAME) is paired with the nearest word of Tesseract's text of the same snippet: GARBLED where
they differ (case and accents folded), READ RIGHT where they agree. ORDINARY: Tesseract's words that agree with a word of
the vision reading and are not names (the false-alarm base). Then the five known garbles above with their neighbours.
CONFUSE (the editor 00:5x,): small capitals the signs miss come out as lower-case words with the same swaps
(«Rusrenuotz» RUSTERHOLZ, «Bnecuer» BREGUET, «Fnepno» FREDRO: R as n, T as r, H as u). The swaps are counted from the heavy
garbles of the test; a word of no word list is then compared with every roster form of the same first letter, a swap
costing a quarter of a change. CONFUSE as a sign: the word comes within 0.34 of a roster form. Scored on the heavy garbles
(caught, and the right name found), against the names read right and their own roster neighbours.
PAGES (the editor,): every signed page's search text (the newest absence ledger's items), each word through the
signs (CONFUSE too); the Cyrillic pages (`ocr/runs/OCR-BISCRIPT-LATIN-CENSUS-2026-10-24d.tsv`) and the Fraktur pages
(PREFERRED.tsv: a recipe of `frk`) left out. A row a item to `<dir>/PAGES.tsv` as it is done (--resume continues), then
`<dir>/SUMMARY.md`: pages by flagged words, snippets, sheets, tokens and the week's share; by title; the census's pages
(3+ telltale words) against the rest.
SELECT: from a pages run (--dir), the pages with --min or more words of tier --tier, less the pages the register
(`ocr/VISION-REGISTER.tsv`) shows read whole by vision, keyed by hand or already snippeted, the born-digital pages, and pages with 5+ words of Cyrillic read as Latin (CYR); --out a pages file for
`ocr-name-crops.py build --pages-file … --tier N`.
TIERS: from a pages run (--dir), each tier's catch on the test's heavy garbles and its cost scaled to the corpus.
WRITE-SET: test, confuse, tiers, select: --out (create-only). pages: <dir> (new, or --resume): PAGES.tsv, PROGRESS.txt, SUMMARY.md.
Reads only otherwise.
"""
import argparse, collections, csv, difflib, glob, importlib.util, os, re, sys, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
_s = importlib.util.spec_from_file_location("nc", os.path.join(HERE, "ocr-name-crops.py"))
NC = importlib.util.module_from_spec(_s); _s.loader.exec_module(NC)
INITIALS = re.compile(r"^(?:[A-ZÀ-Ž][a-z]?\.-?)+,?$")   # «F.-R.», «J.», «Th.» (the title list's initial is one letter)
# TITLES (the editor 2026-10-25 11:5x: «does your title check catch S-roj(n) X, Y, Z, and S-roj X, Y(,) kaj Z, for
# repeating Y? Ges-roj(n)? S-inoj? F-inoj?»): the Esperanto titles with their plurals and accusatives, abbreviated and in
# full, and the French, German and English ones the press prints; a trailing comma or full stop allowed
TITLES = re.compile(r"^(?:S-?ro|Ges-?ro|S-?ino|F-?ino|Ges-?inj?oro|D-?ro|Prof|Profesoro|Doktoro|Sinjoro|Sinjorino|Fraŭlino|"
                    r"Gesinjoro|Pastro|Abato|Kapitano|Leŭtenanto|Kolonelo|Generalo|Majoro|Barono|Grafo|Grafino|Princo|Princino|"
                    r"S-?ano|Sam(?:ideano)?|Herr[n]?|Hr|Frau|Frl|Fräulein|Dr|Mr|Mrs|Miss|Messrs|M|MM|Mme|Mmes|Mlle|Mlles|"
                    r"Monsieur|Madame|Mademoiselle|Fr)(?:j|oj|n|jn|ojn)?\.?,?:?$", re.I)
LINK = re.compile(r"^(?:kaj|k|kaj\.|et|und|u\.|and|&|e|y|i|a|und)$", re.I)


def title_run(tokens):
    """for each token, is it inside a run of names opened by a title or an initial? «S-roj X, Y kaj Z»: X, Y and Z all
    are; a run goes on over names ending in a comma and the link words (kaj, k, et, und, and, &), and ends at a word that
    is neither a capitalised word nor an initial nor a link, or at a full stop after a name of 3+ letters"""
    out = [False] * len(tokens); open_ = False
    for k, t in enumerate(tokens):
        core = re.sub(r"^[^\w]+|[^\w.,:]+$", "", t)
        if TITLES.match(core) or NC.TITLE.match(core) or INITIALS.match(core):
            open_ = True; continue
        if not open_: continue
        if LINK.match(core): continue
        if core[:1].isupper():
            out[k] = True
            if re.search(r"[^\W\d_]{3,}\.$", core) or core.endswith(";"): open_ = False
            continue
        open_ = False
    return out
WORD = re.compile(r"[^\W\d_](?:[^\W\d_'’~-]|['’~-](?=[^\W\d_]))*")


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


class Signals:
    def __init__(self):
        self.lex = NC.lexicon(); self.de = NC.german_lexicon()
        self.tri = set()
        for w in self.lex:
            w = "^" + re.sub(r"[^a-z]", "", w) + "$"
            self.tri.update(w[i:i + 3] for i in range(len(w) - 2))

    def of(self, word, prev=""):
        # the longest run of letters in the token («Ansocp,en» → Ansocp: Tesseract joins words across a comma)
        core = max((m.group(0) for m in WORD.finditer(word)), key=len, default=""); f = fold(core); known = f in self.lex
        letters = "^" + re.sub(r"[^a-z]", "", f) + "$"
        s = set()
        if NC.TELL.search(core): s.add("TELL")
        if re.search(r"[a-zß-öø-ÿ][A-ZÀ-ÖØ-Þ]", core): s.add("MIDCAP")
        if "x" in f and not known: s.add("X")
        if len(letters) >= 5 and not known and any(letters[i:i + 3] not in self.tri for i in range(len(letters) - 2)):
            s.add("CLUSTER")
        after = prev is True or (isinstance(prev, str) and bool(NC.TITLE.match(prev.strip()) or INITIALS.match(prev.strip())
                                                                or TITLES.match(prev.strip())))
        if core[:1].isupper() and len(core) >= 3 and not known and after:
            s.add("AFTER")
        if core[:1].isupper() and len(core) >= 2 and after:
            s.add("TITLED")   # remedy 2: any capitalised word after a title, in a word list or not («S-ro Menu» for MUDIE)
        return s


def pairs(sig):
    out = {"GARBLED": [], "READ RIGHT": [], "ORDINARY": []}
    for d in sorted(glob.glob(os.path.join(G, "sources", "ocr-work", "name-crops-2026-10-24-svisa*"))):
        key = {x[0]: x for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(d, "KEY.tsv"), encoding="utf-8")) if len(x) >= 6}
        for rf in sorted(glob.glob(os.path.join(d, "returns", "sheet-*.txt"))):
            for l in open(rf, encoding="utf-8"):
                x = l.rstrip("\n").split("\t", 1)
                if len(x) < 2 or x[0] not in key or x[1].strip() == "NOT SEEN": continue
                tw = key[x[0]][5].split(); vw = [m.group(0) for m in WORD.finditer(x[1])]
                vf = {fold(w) for w in vw}; where = f"{key[x[0]][2]} p. {key[x[0]][3]}"
                names = [w for w in vw if w[:1].isupper() and len(w) >= 3 and fold(w) not in sig.lex
                         and not NC.german(sig.de, w)]   # a German compound is no name (Fachausdrücke, Wörterbüchern)
                used = set(); tr = title_run(tw)
                for nm in names:
                    best = max(((difflib.SequenceMatcher(None, fold(nm), fold(re.sub(r"^[^\w]+|[^\w]+$", "", t))).ratio(), k)
                                for k, t in enumerate(tw)), default=(0, -1))
                    if best[0] < 0.3: continue
                    k = best[1]; used.add(k); t = re.sub(r"^[^\w]+|[^\w]+$", "", tw[k])
                    cls = "READ RIGHT" if fold(t) == fold(nm) else "GARBLED"
                    out[cls].append((tw[k], nm, sig.of(tw[k], tr[k] or (tw[k - 1] if k else "")), where))
                for k, t in enumerate(tw):
                    c = re.sub(r"^[^\w]+|[^\w]+$", "", t)
                    if k not in used and len(c) >= 3 and fold(c) in vf:
                        out["ORDINARY"].append((t, c, sig.of(t, tr[k] or (tw[k - 1] if k else "")), where))
    return out


def test(a):
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    sig = Signals(); P = pairs(sig)
    S = ["TELL", "MIDCAP", "X", "CLUSTER", "AFTER"]
    with open(a.out, "x", encoding="utf-8") as w:
        w.write("# Small-capital garbles: the widened telltale test, against the snippet readings (2026-10-25)\n\n"
                "`[Miles, generated by tools/smallcaps-signals.py test. Ground truth: the vision readings of the Svisa Espero "
                "name snippets; Tesseract's text of the same snippet is what is tested.]`\n\n")
        # HEAVY: a garble less than 0.7 like the name (case and accents folded) — what small capitals do («BoxxeHox» for
        # Bonnehon, «Fnrrscur» for Fritschi); a LIGHT one is a letter or an accent (the Esperanto model reads è as ĉ:
        # «Vieux-Collĉge», «Thiĉbaud»; ü as ii). The vision readers write small capitals in ordinary case, so case tells nothing
        def like(t, nm):
            c = max((m.group(0) for m in WORD.finditer(t)), key=len, default="")
            return difflib.SequenceMatcher(None, fold(c), fold(nm)).ratio()
        P["HEAVY"] = [x for x in P["GARBLED"] if like(x[0], x[1]) < 0.7]
        n = {k: len(v) for k, v in P.items()}
        w.write(f"Names in the vision readings paired with Tesseract's word: **{n['GARBLED']} garbled**, {n['READ RIGHT']} read "
                f"right. Of the garbled, **{n['HEAVY']} are heavy** (less than 0.7 like the name: what small capitals "
                f"do); the rest are a letter or an accent. Ordinary words read right (the false-alarm base): {n['ORDINARY']}.\n\n"
                "| sign | heavy garbles it catches | all garbled names it catches | names read right it flags | "
                "ordinary words it flags |\n|---|---|---|---|---|\n")
        rows = S + ["any of the five", "any but CLUSTER", "TELL or MIDCAP or X"]
        def hit(s, r):
            return (r in s if r in S else bool(s) if r == "any of the five" else bool(s - {"CLUSTER"}) if r == "any but CLUSTER"
                    else bool(s & {"TELL", "MIDCAP", "X"}))
        for r in rows:
            c = {k: sum(1 for x in v if hit(x[2], r)) for k, v in P.items()}
            w.write(f"| {r} | {c['HEAVY']} ({100 * c['HEAVY'] / max(1, n['HEAVY']):.0f}%) "
                    f"| {c['GARBLED']} ({100 * c['GARBLED'] / max(1, n['GARBLED']):.0f}%) | {c['READ RIGHT']} "
                    f"({100 * c['READ RIGHT'] / max(1, n['READ RIGHT']):.0f}%) | {c['ORDINARY']} "
                    f"({100 * c['ORDINARY'] / max(1, n['ORDINARY']):.1f}%) |\n")
        w.write("\n## The known garbles (`NAME-CROPS-EXPLORATION` § 1, R62)\n\n| Tesseract read | the name | signs |\n|---|---|---|\n")
        for t, nm, prev in (("ZavMExu~HOr", "ZAMENHOF", "Dro"), ("BoxxeHox", "BONNEHON", "MM."), ("TurixE.", "TRINE", "W."),
                            ("Fnrrscur,", "FRITSCHI", "G."), ("Ansocp,en", "ARNOLD", "F.-R."), ("MeEven,", "MEYER", "Sam."),
                            ("Boxsxeuos", "BONNEHON", ""), ("Rosiavx,", "ROSIAUX", "et"), ("O'Coxxok", "O'CONNOR", ""),
                            ("TuixE.", "TRINE", "W."), ("Farrscui,", "FRITSCHI", "G.")):
            w.write(f"| {t} | {nm} | {', '.join(sorted(sig.of(t, prev))) or '— none'} |\n")
        w.write("\n## Garbled names no sign catches\n\n")
        miss = [x for x in P["HEAVY"] if not x[2]]
        w.write(f"Heavy, {len(miss)} of {n['HEAVY']}:\n\n" + "".join(f"- «{t}» for {nm} ({wh})\n" for t, nm, _, wh in miss[:150]))
        w.write("\n## Garbled names caught, a sample\n\n" + "".join(
            f"- «{t}» for {nm}: {', '.join(sorted(s))} ({wh})\n" for t, nm, s, wh in [x for x in P["GARBLED"] if x[2]][:60]))
        w.write("\n## Ordinary words flagged, a sample\n\n" + "".join(
            f"- «{t}»: {', '.join(sorted(s))} ({wh})\n" for t, _, s, wh in [x for x in P["ORDINARY"] if x[2]][:60]))
    print(f"garbled {n['GARBLED']}, read right {n['READ RIGHT']}, ordinary {n['ORDINARY']} → {a.out}")


# THE SWAPS: from the heavy garbles, the letter Tesseract wrote against the letter printed, both folded, where the two
# words are the same length or a stretch of them is
def swaps(P):
    c = collections.Counter()
    for t, nm, _, _ in P["HEAVY"]:
        a_ = fold(max((m.group(0) for m in WORD.finditer(t)), key=len, default="")); b_ = fold(nm)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a_, b_).get_opcodes():
            if op == "replace" and i2 - i1 == j2 - j1:
                c.update(zip(a_[i1:i2], b_[j1:j2]))
    return {k for k, v in c.items() if v >= 3 and k[0] != k[1]}, c


def wdist(a_, b_, sw, cap=9.0):
    """edit distance, a swap of the table a quarter; over the longer word's length. Gives up (returns 9) once every cell
    of a row is over cap × length: the corpus has millions of distinct garbles, the roster thousands of forms"""
    L = max(len(a_), len(b_), 1); lim = cap * L
    prev = list(range(len(b_) + 1))
    for i, x in enumerate(a_, 1):
        cur = [i]
        for j, y in enumerate(b_, 1):
            sub = 0 if x == y else 0.25 if (x, y) in sw else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + sub))
        if min(cur) > lim: return 9
        prev = cur
    return prev[-1] / L


def roster_forms(path):
    by = collections.defaultdict(set)
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        for k, f in enumerate(l.rstrip("\n").split(" | ")):
            if k == 0 and re.fullmatch(r"[a-z0-9-]+", f) and "-" in f: continue   # the person's slug
            for w in re.findall(r"[^\W\d_]{4,}", f):
                w = fold(w); by[w[0]].add(w)
    return by


class Confuse:
    def __init__(self, sw, forms, lex):
        self.sw, self.forms, self.lex, self.cache, self.cap = sw, forms, lex, {}, 9.0

    def best(self, word):
        core = max((m.group(0) for m in WORD.finditer(word)), key=len, default=""); f = fold(core)
        if len(f) < 4 or f in self.lex or not core[:1].isupper(): return None
        if f not in self.cache:
            cands = [g for g in self.forms.get(f[0], ()) if abs(len(g) - len(f)) <= 3]
            self.cache[f] = min(((wdist(f, g, self.sw, self.cap), g) for g in cands), default=(9, ""))
        return self.cache[f]

    def hit(self, word):
        b = self.best(word); return bool(b) and 0 < b[0] <= 0.34


def default_roster():
    return sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")), key=os.path.getmtime)[-1]


def confuse(a):
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    sig = Signals(); P = pairs(sig)
    def like(t, nm):
        c = max((m.group(0) for m in WORD.finditer(t)), key=len, default="")
        return difflib.SequenceMatcher(None, fold(c), fold(nm)).ratio()
    P["HEAVY"] = [x for x in P["GARBLED"] if like(x[0], x[1]) < 0.7]
    sw, cnt = swaps(P); rp = a.roster or default_roster()
    C = Confuse(sw, roster_forms(rp), sig.lex)
    closed = collections.defaultdict(set)   # the ceiling: the snippet readings' own names as the roster
    for x in P["GARBLED"] + P["READ RIGHT"]:
        for w in re.findall(r"[^\W\d_]{4,}", x[1]): closed[fold(w)[0]].add(fold(w))
    CC = Confuse(sw, closed, sig.lex)
    with open(a.out, "x", encoding="utf-8") as w:
        w.write("# Small-capital swaps: a garble compared with the roster (2026-10-25)\n\n`[Miles, generated by "
                f"tools/smallcaps-signals.py confuse; roster {os.path.relpath(rp, G)}.]`\n\n")
        w.write("## The swaps (Tesseract's letter → the printed letter, 3+ times in the heavy garbles)\n\n" + ", ".join(
            f"{x}→{y} {cnt[(x, y)]}" for (x, y) in sorted(sw, key=lambda k: -cnt[k])) + "\n\n")
        for lab, M in (("the roster", C), ("the snippets' own names (the ceiling)", CC)):
            res = collections.Counter(); found = []
            for t, nm, s_, wh in P["HEAVY"]:
                b = M.best(t)
                if not b: res["not tested (in a word list, under 4 letters, or lower-case first)"] += 1; continue
                if M.hit(t):
                    res["flagged"] += 1; res["flagged, not caught by the other signs"] += not s_
                    if b[1] == fold(max(re.findall(r"[^\W\d_]{3,}", nm) or [nm], key=len)): res["flagged, the right name"] += 1; found.append((t, nm, b))
                else: res["not flagged"] += 1
            rr = sum(1 for t, nm, _, _ in P["READ RIGHT"] if M.hit(t))
            w.write(f"## Against {lab}\n\nHeavy garbles {len(P['HEAVY'])}: " + "; ".join(f"{k} {v}" for k, v in res.items())
                    + f".\nNames read right that it flags (a near roster neighbour): {rr} of {len(P['READ RIGHT'])}.\n\n"
                    + "".join(f"- «{t}» → {b[1]} ({b[0]:.2f}), printed {nm}\n" for t, nm, b in found[:40]) + "\n")
    print(f"swaps {len(sw)}; → {a.out}")


def pages(a):
    if os.path.exists(a.out) and not a.resume: sys.exit(f"refusing: {a.out} exists (give --resume)")
    os.makedirs(a.out, exist_ok=True)
    sig = Signals(); P = pairs(sig)
    P["HEAVY"] = [x for x in P["GARBLED"] if difflib.SequenceMatcher(None, fold(max((m.group(0) for m in WORD.finditer(x[0])),
                  key=len, default="")), fold(x[1])).ratio() < 0.7]
    C = Confuse(swaps(P)[0], roster_forms(a.roster or default_roster()), sig.lex); C.cap = 0.34   # only «within 0.34» matters here
    led = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-ABSENCE-LEDGER-20*.tsv")), key=os.path.getmtime)[-1]
    items = [x[0] for x in (l.rstrip("\n").split("\t") for l in open(led, encoding="utf-8") if not l.startswith("#"))
             if len(x) > 1 and x[1].isdigit() and int(x[1]) > 0]
    if a.items:   # --items <file> (2026-10-26, run sheet C7b.2a «Not built yet» (1)): a batch's items only, one a line
        want = {unicodedata.normalize("NFC", l.strip()) for l in open(a.items, encoding="utf-8") if l.strip()}
        items = [x for x in items if unicodedata.normalize("NFC", x) in want]
        if not items: sys.exit(f"--items: none of {a.items} is in the ledger {os.path.basename(led)}")
    if a.sample: items = items[::max(1, len(items) // a.sample)][:a.sample]   # a timing run
    if a.shard:   # --shard k/n: every n-th item from the k-th, so n runs share the corpus (their PAGES.tsv joined after)
        k_, n_ = (int(v) for v in a.shard.split("/")); items = items[k_::n_]
    cyr = {(x[0], int(x[1])) for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(G, "ocr", "runs",
           "OCR-BISCRIPT-LATIN-CENSUS-2026-10-24d.tsv"), encoding="utf-8") if not l.startswith("#")) if len(x) > 1 and x[1].isdigit()}
    pf = os.path.join(a.out, "PAGES.tsv")
    done = {l.split("\t", 1)[0] for l in open(pf, encoding="utf-8")} if os.path.exists(pf) else set()
    R = os.path.join(G, "sources", "ocr-rendersearch"); PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
    memo = {}
    # UNROSTERED (the editor 2026-10-25 12:1x: «20 or even 10 words after a title UNRECOGNISED in our rosters, which are
    # pretty big by now, and 20 tier-1 words»): a word after a title whose every 4+-letter part matches no roster form
    # exactly (case and accents folded): a name we do not know, or a known name garbled out of recognition
    rost = set().union(*C.forms.values())
    def unrostered(tok):
        parts = [fold(w) for w in re.findall(r"[^\W\d_]{4,}", tok)]
        return bool(parts) and not any(w in rost for w in parts)
    def signs(tok, after):
        k = (tok, after)
        if k not in memo:
            s_ = sig.of(tok, True if after else "")
            if "TITLED" in s_ and unrostered(tok): s_.add("UNROSTERED")
            b = C.best(tok)
            if b and 0 < b[0] <= 0.34: s_.add("CONFUSE")
            if b and 0 < b[0] <= 0.2: s_.add("CONFUSE2")
            memo[k] = s_
        return memo[k]
    t0 = time.time()
    with open(pf, "a", encoding="utf-8") as w:
        if not done: w.write("item\tpage\twords\ttell\tany\tany-but-after\tflagged words\tsigns of each (T telltale, M capital "
                             "inside, X x, C cluster, A after a title, F roster ≤0.34, G roster ≤0.2)\n")
        for n_, it in enumerate(items):
            if it in done: continue
            f = os.path.join(R, it + ".txt")
            if not os.path.exists(f): continue
            pre = os.path.join(R, it, "PREFERRED.tsv"); frk = set()
            if os.path.exists(pre):
                for l in open(pre, encoding="utf-8"):
                    x = l.rstrip("\n").split("\t")
                    if x[0].isdigit() and len(x) > 4 and x[4].startswith("frk"): frk.add(int(x[0]))
            parts = PAGE.split(open(f, encoding="utf-8", errors="ignore").read())
            for i in range(1, len(parts) - 1, 2):
                p = int(parts[i])
                if (it, p) in cyr or p in frk: continue
                toks = parts[i + 1].split(); fl = []; tell = 0; nb = 0; codes = []; tr = title_run(toks)
                for k, t in enumerate(toks):
                    after = tr[k]
                    s_ = signs(t, after)
                    if s_:
                        fl.append(t); tell += "TELL" in s_; nb += bool(s_ - {"AFTER"}); codes.append(code(s_))
                w.write(f"{it}\t{p}\t{len(toks)}\t{tell}\t{len(fl)}\t{nb}\t{' '.join(fl[:40])}\t{' '.join(codes)}\n")
            w.flush()
            open(os.path.join(a.out, "PROGRESS.txt"), "w").write(f"{n_ + 1} of {len(items)} items, {time.time() - t0:.0f} s, {time.strftime('%H:%M:%S')}\n")
    summary(a.out)


CODE = {"TELL": "T", "MIDCAP": "M", "X": "X", "CLUSTER": "C", "AFTER": "A", "CONFUSE": "F", "CONFUSE2": "G", "TITLED": "N", "UNROSTERED": "U"}


def code(s_):
    return "".join(sorted(CODE[k] for k in s_))


# THE TIERS (the editor 2026-10-25 01:0x: «this is meant to be triage … we reserve the right to incrementally loose[n] the
# criteria for small cap detection»): a word's signs as codes; tier 1 the strictest. A word is in a tier if it is in the
# one before or meets its own test; a page is picked by its count of words in the tier.
STRONG = set("TMXCG")
_T = [
    ("1: two strong signs (telltale, capital inside, x, cluster, roster ≤0.2)", lambda c: len(set(c) & STRONG) >= 2),
    ("2: + a strong sign after a title or initial", lambda c: len(set(c) & STRONG) >= 1 and "A" in c),
    ("3: + a roster neighbour ≤0.34 after a title or initial", lambda c: "F" in c and "A" in c),
    ("4: + a strong sign alone", lambda c: len(set(c) & STRONG) >= 1),
    ("5: + any sign", lambda c: bool(c)),
]
# cumulative: tier k takes every word of the tiers before it
TIERS = [(lab, (lambda k: lambda c: any(f(c) for _, f in _T[:k + 1]))(k)) for k, (lab, _) in enumerate(_T)]


def tier_predicate(n, roster=None):
    """word, previous word → in tier n? For the cutter (ocr-name-crops.py --tier); the swaps learnt from the test's pairs"""
    sig = Signals(); P = pairs(sig)
    P["HEAVY"] = [x for x in P["GARBLED"] if difflib.SequenceMatcher(None, fold(max((m.group(0) for m in WORD.finditer(x[0])),
                  key=len, default="")), fold(x[1])).ratio() < 0.7]
    C = Confuse(swaps(P)[0], roster_forms(roster or default_roster()), sig.lex); C.cap = 0.34
    f = TIERS[n - 1][1]; memo = {}
    def pred(t, prev):
        after = prev is True or (isinstance(prev, str) and bool(NC.TITLE.match(prev.strip()) or INITIALS.match(prev.strip())
                                                                or TITLES.match(prev.strip())))
        k = (t, after)
        if k not in memo:
            s_ = sig.of(t, True if after else ""); b = C.best(t)
            if b and 0 < b[0] <= 0.34: s_.add("CONFUSE")
            if b and 0 < b[0] <= 0.2: s_.add("CONFUSE2")
            memo[k] = f(code(s_)) and not cyr_word(t)
        return memo[k]
    pred.title_run = title_run   # the cutter marks a line's runs of names with it
    return pred


# CYRILLIC READ AS LATIN (2026-10-25 10:4x, measured on 359 pages of Ruslanda Esperantisto and La Ondo with Russian
# advertisements against 2,343 Latin pages of the British Esperantist, Svisa Espero, Franca Esperantisto, the Belga
# Sonorilo, Internacia Scienca Revuo and La Revuo): ы as «bI», ь after a capital as a final «b», «HH», «XB»/«BX», a vowel
# then «H», «Hb», й as a final «Ĥ»/«ĥ»/«Ĵ». A page with 8+ such words: 56% of the Cyrillic pages, 1% of the Latin ones
# (at 5+: 69% and 5%); the first tries matched «MEMBERS», «verb», «witb» and small-capital «BansHAH», and were dropped.
CYR = re.compile(r"bI|[A-Z]b$|HH|XB|BX|[aeiopy]H|Hb|[ĤĥĴ]$")


def cyr_word(t):
    return bool(CYR.search(re.sub(r"[^\w]", "", t)))


def select(a):
    """the pages a step picks: tier --tier, --min words or more, less the pages the register shows done"""
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    f = TIERS[a.tier - 1][1]
    reg = os.path.join(G, "ocr", "VISION-REGISTER.tsv"); done = {}
    for l in open(reg, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 4 and x[1].isdigit() and x[2] in ("vision", "hand", "names"): done[(x[0], int(x[1]))] = x[2] + (" " + x[3] if x[3] else "")
    # BORN-DIGITAL pages (their own text layer is the printed text, `ocr-rebuild-combined.py`'s rule): nothing to read
    # by vision; their flags are the layer's own spellings (the Berlina Komentario, the ŜTABA almanac)
    born = set()
    tk = os.path.join(G, "sources", "ocr-text-layer-2026-09-30", "tl-kind.tsv")
    for l in open(tk, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        try:
            if len(x) >= 4 and float(x[3]) < 0.5: born.add((x[0], int(x[1])))
        except ValueError: pass
    out, skipped = [], collections.Counter()
    R_ = os.path.join(G, "sources", "ocr-rendersearch"); PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M); texts = {}
    def page_text(it, p):
        if it not in texts:
            f_ = os.path.join(R_, it + ".txt"); d_ = {}
            if os.path.exists(f_):
                parts = PAGE.split(open(f_, encoding="utf-8", errors="ignore").read())
                d_ = {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}
            texts.clear(); texts[it] = d_
        return texts[it].get(p, "")
    rows_ = [x for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(a.dir, "PAGES.tsv"), encoding="utf-8"))
             if x[0] != "item" and len(x) >= 8]
    rows_.sort(key=lambda x: (x[0], int(x[1])))
    for x in rows_:
        ws_, cs_ = x[6].split(), x[7].split()   # the words are kept for the first 40 flagged; a Cyrillic one is no snippet
        n = sum(1 for i, c in enumerate(cs_) if f(c) and not (i < len(ws_) and cyr_word(ws_[i])))
        if n < a.min: continue
        u = sum(1 for c in cs_ if "U" in c)
        if a.whole_unrostered and u < a.whole_unrostered: continue   # round 1b: dense pages, read whole
        k = (x[0], int(x[1]))
        # CYRILLIC READ AS LATIN on a page the Russian step did not mark (Ruslanda Esperantisto's and La Ondo's Russian
        # advertisements, «XYpHanb», «MOCxKBa»): 8+ such words on the page (CYR, above)
        if sum(1 for t in page_text(*k).split() if cyr_word(t)) >= 8:
            skipped["Cyrillic read as Latin"] += 1; continue
        # a page read whole by vision or keyed by hand: never; snippeted «every candidate» (the 2026-10-24 runs, wider than
        # any tier) or at this tier or a looser one: not again
        if k in done and not (a.whole_unrostered and done[k].startswith("names")):   # snippets do not stop a whole read
            skipped[done[k].split()[0]] += 1; continue
        if k in born: skipped["born-digital"] += 1; continue
        out.append((x[0], int(x[1]), n, u))
    with open(a.out, "x", encoding="utf-8") as w:
        w.write(f"# tier {a.tier}, pages with {a.min}+ words" + (f" and {a.whole_unrostered}+ words after a title on no roster (to be read WHOLE)" if a.whole_unrostered else "") + f": {len(out):,} pages, {sum(r[2] for r in out):,} words in the tier; "
                f"left out as done (VISION-REGISTER): " + ", ".join(f"{k} {v}" for k, v in skipped.items()) + "\n")
        w.write("item\tpage\twords in the tier\twords after a title on no roster\n"); w.writelines(f"{i}\t{p}\t{n}\t{u}\n" for i, p, n, u in out)
    print(f"{len(out):,} pages, {sum(r[2] for r in out):,} words; skipped {dict(skipped)} → {a.out}")


def tiers(a):
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    d = a.dir; rows = []
    for l in open(os.path.join(d, "PAGES.tsv"), encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if x[0] != "item" and len(x) >= 8: rows.append((x[0], int(x[1]), x[7].split()))
    led = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-ABSENCE-LEDGER-20*.tsv")), key=os.path.getmtime)[-1]
    total = sum(int(x[1]) for x in (l.rstrip("\n").split("\t") for l in open(led, encoding="utf-8") if not l.startswith("#"))
                if len(x) > 1 and x[1].isdigit())
    scale = total / max(1, len(rows))
    sig = Signals(); P = pairs(sig)
    P["HEAVY"] = [x for x in P["GARBLED"] if difflib.SequenceMatcher(None, fold(max((m.group(0) for m in WORD.finditer(x[0])),
                  key=len, default="")), fold(x[1])).ratio() < 0.7]
    sw = swaps(P)[0]; C = Confuse(sw, roster_forms(a.roster or default_roster()), sig.lex)
    def codes_of(t, prev):
        s_ = sig.of(t, prev); b = C.best(t)
        if b and 0 < b[0] <= 0.34: s_.add("CONFUSE")
        if b and 0 < b[0] <= 0.2: s_.add("CONFUSE2")
        return code(s_)
    # the test's pairs carry their own signs without the roster; recompute with it (the previous word is not kept: the
    # after-a-title sign as the test found it)
    hv = [codes_of(t, "J." if "AFTER" in s_ else "") for t, _, s_, _ in P["HEAVY"]]
    rr = [codes_of(t, "J." if "AFTER" in s_ else "") for t, _, s_, _ in P["READ RIGHT"]]
    od = [codes_of(t, "J." if "AFTER" in s_ else "") for t, _, s_, _ in P["ORDINARY"]]
    with open(a.out, "x", encoding="utf-8") as w:
        w.write(f"# Small-capital triage: tiers, their catch and their cost ({time.strftime('%Y-%m-%d')})\n\n`[Miles, generated by "
                f"tools/smallcaps-signals.py tiers from {os.path.relpath(d, G) if d.startswith(G) else d}/PAGES.tsv: {len(rows):,} "
                f"sample pages, scaled to the {total:,} signed pages of the ledger (×{scale:.0f}). A word in a tier is one snippet "
                "(an upper bound). Cost: 40 snippets a sheet, 5,300 tokens a sheet, 1% of a week ≈ 1.7 M tokens.]`\n\n"
                "| tier | heavy garbles caught (test) | names read right flagged | ordinary words flagged | pages picked (1+ word), "
                "corpus | snippets, corpus | week's share | pages with 3+ words | snippets on them | week's share |\n"
                "|---|---|---|---|---|---|---|---|---|---|\n")
        for lab, f in TIERS:
            pg1 = sum(1 for _, _, cs in rows if any(f(c) for c in cs)); sn1 = sum(sum(1 for c in cs if f(c)) for _, _, cs in rows)
            r3 = [cs for _, _, cs in rows if sum(1 for c in cs if f(c)) >= 3]; sn3 = sum(sum(1 for c in cs if f(c)) for cs in r3)
            wk = lambda n: f"{n * scale / 40 * 5300 / 1.7e6:.1f}%"
            w.write(f"| {lab} | {sum(map(f, hv))} of {len(hv)} ({100 * sum(map(f, hv)) / max(1, len(hv)):.0f}%) | "
                    f"{100 * sum(map(f, rr)) / max(1, len(rr)):.0f}% | {100 * sum(map(f, od)) / max(1, len(od)):.1f}% | "
                    f"{pg1 * scale:,.0f} ({100 * pg1 / max(1, len(rows)):.0f}%) | {sn1 * scale:,.0f} | {wk(sn1)} | "
                    f"{len(r3) * scale:,.0f} | {sn3 * scale:,.0f} | {wk(sn3)} |\n")
        cnt = collections.Counter(c for _, _, cs in rows for c in cs)
        w.write("\n## The commonest sign combinations on the sample pages\n\n| signs | words |\n|---|---|\n" +
                "".join(f"| {k} | {v:,} |\n" for k, v in cnt.most_common(25)))
    print(f"{len(rows)} sample pages → {a.out}")


def threshold(a):
    """the pages read whole by vision (page-NNNN.vision.txt): the names the vision reading has and the page's OCR readings
    lack, against what the signs count on the OCR reading. Which count, at what level, picks the pages that lose names?"""
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    sig = Signals(); de = sig.de
    rost = set().union(*roster_forms(a.roster or default_roster()).values())
    R_ = os.path.join(G, "sources", "ocr-rendersearch"); rows = []
    for vf in glob.glob(os.path.join(R_, "*", "page-*.vision.txt")):
        it = os.path.basename(os.path.dirname(vf)); stem = vf[:-len(".vision.txt")]
        ocr = ""
        for ext in (".txt", ".psm4.txt", ".sc3x.txt", ".cols.txt", ".blocks.txt", ".layout.txt"):
            if os.path.exists(stem + ext): ocr += "\n" + open(stem + ext, encoding="utf-8", errors="ignore").read()
        if not ocr.strip(): continue
        have = {fold(w) for w in re.findall(r"[^\W\d_]{3,}", ocr)}
        vis = open(vf, encoding="utf-8", errors="ignore").read()
        names = {w for w in re.findall(r"\b[A-ZÀ-ÞĈĜĤĴŜŬ][^\W\d_]{3,}", vis) if fold(w) not in sig.lex and not NC.german(de, w)}
        lost = [w for w in names if fold(w) not in have]
        toks = ocr.split(); tr = title_run(toks); t1 = tn = ta = tu = 0
        for k, t in enumerate(toks):
            s_ = sig.of(t, True if tr[k] else "")
            c = set(code(s_)); t1 += len(c & STRONG) >= 2; tn += "N" in c; ta += "A" in c
            parts = [fold(w) for w in re.findall(r"[^\W\d_]{4,}", t)]
            tu += "N" in c and bool(parts) and not any(w in rost for w in parts)
        rows.append((it, os.path.basename(stem), len(names), len(lost), t1, tn, ta, tu))
    with open(a.out, "x", encoding="utf-8") as w:
        w.write(f"# Small capitals: which pages to read whole? ({time.strftime('%Y-%m-%d')})\n\n`[Miles, generated by "
                "tools/smallcaps-signals.py threshold. The pages already read whole by vision (page-NNNN.vision.txt): names "
                "(capitalised, 4+ letters, in no word list, no German compound) in the vision reading that none of the page's "
                "OCR readings has, against the signs counted on the OCR readings.]`\n\n"
                f"Pages: {len(rows):,}; names lost by the OCR on them: {sum(r[3] for r in rows):,}.\n\n")
        for lab, col in (("tier-1 words", 4), ("words after a title (any capitalised word in a run of names)", 5),
                         ("words after a title on no roster", 7)):
            w.write(f"## By {lab} on the page\n\n| {lab} | pages | names lost (mean a page) | pages losing 3+ names | "
                    "share of all lost names |\n|---|---|---|---|---|\n")
            tot = max(1, sum(r[3] for r in rows))
            for lo, hi in ((0, 0), (1, 2), (3, 4), (5, 9), (10, 19), (20, 39), (40, 10 ** 6)):
                b = [r for r in rows if lo <= r[col] <= hi]
                if not b: continue
                w.write(f"| {lo}{'+' if hi > 10 ** 5 else ('' if lo == hi else '–' + str(hi))} | {len(b):,} | "
                        f"{sum(r[3] for r in b) / len(b):.1f} | {sum(1 for r in b if r[3] >= 3):,} | {100 * sum(r[3] for r in b) / tot:.0f}% |\n")
            w.write("\n")
        # the editor's two conditions together (12:1x): T+ unrostered words after a title and 20+ tier-1 words
        w.write("## Both: words after a title on no roster, and tier-1 words\n\n| on no roster | tier-1 | pages | names lost "
                "(mean a page) | share of all lost names |\n|---|---|---|---|---|\n")
        tot = max(1, sum(r[3] for r in rows))
        for T in (10, 20):
            for K in (10, 20):
                b = [r for r in rows if r[7] >= T and r[4] >= K]
                if b: w.write(f"| {T}+ | {K}+ | {len(b):,} | {sum(r[3] for r in b) / len(b):.1f} | {100 * sum(r[3] for r in b) / tot:.0f}% |\n")
    print(f"{len(rows)} pages → {a.out}")


def summary(d):
    rows = [x for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(d, "PAGES.tsv"), encoding="utf-8")) if x[0] != "item"]
    rows = [(x[0], int(x[1]), int(x[2]), int(x[3]), int(x[4]), int(x[5])) for x in rows if len(x) >= 6]
    tab = {r["item"]: r for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8")
                                                 if not l.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE)}
    title = lambda it: (tab.get(it, {}).get("title") or tab.get(it, {}).get("title_key") or it)
    def cost(snips):
        sh = snips / 40; return f"{sh:,.0f} sheets, {sh * 5300 / 1e6:.1f} M tokens, {sh * 5300 / 1.7e6:.1f}% of a week"
    with open(os.path.join(d, "SUMMARY.md"), "w", encoding="utf-8") as w:
        w.write(f"# Small-capital signs over the signed corpus: pages and cost ({time.strftime('%Y-%m-%d')})\n\n`[Miles, generated by "
                "tools/smallcaps-signals.py pages. Cyrillic and Fraktur pages left out. A flagged word is taken as one snippet "
                "(an upper bound: the cutter joins neighbours on a line). Cost: 40 snippets a sheet, 5,300 tokens a sheet, 1% of "
                "a week ≈ 1.7 M tokens.]`\n\n")
        w.write(f"Pages: {len(rows):,}. Words: {sum(r[2] for r in rows):,}.\n\n| a page is picked when it has | pages | snippets "
                "on them (any sign) | cost | snippets without the after-a-title sign | cost |\n|---|---|---|---|---|---|\n")
        for m in (1, 2, 3, 5, 10):
            pk = [r for r in rows if r[4] >= m]; s1 = sum(r[4] for r in pk); s2 = sum(r[5] for r in pk)
            w.write(f"| {m}+ flagged words | {len(pk):,} ({100 * len(pk) / max(1, len(rows)):.0f}%) | {s1:,} | {cost(s1)} | {s2:,} | {cost(s2)} |\n")
        cen = [r for r in rows if r[3] >= 3]; rest = [r for r in rows if r[3] < 3]
        w.write(f"\nThe telltale census's kind of page (3+ telltale words): {len(cen):,} pages, {sum(r[4] for r in cen):,} flagged "
                f"words. The rest: {len(rest):,} pages, of them {sum(1 for r in rest if r[4] >= 3):,} with 3+ flagged words.\n\n")
        bt = collections.defaultdict(lambda: [0, 0, 0])
        for r in rows:
            t = bt[title(r[0])]; t[0] += 1; t[1] += r[4]; t[2] += r[4] >= 3
        w.write("## By title, most flagged words first\n\n| title | pages | flagged words | per 100 pages | pages with 3+ |\n|---|---|---|---|---|\n")
        for t, (pg, fw, p3) in sorted(bt.items(), key=lambda kv: -kv[1][1])[:60]:
            w.write(f"| {t} | {pg:,} | {fw:,} | {100 * fw / max(1, pg):.0f} | {p3:,} |\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("test", "confuse", "pages", "tiers", "select", "threshold")); ap.add_argument("--out", required=True)
    ap.add_argument("--tier", type=int, default=1); ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--whole-unrostered", type=int, help="select: also N+ words after a title on no roster: pages to read WHOLE (round 1b)")
    ap.add_argument("--dir", help="tiers: a pages run's folder")
    ap.add_argument("--roster"); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--sample", type=int, help="pages: every n-th item only, this many (a timing run)")
    ap.add_argument("--items", help="pages: a file of item names, one a line (a batch's ITEMS.txt): those items only")
    ap.add_argument("--shard", help="pages: k/n, every n-th item from the k-th (n runs in parallel; join their PAGES.tsv)")
    a = ap.parse_args(); {"test": test, "confuse": confuse, "pages": pages, "tiers": tiers, "select": select, "threshold": threshold}[a.mode](a)


if __name__ == "__main__":
    main()
