#!/usr/bin/env python3
r"""ocr-number-crops — the printed page number of each page, cropped from its corner and packed into sheets, for vision.

    python3 tools/ocr-number-crops.py build --pages <item⇥PDF page tsv> --pdfs <full list> --out <new dir>
                                            [--corners <prefix>=tl,tr,br …] [--jobs 6] [--per-sheet 32]
    python3 tools/ocr-number-crops.py judge --out <dir>          # after the readers: returns/sheet-NNN.txt

WHY (2026-10-27, cupel19a C6.4.1; the editor, on the 912 pages whose numbers the OCR could not follow). The strip look (tools/ocr-page-number-look.py) sends one image a page,
the head and foot of the page stacked, so 912 pages need about 61 readers under the image caps (15 images each). The
editor's look at the runs gave where they print their numbers: *Dia Regno* 1909–12 and *German-Aŭstria Esperantisto*
1911–14 at the top, in the outer corners, alternately left and right; *Internacia Bulteno* bottom right in 1914–16, at
the top in 1918 (top right, beside the issue number); *Dia Regno* 1908 and the 1910 ANNO issues of *Austria
Esperantisto* none at all (those pages are not for this tool: their check is the mastheads' issue numbers and the page
counts). Miles's look at *Dia Regno* 1910 then found its numbers at the top CENTRE («— 34 —»). So each page here
gives only the places where its run prints its number (--corners: tl, tr, tc, bl, br, bc); one with no ink is dropped;
the rest are packed, with an id beside each, about 32 to a sheet: 814 pages in about 40 sheets, 3 readers.

BUILD. For each page of --pages: the image the conversion read (tools/ocr_page_images.py), the paper found inside the
scan's border (tools/ocr-gutter-cut.py's page_box), then the corners --corners names for the item's prefix (default
tl,tr): tl and tr the top 12% of the paper by its outer 24%, tc the top 12% by its middle 30%, bl and br the bottom 12%
by its outer 24%, bc the bottom 12% by its middle 30% (2026-10-30, cupel19c: *Kroata Esperantisto* prints «— 65 —»). Ink: the share of
pixels darker than the paper's median by more than half the way to its darkest 1%; a corner under --min-ink (0.004)
is empty and dropped. Each kept corner is scaled to 120 px high and put on a sheet, its id (cNNNNN) printed beside
it; a sheet stays under 2000 px a side (the Read tool shrinks a larger one and its ids are lost: 2026-10-25 17:4x).
WRITES, under --out (refused if it exists): crops/cNNNNN.png, sheets/sheet-NNN.png, KEY.tsv (id, sheet, item, PDF
page, corner, ink), EMPTY.tsv (the pages with no corner kept), BRIEF.md (the readers' brief), TASK-NNN.md (one per
reader, at most 15 sheets each).

JUDGE. Reads returns/sheet-NNN.txt (lines «cNNNNN<TAB>number», «cNNNNN<TAB>—» for no number, «cNNNNN<TAB>NOT SEEN»),
takes each page's number (a corner that read a number; two that disagree are listed), and per item lists every step
from one numbered page to the next that is not +1 per PDF page: JUMP (pages missing between), STEP DOWN, REPEAT, with
the PDF pages and the numbers read. WRITES <out>/JUDGE.md and <out>/PAGES.tsv (item, PDF page, number or blank).
"""
import argparse, collections, concurrent.futures, csv, glob, importlib.util, os, re, shutil, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ocr_page_images as PI
_s = importlib.util.spec_from_file_location("gutter", os.path.join(HERE, "ocr-gutter-cut.py"))
GC = importlib.util.module_from_spec(_s); _argv = sys.argv; sys.argv = [_argv[0]]; _s.loader.exec_module(GC); sys.argv = _argv
Image.MAX_IMAGE_PIXELS = None
DEPTH, WIDTH, H = 0.12, 0.24, 120


