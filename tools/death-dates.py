#!/usr/bin/env python3
"""Later mentions of a death, dated as the death (2026-10-26; the accuracy check of the redowse 2026-10-25r found Dor's
«†» on every cover of Lingvo Internacia dated by each cover's issue, his death so put as late as 1914-07; the editor:
).

    tools/death-dates.py [--source S …] [--report OUT.md] [--write]

In each dowse facts file (profiles/by-source/<source>-dowse.md), the lines of kind «morto» are grouped by person (the
head, with its qualifier). A line whose date is a plain date (a year, a month or a day) LATER than the earliest plain
death date the same source gives that person cannot be the death's date: it is a later mention (a «†» kept on a list,
a memorial, an anniversary) dated by its issue. The runbook's dating rule 2 (an act earlier than the issue carries that
date, or a bound) gives it «antaŭ ‹its date›». «Later» is compared at the shorter date's length («1913-08» is not later
than «1913-08-12», «1913-10» is). Lines already bounded («antaŭ», «dum», «inter», «post») are left.

--report writes the persons, their dates and the lines proposed (create-only); --write appends one date row per line to
dowse/<source>/DECISIONS.tsv (keyed on the locator, item by file name, and the anchor), as dowse-undated.py writes its
rows; the sources are then reassembled (dowse-facts-assemble.py <source> --replace) and harvested. A source with no
dowse folder is reported, not written. Ezri, 2026-10-26."""
import argparse, csv, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
PLAIN = re.compile(r"\d{4}(?:-\d\d){0,2}")

def later(a, b):
    n = min(len(a), len(b))
    return a[:n] > b[:n]

def key_names():
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        rows = csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")
        return {r["key"].strip(): r["item"] for r in rows if (r.get("key") or "").strip()}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--source", nargs="*"); ap.add_argument("--report"); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    k2n = key_names()
    why = "a later mention of the death, dated by its issue (tools/death-dates.py, 2026-10-26; the editor)"
    R, total, rows_by, looks = [], 0, {}, []
    for f in sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md"))):
        s = os.path.basename(f)[:-9]
        if a.source and s not in a.source: continue
        by = {}
        for l in open(f, encoding="utf-8"):
            if not l.startswith("- $$$") or " · {morto" not in l: continue
            p = l.rstrip("\n").split(" · ")
            if len(p) < 5 or "**" not in p[0]: continue
            who, date = p[0].split("**")[0].strip()[2:].strip(), p[0].split("**")[1]
            by.setdefault(who, []).append((date, p[3], p[4], l.rstrip("\n")))
        props = []
        for who, ll in by.items():
            plain = [d for d, *_ in ll if PLAIN.fullmatch(d)]
            if len(set(plain)) < 2: continue
            first = min(plain)   # the earliest (string order puts «1913» before «1913-08»)
            for d, anchor, loc, line in ll:
                if PLAIN.fullmatch(d) and later(d, first):
                    item = loc.split(",")[0].strip()
                    # ONLY A DATE FROM THE ISSUE (the first run's review, 2026-10-26: Schleyer's «1912-08-16», his death
                    # day from the passage, came after a misdated «1911-08»; two Berthelots under one head): «antaŭ ‹its
                    # date›» is true of any death line dated by its issue, whoever the person, and false of a date the
                    # passage gives; the others are listed for a look, not changed
                    if "la dato de la numero" not in line: looks.append((s, who, first, d, loc)); continue
                    props.append((who, first, d, anchor, k2n.get(item, item) + loc[len(item):], line))
        if not props: continue
        total += len(props)
        has = os.path.exists(os.path.join(G, "dowse", s, "DECISIONS.tsv"))
        R += [f"## {s}: {len(props)} lines" + ("" if has else " (no dowse/‹source›/DECISIONS.tsv: not written)"), ""]
        R += [f"- {who}: earliest {first}; {d} → «antaŭ {d}» · {loc}" for who, first, d, _a, loc, _l in props] + [""]
        if has: rows_by[s] = props
        print(f"{s}: {len(props)} lines" + ("" if has else " (no DECISIONS.tsv)"))
    print(f"{total} lines proposed; {len(looks)} later dates from the passage, for a look")
    R += ["## For a look: a later death date the passage itself gives (not changed)", ""]
    R += [f"- {s}: {who}: earliest {first}; {d} · {loc}" for s, who, first, d, loc in looks] + [""]
    if a.report:
        if os.path.exists(a.report): sys.exit(f"{a.report} exists: not overwritten")
        open(a.report, "x", encoding="utf-8").write(f"# Later mentions of a death, dated as the death\n\n*Generated by `tools/death-dates.py`. {total} lines proposed; {len(looks)} for a look.*\n\n" + "\n".join(R) + "\n")
        print(f"wrote {os.path.relpath(a.report, ROOT)}")
    if a.write:
        for s, props in rows_by.items():
            with open(os.path.join(G, "dowse", s, "DECISIONS.tsv"), "a", encoding="utf-8") as fh:
                for who, first, d, anchor, loc, _l in props:
                    fh.write("\t".join([loc, anchor.strip("«»")[:60], "date", f"antaŭ {d}", why, f"the source's earliest death date for {who}: {first}"]) + "\n")
            print(f"appended {len(props)} rows to dowse/{s}/DECISIONS.tsv")

if __name__ == "__main__":
    main()
