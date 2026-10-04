#!/usr/bin/env python3
r"""cupel-merge-verdicts — rebuild a MERGED psm-verdicts file from the base and the batches' own files, in order.

    tools/cupel-merge-verdicts.py <base merged json> <batch json> [<batch json> …] --out <merged json>
    e.g. tools/cupel-merge-verdicts.py $G/ocr/runs/OCR-PSM-VERDICTS-2026-09-30-merged.json \
         $G/ocr/runs/OCR-PSM-VERDICTS-2026-10-03-cupel1-batch.json $G/ocr/runs/OCR-PSM-VERDICTS-2026-10-03-cupel2-batch.json \
         --out $G/ocr/runs/OCR-PSM-VERDICTS-2026-10-03-cupel2-merged.json

WHY (approved by the editor, 2026-10-03 18:2x: merged files are full ~27 MB copies, so from cupel batch 3 on only the base and
each batch's `…-batch.json` are tracked, and merged files are gitignored; an internal review of 2026-10-04, not published, found
that no tool rebuilt a merged file from base + batch files). The merge is plain concatenation, base first, then each batch in the order the
batches ran (as tools/cupel-convert.sh writes it). Checked on 3 Oct: base 115,177 + cupel1 328 + cupel2 2,983 =
cupel2-merged 118,488, identical. Refused: a page judged twice (as cupel-convert.sh refuses it), or an existing --out.
WRITE-SET: --out only.
"""
import os, sys, json, argparse


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base"); ap.add_argument("batches", nargs="+"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    out = json.load(open(a.base, encoding="utf-8")); seen = {v["page"] for v in out}
    for b in a.batches:
        new = json.load(open(b, encoding="utf-8"))
        clash = [v["page"] for v in new if v["page"] in seen]
        if clash:
            sys.exit(f"refusing: {b} judges {len(clash)} page(s) already judged, e.g. {clash[:3]}")
        out += new; seen |= {v["page"] for v in new}
        print(f"  + {os.path.basename(b)}: {len(new)}")
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(out)} verdicts → {a.out}")


if __name__ == "__main__":
    main()
