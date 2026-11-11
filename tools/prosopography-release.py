#!/usr/bin/env python3
"""The prosopography's machine tables (the publishing runbook, step 2; the editor, 2026-11-10).

    prosopography-release.py tables TAG VERSION [--out DIR] [--skip STEM ...] [--replace]

Writes, for every person of smelt TAG (smelt/<stem>/PROFILE-FROZEN-<TAG>.md), three CSV files (UTF-8, a header row):
  facts.csv     one row a fact line of the frozen profile: id «<stem>:<TAG>:L<n>», person, date, kind, fact, anchor, label,
                siglum, locator, voice, status (a copy «⟦kopio el …⟧», an absence, a refutation, else blank)
  groups.csv    one row a member of a group: group «<stem>:<TAG>:<G|U|S|R><n>», made_by (tool, reader), kind, object,
                statement, status, fact (the member's fact id); the tool's groups and single lines (S3-INPUT), its spans and
                recurrences (S3-COMPRESSED), the readers' groups (S3-RETURN part 2)
  episodes.csv  one row an episode (S3-RETURN part 1): episode «<stem>:<TAG>:E<n>», title, date, groups, facts,
                circumstances, see_also
and sources.csv: each siglum the facts cite, its entry, and «in_copyright». The anchor of a fact is left empty unless its
siglum's in_copyright is «no» (the runbook, step 4; the editor's ruling: works whose authors died 70 or more years ago;
uncertain, «ask»). in_copyright comes from profiles/COPYRIGHT.tsv (siglum, in_copyright, basis), the editor's ruling; a siglum it
does not list is «ask», so its anchors are withheld. Default output: geniza/prosopografio-eldono/<VERSION>/. Create-only
unless --replace. Ezri, 2026-11-11."""
import csv, glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SM = os.path.join(G, "smelt")
ITEM = re.compile(r"^- \*\*([GUSRKN]\d+)\*\* · (.*)$")


def copyright_table():
    p = os.path.join(G, "profiles", "COPYRIGHT.tsv")
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            out[r["siglum"]] = r["in_copyright"].strip()
    return out


def labels(stem, tag):
    out = {}
    p = os.path.join(SM, stem, f"LABELS-{tag}.tsv")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) > 1 and re.match(r"L\d+$", f[0]): out[int(f[0][1:])] = f[1]
    return out


def siglum_of(label):
    m = re.match(r"([^\s:]+)", label or "")
    s = m.group(1) if m else ""
    return "" if s in ("?", "siglo") else s


def status_of(f):
    t = " ".join((f.get("fact", ""), f.get("voice", ""), f.get("kind", "")))
    if "⟦kopio el" in t or "kopio el" in f.get("voice", ""): return "kopio"
    if re.search(r"\{(foresto|manko)", f.get("kind", "")): return "foresto"
    if "refut" in t or "malvera" in t: return "refuto"
    return ""


