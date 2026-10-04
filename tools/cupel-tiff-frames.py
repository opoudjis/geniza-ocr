#!/usr/bin/env python3
"""cupel-tiff-frames — render chosen frames of a multi-page TIFF to PNG, for cupel's C1 look.

    tools/cupel-tiff-frames.py --out <dir> <tiff> <frame> [<frame> …]      frames number from 0

WHY (2026-10-04, the cold dry run of RUNBOOK.md, C1: «no command to view a frame of a multi-page
TIFF, and no kept place for the renders»). C1 looks at a few frames from the start, middle and end of each
placed scan before anything is converted, to see the print and the scripts. Each frame is saved at a
quarter of its size (enough to see the face and the script; the full pages come at C2) as
<out>/<tiff name>-fNNN.png. Prints the TIFF's frame count, so the last TIFF's range is known.
WRITE-SET: those PNGs only; creates <out>; refuses a PNG that exists. Renders are kept (never discarded).
"""
import os, sys, argparse
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("tiff")
ap.add_argument("frames", nargs="+", type=int)
a = ap.parse_args()
im = Image.open(a.tiff)
n_frames = getattr(im, "n_frames", 1)
print(f"{os.path.basename(a.tiff)}: {n_frames} frames")
bad = [n for n in a.frames if not 0 <= n < n_frames]
if bad:
    sys.exit(f"no such frame(s): {bad} (frames 0–{n_frames - 1})")
os.makedirs(a.out, exist_ok=True)
stem = os.path.splitext(os.path.basename(a.tiff))[0]
for n in a.frames:
    dst = os.path.join(a.out, f"{stem}-f{n:03d}.png")
    if os.path.exists(dst):
        sys.exit(f"exists: {dst}")
    im.seek(n)
    f = im.convert("RGB")
    f.resize((max(1, f.width // 4), max(1, f.height // 4))).save(dst)
    print(f"  → {dst}")
