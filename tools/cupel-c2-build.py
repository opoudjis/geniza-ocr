#!/usr/bin/env python3
r"""cupel-c2-build — RUNBOOK.md step C2: tools/cupel-images-to-pdf.py once per placed scan, its frames in order.

    python3 tools/cupel-c2-build.py --scans <dir of placed scans> --batch <batch dir> [--overlap <px>] <folder>[=<stem>] …

Folded into tools/ 2026-10-13 (on the editor's approval of folding the recurring scratchpad scripts) from cupel10's
build and overlap scripts (scratch scripts, an internal record, 2026-10-13, not published).
For each <folder> (a placed scan under --scans; <stem> its item name if it differs), every `frame-*` file but the .tsv,
in name order, goes to `tools/cupel-images-to-pdf.py --stem <stem> --look-all` into <batch>/<stem>/ — or, with
--overlap <px> (RUNBOOK.md's overlap cut, for an item whose cut look found TOUCHES or CUTS), with `--overlap <px>`
into <batch>/<stem>-overlap/ (the first build stays). The tool refuses an existing folder. Prints, per item, the tool's
summary line and OK when its frame and page counts check (frames = the folder's; pages = frames + spreads split), else
CHECK. WRITES only what cupel-images-to-pdf.py writes.
"""
import argparse, glob, os, re, subprocess, sys

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cupel-images-to-pdf.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scans", required=True); ap.add_argument("--batch", required=True)
    ap.add_argument("--overlap", type=int, help="the overlap cut, in pixels (cupel10: 80); into <stem>-overlap/")
    ap.add_argument("specs", nargs="+", help="<folder>[=<stem>]")
    a = ap.parse_args()
    for spec in a.specs:
        folder, stem = (spec.split("=") + [None])[:2]
        stem = stem or folder
        frames = sorted(f for f in glob.glob(os.path.join(a.scans, folder, "frame-*")) if not f.endswith(".tsv"))
        if not frames:
            sys.exit(f"no frames in {os.path.join(a.scans, folder)}")
        out = os.path.join(a.batch, stem + ("-overlap" if a.overlap else ""))
        cmd = [sys.executable, TOOL, "--stem", stem, "--out", out]
        if a.overlap:
            cmd += ["--overlap", str(a.overlap)]
        r = subprocess.run(cmd + ["--look-all", *frames], capture_output=True, text=True)
        line = (r.stdout.strip().splitlines() or [r.stderr.strip()])[-1]
        m = re.match(r"(\d+) frames · (\d+) spreads split · (\d+) pages", line)
        ok = m and int(m.group(1)) == len(frames) and int(m.group(3)) == int(m.group(1)) + int(m.group(2))
        print(f"{stem[:46]:<46} | {line[:90]} | {'OK' if ok else 'CHECK'} (folder {len(frames)})", flush=True)


if __name__ == "__main__":
    main()
