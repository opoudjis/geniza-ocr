# Searching the corpus for people: two ways, and the one we use

This document describes how *The Geniza of Esperanto* searches its OCR'd corpus for people, and the tools that do it (release v1.2). The rules for matching a name, which tolerate the errors OCR makes, are in `METHOD.md`, section 6, and in `tools/ocr-name-search.py`.

## Two ways to search

**1. A roster against a run: the way this project searches.** Every name on a roster (in this project, a list of about a thousand early Esperantists) is looked for in the items of one journal run, or any chosen set of items. This is how our searches have always been run: a source is taken, and everyone on the roster is looked for in it.

    tools/ocr-dowse.py --roster <roster file> --items "LEsperantiste.1907.*" --write <record.md>

The roster file has one person per line, their forms separated by « | » («Eroŝenko | Eroshenko | Ерошенко»). The record opens with one row per person (hits by kind of match, items hit, items silent), then gives every place of every hit, item and page: a run is small enough to read.

**2. One name against the whole corpus.** One person, in all their forms, looked for in every item. It answers a different question («which of our texts name this person?») and is kept for searches of that kind and for other users.

    tools/ocr-dowse.py "<form>" "<form>" … --write <record.md>

Both ways search every item in scope, with no cap: a capped search never supports a claim that a name is absent.

## How it works

- **Each text is indexed once** (`tools/ocr_index.py`): every word form with the pages it is on, the parts of hyphenated words, adjacent pairs of words, and line-end fragments with the words after them. Every name is then matched against the index, not against the running text. A whole roster costs little more than one name.
- **The index follows the name search's own rules.** It gives exactly the hits `tools/ocr-name-search.py` gives, page by page. This was checked (`tools/ocr-index-check.py`) on 5,176 comparisons of a name against a text, Latin and Cyrillic, with no disagreement.
- **Each text is searched as its class requires.** An item searched for absence across every reading is searched in a text holding every reading of every page; texts in another alphabet are always searched as well.

## Reading the results: tiers of precision

OCR text is imperfect, so a search must tolerate errors to find a name at all: a name read as «Mĉray» or «ARINGHIEN» is still the name. But every step of tolerance that finds more of the name also finds more words that are not the name. There is no setting that finds all of one and none of the other. So the search reports its hits in **tiers**, from the most precise to the least, and the reader decides how far down to go.

The tiers, from the most precise to the least. The examples are real: they come from searches of this corpus.

### 1. Exact

The word on the page is the name, once two kinds of difference are ignored: capitals and accents. Ignoring capitals matters because names are often printed in capitals in headings, lists and signatures: «KABE» is Kabe, «WARINGHIEN» is Waringhien. Ignoring accents matters because printers and OCR both lose them: «Meray» and «MERAY» are Méray (of the 765 exact hits for Méray, only 233 keep the accent). The same step treats the pre-reform Russian letters as their modern ones («Постниковъ» = «Постников»), and digits that OCR reads for letters as those letters («Ka8E» = «KaBE», with 8 for B). This tier is almost always the name itself. When it is not, it is because the name is also an ordinary word: the German «Bein» («leg»), the English «cart». The record lists the exact hits by their spelling as printed («Kabe» 3,702, «KABE» 2,372, «kabe» 2), so the reader can see whether lowercase hits, the likeliest to be the ordinary word, need setting aside (`--exclude-as-read`).

### 2. Near

The word differs from the name by one letter (for names of up to six letters) or two (for longer names): a letter misread, dropped or added. This is the commonest OCR damage, and the tier finds most of it: «Waringien» (h dropped), «ARINGHIEN» (the first letter lost), «Warienghien» (a letter added), «Hodier» (l read as i), and «G.Waringhien», where OCR lost the space between the initial and the name: once the full stop is dropped, «gwaringhien» is one letter from the name. For Cyrillic names it also finds the Russian case endings, which change the end of a name in every sentence: «Постникова», «Постникову», «Постниковымъ» are all Postnikov. The price is that a short name is one letter away from many ordinary words: for «Kabe» this tier also finds «habe» (German «have»), «kae», «kaze», «kase», «abe». For a long name, few real words are within two letters, so the tier is nearly all genuine.

### 3. Confusion

