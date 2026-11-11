#!/usr/bin/env python3
"""Smelt S4: a reading copy of a biography, in the form the S4 template now asks for (the editor, 2026-10-17), for the biographies written before
the template said so. The return is the record and is not changed.

    tools/smelt-s4-view.py <stem> <tag> [--replace]

Reads smelt/<stem>/S4-RETURN-<tag>.md; writes smelt/<stem>/S4-VIEW-<tag>.md (create-only; --replace remakes it):
- the abstract under «### Resumo» is italic (the editor, 17:4x);
- a period summary labelled «*Resumo de la periodo.* …» or «*Resumo.* …» becomes one italic paragraph, unlabelled;
- a note marker «[3]» (digits only, so never «[L3]») becomes a superscript «³»;
- a notes paragraph «**Notoj.** [1] … [2] …» becomes «**Notoj.**» and a numbered list, one note an item.
Since 2026-10-30 also: the dates in ISO form and the abbreviations p., n-ro, vol., fr., kop., the subject's full name
shortened after a section's first mention (compact()), outside the quotations; «Verkoj laŭ la fontoj»
(tools/smelt_works.py, with the works reader's merges and splits) after «Kie troviĝas la fontoj» and in the ToC; a
citation list of more than 8 lines folded into «[vd. fontoj N]» (fold()). Since 2026-11-09, «Samnomuloj» from
S4-SAMNOMULOJ-<tag>.md (smelt-s2-prep.py --samnomuloj, the second route) at the end of «Nomoj».
Since 2026-11-10, the title the gist's name (the fullest established), an abstract's «X (∴ Y)» at the biography's
first mention of X, and the person's pictures under the title (tools/smelt-portraits.py, smelt/PORTRETOJ.tsv).
Then smelt-marks.py (the marks' count) and, since 2026-10-30, fact-labels.py (the labelled copy S4-LABELLED-<tag>.md
with «Referencoj»), so a view is never without its references.
Ezri, 2026-10-17."""
import os, re, sys
import smelt_parts    # the three parts and the ToC (2026-10-22)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

def reopen(par):
    """An italic summary paragraph with titles set back in roman (the template: `*… en* La Lumo *…*`): markdown reopens
    the italics only after a space, so punctuation after a title («Canadien*;») broke the rest of the paragraph (the
    editor, 2026-10-20). The punctuation stays roman, the italics reopen after it; spaces
    move outside the asterisks; an empty italic run is dropped."""
    if not (par.startswith("*") and par.endswith("*")) or par.startswith("**") or par.count("*") < 4: return par
    segs, out = par[1:-1].split("*"), ""
    for k, s in enumerate(segs):
        if k % 2:
            out += s; continue
        if k:
            m = re.match(r"[;:,.!?)»]+", s)
            if m: out += m.group(0); s = s[m.end():]
        lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", s, re.S).groups()
        out += lead + (f"*{core}*" if core else "") + trail
    return out

def tidy(text):
    out, abstract = [], False
    for l in text.split("\n"):
        if l.startswith("#"):
            abstract = l.strip() == "### Resumo"
        elif abstract and l.strip():
            body = l.strip()
            out.append(body if body.startswith("*") and body.endswith("*") else f"*{body}*"); continue
        m = re.match(r"^\*(?:Resumo de la periodo|Resumo)\.\*\s*(.+)$", l)
        if m:
            body = m.group(1).strip()
            out.append(body if body.startswith("*") and body.endswith("*") else f"*{body}*"); continue
        m = re.match(r"^\*\*Notoj\.\*\*\s*(.*)$", l)
        if m:
            nums = re.findall(r"\[(\d+)\]", m.group(1))
            texts = [x for x in re.split(r"\[\d+\]\s*", m.group(1)) if x.strip()]
            out += ["**Notoj.**", ""] + [f"{n}. {t.strip()}" for n, t in zip(nums, texts)]
            continue
        out.append(re.sub(r"(?<![L\w])\[(\d{1,2})\]", lambda mm: mm.group(1).translate(SUP), l))
        if abstract and l.strip(): out.append("")   # the abstract's paragraphs apart (Fable's proposal 10, 2026-10-30)
    # one blank line between blocks, never two (Fable's proposal 10: the notes' double blank)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(reopen(l) for l in out))

