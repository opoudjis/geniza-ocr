#!/usr/bin/env python3
"""A workflow's readers, as the agents files the filing tools read (P1, the batch run as one workflow: the editor,
2026-10-17 18:0x,; to Ezri's plan, approved).

    tools/workflow-agents.py <run id> [<run id> …] [--write]     (several runs of one batch: one write)

A workflow labels each reader with the return it is to be filed as, a path under geniza/ («geniza/dowse/<source>/
facts-return-<date>-<N>.md»). This tool reads the run's journal (~/.claude/projects/<this project>/*/subagents/
workflows/<run id>/journal.jsonl: one «started» record per agent, with its id and label) and writes the agents files:
- a facts return «geniza/dowse/<source>/facts-return-<date>-<N>.md» goes to dowse/<source>/agents-<date>.tsv, the file
  `dowse-facts-assemble.py --after-readers <date>` files and takes its «returns» from;
- a grouped reader «…/facts-return-<tag>-gA-B.md» (2026-10-20) goes to agents-<tag>.tsv as one row per part its brief
  facts-brief-<tag>-gA-B.md lists in «La legiloj», each with the same agent id and «group gA-B» in the note;
- any other return goes to agents-<run id>.tsv in its own folder, for `dowse-file-returns.py`.
Each line: «<agent id> TAB <label> TAB workflow <run id>». Agents whose label is not a geniza/ .md path are listed and
skipped. Without --write it prints what it would write. Write-set: those agents files only, create-only (an existing
one refuses the whole run, nothing written). Reads the journal, and a grouped reader's brief. Ezri, 2026-10-17."""
import json, os, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENIZA = ROOT / "published" / "heterophony-resources" / "geniza"
# CLAUDE_CONFIG_DIR, where set, names the account whose runs are read (2026-10-20: the second account's session keeps
# its transcripts under ~/.claude-second; run the tool with CLAUDE_CONFIG_DIR=$HOME/.claude-second for its workflows)
PROJECT = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects" / str(ROOT).replace("/", "-")


CACHE_READ = [0]   # the cache reads, summed apart (2026-10-18: where a large brief re-read at every turn shows)
SPLIT = []         # (output tokens, visible characters, has a thinking block) per message

def split_line():
    """The output's split into visible text and thinking, as a line for the cost report."""
    # A first try calibrated the characters per token on the messages with no thinking block: 1.25, far below any text,
    # so those messages carry thinking too that the transcript does not record (2026-10-18). The split is therefore given
    # as a range, at 2.5 to 3.5 characters a token (Esperanto and English with diacritics, sigils and «»), not as a point
    tot_o = sum(o for o, _v, _t in SPLIT); tot_v = sum(v for _o, v, _t in SPLIT)
    if not tot_o: return "the split: no output"
    lo, hi = min(tot_o, int(tot_v / 3.5)), min(tot_o, int(tot_v / 2.5))
    return (f"the split: visible {tot_v:,} characters ≈ {lo:,}–{hi:,} tokens at 3.5–2.5 a token "
            f"({100 * lo / tot_o:.0f}–{100 * hi / tot_o:.0f}% of the output); thinking the rest, "
            f"{100 - 100 * hi / tot_o:.0f}–{100 - 100 * lo / tot_o:.0f}% (the transcripts keep no thinking text, so a range, not a count)")
def cost(run_dir, only=None):
    """The run's cost from its agents' transcripts (P6, the batch's cost line; 2026-10-18, the dowse fixes): each message
    once (a message's chunks repeat its usage), its input, cache and output tokens summed; the minutes from the run's
    first record to its last. -> (agents, output tokens, all tokens, minutes). The output tokens are exact; «all» (input,
    cache writes and output, cache reads left out) is not the harness's «subagent_tokens», which it does not let a tool
    reproduce (2026-10-18: the dedupe run 84,831 against 73,555, the S3 run 837,326 against 545,565): the main session
    adds the harness's figure from the notification."""
    from datetime import datetime
    out_t = all_t = 0; n = 0; times = []
    for f in sorted(run_dir.glob("agent-*.jsonl")):
        # --agents ID,ID (2026-10-18, the per-reader brief's probe): those agents only, to set the same ranges of two
        # runs side by side
        if only and f.stem[len("agent-"):] not in only: continue
        n += 1; last = {}; blocks = {}
        for raw in open(f, encoding="utf-8"):
            try: d = json.loads(raw)
            except json.JSONDecodeError: continue
            if d.get("timestamp"): times.append(d["timestamp"])
            m = d.get("message") if isinstance(d.get("message"), dict) else None
            if m and m.get("usage"): last[m.get("id")] = m["usage"]   # a message's last record holds its whole output
            if m and m.get("role") == "assistant" and isinstance(m.get("content"), list):
                blocks.setdefault(m.get("id"), []).extend(m["content"])
        # THE THINKING AND THE VISIBLE OUTPUT (2026-10-18; Fable's review: «measure the split»; the editor):
        # the transcripts keep thinking blocks empty (only a signature), so the split is measured, not read: each
        # message's visible characters (its text and its tool calls' input) against its exact output tokens; the
        # messages with no thinking block give the characters per token
        for mid, u in last.items():
            bl = blocks.get(mid, [])
            vis = sum(len(b.get("text", "")) for b in bl if b.get("type") == "text") \
                + sum(len(json.dumps(b.get("input", {}), ensure_ascii=False)) for b in bl if b.get("type") == "tool_use")
            SPLIT.append((u.get("output_tokens", 0), vis, any(b.get("type") == "thinking" for b in bl)))
        for u in last.values():
            # cache reads left out: each turn reads the whole cached context again, and counting them inflates the run
            # five times over (the dedupe reader of 2026-10-18: 377,930 against the harness's 73,555)
            out_t += u.get("output_tokens", 0); CACHE_READ[0] += u.get("cache_read_input_tokens", 0)
            all_t += sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "output_tokens"))
    ts = sorted(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)
    mins = (ts[-1] - ts[0]).total_seconds() / 60 if len(ts) > 1 else 0
    return n, out_t, all_t, mins

