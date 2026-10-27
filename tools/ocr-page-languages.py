#!/usr/bin/env python3
r"""ocr-page-languages — which language each page reads as, against the word lists: the check of a declared main language.
    python3 tools/ocr-page-languages.py --root <$R> --items <stem,…|@ITEMS.txt> --out <new .md> [--langs <l1,l2,…>] [--min-words 20]
Run sheet C5.1a (corrected 2026-10-25 from «C5.2», to match the sheet) (the editor 2026-10-23, on failure map R52: *Lingua
Internationale* declared «french, occidental» at C5 from the C1 look at one French page, though 71 of its 84 pages read
best as Latino sine flexione). For every page of the named items, the conversion's reading `page-NNNN.txt` (ÖNB and
Google cover sheets skipped, by the gate's own patterns): its words (letters only, two or more) scored against each
candidate language's list (`tools/lexicons/`, loaded as the gate loads them, old Portuguese spellings folded). A page's
language is the one with the most words found in its list and in no other candidate's list (the lists share many short
words; the shared ones decide nothing); a page with fewer than --min-words words, or no such word, is not scored.
Per item: the pages each language wins, and the item's main language in the live language table (its first language);
**FLAG** where another language wins more pages than that main language (a parallel-column paper splits its pages
between its languages, so «fewer than half» would flag honest declarations: *Rund um die Welt*, cupel17). Candidates: --langs, or by default the
planned three, the item's languages in the live table, and the common Latin-script neighbours.
WRITES only --out and the per-page TSV beside it (`<out>.tsv`); refuses either if it exists. Reads only.
"""
import argparse, collections, glob, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ocr_scope_g4", os.path.join(HERE, "ocr-scope-g4.py"))
S = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(S)   # the gate, with its folds (failure map R54)
A = S.A
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
DEFAULT = ["esperanto", "ido", "occidental", "latino-sine-flexione", "french", "german", "spanish", "portuguese",
           "italian", "english"]
WORD = re.compile(r"[^\W\d_]{2,}")


def live_table():
    p = sorted(glob.glob(os.path.join(G, "OCR-TEXT-LANGUAGES-*.tsv")))[-1]
    t = {}
    for l in open(p, encoding="utf-8"):
        c = l.rstrip("\n").split("\t")
        if l.startswith("#") or c[0] == "item" or len(c) < 2:
            continue
        t[c[0]] = [x for x in c[1].split(",") if x]
    return os.path.basename(p), t


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True); ap.add_argument("--items", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--langs"); ap.add_argument("--min-words", type=int, default=20)
    a = ap.parse_args()
    tsv = a.out.rsplit(".", 1)[0] + ".tsv"
    for p in (a.out, tsv):
        if os.path.exists(p):
            sys.exit(f"refusing: {p} exists")
    items = ([l.strip() for l in open(a.items[1:]) if l.strip()] if a.items.startswith("@")
             else [x for x in a.items.split(",") if x])
    tname, table = live_table()
    rows, summary = [], []
    for item in items:
        main_ = next((x for x in table.get(item, []) if not x.endswith(("-cited", "?"))), None)
        cands = ([x for x in a.langs.split(",") if x] if a.langs else
                 list(dict.fromkeys(DEFAULT + [x for x in table.get(item, []) if A.lex(x)])))
        lists = {l: A.lex(l) for l in cands if A.lex(l)}
        wins, scored = collections.Counter(), 0
        for f in sorted(glob.glob(os.path.join(a.root, item, "page-[0-9][0-9][0-9][0-9].txt"))):
            text = open(f, encoding="utf-8", errors="replace").read()
            if any(c.search(text) for c in A.COVER):
                continue
            words = [w.lower() for w in WORD.findall(text)]
            if len(words) < a.min_words:
                continue
            own = {l: sum(1 for w in words if w in L and not any(w in M for m, M in lists.items() if m != l))
                   for l, L in lists.items()}
            best = max(own, key=lambda l: own[l])
            if not own[best]:
                continue
            scored += 1; wins[best] += 1
            rows.append([item, os.path.basename(f)[5:9], str(len(words)), best] +
                        [f"{l}:{own[l]}" for l in sorted(own, key=lambda l: -own[l]) if own[l]])
        flag = bool(main_ and scored and any(c > wins[main_] for l, c in wins.items() if l != main_))
        summary.append((item, main_ or "—", scored, wins, flag))
    with open(tsv, "x", encoding="utf-8") as f:
        f.write("# item\tpage\twords\tbest\twords found in that list only, per language\n")
        f.writelines("\t".join(r) + "\n" for r in rows)
    flagged = [s for s in summary if s[4]]
    out = [f"# Page languages — {len(items)} items, against the word lists ({a.min_words}+ words a page)\n",
           f"`tools/ocr-page-languages.py`; the main language from `{tname}` (its first language); per page "
           f"`{os.path.basename(tsv)}`. **FLAG**: another language wins more pages than the main language.\n",
           f"**Flagged: {len(flagged)}**" + ("" if not flagged else ": " + ", ".join(s[0] for s in flagged)) + "\n",
           "| item | main (table) | pages scored | pages won, by language | |", "|---|---|---:|---|---|"]
    for item, m, n, w, fl in summary:
        out.append(f"| {item} | {m} | {n} | {', '.join(f'{l} {c}' for l, c in w.most_common())} | {'**FLAG**' if fl else ''} |")
    with open(a.out, "x", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{len(items)} items · {sum(s[2] for s in summary)} pages scored · flagged {len(flagged)}"
          + (f": {', '.join(s[0] for s in flagged)}" if flagged else "") + f" → {a.out}")


if __name__ == "__main__":
    main()
