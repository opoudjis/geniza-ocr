#!/usr/bin/env python3
"""page-cache-prune — the page-image cache folders past their week, listed, then deleted on the editor's word (2026-10-31).

    python3 tools/page-cache-prune.py --report <new .md>                     # lists only
    python3 tools/page-cache-prune.py --report <new .md> --delete [--orphans]  # deletes what the report calls DUE

WHY (run sheet C13: a batch's cached page images go one week after its signature, the editor 2026-10-14; the editor,
2026-10-31 18:2x: the cache had not been cleared back past a week, «OraLibroDeLaEsperantoMovado_1887_kul46892 modified
14 Oct, 2 GB»). C13 put each batch's date in the QUEUE and left the deletion to be remembered; it was not done.
WHAT. Every folder of geniza/sources/page-image-cache.noindex/ is one item's renders, filed as:
  DUE       signed (an ACCEPTED or WITHDRAWN line in a geniza/ocr/lines/*SIGNED* file) 7 or more days ago, by the
            file's date; its PDF on the newest full list exists (a later pass renders again from it);
  WAIT      signed less than 7 days ago, or on the list and not yet signed (a batch running);
  ORPHAN    on no full list (a withdrawn or ruled-out copy, or renders made outside the cupel): deleted only with
            --orphans;
  NO-PDF    signed and due, but its PDF is not on disk: kept, named.
Sizes from the files' bytes. Not the G1 ink cache (geniza/sources/ocr-work/g1-ink-cache.noindex/), never touched.
WRITE-SET: --report (create-only); with --delete, the DUE (and with --orphans the ORPHAN) folders removed, each listed in
the report. Refuses to delete while the chain lock stands (tools/corpus_locks.py).
"""
import argparse, datetime, glob, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
G = os.path.join(REPO, "published", "heterophony-resources", "geniza")
CACHE = os.path.join(G, "sources", "page-image-cache.noindex")
LINE = re.compile(r"^(?:ACCEPTED|WITHDRAWN): (\S+) \|")


def signed_dates():
    out = {}
    for f in glob.glob(os.path.join(G, "ocr", "lines", "*SIGNED*")):
        d = re.search(r"(\d{4}-\d\d-\d\d)", os.path.basename(f))
        if not d: continue
        for l in open(f, encoding="utf-8"):
            m = LINE.match(l)
            if m: out[m[1]] = max(out.get(m[1], ""), d[1])
    return out


def full_list():
    lists = sorted(f for f in glob.glob(os.path.join(G, "sources", "OCR-PDF-LIST-*.txt")) if not f.endswith("-NEW.txt"))
    pdfs = {}
    for l in open(lists[-1], encoding="utf-8"):
        p = l.strip()
        if p: pdfs[os.path.basename(p)[:-4]] = os.path.join(REPO, p)
    return lists[-1], pdfs


def size(d):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--report", required=True)
    ap.add_argument("--delete", action="store_true"); ap.add_argument("--orphans", action="store_true")
    a = ap.parse_args()
    if os.path.exists(a.report): sys.exit(f"{a.report} exists; not overwriting it")
    if a.delete and os.path.exists(os.path.join(G, "ocr", "locks", "chain.lock")): sys.exit("refusing: a chain is running")
    today = datetime.date.today()
    cut = (today - datetime.timedelta(days=7)).isoformat()
    signed, (lst, pdfs) = signed_dates(), full_list()
    rows = []
    for stem in sorted(os.listdir(CACHE)):
        d = os.path.join(CACHE, stem)
        if not os.path.isdir(d): continue
        s = signed.get(stem)
        if s and s <= cut: kind = "DUE" if os.path.exists(pdfs.get(stem, "")) else "NO-PDF"
        elif s or stem in pdfs: kind = "WAIT"
        else: kind = "ORPHAN"
        rows.append((kind, stem, s or "", size(d)))
    go = {"DUE"} | ({"ORPHAN"} if a.orphans else set())
    gib = lambda n: f"{n / 2**30:.1f} GiB"
    L = [f"# Page-image cache: folders past their week ({today})", "",
         f"`tools/page-cache-prune.py`{' --delete' if a.delete else ''}{' --orphans' if a.orphans else ''}; the signed "
         f"lines in `ocr/lines/*SIGNED*`; the full list `{os.path.relpath(lst, G)}`; due = signed on or before {cut}.", ""]
    for k in ("DUE", "ORPHAN", "NO-PDF", "WAIT"):
        rs = [r for r in rows if r[0] == k]
        L.append(f"- **{k}**: {len(rs)} folders, {gib(sum(r[3] for r in rs))}")
    L += ["", "| kind | item | signed | size |", "|---|---|---|---|"]
    L += [f"| {k} | `{stem}` | {s} | {gib(n)} |" for k, stem, s, n in rows if k != "WAIT"]
    if a.delete:
        gone = 0
        for k, stem, s, n in rows:
            if k in go:
                shutil.rmtree(os.path.join(CACHE, stem)); gone += n
        L += ["", f"**Deleted**: the {' and '.join(sorted(go))} folders above, {gib(gone)}."]
    open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(" · ".join(f"{k} {sum(1 for r in rows if r[0] == k)} ({gib(sum(r[3] for r in rows if r[0] == k))})"
                     for k in ("DUE", "ORPHAN", "NO-PDF", "WAIT")) + f" → {a.report}" + (" (deleted)" if a.delete else ""))


if __name__ == "__main__":
    main()
