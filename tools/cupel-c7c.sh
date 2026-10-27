#!/bin/bash
# cupel-c7c — the run sheet's C7b.2 (small capitals) and C7c (columns rounds 1 and 2, the blocks cut, Fraktur, second
# readings, empty pages) for one batch, under rule 0, as ONE repo tool so that no step asks (the editor 2026-10-24: «cupel
# fix to make it autopilot: approved»; the run sheet's command templates). Made general from cupel18a's driver of 2026-10-23.
#
#   python3 tools/cupel-detach.py --log <batch-dir>/C7C.out --pid <batch-dir>/C7C.pid -- \
#       bash tools/cupel-c7c.sh <batch-dir> <full PDF list> <NEW PDF list> <gate .md.json>
#
# Each step is journaled page by page (<batch-dir>/<STEP>.journal.jsonl; small capitals skip pages that have their
# .sc3x.txt), PROGRESS.txt rewritten every minute; a step that ended leaves <STEP>.done and is skipped on a later run; logs
# appended to. To resume after any stop: the same command again. Run detached, so tesseract and pdftoppm go through
# tools/shims and the core dial; pools at 14 (J=…), the dial decides how many work. Needs <batch-dir>/ITEMS.txt.
# WRITE-SET: the readings the five passes write in sources/ocr-rendersearch (each pass's own new files and records), and
# in <batch-dir>: the step logs, journals, .done markers, PROGRESS.txt/.log, columns-items.json, BLOCKS-PAGES.tsv,
# FRAKTUR-PAGES.tsv, EMPTIES.tsv, look-empties/, smallcaps-<time>/ (each created only if absent).
set -e
cd "$(dirname "$0")/.."
B=${1:?batch dir}; L=${2:?full list}; NEW=${3:?NEW list}; GATE=${4:?gate .md.json}
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch
T=tools/ocr-reocr-best.py; J=${J:-14}
K="--progress $B/PROGRESS.txt --chunk 100 --jobs $J"
[ -e $B/columns-items.json ] || python3 -c 'import json,sys,unicodedata as u; print(json.dumps([u.normalize("NFC",l.strip()) for l in open(sys.argv[1],encoding="utf-8") if l.strip()],ensure_ascii=False))' $B/ITEMS.txt > $B/columns-items.json
step() {  # step <NAME> <mode and arguments…>
  local n=$1; shift
  if [ -e $B/$n.done ]; then echo "=== $n done before, skipped"; return; fi
  echo "=== $n $(date '+%F %T') jobs $J"
  python3 $T "$@" --journal $B/$n.journal.jsonl $K >> $B/$n.log 2>&1
  tail -1 $B/$n.log; date '+%F %T' > $B/$n.done
}
if [ ! -e $B/SMALLCAPS.done ]; then
  echo "=== SMALLCAPS $(date '+%F %T')"
  python3 tools/ocr-smallcaps-reread.py --preferred $G/sources/ocr-preferred --root $R --pdfs $NEW --gate $GATE \
    --out $B/smallcaps-$(date '+%H%M%S') --jobs $J --progress $B/PROGRESS.txt >> $B/SMALLCAPS.log 2>&1
  tail -1 $B/SMALLCAPS.log; date '+%F %T' > $B/SMALLCAPS.done
fi
step COLUMNS columns $R --pdfs $L --items $B/columns-items.json
step COLUMNS2 columns2 $R --pdfs $L --items $B/columns-items.json
[ -e $B/BLOCKS-PAGES.tsv ] || python3 -c '
import json, os, sys
R, B = sys.argv[1], sys.argv[2]
rows = []
for it in json.load(open(f"{B}/columns-items.json", encoding="utf-8")):
    cj = os.path.join(R, it, "COLUMNS.json")
    if os.path.exists(cj):
        for r in json.load(open(cj)).get("round2", []):
            if not r["kept"] and not r.get("untried") and (r.get("psm3") or {}).get("share5") is not None:
                rows.append(it + "\t" + str(r["page"]) + "\n")
open(f"{B}/BLOCKS-PAGES.tsv", "x", encoding="utf-8").write("".join(rows)); print(len(rows), "pages to the blocks cut")' "$R" "$B"
step BLOCKS blocks $R --pdfs $L --list $B/BLOCKS-PAGES.tsv
[ -e $B/FRAKTUR-PAGES.tsv ] || { python3 $T frkcands $R --pdfs $L --items $B/columns-items.json --out $B/FRAKTUR-PAGES.tsv >> $B/FRKCANDS.log 2>&1; tail -1 $B/FRKCANDS.log; }
step FRAKTUR fraktur $R --pdfs $L --list $B/FRAKTUR-PAGES.tsv
step ADDS adds $R --pdfs $L --items $B/columns-items.json
step EMPTIES empties $R --pdfs $L --items $B/columns-items.json --out $B/EMPTIES.tsv --look $B/look-empties
echo "=== DONE $(date '+%F %T')"
