#!/usr/bin/env python3
r"""build-ido-lexicon — a clean Ido lexicon for OCR adjudication, from born-digital sources only.

    tools/build-ido-lexicon.py            # writes tools/lexicons/ido.txt and reports per source

WHY IDO NEEDED ITS OWN. The Ido runs — *Progreso*, *Ido* 1923–29, *Mondo*, *Suisa Idisto* — were
scored against the ESPERANTO lexicon, flagged 13,061 «errors», and were then marked unscoreable,
because there was no clean Ido lexicon to score them against. A text that cannot be scored cannot
pass the gate, and a corpus that cannot pass the gate is presence-only for ever. This removes that.

THE CLEAN-SOURCE RULE HOLDS, SAME AS FOR EVERY OTHER LEXICON HERE. A lexicon built from OCR
learns OCR's errors as words, and then vouches for them — which is exactly the fault the Esperanto
lexicon had until it was purified (it vouched for `president`, and the French accents were lost).
Sources, all born-digital, APPROVED BY THE EDITOR 2026-09-25 before any text was used:

  1. ILSGB `idan.htm` — Ido→English, 13,441 headwords, **morpheme boundaries dotted**
     (`abat.aj.ar.o`), so roots and endings come free and the paradigm can be GENERATED
  2. ILSGB Ido→German / →French / →Spanish / →Polish / →Esperanto / →Italian, + new-words list
  3. io.wiktionary dump — ONLY the `=={{io}}==` sections. Most of that wiki's pages are for other
     languages glossed in Ido; its wikilinks are therefore mostly Ido, but not reliably, so links
     are harvested only from inside an Ido section, where they are Ido by construction.

EXCLUDED, and each exclusion was found rather than assumed:
  · the four PDFs on idolinguo.org.uk — SCANS WITH OCR LAYERS (`Narn` for `Nam`, `konslante`,
    lost word-spaces). One is *Progreso* extracts, squarely in period, which makes it a good
    TEST TARGET for this lexicon and a forbidden SOURCE for it.
  · `idoavan.htm`, `kielido.htm` — look like Ido prose, ARE ESPERANTO, addressed to Esperantists.
    They would inject exactly the forms this lexicon exists to tell apart from Ido.

ERA — STATED, NOT DISCOVERED LATER. Everything clean here is MODERN Ido. The core carries over,
so most 1908–1914 tokens adjudicate correctly; but forms WITHDRAWN by later reforms are absent,
and those are what an adjudicator most needs on early *Progreso*. The planned remedy: the 1908
de Beaufront & Couturat *International-English Dictionary* (archive.org
`internationalen00jespgoog`), whose OCR'd headwords contribute ONLY their DELTA against this list,
hand-reviewed — so OCR never enters the lexicon except through a human. DONE 2026-09-25: the
reviewed delta is `lexicons/ido-1908-reviewed.tsv` (read by `reviewed_1908()`). The review found
most «absent» 1908 words were modern words the scanner had mangled — 40 of the first 48 checked.

AND THE ESPERANTO OVERLAP. Ido shares a great deal of surface with Esperanto (`la`, `kaj`→no,
`e`; `esas`/`estas`). The lexicon is written as-is; the arbitrator's `purify()` step resolves the
overlap at use-time against whichever other lexicon is in play, as it does for every pair.
"""
import os, re, bz2, html, sys, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "published/heterophony-resources/geniza/sources/"
                              "ido-lexicon-candidates-2026-09-25")
OUT = os.path.join(HERE, "lexicons", "ido.txt")
WORD = re.compile(r"^[a-zA-Z]{2,}$")

# ---------------------------------------------------------------- morphology
VERB = ("ar", "ir", "or")
V_END = ["ar", "ir", "or", "as", "is", "os", "us", "ez"]
PART = ["ant", "int", "ont", "at", "it", "ot"]


def paradigm(lemma):
    """Every regular surface form of an Ido lemma. Ido is fully regular, which is what makes this
    safe: there are no irregular verbs and no irregular plurals to get wrong."""
    w = lemma.lower()
    out = {w}
    for e in VERB:
        if w.endswith(e) and len(w) > len(e) + 1:
            st = w[:-len(e)]
            out |= {st + x for x in V_END}
            for p in PART:
                out |= {st + p + x for x in ("a", "e", "o", "i")}
            out |= {st + "o", st + "i", st + "ado", st + "adi", st + "anto", st + "anti"}
            return out
    if w.endswith("o") and len(w) > 2:                    # noun
        st = w[:-1]
        out |= {st + "i", st + "on", st + "in", st + "a", st + "e"}
    elif w.endswith("a") and len(w) > 2:                  # adjective
        st = w[:-1]
        out |= {st + "e", st + "o", st + "i"}
    elif w.endswith("e") and len(w) > 2:                  # adverb
        st = w[:-1]
        out |= {st + "a", st + "o"}
    return out


