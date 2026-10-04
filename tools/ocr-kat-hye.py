#!/usr/bin/env python3
r"""ocr-kat-hye — GEORGIAN and ARMENIAN text on the pages that carry it, as readings of their own.

    tools/ocr-kat-hye.py <root> --pdfs <list> --items <glob> --out-kat <dir> --out-hye <dir> [--jobs 12]
    e.g. --items 'KaukazaEsperantisto*'

WHY (the editor asked on 2026-09-27 13:07 for Georgian and Armenian to be added). *Kaŭkaza Esperantisto*
(Tiflis) prints Georgian and Armenian beside Russian and Esperanto. Every model used so far turned those
blocks into junk (blind looks 1–5 and the clean-readings look, 2026-09-27).

HOW, per page — layout first, as `ocr-layout-mixed.py` (same psm 3 blocks, same image-gutter split):
each block (1%+ of the page) is read at psm 6 with `kat`, `hye`, `rus` and `epo+eng`, and the block is
GEORGIAN or ARMENIAN if that model's mean word confidence is >= 40 AND at least 8 points above the best
of `rus` and `epo+eng`. Probe, 3 known pages, 2026-09-27: Georgian blocks kat 45–88 vs every other <= 41;
Armenian blocks hye 47–91 vs the next best 35–50. Tesseract's own script detector (`--psm 0`) was tried
first and FAILED — it called Georgian «Bengali» and Georgian/Armenian «Arabic». `kat_old` was dropped:
it reads 1910 print as Asomtavruli capitals (junk).

WRITES per page `page-NNNN.kathye.json` (always; marks it done — a killed run resumes) and, where such
blocks exist, `page-NNNN.kat.txt` / `page-NNNN.hye.txt` holding ONLY those blocks, in layout order.
Per item, `<out-kat>/<item>.txt` and `<out-hye>/<item>.txt` in the combined files' format — SIBLING
folders of `ocr-rendersearch/`, as `ocr-rendersearch-rus/`, so no `*.txt` lister counts them as items.
Nothing existing is touched; the Esperanto and Russian readings stay as they are.
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, statistics, importlib.util
import concurrent.futures as fut
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images
_spec = importlib.util.spec_from_file_location("lm", os.path.join(HERE, "ocr-layout-mixed.py"))
lm = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(lm)
Image.MAX_IMAGE_PIXELS = None
LANGS = ("kat", "hye", "rus", "epo+eng")
MIN_CONF, MARGIN = 40, 8


def read(img, lang):
    out = subprocess.run(["tesseract", img, "-", "-l", lang, "--psm", "6", "tsv"], capture_output=True, text=True).stdout
    ws = [f for f in (r.split("\t") for r in out.splitlines()[1:]) if len(f) == 12 and f[0] == "5" and f[11].strip()]
    if not ws:
        return 0.0, ""
    lines = {}
    for f in ws:
        lines.setdefault((f[2], f[3], f[4]), []).append(f[11])
    return statistics.mean(float(f[10]) for f in ws), "\n".join(" ".join(v) for v in lines.values())


def do_page(job):
    d, pdf, n = job
    done = os.path.join(d, f"page-{n:04d}.kathye.json")
    rec = {"page": n}
    work = tempfile.mkdtemp(prefix="ocrlayout-")
    try:
        img = page_images(pdf, work, jobs=1, pages=[n]).get(n)
        if not img:
            rec["skipped"] = "no image"
        else:
            im = Image.open(img)
            if im.mode not in ("1", "L", "RGB"):
                im = im.convert("RGB")
            W, H = im.size; ink = np.asarray(im.convert("L")) < 128
            boxes, nl = {}, {}
            for row in lm.ocr(img, "epo+eng", 3).splitlines()[1:]:
                f = row.split("\t")
                if len(f) == 12 and f[0] == "5" and f[11].strip():
                    b = int(f[2]); l, t, w, h = map(int, f[6:10])
                    x = boxes.setdefault(b, [l, t, l + w, t + h])
                    x[0], x[1], x[2], x[3] = min(x[0], l), min(x[1], t), max(x[2], l + w), max(x[3], t + h)
                    nl.setdefault(b, set()).add((f[3], f[4]))
            parts = {}
            for b, bx in boxes.items():
                g = lm.gutter(ink, bx, W, H) if len(nl[b]) >= 5 else None
                if g:
                    parts[(b, 0)] = [bx[0], bx[1], g, bx[3]]; parts[(b, 1)] = [g, bx[1], bx[2], bx[3]]
                else:
                    parts[(b, 0)] = bx
            got = {"kat": [], "hye": []}; blocks = []
            for k in sorted(parts):
                l, t, r, b = parts[k]
                if (r - l) * (b - t) < 0.01 * W * H:
                    continue
                crop = os.path.join(work, f"b{k[0]}-{k[1]}.png")
                im.crop((max(0, l - 8), max(0, t - 8), min(W, r + 8), min(H, b + 8))).save(crop)
                res = {lang: read(crop, lang) for lang in LANGS}
                other = max(res["rus"][0], res["epo+eng"][0])
                pick = None
                for lang in ("kat", "hye"):
                    c = res[lang][0]
                    if c >= MIN_CONF and c >= other + MARGIN and (pick is None or c > res[pick][0]):
                        pick = lang
                blocks.append({"block": list(k), "conf": {x: round(res[x][0]) for x in LANGS}, "script": pick})
                if pick:
                    got[pick].append(res[pick][1])
            rec["blocks"] = blocks
            for lang in ("kat", "hye"):
                p = os.path.join(d, f"page-{n:04d}.{lang}.txt")
                rec[lang + "_blocks"] = len(got[lang])
                if got[lang]:
                    open(p, "w", encoding="utf-8").write("\n\n".join(got[lang]) + "\n")
                elif os.path.exists(p):
                    os.remove(p)
    except Exception as e:
        rec = {"page": n, "skipped": "error", "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    json.dump(rec, open(done, "w", encoding="utf-8"))
    return d, rec


def companions(dirs, lang, out):
    os.makedirs(out, exist_ok=True); items = pages = 0
    for d in dirs:
        stem = os.path.basename(d); body = []
        for f in sorted(glob.glob(os.path.join(d, f"page-*.{lang}.txt")),
                        key=lambda p: int(re.search(r"page-(\d+)\.", p).group(1))):
            n = int(re.search(r"page-(\d+)\.", f).group(1))
            body.append(f"=== page {n} ===\n{open(f, encoding='utf-8').read().rstrip()}\n")
        target = os.path.join(out, stem + ".txt")
        if body:
            open(target, "w", encoding="utf-8").write("\n" + "\n".join(body)); items += 1; pages += len(body)
        elif os.path.exists(target):
            os.remove(target)
    return items, pages


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--pdfs", required=True); ap.add_argument("--items", required=True)
    ap.add_argument("--out-kat", required=True); ap.add_argument("--out-hye", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    dirs = [d for d in sorted(glob.glob(os.path.join(a.root, a.items))) if os.path.isdir(d) and os.path.basename(d) in pdfs]
    jobs = []
    for d in dirs:
        for p in glob.glob(os.path.join(d, "page-*.txt")):
            m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(p))
            if m and not os.path.exists(os.path.join(d, f"page-{int(m.group(1)):04d}.kathye.json")):
                jobs.append((d, pdfs[os.path.basename(d)], int(m.group(1))))
    print(f"{len(dirs)} items · {len(jobs)} pages to do", flush=True)
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for _ in ex.map(do_page, jobs, chunksize=2):
            pass
    ki, kp = companions(dirs, "kat", a.out_kat); hi, hp = companions(dirs, "hye", a.out_hye)
    errs = sum(1 for d in dirs for f in glob.glob(os.path.join(d, "page-*.kathye.json")) if json.load(open(f)).get("skipped") == "error")
    print(f"Georgian: {ki} items, {kp} pages · Armenian: {hi} items, {hp} pages · page errors {errs}", flush=True)


if __name__ == "__main__":
    main()
