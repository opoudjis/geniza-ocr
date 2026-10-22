#!/usr/bin/env python3
r"""cupel_progress — save as you go, resume, report: rule 0 of RUNBOOK.md for every long cupel step.

On 2026-10-22 14:1x, after cupel17's text-blocks dry pass ran two hours, wrote nothing until its end and died with
the session, the editor ruled that a job must save its outputs incrementally, so that they can be recovered from, and
must not run for hours without reporting; and that batches be smaller.

    import cupel_progress as CP
    J = CP.Journal(path)              # JSONL, one line per finished page; J.done: the keys already in it
    CP.write_new(path, text, J.resuming)   # temp file then rename; refuses an existing file unless resuming
    J.add(key, rec)                   # appended and fsynced AFTER the page's files are written
    P = CP.Progress(path, step, total, done=len(J.done), chunk=100)
    P.tick(); ...; P.finish(summary)

The journal line is written after the page's own files, so a line means the page is complete; a page with files but no
line (a crash between the two) is done again, its file replaced (resuming only). PROGRESS.txt is rewritten every 60 s by
a thread of its own, whether or not a page finished, so its «last page» time shows a stall; PROGRESS.log gets one line per
chunk of pages and one at the end. Neither is a record of results: the journal is.
"""
import os, sys, json, time, threading


def write_new(path, text, resuming=False):
    if os.path.exists(path) and not resuming:
        sys.exit(f"exists: {path}")
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


class Journal:
    def __init__(self, path):
        self.path, self.done, self.recs = path, set(), []
        self.resuming = os.path.exists(path)
        if self.resuming:
            for l in open(path, encoding="utf-8"):
                try:
                    j = json.loads(l)
                except ValueError:
                    continue          # a line cut short by a crash: its page is done again
                self.done.add(tuple(j["key"])); self.recs.append(j["rec"])
        self.f = open(path, "a", encoding="utf-8")

    def add(self, key, rec):
        self.f.write(json.dumps({"key": list(key), "rec": rec}, ensure_ascii=False) + "\n")
        self.f.flush(); os.fsync(self.f.fileno())
        self.done.add(tuple(key)); self.recs.append(rec)


def _hms(s):
    s = int(max(0, s)); return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


class Progress:
    def __init__(self, path, step, total, done=0, chunk=100):
        self.path, self.log, self.step, self.total, self.chunk = path, os.path.splitext(path)[0] + ".log", step, total, chunk
        self.done0 = self.done = done
        self.t0, self.last = time.time(), None
        self.lock, self.stop = threading.Lock(), threading.Event()
        self._line(f"start · {done} of {total} already done" + (" (resumed)" if done else ""))
        self.write()
        threading.Thread(target=self._beat, daemon=True).start()

    def _line(self, s):
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{self.step}\t{s}\n")

    def write(self, state="running"):
        with self.lock:
            now, new = time.time(), self.done - self.done0
            rate = new / (now - self.t0) if new and now > self.t0 else 0.0
            eta = time.strftime("%H:%M", time.localtime(now + (self.total - self.done) / rate)) if rate else "?"
            last = time.strftime("%H:%M:%S", time.localtime(self.last)) if self.last else "none yet"
            text = (f"step\t{self.step}\nstate\t{state}\ndone\t{self.done} of {self.total}\n"
                    f"rate\t{rate * 60:.1f} pages a minute\nexpected end\t{eta}\nlast page\t{last}\n"
                    f"running for\t{_hms(now - self.t0)}\nwritten\t{time.strftime('%Y-%m-%d %H:%M:%S')}\npid\t{os.getpid()}\n")
            tmp = self.path + ".part"
            open(tmp, "w", encoding="utf-8").write(text); os.replace(tmp, self.path)

    def _beat(self):
        while not self.stop.wait(60):
            self.write()

    def tick(self, n=1):
        with self.lock:
            self.done += n; self.last = time.time(); d = self.done
        if d % self.chunk == 0 or d == self.total:
            self._line(f"{d} of {self.total}")
            self.write()

    def finish(self, summary):
        self.stop.set(); self.write("done"); self._line("done · " + summary)
