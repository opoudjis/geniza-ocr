#!/bin/bash
# ocr-run-corpus.sh — run NEW texts through the whole OCR pipeline, in order, unattended.
#
#   tools/ocr-run-corpus.sh <tag> <pdf-list> [<pdf-list> …]
#       <tag>       names the outputs: OCR-PSM-VERDICTS-<tag>.json · OCR-GATE-<tag>.md · OCR-GATE-G1-<tag>.md
#       <pdf-list>  files of PDF paths, one per line
#
#   env: FILES=4   files converted at once      JOBS=5   threads per file (conversion)
#        R=<root>  output root (default: the `ocr-rendersearch` folder set below — NEVER the `ocr/` folder, which is cited)
#
# Specification: an internal record, not published.
#
# BUILD THE PDF LIST FROM WHAT IS ON DISK OR FROM THE FETCH MANIFEST — NEVER FROM FILE NAMES OF
#    PRIOR OUTPUT. Three work lists in one week skipped real material by trusting a name (2026-09-25:
#    La Lumo, Australian Esperantist, Suisa Idisto, the per-issue Belga Sonorilo). For a fetch, use
#    its manifest, not a directory listing.
# LOOK AT ONE PAGE OF EACH NEW CORPUS FIRST. Handwriting and lithograph return confident
#    nonsense that no step below detects; exclude them by name before running. FRAKTUR is salvageable
#    (the editor's ruling, 2026-10-04): read it with the `frk+epo`
#    variant of tools/ocr-reocr-best.py (the item's stem in its FRAKTUR list), as for Estlanda
#    Esperantisto and Idowoti.
#
# Every step is re-runnable: a file already converted, a page already re-read, is skipped.
# Nothing is overwritten except the derived combined text, which is rebuilt from per-page files.

set -u
cd "$(dirname "$0")/.."
TAG="${1:?tag}"; shift
[ $# -ge 1 ] || { echo "need at least one pdf list"; exit 1; }
G=published/heterophony-resources/geniza
RUNS=$G/ocr/runs   # run outputs (the folder move of 2026-10-04)
R="${R:-$G/sources/ocr-rendersearch}"
FILES="${FILES:-4}"; JOBS="${JOBS:-5}"
WORK="$(mktemp -d)"; LIST="$WORK/all.txt"; mkdir -p "$WORK/lock"
cat "$@" | grep -v '^[[:space:]]*$' | sort -u > "$LIST"
# NAME COLLISIONS (found 2026-09-26): every tool names its output by the PDF's file name alone,
# so two DIFFERENT PDFs called `39.pdf` (Posta Mundi 39, Informilo por Interlingvistoj 39) shared one
# output folder — one was never converted, and later steps read the other's images. Refuse to run;
# give such PDFs unique names with links.
DUP=$(sed -E 's#.*/##; s#\.[^.]*$##' "$LIST" | sort | uniq -d)
if [ -n "$DUP" ]; then
  echo "⛔ REFUSING: these file names occur more than once in the list: $DUP"
  echo "   Link each to a unique name (sources/_stem-aliases/) and list the links instead."; exit 2
fi
echo "=== $(wc -l < "$LIST" | tr -d ' ') PDFs · tag $TAG · root $R · $(date '+%F %T')"

# 1 · ACQUIRE + READ at psm 6 — FILES at once, each locked so no two workers take the same file.
echo "=== 1 · CONVERT $(date '+%T')"
export R JOBS WORK
tr '\n' '\0' < "$LIST" | xargs -0 -P "$FILES" -n 1 bash -c '
  pdf="$0"; stem="$(basename "$pdf")"; stem="${stem%.*}"
  [ -s "$R/$stem.txt" ] && exit 0
  mkdir "$WORK/lock/$stem" 2>/dev/null || exit 0
  echo "  start $stem  $(date +%T)"
  python3 tools/ocr-pages.py "$pdf" --out "$R" --lang epo --psm 6 --jobs "$JOBS" 2>&1 | tail -1'

# 2 · SEGMENT — every page also read at psm 4 (same image, same safety net).
echo "=== 2 · PSM 4 $(date '+%T')"
python3 tools/ocr-psm-both.py --pdfs "$LIST" --root "$R" --files 6 --jobs 3 2>&1 | tail -2

# 3 · RESOLUTION — pages stored as colour layer + sharp text mask, re-read at the mask's ppi (cap 400).
echo "=== 3 · TEXT-MASK RE-READ $(date '+%T')"
python3 tools/ocr-mask-reread.py --pdfs "$LIST" --root "$R" --jobs 16 2>&1 | tail -2

# 4 · CHOOSE per page among up to four readings, then assemble.
echo "=== 4 · ADJUDICATE · REBUILD $(date '+%T')"
python3 tools/ocr-psm-adjudicate.py "$R" --write "$RUNS/OCR-PSM-VERDICTS-$TAG.json" 2>&1 | tail -10
python3 tools/ocr-rebuild-combined.py "$R" --verdicts "$RUNS/OCR-PSM-VERDICTS-$TAG.json" 2>&1 | tail -1

# 5 · GATE — G2–G4 by text, G1 by the ink on the image.
echo "=== 5 · GATE $(date '+%T')"
python3 tools/ocr-accept.py "$R" --psm-used 4 --write "$RUNS/OCR-GATE-$TAG.md" 2>&1 | tail -5
python3 tools/ocr-g1-ink.py --pdfs "$LIST" --root "$R" --write "$RUNS/OCR-GATE-G1-$TAG.md" 2>&1 | tail -6

rm -rf "$WORK"
cat <<EOF
=== MACHINE STEPS COMPLETE $(date '+%T')

NOT YET ACCEPTED. By hand, per the spec, before any ACCEPTED line:
  · G1  — look at the «unread» pages in OCR-GATE-G1-$TAG.md (vision → a subagent). G1 is not a
          verdict until they are looked at.
  · G2  — every corpus with a second language (Ido corpora: French BY RULE) goes to
          tools/ocr-arbitrate.py; re-gate after.
  · G4  — below the bar: check the primary language and lexicon before calling it damage.
  · a sample page of every corpus looked at for handwriting / lithograph, if not done up front.
  · ACCEPTED lines go to the scout ONCE, in the signed form in the spec.
EOF
