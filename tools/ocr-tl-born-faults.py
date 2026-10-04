#!/usr/bin/env python3
r"""ocr-tl-born-faults — the intake for emending born-digital text layers: which faults, how many, where.

    tools/ocr-tl-born-faults.py --root <ocr-rendersearch> --kind <tl-kind.tsv> --out <stem>

WHY (2026-09-30). The editor approved born-digital text layers into the search text (points 1 and 2) and asked
for them to be emended, judging this a tractable and finite task worth doing. A
born-digital layer IS the printed text, but it carries known faults of its own (an internal record, 2026-09-30,
not published). This measures them per page and per corpus before anything is changed. Read-only.

THE FIRST ACCENT TEST WAS WRONG (14:52). It compared the layer's ĉĝĥĵŝŭ with our OCR's and flagged a layer with
far fewer. But our Esperanto-model OCR FORCES Esperanto letters onto other languages' accents (Serbian
«Milanović» → «Milanoviĉ», Italian «gioventù» → «gioventŭ», French «état» → «ĉtat»), so it flagged correct layers.
The test below uses the LAYER ALONE and the lexicons: a word lost its accent if it is in no lexicon as printed but
becomes an Esperanto word when the accent is restored.

Per born-digital page (tl-kind.tsv: largest image < 50% of the page) with a `page-NNNN.tl.txt`:
  words    words of 3+ letters in the layer
  miss     words in no lexicon that become an Esperanto lexicon word when c g h j s u take their accent
           (ci → ĉi, sangxo aside): accents dropped by a font without a Unicode map
  subst    words in no lexicon that become an Esperanto word when a foreign accented letter (é è ê ë à ù ü û
           č ć š ž ĝ …) is read as ĉ ĝ ĥ ĵ ŝ ŭ: a font that maps the Esperanto glyphs to other code points
  xsys     x-system digraphs (cx gx hx jx sx) — typed-in substitutes; «ux» is not counted (French aux/deux/ceux)
  bad      private-use (U+E000–F8FF) and replacement (U+FFFD) characters: glyphs with no Unicode at all
  lig      ligature code points (U+FB00–FB06)
  hyph     words split at a line end («vor-\nto») — near zero: born-digital layers are reflowed
A corpus is flagged for a fault at: miss+subst ≥ 1% of its words and ≥ 20 words; xsys ≥ 20; bad ≥ 5; lig ≥ 5; hyph ≥ 20.
Output: <stem>-pages.tsv, <stem>-corpora.tsv, and a summary on stdout.
"""
import argparse, glob, os, re, collections, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
LET = re.compile(r"[^\W\d_]", re.UNICODE)
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
XSYS = re.compile(r"(?i)(?<![a-z])[a-z]*(?:cx|gx|hx|jx|sx)[a-z]*")
BAD = re.compile("[-�]")
LIG = re.compile("[ﬀ-ﬆ]")
HYPH = re.compile(r"[^\W\d_]-\n[^\W\d_]", re.UNICODE)
ACC = {"c": "ĉ", "g": "ĝ", "h": "ĥ", "j": "ĵ", "s": "ŝ", "u": "ŭ"}
FOREIGN = set("éèêëàáâäùúüûìíîïòóôöčćšžřťďňĉĝĥĵŝŭ")   # a stand-in glyph may be any of these

EO, ANY = set(), set()
for f in glob.glob(os.path.join(HERE, "lexicons", "*.txt")):
    w = {x.strip().lower() for x in open(f, encoding="utf-8", errors="ignore") if x.strip()}
    ANY |= w
    if os.path.basename(f) == "esperanto.txt":
        EO |= w


def missing_accent(w):
    """w (lower case, in no lexicon) → True if restoring accents on c g h j s u gives an Esperanto word."""
    pos = [i for i, ch in enumerate(w) if ch in ACC]
    if not pos or len(pos) > 6:
        return False
    for k in range(1, len(pos) + 1):
        for sub in itertools.combinations(pos, k):
            v = "".join(ACC[ch] if i in sub else ch for i, ch in enumerate(w))
            if v in EO:
                return True
    return False


def substituted(w):
    """w (lower case, in no lexicon) with foreign accented letters → True if reading them as ĉĝĥĵŝŭ gives an Esperanto word."""
    pos = [i for i, ch in enumerate(w) if ch in FOREIGN]
    if not pos or len(pos) > 3:
        return False
    for combo in itertools.product("ĉĝĥĵŝŭ", repeat=len(pos)):
        v = list(w)
        for i, ch in zip(pos, combo):
            v[i] = ch
        if "".join(v) in EO:
            return True
    return False


def measure(t):
    ws = [w.lower() for w in WORD.findall(t)]
    unk = [w for w in ws if w not in ANY]
    return dict(words=len(ws), miss=sum(1 for w in unk if missing_accent(w)), subst=sum(1 for w in unk if substituted(w)),
                xsys=len(XSYS.findall(t)), bad=len(BAD.findall(t)), lig=len(LIG.findall(t)), hyph=len(HYPH.findall(t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True); ap.add_argument("--kind", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    born = [(c, int(p)) for c, p, _, f in (l.rstrip("\n").split("\t") for l in open(a.kind, encoding="utf-8")) if float(f) < 0.5]
    F = ("words", "miss", "subst", "xsys", "bad", "lig", "hyph")
    pages, per = [], collections.defaultdict(collections.Counter)
    for c, p in born:
        tf = os.path.join(a.root, c, f"page-{p:04d}.tl.txt")
        if not os.path.exists(tf):
            continue
        r = measure(open(tf, encoding="utf-8", errors="ignore").read())
        pages.append((c, p, r)); per[c]["pages"] += 1
        for f in F:
            per[c][f] += r[f]
    with open(a.out + "-pages.tsv", "w", encoding="utf-8") as fh:
        fh.write("corpus\tpage\t" + "\t".join(F) + "\n")
        for c, p, r in pages:
            fh.write(f"{c}\t{p}\t" + "\t".join(str(r[f]) for f in F) + "\n")
    flags, fpages = collections.Counter(), collections.Counter()
    with open(a.out + "-corpora.tsv", "w", encoding="utf-8") as fh:
        fh.write("corpus\tpages\t" + "\t".join(F) + "\taccent_share\tflags\n")
        for c, k in sorted(per.items(), key=lambda z: -z[1]["pages"]):
            share = (k["miss"] + k["subst"]) / k["words"] if k["words"] else 0
            hit = {"accents": share >= 0.01 and k["miss"] + k["subst"] >= 20, "xsys": k["xsys"] >= 20,
                   "bad": k["bad"] >= 5, "lig": k["lig"] >= 5, "hyph": k["hyph"] >= 20}
            for n, h in hit.items():
                if h:
                    flags[n] += 1; fpages[n] += k["pages"]
            fh.write(f"{c}\t{k['pages']}\t" + "\t".join(str(k[f]) for f in F) +
                     f"\t{share:.3f}\t{','.join(n for n, h in hit.items() if h)}\n")
    print(f"born-digital pages with a text layer: {len(pages)} in {len(per)} corpora")
    for n in ("accents", "xsys", "bad", "lig", "hyph"):
        print(f"  {n:8} corpora {flags[n]:4}  pages {fpages[n]:6}")


if __name__ == "__main__":
    main()
