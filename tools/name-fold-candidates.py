#!/usr/bin/env python3
"""Two spellings, one person? Every head against every head, on the roster or not (2026-11-05; the editor, on DRAGOUMIS ~ DRAGUMIS, two
profiles the fold scoring never compared, since it stops at a name the roster holds and the roster is built from the profiles).

    tools/name-fold-candidates.py [--min-lines N] [--write]

A candidate: two heads with two profiles of their own (the harvest's canon and slug), without a qualifier, one letter apart (six letters or
more), or with the same transliteration key. Left out: a pair the names register already joins, and a pair in profiles/FOLD-RULINGS.tsv
(a, b, same|two, who, date, why), so a ruling is asked once. It proposes; it folds nothing. A ruling «same» goes into the register.

Each pair: the spelling, by name-ungarble.py's score_one and the editor's weights, the smaller as the name read; and the evidence that it is
one person, from the two heads' lines in the facts files:
  given names   line by line (2026-11-05; a head is a surname, so it can hold several people: JONSON holds a Birger and an E.): the capitalised word
                set before the surname in each line's fact and quotation, an ordinary word left out, kept apart by person within each head. The verdict:
                same (every person of the smaller is in the target, and the target is one person), same, initial only; several (the smaller's person is
                there, but the target also holds others, so the head cannot fold whole); partly (only some of the smaller's); differ (none; a family's men
                share a surname); none (one side names no given name). Johano ~ Jean is not seen: it reads «differ», for a reader;
  rare words    words of ours in the kinds' objects that few heads share (Lingva Komitato; loĝado's places, Ateno): shared ones count for;
  years         lines more than 40 years apart count against;
  one line      a line under one head whose kind names the other counts against: two people.
WHICH IS THE TARGET (the editor, 2026-11-05, on RAYCHETT ~ RAYCHETR, 1 line each): by lines, but where both sides have five lines or fewer, by plausibility: a form the
phonotactic tests refuse (implausible(), hard_cluster(); Slavic endings spared, as in score_one) ranks lowest, a Wikidata surname highest. A target those tests refuse flips to a plausible
partner at any size up to five times the partner's lines. Each flip is scored afresh.
CHAINS: a pair is scored alone, so the target's own target is followed here, through the pairs at the bar, to its end; an end the tests refuse is marked, with the best plausible head within
two letters if one reaches the bar (the editor, on RÔANISCN ~ RÔUNISCN). The chain is only shown: nothing folds.
TWO CLASSES APART, neither scored: a given name and one letter (OLGA E.: the «surname» is an initial, to join a full surname, as the initials pass does; FOLD-INITIAL-SURNAMES-LATEST.md);
and a closing LL, LI, IL, II (PEDRO LI: by default the Roman numeral, so PEDRO II, whatever the lines).
A: spelling and evidence for, no evidence against. B: the rest, to read. C: evidence against. Sorted by the smaller's lines.
--write: profiles/build/FOLD-CANDIDATES-LATEST.md (the pairs at --min-lines, default 3) and .tsv (all), and FOLD-SCORED-LATEST.md, every pair at the
editor's bar of +1 by the spelling's score alone (the given names do not enter the score: their weight would be his to set). harvest-chain.py runs it after each harvest."""
import argparse, collections, csv, glob, importlib.util, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
saved, sys.argv = sys.argv, ["x"]
_s = importlib.util.spec_from_file_location("name_ungarble", os.path.join(ROOT, "tools", "name-ungarble.py")); NG = importlib.util.module_from_spec(_s); _s.loader.exec_module(NG)
_s = importlib.util.spec_from_file_location("harvest_facts", os.path.join(ROOT, "tools", "harvest-facts.py")); HF = importlib.util.module_from_spec(_s); _s.loader.exec_module(HF)
sys.argv = saved
HEAD = re.compile(r"- \$\$\$ (.+?) \$\$\$(?: \(([^)]*)\))?")
STOP = set("membro prezidanto sekretario kasisto redaktoro esperanto esperantisto esperantista grupo societo klubo kongreso letero artikolo verko aliĝo adresaro numero "
           "universala internacia lingvo lingva unua dua tria nova kurso prelego prezidanto vicprezidanto".split()) | set("planita aperoj".split())
