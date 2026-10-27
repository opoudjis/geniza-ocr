#!/usr/bin/env python3
r"""harvest-facts.py — roll per-source fact lines up into per-person profiles.

Usage:
    tools/harvest-facts.py --check      # validate format only, write nothing
    tools/harvest-facts.py              # validate, then write geniza/profiles/<surname>.md; REFUSES to write
                                        # anything on a format error or a profile collision (2026-10-10); then
                                        # writes profiles/build/FACTS-LIST.tsv and MISSING-FACTS-LATEST.md
    tools/harvest-facts.py --csv f.csv  # also dump everything flat

Facts files declaring `facts-format: 2` near their head get the strict checks (see FORMAT2 below).

THE CONTRACT (geniza/PROFILE-RETROFIT-SPEC-2026-09-04.md sec. 2)

Per-source files live in `geniza/profiles/by-source/`. Facts are written one per line,
each line naming its own subject:

    - $$$ TROMPETER $$$ **1896** · Sent 200 marks to Lingvo Internacia · `sources/ocr/Lingvo Internacia 1896.2.txt` · [B][BIO] · ✅
    - $$$ TROMPETER $$$ **[n.d.]** · German mine-surveyor of Schalke, Westphalia · EdE s.v. Trompeter · [BIO] · 📄

      ^ sigil  ^ NAME (upper) ^ sigil  ^ year or [n.d.]  ^ fact  ^ source+locator  ^ theme(s)  ^ confidence

`$$$` is RESERVED: it occurs on fact lines and nowhere else, so `grep '^- \\$\\$\\$'`
returns the pure fact corpus. Synthesis, argument and cross-references are wanted in the
same file — the editor asked for them — but they use ordinary prose and can never match.

WHO A FACT IS ABOUT is carried IN THE LINE, between the sigils. That costs a repeated name
and buys self-containment: no dependency on heading structure, nothing breaks on reorder or
copy, and one grep per person. A fact about two roster people is written twice.

WHY THIS EXISTS. The per-source files are the working record; the per-person files are what
you actually open when writing a paragraph. Editor, 2026-09-04, asked whether the harvested
per-person index was the deliverable meant by "detailed enough to poll for info for writing":
"yes". This script is that harvest, and --check is the format gate the scout output is
tested against BEFORE six agents produce six files in the wrong shape.
"""
import os, re, sys, glob, csv, json, subprocess, unicodedata
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import date_vocab                # the date field's vocabulary and its EDTF (2026-10-12)

# For the context dates (the Fable review's finding 4, 2026-10-12): month names; a fact that states a state, not an act
# («[ĝenerala]» wanted); the items not told in the order of their pages, from profiles/CHRONOLOGY.tsv
MONTHS = r"(?:januar|februar|mart|april|maj|juni|juli|aŭgust|septembr|oktobr|novembr|decembr)on?"
STATE = re.compile(r"\s*(?:\([^)]*\)\s*)?(?:(?:Li|Ŝi|Ĝi|Ili|\w+) )?(?:estis|estas) (?!\w+(?:it|int)a?j?n?\b)", re.I)   # «estis elektita / mortinta» are events
# An office held is not a state: undated, it is «[sen dato]» (the editor, 2026-10-12); the states check spares it (2026-10-13).
OFFICE = re.compile(r"(?:unu el (?:la )?(?:\w+ )?|la |\w+ )?(?:honora |vic-?)?"
                    r"(?:sekretari|prezidant|direktor|membr|redaktor|kasist|delegit|komitatan|estraran)", re.I)
def _not_chronological():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza",
                     "profiles", "CHRONOLOGY.tsv")
    if not os.path.exists(p): return set()
    rows = csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t")
    return {r["item"] for r in rows if r.get("chronological", "").strip().lower() == "no"}
NOT_CHRONOLOGICAL = _not_chronological()
def _fact_keys():
    """NAMES-REGISTER.tsv rows of relation «fact key», status «confirmed»: NAME as written -> (surname, qualifier)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza",
                     "profiles", "NAMES-REGISTER.tsv")
    if not os.path.exists(p): return {}
    out = {}
    for r in csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r.get("relation") == "fact key" and (r.get("status") or "").startswith("confirmed"):
            m = re.fullmatch(r"\s*(.+?)\s*\(([^)]+)\)\s*", r["main_form"])
            if m: out[r["name"].strip()] = (m.group(1), m.group(2))
    return out
FACT_KEYS = _fact_keys()
def _contrib_dates():
    """CONTRIBUTORS.tsv's «date» column (the Fable review's finding 5, the editor 2026-10-12): item -> [(from, to,
    date)] for contributions whose own date is known (an essay first printed earlier than the volume)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza",
                     "profiles", "CONTRIBUTORS.tsv")
    out = defaultdict(list)
    if os.path.exists(p):
        for r in csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            if (r.get("date") or "").strip() and r["pdf_from"].isdigit() and r["pdf_to"].isdigit():
                out[r["item"].strip()].append((int(r["pdf_from"]), int(r["pdf_to"]), r["date"].strip()))
    return out
CONTRIB_DATES = _contrib_dates()
def _events():
    """EVENT-CALENDAR.tsv as (phrase pattern, first day, last day), for dates written relative to an event («dum la unua
    mondmilito», «post la kongreso de Bulonjo»: the date vocabulary's event forms; the editor 2026-10-12,). Days «1905-08-05/12» and «1906-08-28/09-02» are short for the last day."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "published", "heterophony-resources", "geniza",
                     "profiles", "EVENT-CALENDAR.tsv")
    out = []
    for l in (open(p, encoding="utf-8") if os.path.exists(p) else []):
        x = l.rstrip("\n").split("\t")
        if l.startswith("#") or x[0] == "event" or len(x) < 4: continue
        # the days only: a note after them in the field («1908-08-15/22 (or 16)», read as the last day «22 (or 16)», stopped
        # the harvest 2026-10-22 on Zakrzewski's «post la kongreso de Dresdeno»)
        a, _, b = (x[3].split() or [""])[0].partition("/")
        hi = (a[:8] + b if len(b) == 2 else a[:5] + b if len(b) == 5 else b) if b else a
        out.append((re.compile(x[1], re.I), a, hi))
    return out
EVENTS = _events()
def resolved(datefield):
    """A date in an event form, resolved from the calendar (a date_vocab.Date with bounds), else None."""
    try: d = date_vocab.parse(datefield)
    except ValueError: return None
    if d.kind != "event": return None
    return next((date_vocab.resolve(d, lo, hi) for rx, lo, hi in EVENTS if rx.search(d.phrase)), None)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(REPO, "published", "heterophony-resources", "geniza")
SRC = os.path.join(GEN, "profiles", "by-source")
OUT = os.path.join(GEN, "profiles")
OUT_BANNER = "Ekster la amplekso laŭ la registro de amplekso"   # tools/dowse-full-roster.py reads this banner

# THE BROTHER DISAMBIGUATOR, added 2026-09-06.
#
# The venture's hardest recurring error is the same-surname homonym: FIVE Postnikov brothers,
# TWO Milter brothers (Fritz the Kifintern secretary and Philippe, arrested with him), three
# Schmidts, two Lorenzes, Drezen versus Hilda Dresen. Every scout brief now carries the rule
# «never write MILTER bare — write MILTER (Fritz) or MILTER (Philippe)».
#
# A scout obeyed it and the gate rejected 48 of its lines, because the disambiguator sat
# between the closing sigil and the year. **The gate was punishing the instruction the brief
# had given** — the same failure as the guillemet and novelty-annotation relaxations below.
#
# So: accept `- $$$ MILTER (Fritz) $$$` and KEEP the qualifier on the line, but KEY THE
# PERSON ON THE SURNAME ALONE. All Milters stay in one profile — which is what makes the two
# brothers visible side by side — while every individual line says which one it is. Splitting
# them into separate profiles would hide exactly the confusion the rule exists to expose.
FACT = re.compile(r"^- \$\$\$ (?P<who>[^$]+?) \$\$\$(?: *\((?P<qual>[^)]{1,40})\))? \*\*(?P<year>[^*]+)\*\* · (?P<rest>.+)$")
CONF = {"✅", "📄", "📣", "⚠", "❓"}   # 📣 relays what the source says of others (the editor 2026-10-13); 📄 its older form, shown as 📣

def parse(line):
    r"""-> (WHO, year, fact, source, themes, confidence) or (None, reason).

    The person is carried IN THE LINE, between the two sigils, not by an enclosing
    heading (editor's ruling, 2026-09-04: `- $$$ NAME $$$ **<date>**`). A fact line is
    therefore self-contained: it can be moved, reordered or copied between files without
    losing its subject, and `grep '^- \$\$\$ TROMPETER'` returns one person's whole
    corpus in a single call. A fact about two roster people is written twice."""
    m = FACT.match(line.rstrip())
    if not m:
        return None, "does not match `- $$$ NAME $$$ **<year>** · fact · source · [theme] · conf`"
    parts = [p.strip() for p in m.group("rest").split(" · ")]
    if len(parts) < 4:
        return None, f"needs 4 fields after the year (fact · source · theme · confidence); got {len(parts)}"
    fact, source, theme, conf = parts[0], " · ".join(parts[1:-2]), parts[-2], parts[-1]
    # 2026-09-12: also accept the side-specific codes [E1]–[E8] / [I1]–[I8] from
    # SCOUT-THEMES-BY-SIDE-2026-09-10.md, the erasure typology [X1]–[X11], and the ledger's [B1]–[B9]
    # adjudication codes — the Belga Sonorilo scouts used all three as themes.
    # «[?]»: no theme matched (the editor 2026-10-11: no-match lines stay [?] rather than fall back to [G])
    if not re.fullmatch(r"(\[(?:[A-Z]+|[EIXB][0-9]{1,2}|\?)\])+", theme):
        return None, f"theme field malformed: {theme!r} (want e.g. [B], [B][BIO], or [I1][X])"
    # The confidence field is `<mark>` or `<mark> (why)`. The gloss is OPTIONAL and KEPT.
    #
    # It was originally required to be a bare mark. The first six scouts ignored that and
    # wrote «(four sources conflict; Künzli does not adjudicate)» — and they were right:
    # the ground of a doubt is worth more than the doubt. Rejecting 27 such lines would have
    # discarded exactly the reasoning the venture wants preserved. The gate now takes the
    # mark from the head of the field and carries the gloss through to the harvested profile.
    # The gloss may be wrapped in markdown emphasis — `(why)`, `*(why)*`, `📄 _(why)_` — because
    # scouts write prose and italicise asides. Rejecting the italic form would discard the same
    # reasoning the plain form was relaxed to keep (2026-09-05, second relaxation, same lesson).
    # THIRD RELAXATION, 2026-09-05, and the same lesson a third time. Two scouts wrote the gloss
    # in GUILLEMETS — «why» — not parentheses, because « » is the venture's own quotation convention
    # and appears on every second line of every scout file. Eleven lines were rejected, and they were
    # the richest in that file: Kofman glossing Vashti's killing as a pogrom «segun la konocata maniero
    # di la sovaja Scyti», and the appeal describing Yushmanov as «collaborateur de Nia standardo».
    # Rejecting a fact because its ANNOTATION used the house quote-mark is the gate serving itself
    # rather than the corpus. Accept , « » and " " alike.
    # FOURTH RELAXATION, 2026-09-06 — THE NOVELTY ANNOTATION.
    #
    # The editor issued a standing rule today: ** —
    # because the venture twice announced as discoveries things it already held (Milter's dossier,
    # 41 fact lines deep; the 1917 de Beaufront paralysis, on file five days). A scout re-briefed
    # mid-run promptly did the right thing and started tagging every line with what it does to the
    # existing record: `⟳ CONFIRMS mondo-periodicals-2026-09-05.md`, `⟵ NEW (the existing file
    # lists only Hiestand and Denzler)`, `⟳ CLOSES open item 1 of …`.
    #
    # The gate then rejected 60 lines for it. **That is the gate punishing exactly the behaviour
    # the editor just asked for**, which is the same mistake the guillemet relaxation was written to
    # stop. So: accept a trailing `⟳` / `⟵` / `⟶` annotation after the mark, with or without a
    # bracketed gloss, and CARRY IT THROUGH to the harvested profile — a fact's relation to the
    # existing record is part of the fact's value, not decoration.
    # SIXTH RELAXATION: a scout wrote `📄 (why) ⟳ CONFIRMS file` — gloss AND a second
    # mark AND a novelty tag. Strip any stray second confidence mark before the gloss test.
    conf = re.sub(r"\s*([⟳⟵⟶])\s*", r" \1 ", conf).strip()
    # VOICE AND DOUBT (the editor 2026-10-13): a reader gives the voice (the author acts, 📣 the source relays;
    # 📄 the older 📣) and, where there is one, a doubt (the source doubts, ❓ whose fact it is is uncertain):
    # «📣 (why)»: two orthogonal flags in one field (the editor
    #). The doubt is lifted off here, before the sixth relaxation below could strip it (it did, silently,
    # until 2026-10-13), and put back after the voice; at most one of each.
    doubt = None
    m_vd = re.match(r"^(?P<v>[✅📄📣])\s+(?P<d>⚠(?:\s+❓)?|❓(?:\s+⚠)?)(?P<rest>(?:\s+.*)?)$", conf)   # and ❓ are orthogonal too
    if m_vd:
        if re.match(r"^\s*[✅📄📣⚠❓]", m_vd.group("rest")):
            return None, f"confidence: at most one voice (✅ 📣), one ⚠ and one ❓; got {conf!r}"
        doubt, conf = re.sub(r"\s+", " ", m_vd.group("d")), (m_vd.group("v") + m_vd.group("rest")).strip()
    conf = re.sub(r"^([✅📄📣⚠❓])\s+[✅📄📣⚠❓]\s+", r"\1 ", conf)
    # SEVENTH RELAXATION: scouts also append a HANDLING marker — `*recorded, not expanded*`
    # — when a brief told them to note something without pursuing it. That is compliance, not
    # malformation; keep it as the gloss rather than rejecting the line.
    m_h = re.match(r"^(?P<mark>[✅📄📣⚠❓])\s+⛔\s*[*_]{0,2}(?P<why>.*?)[*_]{0,2}$", conf)
    if m_h:
        why_h = m_h.group("why").strip()
        conf = f'{m_h.group("mark")} (⛔ {why_h})' if why_h else f'{m_h.group("mark")} (⛔ recorded, not expanded)'
    m_nov = re.match(r"^(?P<head>\S+(?:\s+[*_]{0,2}[(«\"].+?[)»\"][*_]{0,2})?)\s+"
                     r"(?P<nov>[⟳⟵⟶]\s+.+)$", conf)
    novelty = None
    if m_nov:
        conf, novelty = m_nov.group("head"), m_nov.group("nov").strip()
    # FIFTH RELAXATION, same day, same lesson: scouts also gloss with BARE EMPHASIS —
    # `**THE OFFICE, IN PRINT, IN THE MOVEMENT'S OWN PAPER**` — with no bracket at all.
    # Eighteen lines, and they are the ones the scout thought mattered most. Accept it.
    m_em = re.match(r"^(?P<mark>\S+)\s+[*_]{1,2}(?P<why>.+?)[*_]{1,2}$", conf)
    if m_em and m_em.group("mark") in CONF:
        conf = f'{m_em.group("mark")} ({m_em.group("why").strip()})'
    # EIGHTH RELAXATION, 2026-09-12 (editor's go): the 2026-09-10 Belga Sonorilo Ido-years scout
    # wrote the gloss as BARE PROSE with no bracket at all — «primary seen», «📄 the source asserts
    # it», «single-sourced, hostile **why it matters**» — 750+ lines, the whole Ido-years read,
    # silently unharvested for two days. Same lesson as relaxations 3–5: the mark is the datum, the
    # rest is the gloss. If the field STARTS with a mark, take the mark and keep everything after it.
    m_bare = re.match(r"^(?P<mark>[✅📄📣⚠❓])\s+(?P<why>[^(«\"*_].*)$", conf)
    if m_bare and not re.match(r"^[✅📄📣⚠❓]\s+[*_]{0,2}[(«\"]", conf):
        conf = f'{m_bare.group("mark")} ({m_bare.group("why").strip()})'
    m2 = re.match(r"^(?P<mark>\S+)(?:\s+[*_]{0,2}[(«\"](?P<why>.+)[)»\"][*_]{0,2})?$", conf)
    if not m2 or m2.group("mark") not in CONF:
        return None, f"confidence must START with one of {' '.join(sorted(CONF))}, optionally followed by ' (why)'; got {conf!r}"
    why = m2.group("why")
    conf = m2.group("mark") + (f" ({why})" if why else "") + (f"  {novelty}" if novelty else "")
    if doubt: conf = m2.group("mark") + " " + doubt + conf[len(m2.group("mark")):]
    if not source or source in ("—", "-"):
        return None, "empty source/locator — a fact with no locator does not go in"
    who = m.group("who").strip()
    if not who or who != who.upper():
        return None, f"name field must be present and UPPER CASE; got {who!r}"
    # THE NAMES REGISTER'S FACT KEYS (the Fable review's finding 7, the editor 2026-10-12): a NAME written
    # against the rule (a given name, an initial, a slug) is mapped to the surname and its qualifier
    qual = m.group("qual")
    if who in FACT_KEYS and not qual:
        who, qual = FACT_KEYS[who]
    # The brother-qualifier rides ON THE FACT, not on the person key — see the FACT note above.
    if qual:
        fact = f"**({qual.strip()})** {fact}"
    return (who, m.group("year").strip(), fact, source, re.findall(r"\[([A-Z]+|[EIXB][0-9]{1,2})\]", theme), conf), None

# NAME CANONICALISATION — added 2026-09-05 after the deliverable was found FRAGMENTING PEOPLE.
#
# The per-person index is the deliverable. On 2026-09-05 it silently produced FOUR files for two men:
# `SÉBERT` → s-bert.md (19 facts) beside `SEBERT` → sebert.md (1), and `DE BEAUFRONT` → de-beaufront.md
# beside `BEAUFRONT` → beaufront.md. A slug built by deleting every non-[a-z0-9] character turns an
# accent into a hyphen, so one man's corpus splits on whether a scout typed the acute. Nobody polling
# `beaufront.md` would have known the other file existed.
#
# Fix in two parts: fold diacritics before slugging (mechanical, safe), and apply an EXPLICIT alias
# table (never a heuristic). The table is deliberately conservative -- THE POSTNIKOVS ARE DIFFERENT
# MEN and must never be merged, which is exactly why prefix-matching or fuzzy-joining is refused here.
ALIASES = {
    "BEAUFRONT": "DE BEAUFRONT", "DE-BEAUFRONT": "DE BEAUFRONT",   # hyphen form used by some scouts (2026-09-12)
    "SEBERT": "SÉBERT",
    "WAHL": "DE WAHL", "DE-WAHL": "DE WAHL",   # hyphen form slugged to the same file and clobbered it (Brief 4 scout, 2026-09-12)
    "DOMBROVSKI": "DAMBRAUSKAS", "DOMBROVSKIJ": "DAMBRAUSKAS",
    "DOMBROWSKI": "DAMBRAUSKAS", "JAKŠTAS": "DAMBRAUSKAS", "DABRAUSKAS": "DAMBRAUSKAS",
    "KABE": "BEIN", "BEIN/KABE": "BEIN",
    "SAUSSURE": "DE SAUSSURE",
    "ĈAJKOVSKAJA": "CHAJKOVSKAJA", "CAJKOVSKAJA": "CHAJKOVSKAJA",
    "KORĴENKOV": "KORZHENKOV", "KORJENKOV": "KORZHENKOV",
    "MERAY": "MÉRAY", "MOBUSZ": "MÖBUSZ", "KUNZLI": "KÜNZLI",
    "WASNIEWSKI": "WAŚNIEWSKI", "ITO": "LUDOVIKITO", "ITÔ": "LUDOVIKITO",
    "SATUNOVSKI": "ŜATUNOVSKIJ", "SATUNOVSKIJ": "ŜATUNOVSKIJ", "ŜATUNOVSKI": "ŜATUNOVSKIJ", "RUBLEV": "RUBLOV",   # two Satunovskij profiles found 2026-09-13; the 1923 page prints Ŝatunovskij; Rublev = the S. Rublov of OV III.5
    "TWOMBLY": "TWOMBLEY",   # John Fogg Twombly of Brookline; the profile stem is twombley (2026-09-14)
    "ULIANOV": "ULYANOV",   # Kharkiv Ido lexicographer, two spellings (Brief 14, 2026-09-14)
    "RIC BERGER": "BERGER",
    "WALRISAUN": "WALTISBÜHL",   # Neves's facsimile of the Progresido notice, OCR «Anton WaLrisaun, 36, Bahnhofstrasse Zurich»; Progreso 1910-02 prints «Anton WALTISBUHL, 36, Bahnhofstrasse Zurich» (profiles/waltisbuhl.md); the editor 2026-10-14 → approved (identifications live outside the lines)
    # the redowse's NOMOs, 2026-10-15 (the editor; dowse/<source>/align-names-2026-10-15*.md; one profile each, the
    # twins had two): Itô Kanzi is Ludovikito (eo.wikipedia «Ito Kanzi», saved in sources/ludovikito-inventory-2026-09-14/:
    # «en la Esperanto-movado konata kiel Ludovikito»); Neves's «P. ALBERG, Surbrunsgatan 97, Stokholm» is the Stockholm
    # AHLBERG; Korĵenkov's «hispana pastro Antonio Guinard» is EdE 1933's «Guinart (ginar) Antonio, hispano: pastro
    # katolika»; Korĵenkov's «germanino Marie Henkel», poet with Privat, Schulhof and Belmont, is Marie Hankel (Dresden,
    # «Sableroj»); «Julio Mangada Rosenorn» (Korĵenkov PDF 116) is the «kolonelo Julio Mangada» of PDF 89
    "ITÔ KANZI": "LUDOVIKITO", "ITO KANZI": "LUDOVIKITO", "ALBERG": "AHLBERG", "P. ALBERG": "AHLBERG", "GUINARD": "GUINART",
    "HENKEL": "HANKEL", "MANGADA ROSENORN": "MANGADA", "MANGADA ROSENÖRN": "MANGADA",
    # Auguste Capé, ps. Auguste Montrosier (EdE 1933: «Capé (kape) Auguste, (ps. Auguste Montrosier), franco, kapitano»;
    # Ruslanda Esperantisto 1905 n-ro 3-4, PDF 23: «Aŭgusto Cape—Montrosier, … sub la modesta nomo de Alĝera Kapitano
    # Cape»); the editor, 2026-10-17 23:4x (CAPE and CAPÉ fold to one slug already)
    "CAPE-MONTROSIER": "CAPÉ", "CAPÉ-MONTROSIER": "CAPÉ", "CAPE MONTROSIER": "CAPÉ", "CAPÉ MONTROSIER": "CAPÉ", "MONTROSIER": "CAPÉ",
    # Georges Kolowrat, in Russian Kolovrat-Červinskij (Ruslanda Esperantisto 1906 n-ro 11, PDF 24: «Коловрат-Червинский»
    # for its collaborator; eo.wikipedia «Georges Kolowrat»); 2026-10-18, the walk-through (the editor)
    # the variant spellings the older roster files keep, which no dowse rename reaches (2026-10-18, found by the homograph
    # rule of the fact-text listing): Antoni Grabowski in the Russian spelling; the printer of Ruslanda Esperantisto
    "GRABOVSKI": "GRABOWSKI", "GRABOVSKIJ": "GRABOWSKI", "VEJSBRUT": "WEJSBRUT",
    "KOLOVRAT": "KOLOWRAT", "KOLOVRAT-ČERVINSKI": "KOLOWRAT", "KOLOVRAT-ĈERVINSKI": "KOLOWRAT", "KOLOVRAT-ČERVINSKIJ": "KOLOWRAT", "KOLOWRAT-ĈERVINSKIJ": "KOLOWRAT",
    # twins merged 2026-09-20 20:56 (editor; difflib scan of the 949 stems): same person, variant spellings
    "LA FONTAINE": "LAFONTAINE", "BLUMENTAL": "BLUMENTHAL", "VAN LANGENMEERSCH": "VAN LANGERMEERSCH", "HOUZEAU DE LEHAYE": "HOUZEAU DE LEHAIE",
    "SEYNAVE": "SEYNAEVE", "S ROSENBERGER": "ROSENBERGER", "ROZENBERGER": "ROSENBERGER", "LEIZEROWICZ": "LEJZEROWICZ", "CHAKHOTIN": "CAHOTIN",
    "GALLARD": "GALARD", "L'ESPÉRANTISTE": "LESPERANTISTE", "PUJULA I VALLÈS": "PUJULA Y VALLES", "PUJULÀ I VALLÈS": "PUJULA Y VALLES", "PUJULA Y VALLÈS": "PUJULA Y VALLES", "PUJULÀ Y VALLÈS": "PUJULA Y VALLES", "PUJULA": "PUJULA Y VALLES", "P AHLBERG": "AHLBERG", "P. AHLBERG": "AHLBERG", "OSTROVSKI": "OSTROVSKIJ", "SHMURLO": "ŜMURLO", "SZMURLO": "ŜMURLO", "TSCHESCHICHIN": "ČEŠIXIN", "ĈEŜIĤIN": "ČEŠIXIN", "EDGAR DE WAHL": "DE WAHL", "LEO WIENER": "WIENER", "A MATEJKA": "MATEJKA", "OTTO JESPERSEN": "JESPERSEN", "PUJULA I VALLES": "PUJULÀ Y VALLÈS",   # full-name sigils surfaced by the B1 error fix 2026-09-14 (contract: ONE surname per pair); folded, not re-sigilled
    "EVSTIFEIEFF": "EVSTIFEJEV", "EVSTIFEJEFF": "EVSTIFEJEV", "EVSTIFEEV": "EVSTIFEJEV", "JEVTIFEJEV": "EVSTIFEJEV",   # three profiles for one man found 2026-09-13 (35+8+12 lines); the 1914 «N. O.» censor carries a ❓ qualifier on the line, not a separate key
    # Brief 16 (2026-09-14): the missing pre-1908 profiles — the spellings the sources use for the new keys (diacritic-only
    # variants such as SUSSMUTH/SÜSSMUTH, SVACINA/SVAČINA, ROSICKY/ROSICKÝ already fold by slug and need no row)
    "ANTTILA": "ANTILLA", "ANTTILLA": "ANTILLA",   # EdE «Anttila», the OGE rolls «Antilla», the 1922 list «Anttilla»
    "FRIDERI": "FRIDORI", "FRIDÖRI": "FRIDORI",   # EdE «Fridöri», the 1922 list «Frideri»
    "UITTERDYCK": "UITTERDIJK", "SEPULVEDA CUADRA": "SEPÚLVEDA", "SEPULVEDA-CUADRA": "SEPÚLVEDA",
    "KRESTANOV": "KRESTANOF", "KRESTANOFF": "KRESTANOF", "GUMINSKI": "GUMINSKIJ", "GUMINSKY": "GUMINSKIJ",
    "POLGAR-POLITZER": "POLGAR", "POLGÁR": "POLGAR", "MIKOŁAJSKI": "MIKOLAJSKI", "SOLOVJOV": "SOLOVJEV",
    "SHCHELOKOV": "ŜĈELOKOV", "BEIRAKH": "BEJRAĤ", "OREŜKOFF": "OREŜKOV", "ORESHKOV": "OREŜKOV", "ORESKOFF": "OREŜKOV",
    "TOEROEK": "TÖRÖK", "BUENEMANN": "BÜNEMANN", "OCONNOR": "O'CONNOR", "O’CONNOR": "O'CONNOR",
    "BREMON": "BREMON Y MASGRAU", "BREMON MASGRAU": "BREMON Y MASGRAU", "COUTO": "COUTO FERNANDES", "SKEEL": "SKEEL-GIÖRLING", "SKEET-GIÖRLING": "SKEEL-GIÖRLING",
}

# SAME-SURNAME PERSONS, 2026-09-14 (editor
#). The design above stands — one profile per surname, the qualifier on every line — but a
# profile that holds two or more distinct people is RENDERED IN SECTIONS, one per person, so that the fusion
# is visible and readable instead of interleaved by year. A person is recognised by the first token(s) of the
# line's qualifier; lines with no qualifier or an unlisted one fall into an «(unassigned)» section at the end
# — which is the to-do list for the next qualifier pass. Add a surname here when a fusion is found.
PERSONS = {
    "MEIER": [("Ludwig Emil Meier (München, 1847–1916)", ("L. E.", "Ludwig Emil", "L.E.", "Ludwig", "L.,")),
              ("Henri Meier (Luxembourg)", ("Henri", "H., Luxembourg", "H. Luxembourg", "H.,")),
              ("Jeanne Meier (Luxembourg)", ("Jeanne",)),
              ("Georg Meier (Rapperswil)", ("G., Rapperswil", "Georg", "G. Rapperswil")),
              ("a Meier of Nürnberg (ten subscriptions in the 1894 roll)", ("Nürnberg", "Nurnberg", "Nuremberg")),
              ("other / unidentified Meiers (the LK «Merer» of 1908; the Swiss Idist of 1926)", ("unidentified", "Swiss", "other"))],
    "RICHARDSON": [("Gilbert H. Richardson (Newcastle, the Idist)", ("G. H.", "G.H.", "Gilbert")),
                   ("Abbé Austin Richardson (Brussels, 1843–1913)", ("Abbé", "Abato", "Austin", "priest", "Belgian"))],
    "LORENZ": [("Richard Lorenz (Zürich/Frankfurt, the Uniono president)", ("Richard", "R.,", "Zürich")),
               ("F. V. Lorenz (Prague → Brazil, 1872–1957)", ("F. V.", "F.V.", "František", "Frantisek", "Brazil", "Brasil", "Fr. Vl.", "Fr. Vladimír", "Vladimír", "F., Zbislav", "F.,", "Lorenc")),
               ("C. Lorenz (Leobschütz; factory manager; UEA delegate 1913)", ("C.,", "C.", "Leobschütz"))],
    # two Stroeles of Neuchâtel: Hermann the astronomer (LK 1909; † 14 Mar 1921 aged 41) and Georges the teacher
    # (ps. Goso, b. 1879; LK 1912; the EdE entry) — split 2026-09-14 after T7 found the EdE row was Georges
    "STROELE": [("Hermann Stroele (Neuchâtel, astronomer, LK 1909, † 1921)", ("Hermann", "H.", "H.,")),
                ("Georges Stroele (Neuchâtel, teacher, ps. Goso, LK 1912)", ("Georges", "George", "G.", "Goso")),
                ("a Stroele of Neuchâtel, surname only — which brother undetermined", ("Neuchatel, surname only", "Neuchâtel, surname only", "surname only"))],
    # two Postnikovs, brothers: Fjodor A. («Captain Post», b. 1872 Kovno; Ussuri 1891, Vladivostok, USA 1915–, † 1952)
    # and Aleksandr A. (the captain, Ruslanda Ligo president 1909–11, the 1911 trial) — sectioned 2026-09-15 after
    # Brief 19 C batch 11 met «F. A. Postnikov, Berkeley, malnova rusa Esperantisto» (1915)
    "POSTNIKOV": [("Fjodor A. Postnikov («Captain Post», the engineer; Vladivostok → USA, 1872–1952)", ("Fjodor", "F. A.", "F.A.", "F.", "Fyodor", "Fedor", "Feodor", "the military engineer", "F.A.,")),
                  ("Aleksandr A. Postnikov (the captain; Ruslanda Ligo president 1909–11, tried 1911)", ("Aleksandr", "A. A.", "A.A.", "A.", "the captain")),
                  ("V. Postnikov (Kronstadt naval technical school, Adresaro 1892), S. Postnikov (1897), B. Postnikov (Samara, the kumis exporter 1899) and undetermined Postnikovs", ("V.", "S.", "B.", "which", "undetermined"))],
    # father and son: Ivan Markoviĉ Lojko (Vilna, LE 1890–95, Tolstoy translator; † 23 Jun 1905 aged 49, RE obituary)
    # and Vsevolod Ivanoviĉ («Vs. L–o», LIU 1903–04, RE 1905–10) — the profile merged them; sectioned 2026-09-15
    "LOJKO": [("Ivan Markoviĉ Lojko (Vilna; La Esperantisto 1890–95; † 23 Jun 1905)", ("Ivan", "I. M.", "I.M.", "I.", "the father")),
              ("Vsevolod Ivanoviĉ Lojko (the son; LIU 1903–04, Ruslanda Esperantisto 1905–10)", ("Vsevolod", "Vs.", "V. I.", "V.I.", "the son", "V."))],
    # --- the U26 splits (Miles 2026-09-15 01:01; editor 01:04) + PARKER + LAMBERT ---
    "BERNOT": [("Lucien Bernot (Fontenay-sous-Bois; composer; SFPE committee 1903; † 1906)", ("Lucien", "L.", "L.,")),
               ("Gaëtan Bernot (Fontenay-sous-Bois; registrant 1899–1900, introduced by L. Bernot)", ("Gaëtan", "Gaetan", "G."))],
    "DESHAYES": [("René Deshayes (Chaumont / Sens; professor; music for «L'Espero» 1903)", ("René", "Rene", "R.", "M. R.", "Sens", "Chaumont")),
                 ("Dr Deshayes (Alger, Institut Pasteur; registrant 1902)", ("Alger", "Doktoro", "Dr Deshayes", "the Alger"))],
    "KIMEL": [("Dr S. Kimel (Bucharest; physician; RES co-founder 1907; 1875–1930)", ("Dr S.", "Dr S", "S.", "E.", "Bucharest", "Dr")),
              ("F-ino I. Kimel (Bucharest, calea Mosilor 300; registrant 1908)", ("F-ino I.", "I.")),
              ("F-ino R. Kimel (Bucharest, calea Grivitei 79; registrant 1908)", ("F-ino R.", "R."))],
    "PRIOU": [("General Priou (Paris; president, Franca Societo Esperanto-Ruĝa-Kruco 1908–10; the OGE roll man)", ("Generalo", "General", "Gen.")),
              ("Maurice Priou (Fontenay-sous-Bois; registrant 1901)", ("Maurice", "M."))],
    "LAMBERT": [("Charles Lambert (Dijon; professor, dean; editor of «Esperanto» 1905; LK 1909–10)", ("Ch.", "Charles", "CHARLES", "Ch.,", "Prof. Ch.", "Prof. Charles", "Dijon")),
                ("Daniel Henry Lambert (Penge/London; solicitor; BEA founder 1904; Shakespeare translator; † 1930)", ("D. H.", "D.H.", "Daniel")),
                ("the Belgian Finance-Ministry collector (the Lemaire charge of 1914)", ("the Belgian collector", "the collector", "Belgian")),
                ("Louis Lambert (Jumet; glassworks master)", ("LOUIS", "Louis"))],
    # the album's «St. Atanasoff, Plovdiv, redaktoro de Rondiranto» (U25b 2026-09-15): three Bulgarian Atanasovs on one key
    "ATANASOV": [("St. Atanasoff of the 1906 album (Plovdiv, Rondiranto — Sterio or Georgi? ❓)", ("St.,", "St., Plovdiv", "St.")),
                 ("Sterio (Ŝterju) Atanasov (Varna; treasurer of «Frateco» 1904; national committee 1906)", ("Sterio", "Ŝterju", "Shterju")),
                 ("Georgi Atanasov (b. 1881 Nova Zagora; Varna → Plovdiv → Sofia; Rondiranto; the 1910 dictionary)", ("Georgi", "G.,", "G. ", "Georgij", "G.")),
                 ("Atanas D. Atanasov, «Ada» (b. 1892, Sofia; Rememoroj de esperantisto 1925)", ("Atanas D.", "At. D.", "A. D.", "A.D.", "Ada", "«Ada»")),
                 ("other Atanasovs (Bulgaria)", ("others", "other", "unassigned"))],
    "PARKER": [("Patrick Parker (Co. Wexford; priest; IKUE president 1913; 1869–1948)", ("Patrick", "Pastro Patrick", "Rev.", "P.")),
               ("Stephen Parker (Goole; group founder 1906; UEA delegate)", ("Stephen", "Stephens")),
               ("Edward Parker (Holmfirth / Shipley; Yorkshire Federation; † 8 Mar 1915)", ("Edward",)),
               ("F-ino Parker (Shipley; Yorkshire Federation vice-president 1911–15)", ("F-ino", "Shipley Miss Mary", "Shipley")),
               ("G. H. Parker (1916)", ("G. H.", "G.H.")),
               ("Fred Parker (Burnley; joined 1908; † 1974)", ("Fred",))],
    # --- Brief 22 (Miles, 2026-09-15): the eight two-men surnames Group C left «with qualifiers, unresolved» ---
    # LEMAIRE: Commandant Charles (Brussels; Belga Ligo president; Ido 1908; the 1914 charge; † 21 Jan 1926) and
    # René (Épernay; SFPE pioneer; Adresaro introducer of 47; Ido 1908). The shared row is listed FIRST so that the
    # mixed qualifiers («Charles or René — undetermined», «René 47 + Charles 5», «both …») do not fall to Charles by prefix.
    "LEMAIRE": [("both Lemaires, or undetermined (a fact naming the two, or a scout who could not tell)", ("both", "Charles or René", "René 47", "Charles and René", "undetermined")),
                ("Commandant Charles Lemaire (Brussels; Belga Ligo president; Ido from 1908; 1863–1926)", ("Charles", "CHARLES", "Ch.", "Kom.", "Komandanto", "Commandant", "Major", "C.")),
                ("René Lemaire (Épernay; SFPE pioneer, Adresaro introducer; Ido from 1908)", ("René", "RENÉ", "Rene", "R.", "R.,", "Épernay", "Epernay")),
                ("the Lemaire family of Épernay beside René (André; Mme Victor — SFPE roll 1902)", ("the Épernay family",))],
    # (the Épernay family: its lines are copied to René, FAMILIES below)
    "COX": [("Major-General George Cox (London; LK 1909; † 27 Oct 1909)", ("Major-General", "Major General", "General", "George Cox", "London")),
            ("George J. Cox (London Federation president 1912; BEA vice-president 1911–16)", ("George J.", "G. J.", "G.J."))],
    "HARVEY": [("Col. George B. M. Harvey (New York; North American Review; Delegation Committee; KK 1909–11; 1864–1928)", ("Col.", "George", "G.,")),
               ("Edward K. Harvey (Boston, Perkins Institution)", ("Edward K.", "EDWARD K.", "E. K.", "E.K.")),
               ("William Harvey (Edinburgh; club vice-president 1910; Skota Federacio; BEA delegate councillor 1909–12)", ("William", "Wm.", "W.,", "W. Harvey"))],
    "SCHMIDT": [("Christian Schmidt (Nürnberg; La Esperantisto publisher 1889–90; Idiom Neutral 1894; Ido 1908; 1849–1909)", ("Christian", "CHRISTIAN", "Chr.", "CHR.", "Chrystian", "Nürnberg")),
                ("Prof. Dr Adolf Schmidt (Potsdam, Telegrafenberg observatory; LK 1905–22; b. 23 Jul 1860)", ("Prof. Ad.", "Prof. A.", "Prof. Adolf", "Adolf", "Ad.,", "Ad.", "A.,", "A.", "D-ro A.", "Potsdam", "Dr, Berlin", "Berlin")),
                ("Dr Miloslav Schmidt (Prague; Svaz general secretary 1910–12)", ("Mil.", "Miloslav")),
                ("Paul Schmidt (Dresden; league president 1911)", ("Paul",)),
                ("Generalmajor Schmidt (Germany; Red Cross committee vice-president 1910)", ("generalmajoro", "Generalmajor")),
                ("J. Schmid (Bern; 1913 congress president)", ("J.,", "J. Schmid", "Bern")),
                ("Friedrich Schmidt (Nürnberg schoolboy at Christian's address, 1891–92)", ("Friedrich",))],
    "KÜHNL": [("Eduard Kühnl (Prague; redaktoro of Časopis českých esperantistů; LK 1905–22 (Boulogne roll, ED 1; header said 1908 until 2026-09-18), Akademio 1920; 1884–)", ("Eduard", "Ed.", "E.", "the redaktoro", "Praha", "Prague")),
              ("Ing. Fr. Kühnl (Prague; Klub vice-president 1903; engineers' Svaz)", ("Ing.", "Fr.", "Fr,", "Frant.", "František"))],
    "MORIN": [("Anselmo Morin (Santa Rosa / Veracruz, Mexico; LK 1905–14; † 1916)", ("Anselmo", "S-ro Anselmo", "A., Veracruz", "A.,", "Veracruz", "Santa")),
              ("C. J. (Chas. J.) Morin (Durban; group secretary 1908, president 1911)", ("C. J.", "C.J.", "Chas.", "Charles J.", "Durban")),
              ("a Morin of Dijon (SFPE adepte 1902; no forename)", ("Dijon",)),
             ("Francis G. Morin (Chicago; AEA vice-president 1906; Illinois secretary to 1910)", ("Francis", "F. G.", "F.G.", "F.-G.", "Morin of Chicago", "Chicago", "Arthur Baker succ."))],
    # GRAU is keyed GRAU-CASAS: the brothers Josep (b. 1888; K.E. secretary; LK 1913) and Jaume (b. 1896; the poet; LK 1926–35)
    "GRAU-CASAS": [("Josep Grau-Casas (Barcelona; Kataluna Esperantisto secretary/director; LK 1913–22; b. 8 Sep 1888)", ("Josep", "Jozefo", "Josefo", "J.")),
                   ("Jaume Grau-Casas (Barcelona; the poet, Kataluna Antologio; LK 1926–35; b. 2 Dec 1896)", ("Jaume", "James"))],
    "PALMER": [("Harold E. Palmer (Verviers; the phonetician, Méthode Palmer; Hythe 1906; 1877–1949)", ("Harold", "HAROLD", "H. E.", "H.E.", "H.", "H.,", "Verviers", "Hythe")),
               ("Wm. Palmer (Bedford editor 1905; Eastbourne group 1912)", ("Wm.", "William", "W.,", "Bedford")),
               ("Godfrey Palmer (USA; † 1912 aged 19)", ("Godfrey",))],
    # --- the 2026-09-18 cleanups (Brief 21 organ 1 § 2; T11 § 9 items 1–2) ---
    # Nikolaj Halle (Espero founder, librarian 1892) vs Miss N. (Nansi) Halle (candidate Jun 1892, efektiva membro Aug 1892, Ligovskaja 4)
    "HALLE": [("Nikolaj Halle (S. Peterburg; Espero founder-member, initiator, librarian 1892)", ("Nikolaj", "N., S. Peterburg", "N.,")),
              ("Nansi Halle (S. Peterburg, Ligovskaja 4; fraŭlino; Espero candidate Jun 1892, efektiva membro Aug 1892)", ("Nansi", "fraŭlino", "Miss", "F-ino"))],
    # three on one key (EdE l.7985–7997): Léon the squadron commander, Marcelle his wife (b. 14 Nov 1859), Louis their son
    "FAUVART-BASTOUL": [("Léon Fauvart-Bastoul (Dijon; squadron commander)", ("Léon", "Leon", "M., advocate", "M.,", "the husband", "Commandant")),
                        ("Marcelle Fauvart-Bastoul (Dijon; his wife, b. 14 Nov 1859; Mme / S-ino)", ("Marcelle", "Mme", "S-ino", "Madame", "the wife")),
                        ("Louis Fauvart-Bastoul (Dijon; their son)", ("Louis", "the son"))],
    # two men (T11 § 9.2): H. Fischer-Galati, publisher and printer, Bucharest («Galati» is in the surname; EdE) and M./Marx Fischer, industrialist, Galați (1904–05)
    # FILIPPOV: three men — split 2026-09-19 after the Ora Libro's Veteranoj entry (A. G., Saratov dentist, Esperantist 1888)
    # landed on a profile built from S. Filippov of Omsk (Ido textbooks, Mondo 1921–23); the 1934 SEU line names both plus Georgij.
    "FILIPPOV": [("Aleksander Gavriloviĉ Filippov (Saratov dentist; Esperantist from 1888; «tute silentas» by 1937)", ("Aleksander", "Aleksandr", "A. G.", "A.G.", "Saratov", "dentist")),
                 ("S. Filippov (Omsk; Klubo Esperanto; Ido textbooks 1921–23)", ("S.", "S.,", "Omsk")),
                 ("Georgij Filippov (Soviet pedagogue, SEU 1934)", ("Georgij", "G.,", "pedagogue"))],
    # SIMON: split 2026-09-19 22:55 — the card's 🟦 on Prof. Otto Simon (Wien; LK 1905–21+, Ora Libro veteran, never Ido) came from
    # the BELGIAN Simon of Ixelles («ta nefatigebla apostolino», Bonveno delegate 1908, taught Ido at the Ixelles Teaching Club 1909):
    # two people, one stem. The Progreso roster's unqualified STATUS line is the Belgian's and stays unassigned until re-keyed.
    "SIMON": [("Prof. Otto Simon (Wien; mathematics; LK 1905–1921+; Delegation delegate for Austria 1907; † 1941)", ("Otto", "O.", "O.,", "Wien", "Vieno", "Prof.", "Vienna")),
              ("the French Simons of the SFPE roll 1902 (a Simon, avocat, Besançon; Paul Simon, Reims)", ("Besançon", "Paul")),
             ("Mlle Clotilde Simon of Ixelles (Bonveno delegate 1908; the «apostolino» who taught Ido at the Ixelles Teaching Club 1909)", ("C.", "C.,", "Clotilde", "F-ino", "Ixelles", "Bonveno", "apostolino", "Mlle", "S-ino"))],
    # BECKER (U25 tier 1, 2026-09-20): two men — Alwin of Kleinzschachwitz (Reform-Esperanto society at Leuben, 1908) and Eduard the priest (EdE: b. 1867, † 1930); distinct from BEKER of Petersburg
    "BECKER": [("Alwin Becker (Kleinzschachwitz; Reform-Esperanto Societo at Leuben bei Dresden, 1908)", ("Alwin", "A.", "Kleinzschachwitz", "Leuben")),
               ("Eduard Becker (Catholic priest, church councillor; 1867–1930; EdE)", ("Eduard", "E.", "pastro", "priest"))],
    "FISCHER": [("Heinrich Fischer-Galati (Galatz → Bucharest; publisher and printer; the EdE entry)", ("Heinrich", "H., of Galatz", "H., of Bucharest", "H.,", "H.", "Henriko", "Galati", "Bucharest", "Bucuresti")),
                ("M. / Marx Fischer (Galați; industrialist 1904; the Adresaro 1905 address-holder)", ("M.,", "M.", "Marx", "industriisto"))],
    # two Trompeters on the 1894 ballot, both point IV: W. H. the Markscheider of Schalke (the paper's funder) and Richard, Kaufmann,
    # Schalke 1892 → Dortmund 1894 (Adresaro XI no. 2054, introduced by [Trompeter]; roll no. 476) — kin undetermined; row added 2026-09-18 (editor)
    "TROMPETER": [("W. H. Trompeter (Schalke, Westfalen; Markscheider; the funder-publisher of La Esperantisto 1892–95; abon. 453)", ("W. H.", "W.H.", "Wilhelm", "W.,", "the funder")),
                  ("Richard Trompeter (Kaufmann; Schalke 1892 → Dortmund 1894; abon. 476; kin of W. H. — son, brother, nephew undetermined)", ("Richard", "R.", "R.,", "Dortmund"))],
}

# FAMILIES AND HOUSEHOLDS (the editor, 2026-10-16,
# approved). A group of relatives with a PERSONS
# row of its own is a household, named for its head, the father by default, where the sources name him («the household of
# Markus Zamenhof», apart from «the household of L. L. Zamenhof»); where they do not, for the member the sources tie it to
# («the Lemaire family of Épernay beside René»). One generation's unit, not a lineage. Its lines are copied to each member
# with a profile, ⟦kopio el SURNAME (the group's qualifier)⟧: surname -> [(the group's qualifier prefixes, [member qualifiers])]
SAYING_KINDS = {"juĝo", "aserto", "karaktero"}   # kinds dated by their saying; an event kind is dated by the event
WHOLE_LIFE_KINDS = {"deveno"}                    # whole-life by kind: undated, «[ĝenerala; laŭ la speco]» (2026-10-16 22:2x)
# whole-life or for a time: the reader's call. Character moved here 23:0x (the editor
#), after the build showed 5 of 8 character lines made whole-life were attitudes held for a time
EITHER_KINDS = {"profesio", "studo", "loĝado", "familio", "sano", "nomo", "karaktero"}
NEVER_GENERAL_EXEMPT = WHOLE_LIFE_KINDS | EITHER_KINDS | {"alia", "samnomo"}   # any other kind is an act, never [ĝenerala]
GENERAL_BY_KIND = []                             # the files of the lines made [ĝenerala] by their kind, for the count
ISSUE_DATED = []                                 # the files of the undated lines a periodical's issue dated (2026-10-17u)
FT_HOMOGRAPHS = []                               # surnames the fact texts use as places or common names (2026-10-18)
FT_OUT = [0]                                     # occurrences ruled out by their context (2026-10-18)
_BPEAPE = {}
def bpeape_titles(word):
    """The periodicals' titles in BPEAPE (bpeape-proofreading/sources/derived/bpeape-entries.tsv, «title») holding the
    word, more than the word alone, the longest first."""
    if not _BPEAPE:
        p = os.path.join(GEN, "..", "bpeape-proofreading", "sources", "derived", "bpeape-entries.tsv")
        _BPEAPE["all"] = [l.split("\t")[2].strip() for l in open(p, encoding="utf-8").read().split("\n")[1:] if l.count("\t") >= 3] if os.path.exists(p) else []
    if word not in _BPEAPE:
        _BPEAPE[word] = sorted({t for t in _BPEAPE["all"] if re.search(rf"\b{re.escape(word)}\b", t, re.I) and t.lower() != word.lower()}, key=len, reverse=True)
    return _BPEAPE[word]
FT_TITLE = re.compile(r"(?:S-ro|Sro|S-ino|Sino|F-ino|D-ro|Dro|Prof\.?|Profesoro|Pastro|Kolonelo|Generalo|Majoro|Kapitano|Leŭtenanto|"
                      r"Sinjoro|Sinjorino|Fraŭlino|Doktoro|Mr\.?|Mrs\.?|Miss|Dr\.?|Rev\.?|Col\.?|Gen\.?|Capt\.?|Hon\.?|Sir|Lady|M\.|Mme\.?|Mlle\.?)\s+$")
class surnames_finder:
    """The surnames of a set as whole words in a text, leftmost and longest first: what
    re.compile(r"\\b(" + "|".join(sorted(map(re.escape, sur), key=len, reverse=True)) + r")\\b").findall gives, without
    the alternation (2026-10-24; the editor, to the fix of the harvest's slow section: the regular expression of
    13,658 surnames run over every dowse line took about 45 minutes of each harvest and of each check). A surname made of
    word characters only matches only a whole run of them, so those are one dictionary lookup per word; the few with a
    hyphen, an apostrophe or a dot keep a small alternation of their own, tried first, as their greater length put them
    first before; a word inside one of their matches is not matched again."""
    def __init__(self, sur):
        self.plain = {s for s in sur if re.fullmatch(r"\w+", s)}
        other = sorted((s for s in sur if s not in self.plain), key=len, reverse=True)
        self.other = re.compile(r"\b(" + "|".join(map(re.escape, other)) + r")\b") if other else None
    def findall(self, text):
        spans, out = [], []
        if self.other:
            for m in self.other.finditer(text):
                spans.append((m.start(), m.end(), m.group(1)))
        for m in re.finditer(r"\w+", text):
            if m.group(0) in self.plain and not any(a <= m.start() < b for a, b, _ in spans):
                spans.append((m.start(), m.end(), m.group(0)))
        return [s for _a, _b, s in sorted(spans)]


def ft_context(body, nm):
    """A surname met in a fact text, by its contexts (the editor, 2026-10-18): «in», a clear name somewhere in the text (an initial, a given name or a title before it,
    or written in capitals); «out», a clear common noun or title word everywhere it stands (inside a periodical's title
    from BPEAPE, «Amerika Esperantisto»; an article before it: the, a, an, la; a sentence opened by it and an article
    after it, «Post la Kongreso»); else «review», for a reader. (An adjective in -a before it was tried as the title
    test and dropped: it would rule out «Ida Zamenhof».)"""
    cls = set()
    # THE PERIODICALS' TITLES (the editor, 2026-10-18
    #): an occurrence inside a
    # title of bpeape-entries.tsv that the fact text holds is the periodical, not a person
    spans = [(t.start(), t.end()) for title in bpeape_titles(nm) for t in _rx(title, re.escape(title), re.I).finditer(body)]
    for m in _rx(("nm", nm), rf"\b{re.escape(nm)}\b").finditer(body):
        before, after = body[:m.start()], body[m.end():]
        if any(a <= m.start() and m.end() <= b for a, b in spans): cls.add("out"); continue
        if ((re.search(r"\b[A-ZĈĜĤĴŜŬ]\.\s*(?:[A-ZĈĜĤĴŜŬ]\.\s*)*$", before) and not re.search(r"\bSt\.\s*$", before)) or FT_TITLE.search(before)
                or re.search(r"\b[A-ZĈĜĤĴŜŬ][a-zĉĝĥĵŝŭéèêëàâäîïôöûüç]{2,}\s+$", before) and not re.search(r"(?:^|[.!?;:]\s+)[A-ZĈĜĤĴŜŬ]\w+\s+$", before)
                and not re.search(r"\b(?:Saint|Sankta|West|East|North|South|New|Fort|Port|Mount|Lake)\s+$", before)):
            cls.add("in"); continue
        if (re.search(r"(?i)\b(?:the|a|an|la|this|that|tiu|ĉi tiu)\s+$", before)
                or (re.search(r"(?:^|[.!?;:«]\s*)$", before) and re.match(r"\s+(?:la|the)\b", after))
                # a place (2026-10-18, the review pile's head: MANCHESTER, NEWTON of West Newton, LOUIS of St. Louis,
                # PARK): a preposition of place or a place's prefix before it
                or re.search(r"\b(?:en|el|ĝis|al|in|at|from|near|of|to|St\.?|Saint|Sankta|West|East|North|South|New|Fort|Port|Mount|Lake)\s+$", before)):
            cls.add("out"); continue
        cls.add("review")
    if nm.upper() in body and _rx(("up", nm), rf"\b{re.escape(nm.upper())}\b").search(body): cls.add("in")
    return "in" if "in" in cls else "review" if "review" in cls else "out"


# EACH PATTERN COMPILED ONCE (2026-10-24; the editor, to the fix of the harvest's slow section, measured without the
# profiler: ft_context 3,580 s in 154,190 calls, 23 ms each, against 17 s for finding the surnames): ft_context built a
# pattern for every periodical title holding the surname and for the surname itself, at every call; thousands of distinct
# patterns, more than the re module's cache keeps, so each was compiled anew. The same patterns, compiled once
_RX = {}
def _rx(key, pattern, flags=0):
    if key not in _RX: _RX[key] = re.compile(pattern, flags)
    return _RX[key]
SOURCE_YEAR_SKIPS = []                           # the files of the page guesses a neighbour dated by its source's year would have changed
SAYING_SKIPPED = []                             # lines with a saying theme under an event kind (a probable kind fault)
# a fact that reports someone's judgement: under a kind other than «juĝo» or «interpreto», a probable kind fault (rule 4a)
JUDGE_WORDS = re.compile(r"\b(juĝas|juĝis|opinias|opiniis|supozas|supozis|konjektas|konjektis|klarigas|klarigis|taksas|taksis|konsideras|konsideris)\b")

FAMILIES = {
    "LEMAIRE": [(("the Épernay family",), ["René"])],
}

# ONE FILE PER PERSON, 2026-10-08 (editor, on the two Lemaire profiles
#). A PERSONS surname no longer gets one sectioned profile: each
# person gets a file of their own, the rows that cannot tell the people apart (an AMBIG label, or a line with no
# or an unlisted qualifier) go to <surname>-ambiguous.md, and <surname>.md becomes an index of those files. The
# file stem comes from the label's name (before the first « (», « —» or «,»), unless overridden here; a label
# that names no single person is AMBIG. A person file whose stem is also a stand-alone profile (RENÉ LEMAIRE
# lines written without the qualifier) absorbs it.
AMBIG_LABEL = re.compile(r"undetermined|unidentified|\bother\b|\bothers\b|\bboth\b|❓", re.I)
PERSON_STEM = {   # label prefix → file stem; "AMBIG" sends the row to the ambiguous file
    "Commandant Charles Lemaire": "charles-lemaire", "Sterio (Ŝterju) Atanasov": "sterio-atanasov",
    "C. J. (Chas. J.) Morin": "c-j-morin", "Richard Trompeter": "richard-trompeter",
    "Prof. Dr Adolf Schmidt": "adolf-schmidt", "Prof. Otto Simon": "otto-simon",
    "Col. George B. M. Harvey": "george-b-m-harvey", "Major-General George Cox": "george-cox",
    "Dr S. Kimel": "s-kimel", "Dr Miloslav Schmidt": "miloslav-schmidt", "Abbé Austin Richardson": "austin-richardson",
    "Mlle Clotilde Simon of Ixelles": "clotilde-simon", "Ing. Fr. Kühnl": "fr-kuhnl",
}

def person_stem(who, label):
    """File stem for one PERSONS label, or None for the surname's ambiguous file."""
    for k, v in PERSON_STEM.items():
        if label.startswith(k): return None if v == "AMBIG" else v
    if label.startswith("(unassigned") or AMBIG_LABEL.search(label): return None
    return slug(re.split(r" \(| —|,", label)[0])

# Two men of one surname, filed under either spelling (2026-10-18, the walk-through; the editor; the
# register's «keep apart» row): Adam Zakrzewski of Warsaw, the historian, and Aleksandr Kasperoviĉ Zakrĵevskij of
# Smolensk, later Ekaterinodar. Only the given name the line prints decides (a Russian source transliterates Adam's name
# too, so no spelling and no place does); a line with «A.» alone stays where its reader put it
# (the name next to the surname, or the line's own qualifier: «Aleksander Brzostowski» on Adam's Warsaw line is another
# man, the first rule's catch, 2026-10-18)
REASSIGN = {
    "ZAKRZEWSKI": [("ZAKRJEVSKI", r"^\*\*\((?:Aleksand|Aleks\.)|\b(?:Aleksand\w*|Aleks\.)\s+(?:Kasperovi\w+\s+)?Zakr")],
    "ZAKRJEVSKI": [("ZAKRZEWSKI", r"^\*\*\(Adam\b|\bAdam\s+Zakr")],
    # Ivy Kellerman, Amerika Esperantisto's editor, later Kellerman-Reed (the editor, 2026-10-18
    #): only the lines that print «Ivy»; «Prof. Ira Kellerman, Toledo» and the bare
    # «Dr. Kellerman» stay under KELLERMAN
    "KELLERMAN": [("KELLERMANN-REED", r"^\*\*\(Ivy\b|\bIvy\s+(?:[A-Z]\.\s+)?Kellerman")],
}
REASSIGNED = []

def person_of(who, fact):
    """Which section of a multi-person profile a line belongs to, from its (qualifier) prefix."""
    if who not in PERSONS: return None
    if not fact.startswith("**("): return "(unassigned — no qualifier)"
    q = fact[3:fact.index(")**")] if ")**" in fact else ""
    for label, keys in PERSONS[who]:
        if any(q.startswith(k) for k in keys): return label
    return "(unassigned — qualifier not in the PERSONS table)"

def canon(who):
    """Canonical display name. Explicit table only — no fuzzy joining, ever."""
    return ALIASES.get(who.strip().upper(), who.strip())

def slug(who):
    """Filename stem: diacritics folded, so SÉBERT and SEBERT cannot land in two files."""
    flat = "".join(c for c in unicodedata.normalize("NFD", who.lower())
                   if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", flat).strip("-")
    # a profile may not be named as a file Claude Code reads as instructions (2026-10-18: the surname CLAUDE, of Amerika
    # Esperantisto, made profiles/CLAUDE.md on a case-insensitive disk, loaded into every session that touched profiles/)
    return f"{s}-persono" if s in ("claude", "claude-local", "agents") else s

def sortkey(year):
    r = resolved(year) if not year.startswith("[") else None    # an event form sorts at its event (2026-10-12)
    p = 1 if year.rstrip("* ").endswith("☞") else 0             # a plan after the real dates of its year (2026-10-22)
    if r and (r.lo or r.hi): return (0, int((r.lo or r.hi)[:4]), p)
    m = re.search(r"(1[6-9]\d\d|20\d\d)", year)
    return (0, int(m.group(1)), p) if m else (1, 0, 0)     # [n.d.] sorts last

# FACTS FORMAT 2 AND THE MISSING-FACTS REPORT, 2026-10-10 (geniza/QUEUE.md: the NOVELTY, LOCATOR AND QUOTATION,
# MISSING-FACTS and REISSUE rulings, after the Fable review plans/fable-review-prosopography-return-2026-10-10.md).
#
# A facts file that declares `facts-format: 2` near its head gets strict checks on every line: the locator is
# `<item>, PDF N (prese M)` or `<item>, ¶ N` with an item key from OCR-ITEM-TABLE.tsv; the fact carries a verbatim
# quotation «…» of six or more words; the confidence carries no novelty marks (NOVA, «jam registrita», ⟳, ⟵: novelty is
# decided here, at the build, not in the facts file); and a line from a SECONDARY source carries an independence label.
# Older files keep their form until their re-dowse, so they are not held to this.
#
# After each successful build the full list of fact lines is saved (profiles/build/FACTS-LIST.tsv) and compared with the
# previous one. An old line counts as present if the same line is still there (in any file), or if a line for the same
# person quotes overlapping words on the same page of the same item (re-found in the item's text: the FACT-ID RULING's
# mechanism, tested in geniza/ocr/method/FACT-ID-TRIAL-korzhenkov-2026-10-10.md, where matching by key flagged 42 of 56
# facts as missing on a simulated reissue and matching by passage 0). Lines with no item locator fall back to person +
# year + first quoted words. Everything else is reported in profiles/build/MISSING-FACTS-LATEST.md, by source. The
# folder is `build/`, not profiles/ itself, because tools/ocr-dowse.py reads every profiles/*.md as a person. The list is
# kept local and not tracked in git (55 MB on 2026-10-22, near GitHub's 100 MB limit; the editor 2026-10-23: «change
# it»): the comparison reads the copy on disk, and a fresh clone gets one by building at the previous commit.
FORMAT2 = re.compile(r"^\W*facts-format:\s*[234]\b")    # format 3 is format 2 with the anchor in its own field
# FACTS FORMAT 3 (the editor 2026-10-11
#): `fact · anchor · locator · [theme] · confidence`,
# the anchor bare, the fourth field from the right. Read here by turning the line into the format-2 shape with the
# anchor as the fact's last «…» (to3 below), and only that last quotation counts as the anchor.
FORMAT3 = re.compile(r"^\W*facts-format:\s*[34]\b")
FMT3 = set()      # the format-3 files of this run (format 4 included)
# FACTS FORMAT 4 (the editor 2026-10-13; the facts-writing template § 3, «speco»): format 3 with the event kind,
# `{kind: object; +second}`, as a field right after the date. The field is taken off before the line is read, so every
# check, key and the missing-facts comparison see the format-3 line; the kind is kept aside (KINDS), shown in the profile
# after the date, written to FACTS-LIST's last column and checked against the list in force
# (geniza/ocr/method/EVENT-KINDS-PROPOSAL-2026-10-13.md, «The list in force»).
FORMAT4 = re.compile(r"^\W*facts-format:\s*4\b")
# «facts-kinds: 4» (2026-10-19, the editor): a hand-written file in format 4's line form whose sources are not items
# of OCR-ITEM-TABLE.tsv (web pages, BAnQ pastes): its kinds and anchors are read as format 4's, without format 2's
# strict checks (item keys, locator form). Found when beauchemin-additions-2026-10-19-dowse.md, harvested without its
# «facts-format: 4» line to pass the item-key check, had lost its 180 lines' kinds and the copies to the people they name.
KINDS4 = re.compile(r"^\W*facts-kinds:\s*4\b")
KINDF = re.compile(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))? \*\*[^*]+\*\* · )\{([^{}]*)\} · (.*)$")
KINDS = {}        # (facts file, source, fact) -> «kind: object; +second»

