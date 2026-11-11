#!/usr/bin/env python3
r"""ocr-index-store — the stored index: a strong name search as a look-up, not a comparison (the editor 2026-11-07).

    tools/ocr-index-store.py update [--jobs N] [--store DIR] [--texts FILE]   every search text indexed, by the hash of its text
    tools/ocr-index-store.py names ROSTER [--jobs N] [--store DIR]            every form of the roster against every word form
    tools/ocr-index-store.py fold [--quantum N] [--texts FILE] [--no-update]  update, then the new word forms against the names asked
    tools/ocr-index-store.py status [--store DIR]
    tools/ocr-index-store.py check ROSTER --texts FILE [--store DIR]          stored against ocr_index.match, on those texts

WHAT IS STORED, under sources/ocr-work/index-store.noindex/ (untracked: it holds the texts' words):
- texts/<sha1>.bin: one search text's word forms, {form: [(page, as read)]}, as ocr_index.build(words_only=True) gives. The
  file is named by the hash of the text, so a changed text cannot be taken for its old index: a stale entry is impossible, only
  a missing one. `update` indexes what is missing; `ocr-dowse.py --stored` refuses a text with none. A chain calls `update` at
  its end (the editor); skipping it costs a refusal, never a wrong answer.
- store.sqlite: texts (path, sha1); forms (id, form), every distinct word form, only ever added to; matches (f, form_id, why),
  each roster form's matching word forms; done (f, shard), which blocks of forms a roster form has been compared with; meta, the
  matcher's version (the hash of ocr-name-search.py and its confusions): another version refuses, and `names --rebuild` starts
  the matches again.

WHY THIS IS THE SAME SEARCH. ocr_index.match_words() is match()'s word step alone, and what it returns depends only on the name's
form and the word's. The page rule (a name's second form only on pages its first did not hit) is applied at look-up, in
stored_hits(), as match() applies it. So this covers --strong-only, which uses words alone; the join tiers (parts, pairs, column
splits) are not stored, and a presence record still runs the old way. `check` compares the two; so did a search of 1,803 pages.

THE WORK IS IN BLOCKS. Word forms are numbered as found and cut into shards of SHARD forms; a task is one shard against a share of
the names; each finished task is committed at once, so an interrupted run loses at most the tasks in hand, and any run resumes.
A full shard, once compared, is in `done`. The last shard may be part full: a name's place in it is in open_done (f, shard, upto),
so word forms that later fill it are still compared with that name. A new name is compared against all shards; nothing else is
ever compared again. It holds no corpus lock: `names` reads only the store, and `update` reads a text once and names its index by
that text's hash.

CACHE AND FOLD (the editor, 2026-11-07). A name is cached by `names`, on a roster of any size, and is then in `asked`. A changed
text takes a new index by its hash, and the old index is deleted when no text uses it. `fold` compares the word forms not yet seen
against the names asked; --quantum N waits until N new word forms are pending, those being what a fold costs. A name short of the
newest forms is never answered from the store: `ocr-dowse.py --stored` searches it the ordinary way, so skipping a fold costs time,
never a hit. WRITE-SET: the store's folder only. Ezri, 2026-11-07.
"""
import argparse, collections, glob, hashlib, importlib.util, marshal, os, sqlite3, sys, time, zlib
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocr_index as IX
import cupel_workers as CW
NS = IX.NS
G = os.path.normpath(os.path.join(HERE, "..", "published", "heterophony-resources", "geniza"))
S = os.path.join(G, "sources")
DEFAULT = os.path.join(S, "ocr-work", "index-store.noindex")
FOLDERS = ("ocr-rendersearch", "ocr-rendersearch-all", "ocr-rendersearch-rus", "ocr-rendersearch-hye", "ocr-rendersearch-kat")
SHARD = int(os.environ.get("OCR_STORE_SHARD", 200_000))   # the variable for tools/ocr-index-store-test.py alone
SHARE = 200          # roster forms a task


def version():
    h = hashlib.sha1()
    for f in ("ocr-name-search.py", "ocr-name-search-confusions.tsv"):
        h.update(open(os.path.join(HERE, f), "rb").read())
    return h.hexdigest()[:16]


