#!/usr/bin/env python3
"""The our-documents pass, its first step by tool: find the primary source and page behind every line of our own
documents, so that the reader who rewrites them rereads a page it is given instead of searching for it (the editor,
2026-10-20; the test on Beauchemin's 24 lines cost
461,875 tokens, most of it the reader's 53 reads finding the sources; the dowse runbook, D6, point 1).

    tools/ourdocs-locate.py                         every line of our documents: profiles/build/OURDOCS-LOCATED-LATEST.tsv
    tools/ourdocs-locate.py --also FILE.md ...      add files to «our documents» (analyses not named …-fold-…)
    tools/ourdocs-locate.py --person NAME --pages OUT.md
                                                    that person's lines with the page text of each located source, for a
                                                    reader's brief (create-only)

Our documents: the files of profiles/by-source/ named «-fold-» or «adjudications», with any named by --also. For each fact
line, in this order:
  item    a locator already in the item form («‹item key›, PDF N», «¶ N», «l. N»);
  old     a text file and line or page whose stem is an item of OCR-ITEM-TABLE.tsv («progreso10.txt ll. 890», «oge.1
          p123», «lalumo.1902.arb/page-0024») (fact-labels.py's failsafe, `old_locator`);
  alias   a work named in prose: the *Ora Libro* with «PDF N»; the EdE; eo.wikipedia «Title» (the saved wikitext);
          a Belga Sonorilo issue «nNNN (mon YYYY) pN»;
  same    «same»: the source of the line before it in the file;
  ruling  no source, and the line is a ruling or a judgement of ours (an adjudications file, «RULED», «⇒ juĝo»): it
          needs no page, only its rewriting as a `juĝo` line;
  none    nothing found: the reader looks, or the line keeps its locator.
The TSV: file, line, name, how, item key, page, text path, the locator as written. Ezri, 2026-10-20."""
import csv, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
BS = os.path.join(G, "profiles", "by-source")
_spec = importlib.util.spec_from_file_location("fact_labels", os.path.join(ROOT, "tools", "fact-labels.py"))
FL = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(FL)

def ours(also):
    fs = sorted(f for f in os.listdir(BS) if f.endswith(".md") and ("-fold-" in f or "adjudication" in f))
    return fs + [os.path.basename(a) for a in also if os.path.basename(a) not in fs]

def name(l):
    m = re.match(r"^- \$\$\$ (.+?) \$\$\$", l)
    return m.group(1) if m else ""

def item_path(key):
    items = FL._items()
    inv = {v: k for k, v in items.items()}
    return FL._txt(inv.get(key, key)) or ""

def alias(l):
    """(item key, page, path) for a work named in prose, or None."""
    items = FL._items()
    pdf = re.search(r"\bPDF (\d+)", l)
    if re.search(r"Ora Libro", l) and pdf:
        return items.get("oralibro", "oralibro"), pdf.group(1), FL._txt("oralibro") or ""
    if re.search(r"\bEdE\b|Enciklopedio de Esperanto", l) and pdf:
        k = "ENCIKLOPEDIO_DE_ESPERANTO_1933_"
        return items.get(k, k), pdf.group(1), FL._txt(k) or ""
    m = re.search(r"eo\.wikipedia «([^»]+)»", l)
    if m:
        f = os.path.join(G, "sources", "wikipedia-eo-io", "eo-" + m.group(1).replace(" ", "_") + ".wikitext")
        if os.path.exists(f): return "eo-" + m.group(1).replace(" ", "_"), "", f
    m = re.search(r"\bn(\d{3}) \((\w{3})\w* (\d{4})\) p\.? ?(\d+)", l)
    if m:
        it = f"LaBelgaSonorilo_{m.group(3)}_n{m.group(1)}_{m.group(2).lower()}"
        if it in items: return items[it], m.group(4), FL._txt(it) or ""
    return None

