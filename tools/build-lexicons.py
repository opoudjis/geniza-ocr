#!/usr/bin/env python3
"""build-lexicons — word-type lexicons from GENUINELY CLEAN text, for the OCR lexical measure.

  build-lexicons.py [--min-freq 3] [--out tools/lexicons]

Writes one `<lang>.txt` per language (one lowercased word type per line) plus `_MANIFEST.md`
recording, per language, the sources used, the file count, the token count and the type count.

WHY THE SOURCE MUST BE CLEAN (2026-09-23 — the caution that makes or breaks
this): a lexicon built from OCR contains the OCR's own errors as legitimate words, and the bands
COLLAPSE — everything scores well and nothing separates. This was tested exactly and seen to
fail. So every source registered here must be either born-digital text or a transcription, never
an OCR extraction. If you add a language, add it from clean text or do not add it.

WHY THE MEASURE IS PER-LANGUAGE: a hit-rate is meaningless against the wrong lexicon. A clean
French page scored against Occidental looks like garbage. Where no clean lexicon exists for a
language, the scanner must SKIP the measure and say so — never guess, never score against a
near neighbour. As of 2026-09-23 the repo holds ELEVEN lexicons: occidental and esperanto from
clean corpora, plus french/german/spanish/czech/italian/swedish/dutch/polish and post-1918
russian from Hunspell stem lists. Still deliberately ABSENT, and reported as «no lexicon»:
**Ido, Novial, Interlingua** (no dictionary published for these) and **pre-revolutionary
Russian** (the 1918 reform: see hunspell/SOURCE.md).

Registered sources (add here, with provenance, when a clean corpus arrives):
  occidental — the cosmoglotta/occidental-lang-1927-42/*.html transcriptions (146 files, the
               born-digital occidental-lang.com transcriptions; an earlier bench test used these and got
               0.93–0.95 self-test against 0.74–0.83 for the ANNO Helvetia OCR)
  esperanto  — ../tekstaro_de_esperanto_html_sen_streketoj (the Tekstaro de Esperanto, curated
               transcriptions, «sen streketoj» = the clean phrase-greppable build)
"""
import shutil, subprocess, re, sys, html, pathlib, collections

REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCES = {
    "occidental": [REPO / "published/heterophony-resources/geniza/sources/cosmoglotta/occidental-lang-1927-42"],
    "esperanto": [REPO.parent / "tekstaro_de_esperanto_html_sen_streketoj"],
}
# Hunspell stem lists — MEMBERSHIP word-lists, not corpora. Fetched 2026-09-23; provenance and
# licences in tools/lexicons/hunspell/SOURCE.md. These satisfy the «clean source» rule by
# construction: a spelling dictionary contains no OCR errors.
# EXPANDED with each dictionary's own affix rules (`.aff`, unmunch) from 2026-09-26; before that
# they were STEM lists and inflected forms missed (`journaux`, `jeunes`).
# Compare a file only against its own language's baseline — never across languages.
# ru = POST-1918 ORTHOGRAPHY ONLY (0 final-ъ, 0 ѣ/і/ѳ/ѵ, measured). Pre-revolutionary Russian
# is declared UNSCOREABLE in ocr-quality-scan.py, not scored against this.
HUNSPELL = {"french": "fr", "german": "de", "spanish": "es", "czech": "cs", "italian": "it",
            "swedish": "sv", "dutch": "nl", "polish": "pl", "russian_post1918": "ru",
            "danish": "da", "catalan": "ca",
            # 2026-10-14 (on the editor's request for Portuguese): Brazila Esperantisto's second language (cupel11);
            # wooorm/dictionaries `pt` = VERO, Brazilian Portuguese (LGPL-3.0 OR MPL-2.0); MODERN spelling, the
            # pre-1943 orthography («approvarem») under-credited (hunspell/SOURCE.md)
            "portuguese": "pt",
            # 2026-09-27 (approved by the editor): second languages of Estlanda Esperantisto, Latviana and Dambrauskas,
            # which had no word list and so could not earn credit. GREEK built too (at the editor's request, though
            # the editor expected it not to help) — the hunspell list is MODERN monotonic; 1947 Helena Esperantisto prints
            # polytonic katharevousa, so its Greek stays PRESENCE ONLY (treated like Armenian).
            "estonian": "et", "latvian": "lv", "lithuanian": "lt",   # greek REMOVED 16:25 (on the editor's decision to remove it)
            # 2026-10-03 (approved by the editor): the language table found Bulgarian and Ukrainian texts and had no list to
            # confirm them (geniza/ocr/runs/archive/OCR-TEXT-LANGUAGES-2026-10-03.tsv); same source, licences in hunspell/SOURCE.md
            "bulgarian": "bg", "ukrainian": "uk",
            # 2026-10-17 (the editor chose option b, then approved): the base of the Latino sine flexione list
            # (tools/build-lsf-lexicon.py; an internal record, 2026-10-17, not published); wooorm/dictionaries `la` = Karl Zeiler's Latin 3.1 (2013)
            "latin": "la",
            # 2026-10-12 (at the editor's request to add Slovak to the gate): cupel9's Gašparíková & Pollák 1987 is Slovak, and the
            # gate had no list for it (a Slovak page scored against Czech is not a measurement); same source, hunspell/SOURCE.md
            "slovak": "sk"}
