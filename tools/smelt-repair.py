#!/usr/bin/env python3
"""The repair pass of a smelt (2026-11-11; the editor, proofreading the first smelt's biographies
).

    smelt-repair.py brief <stem> <tag> [--max-items N]     the repair briefs of one biography (create-only)
    smelt-repair.py count <tag>                            the candidates of every biography, and the briefs' sizes
    smelt-repair.py apply <stem> <tag> [--write]           a reader's return's replacements into S4-RETURN-<tag>.md

The candidates, from the biography's part 1 (S4-VIEW-<tag>.md, its L-numbers the frozen profile's lines):
  (1) HOLES: each sentence with ⚫ («truo en la legitaj fontoj»): a period writer saw only its own part's lines, so its hole may be
      filled elsewhere in the biography or the profile. Beside it, the passages of other sections and the profile's lines that
      share its rare words (by tool, up to 4 and 4), and, for a periodical, the BPEAPE entry of the item table.
  (2) RETELLINGS: two sections citing two or more of the same lines: the event told twice. The rule (the editor's ruling): the full
      telling in the section of the event's own date; a later report of it one sentence, its date and «vidu supre», with what
      the report itself got wrong or how it was received.
  (3) OUR DOCUMENTS: each sentence citing a GZ- siglum: kept only as a new finding of ours, else cited to the source it reads.
A reader returns, for each candidate, a verdict and, where the text changes, the sentence as it stands and the sentence that
replaces it. `apply` writes them into the joined return (the return kept as S4-RETURN-<tag>-before-repair.md), every old
sentence found exactly once or the replacement refused and listed; then smelt-s4-view.py --replace and fact-labels.py remake the
reading copies. Ezri, 2026-11-11."""
import collections, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
SM = os.path.join(G, "smelt")
STOP = set("""estis estas esti sian siaj sia lian liaj lia ilia iliaj kiel kiun kiuj kiu kiam kaj aŭ sed ankaŭ ankoraŭ tamen
la de en al el por pri kun sen post antaŭ inter laŭ ĉe tra super sub kontraŭ ĝis dum ekde ke ne nur jam tiu tiuj tio ĉi
legitaj fontoj fonto linioj linio periodo periodo tiu ĉi diras donas mankas truo nomas nomis sekcio parto li ŝi ili oni""".split())


def part1(stem, tag):
    t = open(os.path.join(SM, stem, f"S4-VIEW-{tag}.md"), encoding="utf-8").read()
    t = t[:t.find("\n## 2. ")] if "\n## 2. " in t else t
    secs, cur = [], ["(antaŭ la sekcioj)", []]
    for l in t.split("\n"):
        if re.match(r"^#{2,4} ", l):
            if cur[1]: secs.append((cur[0], "\n".join(cur[1])))
            cur = [l.lstrip("# ").strip(), []]
        else: cur[1].append(l)
    if cur[1]: secs.append((cur[0], "\n".join(cur[1])))
    return secs


def paras(secs):
    for name, body in secs:
        for p in body.split("\n\n"):
            p = p.strip()
            if p and not p.startswith("`["): yield name, p


SKIP_SECS = re.compile(r"^(Enhavo|Resumo|Kie troviĝas la fontoj|Verkoj laŭ la fontoj|Nomoj|Samnomuloj|La malfermitaj konfliktoj|Notoj pri malgravaj malkongruoj|Aldonoj)", re.I)


def sentences(p):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZĈĜĤĴŜŬ«(*⚫])", p) if s.strip()]


def rare_words(s, n=6):
    ws = [w for w in re.findall(r"[A-Za-zĈĜĤĴŜŬĉĝĥĵŝŭÀ-ÿ'-]{5,}", re.sub(r"\[[^\]]*\]|⟦[^⟧]*⟧", " ", s))]
    out = []
    for w in ws:
        k = w.lower().rstrip("jn")
        if k in STOP or k[:-1] in STOP: continue
        stem = k[:max(5, len(k) - 3)]   # «stenografisto» and «stenografion» meet on «stenograf»
        if stem not in out: out.append(stem)
    return sorted(out, key=lambda w: -len(w))[:n]


_BP = None