def _line_page(path, n):
    """The page of line n of a text file by its «=== page N ===» markers, or ""."""
    if not path or not path.endswith(".txt") or not os.path.exists(path): return ""
    pg = ""
    for k, x in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        if k > n: break
        m = re.match(r"=== page (\d+) ===", x)
        if m: pg = m.group(1)
    return pg

def by_file(l):
    """A source named by its path or its file stem though it is no item of the table (Belga Sonorilo's year bundles,
    saved web pages, captions): (how, key, page, path) or None; the key is the file's stem, marked «file»/«web»."""
    m = re.search(r"(sources/[^`\s:;,()]+\.(txt|wikitext|html|md))", l)
    if m and os.path.exists(os.path.join(G, m.group(1))):
        path = os.path.join(G, m.group(1)); stem = os.path.basename(m.group(1)).rsplit(".", 1)[0]
        ln = re.search(re.escape(m.group(1)) + r"`?\s*(?::|l\.\s?|ll\.\s?)(\d+)", l)
        if m.group(2) == "txt":
            pm = re.search(r"\bp\.?\s?(\d+)", l[m.end():])
            return ("file", stem, pm.group(1) if pm else (_line_page(path, int(ln.group(1))) if ln else ""), path)
        return ("web", stem, f"l. {ln.group(1)}" if ln else "", path)
    m = re.search(r"\bBS(\d\d):(\d+)", l) or re.search(r"\b(?:belgaSonorilo|BelgaSonorilo)\.19(\d\d)\.txt`?\s*(?::|l\.\s?)(\d+)", l)
    if m:
        stem = f"belgaSonorilo.19{m.group(1)}"; path = FL._txt(stem)
        if path: return ("file", stem, _line_page(path, int(m.group(2))), path)
    m = re.search(r"Enciklopedio de Esperanto\*? \(1933\),? (?:s\.v\.|art\.) [«\"]*([A-ZĈĜĤĴŜŬ][\wĉĝĥĵŝŭ-]+)", l) or re.search(r"\bEdE[^·]*?s\.v\. «?([A-ZĈĜĤĴŜŬ][\wĉĝĥĵŝŭ-]+)", l)
    if m:
        k = "ENCIKLOPEDIO_DE_ESPERANTO_1933_"; path = FL._txt(k)
        if path:
            pg = ""
            for x in open(path, encoding="utf-8", errors="replace"):
                mm = re.match(r"=== page (\d+) ===", x)
                if mm: pg = mm.group(1)
                elif x.startswith(m.group(1)): return ("alias", FL._items().get(k, k), pg, path)
    # the work alone, its page unknown («`belgaSonorilo.1906.txt`», «`oge.5`»): the reader looks within that one text
    items = FL._items()
    for c in re.findall(r"`([A-Za-z][\w.\- ]*?)(?:\.txt)?`", l):
        if c in items or FL._txt(c):
            path = FL._txt(c) or ""
            return ("work", items.get(c, c), "", path)
    return None

def locate(lines):
    out, prev = [], None
    for n, l in enumerate(lines, 1):
        if not l.startswith("- $$$"): continue
        ps = l.split(" · ")
        loc_field = next((p for p in ps[2:] if re.search(r"`|PDF|\bp\.? ?\d|same|txt|¶|l\. ?\d", p)), ps[-3] if len(ps) > 3 else "")
        r = None
        m = next((FL.LOC.match(p) for p in ps if FL.LOC.match(p)), None)
        if m:
            k = m.group(1)
            # a judgement line of ours, located at our document itself (the pass's own output): no page to read
            r = ("ruling", k, "", "") if os.path.exists(os.path.join(BS, k + ".md")) else ("item", k, m.group(2) or m.group(3) or m.group(4), item_path(k))
        if not r:
            o = FL.old_locator(l)
            if o: r = ("old", o[0], o[1], item_path(o[0]))
        if not r:
            a = alias(l) or by_file(l)
            if a: r = a if a[0] in ("file", "web", "alias", "work") else ("alias",) + a
        if not r and re.search(r"(^|· )same\b", l) and prev:
            sl = re.search(r"same,?\s*`?:(\d+)", l)   # «same, `:723–726`»: the same file, another line
            r = ("same", prev[1], _line_page(prev[3], int(sl.group(1))) if sl and prev[3] else prev[2], prev[3])
        if not r and (re.search(r"RULED|⇒ juĝo|\{juĝo:", l)):
            r = ("ruling", "", "", "")
        if not r: r = ("none", "", "", "")
        if r[0] in ("item", "old", "alias", "same", "file", "web", "work"): prev = r
        out.append((n, name(l), r, loc_field.strip()[:160], l))
    return out