def form_repair(line):
    """The two form faults of the cut brief, repaired (the editor, 2026-10-17; the probe P2(a), every
    return failing the format check for these two only): a date left bare, «[sen dato]» or «[ĝenerala]», is made bold;
    a missing themes field «[?]» is put back before the voice. Used by the assembler on every reader's line and by
    file-return.py's check at filing, so neither counts as a fault. A line already in form comes back unchanged."""
    if not line.startswith("- $$$"): return line
    line = re.sub(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))?) (\[(?:sen dato|ĝenerala)[^\]]*\]) · ", r"\1 **\2** · ", line)
    # AMERIKA ESPERANTISTO'S FORM FAULTS (2026-10-18, the first dowse of 637 readers; the editor):
    # a «Mc»/«Mac» name written as printed («McKINNEY», «MacLEOD») made upper case, as the form wants; the kind
    # «propaganda» (the English and Italian word) for «propagando»
    line = re.sub(r"^- \$\$\$ (.+?) \$\$\$", lambda m: f"- $$$ {m.group(1).upper()} $$$", line, count=1)
    line = re.sub(r"\{propaganda:", "{propagando:", line)
    line = re.sub(r"; \+propaganda:", "; +propagando:", line)
    # the voice with its notes after the bracket («📣 (sen fontindiko) [la antaŭnomo perdita]», «📣 (sendependa) ⟦…⟧»),
    # a label after it («📣 (OCR …) sen fontindiko»), or two marks run together («📣❓»): one bracket, as the form wants
    ps9 = line.split(" · ")
    if len(ps9) >= 6:
        f9 = ps9[-1]; trail = f9[len(f9.rstrip()):]
        v9 = re.sub(r"^([✅📣📄])([⚠❓])", r"\1 \2", f9.strip())
        m9 = re.fullmatch(r"([✅📣📄](?: [⚠❓]+)?) \(((?:[^()]|\([^()]*\))*)\)\s*([⚠❓]*)\s*(?:\[([^\[\]]+)\]|⟦([^⟦⟧]+)⟧|(sen fontindiko|sendependa))\s*", v9)
        if m9:   # a mark between the bracket and the note («📣 (sen fontindiko) ❓ [la nomo eble misa OCR]») joins the voice's
            extra = f"⟦{m9.group(4) or m9.group(5)}⟧" if (m9.group(4) or m9.group(5)) else None
            inner = f"{m9.group(6)}; {m9.group(2)}" if m9.group(6) else f"{m9.group(2)}; {extra}"
            head9 = m9.group(1) + "".join(f" {c}" for c in m9.group(3) if c not in m9.group(1))
            v9 = f"{head9} ({inner})"
        if v9 != f9.strip(): ps9[-1] = v9 + trail; line = " · ".join(ps9)
    # FIELDS BETWEEN THE LOCATOR AND THE VOICE (2026-10-18, Amerika Esperantisto's held-back lines, the tidy-up; the
    # editor): a note as a field of its own («· [la tago el OCR …] · [?] · 📣»,
    # «· [OCR misa; …] · ❓ · 📣», «· ⟦…⟧ · 📣»), a mark as a field of its own: the themes field kept (or «[?]»), the
    # marks after the voice's, the notes into its bracket as ours. The bare kinds without an object («· morto ·»,
    # «· naskiĝo ·») take their braces
    line = re.sub(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))? \*\*[^*]+\*\*) · (morto|naskiĝo) · ", r"\1 · {\2} · ", line)
    ps8 = line.split(" · ")
    # the marks before the voice in the last field («❓ 📣 (…)»): the voice first, as the form wants
    mf = re.fullmatch(r"([⚠❓](?: ?[⚠❓])*)\s*([✅📣📄])(.*)", ps8[-1].strip())
    if mf: ps8[-1] = f"{mf.group(2)} {' '.join(re.sub(r'\s', '', mf.group(1)))}{mf.group(3)}" + ps8[-1][len(ps8[-1].rstrip()):]
    li = next((i for i in range(2, len(ps8)) if re.match(r"^[\w.-]+, (?:PDF|¶) \d+", ps8[i].strip())), None)
    if li is not None and li <= len(ps8) - 3 and re.match(r"^[✅📣📄]", ps8[-1].strip()):
        mid = [m.strip() for m in ps8[li + 1:-1]]
        THEME = re.compile(r"(?:\[(?:\?|[A-Z][A-Z0-9]{0,5})\])+")
        themes = [m for m in mid if THEME.fullmatch(m)]
        marks = "".join(m for m in mid if re.fullmatch(r"[⚠❓]+", m))
        notes = [m.strip("[]⟦⟧ ") for m in mid if not THEME.fullmatch(m) and not re.fullmatch(r"[⚠❓]+", m) and m]
        if len(mid) > 1 or notes or marks:
            f8 = ps8[-1]; trail8 = f8[len(f8.rstrip()):]
            mv = re.match(r"([✅📣📄])((?: ?[⚠❓])*)\s*(.*)", f8.strip())
            rest = mv.group(3).strip()
            # the labels and the bracket as the reader wrote them («sen fontindiko (…)», «(sendependa; …)», a bare
            # «sen fontindiko»); the notes go inside the bracket; nothing already in form is wrapped again (the first
            # try made «📣 ❓ (sen fontindiko (…))» of seven Ruslanda Esperantisto lines and lost a ⟦…⟧)
            mlab = re.fullmatch(r"(.*?)\s*\(((?:[^()]|\([^()]*\))*)\)", rest)
            pre, inner = (mlab.group(1).strip(), mlab.group(2)) if mlab else (rest, "")
            inner = "; ".join(x for x in [inner] + [f"⟦{n}⟧" for n in notes] if x)
            allmarks = "".join(dict.fromkeys(re.sub(r"\s", "", mv.group(2)) + marks))
            voice = mv.group(1) + (" " + " ".join(allmarks) if allmarks else "") + (f" {pre}" if pre else "") + (f" ({inner})" if inner else "")
            line = " · ".join(ps8[:li + 1] + [themes[0] if themes else "[?]", voice + trail8])
    # A NOTE WHERE THE THEMES GO (2026-10-17, the Ruslanda Esperantisto pilot): a field «⟦…⟧» of its own before the
    # voice (readers 4 and 14, 44 lines), or a tag that is not a theme code (reader 1, 23 lines: «[OCR: «A. I. ASNES»;
    # la dato estas tiu de la numero]»), goes, as a note of ours, into the labels' brackets; «[?]» if no tag is left
    m0 = re.search(r" · (⟦[^⟧]*⟧) · [✅📣📄]", line)
    if m0:
        line = line[:m0.start(1)] + "[?]" + line[m0.end(1):]
        line = line[:-1] + f"; {m0.group(1)})" if line.rstrip().endswith(")") else line.rstrip() + f" ({m0.group(1)})"
    m = re.search(r" · ((?:\[[^\]]*\])+) · ([✅📣📄])", line)
    if m:
        tags = re.findall(r"\[([^\]]*)\]", m.group(1))
        notes = [t for t in tags if not re.fullmatch(r"\?|[A-Z][A-Z0-9]{0,5}", t.strip())]
        if notes:
            keep = "".join(f"[{t}]" for t in tags if t not in notes) or "[?]"
            line = line[:m.start(1)] + keep + line[m.end(1):]
            note = "⟦" + "; ".join(n.strip().strip("⟦⟧") for n in notes) + "⟧"
            line = line[:-1] + f"; {note})" if line.rstrip().endswith(")") else line.rstrip() + f" ({note})"
    # FIELDS RUN TOGETHER OR DOUBLED (the 30 issues, 2026-10-17): the themes and the voice in one field («[?] 📣»);
    # an empty field more than the form has («fact ·  · anchor»: eight fields with one empty; an empty anchor in seven
    # is a missing anchor, left for the check); «(sen presa numero)» for «(prese sen numero)»
    line = re.sub(r" · ((?:\[[^\]]*\])+) ([✅📣📄⚠❓])", r" · \1 · \2", line, count=1)
    ps0 = line.split(" · ")
    if len(ps0) == 8 and sum(1 for p in ps0[1:-1] if not p.strip()) == 1:
        line = " · ".join(p for i, p in enumerate(ps0) if i == 0 or i == len(ps0) - 1 or p.strip())
    line = re.sub(r"\((?:sen presa numero|sen numero|prese: sen numero)\)", "(prese sen numero)", line)
    # the locator with its line run on, as readers of the lean brief wrote it where the source's own note asked for the
    # item (2026-10-18t): «…, PDF 12 l. 10», «…, PDF 28 (prese 100) l. 149» → «…, PDF 12 (prese ?), l. 10»
    line = re.sub(r"(, PDF \d+)(?: (\(prese [^)]*\)))? l\. ?(\d+)(?= · |$)", lambda m: f"{m.group(1)} {m.group(2) or '(prese ?)'}, l. {m.group(3)}", line)
    # THE VOICE FIELD AS THE 30 ISSUES' READERS WROTE IT (2026-10-17, 30 lines of 225 returns): a mark in the themes
    # position («· ❓ · 📣»); the marks first («❓ 📣 sen fontindiko (…)»); the mark after the labels' brackets
    # («📣 (sen fontindiko) (…) ❓»). Each becomes the form: voice, marks, one bracket of labels
    line = re.sub(r" · ([⚠❓]) · ([✅📣📄])", r" · [?] · \2 \1", line, count=1)
    parts = line.split(" · ")
    if len(parts) >= 6:
        last = parts[-1]
        m2 = re.fullmatch(r"([⚠❓]+) ([✅📣📄])\s*(.*)", last)
        if m2:
            rest = m2.group(3).strip()
            last = f"{m2.group(2)} {m2.group(1)}" + (f" {rest}" if rest.startswith("(") and rest.endswith(")") else f" ({rest})" if rest else "")
        m3 = re.fullmatch(r"([✅📣📄])((?: \((?:[^()]|\([^()]*\))*\))+) ([⚠❓]+)", last)
        if m3:
            groups = re.findall(r"\(((?:[^()]|\([^()]*\))*)\)", m3.group(2))
            last = f"{m3.group(1)} {m3.group(3)} ({'; '.join(g.strip() for g in groups)})"
        parts[-1] = last
        line = " · ".join(parts)
    # THE VOICE OVER SEVERAL FIELDS (2026-10-18, Ruslanda Esperantisto's held-back lines, the walk-through; the editor:
    #): «· voĉo sendependa»; «· sendependa · ❓ (…)»; «· (…) · sendependa». The word «voĉo»
    # goes; trailing fields that are all of the voice (a mark, a label, a bracket) become one: the marks, then one bracket
    # of the labels and the notes. Nothing else is merged
    line = re.sub(r" · voĉo:? ([✅📣📄⚠❓])", r" · \1", line)
    ps1 = line.split(" · ")
    VOICEY = re.compile(r"^(?:[✅📣📄⚠❓]|\(|sendependa\b|derivita\b|sen fontindiko\b|refutas:)")
    v = next((i for i in range(2, len(ps1)) if re.match(r"^[✅📣📄⚠❓]", ps1[i].strip())), None)
    if v is not None and v < len(ps1) - 1 and all(VOICEY.match(p.strip()) for p in ps1[v + 1:]):
        text = " ".join(p.strip() for p in ps1[v:])
        groups = re.findall(r"\(((?:[^()]|\([^()]*\))*)\)", text)
        bare = re.sub(r"\((?:[^()]|\([^()]*\))*\)", " ", text)
        marks = [c for c in "✅📣📄" if c in bare][:1] + [c for c in "⚠❓" if c in bare]
        labels = re.sub(r"[✅📣📄⚠❓]", " ", bare).strip(" ;,")
        labels = re.sub(r"\s+", " ", labels)
        labels = re.sub(r"\s+(refutas:|derivita\b|sen fontindiko\b|sendependa\b)", r"; \1", labels).strip("; ")
        inner = "; ".join([x for x in [labels] + [g.strip() for g in groups] if x])
        if marks and marks[0] in "✅📣📄":
            ps1 = ps1[:v] + [" ".join(marks) + (f" ({inner})" if inner else "")]
            line = " · ".join(ps1)
    if not re.search(r" · (?:\[[^\]]*\])+ · [✅📣📄]", line):   # one or more tags: «[B][BIO]»
        line = re.sub(r" · ([✅📣📄])", r" · [?] · \1", line, count=1)
    # THE UNNUMBERED PAGE (2026-10-17, the Ruslanda Esperantisto pilot; the editor
    # to the vocabulary, approved): «(prese …)» in five words only: «kovrilo»,
    # «interna kovrilo», «interna malantaŭa kovrilo», «malantaŭa kovrilo» (a periodical's cover pages 1–4, so «kovrilo 2»
    # is the inner cover), and «sen numero» (an inner page with no printed number; the readers wrote «—» and «?»)
    line = re.sub(r"\(prese (?:—|–|-|\?|)\)", "(prese sen numero)", line)
    for k, w in (("1", "kovrilo"), ("2", "interna kovrilo"), ("3", "interna malantaŭa kovrilo"), ("4", "malantaŭa kovrilo")):
        line = line.replace(f"(prese kovrilo {k})", f"(prese {w})")
    # DATES IN WORDS (the same pilot: 68 lines outside the date vocabulary, all of it; the editor): a month or a
    # day written in words becomes the vocabulary's form; a double date «11/24 januaro 1904» (old style / new style)
    # becomes the new style, the vocabulary's own rule for a double-dated Julian date, with the old style in a note; a
    # year the reader added in brackets («5 januaro [1907]», the issue's year) keeps a note saying so. Other forms
    # («somero 1905», «1886–1891», span or once) are left for a reading.
    m = re.match(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))? )\*\*([^*]+)\*\*", line)
    if m:
        new, notes = date_in_words(m.group(2).strip())
        if not new and needs_reading(m.group(2).strip()): new, notes = relative_date(m.group(2).strip(), line)
        if new:
            line = m.group(1) + f"**{new}**" + line[m.end():]
            for note in notes:
                line = line[:-1] + f"; {note})" if line.rstrip().endswith(")") else line.rstrip() + f" ({note})"
    line = span_by_kind(line)
    return line

