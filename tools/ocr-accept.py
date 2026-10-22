#!/usr/bin/env python3
r"""ocr-accept — the acceptance gate. A corpus passes all four checks, or it does not pass.

    tools/ocr-accept.py <root>                    # gate every corpus under a root
    tools/ocr-accept.py <root> --corpus NAME      # one corpus
    tools/ocr-accept.py <root> --write REPORT.md

THE CONTRACT (an internal record, frozen 2026-09-24, not published). **There is no partial
acceptance and no «accepted pending».** A corpus that fails is fixed and re-gated BEFORE anyone
is told about it. A corpus that passes is handed to a scout ONCE, with a signed line, and is not
handed again — if a later improvement would change it, the improvement waits and the editor
decides whether it is worth disturbing finished scouting work.

    ACCEPTED: <corpus> | <pages> | G1 0 dead · G2 <lang> · G3 <n> list pages · G4 <median>
              | <signer>, <date>

**A corpus without that line has not been handed over and must not be scouted. A corpus with it
is final, and an absence finding over it is admissible.** That last clause is the whole purpose:
the gate exists so that a NULL means something.

THE FOUR CHECKS

  G1 DEAD PAGES — pages yielding under 25% of the corpus median that nevertheless carry INK IN
     LINE STRUCTURE. Threshold 0. This is the only check that looks at the IMAGE, and it is the
     only one that can tell a blank leaf from a page we failed to read — which matter equally in
     the text and differently in a finding. Ink-testing is expensive, so a cap applies and the
     report says what fraction was tested; an untested residue is reported as UNTESTED, never as
     passed.
  G2 LANGUAGE — the bilingualism gate per page, never per corpus. Where a second language is
     present, arbitration must have run. A corpus average over a sectioned book measures neither
     section. An IDO corpus requires French BY RULE (2026-09-25): its French is names, which no
     density test sees, and the Esperanto model cannot emit an accent.
  G3 SHAPE — every page `page-shape.py` calls list-shaped must have been converted at `--psm 4`.
     The default mode reads a multi-column roster as running prose and severs the member number
     from the member.
  G4 LEXICON — median per-page lexical hit-rate against the detected language, plus any second
     language of the corpus on the pages where it is present (≥ 10 exclusive word types).
     **≥ 0.75 prose · ≥ 0.65 roster.** The roster threshold is lower ON PURPOSE: a page of
     surnames and foreign towns scores ~0.73 where prose scores ~0.88. That is the measure
     working, not damage. Never re-queue a roster on its hit-rate.

WHAT THE GATE CANNOT CATCH, stated here so it is never rediscovered as a surprise:
handwriting and lithograph (confident well-formed nonsense — exclude by name after LOOKING);
a second language in another script (silence, not damage); proper names (in no lexicon, which is
why G1 and G3 are not lexical); and a genuinely blank page versus one we failed to read, which
only G1's ink test separates.
"""
import os, re, sys, glob, json, argparse, subprocess, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_text_languages as TL
import old_orthography as OO   # Portuguese before the spelling reforms (2026-10-21)
import cyrillic_lexicon as CL   # Russian or Bulgarian list per item (2026-10-17)   # the language table: which non-Latin languages a text prints (2026-10-03)
LEXDIR = os.path.join(HERE, "lexicons")
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
WORD4 = re.compile(r"[^\W\d_]{4,}", re.UNICODE)
CYRILLIC = re.compile(r"[а-яёѣіѳѵА-ЯЁѢІѲѴ]")
_LEX = {}


def lex(name):
    if name in ("volapuk", "volapuk-reformed") and name not in _LEX:
        # VOLAPÜK: the list and its compound analyser (tools/volapuk_analyser.py; approved by the editor, 2026-10-17):
        # the journals compound and derive beyond any list (an internal record, 2026-10-17, not published);
        # «volapuk-reformed», de Jong's (2026-10-18, approved by the editor: tools/build-volapuk-reformed-lexicon.py)
        sys.path.insert(0, HERE)
        import volapuk_analyser
        _LEX[name] = volapuk_analyser.words_for(name)
    if name not in _LEX:
        p = os.path.join(LEXDIR, name + ".txt")
        _LEX[name] = ({w.strip().lower() for w in open(p, encoding="utf-8") if w.strip()}
                      if os.path.exists(p) else None)
    return _LEX[name]


# A LIBRARY'S COVER SHEET IS NOT THE PUBLICATION. ÖNB prefixes every scan with a German metadata
# sheet (Autor · Ort · Jahr · Zitierlink · Nutzungsbedingungen · Hinweis) and Google with an English
# boilerplate page. They were being scored as the corpus's own text: on *Progreso* vol. 1 the ÖNB
# sheet is page 1, mostly German, with an Ido title whose «la / por / Linguo» read as Esperanto
# (the editor, 2026-09-25, asked that such a page 1 be excluded from language detection). Recognised by
# CONTENT, never by page number — 113 corpora carry the ÖNB sheet, 2 the Google one.
COVER = [re.compile(r"Nationalbibliothek[\s\S]*(Zitierlink|Nutzungsbedingungen)"),
         re.compile(r"digital copy of a book that was preserved|books\.google\.com")]


