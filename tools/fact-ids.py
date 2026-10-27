#!/usr/bin/env python3
"""fact-ids — TRIAL: compute source-anchored fact IDs for one facts file, and test how stable they are.

Design under trial: plans/second-witnesses-plan-2026-10-09.md § 10 and the Fable review's B2/B3
(plans/fable-review-prosopography-return-2026-10-10.md). Not ruled; nothing here is written into any facts file.

For each «- $$$ NAME $$$ …» line: take its first quotation «…» and its locator «PDF N»; find the quotation on that page
of the OCR text (trying 6, 5, 4, then 3 opening words; then the neighbouring pages); walk back to the start of the
sentence that holds it, with one fixed splitter; normalise the sentence's first six words (lower case, accents and
punctuation stripped, line-end hyphens joined); the ID is the first 12 hex characters of
sha1("<item>|<page where the sentence starts>|<six words>"). Lines that share an ID are flagged, not numbered: whether
they are one statement about several people or two facts from one sentence (needing counters -1, -2) is the reader's
call. Hyphens are dropped in normalising, so «23-jara», «23- jara» and a line-end «23-/jara» agree.

Tests reported:
  T1  two runs give identical IDs;
  T2  quoting from a later word of the same quotation (words 4–9 instead of 1–6) gives the same ID;
  T3  (with --alt-text) a different OCR reading of the same pages: how many IDs survive.

    tools/fact-ids.py <facts.md> --text <ocr.txt> --item <item-key> [--alt-text <ocr2.txt>] --report <out.md>

Writes only --report, and refuses to overwrite it.
"""
import argparse, hashlib, os, re, sys, unicodedata

ABBR = {"k.a.", "t.e.", "ktp.", "k.t.p.", "kp.", "ekz.", "pĝ.", "p.", "s-ro", "s-ino", "f-ino", "d-ro", "n-ro",
        "prof.", "akad.", "gen.", "st.", "vol.", "no.", "n.", "red.", "eld.", "jan.", "feb.", "mar.", "apr.",
        "jun.", "jul.", "aŭg.", "sep.", "okt.", "nov.", "dec.", "s-roj", "d-ino", "ĉ.", "pr.", "ark.", "inĝ.", "dr."}
HEADER = re.compile(r"^[\s|\d]*[A-ZĈĜĤĴŜŬ][A-ZĈĜĤĴŜŬ \-]{4,}[\s|\d]*$")
OPEN = "«“\"'(—–-[„‹"
CLOSE = "»”\"')]›"

def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("-", "")   # «23-jara» = «23jara» = «23- jara»
    return re.sub(r"[\W_]+", " ", s).strip()   # letters and digits of any script: a Cyrillic quotation was wiped (2026-10-13)

