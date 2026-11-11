#!/usr/bin/env python3
"""The bingo card's visual form bound into one PDF (the editor, 2026-11-06; the preface).

    bingo-book.py --preface FILE.md --out FILE.pdf --version V --cover IMAGE [--compiler NAME] [--aligned LINE] [--replace]

The book, in order: the front cover (the editor, 2026-11-07: its wording his, the caricature on it); the preface up to its «## Kreditoj» heading; the key; the album's plates in page order; the pages of the people outside the album; the counts; the credits.
Reads bingo-card/visual/ (key.png, plate-NN.jpg, rest-NN.jpg, as tools/bingo-visual.py left them) and FILE.md (the English summary, a <details> block, and the caricature, a <div class="genizo-karikaturo"> block, both for the site, are left out).
Needs pandoc and xelatex. Writes FILE.pdf, refused if it exists unless --replace. No network.
"""
import argparse, glob, os, re, shutil, subprocess, sys, tempfile

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter

HERE = os.path.dirname(os.path.abspath(__file__))
VISUAL = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza", "bingo-card", "visual")
WIDTH = 595.0   # points: the width of an A4 page, every picture page set to it
FONTDIR = os.path.join(VISUAL, "..", "..", "sources", "web-2026-11-07-fonts", "Crimson-Pro")   # the editor, 2026-11-07; OFL, Google Fonts


TEMPLATE = r"""\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{Regular.ttf}[Path=FONTDIR/,BoldFont=Bold.ttf,ItalicFont=Italic.ttf,BoldItalicFont=BoldItalic.ttf]
\usepackage[margin=2.4cm]{geometry}
\usepackage[colorlinks,urlcolor=blue,linkcolor=blue]{hyperref}\urlstyle{same}
\usepackage{fancyhdr}\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0.3pt}\lhead{\small HEADER}\cfoot{\small\thepage}
\providecommand{\tightlist}{\setlength{\itemsep}{2pt}\setlength{\parskip}{0pt}}
\setcounter{secnumdepth}{-1}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\raggedright\hyphenpenalty=10000\exhyphenpenalty=10000\tolerance=9999   % no word or link broken at a line's end: the engine has no Esperanto patterns
\begin{document}
\setcounter{page}{STARTPAGE}
$body$
\end{document}
"""


COVER = r"""\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{Regular.ttf}[Path=FONTDIR/,BoldFont=Bold.ttf,ItalicFont=Italic.ttf,BoldItalicFont=BoldItalic.ttf]
\usepackage[margin=2.4cm]{geometry}
\usepackage{graphicx}
\usepackage[colorlinks,urlcolor=blue,linkcolor=blue]{hyperref}\urlstyle{same}
\pagestyle{empty}\setlength{\parindent}{0pt}
\begin{document}
\begin{center}
\vspace*{0.2cm}
{\huge\bfseries La bingo-karto de la eminentaj esperantistoj\par}
\vspace{0.5cm}
{\LARGE\bfseries Kiu restis, kiu foriris post la Ido-skismo\par}
\vspace{0.9cm}
\includegraphics[width=\textwidth,height=0.5\textheight,keepaspectratio]{IMAGE}
\vspace{0.9cm}

{\large Kompilis COMPILER\par
Melburno 2026\par
versio VERSION\par
ALIGNED}
\vspace{0.9cm}
Permesilo: \href{https://creativecommons.org/licenses/by-sa/4.0/deed.eo}{CC BY-SA 4.0}, krom citaĵoj kaj bildoj el aliaj fontoj (vidu la Kreditojn)\par
\vspace{0.4cm}
Projekto: La Genizo de Esperanto. \url{https://genizo.opoudjis.net}\par
\end{center}
\end{document}
"""


def cover_pdf(image, version, compiler, out, tmp, aligned=""):
    """aligned: a line under the version (the editor, 2026-11-10 22:4x: the card), or none."""
    src = os.path.join(tmp, "cover.tex")
    open(src, "w", encoding="utf-8").write(COVER.replace("FONTDIR", os.path.abspath(FONTDIR)).replace("IMAGE", os.path.abspath(image)).replace("COMPILER", compiler).replace("VERSION", version).replace("ALIGNED", (aligned + r"\par") if aligned else ""))
    subprocess.run(["/Library/TeX/texbin/xelatex", "-interaction=batchmode", "-output-directory", tmp, src], check=True, cwd=tmp, capture_output=True)
    shutil.move(os.path.join(tmp, "cover.pdf"), out)


def text_pdf(md, title, out, tmp, start):
    """start: the book's page number of the text's first page (the cover is page 1, unnumbered), so that every printed number is the PDF page."""
    src = os.path.join(tmp, title + ".md"); open(src, "w", encoding="utf-8").write(md)
    tpl = os.path.join(tmp, "book.tex"); open(tpl, "w", encoding="utf-8").write(TEMPLATE.replace("HEADER", HEAD[0]).replace("FONTDIR", os.path.abspath(FONTDIR)).replace("STARTPAGE", str(start)))
    subprocess.run(["/opt/homebrew/bin/pandoc", src, "-f", "markdown-smart", "-o", out, "--pdf-engine=/Library/TeX/texbin/xelatex", "--template", tpl], check=True, cwd=tmp, capture_output=True)