def bpeape(s):
    """the BPEAPE entries («Bibliografio de Periodaĵoj en aŭ pri Esperanto», sources/…/bpeape.txt, «1158. Bremena Esperanto-
    Spegulo. …») whose title begins with a title or a capitalised word of the sentence (the editor)"""
    global _BP
    if _BP is None:
        p = next(iter(glob.glob(os.path.join(G, "sources", "*", "bpeape.txt"))), None)
        t = open(p, encoding="utf-8", errors="replace").read() if p else ""
        _BP = [(m.group(2).lower(), m.group(0)[:700]) for m in re.finditer(r"(?m)^(\d{1,5})\. ([^.\n]{2,80})\.[^\n]*(?:\n(?!\d{1,5}\. )[^\n]*){0,6}", t)]
    keys = [k.strip("* ").lower() for k in re.findall(r"\*([^*]{3,60})\*", s)]
    keys += [w.lower() for w in re.findall(r"\b([A-ZĈĜĤĴŜŬ][a-zĉĝĥĵŝŭ]{3,})\b", s) if w.lower() not in STOP]
    out = []
    for k in keys:
        for title, entry in _BP:
            if title == k or (len(k) > 6 and title.startswith(k)):
                if entry not in out: out.append(entry)
            if len(out) >= 3: return out
    return out


def gz_lines(stem, tag):
    """the profile lines whose label is one of our documents (a GZ- siglum), by the labels table"""
    p = os.path.join(SM, stem, f"LABELS-{tag}.tsv")
    out = set()
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) > 1 and f[1].startswith("GZ") and f[0].startswith("L"): out.add(int(f[0][1:]))
    return out


def candidates(stem, tag):
    secs = part1(stem, tag)
    prof = open(os.path.join(SM, stem, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").read().split("\n")
    allp = list(paras(secs))
    gzl = gz_lines(stem, tag)
    holes, rets, gz = [], [], []
    for name, p in allp:
        if SKIP_SECS.match(name): continue
        for s in sentences(p):
            if "⚫" in s and not s.startswith("= kalkulite"):
                ws = rare_words(s)
                if not ws: continue
                near = [(n2, p2) for n2, p2 in allp if n2 != name and sum(w in p2.lower() for w in ws) >= max(1, min(2, len(ws) - 1))][:4]
                pl = [(i + 1, l) for i, l in enumerate(prof) if l.startswith("- $$$") and sum(w in l.lower() for w in ws) >= max(1, min(2, len(ws) - 1))][:4]
                holes.append({"section": name, "sentence": s, "words": ws,
                              "passages": [(n2, p2[:600]) for n2, p2 in near], "profile": [f"L{i}: {l[:400]}" for i, l in pl],
                              "bpeape": bpeape(s)})
            ls = {int(n) for n in re.findall(r"\bL(\d+)\b", s)} & gzl
            if ls:
                gz.append({"section": name, "sentence": s, "lines": [prof[n - 1][:500] for n in sorted(ls) if 0 < n <= len(prof)]})
    # retellings: two sections citing two or more of the same lines
    cites = collections.defaultdict(set)
    sec_paras = collections.defaultdict(list)
    for name, p in allp:
        if SKIP_SECS.match(name) or p.startswith("*"): continue   # the italic section summaries repeat by design
        for n in re.findall(r"\bL(\d+)\b", p): cites[int(n)].add(name)
        sec_paras[name].append(p)
    pairs = collections.Counter()
    for n, ss in cites.items():
        ss = sorted(ss)
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)): pairs[(ss[i], ss[j])] += 1
    for (a, b), k in pairs.items():
        if k < 2: continue
        shared = {n for n, ss in cites.items() if a in ss and b in ss}
        pa = [p for p in sec_paras[a] if any(re.search(rf"\bL{n}\b", p) for n in shared)]
        pb = [p for p in sec_paras[b] if any(re.search(rf"\bL{n}\b", p) for n in shared)]
        rets.append({"sections": [a, b], "shared": sorted(shared), "a": [p[:1500] for p in pa][:3], "b": [p[:1500] for p in pb][:3]})
    return holes, rets, gz


def count(tag):
    tot = collections.Counter(); size = 0
    for d in sorted(glob.glob(os.path.join(SM, "*", f"S4-VIEW-{tag}.md"))):
        stem = d.split(os.sep)[-2]
        if stem == "collinson": continue
        h, r, g = candidates(stem, tag)
        chars = len(json.dumps([h, r, g], ensure_ascii=False))
        size += chars; tot["holes"] += len(h); tot["retellings"] += len(r); tot["gz"] += len(g)
        print(f"{stem}: {len(h)} holes, {len(r)} retellings, {len(g)} GZ; candidates {chars:,} characters")
    print(f"ALL: {dict(tot)}; {size:,} characters of candidates")


