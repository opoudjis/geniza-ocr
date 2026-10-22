"""ocr_replace_guard — replace a generated table under a FIXED name, git history being its only archive.

The editor ruled on 2026-10-08 that the map file is to be retired rather than appended to: the page map and
the item table keep one name each (ocr/runs/OCR-PAGE-MAP.tsv, geniza/OCR-ITEM-TABLE.tsv), replaced on each run, as the
dowse layout (the dowse runbook, an internal record, not published, D6a) keeps a dowse. Two rules make that safe:

  1. may_replace(): an existing file is replaced only when git tracks it and it has no uncommitted change, so nothing
     is lost that history does not hold. Any other existing file is refused (never write over a file otherwise).
  2. report(): before the new file takes the old one's place, a difference by row key, LOSSES FIRST (a value present
     before and empty, «?» or different now), then changes and gains (the rule after the W fixes: diff for what
     silently disappeared). The caller prints it.
"""
import os, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def may_replace(path):
    """None if `path` may be written (absent, or tracked and clean); else the reason it may not."""
    if not os.path.exists(path):
        return None
    rel = os.path.relpath(os.path.abspath(path), REPO)
    tracked = subprocess.run(["git", "-C", REPO, "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
    if not tracked:
        return f"{rel} exists and is not committed: commit it first (git history is the archive), or choose a new name"
    dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--", rel], capture_output=True, text=True).stdout.strip()
    if dirty:
        return f"{rel} has uncommitted changes: commit them first, so that the version being replaced is in history"
    return None


def _rows(path, key_cols):
    out, head = {}, None
    for l in open(path, encoding="utf-8"):
        if l.startswith("#"): continue
        x = l.rstrip("\n").split("\t")
        if head is None: head = x; continue
        out[tuple(x[head.index(k)] for k in key_cols)] = dict(zip(head, x))
    return out


def report(old_path, new_path, key_cols, cols, empty=("", "?"), show=20):
    """Lines describing what changed from old_path to new_path, losses first."""
    if not os.path.exists(old_path):
        return ["(no earlier version: nothing to compare)"]
    old, new = _rows(old_path, key_cols), _rows(new_path, key_cols)
    lost, changed, gained = [], [], []
    for k in sorted(set(old) | set(new)):
        o, n = old.get(k), new.get(k)
        if o is None: gained.append((k, "(new row)")); continue
        if n is None: lost.append((k, "(row gone)")); continue
        for c in cols:
            a, b = o.get(c, ""), n.get(c, "")
            if a == b: continue
            if a not in empty and b in empty: lost.append((k, f"{c}: «{a}» → «{b}»"))
            elif a in empty: gained.append((k, f"{c}: «{a}» → «{b}»"))
            else: changed.append((k, f"{c}: «{a}» → «{b}»"))
    L = [f"rows {len(old)} → {len(new)}; LOST {len(lost)}, changed {len(changed)}, gained {len(gained)}"]
    for name, xs in (("LOST", lost), ("changed", changed), ("gained", gained)):
        for k, why in xs[:show]:
            L.append(f"  {name}: {' · '.join(k)}: {why}")
        if len(xs) > show: L.append(f"  … {len(xs) - show} more {name}")
    return L
