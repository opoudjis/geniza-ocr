#!/usr/bin/env python3
"""Who hides behind the initials (2026-11-04; the editor: initials often hide a name, as «A. Z.» in the first issue of
*Lingvo Internacia* hid its first donor; the initials disambiguated, and raised as disambiguations). No tokens.

    tools/initials-candidates.py [--min-lines 1] [--top 3] [--date YYYY-MM-DD] [--write]

From profiles/build/FACTS-LIST.tsv (the last harvest): every person whose NAME is initials only («A. Z.», «H. K. B.»,
Cyrillic «А. З.» read by its Latin letters), with its lines' sources, years and towns; and for each, the persons of the
list whose surname begins with the last initial and whose lines give a forename or initial beginning with the others
(from the head's qualifier, «LEMAIRE (Charles)», or a printed «Aleksej Zinovjev» / «A. Zinovjev» before the surname in
the line). A candidate is scored by what the dowse already counts as bearing an identification out:
  +3 the same source (a facts file both have lines in); +2 the years overlap (within two years);
  +2 the same town (a {loĝado: …} or a town named in both); +1 the forename initial attested (else «forename unknown»).
Proposals only, never a merge: an identification behind initials is a historiographic claim (the hiding was deliberate),
so each goes to the editor with its evidence; a reading pass over the best candidates' lines comes after, its cost first.
With --write (create-only): geniza/dowse/initials/INITIALS-CANDIDATES-<date>.tsv (one row a candidate) and
INITIALS-REVIEW-<date>.md (one entry an initials head, its lines' sources and years, its candidates). Without --write it
prints the counts. Ezri."""
import argparse, csv, datetime, os, re, sys
from collections import Counter, defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
csv.field_size_limit(sys.maxsize)
CYR = dict(zip("АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЭЮЯ", ["A", "B", "V", "G", "D", "E", "Ĵ", "Z", "I", "J", "K", "L", "M", "N", "O", "P", "R", "S",
                                               "T", "U", "F", "H", "C", "Ĉ", "Ŝ", "Ŝ", "E", "J", "J"]))
FOLD = {"Ĉ": "C", "Ĝ": "G", "Ĥ": "H", "Ĵ": "J", "Ŝ": "S", "Ŭ": "U", "Ž": "Z", "Š": "S", "Č": "C", "Ł": "L", "Ś": "S", "Ź": "Z", "Ż": "Z"}
INIT = re.compile(r"^((?:[A-ZĈĜĤĴŜŬА-Я][a-z]?\.\s?){1,3})$")
def letters(name):
    """«A. Z.» → ['A', 'Z'] (Latin, folded); «Ch. B.» → ['C', 'B']."""
    out = []
    for tok in re.findall(r"[A-ZĈĜĤĴŜŬА-Я][a-z]?", name):
        c = CYR.get(tok[0], tok[0]); out.append(FOLD.get(c, c))
    return out
