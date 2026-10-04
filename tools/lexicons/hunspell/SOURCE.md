# Hunspell dictionaries — provenance and licences

Fetched 2026-09-23 16:41 from **wooorm/dictionaries** (`https://github.com/wooorm/dictionaries`),
file `dictionaries/<lang>/index.dic` in each case. Used as **membership word-lists** for the OCR
lexical measure and for the dual-pass per-line arbitration — not as corpora, and never edited.

| file | language | entries | licence |
|---|---|---:|---|
| `fr.dic` | French | 84,278 | **MPL-2.0** |
| `de.dic` | German | 75,888 | GPL-2.0 OR GPL-3.0 |
| `es.dic` | Spanish | 57,345 | GPL-3.0 OR LGPL-3.0 OR MPL-1.1 |
| `cs.dic` | Czech | 260,461 | GPL-2.0 |
| `it.dic` | Italian | 95,438 | GPL-3.0 |
| `sv.dic` | Swedish | 153,717 | LGPL-3.0 |
| `nl.dic` | Dutch | 180,745 | BSD-3-Clause OR CC-BY-3.0 |
| `pl.dic` | Polish | 300,677 | GPL-3.0 OR LGPL-3.0 OR MPL-2.0 |
| `ru.dic` | Russian **(post-1918 only — see below)** | 146,270 | BSD-3-Clause |
| `ca.dic` | **Catalan** | 209,521 | GPL-2.0 or later |

**Bulgarian and Ukrainian added 2026-10-03, same source and same route** (`dictionaries/bg/`, `dictionaries/uk/`: `index.dic`, `index.aff`, `license` → `bg.*`, `uk.*`). Licences from each package.json: **bg (GPL-2.0 OR LGPL-2.1 OR MPL-1.1)**, bgOffice; **uk GPL-3.0**. Word lists `../bulgarian.txt` (866,654 forms) and `../ukrainian.txt` (2,795,695): built by `tools/build-lexicons.py --only bulgarian,ukrainian` (stems + the dictionaries' own affix expansion, `unmunch`; `uk.dic`'s `+xx=` prefixes dropped), gitignored and rebuilt from these files (20:1x; a first stems-only build of 19:2x, 78,005 / 320,312, was replaced). On the authoritative Cyrillic: *Esperanto_Bulgarien* bg 0.69 (ru 0.16); *Ukraina Stelo* 2017 uk 0.90 (ru 0.10); Russian texts stay highest on ru. WHY: the language table (`geniza/ocr/runs/archive/OCR-TEXT-LANGUAGES-2026-10-03.tsv`) found Bulgarian in *Esperanto_Bulgarien* and *Jahrhundert des Esperanto … BULGARIEN* by its letters and had no list to confirm it (the editor asked for one to be scheduled); Ukrainian in *Ukraina Stelo* 2017, *Studia Slavica* 2017 and *ukraina* likewise.

**Catalan added 2026-09-23, same source and same route.** *Tutmonda Espero* (Barcelona, 1908–14, 6 volumes) arrived that night and was expected to be bilingual, with the note that we had no lexicon for its second language — which would have made it the one title the density gate could not measure. The rule in `build-lexicons.py` forbids the obvious shortcut: **a Catalan page scored against Spanish is not a measurement**, and where no clean lexicon exists the scanner must skip and say so rather than score against a near neighbour. So the gap was real, and it was also fifteen minutes' work — 196,984 stems. ⚠ Note the conversion side was never blocked: tesseract has `cat` installed alongside `spa` and `epo`. The gap was in the *measure*, not in the OCR.

**Why these five.** French was the blocker for the *Belga Sonorilo* / *L'Espérantiste* re-OCR.
German, Spanish, Czech and Italian were taken in the same pass on the editor's steer (2026-09-23):
*«not much german or spanish or czech or italian before 1906, though non zero, we will run into
this again»* — the corpus carries Bohemian, Catalan/Spanish, Italian and German organs, and the
next bilingual run should not stall for want of a word list.

## ⚠⚠ PRE-REVOLUTIONARY RUSSIAN IS NOT COVERED, AND MUST BE DECLARED UNSCOREABLE

