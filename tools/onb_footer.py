"""onb_footer — the ÖNB viewer's page footer, «https://data.onb.ac.at/rep/<id> Seite N von M», taken out of a page's text.

    import onb_footer as OF;  OF.strip(text)

WHY (the editor 2026-11-03 14:5x, after; 31,039 pages of 128 items carry it).
The footer is the library's, not the source's. Nothing paginates by it: the page-number check ignores it on purpose
(`ocr-page-sequence.py` VIEWER, check 2b of 2026-10-08), and the download checks read it from the PDFs. The readings on
disk keep it; `ocr-rebuild-combined.py` strips it from the search and preferred texts it writes, and
`ocr-recupel-notice.py` compares pages without it, so its removal raises no notice.
Only the footer's own words go (the link, any token holding «onb.ac.», as the OCR mangles it: «data.onb.ac.atYrep»,
«hitps:/data.onb.ac.aUrep»; and «Seite N von M», misread letters allowed as in VIEWER); a line left empty goes with
them, and any other words on the line stay.
"""
import re

FOOTER = re.compile(r"\S*onb\.ac\.\S*|\bS[eo][il1I|]te\s*\d+\s*v[o0a]n\s*\d+\b")


def key(text):
    """for comparing two versions of a page: the footer out and the white space collapsed (a page that held only the
    footer differs from its rebuilt self by a blank line alone: svensk.varldspraks, 6 of 263 pages, tested 2026-11-03)"""
    return " ".join(strip(text).split())


def strip(text):
    if "onb.ac." not in text and not re.search(r"v[o0a]n\s*\d", text):
        return text
    out = []
    for line in text.split("\n"):
        new = FOOTER.sub("", line)
        if new != line:
            new = re.sub(r"[ \t]{2,}", " ", new).strip()
            if not new:
                continue
        out.append(new)
    return "\n".join(out)
