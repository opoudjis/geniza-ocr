#!/usr/bin/env python3
r"""ocr-rus-companion — the RUSSIAN reading of every item that has Russian, as a searchable file
beside the Esperanto one.

    tools/ocr-rus-companion.py <root> <out-dir>
    e.g. tools/ocr-rus-companion.py published/heterophony-resources/geniza/sources/ocr-rendersearch \
                                    published/heterophony-resources/geniza/sources/ocr-rendersearch-rus

WHY (2026-09-27, approved by the editor). A page printed in Russian AND Esperanto has two readings on disk: the
Esperanto one (`page-NNNN.txt`, in the combined `<item>.txt`), which gets the Esperanto right and
turns the Russian into Latin-letter junk, and the Russian one (`page-NNNN.rus.txt`), which gets the
Russian right and turns the Esperanto into Cyrillic junk. Merging them into one text failed five blind
looks (an internal record, 2026-09-27, not published). For SEARCH — presence and absence alike — no merge is needed:
each reading is right in its own script, so searching BOTH covers the page. This is the principle of
`ocr-canonical.py` («neither is better … the record names a text PER PURPOSE»; the original is never
superseded). What was missing was a searchable file for the second reading: until now the Russian
readings sat only as per-page files inside each item's folder, where no search looked.

WHAT. For every item with a `RUSSIAN.json` (the items with Russian candidate pages), writes
`<out-dir>/<item>.txt` in the combined files' format (`=== page N ===` blocks), holding the Russian
reading of each page that PASSES THE PAGE GATE of `ocr-layout-mixed.py` (at least 0.14 of the page's
3+-letter words in the Russian list, pre-1918 letters folded): pages with real Russian on them. Pages
below it are left out — their Russian reading is Esperanto turned into Cyrillic junk. The folder is a
SIBLING of `ocr-rendersearch/`, not inside it, because some twenty tools list `*.txt` in a folder and
would count a second file per item as a second item.

The Esperanto file stays the canonical text and the citation text; nothing in `ocr-rendersearch/`
is touched. Absence claims on these items must search BOTH folders.

GENERATED. Re-run after any Russian re-read; never hand-edit.
"""
import os, re, sys, glob, json, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ml", os.path.join(HERE, "ocr-mixed-lines.py"))
ml = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ml)
sys.path.insert(0, HERE)
import ocr_russian_reading as RR   # the old-letter rule: `orus` or `rus` per page
import ocr_text_languages as TL    # the language table (2026-10-03): which texts print a Cyrillic language
UK_WORDS = 20
_UK = {}


def uk_words(text):
    """Distinct 4+-letter words of a Ukrainian-model reading that are in the Ukrainian list (tools/lexicons/ukrainian.txt,
    built by build-lexicons.py; gitignored, rebuilt locally)."""
    if "s" not in _UK:
        _UK["s"] = {w.strip() for w in open(os.path.join(HERE, "lexicons", "ukrainian.txt"), encoding="utf-8") if w.strip()}
    return len({w.lower() for w in re.findall(r"[Ѐ-ӿ'’]{4,}", text) if w.lower() in _UK["s"]})
_sa = importlib.util.spec_from_file_location("acc", os.path.join(HERE, "ocr-accept.py"))
ACC = importlib.util.module_from_spec(_sa); _sa.loader.exec_module(ACC)   # ru_only_score(): the validated Russian-only score
GATE = 0.14

