#!/usr/bin/env python3
"""ocr-dowse — the «dowse» query (plan item W5): find names (or, with --stem, theme words) in the geniza corpus, each
item searched in the text its signed line prescribes, and say for every item what a silence may claim.

TWO WAYS TO RUN IT (the editor's ruling of 2026-10-06: the roster against one run is how the project searches, and is the
primary way; the one-name-over-the-corpus way is kept for other searches and other users):

    ROSTER × RUN (the primary way): every name of a roster against the items of one journal run
    tools/ocr-dowse.py --roster <names file> --items "<pattern>[,<pattern>…]" --write <new record.md>

    ONE NAME × THE WHOLE CORPUS
    tools/ocr-dowse.py "<form>" ["<form>" …] --write <new record.md>

A roster file has one person per line: their forms separated by « | » («Eroŝenko | Eroshenko | Ерошенко»); a line
starting «#» is a comment. On the command line, every argument is one form of ONE name. An item is a hit for a person
if any of their forms is found. --items takes item-name patterns (shell style: «LEsperantiste.1907.*», «larevuo.*»),
comma-separated, or @file with one pattern per line. Reads only; writes two new files (refused if either exists): the
record (.md) and every hit before any exclusion (.hits.tsv).

WHAT IT SEARCHES, per item of the current ledger (an internal record, not published; its path is in the code):
  - the text its SIGNED acceptance line names (the signed acceptance records, internal and not published; where an
    item has lines in two of them, the later one holds): the search text `sources/ocr-rendersearch/<item>.txt`, or for SPECIAL
    HANDLING the every-reading text `sources/ocr-rendersearch-all/<item>.txt`;
  - an item with no signed line: its search text, and its every-reading text where one exists (presence only);
  - always, where they exist, its texts in another alphabet: `ocr-rendersearch-rus/`, `-hye/`, `-kat/`.
HOW: tools/ocr_index.py — each text is indexed ONCE (every word form with its pages, the parts of hyphenated words,
adjacent pairs, line-end fragments), and every name is matched against the index by the name search's own rules
(tools/ocr-name-search.py; the index gives exactly what find() gives, checked by tools/ocr-index-check.py). --stem: a
theme word, matched as a folded PREFIX of a word, no fuzziness.
NO CAP on the search: every item is searched and every hit kept. THE RECORD sorts hits by tier (exact · near ·
confusion · translit · small caps and run-ins · join), counts PAGES as well as hits (an every-reading text holds a
printed name once per reading), gives each matched form its corpus count (the lexicon) and, up to --where-max hits of a
form (default: ALL in the roster way, 10 over the whole corpus), WHERE it is; and, for each silent item, what its
silence may claim. Every hit is a CANDIDATE until confirmed on the page image.

READING AN ITEM, per person (the editor's rule of 2026-10-06, «Do not walk down the tiers until something turns up», in
docs/SEARCHING.md): the item's STRONGEST tier decides. Exact, near or confusion: a candidate. Translit hits in an
alphabet the person was given no form in (Latin forms only, hits in Cyrillic; or Cyrillic forms only, hits in Latin —
symmetric, as the editor ruled on 2026-10-06): UNDERSPECIFIED, wherever the reading stopped — give the form in that alphabet
and search again; the item is neither present nor silent until then. Translit first for a person given both
alphabets: CONFIRM — almost certainly noise, but neither present nor silent until judged (a «confirmed» page, a form
set aside, or a cutoff above translit; the editor ruled on 2026-10-06 to err on the side of caution here). Small caps and run-ins,
or join: PRESUMED NOISE, counted as no hit unless a page is confirmed, with its page count shown (0 · 0 · 0 · 1 is
worth reading; hundreds are not pursued by default). Tiers below the person's cutoff are not read at all.

JUDGEMENTS (--judgements FILE), one line per person, fields separated by « | », all but the person optional:
    Bein | stop: exact | exclude: кап, кат | exclude-as-read: kabe | confirmed: RuslandaEsperantisto1907.1 p.20 | why: …
«stop» is the tier the reading stopped at (default: join, i.e. every tier, by the rule above); «exclude» and
«exclude-as-read» act for THAT person only (--exclude and --exclude-as-read act for everyone); a «confirmed» page makes
its item present whatever its tier. The record prints each person's judgement, and their silences follow their cutoff;
the silent counts at the exact-only and up-to-confusion cutoffs are given beside it.
"""
import argparse, collections, datetime, fnmatch, glob, importlib.util, os, random, re, resource, sys, unicodedata
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
S = os.path.join(G, "sources")
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)
sys.path.insert(0, HERE)
import ocr_index as IX  # noqa: E402

STRONG = ("exact", "near", "confusion")
SCRR = "small caps and run-ins"  # tier 5, named by both its contents (the editor's decision, 2026-10-06; was «other»)
TIERS = ("exact", "near", "confusion", "translit", SCRR, "join", "stem")
_CYR = re.compile("[а-яёѣіѳѵ]")


def read_judgements(path):
    """person → {stop, exclude, exclude-as-read, confirmed, why} (see the module docstring)."""
    out = {}
    for l in (open(path, encoding="utf-8") if path else []):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        x = [p.strip() for p in l.split(" | ")]
        j = {"stop": "join", "exclude": "", "exclude-as-read": "", "confirmed": "", "assign": "", "not": "",
             "ambiguous": "", "default": "", "why": ""}
        for f in x[1:]:
            k, _, v = f.partition(":")
            if k.strip() not in j:
                sys.exit(f"judgements: unknown field «{k.strip()}» in: {l}")
            j[k.strip()] = v.strip()
        if j["stop"] == "other":
            j["stop"] = SCRR
        if j["stop"] not in TIERS[:6]:
            sys.exit(f"judgements: stop must be one of {', '.join(TIERS[:6])}: {l}")
        for k in ("confirmed", "assign", "not", "ambiguous"):
            j[k] = {(m.group(1), int(m.group(2))) for m in re.finditer(r"(\S+) p\.?\s*(\d+)", j[k])}
        out[x[0]] = j
    return out


