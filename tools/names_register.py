"""The names register's spellings, for the tools that file a NAME under another: profiles/NAMES-REGISTER.tsv rows of
relation «fact key», status «confirmed», whose main form is a NAME alone (no qualifier in brackets): the NAME as
written -> the NAME it is filed under (BEAUFRONT -> DE BEAUFRONT). The rows with a qualifier are the harvest's
FACT_KEYS. These rows were the harvest's ALIASES table until 2026-10-31 (the editor, 2026-10-30: to be eliminated before the next harvest); read by tools/harvest-facts.py (ALIASES, canon), tools/dowse-facts-assemble.py and
tools/name-ungarble.py. Ezri, 2026-10-31."""
import csv, os, re
REGISTER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "published", "heterophony-resources",
                        "geniza", "profiles", "NAMES-REGISTER.tsv")

def aliases():
    """{NAME as written (upper case): NAME filed under}; {} if the register is missing."""
    if not os.path.exists(REGISTER): return {}
    out = {}
    for r in csv.DictReader((l for l in open(REGISTER, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if r.get("relation") == "fact key" and (r.get("status") or "").startswith("confirmed") and not re.search(r"\(", r["main_form"] or ""):
            out[r["name"].strip().upper()] = r["main_form"].strip()
    return out
