"""One reader for a fact line's fields, for the smelt tools (2026-10-16; the editor, to: the brief's source list, the witness display and the period
check had each parsed the locator with its own pattern, and the brief's had dropped Neves, whose item name holds spaces).

The locator is read by the harvest's own tested pattern (`harvest-facts.py`, LOC2 and locators()), imported here, never
copied. Imported, not run on its own.

    from line_fields import fields
    f = fields(line)   # {"item", "place", "pdf", "para", "file", "author", "contributor", "date", "kind", "derived"}
"""
import importlib.util, os, re, sys
_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("harvest_facts", os.path.join(_here, "harvest-facts.py"))
_hf = importlib.util.module_from_spec(_spec)
_saved, sys.argv = sys.argv, ["x"]
try:
    _spec.loader.exec_module(_hf)
finally:
    sys.argv = _saved

DATE = re.compile(r"\$\$\$(?: *\([^)]*\))? \*\*(.+?)\*\* ·")
KIND = re.compile(r"\*\* · \{([^}]*)\}")
FILE = re.compile(r"⟵ `([^`]+)`")
CONTRIB = re.compile(r"\(kontribuo de ([^)]+)\)")      # the bracket after the page, until 2026-10-17
CONTRIB_LABEL = re.compile(r"⟦kontribuo: ([^⟧]+)⟧")    # among the labels, from 2026-10-17 (the editor)
# … the bracket closes before the line's end, or before the labels the harvest adds after it (⟦kontribuo: …⟧,
# ⟦malamika atestanto …⟧), 2026-10-17
DERIVED = re.compile(r"derivita(?:, fonto nevidita)? ↤ (.+?)(?:;|\)\s*(?:⟦[^⟧]*⟧\s*)*(?:⟵|$))")

def fields(line):
    """A profile or facts-file line -> its fields; a field the line lacks is None."""
    out = {"item": None, "place": None, "pdf": None, "para": None, "file": None, "author": None,
           "contributor": None, "date": None, "kind": None, "derived": None}
    m = DATE.search("- " + line.lstrip("- ")); out["date"] = m.group(1) if m else None
    m = KIND.search(line); out["kind"] = m.group(1).split(":")[0].strip() if m else None
    m = FILE.search(line); out["file"] = m.group(1) if m else None
    m = CONTRIB_LABEL.search(line) or CONTRIB.search(line); out["contributor"] = m.group(1).strip() if m else None
    m = DERIVED.search(line); out["derived"] = m.group(1).strip() if m else None
    for part in line.split(" · "):
        # a collective volume's locator ends «(prese 386) (kontribuo de X)», which the harvest's pattern does not take
        # after the page: the contributor is read above and set aside here
        ms = _hf.locators(CONTRIB.sub("", part).strip())
        if ms:
            g = ms[0]
            out["item"], out["pdf"], out["para"] = g.group("item").strip(), g.group("pdf"), g.group("para")
            out["place"] = f"PDF {g.group('pdf')}" if g.group("pdf") else f"¶ {g.group('para')}"
            break
    # the author: the contributor of a collective volume; else the dowse file's first word; else the item's first word
    if out["contributor"]:
        out["author"] = out["contributor"].split()[-1].lower()
    elif out["file"] and out["file"].endswith("-dowse.md"):
        out["author"] = re.match(r"[a-z]+", out["file"]).group(0) if re.match(r"[a-z]+", out["file"]) else out["file"]
    elif out["item"]:
        ws = [w for w in re.split(r"[-_ ]", out["item"].lower()) if w.isalpha() and w not in ("komenti", "komentoj", "da", "de")]
        out["author"] = ws[0] if ws else out["item"].lower()
    return out
