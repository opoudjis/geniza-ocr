#!/usr/bin/env python3
r"""smelt_pieces.py — a smelt reader writes its report to files in pieces, not in its final message (the pilot,
2026-10-30: three readers, Bourlet's S3 parts 1 and 3 and Beauchemin's single S4 writer, cut off at their output limit
and refused; the limit is one response's output, the reader's thinking in it too, so no count of the input predicts it;
the editor). Each piece is one Write, one response; the final message is only the report's
last line.

    python3 tools/smelt_pieces.py brief BRIEF RETURN     # an existing brief told to write RETURN in pieces (in place)
    python3 tools/smelt_pieces.py join RETURN            # the pieces joined as RETURN, create-only
    python3 tools/smelt_pieces.py copy BRIEF NEW_BRIEF NEW_RETURN [--warm]
                                                         # a brief in pieces copied for another return (create-only);
                                                         # --warm: the pieces written as the work goes (WARM), for
                                                         # an older brief; add() writes WARM into every brief now

As a module: `add(brief_text, return_path)` -> the brief told to write in pieces (smelt-compress.py --brief and
--s3-parts, smelt-periods.py --s4). The pieces are `<RETURN stem>.piece-01.md`, `-02`, …, beside RETURN; they stay on
disk after the join, as the record of what the reader wrote. Launch such a reader as file-reader-writer, with «Your final
message is the line the brief asks for.» in place of «… the report it asks for.».
Ezri, 2026-10-30."""
import os, re, sys

MARK = "## Kiel skribi la raporton: en pecoj"
# the tool lines of the S3 and S4 templates (smelt-s2-prep.py), each replaced by its Read-and-Write form
TOOLS = [("Uzu nur la ilon Read. Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn, skribu neniujn dosierojn. Via "
          "fina mesaĝo estas via raporto.",
          "Uzu nur la ilojn Read kaj Write. Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn, kaj skribu neniujn "
          "dosierojn krom la pecoj de via raporto (vidu «Kiel skribi la raporton», fine). Via raporto estas en tiuj pecoj; via "
          "fina mesaĝo estas nur ĝia lasta linio."),
         ("Ne rulu ŝelajn komandojn, ne faru retajn serĉojn, ne skribu dosierojn. Via fina mesaĝo estas via raporto.",
          "Uzu nur la ilojn Read kaj Write. Ne rulu ŝelajn komandojn, ne faru retajn serĉojn, kaj skribu neniujn dosierojn "
          "krom la pecoj de via raporto (vidu «Kiel skribi la raporton», fine). Via raporto estas en tiuj pecoj; via fina "
          "mesaĝo estas nur ĝia lasta linio.")]
PIECE = re.compile(r"\.piece-(\d\d)\.md$")


def piece(ret, n): return re.sub(r"\.md$", f".piece-{n:02d}.md", ret)


# THE EDITOR'S DATED QUOTATIONS OUT OF THE READERS' COPIES (2026-11-10; the editor's to Fable's proposal 6): a bracket
# that holds «la redaktoro, ‹date›» and a «…» quotation, nothing nested; the rule's own sentence outside it stays as written
QUOTE = re.compile(r" ?\((?P<pre>[^()«»]*?;\s*)?(?:la redaktoro|the editor)[^()«»]*?\d{4}-\d{2}-\d{2}[^()«»]*?«[^«»]*»(?:[^()«»]*?«[^«»]*»)*[^()«»]*\)")
def unquote(b):
    """the brief less its bracketed quotations of the editor, and how many; what a bracket holds before «; la redaktoro, …»
    (a rule's examples) stays, in its brackets"""
    n = len(QUOTE.findall(b))
    return QUOTE.sub(lambda m: f" ({m.group('pre').rstrip('; ')})" if m.group("pre") and m.group("pre").strip("; ") else "", b), n

def add(b, ret):
    if MARK in b: sys.exit(f"refusing: the brief for {os.path.basename(ret)} says «{MARK}» already")
    b, nq = unquote(b)
    if nq: print(f"  {os.path.basename(ret)}: {nq} of the editor's dated quotations left out of the reader's copy")
    for old, new in TOOLS:
        if old in b: b = b.replace(old, new, 1); break
    else: sys.exit("refusing: the brief has neither template's tool line")
    return b.rstrip("\n") + (
        f"\n\n{MARK}\n\n"
        "Ne skribu la raporton en via fina mesaĝo: tuta raporto estas tro longa por unu respondo, kaj legilo, kiu haltas ĉe la "
        "limo de sia eligo, ne estas akceptata (la piloto, 2026-10-30). **Skribu ĝin per la ilo Write, en pecoj, laŭ ordo:**\n\n"
        f"- `{piece(ret, 1)}`\n- `{piece(ret, 2)}`\n- kaj tiel plu (`.piece-03.md`, `.piece-04.md` …).\n\n"
        "Unu peco estas unu sekcio de la raporto; longan sekcion (la epizodojn, la biografion, la grupojn) dividu en pecojn de "
        "ĉirkaŭ 15 epizodoj, sekcioj aŭ grupoj, ne pli ol ĉirkaŭ 20 000 signoj. Ĉiu peco daŭrigas la antaŭan: la titolo de "
        "sekcio (`## 1. …`) staras nur en la peco, kie la sekcio komenciĝas, kaj ĉio estas en la ordo kaj la formo, kiujn "
        "la briefo donas por la raporto. Skribu ĉiun pecon unufoje, kiam ĝi estas preta; reskribu pecon nur por ripari ĝin. "
        + WARM.strip("\n") + " "
        "**La lasta peco finiĝas per la fina linio de la raporto**, kiun la briefo donas («Fino…»). **Via fina mesaĝo estas nur "
        "tiu linio.** Ilo kunmetas la pecojn laŭ ilia numero.\n")