# LONG CITATION LISTS FOLDED (Fable's proposal 10; the editor, 2026-10-30: approved, with a «Fontoj»
# list and «[vd. fontoj 1]» inline): a list of more than FOLD lines stands in the prose as «[vd. fontoj N]», and
# the section ends with «**Fontoj.**», a numbered list, one list an item, after its notes; numbered by section, as the
# notes are. The return keeps every list in place.
FOLD = 8
CITE = re.compile(r"\[(L\d+(?:\s*[,;–-]\s*L\d+)*)\]")

def fold(text):
    out, cur = [], []
    def close():
        if cur: out.extend(["", "**Fontoj.**", ""] + [f"{i}. [{c}]" for i, c in enumerate(cur, 1)] + [""]); cur.clear()
    for l in text.split("\n"):
        if l.startswith("#"):
            close(); out.append(l); continue
        def sub(m):
            if len(re.findall(r"L\d+", m.group(1))) <= FOLD: return m.group(0)
            cur.append(m.group(1)); return f"[vd. fontoj {len(cur)}]"
        out.append(CITE.sub(sub, l))
    close()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))

# ISO DATES AND TWO COMPACTIONS (the editor, 2026-10-30, on Devjatnin: ISO dates
# rather than spelled-out ones, which run distractingly long; of Ezri's compactions, 1 and 2 approved, 3
# not): in the reading copy only, outside the sources' quotations. A closed set: the twelve months, «la N-an de», the
# old style. «la 21-an de aprilo 1910 laŭ la malnova stilo (= 4 majo laŭ la nova)» → «1910-04-21 m.s. (= 05-04 n.s.)»,
# «novembro–decembro 1909» → «1909-11/12», «aprilo 1910» → «1910-04»; a day or a month with no year stays. (1) «p.»,
# «n-ro», «vol.», «fr.», «kop.» before or after a number; (2) the subject's full name, after its first mention in a
# section, by the surname. The return keeps every form.
import factline as FL
MON = ["januaro", "februaro", "marto", "aprilo", "majo", "junio", "julio", "aŭgusto", "septembro", "oktobro", "novembro", "decembro"]
M = "(" + "|".join(MON) + ")"
DAY = r"(?:la\s+)?(\d{1,2})(?:-?an|-?a)?"
mm = lambda m: f"{MON.index(m.lower()) + 1:02d}"
DATE_RULES = [
    # the new style in brackets, after an old-style date
    (re.compile(rf"\(=\s*{DAY}(?:\s+de)?\s+{M}(?:\s+(\d{{4}}))?\s+laŭ\s+la\s+nova(?:\s+stilo)?\)", re.I),
     lambda m: f"(= {m.group(3) + '-' if m.group(3) else ''}{mm(m.group(2))}-{int(m.group(1)):02d} n.s.)"),
    # and a day range there: «(= 3–8 majo laŭ la nova)» (Devjatnin's Tutrusa Kongreso, a citation between)
    (re.compile(rf"\(=\s*{DAY}\s*(?:ĝis|–|-)\s*{DAY}(?:\s+de)?\s+{M}(?:\s+(\d{{4}}))?\s+laŭ\s+la\s+nova(?:\s+stilo)?\)", re.I),
     lambda m: f"(= {m.group(4) + '-' if m.group(4) else ''}{mm(m.group(3))}-{int(m.group(1)):02d}/{int(m.group(2)):02d} n.s.)"),
    (re.compile(r"\s+laŭ\s+la\s+malnova\s+stilo\b", re.I), lambda m: " m.s."),
    (re.compile(r"\s+laŭ\s+la\s+nova\s+stilo\b", re.I), lambda m: " n.s."),
    # day ranges: «la 3-an ĝis la 5-an de majo 1910», «3–5 majo 1910»
    (re.compile(rf"{DAY}\s*(?:ĝis|–|-)\s*{DAY}(?:\s+de)?\s+{M}\s+(\d{{4}})", re.I),
     lambda m: f"{m.group(4)}-{mm(m.group(3))}-{int(m.group(1)):02d}/{int(m.group(2)):02d}"),
    (re.compile(rf"{DAY}\s+(kaj|aŭ)\s+{DAY}(?:\s+de)?\s+{M}\s+(\d{{4}})", re.I),
     lambda m: f"{m.group(5)}-{mm(m.group(4))}-{int(m.group(1)):02d} {m.group(2)} {m.group(5)}-{mm(m.group(4))}-{int(m.group(3)):02d}"),
    (re.compile(rf"{DAY}(?:\s+de)?\s+{M}\s+(\d{{4}})", re.I), lambda m: f"{m.group(3)}-{mm(m.group(2))}-{int(m.group(1)):02d}"),
    (re.compile(rf"{M}\s*[–-]\s*{M}(?:\s+de)?\s+(\d{{4}})", re.I), lambda m: f"{m.group(3)}-{mm(m.group(1))}/{mm(m.group(2))}"),
    (re.compile(rf"\b{M}(?:\s+de)?\s+(\d{{4}})", re.I), lambda m: f"{m.group(2)}-{mm(m.group(1))}"),
]
# [WITHDRAWN 2026-11-11, no longer called by compact(); kept for the record] A DATE WITH ITS YEAR UNSAID (the editor, 2026-11-10, of Devjatnin's beside
# «1910-04-20/25 m.s.»: a date with no year stated left unconverted, a jarring inconsistency; and
# «Inter februaro kaj 1910-03», another date the replacement missed): after DATE_RULES, a day or a month
# with no year takes (1) the year of an ISO date it is paired with by «kaj», «ĝis» or «aŭ» right after it («februaro kaj
# 1910-03» → «1910-02 kaj 1910-03»), else (2) the last year written before it in the same paragraph; with neither it stays.
# The months in lower case only (Aŭgusto the name stays). INHERITED collects each change for review.
# a year counts only as a date: an ISO date, or a year after a preposition of time; never a bare number («1750 ekzempleroj»)
# nor a historian's year in brackets («Jossinet (1998)»)
# («n-roj 1856 kaj 1857 de la Adresaro», «de 1500 ekzempleroj»: no «kaj», and 1800-2029 only), or a place and year in brackets
# («(Ĝenevo, 1906)»)
YR = re.compile(r"\b(1[89]\d\d|20[0-2]\d)(?=-\d\d\b)|(?:\b(?:[Ee]n|[Dd]e|[Ee]kde|ĝis|[Pp]ost|[Aa]ntaŭ|[Dd]um|[Ii]nter|[Ĉĉ]irkaŭ|[Jj]e)\s+(?:la\s+jaro\s+)?)(1[89]\d\d|20[0-2]\d)\b(?!\))|,\s+(1[89]\d\d|20[0-2]\d)\)")
AFTER = re.compile(r"\s*\((?:∴|◊\?|=)?\s*(1[89]\d\d|20[0-2]\d)\)")   # «La 8-an de aŭgusto (∴ 1904)»: the year the writer put after it
YEARLESS = [
    ("months", re.compile(rf"\b{M}\s*[–-]\s*{M}\b(?![-\d])(?!\s+\d{{4}})"),
     lambda m, y: f"{y}-{mm(m.group(1))}/{mm(m.group(2))}"),   # «aŭgusto–septembro» → «1899-08/09», as DATE_RULES with a year
    ("days", re.compile(rf"\b{DAY}\s+(kaj|aŭ)\s+{DAY}(?:\s+de)?\s+{M}\b(?![-\d])(?!\s+\d{{4}})"),   # «la 29-a kaj la 31-a de aŭgusto»
     lambda m, y: f"{y}-{mm(m.group(4))}-{int(m.group(1)):02d} {m.group(2)} {y}-{mm(m.group(4))}-{int(m.group(3)):02d}"),
    ("range", re.compile(rf"\b{DAY}\s*(?:ĝis|–|-)\s*{DAY}(?:\s+de)?\s+{M}\b(?![-\d])(?!\s+\d{{4}})"),
     lambda m, y: f"{y}-{mm(m.group(3))}-{int(m.group(1)):02d}/{int(m.group(2)):02d}"),
    ("day", re.compile(rf"\b{DAY}(?:\s+de)?\s+{M}\b(?![-\d])(?!\s+\d{{4}})"),
     lambda m, y: f"{y}-{mm(m.group(2))}-{int(m.group(1)):02d}"),
    ("month", re.compile(rf"\b{M}\b(?![-\d])(?!\s+\d{{4}})"),
     lambda m, y: f"{y}-{mm(m.group(1))}"),
]
# a list whose last member carries the year: «februaro, marto, aprilo kaj 1906-08/09», «februaro kaj 1910-03»
PAIRED = re.compile(rf"(?:\s*,\s*(?:{DAY}(?:\s+de)?\s+)?{M})*\s+(?:kaj|ĝis|aŭ)\s+(\d{{4}})-\d\d\b")
INHERITED = []


