#!/usr/bin/env python3
"""old-format-port.py — the old-format lines kept without a twin, brought to format 4 by legiloj (the editor, 2026-10-31
11:1x–11:3x: the old lines brought to format 4, only the 4,711 without a twin; approved).

The lines are the rows «kept, no twin» of the newest profiles/SUPERSEDED-LINES-<tag>.tsv (tools/old-format-supersede.py):
an old line whose item and page an assembled format-4 dowse has read, with no format-4 line for its person there. Each is
found in today's text by its quotation (tools/fact-lines.py's search, on its page and the pages either side; on every
page of the item where the line has none), else by the person's surname on its page or beside it, and handed to a
legilo with the passage around it (the page's lines from 6 before to 8 after; the page's first 80 lines where neither
is found on a known page). Where the quotation is not on its page or beside it, or the line has no page, it is
sought on every page of the item (its longest run, 4 words at least); a line with no page, by its names over the
whole item (the surname with another of its names) or its Adresaro number; an Adresaro line in the series' other
pieces too (2026-10-31, tag u). A line found on
no page is not handed out: it is listed as unplaced. The legilo writes the fact as a lean format-4 line, its «l. K» the
text's own line as the passage numbers it, or drops it with its reason; the tool expands the line as the assembler
does (harvest-facts.py's expand_lean: the item's key, the PDF page, the anchor checked on line K, the default voice, the
issue's date for «[n]»; the themes by dowse-facts-assemble.py's themes()).

    old-format-port.py prep TAG [--sample K] [--exclude TAG2,…] [--parts N] [--group G] [--write]
        dowse/old-format-port/: port-rows-TAG.tsv (every line handed out: P-number, file, line, person, item, page,
        text line found, how), port-unplaced-TAG.tsv, port-lines-TAG-N.md (part N's lines and passages), the briefs
        facts-brief-TAG-gA-B.md (G parts a legilo, default 3), and dowse/workflow-readers-TAG.json; --sample K takes K
        lines spread over the whole (the pilot), --exclude leaves out the lines of earlier tags, --parts N lines a part
        (default 25). Without --write, the counts only. Refuses if any file exists.
    old-format-port.py apply TAG [--write]
        the returns facts-return-TAG-N-pK.md joined by part; writes profiles/by-source/old-format-port-TAG.md
        (format 4) and dowse/old-format-port/port-done-TAG.tsv (each old line ported or dropped, with the reason),
        read by old-format-supersede.py, and port-apply-TAG.md (the counts, the lines refused). Refuses if any exists.
    old-format-port.py adresaro TAG --from TAG2[,TAG3] --gazetteer T [--show] [--write]
        the unplaced Adresaro lines of TAG2 by tool, no legilo (the Wikisource texts have no pages): each line's entry by
        series and number, written by tools/adresaro-extract.py under the old line's person; the same three files as
        apply. A line whose person is not the entry's registrant nor its collector is dropped (a street, a town, a trade).
Ezri, 2026-10-31."""
import os, re, sys, csv, json, glob, collections, importlib.util, unicodedata

TOOLS = os.path.dirname(os.path.abspath(__file__))
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, fn)); m = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]
    try: spec.loader.exec_module(m)
    finally: sys.argv = saved
    return m
H = load("harvest_facts", "harvest-facts.py")
FLN = load("fact_lines", "fact-lines.py")
FID = load("fact_ids", "fact-ids.py")
GEN = H.GEN
D = os.path.join(GEN, "dowse", "old-format-port")
TEXT_DIRS = ("ocr-preferred", "ocr-work", "born-digital-text", "ocr")
PAGE = re.compile(r"^=== page (\d+) ===\s*$")
KINDS_DOC = os.path.join(GEN, "ocr", "method", "EVENT-KINDS-PROPOSAL-2026-10-13.md")

def register():
    regs = sorted(glob.glob(os.path.join(GEN, "profiles", "SUPERSEDED-LINES-*.tsv")))
    if not regs: sys.exit("no register: run tools/old-format-supersede.py --write --tag T first")
    return regs[-1], list(csv.DictReader((l for l in open(regs[-1], encoding="utf-8") if not l.startswith("#")), delimiter="\t"))

def text_path(item):
    return next((p for d in TEXT_DIRS for p in [os.path.join(GEN, "sources", d, item + ".txt")] if os.path.isfile(p)), None)

_T = {}
def text(item):
    """(path, lines, page words, [(marker line, page)]) of an item's text."""
    if item not in _T:
        p = text_path(item)
        if not p: _T[item] = None
        else:
            L = open(p, encoding="utf-8", errors="replace").read().split("\n")
            marks = [(i, int(m.group(1))) for i, l in enumerate(L, 1) for m in [PAGE.match(l)] if m]
            _T[item] = (p, L, FLN.page_words(p, FID), marks)
    return _T[item]

def page_span(marks, nlines, page):
    """(first, last) text lines of a page, its marker excluded."""
    for k, (i, p) in enumerate(marks):
        if p == page: return i + 1, (marks[k + 1][0] - 1 if k + 1 < len(marks) else nlines)
    return None

def page_at(marks, line):
    pg = None
    for i, p in marks:
        if i > line: break
        pg = p
    return pg

def quote_words(t):
    qs = [q for q in H.QUOTE.findall(t) if q.strip()]
    segs = [s for q in qs for s in re.split(r"…|\.\.\.", re.sub(r"\[[^\]]*\]", " ", q)) if len(s.split()) >= 3]
    return FID.norm(max(segs, key=lambda s: len(s.split()))).split() if segs else []

_J = {}
def find_anywhere(item, pw, words):
    """The quotation on any page of the item, its longest run first and 4 words at least (a page given and the
    quotation not on it or beside it, or no page; 2026-10-31, the port of the 864: 735 had no page)."""
    if item not in _J:
        _J[item] = [(p, " " + " ".join(w for w, _ in pw[p]) + " ", pw[p]) for p in sorted(pw)]
    for k in (6, 5, 4):
        for s in range(0, len(words) - k + 1):
            q = " " + " ".join(words[s:s + k]) + " "
            for _p, joined, flat in _J[item]:
                at = joined.find(q)
                if at >= 0: return flat[joined.count(" ", 0, at)][1]
    return None

def one_edit(a, b):
    """a and b differ by one letter changed, added or dropped at most."""
    if abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b): a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))

PIECE = re.compile(r"^(adresaro-\d{4}-serio-\d+)-\d+$")
def place(r):
    """(text line found, page, how) or None. An Adresaro series' line not found in the piece the register names (its
    first) is sought in the series' other pieces, and r["item"] becomes the piece it is found in (CHAPRON, no. 12192,
    in serio-26-2, not 26-1)."""
    got = place_in(r)
    m = PIECE.match(r["item"])
    if m and (not got or got[2] == "la paĝo"):
        for it in sorted({os.path.basename(p)[:-4] for d in TEXT_DIRS for p in glob.glob(os.path.join(GEN, "sources", d, m.group(1) + "-*.txt"))}):
            if it == r["item"]: continue
            g = place_in(dict(r, item=it))
            if g and g[2] != "la paĝo": r["item"] = it; return g
    return got

def place_in(r):
    t = text(r["item"])
    if not t: return None
    _p, L, pw, marks = t
    words = quote_words(r["text"])
    pg = int(r["page"]) if r["page"] else None
    # a line sent back (prep --retry): its quotation found the wrong spot (a roll's title above the person's entry,
    # tag u's 465), so by the names alone
    if words and not r.get("_names"):
        ln = FLN.find_line(pw, pg, words) if pg is not None else None
        if not ln and pg is None:
            for p in sorted(pw):
                ln = FLN.find_line(pw, p, words)
                if ln: break
        if not ln: ln = find_anywhere(r["item"], pw, words)
        if ln: return ln, page_at(marks, ln), "la citaĵo"
    # the quotation not found (the September OCR read otherwise): the old line's proper names (its person's surname,
    # the others it names) on the page or beside it, the spot where most of them stand within 3 lines (P1 of the first
    # pilot: «Zamenhof» alone found the masthead, not the Ligo's proposal beside «Prohoroviĉ» and «Rjabinin»)
    sur = [w for w in FID.norm(re.sub(r"\(.*", "", r["person"])).split() if len(w) >= 4]
    body = r["text"].split("$$$", 2)[-1]
    keys = set(sur) | {w for t in re.findall(r"\b[A-ZĈĜĤĴŜŬ][\wĉĝĥĵŝŭ'-]{3,}", body) for w in FID.norm(t).split() if len(w) >= 4}
    keys -= {"esperanto", "esperantisto", "esperantistoj", "the", "this", "first", "from", "with"}
    # an Adresaro row's number («…, no. 12192»), where the line gives no page
    nums = set(re.findall(r"\bno\.\s*(\d{3,6})\b", body)) if pg is None else set()
    keys |= nums
    if keys:
        best = None
        # a line sent back: the roll's next pages too, and the surname at one edit (oge.3: the 1911 roll from PDF 332,
        # NAUMANN read «Naumaxn» on 336)
        pages = (pg, pg - 1, pg + 1) if pg is not None else sorted(pw)
        if r.get("_names") and pg is not None: pages = sorted(range(pg - 1, pg + 8), key=lambda p: abs(p - pg))
        for p in pages:
            flat = pw.get(p, [])
            at = collections.defaultdict(set)
            for w, x in flat:
                if w in keys: at[x].add(w)
                elif r.get("_names") and len(w) >= 5:
                    s = next((s for s in sur if len(s) >= 5 and one_edit(w, s)), None)
                    if s: at[x].add(s)
            for x in sorted(at):
                near = set().union(*(at[y] for y in at if abs(y - x) <= 3))
                # over the whole item: the number, or the surname with another of the line's names
                if pg is None and not (near & nums or (near & set(sur) and len(near) >= 2)): continue
                # the person's own name at the spot (tag u: «Lingva Komitato» found a roll's title, not NAUMANN on it)
                if sur and not near & (set(sur) | nums): continue
                score = (bool(near & nums), len(near), bool(near - set(sur)), p == pg)
                if best is None or score > best[0]: best = (score, x)
        if best: return best[1], page_at(marks, best[1]), "la numero" if best[0][0] else "la nomoj"
    if pg is not None and page_span(marks, len(L), pg): return None, pg, "la paĝo"
    return None

