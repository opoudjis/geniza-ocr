#!/usr/bin/env python3
r"""ocr-garbage-filter — two clean single-language texts from the two readings of a bi-script page.

    tools/ocr-garbage-filter.py train <root> <gate.json> <model-dir>     # build + measure the models
    tools/ocr-garbage-filter.py apply <root> <model-dir> [--tau 0]       # write the clean files

PLAN: an internal record, 2026-09-27, not published (approved by the editor, 2026-09-27 12:17).

A page printed in Russian AND Esperanto has two readings: the Esperanto one gets the Esperanto right
and turns the Russian into Latin-letter junk; the Russian one gets the Russian right and turns the
Esperanto into Cyrillic junk. Nothing is merged. EACH READING IS CLEANED OF THE OTHER SCRIPT'S JUNK.

MODELS (character n-grams, orders 1–4, interpolated), four of them, all from text already on disk:
  ru     — lines of the Russian reading of the pages ACCEPTED whole as Russian (RUSSIAN.json «accept»)
           that are >= 90% Cyrillic; pre-1918 spelling included, which is why no dictionary will do
  jcyr   — the Russian reading of pages that FAIL the page gate (Esperanto pages read as Russian)
  eo     — lines of the combined text of passing items with median G4 >= 90, >= 70% of words in
           the Latin lists, no bi-script page
  jlat   — the Esperanto reading of pages accepted whole as Russian (Russian read as Latin letters),
           lines with under 30% of words in the Latin lists
A word is scored by its per-character log-likelihood ratio, own language vs junk; the score is
decided on its own if |score| >= 0.5 per character, else by the length-weighted mean over five words;
words scoring above tau are kept. Words are split at «|» (the column rule, read with no space round it).
FIX (b), 2026-09-27: on the Esperanto side a word is also KEPT if it is in any Latin-script list we hold
(13 languages) and has 4+ letters, or is a capitalised name of 4+ letters scoring above 0 on its own (neighbours ignored) —
the clean-readings look found names and non-Esperanto words dropped on Russian-heavy pages. Lines
left with no letters are dropped.

INPUTS per bi-script page (LAYOUT.json: >= 3 Russian lines, under 90% of lines Russian):
  Esperanto: the combined text's page if the page was NOT swapped whole to Russian; otherwise the
             Esperanto reading `page-NNNN.txt`.
  Russian:   `page-NNNN.rus.txt`.
OUTPUTS beside them: `page-NNNN.eo-clean.txt`, `page-NNNN.ru-clean.txt` (READING AID); `page-NNNN.eo-gate.txt`
(GATE MODE, 2026-09-27 fix (3): only words clearly junk on their own score are dropped, never by neighbour
vote, so the G4 of `ocr-accept.py --script-segregated` can understate but not flatter); per item `CLEAN.json`.
FIXES (1)(2), 2026-09-27: ALL-CAPS words judged by their Title-case form (kept if > 0 and as-is > -2.0);
an initial («D.», «Rusl.») kept before a kept name.
Nothing existing is touched: the Esperanto combined text stays the canonical and citation text.
CAVEATS (editor, 2026-09-27): the clean files are a READING AID and the input to script-segregated
G4 scoring — never canonical, never cited, never searched for ABSENCE (search the full text). They drop
some real Latin-script words (two blind looks: 33·10·1 and 29·13·2 against raw), so a G4 on them can
slightly flatter.
"""
import os, re, sys, glob, json, math, zlib, random, collections, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ml", os.path.join(HERE, "ocr-mixed-lines.py"))
ml = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ml)
sys.path.insert(0, HERE)
import ocr_russian_reading as RR   # the old-letter rule: `orus` or `rus` per page
LET = re.compile(r"[^\W\d_]")
N = 4
LAMBDA = (0.1, 0.2, 0.3, 0.4)
CAP = 120_000  # training lines per model
STRONG = 0.5   # |per-character LLR| at or above which a word is decided on its own score
NAME_FLOOR = 0.0   # a capitalised name-shaped word keeps its OWN verdict (> 0), whatever its neighbours say — measured
                   # 2026-09-27: 18 real names +0.04…+3.04, 18 junk words −0.12…−2.06; names were lost to SMOOTHING, not to their scores
LEXDIR = os.path.join(HERE, "lexicons")
_REAL = {}


def real_latin():
    """every word of every Latin-script list we hold — a real word in any of them is never junk
    (fix (b), editor 2026-09-27 13:08: the clean-readings look dropped names and non-Esperanto words)"""
    if not _REAL:
        s = set()
        for f in glob.glob(os.path.join(LEXDIR, "*.txt")):
            if "russian" in os.path.basename(f):
                continue
            s |= {w.strip().lower() for w in open(f, encoding="utf-8", errors="ignore") if w.strip()}
        _REAL["s"] = s
    return _REAL["s"]