BRIEF = """# Riparo de la biografio de {name} (smelt {tag}), peco {k} el {n}

## La briefo

Vi kontrolas kandidatojn por riparo de biografio, kiun verkis pluraj legiloj, ĉiu por sia periodo kaj ĉiu vidante nur la liniojn de sia propra periodo. Legu nur ĉi tiun dosieron; ne rulu ŝelajn komandojn, ne faru retajn serĉojn. Skribu vian respondon per la ilo Write al `{ret}`; via fina mesaĝo estas nur la linio «Skribita: {retname}, ‹N› kandidatoj».

Tri specoj de kandidatoj:

- **H, truo.** Frazo kun ⚫️ («truo en la legitaj fontoj»). Ĝia verkanto vidis nur sian periodon, do la truo eble estas plenigita aliloke en la biografio aŭ en la profilo. Sub ĝi: la pasaĵoj de aliaj sekcioj kaj la linioj de la profilo (kun siaj L-numeroj), kiuj havas ĝiajn maloftajn vortojn, kaj, por periodaĵo, la eniroj de BPEAPE (*Bibliografio de Periodaĵoj en aŭ pri Esperanto*), registro, en kiu oni rajtas serĉi datojn kaj lokojn de periodaĵoj. Verdikto: **plenigita** (la truo ne staras: skribu la anstataŭan frazon, citante la L-numerojn de la linioj, kiuj plenigas ĝin; por BPEAPE skribu «[BPEAPE n-ro ‹N›]»), **parte** (la frazo ŝanĝiĝu, sed parto de la truo restas), aŭ **restas** (nenio el la sube montrita plenigas ĝin; ne skribu anstataŭaĵon).
- **R, rerakonto.** Du sekcioj citas du aŭ pli da samaj linioj: la sama okazaĵo rakontita dufoje. La regulo de la redaktoro: la plena rakonto staras en la sekcio de la propra dato de la okazaĵo; posta raporto pri ĝi (artikolo, letero, rememoro) en sia sekcio havas nur unu frazon kun sia dato kaj «(vidu supre)», plus kion la raporto mem eraris aŭ kiel ĝi estis akceptita. Verdikto: **mallongigita** (skribu la mallongan anstataŭaĵon de la posta rakonto, kaj se necese aldonon al la frua) aŭ **akceptebla** (la du pasaĵoj diras malsamajn aferojn; nenio ŝanĝiĝu).
- **G, nia dokumento.** Frazo citas linion de nia propra laboraĵo (siglo GZ-…). La regulo de la redaktoro: tia citaĵo restas nur, kiam ĝi estas nia propra nova kontribuo, kiun neniu fonto donas; kiam la linio nur legas fonton, la frazo citu la fonton. Verdikto: **restas**, **al-fonto** (anstataŭu la citaĵon per la L-numero de la linio de la fonto mem, se ĝi estas montrita), aŭ **forigi** (la frazo perdas la parton, kiu ripozas nur sur nia juĝo).

Reguloj por ĉiu anstataŭaĵo: «malnova» estas **ekzakte** kopiita el la teksto montrita, signo post signo, unu tuta frazo aŭ alineo; «nova» estas en la stilo de la biografio: Esperanto, la L-numeroj en rektaj krampoj kiel «[L123, L456]», niaj markoj (∴ konkludite, ◊? konjektite, ⚫️ truo) kiel en la teksto, ĉiu dato kun sia jaro (ISO), neniu fakto, kiun la montritaj linioj kaj pasaĵoj ne donas. Ne tuŝu la tekston de aliaj frazoj.

## La formo de via respondo

Por ĉiu kandidato unu bloko, en la ordo de la kandidatoj:

```
### H1
verdikto: plenigita
malnova: ‹la frazo ekzakte›
nova: ‹la anstataŭa frazo›
kialo: ‹unu linio›
```

Por «restas» kaj «akceptebla» skribu nur «verdikto» kaj «kialo».

## La kandidatoj
"""


