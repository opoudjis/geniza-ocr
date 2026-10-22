#!/usr/bin/env python3
r"""build-volapuk-reformed-lexicon — the word list for de Jong's reformed Volapük (1931 on): tools/lexicons/volapuk-reformed.txt.

    python3 tools/build-volapuk-reformed-lexicon.py [--work <dir>] [--test] [--no-write]

WHY (2026-10-18). Cupel16 takes *Volapükagased pro Nedänapükans* 1932–39, de Jong's journal (included on the editor's
decision, 21:0x). De Jong's reform (1929–31) changed much of Schleyer's vocabulary, so Schleyer's list (`tools/lexicons/volapuk.txt`,
`tools/build-volapuk-lexicon.py`) would score it low for words it does not hold. The list was put to the editor as
not built yet, and approved by the editor, 21:0x.

SOURCES, retyped or born-digital (never OCR), from temerov's site (saved 2026-10-16 and registered in the project's
web-downloads register, an internal record, not published):
  1. Morozov, *Большой волапюко-русский словарь. Материалы* (DOCX): reformed Volapük, de Jong's vocabulary and the
     Academy's later words. The headword is the first word of an entry line (a trailing homonym number dropped:
     «a-1», «-ab1»); the Volapük examples before « — » in its numbered senses are taken as words too.
  2. Ikai, *Vödabuk Volapüka Rigik*: «rigik / nulik (Esperanto)»: the SECOND field, the reformed form (the Schleyer
     list takes the first).
Inflection, numerals and the word-shape rules are the Schleyer builder's own (imported from it): de Jong kept the
case endings, the person endings, the tense and passive prefixes and the moods. Verbs are listed as headwords only:
their forms are the analyser's (`tools/volapuk_analyser.py` words_for("volapuk-reformed")), as the gate reads them.

TEST (--test): the typed texts of the journal itself (temerov's `vpn_1932_y1.rtf` … `vpn_1939_y8.rtf`) scored against
this list, against Schleyer's, and against the two together, each with the same text's letters shuffled as the control.
The typed journal is a test only, never a source (a list built from the text it scores would measure nothing).
WRITES only the list, its parts (`tools/lexicons/volapuk-reformed-parts.json`, for the analyser), its line in
`tools/lexicons/_MANIFEST.md`, and the converted sources in --work.
"""
import argparse, glob, importlib.util, json, os, random, re, statistics, subprocess, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "lexicons")
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
SRC = os.path.join(G, "sources", "volapuk.journals", "web-2026-10-16-temerov")
_s = importlib.util.spec_from_file_location("bvl", os.path.join(HERE, "build-volapuk-lexicon.py"))
B = importlib.util.module_from_spec(_s); _s.loader.exec_module(B)
FILES = {"morozov": "morozov_bolshoy_vp-ru_slovar.docx", "ikai": "Ikai_Vodabuk_Volapuka_Rigik.doc"}
TESTS = sorted(glob.glob(os.path.join(SRC, "vpn_19*_y*.rtf")))
HEAD = re.compile(r"^(-?[A-Za-zÄÖÜäöü‛'’-]+?-?)\d*(?=[\s\t]|$)")


