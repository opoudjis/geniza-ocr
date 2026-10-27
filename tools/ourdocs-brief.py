#!/usr/bin/env python3
"""The our-documents pass, the briefs: one reader's brief for a group of our files, with the rules and, under each line,
the source the locating tool found and the page text cut around the name (the dowse runbook, D6, point 1; the editor,
2026-10-20, to the pass over the remaining files; the Henry Jacob test with the sources named: about 3,400 tokens a
line, against 19,000 without).

    tools/ourdocs-brief.py TAG N FILE.md [FILE.md ...]
        writes smelt/ourdocs/OURDOCS-BRIEF-TAG-N.md (create-only); the reader's return is filed as
        smelt/ourdocs/OURDOCS-RETURN-TAG-N.md and written into the files by tools/ourdocs-apply.py RETURN --write
        (the sections name their file: «### FILE.md l. N»).

The root document of a fold (named in its header, «`X.md` sits in the geniza root») is given to the reader for what the
document withdrew, superseded or corrected later. Lines already rewritten (a kind field and «reverkita 2026-10-20» or
«tradukita el la angla 2026-10-20») are listed as done. Ezri, 2026-10-20."""
import importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
BS = os.path.join(G, "profiles", "by-source")
_s = importlib.util.spec_from_file_location("ourdocs_locate", os.path.join(ROOT, "tools", "ourdocs-locate.py"))
OL = importlib.util.module_from_spec(_s); _s.loader.exec_module(OL)

RULES = """## La briefo

Vi reverkas faktoliniojn de esplora projekto pri la historio de la internaciaj helplingvoj. Uzu nur la ilon Read. Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn, skribu neniujn dosierojn. Via fina mesaĝo estas via raporto. Skribu ĝin en Esperanto.

**Kio estas tiuj linioj.** La projekto mem verkis ilin en septembro 2026, en siaj propraj dokumentoj (faldoj de niaj esploroj, verdiktoj de la redaktoro, analizoj), ne el unu fonto legita paĝon post paĝo. Ili estas nia terciara esploro pri la ĉefaj kaj duarangaj fontoj (la redaktoro, 2026-10-19). Por ĉiu linio:

1. **La lokindiko en la formo de ero:** `‹ŝlosilo›, PDF N` (konservita retpaĝo: `‹dosiernomo›, l. N`), la fonto, sur kiu la linio staras, ne la dokumento. Sub ĉiu linio sube staras la fonto, kiun la ilo trovis, kun ĝia ŝlosilo kaj paĝo kaj, kie eble, la teksto de la paĝo: kontrolu la fakton tie kaj prenu el ĝi la ankron, ses aŭ pli da vortoj laŭvorte (linirompo: « / »). Kie la ilo trovis nenion aŭ nur la verkon, serĉu en la nomita dosiero aŭ en la radika dokumento; kie la fonto ne estas sur disko (arkivoj, FindMyPast, libroj ne skanitaj), lasu la malnovan lokindikon kaj diru «la fonto ne estas legebla ĉi tie».
2. **Nia juĝo nur ene de ⟦…⟧,** aŭ, se la linio estas nur juĝo de ni, linio de speco `juĝo`, datita per la dato de la diro (la dato de la dokumento, se la linio ne donas alian), kun ✅ kaj ⟦nia juĝo, ‹dato›⟧, kaj la lokindiko de la dokumento mem (`‹dosiero sen .md›, l. N`). Juĝo, kiun la fonto kontraŭas: diru tion en la ⟦…⟧ kaj en la raporto. La steloj, ⇒, ⛔ kaj la majuskloj de emfazo ne estas faktoj: forigu ilin; kion ili diras pri graveco, iras en la juĝon, se entute.
3. **La verdiktoj de la redaktoro:** linioj de speco `juĝo`, datitaj per la dato de la verdikto, tradukitaj en Esperanton (la redaktoro); tiu, kiun posta verdikto anstataŭis, portas ⟦anstataŭita ‹dato›⟧.
4. **Unu fakto en unu linio; la speco** el «The list in force» de `{kinds}` (ankaŭ `rilato`, `distro`, `civito`; `samnomo` nur por samnomuloj tenataj aparte, ne por la agoj de parencoj); **la fakto en Esperanto**, ankaŭ kie la malnova linio estas angla; **la dato de la fakto**, kaj por aserto aŭ juĝo la dato de la diro; **la kapo** (`$$$ NOMO $$$ (kvalifiko)`) restas, krom se la fonto montras ĝin malĝusta.
5. **Serĉo, kiu trovis nenion:** ĝi ne estas fakto; se ĝi testas aserton, la linio havas la specon de la aserto kaj la etiketon ⟦nekonfirmo: ‹la fonto, kiel, kiam›⟧; se ĝi testas nenion, FORIGU (ĝi estas protokolo de nia esploro, kaj restas en la prozo de la dokumento).
6. **FORIGU** ankaŭ: duoblan linion (nomu tiun, kiu restas) kaj linion, kiun la dokumento mem retiris aŭ superis (nomu la lokon en la dokumento). **SAMA:** linio jam en la nova formo (ĝi havas specon kaj ⟦reverkita 2026-10-20⟧ aŭ ⟦tradukita el la angla 2026-10-20⟧): ne relegu ĝin.
7. **Neniam « · » ene de kampo** (ĝi estas la apartigilo de la kampoj): ene de fakto, ankro aŭ la etikedoj skribu «;» aŭ «,».

**La formo de linio:** `- $$$ NOMO $$$ (kvalifiko) **dato** · {{speco: objekto}} · fakto · ankro · lokindiko · [temoj] · voĉo (etikedoj)`, kiel en `{tpl}`, «La linio»; la temoj de la malnova linio restas.

**La formo de la raporto:** por ĉiu linio, laŭ ĝia dosiero kaj numero:

```
### ‹dosiero›.md l. 5
- ANSTATAŬIGU
- $$$ NOMO $$$ **…** · {{…}} · … · … · ‹ŝlosilo›, PDF N · [G] · 📣 (…)
### ‹dosiero›.md l. 6
- FORIGU (= l. 5)
### ‹dosiero›.md l. 7
- SAMA (kial)
```

Post ĉiuj linioj, mallonge: kiuj niaj juĝoj kontraŭas la fontojn; kio en la regulo ne funkciis. Fine, en du paŝoj: (1) la tuta raporto kiel unu mesaĝo; (2) en la sama mesaĝo, post la raporto, legu `{fino}` kaj respondu nur per la linio, kiun ĝi petas.
"""

