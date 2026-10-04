"""ocr_russian_reading — THE Russian reading of a page: `orus` or `rus`, by the OLD-LETTER RULE.

The editor's ruling of 2026-09-28 (the old-letter rule), on a blind look (an internal record, 2026-09-28, not published): use the
`orus` (pre-reform model) reading where it has >= OLD_MIN words (3+ letters) containing ѣ, і, ѳ or ѵ — the page is
pre-reform print; otherwise the `rus` reading (modern/Soviet Russian, where `rus` reads better). Matched the blind
judges 39/39; the threshold was set on that sample and is checked on held-out pages. Both readings
stay on disk; nothing is overwritten.
"""
import os, re

OLD_MIN = 10
_OLD = re.compile(r"[ѣіѳѵѢІѲѴ]")
_W = re.compile(r"[а-яёѣіѳѵА-ЯЁѢІѲѴ]{3,}")
# SHARPENED (approved by the editor, 2026-10-03, on a look of that date, an internal record, not published): the page
# must ALSO hold at least one old-letter word of 4+ letters that is a Russian word once folded (ѣ→е, і→и, ѳ→ф, ѵ→и,
# final ъ dropped). Stray letters in mangled Latin text («пасіоп» = nacion) and 3-letter chance matches («сіи», «іго»)
# no longer count. Measured: the 28 Sep sample 39/39; Soviet-press misfires 103 → 5. Still NOT a reliable judge of
# orthography (the 3 Oct look: right on 3 of 7 printed-Russian pages) — so where it picks `orus`, the Russian search file
# carries the `rus` reading too (tools/ocr-rus-companion.py).
_FOLD = str.maketrans({"ѣ": "е", "і": "и", "ѳ": "ф", "ѵ": "и"})
_RU = {}


def _ru():
    if "s" not in _RU:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicons", "russian_post1918.txt")
        _RU["s"] = {w.strip() for w in open(p, encoding="utf-8") if w.strip()}
    return _RU["s"]


def old_letter_words(text):
    return sum(1 for w in _W.findall(text) if _OLD.search(w))


def real_old_letter_words(text):
    ru = _ru()
    return sum(1 for w in _W.findall(text) if len(w) >= 4 and _OLD.search(w)
               and w.lower().translate(_FOLD).rstrip("ъ") in ru)


def russian_reading_path(page_txt_path):
    """Given `…/page-NNNN.txt` (or `.rus.txt`), the path of the Russian reading the rule chooses, or None."""
    base = re.sub(r"(\.rus)?\.txt$", "", page_txt_path)
    rus, orus = base + ".rus.txt", base + ".orus.txt"
    # POST-1918 ITEMS (the editor ruled on 2026-10-03, of cupel batch 2, that the item is Soviet-era): an item folder holding
    # the marker ORTHOGRAPHY-POST-1918 always takes `rus`. On its bi-script pages the pre-reform model reads the
    # Esperanto as Cyrillic with Latin i as «і» («пасіеса» = nacieca), which tripped the rule on 103 of 1,857 pages.
    # SET THE MARKER BY GENRE, NEVER BY DATE (the editor's ruling, 2026-10-03; docs/FAILURE-MAP.md, the standing
    # requirement that Russian orthography is decided per page): a post-1918 history, bibliography, dictionary or linguistics
    # text quotes pre-reform print; only a text that never quotes old print (the post-Revolutionary press, Soviet and post-Soviet) gets it.
    if os.path.exists(os.path.join(os.path.dirname(base), "ORTHOGRAPHY-POST-1918")) and os.path.exists(rus):
        return rus
    if os.path.exists(orus):
        t = open(orus, encoding="utf-8", errors="ignore").read()
        if (old_letter_words(t) >= OLD_MIN and real_old_letter_words(t) >= 1) or not os.path.exists(rus):
            return orus
    return rus if os.path.exists(rus) else None


def russian_reading(page_txt_path):
    p = russian_reading_path(page_txt_path)
    return open(p, encoding="utf-8", errors="ignore").read() if p else None
