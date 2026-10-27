#!/usr/bin/env python3
"""ocr_index — an index of a text's word forms, so that a name (or a whole roster) is matched against each distinct
form ONCE, and its hits looked up, instead of the text being scanned once per name (on the editor's decision of
2026-10-06 that the dowse must be able to run on just one item at a time (one journal run), with all the roster's
names against one item, which makes the lexicon more critical).

    (import) idx = build(text)            # text marked «=== page N ===»
             hits = match(name, idx)      # [(page, how, as read)]

THE RULE IS THE NAME SEARCH'S, NOT A NEW ONE. match() gives exactly what tools/ocr-name-search.py find() gives page by
page — the same spellings and allowances (name_targets), the same comparison (close), the same joins (a word; else the
first matching part of a hyphenated word; two adjacent words joined; a line-end fragment with one of the next WINDOW
words), and the same rule that a name's second form is tried only on pages its first form did not hit. Checked by
tools/ocr-index-check.py against find() before use. Forms are pre-filtered by length and alphabet within bounds wide
enough for every rule (Russian endings, a name glued to a short word, transliteration); the check is what proves them.
"""
import collections, importlib.util, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
_CYR = NS._CYRRE


def pages(text):
    parts = PAGE.split(text)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)] or [(0, text)]


class Index:
    def __init__(self):
        self.words = collections.defaultdict(list)   # form -> [(page, as read)]
        self.parts = collections.defaultdict(list)   # part form -> [(page, occ, k, token form, as read)]
        self.pairs = collections.defaultdict(list)   # joined form -> [(page, as read)]
        self.splits = []                             # (page, fragment form, as read, [(form, as read)] of the next WINDOW)
        self.buckets = {}                            # (kind, cyrillic?, length) -> [forms]

    def bucket(self):
        for kind, d in (("w", self.words), ("p", self.parts), ("j", self.pairs)):
            for f in d:
                cy = NS.is_cyr(f)
                self.buckets.setdefault((kind, cy, len(f)), []).append(f)
                if cy:   # also by the length of its transliteration, whole and stemmed (_lengths, the other alphabet)
                    for n in {len(NS.translit(f)), len(NS.translit(NS.stem(f)))}:
                        self.buckets.setdefault((kind, "tl", n), []).append(f)
        return self


def build(text, words_only=False):
    """words_only (2026-10-17, the readers' roster at scale; approved by the editor, as both speed fixes were likely to
    be needed anyway): the single words only, no parts, pairs or column splits. Those give only the «join» tier, which the
    readers' roster does not take (tools/dowse-reader-roster.py: exact, near, confusion), and the word pairs are most of
    the forms to compare. The strong tiers are the same or more: a name's second form is then tried on pages its first
    form hit only by a join. Not a presence record: its silences say nothing."""
    idx = Index(); occ = 0
    for p, ptxt in pages(text):
        raw = NS.normalise(ptxt).split()
        toks = [NS.fold(t) for t in raw]
        parts = [] if words_only else [[NS.fold(x) for x in NS.PARTS.split(r) if NS.fold(x)] for r in raw]   # the name search's own rule
        for i, t in enumerate(toks):
            occ += 1
            if t:
                idx.words[t].append((p, raw[i]))
            if words_only:
                continue
            if len(parts[i]) > 1:
                for k, x in enumerate(parts[i]):
                    idx.parts[x].append((p, occ, k, t, raw[i]))
            if i + 1 < len(toks) and toks[i + 1]:
                idx.pairs[t + toks[i + 1]].append((p, raw[i] + " " + raw[i + 1]))
            if raw[i].endswith(("-", "¬")) and t:
                idx.splits.append((p, t, raw[i], [(toks[j], raw[j]) for j in range(i + 1, min(len(toks), i + 1 + NS.WINDOW))]))
    return idx.bucket()


def _lengths(targets):
    """The buckets a form may be in and still match one of the targets, by any rule of close(): (cyrillic?, length),
    and ("tl", length) for a Cyrillic form by the length of its transliteration.

    THE OTHER ALPHABET BY LENGTH (2026-10-17; judged worth testing and approved by the editor): close() matches a Cyrillic word and a Latin
    one only by (a) the plain distance, within the allowance c, or (b) the distance of the Cyrillic one transliterated,
    whole or stemmed, within c + 1; the distance is never below the difference in length. So only forms within those
    lengths can match, and the rest are not compared: before, every form of the other alphabet up to 4 × the name's
    length was (Ruslanda Esperantisto, a Latin name against nearly every Russian word of the issue)."""
    out = set()
    for tg, _, c in targets:
        L, cyr = len(tg), NS.is_cyr(tg)
        for n in range(max(1, L - c - 3), L + c + 5):       # same alphabet: allowance, Russian endings, a glued word
            out.add((cyr, n))
        for n in range(max(1, L - c), L + c + 1):          # the other alphabet, (a) the plain distance
            out.add((not cyr, n))
        if cyr:                                            # (b) Latin forms near the name transliterated
            for x in {NS.translit(tg), NS.translit(NS.stem(tg))}:
                for n in range(max(1, len(x) - c - 1), len(x) + c + 2):
                    out.add((False, n))
        else:                                              # (b) Cyrillic forms whose transliteration is near the name
            for n in range(max(0, L - c - 1), L + c + 2):
                out.add(("tl", n))
    return out


def _cands(idx, kind, lens):
    """each form once (a Cyrillic form is in two kinds of bucket), the same-alphabet buckets first."""
    keys = sorted(lens, key=lambda k: (k[0] == "tl", str(k[0]), k[1]))
    return dict.fromkeys(f for k in keys for f in idx.buckets.get((kind,) + k, ()))


