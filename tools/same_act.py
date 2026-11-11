#!/usr/bin/env python3
"""The same act under different heads (the editor, 2026-11-05; scoped by scratch dispute_test.py, built on his approved 2026-11-06).

    tools/same_act.py [--write]

An act: the facts files' lines alike in kind, object and year. Two or three heads on one act make a pair; more is a shared thing (a congress, a committee), no singular act; so is an
object more than six heads have across the years. A line that names the other head is a shared act: no pair. Each pair is near (the names confusable: a fold's evidence, which
name-fold-candidates.py reads through pairs()) or far (a candidate dispute).
The far pairs are sifted, not cut (the editor: not limited to authorship and founding): A, a singular act (KINDS_ONE) in two sources; B, a singular act in one source; C, another kind in two
sources; D, the rest; T, the two lines at different months or days of the year (times_differ()); I, an indefinite object (definite()), only suggestive; S, a kind shared by nature or an
office of a shared seat (shared(); 2026-11-07); J, last, a line that itself says the work was joint or an occasion (JOINT). It rules on nothing.
--write: profiles/build/SAME-ACT-PAIRS-LATEST.tsv (all), DISPUTE-CANDIDATES-LATEST.md (the far pairs, by class) and FONDO-RULE-LATEST.md (each line the founding rule changes). harvest-chain.py runs it after each harvest."""
import argparse, collections, csv, glob, importlib.util, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
LINE = re.compile(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))? \*\*([^*]*)\*\* · \{([^}]*)\} · ")
KINDS_ONE = {"verko", "fondo", "naskiĝo", "morto", "eltrovo", "invento", "traduko", "projekto", "propono"}
def plain(x): return "".join(c for c in unicodedata.normalize("NFKD", x.lower()) if not unicodedata.combining(c))

# A DEFINITE OBJECT (the editor, 2026-11-06, on Lojko's and Dombrovski's «versaĵoj», 1906
#): a title in «…», or a name: a capital after the object's first word, or a capitalised first word
# with another word beside it that is one too. A lone word, capitalised or not, and a phrase in small letters name a kind of thing, not one thing
def definite(obj):
    obj = obj.strip()
    if re.search(r"«[^»]+»", obj): return True
    w = re.findall(r"[^\W\d_][\w'’-]*", obj)
    return any(x[0].isupper() for x in w[1:])

def tools():
    saved, sys.argv = sys.argv, ["x"]
    out = []
    for name, f in (("harvest_facts", "harvest-facts.py"), ("name_ungarble", "name-ungarble.py")):
        s = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", f)); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); out.append(m)
    sys.argv = saved
    return out

def pairs(HF, NG):
    """Every pair of heads on one act: dicts of kind, object, year, the two heads' slugs and forms, their sources and lines, near."""
    rec = collections.defaultdict(list)
    for f in glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md")):
        src = os.path.basename(f)[:-9]
        for l in open(f, encoding="utf-8", errors="replace"):
            m = LINE.match(l)
            if not m: continue
            y = re.search(r"\b(1[89]\d\d)\b", m.group(3))
            if not y: continue
            ps = l.split(" · ")
            for part in HF.fondo_kind(m.group(4), ps[2] if len(ps) > 2 else "").split(";"):     # the kind as the harvest reads it: a speech is no founding
                part = part.strip().lstrip("+")
                if ":" not in part or part.startswith("kun:"): continue
                k, obj = part.split(":", 1)
                # an illegible place is no shared object (the editor, 2026-11-07 23:1x, on CABEZA / CADENAT)
                if "nelegebl" in plain(obj): continue
                w = re.findall(r"[^\W\d_]{3,}", plain(obj))
                if len(w) < 2 and not (w and len(w[0]) >= 6): continue
                rec[(k.strip(), " ".join(w), y.group(1))].append((HF.slug(HF.canon(m.group(1))), m.group(1), src, l.rstrip("\n"), definite(obj)))
    df = collections.Counter()
    for (k, o, y), v in rec.items(): df[(k, o)] += len({x[0] for x in v})
    def named(a, b): return plain(b[1].split()[-1]) in plain(a[3]) or plain(a[1].split()[-1]) in plain(b[3])
    out = []
    for (k, o, y), v in rec.items():
        hs = {x[0] for x in v}
        if not 2 <= len(hs) <= 3 or df[(k, o)] > 6: continue
        byh = {}
        for x in v: byh.setdefault(x[0], x)
        L = list(byh.values())
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                a, b = L[i], L[j]
                if named(a, b): continue
                near = NG.skeleton(a[0].replace("-", "")) == NG.skeleton(b[0].replace("-", "")) or NG.distance(a[0], b[0], 2) <= 2
                out.append(dict(kind=k, obj=o, year=y, a=a[0], b=b[0], fa=a[1], fb=b[1], sa=a[2], sb=b[2], la=a[3], lb=b[3], near=near, definite=a[4] or b[4]))
    return out

