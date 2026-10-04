#!/usr/bin/env python3
r"""ocr-quality-scan.py — which text extractions are too corrupt to trust, and why.

    tools/ocr-quality-scan.py                # scan geniza sources, write the report
    tools/ocr-quality-scan.py --top 40       # print the worst N to stdout as well

WHY. The editor noted on 2026-09-05 that there was a great deal to go through, and that some
files seemed to need re-OCR. True, and previously only ever noticed one file at a time, in the middle of
doing something else — the *Bibliografio* scout found the Milter primer's title corrupt in
BOTH held copies, in different places, and neither prints `meždunarodnogo` correctly. That
kind of discovery is luck. This makes it a list.

IT RANKS SUSPICION, IT DOES NOT CONDEMN. Every measure here is a proxy. A text can score
badly and be fine (a dictionary is mostly short tokens; a bibliography is mostly numerals),
and a text can score well and still be missing pages. **The output is a queue to inspect,
never a verdict to act on** — and re-OCR is expensive, so nothing here should be run without
the editor choosing it.

AND IT NEVER TOUCHES ANYTHING. Standing project rule, from the 2026-09-04 destruction of
two irreplaceable extractions: nothing under `sources/` is deleted or moved, ever. This
script only reads. A re-OCR, when one is decided on, writes a NEW file beside the old one.

THE MEASURES, and what each is actually detecting:

  diacritic-loss   the killer for this corpus. Esperanto/Ido/Slavic-romanised texts should
                   carry ĉĝĥĵŝŭ / čžš / ’. archive.org's djvu layer FLATTENS them — which is
                   exactly why `Milter` returned one hit and `Mil'tjer` four. A text whose
                   language demands diacritics and shows none is not merely ugly, it is
                   UNSEARCHABLE FOR THE NAMES WE ARE HUNTING.
  junk-token       proportion of tokens that are neither a word nor a number — the classic
                   scanner-noise signature.
  short-token      proportion of 1–2 character tokens; column-bleed and broken ligatures
                   shatter words into fragments.
  vowel-less       lines carrying no vowel at all: dead scan lines.
  words/page       against the `=== page N ===` markers where present. A page averaging under
                   ~120 words was probably half-captured. NO markers is itself reported —
                   the content-test the project runs on every extraction.
"""
import os, re, sys, glob, unicodedata
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(REPO, "published", "heterophony-resources", "geniza")
SRC = os.path.join(GEN, "sources")
OUT = os.path.join(GEN, "OCR-QUALITY-SCAN.md")

DIACRITIC = set("ĉĝĥĵŝŭČĈĜĤĴŜŬčžšćłńśźżáàâäéèêëíìîïóòôöúùûüñõãåøæœ’ʼ")

# IDO HAS NO DIACRITICS. THIS IS THE WHOLE POINT OF IDO.
#
# The first version of this scan flagged `NiaStandardo1922No2` and every page of Jacob's
# *Kontributaji* as "DIACRITICS STRIPPED — names unsearchable", top of the ranking, because
# the language test matched Ido function words (`linguo`, `esas`, `quo`, `ma`) alongside
# Esperanto ones. But de Beaufront's reform REMOVED the supersigned letters — a text in clean,
# perfectly-OCR'd Ido contains none by design. The scan was proposing to re-OCR sound files,
# and would have sent the editor an expensive queue topped by its own error (caught 2026-09-05
# before the list was acted on).
#
# So: require diacritics ONLY where the language actually uses them. Esperanto (ĉĝĥĵŝŭ),
# Slavic romanisation (č/ž/š, the soft-sign apostrophe) and the western European languages
# (French, German, Portuguese) do; Ido, Latin and English do not. The test is on the text,
# never the filename.
# DISTINCTIVE FORMS ONLY. The first attempt put `la`, `pri`, `ne`, `por` in the Esperanto
# list — all four are equally Ido — so the Esperanto count won every comparison and Ido texts
# were never detected. Ido is a REFORM of Esperanto: most function words are shared, and only
# the reformed ones discriminate. Esperanto `kaj/estas/tiu/kiu/ĝi` ↔ Ido `ed/esas/ta/qua/ol`.
ESPERANTO = re.compile(r"\b(kaj|estas|estis|tiu|kiu|ĉiu|ankaŭ|ĝi|ŝi|ili|nia|kiel|jam)\b", re.I)
IDO = re.compile(r"\b(esas|esis|quo|qua|quan|ta|ito|ol|ilu|elu|dil|dal|kande|nulu|lore|ed|ma|ye|pro|kom)\b", re.I)
ROMANCE_GERMANIC = re.compile(r"\b(les|des|dans|nous|über|nicht|werden|não|são)\b", re.I)