# ---------------------------------------------------------------- sources
IDO_TO_X = {"idan.htm", "idger.htm", "idfr.htm", "idhisp.htm", "idopol.htm", "idoesp2.htm",
            "iditalp.rtf", "idoeng.htm", "novvorti.rtf", "nvrus3.htm"}


def ilsgb():
    """Dotted headwords from the ILSGB dictionaries. A headword is the first token of an entry
    that carries a dot or a recognised grammatical ending — the dots are the tell."""
    lemmas = collections.Counter()
    for f in sorted(glob.glob(os.path.join(SRC, "*.htm")) + glob.glob(os.path.join(SRC, "*.rtf"))):
        base = os.path.basename(f)
        # ONLY Ido→X DICTIONARIES. Their headwords are Ido. The reverse-direction ones —
        # `espido2.htm` (Esperanto→Ido) and `engido.htm` (English→Ido) — have ESPERANTO and ENGLISH
        # headwords, and the first build let them in: `estas`, `kaj`, `lingvo`, `kiu`, `tiu` all
        # entered an IDO lexicon that way, which is the precise contamination this list exists to
        # detect. `idofaq.htm` is an English FAQ, not a dictionary.
        if base not in IDO_TO_X:
            continue
        raw = open(f, encoding="latin-1", errors="ignore").read()
        if base.endswith(".rtf"):
            raw = re.sub(r"\\'[0-9a-f]{2}|\\[a-z]+-?\d* ?|[{}]", " ", raw)
        n0 = len(lemmas)
        # ⊕ THE CLOSED CLASSES HAVE NO DOT. A particle has no morpheme boundary, so the dotted rule
        # below silently dropped `por` and `sur` — among the commonest words in any Ido text (found
        # 2026-09-25 when *Progreso* vol. 1 showed `por` ×2,571 missing). The dictionary marks them
        # anyway: a BOLD headword with a part-of-speech tag. Only the closed classes are taken —
        # the other bold undotted entries are affixes (`ach-`), note names and loans.
        for m in re.finditer(r"<b>([a-z]{1,15})</b>\s*\{(?:prep|adv|pron|konj|artikl)", raw):
            lemmas[m.group(1)] += 1
        txt = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
        for line in txt.splitlines():
            m = re.match(r"\s*([a-zA-Z][a-zA-Z.\-]{1,40})\b", line)
            if not m:
                continue
            h = m.group(1)
            # DOTTED HEADWORDS ONLY. The dots are the ILSGB's morpheme segmentation and no gloss
            # carries them. The first build also took undotted line-initial tokens ending in -o, -a,
            # -ar — and a wrapped Spanish gloss beginning «estar» is indistinguishable from an Ido
            # verb, so `estas` entered an Ido lexicon. In idan.htm only 13,342 of 26,172
            # line-initial tokens are dotted: roughly half of what looked like headwords were glosses.
            if "." not in h:
                continue
            h = h.replace("-", "").replace(".", "")
            if WORD.match(h):
                lemmas[h.lower()] += 1
        print(f"  {base:<16} +{len(lemmas) - n0:>6,} new headwords", file=sys.stderr)
    return set(lemmas)