def main():
    skip = {sys.argv.index("--agents") + 1} if "--agents" in sys.argv else set()   # the value of --agents
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and i not in skip]
    # SEVERAL RUNS (2026-10-23, Picard's batch of 2026-10-22 in two runs, the check and the rest): their rows go into the
    # same agents files in one write, since the files are create-only and a second call would refuse
    if not args or not all(re.fullmatch(r"wf_[0-9a-z-]{6,}", a) for a in args) or ("--cost" in sys.argv and len(args) != 1):
        sys.exit(__doc__)
    journal = {}
    for run in args:
        journals = list(PROJECT.glob(f"*/subagents/workflows/{run}/journal.jsonl"))
        if len(journals) != 1:
            sys.exit(f"{len(journals)} journals for {run}")
        journal[run] = journals[0]
    if "--cost" in sys.argv:   # reads only
        run = args[0]
        only = set(sys.argv[sys.argv.index("--agents") + 1].split(",")) if "--agents" in sys.argv else None
        n, o, t, mins = cost(journal[run].parent, only)
        print(f"{run}: {n} agents, {o:,} output tokens, {t:,} by the transcripts (not the harness's count), {CACHE_READ[0]:,} cache reads, {mins:.0f} min; " + split_line()); return
    started = {}
    for run in args:
        for raw in open(journal[run], encoding="utf-8"):
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "started" and d.get("agentId"):
                started[d["agentId"]] = (d.get("label") or "", run)
    out, skipped = defaultdict(list), []
    for aid, (label, run) in started.items():
        if not (label.startswith("geniza/") and label.endswith(".md")):
            skipped.append(f"{aid} {label!r}"); continue
        dest = GENIZA / label[len("geniza/"):]
        # A GROUPED READER (2026-10-20; the editor): labelled facts-return-<tag>-gA-B.md, it wrote the returns of
        # the parts its brief lists in «La legiloj»: one row per part, in the batch's own agents file, the same agent id
        g = re.fullmatch(r"facts-return-(.+)-g(\d+)-(\d+)\.md", dest.name)
        if g and dest.parent.parent.name == "dowse":
            bp = dest.parent / f"facts-brief-{g.group(1)}-g{g.group(2)}-{g.group(3)}.md"
            if not bp.exists(): sys.exit(f"refused, nothing written: {os.path.relpath(bp, ROOT)} is missing (a grouped reader's parts are read from its brief)")
            sec = re.split(r"## La leg(?:iloj|antoj)", bp.read_text(encoding="utf-8"), maxsplit=1)[1]   # «legantoj» before 2026-10-22
            ns = re.findall(r"^(\d+): ", sec, flags=re.M)
            if not ns: sys.exit(f"refused, nothing written: no parts in «La legiloj» of {bp.name}")
            for n in ns:
                out[dest.parent / f"agents-{g.group(1)}.tsv"].append(
                    f"{aid}\tgeniza/{os.path.relpath(dest.parent / f'facts-return-{g.group(1)}-{n}.md', GENIZA)}\tworkflow {run}, group g{g.group(2)}-{g.group(3)}")
            continue
        m = re.fullmatch(r"facts-return-(.+)-(\d+)\.md", dest.name)
        tsv = dest.parent / (f"agents-{m.group(1)}.tsv" if m and dest.parent.parent.name == "dowse" else f"agents-{run}.tsv")
        out[tsv].append(f"{aid}\t{label}\tworkflow {run}")
    # A RETURN CLAIMED BY TWO RUNS (2026-10-23, Picard's Lingvo Internacia 1906–1914: the first run's 60 idle legiloj and
    # the relaunch's 60 for the same 180 parts): the later run on the command line wins, its row in the earlier's place
    for p, lines in out.items():
        by = {}
        for l in lines:
            r = l.split("\t")
            by[r[1]] = l if r[1] not in by or args.index(r[2].split()[1].rstrip(",")) >= args.index(by[r[1]].split("\t")[2].split()[1].rstrip(",")) else by[r[1]]
        if len(by) < len(lines):
            print(f"{os.path.relpath(p, ROOT)}: {len(lines) - len(by)} rows of an earlier run replaced by a later run's")
        out[p] = list(by.values())
    exists = [p for p in out if p.exists()]
    if exists:
        sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(p, ROOT) for p in exists))
    for p, lines in sorted(out.items()):
        print(f"{os.path.relpath(p, ROOT)}: {len(lines)} agents")
        if "--write" in sys.argv:
            if not p.parent.is_dir():
                sys.exit(f"refused: no folder {p.parent}")
            with open(p, "x", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
    for s in skipped:
        print(f"  skipped (label not a geniza/ return): {s}")
    if "--write" not in sys.argv:
        print("(dry run: --write to write)")


if __name__ == "__main__":
    main()
