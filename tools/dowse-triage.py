#!/usr/bin/env python3
"""The dowse triage: every text of the corpus given a proposed priority, so a second account's three months go to what
matters (the editor, 2026-10-20).

    tools/dowse-triage.py [--out FILE.md]

Counts words per text as tools/corpus-word-counts.py does (geniza/sources/ocr-preferred/*.txt and born-digital-text/*.txt,
grouped by OCR-ITEM-TABLE.tsv's title_key), but per ITEM with the item's year, so a run can fall in two tiers (Lingvo
Internacia to 1905 is a first journal, 1906–1914 the crisis). The first matching rule of RULES gives the tier and the
reason; titles with identical word totals are flagged as likely doubles (a second copy of one text). Writes the review
document (default geniza/ocr/method/DOWSE-TRIAGE-<today>.md, create-only) and a TSV beside it, one row per title and
tier. Proposals only: the editor rules. Reads only the corpus. Ezri, 2026-10-20."""
import ast, csv, datetime, glob, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
WEEK = 4_000_000   # tokens one Max account dowses a week (2026-10-18: Amerika Esperantisto, 1.84M tokens = 45% of a week)

TIERS = [
    ("0", "done", "already dowsed"),
    ("1", "first journals", "the founding era: Esperanto periodicals to 1905, the first congress"),
    ("2", "crisis core", "the international organs of both camps during the crisis, 1906–1914, where the Delegation, Ido and the purges were fought out"),
    ("3", "major secondary", "the histories, encyclopaedias, letters and works the venture leans on"),
    ("2b", "crisis, national organs", "the national and specialist organs of the crisis years, 1906–1914 (the editor, 2026-10-20)"),
    ("4", "other primary to 1914", "periodicals of 1906–1914 outside the core, single primary texts (books, pamphlets) to 1914, and Volapük"),
    ("5", "after 1914", "periodicals after 1914 (Ido, Occidental, the Soviet and later Esperanto press)"),
    ("6", "other secondary", "the rest of the secondary literature"),
    ("F", "forewords only", "dictionaries and word lists: dowse the foreword and front matter, skip the body (the editor, 2026-10-20)"),
    ("S", "skip", "bibliographies and catalogues: added mechanically, and redundant (the editor, 2026-10-20)"),
    ("L", "low by the editor", "named by the editor as no priority"),
    ("?", "undated or unregistered", "no year in the item table, or a text the table does not know"),
]
TNAME = {t: n for t, n, _ in TIERS}

