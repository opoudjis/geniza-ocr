#!/usr/bin/env python3
r"""fact-groups.py — group a person's fact lines that tell the same fact, by their event kinds (facts format 4).

Why (2026-10-13): the editor approved two levels of grouping, «fact groups» by tool for deduplication and «episodes» by
a reader for the biography (geniza/dowse/event-kinds-trial-2026-10-13/REPORT.md § 5, approved). This is the tool
level. It reads the kinds the facts lines carry (geniza/profiles/build/FACTS-LIST.tsv, column «kind», written by
tools/harvest-facts.py from format-4 files) and groups two lines when they have
  - the same person,
  - the same kind (the list: geniza/ocr/method/EVENT-KINDS-PROPOSAL-2026-10-13.md, «The list in force»),
  - the same object (case and spacing folded),
  - compatible dates (tools/date_vocab.py's compatible(): the ranges overlap, «about» widened by one unit).
«alia» and «samnomo» are never grouped; a line also joins the groups of a second kind that carries an object
(«+ofico: …»). An undated line joins a group only when its kind and object have exactly one dated group (or
none: the undated lines together), so an undated line never chains a 1900 line to a 1910 one (round 2 of the trial).
From the trial script geniza/dowse/event-kinds-trial-2026-10-13/kind_group.py, which read readers' tables instead.

    python3 tools/fact-groups.py [--person NAME] [--out FILE] [--min 2] [--list FACTS-LIST.tsv] [--match entity|object]

Since 2026-10-14 the default is --match entity (signed off; the editor): see ⇒ THE ENTITY MATCH below and
geniza/ocr/method/SMELT-GROUPING-PROPOSAL-2026-10-14.md. The description above is --match object.

Prints the groups of two or more lines, by person, or writes them to --out (a new file only: it refuses to overwrite).
Write-set: --out only. Lines without a kind (formats 2 and 3) are counted and left out."""
import argparse, csv, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import date_vocab

GEN = os.path.join(os.path.dirname(HERE), "published", "heterophony-resources", "geniza")
LIST = os.path.join(GEN, "profiles", "build", "FACTS-LIST.tsv")


def norm_object(obj):
    """Reasonable normalisation of an object (the editor 2026-10-13): hyphens
    and punctuation folded, case kept («Ido-Akademio» = «Ido Akademio»), years dropped (no date in an object: a date is never an object), spaces collapsed."""
    o = obj        # case kept (the editor 2026-10-13)
    o = re.sub(r"\b1[6-9]\d\d\b|\b20\d\d\b", " ", o)
    o = re.sub(r"[^\w]+", " ", o)
    return re.sub(r"\s+", " ", o).strip()


def split_kind(k):
    """«kind: object; +second; propono: …» -> (kind, normalised object)."""
    head = k.split(";")[0]
    kind, _, obj = head.partition(":")
    return kind.strip(), norm_object(obj)


def seconds(k):
    """The second kinds that carry an object, «+ofico: membro, Lingva Komitato, eksigita» -> [(kind, object)]: a line
    joins the groups of its second kind too (the editor 2026-10-13, on being struck off a body: «both»)."""
    out = []
    for x in k.split(";")[1:]:
        x = x.strip()
        if x.startswith("+") and ":" in x:
            kind, _, obj = x[1:].partition(":")
            out.append((kind.strip(), norm_object(obj)))
    return out


def date_of(field):
    """The line's date as a date_vocab Date, or None when undated or outside the vocabulary (a guess is not a date)."""
    f = field.strip().strip("*")
    if not f or "sen dato" in f or "ĝenerala" in f:
        return None
    try:
        d = date_vocab.parse(f)
    except ValueError:
        return None
    return None if d.kind in ("none", "general") else d


