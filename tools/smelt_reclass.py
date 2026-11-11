#!/usr/bin/env python3
r"""smelt_reclass.py — the kind of a copy made by naming, from the named person's side (the editor, 2026-10-30, on
Ekland's «verko: nekrologo de MIDTHUS» copied to Midthus as if his own work).

The harvest copies a line to every person its kind names in capitals, the kind unchanged (harvest-facts.py, «every
person the kind names», 2026-10-16), and since 2026-10-30 adds «far: <the person copied from>». The kind is still the
doer's: under Midthus, Ekland's obituary is a «verko». A reader gives each such copy its kind from the named person's
side, from the list in force (ocr/method/EVENT-KINDS-PROPOSAL-2026-10-13.md): the obituary is his «juĝo», a letter to
him «renkonto», an attack on him «konflikto», a dedication «honoro». Its answers go to profiles/build/KIND-RECLASS.tsv,
which the harvest reads: the next harvest writes those copies with the new kind, «far:» kept.

    tools/smelt_reclass.py brief <stem> <tag>   smelt/<stem>/RECLASS-BRIEF-<tag>.md (in pieces where long) and
                                               RECLASS-LIST-<tag>.tsv (create-only): the profile's copies made by
                                               naming, not yet in KIND-RECLASS.tsv; prints the reader's launch line
    tools/smelt_reclass.py apply <stem> <tag>  RECLASS-RETURN-<tag>.md checked (each kind on the list, an object) and
                                               its rows added to profiles/build/KIND-RECLASS.tsv; prints the refused

A copy made by naming: the kind has «far:», or (profiles harvested before 2026-10-30) the line is «⟦kopio el X⟧», its
kind not one the harvest turns round (renkonto, konflikto, interkonsento), its «kun:» not naming X. Ezri, 2026-10-30."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factline as FL
import smelt_inputs as SI
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
TABLE = os.path.join(G, "profiles", "build", "KIND-RECLASS.tsv")
KINDS_DOC = os.path.join(G, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md")
TURNED = {"renkonto", "konflikto", "interkonsento"}
COLS = "person\tfile\tlocator\told_kind\tnew_kind\tfrom\n"
RET = re.compile(r"^\s*[-*]?\s*(\d+)\s*·\s*(.+?)\s*·\s*(.*?)\s*$", re.M)

def kinds_table():
    t = open(KINDS_DOC, encoding="utf-8").read()
    i = t.find("## The list in force"); j = t.find("\n## ", i + 5)
    rows = [l for l in t[i:j].splitlines() if l.startswith("|")]
    return rows, set(re.findall(r"^\| \*\*([^*]+)\*\* \|", "\n".join(rows), re.M))

def base_kind(kind):
    """The kind without its «far:» field, as the harvest writes it before adding one: the table's key."""
    return ";".join(p for p in kind.strip("{}").split(";") if not p.strip().startswith("far:")).strip()

def table():
    if not os.path.exists(TABLE): return {}
    out = {}
    for l in open(TABLE, encoding="utf-8").read().splitlines()[1:]:
        r = l.split("\t")
        # keyed by the old kind and by the new: a profile harvested after the table has the new one
        if len(r) >= 5: out[(SI.fold(r[0]), r[1], r[2], r[3])] = out[(SI.fold(r[0]), r[1], r[2], r[4])] = r[4]
    return out

def copies(prof):
    """[(n, person, file, locator, kind, fact, anchor, from)] the profile's copies made by naming."""
    out = []
    for n, l in enumerate(prof, 1):
        if not l.startswith("- $$$"): continue
        f = FL.fields(l)
        if not f or not f["kind"]: continue
        parts = [p.strip() for p in f["kind"].strip("{}").split(";")]
        far = next((p[4:].strip() for p in parts if p.startswith("far:")), None)
        src = re.search(r"⟦kopio el ([^⟧]+?)⟧", l)
        if not far:
            if not src: continue
            x = re.sub(r"\s*\(.*$", "", src.group(1)).strip()
            kun = next((p[4:].strip() for p in parts if p.startswith("kun:")), "")
            heads = {p.lstrip("+").split(":")[0].strip() for p in parts if not p.startswith(("kun:", "sugestas:"))}
            if heads & TURNED or SI.fold(x) in SI.fold(kun): continue
            far = src.group(1)
        fm = re.search(r"⟵ `([^`]+)`", l)
        out.append((n, f["head"], fm.group(1) if fm else "", f["locator"], base_kind(f["kind"]), f["fact"], f["anchor"], far))
    return out

