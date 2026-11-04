#!/usr/bin/env python3
"""The harvest chain: everything after a dowse's readers, for one or more sources at once, as one chained command with a
record of where it stands (2026-10-28; the editor: the harvest chained and sequenced as the dowse is, up to the
assembly, over more than one dowse pass, so that nothing is left half done for the editor to remember).

    tools/harvest-chain.py start NAME TAG SOURCE… [--at STAGE] [--picard]
    tools/harvest-chain.py next NAME [--run RUN_ID] [--picard]
    tools/harvest-chain.py status

The stages, each for every source of the chain, the harvest once at a stage's end (never once a source):
  assemble       each source `dowse-facts-assemble.py SRC --after-readers TAG --until 8b`; the harvest; each source's
                 dedupe brief. → WAIT go: the dedupe, one workflow for all (dowse/chains/NAME-dedupe.json).
  dedupe         after its run (`next --run`): each `--after-dedupe TAG RUN --no-harvest` (the rows, reassembly, the
                 undated list and brief, the accuracy sample and brief); the harvest. → WAIT go: the undated pass and the
                 accuracy check, one workflow (NAME-undated.json).
  undated        after its run: each `--after-undated TAG RUN` (filed, the dates dry-run), `dowse-undated-check.py`.
                 → WAIT Ezri: the checks and the accuracy returns read; the dates written (`dowse-undated.py apply
                 … --write`), step 12's rows in DECISIONS.tsv; then `next`.
  written        each `--after-undated-written TAG --no-harvest` (the page look's brief); the harvest. → WAIT go: the
                 page look, one workflow (NAME-page.json); if no source has a page look, straight on to «done».
  page           after its run: each `--after-undated TAGp RUN`, the check. → WAIT Ezri: the page look's dates written.
  page-written   each `--after-undated-written TAGp --no-harvest`; the vision requests the passes named
                 (`vision-requests-collect.py`); the harvest. → done.
A source given as SOURCE@TAG keeps its own tag (its readers' run of an earlier day, agents-TAG.tsv) in every stage; the
others take the chain's. A source already assembled to 8b at its tag (its after-readers-TAG.log) is reassembled (7e)
instead, on today's tools (2026-11-01; the editor, after the books' chain stopped on the prose books' and the
Poŝkalendaro's own tags).
--at STAGE starts a chain at a later stage, for sources already part-way (their earlier steps done by hand). --picard: the
run was on the second account (its journal under ~/.claude-second). The record: dowse/chains/NAME.json and NAME.log;
`status` writes dowse/chains/STATUS.md, every chain's stage and what it waits on, which the QUEUE's «STARTED, NOT
FINISHED» list points to. Nothing is launched by this tool: a legilo stage stops for the editor's ruling. Ezri."""
import argparse, datetime, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
T = os.path.join(ROOT, "tools")
CH = os.path.join(G, "dowse", "chains")
ASM = os.path.join(T, "dowse-facts-assemble.py")
STAGES = ["assemble", "dedupe", "undated", "written", "page", "page-written", "done"]
WAITS = {"assemble": "go: the dedupe (one workflow, {name}-dedupe.json)",
         "dedupe": "go: the undated pass and the accuracy check (one workflow, {name}-undated.json)",
         "undated": "Ezri: the undated checks and accuracy returns read, the dates written, step 12; then next",
         "written": "go: the page look (one workflow, {name}-page.json)",
         "page": "Ezri: the page look's checks read, its dates written (dowse-undated.py apply SOURCE TAGp[-N] --write); then next",
         "page-written": "", "done": ""}

DRY = False   # --dry-run: each command printed, nothing run, nothing written
def path(name, ext): return os.path.join(CH, f"{name}.{ext}")
def load(name): return json.load(open(path(name, "json"), encoding="utf-8"))
def save(c):
    if DRY: return
    tmp = path(c["name"], "json") + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, path(c["name"], "json"))

def log(c, msg):
    if not DRY:
        with open(path(c["name"], "log"), "a", encoding="utf-8") as fh: fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    print(msg)

def run(c, label, args, picard=False, ok_codes=(0,)):
    if DRY:
        print(f"would run  {label}: {'CLAUDE_CONFIG_DIR=~/.claude-second ' if picard else ''}{' '.join(os.path.relpath(x, ROOT) if x.startswith(ROOT) else x for x in args)}")
        return ""
    env = dict(os.environ)
    if picard: env["CLAUDE_CONFIG_DIR"] = os.path.expanduser("~/.claude-second")
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    with open(path(c["name"], "log"), "a", encoding="utf-8") as fh: fh.write(f"\n## {label}\n$ {' '.join(args)}\n{out}\n")
    last = (out.strip().split("\n") or [""])[-1][:180]
    if p.returncode not in ok_codes:
        log(c, f"STOP {label}: {last}"); c["waits"] = f"Ezri: {label} failed, see {os.path.relpath(path(c['name'], 'log'), ROOT)}"
        save(c); sys.exit(1)
    log(c, f"ok  {label}: {last}")
    return out

