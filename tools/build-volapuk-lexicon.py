#!/usr/bin/env python3
r"""build-volapuk-lexicon — the Volapük word list for the gate (Schleyer's Volapük, 1880–1890s): tools/lexicons/volapuk.txt.

    python3 tools/build-volapuk-lexicon.py [--sources <dir>] [--work <dir>] [--test <sprague text dir>]

WHY (2026-10-17). The Volapük journals (ÖNB's *Volapükabled* 1881–1906 and the rest)
need a list of their own before any cupel (G4). On 2026-10-16 22:0x the editor asked whether a Volapük spellchecker
could be built; at 09:5x the editor had noted that a Volapük dictionary would be a problem, the language being
agglutinative and using prefixes. The sources and method were put to the editor and approved, 22:3x (a proposal, an
internal record, 2026-10-16, not published); built on the editor's approval, 2026-10-17 18:0x.

SOURCES, all retyped or born-digital (never OCR), from temerov's site, saved 2026-10-16 and registered in the
project's web-downloads register (an internal record, not published):
  1. Bik, *Словарь всемирного языка* (Moscow 1886, after Schleyer's 3rd ed.), Morozov's electronic 2nd ed. 2014: the
     base; each line «headword<TAB>Russian gloss»; braces and square brackets in it are Morozov's additions, kept as
     words; «‛» is Schleyer's early sign for h, written both ways; an accent on a vowel marks the stress, both ways.
  2. Schleyer, *Gudumots stämavödas* (1895): «German<TAB>Volapük», variants split at «;» and «,».
  3. Scherzinger, *English dictionary of the roots* (1897, extracts): «root-<TAB>English».
  4. Morozov, *Votükams … 1880–1889*: Schleyer's spellings year by year, four tables of «Russian | German | 1880 |
     1882 | 1885 | 1888» (tables 3–4 without 1880); «ä. b.» (as before) and «n. d.» (not there) skipped.
  5. Ikai, *Vödabuk Volapüka Rigik*: «rigik/nulik (Esperanto)»: the first field only (the reformed form is another
     language for the gate).
Parenthesised letters give both forms («an(s)» → an, ans); a leading or trailing hyphen marks an affix.

INFLECTION, by Sprague's *Hand-book of Volapük* (1888, en.wikisource, proofread):
nouns -a -e -i and the plural -s (-as -es -is); adjectives in -ik with the noun's endings when they
agree, the degrees -um -ün, the adverb -o; verbs: the tense prefixes ä- e- i- o- u- and the passive pa- pä- pe- pi- po-
pu-, the person endings, the plural -s, the moods -öv -öd -ös -öz -öx after the person, the reflexive -ok, the
infinitive -ön and participle -öl in every tense; «-li» (question) and «-la» (conjunctive) are hyphenated and so are
words of their own. Derivation and compounds (vol-a-pük) are not generated: measured first (the proposal's method).

TEST (--test): Sprague's own Volapük (exercises, the key, the reading texts) scored against the list, with the same
text's letters shuffled as the control, as for Latino sine flexione. Lower case. WRITES only the list, a line in
`tools/lexicons/_MANIFEST.md`, and the converted sources in --work.
"""
import os, re, sys, glob, json, random, argparse, subprocess, unicodedata, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "lexicons")
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
SRC = os.path.join(G, "sources", "volapuk.journals", "web-2026-10-16-temerov")
FILES = {"bik": "Bik_Slovar_vsemirnogo_yazyka_2014.docx", "gudumots": "Schleyer_Gudumots_1895.docx",
         "scherzinger": "Scherzinger_1897_Scherz_I_setrats.docx", "votukams": "Morozov_Votuykams_1880_1889.docx",
         "ikai": "Ikai_Vodabuk_Volapuka_Rigik.doc"}
VP = re.compile(r"^[a-zäöüàèìòùáéíóúâêîôûëïÿ‛ƈ'’-]+$", re.I)   # a Volapük word as the dictionaries print it
CYR = re.compile(r"[Ѐ-ӿ]")

CASES = ["", "a", "e", "i", "s", "as", "es", "is"]
PERSONS = ["ob", "ol", "om", "of", "os", "on"]   # Sprague, «Persons»: «OBOLOMOFOSON»; the plural -s on ob ol om of only
PLURAL = {"ob", "ol", "om", "of"}
TENSES = ["", "ä", "e", "i", "o", "u"]   # Sprague, «Tenses»: the present's a- is left out in the active
PASSIVE = ["pa", "pä", "pe", "pi", "po", "pu"]
MOODS = ["", "öv", "öd", "ös", "öz", "öx"]


