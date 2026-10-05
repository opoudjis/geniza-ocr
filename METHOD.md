# Grading the OCR of an Esperanto-era corpus: finding names, and claiming their absence

## Abstract

This document describes how the text of a historical corpus was checked and graded for its reliability for NAMES: how likely a name printed on a page is to be found by a search of the text, and, at the highest grade, whether a statement of the form "person X is not mentioned in this item" can be made over it, and how far such a statement can be trusted. The two go together: every page read better is a page whose names a search can find, so each item's class is also a confidence level for presence queries — how likely a search is to find a name that is printed there — and the work that makes absence claims possible also makes presence searches find more. The corpus consists of Esperanto-movement periodicals and books, mostly from the decades around 1900, many of them bilingual and some printed in two scripts (Latin and Cyrillic, occasionally Georgian, Armenian or Greek). Its text was produced by OCR (optical character recognition: software that turns a picture of a printed page into machine-readable text). Many of the scans came from the digital archive BitArkivo; others came from the Austrian National Library's ANNO service, from other libraries, or were born-digital (made directly from a word processor or typesetting program).

At signing on 2 October 2026 the corpus held 2,815 items and 113,477 pages (the acceptance record, an internal record of 2 October 2026, not published). The method rests on one observation: a name missing from a text may mean that the page was blank, that the software failed to read the page, or that the name is genuinely not there. The text looks the same in all three cases. Each page is therefore read several ways. Four tests (G1 to G4) check the result, and a ledger sorts every item into a class that states what kind of search an absence claim over it must use. A fifth test (G5) then audits those classes on blind samples, measuring how often a name printed on a page cannot be found in the text that class searches. On the best-performing class, 3 printed names in 238 were missed; on the largest class, 10 in 204 (the acceptance record, not published). No test certifies absence; what is measured is name recall on samples, and section 9 says plainly what is outside the method's reach. The document ends with ten lessons for anyone building a similar corpus and, as an appendix, a condensed list of every recorded failure.

The figures here are those signed on 2 October 2026; they will be updated after the next intake run.

## What «95%» means, and why we stopped there

The figures in this document are percentages of names found. On the largest class of items, a search finds about 19 of every 20 personal names printed on a page; one in 20 is missed (section 8). That is not perfection, and this document does not claim it.

Reaching it took about two weeks of full-time work, much of it on the last few points. The common faults, such as a wrong language model or a missing column reading, were found and fixed early, and a single such fix could change thousands of pages at once: the column reading alone was chosen on 26,174 pages (docs/REPLICATION.md § 4, stage 5). What remained was a long tail of rarer faults: faint print, small capitals, turned pages, pages in two scripts, a misfiled scan. Each of those affects fewer pages and costs more effort per name recovered. That is the point of diminishing returns, and the method stops there. The only ways past it are to type the whole corpus by hand, or to have every one of its 113,477 pages transcribed by an AI vision model, at a cost of thousands of dollars, and with errors of its own (see «Vision transcription», below). Neither is in prospect.

What the method offers instead is triage, and a measured error rate. The tests described below do not make the text perfect. They find where it is weakest, send those pages to more work or to a person, and keep them out of any claim the text cannot support. Then they measure what is left, class by class, so that a searcher knows how far to trust a search, whether it finds a name or not (section 6).

The alternative is not a perfect text; it is an unmeasured one. OCR run once and never checked looks plausible, and it is much worse than it looks, above all where accented letters matter. The Esperanto model cannot write the French é, è, à or ç: across the whole of *Progreso* it wrote none, so every French name with an accent was misspelt (docs/REPLICATION.md § 4, stage 7). On one volume of *Esperanto* (UEA, 1906), reading the page again with the French model restored 664 accents that a single reading had lost (docs/REPLICATION.md § 4, stage 8). Nobody who reads only the first text would know.

## A note on the tools and measurements

Every timing, count and score in this document was measured on one machine: an Apple MacBook Pro (Mac17,8) with an Apple M5 Pro chip, 18 cores (6 super cores and 12 performance cores), and 64 GB of memory, running macOS 26.5.2, with Tesseract 5.5.3 and Poppler 26.09.0 (docs/REPLICATION.md § 1). Timings on other hardware will differ; counts and scores should not, given the same inputs and tool versions.

**Vision transcription.** Some pages are also read a second way: an AI model looks at the page image and writes out its text, much as a person would. This document calls it «transcribed by vision». It was done with Claude Opus 5.5 (Anthropic). It can read what OCR cannot, such as faint print, type on a coloured ground, display lettering or a page turned on its side, and the same kind of model serves as the blind checker in the image sort and as the judge in G5 (sections 3 and 6). It is not used on the whole corpus, for two reasons. First, cost: a vision reading costs far more per page than a Tesseract reading, and the allowance for it is limited, so it is spent only where a check has shown a problem (`tools/ocr-g1-faint.py`, header, «against quota»; RUNBOOK.md, C11a). Second, it is not perfect either. One vision transcription, checked later against a published scholarly transcription of the same document, had left a word unread and had to be corrected (the Bokanov card; the vision additions, an internal record of 27 September 2026, with its correction note of 28 September, not published). Its readings are kept as readings of their own, beside Tesseract's, like every other reading.

## Spelling and script reforms the corpus spans

The corpus spans more than a century of print, across spelling reforms in three of its languages. Each one broke a test that assumed one spelling per language, and each comes back in the sections below; they are gathered here so that the reader meets them once, first.

**Russian: pre-revolutionary and Soviet spelling.** Russian before the 1918 reform was printed with letters later abolished (ѣ, і, ѳ, ѵ, final ъ). There are two Russian models, one for each spelling. A rule chooses the pre-reform reading where enough old-letter words appear. On a Soviet-era batch the rule misfired: the pre-reform model read Esperanto as Cyrillic, taking a Latin *i* for the old letter і, and 103 of 1,857 Russian pages went to the wrong model (docs/FAILURE-MAP.md R1). The Russian word list the tests use has the Soviet (post-1918) spelling only: it holds no word with ѣ, і, ѳ or ѵ (`tools/lexicons/hunspell/SOURCE.md`). So before a pre-revolutionary word is looked up, or matched against a name, its abolished letters are folded to their Soviet equivalents: ѣ to е, і to и, ѳ to ф, ѵ to и, and a word-final ъ dropped (`tools/ocr-name-search.py`, header). A ъ inside a word, which Soviet spelling keeps as a separating sign (подъезд), is left alone; the Soviet word list has no word ending in ъ (0 of its 146,229 words; `tools/lexicons/russian_post1918.txt`), so there is nothing to strip on the list's side. Which spelling a page uses is decided page by page, never from the date of the text: a history written after 1918 may quote pre-revolutionary print, and the editor ruled that only the post-Revolutionary press, Soviet and post-Soviet, may be marked as post-reform spelling throughout (section 4, «Old and new Russian spelling, decided per page»; docs/FAILURE-MAP.md, the standing requirement of 3 October). Ukrainian keeps і as an ordinary letter, so і alone is no sign of the old Russian spelling (the orthography look, an internal record of 3 October 2026, not published).

**Ido: its first years.** Ido's forms changed in its first years, and the clean word lists come mostly from later dictionaries. The Ido list therefore also carries the 1908 forms of de Beaufront and Couturat, reviewed line by line by the editor, with the 1908 spellings in `y` accepted as a rule; even so, early Ido (*Progreso* 1908) still scores low, because words it uses, such as *jam*, *tiu* and *kun*, are in no clean source (docs/REPLICATION.md § 6; the review of the 1908 delta, an internal record of 25 September 2026, not published). Ido also has no letters with the Esperanto circumflex, so in an Ido text such a letter is always an OCR error (section 2, the accent-strip guard).

**Estonian: the old w-spelling.** Older Estonian prints w where modern Estonian writes v. The Estonian word list is modern, so for lookup a w is matched as v; the text itself keeps its w (docs/REPLICATION.md § 9, Estonian; `tools/ocr-accept.py`, `--estonian-fold wv`). The language look of 3 October found the old w-spelling throughout *Estlanda Esperantisto* (an internal record of 3 October 2026, not published).

A related matter of typeface rather than spelling: some of the same Estonian pages are set in Fraktur (blackletter), which the Esperanto model reads badly and which the Cyrillic detector once took for Russian; Fraktur pages get a re-read with a Fraktur model (RUNBOOK.md, C7a).

## 1. Three silences

A historian searching a digitised periodical for a name gets one of two answers: the name is there, or it is not. A hit is evidence of presence, and it needs no further apparatus: the searcher goes to the page and reads it. But a search finds only the names the OCR read: a name misread is a presence missed, and the searcher never learns of it. So the quality of the reading decides how many of the names that are present a search will find, as much as it decides whether a miss means anything. A miss can mean three things that look identical in the text:

1. the page was blank, so the silence is real;
2. the page carried print that the OCR failed to read, so the silence is an artefact;
3. the page was read, and the name is not on it.

The gate's own specification states this as the reason the checks exist: a corpus passes so that an empty search result means something (`tools/ocr-accept.py`, header). The G1 tool's header puts it more sharply: a page that was not read and a page with nothing on it produce the same output, and that output is also what an absence finding looks like; no measure that sees only the text can tell the three apart (`tools/ocr-g1-ink.py`, header).

From this follows the rule the whole method serves. A presence finding stands over any text in the corpus. An absence finding is admissible only over an item that has passed the tests and carries a signed acceptance line, and only under the search that line names (the frozen pipeline specification, an internal record of 24 September 2026, not published, "Handover to a scout"; the acceptance record, not published, "What signing does"). An item without such a line may be searched for presence, never for absence.

The classes of section 5 are therefore a CONFIDENCE LEVEL FOR PRESENCE QUERIES, not only a licence for absence. G5 (section 6) measures, per class, how many of the names printed on sampled pages a search of the text finds: that recall is the confidence a searcher can have that a name printed in an item of that class will be found. The re-readings the tests caused raised it for every item, admitted to absence searching or not. A searcher looking for a person benefits whether the answer turns out to be yes or no; and when it is no, the class says how much that no is worth.

The specification also names, from the start, what no text measure can catch (the frozen specification, not published, "What the gate cannot catch"):

- handwriting and lithograph, which OCR turns into confident, well-formed nonsense;
- a second language in another script, which the specification expected to come out as silence rather than damage; the corpus later showed that Cyrillic read with a Latin-script model comes out as Latin-letter junk that the language detector cannot flag (docs/REPLICATION.md § 7, and § 8, 09-26);
- proper names, which are in no dictionary, so no dictionary-based measure sees them;
- a blank page and an unread page, which only a look at the image can separate.

Sections 2 to 7 describe how each of these was addressed. Section 9 says what remains.

## 2. Reading each page many times

The OCR engine is Tesseract 5.5.3, with language models of the 4.1.0 release, plus one model not in that release: `orus`, for pre-revolutionary Russian, the stock Russian model fine-tuned on *Iskra* (1900–1905), printed in the old spelling. It comes from a single user's repository (iskra_ocr, Apache 2.0), not from the official Tesseract models, and is pinned by its checksum (`tools/tessdata-extra/SOURCE.md`). Everything runs on one machine; every tool version is pinned by a git commit, and a run records the commit it used (docs/REPLICATION.md § 1). The design principle, adopted by the editor on 26 September, is that every rule applies only where it has purchase. Settings are chosen per page, not per corpus, because each fault found had been a global default that was wrong somewhere (docs/REPLICATION.md, opening). Nothing is overwritten: every reading of a page is kept as its own file, and the combined text of an item is assembled from them and can be rebuilt (docs/REPLICATION.md § 3).

### The image