def needs_diacritics(text):
    """True only where the language genuinely carries diacritics — see the Ido note above."""
    head = text[:400000]
    eo, ido = len(ESPERANTO.findall(head)), len(IDO.findall(head))
    # Ido and Esperanto share function words, so decide by MARGIN, not by presence.
    if ido > eo:
        return False                       # Ido: correctly diacritic-free
    return eo > 40 or len(ROMANCE_GERMANIC.findall(head)) > 40
WORD = re.compile(r"[A-Za-zÀ-ÿĀ-ſ'’]+")
TOKEN = re.compile(r"\S+")

# CHECK 12 — LETTERSPACED OCR. `K o f m a n` instead of `Kofman`.
#
# WHY THIS IS ITS OWN CHECK AND NOT A CASE OF "fragmented". Letterspacing is what happens when
# the scanner meets a passage the typesetter set with extra tracking — in German and Central
# European printing that is the house convention for EMPHASIS, and emphasis in a prosopography
# falls on NAMES. So the defect concentrates on exactly the tokens we are searching for, and the
# file otherwise looks fine: normal diacritics, normal word count, normal page density. The
# existing `short` measure scores it as merely «fragmented — N% tokens ≤2 chars», which reads as
# *degraded, re-OCR sometime* rather than *every name-grep against this file is unreliable*.
#
# Found 2026-09-06 in the Forster extract: 385 letterspaced lines, and the 2026-09-02 scout's
# null list was built on it. «Kofman — not mentioned» was wrong; he is at l.6676, letterspaced.
# ONE null flipped, but that was unknowable without re-running every one of them.
#
# Signature: four or more consecutive single-letter tokens. Four, not three, because genuine
# prose throws up runs of three (`a i o` in a vowel table, `I a m`), and because initials are
# excluded separately — `A. A. Postnikov` carries periods and must not fire.
LETTERSPACED = re.compile(r"(?:(?<=\s)|^)(?:[^\W\d_]\s+){3,}[^\W\d_](?=[\s,.;:]|$)", re.M)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# CHECK 13 — LEXICAL HIT-RATE. The blind spot, found 2026-09-23.
#
# Every measure above detects a failure of SHAPE: junk tokens, letterspacing, fragmentation,
# dead lines, stripped diacritics. There is a whole failure class they cannot see — OCR that
# produces PLAUSIBLY-SHAPED NONSENSE. Right token lengths, right line counts, right page
# density, words shaped like words that are not words. Such a file passes every test here.
#
# It cost the venture real evidence. The ANNO *Helvetia* 1929–33 extractions went through this
# scanner and landed in «clean enough not to flag» — `19320053.txt` at 8,981 tokens over 25
# pages — while its masthead OCRs as «Avv ccioLiowporj». Kofman's «Reminiscenties
# interlinguistic», attested by *Cosmoglotta* A 84 for the March–June 1932 numbers we hold,
# returns ZERO hits for «reminisc» across all four. The same class hid the January 1911
# removals in `oge.3`, where the three struck-off men print as «Avicov, Jamix, kaj ScaxgEencen»
# — no name search could ever have found them, and a wrong name sat in the dossier for weeks.
# The rule the arc depends on — «not in the OCR» ≠ «not in the record» — has no teeth
# without a measure that can tell the difference. This is that measure.
#
# METHOD: the proportion of word tokens of length >= 3 that are real words of the language the
# file is actually in. Word-shaped garbage still fails a dictionary. Bands measured on the
# bench (13:12): clean Occidental self-test 0.93-0.95 · ANNO Helvetia 1932 0.74-0.83 ·
# bitarkivo Kosmoglott 1922-26 0.47-0.50 — the last far worse than anything previously recorded.
#
# TWO CAUTIONS, both learned by testing (do not relax either):
#  1. The lexicon must come from GENUINELY CLEAN text. Built from other OCR, the bands collapse
#     and nothing separates. See tools/build-lexicons.py.
#  2. The measure is PER-LANGUAGE and a hit-rate against the wrong lexicon is meaningless. Where
#     the language is not one we hold a clean lexicon for, the measure REPORTS NOTHING rather
#     than guessing — silence is the honest answer, and this tool exists to stop false
#     confidence, not to manufacture it. As of 2026-09-23 that means Ido, French, German and
#     Russian extractions are not scored.
LEXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicons")
# Discriminative function words. Deliberately NOT the commonest words — `de`, `li`, `in`, `e`
# are shared across these languages and decide nothing. These are markers that are frequent in
# one and rare or absent in the others.
LANG_MARKERS = {
    "occidental": {"quel", "anc", "ma", "ti", "vel", "pos", "che", "tam", "mem", "sam",
                   "hay", "ci", "on", "ples", "nequande", "ilu", "noi", "vu", "li", "es"},
    "esperanto":  {"kaj", "estas", "kun", "sed", "tiu", "pri", "oni", "ĉiu", "kiel", "nur",
                   "jam", "ankaŭ", "tamen", "tiam", "ĉar", "kvankam", "esperanto", "lingvo"},
    # Scored from 2026-09-25. Markers chosen ABSENT from Esperanto and Occidental, so that an
    # Ido text wins detection outright rather than sharing it — the same design that stopped
    # Novial cannibalising Helvetia.
    "ido":        {"esas", "esis", "esos", "ed", "od", "ka", "kad", "nam", "quale", "omna",
                   "ica", "ita", "olu", "elu", "irga", "singla", "forsan", "yen", "dil", "til"},
}
# LANGUAGES WE CAN RECOGNISE BUT MUST NOT SCORE. Detection is not enough: the tool also has
# to know when to SHUT UP. Without this table the scan's first run flagged 13,061 extractions,
# and its top eight corpora were `ocr/Ido.*` — thousands of pages of perfectly good Ido scored
# against the Esperanto lexicon, because Ido shares `kun`, `nur`, `jam`, `pri`, `ma`, `on` with
# the two languages we hold and so cleared the marker bar. The caution above, exactly: «the measure
# is per-language, and a hit-rate against the wrong lexicon is meaningless». These markers are
# chosen to be absent from Esperanto and Occidental, so that a text in one of these languages
# WINS detection and is then reported as unscoreable rather than as bad.
# Remove a language from here only by adding a clean lexicon for it in tools/build-lexicons.py.
UNLEXICONED_MARKERS = {
    # IDO REMOVED FROM THIS TABLE 2026-09-25 — it now has a clean lexicon
    #    (tools/lexicons/ido.txt, built by tools/build-ido-lexicon.py) and is SCORED; its markers
    #    moved to LANG_MARKERS above. This is the exit the rule below describes.
    # DISTINCTIVE AGAINST OCCIDENTAL, which Novial closely resembles. The first version of
    # this set included li/ma/pos/sam — all four equally Occidental — and it CANNIBALISED the
    # detection: Helvetia 1932, the file this check was built to catch, began winning as
    # «novial» (unscoreable) and fell straight back into «clean enough not to flag». Novial's
    # discriminators are its own grammar words: the -um/-en forms, `blimen`, `sel`, `vud`.
    "novial": {"vud", "sal", "blim", "blimen", "sel", "somen", "nulum", "omnum", "kelkum",
               "questum", "disum", "talum", "lo", "les", "nus", "vus", "mem"},
    "french":  {"les", "des", "une", "dans", "pour", "qui", "que", "est", "sont", "avec",
                "cette", "nous", "vous", "leur", "plus", "mais", "tout", "être", "ont"},
    "german":  {"und", "der", "die", "das", "nicht", "eine", "auch", "auf", "aber", "sich",
                "werden", "wurde", "durch", "nach", "über", "sind", "haben", "einer"},
    "russian": {"что", "как", "это", "для", "был", "она", "все", "его", "или", "при",
                "так", "если", "было", "года", "него", "они", "мы", "уже"},
}
# DECLARED CORPORA — the brief for this check allows the language to be detected OR declared per corpus, and
# declaration is the honest answer where detection cannot be trusted. Marker detection fails on
# badly-OCR'd text in a language close to one we score: *Novialiste* 1938–39 persistently reads
# as degraded Occidental (0.63) because its own grammar words are mangled, so Novial's
# discriminators never fire. Rather than tune markers until a number looks right, declare the
# corpus. Substring match on the path, longest match wins; value None = do not score.
DECLARED = {
    "Novialiste": None,        # Novial — no clean lexicon
    # Ido DECLARED AND SCORED from 2026-09-25 (it was `None`, «no clean lexicon»). A value
    # here OVERRIDES detection, so moving Ido into LANG_MARKERS alone would have left these runs
    # unscored — the declaration had to change too.
    "/Ido.": "ido", "Ido.19": "ido",
    "Progreso": "ido",
    "suisian": "ido",          # Suisa Idisto
    # NOT «mondo» — *Mondo* is Ido but *La Bela Mondo* and *Tra la Mondo* are Esperanto, and a
    #   substring would catch all three. Mondo is left to marker detection, which now knows Ido.
    "historio-ru/": None,      # Russian
    # 2026-09-27, the editor ruled that the wrong language had been declared, and approved the fix — both had been scored as Esperanto:
    "1909-Ritz-Speech": "english",   # the 1909 Ritz speech (Tasmania) — lexicon: tools/lexicons/english.txt (web2)
    "dragoumis-1881": None,          # Dragoumis 1881 — Greek (katharevousa); no Greek lexicon, so NOT scored
    # 2026-09-27, approved by the editor: Ido-named items that detect as Esperanto — declared Ido
    "Epigrami-ido-vivo": "ido", "Idomarcho": "ido",
    "Idowoti": "ido",                # Estonian FRAKTUR: its low G4 is the typeface, not the language
    # 2026-09-27 16:20, the editor ruled that the rest were fine as plain Ido, and the Spanish course mixed Spanish
    # and Ido (Ido primary, its Spanish credited as a second language). NOT the Internacia lernolibro por
    # Esperantistoj: measured mostly Esperanto (1,805 Esperanto-only vs 588 Ido-only words) — detection right.
    "/Idoguide.": "ido", "/Olimpialaludi2016.": "ido", "/ambicio.": "ido", "/korokanti.": "ido",
    "/latviana.": "ido", "/sundiala.": "ido", "/vivo.": "ido", "/kursoidoenlahispana.": "ido",
    # 2026-09-28 01:06, the editor approved the suggested fixes (the presence-only breakdown):
    "/belgasonorilo.1912.11.": "ido",   # reads as Ido; detection chose Occidental because of a Romanal specimen
    "Contribution_of_A_Jakstas-Dambrauskas": "english",   # an English-language paper
    "Carlevaro - Lalortel Radicarium": "english",         # Carlevaro's radicarium: English apparatus
    "/1.": "ido",                    # Astro Idista no. 1 (archive-org-ido/astro_idista_1/1.pdf, unique name) — Brazilian, Portuguese + Ido; included by the editor, 16:21
}