def root_doc(path):
    head = open(path, encoding="utf-8").read(3000)
    m = re.search(r"`([A-Za-z0-9._-]+\.md)` sits in the geniza root", head)
    return os.path.join(G, m.group(1)) if m and os.path.exists(os.path.join(G, m.group(1))) else ""

def main():
    a = sys.argv[1:]
    if len(a) < 3: sys.exit(__doc__)
    tag, n, files = a[0], a[1], a[2:]
    d = os.path.join(G, "smelt", "ourdocs"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f"OURDOCS-BRIEF-{tag}-{n}.md")
    parts = [f"# La pasado de niaj propraj dokumentoj, grupo {n} ({tag})", "",
             f"`[tools/ourdocs-brief.py {tag} {n}: {len(files)} dosieroj; la fontoj trovitaj de tools/ourdocs-locate.py. La dowse-gvidlibro, D6, punkto 1.]`", "",
             RULES.format(kinds=os.path.join(G, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md"),
                          tpl=os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-FACTS-READING-BRIEF-EO-2026-10-13.md"),
                          fino=os.path.join(G, "dowse", "_FINO.txt")), "## La dosieroj kaj iliaj linioj", ""]
    total = done = 0
    for f in files:
        p = os.path.join(BS, os.path.basename(f))
        lines = open(p, encoding="utf-8").read().split("\n")
        rd = root_doc(p)
        parts += [f"### {os.path.basename(p)}", "", f"La dosiero: `{p}`." + (f" La radika dokumento: `{rd}`." if rd else ""), ""]
        for ln, who, r, lf, l in OL.locate(lines):
            total += 1
            if re.search(r"\{[^}]+\}", l.split(" · ")[1] if " · " in l else "") and re.search(r"reverkita 2026-10-20|tradukita el la angla 2026-10-20", l):
                done += 1; parts += [f"**l. {ln}** jam farita: SAMA.", ""]; continue
            src = f"{r[0]}" + (f": `{r[1]}`" if r[1] else "") + (f", {('PDF ' + r[2]) if r[2] and not r[2].startswith('l.') else r[2]}" if r[2] else "") + (f" — `{r[3]}`" if r[3] else "")
            parts += [f"**l. {ln}** ({src})", "", f"`{l[2:]}`", ""]
            if r[0] in ("item", "old", "alias", "same", "file", "web"):
                pt = OL.page_text(r[3], r[2] if r[2] and not r[2].startswith("l.") else "", who, width=10)
                if pt:
                    pt = "\n".join(pt.split("\n")[:30])
                    parts += ["```", pt, "```", ""]
    with open(out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"{os.path.relpath(out, ROOT)}: {len(files)} files, {total} lines ({done} done)")

if __name__ == "__main__":
    main()
