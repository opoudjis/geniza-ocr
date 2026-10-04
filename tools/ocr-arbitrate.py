#!/usr/bin/env python3
"""ocr-arbitrate — OCR a bilingual page TWICE and merge the two readings TOKEN BY TOKEN.

    tools/ocr-arbitrate.py <file.pdf> [--first N] [--last N] [--out DIR] [--langs epo,fra] [--dpi 300]
    tools/ocr-arbitrate.py --text A.txt B.txt --langs epo,fra      # arbitrate two existing texts

THE PROBLEM THIS SOLVES (2026-09-23). *La Belga Sonorilo* and *L'Espérantiste* are bilingual
French/Esperanto **page by page and column by column**. Their OCR manifests chose a model by ERA
(`-l epo` for 1902–1908), so every French page went through an Esperanto model, which renders
every «é» as «ĉ». Measured on `belgaSonorilo.1908` p040: `-l epo` = 116 ĉ / 0 é; `-l fra` = 0 ĉ /
127 é. The damage is not noise — it is SYSTEMATIC AND SILENT, and it destroys search keys:

    Méray   0 correct / 4 mangled        Dĉlĉgation ×246 — «Délégation», unfindable,
    Gérard  0 correct / 2 mangled        in the corpus that carries the schism.

A persons pass that cannot see Méray and a themes pass that cannot see the Délégation have not
been done; they have been performed.

WHY NOT JUST `-l fra+epo`. Measured, on a real L'Espérantiste page: `epo` 27ĉ/0é · `fra` 0ĉ/38é ·
`fra+epo` **8ĉ/33é** · `epo+fra` **8ĉ/33é** — identical, so ORDER IS IRRELEVANT and a combined
model leaks about a fifth of the accents. Tesseract arbitrates per token, not per language region.
The combined model was never capable of protecting a bilingual page.

WHY NOT PER-LINE ARBITRATION. The editor pointed out on 2026-09-23 that there will be lines of
Esperanto containing French text with diacritics — an Esperanto sentence naming «Délégation» or «Sébert»
would lose its accents to a line-level vote, because the line is mostly Esperanto. Correct.
Hence TOKEN level.

THE RULE, and it never looks at diacritics:
    for each token where the two readings DISAGREE —
      · if the Esperanto reading is a valid Esperanto word  -> keep it        (ĉar, ĉiuj, samideano)
      · else                                                -> take the French reading
    Word-validity decides, not the presence of «ĉ» — which is correct 6,000× and wrong 4,000× in
    the same L'Espérantiste files. A heuristic on «ĉ» would be wrong half the time; this is not.
    Proper names sit in NEITHER dictionary (`sébert` is in no spelling list) and the fallback
    handles them: «Sĉbert» is not possible Esperanto, so the French reading wins by default.

NEVER OVERWRITES. Writes a NEW file beside the old (`page-0040.arb.txt`), plus one `.tags.tsv`
per document recording which model won each token — a per-line language tag, free from the
merge, and evidence in its own right for an organ that ran two columns for two audiences.
"""
import re, sys, os, subprocess, tempfile, pathlib, difflib, collections
import concurrent.futures as _fut

IDO_MODE = False

REPO = pathlib.Path(__file__).resolve().parent.parent
HUNS = REPO / "tools/lexicons/hunspell"

# Esperanto is agglutinative and the dictionary holds STEMS. Strip the regular grammatical
# endings to reach one. The «j» plural must be here: without it `ĉiuj` tested as NOT Esperanto
# and the merge would have overwritten it — 3,807 occurrences in L'Espérantiste alone, silently.
# That defect was found by testing the rule before running it, and it is the reason this stripper
# is explicit rather than clever.
ENDINGS = re.compile(r"(ojn|ajn|oj|aj|on|an|en|oj|j|n|o|a|e|i|is|as|os|us|u)$")


