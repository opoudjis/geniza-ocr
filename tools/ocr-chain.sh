#!/bin/sh
# ocr-chain — THE ENTRY POINT of the geniza OCR chain (M4.2; an internal record, 2026-10-02, not published).
#
#   tools/ocr-chain.sh <suffix> [--pdfs <list>] [--verdicts <psm verdicts json>] [--mode solo|shared] [--dry]        e.g.  tools/ocr-chain.sh 2026-10-03a
#   tools/ocr-chain.sh <suffix> --resume [the same options]       a stopped chain, from the first step not done
#
# Replaces the hand-copied chain scripts (untracked, not published). Run from
# the repo root. Order, and why:
#   1. rebuild      tools/ocr-rebuild-combined.py — the combined search text per item, from every reading on disk
#   2. Russian      tools/ocr-rus-companion.py — the Russian search (ocr-rendersearch-rus/), rewritten in place; the old
#                   folder is kept as sources/ocr-work/ocr-rendersearch-rus.bak-<suffix>
#   3. G1           tools/ocr-g1-ink.py → ocr/runs/OCR-GATE-G1-<suffix>.md
#   4. gate         tools/ocr-accept.py → ocr/runs/OCR-GATE-<suffix>-segregated.md
#   5. ledger       tools/ocr-absence-ledger.py → ocr/runs/OCR-ABSENCE-LEDGER-<suffix>.tsv
#   6. every reading tools/ocr-search-all-readings.py, for the SPECIAL HANDLING items of THAT ledger (the editor's choice
#                   of option (a), 2026-10-02): built as ocr-rendersearch-all.<suffix>, then swapped into ocr-rendersearch-all/ (the old one
#                   kept as sources/ocr-work/ocr-rendersearch-all.bak-<suffix>)
# Steps 2 and 6 were run by hand until 2 Oct; both must follow ANY re-read.
# Refuses: an existing output name; a second chain running; the sandbox. Never rebuild or file while a chain runs.
# SAVES AS IT GOES AND RESUMES (run sheet rule 0; the editor 2026-10-22 14:1x: «there needs to be incremental saving of
# outputs that can be recovered from»; built 2026-10-25 23:4x, the editor to the build queue's item 1): each step,
# once done, is written to `ocr-chain-logs/CHAIN-<suffix>.done`; `--resume` runs the same suffix again from the first
# step not in it, the log appended. A step's output left by a stopped run is moved aside as `<name>.partial-<HHMMSS>`
# and the step run again whole (no step is longer than ~10 minutes over the whole corpus). The Russian backup is not taken
# twice; the every-reading search is built, then swapped, as two steps. `ocr-chain-logs/CHAIN-<suffix>.PROGRESS.txt` is
# rewritten every minute: the step, how long it has run («OVER 30 MIN»), the steps done.
# THE SANDBOX (2026-10-25: two chains started inside it stopped at G1, whose process pool cannot start there, and the
# check for a running chain step passed because `pgrep` cannot see the process list): refused before anything is written,
# with the way to run it (tools/cupel-detach.py, outside the sandbox).
# The ACCEPTED lines are NOT regenerated here: that is the editor's signature (tools/ocr-acceptance-lines.py).
set -e
cd "$(dirname "$0")/.."   # to the repo root wherever it is called from (editor 2026-10-11 19:3x, sandbox model decision D)
export PATH="$PWD/tools/shims:$PATH"   # the core dial (tools/cupel_workers.py): tesseract and pdftoppm wait for a slot while geniza/ocr/CORE-DIAL exists
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch; P=$G/sources/OCR-PDF-LIST-2026-09-30.txt
SUF=""; DRY=""; VOPT=""; WHY=""; MODE=shared; RESUME=""   # --mode (the editor 2026-10-14 00:3x): workers from tools/cupel_workers.py; shared 40% (a dowse beside it), solo 80%
# --pdfs <list>: the PDF list the chain covers (default the 30 Sep list). cupel (2026-10-03) passes a NEW list —
# the 30 Sep list plus the batch's items — so new items enter G1, the gate and the ledger.
while [ $# -gt 0 ]; do
  case "$1" in
    --dry) DRY=--dry ;;
    --resume) RESUME=1 ;;
    --mode) shift; MODE="$1"; case "$MODE" in solo|shared) ;; *) echo "--mode must be solo or shared: $MODE"; exit 2;; esac ;;
    --pdfs) shift; P="$1"; [ -f "$P" ] || { echo "no PDF list at $P"; exit 2; } ;;
    --verdicts) shift; VOPT="$1"; [ -f "$VOPT" ] || { echo "no verdicts file at $VOPT"; exit 2; } ;;
    --why) shift; WHY="$1" ;;   # the recupel notices' «why» (tools/ocr-recupel-notice.py; default «chain <suffix>»)
    --why-items) shift; WHYI="$1"; [ -f "$WHYI" ] || { echo "no why-items file at $WHYI"; exit 2; } ;;   # item⇥why: a notice's own why (D4b's vision requests)
    -*) echo "unknown option $1"; exit 2 ;;
    *) [ -z "$SUF" ] && SUF="$1" || { echo "one suffix only"; exit 2; } ;;
  esac; shift
