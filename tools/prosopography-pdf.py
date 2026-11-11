#!/usr/bin/env python3
"""The prosopography's reading copies as PDF (ocr/method/PROSOPOGRAPHY-PUBLISHING-RUNBOOK-2026-11-10.md, step 5).

    prosopography-pdf.py gists TAG --version V [--out FILE.pdf] [--compiler NAME] [--replace] [--skip STEM ...]
    prosopography-pdf.py bio TAG (STEM ... | --all) --version V [--outdir DIR] [--compiler NAME] [--replace] [--skip STEM ...]

For the release 0.1: --skip collinson (the editor, 2026-11-11: not to be published).

gists: the gists of every person of smelt TAG (smelt/<stem>/S4-GIST-VIEW-<TAG>.md), bound into one PDF (the editor, 2026-11-10: the gists bound as one book): a cover, the table of contents, a person a section from a new page, with the pictures
the gist view places; in the card's order (bingo-card/bingo-card-*.csv, then its supplement), the rest after them by stem.
bio: one PDF a person, from smelt/<stem>/S4-LABELLED-<TAG>.md: the biography's part 1 (the summary,
the contents, the periods, the appendices) and its «Referencoj»; parts 2-4 (the writer's report) are left out.

The face (the editor's choices, 2026-11-10, specimen prosopografio-pdf/TIPARO-PROVO-2026-11-10h.pdf, approved): the bingo
card's route and style (tools/bingo-book.py: pandoc to xelatex, A4, 12 point, margins of 2.4 cm, no hyphenation); Crimson Pro
for the text; EB Garamond for every Greek and Cyrillic letter (a whole name in one face) and for what Crimson Pro lacks;
STIX General, upright, for ∴ ⚫ ⚠ (⚠ at 80%); Cardo's pilcrow ¶, scaled to the capitals. Constant line spacing
(the line spacing constant, even where a fact is set as a subscript): \\lineskiplimit=-\\maxdimen, each
label's letter a subscript that takes no height.

Stops before writing anything if a character is in no face, a picture is missing, or a person lacks a file; stops after the
run if xelatex reports a missing character. Writes create-only (--replace to overwrite). Default output folder
geniza/prosopografio-pdf/: prosopografio-v<V>-skizaj-biografioj.pdf and prosopografio-v<V>-biografio-<stem>.pdf.
Needs pandoc, xelatex, fc-query, pypdf. No network.
"""
import argparse, csv, glob, os, re, shutil, subprocess, sys, tempfile, urllib.parse

from PIL import Image, ImageDraw
from pypdf import PdfReader

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.normpath(os.path.join(HERE, "..", "published", "heterophony-resources", "geniza"))
SMELT, CARD = os.path.join(G, "smelt"), os.path.join(G, "bingo-card")
FONTS = os.path.join(G, "sources", "web-2026-11-07-fonts")
STIX = "/System/Library/Fonts/Supplemental/"
PANDOC, XELATEX, FCQ = "/opt/homebrew/bin/pandoc", "/Library/TeX/texbin/xelatex", "/opt/homebrew/bin/fc-query"
OUTDIR = os.path.join(G, "prosopografio-pdf")
# the title (the editor, 2026-11-11: «La prosopografio de la Genizo» renamed «Prosopografio (personmenciaro) de pioniraj esperantistoj, de
# la projekto La Genizo de Esperanto»; the pioneer Idists a separate publication); SHORT for the running header and footer
TITLE = "Prosopografio (personmenciaro) de pioniraj esperantistoj, de la projekto La Genizo de Esperanto"
TITLE_MAIN, PROJECT = "Prosopografio (personmenciaro) de pioniraj esperantistoj", "de la projekto La Genizo de Esperanto"
SHORT = "Prosopografio de pioniraj esperantistoj"
# the titles in italics wherever the title is cited (the editor, 2026-11-11: «*Prosopografio (personmenciaro) de pioniraj
# esperantistoj*, de la projekto *La Genizo de Esperanto*»; the title in italics in the header;
# the title and the project's name in italics in «Citu kiel» too)
TITLE_IT = "\\textit{" + TITLE_MAIN + "}, de la projekto \\textit{La Genizo de Esperanto}"
SHORT_IT = "\\textit{" + SHORT + "}"

PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{Regular.ttf}[Path=CRIM/,BoldFont=Bold.ttf,ItalicFont=Italic.ttf,BoldItalicFont=BoldItalic.ttf]
\newfontfamily\gb{Regular.ttf}[Path=EBG/,BoldFont=Bold.ttf,ItalicFont=Italic.ttf,BoldItalicFont=BoldItalic.ttf,Ligatures=TeX]
\newfontfamily\fs{STIXGeneral.otf}[Path=STIX,ItalicFont=STIXGeneral.otf,BoldFont=STIXGeneralBol.otf,BoldItalicFont=STIXGeneralBol.otf,Scale=MatchLowercase]
\newfontfamily\cd{Regular.ttf}[Path=CARDO/,Scale=MatchUppercase]
\usepackage{graphicx}\usepackage{array}
\newcommand{\warnx}[1]{\scalebox{0.8}{\fs #1}}
\newcommand{\cdx}[1]{{\cd #1}}\newcommand{\gbx}[1]{{\gb #1}}\newcommand{\fsx}[1]{{\fs #1}}
\usepackage[margin=2.4cm]{geometry}
\usepackage[colorlinks,urlcolor=blue,linkcolor=blue,bookmarksnumbered=false]{hyperref}\urlstyle{same}
\usepackage{fancyhdr}\setlength{\headheight}{14pt}\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0.3pt}\lhead{\small HEADER}
\renewcommand{\footrulewidth}{0.3pt}\lfoot{\scriptsize FOOTER}\rfoot{\scriptsize paĝo \thepage{} el \pageref{FinoDeLaDokumento}}
\fancypagestyle{plain}{\fancyhf{}\renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0.3pt}\lfoot{\scriptsize FOOTER}\rfoot{\scriptsize paĝo \thepage{} el \pageref{FinoDeLaDokumento}}}
\providecommand{\tightlist}{\setlength{\itemsep}{2pt}\setlength{\parskip}{0pt}}
\setcounter{secnumdepth}{-1}\setcounter{tocdepth}{1}\renewcommand{\contentsname}{Enhavo}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\lineskiplimit=-\maxdimen
\newcommand{\lsub}[1]{\smash{\textsubscript{#1}}}
\raggedright\hyphenpenalty=10000\exhyphenpenalty=10000\tolerance=9999
% every heading kept with what follows it (the editor, 2026-11-11): a new page
% before a heading with less than five lines' room under it (needspace's test, written out: this TeX Live has no needspace)
\makeatletter
% (a heading straight after another, «Aldonoj» then «Nomoj», makes no test of its own: the first heading's test covers both,
% else the second would push itself over and leave the first alone at the page's foot)
\newcommand{\keepnext}[1]{\if@nobreak\else\par\penalty-100\begingroup\setlength{\dimen@}{#1}\dimen@ii\pagegoal\advance\dimen@ii-\pagetotal
  \ifdim\dimen@>\dimen@ii\ifdim\dimen@ii>\z@\vfil\fi\break\fi\endgroup\fi}
\makeatother
\usepackage{etoolbox}
\pretocmd{\section}{\keepnext{9\baselineskip}}{}{}
\pretocmd{\subsection}{\keepnext{5\baselineskip}}{}{}
\pretocmd{\subsubsection}{\keepnext{5\baselineskip}}{}{}
\pretocmd{\paragraph}{\keepnext{4\baselineskip}}{}{}
\begin{document}
$body$
\end{document}
"""

COVER = r"""\begin{titlepage}\begin{center}
\vspace*{3cm}
{\huge\bfseries TITLE\par}
\vspace{0.3cm}
{\Large PROJECT\par}
\vspace{0.6cm}
{\LARGE\bfseries SUBTITLE\par}
\vspace{0.6cm}
{\large COUNT\par}
\vspace{2.5cm}
{\large Kompilis COMPILER\par
Melburno 2026\par
versio VERSION\par}
\vspace{1.5cm}
Permesilo: \href{https://creativecommons.org/licenses/by-sa/4.0/deed.eo}{CC BY-SA 4.0}, krom citaĵoj kaj bildoj el aliaj fontoj\par
\vspace{0.4cm}
Projekto: La Genizo de Esperanto. \url{https://genizo.opoudjis.net}\par
\end{center}\end{titlepage}
\setcounter{page}{2}
"""   # the cover is page 1, unnumbered, so that every printed number is the PDF's page (as tools/bingo-book.py)


def charset(p):
    cs = subprocess.run([FCQ, "-i", "0", "-f", "%{charset}", p], capture_output=True, text=True, check=True).stdout.split()
    s = set()
    for r in cs:
        a, _, b = r.partition("-"); s |= set(range(int(a, 16), int(b or a, 16) + 1))
    return s


# THE FOOTER, THE INFORMATION BOX, THE PLACEHOLDER AND THE COLOPHON (the editor, 2026-11-11
# a colophon at the end, its wording his, below). The box reads the newest cut of the card (its main table, the supplement
# and the Lingva Komitato of 1905; everyone in it is on the card, by definition), draws the ribbon, the flag and the placeholder
# with tools/bingo-visual.py's own code, and adds the other spellings from profiles/NAMES-REGISTER.tsv.
SITE = "https://genizo.opoudjis.net"
FOOTER = f"{SHORT_IT} · versio VERSION · CC BY-SA 4.0 · genizo.opoudjis.net"
CARD_ALIAS = {"thisell": "cederblad"}   # the smelt's stem where the card has another (else the stem's last word: anselmo-morin → morin)
# the countries in the prosopography's Esperanto, -ujo for a people's land (memory: the site's style), from the card's English
UJO = {"Francio": "Francujo", "Rusio": "Rusujo", "Britio": "Britujo", "Aŭstrio-Hungario": "Aŭstrujo-Hungarujo", "Germanio": "Germanujo",
       "Italio": "Italujo", "Belgio": "Belgujo", "Svedio": "Svedujo", "Hispanio": "Hispanujo", "Bulgario": "Bulgarujo", "Japanio": "Japanujo",
       "Norvegio": "Norvegujo", "Danio": "Danujo", "Grekio": "Grekujo", "Persio": "Persujo", "Portugalio": "Portugalujo", "Barato": "Hindujo",
       "Pollando": "Polujo", "Litovio": "Litovujo", "Estonio": "Estonujo", "Ukrainio": "Ukrainujo", "Svislando": "Svisujo",
       "Finnlando": "Finnlando", "Nederlando": "Nederlando"}
COLOPHON = (   # the editor's points, 2026-11-11, in Esperanto; X and Y the items read and held at the release
    "\\href{" + SITE + "}{La Genizo de Esperanto: genizo.opoudjis.net}\\par\\smallskip "
    # the editor's own wording, 2026-11-11 01:0x
    "La prosopografio estas farata per artefarita inteligenteco, kunlabore kun la redaktoro, Nick Nicholas. Ĝia metodo estas severa: "
    "ĉiu atomeca fakto estas eltirita el fonto kaj kontrolata kontraŭ pluraj fontoj, ĉiu aserto estas pravigata per siaj fontoj, kaj "
    "necertaĵoj kaj truoj agnoskiĝas eksplicite.\\par\\smallskip "
    "Iuj faktoj neeviteble preterlasiĝas, kaj kelkajn konkludojn evidentajn al homo, la AI mistrafas; sed ĉiu homo, kiu trairus cent "
    "milionojn da vortoj, farus ankaŭ siajn proprajn erarojn.\\par\\smallskip "
    "La prosopografio estas daŭre ĝisdatigata, dum ĝi kovras ĉiam pli da fontoj, kaj dum korektiĝas la eraroj en la eltirado kaj la "
    "akordigo de la faktoj. Ĉi tiu versio kovras XITEMS erojn el la YITEMS fontaj dokumentoj, kiujn la projekto havas.")
_TMP = tempfile.mkdtemp(prefix="prosopografio-")   # the drawn pictures of one run


def items_read_and_held():
    """X: the items dowsed (dowse/DOWSED-ITEMS-LATEST.tsv, at the last harvest); Y: the items the project holds, the item table's
    and the dowsed items outside it (born-digital texts)."""
    rd = lambda p: list(csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t"))
    held = rd(os.path.join(G, "OCR-ITEM-TABLE.tsv")); read = rd(os.path.join(G, "dowse", "DOWSED-ITEMS-LATEST.tsv"))
    hi, hk = {r["item"] for r in held}, {r["key"] for r in held}
    x = {r["item"] for r in read}
    return len(x), len(hi) + len({r["item"] for r in read if r["item"] not in hi and r["key"] not in hk})


def bv():
    """tools/bingo-visual.py, for its ribbon, flags and placeholder"""
    import importlib.util
    if "_BV" not in globals():
        sp = importlib.util.spec_from_file_location("bingo_visual", os.path.join(HERE, "bingo-visual.py"))
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); globals()["_BV"] = m
    return globals()["_BV"]


def card_row(stem):
    files = latest_card_csvs()
    files.append(files[0].replace(".csv", "-lk1905.csv"))
    for want in (CARD_ALIAS.get(stem, stem), stem.split("-")[-1]):
        for f in files:
            if not os.path.exists(f): continue
            for r in csv.DictReader(open(f, encoding="utf-8")):
                if r.get("stem") == want: return r
    return None


def esc(s):
    return re.sub(r"([&%#_$])", r"\\\1", s)


def placeholder_tex():
    p = os.path.join(_TMP, "placeholder.png")
    if not os.path.exists(p): bv().placeholder(400, 520).save(p)
    return f"\\begingroup\\lineskiplimit=0pt\\begin{{center}}\\includegraphics[height=6.5cm]{{{p}}}\\end{{center}}\\par\\endgroup"


def infobox(stem, name, kind, version, compiler):
    """The box under the pictures: from the card, -> TeX, or exit if the person is not on it."""
    r = card_row(stem)
    if not r: sys.exit(f"{stem}: not on the card (main table, supplement, the Lingva Komitato of 1905): no box")
    V = bv()
    toks = V.tokens(r["tags_in_sequence"])
    born = next((y for m, y, _ in toks if m == "*"), "") or "⚫"
    died = next((y for m, y, _ in toks if m in "†‡"), "") or "⚫"
    c = r["country"]; base = re.sub(r" \(.*", "", c); sub = re.search(r"\((.*)\)", c)
    eo = UJO.get(V.COUNTRY_EO.get(base, base), V.COUNTRY_EO.get(base, base))
    if sub: eo += f" ({UJO.get(V.SUB_EO.get(sub.group(1), sub.group(1)), V.SUB_EO.get(sub.group(1), sub.group(1)))})"
    fp = os.path.join(_TMP, f"flag-{stem}.png"); fi = Image.new("RGB", (192, 128), (255, 255, 255)); V.flag(fi, c, 0, 0, 192, 128); fi.save(fp)
    adr = re.search(r"Adresaro (\d{4}), serio (\d+), n-ro (\d+)", r.get("evidence", ""))
    if adr: adr = f"{adr.group(1)}, serio {adr.group(2)}, n-ro {adr.group(3)}"
    else:
        a2 = re.search(r"adresaro-(\d{4})-serio-(\d+), ¶ ?(\d+)", r.get("evidence", ""))
        adr = f"{a2.group(1)}, serio {a2.group(2)}" if a2 else "⚫"
    # the ribbon, drawn as on the card, and a key of its own marks only
    s = 46
    W = sum(w for _, w in V.band_rows(toks, 10 ** 6, s)[0][0]) + int(s * .6)   # one row, as wide as its marks
    h = V.band_height(r["tags_in_sequence"], W, s)
    bp = os.path.join(_TMP, f"band-{stem}.png"); bi = Image.new("RGB", (W, h), V.BAND); V.band(bi, (0, 0, W, h), r["tags_in_sequence"], s); bi.save(bp)
    # the key of the ribbon's own marks, «*» too (the editor, 2026-11-11): each mark drawn as on
    # the card, its meaning set in the text's face
    used = []
    for m, _, _ in toks:
        if m not in used: used.append(m)
    meaning = dict(V.KEY)
    key = []
    for i, m in enumerate(used):
        gp = os.path.join(_TMP, f"mark-{stem}-{i}.png"); gi = Image.new("RGB", (72, 72), V.BAND); V.glyph(ImageDraw.Draw(gi), m, 6, 6, 60); gi.save(gp)
        mean = meaning.get(m, "")
        # a meaning the card's key gives for one person in its second half (💚: «…antaŭ 1894; poste nur Guillaume, apoganto sen
        # lerni ĝin»): that half only in that person's box, the first half in every other (the editor, 2026-11-11
        #)
        part = re.match(r"(.*?); poste nur (\w+), (.*)$", mean)
        if part: mean = part.group(3) if r.get("stem", "").lower() == part.group(2).lower() else part.group(1)
        key.append(f"\\hangindent=1.5em\\hangafter=1\\raisebox{{-0.2em}}{{\\includegraphics[height=1em]{{{gp}}}}}\\enspace {tex_text(mean, stem)}")
    rows = [("Naskiĝis", born), ("Mortis", died),
            ("Lando (laŭ la limoj de 1906)", f"\\raisebox{{-0.15em}}{{\\includegraphics[height=0.9em]{{{fp}}}}}\\enspace {esc(eo)}"),
            ("Faktoj en la prosopografio", f"{int(r['n_fact_lines']):,}".replace(",", " ")), ("La Adresaro de Zamenhof", adr)]
    if r.get("plate"):
        # the card's own notes inside a caption in Esperanto (the editor, 2026-11-11;
        # the same fix asked of the card's table)
        cap = r["caption"].replace("[shared legend as above]", "[la komuna surskribo, kiel supre]").replace("[shared legend, spanning TL+TR:]", "[komuna surskribo super la du supraj portretoj:]").replace("[photo credit printed under the portrait: «TRA LA MONDO»]", "[sub la portreto presita: «TRA LA MONDO»]")
        rows.append(("La albumo de Schuck", f"tabulo {esc(r['plate'].split(' ')[0])}: «{esc(cap)}»"))
    forms = names_forms(stem)
    if forms: rows.append(("Aliaj formoj", "; ".join(forms)))
    tab = "\n".join(f"{tex_text(a, stem)} & {tex_text(b, stem)}\\\\[2pt]" for a, b in rows)
    cite = (f"{compiler} (kompil.), «{'La biografio' if kind == 'bio' else 'La skiza biografio'} de {name}», en {TITLE_IT}, versio "
            f"{version}, Melburno 2026, \\url{{{SITE}}}")
    # the box's baseline at its foot ([b]) and the depth after it nothing, so that the fixed line spacing sets no line over it
    return ("\\begingroup\\lineskiplimit=0pt\\begin{center}\\fbox{\\begin{minipage}[b]{0.94\\textwidth}\\small\\setlength{\\parskip}{3pt}"
            f"\\begin{{tabular}}{{@{{}}>{{\\raggedright\\arraybackslash}}p{{5.2cm}}>{{\\raggedright\\arraybackslash}}p{{9.6cm}}@{{}}}}\n{tab}\n\\end{{tabular}}\\par\\medskip "
            # the heading and the ribbon centred, the key under the ribbon in two columns, each entry wrapping within its column
            # (the editor, 2026-11-11
            # the 💚 line ran past the column
            #); a long ribbon (Beauchemin's thirteen marks) kept within the box
            "{\\centering\\textbf{La bendo de la bingo-karto}\\par\\smallskip "
            f"\\includegraphics[width=\\linewidth,height=1.15cm,keepaspectratio]{{{bp}}}\\par\\smallskip "
            "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{0.47\\linewidth}@{\\hspace{0.04\\linewidth}}>{\\raggedright\\arraybackslash}p{0.47\\linewidth}@{}}"
            + "\\\\[1pt] ".join(" & ".join(key[i:i + 2] + ([""] if len(key[i:i + 2]) == 1 else [])) for i in range(0, len(key), 2))
            + "\\end{tabular}\\par}\\medskip "
            f"{{\\raggedright\\textbf{{Citu kiel:}} {tex_text(cite, stem)}\\par}}"
            "\\end{minipage}}\\end{center}\\par\\prevdepth=0pt\\endgroup")


def names_forms(stem):
    """the register's other forms of the person's main form (relation «name form»): the scripts and spellings beside the Latin"""
    head = None
    p = os.path.join(SMELT, stem, "PROFILE-FROZEN-2026-11-09s.md")
    for f in sorted(glob.glob(os.path.join(SMELT, stem, "PROFILE-FROZEN-*.md"))): p = f
    if os.path.exists(p):
        m = re.match(r"# (.+?) — ", open(p, encoding="utf-8").readline()); head = m.group(1) if m else None
    if not head: return []
    out = []
    for r in csv.DictReader((l for l in open(os.path.join(G, "profiles", "NAMES-REGISTER.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r.get("main_form") == head and r.get("relation") == "name form" and r["name"] not in out and re.search(r"[^\x00-\u024f]", r["name"]):
            out.append(r["name"])
    return out


def colophon():
    x, y = items_read_and_held()
    return ("\\par\\vfill\\begingroup\\lineskiplimit=0pt\\noindent\\rule{\\linewidth}{0.3pt}\\par\\smallskip{\\itshape\\footnotesize "
            + COLOPHON.replace("XITEMS", f"{x:,}".replace(",", " ")).replace("YITEMS", f"{y:,}".replace(",", " "))
            + "\\label{FinoDeLaDokumento}\\par}\\endgroup")


CRIM = charset(os.path.join(FONTS, "Crimson-Pro", "Regular.ttf"))
EB = charset(os.path.join(FONTS, "EB-Garamond", "Regular.ttf"))
SX = charset(os.path.join(STIX, "STIXGeneral.otf"))
NOFACE = {}   # character -> the stems it occurs in, where no face has it


def script(o):
    return 0x370 <= o <= 0x3ff or 0x1f00 <= o <= 0x1fff or 0x400 <= o <= 0x52f


def tex_text(s, stem):
    """A run of text (no link targets in it): each character Crimson Pro lacks, and every Greek and Cyrillic letter, put in a
    command pandoc passes through as raw TeX (a brace group it would escape): \\gbx{…} EB Garamond, \\fsx{…} STIX General,
    \\cdx{¶} Cardo, \\warnx{⚠} STIX at 80%."""
    out, run, kind = [], "", None
    def flush():
        nonlocal run, kind
        if run: out.append(("\\gbx{" if kind == "g" else "\\fsx{") + run + "}")
        run, kind = "", None
    for ch in s:
        o = ord(ch)
        if ch == "¶": flush(); out.append("\\cdx{¶}"); continue
        if ch == "⚠": flush(); out.append("\\warnx{⚠}"); continue
        if o > 127 and (o not in CRIM or script(o)):
            if o in EB: k = "g"
            elif o in SX: k = "s"
            else: NOFACE.setdefault(ch, set()).add(stem); continue
            if kind and k != kind: flush()
            run += ch; kind = k; continue
        if run and kind == "g" and ch == " ": run += ch; continue
        flush(); out.append(ch)
    flush()
    return "".join(out)


FORMS = [   # the venture's Esperanto forms, set at print time over what the writers wrote (their returns stay as written)
    # the editor, 2026-11-10
    (re.compile(r"\bOCR\b"), "OSR"),
    # the editor, 2026-11-10; a writer's gloss after the
    # German name folded into one; the writers' «Aŭstria» made «Aŭstra», its endings kept; the sigla (ÖNB2026) untouched
    (re.compile(r"Österreichischen? Nationalbibliothek\s*[\[(]Aŭstri?a Nacia Biblioteko[\])]"), "Aŭstra Nacia Biblioteko"),
    (re.compile(r"Österreichischen? Nationalbibliothek"), "Aŭstra Nacia Biblioteko"),
    (re.compile(r"\bAŭstria(n?) Nacia(n?) Biblioteko(n?)"), r"Aŭstra\1 Nacia\2 Biblioteko\3"),
    (re.compile(r"Aŭstra Nacia Biblioteko\s*[\[(]Aŭstra Nacia Biblioteko[\])]"), "Aŭstra Nacia Biblioteko"),
]


def forms(s):
    for p, r in FORMS: s = p.sub(r, s)
    return smart_quotes(s)


# TYPOGRAPHIC QUOTES AND APOSTROPHES (the editor, 2026-11-11, of «—(”Ido.”)»: a curly-quote error at a boundary,
# likely to recur; of «Uniono di l'Amiki»: a straight apostrophe there): TeX sets a straight " as a closing quote wherever it
# stands; here each straight quote is made the curly one its place calls for: opening after the start, a space, a bracket, a
# dash, a slash or «, the markdown stars and underscores looked through; closing elsewhere; an apostrophe between letters (l'Amiki,
# Ido's) the closing single quote; a curly closing quote where an opening one belongs turned round
OPENERS = set(" \t\n([{«—–/“‘") | {""}


def smart_quotes(s):
    out = []
    for i, ch in enumerate(s):
        if ch in "\"'”’":
            j = i - 1
            while j >= 0 and s[j] in "*_": j -= 1
            prev = s[j] if j >= 0 else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            opening = prev in OPENERS and nxt not in " \t\n" and not (ch in "'’" and nxt.isdigit())   # «'08» an elision
            if ch in "\"”": ch = "“" if opening else "”"
            else: ch = "‘" if opening else "’"
        out.append(ch)
    return "".join(out)


TARGET = re.compile(r"(\]\([^)\s]*\)|<https?://[^>\s]+>)")   # a link's target and an autolink: never wrapped, non-ASCII %-encoded


def tex_md(s, stem):
    s = s.replace("\ufe0f", "")
    # every backslash, dollar, caret and tilde the text holds is printed as itself, never read as TeX, mathematics, a superscript
    # or a subscript (the editor, 2026-11-10):
    # Wallon's «\Val!ou» (the OCR's reading of «Wallon», quoted as a misreading), Dragoumis's «D^r», Bourlet's «5$11»
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([$^~])", r"\\\1", s)
    s = re.sub(r"<sub>([^<]*)</sub>", r"\\lsub{\1}", s)
    parts = TARGET.split(s)
    for i in range(1, len(parts), 2):
        p = parts[i]
        if p.startswith("<"): parts[i] = "<" + urllib.parse.quote(p[1:-1], safe=":/?&=#%+@,;~!$*'()[]-._") + ">"
        elif not p.startswith("](#"): parts[i] = "](" + urllib.parse.quote(p[2:-1], safe=":/?&=#%+@,;~!$*'()[]-._") + ")"
    for i in range(0, len(parts), 2): parts[i] = tex_text(forms(parts[i]), stem)
    return "".join(parts)


IMG = re.compile(r'<img src="([^"]+)"[^>]*>')
MISSING_PICTURES = []
PICS = []   # the pictures' TeX, put back by put_pictures() after tex_md, which would escape its commands


def put_pictures(md):
    return re.sub(r"PICTUREBLOCK(\d+)END", lambda m: PICS[int(m.group(1))], md)


def pictures(md, base, stem):
    """A gist view's «<p><img …> <img …></p>» line: the pictures side by side, centred, each at most 6.5 cm high and within its
    share of the width."""
    def one(m):
        srcs = IMG.findall(m.group(0))
        w = 0.95 / max(1, len(srcs))
        cells = []
        for s in srcs:
            p = os.path.normpath(os.path.join(base, urllib.parse.unquote(s)))   # the view's %-encoded names (Carlo_Bourlet%2C_1908.jpg)
            if not os.path.exists(p): MISSING_PICTURES.append((stem, p)); continue
            cells.append(f"\\includegraphics[height=6.5cm,width={w:.2f}\\textwidth,keepaspectratio]{{{p}}}")
        # the fixed line spacing set aside for the pictures alone: under \lineskiplimit=-\maxdimen a picture's line would be
        # set one baseline below the line before it and overprint it
        PICS.append("\\begingroup\\lineskiplimit=0pt\\begin{center}" + "\\hspace{0.8em}".join(cells) + "\\end{center}\\par\\endgroup")
        return f"PICTUREBLOCK{len(PICS) - 1}END"
    return re.sub(r"(?m)^<p>(?:\s*<img [^>]*>)+\s*</p>$", one, md)


def inner_titles(md):
    """A picture's caption, set in italics, that holds a title in italics («*1. foto: … el *Les Prix Nobel 1920* (…)*»): the
    title set upright inside it, as the biographies' abstracts do (the editor, 2026-10-19), so that the stars pair"""
    def one(m):
        body = m.group(1)
        # «el *T* (A.» → «el* T *(A.»: the stars against the outer words, so that they close and reopen the italics
        return "*" + re.sub(r"\s\*([^*\n]+)\*\s?(?=[^\s])", lambda k: f"* {k.group(1)} *", body) + "*"
    return re.sub(r"(?m)^\*(\d+\. [^\n]*\*[^*\n]+\*[^\n]*)\*$", one, md)


def notes_out(md):
    """The tools' provenance notes («`[tools/… ]`» lines), which belong to the working copies, not the reading copies."""
    return re.sub(r"(?m)^`\[[^\n]*\]`\s*\n", "", md)


def latest_card_csvs():
    """The newest cut of the card and its supplement: the order of the people."""
    vs = sorted({re.search(r"bingo-card-v(\d+(?:\.\d+)*)", f).group(1) for f in glob.glob(os.path.join(CARD, "bingo-card-v*.csv"))},
                key=lambda v: [int(x) for x in v.split(".")])
    v = vs[-1]
    return [os.path.join(CARD, f"bingo-card-v{v}.csv"), os.path.join(CARD, f"bingo-card-v{v}-supplement.csv")]


def order(stems):
    """the card's order: its main table, the supplement, then the Lingva Komitato of 1905; a smelt stem found under the card's
    own stem (CARD_ALIAS, or its last word)"""
    files = latest_card_csvs(); files.append(files[0].replace(".csv", "-lk1905.csv"))
    pos, n = {}, 0
    for f in files:
        if not os.path.exists(f): continue
        for r in csv.DictReader(open(f, encoding="utf-8")):
            pos.setdefault(r.get("stem"), n); n += 1
    at = lambda s: min((pos[k] for k in (CARD_ALIAS.get(s, s), s.split("-")[-1]) if k in pos), default=None)
    on = sorted((s for s in stems if at(s) is not None), key=at)
    return on + sorted(s for s in stems if at(s) is None)


def compile_pdf(md, header, out, replace, footer):
    if os.path.exists(out) and not replace: sys.exit(f"{out} exists (--replace to overwrite)")
    if "<img" in md or "PICTUREBLOCK" in md or "\\\\includegraphics" in md: sys.exit(f"{out}: a picture not placed, nothing written")
    pics = md.count("\\includegraphics")
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "t.md"), "w", encoding="utf-8").write(md)
        tpl = (PREAMBLE.replace("CRIM", os.path.join(FONTS, "Crimson-Pro")).replace("EBG", os.path.join(FONTS, "EB-Garamond"))
               .replace("CARDO", os.path.join(FONTS, "Cardo")).replace("Path=STIX", "Path=" + STIX).replace("HEADER", header).replace("FOOTER", footer))
        open(os.path.join(tmp, "tpl.tex"), "w", encoding="utf-8").write(tpl)
        subprocess.run([PANDOC, "t.md", "-f", "markdown-smart+gfm_auto_identifiers", "-o", "t.tex", "--template", "tpl.tex"], check=True, cwd=tmp)
        for _ in range(3):   # three times: the contents, then the pages it pushes on, then the links' targets
            r = subprocess.run([XELATEX, "-interaction=batchmode", "-halt-on-error", "t.tex"], cwd=tmp, capture_output=True, text=True)
        log = open(os.path.join(tmp, "t.log"), encoding="utf-8", errors="replace").read()
        if r.returncode or not os.path.exists(os.path.join(tmp, "t.pdf")):
            sys.exit(f"xelatex failed for {out}:\n" + log[-2500:])
        miss = sorted(set(re.findall(r"Missing character: There is no (.+?) in font ([^!]+)!", log)))
        if miss: sys.exit(f"{out}: xelatex found characters missing from their face, nothing written: {miss[:20]}")
        dead = sorted(set(re.findall(r"name\{([^}]*)\} has been referenced but does not exist", log)))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(os.path.join(tmp, "t.pdf"), out)
    n = len(PdfReader(out).pages)
    if n == 0: sys.exit(f"{out}: no pages")
    print(f"{os.path.relpath(out, G)}: {n} pages, {pics} pictures, {os.path.getsize(out) // 1024} KB" + (f"; {len(dead)} contents links with no heading: {dead[:5]}" if dead else ""))


def stop_if_faults():
    if NOFACE or MISSING_PICTURES:
        for ch, st in sorted(NOFACE.items()): print(f"no face has {ch!r} (U+{ord(ch):04X}): {', '.join(sorted(st))}", file=sys.stderr)
        for st, p in MISSING_PICTURES: print(f"{st}: picture missing: {p}", file=sys.stderr)
        sys.exit("stopped before writing: the faults above")


def gists(a):
    files = sorted(glob.glob(os.path.join(SMELT, "*", f"S4-GIST-VIEW-{a.tag}.md")))
    stems = order([f.split(os.sep)[-2] for f in files if f.split(os.sep)[-2] not in a.skip])
    if not stems: sys.exit(f"no smelt/*/S4-GIST-VIEW-{a.tag}.md")
    body = []
    for s in stems:
        p = os.path.join(SMELT, s, f"S4-GIST-VIEW-{a.tag}.md")
        md = inner_titles(notes_out(open(p, encoding="utf-8").read()))
        md = pictures(md, os.path.dirname(p), s)
        h = re.search(r"(?m)^# (La skiza biografio de )?(.+)$", md)
        if not h: sys.exit(f"{s}: no «# » title in {os.path.relpath(p, G)}")
        # a new page for each person; the contents and the bookmarks give the name alone
        name = tex_md(h.group(2).strip(), s)
        rest = md[h.end():]
        k = re.search(r"(?m)^## ", rest)
        if not k: sys.exit(f"{s}: no «## » heading in the gist")
        lead = rest[:k.start()]
        if "PICTUREBLOCK" not in lead: PICS.append(placeholder_tex()); lead = f"\n\nPICTUREBLOCK{len(PICS) - 1}END\n\n" + lead
        rest = with_box(lead + "\n\nINFOBOXHERE\n\n" + rest[k.start():], s, h.group(2).strip(), "gist", a)
        md = md[:h.start()] + f"\\clearpage\n\n\\section[{name}]{{{tex_md(h.group(0)[2:].strip(), s)}}}\n" + put_pictures(tex_md(rest, s))
        body.append(md)
    stop_if_faults()
    cover = (COVER.replace("SUBTITLE", "La skizaj biografioj").replace("TITLE", TITLE_MAIN).replace("PROJECT", PROJECT).replace("COUNT", f"{len(stems)} personoj")
             .replace("COMPILER", a.compiler).replace("VERSION", a.version))
    md = "```{=latex}\n" + cover + "\\tableofcontents\n```\n\n" + "\n\n".join(body) + "\n\n```{=latex}\n" + colophon() + "\n```\n"
    out = a.out or os.path.join(OUTDIR, f"prosopografio-v{a.version}-skizaj-biografioj.pdf")
    compile_pdf(md, f"{SHORT_IT} · la skizaj biografioj · versio {a.version} · kompilis: {a.compiler}", out, a.replace, FOOTER.replace("VERSION", a.version))
    print("in order:", " ".join(stems))


def bio_md(stem, tag):
    p = os.path.join(SMELT, stem, f"S4-LABELLED-{tag}.md")
    if not os.path.exists(p): sys.exit(f"{stem}: no {os.path.relpath(p, G)}")
    t = open(p, encoding="utf-8").read()
    m = re.search(r"(?m)^# La biografio de (.+)$", t)
    p1 = re.search(r"(?m)^## 1\. La resumo kaj la biografio\s*$", t)
    p2 = re.search(r"(?m)^## 2\. ", t)
    if not (m and p1 and p2 and m.start() < p1.start() < p2.start()): sys.exit(f"{stem}: the title, «## 1.» or «## 2.» not found in order")
    name = re.sub(r"\s*\((?:smelt )?S4, [^)]*\).*$", "", m.group(1)).strip()
    pre = inner_titles(notes_out(t[m.end():p1.start()]))
    # the writers' notes of the working files they read («Legitaj: S3-RETURN-2026-11-09s.md, …», Miletz's), which mean nothing to
    # a reader (the editor, 2026-11-11): every line naming one of our files, out
    WORKFILE = re.compile(r"\b[A-Z][A-Z0-9-]*-\d{4}-\d\d-\d\d\w*(?:-[\w-]+)?\.(?:md|tsv)\b")
    pre = "\n".join(l for l in pre.split("\n") if not WORKFILE.search(l))
    pre = re.sub(r"(?m)^# La biografio de .*\n", "", pre)   # a second title line (Brzostowski's)
    body = notes_out(t[p1.end():p2.start()])
    body = "\n".join(l for l in body.split("\n") if not WORKFILE.search(l))
    lines = []
    for l in body.split("\n"):
        h = re.match(r"^(#+) (.*)$", l)
        if h:
            n = len(h.group(1))
            if n == 1: l = f"*{h.group(2).strip()}*"   # a writer's own subtitle (Dervaux's), set as a line, not a heading
            elif n == 2: l = "# " + h.group(2)            # «## Referencoj»
            else: l = "#" * (n - 2) + " " + h.group(2)    # ### → #, #### → ##
        lines.append(l)
    # the references' key, from «Kiel legi» to the first entry, in small type (the editor, 2026-11-11
    #)
    k = next((i for i, l in enumerate(lines) if l.startswith("Kiel legi la ŝlosilojn")), None)
    if k is not None:
        e = next((i for i in range(k + 1, len(lines)) if lines[i].startswith("- **") or lines[i].startswith("#")), len(lines))
        PICS.append("\\begingroup\\footnotesize"); a_ = len(PICS) - 1
        PICS.append("\\par\\endgroup"); b_ = len(PICS) - 1
        lines = lines[:k] + [f"PICTUREBLOCK{a_}END", ""] + lines[k:e] + ["", f"PICTUREBLOCK{b_}END", ""] + lines[e:]
    pre = pictures(pre, os.path.dirname(p), stem)
    if "PICTUREBLOCK" not in pre: PICS.append(placeholder_tex()); pre = f"PICTUREBLOCK{len(PICS) - 1}END\n\n" + pre
    return name, pre + "\n\nINFOBOXHERE\n\n" + "\n".join(lines)


def with_box(md, stem, name, kind, a):
    """the information box where INFOBOXHERE stands, and the colophon at the end"""
    PICS.append(infobox(stem, name, kind, a.version, a.compiler))
    return md.replace("INFOBOXHERE", f"PICTUREBLOCK{len(PICS) - 1}END", 1)


def bio(a):
    stems = sorted(f.split(os.sep)[-2] for f in glob.glob(os.path.join(SMELT, "*", f"S4-LABELLED-{a.tag}.md"))) if a.all else a.stems
    stems = [s for s in stems if s not in a.skip]
    if not stems: sys.exit("no person named (STEM ... or --all)")
    built = []
    for s in stems:
        name, md = bio_md(s, a.tag)
        doc = ("```{=latex}\n\\begin{center}{\\LARGE\\bfseries " + tex_text("La biografio de " + name, s) + "\\par}\\vspace{0.3cm}"
               + f"{{\\small {TITLE_IT}\\par versio {a.version} · kompilis {a.compiler} · Melburno 2026\\par "
               + "Permesilo: \\href{https://creativecommons.org/licenses/by-sa/4.0/deed.eo}{CC BY-SA 4.0}, krom citaĵoj kaj bildoj el aliaj fontoj\\par}"
               + "\\end{center}\n```\n\n" + put_pictures(tex_md(with_box(md, s, name, "bio", a), s))
               + "\n\n```{=latex}\n" + colophon() + "\n```\n")
        stop_if_faults()
        built.append((s, name, doc))
    for s, name, doc in built:
        out = os.path.join(a.outdir or OUTDIR, f"prosopografio-v{a.version}-biografio-{s}.pdf")
        compile_pdf(doc, tex_text(f"La biografio de {name} · {SHORT_IT}, versio {a.version}", s), out, a.replace, FOOTER.replace("VERSION", a.version))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gists"); g.add_argument("tag"); g.add_argument("--out")
    b = sub.add_parser("bio"); b.add_argument("tag"); b.add_argument("stems", nargs="*"); b.add_argument("--all", action="store_true"); b.add_argument("--outdir")
    for p in (g, b):
        p.add_argument("--version", required=True); p.add_argument("--compiler", default="Nick Nicholas"); p.add_argument("--replace", action="store_true")
        # a person smelted but not for this release (the editor, 2026-11-11
        #)
        p.add_argument("--skip", nargs="*", default=[], metavar="STEM")
    a = ap.parse_args()
    gists(a) if a.cmd == "gists" else bio(a)


if __name__ == "__main__":
    main()
