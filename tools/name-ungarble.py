#!/usr/bin/env python3
"""The name ungarbler, its first stage: the measure (2026-10-27; the editor: a global pass, and a new phase of the dowse's
postprocessing; on the first measure, the clear garbles, with x's and figures in them, pursued).

    tools/name-ungarble.py measure FACTS-FILE… [--ido IDO-NAMES.tsv] [--tag TAG] [--write]
    tools/name-ungarble.py apply FACTS-FILE… [--tag TAG] (--review | --write)

apply: the classes «transliteration», «ungarblable» and «near a head» as «rename» rows [OLD, qual, NEW, qual,
«legita»] in each source's dowse/<source>/facts-config.json, one per head; the assembler (dowse-facts-assemble.py)
then keeps the form as read in the line, «⟦nomo legita: OLD → NEW⟧». --review writes only the review document
(dowse/NAME-UNGARBLE-REVIEW-<tag>.md, every row); --write writes the rows (a head with a rename row already is left)
and dowse/NAME-UNGARBLE-APPLY-<tag>.md. Then reassemble the sources and harvest.

A dry run: nothing in any facts file is changed. For every head («- $$$ HEAD $$$») of each facts file
(profiles/by-source/<source>-dowse.md), in this order:
  on the roster   its surname, without forename and particles, is a search key or label of the latest
                  dowse/ROSTER-FULL-CROSS-ARC-*.txt («BEAUFRONT» = «de-beaufront | beaufront»; «MAC PIKE» = «mcpike»).
                  The roster is built from the profiles, and the harvest made profiles of earlier garbles (bnexox.md):
                  so a roster entry that is itself garbled by the rules below counts for nothing, neither as the
                  head's home nor as a target;
  known variant   it is a variant name already registered: the harvest's ALIASES (tools/harvest-facts.py) or a
                  «spelling» row of profiles/NAMES-REGISTER.tsv (DOMBROWSKI → DAMBRAUSKAS); the harvest files it right;
  transliteration its transliteration key (skeleton(): V ~ W, -IJ ~ -I, -EV ~ -EF ~ -EFF, -OV ~ -OF ~ -OFF, …) is
                  that of a roster or registered name, or of a head with more lines in all the files measured: a
                  variant name to register (EVSTIFEJEFF beside EVSTIFEJEV);
  Ido roster      it is an Ido surname the dowse roster lacks (the latest dowse/IDO-NAMES-*.tsv, or --ido);
  ungarblable     undoing the OCR's confusions (X→N, 0→O, 1→I or L, 5→S, 6→G, 8→B, and in small capitals R→T, R→I,
                  R→P, C→G; each one alone, then those of the first six all at once) gives a roster or Ido surname, or
                  another head of the same file with more lines: the target is named. R and C, too often a real
                  letter (HEAR is not «heap»), point only to a head of the same file; a head of initials only is left;
  near a head     one letter from a head of the same file with three times its lines (two letters, from 8 letters up,
                  with five times, only for a form garbled by the rules below), or the same letters but for accents («BOCKLER» beside «BÖCKLER»): a variant for the
                  review, not a garble by itself (HAUG beside HAUGG may be two people);
  attested, not folded
                  a riskier fold (near a head, but for accents; R or C read as another letter) whose form is a surname
                  in Wikidata (its family-name items, surnames(): sources/, not tracked): FRIEDEMANN is, PETPERS is not;
  garbled         no target, but the form cannot be a name as printed: a digit or a stray sign; an X after a consonant
                  or before one (but for T, F, W, H, M and a final X); four consonants running, with no H, S, V or W,
                  that do not end in a cluster a syllable can begin with (HOLMGREN's «lmgr» does); no vowel;
  unknown         none of these: most likely a name read right that no list holds yet.
With --write, dowse/NAME-UNGARBLE-MEASURE-<tag>.md (create-only): the counts per file and in all, then every head of
the classes «ungarblable» and «garbled» with its lines and target, and the «unknown» heads with five lines or more.
The next stage, once the measure is reviewed: the targets as «rename» rows in each source's facts-config.json (as
tools/adresaro-numbers.py --apply writes them), then reassembly and harvest. Not built yet. Ezri."""
import argparse, collections, csv, datetime, difflib, glob, itertools, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FL   # a line's own fields (the kind field for --lists, 2026-10-28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
PARTICLES = {"de", "di", "van", "von", "la", "le", "du", "del", "der", "den", "ten", "ter", "da", "dos", "des", "d", "l"}
CONFUSIONS = [("x", "n"), ("0", "o"), ("1", "i"), ("1", "l"), ("5", "s"), ("6", "g"), ("8", "b"),
              ("r", "t"), ("r", "i"), ("r", "p"), ("c", "g"),
              ("c", "e")]   # Ĉ ~ É too, the accents folded (the editor, 2026-10-29 03:1x)
ALL_AT_ONCE = {("x", "n"), ("0", "o"), ("1", "i"), ("5", "s"), ("6", "g"), ("8", "b")}
VOWELS = set("aeiouy")
ONSETS = {"pr", "br", "tr", "dr", "gr", "kr", "fr", "pl", "bl", "kl", "gl", "fl", "sl", "sk", "sp", "st", "ch", "th", "sh", "sc", "kv", "qv", "zk"}

def distance(a, b, cap):
    """Levenshtein distance of a and b, or cap + 1 once it passes cap."""
    if abs(len(a) - len(b)) > cap: return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap: return cap + 1
        prev = cur
    return prev[-1]

_NODECOMP = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ß": "ss", "ł": "l", "Ł": "L",
                           "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "þ": "th", "Þ": "TH"})
def fold(s):
    # the letters NFKD does not decompose written out first: they were dropped, so «Gjørling» read «gjrling», an
    # «impossible cluster», and «Høffding» «hffding» (found 2026-10-28 23:3x)
    return unicodedata.normalize("NFKD", s.translate(_NODECOMP)).encode("ascii", "ignore").decode().lower()

def compact(s):
    """A surname as one key: letters and digits only, «mac» as «mc» («MAC PIKE» → «mcpike»)."""
    c = re.sub(r"[^a-z0-9]", "", fold(s))
    return "mc" + c[3:] if c.startswith("mac") and len(c) > 5 else c

def skeleton(k):
    """A compact key with the known transliterations levelled (the editor, 2026-10-27 19:3x): w → v; a final -ij → -i; a final -ev, -ef, -eff → -ev and -ov, -of, -off → -ov. And two of
    the same kind, for Russian names: a final -iy, -ii, -y after -sk- → -i (Dombrovskiy, Dombrowsky), and a j or i
    between two e's dropped (Evstifejev = Evstifeiev = Evstifeev). «DOMBROVSKIJ» = «DOMBROWSKI» = «dombrovski»."""
    s = k.replace("w", "v")
    s = re.sub(r"([eo])(v|ff?)$", r"\1v", s)
    s = re.sub(r"ij$", "i", s)
    s = re.sub(r"(sk)(iy|ii|y)$", r"\1i", s)
    # between e's only (between any vowels it made BAIO «bao»), and only before the -ev of the end (Evstifejev): else it
    # made Meier «meer» (MEER folded to a Meier of Nürnberg, found at the reassembly, 2026-10-27 20:5x)
    return re.sub(r"(?<=e)[ji](?=ev$)", "", s)

SURNAMES = sorted(glob.glob(os.path.join(G, "sources", "web-2026-10-27-surnames", "wikidata-family-names-*.tsv")))
MAX_RATIO = 0.2   # letters differing, over the name's length (the editor, 2026-10-27 19:4x: two errors in five letters
                  # suspect, two in ten acceptable)

def surnames():
    """The world's surnames as Wikidata has them (the family-name items' native forms and English labels, fetched
    2026-10-27 through QLever; geniza/sources/web-2026-10-27-surnames/, untracked, in _WEB-DOWNLOADS.tsv): compact keys."""
    out = set()
    for p in SURNAMES:
        for l in open(p, encoding="utf-8"):
            m = re.match(r'"(.*)"(?:@[\w-]+)?\s*$', l.strip())
            if m: out.add(compact(m.group(1)))
    return out

def harvest_aliases():
    """The harvest's own variant names (head as written → the head it is filed under): the names register's spellings,
    the harvest's ALIASES since 2026-10-31 (tools/names_register.py; no longer read from the harvest's code)."""
    sys.path.insert(0, os.path.join(ROOT, "tools")); import names_register
    return names_register.aliases()

def head_keys(head):
    """The keys a head may stand under: its surname whole, and without its particles."""
    h = re.sub(r"\s*\(.*?\)", "", head).strip()
    ws = [w for w in re.split(r"[\s’']+", h) if w]
    keys = [compact(h)]
    bare = [w for w in ws if fold(w).strip(".") not in PARTICLES]
    if bare and len(bare) < len(ws): keys.append(compact(" ".join(bare)))
    # the last word alone only when it is a name, never an initial: «W. H. H.» under «h» made every «H.» a fold to it
    # (2026-10-27 20:5x, the first reassembly: 2,264 lines of Amerika Esperantisto; reverted)
    if len(bare) > 1 and len(compact(bare[-1])) >= 4: keys.append(compact(bare[-1]))
    return [k for k in dict.fromkeys(keys) if k]

def implausible(head):
    """Why a head cannot be a name as printed, or ''."""
    h = re.sub(r"\s*\(.*?\)", "", head).strip()
    if re.search(r"\d", h): return "a digit"
    if re.search(r"[^\w\s'’.\-]", h): return "a stray sign"
    if re.search(r"([^\W\d_])\1\1", fold(h)): return "a letter three times"   # QURRRA (the editor, 2026-10-28 23:2x)
    for w in re.split(r"[\s\-'’.]+", fold(h)):
        if not w: continue
        if len(w) >= 3 and not set(w) & VOWELS: return "no vowel"
        for m in re.finditer("x", w):
            i = m.start()
            if i > 0 and w[i - 1] not in VOWELS and not (w[i - 1] == "k" and i + 1 == len(w)):   # Flemish -ckx (Coninckx)
                return "X after a consonant"
            if i + 1 < len(w) and w[i + 1] not in VOWELS and w[i + 1] not in "tfwhm": return "X before a consonant"
        for run in re.findall(r"[^aeiouy]{4,}", w):
            flemish = w.endswith(run) and run.endswith("kx")   # Coninckx, Hendrickx
            if not flemish and not set(run) & set("hsvw") and run[-2:] not in ONSETS: return "four consonants"
    return ""

def variants(k):
    """The key with the OCR's confusions undone: each confusable letter alone, then all of one kind at once."""
    out = set()
    for a, b in CONFUSIONS:
        for i, ch in enumerate(k):
            if ch == a: out.add(k[:i] + b + k[i + 1:])
        if a in k and (a, b) in ALL_AT_ONCE: out.add(k.replace(a, b))
    allx = k
    for a, b in ALL_AT_ONCE: allx = allx.replace(a, b)
    out.add(allx); out.discard(k)
    return out

def variants_sure(k):
    """The variants by the first six confusions only (a digit or an X for a letter): these may name a roster or Ido
    surname; the small capitals' R and C, too often a real letter, only another head of the same file."""
    out = set()
    for a, b in CONFUSIONS[:7]:
        for i, ch in enumerate(k):
            if ch == a: out.add(k[:i] + b + k[i + 1:])
    allx = k
    for a, b in ALL_AT_ONCE: allx = allx.replace(a, b)
    out.add(allx); out.discard(k)
    return out

FOLD = ("transliteration", "ungarblable", "near a head")   # the classes folded (the editor, 19:3x: both reliable)

def target_head(t):
    """The head a fold goes to, from the measure's target: a head of the files, a roster label (its profile's own
    heading, «# JANOTTA — rikoltita profilo»), a registered main form, or an Ido name's surname."""
    m = re.match(r"head: (.+?) \(\d+(?: in all files)?\)", t)
    if m: return m.group(1)
    m = re.match(r"roster: (.+)", t)
    if m:
        lab = m.group(1).strip()
        p = os.path.join(G, "profiles", f"{lab}.md")
        if os.path.exists(p):
            first = open(p, encoding="utf-8").readline()
            mm = re.match(r"# (.+?) — ", first)
            if mm and mm.group(1) == mm.group(1).upper(): return mm.group(1)   # a heading that is no head («a Meier
            return ""   # of Nürnberg (ten subscriptions …)», a description): no target
        return lab if lab.upper() == lab else ""
    m = re.match(r"Ido roster: (.+)", t)
    if m: return m.group(1).split(" / ")[0].split()[-1].upper()
    return ""

