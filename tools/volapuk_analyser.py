#!/usr/bin/env python3
r"""volapuk_analyser — is a word Volapük? The list (tools/lexicons/volapuk.txt), or a compound or derivative of its parts.

    import volapuk_analyser as VA; VA.is_word("volapükatidäls")
    python3 tools/volapuk_analyser.py --measure <dir of texts> [<dir> …]     # list against list + analyser

WHY (2026-10-17). The list alone scores Sprague 0.87 but our OCR of *Volapükabled* before 1900 only 0.40–0.67: the
journals compound and derive freely («volapükatidäls», «kluböp», «gretikos», «deutapük»), which no list holds
(an internal record, 2026-10-17, not published). The proposal's option (a) («a small analyser that accepts
root + genitive + root and the regular affixes»; a proposal, an internal record, 2026-10-16, not published); approved
by the editor, 2026-10-17 18:3x.

THE RULE. A word is Volapük if it is in the list, or if it parses as
    [tense or passive sign]  UNIT (LINK UNIT){0,2}  ENDING
where a UNIT is [compounding head] STEM [suffix]{0,2}; a LINK is nothing or a linking vowel (a e i; «as» the plural
genitive); an ENDING is one of the list's own inflection endings (the noun's cases, the adjective's -ik forms, the
adverb -o, the verb's persons, moods, infinitive and participle). The tense and passive signs go only with a verb
ending. The parts come from the five approved sources (`tools/lexicons/volapuk-parts.json`, written by
`tools/build-volapuk-lexicon.py`): 17,739 stems, 397 compounding heads, 162 suffixes. Stems of fewer than MIN_STEM
letters count only as the first unit, so short stems cannot string any letters together (measured: see --measure).
"""
import os, re, sys, json, glob, random, statistics, functools, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "lexicons")
MIN_STEM = 3
INFLECTIONAL = {"a", "e", "i", "s", "as", "es", "is", "ob", "ol", "om", "of", "os", "on", "ok", "od", "öd", "ös", "öz",
                "öv", "öx", "ön", "öl", "la", "li", "ls", "um", "ün", "o", "ik", "iko", "ikum", "ikün", "öd-la"}

_spec = importlib.util.spec_from_file_location("bvl", os.path.join(HERE, "build-volapuk-lexicon.py"))
BVL = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(BVL)


# the list this instance reads: «volapuk» (Schleyer's), unless the module was loaded by words_for() for another list
# (2026-10-18: «volapuk-reformed», de Jong's, tools/build-volapuk-reformed-lexicon.py)
NAME = globals().get("NAME", "volapuk")


def _load():
    words = {l.rstrip("\n") for l in open(os.path.join(LEX, NAME + ".txt"), encoding="utf-8")}
    parts = json.load(open(os.path.join(LEX, NAME + "-parts.json"), encoding="utf-8"))
    stems = {s for s in parts["stems"] if len(s) >= 2 and re.fullmatch(r"[a-zäöü]+", s)}
    heads = {h for h in parts["heads"] if re.fullmatch(r"[a-zäöü]+", h)}
    suffixes = {x for x in parts["suffixes"] if re.fullmatch(r"[a-zäöü]+", x) and x not in INFLECTIONAL}
    # the endings, by the list's own inflection of a dummy noun, adjective and verb
    nominal = {e[3:] for e in BVL.inflect("xxx")} | {e[3:] for e in BVL.inflect("xxxik")}
    verbal = {e for e in BVL.inflect("xxxön") if e.startswith("xxx")}
    verbal = {e[3:] for e in verbal}
    signs = {p for p in BVL.TENSES + BVL.PASSIVE if p}
    return words, stems, heads, suffixes, nominal, verbal, signs


WORDS, STEMS, HEADS, SUFFIXES, NOMINAL, VERBAL, SIGNS = _load()
LINKS = ("", "a", "e", "i", "as")


@functools.lru_cache(maxsize=500000)
def _units(core, first=True, n=0):
    """can `core` be cut into 1–3 units joined by links?"""
    if n >= 3 or not core:
        return False
    for i in range(len(core), 1, -1):
        if _unit(core[:i], first):
            rest = core[i:]
            if not rest:
                return True
            for l in LINKS:
                if rest.startswith(l) and _units(rest[len(l):], False, n + 1):
                    return True
    return False


