#!/usr/bin/env python3
"""ocr-holdings-census.py — every document the projects hold that is neither on the cupel's PDF list nor left out on purpose.

    python3 tools/ocr-holdings-census.py --pdfs <the full OCR-PDF-LIST> --out <new .md>

WHY (2026-10-10: the editor was concerned that Ĥvorostin had been dark and missed, and asked what else might have been
missed; approved a standing check at the start of every cupel batch, so that this cannot recur silently; and ruled that
anything used in the Geniza must be held as a copy in the Geniza, the Tekstaro being the large exception). Ĥvorostin 1972
sat image-only in another project's sources for months, outside every dowse. The census of that day (an internal record,
2026-10-10, not published) also showed how a
false alarm happens: a folder outside the list is not yet a missed source (the Belga Sonorilo per-issue run is a second copy).
So this tool lists LEADS, each to be checked against the ledger and the files before anything is said to the editor.

WHAT. Documents (.pdf .doc .docx .djvu .epub) under <project>/sources/ in every project, skipping machinery folders (OCR
outputs, page images, scans, cupel batch folders, the REU download). A document is ACCOUNTED FOR if it is on the PDF list (by
path or file name), or a born-digital list's text (by item), or matches a line of the left-out register
(geniza/ocr/method/CENSUS-LEFT-OUT.tsv: a path glob relative to heterophony-resources/, the reason, the ruling). Outside the
Geniza only documents whose names point to the movements are listed (the word filter below); the rest belong to their own
project. Everything else is a LEAD.

A BORN-DIGITAL TEXT'S SOURCE (2026-10-15; the editor 11:5x, on Gacond's CDELI history, signed as the born-digital text
`gacond-cdeli-historio-2003` but listed here as a lead, though the editor recalled its having been ruled out of scope; the
same flaw listed Schor's *Bridge of Words* on 13 Oct). Matching a born-digital item by the document's file stem misses every text whose item
name differs from its source file's. So a document is also accounted for (a) if a born-digital spec
(`geniza/ocr/method/born-digital-spec-*.tsv`, its `source` column, parts joined by « + ») names it, or (b) if it is a PDF
whose own text is the text of a spec's source in the SAME folder (the PDF's text extracted beside it, e.g. `gacond.txt`
from `gacond-cdeli-rapport-historique-1954-2003.pdf`): 60% or more of the five-word runs of its first five pages' text
layer found in that source. Reported as «born-digital (by source)».

WRITE-SET: --out only (refuses an existing file). Exit status 1 when there are leads, so a batch start can see it.
"""
import argparse, fnmatch, glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "published", "heterophony-resources")
REG = os.path.join(ROOT, "geniza", "ocr", "method", "CENSUS-LEFT-OUT.tsv")
DOC = re.compile(r"\.(pdf|docx?|djvu|epub)$", re.I)
SKIP = re.compile(r"web-2026-10-08-reu-pbf|page-image-cache|/pages/|/scans/|cupel-batch|ocr-work|/ocr/|\.noindex|/look|/g5|"
                  r"/frames|ocr-rendersearch|ocr-preferred|born-digital-text")
MOVEMENT = re.compile(r"esperant|\bido\b|ido[-_ ]|occident|cosmoglott|kosmoglott|volap|novial|zamenhof|beaufront|couturat|"
                      r"delegat|jespersen|wahl|schleyer|hvorostin|cenzur|privat|drezen|k[uü]nzli|korzhenkov|kor[ĵj]enkov|"
                      r"interhelpo|weltsprache|langue.?internationale|lingvo|sonorilo", re.I)


REPO = os.path.join(HERE, "..")
SPECS = os.path.join(ROOT, "geniza", "ocr", "method", "born-digital-spec-*.tsv")


