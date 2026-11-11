#!/usr/bin/env python3
"""A test of tools/ocr-index-store.py on a throwaway store (2026-11-07; the editor): the cache and the fold
give the same hits as ocr_index.match, before and after a text changes, across the edge of a shard.

    tools/ocr-index-store-test.py SCRATCH_DIR [--texts N]

Copies the N smallest search texts of 20 KB or more into SCRATCH_DIR/texts, with shards of 2,000 forms, and then:
  1. update, names, check: no disagreement;
  2. one text changed, with new word forms enough to fill the open shard and pass its edge, a near form of a name among them:
     update: the old index gone; the names now short of the new forms; `fold`: no name short, check: no disagreement, the near
     form matched. Before 2026-11-07 a name marked done in a part-full shard was never compared with forms filling it;
  3. --quantum over the pending count: nothing folded, the names still short.
WRITE-SET: SCRATCH_DIR only, which must not exist. Ezri, 2026-11-07."""
import argparse, glob, os, random, shutil, sqlite3, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "ocr-index-store.py")
S = os.path.normpath(os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources"))
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("dir"); ap.add_argument("--texts", type=int, default=6)
a = ap.parse_args()
if os.path.exists(a.dir): sys.exit(f"refusing: {a.dir} exists")
T, ST = os.path.join(a.dir, "texts"), os.path.join(a.dir, "store")
os.makedirs(T)
ENV = dict(os.environ, OCR_STORE_SHARD="2000")


def run(*args, ok=(0,)):
    r = subprocess.run([sys.executable, TOOL, *args, "--store", ST, "--jobs", "4"], capture_output=True, text=True, env=ENV)
    print(f"$ {' '.join(args[:2])}: rc {r.returncode}: " + " | ".join(l[:150] for l in r.stdout.strip().split("\n")[-2:]), flush=True)
    if r.returncode not in ok: sys.exit("FAILED:\n" + r.stdout[-1500:] + r.stderr[-1500:])
    return r.stdout


def say(what, good):
    print(("ok   " if good else "FAIL ") + what, flush=True)
    if not good: sys.exit(1)


big = sorted((f for f in glob.glob(os.path.join(S, "ocr-rendersearch", "*.txt")) if os.path.getsize(f) >= 20_000), key=os.path.getsize)[:a.texts]
files = [shutil.copy(f, T) for f in big]
lst = os.path.join(a.dir, "texts.txt"); open(lst, "w", encoding="utf-8").write("".join(f + "\n" for f in files))
roster = os.path.join(a.dir, "roster.txt")
open(roster, "w", encoding="utf-8").write("Zamenhof\nBoirac\nBeaufront | de Beaufront\nBourlet\nCart\nGrabowski\nMidthus\nSebert\nПривет\nSchneeberger\n")

run("update", "--texts", lst)
run("names", roster)
run("check", roster, "--texts", lst)
c = lambda: sqlite3.connect(os.path.join(ST, "store.sqlite"))
n0 = c().execute("SELECT MAX(id) FROM forms").fetchone()[0]
print(f"{n0:,} word forms, open shard at {n0 % 2000:,} of 2,000", flush=True)
blobs0 = {os.path.join(d, x) for d, _, fs in os.walk(os.path.join(ST, "texts")) for x in fs}

random.seed(7)
new = {"zamenhov"} | {"".join(random.choice("bcdfgklmnprstvz") + random.choice("aeiou") for _ in range(5)) for _ in range(2600)}
txt = open(files[0], encoding="utf-8", errors="replace").read()
open(files[0], "w", encoding="utf-8").write(txt.rstrip() + "\n=== page 99999 ===\n" + " ".join(sorted(new)) + "\n")
run("update", "--texts", lst)
blobs1 = {os.path.join(d, x) for d, _, fs in os.walk(os.path.join(ST, "texts")) for x in fs}
say("the changed text's old index dropped, one new", len(blobs0 - blobs1) == 1 and len(blobs1 - blobs0) == 1)
out = run("check", roster, "--texts", lst, ok=(0, 1))
say("names short of the new forms before the fold", "0 forms short" not in out)
n1 = c().execute("SELECT MAX(id) FROM forms").fetchone()[0]
say("the new forms pass a shard's edge", n1 // 2000 > n0 // 2000)
out = run("fold", "--no-update", "--quantum", str(10 ** 7))
say("the quantum holds a fold back", "not folded" in out)
run("fold", "--no-update")
out = run("check", roster, "--texts", lst)
say("after the fold: no name short, no disagreement", "0 forms short" in out and " 0 disagreements" in out)
m = c().execute("SELECT COUNT(*) FROM matches m JOIN forms o ON o.id = m.form_id WHERE m.f = 'Zamenhof' AND o.form = 'zamenhov'").fetchone()[0]
say("the near form in the new text matched", m == 1)
print("all passed", flush=True)
