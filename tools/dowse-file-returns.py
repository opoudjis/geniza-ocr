#!/usr/bin/env python3
"""File a batch of readers' returns with tools/file-return.py (made a tool 2026-10-14, from the stage-1 helper
file_done.sh: a stage runs on approved tools).

    tools/dowse-file-returns.py <agents.tsv> [--note TEXT]

agents.tsv: one reader a line, tab-separated: <agent id> <destination under geniza/> [<note>]. A line starting «#» is
skipped; a destination that exists is skipped (already filed). Prints one line a reader: filed, already there, or why
file-return.py refused (a reader still running, or unfinished: resume it, then file by hand, joined). Ezri, 2026-10-14.

A RETURN WRITTEN IN PIECES (2026-10-20; the editor, after PROBE-2026-10-20rstu.md): a reader briefed by
`dowse-brief-fill.py --write-returns` writes each part's return itself, as pieces facts-return-<tag>-<N>-p1.md,
-p2.md …; where the destination is missing and its piece 1 exists, the pieces are joined into it (in order, a provenance
line at the head) instead of filing from the transcript. Refused: a gap in the pieces' numbers. Write-set: the
destinations only, create-only; the pieces are kept."""
import argparse, glob, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def join_pieces(path, note):
    """-> the line to print, or None when there are no pieces."""
    stem = path[:-3]
    ps = sorted(glob.glob(glob.escape(stem) + "-p*.md"), key=lambda p: int(re.search(r"-p(\d+)\.md$", p).group(1)))
    ps = [p for p in ps if re.search(r"-p\d+\.md$", p)]
    if not ps: return None
    nums = [int(re.search(r"-p(\d+)\.md$", p).group(1)) for p in ps]
    if nums != list(range(1, len(ps) + 1)): return f"refused: the pieces are {nums}, not 1–{len(ps)}"
    texts = [open(p, encoding="utf-8").read().strip("\n") for p in ps]
    lines = sum(1 for t in texts for l in t.split("\n") if l.startswith("- $$$"))
    head = (f"# Return: {os.path.basename(path)}\n\n`[{note.replace('`', '«')}; joined by tools/dowse-file-returns.py from the "
            f"reader's {len(ps)} piece(s), written by it with Write: {', '.join(os.path.basename(p) for p in ps)}]`\n\n")
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(head + "\n\n".join(texts) + "\n")
    return f"joined {len(ps)} piece(s), {lines} lines"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("agents"); ap.add_argument("--note", default="Filed by Ezri")
    a = ap.parse_args()
    for l in open(a.agents, encoding="utf-8"):
        if not l.strip() or l.startswith("#"): continue
        parts = l.rstrip("\n").split("\t")
        aid, dest = parts[0], parts[1]; note = parts[2] if len(parts) > 2 else a.note
        path = os.path.join(G, dest.removeprefix("geniza/"))
        if os.path.exists(path):
            print(f"{dest}: already filed"); continue
        j = join_pieces(path, f"{a.note}; {parts[2]}" if len(parts) > 2 else a.note)
        if j is not None:
            print(f"{dest}: {j}"); continue
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "file-return.py"), "--note", note, f"agent:{aid}={dest}"], capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip().split("\n")
        print(f"{dest}: {out[-1][:200] if out else '(no output)'}")

if __name__ == "__main__":
    main()