def declared_for(path):
    hit, best = "MISS", 0
    for frag, lang in DECLARED.items():
        if frag in path and len(frag) > best:
            hit, best = lang, len(frag)
    return hit


_LEX = {}


def lexicon(lang):
    """Lazily load a lexicon; None if we hold no clean one for this language."""
    if lang not in _LEX:
        p = os.path.join(LEXDIR, lang + ".txt")
        try:
            with open(p, encoding="utf-8") as fh:
                _LEX[lang] = {w.strip() for w in fh if w.strip()}
        except OSError:
            _LEX[lang] = None
    return _LEX[lang]


def detect_lang(words):
    """Which lexicon (if any) applies. Marker-frequency, NOT best-hit-rate — scoring a file
    against every lexicon and keeping the winner would label a French page as bad Occidental,
    which is exactly the false confidence this check exists to prevent."""
    if not words:
        return None
    low = [w.lower() for w in words]
    n = len(low)
    best, best_rate, scoreable = None, 0.0, False
    # Score EVERY language we can recognise, lexiconed or not, and let them compete. If an
    # unlexiconed language wins, the answer is None — «we know what this is and cannot judge it»
    # — which is the honest result and the one that keeps thousands of clean Ido pages out of
    # the register.
    for lang, markers in list(LANG_MARKERS.items()) + list(UNLEXICONED_MARKERS.items()):
        rate = sum(1 for w in low if w in markers) / n
        if rate > best_rate:
            best, best_rate, scoreable = lang, rate, lang in LANG_MARKERS
    # 1.5% of tokens being this language's markers is a low bar in absolute terms and a decisive
    # one in practice: a text in an unrelated language does not clear it even when degraded.
    if best_rate < 0.015 or not scoreable:
        return None
    return best if lexicon(best) else None