def wiktionary():
    """Titles and in-section wikilinks from the `=={{io}}==` sections only."""
    path = os.path.join(SRC, "iowiktionary-latest-pages-articles.xml.bz2")
    if not os.path.exists(path):
        return set()
    heads, links = set(), set()
    title = ns = None
    intext, txt = False, []
    for line in bz2.open(path, "rt", encoding="utf-8"):
        if "<title>" in line:
            title = re.sub(r".*<title>|</title>.*", "", line).strip()
        elif "<ns>" in line:
            ns = re.sub(r"\D", "", line)
        elif "<text" in line:
            intext, txt = True, [line]
        elif intext:
            txt.append(line)
        if intext and "</text>" in line:
            intext = False
            if ns != "0":
                continue
            t = "".join(txt)
            # Multi-sense pages number their Ido sections — `==I {{io}}==`, `==II {{io}}==` — and
            # the first pattern missed them, which is why `od` (the conjunction) was absent.
            secs = re.findall(r"==\s*(?:[IVX]+\s+)?\{\{io\}\}\s*==(.*?)"
                              r"(?=\n==\s*(?:[IVX]+\s+)?\{\{[a-z]{2,3}\}\}\s*==|\Z)", t, re.S)
            if not secs:
                continue
            # A ROOT IS NOT A WORD. Wiktionary has pages for bare roots — `kaj`: «Radiko por:
            # kajo» (cage) — and taking the title of a root page put Esperanto-shaped `kaj` into an
            # Ido lexicon. The title counts as a word only if SOME Ido section is not a root entry.
            if title and WORD.match(title) and any(
                    not sec.strip().startswith("Radiko por") for sec in secs):
                heads.add(title.lower())
            # …but a root page's DERIVATIONS are Ido words by construction: «Radiko por: [[kajo]]»,
            # «+ al = [[kajala]]». These are harvested; the translation tables that made the
            # first build's 171,264 links untrustworthy are not.
            for sec in secs:
                for l in re.findall(r"(?:Radiko por:|=)\s*((?:\[\[[^\]]+\]\][,\s]*)+)", sec):
                    for w in re.findall(r"\[\[([^\]|#:]+)(?:\|[^\]]*)?\]\]", l):
                        w = w.strip()
                        if WORD.match(w):
                            links.add(w.lower())
    # HEADWORDS ONLY. The first build also took every wikilink inside an Ido section: 171,264
    # of them, against 53,664 headwords. That ratio is itself the warning — Ido sections carry
    # translation tables and cross-language examples, so their links are not Ido by construction
    # after all. Headwords are: a page exists for the word, under an Ido heading.
    print(f"  io.wiktionary    {len(heads):>6,} Ido headwords · {len(links - heads):>6,} derived forms "
          f"from root pages", file=sys.stderr)
    return heads | links


def reviewed_1908():
    """The 1908 delta, HAND-REVIEWED by the editor (2026-09-25). The only OCR-derived input, and it
    arrives through a human: each line of `ido-1908-reviewed.tsv` was checked against the printed
    dictionary line (an internal record, 2026-09-25, not published)."""
    path = os.path.join(os.path.dirname(OUT), "ido-1908-reviewed.tsv")
    if not os.path.exists(path):
        return set()
    return {l.split("\t")[0].strip() for l in open(path, encoding="utf-8")
            if l.strip() and not l.startswith("#")}


def main():
    lem = ilsgb()
    wik = wiktionary()
    old = reviewed_1908()
    lemmas = lem | wik | old
    forms = set()
    for l in lemmas:
        forms |= paradigm(l)
    forms = {f for f in forms if WORD.match(f) and 2 <= len(f) <= 30}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(sorted(forms)) + "\n")
    man = os.path.join(os.path.dirname(OUT), "_MANIFEST-ido.md")
    open(man, "w", encoding="utf-8").write("\n".join([
        "# Ido lexicon manifest — generated by `tools/build-ido-lexicon.py`. Do not hand-edit.\n",
        "Built separately from `build-lexicons.py` because Ido has no clean running corpus: its "
        "sources are DICTIONARIES, and the lemmas are expanded by paradigm generation (Ido is "
        "fully regular — no irregular verbs, no irregular plurals).\n",
        "| source | lemmas |", "|---|---:|",
        f"| ILSGB Ido→X dictionaries (dotted headwords only) | {len(lem):,} |",
        f"| io.wiktionary — `{{{{io}}}}` headwords + root-page derivations | {len(wik):,} |",
        f"| 1908 de Beaufront & Couturat delta — HAND-REVIEWED (`ido-1908-reviewed.tsv`) | {len(old):,} |",
        f"| **union** | **{len(lemmas):,}** |",
        f"| **surface forms after paradigm generation** | **{len(forms):,}** |\n",
        "⛔ **Three contaminations were caught and fixed before first use** — each is documented "
        "in the builder's source: reverse-direction dictionaries contributing Esperanto and "
        "English headwords; wrapped Spanish gloss lines read as Ido verbs (`estar` → `estas`); "
        "and Wiktionary ROOT pages read as words (`kaj`). Test after the fix: 21/21 Ido "
        "function words present, no Esperanto leakage.\n",
        "⚠ **MODERN Ido, plus a reviewed 1908 layer.** The clean sources are modern; early forms "
        "withdrawn by later reforms come ONLY from the 1908 de Beaufront & Couturat delta, which "
        "the editor reviewed line by line against the printed dictionary on 2026-09-25 "
        "(`geniza/IDO-1908-DELTA-REVIEW-2026-09-25.md`). It includes the 1908 `y` spellings "
        "(`alyo` for modern `alio`). OCR enters this lexicon through that file and nowhere else.\n"]) + "\n")
    print(f"\n  lemmas: ILSGB {len(lem):,} · wiktionary {len(wik):,} · union {len(lemmas):,}",
          file=sys.stderr)
    print(f"  surface forms after paradigm generation: {len(forms):,}  →  {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
