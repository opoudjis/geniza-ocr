#!/usr/bin/env python3
r"""date_vocab.py — the dowse's date vocabulary: parse a facts line's date field, convert it to EDTF, compare dates.

The editor, 2026-10-12 (
; approved): readers write the date field in a closed Esperanto vocabulary close to the
source's words; the tools convert it to EDTF (ISO 8601-2, the Extended Date/Time Format) for sorting, the event calendar
and grouping. The vocabulary and its rules: geniza/ocr/method/DATE-VOCABULARY-PROPOSAL-2026-10-12.md.

    D  := YYYY | YYYY-MM | YYYY-MM-DD [m.s.]        (m.s.: a Julian date, converted to Gregorian; day precision only)
    QD := [verŝajne ][ĉirkaŭ ]D                     (~ approximate, ? uncertain, % both)
    QD                         a point                  1908~
    de QD ĝis QD               it lasted                1881/1882
    ekde QD | ĝis QD           it lasted, one end open  1905/.. | ../1900
    inter QD kaj QD            once, somewhen between   [1882..1887]
    antaŭ QD | post QD         once or lasting, strictly before / after   [..1904] | [1905-09..]   (antaŭ 1905, post 1905-08)
    dum aŭ antaŭ QD | dum aŭ post QD   once, in or before / in or after   [..1905] | [1905-08..]   (2026-10-22)
    komence|meze|fine de Y[-M] part of a year or month  [1893-10..1893-12]
    la NNN0aj jaroj            a decade                 192X
    post|antaŭ|dum <event>     relative to an event     resolved by the caller from the event calendar
    YYYY+YYYY                  the dates of two copies  {2018,2019}   (copy-difference lines only)
    [sen dato] | [ĝenerala]    no date | a state, never guessed
    <any of the above>☞        a plan: the date it was meant for, which the source does not say happened; the
                               announcement's own date goes in the voice field, ⟦anoncita …⟧ (2026-10-22, the editor:
; a suffix: a
                               real date sorts before the same date planned)

parse(field) -> Date or raises ValueError (the field outside the vocabulary). A Date has kind («point», «span», «oneof»,
«event», «none», «general»), edtf, lo and hi (ISO day bounds, or None for an open end), approx and uncertain, and, for
an event, rel and phrase. compatible(a, b): the ranges overlap, «about» widened by one unit of its precision (ruled
2026-10-12). Read-only: nothing here writes a file.   python3 tools/date_vocab.py --test
"""
import calendar as _cal, datetime, re, sys
from dataclasses import dataclass, field

_D = r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(\s+m\.s\.)?"
# No «ĉirkaŭ» or «verŝajne» inside a set (inter, antaŭ, post): EDTF shows no qualified member of a set, and python-edtf
# refuses one («[1917~..1920]»); an unsure reader writes a wider range (2026-10-13, the editor;
# the spec, www.loc.gov/standards/datetime/, saved sources/web-2026-10-13-edtf/)
NOQUAL = "no «ĉirkaŭ» or «verŝajne» inside «inter», «antaŭ» or «post»: write a wider range instead"
_QD = r"((?:verŝajne\s+)?(?:ĉirkaŭ\s+)?)" + _D
PLANNED = "☞"     # the plan's suffix (U+261E), 2026-10-22


@dataclass
class Date:
    kind: str
    edtf: str = ""
    lo: str = None
    hi: str = None
    approx: bool = False
    uncertain: bool = False
    unit: str = ""            # «year», «month», «day»: the precision, for widening
    rel: str = ""
    phrase: str = ""
    words: str = field(default="", repr=False)
    planned: bool = False     # «…☞»: meant for this date, not attested as done (2026-10-22)


def julian_to_gregorian(y, m, d):
    a = (14 - m) // 12; y2 = y + 4800 - a; m2 = m + 12 * a - 3
    jdn = d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - 32083
    return datetime.date.fromordinal(jdn - 1721425)


def _bounds(y, m, d):
    if d: return f"{y:04d}-{m:02d}-{d:02d}", f"{y:04d}-{m:02d}-{d:02d}", "day"
    if m: return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{_cal.monthrange(y, m)[1]:02d}", "month"
    return f"{y:04d}-01-01", f"{y:04d}-12-31", "year"