WHOLE = False   # prep --retry: the whole page (up to 150 lines), not the passage
def passage(r, ln, pg):
    _p, L, _pw, marks = text(r["item"])
    a, b = page_span(marks, len(L), pg)
    # (tag t: the whole page for every line sent back; since tag v, only where the names were not found either)
    if ln: a, b = max(a, ln - 6), min(b, ln + 8)
    else: b = min(b, a + (149 if WHOLE else 79))
    return [(k, L[k - 1]) for k in range(a, b + 1)]

BRIEF = """# old-format-port: la malnovaj linioj al formato 4 ({tag}{gname})

`[Ezri, {tag}, per tools/old-format-port.py prep; la redaktoro, 2026-10-31, aprobite. La malnovaj linioj de septembro (formatoj 2 kaj 3), kiujn neniu linio de formato 4 ripetas sur ilia paĝo.]`

Vi legas por esplora projekto pri la historio de la internaciaj helplingvoj. Uzu nur la ilojn Read kaj Write (Write nur por viaj raportoj, kiel dirite sube). Rulu neniujn ŝelajn komandojn, faru neniujn retajn serĉojn. Skribu viajn raportojn en Esperanto.

**Legu unue** la specojn de fakto: `{kinds}`, nur la sekcion «The list in force»: legu nur la liniojn 15 ĝis 68 de la dosiero (la ilo Read kun offset kaj limit).

**La tasko.** Antaŭ unu monato la projekto skribis faktojn pri personoj en malnova formo, angle, el malnovaj OCR-tekstoj. Ĉiu el ili nun staras en via parto kiel **«P-numero»**, kun la eltiraĵo de la hodiaŭa teksto, kie ĝi troviĝas (la linioj kun sia numero en la teksto antaŭ «|»). Por ĉiu P-numero: legu la malnovan linion kaj la eltiraĵon; **se la eltiraĵo portas la fakton**, skribu ĝin kiel unu aŭ plurajn liniojn de formato 4 (sube), ĉiun komence kun sia P-numero: `P12 · - $$$ NOMO $$$ …`. **Se ne**, skribu unu linion `P12 · forigu: kialo` (kialoj: la fakto ne staras en la eltiraĵo; la nomo estas OCR-rubo aŭ ne persono; la malnova linio diras pli ol la teksto, kaj la teksto portas nenion pri la persono). La malnova linio estas propono, ne fonto: ĝiaj dato, fakto kaj identigo estas kontrolendaj kontraŭ la teksto, kaj vi skribas nur tion, kion la eltiraĵo diras. Ne serĉu aliajn faktojn en la eltiraĵo: nur la fakton de la malnova linio (aŭ ĝiajn partojn, se ĝi havis plurajn). Ĉiu P-numero ricevas almenaŭ unu linion.

**La linio:**

`P12 · - $$$ NOMO $$$ (kvalifiko) **dato** · {{speco: objekto}} · fakto en Esperanto · ankro · (prese M) l. K · voĉo (etikedoj)`

- **NOMO** majuskle, kiel en la malnova linio; evidentan misformon de la OCR korektu en la kapo kaj skribu la OCR-formon en la krampo de la voĉo: `📣 (OCR «GIEMOUR»)`. Kvalifiko nur kiel en la malnova linio, neniam el via propra scio. La kapo estas ĉiam persono.
- **dato:** ĉiu dato, kiun la teksto mem donas al la ago, grasa; relativan daton per la vortoj de la teksto, sen kalkuli; nur kie la teksto donas neniun daton al la ago, `**[n]**` (la dato de la numero). `[ĝenerala]` nur por karaktero, deveno kaj dumviva profesio. Neniam dato, kiun la teksto ne donas (ankaŭ ne la daton de la malnova linio, se la eltiraĵo ne donas ĝin).
- **speco:** el la listo, laŭ la propra predikato de la linio; ĉiam kun objekto (krom naskiĝo kaj morto), neniam dato en la objekto. Juĝo aŭ klarigo pri fakto estas `juĝo` aŭ `interpreto`. `alia` nur se neniu speco taŭgas (`{{alia: objekto; sugestas: …}}`).
- **Pluraj personoj:** kiuj faris aŭ spertis la samon, unu linio sub la unua, la aliaj post `kun:`; renkonto, konflikto, interkonsento: la aliaj en la objekto. Ĉiu persono, pri kiu la fakto estas, staras en la speca kampo per sia NOMO.
- **fakto:** viaj vortoj en Esperanto; unu fakto en unu linio; la linio staras sola (nomu la verkon aŭ okazon plene); «» en la fakto nur por vortoj, kiuj staras en la ankro (krom titoloj).
- **ankro:** almenaŭ ses vortoj de la eltiraĵo, laŭvorte, en ĝia lingvo, kiel la hodiaŭa teksto ilin havas (ne kiel la malnova linio citas); kie la OCR estas tro misa por ses vortoj, kiom ajn legeblas.
- **lokindiko:** nur `(prese M) l. K`: M la presita numero de la paĝo, se la eltiraĵo montras ĝin (alie nur `l. K`); K la numero de la linio en la teksto, kiun la eltiraĵo donas antaŭ «|», sur kiu la ankro komenciĝas. La projekto aldonas la eron kaj la PDF-paĝon.
- **voĉo:** ne skribu ĝin, se ĝi estas 📣 sen fontindiko (la projekto aldonas ĝin). Alie: ✅ kie la aŭtoro de la fonto mem agas; ⚠ (la fonto mem dubas); ❓ (vi ne certas, ke la fakto koncernas ĉi tiun personon); `derivita ↤ aŭtoro jaro, «titolo», p. N`. Viaj propraj aldonoj en krampo, mallonge.

**Viaj partoj kaj la raportoj:** {nparts}. Por ĉiu parto: legu ĝian dosieron tute; skribu ĝian raporton per la ilo Write **en pecoj** al `{dir}/facts-return-{tag}-N-pK.md` (N la numero de la parto, kiel la sekcio «La legiloj» donas ĝin; K = 1, 2, 3 … la numero de la peco): ĉiu peco havas ne pli ol 40 liniojn, en la ordo de la P-numeroj; skribu ĉiun pecon, tuj kiam ĝiaj linioj estas pretaj. Skribu per Write nur tiujn dosierojn, ĉiun unufoje, kaj neniun alian.

**Fine:** via fina mesaĝo estas nur unu linio, `Fino: X linioj` (X la sumo de la linioj, kiujn vi skribis); ne ripetu la raportojn en ĝi.

## La legiloj

{parts}
"""

def prep(tag, args):
    write = "--write" in args
    sample = int(args[args.index("--sample") + 1]) if "--sample" in args else None
    per = int(args[args.index("--parts") + 1]) if "--parts" in args else 25
    group = int(args[args.index("--group") + 1]) if "--group" in args else 3
    excl = set()
    if "--exclude" in args:
        for t2 in args[args.index("--exclude") + 1].split(","):
            for r in csv.DictReader(open(os.path.join(D, f"port-rows-{t2}.tsv"), encoding="utf-8"), delimiter="\t"):
                excl.add((r["file"], r["text"]))
    reg, rows = register()
    todo = [r for r in rows if r["status"] == "kept, no twin" and (r["file"], r["text"]) not in excl]
    if "--retry" in args:
        # the lines an earlier tag's legiloj sent back for want of the page, or did not return: the whole page now
        global WHOLE
        WHOLE, again = True, set()
        for t2 in args[args.index("--retry") + 1].split(","):
            for r in csv.DictReader(open(os.path.join(D, f"port-done-{t2}.tsv"), encoding="utf-8"), delimiter="\t"):
                if r["status"] in ("retry", "not returned"): again.add((r["file"], r["text"]))
        # … and the kept lines no tag has handed out yet (a register tag since: tag f's three, a qualified person no
        # longer «named in a kind» by his bare surname)
        # (the tags named, those launched: p and r were prepped and superseded, never read)
        # (the unplaced of those tags too: they wait for their own pass, after all this, the editor)
        out_ever = {(r["file"], r["text"]) for t2 in args[args.index("--retry") + 1].split(",") for k in ("rows", "unplaced")
                    for r in csv.DictReader(open(os.path.join(D, f"port-{k}-{t2}.tsv"), encoding="utf-8"), delimiter="\t")}
        todo = [r for r in rows if r["status"] == "kept, no twin" and ((r["file"], r["text"]) in again or (r["file"], r["text"]) not in out_ever)]
        # a line sent back is placed by its names (place_in), on the item and page the earlier tag found it on
        was = {(r["file"], r["text"]): (r["item"], r["page"]) for t2 in args[args.index("--retry") + 1].split(",")
               for r in csv.DictReader(open(os.path.join(D, f"port-rows-{t2}.tsv"), encoding="utf-8"), delimiter="\t")}
        todo = [dict(r, item=was[k][0], page=was[k][1], _names=True) if k in again and k in was else r
                for r in todo for k in [(r["file"], r["text"])]]
    if sample: todo = [todo[int(i * len(todo) / sample)] for i in range(sample)]
    placed, unplaced, how = [], [], collections.Counter()
    for r in todo:
        p = place(r)
        # --located: a line found only by its page is not handed out (tag v: the Lingva Komitato's rolls and ballots
        # summed over several volumes, which no one page carries)
        if not p or ("--located" in args and p[2] == "la paĝo"): unplaced.append(r); continue
        ln, pg, h = p; how[h] += 1
        placed.append((r, ln, pg, h))
    parts = [placed[i:i + per] for i in range(0, len(placed), per)]
    groups = [list(range(i + 1, min(i + group, len(parts)) + 1)) for i in range(0, len(parts), group)]
    words = sum(len(r["text"].split()) + sum(len(x.split()) for _k, x in passage(r, ln, pg)) for r, ln, pg, _h in placed)
    print(f"register {os.path.relpath(reg, GEN)}: {len(todo)} lines; placed {len(placed)} ({dict(how)}), unplaced {len(unplaced)}; "
          f"{len(parts)} parts of {per}, {len(groups)} legiloj; about {words:,} words handed out")
    if not write: return 0
    files = [os.path.join(D, f"port-rows-{tag}.tsv"), os.path.join(D, f"port-unplaced-{tag}.tsv"),
             os.path.join(GEN, "dowse", f"workflow-readers-{tag}.json")]
    files += [os.path.join(D, f"port-lines-{tag}-{n}.md") for n in range(1, len(parts) + 1)]
    names = [f"{tag}-g{g[0]}-{g[-1]}" if len(g) > 1 else f"{tag}-{g[0]}" for g in groups]
    files += [os.path.join(D, f"facts-brief-{nm}.md") for nm in names]
    ex = [f for f in files if os.path.exists(f)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(f, GEN) for f in ex))
    os.makedirs(D, exist_ok=True)
    pid = 0
    with open(files[0], "x", encoding="utf-8", newline="") as fr:
        w = csv.writer(fr, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "part", "file", "line", "person", "item", "page", "found", "how", "text"])
        for n, part in enumerate(parts, 1):
            with open(os.path.join(D, f"port-lines-{tag}-{n}.md"), "x", encoding="utf-8") as fh:
                fh.write(f"# La parto {n} ({tag})\n\n")
                for r, ln, pg, h in part:
                    pid += 1
                    w.writerow([f"P{pid}", n, r["file"], r["line"], r["person"], r["item"], pg, ln or "", h, r["text"]])
                    fh.write(f"## P{pid} · `{r['item']}` PDF {pg} (trovita per {h})\n\n**La malnova linio:** {r['text']}\n\n**La eltiraĵo:**\n\n```\n")
                    for k, x in passage(r, ln, pg): fh.write(f"{k}| {x}\n")
                    fh.write("```\n\n")
    with open(files[1], "x", encoding="utf-8", newline="") as fu:
        w = csv.writer(fu, delimiter="\t", lineterminator="\n")
        w.writerow(["file", "line", "person", "item", "page", "text"])
        for r in unplaced: w.writerow([r["file"], r["line"], r["person"], r["item"], r["page"], r["text"]])
    for g, nm in zip(groups, names):
        plist = "\n".join(f"{n}: `{D}/port-lines-{tag}-{n}.md`" for n in g)
        with open(os.path.join(D, f"facts-brief-{nm}.md"), "x", encoding="utf-8") as fh:
            fh.write(BRIEF.format(tag=tag, gname=f", {nm}", kinds=KINDS_DOC, dir=D, parts=plist,
                                  nparts=(f"vi legas {len(g)} partojn, unu post la alia" if len(g) > 1 else "vi legas unu parton")))
    with open(files[2], "x", encoding="utf-8") as fh:
        json.dump({"sources": [{"dir": D, "tag": tag, "groups": [nm[len(tag) + 1:].lstrip("g") for nm in names]}]}, fh, ensure_ascii=False)
    print(f"  wrote {len(files)} files under dowse/old-format-port/ and dowse/workflow-readers-{tag}.json")
    return 0