_RU = {}
RU_FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
RU_END = (("аго", "ого"), ("яго", "его"), ("ыя", "ые"), ("ия", "ие"))
RU_WORD = re.compile(r"[а-яёѣіѳѵ]{3,}")
BG_WORD = re.compile(r"[а-яёѣіѳѵѫѭѝєїґ]{3,}")   # Bulgarian, the old spelling with ѫ ѭ (2026-10-17); Ukrainian є ї ґ (2026-10-18)


def ru_only_score(text, L=None):
    """Share of Cyrillic words (3+ letters) recognised after folding to modern spelling (ѣ→е, і→и, ѳ→ф, ѵ→и,
    final ъ dropped; -аго/-яго/-ыя/-ия also tried as -ого/-его/-ые/-ие), against the stems list + the corpus
    forms list. None under 30 Cyrillic words. Definition and bar: an internal record, 2026-09-28, not published."""
    # L (2026-10-17): another Cyrillic list in place of the Russian one, e.g. tools/cyrillic_lexicon.py's Bulgarian
    if L is not None:
        pass
    elif "L" not in _RU:
        L = set()
        for n in ("russian_post1918", "russian_forms_corpus"):
            p = os.path.join(LEXDIR, n + ".txt")
            if os.path.exists(p):
                L |= {w.strip().lower() for w in open(p, encoding="utf-8", errors="ignore") if w.strip()}
        _RU["L"] = L
    if L is None:
        L = _RU["L"]
    if L is not _RU.get("L"):
        # another list (Bulgarian, Ukrainian): its own word pattern (ѫ ѭ, є ї ґ too) and its own folding, so ѣ can be tried as е and as я
        ws = BG_WORD.findall(text.lower())
        return (100.0 * sum(w in L for w in ws) / len(ws)) if len(ws) >= 30 else None
    ws = RU_WORD.findall(text.lower())
    if len(ws) < 30:
        return None
    ok = 0
    for w in ws:
        f = re.sub(r"ъ$", "", w.translate(RU_FOLD))
        ok += f in L or any(f.endswith(a) and f[:-len(a)] + b in L for a, b in RU_END)
    return 100.0 * ok / len(ws)


class FoldedEstonian(set):
    """Estonian of c. 1908 prints «w» for modern «v» (*wõib*, *rahwus*), and text read by the Esperanto
    model has no ä õ ö ü. Membership tries the page's word as printed, then its v-spelling; in «wv-strip»
    mode it compares with the Estonian letters stripped on both sides. The TEXT is never changed."""
    STRIP = str.maketrans("äõöüšž", "aoousz")

    def __init__(self, base, mode):
        super().__init__(base)
        self.mode = mode
        self.stripped = {w.replace("w", "v").translate(self.STRIP) for w in base} if mode == "wv-strip" else None

    def __contains__(self, w):
        if set.__contains__(self, w):
            return True
        if self.mode == "wv":
            return "w" in w and set.__contains__(self, w.replace("w", "v"))
        return w.replace("w", "v").translate(self.STRIP) in self.stripped


def is_cover(text):
    return any(c.search(text) for c in COVER)


def pages_of(corpus_dir, segregated=False):
    # SCORE WHAT IS ACCEPTED. The combined `<stem>.txt` is the adjudicated MOSAIC (per page, the
    # psm 4 or psm 6 reading that won — tools/ocr-rebuild-combined.py), and it is what a finding
    # will search. Until 2026-09-25 this read `page-NNNN.txt` — the psm 6 reading — for every page,
    # so the gate scored text that, on the psm 4 winners, is not the text being accepted.
    out = {}
    comb = corpus_dir.rstrip("/") + ".txt"
    if os.path.exists(comb):
        parts = re.split(r"\n=== page (\d+) ===\n", "\n" + open(comb, encoding="utf-8",
                                                                errors="ignore").read())
        for n, t in zip(parts[1::2], parts[2::2]):
            if not is_cover(t):
                out[int(n)] = t
        # SCORE THE PREFERRED READING, NOT A DOUBLE ONE (approved by the editor, 2026-09-30). Since 2026-09-30 the search
        # text can hold a second, boosted reading of the same page appended after the first; an appended reading can
        # only add chances to find a name, so it must not lower an item's standing (it did: two items fell to PRESENCE
        # ONLY on junk from moderate boosted readings). Where `ocr-preferred/<corpus>.txt` exists (written
        # by tools/ocr-rebuild-combined.py), each page is scored on its PREFERRED reading — EXCEPT on pages with an
        # accepted Russian reading (PREFERRED.tsv `second_script` set), which are scored as before, on the search text,
        # so the Russian scoring is unchanged. Searches still run over the full search text.
        pref = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(comb))), "ocr-preferred",
                            os.path.basename(comb))
        ptsv = os.path.join(corpus_dir, "PREFERRED.tsv")
        if out and os.path.exists(pref):
            keep = set()
            if os.path.exists(ptsv):
                for l in open(ptsv, encoding="utf-8"):
                    f = l.rstrip("\n").split("\t")
                    if len(f) >= 4 and f[0].isdigit() and f[3]:
                        keep.add(int(f[0]))
            pp = re.split(r"\n=== page (\d+) ===\n", "\n" + open(pref, encoding="utf-8", errors="ignore").read())
            for n, t in zip(pp[1::2], pp[2::2]):
                n = int(n)
                if n in out and n not in keep:
                    out[n] = t
        if out:
            return _segregate(corpus_dir, out) if segregated else out
    for f in sorted(glob.glob(os.path.join(corpus_dir, "page-*.txt"))):
        if f.endswith(".psm4.txt"):
            continue
        m = re.search(r"page-(\d+)", os.path.basename(f))
        if m:
            t = open(f, encoding="utf-8", errors="ignore").read()
            if not is_cover(t):
                out[int(m.group(1))] = t
    return out