def load_pages(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    parts = re.split(r"^=== page (\d+) ===\s*$", t, flags=re.M)
    pages = {}
    for i in range(1, len(parts), 2):
        lines = [l for l in parts[i + 1].split("\n") if not HEADER.match(l)]
        body = "\n".join(lines)
        body = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", body)      # line-end hyphens joined
        pages[int(parts[i])] = body.split()
    return pages

def ends_sentence(tok, nxt):
    core = tok.rstrip(CLOSE)
    if not core or core[-1] not in ".!?":
        return False
    if core[-1] == ".":
        low = core.lower().lstrip(OPEN)
        if low in ABBR or re.fullmatch(r"[^\W\d_]\.", low) or re.fullmatch(r"\d+\.", low):
            return False
    n = nxt.lstrip(OPEN)
    return bool(n) and (n[0].isupper() or n[0].isdigit())

_NW = {}
def page_words(pages, p):
    """[(normalised word, token index)] for page p, computed once per pages-dict and page (2026-10-19: the harvest
    called find() 46,357 times and re-normalised every token of the page up to 48 times a call, 70% of its run;
    the pages dict is kept in the entry so a recycled id() can never return another text's words)."""
    hit = _NW.get((id(pages), p))
    if hit is not None and hit[0] is pages:
        return hit[1]
    toks = pages.get(p)
    nw = [(w, i) for i, t in enumerate(toks) for w in norm(t).split()] if toks else None
    _NW[(id(pages), p)] = (pages, nw)
    return nw

def find(pages, page, words):
    """Return (page, token index) of the quotation's start, trying the page then its neighbours."""
    # fewer than three words reach here only from an anchor padded with ⟨fino⟩ (a text under six words, 2026-10-14):
    # match them as they are, from the first word
    for start in ((0, 1, 2, 3) if len(words) >= 3 else (0,)):  # an OCR error in the opening words: start later
      for k in ((6, 5, 4, 3) if len(words) >= 3 else (len(words),)):
        q = words[start:start + k]
        if len(q) < k:
            continue
        for p in (page, page - 1, page + 1):
            # a token can normalise to several words («s-ro» → «s ro»): match word by word, each word knowing its token
            nw = page_words(pages, p)
            if not nw:
                continue
            flat = [w for w, _ in nw]
            for j in range(len(flat) - len(q) + 1):
                if flat[j:j + len(q)] == q:
                    return p, nw[j][1], f"{k}" if not start else f"{k}, from word {start + 1}"
    return None

def sentence_start(pages, page, idx):
    toks = pages[page]
    j = idx
    while j > 0:
        if ends_sentence(toks[j - 1], toks[j]):
            return page, j
        j -= 1
    prev = pages.get(page - 1)                                  # crosses a page break: start on the page before
    if prev and not ends_sentence(prev[-1], toks[0]):
        k = len(prev)
        while k > 0 and not ends_sentence(prev[k - 1], prev[k] if k < len(prev) else toks[0]):
            k -= 1
        return page - 1, k
    return page, 0

def six_words(pages, page, j):
    out, p, i = [], page, j
    while len(out) < 6 and p in pages:
        toks = pages[p]
        while i < len(toks) and len(out) < 6:
            out += norm(toks[i]).split()
            i += 1
        p, i = p + 1, 0
    return " ".join(out[:6])

def parse(path):
    rows = []
    for n, l in enumerate(open(path, encoding="utf-8"), 1):
        if not l.startswith("- $$$"):
            continue
        name = re.match(r"- \$\$\$ (.+?) \$\$\$", l).group(1)
        date = (re.search(r"\*\*([^*]+)\*\*", l) or [None, ""])[1]
        pdf = re.search(r"PDF (\d+)", l)
        quote, segments = None, []
        for q in re.findall(r"«([^«»]*(?:«[^»]*»[^«»]*)*)»", l):     # every part of every quotation, for matching
            for seg in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", q)):
                w = norm(seg).split()
                if len(w) >= 3:
                    segments.append(w)
        for q in re.findall(r"«([^«»]*(?:«[^»]*»[^«»]*)*)»", l):
            for seg in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", q)):   # «[sic]» insertions dropped
                w = norm(seg).split()
                if len(w) >= 3:
                    quote = w
                    break
            if quote:
                break
        rows.append(dict(n=n, name=name, date=date, pdf=int(pdf.group(1)) if pdf else None, quote=quote, segments=segments))
    return rows

def compute(rows, pages, item, shift=0):
    out = {}
    for r in rows:
        if not r["pdf"] or not r["quote"]:
            out[r["n"]] = dict(status="no quote" if r["pdf"] else "no locator")
            continue
        q = r["quote"][shift:]
        if len(q) < 3:
            out[r["n"]] = dict(status="quote too short to shift")
            continue
        hit = find(pages, r["pdf"], q)
        if not hit:
            out[r["n"]] = dict(status="not found")
            continue
        p, idx, k = hit
        sp, sj = sentence_start(pages, p, idx)
        six = six_words(pages, sp, sj)
        pre = f"{item}|{sp}|{six}"
        out[r["n"]] = dict(status=f"found ({k} words{', page ' + str(p) if p != r['pdf'] else ''})", page=sp, six=six,
                          id=hashlib.sha1(pre.encode()).hexdigest()[:12], anchor=" ".join(q[:6]))
    # Lines sharing an ID but quoting different words: one statement about several people, or two facts from one
    # sentence? The tool cannot tell (trial finding, 2026-10-10: Jacob and Stettler 1934 quote different stretches of one
    # statement). So it only flags them; the reader assigns a counter (-1, -2) where they are two facts.
    groups = {}
    for r in rows:
        o = out[r["n"]]
        if "id" in o:
            groups.setdefault(o["id"], []).append(r["n"])
    for i, g in groups.items():
        if len(g) > 1:
            for n in g:
                out[n]["shares"] = ", ".join(str(m) for m in g if m != n)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("facts"); ap.add_argument("--text", required=True); ap.add_argument("--item", required=True)
    ap.add_argument("--alt-text"); ap.add_argument("--report", required=True)
    a = ap.parse_args()
    if os.path.exists(a.report):
        sys.exit("refusing to overwrite " + a.report)
    rows = parse(a.facts)
    pages = load_pages(a.text)
    r1, r2 = compute(rows, pages, a.item), compute(rows, pages, a.item)
    t1 = sum(1 for n in r1 if r1[n].get("id") == r2[n].get("id"))
    rs = compute(rows, pages, a.item, shift=3)
    t2 = [(n, r1[n].get("id"), rs[n].get("id"), rs[n]["status"]) for n in r1 if "id" in r1[n]]
    alt = compute(rows, load_pages(a.alt_text), a.item) if a.alt_text else None
    ided = [n for n in r1 if "id" in r1[n]]
    L = [f"# Fact-ID trial: `{os.path.basename(a.facts)}`", "",
         f"`[tools/fact-ids.py, item «{a.item}», text {a.text}{', alternative reading ' + a.alt_text if a.alt_text else ''}. A trial; nothing written into the facts file.]`", "",
         f"- fact lines: {len(rows)}; with an ID: {len(ided)}; without: {len(rows) - len(ided)}",
         f"- distinct IDs: {len({r1[n]['id'] for n in ided})}; lines sharing a sentence with another line (reader decides: one statement, or two facts needing counters): {sum(1 for n in ided if r1[n].get('shares'))}",
         f"- **T1, determinism:** {t1} of {len(rows)} identical on a second run",
         f"- **T2, quoting from word 4 instead of word 1:** {sum(1 for x in t2 if x[1] == x[2])} same ID, "
         f"{sum(1 for x in t2 if x[2] and x[1] != x[2])} different ID, {sum(1 for x in t2 if not x[2])} not testable (quotation too short or not found)"]
    if alt:
        same = sum(1 for n in ided if alt[n].get("id") == r1[n]["id"])
        L.append(f"- **T3, a different OCR reading:** {same} of {len(ided)} IDs survive; "
                 f"{sum(1 for n in ided if alt[n].get('id') and alt[n]['id'] != r1[n]['id'])} change; {sum(1 for n in ided if not alt[n].get('id'))} not found in the other reading")
    L += ["", "| line | person | PDF | status | ID | shares the sentence with line | sentence's first six words | T2 | T3 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        o, s = r1[r["n"]], rs[r["n"]]
        t2c = "" if "id" not in o else ("same" if s.get("id") == o["id"] else ("—" if not s.get("id") else "DIFFERENT: " + s.get("six", "")))
        t3c = "" if not alt or "id" not in o else ("same" if alt[r["n"]].get("id") == o["id"] else ("not found" if not alt[r["n"]].get("id") else "CHANGED: " + alt[r["n"]].get("six", "")))
        L.append(f"| {r['n']} | {r['name']} | {r['pdf'] or ''} | {o['status']} | {o.get('id', '')} | {o.get('shares', '')} | {o.get('six', '')} | {t2c} | {t3c} |")
    open(a.report, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[4:10])); print("wrote", a.report)

if __name__ == "__main__":
    main()
