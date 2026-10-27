#!/usr/bin/env python3
"""Smelt S4b: the polish pass after S4 (the smelt runbook, S4, «a polish pass after S4»; the editor, 2026-10-19, 16:38). One reader rewrites the biography's part (1) and changes nothing but three things: a
translation in square brackets after each quotation not in Esperanto, a paragraph break where the theme shifts, and the
titles of periodicals and books in italics. A tool check then refuses any other change.

    tools/smelt-polish.py <stem> <tag> --prep     smelt/<stem>/S4-POLISH-BRIEF-<tag>.md (create-only)
    tools/smelt-polish.py <stem> <tag> --check    the filed smelt/<stem>/S4-POLISH-RETURN-<tag>.md against the part (1)
    tools/smelt-polish.py <stem> <tag> --apply    the check, then part (1) of S4-RETURN-<tag>.md replaced by the return;
                                                  the return before it kept as S4-RETURN-<tag>-unpolished.md (create-only)

The check: with every «*», every square bracket that is not a citation ([L12, L45]) and all spacing taken out, the
return's text equals the original's; the citations and the note markers (¹ ² …, [1] …) are the same, in the same
order. Then smelt-s4-view.py --replace and fact-labels.py as after any S4. Ezri, 2026-10-19."""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

BRIEF = """# La polura legado (smelt S4b): {stem} ({tag})

`[tools/smelt-polish.py --prep: la parto (1) de la biografio, {n} linioj. La smelt-gvidlibro, S4, «a polish pass after S4».]`

## La briefo

Vi poluras biografion de esplora projekto pri la historio de la internaciaj helplingvoj. Uzu nur la ilon Read. Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn, skribu neniujn dosierojn. Via fina mesaĝo estas via raporto.

**La teksto:** `{path}`, de la linio «## 1. La resumo kaj la biografio» ĝis la linio antaŭ «## 2.» (linioj {a}–{b}). Legu ĝin tutan.

**Faru nur tri aferojn, nenion alian:**

1. **Tradukoj.** Post ĉiu citaĵo en alia lingvo ol Esperanto (franca, angla, Ido, Occidental, latina …), ankaŭ post titolo de artikolo, aldonu ĝian tradukon en Esperanto inter rektaj krampoj, tuj post la fermaj «»: «is nothing but a language» [estas nenio alia ol lingvo]. Ne traduku la titolojn de periodaĵoj kaj libroj, nek la nomojn de personoj, lokoj, kluboj kaj korpoj, nek mallongajn vortojn, kiujn la frazo jam klarigas. Citaĵon en Esperanto ne tuŝu. La traduko estas fidela kaj simpla; kie la citaĵo estas fragmento, ankaŭ la traduko.
2. **Alineoj.** Kie alineo ŝanĝas temon interne (nova afero, nova jaro de alia afero, nova rolo), dividu ĝin tie per malplena linio; iom pli ofte ol la verkinto, sed ne ĉiun frazon: alineo de unu frazo nur kie la temo vere staras sola. Neniam dividu frazon, neniam movu frazon, neniam kunigu alineojn.
3. **Kursivo.** La titoloj de periodaĵoj kaj de libroj kursive: *La Lumo*, *La Presse*, *Lingvo Internacia*, *Biographies canadiennes-françaises*, *Enciklopedio de Esperanto*, *Ora Libro*. Ne la nomoj de kluboj kaj korpoj: la klubo Progreso, sed la revuo *Progreso*; la lingvo Ido, sed la revuo *Ido* (Zürich). En la kursivaj resumoj (la tuta alineo inter *…*), la titolo reiras al rekta skribo: `*… en* La Lumo *…*`.

**Ŝanĝu neniun vorton, neniun citaĵon de linioj** («[L12, L45]»), **neniun supraskribitan ciferon** (¹ ²), neniun markon (= ∴ ◊? ⚫️), neniun titolon de sekcio. Ilo komparas vian tekston kun la originalo: krom la steletoj (*), la novaj rektaj krampoj kaj la spacoj, ĝi devas esti la sama, litero post litero; alie ĝi estas rifuzita.

**La formo de la raporto:** la tuta parto (1), de «## 1. La resumo kaj la biografio» ĝis la fino de la parto, poluita, sen io antaŭ ĝi; poste unu linio «Fino.». Nenion alian.
"""

def part1(text):
    lines = text.split("\n")
    a = next(i for i, l in enumerate(lines) if l.startswith("## 1."))
    b = next((i for i, l in enumerate(lines) if i > a and re.match(r"^## \d", l)), len(lines))
    return lines, a, b

def norm(s):
    s = re.sub(r"\[(?!L\d)[^\]]*\]", "", s.replace("*", ""))
    return re.sub(r"\s+", "", s)

def marks(s):
    return re.findall(r"\[L\d[^\]]*\]|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|(?<![L\w])\[\d{1,2}\]", s)

def main():
    a = sys.argv[1:]
    if len(a) != 3 or a[2] not in ("--prep", "--check", "--apply"):
        sys.exit(__doc__)
    stem, tag, act = a
    d = os.path.join(G, "smelt", stem)
    ret = os.path.join(d, f"S4-RETURN-{tag}.md")
    lines, i, j = part1(open(ret, encoding="utf-8").read())
    if act == "--prep":
        out = os.path.join(d, f"S4-POLISH-BRIEF-{tag}.md")
        with open(out, "x", encoding="utf-8") as fh:
            fh.write(BRIEF.format(stem=stem, tag=tag, n=j - i, path=ret, a=i + 1, b=j))
        print(f"{out}: part (1), lines {i + 1}–{j}")
        return
    pol = open(os.path.join(d, f"S4-POLISH-RETURN-{tag}.md"), encoding="utf-8").read().split("\n")
    k = next(n for n, l in enumerate(pol) if l.startswith("## 1."))
    pol = pol[k:]
    while pol and pol[-1].strip() in ("", "Fino."):
        pol.pop()
    orig, new = "\n".join(lines[i:j]), "\n".join(pol)
    bad = []
    if norm(orig) != norm(new):
        x, y = norm(orig), norm(new)
        p = next((n for n in range(min(len(x), len(y))) if x[n] != y[n]), min(len(x), len(y)))
        bad.append(f"the text differs at character {p}: «…{x[max(0, p - 60):p + 60]}…» against «…{y[max(0, p - 60):p + 60]}…»")
    if marks(orig) != marks(new):
        bad.append(f"citations or note markers differ: {len(marks(orig))} against {len(marks(new))}")
    tr = re.findall(r"\[(?!L\d)[^\]]*\]", new.replace("[sen dato]", ""))
    paras = lambda s: len([p for p in re.split(r"\n\s*\n", s) if p.strip()])
    print(f"{stem} {tag}: translations {len(tr)}; paragraphs {paras(orig)} → {paras(new)}; italic marks {orig.count('*')} → {new.count('*')}")
    if bad:
        sys.exit("REFUSED: " + "; ".join(bad))
    print("check: the same text, citations and markers")
    if act == "--apply":
        keep = os.path.join(d, f"S4-RETURN-{tag}-unpolished.md")
        with open(keep, "x", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        with open(ret, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines[:i] + pol + [""] + lines[j:]))
        print(f"wrote {ret} (the return before it: {keep})")

if __name__ == "__main__":
    main()