def unwrite(facts):
    """Every «legita» row out of the sources' configs (the folds undone, for a clean rewrite); other rename rows kept."""
    import json
    for fp in facts:
        src = re.sub(r"-dowse\.md$", "", os.path.basename(fp))
        cp = os.path.join(G, "dowse", src, "facts-config.json")
        if not os.path.exists(cp): continue
        cfg = json.load(open(cp, encoding="utf-8"))
        keep = [r for r in cfg.get("rename", []) if not (len(r) > 4 and r[4] == "legita")]
        if len(keep) == len(cfg.get("rename", [])): continue
        print(f"{src}: {len(cfg['rename']) - len(keep)} «legita» rows out")
        cfg["rename"] = keep
        with open(cp + ".tmp", "w", encoding="utf-8") as fh: json.dump(cfg, fh, ensure_ascii=False, indent=1); fh.write("\n")
        os.replace(cp + ".tmp", cp)

_K2I, _FACTS, _TEXTS = {}, {}, {}
def ocr_context(src, name, lists, most=3):
    """The OCR as it stands at a candidate's lines (the editor, 2026-10-28 18:0x): up to `most` of the source's lines that carry the name
    (its head, or with lists the name inside a kind), each as its locator and the text file's lines l. N-1 to N+1.
    -> [(locator, [text lines])]."""
    if not _K2I:
        for r in csv.DictReader((l for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            _K2I[r["key"]] = r["item"]; _K2I.setdefault(r["item"], r["item"])
    fp = os.path.join(G, "profiles", "by-source", f"{src}-dowse.md")
    if fp not in _FACTS:   # each file parsed once, indexed by head (the first runs parsed it once a candidate)
        fs = [f for f in (FL.fields(l) for l in open(fp, encoding="utf-8") if l.startswith("- $$$")) if f]
        byh = collections.defaultdict(list)
        for f in fs: byh[re.sub(r"\s*\(.*", "", f["head"]).strip()].append(f)
        _FACTS[fp] = (fs, byh)
    fs, byh = _FACTS[fp]
    if not lists: hits = byh.get(name, [])[:most]
    else:
        rx = re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")
        hits = [f for f in fs if rx.search(f.get("kind") or "")][:most]
    out = []
    for f in hits:
        loc = f.get("locator") or ""
        m = re.match(r"(.+?), (?:PDF \d+.*?, )?l\. (\d+)", loc) or re.match(r"(.+?), ¶ (\d+)", loc)
        item = _K2I.get(m.group(1).strip()) if m else None
        text = None
        for d in ("ocr-preferred", "born-digital-text"):
            p = os.path.join(G, "sources", d, f"{item}.txt") if item else ""
            if p and os.path.exists(p):
                if p not in _TEXTS:   # each text read once, its page starts with it (the first run took 25 minutes)
                    tl = open(p, encoding="utf-8").read().split("\n")
                    _TEXTS[p] = (tl, [i for i, x in enumerate(tl) if x.startswith("=== page ")])
                text, _starts = _TEXTS[p]; break
        if not (m and text) or "¶" in loc:
            out.append((loc, [f"(the OCR line not found by the locator; the anchor: «{(f.get('anchor') or '')[:160]}»)"])); continue
        k = int(m.group(2))
        # the name as read anywhere on the line's PDF page (its last word of three letters or more, case and accents
        # folded, a whole word), each such line with its number; else the anchor's line and its neighbours, blank lines
        # skipped (the first version showed only l. N ± 1, where a «kun:» name seldom stands: LOWE, 2026-10-28 18:0x)
        pm = re.search(r"PDF (\d+)", loc)
        lo, hi = 0, len(text)
        if pm:
            starts = _starts
            at = [i for i in starts if text[i].startswith(f"=== page {pm.group(1)} ")]
            if at: lo = at[0]; hi = next((i for i in starts if i > lo), len(text))
        ws = [w for w in re.findall(r"[^\W\d_]{3,}", name)] or [name]
        key = fold(ws[-1]).lower()
        found = [i for i in range(lo, hi) if re.search(rf"(?<![^\W\d_]){re.escape(key)}(?![^\W\d_])", fold(text[i]).lower())]
        if found:
            out.append((loc, [f"l. {i + 1}: {text[i].strip()}" for i in found[:4]] + ([f"… {len(found) - 4} more on the page"] if len(found) > 4 else [])))
        else:
            near = [i for i in range(max(0, k - 4), min(len(text), k + 3)) if text[i].strip()][:4]
            out.append((loc, [f"(«{ws[-1]}» not on PDF {pm.group(1) if pm else '?'} as a word; the anchor's line and neighbours:)"]
                        + [f"l. {i + 1}: {text[i].strip()}" for i in near]))
    return out

def apply_scored(paths, a):
    """apply-scored SCORES.tsv… --min 1 (--review | --write) --tag T (2026-10-30; the editor 16:3x, on the folds of tag
    2026-10-30l): every fold scored at --min or more, heads and list names
    alike, as a «rename» row marked «legita» in its source's dowse/<source>/facts-config.json, as `apply` writes them
    (a head with a rename row already is left). Left: a head with an open vision request (runbook D4b), a fold with no
    usable target, a head with two targets at --min or more. Writes dowse/NAME-UNGARBLE-APPLY-SCORED-<T>.md (create-only)."""
    import json
    held = set()
    for r in csv.reader(open(os.path.join(G, "ocr", "VISION-REQUESTS.tsv"), encoding="utf-8"), delimiter="\t"):
        if len(r) > 10 and r[10].strip().startswith("held"): held |= set(re.findall(r"the head as read «([^»]+)»", r[6]))
    best = {}   # (source, head as read) → [(score, target, from)]
    for p in paths:
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
            if float(r["score"]) >= a.min: best.setdefault((r["source"], r["as read"]), []).append((float(r["score"]), r["target"], os.path.basename(p)))
    per, left = collections.defaultdict(list), []
    for (src, h), cands in sorted(best.items()):
        tgts = {t for _s, t, _p in cands}
        s = max(x[0] for x in cands)
        if len(tgts) > 1: left.append((src, h, s, " / ".join(sorted(tgts)), "two targets at the bar")); continue
        new = tgts.pop()
        if h in held: left.append((src, h, s, new, "an open vision request")); continue
        m = re.match(r"(.+?)(?: \((.*)\))?$", h); name, q = m.group(1).strip(), (m.group(2) or "").strip()
        sig = compact(new) == compact(h) and all(len(w.strip(".")) <= 2 for w in re.split(r"[\s\-—]+", new) if w)
        if not new or (implausible(new) and not sig) or new == name: left.append((src, h, s, new, "no usable target")); continue
        nm = re.match(r"(.+?)(?: \((.*)\))?$", new)
        per[src].append((name, q, nm.group(1).strip(), (nm.group(2) or "").strip(), s, ", ".join(sorted({x[2] for x in cands}))))
    out = os.path.join(G, "dowse", f"NAME-UNGARBLE-APPLY-SCORED-{a.tag}.md")
    if os.path.exists(out): sys.exit("refusing to overwrite: " + out)
    written, had, nocfg = collections.Counter(), collections.Counter(), []
    for src, folds in sorted(per.items()):
        cp = os.path.join(G, "dowse", src, "facts-config.json")
        if not os.path.exists(cp): nocfg.append(src); continue
        cfg = json.load(open(cp, encoding="utf-8"))
        have = {(r[0], r[1]) for r in cfg.get("rename", [])}
        for name, q, new, nq, *_ in folds:
            if (name, q) in have: had[src] += 1; continue
            if a.write: cfg.setdefault("rename", []).append([name, q, new, nq, "legita"]); have.add((name, q))
            written[src] += 1
        if a.write and written[src]:
            with open(cp + ".tmp", "w", encoding="utf-8") as fh: json.dump(cfg, fh, ensure_ascii=False, indent=1); fh.write("\n")
            os.replace(cp + ".tmp", cp)
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The name ungarbler: the scored folds {'written' if a.write else 'for review'} ({a.tag})\n\n`[GENERATED by tools/name-ungarble.py "
                 f"apply-scored. Do not hand-edit — re-run it.]`\n\nFrom {', '.join(os.path.basename(p) for p in paths)}, every fold at {a.min:+g} or more. "
                 + (f"**{sum(written.values())} «rename» rows marked «legita» written** into the sources' `facts-config.json`" if a.write else
                    f"**For review: nothing written.** {sum(written.values())} rows would be written")
                 + f"; {sum(had.values())} heads had a rename row already, left. Each line folded keeps «⟦nomo legita: OLD → NEW⟧» at its next "
                 "assembly; to undo a fold, remove its row and reassemble.\n\n" + (f"No facts-config.json: {', '.join(nocfg)}\n\n" if nocfg else ""))
        fh.write("| score | source | head as read | folded to | from |\n|---:|---|---|---|---|\n")
        for src, folds in sorted(per.items()):
            for name, q, new, nq, s, frm in sorted(folds, key=lambda f: (-f[4], f[0])):
                fh.write(f"| {s:+g} | {src} | {name}{f' ({q})' if q else ''} | {new}{f' ({nq})' if nq else ''} | {frm} |\n")
        if left:
            fh.write(f"\n## Left ({len(left)})\n\n| score | source | head as read | target | why |\n|---:|---|---|---|---|\n")
            for src, h, s, t, why in sorted(left, key=lambda x: (x[4], x[0], x[1])): fh.write(f"| {s:+g} | {src} | {h} | {t} | {why} |\n")
    print(f"{sum(written.values())} rows {'written' if a.write else 'to write'} in {len([s for s in written if written[s]])} sources; "
          f"{sum(had.values())} had a row already; {len(left)} left (" + ", ".join(f"{k} {v}" for k, v in collections.Counter(x[4] for x in left).items())
          + f"); {'missing config: ' + ', '.join(nocfg) if nocfg else 'every config found'} → {os.path.relpath(out, ROOT)}")

def apply(rows, a, out):
    """The folds as «rename» rows marked «legita», one per head, into each source's dowse/<source>/facts-config.json
    (with --write; a head that already has a rename row is left as it is), and the review document of every row."""
    import json
    per = collections.defaultdict(list); skipped = []
    held = set()   # heads with an open vision request: no judgement until the vision text (runbook D4b)
    for r in csv.reader(open(os.path.join(G, "ocr", "VISION-REQUESTS.tsv"), encoding="utf-8"), delimiter="\t"):
        # held while Ezri's status holds it («held: no judgement until the vision text and the redowse»), whatever
        # Miles's (a request read by vision stays held until the redowse brings the new text)
        if len(r) > 10 and r[10].strip().startswith("held"): held |= set(re.findall(r"the head as read «([^»]+)»", r[6]))
    for c in FOLD:
        for src, h, n, t in rows[c]:
            if h in held: skipped.append((src, h, n, t, "an open vision request")); continue
            new = target_head(t)
            m = re.match(r"(.+?)(?: \((.*)\))?$", h)
            name, q = m.group(1).strip(), (m.group(2) or "").strip()
            # a signature of initials folds to the same initials however dotted or dashed («P. NN.», «P. NN» → «P. N—N»;
            # the editor, 20:3x); any other garbled target is no target
            sig = bool(new) and compact(new) == compact(h) and all(len(w.strip(".")) <= 2 for w in re.split(r"[\s\-—]+", new) if w)
            if not new or (implausible(new) and not sig) or new == name:
                skipped.append((src, h, n, t, "no usable target")); continue
            nm = re.match(r"(.+?)(?: \((.*)\))?$", new)
            per[src].append((name, q, nm.group(1).strip(), (nm.group(2) or "").strip(), c, n, t))
    total = sum(len(v) for v in per.values())
    print(f"{total} folds in {len(per)} sources ({sum(x[5] for v in per.values() for x in v)} lines); {len(skipped)} left (no usable target)")
    if not (a.write or a.review): return
    written = collections.Counter(); nocfg = []
    for src, folds in sorted(per.items()):
        cp = os.path.join(G, "dowse", src, "facts-config.json")
        if not os.path.exists(cp): nocfg.append(src); continue
        if not a.write: written[src] = len(folds); continue   # --review: the document only, no config touched
        cfg = json.load(open(cp, encoding="utf-8"))
        have = {(r[0], r[1]) for r in cfg.get("rename", [])}
        for name, q, new, nq, *_ in folds:
            if (name, q) in have: continue
            cfg.setdefault("rename", []).append([name, q, new, nq, "legita"]); have.add((name, q)); written[src] += 1
        tmp = cp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(cfg, fh, ensure_ascii=False, indent=1); fh.write("\n")
        os.replace(tmp, cp)
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The name ungarbler: the folds written ({a.tag})\n\n`[GENERATED by tools/name-ungarble.py apply. Do not hand-edit — re-run it.]`\n\n")
        fh.write((f"{sum(written.values())} «rename» rows marked «legita» written into the sources' `facts-config.json`" if a.write else
                  f"**For review: nothing written.** {sum(written.values())} «rename» rows marked «legita» would go into the sources' `facts-config.json` "
                  f"(`apply … --tag {a.tag} --write`)") + "; each line folded keeps "
                 "«⟦nomo legita: OLD → NEW⟧» at its next assembly. To undo a fold, remove its row and reassemble.\n\n")
        if nocfg: fh.write("No facts-config.json, not written: " + ", ".join(nocfg) + "\n\n")
        # by class, then by the letters the fold changes (the editor, 2026-10-28 17:5x; two-letter folds by
        # letter distance next), then by file and lines
        allf = [(src,) + f for src, folds in per.items() for f in folds]
        dist = lambda f: distance(compact(f[1]), compact(f[3]), 4)
        for c in FOLD:
            sel = sorted((f for f in allf if f[5] == c), key=lambda f: (dist(f), f[0], -f[6], f[1]))
            if not sel: continue
            if a.context:   # each candidate followed by the OCR at its lines, numbered for the editor's queries
                fh.write(f"\n## {c} ({len(sel)})\n\n")
                for i, (src, name, q, new, nq, _c, n, t) in enumerate(sel, 1):
                    d = dist((src, name, q, new))
                    fh.write(f"**{c[0].upper()}{i}. {name}{f' ({q})' if q else ''} → {new}{f' ({nq})' if nq else ''}** · {d if d < 4 else '4+'} letter{'s' if d != 1 else ''} · "
                             f"{src} · {n} {'place' if a.lists else 'line'}{'s' if n != 1 else ''} · {t}\n\n")
                    for loc, tl in ocr_context(src, name, a.lists):
                        fh.write(f"- `{loc}`\n\n  ```\n" + "".join(f"  {x}\n" for x in tl) + "  ```\n\n")
                continue
            fh.write(f"\n## {c} ({len(sel)})\n\n| letters changed | file | head as read | lines | folded to | the measure's evidence |\n|---|---|---|---|---|---|\n")
            for src, name, q, new, nq, _c, n, t in sel:
                d = dist((src, name, q, new))
                fh.write(f"| {d if d < 4 else '4+'} | {src} | {name}{f' ({q})' if q else ''} | {n} | {new}{f' ({nq})' if nq else ''} | {t} |\n")
        if skipped:
            fh.write(f"\n## Left: no usable target, or an open vision request ({len(skipped)})\n\n| file | head | lines | the measure's evidence | why left |\n|---|---|---|---|---|\n")
            for src, h, n, t, why in skipped: fh.write(f"| {src} | {h} | {n} | {t} | {why} |\n")
    print("wrote", os.path.relpath(out, ROOT), "and", ", ".join(f"{s} {k}" for s, k in written.items()))

# THE SCORING (the editor, 2026-10-28 19:2x: the de-garbling scored, with points for and against each fold, and the
# rankings tried; the editor's first points below, «name» the name as OCR'd). Each point ±1 until he weighs them; `score --weights F` takes a TSV «feature<TAB>points».
WEIGHTS = {   # the editor's weights, 2026-10-28 22:1x (A1–A4, F1–F7 as he numbered them)
    "a one-letter change in a name of five letters or fewer": -2,                 # A1
    "the first letter added or dropped, title case to title case": -4,            # A2 (the editor: added or dropped, not changed)
    # A3 split by its leg (the editor, 2026-10-30 16:2x: −3 tried, then split, the corpus leg
    # mistrusted; the corpus-only leg perhaps as low as −1): a Wikidata surname
    # −3 (BOUCHER, FERRER, PORTER), the corpus leg alone −1, the recurring garbles' (AGOSRON 12 items, HASREY 10; the
    # editor, 16:3x: −1 accepted)
    "the name as read is a surname in Wikidata": -3,                                        # A3
    "the name as read stands in five corpus items or more, not in Wikidata": -1,            # A8
    "the OCR added a letter at the start or end": -1,                             # A5 (23:2x)
    # A4, the editor's rule of 2026-10-27 19:4x (the letter errors divided by the surname's length,
    # two in five letters suspect), on the case-aware distance (KANTARĜIEV → AKTARGIEV, 4)
    "the distance over the length is past MAX_RATIO": -2,
    "the target is on the roster, the name is not": +0.5,                         # F1
    "the target heads five times the lines or more": +1,                          # F2
    "a known transliteration": +2,                                                # F3
    "every letter changed is a known OCR confusion": +1,                          # F4
    "only a space differs": +1,                                                   # F5
    "the name has impossible clusters": +2,                                       # F6
    "the name has an X in it": +2,                                                # F7
    # A6 (the editor, 2026-10-29 12:0x, on OSTROVSKAJA → OSTROVSKIJ at −2.5: a new penalty,
    # A6, −4, for the known feminine and masculine suffix pairs): the gender pair is never folded by `apply`, and now scores so
    "a feminine form beside the masculine": -4,                                   # A6
    # F4 moved by the confusion's share (below, changes())
    # (the editor, 16:1x: +2 at 30% or more, +1.5 between 10% and 30%, +1 at 10% or less; his first tiers, 15:5x–16:0x, +2, +1, +0.5, moved no fold up)
    "F4 at 30% or more of the wrong readings: F4 counts +2": +1,                  # F9
    "F4 between 10% and 30% of the wrong readings: F4 counts +1.5": +0.5,         # F10
    "F4 at 10% or under of the wrong readings: F4 counts +1": 0,                  # F11
}
# the known feminine and masculine endings (the editor, 2026-10-28 18:5x and 23:2x–23:3x), for the measure and A6 alike
FEM = (("ova", "ov"), ("eva", "ev"), ("ina", "in"), ("ska", "ski"), ("cka", "cki"), ("zka", "zki")) + \
      tuple((fe, ma) for fe in ("aja", "aya") for ma in ("ij", "iy", "ii", "y", "i"))
def gender(x, y): return any(x.endswith(f) and y == x[:-len(f)] + m for f, m in FEM)
OCR_PAIRS = {frozenset(p) for p in CONFUSIONS} | {frozenset(("c", "e")), frozenset(("e", "o")), frozenset(("n", "u")),
                                                  frozenset(("i", "l")), frozenset(("h", "b")), frozenset(("rn", "m"))}

def hard_cluster(word):
    """A consonant cluster that sonority will not allow (the editor, 2026-10-29 03:0x: the sonority principle, more aggressively: DARCNICOURR's «rcn», FRXOR, WVLER): a word's onset must be one consonant, an
    obstruent before l, r or a glide, or s before a stop (and then l or r); inside a word, three consonants or more must
    end in such an onset or hold an s. Digraphs (ch, sh, th, ph, ck, gh, sch) count as one consonant, x as two.
    The onsets the European names have besides (kn, gn, pf, ps, sch- before a sonorant, ts, z-, mc) pass; inside a word,
    three consonants pass as a sonorant, an obstruent, then l, r or a glide (ntr, mbl), or a sonorant, t or d, then a
    sonorant (HARTMANN, LINDNER), or before an h (BERNHARD); anything with s or z passes. Doubles count once.
    -> the cluster, or ''."""
    if re.search(r"[\s\-]", word.strip()):
        return next((c for c in map(hard_cluster, re.split(r"[\s\-]+", word.strip())) if c), "")
    w = re.sub(r"sch|ch|sh|th|ph|ck|gh|kh|qu", "C", fold(word).lower()).replace("pf", "F").replace("x", "ks")   # kh: KHANNA
    w = re.sub(r"([^aeiouy])\1+", r"\1", w)
    OBS, SON, LIQ = set("bcdfghkpqtvzCF"), set("lmnrwj"), set("lrwj")
    INIT = {"kn", "gn", "rh", "wr", "wh", "vl", "vr", "wl", "ps", "pn", "pt", "ts", "tz", "tC", "mc", "dz", "Cl", "Cm", "Cn", "Cr", "Cw", "zw", "zv", "sz", "Cv"}
    def onset_ok(c, initial=False):
        if len(c) <= 1 or (initial and c in INIT): return True
        if c[0] == "s" and (c[1] in "ptkcCmnlwv"): return len(c) == 2 or (len(c) == 3 and c[1] in "ptkcC" and c[2] in "lrw")
        if initial and len(c) == 3 and c[:2] in INIT and c[2] in LIQ: return True   # pfl, schw-r…
        return len(c) == 2 and c[0] in OBS and c[1] in LIQ
    m = re.match(r"[^aeiouy]+", w)
    if m and not onset_ok(m.group(0), True): return m.group(0)
    for mm in re.finditer(r"(?<=[aeiouy])[^aeiouy]{3,}(?=[aeiouy])", w):
        c = mm.group(0)
        if "s" in c or "z" in c or c[-1] == "h": continue
        if len(c) == 3 and c[0] in SON and c[1] in OBS and c[2] in LIQ: continue
        if len(c) == 3 and c[0] in SON and c[1] in "td" and c[2] in SON: continue
        if len(c) == 3 and onset_ok(c[1:]): continue   # a coda, then an onset that rises (GOTTFRIED's t|fr)
        return c
    # at the end of a word, an obstruent before r or a nasal (MONRROSIGR's «-gr»; the editor, 2026-10-29 12:0x: it should have
    # scored higher for its impossible cluster); not before l, the Austrian and Bavarian -dl, -gl, -kl (MANDL, SIEGL)
    m = re.search(r"(?<=[aeiouy])[^aeiouy]{2,}$", w)
    if m and m.group(0)[-1] in "rmn" and m.group(0)[-2] in OBS: return m.group(0)
    return ""

THIN = set("il1jtf'’|")   # the strokes the OCR adds from a speck or crack, or loses (the editor, 23:4x: F8 within F4)
SPLITS = [("rn", "m"), ("ri", "n"), ("ii", "u"), ("vv", "w"), ("cl", "d"), ("in", "m"), ("li", "h")]

# THE CONFUSION'S SHARE (the editor, 2026-10-30 15:5x: +1 more where the change is over 30% of the class, −0.5
# where it is under 10%): F4's point moved by the share of the truth letter
# that the OCR confusions survey measured for the change (tools/ocr-confusions.py, the vision and born-digital truth of
# 2026-10-29), in its class: old print (the dowse's scans), the truth letter's case. A fold of several changes goes by
# its least confusable one; a change of case alone is no letter change. A change the survey never saw twice has share 0.
# The share READ-SIDE (the editor, 16:2x; the share of the truth letter left the
# garbler's own swaps under 3%, N→X 1.4%): of the OCR's wrong readings of a letter or group as written, the share whose
# truth is the fold's letter (N→X: 63.1% of the wrong X in old capitals are N), from the survey's counts; read_of()
HIGH, LOW = 0.30, 0.10
TIERS = ("F4 at 30% or more of the wrong readings: F4 counts +2", "F4 between 10% and 30% of the wrong readings: F4 counts +1.5",
         "F4 at 10% or under of the wrong readings: F4 counts +1")
def f4_tier(ch):
    """The F4 tier of a fold's changes, by the least confusable."""
    m = min(s_ for _k, s_ in ch)
    return TIERS[0] if m >= HIGH else TIERS[2] if m <= LOW else TIERS[1]
SURVEY = sorted(glob.glob(os.path.join(G, "ocr", "method", "OCR-CONFUSIONS-SURVEY-*.tsv")))
SHARE, SEEN_CHANGES = {}, collections.defaultdict(set)   # (case, truth, written) → share; → the folds it stands in

def share_of(k):
    if not SHARE and SURVEY:
        for r in csv.DictReader((l for l in open(SURVEY[-1], encoding="utf-8") if not l.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["print"] == "old":   # written in either case, one change
                kk = (r["case"], r["letter"], r["written"].lower()); SHARE[kk] = SHARE.get(kk, 0) + float(r["share"])
    return SHARE.get(k, 0.0)

WRONG, WRONG_OF = collections.Counter(), collections.Counter()   # (case, truth, written) → count; (case, written) → count
def read_of(k):
    """Of the OCR's wrong readings written k[2] (truth in case k[0]), the share whose truth is k[1]; 0 if never seen twice."""
    if not WRONG_OF and SURVEY:
        for r in csv.DictReader((l for l in open(SURVEY[-1], encoding="utf-8") if not l.startswith("#")), delimiter="\t", quoting=csv.QUOTE_NONE):
            w = r["written"].lower()
            if r["print"] == "old" and w != r["letter"]:
                WRONG[(r["case"], r["letter"], w)] += int(r["count"]); WRONG_OF[(r["case"], w)] += int(r["count"])
    return WRONG[k] / WRONG_OF[(k[0], k[2])] if WRONG_OF[(k[0], k[2])] else 0.0

def changes(ocr, tgt, ed=None):
    """A fold's letter changes as the survey keys them, (case, truth, written), each with its read-side share. Span by
    span (the editor, 16:2x, on rewrites of n letters as m, ii as ü): each run of
    differing letters looked up whole when the survey has it, up to three letters a side (ü as «ii», 154 times; H as
    «ll», m as «rn» or «in», w as «iv»); else letter by letter. A change of case alone is none. ed: unused, kept for the
    callers."""
    case = lambda ch: "upper" if ch.isupper() else "lower"
    read_of(("", "", ""))   # the survey's counts loaded
    if ed is None: ed = [e for e in wdist(ocr, tgt)[1] if " " not in (e[1] + e[2])]
    ed = [e for e in ed if not (e[0] == "sub" and e[1].lower() == e[2].lower()) and "-" not in (e[1] + e[2])]
    # the edits in runs: each next edit at the place the last one left off (wdist's positions are in the OCR form)
    runs = []
    for e in ed:
        if runs and e[3] == runs[-1][-1][3] + (0 if runs[-1][-1][0] == "ins" else 1): runs[-1].append(e)
        else: runs.append([e])
    def one(e):
        op, x, y, i = e
        if op in ("sub", "ins"): k = (case(y), y.lower(), x.lower()); return (k, read_of(k))
        # a letter the OCR added: the truth letter beside it written with it (truth «t» as «tr»)
        ks = ([(case(ocr[i - 1]), ocr[i - 1].lower(), (ocr[i - 1] + x).lower())] if i > 0 else []) + \
             ([(case(ocr[i + 1]), ocr[i + 1].lower(), (x + ocr[i + 1]).lower())] if i + 1 < len(ocr) else [])
        return max(((k, read_of(k)) for k in ks), key=lambda ks_: ks_[1], default=((case(x), "", x.lower()), 0.0))
    out = []
    for run in runs:
        w, t_ = "".join(e[1] for e in run).lower(), "".join(e[2] for e in run)
        if len(run) > 1 and t_ and len(t_) <= 3 and len(w) <= 3 and WRONG[(case(t_[0]), t_.lower(), w)]:
            k = (case(t_[0]), t_.lower(), w); out.append((k, read_of(k)))   # the span whole (ü as «ii»)
        else: out += [one(e) for e in run]
    return out

def known_changes(ch):
    """F4 for a fold with a many-letter span (ü as «ii», H as «ll»): that span seen five times or more in the survey (the
    register's bar), and every other change one the old test passes (OCR_PAIRS, an accent, a thin stroke lost or
    added). Single letters stay with the old test: the survey's bar alone gave 591 more head folds F4 (V→Y, X→K)."""
    multi = False
    for k, _s in ch:
        t_, w = k[1], k[2]
        if len(t_) == 1 and len(w) == 1: ok = fold(t_) == fold(w) or frozenset((fold(t_), fold(w))) in OCR_PAIRS
        elif len(t_) == 1 and not w: ok = t_ in THIN
        elif len(t_) == 1 and len(w) == 2 and t_ in (w[0], w[1]): ok = (w[1] if w[0] == t_ else w[0]) in THIN
        else: multi, ok = True, WRONG[k] >= 5
        if not ok: return False
    return multi

def skel2(k):
    """skeleton(), with the editor's transliterations for the scoring (2026-10-28): -y ~ -i ~ -ij ~ -iy at any final (19:2x);
    CiV ~ CjV (DIAKONOV ~ DJAKONOV), ou ~ u, a double consonant ~ a single one (23:2x)."""
    s = re.sub(r"(iy|ij|ii|y)$", "i", skeleton(k))
    s = re.sub(r"^je", "e", s.replace("lj", "l"))   # lj ~ l, initial je- ~ e- (the editor, 2026-10-29 03:2x)
    s = re.sub(r"(?<=[bcdfghjklmnpqrstvwxz])j(?=[aeiou])", "i", s)
    s = re.sub(r"(?<=[aeiou])[jy]", "i", s)   # Vi ~ Vj ~ Vy, MIKOLAISKI ~ MIKOLAJSKI (the editor, 2026-10-29 03:0x)
    s = s.replace("ou", "u").replace("tc", "tz")   # tc ~ tz (the editor, 2026-10-29 03:0x)
    # Rh- ~ R-, a name variant (the editor, 2026-10-29 12:0x); Kh, Ch and Ph in score_one, by the name's language
    s = s.replace("rh", "r")
    return re.sub(r"([bcdfghjklmnpqrstvwxz])\1+", r"\1", s)

# a Slavic or Greek name, by its ending or its letters (the F6 test's, and Greek -ides, -akis, -poulos …)
SLAVGREEK = re.compile(r"([iy][cćĉč]|ov|ev|in|ski|skij|sky|enko|vi[cćĉč]|ova|eva|ina|aja|ides|idis|iades|iadis|akis|akos|oulos|opoulou|atos)$")
def slavgreek(name):
    n = re.sub(r"\s*\(.*", "", name)
    return bool(SLAVGREEK.search(fold(n).lower()) or re.search(r"[ĉĝĵŝŭžšćč]", n.lower()))

def kx(s, sg):
    """Kh ~ H ~ Ĥ and Ph ~ F everywhere, Ch ~ H only in a Slavic or Greek name (the editor, 2026-10-29 12:2x: ECKHERT ~
    ECHERT is no transliteration)."""
    s = re.sub(r"(?<!c)kh", "h", s).replace("ph", "f")   # not the «ck» + h of ECKHERT
    return s.replace("ch", "h") if sg else s

def destud(w):
    """Studly caps split: «DeGrof» → «De Grof» (the editor: the name as printed, to be normalised so)."""
    # only before a capital that a small letter follows («DeGrof»), never inside a garble's capitals («PorgANskij»)
    return re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Þ][a-zà-ÿ])", " ", w)

def wdist(a, b):
    """A weighted Levenshtein of two forms as printed (the editor, 2026-10-28 19:1x–19:2x): a change of case is an edit
    (it counts; unless the word is in capitals, when both are compared in capitals), a space inserted or lost counts
    0.5. -> (distance, [edits as (op, from, to, position in a)])."""
    n, m = len(a), len(b)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): D[i][0] = D[i - 1][0] + (0.5 if a[i - 1] == " " else 1)
    for j in range(1, m + 1): D[0][j] = D[0][j - 1] + (0.5 if b[j - 1] == " " else 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = 0 if a[i - 1] == b[j - 1] else 1
            D[i][j] = min(D[i - 1][j] + (0.5 if a[i - 1] == " " else 1), D[i][j - 1] + (0.5 if b[j - 1] == " " else 1), D[i - 1][j - 1] + sub)
    i, j, ed = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1):
            if a[i - 1] != b[j - 1]: ed.append(("sub", a[i - 1], b[j - 1], i - 1))
            i, j = i - 1, j - 1
        elif i > 0 and D[i][j] == D[i - 1][j] + (0.5 if a[i - 1] == " " else 1):
            ed.append(("del", a[i - 1], "", i - 1)); i -= 1
        else:
            ed.append(("ins", "", b[j - 1], i)); j -= 1
    return D[n][m], ed[::-1]