# THE BUILT LEXICON COMES FIRST, AND THIS IS NOT A PREFERENCE (measured 2026-09-24).
# The arbitrator originally read the raw Hunspell `.dic` — **29,906 stems for Esperanto** —
# while `tools/build-lexicons.py` had already built a Tekstaro-derived lexicon of **144,231
# forms** for exactly this job. Esperanto is made of affixes and participles, and the small
# dictionary holds almost none of them: `karega`, `akompanita`, `aplaŭdadojn`, `laŭtaktan` all
# FAIL the stem test, and so does **`kiam`**. Measured on a monolingual Esperanto page, the
# Hunspell test accepts **77.3%** of tokens and the built lexicon **90.2%** — so **12.9% of a
# genuinely Esperanto page was exposed to being overwritten** by whatever the other model said,
# for no reason but which file was opened. It is the founding defect in miniature: a test that
# fails silently and returns plausible text.
#   Visible consequence, Tutmonda Espero 1910 p.95: `karega`→`rarega`, `laŭtaktan`→`laútaltan`,
#   `akompanita`→`alompanita`; p.173 `ĵus kiam`→`ĵus liam`.
# Prefer `tools/lexicons/<language>.txt` (corpus-derived where we have a corpus, Hunspell-
#   derived otherwise, but always the FULL built set); fall back to the raw `.dic` only where no
#   built lexicon exists, and say so on stderr rather than silently using the weaker test.
BUILT = {"eo": "esperanto", "fr": "french", "de": "german", "it": "italian", "es": "spanish",
         "cs": "czech", "sv": "swedish", "nl": "dutch", "pl": "polish", "da": "danish",
         "ca": "catalan", "ru": "russian_post1918", "et": "estonian", "en": "english"}


def load(code):
    s = set()
    built = REPO / "tools/lexicons" / f"{BUILT.get(code, code)}.txt"
    if built.exists():
        for line in built.read_text(encoding="utf-8", errors="replace").splitlines():
            w = line.strip().lower()
            if w:
                s.add(w)
        return s
    p = HUNS / f"{code}.dic"
    print(f"  ⚠ no built lexicon for «{code}» — falling back to the raw Hunspell stems, which is "
          f"a materially weaker test; see the note above.", file=sys.stderr)
    if not p.exists():
        sys.exit(f"missing lexicon {p} — run tools/build-lexicons.py notes / see hunspell/SOURCE.md")
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
        if i == 0 and line.strip().isdigit():
            continue
        w = line.split("/")[0].strip().lower()
        if w:
            s.add(w)
    return s


def deaccent(w):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c))


def purify(primary, primary_code, other):
    """Drop from the PRIMARY lexicon the OTHER language's words that a corpus swept in.

    THE THIRD LEXICON DEFECT, and the one that shows why neither dictionary is right alone
    (measured 2026-09-24, La Belga Sonorilo 1907).

    Fixing the arbitrator to use the 144,231-form Tekstaro lexicon instead of the 29,906
    Hunspell stems recovered ~1,000 Esperanto tokens a volume — and LOST HALF THE FRENCH
    ACCENTS: `présid…` fell from 70 occurrences to 35 in one volume. The cause is not
    subtle once seen. **A corpus lexicon contains whatever the corpus contains**, and
    Esperanto texts quote French:

        president  in Tekstaro yes  in Hunspell —   ← the accent-stripped French form,
        monsieur · groupe · membres · societe · france, all present in Tekstaro
        6,768 forms sit in BOTH the Esperanto and the French lexicon

    So the arbitrator asked «is the Esperanto reading a real Esperanto word?», `president`
    answered yes, and `président` lost. The instrument was vouching for the damage.

    THE ADJUDICATION: coverage from the corpus, VOUCHING from the curated dictionary. A form
      is struck from the primary lexicon when all three hold —
        · it is NOT in the curated (Hunspell) dictionary for this language, which would vouch
          for it — `general` survives on that ground, being genuine Esperanto;
        · its ACCENTED counterpart is a word of the other language — `president` → `président`;
        · it is not reachable by the primary language's own morphology.
      Anything the curated dictionary knows is kept, so the fix cannot cost native vocabulary.
    """
    if not other:
        return primary
    curated = set()
    p = HUNS / f"{primary_code}.dic"
    if p.exists():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
            if i == 0 and line.strip().isdigit():
                continue
            w = line.split("/")[0].strip().lower()
            if w:
                curated.add(w)
    flat = {}
    for w in other:
        flat.setdefault(deaccent(w), w)
    struck = {w for w in primary
              if w not in curated and w in flat and flat[w] != w}
    if struck:
        print(f"  purified: struck {len(struck):,} of {len(primary):,} forms from the primary "
              f"lexicon as the other language's (e.g. "
              f"{', '.join(sorted(struck)[:4])})", file=sys.stderr)
    return primary - struck


