#!/usr/bin/env python3
r"""corpus_locks — the locks that keep the chain and the dowse apart: one folder both accounts see, `geniza/ocr/locks/`.

    python3 tools/corpus_locks.py take chain -- <the command line>     the chain's lock, or refuse (exit 1)
    python3 tools/corpus_locks.py take dowse -- <the command line>     a dowse's lock, dowse-<pid>.lock, or refuse
    python3 tools/corpus_locks.py release chain|dowse [--pid N]
    python3 tools/corpus_locks.py show
    (in Python: import corpus_locks as CL; CL.take("dowse"); CL.release("dowse"), or `with CL.held("dowse"): …`)

WHY (2026-10-25 23:38: the test chain `2026-10-25-chaintest` started two minutes after Ezri's redowse search, the
editor's of 19:1x taken as still true; the chain's rebuild rewrites the search text in place under
the dowse; it wrote nothing before it was stopped, 00:28; the editor). The specifics are Ezri's (2026-10-26 00:3x): one folder both accounts can see;
`chain.lock` for the chain, `dowse-<pid>.lock` for each dowse, since hers and Picard's run side by side; a lock holds the
pid, the account (CLAUDE_CONFIG_DIR, or «default»), the start time and the command line; a lock whose pid no longer runs
is STALE, said and removed by whoever finds it; REFUSE, NEVER WAIT: each side refuses while the other's lock stands,
saying who holds it and since when. The chain takes `chain` (tools/ocr-chain.sh); the dowse side, `ocr-dowse.py` and
`dowse-brief-fill.py` (which copies the preferred text into the readers' page files), takes `dowse` (Ezri builds it); a
reader batch reads only those page files and takes none.

The order makes it race-safe: a side writes its own lock first (the chain's by exclusive create), then looks for the
other's; if one stands it removes its own and refuses. Two chains: the second fails the exclusive create.
`--pid` (take): the process the lock belongs to, by default the caller's parent (the shell running the chain), so the
lock is stale once that process ends however it ended.
WRITE-SET: `geniza/ocr/locks/chain.lock`, `geniza/ocr/locks/dowse-<pid>.lock`; stale locks of either kind removed.
"""
import contextlib, datetime, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOCKS = os.path.normpath(os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "ocr", "locks"))
OTHER = {"chain": "dowse", "dowse": "chain"}


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:   # another account's process: it runs
        return True
    return True


def _path(kind, pid):
    return os.path.join(LOCKS, "chain.lock" if kind == "chain" else f"dowse-{pid}.lock")


def holders(kind, say=print):
    """The live locks of a kind; stale ones are said and removed."""
    live = []
    for f in sorted(glob.glob(os.path.join(LOCKS, "chain.lock" if kind == "chain" else "dowse-*.lock"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            d = {"pid": 0}
        if d.get("pid") and _alive(int(d["pid"])):
            live.append((f, d))
        else:
            say(f"stale lock removed: {os.path.basename(f)} (pid {d.get('pid')} not running; "
                f"{d.get('account', '?')}, since {d.get('started', '?')}: {d.get('command', '?')})")
            with contextlib.suppress(FileNotFoundError):
                os.remove(f)
    return live


def describe(f, d):
    return f"{os.path.basename(f)}: pid {d['pid']}, account {d.get('account')}, since {d.get('started')}: {d.get('command')}"


def take(kind, command=None, pid=None, say=print):
    """Write the lock, then look for the other side's; refuse (False) if it stands or (chain) a chain holds it."""
    os.makedirs(LOCKS, exist_ok=True)
    pid = pid or os.getpid()
    d = {"pid": pid, "account": os.environ.get("CLAUDE_CONFIG_DIR") or "default",
         "started": datetime.datetime.now().isoformat(timespec="seconds"),
         "command": command or " ".join(sys.argv)}
    if kind == "chain":
        holders("chain", say)                     # a stale chain lock goes first
    f = _path(kind, pid)
    try:
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        live = holders(kind, say)
        say("refusing: " + "; ".join(describe(*x) for x in live) if live else f"refusing: {f} exists")
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    other = holders(OTHER[kind], say)
    if other:
        os.remove(f)
        say(f"refusing to start the {kind}: the {OTHER[kind]} holds the corpus — " + "; ".join(describe(*x) for x in other))
        return False
    return True


def release(kind, pid=None):
    with contextlib.suppress(FileNotFoundError):
        os.remove(_path(kind, pid or os.getpid()))


@contextlib.contextmanager
def held(kind, command=None):
    if not take(kind, command):
        sys.exit(1)
    try:
        yield
    finally:
        release(kind)


if __name__ == "__main__":
    av = sys.argv[1:]
    if not av or av[0] not in ("take", "release", "show"):
        sys.exit(__doc__)
    if av[0] == "show":
        for k in ("chain", "dowse"):
            for f, d in holders(k):
                print(describe(f, d))
        sys.exit(0)
    kind = av[1] if len(av) > 1 else ""
    if kind not in OTHER:
        sys.exit("kind: chain or dowse")
    pid = int(av[av.index("--pid") + 1]) if "--pid" in av else os.getppid()
    if av[0] == "release":
        release(kind, pid); sys.exit(0)
    cmd = " ".join(av[av.index("--") + 1:]) if "--" in av else None
    sys.exit(0 if take(kind, cmd, pid) else 1)
