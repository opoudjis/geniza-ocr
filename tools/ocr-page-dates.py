#!/usr/bin/env python3
"""ocr-page-dates.py — the date of the ISSUE each PDF page belongs to, for files that hold several issues across years.

    python3 tools/ocr-page-dates.py --out geniza/ocr/runs/OCR-PAGE-DATES-<date>.tsv

WHY (2026-10-10, 22:05, on the editor's stress tests: the editor agreed that tests 1 and 2 are the priority, the case
of test 1 having occurred often, and then approved this). The dowse and the harvester date a fact by its item (the item table's one year). A file holding several
years puts every fact under one year, and where those years straddle a cutoff (1914/15; 1930/31 for Ido and Occidental)
facts land on the wrong side. A screen of the multi-year items (an internal record, 2026-10-10, not published) found one genuine crossing,
oge.7; the bound volumes of La Belga Sonorilo and The Esperantist's two volumes in one scan need the same.

WHAT. One row per (item, PDF page) that a page-to-issue source dates, from:
- La Belga Sonorilo: the ÖNB bound volumes' pages matched to the per-issue run (tools/ocr-copy-align.py, the newest
  OCR-COPY-ALIGN-*-belga-sonorilo.tsv, rows held in BOTH copies): the issue file's year, number and month; a match outside
  the binding's year − 1 to + 2 is dropped (recurring matter matched to the wrong issue). The run ends Jul 1914: no page
  of it crosses a cutoff, so these dates change the year cited, not the kind.
- The Esperantist: the 26 issue stretches of the scan in the dowse's COPIES table (the page maps): vol. 1 n-roj 1–2 are
  Nov–Dec 1903, n-roj 3–14 1904 (Jan–Dec); vol. 2 n-roj 1–12 are 1905.
- oge.7: the issue starts read in an internal record of 2026-09-15 (not published): n-ro 7-8 (73-74), 25 Dec 1917 – 25 Dec 1918, from PDF
  page 157 (its wrapper); n-ro 9 (75), 25 Oct 1919, from 177; n-ro 10 (76), 25 Jan 1920, from 193 to the end. Pages before
  157 are left to the item's own year (1914).
A page no source dates gets no row: the item's year stands. WRITE-SET: --out only (refuses an existing file).
"""
import argparse, csv, glob, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
MON = {m: i for i, m in enumerate("jan feb mar apr maj jun jul aug sep okt nov dec".split(), 1)}


def belga_sonorilo():
    fs = sorted(glob.glob(os.path.join(G, "ocr", "runs", "OCR-COPY-ALIGN-*-belga-sonorilo.tsv")))
    out = {}
    if not fs:
        return out
    for r in csv.DictReader((l for l in open(fs[-1], encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r["verdict"] != "BOTH" or not r["a_item"]:
            continue
        m = re.match(r"LaBelgaSonorilo_(\d{4})_n(\d+(?:-\d+)?)_([a-z]+)", r["b_item"])
        by = re.match(r"belga[sS]onorilo\.(\d{4})", r["a_item"])
        # a binding holds its own year's volume and the next two at most (two-year bindings, a volume running Sep–Aug):
        # a match outside one year before to two after is recurring matter matched to the wrong issue, and is dropped
        if m and by and not (int(by.group(1)) - 1 <= int(m.group(1)) <= int(by.group(1)) + 2):
            continue
        if m:
            out[(r["a_item"], int(r["a_pdf_page"]))] = (m.group(1), m.group(2), m.group(3),
                                                       f"matched to {r['b_item']} PDF {r['b_pdf_page']} ({os.path.basename(fs[-1])})")
    return out


def the_esperantist():
    spec = importlib.util.spec_from_file_location("d", os.path.join(HERE, "ocr-dowse.py"))
    sys.argv = [sys.argv[0]]; m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    out = {}
    for w in m.COPIES:
        for it, rng, _ in w["copies"]:
            if it == "TheEsperantist.1903-1904.v1" and rng:
                k = re.search(r"pg-\d{4}-(v\d)n(\d+)", w["whole_in"])
                vol, no = k.group(1), int(k.group(2))
                yr = "1905" if vol == "v2" else ("1903" if no <= 2 else "1904")
                for p in range(rng[0], rng[1] + 1):
                    out[(it, p)] = (yr, str(no), "", f"vol. {vol[1]} n-ro {no}: {w['whole_in']}'s stretch in COPIES")
    return out


def oge7():
    starts = [(157, "1917", "7-8", "N-ro 7-8 (73-74), 25 Dec 1917 – 25 Dec 1918"), (177, "1919", "9", "N-ro 9 (75), 25 Oct 1919"),
              (193, "1920", "10", "N-ro 10 (76), 25 Jan 1920")]
    f = os.path.join(G, "sources", "ocr-rendersearch", "oge.7.txt")
    last = max([int(x) for x in re.findall(r"^=== page (\d+) ===", open(f, encoding="utf-8", errors="ignore").read(), re.M)] or [247]) if os.path.exists(f) else 247
    out = {}
    for i, (s, y, n, ev) in enumerate(starts):
        e = starts[i + 1][0] - 1 if i + 1 < len(starts) else last
        for p in range(s, e + 1):
            out[("oge.7", p)] = (y, n, "", f"{ev} (zzz-oge7-1917-1919-2026-09-15.md, from PDF {s})")
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    rows = {}
    for src in (belga_sonorilo(), the_esperantist(), oge7()):
        rows.update(src)
    with open(a.out, "x", encoding="utf-8") as f:
        f.write("# GENERATED by tools/ocr-page-dates.py: the date of the issue a PDF page belongs to, where a page-to-issue source "
                "gives it; the dowse carries it on each hit (page_year, page_issue). A page with no row keeps its item's year.\n")
        f.write("item\tpdf_page\tyear\tissue\tmonth\tsource\n")
        for (it, p), (y, n, mo, ev) in sorted(rows.items()):
            f.write(f"{it}\t{p}\t{y}\t{n}\t{mo}\t{ev}\n")
    import collections
    c = collections.Counter(it for it, _ in rows)
    print(f"{len(rows)} pages dated in {len(c)} items → {a.out}; " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))


if __name__ == "__main__":
    main()