def measures(text, path=""):
    toks = TOKEN.findall(text)
    if len(toks) < 200:
        return None
    words = WORD.findall(text)
    junk = sum(1 for t in toks if not WORD.fullmatch(t.strip(".,;:!?()[]«»\"'—–-"))
               and not re.fullmatch(r"[\d.,/–—-]+", t))
    short = sum(1 for w in words if len(w) <= 2)
    lines = text.splitlines()
    body = [l for l in lines if len(l.strip()) > 12]
    vowelless = sum(1 for l in body if not re.search(r"[aeiouAEIOUàéíóúäëïöü]", l))
    dia = sum(1 for c in text if c in DIACRITIC)
    lines_all = [l.strip() for l in lines if l.strip()]
    # Uniqueness must be measured on line SHAPE, not on the literal line. `Seite 1 von 99`,
    # `Seite 2 von 99` … are 99 DISTINCT strings and one single piece of boilerplate. Normalising
    # digits away collapses them, and separates a null extraction from a real text cleanly:
    # Romanal1917 scores 0.08, its own re-OCR 0.93, Lins 0.98. (The literal-line version of this
    # test scored Romanal1917 at 0.54 and did not fire — 2026-09-05.)
    shapes = {re.sub(r"\d+", "#", l) for l in lines_all}
    uniq = len(shapes) / max(len(lines_all), 1)
    pages = len(re.findall(r"===\s*page\s+\d+\s*===", text, re.I))
    # Letterspacing is counted per LINE, not per match: one affected line is one place a name
    # can be hiding, and a line often carries several runs. Samples are kept so the report can
    # SHOW the defect — a count alone does not let the reader judge a false positive.
    ls_hits, ls_init = [], 0
    for i, l in enumerate(text.splitlines()):
        m = LETTERSPACED.search(l)
        if not m:
            continue
        ls_hits.append((i + 1, l.strip()))
        # THE DISCRIMINATOR (editor, 2026-09-06, from the Sperrdruck point). Deliberate
        # letterspacing in the SOURCE is a heading/emphasis convention and sits LINE-INITIAL;
        # an OCR artefact strikes wherever it likes, mid-sentence. Measured: EdE 75% initial
        # (sub-headings: `S v e d u j o`, `K o m e r c o`), Forster 29% (`As B o d m e r
        # remarks`), Tartuensis 5%. A high initial-fraction means the damage is CONFINED to
        # a predictable target class and the file's body prose is searchable; a low one means
        # it is loose in the running text, where the names are.
        if m.start() - (len(l) - len(l.lstrip())) <= 2:
            ls_init += 1
    # CHECK 13 — lexical hit-rate (see the block above). Length >= 3 because two-letter
    # tokens are mostly function words and are the part OCR gets right even when it is failing.
    # MINIMUM SAMPLE. Marker detection on a few hundred words is a coin-toss, and per-page
    # extracts (`oge.3/page-0001.txt` and its thousands of siblings) were generating most of the
    # residual noise in the first runs — a page of tabular matter or a masthead is not evidence
    # about a corpus. Below this floor the measure reports nothing, like any other honest sample.
    dec = declared_for(path)
    if dec != "MISS":
        lang = dec                      # declared: None means «known, unscoreable»
    else:
        lang = detect_lang(words) if len(words) >= 600 else None
    lex = lexicon(lang) if lang else None
    if lex:
        cand = [w.lower() for w in words if len(w) >= 3]
        lex_rate = (sum(1 for w in cand if w in lex) / len(cand)) if cand else None
        lex_n = len(cand)
    else:
        lex_rate, lex_n = None, 0
    return {
        "lang": lang, "lex_rate": lex_rate, "lex_n": lex_n,
        "tokens": len(toks),
        "junk": junk / len(toks),
        "short": short / max(len(words), 1),
        "vowelless": vowelless / max(len(body), 1),
        "dia_per_kw": 1000.0 * dia / max(len(words), 1),
        "uniq": uniq, "nlines": len(lines_all),
        "needs_dia": needs_diacritics(text),
        "pages": pages,
        "wpp": len(words) / pages if pages else 0,
        "ls_lines": len(ls_hits),
        "ls_frac": len(ls_hits) / max(len(lines_all), 1),
        "ls_sample": [h[1][:110] for h in ls_hits[:3]],
        "ls_first": ls_hits[0][0] if ls_hits else 0,
        "ls_init": ls_init / max(len(ls_hits), 1),
    }