The word is the name as OCR was *measured* to misspell it. A survey of 27,308 pages whose true text is known (`docs/OCR-ACCENT-SURVEY-2026-10-05.md`) showed that OCR does not simply drop accents: it often writes a different letter, or two letters for one. The commonest: «ü» read as «ii» (half the time in modern print), so «Müller» comes out «Miiller»; «é» read as «ĉ» (a third of the time in old print, by the Esperanto model), so «Méray» comes out «Mĉray»; «ř» read as «f», so «Přibram» comes out «Pfibram»; in Russian, «ѣ» read as «ъ», so «Бѣлый» comes out «Бълый». Most of these are one-letter changes that the near tier already finds; this tier adds the ones that cost two (like «ü» as «ii»), which would otherwise lose a short name. It allows nothing else on top: a spelling it makes from a confusion must then match exactly or nearly. It is rare, and when it hits it is usually right.

### 4. Translit

A Latin-letter name is compared with words in Cyrillic, spelled out in Latin letters, and a Cyrillic name with words in Latin letters. This finds a Russian name printed in a Russian text when the searcher gave it in Latin letters: «Lebedev» finds «Лебедевъ», «Ĉirikov» finds «Чириковъ». To allow for the many ways of transliterating, it tolerates one letter more than the near tier. That makes it the floodiest tier: for «Méray» it finds the Russian «мира» («world», «of peace») over a thousand times, and for «Kabe» it finds «какъ» («how»), «Кап», «кие» tens of thousands of times. It is best avoided by giving the Cyrillic form of a Russian name yourself, so that it is found in the exact and near tiers instead.

### 5. Small caps and run-ins: small capitals, and a name run into the next word

Two particular kinds of damage, each with its own rule.

- *Small capitals.* Many journals set names in small capitals (capital letters the height of lower-case ones), and OCR reads them badly: it confuses r with n and w, g with c, and d with p. So «BRÉON» comes out «Bnéow», «HAUGG» comes out «Haucc», «H. HODLER» comes out «H. Hopren». These are too far from the name for the near tier, so for names of five letters or more the search compares again, with those letters treated as the same.
- *A name run into the next word.* When OCR loses the space after a name, the name and the next short word come out as one: «Asnes de» as «asnesde», «Moĵaev de» as «mojaevde». The search finds the name at the start of such a word when what follows is a short function word (de, la, kaj, en, und, et …).

Both rules are needed, and both let in other words that happen to fit the pattern: for «Waringhien» this tier finds mostly the German «Kaninchen» («rabbit»); for «Kabe», «dabei» («thereby») and «fabela».

### 6. Join

The name is found across two or more pieces that OCR split apart. A word broken by a hyphen at the end of a line comes out in two halves («Za-» and «menhof»): the search joins them. In pages with two columns, OCR sometimes interleaves the lines of the columns, so the two halves of a broken name end up far apart («Apple-» … «baum»): the search joins a line-end fragment with each of the next 40 words. It also tries each part of a hyphenated name on its own («Grosjean-Maupin» finds «Maupin»), and two neighbouring words joined. Joins find names that would otherwise be lost entirely, but joining two short words often makes something name-like by chance, and many join hits merely repeat a place already found (the initial and the name, «G. Waringhien», tried joined as «G.Waringhien», are the same place as the exact hit «Waringhien»). Read this tier for its new places only.

## When to stop

### It depends on the name

A long, unusual name can go far down the tiers before it meets other words; a short name meets them at once. Three names searched over the whole corpus show the difference. For each tier, the table gives the pages it adds that the stronger tiers had not already found, and what brings them; «common words» are forms found more than 200 times in the corpus, which are other words, not the name.

| tier | **Kabe** (4 letters) | **Waringhien** (10 letters) | **Zinoviev** (8 letters; 8 spellings searched, Latin and Cyrillic) |
|---|---|---|---|
| exact | 1,796 pages | 698 pages | 287 pages |
| near | **5,645 new pages** (three times the exact), 70% only through common words: «habe» (German), «kae», «kaze», «kase», «abe» | 20 new pages (3% more), all the name: «ARINGHIEN», «Waringien», «Warienghien» | 126 new pages (44% more), none through common words: «Zinov'ev» (another transliteration), «Zimoviev» (m for n), «Зиновьева» (a Russian ending, or his wife «Zinovjeva»); but also «Зиновьевск», a town named after another Zinoviev (see below) |
| translit | 8,575 new pages, mostly fragments of Cyrillic words: «какъ», «Кап», «кие» | — | **10,440 new pages**, 73% only through common words: «denove» (Esperanto «again») 15,374 times, «nove», «новые» |
| small caps and run-ins | 649 new pages, about half through common words: «dabei» (German), «fabela» | 16 new pages, most of them «Kaninchen» (German «rabbit») | — |
| join | 7,256 new pages; a fifth through common words, most of the rest rare fragments | 38 new pages (5% more), mostly the name run into its neighbour | 11,149 new pages, nearly all chance fragments |

