#!/usr/bin/env python3
r"""cupel_workers — how many workers a cupel step may use: the editor's two modes, and the core dial.

    python3 tools/cupel_workers.py <solo|shared> [total|files|jobs]      # prints one number
    python3 tools/cupel_workers.py set <n|solo|shared|off>               # the core dial
    python3 tools/cupel_workers.py now                                   # the dial and the slots in use

On the editor's ruling of 2026-10-14, cupel's parallelisation has two modes: running at the same time as a parallelised
dowse, with 40% of the cores, and running solo, with 80% of the cores. TOTAL = the cores (os.cpu_count) × 0.8 (solo) or × 0.4 (shared), rounded
down, at least 1 (18 cores: solo 14, shared 7). A step that reads several PDFs at once with several page workers each
splits it as FILES × JOBS: FILES = 3 when TOTAL ≥ 6, else 1; JOBS = TOTAL // FILES (solo 3 × 4, shared 3 × 2).
Read by tools/cupel-convert.sh and tools/ocr-chain.sh (their --mode).

THE CORE DIAL (geniza/ocr/method/CORE-DIAL-DESIGN-2026-10-21.md; the editor 2026-10-21 16:5x; Ezri's
answer: one dial for the whole machine, cupel and dowse together). The dial is the file `geniza/ocr/CORE-DIAL` (one
integer; untracked), written by `set`, removed by `set off`. While it exists: the modes no longer halve (both give the
solo numbers: every pool is the maximum), and a worker takes one of the dial's slots before each unit of heavy work and
waits while none is free. The slots are lock files `geniza/ocr/.core-slots/slot-NN`, taken by a non-blocking `flock`
on the first free one below the dial (the dial re-read on every try); the kernel releases a lock when its process
ends, so a crash never leaves a slot held. Up: waiting workers take the new slots within a second. Down: nothing is
killed; work in progress finishes and no new unit starts while the slots in use are at the dial. Where the slot is
taken: `tools/shims/tesseract` and `tools/shims/pdftoppm` (the drivers put `tools/shims` first on PATH, so every
tool's page reading and rendering waits on the dial with no change to the tool), and `slot()` in-process
(`tools/ocr-dowse.py`, whose search runs in Python). No dial file: no slot is taken, and every tool behaves as before.
"""
import contextlib, fcntl, os, sys, time

SHARE = {"solo": 0.8, "shared": 0.4}
HERE = os.path.dirname(os.path.abspath(__file__))
OCR = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "ocr")
DIAL = os.path.join(OCR, "CORE-DIAL")
SLOTS = os.path.join(OCR, ".core-slots")
CORES = os.cpu_count() or 1


def dial():
    """the dial (an int), or None when there is no dial file."""
    try:
        return max(0, min(CORES, int(open(DIAL).read().strip())))
    except (FileNotFoundError, ValueError):
        return None


def total(mode):
    return max(1, int(CORES * SHARE["solo" if dial() is not None else mode]))


def split(mode):
    t = total(mode)
    f = 3 if t >= 6 else 1
    return f, t // f


def take(poll=0.5):
    """block until a slot below the dial is free; its open fd (the lock held), or None when there is no dial file."""
    while True:
        n = dial()
        if n is None:
            return None
        os.makedirs(SLOTS, exist_ok=True)
        for i in range(n):
            fd = os.open(os.path.join(SLOTS, f"slot-{i:02d}"), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                os.close(fd)
        time.sleep(poll)


@contextlib.contextmanager
def slot():
    fd = take()
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)                        # closing the fd releases the lock


def in_use():
    n = 0
    if os.path.isdir(SLOTS):
        for name in sorted(os.listdir(SLOTS)):
            fd = os.open(os.path.join(SLOTS, name), os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                n += 1
            finally:
                os.close(fd)
    return n


def set_dial(v):
    if v == "off":
        if os.path.exists(DIAL):
            os.remove(DIAL)
        return None
    n = int(CORES * SHARE[v]) if v in SHARE else int(v)
    if not 1 <= n <= CORES:
        sys.exit(f"the dial must be 1 to {CORES}")
    tmp = DIAL + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"{n}\n")
    os.replace(tmp, DIAL)                       # a reader never sees a half-written file
    return n


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        n = set_dial(sys.argv[2])
        print("dial off: every tool as before" if n is None else f"dial {n}")
    elif len(sys.argv) >= 2 and sys.argv[1] == "now":
        d = dial()
        print(f"dial {'off' if d is None else d} · slots in use {in_use()} · cores {CORES}")
    elif len(sys.argv) >= 2 and sys.argv[1] in SHARE:
        what = sys.argv[2] if len(sys.argv) > 2 else "total"
        f, j = split(sys.argv[1])
        print({"total": total(sys.argv[1]), "files": f, "jobs": j}[what])
    else:
        sys.exit("usage: cupel_workers.py <solo|shared> [total|files|jobs] | set <n|solo|shared|off> | now")