# ESPERANTO IS PRODUCTIVE — AFFIXATION *AND* COMPOUNDING (the editor ruled on 2026-09-26 that,
# Esperanto being productive, forms must not be discarded too eagerly: compounds can be taken
# apart, and the Esperanto parser must handle agglutination as well as compounding, e.g. kotizo >
# kotizaĵo, Ruĝa-Kruco). A dictionary never lists every compound. The old test stripped endings
# only, so `kotizaĵo`, `enpresaĵo`, `poŝtsignoj`, `superŝatigita` FAILED it — and the merge then
# took the foreign model's reading, which simply dropped the supersigns: 9,315 hatted Esperanto
# tokens stripped in the first French run. Now a word is Esperanto if, after its grammatical
# ending, it can be SEGMENTED into roots, affixes and linking -o-: generous by design.
EO_PREFIXES = ("bo", "dis", "ek", "eks", "fi", "ge", "mal", "mis", "pra", "re", "ĉef", "vic",
               "sen", "ne", "ali", "for", "kun", "el", "en", "al", "de", "antaŭ", "post", "super",
               "sub", "tra", "trans", "inter", "kontraŭ", "ĉirkaŭ", "sur", "pri", "pro", "preter")
EO_SUFFIXES = ("aĉ", "ad", "aĵ", "an", "ar", "ebl", "ec", "eg", "ej", "em", "end", "er", "estr",
               "et", "id", "ig", "iĝ", "il", "in", "ind", "ing", "ism", "ist", "obl", "on", "op",
               "uj", "ul", "um", "ĉj", "nj", "ant", "int", "ont", "at", "it", "ot")
EO_AFFIXES = set(EO_PREFIXES) | set(EO_SUFFIXES)
EO_HAT = re.compile(r"[ĉĝĥĵŝŭ]")


def make_is_word(stems, agglutinative=False):
    roots = None

    def root_set():
        nonlocal roots
        if roots is None:
            roots = set()
            for w in stems:
                r = w
                for _ in range(3):
                    r2 = ENDINGS.sub("", r)
                    if r2 == r:
                        break
                    r = r2
                if len(r) >= 2:
                    roots.add(r)
        return roots

    import functools

    @functools.lru_cache(maxsize=200000)
    def segments(s, depth=0):
        """Can s be cut into roots/affixes, with an optional linking -o- between pieces?"""
        if s == "":
            return True
        if depth > 6:
            return False
        R = root_set()
        for k in range(min(len(s), 14), 1, -1):
            head = s[:k]
            if head in R or head in EO_AFFIXES:
                rest = s[k:]
                if segments(rest, depth + 1):
                    return True
                if rest.startswith("o") and segments(rest[1:], depth + 1):
                    return True
        return False

    def compositional(w):
        base = w
        for _ in range(3):
            b2 = ENDINGS.sub("", base)
            if b2 == base:
                break
            base = b2
        if base == w or len(base) < 3:
            return False                       # needs a grammatical ending and a real stem
        R = root_set()
        # at least one piece must be a CONTENT root of ≥ 3 letters, so affix soup is not a word
        return segments(base) and any(base[i:j] in R and j - i >= 3
                                      for i in range(len(base)) for j in range(i + 3, len(base) + 1))

    def is_word(w):
        lw = w.lower()
        if lw in stems:
            return True
        if not agglutinative:
            return False
        if "-" in lw:
            parts = [p for p in lw.split("-") if p]
            return bool(parts) and all(is_word(p) for p in parts)
        x = lw
        for _ in range(3):
            x2 = ENDINGS.sub("", x)
            if x2 == x:
                break
            if x2 in stems or (x2 + "i") in stems or (x2 + "o") in stems or (x2 + "a") in stems:
                return True
            x = x2
        # LOCAL, NOT GLOBAL (measured 2026-09-26): the compound test applies only to words CARRYING
        # SUPERSIGNS — the class the fix is for (`kotizaĵo`, `superŝatigita`). Applied to plain-letter
        # words it let mangled French pass as Esperanto via the corpus's foreign stems:
        # `Congrès`→`Congris`, `prospérité`→`prosperite` (UEA 1906 lost 34 accents).
        return compositional(lw) if EO_HAT.search(lw) else False
    return is_word


