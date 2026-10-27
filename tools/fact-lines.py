#!/usr/bin/env python3
"""The line of the source text each dowse fact stands on, by tool (the editor, 2026-10-17 20:1x; to Ezri's design,
).

    tools/fact-lines.py [--source <dowse source> …] [--date D]

For every line of profiles/by-source/<source>-dowse.md (every *-dowse.md without --source): its first locator gives the
item and the PDF page; the line of the item's OCR text (sources/ocr-preferred/<item>.txt) where the anchor begins is
found the way fact-ids.py finds a quotation (the first three to six words, from the first to the fourth word, on the page
and its neighbours), on the page's own lines, a line-end hyphen joined as fact-ids.py joins it. Where the anchor is not
found (garbled OCR), the line of the page that holds the head's surname, if one only, is taken instead, marked «name».
A line whose locator itself cites «l. N» keeps it, marked «cited».

THE ANCHOR STAYS THE KEY; THE LINE IS A CACHE (the editor): the text is
re-OCR'd from time to time and its lines shift, so each row carries the text's fingerprint (sha256, 12 characters), and
a row whose fingerprint no longer matches the text is to be recomputed, never trusted.

Writes profiles/build/FACT-LINES.tsv (remade each run: source file, line in it, item, page, text line, how, fingerprint)
and prints the counts per source. Born-digital («¶ N») items are paragraphs, not lines: skipped. Reads only. Ezri,
2026-10-17."""
import argparse, collections, datetime, glob, hashlib, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = saved
    return m

def page_words(path, fid):
    """{page: [(normalised word, text line)]}, the page's own lines, headers left out and line-end hyphens joined as
    fact-ids.load_pages() joins them (the joined word is the first line's)."""
    out, cur, page = {}, None, None
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    carry = None                                  # a word broken at a line end: (its first part, its line)
    for n, l in enumerate(lines, 1):
        m = re.match(r"^=== page (\d+) ===\s*$", l)
        if m:
            page = int(m.group(1)); cur = out.setdefault(page, []); carry = None; continue
        if cur is None or fid.HEADER.match(l): continue
        toks = l.split()
        ln0 = n                                   # the line the first word is counted on
        if carry and toks:
            toks[0] = carry[0] + toks[0]; ln0 = carry[1]
        carry = None
        if toks and re.search(r"\w-$", toks[-1]) and n < len(lines) and re.match(r"\s*\w", lines[n]):   # lines[n]: the next
            carry = (toks[-1][:-1], ln0 if len(toks) == 1 else n); toks = toks[:-1]
        for k, t in enumerate(toks):
            for w in fid.norm(t).split():
                cur.append((w, ln0 if k == 0 else n))
    return out

def find_line(pw, page, words):
    """The text line where the anchor's words begin: fact-ids.find()'s order of tries."""
    for start in ((0, 1, 2, 3) if len(words) >= 3 else (0,)):
        for k in ((6, 5, 4, 3) if len(words) >= 3 else (len(words),)):
            q = words[start:start + k]
            if len(q) < k: continue
            for p in (page, page - 1, page + 1):
                flat = pw.get(p)
                if not flat: continue
                ws = [w for w, _ in flat]
                for j in range(len(ws) - len(q) + 1):
                    if ws[j:j + len(q)] == q:
                        return flat[j][1]
    return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--source", action="append"); ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    hf = load("hf", os.path.join(ROOT, "tools", "harvest-facts.py")); fid = load("fid", os.path.join(ROOT, "tools", "fact-ids.py"))
    files = ([os.path.join(G, "profiles", "by-source", f"{s}-dowse.md") for s in a.source] if a.source
             else sorted(glob.glob(os.path.join(G, "profiles", "by-source", "*-dowse.md"))))
    texts, shas, rows, counts = {}, {}, [], collections.defaultdict(collections.Counter)
    for f in files:
        fn = os.path.basename(f)
        for n, line in enumerate(open(f, encoding="utf-8"), 1):
            if not line.startswith("- $$$"): continue
            ps = line.rstrip("\n").split("  ⟵ ")[0].split(" · ")
            if len(ps) < 6: counts[fn]["unparsed"] += 1; continue
            anchor, loc = ps[-4], ps[-3]
            ms = hf.locators(loc)
            if not ms or not ms[0].group("pdf"): counts[fn]["no PDF page"] += 1; continue
            item, page = ms[0].group("item").strip(), int(ms[0].group("pdf"))
            path = os.path.join(G, "sources", "ocr-preferred", item + ".txt")
            if not os.path.exists(path): counts[fn]["no text"] += 1; continue
            if path not in texts:
                texts[path] = page_words(path, fid)
                shas[path] = hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]
            cited = re.search(r", l\. (\d+)\b", loc)
            if cited:
                rows.append((fn, n, item, page, int(cited.group(1)), "cited", shas[path])); counts[fn]["cited"] += 1; continue
            segs = [s for s in re.split(r"…|\.\.\.", anchor) if s.strip()]
            words = fid.norm(max(segs, key=lambda s: len(s.split())) if segs else anchor).split()
            ln = find_line(texts[path], page, words) if words else None
            how = "anchor"
            if ln is None:                            # garbled OCR: the head's surname on the page, if on one line only
                sur = fid.norm(re.match(r"^- \$\$\$ (.+?) \$\$\$", line).group(1)).split()
                key = max(sur, key=len) if sur else ""
                hits = sorted({l for w, l in texts[path].get(page, []) if key and len(key) >= 4 and w == key})
                if len(hits) == 1: ln, how = hits[0], "name"
            if ln is None: counts[fn]["not found"] += 1; continue
            rows.append((fn, n, item, page, ln, how, shas[path])); counts[fn][how] += 1
    out = os.path.join(G, "profiles", "build", "FACT-LINES.tsv")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(f"# tools/fact-lines.py, {a.date}: the text line of each dowse fact; a row whose fingerprint no longer matches its text is stale\n")
        fh.write("file\tline\titem\tpage\ttext_line\thow\ttext_sha12\n")
        fh.writelines("\t".join(map(str, r)) + "\n" for r in rows)
    tot = collections.Counter()
    for fn in sorted(counts):
        c = counts[fn]; tot.update(c)
        print(f"{fn}: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"all: " + ", ".join(f"{k} {v}" for k, v in tot.most_common()) + f" → {os.path.relpath(out, ROOT)}")

if __name__ == "__main__":
    main()