def fold(s): return "".join(FOLD.get(c, c) for c in s.upper())
YEAR = re.compile(r"\b(1[89]\d\d)\b")
TOWN = re.compile(r"\{[^}]*?lo[ĝg]ado: ([^;},]+)")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-lines", type=int, default=1); ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--date", default=datetime.date.today().isoformat()); ap.add_argument("--write", action="store_true")
    ap.add_argument("--reading-input", action="store_true", help="with --write: the reading pass's inputs and briefs too")
    ap.add_argument("--reading-min", type=int, default=3); ap.add_argument("--per-cand", type=int, default=8)
    ap.add_argument("--part-words", type=int, default=18000)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(G, "profiles", "build", "FACTS-LIST.tsv"), encoding="utf-8"), delimiter="\t"))
    # (second form, 2026-11-04: the first scored by whole facts files and whole year spans, so ZAMENHOF, GRABOWSKI and
    # the like, in every source and every decade, led every list; and «D-ro», «En» were read as forenames)
    files, towns, given = (defaultdict(set) for _ in range(3))
    srcyears = defaultdict(set)        # (facts file, year) of a person's primary lines, to 1917
    nlines, sample = Counter(), defaultdict(list)
    TITLE = {"D", "DRO", "D-RO", "S", "SRO", "S-RO", "SINJORO", "PROF", "PROFESORO", "F", "FINO", "F-INO", "S-INO", "SINO",
             "EN", "LA", "DE", "AL", "KAJ", "PASTRO", "ABATO", "KAPITANO", "LEŬTENANTO", "GENERALO", "KOMANDANTO", "M", "MR",
             "MME", "MLLE", "HERR", "FRL", "FRAU", "DR", "MRS", "MISS", "REV", "SIR", "MONS", "MGR", "INĜ", "ING", "ADV"}
    for r in rows:
        p = r["person"].strip(); line = r["line"]
        files[p].add(r["file"]); nlines[p] += 1
        ys = [int(y) for y in YEAR.findall(r["year"] or "")]
        for y in ys:
            if y <= 1917: srcyears[p].add((r["file"], y))
        for t in TOWN.findall(line): towns[p].add(t.strip().lower())
        # (third form: initials are one person per source, «A. Z.» of Juna Esperantisto 1910 not the «A. Z.» of
        # Lingvo Internacia 1897, so a head is the initials in one facts file)
        if INIT.match(p): sample[(p, r["file"])].append(r); continue
        m = re.match(r"^- \$\$\$ .+? \$\$\$\s*\(([^)]{1,40})\)", line)
        if m:
            for w in re.findall(r"[A-ZĈĜĤĴŜŬÀ-Ž][\wÀ-ž]*", m.group(1)):
                if fold(w).strip(".") not in TITLE: given[p].add(fold(w)[0])
        sur = re.split(r"[ (-]", p)[0]
        if len(sur) >= 4:
            for m in re.finditer(r"\b([A-ZĈĜĤĴŜŬÀ-Ž][\wà-ž-]*)\.?\s+(?:[A-ZĈĜĤĴŜŬÀ-Ž]\.\s*)?" + re.escape(sur[:4].title()), line):
                w = fold(m.group(1)).replace("-", "")
                if w.strip(".") not in TITLE and len(w) >= 1: given[p].add(w[0])
    heads = sorted((p for p in sample if len(sample[p]) >= a.min_lines), key=lambda p: -len(sample[p]))
    by_init = defaultdict(list)
    for p in nlines:
        if not INIT.match(p) and p[:1]: by_init[fold(p)[0]].append(p)
    cands, review = [], []
    for key in heads:
        h, hf = key
        L = letters(h)
        if len(L) < 2: continue          # a single initial: too weak to propose
        sur, fore = L[-1], L[:-1]
        hy = {int(y) for r in sample[key] for y in YEAR.findall(r["year"] or "") if int(y) <= 1917}
        ht = {t for r in sample[key] for t in TOWN.findall(r["line"])}
        for r in sample[key]:
            for t in re.findall(r"\ben ([A-ZÀ-Ž][\wà-ž-]+)", r["line"]): ht.add(t.lower())
        sc = []
        for p in by_init.get(sur, []):
            if nlines[p] < 2: continue
            if given[p] and fore[0] not in given[p]: continue      # a forename known, and not the initial: not him
            near = sorted({y for f, y in srcyears[p] if f == hf and any(abs(x - y) <= 1 for x in hy)})
            if not near and hf not in files[p]: continue           # never in this source: not proposed
            s, why = 0, []
            if near: s += 4; why.append(f"sama fonto, jaroj {near[0]}–{near[-1]}")
            else: s += 2; why.append("sama fonto, aliaj jaroj")
            tw = towns[p] & ht
            if tw: s += 2; why.append("urbo: " + ", ".join(sorted(tw))[:40])
            if given[p]: s += 2; why.append("persona nomo kun " + fore[0])
            else: why.append("persona nomo nekonata")
            here = sum(1 for f, y in srcyears[p] if f == hf)
            if s >= 4: sc.append((s, here, p, "; ".join(why)))
        sc.sort(key=lambda x: (-x[0], -x[1]))
        sc = [(s, p, why) for s, here, p, why in sc]
        for s, p, why in sc[:a.top]: cands.append([h, hf.replace("-dowse.md", ""), len(sample[key]), p, nlines[p], s, why])
        review.append(f"### {h} en {hf.replace('-dowse.md', '')} · {len(sample[key])} linioj · jaroj "
                      f"{min(hy) if hy else '?'}–{max(hy) if hy else '?'}\n\n"
                      + ("".join(f"- **{p}** ({nlines[p]} linioj), poentoj {s}: {why}\n" for s, p, why in sc[:a.top]) or "- neniu kandidato kun almenaŭ 4 poentoj\n") + "\n")
    with_c = len({(c[0], c[1]) for c in cands})
    print(f"{len(heads)} initials heads, one a source ({sum(len(sample[h]) for h in heads)} lines); {with_c} with a candidate of 4 points or more; "
          f"{len(cands)} candidate rows")
    for c in cands[:15]: print("  ", c[0], "in", c[1], f"({c[2]})", "→", c[3], c[5], "|", c[6][:80])
    if not a.write: print("(dry run: nothing written)"); return
    od = os.path.join(G, "dowse", "initials"); os.makedirs(od, exist_ok=True)
    tp, rp = os.path.join(od, f"INITIALS-CANDIDATES-{a.date}.tsv"), os.path.join(od, f"INITIALS-REVIEW-{a.date}.md")
    for p in (tp, rp):
        if os.path.exists(p): sys.exit(f"refusing to overwrite {p}")
    with open(tp, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["initials", "source", "their lines", "candidate", "his lines", "points", "why"]); w.writerows(cands)
    open(rp, "x", encoding="utf-8").write(
        f"# Kiu kaŝiĝas malantaŭ la inicialoj ({a.date})\n\n`[GENERATED by tools/initials-candidates.py from profiles/build/"
        f"FACTS-LIST.tsv. Do not hand-edit — re-run it. Proposals only: no line is moved by this list.]`\n\n"
        f"{len(heads)} kapoj el inicialoj, unu por fonto; {with_c} kun kandidato. La poentoj: +4 la sama fonto en apudaj jaroj "
        f"(+2 en aliaj), +2 la sama urbo, +2 la persona nomo atestita kun la inicialo; persona nomo konata kaj alia: ne kandidato. "
        f"Ordo de egalaj: kiom da linioj la kandidato havas en la sama fonto.\n\n" + "".join(review))
    print(f"wrote {os.path.relpath(tp, ROOT)} and {os.path.relpath(rp, ROOT)}")
    if a.reading_input: reading_input(a, heads, sample, cands, rows, od)

