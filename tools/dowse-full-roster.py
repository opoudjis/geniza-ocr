#!/usr/bin/env python3
"""dowse-full-roster.py: the venture's full person roster, as a dowse roster file (geniza/dowse/ROSTER-*.txt format:
one person per line, forms separated by « | »). The names are exactly those of tools/cross-arc-person-index.py, whose
loader it reuses: every geniza/profiles/*.md (the curated persons) plus tools/cross-arc-roster-extra.txt (Interglossa-side
figures and entities). Each line gives the label as the index prints it and the search key, where they differ.

Why: a whole-source dowse (one book against everyone the venture tracks) needs the full cast, and the dowse runbook
(geniza/ocr/method/DOWSE-RUNBOOK-2026-10-06.md, D1) had no ready roster to point to (editor, 2026-10-07). Limits: one alphabet, the forms the profiles are filed under; a run
on a Russian or Cyrillic source needs the national and Cyrillic forms added (runbook D1), and the record will mark items
underspecified. Short names and ordinary words flood (runbook D1, last paragraph).

Usage: python3 tools/dowse-full-roster.py OUT.txt   (refuses to overwrite)   (Ezri, 2026-10-07)"""
import datetime, importlib.util, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cai", HERE / "cross-arc-person-index.py")
cai = importlib.util.module_from_spec(spec)
argv = sys.argv; sys.argv = argv[:1]; spec.loader.exec_module(cai); sys.argv = argv
out = Path(sys.argv[1])
if out.exists():
    sys.exit(f"refusing to overwrite {out}")
roster = cai.load_roster()
# one line per PERSON: every profile file, not one per search key (the index's loader merges people who share a key:
# zamenhof-lidja took Ludwik Zamenhof's «zamenhof»); a file with no stem (profiles/.md) is skipped
people = []
# a profile the harvest marks out by the scope register (all its lines of a person the register has out; the editor
# 2026-10-15: approved to «mark rather than drop») is not searched for: tools/harvest-facts.py OUT_BANNER
OUT_BANNER = "Ekster la amplekso laŭ la registro de amplekso"
skipped_out = []
for f in sorted(cai.PROFILES.glob("*.md")):
    if not f.stem or f.stem.startswith("."):
        continue
    if OUT_BANNER in f.read_text(encoding="utf-8")[:2000]:
        skipped_out.append(f.stem); continue
    key = cai.key_from_basename(f.stem)
    people.append((f.stem, key, "profile"))
for key, v in roster.items():
    if v["origin"] == "extra":
        people.append((v["label"].strip(), key, "extra"))
lines = [f"# ROSTER-FULL: the venture's full person roster, {len(people)} names, generated "
         f"{datetime.datetime.now():%Y-%m-%d %H:%M} by tools/dowse-full-roster.py",
         "# one line per geniza/profiles/*.md file (origin «profile», label = the file's stem) and per entry of",
         "# tools/cross-arc-roster-extra.txt (origin «extra»). One alphabet only: add national and Cyrillic forms for a",
         "# Russian source (runbook D1). Label first, then the search key where it differs."]
# The names register's confirmed short forms of bodies (the editor 2026-10-13
#): a short form the name search never looks for can never be kept by dowse-context.py («L. K.»).
# Forms with an inner space are left to the entry's key («la Ondo» is found by «ondo»).
import re as _re
SHORT = {}
_reg = HERE.parent / "published" / "heterophony-resources" / "geniza" / "profiles" / "NAMES-REGISTER.tsv"
if _reg.exists():
    for _l in _reg.read_text(encoding="utf-8").splitlines():
        _f = _l.split("\t")
        if len(_f) >= 9 and _f[3].startswith("short form") and _f[7] == "confirmed":
            _slug = _re.sub(r"[^\w]+", "-", _f[2].split(" (")[0].lower()).strip("-")
            _forms = [_f[0].split(" (")[0].strip()] + _re.findall(r"«([^«»]+)»", _f[0])
            _forms += [x.strip() for x in _re.findall(r"also ([^)]*)", _f[0])[0].split(",")] if "also " in _f[0] else []
            SHORT.setdefault(_slug, [])
            SHORT[_slug] += [x for x in _forms if x and " " not in x.strip() and x not in SHORT[_slug]]
n = {"profile": 0, "extra": 0}
# A PERSON KNOWN BY A NUMBER (2026-10-23: The Esperantist's «Esp. 10549», «O.W. 7074», a writer under his number in the
# Adresaro): the search key has no letter, which the name search cannot take (ocr-name-search.py name_targets: «max()
# iterable argument is empty»), and the label's letters («esp», «ow») would match every abbreviation; not searched for,
# listed. A number is found by reading, not by the name search
numbered = []
# FRAGMENTS (2026-10-24; La Ondo de Esperanto's strong search: 25.3 million hits, 3.8 GB, against Bohema Esperantisto's
# 456,653; the 584 names of 10,000 hits or more, 17.5 million of them, were profiles like «o-w», «a-z», «d-ro-n | ro»,
# «ko-fo», whose longest part, the part the name search compares, has one or two letters, and which the cross-alphabet
# rule matched against nearly every short Russian word; the editor): a person every one of whose forms has no
# part longer than two letters is not searched for, listed. Such a part names no one a legilo could be told of
fragments = []
for label, key, origin in sorted(people, key=lambda p: p[0].lower()):
    if not _re.search(r"[^\W\d_]", key):
        numbered.append(label); continue
    forms = [label] + ([key] if cai.fold(key) != cai.fold(label) else [])
    forms += [x for x in SHORT.get(label, []) if cai.fold(x) not in {cai.fold(y) for y in forms}]
    if all(max((len(p) for p in _re.findall(r"[^\W\d_]+", x)), default=0) <= 2 for x in forms):
        fragments.append(label); continue
    lines.append(" | ".join(forms))
    n[origin] += 1
lines[0] = lines[0].replace(f" {len(people)} names,", f" {n['profile'] + n['extra']} names,")   # the numbered and fragments left out
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {out}: {n['profile'] + n['extra']} names ({n['profile']} from profiles, {n['extra']} extra); "
      f"{len(numbered)} known by a number only, not searched for: {', '.join(numbered)}; "
      f"{len(fragments)} fragments (no part over two letters), not searched for: {', '.join(fragments[:30])}{' …' if len(fragments) > 30 else ''}; "
      f"{len(skipped_out)} profiles left out, marked out by the scope register: {', '.join(skipped_out[:20])}{' …' if len(skipped_out) > 20 else ''}")
