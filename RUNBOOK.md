# cupel — the runbook: a placed scan into the geniza OCR corpus, with an absence class

Procedure as reviewed on 2026-10-04 through three cold dry runs.

## 1 · What cupel is

Trigger: «cupel <item>» or «cupel <batch>» (e.g. «cupel korzhenkov»).

Goal: each new item enters the corpus with a ledger class — ABSENCE-ADMISSIBLE, SPECIAL HANDLING or WITH EXCEPTIONS where the checks allow, PRESENCE ONLY where they do not — and, once the editor signs, `ACCEPTED:` lines in a new signed file. An item may be searched for absence only under a signed `ACCEPTED:` line (`tools/ocr-acceptance-lines.py` header).

The latchkey test (the editor set Korĵenkov as the latchkey test of cupel, 2026-10-03 20:1x): «cupel korzhenkov» is executed from this runbook alone, step by step, no step improvised and no fix made mid-run. Order (the editor ruled at 20:1x that the write-ups come before any latchkey test): the planned write-ups (an internal record, 2026-10-01, not published) are finished before the test runs. § 6 says what happens when a step fails.

Batches (D2: on 2026-10-03 00:1x the editor agreed, and asked that batching new additions together, for a more global sample, be the recommendation): new items are run as a batch — one conversion, one chain, one G5 sample across the batch. A batch of one item (Korĵenkov) is a batch. D4 (00:1x: the editor wanted Korĵenkov's precursors run before it, so that the scout of Korĵenkov is informed by them; Korĵenkov last): Korĵenkov runs after the precursor batch (batch 1, signed 02:21).

How each step is written: Run (the exact command) · Writes (its write-set) · Check (what must hold before going on) · If the check fails · Why (the ruling or failure-map row).

Where commands run: from the root of the project's working copy. Below, `$G` = `published/heterophony-resources/geniza` and `$R` = `$G/sources/ocr-rendersearch` (the tools use these same relative paths).

Placeholders: `<batch>` the batch name (`cupel3` for Korĵenkov unless the editor names it otherwise); `<date>` today, YYYY-MM-DD; `<batch-dir>` = `$G/sources/cupel-batch-<n>`; `<stem>` an item's name; `<suffix>` a chain's name, e.g. `<date>-<batch>`.

## 1a · The tests cupel applies: G1–G5, the classes, the signed line

(Added after the editor noted, 2026-10-04 03:1x, that cupel applied the G1–G5 tests without ever defining them. Defined here from the tools' own headers, which are the authority; the full write-up is `METHOD.md`. A cupel batch runs no test of its own: it runs these, through the chain (C7), the image sort (C9) and G5 (C11).)

**Why the tests exist.** An absence finding («X is not in this item») is only worth something if a silence in the text means a silence on the page. Three different facts look the same in the text — the page was blank, we failed to read it, the name is not there — so the tests separate them before any item may be searched for absence (`ocr-accept.py`: «the gate exists so that a NULL means something»).

**G1 — dead pages** (`tools/ocr-g1-ink.py`; run by the chain). The only test that looks at the IMAGE. A page whose text is under 25% of the item's median but whose image carries ink in line structure is a page we failed to read; no ink means the silence is real. Threshold 0. Pages it flags, or cannot decide («untested»: dark scans, photographs, covers), go to the **image sort** (C9): a blind checker sees each page beside its final text and sorts it NOTHING / MINOR (≤ 3 lines of masthead, caption or date missing) / LOST (a paragraph or more) / SCRIPT. Untested is never passed.

**G2 — a second language** (`tools/ocr-accept.py`; detected per ITEM, from its words against a noise floor calibrated on the item itself, then read on its pages). Where a second language is present, arbitration with that language's model must have run (`ocr-second-model.py`); an Ido item requires French by rule. Pending G2 blocks the class until it is done (the C7b.1 branch).

**G3 — shape** (`ocr-accept.py`, `page-shape.py`). Every page the shape test calls a list (rosters, address lists, columns) must have been read in column mode (`--psm 4`), or a member's number is severed from the member.

**G4 — lexicon** (`ocr-accept.py`). The median per-page share of words found in the item's language's word list (and a second language's where it is present): **at least 0.75 for prose, 0.65 for lists** — a page of surnames and towns scores lower by nature. On bi-script pages (`--script-segregated`) the Esperanto side alone is scored; the other script is presence only, unless the **Russian-only score** (the Russian side against the Russian list) reaches 40, in which case the Russian side is admissible too (the ledger's SPECIAL HANDLING / WITH EXCEPTIONS rules). The language table (C5) decides which pages are bi-script at all.

**What the gate cannot catch** (its header): handwriting and lithograph (excluded at C1 by looking); a second language in another script (silence, not damage — hence the language table); proper names (in no word list — hence G1 and G3 are not lexical, and G5 tests names).

**The classes** (`tools/ocr-absence-ledger.py`, one row per item, the CURRENT ledger):
- ABSENCE-ADMISSIBLE — passes G2–G4 and G1 is clean: absence may be claimed over the whole item, searching its search text.
- SPECIAL HANDLING — passes only by a special route (e.g. the Russian side, or a Russian-dominant item): absence only by searching EVERY reading of each page (`sources/ocr-rendersearch-all/`), the standing requirement of 2 Oct.
- WITH EXCEPTIONS — as admissible, but named pages or scripts are excluded (MINOR or LOST pages, the other script of bi-script pages, advertisement pages ruled out); absence only off those, on the side the row admits.
- PENDING — no valid verdict yet (G1 untested or unsorted, or stale inputs): a batch item may not stay PENDING at C11.
- PRESENCE ONLY — fails G4, too short, or unscoreable, or ruled so (e.g. Greek): presence findings only, never absence.

**G5 — the verdict-class audit** (`tools/ocr-g5-sample.py`; C11). The test of the tests: blind judges are shown pages drawn from each class and report coverage, orientation, how much Russian is printed, and up to 10 printed names; for each absence class, every listed name is searched in the text that class's search uses (`tools/ocr-name-search.py`), and a page is contradicted if two or more of its names are not found. Per class, 40 pages (all if fewer); the bar is ≤ 1 contradicted page at 40 and 0 below (editor 2026-09-30, 2026-10-04).

**The signed line** (`tools/ocr-acceptance-lines.py`; C12). An item may be searched for absence only if it carries an `ACCEPTED:` line, signed by the editor: corpus | pages | class · G4 | the search its class requires | the ledger's conditions verbatim (scope, sides, exclusions) | the ledger and G5 it rests on | the signature. Unsigned lines are `PROPOSED-ACCEPTED:` and no reader takes them up.

**Where each test runs** (added after the editor noted, 2026-10-04 03:1x, that the runbook did not make clear where each of G1–G5 is tested). A test is APPLIED in one step, from inputs other steps make; the steps that make the inputs run no test themselves.

| test | inputs made at | applied at | its result read at | if it fails |
|---|---|---|---|---|
| G1, dead pages | C4 (the readings), C7 rebuild (the final text) | C7, chain step 3 (`ocr-g1-ink.py`) | C7's check; finished by the image sort, C9, then the ledger re-run (C9) | C9: MINOR / LOST pages become named exceptions; vision only on the editor's word (C11a) |
| G2, language per page | C7b.1 (`ocr-second-model.py`, its `SECOND-MODEL.json`); vision, hand or ruled readings | C7, chain step 4 (the gate; Latin-script second languages only) | `g2_pending` in the gate's `OCR-GATE-<suffix>-segregated.md.json` (the report's G2 column lists languages, never «pending») | C7b.1, then one chain again (C7b.3) |
| G3, shape | C4 (the `--psm 4` reading of every page): where G3 is really met | C7, chain step 4 (the gate takes column mode from the chain's `--psm-used 4`, so G3 cannot fail there) | C4's check (every page has its psm 4 reading) | the editor (a conversion fault) |
| G4, lexicon | C4, C6 (the Russian passes, layout, garbage filter: the sides scored), C6.4.2 (ruled re-reads), C6.4.3 (the Georgian / Armenian mask), C7a (Fraktur), C7b.1 (the merges); not C7b.2 (small capitals feed the search text only) | C7, chain step 4 (the gate); the class from it at step 5 (the ledger) | C7's check; compared with the CURRENT ledger at C8 | the editor (an item under its bar is PRESENCE ONLY: the test working, not a failure of the run) |
| the classes | G1–G4 | C7, chain step 5 (the ledger); re-run at C9 | C8 (the compare), C9 (no PENDING row) | C8: a moved item outside the batch — stop |
| G5, the audit of the classes | the ledger after C9; C10 (scope) | C11 (`ocr-g5-sample.py` build, judges, file, score) | C11's score | diagnose; the editor's fix; a FRESH sample (C11) |
| the signed line | everything above | C12 | the editor | no signature, no line |

The missing-leaves and rotation checks (C6.4.1–2) are not gate tests: they make sure G1–G5 are run on every printed page, the right way up.

## 2 · Rules that hold at every step

1. Copyright. Scans, page images and text of in-copyright items stay in the gitignored `sources/`; nothing of them goes to a tracked file or a public place (draft, line 7: «All in copyright: images and text stay in the gitignored `sources/`»).
2. Keep page images. Never discard a render or an extraction (failure map, standing requirement of 2026-10-02, on the editor's request that image extractions not be discarded). `cupel-images-to-pdf.py` keeps `pages/`; renderers use `$G/sources/page-image-cache.noindex/`.
3. Kept folders only. Models, lists and keys a later run needs live under `$G/sources/` or the repo, never the session scratchpad (failure map, standing requirement of 2026-10-03; R4).
4. Read a tool's write-set before running it in a new way (R6; each tool header has a WRITE-SET line). No output over an existing file: the cupel tools refuse existing names; choose a new name, never delete the old.
5. One chain at a time; never rebuild or file while a chain runs (`tools/ocr-chain.sh` header; lock `$G/sources/.ocr-chain.lock`).
6. A fix to a shared module (`ocr_russian_reading.py` and the like) does not reach a process already running (R3). In the latchkey test any fix is a failure anyway (§ 6).
7. Russian orthography is decided per page, never by the date of the text (failure map, standing requirement of 2026-10-03; the editor ruled at 20:2x–20:3x that a history written after 1918 cannot be assumed to use Soviet orthography, and that where pre-reform text occurs cannot be judged by date, only by genre).
8. An absence search reads every reading on disk (failure map, standing requirement of 2026-10-02). SPECIAL HANDLING items are searched in `ocr-rendersearch-all/`.
9. Blind looks and G5 judges are AI checkers given the Read and Write tools only; they run no shell commands. Prepare their inputs first (the vision-batch header; an internal record, 2026-09-29, not published). Decision-bearing looks use at least 40 pages or spreads (an internal record, 2026-09-26, not published). A judge's return is filed intact, verbatim, with its key.
10. Vision (AI image reading) only where a check showed a quality problem; the quota is finite (`ocr-vision-batch.py` header; an internal record, 2026-09-30, not published).
11. Only the editor signs. Only the editor names a ledger CURRENT. Nothing is committed except what the editor stages.
12. Nothing in chat only. Every step that produces a result gets a dated entry at the top of the board (an internal log, not published); every misstep a row in `docs/FAILURE-MAP.md` § «cupel's first batches»; every open item a line in the queue of open items (an internal list, not published).

## 3 · The state to start from (read it from the board, not from here)

Before C0, read `$G/OCR-STATUS.md` (what is current, in one place) and the newest entries of `$G/ocr/OCR-BOARD.md`, and write down these names. As of 2026-10-04 15:3x they were:

| what | name on 2026-10-04 22:1x |
|---|---|
| CURRENT ledger | `$G/ocr/runs/OCR-ABSENCE-LEDGER-2026-10-04-list95b.tsv` (the editor made it current, 2026-10-04 22:15) |
| gate and G1 of the current state | `$G/ocr/runs/OCR-GATE-2026-10-04-list95b-segregated.md.json`, `$G/ocr/runs/OCR-GATE-G1-2026-10-04-list95b.md.json` |
| full PDF list | `$G/sources/OCR-PDF-LIST-2026-10-03-cupel2.txt` (one PDF per line; absolute paths and some repo-relative ones, both resolving from the repo root, C3) |
| latest merged psm verdicts | `$G/ocr/runs/OCR-PSM-VERDICTS-2026-10-04-list95b-merged.json` (the cupel2 verdicts with the list-page rule of 4 Oct applied by `ocr-psm-adjudicate.py --rechoose`) |
| language table / its evidence / look evidence | `$G/OCR-TEXT-LANGUAGES-2026-10-04.tsv` / `$G/ocr/runs/OCR-TEXT-LANGUAGES-EVIDENCE-2026-10-04.tsv` / `$G/ocr/runs/OCR-TEXT-LANGUAGES-LOOK-EVIDENCE-2026-10-03.tsv` and `…-03b.tsv` (the table's header line). Rebuilt 4 Oct 15:2x under the editor's cited rule (§ 1a, C5.3), so C5.3's check (b) sees only the batch's rows change. **Precondition:** the live table must be built by the CURRENT table tools; if `ocr-text-languages.py` or `ocr-text-languages-table.py` changed since the table's date, rebuild it first (as on 4 Oct) and put any change outside the batch to the editor before C0. |
| garbage-filter models | `$G/sources/gfmodels-2026-10-03/` |
| signed files (readers take the union; where an item has lines in two, the later file holds) | `OCR-ACCEPTANCE-LINES-2026-10-02-SIGNED.txt`, `…-2026-10-03-SIGNED-cupel1.txt`, `…-SIGNED-cupel2.txt`, `…-SIGNED-lang.txt` |

SETTLED (2026-10-04 00:1x): the base for C4 is the CURRENT chain's `--verdicts` file, read from its log, `$G/sources/ocr-work/ocr-chain-logs/CHAIN-<current suffix>.log` (the `+ python3 tools/ocr-rebuild-combined.py … --verdicts …` line). A log written before the folder move of 4 Oct names the file at its OLD path (`$G/OCR-PSM-VERDICTS-…`): take the file name from it and find it in `$G/ocr/runs/` (the move list, `$G/ocr/method/OCR-FOLDER-MOVE-LIST-2026-10-04.tsv`, gives every old and new path; one exception: it sends `OCR-PSM-VERDICTS-2026-10-03-cupel2-merged.json` to `runs/archive/`, but it was moved back to `runs/` the same day, failure map R11). On 4 Oct 22:1x (chain `2026-10-04-list95b`) it is `$G/ocr/runs/OCR-PSM-VERDICTS-2026-10-04-list95b-merged.json` (how to rebuild it: C4). If that file is missing (merged files are gitignored from batch 3 on), rebuild it first with `tools/cupel-merge-verdicts.py` (C4).

## 4 · The steps

### C0 · Precondition: the source is in place; nothing is running

The source comes in one of two kinds (the editor ruled on 2026-10-04 00:4x that cupel also runs on PDFs in `sources/`, not only on separate scan images in `scans/`, so the source may be a PDF rather than TIFFs):

- **(A) Placed scans** — TIFFs of spreads filed by placer under `$G/sources/scans/<item>/…` (Korĵenkov; batch 1). They go through C2 (split, PDF, look).
- **(B) A PDF already in `$G/sources/`** — a downloaded or delivered PDF, scanned or born-digital (cupel batch 2: the 53 *Meždunarodnyj Jazyk* and *Bulteno* PDFs). It skips C2: the PDF itself is converted.

For both:
- Run: check that no chain runs: the folder `$G/sources/.ocr-chain.lock` must not exist, and `pgrep -fl 'tools/[o]cr-'` must print nothing (the brackets keep the check from matching the shell that runs it). Check the free disk: `df -h $G` must show at least 50 GiB free PLUS room for the batch (its scans or PDFs again as page images, the readings, and one backup of each search folder: a few GiB for a book). Below 50 GiB the page-image cache stops keeping images (`ocr_page_images.py`, its disk guard), so the rule «keep page images» silently fails (4 Oct 13:2x: 27 GiB free).
- Writes: nothing.
- If the disk check fails: stop, for the editor (freeing space is the editor's; nothing of the OCR's is to be deleted for it).

For (A):
- Check: the scans are filed under a named folder with a manifest row (draft: «Precondition: placer has run — the scans are filed under a named folder with a manifest row»). The manifest is `interglossa/sources/scans/MANIFEST.md` (placer adds one row per placed scan, e.g. «`geniza/sources/scans/korzhenkov-historio-2005/slv-scan-2026-10-01/` …»), with placer's move log beside it (`MOVE-LOG-placer.txt`, `placer-move-log.md`). For Korĵenkov: `$G/sources/scans/korzhenkov-historio-2005/slv-scan-2026-10-01/`, 4 TIFFs, 65 spreads. Count the TIFFs against the manifest row, and count their FRAMES (each frame is one scanned image, a spread or a single page) against the manifest's spread count:

  ```
  python3 -c "import sys; from PIL import Image; print(sum(Image.open(f).n_frames for f in sys.argv[1:]))" <tiff> [<tiff> …]
  ```

  (Korĵenkov: 65. The frame count is what C2's console line is checked against.)
- If the check fails: stop. Placing is placer's step, not cupel's.

For (B):
- Check, three things:
  1. The PDF is registered. «Registered» means: some venture file names the PDF by its file name and gives its URL or provenance (the rule «record URLs for sources»). Neither the source register (an internal record, 2026-08-31, not published; one row per person or theme) nor the sources inventory (`$G/sources/_INVENTORY.md`, a map by folder) lists every file, so check by search, not by looking in one place:

     ```
     grep -rl --include='*.md' -F '<name>.pdf' $G published/heterophony-resources/interglossa | head
     ```

     A hit that gives the URL or how the file came (fetched from …, sent by …, scanned at …) is registered. No hit, or a hit without provenance: add one line, with the URL, to the `_INVENTORY.md` section for the PDF's folder before going on. Copyright PDFs stay in `sources/`, untracked.
  2. It is not already in the corpus: its name is not in the CURRENT full PDF list (`grep -c '/<name>.pdf$' <full list>` prints 0), and it is not the same file under another name — compare its size, then its checksum, with the corpus PDFs of the same size:

     ```
     s=$(stat -f %z <pdf>); while read f; do [ "$(stat -f %z "$f")" = "$s" ] && shasum "$f"; done < <full list>; shasum <pdf>
     ```

     (no line from the loop, or no matching checksum, = not a duplicate; the 28 Sep sweep found 56 duplicate groups, an internal record, 2026-09-28, not published).
  3. Its name will serve as the stem (`cupel-convert.sh` takes the stem from the PDF's basename): no spaces at the ends, unique, not an existing `$R/<stem>` folder.
- If the check fails: (1) register it first (with its URL), then go on; (2) a duplicate is not cupelled: note it on the board; (3) for the editor (renaming a source is not cupel's to do).

### C1 · Look at the source; name the item

- Run: open a few page images yourself, from the start, middle and end, rendered into a KEPT folder, `<batch-dir>/c1-look/` (`<batch-dir>` is `$G/sources/cupel-batch-<n>/`, C3; renders are never discarded and never put in the scratchpad, rules 2–3):
  - (A) frames of each TIFF (frame numbers from 0; Korĵenkov: frames 0, 10, 19 of each):

    ```
    python3 tools/cupel-tiff-frames.py --out <batch-dir>/c1-look <tiff> 0 10 19
    ```

    (one call per TIFF; it prints the TIFF's frame count, and refuses a frame past the last — Korĵenkov's fourth TIFF has 5 frames, so `0 2 4`; the PNGs are at a quarter of the scan's size, `<tiff name>-fNNN.png`)

    (a quarter of the scan's size, enough to see the script and the face; the full-size pages come at C2);
  - (B) pages of the PDF: `mkdir -p <batch-dir>/c1-look/<name>; pdftoppm -r 100 -f N -l N -png <pdf> <batch-dir>/c1-look/<name>/p` for a few N. Note whether it has a text layer (`pdftotext -f N -l N <pdf> -` prints text). The conversion (C4) reads the layer as one more COMPETING reading, `page-NNNN.tl.txt` (`tools/ocr-textlayer.py`, step 3b of `cupel-convert.sh`; ruled 2026-10-04 12:4x, § 7): it can win a page in adjudication; it replaces nothing and is not ground truth. Note on the board whether the PDF has a layer, and whether it looks born-digital (no page image, or a small one) — see § 7, point 2.
- Writes: the renders in `<batch-dir>/c1-look/` (kept); a board entry (C1 below).
- Check, four things:
  1. Print the OCR can read. Handwriting and lithograph return confident nonsense that no later step detects (the rule in `ocr-run-corpus.sh`, draft C0): such an item is not cupelled. FRAKTUR (blackletter) is NOT excluded (the editor ruled on 2026-10-04 01:0x that Fraktur, unlike handwriting and lithograph, is salvageable): note it — whole item, or which pages — and it takes the Fraktur re-read of C7a. A blackletter-style face in a title or heading only is ordinary print.
  2. The scripts on the pages: any Cyrillic, Greek, Georgian, Armenian, Hebrew? As running text, or as a few names and titles? This feeds C5.
  3. (A) A stem: lower case, unique (the name-collision rule, draft C2), in the form of batch 1 (`li-kaj-ni-1985`, `manders-1950`). For Korĵenkov, e.g. `korzhenkov-historio-2005`. The stem must not already be a folder `$R/<stem>` and must not be in the full PDF list (`grep -c '/<stem>.pdf$' <full list>` prints 0). `cupel-convert.sh` skips a stem already converted, so a name collision would silently reuse old pages.
  4. (B) Spreads inside the PDF (two printed pages on one PDF page): the split tool takes images, not PDFs, and no tool splits a PDF's pages; stop, for the editor.
  For (B) the stem is the PDF's name (C0).
- If the check fails: (1) stop, for the editor; (3) choose another stem; (4) stop, for the editor.

### C2 · Spreads to pages to PDF; EVERY cut looked at — (A) placed scans only

For (B), a PDF already in `sources/`, skip to C3.

Why: D1 (the editor chose option (b) at 00:1x: (a) had been done only because Kapis of BitArkivo required it, and (b) has worked well): an automatic split at the gutter, and every cut checked before any OCR (the editor ruled on 2026-10-04 01:3x against a blind sample of the cuts as too risky for content, unlike a sample of names: every page must be looked at, not a blind 40). A sample suits a measure (G5's names); a cut that loses text loses it for good, so no cut goes unseen.

- Run, one item at a time, the TIFFs in reading order:

  ```
  python3 tools/cupel-images-to-pdf.py --stem <stem> --out <batch-dir>/<stem> --look-all <tiff> [<tiff> …]
  ```

- Writes, into the new folder `<batch-dir>/<stem>/` (refused if it exists): `<stem>.pdf` (lossless, the scan's dpi kept), `pages/page-NNNN.png` (kept), `SPLIT.tsv` (per frame: the fold x, the ink share at the cut, MOVED where the second pass moved the cut), `look/NN.png` (40 spreads, the doubtful first, shuffled, a red line at the cut) and `look/KEY.tsv` (image to frame and cut).
- The tool, for the record: a frame wider than 1.15 × its height is a spread; it is cut at the fold — among print-free columns, the darkest (the binding shadow); on a flat scan with no shadow, the gutter column nearest the item's usual fold (the flat-scan rule, after look 4); a second pass searches within 200 px of the item's median confident fold, so a blank page cannot draw the cut. Nothing is deskewed or cropped.
- Check: the console line («N frames · S spreads split · P pages»): N = the frame count of C0. S and P are recorded on the board, not checked against the manifest (the manifest gives spreads «as the brief gives them», not how many frames are single pages); P = 2 × S + (N − S) is checked. Then the look at EVERY spread (`--look-all` puts every spread in `look/`, shuffled): checkers, Read tool only, about 20 images each (one checker per `look/` slice: `01.png`–`20.png`, `21.png`–`40.png`, …; never `KEY.tsv`), each given this brief, with its slice's paths filled in:

  > You are checking where a scanned book spread will be cut into two pages. Use ONLY the Read tool. Do not run commands and write no files. Read each of these images: `<the slice's look/NN.png paths>`. Each shows one spread, two printed pages side by side, with a red vertical line where the software will cut it. For each image, answer one question: **does the red line cross or touch print?** Print is any letter, digit, accent, rule, ornament or picture. Answer CLEAN if the line runs only through blank paper or the gutter; TOUCHES if it touches the edge of a printed mark; CUTS if it passes through one. Add a short note: where (head, middle, foot of the page; which line of text), and say so if the line runs through a page that is entirely blank. Do not open any other file. Return a table and nothing else, one row per image: `image | CLEAN / TOUCHES / CUTS | note`.

  Check that every image of `look/` has a row (the count of rows = S). Pass: no cut through print — every spread CLEAN, or its line inside a blank page (noted). Any TOUCHES or CUTS through print fails the item (looks 2, 3 and 6 passed; look 1 failed at 15 / 4 / 1).
- Filing: the return, verbatim, with the key, into `<batch-dir>/<stem>/look/RETURN.md`, and the result on the board.
- If the check fails: do not tune the tool (that is a patch, § 6). The ruled branch is the overlap cut (ruled by the editor at 00:4x, for *Li kaj Ni*, whose text curves into a narrow gutter at the head of the page, so no straight cut clears it): on the editor's word, re-run into a NEW folder, `<batch-dir>/<stem>-overlap/`, with the SAME `--stem <stem>` (so the PDF is still `<stem>.pdf`) and `--overlap 80 --look-all`; the failed folder `<batch-dir>/<stem>/` is kept (§ 6, rule 3), and C3 takes the PDF from the overlap folder. Then fresh checkers over EVERY spread, with the brief above changed to the overlap question: «Each image shows one spread with TWO red vertical lines. The left-hand page keeps everything up to the RIGHT line; the right-hand page keeps everything from the LEFT line (`tools/cupel-images-to-pdf.py`, the overlap crop). **Is any letter cut off** — does the RIGHT line cut a letter of the left-hand page, or the LEFT line cut a letter of the right-hand page? (A few letters of the facing page between the lines are harmless.) Answer SAFE or CUT, with a note.» Pass: every spread SAFE (look 7, a sample of 20 before the every-spread rule: 20 / 20).
- RULED (editor 2026-10-04 01:3x, superseding the editor's 00:0x ruling of a 40-spread sample): **EVERY spread is looked at** — no sample, of 20 or 40. Looks 1–7 (20 each) predate the rule.
- RULED (editor 00:0x): only a cut through PRINT fails the look. A cut line inside a blank page (look 1 no. 19; looks 4 and 5 no. 09) is noted in the return and does not fail it.

### C3 · The lists: which PDFs each later step works on

What and why (expanded after the editor asked, 2026-10-04 03:0x, for more text at the start to motivate this step, and which lists were meant). The tools take their work from plain lists, not from folders, and a batch needs THREE of them, because some steps must touch ONLY the new items and others must see the WHOLE corpus:

1. **The batch's own PDF list** — `$G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt`: the absolute path of each new PDF, one per line, and nothing else. The steps that read or write page files use it: the conversion (C4, `cupel-convert.sh`), the Russian passes (C6.2, `cupel-russian.sh`), the Ukrainian reading (C6.3). Why only the new items: these steps write readings and verdicts, and run over the whole corpus they would re-read or re-judge items already accepted and signed. That happened once in planning: `ocr-run-corpus.sh` would have rebuilt every item from the new items' verdicts alone (failure map R6).
2. **The full corpus PDF list** — `$G/sources/OCR-PDF-LIST-<date>-<batch>.txt`: the CURRENT full list (the one the last chain used, from its log) with the new lines appended. The steps that judge the corpus as a whole use it: the chain (C7: rebuild, G1, gate, ledger — so the ledger compare of C8 can show that nothing already accepted moved), the Fraktur re-read's page images (C7a), the G5 sampler (C11, which renders the pages it samples). Why the whole: a ledger built over the new items alone could not be compared with the current one, and an old item missing from the list would silently drop out of the corpus.
3. **The items file** — `<batch-dir>/ITEMS.txt`: the new items' STEMS (the PDF names without folder or `.pdf`), one per line. The steps that pick items by name use it: the old-letter count (C6.2, `ocr-orus-choices.py --items`), G5 (`--items`), the acceptance lines (C12, `--items`). Why a separate file: these tools take item names, not paths; and one per line, because names with spaces broke a space-separated list (R7, the *Bulteno* names).

The three must agree: the items file is made FROM the batch list, and the full list is the current list PLUS the batch list, so a typo cannot make them differ.

- Run (plain shell; Korĵenkov's example in the comment):

  ```
  # (A) placed scans: the PDF of the folder whose look PASSED, one per item — <batch-dir>/<stem>/<stem>.pdf,
  #     or <batch-dir>/<stem>-overlap/<stem>.pdf where the overlap re-run was ruled (C2); never both
  for s in <stem> [<stem> …]; do d=<batch-dir>/$s; [ -d "$d-overlap" ] && d="$d-overlap"; echo "$PWD/$d/$s.pdf"; done \
    > $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt
  # (B) PDFs already in sources: their absolute paths, one per line (batch 2's list was made so)
  ls $PWD/$G/sources/<name>.pdf … > $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt
  # a batch may mix (A) and (B): append the (B) lines to the (A) list
  cat <full list> $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt > $G/sources/OCR-PDF-LIST-<date>-<batch>.txt
  sed -E 's#.*/##; s#\.pdf$##' $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt > <batch-dir>/ITEMS.txt   # one stem per line, (A) and (B) alike (R7)
  ```

- Writes: the batch's own list (`…-NEW.txt`), the new full list, the items file.
- Check: every line of both lists names an existing PDF, either as an absolute path or as a path relative to the repo root (the cupel2 list has both; the tools are run from the repo root, so both resolve; corrected after the cold dry run, which found lines 2890–2908 relative); the new list has exactly the batch's PDFs; the full list = the old one plus those lines; the items file has one stem per line and nothing else (R7: item lists split on spaces broke the *Bulteno* names; both tools now read one item per line).
- If the check fails: fix the list (it is this step's own output) and check again.
- SETTLED (00:1x): names as used by batches 1 and 2 — the batch's own PDFs `$G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt`; the whole corpus after the batch `$G/sources/OCR-PDF-LIST-<date>-<batch>.txt` (the previous full list plus the NEW lines); the items, one stem per line, `<batch-dir>/ITEMS.txt` (batch 2: `sources/cupel-batch-2/ITEMS.txt`). The batch folder `<batch-dir>` is `$G/sources/cupel-batch-<n>/` (batch 3: `cupel-batch-3`), and `<batch>` is `cupel<n>` (`cupel3`) — the form of batches 1 and 2 (corrected 2026-10-04 after the cold dry run, which found two forms).

### C4 · Convert the batch's new PDFs only

What this step does for the tests (added after the editor noted, 2026-10-04 03:1x, that the same explanation was needed for the tests that bear on steps other than C7). No test runs here, but C4 makes the readings two of them depend on: every page is read twice, in block mode (`--psm 6`) and in column mode (`--psm 4`, `ocr-psm-both.py`), plus a re-read at the text mask's resolution; and each page gets a verdict (the merged psm verdicts) saying which reading is better. **G3** (C7, the gate) requires the column-mode reading of every list-shaped page — it exists only because this step made it. **G4** reads whichever reading the verdicts chose. A page this step does not read is a page no later test can see.

Why: R6 — `ocr-run-corpus.sh` would have rebuilt the whole corpus from the new items' verdicts alone (its step 4 adjudicates over the whole root). Never use `ocr-run-corpus.sh` for a batch.

- Run:

  ```
  tools/cupel-convert.sh $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt <base merged verdicts> $G/ocr/runs/OCR-PSM-VERDICTS-<date>-<batch>-merged.json
  ```

  `<base merged verdicts>` is the file named in § 3 (from 4 Oct: `$G/ocr/runs/OCR-PSM-VERDICTS-2026-10-04-list95b-merged.json`). That file is the cupel2 verdicts with the list-page rule of 4 Oct applied, so it is NOT base + batch files; if it is missing (merged files are gitignored), rebuild it in two steps: `tools/cupel-merge-verdicts.py` gives `…-2026-10-03-cupel2-merged.json` (now in `runs/archive/`), then `python3 tools/ocr-psm-adjudicate.py x --rechoose <that file> --write $G/ocr/runs/OCR-PSM-VERDICTS-2026-10-04-list95b-merged.json`.
- Writes: the new items' folders `$R/<stem>/` and `$R/<stem>.txt` (psm 6, psm 4, the text-mask re-read, and the PDF's own text layer as `page-NNNN.tl.txt` where it has one — step 3b, approved by the editor, 2026-10-04; a placed scan's PDF from C2 has none); the merged verdicts `…-<batch>-merged.json` AND the batch's own `…-<batch>-batch.json`. Both refused if they exist; the existing items are never touched.
- Check: the last lines say «=== DONE» and «B + N verdicts → … ; the batch's own → …», N = the batch's page count. One folder per stem in `$R`.
- Tracking (approved by the editor at 18:2x, on condition that the history is kept, and on the expectation that the psm verdicts will not keep growing): only the batch file is tracked; merged files are gitignored from batch 3 on, and a merged file is rebuilt as `2026-09-30-merged` + each batch file in order (2026-09-30-merged 115,177 + cupel1-batch 328 + cupel2-batch 2,983 = cupel2-merged 118,488).
- If the check fails: «refusing: … new verdicts name pages already judged» means a stem collides with an existing item: stop (C1.3 was missed). Any other failure: stop, § 6.
- SETTLED (00:1x): `tools/cupel-merge-verdicts.py <base merged> <batch files in order> --out <merged>` rebuilds a merged file (written 2026-10-04; checked: base + cupel1-batch + cupel2-batch is identical to cupel2-merged, 118,488 verdicts). Use it whenever a merged file is missing.

### C5 · Declare the languages; rebuild the language table

Why: the Russian reader refuses an item not in the language table (`ocr_text_languages.py`: «the Russian reader refuses such items (rebuild the table first, cupel runbook)»; `ocr-text-languages-table.py`: «a batch's languages are declared here at intake and the table rebuilt before its Russian passes»). The table is the filter (the editor ruled at 18:1x that the table mapping texts to the languages they contain should have acted as a filter, and that it must track all languages, not only Latin-script ones). A fresh scan has no authoritative reading (no text layer, no vision, no hand keying), so its non-Latin languages can only come from a declaration. Cited languages never license a model run, a search file or a bi-script label (`ocr-text-languages-table.py`, CITED).

C5.1 · Nothing to run: the new items are already visible to the evidence tool. (SETTLED 2026-10-03 23:4x, approved by the editor, on the gap this draft found: the evidence tool used to list only items with `PREFERRED.tsv`, which the chain's rebuild writes, so a new item could not be declared before its Russian passes. `tools/ocr-text-languages.py` now lists every item folder with page readings — `page-0001.txt` from C4 — and counts pages from them when there is no `PREFERRED.tsv`. Checked: the 2,952 existing items' evidence is unchanged; a simulated new item with only page readings is listed with its page count. The rebuild's `--preferred-only` was NOT chosen: it rewrites records for every item.)
- Check: after C4, each batch item has `$R/<item>/page-0001.txt`. If not, C4 did not finish: stop, § 6.

C5.2 · Declare.

- Run: edit `DECLARED = {}` in `tools/ocr-text-languages-table.py` — one entry per item: item-name prefix → (languages, provenance), e.g.

  ```
  DECLARED = {"korzhenkov-historio-2005": (("esperanto",), "cupel <batch>, C1 look <date>; editor <date HH:MM> «…»")}
  ```

  Languages are the table's names (`esperanto`, `russian`, `ukrainian`, `greek`, …; `russian-cited` for a few names or titles). This edit is a planned step of the procedure (the tool's own comment), not a patch.
- Who decides — RULED (editor 2026-10-04 00:0x: the operator proposes, the editor must confirm): the operator PROPOSES from the C1 look (a language printed as running text on at least 5% of the pages is declared; names and titles only are declared `-cited`, which licenses nothing — the table's CITED and CITED_SHARE), and the EDITOR CONFIRMS before C5.3. No declaration enters `DECLARED` unconfirmed; the confirmation is quoted in the entry's provenance. This stop is part of the procedure, not an improvisation.

C5.3 · Rebuild the evidence and the table, under new dated names.

- Run:

  ```
  python3 tools/ocr-text-languages.py $R <current gate .md.json> --out $G/ocr/runs/OCR-TEXT-LANGUAGES-EVIDENCE-<date><x>.tsv
  python3 tools/ocr-text-languages-table.py $G/ocr/runs/OCR-TEXT-LANGUAGES-EVIDENCE-<date><x>.tsv \
      $G/ocr/runs/OCR-TEXT-LANGUAGES-LOOK-EVIDENCE-2026-10-03.tsv $G/ocr/runs/OCR-TEXT-LANGUAGES-LOOK-EVIDENCE-2026-10-03b.tsv \
      --out $G/OCR-TEXT-LANGUAGES-<date><x>.tsv
  ```

  `<x>` is a letter after the newest table's (on 3 Oct the newest is `2026-10-03d`, so `2026-10-03e`; on a later date, no letter). The lookup takes the newest name that matches `OCR-TEXT-LANGUAGES-YYYY-MM-DD[x].tsv` (`ocr_text_languages.py`), so the new table must sort last.
- Writes: the two TSVs; each refused if it exists. Both tools read only.
- Check: (a) each batch item has a row, with `declared:` in its evidence and the declared languages in `languages`; (b) every other row is unchanged against the previous table (`diff <(grep -v '^#' <old table>) <(grep -v '^#' <new table>)` shows only the batch's rows); (c) no batch row is flagged DOUBT or RUS-READ-NO-RUSSIAN.
- If the check fails: (a) a missing row: the item has no page readings (C4) or its folder name differs from its PDF's: stop, § 6. (b) Changed rows of other items: stop and surface to the editor; no Russian pass until ruled. (c) DOUBT: for the editor.

### C6 · Second-script passes, only where the table licenses them

What this step does for the tests. No test runs here; it makes the readings **G4** needs for any text with another script, and the Russian search an absence claim reads. The forced Russian reading of every page, the layout pass (which pages are bi-script) and the garbage filter (which splits a bi-script page into its Esperanto and its Russian side) are what let the gate (C7) score the Esperanto side alone and give the Russian side its own score; without them, Russian on a page reads as Latin junk and drags G4 down, or is never read at all (R5: names missed). Only the texts the language table licenses (C5) get these passes.

If the table lists no licensed Cyrillic language for any batch item, skip C6.1–C6.3 (the Cyrillic passes; `ocr-russian-pages.py` skips texts with no Cyrillic language; a cited language licenses nothing). **C6.4 and C6.5 always run**: they are not about Cyrillic (corrected 2026-10-04 after the cold dry run, which found that «skip C6» skipped the missing-leaves check a scanned book needs).

C6.1 · Orthography marker — only by genre, only on the editor's ruling.

- `SKIP_ORUS=1` and the marker file `$R/<stem>/ORTHOGRAPHY-POST-1918` are for texts that never quote old print: periodicals written and printed under the post-reform spelling: the post-Revolutionary press, Soviet and post-Soviet (the editor ruled on 2026-10-04 that it applies to the post-Soviet press too; first applied to cupel batch 2, on the editor's ruling at 04:09 that batch 2's press is Soviet-era). Never set from a date; never on a history, bibliography, dictionary or linguistics text, whatever its date (failure map, standing requirement of 2026-10-03; draft C4 «CORRECTED 3 Oct 20:3x»). Korĵenkov's *Historio de Esperanto* (2005) is a history: no marker, no SKIP_ORUS; the old-letter rule decides per page.
- Run, for a ruled post-Revolutionary press item only, before C6.2: `touch $R/<stem>/ORTHOGRAPHY-POST-1918`.
- Why the marker exists at all: R1 — on bi-script pages the pre-reform model reads the Esperanto as Cyrillic, Latin i as «і» («пасіеса» = nacieca); 103 of batch 2's 1,857 Russian pages went to `orus`. R2: running `orus` on a Soviet-era batch wasted machine time and caused those misreadings.

C6.2 · The Russian passes, forced on every page, BEFORE the first chain.

Why: R5 — `ocr-russian-pages.py` alone reads only the pages its candidate rule picks; it passed over 1,126 of batch 2's 2,983 pages, and the first G5 failed (SPECIAL HANDLING 5 / 40, WITH EXCEPTIONS 8 / 40, the misses nearly all Cyrillic names). After `FORCE_ALL=1` a fresh G5 passed (0 / 40, 1 / 40). R9 — the forced reading run AFTER a chain once demoted the accepted Russian pages; the tool was fixed, and the lesson stands: the forced reading belongs before the first chain.

- Check first: `$G/sources/gfmodels-2026-10-03/ru.json` exists (the script refuses otherwise). These are the kept, seeded models of 3 Oct (R4); never the scratchpad.
- Run (add `SKIP_ORUS=1` before `FORCE_ALL=1` only after C6.1's ruling; it is long, so it runs detached like the chain, its output in `<batch-dir>/RUSSIAN.log`; the rusfull MANIFEST folder goes to `sources/ocr-work/`, with the earlier ones since the folder move — the readings themselves go into the items' folders).   CORRECTED 2026-10-04 (the cold dry run: copying batch 2's `OVERNIGHT3.sh` would carry its restart flags `FROM=3` and `SKIP_ORUS=1`, and it runs the chain before this step's checks and before C6.3). Run C6.2 on its own, detached, logging to the batch folder — no `FROM` (a first run starts at step 1), `SKIP_ORUS=1` only by genre (C6.1):

  ```
  FORCE_ALL=1 nohup caffeinate -i -s tools/cupel-russian.sh $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt $G/sources/gfmodels-2026-10-03 $G/sources/ocr-work/ocr-rusfull-<date>-<batch> > <batch-dir>/RUSSIAN.log 2>&1 &
  ```

  When it ends («=== DONE» as the log's last line), do this step's checks, then C6.3–C6.5; the chain (C7) only after all of them. Batch 2's drivers (`sources/cupel-batch-2/OVERNIGHT*.sh`) are records of restarts, not templates; the first of them lacked `FORCE_ALL=1` (R5).

- Writes: in the new items' folders only — `page-NNNN.rus.txt` and `RUSSIAN.json` (steps 1 and 1b), `page-NNNN.orus.txt` (step 2, unless SKIP_ORUS), `LAYOUT.json` (3), `rusfull` readings (4; images kept in the cache), the garbage filter's clean Esperanto and Russian (`eo-gate`, `eo-clean`, `ru-clean`; step 5, on a scratch root of links to the new items, because `apply` rewrites every bi-script page of the root it is given); the new rusfull manifest folder (refused if it exists).
- Check: «=== DONE» at the end; every item has `RUSSIAN.json`; nearly every page has a `.rus.txt` (batch 2: 2,922 of 2,983); the accept tally is plausible. Then count the pages the old-letter rule sends to `orus` per item: on a post-Revolutionary press item, about 0; on any other text, the pages it sends to `orus` get a blind look (≥ 40, or all) — «do they print pre-reform Russian?» (failure map, standing requirement, point 3; the 3 Oct orthography look). Since 3 Oct a wrong `orus` pick loses nothing: where the rule picks `orus`, the Russian search file carries the `rus` reading too.
- If the check fails: stop. A step that stopped part-way can be restarted with `FROM=<n>` (the script's header: e.g. `FROM=3` after a restart), with a NEW manifest folder name, `$G/sources/ocr-work/ocr-rusfull-<date>-<batch>-r<n>`, `<n>` the step restarted from (the script refuses an existing one, line 20; the first run's folder stays), logging to `<batch-dir>/RUSSIAN-r<n>.log`. What `FROM` skips (`cupel-russian.sh` lines 25–40): steps 1, 2 and 3 below `<n>` only; step 1b runs whenever `FORCE_ALL=1` is set (leave it off if 1b had finished), and steps 4 and 5 always run. Restart from the first step whose «=== n ·» line has no finished output after it; that is a defined restart, but in the latchkey test any stop is logged (§ 6).
- SETTLED (00:1x): `tools/ocr-orus-choices.py $R --items @<batch-dir>/ITEMS.txt` (written 2026-10-04, reads only) prints per item: pages with both readings, to `orus`, to `rus`, and the marker. Check: an item sending many pages to `orus` is either pre-reform print or a case for the marker by GENRE (the Soviet press only) — for the editor, never by date.

C6.3 · Ukrainian, where the table lists it.

- Run: `python3 tools/ocr-ukr-pages.py $R --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt` (try `--dry` first).
- Writes: `$R/<item>/page-NNNN.ukr.txt` for the scanned pages of the table's Ukrainian texts, never over an existing file. The chain's Russian companion writes the reading beside the Russian ones and admits a Ukrainian page at ≥ 20 Ukrainian words.
- Why: Ukrainian і is not pre-reform evidence (the editor noted at 20:4x that Ukrainian has both the decimal і and the octal и, so і there is no sign of pre-revolutionary spelling); Ukrainian goes to its own model, not to the orus / rus choice.
- Check: the batch's Ukrainian items, and only those, gain `.ukr.txt` files.
- SETTLED (00:1x): the tool no longer needs `PREFERRED.tsv` — for a new item without one it takes every page (2026-10-04), so it runs here, before the first chain. Pass the full corpus list: the tool reads only the table's Ukrainian texts and only pages without a `.ukr.txt`, so earlier items cost nothing (the batch's NEW list works too, as long as no earlier Ukrainian item is missing a reading).

C6.4 · Missing leaves, rotation, Georgian and Armenian — before the first chain

(Written 2026-10-04 after the cold dry run, from the tools' code; the findings per tool and line numbers are in an internal record, 2026-10-04, not published. `ocr-rotation-flag.py`, named in old notes, is retired: the conversion honours a PDF's /Rotate itself.)

What this step does for the tests. No gate test sees a page that was never scanned, or a page read upside down as junk: G1 sees text where there is ink, G4 a low score, and nothing says why. An absence claim over an item with a missing leaf would cover printed pages that are not there. So every item gets two checks that read only — the printed page numbers (missing leaves) and the turned readings (rotation) — and an item with Georgian or Armenian gets its own readings, so that G4 scores the Esperanto side alone. All three need only C4's readings (and, for the mask, C6.2's), so they run before the chain and their results are in its first text. Record for each item on the board which ran and what they found.

C6.4.1 · Missing leaves — every item, by default.

- Run: make the item pattern from the items file (an anchored regular expression; the tool matches it against every folder name), check the output name is free, then the check:

  ```
  python3 -c "import re,sys; print('^(' + '|'.join(re.escape(l.strip()) for l in open(sys.argv[1]) if l.strip()) + ')$')" <batch-dir>/ITEMS.txt
  ls $G/ocr/runs/OCR-PAGE-SEQUENCE-<date>-<batch>.tsv          # must say: No such file
  python3 tools/ocr-page-sequence.py scan --out $G/ocr/runs/OCR-PAGE-SEQUENCE-<date>-<batch>.tsv --items '<the pattern printed above>'
  ```

  For a new issue of a periodical already in the corpus, use the title's prefix instead (e.g. `--items '^BultenoTEKS'`), so that the join with the neighbouring issues is tested; the other issues' rows are not the batch's and need nothing.
- Writes: the TSV only (the tool overwrites, hence the `ls`). It reads only.
- Check: each batch item's row, column 2:
  - COMPLETE: nothing missing. Done.
  - GAP, or a «JOIN … missing before <batch item>» in any row's evidence: the strip look (below).
  - LEAD: the tool gives it for a step up and a step back in the numbering, and also to an otherwise COMPLETE item whose evidence has a REPEAT, JOIN or SHORT (`ocr-page-sequence.py` line 214). Route each by its evidence (the 13:2x ruling, § 7 point 3): a JOIN → the strip look (below; `build` takes JOINs whatever the verdict); a REPEAT, or a step up and back → the NEIGHBOUR LOOK (below) on the scan pages the evidence names, the operator giving the leads ids `L01`, `L02` …; SHORT only (no pages named) → the board, for the editor.
  - PARTLY-VERIFIED (the numbering could not be followed over the whole item) or CANT-TELL (too few printed numbers): on the board, for the editor's ruling per item (§ 7 point 3). A whole book often comes out PARTLY-VERIFIED (unnumbered front matter, plates): expect this stop, and give the editor the row (scan_pages, numbered, first and last printed): the tool does not write which stretch it could not follow.
- The strip look, for GAP and JOIN leads. Keep only the header and the rows that name a batch item (else old leads go to vision again), then build, from the FULL list (a JOIN needs the next issue's PDF):

  ```
  (head -1 $G/ocr/runs/OCR-PAGE-SEQUENCE-<date>-<batch>.tsv; grep -F -f <batch-dir>/ITEMS.txt $G/ocr/runs/OCR-PAGE-SEQUENCE-<date>-<batch>.tsv) > <batch-dir>/pagenum-leads.tsv
  python3 tools/ocr-page-number-look.py build --seq <batch-dir>/pagenum-leads.tsv --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --out <batch-dir>/pagenum-look
  ```

  Writes `<batch-dir>/pagenum-look/bNN/NNN.png` (24 strips a batch) and `KEY.tsv`. The tool does not refuse an existing folder: `<batch-dir>/pagenum-look` must be new. Then one checker per bNN, Read tool only, never `KEY.tsv`, with this brief (its slice's paths filled in):

  > You are reading printed page numbers. Use ONLY the Read tool. Do not run commands and write no files. Read each of these images: `<the bNN/NNN.png paths>`. Each image shows the top strip and the bottom strip of one scanned page, stacked; the images are consecutive scanned pages. For each image, report the printed page number you see, exactly as printed (two numbers if two are printed, e.g. «58 / 14»), or NONE if there is none or it is a Roman numeral. Do not guess a number from the order of the pages. Return a table and nothing else, one row per image: `| NNN | printed page number(s) as printed, or NONE | note |`, NNN the image's three-digit name.

  (The columns are those of the 29 Sep returns, `sources/ocr-work/ocr-scratch-2026-09-29/pnlook-returns.md`; that look's brief is not on file; `judge` reads the first two columns.) File the returns verbatim, with the key, in `<batch-dir>/pagenum-look/RETURNS.md`, then judge:

  ```
  python3 tools/ocr-page-number-look.py judge --out <batch-dir>/pagenum-look --returns <batch-dir>/pagenum-look/RETURNS.md > <batch-dir>/pagenum-look/JUDGE.md
  ```

- Check: every lead has a verdict. REFUTED: nothing missing. CONFIRMED, IRREGULAR or UNREADABLE: the neighbour look — the whole pages either side of the gap, one page more each side ((A): `<batch-dir>/<stem>/pages/page-NNNN.png`, which is PDF page N; (B): `mkdir -p <batch-dir>/gap-look`, then `pdftoppm -r 100 -f N -l N -png <pdf> <batch-dir>/gap-look/<stem>-p` for each page, kept), one checker per 20 or so, Read tool only, with this brief (the 29 Sep brief, `sources/ocr-work/ocr-review-2026-09-29/gaps/BRIEF-01.md`, with its own leads taken out; fill in the images and the leads):

  > USE ONLY THE Read TOOL. No shell commands, no files written, no directory listings. Read each image listed below, in order: `<the image paths>`. Context: these are scans of a book or periodical. A check of the printed page numbers found places where printed pages may be missing from the scan. The leads: `<per lead: its id, the item, the PDF pages shown, and the printed numbers expected to be missing>`. The images are consecutive PDF pages around each place (one extra page each side; the PDF page numbers may be off by one, so read the printed numbers yourself). For EACH image report one line: image | printed page number you see (or NONE) | TOP: does a new chapter/article/section begin at the top (heading)? | BOTTOM: does the text stop partway down (end of a piece), run to the bottom, or is the page blank / a plate / an advertisement? | a few words on what the page is. Then for EACH lead give a verdict line: for each missing printed page, one of BLANK-LIKELY (the page before ends a piece AND the page after begins a new one), LOST (the text runs on across the gap, or a piece is visibly interrupted), UNCLEAR — with a one-line reason quoting what you saw (e.g. last words before, first words after). For a JOIN lead (the end of one issue and the start of the next file): does the first file end its issue, and does the second begin a new issue? Report the issue numbers or dates on the mastheads and the printed page numbers, and say whether the numbers imply a whole issue (or supplement) missing between them. For a REPEAT lead (no page missing): is a page scanned twice, or does the printed numbering restart (a new part, a reissue)? Answer TWICE, RESTART or UNCLEAR, with what you saw. Be literal: report what the page shows, not what you expect.
 File the return verbatim with its key in `<batch-dir>/gap-look/RETURN.md`.
- If the check fails (a page LOST or UNCLEAR): stop, for the editor (a stop point of the procedure, not a patch). The routes ruled before: (A) a re-scan of the missing spread (the editor scanned it); a second copy (the 29 Sep second-copy check); or the page recorded as not in the scan — an entry in `NOT_IN_SCAN` in `tools/ocr-absence-ledger.py` with the ruling quoted, and a line in `geniza/OCR-NOT-HELD-REGISTER.md` § 2 (a planned edit on the editor's word, as for `DECLARED` at C5.2). An omitted blank back is not listed: nothing is lost (the editor's rule, 30 Sep: a piece ends before the gap and a new one begins after it).
- Why: «A leaf never scanned is invisible to every OCR check, and an absence claim would silently cover it» (`ocr-page-sequence.py` header; a check suggested by Kapis of BitArkivo, 29 Sep); the 29 Sep run found 35 confirmed gaps, 7 of them lost pages (an internal record, 2026-09-29, not published).

C6.4.2 · Rotation — every item, by default; the repair only on the editor's ruling.

- Run: the candidate pass reads the WHOLE corpus (it has no item filter and loads every word list: slow, and it reads only); cut its list to the batch; turn the batch's candidates:

  ```
  python3 tools/ocr-flip-check.py candidates --below 0.35 --out <batch-dir>/rotation/FLIP-CANDIDATES-ALL.tsv
  awk -F'\t' 'NR==FNR{s[$0];next} ($1 in s)' <batch-dir>/ITEMS.txt <batch-dir>/rotation/FLIP-CANDIDATES-ALL.tsv > <batch-dir>/rotation/FLIP-CANDIDATES.tsv
  python3 tools/ocr-flip-check.py test --candidates <batch-dir>/rotation/FLIP-CANDIDATES.tsv --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt --out <batch-dir>/rotation/FLIP-TEST.tsv
  ```

  (`mkdir -p <batch-dir>/rotation` first. If `FLIP-CANDIDATES.tsv` is empty, skip `test` and `decide`: no page needs turning.)
- Writes: the two candidate lists (overwritten if they exist: use the new folder); `FLIP-TEST.tsv` and `FLIP-TEST.tsv.texts/` (the turned readings). `test` RESUMES an existing `FLIP-TEST.tsv` rather than refusing it — only a restart after a stop may reuse the name.
- Check: apply the decision rule (on words of 5+ letters, the best turn ≥ 0.5 on ≥ 10 words, ≥ the current reading + 0.2, ≥ the next-best turn + 0.3), which `decide` applies (added 2026-10-04, approved by the editor, § 7 point 5; on the 29 Sep test it passes the same 5 pages in 4 items as the check of 29 Sep 10:32, an internal record, not published):

  ```
  python3 tools/ocr-flip-check.py decide --test <batch-dir>/rotation/FLIP-TEST.tsv --out <batch-dir>/rotation/FLIP-PASS.tsv
  ```

  (refuses an existing `FLIP-PASS.tsv`; one row per passing page: `corpus · page · angle` (counter-clockwise, as `test` turned it) `· rotate_cw` (the same turn clockwise, for the ruling) `· the scores`)

  Only the header line (the console says «0 pass the rule»): nothing turned. Done. Each line (item, page, angle, score) is a CANDIDATE, not a repair: an image look of every one ((A) `<batch-dir>/<stem>/pages/page-NNNN.png`; (B) rendered at 100 dpi into `<batch-dir>/rotation/look/`, kept), one checker, Read tool only, never `FLIP-PASS.tsv`: «For each image: is the printed text UPRIGHT, UPSIDE DOWN, or SIDEWAYS? If sideways, does the top of the lines of text point to the LEFT or to the RIGHT edge of the image? Is all the text turned, or only part (a table, a caption)? Return `image | UPRIGHT / UPSIDE DOWN / SIDEWAYS-LEFT / SIDEWAYS-RIGHT | whole / part, a few words`.» File the return verbatim with its key in `<batch-dir>/rotation/LOOK-RETURN.md`.
- If the check fails (a page turned): stop, for the editor. On the editor's ruling, the ruled re-read (a defined branch, as for G1 rulings): write `<batch-dir>/rotation/RULINGS.tsv`, one page per line, `<stem><TAB><page><TAB><absolute PDF path><TAB>epo<TAB>rotate=<degrees CLOCKWISE>` (`rotate=` is the `rotate_cw` column of `FLIP-PASS.tsv`: flip-check's angle is counter-clockwise, so 90 → 270, 270 → 90, 180 → 180; add `crop=x0,y0,x1,y1` where only part is turned, as fractions of the page AS SCANNED, before the turn: the tool crops first), then

  ```
  python3 tools/ocr-ruled-reread.py <batch-dir>/rotation/RULINGS.tsv --root $R --dry-run
  python3 tools/ocr-ruled-reread.py <batch-dir>/rotation/RULINGS.tsv --root $R
  ```

  Writes `$R/<stem>/page-NNNN.ruled.txt` and `.ruled.json` (written over an existing ruled file: check there is none). The ruled reading is looked at against its image before the ruling is marked done (its header). The first chain's rebuild takes it over every OCR reading.
- Why: a scan can be stored upside down or sideways with no flag, and G5 found upside-down readings an earlier check had missed (`ocr-flip-check.py` header, 29 Sep). A PDF's own /Rotate flag needs no pass: the conversion honours it (`ocr_page_images.py`, 28 Sep).

C6.4.3 · Georgian and Armenian — only where C5.2 declared them.

- Run, for each declared item (the `--items` of the first tool is a GLOB of folder names, one stem per run; of the second, a COMMA LIST of exact names):

  ```
  python3 tools/ocr-kat-hye.py $R --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt --items '<stem>' \
      --out-kat $G/sources/ocr-rendersearch-kat --out-hye $G/sources/ocr-rendersearch-hye
  ```

  then, AFTER C6.2 (it replaces the clean files C6.2's garbage filter writes, and picks the Russian model from C6.2's readings), ONCE:

  ```
  python3 tools/ocr-mask-kathye.py $R --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt --items =<stem>[,<stem>…] --models $G/sources/gfmodels-2026-10-03
  ```

  (`--models` is required in practice, though the tool shows it as optional.)
- Writes: kat-hye — `$R/<stem>/page-NNNN.kathye.json` for every page, `page-NNNN.kat.txt` / `.hye.txt` where found, and the item's file in `ocr-rendersearch-kat/` and `-hye/` (rewritten for the items passed only). The mask — `page-NNNN.masked.eo.txt` / `.masked.ru.txt`, new `eo-gate` / `eo-clean` / `ru-clean` (the previous ones kept as `.pre4s.txt`), `MASK-KATHYE.json`. A second run of the mask would copy its own output over the `.pre4s` copies: never re-run it.
- Check: kat-hye's last line, «page errors 0», and Georgian or Armenian pages found on each declared item; the mask's per-item list, `unmatched` 0 on every page.
- If the check fails: a declared item with no Georgian or Armenian pages, page errors, or unmatched blocks: stop, for the editor.
- Why: on four-script pages the Russian and Esperanto models turn Georgian and Armenian into junk, so the Russian-only score and the Esperanto G4 were «measured partly on junk» (`ocr-mask-kathye.py` header; the four-script pass approved by the editor, 28 Sep); the gate scores the masked Esperanto side on any item the table lists with a non-Latin language (`ocr-accept.py`, `_segregate`). The Georgian and Armenian stay PRESENCE ONLY.

C6.5 · Other scripts — BY NEGOTIATION with the editor (the editor ruled on 2026-10-04 03:0x that other scripts are settled by negotiation: Japanese, Arabic, Chinese and Greek are all possible; other Asian scripts would be a surprise but cannot be ruled out). There is no automatic pass for Japanese, Arabic, Chinese, Greek, Korean or any other script. When C1 or the language table (C5.3: its evidence counts Arabic, han, kana, hangul and a catch-all «other» script, as well as Cyrillic, Greek, Georgian, Armenian and Hebrew) shows one on a batch item as running text — not a few cited words — stop and put it to the editor: what the script is, on which pages, and a proposed route (Tesseract models installed include `jpn`, `chi_sim`, `chi_tra`, `ara`, `kor`, `ell`, `grc`; or PRESENCE ONLY, as for *Helena Esperantisto*'s Greek). The editor decides per item; the ruling goes into the table as a declaration (C5.2) and onto the board. A cited script (a title, a name, an advert line) needs nothing: the table records it as `-cited`, which licenses no pass.

### C7 · The chain

- Run (from the repo root; it detaches; the log is the output):

  ```
  nohup caffeinate -i -s tools/ocr-chain.sh <suffix> --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --verdicts $G/ocr/runs/OCR-PSM-VERDICTS-<date>-<batch>-merged.json > <batch-dir>/CHAIN-<suffix>.nohup.log 2>&1 &
  ```

  (The chain writes its own log, `$G/sources/ocr-work/ocr-chain-logs/CHAIN-<suffix>.log`; the `> <batch-dir>/…nohup.log` catches what it prints BEFORE that log opens — a refusal of an existing name or of a second chain — which `nohup` would otherwise put in `nohup.out` in the repo root. Read it if the chain log does not appear.)

  `<suffix>`: e.g. `<date>-<batch>`. Try `--dry` first: it prints the commands and refuses an existing name.
- What it does, step by step, and which test each step applies (§ 1a defines the tests; expanded after the editor noted, 2026-10-04 03:1x, that this C7 section did not mention G2, G3 or G4 and needed more prose). The chain is where a batch's items are TESTED: G1, G2, G3 and G4 all run here, over the whole corpus at once, so the new items are judged by the same rules, in the same run, as everything already accepted.
  1. **Rebuild** (`ocr-rebuild-combined.py`). For every item, it picks the best reading of each page (by the merged psm verdicts of C4, and the Russian, re-OCR and vision readings where they exist) and joins every good reading into the item's search text. No test yet: this makes the text the tests read. It is why C4–C7a must be finished first — a reading made after the chain is not in the text it tests.
  2. **The Russian search** (`ocr-rus-companion.py`). The Cyrillic search file of each text the language table lists with a Cyrillic language (C5), from the readings of C6, with both readings where the old-letter rule picks the pre-reform one, and the Ukrainian reading beside them (C6.3). No test: it is the text that the Russian side of G4 and of absence searches reads. The old folder is kept as `.bak-<suffix>`.
  3. **G1 — dead pages** (`ocr-g1-ink.py`, writes `OCR-GATE-G1-<suffix>.md` and `.md.json`). It renders every page whose text is under a quarter of its item's median and asks whether the image carries ink in lines of type. It needs the page images (kept since C2/C4). A page with ink and no text is FLAGGED; a page it cannot decide (dark, photographic, a cover) is UNTESTED. Neither is a pass: both go to the image sort (C9), and until they are sorted their item is PENDING in the ledger.
  4. **The gate: G2, G3 and G4** (`ocr-accept.py --script-segregated`, writes `OCR-GATE-<suffix>-segregated.md` and `.md.json`), item by item:
     - **G2, language:** on each page it detects a second language; where one is present, the second-language reading must exist (`ocr-second-model.py`). If not, the item is «G2 pending» — the branch of C7b.1, then ONE chain again (C7b.3). The per-item list is `g2_pending` in the gate's `.md.json`; the report and the chain log give only languages and a count.
     - **G3, shape:** every page it judges list-shaped (rosters, address lists, columns) must have been read in column mode (`--psm 4`), which the conversion did at C4. If not, the item fails G3.
     - **G4, the word lists:** the median share of each page's words found in the item's language's word list (and a second language's where present) — at least 0.75 for prose, 0.65 where there are list pages. On the pages the language table makes bi-script (C5), only the Esperanto side is scored (from the cleaning of C6), and the Russian side gets its own «Russian-only» score (the bar is 40). The language and its list come from the gate's detection or the table's declaration (C5).
  5. **The ledger: the class** (`ocr-absence-ledger.py`, writes `OCR-ABSENCE-LEDGER-<suffix>.tsv`). From G1 and the gate together, each item gets its class (§ 1a): ABSENCE-ADMISSIBLE, SPECIAL HANDLING, WITH EXCEPTIONS, PENDING or PRESENCE ONLY, with its conditions (excluded pages, the side admitted, rulings). This is what C8 compares and C11 audits.
  6. **The every-reading search** (`ocr-search-all-readings.py`). For that ledger's SPECIAL HANDLING items, a file holding every reading of each page (`ocr-rendersearch-all.<suffix>`), swapped into `ocr-rendersearch-all/` (old kept as `.bak-<suffix>`): the text an absence search over those items must read. No test.

  Log: `$G/sources/ocr-work/ocr-chain-logs/CHAIN-<suffix>.log`.
- Rules: the full list and the merged verdicts, never the 30 Sep defaults; never two chains at once (the lock and the process check refuse); never rebuild or file anything while it runs.
- Check: the log's last line is `done HH:MM:SS`; the gate, G1 and ledger files exist; `$G/sources/.ocr-chain.lock` is gone. Then read the TESTS' results for each batch item: in the ledger (column 4 the class, column 3 the G4, the conditions after); in the gate report, the item's G2 (pending?), G3 (list pages, psm 4?) and G4 lines; in the G1 report, its flagged and untested pages (they go to C9). An item that is PENDING, «G2 pending», failing G3, or under its G4 bar is not a failure of the run: it is the test working, and its branch is C7b.1 (G2), C9 (G1), or the editor (G3, G4).
- If the check fails: the lock is removed on exit and the names already written cannot be reused, so a re-run takes a new suffix — on the editor's word (§ 6).

### C7a · Fraktur items: the Fraktur re-read, then the chain again — only where C1 found Fraktur

Why: Fraktur is salvageable (the editor's ruling of 2026-10-04 01:0x, C1): the `epo` model reads blackletter badly, and the `frk+epo` variant of `tools/ocr-reocr-best.py` (400 ppi grey, psm 6) has read the corpus's Fraktur before (*Estlanda Esperantisto*, *Idowoti*). The Fraktur pages are also the ones the Cyrillic detector once took for Cyrillic (the 3 Oct language look: *Estlanda Esperantisto* 1908), so they matter beyond the Esperanto.

- Run:
  1. Declare: add the item's stem (or a prefix of it) to `FRAKTUR = (…)` in `tools/ocr-reocr-best.py`, with a comment quoting the C1 look — a planned edit of the procedure (the operator proposes, the editor confirms, as for the languages, C5.2), not a patch.
  2. The items: write the Fraktur stems C1 found, one per line, to `<batch-dir>/FRAKTUR-ITEMS.txt` (a subset of `ITEMS.txt`), and turn it into the JSON list the tool reads. Then probe, then run (the tool's header):

     ```
     python3 -c 'import json,sys; print(json.dumps([l.strip() for l in open(sys.argv[1]) if l.strip()]))' <batch-dir>/FRAKTUR-ITEMS.txt > <batch-dir>/fraktur-items.json
     python3 tools/ocr-reocr-best.py probe $R --pdfs <full list> --items <batch-dir>/fraktur-items.json --out <batch-dir>/reocr-probe.json
     python3 tools/ocr-reocr-best.py run   $R --pdfs <full list> --probe <batch-dir>/reocr-probe.json --min-gain 5
     ```

  3. Then C7b: the chain runs again ONCE, after C7a and C7b's passes (C7b.3, suffix `<date>-<batch>-2`); its rebuild takes a page's `page-NNNN.reocr.txt` where it exists (`ocr-rebuild-combined.py`).
- Writes: `<batch-dir>/FRAKTUR-ITEMS.txt` and `fraktur-items.json`; `$R/<item>/page-NNNN.reocr.txt` BESIDE the existing readings (kept only where it scores higher than the page as it stands), `$R/<item>/REOCR.json`; the probe file; nothing replaced.
- Check: the probe names `vfrk` as the item's best variant; after the run, the item's re-read pages are listed in `REOCR.json`; the second chain's ledger is the one C8 compares.
- If the check fails: (a) `vfrk` does not win the probe: the item stays as read; note it for the editor (vision is used only where a check shows a problem, C11a). (b) The run writes nothing: as (a).

### C7b · Passes that need the first chain, then ONE second chain

What this step does for the tests. Two passes read what only the chain writes (the gate json, the `ocr-preferred` tree), and their readings reach the tested text only through the rebuild. They run after the first chain, with C7a's Fraktur re-read, and are followed by ONE chain again — so C8 compares, C9 sorts and G5 samples the text that includes them.

- Skip if no batch item has a non-empty `g2_pending` in the first chain's gate `.md.json`, no small capitals were seen at C1, and C7a did not apply: then the first chain's ledger is the one C8 compares.

C7b.1 · A second Latin-script language pending (G2): the gate shows «G2 pending» on a batch item.

- Run, per language the gate names for the item (`fra`, `deu`, `ces`, …; `--corpus` with `=` names exact items — without `=` it matches any name containing the text, and without `--corpus` it reads every flagged item of the corpus):

  ```
  python3 tools/ocr-second-model.py --gate $G/ocr/runs/OCR-GATE-<suffix>-segregated.md.json --verdicts $G/ocr/runs/OCR-PSM-VERDICTS-<date>-<batch>-merged.json \
      --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --root $R --lang <fra|deu|ces|…> --corpus =<stem>[,<stem>…]
  ```

- Writes: `page-NNNN.<lang>.txt` and the merges `page-NNNN.<reading>.<lang>.arb.txt` beside the readings; never over a reading.
- Check: its stderr names each batch item and a tally; no other item.
- Why: G2 (§ 1a). For Korĵenkov (Esperanto, 2005) none is expected; if the gate shows one, it is a planned branch, not a patch (formerly the SETTLED note under C6.5).

C7b.2 · Small capitals: only where C1 (or C2's `pages/`) showed names or text set in small capitals.

- Run (pass the batch's NEW list: the tool works on every gated item in `--pdfs`, so the full list would add readings to earlier items too):

  ```
  python3 tools/ocr-smallcaps-reread.py --preferred $G/sources/ocr-preferred --root $R --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>-NEW.txt \
      --gate $G/ocr/runs/OCR-GATE-<suffix>-segregated.md.json --out <batch-dir>/smallcaps
  ```

- Writes: `$R/<stem>/page-NNNN.sc3x.txt` where none exists (search only; the preferred reading and G4 are unchanged), and `<batch-dir>/smallcaps/MANIFEST.tsv` (refused if the folder exists).
- Check: the first console line's page count is plausible for the item (all-caps headings also qualify); MANIFEST rows only for batch items; `status` written or empty, no timeouts.
- Why: names in small capitals are misread past finding («BRÉON» → «Bnéow»); a 3× re-read recovered one name in four (G5 re-sample 30 Sep; failure map row 5b).

C7b.3 · The chain again — once, after C7a and C7b.1–2, under the suffix `<date>-<batch>-2` (C7's command and checks). Its ledger is the one C8 compares, its G1 the one C9 sorts, and `<suffix>` from here on means this one.

### C8 · The ledger comparison against the CURRENT ledger

What this step does for the tests. No new test: it checks that the TESTS OF C7 changed nothing they should not. The chain re-ran G1–G4 and the class over the whole corpus; this comparison, item by item against the CURRENT ledger, must show that every item already accepted keeps its class and its conditions — only the batch's items are new. A moved item means a test now judges it differently: that is surfaced to the editor before anything else, because a signed line may rest on the old class.

- Run:

  ```
  python3 tools/ocr-ledger-compare.py <CURRENT ledger> $G/ocr/runs/OCR-ABSENCE-LEDGER-<suffix>.tsv > $G/ocr/runs/OCR-LEDGER-COMPARE-<current suffix>-<suffix>.md
  ```

- Writes: the compare file (the tool itself writes nothing).
- Check: the accepted corpus has not moved. (a) Every class move is `(absent) → <class>` for a batch item; (b) the count of items that kept their class but changed notes is 0; (c) the class totals of the existing items are unchanged. Batches 1 and 2 met this at every step («What held: nothing in the accepted corpus moved at any step», failure map).
- If the check fails: any class or condition change of an existing item — above all a signed one — is surfaced to the editor before anything else is done. Nothing is signed, and nothing is re-run to «fix» it in the test (R10: a changed label moved 157 items from SPECIAL HANDLING to WITH EXCEPTIONS and was caught here).
- Board: the result, with the batch items' classes.

### C9 · The G1 image sort of the flagged pages, before G5

What this step does for the tests. It FINISHES **G1**. The chain's ink test (C7, step 3) can only say «ink and no text» (flagged) or nothing (untested); this step is where a person or a blind checker looks at each such page beside its text and decides: NOTHING missing, MINOR (≤ 3 lines of masthead, caption or date), LOST (a paragraph or more), or SCRIPT (another script, read elsewhere). Until it is done, the item is PENDING, which no G5 sample can test and no line can sign. After it, the ledger is re-run alone, and the verdicts become the item's G1 result: MINOR and LOST pages become named exceptions (WITH EXCEPTIONS), or the item stays ADMISSIBLE.

Why: R8 — batch 2's overnight plan left it out; 8 items came out PENDING (17–18 G1-flagged pages) and waited for a morning sort.

- Skip if the batch items have no G1-flagged or undecided pages and no PENDING row.
- Run:

  ```
  python3 tools/ocr-g1-sort-build.py --g1 $G/ocr/runs/OCR-GATE-G1-<suffix>.md.json --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --out <batch-dir>/g1-sort --tag <date>-<batch>
  ```

- Writes: `<batch-dir>/g1-sort/bNN/NNN.png` + `NNN.txt` (batches of 20) and `KEY.tsv`. Pages sorted before (any `OCR-G1-SORT-KEY-*.tsv`) are not re-sent.
- Check: every page in `KEY.tsv` belongs to a batch item. Then one blind checker per bNN, each given this brief with its folder filled in (the classes as recorded in the first sort, an internal record, 2026-09-26, not published: MINOR «display type, mastheads, captions, dates (≤ 3 lines)», and SCRIPT as added 2026-09-27; the return's columns as in batch 2's sort record, an internal record, 2026-10-03, not published, in the form the ledger reads):

  > You are checking scanned pages against the text an OCR program kept for them. Use ONLY the Read tool. Do not run commands and write no files. The folder `<batch-dir>/g1-sort/<bNN>/` holds pairs: `NNN.png`, the page image, and `NNN.txt`, the text kept for that page. Read every pair in the folder. For each, ask: is there printed matter on the image that the text does not hold? Answer one of: **NOTHING** — the text holds everything printed (or the page has no words: blank, or a picture alone); **MINOR** — the text misses only display type, a masthead, a caption, a date or a page number, three lines or fewer and no running text; **LOST** — the text misses running text (more than three lines, or any paragraph), or holds a different page altogether; **SCRIPT** — what the text misses is Cyrillic, Georgian or Armenian writing only. If what is missing is in another non-Latin script, say which in the note and answer MINOR or LOST by the amount. Do not open `KEY.tsv` or any file outside the folder. Return a table and nothing else, one row per page: `| NNN | VERDICT | what the page is | what is missing, if anything |`.
- Filing: `$G/ocr/runs/OCR-G1-SORT-<date>-<batch>.md` (a header naming the checker and the build, the key, «## Return, verbatim»), and `KEY.tsv` copied to `$G/ocr/runs/OCR-G1-SORT-KEY-<date>-<batch>.tsv`; the ledger reads both (`ocr-absence-ledger.py`, `sort_verdicts()`).
- Then the ledger step alone and the every-reading search, as the chain runs them (batch 2 did this, as `cupel2b`), with no chain running:

  ```
  python3 tools/ocr-absence-ledger.py --gate $G/ocr/runs/OCR-GATE-<suffix>-segregated.md.json --g1 $G/ocr/runs/OCR-GATE-G1-<suffix>.md.json --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --out $G/ocr/runs/OCR-ABSENCE-LEDGER-<suffix>b
  python3 tools/ocr-search-all-readings.py --ledger $G/ocr/runs/OCR-ABSENCE-LEDGER-<suffix>b.tsv --root $R --out $G/sources/ocr-rendersearch-all.<suffix>b
  mv $G/sources/ocr-rendersearch-all $G/sources/ocr-work/ocr-rendersearch-all.bak-<suffix>b
  mv $G/sources/ocr-rendersearch-all.<suffix>b $G/sources/ocr-rendersearch-all
  ```

  (the backup goes to `sources/ocr-work/`, as the chain's own backups do since the folder move of 2026-10-04)
- Check: no batch row is PENDING; C8 repeated against the CURRENT ledger, its output `$G/ocr/runs/OCR-LEDGER-COMPARE-<current suffix>-<suffix>b.md`, with the same result for every item outside the batch.
- If the check fails: pages from items outside the batch in `KEY.tsv` — stop and ask. LOST or MINOR pages become ledger exceptions; whether any gets vision is the editor's call (C11).
- SETTLED (00:1x): the checker's brief is the one above (written out 2026-10-04 after the cold dry run, which found no brief text on file; its classes are those of the first sort (an internal record, 2026-09-26, not published), «each page's IMAGE beside its FINAL text, sorted NOTHING / MINOR / LOST», with SCRIPT from 2026-09-27); the batch-2 record (an internal record, 2026-10-03, not published) shows the form (one blind checker, Read tool only; key; the return verbatim). `ocr-g1-sort-build.py` writes the images and texts itself (`<out>/bNN/NNN.png + NNN.txt`, `<out>/KEY.tsv`); filing: the record `OCR-G1-SORT-<tag>.md` and the key copied to `OCR-G1-SORT-KEY-<tag>.tsv`, which the ledger reads.

### C10 · Scope: which pages get absence lines, and of what kind — the editor's

Batch 1 is the precedent (editor 01:5x–02:04). An item may get:

- Scoped lines: page ranges of the split PDF (`page-NNNN`, not the printed page numbers), each with a kind. PRIMARY, or SECONDARY LITERATURE with the editor's condition that absence there shows only that the work does not mention X, and is no evidence about the event (so «the secondary literature never cites the Owen letter» is admissible; «it did not happen, since Waringhien does not say so» is not). Batch 1: the editor ruled *Lingvo kaj Vivo* secondary literature, and *Li kaj Ni* primary sources on pages 14–39 and secondary literature on 42–60; lines ruled (a), all scoped pages, confirmed by the editor at 02:04.
- No lines at all: Manders, which the editor ruled gets none, being linguistic rather than historical. The item stays in the corpus for presence searches and for the wider research; only the dowse sweep and absence lines exclude it (the editor ruled at 01:5x that all this material will be used, but that the sweep of themes and names is only for the corpus additions).
- Whole-item lines (no scope file), if the editor so rules.

- Run: ask the editor, with the item's contents (front matter, contents page) in hand. Write the ruling to `$G/ocr/runs/CUPEL-BATCH-<n>-SCOPE.tsv`, in the form of batch 1's scope file (an internal record, 2026-10-03, not published): comment lines quoting the ruling, then `item<TAB>pages<TAB>kind`, rows like `li-kaj-ni-1985<TAB>14-39<TAB>PRIMARY` (kind PRIMARY or SECONDARY; pages `lo-hi`).
- Check: every row's item is in the batch; ranges within the item's pages.
- If the editor has not ruled: stop. G5 samples from the scoped pages, so the scope comes first.

### C11 · G5: one blind sample across the batch

What this step does for the tests. **G5** is the test OF the tests: it checks that the classes the ledger gave (from G1–G4) are true on the page. For each absence class, blind judges list the names printed on sampled pages, and every name is searched in exactly the text that class's search uses (§ 1a); a page whose names the search cannot find (two or more missed) contradicts the class. G1–G4 measure the text; G5 measures whether an absence search over it would be right — so it is the last test before a line can be proposed.

Why: D2 (00:1x) — one global sample per batch; the corpus bar is at most 1 contradicted page in 40 (set by the editor as the maximum threshold, 2026-09-30 15:15); D2 for small samples: «sample min(40, all pages); pass at 0 contradicted below 40 pages, at most 1 at 40».

- Run, build:

  ```
  python3 tools/ocr-g5-sample.py build --ledger $G/ocr/runs/OCR-ABSENCE-LEDGER-<suffix>[b].tsv --g1 $G/ocr/runs/OCR-GATE-G1-<suffix>.md.json \
      --pdfs $G/sources/OCR-PDF-LIST-<date>-<batch>.txt --out <batch-dir>/g5 --items @<batch-dir>/ITEMS.txt \
      [--scope $G/ocr/runs/CUPEL-BATCH-<n>-SCOPE.tsv] --classes-2610 --classes ledger-admissible,ledger-special,ledger-exceptions --n 40 --seed <S>
  ```

  Always pass `--pdfs`: its default is a 28 Sep list in `/tmp`. Pick a new seed and write it on the board (batch 1 used 19, batch 2's fresh sample 29).
- Writes: `<batch-dir>/g5/bNN/` (page images at 150 dpi, `NNN.esperanto-text.txt`, `NNN.russian-text.txt`, `NNN.all-readings.txt` for SPECIAL HANDLING), `KEY.tsv`.
- Check: the console count per class: 40 per class the batch has (or all its pages, if fewer), drawn only from batch items (and, with `--scope`, only scoped pages). Every page in `KEY.tsv` is a batch item's.
- SETTLED in part (00:1x): the batch-1 and batch-2 commands were not logged. Their keys show the classes of `--classes-2610` (batch 1: 40 `ledger-admissible`; batch 2: 40 `ledger-special` + 40 `ledger-exceptions`) with `--items` (the batch), and batch 2's fresh sample (`g5c`) avoided the first (`--avoid <batch-dir>/g5/KEY.tsv`). So: `python3 tools/ocr-g5-sample.py build --ledger <ledger> --g1 <g1 .md.json> --pdfs <full list> --out <batch-dir>/g5 --items @<batch-dir>/ITEMS.txt --classes-2610 [--scope <scope tsv>]`. From now on the exact command goes on the board with the result.
- Judges: copy the standard brief into `<batch-dir>/g5/BRIEF.md` word for word (the 30 Sep brief: coverage NOTHING / MINOR / LOST, orientation UPRIGHT / ROTATED, Russian printed NONE / SOME / MUCH, up to 10 printed personal names; the sampler's header). One fresh judge per bNN folder (20 pages each), Read tool only (the brief says so), shown the brief and that folder's images and text files — never `KEY.tsv`, never `*.all-readings.txt` — RETURNING its table, one row per page, `| NNN | coverage | orientation | Russian | names separated by ; |`, as its final message. The operator writes each returned table, verbatim, to `<batch-dir>/g5/bNN.return.txt` (the file `file --table` reads; corrected 2026-10-04 after the cold dry run, which found the runbook saying both that judges write a file and that they write none).
- SETTLED (00:1x): the brief is `<G5 dir>/BRIEF.md`, copied word for word from the 30 Sep brief (as `sources/cupel-batch-2/g5c/BRIEF.md` and `sources/g5-orth-2026-10-03/BRIEF.md`); the judges RETURN their table as their final message (they write no file); it is filed with `ocr-g5-sample.py file --batch bNN --table <a file holding the table>`, which appends it verbatim to `<G5 dir>/RETURNS.md` and refuses a wrong or second filing.
- Run, file each return, then score:

  ```
  python3 tools/ocr-g5-sample.py file --out <batch-dir>/g5 --batch b01 --table <batch-dir>/g5/b01.return.txt
  python3 tools/ocr-g5-sample.py score --out <batch-dir>/g5 --returns <batch-dir>/g5/RETURNS.md
  ```

- Writes: `RETURNS.md` (each return verbatim; refused if the rows are not exactly the batch's pages, or the batch is already filed); `SCORE.json`.
- Check: each clearing class PASS. RULED (editor 2026-10-04 00:0x, accepting the recommendation): the sample is PER CLASS — 40 pages, or every page of the class if it has fewer — drawn across all the batch's items (D2's «one sample» = across the batch, per class); the bar is ≤ 1 contradicted at 40 pages and 0 below 40. `ocr-g5-sample.py score` applies this bar (taught 2026-10-04). Record names found per class.
- If the check fails: diagnose BEFORE any re-sample — which names were missed, in which script, and whether they are in any reading on disk (batch 2: the misses were Cyrillic names on pages with no Russian reading at all, R5). Write the diagnosis on the board and in the failure map; the fix is the editor's word; then the re-runs the fix needs (for batch 2: forced readings, layout, rusfull, garbage filter, a new chain) and a FRESH sample with a new seed and `--avoid <batch-dir>/g5/KEY.tsv`, into a new folder (`g5b`, …). Never re-judge the same pages to get a pass.

C11a · Vision, only where G1 or G5 showed a problem (draft C8). On the editor's word only, with `tools/ocr-vision-batch.py render --dir <run dir> --pdfs <full list>`, then `prompt --dir <run dir> --batch bNNN` (the transcriber, Read and Write only, writes `returns/bNNN.txt`), then `file --dir <run dir> --batch bNNN --record <transcriptions .md>`. Any new reading must be followed by a chain (C7) — steps 2 and 6 «must follow ANY re-read» (chain header) — then C8 again, then a fresh G5 for the classes it touched.
- SETTLED (00:1x): `KEY-ALL.tsv` is written by hand (or a short script) before `render`: one line per page, tab-separated, `batch · tag · corpus · PDF page · kind` (as `sources/ocr-work/ocr-vision-2026-10-03-langlook/KEY-ALL.tsv`); `BRIEF-TEMPLATE.md` (as `sources/ocr-work/ocr-vision-2026-09-30/BRIEF-TEMPLATE.md`) only for the transcription mode (`prompt`, `file`). A blind LOOK (a question, not a transcription) needs only `render`, then a brief written for its question, and its return filed intact in a geniza record with the key.

### C12 · Proposed lines; the editor signs; a new signed file

What this step does for the tests. No test: it writes the RESULTS of all of them into the line an absence claim must cite — the class (G1–G4, through the ledger), the G4 score, the conditions (G1's excluded pages, the sides G4 admitted, the editor's scope), and the G5 the class was audited by. The editor's signature is what turns a tested item into one that may be searched for absence.

Why: D3 (approved by the editor at 00:1x, for probity): each batch its own new signed file; earlier signed files are never edited.

- Run, proposed:

  ```
  python3 tools/ocr-acceptance-lines.py --ledger $G/ocr/runs/OCR-ABSENCE-LEDGER-<suffix>[b].tsv --out $G/OCR-ACCEPTANCE-LINES-<date>-PROPOSED-<batch>.txt \
      --items @<batch-dir>/ITEMS.txt --g5 "G5 <batch> <date>: <class> <c>/<n> contradicted, <found>/<names> names[; <class> …]" [--scope $G/ocr/runs/CUPEL-BATCH-<n>-SCOPE.tsv]
  ```

- Writes: the PROPOSED file only (refused if it exists). Its lines begin `PROPOSED-ACCEPTED:`, which no reader takes up. PRESENCE ONLY items get no line; with `--scope`, an item without a row gets none (named on the console).
- Check: one line per scoped row (or per admitted item); each line's conditions are the ledger's, verbatim; SECONDARY lines carry the editor's condition; the `--g5` label states the G5 result for EVERY class sampled, one clause per class, `<n>` = the class's sample size (40, or all its pages if fewer); `<class>` is the ledger's class name (as batch 2's label: «SPECIAL HANDLING 0/40»), and `<date>` in the label the date of the G5 score. In the file names, the proposal carries the date it was made and the signed file the date of signing: they may differ.
- Then STOP, and put the proposal to the editor (board entry «FOR THE EDITOR'S SIGNATURE»). Only the editor signs.
- Run, signed — only after the editor's words of signature, quoted exactly:

  ```
  python3 tools/ocr-acceptance-lines.py --ledger <same> --out $G/OCR-ACCEPTANCE-LINES-<date>-SIGNED-<batch>.txt --items @<batch-dir>/ITEMS.txt \
      --g5 "<same label>" [--scope <same>] --signed "signed by the editor <date> <HH:MM> («<the editor's words>»)"
  ```

  The signature's form is that of the batch-1 file (signed by the editor 2026-10-03 02:21): «signed by the editor», the date and time, then the editor's words of signature in «…».
- Check: the signed file's lines are identical to the proposal's apart from the prefix (`ACCEPTED:` for `PROPOSED-ACCEPTED:`) and the signature (the last field); the header line differs as well (it says SIGNED, not NOT SIGNED; `ocr-acceptance-lines.py` lines 67–71). Compare (tested on batch 2's files, 4 Oct):

  ```
  diff <(grep -v '^#' $G/OCR-ACCEPTANCE-LINES-<date>-PROPOSED-<batch>.txt | sed -E 's/^PROPOSED-ACCEPTED: //; s/ \| [^|]*$//') \
       <(grep -v '^#' $G/OCR-ACCEPTANCE-LINES-<date>-SIGNED-<batch>.txt | sed -E 's/^ACCEPTED: //; s/ \| [^|]*$//')      # prints nothing
  ```

  Then the proposal is superseded: add a first line «# SUPERSEDED <date> <HH:MM> by OCR-ACCEPTANCE-LINES-<date>-SIGNED-<batch>.txt (the editor signed). Kept for the record; not for use.» (as batch 2's), and move it to `$G/ocr/runs/archive/` with `mv` (with `git mv` only if the editor has already staged it); the signed file stays in `$G/`.
- After: readers take the union of the signed files; where an item has lines in two signed files, the later holds. The new ledger becomes CURRENT only when the editor says so.

### C13 · Record

At each step (rule 12), and at the end:

- The board (an internal log, not published): a dated entry at the top for each step's result; the last says what was signed and what is CURRENT.
- `docs/FAILURE-MAP.md` § «cupel's first batches»: a new row (R11, …) for every misstep: what went wrong, how it was caught, what fixed it (the editor asked at 12:4x that the missteps of this testing of the new Russian passes be captured in documentation).
- The queue of open items (an internal list, not published): what is left open (vision owed, a scope not yet ruled).
- This runbook: corrected where the run showed it wrong, with the date.
- SETTLED (00:1x): the source register (an internal record, 2026-08-31, not published) gets a line per item from a cupel batch (what it is, where the scans are, its class and signed file), as for La Vojo and the Soviet press on 3 Oct.

## 5 · Korĵenkov: the values known before the test

| step | value |
|---|---|
| C0 | `$G/sources/scans/korzhenkov-historio-2005/slv-scan-2026-10-01/`, 4 TIFFs, 65 spreads; Sezonoj 2005; in copyright |
| C1 | stem e.g. `korzhenkov-historio-2005`; print to be looked at |
| C2 | `--look-all` (every spread looked at); overlap only on the editor's word |
| C5 | languages: the C1 look's proposal, the editor's confirmation |
| C6 | a history: never the marker, never SKIP_ORUS; Russian passes only if a Cyrillic language is licensed |
| C10 | scope: the editor's (a history of Esperanto: PRIMARY / SECONDARY for the editor to rule) |
| C12 | the signed file `OCR-ACCEPTANCE-LINES-<date>-SIGNED-<batch>.txt` |

The stop points where the editor rules are part of the procedure, not improvisation: C5.2 (the declaration), C6.1 (a genre marker), C10 (scope), C11 (a failure's fix; vision), C12 (the signature; CURRENT).

## 6 · If a step fails

The rule for the latchkey test (draft, under D4: «Anything that has to be patched during it is a runbook failure, logged in the failure map, and the runbook is corrected before the test counts»):

1. Stop at the failing check. Do not patch a tool, a list, a module or a file to get past it, and do not improvise a step this runbook does not name. A defined branch («If the check fails» above) is not a patch; an editor's ruling at a stop point is not a patch.
2. Write it down before anything else: a dated board entry (what step, what check, the output), and a row in `docs/FAILURE-MAP.md` § «cupel's first batches» (what went wrong, how it was caught, what will fix it).
3. Leave the outputs as they are. Nothing is deleted or overwritten; the tools refuse existing names, so a later run uses new names. What to clean, if anything, is the editor's call.
4. Correct this runbook (and, on the editor's word, the tool), dated, saying what changed and why.
5. Re-run the test — from the start or from the failed step, as the editor rules. The test counts only when a run goes from C0 to C12 with no patch.

Why so strict: batch 2 met nine missteps (R1–R9) and the language table one more (R10). Each was caught before a line was signed, but each was caught by someone noticing — the latchkey test is the proof that the procedure no longer depends on that.

## 7 · Open points — the draft's settled (2026-10-04 00:1x); two raised since, one ruled (below)

The draft's 17 «CHECK:» points are settled; each is marked SETTLED or RULED where it stood. The editor's rulings (00:0x): the C2 look covers EVERY spread (01:3x, superseding the 00:0x ruling of a 40-spread sample); only a cut through PRINT fails it; the operator proposes a batch's languages and the editor confirms before C5.3; G5 is per class, 40 pages (all if fewer), ≤ 1 contradicted at 40 and 0 below, and `ocr-g5-sample.py score` applies it. The real gap (C5.1: a new item could not enter the language table before its first chain) is fixed in `tools/ocr-text-languages.py` (approved by the editor, 3 Oct 23:4x). New tools for the open points: `tools/cupel-merge-verdicts.py`, `tools/ocr-orus-choices.py`; `tools/ocr-ukr-pages.py` now runs before a first chain. Nothing is open before the latchkey test except the other write-ups (the editor ruled that the write-ups come before any latchkey test, § 1).

**OPEN since 2026-10-04 (the cold dry run's gaps filled):**

1. **A (B) PDF's own text layer — RULED 2026-10-04 12:4x.** The runbook said the conversion keeps a born-digital layer as the preferred reading; it did not: `cupel-convert.sh` never ran `tools/ocr-textlayer.py`, the only tool that reads the layer. Asked whether it should, so that the layer becomes one more competing reading as the corpus had on 26 Sep, the editor approved. Done: step 3b of `cupel-convert.sh` (C4).
2. **OPEN: a new BORN-DIGITAL PDF's layer in the search text.** The rebuild adds a page's layer to its SEARCH text only for pages listed as born-digital in `sources/ocr-text-layer-2026-09-30/tl-kind.tsv` (the page's largest image under half of it; `ocr-rebuild-combined.py`, «THE TEXT LAYER'S KIND»). That file was made on 30 Sep and no tool in `tools/` writes it, so a new item's pages are never in it: its layer competes in adjudication but never joins the search text, born-digital or not. For the editor, when a born-digital (B) PDF comes: extend `tl-kind.tsv` for its pages (a new tool), or let it stand as is.

From the C6.4 draft (an internal record, 2026-10-04, not published; its OPEN 1–10). Settled from the code: `ocr-rotation-flag.py` is retired (`tools/retired/README.md`: «the fault is fixed at the source»); the language table takes `georgian` and `armenian` as it takes `russian` (`ocr-text-languages-table.py`, its language map); the page-sequence TSV goes to `$G/ocr/runs/` with the other run outputs; the strip look's return has the columns of the 29 Sep returns (its brief is not on file). OPEN, for the editor:

3. **RULED 13:2x (approved by the editor): LEAD items get the neighbour look; PARTLY-VERIFIED and CANT-TELL go on the board for the editor's ruling per item.** Was: **Page numbers that cannot be followed** (C6.4.1): LEAD, PARTLY-VERIFIED and CANT-TELL items get no strip look (the tool builds one only for GAP and JOIN). A look built by hand, the neighbour look, or a note on the signed line?
4. **RULED 13:2x (approved by the editor): only when C1 sees them, as drafted.** Was: **Small capitals** (C7b.2): only when C1 sees them (as drafted), or by default? By default means a second chain for nearly every batch (the telltale also catches all-caps headings).
5. **RULED 13:2x (approved by the editor): a `decide` mode of `ocr-flip-check.py`, so the runbook carries no code (tool change to make).** Was: **The rotation rule** (C6.4.2): the decision rule is in `ocr-flip-check.py`'s header but not its code, so the runbook carries it as inline Python. Make it a `decide` mode of the tool (a tool change)?
6. **RULED 13:2x (approved by the editor): dropped from the runbook; `ocr-flip-check.py` is the one route (the file stays in `tools/`).** Was: **`ocr-rotation-check.py`** (C6.4.2): keep as an optional second opinion, or drop it (how its «Rotate» converts to the ruling's clockwise degrees is not settled from the code)?
7. **RULED 13:2x: keep them too — otherwise, as the editor noted, they would have to be re-extracted if something goes wrong later.** DONE 13:4x: `ocr-flip-check.py test` and `ocr-kat-hye.py` already take their pages through the page-image cache (`ocr_page_images.py`); `ocr-page-number-look.py` now puts each page it uses there too (tested: 3 pages of one lead cached); `ocr-rotation-check.py` is out (point 6). The cache stops growing below 50 GiB free (its guard): check `df` before a batch. Was: **Page images of (B) PDFs**: four of these tools discard their full-page renders (`ocr-page-number-look.py`, `ocr-rotation-check.py`, `ocr-flip-check.py test`, `ocr-kat-hye.py`). Nothing is lost for (A), whose pages C2 keeps; for (B), keep these renders too (rule «keep page images»)?
8. **RULED 13:2x (approved by the editor, who will photograph the page): the missing page is re-photographed or re-scanned from the book first, by the editor; the item waits; `NOT_IN_SCAN` only if that cannot be done.** Was: **A confirmed missing leaf in an (A) scan** (C6.4.1): is a re-scan of the spread the first route, before `NOT_IN_SCAN`? And must the `NOT_IN_SCAN` entry exist before the first chain, so the first ledger carries it?

## Appendix · Old and new step numbers

| draft (3 Oct 00:0x) | this runbook |
|---|---|
| C0 look at one page | C1 |
| C1 images → pages → PDF; the blind look | C2 |
| C2 name and list | C1.3, C3 |
| C3 convert (`ocr-run-corpus.sh`; superseded by R6) | C4 (`cupel-convert.sh`) |
| C4 passes the item needs | C5 (languages), C6 |
| C5 the chain | C7 |
| C6 the class (ledger compare) | C8 |
| C6½ the G1 image sort (R8) | C9 |
| — (batch 1's scope rulings) | C10 |
| C7 G5 | C11 |
| C8 vision | C11a |
| C9 the editor signs | C12 |
| C10 record | C13 |
