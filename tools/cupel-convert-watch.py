#!/usr/bin/env python3
r"""cupel-convert-watch — PROGRESS.txt for tools/cupel-convert.sh, counted from what is on disk (run sheet rule 0 (b)).
    python3 tools/cupel-convert-watch.py --new <NEW list> --root <$R> --dir <batch-dir> --pid <the driver's pid>
Started by cupel-convert.sh when it is given --dir (the editor 2026-10-22 14:1x). The driver writes the step it is in to `<dir>/STEP`; every 60 s
this rewrites `<dir>/PROGRESS.txt` (step, done of total, rate, expected end, the time of the newest output, running
for) and appends to `<dir>/PROGRESS.log` at each change of step, every 10 minutes, and at a stall: no new output for
10 minutes while the step should be writing (state STALL, for the editor). It counts files, never results:
  convert   pages of the NEW items whose combined `$R/<stem>.txt` exists (ocr-pages.py writes it last, whole)
  psm4      `page-NNNN.psm4.txt` of those items, of their `page-NNNN.txt`
  mask      `page-NNNN.hr.psm4.txt` written (the pages chosen for the re-read are not known in advance: no total)
  textlayer `page-NNNN.tl.txt` written (no total)
  adjudicate, merge: the state only
It exits when STEP says «done», or when the driver's pid is gone (then state ENDED, for the step's log to say why).
WRITES only `<dir>/PROGRESS.txt` (whole, by rename) and `<dir>/PROGRESS.log`. Reads only otherwise.
"""
import argparse, glob, os, re, subprocess, time

STALL = 600


def pages_of(pdf):
    o = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", o, re.M)
    return int(m.group(1)) if m else 0


def stem_of(pdf):
    b = os.path.basename(pdf)
    return b[:-4] if b.lower().endswith(".pdf") else b


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def count(step, stems, total_pages, root):
    """(done, total or None, newest output mtime)"""
    newest, done, total = 0.0, 0, None
    if step == "convert":
        total = sum(total_pages.values())
        for s in stems:
            f = os.path.join(root, s + ".txt")
            if os.path.exists(f):
                done += total_pages[s]; newest = max(newest, os.path.getmtime(f))
        return done, total, newest
    pat = {"psm4": "page-[0-9][0-9][0-9][0-9].psm4.txt", "mask": "page-[0-9][0-9][0-9][0-9].hr.psm4.txt",
           "textlayer": "page-[0-9][0-9][0-9][0-9].tl.txt"}.get(step)
    if not pat:
        return None, None, 0.0
    total = 0 if step == "psm4" else None
    for s in stems:
        d = os.path.join(root, s)
        for f in glob.glob(os.path.join(d, pat)):
            done += 1; newest = max(newest, os.path.getmtime(f))
        if step == "psm4":
            total += len(glob.glob(os.path.join(d, "page-[0-9][0-9][0-9][0-9].txt")))
    return done, total, newest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--new", required=True); ap.add_argument("--root", required=True)
    ap.add_argument("--dir", required=True); ap.add_argument("--pid", type=int, required=True)
    a = ap.parse_args()
    pdfs = [l.strip() for l in open(a.new) if l.strip()]
    stems = [stem_of(p) for p in pdfs]
    total_pages = {stem_of(p): pages_of(p) for p in pdfs}
    prog, log, stepf = (os.path.join(a.dir, n) for n in ("PROGRESS.txt", "PROGRESS.log", "STEP"))
    t0, cur, step_t0, step_done0, last_log, last_new, stalled = time.time(), None, 0.0, 0, 0.0, time.time(), False

    def line(s):
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{cur or '-'}\t{s}\n")

    while True:
        step = open(stepf).read().strip() if os.path.exists(stepf) else "starting"
        now = time.time()
        done, total, newest = count(step, stems, total_pages, a.root)
        if step != cur:
            cur, step_t0, step_done0, last_new, stalled = step, now, done or 0, now, False
            line(f"step begins · {done if done is not None else '-'} of {total if total is not None else '?'} already on disk")
        if newest and newest > last_new:
            last_new, stalled = newest, False
        writing = step in ("convert", "psm4", "mask", "textlayer")
        state = "running"
        if step == "done":
            state = "done"
        elif not alive(a.pid):
            state = "ENDED (the driver is gone: see its log)"
        elif writing and now - last_new > STALL:
            state = f"STALL (no new output for {int((now - last_new) // 60)} min)"
            if not stalled:
                line(state); stalled = True
        new = (done or 0) - step_done0
        rate = new / (now - step_t0) * 60 if new > 0 and now > step_t0 else 0.0
        eta = (time.strftime("%H:%M", time.localtime(now + (total - done) / rate * 60))
               if rate and total is not None and total > done else "?")
        text = (f"step\t{step}\nstate\t{state}\n"
                f"done\t{done if done is not None else '-'}{f' of {total}' if total is not None else ''}"
                f"{' pages' if done is not None else ''}\n"
                f"rate\t{rate:.1f} pages a minute (this step)\nexpected end of step\t{eta}\n"
                f"newest output\t{time.strftime('%H:%M:%S', time.localtime(last_new))}\n"
                f"running for\t{int((now - t0) // 3600)}:{int((now - t0) % 3600 // 60):02d}\n"
                f"written\t{time.strftime('%Y-%m-%d %H:%M:%S')}\nitems\t{len(stems)} · {sum(total_pages.values())} pages\n")
        tmp = prog + ".part"
        open(tmp, "w", encoding="utf-8").write(text); os.replace(tmp, prog)
        if now - last_log >= 600:
            line(f"{done if done is not None else '-'} of {total if total is not None else '?'} · {state}"); last_log = now
        if state != "running" and not state.startswith("STALL"):
            line(state); return
        for _ in range(12):               # PROGRESS.txt every 60 s; the end (done, or the driver gone) seen within 5 s
            time.sleep(5)
            st = open(stepf).read().strip() if os.path.exists(stepf) else ""
            if st != step or not alive(a.pid):
                break


if __name__ == "__main__":
    main()
