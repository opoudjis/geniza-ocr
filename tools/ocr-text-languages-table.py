#!/usr/bin/env python3
r"""ocr-text-languages-table — THE LANGUAGE TABLE: every language each text prints, every script, with its evidence.

    tools/ocr-text-languages-table.py <evidence.tsv> <look-evidence.tsv> --out <tsv>
    e.g. (from geniza/) ../../../tools/ocr-text-languages-table.py OCR-TEXT-LANGUAGES-EVIDENCE-2026-10-03.tsv \
         OCR-TEXT-LANGUAGES-LOOK-EVIDENCE-2026-10-03.tsv --out OCR-TEXT-LANGUAGES-2026-10-03.tsv

WHY (the editor's ruling, 2026-10-03): a table mapping texts to the languages they contain should have acted as a
filter; it needs entries for Russian, Greek, Georgian and Armenian, and must track every language; and the other-script
languages (Ukrainian, Georgian, Armenian, Greek) were to be done at once. The gate's `all_seconds` held Latin-script languages only, so the
28 Sep Cyrillic chain (keyed on script detection alone) read Greek, Ido and Latin headings as Russian.
SCRIPT and LANGUAGE are separate fields (Hebrew, raised by the editor on 2026-10-03: *Posta Mundi* 20 prints Ido in Hebrew letters).

SOURCES, per language, in the `evidence` column:
  gate      the gate's primary language and `all_seconds` (Latin script; detected or declared)
  look:N    N pages where a blind look (26 Sep – 1 Oct) saw it (OCR-TEXT-LANGUAGES-LOOK-EVIDENCE; report beside it)
  auth:N    N pages whose authoritative readings (hand, vision, text layer) print its script / its marker letters
  lex:N     N pages whose Russian-model reading has >= 15 Russian-list words (Russian only)
  mask      the item's MASK-KATHYE.json (Georgian/Armenian masking, 27 Sep)
  ruling    an editor's ruling (ocr-absence-ledger.py PRESENCE_ONLY_NAMED: Greek)
RULES (non-Latin): russian ⇐ look, or lex >= 5, or lex >= 1 with Cyrillic in an authoritative reading, or pre-reform /
ы э letters in one; ukrainian ⇐ look, or є ї ґ; belarusian ⇐ look, or ў; greek ⇐ look, auth, or ruling; georgian,
armenian ⇐ look, auth, or mask. A language on weaker evidence is listed with `?` and the row is flagged DOUBT.
FLAGS: RUS-READ-NO-RUSSIAN = the item has Russian-model readings on disk but the table gives it no Cyrillic language:
those readings are junk and must not reach the Russian companion, the ledger's bi-script label, or any rule.
READS ONLY. WRITE-SET: the --out TSV alone, refused if it exists.
"""
import os, re, sys, csv, argparse, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_OF = {"russian": "cyrillic", "ukrainian": "cyrillic", "belarusian": "cyrillic", "serbian-or-macedonian": "cyrillic",
             "bulgarian": "cyrillic", "russian-cited": "cyrillic", "cyrillic-cited": "cyrillic", "serbian-cited": "cyrillic",
             "cyrillic": "cyrillic", "cyrillic-unspecified": "cyrillic", "greek": "greek", "greek-polytonic": "greek",
             "georgian": "georgian", "armenian": "armenian", "hebrew": "hebrew", "japanese": "japanese",
             "arabic-script": "arabic", "chinese-script": "han", "korean": "hangul", "other-script": "other"}
