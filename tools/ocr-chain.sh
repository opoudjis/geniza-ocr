#!/bin/sh
# ocr-chain — THE ENTRY POINT of the geniza OCR chain (M4.2; an internal record, 2026-10-02, not published).
#
#   tools/ocr-chain.sh <suffix> [--pdfs <list>] [--verdicts <psm verdicts json>] [--mode solo|shared] [--dry]        e.g.  tools/ocr-chain.sh 2026-10-03a
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
# Refuses: an existing output name; a second chain running. Never rebuild or file while a chain runs.
# The ACCEPTED lines are NOT regenerated here: that is the editor's signature (tools/ocr-acceptance-lines.py).
set -e
cd "$(dirname "$0")/.."   # to the repo root wherever it is called from (editor 2026-10-11 19:3x, sandbox model decision D)
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch; P=$G/sources/OCR-PDF-LIST-2026-09-30.txt
SUF=""; DRY=""; VOPT=""; MODE=shared   # --mode (the editor 2026-10-14 00:3x): workers from tools/cupel_workers.py; shared 40% (a dowse beside it), solo 80%
# --pdfs <list>: the PDF list the chain covers (default the 30 Sep list). cupel (2026-10-03) passes a NEW list —
# the 30 Sep list plus the batch's items — so new items enter G1, the gate and the ledger.
while [ $# -gt 0 ]; do
  case "$1" in
    --dry) DRY=--dry ;;
    --mode) shift; MODE="$1"; case "$MODE" in solo|shared) ;; *) echo "--mode must be solo or shared: $MODE"; exit 2;; esac ;;
    --pdfs) shift; P="$1"; [ -f "$P" ] || { echo "no PDF list at $P"; exit 2; } ;;
    --verdicts) shift; VOPT="$1"; [ -f "$VOPT" ] || { echo "no verdicts file at $VOPT"; exit 2; } ;;
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
LOGD=$W/ocr-chain-logs; LOG=$LOGD/CHAIN-$SUF.log
[ -d "$R" ] || { echo "run from the repo root ($R not found)"; exit 2; }
[ -d "$RUNS" ] && [ -d "$W" ] || { echo "no $RUNS or $W (the 2026-10-04 layout)"; exit 2; }
for f in "$G1" "$GATE" "$LED.tsv" "$RUSBAK" "$ALL.$SUF" "$ALLBAK" "$LOG"; do
  [ -e "$f" ] && { echo "exists: $f — choose a new suffix"; exit 1; }
done
# A second chain is refused by a LOCK folder (atomic; removed on exit), and any chain step or old chain script already
# running by its process name. (Matching «ocr-chain.sh» itself would also catch the shell that launched this one.)
if pgrep -f "tools/ocr-rebuild-combined.py|tools/ocr-accept.py|tools/ocr-g1-ink.py|tools/ocr-absence-ledger.py|scripts/chain-[0-9a-z-]+\.sh" >/dev/null; then
  echo "a chain step (or an old chain script) is running — refusing"; exit 1
fi
LOCK=$G/sources/.ocr-chain.lock
if [ "$DRY" != "--dry" ]; then
  mkdir "$LOCK" 2>/dev/null || { echo "another ocr-chain holds $LOCK — refusing (remove it only if no chain runs)"; exit 1; }
  trap 'rmdir "$LOCK"' EXIT
fi
run() { echo "+ $*"; [ "$DRY" = "--dry" ] || "$@"; }
step() { echo "$1 $(date '+%H:%M:%S')"; }
[ "$DRY" = "--dry" ] || { mkdir -p "$LOGD"; exec > "$LOG" 2>&1; }
step rebuild; run python3 tools/ocr-rebuild-combined.py "$R" --verdicts "$V"
step russian; run cp -Rp "$RUS" "$RUSBAK"; run python3 -W ignore tools/ocr-rus-companion.py "$R" "$RUS"
step G1;      run python3 tools/ocr-g1-ink.py --pdfs "$P" --root "$R" --files "$(python3 tools/cupel_workers.py "$MODE" total)" --write "$G1"
step gate;    run python3 tools/ocr-accept.py "$R" --psm-used 4 --script-segregated --write "$GATE"
step ledger;  run python3 tools/ocr-absence-ledger.py --gate "$GATE.json" --g1 "$G1.json" --pdfs "$P" --out "$LED"
step every-reading
run python3 tools/ocr-search-all-readings.py --ledger "$LED.tsv" --root "$R" --out "$ALL.$SUF"
[ -d "$ALL" ] && run mv "$ALL" "$ALLBAK"
run mv "$ALL.$SUF" "$ALL"
step done
