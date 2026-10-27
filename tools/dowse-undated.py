#!/usr/bin/env python3
"""The undated lines of a dowsed source, read once and ruled as DECISIONS (dowse runbook D6c step 10c; the editor,
2026-10-15). The first pass, by hand on the
six redowsed sources, is profiles/build/UNDATED-YEARS-*-2026-10-15.

    tools/harvest-facts.py --check --undated profiles/build/UNDATED-<tag>.tsv
    tools/dowse-undated.py prep <source> <tag> [--list FILE] [--page]
    (one Read-only reader on dowse/<source>/undated-brief-<tag>.md; its return filed as dowse/<source>/undated-return-<tag>.md)
    tools/dowse-undated.py rekey <source> [--write]      (UNDATED-KEPT's stale keys, 2026-10-26: rekey())
    tools/dowse-undated.py owed --list profiles/build/UNDATED-<tag>.tsv [--out FILE]   (the page looks still owed: owed())
    tools/dowse-undated.py apply <source> <tag> [--skip N,N] [--keep N,N --why TEXT] [--set N=VALUE] [--input FILE --return FILE] [--write]

prep: the harvest's list (four classes of «[sen dato]» line: the fact names a year, describes a date, states a state,
or its labels cite a dated document), the source's own lines only, less those already ruled to stay undated or sent to
the page (dowse/<source>/UNDATED-KEPT.tsv, keyed on locator and anchor, so a redowse does not ask again). Writes
dowse/<source>/undated-input-<tag>.tsv and undated-brief-<tag>.md (from
ocr/method/DOWSE-TEMPLATE-UNDATED-BRIEF-EO-2026-10-15.md), create-only, and prints the reader's prompt.

apply: reads the return. Each DATO item becomes a date row of dowse/<source>/DECISIONS.tsv, keyed on the line's full
locator and the reader's anchor phrase; the value must parse in the date vocabulary. A date row dates every line at its
locator that holds its phrase, so the phrase must find this line alone in the facts file: where the anchor is shared
(the Höveler row of 2026-10-15 took four lines), the row is keyed on the first words of the fact instead, and an item
no phrase singles out is listed for a hand ruling. RESTU and PAĜO items go to UNDATED-KEPT.tsv; PAĜO items also to
undated-page-<tag>.md, for a look at the page. --skip drops items, --set N=VALUE replaces a reader's date (Ezri's check
of the DATO items, before --write). Without --write it prints only. Prints the number of lines the reassembly should
change, to check against git diff --numstat. Ezri, 2026-10-15."""
import argparse, csv, glob, importlib.util, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
TEMPLATE = os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-UNDATED-BRIEF-EO-2026-10-15.md")
PAGE_TEMPLATE = os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-UNDATED-PAGE-BRIEF-EO-2026-10-15.md")
DEC_HEAD = ("# DECISIONS: the editor's line rulings, keyed on the locator and a phrase of the SOURCE's own text (anchor or "
            "fact), applied by tools/dowse-facts-assemble.py after the settings, so they survive a redowse (the editor "
            "2026-10-12: decisions logged so that they can be reapplied; approved). A qualifier row's value "
            "is «NAME (qualifier)» and touches only that person's lines. A row that finds no line is reported.\n"
            "locator\tphrase\tkind\tvalue\truling\tnote\n")
KEPT_HEAD = ("# UNDATED-KEPT: lines of this source that the undated pass (dowse runbook D6c step 10c) ruled to stay «[sen dato]» "
             "(RESTU) or sent to the page (PAĜO), keyed on locator and anchor; tools/dowse-undated.py prep leaves them out.\n"
             "locator\tanchor\tclass\tverdict\treason\ttag\n")
THEME = re.compile(r"^(?:\[[A-Z?]+\])+$")

spec = importlib.util.spec_from_file_location("date_vocab", os.path.join(ROOT, "tools", "date_vocab.py"))
date_vocab = importlib.util.module_from_spec(spec); spec.loader.exec_module(date_vocab)

def file_names(loc):
    """A locator's items under their file names, the form DECISIONS rows match before the assembler writes keys
    (OCR-ITEM-TABLE.tsv, column «key»; 2026-10-17: Neves's row keyed «neves-parnaso-ido-2018, PDF 43» matched no line)."""
    k2n = {}
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if (r.get("key") or "").strip() and r["key"].strip() != r["item"]: k2n[r["key"].strip()] = r["item"]
    return "; ".join(k2n.get(p.split(",")[0].strip(), p.split(",")[0].strip()) + p[len(p.split(",")[0]):] for p in loc.split("; "))