NAME = re.compile(r"^[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬŁŚŹŻČŠŽ][a-zß-öø-ÿĉĝĥĵŝŭłśźżčšžěřůáéíóúý]{3,}$")
CAPS = re.compile(r"^[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬŁŚŹŻČŠŽ]{3,}(?:-[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬŁŚŹŻČŠŽ]{2,})*$")
INITIAL = re.compile(r"^[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬŁŚŹŻČŠŽ][a-zß-ÿĉĝĥĵŝŭ]?\.$")
CAPS_FLOOR = -2.0   # an ALL-CAPS word is kept if its Title-case form scores > 0 AND its as-is score is above this
                    # (measured 2026-09-27: 14 caps names — 13 kept, HORBYK lost; 14 caps Cyrillic junk — 14 dropped)


def protected_latin(tok, llr, own=None, junk=None):
    core = tok.strip(".,;:!?«»„“”\"'()[]—–-")
    if own is not None and CAPS.match(core) and llr > CAPS_FLOOR:
        t = "-".join(w.title() for w in core.split("-"))
        if own.logp(t) - junk.logp(t) > 0:   # fix (1): capitals judged by their Title-case form
            return True
    if len(core) >= 4 and core.lower() in real_latin():   # short junk is often a real word somewhere («Ero» ← его)
        return True
    return bool(NAME.match(core)) and llr > NAME_FLOOR


def held_out(line):
    return zlib.crc32(line.encode("utf-8")) % 10 == 0


class Model:
    def __init__(self):
        self.c = [collections.Counter() for _ in range(N + 1)]
        self.ctx = [collections.Counter() for _ in range(N + 1)]
        self.v = set()

    def add(self, tok):
        s = "^" + tok + "$"
        for ch in s:
            self.v.add(ch)
        for n in range(1, N + 1):
            for i in range(len(s) - n + 1):
                g = s[i:i + n]; self.c[n][g] += 1; self.ctx[n][g[:-1]] += 1

    def dump(self):
        return {"c": [dict(x) for x in self.c], "ctx": [dict(x) for x in self.ctx], "v": sorted(self.v)}

    @classmethod
    def load(cls, d):
        m = cls(); m.c = [collections.Counter(x) for x in d["c"]]; m.ctx = [collections.Counter(x) for x in d["ctx"]]
        m.v = set(d["v"]); return m

    def logp(self, tok):
        """mean log-probability per character of «^tok$»"""
        s = "^" + tok + "$"; V = len(self.v) + 1; tot = sum(self.c[1].values()); lp = 0.0
        for i in range(1, len(s)):
            p = LAMBDA[0] * (self.c[1][s[i]] + 1) / (tot + V)
            for n in range(2, N + 1):
                if i - n + 1 < 0:
                    break
                g = s[i - n + 1: i + 1]; cx = self.ctx[n][g[:-1]]
                if cx:
                    p += LAMBDA[n - 1] * self.c[n][g] / cx
            lp += math.log(p)
        return lp / (len(s) - 1)


def toks(line):
    """whitespace words, split again at «|»: the printed column rule, read with no space round it,
    glues a word of one column to the junk of the other"""
    return [t for w in line.split() for t in re.split(r"(?<=.)\|(?=.)", w) if t]


def lat_share(line, lat):
    ws = [m.group(0).lower() for m in ml.W.finditer(line)]
    return sum(w in lat for w in ws) / len(ws) if ws else None


def gate_share(text, ru):
    ws = [m.group(0) for m in ml.W.finditer(text)]
    return ml.ru_score(text, ru) / len(ws) if ws else 0.0


def combined_pages(root, stem):
    p = os.path.join(root, stem + ".txt")
    if not os.path.exists(p):
        return {}
    t = open(p, encoding="utf-8", errors="ignore").read()
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def accepted(root):
    acc = set()
    for f in glob.glob(os.path.join(root, "*", "RUSSIAN.json")):
        c = os.path.basename(os.path.dirname(f))
        acc |= {(c, p["page"]) for p in json.load(open(f))["pages"] if p["verdict"] == "accept"}
    return acc