For **Kabe**, the near tier would more than triple the result, and most of what it adds is other words: the search should stop after the exact tier. For **Waringhien**, the near and join tiers add a few per cent more pages, and what they add is the name, misread or run together: those tiers are worth reading. **Zinoviev** sits between: the near tier is worth reading (it adds 44%, all of it rare forms of the name), but the translit and join tiers flood, and the search should stop before them.

### Example: one person, many spellings

Aleksej Zinoviev, an early Esperantist of Poltava, is printed under at least eight spellings, depending on the language of the source: «Zinovjev» in the Esperanto press, «Zinoviev» in English, «Zinovieff» in French records, «Zinovyev», «Zinowiew» (Polish), «Sinowjew» (German), «Зиновьев», and «Зиновьевъ» in the pre-reform Russian spelling. Most sources use only one of them: of the 164 items that name him in the exact and near tiers, 52 print only «Zinoviev», 44 only «Zinovjev», 7 only a Cyrillic form. Some spellings are reached from another through the near tier («Zinovjev» and «Zinoviev» differ by one letter), but not all: «Sinowjew» is three letters from «Zinovjev», too far for the near tier, and a Cyrillic form is reached from a Latin one only through the translit tier, where it drowns among «denove». **So give every spelling you know, Cyrillic included, as a form of the same person**: each is then searched in its own right and found in the precise tiers.

### The rule we use, tier by tier

A working rule, not a measured one:

1. **Always take the exact tier**, and check it on the page image: every OCR page up to 40, beyond that a blind sample of 40 (born-digital pages need no check).
2. **For each weaker tier, look at two things:** how many new pages it adds compared with the pages already found, and which forms bring them, with their counts in the corpus (the record gives them, from a lexicon of every word form in the corpus, `tools/ocr-corpus-lexicon.py`).
3. **Keep reading a tier while it adds few pages** (a few per cent of what you have) **and the forms that bring them look like the name**: misreadings, the name run into a neighbour, the name in small capitals.
4. **Stop at the first tier that would multiply the result**, where the new pages outnumber the pages already found, **and whose forms are words of the corpus's languages** (common in the corpus, and recognisably German, Esperanto, Russian … rather than a damaged form of the name).
5. **Even in a tier you stop at, look at the rare forms**: a form found only a few times in the whole corpus, that looks like the name, is a real candidate. The record lists where each rare form is.
6. **Set noise aside explicitly** (`--exclude «habe,Kaninchen»`, or, for a spelling exactly as printed such as lowercase «kabe», `--exclude-as-read`), and record why. The record can be rebuilt from the saved hits in seconds (`--from-hits`).

Being rare in the corpus is not enough on its own: for Kabe, most of the rare forms in the translit and join tiers are junk fragments of Cyrillic, not misreadings of the name. The judgement «this looks like the name» is the reader's, and it is why a hit on an OCR page is a candidate until it is read on the page image; born-digital pages need no check, and a frequent name is checked by a blind sample of 40 pages per tier.

### Do not walk down the tiers until something turns up

The weaker tiers are for widening what a stronger tier has already found: more pages for a name a stronger tier finds, through its misreadings. They are not a ladder to keep climbing down until a person appears. In an item where a name has no exact hit, a first hit in a weaker tier calls for care, and the further down it is, the more care. The weaker the tier, the more of its hits are other words, and where no genuine hit is hidden among them, only the false hits remain. So:

- a first hit in the **near** or **confusion** tier is a candidate, to be read on the page image like any other;
- a first hit in the **translit** tier means one of two things. If its hits are in an alphabet the name was given no form in (a name given in Latin letters only, found only in Cyrillic, or the reverse), the search was **underspecified**: give the form in that alphabet, search again, and read the result tier by tier as usual. If the name was given in both alphabets and an item still finds it only by transliteration, the hit is almost certainly another word, since both spellings were already searched. But counterexamples are conceivable, so it is not presumed to be noise: confirm on the page image that it is noise before setting it aside;
- a first hit in the **small caps and run-ins** tier or the **join** tier, four or more tiers below exact, is presumed to be noise, and how far to trust it depends on the order of magnitude. Read the hits per item, tier by tier. Scores such as **0 · 0 · 0 · 1**, a single small-caps, run-in or join hit after nothing, are worth considering: read it on the page image, especially if its form looks like the name, such as a name split at a line end («Was- … niewski») or set in small capitals. **0 · 0 · 0 · 0 · 200**, hundreds of hits after nothing, may hold a correct hit or two. But that is unlikely enough, against the manual checking that hundreds of page images would take, that by default it is not pursued further.

