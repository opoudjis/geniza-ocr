#!/usr/bin/env python3
r"""ocr-second-model — read a page again with a SECOND language model, through the SAME route as
its chosen reading, and merge the two word by word.

    tools/ocr-second-model.py --gate OCR-GATE-<tag>.md.json --verdicts OCR-PSM-VERDICTS-<tag>.json \
        --pdfs <list> --root <ocr root> --lang fra [--corpus SUBSTR] [--page-gate N] [--files 6]

WHY A WRAPPER AND NOT `ocr-arbitrate.py` DIRECTLY (2026-09-26, French approved by the editor).
`ocr-arbitrate.py` renders every page itself at a fixed 300 dpi, greyscale, one segmentation mode
for the whole document. The pipeline now chooses, PER PAGE, among readings of different images
(extracted scan · rendered page · text-mask re-read · 300 ppi image-free re-read) and modes (psm 6
/ psm 4). Arbitrating against a reading of a DIFFERENT image compares two things that are not the
same page, and throws the per-page choice away. So this reads the second model through the chosen
reading's own route — same image, same resolution, same psm — and hands both texts to
`ocr-arbitrate.py`'s own `arbitrate()`. The merge rule is that tool's, unchanged.

THE FOUR GUARDS, each inherited or learned:
  1. BASELINE (ocr-arbitrate.py, Belga Sonorilo 1910: Lemaire 56→36 when arbitrated over text
     that already used the right model). Our readings are all `-l epo`, so French is valid — EXCEPT
     where the chosen reading is the PDF's own text layer (`tl`): someone else's OCR, whose accents
     may already be right. Those pages are skipped.
  2. PRIMARY LEXICON = THE CORPUS'S LANGUAGE. «Keep the reading if it is a valid word» must test
     IDO words on an Ido corpus: against Esperanto, nearly every Ido word fails and loses to the
     French reading, which puts accents on Ido (`téorlo`, `questionés`, measured 2026-09-25).
     Ido also gets `ocr-arbitrate.py`'s IDO_MODE: a supersigned letter in Ido is an impossibility.
  3. PAGE GATE (ocr-arbitrate.py: a page with < N exclusive second-language word types passes
     through untouched; N=10 was measured against CATALAN). For French NAMES in Ido/Esperanto text
     a page may carry one `Sébert` and nothing else French — so N is a parameter, set by
     measurement for French, not inherited.

  4. SAFETY NET (2026-09-26). If the second reading comes in under ¼ of the chosen reading, the page
     is rendered and read again, as the conversion did for pages it rescued. If it still falls short,
     NOTHING is merged, so the page stays open for a re-run instead of being marked done by a merge
     that changes nothing. (*Ido-Saluto* 2025 p.23: 0 chars from its picture against 2,155 chosen.)

Writes `page-NNNN.<lang>.txt` (the second reading) and `page-NNNN.<winner>.arb.txt` (the merge, NAMED BY
the reading it was merged with) beside the others; `ocr-rebuild-combined.py` uses it only while
that reading is still the page's choice — a later re-adjudication cannot pick up a stale merge. Never overwrites a
reading; re-runnable (a page with `.arb.txt` is skipped).
"""
import os, re, sys, json, glob, argparse, subprocess, tempfile, shutil, collections, importlib.util, difflib
import concurrent.futures as fut