def bi_pages(root):
    out = []
    for f in sorted(glob.glob(os.path.join(root, "*", "LAYOUT.json"))):
        c = os.path.basename(os.path.dirname(f))
        for p in json.load(open(f))["pages"]:
            if p.get("ru_lines", 0) >= 3 and p.get("lines") and p["ru_lines"] / p["lines"] < 0.9:
                out.append((c, p["page"]))
    # and every page of the GREEK-bearing items (the editor ruled on 2026-09-27 that Greek is treated like Armenian, presence only)
    have = set(out)
    for d in sorted(glob.glob(os.path.join(root, "HelenaEsperantisto*"))):
        if os.path.isdir(d):
            c = os.path.basename(d)
            for f in glob.glob(os.path.join(d, "page-*.txt")):
                m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
                if m and (c, int(m.group(1))) not in have:
                    out.append((c, int(m.group(1))))
    # and every page carrying Georgian or Armenian blocks (`tools/ocr-kat-hye.py`), editor 2026-09-27:
    # segregate those scripts from the Esperanto too, so the Esperanto text can be gated alone
    have = set(out)
    for f in sorted(glob.glob(os.path.join(root, "*", "page-*.kathye.json"))):
        r = json.load(open(f)); c = os.path.basename(os.path.dirname(f))
        if (r.get("kat_blocks") or r.get("hye_blocks")) and (c, r["page"]) not in have:
            out.append((c, r["page"]))
    return out


def lines_of(path):
    return [l for l in open(path, encoding="utf-8", errors="ignore").read().split("\n") if l.strip()]


