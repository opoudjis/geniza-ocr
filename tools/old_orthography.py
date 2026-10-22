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
