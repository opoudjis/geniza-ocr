#!/usr/bin/env python3
"""ocr_index — an index of a text's word forms, so that a name (or a whole roster) is matched against each distinct
form ONCE, and its hits looked up, instead of the text being scanned once per name (at the editor's request of
2026-10-06 that a whole roster be searched against one journal run, the project's usual search, which makes such an
index essential).

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
                self.buckets.setdefault((kind, bool(_CYR.search(f)), len(f)), []).append(f)
        return self


def build(text):
    idx = Index(); occ = 0
    for p, ptxt in pages(text):
        raw = NS.normalise(ptxt).split()
        toks = [NS.fold(t) for t in raw]
        parts = [[NS.fold(x) for x in re.split(r"[-‐¬/'’]", r) if NS.fold(x)] for r in raw]
        for i, t in enumerate(toks):
            occ += 1
            if t:
                idx.words[t].append((p, raw[i]))
            if len(parts[i]) > 1:
                for k, x in enumerate(parts[i]):
                    idx.parts[x].append((p, occ, k, t, raw[i]))
            if i + 1 < len(toks) and toks[i + 1]:
                idx.pairs[t + toks[i + 1]].append((p, raw[i] + " " + raw[i + 1]))
            if raw[i].endswith(("-", "¬")) and t:
                idx.splits.append((p, t, raw[i], [(toks[j], raw[j]) for j in range(i + 1, min(len(toks), i + 1 + NS.WINDOW))]))
    return idx.bucket()


def _lengths(targets):
    """(cyrillic?, length) pairs a form may have and still match one of the targets, by any rule of close()."""
    out = set()
    for tg, _, c in targets:
        L, cyr = len(tg), bool(_CYR.search(tg))
        for n in range(max(1, L - c - 3), L + c + 5):       # same alphabet: allowance, Russian endings, a glued word
            out.add((cyr, n))
        for n in range(1, 4 * L + c + 3):                  # the other alphabet, compared through transliteration
            out.add((not cyr, n))
    return out


def _cands(idx, kind, lens):
    for cyr, n in lens:
        yield from idx.buckets.get((kind, cyr, n), ())


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
        for form in _cands(idx, "w", lens):
            w = near(form)
            if w is not None:
                for p, r in idx.words[form]:
                    hits[p].append(("word" + w, r))
        part_hit = {}
        for form in _cands(idx, "p", lens):
            w = near(form)
            if w is None:
                continue
            for p, occ, k, t, r in idx.parts[form]:
                if near(t) is None and (occ not in part_hit or k < part_hit[occ][1]):
                    part_hit[occ] = (p, k, w, r)
        for p, k, w, r in part_hit.values():
            hits[p].append(("part of a hyphenated word" + w, r))
        for form in _cands(idx, "j", lens):
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
