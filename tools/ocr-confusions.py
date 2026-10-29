#!/usr/bin/env python3
"""The OCR confusions register: what Tesseract prints in place of each letter, measured against a ground truth, for
every letter (not only the accented ones), capitals kept apart, and letter groups (rn for m, ii for u, cl for d).
Asked for by the editor on 2026-10-29, for the gazetteer's OCR-only towns and the towns it does not find, and ranked
above the smelt costing; the design approved earlier the same day for the name ungarbler (F4 weighs a change by its frequency): Miles's vision reads
against Tesseract's, by printing kind. It widens tools/ocr-accent-survey.py (2026-10-05: accented and Cyrillic letters
only, lower-cased, far fewer vision pages), whose table the name search still reads.

GROUND TRUTH: page-NNNN.vision.txt (Miles's vision transcriptions) and page-NNNN.hand.txt (the editor's keying), old
print; the born-digital pages whose own text layer is the preferred reading (PREFERRED.tsv «tl-born…»), modern print.
The vision reads' «[?]» and «[word?]» are taken out first. OCR COMPARED: the block reading page-NNNN.txt (Tesseract
--psm 6, the commonest main text). A page is used only when at least MINPAIR of its truth words find their OCR word.
METHOD: words (whitespace-split, outer punctuation off) aligned case-blind (difflib); a pair kept when the words are
close (similarity ≥ 0.5, lengths within two letters); its letters aligned. Each truth letter gets what was written in
its place («» = dropped, counted only for one letter inside a word);
an unequal run (m → rn, in → m) is counted as a group, up to three letters. CASE: «upper» when the truth letter is a
capital (C read as G is a capital's shape), else «lower»; small capitals the vision reads write in lower case, so their
confusions count as «lower». COST: the edit distance after the name search's fold (tools/ocr-name-search.py): 0 = the
search already sees no difference.
TRUTH THAT IS NOT TRUE (2026-10-29b, Ezri, reading the first register's modern rows for the site page): a truth word
with a Cyrillic or Greek letter («Sovеtunio» with a Cyrillic е, «Ҫefo», «heiβt», «20-а») holds a look-alike typed into
the text layer in place of a Latin letter, which Tesseract reads rightly as the Latin one, or a script the Esperanto
model cannot write at all: the pair is left out. NOT left out: *Informilo por Interlingvistoj* 1999–2002, whose PDFs
lost their Esperanto font and PRINT «interesiøi», «Æinio», «Naðodka» for interesiĝi, Ĉinio, Naĥodka (the page images
looked at, 2026-10-29): Tesseract's «g» for that printed ø is a true confusion, the one it makes on a Danish ø too
(«Translatørforbund»); a first try that dropped those items as false truth was wrong and is undone.

    tools/ocr-confusions.py --survey <new.tsv> --register <new.tsv> --write <new.md> [--jobs N] [--reading fra]

--reading LANG measures another of the page's readings, page-NNNN.<LANG>.txt (a second language's model), instead of
the block reading, on the pages that have it (2026-10-29: what the French model writes for the Esperanto letters, for
the site page Konfuzoj). Such a run is not the register the gazetteer reads: name its files apart.

Writes only those three files (and <survey>.progress while it runs); refuses existing ones.
"""
import argparse, collections, difflib, glob, importlib.util, os, re, sys, unicodedata
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "sources", "ocr-rendersearch")
_s = importlib.util.spec_from_file_location("ns", os.path.join(HERE, "ocr-name-search.py"))
NS = importlib.util.module_from_spec(_s); _s.loader.exec_module(NS)

KEYS = {x[0]: x[1] for x in (l.rstrip("\n").split("\t") for l in open(os.path.join(HERE, "..", "published",
        "heterophony-resources", "geniza", "OCR-ITEM-KEYS.tsv"), encoding="utf-8") if not l.startswith("#"))
        if len(x) > 1}
MINPAIR = 0.3      # share of a page's truth words that must find their OCR word
MAXSEG = 3          # longest letter group counted
PRINT = {"vision": "old", "hand": "old", "born": "modern"}
DOUBT = re.compile(r"\[[^\]]*\]")
EDGE = re.compile(r"^[^\w]+|[^\w]+$")
YEAR = re.compile(r"(1[89]\d\d|20[0-2]\d)")


def pages():
    """(truth file, truth kind) for every vision, hand and born-digital preferred page, sorted."""
    out = []
    for k in ("vision", "hand"):
        out += [(f, k) for f in glob.glob(os.path.join(R, "*", f"page-*.{k}.txt"))]
    for p in glob.glob(os.path.join(R, "*", "PREFERRED.tsv")):
        d = os.path.dirname(p)
        for l in open(p, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) > 1 and x[1].startswith("tl-born") and x[0].isdigit():
                f = os.path.join(d, f"page-{int(x[0]):04d}.tl.txt")
                if os.path.exists(f):
                    out.append((f, "born"))
    return sorted(out)


def words(text):
    t = unicodedata.normalize("NFC", text)
    ws = (EDGE.sub("", w) for w in t.split())
    return [w for w in ws if w and any(c.isalpha() for c in w) and len(w.lower()) == len(w)]


