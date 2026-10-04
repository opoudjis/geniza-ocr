# OCR pipeline — replication record

`[The full replication record of the OCR pipeline, started 2026-09-26 and kept current: every pipeline change is written here the same day.]`

**What this file is for.** Someone with the same PDFs and this file should be able to produce the
same texts, and understand why each step is what it is. Every rule below carries **the measurement
that justified it** and **the date and the editor's word** that adopted it. A rule without its
measurement is a guess, and this pipeline has been wrong about plausible guesses about a fifth of
the time.

**The design principle, in one line** (the editor, 2026-09-26: confining a rule to where it gives purchase is sensible, and every refinement so far has been a matter of making rules local rather than global in scope):
**every rule applies only where it has purchase.** Each fault in §8 was a GLOBAL default that was wrong somewhere, and each fix made the rule LOCAL:
- the segmentation mode, the resolution and the language model are all chosen per PAGE, not per corpus;
- structure decides only on LIST pages, and only between near-tied readings;
- the second model reads through each page's OWN route;
- French for Ido comes by rule, but is merged per page;
- G4 counts a second language only on pages where it is present.
When a new rule is proposed, the first question is: where does it have purchase, and how is it kept from acting anywhere else?

---

## 1 · Environment

| component | version | note |
|---|---|---|
| machine | MacBook Pro (Mac17,8) · Apple M5 Pro · 18 cores (6 super + 12 performance, as `system_profiler` names them, 2026-10-04) · 64 GB | performance cores matter: 16 single-threaded OCR processes each get about half a core |
| OS | macOS 26.5.2 | |
| Tesseract | **5.5.3** (leptonica 1.87.0), LSTM engine `--oem 1` | Homebrew |
| language models | Homebrew `tesseract-lang` **4.1.0** | `epo` 4,728,393 B sha256 `71181a6a07af3812…` · `fra` 1,130,365 B `ced037562e8c80c1…` · `deu` 1,525,436 B `19d219bbb6672c86…` · `ces` 3,795,684 B `934bcaf97ef33484…` · `pol` 4,765,518 B `c4476cdbc0e33d89…` |
| pre-revolutionary Russian | `orus.traineddata` (not in the 4.1.0 release): `rus` fine-tuned on *Iskra* 1900–1905, from github.com/AButon-8/iskra_ocr (Apache 2.0), added 2026-09-28 | 11,786,045 B sha256 `cac59e7e4b8e29de…`; provenance and install: `tools/tessdata-extra/SOURCE.md` |
| Poppler | **26.09.0** | `pdfimages`, `pdftoppm`, `pdftotext`, `pdfinfo` |
| Python | 3.14.7 · Pillow 12.2.0 | standard library otherwise |

**Tool versions:** pinned by git commit. **`4fc637d`** (2026-09-26 13:27) holds every pipeline tool as it stands after rule E and the French safety net. A run records the commit it used; a later fix gets a new commit and a line in the failure log (§8).

**`OMP_THREAD_LIMIT=1` for every Tesseract process.** The pipeline parallelises across pages
and files itself. Without the limit each Tesseract also spawns a thread per core, and the load
reached **218 on 18 cores** (2026-09-25). All tools set it.

---

## 2 · Inputs — the list of PDFs

- **Build the list from what is on disk, or from the fetch manifest** (e.g. `geniza/FETCH-U40-MANIFEST.tsv`).
  **Never** build it from the file names of earlier output, and never from a directory listing of a fetch.
  - Three work lists in one week skipped real material by trusting a name: *La Lumo*, *The Australian Esperantist* 1908–09, *Suisa Idisto* 1922, and the per-issue *Belga Sonorilo* 1909–12.
  - The fetch tool once counted a file cut off at 2 MiB as done.
- **Look at one page of each new corpus first** (by vision). Handwriting, lithograph and fraktur return confident nonsense that nothing downstream detects. Exclude them by name.
- **Output root:** `sources/ocr-rendersearch/`. **Never `sources/ocr/`.** That root is cited — 22,257 fact-line locators point into it — and a cited text is never replaced in place.

---

## 3 · Files and names