# THE READING PASS'S INPUTS (2026-11-04; the editor, on Zivoniev and Zakrzewski, who both
# appear in it): one initials head can be several persons, so the reader judges line
# by line. Each head with --reading-min lines or more: its lines, numbered, and for each candidate up to --per-cand of his
# lines in the same source, the nearest in year first. Parts of about --part-words words, each with its brief; the
# readers' answer: «H.k · KANDIDATO|neniu|necerta · kial», one line per line of the head.
def reading_input(a, heads, sample, cands, rows, od):
    byp = defaultdict(list)
    for r in rows: byp[(r["person"].strip(), r["file"])].append(r)
    bycand = defaultdict(list)
    for c in cands: bycand[(c[0], c[1])].append(c[3])
    blocks = []
    for key in heads:
        h, hf = key
        if len(sample[key]) < a.reading_min or (h, hf.replace("-dowse.md", "")) not in bycand: continue
        hy = sorted({int(y) for r in sample[key] for y in YEAR.findall(r["year"] or "")})
        b = [f"### {len(blocks) + 1}. «{h}» en {hf.replace('-dowse.md', '')} ({len(sample[key])} linioj)\n\n**La linioj sub «{h}»:**\n"]
        b += [f"- {len(blocks) + 1}.{k} {r['line'][:420]}\n" for k, r in enumerate(sample[key], 1)]
        for p in bycand[(h, hf.replace("-dowse.md", ""))]:
            mine = byp[(p, hf)]
            def dist(r):
                ys = [int(y) for y in YEAR.findall(r["year"] or "")]
                return min((abs(y - x) for y in ys for x in hy), default=99)
            mine = sorted(mine, key=dist)[:a.per_cand]
            b.append(f"\n**Kandidato {p}** ({len(byp[(p, hf)])} linioj en la sama fonto; jen la plej proksimaj laŭ jaro):\n")
            b += [f"  - {r['line'][:300]}\n" for r in mine]
        blocks.append("".join(b) + "\n")
    parts, cur, words = [], [], 0
    for bl in blocks:
        w = len(bl.split())
        if cur and words + w > a.part_words: parts.append(cur); cur, words = [], 0
        cur.append(bl); words += w
    if cur: parts.append(cur)
    BRIEF = ("Vi juĝas, kiu persono kaŝiĝas malantaŭ la inicialoj en ĉiu linio. La fontoj ofte kaŝis nomon per inicialoj "
             "(«A. Z.» en la unua *Lingvo Internacia*), kaj unu inicialoj en unu fonto povas esti pluraj personoj, do juĝu "
             "**linion post linio**. Por ĉiu linio: la kandidato, se la linio mem kaj la linioj de la kandidato en la sama "
             "fonto konfirmas ĝin per io konkreta (la sama urbo, ofico, temo, rilato kun la sama persono, la sama tempo); "
             "**neniu**, se la linio montras alian personon ol ĉiuj kandidatoj; **necerta**, se nenio konkreta decidas. Ne "
             "divenu: la inicialoj solaj neniam sufiĉas.\n\n**La raporto:** unu linio por ĉiu linio de la eroj, en ĉi tiu formo:\n\n"
             "`N.k · KANDIDATO|neniu|necerta · kial (malpli ol 25 vortoj)`\n\nFinu per la linio «Fino: M linioj.»\n")
    for i, part in enumerate(parts, 1):
        ip = os.path.join(od, f"INITIALS-INPUT-{a.date}-{i}.md"); bp = os.path.join(od, f"initials-brief-{a.date}-{i}.md")
        for p in (ip, bp):
            if os.path.exists(p): sys.exit(f"refusing to overwrite {p}")
        open(ip, "x", encoding="utf-8").write(f"# La inicialoj, parto {i} ({a.date})\n\n`[GENERATED by tools/initials-candidates.py "
                                              f"--reading-input. Do not hand-edit — re-run it.]`\n\n" + "".join(part))
        n = sum(int(re.search(r"\((\d+) linioj\)", bl).group(1)) for bl in part)
        open(bp, "x", encoding="utf-8").write(f"# La inicialoj: parto {i}\n\n`[Ezri, {a.date}; la redaktoro petis la inicialojn kaj ilian daŭrigon. "
            f"La legilo legas nur per la ilo Read; ĝi skribas nenion; ĝia raporto estas ĝia fina mesaĝo.]`\n\n"
            f"## La briefo, kiel donita al la legilo\n\nLegu `{ip}` tute, per Read kun offset kaj limit, en partoj de 400 linioj. "
            f"Legu nenion alian.\n\n" + BRIEF.replace("M linioj", f"{n} linioj"))
        print(f"wrote {os.path.relpath(ip, ROOT)} and its brief: {len(part)} heads, {n} lines, {sum(len(b.split()) for b in part)} words")

if __name__ == "__main__":
    main()
