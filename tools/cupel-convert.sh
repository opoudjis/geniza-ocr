#!/bin/bash
# cupel-convert — cupel step C3: convert a batch's NEW PDFs, and merge their psm verdicts — nothing else.
#
#   tools/cupel-convert.sh <new-pdf-list> <base verdicts json> <out merged verdicts json>
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
# WRITE-SET: the new items' folders under the render root $R (page files, including each page's text-layer
# reading page-NNNN.tl.txt, step 3b; skipped where a file is already converted); the out verdicts file and its batch file (each refused if it exists). Never the existing items. Run from the repo root.
set -euo pipefail
NEW="${1:?new pdf list}"; BASE="${2:?base verdicts}"; OUT="${3:?out merged verdicts}"
case "$OUT" in *-merged.json) ;; *) echo "out must end in -merged.json: $OUT"; exit 2;; esac
BATCH="${OUT%-merged.json}-batch.json"
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch
FILES="${FILES:-3}"; JOBS="${JOBS:-5}"
[ -e "$OUT" ] && { echo "exists: $OUT"; exit 1; }
[ -e "$BATCH" ] && { echo "exists: $BATCH"; exit 1; }
DUP=$(sed -E 's#.*/##; s#\.[^.]*$##' "$NEW" | sort | uniq -d); [ -z "$DUP" ] || { echo "duplicate names: $DUP"; exit 2; }
echo "=== 1 · CONVERT $(date '+%T')"
export R JOBS
grep -v '^[[:space:]]*$' "$NEW" | tr '\n' '\0' | xargs -0 -P "$FILES" -n 1 bash -c '
  pdf="$0"; stem="$(basename "$pdf")"; stem="${stem%.*}"
  [ -s "$R/$stem.txt" ] && { echo "  have $stem"; exit 0; }
  echo "  start $stem $(date +%T)"; python3 tools/ocr-pages.py "$pdf" --out "$R" --lang epo --psm 6 --jobs "$JOBS" 2>&1 | tail -1'
echo "=== 2 · PSM 4 $(date '+%T')"
python3 tools/ocr-psm-both.py --pdfs "$NEW" --root "$R" --files 3 --jobs 3 2>&1 | tail -2
echo "=== 3 · TEXT-MASK RE-READ $(date '+%T')"
python3 tools/ocr-mask-reread.py --pdfs "$NEW" --root "$R" --jobs 8 2>&1 | tail -2
echo "=== 3b · THE PDF'S OWN TEXT LAYER $(date '+%T')"
# (approved by the editor, 2026-10-04 12:4x: the layer becomes one more competing reading, as the corpus had on 26 Sep.)
# tools/ocr-textlayer.py writes page-NNNN.tl.txt beside the other readings (a page whose layer holds < 20 characters
# gets none; a page that has one is skipped); ocr-psm-adjudicate.py weighs it like any other reading. Not ground truth
# (editor 2026-09-26): it competes, it does not replace.
python3 tools/ocr-textlayer.py --pdfs "$NEW" --root "$R" --jobs 8 2>&1 | tail -2
echo "=== 4 · ADJUDICATE the new items alone $(date '+%T')"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/root"
while read -r pdf; do [ -n "$pdf" ] || continue; s="$(basename "$pdf")"; s="${s%.*}"; ln -s "$PWD/$R/$s" "$T/root/$s"; done < "$NEW"
python3 tools/ocr-psm-adjudicate.py "$T/root" --write "$T/new.json" 2>&1 | tail -3
echo "=== 5 · MERGE $(date '+%T')"
python3 - "$BASE" "$T/new.json" "$OUT" "$BATCH" <<'EOF'
import json, sys
base, new, out, batch = (json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3], sys.argv[4])
have = {v["page"] for v in base}; clash = [v["page"] for v in new if v["page"] in have]
if clash: sys.exit(f"refusing: {len(clash)} new verdicts name pages already judged, e.g. {clash[:3]}")
json.dump(base + new, open(out, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(new, open(batch, "w", encoding="utf-8"), ensure_ascii=False)
print(f"{len(base)} + {len(new)} verdicts → {out}; the batch's own → {batch} (track this one)")
EOF
echo "=== DONE $(date '+%T') — next: tools/ocr-chain.sh <suffix> --pdfs <full list> --verdicts $OUT"
