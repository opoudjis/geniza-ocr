#!/usr/bin/env python3
"""wait-pids — wait until detached runs end, so the session hears of it at once (2026-10-28).

    tools/wait-pids.py --pid-file <batch-dir>/<NAME>.pid [--pid-file …] [--every 5]

WHY (the editor 2026-10-28 14:0x, on C8's slowness): the chain 2026-10-28-cupel19a-2 ended at
13:31 and was not looked at until 14:06, because a run started by tools/cupel-detach.py is detached and nothing tells the
session it has ended. Run this as a background command right after a detach: it returns when every pid has ended, and
that return is the notice. One approved tool, no shell loop (the autopilot rule). Prints one line per run as it ends.
Reads the pid files only; writes nothing.
"""
import os, sys, time, argparse

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--pid-file", action="append", required=True)
ap.add_argument("--every", type=float, default=5.0)
a = ap.parse_args()
live = {}
for f in a.pid_file:
    try:
        live[int(open(f).read().split()[0])] = f
    except Exception as e:
        print(f"no pid in {f}: {e}", flush=True)


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


t0 = time.time()
while live:
    for pid in [p for p in live if not alive(p)]:
        print(f"ended: pid {pid} ({os.path.basename(live.pop(pid))}) after {int(time.time() - t0)} s, at {time.strftime('%H:%M:%S')}", flush=True)
    if live:
        time.sleep(a.every)
print("all ended", flush=True)