HUNSPELL_DIR = REPO / "tools/lexicons/hunspell"
# STEMS ONLY for these (2026-09-27): affix expansion gave Lithuanian 36.4 M forms (634 MB) and Estonian
# 15.0 M (227 MB) — too heavy to load, and a false-credit risk. Measured on 31,193 junk tokens (Cyrillic
# read as Latin): stems match 0.69% (lt) / 1.23% (et), under French's 2.40% baseline; Latvian EXPANDED 1.70%.
STEMS_ONLY = {"estonian", "lithuanian"}
WORD = re.compile(r"[^\W\d_]{2,}", re.U)
LETTERS = re.compile(r"[^\W\d_]+", re.U)
TAG = re.compile(r"(?is)<(script|style|head)[^>]*>.*?</\1>|<[^>]+>")


def text_of(p):
    raw = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() in (".html", ".htm"):
        raw = html.unescape(TAG.sub(" ", raw))
    return raw


def main():
    argv = sys.argv[1:]
    minf = int(argv[argv.index("--min-freq") + 1]) if "--min-freq" in argv else 3
    out = pathlib.Path(argv[argv.index("--out") + 1]) if "--out" in argv else REPO / "tools/lexicons"
    out.mkdir(parents=True, exist_ok=True)
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None   # build just these; manifest APPENDED
    manifest = ["# Lexicon manifest — generated by `tools/build-lexicons.py`. Do not hand-edit.",
                "",
                f"Minimum type frequency: **{minf}**. Sources must be clean (born-digital or "
                "transcribed), never OCR — see the script's docstring for why.",
                "",
                "| language | sources | files | tokens | types kept |",
                "|---|---|---|---|---|"]
    for lang, dirs in ({} if only else SOURCES).items():
        freq, files, toks, used = collections.Counter(), 0, 0, []
        for d in dirs:
            if not d.exists():
                print(f"  ⚠ {lang}: source missing, skipped — {d}", file=sys.stderr)
                continue
            used.append(str(d))
            for p in sorted(d.rglob("*")):
                if p.suffix.lower() not in (".html", ".htm", ".txt") or not p.is_file():
                    continue
                ws = [w.lower() for w in WORD.findall(text_of(p))]
                if not ws:
                    continue
                files += 1
                toks += len(ws)
                freq.update(ws)
        if not freq:
            print(f"  ⚠ {lang}: NO LEXICON BUILT (no readable source)", file=sys.stderr)
            continue
        kept = sorted(w for w, n in freq.items() if n >= minf)
        (out / f"{lang}.txt").write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"  {lang}: {files} files, {toks:,} tokens, {len(kept):,} types -> {out / (lang + '.txt')}")
        manifest.append(f"| {lang} | {'<br>'.join(used)} | {files} | {toks:,} | {len(kept):,} |")
    for lang, code in HUNSPELL.items():
        if only and lang not in only:
            continue
        src = HUNSPELL_DIR / f"{code}.dic"
        if not src.exists():
            print(f"  ⚠ {lang}: {src} missing, skipped", file=sys.stderr); continue
        words = set()
        for i, line in enumerate(src.read_text(encoding="utf-8", errors="replace").splitlines()):
            if i == 0 and line.strip().isdigit():
                continue                      # first line is the entry count
            w = line.split("/")[0].strip().lower()
            w = re.sub(r"^\+\w+=", "", w)       # uk.dic marks some entries «+cs=…» (2026-10-03)
            if w and not w.isdigit():
                words.add(w)
        # INFLECTED FORMS (2026-09-26: the editor ruled that the inflections are absolutely needed). The
        # stems alone held `journal` and `jeune` but not `journaux` and `jeunes`, and EVERY
        # «is this a real word?» test downstream ran on them: the second-model merge, G2's density
        # and G4's bilingual credit. Hunspell's own affix rules (`<code>.aff`, same source) expand
        # them with `unmunch` — still a clean source: the rules are the dictionary's own.
        aff, how = HUNSPELL_DIR / f"{code}.aff", "stems"
        if aff.exists() and shutil.which("unmunch") and lang not in STEMS_ONLY:
            r = subprocess.run(["unmunch", str(src), str(aff)], capture_output=True)
            for line in r.stdout.decode("utf-8", errors="replace").splitlines():
                w = line.split("/")[0].strip().lower()
                # LETTERS ONLY: Catalan's clitic and Italian's elision rules generate tens of millions
                # of hyphen/apostrophe forms (`donar-li-ho`, `dell'`) — 1.0 GB for Catalan — which no
                # tokeniser here ever produces (they split on both).
                if w and LETTERS.fullmatch(w):
                    words.add(w)
            how = "stems + affix expansion"
        kept = sorted(words)
        (out / f"{lang}.txt").write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"  {lang}: hunspell {code}.dic ({how}), {len(kept):,} forms -> {out / (lang + '.txt')}")
        manifest.append(f"| {lang} | hunspell `{code}.dic`{' + `' + code + '.aff` (unmunch)' if how != 'stems' else ''} "
                        f"(see hunspell/SOURCE.md) | 1 | — | {len(kept):,} |")
    manifest.append("\n⊕ **Ido** is built separately, from dictionaries rather than a running corpus, "
                    "by `tools/build-ido-lexicon.py` — see `_MANIFEST-ido.md`.")
    if only:   # --only: APPEND the new rows; never overwrite the full manifest (it was, once, 2026-09-27)
        with open(out / "_MANIFEST.md", "a", encoding="utf-8") as f:
            f.write("\n".join(l for l in manifest if l.startswith("| ") and not l.startswith("| language")) + "\n")
    else:
        (out / "_MANIFEST.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"  manifest -> {out / '_MANIFEST.md'}")


if __name__ == "__main__":
    main()
