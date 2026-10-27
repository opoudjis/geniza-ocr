#!/usr/bin/env python3
r"""file-return.py — file a reader's (subagent's) final message verbatim, with a provenance line.

Usage:
    tools/file-return.py --note "Filed by Ezri, ..." agent:a07f40bc74857acee=geniza/profiles/samples/x-lean.md
    tools/file-return.py --note "..." "korzhenkov-historio-2005&&PDF 27=geniza/dowse/korzhenkov-historio-2005/r2.md" ...
    tools/file-return.py --check agent:a07f40bc74857acee=geniza/profiles/samples/x-lean.md

Each argument is SELECTOR=DEST:
    SELECTOR  agent:<id>   the subagent transcript agent-<id>.jsonl (searched in every session of this project);
              any other    strings that must all occur in the reader's first prompt ("a&&b"); exactly one
                           transcript must match, among transcripts written in the last --days days (default 2),
                           or in --session <id> only.
    DEST      the .md file to write; relative to the cwd, or starting "geniza/" for the geniza root.

The file is "# Return: <name>", the --note in backticks (one line, backticks made quotes), then the reader's
final message, unchanged. Refused, each pair on its own (exit 1 if any pair was refused):
    - a reader that has not finished (its last message did not stop with end_turn: interrupted, cut off, running);
    - a reader that got anything after its brief (a message sent to it, «[Request interrupted by user]»):
      its final message may answer that, not the brief; --resumed-ok files it anyway;
    - a final message under 30% of the length of an earlier message of the same reader that is over 1,500
      characters: the report may be the earlier message and the final one a closing line. This can be a false
      alarm (a reader that wrote its report to a file); the editor arbitrates, and --short-ok is passed only on
      his ruling;
    - a DEST that exists, is not under geniza/, is not .md, or whose folder does not exist.
A final message that is the sign-off «Fino: N linioj.» (before 2026-10-15 «Finita»; the reader read geniza/dowse/_FINO.txt after writing its
report) files the reader's previous message instead: the report (2026-10-14).
Write-set: the DEST files only, create-only, opened with "x"; if writing one fails partway, that file (just
created by this call) is removed, so no cut-off return is left. Any error refuses its pair only. Reads only
~/.claude/projects/<this project>/*/subagents/**/agent-*.jsonl (a workflow's agents under workflows/<run id>/),
and DEST with --check.
--check writes nothing: it says whether each DEST still ends with its reader's final message.
"""
import argparse, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent                      # carney/
GENIZA = ROOT / "published" / "heterophony-resources" / "geniza"
# CLAUDE_CONFIG_DIR, where set, names the account whose transcripts are read (2026-10-20: the second account's session
# keeps them under ~/.claude-second)
PROJECT = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects" / str(ROOT).replace("/", "-")
SHORT_RATIO, SHORT_FLOOR = 0.3, 1500
NOT_FOLLOWUPS = ("[Image:", "[SYSTEM NOTIFICATION")                # user records Claude Code inserts by itself
# A WORKFLOW'S READER (P1, 2026-10-17) opens with two harness messages: the user's request relayed, then the task the
# script computed (the brief's prompt). The relayed request is skipped; the computed task is the reader's first prompt.
WF_REQUEST, WF_TASK = "[Workflow harness — user request]", "[Workflow harness — computed task]"
# A READER CUT OFF AT ITS OUTPUT LIMIT (2026-10-15, the De Beaufront episode reader, 264 groups): the harness resumes it
# with «Output token limit hit. Resume directly …», and its report comes in parts. REFUSED (the editor, 08:4x
#): the part is re-run smaller. --cut-ok files
# the parts in order, joined by a marked line, for the record only.
CUTOFF = "Output token limit hit"
CUT_MARK = "\n\n`[the reader's output limit was reached here; it was resumed and continued]`\n\n"
# THE SIGN-OFF (the editor 2026-10-13): a reader writes
# its report as a message, reads geniza/dowse/_FINO.txt, and ends with one line «Finita: N linioj.», so the report
# does not fill the editor's screen. A final message that is that sign-off files the reader's previous message.
SIGNOFF = re.compile(r"^\s*[«\"]?(?:Fino|Finita)\b")   # «Fino» from 2026-10-15 (the editor)