# THE PRE-FILTER (2026-10-24; the editor, on La Ondo de Esperanto's strong search still running after an hour: the name
# search was too slow, and name indexing should have taken care of it; the fix approved). The
# index saves reading the text once per name, but every name's spellings (up to 64, the measured confusions) were still
# put through close() against every form of its length buckets, one Python call each: on a poor OCR with Russian in it
# that is most of the hours. Each rule of close() matches only where an edit distance on some form of the two words is
# within an allowance: the words (c), their Russian stems (c), a Cyrillic word transliterated, whole or stemmed, against
# the Latin one (c + 1), the small-capital folds (c), a word's part before a glued function word (c), the Polish stems
# (1). So a form none of those distances admits for any spelling cannot match, and the distances are taken for all the
# forms of a bucket at once (rapidfuzz's cdist, in C). What passes still goes through close(), the judge: the hits are
# the same by construction (checked: tools/ocr-index-check.py, and the strong search of a source against its record).
try:
    import numpy as _np
    from rapidfuzz import process as _RP
    from rapidfuzz.distance import Levenshtein as _LV
except ImportError:
    _RP = None


def _glue_prefixes(t):
    return [t[:k] for k in range(1, len(t)) if t[k:] in NS._GLUE]


def _forms_of(idx, key):
    """a bucket's forms and their transforms, computed once per index."""
    if not hasattr(idx, "_tf"): idx._tf = {}
    if key not in idx._tf:
        B = idx.buckets.get(key, [])
        gp, go = [], []
        for i, f in enumerate(B):
            for p in _glue_prefixes(f): gp.append(p); go.append(i)
        idx._tf[key] = {"w": B, "stem": [NS.stem(f) for f in B], "tl": [NS.translit(f) for f in B],
                        "tls": [NS.translit(NS.stem(f)) for f in B], "sc": [f.translate(NS._SC) for f in B],
                        "ls": [NS.lstem(f) for f in B], "gp": gp, "go": _np.array(go, dtype=_np.int64)}
    return idx._tf[key]


def _admit(queries, caps, choices, extra=0):
    """the choices within its allowance (+ extra) of at least one query: a boolean array over the choices."""
    if not choices or not queries: return _np.zeros(len(choices), dtype=bool)
    caps = _np.asarray(caps) + extra
    m = _RP.cdist(queries, choices, scorer=_LV.distance, score_cutoff=int(caps.max()), dtype=_np.int32)
    return (m <= caps[:, None]).any(axis=0)


def _prefilter(idx, kind, lens, targets):
    """the forms of the buckets that some rule of close() may admit for some target (a superset of the matches)."""
    if _RP is None: return None
    q = [tg for tg, _, c in targets]; cs = [c for tg, _, c in targets]
    qs = [NS.stem(tg) for tg in q]; qsc = [tg.translate(NS._SC) for tg in q]; ql = [NS.lstem(tg) for tg in q]
    qt = [NS.translit(tg) for tg in q] + [NS.translit(NS.stem(tg)) for tg in q]; ct = cs + cs
    keep = set()
    for k in lens:
        T = _forms_of(idx, (kind,) + k)
        B = T["w"]
        if not B: continue
        ok = _admit(q, cs, B)
        ok |= _admit(qs, cs, T["stem"])
        ok |= _admit(q, cs, T["tl"], 1) | _admit(q, cs, T["tls"], 1)
        ok |= _admit(qt, ct, B, 1)
        ok |= _admit(qsc, cs, T["sc"])
        ok |= _admit(ql, [1] * len(ql), T["ls"])
        if T["gp"]:
            g = _admit(q, cs, T["gp"])
            ok[T["go"][g]] = True
        keep.update(B[i] for i in _np.flatnonzero(ok))
    return keep


def match(name, idx):
    """[(page, how, as read)] — what find(name, page text) returns, over every page of the indexed text."""
    out, done = [], set()
    for f in NS.forms(name):
        targets = NS.name_targets(f)
        memo = {}

        def near(t):
            if t not in memo:
                memo[t] = next((why for tg, why, c in targets if NS.close(t, tg, c)), None)
            return memo[t]

        lens = _lengths(targets)
        hits = collections.defaultdict(list)
        keep = _prefilter(idx, "w", lens, targets)   # None: no rapidfuzz, every form to close() as before
        for form in _cands(idx, "w", lens):
            if keep is not None and form not in keep: continue
            w = near(form)
            if w is not None:
                for p, r in idx.words[form]:
                    hits[p].append(("word" + w, r))
        part_hit = {}
        keep = _prefilter(idx, "p", lens, targets) if idx.parts else set()
        for form in _cands(idx, "p", lens):
            if keep is not None and form not in keep: continue
            w = near(form)
            if w is None:
                continue
            for p, occ, k, t, r in idx.parts[form]:
                if near(t) is None and (occ not in part_hit or k < part_hit[occ][1]):
                    part_hit[occ] = (p, k, w, r)
        for p, k, w, r in part_hit.values():
            hits[p].append(("part of a hyphenated word" + w, r))
        keep = _prefilter(idx, "j", lens, targets) if idx.pairs else set()
        for form in _cands(idx, "j", lens):
            if keep is not None and form not in keep: continue
            w = near(form)
            if w is not None:
                for p, r in idx.pairs[form]:
                    hits[p].append(("two words joined" + w, r))
        for p, t, r, nxt in idx.splits:
            if any(tg.startswith(t[:max(2, len(t) - 1)]) for tg, _, _ in targets):
                for fj, rj in nxt:
                    w = near(t + fj) if fj else None
                    if w is not None:
                        hits[p].append(("column split" + w, r + " … " + rj)); break
        for p, hs in hits.items():
            if p not in done:
                out += [(p, how, r) for how, r in hs]
        done |= set(hits)
    return out
