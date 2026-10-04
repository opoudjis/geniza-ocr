#!/usr/bin/env python3
r"""ocr-text-languages — the machine EVIDENCE for which languages each text prints, every script, one row per item.

    tools/ocr-text-languages.py <root> <gate.json> --out <tsv>
    e.g. tools/ocr-text-languages.py published/heterophony-resources/geniza/sources/ocr-rendersearch \
         published/heterophony-resources/geniza/ocr/runs/archive/OCR-GATE-2026-10-03-cupel2c-segregated.md.json \
         --out published/heterophony-resources/geniza/ocr/runs/archive/OCR-TEXT-LANGUAGES-EVIDENCE-2026-10-03.tsv

WHY (the editor's ruling, 2026-10-03). The per-text language record (the gate's `all_seconds`) held Latin-script languages
only, so it could not stop the 28 Sep Cyrillic chain: `ocr-cyrillic-detect.py` flagged 220 items by script alone, the
Russian model read every page of each, and Greek (*Helena Esperantisto* 1947), Latin headings and Ido came out as
«Russian» in the companion and the ledger. The editor ruled that the record needs entries for Russian, Greek, Georgian
and Armenian and must track every language, not only Latin-script ones, and that the other-script languages (Ukrainian,
Georgian, Armenian, Greek) be done at once. This tool gathers the evidence; the table itself (`OCR-TEXT-LANGUAGES-<date>.tsv`) is built from it together with the
blind looks and the editor's rulings, and is the filter every pass must consult.

EVIDENCE, per item (a page counts once per column):
  * `primary`, `latin_seconds` — the gate's detected or declared main language and its `all_seconds` (Latin script).
  * `auth_<script>` — pages whose AUTHORITATIVE readings print that script: the editor's keying (`.hand`, `.hand-add`),
    the vision transcriptions (`.vision`, `.vision-add`), and the PDF's own text layer (`.tl`, `.tl-emended`; a
    library's OCR on scans, the printed text on born-digital PDFs). A page counts at >= MIN letters of the script.
    Scripts: cyrillic, greek (modern), greek-polytonic, georgian, armenian, hebrew. Our own Esperanto-model OCR is NOT
    used here: it turns every script into Latin junk, which is what misled the detector.
  * Cyrillic, split by letters only one language uses (on the authoritative readings): `ukr` (є ї ґ), `bel` (ў),
    `srp_mkd` (ђ ј љ њ ћ џ ѓ ќ ѕ), and `rus_letters` (ы э, or the pre-reform ѣ ѳ ѵ).
  * `rus_lex_pages` — pages whose Russian-model reading (`.rus`, `.orus`) has >= RUS_WORDS distinct words of 4+ letters
    in the Russian word list (pre-reform letters folded). Junk Cyrillic from Latin or Greek print does not pass.
  * `rus_read_pages` — pages that have a Russian-model reading at all (what lists A/B of 3 Oct wrongly counted).
  * `kathye_mask` — the item has `MASK-KATHYE.json` (the Georgian/Armenian masking of 27 Sep).
READS ONLY. WRITE-SET: the --out TSV alone, refused if it exists.
"""
import os, re, sys, glob, json, argparse, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ml", os.path.join(HERE, "ocr-mixed-lines.py"))
ml = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ml)

MIN = 20          # letters of a script on a page before the page counts
RUS_WORDS = 15    # distinct Russian-list words (4+ letters) on a page's Russian reading
SCRIPTS = {
    "cyrillic": re.compile(r"[Ѐ-ӿ]"),
    "greek": re.compile(r"[Ͱ-Ͽ]"),
    "greek_polytonic": re.compile(r"[ἀ-῿]"),
    "georgian": re.compile(r"[Ⴀ-ჿᲐ-Ჿ]"),
    "armenian": re.compile(r"[԰-֏]"),
    "hebrew": re.compile(r"[֐-׿]"),
    # 2026-10-04 03:0x (the editor ruled that other scripts are settled by negotiation: Japanese, Arabic, Chinese and Greek
    # are all possible, other Asian scripts unlikely but not ruled out): the table must SEE them to put them to the editor
    "arabic": re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]"),
    "han": re.compile(r"[一-鿿㐀-䶿]"),
    "kana": re.compile(r"[぀-ヿ]"),
    "hangul": re.compile(r"[가-힯ᄀ-ᇿ]"),
    # any other script: Syriac, Ethiopic, Indic, Thai/Lao, Tibetan, Myanmar, Khmer, Mongolian
    "other_script": re.compile(r"[܀-ݏऀ-෿฀-໿ༀ-࿿က-႟ሀ-፿ក-៿᠀-᢯]"),
}
MARK = {"ukr": re.compile(r"[єїґЄЇҐ]"), "bel": re.compile(r"[ўЎ]"),
        "srp_mkd": re.compile(r"[ђјљњћџѓќѕЂЈЉЊЋЏЃЌЅ]"), "rus_letters": re.compile(r"[ыэѣѳѵЫЭѢѲѴ]")}
