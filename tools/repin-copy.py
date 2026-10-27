#!/usr/bin/env python3
"""Re-pin our citations of a withdrawn copy to the copy kept (2026-10-20; Miles: «Could you re-pin any facts that cite
LEsperantiste.1907.5 to the same pages of …1907.5.1»; the editor's rule of 2026-10-20: a second copy kept off is
deleted from the corpus, the scan kept, so nothing may cite it).

    tools/repin-copy.py OLD-STEM NEW-STEM FILE... [--write] [--min 0.5]

OLD-STEM and NEW-STEM name texts under geniza/sources/ocr-preferred/ (or born-digital-text/), without «.txt». In each
FILE every locator «OLD-STEM.txt l.A–B» or «l.A» (with an optional «p.N» or «(fpN…» after it) is re-pinned to
«NEW-STEM.txt l.A'–B'» (the span kept), its «p.N» the new copy's PDF page of line A' (and «fpN–M» the pages of A' and
B'). The printed pages written after it are left as they are (the same issue, the same print). The old copy's own lines
are not used: the line numbers may belong to an earlier OCR of it (2026-10-20: LEsperantiste.1907.5 had 2,7xx lines
when cited, 1,857 now). Instead:
1. the anchor the locator stands for, a «…» right after it («l.A — «…»»), else the last before it on its line, else
   the first after, is found in the new copy: the window whose words of four letters or more best cover the quote's;
   kept where it covers at least --min of them (default 0.5) and the quote has three such words;
2. the others (short quotes, poor OCR) are looked for near the line the kept ones predict (old and new line numbers
   rise together: the line interpolated between the nearest kept locators below and above), within 25 lines, where at
   least half the quote's words stand;
3. what is left is listed for a look by hand and not changed.
Without --write it prints each change; with --write it rewrites the FILEs in place (their only write-set) and prints the
count. Ezri, 2026-10-20."""
import bisect, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
W = lambda s: {w.lower() for w in re.findall(r"[\wĉĝĥĵŝŭĈĜĤĴŜŬéèêàâôûç]{4,}", s)}

def load(stem):
    for sub in ("ocr-preferred", "born-digital-text"):
        p = os.path.join(G, "sources", sub, stem + ".txt")
        if os.path.exists(p):
            lines = open(p, encoding="utf-8").read().split("\n")
            page, pages = 0, []
            for l in lines:
                m = re.match(r"=== page (\d+) ===", l)
                if m: page = int(m.group(1))
                pages.append(page)
            return lines, pages
    sys.exit(f"no text {stem}.txt")

def quote_for(line, m):
    after = re.match(r"\s*—\s*«([^«»]{3,})»", line[m.end():])
    if after: return after.group(1)
    qs = [(x.start(), x.group(1)) for x in re.finditer(r"«([^«»]{3,})»", line)]
    before = [q for s, q in qs if s < m.start()]
    later = [q for s, q in qs if s > m.start()]
    return before[-1] if before else (later[0] if later else "")

