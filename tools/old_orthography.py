"""Old spellings matched against a modern word list (2026-10-21, cupel17; at 04:0x, on *Portugala Revuo*, the editor
asked that the gate honour the declared Portuguese, noting that there might well be historical orthography issues).

Portuguese before the 1911 reform (Portugal) and the 1943 one (Brazil) wrote etymological spellings the modern list
(tools/lexicons/portuguese.txt) lacks: *pharmacia*, *theatro*, *typographia*, *annos*, *commercio*, *projecto*,
*direcção*, *scientifico*, *portuguez*, *paiz*, *realisou*, *jornaes*, *teem*. Measured on the 21 *Portugala Revuo*
items (Esperanto-model reading): of the words in neither the Esperanto nor the Portuguese list, 441 tokens match once
both sides are folded as below. The word on the page is never changed: only the membership test is folded.

Used by tools/ocr-accept.py (G2 density, G4 credit) and tools/ocr-second-model.py (`por`: which reading is a word).
"""
import unicodedata

# order matters: doubled letters first, so «direcção» → «direccao» → «direcao» like modern «direção»
_PT = (("ph", "f"), ("th", "t"), ("rh", "r"), ("y", "i"),
       ("mm", "m"), ("nn", "n"), ("ll", "l"), ("tt", "t"), ("pp", "p"), ("cc", "c"), ("ff", "f"),
       ("gg", "g"), ("dd", "d"), ("bb", "b"), ("ss", "s"),
       ("ct", "t"), ("pt", "t"), ("sc", "c"), ("z", "s"), ("ee", "e"))


def fold_portuguese(w):
    """Accents stripped (the reforms moved them: *sciencia* / *ciência*), then the etymological letters dropped and
    «z»/«s» merged (*portuguez* / *português*, *realisou* / *realizou*); a final «-aes»/«-ae» read as «-ais»/«-ai»
    (*jornaes*). «ch» is left alone: modern Portuguese keeps it (*chave*)."""
    x = "".join(c for c in unicodedata.normalize("NFD", w.lower()) if unicodedata.category(c) != "Mn")
    for a, b in _PT:
        x = x.replace(a, b)
    if x.endswith("aes"):
        x = x[:-3] + "ais"
    elif x.endswith("ae"):
        x = x[:-2] + "ai"
    return x


class FoldedPortuguese(set):
    """A Portuguese word list whose membership tries the word as printed, then its folded form (4 letters or more:
    folded, three-letter fragments of a broken reading matched by chance: *nio* ×81, *lli*, *tes*, *gre*)."""

    def __init__(self, base):
        super().__init__(base)
        self.folded = {fold_portuguese(w) for w in base}

    def __contains__(self, w):
        return set.__contains__(self, w) or (len(w) >= 4 and fold_portuguese(w) in self.folded)


# GERMAN AND SWEDISH (2026-10-31, the editor 19:5x, then approved: measured,
# then built; geniza/ocr/runs/OLD-SPELLING-MEASURE-2026-10-31.md). German before 1901 (thun, Theil, Thätigkeit;
# Redaction, Correspondenz, October; broschirt; giebt) and before 1996 (daß, muß, Kongreß: `german.txt` is the 1996
# spelling): 18,205 tokens recovered in 630 of 726 items, every top form a true old spelling. Swedish before 1906 (hvad,
# hvilken, qvinna, öfver, hafva, af): 1,524 tokens in 25 of 49 items. A word is tried as printed, then in each variant;
# the word on the page is never changed. (Hungarian «cz»: 14 tokens, place names; not folded. Dutch: judged by Hunspell
# behind its list, with its own variants, tools/hunspell_words.py.)
import itertools, re


def german_variants(w):
    v = w.lower().replace("ß", "ss").replace("giebt", "gibt").replace("th", "t")
    v = re.sub(r"ir(en|t|te|ten|ung|ungen|bar)$", r"ier\1", v)          # marschiren, studirt
    v = re.sub(r"niss$", "nis", v)                                        # Kenntniß → Kenntnis
    out = {v}
    cs = [m.start() for m in re.finditer(r"c(?![hk])", v)][:2]           # Concert, Citrone, Centrum
    for combo in itertools.product("kz", repeat=len(cs)):
        x = list(v)
        for i, c in zip(cs, combo):
            x[i] = c
        out.add("".join(x))
    return out


def swedish_variants(w):
    v = w.lower().replace("hv", "v").replace("qv", "kv").replace("fv", "v")
    v = re.sub(r"(?<=[aeiouyåäö])f$", "v", v)                            # af → av, haf → hav
    return {v, re.sub(r"dt$", "t", v), re.sub(r"dt$", "d", v)}


def dutch_variants(w):
    """Dutch before 1947: a final «sch» (Duitsch, wensch, tusschen), doubled vowels in open syllables (vereeniging,
    zooals, noodig), «ae» for «aa», «y» for «ij». Tried by tools/hunspell_words.py when Hunspell rejects the word."""
    v = re.sub(r"sch(e|en|er)?$", lambda m: "s" + (m.group(1) or ""), w.lower())
    out = {v, v.replace("ae", "aa"), v.replace("y", "ij")}
    for x in list(out):
        out |= {x.replace("oo", "o"), x.replace("ee", "e"), x.replace("oo", "o").replace("ee", "e")}
    return out


class FoldedVariants(set):
    """A word list whose membership tries the word as printed, then (4 letters or more) each old-spelling variant."""

    def __init__(self, base, variants):
        super().__init__(base)
        self.variants = variants

    def __contains__(self, w):
        # «muß» (1,066 tokens) is three letters: a word with «ß» is folded whatever its length
        return set.__contains__(self, w) or ((len(w) >= 4 or "ß" in w)
                                             and any(v != w and set.__contains__(self, v) for v in self.variants(w)))