def read_transcript(path):
    """The reader's first prompt, final message and what bears on trusting it. The final message is the last
    API message (its records share one message id); it must have stopped with end_turn (2026-10-12: 627 of
    3,117 transcripts in this project ended unfinished)."""
    t = {"first": None, "body": None, "err": None, "longest_earlier": 0, "followups": [], "prev_body": None, "cut_parts": []}
    last_id, last_stop, texts = None, None, []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg = d.get("message") if isinstance(d, dict) else None
            if not isinstance(msg, dict):                          # malformed record: skip, don't crash
                continue
            content = msg.get("content", [])
            blocks = [x for x in content if isinstance(x, dict)] if isinstance(content, list) else []
            if d.get("type") == "user":
                if isinstance(content, str):
                    text = content
                elif any(x.get("type") == "text" for x in blocks) and not any(
                        x.get("type") == "tool_result" for x in blocks):  # text, possibly with images beside it
                    text = " ".join(str(x.get("text") or "") for x in blocks if x.get("type") == "text")
                else:
                    continue                                       # tool results
                if text.startswith(WF_REQUEST) and t["first"] is None:
                    continue                                       # a workflow's relayed user request: not the brief
                if t["first"] is None or (text.startswith(WF_TASK) and t["first"].startswith(WF_REQUEST)):
                    t["first"] = text
                elif text.startswith(CUTOFF):                      # the harness resumed a reader cut off at its
                    t["cut_parts"].append("".join(texts))          # output limit: the report is in parts
                elif not text.startswith(NOT_FOLLOWUPS):
                    t["followups"].append(" ".join(text.split())[:70])
            elif d.get("type") == "assistant":
                if msg.get("id") != last_id:
                    t["longest_earlier"] = max(t["longest_earlier"], len("".join(texts)))
                    if "".join(texts).strip(): t["prev_body"] = "".join(texts)
                    last_id, last_stop, texts = msg.get("id"), None, []
                texts += [str(x.get("text") or "") for x in blocks if x.get("type") == "text"]
                last_stop = msg.get("stop_reason") or last_stop
    t["first"] = t["first"] or ""
    body = "".join(texts)
    if last_id is None:
        t["err"] = "no reply"
    elif last_stop != "end_turn" and not (last_stop is None and (
            (SIGNOFF.match(body or "") and t["prev_body"])
            # the report and its sign-off in one message (2026-10-17, four of the 225 workflow readers, each complete
            # in the workflow's journal): the sign-off ending the message proves the reader reached its end too
            or re.search(r"\n\s*[«\"]?(?:Fino|Finita): \d+ linioj\.?\s*$", body or ""))):
        # a final sign-off («Fino: N linioj.») recorded without a stop reason (2026-10-15: the harness wrote the last
        # record with stop_reason null for a reader whose completion it had notified) proves the reader reached its end
        t["err"] = f"not finished (last stop_reason: {last_stop})"
    elif not body.strip():
        t["err"] = "final message has no text"
    else:
        t["body"] = CUT_MARK.join(t["cut_parts"] + [body]) if t["cut_parts"] else body
    return t


def transcripts(session, days):
    if session:
        return sorted((PROJECT / session / "subagents").glob("agent-*.jsonl"))
    cutoff = time.time() - days * 86400
    return sorted(p for p in PROJECT.glob("*/subagents/agent-*.jsonl") if p.stat().st_mtime >= cutoff)


def find(selector, session, days):
    """Return (transcript path, transcript dict) or an error string."""
    if selector.startswith("agent:"):
        aid = selector[6:]
        if not re.fullmatch(r"[0-9a-f]{6,40}", aid):              # a plain id, never a glob pattern or a path
            return f"not an agent id: {aid!r}"
        # a workflow's agents are under subagents/workflows/<run id>/ (P1, 2026-10-17): the search goes below subagents/
        hits = [(p, read_transcript(p)) for p in PROJECT.glob(f"*/subagents/**/agent-{aid}.jsonl")]
        if len(hits) != 1:
            return f"{len(hits)} transcripts for {selector}"
    else:
        wanted = selector.split("&&")
        if not all(w.strip() for w in wanted):                     # an empty string would match every transcript
            return f"empty string in selector {selector!r}"
        hits = [(p, t) for p in transcripts(session, days) for t in [read_transcript(p)]
                if all(w in t["first"] for w in wanted)]
        if len(hits) != 1:
            return f"{len(hits)} transcripts match {selector!r}"
    p, t = hits[0]
    return f"{t['err']}: {p.name}" if t["err"] else (p, t)


