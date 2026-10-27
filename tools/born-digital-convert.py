#!/usr/bin/env python3
"""born-digital-convert — normalise born-digital texts (the Tekstaro first) into fixed plain text for the dowse, and
draft the PROPOSED born-digital list for the editor to sign.

Agreed 2026-10-09 with Miles (plans/relay-ezri-to-miles-born-digital-2026-10-09.md and his reply,
plans/relay-miles-to-ezri-born-digital-2026-10-09.md): born-digital texts reach tools/ocr-dowse.py through a signed list
read beside the OCR ledger, with no OCR gate. This tool writes:

  - one text per item, geniza/sources/born-digital-text/<item>.txt: the HTML stripped, whitespace folded, one paragraph
    per line with a blank line between, and every heading written as a marker line «=== section N: <title> ===» so that
    a scope can read «sections 3–7». ONCE SIGNED, A TEXT MUST NOT CHANGE: unpaged hits carry «¶ N» / «line N» locators
    counted in it. So the tool refuses to overwrite a text that differs from what it would write (it says so); an
    identical text is left as is.
  - the draft list, geniza/ocr/lines/BORN-DIGITAL-LINES-<date>-PROPOSED-<label>.txt (TSV; «#» comment lines): columns item, path,
    pages, scope, label, class. Kind and year of writing are NOT judged here: they come from the item table
    (Miles: «take them from the item table … the editor's signature then confirms them»).

An item stem must not already be an item in geniza/OCR-ITEM-TABLE.tsv (a born-digital text and a scan of the same work
stay two items): the tool refuses a clash.

    tools/born-digital-convert.py <spec.tsv> --label <label> [--date YYYY-MM-DD]

spec.tsv columns: item, source (path; .html read as Tekstaro HTML, else plain text), scope, label, class.

A source may end «#sections=N-M» (or «#sections=N»): the text is then those sections only, with their original section
markers and numbers, and nothing else. This is for added material made a source of its own (Miles 2026-10-10, «added
material (a translator's or compiler's preface, notes, appendix) is a source of its own»): a translator's preface becomes
its own item, so the translation's body is never searched for it.

A source may instead end «#h1=K»: only the K-th <h1> block of the page, for pages that hold several issues of a periodical
(occidental-lang.com's Cosmoglotta, 2026-10-10: one item per issue, each dated by its own heading).

A plain-text source may end «#paras-from=<path of the saved .html>»: the words as given, with a break wherever a
paragraph of that page visibly begins (two or more <br> in a row, a closed block, a heading; never a single <br>). For
our own text extractions of web pages that lost the paragraphs (2026-10-11). It only adds paragraph breaks.

A plain-text source may end «#body» (2026-10-26): a paste file of ours, its words only, our title, note and address
lines left out, so that «¶ 1» is the paste's first paragraph (paste_body()).

A plain-text source may end «#paged» (2026-10-16, Miles, for en.wikisource's validated transcription of Clark 1907,
split by the scan's pages): the file already holds «=== page N ===» markers, one per scan page in rising order, and
keeps them with their numbers; each page gets the plain-text rules within it, as a typed PDF's does, and the list row
says «pdf» in «pages», so its hits are cited «PDF N» like a scan. Refused if the file has no markers, text before the
first, or numbers that do not rise.

--dry-run writes nothing: each row's words, section markers and pages are printed, and whether its fixed text would be
new, the same, or refused.

A source may also be several files joined by « + », converted in that order into one text with its section markers
renumbered (a book split over web pages). Non-UTF-8 files are read as Windows-1252. Plain-text sources lose Project
Gutenberg's header and footer and have each paragraph folded onto one line (2026-10-10).
"""
import os, re, sys, html, csv, argparse, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
OUT = os.path.join(G, "sources", "born-digital-text")

def read_any(path):
    """UTF-8 if the file is valid UTF-8 (every Tekstaro file is), else Windows-1252: older hand-made pages such as the
    1923 Dyer book's (2026-10-10), whose bytes would otherwise come out as «�»."""
    return read_any_bytes(open(path, "rb").read())