def text_of(path):
    return subprocess.run(["textutil", "-convert", "txt", "-stdout", path], capture_output=True, text=True,
                          check=True).stdout


def variants(w):
    """parenthesised letters both ways; ‛ as h and dropped; stress accents kept and dropped"""
    out = set()
    stack = [w]
    while stack:
        x = stack.pop()
        m = re.search(r"\(([^()]*)\)", x)
        if m:
            stack += [x[:m.start()] + x[m.end():], x[:m.start()] + m.group(1) + x[m.end():]]
        else:
            out.add(x)
    more = set()
    for x in out:
        for y in {x, x.replace("‛", "h"), x.replace("‛", "")}:
            more.add(y)
            # the stress accents (grave, acute, circumflex on a e i o u), never the umlauts ä ö ü
            more.add("".join(c for c in unicodedata.normalize("NFD", y) if unicodedata.category(c) != "Mn" or
                             c in "̈"))
    return {unicodedata.normalize("NFC", x).lower().strip("’'") for x in more if x}


def heads(field):
    """the Volapük words of one dictionary field: separators, editorial marks and glosses off"""
    field = re.sub(r"[{}\[\]!?.;:„“”«»…]", " ", field)
    words = set()
    for part in re.split(r"[,/\s]+", field):
        part = part.strip()
        if not part or CYR.search(part) or not re.search(r"[a-zäöü]", part, re.I):
            continue
        for v in variants(part):
            if VP.match(v) and (len(v.strip("-")) > 1 or v in "aeiou"):
                words.add(v)
    return words


def read_sources(work):
    os.makedirs(work, exist_ok=True)
    txt = {}
    for k, f in FILES.items():
        p = os.path.join(work, os.path.splitext(f)[0] + ".txt")
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(text_of(os.path.join(SRC, f)))
        txt[k] = open(p, encoding="utf-8").read().splitlines()
    got = {k: set() for k in FILES}
    for l in txt["bik"]:
        f = l.split("\t")
        if len(f) >= 2 and not CYR.search(f[0]):
            got["bik"] |= heads(f[0])
    for l in txt["gudumots"]:
        f = l.split("\t")
        if len(f) >= 2:
            got["gudumots"] |= heads(f[1])
    # Scherzinger: five sections, each with its own columns (the Volapük fields by section)
    sec, cols = None, {"affixes": (0,), "new": (1, 2), "changed": (0,), "obsolete": (0, 1), "improved": (1, 2)}
    for l in txt["scherzinger"]:
        s = l.strip()
        if s == "List of Affixes.": sec = "affixes"; continue
        if s == "List of new words.": sec = "new"; continue
        if s == "Supplements.": sec = "changed"; continue
        if s.startswith("List of obsolete words"): sec = "obsolete"; continue
        if s.startswith("List of improved"): sec = "improved"; continue
        f = l.split("\t")
        if sec and len(f) >= 2:
            for c in cols[sec]:
                if c < len(f):
                    got["scherzinger"] |= heads(f[c])
    # Morozov: cells one per line; a row begins with its Russian cell; the Volapük cells follow the German one
    cells = [c.strip() for c in txt["votukams"] if c.strip()]
    i = 0
    while i < len(cells):
        if CYR.search(cells[i]) and i + 2 < len(cells):
            j = i + 2
            while j < len(cells) and not CYR.search(cells[j]) and not cells[j].startswith("Taib"):
                c = cells[j]
                if c.lower() not in ("ä. b.", "n. d.") and not re.fullmatch(r"1[89]\d\d", c):
                    got["votukams"] |= heads(re.sub(r"\([^)]*[A-ZÄÖÜa-z]{3,}[^)]*\)", " ", c))
                j += 1
            i = j
        else:
            i += 1
    for l in txt["ikai"]:
        if "/" in l and not l.startswith("Vödabuk"):
            got["ikai"] |= heads(l.split("/", 1)[0])
    return got


def inflect(base):
    """every regular form of one headword, by its ending"""
    w = base.strip("-")
    out = {w}
    if base.startswith("-") or base.endswith("-") or len(w) < 2:
        return out                                            # an affix: as listed
    if w.endswith("ön"):
        stem = w[:-2]
        for pre in TENSES + PASSIVE:
            for p in PERSONS:
                for pl in (("", "s") if p in PLURAL else ("",)):
                    for m in MOODS:
                        out.add(pre + stem + p + pl + m)
                        out.add(pre + stem + p + pl + "ok" + m)
            for m in ("öd", "ös", "öz"):
                out.add(pre + stem + m)
            out.add(pre + stem + "ön")
            for c in CASES:
                out.add(pre + stem + "öl" + c)
        return out
    if w.endswith("ik"):
        for deg in ("", "um", "ün"):
            for c in CASES:
                out.add(w + deg + c)
            out.add(w + deg + "o")
        return out
    for c in CASES:
        out.add(w + c)
    return out