def dest_path(dest):
    p = (GENIZA / dest[len("geniza/"):]) if dest.startswith("geniza/") else (Path.cwd() / dest)
    p = p.resolve()
    if GENIZA.resolve() not in p.parents:
        return None, f"not under geniza/: {p}"
    if p.suffix != ".md":
        return None, f"not a .md file: {p}"
    return p, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+", metavar="SELECTOR=DEST")
    ap.add_argument("--note", help="provenance line (required unless --check)")
    ap.add_argument("--check", action="store_true", help="compare filed DESTs with their transcripts; write nothing")
    ap.add_argument("--session", help="session id, to limit prompt-string matching to one session")
    ap.add_argument("--days", type=float, default=2, help="prompt-string matching: transcripts written in the last N days")
    ap.add_argument("--resumed-ok", action="store_true", help="file a reader that got messages after its brief")
    ap.add_argument("--cut-ok", action="store_true", help="file a reader cut off at its output limit and resumed, its parts joined (for the record only)")
    ap.add_argument("--short-ok", action="store_true", help="file a short final message (only on the editor's ruling)")
    a = ap.parse_args()
    if not a.check and not a.note:
        ap.error("--note is required when filing")
    if a.session and not re.fullmatch(r"[0-9a-f-]{8,40}", a.session):  # a plain session id, never a path
        ap.error(f"not a session id: {a.session!r}")
    note = " ".join((a.note or "").replace("`", "'").split())      # one line, no backticks: the header stays intact
    refused = 0
    for pair in a.pairs:
        try:                                                       # any error refuses this pair only
            ok = file_pair(pair, a, note)
        except Exception as e:
            print(f"refused, error: {type(e).__name__}: {e}:", pair); ok = False
        refused += not ok
    sys.exit(1 if refused else 0)


def file_pair(pair, a, note):
    """File (or with --check, compare) one SELECTOR=DEST pair; print the outcome; return True if done."""
    if "=" not in pair:
        print("refused, no '=':", pair); return False
    selector, dest = pair.rsplit("=", 1)
    out, err = dest_path(dest)
    if err:
        print("refused,", err); return False
    found = find(selector, a.session, a.days)
    if isinstance(found, str):
        print("refused,", found); return False
    src, t = found
    body = t["body"]
    signed_off = bool(SIGNOFF.match(body or "")) and bool(t["prev_body"])
    if signed_off:                                                 # the report is the message before the sign-off
        body = t["prev_body"]
    if a.check:
        if not out.is_file():
            print("missing", out); return False
        same = out.read_text(encoding="utf-8").strip().endswith(body.strip())
        print("matches" if same else "DIFFERS", out, "<-", src.name)
        return same
    if t["cut_parts"] and not a.cut_ok:
        print(f"refused, cut off at its output limit {len(t['cut_parts'])} time(s) and resumed: re-run the part smaller "
              "(--cut-ok files the parts joined, for the record only):", src.name); return False
    if t["followups"] and not a.resumed_ok:
        print(f"refused, {len(t['followups'])} message(s) after the brief, first: «{t['followups'][0]}»:",
              src.name, "(--resumed-ok to file anyway)"); return False
    if not signed_off and t["longest_earlier"] > SHORT_FLOOR and len(body) < SHORT_RATIO * t["longest_earlier"] and not a.short_ok:
        print(f"refused, final message {len(body)} chars, an earlier one {t['longest_earlier']}: the report may "
              f"be the earlier one; the editor arbitrates (--short-ok on his ruling):", src.name,
              f"\n  final begins: «{' '.join(body.split())[:120]}»"); return False
    if out.exists():
        print("refused, exists:", out); return False
    if not out.parent.is_dir():
        print("refused, no such folder:", out.parent); return False
    fh = open(out, "x", encoding="utf-8")                          # "x": never overwrites, even in a race
    try:
        fh.write(f"# Return: {out.name}\n\n`[{note}]`\n\n" + body.rstrip() + "\n")
        fh.close()
    except BaseException:                                          # a cut-off file is worse than none: remove the
        try:                                                       # file this call itself just created, and re-raise
            fh.close()
        except OSError:
            pass
        out.unlink()
        raise
    print("filed", out, len(body), "chars <-", src.name)
    if out.name.startswith("facts-return-"):
        errs = line_faults(body, *pages_of(out))
        for w in printed_pages(body, *pages_of(out))[:40]: print("  PRINTED PAGE: " + w)
        if errs:
            print(f"  FORMAT: {len(errs)} line(s) the harvest would refuse; re-run the reader, or fix by DECISIONS before assembly:")
            for e in errs[:40]: print("    " + e)
            return False
    return True