done
[ -n "$SUF" ] || { echo "usage: tools/ocr-chain.sh <suffix> [--pdfs <list>] [--verdicts <json>] [--dry]"; exit 2; }
# Run outputs go to geniza/ocr/runs/; backups and logs to geniza/sources/ocr-work/ (the folder move of 2026-10-04,
# an internal record, not published). The searched folders themselves stay in geniza/sources/.
RUNS=$G/ocr/runs; W=$G/sources/ocr-work
V=${VOPT:-$RUNS/OCR-PSM-VERDICTS-2026-09-30-merged.json}   # --verdicts: cupel passes the 30 Sep verdicts + the batch's
G1=$RUNS/OCR-GATE-G1-$SUF.md; GATE=$RUNS/OCR-GATE-$SUF-segregated.md; LED=$RUNS/OCR-ABSENCE-LEDGER-$SUF
RUS=$G/sources/ocr-rendersearch-rus; ALL=$G/sources/ocr-rendersearch-all
RUSBAK=$W/ocr-rendersearch-rus.bak-$SUF; ALLBAK=$W/ocr-rendersearch-all.bak-$SUF
LOGD=$W/ocr-chain-logs; LOG=$LOGD/CHAIN-$SUF.log; DONE=$LOGD/CHAIN-$SUF.done; PROG=$LOGD/CHAIN-$SUF.PROGRESS.txt
[ -d "$R" ] || { echo "run from the repo root ($R not found)"; exit 2; }
[ -d "$RUNS" ] && [ -d "$W" ] || { echo "no $RUNS or $W (the 2026-10-04 layout)"; exit 2; }
if [ -n "$RESUME" ]; then
  [ -f "$LOG" ] || { echo "--resume: no chain $SUF to resume ($LOG not found)"; exit 2; }
  grep -qx done "$DONE" 2>/dev/null && { echo "--resume: chain $SUF is done already ($DONE)"; exit 1; }
else
  for f in "$G1" "$GATE" "$LED.tsv" "$RUSBAK" "$ALL.$SUF" "$ALLBAK" "$LOG" "$DONE"; do
    [ -e "$f" ] && { echo "exists: $f — choose a new suffix (or --resume a stopped chain)"; exit 1; }
  done