def train(root, gate_json, mdir):
    lat, ru = ml.lists()
    acc = accepted(root); bi = set(c for c, _ in bi_pages(root))
    data = {k: [] for k in ("ru", "jcyr", "eo", "jlat")}
    for c, n in sorted(acc):
        d = os.path.join(root, c)
        rp, ep = os.path.join(d, f"page-{n:04d}.rus.txt"), os.path.join(d, f"page-{n:04d}.txt")
        if os.path.exists(rp):
            data["ru"] += [l for l in lines_of(rp) if len(toks(l)) >= 3 and ml.cyr_share(l) >= 0.9]
        if os.path.exists(ep):
            data["jlat"] += [l for l in lines_of(ep) if len(toks(l)) >= 2 and (lat_share(l, lat) or 0) < 0.3
                             and ml.cyr_share(l) < 0.1]
    for f in glob.glob(os.path.join(root, "*", "page-*.rus.txt")):
        c = os.path.basename(os.path.dirname(f)); n = int(re.search(r"page-(\d+)\.rus", f).group(1))
        if (c, n) in acc:
            continue
        t = open(f, encoding="utf-8", errors="ignore").read()
        if gate_share(t, ru) < 0.10:  # clearly no real Russian on the page
            data["jcyr"] += [l for l in t.split("\n") if len(toks(l)) >= 3 and ml.cyr_share(l) >= 0.6]
    g = json.load(open(gate_json)); good = [r["corpus"] for r in g if r["g4"] >= 90 and r["corpus"] not in bi]
    random.Random(27).shuffle(good)
    for c in good:
        if len(data["eo"]) >= CAP * 1.2:
            break
        for pg in combined_pages(root, c).values():
            data["eo"] += [l for l in pg.split("\n") if len(toks(l)) >= 4 and (lat_share(l, lat) or 0) >= 0.7]
    os.makedirs(mdir, exist_ok=True); report = {}
    models = {}
    for k, L in data.items():
        random.Random(27).shuffle(L)
        tr = [l for l in L if not held_out(l)][:CAP]; ho = [l for l in L if held_out(l)][:5000]
        m = Model()
        for l in tr:
            for t in toks(l):
                m.add(t)
        models[k] = m; report[k] = {"lines_all": len(L), "train": len(tr), "held_out": len(ho)}
        json.dump(m.dump(), open(os.path.join(mdir, k + ".json"), "w"))
        json.dump(ho, open(os.path.join(mdir, k + ".heldout.json"), "w"), ensure_ascii=False)
    # separation on held-out lines: word-level and line-level
    for own, junk, pos, neg in (("eo", "jlat", "eo", "jlat"), ("ru", "jcyr", "ru", "jcyr")):
        for kind in (pos, neg):
            ho = json.load(open(os.path.join(mdir, kind + ".heldout.json")))
            w_ok = w_n = l_ok = 0
            for l in ho:
                sc = [models[own].logp(t) - models[junk].logp(t) for t in toks(l) if LET.search(t)]
                if not sc:
                    continue
                want = kind == pos
                w_ok += sum((s > 0) == want for s in sc); w_n += len(sc)
                l_ok += ((sum(sc) / len(sc)) > 0) == want
            report[f"{own} vs {junk} on held-out {kind}"] = {
                "words_correct": round(w_ok / max(1, w_n), 4), "lines_correct": round(l_ok / max(1, len(ho)), 4),
                "lines": len(ho)}
    json.dump(report, open(os.path.join(mdir, "REPORT.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))


def clean(text, own, junk, tau, protect=None, strict=False):
    """strict=True (the GATE mode): a word is dropped only if its OWN score is below -STRONG — never by
    its neighbours — so junk is under-removed and a G4 scored on the result can understate, not flatter."""
    out, kept_w, drop_w = [], 0, 0
    for line in text.split("\n"):
        ts = toks(line)
        if not ts:
            continue
        sc = []
        for t in ts:
            if LET.search(t):
                sc.append((own.logp(t) - junk.logp(t), len(LET.findall(t))))
            else:
                sc.append(None)
        keep = []
        for i, t in enumerate(ts):
            win = [x for x in sc[max(0, i - 2): i + 3] if x]
            if strict:
                s = sc[i][0] + STRONG if sc[i] is not None else (1 if not win else sum(a * w for a, w in win) / sum(w for _, w in win))
            elif sc[i] is not None and abs(sc[i][0]) >= STRONG:
                s = sc[i][0]            # a clear word decides for itself; neighbours only settle borderline ones
            elif win:
                s = sum(a * w for a, w in win) / sum(w for _, w in win)
            else:
                s = -1
            keep.append(s > tau or (protect is not None and sc[i] is not None and protect(t, sc[i][0], own, junk)))
            if sc[i] is not None:
                kept_w += keep[-1]; drop_w += not keep[-1]
        for i in range(len(ts) - 1):   # fix (2): an initial before a kept name-like word is kept
            nxt = ts[i + 1].strip(".,;:!?«»„“”()[]—–-")
            if not keep[i] and INITIAL.match(ts[i]) and keep[i + 1] and (NAME.match(nxt) or CAPS.match(nxt)):
                keep[i] = True
        kept = [t for t, k in zip(ts, keep) if k]
        if any(LET.search(t) for t in kept):
            out.append(" ".join(kept))
    return "\n".join(out) + ("\n" if out else ""), kept_w, drop_w


class Folded:
    """A model that scores a word in MODERN spelling (ѣ→е, і→и, ѳ→ф, ѵ→и) and so leaves the word itself as read.
    The Russian models were trained on `rus` readings, which never contain the old letters; an `orus` reading of
    a pre-reform page does (the editor's old-letter rule, 2026-09-28), and unfolded, its real words would score as junk."""
    FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и", "Ѣ": "Е", "І": "И", "Ѳ": "Ф", "Ѵ": "И"})

    def __init__(self, m):
        self.m = m

    def logp(self, tok):
        return self.m.logp(tok.translate(self.FOLD))


def apply(root, mdir, tau):
    M = {k: Model.load(json.load(open(os.path.join(mdir, k + ".json")))) for k in ("ru", "jcyr", "eo", "jlat")}
    acc = accepted(root); per = collections.defaultdict(list); tot = collections.Counter()
    cache = {}
    for c, n in bi_pages(root):
        d = os.path.join(root, c)
        if c not in cache:
            cache = {c: combined_pages(root, c)}
        eo_src = os.path.join(d, f"page-{n:04d}.txt") if (c, n) in acc else None
        eo = open(eo_src, encoding="utf-8", errors="ignore").read() if eo_src else cache[c].get(n, "")
        # the Russian reading by the OLD-LETTER RULE (`orus` on pre-reform pages, else `rus`; editor 2026-09-28)
        rp = RR.russian_reading_path(os.path.join(d, f"page-{n:04d}.txt")) or ""
        rus = open(rp, encoding="utf-8", errors="ignore").read() if rp else ""
        e, ek, ed = clean(eo, M["eo"], M["jlat"], tau, protect=protected_latin)
        g, gk, gd = clean(eo, M["eo"], M["jlat"], tau, protect=protected_latin, strict=True)
        open(os.path.join(d, f"page-{n:04d}.eo-gate.txt"), "w", encoding="utf-8").write(g)
        tot["eo_gate_kept"] += gk; tot["eo_gate_dropped"] += gd
        r, rk, rd = clean(rus, Folded(M["ru"]), Folded(M["jcyr"]), tau)
        open(os.path.join(d, f"page-{n:04d}.eo-clean.txt"), "w", encoding="utf-8").write(e)
        open(os.path.join(d, f"page-{n:04d}.ru-clean.txt"), "w", encoding="utf-8").write(r)
        per[c].append({"page": n, "eo_source": "Esperanto reading" if eo_src else "combined text",
                       "eo_kept": ek, "eo_dropped": ed, "ru_kept": rk, "ru_dropped": rd})
        tot["pages"] += 1; tot["eo_kept"] += ek; tot["eo_dropped"] += ed; tot["ru_kept"] += rk; tot["ru_dropped"] += rd
    for c, recs in per.items():
        json.dump({"tau": tau, "models": mdir, "pages": recs}, open(os.path.join(root, c, "CLEAN.json"), "w"), indent=1)
    print(f"{len(per)} items · " + " · ".join(f"{k} {v}" for k, v in tot.items()))


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "train":
        train(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) >= 4 and sys.argv[1] == "apply":
        tau = float(sys.argv[sys.argv.index("--tau") + 1]) if "--tau" in sys.argv else 0.0
        apply(sys.argv[2], sys.argv[3], tau)
    else:
        sys.exit(__doc__)
