#!/usr/bin/env python3
r"""ocr-name-crops — the name snippets of a page, cut from the scan and packed into sheets, for vision on lines, not pages.

    python3 tools/ocr-name-crops.py build --pdfs <PDF list> (--pages <item>:<page>[,…] | --pages-file <tsv>) --out <new dir>
                                          [--per-sheet 40] [--max-per-page 40] [--lang epo]
    python3 tools/ocr-name-crops.py split --dir <run dir> [--max-scale 3.0]
    python3 tools/ocr-name-crops.py file  --dir <run dir> --root <$R>

WHY (failure map row 5b, its step 3 never built: «vision on the remaining small-caps line crops (not pages)»; the editor
2026-10-24 13:2x, after cupel18a's 698-page vision run: a win, since 9,000 pages across the corpus is not
feasible, to be explored; 13:3x: to be tested on the rest of *Svisa Espero*). A name set in small
capitals is a few words on a page; a page image spends a vision read on all of it, scaled down.
Exploration and first test: `geniza/ocr/method/NAME-CROPS-EXPLORATION-2026-10-24.md`.

build  Per page: the image the conversion read (`tools/ocr_page_images.py`), read by Tesseract (`--psm 4`, TSV) for its
       word boxes. A word is a CANDIDATE if it is capitalised, 4+ letters, and in no Latin-script list of `tools/lexicons/`
       (case and accents folded), or a telltale garble (the widened test of `tools/ocr-smallcaps-reread.py`). Candidates
       on one line are joined, with one word on either side; each run is cut from the image with a margin as a SNIPPET
       (`snippets/<id>.png`). A page with more than --max-per-page snippets (a directory, a name on every line) is cut
       nothing and listed in `WHOLE-PAGES.tsv`, for a page read instead. Snippets are packed into SHEETS
       (`sheets/sheet-NNN.png`, --per-sheet a sheet, one column, each id printed beside it), one vision read a sheet.
       `KEY.tsv`: id, sheet, item, page, box, Tesseract's text. --pages-file: a TSV of item and PDF page (other columns
       ignored; a KEY-ALL.tsv of a vision run reads as batch, tag, item, page: give --pages-cols 3,4), --items a regex
       on the item. --german: a German compound (two German list words, a linking s/n/en/e/er between) is no
       candidate unless an initial or title stands before it («J. Feierabend» stays). --skip-done <$R>: pages with a
       snippet reading already are not cut again.
split  Sheets too large for a reader to see their ids (shrunk more than --max-scale times) packed again as pieces
       `sheets/sheet-NNN-pK.png` of at most 2000 px a side; each piece read as a sheet (split() says why).
file   Every return `returns/sheet-NNN.txt` (lines «sNNNNN<TAB>text as printed», or «sNNNNN<TAB>NOT SEEN») against
       KEY.tsv: each page's readings, in snippet order, written as `<root>/<item>/page-NNNN.names.txt`, a SEARCH-ONLY
       reading (`tools/ocr-rebuild-combined.py` joins it to the search text as it does `.sc3x`; the preferred reading
       unchanged), only where no such file exists; `FILED.tsv` in the run dir.
--tier N (2026-10-25, run sheet C7b.2a): the candidates are the words of small-capital tier N of
       `tools/smallcaps-signals.py` (its signs on Tesseract's words here, the word before counted for «after a title»),
       not the rule above; `TIER.txt` in the run dir, which `file` copies into FILED.tsv as a `tier` line.
WRITE-SET: build: --out only, a new folder (refused if it exists, unless --resume; KEY-PARTIAL.tsv, DONE.tsv and PROGRESS.txt
as it goes), the page renders in a temporary folder removed after;
split: `<dir>/sheets/sheet-NNN-pK.png` and `<dir>/SPLIT.tsv` (appended);
file: the new `page-NNNN.names.txt` files and `<dir>/FILED.tsv`.
"""
import argparse, csv, glob, importlib.util, io, os, re, subprocess, sys, tempfile, shutil, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
TELL = re.compile(r"\b[A-ZÀ-Ž][a-zà-ž]+[A-ZÀ-Ž]{2,}[a-zà-ž]*\b|\b[A-ZÀ-Ž]{2,}[a-zà-ž]{1,2}[A-ZÀ-Ž]+[a-zà-ž]{0,2}\b")
LATIN = ("esperanto", "french", "german", "english", "ido", "italian", "spanish", "portuguese", "dutch", "catalan",
         "occidental", "latino-sine-flexione", "latin")


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))