RET = re.compile(r"^\s*-?\s*\**(P\d+)\**\s*·\s*(.*)$")

def expand_body(body, item, DA):
    """A lean format-4 line (a legilo's, or the tool's own) expanded on the item's text as the assembler does: -> (line,
    the harvest's error or '')."""
    t = text(item)
    # «kun: …» written as a field of its own after the kind (14 lines of tag s): into the kind
    fs = body.split(" · ")
    if len(fs) > 3 and fs[2].strip().startswith("kun:") and fs[1].strip().endswith("}"):
        fs[1] = fs[1].rstrip()[:-1] + "; " + fs[2].strip() + "}"; del fs[2]; body = " · ".join(fs)
    line = H.expand_lean(DA.form_repair(body), t[1], item)
    ps = line.split(" · ")
    # the locator found by its form (expand_lean writes «… · locator · [?] · voice», or no themes where the
    # reader wrote no voice); then the themes as the assembler fills them, and the voice
    li = next((i for i in range(4, len(ps)) if H.locators(ps[i])), None)
    if li is None: return line, "la lokindiko ne plenigebla"
    after = ps[li + 1:]
    th = after.pop(0) if after and re.fullmatch(r"(?:\[[^\]]*\])+", after[0].strip()) else "[?]"
    if th.strip() == "[?]": th = DA.themes(ps[2])
    # a note in brackets with no mark before it («· (OCR «Coururar»)», 12 of the pilot's lines), which
    # expand_lean takes for a field and follows with the default voice: the note into the voice's brackets
    notes = [x.strip()[1:-1] for x in after if x.strip().startswith("(") and x.strip().endswith(")")]
    marks = [x for x in after if not (x.strip().startswith("(") and x.strip().endswith(")"))]
    voice = " · ".join(marks) or "📣 (sen fontindiko)"
    if notes: voice = (voice[:-1] + "; " if voice.endswith(")") else voice + " (") + "; ".join(notes) + ")"
    # A SECONDARY SOURCE'S LINE NAMES ITS INDEPENDENCE (the harvest's check; 133 lines of tags q–t): «sendependa»
    # after ✅ (the author's own act or judgement), «sen fontindiko» otherwise, where the legilo wrote none
    if H.item_table().get(item) == "SECONDARY" and not re.search(r"\((?:sendependa|derivita|sen fontindiko|refutas|kopio el)", voice):
        lab = "sendependa" if voice.lstrip().startswith("✅") else "sen fontindiko"
        voice = (voice[:voice.index("(") + 1] + lab + "; " + voice[voice.index("(") + 1:]) if "(" in voice else voice + f" ({lab})"
    # an anchor under six words padded with ⟨fino⟩, as the short ones of a title or caption are
    aw = ps[li - 1].split()
    if len(aw) < 6: ps[li - 1] = " ".join(aw + ["⟨fino⟩"] * (6 - len(aw)))
    line = " · ".join(ps[:li + 1] + [th, DA.bracket(voice)])
    rec, err = H.parse(H.to2(H.take_kind(line)[0]))
    if not err: err = H.strict(rec, True)   # the harvest's own check of a format-4 file's line
    return line, err or ""

def apply(tag, args):
    write = "--write" in args
    DA = load("dfa", "dowse-facts-assemble.py")
    rows = {r["pid"]: r for r in csv.DictReader(open(os.path.join(D, f"port-rows-{tag}.tsv"), encoding="utf-8"), delimiter="\t")}
    pieces = collections.defaultdict(list)
    for p in glob.glob(os.path.join(D, f"facts-return-{tag}-*-p*.md")):
        m = re.search(rf"facts-return-{re.escape(tag)}-(\d+)-p(\d+)\.md$", p)
        if m: pieces[int(m.group(1))].append((int(m.group(2)), p))
    out, done, refused, seen = [], [], [], collections.defaultdict(list)
    for part in sorted(pieces):
        for _k, p in sorted(pieces[part]):
            for raw in open(p, encoding="utf-8"):
                m = RET.match(raw.rstrip("\n"))
                if not m: continue
                pid, body = m.group(1), m.group(2).strip()
                r = rows.get(pid)
                if not r or r["part"] != str(part): refused.append((pid, "P-numero ne de ĉi tiu parto", body)); continue
                if body.lower().startswith("forigu"):
                    seen[pid].append(("dropped", body.split(":", 1)[1].strip() if ":" in body else "")); continue
                if not body.startswith("- $$$"): refused.append((pid, "nek linio nek forigo", body)); continue
                line, err = expand_body(body, r["item"], DA)
                if err: refused.append((pid, err, line)); continue
                out.append(line); seen[pid].append(("ported", ""))
    for pid, r in rows.items():
        v = seen.get(pid)
        st = "ported" if v and any(s == "ported" for s, _ in v) else "dropped" if v else "not returned"
        why = "; ".join(x for s, x in (v or []) if s == "dropped" and x)
        # A DROP THAT BLAMES THE PASSAGE is no drop (the pilot, tag 2026-10-31q: 30 of its 35, «la listo … haltas ĉe
        # Karovina; Langlet ne aperas»: the quotation a list's heading, the person further down): «retry», handed out
        # again with the whole page (prep --retry); it stays in scope meanwhile
        # (--final: a round that had the whole page, prep --retry; its drops are drops)
        if st == "dropped" and "--final" not in args and re.search(r"eltiraĵo|haltas|fortranĉ|ne aperas|ne staras", why) and not re.search(r"OCR-rubo|ne persono", why):
            st = "retry"
        # --keep KEY,…: a drop that today's OCR caused where September's read the line (the directory extracts' «Meise,
        # Adolf, Postmeister …», tag ze): kept in the old format, its page asked of the vision reader
        if st == "dropped" and "--keep" in args and r["person"] in args[args.index("--keep") + 1].split(","):
            st = "retry"
        done.append([pid, r["file"], r["line"], r["person"], st, why, r["text"]])
    c = collections.Counter(d[4] for d in done)
    print(f"{len(rows)} lines handed out: " + ", ".join(f"{k} {v}" for k, v in c.most_common()) + f"; {len(out)} format-4 lines, {len(refused)} refused")
    if "--show" in args:
        print("  refused, by reason: " + "; ".join(f"{k} {v}" for k, v in collections.Counter(w[:60] for _p, w, _b in refused).most_common(8)))
        for pid, why, body in refused[:6]: print(f"  {pid}: {why[:80]} · {body[:220]}")
    if not write: return 0
    fo = os.path.join(GEN, "profiles", "by-source", f"old-format-port-{tag}.md")
    fd = os.path.join(D, f"port-done-{tag}.tsv"); fa = os.path.join(D, f"port-apply-{tag}.md")
    ex = [f for f in (fo, fd, fa) if os.path.exists(f)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(f, GEN) for f in ex))
    with open(fo, "x", encoding="utf-8") as fh:
        fh.write(f"# La malnovaj linioj al formato 4 ({tag})\n\nfacts-format: 4\n\n`[Ezri, {tag}, per tools/old-format-port.py apply: "
                 "la malnovaj linioj de septembro kiujn neniu linio de formato 4 ripetis sur ilia paĝo, legitaj denove de legiloj "
                 "kontraŭ la hodiaŭa teksto (la redaktoro, 2026-10-31). "
                 f"La malnova linio de ĉiu: dowse/old-format-port/port-done-{tag}.tsv.]`\n\n")
        for l in out: fh.write(l + "\n")
    with open(fd, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "file", "line", "person", "status", "why", "text"]); w.writerows(done)
    with open(fa, "x", encoding="utf-8") as fh:
        fh.write(f"# The port of tag {tag}\n\n{len(rows)} lines handed out: " + ", ".join(f"{k} {v}" for k, v in c.most_common())
                 + f".\n\n{len(out)} format-4 lines written to `profiles/by-source/old-format-port-{tag}.md`; {len(refused)} refused:\n\n")
        for pid, why, body in refused: fh.write(f"- {pid}: {why} · {body[:300]}\n")
    print(f"  wrote {os.path.relpath(fo, GEN)}, {os.path.relpath(fd, GEN)}, {os.path.relpath(fa, GEN)}")
    return 0