UNITS = ["bal", "tel", "kil", "fol", "lul", "mäl", "vel", "jöl", "zül"]


def numerals():
    """Sprague, «Numbers»: units; tens unit+s; tens+e+unit («kilsekil»); unit+tum (100s), unit+mil (1000s); and
    their ordinals -id, the adverbs -o, the cases"""
    base = set(UNITS) | {u + "s" for u in UNITS} | {"tum", "mil", "balion"}
    base |= {u + "se" + v for u in UNITS for v in UNITS}
    base |= {u + "tum" for u in UNITS} | {u + "mil" for u in UNITS}
    out = set()
    for b in base:
        for x in (b, b + "id", b + "idik", b + "ido", b + "o", b + "na", b + "ik"):
            out |= {x + c for c in CASES}
    return out


def volapuk_lines(text, english):
    """the lines of a mixed English/Volapük page that are Volapük: under half of their words English words"""
    out = []
    for l in text.splitlines():
        toks = [t.lower() for t in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", l)]
        if toks and sum(t in english for t in toks) / len(toks) < 0.5:
            out.append(l)
    return "\n".join(out)


def score(text, words):
    toks = [t.lower() for t in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", text)]
    return (sum(t in words for t in toks) / len(toks)) if toks else None, len(toks)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=os.path.join(G, "sources", "ocr-work", "volapuk-list-2026-10-17"))
    ap.add_argument("--test", help="a folder of Sprague's pages as text: score them, with a shuffled control")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    got = read_sources(a.work)
    allheads = set().union(*got.values())
    words = set()
    for h in allheads:
        words |= inflect(h)
    words |= {"li", "la", "o"}
    words |= numerals()
    print(" · ".join(f"{k} {len(v):,}" for k, v in got.items()) + f" → {len(allheads):,} headwords → {len(words):,} forms")
    if not a.no_write:
        out = os.path.join(LEX, "volapuk.txt")
        open(out, "w", encoding="utf-8").write("\n".join(sorted(words)) + "\n")
        man = os.path.join(LEX, "_MANIFEST.md")   # this list's line replaced, not appended again on a re-run
        keep = [l for l in open(man, encoding="utf-8").read().split("\n") if not l.startswith("| volapuk |")]
        open(man, "w", encoding="utf-8").write("\n".join(keep).rstrip("\n") + "\n")
        with open(man, "a", encoding="utf-8") as f:
            f.write(f"| volapuk | Bik 1886/2014, Schleyer 1895, Scherzinger 1897, Morozov's Votükams, Ikai (rigik): "
                    f"{len(allheads):,} headwords, inflected by Sprague 1888: tools/build-volapuk-lexicon.py | 5 | — | "
                    f"{len(words):,} |\n")
        print("→", out)
        # THE PARTS for the analyser (tools/volapuk_analyser.py): stems, compounding heads («x-») and suffixes («-x»)
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
        json.dump(parts, open(os.path.join(LEX, "volapuk-parts.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"→ volapuk-parts.json: stems {len(parts['stems']):,}, heads {len(parts['heads'])}, suffixes {len(parts['suffixes'])}")
    if a.test:
        rnd = random.Random(17)
        rows = []
        english = {w.strip().lower() for w in open(os.path.join(LEX, "english.txt"), encoding="utf-8")}
        for f in sorted(glob.glob(os.path.join(a.test, "*.txt"))):
            t = volapuk_lines(open(f, encoding="utf-8").read(), english)
            s, n = score(t, words)
            sh = " ".join("".join(rnd.sample(w, len(w))) for w in re.findall(r"[a-zäöüA-ZÄÖÜ]{2,}", t))
            s2, _ = score(sh, words)
            if s is not None and n >= 50:
                rows.append((os.path.basename(f), n, s, s2))
        for r in rows:
            print(f"  {r[0]:<60} {r[1]:>6} words  {r[2]:.3f}  shuffled {r[3]:.3f}")
        if rows:
            print(f"median {statistics.median(r[2] for r in rows):.3f} · shuffled {statistics.median(r[3] for r in rows):.3f}")


if __name__ == "__main__":
    main()
