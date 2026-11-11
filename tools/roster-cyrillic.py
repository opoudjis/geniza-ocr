#!/usr/bin/env python3
"""roster-cyrillic.py — a roster for a source in Russian: the full roster with each person's Cyrillic forms added (2026-11-09;
Miles, on Espero of St Petersburg, 430 of its 478 pages in Russian; the editor). The full roster holds one alphabet
(its header asks for national and Cyrillic forms for a Russian source, runbook D1), so a Russian page is found only through the
transliteration tier, which the strong search drops (ocr-dowse.py --translit-strict keeps a strict part of it: names of 5+
letters, spelled by the transcription table). A Cyrillic form on the roster line is searched in the ordinary Cyrillic tiers:
exact, near (a misread letter), the Russian case endings; it reaches the short names (Бейн, Кабе) and the names Russian spells
by sound (Бофронъ, Кутюра).

    python3 tools/roster-cyrillic.py ROSTER --write OUT [--forms FORMS.tsv]

Two inputs: (1) profiles/NAMES-REGISTER.tsv, every row whose «name» holds Cyrillic and whose «main_form» is a person's head
in capitals and a roster label (the head's slug; a work's title is left out, Lermontov's «Ангел» having gone to «angelo»): the surname, the last Cyrillic word of each form («фон-» dropped), the row's «;»-separated forms each;
(2) FORMS.tsv (default dowse/ROSTER-CYRILLIC-FORMS.tsv), «label TAB Cyrillic form TAB where attested»: the forms the
register does not hold, each with its attestation in the corpus (file and line), never typed from memory. The forms are
added to the label's line as « | form», after its own; a form already there is not added twice. Writes OUT, create-only,
with a header naming both inputs; prints each label given forms, and each input row whose label is not on the roster.
Ezri, 2026-11-09."""
import argparse, csv, os, re, sys, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
CYR = re.compile("[А-Яа-яЁёѢѣІіѲѳѴѵ]")

def slug(h):
    h = re.sub(r"\s*\(.*\)\s*$", "", h).strip()
    h = "".join(c for c in unicodedata.normalize("NFD", h) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")

def surname(form):
    words = [w for w in re.split(r"\s+", form.strip()) if CYR.search(w)]
    if not words: return None
    w = re.sub(r"^фон-", "", words[-1], flags=re.I).strip(",.;")
    return w if len(w) >= 3 else None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("roster"); ap.add_argument("--write", required=True)
    ap.add_argument("--forms", default=os.path.join(G, "dowse", "ROSTER-CYRILLIC-FORMS.tsv"))
    a = ap.parse_args()
    if os.path.exists(a.write): sys.exit(f"refusing: {a.write} exists")
    lines = open(a.roster, encoding="utf-8").read().split("\n")
    at = {}
    for i, l in enumerate(lines):
        if l.strip() and not l.startswith("#"):
            at.setdefault(l.split(" || ")[0].split(" | ")[0].strip(), i)
    add, missing = {}, []
    reg = [l for l in open(os.path.join(G, "profiles", "NAMES-REGISTER.tsv"), encoding="utf-8") if not l.startswith("#")]
    for r in csv.DictReader(reg, delimiter="\t"):
        if not CYR.search(r["name"]) or not r.get("main_form"): continue
        head = r["main_form"].split(" (")[0].strip()
        if head != head.upper(): continue      # a person's head is in capitals; a work's title is not («Anĝelo», Lermontov's «Ангел»)
        lab = slug(r["main_form"])
        forms = [s for s in (surname(f) for f in r["name"].split(";")) if s]
        if not forms: continue
        if lab not in at: missing.append(f"register: {r['name']} → {r['main_form']} ({lab})"); continue
        add.setdefault(lab, []).extend(forms)
    if os.path.exists(a.forms):
        for l in open(a.forms, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if not l.strip() or l.startswith("#") or x[0] == "label": continue
            if len(x) < 3 or not x[2].strip(): sys.exit(f"{os.path.basename(a.forms)}: a form without its attestation: {l.strip()}")
            if x[0] not in at: missing.append(f"forms: {x[0]} {x[1]}"); continue
            add.setdefault(x[0], []).append(x[1].strip())
    for lab, forms in sorted(add.items()):
        l = lines[at[lab]]; head, sep, tail = l.partition(" || ")
        have = {f.strip().lower() for f in head.split(" | ")}
        new = []
        for f in forms:
            if f.lower() not in have: have.add(f.lower()); new.append(f)
        if new:
            lines[at[lab]] = head + "".join(f" | {f}" for f in new) + (sep + tail if sep else "")
            print(f"{lab}: {', '.join(new)}")
    hdr = (f"# ROSTER FOR A SOURCE IN RUSSIAN, by tools/roster-cyrillic.py from {os.path.basename(a.roster)}: the Cyrillic forms of "
           f"{len(add)} people added, from profiles/NAMES-REGISTER.tsv and {os.path.relpath(a.forms, G)}")
    with open(a.write, "x", encoding="utf-8") as fh: fh.write(hdr + "\n" + "\n".join(lines))
    print(f"wrote {a.write}: {len(add)} people given Cyrillic forms")
    for m in missing: print("  not on the roster:", m)

if __name__ == "__main__":
    main()