A scanned PDF usually stores each page as one image. Where it does, that image is extracted byte for byte rather than re-rendered. Rendering cost 28.6 seconds a page at 300 dots per inch against 0.06 seconds for extraction, and the extracted image read better (docs/REPLICATION.md § 4, stage 1). Where a page has several images it is rendered at the document's median resolution; where it has none, at 300 ppi (pixels per inch). The no-image rule was learned the hard way. Before 26 September such pages were rendered at the resolution of the document's pictures, and one page of *Recenzo pri Universalaj Lingvoj* was rendered at 43 ppi and read as 0 characters; at 300 ppi it reads 1,432 (docs/REPLICATION.md § 4, stage 1). A safety net re-reads any page yielding less than a quarter of its document's median text by the other route, and keeps the longer reading.

Some PDFs store a page as a low-resolution colour layer plus a sharp black-and-white text mask. A third reading takes such pages at the mask's resolution (capped at 400 ppi). This covered 163 PDFs and 3,470 pages; on one *Tra la Mondo* contents page the text rose from 1,771 to 11,184 characters (docs/REPLICATION.md § 4, stage 3). The cap rests on a single sample, and the record says so.

Pages that the PDF marks for rotation on display were at first extracted unturned. Of 169 extracted flagged pages, 53 were read sideways or upside down, so a flagged page is now always rendered (docs/REPLICATION.md § 8, 09-29). A separate check looks for pages whose reading matches no dictionary and re-reads them turned (docs/REPLICATION.md § 9, "Turned pages"); every page it passes goes to a look at the image (docs/REPLICATION.md § 8, 09-29).

### Two layouts

Tesseract reads a page under a "page segmentation mode" (psm), its assumption about layout. Mode 6 treats the page as one block of text; mode 4 as a column of lines of varying size, which suits lists and rosters. Every page is read both ways. On 194 prose pages mode 4 won 22% of the time, mode 6 won 13%, and 64% tied, so neither is a safe default (docs/REPLICATION.md § 4, stage 2).

### The PDF's own text

Most PDFs carry a hidden text layer behind the image: 2,588 of 2,905 PDFs, giving 105,034 page readings at the count of 26 September (docs/REPLICATION.md § 4, stage 4). On a scan this layer is someone else's OCR. On a born-digital PDF it is the printed text itself. The layer is kept as one more competing reading and replaces nothing. A measurement of 30 September showed why the two kinds must be treated differently. On scans our OCR was the better reading on 54% of sampled pages and the PDF's built-in text layer on 21%. On born-digital pages the layer was better on 38% and as good on 57% (the text-layer measurement, an internal record of 30 September 2026, not published). Since then a born-digital page's layer joins the search text, and a scan's built-in text layer does not, unless adjudication chose it as the page's reading (`tools/ocr-rebuild-combined.py`, header).

### Choosing a reading per page

Among all the readings of a page, one is chosen as its PREFERRED reading: the single text the page carries as its reading of record, for instance the one text layer of a PDF/A copy handed over to an archive (the write-ups plan, an internal record of 1 October 2026, not published). Search does not rely on that one reading. For redundancy, an item's search text adds the page's other readings to the preferred one, and the search for the items most at risk reads every reading held (section 5; `tools/ocr-rebuild-combined.py`, header). The preferred reading is chosen by rule E, in force from 26 September (`tools/ocr-psm-adjudicate.py`, header; docs/REPLICATION.md § 4, stage 5):

- on prose pages, the reading with the most recognised words wins, by more than 2 words or 2%, whichever is larger; otherwise the mode 6 reading is kept. Mode 6 is not kept because it is better: the 194-page comparison above shows it is not. It is kept because it is the reading every page gets first, at conversion (docs/REPLICATION.md § 4, stage 1). Another reading replaces it only when it is clearly better, by more than a margin that small differences of noise cannot cross;
- on list pages, among readings within that margin of the best word count, the one with more "entry-form" lines wins, meaning lines that keep a number or name attached to the fields that belong to it.

"Recognised" means found in the Esperanto, Ido or Occidental lexicon (the word lists the tests use). The rule counts words rather than measuring a rate because a rate rewards the reading that barely saw the page. On one page of *Internacia Socia Revuo* a reading of 214 characters scored 93.8% and one of 1,019 characters scored 61.3% (docs/REPLICATION.md § 4, stage 5). The list rule exists because of rosters. On *Belga Esperantisto*, mode 4 recovered 266 more complete roster entries from 1.5% less text: the characters were the same, but numbers stayed attached to their members (`tools/ocr-psm-adjudicate.py`, header).

Rule E was chosen by measurement. Every candidate rule was re-run on the recorded per-page figures, and two blind looks compared rule E with the rule before it. The second look, 40 list pages from 40 titles, gave rule E 26 pages, the old rule 13, with 1 tie (docs/REPLICATION.md § 4, "Evidence for the entries-rule debate", and § 6). A "blind look" here means that judges compare readings labelled only X and Y, in random order, with the key kept out of their sight. Over 114,924 pages, rule E added 850,866 recognised words over mode 6 alone (docs/REPLICATION.md § 4, stage 5).

### A second language model

A page in Esperanto with French names, or a French-Esperanto bilingual, is read badly by the Esperanto model alone: that model cannot write é, è, à or ç (0 such letters across *Progreso*). Where a second language is detected, or required by rule, the page is read again with that language's model, through the same image, resolution and mode as the chosen reading. The two readings are then merged word by word into a third reading, which carries both languages and can serve as the page's reading of record; the two original readings are kept beside it, so that an error in the merge can always be traced and undone (see «Provenance», below). A word stays if the primary reading is a valid word of the primary language; otherwise the second reading's word wins, so names, which are in no dictionary, fall to the second reading (docs/REPLICATION.md § 4, stage 8). French was followed by nine more languages (German, Czech, Catalan, Dutch, Polish, Spanish, Swedish, Italian, Danish), Estonian, and on 2 October English (docs/REPLICATION.md § 4, stage 8, and § 9; docs/FAILURE-MAP.md row 5d).

**Where accents can be lost, and why it matters.** The second language's model does not know the Esperanto letters ĉ, ĝ, ĥ, ĵ, ŝ, ŭ, so its reading of an Esperanto word comes without them: it reads *kotizaĵo* as *kotizajo*. Under the word-by-word rule above, any Esperanto word the dictionary does not hold would lose its accents to the second reading. Esperanto builds words freely from roots and affixes, so many correct Esperanto words are in no dictionary. Unguarded, the merge would have rewritten correct Esperanto into unaccented forms, for the sake of the French names around them. This is a change to the text, not only a reading of it. So the record of it matters, and so do the two guards that limit it:

- **The compound test.** A word carrying Esperanto accents that is not in the dictionary still counts as Esperanto, and keeps its accents, if it breaks down into Esperanto roots, affixes and endings with at least one content root of three or more letters. Hyphenated compounds are tested part by part. On test, 15 real compounds out of 15 passed, among them *kotizaĵo*, *poŝtsignoj*, *Ruĝa-Kruco* and *superŝatigita*. Mangled French failed, such as *Genĉve* and *Dĉlĉgation*. The test applies only to words that carry Esperanto accents: applied to plain-letter words, it let mangled French through, such as *Congris* for *Congrès* and *prosperite* for *prospérité*, and one volume of *Esperanto* (UEA, 1906) lost 34 accents that way (docs/REPLICATION.md § 4, stage 8, and § 8, 09-26).
- **The accent-strip guard.** Where the only difference between the two readings is that the second one drops the Esperanto accents, the second reading's word is accepted only if it is a real word of the second language. That case is an OCR error the other way round: the Esperanto model put a hat on a French word, reading *jour* as *ĵour*. Otherwise the Esperanto word keeps its accents. On the first French run, 9,315 such strips were refused because the result was not French, and 2,041 were accepted because it was. The guard does not apply to Ido, which has no accented letters of this kind: there a hat is always an OCR error (docs/REPLICATION.md § 4, stage 8).

**Provenance.** Nothing is overwritten. Each merge is written as a reading of its own (`page-NNNN.<reading>.<language>.arb.txt`), beside the two readings it was made from, which are kept; the rebuild chooses among the readings, and merges can be recomputed from the readings on disk when the rule improves, without new OCR (`--remerge`). A merged word can therefore always be traced to the reading it came from. Merging is skipped on pages whose chosen reading is the PDF's own text layer, because that text did not come from our model (docs/REPLICATION.md § 4, stage 8, guards).

The other guard learned on the way:

- **in chained merges, a later language may not overwrite an earlier one's correct words.** A page with two second languages is merged twice: first with one language, then the result with the other. At first only Esperanto words were protected in the second merge. On *Bohema Revuo*, an Esperanto journal from Bohemia with Czech in it, the Czech merge restored the Czech words. Then a Polish merge, run because Czech misreads can look like Polish, overwrote correct Czech with Polish spellings: *naši* became *naśi*, *že* became *że*, *této* became *tóto*. The item's lexicon score (G4, section 3) fell from 93% to 44%, and 27 items newly failed G4, 25 of them Bohemian. Since then a word is kept if it is a real word of the primary language or of any language already merged on that page (docs/REPLICATION.md § 8, 09-26; an internal record of 26 September 2026, not published).

Languages cascade: restoring one can make another detectable, so the stage is repeated until no new language is flagged (docs/REPLICATION.md § 4, stage 8, and § 8).

### Cyrillic

Russian printed among Esperanto and read with the Esperanto model comes out as Latin-letter junk, and the language detector cannot flag it, because it reads that junk (docs/REPLICATION.md § 8, 09-26). Pages scoring under 30% against every word list were therefore read with the Russian model. A page was accepted as Russian if that reading was at least 90% Cyrillic and at least 15% of its words were in the Russian list after its pre-revolutionary letters were folded to their Soviet equivalents (see «Spelling and script reforms»). This accepted 1,314 pages in 133 items. A blind look at 42 pages found the Russian reading better on 27 of the 30 accepted pages, the same on 3, worse on none (docs/REPLICATION.md § 8, 09-26). Section 4 describes how pages carrying both scripts were then handled.

### The combined text

The rebuild assembles each item's text page by page from the chosen readings: a "mosaic", not one recipe for the whole item (`tools/ocr-rebuild-combined.py`, header). Above every OCR reading rank, in order: the editor's own hand-keyed text of a page; a "ruled" re-read made as the editor directed for a difficult page (rotated, cropped, at 400 ppi); and a vision transcription (section 7) (docs/REPLICATION.md § 4, stage 6; the vision transcription record, an internal record of 27 September 2026, not published). Two texts are written: a search text, which may hold more than one reading of the same print, and a single preferred reading per page, recorded in the files, for handing over into PDF text layers (docs/FAILURE-MAP.md, standing requirement "one preferred reading per page").

## 3. The gate: G1 to G4

The gate applies four tests to each item. Their bars were fixed on 24 September and are not changed without the editor's instruction (the frozen pipeline specification, an internal record of 24 September 2026, not published).

### G1, dead pages: the only test that looks at the image

G1 takes every "silent" page, one yielding under a quarter of its item's median text, and asks whether its image carries ink arranged in lines of type (docs/REPLICATION.md § 5; `tools/ocr-g1-ink.py`, header):

1. The ink test splits dark from light with Otsu's method, an automatic choice of the grey level that best separates an image into two tones. It does this in two stages, because many scans are photographs of a book lying on a dark board. The scan then holds background that is not part of the book but is as dark as the book's print, and a single split mistakes it for ink: it separates board from page, not ink from paper, and the first version reported a clean, blank leaf as 91% ink. So stage one finds the page within the photograph, and stage two separates ink from paper inside the page only.
   A page is called BLANK if its ink covers under 1% of the page. Where the page's tones do not split clearly into print and paper (the paper less than 25 grey levels lighter than the split point), ink is counted more strictly: only pixels darker than mid-grey (128 or below) count, and a page with under 0.5% of such pixels is clean paper (`tools/ocr-g1-ink.py`, the ink measure, as fixed on 28 September; docs/REPLICATION.md § 5). This stricter count is what faint print fell through (below).
