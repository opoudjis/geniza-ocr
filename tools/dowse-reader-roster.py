#!/usr/bin/env python3
"""The fact readers' roster for one source: the full roster's lines of the persons the name search found at the strong
tiers (exact, near, confusion), not those found only by joins, small caps or stems (mostly noise).

    tools/dowse-reader-roster.py <source> <full roster> <record.hits.tsv> [--date YYYY-MM-DD] [--out-list]

--out-list also writes dowse/<source>/out-list-<date>.md: the people the scope register or its candidates have out and the
name search found in the source, for the brief (the dowse runbook, D6 point 7). People not on the roster are not matched.

Writes geniza/dowse/<source>/roster-reader-<date>.txt (refused if it exists). The readers use it for the spelling of a
NAME only; a person not on it is written as printed (the fact-reading brief). Made for the global redowse, stage 1
(the Jossinet pilot, 2026-10-13: 163 of 230 persons; the editor). Ezri, 2026-10-13."""
import argparse, csv, datetime, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
STRONG = {"exact", "near", "confusion"}
csv.field_size_limit(sys.maxsize)        # a hits file can carry a very long field (Waringhien, Neves: 2026-10-14)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("roster"); ap.add_argument("hits")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--out-list", action="store_true", help="also write out-list-<date>.md for the brief")
    ap.add_argument("--again", action="store_true", help="rewrite this tool's own two files of the date, if git does not track them")
    a = ap.parse_args()
    out = os.path.join(G, "dowse", a.source, f"roster-reader-{a.date}.txt")
    if os.path.exists(out) and not again_ok(a, out): sys.exit(f"refusing: {out} exists")
    found, strong, years, items_seen = set(), set(), set(), set()
    with open(a.hits, encoding="utf-8") as fh:
        rows = csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")
        for r in rows:
            found.add(r["person"])
            if r["tier"] in STRONG: strong.add(r["person"])
            if re.fullmatch(r"1[89]\d\d|20\d\d", (r.get("year") or "").strip()): years.add(int(r["year"]))
            elif r.get("item"): items_seen.add(r["item"])
    if not years and items_seen:    # rows without a year (a book, «kongresa.libro.01»): the item table's year (written)
        for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8"):
            x = l.split("\t")
            if len(x) > 16 and x[0] in items_seen:
                years |= {int(y) for y in re.findall(r"\b(1[89]\d\d|20\d\d)\b", x[5] + " " + x[16])}
    a.last_year = max(years) if years else None    # the source's last year, for the «out» list
    lines = [l.rstrip("\n") for l in open(a.roster, encoding="utf-8") if l.strip() and not l.startswith("#")]
    keep = [l for l in lines if l.split(" | ")[0].strip() in strong]
    head = (f"# La rolulo por la legiloj de {a.source} ({a.date}): nur la personoj, kiujn la nomserĉo trovis je la niveloj "
            f"exact, near aŭ confusion ({len(keep)} el {len(found)}; la ceteraj nur je join, majuskletoj aŭ radikoj, plejparte "
            f"bruo). Por la literumo de la NOMO nur; persono ne en la listo estas skribata kiel presite. "
            f"El {os.path.relpath(a.roster, G)} kaj {os.path.basename(a.hits)}, per tools/dowse-reader-roster.py.")
    open(out, "w", encoding="utf-8").write(head + "\n" + "\n".join(keep) + "\n")
    print(f"{len(keep)} of {len(found)} persons → {out}")
    missing = strong - {l.split(' | ')[0].strip() for l in keep}
    if missing: print(f"  ⚠ found at a strong tier but not on the roster: {sorted(missing)[:20]}")
    if a.out_list: out_list(a, found)

def again_ok(a, path):
    """--again rewrites a file this tool wrote, only if git does not track it (the runbook, P5)."""
    if not a.again: return False
    import subprocess
    r = subprocess.run(["git", "-C", os.path.dirname(path), "ls-files", "--error-unmatch", os.path.basename(path)],
                       capture_output=True)
    if r.returncode == 0: sys.exit(f"refusing --again: {path} is tracked by git")
    return True

def out_list(a, found):
    """The source's «out» list for the brief (the dowse runbook, D6 point 7; the editor 2026-10-13): the people
    the scope register or its candidates have out whom the name search found, with full name, birth and joining year.

    Lean since 2026-10-22 (the editor): the list was 60%
    of every brief (100 entries, 2,530 of 4,224 words in the 106 briefs of 2026-10-21), mostly the register's English
    provenance, and 57% of its people were born after 1914, found only by a shared surname. Now one short line in
    Esperanto an entry («**MARTIN (Hugh)**: naskiĝis 1931»; «aliĝis 1916»; «korpo»), and no one born after the
    source's last year (the hits file's latest year), who cannot be the person in its text."""
    dst = os.path.join(G, "dowse", a.source, f"out-list-{a.date}.md")
    if os.path.exists(dst) and not again_ok(a, dst): sys.exit(f"refusing: {dst} exists")
    f = {x.lower() for x in found}
    def hit(n):
        o = re.sub(r" \(.*\)| de$", "", n).lower()
        return any(o == x or o in x.split("-") or o.replace(" ", "-") == x for x in f)
    items, seen, late = [], set(), 0
    reg = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
    for l in (open(reg, encoding="utf-8") if os.path.exists(reg) else []):
        x = l.rstrip("\n").split("\t")
        x += [""] * (8 - len(x))   # a row whose empty last fields lost their tabs (2026-10-15, the Fable review 20)
        if l.startswith("#") or x[0] == "name" or x[4] != "out" or not hit(x[0]): continue
        born = re.search(r"\bborn (1[5-9]\d\d|20\d\d)", x[7])
        if born and a.last_year and int(born.group(1)) > a.last_year:
            late += 1; continue
        seen.add(re.sub(r" \(.*\)", "", x[0]).upper())
        why = ("korpo" if x[1] == "entity" else f"naskiĝis {born.group(1)}" if born
               else f"aliĝis {x[2] or x[3]}" if (x[2] or x[3]) else "ekster laŭ la registro")
        items.append(f"- **{x[0]}**: {why}")
    # The candidate files are not read here: they are inputs to the register, which alone decides scope (the editor,
    # 2026-10-14 11:3x, approved to the consolidation); their mechanical verdicts reach the readers only as register rows.
    open(dst, "w", encoding="utf-8").write(f"# La personoj «ekster» por {a.source} ({a.date}), per tools/dowse-reader-roster.py --out-list: {len(items)}\n\n" + "\n".join(items) + "\n")
    print(f"{len(items)} out → {dst}" + (f" ({late} born after {a.last_year} left out)" if late else ""))

if __name__ == "__main__":
    main()
