#!/usr/bin/env python3
"""Snippets of the page image for the OCR confusions register: the printed word Tesseract misread, cut from the page,
for the Genizo site's page «Konfuzoj» (the editor, 2026-10-29, asked for snippets of some of the most prominent confusions as visual examples).

Each request names an item, a PDF page, the word as Tesseract wrote it and as printed. The page image is the one the
conversion read (tools/ocr_page_images.py, its cache); Tesseract reads it again with the conversion's settings (the
item's language, --psm 6, --oem 1) to give each word its box; the request's word is found by its OCR form, case-blind,
else the closest word to the OCR form or the printed one (similarity ≥ 0.6). The box, padded, is cut out, scaled to a
common height, and written as PNG.

    tools/ocr-confusion-snippets.py --requests <in.tsv> --out-dir <dir> --report <new.tsv> --work <dir>

REQUESTS (tab-separated, a header line): name · item · page · ocr · printed [· lang, default epo] [· nth, default 1].
Writes <out-dir>/konfuzo-<name>.png for each and the report (name, item, page, the word found, how, its box, the file);
refuses an existing image or report. The page images stay local (copyright scans); only the cut words are written.
"""
import argparse, csv, difflib, os, re, subprocess, sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources")
sys.path.insert(0, HERE)
import ocr_page_images as PI

EDGE = re.compile(r"^[^\w]+|[^\w]+$")
HEIGHT = 64          # the word's box, scaled to this many pixels high
PAD = (0.6, 0.35)    # padding, as a share of the box's height: across, up and down


def find_pdf(item):
    hits = []
    for d, subs, files in os.walk(SRC):
        if d[len(SRC):].count(os.sep) >= 3:
            subs[:] = []
        if item + ".pdf" in files:
            hits.append(os.path.join(d, item + ".pdf"))
        subs[:] = [s for s in subs if not s.endswith(".noindex") and s != "ocr-rendersearch"]
    if len(hits) != 1:
        sys.exit(f"{item}: {len(hits)} PDFs found under sources/ ({hits})")
    return hits[0]


def boxes(img, lang):
    # to a file, not stdout: read from stdout the rows came back empty (2026-10-29)
    base = os.path.splitext(img)[0] + ".words"
    r = subprocess.run(["tesseract", img, base, "-l", lang, "--psm", "6", "--oem", "1", "tsv"], capture_output=True)
    if not os.path.exists(base + ".tsv"):
        sys.exit(f"tesseract wrote no words for {img}: {r.stderr.decode('utf-8', 'replace')[:300]}")
    out = []
    for row in csv.DictReader(open(base + ".tsv", encoding="utf-8", errors="replace"), delimiter="\t",
                              quoting=csv.QUOTE_NONE):
        if row.get("level") == "5" and row.get("text", "").strip():
            out.append((EDGE.sub("", row["text"]), int(row["left"]), int(row["top"]), int(row["width"]),
                        int(row["height"])))
    return out


def pick(ws, ocr, printed, nth):
    same = [w for w in ws if w[0].casefold() == ocr.casefold()]
    if len(same) >= nth:
        return same[nth - 1], "the OCR form"
    best = max(ws, key=lambda w: max(difflib.SequenceMatcher(None, w[0].casefold(), x.casefold()).ratio()
                                     for x in (ocr, printed)), default=None)
    if best and max(difflib.SequenceMatcher(None, best[0].casefold(), x.casefold()).ratio()
                    for x in (ocr, printed)) >= 0.6:
        return best, "the closest word"
    return None, f"not found ({len(ws)} words on the page)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--report", required=True)
    # a folder of one's own, kept: in a temporary folder every page came back with no words (2026-10-29, not traced)
    ap.add_argument("--work", required=True, help="the page images and word boxes, one subfolder a request")
    a = ap.parse_args()
    if os.path.exists(a.report):
        sys.exit(f"refusing: {a.report} exists")
    reqs = list(csv.DictReader(open(a.requests, encoding="utf-8"), delimiter="\t"))
    for q in reqs:
        f = os.path.join(a.out_dir, f"konfuzo-{q['name']}.png")
        if os.path.exists(f):
            sys.exit(f"refusing: {f} exists")
    rep = ["name\titem\tpage\tfound\thow\tbox\tfile"]
    for q in reqs:
        work = os.path.join(a.work, q["name"])
        os.makedirs(work, exist_ok=True)
        pdf, p = find_pdf(q["item"]), int(q["page"])
        img = PI.page_images(pdf, work, jobs=1, pages=[p]).get(p)
        if not img:
            rep.append(f"{q['name']}\t{q['item']}\t{p}\t\tno page image\t\t"); continue
        w, how = pick(boxes(img, q.get("lang") or "epo"), q["ocr"], q["printed"], int(q.get("nth") or 1))
        if not w:
            rep.append(f"{q['name']}\t{q['item']}\t{p}\t\t{how}\t\t"); continue
        text, x, y, bw, bh = w
        im = Image.open(img)
        px, py = int(PAD[0] * bh), int(PAD[1] * bh)
        box = (max(0, x - px), max(0, y - py), min(im.width, x + bw + px), min(im.height, y + bh + py))
        cut = im.crop(box).convert("L")
        s = HEIGHT / bh
        cut = cut.resize((max(1, round(cut.width * s)), max(1, round(cut.height * s))), Image.LANCZOS)
        out = os.path.join(a.out_dir, f"konfuzo-{q['name']}.png")
        cut.save(out + ".partial.png"); os.rename(out + ".partial.png", out)
        rep.append(f"{q['name']}\t{q['item']}\t{p}\t{text}\t{how}\t{box}\t{os.path.basename(out)}")
    with open(a.report + ".partial", "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")
    os.rename(a.report + ".partial", a.report)
    print(f"{len(reqs)} requests → {a.report}")


if __name__ == "__main__":
    main()
