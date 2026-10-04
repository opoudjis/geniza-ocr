#!/usr/bin/env python3
r"""ocr-lost-reread — re-read pages an image sort called LOST, from enhanced versions of the page image.

    tools/ocr-lost-reread.py --list <tsv: NNN, batch, corpus, page, verdict, …> --pdfs <list> --out <dir> [--jobs 8]

WHY (2026-09-29: the editor asked for an attempt to eliminate every LOST page). The blank-page sort (an internal
record, 2026-09-29, not published) found 81 pages whose print is missing from the text, most of them FAINT scans (Progreso 4/5/7 above all: full text
pages that the G1 ink test took for blank paper, and that Tesseract read as noise). A faint page may read well once
its contrast is restored.
HOW: each page's image (the route the conversion uses; a /Rotate page is rendered) is read by `tesseract -l epo
--psm 6` in four versions: as is · autocontrast (0.5% cut) · autocontrast + sharpen · Otsu-binarised. Each reading,
and the current `page-NNNN.txt`, is scored as KNOWN WORDS of 5+ letters against all the Latin-script lexicons
together (short fragments hit an all-language lexicon by chance: the flip-test lesson of 09-29). The best
version is written to <out>/<corpus>__<page>.txt with a TSV of all scores. Nothing in the corpus is changed: a
reading replaces the current one only in a separate, reviewed step, and a page still poor goes to vision.
"""
import os, re, sys, glob, argparse, tempfile, shutil, subprocess, unicodedata, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
LATIN = ("esperanto", "ido", "occidental", "french", "german", "italian", "spanish", "catalan", "dutch", "danish",
         "swedish", "czech", "polish", "english", "latvian", "lithuanian", "estonian")


def fold(w):
    return "".join(ch for ch in unicodedata.normalize("NFD", w.lower()) if unicodedata.category(ch) != "Mn")


def lexicon():
    lex = set()
    for n in LATIN:
        f = os.path.join(HERE, "lexicons", n + ".txt")
        if os.path.exists(f):
            lex |= {fold(l.split("\t")[0].strip()) for l in open(f, encoding="utf-8", errors="ignore") if l.strip()}
    return lex