def plain_text(path, s=None):
    """A plain-text source: Project Gutenberg's header and footer dropped (they are modern metadata), and each paragraph
    (a block between blank lines) folded onto one line, the same shape as the HTML texts."""
    s = (read_any(path) if s is None else s).replace("\r\n", "\n").lstrip("﻿")   # s: already-read text (a PDF's)
    m = re.search(r"\*\*\* ?START OF (?:THIS|THE) PROJECT GUTENBERG[^\n]*\n(.*?)\n\*\*\* ?END OF (?:THIS|THE) PROJECT GUTENBERG", s, re.S)
    if m: s = m.group(1)
    # «[IMG <file>]»: the image markers our own September harvester wrote into the Pioniroj posts' post.txt (2026-10-11),
    # not the blog's text
    s = re.sub(r"\[IMG [^\]\n]*\]", "", s)
    paras = [p for p in (re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", s)) if p]
    if m and paras and paras[0].startswith("Produced by"): paras = paras[1:]     # the Gutenberg producers' credit
    if m and paras and paras[-1].startswith("End of the Project Gutenberg"): paras = paras[:-1]   # and its closing line
    return "\n\n".join(p for p in paras if p) + "\n"

def renumber(text):
    """Section markers numbered 1, 2, 3 … through a text joined from several files."""
    n = 0
    def f(m):
        nonlocal n
        n += 1
        return f"=== section {n}: "
    return re.sub(r"(?m)^=== section \d+: ", f, text)

def paras_from(text, html_path):
    """«#paras-from=<html>» (2026-10-11; the editor): for our own September text extractions of web pages, which lost the page's paragraphs (Jossinet
    1998, the Vaha blog, Kolar 2021, Kiss 2009, Holmi 2008). The text's words unchanged, with a paragraph break inserted
    before each place where a paragraph of the saved HTML page begins, the page's paragraphs being its visual breaks:
    two or more <br> in a row, a closed block (</p>, </div> …) or a heading; a single <br> is not a break (br2 mode of
    tekstaro_text). A paragraph's first six words are matched exactly and in order; one of fewer than three words is
    skipped. Nothing is added or removed but the breaks."""
    W = text.split()
    starts, pos = [], 0
    for p in (q.split() for q in tekstaro_text(html_path, br2=True).split("\n\n") if q.strip()):
        k = p[:6]
        if len(k) < 3 or k[0].startswith("==="): continue
        for i in range(pos, len(W) - len(k) + 1):
            if W[i:i + len(k)] == k:
                if i > 0: starts.append(i)
                pos = i + 1
                break
    cuts = [0] + starts + [len(W)]
    return "\n\n".join(" ".join(W[a:b]) for a, b in zip(cuts, cuts[1:]) if b > a) + "\n"

# InDesign's invisible and spacing characters, garbled in some PDFs' character maps (UTF-8 read as a Windows code page).
# Found in Gordin, Scientific Babel (2015), 2026-10-12: «Wilhelm-Â�Ostwald», so a name search missed every hyphenated
# name printed where a line could break. The editor 15:3x (approved): for every typed PDF, since the sequences are
# unambiguous and harmless where absent (none in the 1,687 born-digital texts of that day). Each replacement is counted
# and reported, so a new garble shows up as a number. Read from Gordin's page images: the «*» beside «â•›» is printed
# (his footnote mark), only the garbled thin space goes.
GARBLE = [
    (re.compile("Â�\\s?"), ""),     # a discretionary line break, after a hyphen or dash or inside a word
    (re.compile("â•‚\\s?"), ""),          # the same, in another font
    (re.compile("â†œ"), ""),              # a thin or hair space after a closing quotation mark
    (re.compile("â•›"), ""),              # a thin space before an opening quotation mark or a note mark
    (re.compile("â•‡|â•…"), " "),          # a tab (contents leaders) and an en space
]

def clean_garble(s, path):
    counts = {}
    for rx, rep in GARBLE:
        s, n = rx.subn(rep, s)
        if n: counts[rx.pattern] = n
    if counts:
        print(f"{os.path.basename(path)}: garbled characters cleaned {counts}; left: {s.count(chr(0xFFFD))} U+FFFD", file=sys.stderr)
    return s

def pdf_text(path):
    """A typed PDF (a text layer made by the publisher or author, not by OCR; Aray 2019, Matsui 2024, 2026-10-10): PAGED.
    The editor 21:56 (): a typed PDF is searched and cited like a scan, «<item>, PDF N». So each PDF page
    is written as «=== page N ===» (the OCR texts' marker; Miles 22:03: ruled by the editor), its text
    in pdftotext's reading order with the plain-text rules applied within the page. The list row says «pdf» in «pages»."""
    import subprocess
    raw = subprocess.run(["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, check=True, text=True).stdout
    pages = clean_garble(raw, path).split("\f")
    if pages and not pages[-1].strip(): pages = pages[:-1]          # pdftotext ends with a form feed
    return "".join(f"=== page {n} ===\n{plain_text(path, p).strip()}\n" for n, p in enumerate(pages, 1))

def paged_text(path):
    """«#paged»: a plain text already split by its scan's pages («=== page N ===», the OCR texts' marker), the markers
    and their numbers kept, the plain-text rules applied within each page (as pdf_text does)."""
    s = read_any(path).replace("\r\n", "\n").lstrip("﻿")
    parts = re.split(r"^=== page (\d+) ===[ \t]*$", s, flags=re.M)
    if len(parts) < 3: sys.exit(f"refusing: «#paged» but no «=== page N ===» markers in {path}")
    if parts[0].strip(): sys.exit(f"refusing: «#paged» but text before the first page marker in {path}")
    nums = [int(x) for x in parts[1::2]]
    bad = [(a, b) for a, b in zip(nums, nums[1:]) if b <= a]
    if bad: sys.exit(f"refusing: «#paged» page numbers that do not rise in {path}: {bad[:5]}")
    return "".join(f"=== page {n} ===\n{plain_text(path, p).strip()}\n" for n, p in zip(nums, parts[2::2]))

def epub_text(path):
    """An e-book: its parts in the order of the book's spine, read as one HTML page, so that section markers run on
    through the book. Project Gutenberg's header and licence (div «pgheader») are dropped (The Esperantist 1903–05,
    2026-10-10)."""
    import zipfile, posixpath
    z = zipfile.ZipFile(path)
    opf = re.search(r'full-path="([^"]+)"', z.read("META-INF/container.xml").decode("utf-8")).group(1)
    o = z.read(opf).decode("utf-8")
    href = {}
    for t in re.findall(r"<item\s[^>]*>", o):
        i, h = re.search(r'\bid="([^"]+)"', t), re.search(r'\bhref="([^"]+)"', t)
        if i and h: href[i.group(1)] = h.group(1)
    body = []
    for idref in re.findall(r'<itemref[^>]*idref="([^"]+)"', o):
        h = read_any_bytes(z.read(posixpath.join(posixpath.dirname(opf), html.unescape(href[idref]))))
        h = drop_divs(h, r"pgheader|tnotes")   # and the transcriber's notes
        m = re.search(r"(?is)<body[^>]*>(.*)</body>", h)
        body.append(m.group(1) if m else h)
    return tekstaro_text(path, s="\n".join(body))

def drop_divs(h, classes):
    """Every <div> whose class names one of «classes» (a regex), dropped whole with the <div>s nested in it: Gutenberg's
    newer packaging nests its header and licence blocks (vol. 1 nos. 2 and 3 of The Esperantist, fetched 2026-10-10)."""
    opener = re.compile(r'(?is)<div[^>]*class="[^"]*\b(?:' + classes + r')\b[^"]*"[^>]*>')
    tag = re.compile(r"(?is)<(/?)div\b[^>]*>")
    while True:
        m = opener.search(h)
        if not m: return h
        depth, pos = 1, m.end()
        while depth:
            t = tag.search(h, pos)
            if not t: return h[:m.start()]        # unclosed: drop to the end
            depth += -1 if t.group(1) else 1
            pos = t.end()
        h = h[:m.start()] + h[pos:]

def div_whole(h, cls):
    """The first <div> whose class is exactly «cls» (or begins with it), whole, with the <div>s nested in it; '' if none."""
    m = re.search(r'(?is)<div[^>]*class="' + cls + r'(?:\s[^"]*)?"[^>]*>', h)
    if not m: return ""
    tag, depth, pos = re.compile(r"(?is)<(/?)div\b[^>]*>"), 1, m.end()
    while depth:
        t = tag.search(h, pos)
        if not t: return h[m.start():]
        depth += -1 if t.group(1) else 1
        pos = t.end()
    return h[m.start():pos]

def read_any_bytes(b):
    """UTF-8 if valid; else the charset the page declares (historio.ru's pages are Windows-1251, 2026-10-10: read as
    Windows-1252 their Cyrillic would be garbled), with ISO-8859-1 read as Windows-1252, as browsers do; else
    Windows-1252."""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        import codecs
        m = re.search(rb"""(?i)(?:charset|encoding)\s*=\s*["']?([a-z0-9_-]+)""", b[:4096])
        cs = m.group(1).decode("ascii").lower() if m else "cp1252"
        if cs in ("iso-8859-1", "latin-1", "latin1", "us-ascii", "ascii"): cs = "cp1252"
        try: codecs.lookup(cs)
        except LookupError: cs = "cp1252"
        return b.decode(cs, errors="replace")

def wikitext_text(path):
    """The Wikisource *Adresaro* (2026-10-11, the editor's to listing it): each {{Adresaro|<entry>|n=<N>|…}}
    becomes one paragraph «N. <entry>» (the entry number is the locator readers know), the wiki emphasis marks «*»
    dropped; the series' header ({{AdresaroPri|jaro=…}}) becomes the section marker; other templates are dropped."""
    s = read_any(path)
    if "{{Adresaro|" not in s: return wiki_text(s)
    out = []
    m = re.search(r"\{\{AdresaroPri\|([^}]*)\}\}", s)
    if m:
        f = dict(x.split("=", 1) for x in m.group(1).split("|") if "=" in x)
        serio = os.path.basename(path).rsplit(".", 1)[0].replace("_", " ")
        # the series' year: «jaro» if given, else the year it runs from («ekde»), else the year of its end date («ĝis»)
        yr = f.get("jaro") or (f.get("ekde") or "")[:4] or (f.get("ĝis") or "")[:4]
        out.append(f"=== section 1: Adresaro, {serio}" + (f" ({yr})" if yr else "") + " ===")
    for e in re.findall(r"\{\{Adresaro\|([^}]*)\}\}", s):
        x = e.split("|")
        n = next((y[2:] for y in x[1:] if y.startswith("n=")), "")
        t = re.sub(r"\s+", " ", x[0].replace("*", "")).strip()
        out.append(f"{n}. {t}" if n else t)
    return "\n\n".join(out) + "\n"

def wiki_text(s):
    """A Wikipedia article in wiki markup (the eo/io corpus, sources/wikipedia-eo-io/, 2026-10-11; the editor). Kept: link texts, image captions, template values (dates,
    infobox data) and the footnotes, which are what may point to sources we lack. Dropped: categories, comments, table
    syntax, emphasis marks. Headings become section markers."""
    s = re.sub(r"(?s)<!--.*?-->", "", s)
    s = re.sub(r"(?is)<ref[^>/]*/>", "", s)
    s = re.sub(r"(?is)<ref[^>]*>(.*?)</ref>", r" [ref: \1]", s)
    def tpl(m):
        parts = m.group(1).split("|")[1:]
        named = [f"{p.split('=', 1)[0].strip()}: {p.split('=', 1)[1].strip()}" for p in parts
                 if re.match(r"\s*[\w -]+=", p) and p.split("=", 1)[1].strip()]
        plain = [p.strip() for p in parts if not re.match(r"\s*[\w -]+=", p) and p.strip()]
        return " " + "; ".join(x for x in [" ".join(plain)] + named if x) + " "     # «26 marto 1863»; «born: 1863»
    for _ in range(10):                                   # innermost templates first, nested ones on later passes
        s2 = re.sub(r"\{\{([^{}]*)\}\}", tpl, s)
        if s2 == s: break
        s = s2
    s = re.sub(r"\[\[(?:Kategorio|Category|Kategorie|Catégorie|Categoria|Категория|Категория|Kategorio):[^\]]*\]\]", "", s)
    s = re.sub(r"\[\[(?:Dosiero|File|Image|Datei|Fichier|Imagen|Fitxer|Файл|Bild|Arkivo):(?:[^\[\]]|\[\[[^\]]*\]\])*\]\]",
               lambda m: re.split(r"\|", m.group(0)[2:-2])[-1], s)
    for _ in range(3):
        s = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", s)
        s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[(https?://\S+) ([^\]]+)\]", r"\2", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"(?m)^\s*(\{\||\|\}|\|-|\|\+).*$", "", s)
    s = re.sub(r"(?m)^\s*[!|]\s*", "", s)
    out, n = [], 0
    for p in re.split(r"\n\s*\n", s):
        lines = []
        for l in p.splitlines():
            mh = re.fullmatch(r"\s*(={2,6})\s*(.*?)\s*\1\s*", l)
            if mh:
                if lines: out.append(re.sub(r"\s+", " ", " ".join(lines)).strip()); lines = []
                n += 1; out.append(f"=== section {n}: {mh.group(2)} ===")
            else:
                lines.append(l)
        t = re.sub(r"\s+", " ", " ".join(lines)).strip()
        if t: out.append(t)
    return "\n\n".join(x for x in out if x) + "\n"

def paste_body(path):
    """«#body» (2026-10-26, Ezri: in the Beauchemin snippets text «the visible «¶ N —» labels don't match the paragraph
    count the harvest uses, because the header and notes count as paragraphs»; the editor): a paste file of ours
    (the editor's BAnQ, FamilySearch and genealogy pastes) opens with our title «# …», our note «`[…]`» and, in the BAnQ
    pastes, the «- **URL:**» / «- **Item:**» lines and a rule «---». The item's text is the pasted words only: after the
    first «---» in the file's first ten lines, else after the opening title and note lines. The provenance stays in the
    paste file, the spec row and `_WEB-DOWNLOADS.tsv`."""
    lines = read_any(path).replace("\r\n", "\n").split("\n")
    rule = next((i for i, l in enumerate(lines[:10]) if l.strip() == "---"), None)
    if rule is not None:
        return "\n".join(lines[rule + 1:])
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].startswith("# ") or lines[i].lstrip().startswith("`[")):
        i += 1
    return "\n".join(lines[i:])

def any_text(path, h1=None):
    """The reader for a source, by its file ending."""
    if path.endswith(".wikitext"): return wikitext_text(path)
    if path.endswith((".html", ".htm")): return tekstaro_text(path, h1)
    if path.endswith(".epub"): return epub_text(path)
    if path.endswith(".pdf"): return pdf_text(path)
    return plain_text(path)

def tekstaro_text(path, h1=None, s=None, post=False, br2=False):
    """Tekstaro HTML (the «tekstarteksto» div), or any HTML whose text sits in <main> (occidental-lang.com's
    Cosmoglotta pages, 2026-10-10), or else the whole page. h1=K keeps only the K-th <h1> block (1-based): one issue
    of a page that holds several. s: HTML already read (an e-book's parts)."""
    s = read_any(path) if s is None else s
    raw = s
    m = re.search(r'<div class="tekstarteksto"[^>]*>(.*)', s, re.S) or re.search(r"<main[^>]*>(.*?)</main>", s, re.S) \
        or re.search(r'(?s)id="historio_content"[^>]*>(.*?)(?:<div id="content_bottom"|<div id="historio_footer")', s)
    # historio.ru (N. Stepanov's «Esperanto en Rusio», 2026-10-10): the page's own text sits in div#historio_content,
    # before its bottom block and footer; the menus and title bar around it are the site's, not the page's.
    if post and 'class="entry-content"' in s:
        # «#post» (2026-10-11, Korĵenkov's «Sezonoj» posts on La Ondo de Esperanto's WordPress site): the post's title,
        # its date line and its body; not the menus, previous/next links, sidebar, tag line, reader comments, footer, or
        # the view counter inside the body, nor WordPress.com's share and related-posts blocks (Butler). Opt-in by a fragment, because two Sezonoj posts were signed whole on
        # 2026-10-10 (the web-saves list) and a signed text must not change.
        parts = [mm.group(0) for mm in [re.search(r'(?is)<h1[^>]*class="entry-title"[^>]*>.*?</h1>', s)] if mm]
        parts += [div_whole(s, "entry-meta"), div_whole(s, "entry-content")]
        return tekstaro_text(path, h1, s="<main>" + drop_divs("".join(p for p in parts if p), r"post-views|sharedaddy|jp-relatedposts") + "</main>")
    s = m.group(1) if m else re.sub(r"(?is)<head[\s>].*?</head>", "", s)     # whole page: never its <title>
    # The Biblioteko Hippolyte Sebert (Unuiĝo Franca por Esperanto, arkivo.esperanto-france.org; 2026-10-10): its pages
    # carry navigation (classes ufe, lig, lig2, lgl, ci0) and the library's own modern presentations (div «prezento»,
    # p «prezent», p «rim»). Both are dropped: modern, not the reissued document.
    if 'class="ufe"' in s:
        s = re.sub(r'(?is)<p[^>]*class="(?:ufe|lig|lig2|lgl|ci0|prezent|rim)"[^>]*>.*?</p>', "", s)
        s = re.sub(r'(?is)<div[^>]*class="prezento"[^>]*>.*?</div>', "", s)
    # An <h1> whose text starts with «=» is a stray: a line of an article («==== bruli, bruligi …») that the source site's
    # Markdown turned into a setext heading (Cosmoglotta theRest.html, seven of them). Kept as an ordinary paragraph.
    s = re.sub(r"(?is)<h1[^>]*>(\s*=.*?)</h1>", r"<p>\1</p>", s)
    if h1 is not None:
        blocks = re.split(r"(?i)(?=<h1[\s>])", s)[1:]
        if not 1 <= h1 <= len(blocks):
            sys.exit(f"refusing: {path} has {len(blocks)} <h1> blocks, not {h1}")
        s = blocks[h1 - 1]
    s = re.sub(r"(?s)<(script|style).*?</\1>", "", s)
    if br2:
        # visual breaks only (2026-10-11): the source's own line breaks show nothing on the page, so they are folded first;
        # then two or more <br> in a row (spaces and &nbsp; between allowed) are a paragraph break, and a single <br> a space
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"(?i)<br[^>]*>(?:(?:\s|&nbsp;|&#160;)*<br[^>]*>)+", "\n\n", s)
        s = re.sub(r"(?i)<br[^>]*>", " ", s)
    n = 0
    def head(mm):
        nonlocal n
        n += 1
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", mm.group(2)))).strip()
        return f"\n\n=== section {n}: {t} ===\n\n"
    s = re.sub(r"(?is)<(h[1-6])[^>]*>(.*?)</\1>", head, s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|blockquote)>", "\n\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    paras = [re.sub(r"[ \t ]+", " ", p).strip() for p in re.split(r"\n\s*\n", s)]
    lines = []
    ufe = 'class="ufe"' in raw
    for p in paras:
        p = re.sub(r"\s*\n\s*", " ", p)
        # Biblioteko Hippolyte Sebert leftovers: bare arrow links («→ post», «← antaŭ»), «Plilarĝigi» (enlarge the
        # picture) and the site's address line.
        if ufe and re.fullmatch(r"[←→\s]*(?:antaŭ|post)?[←→\s]*|Plilarĝigi|arkivo\.esperanto-france\.org", p): continue
        # historio.ru's tagline, at the foot of 43 of the 45 pages taken (2026-10-10): the site's, not the page's
        if p.startswith("Historio.ru — история отечественного движения эсперантистов"): continue
        # esperanto-ondo.ru's own lines at the head and foot of its pages (the Postnikov biographies, 2026-10-10)
        if p in ("Ĉi tiu dokumento uzas la signaron UTF-8.", "Al la indekso pri la historio"): continue
        # the narod.ru host's footer on the Russian Cosmoglotta pages (2026-10-11)
        if p == "Сайт управляется системой uCoz": continue
        if p: lines.append(p)
    return "\n\n".join(lines) + "\n"

def row_text(r):
    """The fixed text for one spec row (also used to check that earlier texts still come out byte-identical)."""
    if " + " in r["source"]:          # several files joined in the order given (a book split over web pages)
        parts = [p if os.path.isabs(p) else os.path.join(ROOT, p) for p in r["source"].split(" + ")]
        text = renumber("".join(any_text(p) for p in parts))
        src, frag = parts[0], ""
    else:
        src, _, frag = r["source"].partition("#")
        src = src if os.path.isabs(src) else os.path.join(ROOT, src)
        mh = re.fullmatch(r"h1=(\d+)", frag)
        if mh: frag = ""
        if frag == "post":                 # a WordPress post only (Sezonoj, 2026-10-11)
            frag, text = "", tekstaro_text(src, post=True)
        elif frag == "paged":              # a plain text split by its scan's pages (Clark 1907, 2026-10-16)
            frag, text = "", paged_text(src)
        elif frag == "body":               # a paste's words only, without our header (2026-10-26, below)
            frag, text = "", plain_text(src, s=paste_body(src))
        elif frag.startswith("paras-from="):   # breaks taken from the saved HTML page's visual breaks (2026-10-11)
            h = frag[len("paras-from="):]
            frag, text = "", paras_from(plain_text(src), h if os.path.isabs(h) else os.path.join(ROOT, h))
        elif frag.startswith("div="):      # only the blocks of this class, in order (DBNL, Wikipedia HTML; 2026-10-11)
            cls, frag = frag[4:], ""
            raw, blocks, pos = read_any(src), [], 0
            while True:
                b = div_whole(raw[pos:], re.escape(cls))
                if not b: break
                blocks.append(b); pos += raw[pos:].index(b) + len(b)
            if not blocks: sys.exit(f"refusing: no <div class=\"{cls}\"> in {src}")
            text = tekstaro_text(src, s="<main>" + "".join(blocks) + "</main>")
        else:
            text = any_text(src, int(mh.group(1)) if mh else None)
    if frag:
        mf = re.fullmatch(r"sections=(\d+)(?:-(\d+))?", frag)
        if not mf: sys.exit(f"refusing: bad fragment «#{frag}» for {r['item']} (want #sections=N or #sections=N-M)")
        lo, hi = int(mf.group(1)), int(mf.group(2) or mf.group(1))
        keep, cur = [], None
        for p in text.split("\n\n"):
            ms = re.match(r"=== section (\d+): ", p)
            if ms: cur = int(ms.group(1))
            if cur is not None and lo <= cur <= hi: keep.append(p.strip("\n"))
        if not keep: sys.exit(f"refusing: no sections {lo}–{hi} in {src}")
        text = "\n\n".join(keep) + "\n"
    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--label", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true", help="write nothing; print each row's counts and what would happen")
    a = ap.parse_args()
    items_table = set()
    tp = os.path.join(G, "OCR-ITEM-TABLE.tsv")
    with open(tp, encoding="utf-8") as f:
        for r in csv.DictReader((l for l in f if not l.startswith("#")), delimiter="\t"):
            # A born-digital row (parsed_by «BD», made by Miles's item-table input from these very lists) is not a
            # clash: only a scanned item of the same name is (2026-10-10, found when a proposal was regenerated).
            if r.get("parsed_by") != "BD": items_table.add(r["item"])
    rows = list(csv.DictReader(open(a.spec, encoding="utf-8"), delimiter="\t"))
    clash = [r["item"] for r in rows if r["item"] in items_table]
    if clash: sys.exit("refusing: these items already exist in OCR-ITEM-TABLE.tsv: " + ", ".join(clash))
    # The lists live in geniza/ocr/lines/ (Miles, 2026-10-10, on the editor's ask: list files out of the Geniza's top level).
    os.makedirs(os.path.join(G, "ocr", "lines"), exist_ok=True)
    lst = os.path.join(G, "ocr", "lines", f"BORN-DIGITAL-LINES-{a.date}-PROPOSED-{a.label}.txt")
    if a.dry_run:
        for r in rows:
            text = row_text(r)
            dest = os.path.join(OUT, r["item"] + ".txt")
            state = ("same as the fixed text" if open(dest, encoding="utf-8").read() == text else "REFUSED: differs from the fixed text") if os.path.exists(dest) else "new"
            secs = text.count("\n=== section ") + (1 if text.startswith("=== section ") else 0)
            pages = len(re.findall(r"^=== page \d+ ===$", text, re.M))
            print(f'{r["item"]}: {len(text.split()):,} words, {secs} section markers, {pages} pages; {state}')
        print("dry run: nothing written"); return
    if os.path.exists(lst) or os.path.exists(os.path.join(G, os.path.basename(lst))): sys.exit("refusing to overwrite " + lst)
    os.makedirs(OUT, exist_ok=True)
    out_rows, refused = [], []
    for r in rows:
        text = row_text(r)
        dest = os.path.join(OUT, r["item"] + ".txt")
        if os.path.exists(dest):
            if open(dest, encoding="utf-8").read() != text:
                refused.append(r["item"]); continue
        else:
            open(dest, "w", encoding="utf-8").write(text)
        secs = text.count("\n=== section ") + (1 if text.startswith("=== section ") else 0)
        # a typed PDF, or a plain text «#paged»: paged, cited «PDF N» (Miles 22:03; 2026-10-16)
        paged = r["source"].partition("#")[0].endswith(".pdf") or r["source"].endswith("#paged")
        out_rows.append([r["item"], os.path.relpath(dest, G), "pdf" if paged else "none", r["scope"], r["label"], r["class"]])
        print(f'{r["item"]}: {len(text.split()):,} words, {secs} section markers')
    with open(lst, "w", encoding="utf-8", newline="") as f:
        f.write(f"# PROPOSED born-digital lines, «{a.label}», drafted {a.date} by tools/born-digital-convert.py from {os.path.relpath(a.spec, ROOT)}.\n"
                "# Not signed. Kind and year of writing come from OCR-ITEM-TABLE.tsv once Miles's item-table input reads this list.\n"
                "# pages «none»: the texts are unpaged; hits will carry a locator (¶ N / line N) counted in the fixed text.\n"
                "# pages «pdf»: a typed PDF, or a plain text split by its scan's pages («#paged»), written page by page («=== page N ===»); searched and cited like a scan, «PDF N».\n")
        w = csv.writer(f, delimiter="\t"); w.writerow(["item", "path", "pages", "scope", "label", "class"]); w.writerows(out_rows)
    print("wrote", os.path.relpath(lst, ROOT), "·", len(out_rows), "items", ("· REFUSED (text differs from the fixed one): " + ", ".join(refused)) if refused else "")

if __name__ == "__main__":
    main()