os.environ.setdefault("OMP_THREAD_LIMIT", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ocr_page_images import page_images, render_page


def _mod(name, file):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


ARB = _mod("arb", "ocr-arbitrate.py")
MR = _mod("mr", "ocr-mask-reread.py")
TESS = {"fra": "fr", "deu": "de", "ces": "cs", "pol": "pl", "cat": "ca", "nld": "nl",
        "spa": "es", "swe": "sv", "ita": "it", "dan": "da",
        "est": "et",   # 2026-09-28: the editor asked for the Estonian OCR model, to attempt ä, õ, ö, ü, with old W read as V
        "eng": "en"}   # 2026-10-02, approved by the editor (failure map row 5d)
SUF = {"psm6": ".txt", "psm4": ".psm4.txt", "hr6": ".hr.txt", "hr4": ".hr.psm4.txt", "tl": ".tl.txt"}


_PRIOR = {}


def with_prior(is1, prior):
    """CHAINED MERGES PROTECT EARLIER LANGUAGES (fixed 2026-09-26). When a second language merges
    onto an earlier language's merge, «keep the token if it is a real word» must count words of
    the EARLIER language too. Otherwise the new model overwrites correct words the earlier pass
    restored: on *Bohema Revuo* 1909 the Polish pass turned Czech `naši` → `naśi`, `že` → `że`,
    `této` → `tóto`, and G4 fell 93 → 44."""
    if not prior:
        return is1
    sets = []
    for c in prior:
        if c not in _PRIOR:
            _PRIOR[c] = ARB.load(TESS[c])
        sets.append(_PRIOR[c])
    return lambda w: is1(w) or any(re.sub(r"[^\w]", "", w).lower() in s for s in sets)


def lexicons(primary, lang):
    """(is_primary_word, is_second_word) — purified against each other, as ocr-arbitrate does."""
    code2 = TESS[lang]
    two = ARB.load(code2)
    if primary == "ido":
        one = {w.strip().lower() for w in open(os.path.join(HERE, "lexicons", "ido.txt"),
                                               encoding="utf-8") if w.strip()}
        is1 = ARB.make_is_word(one, agglutinative=False)     # paradigm-generated: full forms
    else:
        one = ARB.purify(ARB.load("eo"), "eo", two)
        is1 = ARB.make_is_word(one, agglutinative=True)
    is2 = ARB.make_is_word(ARB.purify(two, code2, one), agglutinative=False)
    if lang == "est":
        # OLD ORTHOGRAPHY: Estonian of c. 1908 prints «w» where the modern list has «v» (*wõib*, *weel*,
        # *rahwus*). The Estonian reading keeps the page's «w» — the text stays as printed — but it counts
        # as a real word if its v-spelling is (the editor's ruling, 2026-09-28).
        base2 = is2
        is2 = lambda w, b=base2: b(w) or ("w" in w.lower() and b(re.sub("w", "v", re.sub("W", "V", w))))
    return is1, is2


HAT = re.compile(r"[ĉĝĥĵŝŭĈĜĤĴŜŬ]")
DEHAT = str.maketrans("ĉĝĥĵŝŭĈĜĤĴŜŬ", "cghjsuCGHJSU")


def keep_hats(a, merged, is2):
    """A PLAIN HAT-STRIP IS NOT A FIX (2026-09-26). Where the merge replaced a token that carried
    Esperanto supersigns with the SAME letters minus the supersigns, accept it only if the result
    is a real word of the second language (`ĵour` → `jour`: yes). Otherwise restore the original
    (`kotizaĵo` → `kotizajo`: no). Measured on the first French run: 9,315 such strips were not
    French words, against 2,041 that were."""
    A, M = a.split(), merged.split()
    out = list(M)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, M, autojunk=False).get_opcodes():
        if tag != "replace" or (i2 - i1) != (j2 - j1):
            continue
        for k in range(i2 - i1):
            x, y = A[i1 + k], M[j1 + k]
            if HAT.search(x) and not HAT.search(y) and x.translate(DEHAT) == y:
                if not is2(re.sub(r"[^\w]", "", y)):
                    out[j1 + k] = x
    return " ".join(out)


def merge_lines(base, other, keep, is_other, hat_guard):
    """Word-by-word merge that KEEPS THE BASE READING'S LINE BREAKS (2026-09-26).

    `ocr-arbitrate.py`'s `arbitrate()` splits both readings into words and joins the result with
    spaces, so every merged page came out as ONE LINE — 47,449 of 47,449. That flattened the very
    structure the per-page choice protects on list pages (a member's number on the line with the
    name), and made G1 see one line of text against thirty lines of type. Here the decision is the
    same, token for token — keep the base token if `keep()` says it is a real word; Ido's
    supersign rule; otherwise the other reading — but each output word is put back on the line of
    the base token it came from. Words the other reading adds go on the line of the preceding base
    word. `hat_guard`: a plain supersign-strip is taken only if the result is a real word of the
    other language (see keep_hats)."""
    lines = base.split("\n")
    toks = [(li, w) for li, ln in enumerate(lines) for w in ln.split()]
    A = [w for _, w in toks]
    B = other.split()
    out = [[] for _ in toks]
    lead = []                                   # other-reading words before the first base word

    def put(k, w):
        (out[k] if k >= 0 else lead).append(w)

    def choose(x, y):
        core = re.sub(r"[^\w]", "", x.lower())
        if core and keep(core):
            return x
        if ARB.IDO_MODE and ARB.IDO_IMPOSSIBLE.search(x) and not ARB.IDO_IMPOSSIBLE.search(y):
            return y
        if ARB.IDO_MODE and ARB.IDO_IMPOSSIBLE.search(y) and not ARB.IDO_IMPOSSIBLE.search(x):
            return x
        if (hat_guard and HAT.search(x) and not HAT.search(y) and x.translate(DEHAT) == y
                and not is_other(re.sub(r"[^\w]", "", y))):
            return x
        return y

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag in ("equal", "delete"):
            for k in range(i1, i2):
                put(k, A[k])
        elif tag == "insert":
            for w in B[j1:j2]:
                put(i1 - 1, w)
        else:                                   # replace
            n = max(i2 - i1, j2 - j1)
            for k in range(n):
                x = A[i1 + k] if i1 + k < i2 else None
                y = B[j1 + k] if j1 + k < j2 else None
                if x is None:
                    put(i2 - 1, y)
                elif y is None:
                    put(i1 + k, x)
                else:
                    put(i1 + k, choose(x, y))
    rebuilt = [[] for _ in lines]
    for (li, _), ws in zip(toks, out):
        rebuilt[li].extend(ws)
    text = "\n".join(" ".join(ws) for ws in rebuilt)
    return (" ".join(lead) + "\n" + text) if lead else text