REG_NO = re.compile(r"Adresaro Serio [IVXL]+(?:[ –-][IVXL]+)?\b[^·]*?\bno\.\s*(\d+)")
INTRO = re.compile(r"Bracketed as introducer on (\d+) Adresaro entries \(([^)]*)\)")
SERIES = re.compile(r"Adresaro Serio ([IVXL]+)(?:\s*–\s*([IVXL]+))?")
def _form(s):
    return re.sub(r"[^\wĉĝĥĵŝŭ]", "", re.sub(r"[?!]|\^+\w*\^+", "", s).lower())

def adresaro(tag, args):
    """THE ADRESARO'S SEPTEMBER LINES BY TOOL, no legilo (the editor, 2026-10-31 19:5x: the texts and facts as
    clean as possible before the harvest; the runbook's «Not built yet»): the Wikisource texts have no pages, so the port's legiloj could not be
    handed their passage. Each old Adresaro line of the unplaced (--from TAG2[,TAG3]) gets tools/adresaro-extract.py's own
    lines for its entry, by series and number, under the old line's person and with September's identification named in
    the voice (❓ where the old line was ⚠): a registration («Registered as …») the entry's {aperoj}, {loĝado}, {profesio};
    an introduction the {propagando} line of each entry whose collector is printed as the old line's form, a single one
    («Introduced X … as [Ch. Lambert]») or a run («Bracketed as introducer on 6 Adresaro entries (V. Devjatnin 5, …)»).
    Kept in the old format: a run whose forms bear different initials (two people under one key: LEMAIRE René and
    Charles), a line that is both a registration and a run, a statistic. An entry whose line the extractor already wrote
    for the same person (profiles/by-source/zamenhof-adresaro-dowse.md) is ported with no new line."""
    write = "--write" in args
    frm = args[args.index("--from") + 1].split(",") if "--from" in args else sys.exit("--from TAG2 needed")
    gzt = args[args.index("--gazetteer") + 1] if "--gazetteer" in args else sys.exit("--gazetteer T needed (the extractor's)")
    AX = load("adresaro_extract", "adresaro-extract.py")
    DA = load("dfa", "dowse-facts-assemble.py")
    gz, W = AX.GZ.forms(gzt), AX.wiki()
    ents = {}
    for item, para, s, y, n, t in AX.entries():
        ents[(s, n)] = (item, para, s, y, n, t)
    # ¶ locator → the people the extractor's lines hold there: the assembled first dowse and its newest return (the
    # harvest's next assembly)
    held = collections.defaultdict(set)
    rets = sorted(glob.glob(os.path.join(GEN, "dowse", "zamenhof-adresaro", "facts-return-*-adresaro.md")))
    for f in [os.path.join(GEN, "profiles", "by-source", "zamenhof-adresaro-dowse.md")] + rets[-1:]:
        for l in open(f, encoding="utf-8"):
            m = re.match(r"^- \$\$\$ (.+?) \$\$\$.* · (adresaro-[\w-]+, ¶ \d+) · ", l)
            if m: held[m.group(2)].add(H.slug(m.group(1)))
    def fold(s):
        """A name's letters, its transliterations folded (Kapustjanskij = KAPUSTYANSKIY, Kravtzov = KRAVCOV, Sluckij =
        SLOUTZKY, Veitzler = VEJTCLER)."""
        s = re.sub(r"[^a-z ]", "", unicodedata.normalize("NFD", s.lower()).replace("-", " "))
        for a, b in (("sch", "s"), ("tz", "c"), ("ts", "c"), ("tc", "c"), ("cz", "c"), ("ou", "u"), ("ck", "k"),
                     ("ij", "i"), ("iy", "i"), ("y", "i"), ("j", "i"), ("w", "v")):
            s = s.replace(a, b)
        return re.sub(r"(\w)\1", r"\1", s)
    def names_him(key, name):
        """THE OLD LINE'S PERSON IS THE REGISTRANT: a word of the key (3 letters or more) is a word of the entry's name, at
        one edit. September's second pass took a street («r. Aubert»), a town («Beau Bassin») or a trade («approb.
        Bader») for the person (2026-10-31: AUBERT on Moinard's entries, BEAU on Leroy's, BADER on Emil Müller's)."""
        ws = fold(name).split()
        return any(one_edit(k, w) or k == w for k in fold(re.sub(r"\(.*", "", key)).split() if len(k) >= 3 for w in ws)
    rows = []
    for t2 in frm:
        rows += [r for r in csv.DictReader(open(os.path.join(D, f"port-unplaced-{t2}.tsv"), encoding="utf-8"), delimiter="\t")
                 if r["item"].startswith("adresaro-")]
    out, done, refused, cnt = [], [], [], collections.Counter()
    def entry(s, n):
        if (s, n) not in ents: return None
        item, para, s, y, n, t = ents[(s, n)]
        return AX.marked(AX.parse(s, t), W, item, n, s, t), ents[(s, n)]
    for k, r in enumerate(rows, 1):
        pid, t = f"A{k}", r["text"]
        m = re.match(r"^- \$\$\$ (.+?) \*\*", t)
        hp, key = m.group(1).strip(), re.match(r"^- \$\$\$ (.+?) \$\$\$", t).group(1)
        doubt = re.search(r"· ⚠", t) is not None
        conf = f"📣 {'❓ ' if doubt else ''}(sen fontindiko; {AX.DNOTE}; ⟦identigo de septembro: {r['file']}⟧)"
        sm = SERIES.search(t)
        s0 = AX.roman(sm.group(1)) if sm else int(re.sub(r"^adresaro-\d{4}-serio-(\d+).*$", r"\1", r["item"]))
        s1 = AX.roman(sm.group(2)) if sm and sm.group(2) else s0
        new, why = [], ""
        im = INTRO.search(t)
        if "Registered as" in t and ("introducer" in t or im):
            why = "kept: registration and introductions in one line"
        elif "Registered as" in t:
            nm = REG_NO.search(t)
            got = entry(s0, int(nm.group(1))) if nm else None
            if not got: why = "kept: no entry of that series and number"
            else:
                e, (item, para, s, y, n, et) = got
                # «Registered as» on an entry he collected («… Ignatij Aleksejeviĉ Boĵok … [T. Ŝĉavinskij.]»): his line is the
                # collector's
                if not e["name"]: why = "kept: the extractor does not parse the entry"
                elif not names_him(key, e["name"]) and e["collector"] and names_him(key, e["collector"]):
                    new = [AX.collector_line(e, et, s, y, n, item, para, hp, conf)]; why = "the collector's line (September: «Registered as»)"
                elif not names_him(key, e["name"]): why = f"dropped: la registrito estas «{e['name']}», ne {key} (la nomo estas strato, urbo aŭ profesio en la ero)"
                elif H.slug(key) in held[f"{item}, ¶ {para}"]: why = "twin: the extractor's line"
                else: new = AX.person_lines(e, et, s, y, n, item, para, hp, conf, gz, cnt)
        elif im:
            forms = [(f.rsplit(" ", 1)[0].strip(), int(f.rsplit(" ", 1)[1])) for f in im.group(2).split(", ") if re.search(r" \d+$", f)]
            inits = {re.sub(r"[^A-Za-zĈĜĤĴŜŬ]", "", f.split()[0]).lower() for f, _c in forms if len(f.split()) > 1}
            if len(inits) > 1: why = "kept: the forms bear different initials (two people under one key?)"
            else:
                want = {_form(f) for f, _c in forms}
                hits = [(e, x) for (s, n), x in sorted(ents.items()) if s0 <= s <= s1
                        for e in [AX.marked(AX.parse(s, x[5]), W, x[0], n, s, x[5])] if e["collector"] and _form(e["collector"]) in want]
                for e, (item, para, s, y, n, et) in hits:
                    new.append(AX.collector_line(e, et, s, y, n, item, para, hp, conf))
                if len(hits) != int(im.group(1)): cnt["runs not of the count"] += 1; why = f"{len(hits)} of the {im.group(1)} entries found by the forms"
                if not hits: why = "kept: no entry with the forms " + "; ".join(f for f, _c in forms)
        elif t.split(" · ")[1].startswith("Introduced"):
            fm, nm = re.search(r"to the Adresaro as \[([^\]]+)\]", t), REG_NO.search(t)
            got = entry(s0, int(nm.group(1))) if nm else None
            if not (fm and got): why = "kept: no entry of that series and number"
            elif _form(got[0]["collector"]) != _form(fm.group(1)): why = f"kept: the entry's collector is «{got[0]['collector']}»"
            else:
                e, (item, para, s, y, n, et) = got
                new = [AX.collector_line(e, et, s, y, n, item, para, hp, conf)]
        else:
            why = "kept: neither a registration nor an introduction (a statistic, an identification)"
        ok = 0
        for line in new:
            ps = line.split(" · ")
            line = " · ".join(ps[:-2] + [DA.themes(ps[2]), DA.bracket(ps[-1])])
            rec, err = H.parse(H.to2(H.take_kind(line)[0]))
            if not err: err = H.strict(rec, True)
            if err: refused.append((pid, err, line)); continue
            out.append(line); ok += 1
        st = ("ported" if ok or why.startswith("twin") else "dropped" if why.startswith("dropped")
              else "kept" if why.startswith("kept") or not new else "refused")
        cnt[st] += 1
        done.append([pid, r["file"], r["line"], r["person"], st, why, t])
    print(f"{len(rows)} Adresaro lines: " + ", ".join(f"{k} {v}" for k, v in cnt.most_common()) + f"; {len(out)} format-4 lines, {len(refused)} refused")
    if "--show" in args:
        for d in done:
            if d[4] != "ported" or d[5]: print(f"  {d[0]} {d[3]}: {d[4]} · {d[5]}")
        for pid, why, body in refused[:6]: print(f"  {pid}: {why[:80]} · {body[:220]}")
    if not write: return 0
    fo = os.path.join(GEN, "profiles", "by-source", f"old-format-port-{tag}.md")
    fd = os.path.join(D, f"port-done-{tag}.tsv"); fa = os.path.join(D, f"port-apply-{tag}.md")
    ex = [f for f in (fo, fd, fa) if os.path.exists(f)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(f, GEN) for f in ex))
    with open(fo, "x", encoding="utf-8") as fh:
        fh.write(f"# La malnovaj linioj de la Adresaro al formato 4 ({tag})\n\nfacts-format: 4\n\n`[Ezri, {tag}, per tools/old-format-port.py adresaro: "
                 "la malnovaj linioj de septembro pri la Adresaro de Zamenhof, kiujn neniu linio de formato 4 ripetis, skribitaj de "
                 f"tools/adresaro-extract.py el la serio kaj la numero de ilia ero, sen legilo; la identigo tiu de septembro. "
                 f"La malnova linio de ĉiu: dowse/old-format-port/port-done-{tag}.tsv.]`\n\n")
        for l in out: fh.write(l + "\n")
    with open(fd, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "file", "line", "person", "status", "why", "text"]); w.writerows(done)
    with open(fa, "x", encoding="utf-8") as fh:
        fh.write(f"# The Adresaro lines of tag {tag}, by tool\n\n{len(rows)} lines: " + ", ".join(f"{k} {v}" for k, v in cnt.most_common())
                 + f".\n\n{len(out)} format-4 lines written to `profiles/by-source/old-format-port-{tag}.md`; {len(refused)} refused.\n\n## Not ported, or not whole\n\n")
        for d in done:
            if d[4] != "ported" or (d[5] and not d[5].startswith("twin")): fh.write(f"- {d[0]} `{d[1]}` l. {d[2]} {d[3]}: {d[4]} · {d[5]}\n")
        fh.write("\n## Refused\n\n")
        for pid, why, body in refused: fh.write(f"- {pid}: {why} · {body[:300]}\n")
    print(f"  wrote {os.path.relpath(fo, GEN)}, {os.path.relpath(fd, GEN)}, {os.path.relpath(fa, GEN)}")
    return 0