WORD4 = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def page_language(text_a, text_b, is_a_word, is_b_word):
    """Which language does THIS PAGE mostly belong to? Returns 'A' or 'B'.

    WHY THE TIEBREAK MOVED FROM THE CORPUS TO THE PAGE (editor, 2026-09-24).

    The Belga Sonorilo rule was «keep the Esperanto reading iff it is a valid Esperanto word,
    else take the other model's». Against FRENCH that default is nearly free: French and
    Esperanto share little enough surface that an Esperanto-valid token on a French page is
    rare. Against CATALAN it is not free at all. `natura`, `forma`, `causa`, `problema`,
    `materia` are valid in both, so on a genuinely Catalan page the Esperanto-first default
    holds the Esperanto reading of word after word — and the failure is invisible, because
    every token it keeps IS a real word of the language it was tested against.

    On a page that is mostly Catalan, the Catalan reading should be the one kept-if-valid.
      The rule is unchanged — «keep the reading that is a real word of this page's language» —
      but «this page's language» is now measured per page instead of assumed per corpus.

    The measure is deliberately crude and deliberately EXCLUSIVE: tokens of ≥4 letters that
    are valid in one language and NOT the other. Shared vocabulary is exactly what cannot
    decide this question, so it is discarded rather than weighted. A page with no exclusive
    evidence either way keeps the primary — silence defers to the corpus, it does not guess.
    """
    a, b = 0, 0
    for w in {m.group(0).lower() for m in WORD4.finditer(text_a + " " + text_b)}:
        ia, ib = is_a_word(w), is_b_word(w)
        if ia and not ib:
            a += 1
        elif ib and not ia:
            b += 1
    return "B" if b > a else "A", a, b


def ocr(img, lang, dpi):
    out = tempfile.mktemp()
    subprocess.run(["tesseract", str(img), out, "-l", lang, "--oem", "1"],
                   capture_output=True, check=False)
    p = pathlib.Path(out + ".txt")
    t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    p.unlink(missing_ok=True)
    return t


# THE IDO CASE — three arbiters, because three languages need three (the editor proposed fr+io+eo on
# 2026-09-23, since French is found all over Ido texts, and chunks of Esperanto as well).
# Tesseract has NO Ido model (checked: 163 languages installed, no `ido`; none upstream either), and
# the local Ido text — 21 wikitext files, 112 KB — is far too thin for a lexicon beside the 1.3M
# tokens that gave us Occidental. But an Ido lexicon turns out not to be needed:
#
#   token is valid Esperanto            -> keep the Esperanto reading      (lexicon)
#   else token is valid French          -> take the French reading         (lexicon)
#   else (i.e. it is Ido)               -> take whichever reading has NO Esperanto diacritic
#
# The third rule is sound in Ido and ONLY in Ido. In the bilingual French
# organs «ĉ» is genuinely ambiguous — correct Esperanto 6,000× and broken French 4,000× in the same
# L'Espérantiste files — so a diacritic heuristic there would be wrong half the time. **In Ido it
# cannot occur at all**: de Beaufront's reform removed the supersigned letters, so ĉĝĥĵŝŭ in an Ido
# passage is not evidence, it is an impossibility. That makes it an INDEPENDENT ASSERTION rather
# than a guess — which is why it is enabled only by --ido, never inferred.
IDO_IMPOSSIBLE = re.compile(r"[ĉĝĥĵŝŭĈĜĤĴŜŬ]")

# THE GUARD — ARBITRATION IS ONLY VALID WHERE THE BASELINE USED THE WRONG MODEL.
#
# Learned the hard way, 2026-09-23 20:12, on *Belga Sonorilo* 1910 and 1912. Those years were
# OCR'd `eng+fra+ita` — no Esperanto model — so their FRENCH WAS ALREADY CORRECT. Running the
# epo/fra arbitration over them made the text WORSE, because the rule keeps the Esperanto reading
# whenever the token looks like valid Esperanto, and the agglutinative stripper is permissive
# enough to accept French words as Esperanto:
#
#     Lemaire  56 -> 36        général  35 -> 15        Société  18 -> 3
#
# Both outputs were quarantined and the originals were untouched (the never-overwrite rule doing
# its job). **Before running, read the corpus MANIFEST for the model that produced the existing
# text.** The Belga Sonorilo manifest (an internal record, not published) says it in as many words — «-l epo for
# 1902–1908, -l eng+fra+ita for 1910+» — and it was written down before any of this started.
#
# Rule: arbitrate a corpus ONLY if its existing text was produced under a model that could not
# render one of its languages. If the baseline already used the right model, arbitration can only
# lose. --force exists for deliberate exceptions and must be justified in the checklist.
BASELINE_WARNING = """
⛔ REFUSING: no --baseline given.

Arbitration repairs text produced under the WRONG language model. Run over text that already used
the right one, it DEGRADES it (Belga Sonorilo 1910: Lemaire 56->36, général 35->15, Société 18->3).

Read the corpus MANIFEST for the model that produced the existing text, then pass it:
    --baseline epo        the existing text used an Esperanto model  -> arbitrating fra is VALID
    --baseline fra        the existing text already used French      -> arbitration is NOT valid
    --baseline none       no existing text (a fresh conversion)      -> always valid
"""