def page_text(path, page, who, width=12):
    if not path or not os.path.exists(path): return ""
    t = open(path, encoding="utf-8", errors="replace").read().split("\n")
    if page:
        i = next((j for j, x in enumerate(t) if x.strip() == f"=== page {page} ==="), None)
        if i is None: return ""
        j = next((k for k in range(i + 1, len(t)) if t[k].startswith("=== page ")), len(t))
        block, base = t[i:j], i
    else:
        block, base = t, 0
    stem = re.sub(r"[^A-Za-z]", "", who.split(" (")[0])[:5].lower()
    hits = [k for k, x in enumerate(block) if stem and stem in re.sub(r"[^A-Za-z]", "", x).lower()]
    if hits:
        a, b = max(0, hits[0] - width), min(len(block), hits[-1] + width + 1)
    else:
        a, b = 0, min(len(block), 2 * width + 6)
    return "\n".join(f"{base + k + 1}: {block[k]}" for k in range(a, b))

def main():
    a = sys.argv[1:]
    also = a[a.index("--also") + 1:] if "--also" in a else []
    also = [x for x in also if not x.startswith("--")]
    person = a[a.index("--person") + 1] if "--person" in a else None
    files = ours(also)
    rows, counts = [], {}
    for f in files:
        p = os.path.join(BS, f)
        if not os.path.exists(p): continue
        for n, who, r, lf, l in locate(open(p, encoding="utf-8").read().split("\n")):
            rows.append((f, n, who, r, lf, l)); counts[r[0]] = counts.get(r[0], 0) + 1
    out = os.path.join(G, "profiles", "build", "OURDOCS-LOCATED-LATEST.tsv")
    with open(out, "w", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["file", "line", "name", "how", "item", "page", "text", "locator as written"])
        for f, n, who, r, lf, l in rows:
            w.writerow([f, n, who, r[0], r[1], r[2], os.path.relpath(r[3], G) if r[3] else "", lf])
    print(f"{len(files)} files, {len(rows)} lines: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])) + f" → {os.path.relpath(out, ROOT)}")
    if person and "--pages" in a:
        dest = a[a.index("--pages") + 1]
        sel = [x for x in rows if x[2].split(" (")[0].strip().upper() == person.upper()]
        parts = [f"# The pages behind {person}'s lines in our documents\n",
                 f"`[tools/ourdocs-locate.py --person {person}: {len(sel)} lines; each with the page of its located source, cut around the name. «ruling»: no page needed; «none»: not located.]`\n"]
        for f, n, who, r, lf, l in sel:
            parts += [f"## {f}, l. {n} ({r[0]}{': ' + r[1] + (', PDF ' + r[2] if r[2] else '') if r[1] else ''})", "", f"`{l[2:]}`", ""]
            pt = page_text(r[3], r[2] if r[2] and not r[2].startswith("l.") else "", who) if r[0] in ("item", "old", "alias", "same", "file", "web") else ""
            if pt: parts += ["```", pt, "```", ""]
        with open(dest, "x", encoding="utf-8") as fh:
            fh.write("\n".join(parts) + "\n")
        print(f"{dest}: {len(sel)} lines")

if __name__ == "__main__":
    main()
