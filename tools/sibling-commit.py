#!/usr/bin/env python3
"""sibling-commit.py — one sibling's commit out of a working tree the siblings share (Miles, 2026-11-10; the editor:
 to a repo tool for it). It stages only the paths a spec names, and
of a shared file only the sibling's own lines, as a blob built from HEAD (git hash-object -w, git update-index
--cacheinfo); the working files are never touched.

    python3 tools/sibling-commit.py plan SPEC.tsv                    (a dry run: stages nothing, prints what it would)
    CLAUDE_APPROVED=yes python3 tools/sibling-commit.py commit SPEC.tsv --message MSG.txt [--running TAG …]
    python3 tools/sibling-commit.py pieces [--running TAG …]         (the dowse runbook step 6 check, alone)

SPEC.tsv, one line a rule, tab-separated, «#» a comment; paths relative to the repo root:
    whole   PATH               the whole file (new or changed)
    list    FILE               every path in FILE, one a line, as «whole» (a list made by a scratch script)
    hunks   PATH   PHRASE      of PATH's `git diff -U0` hunks, the one whose added lines hold PHRASE; several lines for
                               one PATH make one blob. Each PHRASE must pick exactly one hunk.
    rows    PATH   REGEX       a table that only grows: the working file's lines not in HEAD that match REGEX (Python re,
                               searched), added after HEAD's last line in the working file's order; several lines for one
                               PATH join (any match)

Refuses, staging nothing: anything staged already (the index is shared: a sibling's files would go under this message);
a path under sources/, a PDF, the akhnai2 draft; a path missing on disk, or ignored by .gitignore; a path named twice; a
PHRASE that picks no hunk or several; with `commit`, CLAUDE_APPROVED other than «yes» (the editor's go, given by the
caller), no --message, or a reader's piece with no joined return (below). After staging, the staged set must equal the
spec's paths, or it unstages and stops. Never pushes.

A hunk is taken whole: where two siblings' lines touch, `-U0` gives them one hunk and the tool cannot split them; the
plan prints each chosen hunk's first lines, so look at them.

THE PIECES CHECK (the dowse runbook, step 6, «What is committed»; the pieces are gitignored since 2026-11-10): every
untracked `dowse/*/facts-return-‹tag›-N-pN.md` must have its joined `facts-return-‹tag›-N.md` beside it, or that
reading reaches git nowhere. A tag still being read is named with --running and is let through (its pieces are joined at
its filing). `pieces` prints the unjoined pieces by folder and tag and exits 1 if any are not --running.
"""
import argparse, collections, glob, os, re, subprocess, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWSE = "published/heterophony-resources/geniza/dowse/"


def git(*a, inp=None):
    return subprocess.run(["git", "-C", R, *a], capture_output=True, text=True, check=True, input=inp).stdout


def unjoined_pieces(running):
    tracked = set(git("ls-files", "-z", "--", DOWSE).split("\0"))
    out = collections.Counter()
    for f in glob.glob(os.path.join(R, DOWSE, "*", "facts-return-*-p[0-9]*.md")):
        rel = os.path.relpath(f, R)
        m = re.search(r"facts-return-(.+?)-\d+-p\d+\.md$", f)
        if not m or rel in tracked or os.path.exists(re.sub(r"-p\d+\.md$", ".md", f)):
            continue
        if m.group(1) in running:
            continue
        out[(rel.split("/")[-2], m.group(1))] += 1
    return out


def hunks(p):
    """`git diff -U0` hunks of p: [old_start, old_len, added lines]."""
    out, cur = [], None
    for l in git("diff", "-U0", "--", p).split("\n"):
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", l)
        if m:
            cur = [int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1, []]
            out.append(cur)
        elif cur is not None and l.startswith("+") and not l.startswith("+++"):
            cur[2].append(l[1:])
    return out


def head_lines(p):
    return git("show", "HEAD:" + p).split("\n")


def read_spec(path):
    whole, hk, rw = [], collections.OrderedDict(), collections.OrderedDict()
    for n, l in enumerate(open(path, encoding="utf-8"), 1):
        l = l.rstrip("\n")
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        c = l.split("\t")
        if c[0] == "whole" and len(c) == 2:
            whole.append(c[1])
        elif c[0] == "list" and len(c) == 2:
            whole += [x.strip() for x in open(os.path.join(R, c[1]) if not os.path.isabs(c[1]) else c[1], encoding="utf-8") if x.strip()]
        elif c[0] == "hunks" and len(c) == 3:
            hk.setdefault(c[1], []).append(c[2])
        elif c[0] == "rows" and len(c) == 3:
            rw.setdefault(c[1], []).append(c[2])
        else:
            sys.exit(f"{path} line {n}: not a rule («whole PATH», «list FILE», «hunks PATH PHRASE», «rows PATH REGEX»): {l[:100]}")
    return whole, hk, rw


