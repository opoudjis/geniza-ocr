#!/usr/bin/env python3
"""The accuracy check's preparation, so that its reader reads passages, not the whole source (the editor, 2026-10-14:
, after the Manders check read the whole book, 130,326 tokens for 40 lines).

    tools/dowse-accuracy-prep.py <source> [--n 40] [--konkludita 10] [--seed N] [--date YYYY-MM-DD] [--window 120] [--redowsed TAG | --from-returns TAG]

(--konkludita K: up to K more lines whose date the assembler inferred from the issue, ⟦la dato de la numero,
konkludita⟧, numbered after the sample and each put to the reader under the brief's date rule 6; 2026-10-24.)

From profiles/by-source/<source>-dowse.md it draws a seeded random sample and, for each line, checks mechanically:
  A  the anchor is found on its page (the harvest's quotation finder, tools/fact-ids.py);
  C  the person's NAME or a roster form stands within the passage;
  D  a dated line's year stands within the passage; an undated line whose passage names a year is flagged.
It writes, refusing to overwrite:
  geniza/dowse/<source>/accuracy-sample-<date>.md     the lines, numbered, each with its mechanical notes;
  geniza/sources/ocr-work/accuracy-excerpts/<source>-<date>.md   the passage around each anchor (±window words on
      its page): copyright text, so under sources/, which is not tracked.
The reader then judges B (the fact as the source says it) and E (the kind) for every line, and C and D only where the
notes flag them. Ezri, 2026-10-14."""
import argparse, datetime, importlib.util, os, random, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FL   # a line's own fields, the source's words left out (2026-10-28)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
YEAR = re.compile(r"(?<!\d)(1[6-9]\d\d|20\d\d)(?!\d)")   # «1907b», a cited work's year, counts (2026-10-14)
PAGECAP = 2000  # words of a whole page given when the anchor is on none of the line's pages (600 until 2026-11-04: a
                # Belga page is about 950 words, and two anchors past word 600 were judged «not on the page»)

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", file))
    m = importlib.util.module_from_spec(spec); sys.argv, saved = ["x"], sys.argv
    spec.loader.exec_module(m); sys.argv = saved
    return m

def is_unpaged(item):
    """A born-digital text without «=== page N ===», which item_pages reads by paragraphs (2026-11-01)."""
    if os.path.exists(os.path.join(G, "sources", "ocr-preferred", item + ".txt")): return False
    b = os.path.join(G, "sources", "born-digital-text", item + ".txt")
    return os.path.exists(b) and not re.search(r"^=== page \d+ ===", open(b, encoding="utf-8").read(), re.M)

def numbered_pages(item):
    """A paragraph-numbered copy (sources/ocr-work/<item>.numbered.txt, «=== ¶ N ===»), which the harvest takes as its
    item: its ¶ as pages (2026-11-07, Privat's Vivo: item_pages knows no «.numbered», and none of the 40 anchors was found)."""
    p = os.path.join(G, "sources", "ocr-work", item + ".txt")
    if not item.endswith(".numbered") or not os.path.exists(p): return None
    parts = re.split(r"^=== ¶ (\d+) ===\s*$", open(p, encoding="utf-8").read(), flags=re.M)
    return {int(parts[i]): parts[i + 1].split() for i in range(1, len(parts), 2)}