def letters_case(ch):
    return "upper" if ch.isupper() else "lower"


def foreign_script(w):
    return any(unicodedata.name(c, "?").split()[0] in ("CYRILLIC", "GREEK") for c in w if c.isalpha())


def survey(job):
    truth_f, src, reading = job
    stem = re.sub(r"\.(vision|hand|tl)\.txt$", "", truth_f)
    f = stem + (f".{reading}.txt" if reading else ".txt")
    item = os.path.basename(os.path.dirname(truth_f))
    # the item's KEY (OCR-ITEM-KEYS.tsv), not its folder: «29 PDF 9» named nothing a reader could find (the editor,
    # 2026-10-29)
    where = f"{KEYS.get(item, item)} PDF {int(re.search(r'page-(\d+)', stem).group(1))}"
    res = {"conf": collections.Counter(), "tot": collections.Counter(), "pages": collections.defaultdict(set),
           "ex": {}, "used": 0, "words": 0, "src": src, "skip": None}
    if not os.path.exists(f):
        res["skip"] = "no OCR reading"
        return res
    tw = words(DOUBT.sub(" ", open(truth_f, encoding="utf-8", errors="ignore").read()))
    if len(tw) < 20:
        res["skip"] = "fewer than 20 truth words"
        return res
    ow = words(open(f, encoding="utf-8", errors="ignore").read())
    pr = PRINT[src]
    pairs = []
    sm = difflib.SequenceMatcher(None, [w.lower() for w in tw], [w.lower() for w in ow], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace"):
            for i, j in zip(range(i1, i2), range(j1, j2)):
                # a pair of near length only: a word cut short («programero → progr») is a split word, not a misread
                # letter (the first run counted the cut tail as dropped letters, «a» → «» the commonest)
                if op == "equal" or (abs(len(tw[i]) - len(ow[j])) <= 2
                                     and difflib.SequenceMatcher(None, tw[i].lower(), ow[j].lower()).ratio() >= 0.5):
                    pairs.append((tw[i], ow[j]))
    if len(pairs) < MINPAIR * len(tw):
        res["skip"] = f"only {len(pairs)} of {len(tw)} truth words found their OCR word"
        return res
    res["used"], res["words"] = 1, len(pairs)

    def hit(case, a, b, t, o):
        k = (pr, case, a, b)
        res["conf"][k] += 1
        res["pages"][k].add(where)
        if a != b and k not in res["ex"]:
            res["ex"][k] = f"{t} → {o} ({where})"

    for t, o in pairs:
        if foreign_script(t):
            continue
        tl, ol = t.lower(), o.lower()
        for n in range(1, MAXSEG + 1):            # the letters and groups seen, for the shares
            for s in range(len(tl) - n + 1):
                g = tl[s:s + n]
                if all(c.isalpha() for c in g):
                    res["tot"][(pr, letters_case(t[s]), g)] += 1
        cm = difflib.SequenceMatcher(None, tl, ol, autojunk=False)
        for cop, a1, a2, b1, b2 in cm.get_opcodes():
            if cop == "equal":
                for k in range(a1, a2):
                    if tl[k].isalpha():
                        hit(letters_case(t[k]), tl[k], tl[k], t, o)
            elif cop == "insert":
                hit("lower", "", ol[b1:b2], t, o)
            elif cop == "delete" and not (a2 - a1 == 1 and 0 < a1 and a2 < len(tl)):
                continue   # a dropped letter only one at a time and inside the word
            elif cop == "delete" or (a2 - a1) == (b2 - b1):
                for k in range(a1, a2):
                    if tl[k].isalpha():
                        hit(letters_case(t[k]), tl[k], "" if cop == "delete" else ol[b1 + k - a1], t, o)
            elif a2 - a1 <= MAXSEG and b2 - b1 <= MAXSEG and tl[a1:a2].isalpha():
                hit(letters_case(t[a1]), tl[a1:a2], ol[b1:b2], t, o)
    return res


def cost(letter, written):
    return NS.edits(NS.fold(letter), NS.fold(written), 9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--survey", required=True)
    ap.add_argument("--register", required=True)
    ap.add_argument("--write", required=True)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--min-n", type=int, default=5)
    ap.add_argument("--min-share", type=float, default=0.01)
    ap.add_argument("--reading", default="", help="measure page-NNNN.<READING>.txt instead of page-NNNN.txt")
    a = ap.parse_args()
    for p in (a.survey, a.register, a.write):
        if os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    jobs = [(f, k, a.reading) for f, k in pages()
            if not a.reading or os.path.exists(re.sub(r"\.(vision|hand|tl)\.txt$", f".{a.reading}.txt", f))]
    conf, tot, pg, ex = collections.Counter(), collections.Counter(), collections.defaultdict(set), {}
    used = collections.Counter(); skipped = collections.Counter(); nwords = 0
    prog = a.survey + ".progress"
    with Pool(a.jobs) as pool:
        for n, r in enumerate(pool.imap(survey, jobs, chunksize=10), 1):
            conf.update(r["conf"]); tot.update(r["tot"]); nwords += r["words"]
            for k, v in r["pages"].items():
                pg[k] |= v
            for k, v in r["ex"].items():
                ex.setdefault(k, v)
            if r["used"]:
                used[r["src"]] += 1
            else:
                skipped[(r["src"], re.sub(r"\d+", "N", r["skip"]))] += 1
            if n % 100 == 0:
                open(prog, "w").write(f"{n} of {len(jobs)} pages\n")
    rows = []
    for (pr, case, ch, w), m in conf.items():
        if ch == "" or ch == w:
            continue
        n = tot[(pr, case, ch)] or m
        rows.append((pr, case, ch, w, m, n, m / n, cost(ch, w), len(pg[(pr, case, ch, w)]), ex.get((pr, case, ch, w), "")))
    ins = [(pr, case, w, m) for (pr, case, ch, w), m in conf.items() if ch == ""]
    rows.sort(key=lambda r: (r[0], r[1], r[2], -r[4]))
    head = "print\tcase\tletter\twritten\tcount\tletter_total\tshare\tcost_after_fold\tpages\texample\n"
    src = (f"{sum(used.values())} ground-truth pages ({', '.join(f'{k} {v}' for k, v in sorted(used.items()))}), "
           f"{nwords} word pairs, OCR reading page-NNNN.{a.reading + '.' if a.reading else ''}txt")
    fmt = lambda r: "\t".join([*r[:4], str(r[4]), str(r[5]), f"{r[6]:.4f}", str(r[7]), str(r[8]), r[9]]) + "\n"
    with open(a.survey + ".partial", "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-confusions.py over {src}: every letter or group of up to {MAXSEG} letters "
                f"and what OCR wrote in its place, seen twice or more. Do not hand-edit — re-run it.\n" + head)
        f.writelines(fmt(r) for r in rows if r[4] >= 2)
    reg = [r for r in rows if r[4] >= a.min_n and r[6] >= a.min_share and r[7] >= 1]
    with open(a.register + ".partial", "w", encoding="utf-8") as f:
        f.write(f"# GENERATED by tools/ocr-confusions.py over {src}: the confusions the fold of tools/ocr-name-search.py "
                f"does not absorb (cost ≥ 1), seen ≥ {a.min_n} times and ≥ {a.min_share:.0%} of the letter. Read by the "
                f"gazetteer and the name ungarbler. Do not hand-edit — re-run it.\n" + head)
        f.writelines(fmt(r) for r in reg)
    L = ["# The OCR confusions register", "",
         f"`[GENERATED by tools/ocr-confusions.py, {src}. Do not hand-edit. The register: "
         f"{os.path.basename(a.register)} ({len(reg)} rows); the whole survey: {os.path.basename(a.survey)} "
         f"({sum(1 for r in rows if r[4] >= 2)} rows). Cost = edits left after the name search's fold: 0 the search "
         f"already sees no difference. «upper» = the truth letter is a capital.]`", "",
         "## The pages", "", "| truth | used |", "|---|---:|"]
    L += [f"| {k} | {v} |" for k, v in sorted(used.items())]
    L += ["", "| truth | not used, because | pages |", "|---|---|---:|"]
    L += [f"| {k[0]} | {k[1]} | {v} |" for k, v in sorted(skipped.items(), key=lambda kv: -kv[1])]
    for pr in ("old", "modern"):
        for case in ("upper", "lower"):
            for group, test in (("single letters", lambda r: len(r[2]) == 1), ("letter groups", lambda r: len(r[2]) > 1)):
                # by SHARE of the letter, never by count (the editor, 2026-10-29: frequent and infrequent OCR errors told
                # apart); the count is only the floor of evidence (--min-n)
                sel = sorted([r for r in reg if r[0] == pr and r[1] == case and test(r)], key=lambda r: (-r[6], -r[4]))
                if not sel:
                    continue
                L += ["", f"## {pr} print, {case} case, {group}: {len(sel)} confusions, by share of the letter", "",
                      "| letter | written | times | of | share | cost | pages | example |",
                      "|---|---|---:|---:|---:|---:|---:|---|"]
                L += [f"| {r[2]} | «{r[3]}» | {r[4]} | {r[5]} | {100 * r[6]:.1f}% | {r[7]} | {r[8]} | {r[9]} |"
                      for r in sel[:40]]
                if len(sel) > 40:
                    L.append(f"| … | {len(sel) - 40} more in the register | | | | | | |")
    ins.sort(key=lambda x: -x[3])
    L += ["", "## Letters OCR adds that the truth does not have (not in the register), the commonest 20", "",
          "| print | added | times |", "|---|---|---:|"]
    L += [f"| {pr} | «{w}» | {m} |" for pr, case, w, m in ins[:20]]
    with open(a.write + ".partial", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    for p in (a.survey, a.register, a.write):
        os.rename(p + ".partial", p)
    if os.path.exists(prog):
        os.remove(prog)
    print(f"{src}; {sum(skipped.values())} pages not used → {a.survey}, {a.register} ({len(reg)} rows), {a.write}")


if __name__ == "__main__":
    main()