# JOINT WORK IS NO DISPUTE (the editor, 2026-11-06): a line that names co-workers in its
# «kun:», or says so in its fact or quotation, claims no sole act. Its pairs stand in a class of their own, J, last: kept, not cut
JOINT = re.compile(r"\bkaj (?:liaj|lia|ŝiaj|ŝia|siaj|sia|aliaj|kelkaj|pluraj|amikoj|samlandanoj|kolegoj|kunlaborantoj|samideanoj)\b|\bkune kun\b|\bkun (?:siaj|sia|liaj|lia|ŝiaj|ŝia|aliaj|amikoj|la helpo)\b"
                   r"|\bhelpe de\b|\bk\. ?a\.|\bkaj (?:k\. ?)?t\. ?p\.|\bkun(?:labor|fond|redakt|verk|aŭtor|tradu)|\bet al\b|\bavec (?:ses|son|sa|l[ae]s?)\b|\bet (?:ses|son|sa) \b|\bund (?:seine|sein)\b|\bmit (?:seinen|seiner|seinem)\b"
                   r"|\band (?:his|her|their|others|friends)\b|\bwith (?:his|her|friends|others)\b"
                   # an occasion, or nobody's sole act (the editor, on Fromageot, Beaune 1903; Cart and Gehet, Rouen 1904)
                   r"|\boni (?:\w+ )?fond|\bfondi[ĝg]is\b|\bestis fondita\b|\bestas fondita\b|\bper la klopodoj\b|\bdank' ?al\b|\bpost (?:\w+ )?(?:parolado|prelego|konferenco|kurso)\b", re.I)
def joint(l):
    ps = l.split(" · ")
    return "kun:" in (ps[1] if len(ps) > 1 and ps[1].startswith("{") else "") or bool(JOINT.search(" · ".join(ps[2:4] if len(ps) > 3 and ps[1].startswith("{") else ps[1:3])))

# KINDS SHARED BY NATURE (the editor, 2026-11-07 23:5x, on class D's left list:
# to be triaged firmly): many people do such an act at once, so two heads on it are no dispute. «interpreto» joins by the
# historiografio reasoning (Ezri). An office counts here when its seat is shared (a member, a committee, a delegate, a vice- or honorary post); one seat (a president, a secretary …) stays
# Widened 2026-11-08 00:5x (the editor, to the 1,231 left
#): appearing in a list, a congress, a profession, a joining, a
# study, propaganda, a pastime, a journey; a residence when its object is a town, not a street address. Two names at one street address stay: different names clash, near names are
# the near pairs (a fold's evidence); one surname with other forenames, family, is no pair here (the heads are one surname)
SHARED_KINDS = {"aserto", "prelego", "renkonto", "rilato", "deliberado", "historiografio", "honoro", "influo", "interkonsento", "juĝo", "konflikto", "memorigo", "interpreto",
                "aperoj", "kongreso", "profesio", "aliĝo", "studo", "propagando", "distro", "vojaĝo"}