# THE CACHE KEPT WARM (the Devjatnin test, 2026-10-30: a writer in pieces thought 740 seconds in one call before its
# first piece; the cache lives 5 minutes, so the next call wrote the whole context again, 274,544 tokens; the weighted
# bill rose 24%; the editor): the pieces written as the work goes, a few minutes' thought each.
# The first piece a single section (the warm test, 2026-10-30 15:5x: ruled by the editor still took 376 seconds
# and one rewrite of 234,789; the editor), and in every brief, by add()
WARM = ("\n**Skribu la pecojn dum vi laboras, ne post longa planado** (la provo ĉe Devjatnin, 2026-10-30: verkanto, kiu "
        "pensis 12 minutojn antaŭ sia unua peco, pagis sian tutan legadon duoble, ĉar la kaŝmemoro vivas nur 5 minutojn): "
        "legu ĉiujn dosierojn, poste pripensu **nur la unuan sekcion** kaj skribu ĝin, kaj nur ĝin, kiel la unuan pecon, "
        "ene de kelkaj minutoj; poste la sekvajn. Inter du pecoj neniam pensu pli ol kelkajn minutojn. La planon de la tuto "
        "vi ne bezonas fini antaŭ la unua peco: la ordon kaj la sekciojn donas la briefo.\n")

def copy(brief, new_brief, new_ret, warm=False):
    """A brief told to write in pieces, copied with its pieces renamed for another return (a test beside the run)."""
    b = open(brief, encoding="utf-8").read()
    if MARK not in b: sys.exit(f"refusing: {os.path.basename(brief)} does not write in pieces")
    m = re.search(r"`([^`]+)\.piece-01\.md`", b)
    if not m: sys.exit(f"refusing: no first piece named in {os.path.basename(brief)}")
    b = b.replace(m.group(1) + ".piece-", re.sub(r"\.md$", "", new_ret) + ".piece-")
    if warm and WARM.strip("\n") not in b:   # a brief made by add() since 2026-10-30 16:0x has it already
        b = b.replace("**La lasta peco finiĝas", WARM.strip("\n") + " **La lasta peco finiĝas", 1)
    with open(new_brief, "x", encoding="utf-8") as fh: fh.write(b)
    print(f"{os.path.basename(new_brief)}: {os.path.basename(new_ret)} in pieces" + (", the cache kept warm" if warm else ""))

def join(ret, by="smelt_pieces.py join"):
    d, base = os.path.dirname(ret), os.path.basename(ret)
    if os.path.exists(ret): sys.exit(f"refusing: {base} exists")
    stem = re.sub(r"\.md$", "", base)
    ps = sorted((f for f in os.listdir(d) if f.startswith(stem + ".piece-") and PIECE.search(f)), key=lambda f: int(PIECE.search(f).group(1)))
    if not ps: sys.exit(f"refusing: no pieces of {base}")
    nums = [int(PIECE.search(f).group(1)) for f in ps]
    if nums != list(range(1, len(ps) + 1)): sys.exit(f"refusing: the pieces of {base} are numbered {nums}, not 1 to {len(ps)}")
    texts = [open(os.path.join(d, f), encoding="utf-8").read().strip("\n") for f in ps]
    last = [l for l in texts[-1].split("\n") if l.strip()][-1]
    if not last.startswith("Fino"): sys.exit(f"refusing: the last piece of {base} does not end with the line «Fino…» (it ends «{last[:80]}»)")
    body = "\n\n".join(texts)
    with open(ret, "x", encoding="utf-8") as fh:
        fh.write(f"# Return: {base}\n\n`[Filed by Ezri: joined from the {len(ps)} pieces the reader wrote ({by})]`\n\n{body}\n")
    print(f"{base}: {len(ps)} pieces, {len(body)} chars; the last line «{last[:80]}»")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "brief":
        p, ret = sys.argv[2], os.path.abspath(sys.argv[3])
        b = add(open(p, encoding="utf-8").read(), ret)
        open(p, "w", encoding="utf-8").write(b)
        print(f"{os.path.basename(p)}: told to write {os.path.basename(ret)} in pieces")
    elif len(sys.argv) in (5, 6) and sys.argv[1] == "copy":
        copy(sys.argv[2], sys.argv[3], os.path.abspath(sys.argv[4]), "--warm" in sys.argv)
    elif len(sys.argv) == 3 and sys.argv[1] == "join":
        join(os.path.abspath(sys.argv[2]))
    else:
        sys.exit(__doc__)
