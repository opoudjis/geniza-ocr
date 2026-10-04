#!/usr/bin/env python3
r"""ocr-flip-check — the HEURISTIC half of the rotation repair: pages whose reading hits no lexicon, read turned.

    tools/ocr-flip-check.py candidates --below 0.35 --out <tsv>          # pages whose reading hits no lexicon well
    tools/ocr-flip-check.py test --candidates <tsv> --pdfs <list> --out <tsv> [--jobs 8]
    tools/ocr-flip-check.py decide --test <test tsv> --out <tsv>          # apply the DECISION RULE (below) to a test

WHY (the editor ruled on 2026-09-29: the exact check first, then the heuristic). The exact half (`ocr-rotation-flag.py`) repairs pages a PDF turns
with a /Rotate. A scan can also be stored upside down or sideways with NO flag, and G5 found upside-down readings
the rotation check had missed. That check had a second fault: it scored a re-read on the ESPERANTO scale, so on
Czech pages (Bohema) an upside-down reading, which is junk in every language, scored higher than the right-way-up
Czech and was kept (an internal failure log, 2026-09-29, not published).
HOW, so that the language of the page cannot mislead it:
  candidates  every page of >= 40 words whose reading hits few words in ANY lexicon (all of `tools/lexicons/*.txt`
              together — Esperanto, Ido, Occidental, the national languages, Estonian, Russian — folded: lower case,
              diacritics off, old Cyrillic letters folded). Real text hits its own language; a turned reading hits none.
              2026-09-29: 1,453 pages in 147 items below 0.35. Most are real non-Latin print (Russian, Georgian,
              Armenian read with a Latin model), which a turn does not help.
  test        each candidate read turned by 180, 90 and 270 degrees (from the image the conversion reads, which now
              honours /Rotate), each reading scored the same way. A turn is a REPAIR only where it scores far above
              the current reading; the decision and the re-read are separate, reviewed steps.
              DECISION RULE (2026-09-29, after the first rule was fooled): on words of 5+ letters, a turn is a repair
              only if it is the UNIQUE best — well above the current reading AND above both other turns. A real page
              has one right way up; if two turns both score well, the scores are junk hitting the lexicon by chance.
              The turned texts are kept (`<out>.texts/`), so a rule can be re-scored without re-reading.
              THRESHOLDS: best turn >= 0.5 on >= 10 words of 5+ letters, >= current + 0.2, >= next-best turn + 0.3.
              Checked on 11 pages: the page the blank sort found printed sideways (kongresa.libro.03 p.94: 270°
              0.71 against 0.2/0.0) passes; Bulteno de TEKS 1911.1 pp.1-8 and 59-58 pp.28-29 (Cyrillic read as Latin,
              where 90° and 270° scored alike) do not. A pass is a CANDIDATE for an image look, not yet a repair.
Reads only; writes the TSV page by page (and resumes from it), so an interrupted run loses nothing.
"""
import os, re, sys, glob, shutil, argparse, tempfile, subprocess, unicodedata, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
_OLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})


def fold(w):
    w = w.lower().translate(_OLD)
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def lexicon():
    lex = set()
    for f in glob.glob(os.path.join(HERE, "lexicons", "*.txt")):
        for l in open(f, encoding="utf-8", errors="ignore"):
            w = l.split("\t")[0].strip()
            if w:
                lex.add(fold(w))
    return lex


def score(t, lex, minlen=3):
    ws = [fold(w) for w in re.findall(r"[^\W\d_]{%d,}" % minlen, t)]
    return (sum(w in lex for w in ws) / len(ws) if ws else 0), len(ws)


def score5(t, lex):
    """On words of 5+ letters: sideways junk breaks into short fragments that hit an 18.7-million-form lexicon of
    every language by chance (2026-09-29: both sideways turns of Bulteno de TEKS scored 0.7-0.9); long words do not."""
    return score(t, lex, 5)


def candidates(a):
    lex = lexicon(); out = []; dist = collections.Counter()
    for d in sorted(glob.glob(os.path.join(R, "*"))):
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "page-*.txt")):
            m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
            if not m:
                continue
            s, n = score(open(f, encoding="utf-8", errors="ignore").read(), lex)
            if n >= 40:
                dist[int(s * 10)] += 1
                if s < a.below:
                    out.append((os.path.basename(d), int(m.group(1)), round(s, 3), n))
    open(a.out, "w").write("".join(f"{c}\t{p}\t{s}\t{n}\n" for c, p, s, n in sorted(out)))
    print("pages >= 40 words by all-lexicon rate (tenths):", dict(sorted(dist.items())))
    print(f"candidates below {a.below}: {len(out)} in {len({o[0] for o in out})} items")


