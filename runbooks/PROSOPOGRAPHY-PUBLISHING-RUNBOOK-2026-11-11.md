# Runbook: publishing the prosopography

*Published in `geniza-ocr` release v1.8 from the project's working file as it stood on 11 November 2026. This undated file is always a copy of the newest dated one beside it; the earlier dated files are kept unchanged. The editor's rulings are given as dated paraphrases, not in his words. The board, the QUEUE, the handovers and the other files it names that are not in this repository are the project's internal records, not published. Commands and paths are given as they were run.*

*Draft, 2026-11-10, by Ezri, at the editor's request of that evening. Nothing in it is built yet; every step names the tool it needs. The editor's rulings are given in paraphrase; his words are in the QUEUE.*

A release of the prosopography is cut from one smelt: every person whose biography that smelt finished. It has three parts:
- **the machine tables**, the evidence layer as CSV;
- **the reading copies**, as PDF;
- **the website**, updated from the release.

All commands are run from the `carney/` folder.

## When to run it

- After a smelt is finished for every person it is to publish, and the editor has said to publish.
- **The release's date** (the editor's ruling, 2026-11-11): the day the editor declares the smelting done. Release 0.1 is dated 2026-11-10.

## The sources' stages at the release

The editor's ruling (2026-11-11): as of the release's date, every source the project holds is recorded at one of four stages:
- **blank**: held, not yet worked;
- **cupel**: its OCR cleaned and checked, not yet read for facts;
- **dowse**: read for facts, not yet harvested into the profiles;
- **sinter**: harvested and folded into the profiles. The dress is part of sinter and is not reported apart.

A source that arrived after the smelt but before the release date stands at the stage it had reached by then. For 0.1, the sources read in the last two days before the release (Germana Esperantisto, Tra la Mondo, the roster-cut redowse and the others) are at dowse.

The site's page of sources (`published/genizo/pages/legitaj-fontoj.md`) lists every source the project holds, in one table for each current stage (sinter, dowse, cupel, blank) (the editor's ruling, 2026-11-11). Each table reports the stages in a column **Etapo**: each version with the stage the source had reached by it, and nothing further once sinter is reached. *Lingvo Internacia* reads «0.1 sinter». *Germana Esperantisto* reads «0.1 dowse» now, and «0.1 dowse 0.2 sinter» from 0.2.

**Built (2026-11-11):** `tools/source-stages.py snapshot <version> <date> --write` records every item's stage to `dowse/ETAPOJ.tsv` (one row an item and a version; 0.1 recorded: sinter 1,451 items in 134 sources, dowse 736 in 49, cupel 4,736 in 1,400, blank 6); `tools/dowse-done.py` draws the page from it at each run: the sinter table with its «Etapo», then one table each for dowse, cupel and blank. Known limit: blank holds only the item table's items without a text; holdings never put through OCR (the ÖNB titles not yet fetched, the Temerov batch) are in no table yet.
- Not after a harvest alone: a harvest changes the profiles, not the smelt's frozen copies, and the release is cut from the frozen copies.

## 1. The inputs, person by person

For each person (`smelt/<stem>/`, tag `<tag>`) the release reads:
- `PROFILE-FROZEN-<tag>.md`: the facts;
- `LABELS-<tag>.tsv`: each fact's label;
- `S3-INPUT-<tag>.md` and `S3-RETURN-<tag>.md`: the tool's groups, the readers' groups and the episodes;
- `S4-LABELLED-<tag>.md`: the full biography, with labels and references;
- `S4-GIST-VIEW-<tag>.md`: the gist, with its pictures;
- `WORKS-LIST-<tag>.tsv` and the works check: the works.

**Check:** every person has every file, and none is older than the person's S4 return. A person who lacks one is held out of the release and listed, never published half.

*Not built yet:* the input check (`tools/prosopography-release.py check <tag>`).

## 2. The machine tables

The editor's ruling: this is the release's machine artefact. It holds the facts, the groups and the episodes, linked by their IDs.

