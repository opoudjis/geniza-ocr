#!/usr/bin/env python3
r"""ocr-rebuild-combined — rebuild each corpus's combined text from the ADJUDICATED per-page winner.

    tools/ocr-rebuild-combined.py <root> --verdicts OCR-PSM-VERDICTS.json

Takes the per-page verdicts from `ocr-psm-adjudicate.py` and assembles each corpus's `<stem>.txt`
from whichever reading won that page — a mosaic, not a wholesale swap. Writes a `CANONICAL.md`
beside it recording which recipe won where and why.

WHY REPLACING THE COMBINED FILE IS SAFE HERE, AND WHERE IT WOULD NOT BE.
The rule this project nearly broke itself on is that **a converted text which has been CITED is an
artefact of record and is never replaced in place**. That rule is about the project's cited OCR tree (not
published), where 22,257 fact-line locators point. It does not bind `ocr-rendersearch/`, which no finding
cites, which has been handed to nobody, and whose combined file is a DERIVED artefact: every
page survives on disk as `page-NNNN.txt` and `page-NNNN.psm4.txt`, so any previous combination is
reconstructible exactly. **Nothing here is lost; only the assembly changes.**

If this tool is ever pointed at a root that findings cite, that reasoning no longer holds and
the output belongs beside the original under a new name.

THE MOSAIC IS THE POINT. `--psm 4` won 3,852 pages and lost 4,073 — so neither recipe is right
for a corpus, and «convert the whole title at psm 4» would have been wrong about half the time.
The unit of the decision is the page, and this file is where that decision is written down.
"""
import os, re, sys, json, glob, argparse, collections, importlib.util
_s = importlib.util.spec_from_file_location("sm", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr-second-model.py"))
SM = importlib.util.module_from_spec(_s); _s.loader.exec_module(SM)   # best_merge(): one rule, two tools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr_russian_reading as RR   # the old-letter rule: `orus` or `rus` per page

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--dry-run", action="store_true")
    # write ONLY `ocr-preferred/<corpus>.txt` and `PREFERRED.tsv`, leaving the search text and CANONICAL.md untouched
    ap.add_argument("--preferred-only", action="store_true")
    a = ap.parse_args()

    v = json.load(open(a.verdicts, encoding="utf-8"))
    # page -> winner, keyed by (corpus, page number)
    win = {}
    for x in v:
        corpus, base = x["page"].split("/", 1)
        m = re.search(r"page-(\d+)", base)
        if m:
            win[(corpus, int(m.group(1)))] = x

    # THE TEXT LAYER'S KIND, PER PAGE (options 1 and 2 approved by the editor, 2026-09-30; an internal record, 2026-09-30, not published).
    # A page whose largest image covers < 50% of it carries BORN-DIGITAL text: its layer is the printed text (better or
    # as good as our OCR on 96% of sampled pages), so it joins the SEARCH text. On a SCAN (image ≥ 50%) the layer is a
    # library's OCR (ours better on 54%, theirs on 21%): it is NOT added to the search text, triangulation included.
    # Where adjudication CHOSE a scan's layer as the page's reading (26 Sep rule, «just another image»), that choice stands.
    tlk = os.path.join(os.path.dirname(os.path.abspath(a.root)), "ocr-text-layer-2026-09-30", "tl-kind.tsv")
    born = set()
    if os.path.exists(tlk):
        for l in open(tlk, encoding="utf-8"):
            x = l.rstrip("\n").split("\t")
            if len(x) >= 4 and float(x[3]) < 0.5:
                born.add((x[0], int(x[1])))

    # real words (3+ letters, in any lexicon) — the guard on the born-digital preferred reading (below)
    LEXW = set()
    for f_ in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicons", "*.txt")):
        LEXW |= {x.strip().lower() for x in open(f_, encoding="utf-8", errors="ignore") if x.strip()}
    RW = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

    def realwords(t):
        return sum(1 for x in RW.findall(t) if x.lower() in LEXW)

    corpora = sorted({c for c, _ in win})
    changed = tally = 0
    for corpus in corpora:
        d = os.path.join(a.root, corpus)
        pages = {}
        for f in sorted(glob.glob(os.path.join(d, "page-*.txt"))):
            # BASE pages only: the glob also matches the .psm4 / .hr readings of each page
            m = re.fullmatch(r"page-(\d+)\.txt", os.path.basename(f))
            if m:
                pages[int(m.group(1))] = f
        if not pages:
            continue
        rows, body, body_pref, prefrows = [], [], [], []
        rj = os.path.join(d, "RUSSIAN.json")
        russian = ({p["page"] for p in json.load(open(rj, encoding="utf-8"))["pages"]
                    if p["verdict"] == "accept"
                    and os.path.exists(os.path.join(d, f"page-{p['page']:04d}.rus.txt"))}
                   if os.path.exists(rj) else set())
        for n in sorted(pages):
            w = win.get((corpus, n))
            src = pages[n]
            recipe = "psm6"
            # winner ∈ psm6 · psm4 · hr6 · hr4 (hr = re-read at the text MASK's resolution)
            suf = {"psm4": ".psm4.txt", "hr6": ".hr.txt", "hr4": ".hr.psm4.txt", "tl": ".tl.txt"}
            emended_tl = False
            if w and w["winner"] in suf:
                alt = src[:-len(".txt")] + suf[w["winner"]]
                # an EMENDED born-digital layer (tools/ocr-tl-emend.py, editor 2026-09-30) stands in for the raw one
                if w["winner"] == "tl" and os.path.exists(src[:-len(".txt")] + ".tl-emended.txt"):
                    alt, emended_tl = src[:-len(".txt")] + ".tl-emended.txt", True
                if os.path.exists(alt):
                    src, recipe = alt, w["winner"]
                    tally += 1
            # A SECOND-MODEL MERGE (tools/ocr-second-model.py) for THIS page's chosen reading
            #   replaces it — never a merge made with a reading that is no longer chosen.
            arb, chain = SM.best_merge(pages[n][:-len(".txt")], recipe)
            if arb:
                src, recipe = arb, recipe + "+" + "+".join(chain)
            elif emended_tl:
                recipe += "+emended"
            # A RUSSIAN page (`tools/ocr-russian-pages.py`: Cyrillic that the Esperanto model misread
            # as Latin letters, re-read with the Russian model and ACCEPTED page by page in
            # `RUSSIAN.json`) takes the Russian reading whole. Blind look 2026-09-26: of 30 accepted
            # pages, 27 better, 3 the same, 0 worse (an internal record, 2026-09-26, not published).
            latin_src, latin_recipe = src, recipe      # kept for the PREFERRED text, where Latin has primacy (below)
            if n in russian:
                # which Russian reading: `orus` (pre-reform model) or `rus`, by the OLD-LETTER RULE
                # (the editor's ruling of 2026-09-28; tools/ocr_russian_reading.py)
                src = RR.russian_reading_path(pages[n])
                recipe = "orus" if src.endswith(".orus.txt") else "rus"
            # A RE-OCR (`page-NNNN.reocr.txt`, tools/ocr-reocr-best.py, on the editor's decision of 2026-09-27 to re-OCR the poor scans):
            # written ONLY where it scored better than the page as it stood; it outranks the OCR readings
            # and merges, but never an accepted Russian page, a ruled re-read or the editor's hand.
            reocr = pages[n][:-len(".txt")] + ".reocr.txt"
            if os.path.exists(reocr) and n not in russian:
                src, recipe = reocr, "reocr"
            # A VISION TRANSCRIPTION (`page-NNNN.vision.txt`, 2026-09-27, the editor's choice of options 1 and 3): a LOST page no OCR
            # variant recovered, transcribed from the image by an AI vision checker. Recipe «vision» — never
            # confused with the editor's hand. Outranks the OCR readings and accepted Russian; below ruled/hand.
            vision = pages[n][:-len(".txt")] + ".vision.txt"
            if os.path.exists(vision):
                src, recipe = vision, "vision"
            # A RULED re-read (`page-NNNN.ruled.txt`, tools/ocr-ruled-reread.py: the page read again as
            # the editor's G1 ruling directed — rotated, cropped, or at another layout mode) outranks
            # every OCR reading and merge; only the editor's own hand-keyed text outranks it.
            ruled = pages[n][:-len(".txt")] + ".ruled.txt"
            if os.path.exists(ruled):
                src, recipe = ruled, "ruled"
            # A HAND-KEYED reading (`page-NNNN.hand.txt`, the editor's transcription — G1 review,
            #   2026-09-26) outranks every OCR reading and every merge.
            hand = pages[n][:-len(".txt")] + ".hand.txt"
            if os.path.exists(hand):
                src, recipe = hand, "hand"
            text = open(src, encoding="utf-8", errors="ignore").read()
            # THE PREFERRED READING (the editor ruled 2026-09-30 that, when OCRs are handed over for inclusion in PDFs,
            # there must still be a preferred reading to inject into the PDF, and which reading is preferred must be
            # recoverable from the files). The SEARCH text may hold two readings of the same print; the PREFERRED text holds one:
            # the chosen reading, plus the SUPPLEMENTS (hand-add, vision-add: lines the reading lost, not a second
            # reading). A boosted second reading replaces it as preferred only where it was CLEARLY better, marked on
            # disk by `page-NNNN.boost-preferred` (≥ 20 known long words and ≥ twice the base's); otherwise it serves
            # search only. Written per corpus: `ocr-preferred/<corpus>.txt` (a tree beside the search tree) and `<corpus>/PREFERRED.tsv`.
            pref_base, pref_recipe, supp = text, recipe, []
            pref_src = src
            # OTHER SCRIPTS (the editor ruled 2026-09-30 that Latin script has primacy, these being Esperanto
            # publications, and that a single file with both scripts is still the ideal): where an accepted Russian reading took the page in the SEARCH text, the
            # PREFERRED text keeps the Latin reading, and PREFERRED.tsv names the Russian file as the second script.
            # A single text with both scripts in place is the ideal, not yet built.
            second_script = ""
            if recipe in ("rus", "orus"):
                pref_base = open(latin_src, encoding="utf-8", errors="ignore").read()
                pref_recipe, pref_src, second_script = latin_recipe + " (Latin primary)", latin_src, os.path.basename(src)
            # A HAND-KEYED ADDITION (`page-NNNN.hand-add.txt`): the editor typed only the part of
            # the page the OCR lost (a framed paragraph, speech balloons). It is APPENDED to the
            # chosen reading, so what the OCR did read is kept.
            add = pages[n][:-len(".txt")] + ".hand-add.txt"
            if os.path.exists(add):
                text = text.rstrip("\n") + "\n" + open(add, encoding="utf-8", errors="ignore").read()
                recipe += "+hand-add"
                supp.append(("hand-add", add))
            # A VISION ADDITION (`page-NNNN.vision-add.txt`, 2026-09-27, mastheads approved by the editor):
            # the lines an image sort judged MINOR-missing (masthead, title, caption, stamp), transcribed
            # from the image by an AI vision checker and APPENDED like a hand-add. Never over the editor's
            # hand: skipped where the page is hand-keyed or already has a hand-add.
            vadd = pages[n][:-len(".txt")] + ".vision-add.txt"
            if os.path.exists(vadd) and recipe.split("+")[0] != "hand" and "+hand-add" not in recipe:
                text = text.rstrip("\n") + "\n" + open(vadd, encoding="utf-8", errors="ignore").read()
                recipe += "+vision-add"
                supp.append(("vision-add", vadd))
            # A BOOSTED SECOND READING (`page-NNNN.boost-add.txt`, 2026-09-30, approved by the editor; tools/ocr-lost-reread.py,
            # docs/FAILURE-MAP.md row 4): the page read again from a contrast-boosted, sharpened image, filed
            # only where it held clearly more real words than the text a search reads. APPENDED, not substituted:
            # the chosen reading (often column-aware) keeps what it has, and a search finds a name in either.
            # Never over the editor's hand, a ruled re-read or a vision transcription (those are complete readings).
            badd = pages[n][:-len(".txt")] + ".boost-add.txt"
            if os.path.exists(badd) and recipe.split("+")[0] not in ("hand", "ruled", "vision"):
                text = text.rstrip("\n") + "\n" + open(badd, encoding="utf-8", errors="ignore").read()
                recipe += "+boost-add"
                if os.path.exists(pages[n][:-len(".txt")] + ".boost-preferred"):
                    pref_base, pref_recipe = open(badd, encoding="utf-8", errors="ignore").read(), "boost"
            # TRIANGULATION, on the PARTLY-READ pages only (those with a boosted addition; approved by the editor
            # 2026-09-30, on condition that it be got right in isolation): the SEARCH text also carries EVERY OTHER stored reading of the page
            # — psm6/psm4, the high-resolution re-reads, the PDF's own text layer, the layout reading, the merges, the
            # boosted reading where a vision transcription took the page — because a blind check found text missing
            # from the search text that sat only in `tl` or `layout` (docs/FAILURE-MAP.md row 4). Search only:
            # the PREFERRED reading is unchanged.
            if os.path.exists(badd):
                stem = pages[n][:-len(".txt")]
                used = {os.path.abspath(src), os.path.abspath(badd) if "+boost-add" in recipe else ""} | \
                       {os.path.abspath(f) for _, f in supp}
                skip = (".eo-gate.txt", ".eo-clean.txt", ".ru-clean.txt", ".rus.txt", ".orus.txt", ".vision.txt",
                        ".hand.txt", ".hand-add.txt", ".ruled.txt", ".vision-add.txt")
                others = [f for f in sorted(glob.glob(stem + ".*.txt")) + [pages[n]]
                          if os.path.abspath(f) not in used and not f.endswith(skip)
                          and not (f.endswith(".tl.txt") and ((corpus, n) not in born   # no scan OCR layer (above);
                                   or os.path.exists(f[:-len(".tl.txt")] + ".tl-emended.txt")))   # the emended one stands in
                          and not (f.endswith(".tl-emended.txt") and (corpus, n) not in born)]
                seen = set()
                for f in others:
                    t_ = open(f, encoding="utf-8", errors="ignore").read()
                    if t_.strip() and t_ not in seen:
                        seen.add(t_); text = text.rstrip("\n") + "\n" + t_
                if seen:
                    recipe += f"+{len(seen)}-other-readings"
            # A BORN-DIGITAL page's own text layer joins its SEARCH text (see `born`, above); never twice, never
            # when it is already the chosen reading. The EMENDED layer (`page-NNNN.tl-emended.txt`) stands in for the raw one.
            tlf = pages[n][:-len(".txt")] + ".tl-emended.txt"
            if not os.path.exists(tlf):
                tlf = pages[n][:-len(".txt")] + ".tl.txt"
            if (corpus, n) in born and os.path.exists(tlf) and os.path.abspath(tlf) != os.path.abspath(src):
                t_ = open(tlf, encoding="utf-8", errors="ignore").read()
                if t_.strip() and t_ not in text:
                    text = text.rstrip("\n") + "\n" + t_
                    recipe += "+tl-born"
            # THE COLUMN-BY-COLUMN LAYOUT READING (`page-NNNN.layout.txt`, tools/ocr-layout-mixed.py, 27–28 Sep) and the
            # SMALL-CAPS RE-READ (`page-NNNN.sc3x.txt`, 3× Tesseract, 2026-09-30) join the SEARCH text of EVERY page that has
            # one — search only; the PREFERRED reading is unchanged. FIXED 2026-09-30 23:0x: the layout reading had joined
            # search only on the partly-read pages (triangulation, above), so on the 2,913 pages that have one, 16,232 real
            # Esperanto words it holds were in no searched text (the editor directed that the gap be plugged).
            for kind in ("layout", "sc3x"):
                xf = pages[n][:-len(".txt")] + f".{kind}.txt"
                if os.path.exists(xf) and os.path.abspath(xf) != os.path.abspath(src):
                    t_ = open(xf, encoding="utf-8", errors="ignore").read()
                    if t_.strip() and t_ not in text:
                        text = text.rstrip("\n") + "\n" + t_
                        recipe += f"+{kind}-search"
            # WHERE THE PREFERRED READING IS THE PDF'S OWN TEXT LAYER, OUR OWN OCR JOINS SEARCH TOO (2026-10-02, the G5
            # final: britaesperantisto 1911 n080 p.7 — the ANNO text layer held 3 of the 6 names the judge saw, our own
            # psm6 reading all 6, and only the layer was searched). 3,612 pages in 801 absence-class items prefer the layer;
            # on 2,435 our reading holds >30% word forms the layer lacks. Search only — the layer stays the preferred,
            # citation text. The same gap as the layout readings above (the editor directed on 2026-09-30 that it be plugged).
            if os.path.basename(src).endswith(".tl.txt"):
                for xf in (pages[n], pages[n][:-len(".txt")] + ".psm4.txt"):
                    if os.path.exists(xf) and os.path.abspath(xf) != os.path.abspath(src):
                        t_ = open(xf, encoding="utf-8", errors="ignore").read()
                        if t_.strip() and t_ not in text:
                            text = text.rstrip("\n") + "\n" + t_
                            recipe += "+own-ocr-search"
            # ON A BORN-DIGITAL PAGE THE (EMENDED) LAYER IS THE PREFERRED READING (the editor ruled 2026-09-30 that the
            # born-digital layer, once emended, is clearly more authoritative; sample: better than our OCR on 38% of pages, worse on 4%).
            # Not over the editor's hand, a ruled re-read or a vision transcription; a blank marker (below) still wins.
            # It carries every script as printed, so no second script is named.
            # GUARD (2026-09-30 16:1x): only where the layer holds at least 90% of the chosen reading's real words.
            # Ledger 30i showed a layer can hold a fragment of the print: *Diskuto pri 'garsono'* p.1 held 7 real
            # words against our OCR's 175, and taking it as preferred threw the text away. 626 of 26,105 born-digital
            # pages (2.4%) fail the guard and keep our reading as preferred; their layer still joins the search text.
            if (corpus, n) in born and os.path.exists(tlf) and recipe.split("+")[0] not in ("hand", "ruled", "vision"):
                t_ = open(tlf, encoding="utf-8", errors="ignore").read()
                ours = realwords(pref_base)
                if t_.strip() and not (ours >= 20 and realwords(t_) < 0.9 * ours):
                    pref_base, pref_src, second_script = t_, tlf, ""
                    pref_recipe = "tl-born" + ("+emended" if tlf.endswith(".tl-emended.txt") else "")
            pref_files = [os.path.basename(badd) if pref_recipe == "boost" else os.path.basename(pref_src)]
            pref = pref_base
            for kind, f in supp:
                pref = pref.rstrip("\n") + "\n" + open(f, encoding="utf-8", errors="ignore").read()
                pref_recipe += "+" + kind; pref_files.append(os.path.basename(f))
            # A PAGE JUDGED BLANK (`page-NNNN.blank`; the editor ruled 2026-09-30 that a page decided as blank is to be
            # blank, rather than garbage characters being asserted as its content): the PREFERRED reading is empty, so no
            # show-through or OCR noise is handed over as the page's text. The SEARCH text keeps every reading.
            if os.path.exists(pages[n][:-len(".txt")] + ".blank"):
                pref, pref_recipe, pref_files = "", "blank", [os.path.basename(pages[n][:-len(".txt")] + ".blank")]
            body_pref.append(f"\n=== page {n} ===\n" + pref)
            prefrows.append((n, pref_recipe, " + ".join(pref_files), second_script, recipe))
            body.append(f"\n=== page {n} ===\n" + text)
            if w:
                rows.append((n, recipe, w["why"], w["entries_psm6"],
                             w.get("entries_" + recipe.split("+")[0], w["entries_psm4"])))
        out = os.path.join(a.root, corpus + ".txt")
        if not a.dry_run:
            # in a tree of its OWN, beside the search tree, so no search over `<root>/*.txt` meets a page twice
            proot = os.path.join(os.path.dirname(os.path.abspath(a.root).rstrip("/")), "ocr-preferred")
            os.makedirs(proot, exist_ok=True)
            open(os.path.join(proot, corpus + ".txt"), "w", encoding="utf-8").write("".join(body_pref))
            with open(os.path.join(d, "PREFERRED.tsv"), "w", encoding="utf-8") as pf:
                pf.write("page\tpreferred\tfiles\tsecond_script\tsearch_text_recipe\n")
                pf.writelines(f"{n}\t{pr}\t{fs}\t{ss}\t{sr}\n" for n, pr, fs, ss, sr in prefrows)
        if a.preferred_only:
            changed += 1
            continue
        if not a.dry_run:
            open(out, "w", encoding="utf-8").write("".join(body))
            c = [f"# CANONICAL — which reading is in the combined text, per page\n",
                 "**GENERATED by `tools/ocr-rebuild-combined.py`. Do not hand-edit — re-run it.**\n",
                 f"`{corpus}` · {len(pages)} pages · "
                 f"{sum(1 for r in rows if r[1]=='psm4')} read at `--psm 4` · "
                 f"{sum(1 for r in rows if r[1] in ('hr6','hr4'))} re-read at the text mask's resolution.\n",
                 "⚠ **This corpus's combined text is a MOSAIC.** `--psm 4` is right for a list page "
                 "and wrong for a prose one, and across the corpus it won barely half the pages, so "
                 "neither recipe was applied wholesale. Each page carries the reading that measured "
                 "better ON THAT PAGE: more complete entry-form lines first, then more RECOGNISED "
                 "WORDS by a clear margin, and the `--psm 6` incumbent held where they tied.\n",
                 "⊕ Every reading remains on disk — `page-NNNN.txt` (psm6), `.psm4.txt`, and where "
                 "the page has a sharp text mask `.hr.txt` / `.hr.psm4.txt` (hr6 / hr4). "
                 "Nothing was discarded; only the assembly changed.\n",
                 "| page | reading | decided by | entries psm6 | entries chosen |",
                 "|---:|---|---|---:|---:|"]
            for n, recipe, why, e6, e4 in rows:
                mark = f"**{recipe}**" if recipe != "psm6" else "psm6"
                c.append(f"| {n} | {mark} | {why} | {e6} | {e4} |")
            open(os.path.join(d, "CANONICAL.md"), "w", encoding="utf-8").write("\n".join(c) + "\n")
        changed += 1
    print(f"{changed} corpora rebuilt · {tally:,} pages took a reading other than psm 6"
          + (" (DRY RUN — nothing written)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
