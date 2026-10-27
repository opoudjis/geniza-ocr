#!/usr/bin/env python3
"""The names register's rows, each with the corpus lines that state it (the editor, 2026-10-17 12:5x, on Couturat's
«bone konata al ĉiuj» written «◊? De Beaufront, laŭ la registro, vico «Ido (signature)», ankoraŭ «proposed»»: uncontroversial,
the register should know that Couturat said that De Beaufront did it, so ∴; to Ezri's
proposal, approved, with testing, the register's build-up
being slow and the smelt not to be held hostage to it).

    tools/register-evidence.py [--date D]

For each row of profiles/NAMES-REGISTER.tsv, the dowse lines (profiles/by-source/*-dowse.md) that state it:
- **a name line:** a line headed by the row's person (its main form or «same as») whose kind is «nomo» with the row's
  name in the object (`{nomo: Ido, subskribo de la reformprojekto}` under DE BEAUFRONT);
- **at a cited place:** a line at one of the places the row's source names (item and PDF page) that holds the row's
  name and is headed by, or names, its person;
- **a work by its own source** (relation «short title», the owner in brackets in «same as»: «Grand Dictionnaire
  Français-Esperanto (De Beaufront)»): a line of a source the row cites (any page) that holds the full title and is
  headed by, or names, the owner (Korĵenkov's «Grand Dictionnaire Français-Esperanto de L. de Beaufront», PDF 31, for
  his «la grandan vortaron de De Beaufront», PDF 35) (the editor, 17:5x, against a register of works; to the two changes, approved).
The row's name matches with the Esperanto endings -j, -n, -jn on its words in -o, -a, -e («la grandan vortaron» for
«la granda vortaro»).
A row with one or more such lines is **attested by the corpus**: the biography writer gives it «∴», not «◊?», whatever
its signed status; a row with none stays as signed. The register itself is not changed (its status is the editor's ruling):
writes profiles/NAMES-REGISTER-EVIDENCE.tsv (this tool's own, remade each run: name, same_as, lines) and
ocr/method/NAMES-REGISTER-EVIDENCE-<D>.md, every attested row with its lines in full, to read only if wanted.
The S4 brief names the TSV (smelt-s2-prep.py --biography). Ezri, 2026-10-17."""
import argparse, csv, datetime, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def bare(s): return re.sub(r"\s*\([^)]*\)", "", s or "").strip()

def inflected(name):
    """The name as a pattern whose words in -o, -a, -e may take -j, -n, -jn (not «la», not short words)."""
    return r"\s+".join(re.escape(w) + ("(?:j?n?)" if re.fullmatch(r"\w{3,}[oae]", w) else "") for w in name.split())

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    reg = [r for r in csv.DictReader((l for l in open(os.path.join(G, "profiles", "NAMES-REGISTER.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t")]
    lines = []
    for f in sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md"))):
        for l in open(f, encoding="utf-8"):
            if l.startswith("- $$$"): lines.append((os.path.basename(f), l.rstrip("\n")))
    out, attested = [], []
    for r in reg:
        persons = {bare(r["same_as"]).upper(), bare(r["main_form"]).upper()} - {""}
        places = []   # «item, PDF 46 (prese 45), PDF 47 …», «item, ¶ 46»: each page or paragraph with the last item named
        item = None
        for m in re.finditer(r"([a-z0-9][a-z0-9-]+-\d{4}[a-z0-9-]*)|(PDF|¶) ?(\d+)", r["source"] or ""):
            if m.group(1): item = m.group(1)
            elif item: places.append((item, m.group(2), m.group(3)))
        # the row's forms: a «;» list, each up to a comma or bracket (a descriptive name, «Courtry (Seine-et-Marne), in
        # the declaration of 1876»); a form under three letters («Z.») only at the row's own places (2026-10-18, T17)
        forms = [re.split(r",|\s\(", bare(x))[0].strip() for x in (r["name"] or "").split(";")]
        forms = [x for x in forms if len(x) >= 3 or (places and len(x) >= 2)]
        if not forms: continue
        # a row the editor kept tentative is not raised to ∴ by its lines (the Courtry row: «rescind Courtry =
        # Sivry-Courtry … they remain tentative»; attested once the place match read «¶», 2026-10-18)
        if "tentative" in (r.get("note") or ""): continue
        name = forms[0]
        nm = re.compile(r"(?<![\w-])(?:" + "|".join(inflected(x) for x in forms) + r")(?![\w-])")
        short = all(len(x) < 3 for x in forms)
        work = r["relation"].strip() == "short title" and re.search(r"\(([^)]+)\)\s*$", r["same_as"] or "")
        owner, title = (work.group(1).upper(), bare(r["main_form"])) if work else (None, None)
        hits = []
        for fn, l in lines:
            head = re.match(r"^- \$\$\$ (.+?) \$\$\$", l).group(1).upper()
            kind = (re.search(r"\*\* · \{([^}]*)\}", l) or [None, ""])[1]
            kh, _, obj = kind.partition(":")
            if head in persons and kh.strip() == "nomo" and nm.search(obj) and not short:
                hits.append((fn, l)); continue
            if any(re.search(rf"{re.escape(it)}, {w} {p}(?!\d)", l) for it, w, p in places) and nm.search(l) \
               and (head in persons or any(p in l.upper() for p in persons)):
                hits.append((fn, l)); continue
            if owner and title and title in l and any(f"{it}, {w} " in l for it, w, _ in places) \
               and (head == owner or owner in l.upper()):
                hits.append((fn, l))
        if hits:
            attested.append((r, hits))
            out.append("\t".join([r["name"], r["same_as"], " | ".join(f"{fn}: {l.split(' · ')[-3] if l.count(' · ') >= 3 else ''}" for fn, l in hits)]))
    tp = os.path.join(G, "profiles", "NAMES-REGISTER-EVIDENCE.tsv")
    open(tp, "w", encoding="utf-8").write("name\tsame_as\tthe corpus lines that state it (dowse file: place)\n" + "\n".join(out) + "\n")
    doc = [f"# The names register: rows the corpus attests ({a.date})", "",
           f"`[tools/register-evidence.py: {len(attested)} of {len(reg)} rows have a dowse line that states them. The biography writer gives these «∴», not «◊?», whatever their signed status; the register's status column is not changed. Every line in full below. Nothing here asks for a decision.]`", ""]
    for r, hits in attested:
        doc += [f"## {r['name']} = {r['same_as']} (signed: {r['status']})", ""]
        doc += [f"- `` {l[2:]} ``  ⟵ `{fn}`" for fn, l in hits] + [""]
    dp = os.path.join(G, "ocr", "method", f"NAMES-REGISTER-EVIDENCE-{a.date}.md")
    open(dp, "w", encoding="utf-8").write("\n".join(doc) + "\n")
    print(f"{len(attested)} of {len(reg)} register rows attested by the corpus → {os.path.relpath(tp, ROOT)}, {os.path.relpath(dp, ROOT)}")
    for r, hits in attested: print(f"  {r['name']} = {r['same_as']} ({r['status']}): {len(hits)} lines")

if __name__ == "__main__":
    main()
