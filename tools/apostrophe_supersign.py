#!/usr/bin/env python3
r"""apostrophe_supersign — Esperanto printed with an apostrophe for each supersign («c'i», «S'evc'enko», «au'»), normalised
to the letters themselves, in the titles named here and nowhere else.

    import apostrophe_supersign as AS;  AS.applies(item);  AS.normalise(text)
    python3 tools/apostrophe_supersign.py <item> … --root <dir of <item>.txt> --out <report.md>     # the test, a report only

WHY (the editor, 2026-11-06 14:1x: normalised, for the texts' use by others; the page readings untouched; named titles only;
tested and applied cautiously). This is a surrogate, not a reform: printers without circumflexes, as *Ukraina Stelo*'s first
number says of itself. Esperantists do normalise old orthography, with a note, so the item's line carries one.

WHAT. Mid-word c' g' h' j' s' (any apostrophe form) followed by a letter become ĉ ĝ ĥ ĵ ŝ, capitals too; u' after a or e
becomes ŭ, at a word's end as well («au'», «ankau'»). Left as printed: every other apostrophe («l'», «dank'», «de l'»), a
final c' g' h' j' s' (it may be a poet's elision: «pac'», «felic'»), and the French forms in FRENCH. Three further cases,
from the test on *Esperantista Movado* (ocr/runs/APOSTROPHE-NORMALISE-TEST-2026-11-06.md): «ec'» alone is «eĉ»; a w before
the apostrophe after a or e is the OCR's u («ankaw'», «antaw'parolo»; Esperanto has no w); and an apostrophe left after a
letter the OCR already read as accented goes («organizaĵ'oj», «ĉ'iuj»). An apostrophe the OCR did not read cannot be
restored. The rebuild applies this to the search and preferred texts it writes, only for items in `applies`; the readings
on disk keep the print as read.

WRITE-SET: as a module, none. As a script: --out, created new (refused if it exists). Reads <root>/<item>.txt and the
Esperanto word list. Miles.
"""
import argparse, collections, os, re, sys

TITLES = ("ANNO_e3j_", "esperantista_movado_")   # Ukraina Stelo 1913-14; Esperantista Movado 1920-21
APOS = "'’`´ʼ‘"
LETTER = "A-Za-zÀ-ÖØ-öø-ÿĈĉĜĝĤĥĴĵŜŝŬŭ"
MAP = {"c": "ĉ", "g": "ĝ", "h": "ĥ", "j": "ĵ", "s": "ŝ", "C": "Ĉ", "G": "Ĝ", "H": "Ĥ", "J": "Ĵ", "S": "Ŝ"}
FRENCH = {"c'est", "c'était", "c'en", "c'a", "s'il", "s'ils", "s'est", "s'en", "s'y", "s'adresser", "j'ai", "j'en", "j'y"}
WORD = re.compile(rf"[{LETTER}]*(?:[{APOS}][{LETTER}]*)+|[{LETTER}]+")
CONS = re.compile(rf"([cghjsCGHJS])[{APOS}](?=[{LETTER}])")
BREVE = re.compile(rf"(?<=[aeAE])([uUwW])[{APOS}]")
STRAY = re.compile(rf"([ĈĉĜĝĤĥĴĵŜŝŬŭ])[{APOS}](?=[{LETTER}])")
ELISION_NOT = {"ec": "eĉ", "Ec": "Eĉ", "EC": "EĈ"}


def applies(item):
    return item.startswith(TITLES)


def _word(w):
    if not any(a in w for a in APOS):
        return w
    if re.sub(f"[{APOS}]", "'", w).lower() in FRENCH:
        return w
    if w[-1] in APOS and w[:-1] in ELISION_NOT:
        return ELISION_NOT[w[:-1]]
    w = STRAY.sub(r"\1", CONS.sub(lambda m: MAP[m.group(1)], w))
    return BREVE.sub(lambda m: "ŭ" if m.group(1) in "uw" else "Ŭ", w)


def normalise(text):
    return WORD.sub(lambda m: _word(m.group(0)), text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("items", nargs="+"); ap.add_argument("--root", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    here = os.path.dirname(os.path.abspath(__file__))
    known = {l.strip().lower() for l in open(os.path.join(here, "lexicons", "esperanto.txt"), encoding="utf-8")}
    yes, no, left = collections.Counter(), collections.Counter(), collections.Counter()
    lines = ["# The apostrophe normalisation, tested (reads only)", "",
             f"Root `{a.root}`. A word is «in the list» if `tools/lexicons/esperanto.txt` holds it, lower-cased, whole.", "",
             "| item | words | apostrophe words | converted | in the list, before | in the list, after |", "|---|---:|---:|---:|---:|---:|"]
    for item in a.items:
        words = WORD.findall(open(os.path.join(a.root, item + ".txt"), encoding="utf-8", errors="replace").read())
        apo = [w for w in words if any(c in w for c in APOS)]
        conv = [(w, _word(w)) for w in apo if _word(w) != w]
        for w in apo:
            n = _word(w)
            if n == w:
                left[w] += 1
            elif n.lower() in known:
                yes[f"{w} → {n}"] += 1
            else:
                no[f"{w} → {n}"] += 1
        before = sum(w.lower() in known for w in words)
        after = sum(_word(w).lower() in known for w in words)
        lines.append(f"| {item} | {len(words):,} | {len(apo):,} | {len(conv):,} | {before / max(1, len(words)):.3f} | {after / max(1, len(words)):.3f} |")
    for title, c in (("Converted, the result in the word list", yes), ("Converted, the result NOT in the word list: look at these", no),
                     ("Apostrophes left as printed", left)):
        lines += ["", f"## {title}: {sum(c.values()):,} tokens, {len(c):,} forms", ""] + [f"- {n} × {k}" for k, n in c.most_common()]
    open(a.out, "x", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"converted, in the list {sum(yes.values())}; not in the list {sum(no.values())}; left {sum(left.values())} → {a.out}")


if __name__ == "__main__":
    main()
