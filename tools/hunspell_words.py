"""hunspell_words — a stems-only word list with Hunspell itself behind it, its verdicts cached.

    import hunspell_words
    L = hunspell_words.words_for("hungarian", stems)   # stems: the set from tools/lexicons/hungarian.txt
    "házban" in L                                       # True if the stems hold it, else Hunspell's verdict

WHY (the editor, 2026-10-29 21:1x–21:2x, cupel19c C5.2; the design approved 21:2x): an agglutinative
language's affix expansion cannot be written out (Estonian 15.0 M forms, 2026-09-27; Hungarian's unmunch passed
59.5 GB, 2026-10-29), so its list is the dictionary's stems only (A), and a word the stems lack is put to Hunspell
with the same dictionary and its own rules (B): the full expansion, judged a word at a time and never written out.
Nothing from our texts enters any list: the forms taken from our pages into the list (Estonian 2026-09-28, Hungarian
and Croatian 2026-10-29) were withdrawn as contamination of the dictionary by the corpus it tests.
THE CACHE holds verdicts, not words for a list: every word judged, accepted or rejected (`word<TAB>1|0`), so a rerun
never asks twice; keyed to the dictionary's version (the first 12 hex of sha256 over the .aff and .dic), so a changed
dictionary starts a new cache. Never merged into the .dic or the .txt lists, and read only through this class.
A word is tried as given (lower case, as every list is) and then capitalised, since the lists hold the dictionaries'
proper names lowercased too (*kolumbija*): names are treated as in every other language.
Hunspell is called through its library (`libhunspell-1.7`, ctypes): no process per word, no suggestions computed.
WRITE-SET: `tools/lexicons/hunspell-cache/<code>-<sha12>.tsv`, appended a line per new verdict (O_APPEND, one write
each, so the gate's worker processes may share it).
"""
import ctypes, ctypes.util, hashlib, os

HERE = os.path.dirname(os.path.abspath(__file__))
HUNSPELL_DIR = os.path.join(HERE, "lexicons", "hunspell")
CACHE_DIR = os.path.join(HERE, "lexicons", "hunspell-cache")
# the languages judged by Hunspell behind their stems (the editor 2026-10-29: Hungarian, Finnish, Estonian; Finnish
# has no dictionary on disk yet: fetched when an item needs it, then «"finnish": "fi"» here)
JUDGED = {"hungarian": "hu", "estonian": "et"}
# THE PRECEDENT (the editor 2026-10-31, cupel19c
#): an agglutinative language is judged here, a word at
# a time, by its dictionary and its own rules, the verdicts cached; never by a list of its forms written out
# (tools/build-lexicons.py keeps them STEMS_ONLY and refuses to build otherwise). EVERY word test reads JUDGED: the gate (ocr-accept lex()), the
# quality scan, the page languages, and the second-model merge (ocr-second-model lexicons()). A new agglutinative
# language goes into JUDGED and STEMS_ONLY, nowhere else.
# DANISH, a non-agglutinative exception (the editor 2026-10-31 10:1x): its list keeps unmunch's
# expansion, but da.aff's numbered flags and twofold affixes left that incomplete (havde, denne, blev, hver, ingen
# missing, all accepted by Hunspell; cupel19c's Raporto, failure map R87), so Hunspell answers for what the list lacks.
JUDGED["danish"] = "da"
FULL_LIST = {"danish"}   # judged languages whose built list is NOT stems only (build-lexicons.py's check allows them)
# OLD SPELLINGS folded before Hunspell is asked (the page's spelling stays; the word counts if its modern form is one):
# Danish «aa» for «å» before 1948 (udgaar, forstaa, saadanne, faaet).
FOLDS = {"da": [("aa", "å"), ("Aa", "Å")]}
# DUTCH, the same exception (2026-10-31, the editor, after the old-spelling measure,
# geniza/ocr/runs/OLD-SPELLING-MEASURE-2026-10-31.md): `dutch.txt` (unmunch of nl.dic) lacks zij, wordt, mensen, woorden,
# vreemde, nederlandse; Hunspell answers for what the list lacks, and the spelling before 1947 (Duitsch, vereeniging,
# zooals, noodig; tools/old_orthography.py dutch_variants) is tried when Hunspell rejects the word as printed.
JUDGED["dutch"] = "nl"
FULL_LIST.add("dutch")
VARIANTS = {"nl": "dutch_variants"}   # a variants function of tools/old_orthography.py, by Hunspell code
CODE_NAMES = {v: k for k, v in JUDGED.items()}
LIBS = ("/opt/homebrew/opt/hunspell/lib/libhunspell-1.7.dylib", "/usr/local/opt/hunspell/lib/libhunspell-1.7.dylib")


