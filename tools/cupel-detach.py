#!/usr/bin/env python3
r"""cupel-detach — start a long cupel run detached from the interactive session, with the Mac kept awake for exactly its life.

    python3 tools/cupel-detach.py --log <batch-dir>/<NAME>.out --pid <batch-dir>/<NAME>.pid -- <command> [args…]

RUNBOOK.md rule 0 (c) (the editor, 2026-10-22 14:1x, identified the issue as the job's lack of persistence and its fragility):
cupel17's driver was a background task of the session and died with it. Here the command runs in a session of its own
(double fork, setsid), stdin from /dev/null, stdout and stderr to --log, under `caffeinate -i -s` (which ends when the
command ends), so a stuck, closed or restarted interactive session cannot kill it. caffeinate hands its process to the
command and keeps a helper of its own asserting on the command's behalf (`pmset -g assertions`: «caffeinate asserting on
behalf of …»), so --pid gets THE COMMAND'S pid: `kill <pid>` stops the run, and the assertion ends with it. Prints the pid
and returns at once. Refuses an existing --log or --pid. Tested 2026-10-22 on 20 pages of cupel17's blocks list: killed
after 6 journaled pages, resumed («6 of 20 already done»), the outputs byte for byte those of an uninterrupted run.
"""
import os, sys, argparse

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--log", required=True); ap.add_argument("--pid", required=True)
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
if not cmd:
    sys.exit("no command")
for p in (a.log, a.pid):
    if os.path.exists(p):
        sys.exit(f"exists: {p}")
r, w = os.pipe()
if os.fork():
    os.close(w); pid = os.read(r, 32).decode().strip(); print(pid); sys.exit(0)
os.close(r); os.setsid()
if os.fork():
    os._exit(0)
fd = os.open(os.devnull, os.O_RDONLY); os.dup2(fd, 0)
lg = os.open(a.log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644); os.dup2(lg, 1); os.dup2(lg, 2)
open(a.pid, "x").write(f"{os.getpid()}\n")
os.write(w, f"{os.getpid()}".encode()); os.close(w)
os.execvp("caffeinate", ["caffeinate", "-i", "-s"] + cmd)
