#!/usr/bin/env python3
r"""ocr-reocr-best — RE-OCR poor scans: find, per item, the render/threshold/layout that reads best.

    tools/ocr-reocr-best.py probe <root> --pdfs <list> --items <json list> --out <probe.json> [--jobs 12]
    tools/ocr-reocr-best.py run   <root> --pdfs <list> --probe <probe.json> [--min-gain 5] [--jobs 12]
    tools/ocr-reocr-best.py pages <root> --pdfs <list> --list <corpus<TAB>page tsv> [--jobs 12]
PAGES mode (2026-09-27, the editor's choice of options 1 and 3): single pages — the LOST pages of the image sorts. Every variant is
tried on the page and the best is kept only if it scores higher than the page as it stands (a LOST page
often scores nothing, so any real reading wins); the rest go to vision transcription.

WHY (the editor's decision of 2026-09-27 15:35 to re-OCR the poor scans). 53 items (679 pp) fail G4 on scan quality —
not on language, not Russian, not rosters (an internal record, 2026-09-27, not published: family G + the 7
failing Ido items). The pipeline already tried 300 ppi and psm 4/6; these are the untried levers.

PROBE: 3 evenly spaced pages per item (all if fewer), each read with every VARIANT:
  v400      400 ppi grey, psm 6
  v400s     400 ppi grey, psm 6, Sauvola adaptive threshold (`-c thresholding_method=2`) — faint/uneven ink
  v400s4    400 ppi grey, psm 4, Sauvola — columns and lists
  vfrk      400 ppi grey, psm 6, `frk+epo` — FRAKTUR items only (Estlanda Esperantisto, Idowoti)
Score = median over the sample of the share of 2+-letter words in the item's own lexicon (Esperanto, or
Ido for Ido items) — the gate's G4 idea, on the sample. The CURRENT text's pages are scored the same way.
RUN: an item is re-read in full with its best variant only if that beats the current text by >= min-gain
points on the sample; then, PAGE BY PAGE, the re-read is kept only where it scores higher than the
current page. Writes `page-NNNN.reocr.txt` BESIDE the existing files and `REOCR.json`; replaces nothing.
Base language `epo+eng` as the render-search pipeline (`ocr-pdf.sh` default).
"""
import os, re, sys, glob, json, argparse, subprocess, tempfile, shutil, statistics, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("OMP_THREAD_LIMIT", "1")
LEXDIR = os.path.join(HERE, "lexicons")
W = re.compile(r"[^\W\d_]{2,}")
_L = {}
FRAKTUR = ("EstlandaEsperantisto", "Idowoti")
IDO = ("posta_mundi", "matematikal", "nordamuziko", "rusalibrovortaro", "ukraina", "Idomarcho", "Idowoti",
       "sundiala", "vivo", "latviana")


def lex(name):
    if name not in _L:
        _L[name] = {w.strip().lower() for w in open(os.path.join(LEXDIR, name + ".txt"), encoding="utf-8", errors="ignore") if w.strip()}
    return _L[name]


def score(text, lexname):
    ws = [w.lower() for w in W.findall(text)]
    return 100.0 * sum(w in lex(lexname) for w in ws) / len(ws) if len(ws) >= 20 else None


def lexname(item):
    return "ido" if any(item.startswith(p) or p in item for p in IDO) else "esperanto"


def variants(item):
    v = {"v400": (400, "6", False, "epo+eng"), "v400s": (400, "6", True, "epo+eng"), "v400s4": (400, "4", True, "epo+eng")}
    if any(item.startswith(p) for p in FRAKTUR):
        v["vfrk"] = (400, "6", False, "frk+epo")
    return v


def read_page(pdf, n, spec, work):
    dpi, psm, sauvola, lang = spec
    stem = os.path.join(work, f"r{n}-{dpi}")
    if not glob.glob(stem + "*.png"):
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), pdf, stem], capture_output=True)
    img = stem + ".png"
    if not os.path.exists(img):
        return ""
    cmd = ["tesseract", img, "-", "-l", lang, "--psm", psm] + (["-c", "thresholding_method=2"] if sauvola else [])
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def current_pages(root, item):
    p = os.path.join(root, item + ".txt")
    t = open(p, encoding="utf-8", errors="ignore").read() if os.path.exists(p) else ""
    parts = re.split(r"\n=== page (\d+) ===\n", "\n" + t)
    return dict(zip(map(int, parts[1::2]), parts[2::2]))