# FIX 1, TIGHTENED (the editor ruled on 2026-10-02 that a page needs 30 or more Russian words that are not words of another
# language, and that the Russian must look like connected Russian, held to the runs test as stated). Esperanto print read by the Russian model yields Cyrillic
# look-alikes that hit the Russian list (рог = por, пеК = nek, Кат = kaj); of the 351 pages fix 1 alone admitted, 188 kept
# under 10 Russian words once these were removed. A Russian-list word counts only if no look-alike reading of it is an
# Esperanto word; the page needs >= 30 such words AND >= 3 of them standing in runs of >= 3 (column breaks split).
# Measured on known pages: junk (Voĉo de Kuracistoj 1909.7/.8/.9/.11, Ruslanda Esperantisto 1907.8 p.6) 0–5 words, no
# runs; real (La Ondo 1909.02 p.2, Espero Kleriga 1908.1 p.46) 90 and 55 words, 7 in runs. 25 of the 351 pass.
HOM = {"а": "a", "б": "b", "в": "b", "г": "r", "д": "d", "е": "e", "ё": "e", "з": "s", "и": "un", "й": "u", "і": "i",
       "к": "k", "л": "l", "м": "m", "н": "h", "о": "o", "п": "nm", "р": "p", "с": "c", "т": "tm", "у": "yu", "ф": "f",
       "х": "x", "ц": "u", "ш": "w", "щ": "w", "ь": "b", "ы": "b", "ѣ": "e", "ч": "c", "ж": "z", "э": "e", "ю": "io", "я": "a"}
SYM = {"!": "i", "$": "s", "@": "d", "]": "j", "%": "t", "|": "l", "&": "e", "1": "l"}
TOK = re.compile(r"[^\s.,;:()\"«»„“”—\-?|]+")
_EO = set()


def _back(tok):
    import itertools
    opts = []
    for ch in tok.lower():
        if ch in HOM: opts.append(HOM[ch])
        elif ch in SYM: opts.append(SYM[ch])
        elif re.match(r"[a-zĉĝĥĵŝŭ]", ch): opts.append(ch)
        else: return []
    if len(opts) < 3 or len(opts) > 14: return []
    n = 1
    for o in opts: n *= len(o)
    return ["".join(p) for p in itertools.product(*opts)] if n <= 64 else []


def fix1(text, ru):
    if not _EO:
        _EO.update(w.strip().lower() for w in open(os.path.join(HERE, "lexicons", "esperanto.txt"),
                                                   encoding="utf-8", errors="ignore") if w.strip())
    good = runs = run = 0
    for k in TOK.findall(text) + [""]:
        ok = bool(k) and bool(ml.W.fullmatch(k)) and ml.ru_score(k, ru) > 0 and not any(v in _EO for v in _back(k))
        if ok: good += 1; run += 1
        else:
            if run >= 3: runs += run
            run = 0
    return good >= 30 and runs >= 3


