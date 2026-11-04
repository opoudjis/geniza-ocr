#!/usr/bin/env python3
"""The undated pass's proposed dates, checked by tool and sampled (2026-10-23; the editor, on 3,993 proposals,
option (b) approved: the mechanical pass first, then a blind sample of 40 a source read by hand; a clean
sample's proposals written, a source with faults read in full).

    tools/dowse-undated-check.py <source> <tag> [--n 40]

Reads the dry runs of `dowse-undated.py apply` in dowse/<source>/after-undated-<tag>.log (the «DATO N: date · locator ·
fact» lines, part by part) and flags each proposed date:
  VOCAB   outside the date vocabulary (tools/date_vocab.py), a date still in words among them;
  LATER   after the end of its own issue (the masthead's or the item's date, tools/harvest-facts.py issue_date), a plan
          («☞») aside;
  EVENT   an event form («antaŭ la kongreso de Bulonjo»), which the calendar resolves at the harvest or not: listed, not a fault.
Then draws a seeded sample of N of the unflagged proposals. Writes dowse/<source>/undated-check-<tag>.md (create-only):
the counts, every flagged proposal in full, the sample in full, numbered, each with its part and DATO number for
`apply --skip/--set`. Writes nothing else. Ezri, 2026-10-23."""
import importlib.util, os, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import date_vocab as DV


def hf():
    spec = importlib.util.spec_from_file_location("hf", os.path.join(ROOT, "tools", "harvest-facts.py"))
    m = importlib.util.module_from_spec(spec); saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = saved
    return m


def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    src, tag = sys.argv[1], sys.argv[2]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 40
    D = os.path.join(G, "dowse", src)
    logp = os.path.join(D, f"after-undated-{tag}.log")
    out = os.path.join(D, f"undated-check-{tag}.md")
    if os.path.exists(out): sys.exit(f"refused: {os.path.relpath(out, ROOT)} exists")
    H = hf()
    rows, part = [], None
    for l in open(logp, encoding="utf-8"):
        m = re.match(r"^## u3, apply, a dry run \((.+)\)", l)
        if m: part = m.group(1); continue
        m = re.match(r"^\s+DATO (\d+): (.+?)  ·  (.+?)  ·  (.*)$", l.rstrip("\n"))
        if m and part: rows.append((part, int(m.group(1)), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()))
    flagged, clean = [], []
    for r in rows:
        part, k, date, loc, fact = r
        why = []
        try: d = DV.parse(date)
        except ValueError: d = None; why.append("VOCAB")
        if d is not None and d.kind == "event": why.append("EVENT")
        if d is not None and d.hi and not getattr(d, "planned", False):
            iss = H.issue_date(f"- $$$ X $$$ **[n]** · {{x: y}} · {loc}")
            if iss and iss[0]:
                y, a, b = iss[0], iss[1], iss[2]
                end = f"{y + (1 if a and b and b < a else 0)}-{(b or 12):02d}-31"
                if d.lo and d.lo > end: why.append(f"LATER (the issue {H.issue_field(iss)})")
        (flagged if [w for w in why if w != "EVENT"] else clean).append((r, why))
    rng = random.Random(f"{src}|{tag}|undated-check")
    sample = sorted(rng.sample(clean, min(n, len(clean))), key=lambda x: (x[0][0], x[0][1]))
    def fmt(i, r, why):
        part, k, date, loc, fact = r
        return f"{i}. **{part} DATO {k}:** «{date}» · {loc} · {fact}" + (f" — {', '.join(why)}" if why else "")
    doc = [f"# The undated pass checked: {src} ({tag})", "",
           f"`[tools/dowse-undated-check.py on after-undated-{tag}.log: {len(rows)} proposals; flagged {len(flagged)} "
           f"(VOCAB outside the vocabulary, LATER after its own issue); a blind sample of {len(sample)} of the {len(clean)} "
           f"unflagged, seed «{src}|{tag}|undated-check», to read by hand against the template's rules.]`", "",
           f"## Flagged ({len(flagged)})", ""] + ([fmt(i, r, w) for i, (r, w) in enumerate(flagged, 1)] or ["(none)"]) + [
           "", f"## The sample ({len(sample)})", ""] + [fmt(i, r, w) for i, (r, w) in enumerate(sample, 1)]
    open(out, "x", encoding="utf-8").write("\n".join(doc) + "\n")
    ev = sum(1 for r, w in flagged + clean if "EVENT" in w)
    print(f"{src}: {len(rows)} proposals; flagged {len(flagged)} (VOCAB {sum(1 for r, w in flagged if 'VOCAB' in w)}, "
          f"LATER {sum(1 for r, w in flagged if any(x.startswith('LATER') for x in w))}); events {ev}; sample {len(sample)} → {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
