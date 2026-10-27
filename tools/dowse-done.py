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
import csv, glob, os, re, subprocess, sys
import sigla

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
    # THE PUBLISHED PAGE (2026-10-25; the editor, on prosopografio/README.md
    #): prosopografio/legitaj-fontoj.md, in Esperanto, each source by its siglum and its
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
    P = [BEGIN, "",
         f"**{len(agg)} fontoj, {sp(sum(len(a['items']) for a in agg.values()))} eroj (numeroj, volumoj, libroj), "
         f"{sp(sum(r[4] for r in rows if r[0] in keep))} vortoj, {sp(sum(a['lines'] for a in agg.values()))} faktoj.**"
         + (f" Ankoraŭ ne listigitaj: {out_n} fontoj legitaj per la pli frua metodo aŭ relegotaj." if out_n else ""), "",
         "| Siglo | Fonto | Jaroj | Eroj | Faktoj |", "|---|---|---|---|---|"]
    import unicodedata
    fold = lambda x: "".join(c for c in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(c) != "Mn")
    for s in sorted(agg, key=fold):
        a = agg[s]
        P.append(f"| {s} | {eo.get(s, s)} | {yrs(a['years'])} | {len(a['items'])} | {sp(a['lines'])} |")
    P += ["", END]
    pp = os.path.join(G, "prosopografio", "legitaj-fontoj.md")
    if os.path.isdir(os.path.dirname(pp)):
        old = open(pp, encoding="utf-8").read() if os.path.exists(pp) else ""
        if BEGIN in old and END in old:
            new = old[:old.index(BEGIN)] + "\n".join(P) + old[old.index(END) + len(END):]
        else:   # the first time with the marks: the editor's prose kept, the old generated note and list replaced
            head = old.split("\n**", 1)[0] if old else "\n".join(INTRO)
            head = head.replace("<!-- GENERATED by tools/dowse-done.py after every harvest. Do not edit here. -->\n\n", "")
            head = re.sub(r" Ankoraŭ ne listigitaj: \d+ fontoj legitaj per la pli frua metodo aŭ relegotaj\.", "", head)
            new = head.rstrip("\n") + "\n\n" + "\n".join(P) + "\n"
        open(pp, "w", encoding="utf-8").write(new)
        # (the page is on the site, page 125: a changed list is put to the editor for Miles's push, as the Siglaro's)
        print(("NOTE the read-sources page (prosopografio/legitaj-fontoj.md) CHANGED: ask the editor whether to push it "
               "(Miles: genizo-push.py legitaj-fontoj)") if new != old else "the read-sources page unchanged: nothing to push")
    print(f"the dowsed list: {len(rows)} sources, {len(items)} items, {sum(r[4] for r in rows):,} tokens → "
          f"{os.path.relpath(os.path.join(D, 'DOWSED-LATEST.md'), ROOT)}, DOWSED-ITEMS-LATEST.tsv")
    return 0

if __name__ == "__main__":
    sys.exit(main())