Every ID carries the person and the smelt, since a line number belongs to one frozen profile and an episode number to one smelt:
- **a fact:** `<stem>:<tag>:L<n>`, for example `de-beaufront:2026-11-09s:L5201`;
- **a group:** `<stem>:<tag>:G<n>`, the tool's (below G1000) and the readers' (G1001 and up) alike;
- **a single line the tool stated:** `<stem>:<tag>:U<n>`;
- **an episode:** `<stem>:<tag>:E<n>`.

### facts.csv, one row a fact line

- **id**: the fact's ID.
- **person**: the head of the line, in the register's main form.
- **date**: as the line gives it («1907-10-24», «inter 1911-07 kaj 1911-08», «[sen dato]»).
- **kind**: the event kind and its object («konflikto: ZAMENHOF»).
- **fact**: the fact, in Esperanto, as the line states it.
- **anchor**: the source's own words, about six, **left empty where the source is in copyright** (§4).
- **label**: the fact label (siglum, place, letter: «BelgSon 1904.23:12a»).
- **siglum**: the work's short code, a key into sources.csv.
- **locator**: the full locator of the line.
- **voice**: who says it («📣» the source itself, or the author named).
- **status**: what the line carries of its standing (a copy, a derived line, a refutation).

### groups.csv, one row a group member

- **group**: the group's ID.
- **made_by**: `tool` or `reader`.
- **kind**, **object**: the group's kind and object.
- **statement**: the group's statement (a reader's group), or the best line's fact (a tool's group).
- **status**: the reader's standing of it («asertita», «konfirmita», …), where given.
- **fact**: one member's fact ID.

### episodes.csv, one row an episode

- **episode**: the episode's ID.
- **title**, **date**: as the reader gave them.
- **groups**, **facts**: the IDs it rests on, separated by spaces.
- **circumstances**: the reader's circumstances, its approximations and notes, as written.
- **see_also**: the episodes it points to («vidu E…»).

**Built (2026-11-11):** `tools/prosopography-release.py tables <tag> <version> [--skip STEM]`, to `geniza/prosopografio-eldono/<version>/` (facts.csv, groups.csv, episodes.csv, sources.csv); 0.1: 37 people, 21,135 facts, 26,930 groups, 2,566 episodes, 139 sigla. The release's notes, in Esperanto, beside them (`NOTOJ.md`).

## 3. The other tables

The editor's ruling: worth having, after the machine tables.
- **people.csv**: one row a person: the main form, birth and death (date and place), the card's number, the release's PDF names.
- **names.csv**: every form of every name (other scripts, patronymics, pseudonyms) with its source, from `profiles/NAMES-REGISTER.tsv`.
- **offices.csv**: who held what, from when to when (the tool's spans, the S items).
- **relations.csv**: person to person (meeting, conflict, agreement, influence), dated and sourced.
- **works.csv**: each person's works, from the works lists as checked.
- **sources.csv**: each short code with its full entry, from `profiles/SIGLA.tsv` and the item table, and the column `in_copyright`.

*Not built yet:* all six.

## 4. The anchors of works in copyright

The editor's ruling: an anchor from a work still in copyright is not published. One anchor is a fair quotation; thousands of them, each keyed to its page, would let the text be rebuilt, as a concordance would.

- `sources.csv` carries `in_copyright` for every short code: `yes`, `no`, or `ask`. It is settled by its authors' deaths (the editor's ruling, 2026-11-10: the authors dead 70 years or more): a work whose authors all died 70 or more years before the release is `no`; a work whose author is living or died within 70 years is `yes`; anything uncertain (an author unknown, an anonymous work, a death year not found) is `ask`, for the editor.
- A fact whose siglum is `yes` or `ask` is published with its label and locator and an empty anchor.

**Check:** no fact row with a non-empty anchor has a siglum that is not `no`.

