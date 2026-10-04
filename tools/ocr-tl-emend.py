#!/usr/bin/env python3
r"""ocr-tl-emend — emend the born-digital text layers: `page-NNNN.tl.txt` → `page-NNNN.tl-emended.txt`.

    tools/ocr-tl-emend.py --root <ocr-rendersearch> --kind <tl-kind.tsv> --tables <glyph-table dir> --log <manifest.tsv> [--dry-run]

WHY (2026-09-30). The editor judged emending the born-digital layers a tractable and finite task worth doing, and
approved the scope; the emended layer then becomes the PREFERRED reading on born-digital pages, which the editor judged
more authoritative once emended. The faults and their sizes: tools/ocr-tl-born-faults.py and
an internal record (2026-09-30, not published).

The raw layer is never changed. An emended file is written ONLY where a fix applies; the manifest logs every
page written, with the count of each fix. Re-running rewrites the emended files from the raw layer.

Fixes, in order (born-digital pages only: tl-kind.tsv, largest image < 50% of the page):
  1 lig      ligature code points U+FB00–FB06 → their letters (ﬁ → fi)
  2 pua      known private-use glyphs, by rule: Symbol-font bullets (U+F0B7 → •, U+F0A7 → ▪); Adobe small
             capitals U+F761–F77A → a–z; Adobe old-style figures U+F730–F739 → 0–9
  3 table    per-font glyph tables, `<tables>/<corpus>.tsv` (code point in hex · replacement · note). A table is
             made by lining the layer up with our OCR, and is SIGHTED BY THE EDITOR before it is put in
             that directory. Any private-use or U+FFFD glyph left after 2–3 stays as it is.
  4 xsys     x-system digraphs (cx gx hx jx sx; ux after a/e) → ĉ ĝ ĥ ĵ ŝ ŭ, only where the converted word is
             in the Esperanto lexicon (case kept)
  5 accent   NOT APPLIED (see `fix` in `emend`): restoring accents by lexicon damaged valid words and names on
             a sampled dry run. Kept for the record only.
"""
import argparse, glob, os, re, itertools, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EO, ANY = set(), set()
for f in glob.glob(os.path.join(HERE, "lexicons", "*.txt")):
    w = {x.strip().lower() for x in open(f, encoding="utf-8", errors="ignore") if x.strip()}
    ANY |= w
    if os.path.basename(f) == "esperanto.txt":
        EO |= w

LIG = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
PUA = {"": "•", "": "▪"}
PUA.update({chr(0xF761 + i): chr(ord("a") + i) for i in range(26)})
PUA.update({chr(0xF730 + i): str(i) for i in range(10)})
XSYS = {"cx": "ĉ", "gx": "ĝ", "hx": "ĥ", "jx": "ĵ", "sx": "ŝ", "ux": "ŭ"}
ACC = {"c": "ĉ", "g": "ĝ", "h": "ĥ", "j": "ĵ", "s": "ŝ", "u": "ŭ"}
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def keep_case(src, new):
    # an all-capitals word written in x-system keeps a lowercase x («EUxGENO», «MIHxALSKI»): capitals all the same
    letters = src.replace("x", "")
    if len(src) > 1 and letters.isupper():
        return new.upper()
    if src[:1].isupper():
        return new[:1].upper() + new[1:]
    return new


def xsys(w):
    lw = w.lower()
    # A word already valid in some language is left alone: the first dry run (15:15) would have turned French
    # «aux» into Esperanto «aŭ».
    if lw in ANY or not re.search(r"(cx|gx|hx|jx|sx|[ae]ux)", lw):
        return None
    v = re.sub(r"(cx|gx|hx|jx|sx)", lambda m: XSYS[m.group(1)], lw)
    v = re.sub(r"([ae])ux", lambda m: m.group(1) + "ŭ", v)
    return keep_case(w, v) if v in EO else None