def lexicon():
    w = set()
    for n in LATIN:
        f = os.path.join(HERE, "lexicons", n + ".txt")
        if os.path.exists(f):
            w.update(fold(l.strip()) for l in open(f, encoding="utf-8", errors="ignore") if l.strip())
    return w


# A GERMAN COMPOUND is no name (2026-10-24, the editor:
# the first sheets of *Svisa Espero* were full of «Generalversammlung», «Esperantistengruppe»): a word that splits into two
# German list words of 3+ letters (with a linking s, n, en, e or er between them, or none) — unless an initial or a title
# stands before it, because Swiss surnames are compounds too («J. Feierabend», «Sro Rusterholz»)
TITLE = re.compile(r"^(?:[A-ZÀ-ŽĈĜĤĴŜŬ][a-zà-ž]?\.|(?:S-?roj?|D-?ro|F-?ino|S-?ino|Prof|Herr[n]?|Hr|Frau|Frl|Mr|Mme|Mlle|M|MM|Dr|Pastro|Fr)\.?,?)$")


PARTICLES = {"von", "van", "vom", "zum", "zur", "ten", "ter", "den", "des", "del", "dei", "della", "les", "aux"}


def german(lex_de, w):
    f = fold(w)
    for i in range(3, len(f) - 2):
        a, b = f[:i], f[i:]
        if b in lex_de and len(b) >= 3:
            for link in ("", "s", "n", "en", "e", "er"):
                if a.endswith(link) and len(a) - len(link) >= 3 and a[:len(a) - len(link)] in lex_de:
                    return True
    return False


def candidate(t, lex, lex_de=None, prev=""):
    core = re.sub(r"^[^\w]+|[^\w]+$", "", t)
    if TELL.search(core):
        return True
    if not (len(core) >= 4 and core[:1].isupper() and core[1:2].isalpha() and fold(core) not in lex):
        return False
    return not (lex_de and german(lex_de, core) and not TITLE.match(prev.strip()))


def words(img, lang):
    r = subprocess.run(["tesseract", img, "-", "--psm", "4", "-l", lang, "tsv"], capture_output=True, text=True,
                       env=dict(os.environ, OMP_THREAD_LIMIT="1"))   # one thread a page: --jobs pages run at once
    rows = list(csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE))
    return [x for x in rows if x.get("level") == "5" and (x.get("text") or "").strip()]


def german_lexicon():
    f = os.path.join(HERE, "lexicons", "german.txt")
    return {fold(l.strip()) for l in open(f, encoding="utf-8", errors="ignore") if len(l.strip()) >= 3}


