#!/usr/bin/env python3
r"""cupel-c3-lists — `RUNBOOK.md` C3: the batch's three lists, from an explicit list of its PDFs.

    python3 tools/cupel-c3-lists.py --geniza <G> --date <YYYY-MM-DD> --batch <cupelN> --batch-dir <batch dir>
                                        --old <the current full PDF list> --pdfs <file: the batch's PDFs, one path a line>
                                        [--sources <dir, default <G>/sources>]

Folded into tools/ 2026-10-13 (the editor approved folding the recurring scratchpad scripts in) from cupel10's
`cupel10-c3-lists.py` (an internal record, 2026-10-13, not published). Unchanged in what it writes.
WRITES only three new files (refuses if any exists): <sources>/OCR-PDF-LIST-<date>-<batch>-NEW.txt (the batch's PDFs),
<sources>/OCR-PDF-LIST-<date>-<batch>.txt (= the old full list + the NEW lines) and <batch dir>/ITEMS.txt (one stem a
line: the PDF's name without .pdf). CHECKS FIRST, writing nothing if one fails: every PDF exists and is a .pdf; no stem
twice; no stem already on the old list; no stem a folder in <G>/sources/ocr-rendersearch.
"""
import argparse, os, sys


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for k in ("--geniza", "--date", "--batch", "--batch-dir", "--old", "--pdfs"):
        ap.add_argument(k, required=True)
    ap.add_argument("--sources", help="where the two PDF lists are written (default <geniza>/sources)")
    a = ap.parse_args()
    R = os.path.join(a.geniza, "sources", "ocr-rendersearch")
    src = a.sources or os.path.join(a.geniza, "sources")
    new = [l.strip() for l in open(a.pdfs, encoding="utf-8") if l.strip()]
    old = [l.strip() for l in open(a.old, encoding="utf-8") if l.strip()]
    stem = lambda p: os.path.basename(p)[:-4] if p.endswith(".pdf") else None
    errs = [f"missing: {p}" for p in new if not os.path.isfile(p)] + [f"not a .pdf: {p}" for p in new if stem(p) is None]
    ss = [stem(p) for p in new]
    errs += [f"stem twice: {s}" for s in sorted({s for s in ss if ss.count(s) > 1})]
    olds = {stem(p) for p in old}
    errs += [f"stem already on the old list: {s}" for s in ss if s in olds]
    errs += [f"stem a folder in $R: {s}" for s in ss if s and os.path.isdir(os.path.join(R, s))]
    outs = [os.path.join(src, f"OCR-PDF-LIST-{a.date}-{a.batch}-NEW.txt"),
            os.path.join(src, f"OCR-PDF-LIST-{a.date}-{a.batch}.txt"), os.path.join(a.batch_dir, "ITEMS.txt")]
    errs += [f"exists: {o}" for o in outs if os.path.exists(o)]
    if errs:
        sys.exit("\n".join(errs))
    with open(outs[0], "x", encoding="utf-8") as f:
        f.write("\n".join(new) + "\n")
    with open(outs[1], "x", encoding="utf-8") as f:
        f.write("\n".join(old + new) + "\n")
    with open(outs[2], "x", encoding="utf-8") as f:
        f.write("\n".join(ss) + "\n")
    print(f"NEW {len(new)} · full {len(old)} + {len(new)} = {len(old) + len(new)} · ITEMS {len(ss)}")
    for o in outs:
        print(o)


if __name__ == "__main__":
    main()