**Ruled and built (2026-11-11):** a work published up to 1930 is out of copyright, later «ask», a periodical issue by issue; `profiles/COPYRIGHT.tsv` holds the exceptions (Privat's three works, in copyright to 2032). The tables tool applies it fact by fact; 0.1 withholds 4,109 anchors.

## 5. The PDFs

The editor's rulings: the gists of all the persons bound into one PDF; one PDF for each full biography; the bingo card's style and font.

- **The route:** `tools/bingo-book.py`'s route: pandoc to xelatex, Crimson Pro (`sources/web-2026-11-07-fonts/Crimson-Pro/`), A4, 12 point, margins of 2.4 cm, no hyphenation (the engine has no Esperanto patterns).
- **The gists:** one PDF, a person a chapter, in the order of the card; each gist with its pictures, as `S4-GIST-VIEW` places them; a table of contents.
- **The biographies:** one PDF a person, from `S4-LABELLED-<tag>.md`, with its «Referencoj».
- **Constant line spacing** (the editor's ruling: no extra space between lines where a label's letter is set below the line): the template sets `\lineskiplimit=-\maxdimen`, so the engine never adds space for a tall line, and sets each label's letter (the «<sub>a</sub>» of «BelgSon 1904.23:12<sub>a</sub>») in a subscript that takes no height (`\smash`).

**Check:** each PDF opens; the page count is above zero; every person in the release has a chapter and a biography.

**Built (2026-11-10):** `tools/prosopography-pdf.py gists <tag> --version <V>` and `… bio <tag> --all --version <V>` (or named stems), to `geniza/prosopografio-pdf/`: `prosopografio-v<V>-skizaj-biografioj.pdf` and `prosopografio-v<V>-biografio-<stem>.pdf`. The faces (the editor's choices): Crimson Pro for the text; EB Garamond for every Greek and Cyrillic letter, so that a name stays in one face, and for what Crimson Pro lacks (☞ → ⅓ ⅔ ❓); STIX General, upright, for ∴ ⚫ ⚠, the last at 80%; Cardo's pilcrow, scaled to the capitals. The tool stops on any character no face has; a new script (Georgian, Armenian) needs a face added first. The gists come in the card's order, its supplement next, the rest by stem; the biographies leave out the writer's report (parts 2-4). The cover is page 1, unnumbered, so each printed page number is the PDF's own, as in the bingo card's book.

## 6. The checks before release

- Every person's labels resolved (step 1b of the smelt: no key without a siglum, no line without a locator); any that remain are listed in the release's notes as difektoj for future repair.
- Every picture a gist names is present.
- The copyright check of §4 passes.
- The release's notes record the smelt tag, the persons, the counts of each table and the date.

## 7. Where the release goes, and its version

- **The files:** the website's downloads (the editor's ruling, 2026-11-10), on the prosopography page (step 8).
- **The title** (the editor's ruling, 2026-11-11): «Prosopografio (personmenciaro) de pioniraj esperantistoj, de la projekto La Genizo de Esperanto»; the running header and footer use the short form «Prosopografio de pioniraj esperantistoj». The pioneer Idists will be a separate publication, «Prosopografio (personmenciaro) de pioniraj idistoj».
- **The version:** the first release is the prosopography 0.1 (the editor's ruling, 2026-11-10). The bingo card, versioned on its own until now, becomes 1.0.0 at that release and says that it is aligned to the prosopography 0.1.

## 8. The website

The editor's ruling: a release also updates the website.

1. Run the progress-pages runbook (`published/genizo/PROGRESS-PAGES-RUNBOOK.md`), so that the site's templated figures, the blocks each generator writes between its marks, follow the release. A release changes two of them above all:
   - `biografatoj`, the blocks `ESPERANTISTOJ` and `IDISTOJ`, by `tools/smeltee-list.py`: who gets a biography and whose is written;
   - `prosopografio`, the block `PROGRESO`, by `tools/prosopografio-progreso.py` (`--dry-run` first): the stages' figures; it reads the other pages, so it runs last.

   If any source or short code changed since the last run, steps 1, 2 and 4 of that runbook too (`legitaj-fontoj`, `siglaro`, `osr-korpuso`). Each page's date line is today's, and nothing outside the marks moves.
2. Put the release's downloads on the prosopography page: the CSV files, the gists' PDF, the biographies' PDFs.
3. Push the pages by the WordPress publishing reference (`~/.claude/memory/reference_wordpress_publishing.md`) and `PUBLISHING_LEARNINGS.md`; ask the editor before the batch push (the site's firewall).

*Not built yet:* step 2's download list on the page.