# (tier, pattern on «title_key | title» lower-cased, (first year, last year) or None, reason). First match wins. Title keys
# run words together («amerikaesperantisto», «larevuo»): patterns allow an optional space and are never anchored.
RULES = [
    # Antaŭen Esperantistoj (Lima), cupelled in cupel17 as ANNO_e7a (no item-table row yet, so its code): «L» on
    # 2026-10-20 («cannot be a priority»), tier 4 on 2026-10-23, the whole run
    ("4", r"anta[uŭ]en.?esperantist|^\[not in the item table\] anno_e7a_|^anno_e7a_", None,
     "the Peru journal: the editor, 2026-10-23, (2026-10-20: «cannot be a priority», L)"),
    ("0", r"amerika ?esperantisto", None, "dowsed 2026-10 (dowse/amerika-esperantisto)"),
    ("0", r"ruslanda ?esperantisto", None, "dowsed 2026-10 (dowse/ruslanda-esperantisto)"),
    ("0", r"korzhenkov-historio\b|li-kaj-ni\b|\bmanders\b|waringhien-lingvo-kaj-vivo|jossinet-1998|komen\w* d[ae] neves|szerdahelyi-krestomatio",
     None, "dowsed 2026-10 (dowse/<source>)"),
    # the dowses of 2026-10-21 and 2026-10-22 (tags 2026-10-21, 2026-10-22), by the years each read
    ("0", r"\bla esperantisto\b", (1889, 1895), "dowsed 2026-10-21 (dowse/la-esperantisto)"),
    ("0", r"\blalumo\b", None, "dowsed 2026-10-21 (dowse/la-lumo)"),
    ("0", r"^kk\b", None, "dowsed 2026-10-21 (dowse/kongresa-gazeto: 1908, 1911, 1912, 1913, 1914)"),
    ("0", r"zakrzewski - historio de esperanto|zakrzewski-historja", None, "dowsed 2026-10-21 (dowse/zakrzewski-historio-1913, dowse/zakrzewski-historja-1906)"),
    ("0", r"lingvo ?internacia", (1895, 1905), "dowsed 2026-10-22 (dowse/lingvo-internacia, Picard)"),
    ("0", r"the ?esperantist\b", (1903, 1905), "dowsed 2026-10-22 (dowse/the-esperantist: both volumes, 1903–1905; the theesperantist-pg issues are copies of it)"),
    ("0", r"la ?suno ?hispana|espero.pacifista|juna.?esperantisto", None, "dowsed 2026-10-22 (dowse/la-suno-hispana, dowse/espero-pacifista, dowse/juna-esperantisto: whole runs)"),
    ("0", r"esperantoruslando", None, "dowsed 2026-10-22 (dowse/esperanto-ruslando)"),
    ("0", r"kongresa.libro", (1905, 1905), "dowsed 2026-10-22 (dowse/kongresa-libro-1905)"),
    # cupel17's periodicals (signed 2026-10-23; the editor), by their ÖNB codes until the item table has
    # their titles, and by title after; before the Volapük rule, which would take «Rund um die Welt» for the Volapük one of
    # 1888–1892
    ("4", r"(anno_e0d_|cirka[uŭ]i? la mondo|rund.um.die.welt.*(19(09|1\d)))", (1909, 1914),
     "Ĉirkaŭ la mondo / Rund um die Welt (Schramm), a German magazine for Esperantists, not Volapük (the editor, 2026-10-23)"),
    ("4", r"anno_e1w_|scienca ?gazeto", None, "Scienca Gazeto, a specialist organ, as Internacia Scienca Revuo (the editor, 2026-10-23)"),
    ("1", r"anno_e1v_|rondiranto", (1887, 1905), "Rondiranto (Plovdiv), a first journal, its run to 1904 (the editor, 2026-10-23)"),
    ("4", r"anno_e0h_|la ?dek.?sepa", None, "La Deksepa (H. de Coppet), a French local monthly (the editor, 2026-10-23)"),
    ("2b", r"anno_e5e_|portugala ?revuo", (1906, 1914), "Portugala Revuo, a national organ of the crisis years (the editor, 2026-10-23)"),
    ("4", r"anno_e6g_|lingua ?internationale", None, "Lingua Internationale, in Latino sine flexione and French (the editor, 2026-10-23)"),
    ("4", r"onb_e1n_|vespera ?horo", None, "Vespera Horo, 1910 (the editor, 2026-10-23)"),
    # bibliographies skipped, dictionaries for their forewords (an article ABOUT one is neither)
    ("S", r"^(?!.*(wikipedia|rimarkoj)).*(bibliogra|katalog|catalog|^bpeape\b)", None,
     "a bibliography or catalogue: the editor, 2026-10-20,"),
    ("F", r"^(?!.*wikipedia).*(vortar|vocabul|dictionn|w(ö|oe)rterb|dictionar|lexik|lexicon|oficiala_aldono)", None,
     "a dictionary or word list: the editor, 2026-10-20,"),
    ("4", r"volap|rund.um.die.welt|nunel|nunal\.nulik|\bvp_|vpik|volaspodel", None, "Volapük: the editor, 2026-10-20,"),
    # the Volapük periodicals of the later cupels, whose keys the rule above misses (2026-10-24; the editor):
    # Volapükabled (ANNO e2s), Kosmopolan, Cogabled, Mulapenad nebolitik, Vpaflen jveizik, Vpaklubs, Nuns blefik;
    # Schleyer's Sionsharfe (1878–1880, where Volapük first appeared); Volkswohl's «Weltsprachliches» (Passau, 1897–1899,
    # the organ of the «Weltbund»: Volapük 296 times, Schleyer 41, Esperanto none in its two files)
    ("4", r"anno_e2s|kosmopolan|cogabled|mulapenad|vpaflen|vpaklubs|nuns.blefik|sionsharfe|volkswohl", None,
     "Volapük: the editor, 2026-10-20, (these titles 2026-10-24)"),
    # the congress books, records, lists and handbooks of 1905–1914 (the editor: the 3rd–5th UK books and the Bern 1913
    # Oficiala Dokumentaro approved; the rest of their kind with them); the spiritists' subcongress stays a specialist text
    ("2", r"^(?!.*subkongreso).*(universala kongreso|kongreso de universala esperanto-asocio|kongreso de esperantistoj"
          r"|kongreso universala|internacia kongreso barcelono|jubilea.?universala.?kongreso|jubileauniversalakongreso"
          r"|jubileakongreso|eco-raporto-unua-kongreso)", (1905, 1914),
     "a congress book, record, list or handbook, 1905–1914 (the editor, 2026-10-20: the congress books approved, with the gazettes in tier 2)"),
    ("2b", r"historio.?kaj.?teorio.?de.?ido", None, "an Ido primary text of the crisis (the editor, 2026-10-20)"),
    ("3", r"clark-1907-international-language", None, "an early history of Esperanto (the editor, 2026-10-20)"),
    ("5", r"^progreso|bulteno", (1915, 2100), "a periodical after 1914 (Progreso's later volumes, the Soviet bulletins)"),
    ("4", r"\bla ?revuo\b|literatura\.aldono", (1906, 2100),
     "literary: the editor, 2026-10-20,; dowsed as belles lettres: "
     "kept in scope only where it relates directly to Esperanto (parody, polemic, hagiography in; else front matter only)"),
    ("4", r"internacia ?scienca ?revuo", None, "the editor, 2026-10-20; 1904 too (2026-10-27: tier 4)"),
    # one year of 1905 read with the run it opens (the editor, 2026-10-23
    #): each to the tier of its 1906–1914 years
    ("2", r"esperanto[- ]\(?uea", (1905, 1905), "1905 with its 1906–1914 run (the editor, 2026-10-23)"),
    ("2b", r"brita ?esperantisto|british esperantist|tra ?la ?mondo", (1905, 1905), "1905 with its 1906–1914 run (the editor, 2026-10-23)"),
    # the first journals: to 1905
    ("1", r"\bla esperantisto\b", (1889, 1895), "the first Esperanto periodical (Nürnberg, 1889–1895)"),
    # its own rule, so the note on what anno_e4a is stays on its row (2026-10-20: one reason for all, it stood on every
    # first journal's row)
    ("1", r"anno_e4a", (1887, 1905), "a first journal, its years to 1905 (anno_e4a = Espero Katolika, Peltier, from 1903)"),
    ("1", r"lingvo ?internacia|l.esp[ée]rantiste|the ?esperantist\b|belga ?sonorilo|bohema ?esperantisto|la ?suno ?hispana"
          r"|\blalumo\b|juna.?esperantisto|tra ?la ?mondo|espero.pacifista|esperanto[- ]\(?uea|brita ?esperantisto|british esperantist",
     (1887, 1905), "a first journal, its years to 1905"),
    # the crisis, 1906–1914, both camps: the international organs (2), then the national and specialist ones (2b)
    ("2b", r"catholique", (1906, 1914), "a national or specialist organ of the crisis years"),
    ("2", r"lingvo ?internacia|l.esp[ée]rantiste|esperanto[- ]\(?uea|oficiala ?gazeto|\boge\b|\bprogreso|belga ?sonorilo|^mondo\b",
     (1906, 1914), "an international organ of the crisis, 1906–1914 (Progreso, Mondo and the Ido-era Belga Sonorilo for the Ido side)"),
    ("2", r"kongresa (libro|gazeto)|\bkk\b|oficialajarlibro|ondo ?de ?esperanto", (1906, 1914),
     "the editor, 2026-10-20"),
    ("2b", r"brita ?esperantisto|british esperantist|germana ?esperantisto|belga ?esperantisto|pola ?esperantisto"
           r"|bohema revuo|ĉasopis|espero \(st petersburg\)|tutmonda ?espero"
           r"|juna.?esperantisto|tra ?la ?mondo|internacia ?socia ?revuo|espero.pacifista", (1906, 1914),
     "a national or specialist organ of the crisis years"),
    # the major secondary sources
    ("3", r"enciklopedio.de.esperanto|the-esperanto-movement|garv[ií]a|privat-(historio|vivo)|zakrzewski|oralibro"
          r"|leteroj-de-zamenhof|originala-verkaro|drezen|histoire.?de.?la.?lang|couturat.?leau|encycl|blanke|gordin"
          r"|esperanto-en-perspektivo|sikosek|\blins\b|^bk[- ]", None,
     "a major secondary source (history, encyclopaedia, letters, collected works)"),
]

