#!/usr/bin/env python3
r"""ocr-page-map-check — a blind check of the page map: strips of sampled pages for vision readers, and their score.

    tools/ocr-page-map-check.py build --old <the map as it was> --out <new dir> [--per-class 15] [--seed 2510]
    tools/ocr-page-map-check.py score --dir <that dir>

WHY (the editor 2026-10-25 11:3x, after the map was rebuilt over the corpus,
10:50, with 33,083 rows it never had; Ezri cites printed pages from it). The checks of 2026-10-08 (2, 2b, 2c:
`geniza/sources/ocr-work/page-map-check-2026-10-08*/`, `ocr/OCR-BOARD.md` 2026-10-08 15:1x) were cut by hand; this is
the same check as a tool: per page, its top and bottom bands (where page numbers stand), one image a page, so the
reader sees the number and not the page, and no map value is shown.
build  Samples the rows of `geniza/ocr/runs/OCR-PAGE-MAP.tsv` whose item is NOT in --old (the new rows only), by the
       map's `source`: --per-class each of «read», «iss», «vol» (fewer where there are fewer), one page an item, at
       random (--seed). Each page from the image the conversion read (`tools/ocr_page_images.py`, its cache): the top
       and bottom 15% cut, scaled to 1,000 px wide, stacked with a white bar between. One batch a class
       (`b01` read, `b02` iss, `b03` vol), `NNN.png`; KEY.tsv (batch, image, item, pdf_page, map_printed, class).
       At most 15 images a batch: the image-reader caps (run sheet, «Image readers: hard caps»).
score  Each batch's return `bNN.return.txt` (the 2026-10-08 form: «| NNN | printed page number (or NONE) | SURE or
       UNSURE | note |») against KEY.tsv: agree, DISAGREE (SURE / UNSURE), none-seen; per class and the cases.
       SCORE.txt in the dir.
WRITE-SET: build: --out (a new folder; refused if it exists); page renders in a temporary folder removed after (the
page-image cache may grow, as for every OCR tool). score: <dir>/SCORE.txt (rewritten).
"""
import argparse, collections, csv, os, random, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
MAP = os.path.join(G, "ocr", "runs", "OCR-PAGE-MAP.tsv")


def rows(f):
    return [x for x in (l.rstrip("\n").split("\t") for l in open(f, encoding="utf-8")) if len(x) >= 5 and x[1].isdigit()]


def build(a):
    from ocr_page_images import page_images
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    if os.path.exists(a.out): sys.exit(f"refusing: {a.out} exists")
    old = {x[0] for x in rows(a.old)}
    new = [x for x in rows(MAP) if x[0] not in old]
    pdfs = {}
    lst = sorted(f for f in os.listdir(os.path.join(G, "sources")) if re.fullmatch(r"OCR-PDF-LIST-.*\.txt", f) and "NEW" not in f)
    for f in lst:   # every list, the newest last: an item's path as the newest list gives it
        for l in open(os.path.join(G, "sources", f), encoding="utf-8"):
            p = l.strip()
            if p: pdfs[os.path.splitext(os.path.basename(p))[0]] = p if p.startswith("/") else os.path.join(HERE, "..", p)
    rnd = random.Random(a.seed); key = []
    for b, cls in (("b01", "read"), ("b02", "iss"), ("b03", "vol")):
        cand = [x for x in new if x[3] == cls and x[0] in pdfs]; rnd.shuffle(cand)
        seen, pick = set(), []
        for x in cand:
            if x[0] in seen: continue
            seen.add(x[0]); pick.append(x)
            if len(pick) >= min(a.per_class, 15): break
        os.makedirs(os.path.join(a.out, b))
        for k, x in enumerate(pick, 1):
            work = os.path.realpath(tempfile.mkdtemp(prefix="pmc-"))
            try:
                im = page_images(pdfs[x[0]], work, jobs=1, pages=[int(x[1])])
                if int(x[1]) not in im: continue
                pg = Image.open(im[int(x[1])]).convert("L"); w, h = pg.size; band = int(h * 0.15)
                top, bot = pg.crop((0, 0, w, band)), pg.crop((0, h - band, w, h))
                sc = 1000 / w; top = top.resize((1000, max(1, int(band * sc)))); bot = bot.resize((1000, max(1, int(band * sc))))
                out = Image.new("L", (1000, top.height + bot.height + 12), 255)
                out.paste(top, (0, 0)); out.paste(bot, (0, top.height + 12))
                out.save(os.path.join(a.out, b, f"{k:03d}.png"))
                key.append((b, f"{k:03d}", x[0], x[1], x[2], cls))
            finally:
                shutil.rmtree(work, ignore_errors=True)
    with open(os.path.join(a.out, "KEY.tsv"), "x", encoding="utf-8") as w:
        w.write("batch\timage\titem\tpdf_page\tmap_printed\tclass\n"); w.writelines("\t".join(r) + "\n" for r in key)
    c = collections.Counter(r[0] for r in key)
    print(f"{len(new):,} new rows; {dict(c)} images → {a.out}")


def score(a):
    key = {(r["batch"], r["image"]): r for r in csv.DictReader(open(os.path.join(a.dir, "KEY.tsv"), encoding="utf-8"), delimiter="\t")}
    out = []
    for b in sorted({k[0] for k in key}):
        rf = os.path.join(a.dir, f"{b}.return.txt")
        if not os.path.exists(rf): out.append(f"{b}: no return"); continue
        got = {}
        for l in open(rf, encoding="utf-8"):
            m = re.match(r"\|\s*(\d{3})\s*\|\s*([^|]*?)\s*\|\s*(SURE|UNSURE)\s*\|\s*(.*?)\s*\|?\s*$", l)
            if m: got[m.group(1)] = (m.group(2), m.group(3), m.group(4))
        c = collections.Counter(); cases = []; cls = ""
        for (bb, img), r in sorted(key.items()):
            if bb != b: continue
            cls = r["class"]
            if img not in got: c["not returned"] += 1; continue
            seen, sure, note = got[img]
            if seen.upper().startswith("NONE"): c["none-seen"] += 1; continue
            if re.sub(r"\D", "", seen) == r["map_printed"]: c["agree"] += 1; continue
            c[f"DISAGREE {sure}"] += 1
            cases.append(f"  {b}/{img} {r['item']} PDF p.{r['pdf_page']}: map {r['map_printed']} vs seen {seen} ({sure}) {note}")
        out.append(f"{b} {cls} {dict(c)}"); out += cases; out.append("")
    open(os.path.join(a.dir, "SCORE.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("\n".join(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("build", "score")); ap.add_argument("--old"); ap.add_argument("--out"); ap.add_argument("--dir")
    ap.add_argument("--per-class", type=int, default=15); ap.add_argument("--seed", type=int, default=2510)
    a = ap.parse_args()
    if a.mode == "build":
        if not (a.old and a.out): sys.exit("build needs --old and --out")
        build(a)
    else:
        if not a.dir: sys.exit("score needs --dir")
        score(a)


if __name__ == "__main__":
    main()