def kind_object(k):
    m = re.match(r"\{([^:}]+):?\s*([^}]*)\}", k or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ((k or "").strip("{} "), "")


def tables(tag, version, out, skip, replace):
    if os.path.exists(out) and os.listdir(out) and not replace: sys.exit(f"{out} exists (--replace)")
    os.makedirs(out, exist_ok=True)
    cr = copyright_table()
    stems = sorted(p.split(os.sep)[-2] for p in glob.glob(os.path.join(SM, "*", f"PROFILE-FROZEN-{tag}.md")) if p.split(os.sep)[-2] not in skip)
    F = csv.writer(open(os.path.join(out, "facts.csv"), "w", encoding="utf-8", newline=""))
    Gw = csv.writer(open(os.path.join(out, "groups.csv"), "w", encoding="utf-8", newline=""))
    E = csv.writer(open(os.path.join(out, "episodes.csv"), "w", encoding="utf-8", newline=""))
    F.writerow(["id", "person", "date", "kind", "fact", "anchor", "label", "siglum", "locator", "voice", "status"])
    Gw.writerow(["group", "made_by", "kind", "object", "statement", "status", "fact"])
    E.writerow(["episode", "title", "date", "groups", "facts", "circumstances", "see_also"])
    sig_used, n = {}, {"facts": 0, "withheld": 0, "groups": 0, "members": 0, "episodes": 0}
    entries = {}
    for l in open(os.path.join(G, "profiles", "SIGLA.tsv"), encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if len(f) > 3 and not l.startswith("#"): entries[f[0]] = f[3]
    items = {}
    for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        for k in {r.get("item", ""), (r.get("key") or "").strip()} - {""}: items[k] = r.get("year") or ""
    Y = re.compile(r"(1[5-9]\d\d|20[0-2]\d)")
    def year_of(label, locator, entry):
        head = (label or "").rsplit(":", 1)[0]
        for t in (head, items.get((locator or "").split(",")[0].strip(), ""), entry):
            m = Y.search(t or "")
            if m: return int(m.group(1))
        return None
    for stem in stems:
        d = os.path.join(SM, stem)
        pid = lambda x: f"{stem}:{tag}:{x}"
        prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
        lab = labels(stem, tag)
        for i, l in enumerate(prof, 1):
            f = FL.fields(l) if l.startswith("- $$$") else None
            if not f: continue
            lb = lab.get(i, ""); sg = siglum_of(lb)
            # the editor's rule (2026-11-11): published up to 1930, out of copyright; later, «ask»; COPYRIGHT.tsv's rows first
            # (Privat's three, in copyright to 2032). The year: the label's head («AmEsp 1910.3», «Zakr1913»), else the item
            # table's year of the line's item, else the siglum's entry
            if sg in cr: state = cr[sg]
            else:
                y = year_of(lb, f["locator"], entries.get(sg, ""))
                state = "no" if y and y <= 1930 else "ask"
            free = state == "no"
            if sg: sig_used.setdefault(sg, set()).add(state)
            F.writerow([pid(f"L{i}"), f["head"] + (f" ({f['qual']})" if f["qual"] else ""), f["date"], f["kind"].strip("{}"), f["fact"],
                        f["anchor"] if free else "", lb, sg, f["locator"], re.sub(r"\s*⟵\s*`[^`]*`", "", f["voice"]).strip(), status_of(f)])   # our working file's name out
            n["facts"] += 1; n["withheld"] += 0 if free else 1
        # the tool's groups, single lines, spans and recurrences
        seen = set()   # (group, line): a membership once; the groups and single lines from S3-INPUT, the spans and recurrences from S3-COMPRESSED
        for p in sorted(glob.glob(os.path.join(d, f"S3-INPUT-{tag}*.md"))) + sorted(glob.glob(os.path.join(d, f"S3-COMPRESSED-{tag}*.md"))):
            if "-read-" in p or p.endswith("-reader.md"): continue
            comp = "S3-COMPRESSED" in p
            for l in open(p, encoding="utf-8"):
                m = ITEM.match(l.rstrip("\n"))
                if not m or m.group(1)[0] in "KN": continue
                gid, rest = m.group(1), m.group(2)
                if comp and gid[0] in "GU": continue
                head, _, mem = rest.rpartition(": ")
                kind, obj = (head.split(" / ", 1) + [""])[:2] if " / " in head else (head, "")
                kind = re.sub(r"^\d{4}(?:–\d{4})? · ", "", kind).strip()
                stmt = (re.search(r"(?:ekz\.|unue): (.*?) — \d+ linioj", rest) or [None, ""])[1]
                ls = [int(x) for x in re.findall(r"\bL(\d+)\b", mem)]
                if not ls: continue
                if comp:   # «· 1895–1896 · loĝado / Odeso (atestita: …) · unue: …»
                    hp = rest.split(" · ")
                    ko = hp[1] if len(hp) > 1 else ""
                    kind, obj = (ko.split(" / ", 1) + [""])[:2]
                    obj = re.sub(r"\s*\(atestita:.*", "", obj)
                n["groups"] += 1
                for x in ls:
                    if (gid, x) in seen: continue
                    seen.add((gid, x)); Gw.writerow([pid(gid), "tool", kind.strip(), obj.strip(" |"), stmt, "", pid(f"L{x}")]); n["members"] += 1
        rp = os.path.join(d, f"S3-RETURN-{tag}.md")
        if not os.path.exists(rp): continue
        t = open(rp, encoding="utf-8").read()
        p1 = re.search(r"(?ms)^## 1\. La epizodoj\s*$(.*?)(?=^## 2\.|\Z)", t)
        p2 = re.search(r"(?ms)^## 2\. La grupoj\s*$(.*?)(?=^## 3\.|\Z)", t)
        for m in re.finditer(r"(?m)^(G\d+): (.*)$", p2.group(1) if p2 else ""):
            ls = sorted({int(x) for x in re.findall(r"\bL(\d+)\b", m.group(2))})
            st = (re.search(r"\b(asertita|konfirmita|kontestita|refutita|probabla)\b", m.group(2)) or [None, ""])[1]
            n["groups"] += 1
            for x in ls: Gw.writerow([pid(m.group(1)), "reader", "", "", m.group(2), st, pid(f"L{x}")]); n["members"] += 1
        for m in re.finditer(r"(?m)^(E\d+): (.*)$", p1.group(1) if p1 else ""):
            ps = m.group(2).split(" · ")
            title = ps[0].strip(); date = ps[1].strip() if len(ps) > 1 else ""
            mem = ps[2] if len(ps) > 2 else ""
            circ = " · ".join(ps[3:])
            gids = [pid(x) for x in re.findall(r"\b([GUSR]\d+)\b", mem)]
            facts = [pid(f"L{x}") for x in sorted({int(x) for x in re.findall(r"\bL(\d+)\b", circ)})]
            see = [pid(x) for x in re.findall(r"\b(E\d+)\b", circ) if x != m.group(1)]
            E.writerow([pid(m.group(1)), title, date, " ".join(gids), " ".join(facts), circ, " ".join(dict.fromkeys(see))]); n["episodes"] += 1
    S = csv.writer(open(os.path.join(out, "sources.csv"), "w", encoding="utf-8", newline=""))
    S.writerow(["siglum", "entry", "in_copyright"])
    # a periodical running past 1930 is «no» for its issues to 1930 and «ask» after: «partly»
    for s in sorted(sig_used): S.writerow([s, entries.get(s, ""), next(iter(sig_used[s])) if len(sig_used[s]) == 1 else "partly (no to 1930, ask after)"])
    print(f"{os.path.relpath(out, G)}: {len(stems)} people; {n['facts']:,} facts ({n['withheld']:,} anchors withheld); "
          f"{n['groups']:,} groups, {n['members']:,} memberships; {n['episodes']:,} episodes; {len(sig_used)} sigla "
          f"({sum(1 for v in sig_used.values() if v == {'no'})} wholly out of copyright)")


def main():
    a = sys.argv[1:]
    if len(a) < 3 or a[0] != "tables": sys.exit(__doc__)
    tag, ver = a[1], a[2]
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(G, "prosopografio-eldono", ver)
    skip = a[a.index("--skip") + 1:] if "--skip" in a else []
    skip = [s for s in skip if not s.startswith("--")]
    tables(tag, ver, out, skip, "--replace" in a)


if __name__ == "__main__":
    main()
