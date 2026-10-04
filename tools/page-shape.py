#!/usr/bin/env python3
r"""page-shape — is this page a LIST or is it PROSE? Decided on geometry, never on words.

    tools/page-shape.py 'sources/ocr/esperantista-dokumentaro/*/page-*.txt'
    tools/page-shape.py '<glob>' --list-only            # print just the list-shaped pages
    tools/page-shape.py '<glob>' --tsv pages.tsv --stem-depth 1   # a repass list, ready to run

WHY NON-LEXICAL, WHICH IS THE WHOLE POINT. Three times on 2026-09-24 a lexical measure went
blind on the same class of page, and a roster page is the class:

  · the arbitrator's page gate DECLINED a French roster page — proper names are in no lexicon,
    so there was no «exclusive French» evidence to merge on;
  · a per-page language hybrid found only 2 French pages in 165, because a roster's French is
    surnames and street addresses while its Esperanto rubrics are ordinary words;
  · Kongresa Libro list pages score ~0.73 against a lexicon where prose scores ~0.88 — the
    measure working correctly, and useless for telling damage from a page of surnames.

A page of names defeats every instrument that asks «are these words?». So this one never asks.
It measures the SHAPE of the text — line length, how lines end, digits, capitalisation runs,
commas — all of which survive OCR damage and none of which care what language the page is in.

WHAT IT IS FOR, AND THE ONE THING IT MUST NOT BE USED FOR. It routes pages to `--psm 4`
(tesseract's single-column mode; one Kongresa Libro volume went from 977 page-level errors to 77
on that flag alone) and flags pages where an absence finding is inadmissible. **It does not say a
page is damaged, and it is not a quality measure.** A clean roster and a ruined roster have the
same shape.

THE SIGNALS, and each is a fact about typography rather than language:
  short      median line length — a roster line is a name and a town, not a sentence
  unended    share of lines not ending in . ! ? : ; — list entries do not close
  digits     share of lines containing a digit — street numbers, membership numbers, years
  caps       share of tokens Capitalised or ALLCAPS — surnames, towns
  commas     commas per line — «SURNAME Forename, 4 Rue du Gril, Louviers (Eure)»
Score is the mean of the five, each normalised to 0–1. Calibrate by eye on any new corpus before
trusting the cut: the default of 0.55 was set against the Esperantista Dokumentaro's Nomaro pages
and the prose of the same volumes.
"""
import re, os, sys, glob, argparse, statistics

SENT_END = tuple(".!?:;»")


def shape(text):
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if len(l) > 2]
    if len(lines) < 6:
        return None
    lens = [len(l) for l in lines]
    med = statistics.median(lens)
    toks = re.findall(r"[^\W\d_]+", text, re.UNICODE)
    caps = sum(1 for t in toks if t[:1].isupper())
    sig = {
        # A roster line is short. 60+ characters is a sentence; 25 is «BEAUFRONT L. de, Louviers».
        "short":   max(0.0, min(1.0, (60 - med) / 40)),
        "unended": sum(1 for l in lines if not l.endswith(SENT_END)) / len(lines),
        "digits":  sum(1 for l in lines if re.search(r"\d", l)) / len(lines),
        "caps":    min(1.0, (caps / max(len(toks), 1)) / 0.45),
        "commas":  min(1.0, (text.count(",") / len(lines)) / 2.0),
    }
    sig["score"] = sum(sig.values()) / 5
    sig["lines"] = len(lines)
    sig["median_len"] = med
    return sig


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patterns", nargs="+")
    ap.add_argument("--cut", type=float, default=0.55)
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--tsv", default=None, help="write a repass page list (stem<TAB>pages)")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()

    files = sorted({f for p in a.patterns for f in glob.glob(p)})
    rows = []
    for f in files:
        try:
            s = shape(open(f, encoding="utf-8", errors="ignore").read())
        except OSError:
            continue
        if s:
            rows.append((s["score"], f, s))
    if not rows:
        sys.exit("no scoreable pages (a page needs at least 6 lines)")
    rows.sort(reverse=True)
    lists = [r for r in rows if r[0] >= a.cut]

    print(f"\n{len(rows)} pages scored · {len(lists)} list-shaped at cut {a.cut} "
          f"({100*len(lists)/len(rows):.0f}%)\n")
    print(f"{'score':>6}{'short':>7}{'unend':>7}{'digit':>7}{'caps':>7}{'comma':>7}  page")
    show = lists if a.list_only else rows
    for sc, f, s in show[:a.top]:
        print(f"{sc:>6.2f}{s['short']:>7.2f}{s['unended']:>7.2f}{s['digits']:>7.2f}"
              f"{s['caps']:>7.2f}{s['commas']:>7.2f}  {os.path.relpath(f)}")
    if len(show) > a.top:
        print(f"  … {len(show)-a.top} more; lowest shown-class score {show[-1][0]:.2f}")

    if a.tsv:
        import collections
        per = collections.defaultdict(list)
        for sc, f, s in lists:
            m = re.search(r"page-(\d+)", os.path.basename(f))
            if m:
                per[os.path.basename(os.path.dirname(f))].append(int(m.group(1)))
        with open(a.tsv, "w", encoding="utf-8") as fh:
            for stem in sorted(per):
                fh.write(stem + "\t" + " ".join(str(p) for p in sorted(per[stem])) + "\n")
        print(f"\nwrote {a.tsv} — {len(per)} volumes, {len(lists)} pages, ready for "
              f"tools/ocr-repass-pages.py --psm 4")


if __name__ == "__main__":
    main()
