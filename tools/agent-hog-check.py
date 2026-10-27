#!/usr/bin/env python3
r"""agent-hog-check — is a running subagent a token hog? Counts only; reads no images, prints no transcript text.

    tools/agent-hog-check.py                      # every Carney session (all siblings), agents active in the last 120 min
    tools/agent-hog-check.py --since 30           # active in the last 30 min
    tools/agent-hog-check.py --session <dir> --all  # every agent of one session folder (…/projects/<project>/<id>), history

WHY (the editor 2026-10-16). Cupel12's ends look: 5 of 28 image readers of 50 images each went into re-reading loops, up to 2,038
Reads of 51 images and ~300 M cache tokens each (a good reader: 51 Reads, ~4 M), 27% of the weekly quota. The harness
strips old images from a reader's context once enough accumulate; the reader cannot see its early images, re-reads
them, more are stripped: no exit. Diagnosis: `geniza/ocr/runs/VISION-HOG-DIAGNOSIS-2026-10-16.md`. The run sheet's
«Image readers: hard caps» says when to run this: 5 minutes after every image launch and every 10 minutes after.

WHAT IT MEASURES, per subagent transcript (`<session>/subagents/agent-<id>.jsonl`): the Read calls; the distinct paths
read; RE-READS (a second Read of a path already read); the list file named in the brief (the first `*.txt` path in
it) and its length; STRIPS (the context shrinking by more than 5k tokens between turns: the harness dropping images);
the last and largest context; the cache tokens read and written so far; minutes since its last entry.

VERDICTS:
  HOG    a re-read of an image path, or Reads past the list's length + 3, or any strip with images in context:
         stop it now (TaskStop with the id shown).
  WATCH  context over 120k tokens, or Reads within 3 of the list's end with no Write yet.
  ok     none of these.
  done   no entry for 10 minutes or more (finished or dead; listed with --all, or when it ended as a HOG).
Exit status 1 when any active agent is a HOG, else 0.
"""
import argparse, glob, json, os, re, sys, time
from collections import Counter

PROJECTS = os.path.expanduser("~/.claude/projects")
CARNEY = "-Users-nickn-Documents-Arbeit-upwork-ribose-carney"
IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".tif", ".tiff")


def all_sessions():
    """Every Carney session with subagents: a hog in any sibling's session spends the same quota."""
    return [os.path.dirname(d) for d in glob.glob(os.path.join(PROJECTS, CARNEY, "*", "subagents"))]


def measure(path):
    first = None
    reads = 0
    writes = 0
    seen = Counter()
    rereads = 0
    img_reads = 0
    strips = 0
    prev = 0
    last_ctx = max_ctx = 0
    cache_read = cache_write = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        if first is None and d.get("type") == "user":
            c = m.get("content")
            first = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
        if d.get("type") != "assistant":
            continue
        u = m.get("usage") or {}
        ctx = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        if ctx:
            if prev and ctx < prev - 5000:
                strips += 1
            prev = last_ctx = ctx
            max_ctx = max(max_ctx, ctx)
        cache_read += u.get("cache_read_input_tokens", 0)
        cache_write += u.get("cache_creation_input_tokens", 0)
        for c in m.get("content") or []:
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            if c.get("name") == "Write":
                writes += 1
            if c.get("name") == "Read":
                reads += 1
                p = (c.get("input") or {}).get("file_path", "")
                if p.lower().endswith(IMG):
                    img_reads += 1
                    if seen[p]:
                        rereads += 1
                seen[p] += 1
    lst = None
    lst_len = None
    if first:
        mm = re.search(r"(/[^\s'\"`]+?\.txt)", first)
        if mm and os.path.exists(mm.group(1)):
            lst = mm.group(1)
            lst_len = sum(1 for l in open(lst, encoding="utf-8", errors="replace") if l.strip())
    return dict(reads=reads, writes=writes, distinct=len(seen), rereads=rereads, img_reads=img_reads, strips=strips,
                last_ctx=last_ctx, max_ctx=max_ctx, cache_read=cache_read, cache_write=cache_write,
                lst=lst, lst_len=lst_len, brief=(first or "")[:2000])