The editor judged on 2026-09-23 that nothing could be done about pre-revolutionary Russian. **Measured,
and he is right about the off-the-shelf list:** `ru.dic` contains **0** words ending in the hard
sign and **0** words containing ѣ, і, ѳ or ѵ. It encodes the **1918 orthography only**. Scoring
pre-reform Russian against it would mark correct text as garbage — the Ido/Novial failure again,
and the venture's Russian-era material is overwhelmingly pre-1918.

⇒ **Pre-reform Russian is DECLARED UNSCOREABLE** in `tools/ocr-quality-scan.py` (`DECLARED`, which
already carries `historio-ru/`), exactly as Ido and Novial are. Reporting nothing is the correct
answer; a number here would be a lie.

**What could be done later, stated precisely so nobody re-opens it casually.** A pre-reform list is
*partly* derivable from a modern one — final **ъ** after a hard consonant is rule-governed, and
**і** before a vowel nearly so. **ѣ (yat) is not**: its distribution is etymological and purely
lexical — the thing Russian schoolchildren memorised for a century — so no transform generates it.
A genuine pre-reform lexicon would have to come from **born-digital pre-1918 text** (Wikisource
carries pre-reform editions), never from our own OCR of it, per the rule in `build-lexicons.py`.
Worth doing only if a Russian-language corpus ever becomes load-bearing for a pass.

**Format:** one entry per line as `word/FLAGS`; the affix flags after `/` are discarded, so these
are stem lists, not full inflectional expansions. That is the right shape for a MEMBERSHIP test —
which is all the measure needs — but it means inflected forms may miss, so a Hunspell-derived
lexicon scores a few points lower than a corpus-derived one on identical text. **Compare a file
only against its own language's baseline, never across languages.**

⚠ These are third-party freely-licensed data files, kept for reproducibility of the build. They
are not venture sources and carry no copyright restriction of the kind `sources/` does.

## Affix rules (`.aff`) — added 2026-09-26

Fetched 2026-09-26 14:56 from the **same source and route** as the `.dic` files:
`https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/<lang>/index.aff`. Each
file's licence is its `.dic`'s (above).

**Why:** the `.dic` files alone are STEM lists, so `journal` and `jeune` were present but `journaux`
and `jeunes` were not. Every «is this a real word?» test in the OCR pipeline — the second-model
merge, G2's language density and G4's bilingual credit — ran on those stems. `tools/build-lexicons.py`
now expands each list with `unmunch <code>.dic <code>.aff`, keeping LETTER-ONLY forms (Catalan's
clitic and Italian's elision rules otherwise generate tens of millions of hyphen/apostrophe forms: 1.0 GB
for Catalan). Still a clean source: the rules are the dictionary's own. Russian has no `.aff` here
(post-1918 only, and pre-reform Russian is declared unscoreable anyway).

| file | size |
|---|---:|
| `fr.aff` | 199,870 B |
| `de.aff` | 19,199 B |
| `es.aff` | 167,135 B |
| `cs.aff` | 112,714 B |
| `it.aff` | 70,020 B |
| `sv.aff` | 18,581 B |
| `nl.aff` | 46,732 B |
| `pl.aff` | 268,824 B |
| `ca.aff` | 49,922 B |
| `da.aff` | 81,584 B |
| `eo.aff` | 16,322 B |

## Added 2026-09-27 — Estonian, Latvian, Lithuanian, Greek (approved by the editor)

Same source and route (`wooorm/dictionaries`, `dictionaries/<lang>/index.dic` + `index.aff`), fetched 2026-09-27 16:10. For the second languages of *Estlanda Esperantisto* (Estonian), *Latviana* (Latvian), Dambrauskas (Lithuanian) and *Helena Esperantisto* 1947 (Greek), which had no word list and so could never earn the gate's second-language credit.

| file | language | entries | licence (as shipped) | word list |
|---|---|---:|---|---|
| `et.dic` | Estonian | 282,173 | see the package's `license` | **stems only**: 282,148 |
| `lv.dic` | Latvian | 66,606 | LGPL (Latvian spelling library, OpenOffice) | stems + affix expansion: 2,499,847 |
| `lt.dic` | Lithuanian | 85,792 | BSD-style (© Albertas Agejevas and contributors) | **stems only**: 84,789 |
| `el.dic` | Greek | 828,806 | MPL 1.1 / GPL 2.0 / LGPL 2.1 (el_GR 0.9) | stems + affix expansion: 826,887 |