In *Ruslanda Esperantisto* 1907, Laurén has no exact hit and 2 near hits. Both near hits are «Auren», Cyrillic misread as Latin, which on the page is «Ангелъ», the title of a poem by Lermontov. Laurén also has 266 join hits. Taking the first tier with a hit on the way down would find him in all nine issues; in fact so weak an attestation is no evidence that he is in any issue. An item where a person's only hits are in the small caps and run-ins tier or the join tier counts, for that person, as an item with no hit, unless one of them is confirmed on the page image.

As a rule of thumb, a surname of five letters or fewer usually stops at the exact tier, with its rare near forms checked one by one; a long and unusual surname can usually be read through the near and join tiers.

## Same surname, different people

The search finds a name, not a person, and in the early Esperanto press several people often carry the same name: brothers, father and son, husband and wife, or strangers. This section is how we tell them apart. The examples are from a search of *L'Espérantiste* (1898–1914, 172 issues) for Joseph and Léopold Jamin, and for Ludwik and Leon Zamenhof.

### Beware of namesakes

The first case of a shared name was in fact what set this project going. We used Aleksej Zinoviev, a pioneering Esperantist of Poltava, as the example above («One person, many spellings»). Grigory Zinoviev (born Radomyslsky), of the Communist International, took the same noble family name as a pseudonym; and since Aleksej did not stay in the movement, within twenty years he had been forgotten, and the early mentions of the Esperantist Zinoviev came to be taken as Grigory's. The same confusion arises from words made from his name. In two issues of the Soviet Esperanto press of 1930 and 1931, the hits for «Зиновьев» are the town of «Зиновьевск» (named after Grigory Zinoviev, with Esperanto schools in it) and «Зиновьевцам» (to the «Zinovievites», his followers): none of them is Aleksej. Only reading the page tells them apart.

Namesakes also turn up where nobody expects them. Searching *L'Espérantiste* for the Belgian Esperantist Joseph Jamin also found Paul Jamin of Dijon, Henri Jamin of Lyon, the boulevard Jamin in Reims, the French writer Jules Janin and, through the near tier, the word «jasmin». Each is a true hit of the search, and none is the person searched for.

### First: who carries the name?

Before searching, find out which people with the surname are already known, and what is known about each — including what a title could tell them apart by: sex («S-ro», «S-ino», «F-ino»; «M.», «Mme», «Mlle»), rank («Sergent», «Lieutenant»), profession («D-ro», «architecte»). In *L'Espérantiste* there are two brothers Jamin: **Joseph**, an architect in Brussels, first president of the first Belgian Esperanto group (March 1898); and **Léopold**, a sergeant, later a second lieutenant at Antwerp. And the early press prints many Zamenhofs: **Ludwik**, the author of the language; his brothers **Feliks**, **Leon**, **Aleksander** and **Henryk**, the last three doctors like him; his wife **Klara**; and his children **Adam**, **Zofia** and **Lidja**, of whom Adam and Zofia later became doctors too. Give each person their own line in the roster, with their first names and initials, in both alphabets and in the languages the press used, after « || first: »:

    Jamin | Жаменъ | Жамен || first: Joseph, Jos., J., Jozefo, Józef, Жозефъ, Ж. || titles: S-ro, M., Monsieur, Sinjoro
    Jamin | Жаменъ | Жамен || first: Léopold, Leopold, Leopoldo, L., Леопольдъ, Л. || titles: S-ro, M., Monsieur, Sinjoro, Sergent, Lieutenant, Sous-lieutenant

The record labels them «Jamin (Joseph)» and «Jamin (Léopold)». After « || titles: » go the titles each can carry: a title just before the name keeps only the people who can carry it («Sergent Jamin» is Léopold; «S-ino Zamenhof» is Klara), and a plural («MM.», «S-oj», «fratoj») gives the hit to all who can carry its singular. The OCR's fragments of a title («S°», «Sr»» for a superscript S-ro) are not read as titles, so they never overrule a first name. Initials cannot be searched for (a word of two letters or fewer matches only exactly), but they can sort what the surname search found.

### Second: sorting the hits by first name and initial

