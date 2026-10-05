# geniza-ocr

The OCR quality-assurance method of **[The Geniza of Esperanto](https://geniza.opoudjis.net)** (*Genizo de Esperanto*): how the text of a corpus of Esperanto-era periodicals and books, many of them bilingual and some printed in two scripts, was read, tested and graded, so that a search for a person's name can be trusted to a known degree, whether it finds the name or not.

This is a **frozen release**: the version the methods document describes. It is updated only as new tagged releases:

- `v1.0` (5 October 2026): the method as signed.
- `v1.1` (6 October 2026): the name search widened by the OCR confusions measured on 27,308 pages (`METHOD.md`, section 6, «Release v1.1»). The figures of section 8 are unchanged.

## What is here

| | |
|---|---|
| `METHOD.md` | The methods document: the tests (G1 to G5), the classes, the measured recall, what the method does not claim, and the lessons. **Start here.** |
| `RUNBOOK.md` | The procedure for bringing a new batch of scans or PDFs through the method, step by step. |
| `docs/REPLICATION.md` | The replication record: the pipeline stage by stage, with commands, parameters and the reasons for each. |
| `docs/FAILURE-MAP.md` | Every way the pipeline failed, how it was found, and what fixed it. |
| `docs/OCR-ACCENT-SURVEY-2026-10-05.md` (and `.tsv`) | What OCR writes in place of each accented Latin letter and each Cyrillic letter, measured on 27,308 pages of known text, old and modern print apart (release v1.1). |
| `tools/ocr-name-search-confusions.tsv` | The measured confusions the name search tries, generated from the survey (release v1.1). |
| `tools/` | The tools that implement the method (Python and shell), in the state the documents describe. |
| `tools/lexicons/hunspell/SOURCE.md` | Where the word lists come from, and their licences. |
| `tools/tessdata-extra/SOURCE.md` | Where the pre-revolutionary Russian Tesseract model comes from, its licence and checksum. |

## What is not here

The corpus itself is not included: no text, no scans, no page images. Many of the items are in copyright. Nor are the built word lists, the ledgers, or the signed acceptance records. The tools therefore do not run out of the box. They are published so that the method can be read, checked, and applied to other material. Their paths assume the project's own folder layout (`published/heterophony-resources/geniza/…`); adapt them to yours.

## What the tools need

Tesseract 5.5.3 with the 4.1.0 language models and the `orus` model (see `tools/tessdata-extra/SOURCE.md`); Poppler (`pdfimages`, `pdftoppm`, `pdftotext`); Python 3 with Pillow and NumPy; Hunspell dictionaries for the word lists (see `tools/lexicons/hunspell/SOURCE.md`). Every measurement in the documents was made on one machine, described in `METHOD.md`.

## Citing

The Geniza of Esperanto, *geniza-ocr: the OCR quality-assurance method*, release `v1.1` (2026), https://github.com/opoudjis/geniza-ocr.

## Licence

The tools are under the MIT licence (`LICENSE`). The documents (`README.md`, `METHOD.md`, `RUNBOOK.md`, `docs/`) are under the Creative Commons Attribution 4.0 International licence (`LICENSE-docs`).