def _qd(groups):
    """(qualifier, YYYY, MM, DD, m.s.) -> (edtf, lo, hi, approx, uncertain, unit)"""
    q, y, m, d, ms = groups
    y, m, d = int(y), int(m) if m else 0, int(d) if d else 0
    if m and not 1 <= m <= 12: raise ValueError(f"month {m}")
    if d and not 1 <= d <= _cal.monthrange(y, m)[1]: raise ValueError(f"day {d}")
    if ms:
        if not d: raise ValueError("m.s. needs a full date")
        g = julian_to_gregorian(y, m, d); y, m, d = g.year, g.month, g.day
    lo, hi, unit = _bounds(y, m, d)
    core = f"{y:04d}" + (f"-{m:02d}" if m else "") + (f"-{d:02d}" if d else "")
    approx, unc = "ĉirkaŭ" in q, "verŝajne" in q
    return core + ("%" if approx and unc else "~" if approx else "?" if unc else ""), lo, hi, approx, unc, unit


def parse(field):
    s = " ".join(field.replace("*", "").split())
    if s.endswith(PLANNED):
        core = s[:-1].rstrip()
        if PLANNED in core or core.startswith("["): raise ValueError("«☞» follows a date, once")
        d = parse(core); d.planned = True; d.words = s
        return d
    if s == "[sen dato]": return Date("none", words=s)
    if s == "[ĝenerala]": return Date("general", words=s)
    # the dates of two copies that differ («(diferenco inter la kopioj)» lines; the editor 2026-10-12
    #): not an event, an all-of set; sorted by the first, matches nothing
    if m := re.fullmatch(r"(\d{4})\+(\d{4})", s):
        return Date("copies", f"{{{m.group(1)},{m.group(2)}}}", f"{m.group(1)}-01-01", f"{m.group(2)}-12-31", unit="year", words=s)
    if m := re.fullmatch(_QD, s):
        e, lo, hi, a, u, unit = _qd(m.groups()); return Date("point", e, lo, hi, a, u, unit, words=s)
    if m := re.fullmatch(rf"de {_QD} ĝis {_QD}", s):
        e1, lo, _, a1, u1, unit = _qd(m.groups()[:5]); e2, _, hi, a2, u2, _ = _qd(m.groups()[5:])
        if lo > hi: raise ValueError("span ends before it starts")
        return Date("span", f"{e1}/{e2}", lo, hi, a1 or a2, u1 or u2, unit, words=s)
    if m := re.fullmatch(rf"(ekde|ĝis) {_QD}", s):
        e, lo, hi, a, u, unit = _qd(m.groups()[1:])
        if m.group(1) == "ekde": return Date("span", f"{e}/..", lo, None, a, u, unit, words=s)
        return Date("span", f"../{e}", None, hi, a, u, unit, words=s)
    if m := re.fullmatch(rf"inter {_QD} kaj {_QD}", s):
        e1, lo, _, a1, u1, unit = _qd(m.groups()[:5]); e2, _, hi, a2, u2, _ = _qd(m.groups()[5:])
        if lo > hi: raise ValueError("«inter» ends before it starts")
        if a1 or a2 or u1 or u2: raise ValueError(NOQUAL)
        # A set's two ends at one precision (2026-10-13, tested against python-edtf 5.0.2: «[1917..1920-08]» rejected,
        # «[1917-01..1920-08]» accepted; the editor): the coarser end written at the finer precision from its bound
        (c1, q1), (c2, q2) = (re.match(r"([\d-]+)(.*)", x).groups() for x in (e1, e2))
        if len(c1) != len(c2):
            n = max(len(c1), len(c2))
            c1, c2 = (lo[:n] if len(c1) < n else c1), (hi[:n] if len(c2) < n else c2)
            e1, e2 = c1 + q1, c2 + q2
        return Date("oneof", f"[{e1}..{e2}]", lo, hi, a1 or a2, u1 or u2, unit, words=s)
    # STRICT AND INCLUSIVE (2026-10-22; the editor
    # «dum aŭ
    # post»): «post X» / «antaŭ X» exclude X (from the day after X ends / to the day before X begins); «dum aŭ post X» /
    # «dum aŭ antaŭ X» include it. Until now «post X» had EDTF «[X..]» (inclusive) and its bound X's last day: neither
    if m := re.fullmatch(rf"(dum aŭ antaŭ|dum aŭ post|antaŭ|post) {_QD}", s):
        if re.search(r"\b(?:ĉirkaŭ|verŝajne)\b", s): raise ValueError(NOQUAL)
        e, lo, hi, a, u, unit = _qd(m.groups()[1:])
        if m.group(1) == "dum aŭ antaŭ": return Date("oneof", f"[..{e}]", None, hi, a, u, unit, words=s)
        if m.group(1) == "dum aŭ post": return Date("oneof", f"[{e}..]", lo, None, a, u, unit, words=s)
        if m.group(1) == "antaŭ":
            b = _shift(lo, -1); return Date("oneof", f"[..{_at(b, unit)}]", None, b, a, u, unit, words=s)
        b = _shift(hi, 1); return Date("oneof", f"[{_at(b, unit)}..]", b, None, a, u, unit, words=s)
    if m := re.fullmatch(r"(komence|meze|fine) de (\d{4})(?:-(\d{2}))?", s):
        part, y, mo = m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else 0
        if mo:
            last = _cal.monthrange(y, mo)[1]
            d1, d2 = {"komence": (1, 10), "meze": (11, 20), "fine": (21, last)}[part]
            lo, hi = f"{y:04d}-{mo:02d}-{d1:02d}", f"{y:04d}-{mo:02d}-{d2:02d}"
            return Date("oneof", f"[{lo}..{hi}]", lo, hi, unit="day", words=s)
        m1, m2 = {"komence": (1, 3), "meze": (5, 8), "fine": (10, 12)}[part]
        lo, hi = f"{y:04d}-{m1:02d}-01", f"{y:04d}-{m2:02d}-{_cal.monthrange(y, m2)[1]:02d}"
        return Date("oneof", f"[{y:04d}-{m1:02d}..{y:04d}-{m2:02d}]", lo, hi, unit="month", words=s)
    if m := re.fullmatch(r"la (\d{3})0aj jaroj", s):
        d = int(m.group(1)) * 10
        return Date("oneof", f"{m.group(1)}X", f"{d:04d}-01-01", f"{d + 9:04d}-12-31", unit="year", words=s)
    if m := re.fullmatch(r"(dum aŭ post|dum aŭ antaŭ|post|antaŭ|dum) (\D.*)", s):
        return Date("event", rel=m.group(1), phrase=m.group(2), words=s)
    raise ValueError(f"outside the date vocabulary: «{s}»")