def _segregate(corpus_dir, out):
    """SCRIPT-SEGREGATED SCORING (editor, 2026-09-27 14:40): on a page printed in Esperanto AND
    Russian, Armenian or Georgian, score the ESPERANTO text alone — `page-NNNN.eo-clean.txt`, the
    Esperanto reading with the other script's junk removed (`tools/ocr-garbage-filter.py`). The other
    scripts are then PRESENCE ONLY, and a pass says the Esperanto text is absence-safe; it says
    nothing about the Russian, Armenian or Georgian. Pages without a clean file are scored as before.
    CAVEATS (editor, 2026-09-27): the clean file drops some real Latin-script words (ALL-CAPS names,
    initials, line-initial words), so this can slightly FLATTER a G4; and an ABSENCE search must still
    run over the FULL Esperanto text, never over the clean file."""
    # THE LANGUAGE TABLE FILTERS (2026-10-03, on the editor's ruling that the table should have acted as a filter): a text the table lists with NO
    # non-Latin language is never bi-script, whatever clean files the 28 Sep Cyrillic chain left on disk (*Progreso* 2a
    # yaro, *Mondo* 1924–25, *kongresa libro* 14 … were scored on a stripped side). Not in the table: as before.
    if TL.nonlatin(os.path.basename(os.path.normpath(corpus_dir))) == set():
        return out
    for n in list(out):
        p = os.path.join(corpus_dir, f"page-{n:04d}.eo-gate.txt")   # GATE MODE first: understates, never flatters
        if not os.path.exists(p):
            p = os.path.join(corpus_dir, f"page-{n:04d}.eo-clean.txt")
        if os.path.exists(p):
            out[n] = open(p, encoding="utf-8", errors="ignore").read()
    return out


def shape_score(text):
    """Geometry only — never asks whether tokens are words. See tools/page-shape.py."""
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 2]
    if len(lines) < 6:
        return 0.0
    med = statistics.median([len(l) for l in lines])
    toks = re.findall(r"[^\W\d_]+", text, re.UNICODE)
    caps = sum(1 for t in toks if t[:1].isupper())
    sig = [max(0.0, min(1.0, (60 - med) / 40)),
           sum(1 for l in lines if not l.endswith((".", "!", "?", ":", ";", "»"))) / len(lines),
           sum(1 for l in lines if re.search(r"\d", l)) / len(lines),
           min(1.0, (caps / max(len(toks), 1)) / 0.45),
           min(1.0, (text.count(",") / len(lines)) / 2.0)]
    return sum(sig) / 5


# Rosters DECLARED lists (the editor ruled on 2026-09-28 01:06, on *Nomaro de la kongresanoj* 1905, that it be
# treated as a list) — the shape test reads them as prose, but every unknown word is a name.
LIST_DECLARED = {"Nomaro de la kongresanoj 1905"}

FRENCH_TITLES = ("lesperantiste.",)   # corpus-name prefixes of titles known to be French-language
# corpus-name prefixes of titles whose second language is Portuguese (2026-10-14, cupel11: Brazila Esperantisto, ANNO
# `e3g` and the BitArkivo July 1907); see «PORTUGUESE BY DECLARATION» below. ANNO `e5e`, *Portugala Revuo* 1909–14
# (2026-10-21, cupel17, on the editor's decision that the gate honour the declared Portuguese): the gate had read its Portuguese as
# Spanish (11 items) and Catalan (1), so C7b.1's `por` pass found nothing to read. A prefix here, not every item the
# language table declares Portuguese: *La Revuo* 1910.0 declares it among five and would be held for a pass it never needed.
PORTUGUESE_TITLES = ("anno_e3g_", "brazilaesperantisto_", "anno_e5e_")


