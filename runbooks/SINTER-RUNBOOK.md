# The sinter: runbook (2026-11-08)

*Published in `geniza-ocr` release v1.8 from the project's working file as it stood on 11 November 2026. This undated file is always a copy of the newest dated one beside it; the earlier dated files are kept unchanged. The editor's rulings are given as dated paraphrases, not in his words. The board, the QUEUE, the handovers and the other files it names that are not in this repository are the project's internal records, not published. Commands and paths are given as they were run.*

The sinter joins the dowse's profiles where two heads are one person, and keeps them apart where they are two. Its scope is `dowse/CORPUS-PASS-SCOPE-2026-11-06.md`; its state and the editor's rulings, verbatim, are in `QUEUE.md`. This file holds the steps and the working rules, the rulings in paraphrase.

## Steps

1. `python3 tools/same_act.py --write` after each harvest: the pairs of lines that may be one act under two heads (`profiles/build/SAME-ACT-PAIRS-LATEST.tsv`), by class.
2. `python3 tools/dispute-sort.py --classes B C D`: the far pairs sorted into easy folds, easy rejections and the rest, as a review document for the editor (`dowse/DISPUTES-SORT-<date>.md`). Pairs already ruled «two people» or rejected are kept in `dowse/SINTER-VERDICTS.tsv` and counted as «ruled», not listed again; add a row there for every pair a page read or the editor rules apart.
3. The editor marks the easy folds. The rest are read by hand from the lines' words (`dowse/DISPUTES-REST-READ-<date>.md`) or by legiloj, priced first.
4. **Page reads.** A pair is read on the page when the two forms are far apart and are not plain garbles of one another in their structure (the editor's rule, 2026-11-08). Read the OCR page first. Where the OCR is damaged on both sides, the pair goes to Miles for a vision read (`ocr/VISION-REQUESTS.tsv`).
5. Approved folds are written as DECISIONS «name» rows, line by line: `python3 tools/fold-by-line.py PAIRS.tsv --note NOTE --ruling TEXT [--write]`. It folds only the lines that pair the two heads in today's pairs file. A line that pairs with a third head is written by a scratch script, after checking that its locator and phrase find exactly one line.
6. `python3 tools/reassemble-sources.py --sinter-tag NOTE` (or the sources by name), then one harvest alone, then `same_act.py --write`, then each folded line checked under its new head.

## Working rules

- **Parallelise the searches** (the editor, 2026-11-08). Never run one page or one search a call and wait for it. Send all the searches for a batch of rows in one message, as parallel calls. Each script should take many items and pages in one run. Read pages while a reassembly or a harvest runs in the background: both only write the profiles, and a page read only reads the OCR.
- **Start each reassembly as soon as its rows are written**, not at the end of a batch. *Progreso* takes about 11 minutes alone (12 MB); most sources take under 2 minutes.
- **A row's phrase must be the line's own subject.** A «name» row keyed on another person's words moves that person's line too, as two of Nylén's and Asklöf's lines were moved in the Zakrzewski split. Where a person's own line names the other man under the wrong form, as its object or in «kun:», use an «object-qualifier» row (`OLD → NEW`). It renames him there, and the harvest skips the copy that would land on the line's own head.
- **A misattributed line with a correct twin is dropped, not re-headed.** Re-headed, it would stand under the right person still saying the wrong name. Use a «duplicate» row, keyed on its locator and phrase, whose value is the kept line's fact.
- **Check the whole corpus before dropping a line as a misreading.** Two articles of one title can be two people's (Cogen's and Hodler's «Rondirantaj gazetoj», 1903 and 1904).
- **Memory is not evidence.** A guess from memory goes into a review document marked «from memory, unchecked», and the page decides (the Boyer / Boulet read).
- **A new «replace_lines» entry must name its return.** Run `tools/dowse-facts-assemble.py SOURCE --key-replace-lines` right after writing it, or the reassembly refuses that source (Ruslanda Esperantisto, 2026-11-08).
- A pen name found on the page goes into `profiles/NAMES-REGISTER.tsv` as «pseudonym», status proposed, with its locators.

## Not built yet

- The page-read scripts (`page_read.py`: the lines of one OCR page that match a pattern; `grep_issues.py`: a pattern over a set of issues, with file and page) are still scratch. To be made one repo tool that reads a list of rows from the review document and prints every page for all of them in one run, in parallel.
- `fold-by-line.py` cannot fold a line whose pair is with a third head, nor every line of a head at once.
