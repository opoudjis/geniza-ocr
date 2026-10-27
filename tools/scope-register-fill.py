#!/usr/bin/env python3
"""The checked scope candidates (EdE 1933, eo.wikipedia, io.wikipedia), triangulated person by person, mapped to roster
persons, and proposed as register rows (the editor, 2026-10-14).
- One person across the files: the same surname and first given name, or the same surname and a birth year within one
  (EdE gives given names in Esperanto: «Kolomano» Kalocsay, «Kálmán» on Wikipedia).
- The verdict: the files' verdicts agree, or one decides and the others are provisional; «in» against «out» is a
  conflict: provisional, both stated. A birth year two or more apart is noted.
- The roster: the stem «surname-given», or the bare surname stem when the roster has no other stem of that surname;
  the person's profile names them (full name, or initial and surname).
- Every row is qualified by the given name; a name the register already decides (hand rows) is skipped.
    tools/scope-register-fill.py [--date YYYY-MM-DD] [--dry-run]

Write-set: profiles/SCOPE-REGISTER.tsv (its mechanical rows, marked «mechanical, from the …» in the note, are replaced;
the hand rows are kept as they are) and profiles/build/SCOPE-REGISTER-CONFLICTS-<date>.md (the people whose files disagree,
in against out). --dry-run writes nothing. Ezri, 2026-10-14."""
import csv, glob, os, re, sys, unicodedata, collections
csv.field_size_limit(sys.maxsize)
import datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
def slug(w):
    w = w.replace("Œ", "OE").replace("œ", "oe")
    f = "".join(c for c in unicodedata.normalize("NFD", w.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", f).strip("-")
roster = [l.split("|")[0].strip() for l in open(sorted(glob.glob(G + "/dowse/ROSTER-FULL-CROSS-ARC-*.txt"))[-1], encoding="utf-8") if l.strip() and not l.startswith("#")]
stems = set(roster)
REGL = [l.split("\t")[0] for l in open(G + "/profiles/SCOPE-REGISTER.tsv", encoding="utf-8") if not l.startswith("#") and "mechanical, from the" not in l]
reg = {slug(n) for n in REGL if "(" not in n}
seen = {(slug(re.sub(r"\s*\(.*\)", "", n)), slug(re.search(r"\((.*)\)", n).group(1).split()[0])) for n in REGL if "(" in n}
PART = {"de", "von", "van", "la", "le", "di", "da", "del", "ten", "der", "den", "du", "des"}
def split_name(full):
    full = re.sub(r"\s*\(.*?\)", "", full).strip()
    toks = full.split()
    if len(toks) < 2: return None, None
    i = len(toks) - 1
    while i > 0 and toks[i - 1].lower() in PART: i -= 1
    return " ".join(toks[i:]), " ".join(toks[:i])
I = lambda x: int(x) if x and str(x).isdigit() else None
FILES = [("EdE", G + "/profiles/SCOPE-REGISTER-CANDIDATES-EDE-2026-10-14.tsv"),
         ("eo.wikipedia", G + "/profiles/SCOPE-REGISTER-CANDIDATES-EOWIKI-2026-10-14-CHECKED2.tsv"),
         ("io.wikipedia", G + "/profiles/SCOPE-REGISTER-CANDIDATES-IOWIKI-2026-10-14.tsv")]
recs = []
for src, f in FILES:
    for r in csv.DictReader((l for l in open(f, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        sur, given = split_name(r["name"])
        if not sur: continue
        recs.append(dict(src=src, sur=sur, given=given, s=slug(sur), g=slug(given.split()[0]) if given else "",
                         born=I(r["born"]), died=I(r.get("died")), jeo=I(r["joined_eo"]), jio=I(r["joined_io"]), v=r["verdict"], ev=r["evidence"]))
parent = list(range(len(recs)))
def find(i):
    while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
    return i
by_sg, by_sur = collections.defaultdict(list), collections.defaultdict(list)
for i, r in enumerate(recs): by_sg[(r["s"], r["g"])].append(i); by_sur[r["s"]].append(i)
def compatible(a, b):
    """Two records may be one person only if their dates allow it (2026-10-14: EdE's George Ledger joined in 1903,
    eo.wikipedia's was born in 1916): birth years within one, and neither's joining before the other's age of six."""
    if a["born"] and b["born"] and abs(a["born"] - b["born"]) > 1: return False
    for x, y in ((a, b), (b, a)):
        for j in (x["jeo"], x["jio"]):
            if j and y["born"] and j < y["born"] + 6: return False
    return True
for ids in by_sg.values():
    for j in ids[1:]:
        if compatible(recs[ids[0]], recs[j]): parent[find(j)] = find(ids[0])
for ids in by_sur.values():
    for a in ids:
        for b in ids:
            if a < b and recs[a]["src"] != recs[b]["src"] and recs[a]["born"] and recs[b]["born"] and abs(recs[a]["born"] - recs[b]["born"]) <= 1:
                parent[find(b)] = find(a)
people = collections.defaultdict(list)
for i, r in enumerate(recs): people[find(i)].append(r)
rep, stats, rows = [], collections.Counter(), []
stats["people"] = len(people)
for grp in people.values():
    srcs = sorted({r["src"] for r in grp})
    vs = {r["v"] for r in grp if r["v"] in ("in", "out")}
    borns = sorted({r["born"] for r in grp if r["born"]})
    notes = []
    if len(srcs) > 1:
        stats["in two or three files"] += 1
        if len(vs) == 2: stats["  conflict: in against out"] += 1
        elif len(vs) == 1 and all(r["v"] in vs for r in grp): stats["  agree"] += 1
        elif len(vs) == 1: stats["  one decides, the others provisional"] += 1
        else: stats["  all provisional"] += 1
    if len(borns) > 1 and borns[-1] - borns[0] >= 2:
        notes.append("birth years differ: " + ", ".join(f"{r['src']} {r['born']}" for r in grp if r["born"])); stats["birth years differ"] += 1
    if len(vs) == 2:
        # The editor, 2026-10-14 12:5x
        # a verdict resting on a stated joining year overrides one inferred without it (from the
        # birth or death year); stated years on both sides stay provisional
        stated = {r["v"] for r in grp if r["v"] in ("in", "out") and (r["jeo"] or r["jio"])}
        v = next(iter(stated)) if len(stated) == 1 else "provisional"
        how = f"resolved: {v}, the stated joining year over the inferred verdict" if len(stated) == 1 else "unresolved: stated years on both sides, provisional"
        notes.append("conflict " + how + ": " + "; ".join(f"{r['src']} {r['v']}" for r in grp))
        stats["  conflict " + how.split(":")[0]] += 1
        rep.append(f"- **{grp[0]['given']} {grp[0]['sur']}** ({how}): " + "; ".join(f"{r['src']}: {r['v']} (born {r['born'] or '?'}, joined {r['jeo'] or r['jio'] or '?'})" for r in grp))
    elif vs: v = next(iter(vs))
    else: v = "provisional"
    if v not in ("in", "out"): continue
    stats["decided"] += 1
    hit, why = None, "no roster person"
    for r in grp:
        cand = [x for x in (f"{r['s']}-{r['g']}", r["s"]) if x in stems]
        if not cand: continue
        stem = cand[0]
        if stem == r["s"] and any(x.startswith(r["s"] + "-") for x in stems if x != r["s"]): why = "several roster stems"; break
        pf = G + f"/profiles/{stem}.md"
        flat = slug(open(pf, encoding="utf-8").read()) if os.path.exists(pf) else ""
        names = [slug(f"{x['given']} {x['sur']}") for x in grp] + [slug(f"{x['given'][:1]} {x['sur']}") for x in grp if x["given"]]
        if any(n and f"-{n}-" in f"-{flat}-" for n in names): hit = (stem, r); break
        why = "the profile lacks the name"; break
    if not hit: stats["not mapped: " + why] += 1; continue
    stem, r = hit
    if r["s"] in reg or stem in reg or (r["s"], r["g"]) in seen: stats["not mapped: the register decides already"] += 1; continue
    seen.add((r["s"], r["g"])); stats["mapped"] += 1
    w = next((x for x in grp if x["src"] != "EdE"), r)
    name = f"{w['sur'].upper()} ({w['given'].split()[0]})"
    jeo = min((x["jeo"] for x in grp if x["jeo"]), default=""); jio = min((x["jio"] for x in grp if x["jio"]), default="")
    ev = " | ".join(f"{x['src']}: {x['ev']}" for x in grp)
    rows.append((name, "Ido" if jio and not jeo else "Esperanto", jeo, jio, v,
                 f"{ev}; triangulated: {', '.join(srcs)}{' (' + '; '.join(notes) + ')' if notes else ''}; mapped to profiles/{stem}.md",
                 "proposed", "mechanical, from the EdE and Wikipedia candidates after the plausibility check, triangulated (the editor, 2026-10-14)"))
date = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else datetime.date.today().isoformat()
if "--dry-run" not in sys.argv:
    rp = os.path.join(G, "profiles", "SCOPE-REGISTER.tsv")
    keep = [l for l in open(rp, encoding="utf-8") if "mechanical, from the" not in l]
    with open(rp, "w", encoding="utf-8") as fh:
        fh.writelines(keep); fh.writelines("\t".join(str(y) for y in x) + "\n" for x in rows)
    with open(os.path.join(G, "profiles", "build", f"SCOPE-REGISTER-CONFLICTS-{date}.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Conflicts between the scope candidate files ({date})\n\n`[tools/scope-register-fill.py: a person in two or three of the files (EdE 1933, eo.wikipedia, io.wikipedia) whom one has in scope and another out. Such a person stays provisional; the editor decides.]`\n\n" + "\n".join(rep) + "\n")
    print(f"register: {len(keep)} hand lines kept, {len(rows)} mechanical rows written")
for k in sorted(stats): print(f"{k}: {stats[k]}")
print(collections.Counter(x[4] for x in rows), len(rep), "conflicts")
