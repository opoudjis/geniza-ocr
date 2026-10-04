#!/usr/bin/env python3
"""
ocr-repass-pages.py — re-OCR a NAMED LIST OF PAGES in a second language string, keeping the first.

WHY: the *Belga Esperantisto* OCR was produced `-l epo` across all 71 issues. The Esperanto
is sound and the erasure findings rest on it — but the Dutch and French on the same pages are
mangled (JAARLIJKSCHIE for JAARLIJKSCHE · KRNEST SOLVAV for ERNEST SOLVAY · ANDELROF for
ANDELHOF · ĉei-inĝeniero for ĉef-). The parallel-column pages — «Het Esperanto in den Vreemde»
and its French twin — are exactly the pages a Dutch model would fix.

IT DOES NOT OVERWRITE. `page-0021.txt` stays as it is; the new text lands beside it as
`page-0021.epo+nld+fra.txt`. The Esperanto findings cite the original BY LINE, and re-verifying
them to save a few megabytes would be a bad trade.

AND IT REPORTS WHAT MOVED. A re-OCR is only interesting where it changed something, so the
run ends with a per-page similarity score and the lines that differ most. **The material
question it exists to answer: is the Dutch column a translation of the Esperanto, or independent
copy?** A page whose Dutch changes a great deal is a page whose earlier reading was guesswork.

  python3 tools/ocr-repass-pages.py --list <pages.tsv> --pdfs <dir> --out <ocr-root> \\
                                    --lang epo+nld+fra [--report <out.md>]

The page list is TSV: `<issue-stem>\\t<space-separated page numbers>`.
"""
import re, os, sys, csv, html, difflib, argparse, subprocess, tempfile, pathlib
from glob import glob as _pre_glob

def render(pdf, page, dpi=300):
    """One page → a temporary 300-dpi grayscale PNG. Deleted by the caller."""
    fd, png = tempfile.mkstemp(suffix=".png"); os.close(fd)
    subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi),
                    "-gray", "-png", "-singlefile", pdf, png[:-4]],
                   check=True, capture_output=True)
    return png

def ocr(png, lang, psm="3"):
    # --psm MATTERS ON LIST-SHAPED PAGES, which is most of what this tool is pointed at.
    # The default mode reads a multi-column roster as running prose and shreds the names: one
    # Kongresa Libro volume went from 977 page-level errors to 77 on `--psm 4` alone. Attendee
    # rosters, membership lists, subscriber lists: pass --psm 4.
    r = subprocess.run(["tesseract", png, "stdout", "-l", lang, "--psm", str(psm)],
                       capture_output=True, text=True)
    return r.stdout