# THE FORMAT CHECK AT FILING (2026-10-16 23:5x; the editor
#): a facts reader's return is checked line by line, as it is filed, with the harvest's own parser and
# checks (format 4: the kind field and its list, then the format-3 line through parse() and strict()), so a malformed
# reader shows the moment it is filed, not after every reader of the source is assembled and `harvest-facts.py --check`
# refuses the build. The return is filed all the same (it is the record); the pair counts as refused (exit 1).
# --lines FILE … checks returns already filed, and writes nothing.
_HF = []
def _hf():
    if not _HF:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hf", ROOT / "tools" / "harvest-facts.py")
        m = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]
        try: spec.loader.exec_module(m)
        finally: sys.argv = saved
        _HF.append((m, m.kind_list()))
    return _HF[0]

def pages_of(dest):
    """(the reader's pages file's lines, the item of a source of one text) for a facts return DEST, as the assembler
    finds them (2026-10-18, the lean brief: its «(prese M) l. K» is expanded from them before the check), or (None, "")."""
    import json
    m = re.fullmatch(r"facts-return-(.+)-(\d+)\.md", dest.name)
    pf = dest.parent / f"facts-pages-{m.group(1)}-{m.group(2)}.txt" if m else None
    if not pf or not pf.is_file(): return None, ""
    cfg = dest.parent / "brief-config.json"
    texts = json.loads(cfg.read_text(encoding="utf-8")).get("texts", []) if cfg.is_file() else []
    return pf.read_text(encoding="utf-8").split("\n"), (Path(texts[0]).stem if len(texts) == 1 else "")

def line_faults(body, pages=None, item=""):
    """Every «- $$$» line of a return that the harvest would refuse: [«line N: why · the line's start»]."""
    hf, kinds = _hf(); out = []
    for n, l in enumerate(body.split("\n"), 1):
        if not l.startswith("- $$$"): continue
        l = hf.expand_lean(l, pages, item)        # the lean brief's locator, from the reader's pages file (2026-10-18)
        l3, k = hf.take_kind(hf.form_repair(l))   # the cut brief's two form faults are the assembler's to repair (2026-10-17)
        why = "no kind field «{…}» after the date (facts format 4)" if k is None else hf.kind_problem(k, kinds)
        if not why:
            rec, why = hf.parse(hf.to2(l3))
            if not why: why = hf.strict(rec, True)
        # an anchor under six words is not a fault here: `dowse-anchor-extend.py` lengthens it from the page at D6c step 7
        # (found 2026-10-17, testing --after-readers on Jossinet's returns of 2026-10-15: two such lines, both extended then)
        if why and why.startswith("format 3: the anchor needs six"): SHORT_ANCHORS.append(n); continue
        if why: out.append(f"line {n}: {why} · {l[:90]}")
    return out

SHORT_ANCHORS = []

