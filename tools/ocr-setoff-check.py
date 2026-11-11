#!/usr/bin/env python3
r"""ocr-setoff-check — pages that carry only a MIRRORED SET-OFF of the facing page's ink, found so that their garbage
OCR can be kept out of the search text.

    tools/ocr-setoff-check.py candidates --out <tsv> [--min-ink 0.5] [--max-bands 2] [--max-hits5 3]
    tools/ocr-setoff-check.py test --candidates <tsv> --out <tsv> [--pdfs <list>] [--jobs 9]   # PDF paths from the G1 cache
    tools/ocr-setoff-check.py review --test <test tsv> --out <new folder>    # the editor's review document
    tools/ocr-setoff-check.py mark --item <item> --page N --mirrors M --why "<the ruling, dated>"   # on his ruling only

WHY (2026-10-28, cupel19a). *Dia Regno* 1912 (ANNO_e1q_19120055) PDF 11 is the blank inside of the back wrapper with
p.40's ink set off onto it in mirror (the editor, 12:1x); PDF 2 is the same at the
front, «DIA REGNO» in mirror. Their OCR is garbage, and it stood in the search text, where the fuzzy name matching
on small capitals can take a garbage string for a garbled name (the editor). The empties look called PDF 11 LOST, and four vision readers read the mirror
image as right-reading, the text they expected: a fluent reading is no proof of a page's orientation.

candidates  NO IMAGE WORK, NO TESSERACT (the editor, 12:2x).
            Reads only the G1 ink cache (`sources/ocr-work/g1-ink-cache.noindex/`, the silent pages G1 has measured)
            and the page's base reading. A page qualifies only if ALL hold:
              - G1 ink >= --min-ink (0.5) with at most --max-bands (2) bands of type: G1's Otsu split the faint paper's
                own tones, so the page measures as nearly all «ink» in one band (PDF 2: 0.967, 1 band; PDF 11: 0.974,
                1 band). A page of real print measures a few per cent ink in many bands.
              - at most --max-hits5 (3) words of 5+ letters in the base reading found in any lexicon (all of
                `tools/lexicons/*.txt`, folded, as `ocr-flip-check.py` scores).
            Writes corpus · page · ink · inked rows · bands · words 5+ · lexicon hits 5+.
test        NO TESSERACT. Each candidate's ink layout (the page image the conversion read, `ocr_page_images`, averaged
            down to 48 × 72), flipped left to right, is correlated with the layouts of the pages before and after, and
            unflipped as the control (see `test` below for the rule). Rows written page by page, resumable. A pass is
            a CANDIDATE for the editor's review document, not yet a marking. (A first test by mirrored OCR, the same
            day, read PDF 11's set-off as pure noise and was dropped.)
Reads only, apart from --out (refused if it exists, for candidates) and the test's texts folder. Miles.
"""
import os, re, sys, glob, json, shutil, argparse, tempfile, subprocess, threading, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
GENIZA = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
R = os.path.join(GENIZA, "sources", "ocr-rendersearch")
CACHE = os.path.join(GENIZA, "sources", "ocr-work", "g1-ink-cache.noindex")