SEAT_SHARED = re.compile(r"(?i)\b(membro|komitat|delegit|honora|vic|kandidat|agent|korespondant|estrar)")
STREET = re.compile(r"(?i)\b(rue|r\.|avenue|av\.|boulevard|bd|place|quai|chaussée|impasse|strasse|straße|str\.|gasse|weg|platz|allee|ring|ulica|ul\.|via|viale|piazza|calle|"
                    r"plaza|rua|street|st\.|road|rd\.|lane|square|terrace|straat|laan|gracht|plein|gatan|gata|vej|gade|tér|utca|út)\b|\d+\s*,|,\s*\d+|n-ro \d+|\d+[a-z]?\s+(rue|r\.)")
def shared(p):
    if p["kind"] == "loĝado":
        return not STREET.search(p["obj"] + " " + fact(p["la"]) + " " + fact(p["lb"]))
    return p["kind"] in SHARED_KINDS or (p["kind"] == "ofico" and bool(SEAT_SHARED.search(p["obj"] + " " + fact(p["la"]) + " " + fact(p["lb"]))))
# DIFFERENT TIMES (the editor, 2026-11-07, on DEGON / DAVALLON
#): the two lines dated to different months or days of the year are two acts, not one: demoted to a class of their own, not cut
def times_differ(p):
    da, db = (re.match(r"- \$\$\$ .+? \$\$\$(?: \([^)]*\))? \*\*([^*]*)\*\*", p[k]) for k in ("la", "lb"))
    da, db = (re.fullmatch(r"\s*(\d{4}-\d\d(?:-\d\d)?)\s*", d.group(1)) if d else None for d in (da, db))
    if not (da and db): return False
    a, b = da.group(1), db.group(1)
    return a[:7] != b[:7] or (len(a) == len(b) == 10 and a != b)

def sift(p):
    # a founding is too collective an act to adjudicate between subjects (the editor, 2026-11-06)
    if p["kind"] == "fondo" or joint(p["la"]) or joint(p["lb"]): return "J"
    if shared(p): return "S"
    if times_differ(p): return "T"
    if not p["definite"]: return "I"
    two = p["sa"] != p["sb"]
    return ("A" if two else "B") if p["kind"] in KINDS_ONE else ("C" if two else "D")

def fact(l):
    ps = l.split(" · ")
    return (ps[2] if len(ps) > 2 and ps[1].startswith("{") else ps[1] if len(ps) > 1 else "")[:110].replace("|", "/")