def verdict(m):
    """-> (score, list of reasons). Score is a suspicion rank, nothing more."""
    why, s = [], 0.0
    # NULL EXTRACTION — a file that LOOKS like a text extract and contains no source text.
    #
    # `ocr/Romanal1917.txt` is 416 lines and 560 words: a library catalogue header, 99 repetitions
    # of the holding library's URL, and «Seite N von 99». NOT ONE WORD OF MICHAUX. The earlier
    # version of this scan flagged it as "junk tokens 20%; fragmented" — i.e. as DEGRADED OCR,
    # which reads as «re-do it» rather than «every grep you run against this returns a false
    # null». In an arc whose method is reading silences, a file that answers every question
    # with silence is the single most dangerous artefact on disk, and it is worse than a missing
    # file because a missing file cannot be searched by mistake. Detected 2026-09-05 by a scout,
    # not by this tool; the check exists so that never happens again.
    #
    # Signature: a tiny proportion of DISTINCT LINE SHAPES. Not words-per-line and not literal
    # line uniqueness — both were tried and both failed on the very file that prompted the check.
    if m["nlines"] >= 50 and m["uniq"] < 0.30:
        why.append(f"★★ NULL EXTRACTION — only {m['uniq']:.0%} of {m['nlines']} lines are "
                   f"distinct in SHAPE: repeated boilerplate, not source text. "
                   f"EVERY GREP AGAINST THIS FILE RETURNS A FALSE NULL")
        s += 20
    # CHECK 12 — LETTERSPACED. Ranked second only to null extraction, and for the same reason:
    # both produce FALSE NULLS rather than visible damage. Twenty affected lines is enough to hide
    # a name; the threshold is deliberately low because the cost of a missed name in this arc is a
    # published claim that somebody was «not mentioned».
    # THE TWO CASES ARE NOT THE SAME DEFECT AND MUST NOT CARRY THE SAME WARNING (corrected
    # 2026-09-06, same night, on the editor's Sperrdruck point — my first version told him every
    # «not in the EdE» null had to be re-run, which was FALSE and was the day's sixth over-claim).
    #
    # SPERRDRUCK is the German compositor's emphasis convention — deliberate, systematic, and
    # aimed at a predictable class. In the *Enciklopedio de Esperanto* 1933 it marks SUB-HEADINGS:
    # of 72 affected lines, 71 are topics and countries (`S v e d u j o`, `K o m e r c o`,
    # `B l i n d u l o j`) and exactly ONE is a personal name — `G r a b o w s k i`, who is
    # abundantly attested elsewhere in the same book. **Exposure to name-nulls: effectively nil.**
    # (Goudy: *"anyone who would letterspace lowercase would steal sheep"* — the convention these
    # files preserve is precisely the one he was insulting.)
    #
    # THE ARTEFACT is OCR mangling ordinary running text, and it lands mid-sentence, on names,
    # unpredictably: Forster, `As B o d m e r remarks`. THAT is what voids a null.
    if m["ls_lines"] >= 20 and m["ls_init"] < 0.55:
        why.append(f"★★ LETTERSPACED IN RUNNING TEXT — {m['ls_lines']} lines ({m['ls_frac']:.1%}), "
                   f"only {m['ls_init']:.0%} line-initial, first at l.{m['ls_first']}. Loose in the "
                   f"body prose, where the NAMES are. ⚠ ANY «not mentioned» FINDING FROM THIS FILE "
                   f"IS UNRELIABLE AND MUST BE RE-RUN SPACE-TOLERANTLY")
        s += 12
    elif m["ls_lines"] >= 20:
        why.append(f"Sperrdruck convention — {m['ls_lines']} lines, {m['ls_init']:.0%} line-initial: "
                   f"deliberate heading/emphasis letterspacing, not OCR damage. Body prose is "
                   f"searchable; inspect before treating any null as void")
        s += 1
    elif m["ls_lines"] >= 5:
        why.append(f"letterspacing present — {m['ls_lines']} lines, first at l.{m['ls_first']} "
                   f"(check any null taken from this file)")
        s += 2
    # CHECK 13 — LEXICAL HIT-RATE. Ranked with null-extraction and letterspacing, because it
    # is the same kind of defect: it produces FALSE NULLS rather than visible damage. Thresholds
    # are set from the bench (clean 0.93-0.95; Helvetia 0.74-0.83; Kosmoglott 0.47-0.50), with
    # the first band deliberately catching Helvetia — the file this check was built to see.
    if m["lex_rate"] is not None:
        if m["lex_rate"] < 0.60:
            why.append(f"★★ LEXICALLY UNSOUND ({m['lang']}) — only {m['lex_rate']:.0%} of "
                       f"{m['lex_n']:,} words are real words. The text is word-SHAPED and largely "
                       f"not words: every «not mentioned» finding from this file is worthless, and "
                       f"positive quotations must be checked at the page")
            s += 18
        elif m["lex_rate"] < 0.86:
            why.append(f"★★ LEXICALLY DEGRADED ({m['lang']}) — {m['lex_rate']:.0%} of "
                       f"{m['lex_n']:,} words are real words (clean text scores 0.93–0.95). "
                       f"⚠ Shape-based measures CANNOT see this: names and titles are mangled "
                       f"into plausible non-words, so NULLS FROM THIS FILE ARE NOT NULLS")
            s += 13
        elif m["lex_rate"] < 0.91:
            why.append(f"lexical hit-rate {m['lex_rate']:.0%} ({m['lang']}) — mild; check any "
                       f"null taken from this file")
            s += 2
    if m["needs_dia"] and m["dia_per_kw"] < 1.0:
        why.append(f"★ DIACRITICS STRIPPED ({m['dia_per_kw']:.1f}/1000 words) — names unsearchable")
        s += 5
    elif m["needs_dia"] and m["dia_per_kw"] < 5.0:
        why.append(f"diacritics sparse ({m['dia_per_kw']:.1f}/1000)")
        s += 1.5
    if m["junk"] > 0.18:
        why.append(f"junk tokens {m['junk']:.0%}")
        s += 3 * m["junk"]
    if m["short"] > 0.30:
        why.append(f"fragmented — {m['short']:.0%} tokens ≤2 chars")
        s += 3 * m["short"]
    if m["vowelless"] > 0.06:
        why.append(f"{m['vowelless']:.0%} dead lines")
        s += 4 * m["vowelless"]
    if m["pages"] and m["wpp"] < 120:
        why.append(f"only {m['wpp']:.0f} words/page over {m['pages']} pages — half-captured?")
        s += 2
    if not m["pages"]:
        why.append("no `=== page N ===` markers (cannot content-test per page)")
        s += 0.5
    return s, why