def main_dowse():
    """--dowse SOURCE OLD-STEM NEW-STEM [--write] [--min 0.5] (2026-10-24; Miles: «Please re-pin your 243 lines from
    …1905.sennumera to …1905.1-2 (tools/repin-copy.py; the pages correspond one for one, PDF n to PDF n)»; the editor:
): a dowse source's facts lines citing OLD-STEM («old key, PDF n (prese M), l. K») re-pinned to NEW-STEM. A dowse
    facts file is rebuilt from its returns at every assembly, so the change goes into dowse/SOURCE/facts-config.json's
    «locator_fixes» ([regex, replacement], applied to the locator as the assembler builds it: the item's name or key),
    never into the facts file. Each line's anchor (its fourth field) is sought on the same PDF page of the new copy, else
    the page before or after: the line whose words of four letters or more best cover it, kept at --min; else the page's
    first line, listed. Without --write it prints each fix and the count."""
    a = sys.argv[1:]
    mn = float(a[a.index("--min") + 1]) if "--min" in a else 0.5
    i = a.index("--dowse"); src, old_s, new_s = a[i + 1], a[i + 2], a[i + 3]
    new, npg = load(new_s)
    nw = [W(l) for l in new]
    def cover(want, s, n): return len(want & set().union(*nw[s:s + n])) / len(want) if want else 0.0
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    LOC = re.compile(r"([\w.-]+), PDF (\d+)((?: \(prese [^)]*\))?), l\. (\d+)")
    fixes, low, seen = [], [], set()
    for line in open(os.path.join(G, "profiles", "by-source", f"{src}-dowse.md"), encoding="utf-8"):
        if not line.startswith("- $$$"): continue
        f = line.rstrip("\n").split(" · ")
        m = next((LOC.fullmatch(x.strip()) for x in f if LOC.fullmatch(x.strip())), None)
        if not m or norm(m.group(1)) != norm(old_s) or (m.group(2), m.group(4)) in seen: continue
        seen.add((m.group(2), m.group(4)))
        p, anchor = int(m.group(2)), f[3] if len(f) > 3 else ""
        want, n = W(anchor), 1 + len(anchor) // 60
        cands = [(cover(want, k, n), npg[k] == p, -k, k) for k in range(len(new)) if abs(npg[k] - p) <= 1]
        sc, _same, _k, k = max(cands, default=(0.0, False, 0, None))
        if k is None: low.append(f"PDF {p}: no such page in {new_s}"); continue
        if sc < mn or (len(want) < 2 and not (sc == 1.0 and _same)):   # a short anchor only found whole on its page
            k = next(j for j in range(len(new)) if npg[j] == p) if p in npg else k
            low.append(f"PDF {p} l. {m.group(4)} «{anchor[:50]}»: {sc:.0%}, to the page's first line, l. {k + 1}")
        pat = f"(?:{re.escape(old_s)}|{re.escape(m.group(1))}), PDF {p}((?: \\(prese [^)]*\\))?), l\\. {m.group(4)}(?!\\d)"
        fixes.append([pat, f"{new_s}, PDF {npg[k]}\\1, l. {k + 1}"])
        if "--write" not in a: print(f"  PDF {p} l. {m.group(4)} → PDF {npg[k]} l. {k + 1} ({sc:.0%}, «{anchor[:40]}»)")
    for l in low: print("  LOW " + l)
    if "--write" in a:
        cp = os.path.join(G, "dowse", src, "facts-config.json"); raw = open(cp, encoding="utf-8").read()
        import json
        c = json.loads(raw); have = {tuple(x) for x in c.get("locator_fixes", [])}
        c["locator_fixes"] = c.get("locator_fixes", []) + [x for x in fixes if tuple(x) not in have]
        open(cp, "w", encoding="utf-8").write(json.dumps(c, ensure_ascii=False, indent=1) + ("\n" if raw.endswith("\n") else ""))
    print(f"{len(fixes)} locators of {old_s} re-pinned to {new_s}" + (" and written to «locator_fixes»" if "--write" in a else " (dry run: --write to write)")
          + f"; {len(low)} to the page's first line, for a look")

def main():
    if "--dowse" in sys.argv: return main_dowse()
    # several pairs at once (2026-10-20, Juna Esperantisto 1911, eleven issues): --map «OLD=NEW;OLD=NEW» FILE..., each
    # pair run in turn over the same files
    a = sys.argv[1:]
    if "--map" in a:
        i = a.index("--map"); pairs = [p.split("=", 1) for p in a[i + 1].split(";") if p]
        rest = a[:i] + a[i + 2:]
        for old_s, new_s in pairs:
            print(f"== {old_s} → {new_s}")
            sys.argv = [sys.argv[0], old_s, new_s] + rest
            main_one()
        return
    main_one()