def corners_for(item, spec):
    hit = max((p for p in spec if item.startswith(p)), key=len, default=None)
    return spec[hit] if hit else ["tl", "tr"]


def ink_share(g):
    """The share of ink pixels, not counting columns or rows that are mostly dark (the binding's shadow, the scan's
    border: *Dia Regno*'s first test crops were all shadow, 2026-10-27)."""
    if g.size == 0: return 0.0   # a corner of no pixels: the paper box found degenerate (cupel19b, 2026-10-29)
    med = float(np.median(g)); dark = float(np.percentile(g, 1))
    if med - dark < 25: return 0.0
    ink = g < med - 0.5 * (med - dark)
    keep_c = ink.mean(axis=0) < 0.5; keep_r = ink.mean(axis=1) < 0.5
    sub = ink[np.ix_(keep_r, keep_c)]
    return float(sub.mean()) if sub.size else 0.0


def crop_page(job):
    item, pdf, n, corners, min_ink = job
    work = tempfile.mkdtemp(prefix="numcrop-")
    try:
        p = PI.page_images(pdf, work, jobs=1, pages=[n]).get(n)
        if not p or not os.path.exists(p): return item, n, []
        img = Image.open(p).convert("L"); g = np.asarray(img)
        x0, x1, y0, y1 = GC.page_box(g); W, Hh = x1 - x0, y1 - y0
        box = {"tc": (x0 + int(0.35 * W), y0, x1 - int(0.35 * W), y0 + int(DEPTH * Hh)),
               "bc": (x0 + int(0.35 * W), y1 - int(DEPTH * Hh), x1 - int(0.35 * W), y1),
               "bl": (x0, y1 - int(DEPTH * Hh), x0 + int(WIDTH * W), y1),
               "tl": (x0, y0, x0 + int(WIDTH * W), y0 + int(DEPTH * Hh)),
               "tr": (x1 - int(WIDTH * W), y0, x1, y0 + int(DEPTH * Hh)),
               "br": (x1 - int(WIDTH * W), y1 - int(DEPTH * Hh), x1, y1)}
        out = []
        for c in corners:
            cr = img.crop(box[c]); share = ink_share(np.asarray(cr))
            if share >= min_ink:
                out.append((c, round(share, 4), cr.resize((max(1, int(cr.width * H / cr.height)), H))))
        return item, n, out
    finally:
        shutil.rmtree(work, ignore_errors=True)


BRIEF = """# Reading printed page numbers from corner crops

USE ONLY THE Read AND Write TOOLS. Do not run shell commands and do not list directories.

Each sheet holds small crops cut from the corners of scanned pages of Esperanto periodicals (1908–1918). Beside each
crop is its id, cNNNNN. A crop may show a printed page number (Arabic figures, sometimes with a running head, a date or
an issue number beside it), or no page number at all.

Read each sheet image ONCE. Never read an image a second time. If a sheet does not display, write NOT SEEN for every id
on it and go on.

For every id on the sheet, write one line: the id, a tab, and the PAGE NUMBER exactly as printed (figures only, e.g.
«117»). If the crop shows no page number, write «—». If a figure is unclear, write your reading with «?» after it
(«11?»). Never guess a number from the order of the crops: read each crop alone. An issue number («N-ro 5», «No. 12»),
a year or a price is NOT a page number: write «—» for it unless a page number is also shown.

Write your return to the file the task names, all the sheets' lines in order, rewriting the whole file after every
five sheets and once at the end. Your final message: one line, «written: <path>, N ids».
"""