# ---------------------------------------------------------------------------------------------------------------- rolls
# THE LINGVA KOMITATO'S ROLLS AND BALLOTS (the editor, 2026-10-31 19:5x: before the harvest too; 21:0x, on the
# names the OCR's small capitals garbled: «legilo»). September's roster run (tools/oge-roster/oge_facts.py) summed each
# person's ballots and roll entries over several volumes into one line, which no one page carries. Its source, the rolls
# and ballots read by eye (tools/oge-roster/oge_curated.py: EVENTS, ROLLS), gives each event apart: one format-4 line
# for each person, record and role, on the record's own pages. The tool writes the line where it finds the person's
# entry in today's text (a roll's entry by its address, else the name with the small capitals' confusions folded); the
# rest go to legiloj, one part a record, with its pages whole. A page an old line cites that no record covers goes to
# the legilo with the old line.
ROLL_CITE = re.compile(r"oge\.(\d) p(\d+)(?:\s*[–-]\s*(\d+))?|oge-rolls/(\d)-0*(\d+)-")
def cite_pages(s, record=False):
    """The (volume, PDF page)s a cite names. A record's extraction file («3-0163-…») gives the extraction's first page,
    not the record's: for a record, only where it cites no page (tag za's part 1 carried the issue's masthead)."""
    out = set()
    ms = list(ROLL_CITE.finditer(s))
    if record and any(not m.group(4) for m in ms): ms = [m for m in ms if not m.group(4)]
    for m in ms:
        if m.group(4): out.add((int(m.group(4)), int(m.group(5)))); continue
        v, a = int(m.group(1)), int(m.group(2)); b = int(m.group(3) or a)
        out |= {(v, p) for p in range(a, (b if a <= b <= a + 40 else a) + 1)}
    return out
BODY_EO = {"LK": "la Lingva Komitato", "A": "la Esperantista Akademio", "AK": "la Esperantista Akademio",
           "KK": "la Konstanta Komitato de la Kongresoj", "IK": "la Internacia Konsilantaro", "AdmK": "la Administra Komitato"}
# role -> (the kind, the fact); {B} the body, {T} the record's title, {n} a tally
ROLE_EO = {
    "voted": ("deliberado: {T}; voĉdonis", "voĉdonis ({T})"),
    "not_voted": ("deliberado: {T}; ne voĉdonis", "ne voĉdonis ({T})"),
    "abstained": ("deliberado: {T}; sindetenis", "sindetenis ({T})"),
    "late": ("deliberado: {T}; voĉo tro malfrua", "sendis sian voĉon tro malfrue ({T})"),
    "lost_in_post": ("deliberado: {T}; voĉo perdita en la poŝto", "sendis voĉon, kiu perdiĝis en la poŝto ({T})"),
    "excused": ("deliberado: {T}; senkulpigita", "estas senkulpigita ({T})"),
    "present": ("deliberado: {T}; ĉeestis", "ĉeestis ({T})"),
    "one_vote": ("deliberado: {T}; ricevis unu voĉon", "ricevis unu voĉon ({T})"),
    "tally": ("deliberado: {T}; ricevis {n} voĉojn", "ricevis {n} voĉojn ({T})"),
    "candidates": ("deliberado: {T}; kandidato", "estas kandidato ({T})"),
    "kept_on_list": ("deliberado: {T}; restis en la listo", "restis en la listo ({T})"),
    "elected": ("ofico: membro, {B}, elektita", "estas elektita membro de {B} ({T})"),
    "proclaimed": ("ofico: membro, {B}, proklamita elektita", "estas proklamita elektita membro de {B} ({T})"),
    "not_elected": ("deliberado: {T}; ne elektita", "ne estas elektita ({T})"),
    "not_reelected": ("ofico: membro, {B}, ne reelektita", "ne estas reelektita en {B} ({T})"),
    "declined_reelection": ("ofico: membro, {B}, ne deziris reelekton", "ne deziris esti reelektita en {B} ({T})"),
    "resigned": ("ofico: membro, {B}, eksiĝo", "eksiĝis el {B} ({T})"),
    "struck": ("ofico: membro, {B}, forstrekita", "estas forstrekita el {B} ({T})"),
    "struck_nonresponse": ("ofico: membro, {B}, forstrekita pro nerespondo", "estas konsiderata eksiĝinta el {B}, ĉar ne respondis ({T})"),
    "struck_anti": ("ofico: membro, {B}, forstrekita", "estas forstrekita el {B} ({T})"),
    "struck_by_academy": ("ofico: membro, {B}, forstrekita de la Akademio", "estas forstrekita el {B} de la Akademio ({T})"),
}
LEGILO_ROLES = {"proxies", "non_members_present", "academy_after", "exempt_academicians", "corrections", "verbatim",
                "offices", "withdrew", "addresses", "died"}   # the record's own words decide: to the legilo, with the reading
# the small capitals' confusions as osr-nomsercxo names them (r ~ n ~ w, g ~ c, d ~ p) and the X the OCR prints for N
# («Korxaxn»); no more (l, t → i made «milita» of ANTILLA)
SC = str.maketrans({"r": "n", "w": "n", "x": "n", "g": "c", "p": "d"})
def _f(s): return re.sub(r"[^a-z ]", "", unicodedata.normalize("NFD", s.lower()))
def _surname(name):
    base = re.sub(r"\s*\(.*", "", name)
    return max(_f(base).split() or [""], key=len)

def roll_name_match(cname, key, qual, quals_of):
    """A curated NAME («ZAMENHOF (Leono)», «DE SAUSSURE») is the old line's person: the same slug; a qualified curated name
    only where the old line's qualifier names it, and an old line with a qualifier takes a bare curated name only where
    no qualified one shares its surname (ZAMENHOF (Leono) is not ZAMENHOF)."""
    base = re.sub(r"\s*\(.*", "", cname).strip()
    if H.slug(base) != H.slug(key): return False
    m = re.search(r"\((.*)\)", cname)
    if m: return bool(qual) and _f(m.group(1)).split()[0] in _f(qual).split()
    return not (qual and any(_f(q).split()[0] in _f(qual).split() for q in quals_of.get(H.slug(base), ())))

def locate(item, pages, cname, printed=""):
    """(line number, the word as read) of the person on the record's pages in today's text, or (None, '')."""
    _p, L, _pw, marks = text(item)
    sur = _surname(cname)
    addr = [w for w in _f(printed.split(",", 1)[1] if "," in printed else "").split() if len(w) >= 5][:4]
    best = None
    for pg in pages:
        sp = page_span(marks, len(L), pg)
        if not sp: continue
        for k in range(sp[0], sp[1] + 1):
            ws = re.findall(r"[^\W\d_]+", L[k - 1])
            fw = [_f(w).replace(" ", "") for w in ws]
            # a roll's entry by its address (its street, not small capitals), two words of it on the line
            if addr and sum(a in _f(L[k - 1]) for a in addr) >= min(2, len(addr)):
                near = [w for w, f in zip(ws, fw) if f and (f == sur or (len(sur) >= 5 and one_edit(f.translate(SC), sur.translate(SC))))]
                return k, (near[0] if near else "")
            for w, f in zip(ws, fw):
                if not f or len(f) < 3: continue
                if f == sur: return k, w
                g, s = f.translate(SC), sur.translate(SC)
                if best is None and len(sur) >= 5 and g[:1] == s[:1] and (g == s or (len(sur) >= 7 and one_edit(g, s))): best = (k, w)
    return best or (None, "")