def db(store):
    c = sqlite3.connect(os.path.join(store, "store.sqlite"), timeout=120)
    c.executescript("""PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS texts (path TEXT PRIMARY KEY, sha1 TEXT);
        CREATE TABLE IF NOT EXISTS forms (id INTEGER PRIMARY KEY AUTOINCREMENT, form TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS indexed (sha1 TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS matches (f TEXT, form_id INTEGER, why TEXT);
        CREATE INDEX IF NOT EXISTS matches_f ON matches (f);
        CREATE TABLE IF NOT EXISTS done (f TEXT, shard INTEGER, PRIMARY KEY (f, shard)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS open_done (f TEXT, shard INTEGER, upto INTEGER, PRIMARY KEY (f, shard)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS asked (f TEXT PRIMARY KEY) WITHOUT ROWID;""")
    return c


def blob_path(store, sha):
    return os.path.join(store, "texts", sha[:2], sha + ".bin")


def load_blob(store, sha):
    return marshal.loads(zlib.decompress(open(blob_path(store, sha), "rb").read()))


_D = None
def read_text(f):
    """the search's own reading of a text (a born-digital text's paragraphs as pages), from ocr-dowse.py."""
    global _D
    if _D is None:
        s = importlib.util.spec_from_file_location("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
        _D = importlib.util.module_from_spec(s); a, sys.argv = sys.argv, ["x"]; s.loader.exec_module(_D); sys.argv = a
    return _D.read_text(f)


def text_sha(f):
    return hashlib.sha1(open(f, "rb").read()).hexdigest()


def index_one(job):
    """one text, its index written if the store has none: (relative path, sha1, its forms if written or asked for)."""
    store, f, want = job
    sha = text_sha(f); p = blob_path(store, sha)
    rel = os.path.relpath(f, S)
    if os.path.exists(p):
        return rel, sha, (list(load_blob(store, sha)) if want(sha) else None) if callable(want) else (list(load_blob(store, sha)) if sha in want else None)
    words = IX.build(read_text(f), words_only=True).words
    d = {k: v for k, v in words.items()}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    t = p + f".{os.getpid()}.tmp"
    open(t, "wb").write(zlib.compress(marshal.dumps(d), 1))
    os.replace(t, p)                      # whole or not at all
    return rel, sha, list(d)


def progress(done, of, what, t0):
    s = time.time() - t0
    print(f"  {done:,}/{of:,} {what}, {s / 60:.0f} min so far, about {s * (of - done) / max(done, 1) / 60:.0f} min left", flush=True)


def update(a):
    os.makedirs(a.store, exist_ok=True)
    c = db(a.store)
    if a.texts:
        files = [l.strip() for l in open(a.texts, encoding="utf-8") if l.strip()]
    else:
        files = [f for d in FOLDERS for f in sorted(glob.glob(os.path.join(S, d, "*.txt")))]
    have = {r[0] for r in c.execute("SELECT sha1 FROM indexed")}
    t0 = time.time(); new_forms = new_texts = 0
    was = dict(c.execute("SELECT path, sha1 FROM texts")); old = set()
    jobs = [(a.store, f, frozenset()) for f in files]
    with Pool(a.jobs) as pool:
        for k, (rel, sha, forms) in enumerate(pool.imap_unordered(index_one, jobs, chunksize=4), 1):
            if was.get(rel) not in (None, sha): old.add(was[rel])
            c.execute("INSERT OR REPLACE INTO texts VALUES (?, ?)", (rel, sha))
            if sha not in have:
                if forms is None: forms = list(load_blob(a.store, sha))
                b = c.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
                c.executemany("INSERT OR IGNORE INTO forms (form) VALUES (?)", ((x,) for x in forms))
                c.execute("INSERT OR IGNORE INTO indexed VALUES (?)", (sha,))
                have.add(sha); new_texts += 1
                new_forms += c.execute("SELECT COUNT(*) FROM forms").fetchone()[0] - b
            if k % 200 == 0 or k == len(jobs):
                c.commit(); progress(k, len(jobs), "texts", t0)
    gone = {r[0] for r in c.execute("SELECT path FROM texts")} - {os.path.relpath(f, S) for f in files} if not a.texts else set()
    for g in gone:
        old.add(was.get(g))
        c.execute("DELETE FROM texts WHERE path=?", (g,))
    c.commit()
    used = {r[0] for r in c.execute("SELECT sha1 FROM texts")}
    dropped = 0
    for sha in old - used - {None}:       # the index of a text that has changed: replaced, no text using it
        c.execute("DELETE FROM indexed WHERE sha1=?", (sha,))
        if os.path.exists(blob_path(a.store, sha)):
            os.remove(blob_path(a.store, sha)); dropped += 1
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM forms").fetchone()[0]
    print(f"{len(files):,} texts, {new_texts:,} newly indexed, {len(gone):,} gone, {dropped:,} old indexes dropped; {new_forms:,} new word forms, {n:,} in all", flush=True)


def roster_fs(path):
    """every form of a name the search tries: ocr-dowse's roster reading, then NS.forms, in order, deduplicated."""
    seen = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        for fm in [x.strip() for x in l.split("||")[0].split(" | ") if x.strip()]:
            for f in NS.forms(fm): seen[f] = 1
    return list(seen)


_SH = {}
def compare(job):
    """one stretch of a shard, the word forms numbered above lo up to hi, against a share of the roster forms: [(f, form id, why)].
    The stretch's index is kept for the worker's next task."""
    store, shard, lo, hi, fs = job
    if _SH.get("n") != (lo, hi):
        c = sqlite3.connect(os.path.join(store, "store.sqlite"), timeout=120)
        rows = c.execute("SELECT id, form FROM forms WHERE id > ? AND id <= ?", (lo, hi)).fetchall()
        c.close()
        idx = IX.Index(); ids = {}
        for i, form in rows:
            idx.words[form] = (); ids[form] = i
        _SH.update(n=(lo, hi), idx=idx.bucket(), ids=ids)
    out = []
    with CW.slot():                       # the one dial for the whole machine, so that a chain can take the cores back
        for f in fs:
            for form, why in IX.match_words(f, _SH["idx"]).items():
                out.append((f, _SH["ids"][form], why))
    return shard, hi, fs, out


def same_matcher(c, rebuild=False):
    """the matcher this store's matches were made with, or a refusal."""
    v = version()
    old = c.execute("SELECT v FROM meta WHERE k='version'").fetchone()
    if old and old[0] != v:
        if not rebuild: sys.exit(f"refusing: the matcher has changed since this store's matches ({old[0]} → {v}); --rebuild starts them again")
        c.executescript("DELETE FROM matches; DELETE FROM done; DELETE FROM open_done; DELETE FROM asked;")
    c.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (v,)); c.commit()