def build(a):
    if os.path.exists(a.out): sys.exit(f"exists: {a.out}")
    spec = {}
    for s in a.corners or []:
        k, _, v = s.partition("="); spec[k] = v.split(",")
    full = {os.path.basename(l.strip())[:-4]: l.strip() for l in open(a.pdfs, encoding="utf-8") if l.strip()}
    if a.from_seq:   # (2026-10-29, cupel19b, box-free C6.4.1) the pages straight from the page-sequence scan: every page
        pages = []   # of a CANT-TELL item, the «unverified_pdf_pages» of a PARTLY-VERIFIED one
        for r in csv.DictReader(open(a.from_seq, encoding="utf-8"), delimiter="\t"):
            if r["verdict"] == "CANT-TELL":
                pages += [[r["corpus"], str(p)] for p in range(1, int(r["scan_pages"]) + 1)]
            elif r["verdict"] == "PARTLY-VERIFIED":
                uv = (r.get("unverified_pdf_pages") or "").split("(")[0].replace("PDF pages", "").replace("PDF page", "")
                for part in filter(None, (x.strip() for x in uv.split(","))):   # (2026-10-30, cupel19c: named
                    # «spec», it overwrote --corners: every item fell back to tl,tr, or a digit-led one crashed)
                    lo, _, hi = part.replace("–", "-").partition("-")
                    pages += [[r["corpus"], str(p)] for p in range(int(lo), int(hi or lo) + 1)]
    else:
        pages = [l.rstrip("\n").split("\t")[:2] for l in open(a.pages, encoding="utf-8") if l.strip()]
    jobs = [(it, full[it], int(n), corners_for(it, spec), a.min_ink) for it, n in pages]
    os.makedirs(os.path.join(a.out, "crops")); os.makedirs(os.path.join(a.out, "sheets")); os.makedirs(os.path.join(a.out, "returns"))
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(crop_page, jobs))
    key, empty, crops = [], [], []
    for item, n, out in res:
        if not out: empty.append((item, n)); continue
        for c, share, im in out:
            cid = f"c{len(crops) + 1:05d}"; im.save(os.path.join(a.out, "crops", cid + ".png"))
            crops.append((cid, im)); key.append([cid, "", item, n, c, share])
    font = ImageFont.load_default()
    cols, cw, lab = 4, 420, 70
    nsheet = 0
    for k in range(0, len(crops), a.per_sheet):
        part = crops[k:k + a.per_sheet]; nsheet += 1
        rows = (len(part) + cols - 1) // cols
        sheet = Image.new("L", (cols * (lab + cw), rows * (H + 16) + 8), 255); d = ImageDraw.Draw(sheet)
        for i, (cid, im) in enumerate(part):
            x, y = (i % cols) * (lab + cw), 8 + (i // cols) * (H + 16)
            d.text((x + 4, y + H // 2 - 6), cid, fill=0, font=font)
            sheet.paste(im.crop((0, 0, min(im.width, cw - 8), H)), (x + lab, y))
            d.rectangle([x + lab - 2, y - 2, x + lab + min(im.width, cw - 8) + 1, y + H + 1], outline=150)
        assert max(sheet.size) <= 2000, sheet.size
        sheet.save(os.path.join(a.out, "sheets", f"sheet-{nsheet:03d}.png"))
        for r in key[k:k + a.per_sheet]: r[1] = f"sheet-{nsheet:03d}"
    with open(os.path.join(a.out, "KEY.tsv"), "w", encoding="utf-8") as f:
        f.write("id\tsheet\titem\tpage\tcorner\tink\n"); f.writelines("\t".join(map(str, r)) + "\n" for r in key)
    with open(os.path.join(a.out, "EMPTY.tsv"), "w", encoding="utf-8") as f:
        f.writelines(f"{i}\t{n}\n" for i, n in empty)
    open(os.path.join(a.out, "BRIEF.md"), "w", encoding="utf-8").write(BRIEF)
    sheets = [f"sheet-{i:03d}" for i in range(1, nsheet + 1)]
    for t, k in enumerate(range(0, nsheet, 15), 1):
        part = sheets[k:k + 15]
        open(os.path.join(a.out, f"TASK-{t:03d}.md"), "w", encoding="utf-8").write(
            f"# Task {t:03d}\n\n- **Brief:** `{os.path.abspath(os.path.join(a.out, 'BRIEF.md'))}`, every word.\n"
            f"- **Sheets** ({len(part)}): " + ", ".join(f"`{os.path.abspath(os.path.join(a.out, 'sheets', s + '.png'))}`" for s in part) +
            f"\n- **Return:** `{os.path.abspath(os.path.join(a.out, 'returns', f'TASK-{t:03d}.txt'))}`\n")
    print(f"{len(pages)} pages · {len(crops)} corners kept · {len(empty)} pages with none · {nsheet} sheets · "
          f"{(nsheet + 14) // 15} readers → {a.out}")


def judge(a):
    key = {}
    for l in list(open(os.path.join(a.out, "KEY.tsv"), encoding="utf-8"))[1:]:
        cid, sheet, item, n, c, _ = l.rstrip("\n").split("\t"); key[cid] = (item, int(n), c)
    read = {}
    for f in sorted(glob.glob(os.path.join(a.out, "returns", "*.txt"))):
        for l in open(f, encoding="utf-8"):
            m = re.match(r"\s*(c\d{5})\t(.*)$", l.rstrip("\n"))
            if m: read[m.group(1)] = m.group(2).strip()
    missing = [c for c in key if c not in read]
    pages, clash = collections.defaultdict(dict), []
    for cid, (item, n, c) in key.items():
        v = read.get(cid, "")
        num = re.fullmatch(r"(\d{1,4})\??", v)
        if num:
            prev = pages[item].get(n)
            if prev is not None and prev != int(num.group(1)): clash.append((item, n, prev, int(num.group(1))))
            pages[item].setdefault(n, int(num.group(1)))
    out = [f"# The page numbers read from the corners (`{a.out}`)", "",
           f"{len(key)} corners, {len(read)} read, {len(missing)} not returned; {sum(len(v) for v in pages.values())} pages with a number.", ""]
    if missing: out += ["**Not returned:** " + ", ".join(missing[:40]) + (" …" if len(missing) > 40 else ""), ""]
    if clash: out += ["**Two corners disagree:**"] + [f"- {i} PDF {n}: {x} / {y}" for i, n, x, y in clash] + [""]
    leads = []
    for item in sorted(pages):
        seq = sorted(pages[item].items())
        for (p1, v1), (p2, v2) in zip(seq, seq[1:]):
            d = (v2 - v1) - (p2 - p1)
            if d > 0: leads.append((item, "JUMP", p1, v1, p2, v2, f"{d} printed page(s) not in the scan"))
            elif v2 < v1: leads.append((item, "STEP DOWN", p1, v1, p2, v2, ""))
            elif v2 == v1: leads.append((item, "REPEAT", p1, v1, p2, v2, ""))
    out += [f"**Leads: {len(leads)}**", "", "| item | kind | PDF page | read | PDF page | read | |", "|---|---|---:|---:|---:|---:|---|"]
    out += [f"| {i} | {k} | {p1} | {v1} | {p2} | {v2} | {w} |" for i, k, p1, v1, p2, v2, w in leads]
    open(os.path.join(a.out, "JUDGE.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    with open(os.path.join(a.out, "PAGES.tsv"), "w", encoding="utf-8") as f:
        for item in sorted(pages):
            for n, v in sorted(pages[item].items()): f.write(f"{item}\t{n}\t{v}\n")
    print(f"{len(read)} of {len(key)} read · {len(leads)} leads · {len(clash)} clashes → {os.path.join(a.out, 'JUDGE.md')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=("build", "judge")); ap.add_argument("--out", required=True)
    ap.add_argument("--pages"); ap.add_argument("--pdfs"); ap.add_argument("--corners", nargs="*")
    ap.add_argument("--from-seq", help="build: the pages from a page-sequence scan (CANT-TELL whole, PARTLY-VERIFIED's unverified pages), in place of --pages")
    ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--per-sheet", type=int, default=32)
    ap.add_argument("--min-ink", type=float, default=0.004)
    a = ap.parse_args()
    build(a) if a.mode == "build" else judge(a)


if __name__ == "__main__":
    main()