def accent(w):
    lw = w.lower()
    if lw in ANY or len(lw) < 3:
        return None
    pos = [i for i, ch in enumerate(lw) if ch in ACC]
    if not pos or len(pos) > 6:
        return None
    found = set()
    for k in range(1, len(pos) + 1):
        for sub in itertools.combinations(pos, k):
            v = "".join(ACC[ch] if i in sub else ch for i, ch in enumerate(lw))
            if v in EO:
                found.add(v)
    return keep_case(w, found.pop()) if len(found) == 1 else None


def load_table(path):
    t = {}
    for l in open(path, encoding="utf-8"):
        x = l.rstrip("\n").split("\t")
        if len(x) >= 2 and re.fullmatch(r"(?i)(u\+)?[0-9a-f]{4,6}", x[0].strip()):
            t[chr(int(x[0].strip().lower().replace("u+", ""), 16))] = x[1]
    return t


def emend(text, table):
    n = collections.Counter()
    out = []
    for ch in text:
        if ch in LIG:
            out.append(LIG[ch]); n["lig"] += 1
        elif ch in PUA:
            out.append(PUA[ch]); n["pua"] += 1
        elif ch in table:
            out.append(table[ch]); n["table"] += 1
        else:
            out.append(ch)
    text = "".join(out)

    def fix(m):
        w = m.group(0)
        v = xsys(w)
        if v:
            n["xsys"] += 1; return v
        # FIX 5 (accent restoration) IS NOT APPLIED (2026-09-30 15:2x). A sampled dry run showed it damages
        # valid words our lexicon lacks: it changes the meaning of verbs («reformigis» → «reformiĝis»,
        # «montrigis» → «montriĝis», both real forms), swaps one word for another («caristoj» tsarists →
        # «ĉaristoj», «praceloj» → «praĉeloj»), and corrupts names («Ahasveros» → «Aĥaŝveroŝ» ×67, «Rakosi» →
        # «Rakoŝi»). The function `accent` is kept for the record. Accent loss is real on only 2 corpora /
        # 16 pages (tools/ocr-tl-born-faults.py); those need another method, decided by the editor.
        return w
    return WORD.sub(fix, text), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True); ap.add_argument("--kind", required=True)
    ap.add_argument("--tables", required=True); ap.add_argument("--log", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    born = sorted({(c, int(p)) for c, p, _, f in (l.rstrip("\n").split("\t") for l in open(a.kind, encoding="utf-8")) if float(f) < 0.5})
    tables = {}
    rows, total, corp = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for c, p in born:
        tf = os.path.join(a.root, c, f"page-{p:04d}.tl.txt")
        ef = os.path.join(a.root, c, f"page-{p:04d}.tl-emended.txt")
        if not os.path.exists(tf):
            continue
        if c not in tables:
            tp = os.path.join(a.tables, c + ".tsv")
            tables[c] = load_table(tp) if os.path.exists(tp) else {}
        raw = open(tf, encoding="utf-8", errors="ignore").read()
        new, n = emend(raw, tables[c])
        if new != raw:
            if not a.dry_run:
                open(ef, "w", encoding="utf-8").write(new)
            rows.append((c, p, n)); total.update(n); corp[c].update(n); total["pages"] += 1
        elif os.path.exists(ef) and not a.dry_run:
            os.remove(ef)   # a page that no longer needs emending keeps no stale emended file
    if not a.dry_run:
        with open(a.log, "w", encoding="utf-8") as fh:
            fh.write("corpus\tpage\tlig\tpua\ttable\txsys\taccent\n")
            for c, p, n in rows:
                fh.write(f"{c}\t{p}\t{n['lig']}\t{n['pua']}\t{n['table']}\t{n['xsys']}\t{n['accent']}\n")
    print(f"{'DRY RUN — ' if a.dry_run else ''}{total['pages']} born-digital pages emended in {len(corp)} corpora; "
          f"fixes: ligatures {total['lig']} · known glyphs {total['pua']} · table glyphs {total['table']} · "
          f"x-system {total['xsys']} · accents {total['accent']}")


if __name__ == "__main__":
    main()