NOHV = False   # next --no-harvest: the stage's harvest left to another chain's, one harvest for both (2026-10-28)
def harvest(c):
    """The stage's one harvest, and what follows every harvest (the dowsed list, the items' online locations, the sigla
    page), as the after-modes run them."""
    if NOHV:
        log(c, "the harvest: left to another chain's (next --no-harvest)")
        c.setdefault("harvests", []).append(f"{datetime.datetime.now():%Y-%m-%d %H:%M} {c['stage']}: left to another chain's harvest"); return
    run(c, "the check", [os.path.join(T, "harvest-facts.py"), "--check", "--quiet"])
    out = run(c, "the harvest", [os.path.join(T, "harvest-facts.py"), "--quiet"])
    run(c, "the dowsed list", [os.path.join(T, "dowse-done.py")])
    run(c, "the items' online locations", [os.path.join(T, "online-locations.py"), "--again"], ok_codes=(0, 1))
    run(c, "the sigla page", [os.path.join(T, "sigla-propose.py"), "--page", os.path.join(ROOT, "published", "genizo", "pages", "siglaro.md")], ok_codes=(0, 1))
    miss = next((l for l in out.split("\n") if l.startswith("missing-facts report")), "")
    c.setdefault("harvests", []).append(f"{datetime.datetime.now():%Y-%m-%d %H:%M} {c['stage']}: {miss[:120]}")