2. Bands of rows with enough ink count as lines of type; lines of the page's text with at least 3 letters count as lines of text.
3. A page with at least 3 bands and fewer than half a recognised text line per band (a line of the OCR text with at least 3 letters, as in point 2) is flagged as unread. Ink without line structure is a plate, a stamp or a cover, and is reported separately.

The threshold is 0 dead pages. Before the line-structure refinement of 26 September the test flagged every correctly read half page, 1,912 pages in all; after it, 440 (docs/REPLICATION.md § 5). A look at 20 images then showed that G1 is a triage, not a verdict. Of 12 flagged pages, only 3 had really lost text, and 1 of 8 passed pages had missed a box of type on a coloured background (docs/REPLICATION.md § 5). So the editor ruled that G1 is triage, and that a human is involved at the final stage, to get as many pages into the corpus as possible (docs/REPLICATION.md § 5). G1 is therefore followed by two stages.

First, the image sort. Every flagged page, and every page G1 cannot decide (dark scans, photographs, covers), goes to a blind checker: an AI vision model, which sees the page image beside its final text and does not know why the page was sent. It calls the page NOTHING missing, MINOR (three lines or fewer of masthead, caption or date), LOST (running text missing) or SCRIPT (only another script missing) (docs/REPLICATION.md § 5; RUNBOOK.md § 1a and C9). The sort does not decide what happens to a page; it decides which pages a person must see.

Second, the human stage: the editor adjudicates what the sort leaves, on a review sheet showing each page's image beside its text. In the first sort, of 422 flagged pages on 26 September, 243 were NOTHING, 165 MINOR and 14 LOST (the image sort, an internal record of 26 September 2026, not published). The editor ruled on each of the 14 LOST pages: where another item's text had been filed under the page's name, the source was fixed and both items converted afresh; the others were read again, some turned or cropped to the lost passage first, and where a re-read could not recover the text the editor keyed it in by hand: a table, a title page, an address panel, speech balloons (the editor's rulings, an internal record of 26 September 2026, not published). In each later batch, MINOR and LOST pages become named exceptions in the ledger, so no absence claim covers them; whether any of them is re-read or transcribed by vision is the editor's decision (RUNBOOK.md, C9 and C11a). A page the test cannot decide is never counted as passed (`tools/ocr-accept.py`, header).

G1's blank verdicts were themselves wrong once, and the method's fifth test grew from that (section 6). On grey, speckled scans the inner split had divided the paper's own tones, so pages carrying print were called clean paper. A re-run found 102 of 1,912 blank verdicts wrong, 5.3% (docs/REPLICATION.md § 8, 09-28). A second fault was faint print. In the G5 re-sample of 30 September, two of the 40 pages G1 had cleared as blank were full pages of print (*mondo* 1928 p. 265; *Oficiala Gazeto Esperantista* vol. 5 p. 64). The cause lies in how the ink test counts ink. Where a page's tones are not clearly split into print and paper, the test counts as ink only pixels darker than mid-grey: 128 or below, on a scale where 0 is black and 255 white. The print on these pages was grey of 160 to 185 on paper of about 198, so almost none of it counted: 0.15% and 0.75% of the page, under the bar of 1% below which a page is called blank. A test of absolute darkness cannot see faint print (`tools/ocr-g1-faint.py`, header).

A further instrument therefore re-tests every page G1 cleared as blank, measuring ink relative to the paper around it. It estimates the paper's tone at every point of the page, and counts as ink any pixel at least 25 grey levels darker than its own paper. It then evens out the paper (dividing the image by its estimated paper), stretches the contrast, and reads the result with Tesseract at twice the size. The page counts as READ if this gives a real reading: at least 10 words of four or more letters, 60% of them in one word list. Otherwise it is UNREAD, which does not mean blank; one printed page in the calibration sample could not be read however the image was prepared (`tools/ocr-g1-faint.py`, header). Run on all 1,804 blank-verdict pages on 30 September, it found 84 READ and 1,720 UNREAD (an internal record of 30 September 2026, not published). Its readings were installed only where no stronger reading of the page existed and the new one beat everything the search already held: 7 were installed. The 125 pages that still had under 50 words in the search text went to vision, on the scan together with an evened-out copy, and 96 were transcribed; on 29 the transcriber found nothing to read (internal records of 30 September 2026, not published).

### G2, a second language

Where an item carries a second language, the second-model reading and merge of section 2 must have run on its pages (the frozen specification, not published; docs/REPLICATION.md § 4, stage 7). Whether a second language is there is decided per ITEM, not per page, and it is calibrated afresh on each item, from that item's own words (`tools/ocr-accept.py`, G2):

1. The item's distinct words of four or more letters are collected, from all its pages.
2. For each candidate language, its DENSITY is the share of those words that are in that language's word list and not in the Esperanto list. Words the two languages share prove nothing, so they are left out.
3. The NOISE FLOOR is the median of the densities of ten fixed baseline languages: French, Catalan, German, Dutch, Spanish, Italian, Danish, Swedish, Czech and Polish. Most of the ten are absent from any given item, so their densities measure only chance: OCR junk, names and international words that happen to sit in a word list. The median of the ten is therefore the item's own level of chance matches.
4. A language is PRESENT if its density is more than four times that floor. On *La Belga Sonorilo*, a Belgian journal of 1902, French (2.77% of words exclusive to it) and Dutch (3.05%) both stood well above it, so both were found, and the journal is trilingual.

The baseline is fixed on purpose. When word lists for Estonian, Latvian and Lithuanian were first added as candidates (27 September), their near-zero densities pulled the median down, weak chance traces of other languages crossed the lowered bar, and the items left waiting for a second-language pass went from 3 to 139. The floor is now taken over the same ten languages whatever else is tested, and languages added later, English among them, are tested against it without being part of it (`tools/ocr-accept.py`, G2, the fixed baseline). A language also counts as present when it is required by rule or declared. Ido items require French by rule, because their French is mostly names, which no density test sees. G2 counts a language as handled when at least 95% of the pages that need it have been merged. Three faults were corrected on the way:

- related languages share vocabulary, so the detector had named a neighbour (Polish for Czech journals, Catalan for Spanish); 78 items were corrected on 30 September (docs/FAILURE-MAP.md row 5a);
- English was not among the second languages tested until 2 October, though *The British Esperantist* is about 44% English by function words (docs/FAILURE-MAP.md row 5d);
- G2 applies only to Latin-script languages. Other scripts are handled by the language table (section 4).

### G3, shape

Every page that `page-shape.py` judges list-shaped (rosters, address lists, columns) must have been read in mode 4 (`tools/ocr-accept.py`, header). The reason is the layout of a roster. A membership list typically prints each member as one entry on its own line: a number followed by a name and a town («123. Ivanov, Moskvo»). Read in mode 6, which treats the page as one uniform block of text, such entries were broken up: a member's number could come out on a line apart from the member's name, so that the list no longer says which number belongs to whom. Read in mode 4, which treats the page as a column of separate lines, the entries stayed whole, number, name and town on one line. The text holds the same characters either way; what mode 4 keeps is which number belongs to which member. On *Belga Esperantisto*, mode 4 recovered 266 more complete roster entries from 1.5% less text (docs/REPLICATION.md § 4, stage 5).

**What G3 checks, and what it does not.** G3 itself only checks that a list page HAS a mode 4 reading. Every page is now read in both modes at conversion, so G3 is met there and cannot fail at the gate (RUNBOOK.md § 1a, "Where each test runs"). Whether the page's preferred reading (section 2) keeps the entries whole is a different question, and it is decided not by G3 but by the choice rule: on list pages, among the readings within the word margin of the best, the one with more entry-form lines wins (rule E, section 2).

**How far the choice rule keeps the entries, measured.** The verdicts file records, for every page, how many entry-form lines each reading has and which reading was chosen, so the question can be answered from it directly. Before rule E, a check over the 18,908 list pages of the time found that the chosen reading never had fewer entry lines than the mode 4 reading (docs/REPLICATION.md § 4, stage 5). Under rule E that no longer holds. Measured on 4 October over the current verdicts (the verdicts file, an internal record of 3 October 2026, not published): of 20,269 list pages, the chosen reading has fewer entry lines than the mode 4 reading on 2,506, with 6,561 entry lines fewer. On 2,384 of them a reading won by clearly more recognised words, so the entry count never came into play: mostly the mode 6 reading (1,926 pages), and the PDF's built-in text layer (447), as on p. 296 of the item filed as BK-I-GhP-2014-09-28, with 2 entry lines against mode 4's 50. Over all list pages, the chosen readings still hold more entry lines than the mode 4 readings do (92,836 against 87,221).

**What that means.** For searching, nothing is lost: every page's search text includes its mode 4 reading alongside the chosen one (`tools/ocr-rebuild-combined.py`, the search text), so a name in a roster is found whichever reading keeps the entry whole. What is not guaranteed is the reading of record: on those 2,506 pages, the preferred reading does not keep every roster entry together, so a reader extracting a roster from the preferred text alone (for instance from a PDF/A copy) should check it against the mode 4 reading.

**The fix, 4 October.** The preferred text matters for the copy handed over to the archive, so the choice rule was amended for list pages. The readings in contention are now those keeping at least 95% of the best reading's recognised words, and among them the one with the most entry lines wins; mode 6 holds only if it is level on words. The editor chose the 95% threshold from four measured options (95%, 90%, 80%, or entries always winning). Applied to the stored counts, without new OCR, it changed the preferred reading of 1,264 list pages: 1,247 now keep more entries together, 3,866 entry lines in all, for 11,645 recognised words fewer, and no prose page changed. With the new rule switched off, the same procedure changed 0 of 118,488 verdicts, so it is the old rule plus the amendment and nothing else (`tools/ocr-psm-adjudicate.py`, `choose()` and `--rechoose`). Because G4 scores the preferred reading, the chain was run again and its ledger compared with the current one. One signed item, *La Revuo* 1913.0.1, fell from 65.2 to 64.8 under the list bar of 65; the editor ruled that it keeps the old choice as an exception (`LIST_RULE_EXEMPT`). With that, no item changed class (the ledger comparison, an internal record of 4 October 2026, not published), and the new ledger became the current one.

### G4, lexicon

G4 is the median, over an item's pages of at least 60 words, of the share of words found in the item's language's lexicon. (How the word lists cope with the spelling reforms the corpus spans, in Russian, Ido and Estonian: see «Spelling and script reforms».) The bar is at least 0.75 for prose and at least 0.65 for items with list pages (the frozen specification and the ledger review, internal records of 24 and 30 September 2026, not published; docs/REPLICATION.md § 4, stage 7). The list bar is lower on purpose, because a list is mostly proper names, and proper names are not in any word list: a page of surnames and foreign towns, read perfectly, still scores about 0.73 where prose scores about 0.88. That is the measure working, not damage (the frozen specification, not published). Which language is an item's PRIMARY language, the one G4 scores against? Detection serves as the initial triage: the words of the item's first 60 pages are looked up in the three planned-language word lists, Esperanto, Ido and Occidental, and the list with the most hits wins. These three are the default candidates because they are the languages the corpus is mostly written in, and their lists tell them apart well: Ido texts score 75–79% against the Ido list and about 57% against the Esperanto one, Esperanto texts the other way round (`tools/ocr-accept.py`, G4). Where detection gets it wrong, or the main language is none of the three, the language is DECLARED by item, and a declaration always wins over detection. Of the 23 declarations, 17 are Ido: early Ido is close enough to Esperanto that some Ido items detect as Esperanto (*Progreso* vol. 1 does). Three are English, such as the Ritz speech, which had been scored as Esperanto until its declaration counted (`tools/ocr-quality-scan.py`, `DECLARED`; `tools/ocr-accept.py`, «a declared main language wins», 28 September). The detected language stands only until a declaration corrects it, so in effect the primary language of any item whose language is in doubt is set by hand. The language table of 3 October (section 4) records every language each text prints, but it governs which other-script passes a text gets; G4's primary language is still set by detection and declaration (`tools/ocr-accept.py`). An item counts as Ido, detected or declared, for every rule that turns on it: French is required by rule, and in the merge any Esperanto circumflex in an Ido text is treated as an OCR error (section 2). Library cover sheets are recognised by their wording and not scored: 113 from the ÖNB (the Austrian National Library), which puts a German metadata page in front of every scan, and 2 from Google Books, whose cover page is in English. They are not part of the publication, and since they are always in German or English, scoring them would count words of the wrong language against the item; one such sheet had helped *Progreso* vol. 1 read as Esperanto (docs/REPLICATION.md § 4, stage 7, and § 8, 09-25; `tools/ocr-accept.py`, the cover-sheet rule).

