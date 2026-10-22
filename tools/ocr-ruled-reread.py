#!/usr/bin/env python3
r"""ocr-ruled-reread — re-read single pages the editor has RULED on (G1 review), as the ruling says.

    tools/ocr-ruled-reread.py RULINGS.tsv [--root sources/ocr-rendersearch] [--dry-run]

RULINGS.tsv, one page per line, tab-separated:
    corpus   page   pdf   lang   [rotate=<deg clockwise>] [crop=<x0>,<y0>,<x1>,<y1> as fractions of the page] [only]

The G1 review (2026-09-26) put every page whose text had gone missing in front of the editor. Where
the ruling was «re-ocr», the ordinary pipeline had already read that page and failed, so this tool
does NOT repeat the ordinary recipe. It:

  1. renders the page at 400 ppi, so a page with no picture in it is not read at a picture's resolution;
  2. applies what the ruling says: a crop to the part of the page to be read (fractions of the
     page AS SCANNED, applied first), then a rotation. Measure the angle rather than trusting an
     estimate by eye: kongresa.libro.08 p.93 was ruled «45°», measured 58.5°, and read only at 58.5°;
  3. reads it four ways — psm 6 (one block), psm 4 (columns), psm 3 (automatic layout) and
     psm 11 (scattered text: captions, balloons, address panels) — with the page's languages;
  4. keeps the reading with the most recognised words (the word lists in tools/lexicons/).

The kept reading is written as `page-NNNN.ruled.txt`, with `page-NNNN.ruled.json` beside it
recording every candidate and its count. `ocr-rebuild-combined.py` ranks a ruled reading above
every OCR reading and merge, and below the editor's hand-keyed text (`.hand.txt`).
A ruled reading is still a machine reading: it is looked at before the ruling is marked done.
"""
import os, re, sys, json, argparse, subprocess, tempfile, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
LEX_FOR = {"epo": ["esperanto", "ido", "occidental"], "ita": ["italian"], "dan": ["danish"],
           "deu": ["german"], "fra": ["french"], "eng": []}
PSMS = ("6", "4", "3", "11")
PPI = 400


def lexicon(langs):
    words = set()
    for l in langs:
        for n in LEX_FOR.get(l, []):
            p = os.path.join(HERE, "lexicons", n + ".txt")
            if os.path.exists(p):
                words.update(w.strip().lower() for w in open(p, encoding="utf-8", errors="ignore"))
    return words


def recognised(text, lex):
    return sum(1 for m in WORD.finditer(text) if m.group(0).lower() in lex)


def image(pdf, page, work, rotate, crop):
    base = os.path.join(work, f"p{page:05d}")
    subprocess.run(["pdftoppm", "-r", str(PPI), "-png", "-f", str(page), "-l", str(page), pdf, base],
                   capture_output=True, check=True)
    src = glob.glob(base + "*.png")[0]
    im = Image.open(src).convert("L")
    if crop:
        # crop FIRST: the box is measured on the page as scanned, before any rotation
        w, h = im.size
        x0, y0, x1, y1 = crop
        im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    if rotate:
        # PIL turns counter-clockwise; the ruling says clockwise
        im = im.rotate(-rotate, expand=True, fillcolor=255, resample=Image.BICUBIC)
    out = base + ".ready.png"
    im.save(out, dpi=(PPI, PPI))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rulings")
    ap.add_argument("--root", default=os.path.join(HERE, "..", "published", "heterophony-resources",
                                                   "geniza", "sources", "ocr-rendersearch"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for row in open(a.rulings, encoding="utf-8"):
        if not row.strip() or row.startswith("#"):
            continue
        f = row.rstrip("\n").split("\t")
        corpus, page, pdf, lang = f[0], int(f[1]), f[2], f[3]
        opts = dict(o.split("=", 1) for o in f[4:] if "=" in o)
        rotate = float(opts.get("rotate", 0))
        crop = [float(x) for x in opts["crop"].split(",")] if "crop" in opts else None
        lex = lexicon(lang.split("+"))
        with tempfile.TemporaryDirectory() as work:
            img = image(pdf, page, work, rotate, crop)
            cands = {}
            for psm in PSMS:
                # errors="replace" (2026-10-13, approved by the editor; docs/FAILURE-MAP.md R28): tesseract's stderr once held
                # a byte not UTF-8, and decoding it crashed the run before anything was written
                r = subprocess.run(["tesseract", img, "-", "-l", lang, "--psm", psm],
                                   capture_output=True, text=True, errors="replace")
                cands[psm] = r.stdout
        score = {p: recognised(t, lex) for p, t in cands.items()}
        best = max(PSMS, key=lambda p: (score[p], p == "6"))
        d = os.path.join(a.root, corpus)
        old = os.path.join(d, f"page-{page:04d}.txt")
        was = recognised(open(old, encoding="utf-8", errors="ignore").read(), lex) if os.path.exists(old) else None
        print(f"{corpus} p.{page}: psm6 was {was} · " +
              " · ".join(f"psm{p} {score[p]}" for p in PSMS) + f"  → psm {best}")
        if not a.dry_run:
            open(os.path.join(d, f"page-{page:04d}.ruled.txt"), "w", encoding="utf-8").write(cands[best])
            json.dump({"pdf": pdf, "page": page, "lang": lang, "ppi": PPI, "rotate": rotate,
                       "crop": crop, "chosen_psm": best, "recognised": score,
                       "recognised_before": was}, open(os.path.join(d, f"page-{page:04d}.ruled.json"),
                                                       "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