def rolls(tag, args):
    """rolls TAG --from TAG2 --retry TAG3 [--write]: the old OGE lines of TAG2's unplaced and TAG3's sent back, rebuilt."""
    write = "--write" in args
    sys.path.insert(0, os.path.join(TOOLS, "oge-roster"))
    import oge_curated as C
    recs = [dict(r, _roll=False) for r in C.EVENTS] + [dict(r, _roll=True) for r in C.ROLLS]
    for r in recs: r["_pages"] = cite_pages(r["cite"], record=True)
    quals_of = collections.defaultdict(set)
    for r in recs:
        for nm in [e[0] for e in r.get("entries", [])] + [n for v in r.values() if isinstance(v, (list, dict)) for n in v if isinstance(n, str)]:
            m = re.match(r"(.*?)\s*\((.*)\)", nm)
            if m: quals_of[H.slug(m.group(1))].add(m.group(2))
    old = []
    for f, st in ((f"port-unplaced-{args[args.index('--from') + 1]}.tsv", None), (f"port-done-{args[args.index('--retry') + 1]}.tsv", "retry")):
        for r in csv.DictReader(open(os.path.join(D, f), encoding="utf-8"), delimiter="\t"):
            if (st is None or r["status"] == st) and cite_pages(r["text"]): old.append(r)
    # format-4 lines already held: (slug, item, PDF page)
    # format-4 lines already held: (slug, item, PDF page) → their kinds; a fact of the same kind there is skipped (the
    # OGE's own dowse read the same roll: 245 of the first build's 916 facts stood on such pages)
    heldp = collections.defaultdict(set)
    for f in glob.glob(os.path.join(GEN, "profiles", "by-source", "*.md")):
        t = open(f, encoding="utf-8").read()
        if "facts-format: 4" not in t[:600] or " · oge-" not in t: continue
        for m in re.finditer(r"^- \$\$\$ (.+?) \$\$\$.*?\{(\w+):?.*? · (oge-\d), PDF (\d+)", t, re.M):
            heldp[(H.slug(m.group(1)), m.group(3), int(m.group(4)))].add(m.group(2))
    def role_kind(role):
        return "aperoj" if role == "entry" else "morto" if role == "died" else ROLE_EO[role][0].split(":")[0] if role in ROLE_EO else None
    facts, fid_of, uncovered, cnt = [], {}, [], collections.Counter()
    def add(key, hp, rec, role, extra, o):
        k = (H.slug(key), rec["id"], role)
        if k not in fid_of:
            vol = next(iter(rec["_pages"]))[0]; item = f"oge.{vol}"
            pages = sorted(p for v, p in rec["_pages"] if v == vol)
            twin = bool(role_kind(role)) and any(role_kind(role) in heldp.get((H.slug(key), f"oge-{vol}", p), ()) for p in pages)
            if twin: cnt["facts held already (a format-4 line of the kind on the pages)"] += 1
            fid_of[k] = len(facts) + 1
            facts.append({"fid": f"P{len(facts) + 1}", "key": key, "hp": hp, "rec": rec, "role": role, "extra": extra, "item": item,
                          "pages": pages, "old": [], "twin": twin})
        facts[fid_of[k] - 1]["old"].append((o["file"], o["line"], o["text"]))
    for o in old:
        t = o["text"]
        hp = re.match(r"^- \$\$\$ (.+?) \*\*", t).group(1).strip()
        key = re.match(r"^- \$\$\$ (.+?) \$\$\$", t).group(1)
        qm = re.match(r"^- \$\$\$ .+? \$\$\$ \(([^)]*)\)", t); qual = qm.group(1) if qm else ""
        pages, covered, n0 = cite_pages(t, record=True), set(), len(facts)
        for rec in recs:
            if not rec["_pages"] & pages: continue
            got = False
            for fld, v in rec.items():
                if fld.startswith("_") or fld in ("id", "date", "cite", "kind", "formula", "note", "body", "resign_formula"): continue
                if fld == "entries":
                    for nm, office, printed in v:
                        if roll_name_match(nm, key, qual, quals_of): add(key, hp, rec, "entry", (nm, (office, printed)), o); got = True
                elif isinstance(v, list):
                    for nm in v:
                        if isinstance(nm, str) and roll_name_match(nm, key, qual, quals_of): add(key, hp, rec, fld, (nm, ""), o); got = True
                elif isinstance(v, dict):
                    for nm, val in v.items():
                        if roll_name_match(nm, key, qual, quals_of): add(key, hp, rec, fld, (nm, val if isinstance(val, str) else ", ".join(val)), o); got = True
                        elif isinstance(val, list) and any(roll_name_match(x, key, qual, quals_of) for x in val):
                            add(key, hp, rec, fld + "-of", (nm, ""), o); got = True
            if got: covered |= rec["_pages"]
        left = sorted(pages - covered)
        # the cited pages no record of the person covers: the old line itself, page by page (the first of each run)
        runs = [p for i, p in enumerate(left) if i == 0 or p != (left[i - 1][0], left[i - 1][1] + 1)]
        for v, p in runs: uncovered.append({"fid": None, "key": key, "hp": hp, "item": f"oge.{v}", "pages": [p], "old": [(o["file"], o["line"], o["text"])], "role": "old"})
        cnt["old lines with a record"] += len(facts) > n0
    for u in uncovered:
        u["fid"] = f"P{len(facts) + 1}"; u["rec"] = None; u["extra"] = None; u["twin"] = False; facts.append(u)
    # the tool's own lines, where the person is found
    tool, legilo = [], []
    for fa in facts:
        rec, role = fa["rec"], fa["role"]
        if fa["twin"]: continue
        if role == "old" or role in LEGILO_ROLES or role.endswith("-of"): legilo.append(fa); continue
        nm, x = fa["extra"]
        # a tally the curation could not read sure («51?», «[illegible]»): the legilo reads it
        if role == "tally" and not re.fullmatch(r"\d+(?: \(\d+\))?", x.strip()): legilo.append(fa); continue
        k, w = locate(fa["item"], fa["pages"], nm, x[1] if role == "entry" else "")
        if not k: legilo.append(fa); continue
        fa["found"] = k
        title = (re.search(r"«([^»]+)»", rec["cite"]) or re.search(r"(.*)", rec["id"])).group(1)
        body = BODY_EO.get(rec.get("body") or re.match(r"[A-Za-z]+", rec["id"]).group(0), "la Lingva Komitato")
        if role == "entry":
            # the curation's own notes left out («Germana lingvo (new 1911)», «… [OCR «Beanexor (A.)»; ⚠ …]», «★»); a
            # language heading is the roll's section, not an office
            office = re.sub(r"\s*\([^)]*\)|★", "", x[0]).strip()
            printed = re.sub(r"\s*\[.*$", "", x[1]).strip().rstrip(";,")
            tm = re.search(r",\s*([^,()]+?)\s*\(([^)]+)\)\s*\.?$", printed)
            kind = f"aperoj: nomaro de {body}" + (f"; +loĝado: {tm.group(1).strip()}" if tm else "")
            where = (f", en la sekcio {office}" if re.search(r"lingvo|membroj|anoj", office) else f", kiel {office}") if office else ""
            fact = f"{fa['key']} staras en la nomaro de {body} de {rec['date']}{where}, kun la adreso {printed}"
        else:
            kind, fact = ROLE_EO[role]
            n = x if role == "tally" else ""
            kind, fact = kind.format(T=title, B=body[3:] if kind.startswith("ofico") else body, n=n), f"{fa['key']} " + fact.format(T=title, B=body, n=n)
        _p, L, _pw, marks = text(fa["item"])
        anc = " ".join(L[k - 1].split()[:12]).replace(" · ", " ")
        notes = [f"⟦la legado de septembro: tools/oge-roster/oge_curated.py, {rec['id']}⟧"]
        if w and _f(w).replace(" ", "") != _surname(nm): notes.append(f"OCR «{w}»")
        tool.append((fa, f"- $$$ {fa['hp']} **{rec['date']}** · {{{kind}}} · {fact}. · {anc} · l. {k} · 📣 (sen fontindiko; {'; '.join(notes)})"))
    cnt["facts"], cnt["by the tool"], cnt["to legiloj"] = len(facts), len(tool), len(legilo)
    cnt["old lines"], cnt["pages no record covers (to legiloj, with the old line)"] = len(old), len(uncovered)
    # the legiloj's parts: one a record (its pages whole), and one an uncovered page
    byrec = collections.defaultdict(list)
    for fa in legilo: byrec[(fa["rec"]["id"] if fa["rec"] else f"{fa['item']}-p{fa['pages'][0]}")].append(fa)
    def pages_text(item, pages):
        _p, L, _pw, marks = text(item); out = []
        for pg in pages:
            sp = page_span(marks, len(L), pg)
            if sp: out.append((pg, [(k, L[k - 1]) for k in range(sp[0], min(sp[1], sp[0] + 149) + 1)]))
        return out
    parts = list(byrec.values())
    words = sum(sum(len(x.split()) for _pg, ls in pages_text(p[0]["item"], p[0]["pages"]) for _k, x in ls) + 60 * len(p) for p in parts)
    group = 3
    groups = [list(range(i + 1, min(i + group, len(parts)) + 1)) for i in range(0, len(parts), group)]
    print(", ".join(f"{k} {v}" for k, v in cnt.items()) + f"; {len(parts)} parts, {len(groups)} legiloj, about {words:,} words handed out")
    if "--show" in args:
        for fa, l in tool[::max(1, len(tool) // int(args[args.index('--show') + 1]))]:   # spread over the whole
            print("  ", re.sub(r" · 📣.*", "", l)[:260])
    if not write: return 0
    files = [os.path.join(D, f"rolls-facts-{tag}.tsv"), os.path.join(D, f"rolls-tool-{tag}.md"), os.path.join(D, f"port-rows-{tag}.tsv"),
             os.path.join(GEN, "dowse", f"workflow-readers-{tag}.json")]
    files += [os.path.join(D, f"port-lines-{tag}-{n}.md") for n in range(1, len(parts) + 1)]
    names = [f"{tag}-g{g[0]}-{g[-1]}" if len(g) > 1 else f"{tag}-{g[0]}" for g in groups]
    files += [os.path.join(D, f"facts-brief-{nm}.md") for nm in names]
    ex = [f for f in files if os.path.exists(f)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(f, GEN) for f in ex))
    with open(files[0], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["fid", "person", "record", "role", "item", "pages", "how", "old lines (file, line)", "old texts"])
        legset = {id(fa) for fa in legilo}
        for fa in facts:
            w.writerow([fa["fid"], fa["key"], fa["rec"]["id"] if fa["rec"] else "", fa["role"], fa["item"], " ".join(map(str, fa["pages"])),
                        "twin" if fa["twin"] else "legilo" if id(fa) in legset else "tool", " | ".join(f"{a}:{b}" for a, b, _t in fa["old"]), " ⁂ ".join(t for _a, _b, t in fa["old"])])
    with open(files[1], "x", encoding="utf-8") as fh:
        fh.write(f"# The rolls by tool ({tag})\n\n")
        for fa, l in tool: fh.write(f"{fa['fid']} · {l}\n")
    with open(files[2], "x", encoding="utf-8", newline="") as fr:
        w = csv.writer(fr, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "part", "file", "line", "person", "item", "page", "found", "how", "text"])
        for n, part in enumerate(parts, 1):
            p0 = part[0]
            with open(os.path.join(D, f"port-lines-{tag}-{n}.md"), "x", encoding="utf-8") as fh:
                rec = p0["rec"]
                fh.write(f"# La parto {n} ({tag})\n\n")
                if rec:
                    fh.write(f"**La dokumento:** {rec['cite']}, dato {rec['date']}.\n\n" + (f"**Ĝia formulo:** {rec['formula']}\n\n" if rec.get("formula") else ""))
                for fa in part:
                    if fa["role"] == "old":
                        fh.write(f"## {fa['fid']} · {fa['key']} · la malnova linio, sur PDF {fa['pages'][0]}\n\n**La malnova linio:** {fa['old'][0][2]}\n\n"
                                 "(Skribu nur tion, kion la malnova linio diras pri ĉi tiu paĝo.)\n\n")
                    else:
                        nm, x = fa["extra"]
                        what = (f"staras en la nomaro, presita: «{x[1]}»" + (f" (ofico: {x[0]})" if x[0] else "")) if fa["role"] == "entry" else \
                               f"rolo «{fa['role']}» en ĉi tiu dokumento" + (f": {x}" if x else "")
                        fh.write(f"## {fa['fid']} · {fa['key']} (en la dokumento: {nm}) · {what}\n\n")
                    w.writerow([fa["fid"], n, fa["old"][0][0], fa["old"][0][1], fa["key"], fa["item"], fa["pages"][0], "", fa["role"], fa["old"][0][2]])
                fh.write(f"## La eltiraĵo (`{p0['item']}`)\n\n")
                for pg, ls in pages_text(p0["item"], p0["pages"]):
                    fh.write(f"### PDF {pg}\n\n```\n" + "".join(f"{k}| {x}\n" for k, x in ls) + "```\n\n")
    for g, nm in zip(groups, names):
        plist = "\n".join(f"{n}: `{D}/port-lines-{tag}-{n}.md`" for n in g)
        with open(os.path.join(D, f"facts-brief-{nm}.md"), "x", encoding="utf-8") as fh:
            fh.write(ROLLS_BRIEF.format(tag=tag, gname=f", {nm}", kinds=KINDS_DOC, dir=D, parts=plist,
                                        nparts=(f"vi legas {len(g)} partojn, unu post la alia" if len(g) > 1 else "vi legas unu parton")))
    with open(files[3], "x", encoding="utf-8") as fh:
        json.dump({"sources": [{"dir": D, "tag": tag, "groups": [nm[len(tag) + 1:].lstrip("g") for nm in names]}]}, fh, ensure_ascii=False)
    print(f"  wrote {len(files)} files under dowse/old-format-port/ and dowse/workflow-readers-{tag}.json")
    return 0

