#!/usr/bin/env python3
r"""ocr-mask-kathye — FOUR-SCRIPT SEGREGATION: blank out the Georgian and Armenian blocks, then read and filter
the rest as Esperanto and as Russian.

    tools/ocr-mask-kathye.py <root> --pdfs <list> --items =a,b,c [--jobs 6]

WHY (four-script segregation approved by the editor 2026-09-28 17:30, on *Kaukaza Esperantisto* 1910.1 and 1910.4). Those pages print
Georgian, Armenian, Russian and Esperanto. The Russian model turns the Georgian and Armenian into Cyrillic junk that
the garbage filter does not know (its junk model is Esperanto read as Russian), and the Esperanto model turns them
into Latin junk — so both the Russian-only score and the Esperanto-only G4 were measured partly on junk, and so were not valid.
HOW, per page with Georgian or Armenian blocks (`page-NNNN.kathye.json` from `tools/ocr-kat-hye.py`):
1. the SAME block boxes are rebuilt (psm 3 on the same page image, the same gutter split — deterministic);
2. the blocks it classed Georgian or Armenian are filled white;
3. the masked image is read at psm 6 with `epo+eng` and with the Russian model the OLD-LETTER RULE picks for the
   page (`tools/ocr_russian_reading.py`: `orus` on pre-reform print, else `rus`) → `page-NNNN.masked.eo.txt`,
   `page-NNNN.masked.ru.txt`;
4. both are cleaned exactly as `ocr-garbage-filter.py apply` cleans a bi-script page → `eo-gate`, `eo-clean`,
   `ru-clean` REPLACED; the previous ones kept as `page-NNNN.<name>.pre4s.txt`.
The Georgian and Armenian stay presence only (their own readings, `ocr-rendersearch-kat/-hye/`, untouched). The
combined Esperanto text (the citation text) is not touched.
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, importlib.util
import concurrent.futures as fut
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images
import ocr_russian_reading as RR


def _mod(name, file):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


LM = _mod("lm", "ocr-layout-mixed.py")
GF = _mod("gf", "ocr-garbage-filter.py")
MDIR = None


def boxes_of(img, im):
    W, H = im.size; ink = np.asarray(im.convert("L")) < 128
    boxes, nl = {}, {}
    for row in LM.ocr(img, "epo+eng", 3).splitlines()[1:]:
        f = row.split("\t")
        if len(f) == 12 and f[0] == "5" and f[11].strip():
            b = int(f[2]); l, t, w, h = map(int, f[6:10])
            x = boxes.setdefault(b, [l, t, l + w, t + h])
            x[0], x[1], x[2], x[3] = min(x[0], l), min(x[1], t), max(x[2], l + w), max(x[3], t + h)
            nl.setdefault(b, set()).add((f[3], f[4]))
    parts = {}
    for b, bx in boxes.items():
        g = LM.gutter(ink, bx, W, H) if len(nl[b]) >= 5 else None
        if g:
            parts[(b, 0)] = [bx[0], bx[1], g, bx[3]]; parts[(b, 1)] = [g, bx[1], bx[2], bx[3]]
        else:
            parts[(b, 0)] = bx
    return parts


def do_page(job):
    d, pdf, n, mdir = job
    kj = json.load(open(os.path.join(d, f"page-{n:04d}.kathye.json"), encoding="utf-8"))
    kh = {tuple(b["block"]) for b in kj.get("blocks", []) if b.get("script") in ("kat", "hye")}
    rec = {"page": n, "kathye_blocks": len(kh)}
    work = tempfile.mkdtemp(prefix="ocrmask-")
    try:
        img = page_images(pdf, work, jobs=1, pages=[n]).get(n)
        if not img:
            rec["skipped"] = "no image"; return d, rec
        im = Image.open(img)
        if im.mode not in ("1", "L", "RGB"):
            im = im.convert("RGB")
        parts = boxes_of(img, im)
        found = [k for k in kh if k in parts]
        rec["masked"] = len(found)
        if len(found) != len(kh):
            rec["unmatched"] = len(kh) - len(found)   # the rebuilt layout did not reproduce every block
        m = im.convert("RGB"); dr = ImageDraw.Draw(m)
        for k in found:
            l, t, r, b = parts[k]; dr.rectangle([l - 4, t - 4, r + 4, b + 4], fill=(255, 255, 255))
        mp = os.path.join(work, "masked.png"); m.save(mp)
        rp = RR.russian_reading_path(os.path.join(d, f"page-{n:04d}.txt")) or ""
        ru_lang = "orus" if rp.endswith(".orus.txt") else "rus"
        eo = subprocess.run(["tesseract", mp, "-", "-l", "epo+eng", "--psm", "6"], capture_output=True, text=True).stdout
        ru = subprocess.run(["tesseract", mp, "-", "-l", ru_lang, "--psm", "6"], capture_output=True, text=True).stdout
        open(os.path.join(d, f"page-{n:04d}.masked.eo.txt"), "w", encoding="utf-8").write(eo)
        open(os.path.join(d, f"page-{n:04d}.masked.ru.txt"), "w", encoding="utf-8").write(ru)
        M = {k: GF.Model.load(json.load(open(os.path.join(mdir, k + ".json")))) for k in ("ru", "jcyr", "eo", "jlat")}
        out = {"eo-clean": GF.clean(eo, M["eo"], M["jlat"], 0.0, protect=GF.protected_latin)[0],
               "eo-gate": GF.clean(eo, M["eo"], M["jlat"], 0.0, protect=GF.protected_latin, strict=True)[0],
               "ru-clean": GF.clean(ru, GF.Folded(M["ru"]), GF.Folded(M["jcyr"]), 0.0)[0]}
        for name, text in out.items():
            p = os.path.join(d, f"page-{n:04d}.{name}.txt")
            if os.path.exists(p):
                shutil.copy(p, os.path.join(d, f"page-{n:04d}.{name}.pre4s.txt"))
            open(p, "w", encoding="utf-8").write(text)
        rec.update(ru_model=ru_lang, eo_words=len(eo.split()), ru_words=len(ru.split()))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return d, rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--pdfs", required=True); ap.add_argument("--items", required=True)
    ap.add_argument("--models", default=None, help="garbage-filter model dir (eo, jlat, ru, jcyr)")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    items = set(a.items.lstrip("=").split(","))
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    jobs = []
    for it in sorted(items):
        for kj in sorted(glob.glob(os.path.join(a.root, it, "page-*.kathye.json"))):
            j = json.load(open(kj, encoding="utf-8"))
            if any(b.get("script") in ("kat", "hye") for b in j.get("blocks", [])):
                jobs.append((os.path.join(a.root, it), pdfs[it], j["page"], a.models))
    print(f"{len(jobs)} pages with Georgian/Armenian blocks in {len(items)} items", flush=True)
    recs = {}
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for d, rec in ex.map(do_page, jobs):
            recs.setdefault(d, []).append(rec)
    for d, rr in recs.items():
        json.dump({"tool": "ocr-mask-kathye.py", "pages": sorted(rr, key=lambda r: r["page"])},
                  open(os.path.join(d, "MASK-KATHYE.json"), "w", encoding="utf-8"), indent=1)
        print(os.path.basename(d), [(r["page"], r.get("masked"), r.get("unmatched", 0), r.get("ru_model")) for r in sorted(rr, key=lambda r: r["page"])])


if __name__ == "__main__":
    main()
