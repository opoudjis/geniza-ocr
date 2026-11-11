"""smelt_parts — a biography's sections in three parts, and the table of contents (2026-10-22; the editor):

- «La vivo»: the sections of the life, a period's title ending in its years «(1866–1870)», up to and with the death;
- «Post la morto»: a period after the death (its first year later than the death, or «(post 1935)»);
- «La persono»: the thematic sections, whose title carries no years (names, origin, portrait, relations).

The death year is the commonest year of the frozen profile's «{morto}» lines, a refuted claim aside; with none, every
period is «La vivo». Used by tools/smelt-s4-view.py (the parts and the ToC in the reading copy, and so in the labelled
copy) and tools/smelt-periods.py --s4-gist. Ezri, 2026-10-22."""
import collections, glob, os, re

TITLES = ("La vivo", "Post la morto", "La persono")
ROMAN = ("I", "II", "III", "IV")

def death_year(d, tag):
    c = collections.Counter()
    for f in sorted(glob.glob(os.path.join(d, f"PROFILE-FROZEN-{tag}*.md"))):
        for l in open(f, encoding="utf-8"):
            if "{morto" in l and "(refutita aserto)" not in l:
                # a window «inter 1909 kaj 1910-08» counts by its end, the death known to lie before it (2026-11-09,
                # Gustafsson: the window's 1909 tied with Zakrzewski's slip 1909-06-13 against the two 1910-06-13)
                b = re.search(r"\*\*([^*]+)\*\*", l)
                ys = re.findall(r"\b(1[5-9]\d\d|20\d\d)\b", b.group(1)) if b else []
                if ys: c[int(ys[-1] if b.group(1).strip().startswith("inter ") else ys[0])] += 1
    return c.most_common(1)[0][0] if c else None

def the_death(title):
    """A section that tells the death itself («La morto kaj la memoro», «La lastaj atestoj kaj la morto») is of «La vivo»
    whatever its year (2026-11-09, Gustafsson: «1910: La morto kaj la memoro» against the profile's commonest death year
    1909, filed under «Post la morto»)."""
    return bool(re.search(r"\bmorto\b", title, re.I)) and not re.search(r"\bpost\b", title, re.I)

def part_any(title, dy):
    """part_of, or, where the title's year is not in brackets at its end («1873–1902: Deveno …», one writer's form), the
    first year of the title against the death (2026-11-09; the gists of five biographies all filed under «La persono»)."""
    if the_death(title): return 0
    y = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", title)
    if re.search(r"\(([^()]*?)\b(1[5-9]\d\d|20\d\d)\b[^()]*\)\W*$", title) or not y: return part_of(title, dy)
    # «post» counts as after the death only from the death's year (2026-11-10, Krumpholc: «Post 1914: Přerov kaj Holešov»,
    # his last years before his death in 1950, went under «Post la morto»; the editor: his
    # underattested activity put by mistake after his death)
    yy = int(y.group(1))
    return 1 if (dy and (yy > dy or (title.lower().startswith("post") and yy >= dy))) else 0

def part_of(title, dy):
    """0 «La vivo», 1 «Post la morto», 2 «La persono», by the section's title."""
    m = re.search(r"\(([^()]*?)\b(1[5-9]\d\d|20\d\d)\b[^()]*\)\W*$", title)
    if not m: return 2
    if the_death(title): return 0
    yy = int(m.group(2))   # «(post 1935)» after the death only from the death's year (2026-11-10, as part_any)
    if dy and (yy > dy or (m.group(1).strip().startswith("post") and yy >= dy)): return 1
    return 0

def slug(h):
    """The anchor a markdown viewer gives a heading (GitHub's rule, which VS Code follows): lower case, punctuation out,
    spaces as hyphens."""
    return re.sub(r" ", "-", re.sub(r"[^\w\- ]", "", h.strip().lower()))

END = ("Kie troviĝas la fontoj", "Verkoj laŭ la fontoj", "La malfermitaj konfliktoj", "Notoj pri malgravaj malkongruoj", "Nomoj",
       "La nomoj", "Aldonoj")   # the end matter of part (1), under «Aldonoj», never numbered (2026-11-09)

def is_end(title):
    """End matter, «La» or not, any case (2026-11-09, Barthel: the writer numbered «5. Malfermitaj konfliktoj», which went
    under «La persono» with a second «Aldonoj»)."""
    t = re.sub(r"^la\s+", "", title.strip().lower())
    return any(t.startswith(re.sub(r"^la\s+", "", e.lower())) for e in END)