ROLLS_BRIEF = BRIEF.split("**La tasko.**")[0] + """**La tasko.** Via parto estas unu dokumento de la *Oficiala Gazeto Esperantista* (listo de membroj, protokolo de voĉdono, cirkulero …) kun la hodiaŭa teksto de ĝiaj paĝoj (la linioj kun sia numero antaŭ «|»). En septembro la projekto legis tiun dokumenton per la okulo, ankaŭ sur la paĝbildo, kaj ĉiu **P-numero** diras, kion tiu legado trovis pri unu persono: ĝia rolo en la dokumento («voted» = voĉdonis, «not_voted» = ne voĉdonis, «elected» = elektita, «tally» = la nombro de voĉoj, «resigned» = eksiĝis, «struck…» = forstrekita, «present» = ĉeestis, «proxies» = prokuroj, «offices» = ofico, «died» = mortis, …) aŭ ĝia linio en nomaro. La nomoj en tiuj dokumentoj estas presitaj per kapitaletoj, kiujn la OCR misas («Korxaxn» = Kofman, «Tarxev» = Talmey). Por ĉiu P-numero: **trovu la personon en la eltiraĵo** (ankaŭ misformitan) kaj skribu la fakton kiel unu linion de formato 4 (sube), komence kun sia P-numero: `P12 · - $$$ NOMO $$$ …`; la ankro estas la linio de la persono. **Se vi ne trovas la nomon** en la eltiraĵo, skribu la linion tamen, kun la ankro ĉe la kapo de la listo aŭ de la dokumento, kaj en la voĉo `📣 (la nomo ne trovita en la OCR; la fakto el la legado de septembro)`. Skribu `P12 · forigu: kialo` nur se la teksto klare diras alion ol la P-numero. P-numero «la malnova linio» donas malnovan linion kaj unu paĝon: skribu nur tion, kion la eltiraĵo de tiu paĝo portas pri la persono, aŭ `forigu`. Ĉiu P-numero ricevas almenaŭ unu linion.

""" + "**La linio:**" + BRIEF.split("**La linio:**")[1]

def rolls_apply(tag, args):
    """rolls-apply TAG [--write]: the tool's lines and the legiloj's returns joined; the old lines' statuses."""
    write = "--write" in args
    DA = load("dfa", "dowse-facts-assemble.py")
    facts = list(csv.DictReader(open(os.path.join(D, f"rolls-facts-{tag}.tsv"), encoding="utf-8"), delimiter="\t"))
    item_of = {f["fid"]: f["item"] for f in facts}
    bodies = collections.defaultdict(list)
    for l in open(os.path.join(D, f"rolls-tool-{tag}.md"), encoding="utf-8"):
        m = RET.match(l.rstrip("\n"))
        if m: bodies[m.group(1)].append(m.group(2).strip())
    for p in glob.glob(os.path.join(D, f"facts-return-{tag}-*-p*.md")):
        for l in open(p, encoding="utf-8"):
            m = RET.match(l.rstrip("\n"))
            if m and item_of.get(m.group(1)): bodies[m.group(1)].append(m.group(2).strip())
    out, refused, st = [], [], {}
    for f in facts:
        if f["how"] == "twin": st[f["fid"]] = ("ported", ""); continue
        got = []
        for b in bodies.get(f["fid"], []):
            if b.lower().startswith("forigu"): got.append(("dropped", b.split(":", 1)[1].strip() if ":" in b else "")); continue
            if not b.startswith("- $$$"): refused.append((f["fid"], "nek linio nek forigo", b)); continue
            line, err = expand_body(b, f["item"], DA)
            if err: refused.append((f["fid"], err, line)); continue
            out.append(line); got.append(("ported", ""))
        st[f["fid"]] = ("ported" if any(s == "ported" for s, _ in got) else "dropped" if got else "not returned",
                        "; ".join(x for s, x in got if s == "dropped" and x))
    # an old line: ported once every fact of it has a line or a drop; its drops named
    per = collections.OrderedDict()
    for f in facts:
        for (fl, tx) in zip(f["old lines (file, line)"].split(" | "), f["old texts"].split(" ⁂ ")):
            per.setdefault((fl, tx), []).append(f["fid"])
    done = []
    for (fl, tx), fids in per.items():
        ss = [st[x] for x in fids]
        s = "not returned" if any(a == "not returned" for a, _ in ss) else "ported" if any(a == "ported" for a, _ in ss) else "dropped"
        why = "; ".join(f"{x}: {w}" for x, (a, w) in zip(fids, ss) if a == "dropped") or ""
        file, line = fl.rsplit(":", 1)
        person = re.match(r"^- \$\$\$ (.+?) \$\$\$", tx).group(1)
        done.append([",".join(fids), file, line, person, s, (f"{len(fids)} facts" + (f"; dropped {why}" if why else "")), tx])
    c = collections.Counter(d[4] for d in done)
    print(f"{len(facts)} facts, {len(done)} old lines: " + ", ".join(f"{k} {v}" for k, v in c.most_common()) + f"; {len(out)} format-4 lines, {len(refused)} refused")
    if "--show" in args:
        for fid, why, body in refused[:8]: print(f"  {fid}: {why[:80]} · {body[:200]}")
    if not write: return 0
    fo = os.path.join(GEN, "profiles", "by-source", f"old-format-port-{tag}.md")
    fd = os.path.join(D, f"port-done-{tag}.tsv"); fa = os.path.join(D, f"port-apply-{tag}.md")
    ex = [x for x in (fo, fd, fa) if os.path.exists(x)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(x, GEN) for x in ex))
    with open(fo, "x", encoding="utf-8") as fh:
        fh.write(f"# La ruloj kaj voĉdonoj de la Lingva Komitato al formato 4 ({tag})\n\nfacts-format: 4\n\n`[Ezri, {tag}, per tools/old-format-port.py rolls: "
                 "la malnovaj linioj de septembro, kiuj sumis la voĉdonojn kaj la nomarojn de persono tra pluraj volumoj, "
                 "dividitaj laŭ la legado de septembro (tools/oge-roster/oge_curated.py) en po unu linio por dokumento kaj rolo, "
                 f"sur la propraj paĝoj de la dokumento; skribitaj de la ilo aŭ de legiloj. La malnovaj linioj: dowse/old-format-port/port-done-{tag}.tsv.]`\n\n")
        for l in out: fh.write(l + "\n")
    with open(fd, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "file", "line", "person", "status", "why", "text"]); w.writerows(done)
    with open(fa, "x", encoding="utf-8") as fh:
        fh.write(f"# The rolls of tag {tag}\n\n{len(facts)} facts, {len(done)} old lines: " + ", ".join(f"{k} {v}" for k, v in c.most_common())
                 + f".\n\n{len(out)} format-4 lines written to `profiles/by-source/old-format-port-{tag}.md`; {len(refused)} refused:\n\n")
        for fid, why, body in refused: fh.write(f"- {fid}: {why} · {body[:300]}\n")
    print(f"  wrote {os.path.relpath(fo, GEN)}, {os.path.relpath(fd, GEN)}, {os.path.relpath(fa, GEN)}")
    return 0

