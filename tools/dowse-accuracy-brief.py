#!/usr/bin/env python3
"""The accuracy check's brief, filled (2026-10-23; the editor: the steps run one after another by the runbook,
without the editor chasing them, and step 11 fixed on the earlier runs).

    tools/dowse-accuracy-brief.py <source> --date YYYY-MM-DD [--workflow]

Fills geniza/ocr/method/DOWSE-TEMPLATE-ACCURACY-BRIEF-EO-2026-10-23.md for the sample tools/dowse-accuracy-prep.py
wrote (dowse/<source>/accuracy-sample-<date>.md, refused if missing), and writes dowse/<source>/accuracy-brief-<date>.md
(create-only). The dating rules are a periodical's where the facts file dates lines by the issue (⟦la dato de la
numero⟧ in it), else a book's. «The list in force» is found by its heading. With --workflow, it also prints the reader
as one {label, prompt} object for tools/workflows/carney-readers.js. Ezri, 2026-10-23."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
TEMPLATE = os.path.join(G, "ocr", "method", "DOWSE-TEMPLATE-ACCURACY-BRIEF-EO-2026-10-23.md")
KINDS = os.path.join(G, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md")

PERIODICAL = ("(1) kie la pasaĝo donas neniun daton al la ago, la linio portas la daton de la numero de la gazeto, kun "
              "«⟦la dato de la numero⟧»: tio estas ĝusta, eĉ se la jaro ne staras en la pasaĝo; (2) kie la pasaĝo donas "
              "daton al la ago, aŭ la ago estas pli frua ol la numero, la linio devas porti tiun daton; (3) plano (`planita` "
              "en la speco) estas datita per la planita tago kun «☞», aŭ «dum aŭ post ‹la numero›☞»; (4) «interpreto» estas "
              "datita per la ago, kiun ĝi interpretas; (5) dato en vortoj («la pasintan vintron») en la data kampo estas eraro: «ne»; "
              # (2026-10-24; the editor: a real possibility of error remains; step 11's sample of the «konkludita» lines approved)
              "(6) «⟦la dato de la numero, konkludita⟧»: la pasaĝo ne datis la agon, kaj la projekto datis ĝin «dum aŭ antaŭ ‹la "
              "numero›» (plano: «dum aŭ post ‹la numero›☞»): «jes», se la ago okazis antaŭ aŭ dum la numero kaj la pasaĝo donas "
              "neniun pli precizan daton; «ne», se la ago estas ankoraŭ venonta (do «post»), aŭ se la pasaĝo ja donas daton al la "
              "ago (diru ĝin en la noto).")
BOOK = ("(1) la linio portas la daton, kiun la pasaĝo donas al la ago, aŭ «[sen dato]» / «[ĝenerala]», kie ĝi donas neniun; "
        "(2) «juĝo» aŭ «aserto» de la aŭtoro de la fonto, kiun la fonto ne datas, havas la jaron de la fonto mem, kun «⟦pruvo: "
        "la jaro de la fonto, …⟧»: tio estas ĝusta; (3) «interpreto» estas datita per la ago, kiun ĝi interpretas, ne per la "
        "diro: «[sen dato]» estas ĝusta, se la pasaĝo ne datas tiun agon (la jaro de la diro staras en «⟦interpretdato: …⟧»); "
        "(4) dato en vortoj en la data kampo estas eraro: «ne».")


def main():
    if len(sys.argv) < 2 or "--date" not in sys.argv: sys.exit(__doc__)
    src, date = sys.argv[1], sys.argv[sys.argv.index("--date") + 1]
    D = os.path.join(G, "dowse", src)
    sample = os.path.join(D, f"accuracy-sample-{date}.md")
    if not os.path.exists(sample): sys.exit(f"refused: no {os.path.relpath(sample, ROOT)} (tools/dowse-accuracy-prep.py {src} --date {date} first)")
    out = os.path.join(D, f"accuracy-brief-{date}.md")
    if os.path.exists(out):
        # --again: an untracked brief of this tool's written again (Ruslanda Esperantisto's of 2026-10-23, first taken for a book)
        tracked = os.system(f"git -C '{ROOT}' ls-files --error-unmatch '{out}' >/dev/null 2>&1") == 0
        if "--again" not in sys.argv or tracked: sys.exit(f"refused: {os.path.relpath(out, ROOT)} exists" + (" and is tracked" if tracked else " (--again rewrites it)"))
        os.replace(out, out + ".superseded")
    facts = open(os.path.join(G, "profiles", "by-source", f"{src}-dowse.md"), encoding="utf-8").read()
    # a periodical: its lines dated by the issue, or its settings dating or cutting by issue («dating», «journal»); Ruslanda
    # Esperantisto's facts file predates the ⟦la dato de la numero⟧ note (2026-10-23)
    bc = os.path.join(D, "brief-config.json")
    cfg = json.load(open(bc, encoding="utf-8")) if os.path.exists(bc) else {}
    periodical = "⟦la dato de la numero⟧" in facts or "dating" in cfg or "journal" in cfg
    ls = open(KINDS, encoding="utf-8").read().split("\n")
    a = next(i for i, l in enumerate(ls, 1) if l.startswith("## The list in force"))
    b = next((i for i, l in enumerate(ls, 1) if i > a and l.startswith("## ")), len(ls) + 1) - 1
    t = open(TEMPLATE, encoding="utf-8").read()
    body = t.split("## La briefo, kiel donita al la legilo", 1)[1]
    body = (body.replace("{fonto}", src).replace("{dato}", date).replace("{listo}", f"{a} ĝis {b}")
                .replace("{datoj}", PERIODICAL if periodical else BOOK))
    # the sample's own count: 40, and up to ten «konkludita» lines after them (dowse-accuracy-prep.py, 2026-10-24)
    nl = len(re.findall(r"^\d+\. \(linio \d+\)", open(sample, encoding="utf-8").read(), flags=re.M))
    body = body.replace("la 40 liniojn", f"la {nl} liniojn").replace("tabelo de 40 vicoj", f"tabelo de {nl} vicoj").replace("Fino: 40 linioj", f"Fino: {nl} linioj")
    head = (f"# La briefo por la kontrolo de precizeco: {src} ({date})\n\n"
            f"`[tools/dowse-accuracy-brief.py, from DOWSE-TEMPLATE-ACCURACY-BRIEF-EO-2026-10-23.md; the dating rules of a "
            f"{'periodical' if periodical else 'book'}; the dowse runbook D6c step 11.]`\n\n## La briefo, kiel donita al la legilo")
    with open(out, "x", encoding="utf-8") as fh: fh.write(head + body)
    print(f"wrote {os.path.relpath(out, ROOT)} ({'periodical' if periodical else 'book'})")
    if "--workflow" in sys.argv:
        print(json.dumps({"label": f"geniza/dowse/{src}/accuracy-return-{date}.md",
                          "prompt": f"ACCURACY-{src}-{date}. Read the brief at {out} (the section «La briefo, kiel donita al la legilo») "
                                    f"and do exactly what it says. Read tool only. Your report is your final message, ending with the line «Fino: {nl} linioj.»"},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