def probe_item(job):
    root, item, pdf = job
    cur = current_pages(root, item); ln = lexname(item)
    pages = sorted(p for p, t in cur.items() if len(W.findall(t)) >= 20) or sorted(cur)
    sample = pages if len(pages) <= 3 else [pages[len(pages) // 6], pages[len(pages) // 2], pages[5 * len(pages) // 6]]
    work = tempfile.mkdtemp(prefix="reocr-")
    try:
        res = {"item": item, "lexicon": ln, "sample": sample,
               "current": statistics.median([s for s in (score(cur.get(p, ""), ln) for p in sample) if s is not None] or [0])}
        for name, spec in variants(item).items():
            sc = [score(read_page(pdf, p, spec, work), ln) for p in sample]
            sc = [s for s in sc if s is not None]
            res[name] = statistics.median(sc) if sc else 0
        best = max((k for k in res if k.startswith("v")), key=lambda k: res[k])
        res["best"] = best; res["gain"] = round(res[best] - res["current"], 1)
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_page(job):
    root, item, pdf, n, spec, ln = job
    d = os.path.join(root, item); work = tempfile.mkdtemp(prefix="reocr-")
    try:
        t = read_page(pdf, n, spec, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return item, n, t


def page_all_variants(job):
    root, item, pdf, n = job
    ln = lexname(item); work = tempfile.mkdtemp(prefix="reocr-")
    try:
        best = (None, None, "")
        for name, spec in variants(item).items():
            t = read_page(pdf, n, spec, work); sc = score(t, ln)
            if sc is not None and (best[1] is None or sc > best[1]):
                best = (name, sc, t)
        return item, n, best
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("probe", "run", "pages")); ap.add_argument("root")
    ap.add_argument("--list")
    ap.add_argument("--pdfs", required=True); ap.add_argument("--items"); ap.add_argument("--out"); ap.add_argument("--probe")
    ap.add_argument("--min-gain", type=float, default=5.0); ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs) if l.strip()}
    if a.mode == "probe":
        items = [i for i in json.load(open(a.items)) if i in pdfs]
        with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            res = list(ex.map(probe_item, [(a.root, i, pdfs[i]) for i in items]))
        json.dump(res, open(a.out, "w"), indent=1)
        for r in sorted(res, key=lambda r: -r["gain"]):
            print(f"{r['item'][:40]:40} {r['lexicon']:9} current {r['current']:5.1f}  " +
                  "  ".join(f"{k} {r[k]:5.1f}" for k in r if k.startswith("v")) + f"  → {r['best']} {r['gain']:+.1f}")
        return
    if a.mode == "pages":
        want = [l.rstrip("\n").split("\t")[:2] for l in open(a.list, encoding="utf-8") if l.strip()]
        jobs = [(a.root, c, pdfs[c], int(p)) for c, p in want if c in pdfs]
        kept, recs = 0, collections.defaultdict(list)
        with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
            for item, n, (name, new, t) in ex.map(page_all_variants, jobs):
                old = score(current_pages(a.root, item).get(n, ""), lexname(item))
                keep = new is not None and (old is None or new > old)
                recs[item].append({"page": n, "variant": name, "new": new, "old": old, "kept": keep})
                if keep:
                    open(os.path.join(a.root, item, f"page-{n:04d}.reocr.txt"), "w", encoding="utf-8").write(t); kept += 1
        for item, rr in recs.items():
            json.dump({"mode": "pages (LOST pages)", "pages": rr}, open(os.path.join(a.root, item, "REOCR-PAGES.json"), "w"), indent=1)
        print(f"{len(jobs)} pages · re-read kept on {kept} · the rest for vision")
        return
    probe = json.load(open(a.probe)); jobs = []
    for r in probe:
        if r["gain"] < a.min_gain:
            continue
        spec = variants(r["item"])[r["best"]]
        for p in current_pages(a.root, r["item"]):
            jobs.append((a.root, r["item"], pdfs[r["item"]], p, spec, r["lexicon"]))
    kept = collections.Counter(); recs = collections.defaultdict(list)
    with fut.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for item, n, t in ex.map(run_page, jobs, chunksize=2):
            ln = lexname(item); cur = current_pages(a.root, item).get(n, "")
            new, old = score(t, ln), score(cur, ln)
            keep = new is not None and (old is None or new > old)
            recs[item].append({"page": n, "new": new, "old": old, "kept": keep})
            p = os.path.join(a.root, item, f"page-{n:04d}.reocr.txt")
            if keep:
                open(p, "w", encoding="utf-8").write(t); kept[item] += 1
            elif os.path.exists(p):
                os.remove(p)
    for item, rr in recs.items():
        best = next(r for r in probe if r["item"] == item)
        json.dump({"variant": best["best"], "spec": list(variants(item)[best["best"]]), "pages": rr},
                  open(os.path.join(a.root, item, "REOCR.json"), "w"), indent=1)
    print(f"{len(recs)} items re-read · pages kept {sum(kept.values())} of {len(jobs)}")


if __name__ == "__main__":
    main()