MONTHS = {m: i for i, m in enumerate(("januaro", "februaro", "marto", "aprilo", "majo", "junio", "julio", "aŭgusto",
                                       "septembro", "oktobro", "novembro", "decembro"), 1)}

def date_in_words(d):
    """(the vocabulary's form, [notes]) for a date written in words, or (None, []) to leave it."""
    mo = "(" + "|".join(MONTHS) + ")"
    yr = r"(\[)?(1[6-9]\d\d|20\d\d)\]?"
    notes = []
    def year(br, y):
        if br: notes.append("⟦la jaro laŭ la numero⟧")
        return int(y)
    m = re.fullmatch(rf"(\d{{1,2}})/(\d{{1,2}}) {mo} {yr}", d)
    if m and 12 <= int(m.group(2)) - int(m.group(1)) <= 13:
        y = year(m.group(4), m.group(5)); mm = MONTHS[m.group(3)]
        notes.insert(0, f"⟦malnova stilo: {y}-{mm:02d}-{int(m.group(1)):02d}⟧")
        return f"{y}-{mm:02d}-{int(m.group(2)):02d}", notes
    m = re.fullmatch(rf"(\d{{1,2}}) {mo} {yr}", d)
    if m:
        y = year(m.group(3), m.group(4)); return f"{y}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}", notes
    m = re.fullmatch(rf"{mo} {yr}", d)
    if m:
        y = year(m.group(2), m.group(3)); return f"{y}-{MONTHS[m.group(1)]:02d}", notes
    m = re.fullmatch(rf"(komenco|komence|meze|mezo|fino|fine) de {mo} {yr}", d)
    if m:
        part = {"komenco": "komence", "mezo": "meze", "fino": "fine"}.get(m.group(1), m.group(1))
        y = year(m.group(3), m.group(4)); return f"{part} de {y}-{MONTHS[m.group(2)]:02d}", notes
    # A DOUBLE ISSUE'S MONTHS (2026-10-18, Amerika Esperantisto: most of its 1,424 dates outside the vocabulary, lines
    # dated by an issue of two months; the editor, on the walk-through: «approve»): «februaro–marto 1916», «1914, jul.–aŭg.»,
    # «1914-12/1915-01» are once within the two months, «inter … kaj …»
    m = re.fullmatch(rf"{mo}\s*[–-]\s*{mo} {yr}", d)
    if m and MONTHS[m.group(2)] > MONTHS[m.group(1)]:
        y = year(m.group(3), m.group(4)); return f"inter {y}-{MONTHS[m.group(1)]:02d} kaj {y}-{MONTHS[m.group(2)]:02d}", notes
    ab = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6, "jul": 7, "aŭg": 8, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
    abr = "(" + "|".join(ab) + ")"
    m = re.fullmatch(rf"(1[6-9]\d\d),? {abr}\.?\s*[–-]\s*{abr}\.?", d)
    if m and ab[m.group(3)] > ab[m.group(2)]:
        return f"inter {m.group(1)}-{ab[m.group(2)]:02d} kaj {m.group(1)}-{ab[m.group(3)]:02d}", notes
    m = re.fullmatch(r"(1[6-9]\d\d)-(\d\d)/(1[6-9]\d\d)-(\d\d)", d)
    if m and (m.group(3), m.group(4)) > (m.group(1), m.group(2)):
        return f"inter {m.group(1)}-{m.group(2)} kaj {m.group(3)}-{m.group(4)}", notes
    return more_dates(d)

def mon(tok):
    """A month from its name or abbreviation, any case, with or without the dot («Majo», «okt.», «Sep», «sept.»)."""
    t = tok.lower().rstrip(".")
    for name, i in MONTHS.items():
        # Ido's two months unlike Esperanto's, «mayo» and «agosto» (Progreso, 2026-10-27)
        if t == name or (len(t) >= 3 and name.startswith(t)) or t == "aug" and i == 8 or t == "sept" and i == 9 \
           or t.startswith("may") and i == 5 or t.startswith("agost") and i == 8: return i
    return None

SEASONS = {"printempo": ("03", "05"), "somero": ("06", "08"), "somere": ("06", "08"), "aŭtuno": ("09", "11")}

def more_dates(d):
    """THE REMAINING FORMS, 2026-10-18 (the editor; 776 left, sorted by
    form): the vocabulary's form, [notes], or (None, []). Months in any case and order, abbreviated or not; a month range,
    within a year or across two; a season, as its months (northern), the season in a note; a double date with the old
    style in brackets or marked j.s./g.s., the new style kept and the old in a note; a Julian date alone as «m.s.»; «ĉ.»
    as «ĉirkaŭ»; «fino de», «ekde», the decades. Ranges of days are left to range_by_kind, which knows the kind."""
    W = r"([A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ]+\.?)"
    Y = r"(1[6-9]\d\d)"
    def two(a): return f"{int(a):02d}"
    m = re.fullmatch(rf"ĉ\.\s+(\d{{4}}(?:-\d\d){{0,2}})", d) or re.fullmatch(rf"\[ĉ\.\s+(\d{{4}})\]", d)
    if m: return f"ĉirkaŭ {m.group(1)}", []
    m = re.fullmatch(rf"ĉ\.\s+{W}\s+{Y}", d)
    if m and mon(m.group(1)): return f"ĉirkaŭ {m.group(2)}-{two(mon(m.group(1)))}", []
    m = re.fullmatch(rf"{Y},?\s+\(?{W}\)?", d) or None
    if m and mon(m.group(2)): return f"{m.group(1)}-{two(mon(m.group(2)))}", []
    m = re.fullmatch(rf"(\d{{1,2}})\s+{W}\s+{Y}", d)
    if m and mon(m.group(2)): return f"{m.group(3)}-{two(mon(m.group(2)))}-{two(m.group(1))}", []
    m = re.fullmatch(rf"{W}\s+{Y}", d)
    if m and mon(m.group(1)): return f"{m.group(2)}-{two(mon(m.group(1)))}", []
    m = re.fullmatch(rf"(\d{{1,2}}\s+)?{W}\s+\[{Y}\]", d)
    if m and mon(m.group(2)):
        return (f"{m.group(3)}-{two(mon(m.group(2)))}" + (f"-{two(m.group(1))}" if m.group(1) else "")), ["⟦la jaro laŭ la numero⟧"]
    # a month range: «feb.–mar. 1916», «Nov–Dec 1909», «1912 (sep.–okt.)», «decembro 1915 – januaro 1916», «1916-07/08»
    m = re.fullmatch(rf"{W}\s*[–-]\s*{W}\s+{Y}", d) or re.fullmatch(rf"{Y}\s+\({W}\s*[–-]\s*{W}\)", d)
    if m:
        g = m.groups(); a, b, y = (g[0], g[1], g[2]) if not g[0].isdigit() else (g[1], g[2], g[0])
        if mon(a) and mon(b) and mon(b) > mon(a): return f"inter {y}-{two(mon(a))} kaj {y}-{two(mon(b))}", []
    m = re.fullmatch(rf"{W}\s+{Y}\s*[–-]\s*{W}\s+{Y}", d)
    if m and mon(m.group(1)) and mon(m.group(3)) and int(m.group(4)) == int(m.group(2)) + 1:
        return f"inter {m.group(2)}-{two(mon(m.group(1)))} kaj {m.group(4)}-{two(mon(m.group(3)))}", []
    m = re.fullmatch(rf"{Y}-(\d\d)/(\d\d)", d)
    if m and m.group(3) > m.group(2): return f"inter {m.group(1)}-{m.group(2)} kaj {m.group(1)}-{m.group(3)}", []
    # a season, as its months, the word in a note: «1908 printempo», «somero 1911», «1909 (aŭtuno)», «vintro 1908–1909»
    m = re.fullmatch(rf"{Y},?\s+[\(\[]?(printempo|somero|somere|aŭtuno)[\)\]]?", d) or re.fullmatch(rf"(printempo|somero|aŭtuno)\s+{Y}", d)
    if m:
        y, s = (m.group(1), m.group(2)) if m.group(1)[0].isdigit() else (m.group(2), m.group(1))
        a, b = SEASONS[s]; return f"inter {y}-{a} kaj {y}-{b}", [f"⟦la sezono: {s}⟧"]
    m = re.fullmatch(rf"vintro\s+{Y}\s*[–/-]\s*{Y}", d) or re.fullmatch(rf"{Y}\s*[–/-]\s*{Y}\s+\(vintro\)", d)
    if m and int(m.group(2)) == int(m.group(1)) + 1: return f"inter {m.group(1)}-12 kaj {m.group(2)}-02", ["⟦la sezono: vintro⟧"]
    # old style beside new: the new style kept, the old in a note
    m = re.fullmatch(rf"(\d{{1,2}})\s+\((\d{{1,2}})\)\s+{W}\s+{Y}", d)
    if m and mon(m.group(3)) and 12 <= (int(m.group(2)) - int(m.group(1))) % 31 <= 13:
        mo_n = mon(m.group(3)) + (1 if int(m.group(2)) < int(m.group(1)) else 0)
        if mo_n <= 12: return f"{m.group(4)}-{two(mo_n)}-{two(m.group(2))}", [f"⟦malnova stilo: {m.group(4)}-{two(mon(m.group(3)))}-{two(m.group(1))}⟧"]
    m = re.fullmatch(rf"(\d{{1,2}})\s+{W}\s+\((\d{{1,2}})\s+{W}\)\s+{Y}", d)
    if m and mon(m.group(2)) and mon(m.group(4)):
        return f"{m.group(5)}-{two(mon(m.group(4)))}-{two(m.group(3))}", [f"⟦malnova stilo: {m.group(5)}-{two(mon(m.group(2)))}-{two(m.group(1))}⟧"]
    m = re.fullmatch(r"(\d{4}-\d\d-\d\d)\s+\(j\.s\.;\s*(\d{4}-\d\d-\d\d)\s+g\.s\.\)", d) or re.fullmatch(r"(\d{4}-\d\d-\d\d)\s+j\.s\.\s+\((\d{4}-\d\d-\d\d)\)", d)
    if m: return m.group(2), [f"⟦malnova stilo: {m.group(1)}⟧"]
    m = re.fullmatch(rf"(\d{{1,2}})\s+{W}\s+{Y}\s+\(malnova stilo\)", d)
    if m and mon(m.group(2)): return f"{m.group(3)}-{two(mon(m.group(2)))}-{two(m.group(1))} m.s.", []
    m = re.fullmatch(rf"fino de {Y}", d)
    if m: return f"fine de {m.group(1)}", []
    m = re.fullmatch(rf"ekde {W}\s+{Y}", d)
    if m and mon(m.group(1)): return f"ekde {m.group(2)}-{two(mon(m.group(1)))}", []
    m = re.fullmatch(r"(1[6-9]\d0)-aj jaroj", d)
    if m: return f"la {m.group(1)}aj jaroj", []
    # a date in the vocabulary with the reader's note in brackets after it («1913-06 [meze de junio]», «1910-01
    # [«has just»]»): the date kept, the note ours, in the labels
    m = re.fullmatch(r"(\d{4}(?:-\d\d){0,2})\s*\[([^\[\]]+)\]", d)
    if m: return m.group(1), [f"⟦{m.group(2).strip()}⟧"]
    return None, []

def needs_reading(d):
    """A date field outside the vocabulary, or in its event form («dum …», «antaŭ …», «post …») with no event of the
    calendar to resolve it: «dum la pasinta jaro» and «antaŭ la 10a de februaro» parse as events, and only the calendar's
    congresses and the war are events it knows (2026-10-18)."""
    try: x = date_vocab.parse(d)
    except ValueError: return True
    return x.kind == "event" and resolved(d) is None

def issue_date(line, day=False):
    """(year, first month, last month) of the periodical issue a line's locator names, from the item's name
    («AmerikaEsperantisto_1907_v01_n06_jul», «…_1916_v18_n04_feb-mar», «…_1914_v16_n04_dec-jan», the last month then in
    the next year); the months None where the name gives none and the item is an issue of a run (issue_year); else None."""
    loc = next((p.strip() for p in line.split(" · ")[2:] if re.match(r"^[\w.-]+, (?:PDF|¶) \d+", p.strip())), None)
    ms = locators(loc) if loc else None
    if not ms: return None
    it = ms[0].group("item").strip()
    y = issue_year(loc)
    # the masthead first (the editor, 2026-10-22); the item's name
    # (an archive's metadata) only where no masthead reads
    md = masthead_date(it, ms[0].group("pdf"), y)
    if md: return md if day else md[:3]     # DAY: with the masthead's day, for the «[n]» field (issue_field)
    m = re.search(r"_(1[6-9]\d\d)_.*_([a-zŭ]{3})(?:-([a-zŭ]{3}))?$", it)
    if m and mon(m.group(2)) and (not m.group(3) or mon(m.group(3))):
        a = mon(m.group(2)); return int(m.group(1)), a, mon(m.group(3)) if m.group(3) else a
    return (y, None, None) if y else None

# THE ISSUE BY ITS MASTHEAD (2026-10-21; the editor, the build the dowse runbook's D6c named
#): in a file of several issues (La Esperantisto 1892–1895, La
# Lumo, the Kongresa Gazeto) the item's name gives only the year. A page's issue is the last masthead on or before it:
# a line of the source's own «issue_start» pattern (its dowse/<source>/brief-config.json, «journal») in the first
# «issue_window» lines of a page, as dowse-brief-fill.py cuts the issues; its month (two for a double number, «Julio–
# Aŭgusto»), its year, and its day where the OCR reads one cleanly («19" de Aŭgusto», «1-a de Marto»; not «152 Aprilo»,
# the «15ª» misread). A file that begins inside an issue takes the date from the file before it of the same volume (the
# «volume» setting: the 50-page pieces). A masthead whose date does not read leaves its pages undated (the year only);
# a year more than one from the item's is an OCR error, the same.
ISSUE_MONTH = re.compile(r"(?i)\b(?:(januar|februar|mart|april|maj|may|juni|juli|a[uŭû]gust|agost|septembr|oktobr|novembr|decembr)o"
                         r"|(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"
                         r"|(january|february|march|april|may|june|july|august|september|october|november|december))\b")
# Amerika Esperantisto's English masthead («Volume 5 June, 1909 Number 5», 2026-10-22)
EN_MONTH = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"), 1)}
# La Lumo's French masthead of January 1902 («Montreal, 1 Janvier 1902», as L'Espérantiste Canadien)
FR_MONTH = {"jan": 1, "fév": 2, "fev": 2, "mar": 3, "avr": 4, "mai": 5, "jui": 6, "juil": 7, "aoû": 8, "aou": 8, "sep": 9,
            "oct": 10, "nov": 11, "déc": 12, "dec": 12}
_MASTHEADS = None

def masthead_parse(s):
    """(year, first month, last month, day or None) from a masthead's text, or None."""
    mo = list(ISSUE_MONTH.finditer(s))
    if not mo: return None
    my = re.search(r"\b(1[89]\d\d)(?!\d)", s[mo[0].end():])          # «Novembro 1902a» (La Lumo)
    if not my: return None
    ms_ = [m for m in mo if m.start() < mo[0].end() + my.start()]     # the months before the year: one, or a double number's two
    def m_(m):
        if m.group(3): return EN_MONTH[m.group(3).lower()]
        if m.group(2):
            f = m.group(2).lower()
            return FR_MONTH.get(f[:4]) if f.startswith("juil") else FR_MONTH.get(f[:3])
        g = m.group(1).lower().replace("û", "ŭ")
        return mon("aŭg" + g[3:] if g.startswith("aug") else g)
    a = m_(ms_[0]); b = m_(ms_[-1]) or a
    md = re.search(r"(?i)(?<!\w)([1-9]|[12]\d|3[01])(?:-?a|[\"”'ᵃ.])?\s+(?:de\s+)?$", s[:mo[0].start()])
    return (int(my.group(1)), a, b, int(md.group(1)) if md and a == b else None) if a else None

