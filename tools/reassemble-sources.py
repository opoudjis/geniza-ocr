#!/usr/bin/env python3
"""reassemble-sources.py: reassemble several sources' facts files side by side (the editor, 2026-11-07 23:4x). Each source runs `tools/dowse-facts-assemble.py <source> --replace` in its own
process; a source's assembly reads the shared registers and writes only its own files (its facts file, its logs), so
sources do not touch each other (the assembler's --until note). The harvest after it must still run alone.

    python3 tools/reassemble-sources.py SOURCE [SOURCE …] [--jobs N]
    python3 tools/reassemble-sources.py --sinter-tag NOTE [--jobs N]

--sinter-tag NOTE takes every source whose dowse/<source>/DECISIONS.tsv has a row with that note in its last column
(e.g. «sinter-class-d»). --jobs defaults to half the cores (`cupel_workers.total("shared")`), the biggest sources first.
Prints one line a source (return code, seconds, the assembler's count line, its rulings that matched no line) and the
whole time. Writes nothing itself. Ezri, 2026-11-07."""
import argparse, glob, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cupel_workers as CW
ROOT = os.path.dirname(HERE)
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def one(source):
    t = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, "dowse-facts-assemble.py"), source, "--replace"],
                       capture_output=True, text=True, cwd=ROOT)
    out = r.stdout + r.stderr
    head = next((l for l in out.split("\n") if " lines; dropped " in l), (out.strip().split("\n") or [""])[-1])
    unmatched = sum("MATCHED NO LINE" in l for l in out.split("\n"))
    return source, r.returncode, time.time() - t, head.strip()[:110], unmatched, out if r.returncode else ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="*")
    ap.add_argument("--sinter-tag", metavar="NOTE")
    ap.add_argument("--jobs", type=int, default=CW.total("shared"))
    a = ap.parse_args()
    srcs = list(a.sources)
    if a.sinter_tag:
        for p in sorted(glob.glob(os.path.join(G, "dowse", "*", "DECISIONS.tsv"))):
            if any(l.rstrip("\n").split("\t")[-1] == a.sinter_tag for l in open(p, encoding="utf-8")):
                srcs.append(os.path.basename(os.path.dirname(p)))
    srcs = sorted(set(srcs))
    if not srcs: sys.exit("no sources")
    size = lambda s: os.path.getsize(os.path.join(G, "profiles", "by-source", f"{s}-dowse.md")) if os.path.exists(os.path.join(G, "profiles", "by-source", f"{s}-dowse.md")) else 0
    srcs.sort(key=size, reverse=True)        # the biggest first, so the last to finish is a small one
    print(f"{len(srcs)} sources, {a.jobs} at a time", flush=True)
    t0, bad = time.time(), []
    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        for source, code, secs, head, unm, err in ex.map(one, srcs):
            print(f"{source}: rc {code}, {secs:.0f}s, {head}; rulings matching no line {unm}", flush=True)
            if code: bad.append(source); print("   ", err.strip().split("\n")[-1][:300], flush=True)
    print(f"done in {time.time() - t0:.0f}s; failed: {bad or 'none'}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