def flip():
    import importlib.util
    s = importlib.util.spec_from_file_location("ocr_flip_check", os.path.join(HERE, "ocr-flip-check.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def words5(t, F):
    return [F.fold(w) for w in re.findall(r"[^\W\d_]{5,}", t)]


def base(c, p):
    f = os.path.join(R, c, f"page-{p:04d}.txt")
    return open(f, encoding="utf-8", errors="ignore").read() if os.path.exists(f) else ""


def candidates_text(a, F, lex):
    """THE WIDER REACH (2026-10-28 17:3x, the editor to the proposal: the G1 cache holds only near-silent pages, so a
    set-off whose garbage OCR passes as text was not seen). Every base page of the corpus (or of --items) whose reading
    has at least --min-words5 words of 5+ letters and of them a share under --below in every lexicon together (the
    flip check's measure): the garbage a faint mirror image gives. Pages already marked .setoff or .blank are left out.
    Reads the texts only."""
    rows = []; seen = 0
    items = [l.strip() for l in open(a.items, encoding="utf-8") if l.strip()] if a.items else \
        sorted(d for d in os.listdir(R) if os.path.isdir(os.path.join(R, d)))
    # items whose language table names a language in a non-Latin script are left out: their print read with a Latin
    # model is garbage too, and no set-off (the first run, 4,430 pages in 320 items, was mostly these)
    NONLATIN = {"russian", "bulgarian", "ukrainian", "belarusian", "serbian", "macedonian", "georgian", "armenian",
                "japanese", "chinese", "korean", "greek", "hebrew", "yiddish", "arabic", "persian"}
    tabs = sorted(glob.glob(os.path.join(GENIZA, "OCR-TEXT-LANGUAGES-20*.tsv")))
    skip = set()
    if tabs:
        for l in open(tabs[-1], encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 2 and not l.startswith("#") and NONLATIN & {s.strip() for s in x[1].split(",")}:
                skip.add(x[0])
    items = [c for c in items if c not in skip]
    for c in items:
        d = os.path.join(R, c)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            m = re.fullmatch(r"page-(\d+)\.txt", f)
            if not m:
                continue
            p = int(m.group(1)); seen += 1
            if any(os.path.exists(os.path.join(d, f"page-{p:04d}.{k}")) for k in ("setoff", "blank")):
                continue
            ws = words5(open(os.path.join(d, f), encoding="utf-8", errors="ignore").read(), F)
            if len(ws) >= a.min_words5:
                hits = sum(w in lex for w in ws)
                if hits / len(ws) < a.below:
                    rows.append((c, p, "", "", "", len(ws), hits))
    return rows, seen


def candidates(a):
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    F = flip(); lex = F.lexicon(); rows = []; seen = 0
    if a.source == "text":
        rows, seen = candidates_text(a, F, lex)
        with open(a.out, "x", encoding="utf-8") as fh:
            fh.write("corpus\tpage\tink\tinked_rows\tbands\twords5\thits5\n")
            fh.writelines("\t".join(map(str, x)) + "\n" for x in sorted(rows))
        print(f"{seen} pages read · {len(rows)} candidates in {len({x[0] for x in rows})} items (by the text) → {a.out}")
        return
    for f in sorted(glob.glob(os.path.join(CACHE, "*.json"))):
        c = os.path.splitext(os.path.basename(f))[0]
        try:
            ink = json.load(open(f, encoding="utf-8"))["ink"]
        except Exception:
            continue
        for p, r in ink.items():
            seen += 1
            if r is None or r[0] < a.min_ink or r[2] > a.max_bands:
                continue
            ws = words5(base(c, int(p)), F); hits = sum(w in lex for w in ws)
            if hits <= a.max_hits5:
                rows.append((c, int(p), round(r[0], 3), round(r[1], 3), r[2], len(ws), hits))
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("corpus\tpage\tink\tinked_rows\tbands\twords5\thits5\n")
        fh.writelines("\t".join(map(str, x)) + "\n" for x in sorted(rows))
    print(f"{seen} measured pages in the ink cache · {len(rows)} candidates in {len({x[0] for x in rows})} items → {a.out}")


def stretch(g):
    w, h = g.size; c = g.crop((w // 10, h // 10, w - w // 10, h - h // 10))
    hist = c.histogram(); n = sum(hist); acc = 0; lo = hi = None
    for v, k in enumerate(hist):
        acc += k
        if lo is None and acc >= 0.01 * n: lo = v
        if hi is None and acc >= 0.90 * n: hi = v
    if hi <= lo: return g
    return g.point(lambda v: 0 if v <= lo else 255 if v >= hi else (v - lo) * 255 // (hi - lo))


def layout(path):
    """The page's ink layout, coarse: the middle 80% of the image, greyscale, averaged down to 48 × 72, inverted (ink
    high), normalised. Lines of type and their blocks survive; paper grain and the faintness of a set-off do not."""
    import numpy as np
    from PIL import Image, ImageFilter
    g = Image.open(path).convert("L"); w, h = g.size
    g = g.crop((w // 10, h // 10, w - w // 10, h - h // 10)).resize((480, 720), Image.BOX)
    # the broad shading taken off (frame, page edge, uneven light, a set-off's faintness), so that what is compared is
    # the line-scale structure of type (first form, without this: PDF 2 and 11 below the bar, the frame dominating)
    x = np.asarray(g, dtype=float) - np.asarray(g.filter(ImageFilter.BoxBlur(12)), dtype=float)
    x = -x.reshape(144, 5, 96, 5).mean(axis=(1, 3)); x -= x.mean(); s = x.std()
    return x / s if s else x


def match(x, y, shift=10):
    """The best correlation of two layouts over shifts of up to `shift` cells each way."""
    import numpy as np
    best = -1.0; H, W = x.shape
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            a = x[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)]
            b = y[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
            if a.size:
                a = a - a.mean(); b = b - b.mean(); d = np.sqrt((a * a).sum() * (b * b).sum())
                if d: best = max(best, float((a * b).sum() / d))
    return best


def test(a):
    """THE IMAGE TEST (2026-10-28, replacing a mirrored-OCR test that read PDF 11's set-off as pure noise: contrast
    raised far enough to show the ink raised the paper grain with it). No Tesseract. The candidate's layout, flipped
    left to right, against each neighbour's layout; and unflipped, as the control (a page that merely resembles its
    neighbour scores alike both ways). CALIBRATED on the two known set-offs, Dia Regno 1912 (ANNO_e1q_19120055) PDF 2
    (flipped 0.406 against PDF 3, plain 0.164) and PDF 11 (0.328 against PDF 10, plain 0.150); the other 67 candidates
    of the first run mostly 0.02-0.16, alike both ways. SET-OFF: flipped >= 0.25 and >= plain + 0.12. MARGINAL:
    flipped >= 0.10 and >= plain + 0.05, for the review document. Two known cases only: the bar is provisional."""
    import numpy as np
    import ocr_page_images as OPI
    # each PDF's path from the G1 cache, which records it (--pdfs only to override)
    paths = {}
    for f in glob.glob(os.path.join(CACHE, "*.json")):
        try:
            paths[os.path.splitext(os.path.basename(f))[0]] = json.load(open(f, encoding="utf-8"))["pdf"]
        except Exception:
            pass
    if a.pdfs:
        paths.update({os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()})
    cand = collections.defaultdict(list)
    for l in list(open(a.candidates, encoding="utf-8"))[1:]:
        f = l.rstrip("\n").split("\t"); cand[f[0]].append(int(f[1]))
    done = set()
    if os.path.exists(a.out):
        for l in list(open(a.out, encoding="utf-8"))[1:]:
            f = l.rstrip("\n").split("\t")
            if not f[-1].startswith("error"):   # a failed row is read again
                done.add((f[0], int(f[1])))
    else:
        open(a.out, "x", encoding="utf-8").write(
            "corpus\tpage\tflipped_prev\tplain_prev\tflipped_next\tplain_next\tverdict\tmirrors\n")
    lock = threading.Lock(); missing = sorted(c for c in cand if c not in paths)

    def item(c):
        todo = [p for p in cand[c] if (c, p) not in done]
        if not todo or c not in paths:
            return 0
        work = tempfile.mkdtemp(prefix="setoff-"); n = 0
        try:
            want = sorted({q for p in todo for q in (p - 1, p, p + 1) if q >= 1})
            im = OPI.page_images(paths[c], work, jobs=1, pages=want)
            for p in todo:
                if p not in im:
                    continue
                try:
                    x = layout(im[p]); xf = np.fliplr(x); sc = []
                    for q in (p - 1, p + 1):
                        if q in im:
                            y = layout(im[q]); sc.append((round(match(xf, y), 3), round(match(x, y), 3), q))
                        else:
                            sc.append((0.0, 0.0, q))
                    best = max(sc)
                    v = ("SET-OFF" if best[0] >= 0.25 and best[0] >= best[1] + 0.12 else
                         "MARGINAL" if best[0] >= 0.10 and best[0] >= best[1] + 0.05 else "no")
                    row = (c, p, sc[0][0], sc[0][1], sc[1][0], sc[1][1], v, best[2] if v != "no" else "")
                except Exception as e:
                    row = (c, p, 0, 0, 0, 0, "error " + str(e)[:60], "")
                with lock:
                    with open(a.out, "a", encoding="utf-8") as fh:
                        fh.write("\t".join(map(str, row)) + "\n")
                n += 1
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return n
    total = 0
    with fut.ThreadPoolExecutor(a.jobs) as ex:
        for n in ex.map(item, sorted(cand)):
            total += n
    print(f"pages read {total} · already done {len(done)} · items not in --pdfs {missing}")


def review(a):
    """The editor's review document (bulk decisions go to a generated document, every item shown): for each SET-OFF
    and MARGINAL row of --test, one image `NN.png` in --out, the page FLIPPED and contrast-raised on the left, the page
    it would mirror on the right; and `REVIEW.md` listing every page with its scores, its image and a ruling line.
    Refuses an existing --out folder."""
    import ocr_page_images as OPI
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = None
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    paths = {}
    for f in glob.glob(os.path.join(CACHE, "*.json")):
        try:
            paths[os.path.splitext(os.path.basename(f))[0]] = json.load(open(f, encoding="utf-8"))["pdf"]
        except Exception:
            pass
    if a.pdfs:   # pages outside the G1 cache (candidates --source text) need the full list, as `test` does
        paths.update({os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()})
    rows = [l.rstrip("\n").split("\t") for l in list(open(a.test, encoding="utf-8"))[1:]]
    rows = sorted((r for r in rows if r[6] in ("SET-OFF", "MARGINAL")), key=lambda r: (r[6] != "SET-OFF", r[0], int(r[1])))
    os.makedirs(a.out)
    md = ["# Set-off pages: review (2026-10-28)", "",
          "Each image: LEFT the page, flipped left to right and its contrast raised; RIGHT the page it would mirror. "
          "A set-off page carries only the facing page's ink in mirror; flipped, it should read as that page. "
          "Made by `tools/ocr-setoff-check.py review` from `" + os.path.basename(a.test) + "`. "
          "Rule each page on its ruling line: SET-OFF (its readings to be kept out of the search text) or KEEP.", ""]
    for k, r in enumerate(rows, 1):
        c, p, q = r[0], int(r[1]), int(r[7])
        work = tempfile.mkdtemp(prefix="setoff-rv-")
        try:
            im = OPI.page_images(paths[c], work, jobs=1, pages=[p, q])
            L = stretch(ImageOps.mirror(Image.open(im[p]).convert("L"))); Rr = Image.open(im[q]).convert("L")
            L.thumbnail((1100, 1600)); Rr.thumbnail((1100, 1600))
            out = Image.new("L", (L.width + Rr.width + 20, max(L.height, Rr.height)), 255)
            out.paste(L, (0, 0)); out.paste(Rr, (L.width + 20, 0)); out.save(os.path.join(a.out, f"{k:02d}.png"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        fl, pl = (r[2], r[3]) if q == p - 1 else (r[4], r[5])
        md += [f"## {k:02d}. {c}, PDF page {p} (would mirror PDF page {q}): test {r[6]}", "",
               f"Flipped {fl}, plain {pl}.", "", f"![{c} PDF {p} flipped, beside PDF {q}]({k:02d}.png)", "",
               "Ruling: ", ""]
    open(os.path.join(a.out, "REVIEW.md"), "x", encoding="utf-8").write("\n".join(md))
    print(f"{len(rows)} pages → {a.out}/REVIEW.md")


def census(a):
    """Every `page-NNNN.blank` and `page-NNNN.setoff` marker in the corpus, with its first line (the reason recorded),
    to --out (refused if it exists); and, printed, each line of tools/*.py that names «.blank» (what writes them)."""
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    rows = []
    for f in sorted(glob.glob(os.path.join(R, "*", "page-*.blank")) + glob.glob(os.path.join(R, "*", "page-*.setoff"))):
        m = re.fullmatch(r"page-(\d+)\.(blank|setoff)", os.path.basename(f))
        if m:
            first = open(f, encoding="utf-8", errors="ignore").readline().strip().replace("\t", " ")
            rows.append((m.group(2), os.path.basename(os.path.dirname(f)), int(m.group(1)), first))
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("marker\titem\tpage\tfirst_line\n")
        fh.writelines("\t".join(map(str, r)) + "\n" for r in rows)
    k = collections.Counter(r[0] for r in rows)
    print(f"{dict(k)} markers in {len({r[1] for r in rows})} items → {a.out}")
    for t in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        for i, l in enumerate(open(t, encoding="utf-8", errors="ignore"), 1):
            if ".blank" in l and os.path.basename(t) != "ocr-setoff-check.py":
                print(f"{os.path.basename(t)}:{i}: {l.strip()[:140]}")


def mark(a):
    """Writes `page-NNNN.setoff` in the item's folder (created new, refused if it exists), holding the page it mirrors
    and the ruling. `tools/ocr-rebuild-combined.py` then empties both its preferred and its search text, and
    `tools/ocr-search-all-readings.py` leaves it out; its readings stay on disk. Only on the editor's ruling."""
    d = os.path.join(R, a.item)
    if not os.path.isdir(d):
        sys.exit(f"no item folder: {d}")
    f = os.path.join(d, f"page-{a.page:04d}.setoff")
    with open(f, "x", encoding="utf-8") as fh:
        fh.write(f"set-off: a mirror image of PDF page {a.mirrors}, no print of its own\n{a.why}\n"
                 "written by tools/ocr-setoff-check.py mark; every reading of this page is kept out of the preferred "
                 "and the search text (tools/ocr-rebuild-combined.py)\n")
    print(f"marked {a.item} PDF {a.page} (mirrors PDF {a.mirrors}) → {f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("candidates", "test", "review", "mark", "census")); ap.add_argument("--out")
    ap.add_argument("--item"); ap.add_argument("--page", type=int); ap.add_argument("--mirrors", type=int)
    ap.add_argument("--why", help="mark: the ruling, dated")
    ap.add_argument("--test", help="review: the test TSV")
    ap.add_argument("--min-ink", type=float, default=0.5); ap.add_argument("--max-bands", type=int, default=2)
    ap.add_argument("--max-hits5", type=int, default=3)
    ap.add_argument("--source", choices=("g1", "text"), default="g1",
                    help="candidates: from the G1 ink cache (default) or from the texts of every page (the wider reach)")
    ap.add_argument("--below", type=float, default=0.25, help="candidates --source text: the lexicon share under which a page is garbage")
    ap.add_argument("--min-words5", type=int, default=10, help="candidates --source text: words of 5+ letters at least")
    ap.add_argument("--items", help="candidates --source text: a file of items, one a line (default: the whole corpus)")
    ap.add_argument("--candidates"); ap.add_argument("--pdfs"); ap.add_argument("--jobs", type=int, default=9)
    a = ap.parse_args()
    if a.mode == "mark" and not (a.item and a.page and a.mirrors and a.why):
        sys.exit("mark needs --item, --page, --mirrors and --why")
    if a.mode != "mark" and not a.out:
        sys.exit(f"{a.mode} needs --out")
    {"candidates": candidates, "test": test, "review": review, "mark": mark, "census": census}[a.mode](a)