HEAD = [""]   # the running header (the editor, 2026-11-06)


CANVAS = [0, 0]   # (width, height) of every picture page's picture area: the widest picture and the tallest Schuck plate (set in main)


def picture_pdf(path, out, num):
    """One picture page: the picture top-aligned and centred on a white area of the one CANVAS size, never scaled, so that every
    picture page is the same size and a printer scales them all alike (the editor, 2026-11-10; a page wider than tall was turned by the printer); the header above, the page
    number (num, the PDF page) below."""
    src = Image.open(path).convert("RGB")
    cw, ch = max(CANVAS[0], src.width), max(CANVAS[1], src.height)
    bar = max(44, cw // 28)   # the header above the picture, and the footer below it, nothing drawn over the picture
    im = Image.new("RGB", (cw, bar + ch + bar), (255, 255, 255))
    edge = sorted(src.getpixel((x, src.height - 1)) for x in range(0, src.width, 5))
    bg = edge[len(edge) // 2]   # the picture's own background, the median of its bottom row (the people pages are cream, not white)
    im.paste(Image.new("RGB", (cw, ch), bg), (0, bar))
    im.paste(src, ((cw - src.width) // 2, bar))
    font = ImageFont.truetype(os.path.join(FONTDIR, "Regular.ttf"), bar // 2)
    d = ImageDraw.Draw(im)
    d.text((cw // 30, bar // 2), HEAD[0], font=font, fill=(40, 40, 40), anchor="lm")
    d.text((cw // 2, bar + ch + bar // 2), str(num), font=font, fill=(40, 40, 40), anchor="mm")
    im.save(out, "PDF", resolution=im.width / (WIDTH / 72), quality=90)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--preface", required=True); ap.add_argument("--out", required=True); ap.add_argument("--replace", action="store_true"); ap.add_argument("--version", required=True); ap.add_argument("--cover", required=True); ap.add_argument("--compiler", default="Nick Nicholas"); ap.add_argument("--aligned", default="", help="a line under the cover's version, e.g. the prosopography version the card is aligned with")
    a = ap.parse_args()
    if os.path.exists(a.out) and not a.replace: sys.exit(f"{a.out} exists")
    md = open(a.preface, encoding="utf-8").read()
    md = re.sub(r"(?s)<details.*?</details>\s*", "", md)
    md = re.sub(r'(?s)<div class="genizo-karikaturo".*?</div>\s*', "", md)
    HEAD[0] = f"La bingo-karto de la Genizo · versio {a.version} · kompilis: {a.compiler}"
    head, sep, credits = md.partition("## Kreditoj")
    if not sep: sys.exit("no «## Kreditoj» heading in the preface")
    plates = sorted(glob.glob(os.path.join(VISUAL, "plate-*.jpg")))
    rest = sorted(glob.glob(os.path.join(VISUAL, "rest-*.jpg")))
    counts = sorted(glob.glob(os.path.join(VISUAL, "nombroj-*.jpg")))
    sizes = [Image.open(f).size for f in plates]
    CANVAS[:] = [max(s[0] for s in sizes), max(s[1] for s in sizes)]
    w = PdfWriter()
    with tempfile.TemporaryDirectory() as tmp:
        def add(path, mark=None):
            start = len(w.pages)
            for p in PdfReader(path).pages: w.add_page(p)
            if mark: w.add_outline_item(mark, start)
        cv = os.path.join(tmp, "kovrilo.pdf"); cover_pdf(a.cover, a.version, a.compiler, cv, tmp, a.aligned); add(cv, "Kovrilo")
        one = os.path.join(tmp, "antauparolo.pdf"); text_pdf(head, "Antaŭparolo", one, tmp, len(w.pages) + 1); add(one, "Antaŭparolo")
        k = os.path.join(tmp, "key.pdf"); picture_pdf(os.path.join(VISUAL, "key.png"), k, len(w.pages) + 1); add(k, "La ŝlosilo")
        for i, f in enumerate(plates):
            n = os.path.join(tmp, f"p{i}.pdf"); picture_pdf(f, n, len(w.pages) + 1); add(n, "La albumo de Schuck" if i == 0 else None)
        for i, f in enumerate(rest):
            n = os.path.join(tmp, f"r{i}.pdf"); picture_pdf(f, n, len(w.pages) + 1); add(n, "Ekster la albumo" if i == 0 else None)
        for i, f in enumerate(counts):
            n = os.path.join(tmp, f"n{i}.pdf"); picture_pdf(f, n, len(w.pages) + 1); add(n, "Nombroj" if i == 0 else None)
        c = os.path.join(tmp, "kreditoj.pdf"); text_pdf(sep + credits, "Kreditoj", c, tmp, len(w.pages) + 1); add(c, "Kreditoj")
        w.add_metadata({"/Title": "La bingo-karto de la eminentaj esperantistoj: kiu restis, kiu foriris post la Ido-skismo", "/Author": a.compiler})
        with open(a.out, "wb") as f: w.write(f)
    print(a.out, len(w.pages), "pages,", os.path.getsize(a.out) // 1024 // 1024, "MB:", len(plates), "plates,", len(rest), "other pages")


if __name__ == "__main__":
    main()
