#!/usr/bin/env python3
r"""cyrillic_lexicon — which Cyrillic word list an item's Cyrillic side is tested against: Russian, Bulgarian or Ukrainian.

    import cyrillic_lexicon as CL; L = CL.for_item(stem, ru_set)      # `w in L`, as the Russian route's tools test

WHY (2026-10-17). The Russian route (`tools/ocr-russian-pages.py`, `ocr-layout-mixed.py`, `ocr-rus-companion.py`, the
Russian-only score in `ocr-accept.py`) tests Cyrillic words against the Russian list, so a Bulgarian text fails it: on
*Bulgara Esperantisto* 1907 the Russian list takes 0.10–0.18 of the words, the Bulgarian list with the old spelling
folded 0.57–0.78 (an internal record, 2026-10-17, not published). At 19:1x the editor ruled that Bulgarian language
support is still needed, expected it to be handled as orus Cyrillic, and asked for a Bulgarian spellcheck to be arranged
on the precedent of Slovak; at 19:3x the editor approved a Bulgarian-only score on orus with the folding, by the Russian
side's route.

THE RULE. An item the language table lists with Bulgarian and without Russian is tested against
`tools/lexicons/bulgarian.txt` (bgOffice's Hunspell, built by `tools/build-lexicons.py`, the Slovak route), through
the old spelling: pre-1945 Bulgarian prints ѫ (now ъ), ѭ (now ю), ѣ (now е or я) and a final ъ or ь (now dropped),
and the Russian tools have already folded ѣ to е, і to и and dropped a final ъ before they ask. Every other item keeps
the Russian list, exactly as before.

UKRAINIAN (2026-10-18; approved by the editor 00:1x, on *Ukraina Stelo* 1913–14, Kolomyia, Esperanto and Ukrainian). An item
listed with Ukrainian and without Russian is tested against `tools/lexicons/ukrainian.txt` (the Hunspell list, built
by `tools/build-lexicons.py` 2026-10-03), modern spelling, through the Galician spelling of before the 1920s
(Zhelekhivka): ї after a consonant for modern і («сїно», «дїло») or for ’ї after a prefix («зїзд»); є, ю, я after a
consonant for the modern doubled consonant («житє» → «життя», «надісланєм» → «надісланням») or, for є, a plain е.
The Russian route's tools fold і to и before they ask, so и is also tried back as і. Measured on *Ukraina Stelo*
1913–14 (an internal record, 2026-10-18, not published).
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_text_languages as TL

_BG = {}


def bulgarian_variants(w):
    w = w.lower().replace("ѫ", "ъ").replace("ѭ", "ю").replace("і", "и")
    w = re.sub(r"[ъь]$", "", w)
    return {w.replace("ѣ", "е"), w.replace("ѣ", "я")} if "ѣ" in w else {w}


class BulgarianWords:
    """The Bulgarian list, shaped like the Russian route's word sets (`w in L`)."""
    def __init__(self):
        if "L" not in _BG:
            _BG["L"] = {l.strip().lower() for l in open(os.path.join(HERE, "lexicons", "bulgarian.txt"),
                                                         encoding="utf-8", errors="ignore") if l.strip()}
        self.L = _BG["L"]

    def __contains__(self, w):
        return w in self.L or any(v in self.L for v in bulgarian_variants(w))

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.L)

    def __iter__(self):
        return iter(self.L)


_UK = {}
UK_CONS = set("бвгґджзклмнпрстфхцчшщ")


def ukrainian_variants(w, cap=64):
    """the word as printed and its modern spellings (at most `cap`): see UKRAINIAN above"""
    w = w.lower().replace("’", "'").replace("ʼ", "'")
    out = [""]
    for i, ch in enumerate(w):
        prev = w[i - 1] if i else ""
        if prev in UK_CONS and ch == "ї":
            alts = ("ї", "і", "'ї")
        elif prev in UK_CONS and ch == "є":
            alts = ("є", "е", prev + "я")
        elif prev in UK_CONS and ch in "юя":
            alts = (ch, prev + ch)
        else:
            alts = (ch,)
        out = [o + a for o in out for a in alts][:cap]
    return set(out)


class UkrainianWords:
    """The Ukrainian list, shaped like the Russian route's word sets (`w in L`), through the Galician spelling."""
    def __init__(self):
        if "L" not in _UK:
            _UK["L"] = {l.strip().lower().replace("’", "'") for l in open(os.path.join(HERE, "lexicons", "ukrainian.txt"),
                                                                          encoding="utf-8", errors="ignore") if l.strip()}
        self.L = _UK["L"]

    def __contains__(self, w):
        w = w.lower()
        if w in self.L or any(v in self.L for v in ukrainian_variants(w)):
            return True
        # the Russian route's tools fold і to и before they ask (ocr-mixed-lines.py, ocr-russian-pages.py): і is an
        # ordinary Ukrainian letter, so и is tried back as і (every choice up to four и, else all or one)
        pos = [i for i, c in enumerate(w) if c == "и"]
        if not pos:
            return False
        if len(pos) <= 4:
            subs = [{p for k, p in enumerate(pos) if m >> k & 1} for m in range(1, 1 << len(pos))]
        else:
            subs = [set(pos)] + [{p} for p in pos]
        for sub in subs:
            v = "".join("і" if i in sub else c for i, c in enumerate(w))
            if v in self.L or any(x in self.L for x in ukrainian_variants(v, 16)):
                return True
        return False

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.L)

    def __iter__(self):
        return iter(self.L)


def language(stem):
    """«bulgarian» or «ukrainian» for an item listed with that language and without Russian, else «russian»"""
    cy = TL.cyrillic(stem) or set()
    if "russian" in cy:
        return "russian"
    return "bulgarian" if "bulgarian" in cy else "ukrainian" if "ukrainian" in cy else "russian"


def words(side):
    return BulgarianWords() if side == "bulgarian" else UkrainianWords() if side == "ukrainian" else None


def for_item(stem, ru):
    return words(language(stem)) or ru