def test(a):
    import ocr_page_images as OPI
    from PIL import Image
    lex = lexicon()
    paths = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    cand = collections.defaultdict(list)
    for l in open(a.candidates):
        c, p, s, n = l.rstrip("\n").split("\t"); cand[c].append((int(p), float(s)))

    done = set()
    if os.path.exists(a.out):   # resume: pages already written are not read again
        for l in list(open(a.out))[1:]:
            f = l.split("\t"); done.add((f[0], int(f[1])))
    else:
        open(a.out, "w").write("corpus\tpage\tscore_now\tangle\tscore_turned\twords\tscore5_now\tscore5_turned\twords5\n")
    txtdir = a.out + ".texts"; os.makedirs(txtdir, exist_ok=True)
    import threading
    lock = threading.Lock()

    def item(c):
        work = tempfile.mkdtemp(prefix="flip-"); n = 0
        try:
            todo = [(p, s0) for p, s0 in cand[c] if (c, p) not in done]
            if not todo:
                return 0
            im = OPI.page_images(paths[c], work, jobs=1, pages=[p for p, _ in todo])
            for p, s0 in todo:
                if p not in im:
                    continue
                try:
                    # greyscale first: a CMYK JPEG cannot be written as PNG (the crash of 2026-09-29, which lost a run)
                    img = Image.open(im[p]).convert("L")
                    now = open(os.path.join(R, c, f"page-{p:04d}.txt"), encoding="utf-8", errors="ignore").read()
                    s5n, _ = score5(now, lex)
                    rows = []
                    for ang in (180, 90, 270):
                        f = os.path.join(work, f"f{p}_{ang}.png"); img.rotate(ang, expand=True).save(f)
                        t = subprocess.run(["tesseract", f, "stdout", "-l", "epo", "--psm", "6"], capture_output=True, text=True).stdout
                        open(os.path.join(txtdir, f"{c}__{p:04d}__{ang}.txt"), "w", encoding="utf-8").write(t)
                        s, w = score(t, lex); s5, w5 = score5(t, lex)
                        rows.append((c, p, s0, ang, round(s, 3), w, round(s5n, 3), round(s5, 3), w5))
                except Exception as e:
                    rows = [(c, p, s0, "error", str(e)[:60], 0, 0, 0, 0)]
                with lock:   # written page by page, so a crash loses nothing
                    with open(a.out, "a") as f:
                        f.writelines("\t".join(map(str, r)) + "\n" for r in rows)
                n += 1
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return n
    total = 0
    with fut.ThreadPoolExecutor(a.jobs) as ex:
        for n in ex.map(item, sorted(cand)):
            total += n
    print("pages read", total, "· already done", len(done))


def decide(a):
    """THE DECISION RULE, applied (approved by the editor, 2026-10-04 13:2x: the rule lived only in this header, so
    RUNBOOK.md carried it as inline code; now the tool applies it). Per page, on words of 5+ letters: the best turn scores
    >= 0.5 on >= 10 words, >= the current reading + 0.2, and >= the next-best turn + 0.3. Writes one row per PASSING
    page: a CANDIDATE for an image look, not a repair. `angle` is counter-clockwise (PIL's rotate, as `test` turned
    the image); `rotate_cw` is the same turn clockwise, the form `tools/ocr-ruled-reread.py` takes (rotate=).
    Refuses an existing --out. Reads only the test TSV."""
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    r = collections.defaultdict(list)
    for l in list(open(a.test, encoding="utf-8"))[1:]:
        f = l.rstrip("\n").split("\t")
        if len(f) < 9 or f[3] == "error":
            continue
        r[(f[0], int(f[1]))].append((float(f[7]), int(f[8]), int(f[3]), float(f[6])))
    rows = []
    for (c, p), v in sorted(r.items()):
        v.sort(reverse=True); best = v[0]; nxt = v[1][0] if len(v) > 1 else 0.0
        if best[0] >= 0.5 and best[1] >= 10 and best[0] >= best[3] + 0.2 and best[0] >= nxt + 0.3:
            rows.append((c, p, best[2], (360 - best[2]) % 360, best[0], best[1], best[3], nxt))
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("corpus\tpage\tangle\trotate_cw\tscore5_turned\twords5\tscore5_now\tscore5_next\n")
        f.writelines("\t".join(map(str, x)) + "\n" for x in rows)
    print(f"{len(r)} page(s) tested · {len(rows)} pass the rule → {a.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("candidates", "test", "decide"))
    ap.add_argument("--below", type=float, default=0.35); ap.add_argument("--out", required=True)
    ap.add_argument("--candidates"); ap.add_argument("--pdfs"); ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--test")
    a = ap.parse_args()
    {"candidates": candidates, "test": test, "decide": decide}[a.mode](a)