def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--out", required=True);  ap.add_argument("--lang", default="epo+nld")
    ap.add_argument("--report", default="");  ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--psm", default="3",
                    help="tesseract page-segmentation mode; use 4 for roster / "
                         "multi-column list pages (977 errors -> 77 on one volume)")
    ap.add_argument("--skip-existing", action="store_true",
                    help="don't redo a page whose output already exists — the tool is "
                         "safe to re-run at any point")
    a = ap.parse_args()

    # TWO LIST FORMATS, because the prose-derived list and the generated one differ:
    #   (a) «<issue-stem>\t<page numbers…>»                     — hand-parsed from § 6
    #   (b) «issue\tpage\tpriority\trecipe\tnld_chars\tfra_chars» — a generated set,
    #       which names every page unambiguously AND carries its own per-row recipe.
    # (b) wins where present: the recipe column overrides --lang, so one invocation does
    # both priorities at their right language strings instead of two runs at guessed ones.
    jobs = []
    with open(a.list, encoding="utf-8") as fh:
        rows = [r for r in csv.reader(fh, delimiter="\t") if r and not r[0].startswith("#")]
    if rows and rows[0][:2] == ["issue", "page"]:
        for r in rows[1:]:
            if len(r) < 2: continue
            m = re.search(r"(\d+)", r[1])
            if m: jobs.append((r[0], int(m.group(1)), (r[3] if len(r) > 3 and r[3] else a.lang)))
    else:
        for r in rows:
            if len(r) < 2: continue
            for p in r[1].split(): jobs.append((r[0], int(p), a.lang))
    if a.skip_existing:
        keep = []
        for stem, page, lang in jobs:
            hits = _pre_glob(os.path.join(a.out, f"*{stem}", f"page-{page:04d}.{lang}.txt"))
            if not hits: keep.append((stem, page, lang))
        print(f"  skipping {len(jobs)-len(keep)} already re-read", flush=True)
        jobs = keep
    if a.limit: jobs = jobs[:a.limit]
    print(f"{len(jobs)} pages · recipes: "
          + ", ".join(f"{k}×{sum(1 for j in jobs if j[2]==k)}" for k in sorted({j[2] for j in jobs})),
          flush=True)

    # The page list names issues as «1909_n003_jan»; the files on disk are
    # «BelgaEsperantisto_1909_n003_jan.pdf». Resolve by SUFFIX rather than making the caller
    # restate a prefix — the first run reported all 145 pages as "no pdf" for exactly this.
    import glob as _glob
    def resolve(stem):
        hit = [p for p in _glob.glob(os.path.join(a.pdfs, "*.pdf"))
               if os.path.basename(p)[:-4].endswith(stem)]
        return hit[0] if len(hit) == 1 else None

    results, missing = [], []
    for i, (stem, page, lang) in enumerate(jobs, 1):
        pdf = resolve(stem)
        if not pdf: missing.append((stem, page, "no pdf")); continue
        full = os.path.basename(pdf)[:-4]
        old = os.path.join(a.out, full, f"page-{page:04d}.txt")
        new = os.path.join(a.out, full, f"page-{page:04d}.{lang}.txt")
        try:
            png = render(pdf, page)
        except subprocess.CalledProcessError:
            missing.append((stem, page, "render failed")); continue
        try:
            txt = ocr(png, lang, a.psm)
        finally:
            os.unlink(png)
        pathlib.Path(new).parent.mkdir(parents=True, exist_ok=True)
        open(new, "w", encoding="utf-8").write(txt)
        before = open(old, encoding="utf-8", errors="replace").read() if os.path.exists(old) else ""
        ratio = difflib.SequenceMatcher(None, norm(before), norm(txt)).ratio() if before else 0.0
        results.append((stem, page, ratio, before, txt, lang))
        if i % 20 == 0: print(f"  {i}/{len(jobs)}", flush=True)

    results.sort(key=lambda r: r[2])
    o = open(a.report, "w", encoding="utf-8") if a.report else sys.stdout
    P = lambda *x: print(*x, file=o)
    # report the recipes ACTUALLY USED, not the --lang default: with a recipe column in the
    # list they diverge, and a header that misnames its own pass becomes a wrong claim later.
    used = " + ".join(sorted({r[5] for r in results})) or a.lang
    P(f"# Belga Esperantisto — targeted re-OCR, `{used}` `[tools/ocr-repass-pages.py]`\n")
    P(f"**{len(results)} pages re-read** in `{used}`, against the original `-l epo`. "
      "⛔ **The `-l epo` text is untouched** — the new text sits beside it as "
      f"`page-NNNN.<recipe>.txt`, because the Esperanto findings cite the original by line.\n")
    if missing:
        P(f"⚠ **{len(missing)} pages could not be read:** " +
          ", ".join(f"{s} p.{p} ({why})" for s, p, why in missing[:12]) + "\n")
    moved = [r for r in results if r[2] < 0.90]
    P(f"**{len(moved)} of {len(results)} pages changed materially** (similarity < 0.90). "
      "A page that barely moved was already right; a page that moved a lot was guesswork.\n")
    P("| issue | page | recipe | similarity | verdict |")
    P("|---|---:|---|---:|---|")
    for stem, page, ratio, _, _, lang in results[:60]:
        v = ("⛔ **rewritten**" if ratio < 0.70 else "⚠ substantially changed" if ratio < 0.90
             else "· unchanged in substance")
        P(f"| {stem} | {page} | `{lang}` | {ratio:.2f} | {v} |")
    if len(results) > 60: P(f"\n*(showing the 60 most-changed of {len(results)})*")

    P("\n---\n\n## The biggest changes, line by line\n")
    P("*What the Esperanto-only model was reading, against what a Dutch/French model reads.*\n")
    for stem, page, ratio, before, after, lang in results[:8]:
        P(f"### {stem} · page {page} · similarity {ratio:.2f}\n")
        d = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                      lineterm="", n=0))[2:]
        for line in d[:24]:
            if line.startswith("-"): P(f"- `epo`  {line[1:][:110]}")
            elif line.startswith("+"): P(f"+ `{lang}`  {line[1:][:110]}")
        P("")
    if a.report: o.close()
    print(f"DONE · {len(results)} pages · {len(moved)} changed materially")

if __name__ == "__main__":
    main()