def main_one():
    a = sys.argv[1:]
    mn = float(a[a.index("--min") + 1]) if "--min" in a else 0.5
    args = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--min", "--page-offset", "--printed-offset"))]
    if len(args) < 3: sys.exit(__doc__)
    old_s, new_s, files = args[0], args[1], args[2:]
    new, npg = load(new_s)
    nw = [W(l) for l in new]
    def cover(want, s, n): return len(want & set().union(*nw[s:s + n])) / len(want) if want else 0.0
    # --page-offset K (2026-10-20, Juna Esperantisto 1911: the kept 20-page run is the 16-page one with its two cover pages
    # first): a locator naming its page «p.N» is searched on the new copy's page N+K only, which keeps a quote off the
    # covers' advertisements and book lists; with it, a match needs --min of the quote's words on that page
    po = int(a[a.index("--page-offset") + 1]) if "--page-offset" in a else None
    # --printed-offset K (2026-10-20, Carlevaro's Idala foliumi: «… l. 656, printed p. 16»): the printed page written
    # after the locator, plus K, is the new copy's PDF page; a quote is looked for there only, and a line with no usable
    # quote is re-pinned to that page's lines («page only» in the report)
    pro = int(a[a.index("--printed-offset") + 1]) if "--printed-offset" in a else None
    def printed_pages(line, m):
        pm = re.match(r",\s*printed pp?\.\s*(\d+)(?:[–-](\d+))?", line[m.end():])
        return (int(pm.group(1)), int(pm.group(2) or pm.group(1))) if pm else None
    def span_of(m, line=""):
        if pro is not None:
            pp = printed_pages(line, m)
            if pp: return [k for k in range(len(new)) if pp[0] + pro <= npg[k] <= pp[1] + pro]
        pm = re.search(r" p\.(\d+)", m.group(0))
        if po is None or not pm: return range(len(new))
        want_p = int(pm.group(1)) + po
        return [k for k in range(len(new)) if npg[k] == want_p]
    paged = po is not None or pro is not None
    # the stem with or without «.txt» (2026-10-20: the roster runs' «FIRST dated appearance … at JunaEsperantisto.1911.5
    # l.583 — «…»» name it bare, and their «see X.txt l.A» then took the wrong line's quote); «.txt» kept where it was
    # also the September scout files' form (2026-10-20, Carlevaro's Idala foliumi): «`STEM.txt` l. 656, printed p. 16»,
    # «ll. 116–118, 170–174, printed pp. 3–4»: «l. » with a space, «ll.», further spans (each moved by the first span's
    # shift); a printed page after a comma is the print's own and is left as it is
    pat = re.compile(re.escape(old_s) + r"(\.txt)?(`?) (l{1,2}\.\s?)(\d+)(?:[–-](\d+))?((?:, \d+(?:[–-]\d+)?)*)(?: p\.\d+(?:[–-]\d+)?| \(fp\d+(?:[–-]\d+)?)?")
    texts = {f: open(f if os.path.isabs(f) else os.path.join(G, f), encoding="utf-8").read() for f in files}
    hits = []   # (file, line no, match, quote, words, A, B)
    for f, t in texts.items():
        for i, line in enumerate(t.split("\n")):
            for m in pat.finditer(line):
                q = quote_for(line, m)
                hits.append([f, i, m, q, W(q), int(m.group(4)), int(m.group(5) or m.group(4)), None, 0.0, ""])
    # 1. the quotes found whole
    for h in hits:
        want, A, B = h[4], h[5], h[6]
        line_ = texts[h[0]].split("\n")[h[1]]
        sp = span_of(h[2], line_)
        # several spans over several printed pages: the quote may belong to any of them, so the pages' lines are the
        # placement (2026-10-20: «ll. 116–118, 170–174, printed pp. 3–4», the quote in the second span)
        multi = bool(h[2].group(6)) and pro is not None and printed_pages(line_, h[2]) and printed_pages(line_, h[2])[0] != printed_pages(line_, h[2])[1]
        if want and len(want) >= (1 if paged else 3) and not multi:
            n = max(1, min(B - A + 1, 1 + len(h[3]) // 60))
            sc, s = max(((cover(want, s, n), s) for s in sp), default=(0, None))
            if sc >= (mn if len(want) >= 3 else 1.0): h[7], h[8], h[9] = s + 1, sc, "quote" + (f" on p.{npg[s]}" if paged else ""); continue
        if pro is not None and printed_pages(line_, h[2]) and sp:
            h[7], h[8], h[9] = sp[0] + 1, 0.0, f"page only (printed p. {printed_pages(line_, h[2])[0]})"
            h.append(sp[-1] + 1)   # the page's last line, for the span
    # 2. near the line the kept ones predict
    fixed = sorted({(h[5], h[7]) for h in hits if h[7]})
    xs = [x for x, _y in fixed]
    for h in hits:
        if h[7] or not h[4] or not fixed or paged: continue   # with a page offset, the page decides, not the neighbours
        A = h[5]; k = bisect.bisect_left(xs, A)
        lo, hi = fixed[max(0, k - 1)], fixed[min(len(fixed) - 1, k)]
        guess = lo[1] if hi[0] == lo[0] else round(lo[1] + (A - lo[0]) * (hi[1] - lo[1]) / (hi[0] - lo[0]))
        n = max(1, 1 + len(h[3]) // 60)
        cands = [(cover(h[4], s, n), -abs(s + 1 - guess), s) for s in range(max(0, guess - 26), min(len(new), guess + 25))]
        if cands:
            sc, _d, s = max(cands)
            if sc >= (0.5 if len(h[4]) >= 4 else 1.0): h[7], h[8], h[9] = s + 1, sc, f"near l.{guess}"
    # a locator with no quote right after it takes the line its old number got where it had one («FIRST … l.2267 —
    # «…»» and, later on the line, «see … l.2267»)
    adj = {(h[0], h[5]): h[7] for h in hits if h[7] and re.match(r"\s*—\s*«", texts[h[0]].split("\n")[h[1]][h[2].end():])}
    for h in hits:
        if (h[0], h[5]) in adj and not re.match(r"\s*—\s*«", texts[h[0]].split("\n")[h[1]][h[2].end():]) and h[7] != adj[(h[0], h[5])]:
            h[7], h[9] = adj[(h[0], h[5])], "its number's quote"
    # write
    total, low, by = 0, [], {}
    for h in hits:
        f, i, m, q, _w, A, B, A2, sc, how = h[:10]
        if not A2:
            low.append(f"{os.path.basename(f)}: «{m.group(0)}», anchor «{q[:60]}»: left as it is"); continue
        if how.startswith("page only"):   # the whole page's lines, «ll.»; further spans dropped (they were on it)
            loc = f"{new_s}{m.group(1) or ''}{m.group(2)} ll. {A2}–{h[10]}"
            by.setdefault((f, i), []).append((m.start(), m.end(), loc)); total += 1
            if "--write" not in a: print(f"  {os.path.basename(f)}: «{m.group(0)}» → «{loc}» ({how})")
            continue
        B2 = min(len(new), A2 + (B - A))
        loc = f"{new_s}{m.group(1) or ''}{m.group(2)} {m.group(3)}{A2}" + (f"–{B2}" if B != A else "")
        if m.group(6):   # further spans, shifted as the first was
            sh = A2 - A
            loc += re.sub(r"\d+", lambda d: str(min(len(new), max(1, int(d.group(0)) + sh))), m.group(6))
        tail = m.group(0)[m.end(6) - m.start(0):]
        if tail.startswith(" p.") or tail.startswith(" (fp"):
            pa, pb = npg[A2 - 1], npg[B2 - 1]
            loc += (" p." if tail.startswith(" p.") else " (fp") + f"{pa}" + (f"–{pb}" if pb != pa else "")
        by.setdefault((f, i), []).append((m.start(), m.end(), loc))
        total += 1
        if "--write" not in a: print(f"  {os.path.basename(f)}: «{m.group(0)}» → «{loc}» ({sc:.0%}, {how}, «{q[:40]}»)")
    if "--write" in a:
        for f, t in texts.items():
            ls = t.split("\n")
            for (ff, i), reps in by.items():
                if ff != f: continue
                for s, e, loc in sorted(reps, reverse=True):
                    ls[i] = ls[i][:s] + loc + ls[i][e:]
            open(f if os.path.isabs(f) else os.path.join(G, f), "w", encoding="utf-8").write("\n".join(ls))
    for l in low: print("  LOW " + l)
    print(f"{total} locators re-pinned{' and written' if '--write' in a else ' (dry run: --write to write)'}; {len(low)} left for a look")

if __name__ == "__main__":
    main()