# «-cited» = a few names, titles or quoted words in another language (< CITED distinct Cyrillic words of 4+ letters in the
# authoritative readings). The script is printed, the text is not in that language: a cited language NEVER licenses a
# model run, a search file of its own or a bi-script label.
CITED = 30
CITED_SHARE = 0.05   # a non-Cyrillic script on fewer than 5% of an item's pages is cited (BK 2015: Greek on 4 of 392)
# DECLARED languages (a new item, e.g. a cupel batch, before any reading of it can show its scripts): item-name prefix →
# (languages, provenance). Added to the item's row with «declared» as evidence. The Russian reader refuses an item not in
# the table, so a batch's languages are declared here at intake and the table rebuilt before its Russian passes.
DECLARED = {}
# The editor's rulings on a look's unnamed Cyrillic etc.: item-name prefix → (from, to, provenance)
#   (to None = the entry is dropped: the ruling says the language is not there)
RULED = {"StSl2017_XIV": (("arabic-script",), None,
                          "editor 2026-10-04 03:3x «yes, ignore fake arabic»: the PDF text layer garbles a transliteration "
                          "font on 98 pages into shifted Latin and Arabic letters and digits — not Arabic"),
         "ondodeesperanto.": (("cyrillic-unspecified", "russian?", "cyrillic?", "cyrillic-cited"), "russian",
                              "editor 2026-10-03 19:0x «La Ondo is Russian»"),
         "mondo": (("russian?", "cyrillic?", "cyrillic-unspecified"), None,
                   "editor 2026-10-01 00:44 «There IS no Russian in Mondo, that was poor quality OCR»")}
NOT_A_LANGUAGE = re.compile(r"-(names|addresses|romanised|lacinka|show-through)$|^(not-stated|not-verifiable|latin-only|"
                            r"latin-unspecified|examples-several-languages|auxlang-.*|ipa|languages_seen)$")
ALIAS = {"occidental-interlingue": "occidental", "russian-name": None}


def norm(s):
    return re.sub(r"[^0-9a-zа-я]", "", s.lower())