For every hit of the shared surname, the record reads the words beside it: before it («Joseph Jamin», «L. L. Zamenhof»), or after it when nothing comes before («Jamin, Jos.», «Заменгофъ Л. Л.»). Each hit is sorted as:

- **assigned**: a first name, initial or title that only one of them has («J. Jamin» is Joseph; «L. L. Zamenhof» is Ludwik; «S-ino Zamenhof» is Klara);
- **all**: a plural title («MM. Jamin», «S-oj Jamin», «la fratoj Zamenhof»): the hit is everyone's who can carry its singular;
- **ambiguous**: an initial or title they share: «L. Zamenhof» may be Ludwik or Leon, and only «L. L.» tells them apart;
- **titled**: a real title that none of the known people carries («F-ino Zamenhof», with no Miss Zamenhof known): it goes to the residue, never to a default;
- **unlisted**: another word stands before the surname: another first name («Aleksandro Zamenhof», another brother: there were several, Felix too), or another name in a list («Fruictier, Jamin»);
- **bare**: no first name («D-ro Zamenhof», «M. JAMIN»).

Some rules, learnt from the OCR:

- **Titles decide by context.** A title tells apart only the people our knowledge of them allows it to tell apart. «D-ro Zamenhof» does not tell Ludwik from Leon, Aleksander or Henryk, since all were doctors; but «F-ino L. Zamenhof» is a Miss, so Lidja, not either of them, and «Sergent Jamin» is Léopold, not Joseph the architect. So the attributes a title can decide on (sex, rank, profession) belong in what is established about each person first (above). OCR misreads titles too: the French «Dr» comes out as «D'», «D°», «Dre», and these are not read as initials.
- **Abbreviations count** when they begin a first name: «Jos.» is Joseph, «Leop.» is Léopold, and so is «Lĉop.», with é read as ĉ.
- **Titles set with superscript letters** are often invisible to OCR. In a list of puzzle solvers, «S‘i Jamin» is in fact an S with a superscript «oj», «S-oj Jamin»: both brothers, sending a joint solution.
- **Line ends leave junk**: «Jos, LIN Jamin» is «Jos. Jamin», with «LIN» the OCR's junk at the end of a line.

In *L'Espérantiste* this sorting, before titles were added, gave about 160 hits of «Jamin» to one brother or the other. It left 115 hits, on 60 pages, undecided. Weak-tier hits that nobody can claim are not counted among them: they are presumed noise, as any weak first hit is.

### Third: reading in context

An undecided hit is read with its context (some forty words either side) and compared with what is known of each person: trade, town, address, office, date. Of the 115 hits of «Jamin»:

| verdict | hits | on what |
|---|---:|---|
| Joseph | 57 | his name or address («M. JAMIN, architecte, 69, rue des Drapiers»); for 37, an office the context shows and that the profile gives only to Joseph — a weaker ground, and recorded as such |
| Léopold | 10 | «Léop. Jamin», his rank («sous-lieutenant … à Anvers»), the Antwerp group |
| both | 3 | «MM. Joseph et Léopold Jamin», the plural «MM. Jamin» |
| not Jamin | 37 | other words and other people: the namesakes above |
| cannot tell | 8 | the residue (below) |

We keep attribution **by name** apart from attribution **by office**: the second depends on what is already believed about the person, and so can be wrong along with that belief.

### When the bare name is the custom: a default, kept apart

With Zamenhof the problem is different. In *L'Espérantiste* only 51 hits carry a distinguishing first name or initial, and titles decide 62 more, all of them his wife Klara's («S-ino Zamenhof», «Mme Zamenhof»), against 6,854 bare («le docteur Zamenhof») and 1,873 with the shared «L.». Reading each in context is not possible. But the bare name was not really ambiguous to a reader of the time: «D-ro Zamenhof» is Ludwik, because that is what everyone then understood.

For such a case we use a **default**: the bare hits, and those with an initial the default person shares, are attributed to Ludwik. But a default is a risk, so it is kept **apart**:

- its hits are never mixed with those assigned by first name: Ludwik is present by first name or title in 10 issues, and **by default** in 153 more;
- it is checked by a blind sample of 40 pages; a page that turns out to be someone else's is given to them;
- it never makes the others silent: Leon is present by first name in 4 issues, and in the 162 where a bare «Zamenhof» stands, he is neither found nor not found; Klara, by her titles, in 7;
- and it is only as safe as the titles that keep other people's hits out of it: before Klara had a roster line of her own, the default had also given Ludwik 49 hits with a woman's title before the name.