AUTH = (".hand.txt", ".hand-add.txt", ".vision.txt", ".vision-add.txt", ".tl.txt", ".tl-emended.txt")
CYRW = re.compile(r"[Ѐ-ӿ]{4,}")
FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
PAGE = re.compile(r"page-(\d{4})\.")
W2 = re.compile(r"[^\W\d_]{2,}")
_lx = lambda n: {w.strip() for w in open(os.path.join(HERE, "lexicons", n), encoding="utf-8") if w.strip()}
BG, UK = _lx("bulgarian.txt"), _lx("ukrainian.txt")
BG_NOT = ("объ", "подъ", "съ", "разъ", "изъ", "въ", "отъ", "надъ", "предъ", "межъ", "сверхъ")   # Russian ъ after a prefix


def read(p):
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("gate"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    gate = {r["corpus"]: r for r in json.load(open(a.gate, encoding="utf-8"))}
    _, ru = ml.lists()
    cols = (["item", "in_gate", "primary", "latin_seconds", "pages"] + [f"auth_{s}" for s in SCRIPTS] + list(MARK)
            + ["auth_cyr_words", "auth_rus_words", "auth_ru_letter_words", "auth_bg_words", "auth_uk_words",
               "auth_bg_list_permille", "auth_uk_list_permille", "auth_ru_list_permille",
               "auth_greek_words", "auth_georgian_words", "auth_armenian_words", "auth_hebrew_words",
               "auth_arabic_words", "auth_han_words", "auth_kana_words", "auth_hangul_words", "auth_other_script_words",
               "auth_all_words",
               "rus_lex_pages", "rus_read_pages", "kathye_mask"])
    rows = []
    # 2026-10-03 23:4x (approved by the editor; the W3 review, RUNBOOK.md step C5): a NEW item has page readings (`page-NNNN.txt`,
    # from the conversion) but no `PREFERRED.tsv` until the chain's rebuild — and its languages must be declared, and
    # the table rebuilt, BEFORE its Russian passes, which run before the first chain. So every item folder with page
    # readings is listed, not only those with PREFERRED.tsv; the page count then comes from the page readings.
    dirs = sorted({os.path.dirname(p) for p in glob.glob(os.path.join(a.root, "*", "PREFERRED.tsv"))} |
                  {os.path.dirname(p) for p in glob.glob(os.path.join(a.root, "*", "page-0001.txt"))})
    for d in dirs:
        item = os.path.basename(d)
        files = os.listdir(d)
        auth = collections.defaultdict(str)
        rus = collections.defaultdict(str)
        for f in files:
            m = PAGE.match(f)
            if not m:
                continue
            if f.endswith(AUTH):
                auth[m.group(1)] += "\n" + read(os.path.join(d, f))
            elif f.endswith((".rus.txt", ".orus.txt")):
                rus[m.group(1)] += "\n" + read(os.path.join(d, f))
        c = collections.Counter()
        # 2026-10-03 19:0x (step 3): WHICH language the authoritative Cyrillic is — its distinct 4+-letter words, and how
        # many are in the Russian list. A low share marks non-Russian Cyrillic (Bulgarian: no list yet).
        aw = {w.lower().translate(FOLD).rstrip("ъ") for t in auth.values() for w in CYRW.findall(t)}
        c["auth_cyr_words"] = len(aw); c["auth_rus_words"] = sum(1 for w in aw if w in ru)
        # the share alone does not separate them (Sokolova, Russian: 0.19; the Bulgaria books 0.12–0.16): LETTERS do.
        # ы э ё: Russian only. ъ inside a word, outside Russian prefixes: Bulgarian («българия», «кръстьо»). є ї ґ і: Ukrainian.
        c["auth_ru_letter_words"] = sum(1 for w in aw if re.search("[ыэё]", w))
        c["auth_bg_words"] = sum(1 for w in aw if re.search("ъ.", w) and not w.startswith(BG_NOT))
        c["auth_uk_words"] = sum(1 for w in aw if re.search("[єїґ]", w))
        # 19:2x: the Bulgarian and Ukrainian lists (tools/lexicons/hunspell/SOURCE.md): share of the authoritative Cyrillic
        # words in each, as per-mille (Esperanto_Bulgarien: bg 620, ru 160; Ukraina Stelo: uk 380, ru 100)
        for k, lx in (("bg", BG), ("uk", UK)):
            c[f"auth_{k}_list_permille"] = round(1000 * sum(1 for w in aw if w in lx) / len(aw)) if aw else 0
        c["auth_ru_list_permille"] = round(1000 * c["auth_rus_words"] / len(aw)) if aw else 0
        # 19:5x (approved by the editor): distinct words of EVERY other non-Latin script, so the table can tell a text in Greek from
        # a text CITING Greek (Pabst's *Berlina Komentario*: Greek etymons of the affixes, «ἀπό», «ὑπέρ», on 3–4 pages)
        for s in ("greek", "georgian", "armenian", "hebrew", "arabic", "han", "kana", "hangul", "other_script"):
            rx = SCRIPTS[s] if s != "greek" else re.compile(r"[Ͱ-Ͽἀ-῿]")
            c[f"auth_{s}_words"] = len({m.group(0).lower() for t in auth.values()
                                        for m in re.finditer(rf"(?:{rx.pattern}){{2,}}", t)})
        # 2026-10-04 03:3x (the editor's ruling, Q1: these are citations, the threshold being the greater of 5% or 5 words): the item's
        # distinct words of any script in the authoritative readings, against which a script's words are measured
        c["auth_all_words"] = len({w.lower() for t in auth.values() for w in W2.findall(t)})
        for t in auth.values():
            for s, rx in SCRIPTS.items():
                if len(rx.findall(t)) >= MIN:
                    c[f"auth_{s}"] += 1
            if len(SCRIPTS["cyrillic"].findall(t)) >= MIN:
                for k, rx in MARK.items():
                    if len(rx.findall(t)) >= 3:
                        c[k] += 1
        for t in rus.values():
            words = {w.lower().translate(FOLD).rstrip("ъ") for w in CYRW.findall(t)}
            if sum(1 for w in words if w in ru) >= RUS_WORDS:
                c["rus_lex_pages"] += 1
        g = gate.get(item)
        pref = os.path.join(d, "PREFERRED.tsv")
        npages = (sum(1 for l in open(pref, encoding="utf-8") if re.match(r"\d", l)) if os.path.exists(pref)
                  else sum(1 for f in files if re.fullmatch(r"page-\d{4}\.txt", f)))
        rows.append([item, "yes" if g else "no", (g or {}).get("primary") or "",
                     ",".join(x["lang"] for x in (g or {}).get("all_seconds") or []), str(npages)]
                    + [str(c[k]) for k in cols[5:-3]]   # auth_* scripts, marker letters, the auth_* word counts
                    + [str(c["rus_lex_pages"]), str(len(rus)), "yes" if "MASK-KATHYE.json" in files else ""])
    with open(a.out, "w", encoding="utf-8") as o:
        o.write(f"# GENERATED by tools/ocr-text-languages.py from {a.root} and {os.path.basename(a.gate)}. "
                f"EVIDENCE, not the table; page counts. MIN={MIN} letters, RUS_WORDS={RUS_WORDS}.\n")
        o.write("\t".join(cols) + "\n")
        for r in rows:
            o.write("\t".join(r) + "\n")
    print(f"{len(rows)} items → {a.out}")


if __name__ == "__main__":
    main()