def _shift(iso, days):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=days)).isoformat()


def _at(iso, unit):
    """An ISO day written at a precision: «1906-01-01» at «year» is «1906»."""
    return iso[:4] if unit == "year" else iso[:7] if unit == "month" else iso


def resolve(dt, lo, hi):
    """An «event» Date, given the event's own first and last day (from the calendar) -> a Date with bounds; «post» and
    «antaŭ» strict, «dum aŭ post» and «dum aŭ antaŭ» inclusive of the event (2026-10-22)."""
    if dt.rel == "post": b = _shift(hi, 1); return Date("oneof", f"[{b}..]", b, None, unit="day", words=dt.words)
    if dt.rel == "antaŭ": b = _shift(lo, -1); return Date("oneof", f"[..{b}]", None, b, unit="day", words=dt.words)
    if dt.rel == "dum aŭ post": return Date("oneof", f"[{lo}..]", lo, None, unit="day", words=dt.words)
    if dt.rel == "dum aŭ antaŭ": return Date("oneof", f"[..{hi}]", None, hi, unit="day", words=dt.words)
    return Date("oneof", f"[{lo}..{hi}]", lo, hi, unit="day", words=dt.words)


def _widen(d, iso, sign):
    if iso is None or not d.approx: return iso
    t = datetime.date.fromisoformat(iso)
    if d.unit == "year": t = t.replace(year=t.year + sign)
    elif d.unit == "month":
        mo = t.month + sign; y = t.year + (mo - 1) // 12; mo = (mo - 1) % 12 + 1
        t = t.replace(year=y, month=mo, day=min(t.day, _cal.monthrange(y, mo)[1]))
    else: t = t + datetime.timedelta(days=7 * sign)
    return t.isoformat()


