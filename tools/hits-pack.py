#!/usr/bin/env python3
"""hits-pack.py — the name search's hit tables (dowse/**/*.hits.tsv) gzipped while dormant, and unpacked again for a redowse.

    python3 tools/hits-pack.py pack [--except SOURCE …] [--min-mb N] [--jobs N] [--dry-run]
    python3 tools/hits-pack.py unpack SOURCE [SOURCE …]          (a source folder's packed tables back to .hits.tsv)
    python3 tools/hits-pack.py list                              (packed and unpacked, by folder, with sizes)

WHY (Miles, 2026-11-11; the editor, 224 hit tables 43.5 GiB of it). A hit table is read at
the dowse's steps 2 and 4 (dowse-reader-roster.py, dowse-brief-fill.py) and again only by a redowse of that source
(redowse-pages.py, dowse-recall.py's context). Between those it is dormant; gzip keeps it whole at about a tenth.

pack     every *.hits.tsv under geniza/dowse/ of at least --min-mb (default 10), except the folders named by --except
         (a source whose briefs are still being built), written as <file>.gz beside it and the .tsv removed only once the
         .gz has been read back whole and its size matches; --jobs gzip processes (default half the cores).
unpack   a folder's *.hits.tsv.gz back to *.hits.tsv, the .gz removed once the .tsv is whole. Run before a redowse's prep.
Never touches a file outside geniza/dowse/; the files are gitignored, so nothing here changes git.
"""
import argparse, glob, gzip, os, shutil, sys
from concurrent.futures import ThreadPoolExecutor   # threads: zlib releases the GIL, and the sandbox refuses a process pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "published", "heterophony-resources", "geniza", "dowse")


def gz(path):
    out = path + ".gz"
    if os.path.exists(out):
        return f"SKIP {path}: {out} exists"
    tmp = out + ".part"
    with open(path, "rb") as fi, gzip.open(tmp, "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo, 1 << 22)
    n = 0
    with gzip.open(tmp, "rb") as f:   # read back whole before the original goes
        while True:
            b = f.read(1 << 22)
            if not b: break
            n += len(b)
    if n != os.path.getsize(path):
        os.remove(tmp)
        return f"FAIL {path}: read back {n} bytes, not {os.path.getsize(path)}"
    os.rename(tmp, out)
    before = os.path.getsize(path)
    os.remove(path)
    return f"OK {os.path.relpath(path, D)}: {before / 2**20:.0f} MB → {os.path.getsize(out) / 2**20:.0f} MB"


def gunz(path):
    out = path[:-3]
    if os.path.exists(out):
        return f"SKIP {path}: {out} exists"
    tmp = out + ".part"
    with gzip.open(path, "rb") as fi, open(tmp, "wb") as fo:
        shutil.copyfileobj(fi, fo, 1 << 22)
    os.rename(tmp, out)
    os.remove(path)
    return f"OK {os.path.relpath(out, D)}: {os.path.getsize(out) / 2**20:.0f} MB"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pack"); p.add_argument("--except", dest="exc", nargs="*", default=[])
    p.add_argument("--min-mb", type=float, default=10); p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    p.add_argument("--dry-run", action="store_true")
    u = sp.add_parser("unpack"); u.add_argument("sources", nargs="+")
    sp.add_parser("list")
    a = ap.parse_args()
    if a.cmd == "list":
        for f in sorted(glob.glob(os.path.join(D, "**", "*.hits.tsv*"), recursive=True)):
            print(f"{os.path.getsize(f) / 2**20:9.0f} MB  {os.path.relpath(f, D)}")
        return
    if a.cmd == "unpack":
        fs = [f for s in a.sources for f in glob.glob(os.path.join(D, s, "*.hits.tsv.gz"))]
        if not fs: sys.exit("nothing packed in " + ", ".join(a.sources))
        for f in fs: print(gunz(f), flush=True)
        return
    bad = [s for s in a.exc if not os.path.isdir(os.path.join(D, s))]
    if bad: sys.exit(f"--except names no dowse folder: {bad}")
    fs = [f for f in glob.glob(os.path.join(D, "**", "*.hits.tsv"), recursive=True)
          if os.path.getsize(f) >= a.min_mb * 2**20 and os.path.relpath(f, D).split(os.sep)[0] not in a.exc]
    tot = sum(os.path.getsize(f) for f in fs)
    print(f"{len(fs)} hit tables, {tot / 2**30:.1f} GiB, to pack ({a.jobs} jobs)", flush=True)
    if a.dry_run:
        for f in fs: print("  " + os.path.relpath(f, D))
        return
    with ThreadPoolExecutor(a.jobs) as ex:
        for r in ex.map(gz, sorted(fs, key=os.path.getsize, reverse=True)): print(r, flush=True)


if __name__ == "__main__":
    main()