TITLES = set("doktoro profesoro prof kapitano kolonelo generalo pastro abato kanoniko sinjoro sinjorino fraulino grafo barono juĝisto advokato inĝeniero leŭtenanto majoro mister sro dro mr mrs "
             "la le de du van von kaj lau en pro al ke por ĉe kun el pri post antau dum sed ankau d s mlle mme mlles melle melles dlo herr frau fru fraulein hr miss monsieur madame".split())
def plain(s): return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))

def read_heads():
    """slug -> a dict of the head's forms, lines, years, given names and object words."""
    H = collections.defaultdict(lambda: dict(forms=collections.Counter(), n=0, years=[], given=collections.Counter(), words=collections.Counter(), files=set(), names=set()))
    low = collections.Counter()     # words our facts write in small letters: an ordinary word, no given name (Kiam, Sed, Ankaŭ at a sentence's head)
    for f in glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md")):
        for l in open(f, encoding="utf-8", errors="replace"):
            m = HEAD.match(l)
            if not m or m.group(2): continue
            name = m.group(1).strip(); s = HF.slug(HF.canon(name))
            h = H[s]; h["forms"][name] += 1; h["n"] += 1; h["files"].add(os.path.basename(f))
            ps = l.rstrip("\n").split(" · ")
            d = re.search(r"\*\*([^*]*)\*\*", ps[0]); h["years"] += [int(y) for y in re.findall(r"\b(1[89]\d\d)\b", d.group(1))] if d else []
            k = ps[1] if len(ps) > 1 and ps[1].startswith("{") else ""
            for w in re.findall(r"[^\W\d_]{5,}", plain(k)):
                if w not in STOP: h["words"][w] += 1
            fact = " · ".join(ps[2:4] if k else ps[1:3])     # the fact and its quotation
            low.update(plain(w) for w in re.findall(r"(?<![^\W\d_])[a-zà-ÿĉĝĥĵŝŭ]{2,}", fact))
            seen, own = set(), {plain(q) for q in re.split(r"[\s\-]+", name)}     # a head's own word is no evidence (PEDRO, of PEDRO II)
            for g in re.findall(r"((?:[A-ZÀ-ÝĈĜĤĴŜŬ][\w.'’-]*\.?\s+){1,4})(?i:" + re.escape(name.split()[-1]) + r")(?![^\W\d_])", fact):
                for w in g.split():
                    w = w.strip(".").split(".")[0]     # M.L: M
                    if "-" in w and re.search(r"-(?:ro|ron|roj|rojn|ino|inon|inoj|inojn|rino|ano|ra)$", w, re.I): continue     # S-ro, D-ro, F-ino, F-inoj
                    if re.search(r"['’\d]", w) or (w.isupper() and len(w) > 2) or re.search(r"-[A-Za-z]?[oa]$|(?:ujo|lando)$", w): continue     # S'o, D'o, S0, Al-So; XVINA, a numeral or a name in a list; Rusujo
                    if w == "M": continue     # M.: Monsieur, far oftener than an initial, so it proves nothing
                    if plain(w) not in TITLES and plain(w) not in own: seen.add(w); break     # the first name of the line's mention, not «Ivanoviĉ»
            for w in seen: h["given"][w] += 1     # lines, not mentions
            # who the line's kind names besides its head: both spellings in one line are two people
            h["names"] |= {x.strip() for x in re.findall(r"[A-ZÀ-ÝĈĜĤĴŜŬ][A-ZÀ-ÝĈĜĤĴŜŬ'’\- ]{3,}", k)}
    for h in H.values():
        for w in list(h["given"]):
            if low[plain(w)] >= 3 or plain(w) in H and H[plain(w)]["n"] >= 50: del h["given"][w]     # an ordinary word; another big head
    return H