def printed_pages(body, pages=None, item=""):
    """THE PRINTED PAGE AGAINST THE PDF PAGE (2026-10-18; the editor, to «(prese 99) l. 62» on each line, the
    check that comes with it): warnings, not faults (the harvest has no such rule). Two printed numbers on one PDF page
    are flagged unless consecutive (a scan of two facing pages): a line whose line number is wrong lands on another PDF
    page with its own page's printed number. And a PDF page whose distance from its printed page differs from both its
    numbered neighbours', where those two agree. Not the item's one distance: unnumbered inserts shift it within an issue
    (Amerika Esperantisto 1910 n03, PDF 16 is printed 44 after pages at 24), and a bound-in supplement numbers itself
    (the «Unua Amerika Revuo» at PDF 9, printed 1). Covers and «sen numero» are left out."""
    hf, _k = _hf(); got = []
    for n, l in enumerate(body.split("\n"), 1):
        if not l.startswith("- $$$"): continue
        x = hf.expand_lean(l, pages, item)
        for m in re.finditer(r"([\w.-]+), PDF (\d+) \(prese (\d+)\)", x):
            got.append((n, m.group(1), int(m.group(2)), int(m.group(3)), l[:80]))
    out = []
    from collections import Counter, defaultdict
    by_item = defaultdict(list)
    for g in got: by_item[g[1]].append(g)
    for it, gs in by_item.items():
        per_pdf = defaultdict(list)
        for n, _i, q, p, l in gs: per_pdf[q].append((p, n, l))
        for q, xs in sorted(per_pdf.items()):
            ps = {p for p, _n, _l in xs}
            if len(ps) > 1 and not (len(ps) == 2 and max(ps) - min(ps) == 1):
                major = Counter(p for p, _n, _l in xs).most_common(1)[0][0]
                for p, n, l in xs:
                    if p != major: out.append(f"line {n}: PDF {q} (prese {p}), where the page's other lines say prese {major} · {l}")
        offs = sorted((q, Counter(p for p, _n, _l in xs).most_common(1)[0][0] - q) for q, xs in per_pdf.items())
        for (q0, o0), (q, o), (q2, o2) in zip(offs, offs[1:], offs[2:]):
            if o0 == o2 != o and q - q0 <= 2 and q2 - q <= 2:
                out.append(f"{it}, PDF {q}: printed minus PDF is {o}, its neighbours PDF {q0} and {q2} {o0}")
    return out


# THE TIMES AND TOKENS OF A RUN (2026-10-17; the editor
#): `--timing AGENTS.tsv …` reads each listed reader's transcript and prints its
# start, end and minutes, its API calls, and its tokens (output; fresh input; cache written; cache read), then the
# totals and the wall clock of the batch, from the first start to the last end. The usage is the last record of each
# API message (records of one message share its id). Writes nothing.
def timing(path):
    import datetime
    first = last = None; per = {}; model = ""
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            try: d = json.loads(raw)
            except json.JSONDecodeError: continue
            ts = d.get("timestamp") if isinstance(d, dict) else None
            if ts:
                t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                first = first or t; last = t
            msg = d.get("message") if isinstance(d, dict) else None
            if isinstance(msg, dict) and d.get("type") == "assistant" and isinstance(msg.get("usage"), dict):
                per[msg.get("id")] = msg["usage"]; model = msg.get("model") or model
    s = lambda k: sum(int(u.get(k) or 0) for u in per.values())
    return {"start": first, "end": last, "min": ((last - first).total_seconds() / 60) if first and last else 0,
            "calls": len(per), "out": s("output_tokens"), "in": s("input_tokens"),
            "cw": s("cache_creation_input_tokens"), "cr": s("cache_read_input_tokens"), "model": model}

