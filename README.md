# geniza-ocr

The OCR quality-assurance method of **[The Geniza of Esperanto](https://geniza.opoudjis.net)** (*Genizo de Esperanto*): how the text of a corpus of Esperanto-era periodicals and books, many of them bilingual and some printed in two scripts, was read, tested and graded, so that a search for a person's name can be trusted to a known degree, whether it finds the name or not.

This is a **frozen release**: the version the methods document describes. It is updated only as new tagged releases:

- `v1.0` (5 October 2026): the method as signed.
- `v1.1` (6 October 2026): the name search widened by the OCR confusions measured on 27,308 pages (`METHOD.md`, section 6, «Release v1.1»). The figures of section 8 are unchanged.
- `v1.2` (6 October 2026): v1.1's confusions corrected: a spelling made by a measured confusion no longer gets the full allowance of misread letters on top, which had made whole-corpus searches for short names flood (`METHOD.md`, section 6, «Release v1.2»). Short names tightened: a word of two letters or fewer matches only exactly, and a name of four letters or fewer gets a Russian ending or a misread letter, not both. Use this release, not v1.1. It also adds the search tools of `docs/SEARCHING.md`: `ocr-dowse.py`, `ocr_index.py` (with its check, `ocr-index-check.py`) and `ocr-corpus-lexicon.py` — reading each item by its strongest match, page counts, image checks within a practical limit, a judgement file, and people who share a surname.
- `v1.3` (22 October 2026): the whole pipeline as run on the batches of 7 to 22 October (`METHOD.md`, section 6, «Release v1.3»): pages in columns, text blocks and second readings; Fraktur; declared second languages honoured, with old Portuguese spelling recognised; new word lists (Slovak, Latino sine flexione, Volapük); copies of one text aligned and tested; holdings censused and pages dated; long runs that save page by page and resume. `RUNBOOK.md` is the current run sheet, and `docs/FAILURE-MAP.md` runs to row R50. 56 tools updated or added.
- `v1.4` (27 October 2026): the runbooks published (`METHOD.md`, section 6, «Release v1.4»): the cupel run sheet as of 27 October, and the dowse and smelt runbooks for the first time, in `runbooks/`. Each runbook has an undated file, always a copy of its newest dated version, and its earlier dated versions kept; `RUNBOOK.md` now points there. The tools brought up to the run sheet (30 updated, 16 added, among them the gutter cut for pages in columns, `tools/ocr-gutter-cut.py`), and `docs/FAILURE-MAP.md` to row R70.
- `v1.5` (27 October 2026): the tools of the dowse and smelt runbooks (`METHOD.md`, section 6, «Release v1.5»): 62 added, so that every tool the three runbooks name is here.

## What is here

| | |
|---|---|
| `METHOD.md` | The methods document: the tests (G1 to G5), the classes, the measured recall, what the method does not claim, and the lessons. **Start here.** |
| `runbooks/` | The runbooks, each as an undated latest file and its dated versions: `CUPEL-RUN-SHEET.md`, bringing a new batch of scans or PDFs through the method, step by step; `DOWSE-RUNBOOK.md`, reading the facts about people out of a source; `SMELT-RUNBOOK.md`, a person's facts grouped, checked and written up (a draft) (release v1.4). |
| `RUNBOOK.md` | A pointer to `runbooks/`; in v1.3 it held the run sheet. |
| `docs/REPLICATION.md` | The replication record: the pipeline stage by stage, with commands, parameters and the reasons for each. |
| `docs/FAILURE-MAP.md` | Every way the pipeline failed, how it was found, and what fixed it. |
| `docs/OCR-ACCENT-SURVEY-2026-10-05.md` (and `.tsv`) | What OCR writes in place of each accented Latin letter and each Cyrillic letter, measured on 27,308 pages of known text, old and modern print apart (release v1.1). |
| `tools/ocr-name-search-confusions.tsv` | The measured confusions the name search tries, generated from the survey (release v1.1). |
| `docs/SEARCHING.md` | How the corpus is searched for people: a roster against a journal run (the way the project searches), or one name against the whole corpus; the tools, how to read their results and when to stop, people who share a surname, what a silence means, and how long it takes (release v1.2). |
| `tools/` | The tools that implement the method (Python and shell), in the state the documents describe. |
| `tools/lexicons/hunspell/SOURCE.md` | Where the word lists come from, and their licences. |
| `tools/tessdata-extra/SOURCE.md` | Where the pre-revolutionary Russian Tesseract model comes from, its licence and checksum. |

## What is not here

The corpus itself is not included: no text, no scans, no page images. Many of the items are in copyright. Nor are the built word lists, the ledgers, or the signed acceptance records. The tools therefore do not run out of the box. They are published so that the method can be read, checked, and applied to other material. Their paths assume the project's own folder layout (`published/heterophony-resources/geniza/…`); adapt them to yours.

The runbooks name many files that are not here: the board, the QUEUE, the handovers, the checks and reviews. These are the project's internal records, not published.

## What the tools need

Tesseract 5.5.3 with the 4.1.0 language models and the `orus` model (see `tools/tessdata-extra/SOURCE.md`); Poppler (`pdfimages`, `pdftoppm`, `pdftotext`); Python 3 with Pillow and NumPy; Hunspell dictionaries for the word lists (see `tools/lexicons/hunspell/SOURCE.md`). Every measurement in the documents was made on one machine, described in `METHOD.md`.

## Citing

The Geniza of Esperanto, *geniza-ocr: the OCR quality-assurance method*, release `v1.5` (2026), https://github.com/opoudjis/geniza-ocr.

## Licence

The tools are under the MIT licence (`LICENSE`). The documents (`README.md`, `METHOD.md`, `RUNBOOK.md`, `runbooks/`, `docs/`) are under the Creative Commons Attribution 4.0 International licence (`LICENSE-docs`).
