#!/usr/bin/env python3
"""The letters' readers' copies (2026-11-04; the editor: the dowse to tell the editorial voice from the
letters' own, and to read the first and second person as sender and recipient, by program, since not every letter is
Zamenhof's; Waringhien's own narrative dowsed as a secondary source, approved).

    tools/letters-annotate.py leteroj|ov [--write] [--tag T] [--headings OV-HEADINGS.tsv]

Reads the Tekstaro text (geniza/sources/born-digital-text/tekstaro-leteroj-de-zamenhof.txt, or
tekstaro-originala-verkaro.txt) and writes a copy for the readers with a marker paragraph before each block, the text
itself untouched (its words, its «=== section N ===» lines), so the assembler and the harvest still find every
quotation in the original:
  leteroj  each section by its heading. «N. Letero al Y (dd. M .yy …)»: a document from ZAMENHOF to Y; «N. Letero de X
           al Y (…)»: from X to Y; «N. Poŝtkarto / Telegramo / Karto … al Y»: likewise, its kind kept; «N. ‹title›»: a
           document of that title; a bare «N.»: a document, its title the next line; «(dd. M .yy)»: the previous
           document continued, under that date; every other section (the acts, the months, the prologue, the notes):
           Waringhien's own voice, 1948. A document section may end in Waringhien's comment: the brief says so.
  ov       the letters of sections «V. A» and «V. B» (the Tekstaro kept only an end mark per letter, «OV V.N. YEAR.»):
           each letter from ZAMENHOF, its recipient from the salutation where one names him or her («Estimata sinjoro
           D. Gureviĉ !»), else «ne nomita en la teksto», its year from the end mark; the other sections Zamenhof's
           own works, unmarked. With --headings (2026-11-04 13:5x), Dietterle's own headings from the Wikisource
           transcription (tools/ov-headings.py) by number: the recipient (in part B by the addressee's group), letter
           or postcard, the place when not Warsaw, the date by the new style; the salutation only where he gives none.
The markers, in Esperanto, as the readers read them:
  «[DOKUMENTO 5 · letero · de: ZAMENHOF · al: Kofman · dato: 1901-05-28 · la persona «mi» estas la sendinto, «vi» la ricevinto]»
  «[REDAKTORO: Gaston Waringhien, 1948 · lia propra voĉo, ne la dokumentoj]»
With --write: geniza/sources/ocr-work/letters/<text>.annotated.txt (copyright text, so under sources/, not tracked) and
geniza/dowse/letters/LETTERS-INDEX-<text>.tsv (one row a block: section, kind, sender, recipient, date, title; names and
dates only), both create-only. Without --write it prints the counts. Ezri."""
import argparse, csv, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
TEXTS = {"leteroj": "tekstaro-leteroj-de-zamenhof", "ov": "tekstaro-originala-verkaro"}
ROMAN = {r: i for i, r in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"), 1)}
KINDS = r"(Letero|Leteroj|Poŝtkarto|Poŝtkartoj|Telegramo|Karto|Vizitkarto|Cirkulero|Cirkulera letero|Letero-cirkulero|Respondo|Noto|Bileto)"
EDITOR = "[REDAKTORO: Gaston Waringhien, 1948 · lia propra voĉo, ne la dokumentoj]"

def date_of(s):
    """«28. V .01» → 1901-05-28; «V .01» → 1901-05; «1901» → 1901; else «»."""
    m = re.search(r"(?:(\d{1,2})\s*\.\s*)?\b([IVX]{1,4})\s*\.\s*(\d{2,4})\b", s)
    if m and m.group(2) in ROMAN:
        y = int(m.group(3)); y = y if y > 100 else (1800 + y if y >= 80 else 1900 + y)
        return f"{y}-{ROMAN[m.group(2)]:02d}" + (f"-{int(m.group(1)):02d}" if m.group(1) else "")
    m = re.search(r"\b(18[89]\d|19[01]\d)\b", s)
    return m.group(1) if m else ""

def person(s):
    return re.sub(r"\s+", " ", s).strip(" .,;:")

def marker(n, kind, frm, to, date, title="", place=""):
    bits = [f"DOKUMENTO {n}" if n else "DOKUMENTO", kind]
    if frm: bits.append(f"de: {frm}")
    if to: bits.append(f"al: {to}")
    if place: bits.append(f"loko: {place}")
    if date: bits.append(f"dato: {date}")
    if title: bits.append(f"titolo: {title}")
    if kind.lower().startswith(("letero", "poŝtkarto", "telegramo", "karto", "vizitkarto", "bileto", "respondo")):
        bits.append("la persona «mi» estas la sendinto, «vi» la ricevinto")
    return "[" + " · ".join(bits) + "]"

def leteroj(text):
    parts = re.split(r"^(=== section \d+: .*? ===)\s*$", text, flags=re.M)
    out, index, prev = [parts[0]], [], None
    for i in range(1, len(parts), 2):
        head, body = parts[i], parts[i + 1]
        sec = int(re.match(r"=== section (\d+):", head).group(1)); h = re.match(r"=== section \d+: (.*?) ===", head).group(1).strip()
        m = re.match(r"(\d+)\s*\*?\s*\.\s*(.*)$", h)
        if m:
            n, rest = m.group(1), m.group(2).strip()
            k = re.match(KINDS + r"\b(.*)$", rest)
            if k:
                kind, tail = k.group(1).lower(), k.group(2)
                # sender and recipient before the parenthesis only: inside it are the date and the citation, whose «de»
                # («La Ondo de Esperanto», section 133) is no sender (2026-11-04, the first run)
                who = tail.split("(")[0]
                fr = re.search(r"\bde\s+(.+?)(?=\s+al\s+|\s*\.?\s*$)", who)
                to = re.search(r"\bal\s+(.+?)(?=\s*\.?\s*$)", who)
                frm = person(fr.group(1)) if fr else "ZAMENHOF"
                rec = person(to.group(1)) if to else ""
                mk = marker(n, kind, frm, rec, date_of(tail)); prev = (n, kind, frm, rec)
                index.append([sec, kind, frm, rec, date_of(tail), ""])
            else:
                title = rest or next((l.strip() for l in body.split("\n") if l.strip()), "")
                mk = marker(n, "dokumento", "", "", date_of(rest), title[:80]); prev = (n, "dokumento", "", "")
                index.append([sec, "dokumento", "", "", date_of(rest), title[:80]])
            out += [head, "\n\n" + mk + "\n" + body]
        elif re.match(r"\(\s*\d", h) and prev:
            n, kind, frm, rec = prev
            mk = marker(n, kind + " (daŭrigo)", frm, rec, date_of(h))
            index.append([sec, kind + " (daŭrigo)", frm, rec, date_of(h), ""])
            out += [head, "\n\n" + mk + "\n" + body]
        else:
            index.append([sec, "redaktoro", "WARINGHIEN", "", "1948", h[:80]])
            out += [head, "\n\n" + EDITOR + "\n" + body]
    return "".join(out), index

SALUT = re.compile(r"^(?:Kara|Karaj|Kare|Estimata|Estimataj|Tre estimata|Tre estimataj|Multe estimata|Kara kaj estimata|Sinjoro|Sinjorino|Fraŭlino)\b[^\n!]{0,80}?(?=\s*[!,—])", re.M)
def ov(text, heads=None):
    a = text.index("=== section 91:"); b = text.index("=== section 94:")
    head, body, tail = text[:a], text[a:b], text[b:]
    out, index, pos = [], [], 0
    ends = list(re.finditer(r"^OV V\.\s?(\d+)\.\s*(\d{4})?.*$", body, re.M))
    for m in ends:
        block = body[pos:m.end()]
        # the block's own section line (V.A, V.B) stays where it is, above the first letter of its part
        pre = ""
        sm = re.match(r"(\s*=== section \d+: .*? ===\s*\n)", block)
        if sm: pre, block = sm.group(1), block[sm.end():]
        s = SALUT.search(block)
        rec = person(re.sub(r"^(?:Kara|Karaj|Kare|Estimata|Estimataj|Tre estimata|Tre estimataj|Multe estimata|Kara kaj estimata)\s+", "", s.group(0))) if s else "ne nomita en la teksto"
        # a title alone names no one («Estimata sinjoro!»: the first run counted it as named)
        if re.fullmatch(r"(?i)(s-?ro|sinjoro|sinjorino|fraŭlino|sinjoroj|amiko|amikoj|samideano|samideanoj|kolego|doktoro|profesoro)", rec):
            rec = f"ne nomita en la teksto (nur «{rec}»)"
        n, y = m.group(1), m.group(2) or ""
        # the Tekstaro prints «OV V.187.» twice, the second (1905) after 188: Dietterle's 189. A repeated mark takes the
        # number after the previous block's when his year for it agrees (2026-11-04, the run with --headings)
        if heads and any(r[5] == f"OV V.{n}" for r in index) and index:
            nxt = int(index[-1][5].split(".")[-1]) + 1
            my = re.search(r"\b(1[89]\d\d)\b", m.group(0))
            if nxt in heads and my and heads[nxt]["date (new style)"][:4] == my.group(1): n = str(nxt)
        sec = "V.A" if "=== section 93:" not in body[:m.start()] else "V.B"
        kind, place, title = "letero", "", ""
        h = (heads or {}).get(int(n))
        if h:
            # Dietterle's heading (tools/ov-headings.py) over the salutation; his date by the new style, else as printed
            kind, place, title = h["kind"], h["place"], h["title"] if h["part"] == "A" else ""
            if h["recipient"] != "ne donita": rec = h["recipient"]
            y = h["date (new style)"] or h["date as printed"] or y
            if h["date note"]: y += f" ({h['date note']})"
        out.append(pre + "\n" + marker(f"OV {sec} {n}", kind, "ZAMENHOF", rec, y, title, place) + "\n" + block)
        index.append([sec, kind, "ZAMENHOF", rec, y, f"OV V.{n}"])
        pos = m.end()
    out.append(body[pos:])
    return head + "".join(out) + tail, index

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=sorted(TEXTS)); ap.add_argument("--write", action="store_true")
    ap.add_argument("--tag", default="", help="a suffix for both outputs' names, for a second run (the outputs are create-only)")
    ap.add_argument("--headings", help="ov only: dowse/letters/OV-HEADINGS-*.tsv (tools/ov-headings.py), Dietterle's headings by number")
    a = ap.parse_args()
    name = TEXTS[a.which]
    src = os.path.join(G, "sources", "born-digital-text", name + ".txt")
    text = open(src, encoding="utf-8").read()
    heads = {int(r["N"]): r for r in csv.DictReader(open(a.headings, encoding="utf-8"), delimiter="\t")} if a.headings else None
    new, index = leteroj(text) if a.which == "leteroj" else ov(text, heads)
    if heads:
        got = {int(r[5].split(".")[-1]) for r in index}
        print(f"  headings: {len(got & set(heads))} of the copy's {len(got)} letters; in Dietterle, not in the Tekstaro: {sorted(set(heads) - got)}")
    # the text untouched: every line of the original is in the copy, in order (only marker paragraphs added)
    strip = lambda t: [l for l in t.split("\n") if l.strip() and not l.startswith(("[DOKUMENTO", "[REDAKTORO"))]
    if strip(new) != strip(text): sys.exit("refusing: the copy's text differs from the original's (a marker merged into a line?)")
    from collections import Counter
    c = Counter(r[1] for r in index)
    print(f"{name}: {len(index)} blocks: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    if a.which == "ov": print(f"  recipient named: {sum(1 for r in index if not r[3].startswith('ne nomita'))} of {len(index)}")
    else: print(f"  from another sender: {sum(1 for r in index if r[2] not in ('ZAMENHOF', 'WARINGHIEN', ''))}; to Zamenhof: {sum(1 for r in index if 'zamenhof' in r[3].lower())}")
    if not a.write: print("(dry run: nothing written)"); return
    od = os.path.join(G, "sources", "ocr-work", "letters"); os.makedirs(od, exist_ok=True)
    idd = os.path.join(G, "dowse", "letters"); os.makedirs(idd, exist_ok=True)
    sfx = f"-{a.tag}" if a.tag else ""
    op, ip = os.path.join(od, f"{name}.annotated{sfx}.txt"), os.path.join(idd, f"LETTERS-INDEX-{name}{sfx}.tsv")
    for p in (op, ip):
        if os.path.exists(p): sys.exit(f"refusing to overwrite {p}")
    open(op, "x", encoding="utf-8").write(new)
    with open(ip, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["section", "kind", "sender", "recipient", "date", "title or mark"]); w.writerows(index)
    print(f"wrote {os.path.relpath(op, ROOT)} and {os.path.relpath(ip, ROOT)}")

if __name__ == "__main__":
    main()