def best_merge(base, w):
    """The merge with the LONGEST language chain for reading `w` of this page, as (path, [langs]).
    Names: `page-NNNN.<w>.arb.txt` = French (the first run, 2026-09-26); `page-NNNN.<w>.<a+b>.arb.txt`
    = merged with a, then b. Each language merges onto the previous merge, so a Belgian page gets
    French AND Dutch, not whichever ran last."""
    best = (None, [])
    legacy = f"{base}.{w}.arb.txt"
    if os.path.exists(legacy):
        best = (legacy, ["fra"])
    for p in glob.glob(glob.escape(f"{base}.{w}.") + "*.arb.txt"):
        chain = p[len(f"{base}.{w}."):-len(".arb.txt")].split("+")
        if len(chain) > len(best[1]):
            best = (p, chain)
    return best


def do_corpus(job):
    (corpus, pdf, root, primary, lang, verdicts, gate, jobs) = job[:8]
    d = os.path.join(root, corpus)
    if not os.path.isdir(d):
        return corpus, collections.Counter()
    pages = {}
    for f in glob.glob(os.path.join(d, "page-*.txt")):
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m:
            pages[int(m.group(1))] = f
    todo, skipped_tl = [], 0
    for n, f in sorted(pages.items()):
        w = verdicts.get(f"{corpus}/page-{n:04d}.txt", "psm6")
        if w == "tl":
            skipped_tl += 1
            continue                                   # guard 1: not our model's text
        if lang in best_merge(f[:-4], w)[1]:
            continue                                   # already merged in this language
        todo.append((n, w))
    if not todo:
        write_summary(d, pages, verdicts, corpus, lang, skipped_tl)
        return corpus, collections.Counter()
    ARB.IDO_MODE = (primary == "ido")
    is1, is2 = lexicons(primary, lang)
    hr_ppi = MR.mask_pages(pdf) if any(w.startswith("hr") for _, w in todo) else {}
    work = tempfile.mkdtemp()
    tally = collections.Counter()
    try:
        imgs = page_images(pdf, work, jobs=jobs, pages=[n for n, w in todo if not w.startswith("hr")])

        def one(job):
            n, w = job
            psm = "4" if w.endswith("4") else "6"
            if w.startswith("hr"):
                r = min(hr_ppi.get(n, 300), 400)
                b = os.path.join(work, f"h{n:05d}")
                subprocess.run(["pdftoppm", "-r", str(r), "-png", "-f", str(n), "-l", str(n), pdf, b],
                               capture_output=True)
                hit = glob.glob(b + "*.png"); img = hit[0] if hit else None
            else:
                img = imgs.get(n)
            if not img:
                return "no image"
            base = pages[n][:-4]
            prev, chain = best_merge(base, w)             # merge onto the previous language's merge
            a = open(prev or base + SUF[w], encoding="utf-8", errors="ignore").read()
            def read(im):
                return subprocess.run(["tesseract", im, "stdout", "-l", lang, "--psm", psm,
                                       "--oem", "1"], capture_output=True, text=True).stdout or ""
            b2 = read(img)
            # The conversion's SAFETY NET, mirrored (as in ocr-psm-both.py): a page whose extracted
            # image read far below its neighbours was re-read by RENDERING, and that is the text
            # being merged with. Found 2026-09-26: 0 chars from the extracted picture of a born-
            # digital page (*Ido-Saluto* 2025 p.23) against 2,155 in the chosen reading.
            if len(b2) < 0.25 * len(a) and not w.startswith("hr"):
                alt = render_page(pdf, work, n)
                if alt:
                    b3 = read(alt)
                    if len(b3) > len(b2):
                        b2 = b3
            if len(b2) < 0.25 * len(a):
                return "second reading failed — not merged"   # no merge: retried on a re-run
            open(f"{base}.{lang}.txt", "w", encoding="utf-8").write(b2)
            isA = with_prior(is1, chain)                  # earlier languages are protected too
            which, ea, eb = ARB.page_language(a, b2, isA, is2)
            if eb < gate:
                merged, how = a, "untouched"                # guard 3
            elif which == "B":
                merged = merge_lines(b2, a, is2, isA, False); how = "second-language page"
            else:
                merged = merge_lines(a, b2, isA, is2, primary != "ido"); how = "merged"
                # (hat guard off for Ido: it has no supersigns, so a hat there is an OCR error)
            # named by the reading it was merged WITH (valid only while that reading is chosen) and
            # by its language chain
            open(f"{base}.{w}.{'+'.join(chain + [lang])}.arb.txt", "w",
                 encoding="utf-8").write(merged + "\n")
            return how
        with fut.ThreadPoolExecutor(max_workers=jobs) as pool:
            for how in pool.map(one, todo):
                tally[how] += 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    write_summary(d, pages, verdicts, corpus, lang, skipped_tl)
    return corpus, tally