BRIEF = """# La specoj de la kopioj ĉe {name}, de ties flanko ({tag})

`[Ezri, per tools/smelt_reclass.py brief {stem} {tag}: {n} kopioj el PROFILE-FROZEN-{tag}.md, kiujn la ilo faris, ĉar la speca kampo de alies linio nomas {name}.]`

## La briefo

La ilo de La Genizo kopias linion al ĉiu persono, kiun ĝia speca kampo nomas per majuskloj, kun la speco senŝanĝa. Tiel la linio de EKLAND `{{verko: nekrologo de MIDTHUS}}` (Ekland verkis nekrologon) staras ankaŭ ĉe Midthus, kie «verko» legiĝas, kvazaŭ Midthus ĝin verkus. Sube staras tiaj kopioj ĉe {name}: ĉe ĉiu, la speco de la origina linio, «far: X» (kies ago ĝi estas), la fakto kaj la ankro (la vortoj de la fonto).

Via tasko: doni al ĉiu kopio la specon **de la flanko de {name}**, el la listo sube, kun objekto: kio la fakto estas por {name}. Ekzemple: nekrologo pri li `juĝo: nekrologo, Lingvo Internacia`; letero al li aŭ respondo al li `renkonto: EKLAND, letero`; artikolo kontraŭ li `konflikto: EKLAND, artikolo kontraŭ li`; dediĉo al li `honoro: dediĉo de la traduko`; lia portreto presita `aperoj: portreto` aŭ `atestaĵo: portreto`; citaĵo de lia verko `influo: …`. Kie la origina speco jam estas ĝusta de lia flanko (ekz. ankaŭ li kunverkis), skribu `=`.

Vi ne ŝanĝas faktojn, ankrojn nek nomojn. La ilo aldonas «far: X» mem; tial en la objekto neniam «de X» por la aŭtoro aŭ la aganto (`juĝo: nekrologo, La Belga Sonorilo`, ne `juĝo: nekrologo de Verbanck`): «de» povas legiĝi ankaŭ kiel «pri» (la redaktoro, 2026-10-30).

## La listo de specoj

{kinds}

## La raporto

Skribu la novan dosieron `{ret}`, kun unu linio por ĉiu kopio, laŭ ĝia numero:

`- 12 · juĝo: nekrologo, Lingvo Internacia · kial, per kelkaj vortoj`

aŭ `- 12 · = · kial`. Ĉiu numero unufoje. La objekto kiel en la listo (sen dato).

Via fina mesaĝo estas unu linio: `<N> kopioj, <M> «=»`.

## La kopioj

{items}
"""

def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("brief", "apply"): sys.exit(__doc__)
    cmd, stem, tag = sys.argv[1:]
    d = os.path.join(G, "smelt", stem)
    bp, lp, rp = (os.path.join(d, f"RECLASS-{x}-{tag}.{e}") for x, e in (("BRIEF", "md"), ("LIST", "tsv"), ("RETURN", "md")))
    rows, kinds = kinds_table()
    if cmd == "brief":
        prof = open(os.path.join(d, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
        done = table()
        cs = [c for c in copies(prof) if (SI.fold(c[1]), c[2], c[3], c[4]) not in done]
        if not cs: print(f"{stem}: no copies by naming left to reclassify"); return
        for p in (bp, lp):
            if os.path.exists(p): sys.exit(f"{os.path.relpath(p, G)} exists: not overwritten")
        name = cs[0][1]
        open(lp, "x", encoding="utf-8").write("n\tL\tperson\tfile\tlocator\tkind\tfrom\n"
                                              + "".join(f"{i}\t{c[0]}\t{c[1]}\t{c[2]}\t{c[3]}\t{c[4]}\t{c[7]}\n" for i, c in enumerate(cs, 1)))
        items = "\n".join(f"{i}. `{{{c[4]}}}` · far: {c[7]} · {c[5]} · «{c[6]}»" for i, c in enumerate(cs, 1))
        open(bp, "x", encoding="utf-8").write(BRIEF.format(name=name, tag=tag, stem=stem, n=len(cs), ret=rp, kinds="\n".join(rows), items=items))
        parts = SI.for_reader(bp)
        print(f"wrote {os.path.relpath(bp, G)} ({os.path.getsize(bp):,} bytes, {len(parts)} piece{'s' if len(parts) > 1 else ''}) "
              f"and {os.path.basename(lp)}: {len(cs)} copies by naming")
        print(f"launch (file-reader-writer): Read the brief {parts[0]} and carry out the task it gives, section «La briefo». "
              f"Your final message is the line the brief asks for.")
        return
    L = {int(r[0]): r for r in (l.split("\t") for l in open(lp, encoding="utf-8").read().splitlines()[1:])}
    new, bad, same, stripped = [], [], 0, []
    for m in RET.finditer(open(rp, encoding="utf-8").read()):
        n, k = int(m.group(1)), m.group(2).strip().strip("`{}")
        if n not in L: bad.append(f"{n}: not in the list"); continue
        r = L[n]
        if k == "=": same += 1; k = r[5]
        else:
            head, _, obj = k.partition(";")[0].partition(":")
            if head.strip() not in kinds: bad.append(f"{n}: kind not on the list «{head.strip()}»"); continue
            if not obj.strip() and head.strip() not in ("naskiĝo", "morto"): bad.append(f"{n}: no object for «{head.strip()}»"); continue
            # «de <the doer>» in the object is the brief's to forbid, not the tool's to strip: a tool cannot tell «nekrologo
            # de Verbanck» (by him) from «historio de Zamenhof» (of him) when Zamenhof is also the doer copied from
            # (Midthus's test, 2026-10-30); shown, so the editor sees it
            if re.search(r"\bde\s+[\w.'’ -]*" + re.escape(re.sub(r"\s*\(.*$", "", r[6]).strip()[:4]), k, re.I): stripped.append(f"{n}: «{k}»")
        new.append(f"{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\t{k}\t{os.path.relpath(rp, G)}\n")
    if not os.path.exists(TABLE): open(TABLE, "x", encoding="utf-8").write(COLS)
    have = open(TABLE, encoding="utf-8").read()
    add = [x for x in new if x.split("\t")[:4] and "\t".join(x.split("\t")[:4]) not in have]
    with open(TABLE, "a", encoding="utf-8") as fh: fh.writelines(add)
    print(f"{os.path.relpath(rp, G)}: {len(new)} kinds ({same} «=»), {len(add)} rows added to {os.path.relpath(TABLE, G)}; {len(bad)} refused")
    for b in bad: print(f"  refused: {b}")
    for s in stripped: print(f"  «de» before the doer's name, to read: {s}")
    print(f"  of {len(L)} copies listed, {len(L) - len(new) - len(bad)} not answered")

if __name__ == "__main__":
    main()