# --------------------------------------------------------------------------------------------------------------- places
# THE LAST OF THE OLD LINES (the editor, 2026-10-31 21:4x): lines that
# name several places, a person's first and last dated appearance in a run, an office printed over several years. Each
# place the line names (its own field, the places written in it as old-format-supersede.py reads them, the quotation
# over the whole item where it gives no page) is a P-number of its own, placed and handed out as prep does; the legilo
# writes what that place carries about the person, or drops a place whose hit is another word or another person.
# Not handed out: the Adresaro's (by hand), a line whose image is asked for, and research notes, no fact about a person
# at a place (an absence, a count, a body or a journal at the head).
NOTE_KEYS = {"AKADEMIO", "LESPERANTISTE", "SFPE"}
def is_note(r):
    t = r["text"]
    return (r["person"] in NOTE_KEYS or " NULL " in t or "⇒" in t
            or re.search(r"themes-|-register-vols|ballots-check", r["file"]) is not None)

def places(tag, args):
    write = "--write" in args
    per = int(args[args.index("--parts") + 1]) if "--parts" in args else 25
    hold = set(args[args.index("--hold") + 1].split(",")) if "--hold" in args else set()
    SU = load("ofs", "old-format-supersede.py"); items = SU.Items()
    reg, rows = register()
    todo, skipped = [], collections.Counter()
    for r in rows:
        if r["status"] != "kept, no twin": continue
        if r["item"].startswith("adresaro-"): skipped["the Adresaro's, by hand"] += 1; continue
        if r["person"] in hold: skipped["held (an image asked for)"] += 1; continue
        if is_note(r): skipped["research notes"] += 1; continue
        todo.append(r)
    placed, unplaced, how = [], [], collections.Counter()
    for r in todo:
        ps = [(r["item"], int(r["page"]))] if r["item"] and r["page"] else []
        for it, pg, _nm in SU.inline_cites(r["text"], items):
            if (it, pg) not in ps: ps.append((it, pg))
        got = []
        for it, pg in ps[:4]:
            p = place(dict(r, item=it, page=str(pg)))
            if p: got.append((dict(r, item=r2_item(it, p)), p))
        # THE SEPTEMBER LINE ITSELF (2026-10-31 22:0x, the editor on the 34 left): a line that cites
        # September's text by its line («`…zakrzewski-historio-1913.txt:5411`», «`enciklopedio-de-esperanto-1933.txt`
        # L2209», «AmerikaEsperantisto.1910.v8n4.txt l.3996», an extract file's «l.195») is found by that line's own words
        # in today's text, as a quotation is; else the page the cite writes («f.p. 10», «l.566 p.12», an extract's «-p11-»)
        if not got and r["item"] and text(r["item"]):
            for sp in sept_places(r):
                if sp[0] == "line": got.append((r, (sp[1], sp[2], "la septembra linio")))
                else:
                    p = place(dict(r, page=str(sp[1])))
                    if p: got.append((r, p))
                if len(got) >= 4: break
        if not ps and not got and r["item"]:
            p = place(dict(r, page=""))
            if p and p[2] != "la paĝo": got.append((r, p))
        # last: in a single issue, the first line where the surname stands as a word (a «FIRST dated appearance» whose
        # September line the OCR has since read otherwise); the legilo judges it
        if not got and r["item"] and text(r["item"]) and "FIRST dated appearance" in r["text"]:
            _p, _L, pw, marks = text(r["item"])
            sur = max(FID.norm(re.sub(r"\(.*", "", r["person"])).split() or [""], key=len)
            hit = next(((p, ln) for p in sorted(pw) for w, ln in pw[p] if w == sur), None) if len(sur) >= 4 else None
            if hit: got.append((r, (hit[1], hit[0], "la nomo sola")))
        if not got: unplaced.append(r); continue
        for k, (rr, (ln, pg, h)) in enumerate(got, 1):
            how[h] += 1; placed.append((rr, ln, pg, h, k, len(got)))
    parts = [placed[i:i + per] for i in range(0, len(placed), per)]
    groups = [list(range(i + 1, min(i + 3, len(parts)) + 1)) for i in range(0, len(parts), 3)]
    words = sum(len(r["text"].split()) + sum(len(x.split()) for _k, x in passage(r, ln, pg)) for r, ln, pg, _h, _k, _n in placed)
    print(f"register {os.path.relpath(reg, GEN)}: {len(todo)} lines (" + ", ".join(f"{k} {v}" for k, v in skipped.items()) + " left out); "
          f"{len(placed)} places of {len(todo) - len(unplaced)} lines ({dict(how)}), unplaced {len(unplaced)}; {len(parts)} parts, "
          f"{len(groups)} legiloj; about {words:,} words handed out")
    if "--show" in args:
        for r in unplaced: print("   unplaced:", r["person"], r["item"], "|", r["text"][:150])
    if not write: return 0
    files = [os.path.join(D, f"port-rows-{tag}.tsv"), os.path.join(D, f"port-unplaced-{tag}.tsv"), os.path.join(GEN, "dowse", f"workflow-readers-{tag}.json")]
    files += [os.path.join(D, f"port-lines-{tag}-{n}.md") for n in range(1, len(parts) + 1)]
    names = [f"{tag}-g{g[0]}-{g[-1]}" if len(g) > 1 else f"{tag}-{g[0]}" for g in groups]
    files += [os.path.join(D, f"facts-brief-{nm}.md") for nm in names]
    ex = [f for f in files if os.path.exists(f)]
    if ex: sys.exit("refused, nothing written: exists: " + ", ".join(os.path.relpath(f, GEN) for f in ex))
    pid = 0
    with open(files[0], "x", encoding="utf-8", newline="") as fr:
        w = csv.writer(fr, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "part", "file", "line", "person", "item", "page", "found", "how", "text"])
        for n, part in enumerate(parts, 1):
            with open(os.path.join(D, f"port-lines-{tag}-{n}.md"), "x", encoding="utf-8") as fh:
                fh.write(f"# La parto {n} ({tag})\n\n")
                for r, ln, pg, h, k, nk in part:
                    pid += 1
                    w.writerow([f"P{pid}", n, r["file"], r["line"], r["person"], r["item"], pg, ln or "", h, r["text"]])
                    note = (f" · loko {k} el {nk} de la malnova linio: skribu nur tion, kion ĉi tiu loko portas pri la persono; se la "
                            "trafo ĉi tie estas alia vorto aŭ alia persono, `forigu`") if nk > 1 else ""
                    fh.write(f"## P{pid} · `{r['item']}` PDF {pg} (trovita per {h}){note}\n\n**La malnova linio:** {r['text']}\n\n**La eltiraĵo:**\n\n```\n")
                    for kk, x in passage(r, ln, pg): fh.write(f"{kk}| {x}\n")
                    fh.write("```\n\n")
    with open(files[1], "x", encoding="utf-8", newline="") as fu:
        w = csv.writer(fu, delimiter="\t", lineterminator="\n")
        w.writerow(["file", "line", "person", "item", "page", "text"])
        for r in unplaced: w.writerow([r["file"], r["line"], r["person"], r["item"], r["page"], r["text"]])
    for g, nm in zip(groups, names):
        plist = "\n".join(f"{n}: `{D}/port-lines-{tag}-{n}.md`" for n in g)
        with open(os.path.join(D, f"facts-brief-{nm}.md"), "x", encoding="utf-8") as fh:
            fh.write(BRIEF.format(tag=tag, gname=f", {nm}", kinds=KINDS_DOC, dir=D, parts=plist,
                                  nparts=(f"vi legas {len(g)} partojn, unu post la alia" if len(g) > 1 else "vi legas unu parton")))
    with open(files[2], "x", encoding="utf-8") as fh:
        json.dump({"sources": [{"dir": D, "tag": tag, "groups": [nm[len(tag) + 1:].lstrip("g") for nm in names]}]}, fh, ensure_ascii=False)
    print(f"  wrote {len(files)} files under dowse/old-format-port/ and dowse/workflow-readers-{tag}.json")
    return 0

SEPT_CITE = re.compile(r"((?:[\w.\-]+/)*[\w.\-…]*?[\w-])\.txt`?\s*(?::|L|l\.\s?)(\d+)")
SEPT_PAGE = re.compile(r"\.txt`?\s+(?:f\.p\.\s?|l\.\s?\d+\s+p\.\s?)(\d+)|-p0*(\d+)-[\w-]*\.txt")
def sept_file(path):
    """September's copy of a text cited by name or by path: under sources/, never today's text directories."""
    path = path.lstrip("…").strip()
    if "/" in path:
        p = os.path.join(GEN, path if path.startswith("sources/") else "sources/" + path) + ".txt"
        return p if os.path.isfile(p) else None
    cands = [p for p in glob.glob(os.path.join(GEN, "sources", "*", path + ".txt"))
             if os.path.basename(os.path.dirname(p)) not in TEXT_DIRS + ("ocr-rendersearch",) or os.path.basename(os.path.dirname(p)) == "ocr"]
    return sorted(cands, key=lambda p: os.path.basename(os.path.dirname(p)) != "ocr")[0] if cands else None

def sept_places(r):
    """[("line", today's line, page) or ("page", page)] from the September cites of an old line."""
    out, item = [], r["item"]
    _p, _L, pw, marks = text(item)
    for m in SEPT_CITE.finditer(r["text"]):
        f = sept_file(m.group(1))
        if not f: continue
        SL = open(f, encoding="utf-8", errors="replace").read().split("\n")
        n = int(m.group(2))
        if not 0 < n <= len(SL): continue
        # the line itself, else with two lines either side (a short line, «€. Aymonier, en La Revuo», finds no run of four)
        for a, b in ((n - 1, n + 1), (max(0, n - 3), n + 2)):
            words = FID.norm(" ".join(SL[a:b])).split()
            ln = find_anywhere(item, pw, words) if len(words) >= 4 else None
            if ln: out.append(("line", ln, page_at(marks, ln))); break
    for m in SEPT_PAGE.finditer(r["text"]):
        pg = int(m.group(1) or m.group(2))
        if not any(o[0] == "page" and o[1] == pg for o in out): out.append(("page", pg))
    seen, uniq = set(), []
    for o in out:
        k = o[2] if o[0] == "line" else o[1]
        if k not in seen: seen.add(k); uniq.append(o)
    return uniq

def r2_item(it, p):
    """The item a place was found in: place() may move an Adresaro line to the series' other piece; else the item."""
    return it

if __name__ == "__main__":
    CMDS = {"prep": prep, "apply": apply, "adresaro": adresaro, "rolls": rolls, "rolls-apply": rolls_apply, "places": places}
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS: sys.exit(__doc__)
    sys.exit(CMDS[sys.argv[1]](sys.argv[2], sys.argv[3:]))