def ocr_word(lines, word):
    """The word as the OCR prints it, from a candidate's page lines; None if it is not there."""
    key = fold(word).lower()
    for l in lines:
        for m in re.finditer(r"[^\W\d_][^\W\d_'’\-]*", l.split(": ", 1)[-1]):
            if fold(m.group(0)).lower() == key: return m.group(0)
    return None

def score_one(h, n, tg, tlines, name_on_roster, tgt_on_roster, attest, ctx, W):
    """The features a fold of the head as read h (n lines) to tg (tlines) has, and its score. ctx: its OCR page lines."""
    # the word that the fold changes, not the last word (KANALOŜI-LEFLER → KANALOŜŜI-LEFLER was judged by «LEFLER»,
    # a real surname, 2026-10-29 02:3x): of the same number of words, the first pair that differs; else the last word
    # an apostrophe inside a word is kept, the OCR's ' for l or i (DE THÉ'IN → DE THÉLIN; the editor, 2026-10-29 12:0x)
    # but not the elision after a single letter, L' D' O' (L'ABENSKI, D'ARROIS: the particle stays apart, as before)
    WRD = r"[^\W\d_](?:[^\W\d_]|(?<=[^\W\d_]{2})['’](?=[^\W\d_]))+"
    hw = re.findall(WRD, re.sub(r"\s*\(.*", "", h)) or [h]
    gw = re.findall(WRD, re.sub(r"\s*\(.*", "", tg)) or [tg]
    pair = next(((x, y) for x, y in zip(hw, gw) if compact(x) != compact(y)), None) if len(hw) == len(gw) else None
    nw, tw = pair or (hw[-1], gw[-1])
    # of a different number of words, the whole names (FLEURDELYS → FLEUR DE LYS was judged as «FLEURDELYS» against
    # «LYS», −11; the editor, 2026-10-29 03:1x: a missing space a minor score)
    # unless the longer has particles in front that the shorter lacks (COUTADES → DE CONTADES is judged as COUTADES
    # against CONTADES; DEROO → DE ROY stays whole, the particle is in the name as read)
    if len(hw) != len(gw):
        nw, tw = " ".join(hw), " ".join(gw)
        PART = {"de", "du", "des", "le", "la", "les", "van", "von", "der", "den", "di", "da", "del", "della", "ten", "ter"}
        lo, sh = (hw, gw) if len(hw) > len(gw) else (gw, hw)
        k = 0
        while k < len(lo) - len(sh) and lo[k].lower() in PART: k += 1
        if compact(nw).replace(" ", "") != compact(tw).replace(" ", "") and len(lo) - k == len(sh) and k and \
                not fold(sh[0]).lower().startswith(fold(lo[0]).lower()):
            rest = lo[k:]
            pair = next(((x, y) for x, y in zip(rest if lo is hw else sh, sh if lo is hw else rest) if compact(x) != compact(y)), None)
            nw, tw = pair or (hw[-1], gw[-1])
    seen = ocr_word([x for _l, ls in ctx for x in ls], nw)
    ocr = destud(seen) if seen else nw.title()
    # AN INITIAL RUN INTO THE NAME, two capitals before small letters («KFaudemer»: K. Faudemer; the editor, 2026-10-29
    # 12:0x: the initial's penalty does not apply, a clear case of K Faudemer): the initial taken off,
    # a lost space and no more
    run_in = bool(re.match(r"^[A-ZÀ-Þ][A-ZÀ-Þ][a-zà-ÿ]{2,}$", ocr)) and compact(nw[1:]) == compact(tw)
    if run_in: ocr, nw = ocr[1:], nw[1:]
    # garbled capitals (a capital after the first letter that is no studly split: «KorrrericH», «KaPusryanskiy»): the
    # case is noise, so both forms in title case (the editor, 2026-10-29 02:4x)
    if re.search(r"[^\W\d_][A-ZÀ-Þ]", ocr) and not ocr.isupper():
        ocr = ocr[:1].upper() + ocr[1:].lower()
    tgt = tw.upper() if ocr.isupper() else tw[:1].upper() + tw[1:].lower()
    d, ed = wdist(ocr, tgt)
    letters = [e for e in ed if " " not in (e[1] + e[2])]
    f = []
    # THE TRANSLITERATION TEST, first, for A1, A3, A4 and F3 alike.
    # AE ~ Ä, OE ~ Ö, UE ~ Ü (the editor, 23:3x): both forms with the umlauts written out before the skeleton
    # and generalised (the editor, 23:3x): the letters written
    # out before compact(), which drops Ø and Æ (HØFFDING became «hffding»): Ø Œ → OE, Æ → AE, Å → AA, ß → SS,
    # Þ → TH, Ð → D, Ł → L, Dutch IJ → Y
    OUT = {"ä": "ae", "ö": "oe", "ü": "ue", "ø": "oe", "œ": "oe", "æ": "ae", "å": "aa", "ß": "ss", "þ": "th", "ð": "d", "ł": "l"}
    uml = lambda s: re.sub(r"ij", "y", "".join(OUT.get(ch, ch) for ch in s.lower()))
    # and the umlaut dropped, AE ~ A, OE ~ O, UE ~ U (the editor, 23:3x): written out,
    # then levelled, so Schröder = Schroeder = Schroder
    sg = slavgreek(h) or slavgreek(tg)
    lev = lambda s: re.sub(r"aa", "a", re.sub(r"([aou])e", r"\1", kx(skel2(compact(uml(s))), sg)))
    # Œ ~ OE ~ E (PHEBUS ~ PHŒBUS) beside the dropped umlaut's OE ~ O: either levelling may match (the editor, 03:0x)
    lev2 = lambda s: re.sub(r"aa", "a", re.sub(r"oe", "e", kx(skel2(compact(uml(s))), sg)))
    translit = compact(nw) != compact(tw) and (lev(nw) == lev(tw) or lev2(nw) == lev2(tw))
    # a letter that NFKD does not decompose, written out (SCHŒLL → SCHOELL, the same key; the editor, 2026-10-29 12:0x:
    # Œ, Ö and OE one transliteration)
    letterform = compact(nw) == compact(tw) and nw.upper() != tw.upper() and any(ch in "œøæßłþðå" for ch in (nw + tw).lower())
    translit = translit or letterform
    # the whole name's length for A1 and A4, not the changed word's (JIMÉNEZ LOMA → JIMÉNEZ LOIRA, PINOT LA BEAUME → PICOT
    # LA BEAUME; the editor, 2026-10-29 12:0x)
    whole = max(len(compact(re.sub(r"\s*\(.*", "", h))) - (1 if run_in else 0), len(compact(nw)), 1)
    # A1, generalised (the editor, 23:4x): n letters changed in a name of 5n letters or fewer, so two changes are no
    # fault in a name of more than ten letters; not for a fold that is wholly a transliteration, whose changes are
    # explained, as for A4 (the editor, 2026-10-29 02:3x, BOHENSKIJ → BOĤENSKI)
    if letters and not translit and whole <= 5 * len(letters): f.append("a one-letter change in a name of five letters or fewer")
    # A2: an initial letter gained or lost, both forms in title case (Arĵenkov ~ Karĵenkov, Aktargiev ~ Kantarĝiev): the
    # first letter would have to be both wrong and wrongly capitalised (the editor, 2026-10-28 19:1x and 22:1x)
    # not for a transliteration (EZERSKIJ → JEZERSKIJ, KHARALAMBEV → HARALAMBEV; the editor, 12:0x: a
    # transliteration overrides the penalty for the first letter's case)
    if not translit and any(e[0] in ("ins", "del") and e[3] == 0 for e in letters) and ocr[:1].isupper() and not ocr.isupper():
        f.append("the first letter added or dropped, title case to title case")
    # A3, widened (the editor, 23:2x, on GUILHAUME): the
    # Wikidata lists miss regional forms, so the form standing in more than two corpus items counts too, as in the screen;
    # not for a form with an impossible cluster (QURRRA stands in three corpus items, still no surname), nor for a
    # transliteration across scripts, a real spelling by its nature (SAHAROF → SAĤAROV, 23:2x); a native variant in the
    # same script, a double consonant or an umlaut, is a surname of its own and keeps A3 (the editor, 2026-10-29 02:2x,
    # (b): DOUGLASS a native variant)
    # Vi ~ Vj ~ Vy is a Slavonic transliteration in general, so across scripts (the editor, 2026-10-29 03:0x:
    # MIKOLAISKI ~ MIKOLAJSKI, which a real surname had blocked)
    # and lj ~ l, an initial je- ~ e- (the editor, 2026-10-29 03:2x)
    # and Kh ~ H ~ Ĥ ~ Ch, ph ~ f (the editor, 12:0x; ORPHANIDES → ORFANIDES, for Greek names at least), sparing A3 only
    # in a Slavic or Greek name (12:2x: KHANNA, an Indian surname, keeps it)
    pre = lambda s: re.sub(r"^je", "e", (kx(skeleton(compact(s)), True) if sg else skeleton(compact(s))).replace("ou", "u").replace("lj", "l"))
    cross = lambda s: re.sub(r"(iy|ij|ii|y)$", "i", re.sub(r"(?<=[aeiou])[jy]", "i", re.sub(r"(?<=[bcdfghjklmnpqrstvwxz])j(?=[aeiou])", "i", pre(s))))
    xscript = compact(nw) != compact(tw) and cross(nw) == cross(tw)
    # the corpus leg not where the target is in 20 times the items or more: a famous name's recurring garble (HOIRAC, 5
    # items, BOIRAC in thousands; the editor, 2026-10-29 02:3x: the
    # corpus test kept for now at 20 times, its validity doubted)
    ni, ti = LEXN.get(fold(nw).lower(), 0), LEXN.get(fold(tw).lower(), 0)
    corpus = ni >= 5 and ti < 20 * ni   # five items, not three (the editor, 2026-10-29 12:2x)
    # nor for a fold of accents only, the same name (SERANT → SÉRANT: the lexicon folds accents, so the corpus test counted
    # the target's own spelling; the editor, 2026-10-29 02:3x)
    # and a fold of spaces or hyphens only, the same name too (FLEURDELYS → FLEUR DE LYS; the editor, 2026-10-29 03:1x)
    accents_only = re.sub(r"[\s\-]", "", fold(nw).lower()) == re.sub(r"[\s\-]", "", fold(tw).lower())
    # Œ ~ E is a transliteration, so no surname of its own (PHEBUS → PHŒBUS; the editor, 03:0x)
    xscript = xscript or ("œ" in (nw + tw).lower() and lev2(nw) == lev2(tw)) or letterform
    if len(compact(nw)) >= 4 and not implausible(h) and not xscript and not accents_only:
        if attest is not None and compact(nw) in attest: f.append("the name as read is a surname in Wikidata")
        elif corpus: f.append("the name as read stands in five corpus items or more, not in Wikidata")
    # A5 (the editor, 23:2x: a letter the OCR added at the start or end penalised, one it dropped not, as
    # GRIBELI → GRIBELIN is believable): a letter of the name as read that the target lacks, at its start or end
    # not for a transliteration (BOHENSKIJ's -IJ; the editor, 2026-10-29 02:4x)
    if not translit and any(e[0] == "del" and e[3] in (0, len(ocr) - 1) for e in letters): f.append("the OCR added a letter at the start or end")
    # F1 and F2 are one point (the editor, 23:3x: exclusive, the second only where the first fails)
    if tgt_on_roster and not name_on_roster: f.append("the target is on the roster, the name is not")
    elif tlines >= 5 * max(n, 1): f.append("the target heads five times the lines or more")
    if translit: f.append("a known transliteration")
    def conf(e):
        x, y = fold(e[1]).lower(), fold(e[2]).lower()
        if e[0] in ("ins", "del"): return (x or y) in THIN   # a stray or lost thin stroke (F8 in F4, the editor 23:4x)
        return e[0] == "sub" and (x == y or frozenset((x, y)) in OCR_PAIRS)   # a case, a diacritic, or a known swap
    # a letter split or merged (m ~ rn, n ~ ri, u ~ ii, w ~ vv, d ~ cl): one OCR confusion though two edits
    split = any(re.sub(p, q, ocr.lower()) == tgt.lower() or re.sub(p, q, tgt.lower()) == ocr.lower() for p, q in SPLITS)
    # F3 and F4 exclusive (the editor, 2026-10-29 01:5x, on ROVENSKI → ROVENSKIJ:
    # a letter scored as an OCR error is not also a transliteration)
    # or every span a confusion the survey saw five times or more (ü as «ii», 2026-10-30 16:2x)
    if translit: pass
    elif split or known_changes(changes(ocr, tgt)) or (letters and all(conf(e) for e in letters)
                 and not all(fold(e[1]).lower() == fold(e[2]).lower() and e[1].lower() == e[2].lower() for e in letters)):
        f.append("every letter changed is a known OCR confusion")
        ch = changes(ocr, tgt, letters)
        for k, _s in ch: SEEN_CHANGES[k].add((h, tg))
        if ch: f.append(f4_tier(ch))
    if (ed and not letters) or run_in: f.append("only a space differs")
    # A6, the gender pair (above)
    a1, a2 = compact(re.sub(r"\s*\(.*", "", h)), compact(re.sub(r"\s*\(.*", "", tg))
    if gender(a1, a2) or gender(a2, a1): f.append("a feminine form beside the masculine")
    # F6 (the editor, 23:2x: impossible phonotactics only where the form read is impossible and the
    # target is not, Serbian and Russian never penalised): only where the target is possible, and never a cluster a Slavic name has by nature
    # (Mrkonjić, Zdravković, Ŝĉerbakov: a South or East Slavic ending, or a letter of Esperanto's or the Slavs' own); a
    # letter three times (QURRRA) counts whatever the language
    why = implausible(h)
    slavic = bool(re.search(r"([iy][cćĉč]|ov|ev|in|ski|skij|sky|enko|vi[cćĉč]|ova|eva|ina|aja)$", fold(re.sub(r"\s*\(.*", "", h)).lower())
                  or re.search(r"[ĉĝĵŝŭžšćč]", h.lower()))
    hc = hard_cluster(nw)   # by sonority too (03:0x): only where the target has no such cluster
    if (why and "X" not in why and not implausible(tg) and (why == "a letter three times" or not slavic)) or \
            (hc and not hard_cluster(tw) and not slavic):
        f.append("the name has impossible clusters")
    if "x" in fold(nw) and "x" not in fold(tw): f.append("the name has an X in it")
    if not translit and d / whole > MAX_RATIO: f.append("the distance over the length is past MAX_RATIO")
    return sum(W.get(x, 0) for x in f), f, d, ocr, tgt, bool(seen)