def compatible(a, b):
    """Two dates may be the same event's: their ranges overlap, «about» widened by one unit. A date without bounds
    (none, general, an unresolved event) decides nothing: True."""
    if a.kind in ("none", "general", "event", "copies") or b.kind in ("none", "general", "event", "copies"): return True
    alo, ahi, blo, bhi = _widen(a, a.lo, -1), _widen(a, a.hi, 1), _widen(b, b.lo, -1), _widen(b, b.hi, 1)
    return (alo is None or bhi is None or alo <= bhi) and (blo is None or ahi is None or blo <= ahi)


def _test():
    cases = {
        "**1889**": ("point", "1889"), "1889-07": ("point", "1889-07"), "1889-07-03": ("point", "1889-07-03"),
        "ĉirkaŭ 1908": ("point", "1908~"), "verŝajne 1907": ("point", "1907?"), "verŝajne ĉirkaŭ 1908": ("point", "1908%"),
        "de 1881 ĝis 1882": ("span", "1881/1882"), "ekde 1905": ("span", "1905/.."), "ĝis 1900": ("span", "../1900"),
        "ĝis ĉirkaŭ 1900": ("span", "../1900~"), "inter 1882 kaj 1887": ("oneof", "[1882..1887]"),
        "antaŭ 1905": ("oneof", "[..1904]"), "post 1905-08": ("oneof", "[1905-09..]"), "post 1905-12-31": ("oneof", "[1906-01-01..]"),
        "dum aŭ antaŭ 1905": ("oneof", "[..1905]"), "dum aŭ post 1905-08": ("oneof", "[1905-08..]"),
        "dum aŭ post 1913-08-22☞": ("oneof", "[1913-08-22..]"), "dum aŭ post la kongreso de Berno": ("event", ""),
        "fine de 1893": ("oneof", "[1893-10..1893-12]"), "komence de 1906": ("oneof", "[1906-01..1906-03]"),
        "fine de 1889-07": ("oneof", "[1889-07-21..1889-07-31]"), "la 1920aj jaroj": ("oneof", "192X"),
        "1889-07-12 m.s.": ("point", "1889-07-24"), "1900-03-01 m.s.": ("point", "1900-03-14"),
        "post la kongreso de Bulonjo": ("event", ""), "[sen dato]": ("none", ""), "[ĝenerala]": ("general", ""),
        "2018+2019": ("copies", "{2018,2019}"),
    }
    bad = ["1879-1884", "1881–1882", "≥ 1905", "ĉ. 1900", "1905 (kalkulite: …)", "3 jul 1889", "1889-13", "1889-02-30",
           "de 1890 ĝis 1880", "fine 1893", "1889 m.s."]
    fails = 0
    for f, (k, e) in cases.items():
        d = parse(f)
        if (d.kind, d.edtf) != (k, e): print("FAIL", f, d.kind, d.edtf); fails += 1
    for f in bad:
        try: parse(f); print("FAIL (accepted)", f); fails += 1
        except ValueError: pass
    assert compatible(parse("ĉirkaŭ 1908"), parse("1909")) and not compatible(parse("1908"), parse("1909"))
    assert compatible(parse("inter 1882 kaj 1887"), parse("1885-03")) and not compatible(parse("antaŭ 1905"), parse("1906"))
    assert compatible(parse("verŝajne 1907"), parse("1907-05")) and not compatible(parse("verŝajne 1907"), parse("1908"))
    assert resolve(parse("post la kongreso"), "1905-08-05", "1905-08-12").edtf == "[1905-08-13..]"
    assert resolve(parse("dum aŭ post la kongreso"), "1905-08-05", "1905-08-12").edtf == "[1905-08-05..]"
    assert compatible(parse("dum aŭ antaŭ 1905"), parse("1905")) and not compatible(parse("antaŭ 1905"), parse("1905"))
    assert compatible(parse("dum aŭ post 1913-08"), parse("1913-08-24")) and not compatible(parse("post 1913-08"), parse("1913-08-24"))
    print(f"{len(cases)} accepted, {len(bad)} refused, 6 comparisons: {'all pass' if not fails else str(fails) + ' FAILED'}")
    return fails


if __name__ == "__main__":
    if "--test" in sys.argv: sys.exit(1 if _test() else 0)
    for a in sys.argv[1:]:
        try: print(a, "→", parse(a))
        except ValueError as e: print(a, "→", e)