def timing_report(tsvs):
    rows, seen = [], set()
    for tsv in tsvs:
        if tsv.startswith("prompt:"):   # every reader of the last 4 days whose first prompt holds the string(s) «a&&b»
            wanted = tsv[7:].split("&&")
            for p in transcripts(None, 4):
                tr = read_transcript(p)
                if all(w in tr["first"] for w in wanted):
                    t = timing(p); t["dest"] = tsv[7:][:20] + "…" + p.name[6:14]; rows.append(t)
            continue
        p = (GENIZA / tsv[len("geniza/"):]) if tsv.startswith("geniza/") else Path(tsv)
        for l in p.read_text(encoding="utf-8").split("\n"):
            if not l.strip() or l.startswith("#"): continue
            aid, dest = (l.split("\t") + [""])[:2]
            # a grouped reader has a row per part (2026-10-20): counted once, under its first part
            if aid.strip() in seen: continue
            seen.add(aid.strip())
            hits = list(PROJECT.glob(f"*/subagents/**/agent-{aid.strip()}.jsonl"))
            if len(hits) != 1: print(f"  {aid}: {len(hits)} transcripts"); continue
            t = timing(hits[0]); t["dest"] = Path(dest).name; rows.append(t)
    if not rows: print("no transcripts"); return 1
    print(f"{'return':<34} {'start (UTC)':<9} {'min':>6} {'calls':>5} {'output':>8} {'input':>7} {'cache w':>8} {'cache r':>10}")
    for t in rows:
        print(f"{t['dest'][:34]:<34} {t['start'].strftime('%H:%M:%S'):<9} {t['min']:>6.1f} {t['calls']:>5} {t['out']:>8,} {t['in']:>7,} {t['cw']:>8,} {t['cr']:>10,}")
    tot = lambda k: sum(t[k] for t in rows)
    span = (max(t["end"] for t in rows) - min(t["start"] for t in rows)).total_seconds() / 60
    print(f"{len(rows)} readers ({', '.join(sorted({t['model'] for t in rows}))}); wall clock {span:.1f} min "
          f"(from {min(t['start'] for t in rows).strftime('%Y-%m-%d %H:%M')} UTC); reader-minutes {tot('min'):.1f}; calls {tot('calls')}; "
          f"output {tot('out'):,}; fresh input {tot('in'):,}; cache written {tot('cw'):,}; cache read {tot('cr'):,}")
    # the API price as the stand-in for quota (2026-10-20, the probes of grouped readers): input 1, cache write 1.25,
    # cache read 0.1, output 5, in input-token equivalents
    print(f"weighted (input 1, cache write 1.25, cache read 0.1, output 5): "
          f"{tot('in') + 1.25 * tot('cw') + 0.1 * tot('cr') + 5 * tot('out'):,.0f}")
    return 0


if __name__ == "__main__":
    if "--timing" in sys.argv:
        sys.exit(timing_report(sys.argv[sys.argv.index("--timing") + 1:]))
    if "--lines" in sys.argv:
        bad = 0; TOT = [0, 0, 0, 0]   # returns, faults, printed-page warnings, returns warned
        for f in sys.argv[sys.argv.index("--lines") + 1:]:
            p = (GENIZA / f[len("geniza/"):]) if f.startswith("geniza/") else Path(f)
            SHORT_ANCHORS.clear()
            if "--show" in sys.argv:   # each line as the assembler will take it: expanded and repaired (2026-10-18)
                hf, _k = _hf(); pg, itm = pages_of(p); moved = unfound = n = 0
                for l in p.read_text(encoding="utf-8").split("\n"):
                    if not l.startswith("- $$$"): continue
                    x = hf.form_repair(hf.expand_lean(l, pg, itm)); n += 1
                    moved += "laŭ la ankro⟧" in x; unfound += "la ankro ne troviĝis" in x
                    if "--show-all" in sys.argv or "laŭ la ankro⟧" in x or "la ankro ne troviĝis" in x: print(x)
                print(f"{p.name}: {n} lines; the line number moved by the anchor {moved}; the anchor not found at its line {unfound}")
                continue
            errs = line_faults(p.read_text(encoding="utf-8"), *pages_of(p))
            pw = printed_pages(p.read_text(encoding="utf-8"), *pages_of(p))
            TOT[0] += 1; TOT[1] += len(errs); TOT[2] += len(pw); TOT[3] += bool(pw)
            if "--quiet" in sys.argv and not errs and not pw: continue   # only the files with something to say (2026-10-18)
            print(f"{p.name}: {len(errs)} format fault(s)" + (f"; {len(SHORT_ANCHORS)} short anchor(s), for step 7's extension" if SHORT_ANCHORS else "")
                  + (f"; printed-page warnings {len(pw)}" if pw else ""))
            for e in errs[:40]: print("    " + e)
            for w in pw[:40]: print("    PRINTED PAGE: " + w)
            bad += bool(errs)
        print(f"{TOT[0]} returns: {TOT[1]} format faults in {bad}; {TOT[2]} printed-page warnings in {TOT[3]}")
        sys.exit(1 if bad else 0)
    main()
