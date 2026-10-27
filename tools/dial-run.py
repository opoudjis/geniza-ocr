#!/usr/bin/env python3
r"""tools/dial-run.py <command> [args …] — a command run in one slot of the core dial (2026-10-23; the editor).

tools/cupel_workers.py (THE CORE DIAL, Miles, 2026-10-23). The dowse's single-process tools (the assembler, the harvest,
the accuracy and recall preparations) take no slot themselves; run side by side (D6c: `--until 8b` for each source of a
batch at once), they would use cores the dial has given the cupel. Run through this, each waits for a slot while the
dial file exists, and runs at once when it does not. The command is EXECUTED in this process with the slot's lock fd
handed to it, as Miles's shims do for tesseract: the slot is held exactly as long as the command runs. Never wrap a
command that takes slots itself (tools/ocr-dowse.py, the cupel drivers): it would hold one slot while waiting for
another, and at a dial of 1 never get it. Ezri, 2026-10-23.
"""
import os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cupel_workers as CW

if len(sys.argv) < 2: sys.exit(__doc__)
if any(os.path.basename(a) in ("ocr-dowse.py", "cupel-convert.sh", "ocr-chain.sh", "cupel-detach.py") for a in sys.argv[1:3]):
    sys.exit(f"refused: {sys.argv[1:3]} takes slots itself (see the docstring)")
prog = shutil.which(sys.argv[1]) or sys.argv[1]
fd = CW.take()
if fd is not None:
    os.set_inheritable(fd, True)
os.execv(prog, [prog] + sys.argv[2:])