def inherit_years(l, hy=None):
    """One paragraph: each yearless day or month outside the quotations given its year (above), the quotations untouched;
    hy, the year of the section's heading when it names one year alone («#### 1902»), for a paragraph with no year before
    the date («(Madrido, la 26-an de majo)» in De Beaufront's 1902)."""
    out, last = [], 0
    def seg(text, prefix):
        for kind, rx, rp in YEARLESS:
            def one(m, rx=rx, rp=rp, kind=kind):
                if m.groups()[-1].lower() != m.groups()[-1]: return m.group(0)   # «Aŭgusto», a name
                after = PAIRED.match(m.string, m.end()) or AFTER.match(m.string, m.end())
                ys = [a or b or c for a, b, c in YR.findall(prefix + m.string[:m.start()])]
                y = after.groups()[-1] if after else (ys[-1] if ys else hy)
                if not y: return m.group(0)
                new = rp(m, y); INHERITED.append((kind, m.group(0), new, (prefix + m.string)[max(0, len(prefix) + m.start() - 70):len(prefix) + m.end() + 30]))
                return new
            text = rx.sub(one, text)
        return text
    done = ""
    for g in FL.QUOTES_NOTES.finditer(l):
        done += seg(l[last:g.start()], done) + g.group(0); last = g.end()
    return done + seg(l[last:], done)


