#!/usr/bin/env python3
r"""ocr-tl-kind — the text-layer kind table extended to the pages it does not list: is a page's PDF text layer someone's
OCR over a scan, or born-digital text?

    tools/ocr-tl-kind.py --base <tl-kind.tsv> --pdfs <full list> --root <ocr-rendersearch> --out <new tsv>
                         [--changes <new tsv>] [--jobs 4]
    tools/ocr-tl-kind.py --auto <geniza/sources> --pdfs <full list> --root <ocr-rendersearch> [--jobs 4]

WHY (the editor 2026-11-03 14:1x, on the build queue's item 10). The table
(`sources/ocr-text-layer-2026-09-30/tl-kind.tsv`, made by that folder's one-off `tl-kind.py`) was built once, on
2026-09-30, and nothing extended it: the items added since have no row, so a born-digital page among them never joins
its layer to the search text (`ocr-rebuild-combined.py`: a page whose largest image covers < 50% of it), the small-
capitals selection does not leave it out (`smallcaps-signals.py select`), and the dowse checks its hits against the
image (`ocr-dowse.py born_digital()`).
WHAT: every row of --base, verbatim and first (an old page's kind does not move); then, for every page with a
`page-NNNN.tl.txt` of more than 20 bytes under --root that --base does not list, its PDF's largest image's share of the
page (`pdfinfo` for the page sizes, `pdfimages -list` for the images, masks and stencils left out), as `tl-kind.py`
measured it: ≥ 0.85 «scan-OCR», < 0.15 «born-digital», else «mixed». A page whose PDF is not on --pdfs, or whose
Poppler call fails, gets «no-pdf» or «error» and the share 1.0, so the readers treat its layer as a scan's (out of the
search text) rather than as born-digital. --changes: the new rows the rebuild would read as born-digital (share < 0.5)
whose page's chosen reading (`<root>/<item>/PREFERRED.tsv`) is not the layer: the pages whose search text gains the
layer at the next rebuild once the readers read --out.
NOTHING NEW, NOTHING WRITTEN: where every page with a layer is listed already, it says so and writes no file.
--auto <sources> (the chain's step `tl-kind`, before the rebuild; the editor 2026-11-03): --base is the newest
`<sources>/ocr-text-layer-*/tl-kind.tsv` (sorted by path, as its readers sort it), --out a new
`<sources>/ocr-text-layer-<YYYY-MM-DD>T<HHMMSS>/tl-kind.tsv` (the «T» sorts after a date-only folder of the same day,
whose «/» would otherwise sort after the «-» of a time), --changes `<sources>/ocr-work/tl-kind-<the same stamp>/CHANGES.tsv`.
The chain's `trim` keeps the two newest of these timed folders (each holds every row of the one before it); the dated
folders made by hand (2026-09-30, 2026-11-03) are never removed.
WRITE-SET: --out and --changes, new files (refused if either exists); the table is written as `<out>.part` and renamed
when whole, so a stopped run leaves no table a reader would take. Reads the PDFs, the readings and PREFERRED.tsv.
"""
import argparse, collections, glob, os, re, subprocess, sys, time
import concurrent.futures as fut

TL = re.compile(r"page-(\d+)\.tl\.txt$")


def shares(job):
    item, pdf, pp = job
    if not pdf or not os.path.exists(pdf):
        return item, [(p, "no-pdf", 1.0) for p in pp]
    try:
        info = subprocess.run(["pdfinfo", "-f", "1", "-l", str(max(pp)), pdf], capture_output=True, text=True, timeout=120).stdout
        lst = subprocess.run(["pdfimages", "-list", pdf], capture_output=True, text=True, timeout=300).stdout
    except Exception:
        return item, [(p, "error", 1.0) for p in pp]
    size = {int(m.group(1)): float(m.group(2)) * float(m.group(3))
            for m in re.finditer(r"Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+) pts", info)}
    area = collections.defaultdict(float)
    for l in lst.splitlines()[2:]:
        x = l.split()
        if len(x) < 14 or x[2] != "image":
            continue
        try:
            p, w, h, xp, yp = int(x[0]), int(x[3]), int(x[4]), float(x[12]), float(x[13])
        except ValueError:
            continue
        if xp > 0 and yp > 0:
            area[p] = max(area[p], (w / xp * 72) * (h / yp * 72))
    out = []
    for p in pp:
        a = size.get(p) or size.get(1) or 0
        f = area.get(p, 0) / a if a else 0
        out.append((p, "scan-OCR" if f >= 0.85 else ("born-digital" if f < 0.15 else "mixed"), round(f, 2)))
    return item, out