# Notes the counts cannot show, printed under the summary of every run (kept here so a re-run keeps them).
NOTES = [
    "**Not counted, not yet cupelled:** the big haul of missing ÖNB titles (*Antaŭen Esperantistoj*, the Peru journal, "
    "among them: tier L by the editor's word, «cannot be a priority»), and Temerov's Volapük batch (cupel16). They take "
    "their tiers by the same rules when they enter the item table; a re-run of the tool writes a new dated triage.",
    "**The largest double is in the core:** *La Belga Sonorilo* is on disk twice, as volumes (`belgasonorilo`) and as issues "
    "(`labelgasonorilo`): about 2.6M tokens of tier 2 for one run. **Both are read, every copy, not triangulated** (the editor, "
    "2026-10-20 18:4x: no copies of La Belga Sonorilo deleted by heuristic, some but not all: all "
    "issues of the journal are kind 1; Miles's name test, `ocr/runs/NAME-TESTS-2026-10-20-RESULT.md`: the issue run holds "
    "315 pages the volumes lack, the volumes 163 the run lacks, and on 698 of the 1,333 shared pages a name is caught in one "
    "reading and garbled in the other); one work in `COPIES`, its facts merged at the harvest, no page skipped.",
    "**The week is one measure:** 4M tokens a week of a Max account comes from one source (Amerika Esperantisto, "
    "2026-10-18). Clean modern text will go faster, poor OCR and Fraktur slower; the first week on the second account is "
    "the real measure.",
    "**The rules are in `tools/dowse-triage.py` (RULES):** a title in the wrong tier is moved by a pattern there and a "
    "re-run, so a ruling survives the next triage. Rulings so far (the editor, 2026-10-20): the Peru journal low; Volapük "
    "tier 4; tier 2 split, its national and specialist organs (2b) after the major secondary sources; Internacia Scienca "
    "Revuo, La Revuo and the Lingvo Internacia literary supplement tier 4; the congress books and gazettes, the Oficiala "
    "Jarlibro and La Ondo de Esperanto up from 2b to 2; the congress books and records of 1905–1914 to 2; Historio kaj "
    "teorio de Ido to 2b; Clark's International Language (1907) to 3; dictionaries forewords only (F), bibliographies and catalogues skipped (S); La Revuo and the "
    "literary supplement dowsed as belles lettres, only what relates directly to Esperanto.",
    "**Built 2026-10-20 (the dowse runbook, D0 point 6):** the page scope, `dowse/‹source›/scope.tsv` by "
    "`tools/dowse-page-scope.py`: the forewords of tier F as one source (`dowse/vortaroj-antauparoloj/`), La Revuo's belles "
    "lettres out (0.66M of its 2.48M tokens), the Lingvo Internacia literary supplement read for its front matter and contents only. "
    "The tokens here are each title's whole text; the scope reads less of these three.",
    "**«Tokens», not words** (Miles and Ezri, 2026-10-20, the editor wanting one name for each figure): this list counts every "
    "whitespace token of `ocr-preferred/` and `born-digital-text/`, everything a reader is given (78.1M); Miles's «words on "
    "signed pages» (69.4M) counts only tokens with a letter, on the signed lines' scoped pages and the signed born-digital lists. "
    "The week's 4M is in tokens too (Amerika Esperantisto's 1.84M by the same count).",
]