Lexicons are built from clean sources only. OCR output enters a lexicon only through a human, and the 1908 de Beaufront–Couturat delta (the words it adds to the other sources) was reviewed line by line by the editor. Foreign lexicons were expanded to their inflected forms on 26 September, because before that "journaux" did not count as French (docs/REPLICATION.md § 6).

Two extensions of G4 were each defended by a measurement and a blind look:

- **Bilingual credit.** At first G4 counted only words of the primary language, so once the French merge had restored correct French, that French counted AGAINST bilingual journals: 43 items fell below the bar, 34 of them *L'Espérantiste*. Now a word also counts if it is valid in one of the item's second languages (section 3, G2), but only on a page where that language is really present: the page must carry at least 10 different words (of four or more letters) that are in that language's list and NOT in the primary language's list. Words the two languages share prove nothing, so they do not count towards the 10. The limit is per page because counting a second language on every page lifted the Ido items, which require French by rule, by 4.3 points on French names alone; the 10-word limit cut that to 1.5 (`tools/ocr-accept.py`, G4, «bilingual credit, page-local»). Of 926 items with a second language, 222 then crossed the bar. A blind look at 60 pages by 3 readers found the crossing pages GOOD or USABLE on 92%, against 89% of passing and 80% of failing controls (docs/REPLICATION.md § 6, "G4 for bilingual corpora").
- **Auxiliary-language credit.** Items printing Esperanto, Ido and Occidental side by side, such as *Posta Mundi*, give the other two planned languages the same page-local credit. A blind look at 60 pages found the items it let through 95% GOOD or USABLE (docs/REPLICATION.md § 8, 09-26).

Both bars were set in the frozen pipeline contract of 24 September (an internal record, not published, the gate table), and no derivation of either number is on file. The reason the record gives for the lower list bar is the one above: a roster page scores lower by nature, about 0.73 against about 0.88 for prose (the frozen contract, not published; RUNBOOK.md § 1a).

On pages carrying two scripts, G4 scores the Esperanto side alone, using a strictly cleaned text that can understate but not flatter. The Russian side has its own score (section 4) (`tools/ocr-absence-ledger.py`, header; RUNBOOK.md § 1a).

## 4. Pages in two scripts

About 1.2% of the corpus, 1,425 pages in 145 items, carries both Latin-script and Cyrillic text. Seven Russian-Empire journals hold 1,139 of those pages (docs/REPLICATION.md § 8, 09-27). Typical examples are *Ruslanda Esperantisto*, *La Ondo de Esperanto* and *Kaŭkaza Esperantisto*; the last also prints Georgian and Armenian.

### Two readings, searched together

Five successive attempts were made to merge the two scripts of such a page into one text, each judged by a blind look at 44 fresh pages: a checker saw the page image and two readings in random order, the merged one and the current one, without knowing which was which. None was adopted (docs/REPLICATION.md § 8, 09-27; `tools/ocr-mixed-lines.py`, header; `tools/ocr-layout-mixed.py`, header). So that no one repeats them:

1. **Line by line, by word count.** Take the Russian reading of a line where it has more recognised Russian words than the Esperanto reading of the line has words in the Latin-script lists. Failed: current text better on 29 pages, the merge on 8, 7 the same; no Cyrillic line came out GOOD. Cyrillic read as Latin letters hits the Latin-script lists often enough to outscore a Russian list that recognises only about one pre-1918 word in four (the first look, an internal record of 27 September 2026, not published).
2. **Line by line, by script share** («share»). Take the Russian line where its Russian reading is at least 60% Cyrillic letters and under half of the Esperanto line's words are in the Latin-script lists. Better, but not a pass: merge 23, current 15, same 6. The Russian model writes Cyrillic for any text, so it took lines as Russian on poorly read Esperanto and Ido pages with no Russian at all (the second look, an internal record of 27 September 2026, not published).
3. **Line by line, with a page gate** («gated»). First ask whether the page has Russian at all (at least 14% of the words of its Russian reading in the Russian list), then decide line by line as in 2. Merge 19, current 9, same 16; still lost on nearly all-Russian pages, where the current text was already the whole-page Russian reading (the third look, an internal record of 27 September 2026, not published).
4. **The same rule, only on pages under 70% Russian.** It had done best there, so a fourth look tested only that band, against a criterion set beforehand: the merge better on at least twice as many pages as the current text, and the current text better on no more than 5 of 44. Failed: merge 25, current 13. On mostly-Esperanto pages printed in parallel columns, the current text kept the whole Esperanto column, while the merge traded Esperanto lines for part of the Russian (the fourth look, an internal record of 27 September 2026, not published).
5. **Column first.** Find the page's blocks and columns, cut at the gutters, and decide each block as in 2. It read the Russian far better (Cyrillic GOOD on 25 pages against 12), but failed the same pre-set criterion: merge 26, current 14. Overlapping blocks were read twice, duplicating text on 8 pages, and the gutter between two columns was missed on some pages (the fifth look, an internal record of 27 September 2026, not published).

**What a bi-script page's preferred text is.** One text per page must still be named as the preferred reading, the one a PDF/A copy carries (section 2). For pages in two scripts the editor ruled on 30 September that the Latin script has primacy, since these are Esperanto publications, while a single text with both scripts in place remains the ideal. So the preferred text of such a page is its Latin-script reading, and that is the text layer of the PDF/A copy handed over to the archive. The page's other readings, its Russian reading among them, go with it as plain text, for researchers to search separately, for completeness (the editor, 4 October); the page's record (`PREFERRED.tsv`) names the Russian reading as its second script, and it is searched here too (`tools/ocr-rebuild-combined.py`, «other scripts»; the write-ups plan, an internal record of 1 October 2026, not published). The column-first reading of attempt 5 is the nearest thing to the ideal, but it is not used as a reading of record: it duplicates text where blocks overlap, misses some gutters, and failed its pre-set criterion. It could replace the Latin reading as the preferred text only after both faults are fixed and it passes a fresh blind look (the editor's decision of 4 October).

**Why they failed.** Three causes run through the five looks. First, there is no reliable test of whether a given line is Russian. The Russian model writes Cyrillic for any text, so a high share of Cyrillic letters proves nothing; Cyrillic read with the Latin-script models turns into junk that often hits the Latin-script word lists, so word counts mislead; and the Russian word list recognises only about one pre-1918 word in four, so it is a weak detector (attempts 1–3). Second, the layout: many of these pages print Esperanto and Russian in parallel columns, so each printed line runs across both scripts. The checker of look 4 noted that on most pages the script changes on every line, because the columns are joined; whichever reading a line-by-line merge takes, half that line is in the wrong script, and the merge traded Esperanto for part of the Russian (attempt 4). The same follows for a line that switches script within itself: the unit of choice is a whole line, so such a line is right in neither reading. Third, finding the columns first, which deals with the layout, brought faults of its own: blocks that overlapped were read twice, and some gutters between columns were missed (attempt 5).

After the fifth look the work on a merged text stopped. Bi-script pages were 1,425 pages in 145 items, 1.2% of the corpus, and for SEARCH no merge is needed: each reading is right in its own script. So both are kept and both are searched, the Esperanto in the item's search text and the Russian in a search file of its own (docs/REPLICATION.md § 8, 09-27, the decision). The line-by-line merges stay on disk, unused (`page-NNNN.mixed.txt`). The column-first reading of attempt 5 (`page-NNNN.layout.txt`) found a use after all: it is not a reading of record, but since 30 September it joins the search text of every page that has one, because it held 16,232 real Esperanto words on 2,913 pages that no searched text held (`tools/ocr-rebuild-combined.py`, the layout reading). The decision was that for searching no merge is needed, because each reading is right in its own script. Every page past a Russian page gate therefore has its Russian reading written to a separate Russian search file, and an absence claim on such an item searches both (docs/REPLICATION.md § 8, 09-27, "Decision"). This has one limit. Each of the two texts is right only in its own script: the Russian reading turns the page's Latin-script words into Cyrillic junk, and the Esperanto reading turns its Russian into Latin-letter junk. So a single word, a name above all, is found in one text or the other, but a PHRASE that switches script in mid-run, such as a Russian verb followed by a French name in Latin letters, is correct in neither, and a phrase search will not retrieve it. Only a merged text would hold such a phrase, and the five attempts above show why there is none. A "garbage filter" was also tried, which cleans each reading of the other script's junk using character models. Three blind looks found that it beat the raw reading about 2.5 to 1, but lost on about a quarter of pages by dropping real Latin-script text, mostly names. It is kept as a reading aid, never as the search text (docs/REPLICATION.md § 8, 09-27).

The Russian page gate was widened on 2 October. It had kept out 1,237 pages in 138 items whose Russian reading held at least 30 real Russian words; one such page of *Kaŭkaza Esperantisto* 1910 had all five of its missed names in the rejected reading (docs/FAILURE-MAP.md row 8c). Every page with a Russian reading was also re-read from a full-page render, because some Russian readings had been taken from an embedded photograph rather than the page. The fault was found on one almanac, and corpus-wide on 142 pages in 14 items, 28 of those pages in that almanac (the ledger review, an internal record of 30 September 2026, not published; docs/FAILURE-MAP.md row 8b). As of 2 October, 5,551 pages had been re-read this way (the acceptance record, an internal record of 2 October 2026, not published). Like every count in this document, it is a figure at a point in time; the counts are finalised after the next batch is added.

### The Russian-only bar of 40

An item's Russian side may support an absence claim only if its "Russian-only score" reaches 40. That score is the median, over pages with at least 30 Cyrillic words, of the share of Cyrillic words of 3 or more letters recognised by the Russian word lists, after folding old spellings to modern ones (the record of the Russian-only bar, an internal record of 28 September 2026, not published). The editor asked whether the bar was defensible as not ad hoc, and the record answers with three tests. The bar must separate real Russian from non-Russian text that the Russian model turns into Cyrillic-looking junk, erring against the junk.

- On the sample it was chosen from, 40 lay above every junk sample (maximum 26.3) and below 90% of real pages.
- On held-out pages, 4 of 297 real Russian pages fell below it, and 1 of 284 junk pages rose above it.
- On a strictly held-out half, with the word list rebuilt from the other half only, every bar from 37.8 to 43.4 separated the two perfectly, and 40 lies near the middle of that gap.

The record states its caveats. A change to the lists, the folding or the model means re-running the third test, and the item-level rule (a median of pages) was not separately tested.

### The language table as a filter

On 3 October the corpus gained a language table: for each item, which languages and scripts it actually prints as running text, and which it only cites (a title, a name). Only a printed language licenses a model run, a search file or a bi-script label (RUNBOOK.md C5). The table exists because text-only detectors had been wrong in both directions:

- the Russian model writes Cyrillic for any text, so Estonian Fraktur (blackletter type), Polish and Esperanto pages were marked as carrying Russian;
- a blind look of 3 October at the 12 pages behind six doubtful rows, with 4 controls, all 4 answered right, found that four of the six items print no Cyrillic at all (the language look, an internal record of 3 October 2026, not published).