def roster_forms(path):
    """Roster label (a profile stem) -> its search forms, lower-cased and normalised by the caller."""
    out = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        forms = [f.strip() for f in l.split("||")[0].split(" | ") if f.strip()]
        if forms: out[forms[0]] = forms
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("source")
    ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--date", default=datetime.date.today().isoformat()); ap.add_argument("--window", type=int, default=120)
    ap.add_argument("--roster", default=None, help="the full roster (default: the newest dowse/ROSTER-FULL-CROSS-ARC-*.txt)")
    ap.add_argument("--outdir", default=None, help="write both files here instead (a test of the tool itself)")
    ap.add_argument("--facts", default=None, help="draw from this facts file instead (a test against an earlier version)")
    ap.add_argument("--konkludita", type=int, default=10, help="up to K more lines whose date was inferred from the issue (default 10)")
    ap.add_argument("--redowsed", default=None, metavar="TAG", help="draw only from the lines on the pages this tag redowsed (R6)")
    ap.add_argument("--from-returns", default=None, metavar="TAG", help="draw only from the lines this tag's returns wrote (R6 of an extracts run)")
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else int(a.date.replace("-", ""))
    sample_p = os.path.join(a.outdir or os.path.join(G, "dowse", a.source), f"accuracy-sample-{a.date}.md")
    exc_dir = a.outdir or os.path.join(G, "sources", "ocr-work", "accuracy-excerpts"); os.makedirs(exc_dir, exist_ok=True)
    exc_p = os.path.join(exc_dir, f"{a.source}-{a.date}.md")
    for p in (sample_p, exc_p):
        if os.path.exists(p): sys.exit(f"refusing: {p} exists")
    hf = load("hf", "harvest-facts.py"); fid = hf._fid()
    import glob
    roster = a.roster or sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")))[-1]
    forms = roster_forms(roster)
    facts = a.facts or os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md")
    L = [l.rstrip("\n") for l in open(facts, encoding="utf-8") if l.startswith("- $$$")]
    # --redowsed TAG (2026-10-26, the selective redowse's R6: «step 11: the accuracy sample drawn from the new lines»):
    # the population is the lines citing a page the tag redowsed («redowsed_pages» in the source's facts-config)
    if a.redowsed:
        import json
        cfg = json.load(open(os.path.join(G, "dowse", a.source, "facts-config.json"), encoding="utf-8"))
        rp = {(hf.item_key(e["item"]), int(p)) for e in cfg.get("redowsed_pages", []) if e.get("tag") == a.redowsed for p in e["pages"]}
        L = [l for l in L if {(hf.item_key(m.group(1).strip()), int(m.group(2)))
                              for m in re.finditer(r"(?:^|; | · )([^·;]+?), PDF (\d+)\b", l)} & rp]
        if not L: sys.exit(f"refusing: no line of {a.source} cites a page redowsed by {a.redowsed}")
    # --from-returns TAG (2026-11-03; the editor, on Rondiranto's sample): the population is the lines
    # the tag's returns wrote, for a run that redowsed no whole page (the extracts run of redowse-pages.py prep
    # --other-readings writes no «redowsed_pages»); a line is the return's by its NAME, its kind and its fact, which the
    # assembler copies unchanged (the date, the anchor's «» and the locator it rewrites)
    if a.from_returns:
        import glob
        def key(l):
            f = l.split(" · ")
            m = re.match(r"^- \$\$\$ (.+?) \$\$\$", l)
            return (m.group(1), f[1].strip(), f[2].strip()) if m and len(f) > 2 else None
        rf = [f for f in glob.glob(os.path.join(G, "dowse", a.source, f"facts-return-{a.from_returns}-*.md"))
              if not re.search(r"-p\d+\.md$", f)]
        mine = {key(l) for f in rf for l in open(f, encoding="utf-8") if l.startswith("- $$$")} - {None}
        L = [l for l in L if key(l) in mine]
        print(f"{len(rf)} returns of {a.from_returns}: {len(mine)} lines; {len(L)} of them in the facts file")
        if not L: sys.exit(f"refusing: no line of {a.source} is one {a.from_returns}'s returns wrote")
    pick =sorted(random.Random(seed).sample(range(len(L)), min(a.n, len(L))))
    # THE «KONKLUDITA» LINES (2026-10-24; the editor, on the dates the tool infers from the issue
    #): up to --konkludita more lines, seeded, of
    # those whose date the assembler inferred from the issue (⟦la dato de la numero, konkludita⟧), each put to the reader
    kon = [i for i, l in enumerate(L) if "konkludita⟧" in l and i not in set(pick)]
    extra = sorted(random.Random(seed + 1).sample(kon, min(a.konkludita, len(kon))))
    cache, sample, excerpts, flags = {}, [], [], defaultdict(int)
    for k, n in enumerate(pick + extra, 1):
        line = L[n]; l3, kind = hf.take_kind(line); rec, err = hf.parse(hf.to2(l3))
        notes = []
        if err:
            sample.append(f"{k}. (linio {n+1}) {line}\n   - maŝine: la linio ne legeblas ({err[:60]})"); continue
        who, date, fact, src = rec[0], rec[1], rec[2], rec[3]
        # Every locator of the line, not only the first (2026-10-14, the Neves check: an anchor quoted from the Esperanto
        # edition was sought only in the Ido one, and the top of that page, another text, was given as the passage).
        segs = hf.segments(fact, last=True); words = max(segs, key=len) if segs else []
        # normalised as the harvest does, the whole then split (2026-11-04, Belga 1906–1914's lines 26 and 35): word by
        # word, «›» and «:» became empty words that no page holds, and «La 29an › Fino Guilliaume» was never found
        nw = fid.norm(" ".join(words)).split()
        locs = []
        for m in hf.locators(src):
            item = m.group("item").strip(); page = int(m.group("pdf") or m.group("para"))
            if item not in cache: cache[item] = hf.item_pages(item, fid) or numbered_pages(item)
            pages = cache[item] or {}
            hit = fid.find(pages, page, nw) if pages and nw else None
            # A BORN-DIGITAL TEXT WITHOUT PAGES, CITED «PDF N, l. K» (2026-11-01, the Russian Adresaro's check: read as
            # paragraphs, «PDF 1» was its heading, and all 40 passages were «=== section 1 … ===» alone): the anchor
            # sought in the whole text read as one page, so that its window holds the neighbouring entries and the heading
            if not hit and pages and nw and is_unpaged(item):
                if (item, "whole") not in cache: cache[(item, "whole")] = {1: [w for q in sorted(pages) for w in pages[q]]}
                whole = cache[(item, "whole")]; hit = fid.find(whole, 1, nw)
                if hit: pages, page = whole, 1
            locs.append((item, page, pages, hit))
        found = [x for x in locs if x[3]]
        cuts = []   # (item, page, how, words)
        if found:
            item, _, pages, hit = found[0]; p, i = hit[0], hit[1]; toks = pages[p]
            cuts.append((item, p, "la ankro", toks[max(0, i - a.window): i + len(words) + a.window]))
            rel = i / max(1, len(toks))
            # the other editions only where the line is about the copies' differences: elsewhere they repeat the same
            # passage and double the checker's reading (the test of 2026-10-14: 50k → 94k characters for Neves)
            others = [x for x in locs if x is not found[0]] if "diferenco inter la kopioj" in FL.ours(line) else []   # audit 36
            for it2, pg2, pages2, hit2 in others:
                if hit2:
                    q, j = hit2[0], hit2[1]; t2 = pages2[q]
                    cuts.append((it2, q, "la ankro", t2[max(0, j - a.window): j + len(words) + a.window]))
                else:   # the other edition: the same place on its page, by proportion (2026-10-14: the copies' differences)
                    t2 = pages2.get(pg2, []); c = int(rel * len(t2))
                    cuts.append((it2, pg2, "la sama loko laŭ proporcio, ne la ankro", t2[max(0, c - a.window - len(words)): c + a.window + len(words)]))
            notes.append(f"A ✓ (la ankro en {item}, {'PDF' if 'PDF' in src else '¶'} {p})")
        else:
            for it2, pg2, pages2, _ in locs:
                cuts.append((it2, pg2, "la ankro ne trovita; la paĝo", pages2.get(pg2, [])[:PAGECAP]))
            notes.append("A ✗ la ankro ne trovita: kontrolu"); flags["A"] += 1
        passage = " ".join(" ".join(c[3]) for c in cuts); np = " " + fid.norm(passage) + " "
        stem = hf.slug(re.sub(r" \(.*\)", "", who))
        cand = forms.get(stem, []) + [who.split("(")[0].strip().split()[-1]]
        if any(f" {fid.norm(f)} " in np for f in cand if len(fid.norm(f)) > 2):
            notes.append("C ✓ (la nomo en la pasaĝo)")
        else:
            notes.append("C ? la nomo ne en la pasaĝo: juĝu"); flags["C"] += 1
        ly, py = set(YEAR.findall(date)), set(YEAR.findall(passage))
        if n in extra:
            notes.append("D ? la dato konkludita el la numero («dum aŭ antaŭ …», plano «dum aŭ post …☞»): juĝu, laŭ regulo 6")
            flags["D"] += 1; flags["K"] += 1
        elif ly and not (ly & py) and not re.search(r"kalkulite|laŭ ¶|laŭ PDF", FL.ours(line)):   # audit 36
            notes.append(f"D ? la jaro {', '.join(sorted(ly))} ne en la pasaĝo: juĝu"); flags["D"] += 1
        elif not ly and py and "sen dato" in date:
            notes.append(f"D ? sen dato, sed la pasaĝo nomas {', '.join(sorted(py))}: juĝu"); flags["D"] += 1
        else:
            notes.append("D ✓")
        sample.append(f"{k}. (linio {n+1}) {line}\n   - maŝine: " + "; ".join(notes))
        for it2, pg2, how, ws in cuts:
            excerpts.append(f"### {k}. {it2}, {'PDF' if 'PDF' in src else '¶'} {pg2} ({how})\n\n{' '.join(ws)}\n")
    head = (f"# La specimeno por la kontrolo de precizeco: {a.source} ({a.date})\n\n`[{len(pick)} linioj hazarde el "
            f"profiles/by-source/{a.source}-dowse.md ({len(L)} linioj), random.seed({seed})"
            + (f", kaj {len(extra)} el ĝiaj {len(kon) + sum(1 for i in pick if 'konkludita⟧' in L[i])} linioj kun dato konkludita el la "
               f"numero (n-roj {len(pick) + 1}–{len(pick) + len(extra)}), random.seed({seed + 1})" if extra else "")
            + f", per tools/dowse-accuracy-prep.py; "
            f"la pasaĝoj en sources/ocr-work/accuracy-excerpts/{a.source}-{a.date}.md. Maŝine: A {len(pick)-flags['A']}/{len(pick)} ankroj "
            f"trovitaj; C {flags['C']} kaj D {flags['D']} por juĝi.]`\n\n")
    open(sample_p, "w", encoding="utf-8").write(head + "\n".join(sample) + "\n")
    open(exc_p, "w", encoding="utf-8").write(f"# La pasaĝoj por la kontrolo de precizeco: {a.source} ({a.date})\n\n"
                                              "Kopirajta teksto: nur por la kontrolo, ne por citado.\n\n" + "\n".join(excerpts))
    print(f"{len(pick) + len(extra)} lines ({len(extra)} of them «konkludita») → {sample_p}\n  passages → {exc_p} ({sum(len(x) for x in excerpts)} chars)\n"
          f"  mechanical: A not found {flags['A']}, C to judge {flags['C']}, D to judge {flags['D']}")

if __name__ == "__main__":
    main()
