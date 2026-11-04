"""The fields of a fact line, and the source's words kept out of every trigger (2026-10-28; the editor: a field never recognised by words that can occur
elsewhere; triggers recognised only inside a field, or else given unique delimiters such as double brackets, since
anchors will hold all-caps words; the audit: ocr/method/TRIGGER-WORDS-AUDIT-2026-10-28.md).

A fact line (facts format 4):
    - $$$ HEAD $$$ **DATE** · {KIND} · FACT · ANCHOR · LOCATOR · [THEMES] · VOICE
The ANCHOR is the source's own words, bare; FACT, KIND and VOICE may quote the source in «…», “…” or "…"; our notes
stand in ⟦…⟧. A tool that looks for a trigger reads the field the trigger belongs to, through unquoted() (the source's
quotations and our notes blanked) or noquotes() (the quotations only); it changes a field through sub_outside(), which
leaves quoted words as they are. Imported by the tools in tools/ (`import factline`). Ezri."""
import re

QUOTES = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"")
QUOTES_NOTES = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"|⟦[^⟧]*⟧")
HEAD = re.compile(r"^- \$\$\$ (.+?) \$\$\$(?: *\(([^)]*)\))?\s*(\*\*[^*]*\*\*)?\s*")

def unquoted(s):
    """The text with the source's quotations and our ⟦notes⟧ blanked: for a trigger of the line's own form."""
    return QUOTES_NOTES.sub(" ", s or "")

def noquotes(s):
    """The text with only the source's quotations blanked: for a trigger read inside one of our ⟦notes⟧."""
    return QUOTES.sub(" ", s or "")

def sub_outside(pattern, repl, s, flags=0, notes=True):
    """re.sub only in the text outside the source's quotations (and outside ⟦notes⟧ unless notes=False), the quoted
    words left as printed."""
    pat = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
    guard = QUOTES_NOTES if notes else QUOTES
    out, last = [], 0
    for m in guard.finditer(s or ""):
        out.append(pat.sub(repl, s[last:m.start()])); out.append(m.group(0)); last = m.end()
    out.append(pat.sub(repl, (s or "")[last:]))
    return "".join(out)

def ours(line):
    """A line's own words, for a tool that looks for one of ours anywhere in it: the kind, the fact and the voice, with
    the source's quotations blanked and our ⟦notes⟧ kept; the anchor (the source's words, bare) left out. A line not of
    the fact-line form: the whole line, quotations blanked."""
    f = fields(line)
    if f is None: return noquotes(line)
    return noquotes(" · ".join((f["kind"], f["fact"], f["themes"], f["voice"])))

def fields(line):
    """A format-4 line's fields by their place: head, qual, date, kind, fact, anchor, locator, themes, voice (str; ""
    where the line has no such field). A line not of the form gives None."""
    m = HEAD.match(line or "")
    if not m: return None
    rest = line[m.end():].lstrip("· ").rstrip("\n")
    ps = [p.strip() for p in rest.split(" · ")]
    f = {"head": m.group(1), "qual": m.group(2) or "", "date": (m.group(3) or "").strip("*")}
    if ps and ps[0].startswith("{"): f["kind"] = ps.pop(0)
    else: f["kind"] = ""
    for k in ("fact", "anchor", "locator"): f[k] = ps.pop(0) if ps else ""
    f["themes"] = ps.pop(0) if ps and ps[0].startswith("[") else ""
    f["voice"] = " · ".join(ps)
    return f