def arbitrate(text_a, text_b, is_a_word):
    """a = the agglutinative/primary reading (kept when valid), b = the fallback reading."""
    A, B = text_a.split(), text_b.split()
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    out, tags = [], collections.Counter()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.extend(A[i1:i2]); tags["same"] += i2 - i1
        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                x = A[i1 + k] if i1 + k < i2 else None
                y = B[j1 + k] if j1 + k < j2 else None
                if x is None:
                    out.append(y); tags["B"] += 1; continue
                if y is None:
                    out.append(x); tags["A"] += 1; continue
                core = re.sub(r"[^\w]", "", x.lower())
                if core and is_a_word(core):
                    out.append(x); tags["A"] += 1
                elif IDO_MODE and IDO_IMPOSSIBLE.search(x) and not IDO_IMPOSSIBLE.search(y):
                    # Ido cannot carry a supersigned letter: the reading that has one is wrong.
                    out.append(y); tags["B_ido"] += 1
                elif IDO_MODE and IDO_IMPOSSIBLE.search(y) and not IDO_IMPOSSIBLE.search(x):
                    out.append(x); tags["A_ido"] += 1
                else:
                    out.append(y); tags["B"] += 1
        elif tag == "delete":
            out.extend(A[i1:i2]); tags["A"] += i2 - i1
        elif tag == "insert":
            out.extend(B[j1:j2]); tags["B"] += j2 - j1
    return " ".join(out), tags