def where(l):
    ps = l.split(" · ")
    return next((x for x in ps if re.search(r"(?:PDF|¶) \d+", x)), "")[:60].replace("|", "/")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    HF, NG = tools()
    P = pairs(HF, NG)
    far = [p for p in P if not p["near"]]
    c = collections.Counter(sift(p) for p in far)
    print(f"pairs {len(P)}: near {len(P) - len(far)}, far {len(far)}; far by class {sorted(c.items())}")
    print("far by kind:", collections.Counter(p["kind"] for p in far).most_common(14))
    if not a.write: return
    b = os.path.join(G, "profiles", "build")
    with open(os.path.join(b, "SAME-ACT-PAIRS-LATEST.tsv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow("near_or_far class kind object year head_a source_a head_b source_b fact_a fact_b".split())
        for p in sorted(P, key=lambda p: (not p["near"], sift(p), p["kind"], p["year"])):
            w.writerow(["near" if p["near"] else "far", sift(p), p["kind"], p["obj"], p["year"], p["fa"], p["sa"], p["fb"], p["sb"], fact(p["la"]), fact(p["lb"])])
    T = dict(A="A: a singular act, in two sources", B="B: a singular act, in one source", C="C: another kind, in two sources", D="D: the rest", T="T: one kind and object in one year, at different months or days: two acts, no dispute on its face", I="I: an indefinite object, a kind of thing and not one thing: only suggestive", S="S: a kind shared by nature (a lecture, a meeting, an honour, a judgement …; an office of a shared seat): many do it at once, no dispute", J="J: joint work, or an occasion, by the line's own words: no dispute on its face")
    doc = ["# Candidate disputes: the same act under different heads", "",
           "**GENERATED by `tools/same_act.py --write`, after each harvest. Do not edit.** Lines alike in kind, object and year, under heads whose names are not confusable, neither line naming the other head. A candidate only: two people may truly have done it, or the kind's object may be too general. It rules on nothing; sifted, not cut.", "",
           f"{len(far)} pairs: " + ", ".join(f"{T[k].split(':')[0]} {c[k]}" for k in "ABCDTISJ") + ". Two people on one act are often simply joint work where neither line says so; a real dispute needs a line that gives it to one alone, or denies the other. The near pairs, evidence for a fold, are in `SAME-ACT-PAIRS-LATEST.tsv` and in the fold's second score.", ""]
    for k in "ABCDTISJ":
        rows = sorted((p for p in far if sift(p) == k), key=lambda p: (p["kind"], p["year"], p["obj"]))
        doc += [f"## {T[k]} ({len(rows)})", "", "| kind | object | year | one says | where | another says | where |", "|---|---|---|---|---|---|---|"]
        doc += [f"| {p['kind']} | {p['obj'][:40]} | {p['year']} | **{p['fa']}**: {fact(p['la'])} | {where(p['la'])} | **{p['fb']}**: {fact(p['lb'])} | {where(p['lb'])} |" for p in rows] + [""]
    open(os.path.join(b, "DISPUTE-CANDIDATES-LATEST.md"), "w", encoding="utf-8").write("\n".join(doc))
    print("wrote profiles/build/SAME-ACT-PAIRS-LATEST.tsv and DISPUTE-CANDIDATES-LATEST.md")
    # the founding rule's changes, each listed, for the editor's eye (harvest-facts.py, fondo_kind)
    ch = []
    for f in sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md"))):
        for l in open(f, encoding="utf-8", errors="replace"):
            m = LINE.match(l)
            if not m or "fondo" not in m.group(4): continue
            ps = l.split(" · "); k1 = HF.fondo_kind(m.group(4), ps[2] if len(ps) > 2 else "")
            if k1 != m.group(4): ch.append(("a plan" if "planita" in k1 else "a talk" if "prelego" in k1 else "off", m.group(1), m.group(4), k1, fact(l), where(l)))
    n = collections.Counter(x[0] for x in ch)
    doc = ["# The founding rule: the lines it changes", "", "**GENERATED by `tools/same_act.py --write`, after each harvest. Do not edit.** The kind as the harvest reads it (`harvest-facts.py`, `fondo_kind`; the editor, 2026-11-06: a speech is no founding; agency keeps `fondo`; a wish is a plan; a founding with no link to the head is not his). The facts files keep the reader's kind.", "", f"{len(ch)} lines: " + ", ".join(f"{k} {v}" for k, v in sorted(n.items())) + ".", ""]
    for k in ("a talk", "a plan", "off"):
        doc += [f"## {k} ({n[k]})", "", "| head | the reader's kind | as read now | the fact | where |", "|---|---|---|---|---|"]
        doc += [f"| {x[1]} | {x[2][:60].replace('|', '/')} | {x[3][:60].replace('|', '/')} | {x[4]} | {x[5]} |" for x in sorted(ch, key=lambda z: z[1]) if x[0] == k] + [""]
    open(os.path.join(b, "FONDO-RULE-LATEST.md"), "w", encoding="utf-8").write("\n".join(doc))
    print(f"wrote profiles/build/FONDO-RULE-LATEST.md: {len(ch)} lines, {dict(n)}")

if __name__ == "__main__":
    main()