def chosen_is_layer(root, item, p):
    pf = os.path.join(root, item, "PREFERRED.tsv")
    if not os.path.exists(pf):
        return False
    for l in open(pf, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if x[0] == str(p) and len(x) > 2:
            return ".tl.txt" in x[2] or ".tl-emended.txt" in x[2]
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base"); ap.add_argument("--pdfs", required=True)
    ap.add_argument("--root", required=True); ap.add_argument("--out")
    ap.add_argument("--changes"); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--auto", metavar="SOURCES")
    a = ap.parse_args()
    if a.auto:
        if a.base or a.out or a.changes:
            sys.exit("--auto names --base, --out and --changes itself")
        tables = sorted(glob.glob(os.path.join(a.auto, "ocr-text-layer-*", "tl-kind.tsv")))
        if not tables:
            sys.exit(f"--auto: no ocr-text-layer-*/tl-kind.tsv under {a.auto}")
        stamp = time.strftime("%Y-%m-%dT%H%M%S")
        a.base = tables[-1]
        a.out = os.path.join(a.auto, f"ocr-text-layer-{stamp}", "tl-kind.tsv")
        a.changes = os.path.join(a.auto, "ocr-work", f"tl-kind-{stamp}", "CHANGES.tsv")
        print(f"base {a.base}", file=sys.stderr)
    elif not (a.base and a.out):
        sys.exit("--base and --out, or --auto")
    for f in (a.out, a.out + ".part", a.changes):
        if f and os.path.exists(f):
            sys.exit(f"refused: {f} exists; name a new file")
    base = [l for l in open(a.base, encoding="utf-8") if l.strip()]
    listed = set()
    for l in base:
        x = l.rstrip("\n").split("\t")
        if len(x) >= 2 and x[1].isdigit():
            listed.add((x[0], int(x[1])))
    pdfs = {os.path.splitext(os.path.basename(l.strip()))[0]: l.strip() for l in open(a.pdfs, encoding="utf-8") if l.strip()}
    want = collections.defaultdict(list)
    for item in sorted(os.listdir(a.root)):
        d = os.path.join(a.root, item)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            m = TL.match(f)
            if m and (item, int(m.group(1))) not in listed and os.path.getsize(os.path.join(d, f)) > 20:
                want[item].append(int(m.group(1)))
    print(f"{len(listed):,} pages in the base; {sum(map(len, want.values())):,} pages in {len(want):,} items to measure",
          file=sys.stderr, flush=True)
    if not want:
        print(f"no page to measure: nothing written; {a.base} stands")
        return
    new = []
    with fut.ThreadPoolExecutor(a.jobs) as ex:
        for item, rows in ex.map(shares, [(it, pdfs.get(it), sorted(pp)) for it, pp in sorted(want.items())]):
            new += [(item, p, k, f) for p, k, f in rows]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out + ".part", "x", encoding="utf-8") as w:
        w.writelines(base)
        w.writelines(f"{c}\t{p}\t{k}\t{f}\n" for c, p, k, f in new)
    if os.path.exists(a.out):
        sys.exit(f"refused: {a.out} appeared while measuring; the table is left as {a.out}.part")
    os.rename(a.out + ".part", a.out)
    kinds = collections.Counter(k for _, _, k, _ in new)
    born = [(c, p, f) for c, p, _, f in new if f < 0.5]
    gain = [(c, p, f) for c, p, f in born if not chosen_is_layer(a.root, c, p)]
    print(f"{len(new):,} rows added ({', '.join(f'{k} {v:,}' for k, v in kinds.most_common())}) → {a.out}")
    print(f"born-digital by the rebuild's rule (share < 0.5): {len(born):,} pages in {len({c for c, _, _ in born}):,} items; "
          f"of them, the chosen reading not the layer: {len(gain):,} pages in {len({c for c, _, _ in gain}):,} items")
    if a.changes:
        os.makedirs(os.path.dirname(os.path.abspath(a.changes)), exist_ok=True)
        with open(a.changes, "x", encoding="utf-8") as w:
            w.write("item\tpage\timage share\n")
            w.writelines(f"{c}\t{p}\t{f}\n" for c, p, f in gain)


if __name__ == "__main__":
    main()
