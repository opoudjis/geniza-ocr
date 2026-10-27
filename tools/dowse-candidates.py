#!/usr/bin/env python3
"""The namesakes a dowse reader may meet in a source, with the dates and places that tell them apart (2026-10-15: the
probe reader who qualified «Postnikov» as «(Fjodor)» from «ekstera scio, ne kontrolita kontraŭ la profiloj»; the
editor, to
, with a tool giving the candidates).

    tools/dowse-candidates.py <source> [--date D]

For every surname of the harvest's PERSONS table (tools/harvest-facts.py: a surname held by two or more people, each
with a description and the qualifier forms that name him) that occurs in the source's texts (brief-config.json,
«texts»), lists the candidates: the description and the qualifier to write. Writes dowse/<source>/candidates.md, or
candidates-<D>.md with --date, create-only; the brief (tools/dowse-brief-fill.py) points to it. Ezri, 2026-10-15."""
import argparse, ast, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def persons():
    src = open(os.path.join(ROOT, "tools", "harvest-facts.py"), encoding="utf-8").read()
    m = re.search(r"^PERSONS = (\{.*?^\})", src, re.M | re.S)
    if not m: sys.exit("PERSONS not found in tools/harvest-facts.py")
    return ast.literal_eval(re.sub(r"#[^\n]*", "", m.group(1)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--date", default="")
    a = ap.parse_args()
    D = os.path.join(G, "dowse", a.source)
    cp = os.path.join(D, "brief-config.json")
    if not os.path.exists(cp): sys.exit(f"refusing: dowse/{a.source}/brief-config.json is missing (D6c step 3 makes it first)")
    c = json.load(open(cp, encoding="utf-8"))
    text = "\n".join(open(os.path.join(G, t), encoding="utf-8").read() for t in c["texts"]).lower()
    P = persons()
    out = [f"# La samnomuloj en {a.source}", "",
           "`[tools/dowse-candidates.py el la tabelo PERSONS de tools/harvest-facts.py: ĉiu familinomo de la projekto, kiun "
           "tenas du aŭ pli da personoj, kaj kiu aperas en la teksto de la fonto. Por ĉiu persono: la priskribo kaj la "
           "kvalifiko skribenda. Kie la fonto ne permesas elekti, skribu la nudan nomon kaj proponu.]`", ""]
    n = 0
    for name, people in sorted(P.items()):
        if not re.search(r"\b" + re.escape(name.lower()) + r"\b", text): continue
        n += 1
        out.append(f"- **{name}**")
        for desc, forms in people:
            out.append(f"  - ({forms[0]}): {desc}" if forms else f"  - {desc}")
    if not n: out.append("(neniu samnomulo de la projekto aperas en la fonto)")
    path = os.path.join(D, f"candidates-{a.date}.md" if a.date else "candidates.md")
    with open(path, "x", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
    print(f"{n} surnames with namesakes → {os.path.relpath(path, ROOT)}")

if __name__ == "__main__":
    main()