def main():
    rows = []
    for p in glob.glob(os.path.join(SRC, "**", "*.txt"), recursive=True):
        try:
            text = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        m = measures(text, p)
        if not m:
            continue
        s, why = verdict(m)
        rows.append((s, os.path.relpath(p, SRC), m, why))
    rows.sort(key=lambda r: -r[0])

    flagged = [r for r in rows if r[0] >= 2.0]
    stripped = [r for r in rows if any("DIACRITICS STRIPPED" in w for w in r[3])]
    spaced = sorted([r for r in rows if r[2]["ls_lines"] >= 5],
                    key=lambda r: -r[2]["ls_lines"])

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# OCR quality scan — geniza sources\n\n")
        fh.write("**GENERATED by `tools/ocr-quality-scan.py`. Do not hand-edit — re-run it.**\n\n")
        fh.write(f"**{len(rows)} extractions scanned · {len(flagged)} flagged for inspection · "
                 f"{len(stripped)} with diacritics stripped.**\n\n")
        fh.write("⚠ **This ranks SUSPICION; it does not condemn.** Every measure is a proxy. A "
                 "dictionary is legitimately full of short tokens; a bibliography is legitimately "
                 "full of numerals. **Inspect before re-OCRing anything** — re-OCR is expensive "
                 "and is the editor's call, not the script's.\n\n")
        fh.write("⚠⚠ **Nothing under `sources/` is ever deleted or moved.** A re-OCR writes a NEW "
                 "file beside the old one. (Standing rule since two irreplaceable extractions "
                 "were destroyed on 2026-09-04 by a guard that tested existence rather than "
                 "content.)\n\n")
        fh.write("★ **Why diacritic-loss leads the ranking.** It is not cosmetic. The archive.org "
                 "djvu layer flattens `č/ž/š` to `c/z/s` and drops the soft-sign apostrophe — "
                 "which is precisely why `Milter` returned one hit in the *Bibliografio* and "
                 "`Mil'tjer` returned four, and why the man at the centre of this arc was invisible "
                 "for weeks. **A stripped text is not merely ugly; it is unsearchable for the very "
                 "names we are hunting.** Where a stripped copy has a cleaner twin (the "
                 "`carlevaro/text/B8` case), prefer the twin and cite it.\n\n")
        fh.write("| rank | extraction | why |\n|---|---|---|\n")
        for s, name, m, why in flagged:
            fh.write(f"| {s:.1f} | `{name}` | {'; '.join(why)} |\n")
        # The letterspacing register is written SEPARATELY from the suspicion table, because it
        # is not a quality judgement — it is a list of files whose NULLS are void. A reader of the
        # ranked table sees «letterspaced» as one defect among several; this section says what to
        # do about it.
        fh.write(f"\n---\n\n## ★★ LETTERSPACED EXTRACTIONS — nulls taken from these are void "
                 f"({len(spaced)})\n\n")
        fh.write("⚠ **The defect that hid Kofman.** Letterspacing (`K o f m a n`) is how Central "
                 "European printing sets EMPHASIS, and in a prosopography emphasis falls on "
                 "**names** — so this corruption concentrates on precisely the tokens the venture "
                 "searches for, while leaving the file looking healthy on every other measure. "
                 "Found 2026-09-06 in the Forster extract (385 lines), where it had already "
                 "invalidated a scout's «not mentioned» list from 2026-09-02.\n\n")
        fh.write("⇒ **What to do:** do NOT re-OCR. Search these files **space-tolerantly** — build "
                 "the pattern `K\\s*o\\s*f\\s*m\\s*a\\s*n` rather than `Kofman`. ⚠ **And re-run "
                 "every null already recorded against a file in this list**; a null from here is "
                 "not evidence of absence.\n\n")
        if spaced:
            fh.write("| lines | % | line-initial | kind | extraction | sample |\n"
                     "|---|---|---|---|---|---|\n")
            for s, name, m, why in spaced:
                sample = (m["ls_sample"][0] if m["ls_sample"] else "").replace("|", "\\|")
                kind = ("**⚠ artefact**" if m["ls_init"] < 0.55 and m["ls_lines"] >= 20
                        else "Sperrdruck" if m["ls_init"] >= 0.55 else "minor")
                fh.write(f"| **{m['ls_lines']}** | {m['ls_frac']:.1%} | {m['ls_init']:.0%} | {kind} "
                         f"| `{name}` | `{sample}` |\n")
        else:
            fh.write("*None at or above the 5-line threshold.* ⚠ Reported as a **content result**, "
                     "not as «not checked»: the scan ran over every extraction below.\n")
        fh.write(f"\n---\n\n## Clean enough not to flag ({len(rows)-len(flagged)})\n\n")
        fh.write("Listed so an absence from the flagged table is legible as *scanned and passed*, "
                 "not *not scanned*.\n\n")
        for s, name, m, why in rows[len(flagged):]:
            fh.write(f"- `{name}` — {m['tokens']:,} tokens"
                     + (f", {m['pages']} pages" if m["pages"] else "") + "\n")

    print(f"{len(rows)} extractions · {len(flagged)} flagged · {len(stripped)} diacritics stripped "
          f"· {len(spaced)} letterspaced")
    print("wrote", os.path.relpath(OUT, REPO))
    n = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 0
    for s, name, m, why in flagged[:n]:
        print(f"  {s:5.1f}  {name}\n         {'; '.join(why)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