def page_gate(text, ru):
    ws = [m.group(0) for m in ml.W.finditer(text)]
    return ml.ru_score(text, ru) / len(ws) if ws else 0.0


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    _, ru = ml.lists()
    items = pages = 0
    skipped = []
    for rj in sorted(glob.glob(os.path.join(root, "*", "RUSSIAN.json"))):
        d = os.path.dirname(rj); stem = os.path.basename(d)
        # THE LANGUAGE TABLE FILTERS (2026-10-03): no companion for a text the table lists with no Cyrillic language —
        # its Russian-model readings are junk (Greek, Ido, Estonian Fraktur, Latin headings read as Cyrillic)
        if TL.cyrillic(stem) == set():
            skipped.append(stem)
            stale = os.path.join(out, stem + ".txt")   # a companion file an earlier run wrote: removed (tools/ocr-chain.sh
            if os.path.exists(stale):                  # backs the whole folder up first, as .bak-<suffix>)
                os.remove(stale)
            continue
        body = []
        for f in sorted(glob.glob(os.path.join(d, "page-*.rus.txt")),
                        key=lambda p: int(re.search(r"page-(\d+)\.rus\.txt", p).group(1))):
            n = int(re.search(r"page-(\d+)\.rus\.txt", f).group(1))
            t = open(f, encoding="utf-8", errors="ignore").read()
            chosen = RR.russian_reading(f) or t
            picked_orus = (RR.russian_reading_path(f) or "").endswith(".orus.txt")
            # FULL-PAGE RE-READ (approved by the editor, 2026-10-01): on some pages the Russian pass read a PHOTO embedded on
            # the page (the page-image helper extracted it in place of the page), so `rus`/`orus` came back near-empty —
            # 142 such pages in 14 items. Where `page-NNNN.rusfull.txt` exists (Tesseract rus --psm 4 on a 300 dpi
            # render of the whole page), it is the reading used.
            # 2026-10-02 (the editor approved both proposals, as too much was at stake): the full-page re-read now exists for EVERY page with a Russian
            # reading; the reading kept is whichever holds MORE real Russian words (ml.ru_score) — no longer the re-read
            # unconditionally (on Ukraina Stelo's Esperanto pages it is Cyrillic junk).
            # 2026-10-02 21:5x: the gate is ALSO tested on the original `rus` reading (t0). Swapping `t` for the re-read
            # alone dropped pages the gate had admitted (HV-13032018 lost 27: the re-read had more Russian words but
            # a lower share). A page passes if EITHER reading passes; more Russian search text can only make absence safer.
            t0 = t
            full = f.replace(".rus.txt", ".rusfull.txt")
            if os.path.exists(full):
                tf = open(full, encoding="utf-8", errors="ignore").read()
                if ml.ru_score(tf, ru) > ml.ru_score(chosen, ru):
                    t = chosen = tf; picked_orus = False
            # FIX 1 (same ruling): a page whose kept reading holds at least 30 real Russian words is admitted even if the
            # proportion gate rejects it — 1,237 pages in 138 items were kept out (Kaŭkaza Esperantisto 1910.5 p.6: all five
            # names the G5 judge saw were in the rejected reading).
            # UKRAINIAN PAGES (2026-10-03 21:3x): the gate reads the Russian-model readings, which garble Ukrainian, and kept
            # 3 of *ukraina*'s 5 look-confirmed Ukrainian pages out (pp. 2, 4, 7). For a text the table lists with Ukrainian,
            # a page is ALSO admitted if its `ukr` reading holds >= UK_WORDS distinct Ukrainian words of 4+ letters.
            ukf = f.replace(".rus.txt", ".ukr.txt")
            uk_ok = ("ukrainian" in (TL.cyrillic(stem) or set()) and os.path.exists(ukf)
                     and uk_words(open(ukf, encoding="utf-8", errors="ignore").read()) >= UK_WORDS)
            if uk_ok or page_gate(t, ru) >= GATE or page_gate(t0, ru) >= GATE or (ACC.ru_only_score(chosen) or 0) >= 40 or fix1(chosen, ru):   # gate on `rus` (0.14 measured on it); rescue as in ocr-layout-mixed.py
                # the text written is the reading the OLD-LETTER RULE chooses (`orus` on pre-reform pages; editor 2026-09-28)
                # BOTH READINGS where the rule picked `orus` (approved by the editor, 2026-10-03): the rule cannot judge orthography
                # reliably (an internal record, 2026-10-03, not published: right on 3 of 7), so the modern-model reading is
                # written too; a name in either is found, and a wrong pick loses nothing.
                also = f"\n--- rus (modern-model reading, kept beside the pre-reform one) ---\n{t0.rstrip()}\n" \
                    if picked_orus and t0.strip() and t0.strip() != chosen.strip() else ""
                # THE UKRAINIAN READING (approved by the editor, 2026-10-03: the Cyrillic search file is where it goes): for a text
                # the language table lists with Ukrainian, `page-NNNN.ukr.txt` (tools/ocr-ukr-pages.py) is written beside
                # the Russian-model readings — the Russian model is the wrong reader for Ukrainian.
                uk = f.replace(".rus.txt", ".ukr.txt")
                if "ukrainian" in (TL.cyrillic(stem) or set()) and os.path.exists(uk):
                    tu = open(uk, encoding="utf-8", errors="ignore").read().strip()
                    if tu:
                        also += f"\n--- ukr (Ukrainian-model reading) ---\n{tu}\n"
                body.append(f"=== page {n} ===\n{chosen.rstrip()}\n{also}")
        target = os.path.join(out, stem + ".txt")
        if body:
            open(target, "w", encoding="utf-8").write("\n" + "\n".join(body))
            items += 1; pages += len(body)
        elif os.path.exists(target):
            os.remove(target)
    print(f"{items} items · {pages} pages of Russian reading written to {out}")
    print(f"{len(skipped)} items skipped: the language table ({os.path.basename(TL.path())}) lists no Cyrillic language")


if __name__ == "__main__":
    main()