def fields(line):
    """-> (fact, anchor, locator) of a facts line, found from the theme field «[V][BIO]» back, or None."""
    f = line.split(" · ")
    i = next((k for k, x in enumerate(f) if THEME.match(x.strip())), None)
    return (f[i - 3].strip(), f[i - 2].strip(), f[i - 1].strip()) if i and i >= 3 else None

def kept(D):
    """-> {(locator, anchor): the last verdict} of UNDATED-KEPT.tsv (a PAĜO line later ruled RESTU reads RESTU)."""
    p = os.path.join(D, "UNDATED-KEPT.tsv")
    if not os.path.exists(p): return {}
    return {(r[0], r[1]): r[3] for r in csv.reader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t")
            if r and r[0] != "locator"}

REASK = ("**Por ĉi tiuj linioj (la dua demando, 2026-10-26):** ĉiu el ili jam estis legita unu- aŭ dufoje, kaj la respondo "
         "estis dato per vortoj («merkrede matene», «post kelkaj semajnoj», «la 2-an (matene)»), kiun la iloj ne povas legi. "
         "**Ne respondu per vortoj.** Respondu nur per DATO el la tabelo de datoformoj, per ciferoj (tago, monato, jaro, aŭ "
         "limo kiel «antaŭ 1913-02», «inter 1905-08-05 kaj 1905-08-12»), kalkulita el la paĝo, la dato de la numero kaj "
         "la evento, kiun la paĝo priskribas; aŭ per RESTU, se la paĝo ne sufiĉas. Ekzemplo: «merkrede matene» en la "
         "raporto pri la kongreso de Bulonjo (5–12 de aŭgusto 1905) estas 1905-08-09. Kie vi kalkulas, diru en la kialo, "
         "el kio. Se la OCR difektis la daton (cifero, kiu ne povas esti ĝusta; monato aŭ jaro nelegebla aŭ detranĉita), "
         "ne kalkulu el ĝi kaj ne donu limon: PAĜO, kun kialo komencanta per «OCR difektita:».\n\n")