def _runs(text, n=5):
    w = re.findall(r"[^\W\d_]{2,}", text.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def spec_sources():
    """every born-digital spec's source files, as real paths"""
    out = set()
    for f in glob.glob(SPECS):
        for l in open(f, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) < 2 or x[0] == "item" or l.startswith("#"):
                continue
            for p in x[1].split(" + "):
                p = p.strip()
                if p:
                    out.add(os.path.realpath(os.path.join(REPO, p)))
    return out


def pdf_is_source_text(pdf, srcs_here):
    """the PDF's first pages' text layer found (≥ 60% of its five-word runs) in a spec source in the same folder"""
    if not pdf.lower().endswith(".pdf") or not srcs_here:
        return False
    t = subprocess.run(["pdftotext", "-l", "5", pdf, "-"], capture_output=True, text=True).stdout
    mine = _runs(t)
    if len(mine) < 50:
        return False
    for s in srcs_here:
        try:
            theirs = _runs(open(s, encoding="utf-8", errors="ignore").read())
        except OSError:
            continue
        if len(mine & theirs) >= 0.6 * len(mine):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pdfs", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    listed = {os.path.realpath(l.strip()) for l in open(a.pdfs, encoding="utf-8") if l.strip()}
    names = {os.path.basename(p) for p in listed}
    sys.path.insert(0, HERE); import born_digital_lines as BDL
    bd = set(BDL.lists("proposed"))
    srcs = spec_sources()
    by_dir = {}
    for s in srcs:
        by_dir.setdefault(os.path.dirname(s), []).append(s)
    reg = []
    if os.path.exists(REG):
        for l in open(REG, encoding="utf-8"):
            if l.startswith("#") or not l.strip() or l.startswith("glob\t"):
                continue
            x = l.rstrip("\n").split("\t")
            reg.append((x[0], x[1] if len(x) > 1 else "", x[2] if len(x) > 2 else ""))
    leads, queued, counts = [], [], {"listed": 0, "born-digital": 0, "born-digital (by source)": 0, "left out": 0}
    root = os.path.realpath(ROOT)
    for b in sorted(os.listdir(root)):
        sd = os.path.join(root, b, "sources")
        if not os.path.isdir(sd):
            continue
        for dp, dn, fn in os.walk(sd):
            if SKIP.search(dp + "/"):
                dn[:] = []
                continue
            for f in sorted(fn):
                if not DOC.search(f):
                    continue
                p = os.path.join(dp, f); rel = os.path.relpath(p, root)
                if os.path.realpath(p) in listed or f in names:
                    counts["listed"] += 1; continue
                if os.path.splitext(f)[0] in bd:
                    counts["born-digital"] += 1; continue
                if os.path.realpath(p) in srcs or pdf_is_source_text(p, by_dir.get(os.path.realpath(dp), [])):
                    counts["born-digital (by source)"] += 1; continue
                hit = next((r for g, r, _ in reg if fnmatch.fnmatch(rel, g)), None)
                if hit is not None:
                    if hit.startswith("QUEUED"):
                        queued.append((rel, hit))
                    else:
                        counts["left out"] += 1
                    continue
                if b != "geniza" and not MOVEMENT.search(rel):
                    continue
                leads.append(rel)
    with open(a.out, "x", encoding="utf-8") as fh:
        fh.write("# Holdings census: leads `[generated by tools/ocr-holdings-census.py]`\n\n")
        fh.write(f"Accounted for: {counts['listed']} on the PDF list, {counts['born-digital']} as born-digital texts, "
                 f"{counts['born-digital (by source)']} as the sources of born-digital texts, "
                 f"{counts['left out']} left out on purpose (`geniza/ocr/method/CENSUS-LEFT-OUT.tsv`). **Leads: {len(leads)}.** "
                 "A lead is not a missed source: check it against the ledger and the files before reporting it "
                 "(it may be a copy, a part, or a page check); then either put it on a batch or add it to the register with its "
                 "reason.\n\n")
        for r in leads:
            fh.write(f"- `{r}`\n")
        fh.write(f"\n## Queued, not yet in ({len(queued)})\n\n")
        for r, why in queued:
            fh.write(f"- `{r}`: {why}\n")
    print(f"{len(leads)} leads, {len(queued)} queued; accounted for: " + ", ".join(f"{k} {v}" for k, v in counts.items()) + f" → {a.out}")
    sys.exit(1 if leads else 0)


if __name__ == "__main__":
    main()