def _lib():
    path = next((p for p in LIBS if os.path.exists(p)), None) or ctypes.util.find_library("hunspell-1.7")
    if not path:
        raise RuntimeError("libhunspell-1.7 not found (brew install hunspell)")
    lib = ctypes.CDLL(path)
    lib.Hunspell_create.restype = ctypes.c_void_p
    lib.Hunspell_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.Hunspell_spell.restype = ctypes.c_int
    lib.Hunspell_spell.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.Hunspell_get_dic_encoding.restype = ctypes.c_char_p
    lib.Hunspell_get_dic_encoding.argtypes = [ctypes.c_void_p]
    return lib


class HunspellWords(set):
    """The stems as a set; membership falls back to the cache, then to Hunspell (verdict cached)."""

    def __init__(self, stems, code):
        super().__init__(stems)
        aff, dic = (os.path.join(HUNSPELL_DIR, f"{code}.{x}") for x in ("aff", "dic"))
        h = hashlib.sha256()
        for p in (aff, dic):
            with open(p, "rb") as f:
                h.update(f.read())
        self.code, self.version = code, h.hexdigest()[:12]
        self.lib = _lib()
        self.h = self.lib.Hunspell_create(aff.encode(), dic.encode())
        enc = (self.lib.Hunspell_get_dic_encoding(self.h) or b"UTF-8").decode()
        self.enc = {"utf-8": "utf-8", "utf8": "utf-8"}.get(enc.lower(), enc)
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.cache_path = os.path.join(CACHE_DIR, f"{code}-{self.version}.tsv")
        self.cache = {}
        if os.path.exists(self.cache_path):
            for line in open(self.cache_path, encoding="utf-8"):
                w, _, v = line.rstrip("\n").partition("\t")
                if w:
                    self.cache[w] = v == "1"
        self.fd = os.open(self.cache_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        self.judged = 0   # new verdicts this run

    def _spell(self, w):
        try:
            b = w.encode(self.enc)
        except (UnicodeEncodeError, LookupError):
            return False
        return bool(self.lib.Hunspell_spell(self.h, b))

    def listed(self, w):
        return set.__contains__(self, w)

    def __contains__(self, w):
        if set.__contains__(self, w):
            return True
        v = self.cache.get(w)
        if v is None:
            v = self._spell(w) or (w[:1].upper() + w[1:] != w and self._spell(w[:1].upper() + w[1:]))
            for old, new in (FOLDS.get(self.code, []) if not v else []):
                f = w.replace(old, new)
                if f != w and (set.__contains__(self, f) or self._spell(f) or self._spell(f[:1].upper() + f[1:])):
                    v = True
                    break
            if not v and self.code in VARIANTS and len(w) >= 4:
                import old_orthography as OO
                for f in getattr(OO, VARIANTS[self.code])(w):
                    if f != w and (set.__contains__(self, f) or self._spell(f) or self._spell(f[:1].upper() + f[1:])):
                        v = True
                        break
            self.cache[w] = v
            self.judged += 1
            os.write(self.fd, f"{w}\t{int(v)}\n".encode("utf-8"))
        return v


def listed(L, w):
    """Is `w` in list L's own words? For a judged list (or a fold over one) its stems only, not Hunspell's verdicts:
    the judge adds what no other list explains, and never takes a word another list holds (the editor 2026-10-29
    21:3x: Esperanto lost about a tenth of its words on Esperanto pages to Estonian's judge)."""
    return L.listed(w) if hasattr(L, "listed") else w in L


def words_for(lang, stems):
    """The judged list for a JUDGED language, or the stems unchanged (all stems if HUNSPELL_WORDS=off: to measure A against B)."""
    on = os.environ.get("HUNSPELL_WORDS", "on") != "off"
    return HunspellWords(stems, JUDGED[lang]) if on and lang in JUDGED and stems else stems
