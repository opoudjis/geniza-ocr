#!/bin/bash
# cupel-convert — cupel step C4 (corrected 2026-10-25 from «C3», to match the run sheet of 2026-10-11): convert a batch's NEW PDFs, and merge their psm verdicts — nothing else.
#
#   tools/cupel-convert.sh <new-pdf-list> <base verdicts json> <out merged verdicts json> [--mode=solo|--mode=shared] [--dir=<batch-dir>]
#
# RULE 0 (the run sheet; the editor 2026-10-22 14:1x: «I will not accept jobs that go into outer space for hours on end with
# no communication»), 2026-10-23: every pass writes each page whole (a temp file, then renamed) and skips what is done, so
# the same command again RESUMES; with --dir, the step is written to <batch-dir>/STEP and tools/cupel-convert-watch.py
# rewrites <batch-dir>/PROGRESS.txt every minute from what is on disk (a stall after 10 minutes without output). Run it
# detached (tools/cupel-detach.py). CUPEL_ROOT=<dir> sends the readings to another root: for tests only.
#
# --mode (the editor ruled on 2026-10-14 00:3x for two modes: running alongside a parallelised dowse, with 40% of the
# cores, and running alone, with 80% of the cores): the workers every pass may use, from tools/cupel_workers.py; default shared (40%), so a dowse
# beside it is not starved; --mode=solo for an unattended run (overnight).
#
# WHY (2026-10-03, cupel batch 1). tools/ocr-run-corpus.sh converts well, but its step 4 judges psm verdicts over the WHOLE
# root and then rebuilds every item from that one new verdicts file — not from the merged 30 Sep verdicts the accepted
# corpus rests on. So cupel converts here (steps 1–3 of ocr-run-corpus.sh, for the listed PDFs only), adjudicates the new
# items alone (a scratch root of links to them), and merges their verdicts into a NEW file; tools/ocr-chain.sh then
# rebuilds and gates with `--pdfs <full list> --verdicts <merged>`.
# BATCH FILE (approved by the editor, 2026-10-03 18:2x): every merged file is a full copy of the corpus's verdicts (~27 MB),
# so the BATCH'S OWN verdicts are also written, to <out minus -merged.json>-batch.json. The batch file is tracked in git;
# merged files are not (.gitignore), and are rebuilt as base + each batch file in order:
# 2026-09-30-merged (115,177) + cupel1-batch (328) + cupel2-batch (2,983) = cupel2-merged (118,488).
# WRITE-SET: the new items' folders under sources/ocr-rendersearch/ (page files, including each page's text-layer
# reading page-NNNN.tl.txt, step 3b; skipped where a file is already converted); the out verdicts file and its batch file (each refused if it exists). Never the existing items. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."   # to the repo root wherever it is called from (editor 2026-10-11 19:3x, sandbox model decision D)
export PATH="$PWD/tools/shims:$PATH"   # the core dial (tools/cupel_workers.py): tesseract and pdftoppm wait for a slot while geniza/ocr/CORE-DIAL exists
NEW="${1:?new pdf list}"; BASE="${2:?base verdicts}"; OUT="${3:?out merged verdicts}"
case "$OUT" in *-merged.json) ;; *) echo "out must end in -merged.json: $OUT"; exit 2;; esac
BATCH="${OUT%-merged.json}-batch.json"
G=published/heterophony-resources/geniza; R="${CUPEL_ROOT:-$G/sources/ocr-rendersearch}"
MODE="${4:---mode=shared}"; MODE="${MODE#--mode=}"
case "$MODE" in solo|shared) ;; *) echo "--mode must be solo or shared: $MODE"; exit 2;; esac
DIR="${5:-}"; DIR="${DIR#--dir=}"
step() { [ -n "$DIR" ] && echo "$1" > "$DIR/STEP"; true; }
FILES=$(python3 tools/cupel_workers.py "$MODE" files); JOBS=$(python3 tools/cupel_workers.py "$MODE" jobs); TOTAL=$(python3 tools/cupel_workers.py "$MODE" total)
echo "mode $MODE: $TOTAL workers ($FILES PDFs × $JOBS pages)"
[ -e "$OUT" ] && { echo "exists: $OUT"; exit 1; }
[ -e "$BATCH" ] && { echo "exists: $BATCH"; exit 1; }
DUP=$(sed -E 's#.*/##; s#\.[^.]*$##' "$NEW" | sort | uniq -d); [ -z "$DUP" ] || { echo "duplicate names: $DUP"; exit 2; }
if [ -n "$DIR" ]; then
  [ -d "$DIR" ] || { echo "no such batch dir: $DIR"; exit 2; }
  step starting
  python3 tools/cupel-convert-watch.py --new "$NEW" --root "$R" --dir "$DIR" --pid $$ >/dev/null 2>&1 &
  WATCH=$!   # the watcher ends by itself: at STEP «done» (waited for, below), or within seconds of this driver's end (state ENDED)