# THE SECOND SCORE (the editor, 2026-11-05, on the same acts
#): the given names and the same acts, beside the spelling's and never added to it. The weights by Ezri, the editor 2026-11-06.
SECOND_GIVEN = {"same": 2, "same, initial only": 1, "partly": 0.5, "none": 0, "differ": -1}
SECOND_ACT, SECOND_ACT_INDEF, SECOND_ACTS_CAP, SECOND_AGAINST = 1, 0.25, 3, 2     # each same act, up to three in all; an indefinite object only suggestive (the editor, 2026-11-06, on); lines forty years apart, or a line naming both
def second_given(gv, a, b):
    """«several» by whom the smaller matches: the target's main person with three quarters of its lines or more, as good as «same» (the others mostly garble and places: OREŜKOV's
    «Plovdiv»); its main person in a truly mixed head, +1; a minority person, +0.5."""
    if gv != "several": return SECOND_GIVEN[gv]
    B = people(b); top, tn = max(B, key=lambda q: q[1])
    if not any(same_given(w, top) for w, _ in people(a)): return 0.5
    return 2 if tn >= 0.75 * sum(v for _, v in B) else 1

def one_letter(f): return bool(re.fullmatch(r".+\s[^\W\d_]\.?", f))
def numeral(f):
    """A closing LL, LI, IL, II, a Roman numeral by default: the form as II, else None."""
    w = f.split()
    return " ".join(w[:-1] + [w[-1].replace("L", "I").replace("1", "I")]) if len(w) >= 2 and re.fullmatch(r"[IL1]{2,4}", w[-1]) else None
def refused(f, attest=None):
    """The phonotactic tests, Slavic endings spared as in score_one, and a Wikidata surname (KORNFELD: the tests refuse its «rnf»)."""
    if NG.implausible(f): return True
    if attest is not None and NG.compact(f.split()[-1]) in attest: return False
    return bool(NG.hard_cluster(f)) and not re.search(r"([iy][cćĉč]|ov|ev|in|ski|skij|sky|enko|vi[cćĉč]|ova|eva|ina|aja)$|[ĉĝĵŝŭžšćč]", f.lower())
def rank(f, attest):
    if refused(f, attest): return 0
    return 2 if attest is not None and NG.compact(f.split()[-1]) in attest else 1

def same_given(x, y):
    """Can two given names be one person? «full», «initial», or None. X ~ KS, and the first four letters (Aleksandro ~ Aleksander)."""
    a, b = plain(x).replace("x", "ks").strip("'’"), plain(y).replace("x", "ks").strip("'’")
    if not a or not b: return None
    if len(a) == 1 or len(b) == 1: return "initial" if a[0] == b[0] else None
    return "full" if a == b or a[:4] == b[:4] or (min(len(a), len(b)) >= 5 and NG.distance(a, b, 1) <= 1) else None     # Dominico ~ Domenico

def people(c):
    """A head's given names, as people: [[name, lines]], the commonest first; an initial or a variant joins the commonest it can be."""
    out = []
    for w, v in sorted(c.items(), key=lambda kv: (len(kv[0].strip(".")) <= 1, -kv[1], kv[0])):
        for p in out:
            if same_given(w, p[0]): p[1] += v; break
        else: out.append([w, v])
    return out

