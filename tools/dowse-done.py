#!/usr/bin/env python3
"""What has been dowsed to date (2026-10-24; the editor; to the proposal).

Every source with a facts file (profiles/by-source/<source>-dowse.md): its siglum (profiles/SIGLA.tsv), its items (the
texts of dowse/<source>/brief-config.json, else facts-config.json's «item»), their years (OCR-ITEM-TABLE.tsv), tokens
(every whitespace token of the texts, the triage's count), the facts file's lines, the batch's steps done (by the logs
and files in dowse/<source>/: readers, dedupe, undated, page look, accuracy, review document; the last tag of each) and
whether the facts file is committed. Writes, rewritten at every run (derived, never hand-edited):

  dowse/DOWSED-LATEST.md          one row a source, for the editor
  dowse/DOWSED-ITEMS-LATEST.tsv   item, key, source, siglum, last readers' tag, committed: for a redowse list (Miles's
                                  recupel notices name items) and for tools/dowse-triage.py's tier 0

Run by dowse-facts-assemble.py after each harvest (--after-readers step 9b2, --after-dedupe d6b), or by hand:

  python3 tools/dowse-done.py
"""
import collections, csv, glob, os, re, subprocess, sys
import sigla
import page_date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
D = os.path.join(G, "dowse")

def tags(d, pat):
    """The tags of the files in d matching pat («after-readers-(.+?)(?:-from-.*)?\\.log»), latest last."""
    out = sorted({m.group(1) for f in os.listdir(d) for m in [re.fullmatch(pat, f)] if m})
    return out

def git_state(path):
    rel = os.path.relpath(path, ROOT)
    tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", rel], capture_output=True).returncode == 0
    if not tracked: return "not committed"
    changed = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", rel], capture_output=True, text=True).stdout.strip()
    return "committed, changed since" if changed else "committed"