A suspicion is not a default. With Jamin, the bare name is most likely Joseph; but nothing in the texts says so beyond doubt, so no default was set.

### The residue, and when it stays

What is left after the sorting, the context and the default is the **residue**: hits that an expert has to judge. With Jamin, 8 hits on 5 pages. Two were decided by careful reading, by a human eye (the puzzle lists above). Three pages were ruled **ambiguous**: the speakers at the 1906 Geneva congress («Kolonelo Ayza, por la Hispanoj; Jamin, por la Belgoj»), the report of its last day («c'est M. Jamin qui raconte les séances du dernier jour»), and the 1907 speeches at a school for the blind («MM. Blanjean et Jamin»). The text says nothing more about these: the decision, if one can be made, will come from another source, such as the minutes of the Geneva congress. Such a page is an ambiguous datum, not a fault of the search.

In the end, Joseph Jamin is present in 53 issues of *L'Espérantiste*, Léopold in 29 (two of them by his rank alone: «le lieutenant Jamin»), and three pages stay ambiguous.

### Recording the decisions: the judgement file

Each person's decisions are written in a judgement file, one line per person, which the record reads (`--judgements <file>`), and the record is rebuilt from the saved hits in seconds (`--from-hits <record>.hits.tsv`), without a new search:

    Jamin (Joseph) | assign: LEsperantiste.1901.3 p.14 | not: LEsperantiste.1900.11 p.11 | ambiguous: LEsperantiste.1906.8-9 p.15 | why: …
    Zamenhof (Ludwik) | default: yes | why: «D-ro Zamenhof» is Ludwik in the press of the time

- `assign`: pages of the shared surname given to this person by contextual reading or by checking;
- `not`: pages where the surname is shown not to be this person (another word, a namesake: 1900.11 p.11 is «jasmin en allemand»);
- `ambiguous`: pages ruled undecidable from the text (the record marks them «ruled ambiguous», not «awaiting»);
- `default: yes`: this person takes the bare and shared-initial hits, kept apart;
- `why`: the reasons, which the record prints.

The same file records, for any person, where the reading stopped (`stop: <tier>`), the forms set aside for that person only (`exclude`, `exclude-as-read`), and the pages read on the image (`confirmed`). The record's «Shared surname» section lists the residue with its context, and every sorted hit is in its `.surnames.tsv`.

### What it means for a silence

Two rules are added to «What a silence means» below:

- **An item where the surname is found only in the residue is, for none of the people who share it, evidence of absence**: it is neither a find nor a silence until it is decided.
- **A default never makes a silence**: that the bare «Zamenhof» is given to Ludwik does not show that Leon is not there.

Expect, then, that the best-known names, those the press printed without a first name, will have the largest residue, and the fewest silences for their relatives.

## What a silence means

An item in which a name was not found is evidence that the name is not printed there only if the item is searchable for absence (see the classes in `METHOD.md`, section 5), and only within its conditions: not on pages it excludes, and on one side only where it says so. Even then a silence is evidence, not proof: on blind samples the search found about 19 in 20 printed names in the main class, and about 99 in 100 in the two classes searched with extra care. For people who share a surname, see «Same surname, different people» above: an item where the surname is only in the residue claims nothing, and a default never makes a silence.

## How long it takes

On one machine (Apple M5 Pro, 18 cores, 64 GB), with 8 processes:

| search | text searched | time |
|---|---|---:|
| 986 names against one journal-year (*L'Espérantiste* 1907) | 11 issues, 262 pages, 291,835 words | about 8½ minutes |
| one name against the whole corpus | 2,871 items, about 58 million words (one reading per page); a search reads about 110 million, since it reads several readings of the same pages | about 4 minutes for «Kabe» (one run timed on the index; before the index, text by text, 6 to 20 minutes) |
| the corpus lexicon, built once | the search texts (85 million words, several readings per page), 3.7 million distinct forms | under a minute |

A name given in two alphabets, or a short name, takes longer: it has more spellings to compare, and matching across alphabets considers far more of the corpus's words.

## Themes

For a theme rather than a person, `--stem` matches word stems (a stem matches any word it begins, after folding), with no tolerance of misread letters, since theme words are short and a tolerant search of them floods. The measured recall is for personal names only; nothing was measured for theme words, and the ways of wording a theme in common nouns and verbs can never be exhausted, so no list of stems is complete. **A theme search therefore supports presence only:** a theme's silence is not evidence.