def given_verdict(a, b):
    """The smaller's given names against the target's: (same | same, initial only | several | partly | differ | none, the names as read)."""
    A, B = people(a), people(b)
    show = lambda P: ", ".join(f"{w} {v}" for w, v in P[:4]) + (f", +{len(P) - 4}" if len(P) > 4 else "")
    text = f"{show(A) or '-'} ~ {show(B) or '-'}"
    if not A or not B: return "none", text
    how = [max((same_given(w, q[0]) or "" for q in B), key=len) for w, _ in A]
    if not any(how): return "differ", text
    if not all(how): return "partly", text
    if len(B) > 1: return "several", text
    return ("same" if "full" in how else "same, initial only"), text

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-lines", type=int, default=3); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    H = read_heads()
    prof = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(G, "profiles", "*.md"))}
    H = {s: h for s, h in H.items() if s in prof and re.fullmatch(r"[a-z\-]+", s) and len(s) >= 4}
    form = {s: h["forms"].most_common(1)[0][0] for s, h in H.items()}
    df = collections.Counter(w for h in H.values() for w in h["words"])
    joined = set()
    with open(os.path.join(G, "profiles", "NAMES-REGISTER.tsv"), encoding="utf-8") as fh:
        for r in csv.reader((l for l in fh if not l.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(r) > 3 and r[0] != "name":
                names = [HF.slug(HF.canon(x.strip())) for x in r[:3] if x.strip()]
                joined |= {frozenset((x, y)) for x in names for y in names if x != y}
    ruled = {}
    rp = os.path.join(G, "profiles", "FOLD-RULINGS.tsv")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as fh:
            for r in csv.reader((l for l in fh if not l.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(r) > 2: ruled[frozenset((r[0], r[1]))] = r[2]
    buckets, keys = collections.defaultdict(set), collections.defaultdict(set)
    for s in H:
        if len(s) >= 6:
            for i in range(len(s)): buckets[s[:i] + "*" + s[i + 1:]].add(s)
            for i in range(len(s) + 1): buckets[s[:i] + "*" + s[i:]].add(s)
        keys[NG.skeleton(s.replace("-", ""))].add(s)
    pairs = set()
    for grp in list(buckets.values()) + list(keys.values()):
        if 1 < len(grp) < 40: pairs |= {frozenset((x, y)) for x in grp for y in grp if x != y}
    apart = {s for s, f in form.items() if one_letter(f) or numeral(f)}
    pairs = [p for p in pairs if p not in joined and p not in ruled and not p & apart]
    rost = sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")))[-1]
    onr = {x.strip().lower() for l in open(rost, encoding="utf-8") for x in l.split("|")}
    attest = NG.surnames() if NG.SURNAMES else None
    # the corpus items a name stands in, for A8, as the ungarbler loads them before it scores (without them A8 never fired here)
    NG.LEXN = NG.lexicon_items({NG.fold(w).lower() for s in form.values() for w in re.findall(r"[^\W\d_]+", s)})
    code = {"a one-letter change in a name of five letters or fewer": "A1", "the first letter added or dropped, title case to title case": "A2", "the name as read is a surname in Wikidata": "A3",
            "the name as read stands in five corpus items or more, not in Wikidata": "A8", "the OCR added a letter at the start or end": "A5", "the distance over the length is past MAX_RATIO": "A4",
            "a feminine form beside the masculine": "A6", "the target is on the roster, the name is not": "F1", "the target heads five times the lines or more": "F2", "a known transliteration": "F3",
            "every letter changed is a known OCR confusion": "F4", "only a space differs": "F5", "the name has impossible clusters": "F6", "the name has an X in it": "F7",
            "F4 at 30% or more of the wrong readings: F4 counts +2": "F9", "F4 between 10% and 30% of the wrong readings: F4 counts +1.5": "F10", "F4 at 10% or under of the wrong readings: F4 counts +1": "F11"}
    # the same acts (tools/same_act.py): for the second score, beside the spelling's and never added to it (the editor, 2026-11-05)
    _s = importlib.util.spec_from_file_location("same_act", os.path.join(ROOT, "tools", "same_act.py")); SA = importlib.util.module_from_spec(_s); _s.loader.exec_module(SA)
    acts = collections.defaultdict(list)
    for q in SA.pairs(HF, NG): acts[frozenset((q["a"], q["b"]))].append(q)
    rows = []
    for p in pairs:
        x, y = sorted(p, key=lambda s: (H[s]["n"], rank(form[s], attest)))      # x the smaller, the name as read
        rx, ry = rank(form[x], attest), rank(form[y], attest)
        flip = (H[x]["n"] <= 5 and H[y]["n"] <= 5 and rx > ry) or (ry == 0 and rx > 0 and H[y]["n"] <= 5 * H[x]["n"])
        if flip: x, y = y, x
        hx, hy = H[x], H[y]
        try: sc, feats = NG.score_one(form[x], hx["n"], form[y], hy["n"], x in onr, y in onr, attest, [], NG.WEIGHTS)[:2]
        except Exception: sc, feats = 0, []
        gv, gtext = given_verdict(hx["given"], hy["given"])
        own = {plain(w) for f_ in (form[x], form[y]) for w in re.split(r"[\s\-]+", f_)}     # their own names in a kind are no evidence
        shared = sorted((w for w in set(hx["words"]) & set(hy["words"]) if df[w] <= 60 and w not in own), key=lambda w: df[w])
        gap = None
        if hx["years"] and hy["years"]:
            gap = max(0, min(hx["years"]) - max(hy["years"]), min(hy["years"]) - max(hx["years"]))
        against = []
        if gv == "differ": against.append("given names differ")
        if gap and gap > 40: against.append(f"{gap} years apart")
        if form[y] in hx["names"] or form[x] in hy["names"]: against.append("one names the other in a line")
        forw = []
        if gv in ("same", "same, initial only", "several"): forw.append("given names agree")
        if shared: forw.append("shared: " + ", ".join(shared[:5]))
        cls = "C" if against else "A" if sc >= 0 and forw else "B"
        same = acts.get(p, [])
        second = second_given(gv, hx["given"], hy["given"]) + min(sum(SECOND_ACT if q["definite"] else SECOND_ACT_INDEF for q in same), SECOND_ACTS_CAP) - sum(SECOND_AGAINST for q in against if not q.startswith("given"))
        why = "; ".join(f"{q['kind']}: {q['obj'][:40]}, {q['year']}" for q in same[:3])
        rows.append([cls, min(hx["n"], hy["n"]), form[x], hx["n"], len(hx["files"]), form[y], hy["n"], len(hy["files"]), f"{sc:+.1f}", "; ".join(forw + against), gv, gtext, " ".join(code.get(q, "?") for q in feats), "flipped" if flip else "", "", f"{second:+.1f}", len(same), why])
    rows.sort(key=lambda r: ("ABC".index(r[0]), -r[1]))
    # the chains, through the pairs at the bar: each name's best target, followed to its end
    best = {}
    slug_of = {f: s for s, f in form.items()}
    for r in rows:
        if float(r[8]) >= 1 and (r[2] not in best or (r[6], float(r[8])) > (best[r[2]][6], float(best[r[2]][8]))): best[r[2]] = r     # the bigger target first
    plaus = [s for s in H if not refused(form[s], attest) and s not in apart]
    further = {}
    def beyond(f):
        """The best plausible head within two letters of a form the tests refuse, at the bar."""
        if f in further: return further[f]
        s0, top = slug_of[f], None
        for s in plaus:
            if s[0] == s0[0] and abs(len(s) - len(s0)) <= 2 and s != s0 and NG.distance(s, s0, 2) <= 2:
                try: sc = NG.score_one(f, H[s0]["n"], form[s], H[s]["n"], s0 in onr, s in onr, attest, [], NG.WEIGHTS)[0]
                except Exception: continue
                if sc >= 1 and (top is None or (sc, H[s]["n"]) > top[:2]): top = (sc, H[s]["n"], form[s])
        further[f] = top
        return top
    for r in rows:
        if float(r[8]) < 1: continue
        end, seen = r[5], {r[2]}
        while end in best and end not in seen: seen.add(end); end = best[end][5]
        note = [f"chain: {end}"] if end != r[5] else []
        if refused(end, attest):
            top = beyond(end)
            note.append(f"{end} refused by the tests" + (f"; nearest plausible {top[2]} {top[0]:+.1f}" if top else "; no plausible head near"))
        r[14] = "; ".join(note)
    c = collections.Counter(r[0] for r in rows); big = [r for r in rows if r[1] >= a.min_lines]
    cb = collections.Counter(r[0] for r in big)
    print(f"heads with a profile: {len(H)}; pairs: {len(rows)} (A {c['A']}, B {c['B']}, C {c['C']}); at {a.min_lines}+ lines: {len(big)} (A {cb['A']}, B {cb['B']}, C {cb['C']}); already ruled {len(ruled)}")
    if a.write:
        b = os.path.join(G, "profiles", "build")
        with open(os.path.join(b, "FOLD-CANDIDATES-LATEST.tsv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n"); w.writerow("class smaller_lines name lines files target lines files spelling evidence given given_names features direction chain second same_acts same_act_list".split()); w.writerows(rows)
        doc = ["# Two spellings, one person? The fold candidates", "", "**GENERATED by `tools/name-fold-candidates.py --write`, after each harvest. Do not edit.** It proposes and folds nothing; a ruling goes to `profiles/FOLD-RULINGS.tsv`, a «same» into the names register.", "",
               f"{len(rows)} pairs; at {a.min_lines}+ lines {len(big)}: A (spelling and evidence for) {cb['A']}, B (to read) {cb['B']}, C (evidence against) {cb['C']}. All in the .tsv beside this file.", ""]
        for k, t in (("A", "A: spelling and evidence for"), ("B", "B: to read"), ("C", "C: evidence against")):
            doc += [f"## {t}", "", "| name | lines, files | target | lines, files | spelling | evidence |", "|---|---|---|---|---|---|"]
            doc += [f"| {r[2]} | {r[3]}, {r[4]} | {r[5]} | {r[6]}, {r[7]} | {r[8]} | {r[9].replace('|', '/')} |" for r in big if r[0] == k]
            doc.append("")
        open(os.path.join(b, "FOLD-CANDIDATES-LATEST.md"), "w", encoding="utf-8").write("\n".join(doc))
        print("wrote profiles/build/FOLD-CANDIDATES-LATEST.md and .tsv")
        order = ("same", "same, initial only", "several", "partly", "none", "differ")
        bar = sorted((r for r in rows if float(r[8]) >= 1), key=lambda r: (order.index(r[10]), -float(r[15]), -float(r[8]), -r[1]))
        targets = collections.Counter(r[2] for r in bar)
        n = collections.Counter(r[10] for r in bar)
        doc = ["# The fold candidates at +1 or above", "", "**GENERATED by `tools/name-fold-candidates.py --write`, after each harvest. Do not edit.** Scored by `name-ungarble.py`'s `score_one` and the editor's weights, the smaller head as the name read, the page lines not consulted (a line's OCR form may move a score). It folds nothing.", "",
               f"{len(bar)} pairs at +1 or above, of {len(rows)}: " + ", ".join(f"{k} {n[k]}" for k in order) + ".", "",
               f"**Second score,** beside the spelling's and never added to it (the editor, 2026-11-05), sorting each class; his weights: given names " + ", ".join(f"{k} {v:+g}" for k, v in SECOND_GIVEN.items()) + "; several +2 where the smaller is the target's main person, at three quarters of its lines or more, +1 where the target is truly mixed, +0.5 for a minority person" + f"; each same act (`tools/same_act.py`) {SECOND_ACT:+g}, an indefinite object only {SECOND_ACT_INDEF:+g}, up to {SECOND_ACTS_CAP} in all; lines forty years apart, or a line naming both, {-SECOND_AGAINST:+g}.", "",
               "Given names, read line by line, the number being lines: **same**, one person by the given name; **several**, the smaller's person is there but the target holds others, so it cannot fold whole; **partly**, only some of the smaller's; **none**, one side names none; **differ**, none of the smaller's. A variant across languages (Johano ~ Jean) reads «differ». «two targets»: the smaller has another pair at the bar, which `apply-scored` would leave.", "",
               "Features: " + "; ".join(f"{c} {NG.WEIGHTS[q]:+g} {q}" for q, c in code.items()) + ".", ""]
        for k in order:
            doc += [f"## {k} ({n[k]})", "", "| spelling | second | name | lines, files | target | lines, files | given names | same acts | features | else |", "|---|---|---|---|---|---|---|---|---|---|"]
            doc += [f"| {r[8]} | {r[15]} | {r[2]} | {r[3]}, {r[4]} | {r[5]} | {r[6]}, {r[7]} | {r[11].replace('|', '/')} | {r[17].replace('|', '/')} | {r[12]} | {'; '.join(x for x in [r[9], 'two targets' if targets[r[2]] > 1 else '', r[13], r[14]] if x).replace('|', '/')} |" for r in bar if r[10] == k]
            doc.append("")
        nums = sorted(((form[s], H[s]["n"], numeral(form[s]), H[slug_of[numeral(form[s])]]["n"] if numeral(form[s]) in slug_of else 0) for s in apart if numeral(form[s]) and numeral(form[s]) != form[s]), key=lambda z: -z[1])
        doc += [f"## A closing LL, LI, IL, II, by default a Roman numeral ({len(nums)})", "", "Not scored: the target is the form with II, whatever the lines.", "", "| name | lines | target | its lines |", "|---|---|---|---|"]
        doc += [f"| {x[0]} | {x[1]} | {x[2]} | {x[3]} |" for x in nums] + [""]
        open(os.path.join(b, "FOLD-SCORED-LATEST.md"), "w", encoding="utf-8").write("\n".join(doc))
        # a given name and one letter: candidates, a head of that initial naming that given name in its lines
        byg = collections.defaultdict(list)
        for s, h in H.items():
            if s in apart: continue
            for w, v in h["given"].items():
                if len(plain(w)) > 1: byg[plain(w)[:4]].append((w, v, s))
        ol = []
        for s in (s for s in apart if one_letter(form[s]) and re.fullmatch(r"[^\W\d_]{3,}", form[s].split()[0])):     # H. K. B. is the initials pass's
            w = form[s].split(); gv, ini = plain(w[0]), plain(w[-1]).strip(".")
            cands = sorted(((v, form[c], g) for g, v, c in byg.get(gv[:4], ()) if plain(form[c].split()[-1]).startswith(ini) and same_given(g, w[0])), reverse=True)
            ol.append((H[s]["n"], form[s], ", ".join(f"{f} ({g}, {v} lines)" for v, f, g in cands[:5]) or "-"))
        ol.sort(key=lambda z: (-z[0], z[1]))
        doc = ["# A given name and one letter", "", "**GENERATED by `tools/name-fold-candidates.py --write`, after each harvest. Do not edit.** A class of its own (the editor, 2026-11-05, on OLGA E. ~ OLGA L.): the «surname» is an initial, so two such heads never fold into each other; each is a candidate to join a full surname, as the initials pass does. A candidate: a head of that initial whose lines give that given name. A closing I, V or X may be a Roman numeral.", "",
               f"{len(ol)} heads; {sum(1 for z in ol if z[2] != '-')} with a candidate.", "", "| lines | head | candidates |", "|---|---|---|"] + [f"| {z[0]} | {z[1]} | {z[2]} |" for z in ol] + [""]
        open(os.path.join(b, "FOLD-INITIAL-SURNAMES-LATEST.md"), "w", encoding="utf-8").write("\n".join(doc))
        print(f"wrote profiles/build/FOLD-INITIAL-SURNAMES-LATEST.md: {len(ol)} heads; numerals {len(nums)}; flipped at the bar {sum(1 for r in bar if r[13])}; ending on a refused form {sum(1 for r in bar if 'refused' in r[14])}; with a chain {sum(1 for r in bar if 'chain:' in r[14])}")
        print(f"wrote profiles/build/FOLD-SCORED-LATEST.md: {len(bar)} pairs at +1 or above; " + ", ".join(f"{k} {n[k]}" for k in order))
    return rows

if __name__ == "__main__":
    main()