ABBR = [(re.compile(r"\bpaĝoj?n?\s+(?=\[?\d)"), "p. "), (re.compile(r"\bnumero(j?)n?\s+(?=\d)"), lambda m: f"n-ro{m.group(1)} "),
        (re.compile(r"\bvolumoj?n?\s+(?=\d)"), "vol. "), (re.compile(r"(\d)\s+frank(?:oj|ojn|on|o)\b"), r"\1 fr."),
        (re.compile(r"(\d)\s+kopek(?:oj|ojn|on|o)\b"), r"\1 kop.")]

def compact(text, full, short):
    out, seen, n, hy = [], False, {"dates": 0, "abbr": 0, "name": 0}, None
    for l in text.split("\n"):
        if l.startswith("#"):
            seen = False; out.append(l)
            ys = set(re.findall(r"\b1[89]\d\d\b", l)); hy = ys.pop() if len(ys) == 1 else None   # «Januaro–aprilo 1907: … (1907)»
            continue
        if l.startswith("`["): out.append(l); continue   # the tools' own head lines
        for rx, rp in DATE_RULES + ABBR:
            def count(m, rp=rp, rx=rx):
                n["dates" if (rx, rp) in DATE_RULES else "abbr"] += 1
                return rp(m) if callable(rp) else m.expand(rp)
            l = FL.sub_outside(rx, count, l)
        # the year inheritance WITHDRAWN (the editor, 2026-11-11, after for a game of 1940, the year taken from «naskita
        # ĉirkaŭ 1860», and «laŭ la biografio de 1927» dating a congress of 1907: completing years mechanically likely
        # more trouble than it is worth, a matter for the facts rather than postproduction; the proposal approved): a date
        # with no year stays as the writer wrote it; the writers are told to give every date its year (the biography brief)
        if full and full != short and full in l:
            parts = l.split(full)
            keep = 0 if seen else 1   # the first mention in the section stays whole
            l = full.join(parts[:keep + 1]) + "".join(short + p for p in parts[keep + 1:]) if len(parts) > keep + 1 else l
            n["name"] += len(parts) - 1 - keep
            seen = True
        out.append(l)
    text = "\n".join(out)
    if " m.s." in text or " n.s." in text:
        text = text.replace("⚫️: truo en la legitaj fontoj\n", "⚫️: truo en la legitaj fontoj · m.s. / n.s. laŭ la malnova (juliana) / nova stilo\n", 1)
    return text, n