Per corpus `<stem>` (the PDF's base name), under the output root:

| file | what it is | written by |
|---|---|---|
| `<stem>/page-NNNN.txt` | reading at `--psm 6`, `-l epo` (stage 1) | `ocr-pages.py` |
| `<stem>/page-NNNN.psm4.txt` | same image, `--psm 4` | `ocr-psm-both.py` |
| `<stem>/page-NNNN.hr.txt` · `.hr.psm4.txt` | re-read at a BETTER RESOLUTION than stage 1 used, psm 6 / psm 4 | `ocr-mask-reread.py` |
| `<stem>/page-NNNN.tl.txt` | the PDF's own text layer | `ocr-textlayer.py` |
| `<stem>/page-NNNN.fra.txt` | second model (French) through the chosen reading's route | `ocr-second-model.py` |
| `<stem>/page-NNNN.<winner>.arb.txt` | word-by-word merge of the chosen reading with the second model, **named by the reading it was merged with** | `ocr-second-model.py` |
| `<stem>/page-NNNN.ruled.txt` · `.ruled.json` | the page re-read as the editor's G1 ruling directed (rotated, cropped, 400 ppi, best of psm 6/4/3/11), with every candidate's count | `ocr-ruled-reread.py` |
| `<stem>/page-NNNN.hand.txt` | the editor's own transcription of the page | by hand |
| `<stem>/page-NNNN.hand-add.txt` | the editor's transcription of only the PART of the page the OCR lost; appended to the chosen reading, not replacing it | by hand |
| `<stem>/CANONICAL.md` | which reading is in the combined text, per page, and why | `ocr-rebuild-combined.py` |
| `<stem>.txt` | the COMBINED text: `=== page N ===` markers + the chosen reading per page | `ocr-rebuild-combined.py` |

**Nothing is overwritten.** Every reading is its own file; only `<stem>.txt` is rebuilt, and it is derived.
A tool that globs `page-*.txt` must match **base pages exactly** (`page-\d+\.txt`), because the glob also matches every reading. Found 2026-09-26, when three tools were caught by it.

---

## 4 · The stages — commands, parameters, why

One command runs stages 1–7 in order, re-runnably: `tools/ocr-run-corpus.sh <tag> <pdf-list>`
(env `FILES=4 JOBS=5`). The stages individually:

### Stage 1 · ACQUIRE + READ — `tools/ocr-pages.py <pdf> --out <root> --lang epo --psm 6 --jobs 5`

- **Choose the image per page from `pdfimages -list`:**
  - exactly **one** stored image → **extract it byte-for-byte** (`pdfimages -j -p`);
  - **several** images → render with `pdftoppm` at the document's **median native ppi**;
  - **no** image → render at **300 ppi** (`TEXT_PPI`).
- Why extract rather than render: rendering costs 28.6 s/page at 300 dpi against 0.06 s/page extracted, and the OCR of the extraction is better. A fixed 300 was right for no scan.
- **The no-image rule changed on 2026-09-26** (approved by the editor, 2026-09-26). Before that, image-free pages were rendered at the median ppi of the document's *pictures*.
  - *Recenzo pri Universalaj Lingvoj* p.9 was rendered at 43 ppi and read as **0 characters**; at 300 ppi it reads **1,432**.
  - *Bibliografio di Ido* (3rd edition) was rendered at **9 ppi**.
  - Affected: 107 PDFs (4,328 pages) below 150 ppi, and 124 PDFs (5,101 pages) at 150–249.
- **Safety net.** A page yielding under ¼ of the document's median is re-read by the other route (extract ↔ render), and the longer reading is kept.
- Parallel: several files at once (`xargs -P 4`, a lock directory per file), and rendering parallel within a file.
  - Serial rendering had left the machine at 1 render and 0 OCR processes on 18 cores: about 1 page/s.
  - Parallel runs measured 2.5–4.6 pages/s, over different files, so the two effects aren't separated.

### Stage 2 · SEGMENT — `tools/ocr-psm-both.py --pdfs <list> --root <root> --files 6 --jobs 3`

- **Every page is also read at `--psm 4`, on the same image and through the same safety net.**
- **Why every page** (the editor ruled on 2026-09-25 that the rule should change to what the measurement had shown). On 194 prose pages psm 4 won 22%, psm 6 won 13%, and 64% tied. Neither mode dominates, so no default is right. The earlier rule (psm 4 only where `page-shape.py` flags a list) was a guess.
- **Same image** (`tools/ocr_page_images.py`, 2026-09-25). The tool had taken the first image extracted and had no safety net. *Progreso* 5 p.533 read 28 characters that way, against 505 by the conversion's route.
- **Files in parallel** (2026-09-26). One file at a time gave 53 pages in 10 minutes on 4-page, 600 ppi issues; 6 files at once gave 3.0 pages/s.

### Stage 3 · RESOLUTION — `tools/ocr-mask-reread.py --pdfs <list> --root <root> --jobs 16`

- **(a) Colour layer + text mask.**
  - Some PDFs store a page as colour layers at 100–173 ppi plus a 1-bit JBIG2 text mask at 240–900 ppi. `pdfimages -list` shows these as `image` rows plus a `mask` row, and stage 1 counts only `image` rows.
  - Pages with a full-page mask (width ≥ 1000) that out-resolves the colour layer by > 1.2× are re-read at **the mask's ppi, capped at 400**, in both psm modes.
  - 163 PDFs · 3,470 pages: the Kraków JBC scans, *Tra la Mondo*, *Internacia Socia Revuo*, *Gento Esperanto*, *Belga Katoliko*.
  - A first census said 291 PDFs. It was fooled by the small logo mask on ÖNB cover sheets.
  - Measured on 3 pages each, old ppi → mask ppi:
    - *Tra la Mondo* contents: 1,771 → 11,184 chars;
    - *Gento*: 69.3 → 72.1%;
    - *Revuo* p.11: 214 → 1,019 chars;
    - Kraków at 900 ppi: 65.6 → 63.7%, which is the reason for the 400 cap. The cap is provisional, resting on one sample.
- **(b) Image-free pages** that stage 1 rendered below 250 ppi (see stage 1) are re-read at 300. They use the same `.hr` files.

### Stage 4 · TEXT LAYER — `tools/ocr-textlayer.py --pdfs <list> --root <root>`

- One `pdftotext -enc UTF-8` call per document, split on form feeds. A page with ≥ 20 non-space characters gets `page-NNNN.tl.txt`.
- 2,588 of 2,905 PDFs carry a layer, giving 105,034 page readings: libraries' own OCR under their scans, and born-digital text.
- **It competes, it does not replace** (the editor ruled on 2026-09-26 that the PDFs' own existing text is itself OCR-derived and already compromised, so it is to be treated as one more image). A library's layer is someone else's OCR, and a born-digital font without a Unicode map mangles ĉ/ĝ/ŝ.

### Stage 5 · CHOOSE — `tools/ocr-psm-adjudicate.py <root> --write OCR-PSM-VERDICTS-<tag>.json`

**RULE E, in force from 2026-09-26** (approved by the editor, 2026-09-26). Per page, among every reading present (psm6 · psm4 · hr6 · hr4 · tl):
- **prose pages** (shape < 0.55): the reading with the **most recognised words** wins, by > max(2, 2% of psm 6's count); otherwise psm 6 holds;
- **list pages** (shape ≥ 0.55, the G3 test): among readings within max(2, 2% of the best count) of the best, the one with the **most entry-form lines** wins; psm 6 holds a tie.

Recognised means in the Esperanto, Ido or Occidental lexicon. Entry-form line: `^\s*\d{1,4}\s*[.,)]\s*\S.*?,` or `^\s*[^\W\d_][\w'’\-]{1,}\s*,\s*\S.*?,`.

Result over 114,924 pages: psm6 94,970 · psm4 9,040 · tl 8,418 · hr6 1,714 · hr4 782. **Recognised words +850,866** over psm 6 alone (against +223,114 under the previous rule). The tool's totals match the simulation exactly (lists 3,399,031 · prose 26,628,511 words). The evidence for rule E is below.

**The rule before 2026-09-26** ran entries first on every page: (1) most entry-form lines; (2) most recognised words by the margin; (3) psm 6 holds.
- **Why structure first:** on *Belga Esperantisto*, psm 4 recovered **266 more complete roster entries out of 1.5% LESS text**. The characters were always there; what changed is that numbers stayed attached to their members.
- **Why a count, not a rate** (approved by the editor, 2026-09-25): a rate crowns the reading that barely saw the page. *Revuo* p.11 read 214 chars at 93.8% and 1,019 at 61.3%.
- 2026-09-25, over 114,924 pages: psm4 won 26,174, hr4 887, hr6 611, psm6 held the rest. **Entry-form lines +49,090 (+17%); recognised words +338,644.**
- **Check:** across all 18,908 list-shaped pages, the chosen reading never has fewer entries than the psm 4 reading. This is what makes G3 hold by construction.

### Evidence for the entries-rule debate (2026-09-26: the editor asked for it to be measured; he did not want structure to take priority over words, since missed structure is more remediable than missed words, but asked for a more contained subcorpus and more evidence)

Pages classified by `page-shape.py`'s test (shape ≥ 0.55 = list-shaped, the G3 test): **18,908 list pages of 114,924 (16%)**.
Every rule re-run on the recorded per-page figures (`OCR-PSM-VERDICTS-2026-09-26.json`):

| rule | lists: words | lists: entries | prose: words | prose: entries |
|---|---:|---:|---:|---:|
| ceiling (best reading's words, every page) | 3,407,574 | — | 26,674,784 | — |
| A current — entries → words → psm6, everywhere | 3,293,534 | 101,328 | 26,106,256 | 275,640 |
| B words only, everywhere | 3,399,461 | 82,316 | 26,628,511 | 226,451 |
| C lists: entries first · prose: words | 3,293,534 | 101,328 | 26,628,511 | 226,451 |
| D lists: entries if ≥ 90% of the words · prose: words | 3,373,526 | 96,679 | 26,628,511 | 226,451 |
| **E lists: words first, entries break near-ties (within the 2% margin) · prose: words** | **3,399,031** | **90,129** | **26,628,511** | 226,451 |

- On prose, «entries» decided **34,873 pages (30% of all)** — psm4 15,168 (−114,323 words), text layer 11,731 (−377,933), psm6 6,817, hr 1,157. On prose the entry pattern is mostly noise (`Sed, kiel ni vidis, …` matches it).
- Rule E keeps all but 430 of the words-only total on lists and recovers 41% of the extra structure.
- Blind visual check of 14 list pages where A and E disagree (an internal record, 2026-09-26, not published): **E 8 · A 5 · tie 1**. E wins every page where A chose a shredded reading; the lexicon COUNT misjudged at least 2 pages (numbers, names, other languages are in no lexicon); a CONTENT count (lexicon words + numbers + capitalised names) agrees with the look on 9–10 of 13 against 8 of 13.

### Stage 6 · ASSEMBLE — `tools/ocr-rebuild-combined.py <root> --verdicts OCR-PSM-VERDICTS-<tag>.json`

- `<stem>.txt` = the chosen reading of each page, or that reading's **second-model merge** if one exists **for that same reading** (`page-NNNN.<winner>.arb.txt`).
- A merge made with a reading that is no longer chosen is ignored.
- A **ruled** re-read (`.ruled.txt`) outranks every OCR reading and merge; the editor's **hand-keyed** text (`.hand.txt`) outranks everything. Both come from the G1 review, page by page, and are recorded in `OCR-G1-RULINGS-<date>.md` (the rulings) and `OCR-G1-RULED-<date>.tsv` (the re-read list: corpus, page, PDF, languages, rotation, crop).
- `CANONICAL.md` records every page's reading and the rule that chose it.

### Stage 7 · GATE — `tools/ocr-accept.py <root> --psm-used 4 --write OCR-GATE-<tag>.md` · `tools/ocr-g1-ink.py`

| check | measure | threshold |
|---|---|---|
| G1 dead pages | see §5 — **triage, not a verdict** | flagged pages looked at; human final stage |
| G2 language | every second language above 4× the median noise floor (exclusive density, over 10 candidate lexicons) **+ by rule / declaration** | present ⇒ second model run |
| G3 shape | every page read both ways and chosen by entries first | holds by construction; check in §4 stage 5 |
| G4 lexicon | median per-page hit-rate (pages ≥ 60 tokens) against the corpus's **detected** primary language | ≥ 75 prose · ≥ 65 roster |

**G2 checks its own specification** (from 2026-09-26): a second language counts as handled when `SECOND-MODEL.json` shows ≥ 95% of pages merged in it, text-layer pages excepted. Before, any second language simply blocked acceptance for ever. With French recorded, passes G2–G4 rose 1,717 → 2,028.

**G4 credits a second language page-locally** (adopted by the editor): a word counts if it is valid in the primary language or in a second language of the corpus present on that page (≥ 10 exclusive word types). G4 failures 667 → 445. Blind look: an internal record, 2026-09-26, not published.

What the gate scores:
- **the combined mosaic** — until 2026-09-25 it scored the psm 6 page files, which on psm 4 winners is not the accepted text;
- **not library cover sheets**, recognised by their wording: ÖNB `Nationalbibliothek … (Zitierlink|Nutzungsbedingungen)`, Google `digital copy of a book that was preserved|books.google.com`. That's 113 ÖNB and 2 Google;
- **the primary language, detected per corpus** among Esperanto / Ido / Occidental by lexicon hits over the first 60 pages, or declared in `ocr-quality-scan.py` `DECLARED`.

G2 rules and declarations:
- **Ido corpora require French BY RULE** (approved by the editor for G2, 2026-09-25). Their French is names, which no density test sees, and the Esperanto model cannot emit an accent: 0 é/è/à/ç across *Progreso*. On 11 pages the French model left the Ido hit-rate flat (71.9 → 71.1%) and restored the accents.
- **Known French titles are declared** (`FRENCH_TITLES`): *L'Espérantiste*, de Beaufront's journal, which defected to Ido and stayed bilingual for a while (editor).
- **The flags are real.** Checked 2026-09-26: Czech in *Bohema Revuo* / *Bohema Esperantisto*; Polish in the Kraków scans; Swedish in *La Espero*; German in the Lublin scans. The words driving each flag are genuine.

### Stage 8 · SECOND MODEL — `tools/ocr-second-model.py --gate … --verdicts … --pdfs … --root … --lang fra --page-gate 0`

- For each page of a corpus flagged for the language, the second model reads **through the chosen reading's own route**: same image, same resolution, same psm. The two texts are then merged by `ocr-arbitrate.py`'s `arbitrate()`, where a token stays if the primary reading is a valid primary-language word, and the second reading wins otherwise. Names fall to the second reading because they are in no dictionary.
- **The safety net applies here too** (fixed 2026-09-26). If the second reading comes in under ¼ of the chosen reading, the page is rendered and read again. This covers pages the conversion rescued by rendering, where the extracted image is only a picture. If the reading still falls short, **nothing is merged** and the page stays open for a re-run.
  - Before this fix, *Ido-Saluto* 2025 p.23 gave 0 characters against 2,155 in the chosen reading, and was marked done after a merge that changed nothing.
- **The Esperanto word test knows compounding** (the editor, 2026-09-26: Esperanto is productive, so forms should not be discarded over-eagerly, and the Esperanto parser must be aware of agglutination as well as compounding, as in kotizo > kotizaĵo and Ruĝa-Kruco). A word CARRYING SUPERSIGNS that is not in the dictionary counts as Esperanto if, after its ending, it segments into roots, affixes and linking -o- with at least one content root of ≥ 3 letters. Hyphenated compounds are tested part by part. Tested: 15/15 real compounds pass (`kotizaĵo`, `poŝtsignoj`, `Ruĝa-Kruco`, `superŝatigita`); mangled French fails (`Genĉve`, `Dĉlĉgation`).
  - **Local, not global:** applied to plain-letter words, it let mangled French through the corpus's foreign stems (`Congrès` → `Congris`, `prospérité` → `prosperite`; UEA 1906 lost 34 accents). So it applies to hatted words only.
- **Hat-strip guard.** A merge that only strips supersigns (`kotizaĵo` → `kotizajo`) is accepted only if the result is a real word of the second language (`ĵour` → `jour`). First French run: 9,315 strips were not French, 2,041 were. **Not for Ido**, which has no supersigns: there a hat is an OCR error.
- Scratch comparison on 3 samples, old rule → new: UEA 1906 accents 325 → 332 and Esperanto supersigns **26 → 103**; *L'Espérantiste* 1914 accents 589 → 655; *Progreso* 5 unchanged.
- **Several second languages, chained.** Each language merges onto the previous language's merge (`page-NNNN.<w>.fra+nld.arb.txt`); the rebuild takes the longest chain for the page's chosen reading.
- **Merges keep the page's lines** (`merge_lines()`, 2026-09-26): the decision is `arbitrate()`'s, token for token, but each word is put back on the line of the base reading it came from; words the other reading adds go on the preceding base word's line.
- **Chained merges protect earlier languages** (2026-09-26): in a merge onto an earlier language's merge, a token is kept if it is a real word of the primary language OR of any language already merged on that page.
- **`--remerge`** recomputes merges from the second readings already on disk, with no OCR, for when the merge rule improves.
- **Languages CASCADE — iterate until no new flags.** Restoring one language's accents can make another detectable (gate h, 2026-09-26: 122 corpus–language pairs flagged only after the first pass, e.g. the *Enciklopedio* front matter's French). So the second-model stage is re-run on the new gate's flags, skipping everything already merged, until G2 shows no newly detected language.
- **Record for the gate:** `<stem>/SECOND-MODEL.json` — per language, pages merged / skipped as text layer / total.
- **Nine more languages** (2026-09-26, the editor directed that the next problem be addressed for the same reason): German, Czech, Catalan, Dutch, Polish, Spanish, Swedish, Italian, Danish. Measured on 15–33 sample pages each at gates 0/5/10: large gains on pages rich in the language (e.g. Czech +1,476 accents, +577 recognised words; Swedish +1,483 / +889), and on pages with little of it gate 0 still raised primary-language words in every language (+6 to +79). Gate 0 for all.
- **Why not `ocr-arbitrate.py` on the PDF:** it renders every page itself at a fixed 300 dpi in greyscale and one psm, so its readings are of a different image from the chosen one.
- **Guards:**
  1. **Skip pages whose chosen reading is the text layer.** It isn't our model's output, and arbitrating text that already used the right model degrades it (*Belga Sonorilo* 1910: Lemaire 56 → 36).
  2. **The primary lexicon is the corpus's language.** On an Ido corpus, testing Ido words against Esperanto puts French accents on Ido (`téorlo`). `IDO_MODE` treats a supersigned letter in Ido as impossible.
  3. **Page gate 0 for French.**
- **Page gate, measured 2026-09-26** (3 samples × gates 0/3/10):

  | sample | accents | accented names | recognised words | ĉ/ĝ/ŝ wrongly in Ido |
  |---|---|---|---|---|
  | *Esperanto* UEA 1906 | 0 → 664 | 0 → 53 | 2,406 → 2,878 | — |
  | *L'Espérantiste* 1914 | 0 → 621 | 0 → 30 | 8,368 → 8,777 | 372 → 33 |
  | *Progreso* 5 (26 pp.) | 0 → 43 at gate 0 · **0 at gate 10** | — | 3,720 → 3,817 | 22 → 3 |

  - Gate 10, which was measured against Catalan, leaves Ido-with-French-names untouched.
  - The damage count did not move with the gate. The 37 "suspect accents" on UEA are almost all genuine French missing from the lexicon (`réservés`, `première`, `Sébert`).
- **Run 2026-09-26 (rule E choices):** 422 corpora · 19,569 pages merged · 436 pages where French was the page's majority language (merged French-first). Gate g: across the French corpora G4 rose +1.2 points on average; 43 bilingual corpora (34 *L'Espérantiste*) fell below the bar by ~1.9 points because G4 counts only primary-language words. **Open:** G4 for bilingual corpora.
- Scope 2026-09-25: 405 corpora · 28,172 pages, of which 166 Ido corpora (20,989 pages) are by rule.

---

## 5 · G1 — triage with a human final stage

`tools/ocr-g1-ink.py --pdfs <list> --root <root> --write OCR-GATE-G1-<tag>.md` (process-parallel, `--files 12`)

1. A **silent page** is one under ¼ of the corpus median text.
2. **Ink test**, on the image the conversion used, downscaled to at most 900 px:
   - two-stage Otsu: first board vs page (the bright bounding box), then ink vs paper inside it;
   - no bimodality (paper − threshold < 25) → blank;
   - ink < 1% → **blank**.
3. **Lines of type** = bands of rows ≥ 2 px tall with > 3% ink. **Lines of text** = lines of the combined text's page with ≥ 3 letters.
4. **Flagged ("unread")** when there are ≥ 3 bands and fewer than 0.5 text lines per band. Otherwise the page is plate, cover or short page.
   - This refinement came 2026-09-26 (the editor directed that the test be refined first, then looked at). «Silent» is not «empty», so the unrefined test flagged every correctly-read half page: all 15 *Progreso* volumes «failed».
   - Result: 1,912 → **440** flagged pages, in 218 corpora.
5. **Look** (an internal record, 2026-09-26, not published; 20 images):
   - of 12 flagged, 3 really lost text (9 false alarms: show-through, paper texture, photos);
   - of 8 passed, 1 missed a box of type on a coloured background.
   - Real loss: display type and mastheads, type on colour, one low-resolution render.
6. **G1 is a TRIAGE list, not a verdict** (the editor, 2026-09-26, confirmed that G1 is triage and required a human in the final stage, to get as many pages in as possible). A vision pass sorts the flagged pages; **the editor adjudicates** what remains, on a sheet with image and text side by side.

---

## 6 · Lexicons — `tools/lexicons/`

Built from clean sources only. **OCR enters a lexicon only through a human.**
- **Esperanto etc.:** `tools/build-lexicons.py`, see `_MANIFEST.md`.
- **Foreign languages — INFLECTED since 2026-09-26** (the editor ruled that the inflections are indispensable). Hunspell `.dic` + the dictionary's own `.aff` rules, expanded with `unmunch`, letter-only forms kept (registered in `tools/lexicons/hunspell/SOURCE.md`). French 81,691 stems → 744,651 forms; German → 357,780; Czech → 3,977,556; Polish → 3,479,853; Danish → 1,378,733; Spanish → 922,177; Swedish → 839,741; Dutch → 670,733. Before this, `journaux` and `jeunes` were not «French words», and every validity test ran on stems.
- **Ido:** `tools/build-ido-lexicon.py` → 605,996 forms. Sources, see `_MANIFEST-ido.md`:
  - ILSGB Ido→X dictionaries — dotted headwords, plus closed-class particles tagged `{prep.|adv.|pron.|konj.|artikl}` (`por` and `sur` were missing until 2026-09-25);
  - io.wiktionary `{{io}}` sections and root-page derivations;
  - paradigm generation;
  - the **1908 de Beaufront & Couturat delta, reviewed line by line by the editor**: `ido-1908-reviewed.tsv`, review in `IDO-1908-DELTA-REVIEW-2026-09-25.md`, with the 1908 `y` spellings accepted as a rule.
- Early Ido (*Progreso* 1908) still under-scores: its `jam`, `tiu`, `kun` are in no clean source.

---

- **Second blind look, 40 pages from 40 titles** (an internal record, 2026-09-26, not published): **rule E 26 · current rule 13 · tie 1.** The content count did NOT beat the lexicon count at this size (26 vs 26 on OVERALL; 24 vs 26 on WORDS) — the 14-page hint was noise. Rule E stands on the lexicon count.

### G4 for bilingual corpora — measured 2026-09-26 (the editor agreed, judging it sensible to confine the rule to where it gives purchase)

926 corpora with a flagged or declared second language were rescored three ways. Of them, 419 fail G4 when only primary-language words count.

| second-language words count… | fail → pass | mean lift, all 926 | mean lift, 157 Ido-by-rule corpora |
|---|---:|---:|---:|
| on every page | 233 | +7.3 | +4.26 |
| on pages with ≥ 5 exclusive second-language word types | 232 | +6.8 | +2.69 |
| **on pages with ≥ 10 exclusive second-language word types** | **222** | +6.3 | **+1.51** |

- The corpora that cross are genuinely bilingual: *L'Espérantiste* 63 · *Esperanto* (UEA) 19 · *La Espero* Swedish edition 16 · *Jahrhundert des Esperanto* 13 · the Lublin and Kraków scans · *La Suno Hispana*.
- The ≥ 10 page rule keeps the Ido-by-rule inflation (French NAMES are not French text) to a third of the global rule's.
- **Blind look** (an internal record, 2026-09-26, not published; 60 pages, 3 readers): GOOD or USABLE on 92% of the crossing pages, against 89% of passing and 80% of failing controls. The crossers read like passes. **Proposed: ≥ 10**, pending the editor's word.

## 6b · Standing rule for evidence

- **Blind looks of ≥ 40 pages** decide rules that rest on a visual check (the editor ruled on 2026-09-26, as a general principle, for more blind looks, 20 being too few). Readings labelled X/Y in random order; the key outside the reader's folder; the report filed intact, then unblinded.

## 7 · Known limits and open problems

- **Russian read as Latin look-alikes.** *Kovno Esperanto* and *Bulteno TEKS* contain Russian, which the `epo` model outputs as `KOBHO` (КОВНО), `DcnepaHTo` (Эсперанто), `KAKb` (какъ). It is mangled, not silent, and G2 cannot see it. **Open:** detect it and run a Russian second model.
- **Display type, mastheads, type on coloured backgrounds** are not read (G1 look). Stated limit.
- **Handwriting, lithograph, fraktur** — look before converting; exclude by name.
- **The 400 ppi cap** rests on one 900 ppi sample.
- **G4 on short issues** — they are mostly COMPLETE issues, and their low scores catch real problems (the Russian above; French accents). **Proposed, agreed by the editor 2026-09-26:** score a periodical across its issues, and detect Cyrillic-as-Latin.

---

## 8 · The failure log — what went wrong, and what it taught

Each of these produced plausible text and was invisible downstream. They are the reason the pipeline measures per page instead of choosing a default.

| date | failure | caught by | rule it left |
|---|---|---|---|
| 09-24 | a re-run deleted cited output before rebuilding; one 249-page item lost | noticed 2 min in | a cited text is never replaced in place |
| 09-25 | psm 4 assumed harmful to prose | measurement (194 pages) | read every page both ways |
| 09-25 | hit RATE as tiebreak crowned barely-read pages | *Revuo* p.11 | tiebreak on COUNT |
| 09-25 | tools took «the first image» of a page | *Progreso* 5 p.533 | one image-choice rule, shared |
| 09-25 | mask rows ignored → text read at colour-layer ppi | *Gento Esperanto* 100 vs 300 ppi | stage 3 re-read |
| 09-25 | gate scored psm 6 files, not the accepted mosaic | reading the gate's code | score the combined text |
| 09-25 | library cover sheet scored as the publication | *Progreso* vol. 1 read as Esperanto | cover sheets excluded by wording |
| 09-25 | serial rendering; Tesseract threads oversubscribed | load 218; 1 page/s | parallel files; `OMP_THREAD_LIMIT=1` |
| 09-26 | psm 4 step one file at a time | 53 pages in 10 min | files in parallel |
| 09-26 | glob `page-*.txt` matched readings as pages | reading the code | match base pages exactly |
| 09-26 | image-free pages rendered at the pictures' ppi (43, 9 ppi) | G1 look, *Recenzo* p.9 | image-free pages at 300 |
| 09-26 | born-digital text never consulted | same | text layer as a competing reading |
| 09-26 | G1 counted half-pages as unread | *Progreso* 15/15 «fail» | text lines vs lines of type; triage + human |
| 09-26 | page gate 10 (Catalan-tuned) blocks French names | *Progreso* 5 untouched | gate 0 for French, measured |
| 09-26 | «entries first» let a FOREIGN reading win on line breaking: the text layer won 9,514 pages with fewer recognised words (−395,053 in all; *Esperanto* 1891 no.4 p.2: 912 → 332 words, «entries» 3 → 10) | gate f: recognised words rose LESS with a fifth reading added; orphan numbers 30,362 → 69,947 | **OPEN — editor's word:** entries win only if the reading keeps ≥ X% of the best reading's recognised words |
| 09-26 | the French wrapper read the extracted PICTURE of pages the conversion had rescued by rendering: 0 chars (*Ido-Saluto* 2025 p.23 vs 2,155 chosen) → a no-op merge that marks the page done | checking the run after the laptop slept | the safety net mirrored in EVERY tool that re-reads a page; a second reading under ¼ of the chosen one is not merged |
| 09-26 | G2 never checked its spec: any second language blocked acceptance for ever | gate g3: bilingual G4 fixed 222 corpora, passes did not move | G2 reads `SECOND-MODEL.json` |
| 09-26 | foreign lexicons were STEMS: `journaux`, `jeunes` «not French» | the hat-strip measurement | inflections via each dictionary's own `.aff` |
| 09-26 | the merge stripped supersigns from Esperanto compounds not in the dictionary (`kotizaĵo`, `superŝatigita`) | nine-language gate measurement, «hats removed» column | compound-aware Esperanto test; hat-strip guard |
| 09-26 | the compound test, applied to plain-letter words, passed mangled French (`Congris`, `prosperite`) | scratch re-merge: UEA lost 34 accents | compound test for HATTED words only |
| 09-26 | the hat guard restored supersigns in IDO (`novaĵi`, `voyaĵo`) | same scratch re-merge | guard off for Ido |
| 09-26 | CHAINED merges protected only Esperanto words, so a later language overwrote an earlier one's correct words: Polish over Czech on *Bohema Revuo* (`naši`→`naśi`, `že`→`że`, `této`→`tóto`); G4 93 → 44 | gate i: 27 corpora newly failing G4, 25 of them Bohemian | a token is kept if valid in the primary OR any language already merged on the page; all 3,861 chained pages re-merged from readings on disk (the test issue: G4 back to 93); gate j: Bohemian titles 0 of 112 failing, 2,582 corpora pass G2–G4 |
| 09-26 | every second-model MERGE came out as ONE LINE per page (47,449 of 47,449): `ocr-arbitrate.py`'s `arbitrate()` joins words with spaces — flattening list pages' number-with-name lines and making G1 flag 1,026 pages | G1 on the final texts (1,026 vs 440); blind readers' «whole page came out as one line» | `merge_lines()`: same word choices (28/28 test pages identical), each word back on its base line; all merges redone from readings on disk. RESOLVED the same day: the 09-23/24 `ocr-arbitrate.py` arbitrations were flattened too. They ARE cited — 804 references (person profiles, roster and themes files) — but **every one by PAGE, 0 by line**, 641 with the quoted wording. The editor preferred overwriting if it could be done safely, and then approved it. `tools/ocr-arb-relines.py` took the line breaks from the original page (or the re-read page where the arbitration ran from the PDF: *La Lumo*, *Danlando*) and rewrote **6,582 pages in place, each verified word-identical** (backup `sources/_backup-arb-flattened-20260926-1934.tar.gz`). The 1,576 left on one line are blank or near-blank (1,573 hold ≤ 10 words). Caveat: a quotation crossing a restored break is found by a whitespace-folding search, not by a plain line grep. |
| 09-26 | FILE-NAME COLLISIONS: the tools name output by the PDF's file name alone, so two different PDFs called `39.pdf` (*Posta Mundi* 39 · *Informilo por Interlingvistoj* 39), `42.pdf`, `Epigrami.pdf` shared one output folder — one of each never converted, later steps read the other's images | G1 vision sort: *Informilo* images beside *Posta Mundi* text (the editor judged them clearly different texts and directed that the source be fixed) | unique-name links in `sources/_stem-aliases/`; the six converted afresh; `ocr-run-corpus.sh` now REFUSES a list with duplicate file names (the mixed old output is kept, outside the corpus root, in `sources/_collided-ocr-2026-09-26/`: set aside first INSIDE the root, it was gated as three extra corpora, so nothing set aside may live there) (5 other shared names are the same file twice — harmless) |
| 09-26 | 14 pages LOST after every recipe (rotated tables and adverts, balloons, framed small print, a contents page) | G1 vision sort; the editor's review sheet | the editor RULED each page (an internal record, 2026-09-26, not published): re-read as ruled — rotated, cropped, 400 ppi, best of psm 6/4/3/11 (`ocr-ruled-reread.py` → `.ruled.txt`) — or keyed by hand (`.hand.txt` for a whole page, `.hand-add.txt` for only the lost part, appended). Rank in the rebuild: hand > ruled > every OCR reading and merge. Each re-read was checked against its image (an internal record, 2026-09-26, not published) |
| 09-26 | a page ruled to be rotated 45° read badly at 45°, 90°, and unrotated | the re-read's word counts; the checker MEASURED the text at 58.5° | cropped to the advert, rotated 58.5°: read whole. The tool now crops before it rotates, and its notes say to measure an angle, not estimate it by eye |
| 09-26 | output set aside INSIDE the corpus root (`_collided-*`) was gated as three extra corpora (gate m: 2,897) | diff of gate l against gate m | moved to `sources/_collided-ocr-2026-09-26/`; gate m re-run (2,894). Nothing set aside may live in the root |
| 09-26 | the same book fetched twice: `idohistorio` (Ido-vivo) and `jacob-kontributaji-historio-di-nia-linguo` are byte-identical PDFs, so every hit counted twice | G1 sort items 231/233; `cmp` | the editor ruled that the duplicate be dropped. `idohistorio`'s output moved to `sources/_duplicates-ocr-2026-09-26/` (README); the PDF stays; the kept name is the one the roster audit cites |
| 09-26 | a born-digital page that stores ONE small picture (a logo, a photo) was taken to BE that picture, so G1 measured a logo against a page of text and flagged it | G1 sort items 231, 358; census: 1,424 such pages in ~340 corpora | the TEXTS were unharmed (1,421 of 1,424 carry ≥ 80% of their stored words; the safety net and the text layer caught them). So the fix is in G1 ONLY: a silent page with a text layer of ≥ 20 words is rendered whole (Jacob p.1 no longer flagged; *posta_mundi_48* pp.2, 30 stay flagged — genuinely photo pages) |
| 09-26 | *Tutmonda Espero* 1908 pp.69 and 71 identical | G1 sort items 396/397 | a duplicate scan IN THE ÖNB COPY (mean pixel difference 0.6 against ~20 between any other neighbouring pages); not ours to fix; noted |
| 09-26 | CYRILLIC read with the Esperanto model came out as Latin-letter junk, and no step could see it: the second model is chosen by the gate's language detection, which reads that junk, so Russian was never flagged | the list of G4 failures (Kovno, Bulteno TEKS); a scan for pages recognised under 30% by every list we hold: 1,425 pages in 153 corpora | `ocr-russian-pages.py`: each candidate page is read with the Russian model and ACCEPTED if that reading is ≥ 90% Cyrillic and ≥ 15% of its words are in the Russian list after folding pre-1918 letters (ѣ→е, і→и, ѳ→ф, ѵ→и, final ъ dropped) — the list only DETECTS (probe: Russian 20–38%, non-Russian 6–9%). An accepted page takes the Russian reading WHOLE (no word merge: the post-1918 list misses ~70% of real pre-1918 words). 1,314 accepted in 133 corpora. Blind look, 42 pages: of 30 accepted, 27 better, 3 same, **0 worse**; of 12 rejected, 4 would have gained (mostly Ukrainian — a later `ukr` pass). The gate leaves Cyrillic pages out of G4 (the editor's ruling of 09-23: pre-reform Russian is unscoreable); an all-Cyrillic corpus is reported unscoreable. LIMITATION: the Russian model never writes ѣ or і (ѣ comes out as Ъ/ф/5/%, і as !/1), so pre-1918 pages become readable but a search for a ѣ-word will not find it. NOT COVERED: mixed Esperanto + Russian pages; Georgian, Armenian and Greek. Gate o (after the rebuild): 2,893 corpora · 2,618 pass G2–G4 (gate n 2,612) · G4 fail 257 (282) · 18 unscoreable (all-Cyrillic: Bulteno TEKS, one Kovno) · G2 pending 0, after two Kovno 1912 no. 16 copies, newly flagged Czech once the junk was gone, went through the Czech second model |
| 09-26 | 22 corpora read «G4 0» because NO page reaches the 60 words G4 needs (covers, one-page items, short poems) — *Epigrami* among them, at 92% Ido over the whole corpus | G4 triage of gate o's 257 failures | reported «too short to score» (G4 = −2 internally): neither a failure nor a pass. The triage's other groups: ~100 Russian-era corpora with MIXED pages (their Russian lines still Latin-letter junk), 37 multi-auxlang issues (*Posta Mundi*, *Mondo*), and ~98 near misses and others — see the trial auxlang credit (look: an internal record, 2026-09-26, not published) |
| 09-26 | multi-auxlang issues (*Posta Mundi*, *Mondo*: Esperanto, Ido and Occidental side by side) failed G4 by design, scored against one of the three | G4 triage | AUXLANG CREDIT, adopted: the other two planned languages earn PAGE-LOCAL credit under the same «≥ 10 exclusive word types» rule as French. Measured: G4 failures 235 → 165 (70 corpora, ~43 of them *Posta Mundi*/*Mondo*); median G4 of all other corpora +0. Blind look, 60 pages (an internal record, 2026-09-26, not published): corpora it lets through 95% GOOD+USABLE (17/2/1), passing 100%, still failing 55%. `--no-auxlang-credit` reproduces the earlier gates. The look also exposed faults no step catches, and that the whole-page Russian swap costs the Esperanto parts of MIXED pages |
| 09-27 | the DISK FILLED (Data volume 100%) during the mixed-line pass; the pass died on *Progreso* p.245 | `OSError: No space left on device` | 100 leaked temp folders of page images (7.6 GB; from one-off probes and runs stopped mid-way, which never reach their clean-up — the tools themselves all clean up) removed after checking each held only OCR page images; 46 empty `.rus.txt` written after midnight deleted so they are re-read; pass resumed. The disk as a whole stays near 99% (1.7 of 1.8 TB), not from this work: probes must clean their temp folders by hand |
| 09-27 | the resumed mixed-line pass was KILLED at session rotation (01:05): no summary line, only a leaked-semaphore warning; 152 of 153 corpora done, *Progreso* 2a yaro at 501 of 969 pages | `MIXED.json` count 152, the log | a run launched from a session dies with that session: check for the summary line, not only the file count. Restarted 01:07; done 01:20 (153 corpora, 6,288 pages: 3+ Russian lines 2,055 · 1–2 lines 670 · none 3,061 · not aligned 502). The 7 empty *Progreso* Russian readings are blank pages |
| 09-27 | the LINE-BY-LINE RULE (Russian line taken only if it has MORE recognised Russian words than the Esperanto line has Latin-list words) leaves a quarter to a third of the Russian lines of a Russian page as Latin-letter junk | blind look, 44 pages from 30 corpora (an internal record, 2026-09-27, not published, key beside it): current text better 29 · line-by-line 8 · same 7. Latin lines GOOD 26 line-by-line vs 12 current; Cyrillic lines GOOD **0** line-by-line vs 28 current. By share of Russian lines: under 35% line-by-line 7 · current 2 · same 7; 35–70% current 15 · line-by-line 1; 70% and over current 12 · line-by-line 0 | NOT ADOPTED; `.mixed.txt` stays out of the rebuild. Cause: the Latin score counts 3+-letter hits in seven combined lists (Esperanto, Ido, Occidental, French, German, Polish, Czech), which junk from Cyrillic often hits, against a Russian list that recognises about 1 in 4 pre-1918 words — count against count favours the junk. The Latin choice itself works (Latin GOOD 26 vs 12). Rule change waits for the editor |
| 09-27 | RULE «share» (Russian line if its Russian reading is >= 60% Cyrillic and under half of the Esperanto line's words are in the Latin lists) fixes the Russian lines but takes Russian on Latin-only lines: the Russian model writes Cyrillic for ANY text, so the 60% test does not tell real Russian from Esperanto read as Russian | blind look 2, 44 fresh pages from 32 corpora (an internal record, 2026-09-27, not published, key beside it): line by line better 23 · current 15 · same 6. Cyrillic GOOD 17 line by line vs 11 current; Latin GOOD 8 vs 30. Under 35% Russian lines: line by line 5 · current 11; 35–70%: 13 · 2 (1 same); 70% and over: 5 · 2 (5 same). 10 of the lost pages have NO Cyrillic (poorly read Esperanto and Ido pages, Russian candidates because under 30% recognised) | NOT ADOPTED yet. Measured on both looks: the share of a page's Russian reading in the Russian list is 0.04–0.20 on the 10 pages without Cyrillic (9 under 0.14) and 0.04–0.46 on the 78 with Cyrillic (73 at 0.14 or over) — a page gate at 0.14 is a candidate, tuned on looked-at pages, so it needs a fresh look. Parallel-column pages stay zero-sum at line level (one column lost per line, whichever is chosen) |
| 09-27 | RULE «gated» (page gate: >= 0.14 of the page's Russian reading in the Russian list; then «share» line by line) still loses on nearly all-Russian pages: where the current text is already the whole-page Russian reading, line by line leaves some Russian lines as Latin junk | blind look 3, 44 fresh pages from 32 corpora, none from looks 1–2 (an internal record, 2026-09-27, not published, key beside it): line by line better 19 · current 9 · same 16. Cyrillic GOOD 15 vs 11; Latin GOOD 7 vs 30 (MINOR 28 vs 3). Under 35% Russian lines: 3 · 2 · 11 same (the gate removed look 2's losses on pages with no Russian; the sames are parallel-column trade-offs); **35–70%: 13 · 0 · 3 same** (look 2, same band: 13 · 2); 70% and over: 3 · 7 · 2 same | Candidate: «gated» only on pages with under 70% Russian lines, whole-page Russian kept above. Look 3 below 70%: 16 · 2 · 14 same on 32 pages, which is under the 40-page minimum for a decision, so a look 4 limited to that band is needed. Parallel columns remain the main loss (25 of 44 pages have columns read straight across) |
| 09-27 | RULE «gated» on pages UNDER 70% Russian lines FAILS its pre-set criterion (line by line better on at least twice as many pages as current, AND current better on no more than 5 of 44) | blind look 4, 44 fresh pages from 32 corpora, 22 under 35% + 22 at 35–70%, none from looks 1–3 (an internal record, 2026-09-27, not published, key beside it): line by line 25 · current 13 · same 6. **Under 35%: 8 · 12 · 2 same** (Esperanto-dominant pages, mostly parallel columns: the current text keeps the whole Esperanto column, line by line trades Esperanto lines for part of the Russian). **35–70%: 17 · 1 · 4 same.** Latin GOOD 6 vs 37; Cyrillic GOOD 8 vs 0 (current LOST on all 42 pages with Cyrillic) | NOT ADOPTED. The 35–70% band has now won in three looks: look 2 (rule «share») 13 · 2 · 1 same; looks 3 + 4 (rule «gated», 38 pages) 30 · 1 · 7 same. The band was found in look 3 and confirmed on look 4's 22 fresh pages; the 38 gated pages fall just under the 40-page minimum. Corpus-wide the band is 400 pages in 96 corpora, of which only 13 are whole-page Russian today; the rest carry their Russian as Latin junk. Under 35%: 457 pages; 70% and over: 1,341 |
| 09-27 | COLUMN-FIRST reading (`tools/ocr-layout-mixed.py`: psm 3 blocks, split at image gutters, rule «share» per block) FAILS its pre-set criterion (better on at least twice as many pages as current, AND current better on no more than 5 of 44) | blind look 5, 44 fresh pages from 29 corpora, none from looks 1–4 (an internal record, 2026-09-27, not published, key beside it): column-first 26 · current 14 · same 4. **Cyrillic GOOD 25 vs 12, LOST 4 vs 29**; Latin GOOD 16 vs 24, LOST 4 vs 9. Under 35%: 8 · 5 · 1; 35–70%: 13 · 4 · 1; 70%+: 5 · 5 · 2 | NOT ADOPTED. Two faults of the tool, both fixable: (1) **DUPLICATED TEXT** — psm 3 blocks can overlap and each crop is read whole, so overlapping text is read twice; all 8 pages where the checker saw duplicated blocks (07, 11, 16, 23, 25, 30, 36, 38) were the column-first reading, and 3 of them (23, 30, 38) went to current. (2) **GUTTER MISSED** on four *Espero Kleriga* two-column pages (02, 03, 23, 30): read straight across, Cyrillic LOST, all four to current. Pages 70%+ Russian: the current whole-page Russian text is as good (5 · 5 · 2) |
| 09-27 | DECISION after five failed merge looks and the editor's global review: the bi-script problem is 1,425 pages in 145 items (1.2% of the corpus; seven Russian-Empire journals hold 1,139 of them), and for SEARCH no merge is needed — each reading is right in its own script | global tally over gate p (an internal record, 2026-09-26, not published; the gate's own rule, 2,688 pass reproduced): tier 1 pass with no bi-script page 2,629 items / 107,280 pp; tier 2 pass with bi-script pages 59 / 3,895 (391 bi-script pp); tier 3 fail/unscoreable/short 205 / 3,669 (1,034 bi-script pp, 86 items). Tier 1 by median G4: 90+ 1,004 items / 42,659 pp; 85–90 988 / 41,897; 80–85 317 / 9,597; under 80 320 / 13,127 | (1) MERGED-TEXT WORK STOPPED — no look 6; `.mixed.txt`, `.layout.txt` stay on disk, unused. (2) **BOTH READINGS SEARCHABLE**: `tools/ocr-rus-companion.py` writes the Russian reading of every page past the page gate to `sources/ocr-rendersearch-rus/<item>.txt` (145 items, 2,411 pp; a SIBLING folder so no `*.txt` lister counts it as an item; gitignored like all sources). (3) **RULE: an absence claim on any of the 145 items searches BOTH folders.** (4) Clean single-language texts by filtering each reading's junk: PLANNED, not built — an internal record, 2026-09-27, not published |
| 09-27 | GARBAGE FILTER (`tools/ocr-garbage-filter.py`: each reading of a bi-script page cleaned of the other script's junk by character models) passes one leg of its pre-set criterion and misses the other | blind look, 44 fresh pages from 30 items, none from looks 1–5 (an internal record, 2026-09-27, not published, key beside it): cleaned better 33 · raw 10 · same 1 — **leg 1 met** (33 ≥ 2 × 10), **leg 2 missed** (raw better on 10, limit 5). Russian GOOD 29 vs 11, LOST 2 vs 6; Latin GOOD 11 vs 1, LOST 12 vs 17. By Russian share: under 35% 12 · 3 · 1; 35–70% 12 · 4; 70–90% 9 · 3. The 10 raw wins: Georgian/Armenian pages, junk either way (01, 23); REAL LATIN TEXT DROPPED on Russian-dominant or tabular pages, mainly proper names and non-Esperanto Latin words, which the Esperanto model scores as unlike Esperanto (02, 03, 06, 07, 16, 32, 43); a storyboard page (41) | NOT ADOPTED as canonical. The cleaned files stay on disk beside the raw readings, nothing replaced. The editor decides: keep them as a READING AID only (never canonical, never for absence, never fed to the gate), fix the dropped Latin names and re-look, or park |
| 09-27 | GEORGIAN + ARMENIAN (`tools/ocr-kat-hye.py`: psm 3 blocks, each read with kat / hye / rus / epo+eng, block = Georgian or Armenian if that model's mean confidence >= 40 and 8+ above Russian and Esperanto) FAILS its pre-set criterion (Georgian or Armenian text GOOD or MINOR on >= 80% of pages, AND wrong-language blocks on <= 10% of pages) | look, 44 of the 89 pages with such blocks, all 13 issues (an internal record, 2026-09-27, not published, key beside it): **Georgian GOOD or MINOR 25 of 31 pages with Georgian (81%)**; **Armenian 15 of 37 (41%)** — 22 LOST, 10 of them EMPTY though the page has Armenian; **wrong language on 26 of 44** (19 of them whole lines or blocks: Armenian filed as Georgian junk on 03, 08, 09, 22, 42; Russian in the Georgian file on 15, 21, 43; junk in the Georgian file on 4 pages with no Georgian) | NOT ADOPTED; files on disk, nothing replaced. Causes to work on: (1) the block decision loses Armenian — its confidence runs lower than Georgian's and blocks holding both scripts go to Georgian; (2) psm 3 blocks mix scripts (upper-right blocks, ads with Russian address lines, lesson pages with Esperanto words in the text); (3) systematic Armenian misreadings (italic հ → ճ/ծ, և → ե/ն). Georgian alone is close to usable |
| 09-27 | GARBAGE FILTER WITH FIX (b) (real 4+-letter words in 13 Latin lists kept; capitalised names scoring > 0 keep their own verdict) does NOT improve on the first filter look | second blind look, 44 fresh pages from 36 items, none from any earlier look (an internal record, 2026-09-27, not published, key beside it): cleaned better 29 · raw 13 · same 2 (first look, before the fix: 33 · 10 · 1). Russian GOOD 27 vs 13; Latin GOOD 11 vs 2. Leg 1 met (29 ≥ 26), leg 2 missed (13 > 5). The 13 raw wins: still REAL LATIN TEXT DROPPED — ALL-CAPS names (KOVNO-ESPERANTO, D. BUNČIĆ), initials and abbreviations («A. A.», «(Rusl.)»), and line-initial Esperanto words right after the other column's junk on straight-across lines (smoothing drags them); plus Georgian/Armenian pages and a four-column dictionary | NOT ADOPTED as canonical. Two looks agree: cleaned beats raw about 2.5 to 1, and loses on about a quarter of pages by dropping real Latin-script text. Stopped tuning; the editor decides |
| 09-27 | FILTER FIXES (1)–(3) (ALL-CAPS names by Title-case form; initials before names; strict gate mode) do not change the reading files' balance against raw | third blind look, 44 fresh pages (an internal record, 2026-09-27, not published, key beside it): cleaned 29 · raw 13 · same 2 — identical to look 2. Losses: first words of Esperanto lines where columns touch with no gap, dictionary headwords, some names | Three looks agree (33·10, 29·13, 29·13): the clean files are a READING AID only; tuning STOPPED. The strict gate mode (`eo-gate`) is the scoring input (understates, never flatters) |
| 09-27 | G1 «UNTESTED» (337 pages, 202 corpora) was diagnosed as a missing image and «fixed» by rendering such pages whole — WRONG | G1 run 27b with the fix: untested still 337 | The real cause: `ink_of()` finds no bright PAPER region (dark scans, photographs, white-on-dark covers), so the ink test cannot decide. Patch removed, a true note left in the tool. These pages need the image sort, as on 26 Sep. With them: 15 newly flagged pages not yet sorted |
| 09-27 | THE REBUILD WAS GIVEN A VERDICTS FILE WITHOUT THE ALIAS CORPORA (`OCR-PSM-VERDICTS-2026-09-26E.json` lacks 12 renamed items: Epigrami-ido-vivo, Epigrami-archive-org, ipi-39/42, posta-mundi-39/42, IE-Munde11, grekaidokurso, four web items), so their combined texts were never rewritten and 36 Epigrami vision pages never reached the text | a blind checker reported «raw OCR» on pages that had vision transcriptions; the combined file's date (26 Sep 23:08) predated both of the evening's rebuilds | `OCR-PSM-VERDICTS-2026-09-27-merged.json` = the collisions verdicts + the 83 pages only in 26E (the two agree on all 114,841 shared pages). The 36 verdicts of sort 27c VOIDED (key rows moved to `OCR-G1-SORT-KEY-2026-09-27c-VOID.tsv`, which the ledger does not read), re-checked as 27d (36 NOTHING). LESSON: after a rebuild, check that the files you expect to change did change. |
| 09-28 | THE FORCED RUSSIAN READING WOULD HAVE SWAPPED MIXED PAGES WHOLE. `ocr-russian-pages.py --all-pages` (new) reads every page of named items; 104 of 160 mixed pages passed the whole-page accept rule (≥ 90% Cyrillic, ≥ 15% recognised), because the Russian model turns the page's Esperanto into Cyrillic too — and the rebuild swaps an accepted page WHOLE, losing its Esperanto | the tally «accept 104» on pages the candidate rule had never chosen | Guard added before any rebuild: a forced page the candidate rule would not have chosen is «mixed (forced; never swapped)»; its Russian reading only feeds the segregation tools. LESSON: an accept rule measured on one population (whole-Russian pages) does not transfer to another (mixed pages). |
| 09-28 | A RE-OCR OUTRANKED A BETTER SECOND-MODEL MERGE. The rebuild ranks a re-OCR page above any merge; the Estonian pass merged onto the older reading, so on *Estlanda Esperantisto* 1908.2 the Estonian letters never reached the text | äõöü 0 in 1908.2's combined text after the rebuild, 208 and 395 in its siblings | Per page, the higher-scoring reading kept (merge on pp.1,2,3,6; re-OCR on 4,5,7,8); superseded re-OCR renamed `page-NNNN.reocr.superseded-by-est.txt`, logged in `REOCR.json`. OPEN: `ocr-second-model.py` does not read through the re-OCR route, so a later second-model pass on a re-OCR'd item will hit the same rank. |
| 09-28 | A DECLARED MAIN LANGUAGE CAN LOWER A SCORE. Once the gate honoured declarations, *korokanti* (declared Ido 27 Sep, correctly — an Ido songbook) fell from ADMISSIBLE (72.0, scored as Esperanto with Ido credit) to PRESENCE ONLY (59.4 as Ido) | ledger 28a→28b compared item by item | Its old pass was an artefact of the wrong language; the editor ruled that, for a songbook, presence only is acceptable. LESSON: compare ledgers item by item after any scoring change, not totals only. |
| 09-28 | THE PARALLEL CHECKSUM SWEEP CORRUPTED ITS OWN OUTPUT (`xargs -P 8 md5 -r` into one file interleaved lines: 29 malformed) | the parser failed on unsplittable lines | Redone in Python, one hash per file, written after. |
| 09-28 | A RIGHT NUMBER WAS «CORRECTED». The Estonian list merge gave 359,985; 370,893 was expected, `sort -u` locale collation was blamed, the list was rebuilt with a set union — and gave 359,985 again: hunspell had printed 88,745 lines for 78,368 distinct forms, 531 already listed | the set union's own counts | SOURCE.md states the true counts. LESSON: check the input's distinct count before blaming the tool. |
| 09-28 | CHECKERS APPLIED THE BRIEF UNEVENLY: batches b01–b07 of the masthead pass left misread dates/volume/issue numbers alone as «minor OCR errors»; in the 27e re-sort one checker counted the ÖNB digitiser footer as missing text, two did not | the notes, read across batches | From b08 the brief says dates, years, volume and issue numbers are corrected; the footer ruled not page text (sort 28a, editor 00:06). OWED: the b01–b07 date misreads → the misread-dates queue (an internal record, 2026-09-28, not published). |
| 09-27 | A WORK-LOG ENTRY WAS TIMED AHEAD OF THE CLOCK («23:25» written at 23:23) | the next timestamp call | Corrected to the real times. Rule: times in the work log come from a `date` call, never estimated. |
| 09-28 | the name search fused real compounds at line ends («Dietterle-/statistiko»), never matched hyphenated names' parts, Russian case endings or two-form names: names in the text were reported absent | G5 scoring, then a check of each «missed» name against the text | hyphen joins and parts are tried as candidates, Russian endings stripped, Cyrillic–Latin transliterated (`ocr-name-search.py`) |
| 09-28 | pages whose text is the page read UPSIDE DOWN (reverse-order gibberish; the image is upright). Three of the five kept rotation re-reads, and *Voĉo de Kuracistoj* 1909.8 p.9, which the rotation check never saw | G5, confirmed on the images | extent unknown; a 180° sweep is owed (an internal record, 2026-09-28, not published) |
| 09-28 | G1 «blank» after the ink fix still wrong on 5 of 40 sampled: very faint print (oge.1 p.254), a 90%-lost Ido page, three small losses | G5 | the blank class fails; its remedy is for the editor to rule |
| 09-28 | a G5 scoring rule counted a re-read page as contradicted for being rotated, when that is why it was re-read | the G5 image check | only LOST contradicts a re-read |
| 09-29 | extraction (`pdfimages`) ignored a page's /Rotate: 169 of the 697 flagged pages were extracted, and 53 of those read turned (*Voĉo de Kuracistoj* 1909: every flagged page upside down). The flag is NOT exact alone: a PDF may place the image turned and the flag undo it | G5 (page 321), then a PDF census and a both-ways reading of every extracted flagged page | a flagged page is rendered, never extracted (`ocr-pages.py` `page_rotations`, `ocr_page_images.py`, `ocr-listpage-repass.py`); an existing reading is replaced only where the upright one reads better |
| 09-29 | the rotation check scored Czech pages on the ESPERANTO scale and kept three upside-down re-reads that scored higher as gibberish | G5 image check (074, 084, 105) | a re-read is scored in the page's own language, or on all Latin-script lexicons together; the three reverted |
| 09-29 | the first flip-test rule was fooled: sideways junk broke into 3–4-letter fragments that hit the 18.7M-form all-language lexicon by chance, so 279 of the first 321 pages «read better turned» | two sideways turns of one page (*Bulteno de TEKS*) both scoring 0.7–0.9, which a real page cannot | score on 5+-letter words; a turn counts only as the UNIQUE best; every pass goes to an image look (5 passed; 1 real) |
| 09-29 | a page whose stored image is placed INVERTED inside the PDF with no /Rotate (*Kataluna Esperantisto* 1916 suplemento p.1) is read upside down by extraction; the /Rotate fix cannot see it | the flip test, then the image look | caught only by the flip check; re-read from the rendered page |
| 09-29 | faint pages that the boosted re-read «recovered» (17 → 170 known long words) still lost lines and paragraphs: Tesseract drops text even on a clear rendered page (Progreso 4/5/7, Mondo 1928) | the blind re-sort of the repaired pages (29c: 32 of 61 still LOST) | a re-read is checked by a blind re-sort before it counts; the reliable repair is vision transcription (re-sort 29d: 41 of 41 complete) |
| 09-29 | some losses are in the SOURCE, not the OCR: The Esperantist 1903–04 covers (150 ppi, dark) — no processing recovers the small type | vision at 200 dpi and 3× lightened tiles | recorded as a source-quality loss in the ledger («needs a better scan»), not as an OCR residue |

## 9 · Additions of 27–28 September (stages and rules added after § 1–8 were written)

Each is in its tool's docstring with the editor's words; this is the index.

| stage / rule | tool | what it does |
|---|---|---|
| VISION ADDITIONS (MINOR pages) | `tools/ocr-minor-batch-build.py` → AI vision checkers → `page-NNNN.vision-add.txt` | the lines an image sort judged missing (masthead, title, caption, stamp, misread date line), APPENDED to the chosen reading by `ocr-rebuild-combined.py` (recipe «+vision-add»), never over the editor's hand or hand-add. Record: an internal record, 2026-09-27, not published (verbatim, keys). Scan watermarks stripped from the page files, kept in the record. |
| RE-SORT BY NAMED PAGES | `tools/ocr-g1-sort-build.py --list … --force` (`--g1 -` for a list-only sort) | any pages re-sorted after a change; later sort tags supersede earlier ones in the ledger. |
| RULINGS AS SORT TAGS | an internal record, 2026-09-28, not published (sort 28a) + key | an editor ruling applied to named pages (digitiser footers and facing-page fragments are not page text). |
| DUPLICATES | `OCR-NOT-CORPUS.tsv` § DUPLICATES; evidence `OCR-PDF-DUPLICATES-2026-09-28.tsv` | byte-identical PDFs (md5, 2,905 hashed): one copy kept per group, the more-cited name. |
| DECLARED MAIN LANGUAGE | `tools/ocr-accept.py` + `DECLARED` in `tools/ocr-quality-scan.py` | a declaration now sets the scoring language (it used to set only the Ido → French rule). |
| LISTS BY DECLARATION | `LIST_DECLARED` in `ocr-accept.py` | a roster the shape test reads as prose scored on the list bar. |
| NAMED PRESENCE-ONLY | `PRESENCE_ONLY_NAMED` in `tools/ocr-absence-ledger.py` | items ruled presence only whatever their OCR (dictionaries, the Greek, the Ido songbook). |
| SHORT ITEM CLEARED BY LOOK | `ocr-absence-ledger.py` | a G4 failure of ≤ 4 pages is cleared if every page's latest sort is NOTHING and every note says «well read» (no «mostly», no «garbled»). |
| FORCED RUSSIAN READINGS | `tools/ocr-russian-pages.py --all-pages =a,b` | the Russian reading of every page of named MIXED items; never swapped whole (see failure log 09-28). Then `ocr-layout-mixed.py`, `ocr-garbage-filter.py apply`, `ocr-rus-companion.py` on a linked root holding only those items. |
| CYRILLIC DETECTION | `tools/ocr-cyrillic-detect.py` | every item with Cyrillic read as Latin, by the garbage filter's models; a word is junk only if the Russian-as-Latin model wins by > 0.5/char AND it is in no Latin-script list. |
| ESTONIAN | `ocr-second-model.py --lang est`; `ocr-accept.py --estonian-fold wv` (default) | the Estonian model restores ä õ ö ü; «w» of the old orthography matched as «v» (the text keeps «w»). Lexicon: stems + 78,368 corpus forms accepted by `hunspell -d et` (`tools/lexicons/hunspell/SOURCE.md`). |
| G4 PROFILE | `tools/ocr-g4-profile.py` | for a failing item, what the unknown words are: another language, names, junk, or plain vocabulary gaps. |
| ROTATION FLAG (exact) | `tools/ocr-rotation-flag.py census / measure / apply`; extraction fixed in `ocr-pages.py` (`page_rotations`), `ocr_page_images.py`, `ocr-listpage-repass.py` | a page the PDF turns for display (/Rotate) is RENDERED, never extracted. Readings made before the fix are replaced only where the upright reading is clearly better (53 of 169 extracted flagged pages, 2026-09-29); every moved file backed up in `sources/ocr-work/ocr-rotation-backup-2026-09-29/`. Census and measure: `OCR-ROTATION-FLAG-CENSUS-` / `-MEASURE-2026-09-29.tsv`. |
| TURNED PAGES (heuristic) | `tools/ocr-flip-check.py candidates / test` | pages whose reading hits no lexicon (all lexicons together) read turned 180/90/270; a turn is a repair only where it scores far higher. Never scored in one language (the rotation check's fault on Czech pages). |
| NAME SEARCH | `tools/ocr-name-search.py` | an absence claim is searched this way: line-end hyphens and hyphenated parts tried, column splits, 1–2 letter misreadings, Russian case endings, Cyrillic–Latin transliteration, two-form names (fixed 2026-09-28 after G5). |
| G5 SCORING | `tools/ocr-g5-sample.py score --exclude … --search-all` | pages corrected after judging are not scored; a page is searched in every text a searcher would search; a re-read page is contradicted only if LOST. |
| 09-28 | KNOWN ISSUE — THE CYRILLIC DETECTOR TAKES SOME LATIN-SCRIPT TEXT FOR CYRILLIC JUNK. `tools/ocr-cyrillic-detect.py` calls a word junk if the Russian-read-as-Latin model beats the Esperanto model and the word is in none of our Latin-script lists; words of a Latin-script language WITHOUT a list (Albanian), or badly misread words of a language WITH one (Estonian in old «w» spelling on a poor scan), pass both tests. Found in ledger 28e: *Albana Esperanto-lernolibro* 2004 (Bardhyl Selimi, *Ĉu vi parolas Esperanton?*, Albanian Esperanto Institute, Tirana) and *Estlanda Esperantisto* 1908.6 were flagged and segregated | the presence-only breakdown of 28e: two «bi-script» items with no Russian on them (Russian-only score: none) | HARMLESS so far — their G4 did not move (61.8, 67.1), because the Russian page gate found no Russian and nothing was swapped — but their pages were read with the Russian model for nothing, and a flagged page's Esperanto IS scored on the strict filtered text (`eo-gate`), which can understate. The editor directed that this be documented as a known issue. Mitigation if it matters: a word list for the language (Albanian), or require the Russian reading to pass the page gate before an item counts as bi-script in the ledger. |
| 09-28 | G1 CALLED TEXT PAGES «BLANK». `ink_of()` declared «clean paper» when the paper's mean brightness was under 25 above the in-page Otsu threshold; on grey, speckled JPEG scans Otsu inside the page splits the PAPER's own tones (*La Ondo de Esperanto* 1910.02: t2 = 207, paper 231, diff 23.9) and a page 12% dark with print was «clean paper». G1 examines only pages under 25% of the item's median text; there a «blank» verdict closed the question, listed no exception, and was NEVER AUDITED — every G1 look (26–27 Sep) sampled what G1 flagged or could not decide, never what it cleared | found only by tracing a page the final audit caught (*La Ondo* 1910.02 p.8, a partial loss G1 does not even examine) back to `ink_of` | FIX: clean paper only if under 0.5% of the page is truly dark (below mid-grey and below t1); otherwise the ink is measured at the lower threshold. G1 re-run 28h: of 1,912 «blank» verdicts, 102 were wrong (5.3%) — 69 plates/short pages (no loss), 33 now flagged as unread (image-sorted as 2026-09-28d). G1 now RECORDS its blank pages (`blank_pages`). LESSON (the editor's charge, and right): audit what a check CLEARS, not only what it flags — a 40-page blind look at the «blank» class on day one would have had ~89% chance of exposing this. → proposed G5, the verdict-class audit. |
| 09-28 | G1 DOES NOT EXAMINE PARTIAL LOSS. A page is tested only under 25% of its item's median text; *La Ondo* 1910.02 p.8 carries 44% and lost ~80% of its print. Its line-count yardstick cannot see this on multi-column pages either (one line of type holds several lines of text) | the final audit (name recall 0/7 on that page) | `tools/ocr-coverage-check.py` (new): TEXT PER INK, against the item's own normal pages, on pages at 25–60% of the median (7,352 suspects). OPEN: on grey scans its reference pages fail the ink measure (fixed in `ink_of` above; re-test pending). |