An earlier image check had removed 11 false bi-script marks of the same kind (the ledger review, an internal record of 30 September 2026, not published).

Georgian and Armenian are presence only throughout. A block-by-block reading found Georgian GOOD or MINOR on 81% of pages with Georgian but Armenian on only 41%, with wrong-language blocks on 26 of 44 pages (docs/REPLICATION.md § 8, 09-27). Greek is presence only by the editor's ruling. Japanese, Arabic, Chinese and other scripts get no automatic route: each case goes to the editor (RUNBOOK.md C6.5).

### Old and new Russian spelling, decided per page

The pre-revolutionary letters, the two Russian models and the rule that chooses between them are introduced in «Spelling and script reforms the corpus spans», before section 1; what follows is how the choice is made and checked.

A date-based marker for post-1918 texts was proposed and rejected. The editor ruled that orthography must be decided by genre and page, never by date. Histories, bibliographies and dictionaries quote their sources in the spelling of the source. An émigré press could keep the old spelling long after 1918. A pre-1918 text can print modern-looking Russian, and a 1969 history (Holzhaus) contains modern typescript beside pre-reform facsimiles. And in Ukrainian, і is an ordinary letter (docs/FAILURE-MAP.md, standing requirement of 3 Oct). A blind look at 45 pages bore this out (the orthography look, an internal record of 3 October 2026, not published):

- 4 of 4 controls answered right;
- Holzhaus's *Doktoro kaj lingvo Esperanto* (1969) prints pre-reform Russian in facsimiles of 1888–1905 originals, which a date-based marker would have forced onto the modern model;
- a 2009 volume of *Interlinguistica Tartuensis* prints modern Russian in Soviet bibliographies;
- of the pages the sharpened rule still sent to the pre-reform model, 7 printed Russian (3 pre-reform, 4 modern), and 34 printed no Cyrillic at all.

So:

- the post-1918 marker is kept only for genres that never quote old print, such as the Soviet Esperanto press;
- the rule now requires at least one old-letter word of 4 or more letters that is a Russian word once folded, which reduced the Soviet-press misfires from 103 to 5;
- where the rule picks the pre-reform reading, the modern reading is written into the Russian search file beside it, so a wrong pick loses nothing (docs/FAILURE-MAP.md R1; an internal record of 3 October 2026, not published);
- Ukrainian pages go to their own model (RUNBOOK.md C6.3).

A G5 sample on the Russian side after this change found 1 contradicted page in 40, with 72 of 75 Cyrillic names found (an internal record of 3 October 2026, not published).

## 5. The classes

The ledger (`tools/ocr-absence-ledger.py`) derives each item's class mechanically from the current gate and G1 results, and refuses inputs that are out of date. It was built after a hand-assembled classification overstated what had passed (`tools/ocr-absence-ledger.py`, header). It signs nothing. At signing, the classes stood as follows (the acceptance record, an internal record of 2 October 2026, not published):

| class | items | pages | what an absence search must read |
|---|---:|---:|---|
| ABSENCE-ADMISSIBLE | 2,540 | 103,157 | the item's main search text |
| SPECIAL HANDLING | 166 | 6,791 | every reading of every page held on disk |
| WITH EXCEPTIONS | 41 | 1,934 | the main text and the Russian search file, off the excluded pages and only on the side admitted |
| PRESENCE ONLY | 68 | 1,595 | none: presence findings only |
| total | 2,815 | 113,477 | 2,747 signed lines |

What each class means (RUNBOOK.md § 1a; `tools/ocr-absence-ledger.py`, header):

- **ABSENCE-ADMISSIBLE**: passes G2 to G4 and has a clean G1 on the current text. An absence claim may cover the whole item.
- **SPECIAL HANDLING**: passes only by a special route, for example on its Russian side, or as a Russian-dominant item. An absence claim must search every reading of each page. The class was split out of WITH EXCEPTIONS on 1 October, at the editor's observation that items from which absence can be reached with care are not exceptions (the ledger review, an internal record of 30 September 2026, not published).
- **WITH EXCEPTIONS**: as admissible, but named pages or scripts are excluded. These are pages judged MINOR or LOST, pages missing from the source with no second copy, the other script of bi-script pages, and the 18 advertisement pages the editor ruled out on 2 October. Only ordinary commercial advertisements were excluded; book announcements and publishers' notices stay in (the acceptance record's rulings, not published; docs/FAILURE-MAP.md row 9). The signed line states the side admitted (Esperanto, Russian, or both readings) and the excluded pages (Amendment 1 to the frozen specification, an internal record of 28 September 2026, not published).
- **PENDING**: no valid verdict yet. G1 pages are untested or unsorted, or the text is newer than its test. A pending item gets no line. None was pending at signing.
- **PRESENCE ONLY**: fails G4, too short to score, unscoreable, or ruled so. The editor ruled secondary material presence only regardless of its OCR: two-language dictionaries, an Ido songbook, the Greek issues of *Helena Esperantisto*, and the later *Posta Mundi*. Each such ruling was itemised and assented to one by one (the ledger review, an internal record of 30 September 2026, not published).

### The classes as confidence levels for presence queries

The same classes tell a searcher looking for a person how far to trust a search that finds nothing, and how likely a search is to find a name that is printed. G5 measured, per class, the share of printed names a search of that class's text finds (section 8; the acceptance record, an internal record of 2 October 2026, not published, "The measured recall"):

| class | a printed name is found by the class's search | as of |
|---|---|---|
| ABSENCE-ADMISSIBLE | 194 of 204 names (95%) | 2 Oct (ledger 10-01a) |
| WITH EXCEPTIONS | 156 of 158 names (99%), off the excluded pages | 2 Oct (ledger 10-02c) |
| SPECIAL HANDLING | 235 of 238 names (99%), searching every reading | 2 Oct (ledger 10-02d) |
| PRESENCE ONLY | not measured | — |

Two cautions follow. First, the figure holds for the search the class prescribes, for presence queries as for absence ones: on SPECIAL HANDLING items the names missed by one reading were in others, and only the every-reading search found them (`tools/ocr-search-all-readings.py`, header). A presence query that searches less finds less. Second, a PRESENCE ONLY item may still yield a hit, and a hit is still a finding; but nothing measures how many of its names a search misses, so a miss there says nothing at all.

These five classes are the ones the ledger tool's code and the runbook have (RUNBOOK.md § 1a). The tool's header lists four, because it predates the splitting out of SPECIAL HANDLING on 1 October. The acceptance record's table shows four because none was PENDING at signing.

Some items were moved between classes on evidence the gate cannot see:

- Name lists, such as the 1905 congress list *Nomaro de la kongresanoj* and its Boulogne address list, fail G4 by nature, because names are in no lexicon. They were judged instead by a name check: blind checkers compared each text page, on the image, with its existing search text, and every name the checkers found missing was re-run through the name search. Over 53 pages and about 996 names, 1 name was unfindable, and both lists joined the admissible class (the name-list check and the ledger review, internal records of 1 October and 30 September 2026, not published).
- Three dense bilingual issues of *Kaŭkaza Esperantisto* (1910) and four of *La Ondo de Esperanto* (1909) passed their Esperanto score, but a G5 re-sample found garbled columns and signatures on three of their pages, the only contradicted pages among 24 Esperanto-side pages sampled. They were moved to presence only by a rule: a quarter or more of an item's pages bi-script, and its Russian side under the bar of 40 (the ledger review, not published).
- A short item of up to 4 pages may be cleared by an image look of every page (docs/REPLICATION.md § 9).

The rule that governs the special class became a standing requirement on 2 October. A G5 sample failed SPECIAL HANDLING at 2 pages in 40, both in *La Ondo de Esperanto* 1913. On both pages the missed names were on disk, but in readings the search had not read. Searching the union of every reading scored 0 in 40 on the same sample. The lesson recorded for every user of this OCR is that a single chosen text, however good, is a presence instrument. An absence claim must search every reading held of the page, and a PDF text layer alone cannot support one on these items (docs/FAILURE-MAP.md, standing requirement of 2 Oct). A related gap was closed the same day. Where a scan's built-in text layer had been chosen as a page's reading, our own OCR of that page had not been searched. On one page of *The British Esperantist* the layer held 3 of 6 names and our reading all 6. Our readings now join the search text on the 3,612 pages so affected in absence-class items (docs/FAILURE-MAP.md row 4b).

Two different searches are meant here, and they do not conflict. The ordinary search text keeps a scan's built-in text layer out, unless adjudication chose it as the page's reading (the ruling of 30 September, in the text-layer measurement, an internal record of that date, not published; `tools/ocr-rebuild-combined.py`, header). The every-reading file built for SPECIAL HANDLING items holds every reading on disk, the text layer included (`tools/ocr-search-all-readings.py`, header).

## 6. G5: testing the tests

### Why a fifth test

The G1 fault of 28 September (section 3) had gone unseen because every look at G1 had sampled the pages it flagged or could not decide, never the pages it cleared (docs/REPLICATION.md § 8, 09-28). The editor asked for a test that would have caught it from the start. The rule proposed and approved is that every automated verdict class is audited on its own blind sample, including the classes that clear a page (the G5 proposal, an internal record of 28 September 2026, not published). A random sample of the whole corpus rarely lands on a narrow faulty class: G1's blank class was 1.7% of pages. A 40-page sample of that class alone would have shown at least one wrong page with probability of about 89%, given its 5.3% error rate. The proposal states the limit as plainly: at an error rate of 1 in 100, the same sample catches the fault only one time in three. That is why each class's measured rate is reported, not only a pass or a fail.

### What it measures

G5 measures NAME RECALL: of the personal names printed on a page, how many a search of the page's prescribed text finds. That one number serves both kinds of query. For a presence query it is the confidence that a printed name will be found; for an absence query it is the risk that a name is there but unfound. G5 is therefore not an absence instrument only: it is the corpus's confidence level for finding names at all.

### How it works

Pages are drawn from each class, shuffled together and given to judges in batches of 20. The judges are AI vision models working from the page image, with no access to the key, so they never learn a page's class (`tools/ocr-g5-sample.py`, header). One brief serves every page. The judge reports coverage (NOTHING, MINOR or LOST missing), orientation (UPRIGHT or ROTATED), how much Russian is printed (NONE, SOME or MUCH), and up to ten printed personal names. Each class is scored against its own claim. A page in the blank class is contradicted if the judge finds print that the text does not hold; a page in the Russian-rejected class, if the judge sees much Russian. For the ledger classes the measure is name recall. Every name the judge lists is searched with `tools/ocr-name-search.py` in exactly the text that class's absence search reads, and a page is contradicted if two or more of its names are not found (the acceptance record, an internal record of 2 October 2026, not published, "The measured recall").

The bar is at most 1 contradicted page in 40. The editor set it on 30 September as the maximum, judging it if anything too liberal, and left a stricter bar open to discussion (the G5 audit, an internal record of 28 September 2026, not published, "The scores"). For a class with fewer than 40 pages, every page is sampled and the bar is 0 (RUNBOOK.md § 1a and C11). A class that fails blocks the signing of every item that depends on it, until it is fixed and sampled afresh on pages not used before (the G5 proposal, not published). Judges' returns are filed verbatim with their keys.

### What G5 is not

The bar is a bar on names, not a certificate of absence. A class that passes has shown that, on 40 pages nobody chose, printed names were findable at the measured rate. It has not shown that any given name absent from the text is absent from the page. The acceptance record says this in its first disclaimer: no test certifies absence to a level, and an absence claim remains a claim about what the corpus shows, made with variant and fold-insensitive spellings, the fold covering case, accents and the pre-revolutionary Russian letters (see «Spelling and script reforms»; the acceptance record, an internal record of 2 October 2026, not published, "What the record does not claim"; `tools/ocr-name-search.py`, header).

### How the name search finds a name