def verdict(r, idle_min):
    hog = []
    if r["rereads"]:
        hog.append("%d re-reads" % r["rereads"])
    if r["lst_len"] is not None and r["reads"] > r["lst_len"] + 1 + 3:  # +1: the list file itself
        hog.append("Reads %d > list %d + 4" % (r["reads"], r["lst_len"]))
    if r["strips"] and r["img_reads"]:
        hog.append("%d strips" % r["strips"])
    if hog:
        return "HOG", "; ".join(hog)
    watch = []
    if r["max_ctx"] > 120000:
        watch.append("context %dk" % (r["max_ctx"] // 1000))
    if r["lst_len"] is not None and r["reads"] >= r["lst_len"] - 2 and not r["writes"]:
        watch.append("near list end, no Write")
    if watch:
        return "WATCH", "; ".join(watch)
    return "ok", ""


def label(brief):
    for pat in (r"RETURN-(\w[\w.-]*)\.md", r"/([\w.-]+-reader\w+)\.txt", r"WROTE (\w+)"):
        mm = re.search(pat, brief)
        if mm:
            return mm.group(1)
    return "?"


def main():
    ap = argparse.ArgumentParser(description="Flag subagents that are re-reading images (token hogs).")
    ap.add_argument("--session", help="session folder (contains subagents/); default: the newest Carney session")
    ap.add_argument("--since", type=float, default=120, help="only agents with an entry in the last N minutes (default 120)")
    ap.add_argument("--all", action="store_true", help="every agent of the session")
    a = ap.parse_args()
    if a.all and not a.session:
        sys.exit("--all needs --session (one session's history)")
    sessions = [a.session] if a.session else all_sessions()
    files = [f for s in sessions for f in glob.glob(os.path.join(s, "subagents", "agent-*.jsonl"))]
    now = time.time()
    rows = []
    any_hog = False
    for f in sorted(files, key=os.path.getmtime):
        idle = (now - os.path.getmtime(f)) / 60
        if not a.all and idle > a.since:
            continue
        r = measure(f)
        v, why = verdict(r, idle)
        active = idle < 10
        if v == "HOG" and active:
            any_hog = True
        state = v if active else ("done/HOG" if v == "HOG" else "done")
        aid = os.path.basename(f)[len("agent-"):-len(".jsonl")]
        sid = os.path.basename(os.path.dirname(os.path.dirname(f)))[:8]
        rows.append((state, aid, sid + " " + label(r["brief"]), r, why if state != "done" else "", idle))
    print("sessions:", ", ".join(os.path.basename(s)[:8] for s in sessions))
    print("%-10s %-19s %-22s %6s %5s %4s %5s %6s %6s %8s %8s %5s  %s" % (
        "verdict", "agent id", "session label", "reads", "list", "rerd", "strip", "ctx_k", "max_k", "cRead_M", "cWrit_M", "idle", "why"))
    for state, aid, lab, r, why, idle in rows:
        print("%-10s %-19s %-22s %6d %5s %4d %5d %6d %6d %8.1f %8.1f %5.0f  %s" % (
            state, aid, lab[:22], r["reads"], r["lst_len"] if r["lst_len"] is not None else "-", r["rereads"], r["strips"],
            r["last_ctx"] // 1000, r["max_ctx"] // 1000, r["cache_read"] / 1e6, r["cache_write"] / 1e6, idle, why))
    if not rows:
        print("(no agent active in the last %g min)" % a.since)
    if any_hog:
        print("\nHOG: stop the agent(s) above now (TaskStop with the agent id).")
    sys.exit(1 if any_hog else 0)


if __name__ == "__main__":
    main()