def rows(path):
    return list(csv.DictReader((l for l in open(path, encoding="utf-8") if not l.startswith("#")), delimiter="\t"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("evidence"); ap.add_argument("looks", nargs="+", help="look-evidence TSVs (the harvest, then later looks)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    ev = {r["item"]: r for r in rows(a.evidence)}
    byn = {norm(k): k for k in ev}
    s = importlib.util.spec_from_file_location("led", os.path.join(HERE, "ocr-absence-ledger.py"))
    led = importlib.util.module_from_spec(s); s.loader.exec_module(led)
    greek_ruled = {k for k, v in led.PRESENCE_ONLY_NAMED.items() if "Greek" in v}

    look = collections.defaultdict(lambda: collections.defaultdict(set))   # item → language → pages
    unmatched = collections.Counter()
    latin_only = collections.defaultdict(set)   # item → pages a look saw with NO non-Latin script (evidence of absence)
    for r in (x for f in a.looks for x in rows(f)):
        item = r["item"].strip()
        if item not in ev:
            item = byn.get(norm(item)) or next((k for n, k in byn.items() if norm(r["item"]) and n.startswith(norm(r["item"]))), None)
        if not item:
            unmatched[r["item"]] += 1; continue
        if "latin-only" in r["languages_seen"]:
            latin_only[item].add(r["pdf_page"])
        for lang in (x.strip() for x in r["languages_seen"].split(",")):
            lang = ALIAS.get(lang, lang)
            if lang and not NOT_A_LANGUAGE.search(lang):
                look[item][lang].add(r["pdf_page"])

    out = []
    n = lambda r, k: int(r.get(k) or 0)
    for item, r in sorted(ev.items()):
        L = collections.OrderedDict()   # language → [evidence]
        def add(lang, src):
            L.setdefault(lang, []).append(src)
        if r["primary"]:
            add(r["primary"], "gate")
        for x in filter(None, r["latin_seconds"].split(",")):
            add(x, "gate")
        for lang, pages in look[item].items():
            add(lang, f"look:{len(pages)}")
        for prefix, (langs_, why) in DECLARED.items():
            if item.startswith(prefix):
                for x in langs_:
                    add(x, f"declared:{why}")
        doubt, notes = [], []
        cyr, lex = n(r, "auth_cyrillic"), n(r, "rus_lex_pages")
        cw, rw, bg, uk = (n(r, k) for k in ("auth_cyr_words", "auth_ru_letter_words", "auth_bg_words", "auth_uk_words"))
        cited = cw < CITED   # a few Cyrillic names or titles in an otherwise Latin text
        # WHICH Cyrillic language (step 3, 2026-10-03 19:0x), by letters in the authoritative readings: є ї ґ Ukrainian;
        # ъ inside a word and no ы э ё Bulgarian; ы э ё Russian. The word-list share does not separate them.
        if uk >= 5 or n(r, "ukr"):
            add("ukrainian", f"auth:{max(uk, n(r, 'ukr'))}")
            ukl_ = n(r, "auth_uk_list_permille")
            if ukl_ > n(r, "auth_ru_list_permille"):
                L["ukrainian"].append(f"list:{ukl_}‰")
        bgl, ukl, rul = (n(r, f"auth_{k}_list_permille") for k in ("bg", "uk", "ru"))
        if bg >= 2 and not rw:
            add("bulgarian", f"auth-words:{bg}")
            if bgl > rul:
                L["bulgarian"].append(f"list:{bgl}‰ (ru {rul}‰)")
            else:
                doubt.append(f"Bulgarian letters but the Bulgarian list does not confirm ({bgl}‰ vs ru {rul}‰)")
        if n(r, "bel"):
            add("belarusian", f"auth:{n(r, 'bel')}")
        other_cyr = any(k in L for k in ("ukrainian", "bulgarian", "belarusian"))
        # lex alone needs >= 5 pages: *Mondo* 1924 has 2 such pages and no Russian (the editor ruled on 2026-10-01 that Mondo
        # has no Russian and those readings were poor-quality OCR; ocr-absence-ledger.py FALSE_BISCRIPT)
        if "russian" in L:
            pass                                          # a look saw it
        elif lex >= 5:
            add("russian", f"lex:{lex}")
        elif cyr and (rw or (lex and not other_cyr)):
            add("russian-cited" if cited else "russian", f"auth-words:{rw}" if rw else f"lex:{lex}")
        elif cyr and not other_cyr:
            if cited:
                add("cyrillic-cited", f"auth-words:{cw}")
            else:
                add("cyrillic?", f"auth-words:{cw}"); doubt.append("Cyrillic, language not shown by its letters")
        elif lex and not cyr:
            # the language look of 3 Oct (an internal record, 2026-10-03, not published): where a blind look saw the item's pages and
            # NO non-Latin script, Russian-list words on 1–4 pages are junk (Estonian Fraktur, Polish, Esperanto)
            if latin_only[item] and not any(SCRIPT_OF.get(x) == "cyrillic" for x in look[item]):
                notes.append(f"Russian-list words on {lex} page(s) are junk: a blind look saw pages "
                             f"{','.join(sorted(latin_only[item], key=int))} with no non-Latin script")
            else:
                add("russian?", f"lex:{lex}"); doubt.append("Russian-list words on 1–4 pages of a Russian-model reading only")
        if n(r, "srp_mkd"):
            if n(r, "srp_mkd") <= 2:       # checked on the editor's request for details (2026-10-03): Sokolova, *Studia Slavica* — Russian linguistics
                add("serbian-cited", f"auth:{n(r, 'srp_mkd')}")   # citing Serbian words, letters and a Belić title
            else:
                add("serbian-or-macedonian?", f"auth:{n(r, 'srp_mkd')}"); doubt.append("ђ ј љ њ ћ џ ѓ ќ ѕ on 3+ pages")
        for prefix, (frms, to, why) in RULED.items():
            if item.startswith(prefix):
                for frm in frms:
                    if frm in L:
                        ev_ = L.pop(frm)
                        if to:
                            L.setdefault(to, []).extend(ev_ + [f"ruling:{why}"])
                        else:
                            notes.append(f"{frm} dropped by ruling: {why}")
                if to in L or not to:
                    doubt[:] = [d for d in doubt if not d.startswith(("Russian-list", "Cyrillic"))]
        if n(r, "auth_greek"):
            add("greek", f"auth:{n(r, 'auth_greek')}")
        if n(r, "auth_greek_polytonic"):
            add("greek-polytonic", f"auth:{n(r, 'auth_greek_polytonic')}")
        if item in greek_ruled:
            add("greek", "ruling")
        for k in ("georgian", "armenian"):
            if n(r, f"auth_{k}"):
                add(k, f"auth:{n(r, f'auth_{k}')}")
            if r["kathye_mask"]:
                add(k, "mask")
        if n(r, "auth_hebrew"):
            # the editor judged on 2026-10-03 that the Hebrew script is likely Hebrew, though this is uncertain
            add("hebrew", f"auth:{n(r, 'auth_hebrew')}"); add("hebrew", "ruling:likely")
            notes.append("Hebrew per the editor's «likely»; Posta Mundi 20 p. 7 reads as Ido in Hebrew letters, "
                         "HV-13032018 p. 34 also prints Yiddish")
        # OTHER SCRIPTS, BY NEGOTIATION (the editor ruled on 2026-10-04 that other scripts are settled by negotiation:
        # Japanese, Arabic, Chinese and Greek are all possible, other Asian scripts unlikely but not ruled out; RUNBOOK.md C6.5): the
        # table records them so they can be put to the editor; running text (not cited) is flagged DOUBT for that.
        for col, lang in (("auth_arabic", "arabic-script"), ("auth_kana", "japanese"), ("auth_han", "chinese-script"),
                          ("auth_hangul", "korean"), ("auth_other_script", "other-script")):
            if n(r, col) and not (lang == "chinese-script" and n(r, "auth_kana")):   # han beside kana is Japanese
                add(lang, f"auth:{n(r, col)}")
        # the rulings again, for the entries just added (a ruling that DROPS a script, e.g. Studia Slavica's fake Arabic)
        for prefix, (frms, to, why) in RULED.items():
            if item.startswith(prefix) and to is None:
                for frm in frms:
                    if frm in L:
                        L.pop(frm); notes.append(f"{frm} dropped by ruling: {why}")
        # CITED, EVERY SCRIPT (approved by the editor, 2026-10-03, after the editor asked what BK-I-2015 is, why it has Greek
        # in it, and where the Japanese came from): Pabst's *Berlina Komentario* cites Greek etymons of the affixes
        # on 3–4 of 392 pages; *Ruslanda Esperantisto* 1910.1 prints one Japanese line in an advert. A script on < CITED_SHARE
        # of the item's pages, or seen by a look on one page with no reading of it, is CITED — unless a ruling, the mask
        # or a declaration stands behind it (the editor's judgement that the Hebrew is likely Hebrew names the language, not its extent).
        npg = max(n(r, "pages"), 1)
        for lang in list(L):
            base = lang.rstrip("?")
            scr = SCRIPT_OF.get(base)
            if scr in (None, "latin") or base.endswith("-cited") or base == "cyrillic-unspecified":
                continue
            ev_ = L[lang]
            if any(e.startswith(("mask", "declared")) or (e.startswith("ruling:") and "likely" not in e) for e in ev_):
                continue
            lp = max([int(e.split(":")[1]) for e in ev_ if re.fullmatch(r"look:\d+", e)] or [0])
            ap = (n(r, "auth_greek") + n(r, "auth_greek_polytonic") if scr == "greek" else
                  n(r, f"auth_{scr}") if scr in ("georgian", "armenian", "hebrew") else
                  max(n(r, "auth_kana"), n(r, "auth_han")) if scr == "japanese" else
                  n(r, {"arabic": "auth_arabic", "han": "auth_han", "hangul": "auth_hangul",
                        "other": "auth_other_script"}.get(scr, "")) if scr in ("arabic", "han", "hangul", "other") else 0)
            if scr == "cyrillic":          # Cyrillic keeps its own word rule above; here only the one-page look sighting
                if base == "russian":      # of a language with no reading behind it (*Ruslanda* 1906.8: one Ukrainian title)
                    continue
                # 21:2x: judged by PAGE SHARE like the other scripts (was: only a one-page look sighting, and Bulgarian was
                # looked up in the wrong column, srp_mkd, so it came out «cited» by accident). Pages that show the
                # language: its marker letters (ukr, bel), or for Bulgarian the pages with Cyrillic at all.
                ap = n(r, {"ukrainian": "ukr", "belarusian": "bel", "bulgarian": "auth_cyrillic"}.get(base, "srp_mkd"))
                cited_ = max(lp, ap) / npg < CITED_SHARE or (not ap and lp <= 1)
                label = f"share:{max(lp, ap)}/{npg}pp"
            elif ap:
                # the editor ruled on 2026-10-04 (Q1) that these are citations, the threshold being the greater of 5% or 5 words: a script
                # with authoritative readings is CITED when its distinct words are fewer than the greater of 5% of the item's
                # distinct words, or 5 (short items cite a few names: IpI 130's Japanese, Posta Mundi 8's Chinese, 38's Telugu)
                col = {"greek": ("auth_greek_words",), "japanese": ("auth_kana_words", "auth_han_words"),
                       "han": ("auth_han_words",), "hangul": ("auth_hangul_words",), "other": ("auth_other_script_words",)
                       }.get(scr, (f"auth_{scr}_words",))
                words = sum(n(r, k) for k in col)
                cited_ = words < max(CITED_SHARE * n(r, "auth_all_words"), 5)
                label = f"words:{words}/{n(r, 'auth_all_words')}"
            else:   # seen by a look only: by page share, as before
                cited_ = lp / npg < CITED_SHARE or lp <= 1
                label = f"share:{lp}/{npg}pp"
            if cited_:
                L[f"{base}-cited"] = L.pop(lang) + [label]
                doubt[:] = [d for d in doubt if "Hebrew" not in d] if base == "hebrew" else doubt
                notes[:] = [x for x in notes if not x.startswith("Hebrew per")] if base == "hebrew" else notes
        for x in ("arabic-script", "japanese", "chinese-script", "korean", "other-script"):
            if x in L and not any(e.startswith(("ruling:", "declared:")) for e in L[x]):
                doubt.append(f"{x} as running text: by negotiation with the editor (cupel runbook C6.5)")
        if "cyrillic-unspecified" in L and not any(SCRIPT_OF.get(x.rstrip("?")) == "cyrillic" and x != "cyrillic-unspecified" for x in L):
            doubt.append("Cyrillic seen in a look, language not named")
        langs = [x for x in L if x != "cyrillic-unspecified" or len([y for y in L if SCRIPT_OF.get(y.rstrip('?')) == 'cyrillic']) == 1]
        scripts = sorted({SCRIPT_OF.get(x.rstrip("?"), SCRIPT_OF.get(x.rstrip("?").removesuffix("-cited"), "latin"))
                          for x in langs})   # a cited script is still PRINTED: it stays in the scripts column
        flags = []
        licensed = [x for x in langs if SCRIPT_OF.get(x.rstrip("?")) == "cyrillic" and not x.endswith("-cited")]
        if n(r, "rus_read_pages") and not licensed:
            flags.append(f"RUS-READ-NO-RUSSIAN ({n(r, 'rus_read_pages')} pages read"
                         + (", Cyrillic cited only)" if "cyrillic" in scripts else ")"))
        if doubt:
            flags.append("DOUBT: " + "; ".join(doubt))
        if notes:
            flags.append("NOTE: " + "; ".join(notes))
        out.append([item, ",".join(langs), ",".join(scripts),
                    "; ".join(f"{k}[{','.join(v)}]" for k, v in L.items()), " | ".join(flags)])

    with open(a.out, "w", encoding="utf-8") as o:
        o.write(f"# GENERATED by tools/ocr-text-languages-table.py from {os.path.basename(a.evidence)} + "
                f"{' + '.join(os.path.basename(f) for f in a.looks)} + the editor's rulings. THE FILTER: no pass reads a text with a language's "
                f"model, writes its search file, or labels it bi-script in it, unless this table lists that language.\n")
        o.write("item\tlanguages\tscripts\tevidence\tflags\n")
        for x in out:
            o.write("\t".join(x) + "\n")
    c = collections.Counter(s for x in out for s in x[2].split(","))
    print(f"{len(out)} items → {a.out}; scripts: {dict(c)}")
    print(f"RUS-READ-NO-RUSSIAN {sum('RUS-READ-NO-RUSSIAN' in x[4] for x in out)}; DOUBT {sum('DOUBT' in x[4] for x in out)}")
    if unmatched:
        print(f"look rows not matched to an item ({sum(unmatched.values())}): {dict(unmatched)}")


if __name__ == "__main__":
    main()