def pool(c, kind, files):
    """One workflow's arguments for every source's readers of a kind: dowse/chains/NAME-KIND.json; -> its path or None."""
    readers = []
    for f in files:
        if os.path.exists(f): readers += json.load(open(f, encoding="utf-8")).get("readers", [])
    p = path(f"{c['name']}-{kind}", "json")
    if DRY:
        print(f"would pool the {kind} legiloj of {', '.join(os.path.relpath(f, G) for f in files)} → {os.path.relpath(p, ROOT)}"); return p
    if not readers: return None
    if os.path.exists(p): sys.exit(f"refusing: {os.path.relpath(p, ROOT)} exists")
    json.dump({"readers": readers}, open(p, "x", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(c, f"pooled {len(readers)} legiloj → {os.path.relpath(p, ROOT)}")
    return p

def D(src): return os.path.join(G, "dowse", src)
def has(p): return DRY or os.path.exists(p)   # a dry run shows every source's every step
def tg(c, s): return c.get("tags", {}).get(s, c["tag"])   # a SOURCE@TAG's own tag, else the chain's

def stage_assemble(c):
    """The assembler's own batch form (2026-10-23): each source to 8b, one `--from 9a` (the harvest and what follows it,
    and that source's dedupe brief), `--from 9c` for the others (their dedupe briefs and workflow files)."""
    first, rest = c["sources"][0], c["sources"][1:]
    again = set()   # reassembled at their own tag: their dedupe brief at that tag already written, and asked
    for s in c["sources"]:
        lp = os.path.join(D(s), f"after-readers-{tg(c, s)}.log")
        if os.path.exists(lp) and "\n## 7e, assemble" in open(lp, encoding="utf-8").read():   # to 8b already, at its own tag
            run(c, f"{s}: reassembled (7e; to 8b already at {tg(c, s)})", [ASM, s, "--replace"]); again.add(s)
        else:
            run(c, f"{s}: assembled to 8b", [ASM, s, "--after-readers", tg(c, s), "--until", "8b"])
    out = run(c, f"{first}: the harvest, for all (9a)", [ASM, first, "--after-readers", tg(c, first), "--from", "9a"])
    miss = next((l for l in out.split("\n") if "9b, the harvest" in l), "")
    c.setdefault("harvests", []).append(f"{datetime.datetime.now():%Y-%m-%d %H:%M} assemble: {miss[:120]}")
    for s in rest:
        # (2026-11-01, books-2026-11-01r: the prose books' 9c at their own tag refused, its log there since the chain before)
        if s in again: log(c, f"{s}: the dedupe brief (9c) already written at {tg(c, s)}, its dedupe asked: skipped"); continue
        run(c, f"{s}: the dedupe brief (9c)", [ASM, s, "--after-readers", tg(c, s), "--from", "9c"])
    # a redowse writes no dedupe brief here: the alignment (D6c step 10) comes first, by hand
    c["align"] = [s for s in c["sources"] if s not in again and not has(os.path.join(D(s), f"workflow-dedupe-{tg(c, s)}.json"))]
    if c["align"]: log(c, f"no dedupe workflow (a redowse: the alignment, D6c step 10, first): {', '.join(c['align'])}")
    p = pool(c, "dedupe", [os.path.join(D(s), f"workflow-dedupe-{tg(c, s)}.json") for s in c["sources"] if s not in again])
    c["stage"] = "dedupe" if p else "dedupe-none"

def stage_dedupe(c, rid, picard):
    for s in c["sources"]:
        # a source with no pair to ask had no dedupe reader: its steps from d7 on (the undated list and brief, the
        # accuracy sample) still run (2026-10-29, the 1905 report: d1 found no agents file of its own and stopped)
        own = has(os.path.join(D(s), f"workflow-dedupe-{tg(c, s)}.json"))
        run(c, f"{s}: after the dedupe", [ASM, s, "--after-dedupe", tg(c, s), rid, "--no-harvest"] + ([] if own else ["--from", "d7"]), picard)
    harvest(c)
    c["accuracy_date"] = datetime.date.today().isoformat()
    files = [os.path.join(D(s), f"workflow-{k}-{tg(c, s)}.json") for s in c["sources"] for k in ("undated", "accuracy")]
    p = pool(c, "undated", files)
    c["stage"] = "undated" if p else "written"

def stage_undated(c, rid, picard):
    # the one run's agents files, every source's at once (the per-source modes accept the refusal that follows)
    run(c, "the run's agents files", [os.path.join(T, "workflow-agents.py"), rid, "--write"], picard, ok_codes=(0, 1))
    for s in c["sources"]:
        if has(os.path.join(D(s), f"workflow-accuracy-{tg(c, s)}.json")) and \
           not has(os.path.join(D(s), f"workflow-undated-{tg(c, s)}.json")):   # the accuracy return alone
            run(c, f"{s}: the accuracy return filed", [os.path.join(T, "dowse-file-returns.py"), os.path.join(D(s), f"agents-{rid}.tsv")])
    for s in c["sources"]:
        if has(os.path.join(D(s), f"workflow-undated-{tg(c, s)}.json")):
            run(c, f"{s}: after the undated pass", [ASM, s, "--after-undated", tg(c, s), rid], picard)
            run(c, f"{s}: the undated check", [os.path.join(T, "dowse-undated-check.py"), s, tg(c, s), "--n", "40"])
    c["stage"] = "undated-read"

def prep_page(c, s, kept_tag):
    """An owed page look prepared as --after-undated-written's w4 would: the source's undated list from the build, the
    page brief (split at a reader's cap), its workflow file by the assembler's own undated_workflow()."""
    import importlib.util
    ul = os.path.join(G, "profiles", "build", f"UNDATED-{tg(c, s)}-{s}.tsv")
    if not os.path.exists(ul):
        run(c, f"{s}: the undated list", [os.path.join(T, "harvest-facts.py"), "--check", "--quiet", "--undated", ul])
    # the kept rows re-keyed to the lines' current locators first (2026-10-28: Progreso's keys had gone stale with the
    # reassemblies since its undated pass, 49 of 468 found, so the first chain prepared 40 of the 486 owed page looks)
    run(c, f"{s}: the kept rows re-keyed", [os.path.join(T, "dowse-undated.py"), "rekey", s, "--write"])
    out = run(c, f"{s}: the owed page look's brief", [os.path.join(T, "dowse-undated.py"), "prep", s, f"{tg(c, s)}p", "--page",
                                                    "--kept-tag", kept_tag, "--list", ul, "--split", "80"])
    if DRY: return
    spec = importlib.util.spec_from_file_location("asm", ASM); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    log(c, f"{s}: {m.undated_workflow(s, tg(c, s) + 'p', out, page=True)}")

def stage_written(c, sfx=""):
    # the dates must be written first (`dowse-undated.py apply … --write`): on 2026-10-29 03:5x the page look's stage ran
    # before them, reassembled nothing and harvested for nothing; a source applied has rows of the tag in DECISIONS.tsv
    # or UNDATED-KEPT.tsv
    # (a dry run takes the dates as written: its files do not exist yet, 2026-10-31)
    unwritten = [] if DRY else [s for s in c["sources"] if has(os.path.join(D(s), f"after-undated-{tg(c, s)}{sfx}.log")) and not any(
        has(p) and f"{tg(c, s)}{sfx}" in open(p, encoding="utf-8").read() for p in (os.path.join(D(s), "DECISIONS.tsv"), os.path.join(D(s), "UNDATED-KEPT.tsv")))]
    if unwritten:
        sys.exit("stopped: the dates are not written for " + ", ".join(f"{s} ({tg(c, s)}{sfx})" for s in unwritten) + "; first: tools/dowse-undated.py apply SOURCE TAG[-N] --write, each part")
    for s in c["sources"]:
        tag = f"{tg(c, s)}{sfx}"
        if has(os.path.join(D(s), f"after-undated-{tag}.log")):
            run(c, f"{s}: after the dates written ({tag})", [ASM, s, "--after-undated-written", tag, "--no-harvest"])

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a1 = sp.add_parser("start"); a1.add_argument("name"); a1.add_argument("tag"); a1.add_argument("sources", nargs="+")
    a1.add_argument("--at", choices=STAGES[:-1], default="assemble"); a1.add_argument("--picard", action="store_true")
    a1.add_argument("--kept-tag", help="with --at page: the page looks still owed from the pass of this tag (UNDATED-KEPT's "
                    "tag column, e.g. 2026-10-27q), prepared under the chain's tag + «p»")
    a2 = sp.add_parser("next"); a2.add_argument("name"); a2.add_argument("--run"); a2.add_argument("--picard", action="store_true")
    a2.add_argument("--no-harvest", action="store_true", help="the stage's harvest left to another chain's, so two chains harvest once")
    sp.add_parser("status")
    a3 = sp.add_parser("drop", help="a chain given up, its files left as written (a stale input found after the start)")
    a3.add_argument("name"); a3.add_argument("--why", required=True)
    for p_ in (a1, a2): p_.add_argument("--dry-run", action="store_true", help="print each command; run and write nothing")
    a = ap.parse_args()
    os.makedirs(CH, exist_ok=True)
    if a.cmd == "status": return status()
    if a.cmd == "drop":
        c = load(a.name); c["stage"] = "dropped"; c["waits"] = f"nothing: dropped, {a.why}"
        save(c); log(c, f"chain {a.name} dropped: {a.why}"); return status()
    global DRY, NOHV; DRY = a.dry_run; NOHV = getattr(a, "no_harvest", False)
    if a.cmd == "start":
        if os.path.exists(path(a.name, "json")): sys.exit(f"refusing: chain {a.name} exists")
        c = {"name": a.name, "tag": a.tag, "sources": [s.split("@")[0] for s in a.sources], "stage": a.at, "started": f"{datetime.datetime.now():%Y-%m-%d %H:%M}"}
        own = {s.split("@")[0]: s.split("@", 1)[1] for s in a.sources if "@" in s}
        if own: c["tags"] = own
        if DRY:
            if a.at == "page" and a.kept_tag:
                for s in c["sources"]: prep_page(c, s, a.kept_tag)
            return walk(c)
        save(c); log(c, f"chain {a.name} started at «{a.at}»: tag {a.tag}, {', '.join(a.sources)}")
        if a.at == "assemble": stage_assemble(c)
        else:   # sources part-way: a legilo stage pools the workflow files their after-modes already wrote
            if a.at == "page" and a.kept_tag:   # the page looks owed (UNDATED-KEPT's PAĜO of an earlier pass), prepared here
                for s in c["sources"]: prep_page(c, s, a.kept_tag)
            kinds = {"dedupe": ["dedupe-{t}"], "undated": ["undated-{t}", "accuracy-{t}"], "page": ["undated-{t}p"]}.get(a.at)
            if kinds and not pool(c, a.at, [os.path.join(D(s), "workflow-" + k.format(t=tg(c, s)) + ".json") for s in c["sources"] for k in kinds]):
                sys.exit(f"refusing: no source has workflow-{' or workflow-'.join(kinds)}.json")
            c["stage"] = {"undated": "undated", "dedupe": "dedupe", "page": "page"}.get(a.at, a.at)
    else:
        c = load(a.name); st = c["stage"]
        if st in ("dedupe", "undated", "page") and not a.run: sys.exit(f"the stage «{st}» needs its workflow's run id: next {a.name} --run RUN")
        if st == "dedupe": stage_dedupe(c, a.run, a.picard)
        elif st == "dedupe-none": c["stage"] = "written"
        elif st == "undated": stage_undated(c, a.run, a.picard)
        elif st in ("undated-read", "written"):
            stage_written(c); harvest(c)
            p = pool(c, "page", [os.path.join(D(s), f"workflow-undated-{tg(c, s)}p.json") for s in c["sources"]])
            c["stage"] = "page" if p else "page-written"
            if not p:   # no page look anywhere: the last stage at once
                finish(c)
        elif st == "page":
            for s in c["sources"]:
                if has(os.path.join(D(s), f"workflow-undated-{tg(c, s)}p.json")):
                    run(c, f"{s}: after the page look", [ASM, s, "--after-undated", f"{tg(c, s)}p", a.run], a.picard)
                    run(c, f"{s}: the page look's check", [os.path.join(T, "dowse-undated-check.py"), s, f"{tg(c, s)}p", "--n", "20"])
            c["stage"] = "page-read"
        elif st == "page-read": finish(c)
        elif st == "done": print(f"chain {a.name} is done"); return status()
    st = c["stage"]
    c["waits"] = {"dedupe": WAITS["assemble"], "undated": WAITS["dedupe"], "undated-read": WAITS["undated"],
                  "page": WAITS["written"], "page-read": WAITS["page"], "done": ""}.get(st, "next").format(name=c["name"])
    if c.get("align") and st in ("dedupe", "dedupe-none"):
        c["waits"] += f"; and Ezri: the alignment (D6c step 10) of {', '.join(c['align'])}"
    if DRY: return
    save(c); log(c, f"stage «{st}»; waits: {c['waits'] or 'nothing'}")
    status()

def walk(c):
    """--dry-run with start: every stage's commands in order, the workflows' run ids as RUN."""
    print(f"chain {c['name']} (dry run): tag {c['tag']}, {', '.join(s + ('@' + tg(c, s) if tg(c, s) != c['tag'] else '') for s in c['sources'])}, from «{c['stage']}»")
    def written(): stage_written(c); harvest(c); pool(c, "page", [os.path.join(D(s), f"workflow-undated-{tg(c, s)}p.json") for s in c["sources"]])
    def page():
        for s in c["sources"]: run(c, f"{s}: after the page look", [ASM, s, "--after-undated", f"{tg(c, s)}p", "RUN"])
    steps = [("assemble", "# assemble", lambda: stage_assemble(c)),
             ("dedupe", "# WAIT go: the dedupe workflow\n\n# next --run RUN (the dedupe)", lambda: stage_dedupe(c, "RUN", False)),
             ("undated", "# WAIT go: the undated and accuracy workflow\n\n# next --run RUN (the undated pass)", lambda: stage_undated(c, "RUN", False)),
             ("written", "# WAIT Ezri: the checks read, dates written, step 12\n\n# next (written)", written),
             ("page", "# WAIT go: the page look\n\n# next --run RUN (the page look)", page),
             ("page-written", "# WAIT Ezri: the page look's dates written\n\n# next (finish)", lambda: finish(c))]
    on = False
    for st, head, fn in steps:
        on = on or st == c["stage"]
        if on: print("\n" + head); fn()

def finish(c):
    stage_written(c, "p")
    run(c, "the vision requests", [os.path.join(T, "vision-requests-collect.py")] + [x for t in sorted({tg(c, s) for s in c["sources"]}) for x in ("--kept-tag", t)] + ["--write"]
        + (["--accuracy", c["accuracy_date"]] if c.get("accuracy_date") else []), ok_codes=(0, 1))
    harvest(c)
    c["stage"] = "done"

def status():
    rows = []
    for f in sorted(os.listdir(CH)):
        if not f.endswith(".json") or f.endswith(("-dedupe.json", "-undated.json", "-page.json")): continue   # the pooled args
        try: c = json.load(open(os.path.join(CH, f), encoding="utf-8"))
        except Exception: continue
        if "stage" not in c: continue
        rows.append(f"| {c['name']} | {c['tag']} | {', '.join(s + ('@' + c['tags'][s] if s in c.get('tags', {}) else '') for s in c['sources'])} | {c['stage']} | {c.get('waits') or '—'} | {(c.get('harvests') or ['—'])[-1]} |")
    doc = ["# The harvest chains", "", "`[GENERATED by tools/harvest-chain.py status. Do not hand-edit.]`", "",
           "| chain | tag | sources | stage | waits on | last harvest |", "|---|---|---|---|---|---|"] + (rows or ["| (none) | | | | | |"])
    open(os.path.join(CH, "STATUS.md"), "w", encoding="utf-8").write("\n".join(doc) + "\n")
    print("\n".join(doc[4:]))

if __name__ == "__main__":
    main()