def mastheads():
    """item -> {PDF page: (year, first month, last month, day) or None}, for the texts of every dowse source whose
    brief-config.json has a «journal» «issue_start»."""
    global _MASTHEADS
    if _MASTHEADS is not None: return _MASTHEADS
    _MASTHEADS = {}
    for cp in sorted(glob.glob(os.path.join(GEN, "dowse", "*", "brief-config.json"))):
        try: c = json.load(open(cp, encoding="utf-8"))
        except (OSError, ValueError): continue
        # «dating»: the masthead settings of a source of one issue per file, which the brief filler must not cut as a
        # journal (Amerika and Ruslanda Esperantisto, 2026-10-22; the editor
        #); else the «journal» settings of a file of several issues
        j = c.get("dating") or c.get("journal") or {}
        if not (j.get("masthead") or j.get("issue_start")): continue
        # «masthead»: a pattern for the dating only, where the cutting's «issue_start» missed issues (the Kongresa
        # Gazeto's 1911, 1912 and 1914 numbers, 2026-10-21); the cutting's own pattern stays as it cut
        rx, win = re.compile(j.get("masthead") or j["issue_start"]), int(j.get("issue_window", 30))
        # «masthead_number» / «item_number»: a masthead whose number is not the item's is another issue's (Amerika
        # Esperantisto June 1909: «Volume 5 July, 1909 Number 6» above its own «Volume 5 June, 1909 Number 5»)
        nrx = re.compile(j["masthead_number"]) if j.get("masthead_number") else None
        irx = re.compile(j["item_number"]) if j.get("item_number") else None
        vol = re.compile(j["volume"]) if j.get("volume") else None
        last_vol = cur = None
        for tp in c.get("texts", []):
            p_ = os.path.join(GEN, tp)
            if not os.path.isfile(p_): continue
            stem = os.path.splitext(os.path.basename(tp))[0]
            fy = int(re.search(r"(1[89]\d\d)", stem).group(1)) if re.search(r"(1[89]\d\d)", stem) else None
            mv = vol.match(stem) if vol else None
            if not (mv and mv.group(1) == last_vol): cur = None
            mi = irx.search(stem) if irx else None
            def same_no(h, ls):
                mn = nrx.search(ls[h] + (" " + ls[h + 1] if h + 1 < len(ls) else "")) if nrx and mi else None
                return not mn or int(mn.group(1)) == int(mi.group(1))
            last_vol = mv.group(1) if mv else None
            pieces = re.split(r"^=== (?:page|¶) (\d+) ===[ \t]*$", open(p_, encoding="utf-8").read(), flags=re.M)
            dates = {}
            for i in range(1, len(pieces) - 1, 2):
                # «first_pages»: a file of one issue has its masthead on its first pages; a dateline further in (a
                # letter's «Chicago, July 1, 1909») is not the issue's
                if j.get("first_pages") and (int(pieces[i]) > int(j["first_pages"]) or cur):   # the first that reads
                    dates[int(pieces[i])] = cur; continue
                ls = pieces[i + 1].split("\n")[:win]
                hs = [k for k, l in enumerate(ls) if rx.search(l) and same_no(k, ls)]
                if hs:   # the date after the masthead's words only (1911: «(Antverpeno, 20-27 augusto 1911)» before them,
                    # the congress's dates, read as the issue's when its own «Augusto 1011» did not read); the first of the
                    # page's matches that reads (La Esperantisto 1892: «Gazeto de la lingvo internacia» above «No. 12.
                    # Nurnbergo, Decembro 1892»); a year more than one from the file's is the OCR's («1899» in 1892)
                    # «masthead_lines» (default 2: the masthead's line and the next): a cover that sets the number and the
                    # month apart, blank lines between («No. 12.» … «Oktobro, 1904.», The Esperantist, 2026-10-23)
                    ml = int(j.get("masthead_lines", 2))
                    got = (masthead_parse(ls[h][rx.search(ls[h]).end():] + "".join(" " + x for x in ls[h + 1:h + ml])) for h in hs)
                    # «year_tolerance» (default 1): 0 for a file of one issue, whose name carries the issue's year (a
                    # later page's «August, 1909» in September 1908's file is not its masthead)
                    tol = int(j.get("year_tolerance", 1))
                    cur = next((g for g in got if g and not (fy and abs(g[0] - fy) > tol)), None)
                    # «no_day»: a masthead whose number stands before its month («N"e 2. Februaro 1908», Juna
                    # Esperantisto) gives no day
                    if cur and j.get("no_day"): cur = tuple(cur[:3]) + (None,)
                    # «number_month» (2026-10-23; the editor
                    #): a masthead whose month does not read («VIII-a jaro. N-ro 1 (85)», Lingvo
                    # Internacia 1903), in a run whose number is its month, takes the month from the number and the year
                    # from the file; «per_month» {year: issues a month} for a run published twice a month (1905–1906:
                    # «Duonmonata organo», no. 7 the first of April). A month word, where one reads, comes first: the OCR
                    # misreads digits («N-ro 5 (183) Marto 1909» for no. 3)
                    nmj = j.get("number_month")
                    # … and first a month word whose year does not read («Junio 1g11», «Novembro 1942» in 1912's file):
                    # the month with the file's year
                    if cur is None and (nmj or j.get("month_file_year")) and fy:
                        # (the OCR's «Ĵulio» and «[anuaro» for Julio and Januaro, Lingvo Internacia 1901 and 1910)
                        mw = next((list(ISSUE_MONTH.finditer(t))[:2] for t in ((ls[h][rx.search(ls[h]).end():] + "".join(
                            " " + x for x in ls[h + 1:h + ml])).replace("Ĵ", "J").replace("[", "J") for h in hs)
                            if ISSUE_MONTH.search(t)), None)
                        if mw:
                            # (a second month only beside the first, a double number's «Julio-Aŭgusto»; not a month word
                            # further on in the OCR's noise)
                            if len(mw) > 1 and mw[1].start() - mw[0].end() > 3: mw = mw[:1]
                            a = masthead_parse(f"{mw[0].group(0)} {fy}"); b = masthead_parse(f"{mw[-1].group(0)} {fy}")
                            if a and b and a[1] <= b[1] and b[1] - a[1] <= 1: cur = (fy, a[1], b[1], None)
                    # («per_month» 0: a year whose numbers are not its months, 1899's from July, «N:o 1 (87) la 25:an de julio»)
                    pm = int(nmj.get("per_month", {}).get(str(fy), 1)) if nmj else 0
                    if cur is None and nmj and fy and pm:
                        nm = next((m for m in (re.search(nmj["pattern"], " ".join(ls[h:h + ml])) for h in hs) if m), None)
                        if nm:
                            a = -(-int(nm.group(1)) // pm); b = -(-int(nm.group(2)) // pm) if nm.lastindex and nm.lastindex > 1 and nm.group(2) else a
                            if 1 <= a <= b <= 12: cur = (fy, a, b, None)
                    # «unread_between»: a masthead that does not read is an issue between the issues before and after
                    # it, settled once the volume's pieces are read (below); a line the pattern took for a masthead inside
                    # an issue then costs nothing, its neighbours being the same issue
                    if cur is None and j.get("unread_between"): cur = "?"
                dates[int(pieces[i])] = cur
            # «name_month» (2026-10-23): a file of one issue whose name gives its month («juna.esperantisto.1906.07»)
            # dates the pages no masthead reads by its name; the masthead first (the double number «Julio-Aŭgusto»)
            # … or its number, monthly within a year: «name_offset» {year: k}, the month = the number + k (La Suno
            # Hispana: no. 1 October 1903, k 9; no. 13 January 1905, k −12), and «name_first» where the name is surer
            # than the OCR's mastheads; a group 3 for a double number («jarkolekto-27-28»)
            mnm = re.search(j["name_month"], stem) if j.get("name_month") else None
            off = j.get("name_offset", {}).get(mnm.group(1)) if mnm and j.get("name_offset") else (0 if mnm else None)
            if mnm and off is not None:
                a = int(mnm.group(2)) + off
                b = int(mnm.group(3)) + off if mnm.lastindex and mnm.lastindex > 2 and mnm.group(3) else a
                if 1 <= a <= b <= 12:
                    for p in dates:
                        # (a masthead whose months hold the name's keeps its reading: a double number, a day)
                        keep = dates[p] and dates[p][0] == int(mnm.group(1)) and dates[p][1] <= a and b <= dates[p][2]
                        if not dates[p] or (j.get("name_first") and not keep): dates[p] = (int(mnm.group(1)), a, b, None)
            # A MISSED NUMBER (La Lumo April 1903, its masthead not in the OCR): where the next dated issue is more than a
            # month after this one, this one's pages may run into the months between, so they are dated to the range
            # («inter 1903-03 kaj 1903-04»), not to this issue alone
            runs = []
            for p in sorted(dates):
                if not runs or runs[-1][1] != dates[p]: runs.append([p, dates[p]])
            for r, nx in zip(runs, runs[1:]):
                x, y_ = r[1], nx[1]
                if x and y_ and x[0] == y_[0] and y_[1] > x[2] + 1:
                    w = (x[0], x[1], y_[1] - 1, None)
                    for p in dates:
                        if p >= r[0] and p < nx[0] and dates[p] == x: dates[p] = w
            _MASTHEADS[stem] = dates
        if j.get("unread_between"):
            # the unread stretches, over the source's texts in order within one volume: the same issue on both sides
            # gives it; two issues of one year the months between them («inter» the earlier's last and the later's
            # first); else no date
            seq = []
            for tp in c.get("texts", []):
                stem = os.path.splitext(os.path.basename(tp))[0]
                mv = vol.match(stem) if vol else None
                seq += [(stem, p, mv.group(1) if mv else stem) for p in sorted(_MASTHEADS.get(stem, {}))]
            def val(k): return _MASTHEADS[seq[k][0]][seq[k][1]]
            k = 0
            while k < len(seq):
                if val(k) != "?": k += 1; continue
                e = k
                while e < len(seq) and val(e) == "?" and seq[e][2] == seq[k][2]: e += 1
                pv = val(k - 1) if k and seq[k - 1][2] == seq[k][2] and val(k - 1) not in (None, "?") else None
                nx = val(e) if e < len(seq) and seq[e][2] == seq[k][2] and val(e) not in (None, "?") else None
                w = None
                if pv and nx and tuple(pv[:3]) == tuple(nx[:3]): w = pv
                elif pv and nx and pv[0] == nx[0] and pv[2] <= nx[1]: w = (pv[0], pv[2], nx[1], None)
                for q in range(k, e): _MASTHEADS[seq[q][0]][seq[q][1]] = w
                k = e
    return _MASTHEADS

def masthead_report(src):
    """--mastheads SOURCE: for each text of dowse/SOURCE, the issues its mastheads date (first page, date) and the pages
    left undated; writes nothing."""
    c = json.load(open(os.path.join(GEN, "dowse", src, "brief-config.json"), encoding="utf-8"))
    mh = mastheads(); un = 0
    for tp in c.get("texts", []):
        stem = os.path.splitext(os.path.basename(tp))[0]; d = mh.get(stem, {})
        runs = []
        for p in sorted(d):
            if not runs or runs[-1][1] != d[p]: runs.append((p, d[p]))
        und = [p for p in sorted(d) if not d[p]]; un += len(und)
        print(f"{stem}: {len(d)} pages, {sum(1 for r in runs if r[1])} issues dated, {len(und)} pages undated"
              + (f" (PDF {und[0]}–{und[-1]})" if und else ""))
        for p, x in runs:
            print(f"    PDF {p}: " + (issue_field(x) if x else "[sen dato]"))
    print(f"{src}: {un} pages undated")
    return 0

# THE ISSUE-DATE REGISTER (2026-10-22; the editor):
# profiles/ISSUE-DATES.tsv, one row per issue whose masthead no pattern reads: item, the issue's first PDF page, its
# date in the vocabulary («1907-04», «inter 1909-05 kaj 1909-07», «1909»), the basis («kapo»: the masthead as an image
# reader or the editor read it; «enhavo»: no month printed, the range the issue's own contents allow), the source. A
# row overrides the pattern's reading of that issue.
_ISSUE_REG = None

def issue_register():
    global _ISSUE_REG
    if _ISSUE_REG is not None: return _ISSUE_REG
    _ISSUE_REG = defaultdict(list)
    p = os.path.join(GEN, "profiles", "ISSUE-DATES.tsv")
    if not os.path.isfile(p): return _ISSUE_REG
    for r in csv.reader(open(p, encoding="utf-8"), delimiter="\t"):
        if not r or r[0].startswith("#") or r[0] == "item" or len(r) < 4: continue
        d = r[2].strip()
        if m := re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", d): t = (int(m[1]), int(m[2]), int(m[2]), int(m[3]))
        elif m := re.fullmatch(r"(\d{4})-(\d\d)", d): t = (int(m[1]), int(m[2]), int(m[2]), None)
        elif m := re.fullmatch(r"inter (\d{4})-(\d\d) kaj (\d{4})-(\d\d)", d): t = (int(m[1]), int(m[2]), int(m[4]), None)
        elif m := re.fullmatch(r"(\d{4})", d): t = (int(m[1]), None, None, None)
        else: raise SystemExit(f"ISSUE-DATES.tsv: a date outside the forms: {r}")
        _ISSUE_REG[r[0].strip()].append((int(r[1] or 1), t + (r[3].strip(),)))
    for k in _ISSUE_REG: _ISSUE_REG[k].sort()
    return _ISSUE_REG

def issue_contents(src, validate=False):
    """--issue-contents SOURCE [--validate]: for each issue (file) of dowse/SOURCE, the range of months its own dowse lines
    allow (the editor, 2026-10-22): from the latest past event it reports (a line's date, not a
    plan, not «antaŭ» / «post» / an event, not dated by the issue itself: its earliest month) to the earliest plan it
    announces (a «☞» date of its own, not «dum aŭ post» the announcement: its last month), narrowed by the dated issues
    before and after it in the run. With --validate, for the issues of known month: the range computed without their own
    date, and whether it holds the month. Writes nothing; its rows go into profiles/ISSUE-DATES.tsv as «enhavo» once read."""
    c = json.load(open(os.path.join(GEN, "dowse", src, "brief-config.json"), encoding="utf-8"))
    stems = [os.path.splitext(os.path.basename(t))[0] for t in c.get("texts", [])]
    def ym(s): return int(s[:4]) * 12 + int(s[5:7]) - 1
    def fmt(n): return f"{n // 12}-{n % 12 + 1:02d}"
    known = {}
    for s in stems:
        d = masthead_date(s, 1)
        if d and d[1]: known[s] = (d[0] * 12 + d[1] - 1, d[0] * 12 + d[2] - 1 + (12 if d[2] < d[1] else 0))
    low, high = defaultdict(list), defaultdict(list)
    fp = os.path.join(GEN, "profiles", "by-source", f"{src}-dowse.md")
    for l in open(fp, encoding="utf-8"):
        if not l.startswith("- $$$") or "la dato de la numero" in l: continue
        md = re.search(r"\*\*([^*]+)\*\*", l)
        loc = next((p.strip() for p in l.split(" · ")[2:] if re.match(r"^[\w.-]+, (?:PDF|¶) \d+", p.strip())), None)
        ms = locators(loc) if loc else None
        if not md or not ms: continue
        it, dv = ms[0].group("item").strip(), md.group(1).strip()
        if re.match(r"(?:antaŭ|post|ĝis|ekde|dum|ĉirkaŭ|\[)", dv): continue
        try: x = date_vocab.parse(dv)
        except ValueError: continue
        if x.kind == "event" or x.approx or x.unit not in ("month", "day") or not x.lo or not x.hi: continue
        if x.planned: high[it].append((ym(x.hi), l.strip()))
        else: low[it].append((ym(x.lo), l.strip()))
    rows, hits, n = [], 0, 0
    for i, s in enumerate(stems):
        y = int(re.search(r"(1[89]\d\d)", s).group(1)) if re.search(r"(1[89]\d\d)", s) else None
        if validate != (s in known): continue
        lo = [v for v in low.get(s, []) if y and y - 1 <= v[0] // 12 <= y]
        hi = [v for v in high.get(s, []) if y and y <= v[0] // 12 <= y + 1]
        L = max(lo) if lo else None
        U = min((v for v in hi if not L or v[0] >= L[0]), default=None)
        prev = next((known[t][0] for t in reversed(stems[:i]) if t in known), None)
        nxt = next((known[t][1] for t in stems[i + 1:] if t in known), None)
        a = max(v for v in (L and L[0], prev, y * 12 if y else None) if v is not None)
        b = min(v for v in (U and U[0], nxt, y * 12 + 11 if y else None) if v is not None)
        rng = "?" if a > b else (fmt(a) if a == b else f"inter {fmt(a)} kaj {fmt(b)}")
        mark = ""
        if validate:
            n += 1; k = known[s]; ok = a <= k[0] and k[1] <= b; hits += ok
            mark = f" | known {fmt(k[0])}{'' if k[0] == k[1] else '–' + fmt(k[1])} {'HELD' if ok else 'MISSED'} ({b - a + 1} months)"
        print(f"{s}: {rng}{mark}\n    from: {L[1][:150] if L else '—'}\n    to:   {U[1][:150] if U else '—'}")
    if validate: print(f"{src}: {hits} of {n} known months inside the range")
    return 0

def masthead_date(item, pdf, year=None):
    """(year, first month, last month, day or None) of the issue PDF page PDF of ITEM belongs to, by its masthead; None
    where the source has no masthead pattern, or the page's issue does not read (a year far from YEAR, the item's).
    From the issue-date register first: then a fifth member, the basis («kapo», «enhavo»)."""
    if not pdf: return None
    reg = [(p0, t) for p0, t in issue_register().get(item, []) if p0 <= int(pdf)]
    md = mastheads().get(item, {})
    d = md.get(int(pdf))
    if reg:
        # A FILE OF SEVERAL ISSUES (2026-10-23, The Esperantist's one file of 26 numbers: a row for no. 10, PDF 181, dated
        # every later page): the row holds until the next issue whose masthead reads, the later start winning
        p0, t = max(reg, key=lambda r: r[0])
        s = int(pdf)
        while d is not None and md.get(s - 1) == d: s -= 1
        # (a masthead that reads the register's own date leaves the row, its basis kept: Ruslanda Esperantisto 1905.1)
        # (a file of one issue, its patterns dating only one issue, keeps its row whole: the row is there because they
        # misread it, Ruslanda Esperantisto 1908's «April» on PDF 2–4)
        several = len({v for v in md.values() if v}) > 1
        # (a head whose months lie inside the row's is the row's issue, read in part: Espero Pacifista 1907's running
        # head «Marto-Apr. 1907», its «Apr.» unread, under the row «inter 1907-03 kaj 1907-04»; 2026-10-24)
        # (only for a row of several months: a later head within a row of one month, with its day, is the surer)
        inside = d is not None and t[1] and t[1] != t[2] and d[0] == t[0] and d[1] and t[1] <= d[1] and d[2] <= t[2]
        if not (several and d is not None and s > p0 and tuple(d[:4]) != tuple(t[:4]) and not inside): return t
    d = d
    if d and year and abs(d[0] - year) > 1: return None
    return d

def issue_field(iss):
    """The issue's own date in the vocabulary: «1907-07», «inter 1916-02 kaj 1916-03», «inter 1914-12 kaj 1915-01», «1905»."""
    y, a, b = iss[:3]
    if not a: return str(y)
    if a == b and len(iss) > 3 and iss[3]: return f"{y}-{a:02d}-{iss[3]:02d}"   # the masthead's day (2026-10-21)
    if a == b: return f"{y}-{a:02d}"
    return f"inter {y}-{a:02d} kaj {y + (1 if b < a else 0)}-{b:02d}"

RECENT = re.compile(r"lastatempe|antaŭ nelonge|antaŭ ne longe|ĵus|nuntempe|antaŭ kelkaj (?:tagoj|semajnoj)|ĉi-semajne|"
                    r"ĉi-monate|(?:antaŭ)?hieraŭ(?: (?:nokte|vespere|matene))?|(?:en|dum) la lastaj (?:\w+ )?(?:tagoj|semajnoj)|"
                    r"(?:en|dum) la pasinta semajno|la pasintan semajnon")
NUMWORD = {"unu": 1, "du": 2, "tri": 3, "kvar": 4, "kvin": 5, "ses": 6, "sep": 7, "ok": 8, "naŭ": 9, "dek": 10}

def relative_date(d, line):
    """RELATIVE DATES (2026-10-18; the lean brief's probe, readers writing the text's words; the editor): a date in words that is relative to the issue, or to a
    date the field gives, in the vocabulary's form, the reader's words kept in a note. -> (form, [notes]) or (None, []):
    what this cannot convert stays as written, and the harvest's undated list sends it to the reader (class «words»).
    - not «lately» («lastatempe», «antaŭ kelkaj tagoj», «en la lastaj ses semajnoj», «hieraŭ»): to the reader;
    - a year from the issue's: «dum la pasinta jaro», «en la nuna jaro», «venontjare»;
    - a season: «la lastan someron», the year the reader bracketed («(1907)») or the issue's (this year's if the
      season ended before the issue's month, else last year's); winter, which spans two years, left;
    - «antaŭ», «post», «ekde», «ĝis» before a day or month in words: «antaŭ la 10a de februaro (1908)» → `antaŭ 1908-02-10`;
    - a day and month with no year, the issue's year if the month is not after the issue's;
    - «sep tagojn post 27 aprilo», «ĉ. ses semajnojn post …»: counted;
    - a date in words with the reader's gloss: «julio 1911 (of last July)».
    Nothing relative to an event the line does not date («post la skribo de …», «ekde lia alveno»), and no length of time
    («dum tri monatoj»): those go to the reader."""
    import datetime as _dt
    words = d.strip(); s = words; hint = gloss = None
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", s)
    if m:
        s = m.group(1).strip()
        if re.fullmatch(r"1[6-9]\d\d", m.group(2).strip()): hint = int(m.group(2).strip())
        else: gloss = m.group(2).strip()
    low = s.lower(); said = f"⟦«{words}»⟧"
    if gloss:
        new, notes = date_in_words(low)
        if new: return new, notes + [said]
    iss = issue_date(line)
    if not iss and not hint: return None, []
    def year_of(mo_n):   # a month's year without a year written: the reader's, else the issue's if not after its month
        if hint: return hint, []
        y, a, b = iss
        if a and b >= a and mo_n <= b: return y, ["⟦la jaro laŭ la numero⟧"]
        # A VOLUME'S SPAN ACROSS THE YEAR'S END (2026-10-27, Progreso: its bound volumes dated «inter 1908-03 kaj 1909-02»
        # by the register, 4,173 bare months, «aprilo», «januaro», left to the undated readers): a month from the span's
        # first month on is the first year's, a month up to its last the next year's; the note says how
        if a and b < a and (mo_n >= a or mo_n <= b):
            return (y if mo_n >= a else y + 1), ["⟦la jaro laŭ la daŭro de la volumo⟧"]
        return None, []
    # «LATELY» GOES TO THE READER (2026-10-18; the editor): «lastatempe», «en la lastaj ses
    # semajnoj» are relative to when the text was written, which a reprinted letter puts months before its issue (Parrish's
    # letter of about June 1911 in the August issue); the reader dates it from the text, or by the issue
    if RECENT.fullmatch(low): return None, []
    m = re.fullmatch(r"(?:dum |en )?(?:la |ĉi tiu |ĉi tiun )?(pasinta|nuna|venonta)n? jaro(?:n)?|(pasintjare|ĉi-jare|venontjare)", low)
    if m:
        w = m.group(1) or m.group(2)
        if hint: return str(hint), [said]
        off = -1 if w.startswith("pasint") else 1 if w.startswith("venont") else 0
        return str(iss[0] + off), [f"⟦kalkulite el la numero: «{words}»⟧"]
    m = re.fullmatch(r"(?:dum |en )?(?:la )?(?:pasinta|lasta)n? (somero|printempo|aŭtuno)n?", low)
    if m:
        a, b = SEASONS[m.group(1)]
        if hint: y, how = hint, said
        elif iss[1]: y, how = (iss[0] if iss[1] > int(b) else iss[0] - 1), f"⟦kalkulite el la numero: «{words}»⟧"
        else: return None, []
        return f"inter {y}-{a} kaj {y}-{b}", [f"⟦la sezono: {m.group(1)}⟧", how]
    m = re.fullmatch(r"(antaŭ|post|ekde|ĝis) (?:la )?(\d{1,2})(?:-?a)? (?:de )?([a-zĉĝĥĵŝŭ]+\.?)(?: (1[6-9]\d\d))?", low) \
        or re.fullmatch(r"(antaŭ|post|ekde|ĝis) ()([a-zĉĝĥĵŝŭ]+\.?)(?: (1[6-9]\d\d))?", low)
    if m and mon(m.group(3)):
        y, notes = (int(m.group(4)), []) if m.group(4) else year_of(mon(m.group(3)))
        if not y: return None, []
        # the words kept only where a year was supplied («antaŭ julio 1906» → `antaŭ 1906-07` is the form alone)
        return f"{m.group(1)} {y}-{mon(m.group(3)):02d}" + (f"-{int(m.group(2)):02d}" if m.group(2) else ""), notes + ([] if m.group(4) else [said])
    # «la pasintan julion»: the last such month before the issue's; a month alone («februaro»), as a day and month below
    m = re.fullmatch(r"(?:en |dum )?(?:la )?pasinta(?:n)? ([a-zĉĝĥĵŝŭ]+?)n?", low)
    if m and mon(m.group(1)) and iss and iss[1]:
        mo_n = mon(m.group(1)); y = iss[0] if mo_n < iss[1] else iss[0] - 1
        return f"{y}-{mo_n:02d}", [f"⟦kalkulite el la numero: «{words}»⟧"]
    m = re.fullmatch(r"(?:en |dum )?([a-zĉĝĥĵŝŭ]+?)n?", low)
    if m and mon(m.group(1)) and len(m.group(1)) >= 4:
        y, notes = year_of(mon(m.group(1)))
        if y: return f"{y}-{mon(m.group(1)):02d}", notes
        return None, []
    m = re.fullmatch(r"(\d{1,2})(?:-?a)? (?:de )?([a-zĉĝĥĵŝŭ]+\.?)", low)
    if m and mon(m.group(2)):
        y, notes = year_of(mon(m.group(2)))
        if y: return f"{y}-{mon(m.group(2)):02d}-{int(m.group(1)):02d}", notes
        return None, []
    m = re.fullmatch(r"(ĉ\. |ĉirkaŭ )?(\d{1,2}|" + "|".join(NUMWORD) + r") (tago|semajno)j?n? post (?:la )?(\d{1,2})(?:-?a)? (?:de )?([a-zĉĝĥĵŝŭ]+\.?)(?: (1[6-9]\d\d))?", low)
    if m and mon(m.group(5)):
        y, notes = (int(m.group(6)), []) if m.group(6) else year_of(mon(m.group(5)))
        if not y: return None, []
        n = int(m.group(2)) if m.group(2).isdigit() else NUMWORD[m.group(2)]
        try: day = _dt.date(y, mon(m.group(5)), int(m.group(4))) + _dt.timedelta(days=n * (7 if m.group(3) == "semajno" else 1))
        except ValueError: return None, []
        return ("ĉirkaŭ " if m.group(1) else "") + day.isoformat(), notes + [f"⟦kalkulite: «{words}»⟧"]
    return None, []

# A BARE YEAR SPAN BY THE KIND (the editor, 2026-10-18, on the walk-through
#): «1911–1912» is «de … ĝis» for what lasts (an office, an occupation, a residence, a journey, study,
# propaganda, lecturing, a dispute, a presence, a trait, health, influence, descent) and «inter … kaj» for what happens
# once (birth, death, founding, joining, leaving, a meeting, a congress, a deliberation, a work, a notice, a saying, an
# honour, a record, a family event, an agreement); interpreto, samnomo and alia are left for a reading
SPAN_DURATION = {"ofico", "profesio", "loĝado", "vojaĝo", "studo", "propagando", "prelego", "konflikto", "aperoj",
                 "karaktero", "sano", "influo", "deveno"}
SPAN_POINT = {"naskiĝo", "morto", "postmorto", "memorigo", "registro", "fondo", "aliĝo", "foriro", "deliberado",
              "kongreso", "renkonto", "honoro", "anonco", "aserto", "juĝo", "historiografio", "atestaĵo", "verko",
              "familio", "nomo", "interkonsento"}

def range_ends(d):
    """A range written outside the vocabulary -> (first, last, approx) in the vocabulary's dates, or None: years
    «1911–1912», «ĉ. 1881–1882»; days «1909-08-09–14», «1909-08-09/14», «1912-08-11/1912-08-17», «17–25 aŭgusto 1912»,
    «1 sep 1909 – 1 feb 1910», «28 mar. – 3 apr. 1910», «20 decembro 1915 – 5 januaro 1916»; months «1909-07 – 1909-09»
    (2026-10-18, the remaining dates)."""
    Y, W = r"(1[6-9]\d\d)", r"([A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ]+\.?)"
    two = lambda a: f"{int(a):02d}"
    m = re.fullmatch(rf"(ĉ\.\s+)?{Y}\s*[–-]\s*{Y}", d)
    if m and int(m.group(3)) > int(m.group(2)): return m.group(2), m.group(3), bool(m.group(1))
    m = re.fullmatch(rf"{Y}-(\d\d)-(\d\d)\s*[–/-]\s*(\d\d)", d)
    if m and m.group(4) > m.group(3): return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", f"{m.group(1)}-{m.group(2)}-{m.group(4)}", False
    m = re.fullmatch(r"(\d{4}-\d\d(?:-\d\d)?)\s*(?:/|\s[–-]\s)\s*(\d{4}-\d\d(?:-\d\d)?)", d)
    if m and m.group(2) > m.group(1) and len(m.group(1)) == len(m.group(2)): return m.group(1), m.group(2), False
    m = re.fullmatch(rf"(\d{{1,2}})\s*[–-]\s*(\d{{1,2}})\s+{W}\s+\[?{Y}\]?", d)
    if m and mon(m.group(3)) and int(m.group(2)) > int(m.group(1)):
        mm = two(mon(m.group(3))); return f"{m.group(4)}-{mm}-{two(m.group(1))}", f"{m.group(4)}-{mm}-{two(m.group(2))}", False
    m = re.fullmatch(rf"(\d{{1,2}})\s+{W}(?:\s+{Y})?\s*[–-]\s*(\d{{1,2}})\s+{W}\s+{Y}", d)
    if m and mon(m.group(2)) and mon(m.group(5)):
        y1 = m.group(3) or m.group(6)
        a, b = f"{y1}-{two(mon(m.group(2)))}-{two(m.group(1))}", f"{m.group(6)}-{two(mon(m.group(5)))}-{two(m.group(4))}"
        if b > a: return a, b, False
    return None

def span_by_kind(line):
    """A range by the line's kind (the editor, 2026-10-18): «de … ĝis» for what
    lasts, «inter … kaj» for what happens once; «ĉirkaŭ» kept on the ends of a duration (a set takes no qualifier: the
    vocabulary's rule); interpreto, samnomo and alia left for a reading."""
    m = re.match(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))? )\*\*([^*]+)\*\*( · \{(\w+))?", line)
    if not m or not m.group(4): return line
    ends = range_ends(m.group(2).strip())
    if not ends: return line
    a, b, approx = ends; k = m.group(4)
    q = "ĉirkaŭ " if approx else ""
    new = f"de {q}{a} ĝis {q}{b}" if k in SPAN_DURATION else f"inter {a} kaj {b}" if k in SPAN_POINT else None
    return m.group(1) + f"**{new}**" + line[m.end(2) + 2:] if new else line

def take_kind(line):
    """A format-4 line -> (the format-3 line, the kind field without braces), or (line, None)."""
    m = KINDF.match(line.rstrip())
    return (m.group(1) + m.group(3), m.group(2).strip()) if m else (line, None)

def kind_list():
    """The kinds in force: the bold first cells of the table under «The list in force»."""
    p = os.path.join(GEN, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md")
    if not os.path.exists(p): return set()
    t = open(p, encoding="utf-8").read()
    i = t.find("## The list in force"); j = t.find("\n## ", i + 5)
    return set(re.findall(r"^\| \*\*([^*]+)\*\* \|", t[i:j], re.M)) if i >= 0 else set()

def kind_problem(k, kinds):
    """The checks on a kind field: on the list, an object (but for birth and death), a second kind on the list."""
    head, _, more = k.partition(";")
    kind, _, obj = head.partition(":")
    kind, obj = kind.strip(), obj.strip()
    if kind not in kinds: return f"kind not on the list: «{kind}»"
    if not obj and kind not in ("naskiĝo", "morto"): return f"no object for «{kind}»"
    extras = [x.strip() for x in more.split(";") if x.strip()]
    for x in extras:
        if x.startswith("+") and x[1:].split(":")[0].strip() not in kinds:   # «+ofico» or «+ofico: object»
            return f"second kind not on the list: «{x[1:].split(':')[0].strip()}»"
    if kind == "alia" and not any(x.startswith("sugestas:") for x in extras): return "alia without «sugestas: …»"
    return None

# COPIES FOR THE OTHER PERSONS (the editor 2026-10-13 20:1x, on every meeting or letter written twice
# at harvest, so the profile shows it at once:
# approved): a meeting, a quarrel or an agreement reads the same from both sides, so the reader writes it once, under the
# first person, with the others as roster names in the object (`{renkonto: POSTNIKOV}`, `{renkonto: ZAMENHOF kaj DE
# BEAUFRONT, …}`, `+renkonto: LEMAIRE`); the harvest writes the copy under each of them, the names swapped in the kind,
# marked «⟦kopio el NAME⟧» (until 2026-10-16 «kopio el la linio de NAME»; the editor). Not copied: a person who already has a line with the same anchor and locator in
# the same file (returns written before the rule carry their own copies); a person with no lines of their own (the
# reader judged them out of scope); an object that is not wholly roster names («familio de MAIGRET»). Directed kinds
# (influo, propagando) are never copied: «A influenced B» is not «B influenced A».
COPY_KINDS = {"renkonto", "konflikto", "interkonsento"}
# every Latin capital, not only the Western ones (2026-10-14: «WIĘCHOWSKI» in a «kun:» list got no copy; Ł, Ż, Š, Č,
# Ő, Œ and the rest of Latin Extended-A and B were refused)
_UP = "A-ZÀ-ÖØ-Þ" + "".join(chr(c) for c in range(0x100, 0x250) if chr(c).isupper())
OBJ_PERSON = re.compile(rf"([{_UP}][{_UP}' \-]+?)(?: \(([^)]{{1,40}})\))?")
# a roster NAME anywhere in a kind field: words of two or more capitals, joined by a space, hyphen or apostrophe, not
# inside a lower-case word, with an optional qualifier in brackets («LEMAIRE (René)», «DE BEAUFRONT»)
NAMED = re.compile(rf"(?<![\w])([{_UP}]{{2,}}(?:(?: |-|'|’)[{_UP}]{{2,}})*)(?![\w])(?: \(([^)]{{1,40}})\))?")

def anchor_of(fact):
    """The anchor of a format-2-shaped fact (its last «…»), else the fact: the key of «the same line»."""
    q = QUOTE.findall(fact)
    return q[-1] if q else fact

HCROSS = re.compile(r"^(aliĝo|foriro): (Esperanto|Ido|Occidental|Novial)\b")
COLLECTION = re.compile(r"originala|verkaro|leteroj|antologio|krestomatio", re.I)
WITNESS_UNTIL = 1939      # rule 2: an item written in 1939 or before is a witness's (the editor, 2026-10-15)

def hostile_labels(now, refs, every):
    """The hostile-witness label, line by line (the proposal's rule, as settled 2026-10-15): the line's item has a side
    (tools/item-sides.py: its language; «hostile» = Occidental, Novial, Latino sine flexione), the piece was written in
    1939 or before (the line's «derivita ↤» year, else the item's year; a collection without the first, no label), and
    the person was on another side than the venue's at the line's date, by their own crossing lines («aliĝo» or
    «foriro», of Esperanto, Ido, Occidental, Novial) keyed by surname and qualifier; undated lines, a span the sources
    dispute, and a person without crossing lines get none. -> ({index in refs: «Esperanto 1912»}, counts)."""
    sp = sorted(glob.glob(os.path.join(GEN, "ocr", "method", "ITEM-SIDES-*.tsv")))
    if not sp: return {}, {"no side table": 1}
    side = {r[0]: r[1] for r in (l.rstrip("\n").split("\t") for l in open(sp[-1], encoding="utf-8") if not l.startswith("#")) if len(r) > 1}
    year = {}
    tp = os.path.join(GEN, "OCR-ITEM-TABLE.tsv")
    if os.path.exists(tp):
        for r in csv.DictReader((l for l in open(tp, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            m = re.match(r"(1[89]\d\d|20\d\d)", r.get("year") or "")
            if m: year[r["item"]] = int(m.group(1))
    def pkey(k):           # person: surname and qualifier, from the raw line
        who, line = every[k][2], every[k][3]
        mq = re.match(r"^- \$\$\$ [^$]*?(?:\(([^)]*)\))?\s*\$\$\$\s*(?:\(([^)]*)\))?", line)
        mw = re.search(r"\(([^)]*)\)", who)   # (an unclosed «(» in a name, OGE 2026-10-25, no longer stops the check)
        q = ((mq.group(1) or mq.group(2)) if mq else None) or (mw.group(1) if mw else "")
        return (re.sub(r"\s*\(.*", "", who), (q or "").strip().lower())
    def years(d):
        ys = [int(x) for x in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", d or "")]
        return (min(ys), max(ys)) if ys and "sen dato" not in d and "ĝenerala" not in d else None
    ev = defaultdict(list)
    for k, (who, i, j) in enumerate(refs):
        kind = now[j][5] if len(now[j]) > 5 else ""
        m = HCROSS.match(kind or "")
        yy = years(now[j][2])
        if m and yy: ev[pkey(k)].append((yy[0], m.group(1), m.group(2)))
    def norm(l): return "hostile" if l in ("Occidental", "Novial") else l
    def side_at(p, y):
        es = sorted(ev.get(p, []))
        if not es: return None
        ido = [e[0] for e in es if e[1] == "aliĝo" and e[2] == "Ido"]
        if ido and max(ido) - min(ido) > 1 and min(ido) <= y <= max(ido): return None      # the crossing disputed
        s, seen = None, False
        for ye, verb, lang in es:
            if ye > y: break
            seen = True
            if verb == "aliĝo": s = norm(lang)
            elif s == norm(lang): s = None
        if not seen and es[0][1] == "foriro": s = norm(es[0][2])     # was there before leaving
        return s
    out, st = {}, Counter()
    for k, (who, i, j) in enumerate(refs):
        yy = years(now[j][2])
        if not yy: continue
        ms = locators(now[j][3]) or []
        if not ms: st["no item"] += 1; continue
        line = every[k][3]
        dy = re.search(r"derivita[^;)]*?\b(1[6-9]\d\d)\b", line)
        for mm in ms:
            item = mm.group("item").strip()
            v = side.get(item)
            if v not in ("Esperanto", "Ido", "hostile"): continue
            # the piece's year: the item's own (the item table, else a year in its name); in a collection, the year of the
            # piece the line cites («derivita ↤ … 1905»), and none without it. An item of unknown year: no label (a book
            # of 2018 citing a document of 1889 is not an 1889 witness: the witness is the document, whose side it is not)
            iy = year.get(item) or next((int(x) for x in re.findall(r"(1[89]\d\d|20[0-2]\d)", item)), None)
            py = (int(dy.group(1)) if dy else None) if COLLECTION.search(item) else iy
            if not py or py > WITNESS_UNTIL: continue
            p = pkey(k)
            a, b = side_at(p, yy[0]), side_at(p, yy[1])
            if a is None or a != b or a == v: continue
            out[k] = f"{v} {py}"; st[v] += 1; HOSTILE_SHOWN.append(f"{every[k][0]}:{every[k][1]}: {who} ({p[1]}) · {now[j][2]} · {v} {py} · {item}"); break
    return out, st
HOSTILE_SHOWN = []

def scope_out():
    """The people the scope register has out (profiles/SCOPE-REGISTER.tsv, proposed or confirmed): {(slug, qualifier
    or None)}. An unqualified row puts the surname out; a qualified row only that person (2026-10-14: one Zamenhof's
    row must not put every Zamenhof out)."""
    p = os.path.join(GEN, "profiles", "SCOPE-REGISTER.tsv")
    if not os.path.exists(p): return set()
    rows = [l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8") if not l.startswith("#")]
    out = set()
    for r in rows[1:]:
        if len(r) > 4 and r[4] == "out":
            m = re.match(r"^(.*?)\s*(?:\(([^)]*)\))?\s*$", r[0].strip())
            out.add((slug(m.group(1)), (m.group(2) or "").strip().lower() or None))
    return out

def scope_entities():
    """The register's entities (movement «entity», verdict «out»: bodies, periodicals, events, documents, a language; the
    editor, 2026-10-16): {slug}. Out like a person,
    so no copies and no dowse; but their lines are no fault, so the scope warning leaves them out."""
    p = os.path.join(GEN, "profiles", "SCOPE-REGISTER.tsv")
    if not os.path.exists(p): return set()
    rows = [l.rstrip("\n").split("\t") for l in open(p, encoding="utf-8") if not l.startswith("#")]
    return {slug(re.sub(r"\s*\(.*", "", r[0])) for r in rows[1:] if len(r) > 4 and r[1] == "entity" and r[4] == "out"}

def out_of_scope(name, qual, OUT):
    """By the register: the surname out (an unqualified row), or this qualifier out (one begins the other)."""
    k, q = slug(name), (qual or "").strip().lower()
    if (k, None) in OUT: return True
    return bool(q) and any(rk == k and rq and (q.startswith(rq) or rq.startswith(q)) for rk, rq in OUT)

LIFE_DROPS = []
def life_guess_drops(people):
    """A page guess outside the person's life is dropped (2026-10-17, the resmelt's faults T3: Schneeberger's joining Ido
    and his 18 years in it guessed «ĉ. 1937 laŭ la paĝo 73», after his death in 1926; Couturat's acts guessed «≥ 1928»,
    he died in 1914; the editor's rule of 2026-10-12, «wrong date worse than missing date»). Only a guess from the page
    («laŭ la paĝo»), only on a line of the person's own acts: a judgement, claim or character line (SAYING_KINDS) may come
    after his death, and a copy («⟦kopio el …⟧») may be another's act. The life: the earliest dated «naskiĝo» and «morto»
    lines of the profile. A guess wholly after the death, or wholly before the birth, becomes «[sen dato]»."""
    def y(d):
        m = re.search(r"(1[6-9]\d\d|20\d\d)", d); return int(m.group(1)) if m and "sen dato" not in d and "divene" not in d else None
    # one life for each first-name qualifier of a surname («**(Vsevolod)**», «**(Ivan Markoviĉ)**»: 2026-10-17u, the two
    # Lojkos of Ruslanda Esperantisto, one's death capping the other's guesses); a line with no qualifier, where the
    # surname has several, is not capped
    qual = lambda r: (m.group(1) if (m := re.match(r"\s*\*\*\(([^)]*)\)\*\*", r[1])) else None)
    for w, rs in people.items():
        lives = defaultdict(lambda: {"naskiĝo": [], "morto": []})
        for r in rs:
            kd = KINDS.get((r[-1], r[2], r[1], slug(w)), "")
            k = kd.split(":")[0].strip()
            if k in ("naskiĝo", "morto") and y(r[0]) and "kopio el" not in r[4]: lives[qual(r)][k].append(y(r[0]))
        if not lives: continue
        quals = {qual(r) for r in rs} - {None}
        for i, r in enumerate(rs):
            q = qual(r)
            if q is None and quals: continue
            life = lives.get(q, {"naskiĝo": [], "morto": []})
            # the death by the latest «morto» line, not the earliest (2026-10-17u, smelt S5: Zamenhof's guesses of
            # 1907–1913 dropped as after his death, by a «morto» line under him that is another's death); a later one
            # can only spare a guess
            born, died = min(life["naskiĝo"], default=None), max(life["morto"], default=None)
            if born is None and died is None: continue
            d = r[0]
            # a guess from the page or from a periodical's issue (2026-10-17u: an issue of 1907 says nothing of when a man
            # dead in 1885 acted)
            if "divene" not in d or not ("laŭ la paĝo" in d or "laŭ la numero" in d) or "kopio el" in r[4]: continue
            kd = KINDS.get((r[-1], r[2], r[1], slug(w)), "")
            if kd.split(":")[0].strip() in SAYING_KINDS | {"interpreto", "historiografio"}: continue
            lo = re.search(r"(?:≥|ĉ\.)\s*(\d{4})", d); hi = re.search(r"(?:≤|ĉ\.)\s*(\d{4})", d)
            if (died and lo and int(lo.group(1)) > died) or (born and hi and int(hi.group(1)) < born):
                LIFE_DROPS.append(f"{w}: {d} · {r[1][:80]} · {r[2]}")
                rs[i] = ("[sen dato]",) + r[1:]

def copies(people, tocopy, now):
    """Write the copies into people and now; -> (number written, skip counts)."""
    skips = {"there": 0, "nolines": 0, "names": Counter(), "kun": 0, "out": 0, "notname": 0,
             "named": 0, "named_nolines": 0, "named_out": 0, "named_to": Counter(), "family": 0}
    OUT = scope_out()
    own = {slug(w) for w in people}
    held = {(r[5], slug(w), r[2], anchor_of(r[1])) for w, rows in people.items() for r in rows}
    def persons_in(kind):
        """(kind, person) pairs a kind field names: `renkonto: A kaj B, …; +konflikto: C` -> (renkonto, A), (renkonto, B), (konflikto, C)."""
        heads = [x.strip() for x in kind.split(";")]
        for h in [heads[0]] + [x[1:].strip() for x in heads[1:] if x.startswith("+")]:
            k, _, obj = h.partition(":")
            seg, tail = re.match(r"^(.*?)((?:\s*[,:].*)?)$", obj.strip()).groups()
            parts = re.split(r"\s+kaj\s+", seg)
            yield k.strip(), parts, [OBJ_PERSON.fullmatch(p) for p in parts], tail
    # the same line written by the reader under another quotation: same file, place and kind, naming the first person
    named = {(fn, slug(who), people[who][idx][2], k, slug(canon(m.group(1).strip())))
             for fn, who, idx, kind, line in tocopy for k, parts, ms, tail in persons_in(kind) for m in ms if m}
    n = 0
    for fn, who, idx, kind, line in tocopy:
        date, fact, src, th, conf, frm = people[who][idx]
        q0 = re.match(r"\*\*\(([^)]*)\)\*\* ", fact)
        bare = fact[q0.end():] if q0 else fact
        me = f"{who}{f' ({q0.group(1)})' if q0 else ''}"
        for k, parts, ms, tail in persons_in(kind):
            if k not in COPY_KINDS or not all(ms): continue
            for i, m in enumerate(ms):
                name, qual = m.group(1).strip(), m.group(2)
                if name in FACT_KEYS and not qual: name, qual = FACT_KEYS[name]
                name = canon(name)
                if slug(name) == slug(who): continue
                if slug(name) not in own:
                    skips["nolines"] += 1; skips["names"][name] += 1; continue
                if (frm, slug(name), src, anchor_of(fact)) in held or (frm, slug(name), src, k, slug(who)) in named:
                    skips["there"] += 1; continue
                others = "".join(f" kaj {parts[j]}" for j in range(len(parts)) if j != i)
                ckind = f"{k.strip()}: {me}{others}{tail}"
                cfact = f"**({qual})** {bare}" if qual else bare
                mark = f"⟦kopio el {me}⟧"
                cconf = conf[:-1] + f"; {mark})" if conf.rstrip().endswith(")") else f"{conf} ({mark})"
                people[name].append((date, cfact, src, th, cconf, frm))
                KINDS[(frm, src, cfact, slug(name))] = ckind
                held.add((frm, slug(name), src, anchor_of(fact)))   # «named» keeps only the readers' own lines: a copy
                # must not block the copy of another fact at the same place (the Jossinet ¶ 31 test, 2026-10-13)
                cline = re.sub(r"^- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))?", f"- $$$ {name}{f' ({qual})' if qual else ''} $$$", line.strip())
                now.append([fn, name, date, src, cline, ckind])
                n += 1
        # CO-SUBJECTS (the editor 2026-10-13 22:4x
        #): `…; kun: A kaj B` names the others who did the same thing. Each gets the line, the kind
        # unchanged, «kun:» naming the rest. Copied unless the scope register has the person out; a person with no lines
        # of their own is copied too (inclusion).
        kun = next((x.strip()[4:].strip() for x in kind.split(";")[1:] if x.strip().startswith("kun:")), None)
        if kun:
            parts = [x.strip() for x in re.split(r"\s+kaj\s+", kun)]
            base = ";".join(x for x in kind.split(";") if not x.strip().startswith("kun:")).strip()
            for i, part in enumerate(parts):
                m = OBJ_PERSON.fullmatch(part)
                if not m: skips["notname"] += 1; continue
                name, qual = m.group(1).strip(), m.group(2)
                if name in FACT_KEYS and not qual: name, qual = FACT_KEYS[name]
                name = canon(name)
                if slug(name) == slug(who): continue
                if out_of_scope(name, qual, OUT): skips["out"] += 1; continue
                if (frm, slug(name), src, anchor_of(fact)) in held: skips["there"] += 1; continue
                ckind = f"{base}; kun: " + " kaj ".join([me] + [parts[j] for j in range(len(parts)) if j != i])
                cfact = f"**({qual})** {bare}" if qual else bare
                mark = f"⟦kopio el {me}⟧"
                cconf = conf[:-1] + f"; {mark})" if conf.rstrip().endswith(")") else f"{conf} ({mark})"
                people[name].append((date, cfact, src, th, cconf, frm))
                KINDS[(frm, src, cfact, slug(name))] = ckind
                held.add((frm, slug(name), src, anchor_of(fact)))
                cline = re.sub(r"^- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))?", f"- $$$ {name}{f' ({qual})' if qual else ''} $$$", line.strip())
                now.append([fn, name, date, src, cline, ckind])
                n += 1; skips["kun"] += 1
        # EVERY PERSON THE KIND NAMES (2026-10-16; the editor
        # the De Beaufront smelt: Lemaire's lines on the tomb, the manuscripts
        # and the call after the death named DE BEAUFRONT in the kind and reached only Lemaire): any line whose kind names
        # another roster person in capitals, inside a phrase too («la tombo de DE BEAUFRONT»), whatever the kind, is
        # copied under that person, the line as written, the kind not swapped. Not to a person with no lines of their
        # own («if a person is only ever mentioned as an object and not a subject, they do not get a profile»), nor to
        # one the scope register has out (entities go out there, reason «entity»); the meetings' and «kun:»'s copies above
        # come first, and a line already held there is not copied twice.
        base = ";".join(x for x in kind.split(";") if not x.strip().startswith("kun:"))
        for m in NAMED.finditer(base):
            name, qual = m.group(1).strip(), m.group(2)
            if name in FACT_KEYS and not qual: name, qual = FACT_KEYS[name]
            name = canon(name)
            if slug(name) == slug(who): continue
            if slug(name) not in own: skips["named_nolines"] += 1; continue
            if out_of_scope(name, qual, OUT): skips["named_out"] += 1; continue
            # the same anchor at the same place only: the meetings' wider test («the same kind naming the first person»)
            # took Lemaire's call after the death (Jossinet ¶ 7) for De Beaufront's own line on their friendship there
            if (frm, slug(name), src, anchor_of(fact)) in held:
                skips["there"] += 1; continue
            # a relational kind turned round in the copy: this copy kept the kind as it is, and so named the person as his
            # own opponent (2026-10-17, the resmelt's fault T5: Bourlet's L24, «konflikto: BOURLET kaj CART», a copy from
            # De Beaufront's line; the relational copy above had skipped it, the reader having written a «konflikto»
            # naming De Beaufront on the same page). In a head of a relational kind, the person copied to becomes the
            # person copied from; other kinds keep their object («la tombo de DE BEAUFRONT» stays)
            ckind_named = kind
            heads = kind.split(";")
            for hi_, h in enumerate(heads):
                hk = (h.strip()[1:] if h.strip().startswith("+") else h).split(":")[0].strip()
                if hk in COPY_KINDS and re.search(r"(?<![\w-])" + re.escape(m.group(1).strip()) + r"(?![\w-])", h):
                    heads[hi_] = re.sub(r"(?<![\w-])" + re.escape(m.group(1).strip()) + r"(?: \([^)]*\))?(?![\w-])", me, h, count=1)
            ckind_named = ";".join(heads)
            cfact = f"**({qual})** {bare}" if qual else bare
            mark = f"⟦kopio el {me}⟧"
            cconf = conf[:-1] + f"; {mark})" if conf.rstrip().endswith(")") else f"{conf} ({mark})"
            people[name].append((date, cfact, src, th, cconf, frm))
            KINDS[(frm, src, cfact, slug(name))] = ckind_named
            held.add((frm, slug(name), src, anchor_of(fact)))
            cline = re.sub(r"^- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))?", f"- $$$ {name}{f' ({qual})' if qual else ''} $$$", line.strip())
            now.append([fn, name, date, src, cline, ckind_named])
            n += 1; skips["named"] += 1; skips["named_to"][name] += 1
    # A FAMILY'S LINES TO ITS MEMBERS (FAMILIES above): every line of the group, of any format, copied under each member
    # with a profile, the member's qualifier in place of the group's; not where the member already has a line with the
    # same anchor at the same place
    for sur, groups in FAMILIES.items():
        who = next((w for w in people if slug(w) == slug(sur)), None)
        if not who: continue
        rows = list(people[who])
        for pref, members in groups:
            for date, fact, src, th, conf, frm in rows:
                q0 = re.match(r"\*\*\(([^)]*)\)\*\* ", fact)
                if not q0 or not q0.group(1).startswith(pref): continue
                bare = fact[q0.end():]
                for mq in members:
                    mine = {(r[5], r[2], anchor_of(r[1][re.match(r"\*\*\([^)]*\)\*\* ", r[1]).end():] if re.match(r"\*\*\([^)]*\)\*\* ", r[1]) else r[1]))
                            for r in people[who] if r[1].startswith(f"**({mq}")}
                    if (frm, src, anchor_of(bare)) in mine: skips["there"] += 1; continue
                    mark = f"⟦kopio el {sur} ({q0.group(1)})⟧"
                    cconf = conf[:-1] + f"; {mark})" if conf.rstrip().endswith(")") else f"{conf} ({mark})"
                    people[who].append((date, f"**({mq})** {bare}", src, th, cconf, frm))
                    now.append([frm, who, date, src, f"- $$$ {sur} $$$ **{date}** · **({mq})** {bare} · {src} · {cconf}", ""])
                    n += 1; skips["family"] += 1
    return n, skips

def to2(line):
    """A format-3 line -> the same line in format-2 shape: «fact «anchor» · locator · …»."""
    m = re.match(r"(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,40}\))? \*\*[^*]+\*\* · )(.*)$", line.rstrip())
    if not m: return line
    parts = m.group(2).split(" · ")
    if len(parts) < 5: return line
    fact, anchor = " · ".join(parts[:-4]), parts[-4]
    return m.group(1) + f"{fact} «{anchor}» · " + " · ".join(parts[-3:])
LOC2 = re.compile(r"^(?P<item>[^,·]+?), (?:PDF (?P<pdf>\d+)(?: \(prese [^)]+\))?|¶ (?P<para>\d+))(?:, .+)?$")
NOVELTY_MARK = re.compile(r"\bNOVA\b|jam registrita|⟳|⟵")
# EVERY FACTS LINE STANDS ALONE (the editor 2026-10-11
#): a format-2 line whose fact opens by pointing back at another line, or names issue or article
ANAPHOR = re.compile(r"^(same\b|la sama\b|en (tiu|la sama|tiu ĉi)\b|tiu\b|tio\b|tiam\b|poste\b|ĝi\b|ili\b)|"
                     r"\b(la sama|tiu ĉi|tiu) (numero|revuo|gazeto|artikolo|libro|letero|recenzo|poemo|kunsido|broŝuro|teksto)\b|"
                     r"\bsimil(?:a|an|aj|ajn|e)\b", re.I)   # comparison words too (the editor)
INDEP = re.compile(r"\bsendependa\b|\bderivita\b|\bsen fontindiko\b")
QUOTE = re.compile(r"«([^«»]*(?:«[^»]*»[^«»]*)*)»")
BUILD = os.path.join(OUT, "build")
_items = None

def item_table():
    """item key -> kind (PRIMARY / SECONDARY / ''), from Miles's generated item table."""
    global _items
    if _items is None:
        p = os.path.join(GEN, "OCR-ITEM-TABLE.tsv")
        with open(p, encoding="utf-8") as fh:
            _items = {r["item"]: (r.get("kind") or "") for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")}
    return _items

_rows, _langs = None, None

def item_rows():
    """item key -> its whole row in Miles's item table (written, kind, …)."""
    global _rows
    if _rows is None:
        with open(os.path.join(GEN, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
            _rows = {r["item"]: r for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")}
    return _rows

def item_language(item):
    """item key -> its main language, from the newest OCR-TEXT-LANGUAGES table ('' if unknown)."""
    global _langs
    if _langs is None:
        _langs = {}
        tabs = sorted(glob.glob(os.path.join(GEN, "OCR-TEXT-LANGUAGES-20*.tsv")))
        for l in (open(tabs[-1], encoding="utf-8") if tabs else []):
            x = l.rstrip("\n").split("\t")
            if not l.startswith("#") and len(x) > 1 and x[0] != "item": _langs[x[0]] = x[1].split(",")[0]
    return _langs.get(item, "")

def source_info(source):
    """(item, written year as int or None, kind, language) for a line's first locator, when it names an item key.
    The Fable review's S5/S6 (2026-10-10): source dates and kinds come from the item table, not from dowse order."""
    ms = locators(source)
    if not ms: return ("", None, "", "")
    # the row by the item's name, else by its key (2026-10-17u, smelt S5: the locators of Ruslanda Esperantisto name the
    # key «ruslandaesperantisto1905-5», the table's item is «RuslandaEsperantisto1905.5»; looked up by the key alone, all
    # 32 issues had no year, so no saying there was dated and no page guess capped)
    it = ms[0].group("item").strip(); r = item_rows().get(it) or item_rows().get(key_names().get(it, ""), {})
    m = re.search(r"(1[6-9]\d\d|20\d\d)", r.get("written", "") or "")
    lang = item_language(it)
    # A page dated by its issue (a file holding several years: Miles's tools/ocr-page-dates.py, 2026-10-10 22:12, on the
    # editor's to dating a hit by its page's issue) gives the year, and the kind follows from it by the cutoffs:
    # 1914 inclusive; before 1931 for Ido, Occidental, Novial and Latino sine flexione (geniza/QUEUE.md, 1914 INCLUSIVE and
    # OCCIDENTAL CUTOFF; the board, 2026-10-11 03:1x).
    pdf = ms[0].group("pdf")
    py = page_dates().get((it, int(pdf))) if pdf else None
    if py:
        late = py >= 1931 if lang in ("ido", "occidental", "novial", "latino-sine-flexione") else py >= 1915   # Peano's: the board, 2026-10-11 03:1x
        return (it, py, "SECONDARY" if late else "PRIMARY", lang)
    return (it, int(m.group(1)) if m else None, r.get("kind", "") or "", lang)

_issues = None
def issue_year(source):
    """The year of the periodical issue a line's first locator names, or None: an item whose title_key the item table
    gives to two or more items is an issue of a run. The editor, 2026-10-17, on Ruslanda Esperantisto
     (the dowse runbook, D6c
    )."""
    global _issues
    if _issues is None:
        from collections import Counter
        _issues = {k for k, n in Counter((r.get("title_key") or "").strip() for r in item_rows().values()).items() if k and n > 1}
    ms = locators(source)
    if not ms: return None
    it = ms[0].group("item").strip(); r = item_rows().get(it) or item_rows().get(key_names().get(it, ""), {})
    return source_info(source)[1] if (r.get("title_key") or "").strip() in _issues else None

_pdates = None
def page_dates():
    """(item, PDF page) → year of the issue the page belongs to, from the newest geniza/ocr/runs/OCR-PAGE-DATES-*.tsv."""
    global _pdates
    if _pdates is None:
        _pdates = {}
        tabs = sorted(glob.glob(os.path.join(GEN, "ocr", "runs", "OCR-PAGE-DATES-*.tsv")))
        for l in (open(tabs[-1], encoding="utf-8") if tabs else []):
            x = l.rstrip("\n").split("\t")
            if l.startswith("#") or x[0] == "item" or len(x) < 3 or not x[2].isdigit(): continue
            _pdates[(x[0], int(x[1]))] = int(x[2])
    return _pdates

def independence(conf):
    """The independence label in a confidence field, with the cited work after «↤» if any ('' if none)."""
    m = re.search(r"(sendependa|derivita, fonto nevidita|derivita|sen fontindiko)(\s*↤\s*[^;)]+)?", conf)
    return m.group(0).strip() if m else ""

def item_pages(item, fid):
    """The OCR text (pages) or born-digital text (¶ as pages) of an item, or None."""
    p = os.path.join(GEN, "sources", "ocr-preferred", item + ".txt")
    b = os.path.join(GEN, "sources", "born-digital-text", item + ".txt")
    if os.path.exists(p): return fid.load_pages(p)
    if os.path.exists(b):
        # A PAGED BORN-DIGITAL TEXT (2026-10-26: Couturat's typed PDF and the Beauchemin transcriptions, «=== page N ===»,
        # cited «PDF N»; read as paragraphs, «PDF 5» was looked up as the fifth paragraph, and the accuracy sample found
        # none of its 40 anchors): by its pages, as a scan's text
        if re.search(r"^=== page \d+ ===", open(b, encoding="utf-8").read(), re.M): return fid.load_pages(b)
        paras = [x for x in open(b, encoding="utf-8").read().split("\n\n") if x.strip()]
        return {i + 1: x.split() for i, x in enumerate(paras)}
    return None

def segments(fact, last=False):
    """Every part of every quotation, split at «…» with [insertions] dropped: lists of words. last=True: only the last
    quotation (a format-3 line's anchor, see to2)."""
    out = []
    qs = QUOTE.findall(fact)
    for q in (qs[-1:] if last else qs):
        # THE SOURCE'S OWN BRACKETS (2026-10-21; the editor): a quotation that is nothing but a bracketed
        # passage is the source's print, not our insertion («[Gazeta eltranĉo, sendita de W. H. Trompeter.]», La
        # Esperantisto 1893, PDF 29, held back as having no words): its words count. An insertion of ours always stands
        # beside the source's own words, and is dropped as before
        nb = re.sub(r"\[[^\]]*\]", " ", q)
        if not re.search(r"\w", nb.replace("⟨fino⟩", "")): nb = q.replace("[", " ").replace("]", " ")
        for seg in re.split(r"…|\.\.\.", nb):
            # ⟨fino⟩ pads an anchor from a text under six words (a title, a caption) to six (the editor, 2026-10-14:
            #): it counts as a word
            # for the six, and is not sought on the page
            ws = [w for w in seg.split() if w != "⟨fino⟩"]
            if ws: out.append(ws)
    return out

def locators(source):
    """The locators of a source field, or None if any part is not in the ruled form. Several are separated by «;»: a fact
    found in a work and in its copies (a translation, another edition: COPIES, Miles 2026-10-10, «one line with two
    locators»), e.g. `esenco-…, ¶ 12; reu-sbornik-1909, PDF 34`. The split happens only where a locator follows."""
    # a line written before 2026-10-21 with an item name a locator cannot carry («Zakrzewski - Historio de Esperanto,
    # 1913»): the name read as its key (expand_lean now writes the key)
    for n, k in unsafe_names().items():
        if n in source: source = source.replace(n + ",", k + ",")
    parts = re.split(r"\s*;\s*(?=[^,;·]+, (?:PDF \d|¶ \d))", source)
    # AN ITEM KEY READS AS ITS ITEM (2026-10-17; the item-key reform, the editor; the
    # keys assigned by Miles 2026-10-16 23:21 in OCR-ITEM-KEYS.tsv, the table's «key» column): a locator may name the item
    # by its key (`neves-parnaso-ido-2018, PDF 8`) or, in the older lines, by its file name; every lookup here and in the
    # tools that read locators through this function (line_fields.py, smelt-view.py) gets the file name
    k2n = key_names(); ms = []
    for p in parts:
        h = p.split(",")[0].strip()
        if h in k2n and re.search(r"[,;·«»]", k2n[h]):     # matched by the key, read as the name (2026-10-21)
            m = LOC2.match(p); ms.append(_NamedLoc(m, k2n[h]) if m else None)
        else:
            ms.append(LOC2.match(k2n[h] + p[len(p.split(",")[0]):] if h in k2n else p))
    return ms if all(ms) else None

class _NamedLoc:
    """A locator matched by its item's key whose item reads as the file name: a name LOC2 cannot match («Zakrzewski -
    Historio de Esperanto, 1913», its comma), so that every caller of locators() still gets the file name."""
    def __init__(self, m, item): self.m, self.item = m, item
    def group(self, *g): return self.item if g == ("item",) else self.m.group(*g)
    def __getattr__(self, a): return getattr(self.m, a)

def copy_works():
    """COPIES of tools/ocr-dowse.py, read as data (parsed, never imported, so nothing of that tool runs): [(work, [(item,
    stretch or None)], [set of items holding one text])]."""
    import ast
    src = open(os.path.join(REPO, "tools", "ocr-dowse.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "COPIES" for t in node.targets):
            return [(e["work"], [(c[0], c[1]) for c in e["copies"]], [set(g) for g in e.get("same_text", [])])
                    for e in ast.literal_eval(node.value)]
    return []

COPY_MERGED = []   # (person, kept row, dropped row, "two copies" | "two texts"), for the review document
COPY_SEEN = Counter()   # (work, item) -> lines placed there, for the review document

def merge_copies(people):
    """ONE FACT IN TWO COPIES, OR IN TWO TEXTS OF ONE WORK (2026-10-20; the doubles method, ocr/method/DOWSE-DOUBLES-METHOD-
    PROPOSAL-2026-10-20.md, APPROVED; the editor to the fact files keeping both lines): two lines of one
    person, under two different items of one COPIES work (each locator's page inside its copy's stretch), of one kind,
    whose facts without their anchors share 80% of their content words and differ in no number but a year (the rule of
    duplicate_pairs, less its one page), become ONE line in the profile: the first line's text, its locator and the
    other's («A; B», the form locators() reads), and a label: «du kopioj de unu teksto» for a same_text group (kind 1),
    else «du tekstoj de unu verko» (kind 0: editions, translations). Counted once, not as corroboration. The fact files
    and FACTS-LIST keep both lines. -> merged count. Each merge listed in COPY_MERGED for COPIES-MERGED-LATEST.md."""
    works = copy_works()
    if not works: return 0
    k2n = key_names()
    def name(it): return k2n.get(it, it)
    def works_of(src):
        """every work one of whose copies holds the locator's item and page (a scan can hold several works: Originala
        Verkaro whole, and its stretches that are the Aldono, the Fundamento's Antaŭparolo …)"""
        ms = locators(src)
        if not ms or len(ms) != 1: return [], None
        it, pg = name(ms[0].group("item").strip()), int(ms[0].group("pdf") or ms[0].group("para"))
        return [w for w, (_t, cps, _g) in enumerate(works)
                if any(name(c) == it and (stretch is None or stretch[0] <= pg <= stretch[1]) for c, stretch in cps)], it
    def cwords(t):
        return {w for w in re.findall(r"[\wĉĝĥĵŝŭĈĜĤĴŜŬ]{4,}", t.lower())} - {"estis", "kiam", "laŭ", "sian", "siaj", "lian", "liaj", "kiun", "kiuj", "ankaŭ", "post", "antaŭ", "inter", "dum", "ĉar"}
    def bare(fact): return fact.rsplit(" «", 1)[0]
    n = 0
    for who, rows in people.items():
        by = defaultdict(list)
        for i, r in enumerate(rows):
            ws, it = works_of(r[2])
            for w in ws: by[w].append((i, it)); COPY_SEEN[(works[w][0], it)] += 1
        drop = set()
        for w, idx in by.items():
            if len({it for _i, it in idx}) < 2: continue
            for x in range(len(idx)):
                i, it_i = idx[x]
                if i in drop: continue
                for y in range(x + 1, len(idx)):
                    j, it_j = idx[y]
                    if j in drop or it_i == it_j: continue
                    ri, rj = rows[i], rows[j]
                    # THE SAME DATE (2026-10-20, the first real merge: Chalon, Pioniro's secretary in 1910 and his signature
                    # of its rules on 1907-02-21, two facts under one COPIES work, La Belga Sonorilo's whole run): the two
                    # lines agree in year, and in month where both give one; an undated line merges with none
                    ya, yb = re.search(r"(1[5-9]\d\d|20\d\d)(?:-(\d\d))?", ri[0] or ""), re.search(r"(1[5-9]\d\d|20\d\d)(?:-(\d\d))?", rj[0] or "")
                    if not ya or not yb or ya.group(1) != yb.group(1) or (ya.group(2) and yb.group(2) and ya.group(2) != yb.group(2)): continue
                    ki = KINDS.get((ri[5], ri[2], ri[1], slug(who)), ""); kj = KINDS.get((rj[5], rj[2], rj[1], slug(who)), "")
                    if ki.split(":")[0].strip() != kj.split(":")[0].strip(): continue
                    na, nb = set(re.findall(r"\d+", bare(ri[1]))), set(re.findall(r"\d+", bare(rj[1])))
                    if any(not re.fullmatch(r"1[6-9]\d\d|20\d\d", z) for z in na ^ nb): continue
                    a, b = cwords(bare(ri[1])), cwords(bare(rj[1]))
                    if not (len(a) >= 3 and len(b) >= 3 and len(a & b) / min(len(a), len(b)) >= 0.8): continue
                    one = any(it_i in g and it_j in g for g in works[w][2])
                    lab = "du kopioj de unu teksto" if one else "du tekstoj de unu verko"
                    rows[i] = (ri[0], ri[1], f"{ri[2]}; {rj[2]}", ri[3], f"{ri[4]} ⟦{lab}: {works[w][0]}⟧") + tuple(ri[5:])
                    COPY_MERGED.append((who, ri, rj, lab)); drop.add(j); n += 1
                    ri = rows[i]
        if drop: people[who] = [r for k, r in enumerate(rows) if k not in drop]
    return n

def duplicate_pairs(rows):
    """THE SAME FACT TWICE ON ONE PAGE (2026-10-16; the dowse runbook, D6 point 7, deduping kind (b); the editor;
    a function since 2026-10-17, so that tools/dowse-dedupe-prep.py finds the same pairs as the build's listing): two
    dowse lines of one person, one file and one place (item and page or ¶) and one kind whose facts, without their
    anchors, share 80% of their content words, copies left out (they repeat by design).
    rows: (file, person, date, source, line, kind) -> [(file, place, fact i, fact j, line i, line j)]."""
    def cwords(t):
        return {w for w in re.findall(r"[\wĉĝĥĵŝŭĈĜĤĴŜŬ]{4,}", t.lower())} - {"beaufront", "estis", "kiam", "laŭ", "sian", "siaj", "lian", "liaj", "kiun", "kiuj", "ankaŭ", "post", "antaŭ", "inter", "dum", "ĉar"}
    byplace = defaultdict(list)
    for fn, who, date, src, line_, kind_ in rows:
        if not fn.endswith("-dowse.md") or "kopio el" in line_: continue
        body = line_.split("** · ", 1)[1].split(" · ")[0] if "** · " in line_ else ""
        anchor = body.rsplit(" «", 1)[1].rstrip("»").strip() if " «" in body else ""
        body = body.rsplit(" «", 1)[0]          # the fact without its anchor: lines sharing one anchor looked alike
        byplace[(fn, slug(who), src.split(";")[0].strip())].append((body, line_, (kind_ or "").split(":")[0].strip(), anchor))
    OPINION = {"juĝo", "interpreto", "karaktero", "historiografio"}
    out = []
    for (fn, who_, src_), rs in byplace.items():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                # the same kind only: one sentence split one predicate per line («naskiĝis en 1876», «mortis en 1954»)
                # is two facts, not a duplicate. But the opinion kinds are one kind here (2026-10-17, the resmelt's
                # faults T7: one judgement of Korĵenkov written as «interpreto» and as «juĝo», one sentence of Jossinet
                # as «juĝo» and as «karaktero»), and one anchor under two kinds, one of them an opinion, is a candidate
                # too (Neves's «bela frunto», once «historiografio», once «nomo»); the dedupe reader decides
                ki, kj = rs[i][2], rs[j][2]
                same_anchor = rs[i][3] and rs[i][3] == rs[j][3] and (ki in OPINION or kj in OPINION)
                if ki != kj and not (ki in OPINION and kj in OPINION) and not same_anchor: continue
                if same_anchor and ki != kj:
                    out.append((fn, src_, rs[i][0], rs[j][0], rs[i][1], rs[j][1])); continue
                # facts that differ in a number other than a year are two entries (2026-10-16 23:3x, the editor:
                # approved): Neves's bibliography, PDF 90–99, «… volumo I, n-ro 4, p. 151–189» against n-ro 6, 8, 12 …,
                # 243 of his 267 pairs; a year that differs may be one fact with an error (Federn, 1929 against 1930)
                na, nb = set(re.findall(r"\d+", rs[i][0])), set(re.findall(r"\d+", rs[j][0]))
                if any(not re.fullmatch(r"1[6-9]\d\d|20\d\d", x) for x in na ^ nb): continue
                a, b = cwords(rs[i][0]), cwords(rs[j][0])
                if len(a) >= 3 and len(b) >= 3 and len(a & b) / min(len(a), len(b)) >= 0.8:
                    out.append((fn, src_, rs[i][0], rs[j][0], rs[i][1], rs[j][1]))
    return out

_keys = None
def key_names():
    """item key -> file name, for the keys that differ from their item's name (OCR-ITEM-TABLE.tsv, column «key»)."""
    global _keys
    if _keys is None:
        _keys = {}
        with open(os.path.join(GEN, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
            for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
                if (r.get("key") or "").strip() and r["key"].strip() != r["item"]: _keys[r["key"].strip()] = r["item"]
        # a key is safe in a locator or nothing is read (2026-10-21; the editor): ASCII lower case,
        # digits, «-»; the slug rule makes no other, but a pinned key (KEY_PINNED) is written by hand
        bad = [k for k in _keys if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", k)]
        if bad: sys.exit(f"refusing: OCR-ITEM-TABLE.tsv has {len(bad)} key(s) a locator cannot carry, first {bad[0]!r}")
    return _keys

_unsafe = None
def unsafe_names():
    """file name -> key, for the item names a locator cannot carry as they are (a comma, «;», «·» or a guillemet)."""
    global _unsafe
    if _unsafe is None:
        _unsafe = {n: k for k, n in key_names().items() if re.search(r"[,;·«»]", n)}
    return _unsafe

def item_key(item):
    """file name -> its key (the name itself where the table gives none)."""
    return next((k for k, n in key_names().items() if n == item), item)

def short_record_anchor(item, fact):
    """A record's entry is a few words: a census line, a death record's phrase (the Somme records, 2026-10-12). In a short
    born-digital text (under 400 words) an anchor under six words is still unique, so it passes if it occurs exactly once."""
    b = os.path.join(GEN, "sources", "born-digital-text", item + ".txt")
    if not os.path.exists(b):
        return False
    t = open(b, encoding="utf-8").read()
    qs = re.findall(r"«([^«»]+)»", fact)
    return bool(qs) and len(t.split()) < 400 and t.count(qs[-1]) == 1


def strict(rec, fmt3=False):
    """Format-2 checks for one parsed line -> reason or None (format 3: the anchor is the last quotation)."""
    who, year, fact, source, themes, conf = rec
    ms = locators(source)
    if not ms:
        return f"format 2: locator must be `<item>, PDF N (prese M)` or `<item>, ¶ N` (several separated by «;»); got {source!r}"
    for m in ms:
        if m.group("item").strip() not in item_table():
            return f"format 2: unknown item key {m.group('item').strip()!r} (not in OCR-ITEM-TABLE.tsv)"
    kind = item_table()[ms[0].group("item").strip()]       # the first locator is the work; the others its copies
    padded = any("⟨fino⟩" in q and len(q.split()) >= 6 for q in (QUOTE.findall(fact)[-1:] if fmt3 else QUOTE.findall(fact)))
    cited = re.search(r", l\. \d+\b", source) and segments(fact, last=fmt3)   # a short anchor on its cited line (2026-10-17)
    if not padded and not cited and not any(len(s) >= 6 for s in segments(fact, last=fmt3)) and not short_record_anchor(ms[0].group("item").strip(), fact):
        return "format 3: the anchor needs six or more words" if fmt3 else "format 2: needs a verbatim quotation «…» of six or more words"
    if NOVELTY_MARK.search(conf):
        return "format 2: no novelty marks (NOVA, jam registrita, ⟳, ⟵) — novelty is decided at the build"
    if kind == "SECONDARY" and not INDEP.search(conf):
        return "format 2: a secondary source's line needs an independence label (sendependa / derivita ↤ … / sen fontindiko)"
    return None

def _fid():
    """The quotation finder of tools/fact-ids.py (normalising, page loading, word-by-word search)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("fact_ids", os.path.join(REPO, "tools", "fact-ids.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def missing_facts(now, old_profiles, new_profiles):
    """Compare this build's fact lines with the last saved list; write the list and the report. Returns missing count."""
    os.makedirs(BUILD, exist_ok=True)
    lp, rp = os.path.join(BUILD, "FACTS-LIST.tsv"), os.path.join(BUILD, "MISSING-FACTS-LATEST.md")
    prev = []
    if os.path.exists(lp):
        with open(lp, encoding="utf-8") as fh:
            prev = [r for r in csv.reader(fh, delimiter="\t")][1:]
    raw_now = {r[4] for r in now}
    fid, pages_cache = None, {}
    def pages(item):
        if item not in pages_cache:
            p = os.path.join(GEN, "sources", "ocr-preferred", item + ".txt")
            b = os.path.join(GEN, "sources", "born-digital-text", item + ".txt")
            if os.path.exists(p): pages_cache[item] = fid.load_pages(p)
            elif os.path.exists(b) and re.search(r"^=== page \d+ ===", open(b, encoding="utf-8").read(), re.M):
                pages_cache[item] = fid.load_pages(b)   # a paged born-digital text, by its pages (2026-10-26, as item_pages)
            elif os.path.exists(b):      # born-digital: ¶ N counts paragraphs, headings included (Miles's reader)
                paras = [x for x in open(b, encoding="utf-8").read().split("\n\n") if x.strip()]
                pages_cache[item] = {i + 1: x.split() for i, x in enumerate(paras)}
            else: pages_cache[item] = None
        return pages_cache[item]
    span_cache = {}
    def spans(row):
        if row[4] not in span_cache: span_cache[row[4]] = _spans(row)
        return span_cache[row[4]]
    def _spans(row):
        out = []
        for m in (locators(row[3]) or []):                  # every locator: the work and its copies
            item, pg = m.group("item").strip(), int(m.group("pdf") or m.group("para"))
            pp = pages(item)
            if not pp: continue
            for seg in segments(row[4]):
                w = fid.norm(" ".join(seg)).split()
                if len(w) >= 3:
                    hit = fid.find(pp, pg, w)
                    if hit: out.append((item, hit[0], hit[1], hit[1] + len(w) - 1))
        return out or None
    def key(row):
        seg = segments(row[4])
        return (row[1], row[2], " ".join(seg[0][:6]) if seg else "")
    gone = [r for r in prev if r[4] not in raw_now]
    by_passage = by_key = 0
    missing = []
    if gone:
        fid = _fid()
        now_by_person = defaultdict(list)
        for r in now:
            now_by_person[r[1]].append(r)
        keys_now = {key(r) for r in now}
        for r in gone:
            sp = spans(r)
            if sp and any(any(a[0] == b[0] and a[1] == b[1] and b[2] <= a[3] and a[2] <= b[3]
                              for a in sp for b in (spans(q) or [])) for q in now_by_person[r[1]]):
                by_passage += 1
            elif key(r) in keys_now:
                by_key += 1
            else:
                missing.append(r)
    removed = sorted(old_profiles - new_profiles)
    with open(lp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t"); w.writerow(["file", "person", "year", "source", "line", "kind", "malamika"]); w.writerows(now)
    L = ["# Missing facts — the last build compared with the one before\n",
         "**GENERATED by `tools/harvest-facts.py` at every build. Do not edit.** Rulings: `geniza/QUEUE.md`, MISSING-FACTS and REISSUE.\n",
         (f"- previous build: {len(prev)} fact lines; this build: {len(now)}" if prev else f"- no previous list: this build ({len(now)} fact lines) is the baseline"),
         f"- lines no longer present word for word: {len(gone)}; of these, found again by passage: {by_passage}; by person + year + first quoted words: {by_key}",
         f"- **missing: {len(missing)}**; profile files no longer written: {len(removed)}", ""]
    if missing:
        L.append("## Missing, by source\n")
        bysrc = defaultdict(list)
        for r in missing: bysrc[r[0]].append(r)
        for fn in sorted(bysrc):
            L.append(f"### {fn} — {len(bysrc[fn])}\n")
            L += [f"- {r[4]}" for r in bysrc[fn]] + [""]
    if removed:
        L.append("## Profile files no longer written\n")
        L += [f"- {s}.md" for s in removed] + [""]
    with open(rp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"missing-facts report: {len(missing)} missing, {len(removed)} profile files gone → {os.path.relpath(rp, REPO)}")
    return len(missing)

class _Quiet:
    """--quiet (2026-10-15, no shell redirect or pipe to trim the output: the editor,): the counts and the errors only; the per-line warnings («    ⚠ …», «    · …») are left out."""
    def __init__(self, out): self.out, self.buf = out, ""
    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if not re.match(r"\s{3,}[⚠·] ", line): self.out.write(line + "\n")
    def flush(self): self.out.flush()

NAMETOK = r"[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬ][\wĉĝĥĵŝŭ'-]*\.?"
NAME_TITLE = re.compile(r"^(?:S-r[oi]|S-ino|F-ino|D-ro|Dro|Sro|Prof\.?|Profesoro|Sinjor(?:o|ino)|Inĝ\.?|Inĝeniero|Kapitano|"
                        r"Kolonelo|Generalo|Leŭtenanto|Pastro|Mr\.?|Mrs\.?|Dr\.?)$")   # not «M.»: also an initial
def given_runs(l, S):
    """The runs of given names and initials written right before the surname, a title in front left off: «A. F.» of «laŭ
    la iniciato de A. F. Postnikov», «A. A.» of «Kapitano A. A. Postnikov». The person is named by the run's FIRST name or
    initial; the ones after it are a patronymic or a second name (the editor, 2026-10-18, BEARERS-POSTNIKOV: the F. had been read as Fjodor)."""
    out = []
    for m in re.finditer(rf"(?<![\w-]){re.escape(S)}(?![\wĉĝĥĵŝŭ])", l, re.I):
        r = re.search(rf"((?:{NAMETOK}\s*)+)$", l[:m.start()])
        if not r: continue
        toks = re.findall(NAMETOK, r.group(1))
        out.append(" ".join(toks))
        while toks and NAME_TITLE.match(toks[0]): toks.pop(0)
        out.append(" ".join(toks))
    return [r for r in out if r]

def starts_run(run, p):
    """Does the run begin with the prefix «p» («F. A.» begins «F. A. Postnikov», not «A. F. Postnikov»; spaces ignored,
    «F.A.» = «F. A.»)?"""
    a, b = run.replace(" ", ""), p.replace(" ", "").rstrip(",")
    return a.lower().startswith(b.lower()) and (len(a) == len(b) or b.endswith(".") or not re.match(r"[\wĉĝĥĵŝŭ]", a[len(b)]))

def propose_bearers(surname):
    """--propose-bearers SURNAME (2026-10-16; the dowse runbook, D6 point 7, deduping (a), people; the editor; to the six inputs). Reads only; writes
    profiles/build/BEARERS-<SURNAME>.md. For each line of <surname>-ambiguous.md: a proposed bearer among the PERSONS
    table's people of that surname, «both» where the line names two of them, or none, with its cues and margin. Inputs:
    the line (its words, initials, year, file); each candidate's own profile (its words weighed against the others', its
    files, its years); the PERSONS table's descriptions and qualifier prefixes; the other lines of the same file already
    given to a candidate. Nothing is applied: the list is for the editor's ruling, a ruled line goes in by a qualifier or
    a DECISIONS row. NOT READ, AND IT SHOULD BE: the biography. was wrong: it
    places each bearer by period, where a profile only lists lines (the editor, 2026-10-18, on proposed for Fjodor). So
    the rulings wait for the bearers' biographies; reading them here is not built yet."""
    import math
    S = surname.upper()
    idx = os.path.join(OUT, f"{slug(S)}.md"); amb = os.path.join(OUT, f"{slug(S)}-ambiguous.md")
    if not (os.path.exists(idx) and os.path.exists(amb)): sys.exit(f"refusing: no index or ambiguous file for {S} in profiles/")
    rows = PERSONS.get(S, [])
    cands = []   # (label, prefixes, stem)
    links = dict(re.findall(r"\[([^\]]+)\]\(([^)]+)\.md\)", open(idx, encoding="utf-8").read()))
    for label, prefs in rows:
        if label.startswith("both") or "family" in label: continue
        stem = links.get(label)
        if stem: cands.append((label, prefs, stem))
    if len(cands) < 2: sys.exit(f"refusing: fewer than two people of {S} in the PERSONS table")
    WORD = re.compile(r"\b[A-ZÀ-ÖØ-ÞĈĜĤĴŜŬ][\wĉĝĥĵŝŭ'-]{3,}")
    def lines_of(p): return [l for l in open(p, encoding="utf-8") if l.startswith("- $$$")]
    def yrs(l):   # a real date only: a guess («[sen dato; divene ≤ 2005 laŭ la dato de la fonto]») is the source's year, not
        # the line's, and had docked Charles Lemaire for «a date after his death» (2026-10-16, Korĵenkov PDF 46)
        m = re.search(r"\*\*([^*]+)\*\*", l)
        if not m or "sen dato" in m.group(1) or "divene" in m.group(1): return []
        return [int(y) for y in re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", m.group(1))]
    fp = {}
    for label, prefs, stem in cands:
        ls = lines_of(os.path.join(OUT, stem + ".md"))
        words = Counter(w for l in ls for w in set(WORD.findall(l)) if w.upper() != S)
        files = Counter(m.group(1) for l in ls for m in [re.search(r"⟵ `([^`]+)`", l)] if m)
        # the run of files (its first two words: «belga-sonorilo-…»), the milieu a candidate's lines come from
        files.update("run:" + "-".join(re.findall(r"[a-z]+", m.group(1))[:2]) for l in ls for m in [re.search(r"⟵ `([^`]+)`", l)] if m)
        life = re.search(r"(1[89]\d\d)\s*[–-]\s*(1[89]\d\d)", label)
        span = (int(life.group(1)), int(life.group(2))) if life else None
        fp[label] = (words, files, len(ls), span, prefs)
    out, props = [], Counter()
    for l in lines_of(amb):
        cue = {label: [] for label, _, _ in cands}; score = Counter()
        f = re.search(r"⟵ `([^`]+)`", l); fn = f.group(1) if f else ""
        named = []
        runs = given_runs(l, S)
        for label, prefs, _ in cands:
            hits = [p for p in prefs if (any(starts_run(r, p) for r in runs) if p[:1].isupper()
                                         else re.search(rf"(?<!\w){re.escape(p)}\s+{re.escape(S)}", l, re.I))
                    or re.search(rf"\(\s*{re.escape(p)}\b", l)]
            if hits: named.append(label); score[label] += 5 * len(hits); cue[label].append("names " + "/".join(hits))
        ws = set(WORD.findall(l)) - {S.capitalize(), S}
        for w in ws:
            tot = sum(fp[c][0].get(w, 0) for c in fp)
            if not tot: continue
            for c in fp:
                share = (fp[c][0].get(w, 0) + 0.5) / (tot + 0.5 * len(fp))
                if share > 0.8 and fp[c][0].get(w, 0) >= 2: score[c] += math.log(share * len(fp)); cue[c].append(w)
        for c in fp:
            if fn and fp[c][1].get(fn): score[c] += 0.5 * math.log(1 + fp[c][1][fn]); cue[c].append(f"{fp[c][1][fn]} of its lines in this file")
            run = "run:" + "-".join(re.findall(r"[a-z]+", fn)[:2]) if fn else ""
            if run:   # its share of the lines of this run of files, against the others'
                tot_r = sum(fp[x][1].get(run, 0) for x in fp)
                if tot_r and fp[c][1].get(run, 0) / tot_r > 0.8 and fp[c][1][run] >= 5:
                    score[c] += 2; cue[c].append(f"{fp[c][1][run]} of the {tot_r} assigned lines of the run {run[4:]}")
            sp = fp[c][3]; ys = yrs(l)
            if sp and ys and (min(ys) > sp[1] + 1 or max(ys) < sp[0] + 15): score[c] -= 4; cue[c].append(f"date {ys[0]} outside his life {sp[0]}–{sp[1]}")
        census = bool(re.search(r"exact name-hits|FIRST dated appearance", l))
        said = bool(re.search(r"\((?:both|\w+ or \w+)[^)]*\)|undetermined|nedeterminit", l, re.I))   # the line says it is open
        ranked = sorted(score.items(), key=lambda x: -x[1])
        if len(named) >= 2 or census or said:
            prop = "both (split or leave)"
            why = ("the line itself says it is open" if said else "names two of them" if len(named) >= 2 else "a count of name-hits, which counts every bearer")
        elif ranked and ranked[0][1] >= 2 and (len(ranked) < 2 or ranked[0][1] - ranked[1][1] >= 2):
            prop = ranked[0][0].split(" (")[0]; why = "; ".join(cue[ranked[0][0]][:6])
        else:
            short = lambda k: k.split(" (")[0]
            prop = "leave"; why = "no clear margin" + (f" ({', '.join(f'{short(k)} {v:.1f}' for k, v in ranked[:2])})" if ranked else "")
        props[prop] += 1
        keep = "survives the redowse" if fn.endswith("-dowse.md") else "retired at its source's redowse"
        margin = f"{ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0):.1f}" if ranked else "0"
        body = re.sub(r"^- \$\$\$ [^$]+\$\$\$ ", "", l.strip())[:230]
        out.append(f"- **{prop}** · margin {margin} · {why} · {keep}\n  - {body} ⟵ `{fn}`")
    p = os.path.join(BUILD, f"BEARERS-{slug(S).upper()}.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(f"# Proposed bearers for the ambiguous lines of {S} — {len(out)} lines\n\n**GENERATED by `tools/harvest-facts.py --propose-bearers {S}`. "
                 "Do not edit.** **Deferred** (the editor, 2026-10-18): "
                 "not for ruling now; the dowse runbook, D6 point 7. Nothing applied. A ruled line takes its qualifier in its source file, or a DECISIONS row. "
                 f"Candidates: {'; '.join(c[0] for c in cands)}. Proposals: {', '.join(f'{k} {v}' for k, v in props.most_common())}.\n\n" + "\n".join(out) + "\n")
    print(f"{S}: {len(out)} ambiguous lines → {os.path.relpath(p, REPO)}; " + ", ".join(f"{k} {v}" for k, v in props.most_common()))
    return 0

DEDUPE_HEAD = """# {source}: la duoblaj linioj, por la juĝo ({tag})

`[Ezri, {tag}, per tools/harvest-facts.py --dedupe-brief {source} {tag}; the deduping proposal of 2026-10-17, (b) 3, signed by the editor : `geniza/ocr/method/DEDUPE-PROPOSAL-2026-10-17.md`. {n} pairs from `profiles/by-source/{source}-dowse.md` as it stands, found as the build's listing finds them (one person, one page, one kind, the facts without their anchors sharing 80% of their content words). The pairs below are read back by `--dedupe-rows`; do not edit them.]`

## La briefo

Vi estas legilo, kiu juĝas parojn da linioj el unu fonto. **Uzu nur la ilon Read.** Ĉiu paro estas du linioj de la sama persono, de la sama paĝo, de la sama speco, kies faktoj similas. Por ĉiu paro legu la du liniojn, kaj, kie la linioj mem ne sufiĉas, la paĝon en la teksto de la fonto (la teksto: {texts}; la paĝo staras en la lokindiko, «PDF N» aŭ «¶ N»; en la teksto ĝi komenciĝas per «=== page N ===» aŭ «=== ¶ N ===»).

Juĝu ĉiun paron per unu el tri respondoj:
- **unu fakto**: ambaŭ linioj diras la saman fakton (eĉ per aliaj vortoj); diru, kiun konservi: la pli plenan, kiu havas ĉion, kion la alia diras. Se ĉiu havas detalon, kiun la alia ne havas, tio ne estas «unu fakto»: respondu «du faktoj» kaj diru tion.
- **du faktoj**: la linioj diras malsamajn aferojn, kiuj nur similas (la patro kaj la patrino; du verkoj; du datoj de du agoj).
- **necerte**: vi ne povas decidi el la linioj kaj la paĝo.

**La raporto:** unu linio por ĉiu paro, en la ordo de la paroj, kaj nenio alia ol tiuj linioj kaj, fine, unu linio kun la nombroj:
- `P1 · unu fakto · konservu A · <kial, mallonge>`
- `P2 · du faktoj · <kial, mallonge>`
- `P3 · necerte · <kial, mallonge>`

**Fine, en du paŝoj:** (1) skribu la tutan raporton kiel unu mesaĝon; (2) en la sama mesaĝo, post la raporto, legu la dosieron `{fino}`, kaj respondu nur per la linio, kiun ĝi petas.

## La paroj
"""

def _dowse_rows(source):
    """A dowse file's lines as the build reads them: [(file, person, date, source, format-2 line, kind)], and the original
    lines by their format-2 form."""
    fn = f"{source}-dowse.md"
    rows, orig = [], {}
    for l in open(os.path.join(SRC, fn), encoding="utf-8").read().split("\n"):
        if not l.startswith("- $$$"): continue
        l3, k = take_kind(l)
        l2 = to2(l3)
        rec, err = parse(l2)
        if err: continue
        rows.append((fn, canon(rec[0]), rec[1], rec[3], l2.strip(), k or "")); orig[l2.strip()] = l.strip()
    return rows, orig

def dedupe_brief(source, tag):
    """--dedupe-brief SOURCE TAG (2026-10-17; the deduping proposal, (b) 3; the editor): the brief of the
    dedupe reader for one source, with every pair the build's listing finds in its dowse file, both lines in full, as
    dowse/<source>/dedupe-brief-<tag>.md (create-only)."""
    D = os.path.join(GEN, "dowse", source)
    out = os.path.join(D, f"dedupe-brief-{tag}.md")
    if os.path.exists(out): sys.exit(f"refusing: {os.path.relpath(out, REPO)} exists")
    cfg = json.load(open(os.path.join(D, "brief-config.json"), encoding="utf-8"))
    rows, orig = _dowse_rows(source)
    pairs = duplicate_pairs(rows)
    # PAIRS ALREADY RULED (2026-10-17 17:2x; the editor, to a dedupe run before the re-smelt): a pair an earlier
    # dedupe reader of this source ruled, any verdict («du faktoj», «necerte», «unu fakto» kept for the record), is not
    # asked again; matched by the two facts' first 60 characters, so a line changed since only by our notes still matches
    def fk(t): return " ".join(re.sub(r"\s*«[^«»]*»\s*$", "", t).split())[:60]
    def fact4(l):
        p = take_kind(l)[0].split(" · ")
        return " · ".join(p[1:-4]) if len(p) >= 6 else ""
    ruled = set()
    for f in sorted(os.listdir(D)):
        m = re.fullmatch(r"dedupe-brief-(.+)\.md", f)
        if not m or m.group(1) == tag or not os.path.exists(os.path.join(D, f"dedupe-return-{m.group(1)}.md")): continue
        ret = open(os.path.join(D, f"dedupe-return-{m.group(1)}.md"), encoding="utf-8").read()
        done = set(re.findall(r"^`?P(\d+) · (?:unu fakto|du faktoj|necerte)", ret, re.M))
        for mm in re.finditer(r"^### P(\d+) · .*\n\n- A: (.*)\n- B: (.*)$", open(os.path.join(D, f), encoding="utf-8").read(), re.M):
            if mm.group(1) in done: ruled.add(frozenset((fk(fact4(mm.group(2))), fk(fact4(mm.group(3))))))
    before = len(pairs)
    pairs = [p for p in pairs if frozenset((fk(p[2]), fk(p[3]))) not in ruled]
    if before != len(pairs): print(f"{source}: {before - len(pairs)} pairs ruled before, left out")
    if not pairs:
        print(f"{source}: no pair left to ask; no brief written"); return 0
    texts = ", ".join(f"`{os.path.join(GEN, x)}`" for x in cfg["texts"])
    body = DEDUPE_HEAD.format(source=source, tag=tag, n=len(pairs), texts=texts, fino=os.path.join(GEN, "dowse", "_FINO.txt"))
    for k, (fn, place, bi, bj, li, lj) in enumerate(pairs, 1):
        body += f"\n### P{k} · {place}\n\n- A: {orig.get(li, li)}\n- B: {orig.get(lj, lj)}\n"
    open(out, "x", encoding="utf-8").write(body)
    print(f"{source}: {len(pairs)} pairs → {os.path.relpath(out, REPO)}")
    return 0

def dedupe_rows(source, tag):
    """--dedupe-rows SOURCE TAG (2026-10-17; the deduping proposal, (b) 4): from the filed return
    dowse/<source>/dedupe-return-<tag>.md and its brief, the proposed DECISIONS rows of kind «duplicate», one for each
    pair ruled «unu fakto»: the dropped line's locator (as the reader of the source writes it, the file name) and the
    first six words of its own fact, the kept line's fact as the value. Written to dowse/<source>/dedupe-rows-<tag>.tsv
    (create-only) for the editor's sample; nothing is added to DECISIONS.tsv here.
    The date carry (2026-10-17; the editor, to the kept line taking the dropped line's more precise date; Jossinet
    P4/P5, Manders P21–26): where the dropped line's date is more precise than the kept line's, and the kept line is
    «[sen dato]» or dated in the same year, a DECISIONS date row for the kept line follows its duplicate row, keyed on its
    anchor where the anchor singles it out at its locator, else on six words of its fact that do; a kept «[ĝenerala]»
    line, or dates in different years, are noted on the duplicate row for the editor, not carried."""
    D = os.path.join(GEN, "dowse", source)
    bp, rp, out = (os.path.join(D, f"dedupe-{x}-{tag}.{e}") for x, e in (("brief", "md"), ("return", "md"), ("rows", "tsv")))
    # --again rewrites the tool's own rows file, untracked by git (P5 of DOWSE-THROUGHPUT-PROPOSAL-2026-10-17.md: no raw rm)
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", out], cwd=REPO, capture_output=True).returncode == 0
    if os.path.exists(out) and ("--again" not in sys.argv or tracked):
        sys.exit(f"refusing: {os.path.relpath(out, REPO)} exists" + (" and is tracked by git" if tracked else " (--again rewrites it)"))
    pairs = {m.group(1): (m.group(2), m.group(3))
             for m in re.finditer(r"^### P(\d+) · .*\n\n- A: (.*)\n- B: (.*)$", open(bp, encoding="utf-8").read(), re.M)}
    rulings = re.findall(r"^`?P(\d+) · (unu fakto|du faktoj|necerte)(?: · konservu ([AB]))?(?: · (.*?))?`?$", open(rp, encoding="utf-8").read(), re.M)
    k2n = key_names()
    def fact_of(l):
        l3, _k = take_kind(l); parts = l3.split(" · ")
        return " · ".join(parts[1:-4]) if len(parts) >= 6 else ""
    def loc_of(l):
        l3, _k = take_kind(l); src = l3.split(" · ")[-3].split(";")[0].strip()
        it = src.split(",")[0].strip()
        return (k2n.get(it, it) + src[len(src.split(",")[0]):]).strip()
    def date_of(l):
        m = re.search(r"\*\*(.+?)\*\*", take_kind(l)[0]); return m.group(1).strip() if m else ""
    def prec(d):
        m = re.search(r"\b(1[5-9]\d\d|20\d\d)(-\d\d)?(-\d\d)?", d or "")
        return 0 if not m else 1 + bool(m.group(2)) + bool(m.group(3))
    def year(d):
        m = re.search(r"\b(1[5-9]\d\d|20\d\d)", d or ""); return m.group(1) if m else None
    # every line of the dowse file at its locator, for keying a date row on a phrase that holds one line only
    at = defaultdict(list)
    for l in open(os.path.join(SRC, f"{source}-dowse.md"), encoding="utf-8").read().split("\n"):
        if l.startswith("- $$$") and len(take_kind(l)[0].split(" · ")) >= 6: at[loc_of(l)].append(l.strip())
    # a line is the kept or the dropped one by its fact and anchor, not its whole text: the facts file may already carry
    # the kept line's new date, or a label added since the brief (2026-10-17, the second run of --dedupe-rows)
    def ident(l):
        l3, _k = take_kind(l); p = l3.split(" · ")
        return (" ".join(fact_of(l).split()), " ".join(p[-4].split()) if len(p) >= 6 else "")
    def not_pair(x, kept, drop): return ident(x) not in (ident(kept), ident(drop))
    def date_key(kept, drop):
        others = [x for x in at.get(loc_of(kept), []) if not_pair(x, kept, drop)]
        anc = " ".join(take_kind(kept)[0].split(" · ")[-4].split())
        if anc and not any(anc in " ".join(x.split()) for x in others): return anc
        ws = fact_of(kept).split()
        return next((p for p in (" ".join(ws[i:i + 6]) for i in range(max(len(ws) - 5, 1)))
                     if not any(p in " ".join(x.split()) for x in others)), "")
    rows, counts, missing = [], Counter(), sorted(set(pairs) - {r[0] for r in rulings}, key=int)
    carried, uncarried = 0, 0
    for n, ruling, keep, why in rulings:
        counts[ruling] += 1
        if ruling != "unu fakto" or n not in pairs: continue
        a, b = pairs[n]
        kept, drop = (a, b) if keep != "B" else (b, a)
        # the phrase: six words of the dropped line's fact that the kept line does not have, so the row cannot drop both
        # (two facts of one pair often begin alike: Jossinet ¶ 13, «Jossinet konstatas, ke la nesubskribita artikolo»)
        # and no other line at the locator holds it, so the row drops one line only (2026-10-17: «La naskiĝakto refarita en
        # 1876 kaj» opened both Jossinet ¶ 16 lines, the father's and the mother's, and the row dropped both)
        others = [" ".join(x.split()) for x in at.get(loc_of(drop), []) if not_pair(x, kept, drop)]
        alone = lambda p: not any(p in x for x in others)
        # absent from the whole of the kept line the reader wrote (its kind, fact and anchor), not its fact only: the
        # assembler matches a phrase anywhere in the reader's line (2026-10-17: «La kafejo en Surat de Tolstoj», not in
        # the kept fact, which quotes the title, but in its anchor; the row dropped both lines)
        l3k_, kk_ = take_kind(kept)
        ws, kf = fact_of(drop).split(), " ".join(" ".join([kk_ or ""] + l3k_.split(" · ")[1:-3]).split())
        phrase = next((p for p in (" ".join(ws[i:i + 6]) for i in range(max(len(ws) - 5, 1))) if p not in kf and alone(p)), "")
        if not phrase:
            # the dropped fact lies whole inside the kept one (2026-10-17: 19 of 219 rows): a phrase of the reader's own
            # part of the dropped line, its kind, fact and anchor, that the kept line lacks; the assembler matches a phrase
            # in the reader's line, so the labels we add later are not used
            l3d, kd = take_kind(drop); l3k, kk = take_kind(kept)
            pd, pk = l3d.split(" · "), l3k.split(" · ")
            theirs = " ".join(" ".join([kk or ""] + pk[1:-3]).split())
            # each field on its own: in the reader's line the fields stand between « · », so a phrase across two never matches
            # (2026-10-17: 13 rows keyed across the kind and the fact, or the fact and the anchor, found no line)
            fields = [" ".join(f.split()) for f in [kd or ""] + pd[1:-3] if f.strip()]
            phrase = next((p for size in (6, 5, 4, 3) for f in fields for wd in [f.split()]
                           for p in (" ".join(wd[i:i + size]) for i in range(max(len(wd) - size + 1, 1)))
                           if p not in theirs and p.strip("{}·") and len(p) > 10 and alone(p)), "")
        note = "proposed; for the editor's sample (DEDUPE-PROPOSAL-2026-10-17.md, (b) 3–4)" + ("" if phrase else "; NO PHRASE: the two lines are word for word the same, a drop key in the settings is needed")
        dk, dd = date_of(kept), date_of(drop)
        carry = None
        if prec(dd) > prec(dk):
            if dk == "[ĝenerala]": note += f"; DATE NOT CARRIED: the kept line is [ĝenerala], the dropped line {dd}"; uncarried += 1
            elif prec(dk) and year(dk) != year(dd): note += f"; DATE NOT CARRIED: the kept line {dk}, the dropped line {dd}, different years"; uncarried += 1
            else:
                key = date_key(kept, drop)
                if key: carry = key
                else: note += f"; DATE NOT CARRIED: no phrase singles out the kept line at its locator (the dropped line {dd})"; uncarried += 1
        rows.append("\t".join([loc_of(drop), phrase, "duplicate", " ".join(fact_of(kept).split()[:12]),
                               f"the dedupe reader {tag}, P{n}: {why or ''}".strip(), note]))
        if carry:
            carried += 1
            rows.append("\t".join([loc_of(kept), carry, "date", dd,
                                   f"the dedupe reader {tag}, P{n}: the kept line takes the dropped line's date ({dk} → {dd}; the editor 2026-10-17: approved)",
                                   "proposed with the duplicate row above; tools/harvest-facts.py --dedupe-rows"]))
    open(out, "w" if "--again" in sys.argv else "x", encoding="utf-8").write("locator\tphrase\tkind\tvalue\truling\tnote\n" + "".join(r + "\n" for r in rows))
    print(f"{source}: {len(rulings)} rulings ({', '.join(f'{k} {v}' for k, v in counts.most_common())}); {len(rows) - carried} duplicate rows, "
          f"{carried} date rows carried, {uncarried} dates noted, not carried → {os.path.relpath(out, REPO)}"
          + (f"; NO RULING for P{', P'.join(missing)}" if missing else ""))
    return 0

def dedupe_review(tag, n):
    """--dedupe-review TAG [N] (2026-10-17; the editor): one document for the editor's sample of the
    proposed drops of every source with a dowse/<source>/dedupe-rows-<tag>.tsv: N pairs (default 30) drawn evenly
    across the sources in proportion to their drops, each with both lines in full, which is kept, the reader's reason
    and the date carried; then every pair the reader judged two facts that should be merged. Written to
    ocr/method/DEDUPE-REVIEW-<tag>.md (create-only). Nothing is applied."""
    out = os.path.join(GEN, "ocr", "method", f"DEDUPE-REVIEW-{tag}.md")
    if os.path.exists(out): sys.exit(f"refusing: {os.path.relpath(out, REPO)} exists")
    srcs = []
    for rp in sorted(glob.glob(os.path.join(GEN, "dowse", "*", f"dedupe-rows-{tag}.tsv"))):
        D = os.path.dirname(rp); s = os.path.basename(D)
        pairs = {m.group(1): (m.group(2), m.group(3), m.group(4)) for m in re.finditer(
            r"^### P(\d+) · (.*)\n\n- A: (.*)\n- B: (.*)$", open(os.path.join(D, f"dedupe-brief-{tag}.md"), encoding="utf-8").read(), re.M)}
        rulings = re.findall(r"^`?P(\d+) · (unu fakto|du faktoj|necerte)(?: · konservu ([AB]))?(?: · (.*?))?`?$",
                             open(os.path.join(D, f"dedupe-return-{tag}.md"), encoding="utf-8").read(), re.M)
        dates = {}
        for r in csv.DictReader(open(rp, encoding="utf-8"), delimiter="\t"):
            m = re.search(r", P(\d+):", r.get("ruling") or "")
            if m and r.get("kind") == "date": dates[m.group(1)] = r["value"]
        srcs.append((s, pairs, rulings, dates))
    drops = [(s, k, keep, why, pairs[k], dates.get(k)) for s, pairs, rulings, dates in srcs
             for k, v, keep, why in rulings if v == "unu fakto" and k in pairs]
    merges = [(s, k, why, pairs[k]) for s, pairs, rulings, dates in srcs
              for k, v, keep, why in rulings if v == "du faktoj" and k in pairs and "kunfand" in (why or "")]
    # an even draw: every step-th drop of the whole list, the list in source order, so each source gets its share
    step = max(1, len(drops) / max(1, n))
    sample = [drops[int(i * step)] for i in range(min(n, len(drops)))]
    by = Counter(d[0] for d in drops)
    body = [f"# The duplicate drops of {tag}: a sample for the editor", "",
            f"`[Ezri, tools/harvest-facts.py --dedupe-review {tag} {n}. The deduping proposal (geniza/ocr/method/DEDUPE-PROPOSAL-2026-10-17.md, (b) 3–4, signed): a dedupe reader judged each pair the build lists (one person, one page, one kind, 80% shared words); each pair it called «unu fakto» is a proposed drop of one line, the other kept. Nothing is applied until the editor has read this sample.]`", "",
            f"**{len(drops)} proposed drops** ({', '.join(f'{s} {c}' for s, c in by.items())}). Below: {len(sample)} of them, drawn evenly across the list, then {len(merges)} pairs the reader judged two facts to be merged into one line. Each item shows the line kept and the line dropped, in full.", "",
            "**How to answer:** «ok», or the numbers you reject (e.g. «S4, S17 wrong»). On «ok» every proposed drop goes into its source's DECISIONS.tsv, with the date rows carried, and the sources are rebuilt. The merges (M1…) are written by hand, one line each, and shown to you before they go in.", ""]
    body += ["## The sample", ""]
    for i, (s, k, keep, why, (place, a, b), dt) in enumerate(sample, 1):
        kept, drop = (a, b) if keep != "B" else (b, a)
        body += [f"### S{i} · {s} · P{k} · {place}", "", f"- **Kept:** {kept}", f"- **Dropped:** {drop}", f"- **The reader:** {why}"]
        if dt: body += [f"- **Date carried to the kept line:** {dt}"]
        body += [""]
    body += ["## Pairs to merge (the reader: two facts, each line with a detail the other lacks)", ""]
    for i, (s, k, why, (place, a, b)) in enumerate(merges, 1):
        body += [f"### M{i} · {s} · P{k} · {place}", "", f"- **A:** {a}", f"- **B:** {b}", f"- **The reader:** {why}", ""]
    open(out, "x", encoding="utf-8").write("\n".join(body) + "\n")
    print(f"{len(drops)} drops, {len(sample)} in the sample, {len(merges)} merges → {os.path.relpath(out, REPO)}")
    return 0

def dedupe_accept(tag, ruling):
    """--dedupe-accept TAG "RULING" (2026-10-17; the editor on the review: approved): every row of every
    dowse/<source>/dedupe-rows-<tag>.tsv (the drops and the dates carried with them) appended to that source's
    DECISIONS.tsv, the editor's ruling written into each row's note; a row already there (same locator, phrase and kind)
    is skipped. Then reassemble each source (dowse-facts-assemble.py --replace) and harvest. `--source S` takes that one
    source's rows only (2026-10-18: the batch's --after-dedupe of Amerika Esperantisto also rewrote Ruslanda
    Esperantisto's rows of the same tag, their ruling shortened; a tag is a date, which two sources can share)."""
    only = sys.argv[sys.argv.index("--source") + 1] if "--source" in sys.argv else "*"
    for rp in sorted(glob.glob(os.path.join(GEN, "dowse", only, f"dedupe-rows-{tag}.tsv"))):
        D = os.path.dirname(rp); dp = os.path.join(D, "DECISIONS.tsv")
        have = open(dp, encoding="utf-8").read() if os.path.exists(dp) else "locator\tphrase\tkind\tvalue\truling\tnote\n"
        # the tool's own earlier rows for this tag are replaced, not kept beside the new (a row rewritten by --dedupe-rows
        # --again would otherwise stay in its first form too)
        mark = f"\tthe dedupe reader {tag}, P"
        before = have.count("\n")
        have = "".join(l for l in have.splitlines(keepends=True) if mark not in l)
        if have.count("\n") < before: print(f"{os.path.basename(D)}: {before - have.count(chr(10))} earlier rows of {tag} replaced")
        keys = {tuple(l.split("\t")[:3]) for l in have.split("\n") if l.count("\t") >= 2}
        if "--withdraw" in sys.argv:          # take the tag's rows out only (to rebuild the facts file whole first)
            open(dp, "w", encoding="utf-8").write(have); continue
        add = []
        for r in csv.DictReader(open(rp, encoding="utf-8"), delimiter="\t"):
            if (r["locator"], r["phrase"], r["kind"]) in keys or not r["phrase"]: continue
            add.append("\t".join([r["locator"], r["phrase"], r["kind"], r["value"], r["ruling"],
                                  f"accepted by the editor {ruling}; " + (r.get("note") or "")]))
        open(dp, "w", encoding="utf-8").write(have.rstrip("\n") + "\n" + "".join(a + "\n" for a in add))
        print(f"{os.path.basename(D)}: {len(add)} rows added to DECISIONS.tsv")
    return 0

def _letters(s):
    return "".join(re.findall(r"[^\W\d_]+", s.lower()))

def _anchor_at(pages, k, anchor):
    """Whether the anchor's first twelve letters (spaces, punctuation and digits ignored: the OCR's «M r. F. A.», a word
    broken by a hyphen in mid-line where two columns run together) begin on page-file line k or beside it (k-1 … k+1),
    running on into the next line if need be; else the one line of the file where they begin, or None (none, or several).
    An anchor of under six letters is not checked."""
    seg = next((s for s in re.split(r"…|\.\.\.", anchor.strip("«» ")) if _letters(s)), "")
    want = _letters(seg)[:12]
    if len(want) < 6: return k
    L = [_letters(x) for x in pages]
    def begins(i):   # the letters begin on line i (1-based), perhaps running on into line i+1
        both = L[i - 1] + (L[i] if i < len(L) else "")
        at = both.find(want)
        return 0 <= at < max(len(L[i - 1]), 1)
    if any(begins(i) for i in (k, k - 1, k + 1) if 1 <= i <= len(L)): return k
    hits = [i for i in range(1, len(L) + 1) if begins(i)]
    return hits[0] if len(hits) == 1 else None

def expand_lean(line, pages, item=""):
    """THE LEAN LINE EXPANDED (2026-10-18; the editor, to «(prese 99) l. 62» on each line and the rest rebuilt by
    tool; the lean brief, ocr/method/DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-18-LEAN.md): a reader's line whose
    locator is «(prese M) l. K» or «l. K» gets the full one, `<item>, PDF N (prese M), l. K`, from its pages file (pages:
    that file's lines): the item from the «=== teksto: … ===» above line K (else ITEM, a source of one text), the PDF page
    from the «=== page N ===» above it («=== ¶ N ===»: `<item>, ¶ N, l. K`); «(prese ?)» where the reader gave none. The
    anchor's first words must stand on line K or beside it; where they do not, the one line of the file that holds them
    replaces K, noted ⟦l. K → l. J laŭ la ankro⟧, and where none or several do, K stays, noted ⟦la ankro ne troviĝis ĉe
    l. K⟧. Then the default voice «📣 (sen fontindiko)» where the reader wrote none, and the issue's date for «[n]»
    (⟦la dato de la numero⟧). A line in the full form, or with no pages file, comes back unchanged."""
    if not line.startswith("- $$$"): return line
    # DeepSeek's readers' form faults (2026-10-18, the lean probes g and h): markdown escapes («**\[n\]**»), an empty
    # last field («… · l. 54 ·», the voice left out with its separator kept), the printed page without its word
    # («(4) l. 222»)
    line = line.replace("\\[", "[").replace("\\]", "]")
    # a separator between the head and the date («$$$ BAKER $$$ · **[n]**», all 73 lines of V4 Pro's reader 200, k2)
    line = re.sub(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))?) · (\*\*)", r"\1 \2", line)
    line = re.sub(r"(?:\s*·\s*)+$", "", line.rstrip())
    line = re.sub(r"(?<= · )\((\d+|[ivxlc]+)\) (l\. ?\d+)(?= · |$)", r"(prese \1) \2", line)
    # La Esperantisto's form faults (2026-10-21, the five-source batch; the editor): the line
    # before the printed page («l. 220 (prese 4)», 16 lines of range 2); the line written twice, bare and with the page
    # («· l. 115 · (prese 9) l. 115», range 173)
    line = re.sub(r"(?<= · )l\. ?(\d+) (\(prese [^)]*\))(?= · |$)", r"\2 l. \1", line)
    line = re.sub(r" · l\. ?(\d+) · (\(prese [^)]*\) l\. ?\1)(?= · |$)", r" · \2", line)
    # a cover page without «prese» («(kovrilo) l. 394», «kovrilo l. 17», «(malantaŭa kovrilo) l. 238»: 2026-10-22,
    # 174 of the 193 format faults of the seven-source batch): the cover word is the printed page
    line = re.sub(r"(?<= · )\(?((?:interna )?(?:malantaŭa )?kovrilo)\)? (l\. ?\d+)(?= · |$)", r"(prese \1) \2", line)
    # the line in brackets («· (l. 19)», the same batch, La Suno Hispana part 80)
    line = re.sub(r"(?<= · )\((l\. ?\d+)\)(?= · |$)", r"\1", line)
    # a mark written after the head, before the date («$$$ GEFETI $$$ ❓ **[n]**»): moved to the voice at the end, where
    # the form has it (the default voice's «📣 ❓» if there is no voice)
    mh = re.match(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))?) ([⚠❓]+) (\*\*)", line)
    if mh:
        line = mh.group(1) + " " + line[mh.start(3):]
        if re.search(r" · [✅📣📄][^·]*$", line):
            line = re.sub(r" · ([✅📣📄])([^·]*)$", lambda m: f" · {m.group(1)} {mh.group(2)}{m.group(2)}", line)
        else:
            line = line + f" · 📣 {mh.group(2)}"
    if not pages: return line
    ps = line.split(" · ")
    li = next((i for i in range(2, len(ps)) if re.fullmatch(r"(?:\(prese ([^)]*)\) ?)?l\. ?(\d+)", ps[i].strip())), None)
    # NO LOCATOR AT ALL (2026-10-23, the seven-source batch: «… · «S-ro Friedrich Krass, Lai uul. 44, en Reve! (Estlando,»
    # · 📣 (…)», Juna Esperantisto part 55): where the anchor's first letters begin on one line of the pages file only,
    # that line is put after the anchor, noted; else the line stays as it is, and the check holds it back
    if li is None and not any(re.match(r"^[\w.-]+, (?:PDF|¶) \d+", p.strip()) for p in ps[2:]):
        ai = next((i for i in range(len(ps) - 1, 2, -1) if ps[i].strip().startswith("«")), None)
        j = _anchor_at(pages, -9, ps[ai]) if ai is not None else None
        if j is not None and j > 0:
            ps.insert(ai + 1, f"l. {j}")
            return expand_lean(" · ".join(ps) + " ⟦la lokindiko laŭ la ankro: la legilo donis neniun⟧", pages, item)
        return line
    if li is None or any(re.match(r"^[\w.-]+, (?:PDF|¶) \d+", p.strip()) for p in ps[2:]):
        # a reader of the lean brief who wrote the item and the PDF page all the same (2026-10-18t, where the source's own
        # note asked for them): the locator kept, the default voice added as below where it is the last field or a bare
        # mark follows it
        lf = next((i for i in range(2, len(ps)) if re.match(r"^[\w.-]+, (?:PDF|¶) \d+", ps[i].strip())), None)
        if lf is None or lf < len(ps) - 2: return line
        # the locator run on («…, PDF 4 (prese 4) l. 210») put in form first, so that the issue's date can be read from it
        ps[lf] = re.sub(r"(, PDF \d+)(?: (\(prese [^)]*\)))? l\. ?(\d+)$", lambda m: f"{m.group(1)} {m.group(2) or '(prese ?)'}, l. {m.group(3)}", ps[lf].strip())
        # a bare mark only: «❓ 📣 (…)», the marks before the voice, is form_repair's (found 2026-10-18 on last night's
        # return 614: «📣 ❓ 📣 (sen fontindiko)» from a voice put before it)
        _default_voice(ps, lf)
        return _issue_n(" · ".join(ps), [])
    mk = re.fullmatch(r"(?:\(prese ([^)]*)\) ?)?l\. ?(\d+)", ps[li].strip())
    prese, k = (mk.group(1) or "").strip() or "?", int(mk.group(2))
    notes = []
    if k <= len(pages):
        j = _anchor_at(pages, k, ps[li - 1]) if li >= 1 else k
        if j is None: notes.append(f"⟦la ankro ne troviĝis ĉe l. {k}⟧")
        elif j != k: notes.append(f"⟦l. {k} → l. {j} laŭ la ankro⟧"); k = j
    unit = text = None
    for i in range(min(k, len(pages)) - 1, -1, -1):
        mu = re.match(r"^=== (page|¶) (\d+) ===", pages[i])
        if unit is None and mu: unit = (mu.group(1), mu.group(2))
        mt = re.match(r"^=== teksto: (.+?) ===", pages[i])
        if mt: text = mt.group(1); break
    # THE ITEM BY ITS KEY (2026-10-21; the editor): a file
    # name may hold a comma («Zakrzewski - Historio de Esperanto, 1913»: all 1,287 lines of its batch refused, the comma
    # read as the end of the item) or a space («Esperanto 1894.4», which issue_date's locator search does not take); the
    # key is always ASCII letters, digits and «-» (ocr-item-table.py's slug), so the expanded locator carries the key
    it = text or item
    if not unit or not it: return line
    ruled = INDEP_RULED.get(it)
    it = item_key(it)
    ps[li] = f"{it}, PDF {unit[1]} (prese {prese}), l. {k}" if unit[0] == "page" else f"{it}, ¶ {unit[1]}, l. {k}"
    # the default voice: where none follows the locator; before a mark alone («· ❓», «· ❓ (…)»: the voice left out, its
    # mark kept, as the lean brief has it)
    _default_voice(ps, li)
    if ruled: ps[-1] = _ruled_voice(ps[-1], ruled)
    return _issue_n(" · ".join(ps), notes)

# AN ITEM'S INDEPENDENCE BY RULING (2026-10-21; the editor, on Zakrzewski's Historio
# to
#). The item stays SECONDARY (the 2026-10-09 exception, by genre); its lines
# take the ruled label in place of the default «sen fontindiko», and a «» line without one gets it. A line where the
# reader found him naming his source («derivita ↤ …», «refutas: …») keeps the reader's label.
INDEP_RULED = {
    "Zakrzewski - Historio de Esperanto, 1913": "sendependa",
}

def _ruled_voice(v, label):
    """The voice field V with LABEL for its independence, as above."""
    if re.search(r"\bderivita\b|refutas:|\bsendependa\b", v): return v
    if re.search(r"\bsen fontindiko\b", v): return re.sub(r"\bsen fontindiko\b", label, v, count=1)
    m = re.match(r"^([✅📣📄](?: ?[⚠❓])*)\s*(?:\(((?:[^()]|\([^()]*\))*)\))?\s*$", v.strip())
    if m: return f"{m.group(1)} ({label}" + (f"; {m.group(2)})" if m.group(2) else ")")
    # the reader's note with its brackets unbalanced («📣 (noto 7) de p. 54, … ĝis l. 340)»): the label before it, the
    # note as written
    m = re.match(r"^([✅📣📄](?: ?[⚠❓])*)\s*\((.*)\)\s*$", v.strip())
    return f"{m.group(1)} ({label}; {m.group(2)})" if m else v

def _default_voice(ps, li):
    """The voice after the locator ps[li], in place: the default «📣 (sen fontindiko)» where none follows; «📣» before a
    mark alone; a label alone, as the lean brief lets a reader write it («derivita ↤ …», «refutas: …», «sendependa»), into
    the voice's bracket (2026-10-21, La Esperantisto ranges 149, 164, 179: the default put after the label made it a
    field of the source, and the anchor was read from the label's quoted title)."""
    last = ps[-1].strip()
    if li < len(ps) - 1 and re.match(r"^(?:derivita\b|refutas:|sendependa\b|sen fontindiko\b)", last): ps[-1] = f"📣 ({last})"
    elif li == len(ps) - 1 or not re.match(r"^[✅📣📄⚠❓]", last): ps.append("📣 (sen fontindiko)")
    elif re.match(r"^[⚠❓]", last) and not re.search(r"[✅📣📄]", ps[-1]): ps[-1] = "📣 " + last
    # «📣» written only to carry a note («📣 (OCR «Biatystok»)»), as the lean brief has the reader's own additions: the
    # brief's 📣 is «sen fontindiko» unless a label says otherwise, so the label goes in (2026-10-21, Zakrzewski 1913, a
    # SECONDARY source, about 268 lines refused for the label)
    mv = re.fullmatch(r"📣((?: ?[⚠❓])*)\s*(?:\(((?:[^()]|\([^()]*\))*)\))?\s*", ps[-1].strip())
    if mv and not INDEP.search(ps[-1]):
        ps[-1] = f"📣{mv.group(1)} (sen fontindiko" + (f"; {mv.group(2)})" if mv.group(2) else ")")

def _issue_n(line, notes):
    """«[n]» dated by the line's issue (⟦la dato de la numero⟧), and the expansion's notes put into the voice's bracket."""
    mn = re.match(r"^(- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))? )\*\*\[n\]\*\*", line)
    if mn:
        iss = issue_date(line, day=True)
        if iss:   # an issue the register dates by its contents says so (ISSUE-DATES.tsv, 2026-10-22)
            line = mn.group(1) + f"**{issue_field(iss)}**" + line[mn.end():]
            notes.append("⟦la dato de la numero, laŭ la enhavo⟧" if len(iss) > 4 and iss[4] == "enhavo" else "⟦la dato de la numero⟧")
        else: line = mn.group(1) + "**[sen dato]**" + line[mn.end():]; notes.append("⟦«[n]», sed la ero ne estas numero⟧")
    for note in notes:
        line = line[:-1] + f"; {note})" if line.rstrip().endswith(")") else line.rstrip() + f" ({note})"
    return line

def test_copies():
    """--test-copies: merge_copies on made-up rows under the two copies of Privat's vol. 2 (COPIES, one same_text group)
    and the two texts of Zamenhof's Aldono al la Dua Libro (kind 0): the pairs that must merge, and those that must not
    (another person, a number other than a year, a page outside the scan's stretch). Prints each case; writes nothing."""
    A, B = "privat-historio-1927-vol2", "338579940-Historio-de-La-Lingvo-Esperanto-Edmond-Privat"
    f = "La komitato elektis Boirac prezidanto de la Lingva Komitato post la kongreso de Boulogne «elektis»"
    people = {
        "BOIRAC": [("1905", f, f"{A}, PDF 20", "[ORG]", "📣", "t1.md"), ("1905", f, f"{B}, PDF 60", "[ORG]", "📣", "t2.md")],
        "ZAMENHOF": [("1888", "Zamenhof eldonis la Aldonon al la Dua Libro en Varsovio kun respondoj al leteroj «eldonis»",
                      "tekstaro-aldono-dua-libro, ¶ 3", "[ZAM]", "📣", "t3.md"),
                     ("1888", "Zamenhof eldonis la Aldonon al la Dua Libro en Varsovio kun respondoj al leteroj «eldonis»",
                      "OV pli eta 2, PDF 33", "[ZAM]", "📣", "t4.md")],
        "BEAUFRONT": [("1905", "Beaufront ricevis 12 voĉojn en la komitato de Boulogne «voĉojn»", f"{A}, PDF 21", "[ORG]", "📣", "t1.md"),
                      ("1905", "Beaufront ricevis 14 voĉojn en la komitato de Boulogne «voĉojn»", f"{B}, PDF 61", "[ORG]", "📣", "t2.md")],
        "MOCH": [("1905", "Moch skribis artikolon pri la Lingva Komitato post Boulogne «skribis»", f"{A}, PDF 22", "[ORG]", "📣", "t1.md"),
                 ("1905", "Moch skribis artikolon pri la Lingva Komitato post Boulogne «skribis»", f"{B}, PDF 20", "[ORG]", "📣", "t2.md")],
    }
    COPY_MERGED.clear()
    n = merge_copies(people)
    want = {"BOIRAC": 1, "ZAMENHOF": 1, "BEAUFRONT": 2, "MOCH": 2}
    bad = 0
    for who, rows in people.items():
        ok = len(rows) == want[who]; bad += not ok
        print(f"  {'ok ' if ok else 'FAIL'} {who}: {len(rows)} line(s), want {want[who]}" + (f" · {rows[0][2]} · {rows[0][4]}" if len(rows) == 1 else ""))
    print(f"{n} merged; {bad} failure(s)")
    return 1 if bad else 0

def test_relative():
    """--test-relative: relative_date on the lean brief's probe phrases (dowse/amerika-esperantisto/facts-return-
    2026-10-18s-*.md), each under its own issue's locator; prints each case and its result, and the count of failures."""
    L = lambda it, d: f"- $$$ X $$$ **{d}** · {{aperoj: y}} · fakto · ankro · {it}, PDF 3 (prese 3), l. 1 · [?] · 📣 (sen fontindiko)"
    cases = [   # (issue, the reader's words, the form wanted or None for the reader)
        ("AmerikaEsperantisto_1907_v01_n06_jul", "dum la pasinta jaro", "1906"),
        ("AmerikaEsperantisto_1907_v01_n06_jul", "en la nuna jaro", "1907"),
        ("AmerikaEsperantisto_1907_v01_n06_jul", "dum la Kongreso en Cambridge", None),   # an event the calendar resolves: left
        ("AmerikaEsperantisto_1907_v01_n06_jul", "dum la Tria Kongreso", None),
        ("AmerikaEsperantisto_1908_v03_n02_mar", "antaŭ la 10a de februaro (1908)", "antaŭ 1908-02-10"),
        ("AmerikaEsperantisto_1908_v03_n02_mar", "antaŭ la 10a de februaro", "antaŭ 1908-02-10"),
        ("AmerikaEsperantisto_1907_v02_n03_okt", "la lastan someron (1907)", "inter 1907-06 kaj 1907-08"),
        ("AmerikaEsperantisto_1907_v02_n03_okt", "la lastan someron", "inter 1907-06 kaj 1907-08"),
        ("AmerikaEsperantisto_1908_v03_n06_jul", "la lastan someron", "inter 1907-06 kaj 1907-08"),
        ("AmerikaEsperantisto_1908_v03_n03_apr", "post Oktobro 1907", "post 1907-10"),
        ("AmerikaEsperantisto_1912_v11_n02_mar", "julio 1911 (of last July)", "1911-07"),
        ("AmerikaEsperantisto_1912_v11_n02_mar", "la pasintan someron (1911)", "inter 1911-06 kaj 1911-08"),
        ("AmerikaEsperantisto_1909_v06_n04_nov", "lastatempe", None),        # «lately»: to the reader (the editor)
        ("AmerikaEsperantisto_1909_v06_n04_nov", "antaŭhieraŭ nokte", None),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "en la lastaj ses semajnoj", None),
        ("AmerikaEsperantisto_1916_v18_n04_feb-mar", "lastatempe", None),
        ("AmerikaEsperantisto_1914_v16_n04_dec-jan", "antaŭ nelonge (recently)", None),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "sep tagojn post 27 aprilo", "1911-05-04"),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "ĉ. ses semajnojn post 27 aprilo", "ĉirkaŭ 1911-06-08"),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "27 aprilo", "1911-04-27"),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "la tagon post la skribo de «A Letter from Sicily»", None),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "ekde lia alveno en Eŭropo", None),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "dum tri monatoj", None),
        ("AmerikaEsperantisto_1911_v10_n01_aug", "post unu jaro", None),
        ("AmerikaEsperantisto_1908_v04_n01_aug", "en Dresdeno", None),
        # the second lean probe's (2026-10-18t, reader 400)
        ("AmerikaEsperantisto_1912_v11_n02_mar", "la pasintan julion", "1911-07"),
        ("AmerikaEsperantisto_1912_v11_n02_mar", "februaro", "1912-02"),
        ("AmerikaEsperantisto_1912_v11_n02_mar", "la pasintan someron", "inter 1911-06 kaj 1911-08"),
        ("AmerikaEsperantisto_1912_v11_n02_mar", "oktobro", None),    # after the issue's month: which year, the reader's
    ]
    bad = 0
    for it, d, want in cases:
        got = relative_date(d, L(it, d))[0] if needs_reading(d) else None
        ok = got == want; bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {it[-14:]:>14}  «{d}» → {got}" + ("" if ok else f"   (wanted {want})"))
    print(f"{len(cases) - bad} of {len(cases)} as wanted")
    return 1 if bad else 0

def main():
    if "--test-relative" in sys.argv: return test_relative()
    if "--test-copies" in sys.argv: return test_copies()
    if "--mastheads" in sys.argv: return masthead_report(sys.argv[sys.argv.index("--mastheads") + 1])
    if "--issue-contents" in sys.argv:
        return issue_contents(sys.argv[sys.argv.index("--issue-contents") + 1], "--validate" in sys.argv)
    if "--dedupe-accept" in sys.argv:
        i = sys.argv.index("--dedupe-accept"); return dedupe_accept(sys.argv[i + 1], sys.argv[i + 2])
    if "--dedupe-review" in sys.argv:
        i = sys.argv.index("--dedupe-review")
        return dedupe_review(sys.argv[i + 1], int(sys.argv[i + 2]) if len(sys.argv) > i + 2 and sys.argv[i + 2].isdigit() else 30)
    if "--propose-bearers" in sys.argv:
        return propose_bearers(sys.argv[sys.argv.index("--propose-bearers") + 1])
    if "--dedupe-brief" in sys.argv:
        i = sys.argv.index("--dedupe-brief"); return dedupe_brief(sys.argv[i + 1], sys.argv[i + 2])
    if "--dedupe-rows" in sys.argv:
        i = sys.argv.index("--dedupe-rows"); return dedupe_rows(sys.argv[i + 1], sys.argv[i + 2])
    check = "--check" in sys.argv
    if "--quiet" in sys.argv: sys.stdout = _Quiet(sys.stdout)
    files = sorted(glob.glob(os.path.join(SRC, "*.md")))
    if not files:
        print(f"no per-source files yet under {SRC}\n(that is expected before the scouts run)")
        return 0
    people, errors, nofacts, now, fmt2, toverify = defaultdict(list), [], [], [], [], []
    kinded = []      # (file, line, kind or None) for every line of a format-4 file
    every = []       # (file, line, person, the line) for every valid line of every file (the scope warning)
    refs = []        # (person, index in people[person], index in now) for every valid line (the hostile-witness label)
    tocopy = []      # (file, person, row index, kind, line): format-4 lines whose object may name other persons
    for f in files:
        saw = 0
        raw = open(f, "rb").read()
        try:
            content = raw.decode("utf-8").split("\n")
        except UnicodeDecodeError as e:        # the Fable review's S10: was errors="ignore", which dropped bytes silently
            print(f"  ⚠ not valid UTF-8, read with replacement characters: {os.path.basename(f)} ({e})")
            content = raw.decode("utf-8", errors="replace").split("\n")
        strict_file = any(FORMAT2.match(l) for l in content[:15])
        kinds4 = any(KINDS4.match(l) for l in content[:15])
        fmt3 = kinds4 or any(FORMAT3.match(l) for l in content[:15])
        if strict_file: fmt2.append(os.path.basename(f))
        if fmt3: FMT3.add(os.path.basename(f))
        fmt4 = kinds4 or any(FORMAT4.match(l) for l in content[:15])
        pend = []    # format-2 lines in file order, for the context dates below
        for n, line in enumerate(content, 1):
            if not line.startswith("- $$$"): continue
            saw += 1
            kind = None
            if fmt4: line, kind = take_kind(line)
            if fmt3: line = to2(line)
            rec, err = parse(line)
            if not err and strict_file:
                err = strict(rec, fmt3)
            if err:
                errors.append((os.path.basename(f), n, err, line.strip()[:90])); continue
            who, rest = canon(rec[0]), rec[1:]
            # BY THE GIVEN NAME THE LINE PRINTS (REASSIGN): a line filed under one man's surname that names the other man
            # of the same surname by his given name goes to him
            for target, rx in REASSIGN.get(who, ()):
                if re.search(rx, rec[2]): who = target; REASSIGNED.append((os.path.basename(f), rec[0], target)); break
            if strict_file: toverify.append((os.path.basename(f), n, rec))
            people[who].append(rest + (os.path.basename(f),))
            if strict_file:
                ms = locators(rec[3])
                pend.append((who, len(people[who]) - 1, int(ms[0].group("pdf") or ms[0].group("para")), rec[1], rec[4], rec[5], rec[3]))
            if kind:
                KINDS[(os.path.basename(f), rec[3], rec[2], slug(who))] = kind; kinded.append((os.path.basename(f), n, kind))
                tocopy.append((os.path.basename(f), who, len(people[who]) - 1, kind, line))
            elif fmt4: kinded.append((os.path.basename(f), n, None))
            now.append([os.path.basename(f), who, rec[1], rec[3], line.strip(), kind or ""])
            every.append((os.path.basename(f), n, who, line))
            refs.append((who, len(people[who]) - 1, len(now) - 1))
        if not saw: nofacts.append(os.path.basename(f))
        # CONTEXT DATES (the editor 2026-10-11;
        # «diveno > divene»; «ĉ. : add ≤, ≥»): in the profile only (the facts file and FACTS-LIST keep «[sen dato]»), an
        # undated line of a format-2 file takes its date from the nearest dated lines of the same file on the same or a
        # neighbouring page, the file being in the source's page order: a dated line before gives «≥», one after gives
        # «≤», both of one year give «ĉ.»; it is shown, and sorted, as «[sen dato; divene ≥ 1890 laŭ la paĝo]».
        def yr(d): m = re.search(r"(1[6-9]\d\d|20\d\d)", d); return int(m.group(1)) if m and "sen dato" not in d else None
        # THE DATE OF THE SAYING (the editor 2026-10-12 00:5x
        # the rule approved): an undated [AS] or [KAR] line is dated by the act of saying, not by the events on
        # its page: the derived source's year when its label gives one, else the source's own year as an upper bound
        for i, (who, idx, pg, d, th, conf, src) in enumerate(pend):
            kd = KINDS.get((os.path.basename(f), src, people[who][idx][1], slug(who)))
            # a judgement or declaration the reader marked [ĝenerala] is an act all the same, dated by its saying
            # (2026-10-16 22:2x, the editor to the kind deciding [ĝenerala]; listed in KIND-FAULTS-LATEST.md)
            act_gen = bool(kd) and kd.split(":")[0].strip() in ("juĝo", "aserto") and "ĝenerala" in d
            if yr(d) is not None: continue
            # a line kinded as a saying is one, whatever its themes (2026-10-17u, smelt S5: Devjatnin's nineteen «juĝo»
            # lines of Ruslanda Esperantisto, without [AS] or [KAR], took page guesses instead of the date of the saying)
            said = bool(kd) and kd.split(":")[0].strip() in SAYING_KINDS
            if not act_gen and ("sen dato" not in d or not ({"AS", "KAR"} & set(th) or said)): continue
            # only a kind of saying is dated by its saying (2026-10-16; the editor, on Waringhien's «Beaufront multon
            # profitis el la reformprojekto de 1894», kinded «influo» and dated 1948 by this rule
            # approved): a line whose kind is an event keeps
            # «[sen dato]», and is listed as a probable kind fault
            if kd and kd.split(":")[0].strip() not in SAYING_KINDS:
                SAYING_SKIPPED.append(f"{os.path.basename(f)}: {who} · {{{kd[:70]}}} · {people[who][idx][1][:90]} · {src}")
                continue
            m = re.search(r"derivita ↤ ([^;)]*)", conf)
            y = None if not m or "sen dato" in m.group(1) or "s.d." in m.group(1) else re.search(r"(1[6-9]\d\d|20\d\d)", m.group(1))
            ms = locators(src)
            item, n = (ms[0].group("item").strip(), ms[0].group("pdf") or ms[0].group("para")) if ms else (None, None)
            cd = next((d for lo, hi, d in CONTRIB_DATES.get(item, []) if n and lo <= int(n) <= hi), None)
            if y: est = f"[sen dato; divene {y.group(1)} laŭ la dato de la diro]"
            elif cd: est = f"[sen dato; divene {cd} laŭ la dato de la kontribuo]"   # before the volume's year (finding 5)
            elif issue_year(src): est = f"[sen dato; divene {issue_year(src)} laŭ la numero]"   # said in the issue
            else:
                w = source_info(src)[1]
                if w is None: continue
                est = f"[sen dato; divene ≤ {w} laŭ la dato de la fonto]"
            row = people[who][idx]
            people[who][idx] = (est,) + row[1:]
            pend[i] = (who, idx, pg, "dated-by-saying", th, conf, src)   # not used as a neighbour for the page guess below
        for i, (who, idx, pg, d, th, conf, src) in enumerate(pend):
            if yr(d) is not None or "sen dato" not in d: continue
            # THE KIND DECIDES [ĝenerala] (2026-10-16 22:2x, the editor; the redowse checklist, the date
            # guess): origin and character are whole-life by their kind, and an undated line of either is «[ĝenerala;
            # laŭ la speco]», never guessed from its page; a profession, study, residence, family, health or name may be
            # either, so the reader's [ĝenerala] stands and an undated one is guessed as an instant within its span, as
            # an office is (rule (iv) below then does not apply to it). A character line the date of saying has dated
            # above keeps that date: the saying rule (2026-10-12) comes first
            kd = KINDS.get((os.path.basename(f), src, people[who][idx][1], slug(who)))
            kk = kd.split(":")[0].strip() if kd else ""
            # … not when a second kind is an act («deveno: juda; +aliĝo: Esperanto»: the joining has a date)
            acts2 = [x.strip()[1:].split(":")[0].strip() for x in (kd or "").split(";")[1:] if x.strip().startswith("+")]
            if kk in WHOLE_LIFE_KINDS and all(a in NEVER_GENERAL_EXEMPT for a in acts2):
                people[who][idx] = ("[ĝenerala; laŭ la speco]",) + people[who][idx][1:]; GENERAL_BY_KIND.append(os.path.basename(f)); continue
            # A WRONG DATE IS WORSE THAN A MISSING ONE (the Fable review's finding 4, the editor 2026-10-12
            #): no page guess (i) on a bibliography line, which is dated by the
            # year its own entry gives; (ii) when the fact names a year or a month (the check warns: write the date);
            # (iii) in an item not told in its page order (profiles/CHRONOLOGY.tsv); (iv) on a state («li estis …»),
            # which wants «[ĝenerala]» (the check warns)
            fact = people[who][idx][1].split("«")[0]
            if fact.lstrip().startswith("(bibliografio)"):
                y = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", people[who][idx][1]) or re.search(r"\b(1[6-9]\d\d|20\d\d)\b", conf)
                if y: people[who][idx] = (f"[sen dato; divene {y.group(1)} laŭ la bibliografia indiko]",) + people[who][idx][1:]
                continue
            if re.search(rf"\b1[6-9]\d\d\b|\b20\d\d\b|\b{MONTHS}\b", fact, re.I): continue
            # … or dates itself by the life («ĝis sia morto», «dum sia tuta vivo»): neighbouring pages say nothing of it
            if re.search(r"\b(?:ĝis|post|antaŭ|dum|de) (?:sia|lia|ŝia|ilia) (?:tuta )?(?:morto|vivo|junaĝo|infanaĝo|maljunaĝo)\b", fact, re.I): continue
            # a line of a periodical issue is dated by its issue, a state as well as an event: a guess, marked as one
            # (the editor, 2026-10-17
            # built 2026-10-17u, smelt S5: Ruslanda Esperantisto's lines left «[sen dato]» or guessed
            # from the pages of other issues, De Beaufront L140–L144, L216, L497, Devjatnin L92 «≥ 1906» in 1905's n-ro 6)
            if (iy := issue_year(src)):
                people[who][idx] = (f"[sen dato; divene ĉ. {iy} laŭ la numero]",) + people[who][idx][1:]; ISSUE_DATED.append(os.path.basename(f)); continue
            if key_names().get(src.split(",")[0].strip(), src.split(",")[0].strip()) in NOT_CHRONOLOGICAL: continue
            # … but an office is a duration, and a date on it is an instant within it, not its bounds (the editor,
            # 2026-10-13): offices are guessed
            # (an office by its kind too, where OFFICE's words miss it: Couturat «la gvidanto de la Delegacio»)
            if kk not in EITHER_KINDS | {"ofico"} and (sm := STATE.match(fact)) and not OFFICE.match(fact[sm.end():]): continue
            # (vi) a neighbour dated by its source's own year («⟦pruvo: la jaro de la fonto …⟧», a judgement the assembler
            # dated by the saying) says when the book was written, not when anything on its page happened: it is never a
            # neighbour (2026-10-16 23:0x, found in the build of the kind rule: Zamenhof's «kompromisemo» in a letter to
            # Cart, Korĵenkov PDF 53, guessed «ĉ. 2005» from two judgements of Cart dated 2005)
            # (vii) nor is a judgement, claim, interpretation or historiography line: its date is when it was said, not
            # when anything on its page happened (2026-10-17, De Beaufront's periods: Jossinet's lines on acts of the
            # 1890s guessed «ĉ. 1998», «≥ 1998 laŭ la paĝo 38» from his own judgements dated 1998-06 beside them)
            def saying(j):
                wj, ij = pend[j][0], pend[j][1]
                kj = KINDS.get((os.path.basename(f), pend[j][6], people[wj][ij][1], slug(wj)), "")
                return kj.split(":")[0].strip() in SAYING_KINDS | {"interpreto", "historiografio"}
            # (viii) a neighbour is a line of the same item: a file of several items (a run of issues) repeats its PDF
            # numbers in each (2026-10-17u, smelt S5)
            same = lambda j: (locators(pend[j][6]) or [None])[0] is not None and locators(pend[j][6])[0].group("item").strip() == item_i
            item_i = (locators(src) or [None])[0].group("item").strip() if locators(src) else None
            near = lambda rng, skip=True: next(((pend[j][2], yr(pend[j][3])) for j in rng
                                     if abs(pend[j][2] - pg) <= 1 and yr(pend[j][3]) is not None and same(j)
                                     and not (skip and ("la jaro de la fonto" in (pend[j][5] or "") or saying(j)))), None)
            before, after = near(range(i - 1, -1, -1)), near(range(i + 1, len(pend)))
            if (before, after) != (near(range(i - 1, -1, -1), False), near(range(i + 1, len(pend)), False)): SOURCE_YEAR_SKIPS.append(os.path.basename(f))
            if not before and not after: continue
            # the source not told in order here (before later than after, e.g. Jossinet ¶ 45 between 1935 and 1904): no
            # range, the line stays «[sen dato]» (the editor's review 2026-10-11: «≥ 1935, ≤ 1904» is impossible)
            if before and after and before[1] > after[1]: continue
            if before and after and before[1] == after[1]: est = f"ĉ. {before[1]}"
            elif before and after: est = f"≥ {before[1]}, ≤ {after[1]}"
            elif before: est = f"≥ {before[1]}"
            else: est = f"≤ {after[1]}"
            # (v) the guess names the page(s) of the lines it rests on, so it can be checked
            basis = sorted({x[0] for x in (before, after) if x})
            where = ("la paĝo " if len(basis) == 1 else "la paĝoj ") + ", ".join(map(str, basis))
            row = people[who][idx]
            people[who][idx] = (f"[sen dato; divene {est} laŭ {where}]",) + row[1:]

    # THE HOSTILE-WITNESS LABEL (ocr/method/HOSTILE-WITNESS-LABEL-PROPOSAL-2026-10-13.md; its questions settled with the
    # editor 2026-10-15, built 2026-10-16): computed here, never written in a facts file; in the profile line's labels
    # and FACTS-LIST's last column. Before the copies and the merge of spellings, while each line's place is known.
    labs, hstat = hostile_labels(now, refs, every)
    for k, (who, i, j) in enumerate(refs):
        lab = labs.get(k, "")
        if lab:
            r = people[who][i]
            people[who][i] = r[:4] + (f"{r[4]} ⟦malamika atestanto, komputita: {lab}⟧",) + r[5:]
        now[j].append(lab)
    copied, copy_skips = copies(people, tocopy, now)
    life_guess_drops(people)

    # Merge spellings that slug to the same file (NYLÉN/NYLEN, DE SAUSSURE/DE-SAUSSURE, the hyphen
    # forms of BAUDOUIN DE COURTENAY …). The dict was keyed by display name and the files by slug, so
    # the second spelling silently overwrote the first — twelve pairs found by the Brief-5 scout,
    # 2026-09-12. The display name kept is the most frequent spelling; ALIASES still applies first.
    merged, names = defaultdict(list), defaultdict(Counter)
    for who, rows in people.items():
        merged[slug(who)].extend(rows); names[slug(who)][who] += len(rows)
    people = {names[s].most_common(1)[0][0]: rows for s, rows in merged.items()}
    n_copy = merge_copies(people)
    if True:
        with open(os.path.join(BUILD, "COPIES-MERGED-LATEST.md"), "w", encoding="utf-8") as fh:
            fh.write("# One fact in two copies, or in two texts of one work: the lines merged in the profiles\n\n"
                     "`[GENERATED by tools/harvest-facts.py (merge_copies); the doubles method, ocr/method/DOWSE-DOUBLES-METHOD-PROPOSAL-2026-10-20.md. "
                     "The fact files keep both lines; each pair below is one line in the profile, the first line's text with both locators.]`\n\n"
                     f"{n_copy} merged. Lines placed under a COPIES work, by copy (a work with lines under one copy only has nothing to merge):\n\n"
                     + "".join(f"- {w_} · `{it_}`: {c_}\n" for (w_, it_), c_ in sorted(COPY_SEEN.items())) + "\n")
            for k, (who, ri, rj, lab) in enumerate(COPY_MERGED, 1):
                fh.write(f"{k}. **{who}**, {lab}\n   - kept: **{ri[0]}** · {ri[1]} · {ri[2]} · ({ri[5]})\n   - merged: **{rj[0]}** · {rj[1]} · {rj[2]} · ({rj[5]})\n")
        print(f"  one fact in two copies or two texts of one work (COPIES): {n_copy} pairs merged in the profiles (profiles/build/COPIES-MERGED-LATEST.md)")

    total = sum(len(v) for v in people.values())
    print(f"scanned {len(files)} per-source files ({len(fmt2)} in facts format 2) · {total} valid fact lines · {len(people)} people · {len(errors)} errors")
    for fn in nofacts: print(f"  ⚠ no fact lines at all: {fn}")
    print(f"  hostile-witness labels (computed, in the profiles and FACTS-LIST only): {sum(v for k, v in hstat.items() if k in ('Esperanto', 'Ido', 'hostile'))} "
          f"(by the venue's side: {', '.join(f'{k} {v}' for k, v in hstat.items() if k in ('Esperanto', 'Ido', 'hostile')) or 'none'}); "
          f"dated lines whose locator names no item: {hstat.get('no item', 0)}")
    for s in HOSTILE_SHOWN[:100]: print(f"    · {s}")
    if tocopy:
        print(f"  copies for the other persons (renkonto, konflikto, interkonsento; and «kun:», {copy_skips['kun']} of them): {copied - copy_skips['named'] - copy_skips['family']} written; {copy_skips['out']} not copied, out by the scope register; "
              f"{copy_skips['there']} already written by the reader; {copy_skips['nolines']} to persons with no lines of their own")
        for w, c in copy_skips["names"].most_common(20): print(f"    · not copied, no lines of their own: {w} ({c})")
        print(f"  copies for every person a kind names (any kind, 2026-10-16): {copy_skips['named']} written; "
              f"{copy_skips['named_nolines']} to names with no lines of their own; {copy_skips['named_out']} out by the scope register")
        print(f"  copies of a family's lines to its members (FAMILIES): {copy_skips['family']} written")
        if copy_skips["named_to"]:   # one line, so --quiet keeps it
            print("    the most: " + "; ".join(f"{w} {c}" for w, c in copy_skips["named_to"].most_common(40)))
    # The Fable review's S7 (2026-10-10): in format-2 files, every quotation is looked for on the page (or ¶) its locator
    # names. A miss is reported as a warning, not an error: the LOCATOR AND QUOTATION RULING allows an obvious OCR error
    # to be corrected in a quotation, and the search already tries later words and shorter runs.
    if toverify:
        fid, cache, unfound = _fid(), {}, []
        for fn, n, rec in toverify:
            ok = False
            for m in (locators(rec[3]) or []):
                it, pg = m.group("item").strip(), int(m.group("pdf") or m.group("para"))
                if it not in cache: cache[it] = item_pages(it, fid)
                if not cache[it]: continue
                for seg in segments(rec[2], last=fn in FMT3):
                    w = fid.norm(" ".join(seg)).split()
                    if len(w) >= 3 and fid.find(cache[it], pg, w): ok = True; break
                # a record's short entry («sans profession»): under three words, found if it stands once in a short text,
                # as the format check already accepts it (short_record_anchor; the editor 2026-10-13)
                if not ok and short_record_anchor(it, rec[2]): ok = True
                if ok: break
            if not ok: unfound.append((fn, n, rec[3]))
        print(f"  quotations checked against their pages: {len(toverify)}; not found: {len(unfound)}")
        for fn, n, src in unfound[:40]: print(f"    ⚠ quotation not found on its page: {fn}:{n} ({src})")
        # A DERIVED SOURCE IS NAMED WITH AUTHOR AND DATE (the editor 2026-10-11)
        undated = [(fn, n, m) for fn, n, rec in toverify for m in re.findall(r"derivita ↤ ([^;)]*)", rec[5])
                   if not re.search(r"1[5-9]\d\d|20[0-3]\d|sen dato|s\.d\.", m)]   # «s.d.» in references (the editor 2026-10-11)
        print(f"  derived sources named without a year (A DERIVED SOURCE IS NAMED WITH AUTHOR AND DATE): {len(undated)}")
        for fn, n, m in undated[:600]: print(f"    ⚠ {fn}:{n}: derivita ↤ {m[:80]}")
        # THE WORKS REGISTER (the Fable review's finding 6; the editor 2026-10-12): a label
        # «derivita ↤ … s.d.» naming a work the register dates (titles of 12+ characters, not generic headings)
        wr = os.path.join(GEN, "profiles", "WORKS-REGISTER.tsv")
        works = []
        if os.path.exists(wr):
            works = [(r["title"].lower(), r["year"], r["key"]) for r in csv.DictReader(
                (l for l in open(wr, encoding="utf-8") if not l.startswith("#")), delimiter="\t")
                if len(r["title"]) >= 12 and r["title"].lower() not in ("bibliografio", "kroniko")
                and not (r.get("status") or "").startswith("merged")]
        sd = [(fn, n, k, y) for fn, n, rec in toverify for m in re.findall(r"derivita ↤ ([^;)]*)", rec[5])
              if re.search(r"s\.d\.|sen dato", m) for t, y, k in works if t in m.lower()]
        print(f"  derived sources «s.d.» that the works register dates: {len(sd)}")
        for fn, n, k, y in sd[:200]: print(f"    ⚠ {fn}:{n}: {k} ({y})")
        # A CLAIM'S EVENT UNDER ITS SUBJECT (the editor 2026-10-11
        #): an «(aserto pri X)» line needs a line under X in the same file, same page
        def pg_of(rec):
            ms = locators(rec[3]); return int(ms[0].group("pdf") or ms[0].group("para")) if ms else None
        held = {(fn, slug(canon(rec[0])), pg_of(rec)) for fn, n, rec in toverify}
        orphan = []
        for fn, n, rec in toverify:
            m = re.search(r"\((?:aproba |malaproba )?aserto pri ([^)]+)\)", rec[2])
            if m and (fn, slug(canon(m.group(1).strip())), pg_of(rec)) not in held: orphan.append((fn, n, m.group(1).strip()))
        print(f"  claims whose event is not under their subject on the same page: {len(orphan)}")
        for fn, n, x in orphan[:100]: print(f"    ⚠ {fn}:{n}: aserto pri {x}")
        # «[sen dato]» naming a year in its fact (2026-10-11, the Frankfurt 1906 photo line); and described dates
        # («in his twelfth year», the editor)
        yr_named = [(fn, n) for fn, n, rec in toverify if "sen dato" in rec[1] and re.search(r"\b1[89]\d\d\b", rec[2].split("«")[0])]
        # a line dated by its issue (the lean brief's «[n]», ⟦la dato de la numero⟧) whose fact names another year: the
        # text may date the act itself (2026-10-18; the editor)
        yr_named += [(fn, n) for fn, n, rec in toverify if "la dato de la numero⟧" in rec[5] and any(
            y not in rec[1] for y in re.findall(r"\b1[89]\d\d\b", rec[2].split("«")[0]))]
        described = [(fn, n) for fn, n, rec in toverify if "sen dato" in rec[1] and re.search(
            r"jaraĝ|-jara\b|jaro de (?:sia|lia|ŝia) vivo|en (?:sia|lia|ŝia) \w+a jaro|post \w+ jaroj", rec[2].split("«")[0])]
        print(f"  undated lines that name a year: {len(yr_named)}; undated lines with a described date: {len(described)}")
        for fn, n in (yr_named + described)[:100]: print(f"    ⚠ {fn}:{n}")
        # THE DATE VOCABULARY (the editor 2026-10-12; the forms in
        # ocr/method/DATE-VOCABULARY-PROPOSAL-2026-10-12.md, parsed by tools/date_vocab.py). Warnings while the six
        # redowsed files are repaired; then a format error under facts-format 3.
        outside = []
        for fn, n, rec in toverify:
            try: date_vocab.parse(rec[1])
            except ValueError: outside.append((fn, n, rec[1]))
        print(f"  dates outside the vocabulary: {len(outside)}")
        for fn, n, d in outside[:200]: print(f"    ⚠ {fn}:{n}: {d[:80]}")
        if "--dates-outside" in sys.argv:   # every one, with its form's count, to sort them by form (2026-10-18)
            dp_ = sys.argv[sys.argv.index("--dates-outside") + 1]
            forms = Counter(re.sub(r"\d", "9", d) for _f, _n, d in outside)
            with open(dp_, "w", encoding="utf-8") as fh:
                fh.write("# form (digits as 9)\tcount\n" + "".join(f"{k}\t{v}\n" for k, v in forms.most_common()))
                fh.write("\n# every date\nfile\tline\tdate\n" + "".join(f"{f}\t{n}\t{d}\n" for f, n, d in outside))
        # the source's precision collapsed to a bare year (the Fable review's finding 2, approved 2026-10-12): the fact
        # names a month, an approximation, an interval or a second year, and the date field is a year alone
        MON = r"(?:januar|februar|mart|april|maj|juni|juli|aŭgust|septembr|oktobr|novembr|decembr)on?"
        coarse = [(fn, n) for fn, n, rec in toverify if re.fullmatch(r"\**\d{4}\**", rec[1].strip()) and re.search(
            rf"\b{MON}\b|\bĉirkaŭ\b|\bproksimume\b|\binter \d{{4}} kaj\b|\b(?:post|antaŭ|ĝis|ekde) (?:\d{{4}}|la \d|{MON}\b)"
            r"|\b(1[89]\d\d)\b.*\b(?!\1)1[89]\d\d\b", rec[2].split("«")[0], re.I)]
        print(f"  dated lines whose fact is more precise or less certain than their date: {len(coarse)}")
        for fn, n in coarse[:200]: print(f"    ⚠ {fn}:{n}")
        # a date computed without saying so (the Fable review's finding 3, approved 2026-10-12): the fact dates the thing
        # relatively («27-jara», «dek tri jarojn poste») and the date is not marked «kalkulite» in pruvo
        uncomputed = [(fn, n) for fn, n, rec in toverify if not re.search(r"sen dato|ĝenerala", rec[1]) and re.search(
            r"jaraĝ|-jara\b|jarojn poste|jaroj poste|post \w+ jaroj|en (?:sia|lia|ŝia) \w+a jaro", rec[2].split("«")[0])
            and "kalkulite" not in rec[5] + rec[1]
            # an age («33-jara») on a line dated to the day is the record's own statement, not a date worked out from
            # it (the Somme death record; the editor 2026-10-13): spared, unless another relative phrase is there
            and not (re.fullmatch(r"\d{4}-\d\d-\d\d", rec[1].strip("* ")) and not re.search(
                r"jarojn poste|jaroj poste|post \w+ jaroj|en (?:sia|lia|ŝia) \w+a jaro", rec[2].split("«")[0]))]
        print(f"  dated lines with a relative date not marked «kalkulite»: {len(uncomputed)}")
        for fn, n in uncomputed[:200]: print(f"    ⚠ {fn}:{n}")
        # a state written «[sen dato]» where «[ĝenerala]» is meant (the Fable review's finding 4 (iv), approved 2026-10-12)
        # … except where the kind decides (2026-10-16 22:2x): origin and character made [ĝenerala] by the profile, the six
        # kinds that may be either guessed as an instant
        kindat = {(fn, n): (k or "").split(":")[0].strip() for fn, n, k in kinded}
        states = [(fn, n) for fn, n, rec in toverify if "sen dato" in rec[1] and (sm := STATE.match(rec[2].split("«")[0]))
                  and not OFFICE.match(rec[2].split("«")[0][sm.end():])
                  and kindat.get((fn, n), "") not in WHOLE_LIFE_KINDS | EITHER_KINDS | {"ofico"}]
        print(f"  undated lines that state a state («[ĝenerala]» wanted): {len(states)}")
        for fn, n in states[:200]: print(f"    ⚠ {fn}:{n}")
        # EVENT KINDS (facts format 4, the editor 2026-10-13): every line of a format-4 file carries a kind on the list in
        # force, with an object (but for birth and death); «alia» with «sugestas: …» (a verb, like «refutas:», the editor 2026-10-13)
        if kinded:
            kinds = kind_list()
            probs = [(fn, n, "no kind field" if k is None else kind_problem(k, kinds)) for fn, n, k in kinded]
            probs = [p for p in probs if p[2]]
            print(f"  event kinds (format 4): {len(kinded)} lines, {len(kinds)} kinds on the list; problems: {len(probs)}")
            for fn, n, why in probs[:200]: print(f"    ⚠ {fn}:{n} {why}")
        # THE FABLE REVIEW'S FINDINGS 5, 7, 8, 9 (the editor 2026-10-12,, «9. … make
        # reasonable effort»): warnings, each pointing at a rule of the facts-writing template
        docdated = [(fn, n) for fn, n, rec in toverify if "sen dato" in rec[1] and re.search(r"\b1[6-9]\d\d-\d\d-\d\d\b", rec[5])]
        print(f"  undated lines whose label dates a quoted document (the document's date dates the line): {len(docdated)}")
        for fn, n in docdated[:200]: print(f"    ⚠ {fn}:{n}")
        # THE UNDATED LIST (dowse runbook D6c step 10c, 2026-10-15; the editor
        #): the four warnings above on undated lines, whole, to a file for tools/dowse-undated.py; create-only
        uflag = next((f for f in ("--undated", "--undated-years") if f in sys.argv), None)
        if uflag:
            up = sys.argv[sys.argv.index(uflag) + 1]
            if os.path.exists(up): print(f"  {uflag}: {up} exists, not overwritten")
            else:
                cls = defaultdict(list)
                # «words» (2026-10-18; the editor):
                # a date field still in words after form_repair's relative_date, outside the vocabulary or an event the
                # calendar does not know, for the reader to date or leave undated
                worded = [(fn, n) for fn, n, rec in toverify if needs_reading(rec[1].strip())]
                for c, lst in (("year", yr_named), ("described", described), ("state", states), ("document", docdated), ("words", worded)):
                    for fn, n in lst: cls[(fn, n)].append(c)
                raw = {}
                with open(up, "w", encoding="utf-8") as fh:
                    fh.write("file\tline\tclass\tthe line as written\n")
                    for (fn, n), cs in sorted(cls.items()):
                        if fn not in raw: raw[fn] = open(os.path.join(SRC, fn), encoding="utf-8").read().split("\n")
                        fh.write("\t".join([fn, str(n), ",".join(cs), raw[fn][n - 1].replace("\t", " ")]) + "\n")
                print(f"  {uflag}: {len(cls)} lines written to {up}")
        badname = [(fn, n, rec[0]) for fn, n, rec in toverify if re.search(r"(?:^|[\s-])[A-ZĈĜĤĴŜŬ]\.?(?:[\s-]|$)|-.*-", rec[0].split("(")[0].strip())]
        print(f"  NAME forms with an initial or two hyphens (NAME is the surname; a given name only as qualifier): {len(badname)}")
        for fn, n, w in badname[:200]: print(f"    ⚠ {fn}:{n}: {w}")
        comment = [(fn, n) for fn, n, rec in toverify if re.search(r"¶\s?\d|\bPDF\s?\d|\brim\.\s?\d", rec[2].split("«")[0])]
        print(f"  facts citing another page or note of the source (commentary belongs in «pruvo:»): {len(comment)}")
        for fn, n in comment[:200]: print(f"    ⚠ {fn}:{n}")
        # our additions in ⟦…⟧ (the editor 2026-10-14,; ocr/method/ALIGN-JAM-RULE-PROPOSAL-2026-10-14.md, B): in a dowse
        # facts file an addition outside the brackets cannot be stripped for comparison or kept in INTERVENTIONS.tsv
        unbr = [(fn, n) for fn, n, rec in toverify if fn.endswith("-dowse.md")
                and re.search(r"pruvo:|nia identigo|korektit|kalkulit|ne kontrolita", re.sub(r"⟦[^⟧]*⟧", "", rec[5]))]
        print(f"  dowse lines with an addition of ours outside ⟦…⟧ (OUR ADDITIONS IN ⟦ ⟧): {len(unbr)}")
        for fn, n in unbr[:200]: print(f"    ⚠ {fn}:{n}")
        # surnames written both with and without a qualifier, whose default bearer the register does not name: there a
        # forgotten qualifier merges two people silently (the Fable review's finding 7, Ezri's risk note, 2026-10-12)
        qualified, bare = Counter(), Counter()
        for fn, n, rec in toverify:
            (qualified if rec[2].startswith("**(") else bare)[rec[0]] += 1
        p = os.path.join(GEN, "profiles", "NAMES-REGISTER.tsv")
        defaults = {r["name"].strip() for r in csv.DictReader((l for l in open(p, encoding="utf-8") if not l.startswith("#")),
                    delimiter="\t") if r.get("relation") == "default bearer"} if os.path.exists(p) else set()
        nodefault = sorted(w for w in qualified if bare[w] and w not in defaults)
        print(f"  surnames with and without a qualifier and no default bearer in the names register: {len(nodefault)}")
        for w in nodefault[:100]: print(f"    ⚠ {w}: {bare[w]} lines without a qualifier, {qualified[w]} with")
        # LINES OF A PERSON THE SCOPE REGISTER HAS OUT (the scope register proposal of 2026-10-13, § 3: «the harvest warns
        # about any line whose person is out»; built 2026-10-15, the editor): every file, not only the formatted
        # ones; an unqualified row puts the surname out, a qualified row only the lines with that qualifier, as the
        # assembler's drop and the copies read the register. The dowse files have none (the assembler drops them); what
        # it finds is in the older files, which no dowse rewrites
        OUTREG, ENT = scope_out(), scope_entities()
        outl = []
        for fn, n, who, line in every:
            mq = re.match(r"^- \$\$\$ [^$]*?(?:\(([^)]*)\))?\s*\$\$\$\s*(?:\(([^)]*)\))?", line)
            q = (mq.group(1) or mq.group(2)) if mq else None
            if slug(re.sub(r"\s*\(.*", "", who)) in ENT: continue      # an entity's lines are no fault
            if out_of_scope(re.sub(r"\s*\(.*", "", who), q, OUTREG): outl.append((fn, n, who, None if "(" in who else q))
        byfile = Counter(fn for fn, *_ in outl)
        byname = Counter(who if not q else f"{who} ({q})" for _, _, who, q in outl)
        print(f"  lines of a person the scope register has out: {len(outl)} in {len(byfile)} files ({sum(v for k, v in byfile.items() if k.endswith('-dowse.md'))} in dowse files)")
        if outl: print("    the most: " + "; ".join(f"{k} {v}" for k, v in byname.most_common(15)))
        for fn, n, who, q in outl[:200]: print(f"    ⚠ {fn}:{n}: {who}{f' ({q})' if q else ''}")
        # JUDGEMENTS UNDER AN EVENT KIND (2026-10-16, «ok»): a fact that reports someone's judgement («X juĝas, ke …»)
        # under a kind other than «juĝo» or «interpreto»; and the lines the date of saying no longer dates (above). Both
        # probable kind faults, for the cleanup (smelt S5) or DECISIONS rows; listed in profiles/build/KIND-FAULTS-LATEST.md
        jk, at = [], {(e[0], e[1]): e[3] for e in every}
        for fn, n, kind in kinded:
            if not kind or kind.split(":")[0].strip() in ("juĝo", "interpreto", "historiografio"): continue
            l = at.get((fn, n), "")
            body = l.split("** · ", 1)[1].split(" · ")[0] if "** · " in l else ""   # the kind is already taken out
            if JUDGE_WORDS.search(body): jk.append(f"{fn}:{n}: {{{kind[:70]}}} · {body[:140]}")
        # AN ACT MARKED [ĝenerala] (2026-10-16 22:2x, the editor): every kind but origin, character, the six that
        # may be either, «alia» and «samnomo» is an act, and an act has a date; a judgement or declaration so marked is
        # dated by its saying above, the rest stay as the reader wrote them
        datef = {(fn, n): rec[1] for fn, n, rec in toverify}
        actg = []
        for fn, n, kind in kinded:
            if not kind or kind.split(":")[0].strip() in NEVER_GENERAL_EXEMPT or "ĝenerala" not in datef.get((fn, n), ""): continue
            l = at.get((fn, n), "")
            body = l.split("** · ", 1)[1].split(" · ")[0] if "** · " in l else ""
            actg.append(f"{fn}:{n}: {{{kind[:70]}}} · {body[:140]}")
        print(f"  judgements under an event kind (a fact «X juĝas, ke …» kinded otherwise): {len(jk)}; "
              f"undated lines with a saying theme under an event kind, no longer dated by the saying: {len(SAYING_SKIPPED)}; "
              f"acts marked [ĝenerala]: {len(actg)}; undated origin lines made [ĝenerala] by their kind: {len(GENERAL_BY_KIND)}; "
              f"page guesses that a neighbour dated by its source's year would have set, and no longer does: {len(SOURCE_YEAR_SKIPS)} "
              f"({', '.join(f'{k} {v}' for k, v in Counter(SOURCE_YEAR_SKIPS).most_common())}); "
              f"page guesses outside the person's life, dropped: {len(LIFE_DROPS)}; "
              f"undated lines dated by their periodical's issue: {len(ISSUE_DATED)} "
              f"({', '.join(f'{k} {v}' for k, v in Counter(ISSUE_DATED).most_common())}); "
              f"lines moved to the other man of their surname by the given name they print: {len(REASSIGNED)} "
              f"({', '.join(f'{a} → {b} {v}' for (a, b), v in Counter((x[1], x[2]) for x in REASSIGNED).most_common())})")
        for x in LIFE_DROPS[:12]: print(f"    life: {x}")
        if not check:
            with open(os.path.join(BUILD, "KIND-FAULTS-LATEST.md"), "w", encoding="utf-8") as fh:
                fh.write("# Probable kind faults — the last build\n\n**GENERATED by `tools/harvest-facts.py` at every build. Do not edit.** "
                         "For the cleanup (the smelt runbook, S5) or DECISIONS rows. The editor, 2026-10-16.\n\n"
                         f"## A fact reporting a judgement, under a kind other than «juĝo» or «interpreto» ({len(jk)})\n\n"
                         + "".join(f"- {x}\n" for x in jk)
                         + f"\n## Undated lines with a saying theme ([AS], [KAR]) under an event kind, no longer dated by the saying ({len(SAYING_SKIPPED)})\n\n"
                         + "".join(f"- {x}\n" for x in SAYING_SKIPPED)
                         + f"\n## An act marked [ĝenerala] ({len(actg)}): a judgement or declaration among them is dated by its saying in the profile\n\n"
                         + "".join(f"- {x}\n" for x in actg))
        # PEOPLE NAMED ONLY IN THE FACT TEXT (2026-10-16; the dowse runbook, D6 point 7; the editor, on Jossinet ¶ 39,
        # Lemaire's faith shaken by the errors in De Beaufront's manuscripts, an «interpreto» under LEMAIRE alone
        # approved): a dowse line whose fact names, by surname, another person with a profile of their own whom its
        # kind field does not name in capitals, so that no copy reaches them. For the editor's evaluation; a listing,
        # not a fix: many are passing mentions. In profiles/build/FACT-TEXT-NAMES-LATEST.md
        # who counts as a person: the scope register's rows that are not entities and not out (a first try on every
        # profile matched title words, «Internacia» of Lingvo Internacia, «Vortaro» of a section's name); a surname
        # several people bear is shown as shared, not given to one of them
        ENTS, OUTS = scope_entities(), scope_out()
        sur = {}
        sp_ = os.path.join(GEN, "profiles", "SCOPE-REGISTER.tsv")
        for r in ([l.rstrip("\n").split("\t") for l in open(sp_, encoding="utf-8") if not l.startswith("#")][1:] if os.path.exists(sp_) else []):
            if len(r) < 5 or r[1] == "entity" or r[4] == "out": continue
            nm = re.sub(r"\s*\(.*", "", r[0]).strip()
            last = nm.split()[-1] if nm else ""
            if len(last) >= 4 and last.isupper(): sur.setdefault(last.capitalize(), set()).add(nm)
        # and the profiles named by one surname, or a particle and a surname (the register lacks Boirac, Bourlet, Privat,
        # Sébert): not the multi-word titles of bodies and periodicals
        for w in people:
            nm = re.sub(r"\s*\(.*", "", w).strip(); ws = nm.split()
            if slug(nm) in ENTS or out_of_scope(nm, None, OUTS): continue
            if len(ws) == 1 or (len(ws) == 2 and ws[0] in ("DE", "VAN", "VON", "DI", "DA", "LE", "LA")):
                if len(ws[-1]) >= 4 and ws[-1].isupper(): sur.setdefault(ws[-1].capitalize(), set()).add(nm)
        pat = surnames_finder(sur) if sur else None
        ft, ft_to = [], Counter()
        for fn, who, date, src, line_, kind_ in (r[:6] for r in now):
            if not fn.endswith("-dowse.md") or not kind_ or "kopio el" in line_ or not pat: continue
            body = line_.split("** · ", 1)[1].split(" · ")[0] if "** · " in line_ else ""
            # not the line's own sayers: its source's author (the dowse file's first word, a contributor) or the
            # «derivita ↤» source («Laŭ Neves …» in Neves's file is attribution, not a fact about Neves)
            sayers = {fn.split("-")[0].lower()}
            mc = re.search(r"⟦kontribuo: ([^⟧]+)⟧|\(kontribuo de ([^)]+)\)", line_); md = re.search(r"derivita[^↤]*↤ ([^;)]+)", line_)
            if mc: sayers.add((mc.group(1) or mc.group(2)).split()[-1].lower())
            if md: sayers |= {w.lower().strip("«»,.") for w in md.group(1).split()}
            # a word followed by a further name, straight or after a particle, is a given name there («Louis de Beaufront»,
            # «Henri Meier»: LOUIS 212, the list's head, was De Beaufront's own first name; 2026-10-18, the dowse fixes)
            given = {m.group(1) for m in re.finditer(r"\b([A-ZĈĜĤĴŜŬ][a-zĉĝĥĵŝŭéèêëàâäîïôöûüç]+)\s+(?:(?:de|van|von|le|la|du|di|da)\s+)?[A-ZĈĜĤĴŜŬ]", body)}
            for nm in set(pat.findall(body)):
                if nm.lower() in sayers: continue
                # the line's own person under another form of the name («Kellerman» in a line of KELLERMANN-REED)
                if nm.upper() in re.sub(r"\s*\(.*", "", who).upper(): continue
                if nm in given and not re.search(rf"\b{re.escape(nm)}\b(?!\s+(?:(?:de|van|von|le|la|du|di|da)\s+)?[A-ZĈĜĤĴŜŬ])", body): continue
                targets = {t for t in sur[nm] if slug(t) != slug(re.sub(r"\s*\(.*", "", who))}
                if not targets or any(t in kind_ for t in targets): continue
                cls = ft_context(body, nm)
                if cls == "out": FT_OUT[0] += 1; continue
                lab = sorted(targets)[0] if len(targets) == 1 else f"{nm.upper()} (shared by {len(targets)})"
                ft.append((lab, f"{fn}: {who} · {{{kind_[:60]}}} · {body[:150]} · {src}", cls)); ft_to[lab] += 1
        # HOMOGRAPHS (2026-10-18, the dowse fixes): a surname whose bearer has two lines or fewer of his own but which the
        # fact texts name 20 times or more is a place or a common name there (PARIS 140: one «M. Paris, directeur de
        # l'École commerciale»; FRANCE 85), not a person missed: listed apart, not counted
        homog = {lab for lab, n in ft_to.items() if n >= 20 and "(shared" not in lab and len(people.get(lab, ())) <= 2}
        ft_h = [x for x in ft if x[0] in homog]; ft = [x for x in ft if x[0] not in homog]
        for lab in homog: ft_to.pop(lab, None)
        FT_HOMOGRAPHS[:] = sorted((lab, sum(1 for x in ft_h if x[0] == lab)) for lab in homog)
        # THE SAME FACT TWICE ON ONE PAGE (2026-10-16; the dowse runbook, D6 point 7, deduping kind (b); the editor):
        # two dowse lines of one person, one file and one place (item and page or ¶) whose facts share most of their
        # content words, e.g. Jossinet ¶ 17, De Beaufront «not accepted as a soldier» written twice. For a DECISIONS row
        # or the cleanup; copies left out (they repeat by design). In profiles/build/DUPLICATES-LATEST.md
        dups = [f"{fn} · {src_}\n  - {bi[:160]}\n  - {bj[:160]}" for fn, src_, bi, bj, _li, _lj in duplicate_pairs(r[:6] for r in now)]
        print(f"  the same fact twice on one page (one person, file and place; facts sharing 80% of their content words): {len(dups)} pairs")
        if not check:
            with open(os.path.join(BUILD, "DUPLICATES-LATEST.md"), "w", encoding="utf-8") as fh:
                fh.write("# The same fact twice on one page — the last build\n\n**GENERATED by `tools/harvest-facts.py` at every build. Do not edit.** "
                         "Two dowse lines of one person, one file and one place whose facts share 80% or more of their content words (copies left out). "
                         "For a DECISIONS row or the cleanup (the dowse runbook, D6 point 7, deduping (b)); some pairs are two facts on one page that read alike.\n\n"
                         + "".join(f"- {x}\n" for x in dups))
        n_in = sum(1 for x in ft if x[2] == "in")
        print(f"  people named only in the fact text of a dowse line, not in its kind (no copy reaches them): {len(ft)}"
              f" ({n_in} clear names by their context, {len(ft) - n_in} for a reader's review; {FT_OUT[0]} ruled out by their context: a periodical's title, an article)"
              + (("; the most: " + "; ".join(f"{k} {v}" for k, v in ft_to.most_common(12))) if ft else "")
              + (("; left out, a place, a common name or a variant spelling of another profile (to check): "
                  + ", ".join(f"{k} {v}" for k, v in FT_HOMOGRAPHS)) if FT_HOMOGRAPHS else ""))
        if not check:
            with open(os.path.join(BUILD, "FACT-TEXT-NAMES-LATEST.md"), "w", encoding="utf-8") as fh:
                fh.write("# People named only in the fact text — the last build\n\n**GENERATED by `tools/harvest-facts.py` at every build. Do not edit.** "
                         "A dowse line whose fact names another person with a profile of their own, by surname, whom its kind field does not name in capitals: no copy reaches them. "
                         "For the editor's evaluation (the dowse runbook, D6 point 7): many are passing mentions; the rest are for a DECISIONS row or the redowse. "
                         f"By context (2026-10-18): **{n_in} clear names** (an initial, a given name or a title before the surname, or the surname in capitals), "
                         f"**{len(ft) - n_in} for a reader's review**; {FT_OUT[0]} occurrences ruled out (inside a periodical's title from BPEAPE, after an article, "
                         "or a sentence's first word with an article after it) are not listed.\n\n")
                for cls_, head_ in (("in", "Clear names"), ("review", "For a reader's review")):
                    fh.write(f"# {head_}\n\n")
                    for t in sorted(ft_to, key=lambda k: -ft_to[k]):
                        rows_ = [x for tt, x, c in ft if tt == t and c == cls_]
                        if rows_: fh.write(f"## {t} ({len(rows_)})\n\n" + "".join(f"- {x}\n" for x in rows_) + "\n")
        twoyears = [(fn, n) for fn, n, rec in toverify if ";" in rec[2].split("«")[0] and len(set(re.findall(r"\b1[6-9]\d\d\b", rec[2].split("«")[0]))) > 1]
        print(f"  facts with «;» and two years (one predicate per line): {len(twoyears)}")
        for fn, n in twoyears[:200]: print(f"    ⚠ {fn}:{n}")
        leaning = [(fn, n, rec[2]) for fn, n, rec in toverify if ANAPHOR.search(rec[2].split("«")[0])]
        print(f"  lines that may lean on another line (EVERY FACTS LINE STANDS ALONE): {len(leaning)}")
        for fn, n, fact in leaning[:200]: print(f"    ⚠ {fn}:{n}: {fact[:90]}")
        # FAULT RATES BY SOURCE (2026-10-16 22:5x; the smelt runbook, S5, «fault rates per type and source»; the editor:
        # approved to building them now as the redowse's baseline, the fix reader left until after the first redowsed source):
        # the counts of the listings above, for each dowse file, with their share of its lines. Read-only over this build;
        # in profiles/build/FAULT-RATES-LATEST.md. A rate that stays high after a redowse points at the reading brief
        dowsef = sorted({fn for fn, _n, _r in toverify if fn.endswith("-dowse.md")})
        nlines = Counter(fn for fn, _n, _r in toverify)
        # a line that goes to a <surname>-ambiguous.md file (no qualifier, or one the PERSONS table does not list)
        ambig = Counter(fn for fn, n, rec in toverify if rec[0] in PERSONS and person_stem(rec[0], person_of(rec[0], rec[2])) is None)
        def pre(xs): return Counter(x.split(":")[0].split(" · ")[0].strip() for x in xs)
        # A QUOTATION IN THE FACT NOT IN ITS ANCHOR (2026-10-17, the resmelt's faults Q: the biography writers could not
        # quote «la dua patro de Esperanto», «kalumnio», «kunaŭtoro de Ido», the anchor holding other words or the Ido
        # edition's): a «…» in the fact whose words (of four letters or more) do not all stand in the line's anchor
        quoted = []
        for fn, n, rec in toverify:
            if not fn.endswith("-dowse.md") or "«" not in rec[2]: continue
            head, _, anc = rec[2].rpartition(" «")
            aw = set(re.findall(r"\w{4,}", anc.lower()))
            for q in re.findall(r"«([^«»]+)»", head):
                if not q[:1].islower(): continue     # a title in «» («La Esperantisto», «Knock»), not a quotation
                qw = set(re.findall(r"\w{4,}", q.lower()))
                if qw and not qw <= aw: quoted.append((fn, n)); break
        cols = [("kind: a judgement under an event kind", pre(jk)),
                ("kind: a saying theme under an event kind", pre(SAYING_SKIPPED)),
                ("the same fact twice on one page", pre(dups)),
                ("a person named only in the fact text", pre(x for _l, x, _c in ft)),
                ("an undated state («[ĝenerala]» wanted)", Counter(fn for fn, _n in states)),
                ("a relative date not marked computed", Counter(fn for fn, _n in uncomputed)),
                ("an addition of ours outside ⟦…⟧", Counter(fn for fn, _n in unbr)),
                ("«;» and two years in one fact", Counter(fn for fn, _n in twoyears)),
                ("a line leaning on another", Counter(fn for fn, _n, _f in leaning)),
                ("a fact citing another page or note", Counter(fn for fn, _n in comment)),
                ("a quotation in the fact not in its anchor", Counter(fn for fn, _n in quoted)),
                ("a line left to a surname's ambiguous file", ambig)]
        print(f"  fault rates by source: {len(dowsef)} dowse files, {len(cols)} types (profiles/build/FAULT-RATES-LATEST.md)")
        if not check:
            with open(os.path.join(BUILD, "FAULT-RATES-LATEST.md"), "w", encoding="utf-8") as fh:
                fh.write("# Fault rates by source — the last build\n\n**GENERATED by `tools/harvest-facts.py` at every build. Do not edit.** "
                         "For each dowse file, the count of each listing this build makes, and its share of the file's lines. "
                         "The smelt runbook, S5, «fault rates per type and source»; the redowse's baseline is a dated copy of this file. "
                         "Some listings are probable faults, not certain ones (a duplicate pair may be two facts; a name in the text may be a passing mention).\n\n")
                fh.write("| type | " + " | ".join(f.replace("-dowse.md", "") for f in dowsef) + " | all |\n")
                fh.write("|---|" + "---|" * (len(dowsef) + 1) + "\n")
                fh.write("| lines | " + " | ".join(str(nlines[f]) for f in dowsef) + f" | {sum(nlines[f] for f in dowsef)} |\n")
                for name, c in cols:
                    tot, totn = sum(c[f] for f in dowsef), sum(nlines[f] for f in dowsef)
                    fh.write(f"| {name} | " + " | ".join(f"{c[f]} ({100 * c[f] / nlines[f]:.1f}%)" if nlines[f] else "0" for f in dowsef)
                             + f" | {tot} ({100 * tot / totn:.1f}%) |\n")
    if errors:
        print("\n=== FORMAT ERRORS ===")
        for fn, n, why, txt in errors[:60]:
            print(f"  {fn}:{n}  {why}\n      {txt}")
        if len(errors) > 60: print(f"  … and {len(errors)-60} more")
    if check:
        return 1 if errors else 0
    # The MISSING-FACTS RULING (2026-10-10): a build with errors writes nothing. It used to write the rest and drop the
    # failing lines from the profiles, silently, with exit 0.
    if errors:
        print(f"\nREFUSED: {len(errors)} format errors; nothing written. Fix them (see --check), then run again.")
        return 1

    if "--csv" in sys.argv:
        p = sys.argv[sys.argv.index("--csv") + 1]
        with open(p, "w", newline="", encoding="utf-8") as fh:
            # The Fable review's S6 (2026-10-10): the independence label on every line, not only on witness lines; the
            # source's item, year of writing, kind and language from the item and language tables; the iteration.
            itn = sys.argv[sys.argv.index("--iteration") + 1] if "--iteration" in sys.argv else ""
            w = csv.writer(fh); w.writerow(["person", "year", "fact", "source", "themes", "confidence", "from", "fact_key", "witness_of",
                                            "independence", "item", "source_written", "source_kind", "source_language", "iteration"])
            for who, rows in sorted(people.items()):
                for y, fact, src, th, c, frm in rows:
                    k = re.search(r"⟨([^⟩]+)⟩", fact); m = re.search(r"⟳ atestanto: *([^;)]+?) *;", c)
                    it, wr, kd, lg = source_info(src)
                    w.writerow([who, y, fact, src, "|".join(th), c, frm, k.group(1) if k else "", m.group(1) if m else "",
                                independence(c), it, wr or "", kd, lg, itn])
        print("wrote", p)

    os.makedirs(OUT, exist_ok=True)
    # Clear orphans BEFORE writing. A profile whose per-source file has been deleted or renamed used
    # to sit on disk forever, still citing locators that no longer resolve — which is how two
    # decoy-sourced profiles survived the deletion of the decoy scout on 2026-09-05. These files are
    # GENERATED, wholly reproducible from by-source/, so clearing them loses nothing.
    # (The clearing itself now happens below, after the collision check, so that a refused build removes nothing.)
    old_profiles = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(OUT, "*.md"))}

    # CONTRIBUTORS (the editor 2026-10-12 01:1x
    #): a line from a collective volume or a journal names the contribution's author
    # after its locator, from profiles/CONTRIBUTORS.tsv (item, PDF pages, author, title), so the verdict is the author's
    contrib = defaultdict(list)
    cp = os.path.join(GEN, "profiles", "CONTRIBUTORS.tsv")
    for l in (open(cp, encoding="utf-8") if os.path.exists(cp) else []):
        x = l.rstrip("\n").split("\t")
        if l.startswith("#") or x[0] == "item" or len(x) < 4 or not x[1].isdigit() or not x[2].isdigit(): continue
        contrib[x[0]].append((int(x[1]), int(x[2]), x[3]))
    def contributor(src):
        ms = locators(src)
        if not ms or ms[0].group("item").strip() not in contrib: return ""
        n = ms[0].group("pdf") or ms[0].group("para")
        # ⟦kontribuo: X⟧ among the line's labels, not a bracket after the page (2026-10-17; the editor
        #): the locator stays the volume's key and page, and
        # the attribution, ours, from our register, is marked as ours, as the hostile-witness label is
        return next((f" ⟦kontribuo: {a}⟧" for lo, hi, a in contrib[ms[0].group("item").strip()] if n and lo <= int(n) <= hi), "")

    # EVENT CALENDAR (QUEUE item 6b; confirmed 2026-10-12 01:3x): a line dated only by an event's year (or year and month)
    # whose fact names the event's place and a congress shows the calendar's days beside its own date; the source's own
    # date stays first (precedence: source, computed, calendar, context). Undated lines are not touched.
    cal = []
    calp = os.path.join(GEN, "profiles", "EVENT-CALENDAR.tsv")
    for l in (open(calp, encoding="utf-8") if os.path.exists(calp) else []):
        x = l.rstrip("\n").split("\t")
        if l.startswith("#") or x[0] == "event" or len(x) < 4: continue
        # the «status» column (2026-10-22): «ne okazis» for a congress planned and not held (Paris, 1914)
        cal.append((re.compile(x[1], re.I), x[2], x[3], x[5].strip() if len(x) > 5 else ""))
    def calendar(y, fact):
        m = re.fullmatch(r"(\d{4})(?:-(\d\d))?", y.strip())
        if not m or not re.search(r"kongres|congr|\bUK\b", fact, re.I): return y
        for rx, yr_, days, st in cal:
            if m.group(1) == yr_ and rx.search(fact) and (not m.group(2) or days.startswith(f"{yr_}-{m.group(2)}")):
                if st == "ne okazis": return f"{y} [la kongreso planita: {days}, ne okazis, laŭ la kalendaro]"
                return f"{y} [la kongreso: {days}, laŭ la kalendaro]"   # the congress's days, not the line's: a line may be about the run-up
        return y

    def line(who, r, indent=""):
        y, fact, src, th, c, frm = r
        kind = KINDS.get((frm, src, fact, slug(who)))      # facts format 4: the event kind, shown after the date
        y = calendar(y, fact)
        if (r_ := resolved(y)): y = f"{y} [{r_.edtf}, laŭ la kalendaro]"   # an event form, resolved
        c = c + contributor(src)
        fact, c = re.sub(r"\bEzri\b", "AI", fact), re.sub(r"\bEzri\b", "AI", c)
        c = re.sub(r"^📄", "📣", c)   # the relaying mark: 📄 in older files, shown as 📣 (2026-10-13)   # «No \"Ezri\" in the dowse facts, but \"AI\"» (the editor 2026-10-12)
        if frm in FMT3:   # show the anchor as its own field again, bare
            fact = re.sub(r" «([^«»]*(?:«[^»]*»[^«»]*)*)»$", r" · \1", fact)
        themes = "".join("[" + t + "]" for t in th) or "[?]"   # never an empty field (the Fable review, 13)
        return f"{indent}- $$$ {who} $$$ **{y}** · {'{' + kind + '} · ' if kind else ''}{fact} · {src} · {themes} · {c}  ⟵ `{frm}`\n"

    # WITNESSES, 2026-10-09 (editor
    # plan: plans/second-witnesses-plan-2026-10-09.md).
    # A witness line carries a fact key ⟨…⟩ in its fact and «⟳ atestanto: <facts file>, <date>» in its
    # confidence, naming the line it witnesses (and, where that file has several lines of that date, a few of its words:
    # «⟳ atestanto: <file>, <date>, «<words>»; <label>»). The older line is NOT edited (runbook D6a (e): a dowse never
    # touches scout-made files); the harvester finds it here, in the same profile, by facts file and date,
    # and prints the group together: the witnessed line, then its witnesses indented. Within a group the
    # members are ordered by SOURCE date, not by when they were dowsed (editor, 13:4x
    #), from profiles/SOURCE-DATES.tsv (facts file →
    # year, or «fact» where the source is a document of the time or an edition of one, so the fact's own date
    # is the source's); where a member's source date is not known, the witnessed line stays first.
    WIT = re.compile(r"⟳ atestanto: *([^,;)]+?\.md), *([^,;)«]+?)(?:, *«([^»]+)»)? *;")
    KEY = re.compile(r"⟨([^⟩]+)⟩")
    sdates = {}
    sdp = os.path.join(GEN, "profiles", "SOURCE-DATES.tsv")
    if os.path.exists(sdp):
        for l in open(sdp, encoding="utf-8"):
            if l.startswith("#") or not l.strip(): continue
            fn, d = (l.rstrip("\n").split("\t") + [""])[:2]
            sdates[fn.strip()] = d.strip()
    def srcdate(r):
        """Sort key by the SOURCE's date (the Fable review's S5, 2026-10-10): the item table's year of writing for a line
        whose locator names an item key, else profiles/SOURCE-DATES.tsv; PRIMARY before SECONDARY within a year; None if
        the source's date is unknown."""
        it, wr, kd, _ = source_info(r[2])
        rank = 0 if kd == "PRIMARY" else 1
        if wr is not None: return (0, wr, rank)
        d = sdates.get(r[5])
        if d is None: return None
        return (sortkey(r[0]) if d == "fact" else sortkey(d)) + (rank,)
    def grouped(rows):
        """rows: (who, r) sorted by year. Returns [(who, r, indent)], witnesses under what they witness."""
        wit, out_of = defaultdict(list), set()
        for i, (who, r) in enumerate(rows):
            m = WIT.search(r[4])
            if not m: continue
            fn, d, snip = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
            tgt = [j for j, (w2, r2) in enumerate(rows) if j != i and r2[5] == fn and r2[0] == d and not WIT.search(r2[4])
                   and (not snip or snip in r2[1])]
            if len(tgt) == 1:
                wit[tgt[0]].append(i); out_of.add(i)
            else:
                print(f"  ⚠ WITNESS NOT JOINED ({len(tgt)} candidates): {who} {r[0]} → {fn}, {d}")
        res = []
        for j, (who, r) in enumerate(rows):
            if j in out_of: continue
            members = [j] + wit.get(j, [])
            if len(members) > 1:      # undated sources last, never first by accident of dowse order (S5)
                members.sort(key=lambda k: (srcdate(rows[k][1]) is None, srcdate(rows[k][1]) or (0, 0, 0)))
            for n, k in enumerate(members):
                res.append((rows[k][0], rows[k][1], "" if n == 0 else "  "))
        return res

    # A PLAN SHOWN TWICE (2026-10-22; the editor,
    # approved). The facts file keeps one line, the one
    # source of truth; the profile shows it twice: the act (the proposal of a «deliberado», else the announcement) at its
    # ⟦anoncita⟧ date among the real dates, and the plan at its «☞» date with its status: «realigita» (a line of the same
    # person in its fact group, fact-groups.py's entity match, with a real date the plan's allows), «malsukcesis» (a
    # line of the group, or the plan's own, says it was given up, put off, cancelled, refused or failed, or the calendar
    # has the congress «ne okazis»), else «ne konfirmita» (not in our corpus: the list of tentatives).
    ENDED = re.compile(r"\b(?:forlasit|nuligit|rezignit|malakceptit|prokrastit|ĉesigit|rifuzit|ne realigit|malsukces)\w*|\bvan[ae]\b")
    ANN = re.compile(r"⟦anoncita ((?:inter \S+ kaj \S+)|\d{4}(?:-\d\d){0,2})(, laŭ la enhavo)?⟧")
    def rkey(who, r): return (r[5], r[2], r[1], slug(who), r[0])
    STATUS, ACT = {}, set()
    plan_people = {w for w in people if any(r[0].rstrip().endswith("☞") for r in people[w])}
    if plan_people:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("fact_groups", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fact-groups.py"))
        _fg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fg)
        def as_row(w, r):
            k = KINDS.get((r[5], r[2], r[1], slug(w)))
            return (w, r[5], r[0], k, f"- $$$ {w} $$$ **{r[0]}** · {r[1]} · {r[2]} · {r[4]}", r) if k else None
        corpus = [x for w in people for r in people[w] for x in [as_row(w, r)] if x]
        mine = [x for x in corpus if x[0] in plan_people]
        bykey = {(x[0], x[4]): x[5] for x in mine}
        grps, _noms = _fg.groups_entity([x[:5] for x in mine], [x[:5] for x in corpus])
        member = defaultdict(list)
        for _w, _k, _key, rs in grps:
            for x in rs: member[(x[0], x[4])].append(rs)
        def cal_failed(r, pd):
            # only a plan for the congress's own days (the status sample, 2026-10-22: Blaise's lecture «pri la venonta
            # Kongreso en Parizo», May 1914, was held; the British group's journey of 1 August was made)
            m = re.match(r"\D*(\d{4})", r[0])
            if not (m and pd and re.search(r"kongres|congr|\bUK\b", r[1], re.I)): return False
            for rx, yr_, days, st in cal:
                if st != "ne okazis" or yr_ != m.group(1) or not rx.search(r[1]): continue
                a, _, b = days.partition("/")
                try: cd = date_vocab.parse(f"de {a} ĝis {a[:8] + b if len(b) == 2 else b}")
                except ValueError: continue
                if pd.kind not in ("none", "general", "event", "copies") and date_vocab.compatible(pd, cd): return True
            return False
        def cal_held(r, pd):
            # «LA EVENTO OKAZIS» (2026-10-22; the editor, on X proposing Y and others making it happen
            #): a plan for a congress the calendar has as held, its date in the congress's days; the event is
            # attested, the person's part in it not (Zamenhof's arrival in Washington, 12 August 1910; Decarli's Orestes)
            m = re.match(r"\D*(\d{4})", r[0])
            if not (m and pd and re.search(r"kongres|congr|\bUK\b", r[1], re.I)): return None
            for rx, yr_, days, st in cal:
                if st == "ne okazis" or yr_ != m.group(1) or not rx.search(r[1]): continue
                a, _, b = days.partition("/")
                try: cd = date_vocab.parse(f"de {a} ĝis {a[:8] + b if len(b) == 2 else a[:5] + b if len(b) == 5 else b}")
                except ValueError: continue
                if pd.kind not in ("none", "general", "event", "copies") and date_vocab.compatible(pd, cd): return days
            return None
        POSTPONED = re.compile(r"\bprokrastit\w*")
        def item_of(src):
            ms = locators(src)
            return ms[0].group("item") if ms else src
        for w in plan_people:
            acts = []
            for r in people[w]:
                if not r[0].rstrip().endswith("☞"): continue
                try: pd = date_vocab.parse(r[0].strip())
                except ValueError: pd = None
                st = "ne konfirmita"
                gs = member.get((w, f"- $$$ {w} $$$ **{r[0]}** · {r[1]} · {r[2]} · {r[4]}"), [])
                others = [bykey.get((x[0], x[4])) for g_ in gs for x in g_]
                others = [o for o in others if o and o is not r]
                said = [r[1]] + [x for o in others for x in (o[1], KINDS.get((o[5], o[2], o[1], slug(w)), ""))]
                if any(POSTPONED.search(x) for x in said) and not any(ENDED.search(POSTPONED.sub("", x)) for x in said):
                    st = "prokrastita"           # put off is not failed (Ostrovskij's dictionary, 1893)
                elif any(ENDED.search(POSTPONED.sub("", x)) for x in said) or cal_failed(r, pd):
                    st = "malsukcesis"
                else:
                    for o in others:
                        if o[0].rstrip().endswith("☞") or not o[0].strip() or "sen dato" in o[0]: continue
                        # a realisation is reported elsewhere: a later issue or another source, not another line of the
                        # announcement itself (the status sample: the Antwerp cast lists, «ludu …», matched each other)
                        if item_of(o[2]) == item_of(r[2]): continue
                        try: od = date_vocab.parse(o[0].strip())
                        except ValueError: continue
                        unbounded = ("none", "general", "event", "copies")   # compatible() says True for these: no evidence
                        if pd and pd.kind not in unbounded and od.kind not in unbounded and date_vocab.compatible(pd, od):
                            st = f"realigita: {o[0].strip()}, `{o[5]}`"; break
                    if st == "ne konfirmita" and (held := cal_held(r, pd)):
                        st = f"la evento okazis: {held}, laŭ la kalendaro"
                STATUS[rkey(w, r)] = st
                ma = ANN.search(r[4])
                if ma and not WIT.search(r[4]):
                    k = KINDS.get((r[5], r[2], r[1], slug(w)), "")
                    what = "propono" if k.startswith("deliberado") else "anonco"
                    act = (ma.group(1), r[1], r[2], r[3], f"la {what} de plano, ☞ {r[0].strip()}; " + r[4], r[5])
                    acts.append(act); ACT.add(rkey(w, act))
            people[w].extend(acts)
        n_st = Counter(s.split(":")[0] for s in STATUS.values())
        print(f"  plans: {len(STATUS)} lines with «☞»; {len(ACT)} acts shown at their announcement's date; "
              + ", ".join(f"{k} {v}" for k, v in sorted(n_st.items())))
    _line = line
    def line(who, r, indent=""):
        s = _line(who, r, indent)
        st = STATUS.get(rkey(who, r))
        return s.replace("  ⟵ `", f" · stato: {st}  ⟵ `", 1) if st else s

    seen_stems = Counter()
    def write_profile(stem, title, rows, note=""):
        seen_stems[stem] += 1
        if seen_stems[stem] > 1: print(f"  ⚠ COLLISION: {stem}.md written twice ({title}); facts would be lost")
        # Within a year: by the source's year of writing, then by facts file (the Fable review's S10: the order used to
        # follow file names only, so renaming a facts file reordered published entries).
        rows.sort(key=lambda r: (sortkey(r[1][0]), source_info(r[1][2])[1] or 9999, r[1][5]))
        g = grouped(rows)
        nw = sum(1 for _, _, ind in g if ind)
        na = sum(1 for w_, r_ in rows if rkey(w_, r_) in ACT)   # the acts: a plan's second showing, not another fact
        with open(os.path.join(OUT, f"{stem}.md"), "w", encoding="utf-8") as fh:
            # The profile's own text in Esperanto (2026-10-10, the prosopography is in Esperanto; the editor: «pummel through
            # your short list», item 1). The heading keeps its «# NAME — …» shape, which tools/ocr-dowse.py's date check reads.
            nf, ns = len(rows) - nw - na, len({r[1][5] for r in rows})
            fh.write(f"# {title} — rikoltita profilo\n\n"
                     f"**GENERITA de `tools/harvest-facts.py`. Ne redaktu ĉi tie: redaktu la fontan dosieron nomitan ĉe ĉiu linio.**\n"
                     f"**{nf} fakto{'j' if nf != 1 else ''}, el {ns} fonto{'j' if ns != 1 else ''}"
                     + (f"; {nw} plia{'j' if nw != 1 else ''} atestanta{'j' if nw != 1 else ''} linio{'j' if nw != 1 else ''}, enŝovita{'j' if nw != 1 else ''} sub la fakto, kiun {'ili' if nw != 1 else 'ĝi'} atestas" if nw else "")
                     + f".** Ordigitaj laŭ jaro; `[sen dato]` laste.\n\n{note}")
            for who, r, ind in g:
                fh.write(line(who, r, ind))

    # PERSONS surnames: one file per person, an ambiguous file, and an index under the surname's own name.
    split, merges, index = defaultdict(list), [], {}
    for who in [w for w in people if w in PERSONS]:
        labels, amb = [], []
        for r in people[who]:
            label = person_of(who, r[1])
            stem = person_stem(who, label)
            if stem is None:
                amb.append((label, (who, r)))
            else:
                split[stem].append((who, r)); labels.append((label, stem))
        index[who] = (dict(labels), amb)
    standalone = {slug(w): w for w in people if w not in PERSONS}
    for stem in split:
        if stem in standalone:   # e.g. RENÉ LEMAIRE lines written without the qualifier
            w = standalone.pop(stem)
            split[stem].extend((w, r) for r in people[w]); merges.append((w, stem))
    # Refuse before writing if two profiles would land in one file (it used to print «facts would be lost» and overwrite).
    planned = Counter([slug(w) for w in standalone.values()] + list(split)
                      + [slug(who) for who in index] + [slug(who) + "-ambiguous" for who, (_l, amb) in index.items() if amb])
    clash = sorted(s for s, c in planned.items() if c > 1)
    if clash:
        print(f"\nREFUSED: {len(clash)} profile file(s) would be written twice, losing facts: {', '.join(clash)}. Nothing written.")
        return 1
    # only the profiles this tool wrote (2026-10-16: a hand-made file in profiles/, ENTITY-CANDIDATES-2026-10-16.md, was
    # deleted here by the first harvest after it and, git-ignored like the profiles, lost): a file without the
    # «GENERITA de `tools/harvest-facts.py`» header in its first lines is kept, and named
    for p in glob.glob(os.path.join(OUT, "*.md")):
        head = open(p, encoding="utf-8", errors="replace").read(600)
        if "GENERITA de `tools/harvest-facts.py`" in head: os.remove(p)
        else: print(f"  ⚠ kept, not written by the harvest: {os.path.relpath(p, REPO)} (hand-made files belong elsewhere)")
    # OUT BY THE SCOPE REGISTER (2026-10-15, the editor to «mark rather than drop»): a profile all of whose lines
    # are of a person the register has out gets a banner, and tools/dowse-full-roster.py leaves it out of the dowse
    # roster. The lines stay, so a wrong «out» row (some rest on one Wikipedia witness) can be seen and corrected.
    OUTR = scope_out()
    tot_w, out_w = Counter(), Counter()
    for _fn, _n, who_, line_ in every:
        mq = re.match(r"^- \$\$\$ [^$]*?(?:\(([^)]*)\))?\s*\$\$\$\s*(?:\(([^)]*)\))?", line_)
        q_ = (mq.group(1) or mq.group(2)) if mq else None
        tot_w[who_] += 1
        if out_of_scope(re.sub(r"\s*\(.*", "", who_), q_, OUTR): out_w[who_] += 1
    ENTR = scope_entities()
    def banner(n_out, who=""):
        if slug(re.sub(r"\s*\(.*", "", who)) in ENTR:   # the same banner word, which dowse-full-roster.py reads
            return (f"**{OUT_BANNER}** (`profiles/SCOPE-REGISTER.tsv`): ne persono, sed unuo (korpo, periodaĵo, evento, dokumento aŭ lingvo); "
                    "ĝi ne estas en la prosopografio, kaj neniu linio estas kopiata al ĝi. La faktoj restas videblaj.\n\n")
        return (f"**{OUT_BANNER}** (`profiles/SCOPE-REGISTER.tsv`): ĉiuj {n_out} linioj estas pri persono, kiun la registro tenas ekster la amplekso. "
                "La faktoj restas, por ke malĝusta vico estu videbla kaj korektebla; la dowse ne plu serĉas ĉi tiun personon.\n\n")
    n_banner = 0
    written = 0
    for w in sorted(standalone.values()):
        isout = tot_w[w] and out_w[w] == tot_w[w]; n_banner += bool(isout)
        write_profile(slug(w), w, [(w, r) for r in people[w]], banner(out_w[w], w) if isout else ""); written += 1
    for who, (labels, amb) in sorted(index.items()):
        s = slug(who)
        lines_ = [f"# {who} — indekso de kunhavata familia nomo\n\n",
                  "**GENERITA de `tools/harvest-facts.py`.** Pluraj personoj havas ĉi tiun familian nomon (la tabelo PERSONS en la rikoltilo); "
                  "ĉiu havas propran profilon, kaj la faktoj, kiuj ne distingas ilin, estas tenataj en la dosiero de la ambiguaj, ne kunfanditaj en iun ajn.\n\n"]
        for label, stem in sorted(set(labels.items()), key=lambda x: x[0]):
            lines_.append(f"- [{label}]({stem}.md) — {len(split[stem])} faktoj\n")
        if amb:
            lines_.append(f"- [ambigua: ne atribuebla al unu persono]({s}-ambiguous.md) — {len(amb)} faktoj\n")
            note = ("Faktoj pri **" + who + "**, kiujn la tabelo PERSONS ne povas doni al unu persono: fakto, kiu nomas plurajn el ili, "
                    "skolto, kiu ne povis distingi, aŭ linio sen kvalifiko aŭ kun kvalifiko ne en la tabelo. Solvu per nova kvalifiko de la linio en ĝia fonta dosiero.\n\n")
            groups = defaultdict(list)
            for label, wr in amb: groups[label].append(wr)
            with open(os.path.join(OUT, f"{s}-ambiguous.md"), "w", encoding="utf-8") as fh:
                fh.write(f"# {who}, ambigua — rikoltita profilo\n\n"
                         f"**GENERITA de `tools/harvest-facts.py`. Ne redaktu ĉi tie: redaktu la fontan dosieron nomitan ĉe ĉiu linio.**\n"
                         f"**{len(amb)} faktoj.** {note}")
                for label in sorted(groups):
                    fh.write(f"## {label} — {len(groups[label])} faktoj\n\n")
                    for w, r in sorted(groups[label], key=lambda x: sortkey(x[1][0])):
                        fh.write(line(w, r))
                    fh.write("\n")
            written += 1
        seen_stems[s] += 1
        if seen_stems[s] > 1: print(f"  ⚠ COLLISION: {s}.md (index of {who}) written twice")
        with open(os.path.join(OUT, f"{s}.md"), "w", encoding="utf-8") as fh:
            fh.write("".join(lines_))
        written += 1
    for stem, rows in sorted(split.items()):
        label = next(l for (l, st) in ((l, st) for _, (lab, _a) in index.items() for l, st in lab.items()) if st == stem)
        who0 = rows[0][0] if rows else ""
        isout = bool(rows) and out_of_scope(re.sub(r"\s*\(.*", "", who0), label, OUTR); n_banner += bool(isout)
        write_profile(stem, label, rows, banner(len(rows)) if isout else ""); written += 1
    for w, stem in merges:
        print(f"  merged the stand-alone profile {w} into {stem}.md")
    print(f"  profiles marked out by the scope register (all their lines out; left out of the dowse roster): {n_banner}")
    print(f"wrote {written} profiles to {os.path.relpath(OUT, REPO)}/")
    missing_facts(now, old_profiles, {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(OUT, "*.md"))})
    return 0

if __name__ == "__main__":
    sys.exit(main())