**Why stems only for Estonian and Lithuanian:** affix expansion gave 15.0 M and 36.4 M forms (227 MB, 634 MB), too heavy to load and a false-credit risk. Measured on 31,193 junk tokens (Cyrillic read as Latin): stems match 1.23% (et) and 0.69% (lt); Latvian expanded 1.70%; all under French's 2.40% baseline.

**GREEK WILL NOT HELP, and was built anyway** (the editor asked for it while expecting it not to help). The list is MODERN MONOTONIC; *Helena Esperantisto* 1947 prints polytonic katharevousa, and the Esperanto model reads Greek as Latin junk, which a Greek list cannot match (0.00% junk and 0.00% Esperanto matched). **Greek text is PRESENCE ONLY, like Armenian and Georgian** (editor 2026-09-27).

**GREEK REMOVED 2026-09-27 16:25** (on the editor's decision to remove it): `el.dic`/`el.aff` and `greek.txt` deleted. It matched nothing; Greek text stays PRESENCE ONLY.

## Estonian: forms from our own corpus added (2026-09-28, approved by the editor)

The stems-only Estonian list missed the commonest inflected forms (*peame*, *annab*, *keeles*, *aastal*, *teatab*, *selleks*), so *Estlanda Esperantisto* 1908 failed G4 on its Estonian. Rather than expand all affixes (15.0 M forms), every word of 4+ letters occurring in the combined OCR texts and not already listed (1,745,806 types) was checked with `hunspell -d et -G` against `et.aff`/`et.dic`; the 78,368 distinct forms accepted were added, 531 of them already listed (list 282,148 → 359,985). NOTE: `build-lexicons.py --only estonian` regenerates the STEMS only — re-run this hunspell step after it. Measured on the garbage-filter held-out sets (per word, 4+ letters): Cyrillic-read-as-Latin junk 0.65% → 1.33% (0.86% not also Esperanto); real Esperanto 4.52% → 11.01%, only 1.41% not also Esperanto — both under French (0.79% / 2.35% not-Esperanto). The stems-only list is kept beside it as `tools/lexicons/estonian-stems-2026-09-27.txt`.

## Russian: `ru.aff` fetched, and a corpus-forms list for SCORING (2026-09-28, on the editor's decision to take on pre-revolutionary Russian)

`russian_post1918.txt` is STEMS ONLY (146,229): *был*, *была*, *были*, *книги*, *языка* are all absent — which, far more than orthography or the OCR model, is why real pre-1918 Russian scored only 20–38%. `ru.aff` was not on disk; fetched 2026-09-28 10:17 from `https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/ru/index.aff` (same source as `ru.dic`; hunspell needs `-i UTF-8` here). Every Cyrillic word of 3+ letters in our Russian readings (`page-*.rus.txt`, `ocr-rendersearch-rus/`, the `orus` trial; 525,852 types) was FOLDED to modern spelling (ѣ→е, і→и, ѳ→ф, ѵ→и, final ъ dropped; endings -аго/-яго/-ыя/-ия also tried as -ого/-его/-ые/-ие) and checked with `hunspell -d ru -i UTF-8 -G`: 47,936 accepted → `tools/lexicons/russian_forms_corpus.txt`.
Measured (per page, share of Cyrillic words recognised, fold + endings): real pre-1918 Russian (40 accepted Russian pages) stems 27.6 → stems+forms 57.4 median (p10 51.3, min 43.0; `orus` reading 61.6); junk — Esperanto read by the Russian model (333 samples, `jcyr` held-out) — 7.0 → 11.5 median (p90 16.0, max 26.3). **USE: scoring only (the Russian-only score).** The detection and gating tools (`ocr-russian-pages.py`, `ocr-layout-mixed.py`) keep the stems list, because their thresholds (0.15, 0.14) were measured on it. `ru.aff`/`ru.dic` are git-ignored (refetchable); the forms list is KEPT in the repo, like `russian_post1918.txt` — rebuild by the recipe above when the Russian readings change.