fi
# A second chain is refused by the LOCK below (and a dowse by it), and any chain step or old chain script already
# running by its process name. (Matching «ocr-chain.sh» itself would also catch the shell that launched this one.)
# pgrep answers 0 (found) or 1 (none); anything else (3 in the sandbox: «Cannot get process list») means it cannot look.
if [ "$DRY" != "--dry" ]; then
  pg=0; pgrep -f "tools/ocr-rebuild-combined.py|tools/ocr-accept.py|tools/ocr-g1-ink.py|tools/ocr-absence-ledger.py|scripts/chain-[0-9a-z-]+\.sh" >/dev/null 2>&1 || pg=$?
  case $pg in
    0) echo "a chain step (or an old chain script) is running — refusing"; exit 1 ;;
    1) ;;
    *) echo "refusing: this shell cannot see the process list (pgrep answered $pg), so it is inside the sandbox, where G1's process pool cannot start either. Run the chain detached, outside the sandbox: python3 tools/cupel-detach.py --log <dir>/CHAIN.out --pid <dir>/CHAIN.pid -- bash tools/ocr-chain.sh $SUF …"; exit 2 ;;
  esac
  python3 -c 'from concurrent.futures import ProcessPoolExecutor as P
with P(1) as p: p.submit(int, "1").result()' >/dev/null 2>&1 || {
    echo "refusing: a process pool cannot start here (the sandbox), and G1 needs one. Run the chain through tools/cupel-detach.py outside the sandbox."; exit 2; }
fi
# THE LOCK (2026-10-26 00:4x, after the chain of 2026-10-25 23:38 ran under Ezri's redowse search; Ezri's specifics):
# `geniza/ocr/locks/chain.lock`, taken by tools/corpus_locks.py, which refuses while another chain or ANY dowse holds
# a lock there (`dowse-<pid>.lock`, taken by ocr-dowse.py and dowse-brief-fill.py, Picard's account included) and says
# who and since when; a stale lock (its pid gone) is said and removed. Refuse, never wait.
LOCKF=$G/ocr/locks/chain.lock
if [ "$DRY" != "--dry" ]; then
  python3 tools/corpus_locks.py take chain --pid $$ -- "tools/ocr-chain.sh $SUF${RESUME:+ --resume}" || exit 1
  mkdir -p "$LOGD"; echo starting > "$LOGD/CHAIN-$SUF.step"
  # the progress file, every minute while the lock is held: how long the step has run («OVER 30 MIN», rule 0 (d)'s
  # chunk; not «log quiet»: most steps print nothing until they end, 2026-10-25 the rebuild flagged «STALL» falsely)
  ( while [ -f "$LOCKF" ]; do
      q=$(( ( $(date +%s) - $(stat -f %m "$LOGD/CHAIN-$SUF.step" 2>/dev/null || date +%s) ) / 60 ))
      printf 'chain %s · step %s, %s min · done: %s%s · %s\n' "$SUF" "$(cat "$LOGD/CHAIN-$SUF.step")" "$q" \
        "$(cat "$DONE" 2>/dev/null | tr '\n' ' ')" "$( [ $q -ge 30 ] && echo ' · OVER 30 MIN')" "$(date '+%H:%M:%S')" > "$PROG"
      sleep 60; done ) &
  HB=$!
  # `|| true` on each: under `set -e` a failing command ends the EXIT trap itself, and on a kill of the whole group the
  # progress loop is already gone, so `kill $HB` failed and the lock stayed (2026-10-26 00:28, reproduced and fixed 00:4x)
  trap 'kill $HB 2>/dev/null || true; python3 tools/corpus_locks.py release chain --pid $$ || true' EXIT
  trap 'echo "stopped $(date "+%H:%M:%S") (resume: the same command with --resume)"; exit 1' INT TERM HUP   # a kill still frees the lock