G5 can only be as good as the search that looks for each name, and an absence search uses the same tool G5 uses (`tools/ocr-name-search.py`). The search is generous on purpose: a false hit costs a look at the page, while a false miss would become a wrong finding of absence. A name is found when some word of the text, after the changes below, comes close enough to it. The examples are those in the tool's own header:

| the text as the OCR read it | the name sought | how the search connects them |
|---|---|---|
| «Za-» at the end of a line, «menhof» at the start of the next | Zamenhof | the two parts are tried joined |
| «Dietterle-» at a line end, «statistiko» after it | Dietterle | the join is only ONE candidate: joining every line-end hyphen in advance had fused the compound «Dietterle-statistiko» and lost the name |
| «Grosjean-Maupin» | Maupin | each part of a hyphenated name is also tried on its own |
| «Apple-» … «baum», some words apart | Applebaum | a fragment ending in «-» is joined with any fragment up to 40 words later: this is how a name split between two columns comes out |
| «D6hler» | Döhler | folding: both become «dohler» (accent dropped, the digit 6 read as o) |
| «Jglauer» | Iglauer | near miss: one wrong letter is allowed in a name of up to six letters, two beyond |
| «Лебедевъ» (pre-revolutionary spelling) | Lebedev | the final ъ dropped, the Cyrillic transliterated to Latin letters |
| «Мариновой», «Коцынымъ» | Маринова, Коцынъ | Russian case endings stripped from both sides |
| «Яковъ Бородкинъ / Jakov Borodkin» | either form | a name printed in two forms is found if either form is |
| «Bnéow» (small capitals misread) | Bréon | the letters small capitals are misread between (r, n and w; g and c; d and p) are folded together |
| «asnesde» | Asnes | a name run together with a following short word («de») |

Several of these were added after the first G5 run showed the search losing names that were in the text (Appendix B).

### Release v1.1: the confusions measured, not guessed (5–6 October 2026)

The search's map of digits read for letters (0→o, 1→l, 5→s, 6→o, 8→b) was empirical: it held the swaps found among missed names, not a survey of what OCR does to accented letters. Asked whether every accent permutation in the corpus, and Cyrillic, was accounted for, the honest answer was no, so it was measured (`tools/ocr-accent-survey.py`; the report and full table in `docs/OCR-ACCENT-SURVEY-2026-10-05.md` and `.tsv`).

**The ground truth.** 27,308 pages whose true text is known, in two kinds kept apart: 2,243 pages of old print transcribed by an AI vision model (section 7), and 25,065 pages of born-digital PDFs whose own text layer is exact (modern print, which understates old-print damage). Each page was aligned with the Tesseract readings word by word and letter by letter: Latin letters against the block reading, Cyrillic letters against the two Russian readings. Each mangling is priced as the search sees it: the edits left after folding.

**What it found.** OCR often writes not the base letter but a different one, which the fold does not absorb:
- old print: é → ĉ 35% (the Esperanto model forcing its own letters onto other accents), ř → f, t or i 72%, ł → l 98%, ü → ii 23%;
- modern print: ü → ii 50%; ä → ii, ŝi or ĉi;
- Cyrillic: ѣ → ъ 50% (old print) and 75% (modern), even with the pre-reform model; і dropped or read as ш; ъ and ь confused;
- born-digital text layers carry ligature characters (ﬁ, ﬂ, ﬀ), which a search for «fi» does not match.

A one-letter mangling uses up the whole allowance of a name of up to six letters; «ü → ii» and its kind lose such a name outright. Old-print Cyrillic rests on only 56 pages, so it is the least certain part of the survey.

**What changed in the search** (`tools/ocr-name-search.py`, steps 10 and 11):
- compatibility forms are taken apart (NFKC: the ligatures become their letters);
- ł, ø, đ, ı, ß, æ and œ fold to l, o, d, i, ss, ae and oe;
- ъ is taken as ь;
- the name is also tried in every confusion measured at least 5 times and in at least 2% of the letter's occurrences (a dropped letter: 5%), at most 64 spellings per name (`tools/ocr-name-search-confusions.tsv`, generated from the survey: 208 confusions, 66 from old print and 142 from modern, kept apart there, both tried).

**The check.** The four filed G5 samples were scored again from their frozen texts and the judges' returns, with no new vision: the search of v1.0 reproduces the signed figures exactly; the search of v1.1 finds 10 more names (for example the admissible class 194 → 197 of 204, the special-handling class 230 → 233 of 240), contradicts 2 fewer pages, and loses no name. False hits were measured by searching each page's judged names on a page of another item: the v1.0 search already finds something for 10–26% of names, and v1.1 adds about one name in a hundred. The figures of section 8 are not changed: they stand as measured with the search of their day.

## 7. Vision, only where a check shows a problem

"Vision" here means transcription of a page image by an AI vision model rather than by OCR. It is used only where a check has shown a quality problem, never as the default, and the quota is finite (`tools/ocr-vision-batch.py`, header; RUNBOOK.md § 2, rule 10). At intake, new items are converted by OCR (C4), and vision on their pages comes only after the image sort, on the editor's word (RUNBOOK.md § 1a, "Where each test runs").

### The recipe

The recipe has three steps (`tools/ocr-vision-batch.py`, header):

1. **Render.** The page image the conversion itself read is saved in greyscale, at most 2,400 pixels on the long side (about 200 dpi on an A4 page), together with a contrast-boosted copy for faint print. Images are kept.
2. **Transcribe.** A transcriber that may use only file reading and writing, and runs no commands, works from a written brief, a key and the images. It writes its transcription in fixed blocks, one per page.
3. **File.** Each block becomes the page's vision reading, never written over the editor's hand-keyed text or a ruled re-read. The returned text is appended verbatim, with its key, to a dated transcription record.

In the rebuild a vision reading ranks below the editor's hand and rulings and above every OCR reading. The search text keeps every other stored reading beside it (the vision transcription records, internal records of 27 and 30 September 2026, not published).

### The triage

The pages that receive vision are chosen by checks, never by preference:

- pages the image sort judged LOST after every OCR recipe had failed (27 and 29 September);
- the missing lines of MINOR pages, appended to the chosen reading rather than replacing it (docs/REPLICATION.md § 9);
- pages found to be only partly read;
- name-list pages and contents pages set in small capitals, where names were misread past finding;
- named pages the editor directed.

The largest run came from the partly-read pages. G1 examines only silent pages, so a page holding 44% of its item's median text could lose 80% of its print unseen. *La Ondo de Esperanto* 1910.02 p. 8 did exactly that (docs/REPLICATION.md § 8, 09-28). A second reading of every page from a contrast-boosted image found 454 clearly and 825 moderately partly-read pages in 131 items (docs/FAILURE-MAP.md row 4). A blind check then showed that the boosted OCR reading was not a repair: 2 of 25 clear and 5 of 15 moderate pages still lost text. So all 1,279 pages were transcribed by vision (docs/FAILURE-MAP.md row 4 and "Forestalling brute force", step 8). A blind check of 40 of them against whole-page renders found 39 with nothing missing, 1 missing only a printer's signature numeral, and none lost. A second check of 40 more found all 38 second-language pages complete in their own script (docs/FAILURE-MAP.md row 4). On the La Revuo contents pages, 22 of 22 and then 33 of 33 previously lost names were found in the vision transcriptions (the ledger review, an internal record of 30 September 2026, its entries of 1 October, not published).

### Why vision is not the default

There are three reasons:

1. The quota is finite.
2. Vision is checked like everything else. The vision image sort of 29 September called three full pages of print "nothing" or "minor" on ordinary renders (docs/FAILURE-MAP.md row 2). The vision recipe now saves a contrast-boosted copy beside every image (`tools/ocr-vision-batch.py`, header), and the 1,279-page vision run was checked blind against whole-page renders (docs/FAILURE-MAP.md row 4).
3. A method that reads everything by vision would hide the cases where OCR fails, which the checks exist to find and record.

## 8. The measured recall

These figures are the corpus's confidence levels for names: for a presence query, the share of printed names a search of the class's text finds; for an absence query, the risk left over (section 6, "What it measures"). These figures are as signed by the editor on 2 October 2026. They come from G5 samples of 40 fresh pages per class, each sample avoiding every page of the samples before it, 964 pages in all by the last. The judges' returns are filed verbatim (the acceptance record, an internal record of 2 October 2026, not published, "The measured recall").

| class | contradicted pages | printed names found | ledger sampled |
|---|---:|---:|---|
| G1 blank (pages held blank) | 1 / 40 | — | 10-01a |
| ABSENCE-ADMISSIBLE | 1 / 40 | 194 / 204 (95%) | 10-01a |
| WITH EXCEPTIONS | 0 / 40 | 156 / 158 (99%) | 10-02c |
| SPECIAL HANDLING | 0 / 40 | 235 / 238 (99%) | 10-02d |

Every class passes the bar. The ADMISSIBLE and G1-blank classes were sampled on an earlier ledger (10-01a). The changes since then only add search text or exclude the advertisement pages; 14 items left ADMISSIBLE for WITH EXCEPTIONS, and none joined it (the acceptance record, not published, "Known residuals").

### What the figures mean

On a page in the admissible class, chosen by nobody, about 19 printed names in 20 were findable by the prescribed search. On the special-handling class, searched across every reading, 235 of 238 were findable. Two figures are reported per class because they measure different things. "Contradicted pages" counts pages where two or more names were missed, the kind of page on which an absence claim would most likely be wrong. "Names found" counts individual names, and includes single misses on pages that did not count as contradicted. For comparison, the first audit of 28 September, after the name-search fixes but before the later repairs, measured name recall of 93% on the admissible class and 87% on the Esperanto-side-only class (the G5 audit, an internal record of 28 September 2026, not published). An earlier final audit had found 84% of printed names findable by a near-exact search (`tools/ocr-name-search.py`, header).

### Known residuals named at signing

The acceptance record names three ("Known residuals"):

- one name on a page of *La Ondo de Esperanto* 1913 is in no reading held;
- one junk page enters the Russian search, a dotted leader read as Cyrillic letters (search text only);
- the two classes sampled on the earlier ledger, as above.

### Since signing

Two intake batches ("cupel" batches, section 11) were run on 3 October, and their samples are measured the same way:

