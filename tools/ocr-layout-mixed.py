#!/usr/bin/env python3
r"""ocr-layout-mixed — MIXED Russian + Esperanto pages read COLUMN BY COLUMN: layout first, language second.

    tools/ocr-layout-mixed.py <root> --pdfs <list> [--jobs 12]

WHY (2026-09-27, the editor chose option γ, then approved it). Choosing Russian or Esperanto line by line
(`ocr-mixed-lines.py`) cannot work where Russian and Esperanto are printed SIDE BY SIDE: the OCR
reads straight across the page, so every line is half Russian, half Esperanto, and one half is lost
whichever is chosen. Four blind looks (an internal record, 2026-09-27, not published) showed this as the main loss.

HOW, per page:
1. PAGE GATE (as rule «gated» in `ocr-mixed-lines.py`): at least 0.14 of the 3+-letter words of the
   page's whole Russian reading (`page-NNNN.rus.txt`, already on disk) must be in the Russian list.
   Pages below it are skipped: no Russian worth recovering.
2. LAYOUT: `tesseract --psm 3` (automatic layout) with the Esperanto model gives text blocks.
3. GUTTER: a block is split in two at a column gutter found IN THE IMAGE, only if the block is wider
   than 60% of the page, taller than 8% of it, and has 5+ lines (display type has wide letter gaps);
   the gutter is a band in the middle 30-70% of the block, >= 12 px wide, inked on under 3% of rows
   once printed rules (columns inked on >= 50% of rows, +-3 px) are set aside; with no printed rule in
   it, the band must be >= 1% of the page wide; and >= 60% of text rows must have ink on BOTH sides.
   Probe, 6 pages: every parallel-column block split at its rule; no full-width text, list or title cut
   (three earlier false cuts — a running head, a list of short lines, a letter-spaced title — gave the
   last three conditions).
4. EACH BLOCK (or half) is cropped and read with both models at psm 6; then rule «share» line by
   line (`ocr-mixed-lines.py`: Russian if the Russian line is >= 60% Cyrillic and under half of the
   Esperanto line's words are in the Latin lists; short lines follow their neighbours). Where the two
   readings of a block differ in line count, the block is taken whole in one language by the same test.
5. OUTPUT: blocks in layout order, split halves left then right — a parallel page comes out as the
   whole Russian column, then the whole Esperanto column.

The Esperanto model here is `epo+eng` (the rendersearch default in `ocr-pdf.sh`) whatever second model
the corpus got elsewhere. Known limits: headings of 1-4 lines spanning both columns are not split;
Armenian and Georgian stay junk (no model used yet).

Writes per page `page-NNNN.layout.json` (always: marks the page done, so a killed run resumes) and
`page-NNNN.layout.txt` (only if at least one Russian line was taken); per corpus `LAYOUT.json`.
Scope: corpora with a `RUSSIAN.json`.
"""
import os, re, sys, json, glob, argparse, subprocess, tempfile, shutil, collections, importlib.util
import concurrent.futures as fut
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
from ocr_page_images import page_images
import ocr_russian_reading as RR   # the old-letter rule: `orus` or `rus` per page
_sa = importlib.util.spec_from_file_location("acc", os.path.join(HERE, "ocr-accept.py"))
ACC = importlib.util.module_from_spec(_sa); _sa.loader.exec_module(ACC)   # ru_only_score(): the validated Russian-only score
_spec = importlib.util.spec_from_file_location("ml", os.path.join(HERE, "ocr-mixed-lines.py"))
ml = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ml)
Image.MAX_IMAGE_PIXELS = None


def lines(t):
    return [l for l in t.split("\n") if l.strip()]


def share(t, words, test):
    ws = [m.group(0) for m in ml.W.finditer(t)]
    return test(ws) / len(ws) if ws else None


def ocr(img, lang, psm):
    return subprocess.run(["tesseract", img, "-", "-l", lang, "--psm", str(psm)] + (["tsv"] if psm == 3 else []),
                          capture_output=True, text=True).stdout