def main():
    csv.field_size_limit(sys.maxsize)
    table = {}
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"): table[r["item"]] = r
    rows, items = [], []
    for fp in sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md"))):
        src = os.path.basename(fp)[:-len("-dowse.md")]
        d = os.path.join(D, src)
        texts = []
        for cfg in ("brief-config.json", "facts-config.json"):
            p = os.path.join(d, cfg)
            if not os.path.exists(p): continue
            import json
            j = json.load(open(p, encoding="utf-8"))
            if cfg == "brief-config.json" and j.get("texts"): texts = j["texts"]; break
            if cfg == "facts-config.json" and j.get("item"): texts = [j["item"]]
        its = [os.path.basename(t)[:-4] if t.endswith(".txt") else os.path.basename(t) for t in texts]
        # and the items the facts file's own locators name («‹key›, PDF N»), for an older dowse with no config or a
        # config naming its texts otherwise: each key back to its item by the table
        bykey = {(r.get("key") or "").strip(): it for it, r in table.items()}
        for k in sorted({m.group(1) for l in open(fp, encoding="utf-8") if l.startswith("- $$$")
                         for m in re.finditer(r" · ([A-Za-z0-9._-]+), (?:PDF \d|¶ ?\d|l\. ?\d)", l)}):
            it = bykey.get(k)
            if it and it not in its: its.append(it); texts.append(os.path.join("sources", "ocr-preferred", it + ".txt"))
        # A PARSED SOURCE'S ITEMS (2026-11-10; Miles: seven Adresaro series parsed, read whole by the parse, missing here because
        # they gave no facts line): every item of the latest parse table, dowse/<source>/adresaro-<date><tag>.tsv
        if os.path.isdir(d):
            pt = sorted(f for f in os.listdir(d) if re.fullmatch(r"adresaro-\d{4}-\d\d-\d\d\w*\.tsv", f))
            if pt:
                seen = []
                for l in open(os.path.join(d, pt[-1]), encoding="utf-8"):
                    it = l.split("\t", 1)[0]
                    if it and it != "item" and it not in its and it not in seen: seen.append(it)
                for it in seen: its.append(it); texts.append(os.path.join("sources", "born-digital-text", it + ".txt"))
        ntok, ys, sig = 0, [], set()
        for t, it in zip(texts, its):
            p = os.path.join(G, t) if t.endswith(".txt") else next(iter(glob.glob(os.path.join(G, "sources", "*", it + ".txt"))), "")
            if p and os.path.exists(p): ntok += len(open(p, encoding="utf-8", errors="replace").read().split())
            r = table.get(it, {})
            y = re.search(r"(1[6-9]\d\d|20\d\d)", r.get("year") or "")
            if y: ys.append(int(y.group(1)))
            key = (r.get("key") or "").strip()
            h = sigla.head(key)[0] if key else None
            if h: sig.add(h.split(" ")[0])
            items.append((it, key, src, h.split(" ")[0] if h else ""))
        nlines = sum(1 for l in open(fp, encoding="utf-8") if l.startswith("- $$$"))
        steps = []
        if os.path.isdir(d):
            for name, pat in (("readers", r"after-readers-(.+?)(?:-from-.+)?\.log"), ("dedupe", r"after-dedupe-(.+?)(?:-from-.+)?\.log"),
                              ("undated", r"after-undated-(\d{4}-\d\d-\d\d[a-oq-z]?(?:-\d+)?)\.log"),
                              ("page look", r"after-undated-(\d{4}-\d\d-\d\d[a-z]?)p\.log"),
                              ("accuracy", r"accuracy-return-(.+?)\.md"), ("review", r"BATCH-REVIEW-(.+?)\.md")):
                ts = tags(d, pat)
                if ts: steps.append(f"{name} {ts[-1]}")
        last = next((s.split(" ", 1)[1] for s in steps if s.startswith("readers ")), "")
        rows.append((src, ", ".join(sorted(sig)) or "—", len(its), f"{min(ys)}–{max(ys)}" if ys else "—", ntok, nlines,
                     "; ".join(steps) or "(no batch files: an older dowse)", git_state(fp), last))
    with open(os.path.join(D, "DOWSED-ITEMS-LATEST.tsv"), "w", encoding="utf-8") as fh:
        fh.write("# GENERATED by tools/dowse-done.py at every harvest. Do not edit. One row an item dowsed: its source's facts file profiles/by-source/<source>-dowse.md.\n")
        fh.write("item\tkey\tsource\tsiglum\treaders_tag\tcommitted\n")
        st = {r[0]: (r[8], r[7]) for r in rows}
        for it, key, src, sg in items: fh.write(f"{it}\t{key}\t{src}\t{sg}\t{st[src][0]}\t{st[src][1]}\n")
    L = ["# What has been dowsed — the last build", "",
         "**GENERATED by `tools/dowse-done.py` at every harvest. Do not edit.** One row a source with a facts file "
         "(`profiles/by-source/‹source›-dowse.md`); its items, item by item, in `DOWSED-ITEMS-LATEST.tsv` (for a redowse list "
         "and the triage's tier 0). Tokens: every whitespace token of the texts, the triage's count. Steps: the last tag of each "
         "batch step whose files are in `dowse/‹source›/`.", "",
         f"**{len(rows)} sources, {sum(r[2] for r in rows):,} items, {sum(r[4] for r in rows):,} tokens, {sum(r[5] for r in rows):,} fact lines.**", "",
         "| source | siglum | items | years | tokens | lines | steps done | facts file |", "|---|---|---|---|---|---|---|---|"]
    for src, sg, n, yr, tok, nl, steps, gs, _l in rows:
        L.append(f"| {src} | {sg} | {n} | {yr} | {tok:,} | {nl:,} | {steps} | {gs} |")
    open(os.path.join(D, "DOWSED-LATEST.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    # THE PUBLISHED PAGE (2026-10-25; the editor, on prosopografio/README.md, asking that these
    # be synced into this folder as readable pages): published/genizo/pages/legitaj-fontoj.md (in geniza/prosopografio/ until 2026-10-30,
    # the editor: every site page's source in the one place), in Esperanto, each source by its siglum and its
    # work (profiles/SIGLA-EO.tsv), its years, items and fact lines; rewritten with the list
    sp = lambda x: f"{x:,}".replace(",", " ")   # 15 303, the Esperanto page's thousands
    eo = {}
    pe = os.path.join(G, "profiles", "SIGLA-EO.tsv")
    if os.path.exists(pe):
        for l in open(pe, encoding="utf-8"):
            if l.startswith("#") or l.startswith("siglum\t"): continue
            f = l.rstrip("\n").split("\t")
            if len(f) >= 2: eo[f[0]] = f[1]
    # BY SIGLUM, NEW-STYLE ONLY (2026-10-25; the editor, reviewing the page;
    #): one row a siglum (the register's own, not a label's head with its place, «UnivKong1»), its work's entry,
    # its items, years and fact lines summed over the sources that read it; a source counts when it was read by the
    # batch pipeline (a dedupe step, or readers from 2026-10-18 on) and is not in dowse/REDOWSE-SCHEDULED.tsv
    redo = {}
    rp = os.path.join(D, "REDOWSE-SCHEDULED.tsv")
    if os.path.exists(rp):
        for l in open(rp, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if f and f[0] and not l.startswith(("#", "source\t")): redo[f[0]] = f[1] if len(f) > 1 else ""
    def new_style(steps):
        tg = re.search(r"readers (\d{4}-\d\d-\d\d)", steps)
        return "dedupe " in steps or bool(tg and tg.group(1) >= "2026-10-18")
    keep = {r[0] for r in rows if new_style(r[6]) and r[0] not in redo}
    def siglum_of(key):
        for rx, row, _ in sigla.load():
            if rx.search(key): return row["siglum"] if row.get("status") == "signed" else None
        return None
    agg = {}
    for it, key, src, _h in items:
        if src not in keep: continue
        s = siglum_of(key) if key else None
        if not s: continue
        a = agg.setdefault(s, {"items": set(), "years": [], "lines": 0, "srcs": set()})
        a["items"].add(it); a["srcs"].add(src)
        y = re.search(r"(1[6-9]\d\d|20\d\d)", table.get(it, {}).get("year") or "")
        if y: a["years"].append(int(y.group(1)))
    for src in keep:   # the fact lines, each by its own locator's siglum
        fp = os.path.join(G, "profiles", "by-source", f"{src}-dowse.md")
        for l in open(fp, encoding="utf-8"):
            if not l.startswith("- $$$"): continue
            m = re.search(r" · ([A-Za-z0-9._-]+), (?:PDF \d|¶ ?\d|l\. ?\d)", l)
            s = siglum_of(m.group(1)) if m else None
            if s in agg: agg[s]["lines"] += 1
    yrs = lambda ys: "—" if not ys else (str(min(ys)) if min(ys) == max(ys) else f"{min(ys)}–{max(ys)}")
    # A MONOGRAPH'S YEAR OF PUBLICATION (Miles, 2026-11-11; the editor: the «Jaroj» column of Legitaj fontoj never
    # empty for a monograph, since it gives the year of publication): where the item table gives no year, the year its signed
    # siglum carries («Clark1907», «Eins1889a», «Künz2006»), else that of its Esperanto entry («… 1907. *…*»)
    def sigyear(s):
        m = re.search(r"(1[6-9]\d\d|20\d\d)[a-z]?$", s or "")
        if m: return [int(m.group(1))]
        e = eo.get(s, "")
        if re.search(r"(1[6-9]\d\d|20\d\d)\s*[–-]", e): return []   # a run («1895–1914», «1904–»): not one year
        ys = set(re.findall(r"\b(1[6-9]\d\d|20\d\d)\b", e))
        return [int(ys.pop())] if len(ys) == 1 else []   # the entry's one year: «*Ora Libro …*. 1937.», «… aprilo 1914»
    out_n = len([r for r in rows if r[0] not in keep])
    # THE INTRO IS THE EDITOR'S (2026-10-25
    #): the tool writes only between the two marks, the counts and the table;
    # the title and the prose above are written once, the first time, and never again
    BEGIN, END = "<!-- LIST BEGIN: written by tools/dowse-done.py after every harvest; edit above or below, not here -->", "<!-- LIST END -->"
    INTRO = ["# Legitaj fontoj", "", "_Kiuj fontoj estas jam legitaj por la prosopografio._", "",
             "La legiloj legis ĉiun paĝon de la jenaj fontoj kaj skribis ĉiun fakton, kiun ili donas pri la personoj de la amplekso "
             "(la esperantistoj aliĝintaj antaŭ 1908, la idistoj aliĝintaj antaŭ 1931; la biografioj traktas la idistojn "
             "aliĝintajn antaŭ 1919). Fonto ne en ĉi tiu listo ankoraŭ ne estas legita: kion ĝi diras, ankoraŭ mankas en la "
             "profiloj. La sigloj: `siglaro.md`.", ""]
    # THE STAGES (the editor, 2026-11-11;
    # the blank and cupel sources listed too, each stage in a table of its own, by each source's current stage): from
    # dowse/ETAPOJ.tsv (tools/source-stages.py snapshot, one per release); without it, the page as before
    import importlib.util
    _sp = importlib.util.spec_from_file_location("source_stages", os.path.join(ROOT, "tools", "source-stages.py"))
    SS = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(SS)
    hist, hunit = SS.history()
    staged = bool(hist)
    # THE SINTER TABLE HOLDS ONLY WHAT HAS REACHED SINTER (Miles, 2026-11-11; the editor: Blan1999 listed among the sinter
    # sources while at the cupel stage; the fix approved): a facts file appears as soon as a harvest chain assembles a source,
    # before its harvest, so a source whose every item has a stage and none is at sinter goes to its own stage's table below,
    # not here; the word count follows
    if staged:
        _now = {it: l[-1][1] for it, l in hist.items() if l}
        for s in [s for s, a in agg.items() if all(it in _now for it in a["items"]) and not any(_now[it] == "sinter" for it in a["items"])]:
            del agg[s]
        _live = {src for a in agg.values() for src in a["srcs"]}
        keep = {k for k in keep if k in _live}
    P = [BEGIN, "",
         (("## Etapo sinter: legitaj kaj kunfanditaj en la profilojn\n\n") if staged else "")
         + f"**{len(agg)} fontoj, {sp(sum(len(a['items']) for a in agg.values()))} eroj (numeroj, volumoj, libroj), "
         f"{sp(sum(r[4] for r in rows if r[0] in keep))} vortoj, {sp(sum(a['lines'] for a in agg.values()))} faktoj.**"
         + (f" Ankoraŭ ne listigitaj: {out_n} fontoj legitaj per la pli frua metodo aŭ relegotaj." if out_n else ""), "",
         ("| Siglo | Fonto | Speco | Jaroj | Eroj | Faktoj | Etapo |" if staged else "| Siglo | Fonto | Speco | Jaroj | Eroj | Faktoj |"),
         ("|---|---|---|---|---|---|---|" if staged else "|---|---|---|---|---|---|")]
    import unicodedata
    fold = lambda x: "".join(c for c in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(c) != "Mn")
    # PRIMARA OR SEKUNDARA (2026-10-27; the editor: «primara» and «sekundara», defined in the conventions,
    # and a column of Legitaj fontoj): from the item table's «kind» of the source's items; both where they differ
    KIND = {"PRIMARY": "primara", "SECONDARY": "sekundara"}
    for s in sorted(agg, key=fold):
        a = agg[s]
        ks = sorted({KIND.get((table.get(it, {}).get("kind") or "").strip(), "") for it in a["items"]} - {""})
        kind = " kaj ".join(ks) if ks else "—"
        # an organ's issues after the 1914 cutoff count as secondary for the period (Amerika Esperantisto 1915–1916): said so
        if ks == ["primara", "sekundara"]:
            sy = [int(m.group(1)) for it in a["items"] if (table.get(it, {}).get("kind") or "").strip() == "SECONDARY"
                  for m in [re.search(r"(1[6-9]\d\d|20\d\d)", table.get(it, {}).get("year") or "")] if m]
            if sy and min(sy) > 1914: kind = "primara; sekundara post 1914"
        P.append(f"| {s} | {eo.get(s, s)} | {kind} | {yrs(a['years'] or sigyear(s))} | {len(a['items'])} | {sp(a['lines'])} |"
                 + (f" {SS.etapo(a['items'], hist) or '—'} |" if staged else ""))
    if staged:
        # the sources below sinter, one table a stage, each source by its siglum or title key, its items at that stage now
        now = {it: l[-1][1] for it, l in hist.items() if l}
        HEAD = {"dowse": "## Etapo dowse: legitaj, ankoraŭ ne kunfanditaj en la profilojn",
                "cupel": "## Etapo cupel: OSR-teksto preta, ankoraŭ ne legita",
                "blank": "## Etapo blank: tenataj, ankoraŭ sen OSR-teksto"}
        # a source with a signed siglum its own row, by the sigla as they stand now (not as at the snapshot: Miles folded 40
        # signed rows in after it, 2026-11-11); the rest, without a siglum, consolidated into one row a kind (the editor,
        # 2026-11-11: minor sources at one stage and with no siglum consolidated firmly,
        # though in the end everything with a siglum gets its own entry)
        signed = {row["siglum"] for _, row, _ in sigla.load() if row.get("status") == "signed"}
        trows = SS.table()
        for stage in ("dowse", "cupel", "blank"):
            groups, minor = collections.defaultdict(list), collections.defaultdict(list)
            for it, s in now.items():
                if s != stage: continue
                u = SS.unit_of(it, trows)
                if u in signed: groups[u].append(it)
                else: minor[KIND.get((table.get(it, {}).get("kind") or "").strip(), "—")].append(it)
            if not groups and not minor: continue
            n_minor = len({SS.unit_of(i, trows) for v in minor.values() for i in v})
            P += ["", HEAD[stage], "", f"**{len(groups) + n_minor} fontoj, {sp(sum(len(v) for v in groups.values()) + sum(len(v) for v in minor.values()))} eroj.**", "",
                  "| Siglo | Fonto | Speco | Jaroj | Eroj | Etapo |", "|---|---|---|---|---|---|"]
            def row(label, title, its, kind=None):
                ks = [kind] if kind else sorted({KIND.get((table.get(i, {}).get("kind") or "").strip(), "") for i in its} - {""})
                ys = [int(m.group(1)) for i in its for m in [re.search(r"(1[6-9]\d\d|20\d\d)", table.get(i, {}).get("year") or "")] if m]
                return f"| {label} | {title.replace('|', '/')} | {' kaj '.join(ks) or '—'} | {yrs(ys or sigyear(label))} | {sp(len(its))} | {SS.etapo(its, hist) or '—'} |"
            for u in sorted(groups, key=fold):
                its = groups[u]
                title = eo.get(u) or next(((table.get(i, {}).get("title") or "").strip() for i in its if (table.get(i, {}).get("title") or "").strip()), u)
                P.append(row(u, title, its))
            for k in sorted(minor, key=fold):
                its = minor[k]
                nt = len({SS.unit_of(i, trows) for i in its})
                P.append(row("—", f"aliaj fontoj sen siglo: {sp(nt)} " + ("titolo" if nt == 1 else "titoloj"), its, None if k == "—" else k))
    P += ["", END]
    pp = os.path.join(ROOT, "published", "genizo", "pages", "legitaj-fontoj.md")
    if os.path.isdir(os.path.dirname(pp)):
        old = open(pp, encoding="utf-8").read() if os.path.exists(pp) else ""
        if BEGIN in old and END in old:
            new = old[:old.index(BEGIN)] + "\n".join(P) + old[old.index(END) + len(END):]
        else:   # the first time with the marks: the editor's prose kept, the old generated note and list replaced
            head = old.split("\n**", 1)[0] if old else "\n".join(INTRO)
            head = head.replace("<!-- GENERATED by tools/dowse-done.py after every harvest. Do not edit here. -->\n\n", "")
            head = re.sub(r" Ankoraŭ ne listigitaj: \d+ fontoj legitaj per la pli frua metodo aŭ relegotaj\.", "", head)
            new = head.rstrip("\n") + "\n\n" + "\n".join(P) + "\n"
        new = page_date.stamp(old, new)   # «_Aktualigita: …_», the day the list last changed (2026-10-31)
        open(pp, "w", encoding="utf-8").write(new)
        # (the page is on the site, page 125: a changed list is put to the editor for Miles's push, as the Siglaro's)
        print(("NOTE the read-sources page (published/genizo/pages/legitaj-fontoj.md) CHANGED: ask the editor whether to push it "
               "(Miles: genizo-push.py legitaj-fontoj)") if new != old else "the read-sources page unchanged: nothing to push")
    print(f"the dowsed list: {len(rows)} sources, {len(items)} items, {sum(r[4] for r in rows):,} tokens → "
          f"{os.path.relpath(os.path.join(D, 'DOWSED-LATEST.md'), ROOT)}, DOWSED-ITEMS-LATEST.tsv")
    return 0

if __name__ == "__main__":
    sys.exit(main())