def render(stem, tag, items):
    out = []
    for cid, kind, c in items:
        if kind == "H":
            out += [f"### {cid} (truo, sekcio «{c['section']}»)", "", f"**La frazo:** {c['sentence']}", ""]
            for n2, p2 in c["passages"]: out += [f"- *el la sekcio «{n2}»:* {p2}"]
            for l in c["profile"]: out += [f"- *profilo:* {l}"]
            for e in c["bpeape"]: out += [f"- *BPEAPE:* {e}"]
            out.append("")
        elif kind == "R":
            a, b = c["sections"]
            out += [f"### {cid} (rerakonto: «{a}» kaj «{b}», la samaj linioj {', '.join('L' + str(n) for n in c['shared'])})", ""]
            out += [f"**En «{a}»:**", ""] + [p + "\n" for p in c["a"]] + [f"**En «{b}»:**", ""] + [p + "\n" for p in c["b"]]
        else:
            out += [f"### {cid} (nia dokumento, sekcio «{c['section']}»)", "", f"**La frazo:** {c['sentence']}", ""]
            for l in c["lines"]: out += [f"- *la linio:* {l}"]
            out.append("")
    return "\n".join(out)


def briefs(tag, limit=110_000):
    made = 0
    for d in sorted(glob.glob(os.path.join(SM, "*", f"S4-VIEW-{tag}.md"))):
        stem = d.split(os.sep)[-2]
        if stem == "collinson": continue
        h, r, g = candidates(stem, tag)
        items = [(f"H{i + 1}", "H", c) for i, c in enumerate(h)] + [(f"R{i + 1}", "R", c) for i, c in enumerate(r)] + [(f"G{i + 1}", "G", c) for i, c in enumerate(g)]
        if not items: continue
        chunks, cur = [], []
        for it in items:
            cur.append(it)
            if len(render(stem, tag, cur)) > limit: chunks.append(cur[:-1]); cur = [it]
        if cur: chunks.append(cur)
        name = re.sub(r"^#\s+|\s+—.*$", "", open(os.path.join(SM, stem, f"PROFILE-FROZEN-{tag}.md"), encoding="utf-8").readline()).strip()
        for k, ch in enumerate(chunks, 1):
            bp = os.path.join(SM, stem, f"REPAIR-BRIEF-{tag}-{k}.md")
            ret = os.path.join(SM, stem, f"REPAIR-RETURN-{tag}-{k}.md")
            if os.path.exists(bp): sys.exit(f"exists: {os.path.relpath(bp, G)}")
            open(bp, "x", encoding="utf-8").write(BRIEF.format(name=name, tag=tag, k=k, n=len(chunks), ret=ret, retname=os.path.basename(ret)) + "\n" + render(stem, tag, ch) + "\n")
            made += 1
            print(f"{os.path.relpath(bp, G)}: {len(ch)} candidates, {os.path.getsize(bp):,} bytes")
    print(made, "briefs")


def apply(stem, tag, write):
    """the readers' returns into S4-REPAIR-<tag>.tsv (old, new, candidate, verdict); then smelt-s4-view.py --replace applies them"""
    rows, bad = [], []
    for rp in sorted(glob.glob(os.path.join(SM, stem, f"REPAIR-RETURN-{tag}-*.md"))):
        t = open(rp, encoding="utf-8").read()
        for m in re.finditer(r"(?ms)^### ([HRG]\d+)\s*\n(.*?)(?=^### [HRG]\d+|\Z)", t):
            cid, b = m.group(1), m.group(2)
            v = (re.search(r"(?m)^verdikto:\s*(\S+)", b) or [None, ""])[1]
            old = re.search(r"(?ms)^malnova:\s*(.*?)\n(?=nova:)", b)
            new = re.search(r"(?ms)^nova:\s*(.*?)\n(?=kialo:|\Z)", b)
            if v in ("restas", "akceptebla") or not old: continue
            if not new: bad.append(cid); continue
            o, n = old.group(1).strip().strip("‹›"), new.group(1).strip().strip("‹›")
            if o and o != n: rows.append((o, n, f"{os.path.basename(rp)}:{cid}", v))
    out = os.path.join(SM, stem, f"S4-REPAIR-{tag}.tsv")
    print(f"{stem}: {len(rows)} replacements" + (f"; {len(bad)} with no «nova»: {', '.join(bad)}" if bad else ""))
    if write and rows:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("old\tnew\tcandidate\tverdict\n")
            for o, n, c, v in rows: fh.write("\t".join(x.replace("\t", " ").replace("\n", "\\n") for x in (o, n, c, v)) + "\n")
        print("written", os.path.relpath(out, G))


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "count": return count(a[1])
    if a[0] == "brief": return briefs(a[1])
    if a[0] == "apply": return apply(a[1], a[2], "--write" in a)
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