def read_sources(work):
    os.makedirs(work, exist_ok=True)
    txt = {}
    for k, f in FILES.items():
        p = os.path.join(work, os.path.splitext(f)[0] + ".txt")
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(B.text_of(os.path.join(SRC, f)))
        txt[k] = open(p, encoding="utf-8").read().splitlines()
    got = {"morozov": set(), "morozov-examples": set(), "ikai": set()}
    for l in txt["morozov"]:
        m = HEAD.match(l)
        if m and not B.CYR.search(m.group(1)):
            got["morozov"] |= B.heads(m.group(1))
        for seg in re.findall(r"(?:^|[:;]\s*)([^—:;]+?)\s+—", l):
            if not B.CYR.search(seg):
                got["morozov-examples"] |= {w for w in B.heads(seg) if not w.startswith("-") and not w.endswith("-")}
    for l in txt["ikai"]:
        if "/" in l and not l.startswith("Vödabuk"):
            f = l.split("/", 1)[1]
            got["ikai"] |= B.heads(re.sub(r"\([^)]*\)", " ", f))
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=os.path.join(G, "sources", "ocr-work", "volapuk-reformed-list-2026-10-18"))
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    got = read_sources(a.work)
    allheads = got["morozov"] | got["ikai"]
    words = set()
    for h in allheads:
        # verbs: the headword only; their forms are the analyser's (tools/volapuk_analyser.py: the tense and passive
        # prefixes and the verbal endings on the stem), which keeps the list to a size the gate can hold (enumerated,
        # 10.2 M forms took 1.8 GB in one process, 2026-10-18)
        words |= {h.strip("-")} if h.endswith("ön") else B.inflect(h)
    words |= got["morozov-examples"] | {"li", "la", "o"} | B.numerals()
    print(" · ".join(f"{k} {len(v):,}" for k, v in got.items()) + f" → {len(allheads):,} headwords → {len(words):,} forms")
    if not a.no_write:
        out = os.path.join(LEX, "volapuk-reformed.txt")
        open(out, "w", encoding="utf-8").write("\n".join(sorted(words)) + "\n")
        man = os.path.join(LEX, "_MANIFEST.md")
        keep = [l for l in open(man, encoding="utf-8").read().split("\n") if not l.startswith("| volapuk-reformed |")]
        open(man, "w", encoding="utf-8").write("\n".join(keep).rstrip("\n") + "\n")
        with open(man, "a", encoding="utf-8") as f:
            f.write(f"| volapuk-reformed | Morozov's Большой волапюко-русский словарь (headwords and examples), Ikai (nulik): "
                    f"{len(allheads):,} headwords, inflected as Schleyer's: tools/build-volapuk-reformed-lexicon.py | 2 | — | "
                    f"{len(words):,} |\n")
        stems = set()
        for h in allheads:
            if h.startswith("-") or h.endswith("-"):
                continue
            stems.add(h)
            for e in ("ön", "ik", "o"):
                if h.endswith(e) and len(h) > len(e) + 1:
                    stems.add(h[:-len(e)])
        parts = {"stems": sorted(stems),
                 "heads": sorted(h.rstrip("-") for h in allheads if h.endswith("-") and not h.startswith("-")),
                 "suffixes": sorted(h.lstrip("-") for h in allheads if h.startswith("-") and not h.endswith("-"))}
        json.dump(parts, open(os.path.join(LEX, "volapuk-reformed-parts.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("→", out, f"; parts: stems {len(parts['stems']):,}, heads {len(parts['heads'])}, suffixes {len(parts['suffixes'])}")
    if a.test:
        import sys; sys.path.insert(0, HERE); import volapuk_analyser as VA
        schleyer = VA.VolapukWords()
        if not a.no_write:
            words = VA.words_for("volapuk-reformed")   # the list as written, with the analyser behind it
        both = type("Both", (), {"__contains__": lambda self, w: w in words or w in schleyer})()
        rnd = random.Random(18)
        print(f"{'file':<22}{'words':>8}  reformed  Schleyer  both   (shuffled: reformed)")
        rows = []
        for f in TESTS:
            t = B.text_of(f)
            r, n = B.score(t, words); s, _ = B.score(t, schleyer); u, _ = B.score(t, both)
            sh = " ".join("".join(rnd.sample(w, len(w))) for w in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", t))
            c, _ = B.score(sh, words)
            rows.append((r, s, u, c))
            print(f"{os.path.basename(f):<22}{n:>8}  {r:.3f}     {s:.3f}     {u:.3f}  ({c:.3f})")
        if rows:
            print("median", " ".join(f"{statistics.median(x[i] for x in rows):.3f}" for i in range(4)))


if __name__ == "__main__":
    main()