fi
run() { echo "+ $*"; [ "$DRY" = "--dry" ] || "$@"; }
step() { echo "$1 $(date '+%H:%M:%S')"; [ "$DRY" = "--dry" ] || echo "$1 since $(date '+%H:%M:%S')" > "$LOGD/CHAIN-$SUF.step"; }
# todo <step>: true if the step is not yet done (always under --dry); mark <step> once it is
todo() { [ "$DRY" = "--dry" ] && return 0; ! grep -qx "$1" "$DONE" 2>/dev/null || { echo "$1 done already, skipped"; return 1; }; }
mark() { [ "$DRY" = "--dry" ] || echo "$1" >> "$DONE"; }
# aside <file|dir>…: what a stopped run of the step left, moved out of the way before the step runs again
aside() { for f in "$@"; do [ -e "$f" ] && run mv "$f" "$f.partial-$(date '+%H%M%S')"; done; return 0; }
if [ "$DRY" != "--dry" ]; then
  if [ -n "$RESUME" ]; then exec >> "$LOG" 2>&1; echo "resume $(date '+%H:%M:%S')"; else exec > "$LOG" 2>&1; fi
fi
# the selective redowse (2026-10-24, the editor; Ezri's form, ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md): a
# SIGNED item with new readings has its preferred text kept before the rebuild rewrites it, and a notice after
if todo snapshot; then step snapshot; run python3 tools/ocr-recupel-notice.py snapshot --suffix "$SUF"; mark snapshot; fi
if todo rebuild; then step rebuild; run python3 tools/ocr-rebuild-combined.py "$R" --verdicts "$V"; mark rebuild; fi
if todo russian; then
  step russian; [ -e "$RUSBAK" ] || run cp -Rp "$RUS" "$RUSBAK"; run python3 -W ignore tools/ocr-rus-companion.py "$R" "$RUS"; mark russian
fi
if todo G1; then
  step G1; aside "$G1" "$G1.json"
  run python3 tools/ocr-g1-ink.py --pdfs "$P" --root "$R" --files "$(python3 tools/cupel_workers.py "$MODE" total)" --write "$G1"; mark G1
fi
if todo gate; then step gate; aside "$GATE" "$GATE.json"; run python3 tools/ocr-accept.py "$R" --psm-used 4 --script-segregated --write "$GATE"; mark gate; fi
if todo ledger; then
  step ledger; aside "$LED.tsv"; run python3 tools/ocr-absence-ledger.py --gate "$GATE.json" --g1 "$G1.json" --pdfs "$P" --out "$LED"; mark ledger
fi
if todo every-reading; then
  step every-reading; aside "$ALL.$SUF"; run python3 tools/ocr-search-all-readings.py --ledger "$LED.tsv" --root "$R" --out "$ALL.$SUF"; mark every-reading
fi
if todo swap; then
  step swap
  [ -d "$ALL" ] && [ ! -e "$ALLBAK" ] && run mv "$ALL" "$ALLBAK"
  { [ "$DRY" = "--dry" ] || [ ! -e "$ALL" ]; } && run mv "$ALL.$SUF" "$ALL"; mark swap
fi
if todo notices; then step notices; run python3 tools/ocr-recupel-notice.py notice --suffix "$SUF" ${WHY:+--why "$WHY"} ${WHYI:+--why-items "$WHYI"}; mark notices; fi
# the run sheet's backup trim, inside the chain so that no `rm` is typed by hand (2026-10-24, the box-free cupel; the editor
# 2026-10-17 18:4x: all but two to go): of each search folder's rollback copies, the two newest by VERSION order are kept,
# the rest removed by name; only folders named <search folder>.bak-<suffix> (failure map R40)
step trim
[ "$DRY" = "--dry" ] || python3 -c '
import os, re, shutil, sys
W = sys.argv[1]
key = lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
for k in ("ocr-rendersearch-all", "ocr-rendersearch-rus"):
    bak = sorted((d for d in os.listdir(W) if d.startswith(k + ".bak-") and os.path.isdir(os.path.join(W, d))), key=key, reverse=True)
    for d in bak[2:]:
        shutil.rmtree(os.path.join(W, d)); print("removed", d)
    print("kept", bak[:2])' "$W"
mark trim
step done; mark done