def write_summary(d, pages, verdicts, corpus, lang, skipped_tl):
    """`<stem>/SECOND-MODEL.json` — what the gate's G2 checks: per language, how many pages carry a
    merge in it, how many were skipped as text-layer pages, out of how many."""
    merged = 0
    for n, f in pages.items():
        w = verdicts.get(f"{corpus}/page-{n:04d}.txt", "psm6")
        if w != "tl" and lang in best_merge(f[:-4], w)[1]:
            merged += 1
    p = os.path.join(d, "SECOND-MODEL.json")
    s = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    s[lang] = {"pages": len(pages), "merged": merged, "skipped_text_layer": skipped_tl}
    json.dump(s, open(p, "w", encoding="utf-8"), indent=1)


def remerge_corpus(job):
    """--remerge: recompute this language's merges from the second readings ALREADY ON DISK
    (`page-NNNN.<lang>.txt`) — no OCR. For when the merge RULE improves (2026-09-26: compound-aware
    Esperanto test + hat-strip guard) and the readings are still good. The French run's first-
    generation merges (`page-NNNN.<w>.arb.txt`) are replaced by `page-NNNN.<w>.fra.arb.txt`."""
    (corpus, pdf, root, primary, lang, verdicts, gate, jobs) = job[:8]
    suffix = job[8] if len(job) > 8 else None
    d = os.path.join(root, corpus)
    if not os.path.isdir(d):
        return corpus, collections.Counter()
    ARB.IDO_MODE = (primary == "ido")
    is1, is2 = lexicons(primary, lang)
    tally, pages, skipped_tl = collections.Counter(), {}, 0
    for f in glob.glob(glob.escape(d) + "/page-*.txt"):
        m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
        if m:
            pages[int(m.group(1))] = f
    for n, f in sorted(pages.items()):
        base = f[:-4]
        w = verdicts.get(f"{corpus}/page-{n:04d}.txt", "psm6")
        if w == "tl":
            skipped_tl += 1
            continue
        rd = f"{base}.{lang}.txt"
        if not os.path.exists(rd):
            continue
        legacy = f"{base}.{w}.arb.txt"
        prev, chain = best_merge(base, w)
        if lang in chain:                 # the text BEFORE this language: drop it from the chain
            chain = chain[:chain.index(lang)]
            cand = [p for p in glob.glob(glob.escape(f"{base}.{w}.") + "*.arb.txt")
                    if p[len(f"{base}.{w}."):-len(".arb.txt")].split("+") == chain]
            prev = cand[0] if cand else None
        a = open(prev or base + SUF[w], encoding="utf-8", errors="ignore").read()
        b2 = open(rd, encoding="utf-8", errors="ignore").read()
        isA = with_prior(is1, chain)                      # earlier languages are protected too
        which, ea, eb = ARB.page_language(a, b2, isA, is2)
        if eb < gate:
            merged, how = a, "untouched"
        elif which == "B":
            merged = merge_lines(b2, a, is2, isA, False); how = "second-language page"
        else:
            merged = merge_lines(a, b2, isA, is2, primary != "ido"); how = "merged"
        if suffix:                        # --suffix: BESIDE the existing merge, nothing replaced or removed
            open(f"{base}.{w}.{'+'.join(chain + [lang])}.arb.{suffix}.txt", "w", encoding="utf-8").write(merged + "\n")
        else:
            open(f"{base}.{w}.{'+'.join(chain + [lang])}.arb.txt", "w", encoding="utf-8").write(merged + "\n")
            if lang == "fra" and os.path.exists(legacy):
                os.remove(legacy)             # superseded first-generation French merge
        tally["re-merged: " + how] += 1
    if not suffix:
        write_summary(d, pages, verdicts, corpus, lang, skipped_tl)
    return corpus, tally


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--lang", default="fra")
    ap.add_argument("--corpus", default=None, help="only corpora whose name contains this")
    # MEASURED 2026-09-26 for French (3 samples, gates 0/3/10): gate 0 best on all — Progreso 5 went
    # 0 → 43 accents at gate 0 and stayed at 0 at gate 10 (French NAMES never reach 10 word types);
    # the damage count did not move with the gate. Catalan was measured at 10; pass it explicitly.
    ap.add_argument("--page-gate", type=int, default=0)
    ap.add_argument("--files", type=int, default=6)
    ap.add_argument("--remerge", action="store_true",
                    help="recompute merges from second readings on disk (no OCR)")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--suffix", default=None,
                    help="with --remerge: write page-NNNN.<w>.<langs>.arb.<SUFFIX>.txt BESIDE the existing merge; replace/remove nothing")
    ap.add_argument("--primary", default=None, help="force the primary language (e.g. ido) — for comparisons")
    a = ap.parse_args()

    full = {"fra": "french", "deu": "german", "ces": "czech", "pol": "polish", "cat": "catalan",
            "nld": "dutch", "spa": "spanish", "swe": "swedish", "ita": "italian", "dan": "danish",
            "est": "estonian", "eng": "english"}[a.lang]
    gate = json.load(open(a.gate, encoding="utf-8"))
    rows = [r for r in gate if any(x["lang"] == full for x in r["all_seconds"])]
    if a.corpus:
        rows = ([r for r in rows if r["corpus"] in set(a.corpus[1:].split(","))] if a.corpus.startswith("=")   # «=a,b,c»: exact names
                else [r for r in rows if a.corpus.lower() in r["corpus"].lower()])
    verdicts = {v["page"]: v["winner"] for v in json.load(open(a.verdicts, encoding="utf-8"))}
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip()
            for l in open(a.pdfs, encoding="utf-8") if l.strip()}
    # DECLARED BEATS DETECTED (approved by the editor, 2026-09-27): the gate only DETECTS, so progreso1 — Ido by
    # rule, detected as Esperanto — was merged with the ESPERANTO lexicon (812 pages). Use the declaration.
    qs = _mod("ocr_quality_scan", "ocr-quality-scan.py")
    # MEASURED EXCEPTION (2026-09-27): progreso1 (1908) prints much ESPERANTO — the debate was argued in
    # both — and an Ido-lexicon merge strips the hats off it («ĝi»→«&i», «ĉar»→«éar»): Ido∪Esperanto hit-rate
    # 0.9163 against 0.9277 for the Esperanto-lexicon merge (812 pp; `page-NNNN.*.arb.ido.txt` kept beside,
    # unused). So its MERGE stays Esperanto, whatever its declaration.
    MERGE_PRIMARY = {"progreso1": "esperanto"}
    def prim(r):
        if a.primary:
            return a.primary
        if r["corpus"] in MERGE_PRIMARY:
            return MERGE_PRIMARY[r["corpus"]]
        dcl = qs.declared_for(f"/{r['corpus']}.")
        return dcl if dcl not in ("MISS", None) else r["primary"]
    jobs = [(r["corpus"], pdfs[r["corpus"]], a.root, prim(r), a.lang,
             {k: v for k, v in verdicts.items() if k.startswith(r["corpus"] + "/")},
             a.page_gate, a.jobs, a.suffix) for r in rows if r["corpus"] in pdfs]
    print(f"{len(jobs)} corpora flagged for {full} · page gate {a.page_gate}", file=sys.stderr, flush=True)
    total = collections.Counter()
    with fut.ProcessPoolExecutor(max_workers=a.files) as pool:
        for corpus, t in pool.map(remerge_corpus if a.remerge else do_corpus, jobs):
            total.update(t)
            print(f"  {corpus[:50]:<52} " + " · ".join(f"{k} {v}" for k, v in t.items()),
                  file=sys.stderr, flush=True)
    print("done · " + " · ".join(f"{k} {v:,}" for k, v in total.most_common()), file=sys.stderr)


if __name__ == "__main__":
    main()