def tier_of(key, title, year, kind, run):
    hay = f"{key} | {title}".lower()
    for t, pat, span, why in RULES:
        if re.search(pat, hay) and (span is None or (year and span[0] <= year <= span[1])):
            return t, why
    if not year:
        return "?", "no year"
    if run and year > 1914:
        return "5", "a periodical after 1914"
    if run and 1906 <= year <= 1914:
        return "4", "a periodical of the crisis years outside the core"
    if run and year <= 1905:
        return "1", "a periodical to 1905"
    if kind == "SECONDARY" or year > 1914:
        return "6", "a single text, not among the major works"
    return "4", "a single primary text (a book or pamphlet) to 1914"

def main():
    csv.field_size_limit(sys.maxsize)
    rows = {}
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            rows[r["item"]] = r
    agg = defaultdict(lambda: {"w": 0, "n": 0, "ys": set(), "why": "", "title": "", "kind": ""})
    per_title = defaultdict(int)
    texts = []   # (words, key, title, year, kind)
    for sub in ("ocr-preferred", "born-digital-text"):
        for f in glob.glob(os.path.join(G, "sources", sub, "*.txt")):
            n = len(open(f, encoding="utf-8", errors="replace").read().split())
            it = os.path.basename(f)[:-4]; r = rows.get(it)
            if not r:   # a text the table does not know: its file name as key, a year from the name if it has one
                y = re.search(r"(1[89]\d\d|20[0-2]\d)", it)
                texts.append((n, "[not in the item table] " + it, it, int(y.group(1)) if y else None, "", it)); continue
            key = (r.get("title_key") or "").strip() or it
            y = re.search(r"(1[6-9]\d\d|20\d\d)", r.get("year") or r.get("written") or "")
            texts.append((n, key, (r.get("title") or "").strip(), int(y.group(1)) if y else None, (r.get("kind") or "").strip(), it))
    # TIER 0 FROM THE DOWSED LIST (2026-10-24; the editor
    #): an item in dowse/DOWSED-ITEMS-LATEST.tsv (tools/dowse-done.py, rewritten at every harvest) is done, by its
    # source; the hand rules of tier 0 above stay for what the list does not hold
    done = {}
    dp = os.path.join(G, "dowse", "DOWSED-ITEMS-LATEST.tsv")
    if os.path.exists(dp):
        for r in csv.DictReader((l for l in open(dp, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            done[r["item"]] = f"dowsed {r['readers_tag'] or '(an older dowse)'} (dowse/{r['source']}; DOWSED-ITEMS-LATEST.tsv)"
    nitems = defaultdict(int)
    for n, key, title, year, kind, it in texts: nitems[key] += 1
    for n, key, title, year, kind, it in texts:
        t, why = ("0", done[it]) if it in done else tier_of(key, title, year, kind, nitems[key] > 1)
        a = agg[(t, key)]
        a["w"] += n; a["n"] += 1; a["why"] = why; a["title"] = title or key; a["kind"] = kind
        if year: a["ys"].add(year)
        per_title[key] += n
    # likely doubles: two titles with the same word total (a second copy)
    by_total = defaultdict(list)
    for k, w in per_title.items():
        if w >= 5000: by_total[w].append(k)
    doubles = {k for ks in by_total.values() if len(ks) > 1 for k in ks}
    doubles |= {"belgasonorilo", "labelgasonorilo"} & set(per_title)   # the volumes and the issues of one run, both on disk
    # and every title with an item in COPIES (2026-10-20: The Esperantist's 26 Gutenberg issues and the scan, paired in
    # COPIES since 2026-10-10, showed one «double?» in 27, by an accident of totals); read as data, never imported
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr-dowse.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "COPIES" for t in node.targets):
            for e in ast.literal_eval(node.value):
                for c in e["copies"]:
                    r = rows.get(c[0])
                    doubles.add(((r.get("title_key") or "").strip() or c[0]) if r else c[0])
    today = datetime.date.today().isoformat()
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(G, "ocr", "method", f"DOWSE-TRIAGE-{today}.md")
    tot = defaultdict(lambda: [0, 0, 0])
    for (t, k), a in agg.items():
        tot[t][0] += a["w"]; tot[t][1] += a["n"]; tot[t][2] += 1
    allw = sum(v[0] for v in tot.values())
    L = [f"# The dowse triage, proposed ({today})", "",
         f"`[tools/dowse-triage.py: every text of the corpus by its title and year, the first matching rule giving the tier; "
         f"proposals for the editor to rule. {allw:,} tokens (every whitespace token a reader is given; not Miles's «words on signed pages»). "
         f"Weeks = tokens ÷ {WEEK:,}, one Max account's week of dowsing "
         f"(2026-10-18: Amerika Esperantisto's 1.84M tokens were 45% of a week). «double?» = another title has the same token "
         f"total, or a known second copy: a pair for the doubles method (`ocr/method/DOWSE-DOUBLES-METHOD-PROPOSAL-2026-10-20.md`, "
         f"`COPIES` in `tools/ocr-dowse.py`): both read where both are kept, never dropped on this list's word.]`", "",
         "| tier | name | what | titles | items | tokens | weeks | cumulative weeks |", "|---|---|---|---|---|---|---|---|"]
    cum = 0
    for t, name, what in TIERS:
        if t not in tot: continue
        w, n, k = tot[t]; cum += w if t not in ("0", "L", "?", "F", "S") else 0
        L.append(f"| {t} | {name} | {what} | {k:,} | {n:,} | {w:,} | {w / WEEK:.1f} | {cum / WEEK:.1f} |")
    L += ["", "Cumulative weeks count tiers 1–6 in order, leaving out done, forewords-only, skip, low and undated/unregistered "
          "(a foreword is a few pages: tier F's token total is the whole book, not what is dowsed).", ""]
    L += [f"- {x}" for x in NOTES] + [""]
    with open(out.replace(".md", ".tsv"), "x", encoding="utf-8") as tf:
        tf.write("tier\ttier_name\ttitle_key\ttitle\tkind\titems\ttokens\tfirst_year\tlast_year\tdouble\treason\n")
        for t, name, what in TIERS:
            items = sorted(((k, a) for (tt, k), a in agg.items() if tt == t), key=lambda x: -x[1]["w"])
            if not items: continue
            L += [f"## Tier {t} — {name} ({tot[t][0]:,} tokens, {tot[t][2]:,} titles)", "", f"*{what}.*", "",
                  "| title | kind | items | tokens | years | double? | why this tier |", "|---|---|---|---|---|---|---|"]
            for k, a in items:
                ys = a["ys"]; span = f"{min(ys)}–{max(ys)}" if ys else "?"
                dbl = "double?" if k in doubles else ""
                shown = a["title"] if a["title"] == k else f"{a['title']} (`{k}`)"
                L.append(f"| {shown.replace('|', '/')} | {a['kind']} | {a['n']} | {a['w']:,} | {span} | {dbl} | {a['why']} |")
                tf.write(f"{t}\t{name}\t{k}\t{a['title']}\t{a['kind']}\t{a['n']}\t{a['w']}\t{min(ys) if ys else ''}\t{max(ys) if ys else ''}\t{dbl}\t{a['why']}\n")
            L.append("")
    with open(out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {out} and its .tsv: {allw:,} tokens")
    for t, name, _ in TIERS:
        if t in tot: print(f"  {t} {name}: {tot[t][0]:,} tokens, {tot[t][2]:,} titles, {tot[t][0] / WEEK:.1f} weeks")

if __name__ == "__main__":
    main()