# THE VIEW IN ESPERANTO (2026-11-09; the editor, reviewing Abesgus's labelled copy: far too much English in it; «Devioj de la grupoj aŭ epizodoj, kun kaŭzoj»; «fakt-eltirado» the term here): the
# returns written before these rulings keep their words (the return is the record); the view gives (1) part 3's heading
# in the editor's wording, (2) «fakt-eltirado» for the writers' «dovado» and «dowse», (3) the names register's relation
# names, which the writers quote in English in part 4, in Esperanto
OLD_P3 = "## 3. Foriroj de la grupoj aŭ epizodoj, kaj kial"
NEW_P3 = "## 3. Devioj de la grupoj aŭ epizodoj, kun kaŭzoj"
DOWSE_EO = [(r"\b([Dd])ovad(o|on|a|an|aj|ajn)\b", lambda m: ("F" if m.group(1) == "D" else "f") + "akt-eltirad" + m.group(2)),
            (r"\b([Dd])owse\b", lambda m: ("F" if m.group(1) == "D" else "f") + "akt-eltirado"),
            (r"\b([Dd])owsit(a|aj|an|ajn)\b", lambda m: ("F" if m.group(1) == "D" else "f") + "akt-eltirit" + m.group(2)),
            (r"\b([Dd])owsind(a|aj|an|ajn)\b", lambda m: ("F" if m.group(1) == "D" else "f") + "akt-eltirind" + m.group(2))]
EO_REL = {"other language": "alia lingvo", "spelling": "literumo", "spelling / initials": "literumo / inicialoj",
          "short form": "mallonga formo", "short title": "mallonga titolo", "keep apart": "teni aparte", "name form": "nomformo",
          "name forms": "nomformoj", "OCR form": "OCR-formo", "proposed": "proponita", "two": "du personoj",
          "renamed": "nomŝanĝo", "pseudonym": "pseŭdonimo", "transcription": "transskribo", "title forms": "titolformoj",
          "variant": "varianto", "same person": "la sama persono", "abbreviation": "mallongigo", "other name": "alia nomo",
          "full surname": "plena familinomo", "identification": "identigo", "garbling": "misformo", "successor": "posteulo",
          "same body": "la sama organizo", "same event": "la sama evento", "misprint or OCR": "preseraro aŭ OCR"}

def eo_words(src):
    src = src.replace(OLD_P3, NEW_P3)
    # the scan's page as the labels now give it, «{14}» (the editor, 2026-11-09), where
    # a writer copied the old label form from the labelled profile
    src = re.sub(r"\[PDF (\d+)\]", r"{\1}", src)
    # the joined return's own head lines, in Esperanto in the view (the return keeps them as filed)
    src = re.sub(r"^# Return: (\S+)$", r"# Raporto: \1", src, flags=re.M)
    src = re.sub(r"`\[Filed by Ezri: joined from the (\d+) pieces? the reader wrote \(smelt_pieces\.py join\)\]`",
                 r"`[Arkivita de Ezri: kunmetita el la \1 pecoj, kiujn la legilo skribis (smelt_pieces.py join)]`", src)
    for rx, rp in DOWSE_EO: src = re.sub(rx, rp, src)
    # part 4's register proposals keep the register's English relation names (the editor, 2026-11-09 21:4x: «Proponoj por la
    # registro» in English, since they are all to be resolved anyway): EO_REL is not applied; S5 step 5 takes
    # them into the names register
    return src

MASK = re.compile(r"«[^»\n]*»|(?<=[^\n])\*[^*\n]+\*|`[^`\n]*`|\[[^\]\n]*\]\([^)\n]*\)|<[^>\n]+>|\"[^\"\n]*\"")

