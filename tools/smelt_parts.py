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
                m = re.search(r"\*\*[^*]*?\b(1[5-9]\d\d|20\d\d)\b", l)
                if m: c[int(m.group(1))] += 1
    return c.most_common(1)[0][0] if c else None

def part_of(title, dy):
    """0 «La vivo», 1 «Post la morto», 2 «La persono», by the section's title."""
    m = re.search(r"\(([^()]*?)\b(1[5-9]\d\d|20\d\d)\b[^()]*\)\W*$", title)
    if not m: return 2
    if m.group(1).strip().startswith("post") or (dy and int(m.group(2)) > dy): return 1
    return 0

def slug(h):
    """The anchor a markdown viewer gives a heading (GitHub's rule, which VS Code follows): lower case, punctuation out,
    spaces as hyphens."""
    return re.sub(r" ", "-", re.sub(r"[^\w\- ]", "", h.strip().lower()))

def structure(text, dy):
    """Part (1) of a biography («## 1. …» to the next «## ‹digit›») with the parts as «### I. La vivo» …, each numbered
    section under its part as «#### N. …», the end matter (the sources, the conflicts, the minor discrepancies) under
    «### Aldonoj», and «### Enhavo», the table of contents, after the abstract. The rest of the text is unchanged."""
    lines = text.split("\n")
    a = next((i for i, l in enumerate(lines) if l.startswith("## 1.")), None)
    if a is None: return text
    b = next((i for i, l in enumerate(lines) if i > a and re.match(r"^## \d", l)), len(lines))
    body, toc, seen, cur, k = [], [], collections.Counter(), None, 0
    def head(level, title):
        s = slug(title); n = seen[s]; seen[s] += 1
        toc.append(("  " if level == 4 else "") + f"- [{title}](#{s + (f'-{n}' if n else '')})")
        return "#" * level + " " + title
    resumo_end = None
    for i in range(a, b):
        l = lines[i]
        if resumo_end == "pending" and l.startswith("#"):
            resumo_end = len(body)    # the ToC goes before the first heading after the abstract
        m = re.match(r"^### (\d+)\. (.+)$", l)
        if m:
            p = part_of(m.group(2), dy)
            if p != cur:
                cur = p; body += [head(3, f"{ROMAN[k]}. {TITLES[p]}"), ""]; k += 1
            body.append(head(4, f"{m.group(1)}. {m.group(2)}")); continue
        if l.startswith("### ") and l.strip() != "### Resumo":
            if cur != "end":
                cur = "end"; body += [head(3, "Aldonoj"), ""]
            body.append(head(4, l[4:].strip())); continue
        if l.startswith("### Resumo"):
            resumo_end = "pending"
        body.append(l)
    if not toc: return text
    at = resumo_end if isinstance(resumo_end, int) else 1
    body[at:at] = ["### Enhavo", ""] + toc + [""]
    return "\n".join(lines[:a] + body + lines[b:])