def reading(pages_by_tier, confirmed, stop, missing_script):
    """one person in one item: what the item says, by its strongest tier at or above the cutoff (module docstring).
    UNDERSPECIFIED: translit hits in an alphabet the person was not given any form in (Latin forms only and Cyrillic
    hits, or the reverse; the editor ruled on 2026-10-06 that the name must then be given again in that alphabet),
    wherever the reading stopped. Translit first for a person given both alphabets: CONFIRM — almost certainly noise, but
    not presumed so (the editor ruled on 2026-10-06 to err on the side of caution)."""
    if confirmed:
        return "confirmed on the image"
    hit = [t for t in TIERS[:TIERS.index(stop) + 1] if pages_by_tier.get(t)]
    if not hit:
        return "underspecified" if missing_script else "silent"
    b = hit[0]
    if b in ("exact", "near", "confusion"):
        return "candidate" if b != "exact" else "exact"
    if b == "translit":
        return "underspecified" if missing_script else "confirm"
    return "presumed noise"


def current_ledger():
    st = open(os.path.join(G, "OCR-STATUS.md"), encoding="utf-8").read()
    return os.path.join(G, "ocr", "runs", re.search(r"`(OCR-ABSENCE-LEDGER-[^`]+\.tsv)`", st).group(1))


def signed_lines():
    """item → (file, line fields); later files win (their names sort by date)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(G, "OCR-ACCEPTANCE-LINES-*SIGNED*.txt"))):
        for l in open(f, encoding="utf-8"):
            if l.startswith("ACCEPTED: "):
                x = [p.strip() for p in l[len("ACCEPTED: "):].rstrip("\n").split(" | ")]
                out[x[0]] = (os.path.basename(f), x)
    return out


def born_digital():
    """{(item, PDF page)} whose text layer is born-digital (sources/ocr-text-layer-*/tl-kind.tsv, the newest): the layer
    IS the printed text, so a hit there needs no image check (the editor's decision, 2026-10-06)."""
    c = sorted(glob.glob(os.path.join(S, "ocr-text-layer-*", "tl-kind.tsv")))
    out = set()
    for l in (open(c[-1], encoding="utf-8") if c else []):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 3 and x[2] == "born-digital" and x[1].isdigit():
            out.add((x[0], int(x[1])))
    return out


def lexicon(path):
    """folded form → occurrences in the corpus (tools/ocr-corpus-lexicon.py)."""
    if not path:
        c = sorted(glob.glob(os.path.join(S, "ocr-work", "ocr-lexicon-*.tsv")))
        path = c[-1] if c else None
    out = {}
    if path:
        for l in open(path, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 2 and x[1].isdigit():
                out[x[0]] = int(x[1])
    return out


def tier(how, form, targets, stem):
    """the kind of match, strongest first (TIERS)."""
    if stem:
        return "stem"
    if not how.startswith("word"):
        return "join"
    if "measured OCR confusion" in how:
        return "confusion"
    if form in targets:
        return "exact"
    for tg in targets:
        if bool(_CYR.search(form)) == bool(_CYR.search(tg)):
            cap = 1 if len(tg) <= 6 else 2
            if NS.edits(form, tg, cap) <= cap or (_CYR.search(tg) and NS.stem_close(form, tg, cap)):
                return "near"
    if any(bool(_CYR.search(form)) != bool(_CYR.search(tg)) for tg in targets):
        return "translit"
    return SCRR


def stem_match(stems, text):
    return [(p, "stem", r) for p, pt in IX.pages(text) for r in NS.normalise(pt).split()
            if any(NS.fold(r).startswith(s) for s in stems)]


def search_item(job):
    """one item: {person: [(text, page, how, as read)]} for every person of the roster."""
    item, files, people, stem = job
    out = collections.defaultdict(list)
    size = [0, 0]  # pages, words searched (for the record's timing line)
    for f in files:
        text = open(f, encoding="utf-8", errors="ignore").read()
        rel = os.path.relpath(f, S)
        size[0] += len(IX.pages(text)); size[1] += len(text.split())
        if stem:
            for label, forms in people:
                out[label] += [(rel, p, how, r) for p, how, r in stem_match([NS.fold(x) for x in forms], text)]
            continue
        idx = IX.build(text)
        for label, forms in people:
            for fm in forms:
                out[label] += [(rel, p, how, r) for p, how, r in IX.match(fm, idx)]
    out["\0size"] = size
    return item, dict(out)


def read_roster(path):
    """[(label, forms)], {label: [first names and initials]}, {label: {titles, folded}}. A line may end
    « || first: Joseph, Jos., J., Józef || titles: S-ro, M., Sergent »: the person's first names and initials, and the
    titles they can carry, for people who share a surname (the label then carries the first first name)."""
    people, firsts, titles = [], {}, {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l and not l.startswith("#"):
            parts = l.split(" || ")
            forms = [x.strip() for x in parts[0].split(" | ") if x.strip()]
            fs, ts = [], []
            for part in parts[1:]:
                k, _, v = part.partition(":")
                vals = [x.strip() for x in v.split(",") if x.strip()]
                if k.strip() == "first":
                    fs = vals
                elif k.strip() == "titles":
                    ts = vals
                else:
                    sys.exit(f"roster: unknown field «{k.strip()}» in: {l}")
            label = forms[0] + (f" ({fs[0]})" if fs else "")
            if label in {p[0] for p in people}:
                sys.exit(f"roster: two lines with the label «{label}»; give first names (« || first: … »)")
            people.append((label, forms))
            if fs:
                firsts[label] = fs
            if ts:
                titles[label] = {_bare(t) for t in ts if _bare(t)}
    return people, firsts, titles


# SAME SURNAME, DIFFERENT PEOPLE (the editor's method, 2026-10-06: sort the surname's hits by first name or initial, then
# read the remainder in context; what is left is a residue for arbitration). Each hit
# of a shared surname is sorted by the words beside it: before it («L. L. Zamenhof», «Joseph Jamin»), or after it when
# nothing precedes («Jamin, Jos.», «Заменгофъ Л. Л.»). Titles end the run and decide nothing (both Zamenhofs were doctors).
TITLES = {NS.fold(x) for x in ("dro", "d-ro", "sro", "s-ro", "sino", "s-ino", "fino", "f-ino", "s", "m", "mr", "mrs",
          "mme", "mlle", "dr", "prof", "profesoro", "doktoro", "sinjoro", "sinjorino", "fraŭlino", "herr", "frau",
          "monsieur", "madame", "г", "гнъ", "г-нъ", "гжа", "г-жа", "д-ръ", "дръ", "докторъ", "профессоръ", "la", "de",
          # the French doctor's title as the OCR reads it (seen in a test search of 6 October 2026: «D'», «D"», «Dre», «D°», «Docteur»), and
          # other words that sit before a name in a list
          "d", "dre", "do", "docteur", "doct", "mm", "messieurs", "mmes", "abbe", "pere", "sr", "le", "les", "et",
          "kaj", "und", "von", "van")}


def _bare(tok):
    return NS.fold(re.sub(r"[^\w]", "", tok))


def _initial(tok):
    # with its full stop («и», «в», «с» are Russian words), or the stop misread as a comma («L,»)
    return bool(re.fullmatch(r"[^\W\d_][.,],?", tok))


def _abbrev_of(b, name):
    """«jos» of «joseph», «leop» (or «lcop», one letter misread) of «leopold»: three letters or more."""
    return len(b) >= 3 and len(b) < len(name) and (name.startswith(b) or (len(b) >= 4 and NS.edits(b, name[:len(b)], 1) <= 1))


# plural titles: the hit is ALL of the people who share the surname («MM. Jamin», «S-oj Jamin», «al la fratoj Zamenhof»)
# — but only those of them who can carry the plural's singular («fratoj», «MM.» are the men; «Mmes» the women); a
# person with no titles listed is not ruled out; «gesinjoroj» (men and women) is everyone
_MALE, _FEMALE = {"sro", "sinjoro", "m", "monsieur", "mr", "herr", "г", "гнъ"}, {"sino", "sinjorino", "mme", "madame", "frau", "гжа"}
PLURAL = {NS.fold(k): v for k, v in (("mm", _MALE), ("messieurs", _MALE), ("soj", _MALE), ("sroj", _MALE),
                                      ("sinjoroj", _MALE), ("fratoj", _MALE), ("fratojn", _MALE), ("frères", _MALE),
                                      ("gg", _MALE), ("гг", _MALE), ("mmes", _FEMALE), ("sinoj", _FEMALE),
                                      ("gesinjoroj", None), ("gesroj", None))}


FUNCTION = {NS.fold(x) for x in ("la", "de", "le", "les", "et", "kaj", "und", "von", "van")}  # end a run; not titles
# REAL titles: only these (and the titles on the roster's lines) narrow who a hit can be. The OCR's fragments of a
# title («S°», «Sr»», «S“)» for a superscript S-ro; «Do», «D'o» for D-ro) end a run but are not read as a title, so they
# never overrule a first name (seen in a test search of 6 October 2026: «S° Léopold Jamin», «Sr» Jos. Jamin»)
REAL = {_bare(x) for x in ("S-ro", "Sinjoro", "S-ino", "Sinjorino", "F-ino", "Fraŭlino", "M.", "Monsieur", "Mme",
        "Madame", "Mlle", "Mademoiselle", "Mr", "Mrs", "Miss", "Herr", "Frau", "Fräulein", "Dr", "D-ro", "Doktoro",
        "Docteur", "Prof.", "Profesoro", "Professeur", "Sergent", "Serĝento", "Lieutenant", "Leŭtenanto",
        "Sous-lieutenant", "Kapitano", "Capitaine", "Kolonelo", "Colonel", "Komandanto", "Commandant", "Abbé", "Pastro",
        "Г.", "Г-нъ", "Г-жа", "Д-ръ", "Докторъ", "Профессоръ")}


def sort_hit(toks, i, group, firsts, titles=None):
    """the hit at toks[i] (a shared surname): ('assigned', label) · ('all', [labels]) · ('ambiguous', [labels]) ·
    ('titled', title) · ('unlisted', word) · ('bare', None). TITLES DECIDE BY CONTEXT (the editor's ruling of 2026-10-06: a
    title decides only by context, so the attributes a title can decide on are established for each person first): the titles each person can carry are on their roster
    line; a title just before the name (or before its initials) keeps only the people who can carry it — «F-ino L.
    Zamenhof» is Lidja, «Sergent Jamin» Léopold — and a person with no titles listed is not ruled out by one. A bare hit
    whose title fits nobody is «titled»: no default takes it, unless the default person can carry that title."""
    titles = titles or {}
    names = {_bare(w) for lab in group for f in firsts.get(lab, ()) for w in f.split() if len(_bare(w)) > 1}
    known = TITLES | set(PLURAL) | {t for lab in group for t in titles.get(lab, ())}

    def namelike(t):
        b = _bare(t)
        return bool(b) and b not in known and (_initial(t) or b in names or any(_abbrev_of(b, n) for n in names) or
                                               (len(b) >= 5 and any(NS.edits(b, n, 1) <= 1 for n in names if len(n) >= 5)))
    run, j = [], i - 1
    while j >= 0 and namelike(toks[j]):
        run.insert(0, toks[j]); j -= 1
    tpos = j
    if not run and (toks[i].endswith(",") or (i + 1 < len(toks) and _initial(toks[i + 1]))):
        k = i + 1
        while k < len(toks) and namelike(toks[k]):
            run.append(toks[k]); k += 1
    real = (REAL | {t for lab in group for t in titles.get(lab, ())}) | set(PLURAL)
    title = _bare(toks[tpos]) if tpos >= 0 and _bare(toks[tpos]) in real - FUNCTION else None
    if title in PLURAL:
        sing = PLURAL[title]
        return ("all", [c for c in group if sing is None or c not in titles or titles[c] & sing])

    def fit(cands):
        return [c for c in cands if c not in titles or title in titles[c]] if title else list(cands)
    if not run:
        if title:
            who = [c for c in group if title in titles.get(c, ())]
            if len(who) == 1:
                return ("assigned", who[0])
            if not who and any(c in titles for c in group):
                return ("titled", toks[tpos])
            return ("bare", None)
        prev = toks[i - 1] if i > 0 else ""
        if prev[:1].isupper() and _bare(prev) and _bare(prev) not in known and not _initial(prev):
            return ("unlisted", prev)
        return ("bare", None)
    full = [_bare(t) for t in run if len(_bare(t)) > 1]
    if full:
        who = [lab for lab in group if any(
            any(_bare(w) == b or _abbrev_of(b, _bare(w)) or (len(b) >= 5 and NS.edits(b, _bare(w), 1) <= 1) for b in full)
            for f in firsts.get(lab, ()) for w in f.split())]
    else:
        seq = [_bare(t) for t in run]
        who = [lab for lab in group if any([_bare(w)[:1] for w in f.split()][:len(seq)] == seq
                                           for f in firsts.get(lab, ()))]
    narrowed = fit(who)
    if len(narrowed) == 1:
        return ("assigned", narrowed[0])
    if narrowed:
        return ("ambiguous", narrowed)
    if who:
        return ("titled", toks[tpos])  # the initials fit, the title fits none of them
    return ("unlisted", " ".join(run))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms", nargs="*", help="the forms of ONE name (the one-name way)")
    ap.add_argument("--roster", help="a roster file: one person per line, forms separated by « | »")
    ap.add_argument("--items", help="item-name patterns, comma-separated, or @file (default: every item)")
    ap.add_argument("--write", required=True)
    ap.add_argument("--stem", action="store_true", help="theme words: folded prefix match, no fuzziness")
    ap.add_argument("--ledger", default=None, help="default: the current ledger named in the project's status file")
    ap.add_argument("--lexicon", default=None, help="default: the newest sources/ocr-work/ocr-lexicon-*.tsv")
    ap.add_argument("--exclude", default="", help="forms judged noise, comma-separated (as read; folded here)")
    ap.add_argument("--exclude-as-read", default="", help="spellings judged noise EXACTLY as printed, case and accents "
                    "kept, punctuation ignored, comma-separated (e.g. «kabe» to set aside lowercase hits of a name that is "
                    "also a word)")
    ap.add_argument("--judgements", default=None, help="a judgement file: per person, the tier reading stopped at, "
                    "forms set aside, pages confirmed, why (see the module docstring)")
    ap.add_argument("--from-hits", default=None, help="rebuild the record from a saved <record>.hits.tsv, no search")
    ap.add_argument("--where-max", type=int, default=None,
                    help="list the places of a form with at most this many hits (default: all with --items, else 10)")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    people, firsts, titles = (read_roster(a.roster) if a.roster
                              else (([(a.forms[0], a.forms)] if a.forms else []), {}, {}))
    if not people:
        sys.exit("give the forms of a name, or --roster")
    hits_tsv = re.sub(r"\.md$", "", a.write) + ".hits.tsv"
    sur_tsv = re.sub(r"\.md$", "", a.write) + ".surnames.tsv"
    for p in (a.write, sur_tsv) + (() if a.from_hits else (hits_tsv,)):
        if os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    where_max = a.where_max if a.where_max is not None else (10 ** 9 if a.items else 10)
    ledger = a.ledger or current_ledger()
    led = [x for x in (l.rstrip("\n").split("\t") for l in open(ledger, encoding="utf-8")) if x and not x[0].startswith("#")]
    rows = {x[0]: dict(zip(led[0], x)) for x in led[1:]}
    if a.items:
        pats = ([l.strip() for l in open(a.items[1:], encoding="utf-8") if l.strip()] if a.items.startswith("@")
                else [p.strip() for p in a.items.split(",") if p.strip()])
        rows = {k: v for k, v in rows.items() if any(fnmatch.fnmatch(k, p) for p in pats)}
        if not rows:
            sys.exit(f"no ledger item matches {pats}")
    signed = signed_lines()
    pdfl = sorted(f for f in glob.glob(os.path.join(S, "OCR-PDF-LIST-*.txt")) if not f.endswith("-NEW.txt"))[-1]
    pdf = {os.path.splitext(os.path.basename(p))[0]: p for p in (l.strip() for l in open(pdfl)) if p}
    t0 = datetime.datetime.now()
    res = {}  # item -> {person: [(text, page, how, as read)]}
    if a.from_hits:
        res = {it: collections.defaultdict(list) for it in rows}
        for l in open(a.from_hits, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) == 8 and x[0] != "person" and not x[0].startswith("#") and x[1] in res:
                res[x[1]][x[0]].append((x[3], int(x[4]), x[5], x[6]))
    else:
        jobs = []
        for it in rows:
            line = signed.get(it)
            allr = os.path.join(S, "ocr-rendersearch-all", it + ".txt")
            files = ([allr] if line and "ocr-rendersearch-all" in line[1][3] else
                     [os.path.join(S, "ocr-rendersearch", it + ".txt")] + ([allr] if not line else []))
            files += [os.path.join(S, f"ocr-rendersearch-{c}", it + ".txt") for c in ("rus", "hye", "kat")]
            jobs.append((it, [f for f in files if os.path.exists(f)], people, a.stem))
        with Pool(a.jobs) as pool:
            res = dict(pool.imap_unordered(search_item, jobs, chunksize=4))
    secs = (datetime.datetime.now() - t0).seconds
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_utime
    sizes = [v.pop("\0size") for v in res.values() if "\0size" in v]
    n_pages, n_words = sum(x[0] for x in sizes), sum(x[1] for x in sizes)
    lex = lexicon(a.lexicon)
    BD = born_digital()
    excl = {NS.fold(x) for x in a.exclude.split(",") if x.strip()}
    spell = lambda r: re.sub(r"[^\w]", "", unicodedata.normalize("NFC", r))  # as printed: case and accents kept
    excl_ar = {spell(x) for x in a.exclude_as_read.split(",") if x.strip()}
    tg_of = {label: {NS.fold(max(re.findall(r"[^\W\d_]+", f), key=len)) for f in forms} for label, forms in people}
    formof = lambda r: NS.fold(re.sub(r"\s*…\s*", "", r).replace(" ", ""))
    if not a.from_hits:
        with open(hits_tsv, "w", encoding="utf-8") as fh:
            fh.write(f"# GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}: every hit, before any exclusion.\n")
            fh.write("person\titem\ttier\ttext\tpage\thow\tas_read\tform\n")
            for it in sorted(res):
                for label, hs in sorted(res[it].items()):
                    for f, p, how, r in hs:
                        fh.write(f"{label}\t{it}\t{tier(how, formof(r), tg_of[label], a.stem)}\t{f}\t{p}\t{how}\t{r}\t{formof(r)}\n")
    # per person: tiered hits, after exclusions (everyone's, then the person's own judgement)
    J = read_judgements(a.judgements)
    unknown = sorted(set(J) - {label for label, _ in people})
    if unknown:
        sys.exit(f"judgements name people not on the roster: {', '.join(unknown)}")
    jx = {label: ({NS.fold(x) for x in J[label]["exclude"].split(",") if x.strip()},
                  {spell(x) for x in J[label]["exclude-as-read"].split(",") if x.strip()}) for label in J}
    T = collections.defaultdict(list)  # person -> [(tier, item, text, page, how, as read, form)]
    excluded = collections.Counter()
    excluded_p = collections.defaultdict(collections.Counter)  # person -> their own exclusions' hits
    # people who share a surname, with first names given: their hits are sorted by first name (sort_hit)
    grp = {la: tuple(lb for lb, _ in people if lb in firsts and tg_of[lb] & tg_of[la]) for la, _ in people if la in firsts}
    grp = {la: g for la, g in grp.items() if len(g) > 1}
    unsorted = sorted({la for la, _ in people for lb, _ in people
                       if la != lb and tg_of[la] & tg_of[lb] and (la not in grp or lb not in grp)})
    assign_of = {la: (J[la]["assign"] if la in J else set()) for la, _ in people}
    # «not»: pages where the shared surname, unsorted by first name, is shown NOT to be this person (another word, or a
    # namesake: Paul Jamin of Dijon, «boulevard Jamin» in Reims); a page all of them disown is not residue
    not_of = {la: (J[la]["not"] if la in J else set()) for la, _ in people}
    # DEFAULT ATTRIBUTION (the editor's decision, 2026-10-06: a default is a risk but reasonable, kept apart, and vetted
    # where the scale allows): «default: yes» on one person of
    # a shared surname gives them its bare hits, and the ambiguous ones whose initial they share — kept apart from the
    # hits sorted by first name («by default»), never making anyone else silent, and listed for vetting
    dflt = {}
    for la, g in grp.items():
        if la in J and J[la]["default"].lower() in ("yes", "y", "true"):
            if g in dflt:
                sys.exit(f"judgements: two defaults for one surname: {dflt[g]}, {la}")
            dflt[g] = la
    def default_takes(s, d):
        """a default takes a bare hit, an ambiguous one it is among, and a titled one only if it can carry the title"""
        return (s[0] == "bare" or (s[0] == "ambiguous" and d in s[1])
                or (s[0] == "titled" and (d not in titles or _bare(s[1]) in titles[d])))
    TD = collections.defaultdict(list)     # person -> their hits BY DEFAULT [(tier, item, text, page, how, as read, form, context)]
    _pg, _sorted, kseen = {}, {}, collections.Counter()
    SORT = collections.defaultdict(dict)   # group -> {hit key: (sort, tier, context)}
    RES_T = collections.defaultdict(set)   # (group, item) -> tiers of its unresolved (residue) hits

    def page_toks(f, p):
        if f not in _pg:
            txt = open(os.path.join(S, f), encoding="utf-8", errors="ignore").read()
            _pg[f] = {q: NS.normalise(t).split() for q, t in IX.pages(txt)}
        return _pg[f].get(p, [])

    def sort_of(it, f, p, how, r, k, g):
        key = (g, it, f, p, how, r, k)
        if key not in _sorted:
            toks = page_toks(f, p)
            if how.startswith("two words joined"):
                pos = [i for i in range(len(toks) - 1) if toks[i] + " " + toks[i + 1] == r]
            elif how.startswith(("word", "part of")):
                pos = [i for i, t in enumerate(toks) if t == r]
            else:
                pos = []
            if not pos:
                _sorted[key] = (("bare", None), f"«{r}» (context not read: {how.split(' (')[0]})")
            else:
                i = pos[min(k, len(pos) - 1)]
                ctx = " ".join(toks[max(0, i - 5):i] + [f"**{toks[i]}**"] + toks[i + 1:i + 6])
                _sorted[key] = (sort_hit(toks, i, g, firsts, titles), ctx)
        return _sorted[key]
    for it, per in res.items():
        for label, hs in per.items():
            own, own_ar = jx.get(label, (set(), set()))
            for f, p, how, r in hs:
                fm = formof(r)
                if fm in excl:
                    excluded[fm] += 1; continue
                if spell(r) in excl_ar:
                    excluded["as read: " + spell(r)] += 1; continue
                if fm in own:
                    excluded_p[label][fm] += 1; continue
                if spell(r) in own_ar:
                    excluded_p[label]["as read: " + spell(r)] += 1; continue
                t_ = tier(how, fm, tg_of[label], a.stem)
                if label in grp:
                    g = grp[label]
                    k = kseen[(label, it, f, p, r)]; kseen[(label, it, f, p, r)] += 1
                    s, ctx = sort_of(it, f, p, how, r, k, g)
                    SORT[g][(it, f, p, how, r, k)] = (s, t_, ctx)
                    decided = s[0] in ("assigned", "all")
                    mine = (s == ("assigned", label) or (s[0] == "all" and label in s[1])
                            or (not decided and (it, p) in assign_of[label] and (it, p) not in not_of[label]))
                    if not mine:
                        unres = (not decided and not any((it, p) in assign_of[o] for o in g)
                                 and (it, p) not in not_of[label] and not all((it, p) in not_of[o] for o in g))
                        if unres and t_ in STRONG and dflt.get(g) == label and default_takes(s, label):
                            TD[label].append((t_, it, f, p, how, r, fm, ctx)); continue
                        # the residue holds only unresolved hits of the strong tiers: a weak hit nobody can claim is
                        # presumed noise anyway (the rule «Do not walk down the tiers»)
                        if unres and t_ in STRONG:
                            RES_T[(g, it)].add(t_)
                        continue
                T[label].append((t_, it, f, p, how, r, fm))
    # per person and item: the pages of each tier, and what the item says (reading())
    PT = {label: collections.defaultdict(lambda: collections.defaultdict(set)) for label, _ in people}
    TS = collections.defaultdict(set)  # (person, item) -> alphabets of its translit hits
    for label, hs in T.items():
        for h in hs:
            PT[label][h[1]][h[0]].add(h[3])
            if h[0] == "translit":
                TS[(label, h[1])].add("cyr" if _CYR.search(h[6]) else "lat")
    PTD = collections.defaultdict(lambda: collections.defaultdict(set))  # person -> item -> tiers of default hits
    for label, hs in TD.items():
        for h in hs:
            PTD[label][h[1]].add(h[0])
    stop_of = {label: (J[label]["stop"] if label in J else "join") for label, _ in people}
    conf_of = {label: (J[label]["confirmed"] if label in J else set()) for label, _ in people}
    given = {label: {"cyr" if _CYR.search(f.lower()) else "lat" for f in forms} for label, forms in people}

    def read_item(label, it, stop=None):
        if a.stem:
            return "present" if PT[label].get(it) else "silent"
        rd = reading(PT[label].get(it, {}), any(c[0] == it for c in conf_of[label]), stop or stop_of[label],
                     bool(TS[(label, it)] - given[label]))
        if rd in ("silent", "presumed noise") and any(
                TIERS.index(t) <= TIERS.index(stop or stop_of[label]) for t in PTD[label].get(it, ())):
            return "by default"  # present only through the default attribution: kept apart, to be vetted
        if label in grp and rd in ("silent", "presumed noise") and any(
                TIERS.index(t) <= TIERS.index(stop or stop_of[label]) for t in RES_T[(grp[label], it)]):
            return "residue"  # the shared surname is there, unresolved: neither present nor silent
        return rd
    roster_way = len(people) > 1 or bool(a.items)
    L = [f"# dowse: {people[0][0] if len(people) == 1 else f'{len(people)} people'}"
         + (f" × {len(rows)} items ({a.items})" if a.items else " × the whole corpus") + (" (theme stems)" if a.stem else ""), "",
         f"`[GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}, in {secs} s. Ledger "
         f"{os.path.basename(ledger)}; signed files: the union of OCR-ACCEPTANCE-LINES-*-SIGNED*.txt (later holds). "
         f"Searched {len(rows)} items, uncapped. Every hit: `{os.path.basename(a.from_hits or hits_tsv)}`. Every hit is a "
         f"CANDIDATE until confirmed on the page image. Do not hand-edit — re-run it.]`", "",
         (f"**Size and time:** {len(rows):,} items, {n_pages:,} pages, {n_words:,} words searched (each text counted once, "
          f"the texts in other alphabets included), {len(people):,} people; {secs:,} s wall-clock, {cpu:,.0f} s CPU, "
          f"{a.jobs} processes, on the machine described in METHOD.md." if not a.from_hits else
          "**Rebuilt from a saved hits table:** no search was run."), ""]
    if excl or excl_ar:
        L += ["**Excluded as judged noise** (--exclude, --exclude-as-read; their hits do not count, so an item hit only by "
              "them is silent): " + ", ".join([f"«{k}» ({excluded[k]} hits)" for k in sorted(excl)]
              + [f"«{k}» exactly as printed ({excluded['as read: ' + k]} hits)" for k in sorted(excl_ar)]), ""]
    if roster_way:
        L += ["## Summary: pages per person, by tier, and what the items say", "",
              "PAGES, not hits (a page with the name twice, or in two readings, counts once). «read to»: the person's "
              "cutoff (the judgement file; default every tier). Items, by their strongest tier at or above the cutoff: "
              "exact or candidate (near, confusion); underspecified (translit hits in an alphabet the person was given "
              "no form in: give that form and search again); confirm (translit first, both alphabets given: almost "
              "certainly noise, to be judged); presumed noise (small caps and run-ins, or join, only); silent. "
              "Underspecified and confirm items are neither present nor silent; presumed noise counts as silent unless "
              "a page is confirmed.", "",
              "| person | " + " | ".join(TIERS[:6]) + " | read to | exact or candidate | present by default "
              "| underspecified | confirm | shared-surname residue | presumed noise | silent | silent or noise, signed |",
              "|---|" + "---:|" * 6 + "---|" + "---:|" * 8]
        for label, forms in people:
            pg = {t: sum(len(PT[label][it].get(t, ())) for it in PT[label]) for t in TIERS[:6]}
            rd = collections.Counter(read_item(label, it) for it in rows)
            ss = sum(1 for it in rows if it in signed and read_item(label, it) in ("silent", "presumed noise"))
            L.append(f"| {label} | " + " | ".join(str(pg[t]) for t in TIERS[:6]) + f" | {stop_of[label]} | "
                     f"{rd['exact'] + rd['candidate'] + rd['confirmed on the image']} | {rd['by default']} | {rd['underspecified']} | "
                     f"{rd['confirm']} | {rd['residue']} | {rd['presumed noise']} | {rd['silent']} | {ss} |")
        L.append("")
    if unsorted:
        L += ["**Not sorted by first name:** " + ", ".join(unsorted) + " share a surname with someone on the roster "
              "but have no first names given (« || first: … » on their roster line), so the same hits count for each.", ""]
    # SAME SURNAME, DIFFERENT PEOPLE: each group's hits as sorted, and the residue for the editor's arbitration
    with open(sur_tsv, "w", encoding="utf-8") if grp else open(os.devnull, "w") as fs_:
        fs_.write(f"# GENERATED by tools/ocr-dowse.py, {datetime.datetime.now():%Y-%m-%d %H:%M}: every hit of a shared "
                  "surname, as sorted by first name; «resolved by» names a judgement-file «assign».\n")
        fs_.write("group\titem\tpage\ttier\tsorted\tto\tresolved by\tcontext\ttext\n")
        for g in sorted(set(grp.values())):
            S_ = SORT[g]
            n = collections.Counter()
            resid = []
            for (it, f, p, how, r, k), (s, t_, ctx) in sorted(S_.items()):
                decided = s[0] in ("assigned", "all")
                by = [o for o in g if (it, p) in assign_of[o]] if not decided else []
                if not by and not decided and all((it, p) in not_of[o] for o in g):
                    by = ["not any of them («not»)"]
                d = dflt.get(g)
                if not by and d and t_ in STRONG and not decided and default_takes(s, d):
                    by = [f"default: {d}"]
                    n[f"{s[0]}, by default to {d}"] += 1
                else:
                    n[s[1] if s[0] == "assigned" else ("all of them (a plural title)" if s[0] == "all" else s[0])] += 1
                if not decided and not by and t_ in STRONG:
                    resid.append((it, p, t_, s, ctx))
                who = (s[1] if s[0] == "assigned" else (", ".join(s[1]) if s[0] in ("ambiguous", "all") else (s[1] or "")))
                fs_.write(f"{' · '.join(g)}\t{it}\t{p}\t{t_}\t{s[0]}\t{who}\t{', '.join(by)}\t{ctx}\t{f}\n")
            L += [f"## Shared surname: {' · '.join(g)}", "",
                  "Every hit of the surname, sorted by the words beside it (a first name, or an initial only one of "
                  "them has, or a title only one of them can carry; a plural title is all of them). Ambiguous (an "
                  "initial or title they share), titled (a title none of them carries), unlisted (another first name) "
                  "and bare hits go to contextual reading; a page so resolved is given to its person with «assign» in "
                  "the judgement file. What remains is the RESIDUE, for the editor's arbitration: an item where the "
                  "surname is only in the residue is neither present nor silent for any of them.", "",
                  "| sorted | hits |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in sorted(n.items(), key=lambda kv: -kv[1])]
            L += ["", f"### Residue: {len(resid)} hits on {len({(x[0], x[1]) for x in resid})} pages "
                  "(every sorted hit, with its context: `" + os.path.basename(sur_tsv) + "`)", ""]
            if resid:
                # «ambiguous» in the judgement file: the editor ruled the page undecidable from this text (2026-10-06:
                # an ambiguous datum; the disambiguation, if any, comes from another source)
                amb = {k for o in g for k in (J[o]["ambiguous"] if o in J else set())}
                L += ["| item p. PDF page | tier | sorted | arbitration | context |", "|---|---|---|---|---|"]
                for it, p, t_, s, ctx in resid[:where_max]:
                    lab = s[0] + (f": {', '.join(s[1])}" if s[0] == "ambiguous" else (f": «{s[1]}»" if s[1] else ""))
                    arb = "ruled ambiguous" if (it, p) in amb else "awaiting"
                    L.append(f"| {it} p.{p} | {t_} | {lab} | {arb} | {ctx.replace('|', '/')} |")
                if len(resid) > where_max:
                    L.append(f"| … | | | {len(resid) - where_max} more: see `{os.path.basename(sur_tsv)}` |")
            L.append("")
    for label, forms in people:
        hs = T[label]
        L += [f"## {label}" + (f" (forms: {' · '.join(forms)})" if len(forms) > 1 else ""), ""]
        if label in J:
            j = J[label]
            L += [f"**Judgement** (`{os.path.basename(a.judgements)}`): read to **{j['stop']}**"
                  + (f"; set aside for this person: " + ", ".join(f"«{k}» ({n} hits)" for k, n in sorted(excluded_p[label].items()))
                     if excluded_p[label] else "")
                  + (f"; confirmed on the image: " + ", ".join(f"{i} p.{p}" for i, p in sorted(j["confirmed"])) if j["confirmed"] else "")
                  + (f"; shared-surname pages assigned by reading: " + ", ".join(f"{i} p.{p}" for i, p in sorted(j["assign"])) if j["assign"] else "")
                  + (f"; shared-surname pages shown not to be this person: {len(j['not'])}" if j["not"] else "")
                  + ("; DEFAULT for the shared surname (its bare and shared-initial hits, kept apart)" if label in dflt.values() else "")
                  + (f". Why: {j['why']}" if j["why"] else ""), ""]
        by_t = collections.defaultdict(list)
        for h in hs:
            by_t[h[0]].append(h)
        L += ["| tier | hits | pages | items |", "|---|---:|---:|---:|"] + [
            f"| {t} | {len(by_t[t])} | {len({(h[1], h[3]) for h in by_t[t]})} | {len({h[1] for h in by_t[t]})} |"
            for t in TIERS if by_t[t]]
        for t in TIERS:
            if not by_t[t]:
                continue
            forms_m = collections.defaultdict(list)
            for h in by_t[t]:
                # the exact tier is shown by spelling AS PRINTED (Kabe · KABE · kabe), so the reader sees capitals,
                # accents lost or kept, and lowercase hits that may be another word (the editor's decision, 2026-10-06)
                forms_m[spell(h[5]) if t == "exact" else h[6]].append(h)
            L += ["", f"### {label} · {t}" + (" (by spelling as printed)" if t == "exact" else ""), "",
                  "| form as read | in the corpus (lexicon) | hits | pages | items | where (item p. PDF page) |",
                  "|---|---:|---:|---:|---:|---|"]
            for fm, v in sorted(forms_m.items(), key=lambda kv: -len({(h[1], h[3]) for h in kv[1]})):
                places = sorted({(h[1], h[3]) for h in v})
                where = ("; ".join(f"{i} p.{p}" for i, p in places) if len(places) <= where_max
                         else f"{len(places)} pages: see the hits table")
                shown = fm if t == "exact" else v[0][5]
                L.append(f"| «{shown}» | {lex.get(v[0][6], '—')} | {len(v)} | {len(places)} | {len({h[1] for h in v})} | {where} |")
        # per item: pages per tier, and what the item says for this person (items with any hit only)
        if not a.stem and PT[label]:
            L += ["", f"### {label} · by item: pages per tier, and what the item says (read to {stop_of[label]})", "",
                  "| item | " + " | ".join(TIERS[:6]) + " | the item says |", "|---|" + "---:|" * 6 + "---|"]
            for it in sorted(PT[label]):
                r = read_item(label, it)
                note = {"underspecified": "underspecified: give the form in the other alphabet and search again",
                        "confirm": "confirm: translit only (both alphabets searched); almost certainly noise",
                        "presumed noise": "presumed noise: counted as no hit unless a page is confirmed"}.get(r, r)
                L.append(f"| {it} | " + " | ".join(str(len(PT[label][it].get(t, ()))) for t in TIERS[:6]) + f" | {note} |")
        # TO CHECK ON THE PAGE IMAGE (a practical limit, the editor's decision of 2026-10-06):
        # per tier read, born-digital pages need no check; the OCR pages are listed in full up to 40, else a blind sample
        # of 40 (fixed seed), and the tier stands or falls by it; one confirmed page makes an item present; quotations
        # are always read on the image; silences need none
        if not a.stem and hs:
            L += ["", f"### {label} · to check on the page image (D4: every OCR page up to 40 per tier, else a blind "
                  f"sample of 40; born-digital pages need no check)", "",
                  "| tier | pages | born-digital (no check) | already confirmed | to check | pages to check (item p. PDF page) |",
                  "|---|---:|---:|---:|---:|---|"]
            for t in TIERS[:TIERS.index(stop_of[label]) + 1]:
                pgs = sorted({(h[1], h[3]) for h in hs if h[0] == t})
                if not pgs:
                    continue
                bd = [k for k in pgs if k in BD]
                done = [k for k in pgs if k in conf_of[label]]
                left = [k for k in pgs if k not in BD and k not in conf_of[label]]
                chk = left if len(left) <= 40 else sorted(random.Random(label + t).sample(left, 40))
                L.append(f"| {t} | {len(pgs)} | {len(bd)} | {len(done)} | {len(chk)}"
                         + ("" if chk is left else f" (sample of {len(left)})") + " | "
                         + "; ".join(f"{i} p.{q}" for i, q in chk) + " |")
        # hits BY DEFAULT (a shared surname's bare or shared-initial hits), apart, with a vetting list: every page up
        # to 40, else a blind sample of 40 drawn by a fixed seed (the venture's sample size for visual checks)
        if TD.get(label):
            pg_d = {}
            for h in sorted(TD[label]):
                pg_d.setdefault((h[1], h[3]), h)
            keys = sorted(pg_d)
            vet = keys if len(keys) <= 40 else sorted(random.Random(label).sample(keys, 40))
            L += ["", f"### {label} · BY DEFAULT: {len(TD[label])} hits on {len(keys)} pages in "
                  f"{len({k[0] for k in keys})} items (bare or shared-initial hits of the surname, attributed by the "
                  f"judgement file's «default»; kept apart from the hits sorted by first name)", "",
                  f"To vet: {'every page' if vet is keys else 'a blind sample of 40 pages (fixed seed)'}; a page that is "
                  f"another person's goes to them with «assign» in the judgement file.", "",
                  "| item p. PDF page | tier | context |", "|---|---|---|"]
            L += [f"| {k[0]} p.{k[1]} | {pg_d[k][0]} | {pg_d[k][7].replace('|', '/')} |" for k in vet]
        # what each silent item may claim, for this person, at their cutoff (presumed noise counts as silent)
        hit_items = {it for it in rows if read_item(label, it) not in ("silent", "presumed noise")}
        under = sorted(it for it in rows if read_item(label, it) == "underspecified")
        tocon = sorted(it for it in rows if read_item(label, it) == "confirm")
        resid_items = sorted(it for it in rows if read_item(label, it) == "residue")
        groups = collections.defaultdict(list)
        for it in sorted(rows):
            if it in hit_items:
                continue
            line = signed.get(it)
            if not line:
                groups["not signed: the silence says nothing"].append(it)
            else:
                cond = line[1][4].replace("conditions: ", "")
                key = f"signed {line[1][2].split(' · ')[0]}" + ("" if cond == "none" else ", WITH CONDITIONS")
                groups[key].append(it if cond == "none" else f"{it} — conditions: {cond} ({line[0]})")
        L += ["", f"### {label} · no hit: {len(rows) - len(hit_items)} items, by what their silence may claim", ""]
        if not a.stem:
            sil = lambda stop: sum(1 for it in rows if read_item(label, it, stop) in ("silent", "presumed noise"))
            L += [f"Read to **{stop_of[label]}**; an item whose only hits are small caps and run-ins, or join, counts as "
                  f"no hit unless a page is confirmed. At other cutoffs: silent with the exact tier only, "
                  f"{sil('exact')}; up to confusion, {sil('confusion')}; by the rule over every tier, {sil('join')}.", ""]
        for g in sorted(groups):
            L += [f"- **{g}: {len(groups[g])}**"] + [f"  - {x}" for x in groups[g]]
        if under:
            L += [f"- **underspecified, neither present nor silent until the form in the other alphabet is searched: "
                  f"{len(under)}**"] + [f"  - {x}" for x in under]
        if tocon:
            L += [f"- **confirm (translit only, both alphabets searched): neither present nor silent until judged — a "
                  f"confirmed page, a form set aside, or a cutoff above translit: {len(tocon)}**"] + [f"  - {x}" for x in tocon]
        if resid_items:
            L += [f"- **shared-surname residue: the surname is there, but not shown to be this person; neither present "
                  f"nor silent until resolved (judgement «assign») or arbitrated: {len(resid_items)}**"]
            L += [f"  - {x}" for x in resid_items]
        L.append("")
    hit_any = sorted({h[1] for v in T.values() for h in v})
    L += ["## The PDFs, to confirm hits on (pages are PDF pages, not printed ones)", ""]
    L += [f"- {it}: `{os.path.relpath(pdf[it], S) if it in pdf and pdf[it].startswith(S) else pdf.get(it, '?')}`" for it in hit_any]
    open(a.write, "w", encoding="utf-8").write("\n".join(L) + "\n")
    n = sum(len(v) for v in T.values())
    print(f"{len(people)} people × {len(rows)} items · {n} hits ({secs} s) → {a.write}" + ("" if a.from_hits else f" + {hits_tsv}"))


if __name__ == "__main__":
    main()