def build(spec):
    whole, hk, rw = read_spec(spec)
    blobs, faults, report = {}, [], []
    every = whole + list(hk) + list(rw)
    dup = [p for p, k in collections.Counter(every).items() if k > 1]
    if dup:
        faults.append(f"named twice: {dup[:5]}")
    for p in every:
        b = p.rsplit("/", 1)[-1]
        if p.startswith("sources/") or "/sources/" in p or p.lower().endswith(".pdf") or "akhnai2" in b:
            faults.append(f"never committed: {p}")
        if not os.path.exists(os.path.join(R, p)):
            faults.append(f"missing on disk: {p}")
    if whole:   # check-ignore exits 1 when none is ignored, so not through git()
        ci = subprocess.run(["git", "-C", R, "check-ignore", "--stdin", "-z"], capture_output=True, text=True, input="\0".join(whole) + "\0")
        if ci.returncode > 1:
            sys.exit("git check-ignore failed: " + ci.stderr[:300])
        ign = [x for x in ci.stdout.split("\0") if x]
        if ign:
            faults.append(f"{len(ign)} ignored by .gitignore (first: {ign[:3]})")
    for p, phrases in hk.items():
        H, hs = head_lines(p), hunks(p)
        chosen = []
        for ph in phrases:
            hit = [h for h in hs if ph in "\n".join(h[2])]
            if len(hit) != 1:
                faults.append(f"{p}: the phrase picks {len(hit)} hunks, not one: {ph[:80]}")
            chosen += [h for h in hit if h not in chosen]
        for start, ln, add in sorted(chosen, key=lambda h: -h[0]):
            at = start if ln == 0 else start - 1         # -U0: an insertion is «after line start»
            H[at:at + ln] = add
        blobs[p] = "\n".join(H)
        report.append(f"hunks {p}: {len(chosen)} of {len(hs)} hunks")
        for start, ln, add in sorted(chosen, key=lambda h: h[0]):
            report.append(f"    @@ HEAD line {start}, -{ln} +{len(add)}: " + (add[0][:110] if add else "(lines removed)"))
    for p, pats in rw.items():
        H = head_lines(p)
        hs = set(H)
        W = open(os.path.join(R, p), encoding="utf-8").read().split("\n")
        mine = [l for l in W if l and l not in hs and any(re.search(x, l) for x in pats)]
        left = [l for l in W if l and l not in hs and l not in mine]
        while H and H[-1] == "":
            H.pop()
        blobs[p] = "\n".join(H + mine + [""])
        report.append(f"rows {p}: {len(mine)} rows taken, {len(left)} new rows left for others")
    return whole, blobs, faults, report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["plan", "commit", "pieces"])
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--message", help="commit: the message file (git commit -F)")
    ap.add_argument("--running", nargs="*", default=[], help="tags still being read: their unjoined pieces let through")
    a = ap.parse_args()
    up = unjoined_pieces(set(a.running))
    if a.action == "pieces":
        for (d, t), n in sorted(up.items()):
            print(f"  {n:5d} unjoined pieces: {d} {t}")
        print("pieces: none unjoined" if not up else f"pieces: {sum(up.values())} unjoined (run the filing, step 6, or name the tag with --running)")
        sys.exit(1 if up else 0)
    if not a.spec:
        sys.exit("give the SPEC.tsv")
    if git("diff", "--cached", "--name-only").strip():
        sys.exit("refusing: something is staged already (the index is shared; a sibling's files would go under this message)")
    whole, blobs, faults, report = build(a.spec)
    print(f"whole files: {len(whole)}")
    for l in report:
        print(l)
    if up:
        msg = f"{sum(up.values())} unjoined pieces outside --running: " + "; ".join(f"{d} {t} ({n})" for (d, t), n in sorted(up.items())[:6])
        (faults.append if a.action == "commit" else print)(msg)
    if faults:
        print("REFUSED:" if a.action == "commit" else "FAULTS (a commit would refuse):")
        for f in faults:
            print("  " + f)
        sys.exit(1)
    if a.action == "plan":
        print("plan: nothing staged")
        return
    if os.environ.get("CLAUDE_APPROVED") != "yes":
        sys.exit("refusing: commit needs CLAUDE_APPROVED=yes from the caller (the editor's go)")
    if not a.message:
        sys.exit("refusing: commit needs --message FILE")
    want = set(whole) | set(blobs)
    try:
        if whole:
            git("add", "--pathspec-from-file=-", "--pathspec-file-nul", inp="\0".join(whole) + "\0")
        for p, text in blobs.items():
            sha = git("hash-object", "-w", "--stdin", inp=text).strip()
            mode = (git("ls-files", "-s", "--", p).split() or ["100644"])[0]
            git("update-index", "--add", "--cacheinfo", f"{mode},{sha},{p}")
        staged = set(git("diff", "--cached", "--name-only", "-z").split("\0")) - {""}
        if staged != want:
            raise RuntimeError(f"staged set differs: not wanted {sorted(staged - want)[:5]}, missing {sorted(want - staged)[:5]}")
    except (subprocess.CalledProcessError, RuntimeError) as e:
        subprocess.run(["git", "-C", R, "reset", "-q", "--pathspec-from-file=-", "--pathspec-file-nul"], input="\0".join(sorted(want)) + "\0", text=True)
        sys.exit(f"REFUSED, unstaged again: {getattr(e, 'stderr', '') or e}")
    r = subprocess.run(["git", "-C", R, "commit", "-F", a.message], capture_output=True, text=True)
    print(r.stdout[-600:], r.stderr[-600:])
    if r.returncode:
        sys.exit(r.returncode)
    print(f"committed {len(want)} paths; not pushed")


if __name__ == "__main__":
    main()
