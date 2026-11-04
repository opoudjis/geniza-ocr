#!/usr/bin/env python3
"""The headings of OV's letters, from the Wikisource transcription of Dietterle's edition (2026-11-04; the editor 13:1x:
the headings needed, triangulated from the Wikisource copy of Dietterle).

    tools/ov-headings.py [--write] [--tag T]

Reads the «Paĝo:Zamenhof, Dietterle - Originala Verkaro, 1929.pdf/N» pages 418–587 saved as-is in
geniza/sources/web-2026-11-04-wikisource-ov-letters/pages-NN.json, and for each «{{rh|N-ro N.|DATE}}» (one a letter,
375 in all; the Tekstaro's end mark «OV V.N.» is the same N) takes:
  part        A (already printed letters) or B (unprinted), by the position of B's own heading;
  recipient   the «{{c|Al …}}» or «{{f|Al …}}» heading next to the number, before or after it. Part B is ordered by
              addressee and Dietterle names the addressee only for the first letter or postcard of a group, so in B a
              letter without its own heading takes the last one's, marked «(laŭ la grupo, N-ro M)». A heading that does
              not begin «Al» (part A's «Respondo al …») is kept as the title, its «al X» as the recipient;
  kind        «L» letero, «P» poŝtkarto (B's introduction, PDF page 476); else letero;
  place       the words before the date (B names the place only when it is not Warsaw);
  date        as printed, and as an ISO date by the new style: «L 16. (28) V. 1895» is 1895-05-28, the bracket being the
              Gregorian day (and month, «30. I. (11. II.) 1896»); a note in the date's footnote («dato ne konata») kept;
  nekrasov    the superscript N: the copy supplied by N. V. Nekrasov, Moscow;
  citation    part A's source line, the italic line under the heading.
With --texts (2026-11-04 14:1x, the editor): the letters' own text
as well, to geniza/sources/ocr-work/letters/dietterle-ov-letters-wikisource-2026-11-04<tag>.annotated.txt (untracked),
each under its marker, Dietterle's footnotes numbered and given after the letter as his voice.
With --write: geniza/dowse/letters/OV-HEADINGS-2026-11-04<tag>.tsv, create-only (names, places and dates only; the
letters' text stays under sources/). Without it, the counts and the numbers it could not read. Ezri."""
import argparse, csv, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SRC = os.path.join(G, "sources", "web-2026-11-04-wikisource-ov-letters")
ROMAN = {r: i for i, r in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"), 1)}
ROMAN_OF = {i: r for r, i in ROMAN.items()}
MONTHS = {n: i for i, ns in enumerate((("Januaro", "Jan"), ("Februaro", "Feb"), ("Marto",), ("Aprilo", "Apr"), ("Majo",), ("Junio",),
          ("Julio",), ("Aŭgusto", "Aŭg"), ("Septembro", "Sept"), ("Oktobro", "Okt"), ("Novembro", "Nov"), ("Decembro", "Dec")), 1) for n in ns}

def tokens(t):
    """Top-level «{{…}}» templates and the text between them, braces matched."""
    out, i, n = [], 0, len(t)
    while i < n:
        j = t.find("{{", i)
        if j < 0: out.append(("text", t[i:])); break
        if j > i: out.append(("text", t[i:j]))
        d, k = 0, j
        while k < n:
            if t.startswith("{{", k): d += 1; k += 2
            elif t.startswith("}}", k):
                d -= 1; k += 2
                if d == 0: break
            else: k += 1
        out.append(("tpl", t[j:k])); i = k
    return out

def args(tpl):
    """A template's name and its top-level arguments."""
    body, parts, d, cur = tpl[2:-2], [], 0, ""
    for ch_i, ch in enumerate(body):
        if body.startswith("{{", ch_i) or body.startswith("[[", ch_i): d += 1
        if body.startswith("}}", ch_i) or body.startswith("]]", ch_i): d -= 1
        if ch == "|" and d == 0: parts.append(cur); cur = ""
        else: cur += ch
    parts.append(cur)
    return parts[0].strip(), parts[1:]

def plain(s):
    """Wiki markup to plain text: footnotes dropped, small templates to their text, italics and tags removed."""
    s = re.sub(r"<ref[^>/]*/>", "", s); s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    # the templates that keep their text, innermost first, to the end, before any other is dropped: «{{lang|de|… {{sp|
    # konnte}} …}}» lost its whole German original when the drop ran in the same round (no. 374, 2026-11-04 14:3x)
    for _ in range(6):
        while True:
            t = re.sub(r"\{\{(?:sp|lang\|[a-z-]+|sc|tab|nowrap|sup)\|([^{}]*)\}\}", r"\1", s)
            if t == s: break
            s = t
        t = re.sub(r"\{\{[^{}]*\}\}", "", s)
        if t == s: break
        s = t
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", " / ", s); s = re.sub(r"<[^>]+>", "", s); s = s.replace("''", "")
    return re.sub(r"\s+", " ", s).strip(" /")

def notes(s):
    return "; ".join(plain(m) for m in re.findall(r"<ref[^>/]*>(.*?)</ref>", s, flags=re.S))

def parse_date(raw):
    """«{{sup|N}} P. 2. (14.) X. 1887» → (kind, place, printed, ISO, nekrasov)."""
    nek = bool(re.search(r"\{\{sup\|N\}\}|<sup>N</sup>", raw))
    s = plain(re.sub(r"\{\{sup\|N\}\}|<sup>N</sup>", "", raw))
    kind = ""
    m = re.match(r"([LP])\b\.?\s*", s)
    if m: kind, s = {"L": "letero", "P": "poŝtkarto"}[m.group(1)], s[m.end():]
    m = re.match(r"([^\d(]*?)[,\s]*(?=[\d(]|$)", s)
    place = m.group(1).strip(" ,") if m else ""
    rest = s[m.end():] if m else s
    # a place is a name: not «sen dato», «Fine de», «Folio.», «? Marto», a month or a numeral (the first run took them)
    if not re.fullmatch(r"[A-ZĈĜĤĴŜŬ][\w’'\- ]*", place) or place.split()[0].rstrip(".") in MONTHS or \
       place.lower().startswith(("sen dato", "fine de", "folio", "poŝtmandata", "komence", "meze")) or re.fullmatch(r"[IVX]+", place):
        place, rest = "", s
    for name, k in MONTHS.items(): rest = re.sub(rf"\b{name}\b\.?", f"{ROMAN_OF[k]}.", rest)
    rest = re.sub(r"(?<!\d)(\d{1,2})\.\s*(\d{1,2})\.\s*(?=(?:18|19)\d\d)", lambda q: f"{q.group(1)}. {ROMAN_OF[int(q.group(2))]}. " if 1 <= int(q.group(2)) <= 12 else q.group(0), rest)
    iso, y = "", re.findall(r"(?<!\d)(18[6-9]\d|19[0-2]\d)(?!\d)", rest)
    if y:
        year = int(y[-1])
        # «16. (28) V.», «30. I. (11. II.)»: the bracket the new style; else «14. IX.»; else «IX.»; else the year
        m = re.search(r"(\d{1,2})\.?\s*(?:([IVX]+)\.?\s*)?\(\s*(\d{1,2})\.?\s*(?:([IVX]+)\.?)?\s*\)\s*(?:([IVX]+)\.)?", rest)
        if m and (m.group(4) or m.group(2) or m.group(5)):
            mo = m.group(4) or m.group(5) or m.group(2)
            if mo in ROMAN:
                # a new-style January after an old-style December: the year printed is the old style's
                if m.group(2) == "XII" and m.group(4) == "I" and len(y) == 1: year += 1
                iso = f"{year}-{ROMAN[mo]:02d}-{int(m.group(3)):02d}"
        if not iso:
            m = re.search(r"(?:(\d{1,2})\.\s*)?\b([IVX]+)\.\s*(?:18|19)\d\d", rest)
            if m and m.group(2) in ROMAN: iso = f"{year}-{ROMAN[m.group(2)]:02d}" + (f"-{int(m.group(1)):02d}" if m.group(1) else "")
        if not iso: iso = str(year)
    return kind, place, s.strip(), iso, nek

def heading(tpl):
    name, a = args(tpl)
    if name not in ("c", "f") or not a: return None
    # a right-aligned line is the previous letter's signature («Kun estimo Dro Esperanto.»), not a heading
    if any(re.match(r"\s*(align\s*=\s*right|dekstra\s*=)", x) for x in a[1:]): return None
    t = plain(a[0]).strip()
    if not t or t in ("☆", "*", "* * *") or re.match(r"[AB]\. (JAM|ĜIS)", t): return None
    return t

def body_text(s):
    """A letter's wikitext to the readers' text: paragraphs kept, the PDF page marked, Dietterle's footnotes numbered in
    the text («⟦noto 1⟧») and returned apart, as his voice and not the letter's."""
    s = re.sub(r"<noinclude>.*?</noinclude>", "", s, flags=re.S)
    fn = []
    # «Wüster: EG Rim Capé»: a catalogue siglum on its own line (19 of them), not the letter's words: to the notes
    s = re.sub(r"(?m)^Wüster:[^\n]*\n?", lambda m: fn.append("siglo: " + m.group(0).strip()) or "", s)
    s = re.sub(r"<<PAGE (\d+)>>", lambda m: f"\n⟦PDF-paĝo {m.group(1)}⟧\n", s)
    def note(m):
        fn.append(plain(m.group(1))); return f"⟦noto {len(fn)}⟧"
    s = re.sub(r"<ref[^>/]*>(.*?)</ref>", note, s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "⟦noto, kiel supre⟧", s)
    out = []
    for kind, t in tokens(s):
        if kind == "tpl":
            name, a = args(t)
            if name in ("c", "f", "rh", "RunningHeader"): t = " ".join(x for x in a if "=" not in x.split("|")[0] and x.strip() not in ("c", "int"))
            elif name in ("---",): t = "—"
            elif name in ("tab", "anchor"): t = ""
        out.append(t)
    lines = [plain(l) for l in "".join(out).split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text, fn

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true"); ap.add_argument("--tag", default="b")
    ap.add_argument("--texts", help="with --write: the letters' own text too, for «all», «3,5,14», or the numbers missing from a LETTERS-INDEX-*.tsv")
    a = ap.parse_args()
    pages = {}
    for f in sorted(glob.glob(os.path.join(SRC, "pages-*.json"))):
        for v in json.load(open(f, encoding="utf-8"))["query"]["pages"].values():
            if "revisions" in v: pages[int(v["title"].rsplit("/", 1)[1])] = v["revisions"][0]["slots"]["main"]["*"]
    text = "".join(f"\n<<PAGE {n}>>\n" + pages[n] for n in sorted(pages))
    btop = text.index("B. ĜIS NUN NEPRESITAJ")
    toks = tokens(text)
    # transparent between a heading and its number: whitespace, tags, the page marks, anchors
    blank = lambda k: (toks[k][0] == "text" and not plain(re.sub(r"<<PAGE \d+>>", "", toks[k][1])).strip()) or \
                      (toks[k][0] == "tpl" and args(toks[k][1])[0] in ("anchor", "---", "c", "f") and not heading(toks[k][1]))
    pos, offs = 0, []
    for kind, s in toks: offs.append(pos); pos += len(s)
    # the number in «{{rh|N-ro N.|DATE}}», in «{{RunningHeader|N-ro N.|DATE|}}» (239, 240), or as plain text after a
    # page's header, «…</noinclude>N-ro 214. L. 8. XII. 1901» (214–217)
    found = []
    for k, (kind, s) in enumerate(toks):
        if kind == "tpl":
            name, ar = args(s)
            m = re.match(r"\s*N-ro\s*(\d+)\.?", ar[0]) if name in ("rh", "RunningHeader") and ar else None
            if m: found.append((k, int(m.group(1)), ar[1] if len(ar) > 1 else "", True, offs[k], offs[k] + len(s)))
        else:
            for m in re.finditer(r"(?:^|>)[ \t]*N-ro\s*(\d+)\.[ \t]*([^\n<]*)", s, re.M):
                found.append((k, int(m.group(1)), m.group(2), False, offs[k] + m.start(), offs[k] + m.end()))
    rows, last_b, main_b, seen, spans = [], None, None, set(), []
    for k, n, raw, tpl, o1, o2 in found:
        if n in seen: continue
        seen.add(n)
        heads = []
        # a number in plain text shares its token with the text round it: no headings looked for next to it
        j = k - 1 if tpl else -1
        while j >= 0 and (blank(j) or (toks[j][0] == "tpl" and heading(toks[j][1]))):
            if toks[j][0] == "tpl" and heading(toks[j][1]): heads.insert(0, heading(toks[j][1]))
            j -= 1
        start = offs[j + 1] if tpl else o1
        j = k + 1 if tpl else len(toks)
        while j < len(toks) and (blank(j) or (toks[j][0] == "tpl" and heading(toks[j][1]))):
            if toks[j][0] == "tpl" and heading(toks[j][1]): heads.append(heading(toks[j][1]))
            j += 1
        spans.append((n, start, offs[j] if tpl and j < len(toks) else o2))
        part = "A" if offs[k] < btop else "B"
        cite = ""
        if part == "A" and j < len(toks):
            nxt = "".join(x[1] for x in toks[j:j + 4])
            mm = re.match(r"\s*(?:\{\{tab\}\})?\s*''(.+?)''\s*\n", nxt.replace("{{tab}}", "", 1) if nxt.lstrip().startswith("{{tab}}") else nxt)
            if mm: cite = plain(mm.group(1))
        # a heading in brackets, «(Al la prezidanto)», «(Al s-ro F. Postnikov)», names a person within the group
        # (the Societo «Espero», 139–190, by the page headers); so does «Al la prezidanto …» (2026-11-04 14:1x)
        sub = any(h.startswith("(") and h.endswith(")") for h in heads)
        heads = [h[1:-1].strip() if h.startswith("(") and h.endswith(")") else h for h in heads]
        al = next((h for h in heads if re.match(r"(?i)al\b", h)), "")
        title = next((h for h in heads if not re.match(r"(?i)al\b", h)), "")
        rec = re.sub(r"(?i)^al\b\s*", "", al) if al else ""
        if not rec and title:
            mm = re.search(r"\bal\s+(.+?)(?:\s*/|$)", title)
            if mm: rec = mm.group(1)
        if rec.strip(" .…?") == "" and "?" in rec: rec = "ne konata (Dietterle: «Al…?»)"
        # part A's heading's second line: «(Pri la „Delegacio“)» the subject, to the title; «(P. Ahlberg, Stockholm)» the
        # recipient's name, kept with him (16 of them, 2026-11-04 14:2x)
        while " / (" in rec:
            rec, more = rec.split(" / (", 1)
            if more.startswith(("Pri ", "pri ")): title = (title + " / " if title else "") + "(" + more
            else: rec = f"{rec} ({more}"
        if part == "B" and rec:
            if (sub or re.match(r"la [a-zĉĝĥĵŝŭ]", rec)) and main_b: rec = f"{rec} (por {main_b})"
            else: main_b = rec
            last_b = (rec, n)
        elif part == "B" and last_b: rec = f"{last_b[0]} (laŭ la grupo, N-ro {last_b[1]})"
        if not rec: rec = "ne donita"
        page = int(re.findall(r"<<PAGE (\d+)>>", text[:offs[k]])[-1])
        dk, place, printed, iso, nek = parse_date(raw)
        rows.append([n, part, page, dk or "letero", rec, title, place, printed, iso, notes(raw), "jes" if nek else "", cite])
    rows.sort()
    miss = [n for n in range(1, 376) if n not in seen]
    from collections import Counter
    print(f"letters read: {len(rows)} (part A {sum(r[1] == 'A' for r in rows)}, B {sum(r[1] == 'B' for r in rows)}); not read: {miss or 'none'}")
    print(f"  recipient: own heading {sum(1 for r in rows if r[4] and 'laŭ la grupo' not in r[4] and r[4] != 'ne donita')}, "
          f"by the group {sum('laŭ la grupo' in r[4] for r in rows)}, none {sum(r[4] == 'ne donita' for r in rows)}")
    print(f"  kind: {dict(Counter(r[3] for r in rows))}; place named {sum(bool(r[6]) for r in rows)}; Nekrasov {sum(bool(r[10]) for r in rows)}")
    print(f"  date: day {sum(len(r[8]) == 10 for r in rows)}, month {sum(len(r[8]) == 7 for r in rows)}, year {sum(len(r[8]) == 4 for r in rows)}, none {sum(not r[8] for r in rows)}")
    texts = {}
    if a.texts:
        if os.path.exists(a.texts):
            have = {int(r["title or mark"].split(".")[-1]) for r in csv.DictReader(open(a.texts, encoding="utf-8"), delimiter="\t")}
            want = [r[0] for r in rows if r[0] not in have]
        else: want = [r[0] for r in rows] if a.texts == "all" else [int(x) for x in a.texts.split(",")]
        for i, (n, start, bstart) in enumerate(spans):
            if n in want: texts[n] = body_text(text[bstart:spans[i + 1][1] if i + 1 < len(spans) else len(text)])
        # a letter the Tekstaro has whole in another text (half of eight seven-word runs or more found there) (half its six-word runs or more) is left
        # out, the separate works read before OV's copies (the editor 2026-11-04 10:4x); one found in part is kept, noted
        tek = {}
        for f in glob.glob(os.path.join(G, "sources", "born-digital-text", "tekstaro-*.txt")):
            if not f.endswith("originala-verkaro.txt"): tek[os.path.basename(f)[9:-4]] = re.sub(r"\s+", " ", open(f, encoding="utf-8").read())
        elsewhere, skipped = {}, {}
        for n, (b, fn) in list(texts.items()):
            # every six-word run of the letter, Dietterle's bracketed translations out (eight probes at fixed places
            # under-read no. 3, the Borovko letter: 2 of 7, against 69% by every run; Miles's question 14:30)
            ws = re.sub(r"\s+", " ", re.sub(r"⟦[^⟧]*⟧|\[[^\]]*\]", "", b)).strip().split(" ")
            runs = [" ".join(ws[i:i + 6]) for i in range(0, len(ws) - 5)]
            hits = {k: round(100 * sum(r in t for r in runs) / len(runs)) for k, t in tek.items()} if runs else {}
            hits = {k: v for k, v in hits.items() if v >= 5}
            if any(v >= 50 for v in hits.values()): skipped[n] = hits; del texts[n]
            elif hits: elsewhere[n] = ", ".join(f"{k} ({v}% de la vortoj)" for k, v in hits.items())
        print(f"  left out, whole in another Tekstaro text: " + "; ".join(f"{n} {h}" for n, h in sorted(skipped.items())))
        print(f"  kept, in part elsewhere: {sorted(elsewhere)}")
        print(f"  texts: {len(texts)} letters, {sum(len(t[0].split()) for t in texts.values())} words, {sum(len(t[1]) for t in texts.values())} notes of Dietterle's")
    if not a.write: print("(dry run: nothing written)"); return rows
    op = os.path.join(G, "dowse", "letters", f"OV-HEADINGS-2026-11-04{a.tag}.tsv")
    if os.path.exists(op): sys.exit(f"refusing to overwrite {op}")
    with open(op, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["N", "part", "PDF page", "kind", "recipient", "title", "place", "date as printed", "date (new style)", "date note", "Nekrasov copy", "citation"])
        w.writerows(rows)
    print(f"wrote {os.path.relpath(op, ROOT)}")
    if texts:
        tp = os.path.join(G, "sources", "ocr-work", "letters", f"dietterle-ov-letters-wikisource-2026-11-04{a.tag}.annotated.txt")
        if os.path.exists(tp): sys.exit(f"refusing to overwrite {tp}")
        R = {r[0]: r for r in rows}
        with open(tp, "x", encoding="utf-8") as fh:
            fh.write("Johannes Dietterle (red.), Originala Verkaro de L. L. Zamenhof (Leipzig 1929), parto V: la leteroj, kiujn la "
                     "Tekstaro ne havas; el la transskribo de eo.wikisource (kontrolita, nivelo 3–4), 2026-11-04.\n")
            for n in sorted(texts):
                r = R[n]; body, fn = texts[n]
                bits = [f"DOKUMENTO OV V.{r[1]} {n}", r[3], "de: ZAMENHOF", f"al: {r[4]}"] + ([f"loko: {r[6]}"] if r[6] else []) + \
                       [f"dato: {r[8] or r[7]}" + (f" ({r[9]})" if r[9] else "")] + ([f"titolo: {r[5]}"] if r[1] == "A" and r[5] else []) + \
                       [f"PDF-paĝo {r[2]}"] + ([f"parte ankaŭ en la Tekstaro: {elsewhere[n]}"] if n in elsewhere else []) + \
                       ["la persona «mi» estas la sendinto, «vi» la ricevinto"]
                fh.write(f"\n=== section {n}: OV V.{n} ===\n\n[" + " · ".join(bits) + "]\n" + body + "\n")
                if fn:
                    fh.write("\n[REDAKTORO: Johannes Dietterle, 1929 · liaj notoj, ne la letero]\n" + "\n".join(f"noto {i}: {t}" for i, t in enumerate(fn, 1)) + "\n")
        print(f"wrote {os.path.relpath(tp, ROOT)}")

if __name__ == "__main__":
    main()