def runs(ws, lex, lex_de=None, pred=None):
    lines = {}
    for w in ws:
        lines.setdefault((w["block_num"], w["par_num"], w["line_num"]), []).append(w)
    out = []
    for ln in lines.values():
        if pred:   # --tier: the small-capital tier's words only (tools/smallcaps-signals.py), not every candidate;
            # «after a title» over the line's run of names («S-roj X, Y kaj Z»: all three)
            tr = pred.title_run([w["text"] for w in ln])
            flag = [pred(w["text"], tr[k] or (ln[k - 1]["text"] if k else "")) for k, w in enumerate(ln)]
        else:
            flag = [candidate(w["text"], lex, lex_de, ln[k - 1]["text"] if k else "") for k, w in enumerate(ln)]
        if lex_de and not pred:
            # a capitalised word NEXT TO a German list word («dass Verdchtlich-», «Stidte des», «graphische Zeitschrilt»)
            # is a German noun, OCR-damaged or not, unless an initial or a title stands before it («Herr Colardeau»); a
            # name particle (von, van, de, du …) is no German neighbour; telltale garbles still count. (Tesseract joins the
            # French and German columns of a bilingual page into one line, so the line's language cannot be judged.)
            def de(k):
                if not 0 <= k < len(ln):
                    return False
                x = fold(re.sub(r"[^\w]", "", ln[k]["text"]))
                return len(x) >= 3 and x.isalpha() and x not in PARTICLES and x in lex_de and not ln[k]["text"][:1].isupper()
            flag = [f and (bool(TELL.search(w["text"])) or (k > 0 and bool(TITLE.match(ln[k - 1]["text"].strip())))
                           or not (de(k - 1) or de(k + 1)))
                    for k, (f, w) in enumerate(zip(flag, ln))]
        i = 0
        while i < len(ln):
            if not flag[i]:
                i += 1; continue
            j = i
            while j + 1 < len(ln) and (flag[j + 1] or (j + 2 < len(ln) and flag[j + 2])):
                j += 1
            out.append(ln[max(0, i - 1):min(len(ln) - 1, j + 1) + 1]); i = j + 1
    return out