def places(text):
    """THE PLACE NAMES (2026-11-10; the editor): smelt/LOKNOMOJ.tsv, an approved list from the gazetteer. «esperanto»: the first mention in
    the prose «Florenco (Firenze)», the later ones «Florenco», a heading «Florenco»; «period»: the name as written, the modern
    form after it at the first mention, «Madraso (Ĉenajo)»; «korekto»: a writer's own Esperanto form replaced by the gazetteer's,
    no brackets («Zuriho» → «Zuriko», 2026-11-10). Outside quotations, titles, notes, links and tags; a name the
    text already gives with its pair beside it is left. -> (text, count)"""
    tp = os.path.join(G, "smelt", "LOKNOMOJ.tsv")
    if not os.path.exists(tp): return text, 0
    rows = [l.split("\t") for l in open(tp, encoding="utf-8").read().split("\n")[1:] if l.strip()]
    # part (1) only, the biography: parts 2-4 are the writer's notes on the lines, which name places as the lines print them
    cut = re.search(r"^## 2\. ", text, re.M)
    text, tail = (text[:cut.start()], text[cut.start():]) if cut else (text, "")
    n = 0
    for w, e, how, *_ in rows:
        # bold first, so its stars pair with no italic star («**Lia libro de 1953**: *Il congresso di Bologna …*»)
        masked = MASK.sub(lambda m: " " * len(m.group(0)), text.replace("**", "  "))
        rx = re.compile(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])")
        out, last, first_done = [], 0, e in masked and how == "esperanto"
        for m in rx.finditer(masked):
            near = text[max(0, m.start() - len(e) - 3):m.end() + len(e) + 3]
            if e in near: continue                       # «Florenco (Firenze)» or «Madraso (Ĉenajo)» already
            ls = text.rfind("\n", 0, m.start()) + 1
            heading = text.startswith("#", ls)
            if how == "korekto":   # a writer's own Esperanto form, not the gazetteer's (2026-11-10, «Zuriho»): replaced, no brackets
                rep = e
            elif how == "esperanto":
                rep = e if (heading or first_done) else f"{e} ({w})"
                if not heading: first_done = True
            else:
                if heading or first_done: continue
                rep = f"{w} ({e})"; first_done = True
            out += [text[last:m.start()], rep]; last = m.end(); n += 1
        text = "".join(out) + text[last:]
    return text + tail, n

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2: sys.exit(__doc__)
    stem, tag = args
    d = os.path.join(G, "smelt", stem)
    src = eo_words(open(os.path.join(d, f"S4-RETURN-{tag}.md"), encoding="utf-8").read())
    p = os.path.join(d, f"S4-VIEW-{tag}.md")
    head = (f"`[tools/smelt-s4-view.py el S4-RETURN-{tag}.md: la resumoj de la periodoj kursive, la notoj kiel supraj ciferoj kaj "
            f"numerita listo; la tri partoj kaj la enhavo (tools/smelt_parts.py). La raporto de la verkanto estas la registro.]`\n\n")
    dy = smelt_parts.death_year(d, tag)
    src_p, pn = places(tidy(src))   # the place names, before the parts and the ToC are made (headings included)
    out = smelt_parts.structure(src_p, dy)
    # the ISO dates and compactions 1–2, before the works list goes in (its titles as the sources print them)
    nm0 = re.search(r"^# La biografio de (.*?) \(smelt S4", src, re.M)   # not re.match: the joined return opens «# Return: …»
    full = nm0.group(1) if nm0 else ""
    roster = re.sub(r"^#\s+|\s+—.*$", "", open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").readline()).strip()
    sm = re.search(r"(?i)\b" + re.escape(roster) + r"\b", full) if roster else None
    out, cn = compact(out, full, sm.group(0) if sm else full)
    # «SAMNOMULOJ» BY THE SECOND ROUTE (2026-11-09; the editor): smelt-s2-prep.py --samnomuloj's
    # small writer's S4-SAMNOMULOJ-<tag>.md at the end of «Nomoj»; where the biography has no «Nomoj», a «Nomoj» of its own
    # before «Kie troviĝas la fontoj», at that section's level, and in the ToC. Not where the biography has it already
    samp = os.path.join(d, f"S4-SAMNOMULOJ-{tag}.md")
    sam_note = ""
    if os.path.exists(samp):
        sam = eo_words(open(samp, encoding="utf-8").read().strip())
        sam = re.sub(r"\n+Fino:.*$", "", sam).strip()
        if re.search(r"\*\*Samnomuloj\*\*|^#+ Samnomuloj\s*$", out, re.M): sam_note = "; «Samnomuloj» in the biography already, S4-SAMNOMULOJ left out"
        elif not sam.startswith("**Samnomuloj**"): sys.exit(f"refusing: {os.path.relpath(samp, G)} does not begin «**Samnomuloj**»")
        else:
            k = re.search(r"^(#+) (?:La n|N)omoj\s*$", out, re.M)
            if k:
                m = re.compile(r"^#", re.M).search(out, k.end())
                at = m.start() if m else len(out)
                out = out[:at].rstrip() + "\n\n" + sam + "\n\n" + out[at:]
                sam_note = "; «Samnomuloj» at the end of «Nomoj»"
            else:
                f = re.search(r"^(#+) Kie troviĝas la fontoj\s*$", out, re.M) or re.search(r"^## 2\.", out, re.M)
                if not f: sys.exit(f"refusing: {stem}'s view has neither «Nomoj» nor «Kie troviĝas la fontoj» nor part 2 for «Samnomuloj»")
                lv = f.group(1) if f.lastindex else "####"
                out = out[:f.start()] + f"{lv} Nomoj\n\n{sam}\n\n" + out[f.start():]
                out = re.sub(r"^(\s*)- \[Kie troviĝas la fontoj\]\(#kie-troviĝas-la-fontoj\)$",
                             lambda t: f"{t.group(1)}- [Nomoj](#nomoj)\n" + t.group(0), out, count=1, flags=re.M)
                sam_note = "; «Nomoj» made for «Samnomuloj»"
    # «VERKOJ LAŬ LA FONTOJ» after the biography, before the report's parts (tools/smelt_works.py; the editor, 2026-10-30:
    # «Verkoj laŭ la fontoj» approved); fact-labels.py then puts «Referencoj» after it
    import smelt_works
    # the person's name in the works section's line (2026-11-09; the editor: re.match
    # missed the title under «# Return: …», so every view gave the folder's name): the short biography's title, the full
    # name as the abstract gives it («M. M. Abesgus»), where the gist is written; else the head from the biography's title
    gp = os.path.join(d, f"S4-GIST-{tag}.md")
    # (2026-11-10) the gist's title anywhere in its file (a gist of the periods route is filed under «# Return: …»), and
    # before it a row of smelt/TITOLOJ.tsv, the editor's ruling on the name where the sources differ or the gist has no title
    gm = re.search(r"^# La (?:mallonga|skiza) biografio de (.+)$", open(gp, encoding="utf-8").read(), re.M) if os.path.exists(gp) else None
    tp = os.path.join(G, "smelt", "TITOLOJ.tsv")
    tit = next((r[1] for r in (l.split("\t") for l in open(tp, encoding="utf-8").read().split("\n")[1:] if l.strip())
                if r[0] == stem), None) if os.path.exists(tp) else None
    nm = re.search(r"^# La biografio de (.*?) \(smelt S4", src, re.M)
    who = tit or (gm.group(1).strip() if gm else (nm.group(1) if nm else stem))
    prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
    # the works reader's merges, where it has run (smelt_works.py brief / check)
    sure, unsure, bad, splits = smelt_works.merges(d, tag)
    wk = smelt_works.section(prof, who, sure, splits, unsure)
    if wk:
        # after «Kie troviĝas la fontoj», at its level (the editor, 2026-10-30: «Verkoj laŭ la fontoj» after «Kie
        # troviĝas la fontoj»); without that section, before the report's parts
        k = re.search(r"^(#+) Kie troviĝas la fontoj\s*$", out, re.M)
        m = re.compile(r"^#", re.M).search(out, k.end()) if k else re.search(r"^## 2\.", out, re.M)
        if k: wk = [k.group(1) + wk[0][2:]] + wk[1:]
        out = (out[:m.start()].rstrip() + "\n\n" + "\n".join(wk) + "\n" + out[m.start():]) if m else out.rstrip() + "\n\n" + "\n".join(wk)
        # and in the table of contents, after «Kie troviĝas la fontoj» at its indent (smelt_parts.py made the ToC first)
        out = re.sub(r"^(\s*)- \[Kie troviĝas la fontoj\]\(#kie-troviĝas-la-fontoj\)$",
                     lambda t: t.group(0) + f"\n{t.group(1)}- [Verkoj laŭ la fontoj](#verkoj-laŭ-la-fontoj)", out, count=1, flags=re.M)
    # THE TITLE, THE FIRST MENTION AND THE PICTURES (2026-11-10). The title: the fullest name established, the gist's (the
    # editor): the writer's title
    # replaced, or one put before «## 1.» where the return has none; only once the gist is written, so the view is remade
    # after the gist. Where the abstract gives «X (∴ Y)», the biography's first mention of X is given so too (the editor: «G. Blanc (∴ Gaspard Blanc)» kept in the abstract,
    # as correct, and used at the first mention in the
    # biography from now on). The pictures under the title (tools/smelt-portraits.py, smelt/PORTRETOJ.tsv; the editor: a picture under the heading
    # of the biography and the gist where there is one, the bare photograph)
    title_note = ""
    if gm or tit:
        t0 = re.search(r"^# La biografio de (.*?)( \(smelt S4[^)]*\).*)$", out, re.M)
        if t0: out = out[:t0.start()] + f"# La biografio de {who}{t0.group(2)}" + out[t0.end():]
        else:
            s1 = re.search(r"^## 1\. ", out, re.M)
            if s1: out = out[:s1.start()] + f"# La biografio de {who} (smelt S4, {tag})\n\n" + out[s1.start():]
        title_note = f"; titled «{who}»"
    r0 = re.search(r"^### Resumo\s*$", out, re.M)
    a0 = re.compile(r"^\*.*$", re.M).search(out, r0.end()) if r0 else None
    ab = re.match(r"\*([^*(\n]+?) \(∴ ([^)\n]+)\)", a0.group(0)) if a0 else None
    b0 = re.search(r"^### I\. ", out, re.M)
    if ab and b0:
        x = re.compile(re.escape(ab.group(1)) + r"(?! \(∴)").search(out, b0.end())
        if x:
            out = out[:x.end()] + f" (∴ {ab.group(2)})" + out[x.end():]
            title_note += f"; the first mention «{ab.group(1)} (∴ {ab.group(2)})»"
    from importlib import util as ilu   # (main imports importlib.util further down, which makes «importlib» local to it)
    spec = ilu.spec_from_file_location("smelt_portraits", os.path.join(ROOT, "tools", "smelt-portraits.py"))
    sp = ilu.module_from_spec(spec); spec.loader.exec_module(sp)
    pics = sp.heading(stem, d)
    t1 = re.search(r"^# La biografio de .*$", out, re.M)
    if pics and t1:
        out = out[:t1.end()] + "\n\n" + pics + out[t1.end():]
        title_note += f"; {pics.count('<img ')} pictures"
    out = fold(out)
    # THE REPAIR PASS (tools/smelt-repair.py; the editor, 2026-11-11): its readers'
    # replacements, S4-REPAIR-<tag>.tsv (old sentence, new sentence, the candidate, the verdict), applied to the reading copy
    # last, each old sentence found exactly once in part 1 or refused and listed; the return stays as the writers wrote it
    rp = os.path.join(d, f"S4-REPAIR-{tag}.tsv")
    if os.path.exists(rp):
        cut = out.find("\n## 2. "); body, tail = (out[:cut], out[cut:]) if cut > 0 else (out, "")
        done, refused = 0, []
        for l in open(rp, encoding="utf-8").read().split("\n")[1:]:
            f = l.split("\t")
            if len(f) < 2 or not f[0].strip(): continue
            old, new = f[0].replace("\\n", "\n"), f[1].replace("\\n", "\n")
            if body.count(old) == 1: body = body.replace(old, new); done += 1
            else: refused.append((f[2] if len(f) > 2 else "?", body.count(old)))
        out = body + tail
        print(f"  repairs: {done} applied; {len(refused)} refused (not found once): " + ", ".join(f"{c} ({n}×)" for c, n in refused[:20]))
    with open(p, "w" if "--replace" in sys.argv else "x", encoding="utf-8") as fh:
        fh.write(head + out)
    print(f"{os.path.relpath(p, ROOT)}: {len(re.findall(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', out))} note markers; {out.count('[vd. fontoj ')} lists folded; {cn['dates']} dates to ISO, {cn['abbr']} abbreviations, "
          f"{cn['name']} full names shortened; "
          f"{max(0, len(wk) - 5)} works ({len(splits)} splits and {len(sure)} merges by the reader, {len(unsure)} uncertain, {len(bad)} refused); the death {dy or 'not in the profile'}; "
          f"parts: {', '.join(l[4:] for l in out.split(chr(10)) if re.match(r'^### [IV]+\. ', l))}{sam_note}{title_note}" + (f"; {pn} place names set (LOKNOMOJ.tsv)" if pn else ""))
    # the gaps and conjectures, smelt by smelt (2026-10-22, the editor)
    import importlib.util
    spec = importlib.util.spec_from_file_location("smelt_marks", os.path.join(ROOT, "tools", "smelt-marks.py"))
    sm = importlib.util.module_from_spec(spec); spec.loader.exec_module(sm)
    sys.argv = [sys.argv[0], stem]; sm.main()
    # the bibliographic labels and «Referencoj», a fixed step after every view (2026-10-30: the pilot's four reading
    # copies went out with bare L-numbers, the step skipped; the editor: the reading copies still without their
    # references resolved bibliographically; building it in approved): fact-labels.py on the same tag, so the labelled
    # copy can no longer be forgotten; a work with no signed siglum still gets «?» and is listed for the sign-off
    spec = importlib.util.spec_from_file_location("fact_labels", os.path.join(ROOT, "tools", "fact-labels.py"))
    fl = importlib.util.module_from_spec(spec); spec.loader.exec_module(fl)
    sys.argv = [sys.argv[0], stem, tag]; fl.main()

if __name__ == "__main__":
    main()