def _declared(corpus):
    """The per-corpus language DECLARATIONS live in ocr-quality-scan.py (one source, not two).
    Matched case-insensitively against «/<corpus>.», since the gate sees corpus names, not paths."""
    import importlib.util
    if "_DECL" not in globals():
        s = importlib.util.spec_from_file_location("qs", os.path.join(HERE, "ocr-quality-scan.py"))
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
        globals()["_DECL"] = {k.lower(): v for k, v in m.DECLARED.items()}
    key, hit, best = "/" + corpus.lower() + ".", "MISS", 0
    for frag, lang in _DECL.items():
        if frag in key and len(frag) > best:
            hit, best = lang, len(frag)
    return hit


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--primary", default=None,
                    help="force one primary language; default detects it per corpus")
    ap.add_argument("--write", default=None)
    ap.add_argument("--shape-cut", type=float, default=0.55)
    ap.add_argument("--psm-used", default="6", help="the psm the conversion actually used")
    ap.add_argument("--not-corpus", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published",
                    "heterophony-resources", "geniza", "OCR-NOT-CORPUS.tsv"),
                    help="TSV of corpora that are NOT corpus (scaffolding) — skipped, not counted (editor 2026-09-27)")
    ap.add_argument("--script-segregated", action="store_true",
                    help="score the cleaned ESPERANTO text of bi-script pages (page-NNNN.eo-clean.txt); other scripts presence only")
    # default «wv» from 2026-09-28 09:35 (approved by the editor): measured on *Estlanda Esperantisto* 1908 after the Estonian
    # second-model pass — exact 70.1/76.6/64.5, wv 72.5/81.4/67.1, wv-strip 73.1/81.7/67.4 (1908.1/.2/.6): stripping
    # the diacritics adds ≤ 0.6 once the Estonian model has restored them, so the stricter test is kept.
    ap.add_argument("--estonian-fold", choices=("none", "wv", "wv-strip"), default="wv",
                    help="how an Estonian word is matched (the editor, 2026-09-28, asked for W read as V and for G4 "
                         "runs with and without the diacritics): none = exact; wv = old «w» spelling also tried as «v», diacritics exact; "
                         "wv-strip = w→v AND ä õ ö ü š ž stripped on both sides")
    ap.add_argument("--no-auxlang-credit", action="store_true", help="switch OFF the page-local credit for the other planned languages (adopted 2026-09-26) — only to reproduce gates before p")
    ap.add_argument("--no-portuguese-fold", action="store_true",
                    help="match Portuguese words as printed only — only to reproduce gates before 2026-10-21 "
                         "(the old spellings, tools/old_orthography.py)")
    a = ap.parse_args()
    if a.estonian_fold != "none" and lex("estonian"):
        _LEX["estonian"] = FoldedEstonian(lex("estonian"), a.estonian_fold)
    if not a.no_portuguese_fold and lex("portuguese"):
        _LEX["portuguese"] = OO.FoldedPortuguese(lex("portuguese"))
    global NOT_CORPUS
    NOT_CORPUS = set()
    if a.not_corpus and os.path.exists(a.not_corpus):
        NOT_CORPUS = {l.split("\t")[0] for l in open(a.not_corpus, encoding="utf-8")
                      if l.strip() and not l.startswith("#") and not l.startswith("corpus\t")}

    # THE PRIMARY LANGUAGE IS DETECTED PER CORPUS, not assumed (approved by the editor, 2026-09-25).
    # Until today every corpus was scored against ESPERANTO, so the Ido runs — Progreso, Ido
    # 1923–29, Mondo, Suisa Idisto — failed G4 for being written in Ido, and were marked
    # unscoreable for lack of a clean Ido lexicon. That lexicon now exists (tools/lexicons/ido.txt,
    # 68,030 lemmas / 601,316 forms, born-digital sources only) and it discriminates:
    #     Ido corpora        vs ido 75–79%   vs esperanto ~57%
    #     Esperanto corpora  vs ido 22–24%   vs esperanto 65–71%
    # Each corpus is scored against whichever planned language it reads as best. `--primary`
    #   still forces one, for a deliberate single-language run.
    PLANNED = [n for n in ("esperanto", "ido", "occidental") if lex(n)]
    others = [n for n in ("french", "catalan", "german", "dutch", "spanish", "italian",
                          "danish", "swedish", "czech", "polish",
                          "estonian", "latvian", "lithuanian", "english") if lex(n)]   # back 2026-09-27 20:00, approved by the editor
    # ENGLISH added 2026-10-02 (approved by the editor; docs/FAILURE-MAP.md row 5d): it was never tested, so the English of 253
    # items (The British Esperantist, Amerika Esperantisto …) was only ever read by the Esperanto model. Not in BASELINE.
    # FIXED BASELINE for the relative test below: the median is taken over THESE ten, whatever else is
    # listed — so a near-zero list can no longer drag the bar down (gate t, 2026-09-27: 3 → 139 G2 pending).
    BASELINE = {"french", "catalan", "german", "dutch", "spanish", "italian", "danish", "swedish", "czech", "polish"}
    # Languages with NO second-model pass yet: detected and CREDITED at G4, recorded in «g2_unarbitrated»,
    # but not left «pending» forever for a pass that does not exist.
    NO_SECOND_MODEL = {"estonian", "latvian", "lithuanian"}
    # NOT YET: estonian, latvian, lithuanian (word lists built 2026-09-27; greek removed). Gate t added
    # them and G2-pending went 3 → 139 — but NOT through false detections of their own (they flagged only
    # 6, correctly: Estlanda ×4 estonian, latviana + LI 1904 latvian). The test below is RELATIVE —
    # «density > 4 × the MEDIAN of all candidates» — and near-zero languages pulled the median down, so
    # weak Catalan/French/Czech/Polish traces crossed the lowered bar (133 of the 139). To bring them back,
    # compute the median over a FIXED baseline set, not over whatever candidates are listed.
    dirs = sorted(d for d in glob.glob(os.path.join(a.root, "*")) if os.path.isdir(d))
    if a.corpus:
        dirs = [d for d in dirs if a.corpus.lower() in os.path.basename(d).lower()]
    rows = []
    for d in dirs:
        name = os.path.basename(d)
        if os.path.basename(d) in NOT_CORPUS:
            continue
        pg = pages_of(d, a.script_segregated)
        if not pg:
            continue
        lens = sorted(len(t) for t in pg.values())
        med = statistics.median(lens) if lens else 0
        silent = [p for p, t in pg.items() if med and len(t) < med * 0.25]

        # Which planned language does this corpus read as? Decided on the whole corpus, since
        # a page is too small a sample to tell two closely related languages apart.
        if a.primary:
            pname = a.primary
        else:
            sample = [m.group(0).lower() for t in list(pg.values())[:60] for m in WORD.finditer(t)]
            pname = max(PLANNED, key=lambda n: sum(1 for x in sample if x in lex(n))) \
                if sample else "esperanto"
            # A DECLARED MAIN LANGUAGE WINS (the editor, 2026-09-28 01:06, approved the suggested fix). Until now a
            # declaration only triggered the Ido → French rule; detection chooses among the planned
            # languages alone, so the Ritz speech, declared English on 2026-09-27, was still scored as
            # Esperanto. Measured 2026-09-28: Ritz 63.9 → 77.3, Jakštas-Dambrauskas 59.6 → 78.0, Carlevaro
            # *Lalortel* 56.9 → 75.9 (list bar 65), Belga Sonorilo 1912.11 74.8 (as Occidental) → 80.7 (Ido).
            dl = _declared(name)
            if dl not in ("MISS", None) and lex(dl):
                pname = dl
        prim = lex(pname)

        # G3 — list-shaped pages
        # the SHAPE test reads the FULL text: segregation strips a bi-script page's Russian and can make a list page
        # look like prose (La Ondo de Esperanto 1909.04 lost its list bar that way, 2026-09-28; the editor ruled that both be fixed)
        listy = [p for p, t in (pages_of(d) if a.script_segregated else pg).items() if shape_score(t) >= a.shape_cut]
        if name in LIST_DECLARED:   # a roster the shape test reads as prose: every page is a list page
            listy = list(pg)
        g3_ok = (not listy) or a.psm_used == "4"

        # G2 — WHICH second languages are present? ALL of them, not the top one.
        # The editor, 2026-09-25, asked of La Belga Sonorilo whether it was not trilingual — and it is.
        #   french 5.26% (exclusive 2.77%) · dutch 5.25% (exclusive 3.05%), both >5× the floor.
        #   A Belgian journal of 1902 carrying both national languages, which is obvious once
        #   said. Every arbitration we ran on it was `epo,fra`; the Dutch was never addressed.
        # The earlier version of this check reported `max(dens)` and nothing else, so a
        # trilingual title reported as bilingual and the third language was invisible — the
        # founding defect of this whole week, one level further out: testing for the language
        # already found rather than for the languages that might be there.
        seconds = []
        neighbour_notes = []
        allt = "\n".join(pg.values())
        toks = {m.group(0).lower() for m in WORD4.finditer(allt)}
        if toks:
            dens = {}
            for n in others:
                L = lex(n)
                # EXCLUSIVE density: words of that language that are NOT also Esperanto.
                dens[n] = 100 * sum(1 for x in toks if x in L and x not in prim) / len(toks)
            if dens:
                mid = statistics.median([v for n, v in dens.items() if n in BASELINE] or dens.values())
                if mid:
                    seconds = sorted(((n, v) for n, v in dens.items() if v > 4 * mid),
                                     key=lambda kv: -kv[1])
                # NEIGHBOURING LANGUAGES (approved by the editor, 2026-09-30): related languages share much of their
                # lexicons, so the density test named Polish for a Czech journal, Czech for a Kraków (Polish)
                # item and Catalan for a Spanish one. Where one of a pair is flagged, each is scored on the words
                # NOT in the other's lexicon either, and the one with more such words stands for the pair.
                for a_, b_ in (("czech", "polish"), ("spanish", "catalan"), ("danish", "swedish")):
                    names = [n for n, _ in seconds]
                    if (a_ in names or b_ in names) and lex(a_) and lex(b_):
                        La, Lb = lex(a_), lex(b_)
                        da = sum(1 for x in toks if x in La and x not in prim and x not in Lb)
                        db = sum(1 for x in toks if x in Lb and x not in prim and x not in La)
                        keep = a_ if da >= db else b_
                        pos = min(i for i, (n, _) in enumerate(seconds) if n in (a_, b_))
                        seconds = [(n, v) for n, v in seconds if n not in (a_, b_)]
                        seconds.insert(pos, (keep, dens.get(keep, 0.0)))
                        neighbour_notes.append(f"{keep} over {b_ if keep == a_ else a_} ({max(da, db)}:{min(da, db)} distinctive words)")
        # IDO CORPORA NEED FRENCH BY RULE, NOT BY DETECTION (approved by the editor for G2, 2026-09-25).
        # The density test above counts French WORDS; the French in an Ido journal is mostly NAMES
        # — Couturat, de Beaufront, Léau, Sébert — which are in no lexicon, so all 14 *Progreso*
        # volumes reported no second language. And the Esperanto model cannot emit an accent at all:
        # 0 é/è/à/ç across *Progreso*, `Sébert` → `Sebert` every time. Measured on 11 name-bearing
        # pages of *Progreso* 5: the French model left the Ido hit-rate flat (71.9% → 71.1%),
        # restored real French (`Société`, `René`, `français`) and removed 11 spurious ĉ/ŝ/ŭ. Ido
        # has no diacritics for the French model to damage, so the cost is nil and the rule is safe.
        # An Ido corpus — detected OR declared, since *Progreso* vol. 1 detects as Esperanto — has
        #   French as a required second language whatever the density says.
        rule = None
        if (pname == "ido" or _declared(name) == "ido") and not any(n == "french" for n, _ in seconds):
            seconds = [("french", 0.0)] + seconds
            rule = "ido → french by rule"
        # AND FRENCH JOURNALS NEED FRENCH BY DECLARATION. *L'Espérantiste* was de Beaufront's
        # journal; it defected to Ido and stayed bilingual for a while (editor, 2026-09-25) — which
        # is why its 1912–14 issues flip between Esperanto and Ido issue by issue. It is French
        # throughout, yet 9 issues showed NO French by density (`les` ×110 in one of them): the
        # density test is weaker than it looks, so a known French title is declared, not detected.
        elif name.lower().startswith(FRENCH_TITLES) and not any(n == "french" for n, _ in seconds):
            seconds = [("french", 0.0)] + seconds
            rule = "French title → french by declaration"
        # PORTUGUESE BY DECLARATION (the editor ruled on 2026-10-14 03:5x that it be by declaration, cupel11). Portuguese is not in
        # `others`: the corpus-wide search would re-test every item. Without it, Brazila Esperantisto's Portuguese
        # read as SPANISH, the nearest list (10 issues G2-pending for a Spanish pass, no Portuguese credit at G4).
        # For these titles Portuguese replaces Spanish and its neighbour Catalan; its density is measured as above.
        if name.lower().startswith(PORTUGUESE_TITLES) and lex("portuguese"):
            Lpt = lex("portuguese")
            dpt = 100 * sum(1 for x in toks if x in Lpt and x not in prim) / len(toks) if toks else 0.0
            seconds = [(n, v) for n, v in seconds if n not in ("spanish", "catalan", "portuguese")]
            seconds = [("portuguese", dpt)] + seconds
            rule = rule or "Portuguese title → portuguese by declaration"
        # G4 — median per-page lexical hit-rate (pages of ≥ 60 tokens), computed AFTER G2 because
        # it needs the corpus's second languages.
        # BILINGUAL CREDIT, PAGE-LOCAL (adopted by the editor, 2026-09-26, who judged it sensible to constrain
        # it to where it will give purchase). A word counts if it is valid in the primary language OR
        # in a second language of this corpus that is PRESENT ON THIS PAGE — at least 10 word types
        # valid in it and not in the primary. Why: counting only primary words made correct French
        # count AGAINST bilingual journals once French arbitration restored it (43 corpora fell,
        # 34 of them *L'Espérantiste*). Why page-local and ≥ 10: counting a second language on every
        # page lifted the Ido-by-rule corpora +4.3 points on French NAMES; ≥ 10 cut that to +1.5.
        # Blind look, 60 pages: pages this lets through were GOOD/USABLE 92% — like passing
        # corpora (89%), unlike failing ones (80%). (An internal record, 2026-09-26, not published.)
        sec_lex = [(n, lex(n)) for n, _ in seconds if lex(n)]
        # AUXLANG CREDIT (adopted 2026-09-26, approved by the editor): *Posta Mundi* and *Mondo* print Esperanto,
        # Ido and Occidental side by side, so scoring against ONE of them failed them by design. The
        # other two planned languages earn page-local credit under the SAME rule as French. Blind
        # look, 60 pages: corpora it lets through GOOD+USABLE 95%, like passing ones (100%), unlike
        # failing ones (55%) — (an internal record, 2026-09-26, not published). Median G4 elsewhere: +0.
        if not a.no_auxlang_credit:
            sec_lex += [(n, lex(n)) for n in PLANNED if n != pname]
        # DECLARED SECOND LANGUAGES (2026-10-17, approved by the editor): a Latin-script language the language table
        # licenses for the item (a declaration the editor confirmed against its pages) earns the same page-local credit
        # as a detected one. Found on Volapükabled: the gate detects a second language by its words NOT in the main list,
        # and the Volapük analyser takes some German words, so the German columns went uncredited (G4 62–68 against 0.80
        # with German, an internal record, 2026-10-17, not published). Cited languages license nothing.
        for n in sorted(TL.languages(name) or ()):
            if n != pname and n not in TL.NONLATIN and lex(n) and n not in {m for m, _ in sec_lex}:
                sec_lex.append((n, lex(n)))
        hits = []
        cyr_pages = 0
        for p, t in pg.items():
            toks = [m.group(0).lower() for m in WORD.finditer(t)]
            if len(toks) < 60:
                continue
            # RUSSIAN pages (tools/ocr-russian-pages.py) are DECLARED UNSCOREABLE — the editor's
            # ruling of 2026-09-23 (tools/lexicons/hunspell/SOURCE.md): the only Russian list is
            # post-1918, and this material is pre-1918. A page mostly in Cyrillic is left out of G4;
            # a corpus with no other scoreable page is reported unscoreable, neither pass nor fail.
            if sum(1 for x in toks if CYRILLIC.search(x)) >= 0.5 * len(toks):
                cyr_pages += 1
                continue
            here = []
            if sec_lex:
                types = {m.group(0).lower() for m in WORD4.finditer(t)}
                here = [L for n, L in sec_lex
                        if sum(1 for w in types if w in L and w not in prim) >= 10]
            hits.append(100 * sum(1 for x in toks if x in prim or any(x in L for L in here))
                        / len(toks))
        # -1 = unscoreable (Cyrillic); -2 = TOO SHORT TO SCORE: no page reaches 60 words (covers,
        # one-page items, short poems) — 22 corpora read as «G4 0» in gate o, *Epigrami* among them
        # at 92% Ido overall. Neither is a failure; neither is a pass.
        g4 = statistics.median(hits) if hits else (-1.0 if cyr_pages else -2.0)
        # RUSSIAN-ONLY SCORE (the editor asked on 2026-09-28 09:55 to see Esperanto-only and Russian-only
        # scores; bar 40, defended in an internal record, 2026-09-28, not published). Per page: the Russian side of
        # a bi-script page (`page-NNNN.ru-clean.txt`), or the page itself where it is mostly Cyrillic (an
        # accepted Russian page); pages under 30 Cyrillic words not scored; item = median. G4 above, on the
        # segregated text, is the ESPERANTO-ONLY score. Reported only; the ledger applies the rule.
        rus = []
        # BULGARIAN (2026-10-17, approved by the editor): an item listed with Bulgarian and no Russian is scored against the
        # Bulgarian list through the old spelling (tools/cyrillic_lexicon.py), the same bar; reported as its Bulgarian-only score
        # UKRAINIAN (2026-10-18, approved by the editor): likewise an item listed with Ukrainian and no Russian, against the
        # Ukrainian list through the Galician spelling (an internal record, 2026-10-18, not published)
        cyr_side = CL.language(name)
        cyr_list = CL.words(cyr_side)
        # the language table (2026-10-03): no Russian-only score for a text the table lists with no Cyrillic language
        for p, t in (pg.items() if TL.cyrillic(name) != set() else ()):
            rc = os.path.join(d, f"page-{p:04d}.ru-clean.txt")
            if os.path.exists(rc):
                src = open(rc, encoding="utf-8", errors="ignore").read()
            else:
                tk = [m.group(0) for m in WORD.finditer(t)]
                src = t if tk and sum(1 for x in tk if CYRILLIC.search(x)) >= 0.5 * len(tk) else None
            s = ru_only_score(src, cyr_list) if src else None
            if s is not None:
                rus.append(s)
        ru_only = round(statistics.median(rus), 1) if rus else None
        # G2 AS SPECIFIED: «second language present ⇒ arbitration has run» (checked from
        # 2026-09-26; before, any second language simply blocked acceptance for ever). The record is
        # `<stem>/SECOND-MODEL.json`, written by tools/ocr-second-model.py: a language is handled
        # when ≥ 95% of pages carry a merge in it, pages whose chosen reading is the PDF's own text
        # layer excepted (guard 1 there: not our model's text).
        CODE = {"french": "fra", "german": "deu", "czech": "ces", "polish": "pol",
                "catalan": "cat", "dutch": "nld", "spanish": "spa", "swedish": "swe",
                "italian": "ita", "danish": "dan",
                "english": "eng",
                "portuguese": "por",   # 2026-10-14, by declaration on the editor's ruling (cupel11); NOT in `others` either
                "slovak": "slk"}   # 2026-10-12, on the editor's request to add Slovak to the gate (cupel9); Slovak is NOT in `others`
                                   # (the corpus-wide second-language search): adding it there re-tests every Czech item   # 2026-10-02 22:2x: English joined G2 `others` that day; without this entry its pass
                                    # (recorded as `eng`) was never found, and gate 10-02b held 239 items «G2 pending»
        smp = os.path.join(d, "SECOND-MODEL.json")
        sm = json.load(open(smp, encoding="utf-8")) if os.path.exists(smp) else {}
        # A VISION READING SATISFIES G2 ON ITS PAGE (approved by the editor, 2026-09-30, after a blind check of 40
        # second-language vision pages: 38 of 38 COMPLETE, in their own script — an internal record,
        # 2026-09-30, not published). A pending second language counts as handled when EVERY page that carries it
        # (≥ 10 word types valid in it and not in the primary, the page-local test of G4 above) has a vision,
        # hand-keyed or ruled reading as its chosen reading (PREFERRED.tsv, search recipe). One page without
        # such a reading keeps the language pending.
        readpages = set()
        ptsv_ = os.path.join(d, "PREFERRED.tsv")
        if os.path.exists(ptsv_):
            for l_ in open(ptsv_, encoding="utf-8"):
                y_ = l_.rstrip("\n").split("\t")
                if len(y_) >= 5 and y_[0].isdigit() and (y_[4].split("+")[0] in ("vision", "hand", "ruled")
                                                          or y_[1].startswith("tl-born")):
                    # a born-digital preferred reading is the printed text, not our model's OCR: the same exception
                    # G2 already makes for a page whose chosen reading is the text layer (2026-09-30 16:1x)
                    readpages.add(int(y_[0]))
        pending, unarb, by_vision, not_carried = [], [], [], []
        for n_, _ in seconds:
            if n_ in NO_SECOND_MODEL:
                unarb.append(n_); continue
            r = sm.get(CODE.get(n_, n_))
            if not r or (r["merged"] + r["skipped_text_layer"]) < 0.95 * r["pages"]:
                L_ = lex(n_)
                carry = [p for p, t in pg.items() if L_ and
                         sum(1 for w in {m.group(0).lower() for m in WORD4.finditer(t)} if w in L_ and w not in prim) >= 10]
                if carry and all(p in readpages for p in carry):
                    by_vision.append(n_)
                elif not carry:
                    # NOT CARRIED BY ANY PAGE (approved by the editor, 2026-09-30): the corpus-wide density found the language
                    # as scattered words, but no page holds ≥ 10 word types of it, so there is no passage for a
                    # second-language pass to read. It does not hold the item back (*Bulteno TEKS* 1914.9,
                    # *Hungario instruas faŝisman literaturon*, *Tolstoj Lucerno*, gate 30i).
                    not_carried.append(n_)
                else:
                    pending.append(n_)
        second = seconds[0][0] if seconds else None
        best = seconds[0][1] if seconds else 0.0
        rows.append({"corpus": name, "pages": len(pg), "silent": len(silent),
                     "list_pages": len(listy), "g3_ok": g3_ok, "g4": g4, "cyrillic_pages": cyr_pages,
                     "primary": pname, "g2_rule": rule, "g2_pending": pending, "g2_unarbitrated": unarb,
                     "g2_by_vision": by_vision, "g2_not_carried": not_carried, "g2_neighbour": neighbour_notes,
                     "ru_only": ru_only, "ru_pages": len(rus), **({"cyr_side": cyr_side} if cyr_side != "russian" else {}),
                     "second": second, "second_density": best,
                     "all_seconds": [{"lang": n, "density": round(v, 2)} for n, v in seconds]})

    acc = [r for r in rows if r["g3_ok"] and r["g4"] >= (65 if r["list_pages"] else 75)
           and not r["g2_pending"]]
    print(f"{len(rows)} corpora gated · {len(acc)} would pass G2–G4 "
          f"(G1 needs the ink test, run separately)")
    fail3 = [r for r in rows if not r["g3_ok"]]
    fail4 = [r for r in rows if 0 <= r["g4"] < (65 if r["list_pages"] else 75)]
    unsc = [r for r in rows if r["g4"] == -1.0]
    short = [r for r in rows if r["g4"] == -2.0]
    lang = [r for r in rows if r["g2_pending"]]
    print(f"  G3 fail (list pages not at --psm 4): {len(fail3)}")
    print(f"  G4 fail (median hit-rate below bar): {len(fail4)}")
    print(f"  G4 unscoreable (Cyrillic pages only — declared, 2026-09-23): {len(unsc)}")
    print(f"  G4 too short to score (no page of 60+ words): {len(short)}")
    print(f"  G2 pending (second language not yet through the second model): {len(lang)}")
    print(f"  G2 settled by vision readings (every page carrying the language vision/hand/ruled): "
          f"{sum(1 for r in rows if r.get('g2_by_vision'))}")
    print(f"  G2 language flagged but carried by no page (not holding the item back): "
          f"{sum(1 for r in rows if r.get('g2_not_carried'))}")
    print(f"  G2 neighbouring-language choice made (Czech/Polish, Spanish/Catalan, Danish/Swedish): "
          f"{sum(1 for r in rows if r.get('g2_neighbour'))}")
    if a.write:
        w = ["# Acceptance gate — run of " + __import__("time").strftime("%Y-%m-%d %H:%M") + "\n",
             "**GENERATED by `tools/ocr-accept.py`. Contract: `geniza/ocr/method/OCR-PIPELINE-FROZEN.md`.**\n",
             f"{len(rows)} corpora · {len(acc)} pass G2–G4 · G1 (ink) run separately\n",
             ("**SCRIPT-SEGREGATED** (`--script-segregated`): on bi-script pages G2–G4 scored the cleaned ESPERANTO "
              "text only (`page-NNNN.eo-gate.txt`, the strict clean that can understate but not flatter); Russian, Armenian and Georgian text on those pages is PRESENCE ONLY.\n"
              if a.script_segregated else "Scoring: the combined text as accepted (not script-segregated).\n"),
             "| corpus | pages | silent | list pp | G3 | G4 | G2 second lang |",
             "|---|---:|---:|---:|---|---:|---|"]
        for r in sorted(rows, key=lambda x: (x["g3_ok"], x["g4"])):
            w.append(f"| `{r['corpus'][:44]}` | {r['pages']} | {r['silent']} | {r['list_pages']} "
                     f"| {'ok' if r['g3_ok'] else '⛔ psm'} | {('%.0f' % r['g4']) if r['g4'] >= 0 else ('unscoreable (Cyrillic)' if r['g4'] == -1.0 else 'too short to score')} "
                     f"| {' + '.join(('%s (%s)' % (x['lang'], r['g2_rule'])) if r.get('g2_rule') and x['density'] == 0 else '%s %.1f%%' % (x['lang'], x['density']) for x in r['all_seconds']) or '—'} |")
        open(a.write, "w", encoding="utf-8").write("\n".join(w) + "\n")
        print(f"wrote {a.write}")
        json.dump(rows, open(a.write + ".json", "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