def structure(text, dy):
    """Part (1) of a biography («## 1. …» to the next «## ‹digit›») with the parts as «### I. La vivo» …, each numbered
    section under its part as «#### N. …», the end matter (the sources, the conflicts, the minor discrepancies) under
    «### Aldonoj», and «### Enhavo», the table of contents, after the abstract. The rest of the text is unchanged."""
    lines = text.split("\n")
    a = next((i for i, l in enumerate(lines) if l.startswith("## 1.")), None)
    if a is None: return text
    b = next((i for i, l in enumerate(lines) if i > a and re.match(r"^## \d", l)), len(lines))
    # ONE WRITER'S BIOGRAPHY (2026-11-09; the first smelt's twelve views): (1) an abstract with no «### Resumo» heading, the
    # italic paragraph before the first heading, is given one, so the ToC goes after it, not above it; (2) sections the
    # writer did not number («### Deveno …») are numbered in order and put in their parts as numbered ones are, the end
    # matter (END) apart; an undated section takes the part of the one before it, or «La persono» after the last dated one
    # (the marks' legend line may stand before the abstract: the heading goes before both)
    first = next((i for i in range(a + 1, b) if lines[i].strip()), None)
    h1 = next((i for i in range(a + 1, b) if lines[i].startswith("#")), b)
    if first is not None and any(re.match(r"^\*[^*]", lines[i]) for i in range(first, h1)) \
            and not any(l.strip() == "### Resumo" for l in lines[a:b]):
        lines[first:first] = ["### Resumo", ""]; b += 2
    # (3) a wrapper «### La biografio» over «#### …» periods (2026-11-09, Holub: every period filed under «La persono»): the
    # wrapper dropped, its «#### » sections up to the next «### » made «### », the marks' legend line kept where it stood
    for w in [i for i in range(a, b) if re.match(r"^### (?:La )?biografio\s*$", lines[i], re.I)]:
        nx = next((j for j in range(w + 1, b) if lines[j].startswith("### ")), b)
        if any(lines[j].startswith("#### ") for j in range(w + 1, nx)):
            for j in range(w + 1, nx):
                if lines[j].startswith("#### "): lines[j] = lines[j][1:]
            lines[w] = ""
    over = {}    # line index → its part, for the sections numbered here
    if not any(re.match(r"^### \d+\. ", l) for l in lines[a:b]):
        heads = [i for i in range(a, b) if lines[i].startswith("### ") and lines[i].strip() != "### Resumo"
                 and not is_end(lines[i][4:])]
        dated = [i for i in heads if re.search(r"\b(1[5-9]\d\d|20\d\d)\b", lines[i])]
        prev = None
        for n, i in enumerate(heads, 1):
            t = lines[i][4:].strip()
            if i in dated: prev = over[i] = part_any(t, dy)
            elif dated and i < dated[-1]: over[i] = prev if prev is not None else 0
            else: over[i] = 2
            lines[i] = f"### {n}. {t}"
    # THE END MATTER GATHERED AFTER THE LAST NUMBERED SECTION (2026-11-10, Beauchemin's periods route: the thematic writer put
    # «13. Nomoj» between «12. Deveno» and «14. Profesio», and «Aldonoj» opened there, splitting «La persono» into II and
    # III): the end-matter sections and their text kept apart and put, under one «Aldonoj», after all the numbered ones
    body, endb, toc, endtoc, seen, cur, k = [], [], [], [], collections.Counter(), None, 0
    def head(level, title, into=None):
        s = slug(title); n = seen[s]; seen[s] += 1
        (toc if into is None else into).append(("  " if level == 4 else "") + f"- [{title}](#{s + (f'-{n}' if n else '')})")
        return "#" * level + " " + title
    resumo_end, in_end = None, False
    for i in range(a, b):
        l = lines[i]
        if resumo_end == "pending" and l.startswith("#"):
            resumo_end = len(body)    # the ToC goes before the first heading after the abstract
        m = re.match(r"^### (\d+)\. (.+)$", l)
        if m and is_end(m.group(2)):    # a numbered end-matter section goes with the end matter, its number dropped
            l = "### " + m.group(2); m = None
        if m:
            in_end = False
            p = over.get(i, part_of(m.group(2), dy))
            # the parts one way only (2026-11-10, Bourlet: a span from the death year between two «Post la morto» sections)
            if cur is not None and p < cur: p = cur
            if p != cur:
                cur = p; body += [head(3, f"{ROMAN[k]}. {TITLES[p]}"), ""]; k += 1
            body.append(head(4, f"{m.group(1)}. {m.group(2)}")); continue
        if l.startswith("### ") and l.strip() != "### Resumo":
            in_end = True
            endb.append(head(4, l[4:].strip(), endtoc)); continue
        if l.startswith("### Resumo"):
            resumo_end = "pending"
        (endb if in_end else body).append(l)
    if endb:
        if body and body[-1].strip(): body.append("")
        body += [head(3, "Aldonoj"), ""] + endb
        toc += endtoc
    if not toc: return text
    at = resumo_end if isinstance(resumo_end, int) else 1
    body[at:at] = ["### Enhavo", ""] + toc + [""]
    return "\n".join(lines[:a] + body + lines[b:])