def forms_count(c):
    return c.execute("SELECT MAX(id) FROM forms").fetchone()[0] or 0


def compare_all(c, store, fs, jobs_n):
    """fs against every word form they have not met; each task committed as it ends."""
    n = forms_count(c)
    shards = (n - 1) // SHARD + 1 if n else 0
    done = set(c.execute("SELECT f, shard FROM done"))
    place = {(f, sh): u for f, sh, u in c.execute("SELECT f, shard, upto FROM open_done")}
    jobs = []
    for sh in range(shards):
        base, hi = sh * SHARD, min(n, (sh + 1) * SHARD)
        by_lo = collections.defaultdict(list)
        for f in fs:
            if (f, sh) in done: continue
            lo = place.get((f, sh), base)
            if lo < hi: by_lo[lo].append(f)
        for lo, todo in by_lo.items():
            jobs += [(store, sh, lo, hi, todo[i:i + SHARE]) for i in range(0, len(todo), SHARE)]
    print(f"{len(fs):,} roster forms, {n:,} word forms in {shards} shards: {len(jobs):,} tasks to do", flush=True)
    t0 = time.time(); hits = 0
    if jobs:
        with Pool(jobs_n) as pool:
            for k, (sh, hi, tfs, out) in enumerate(pool.imap_unordered(compare, jobs), 1):
                c.executemany("INSERT INTO matches VALUES (?, ?, ?)", out)
                if hi == (sh + 1) * SHARD:        # the shard full: nothing can be added to it
                    c.executemany("INSERT OR IGNORE INTO done VALUES (?, ?)", ((f, sh) for f in tfs))
                    c.executemany("DELETE FROM open_done WHERE f=? AND shard=?", ((f, sh) for f in tfs))
                else:
                    c.executemany("INSERT OR REPLACE INTO open_done VALUES (?, ?, ?)", ((f, sh, hi) for f in tfs))
                c.commit(); hits += len(out)
                if k % max(1, len(jobs) // 200) == 0 or k == len(jobs):
                    progress(k, len(jobs), "tasks", t0)
    print(f"done: {hits:,} matches added", flush=True)


def names(a):
    c = db(a.store)
    same_matcher(c, a.rebuild)
    fs = roster_fs(a.roster)
    compare_all(c, a.store, fs, a.jobs)
    c.executemany("INSERT OR IGNORE INTO asked VALUES (?)", ((f,) for f in fs)); c.commit()


def fold(a):
    if not a.no_update: update(a)
    c = db(a.store)
    same_matcher(c)
    n = c.execute("SELECT COUNT(*) FROM forms").fetchone()[0]    # numbers skip, so the count, not the highest
    row = c.execute("SELECT v FROM meta WHERE k='folded_to'").fetchone()
    pending = n - int(row[0]) if row else n
    if a.quantum and pending < a.quantum:
        print(f"{pending:,} new word forms pending, under the quantum of {a.quantum:,}: not folded", flush=True)
        return
    fs = [r[0] for r in c.execute("SELECT f FROM asked")]
    compare_all(c, a.store, fs, a.jobs)
    c.execute("INSERT OR REPLACE INTO meta VALUES ('folded_to', ?)", (str(n),)); c.commit()


def covered(c, fs):
    """those of fs compared with every word form: a look-up can answer them."""
    n = forms_count(c)
    closed = n // SHARD
    cnt = dict(c.execute("SELECT f, COUNT(*) FROM done WHERE shard < ? GROUP BY f", (closed,)))
    place = dict(c.execute("SELECT f, upto FROM open_done WHERE shard = ?", (closed,))) if n % SHARD else {}
    return {f for f in fs if cnt.get(f, 0) >= closed and (not n % SHARD or place.get(f, 0) >= n)}


def coverage(c, store, files, fs):
    """what a look-up lacks: texts without an index, roster forms not compared with every word form. Empty lists: safe to use."""
    idx = {r[0] for r in c.execute("SELECT sha1 FROM indexed")}
    missing = [f for f in files if text_sha(f) not in idx]
    ok = covered(c, fs)
    short = [f for f in fs if f not in ok]
    v = c.execute("SELECT v FROM meta WHERE k='version'").fetchone()
    return missing, short, (v[0] if v else None) == version()


def matched(c, f):
    """{word form: why} for one roster form."""
    return dict(c.execute("SELECT fo.form, m.why FROM matches m JOIN forms fo ON fo.id = m.form_id WHERE m.f = ?", (f,)))


def stored_hits(c, name, words, cache=None):
    """what ocr_index.match(name, a words-only index) returns, from the store: [(key, how, as read)], words being
    {form: [(key, as read)]}, key the page or (item, text, page). The page rule as in match()."""
    out, done = [], set()
    for f in NS.forms(name):
        m = cache.setdefault(f, matched(c, f)) if cache is not None else matched(c, f)
        hits = {}
        for form, why in m.items():
            for p, r in words.get(form, ()):
                hits.setdefault(p, []).append(("word" + why, r))
        for p, hs in hits.items():
            if p not in done: out += [(p, how, r) for how, r in hs]
        done |= set(hits)
    return out


def stored_search(store, people, jobs, pages=None):
    """for tools/ocr-dowse.py --stored: the people the store can answer, ({person: [((item, text, page), how, as read)]}, the rest
    of the people, a line for the record). jobs: [(item, files)]; pages: {item: pages} or None, as --pages. A person is answered
    only if every form is compared with every word form and every text has an index; anyone else goes to the ordinary search."""
    c = db(store)
    files = [f for _, fl in jobs for f in fl]
    v = c.execute("SELECT v FROM meta WHERE k='version'").fetchone()
    missing, _, same = coverage(c, store, files, [])
    if missing or not v or not same:
        c.close()
        return {}, list(people), f"the store not used: {len(missing)} texts without an index, matcher {'the same' if same else 'changed'}"
    forms_of = {label: [x for fm in forms for x in NS.forms(fm)] for label, forms in people}
    ok = covered(c, {x for fl in forms_of.values() for x in fl})
    mine = [(label, forms) for label, forms in people if all(x in ok for x in forms_of[label])]
    rest = [(label, forms) for label, forms in people if not all(x in ok for x in forms_of[label])]
    cache = {f: matched(c, f) for label, _ in mine for f in forms_of[label]}
    want = {form for m in cache.values() for form in m}
    words = collections.defaultdict(list)
    for item, fl in jobs:
        keep = None if pages is None else pages.get(item, ())
        for f in fl:
            rel = os.path.relpath(f, S)
            d = load_blob(store, text_sha(f))
            for form in want & d.keys():
                words[form] += [((item, rel, p), r) for p, r in d[form] if keep is None or p in keep]
    out = {label: [h for fm in forms for h in stored_hits(c, fm, words, cache)] for label, forms in mine}
    c.close()
    return out, rest, f"{len(mine):,} people answered from the store, {len(rest):,} by the ordinary search"


def check(a):
    c = db(a.store)
    files = [l.strip() for l in open(a.texts, encoding="utf-8") if l.strip()]
    names_ = []
    for l in open(a.roster, encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        names_ += [x.strip() for x in l.split("||")[0].split(" | ") if x.strip()]
    missing, short, ok = coverage(c, a.store, files, roster_fs(a.roster))
    print(f"coverage: {len(missing)} texts without an index, {len(short)} forms short of a shard, version {'ok' if ok else 'DIFFERS'}", flush=True)
    bad = tot = hits = 0
    cache = {}
    for f in files:
        text = read_text(f)
        idx = IX.build(text, words_only=True)
        w = {k: [(p, r) for p, r in v] for k, v in load_blob(a.store, text_sha(f)).items()}
        for n in names_:
            A = collections.Counter(IX.match(n, idx))
            B = collections.Counter((p, how, r) for p, how, r in stored_hits(c, n, w, cache))
            tot += 1; hits += sum(A.values())
            if A != B:
                bad += 1
                if bad <= 8: print("DIFF", os.path.basename(f), repr(n), "match only", list((A - B).items())[:3], "stored only", list((B - A).items())[:3], flush=True)
    print(f"{len(files)} texts × {len(names_)} names = {tot:,} comparisons, {hits:,} hits, {bad} disagreements", flush=True)
    sys.exit(1 if bad else 0)


def status(a):
    c = db(a.store)
    for q, w in (("SELECT COUNT(*) FROM texts", "texts"), ("SELECT COUNT(*) FROM indexed", "indexed"), ("SELECT COUNT(*) FROM forms", "word forms"), ("SELECT COUNT(DISTINCT f) FROM done", "roster forms begun"), ("SELECT COUNT(*) FROM asked", "roster forms asked"), ("SELECT COUNT(*) FROM done", "form-shard blocks done"), ("SELECT COUNT(*) FROM matches", "matches")):
        print(f"{w}: {c.execute(q).fetchone()[0]:,}")
    print("disk GB:", round(sum(os.path.getsize(os.path.join(d, x)) for d, _, fs in os.walk(a.store) for x in fs) / 2**30, 2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("update", "names", "fold", "status", "check"))
    ap.add_argument("roster", nargs="?")
    ap.add_argument("--store", default=DEFAULT); ap.add_argument("--jobs", type=int, default=CW.total("shared"))
    ap.add_argument("--texts"); ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--quantum", type=int, default=0, help="fold: wait until this many new word forms are pending")
    ap.add_argument("--no-update", action="store_true", help="fold: the texts are already indexed")
    a = ap.parse_args()
    {"update": update, "names": names, "fold": fold, "status": status, "check": check}[a.cmd](a)


if __name__ == "__main__":
    main()