REL_KINDS = {"renkonto", "konflikto", "interkonsento", "influo", "rilato"}   # as dowse-facts-assemble.py's
LIST_PERSON = re.compile(r"[A-ZÀ-ÞĈĜĤĴŜŬ][A-ZÀ-ÞĈĜĤĴŜŬ' \-.]+?(?: \([^)]{1,40}\))?")   # the harvest's OBJ_PERSON, a full stop allowed

def list_names(fp):
    """The persons a facts file's kind fields name in lists, as the harvest copies them: every «kun:» list, and the
    opening list of a relation (renkonto, konflikto …, up to its first comma), split on « kaj », the names in capitals
    only. -> Counter of name → lists it stands in (2026-10-28; the editor's list names, SCNNAREZ, TRIRV, HONINGKS)."""
    c = collections.Counter()
    for l in open(fp, encoding="utf-8"):
        f = FL.fields(l) if l.startswith("- $$$") else None
        if not f or not f.get("kind"): continue
        for seg in re.split(r";\s*(?![^()]*\))", f["kind"].strip("{} ")):
            k, _, obj = seg.strip().lstrip("+").strip().partition(":")
            k = k.strip()
            if k == "kun": lst = obj
            elif k in REL_KINDS: lst = re.split(r",\s*(?![^()]*\))", obj, maxsplit=1)[0]
            else: continue
            for p in re.split(r"\s+kaj\s+", lst.strip()):
                p = p.strip()
                if len(p) >= 2 and LIST_PERSON.fullmatch(p): c[p] += 1
    return c

