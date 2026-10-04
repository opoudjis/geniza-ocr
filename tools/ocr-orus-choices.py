#!/usr/bin/env python3
r"""ocr-orus-choices — per item, how the OLD-LETTER RULE chooses between the two Russian readings (reads only).

    tools/ocr-orus-choices.py <root> [--items <stems>|@file]
    e.g. tools/ocr-orus-choices.py <ocr root> --items @<batch>/ITEMS.txt

WHY (2026-10-04, a review of `RUNBOOK.md` found that no tool counts the rule's choices per item; the counts of 3 Oct —
103 Soviet-press pages to `orus` (failure map R1), the 4,171 pages the sharpened rule moved — were made by hand). For each
item with Russian readings: pages with both readings, how many the rule (tools/ocr_russian_reading.py, as it stands)
sends to `orus`, how many to `rus`, and whether the item carries the ORTHOGRAPHY-POST-1918 marker. A batch whose items
send many pages to `orus` and print no pre-reform Russian (by genre: the Soviet press) is a case for the marker, which
only the editor rules; a history, bibliography or dictionary is NOT (the standing requirement that Russian orthography is
decided per page, never by the date of the text, docs/FAILURE-MAP.md).
WRITE-SET: none (prints a table).
"""
import os, re, sys, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_russian_reading as RR


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root"); ap.add_argument("--items")
    a = ap.parse_args()
    want = None
    if a.items:
        want = (set(x.strip() for x in open(a.items[1:], encoding="utf-8") if x.strip()) if a.items.startswith("@")
                else set(a.items.split(",")))
    print("item\tpages with both readings\tto orus\tto rus\tmarker")
    for d in sorted(glob.glob(os.path.join(a.root, "*"))):
        item = os.path.basename(d)
        if want is not None and item not in want or not os.path.isdir(d):
            continue
        both = [f for f in glob.glob(os.path.join(d, "page-*.rus.txt")) if os.path.exists(f.replace(".rus.txt", ".orus.txt"))]
        if not both:
            continue
        orus = sum(1 for f in both if (RR.russian_reading_path(f) or "").endswith(".orus.txt"))
        marker = "yes" if os.path.exists(os.path.join(d, "ORTHOGRAPHY-POST-1918")) else ""
        print(f"{item}\t{len(both)}\t{orus}\t{len(both) - orus}\t{marker}")


if __name__ == "__main__":
    main()