def rekey(a):
    """UNDATED-KEPT's stale keys re-keyed (2026-10-26; the runbook D8's «Not built yet: re-keying UNDATED-KEPT»; the
    backlog of that day: 174 lines ruled RESTU or PAĜO and asked again, their «l. K» moved by a recupel or a page look):
    a row whose (locator, anchor) matches no line of the facts file, where exactly one line has the same anchor on the
    same item and PDF page, gets a new row under that line's locator, the verdict, class and tag kept, the reason noting
    the old key. Appended, as every row of the file; the old row stays. Without --write it prints the counts."""
    D = os.path.join(G, "dowse", a.source)
    p = os.path.join(D, "UNDATED-KEPT.tsv")
    if not os.path.exists(p): sys.exit(f"no UNDATED-KEPT.tsv in dowse/{a.source}")
    now = {}
    for l in open(os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md"), encoding="utf-8"):
        if l.startswith("- $$$") and (fl := fields(l.rstrip("\n"))): now.setdefault(fl[1], set()).add(fl[2])
    page = lambda loc: re.sub(r", l\. ?\d+\s*$", "", loc)
    rows = [r for r in csv.reader((l for l in open(p, encoding="utf-8") if not l.startswith("#")), delimiter="\t") if r and r[0] != "locator"]
    have = {(r[0], r[1]) for r in rows}
    new, stays, none, many = [], 0, 0, 0
    for r in rows:
        if r[0] in now.get(r[1], ()): stays += 1; continue
        hits = [loc for loc in now.get(r[1], ()) if page(loc) == page(r[0])]
        if len(hits) == 1 and (hits[0], r[1]) not in have:
            new.append([hits[0], r[1], r[2], r[3], f"{r[4]} (re-keyed 2026-10-26 from «{r[0]}»)", r[5] if len(r) > 5 else ""]); have.add((hits[0], r[1]))
        elif len(hits) > 1: many += 1
        elif not hits: none += 1
    print(f"{a.source}: {len(rows)} rows; {stays} match a line; {len(new)} re-keyed; {many} with several candidates, {none} with none (left)")
    if a.write and new:
        with open(p, "a", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(new)
        print(f"appended {len(new)} rows to {os.path.relpath(p, ROOT)}")

OCR_WORDS = re.compile(r"\bOCR\b|mis[ae]\b|misleg|difekt|nelegebl|ne legebl|rubo|detranĉ|fuŝ|garbl|damag", re.I)
VR = os.path.join(G, "ocr", "VISION-REQUESTS.tsv")

def vision_requested():
    """-> {(locator key, PDF page)} of ocr/VISION-REQUESTS.tsv (runbook D4b: the pages whose OCR is damaged, sent to
    Miles for a vision recupel), so a «PAĜO» naming OCR damage can be checked against it."""
    if not os.path.exists(VR): return set()
    # only while «Ezri's status» reads «held»: once the page is redowsed the hold is lifted (2026-10-26)
    return {(r[2].strip(), int(m.group(1))) for r in csv.reader(open(VR, encoding="utf-8"), delimiter="\t")
            if len(r) > 10 and r[0] != "request" and r[10].strip().startswith("held") and (m := re.match(r"\s*(\d+)", r[4]))}

def loc_pages(loc):
    """-> {(locator key, PDF page)} a locator cites."""
    return {(m.group(1).strip(), int(m.group(2))) for m in re.finditer(r"(?:^|; )([^;,]+?), PDF (\d+)\b", loc)}

def pool(a):
    """POOLED PARTS (2026-10-27; the editor, on): the inputs `prep` wrote for one tag in every source
    (dowse/<source>/undated-input-<tag>[-k].tsv) pooled into parts of at most --max lines, whatever their source, each
    with one brief (the page-look template with --page), in dowse/_pooled/: undated-input-<out>-<k>.tsv and
    undated-brief-<out>-<k>.md, create-only. A reader's fixed cost (about 100k tokens) is paid once a part, not once a
    source: R6 of 2026-10-26s4, 20 per-source readers of 1 to 60 lines, became 6. `apply-pooled <out>` applies them."""
    rows = []
    for ip in sorted(glob.glob(os.path.join(G, "dowse", "*", f"undated-input-{a.tag}.tsv")) + glob.glob(os.path.join(G, "dowse", "*", f"undated-input-{a.tag}-[0-9]*.tsv"))):
        rows += [r for r in list(csv.reader(open(ip, encoding="utf-8"), delimiter="\t"))[1:] if r]
    if not rows: sys.exit(f"no dowse/*/undated-input-{a.tag}*.tsv")
    P = os.path.join(G, "dowse", "_pooled"); os.makedirs(P, exist_ok=True)
    k = a.max; parts = [rows[i:i + k] for i in range(0, len(rows), k)]
    paths = [(n, os.path.join(P, f"undated-input-{a.out}-{n}.tsv"), os.path.join(P, f"undated-brief-{a.out}-{n}.md")) for n in range(1, len(parts) + 1)]
    for _n, ip, bp in paths:
        for p in (ip, bp):
            if os.path.exists(p): sys.exit(f"{os.path.relpath(p, ROOT)} exists: not overwritten (use a new tag)")
    tp = PAGE_TEMPLATE if a.page else TEMPLATE
    body = open(tp, encoding="utf-8").read().split("\n---\n", 1)[1]
    readers = []
    for (n, ip, bp), rows_ in zip(paths, parts):
        with open(ip, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n"); w.writerow(["file", "line", "class", "the line as written"]); w.writerows(rows_)
        srcs = sorted({r[0][:-len("-dowse.md")] for r in rows_})
        open(bp, "w", encoding="utf-8").write(f"# The undated lines of {len(srcs)} sources{', the page look' if a.page else ''}, pooled, {a.out}-{n}\n\n"
            f"*From `{os.path.relpath(tp, G)}` by `tools/dowse-undated.py pool {a.tag} --out {a.out}{' --page' if a.page else ''}`: {', '.join(srcs)}. One reader, Read tool only.*\n\n---\n"
            + body.replace("{INPUT}", ip).replace("{N}", str(len(rows_)))
            .replace("{TEXTS}", "la dosiero de ĉiu ero, kiun la lokindikoj nomas: " + "; ".join(line_texts(rows_))))
        readers.append({"label": f"geniza/dowse/_pooled/undated-return-{a.out}-{n}.md",
                        "prompt": f"Legu la briefon ĉe {bp} kaj sekvu ĝin ĝis la fino."})
        print(f"wrote {os.path.relpath(ip, ROOT)} and its brief ({len(rows_)} lines; {', '.join(srcs)})")
    print(f"{len(rows)} lines from {len({r[0] for r in rows})} sources in {len(parts)} parts")
    print(json.dumps({"readers": readers}, ensure_ascii=False))

def apply_pooled(a):
    """apply-pooled OUT [--write]: each pooled part's return applied source by source (`apply` with --input and --return,
    which keeps a source's own rows), the date rows noting the pooled return."""
    import argparse as _ap
    P = os.path.join(G, "dowse", "_pooled")
    for ip in sorted(glob.glob(os.path.join(P, f"undated-input-{a.out}-[0-9]*.tsv")), key=lambda p: int(re.search(r"-(\d+)\.tsv$", p).group(1))):
        n = re.search(r"-(\d+)\.tsv$", ip).group(1); rp = os.path.join(P, f"undated-return-{a.out}-{n}.md")
        if not os.path.exists(rp): print(f"part {n}: no return filed, skipped"); continue
        srcs = sorted({r[0][:-len("-dowse.md")] for r in list(csv.reader(open(ip, encoding="utf-8"), delimiter="\t"))[1:] if r})
        for s in srcs:
            print(f"== part {n}, {s}")
            apply(_ap.Namespace(source=s, tag=f"{a.out}-{n}", skip=None, keep=None, why=None, set=None, write=a.write, input=ip, ret=rp))

def with_sen_dato(s, listed):
    """-> the list's lines of a source, and every line of its facts file still «[sen dato]» that the list lacks (the
    harvest's list holds four classes only: lines sent to the page outside them, the congress books' «16 aŭgusto»
    lines, were missed by the first count of the owed page looks, 2026-10-26). The extras' line number is their
    position in the facts file."""
    fp = os.path.join(G, "profiles", "by-source", f"{s}-dowse.md")
    have = {r[3] for r in listed}
    extra = [[f"{s}-dowse.md", str(i), "sen dato", l.rstrip("\n")]
             for i, l in enumerate(open(fp, encoding="utf-8") if os.path.exists(fp) else [], 1)
             if l.startswith("- $$$") and "**[sen dato]**" in l and l.rstrip("\n") not in have]
    return listed + extra

def owed(a):
    """THE PAGE LOOKS STILL OWED, line by line (2026-10-26; the editor, the owed page looks sorted under the
    runbook's D4b): the lines of a harvest's undated list (so still undated) whose last UNDATED-KEPT verdict is PAĜO, in
    every source, with the reason and tag of their last PAĜO row; a reason naming OCR damage is marked «ocr?» for a
    look (those go to ocr/VISION-REQUESTS.tsv, the rest to a page look). --out writes them as a TSV, create-only."""
    rows = [r for r in csv.reader(open(a.list, encoding="utf-8"), delimiter="\t") if r and r[0].endswith("-dowse.md")]
    out, n, vr = [], {}, vision_requested()
    for D in sorted(glob.glob(os.path.join(G, "dowse", "*", "UNDATED-KEPT.tsv"))):
        D = os.path.dirname(D); s = os.path.basename(D); k = kept(D)
        why = {}
        for r in csv.reader((l for l in open(os.path.join(D, "UNDATED-KEPT.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            if len(r) > 4 and r[3] == "PAĜO": why[(r[0], r[1])] = (r[4], r[5] if len(r) > 5 else "")
        for r in with_sen_dato(s, [r for r in rows if r[0] == f"{s}-dowse.md"]):
            if not (fl := fields(r[3])) or k.get((fl[2], fl[1])) != "PAĜO": continue
            reason, tag = why.get((fl[2], fl[1]), ("", ""))
            flag = "requested" if loc_pages(fl[2]) & vr else "ocr?" if OCR_WORDS.search(reason) else ""
            out.append([s, fl[2], fl[1], tag, flag, reason, r[3]])
            c = n.setdefault(s, [0, 0, 0]); c[0] += 1; c[1] += flag == "ocr?"; c[2] += flag == "requested"
    for s, (t, f, q) in n.items(): print(f"  {s}: {t} owed, {f} naming OCR damage, {q} already requested")
    print(f"{len(out)} page looks owed in {len(n)} sources; {sum(c[1] for c in n.values())} naming OCR damage, not yet "
          f"requested; {sum(c[2] for c in n.values())} already in ocr/VISION-REQUESTS.tsv")
    if a.out:
        if os.path.exists(a.out): sys.exit(f"{a.out} exists: not overwritten")
        with open(a.out, "x", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(["source", "locator", "anchor", "tag", "ocr?", "the reader's reason", "the line"]); w.writerows(out)
        print(f"wrote {os.path.relpath(a.out, ROOT)}")

def source_texts(D):
    """The source's text files, from its latest stage brief (facts-brief-<date>.md), as dowse-recall.py finds them."""
    briefs = sorted(glob.glob(os.path.join(D, "facts-brief-*.md")))
    if not briefs: return []
    t = open(briefs[-1], encoding="utf-8").read()
    return sorted(set(re.findall(r"(/[^\s`]+?/sources/(?:ocr-preferred|born-digital-text|ocr-work)/[^`\n]+?\.txt)", t)))

def line_texts(rows_):
    """THE PAGE LOOK'S TEXTS, line by line (2026-10-25: Espero Katolika's page look, all ten lines «wrong source files»):
    source_texts() takes the texts of the latest stage brief, and since the per-reader briefs (2026-10-18) a brief names
    only its own reader's texts, so the page look was given two 1904 issues for lines of 1904 and 1905. Here each item
    a line cites, by its permanent key, with its own text file (OCR-ITEM-TABLE.tsv: key → item → the preferred text,
    else the born-digital one): «‹key›: `‹path›`»."""
    k2n = {}
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if (r.get("key") or "").strip(): k2n[r["key"].strip()] = r["item"]
    out = {}
    for r in rows_:
        fl = fields(r[3])
        if not fl: continue
        for p in fl[2].split("; "):
            key = p.split(",")[0].strip(); item = k2n.get(key, key)
            path = next((x for x in (os.path.join(G, "sources", "ocr-preferred", item + ".txt"),
                                     os.path.join(G, "sources", "born-digital-text", item + ".txt")) if os.path.exists(x)), None)
            if path: out[key] = path
    return [f"«{k}»: `{v}`" for k, v in sorted(out.items())]

def prep(a):
    D = os.path.join(G, "dowse", a.source)
    lp = a.list or os.path.join(G, "profiles", "build", f"UNDATED-{a.tag}.tsv")
    rows = [r for r in csv.reader(open(lp, encoding="utf-8"), delimiter="\t") if r and r[0] == f"{a.source}-dowse.md"]
    k = kept(D)
    # --reask (2026-10-26; the editor): every «words» line whose date the tools still cannot read,
    # whatever an earlier pass ruled (about 920: answered in words in 10c or in its page look), read with its page, the
    # brief told to answer in the table's digits or RESTU, never in words (REASK below)
    if a.reask:
        hs = importlib.util.spec_from_file_location("harvest_facts", os.path.join(ROOT, "tools", "harvest-facts.py"))
        HF = importlib.util.module_from_spec(hs); argv, sys.argv = sys.argv, ["x"]; hs.loader.exec_module(HF); sys.argv = argv
        wd = lambda r: (re.match(r"^- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))? \*\*([^*]+)\*\*", r[3]) or [None, ""])[1].strip()
        todo = [r for r in rows if "words" in r[2].split(",") and fields(r[3]) and HF.needs_reading(wd(r))]
        print(f"{len(todo)} lines of {a.source} dated in words the tools cannot read (re-asked, with the page)")
        if not todo: print("nothing to re-ask"); return
        a.page = True
    elif a.page:      # the lines a reader sent to the page, and only those (with the «[sen dato]» lines the list lacks)
        todo = [r for r in with_sen_dato(a.source, rows) if (fl := fields(r[3])) and k.get((fl[2], fl[1])) == "PAĜO"]
        # D4b: a page already sent to Miles for vision is not looked at again until the redowse
        vr = vision_requested()
        held = [r for r in todo if loc_pages(fields(r[3])[2]) & vr]
        if held: print(f"  {len(held)} held back: their page is in ocr/VISION-REQUESTS.tsv (runbook D4b)")
        todo = [r for r in todo if r not in held]
        # --kept-tag TAG (2026-10-26): only those sent to the page by that pass (UNDATED-KEPT keeps «PAĜO» after a page
        # look is done, which writes its date to DECISIONS, so a bare --page asks every older page look again)
        if a.kept_tag:
            kp = os.path.join(D, "UNDATED-KEPT.tsv")
            tagged = {(r[0], r[1]) for r in csv.reader((l for l in open(kp, encoding="utf-8") if not l.startswith("#")), delimiter="\t")
                      if len(r) > 5 and r[3] == "PAĜO" and r[5].startswith(a.kept_tag)}
            todo = [r for r in todo if (fl := fields(r[3])) and (fl[2], fl[1]) in tagged]
        print(f"{len(todo)} lines of {a.source} sent to the page (UNDATED-KEPT.tsv)")
        if not todo: print("nothing for the page"); return
    else:
        todo = [r for r in rows if (fl := fields(r[3])) and (fl[2], fl[1]) not in k]
        print(f"{len(rows)} lines of {a.source} in {os.path.relpath(lp, ROOT)}; {len(rows) - len(todo)} already ruled (UNDATED-KEPT.tsv); {len(todo)} to read")
        # --redowsed TAG (2026-10-26, R6 of the selective redowse): only the lines citing a page the tag redowsed («the
        # undated pass … on the new lines only»; Oficiala Gazeto's first prep asked 264 lines, 2 of them on its 13 pages)
        if a.redowsed:
            import json
            hs = importlib.util.spec_from_file_location("harvest_facts", os.path.join(ROOT, "tools", "harvest-facts.py"))
            HF = importlib.util.module_from_spec(hs); argv, sys.argv = sys.argv, ["x"]; hs.loader.exec_module(HF); sys.argv = argv
            cfg = json.load(open(os.path.join(D, "facts-config.json"), encoding="utf-8"))
            rp = {(HF.item_key(e["item"]), int(p)) for e in cfg.get("redowsed_pages", []) if e.get("tag") == a.redowsed for p in e["pages"]}
            todo = [r for r in todo if {(HF.item_key(m.group(1).strip()), int(m.group(2)))
                                        for m in re.finditer(r"(?:^|; | · )([^·;]+?), PDF (\d+)\b", r[3])} & rp]
            print(f"  of them on the pages {a.redowsed} redowsed: {len(todo)}")
            if not todo: print("nothing to read on the redowsed pages"); return
        if not todo: print("nothing to read: step 10c is done for this source (but see --page)" if "PAĜO" in k.values() else "nothing to read: step 10c is done for this source"); return
    texts = source_texts(D)
    if a.page and not texts and not a.reask: sys.exit(f"no stage brief with the source's texts in {os.path.relpath(D, ROOT)}")
    # PARTS (2026-10-18, Amerika Esperantisto's 328 undated lines against a reader's 80, P1's cap): over --split K, the
    # list in parts of at most K, in order, each its own tag («TAG-1» …), input, brief and return; `apply` then runs on
    # each part's tag. Every file is checked before any is written
    k = a.split if a.split and len(todo) > a.split else 0
    parts = [(f"{a.tag}-{i // k + 1}", todo[i:i + k]) for i in range(0, len(todo), k)] if k else [(a.tag, todo)]
    paths = [(t, rows_, os.path.join(D, f"undated-input-{t}.tsv"), os.path.join(D, f"undated-brief-{t}.md")) for t, rows_ in parts]
    for _t, _r, ip, bp in paths:
        for p in (ip, bp):
            if os.path.exists(p): sys.exit(f"{os.path.relpath(p, ROOT)} exists: not overwritten (use a new tag)")
    tp = PAGE_TEMPLATE if a.page else TEMPLATE
    body = open(tp, encoding="utf-8").read().split("\n---\n", 1)[1]
    if a.reask or a.kept_tag: body = REASK + body
    for t, rows_, ip, bp in paths:
        with open(ip, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n"); w.writerow(["file", "line", "class", "the line as written"]); w.writerows(rows_)
        open(bp, "w", encoding="utf-8").write(f"# The undated lines of {a.source}{', the page look' if a.page else ''}, {t}\n\n*From `{os.path.relpath(tp, G)}` by "
            f"`tools/dowse-undated.py prep{' --page' if a.page else ''}`. One reader, Read tool only.*\n\n---\n" + body.replace("{INPUT}", ip)
            .replace("{N}", str(len(rows_))).replace("{TEXTS}", ("la dosiero de ĉiu ero, kiun la lokindikoj nomas: " + "; ".join(line_texts(rows_)))
                                                      if a.page else "; ".join(f"`{x}`" for x in texts)))
        print(f"wrote {os.path.relpath(ip, ROOT)} and {os.path.relpath(bp, ROOT)} ({len(rows_)} lines)")
        print(f"the reader's prompt (file-reader): UNDATED-{a.source}-{t}. Read the brief at {bp} (the part after the line «---») "
              f"and do exactly what it says. Read tool only. Your report is your final message, ending with the line «Fino: N linioj.»")
    print(f"then: tools/file-return.py --note \"Filed by Ezri, <date>, unedited: the undated reader\" agent:<id>={os.path.join(D, f'undated-return-{a.tag}.md')}")

def apply(a):
    D = os.path.join(G, "dowse", a.source)
    own = f"{a.source}-dowse.md"           # --input/--return: a list and return of several sources (the first pass's)
    inp = [r for r in list(csv.reader(open(a.input or os.path.join(D, f"undated-input-{a.tag}.tsv"), encoding="utf-8"), delimiter="\t"))[1:]
           if r and r[0] == own]
    by_key = {(r[0], int(r[1])): r for r in inp}
    ret = open(a.ret or os.path.join(D, f"undated-return-{a.tag}.md"), encoding="utf-8").read()
    # «N1.» as well as «1.» (2026-10-25, La Ondo's part 18: a reader numbered its items «N1.», and none was read)
    # and a bare «N.» (OGE's part 4, the same day): numbered by its order in the return
    found = re.findall(r"^\s*N?(\d*)\.\s+(\S+?):(\d+)\s*\|\s*(DATO|RESTU|PAĜO)\s*\|\s*([^|\n]*?)\s*\|\s*([^|\n]*?)\s*\|\s*(.*)$", ret, re.M)
    items = [((x[0] or str(i)),) + tuple(x[1:]) for i, x in enumerate(found, 1) if x[1] == own]
    skip = {int(x) for x in (a.skip or "").split(",") if x.strip()}
    keep = {int(x) for x in (a.keep or "").split(",") if x.strip()}
    sets = dict((int(k), v) for k, v in (s.split("=", 1) for s in a.set or []))
    facts = open(os.path.join(G, "profiles", "by-source", f"{a.source}-dowse.md"), encoding="utf-8").read().split("\n")
    flines = [(l, fields(l)) for l in facts if l.startswith("- ")]
    def hits(loc, phrase):
        h = [l for l, fl in flines if fl and loc in fl[2] and phrase in l]
        if h: return h
        # ACROSS A RECUPEL (2026-10-25, OGE: the input written before a vision page moved the text's line numbers): the
        # item and page without the line, as the assembler matches the row (dowse-facts-assemble.py, DPAGE)
        pg = re.sub(r", l\. ?\d+\s*$", "", loc)
        return [l for l, fl in flines if fl and pg != loc and re.search(re.escape(pg) + r", l\. ?\d", fl[2]) and phrase in l]
    dp = os.path.join(D, "DECISIONS.tsv")
    have = {tuple(l.split("\t")[:2]) for l in open(dp, encoding="utf-8")} if os.path.exists(dp) else set()
    rows, keptrows, page, hand, seen = [], [], [], [], {}
    print(f"{len(items)} items in the return, {len(inp)} lines in the input" + ("" if len(items) == len(inp) else "  ⚠ the counts differ"))
    for n, fn, ln, verdict, value, phrase, why in items:
        n = int(n); r = by_key.get((fn, int(ln)))
        if not r: hand.append((n, f"{fn}:{ln} is not in the input")); continue
        fact, anchor, loc = fields(r[3])
        if n in skip: print(f"  skipped by --skip: item {n}"); continue
        if n in keep and verdict == "DATO":       # Ezri's ruling over the reader's date: the line stays undated, and is not asked again
            verdict, why = "RESTU", f"Ezri over the reader's «{value}»: {a.why or 'kept undated'}"; print(f"  kept by --keep: item {n}")
        # A «words» line (2026-10-18: a date in words the tool could not convert; the editor
        #) ruled RESTU becomes «[sen dato]» by a date row, the words in the row's note: kept as written, it would
        # stay outside the vocabulary
        words_restu = verdict == "RESTU" and "words" in r[2].split(",")
        if verdict != "DATO" and not words_restu:
            keptrows.append([loc, anchor, r[2], verdict, why, a.tag])
            if verdict == "PAĜO": page.append((n, loc, why, r[3]))
            continue
        if words_restu:
            wd = re.match(r"^- \$\$\$ .+? \$\$\$(?: *\([^)]{1,60}\))? \*\*([^*]+)\*\*", r[3])
            value, why = "[sen dato]", f"the date in words «{wd.group(1) if wd else '?'}» left undated: {why}"
            keptrows.append([loc, anchor, r[2], verdict, why, a.tag])   # not asked again once undated
        value = sets.get(n, value).strip()
        try: d = date_vocab.parse(value)
        except ValueError: hand.append((n, f"«{value}» is outside the date vocabulary")); continue
        if d.kind == "none" and not words_restu: hand.append((n, "DATO with «[sen dato]»")); continue
        phrase = phrase.strip().strip("«»").strip()
        key = None
        if phrase and phrase in anchor and len(hits(loc, phrase)) == 1: key = phrase
        else:                                   # the anchor is shared, or the phrase is not the anchor's: the fact's first words
            words = re.sub(r"^\([^)]*\)\s*", "", fact).split()
            for k in (8, 12, 16):
                p = " ".join(words[:k])
                if len(hits(loc, p)) == 1: key = p; break
        if not key: hand.append((n, f"no phrase singles the line out at «{loc}»")); continue
        if (loc, key) in have: print(f"  already in DECISIONS: item {n}"); continue
        if (loc, key) in seen: hand.append((n, f"the same key as item {seen[(loc, key)]}")); continue
        seen[(loc, key)] = n
        rows.append([file_names(loc), key, "date", value, f"the undated pass {a.tag} (dowse runbook D6c step 10c; the editor 2026-10-15: «add 10c»)",
                     f"{why} ({os.path.relpath(a.ret, G) if a.ret else f'dowse/{a.source}/undated-return-{a.tag}.md'}, item {n}{', keyed on the fact: the anchor is shared' if key != phrase else ''})"])
        print(f"  DATO {n}: {value}  ·  {loc}  ·  {fact[:150]}")
    print(f"date rows: {len(rows)} (the reassembly should change {len(rows)} lines of {a.source}-dowse.md, besides the register and interventions)")
    print(f"kept: {sum(1 for k in keptrows if k[3] == 'RESTU')} RESTU, {len(page)} PAĜO")
    for n, loc, why, _ in page: print(f"  PAĜO {n}: {loc}: {why}")
    # D4b (2026-10-26): a page look's PAĜO that names OCR damage goes to Miles for vision; the check that it has
    vr = vision_requested()
    for n, loc, why, _ in page:
        if OCR_WORDS.search(why) and not loc_pages(loc) & vr:
            print(f"  ⚠ OCR DAMAGE, NOT YET IN ocr/VISION-REQUESTS.tsv (runbook D4b): item {n}, {loc}")
    for n, why in hand: print(f"  ⚠ HAND {n}: {why}")
    if not a.write: print("(dry run: nothing written; --write to write)"); return
    if rows:
        new = not os.path.exists(dp)
        with open(dp, "a", encoding="utf-8") as fh:
            if new: fh.write(DEC_HEAD)
            for r in rows: fh.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
    kp = os.path.join(D, "UNDATED-KEPT.tsv")
    if keptrows:
        new = not os.path.exists(kp)
        with open(kp, "a", encoding="utf-8") as fh:
            if new: fh.write(KEPT_HEAD)
            for r in keptrows: fh.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
    if page:
        pp = os.path.join(D, f"undated-page-{a.tag}.md")
        if os.path.exists(pp): print(f"  {os.path.relpath(pp, ROOT)} exists: not overwritten")
        else:
            open(pp, "w", encoding="utf-8").write(f"# The undated lines of {a.source} for a look at the page, {a.tag}\n\n" +
                "".join(f"- item {n} · {loc}: {why}\n  {line}\n" for n, loc, why, line in page))
    print(f"wrote {len(rows)} rows to {os.path.relpath(dp, ROOT)}; {len(keptrows)} to UNDATED-KEPT.tsv" + (f"; {len(page)} to undated-page-{a.tag}.md" if page else ""))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep"); p.add_argument("source"); p.add_argument("tag"); p.add_argument("--list")
    p.add_argument("--redowsed", metavar="TAG", help="only the lines on the pages this tag redowsed (R6 of the selective redowse)")
    p.add_argument("--kept-tag", help="with --page: only the lines that pass (UNDATED-KEPT's tag column) sent to the page")
    p.add_argument("--reask", action="store_true", help="every «words» line the tools still cannot read, with its page, answered in digits or RESTU (2026-10-26)")
    p.add_argument("--page", action="store_true", help="the lines sent to the page, with the source's texts (the page look)")
    p.add_argument("--split", type=int, default=0, metavar="K", help="over K lines, parts of at most K, tags TAG-1, TAG-2 …, each with its own input and brief (P1's cap: 80)")
    q = sub.add_parser("apply"); q.add_argument("source"); q.add_argument("tag"); q.add_argument("--skip")
    q.add_argument("--keep", help="DATO items to rule RESTU instead (recorded in UNDATED-KEPT.tsv)"); q.add_argument("--why", help="the reason for --keep")
    q.add_argument("--set", action="append", metavar="N=VALUE"); q.add_argument("--write", action="store_true")
    q.add_argument("--input", help="the list read (default dowse/<source>/undated-input-<tag>.tsv)")
    q.add_argument("--return", dest="ret", help="the return (default dowse/<source>/undated-return-<tag>.md)")
    k = sub.add_parser("rekey", help="UNDATED-KEPT rows re-keyed to the lines' current locators (2026-10-26)")
    k.add_argument("source"); k.add_argument("--write", action="store_true")
    o = sub.add_parser("owed", help="the page looks still owed, every source, from a harvest's undated list (2026-10-26)")
    o.add_argument("--list", required=True); o.add_argument("--out")
    pl = sub.add_parser("pool", help="the inputs of one tag in every source pooled into parts of at most --max lines (2026-10-27)")
    pl.add_argument("tag"); pl.add_argument("--out", required=True); pl.add_argument("--max", type=int, default=60); pl.add_argument("--page", action="store_true")
    pa = sub.add_parser("apply-pooled", help="each pooled part's return applied source by source")
    pa.add_argument("out"); pa.add_argument("--write", action="store_true")
    a = ap.parse_args()
    {"prep": prep, "apply": apply, "rekey": rekey, "owed": owed, "pool": pool, "apply-pooled": apply_pooled}[a.cmd](a)

if __name__ == "__main__":
    main()