@functools.lru_cache(maxsize=500000)
def _unit(u, first):
    """[head] STEM [suffix]{0,2}"""
    for h in ("",) + tuple(x for x in HEADS if u.startswith(x)):
        v = u[len(h):]
        if _stem_suffixes(v, first and not h, 0):
            return True
    return False


def _stem_suffixes(v, first, k):
    if k == 0:
        for i in range(len(v), 1, -1):
            s = v[:i]
            if s in STEMS and (len(s) >= MIN_STEM or first) and (i == len(v) or _stem_suffixes(v[i:], first, 1)):
                return True
        return False
    if not v:
        return True
    if k > 2:
        return False
    return any(v.startswith(x) and _stem_suffixes(v[len(x):], first, k + 1) for x in SUFFIXES)


@functools.lru_cache(maxsize=2000000)
def is_word(w):
    w = w.lower()
    if w in WORDS:
        return True
    if len(w) < 5 or not re.fullmatch(r"[a-zäöü]+", w):
        return False
    for sign in ("",) + tuple(s for s in SIGNS if w.startswith(s)):
        rest = w[len(sign):]
        for tails in ((VERBAL,) if sign else (NOMINAL, VERBAL)):
            for t in sorted((t for t in tails if rest.endswith(t)), key=len, reverse=True):
                core = rest[:len(rest) - len(t)] if t else rest
                if len(core) >= 2 and _units(core):
                    return True
    return False


class VolapukWords:
    """The list with the analyser behind it, shaped like the word sets the gate tests against (`w in L`): what
    `tools/ocr-accept.py` lex("volapuk") and `tools/ocr-quality-scan.py` lexicon("volapuk") return (2026-10-17,
    approved by the editor). Iterating gives the list's own forms only."""
    def __contains__(self, w):
        return is_word(w)

    def __bool__(self):
        return True

    def __len__(self):
        return len(WORDS)

    def __iter__(self):
        return iter(WORDS)


def words_for(name):
    """the list NAME with the analyser behind it: this module for «volapuk», a second instance of it for another list
    (its own parts; the endings and prefixes are the same)"""
    if name == NAME:
        return VolapukWords()
    spec = importlib.util.spec_from_file_location(f"volapuk_analyser_{name.replace('-', '_')}", __file__)
    m = importlib.util.module_from_spec(spec)
    m.NAME = name
    spec.loader.exec_module(m)
    return m.VolapukWords()


def share(text, test):
    toks = [t.lower() for t in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", text)]
    return (sum(map(test, toks)) / len(toks)) if toks else None, len(toks)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", nargs="+", required=True)
    ap.add_argument("--english-filter", action="store_true", help="score only lines under half English (Sprague's pages)")
    a = ap.parse_args()
    english = {w.strip().lower() for w in open(os.path.join(LEX, "english.txt"), encoding="utf-8")} if a.english_filter else None
    rnd = random.Random(17)
    rows = []
    for d in a.measure:
        for f in sorted(glob.glob(os.path.join(d, "*.txt"))):
            t = open(f, encoding="utf-8", errors="ignore").read()
            if english:
                t = BVL.volapuk_lines(t, english)
            sh = " ".join("".join(rnd.sample(x, len(x))) for x in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", t))
            (l, n), (an, _), (shl, _), (sha, _) = (share(t, lambda x: x in WORDS), share(t, is_word),
                                                   share(sh, lambda x: x in WORDS), share(sh, is_word))
            if l is not None and n >= 50:
                rows.append((os.path.basename(f), n, l, an, shl, sha))
                print(f"  {os.path.basename(f)[:58]:<58} {n:>6}  list {l:.3f}  +analyser {an:.3f}  shuffled {shl:.3f} → {sha:.3f}", flush=True)
    if rows:
        m = lambda i: statistics.median(r[i] for r in rows)
        print(f"median: list {m(2):.3f} · +analyser {m(3):.3f} · shuffled {m(4):.3f} → {m(5):.3f}  ({len(rows)} texts)")


if __name__ == "__main__":
    main()