def known5(t, lex):
    ws = [fold(w) for w in re.findall(r"[^\W\d_]{5,}", t)]
    return sum(w in lex for w in ws), len(ws)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", required=True); ap.add_argument("--pdfs", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    # the corpus-wide second reading (approved by the editor, 2026-09-29; `docs/FAILURE-MAP.md` row 4): one version
    # (boost-sharp won every one of the 302 partly-read faint-volume pages), compared with the page as a SEARCH
    # reads it (its section of the combined `<corpus>.txt`), scores appended as each unit ends, done pages skipped
    ap.add_argument("--versions", default="plain,boost,boost-sharp,otsu")
    # --lang (2026-09-30, row 5 of docs/FAILURE-MAP.md): mixed Esperanto–Russian pages (Kaŭkaza Esperantisto,
    # La Ondo de Esperanto) need `epo+rus`, which reads both scripts on one page; the default keeps earlier runs identical.
    ap.add_argument("--lang", default="epo")
    ap.add_argument("--compare", choices=("page", "combined"), default="page")
    a = ap.parse_args()
    want = a.versions.split(",")
    import ocr_page_images as OPI
    from PIL import Image, ImageOps, ImageFilter
    lex = lexicon()
    paths = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    todo = collections.defaultdict(list)
    for l in open(a.list, encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if len(f) >= 4 and f[3].isdigit():
            todo[f[2]].append(int(f[3]))
    os.makedirs(a.out, exist_ok=True)
    # resume: a page is done only when its SCORE ROW is in SCORES.tsv. (Rows are appended when a 25-page unit ends,
    # so a page whose reading file exists may still lack its row if the run was stopped: that page is read again.)
    # A partial last line from a stop mid-write is dropped, and the file is made to end with a newline.
    sf = os.path.join(a.out, "SCORES.tsv")
    ncol = 7 + len(want)
    scored = set()
    if os.path.exists(sf):
        good = [l for l in open(sf, encoding="utf-8").read().split("\n") if l and len(l.split("\t")) == ncol]
        open(sf, "w", encoding="utf-8").write("\n".join(good) + "\n")
        scored = {(f[0], int(f[1])) for f in (l.split("\t") for l in good[1:]) if f[1].isdigit()}
    for c in list(todo):
        todo[c] = [p for p in todo[c] if (c, p) not in scored]
        if not todo[c] or c not in paths:
            del todo[c]

    # work units of 25 pages, so a few large volumes still spread over all the threads (the faint-volume run)
    units = [(c, sorted(todo[c])[i:i + 25]) for c in sorted(todo) for i in range(0, len(todo[c]), 25)]
    combined = {}

    def comb(c):
        if c not in combined:
            f = os.path.join(R, c + ".txt")
            t = open(f, encoding="utf-8", errors="ignore").read() if os.path.exists(f) else ""
            parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
            combined[c] = {int(p): x for p, x in zip(parts[1::2], parts[2::2])}
        return combined[c]

    import threading
    flock = threading.Lock()

    def failed(c, p, e):
        with flock, open(os.path.join(a.out, "FAILED.tsv"), "a", encoding="utf-8") as f:
            f.write(f"{c}\t{p}\t{type(e).__name__}: {str(e)[:200]}\n")

    def item(u):
        c, pages = u
        work = tempfile.mkdtemp(prefix="lost-"); rows = []
        try:
            try:
                im = OPI.page_images(paths[c], work, jobs=1, pages=pages)
            except Exception as e:
                for p in pages:
                    failed(c, p, e)
                return rows
            for p in pages:
                if p not in im:
                    continue
                if a.compare == "combined":
                    cur = comb(c).get(p, "")
                else:
                    cur = open(os.path.join(R, c, f"page-{p:04d}.txt"), encoding="utf-8", errors="ignore").read() \
                        if os.path.exists(os.path.join(R, c, f"page-{p:04d}.txt")) else ""
                # one page that cannot be opened must not stop the run (2026-09-29: a 615-megapixel scan raised
                # DecompressionBombError and killed the corpus-wide run at 51,226 pages): log it and go on
                try:
                    g = Image.open(im[p]).convert("L")
                except Exception as e:
                    failed(c, p, e)
                    continue
                ac = ImageOps.autocontrast(g, cutoff=0.5)
                hist = ac.histogram(); tot = sum(hist); s = sum(i * h for i, h in enumerate(hist)); sb = wb = 0; best = (0, 128)
                for i in range(256):       # Otsu threshold
                    wb += hist[i]
                    if not wb or wb == tot: continue
                    sb += i * hist[i]; mb = sb / wb; mf = (s - sb) / (tot - wb); v = wb * (tot - wb) * (mb - mf) ** 2
                    if v > best[0]: best = (v, i)
                versions = {"plain": g, "boost": ac, "boost-sharp": ac.filter(ImageFilter.SHARPEN),
                            "otsu": ac.point(lambda x, t=best[1]: 255 if x > t else 0)}
                versions = {n: v for n, v in versions.items() if n in want}
                reads = {}
                for name, img in versions.items():
                    f = os.path.join(work, f"{p}_{name}.png"); img.save(f)
                    reads[name] = subprocess.run(["tesseract", f, "stdout", "-l", a.lang, "--psm", "6"], capture_output=True, text=True).stdout
                sc = {n: known5(t, lex) for n, t in reads.items()}
                bestn = max(sc, key=lambda n: sc[n][0])
                open(os.path.join(a.out, f"{c}__{p:04d}.txt"), "w", encoding="utf-8").write(reads[bestn])
                rows.append((c, p, *known5(cur, lex), bestn, *sc[bestn], *[sc[n][0] for n in versions]))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return rows
    allrows = []
    if not os.path.exists(sf):
        open(sf, "w").write("corpus\tpage\tnow_known5\tnow_words5\tbest\tbest_known5\tbest_words5\t"
                            + "\t".join(n.replace("-", "_") for n in want) + "\n")
    print(f"{sum(len(v) for v in todo.values())} pages to read in {len(units)} units", flush=True)
    with fut.ThreadPoolExecutor(a.jobs) as ex, open(sf, "a") as f:
        for k, r in enumerate(ex.map(item, units), 1):
            allrows += r
            f.writelines("\t".join(map(str, x)) + "\n" for x in r); f.flush()
            if k % 200 == 0:
                print(f"{k}/{len(units)} units", flush=True)
    better = [r for r in allrows if r[5] >= max(20, 2 * r[2])]
    print(f"{len(allrows)} pages re-read · clearly better (>= 20 known long words and >= twice the current): {len(better)}")


if __name__ == "__main__":
    main()
