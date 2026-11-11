"""page_date — the date line of a generated site page: «_Aktualigita: YYYY-MM-DD._», the day its generated part last
changed (2026-10-31; the editor 12:0x; to the question who edits the generators). Read by tools/dowse-done.py
(legitaj-fontoj), tools/sigla-propose.py --page (siglaro), tools/smeltee-list.py (biografatoj), tools/genizo-osr-list.py
--page (osr-korpuso), tools/genizo-osr-grades.py (osr-kvalito; the editor);
the Prosopografio page keeps its own «Dato» line (tools/prosopografio-progreso.py). The runbook:
published/genizo/PROGRESS-PAGES-RUNBOOK.md. Miles.

    stamp(old_page, new_page) -> new_page with one date line, put after the first generated mark («<!-- … generated … -->»,
    «GENERATED», «written by»): today's date where the page differs from old_page beyond the date line, else old_page's
    date (a run that changes nothing changes no date, so «nothing to push» stays true)."""
import datetime, re

LINE = re.compile(r"^_Aktualigita: (\d{4}-\d\d-\d\d)\._\n\n?", re.M)
MARK = re.compile(r"^<!-- (?!/)[^\n]*(?:generated|GENERATED|written by)[^\n]*-->\n\n?", re.M)


def stamp(old_page, new_page):
    bare = LINE.sub("", new_page)
    had = LINE.search(old_page or "")
    day = had.group(1) if had and LINE.sub("", old_page) == bare else datetime.date.today().isoformat()
    m = MARK.search(bare)
    if not m:
        raise SystemExit("page_date: no generated mark («<!-- … generated … -->») to put the date line after")
    return bare[:m.end()] + f"_Aktualigita: {day}._\n\n" + bare[m.end():]   # LINE.sub() gives back `bare` exactly