def gutter(a, box, pagew, pageh):
    """x (page coordinates) of a column gutter in the block, or None — rules in the docstring, step 3."""
    l, t, r, b = box
    if r - l < 0.6 * pagew or b - t < 0.08 * pageh:
        return None
    a = a[t:b, l:r]
    frac = a.mean(axis=0)
    rule = frac >= 0.5
    for d in range(1, 4):
        rule = rule | np.roll(rule, d) | np.roll(rule, -d)
    frac = np.where(rule, 0.0, frac)
    w = a.shape[1]; lo, hi = int(0.3 * w), int(0.7 * w)
    best, run, start = None, 0, 0
    for x in range(lo, hi):
        if frac[x] < 0.03:
            if run == 0:
                start = x
            run += 1
            if run >= 12 and (best is None or run > best[1]):
                best = (start, run)
        else:
            run = 0
    if not best:
        return None
    if not rule[best[0]: best[0] + best[1]].any() and best[1] < 0.01 * pagew:
        return None
    rows = a.any(axis=1)
    both = (a[:, :best[0]].any(axis=1) & a[:, best[0] + best[1]:].any(axis=1))[rows]
    return l + best[0] + best[1] // 2 if both.size and both.mean() >= 0.6 else None


def do_page(job):
    """One page; an error is recorded in its .layout.json and never stops the run."""
    try:
        return _do_page(job)
    except Exception as e:
        d, pdf, n = job
        rec = {"page": n, "skipped": "error", "error": f"{type(e).__name__}: {e}"}
        json.dump(rec, open(os.path.join(d, f"page-{n:04d}.layout.json"), "w", encoding="utf-8"))
        return d, rec


