#!/usr/bin/env python3
"""vision-requests-status — set «Miles's status» on rows of geniza/ocr/VISION-REQUESTS.tsv (2026-10-28).

    tools/vision-requests-status.py --ids VR-2026-10-28-1..70 [--ids VR-2026-10-28-71 …] --status "<text>" [--write]

WHY (the editor 2026-10-28 11:4x): until now the status column was set with
scratch commands, which raise approval boxes and stop the cupel's autopilot (run sheet, the block at the top; rule 22).
One plain call of an approved tool instead.

WHAT: --ids takes request ids, or a range «VR-<date>-<a>..<b>» (both ends in), and may be given more than once. Every id
must be in the file, or nothing is written. Only the column «Miles's status» of those rows changes; every other column,
row and the header stay byte for byte. Without --write it prints what it would change.

WRITE-SET (with --write only): a backup copy of the file as it was, geniza/ocr/VISION-REQUESTS.tsv.bak-<YYYYMMDD-HHMMSS>
(created new, refused if it exists); then VISION-REQUESTS.tsv rewritten whole through a temporary file in the same
folder and a rename. Nothing else is written, renamed or deleted. Miles."""
import argparse, datetime, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VR = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "ocr", "VISION-REQUESTS.tsv")
COL = "Miles's status"


def expand(spec):
    m = re.fullmatch(r"(VR-\d{4}-\d{2}-\d{2})-(\d+)\.\.(\d+)", spec)
    if m:
        a, b = int(m.group(2)), int(m.group(3))
        return [f"{m.group(1)}-{n}" for n in range(a, b + 1)]
    return [spec]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", action="append", required=True)
    ap.add_argument("--status", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="print each row's change (default: the summary line only)")
    a = ap.parse_args()
    if "\t" in a.status or "\n" in a.status:
        sys.exit("the status may hold no tab or newline")
    ids = [i for s in a.ids for part in s.split(",") for i in expand(part.strip()) if i]
    with open(VR, encoding="utf-8", newline="") as fh:
        lines = fh.read().split("\n")
    head = lines[0].split("\t")
    if COL not in head:
        sys.exit(f"no column «{COL}» in the header")
    c = head.index(COL)
    where = {}
    for k, l in enumerate(lines[1:], 1):
        f = l.split("\t")
        if f and f[0]:
            where[f[0]] = k
    missing = [i for i in ids if i not in where]
    if missing:
        sys.exit(f"not in the file, nothing written: {missing}")
    changed = 0
    for i in ids:
        f = lines[where[i]].split("\t")
        while len(f) <= c:
            f.append("")
        if f[c] != a.status:
            if a.verbose:
                print(f"{i}: «{f[c]}» → «{a.status}»")
            f[c] = a.status; changed += 1
        lines[where[i]] = "\t".join(f)
    if not a.write:
        print(f"{changed} of {len(ids)} rows would change; nothing written (--write to write)")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(open_path := VR + ".bak-" + stamp, "x", encoding="utf-8", newline="") as fh, \
            open(VR, encoding="utf-8", newline="") as old:
        fh.write(old.read())
    tmp = VR + ".tmp-" + stamp
    with open(tmp, "x", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))
    os.replace(tmp, VR)
    print(f"{changed} of {len(ids)} rows changed → {VR} (backup {os.path.basename(open_path)})")


if __name__ == "__main__":
    main()