LEXICON = sorted(glob.glob(os.path.join(G, "sources", "ocr-work", "ocr-lexicon-*.tsv")))
LEXN = {}
def lexicon_items(words):
    """{word: the corpus items it stands in}, from the OCR lexicon (tools/ocr-corpus-lexicon.py; untracked), for the words
    asked only (the file is large)."""
    want, out = {w.lower() for w in words}, {}
    if not LEXICON: return out
    for l in open(LEXICON[-1], encoding="utf-8"):
        f = l.split("\t", 3)
        if len(f) > 2 and f[0] in want:
            try: out[f[0]] = int(f[2])
            except ValueError: pass
    return out

def screen(rows, attest):
    """The unknown list names screened (2026-10-28; the editor, to a screen so the review shows the suspects): each
    name's words of three letters or more, a Wikidata surname or in more than two corpus items → «read right, likely»;
    otherwise a SUSPECT. -> rows with the reason as their last field, the suspects first."""
    words = lambda h: [w for w in re.findall(r"[^\W\d_]{3,}", re.sub(r"\s*\(.*?\)", "", h)) if not w.isupper() or len(w) >= 3]
    lex = lexicon_items({w for _s, h, _n, _t in rows for w in words(h)})
    out = []
    for src, h, n, _t in rows:
        ws = words(h)
        att = [w for w in ws if attest is not None and compact(w) in attest]
        common = [f"{w} {lex[w.lower()]} items" for w in ws if lex.get(w.lower(), 0) > 2]
        why = (f"a surname in Wikidata ({', '.join(att)})" if att else "") + ("; " if att and common else "") + (f"in the corpus: {', '.join(common)}" if common else "")
        if not why and not ws:   # initials only («C. C.», «N. K.»): nothing to screen them by
            out.append((src, h, n, "initials: not screened")); continue
        if not why and re.search(r"[ĉĝĥĵŝŭĈĜĤĴŜŬ]", h):   # a Slavic name in Esperanto's spelling (OLŜANSKIJ): the legilo's,
            # not the OCR's, so neither the corpus nor Wikidata has it as written (2026-10-28, the screen's first sample)
            out.append((src, h, n, "Esperantised spelling, the legilo's: not screened")); continue
        out.append((src, h, n, ("read right, likely: " + why) if why else
                    "SUSPECT: no surname in Wikidata, in two corpus items or fewer" + (f" ({', '.join(f'{w} {lex.get(w.lower(), 0)}' for w in ws)})" if ws else "")))
    order = lambda t: 0 if t.startswith("SUSPECT") else 1 if t.startswith("Esperantised") else 2 if t.startswith("initials") else 3
    return sorted(out, key=lambda r: (order(r[3]), r[0], -r[2], r[1]))