fi
step convert; echo "=== 1 · CONVERT $(date '+%T')"
export R JOBS
grep -v '^[[:space:]]*$' "$NEW" | tr '\n' '\0' | xargs -0 -P "$FILES" -n 1 bash -c '
  pdf="$0"; stem="$(basename "$pdf")"; stem="${stem%.*}"
  [ -s "$R/$stem.txt" ] && { echo "  have $stem"; exit 0; }
  echo "  start $stem $(date +%T)"; python3 tools/ocr-pages.py "$pdf" --out "$R" --lang epo --psm 6 --jobs "$JOBS" 2>&1 | tail -1'
step psm4; echo "=== 2 · PSM 4 $(date '+%T')"
python3 tools/ocr-psm-both.py --pdfs "$NEW" --root "$R" --files "$FILES" --jobs "$JOBS" 2>&1 | tail -2
step mask; echo "=== 3 · TEXT-MASK RE-READ $(date '+%T')"
python3 tools/ocr-mask-reread.py --pdfs "$NEW" --root "$R" --jobs "$TOTAL" 2>&1 | tail -2
step textlayer; echo "=== 3b · THE PDF'S OWN TEXT LAYER $(date '+%T')"
# (editor 2026-10-04 12:4x,: the layer becomes one more competing reading, as the corpus had on 26 Sep.)
# tools/ocr-textlayer.py writes page-NNNN.tl.txt beside the other readings (a page whose layer holds < 20 characters
# gets none; a page that has one is skipped); ocr-psm-adjudicate.py weighs it like any other reading. Not ground truth
# (editor 2026-09-26): it competes, it does not replace.
python3 tools/ocr-textlayer.py --pdfs "$NEW" --root "$R" --jobs "$TOTAL" 2>&1 | tail -2
step adjudicate; echo "=== 4 · ADJUDICATE the new items alone $(date '+%T')"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/root"
while read -r pdf; do [ -n "$pdf" ] || continue; s="$(basename "$pdf")"; s="${s%.*}"; ln -s "$PWD/$R/$s" "$T/root/$s"; done < "$NEW"
python3 tools/ocr-psm-adjudicate.py "$T/root" --write "$T/new.json" 2>&1 | tail -3
step merge; echo "=== 5 · MERGE $(date '+%T')"
python3 - "$BASE" "$T/new.json" "$OUT" "$BATCH" <<'EOF'
import json, sys
base, new, out, batch = (json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3], sys.argv[4])
have = {v["page"] for v in base}; clash = [v["page"] for v in new if v["page"] in have]
if clash: sys.exit(f"refusing: {len(clash)} new verdicts name pages already judged, e.g. {clash[:3]}")
import os
for path, data in ((batch, new), (out, base + new)):   # each whole (a temp file, then renamed); out last: it is the «done» mark
    json.dump(data, open(path + ".part", "w", encoding="utf-8"), ensure_ascii=False); os.replace(path + ".part", path)
print(f"{len(base)} + {len(new)} verdicts → {out}; the batch's own → {batch} (track this one)")
EOF
step done; echo "=== DONE $(date '+%T') — next: tools/ocr-chain.sh <suffix> --pdfs <full list> --verdicts $OUT"
[ -n "${WATCH:-}" ] && wait "$WATCH" 2>/dev/null   # its last PROGRESS.txt says «done»
true
