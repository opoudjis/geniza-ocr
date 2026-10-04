#!/usr/bin/env python3
r"""ocr-vision-batch — the VISION RECIPE in three steps: render a batch's images, print a transcriber's prompt, file the return.

    tools/ocr-vision-batch.py render --dir <run dir> --pdfs <PDF list> [--jobs 6]
    tools/ocr-vision-batch.py prompt --dir <run dir> --batch bNNN
    tools/ocr-vision-batch.py file   --dir <run dir> --batch bNNN --record <transcriptions .md>

M4.3 (2026-10-02), promoted from the scratch scripts of 30 Sep, which ran the 1,279-page vision pass (an internal
record, 2026-09-30, not published). Same recipe,
paths made parameters. Vision is used ONLY where a check showed a quality issue (standing rule), so a run starts from a
list of pages someone has already found wanting.

THE RUN DIR holds: `KEY-ALL.tsv` (batch · tag · corpus · PDF page · kind, one line per page, tags 01, 02 … within a
batch), `BRIEF-TEMPLATE.md` (the transcriber's brief between two «---» lines), and one folder per batch with its own
`KEY.tsv` (tag · corpus · page). The transcribers' returns go to `<run dir>/returns/bNNN.txt`.

render  For each page not yet rendered: the page image the CONVERSION read (`tools/ocr_page_images.py` — the same image
        rule as every other reading), greyscale, long side at most 2400 px (about 200 dpi on an A4 page), saved as
        `bNNN/<tag>.png`, plus `bNNN/<tag>.boost.png` (autocontrast, cutoff 0.5). Images are kept (never discarded).
prompt  Prints the write-mode prompt: the transcriber may use only the Read and Write tools (transcribers run no shell
        commands — standing rule), reads the brief, the key and the images, and WRITES its blocks (=== 01 === … then
        === NOTES ===) to `returns/bNNN.txt`.
file    Files a return: `page-NNNN.vision.txt` in the item's folder for every block that is not «NONE», NEVER over a
        hand-keyed or ruled reading (`page-NNNN.hand.txt`, `.ruled.txt`); the returned text VERBATIM, with the batch's
        key, appended to --record; a line in `<run dir>/FILED.tsv`. A batch with no return is logged in
        `FAILED-BATCHES.txt`.
"""
import os, re, sys, argparse, tempfile, shutil, collections
import concurrent.futures as fut

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
R = os.path.join(ROOT, "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")


def render(a):
    sys.path.insert(0, HERE)
    import ocr_page_images as OPI
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = None
    paths = {os.path.splitext(os.path.basename(l.strip()))[0]: (l.strip() if l.strip().startswith("/") else os.path.join(ROOT, l.strip()))
             for l in open(a.pdfs) if l.strip()}
    jobs = [l.rstrip("\n").split("\t") for l in open(os.path.join(a.dir, "KEY-ALL.tsv")) if l.strip()]
    by = collections.defaultdict(list)
    for b, tag, c, p, *_ in jobs:
        if not os.path.exists(os.path.join(a.dir, b, f"{tag}.boost.png")): by[c].append((b, tag, int(p)))

    def corpus(c):
        work = tempfile.mkdtemp(prefix="vision-"); n = 0
        try:
            im = OPI.page_images(paths[c], work, jobs=2, pages=[p for _, _, p in by[c]])
            for b, tag, p in by[c]:
                if p not in im: continue
                os.makedirs(os.path.join(a.dir, b), exist_ok=True)
                g = Image.open(im[p]).convert("L")
                if max(g.size) > 2400: g.thumbnail((2400, 2400))
                g.save(os.path.join(a.dir, b, f"{tag}.png"))
                ImageOps.autocontrast(g, cutoff=0.5).save(os.path.join(a.dir, b, f"{tag}.boost.png")); n += 1
        finally:
            shutil.rmtree(work, ignore_errors=True)   # the helper's working copies; the batch images are kept
        return c, n
    with fut.ThreadPoolExecutor(a.jobs) as ex:
        for c, n in ex.map(corpus, sorted(by)): print(c, n, flush=True)
    print("done")


def prompt(a):
    d = os.path.abspath(a.dir); out = os.path.join(d, "returns", f"{a.batch}.txt")
    print(f"USE ONLY THE Read AND Write TOOLS — no shell commands, no directory listings, no other files written. Read "
          f"{d}/BRIEF-TEMPLATE.md and follow the brief between its two «---» lines, for batch {a.batch}: read {a.batch}/KEY.tsv "
          f"in that folder for the pages (tag, source, PDF page), then the images {a.batch}/01.png, {a.batch}/01.boost.png and so "
          f"on for every tag in the key. Then WRITE the blocks the brief specifies (=== 01 === … then === NOTES ===), and nothing "
          f"else, to the file {out}. Your final reply must be ONLY the single line: WROTE {a.batch}")


def file_return(a):
    b = a.batch; ret = os.path.join(a.dir, "returns", f"{b}.txt")
    if not os.path.exists(ret):
        open(os.path.join(a.dir, "FAILED-BATCHES.txt"), "a").write(f"{b}\tno return at {ret}\n"); sys.exit(f"{b}: no return found")
    txt = open(ret, encoding="utf-8").read()
    key = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(os.path.join(a.dir, b, "KEY.tsv")) if l.strip()}
    blocks = dict(re.findall(r"=== (\d\d) ===\n(.*?)(?=\n=== (?:\d\d|NOTES) ===|\Z)", txt, re.S))
    wrote = 0; nones = []; missing = [t for t in key if t not in blocks]
    for tag, body in blocks.items():
        if tag not in key: continue
        if body.strip() == "NONE": nones.append(tag); continue
        _, c, p = key[tag][:3]; p = int(p); d = os.path.join(R, c)
        if os.path.exists(os.path.join(d, f"page-{p:04d}.hand.txt")) or os.path.exists(os.path.join(d, f"page-{p:04d}.ruled.txt")): continue
        open(os.path.join(d, f"page-{p:04d}.vision.txt"), "w", encoding="utf-8").write(body.strip() + "\n"); wrote += 1
    if not os.path.exists(a.record):
        open(a.record, "w", encoding="utf-8").write(f"# Vision transcriptions — {os.path.basename(os.path.abspath(a.dir))}\n\n"
                                                    "Returned text verbatim, batch by batch (tools/ocr-vision-batch.py file).\n\n")
    with open(a.record, "a", encoding="utf-8") as f:
        f.write(f"## {b}\n\nKey (tag → corpus, page):\n\n```\n" + "".join(f"{k}\t{v[1]}\t{v[2]}\n" for k, v in sorted(key.items()))
                + "```\n\n### Returned text, verbatim\n\n" + txt.strip() + "\n\n")
    with open(os.path.join(a.dir, "FILED.tsv"), "a") as f: f.write(f"{b}\t{ret}\t{wrote}\t{','.join(nones)}\t{','.join(missing)}\n")
    print(f"{b}: {len(blocks)} blocks · {wrote} filed · NONE {nones} · missing {missing}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("render", "prompt", "file")); ap.add_argument("--dir", required=True)
    ap.add_argument("--pdfs"); ap.add_argument("--jobs", type=int, default=6); ap.add_argument("--batch"); ap.add_argument("--record")
    a = ap.parse_args()
    if a.mode == "render" and not a.pdfs: sys.exit("render needs --pdfs")
    if a.mode in ("prompt", "file") and not a.batch: sys.exit(f"{a.mode} needs --batch")
    if a.mode == "file" and not a.record: sys.exit("file needs --record")
    {"render": render, "prompt": prompt, "file": file_return}[a.mode](a)