def main():
    global IDO_MODE
    av = sys.argv[1:]
    IDO_MODE = "--ido" in av
    base = av[av.index("--baseline") + 1] if "--baseline" in av else None
    if base is None and "--force" not in av:
        sys.exit(BASELINE_WARNING)
    if base not in (None, "none", "epo", "eo") and "--force" not in av:
        sys.exit(f"⛔ REFUSING: baseline '{base}' already used the right model — arbitration would "
                 f"only lose. Use --force with a justification in the checklist if you disagree.")
    langs = (av[av.index("--langs") + 1] if "--langs" in av else "epo,fra").split(",")
    dpi = av[av.index("--dpi") + 1] if "--dpi" in av else "300"
    code = {"epo": "eo", "fra": "fr", "deu": "de", "ita": "it", "spa": "es",
            "ces": "cs", "swe": "sv", "nld": "nl", "pol": "pl", "dan": "da",
            "cat": "ca"}
    lex_a, lex_b = load(code[langs[0]]), load(code[langs[1]])
    lex_a = purify(lex_a, code[langs[0]], lex_b)
    is_a = make_is_word(lex_a, agglutinative=(langs[0] == "epo"))
    per_page = "--per-page-tiebreak" in av
    # Exclusive second-language token TYPES a page must carry before it is arbitrated at all.
    # 10 is where the measured gains start; below it the merge only loses. See the guard below.
    gate = int(av[av.index("--page-gate") + 1]) if "--page-gate" in av else 10
    jobs = int(av[av.index("--jobs") + 1]) if "--jobs" in av else max(1, (os.cpu_count() or 4) - 2)
    is_b = make_is_word(purify(lex_b, code[langs[1]], lex_a), agglutinative=(langs[1] == "epo")) if per_page else None

    if "--text" in av:
        i = av.index("--text")
        a = pathlib.Path(av[i + 1]).read_text(encoding="utf-8", errors="replace")
        b = pathlib.Path(av[i + 2]).read_text(encoding="utf-8", errors="replace")
        merged, tags = arbitrate(a, b, is_a)
        sys.stdout.write(merged + "\n")
        sys.stderr.write(f"  same {tags['same']} · kept {langs[0]} {tags['A']} · took {langs[1]} {tags['B']}\n")
        return

    pdf = pathlib.Path(av[0])
    first = av[av.index("--first") + 1] if "--first" in av else "1"
    last = av[av.index("--last") + 1] if "--last" in av else first
    out = pathlib.Path(av[av.index("--out") + 1]) if "--out" in av else pdf.parent / (pdf.stem + ".arb")
    out.mkdir(parents=True, exist_ok=True)
    tsv = [f"# token arbitration · {pdf.name} · {langs[0]} vs {langs[1]} · {dpi} dpi"
           + (" · PER-PAGE tiebreak" if per_page else ""),
           "page\tsame\tkept_" + langs[0] + "\ttook_" + langs[1] + ("\tpage_lang\texcl_" + langs[0]
           + "\texcl_" + langs[1] if per_page else "")]
    # ONE PAGE IS ONE INDEPENDENT JOB, so the pages run in parallel. Each page is two
    # tesseract passes and a diff, sharing nothing with any other page — the sequential loop
    # this replaces used ONE core of eighteen, and a 429-page volume took 58 minutes for want
    # of a thread pool. Tesseract is told OMP_THREAD_LIMIT=1: N single-threaded processes beat
    # one process with N threads for page-at-a-time work, and without it the pool and OpenMP
    # fight for the same cores.
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")

    def do_page(img):
        n = int(re.search(r"(\d+)$", img.stem).group(1))
        ta, tb = ocr(img, langs[0], dpi), ocr(img, langs[1], dpi)
        if per_page:
            which, ea, eb = page_language(ta, tb, is_a, is_b)
            if eb < gate:
                # THE PAGE-LEVEL BASELINE GUARD (measured 2026-09-24, six pages of
                # Tutmonda Espero 1908). The volume-level guard asks «did the existing text
                # use the wrong model?». It is not enough, because a bilingual VOLUME is
                # made of monolingual PAGES. Offering a Catalan model to a page with no
                # Catalan on it is not neutral: wherever the Esperanto reading fails the
                # lexicon the merge takes the Catalan one, and on a monolingual page that
                # trade is always bad. Measured, on pages with zero exclusive Catalan:
                # 94.0%→90.9%, 89.2%→82.3%, 88.6%→83.2%. On the pages that do carry
                # Catalan: 75.0%→77.0% and 75.5%→80.8%. Same run, same settings.
                # A page below the floor is PASSED THROUGH UNARBITRATED, not merged.
                merged, tags = ta, collections.Counter({"same": len(ta.split())})
                extra, flag = f"\t—\t{ea}\t{eb}", "  ·untouched"
            elif which == "B":
                # This page is mostly the second language: IT becomes the kept-if-valid
                # reading. Same rule, different page.
                merged, t = arbitrate(tb, ta, is_b)
                tags = collections.Counter({"same": t["same"], "A": t["B"], "B": t["A"]})
                extra, flag = f"\t{which}\t{ea}\t{eb}", "  ←second-language page"
            else:
                merged, tags = arbitrate(ta, tb, is_a)
                extra, flag = f"\t{which}\t{ea}\t{eb}", ""
        else:
            merged, tags = arbitrate(ta, tb, is_a)
            extra, flag = "", ""
        (out / f"page-{n:04d}.arb.txt").write_text(merged + "\n", encoding="utf-8")
        return (n, f"{n}\t{tags['same']}\t{tags['A']}\t{tags['B']}{extra}",
                f"  page {n:>4}  same {tags['same']:>5} · kept {langs[0]} {tags['A']:>4} · "
                f"took {langs[1]} {tags['B']:>4}{flag}")

    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-f", first, "-l", last, "-r", dpi, "-gray",
                        str(pdf), td + "/p"], capture_output=True, check=False)
        imgs = sorted(pathlib.Path(td).glob("p-*"))
        done = []
        with _fut.ThreadPoolExecutor(max_workers=jobs) as pool:
            for n, row, line in pool.map(do_page, imgs):
                done.append((n, row)); print(line)
        tsv += [row for _, row in sorted(done)]
    (out / "ARBITRATION.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
