#!/usr/bin/env python3
r"""build-lsf-lexicon — the Latino sine flexione word list for the gate: tools/lexicons/latino-sine-flexione.txt.

    python3 tools/build-lsf-lexicon.py        # needs tools/lexicons/latin.txt (tools/build-lexicons.py --only latin)

WHY (2026-10-17, cupel14). *Schola et Vita* (Peano's Academia pro Interlingua, 1926–1934) had no word list of its own
and was scored against the Occidental list as a naturalistic proxy (the editor's option (a) at C5.2). It failed:
Occidental took 0.65 of its words, and 0.63 of an Esperanto page's, so it could not tell the two apart. At 02:3x the
editor asked for an experiment, suggesting Latin ablatives for Latino sine flexione; it was measured (an internal
record, 2026-10-17, not published), the editor chose option (b), and it was built on the editor's approval. Peano's rule takes a noun or
adjective from the Latin ablative and a verb from its stem, so Latin's own forms carry most of it; the international
words in Latin dress («organizatione», «scientifico») come from Occidental by a suffix rule.

WHAT, every part from a clean source (no OCR): (1) `latin.txt`, Karl Zeiler's Latin Hunspell dictionary 3.1 (2013),
every form its affix rules make (18.3 M); (2) `occidental.txt` as the gate has it; (3) the SUFFIX RULE on Occidental's
words: -ion → -ione, -itá/-ita → -itate, -ic → -ico/-ica, -al → -ale, -ism → -ismo, -iv → -ivo, -ist → -ista,
-ent → -ente, -ant → -ante, -ar → -are, -or → -ore, with «-isat-»/«-ise-» also as «-izat-»/«-ize-», and each derived form
also with Peano's plural «-s». Measured on Schola et Vita (32 issues): median 0.91 of words per page, the lowest issue
0.85, against Occidental's 0.65; Esperanto pages 0.67 and Schola's own words with shuffled letters 0.32, so no more
permissive than Occidental ∪ Latin. Lower case, as the gate compares. WRITES only the list and a line in _MANIFEST.md.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "lexicons")
RULES = [(r"ion$", ["ione"]), (r"itá$", ["itate"]), (r"ita$", ["itate"]), (r"ic$", ["ico", "ica"]), (r"al$", ["ale"]),
         (r"ism$", ["ismo"]), (r"iv$", ["ivo"]), (r"ist$", ["ista"]), (r"ent$", ["ente"]), (r"ant$", ["ante"]),
         (r"ar$", ["are"]), (r"or$", ["ore"])]


def main():
    lat = os.path.join(LEX, "latin.txt")
    if not os.path.exists(lat):
        raise SystemExit("needs tools/lexicons/latin.txt: run tools/build-lexicons.py --only latin")
    occ = {w.strip().lower() for w in open(os.path.join(LEX, "occidental.txt"), encoding="utf-8") if w.strip()}
    der = set()
    for w in occ:
        for rx, outs in RULES:
            if re.search(rx, w):
                for o in outs:
                    v = re.sub(rx, o, w); der.add(v)
                    if "is" in v: der.add(re.sub(r"(?<=[aeiou])s(?=a[tr]|e)", "z", v))
    der |= {d + "s" for d in list(der)}
    words = set(occ) | der
    n_lat = 0
    with open(lat, encoding="utf-8") as f:
        for l in f:
            w = l.strip()
            if w: words.add(w); n_lat += 1
    out = os.path.join(LEX, "latino-sine-flexione.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(words)) + "\n")
    with open(os.path.join(LEX, "_MANIFEST.md"), "a", encoding="utf-8") as f:
        f.write(f"| latino-sine-flexione | latin.txt ({n_lat:,}) ∪ occidental.txt ({len(occ):,}) ∪ the suffix rule "
                f"({len(der):,}): tools/build-lsf-lexicon.py | 3 | — | {len(words):,} |\n")
    print(f"latin {n_lat:,} · occidental {len(occ):,} · derived {len(der):,} → {len(words):,} forms → {out}")


if __name__ == "__main__":
    main()
