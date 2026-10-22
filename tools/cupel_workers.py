#!/usr/bin/env python3
r"""cupel_workers — how many workers a cupel step may use: the editor's two modes.

    python3 tools/cupel_workers.py <solo|shared> [total|files|jobs]      # prints one number

On the editor's ruling of 2026-10-14, cupel's parallelisation has two modes: running at the same time as a parallelised
dowse, with 40% of the cores, and running solo, with 80% of the cores. TOTAL = the cores (os.cpu_count) × 0.8 (solo) or × 0.4 (shared), rounded
down, at least 1 (18 cores: solo 14, shared 7). A step that reads several PDFs at once with several page workers each
splits it as FILES × JOBS: FILES = 3 when TOTAL ≥ 6, else 1; JOBS = TOTAL // FILES (solo 3 × 4, shared 3 × 2).
Read by tools/cupel-convert.sh and tools/ocr-chain.sh (their --mode). Reads nothing, writes nothing.
"""
import os, sys

SHARE = {"solo": 0.8, "shared": 0.4}


def total(mode):
    return max(1, int((os.cpu_count() or 1) * SHARE[mode]))


def split(mode):
    t = total(mode)
    f = 3 if t >= 6 else 1
    return f, t // f


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in SHARE:
        sys.exit("usage: cupel_workers.py <solo|shared> [total|files|jobs]")
    what = sys.argv[2] if len(sys.argv) > 2 else "total"
    f, j = split(sys.argv[1])
    print({"total": total(sys.argv[1]), "files": f, "jobs": j}[what])