def groups(rows):
    """rows: [(person, file, date field, kind field, line)] -> [(person, kind, object, [rows])], groups of every size."""
    buckets = defaultdict(list)
    for r in rows:
        for kind, obj in [split_kind(r[3])] + seconds(r[3]):
            if kind and kind not in ("alia", "samnomo"):
                buckets[(r[0], kind, obj)].append(r)
    out = []
    for (who, kind, obj), rs in buckets.items():
        dated = [(r, date_of(r[2])) for r in rs]
        undated = [r for r, d in dated if d is None]
        dated = [(r, d) for r, d in dated if d is not None]
        parent = list(range(len(dated)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]; i = parent[i]
            return i
        for i in range(len(dated)):
            for j in range(i + 1, len(dated)):
                if date_vocab.compatible(dated[i][1], dated[j][1]):
                    parent[find(i)] = find(j)
        clusters = defaultdict(list)
        for i, (r, d) in enumerate(dated):
            clusters[find(i)].append(r)
        cl = list(clusters.values())
        if len(cl) == 1:
            cl[0] += undated
        elif not cl:
            cl = [undated]
        else:
            cl += [[r] for r in undated]
        out += [(who, kind, obj, c) for c in cl if c]
    return out

# THE ENTITY MATCH, PROPOSED 2026-10-14 (the smelt trial, smelt/TRIAL-2026-10-14.md; the editor
#). With --match
# entity: for the kinds whose object is a named thing, two lines match on the object's head (to its first «,» or «:»),
# a name in it made canonical (case, diacritics, the harvest's aliases; an unqualified surname takes the only qualifier
# the person's lines use for it); the other kinds keep the whole object. Every pair in a group has overlapping dates
# (no chaining). A line whose whole object agrees with a group of two or more but whose date does not is NOMINATED as a
# possible date error of that group, not merged.
ENTITY = {"renkonto", "konflikto", "interkonsento", "fondo", "verko", "anonco", "kongreso", "aliĝo", "foriro",
          "vojaĝo", "influo", "atestaĵo", "honoro", "memorigo", "postmorto", "propagando", "loĝado"}
_HF = []
def _hf():
    if not _HF:
        import importlib.util
        spec = importlib.util.spec_from_file_location("hf", os.path.join(HERE, "harvest-facts.py"))
        m = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(m); sys.argv = saved
        _HF.append(m)
    return _HF[0]

def head_of(obj):
    """-> (canonical key of the object's head, its qualifier or None)."""
    h = re.split(r"[,:]", obj, maxsplit=1)[0].strip()
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", h)
    name, q = (m.group(1), m.group(2).strip()) if m else (h, None)
    hf = _hf()
    key = hf.slug(hf.canon(name.upper())) if name else ""
    # a head in another script (a Cyrillic title) slugs to nothing, and every such title shared one key «»: different
    # works in one bucket, a group or a single shown with another line's object (2026-10-18, T15, de-beaufront-F52:
    # «Сущность и будущее …» shown as «Изъ путевого дневника»); such a head keys on itself, lowercased
    if name and not re.search(r"[a-z0-9]", key):
        key = re.sub(r"\s+", " ", name.strip().lower())
    return key, q

def groups_entity(rows, corpus=None):
    """--match entity: -> (groups [(person, kind, key, [rows])], nominations [(person, kind, key, group rows, line)]).
    corpus: every line with a kind, all persons, for the qualifiers a surname takes anywhere (default: rows).
    The relational near-matches are left in CANDIDATES."""
    CANDIDATES.clear(); YEAR_EDGE.clear()
    quals = defaultdict(set)             # a surname's qualifiers across all sources (the editor: «named in other sources
    for r in (corpus or rows):            # as candidates»): a bare surname reconciles only when the corpus has one bearer
        for part in [r[3].split(";")[0]] + [x.strip()[1:] for x in r[3].split(";")[1:] if x.strip().startswith("+")]:
            k, _, o = part.partition(":"); key, q = head_of(o)
            if q: quals[key].add(q)
    def key_of(who, kind, obj):
        if kind not in ENTITY: return norm_object(obj)
        key, q = head_of(obj)
        if q is None and len(quals[key]) == 1: q = next(iter(quals[key]))
        rest = re.split(r"[,:]", obj, maxsplit=1)[1] if re.search(r"[,:]", obj) else ""
        # a relational kind keys on the head alone; its rest (the occasion and its description) is matched fuzzily inside
        # the bucket (rel_clusters; the editor, 14:4x
        #). A work keeps its numbers (the «Bibliografio» parts of Progreso I.12, II.14 …
        # are separate works; round 2 of the check)
        if kind in RELATIONAL: return f"{key}|{q or ''}"
        if kind == "verko":
            nums = re.findall(r"\b[IVXLC]+\.\s*\d+(?:[–-]\d+)?\b|\b\d+[a-z]?\b", rest)
            return f"{key}|{q or ''}|{' '.join(nums)}" if nums else f"{key}|{q or ''}"
        return f"{key}|{q or ''}"
    buckets = defaultdict(list)
    for r in rows:
        if "diferenco inter la kopioj" in r[4]: continue      # about the editions, not the person (round 2)
        parts = [r[3].split(";")[0]] + [x.strip()[1:] for x in r[3].split(";")[1:] if x.strip().startswith("+") and ":" in x]
        for part in parts:
            kind, _, obj = part.partition(":"); kind = kind.strip()
            if kind and kind not in ("alia", "samnomo"):
                # a refuted claim is never a witness for the fact it denies (round 2 of the check, all three readers:
                # «refutita aserto» grouped with its refutation): it groups only with refuted lines of its object
                ref = " [refutita]" if "(refutita aserto)" in r[4] else ""
                buckets[(r[0], kind, key_of(r[0], kind, obj) + ref)].append((r, norm_object(obj)))
    out, noms = [], []
    for (who, kind, key), rs in buckets.items():
        if kind in RELATIONAL:
            gs, cs = rel_clusters(rs)
            out += [(who, kind, key, c) for c in gs]
            CANDIDATES.extend((who, kind, key, a, b) for a, b in cs)
            edge_cands(who, kind, key, gs, cs)
            continue
        # the less precise reconciles with the more precise only when there is one candidate (the editor, 2026-10-14
        # 14:3x
        # the same for a bare name against two qualified ones): the most
        # precise lines are placed first; a vaguer line joins the one cluster it agrees with, a cluster of its own
        # precision first; with two or more candidates it stays apart
        # a real date before a planned one (2026-10-22, the editor: «in grouping facts, a real date always trumps a planned
        # date»): the clusters are founded by attested dates, and a plan («…☞») joins the one it agrees with
        dated = sorted(((r, full, date_of(r[2])) for r, full in rs if date_of(r[2]) is not None), key=lambda x: (x[2].planned, width(x[2])))
        undated = [(r, full) for r, full in rs if date_of(r[2]) is None]
        clusters = []                       # every pair compatible
        for r, full, d in dated:
            fits = [c for c in clusters if all(date_vocab.compatible(d, d2) for _, _, d2 in c)]
            same = [c for c in fits if all(x[2].edtf == d.edtf for x in c)]
            if len(same) == 1: same[0].append((r, full, d))
            elif len(fits) == 1: fits[0].append((r, full, d))
            else: clusters.append([(r, full, d)])
        # nominations: a single line whose whole object is that of a larger cluster with other dates
        for c in clusters:
            if len(c) != 1: continue
            r, full, d = c[0]
            big = [c2 for c2 in clusters if c2 is not c and len(c2) >= 2 and any(f2 == full for _, f2, _ in c2)]
            for c2 in big: noms.append((who, kind, key, [x[0] for x in c2], r))
        # an undated line joins a cluster only where a member has its whole object (round 2: undated lines attached to
        # whatever the head matched); else the undated lines of one whole object stay together, apart
        cl = [[x[0] for x in c] for c in clusters]
        fulls = [{x[1] for x in c} for c in clusters]
        rest = defaultdict(list)
        for r, full in undated:
            hit = [i for i, f in enumerate(fulls) if full in f]
            if len(hit) == 1: cl[hit[0]].append(r)
            else: rest[full].append(r)
        cl += list(rest.values())
        # JUDGEMENTS APART BY WHO AND WHEN (2026-10-16; the editor, to Ezri's
        #): the De Beaufront episodes' G19
        # had joined Cart's letter of 1904-02-25 and Waringhien's undated saying, both «al li ĉiuj esperantistoj
        # ŝuldas», by kind and object, and the reader filed the 1904 letter under the judgements after his death. A
        # «juĝo» or «interpreto» group is split by its sayer and its date; the parts become candidates
        if kind in JUDGEMENT:
            split = []
            for c in cl:
                parts = defaultdict(list)
                for r in c: parts[(sayer(r), r[2])].append(r)
                ps = list(parts.values())
                split += ps
                CANDIDATES.extend((who, kind, key, ps[0], p) for p in ps[1:])
            cl = split
        edge_cands(who, kind, key, [c for c in cl if c], [(x[3], x[4]) for x in CANDIDATES if x[:3] == (who, kind, key)])
        out += [(who, kind, key, c) for c in cl if c]
    return out, noms

# A YEAR'S EDGE, THE PROBE (2026-10-16 22:3x; the GROUP-IDS proposal's design rule 2, «proksimumas», accepted 2026-10-15
# for probing with the editor's caution; his approved to three terms): (1) only a bare year
# against a precise date, a day or a month, lying within --year-edge days outside that year (1912-12-13 and 1913), never
# two precise dates (a letter of December 1912 and one of January 1913 may be two letters); (2) a candidate for the
# episode reader, never merged; (3) the probe lists every such pair in full for the editor, who decides whether the rule
# stays. Off by default (0 days): the candidates go to YEAR_EDGE only, which no other tool reads.
YEAR_EDGE_DAYS = 0
YEAR_EDGE = []    # (person, kind, key, lines, lines) of the last groups_entity() call, when YEAR_EDGE_DAYS > 0

def at_year_edge(a, b, days):
    """a is a bare year (a point, not «ĉirkaŭ»), b a day or a month lying within `days` outside it; or the reverse."""
    import datetime
    for y, p in ((a, b), (b, a)):
        if not (y.kind == "point" and y.unit == "year" and not y.approx and p.kind == "point" and p.unit in ("day", "month")
                and y.lo and y.hi and p.lo and p.hi):
            continue
        ylo, yhi = datetime.date.fromisoformat(y.lo), datetime.date.fromisoformat(y.hi)
        plo, phi = datetime.date.fromisoformat(p.lo), datetime.date.fromisoformat(p.hi)
        if phi < ylo and (ylo - phi).days <= days: return True
        if plo > yhi and (plo - yhi).days <= days: return True
    return False

def edge_cands(who, kind, key, clusters, already):
    """Pairs of clusters of one bucket that a year's edge joins, not already candidates of each other."""
    if YEAR_EDGE_DAYS <= 0: return
    seen = {(id(a), id(b)) for a, b in already} | {(id(b), id(a)) for a, b in already}
    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            ci, cj = clusters[i], clusters[j]
            if (id(ci), id(cj)) in seen: continue
            if any((da := date_of(x[2])) and (db := date_of(y[2])) and at_year_edge(da, db, YEAR_EDGE_DAYS)
                   for x in ci for y in cj):
                YEAR_EDGE.append((who, kind, key, ci, cj))

JUDGEMENT = {"juĝo", "interpreto"}

def sayer(r):
    """Who says a judgement line: the source it is derived from («derivita ↤ X», up to the first comma), else the item
    the line cites, with the contributor of a collective volume («(kontribuo de X)»)."""
    line = r[4]
    m = re.search(r"derivita(?:, fonto nevidita)? ↤ ([^,;)]+)", line)
    if m: return m.group(1).strip().lower()
    it = re.search(r" · ([\w.-]+), (?:PDF|¶|p\.|pĝ|l\.)", line)
    ct = re.search(r"⟦kontribuo: ([^⟧]+)⟧", line) or re.search(r"\(kontribuo de ([^)]+)\)", line)   # the label from 2026-10-17
    return f"{it.group(1) if it else '?'}|{ct.group(1) if ct else ''}"

RELATIONAL = {"renkonto", "konflikto", "interkonsento", "influo"}
CANDIDATES = []   # the relational near-matches of the last groups_entity() call, for the episode reader: (person, kind, key, lines, lines)
# words that say what kind of contact, not which one: shared by two different letters, they prove nothing
GENERIC = {"letero", "leteroj", "letera", "korespondado", "korespondaĵo", "kontakto", "rilato", "rilatoj", "renkonto",
           "renkontiĝo", "konversacio", "vizito", "konflikto", "malpaco", "kverelo", "disputo", "polemiko", "inter",
           "kontraŭ", "pri", "per", "post", "antaŭ", "sian", "siaj", "liaj", "lian", "ilia", "iliaj"}

def rest_words(full):
    """The content words of a relational object after its head, cut to five letters (homaranismo = homaranisma)."""
    rest = re.split(r"[,:]", full, maxsplit=1)[1] if re.search(r"[,:]", full) else ""
    return {w[:5] for w in re.findall(r"[^\W\d_]+", rest.lower()) if len(w) >= 4 and w not in GENERIC}

def rel_clusters(rs):
    """A relational bucket (one person, one kind, one other party): two lines are one occasion when their dates agree
    and their descriptions do: a shared content word, or one of them with none (the less precise reconciles); lines of
    the same exact day always agree. A line joins the one cluster it fits, the most precise lines placed first; with two
    candidates it stays apart (the editor, 14:3x)."""
    items = []
    for r, full in rs:
        d = date_of(r[2])
        items.append((r, rest_words(r[3].split(";")[0].partition(":")[2]), d))   # the object, without «kind:»
    items.sort(key=lambda x: (bool(x[2] and x[2].planned), width(x[2]) if x[2] else 10 ** 8, -len(x[1])))   # a real date first (2026-10-22)
    full = {id(r): norm_object(r[3].split(";")[0].partition(":")[2]) for r, _ in rs}
    def fuzzy(a, b):
        (_, wa, da), (_, wb, db) = a, b
        if da and db and not date_vocab.compatible(da, db): return False
        if da and db and da.unit == "day" and da.edtf == db.edtf: return True
        return not wa or not wb or bool(wa & wb)
    # round 3 of the check (3 of 9 fuzzy groups right; the editor): the tool merges only what is safe,
    # the same exact day or the same whole object with agreeing dates; the fuzzy matches are offered to the episode
    # reader (S3) as candidates, not merged
    def safe(a, b):
        (ra, _, da), (rb, _, db) = a, b
        if da and db and da.unit == "day" and da.edtf == db.edtf: return True
        if da and db and not date_vocab.compatible(da, db): return False
        return full[id(ra)] == full[id(rb)]
    clusters = []
    for it in items:
        fits = [c for c in clusters if all(safe(it, x) for x in c)]
        if len(fits) == 1: fits[0].append(it)
        else: clusters.append([it])
    cands = [(i, j) for i in range(len(clusters)) for j in range(i + 1, len(clusters))
             if all(fuzzy(x, y) for x in clusters[i] for y in clusters[j])]
    groups = [[x[0] for x in c] for c in clusters]
    return groups, [(groups[i], groups[j]) for i, j in cands]

def width(d):
    """A date's span in days (an open range: very wide), for placing the most precise lines first."""
    import datetime
    if not d.lo or not d.hi: return 10 ** 7
    return (datetime.date.fromisoformat(d.hi) - datetime.date.fromisoformat(d.lo)).days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--person")
    ap.add_argument("--out")
    ap.add_argument("--min", type=int, default=2)
    ap.add_argument("--list", default=LIST, help="a FACTS-LIST.tsv to read (default: the harvest's)")
    ap.add_argument("--match", choices=["object", "entity"], default="entity",
                    help="entity (the default, signed off 2026-10-14, ocr/method/SMELT-GROUPING-PROPOSAL-2026-10-14.md): the object's named head, canonical names, dates pairwise, one candidate; object: the whole object, as before")
    ap.add_argument("--year-edge", type=int, default=0, metavar="DAYS",
                    help="the probe of 2026-10-16: list as candidates a bare year and a day or month within DAYS outside it (default 0: off)")
    a = ap.parse_args()
    global YEAR_EDGE_DAYS
    YEAR_EDGE_DAYS = a.year_edge
    if a.out and os.path.exists(a.out):
        sys.exit(f"fact-groups: {a.out} exists; not overwriting it")
    rows, nokind, corpus = [], 0, []
    with open(a.list, encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r.get("kind"): corpus.append((r["person"], r["file"], r["year"], r["kind"], r["line"]))
            if a.person and r["person"] != a.person:
                continue
            if not r.get("kind"):
                nokind += 1; continue
            rows.append((r["person"], r["file"], r["year"], r["kind"], r["line"]))
    noms = []
    if a.match == "entity":
        allg, noms = groups_entity(rows, corpus)
    else:
        allg = groups(rows)
    G = sorted((g for g in allg if len(g[3]) >= a.min), key=lambda g: (g[0], g[1], g[2]))
    L = [f"# Fact groups ({len(rows)} lines with a kind; {nokind} without, left out; groups of {a.min} or more: {len(G)}; match: {a.match})", ""]
    last = None
    for who, kind, obj, rs in G:
        if who != last:
            L += ["", f"## {who}"]; last = who
        L.append(f"- **{kind} / {obj or '-'}**: {len(rs)} lines")
        for r in rs:
            fact = r[4].split(" · ")[1] if " · " in r[4] else r[4]
            mark = "[refutita] " if re.search(r"refutita aserto|\brefutas\b", r[4]) and "(refutita aserto)" in r[4] else ""
            L.append(f"  - {mark}{r[2]} · {fact[:140]} ⟵ `{r[1]}`")
    if noms:
        L += ["", f"## Possible date errors, nominated ({len(noms)}): a line whose whole object is a group's, with another date", ""]
        for who, kind, key, grp, r in noms:
            fact = r[4].split(" · ")[1] if " · " in r[4] else r[4]
            L.append(f"- **{who} · {kind} / {key}**: the group dated {', '.join(sorted({x[2] for x in grp}))} ({len(grp)} lines); "
                     f"this line {r[2]} · {fact[:120]} ⟵ `{r[1]}`")
    if CANDIDATES:
        L += ["", f"## Candidates for the episode reader ({len(CANDIDATES)}): meetings, quarrels, agreements, influences that may be one occasion, not merged", ""]
        for who, kind, key, x, y in CANDIDATES:
            f = lambda r: (r[4].split(" · ")[1] if " · " in r[4] else r[4])[:100]
            L.append(f"- **{who} · {kind} / {key}**: {' | '.join(f'{r[2]} · {f(r)}' for r in x)}  ≈  {' | '.join(f'{r[2]} · {f(r)}' for r in y)}")
    if YEAR_EDGE_DAYS > 0:
        L += ["", f"## Candidates at a year's edge ({len(YEAR_EDGE)}; the probe, --year-edge {YEAR_EDGE_DAYS}): a bare year and a day or month "
              f"within {YEAR_EDGE_DAYS} days outside it, never merged; every line in full", ""]
        for who, kind, key, x, y in YEAR_EDGE:
            L.append(f"- **{who} · {kind} / {key}**")
            L += [f"  - {r[4]} ⟵ `{r[1]}`" for r in x]
            L.append("  - ≈")
            L += [f"  - {r[4]} ⟵ `{r[1]}`" for r in y]
    text = "\n".join(L) + "\n"
    if a.out:
        with open(a.out, "x", encoding="utf-8") as fh:
            fh.write(text)
        print(f"fact-groups: {len(G)} groups → {a.out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