def _do_page(job):
    d, pdf, n = job
    lat, ru = ml.lists()
    done = os.path.join(d, f"page-{n:04d}.layout.json")
    rus = open(os.path.join(d, f"page-{n:04d}.rus.txt"), encoding="utf-8", errors="ignore").read()
    g = share(rus, None, lambda ws: ml.ru_score(" ".join(ws), ru)) or 0
    rec = {"page": n, "gate": round(g, 3)}
    txt = os.path.join(d, f"page-{n:04d}.layout.txt")
    if g < 0.14:
        # RESCUE (2026-09-28, the editor required the gate to be verified: every rejected page read, then checked):
        # of 8,068 pages the gate rejected, 5 carried real Russian by the validated Russian-only score (≥ 40), all
        # just under the gate (0.126–0.139). A page under the gate whose chosen Russian reading scores ≥ 40 is let in.
        rt = RR.russian_reading(os.path.join(d, f"page-{n:04d}.txt")) or ""
        s = ACC.ru_only_score(rt) if rt else None
        if s is not None and s >= 40:
            rec["gate_rescue"] = round(s, 1); g = 0.14
    if g < 0.14:
        rec["skipped"] = "page gate"
    else:
        work = tempfile.mkdtemp(prefix="ocrlayout-")
        try:
            img = page_images(pdf, work, jobs=1, pages=[n]).get(n)
            if not img:
                rec["skipped"] = "no image"
            else:
                im = Image.open(img)
                if im.mode not in ("1", "L", "RGB"):
                    im = im.convert("RGB")  # a CMYK scan cannot be written as PNG (the 2026-09-27 run stopped on one)
                W_, H_ = im.size
                ink = np.asarray(im.convert("L")) < 128
                boxes, nl = {}, {}
                for row in ocr(img, "epo+eng", 3).splitlines()[1:]:
                    f = row.split("\t")
                    if len(f) == 12 and f[0] == "5" and f[11].strip():
                        b = int(f[2]); l, t, w, h = map(int, f[6:10])
                        x = boxes.setdefault(b, [l, t, l + w, t + h])
                        x[0], x[1], x[2], x[3] = min(x[0], l), min(x[1], t), max(x[2], l + w), max(x[3], t + h)
                        nl.setdefault(b, set()).add((f[3], f[4]))
                parts, splits = {}, 0
                for b, bx in boxes.items():
                    gx = gutter(ink, bx, W_, H_) if len(nl[b]) >= 5 else None
                    if gx:
                        parts[(b, 0)] = [bx[0], bx[1], gx, bx[3]]; parts[(b, 1)] = [gx, bx[1], bx[2], bx[3]]; splits += 1
                    else:
                        parts[(b, 0)] = bx
                out, n_lines, n_ru, kinds = [], 0, 0, collections.Counter()
                # the Russian model for the blocks: `orus` on a pre-reform page, else `rus` (OLD-LETTER RULE,
                # editor 2026-09-28; tools/ocr_russian_reading.py). The page gate above stays on `rus`, which
                # its 0.14 was measured on.
                rp = RR.russian_reading_path(os.path.join(d, f"page-{n:04d}.txt")) or ""
                ru_lang = "orus" if rp.endswith(".orus.txt") else "rus"
                rec["ru_model"] = ru_lang
                for k in sorted(parts):
                    l, t, r, b = parts[k]; p = 8
                    crop = os.path.join(work, f"b{k[0]}-{k[1]}.png")
                    im.crop((max(0, l - p), max(0, t - p), min(W_, r + p), min(H_, b + p))).save(crop)
                    el, rl = lines(ocr(crop, "epo+eng", 6)), lines(ocr(crop, ru_lang, 6))
                    if el and len(el) == len(rl):
                        pick = ml.pick_share(el, rl, lat); kinds["lines"] += 1
                        chosen = [bb if pp else aa for aa, bb, pp in zip(el, rl, pick)]; k_ru = sum(pick)
                    else:
                        eo, rs = "\n".join(el), "\n".join(rl)
                        ls = share(eo, None, lambda ws: sum(w.lower() in lat for w in ws))
                        isru = bool(rl) and ml.cyr_share(rs) >= 0.6 and (ls is None or ls < 0.5)
                        chosen = rl if isru else el; k_ru = len(rl) if isru else 0; kinds["whole block"] += 1
                    n_lines += len(chosen); n_ru += k_ru
                    if chosen:
                        out.append("\n".join(chosen))
                rec.update(blocks=len(parts), splits=splits, lines=n_lines, ru_lines=n_ru, decided=dict(kinds))
                if n_ru:
                    open(txt, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
        finally:
            shutil.rmtree(work, ignore_errors=True)
    if not rec.get("ru_lines") and os.path.exists(txt):
        os.remove(txt)
    json.dump(rec, open(done, "w", encoding="utf-8"))
    return d, rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--redo-orus", action="store_true",
                    help="redo pages already done whose Russian reading is now `orus` (old-letter rule) but whose "
                         "layout was read with `rus`")
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    jobs, dirs = [], []
    for f in sorted(glob.glob(os.path.join(a.root, "*", "RUSSIAN.json"))):
        d = os.path.dirname(f); stem = os.path.basename(d)
        if stem not in pdfs:
            continue
        dirs.append(d)
        for p in sorted(glob.glob(os.path.join(d, "page-*.rus.txt"))):
            n = int(re.search(r"page-(\d+)\.rus\.txt", p).group(1))
            lj = os.path.join(d, f"page-{n:04d}.layout.json")
            if not os.path.exists(os.path.join(d, f"page-{n:04d}.txt")):
                continue
            if not os.path.exists(lj):
                jobs.append((d, pdfs[stem], n))
            elif a.redo_orus and (RR.russian_reading_path(os.path.join(d, f"page-{n:04d}.txt")) or "").endswith(".orus.txt"):
                rec = json.load(open(lj, encoding="utf-8"))
                if not rec.get("skipped") and rec.get("ru_model") != "orus":
                    jobs.append((d, pdfs[stem], n))
    print(f"{len(dirs)} corpora · {len(jobs)} pages to do", flush=True)
    done = 0
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for _ in ex.map(do_page, jobs, chunksize=4):
            done += 1
            if done % 250 == 0:
                print(f"{done}/{len(jobs)}", flush=True)
    t = collections.Counter()
    for d in dirs:
        recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(d, "page-*.layout.json")))]
        json.dump({"rule": "layout first (psm 3 blocks, split at image gutters), then rule «share» per block; "
                           "page gate 0.14 — see tools/ocr-layout-mixed.py", "pages": recs},
                  open(os.path.join(d, "LAYOUT.json"), "w", encoding="utf-8"), indent=1)
        for r in recs:
            t["pages"] += 1
            if r.get("skipped"):
                t["skipped: " + r["skipped"]] += 1
            elif r["ru_lines"] >= 3:
                t["3+ Russian lines"] += 1
            else:
                t["under 3 Russian lines"] += 1
            t["blocks split at a gutter"] += r.get("splits", 0)
    print(" · ".join(f"{k} {v}" for k, v in t.most_common()), flush=True)


if __name__ == "__main__":
    main()
