#!/bin/bash
# cupel-c7b1 — the run sheet's C7b.1 for one batch: the second-model passes on the batch's G2-pending items, language by
# language as the gate names them, and (--main) the items whose MAIN language the conversion did not read; as ONE repo tool
# so that no step asks (the editor 2026-10-24).
#
#   python3 tools/cupel-detach.py --log <batch-dir>/C7B1.out --pid <batch-dir>/C7B1.pid -- \
#       bash tools/cupel-c7b1.sh <batch-dir> <gate .md.json> <merged verdicts> <full PDF list> [<lang>=<stem>[,<stem>…] …]
#
# Each extra argument is a --main pass: <lang> the Tesseract model (fra, deu, ita, pol, …; «ita+lsf» for a Latino sine
# flexione item, read with ita and merged against its own list). The pending languages come from the gate's g2_pending
# for the stems in <batch-dir>/ITEMS.txt, written to <batch-dir>/G2-<language>-<gate suffix>.stems (refused if it
# exists, so a rerun on the same gate keeps its list; a later chain's gate, C7b.3's new G2-pending items, gets its own:
# cupel18a, 2026-10-24, three items pending after the second chain). Rule 0: ocr-second-model.py skips pages already merged in the language and writes each file
# whole, so the same command again resumes; <batch-dir>/PROGRESS-<model>.txt per pass. Run detached.
# WRITE-SET: the pass's .<model>.txt, .arb.txt and SECOND-MODEL.json in sources/ocr-rendersearch/<stem>/; in <batch-dir>:
# G2-<language>-<gate suffix>.stems, G2-<model>.log, PROGRESS-<model>.txt/.log.
set -e
cd "$(dirname "$0")/.."
B=${1:?batch dir}; GATE=${2:?gate}; V=${3:?verdicts}; L=${4:?full list}; shift 4
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch
TAG=$(basename "$GATE"); TAG=${TAG#OCR-GATE-}; TAG=${TAG%-segregated.md.json}
python3 -c '
import json, os, sys
B, gate, tag = sys.argv[1], sys.argv[2], sys.argv[3]
items = {l.strip() for l in open(os.path.join(B, "ITEMS.txt"), encoding="utf-8") if l.strip()}
pend = {}
for r in json.load(open(gate)):
    if r["corpus"] in items:
        for lang in r.get("g2_pending") or []:
            pend.setdefault(lang, []).append(r["corpus"])
for lang, st in sorted(pend.items()):
    p = os.path.join(B, f"G2-{lang}-{tag}.stems")
    if not os.path.exists(p):
        open(p, "x").write(",".join(sorted(st)))
    print(lang, len(st))' "$B" "$GATE" "$TAG"
code() { case $1 in french) echo fra;; german) echo deu;; spanish) echo spa;; portuguese) echo por;; italian) echo ita;;
  english) echo eng;; catalan) echo cat;; polish) echo pol;; czech) echo ces;; dutch) echo nld;; swedish) echo swe;;
  danish) echo dan;; hungarian) echo hun;; croatian) echo hrv;; *) echo "";; esac; }
for f in $B/G2-*-$TAG.stems; do
  [ -e "$f" ] || continue
  lang=$(basename "$f" -$TAG.stems); lang=${lang#G2-}; m=$(code $lang)
  [ -n "$m" ] || { echo "=== $lang: no model named here, skipped (for the editor)"; continue; }
  echo "=== $lang ($m) $(date '+%F %T')"
  python3 tools/ocr-second-model.py --gate $GATE --verdicts $V --pdfs $L --root $R --lang $m --corpus =$(cat "$f") \
    --files 4 --jobs 3 --progress $B/PROGRESS-$m.txt >> $B/G2-$m.log 2>&1
  tail -1 $B/G2-$m.log
done
for a in "$@"; do
  m=${a%%=*}; st=${a#*=}; P=""
  case $m in ita+lsf) m=ita; P="--primary latino-sine-flexione";; esac
  echo "=== --main $m $(date '+%F %T'): $st"
  python3 tools/ocr-second-model.py --gate $GATE --verdicts $V --pdfs $L --root $R --main $P --lang $m --corpus =$st \
    --files 2 --progress $B/PROGRESS-main-$m.txt >> $B/G2-main-$m.log 2>&1
  tail -1 $B/G2-main-$m.log
done
echo "=== C7b.1 DONE $(date '+%F %T')"