def build(a):
    from ocr_page_images import page_images
    from PIL import Image, ImageDraw, ImageFont
    Image.MAX_IMAGE_PIXELS = None
    if os.path.exists(a.out) and not a.resume:
        sys.exit(f"exists: {a.out} (give --resume to continue it)")
    paths = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    want = {}
    if a.pages_file:
        ci, cp = (int(x) - 1 for x in a.pages_cols.split(","))
        for l in open(a.pages_file, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) > max(ci, cp) and f[cp].isdigit() and (not a.items or re.search(a.items, f[ci])):
                want.setdefault(f[ci], []).append(int(f[cp]))
    else:
        for s in a.pages.split(","):
            it, p = s.rsplit(":", 1); want.setdefault(it, []).append(int(p))
    os.makedirs(os.path.join(a.out, "snippets"), exist_ok=a.resume); os.makedirs(os.path.join(a.out, "sheets"), exist_ok=a.resume)
    lex, key, snips, whole = lexicon(), [], [], []
    # SAVED AS IT GOES (run sheet rule 0, «Long runs save as they go, can be resumed, and report»; 2026-10-25, before
    # round 1's 9,173 pages): a row a snippet to KEY-PARTIAL.tsv, an item to DONE.tsv when its pages are cut, PROGRESS.txt;
    # --resume reloads them (the crops from snippets/) and goes on with the items not done
    kp, dn = os.path.join(a.out, "KEY-PARTIAL.tsv"), os.path.join(a.out, "DONE.tsv")
    done_items = set()
    if a.resume and os.path.exists(kp):
        for l in open(kp, encoding="utf-8"):
            r = l.rstrip("\n").split("\t")
            if len(r) >= 6 and r[0].startswith("s"):
                key.append([r[0], "", r[2], int(r[3]), r[4], r[5]])
                snips.append((r[0], Image.open(os.path.join(a.out, "snippets", r[0] + ".png")).copy()))
        if os.path.exists(dn):
            for l in open(dn, encoding="utf-8"):
                x = l.rstrip("\n").split("\t")
                done_items.add(x[0])
                if len(x) >= 3 and x[1] == "WHOLE": whole.append((x[0], int(x[2]), int(x[3])))
        done_items.discard("")
    t0 = __import__("time").time()
    lex_de = german_lexicon() if a.german else None
    pred = None
    if a.tier:   # THE TIER (the editor 2026-10-25 01:3x; run sheet C7b.2a)
        _ss = importlib.util.spec_from_file_location("ss", os.path.join(HERE, "smallcaps-signals.py"))
        SS = importlib.util.module_from_spec(_ss); _ss.loader.exec_module(SS)
        pred = SS.tier_predicate(a.tier, a.roster)
        open(os.path.join(a.out, "TIER.txt"), "w", encoding="utf-8").write(f"{a.tier}\t{a.tier_note or ''}\n")
    if a.skip_done:   # pages that already have a snippet reading (an earlier run) are not cut again
        want = {it: [p for p in pp if not os.path.exists(os.path.join(a.skip_done, it, f"page-{p:04d}.names.txt"))]
                for it, pp in want.items()}
        want = {it: pp for it, pp in want.items() if pp}
    for n_it, (it, pp) in enumerate(want.items()):
        if it in done_items: continue
        work = os.path.realpath(tempfile.mkdtemp(prefix="crops-"))   # Tesseract opens /private/tmp/…, not the /tmp/… link
        try:
            im = page_images(paths[it], work, jobs=max(2, a.jobs), pages=sorted(set(pp)))
            # --jobs pages at once (the editor 2026-10-25 11:3x): Tesseract's word boxes read in
            # parallel, one Tesseract thread each; the snippets are then cut and numbered in page order, as before
            import concurrent.futures as _fut
            with _fut.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
                read = dict(zip([p for p in sorted(set(pp)) if p in im],
                                pool.map(lambda p: runs(words(im[p], a.lang), lex, lex_de, pred),
                                         [p for p in sorted(set(pp)) if p in im])))
            for p in sorted(set(pp)):
                if p not in im:
                    continue
                page = Image.open(im[p]).convert("L")
                rr = read[p]
                if len(rr) > a.max_per_page:
                    whole.append((it, p, len(rr)))
                    with open(dn, "a", encoding="utf-8") as fh: fh.write(f"{it}\tWHOLE\t{p}\t{len(rr)}\n")
                    continue
                for run in rr:
                    x0 = min(int(w["left"]) for w in run); y0 = min(int(w["top"]) for w in run)
                    x1 = max(int(w["left"]) + int(w["width"]) for w in run); y1 = max(int(w["top"]) + int(w["height"]) for w in run)
                    m = max(6, (y1 - y0) // 3)
                    box = (max(0, x0 - m), max(0, y0 - m), min(page.width, x1 + m), min(page.height, y1 + m))
                    sid = f"s{len(key) + 1:05d}"
                    crop = page.crop(box); crop.save(os.path.join(a.out, "snippets", sid + ".png"))
                    snips.append((sid, crop))
                    key.append([sid, "", it, p, ",".join(map(str, box)), " ".join(w["text"] for w in run)])
                    with open(kp, "a", encoding="utf-8") as fh: fh.write("\t".join(map(str, key[-1])) + "\n")
            with open(dn, "a", encoding="utf-8") as fh: fh.write(f"{it}\n")
            with open(os.path.join(a.out, "PROGRESS.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"{n_it + 1} of {len(want)} items, {len(key)} snippets, {__import__('time').time() - t0:.0f} s, "
                         f"{__import__('time').strftime('%H:%M:%S')}\n")
        finally:
            shutil.rmtree(work, ignore_errors=True)
    font = ImageFont.load_default()
    nsheet = 0
    for k in range(0, len(snips), a.per_sheet):
        part = snips[k:k + a.per_sheet]; nsheet += 1
        wmax = max(c.width for _, c in part) + 90; h = sum(c.height + 8 for _, c in part) + 8
        sheet = Image.new("L", (wmax, h), 255); d = ImageDraw.Draw(sheet); y = 8
        for sid, c in part:
            d.text((4, y + c.height // 2 - 5), sid, fill=0, font=font)
            sheet.paste(c, (86, y)); d.line([(0, y + c.height + 4), (wmax, y + c.height + 4)], fill=180); y += c.height + 8
        sheet.save(os.path.join(a.out, "sheets", f"sheet-{nsheet:03d}.png"))
        for r in key[k:k + a.per_sheet]:
            r[1] = f"sheet-{nsheet:03d}"
    with open(os.path.join(a.out, "KEY.tsv"), "x", encoding="utf-8") as fh:
        fh.write("id\tsheet\titem\tpage\tbox\ttesseract\n"); fh.writelines("\t".join(map(str, r)) + "\n" for r in key)
    with open(os.path.join(a.out, "WHOLE-PAGES.tsv"), "x", encoding="utf-8") as fh:
        fh.write("item\tpage\tsnippets\n"); fh.writelines(f"{i}\t{p}\t{n}\n" for i, p, n in whole)
    npages = sum(len(set(v)) for v in want.values())
    print(f"{npages} pages · {len(key)} snippets ({len(key) / max(npages - len(whole), 1):.1f} a page cut) · {nsheet} sheets · "
          f"{len(whole)} pages over {a.max_per_page} snippets, for a page read → {a.out}")


def split(a):
    """A sheet the Read tool shrinks more than --max-scale times (its long side to 2000 px) loses its printed ids: a
    reader of sheet-196 of round 1's rest (4275 × 8870) could not pair lines with ids, and one of sheet-195 assigned
    them in order (2026-10-25 17:4x). Its snippets are packed again into PIECES `sheets/sheet-NNN-pK.png` of at most
    2000 px a side, a snippet wider than 1900 px scaled down to it (the reader sees it no smaller than in the whole
    sheet), the ids at full size. A piece is read as a sheet (`returns/sheet-NNN-pK.txt`; `file` reads every return
    by id). Writes the pieces and `SPLIT.tsv` (sheet, scale, pieces); a sheet already split is left."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(); rows = {}
    for l in open(os.path.join(a.dir, "KEY.tsv"), encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if f[0].startswith("s") and f[0][1:].isdigit(): rows.setdefault(f[1], []).append(f[0])
    sf = os.path.join(a.dir, "SPLIT.tsv"); done = set()
    if os.path.exists(sf): done = {l.split("\t")[0] for l in open(sf, encoding="utf-8")}
    out = []
    for s in sorted(rows):
        w, h = Image.open(os.path.join(a.dir, "sheets", s + ".png")).size
        k = max(w, h) / 2000
        if k <= a.max_scale or s in done: continue
        snips = []
        for sid in rows[s]:
            c = Image.open(os.path.join(a.dir, "snippets", sid + ".png")).convert("L")
            if c.width > 1900: c = c.resize((1900, max(1, round(c.height * 1900 / c.width))))
            snips.append((sid, c))
        pieces, cur, ch = [], [], 8
        for sid, c in snips:
            if cur and ch + c.height + 8 > 2000: pieces.append(cur); cur, ch = [], 8
            cur.append((sid, c)); ch += c.height + 8
        pieces.append(cur)
        for n, part in enumerate(pieces, 1):
            wmax = max(c.width for _, c in part) + 90; hh = sum(c.height + 8 for _, c in part) + 8
            sheet = Image.new("L", (wmax, hh), 255); d = ImageDraw.Draw(sheet); y = 8
            for sid, c in part:
                d.text((4, y + c.height // 2 - 5), sid, fill=0, font=font)
                sheet.paste(c, (86, y)); d.line([(0, y + c.height + 4), (wmax, y + c.height + 4)], fill=180); y += c.height + 8
            sheet.save(os.path.join(a.dir, "sheets", f"{s}-p{n}.png"))
        out.append(f"{s}\t{k:.2f}\t{len(pieces)}\n"); print(f"{s} ({w} × {h}, {k:.2f}×) → {len(pieces)} pieces")
    with open(sf, "a", encoding="utf-8") as fh: fh.writelines(out)


def file_returns(a):
    key = {}
    for l in open(os.path.join(a.dir, "KEY.tsv"), encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if f[0].startswith("s") and f[0][1:].isdigit():
            key[f[0]] = (f[2], int(f[3]))
    got = {}
    for r in sorted(glob.glob(os.path.join(a.dir, "returns", "sheet-*.txt"))):
        for l in open(r, encoding="utf-8"):
            m = re.match(r"^(s\d{5})\s+(.*\S)\s*$", l)
            if m and m.group(1) in key and m.group(2) != "NOT SEEN":
                got[m.group(1)] = m.group(2)
    per = {}
    for sid in sorted(got):
        per.setdefault(key[sid], []).append(got[sid])
    wrote = skipped = 0
    for (it, p), lines in sorted(per.items()):
        f = os.path.join(a.root, it, f"page-{p:04d}.names.txt")
        if os.path.exists(f):
            skipped += 1; continue
        with open(f, "x", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        wrote += 1
    tf = os.path.join(a.dir, "TIER.txt"); ff = os.path.join(a.dir, "FILED.tsv")
    if os.path.exists(tf) and not (os.path.exists(ff) and any(l.startswith("tier\t") for l in open(ff, encoding="utf-8"))):
        with open(ff, "a", encoding="utf-8") as fh:   # the level the register (tools/ocr-vision-register.py) reads
            fh.write("tier\t" + open(tf, encoding="utf-8").read().strip() + "\n")
    with open(os.path.join(a.dir, "FILED.tsv"), "a", encoding="utf-8") as fh:
        fh.write(f"{len(got)} snippets read of {len(key)}\t{wrote} pages written\t{skipped} pages already had a .names.txt\n")
    print(f"{len(got)} snippets read of {len(key)} · {wrote} pages written · {skipped} skipped (a .names.txt exists)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("build", "split", "file"))
    ap.add_argument("--max-scale", type=float, default=3.0, help="split: sheets shrunk more than this for a reader are split")
    ap.add_argument("--pdfs"); ap.add_argument("--pages"); ap.add_argument("--pages-file"); ap.add_argument("--pages-cols", default="1,2")
    ap.add_argument("--items", help="build with --pages-file: only items matching this regex")
    ap.add_argument("--german", action="store_true", help="build: German compounds are no candidates (unless after an initial or title)")
    ap.add_argument("--skip-done", help="build: a search root; pages with a page-NNNN.names.txt there are not cut again")
    ap.add_argument("--out"); ap.add_argument("--per-sheet", type=int, default=40); ap.add_argument("--max-per-page", type=int, default=40)
    ap.add_argument("--lang", default="epo"); ap.add_argument("--dir"); ap.add_argument("--root")
    ap.add_argument("--resume", action="store_true", help="build: continue a run (KEY-PARTIAL.tsv, DONE.tsv)")
    ap.add_argument("--jobs", type=int, default=2, help="build: pages read at once (tools/cupel_workers.py shared|solo)")
    ap.add_argument("--tier", type=int, help="build: cut only the words of this small-capital tier (tools/smallcaps-signals.py TIERS)")
    ap.add_argument("--tier-note", help="build with --tier: the signed step, e.g. «1, pages with 3+ words, 2026-10-25»")
    ap.add_argument("--roster", help="build with --tier: the roster file (default the newest ROSTER-FULL-CROSS-ARC)")
    a = ap.parse_args()
    if a.mode == "build":
        if not (a.pdfs and a.out and (a.pages or a.pages_file)):
            sys.exit("build needs --pdfs, --out and --pages or --pages-file")
        build(a)
    elif a.mode == "split":
        if not a.dir: sys.exit("split needs --dir")
        split(a)
    else:
        if not (a.dir and a.root):
            sys.exit("file needs --dir and --root")
        file_returns(a)
