#!/bin/bash
# cupel-russian — cupel step C4 for a batch with Russian: the Russian passes, for the batch's NEW items only.
#
#   tools/cupel-russian.sh <new-pdf-list> <garbage-filter models dir> <rus-fullpage manifest dir (new)>
#
# WHY (2026-10-03, cupel batch 2: the Soviet Esperanto press). The order of the September replication
# (`docs/REPLICATION.md`: forced Russian readings → layout → garbage filter → Russian search), each step held to the
# batch: (1) `ocr-russian-pages.py` finds the Cyrillic pages, reads them with the Russian model, writes `RUSSIAN.json`;
# (2) `ocr-orus-pages.py` the pre-reform (`orus`) reading of every page that has a Russian one; (3) `ocr-layout-mixed.py`
# the per-page layout (`LAYOUT.json`: which pages are bi-script); (4) `ocr-rus-fullpage.py` the full-page 300 dpi re-read
# (`rusfull`, images kept in the cache); (5) `ocr-garbage-filter.py apply` — the clean Esperanto (`eo-gate`, `eo-clean`) and
# Russian (`ru-clean`) of the bi-script pages, run on a SCRATCH ROOT of links to the new items, because `apply` rewrites
# every bi-script page of the root it is given. The Russian search and the every-reading search are rebuilt by
# tools/ocr-chain.sh, which follows.
# WRITE-SET: the new items' folders under the render root $R; the rusfull manifest dir (new). Run from the repo root.
set -euo pipefail
NEW="${1:?new pdf list}"; MD="${2:?garbage-filter models dir}"; RF="${3:?rusfull manifest dir}"
G=published/heterophony-resources/geniza; R=$G/sources/ocr-rendersearch
[ -f "$MD/ru.json" ] || { echo "no garbage-filter models in $MD (train them: ocr-garbage-filter.py train <root> <gate.json> $MD)"; exit 2; }
[ -e "$RF" ] && { echo "exists: $RF"; exit 1; }
# FROM=<n> (env): start at step n — e.g. FROM=3 after a restart (cupel batch 2, 2026-10-03 04:2x: steps 1–2 done; the
# layout pass was stopped and redone once the post-1918 rule was in place). SKIP_ORUS=1: skip step 2 on a post-1918 batch — by GENRE, never by date: only texts that never quote old print, such as the
# Soviet press (docs/FAILURE-MAP.md, the standing requirement of 2026-10-03 that Russian orthography is decided per page).
FROM="${FROM:-1}"
[ "$FROM" -le 1 ] && { echo "=== 1 · RUSSIAN PAGES $(date '+%T')"; python3 -W ignore tools/ocr-russian-pages.py "$R" --pdfs "$NEW" --jobs 10 2>&1 | tail -3; }
# 1b · FORCED RUSSIAN READINGS (2026-10-03, cupel batch 2's first G5 failed 5/40 and 8/40: step 1 reads only the pages
# its candidate rule picks, and passed over 1,126 bi-script pages, whose Cyrillic names were then never read). September's
# replication has the step (docs/REPLICATION.md, «FORCED RUSSIAN READINGS: --all-pages»); it was left out here.
# FORCE_ALL=1 reads EVERY page of the batch's items with the Russian model (the accept rule unchanged: a mixed page is never
# swapped whole). Default for a batch with Russian: set FORCE_ALL=1.
if [ -n "${FORCE_ALL:-}" ]; then
  ITEMS="=$(while read -r pdf; do [ -n "$pdf" ] || continue; s="$(basename "$pdf")"; printf '%s,' "${s%.*}"; done < "$NEW" | sed 's/,$//')"
  echo "=== 1b · FORCED RUSSIAN READINGS, every page $(date '+%T')"
  python3 -W ignore tools/ocr-russian-pages.py "$R" --pdfs "$NEW" --jobs 10 --all-pages "$ITEMS" 2>&1 | tail -3
fi
[ "$FROM" -le 2 ] && [ -z "${SKIP_ORUS:-}" ] && { echo "=== 2 · ORUS $(date '+%T')"; python3 -W ignore tools/ocr-orus-pages.py "$R" --pdfs "$NEW" --jobs 10 2>&1 | tail -3; }
[ "$FROM" -le 3 ] && { echo "=== 3 · LAYOUT $(date '+%T')"; python3 -W ignore tools/ocr-layout-mixed.py "$R" --pdfs "$NEW" --jobs 10 2>&1 | tail -3; }
echo "=== 4 · RUSFULL $(date '+%T')";      OMP_THREAD_LIMIT=1 python3 -W ignore tools/ocr-rus-fullpage.py --root "$R" --pdfs "$NEW" --out "$RF" --jobs 10 2>&1 | tail -2
echo "=== 5 · GARBAGE FILTER on the new items alone $(date '+%T')"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
while read -r pdf; do [ -n "$pdf" ] || continue; s="$(basename "$pdf")"; s="${s%.*}"
  [ -d "$R/$s" ] && { ln -s "$PWD/$R/$s" "$T/$s"; [ -f "$R/$s.txt" ] && ln -s "$PWD/$R/$s.txt" "$T/$s.txt"; }; done < "$NEW"
python3 -W ignore tools/ocr-garbage-filter.py apply "$T" "$MD" 2>&1 | tail -2
echo "=== DONE $(date '+%T')"