def reweigh(old, tag, W=None):
    """reweigh OLD.tsv --tag T: the folds of an earlier scoring, the same folds, with the confusion's share (F9, A7) applied
    to each F4 fold's OCR and target forms as the table holds them (2026-10-30; the editor 15:5x: how many change
    class, and which are now over the +1 threshold: the folds he reviews, not a new measure, whose inputs have moved).
    Writes NAME-UNGARBLE-SCORES-<HEADS|LISTS>-T.tsv (create-only) and its -shares.md; then `compare OLD NEW`."""
    F4 = "every letter changed is a known OCR confusion"
    OLD = set(TIERS) | {"F4 under 10% of the letter: F4 counts +0.5"}   # the first tiers' label too
    kind = "LISTS" if "-LISTS-" in os.path.basename(old) else "HEADS"
    base = os.path.join(G, "dowse", f"NAME-UNGARBLE-SCORES-{kind}-{tag}")
    if os.path.exists(base + ".tsv"): sys.exit("refusing to overwrite: " + base + ".tsv")
    rows = list(csv.DictReader(open(old, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    W = W or WEIGHTS
    # A3 split by its leg (16:2x), from the forms the table holds: the Wikidata surnames, the corpus items (score_one's test)
    A3OLD = "the name as read is a real surname (Wikidata, or in five corpus items or more)"
    A3W, A3C = "the name as read is a surname in Wikidata", "the name as read stands in five corpus items or more, not in Wikidata"
    attest = surnames() if SURNAMES else None
    global LEXN
    form = lambda r, c: re.sub(r" \(not on the page\)$", "", r[c])
    LEXN = lexicon_items({fold(form(r, c)).lower() for r in rows for c in ("OCR form", "target form")})
    off, legs = 0, collections.Counter()
    for r in rows:
        f = [x for x in (r["features"].split("; ") if r["features"] else []) if x not in OLD]
        if abs(sum({**WEIGHTS, A3OLD: -2}.get(x, 0) for x in f) - float(r["score"])) > 1e-9: off += 1   # weighed otherwise
        ocr, tgt = re.sub(r" \(not on the page\)$", "", r["OCR form"]), r["target form"]
        if A3OLD in f:
            f.remove(A3OLD)
            ni, ti = LEXN.get(fold(ocr).lower(), 0), LEXN.get(fold(tgt).lower(), 0)
            leg = A3W if attest is not None and compact(ocr) in attest else A3C if ni >= 5 and ti < 20 * ni else None
            legs[leg or "neither leg found again: Wikidata's points kept"] += 1
            f.append(leg or A3W)
        if F4 not in f and "a known transliteration" not in f and known_changes(changes(ocr, tgt)):
            f.append(F4)   # a many-letter confusion the old test missed (ü as «ii»)
        if F4 in f:
            ch = changes(ocr, tgt)
            for k, _s in ch: SEEN_CHANGES[k].add((r["as read"], r["target"]))
            if ch: f.append(f4_tier(ch))
        r["features"], r["score"] = "; ".join(f), f"{sum(W.get(x, 0) for x in f):g}"
    with open(base + ".tsv", "x", encoding="utf-8") as fh:
        fh.write("\t".join(rows[0].keys()) + "\n" if rows else "")
        for r in sorted(rows, key=lambda r: -float(r["score"])): fh.write("\t".join(r.values()) + "\n")
    band = lambda s_: "30% or more" if s_ >= HIGH else "10% or under" if s_ <= LOW else "10–30%"
    bands = collections.Counter(band(read_of(k)) for k in SEEN_CHANGES)
    with open(base + "-shares.md", "x", encoding="utf-8") as fh:
        fh.write(f"# The OCR confusions' shares in the folds of {os.path.basename(old)}\n\n`[GENERATED by tools/name-ungarble.py reweigh. "
                 f"Do not hand-edit — re-run it.]`\n\nThe survey: {os.path.basename(SURVEY[-1]) if SURVEY else 'none'}, old print, the truth "
                 f"letter's case; a fold by its least confusable change. " + "; ".join(f"{t} ({WEIGHTS[t]:+g} on F4's +1)" for t in TIERS) +
                 f". **{len(SEEN_CHANGES)} change classes**: " + ", ".join(f"{b} {bands[b]}" for b in ("30% or more", "10–30%", "10% or under")) +
                 "\n\n| case | truth | written | of the wrong readings | of the letter | folds |\n|---|---|---|---:|---:|---:|\n" +
                 "".join(f"| {k[0]} | {k[1] or '—'} | {k[2] or '(lost)'} | {read_of(k):.1%} | {share_of(k):.2%} | {len(SEEN_CHANGES[k])} |\n"
                         for k in sorted(SEEN_CHANGES, key=lambda k: (-read_of(k), -len(SEEN_CHANGES[k]), k))))
    print(f"{len(rows)} folds reweighed → {os.path.relpath(base, ROOT)}.tsv; {len(SEEN_CHANGES)} change classes: "
          + ", ".join(f"{b} {bands[b]}" for b in ("30% or more", "10–30%", "10% or under")) + (f"; {off} rows weighed otherwise before" if off else "")
          + ("; A3 by leg: " + ", ".join(f"{('A3 Wikidata' if k == A3W else 'A8 corpus' if k == A3C else k)} {v}" for k, v in legs.items()) if legs else ""))

def compare(old, new, out=None):
    """compare OLD.tsv NEW.tsv --out MD: two scorings of the same folds (2026-10-29 12:0x; the editor): how many folds go from each old
    score to each new one, and every fold at +1 or more now that was below +1 (or absent) before, with its features."""
    rd = lambda p: {(r["source"], r["as read"], r["target"]): r for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t")}
    A, B = rd(old), rd(new)
    moves = collections.Counter((A[k]["score"] if k in A else "absent", B[k]["score"]) for k in B)
    gone = [k for k in A if k not in B]
    up = sorted((k for k in B if float(B[k]["score"]) >= 1 and (k not in A or float(A[k]["score"]) < 1)), key=lambda k: -float(B[k]["score"]))
    down = sorted((k for k in B if k in A and float(A[k]["score"]) >= 1 and float(B[k]["score"]) < 1), key=lambda k: float(B[k]["score"]))
    num = lambda s: float(s) if s != "absent" else 99
    doc = [f"# The folds rescored: {os.path.basename(old)} → {os.path.basename(new)}", "",
           "`[GENERATED by tools/name-ungarble.py compare. Do not hand-edit — re-run it.]`", "",
           f"{len(B)} folds now, {len(A)} before; {sum(1 for k in B if k in A and A[k]['score'] != B[k]['score'])} changed score, "
           f"{sum(1 for k in B if k not in A)} new, {len(gone)} gone; **{len(up)} now at +1 or more that were not**, {len(down)} fallen below +1.", "",
           "## The moves (old score → new score: folds)", "", "| old | new | folds |", "|---|---|---|"]
    doc += [f"| {o} | {n} | {c} |" for (o, n), c in sorted(moves.items(), key=lambda x: (num(x[0][0]), -float(x[0][1]))) if o != n]
    sec = lambda title, ks: ["", f"## {title} ({len(ks)})", "", "| old | new | as read | → target | source | features |", "|---|---|---|---|---|---|"] + \
        [f"| {A[k]['score'] if k in A else '—'} | {B[k]['score']} | {k[1]} | {k[2]} | {k[0]} | {B[k]['features']} |" for k in ks]
    doc += sec("Now at +1 or more, for review", up) + sec("Fallen below +1", down)
    if out:
        if os.path.exists(out): sys.exit(f"refusing to overwrite {out}")
        with open(out, "x", encoding="utf-8") as fh: fh.write("\n".join(doc) + "\n")
    print(f"{len(B)} folds; {len(up)} newly at +1 or more, {len(down)} fallen below" + (f" → {os.path.relpath(out, ROOT)}" if out else ""))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["measure", "apply", "score", "compare", "reweigh", "apply-scored"]); ap.add_argument("facts", nargs="+")
    ap.add_argument("--min", type=float, default=1, help="apply-scored: the bar (the editor's +1)")
    ap.add_argument("--out", help="compare: the document to write (create-only)")
    ap.add_argument("--weights", help="score: a TSV «feature<TAB>points» overriding WEIGHTS (the editor's points, to try out)")
    ap.add_argument("--roster", help="a dowse/ROSTER-FULL-CROSS-ARC-*.txt other than the latest")
    ap.add_argument("--ido"); ap.add_argument("--tag", default=datetime.date.today().isoformat()); ap.add_argument("--write", action="store_true")
    ap.add_argument("--review", action="store_true", help="apply: the review document only, no config touched")
    ap.add_argument("--unwrite", action="store_true", help="apply: take every «legita» row out of the configs")
    ap.add_argument("--lists", action="store_true", help="measure: the names inside «kun:» lists and the relations' person "
                    "lists (the harvest's copies), not the lines' heads; the folds' targets are still the heads (2026-10-28)")
    ap.add_argument("--suspects", action="store_true", help="measure: write the garbled and SUSPECT names (no fold target) to "
                    "dowse/NAME-SUSPECTS-HEADS.tsv or …-LISTS.tsv, for the harvest's mark (2026-10-28)")
    ap.add_argument("--context", action="store_true", help="apply --review: each candidate followed by the OCR text at up to "
                    "three of its lines (the editor, 2026-10-28 18:0x)")
    ap.add_argument("--strict", action="store_true", help="heads: a roster name counts only if it heads lines in two sources "
                    "or more, or three lines or more (every head has a profile of its own; implied by --suspects)")
    a = ap.parse_args()
    if a.mode == "compare": return compare(*a.facts, out=a.out)
    if a.mode == "apply-scored":
        if a.review == a.write: sys.exit("apply-scored: --review or --write")
        return apply_scored(a.facts, a)
    if a.mode == "reweigh":
        W = dict(WEIGHTS)
        for l in (open(a.weights, encoding="utf-8") if a.weights else []):
            if l.strip() and not l.startswith("#") and "\t" in l:
                k_, v_ = l.rstrip("\n").rsplit("\t", 1); W[k_.strip()] = float(v_)
        return reweigh(a.facts[0], a.tag, W)
    if a.mode == "measure": a.review = False
    if a.review and a.write: sys.exit("--review or --write, not both")
    # a list name's fold is the same «legita» rename row, which the assembler applies to the names in a line's kinds and
    # fact as well as to its head, with ⟦nomo legita: OLD → NEW⟧ (the editor's design of 2026-10-27 19:4x), so --lists
    # may review and write as the heads do (2026-10-28)
    a.strict = a.strict or a.suspects
    out = os.path.join(G, "dowse", f"NAME-UNGARBLE-{'MEASURE' if a.mode == 'measure' else 'APPLY' if a.write else 'REVIEW'}{'-LISTS' if a.lists else ''}-{a.tag}.md")
    if a.write and os.path.exists(out): sys.exit("refusing to overwrite: " + out)
    # --roster: an earlier roster, to rescore the same folds as an earlier scoring (2026-10-30: the roster of 2026-10-29
    # 12:32 holds most heads the scorings of 12:2x folded)
    rp = a.roster or sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")))[-1]
    roster = {}
    for l in open(rp, encoding="utf-8"):
        if not l.strip() or l.startswith("#"): continue
        parts = [p.strip() for p in l.split(" | ")]
        if implausible(parts[0].replace("-", " ")): continue
        for p in parts: roster.setdefault(compact(p), parts[0])
        segs = parts[0].split("-")   # a label with its forename, «lorenz-richard»: its surname alone a key too
        for i in range(1, len(segs)):
            pre = compact("".join(segs[:i]))
            if len(pre) >= 4 and segs[i - 1] not in PARTICLES: roster.setdefault(pre, parts[0])
    register = {}   # the names register's confirmed and proposed spellings: each form → the main form
    for row in csv.DictReader((l for l in open(os.path.join(G, "profiles", "NAMES-REGISTER.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if (row.get("relation") or "").strip() != "spelling": continue
        main = (row.get("main_form") or row.get("same_as") or "").strip()
        for f in re.split(r";\s*", row.get("name") or "") + [row.get("same_as") or "", main]:
            for k in head_keys(f.strip()) if f.strip() else []: register.setdefault(k, main)
    for a_, b_ in harvest_aliases().items():
        for k in head_keys(a_): register.setdefault(k, b_)
    rskel = {}
    for k, lab in roster.items(): rskel.setdefault(skeleton(k), lab)
    for k, m in register.items(): rskel.setdefault(skeleton(k), m)
    ip = a.ido or sorted(p for p in glob.glob(os.path.join(G, "dowse", "IDO-NAMES-*.tsv")))[-1]
    ido = {}
    for row in csv.DictReader(open(ip, encoding="utf-8"), delimiter="\t"):
        if row["on the dowse roster"]: continue
        for f in row["surname forms"].split(" | "): ido.setdefault(compact(f), row["full names"].replace(" | ", " / "))
    attest = surnames() if SURNAMES else None
    if attest is None: print("no Wikidata surnames in sources/web-2026-10-27-surnames/: the riskier folds are not checked")
    classes = ["on the roster", "known variant", "transliteration", "Ido roster", "ungarblable", "near a head", "attested, not folded",
               "gender variant, not folded", "sh ~ sch, not folded", "garbled", "unknown"]
    per, rows = {}, collections.defaultdict(list)
    allheads = {fp: collections.Counter(m.group(1).strip() for l in open(fp, encoding="utf-8") for m in [re.match(r"- \$\$\$ (.+?) \$\$\$", l)] if m)
                for fp in a.facts}
    total = collections.Counter()
    for heads in allheads.values(): total.update(heads)
    targets = allheads   # the heads a name may fold to: always the lines' own heads
    if a.strict and not a.lists:
        # a head always has a profile of its own, so the roster would vouch for every garble (SCNNAREZ, 1 line): a roster
        # name counts for a head only if it heads lines in two sources or more, or three lines or more, or is an extra
        nsrc, nlin = collections.Counter(), collections.Counter()
        for heads in allheads.values():
            for h, n in heads.items():
                for k in head_keys(h): nsrc[k] += 1; nlin[k] += n
        xp = os.path.join(ROOT, "tools", "cross-arc-roster-extra.txt")
        extra = {compact(l.split(" | ")[0].strip()) for l in open(xp, encoding="utf-8") if l.strip() and not l.startswith("#")} if os.path.exists(xp) else set()
        roster = {k: v for k, v in roster.items() if nsrc[k] >= 2 or nlin[k] >= 3 or compact(v) in extra or k not in nsrc}
        rskel = {}   # rebuilt from the filtered roster, or each head would match its own profile's skeleton
        for k, lab in roster.items(): rskel.setdefault(skeleton(k), lab)
        for k, m in register.items(): rskel.setdefault(skeleton(k), m)
    if a.lists:
        allheads = {fp: list_names(fp) for fp in a.facts}   # what is measured: the names inside the lists
        # the roster is built from the profiles, and the harvest makes a profile of every name a list copies to (MORAVIV,
        # SCNNAREZ: 2026-10-28), so a garble would vouch for itself: a roster name counts only if it heads lines somewhere
        hk_all = {k for h in total for k in head_keys(h)}
        extra = {compact(l.split(" | ")[0].strip()) for l in open(os.path.join(ROOT, "tools", "cross-arc-roster-extra.txt"), encoding="utf-8")
                 if l.strip() and not l.startswith("#")} if os.path.exists(os.path.join(ROOT, "tools", "cross-arc-roster-extra.txt")) else set()
        roster = {k: v for k, v in roster.items() if k in hk_all or compact(v) in hk_all or compact(v) in extra}
        rskel = {}
        for k, lab in roster.items(): rskel.setdefault(skeleton(k), lab)
        for k, m in register.items(): rskel.setdefault(skeleton(k), m)
    allk = {}   # each key → the head of all files with the most lines under it (for a recurring misreading)
    for h, n in total.most_common():
        if not implausible(h):
            for k in head_keys(h): allk.setdefault(k, (h, n))
    hskel = {}   # each skeleton → the head of all files with the most lines under it
    for h, n in total.most_common():
        if not implausible(h): hskel.setdefault(skeleton(head_keys(h)[0]) if head_keys(h) else "", (h, n))
    for fp in a.facts:
        src = re.sub(r"-dowse\.md$", "", os.path.basename(fp))
        heads = allheads[fp]
        hk = {}
        for h, n in targets[fp].items():
            for k in head_keys(h): hk.setdefault(k, (h, n))
        cnt = collections.Counter(); lines = collections.Counter()
        for h, n in heads.items():
            keys = head_keys(h)
            initials = all(len(w.strip(".")) <= 2 for w in re.split(r"[\s\-—]+", re.sub(r"\s*\(.*?\)", "", h)) if w)
            # a transliteration only of a name of four letters or more, never of initials or a garbled form
            sk = [] if initials or implausible(h) else [skeleton(k) for k in keys if len(k) >= 4]
            hs = next((hskel[s] for s in sk if s in hskel and hskel[s][0] != h and hskel[s][1] > total[h]), None)
            # A RECURRING MISREADING has profiles of its own, so it stood «on the roster» and was never measured
            # (EVSTIFĈIEFF, 27 lines in three sources, É read Ĉ, beside EVSTIFEIEFF's 117; the editor, 2026-10-29 03:1x):
            # the OCR's confusions undone first, against every file's heads, a head of three times the lines winning
            big = None
            if not initials and not implausible(h):
                for k in keys:
                    for v in (sorted(variants(k)) if len(k) >= 5 else []):
                        if v in allk and allk[v][0] != h and allk[v][1] >= 3 * max(total[h], 1) and (not big or allk[v][1] > big[1]):
                            big = allk[v]
            if big: c, t = "ungarblable", f"head: {big[0]} ({big[1]} in all files)"
            elif any(k in roster for k in keys) and not implausible(h): c, t = "on the roster", ""
            elif any(k in register for k in keys): c, t = "known variant", next(register[k] for k in keys if k in register)
            elif any(s in rskel for s in sk): c, t = "transliteration", "roster: " + next(rskel[s] for s in sk if s in rskel)
            elif hs: c, t = "transliteration", f"head: {hs[0]} ({hs[1]} in all files)"
            elif any(k in ido for k in keys): c, t = "Ido roster", next(ido[k] for k in keys if k in ido)
            else:
                t = ""; risky = False
                for k in ([] if initials else keys):
                    for v in sorted(variants(k)):
                        sure = v in variants_sure(k)
                        if sure and v in roster: t = f"roster: {roster[v]}"
                        elif sure and v in ido: t = f"Ido roster: {ido[v]}"
                        elif v in hk and hk[v][1] > n: t = f"head: {hk[v][0]} ({hk[v][1]})"; risky = not sure
                        if t: break
                    if t: break
                near = ""
                if not t:
                    k0 = keys[0]; best = None   # among the clean heads only, the one with the most lines (BORRACX: BORRACK,
                    # not the garbled BORCACX the first match gave; the editor, 20:3x)
                    for k2, (h2, n2) in hk.items():
                        # more lines wins; at equal lines, a head of the same length (a letter misread, BORRACX → BORRACK)
                        # over a shorter or longer one (a letter lost, BORRAC)
                        if h2 == h or (best and (n2, len(k2) == len(k0)) <= (best[1], len(compact(best[0])) == len(k0))): continue
                        if re.sub(r"[.,;:]+$", "", h2) == re.sub(r"[.,;:]+$", "", h): continue   # final punctuation only: the
                        # assembler drops it from every head (the editor, 20:2x), no fold needed
                        initials_pair = all(len(w.strip(".")) <= 2 for w in re.split(r"[\s\-—]+", h2) if w)
                        if implausible(h2) and not initials_pair: continue
                        if k2 == k0 and n2 > n: best = (h2, n2, "accents"); continue
                        if initials or initials_pair: continue   # initials fold only to the same letters (above)
                        # the letters differing, over the length, at most MAX_RATIO: one from 5 letters, two from 10; three
                        # times the lines for one letter, five for two. A plausible form is then checked against the
                        # world's surnames below (FRIEDEMANN beside WIEDEMANN: the editor, 19:3x: too risky)
                        if n2 >= 3 * n and len(k0) >= 5:
                            d = distance(k0, k2, 2)
                            if d <= 2 and d / len(k0) <= MAX_RATIO and (d == 1 or n2 >= 5 * n):
                                best = (h2, n2, "one letter" if d == 1 else "two letters")
                    if best: near = f"head: {best[0]} ({best[1]}), {best[2]}"
                why = implausible(h)
                c = "ungarblable" if t else "near a head" if near else "garbled" if why else "unknown"
                # the riskier folds (a near head but for accents; R or C read as another letter) are left alone when
                # the form is attested as a word of its own in the wikipedias (the editor, 2026-10-27 19:3x: a riskier
                # fold not made where the form is a real surname out there)
                if (risky or (near and "accents" not in near)) and not why and attest is not None:
                    if any(k in attest for k in keys if len(k) >= 4):
                        c, t, near = "attested, not folded", f"{t or near}; a surname in Wikidata", ""
                if c == "near a head": t = near + (f"; {why}" if why else "")
                if c == "garbled": t = why
            # A FORM AS READ THAT IS A REAL SURNAME IS LEFT ALONE, whatever the class (the editor, 2026-10-28 18:1x:
            # the reason all possible surnames were downloaded; the check had covered the riskier near-head folds only, and LOWE → LOVE went through as a
            # transliteration): only a fold that restores accents, the same name, is exempt
            if c in FOLD and attest is not None and "accents" not in t and not implausible(h) \
                    and any(k in attest for k in keys if len(k) >= 4):
                c, t = "attested, not folded", f"{t}; a surname in Wikidata"
            # A GENDER VARIANT IS NO GARBLE (the editor, 2026-10-28 18:5x: -ova to -ov and
            # -eva to -ev rejected; KOŜLAKOVA → KOŜLAKOV, «S-ino I. Koŝlakova»): a fold whose two forms differ only by the feminine
            # -OVA/-EVA against -OV/-EV, either way, is left alone
            if c in FOLD:
                tg = target_head(t)
                a1 = compact(re.sub(r"\s*\(.*", "", h)); a2 = compact(re.sub(r"\s*\(.*", "", tg or ""))
                # widened 23:3x (the editor, on KORZLINSKAJA → KORZLINSKIJ): Russian -aja
                # beside -ij/-ii/-y, -ina beside -in, Polish -ska/-cka beside -ski/-cki
                # and the editor 23:2x: IJ ~ Y ~ I ≠ AJA ~ AYA added to the banned masculine-to-feminine pairs, beside OV ~ OVA
                if tg and (gender(a1, a2) or gender(a2, a1)):
                    c, t = "gender variant, not folded", f"{t}; a feminine form beside the masculine"
            # SH- AND SCH- ARE SEPARATE SURNAMES (the editor, 2026-10-29 12:2x, on SHUBERT → SCHUBERT, SHULTZ, SHWARTZ,
            # GOTTSHALL: never a fold): a pair differing only so is left out, the attested ones too
            if c in FOLD + ("attested, not folded",):
                tg = target_head(t)
                b1 = compact(re.sub(r"\s*\(.*", "", h)); b2 = compact(re.sub(r"\s*\(.*", "", tg or ""))
                if tg and b1 != b2 and b1.replace("sch", "sh") == b2.replace("sch", "sh"):
                    c, t = "sh ~ sch, not folded", f"{t}; Sh- and Sch- are separate surnames"
            cnt[c] += 1; lines[c] += n
            if c != "on the roster": rows[c].append((src, h, n, t))
        per[src] = (cnt, lines)
    if a.mode == "score":
        W = dict(WEIGHTS)
        if a.weights:
            for l in open(a.weights, encoding="utf-8"):
                if l.strip() and not l.startswith("#") and "\t" in l:
                    k_, v_ = l.rstrip("\n").rsplit("\t", 1); W[k_.strip()] = float(v_)
        cands = [(c, r) for c in FOLD + ("attested, not folded",) for r in rows[c]]   # the gender variants stay out (ruled)
        # F1's roster by transliteration too (the editor, 23:3x: DOMBROVSKI, a roster
        # figure's Russian variant, scores as on the roster): the roster's forms and the register's variants, by skel2
        rsk2 = {skel2(k) for k in roster} | {skel2(k) for k in register}
        on_roster = lambda name: any(k in roster or k in register or skel2(k) in rsk2 for k in head_keys(name))
        global LEXN   # the corpus items each name's word stands in, for A3 (23:2x)
        words = lambda s: set(re.findall(r"[^\W\d_]{2,}", re.sub(r"\s*\(.*", "", s or "")))   # every word: the scored one
        # may be any of a name's words (KANALOŜI-LEFLER)
        LEXN = lexicon_items(set().union(*([words(r[1]) | words(target_head(r[3])) for _c, r in cands] or [set()])))
        scored = []
        for c, (src, h, n, t) in cands:
            tg = target_head(t)
            if not tg: continue
            name = re.sub(r"\s*\(.*", "", h).strip()
            ctx = ocr_context(src, name, a.lists)
            s, f, d, ocr, tgt, seen = score_one(h, n, tg, total.get(tg, 0) or sum(v for k, v in total.items() if re.sub(r"\s*\(.*", "", k) == tg),
                                                any(k in roster for k in head_keys(h)), on_roster(tg), attest, ctx, W)
            scored.append((s, d, src, h, n, tg, c, t, f, ocr, tgt, seen, ctx))
        scored.sort(key=lambda x: (-x[0], x[1], x[2], x[3]))
        kind = "LISTS" if a.lists else "HEADS"
        base = os.path.join(G, "dowse", f"NAME-UNGARBLE-SCORES-{kind}-{a.tag}")
        if os.path.exists(base + ".md"): sys.exit("refusing to overwrite: " + base + ".md")
        with open(base + ".tsv", "x", encoding="utf-8") as fh:
            fh.write("score\tdistance\tsource\tas read\tplaces\ttarget\tclass\tOCR form\ttarget form\tfeatures\n")
            for s, d, src, h, n, tg, c, t, f, ocr, tgt, seen, ctx in scored:
                fh.write(f"{s:g}\t{d:g}\t{src}\t{h}\t{n}\t{tg}\t{c}\t{ocr}{'' if seen else ' (not on the page)'}\t{tgt}\t{'; '.join(f)}\n")
        with open(base + ".md", "x", encoding="utf-8") as fh:
            fh.write(f"# The name ungarbler: the folds scored ({'list names' if a.lists else 'heads'}, {a.tag})\n\n"
                     "`[GENERATED by tools/name-ungarble.py score. Do not hand-edit — re-run it.]`\n\n"
                     "**For trying out rankings: nothing written.** The editor's points (2026-10-28), each weighed as below; the distance "
                     "is taken between the name as the OCR prints it (a studly «DeGrof» read «De Grof») and the target in the same case, "
                     "a change of case counting one, a space a half. The table beside it: the `.tsv` of the same name.\n\n"
                     "| feature | points |\n|---|---|\n" + "".join(f"| {k} | {v:+g} |\n" for k, v in W.items()) + "\n")
            hist = collections.Counter(x[0] for x in scored)
            fh.write("**Scores:** " + ", ".join(f"{k:+g}: {hist[k]}" for k in sorted(hist, reverse=True)) + "\n\n")
            band = lambda s_: "30% or more" if s_ >= HIGH else "10% or under" if s_ <= LOW else "10–30%"
            bands = collections.Counter(band(read_of(k)) for k in SEEN_CHANGES)
            fh.write(f"**The OCR confusions' shares** (F9, A7; {os.path.basename(SURVEY[-1]) if SURVEY else 'no survey'}, old print): "
                     f"{len(SEEN_CHANGES)} change classes in the folds that score F4: " + ", ".join(f"{b} {bands[b]}" for b in ("30% or more", "10–30%", "10% or under")) + "\n\n"
                     "| case | truth | written | of the wrong readings | of the letter | folds |\n|---|---|---|---:|---:|---:|\n" +
                     "".join(f"| {k[0]} | {k[1] or '—'} | {k[2] or '(lost)'} | {read_of(k):.1%} | {share_of(k):.2%} | {len(SEEN_CHANGES[k])} |\n"
                             for k in sorted(SEEN_CHANGES, key=lambda k: (-read_of(k), -len(SEEN_CHANGES[k]), k))) + "\n")
            for i, (s, d, src, h, n, tg, c, t, f, ocr, tgt, seen, ctx) in enumerate(scored, 1):
                fh.write(f"**S{i}. {h} → {tg}** · score {s:+g} · distance {d:g} («{ocr}» → «{tgt}»{'' if seen else ', the name not on its page'}) · {src} · {n} {'place' if a.lists else 'line'}{'s' if n != 1 else ''} · {c}\n\n")
                fh.write("".join(f"  - {'−' if W.get(x, 0) < 0 else '+'} {x}\n" for x in f) or "  - (no feature)\n")
                fh.write("\n")
                for loc, tl in ctx:
                    fh.write(f"- `{loc}`\n\n  ```\n" + "".join(f"  {x}\n" for x in tl) + "  ```\n\n")
        # THE COMPACT TABLE (the editor, 2026-10-29 01:5x: the names only, no
        # copies of the source text, and why each scored, as table rows): one row a fold, each factor's points in a column of its own
        code = {"a one-letter change in a name of five letters or fewer": "A1", "the first letter added or dropped, title case to title case": "A2",
                "the name as read is a surname in Wikidata": "A3",
                "the name as read stands in five corpus items or more, not in Wikidata": "A8",
                "the distance over the length is past MAX_RATIO": "A4", "the OCR added a letter at the start or end": "A5",
                "the target is on the roster, the name is not": "F1", "the target heads five times the lines or more": "F2",
                "a known transliteration": "F3", "every letter changed is a known OCR confusion": "F4", "only a space differs": "F5",
                "the name has impossible clusters": "F6", "the name has an X in it": "F7", "a feminine form beside the masculine": "A6",
                TIERS[0]: "F9", TIERS[1]: "F10", TIERS[2]: "F11"}
        cols = sorted(set(code.values()), key=lambda c: (c[0] != "A", int(c[1:])))
        with open(base + "-table.md", "x", encoding="utf-8") as fh:
            fh.write(f"# The folds scored, as a table ({'list names' if a.lists else 'heads'}, {a.tag})\n\n`[GENERATED by tools/name-ungarble.py score. Do not hand-edit — re-run it.]`\n\n"
                     + " · ".join(f"{c} {k} ({W.get(k, 0):+g})" for k, c in sorted(code.items(), key=lambda kc: cols.index(kc[1]))) + "\n\n"
                     f"| # | score | as read | → target | dist. | " + " | ".join(cols) + " | source |\n|---|---|---|---|---|" + "---|" * len(cols) + "---|\n")
            for i, (s, d, src, h, n, tg, c, t, f, ocr, tgt, seen, ctx) in enumerate(scored, 1):
                pts = {code[x]: W.get(x, 0) for x in f if x in code}
                fh.write(f"| {i} | {s:+g} | {h} | {tg} | {d:g} | " + " | ".join(f"{pts[k]:+g}" if k in pts else "" for k in cols) + f" | {src} |\n")
        print(f"scored {len(scored)} folds → {os.path.relpath(base, ROOT)}.md, -table.md and .tsv; " + ", ".join(f"{k:+g}: {hist[k]}" for k in sorted(hist, reverse=True)))
        print(f"change classes in the F4 folds: {len(SEEN_CHANGES)}; " + ", ".join(f"{b} {bands[b]}" for b in ("30% or more", "10–30%", "10% or under")))
        return
    if a.mode == "apply" and a.unwrite: return unwrite(a.facts)
    if a.mode == "apply": return apply(rows, a, out)
    tc = sum((v[0] for v in per.values()), collections.Counter()); tl = sum((v[1] for v in per.values()), collections.Counter())
    fmt = lambda cnt, lines: "; ".join(f"{c} {cnt[c]} heads, {lines[c]} lines" for c in classes)
    for src, (cnt, lines) in sorted(per.items()): print(f"{src}: {fmt(cnt, lines)}")
    if len(per) > 1: print(f"ALL {len(per)} files: {fmt(tc, tl)}")
    if (a.lists or a.suspects) and rows["unknown"]:
        rows["unknown"] = screen(rows["unknown"], attest)
    if a.suspects:   # the garbles without a target, heads and list names alike, for the harvest's mark (the editor, 2026-10-28
        # 17:4x: a person not profiled is not visible; the two cases handled consistently): one file a kind,
        # written whole by each run of its kind
        sp = os.path.join(G, "dowse", f"NAME-SUSPECTS-{'LISTS' if a.lists else 'HEADS'}.tsv")
        sel = [(s, h, n, "garbled", t) for s, h, n, t in rows["garbled"]] + \
              [(s, h, n, "suspect", t) for s, h, n, t in rows["unknown"] if t.startswith("SUSPECT")]
        tmp = sp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(f"# GENERATED by tools/name-ungarble.py measure{' --lists' if a.lists else ''} --suspects, {a.tag}: the names with no fold "
                     f"target that the measure calls garbled or the screen SUSPECT; read by tools/harvest-facts.py for the profiles' mark. Do not hand-edit — re-run it.\n")
            fh.write("name\tsource\tplaces\tkind\tclass\treason\n")
            for s, h, n, c, t in sel: fh.write(f"{h}\t{s}\t{n}\t{'list' if a.lists else 'head'}\t{c}\t{t}\n")
        os.replace(tmp, sp)
        print(f"wrote {len(sel)} names to {os.path.relpath(sp, ROOT)}")
        sc = collections.Counter(r[3].split(":")[0].split(",")[0] for r in rows["unknown"])
        print("the unknowns screened: " + "; ".join(f"{k} {v}" for k, v in sc.most_common()))
    if not a.write: return
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The name ungarbler: the measure ({a.tag})\n\n`[GENERATED by tools/name-ungarble.py measure. Do not hand-edit — re-run it.]`\n\n")
        fh.write(f"A dry run: no line is changed. The roster: `{os.path.basename(rp)}`; the Ido roster: `{os.path.basename(ip)}`. The classes: the tool's docstring.\n\n")
        fh.write("| file | " + " | ".join(classes) + " |\n|---|" + "---|" * len(classes) + "\n")
        for src, (cnt, lines) in sorted(per.items()):
            fh.write(f"| {src} | " + " | ".join(f"{cnt[c]} ({lines[c]} lines)" for c in classes) + " |\n")
        if len(per) > 1: fh.write("| **all** | " + " | ".join(f"{tc[c]} ({tl[c]} lines)" for c in classes) + " |\n")
        for c, title, col in (("transliteration", "Transliterations: to register as variant names (the harvest's ALIASES or the names register)", "the form it is a variant of"),
                              ("ungarblable", "Ungarblable: the OCR's confusions undone give a known name", "target"),
                              ("near a head", "Near a head with more lines: variants for the review", "the head; and why garbled, if so"),
                              ("attested, not folded", "Attested as surnames in Wikidata: not folded", "the fold it would have been"),
                              ("garbled", "Garbled, no target yet", "why"), ("Ido roster", "On the Ido roster, not the dowse roster", "Ido name"),
                              ("unknown", "Unknown, five lines or more: most likely names read right", "")):
            sel = [r for r in rows[c] if c != "unknown" or r[2] >= 5 or a.lists]   # with --lists every one: a name only
            # in lists, heading nothing anywhere, is the suspect (MORAVIV, 2026-10-28)
            fh.write(f"\n## {title} ({len(sel)})\n\n| file | head | lines | {col} |\n|---|---|---|---|\n")
            if not (a.lists and c == "unknown"): sel = sorted(sel, key=lambda r: (r[0], -r[2], r[1]))   # the screen's own order
            for src, h, n, t in sel: fh.write(f"| {src} | {h} | {n} | {t} |\n")
    print("wrote", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    main()