- **Batch 1.** The first batch, signed on 3 October (RUNBOOK.md § 1), passed G5 on 40 of its 104 scoped pages: 0 of 40 contradicted, 140 of 141 names found (99%) (an internal record of 3 October 2026, not published).
- **Batch 2.** The second batch, the Soviet Esperanto press (53 items, 2,983 pages), first failed G5: SPECIAL HANDLING 5 in 40, WITH EXCEPTIONS 8 in 40, the misses nearly all Cyrillic names. The cause was a Russian reading that had not been run on every page. After the fix, a fresh sample passed: SPECIAL HANDLING 0 in 40, WITH EXCEPTIONS 1 in 40, names 99% and 98% (docs/FAILURE-MAP.md R5).
- **The Russian side.** A G5 confined to the Russian side after the orthography change found 1 page in 40 contradicted and 72 of 75 Cyrillic names (96%) (an internal record of 3 October 2026, not published).
- **The v1.1 search.** Scored again with the widened search of release v1.1 (section 6, «Release v1.1»), the signed samples find 10 more names and contradict 2 fewer pages; no name found before is lost.
These figures will be restated after the next intake, the Korĵenkov run (the editor's answer in the outline of this document, an internal record of 4 October 2026, not published).

## 9. What the method does not claim

**No test certifies absence to a level.** The figures above are name recall on blind samples. An absence claim stays a claim about what the corpus shows, made with variant and fold-insensitive spellings, the fold covering case, accents and the pre-revolutionary Russian letters (see «Spelling and script reforms»; the acceptance record, an internal record of 2 October 2026, not published; `tools/ocr-name-search.py`, header). A sample of 40 that passes at 0 or 1 does not rule out a narrow fault: at an error rate of 1 in 100, such a sample would catch it only one time in three (the G5 proposal, an internal record of 28 September 2026, not published). G5 also cannot see a fault in a class nobody has named, which is why every check must record every page's verdict, including the pages it clears (same proposal, "What G5 does not do").

**Phrases that cross scripts are not found.** On pages printed in two scripts, each script is searched in its own text (section 4), so a search for a single word or name works, but a phrase that switches script in mid-run, such as a Russian verb followed by a name in Latin letters, is correct in neither text and will not be retrieved. A search for such a phrase should be split into its single-script parts.

**An absence search must read what the line names.** A single chosen text, the PDF's own text layer included, is a presence instrument (the acceptance record, not published; docs/FAILURE-MAP.md, standing requirement of 2 Oct). A search of the wrong file is not covered by these figures.

**What the corpus does not hold.** An absence finding reads "not found in the issues held", and the not-held register names what is not held. It lists:

- issues of series otherwise held, for example *La Esperantisto* 1890 nos. 10–11 and 1891 no. 7, *Finna Esperantisto* 1907 no. 8, and the whole of *L'Espérantiste* 1910, which the ÖNB holds under another title but has not digitised;
- printed pages missing inside held issues, for example *Bohema Esperantisto* 1909 pp. 107–116, which become named exceptions;
- whole titles not held, for example *La Sago* (Saratov), found nowhere;
- 14 page-number leads that could not be settled, where the numbering suggests a gap but no printed number confirms it.

(The not-held register, an internal record, not published.) Some losses are in the source itself: the covers of *The Esperantist* 1903–04 were scanned at 150 ppi and dark, and no processing recovers the small type. These are recorded as source-quality losses, not OCR residues (docs/REPLICATION.md § 8, 09-29).

**What stays outside, or is presence only:**

- **Scripts the method does not certify.** Handwriting and lithograph are excluded by looking at the source before conversion (the frozen pipeline specification, an internal record of 24 September 2026, not published). Fraktur, at first excluded, has since been ruled salvageable and is re-read with a Fraktur model (RUNBOOK.md C1, C7a). Georgian, Armenian and Greek are presence only, and other non-Latin scripts are handled case by case (RUNBOOK.md C6.4.3, C6.5).
- **Print the reading does not reach.** Text printed only inside pictures, such as book covers and photographs, is a ruled exception (docs/FAILURE-MAP.md row 6). The excluded pages of WITH EXCEPTIONS items and the mundane advertisement pages carry no absence claim.
- **Search limits the measures may underrate.** The Russian model never writes ѣ or і, so a search for a word in the old spelling finds it only through folding (docs/REPLICATION.md § 8, 09-26). Names in small capitals were a recognised fault class still being worked on at signing (docs/FAILURE-MAP.md rows 5b, 5c). Two of the failure map's rows were completed on 2 October, though the map's own rows still read "Running": row 5c, every *Oficiala Gazeto* page re-read at 600 dpi (3,209 pages; 4 of the 9 missed names recovered on the two failed pages; an internal record of 2 October 2026, not published), and row 8b, the full-page Russian re-read (finished, and the Russian search rebuilt; the same internal record). Rows 5 (dense bilingual broadsheets, too garbled for a name to be found) and 5b (small capitals beyond the Gazeto re-read) are open, as the failure map records them.
- **Dates.** Dates, volume and issue numbers misread in the OCR are a queue of their own. They do not hide a person, but a searcher citing an issue by its printed date needs them right (docs/FAILURE-MAP.md, "Also owed").
- **Material not yet in the corpus at signing:** the Korĵenkov, Manders, *Lingvo kaj Vivo* and *Li kaj Ni* scans, held back as test cases for the intake procedure (the acceptance record, an internal record of 2 October 2026, not published). Of these, the precursor batch was signed on 3 October with scoped lines. Manders received no absence lines at all, as linguistic rather than historical (RUNBOOK.md § 1, C10).

**Scoped lines and secondary literature.** Where the editor scopes an item's lines to page ranges and marks a range as secondary literature, absence there shows only that the work does not mention a person, not that an event did not happen (RUNBOOK.md C10).

## 10. What went wrong, and what it taught

Each of these failures produced plausible text and was invisible downstream until something caught it (docs/REPLICATION.md § 8). These ten are the ones a builder of a similar corpus is most likely to meet. The full list is the appendix.

1. **Audit what a check clears, not only what it flags.** G1's blank verdicts were never sampled, and 102 of 1,912 were wrong (5.3%). A 40-page blind look at the blank class on day one would have had about an 89% chance of exposing the fault (docs/REPLICATION.md § 8, 09-28; the G5 proposal, an internal record of 28 September 2026, not published). Every verdict class needs its own blind sample.

2. **Validate a check on known cases before trusting it.** Two coverage measures tried on 29 September both failed on the first set of pages whose answer was known (302 partly-read pages): one examined only 4 of them, the other flagged none (docs/FAILURE-MAP.md row 4; "Forestalling brute force", step 4). A rotation test was fooled the same way: sideways junk broke into fragments that matched an 18.7-million-form lexicon by chance, and 279 of 321 pages "read better turned" (docs/REPLICATION.md § 8, 09-29).

3. **A single chosen text is a presence instrument.** On a sample where the chosen text failed 2 pages in 40, searching every reading held failed none; the names were on disk, in readings nobody searched (docs/FAILURE-MAP.md, standing requirement of 2 Oct). Keep every reading, search their union for absence, and record a single preferred reading per page separately for hand-over.

4. **Decide per page, by measurement, and count rather than rate.** Neither layout mode was right for a whole corpus, and "keep the longer text" would have rejected the reading that recovered 266 roster entries (docs/REPLICATION.md § 4, stage 2; `tools/ocr-psm-adjudicate.py`). A hit rate crowned a reading that had barely seen the page; a count of recognised words did not (docs/REPLICATION.md § 4, stage 5).

5. **Treat a library's text layer as another OCR, and a born-digital layer as the text.** On scans our OCR beat the built-in text layer on 54% of sampled pages and lost on 21%; on born-digital pages the layer was better or as good on 96% (the text-layer measurement, an internal record of 30 September 2026, not published). Born-digital layers carry their own faults: private-use glyphs, ligatures, x-system spellings. Fix them mechanically, and never by restoring accents from a dictionary (same file).

6. **Normalised Unicode, or nothing.** Before a text is searched or handed over it must be standard Unicode (NFC), with ĉ ĝ ĥ ĵ ŝ ŭ as real letters (docs/FAILURE-MAP.md, step 9). Typed substitutes ("cx" for ĉ), Esperanto letters stored in a font's private slots, ligature glyphs (worst in German quotations), and an Esperanto model forcing Esperanto letters onto other languages' accents all hide words from search. Restoring accents by dictionary changed meanings and corrupted names, and was withdrawn (the text-layer measurement, not published).

7. **A second script hides in plausible junk, so map the languages first.** The frozen specification expected Cyrillic under a Latin model to come out as silence; it came out as Latin-letter junk that the language detector could not flag, because it read the junk (the frozen specification, an internal record of 24 September 2026, not published, "What the gate cannot catch"; docs/REPLICATION.md § 7, and § 8, 09-26). The Russian model in turn writes Cyrillic for any text, so detection by text alone failed both ways. A table of the languages each item actually prints should act as the filter from the start (the language look, an internal record of 3 October 2026, not published; RUNBOOK.md C5).

8. **A rule measured on one population does not transfer to another.** The whole-page Russian accept rule, sound on wholly Russian pages, passed 104 of 160 mixed pages, because the Russian model turns Esperanto into Cyrillic too; swapped whole, those pages would have lost their Esperanto (docs/REPLICATION.md § 8, 09-28). The old-letter rule, calibrated on a mostly pre-reform sample, misfired on the Soviet press (docs/FAILURE-MAP.md R1). Orthography in particular is decided by page and genre, never by the date of publication (docs/FAILURE-MAP.md, standing requirement of 3 Oct).

9. **A second OCR reading is not a repair.** Faint pages "recovered" by a boosted re-read still lost lines: 32 of 61 were still LOST on a blind re-sort, while vision transcription completed 41 of 41 (docs/REPLICATION.md § 8, 09-29). Measure each scan's contrast at conversion rather than rescue faint pages later (docs/FAILURE-MAP.md, "Forestalling brute force", steps 1 and 8).

10. **Change one thing, then check everything that reads it.** A changed label broke an exact-string test in another tool and moved 157 items between classes in a working ledger (R10). A fix to a shared module did not reach a process already running (R3). A rebuild given an incomplete verdicts file silently left 12 items unrebuilt (docs/REPLICATION.md § 8, 09-27). Compare ledgers item by item after any change, check that the files expected to change did change, and read a tool's whole write-set before running it in a new way (docs/FAILURE-MAP.md R6, R10; docs/REPLICATION.md § 8, 09-28).

## 11. Adding material

New items enter the corpus through a fixed procedure, called "cupel" in the project's records, which applies these same tests in a set order. It is set out step by step in the intake runbook (RUNBOOK.md):

1. **C0–C3, intake.** Check that the source is registered with its provenance and is not a duplicate. Look at sample pages to exclude handwriting and to note scripts and Fraktur. Cut scanned spreads into pages, with every cut looked at.
2. **C4, conversion.** Convert the new items only, in both layout modes, with the mask re-read and the PDF's text layer. This makes the readings G3 and G4 depend on.
3. **C5, languages.** The operator proposes the languages each item prints, and the editor confirms them before the language table is rebuilt.
4. **C6, other scripts.** Run the second-script readings the table licenses, forced on every page and before the first chain. Run the missing-leaves and rotation checks.
5. **C7, the chain.** Rebuild, run G1 and the gate (G2–G4), and set the classes, over the whole corpus at once, so that new items are judged by the same rules in the same run as everything already accepted.
6. **C8, comparison.** Compare the new ledger item by item with the current one, to show that nothing already accepted has moved.
7. **C9, image sort.** Finish G1 with the image sort.
8. **C10, scope.** The editor rules which pages get lines, and of what kind.
9. **C11, G5.** Run one blind sample across the batch, per class: 40 pages, or all if fewer, with at most 1 contradicted page at 40 and none below.
10. **C12, signature.** Propose the lines and stop. Only the editor's signature turns them into lines an absence claim may cite.

Any step that has to be patched mid-run counts as a failure of the procedure. It is logged in the failure map, and the runbook is corrected before the run counts (RUNBOOK.md § 6).

| test | applied at | result read at |
|---|---|---|
| G1, dead pages | C7 (chain, step 3) | C9, the image sort, then the ledger re-run |
| G2, language per page | C7 (the gate) | the gate's pending list; second-language pass, then the chain again |
| G3, shape | C7 (the gate; met by C4's mode-4 reading) | C4's check |
| G4, lexicon | C7 (the gate) | C7's check; compared with the current ledger at C8 |
| the classes | C7 (the ledger); re-run at C9 | C8, C9 |
| G5 | C11 | its score |
| the signed line | C12 | the editor |

(RUNBOOK.md § 1a, "Where each test runs".)

## Appendix A: the failure map, condensed

One line per row of docs/FAILURE-MAP.md: what failed · how it was found · what fixed it (status as the map records it).

### The chain from page to search

| row | what failed | how it was found | what fixed it |
|---|---|---|---|
| 1 | Printed pages missing from the scan | Page-number sequence check and a look at the strips | Omitted blanks ruled harmless; real gaps entered in the not-held register; two missing issues recovered from BitArkivo; 22 leads unreadable |
| 2 | A page with print has no text, including faint print G1 called blank | G1 ink test; image sort of all blank-verdict pages; a G5 re-sample (3 of 40 blank pages carried print) | A faint-print instrument (ink relative to local paper; an enhanced re-read) set to run over all 1,804 blank-verdict pages; reopened 30 Sep, the remedy in progress |
| 3 | Text upside down, sideways or in the wrong language | Rotation and flip checks; G2 | Flagged pages rendered, not extracted; turned readings replaced where the upright one reads better |
| 4 | The text holds only part of the page | Known from the final audit of 28 Sep (one page lost about 80%); G5 met it again | Corpus-wide boosted second reading, then vision on all 1,279 partly-read pages; blind 40: 39 nothing, 1 minor, 0 lost |
| 4b | Where a scan's text layer was the chosen reading, our own OCR was not searched | Tracing a missed name in the final G5 (*The British Esperantist* 1911) | Our readings join the search text on those 3,612 pages; the layer stays the citation text |
| 5a | The gate named the wrong (related) second language | Review of G2 flags | Each of a related pair scored on words not in the other's lexicon; 78 items corrected |
| 5d | English was not among G2's second languages | Tracing the final G5 | English added to G2; an English second-model pass on 260 items |
| 5 | Text all there but too garbled for a name to be found (dense bilingual broadsheets) | G5 (*La Ondo de Esperanto* 1909, *Kaŭkaza Esperantisto* 1910) | Partly open: a re-read ruled; worst issues moved to presence only; special handling searches every reading |
| 5b | Names in small capitals misread past finding | G5 re-sample; two judges on the image | Open at the time: small-caps confusions in the name search; a re-read, unique-match aliases and vision on line crops ruled |
| 6 | Print inside a picture | G5 | A ruled exception |
| 7 | The name search missed names in the text | G5 scoring, then each "missed" name checked against the text | Hyphens, case endings, two-form names, transliteration |
| 8 | The image read was not the whole page (born-digital PDFs storing a photograph) | A vision retry rendering doubtful pages whole | A born-digital page's own text layer joins its search text (21,450 pages) |
| 8b | The Russian reading taken from an embedded photo, or thinner than the page | The ledger review; the final G5 re-sample | Every page with a Russian reading re-read from a full-page render; the reading with more real Russian kept (the map says "Running"; finished 2 Oct, per an internal record of that date, not published) |
| 8c | The Russian search rejected pages holding real Russian | The final G5 (*Kaŭkaza Esperantisto* 1910) | Any page whose kept reading has at least 30 real Russian words admitted |
| 5c | Small capitals in the *Oficiala Gazeto* not re-read | The final G5 (two Gazeto pages) | Every Gazeto page re-read at 600 dpi (the map says "Running"; done 2 Oct, 3,209 pages, per an internal record of that date, not published) |
| 9 | Advertisement pages cut and garble names | The final G5 | Mundane advertisement pages a named exception; announcements stay in |
| 7b | A name glued to the next word | The final G5 | A ninth rule in the name search |

### The first intake batches, 3–4 October

| row | what failed | how it was found | what fixed it |
|---|---|---|---|
| R1 | The old-letter rule sent post-1918 pages to the pre-reform model | A count of the rule's choices on batch 2, after the editor's objection that the batch was Soviet-era | A sharper rule (a real Russian old-letter word of 4+ letters); both readings searched where it picks the old model; Russian-side G5 passed |
| R2 | The pre-reform model run on a Soviet-era batch | The editor | Skipped for genres that never quote old print, decided by genre, not date |
| R3 | A running pass had loaded the rule before its fix | Checking which passes import the rule | Stopped, its output removed, restarted; fixes do not reach running processes |
| R4 | The trained character models had been kept in a temporary folder, now empty | The batch script's check | Retrained into a kept folder; standing requirement |
| R5 | The forced Russian reading left out of intake; first G5 failed (5/40, 8/40) | G5 | Russian read on every page of the batch; a fresh G5 passed (0/40, 1/40) |
| R6 | The corpus tool would have rebuilt the whole corpus from the new items' verdicts alone | Reading its write-set before use | A batch-only conversion tool |
| R7 | Item lists split on spaces broke titles | The sampler's refusal | One item per line |
| R9 | The forced re-run demoted accepted Russian pages | The operator, on an implausible tally | The test redone on each page's own reading; a forced reading belongs before the first chain |
| R8 | The image sort missing from the overnight plan; items left pending | The ledger | The sort placed before G5 |
| R10 | A changed label broke an exact-string test; 157 items moved class in a working ledger | The ledger comparison | The rewrite matches any label; ledger re-run, 0 class moves; nothing signed touched |
| R11 | A folder move's citation rewrite edited verbatim records and archived a current file | Filling the runbook after the move | Files restored; the rewrite must skip every kind of verbatim record by name; "current" decided from the project's working record (an internal record, not published) |

## Appendix B: the first G5 run (28 September)

The first G5, on 28 September, sampled 455 pages in 23 blind batches over thirteen classes, and did not pass. By its table, six classes passed, five failed, and two flagging classes were only measured; the audit's own verdict line counts seven passing and six failing (the G5 audit, an internal record of 28 September 2026, not published, "Verdict" and "The scores"). Every failure but one was confirmed on the image by two further independent judges:

- pages whose text was the page read upside down, including three that a rotation check had "repaired";
- faint or partly lost print that G1 called blank;
- lines lost from readable pages;
- names present but garbled past finding on dense bilingual broadsheets;
- text printed only inside pictures.

The exception was a scoring rule that wrongly counted rotated re-read pages as contradicted.

The instrument was at fault too. The name search lost names that were in the text, in four ways:

- joining words across line-end hyphens fused real compounds;
- hyphenated names did not match their parts;
- Russian case endings did not match;
- names given in two forms did not match either form.

All four were fixed while the audit was being scored, and transliteration between Cyrillic and Latin was added; the audit's scores were taken with the fixed search. Before the fix, the ledger classes stood at 12.5%, 10%, 27% and 22.5% contradicted (the G5 audit, not published, "Faults in the instrument, fixed during scoring", and "The scores").

## Sources and checks

Fact-checked 2026-10-04 (an internal record, 4 October 2026, not published); its 18 rows fixed.

### Places where sources differ

- Text-layer counts: 105,034 page readings from 2,588 of 2,905 PDFs (docs/REPLICATION.md, 26 Sep) against 104,950 of 114,965 pages (the text-layer measurement, an internal record, 30 September 2026, not published). Different dates; this document cites the first.
- G1 blank-verdict counts: 1,912 (28 Sep), 1,751 (image sort, 29 Sep), 1,804 (faint-print run, 30 Sep), at different dates (docs/REPLICATION.md § 8; docs/FAILURE-MAP.md row 2).
- Fraktur: excluded by name in the frozen pipeline specification (an internal record, 24 September 2026, not published) and docs/REPLICATION.md § 2; ruled salvageable on 4 Oct (RUNBOOK.md C1, C7a). This document gives the later ruling.
- Partial acceptance: `tools/ocr-accept.py`'s header still states "no partial acceptance"; Amendment 1 to the frozen specification (28 Sep; not published) introduced WITH EXCEPTIONS.
- G5 bar below 40 pages: the sampler's header gives "at most 1 of N"; the runbook gives 0 below 40 (ruled 4 Oct).

### Files each section rests on

Paths beginning with `tools/` or `docs/`, and `RUNBOOK.md`, are in this repository; every other record named here is internal and not published.

- **Abstract**: the acceptance record (an internal record, 2 October 2026, not published); the outline of this document (an internal record, 4 October 2026, not published) (figures as of 2 Oct).
- **§ 1**: `tools/ocr-accept.py` header; `tools/ocr-g1-ink.py` header; the frozen pipeline specification (not published); the acceptance record (not published); docs/REPLICATION.md §§ 7, 8 (09-26).
- **§ 2**: docs/REPLICATION.md §§ 1, 3, 4 (stages 1–8, the entries-rule evidence), 6, 8, 9; `tools/ocr-psm-adjudicate.py` header; `tools/ocr-rebuild-combined.py` header; the text-layer measurement (not published); the vision transcription record (an internal record, 27 September 2026, not published); docs/FAILURE-MAP.md (standing requirement, preferred reading; row 5d).
- **§ 3**: the frozen pipeline specification (not published); docs/REPLICATION.md §§ 4 (stage 7), 5, 6, 8; `tools/ocr-g1-ink.py` and `tools/ocr-accept.py` headers; RUNBOOK.md § 1a, C9; docs/FAILURE-MAP.md rows 2, 5a, 5d; the ledger review (an internal record, 30 September 2026, not published); `tools/ocr-absence-ledger.py` header. The blind looks (of the list rule, of bilingual and auxiliary-language G4 credit, and of G1's ruled re-reads; internal records, not published) are cited through their results as reported in docs/REPLICATION.md, not read directly.
- **§ 4**: docs/REPLICATION.md § 8 (09-26 to 09-28); the record of the Russian-only bar (an internal record, 28 September 2026, not published); the language look and the orthography look (internal records, 3 October 2026, not published); docs/FAILURE-MAP.md rows 8b, 8c, R1, R10, standing requirement of 3 Oct; the ledger review (not published); RUNBOOK.md C5, C6.3, C6.4.3, C6.5; the acceptance record, its rulings (not published); the project's working log (an internal record, entries of 2 and 3 October 2026, not published).
- **§ 5**: the acceptance record (not published); `tools/ocr-absence-ledger.py` header; RUNBOOK.md § 1a; Amendment 1 to the frozen specification (not published); the ledger review (not published); docs/FAILURE-MAP.md rows 4b, 9, standing requirement of 2 Oct, step 7; the text-layer measurement (not published); docs/REPLICATION.md § 9; the name-list check (an internal record, 1 October 2026, not published); `tools/ocr-rebuild-combined.py` and `tools/ocr-search-all-readings.py` headers.
- **§ 6**: the G5 proposal (an internal record, 28 September 2026, not published); the G5 audit (an internal record, 28 September 2026, not published; verdict, scores, failures, instrument faults fixed during scoring; the judges' returns not reproduced); `tools/ocr-g5-sample.py` header; `tools/ocr-name-search.py` header; the acceptance record (not published); RUNBOOK.md § 1a, C11; docs/REPLICATION.md § 8 (09-28).
- **§ 7**: `tools/ocr-vision-batch.py` header; the vision transcription records (internal records, 27, 29 and 30 September 2026, not published); docs/FAILURE-MAP.md rows 2, 4, "Forestalling brute force" step 8; the ledger review (not published); docs/REPLICATION.md §§ 8, 9; RUNBOOK.md § 1a ("Where each test runs"), § 2.
- **§ 8**: the acceptance record ("The measured recall", "Known residuals"; not published); the G5 audit (not published); `tools/ocr-name-search.py` header; docs/FAILURE-MAP.md R5; the working log (an internal record, entries of 3 October 2026, not published); RUNBOOK.md § 1.
- **§ 9**: the acceptance record ("What the record does not claim"; not published); the G5 proposal (not published); the not-held register (an internal record, not published); the frozen pipeline specification (not published); docs/REPLICATION.md § 8; docs/FAILURE-MAP.md rows 5, 5b, 5c, 6, 8b, "Also owed", standing requirement of 2 Oct; the working log (an internal record, entries of 2 October 2026, not published); `tools/ocr-name-search.py` header; RUNBOOK.md § 1, C1, C6.4.3, C6.5, C7a, C10.
- **§ 10**: docs/FAILURE-MAP.md (rows, R1–R11, standing requirements, "Forestalling brute force"); the frozen pipeline specification ("What the gate cannot catch"; not published); docs/REPLICATION.md §§ 7, 8; the G5 proposal (not published); the text-layer measurement (not published); the language look (not published); `tools/ocr-psm-adjudicate.py` header; RUNBOOK.md C5.
- **§ 11**: RUNBOOK.md §§ 1, 1a ("Where each test runs"), 4 (C0–C13), 6.
- **Appendix**: docs/FAILURE-MAP.md, main table and § "cupel's first batches".
