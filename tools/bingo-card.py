#!/usr/bin/env python3
"""The Schuck-album bingo card, cut mechanically from the harvested profiles (QUEUE B-CARD v0.1, 2026-09-18).

Reads the 106 portrait captions (sources/ocr/schuckAlbumo.captions.txt), maps each to a profile stem, and PROPOSES the
card's tags from the profile's fact lines — every tag carrying the year and locator of the line that earned it:

  † <year> death, on every timeline where known; the timeline ENDS there.   ‡ died before the end of 1908 (never faced the choice)
  🟨 voted for reform in the 1894 ballot (anything but point I)
  Ⓚ  Lingva Komitato          Ⓐ  Akademio
  🟦 Ido adherent ([B] with an Ido marker)      💙 Ido sympathiser ([X]-only with an Ido marker)
  🟧 other auxlang adherent ([B])               🧡 other auxlang sympathiser
  🟢 returned (a green act dated after a blue/orange)   🟩 stayed (default — everyone on the card is an Esperantist)
  🔴 struck FOR DISLOYALTY (the institution's formula names it)   ⭕ struck WITHOUT a disloyalty formula (silence etc.)
  ⭘ RESIGNED (the man's own «eksiĝis» — 2026-09-19, hand-only, black hollow circle; NOT a strike)
  HEARTS = SYMPATHY (editor 2026-09-19 23:30): 💛 for reform before the Aug 1894 vote · 💚 for the language as it was, before the vote · 💙 Ido sympathiser · 🧡 other-auxlang sympathiser (all hand-confirm; the squares are ACTS, the hearts are LEANINGS)
  ◐ DOUBLE MEMBERSHIP (2026-09-19): an LK/Akademio seat, vote or session held after a camp square, until the strike — a tag, span-dated
  ⬛ RENOUNCED (widened 2026-09-20): publicly renounced world languages (the editor, 2026-11-06), adhering nowhere else — the man's act (Kabe 1931, Moch 1933); ⬜ stays the lapse
  ⬜ (a lapse: the man got too busy) HAND-ONLY; 💙/🧡 HAND-ONLY (bylines in a rival organ prove nothing); 🟢 HAND-ONLY; ⬛ proposed only from an EdE-type «rejected the idea» line

Outputs, in geniza/bingo-card/ (moved there 2026-10-31, the editor): bingo-card-v<ver>.csv, bingo-card-v<ver>.md, and P-SRC / P-GAP v<ver> (sources cited by the
evidence lines; cells with no evidence / ❓ / HAND-PASS). No colour without a fact line behind it: a proposal with no line is
written as «?» and flagged. The script reads; the human reads the diff.
"""
import collections, csv, importlib.util, os, re, sys, unicodedata
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
CAPTIONS = os.path.join(GEN, "sources", "ocr", "schuckAlbumo.captions.txt")
PROFILES = os.path.join(GEN, "profiles")
VER = os.environ.get("BINGO_VER", "0.1")

# the harvester's tables, for surname → stem
spec = importlib.util.spec_from_file_location("hf", os.path.join(HERE, "harvest-facts.py"))
hf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hf)

def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")

# --- caption → stem -------------------------------------------------------------------------------------------------
# Hand-map for captions the surname rule cannot resolve (album spelling → profile stem). Extend as the diff shows.
HAND = {
    "beaufront": "de-beaufront", "de beaufront": "de-beaufront", "saussure": "de-saussure", "de saussure": "de-saussure",
    "menil": "de-menil", "de menil": "de-menil", "dombrovski": "dambrauskas", "dombrowski": "dambrauskas",
    "busutil": "busuttil", "wazniewski": "wasniewski", "oreŝkoff": "oreskov", "oreskoff": "oreskov",
    "davidoff": "davidov", "dragoumis": "dragoumis", "ĉefeĉ": "hoveler", "cefec": "hoveler", "kabe": "bein", "bein": "bein", "melckebeke": "van-melckebeke",
    "capé-montrosier": "cape", "cape-montrosier": "cape", "derveaux": "dervaux", "costa é almeida": "costa-e-almeida", "costa e almeida": "costa-e-almeida",
    "sepúlveda cuadra": "sepulveda", "sepulveda cuadra": "sepulveda", "ostrowski": "ostrovskij", "johnsen": "hageler",
    "zamenhof": "zamenhof", "de wahl": "de-wahl", "wahl": "de-wahl", "de ladevèze": "de-ladeveze", "ladevèze": "de-ladeveze",
    "schmidt": "schmidt", "meyer": "meyer", "meier": "meier", "lengyel": "lengyel", "de lengyel": "lengyel",
    "laurén": "lauren", "atanasoff": "atanasov", "kanaloŝŝy-lefler": "kanalossi-lefler", "boirac": "boirac",
    "krikortz": "krikortz", "bourlet": "bourlet", "michaux": "michaux", "hodler": "hodler", "privat": "privat",
    "codorníu": "codorniu", "codorniu": "codorniu", "cart": "cart", "mybs": "mybs", "javal": "javal", "sébert": "sebert",
    "grabowski": "grabowski", "ostrovski": "ostrovskij", "postnikov": "postnikov", "asnes": "asnes",
}
NOISE = {"dro", "d-ro", "dr", "prof", "profo", "pro", "sro", "s-ro", "sino", "s-ino", "fino", "f-ino", "lt", "kol", "kolonelo",
         "generalo", "gen", "kapitano", "pastro", "abato", "abbé", "l", "k", "o", "fot", "caudevelle", "mr", "mrs", "miss", "de", "van", "von", "la"}

# --- country (1906 borders), from the album's own town caption; the 15 captions without a town by the profile's town -------
TOWN_COUNTRY = {
    "AALBORG": "Denmark", "ANTVERPENO": "Belgium", "AREZZO": "Italy", "ATENO": "Greece", "BERLINO": "Germany", "BLACKHEATH-LONDONO": "Britain",
    "BORDIGHERA": "Italy", "BRESLAU": "Germany", "BRUSELO": "Belgium", "BUDAPESTO": "Austria-Hungary", "BYSTRICE-HOSTYN": "Austria-Hungary",
    "CHI DAMBURAN": "India", "CREMA": "Italy", "DEN HAAG": "Netherlands", "DIJON": "France", "DUFFEL": "Belgium", "EASTSOUND": "USA",
    "EPERNAY": "France", "FRANKFURTO": "Germany", "HAMBURG-ALTONA": "Germany", "HEULE-COURTRAI": "Belgium", "HILVERSUM": "Netherlands",
    "JYVÄSKYLÄ": "Finland", "KEIGHLEY": "Britain", "KÖNIGSBERG": "Germany", "LA ROCHELLE": "France", "LAUFON": "Switzerland",
    "LIMA": "Peru", "LONDONO": "Britain", "LOUVIERS": "France", "LYON": "France", "MALTA": "Malta (Brit.)", "MONTREAL": "Canada",
    "MURCIA": "Spain", "MÜNCHEN": "Germany", "NAPLO": "Italy", "NEW YORK": "USA", "NURNBERGO": "Germany", "ODESSA": "Russia",
    "ORLÉANS": "France", "PARIZO": "France", "PLOVDIV": "Bulgaria", "POTSDAM": "Germany", "PRAGO": "Austria-Hungary",
    "REZENDE": "Portugal", "RIJKJAVIK": "Iceland", "RIOLUNATO": "Italy", "SANKTA ROZO NEKOKSTLO": "Mexico", "SANTIAGO": "Chile",
    "SCHALKE": "Germany", "SILISTRA": "Bulgaria", "STOCKHOLM": "Sweden", "STUTTGART": "Germany", "TÖNSBERG": "Norway",
    "UNG-HRADISCH": "Austria-Hungary", "VALENCIA": "Spain", "VARSOVIO": "Russia (Poland)", "VIENO": "Austria-Hungary", "ĜENEVO": "Switzerland",
}
STEM_COUNTRY = {  # captions that print no town — from the profile
    "matton": "France", "peltier": "France", "michaux": "France", "deligny": "France", "dervaux": "France", "moch": "France",
    "berthelot": "France", "kofman": "Russia", "asnes": "Russia", "dambrauskas": "Russia (Lithuania)", "avilov": "Russia (Caucasus)",
    "ostrovskij": "Russia (Crimea)", "atanasov": "Bulgaria", "nylen": "Sweden", "midthus": "Norway",
}
def country_of(caption, stem):
    segs = [x.strip() for x in caption.split(" / ") if not x.strip().upper().startswith("FOT")]
    for sg in segs[1:]:
        if re.match(r"^[A-ZĈĜĤĴŜŬÀ-Ý0-9\-\.' ]{3,}(\s*\([^)]*\))?$", sg):
            key = re.sub(r"\s*\(.*\)$", "", sg).strip().rstrip(".")
            key = re.sub(r"\s*\(M\.\)$", "", key)
            for k, v in TOWN_COUNTRY.items():
                if key.startswith(k): return v
            return "? " + key
    return STEM_COUNTRY.get(stem, "?")

def stems():
    return {f[:-3] for f in os.listdir(PROFILES) if f.endswith(".md") and not f.startswith("_")}

def name_of(caption):
    """The name segment of a caption: text before the first ' / ', with 'L. K.' / 'O. K.' / † / photographer credit stripped."""
    segs = [x for x in caption.split(" / ") if not x.strip().upper().startswith("FOT")]
    seg = segs[0] if segs else caption
    seg = re.sub(r"\b[LO]\. ?K\.", "", seg).replace("†", "").strip()
    return seg

def stem_of(caption, allstems):
    seg = name_of(caption)
    key = fold(seg)
    for k, v in HAND.items():
        if fold(k) in key.split() or key.endswith(fold(k)) or (" " + fold(k)) in key:
            if v in allstems: return v, "hand"
    toks = [t for t in re.split(r"[\s,]+", seg) if t and fold(t).strip(".") not in NOISE]
    # try the last token, then the last two (de X, van X), then the harvester's aliases
    cands = []
    if toks:
        cands.append(toks[-1]); cands.append(" ".join(toks[-2:]))
    for c in cands:
        s = hf.slug(hf.canon(c.upper().replace(".", "")))
        if s in allstems: return s, "surname"
        s2 = hf.slug(c)
        if s2 in allstems: return s2, "surname"
    return None, "UNMATCHED"

# --- fact lines --------------------------------------------------------------------------------------------------------
LINE = re.compile(r"^- \$\$\$ (?P<who>[^$]+?) \$\$\$ (?:\((?P<q>[^)]*)\) )?\*\*(?P<year>[^*]+)\*\* · (?P<rest>.*)$")
# 2026-09-19 22:58 — BUCKET FILTER for shared stems (the Lemaire fault): a caption on the card selects ONE person's section of a
# multi-person profile (the harvester's «## <bucket>» headers), plus the shared/undetermined and unassigned sections.
CARD_BUCKET = {
    "lemaire":   [(r"Charles", r"Charles Lemaire"), (r"R[ée]n[ée]", r"René Lemaire")],
    "schmidt":   [(r"Adolf|Potsdam", r"Adolf Schmidt"), (r"Chr\.|Christian|Nürnberg|NÜRNBERG", r"Christian Schmidt")],
    "meier":     [(r"L\. ?E\.|München|MÜNCHEN", r"Ludwig Emil Meier")],
    "lambert":   [(r"Ch\.|Dijon|DIJON", r"Charles Lambert")],
    "kuhnl":     [(r"Ed\.|Eduard", r"Eduard Kühnl")],
    "simon":     [(r"Otto", r"Otto Simon")],
    "trompeter": [(r"W\. ?H\.", r"W\. H\. Trompeter")],
    # the card's man whatever the caption, each now a profile of his own, the shared one only an index (2026-11-06: read as
    # that index they had no lines at all; see NAMESAKE). The album's «St.» is Georgi by its prose, and every witness to the editing
    "atanasov":  [(r"", r"Georgi Atanasov")],
    "postnikov": [(r"", r"Fjodor A\. Postnikov")],
    "lojko":     [(r"", r"Ivan Markoviĉ Lojko")],
    "morin":     [(r"", r"Anselmo Morin")],
}
SHARED_SECTION = re.compile(r"^\(|both|undetermined|other / unidentified|other \w+s \(", re.I)
def lines_of(stem, caption=""):
    out = []
    bucket = None
    for cap_rx, sec_rx in CARD_BUCKET.get(stem, []):
        if re.search(cap_rx, caption or ""): bucket = re.compile(sec_rx); break
    section_ok = True
    path = os.path.join(PROFILES, stem + ".md")
    # A NAMESAKE WITH A PROFILE OF HIS OWN (the harvest's PERSONS split: charles-lemaire.md, rene-lemaire.md,
    # ludwig-emil-meier.md, eduard-kuhnl.md, otto-simon.md …): the caption's person is read there, whole; the shared
    # profile is now only an index and the ambiguous file (2026-10-20, the re-cut that lost their deaths)
    if bucket is not None:
        sec = next(s for c, s in CARD_BUCKET.get(stem, []) if re.search(c, caption or ""))
        own = os.path.join(PROFILES, hf.slug(sec.replace("\\", "")) + ".md")
        if os.path.exists(own): path, bucket = own, None
    for ln in open(path, encoding="utf-8"):
        if bucket is not None and ln.startswith("## "):
            hdr = ln[3:].split(" — ")[0]
            section_ok = bool(bucket.search(hdr)) or bool(SHARED_SECTION.search(hdr))
            continue
        if not section_ok: continue
        m = LINE.match(ln.rstrip("\n"))
        if not m: continue
        rest = m.group("rest")
        if "editor-adjudications-" in rest or "bingo-card-hand-pass" in rest: continue   # 2026-09-19 23:42: the rulings themselves are not evidence — they quote the patterns they rule on
        # THE KINDS FORMAT (2026-10-20; the editor, to
        #): since the our-documents pass a line reads «· {kind: object} · fact · anchor · locator · [tags] · voice»,
        # where the older ones read «· fact · locator · [tags] · voice». The kind field is taken off (so the fact is the
        # text's first field again, as every pattern below expects) and kept; the locator is the field before the tags
        kind = obj = ""
        km = re.match(r"\{([^}:]*)(?::\s*([^}]*))?\} · (.*)$", rest)
        if km: kind, obj, rest = km.group(1).strip(), (km.group(2) or "").strip(), km.group(3)
        tags = re.findall(r"\[([A-Z0-9]+)\]", rest)
        fields = rest.split(" · ")
        ti = next((i for i, f in enumerate(fields) if re.fullmatch(r"(\[[A-Z0-9]+\])+", f.strip())), None)
        loc = fields[ti - 1] if ti and ti >= 1 else (fields[1] if len(fields) > 1 else "")
        # an undated line stays undated: the harvest now writes a guess into the date field («[sen dato; divene ≥ 1931,
        # ≤ 1958 laŭ la paĝoj …]»), whose year is no act's date (Asnes and Gernet lost their ⬜ to a 1931 «guess»)
        ym = None if "sen dato" in m.group("year") else re.search(r"(1[89]\d\d|20\d\d)", m.group("year"))
        out.append(dict(year=int(ym.group(1)) if ym else None, ystr=m.group("year"), tags=tags, text=rest, loc=loc,
                        kind=kind, obj=obj, who=m.group("who")))
    return out

IDO = re.compile(r"\b(Ido|Idist|idist|Uniono|Progreso|adjuvid|Ilo\b|Delegit)", re.I)
IDO_STRONG = re.compile(r"(Akademio (di|de) Ido|Ido-Akademio|Ido Akademi|Uniono .{0,40}(prezid|sekretari|komitat|membr)|Idista (grupo|societo|klubo).{0,40}(prezid|sekretari|fond)|adhes|adhér|Ido-(libro|lernolibro|vortaro)|Idist(a|o) (lernolibro|vortaro)|translated .{0,30} into Ido|en Ido\b.*(verk|libro))", re.I)
OTHER = re.compile(r"\b(Occidental|Novial|Idiom Neutral|Interlingue|Interlingua|IALA|Latino sine|Romanal|Arulo|Gloro|Esperanto II|Antido|Nov-Esperanto|Adjuvilo|own (project|language)|propra projekto|reform-?projekt)", re.I)
OTHER_STRONG = re.compile(r"(Occidental-Union|Occidental .{0,40}(prezid|sekretari|membr|adher)|Novialiste|\bjurie\b|IALA .{0,30}(membr|kunlabor|collabor)|his own (project|language|system)|aŭtoro de .{0,30}(Romanal|Arulo|Gloro|Esperanto II|Antido|Adjuvilo)|publik.{0,20}propra)", re.I)
GREEN = re.compile(r"\b(Esperant|UEA|kongres|Universala Kongreso|Lingva Komitato|Akademio|SAT|revenis|returned|re-?join|denove esperant)", re.I)
LK = re.compile(r"(Lingva Komitato|Lingvo Komitato|\bL\.? ?K\.|LK\b|Komitatano|Lingva-Komitat)", re.I)
LK_MEMBER = re.compile(r"(membro|member|elektit|elected|roll|rolo|nomaro|listo|komitatano|sat on|seat|founding|Boulogne|reelekt|re-elect)", re.I)
AK = re.compile(r"\b(Akademio|Academy|Akademian)", re.I)
AK_MEMBER = re.compile(r"(membro|member|elektit|elected|akademiano|seat|vic-?prezid|co-?opt|balot)", re.I)
DEATH = re.compile(r"(†|\bmortis\b|\bdied\b|\bdeath\b|\bfunebr|\bnekrolog|\bobituar|\bmortpaf|\bmortint)", re.I)
SILENCE = re.compile(r"(ne donis signon de vivo|no sign of life|struck (off|out)|eksigit|eksigo|deemed resigned|konsider.{0,20}eksiĝ|for silence|nericevo de respondo)", re.I)
IDO_GUARD = re.compile(r"\b(Ido)\b", re.I)

# --- the editor's hand rulings: cells the script must not propose (🟢 💙 🧡 ⬜ ⬛ …), with their evidence — appended to the proposal ------
# 2026-10-20 «switch bingo» — the our-documents pass read Boirac's reports on the page: the 1912 four «pro personaj motivoj, decidis
# eksiĝi» (oge.5 PDF 78) and the 1914 nine who «ne deziris prezenti sin denove al la elekto» (oge.7 PDF 43, the page image: «… BENOIT,
# CAPÉ JEAN BOREL, EBNER, KOFMANN kaj BICKNELL», Capé and Jean Borel two men) resigned or did not stand: ⭘, not ⭕. Propagated to
# Gauntlett and Krumpholc, who «sendis sian eksiĝon» on the same page with Zinoviev (his ⭘ 1914 ruled 2026-09-19; theirs dated by the OGE «Eksiĝoj» notice of Nov 1913, which the script had read as a strike). The ⬜ of 2026-09-19
# on six of the nine (ruled as «the default of ⭕») dropped the same day (the editor; see the rows below).
RESIGNED_1912 = ("⭘", 1912, "oge.5 PDF 78 (prese 9), Boirac's report to the Eighth Congress (Kraków, Aug 1912): «pro personaj motivoj, decidis eksiĝi el la Akademio kaj Lingva Komitato»", "RULED 2026-10-20: RESIGNED the Akademio and the LK, 1911–12, for personal reasons — not struck (the editor)")
NOT_STOOD_1914 = ("⭘", 1914, "oge.7 PDF 43 (prese 23), Boirac's report to the Tenth Congress (1914): «pro diversaj kaŭzoj, ne deziris prezenti sin denove al la elekto de la Lingva Komitato» (the page image read 2026-10-20)", "RULED 2026-10-20: did not stand again at the first re-election of the 1905 members — his own choice, not a strike for silence (the editor)")
RESIGNED_1913 = ("⭘", 1913, "oge.6 p161 «Eksiĝoj» (N-ro 5 (60), 25 Nov 1913; sources/oge-rolls/6-0161-eksi…); oge.7 PDF 43 (prese 23): «ne povis, pro granda okupiteco, okupiĝi pri la aferoj de la Komitato, sendis sian eksiĝon» (with Zinoviev)", "RULED 2026-10-20: RESIGNED the LK, Nov 1913 — the «Eksiĝoj» notice the script read as a strike; the tier-(i) formula, as Zinoviev (propagated from the editor's ruling)")

HAND_RULINGS = {
    # 2026-09-18 15:16 ruled by the editor
    "beauchemin": [("🟢", 1919, "The Esperanto Monthly, Sep 1919 — LK-MOVEMENTS-1908-1922.md l.269 (folded to by-source 18 Sep)", "RULED 2026-09-18: returned — at the first Esperanto congress held in Canada, Montreal, «the veteran Esperantist of Canada»; one congress")],
    # 2026-09-18 15:50 — ◈ = UNIFIER, a tag beside the colours («agree about unifier tag»); Zinoviev 💙 not 🟦 («1909 makes Zinoviev not an idist but an ido sympathiser»); Hodler «too mild to include»; Swagers a unifier but not in any canon — noted, not tabled
    "zinoviev":   [("◈", 1908, "zinoviev-unheard-letters-1908-1909.md; the 1909 Barcelona petition «Al prezidantaro kaj anaro de Kvina Esperantista Kongreso en Barcelono» (barcelona-1909-congress OCR)", "RULED 2026-09-18: UNIFIER — the 1908 letters and the 1909 union petition; NOT neutral (published in Progreso, «logikatra», expected Ido to win — zinoviev-unheard-letters l.186)"),
                   ("💙", 1908, "Progreso I N° 6 (Aug 1908) p. 275 «Esperanto ed Esperantismo, da A. Zinoviev»; zinoviev-unheard-letters l.75, l.186", "RULED 2026-09-18: Ido SYMPATHISER, not adherent — wrote for Progreso, called Esperanto «logikatra», by 1909 believed Ido would win; no Ido office, no adhesion"),
                   # 2026-09-19 22:45 ruled by the editor — the declared case (signed «Membro de l'Esperantista Lingva Komitato kaj de la Delegitaro», 1908), kept the seat to his resignation of Feb 1914
                   ("◐", 1908, "Progreso I (Aug 1908) p. 275 signature; oge.7 Feb 1914 «sendis sian ekziĝon el la Lingva Komitato»", "RULED 2026-09-19: DOUBLE MEMBERSHIP 1908–1914, declared in print and kept until his own resignation"),
                   ("⭘", 1914, "oge.7 (Feb 1914; Boirac's report to the Tenth Congress, 1 Jul 1914: «ne povis, pro granda okupiteco»)", "RULED 2026-09-19: RESIGNED the LK, Feb 1914 — the tier-(i) formula, not a strike")],
    "michaux":    [("◈", 1907, "owen-invention-of-romanal-2023.txt l.277–281 (Couturat to Michaux, 22 Jan 1907); Progreso 2a yaro L13412–13418, printed p. 179 (1909)", "RULED 2026-09-18: UNIFIER — the go-between Couturat sent to Zamenhof in Jan 1907; the host Progreso proposed for a reconciliation congress at Boulogne, 1909")],
    "de-saussure": [("◈", 1908, "EsperoKleriga.1908.10-11.txt l.3239–3244 p. 27 (Nov–Dec 1908): Antido's grammar «the first attempt to reconcile the two churches»", "RULED 2026-09-18: UNIFIER — Antido 1907–08, reform from inside meant to reconcile the camps; then Esperanto II")],
    # 2026-09-19 14:10 ruled by the editor — Langlet: resigned the SEF presidency Jul 1909 «pro nesufiĉa batalemo» (LIP); Progreso II crowed («demisis»), the Ora Libro 1937 echoes it («poste sekvis la »deflankiĝon«!»); no roll, no adhesion, no act of his — a lapse, not a defection
    "langlet":    [("⬜", 1909, "Lingvo Internacia Jul 1909 (langlet.md l.121); Progreso 2a yaro L28672–28674; Ora Libro 1937 p. 88 (PDF 104)", "RULED 2026-09-19: confirmed LAPSE — the Ido claim (1909, 1937) is a hostile witness, never an adherence")],
    # 2026-09-19 21:20 — GROUP 1 of the hand pass (bingo-card-hand-pass-2026-09-19.md): «let's add resignation, yes, black hollow circle»
    # ⭘ = the man's own resignation («Eksiĝis el la Lingva Komitato» / «sendis sian eksiĝon»), not an institutional strike; the script's ⭕ suppressed below
    "o-connor":   [("⭘", 1910, "oge.2 p512 «Eksiĝoj» 25 May 1910 — sources/oge-rolls/2-0511-eksigoj.txt", "RULED 2026-09-19: RESIGNED the LK «preferas esti neoficiala ano de Esperanto, ĉar li ne povas partopreni … en la laborojn» — from the committee's work, not from Esperanto; no ⬜")],
    "lambert":    [("⭘", 1910, "oge.2 p512 «Eksiĝoj» 25 May 1910", "RULED 2026-09-19: RESIGNED «liaj nunaj okupoj malebligas ke li sin okupu ageme pri Esperanto»"),
                   ("⬜", 1910, "oge.2 p512 «Eksiĝoj» 25 May 1910", "RULED 2026-09-19: confirmed lapse by his own statement")],
    # 2026-09-20 11:22 ruled by the editor — Seynaeve 💙 1909: «Zamenhof kontre Zamenhof» in the Ido-era Belga Sonorilo (8 Aug 1909), Progreso's «nia samideano»; the 1974 Debrouwere letter a late private witness; the 1911 loyalist credits the counterweight
    "seynaeve":   [("💙", 1909, "belgaSonorilo n113 (8 Aug 1909) «Zamenhof kontre Zamenhof»; Progreso_-_2a_yaro.txt (OCR «D' M. SEyNAvE»); eo.wikipedia (Debrouwere to Sielens, 27 Mar 1974)", "RULED 2026-09-20: Ido SYMPATHISER — an act in the rival organ a month before Barcelona, «nia samideano» in Progreso; the 1974 letter says he went over, sixty-five years on; the LK struck him for silence, not disloyalty, and the loyalist organ credited him the Paĝoj initiative in 1911 — not enough for adhesion"),
                   ("⭕", 1911, "oge.3 p337 «konsiderataj kiel eksiĝintaj, pro nerespondo» 25 Jan 1911", "RULED 2026-09-19: the strike is Jan 1911 (the script's 1909 read the roll transcription's «[struck through in the scan]»); NO ⬜ — a loyalist active 1911–12 (the Paĝoj initiative; Zakrzewski's history)")],
    # 2026-10-20 «drop»: the ⬜ 1914 of 2026-09-19 on these six («confirmed lapse», ruled as the default of the ⭕ now gone) dropped.
    # Rhodes (Yorkshire Federation president 1915–16), Moscheles (signed piece Jun 1917) and Bicknell (BEA councillor 1915, translations
    # printed 1918) stayed active; Capé (killed 1916), Ebner and Junck have no act after 1914 on file, which confirms nothing (O'Connor's
    # case, not Lambert's: no word of their own on leaving Esperanto).
    "rhodes":     [NOT_STOOD_1914],
    "moscheles":  [NOT_STOOD_1914],
    "cape":       [NOT_STOOD_1914],
    "ebner":      [NOT_STOOD_1914],
    "bicknell":   [NOT_STOOD_1914],
    "junck":      [NOT_STOOD_1914],
    "borel":      [NOT_STOOD_1914],
    "benoit":     [NOT_STOOD_1914],
    "hanauer":    [RESIGNED_1912],
    "krumpholc":  [RESIGNED_1913],
    "gauntlett":  [RESIGNED_1913],
    "bagnulo":    [("⬜", 1911, "EsperantoUEA.1911.104.txt l.2866 — UEA «Eksigoj (pro nericevo de respondo je 2-a cito)»", "RULED 2026-09-19: confirmed lapse (default); the institution is UEA, not the LK")],
    # 2026-09-20 00:50 ruled by the editor — ⬛ widened to RENOUNCED (publicly renounced world languages (the editor, 2026-11-06), adhering nowhere else); Kabe ⬛ 1931 on the Literatura Mondo interview supersedes the ⬜
    "bein":       [RESIGNED_1912, ("🟢", 1956, "the editor, 2026-11-06", "RULED 2026-11-06, the editor; no line on the profile yet"), ("⬛", 1931, "literatura-mondo-1931-7-kabe.txt L2553–2725 — the interview of 24 Jun 1931 (bein.md l.201–214)", "RULED 2026-09-20: RENOUNCED — demanded that his no longer being an Esperantist be printed; «ideas entirely unfavourable»; «batalu por via afero»; «eĉ kontraŭulo via»; his Esperanto period «1903–1910»; but «a new genius would create the true solution» — the language rejected, not the idea")],
    # 2026-09-19 22:40 approved — Avilov: the blue dates from his own letter to Progreso, Jul 1908; the 1910 Ido lectures (Brussels, Stockholm) while a sitting LK member are the evidence behind the 🔴 of Jan 1911
    "avilov":     [("🟦", 1908, "Progreso I, Jul 1908, «Letro di S. Avilov» (avilov.md l.49)", "RULED 2026-09-19: Ido ADHERENT from his own letter printed in Progreso, Jul 1908 — «Mi estas tre konvinkita, ke la propono…»; then on the 1909 roll, voting in the LK Jul 1909, Ido lectures in Brussels and Stockholm 1910, the Washington LK session Oct 1910, struck Jan 1911")],
    # 2026-09-19 22:53 approved — Talmey: the blue dates from his April 1908 resignation-for-reform and the Nov 1908 «New York Ilo Society» motion; the orange is Arulo 1924
    "talmey":     [("🟦", 1908, "n082 (Apr 1908) — the resignation and its real reason; the Nov 1908 motion (talmey.md l.39–42, 51–53)", "RULED 2026-09-19: Ido ADHERENT 1908 — resigned the NY society's presidency and membership for reform (Apr), carried the motion to adopt Ido and rename it the «New York Ilo Society» (19 Nov), entered Progreso Tomo I as «eks-prezidanto»"),
                   ("🟧", 1924, "talmey.md l.83 — Arulo, later Gloro; presented 1937 with Einstein present", "RULED 2026-09-19: other auxlang — his own ARULO/GLORO, 1924")],
    # 2026-09-19 22:55 approved — Jamin (Joseph, Brussels): the blue is the schism meeting itself, 20 Sept 1908; the Esperanto-marked lines after it are the League quarrel, not a return
    "jamin":      [("🟦", 1908, "BelgaEsperantisto 1908 n001-002 (the 20 Sept 1908 minutes; declines renewal); Progreso Mar 1909 «Jos. JAMIN»; Pioniro reformist committee 12 May 1909 (jamin.md l.133–144, 175–176)", "RULED 2026-09-19: Ido ADHERENT from 20 Sept 1908 — outgoing general secretary at the schism meeting, declined renewal, contested the loyalist League's title with Lemaire, the Lemonnier reform-translation of 22 Nov; no 🟢 (the later Esperanto lines are the quarrel)")],
    # 2026-09-19 23:03 approved — the two Lemaires confirmed (bucket-filtered rows): Charles 🟦 Oct 1908 (the signed «B. S.» Ido lesson, n93), René 🟦 1909 (first Uniono directory; his own acts 1910–12 later and louder); no 🟢 for either
    "lemaire":    [("⭘", 1908, "oge.1 p84 «Eksiĝoj» 25 Jul 1908 — sources/oge-rolls/1-0084-eksigoj.txt", "RULED 2026-09-19: RESIGNED the LK (Charles AND René, the same notice) three weeks after the confession — the defection's first act")],
    # 2026-09-19 23:12 approved — Moch: 🟦 1912 on his own open letter (n150, 4 Feb 1912); ⬛ re-dated to EdE's «nun» (1933) — the rejection is undated between 1913 and 1933
    "moch":       [("🟦", 1912, "n150 (15 Feb 1912) — open letter to Bollack, Neuilly 4 Feb 1912 (moch.md l.240–243)", "RULED 2026-09-19: Ido ADHERENT — «Je vous adresse … mon adhésion à l'Uniono»; in the same letter «je n'ai pas l'intention de donner ma démission de l'Académie» (the ◐ in his own voice); 🔴 Jul 1912"),
                   ("⬛", 1933, "EdE 1933 s.v. «Moch» (Bastien), enciklopedio-de-esperanto-1933.txt L20942–20956", "RULED 2026-09-19: «Nun li reĵetas eĉ la ideon de artefarita lingvo» — «nun» = 1933; the turn undated between the 1913 adoption and the encyclopaedia — an apostate from the IDEA, where Kabe is an apostate from the language")],
    # 2026-09-19 23:15 approved — Meier (L. E., München/Nürnberg): 🟨 1894 confirmed to him at the roll (442–451 «Meier, Nürnberg»; the Adresaro's only E. Meier, 1298; chief editor of the General-Anzeiger für Nürnberg-Fürth 1893); 🟦 1908 by his own letter; 🟢 1910 by his own letter
    "meier":      [("⭘", 1908, "oge.1 p84 «Eksiĝoj» 25 Jul 1908", "RULED 2026-09-19: RESIGNED the LK with the Lemaires"),
                   ("🟨", 1894, "Esperanto 1894.3.txt l.779 «Meier E. (442)» point 4; Esperanto 1894.1.txt l.2663–2665 «442—451. Meier, Nürnberg»; Adresaro 1298", "RULED 2026-09-19: confirmed — No. 442 heads his own ten-copy block in the March 1894 roll; the Adresaro has no other E. Meier; he edited the General-Anzeiger für Nürnberg-Fürth in 1893 («Meier I. (446)» on the same page checked at the image 20 Sep: a second Nürnberg Meier on one of his ten copies — the block 442–451 was distributed to club members who each voted)"),
                   ("🟦", 1908, "meier.md — his letter of 10 May 1908: «me de nun esas sekura adheranto di Esperanto Simpligita»", "RULED 2026-09-19: Ido ADHERENT by his own letter, May 1908; ⭘ Jul 1908 with the Lemaires"),
                   ("🟢", 1910, "meier.md — his letter to Germana Esperantisto, München 9 Jul 1910: «mi nun por ĉiam forlasis « Idon » kaj ree aldonos min al « Esperanto »»; read at the Augsburg congress banquet Oct 1910; Gautherot translation 1911", "RULED 2026-09-19: RETURNED — the most explicit return formula on the roster; an act (the 1911 anti-Ido translation), not a hello")],
    # 2026-09-19 23:28 approved — Meazzini: 🟦 1925 (his own declaration, Kosmoglott Oct 1925; «trahizanto»; the Ido-Asocio Lusana); the 1937 Occidental line is a SYMPATHY (fights inside the Ido Academy to move Ido towards Occidental) → 🧡, not 🟧
    "meazzini":   [("🧡", 1937, "Cosmoglotta A 114 (May 1937) l.945–947 — his letter of 10 Apr 1937", "RULED 2026-09-19: other-auxlang SYMPATHISER — «il joya que anc Matejka adheret a Occidental» and «lucta in li Ido-Academie por que ti-ci perfectiona Ido in li direction de Occidental»; never an adherent")],
    # 2026-09-19 23:32 approved — Dragoumis: the roster's EARLIEST resignation (Cirkulero 15, 15 Jun 1908 — «Dragumis … eksiĝis el la Lingva Komitato»; the script missed the OGE spelling); 🟦 1908 by Progreso I
    "dragoumis":  [("⭘", 1908, "OGE 1908 n° 1 (25 Jun 1908) p. 14 — Cirkulero 15, 15 Jun 1908 «Eksigoj. — S-roj Dragumis, el Ateno, kaj D. Marignoni, el Crema, eksiĝis el la Lingva Komitato» (oge.1.txt l.1141–1161)", "RULED 2026-09-19: RESIGNED the LK 15 Jun 1908 — a month before the Lemaires and Meier, before the confession was public"),
                   ("🟦", 1908, "progreso1.txt l.25346–25350 (Progreso I p. 408): «S° DRAGOUMIS, membro (greka) di la Delegitaro, ed ex-membro di la Lingva Komitato»; Feb 1909 the Uniono's constitutional debate", "RULED 2026-09-19: Ido ADHERENT 1908")],
    # 2026-09-19 23:34 approved — Krikortz: 🟦 1909 (moved the Swedish split: 24 Jan 1909 motion to strike «Esperanto» from the statutes; 17 May 1909 the Stockholm club's 40–10 vote); ⭘ 30 Nov 1912 («mankas al li tempo»); the 1930 Occidental obituary is a sympathy → 🧡
    "krikortz":   [("🟦", 1909, "krikortz.md l.89–92 — 24 Jan 1909 (Ido column), 17 May 1909 (the club's vote), Jun 1909 (resigns the Sveda Esperantista Societo presidency after the Easter vote)", "RULED 2026-09-19: Ido ADHERENT 1909 — the man who moved the Swedish split; Ido Academy medical sub-committee 1911, Sueda Ido-Federuro 1911, president of the IV Ido congress 1924"),
                   ("⭘", 1912, "OGE «Eksiĝo» notice 25 Jan 1913 — letter of 30 Nov 1912 «ĉar mankas al li tempo por aktive partopreni» (oge.5 p299)", "RULED 2026-09-19: RESIGNED the LK, Nov 1912"),
                   ("🧡", 1930, "Cosmoglotta A 75 (Mar 1931) obituary l.180–220", "RULED 2026-09-19: other-auxlang SYMPATHISER — worked in the Swedish Occidental federation «del comensa» while «apartener anc al Ido-movement til su morte»")],
    # 2026-09-19 23:36 approved — Ahlberg: 🟦 1 Jan 1909 (Esperantisten «transirante Rubikon»); the third camp is NOVIAL 1928, not Occidental 1930 (Cosmoglotta was arguing with him)
    "ahlberg":    [("⭘", 1911, "oge.3 p337 «Eksiĝis el la Lingva Komitato» 25 Jan 1911", "RULED 2026-09-19: RESIGNED (tier i), after 🟦 1909"),
                   ("🟦", 1909, "belgaSonorilo.1908.txt:13984–14003 — Esperantisten «transirante Rubikon» from 1 Jan 1909; «Ad Rubikon» Mar 1909; renamed Svensk Världsspråkstidning", "RULED 2026-09-19: Ido ADHERENT 1 Jan 1909 — took the Swedish organ over; twelve Ido titles 1909–23; editor of Mondo"),
                   ("🟧", 1928, "EdE «de 1928 Novialon»; Jespersen in Politiken 18 May 1928; mondo1928.txt l.3050–3064 (Peus); Novialiste 1938–39 (U27)", "RULED 2026-09-19: other auxlang — NOVIAL from 1928 (the script's Occidental 1930 was Cosmoglotta's «De Wahl contra Per Ahlberg»)")],
    # 2026-09-19 23:40 approved — Schneeberger: 🟦 1908 (15 Sept 1908 letter in Ido to Belga Sonorilo; 26 Oct 1908 the Swiss Ido action-committee while still SES president; Nov 1908 the Delegation's list); Inter-Linguo (ILO) = Ido's 1908 name, not a third language; the script's Ⓐ 1910 was the IDO Academy
    "schneeberger": [("🟦", 1908, "schneeberger.md l.123, 126, 132, 138 — Belga Sonorilo 15 Sept 1908 (in Ido); Künzli 34_ENCYCL_IDO l.111–117 (26 Oct 1908); the Delegation's list 5 Nov 1908; Stenilo", "RULED 2026-09-19: Ido ADHERENT 1908 — co-founded the Swiss Ido action-committee «still the serving president of SES»; the Kurzer Lehrgang der Weltsprache Inter-Linguo (ILO) is an Ido primer under the language's 1908 name; his Linguido / Interlinguo naming proposals 1909")],
    "kofman":     [NOT_STOOD_1914, ("🟢", 1921, "Esperanto (UEA) n-ro 256, Dec 1921 «refariĝis Esperantisto kaj kunlaboras al la Esp. gazeto de Ĥarkov»; the Odessa society's letter 23 May 1922", "RULED 2026-09-18: returned — one gazette, one roll (then Ido again 1922–28, Occidental 1929–)")],
}

# script-proposed glyphs the hand has overruled (2026-09-19 group 1): dropped before output
HAND_SUPPRESS = {"jamin": {"🟧", "🟦"},   # 20 Sep 01:36: «Mez-Voio» 1908 is an esperantido proposal, a middle way, not a third camp
                 "blumenthal": {"Ⓐ"},   # 20 Sep 01:36: eo.wikipedia's «Akademiano» carries no year and is not on the Academy rolls on file
                 "bein": {"⬜", "⭕"},   # 00:50: the ⬛ of 1931 supersedes the script's default grey; 2026-10-20: the ⭕ of 1912 is his resignation, ⭘
                 # 2026-10-20 «switch bingo»: resigned or did not stand, not struck (see RESIGNED_1912 / NOT_STOOD_1914 / RESIGNED_1913)
                 "hanauer": {"⭕"}, "rhodes": {"⭕"}, "moscheles": {"⭕"}, "cape": {"⭕"}, "ebner": {"⭕"}, "bicknell": {"⭕"}, "junck": {"⭕"},
                 "borel": {"⭕"}, "benoit": {"⭕"}, "kofman": {"⭕"}, "krumpholc": {"⭕"}, "gauntlett": {"⭕"},
                 "zamenhof": {"Ⓐ"},   # 23:50: the 1890 line is a PROMISE of a future Akademio, not a seat; he never sat in it
                 "schneeberger": {"🟦", "Ⓐ"}, "privat": {"🟦", "🟧", "🧡"},   # 23:38 approved: the 🟦 1910 was Privat REJOICING at Augsburg that the Idists had left (Sikosek p. 257) — pattern hit on «Ido lecture» + «forlasis la movadon»; 🟩
                 "ahlberg": {"⭕", "🟦", "🟧"}, "krikortz": {"🟦", "🟧"}, "dragoumis": {"🟦"}, "meazzini": {"🟧"}, "moch": {"🟦", "⬛"},
                 "schmidt": {"🟨"},   # 2026-09-19 23:00: the 1894 ballot's «Schmidt» is Christian of Nürnberg; the card's Schmidt is Prof. Adolf of Potsdam, an Esperantist from 1903
                 "talmey": {"🟦", "🟧"}, "simon": {"🟦"},   # 2026-09-19 22:55: the 🟦 is the Belgian C. Simon of Ixelles (stem collision) — Prof. Otto Simon never left the LK (Prague 1921)
                 "avilov": {"🟦"}, "o-connor": {"⭕"}, "lambert": {"⭕"}, "lemaire": {"⭕"}, "meier": {"⭕", "🟨", "🟦"},
                 "cejka": {"⭕"},      # false hit: the 1908 «eksigitaj» is the Prague club's expulsion in the Kühnl quarrel (he founded the Bohema Asocio)
                 "seynaeve": {"⭕"}}   # the script's 1909 is the roll transcription's «[struck through]»; the hand ⭕ 1911 above replaces it
# stems whose group-1 (strike) question is RULED — no longer flagged in P-GAP
# stems whose group-2 (proposed square) question is RULED — the script's own square stands as dated; no longer flagged «confirm/date»
# return-shaped dots the hand has dismissed (a counterfactual, a citation, a royal lesson — not an act): no longer flagged
HAND_RETURN_DISMISSED = {"zamenhof", "de-beaufront", "mudie", "schneeberger", "ahlberg", "privat", "jamin", "lemaire", "moch", "meazzini", "kofman", "beauchemin", "dragoumis", "krikortz", "talmey", "meier", "michaux", "avilov"}
# 2026-09-20 00:15 approved — the six 1893–94 hearts confirmed as tabled (Zamenhof's 💚 on Forster, secondary, flagged in the doc); ballot numbers checked at the roll/page:
# Krikortz «503. Krikortz [V. Langlet]»; Meier E. (442) = L. E. Meier on the first number of his ten-copy block, «Meier I. (446)» a second Nürnberg Meier on one of the copies (page image, no OCR error)
# the hearts the editor confirmed (2026-09-20), each with its year as the v0.2 card shows it: a heart a later line
# proposes for the same person is NOT stamped «RULED» (2026-10-20: De Beaufront's 💛 1894 from Amerika Esperantisto,
# Jan 1909, would otherwise have read as ruled)
HAND_CONFIRMED_HEARTS = {"krikortz": {("💛", 1893), ("🟨", 1894)}, "grabowski": {("💛", 1893)}, "de-beaufront": {("💚", 1893)},
                         "meier": {("💚", 1893), ("🟨", 1894)}, "zamenhof": {("💚", 1894), ("💛", 1894)}}
# The initial 🟩 the default rule does not give (it gives 🟩 only to a profile with no camp line): the editor 2026-10-31
# 12:3x, on v0.3: Privat and Schneeberger to have an initial green square. Read by propose() and by --resequence.
INITIAL_GREEN = {"privat": "RULED 2026-10-31: an Esperantist first (initial 🟩)",
                 "schneeberger": "RULED 2026-10-31: an Esperantist first (initial 🟩), before his 🟦 1908"}
HAND_CONFIRMED_CAMP = {"lemaire", "michaux", "deligny", "zabilon-d-her", "beauchemin", "meazzini", "kofman", "privat"}   # kofman 23:30 approved: 🟦 1909 · 🟦 1922 (riadheris; Esther 1925; Mondo 1928) · 🟧 1929 (Cosmoglotta primary; Künzli's «1922» undocumented)   # beauchemin 23:27 approved: 🟦 1909 (the signed Alegorio) and the second 🟦 1925 (Ido Zürich bylines; Uniono Idista Reprezentero 1928) stand as dated   # michaux 23:07 approved: ◈ 1907 → 💙 1908 → 🟧 1909 stands as ruled 14 and 18 Sep
HAND_RESOLVED_STRIKE = {"o-connor", "lambert", "lemaire", "meier", "ahlberg", "cejka", "seynaeve", "rhodes", "moscheles", "cape", "ebner",
                        "bicknell", "junck", "bagnulo", "bein", "hanauer", "gallois", "asnes", "gernet", "talmey", "beauchemin", "kofman",
                        "jamin", "moch", "avilov", "schneeberger", "borel"}   # borel: hold lifted 22:40 — Ora Libro 1937 p. 73, wartime prisoner-mail intermediary (a movement act after the 1914 strike; no ⬜)

BALLOT = None
def surname_key(stem):
    return fold(stem.split("-")[-1])
def load_ballot():
    """Points 2/3/4 of the August 1894 result page, tesseract witness, as {folded surname: (point, number, line)}."""
    global BALLOT
    BALLOT = {}
    path = os.path.join(GEN, "sources", "ocr", "Esperanto 1894.3.txt")
    try: lines = open(path, encoding="utf-8", errors="ignore").read().split("\n")
    except FileNotFoundError: return
    pt = None
    for i, ln in enumerate(lines, 1):
        if i < 755 or i > 800: continue
        m = re.match(r"\s*Por la punkto (\d)", ln)
        if m: pt = int(m.group(1)); continue
        if pt in (2, 3, 4):
            for nm, num in re.findall(r"([A-ZĈĜĤĴŜŬ][\wĉĝĥĵŝŭ\.\-]{1,25}(?: [A-Z]\.)?)\s?\((\d{1,4})\)", ln):
                key = fold(nm.split()[0].strip(".-"))
                if key not in BALLOT: BALLOT[key] = (pt, num, i)

DEATH_VERB = re.compile(r"\b(mortis|mortinta|mortinte|forpasis|estingiĝis|pereis|mortigit\w*|falis|died)\b", re.I)
TITLES = {"prof", "profesoro", "dro", "d-ro", "dr", "doktoro", "s-ro", "sro", "s-ino", "f-ino", "sinjoro", "pastro", "abato",
          "komandanto", "cdt", "kapitano", "kolonelo", "majoro", "generalo", "leŭtenanto", "inĝ", "inĝeniero", "advokato", "la",
          "mr", "mrs", "miss", "rev", "st", "saint"}
TITLES |= {"pro", "s-ro.", "d-rino"}
# the card as passed (v0.2) gives these deaths though the caption's initial and the line's given name differ: van
# Melckebeke's caption «Dro B.» against «Raymond Van Melckebeke» (EdE, Wikipedia); Zabilon d'Her's «E.» against «Jeanne»
NAME_CHECK_OFF = {"van-melckebeke", "zabilon-d-her"}
def _fold2(s): return re.sub(r"(.)\1", r"\1", fold(s).replace("þ", "th").replace("ð", "d").replace("ł", "l"))   # doubles single: Villarreal
# first letters that swap between a national and an Esperanto given name (Giacomo/Jakobo, Carlo/Karlo, Wilhelm/Vilhelmo)
_SAME = str.maketrans({"j": "g", "k": "c", "w": "v", "y": "i", "p": "f"})
def _initial(n): return _fold2(n)[0].translate(_SAME)
def _names(s):
    return [t for t in re.findall(r"[^\W\d_][\w’'.-]*", s) if t[0].isupper() and _fold2(t).strip(".") not in TITLES]
def own_death(fact, caption, stem):
    """Is a «morto» line the card person's own death? (2026-10-20.) The person is named by the line's leading qualifier
    («**(Cdt Pierre Ernest, Clermont-Ferrand)**», the harvest's identity mark) or by the words before the death verb;
    those hold his surname (the stem's last part, folded, þ as th), and where both they and the caption give a first
    name or initial, the first letters agree (titles left out). A subject with no name («Li mortis») counts."""
    parts = [p for p in stem.split("-") if len(p) > 1]          # zabilon-d-her: zabilon, her
    sur = _fold2(parts[-1]) if parts else _fold2(stem)
    in_sur = lambda n: any(_fold2(p) in _fold2(n) for p in parts)
    qm = re.match(r"\s*\*\*\(([^)]*)\)\*\*", fact)
    q = qm.group(1) if qm else ""
    body = fact[qm.end():] if qm else fact
    m = DEATH_VERB.search(body)
    subj = body[:m.start()] if m else ""
    sn = _names(subj)
    # the given names are the names right before the surname, on both sides («Rektoro E. Boirac»: E.; «Georgo
    # Karpoviĉ Davidov»: Georgo, Karpoviĉ; «Boirac, la prezidanto de la Lingva Komitato, forpasis»: none)
    def before_sur(ns):
        i = next((k for k, n in enumerate(ns) if in_sur(n)), None)
        return ns[:i] if i else []
    cn = _names(name_of(caption) or "")
    capn = before_sur(cn)
    if sn and any(in_sur(n) for n in sn):
        given = before_sur(sn)
    elif q:
        given = [n for n in _names(q.split(",")[0]) if not in_sur(n)]
    elif sn:
        return False          # the verb's subject names someone else
    else:
        return bool(m) or sur in _fold2(body)
    if stem in NAME_CHECK_OFF: return True
    if capn and given and not ({_initial(c) for c in capn} & {_initial(g) for g in given}): return False   # «Aug. Th. Laurén»: any
    return True

def propose(stem, caption=""):
    L = lines_of(stem, caption)
    tags = []   # (glyph, year, locator, why)
    for g, y, loc, why in HAND_RULINGS.get(stem, []):
        tags.append((g, y, loc, why))
    own_category = any(g == "◈" for g, *_ in tags)
    def add(g, ln, why):
        tags.append((g, ln["year"], ln["loc"][:90], why))
    # † — the earliest death line; only if ≤ 1908
    deaths = []
    # a namesake's death may stand in the surname's ambiguous file, which the harvest could not give to one bearer
    # (Charles Lambert's «mortis … 1959 en Nico», beside his wife's death of 1920): read there for «morto» lines only,
    # through the same own_death check (2026-10-20)
    AMB = []
    if stem in CARD_BUCKET and os.path.exists(os.path.join(PROFILES, stem + "-ambiguous.md")):
        AMB = [x for x in lines_of(stem + "-ambiguous") if x.get("kind") == "morto"]
    for ln in L + AMB:
        head = ln["text"].split(" · ")[0]
        # 2026-09-19 22:48 (editor) — a BOUNDED death is not a † year
        if re.search(r"(DEATH BOUNDED|death bounded|between .{0,40} and .{0,40}(19|20)\d\d|terminus (ante|post) quem|died after|after 19\d\d\)|no death (date|year)|death (year|date) (unknown|open|not held))", head, re.I): continue
        # A LINE OF THE KIND «morto» (the kinds list in force) is the death itself, on the line's own date: no pattern
        # needed; a date that is not one year (a range, «[sen dato]») gives no † year
        # … but of THIS person: the death verb's subject carries the card's surname, and a given name or initial in it
        # agrees with the caption's (Klara Zamenhof's «S. Zilbernik mortis» 1906, Ernesto beside Federico Villareal,
        # Casimir beside Antoni Grabowski, all in one profile)
        if ln.get("kind") == "morto":
            if re.fullmatch(r"\s*(1[89]\d\d|20\d\d)(-\d\d){0,2}\s*", ln["ystr"]) and own_death(head, caption, stem):
                deaths.append((ln["year"], ln, "a line of the kind «morto»"))
            continue
        sp = re.match(r"\s*(1[6-9]\d\d)\s*[–-]\s*(1[89]\d\d|20\d\d)\s*$", ln["ystr"])
        if sp and int(sp.group(2)) - int(sp.group(1)) >= 30 and re.search(r"(born|nask|†|died|mortis|–\s*\d{4}\)|\(\d{4}\s*[–-]\s*\d{4}\))", head, re.I):
            deaths.append((int(sp.group(2)), ln, "life-span line")); continue
        h = head.lstrip("*").strip().lower()
        dm = re.search(r"(?:died|mortis|†|death|mort\.|mortinta|mortinte|killed)[^·;]{0,45}?\b(1[89]\d\d)\b", head, re.I)
        if dm:
            spn = re.search(r"\b" + dm.group(1) + r"\s*[–-]\s*(1[89]\d\d|20\d\d)\b", head)
            if spn: dm = type("M", (), {"group": (lambda self, i, v=spn.group(1): v), "start": (lambda self, v=dm.start(): v)})()
        if dm and re.search(r"\b(born|nask|naskiĝis|naskita|b\.)\b", head[:dm.start()], re.I) and not re.search(r"(son|filo|father|patro|wife|edzino|brother|frato|daughter|filino|of his |de lia |de sia |namesake|not the )", head[:max(0, dm.start())][-60:], re.I):
            deaths.append((int(dm.group(1)), ln, "death year in the line")); continue
        hh = re.sub(r"^[\s\*⚠★⛔✅⇒]+", "", head)
        dm2 = re.match(r"(?:died|mortis|†|death|obituary|the death|his death|dies|nekrolog|mortpaf|killed|fell)[^·;]{0,60}?\b(1[89]\d\d)\b", hh, re.I)
        if dm2 and ("E2" in ln["tags"] or "BIO" in ln["tags"]) and not re.search(r"(son|filo|father|patro|wife|edzino|brother|frato|daughter|filino|of his |de lia |de sia |namesake|not the |his friend|colleague|another)", head[:dm2.start()], re.I) \
           and not re.search(r"(list|nomaro|among|inter la|Mortis: S-roj|the dead of|dead-list|necrolog)", head[:dm2.start()], re.I):
            yb = int(dm2.group(1)); span = re.search(r"\b" + str(yb) + r"\s*[–-]\s*(1[89]\d\d|20\d\d)\b", hh)
            deaths.append((int(span.group(1)) if span else yb, ln, "death line")); continue
        hq = re.sub(r"^[\s\*⚠★⛔✅⇒]*\([^)]*\)\*{0,2}\s*", "", head)   # drop a leading **(qualifier)**
        hq = re.sub(r"^[\s\*⚠★⛔✅⇒]+", "", hq)
        dm3 = re.match(r"(?:\*\*)?(?:DEATH|death|died|killed|obituary|mortis|†)[^·]{0,80}?\b(1[89]\d\d|20\d\d)\b", hq, re.I)
        if dm3 and ln["year"] and abs(int(dm3.group(1)) - ln["year"]) <= 1 and not re.search(r"(son|filo|father|patro|wife|edzino|brother|frato|daughter|filino|of his |de lia |de sia |namesake|recorded|list|nomaro)", hq[:dm3.end()], re.I):
            deaths.append((int(dm3.group(1)), ln, "DEATH-headed line")); continue
        dm4 = re.search(r"«[^»]{0,60}?\b(?:mortis|mortinta|mortinto)\b[^»]{0,30}?\b(1[89]\d\d|20\d\d)\b", head)
        if dm4 and ("E2" in ln["tags"] or "BIO" in ln["tags"]) and not re.search(r"(filo|son|patro|father|edzino|wife|frato|brother)", head[:dm4.start()], re.I):
            deaths.append((int(dm4.group(1)), ln, "quoted «mortis … year»")); continue
        if ln["year"] and "E2" in ln["tags"] and re.match(r"(death|died|obituary|†|mortis|the death|his death|her death|dies|nekrolog|funebra|killed|fallen)", h) and not re.search(r"(son|filo|father|patro|wife|edzino|brother|frato|of his|de lia|de sia)", h[:60]):
            deaths.append((ln["year"], ln, "death line [E2]"))
    if "†" in caption and not deaths:
        tags.append(("†", 1906, "the album's own † (dead by 1906)", "album caption — year unknown, ≤ 1906"))
        tags.append(("‡", 1906, "the album's own †", "died before the end of 1908 — never faced the choice")); death_year = 1906
    death_year = None
    # the «morto» lines of this person decide alone where there are any: the patterns below them were written for the
    # older English heads and, reading the facts themselves, catch other people's deaths (Boirac: EdE on Miletz,
    # Korĵenkov's essay, BrE 1915, all 1915, against his 1917)
    own = [d for d in deaths if d[2] == "a line of the kind «morto»"]
    if own: deaths = own
    if deaths:
        arc = [d for d in deaths if d[2] in ("life-span line", "death year in the line", "a line of the kind «morto»")]
        dy, ln, why = sorted(arc or deaths, key=lambda x: x[0])[0]
        death_year = dy
        tags.append(("†", dy, ln["loc"][:90], f"{why} — † {dy}"))
        if dy <= 1908: tags.append(("‡", dy, ln["loc"][:90], "died before the end of 1908 — never faced the choice"))
    # Ⓚ / Ⓐ
    if re.search(r"\bL\. ?K\.", caption):
        tags.append(("Ⓚ", 1906, "the album's own «L. K.» mark (printed key p. 14)", "album caption"))
    else:
        for ln in L:
            head = ln["text"].split(" · ")[0]
            if re.search(r"(Lingva Komitato|Lingvo Komitato)", head) and re.search(r"(elektit|elected|membro de la L|member of the L|on the (founding |1905 |LK )?roll|Boulogne roll|komitatano|sat on|re-?elekt)", head, re.I) and not re.search(r"Ido|Uniono|kandidat|candidate|declin|refus", head, re.I):
                add("Ⓚ", ln, "LK membership line"); break
    for ln in L:
        head = ln["text"].split(" · ")[0]
        if re.search(r"Akademi", head) and re.search(r"(elektit|elected|akademiano|membro de la Akademio|member of the Akademio|seat on the Akademio|vic-?prezid|co-?opt)", head, re.I) and not re.search(r"Ido|Uniono|di Ido|Occidental|kandidat|candidate|not elected|ne elektit|declin|akademiano havas|Academy decision \d|decido \d|\[I\d\]", head + " " + ln["text"][:200], re.I) and not any(x in ln["text"] for x in ("[I1]", "[I2]", "[I3]", "[I4]", "[I5]", "[I6]")) and not head.startswith("ADHERENCE") and not re.search(r"(Uniono|Federuro|ULI|Ido-|svensk|Progreso|Mondo)", ln["loc"], re.I) and (ln["year"] or 0) >= 1908:
            add("Ⓐ", ln, "Akademio line"); break
    # camps — from the roster runs' own STATUS lines (Progreso 1908–14 / Mondo 1912–34 → Ido, Mondo ≥ 1928 → Novial; Cosmoglotta → Occidental):
    # ADHERENT [B] → square; INVOLVEMENT with bylines/letters > 0 → circle; mentions only → no colour (a witness, not a camp)
    STATUS = re.compile(r"STATUS in this source: (ADHERENT \[B\][^;·]*|INVOLVEMENT only \[X\])")
    COUNTS = re.compile(r"(\d+) bylines?, (\d+) letter-lines?, (\d+) mentions?")
    seen = {}
    for ln in L:
        m = STATUS.search(ln["text"])
        if not m: continue
        loc = ln["text"]
        organ = "ido" if "progreso-roster" in loc else "mondo" if "mondo-roster" in loc else "occ" if "cosmoglotta-roster" in loc else None
        if not organ: continue
        yr = ln["year"] or 0
        strong = m.group(1).startswith("ADHERENT")
        c = COUNTS.search(ln["text"])
        if not strong:
            tags.append(("·", yr, ln["loc"][:90], f"named in the {organ} organ ({c.group(3) if c else '?'} mentions, {c.group(2) if c else '?'} letter-lines, {c.group(1) if c else '?'} signed pieces) — a witness, not a camp; a circle is hand-only (rival organs cite Esperantists all the time)")); continue
        # date the square by the earliest [B]-tagged line that came from the same run (⟵ <run-file>), else by the STATUS line's first mention, flagged
        runfile = re.search(r"⟵ `([^`]+)`\s*$", ln["text"]) or re.search(r"⟵ `([^`]+)`", ln["text"])
        bl = [x for x in L if "B" in x["tags"] and x["year"] and x is not ln and (not runfile or runfile.group(1) in x["text"])]
        organ_yr = {"ido": (1908, 1934), "mondo": (1912, 1934), "occ": (1922, 1950)}[organ]
        bl = [x for x in bl if organ_yr[0] <= x["year"] <= organ_yr[1]]
        camp = "occ" if organ == "occ" else "ido"
        if bl:
            x = sorted(bl, key=lambda z: z["year"])[0]; yr2 = x["year"]
            if organ == "mondo" and yr2 >= 1928: camp = "novial"
            g = "🟧" if camp in ("occ", "novial") else "🟦"
            if (g,) in seen: continue
            seen[(g,)] = 1
            tags.append((g, yr2, x["loc"][:90], f"{ {'ido':'Ido','novial':'Novial (Mondo ≥ 1928)','occ':'Occidental'}[camp] }: ADHERENT — dated by the earliest [B] line of the run"))
        else:
            if organ == "mondo" and yr >= 1928: camp = "novial"
            g = "🟧" if camp in ("occ", "novial") else "🟦"
            if (g,) in seen: continue
            seen[(g,)] = 1
            tags.append((g, yr, ln["loc"][:90], f"{ {'ido':'Ido','novial':'Novial','occ':'Occidental'}[camp] }: ADHERENT — ⚠ dated by FIRST MENTION (no [B] line found), hand-date"))
    # (4)/(6) adhesion outside the roster runs: an office/membership/adhesion/founding line PROPOSES the square
    ADH_IDO = re.compile(r"(membro (di|de) la Uniono|membro di la (Ido-)?Akademio|(Uniono|Ido-?Akademio|Akademio di Ido)[^·]{0,40}(prezid|sekretari|membr|elektit|elected)|(his|sian?|lia) adhes(ion|ia|ilon) (al|to|a) (la )?(Uniono|Ido)|adhésion à l.Uniono|adhésion à l.Ido|aliĝis al (la )?(Uniono|Ido)|adherent|Ido-(libro|lernolibro|vortaro)|Idista (grupo|societo|klubo)[^·]{0,30}(prezid|sekretari|fond)|di la Delegitaro, ed ex-membro|reprezent[^·]{0,20}(Uniono|Ido)|delegito de la Uniono|nun Idisto|ex-Esperantisto, nun|(Ido|Idista) (lecture|parolado|prelego)|organis\w+ [^·]{0,40}(Ido|Idista|Uniono)|(Idista|Ido-)\w* (grupo|klubo|societo|uniono)[^·]{0,40}(fond|organis|prezid|sekretari))", re.I)
    ADH_OTH = re.compile(r"((founded|created|author of|aŭtoro de|kreis|launched|inventor of|published|publikigis|eldonis|his own project|lia .{0,20}projekto)[^·]{0,50}(Romanal|Arulo|Gloro|Esperanto II|Antido|Adjuvilo|Nov-Esperanto|Idiom Neutral|Novial|Occidental)|(Romanal|Arulo|Gloro|Esperanto II|Antido|Adjuvilo|Nov-Esperanto)[^·]{0,40}(his own|propra|kreita de li|de lia kreo)|(joined|aliĝis al|adher)[^·]{0,30}(Latino sine|Academia pro Interlingua|Occidental|Novial|Idiom Neutral|Interlingue)|Occidental-Union|Novialiste[^·]{0,30}(redakt|jurie|editor)|\bjurie\b)", re.I)   # 2026-09-19 23:08: «juries» (an SFPE examining jury) matched «jurie» and painted Deligny orange
    for ln in L:
        head = ln["text"].split(" · ")[0][:220]
        if not ln["year"] or ln["year"] < 1907 or "STATUS in this source" in ln["text"]: continue
        if re.search(r"(kontraŭ|against|refut|denounc|atak|polemik|malakcept|rejected|refused|kritik|not a member|ne membro|\(from Progreso\)|propagado|profeto|NOT marked|never an Idist|never left|stem collision|rightly)", head, re.I): continue
        if ("🟦",) not in seen and ADH_IDO.search(head):
            seen[("🟦",)] = 1; tags.append(("🟦", ln["year"], ln["loc"][:90], "Ido adhesion/office/membership line outside the roster runs — hand-confirm")); continue
        if ("🟧",) not in seen and ADH_OTH.search(head):
            m2 = re.search(r"(Romanal|Arulo|Gloro|Esperanto II|Antido|Adjuvilo|Nov-Esperanto|Idiom Neutral|Novial|Occidental|Latino sine|Interlingue)", head)
            seen[("🟧",)] = 1; tags.append(("🟧", ln["year"], ln["loc"][:90], f"other-auxlang founding/adhesion line outside the roster runs — {m2.group(1) if m2 else '?'} — hand-confirm"))
    # (5) ⬛ proposed from an encyclopaedic line saying he rejected the idea of an auxlang altogether
    for ln in L:
        head = ln["text"].split(" · ")[0]
        if re.search(r"(reĵet|rejected|gave up|abandon|forlasis|renounc|turned against)[^·]{0,40}(ideon|idea)[^·]{0,40}(artefarita|planlingv|artificial|international language|lingvo internacia|helplingv|auxlang|auxiliary)", head, re.I):
            tags.append(("⬛", ln["year"], ln["loc"][:90], "an encyclopaedic line saying he rejected the very idea of an auxlang — hand-confirm (EdE-type witness)")); break
    # (1) no camp after death
    if death_year:
        tags[:] = [t for t in tags if not (t[1] and t[1] > death_year and t[0] != "†")]
    if any(t[0] == "‡" for t in tags):
        tags[:] = [t for t in tags if t[0] not in "🟦💙🟧🧡"]
    if stem == "de-saussure":   # Progreso scores Antido's author ADHERENT — he never joined Ido (hand, 2026-09-18)
        tags[:] = [t for t in tags if t[0] != "🟦"]
    if stem == "michaux":       # QUEUE U11-B 2026-09-14: «Michaux (Romanal, not Ido)» → pale blue; the script's 🟦 (a Delegation-membership line) withdrawn
        tags[:] = [t for t in tags if t[0] != "🟦"]
        tags.append(("💙", 1908, "QUEUE U11-B, editor 2026-09-14; Progreso § 4c", "RULED 2026-09-14: Ido SYMPATHISER — a Delegation man who never joined the Uniono; his own project was Romanal"))
    if stem == "zinoviev":      # 💙 ruled by hand; the script's 🟦 from Progreso's ADHERENT status is withdrawn
        tags[:] = [t for t in tags if t[0] != "🟦"]
    # explicit adhesion / exit lines outside the three organs (OGE «eksiĝis … Ido», adhesion letters, Ido offices) — flagged, not coloured
    extra = [ln for ln in L if ln["year"] and ln["year"] >= 1907 and IDO_STRONG.search(ln["text"].split(" · ")[0][:160]) and "STATUS in this source" not in ln["text"]]
    if extra and not any(t[0] in "🟦💙" for t in tags):
        tags.append(("·", extra[0]["year"], extra[0]["loc"][:90], f"{len(extra)} Ido-adhesion-shaped line(s) outside the roster runs — hand-pass for 🟦/💙"))
    extra2 = [ln for ln in L if ln["year"] and ln["year"] >= 1907 and OTHER_STRONG.search(ln["text"].split(" · ")[0][:160]) and "STATUS in this source" not in ln["text"]]
    if extra2 and not any(t[0] in "🟧🧡" for t in tags):
        tags.append(("·", extra2[0]["year"], extra2[0]["loc"][:90], f"{len(extra2)} other-auxlang-adherence-shaped line(s) outside the roster runs — hand-pass for 🟧/🧡"))
    # green: default; 🟢 if an Esperanto act dated after the first blue/orange
    camp_years = [t[1] for t in tags if t[0] in "🟦💙🟧🧡" and t[1]]
    if camp_years:
        first = min(camp_years)
        later = [ln for ln in L if ln["year"] and ln["year"] > first and re.search(r"((revenis|reveninte|reiris|reaniĝis) (al|en) (Esperanto|la (esperanta )?movado|la esperantistaro)|returned to Esperanto|return to Esperanto|\bre-?join(ed|s)?\b(?!der)|back to Esperanto|denove esperantist|forlasinte Idon|left Ido|abandoned Ido)", ln["text"].split(" · ")[0], re.I)]   # 2026-10-20: «rejoinder» (Charles Lemaire, 1909) and «Reveninte el Antverpeno» (Michaux, 1911) are no returns
        if later:
            x = sorted(later, key=lambda x: x["year"])[0]
            tags.append(("·", x["year"], x["loc"][:90], "an explicit return-shaped line — 🟢 is HAND-ONLY; propose"))
        else:
            n_later = sum(1 for ln in L if ln["year"] and ln["year"] > first and GREEN.search(ln["text"].split(" · ")[0]) and not IDO.search(ln["text"].split(" · ")[0]) and not OTHER.search(ln["text"].split(" · ")[0]))
            if n_later: tags.append(("·", first, "", f"{n_later} Esperanto-marked lines after the first camp line, no explicit return word — hand-pass for 🟢"))
    if not any(t[0] in "🟦💙🟧🧡‡" for t in tags):
        tags.append(("🟩", None, "", "default — no camp line on the profile" + ("" if L else "; NO FACT LINES")))
    # 🟨 = voted FOR reform in the 1894 ballot — anything but point I («kontraŭ reformoj»): PRIMARY = the August 1894 result page
    # (La Esperantisto No. 8, pp. 13–15; `Esperanto 1894.3.txt` l.761–795, points 2/3/4 as printed; the November additions are point I bar Runstedt),
    # names matched by folded surname to the profile stem; then the profile's own vote lines as a second witness
    if BALLOT is None: load_ballot()
    if surname_key(stem) in BALLOT:
        pt, num, lineno = BALLOT[surname_key(stem)]
        tags.append(("🟨", 1894, f"Esperanto 1894.3.txt l.{lineno}, No. 8 (Aug 1894) pp. 13–15 — «({num})» under «Por la punkto {pt}»", f"voted point {pt} (for reform) in the 1894 ballot — surname match on the printed result page; confirm the number against the March 1894 roll"))
    for ln in L:
        if any(t[0] == "🟨" for t in tags): break
        if not ln["year"] or ln["year"] != 1894: continue
        head = ln["text"].split(" · ")[0]
        if re.search(r"(voted|voĉdonis|voĉis|his vote|ballot paper|sia voĉo)", head, re.I) and re.search(r"(P\.\s?(II|III|IV)\b|punkto (2|3|4)\b|point (II|III|IV|2|3|4)\b|por la punkto [234]|por reformoj|kun ŝanĝoj|aliaj ŝanĝoj|tuta pleneco)", head, re.I) \
           and not re.search(r"(P\.\s?I\b(?!I)|punkto 1\b|point (I|1)\b(?!I)|kontraŭ reformoj|against reform|voted against)", head, re.I):
            add("🟨", ln, "voted for reform in the 1894 ballot (anything but point I)"); break
    # (6b) 2026-09-19 23:20 — PRE-VOTE AGITATION, the editor
    #. Glyphs (hearts since 23:30 —): 💛 (yellow heart — FOR
    # reform before Aug 1894: Grabowski's proposals) and 💚 (green heart — AGAINST before the vote: Meier's «ni lasu Esperanton sen ia
    # ŝanĝo!», Sept 1893). Lines dated 1893 → Jul 1894 only; the ballot itself is 🟨/🟩. Hand-confirm.
    REF_TOPIC = re.compile(r"(reform|ŝanĝ|shanĝ|change proposal|proposed change|the 1893 (change|proposal)|Serbin|Okromĉedjelova|projektitaj|anstataŭig)", re.I)
    REF_FOR = re.compile(r"(propon\w* (ŝanĝ|reform|change)|proposes? (changes?|reforms?|to (replace|drop|abolish))|advocat\w* (reform|change)|agitat\w* for (reform|change)|for reform|por (la )?reform|urg\w* (reform|change)|demands? (reform|change)|his (own )?(reform|change) (proposal|project)|circular for reform|kampanj\w* por|reformed (style|orthography|spelling)|reformemo|substituted the adverbial|-e for (the )?-aŭ|calls a .{0,20}vote on its reformed|preface calls a|his (reform )?project|proposed reforms|projekto de reform|proponas)", re.I)
    REF_AGAINST = re.compile(r"(against (the )?(1893 )?(change|reform)|kontraŭ (la )?(ŝanĝ|reform)|sen ia ŝanĝo|lasu Esperanton|keep Esperanto (as it is|unchanged)|opposed (the )?(change|reform)|refus\w* (the )?(change|reform)|no change|neniu ŝanĝ|ni ne ŝanĝu|defends? the (Fundamento|language as it is)|malbenit|ne bezonas ŝanĝ|accursed)", re.I)
    for ln in L:
        if not ln["year"] or ln["year"] < 1893 or ln["year"] > 1894: continue
        if ln["year"] == 1894 and re.search(r"1894-(0[89]|1[0-2])", ln["ystr"]): continue   # the ballot and its aftermath are 🟨/🟩, not agitation
        # the kind's object read with the fact (2026-10-20: De Beaufront's 1894 letter, «{aserto: kontraŭ ŝanĝoj en
        # Esperanto}», whose fact says «kiam alia persono proponis ŝanĝojn» and so read as a 💛)
        head = ln["text"].split(" · ")[0][:300] + (" " + ln["obj"] if ln.get("obj") else "")
        if not REF_TOPIC.search(head): continue
        if re.search(r"\b(voted|voĉdonis|voĉdonado|votant|votat|ballot|rezultato|tally|the vote of|the 1894 vote|Fina rezultato)\b", head, re.I): continue   # the vote itself is 🟨/🟩
        # primaries only: the 1893–94 organ, Zamenhof's own texts and letters; retellings (Sikosek, Künzli, Garvía, Dyer, Ludovikito, Neves, de Wahl 1927, UEA 1907 …) are for the hand
        if not re.search(r"(Esperanto\.189[34]|Esperanto 189[34]|La Esperantisto|Tekstaro OV|\bOV\b|Waringhien|Leteroj|letero|letter)", ln["loc"] + " " + head, re.I): continue
        if re.search(r"(Sikosek|Künzli|Kunzli|Garvía|Garvia|Dyer|Ludovikito|Historieto|Neves|Cosmoglotta|EsperantoUEA|Zakrzewski|EdE|1907|1913|1927|1933|1974|2003|2008|2023)", ln["loc"], re.I): continue
        # a line against changes is never read as one for them, whether or not a 💚 is already there
        if REF_AGAINST.search(head):
            if not any(t[0] == "💚" for t in tags):
                tags.append(("💚", ln["year"], ln["loc"][:90], "green heart — sympathy for the language as it was, before the Aug 1894 vote (hearts = leanings, squares = acts) — hand-confirm"))
            continue
        if REF_FOR.search(head) and not any(t[0] == "💛" for t in tags):
            tags.append(("💛", ln["year"], ln["loc"][:90], "yellow heart — sympathy for reform before the Aug 1894 vote (hearts = leanings, squares = acts) — hand-confirm"))
    # (7) 2026-09-19 «yes please» — (a) a camp square is dated by the earliest ACT on file (a signed piece, an office, his own statement),
    # not by the first roster appearance; (b) a camp may RECUR after a 🟢 when a later adhesion act exists («their returns really were just
    # popping by to say hello»). Both are proposals the hand confirms.
    ACT_IDO = re.compile(r"(Signs an Ido|signs? (an |the )?Ido|signed (an |the )?Ido|ADHERENCE:|OFFICE \(ADHERENCE\)|Riprezentant|Reprezenter|Reprezentanto[^·]{0,20}(Uniono|Ido)|writes (to|in) Progreso|letter to Progreso|skribas [^·]{0,15}en Ido|\(qua skribas a ni en Ido\)|byline[^·]{0,20}(Progreso|Ido|Mondo)|signed pieces?[^·]{0,30}in (Progreso|Ido|Mondo)|nun Idisto|ni esas Idisti|riadher|readher|rejoined Ido|Idist regained|membro (di|de) la Uniono|Idista (grupo|societo|klubo)[^·]{0,30}(prezid|sekretari|fond))", re.I)
    ACT_OTH = re.compile(r"(Occidental-Union|Occidental[^·]{0,30}(membro|member|reprezent|delegit|signs|signed|byline)|Novial[^·]{0,30}(membro|member|reprezent|signs|signed|byline)|Cosmoglotta[^·]{0,20}(signed|byline|writes)|\bjurie\b)", re.I)
    NOTACT = re.compile(r"(kontraŭ|against|refut|denounc|atak|polemik|rejected|refused|kritik|not a member|ne membro|STATUS in this source|FIRST dated appearance|LAST dated|named in|cited|quoted|retrovenis|revenis|returned)", re.I)
    def acts(rx, lo, hi):
        out = []
        for x in L:
            if not x["year"] or x["year"] < lo or x["year"] > hi: continue
            head = x["text"].split(" · ")[0][:240]
            if NOTACT.search(head): continue
            if rx.search(head): out.append(x)
        return sorted(out, key=lambda z: z["year"])
    for i, t in enumerate(list(tags)):
        if t[0] == "🟦" and t[1] and not t[3].startswith("RULED"):
            a = acts(ACT_IDO, 1907, t[1] - 1)
            if a: tags[i] = ("🟦", a[0]["year"], a[0]["loc"][:90], f"Ido: re-dated to the earliest Ido ACT on file (was roster {t[1]}) — hand-confirm; " + t[3])
        if t[0] == "🟧" and t[1] and not t[3].startswith("RULED"):
            a = acts(ACT_OTH, 1907, t[1] - 1)
            if a: tags[i] = ("🟧", a[0]["year"], a[0]["loc"][:90], f"other auxlang: re-dated to the earliest ACT on file (was roster {t[1]}) — hand-confirm; " + t[3])
    for g0, ry, _, _ in [t for t in tags if t[0] == "🟢" and t[1]]:
        a = acts(ACT_IDO, ry + 1, 1950)
        if a and not any(t[0] == "🟦" and t[1] and t[1] > ry for t in tags):
            tags.append(("🟦", a[0]["year"], a[0]["loc"][:90], f"Ido AGAIN after the 🟢 of {ry} — a later adhesion act on file — hand-confirm"))
        a2 = acts(ACT_OTH, ry + 1, 1950)
        if a2 and not any(t[0] == "🟧" and t[1] and t[1] > ry for t in tags):
            tags.append(("🟧", a2[0]["year"], a2[0]["loc"][:90], f"other auxlang after the 🟢 of {ry} — a later adhesion act on file — hand-confirm"))
    # institutional strikes: 🔴 = struck FOR DISLOYALTY (the formula names anti-Esperanto action); ⭕ = struck WITHOUT a disloyalty formula
    # (silence, non-response, non-payment). ⬜ («got too busy» — the man, not the committee) is HAND-ONLY and never proposed.
    STRIKE = re.compile(r"(ne donis signon de vivo|no sign of life|STRUCK|struck (off|out|by|as)|eksigit|eksigo|eksiĝoj|deemed resigned|konsider\w* (kiel )?eksiĝint|for silence|nericevo de respondo|nerespondo|konsideri kiel eksiĝintaj|konsiderataj kiel)", re.I)
    DISLOYAL = re.compile(r"(kontraŭ-?esperanta agado|kontraŭbatal|publika kontraŭ|anti-Esperanto|disloyal|perfid|traitor|pro (lia |sia )?(ida|Ido)|kontraŭ Esperanto|kontraŭ-esperantist)", re.I)
    surname = fold(stem.split("-")[-1]); strike_lines = []
    for ln in L:
        # the kind's object read with the fact (2026-10-20: Talmey's «{konflikto: Akademio: konsiderita eksiĝinta}», whose
        # sentence splits «konsideri Talmey kaj Gaston Moch kiel eksiĝintajn»)
        head = ln["text"].split(" · ")[0] + (" " + ln["obj"] if ln.get("obj") else "")
        h0 = head.lstrip("*⚠★⛔ ").lower()
        subject_ok = (surname in fold(head)) or re.match(r"(struck|deemed|eksigit|konsiderat|considered|removed|his (name|seat)|expelled|dropped|the (academy|lk|committee) (struck|deemed|dropped|removed) him)", h0)
        if not subject_ok: continue
        if STRIKE.search(head) and ln["year"] and ln["year"] >= 1908 and re.search(r"(Akademio|Lingva Komitato|L\. ?K\.|LK\b|UEA|Asocio|Societo|Komitato|Council|Konsilantaro|Eksiĝoj|Cirkulero|circular)", head) \
           and not re.search(r"(named the .{0,20}grounds|du kaŭzoj|kondiĉojn por eksigo|as president|kiel prezidanto|signs the|subskribis|his signature is on|lia subskribo|subskribita de li|minuted|the rule|regularo|drafted|proposed the|his report|lia raporto|circular he|cirkulero[n]? de li|announced the strik|listed the strik|the Academy'?s? (decid|notice) (on|of) (other|the three|five))", head, re.I) \
           and not re.search(r"eksig\w* (de|of) (S-roj?|D-ro|Prof)", head) and not re.search(r"(never struck|not struck|no strike|neniam eksigit|was never|NOT marked|struck through|in ink|pen's strike|an address, not an exit)", head, re.I):   # a pen mark on a library copy is no strike (Süssmuth, 2026-10-20)
            strike_lines.append((bool(DISLOYAL.search(head)), ln))
    if strike_lines:
        dis = [x for x in strike_lines if x[0]]
        if dis:
            add("🔴", sorted(dis, key=lambda z: z[1]["year"])[0][1], "STRUCK FOR DISLOYALTY — the institution's own formula names anti-Esperanto action")
        else:
            add("⭕", sorted(strike_lines, key=lambda z: z[1]["year"])[0][1], "struck WITHOUT a disloyalty formula (silence / non-response / non-payment) — says nothing about the man")
    # hand suppressions (2026-09-19): drop script-proposed glyphs the editor has overruled — hand rulings (why startswith RULED) are kept
    sup = HAND_SUPPRESS.get(stem, set())
    tags[:] = [t for t in tags if not (t[0] in sup and not t[3].startswith("RULED"))]
    # (8) ◐ DOUBLE MEMBERSHIP — 2026-09-19 «Ok, go half circle» (Zinoviev's own «Membro de l'Esperantista Lingva Komitato kaj de la Delegitaro», 1908;
    # the LK's Barcelona refusal of double membership, oge.2). A tag, not a stance: the span in which a man kept an Esperanto-institution seat
    # (LK/Akademio roll, vote, session) AFTER a camp square, up to his strike/resignation. Its length is the purge lag measured per man.
    SEAT = re.compile(r"(Voted: (LK|Academy|Akademio)|On the Lingva Komitato rolls? of|present at the LK sessions?|LK session: attended|attended [^·]{0,40}(LK|Lingva Komitato) session|Lingva Komitato's full membership roll|listed in the Lingva Komitato|On the printed list of Lingva-Komitato members|Akademio line|sitting LK member|as a sitting)", re.I)
    camp_first = min([t[1] for t in tags if t[0] in "🟦💙🟧🧡" and t[1]] or [0])
    if camp_first and not any(t[0] == "◐" for t in tags):   # a hand ◐ (RULED) pre-empts the automatic span
        stop = min([t[1] for t in tags if t[0] in "🔴⭕⭘" and t[1] and t[1] >= camp_first] or [9999])
        seat_years = []; seat_loc = ""
        for x in L:
            head = x["text"].split(" · ")[0]
            if not SEAT.search(head): continue
            pre = re.split(r"\((absent|did not vote)", head)[0]
            pre = re.sub(r"[Dd]id not vote[^·]*", "", pre)
            ys = [int(y) for y in re.findall(r"\b(19[0-4]\d)\b", pre)]
            ys = [y for y in ys if camp_first <= y <= stop and y >= 1908]
            if ys:
                seat_years += ys
                if not seat_loc: seat_loc = x["loc"][:90]
        if seat_years:
            a, b = min(seat_years), max(seat_years)
            tags.append(("◐", a, seat_loc, f"DOUBLE MEMBERSHIP {a}–{b}: kept an Esperanto-institution seat (LK/Akademio roll, vote or session) after the camp square of {camp_first}" + (f", until the {[t[0] for t in tags if t[0] in '🔴⭕⭘' and t[1] == stop][0]} of {stop}" if stop != 9999 else "") + " — the purge lag per man"))
    # ⬜ = a confirmed lapse — proposed ONLY as the default outcome of a ⭕ with no dated act of the man after the strike (Gernet rule)
    strikes = [t for t in tags if t[0] == "⭕" and t[1] and not any(h[0] in "⬜⬛" and h[3].startswith("RULED") for h in tags)]
    if strikes:
        sy = strikes[0][1]
        later = [x for x in L if x["year"] and x["year"] > sy and not re.search(r"(FIRST dated appearance|LAST dated|STATUS in this source|obituary|nekrolog|died|mortis|mortint|†|death|EdE 1933|wikipedia|wikitext|Holzhaus|posthum|memor|jubile|Niaj Mortintoj|Did not vote|ne voĉdonis|Eksiĝoj|eksigit|namesake|histori|memoir|interview|intervjuo|retrospect|recall|rememor|Ad fontes|on the .{0,20}roll of|named among|listed among|named in|cited|quoted|1933|1937|1969|1974|Bibliografio)", x["text"], re.I)]
        camp_after = any(t[0] in "🟦🟧💙🧡" and t[1] and t[1] >= sy for t in tags)
        if not later and not camp_after:
            tags.append(("⬜", sy, strikes[0][2], "confirmed lapse — struck for silence and no dated act of his own follows on the profile (the default outcome of ⭕; check the profile is not just thin)"))
    if death_year:
        tags[:] = [t for t in tags if not (t[1] and t[1] > death_year and t[0] != "†")]
    if stem in INITIAL_GREEN and not any(t[0] == "🟩" for t in tags):
        tags.insert(0, ("🟩", None, "", INITIAL_GREEN[stem]))
    # within a year: the institution's act (🔴 ⭕ ⭘) before its outcome (⬜ 🟢) — 2026-09-19
    SEQ = {"🔴": 1, "⭕": 1, "⭘": 1, "⬜": 2, "🟢": 2}
    tags.sort(key=lambda t: (t[1] or 0, SEQ.get(t[0], 1)))
    j = join_of(L)   # the initial 🟩's date, set after the sort (a «≤ 1903» is text, and the square stays first)
    if j: tags[:] = [(g, j[0], loc, f"{why}; {j[2]}") if g == "🟩" and y is None else (g, y, loc, why) for g, y, loc, why in tags]
    return L, tags

# --- the SUPPLEMENT: a principled shortlist of canon — (1) the names Schuck's own prose calls pioneers but does not picture
# (the p. 17 «honora tabulo» of Russians, the p. 15 French organisers, the p. 11 Czechs, and three singletons), (2) Bein's roll
# from the Boulogne platform, Aug 1905 (bein-canon-boulogne-1905-2026-09-11.md). Editor 2026-09-18 15:50
#.
SCHUCK_PROSE = {  # stem: (printed page as the OCR's PDF page, the sentence's gist)
    "de-wahl": (17, "«La honora tabulo de Esperanto devas montri la nomojn de multaj rusoj … de Wahl»"),
    "zinoviev": (17, "«… Zinowiew …» — the same honour roll"), "lojko": (17, "«… Lojko …»"), "devjatnin": (17, "«… Devjatnin …»"),
    "kotzin": (17, "«… Boris Kotzin …»"), "radvan-ripinski": (17, "«… Radwan-Ripinski k. t. p.»"),
    "boulet": (12, "named in the prose, p. 12"), "bricard": (15, "the French organisers, p. 15"), "chavet": (15, "the French organisers, p. 15"),
    "dor": (15, "the French organisers, p. 15"), "evrot": (15, "the French organisers, p. 15"), "lallemant": (15, "the French organisers, p. 15"),
    "saquet": (15, "the French organisers, p. 15"), "sentis": (15, "the French organisers, p. 15"),
    "holub": (11, "the Czech pioneers, p. 11"), "kraus": (11, "the Czech pioneers, p. 11"), "krumpholc": (11, "the Czech pioneers, p. 11"),
    "nalli": (16, "named in the prose, p. 16"), "runeberg": (18, "named in the prose, p. 18"), "twombley": (8, "named in the prose, p. 8"),
}
BEIN_1905 = {"kofman", "gernet", "zinoviev", "postnikov", "ostrovskij", "wasniewski", "grabowski", "einstein", "trompeter", "de-beaufront", "nylen", "langlet"}
SUPP_COUNTRY = {"de-wahl": "Russia (Estonia)", "zinoviev": "Russia (Ukraine)", "lojko": "Russia (Lithuania)", "devjatnin": "Russia (Lithuania)", "kotzin": "Russia",
                "radvan-ripinski": "Russia (Poland)", "postnikov": "Russia", "boulet": "France", "bricard": "France", "chavet": "France", "dor": "France",
                "evrot": "France", "lallemant": "France", "saquet": "France", "sentis": "France", "holub": "Austria-Hungary", "kraus": "Austria-Hungary",
                "krumpholc": "Austria-Hungary", "nalli": "Italy", "runeberg": "Finland", "twombley": "USA"}

ORDER = ["🟩", "🟢", "💛", "💚", "🟨", "🟦", "💙", "🟧", "🧡", "⬜", "⬛", "🔴", "⭕", "⭘", "🟪", "🟠", "‡", "†", "Ⓚ", "Ⓐ", "◈", "◐"]
LEGEND = {"🟩": "joined Esperanto, dated; stayed unless a later square says otherwise", "🟢": "returned", "🟨": "voted for reform 1894", "🟦": "Ido adherent", "💙": "Ido sympathiser", "🟧": "other-auxlang adherent",
          "🧡": "other-auxlang sympathiser", "⬜": "confirmed lapse", "⬛": "renounced — publicly renounced world languages (the editor, 2026-11-06), adhering nowhere else (the man's act; ⬜ is the lapse the committee inferred)", "🔴": "struck for disloyalty",
          "⭕": "struck, no disloyalty formula", "⭘": "resigned (the man's own eksiĝo)", "💛": "yellow heart — sympathy for reform before the 1894 vote", "💚": "green heart — sympathy for the language as it was, before the 1894 vote", "🟪": "Volapük adherent, dated", "🟠": "invented an auxlang of their own, dated", "‡": "died before end-1908", "†": "death year known, after 1908", "Ⓚ": "Lingva Komitato", "Ⓐ": "Akademio", "◈": "unifier (proposed a union / reconciliation of the camps)", "◐": "double membership (kept an Esperanto-institution seat after a camp square — the purge lag per man)"}
def tag_table(taglists):
    counts = {g: sum(1 for t in taglists if any(x[0] == g for x in t)) for g in ORDER}
    out = "| tag | meaning | people |\n|---|---|---|\n"
    for g in ORDER:
        if counts[g]: out += f"| {g} | {LEGEND[g]} | {counts[g]} |\n"
    anyc = sum(1 for t in taglists if any(x[0] in "🟦💙🟧🧡" for x in t))
    out += f"| 🟦💙🟧🧡 | **any camp — Ido or other auxlang, adherent or sympathiser** | **{anyc}** |\n"
    return out
def country_table(items):
    """items: (country, tags) — rows: country · portraits · 🟦 · 🟧 · any square · 🔴/⭕ · ‡"""
    bc = {}
    for c, t in items:
        c = re.sub(r"\s*\(.*\)$", "", c); d = bc.setdefault(c, [0, 0, 0, 0, 0, 0])
        g = "".join(x[0] for x in t); d[0] += 1; d[1] += ("🟦" in g or "💙" in g); d[2] += ("🟧" in g or "🧡" in g); d[3] += any(c in g for c in "🟦💙🟧🧡"); d[4] += ("🔴" in g or "⭕" in g); d[5] += "‡" in g
    out = "| country (1906 borders) | people | Ido 🟦+💙 | other 🟧+🧡 | any camp | struck 🔴/⭕ | ‡ |\n|---|---|---|---|---|---|---|\n"
    for c, v in sorted(bc.items(), key=lambda x: (-x[1][0], x[0])): out += f"| {c} | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} | {v[5]} |\n"
    tot = [sum(v[i] for v in bc.values()) for i in range(6)]
    out += f"| **total** | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** | **{tot[3]}** | **{tot[4]}** | **{tot[5]}** |\n"
    return out

# --- TABLE 3: the Lingva Komitato before the 1909 stacking — ROLL 1 (Boulogne, Aug 1905, as ED 1 printed it; BK-IV transcription)
# plus the Dec 1907 admissions (Cirk. 9a/10a: Asada, Evstifejev, Mann, de Saussure), minus the two tables above. Editor 2026-09-18 15:58.
LK_COUNTRY = {"ANGLUJO": "Britain", "AŬSTRUJO": "Austria-Hungary", "BELGUJO": "Belgium", "BRAZILUJO": "Brazil", "BULGARUJO": "Bulgaria", "ĈILIO": "Chile",
              "DANUJO": "Denmark", "FINLANDO": "Finland", "FRANCUJO": "France", "GERMANUJO": "Germany", "GREKUJO": "Greece", "HISPANUJO": "Spain",
              "HOLANDO": "Netherlands", "HUNGARUJO": "Austria-Hungary", "ISLANDO": "Iceland", "ITALUJO": "Italy", "JAPANUJO": "Japan", "KANADO": "Canada",
              "MEKSIKLANDO": "Mexico", "NORVEGUJO": "Norway", "PERUO": "Peru", "PERSUJO": "Persia", "POLUJO": "Russia (Poland)", "PORTUGALUJO": "Portugal",
              "RUSUJO": "Russia", "SVEDUJO": "Sweden", "SVISUJO": "Switzerland", "UNUIGITAJ ŜTATOJ DE AMERIKO": "USA"}
LK_HAND = {"de saussure": "de-saussure", "saussure": "de-saussure", "bein": "bein", "kabe": "bein", "dombrovski": "dambrauskas", "dombrowski": "dambrauskas",
           "ostrovski": "ostrovskij", "ostrowski": "ostrovskij", "de menil": "de-menil", "menil": "de-menil", "de beaufront": "de-beaufront", "beaufront": "de-beaufront",
           "ĉejka": "cejka", "cejka": "cejka", "schafer": "schafer", "ŝefer": "schafer", "fiŝer": "fiser", "fischer": "fischer", "costa e almeida": "costa-e-almeida",
           "sepulveda cuadra": "sepulveda", "sepúlveda cuadra": "sepulveda", "capé": "cape", "cape": "cape", "zabilon d'her": "zabilon-d-her", "van melckebeke": "van-melckebeke",
           "de ladevèze": "de-ladeveze", "ladevèze": "de-ladeveze", "de wahl": "de-wahl", "wahl": "de-wahl", "kanaloŝŝi-lefler": "kanalossi-lefler", "kanaloŝŝy-lefler": "kanalossi-lefler", "benoist": "benoit", "mackenzie": "mac-kenzie", "blumenthal": "blumenthal", "belmont": "blumenthal", "busutil": "busuttil", "dragumis": "dragoumis", "uitterdyk": "uitterdijk", "thornsteinsson": "thorsteinsson", "seynaeve": "seynaeve", "runeberg": "runeberg", "capé-montrosier": "cape", "cape-montrosier": "cape", "blanc": "blanc", "coutinho": "coutinho"}
LK_1907 = {"asada": "Japan", "evstifejev": "Russia", "mann": "Britain", "de-saussure": "Switzerland"}
def lk_roll1(allstems):
    """[(stem or None, printed name, country, line)] from ROLL 1 of the BK-IV transcription."""
    path = os.path.join(GEN, "profiles", "by-source", "bk-iv-lingva-komitato-rolls-2026-09-08.md")
    out, country, inroll = [], None, False
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("## ROLL 1 —"): inroll = True; continue
        if ln.startswith("## ROLL 1a"): break
        if not inroll: continue
        m = re.match(r"### [IVX]+\. — ([A-ZĈĜĤĴŜŬ ]+?)\.", ln)
        if m: country = LK_COUNTRY.get(m.group(1).strip(), m.group(1).strip()); continue
        m = re.match(r"(\d+)\. (.+?)(?: \(([^)]*)\))? — l\.(\d+)", ln.strip())
        if not m: continue
        name = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", m.group(2))              # drop [editorial] and (town) parentheticals
        name = re.sub(r"\b(D-ro|Dr|Dro|Prof\.?|Pastro|Abato|Fr-ino|F-ino|S-ino|Fraŭlino|Generalo|Kapitano|Kolonelo|K-no|Lt\.?|Kol\.?|Sro|S-ro|Mgr\.?|Rev\.?)\b\.?", "", name)
        name = re.sub(r"\s+", " ", name).strip(" .*,")
        key = fold(name)
        stem = None
        for k, v in LK_HAND.items():
            if (key == fold(k) or key.endswith(" " + fold(k)) or key.startswith(fold(k) + " ")) and v in allstems:
                stem = v; break
        if not stem:
            # one-edit fuzzy on the last token against the roster's surname keys (variant spellings: Dragumis/Dragoumis, Uitterdyk/Uitterdijk)
            last = fold(re.split(r"[\s,]+", name)[-1]) if name else ""
            def ed1(a, b):
                if abs(len(a) - len(b)) > 1: return False
                if len(a) == len(b): return sum(x != y for x, y in zip(a, b)) == 1
                (a, b) = (a, b) if len(a) < len(b) else (b, a)
                for i in range(len(b)):
                    if a == b[:i] + b[i+1:]: return True
                return False
            cands = [st for st in allstems if fold(st.split("-")[-1]) == last or (len(last) >= 6 and ed1(last, fold(st.split("-")[-1])))]
            if len(cands) == 1: stem = cands[0]
        if not stem:
            toks = [t for t in re.split(r"[\s,]+", name) if t]
            for c in ([toks[-1]] if toks else []) + [" ".join(toks[-2:])] + [toks[0]] if toks else []:
                st = hf.slug(hf.canon(c.upper().replace(".", "")))
                if st in allstems: stem = st; break
                st2 = hf.slug(c)
                if st2 in allstems: stem = st2; break
        out.append((stem, m.group(2).strip(), country, m.group(4)))
    return out

# (v0.3.5: the death before end-1908 is «‡», 🟪 now being Volapük; «🟪 †» is the old cards' way of writing it)
DEATH_TOK = re.compile(r"^(🟪 †|‡|†)(?: (.+))?$")

def seq_text(s):
    """A sequence with the death last, † and 🟪 written together (2026-10-31; the editor, on v0.3's «† 1906 → 🟪 1906 →
    Ⓚ 1906»). The year is †'s; a sequence already written so is unchanged."""
    toks = s.split(" → ")
    dead = [DEATH_TOK.match(t) for t in toks if DEATH_TOK.match(t)]
    if not dead: return s
    out = [t for t in toks if not DEATH_TOK.match(t)]
    y = next((m.group(2) for m in dead if m.group(2)), None)
    g = "‡" if any(m.group(1) != "†" for m in dead) else "†"
    return " → ".join(out + [f"{g} {y}" if y else g])

def seq_of(tags):
    return seq_text(" → ".join(f"{g}{'' if y is None else ' ' + str(y)}" for g, y, _, _ in tags))

# THE DATE OF THE INITIAL 🟩 (2026-10-31; the editor: the card to give the date of joining Esperanto as the date of the
# initial green square; Miles's proposal approved): in order of weight (1) the series year of the person's
# first entry in Zamenhof's Adresaro (the «{aperoj: Adresaro de Zamenhof, n-ro N}» lines, tools/adresaro-extract.py);
# (2) a line stating the joining («aliĝis al Esperanto», «eklernis», «fariĝis esperantisto» …), on its own exact date;
# (3) else the earliest exactly dated Esperanto act on the profile, written as a bound, «🟩 ≤ 1903» (a bound is not a
# year, as the editor ruled of Zinoviev's death, 2026-09-19). An act earlier than (1) or (2) makes the date that bound.
JOINED = re.compile(r"(aliĝis al (la )?(Esperant|esperant|movado)|ekesperantistiĝis|esperantistiĝis|eklernis|fariĝis "
                    r"esperantist|lernis (la )?Esperant|komencis lerni|varbita al Esperant|(ek)?konis Esperant|konatiĝis kun "
                    r"Esperant|learned Esperanto|took up Esperanto|became an Esperantist)")
# The Adresaro's entries are not yet harvested into the profiles (Ezri's dowse of 2026-10-29): read from its facts file,
# by the line's head, as the dowse identified each entry with a profile
ADRESARO_FACTS = os.path.join(PROFILES, "by-source", "zamenhof-adresaro-dowse.md")
_ADR = None
def adresaro_years():
    global _ADR
    if _ADR is None:
        _ADR = defaultdict(list)
        if os.path.exists(ADRESARO_FACTS):
            for ln in open(ADRESARO_FACTS, encoding="utf-8"):
                m = LINE.match(ln.rstrip("\n"))
                if m and "{aperoj: Adresaro de Zamenhof" in m.group("rest") and EXACT.match(m.group("year")):
                    loc = next((f for f in m.group("rest").split(" · ") if re.match(r"adresaro-\d{4}-serio", f)), "Adresaro")
                    _ADR[m.group("who")].append((int(EXACT.match(m.group("year")).group(1)), loc))
    return _ADR
ESP_MARK = re.compile(r"Esperant|esperant|Lingvo Internacia|Fundament|Unua Libro")
ACT_KINDS = {"aliĝo", "aperoj", "ofico", "verko", "prelego", "propagando", "fondo", "kongreso"}
EXACT = re.compile(r"\s*\**(1[89]\d\d)(-\d\d){0,2}\**\s*$")

def join_of(L):
    """(the date as written, «» or «≤», the evidence) for the initial 🟩, or None"""
    def best(pred):   # nothing before 1887, the Unua Libro (a misread year, «1803», is no act of the language)
        c = [(int(m.group(1)), ln) for ln in L if pred(ln) for m in [EXACT.match(ln["ystr"])] if m and int(m.group(1)) >= 1887]
        return min(c, key=lambda x: x[0]) if c else None
    adr = best(lambda ln: ln["kind"] == "aperoj" and ln["obj"].startswith("Adresaro de Zamenhof"))
    fromfile = [(y, {"loc": loc}) for who in {ln["who"] for ln in L} for y, loc in adresaro_years().get(who, [])]
    if fromfile:
        f = min(fromfile, key=lambda x: x[0])
        adr = f if not adr or f[0] < adr[0] else adr
    said = best(lambda ln: JOINED.search(ln["text"].split(" · ")[0]))
    act = best(lambda ln: ln["kind"] in ACT_KINDS and ESP_MARK.search(ln["obj"] + " " + ln["text"].split(" · ")[0]))
    exact = min((x for x in (adr, said) if x), key=lambda x: x[0], default=None)
    if exact and not (act and act[0] < exact[0]):
        how = "the Adresaro's series year" if exact is adr else "a line stating the joining"
        return str(exact[0]), "", f"joined: {how} [{exact[1]['loc'][:90]}]"
    if act:
        return f"≤ {act[0]}", "≤", f"joined by: the earliest dated Esperanto act on the profile [{act[1]['loc'][:90]}]"
    return None

def with_join(stem, caption, s):
    """the sequence's initial 🟩 given its date (join_of); (sequence, evidence or None)"""
    if not s.startswith("🟩") or re.match(r"^🟩 [^→]", s) or not stem: return s, None
    j = join_of(lines_of(stem, caption))
    return (s.replace("🟩", f"🟩 {j[0]}", 1), f"🟩: {j[2]}") if j else (s, None)

def green(stem, s):
    """the ruled initial 🟩 (INITIAL_GREEN) put first where a sequence lacks it"""
    return s if stem not in INITIAL_GREEN or s.startswith("🟩") else "🟩 → " + s

# THE LK CHECK'S CORRECTIONS (2026-10-31; the editor 13:2x, on the eight proposed in
# geniza/BINGO-LK-CHECK-2026-10-31.md from the notices, sources/oge-rolls/LK-DEPARTURES-2026-10-31.md; and the OGE rolls ranked above the
# Bohemian Esperantist as an authority, on Holub: OGE vol. 3, PDF p. 337 (printed 237), «Eksiĝoj» of the February 1911
# number, names him among those «konsiderataj kiel eksiĝintaj, pro nerespondo»). stem → [(op, glyph, year, new glyph,
# new year, why)]: «add» a mark (year None: undated, put before the death); «change» a mark; «remove» a mark (v0.3.4).
_OGE = "Oficiala Gazeto Esperantista"
CORRECTIONS = {
    "meray": [("add", "⭘", 1910, None, None, f"resigned from the LK, «ĉar lia aĝo ne ebligas lian efektivan partoprenon» ({_OGE}, Nov 1910, `sources/oge-rolls/3-0219…`)")],
    "miletz": [("add", "⭕", 1908, None, None, f"struck for answering no circular (LK Cirkulero 10, voted 41 to 5; {_OGE}, Aug 1908, `sources/oge-rolls/1-0140…`)")],
    "cederblad": [("add", "⭕", 1908, None, None, f"struck for answering no circular (LK Cirkulero 10; {_OGE}, Aug 1908)")],
    "guilbeau": [("add", "⭕", 1908, None, None, f"struck for answering no circular (LK Cirkulero 10; {_OGE}, Aug 1908)")],
    "mac-kenzie": [("add", "⭕", 1908, None, None, f"struck for answering no circular (LK Cirkulero 10; {_OGE}, Aug 1908)")],
    "saint-martin": [("add", "⭕", 1908, None, None, f"struck for answering no circular (LK Cirkulero 10; {_OGE}, Aug 1908)")],
    "guillaume": [("add", "⭘", 1910, None, None, f"resigned, his professional work too heavy ({_OGE}, Nov 1910, `sources/oge-rolls/3-0219…`)")],
    "zinoviev": [("change", "⭘", "1914", "⭘", "1913", f"«sendis sian eksiĝon de la Lingva Komitato» ({_OGE}, Dec 1913, `sources/oge-rolls/6-0205…`)")],
    "hodler": [("add", "⭘", None, None, None, f"had resigned from the LK, the year not given (his obituary, {_OGE}, May 1920, `sources/oge-rolls/7-0219…`)")],
    "lallemant": [("add", "⭘", 1920, None, None, f"resigned from the LK for his health ({_OGE}, May 1920, `sources/oge-rolls/7-0219…`); his seat's date to find")],
    "holub": [("change", "🔴", "1911", "⭕", "1911", f"«konsiderataj kiel eksiĝintaj, pro nerespondo» ({_OGE} vol. 3, PDF p. 337, printed 237, Feb 1911); not for anti-Esperanto activity")],
    # v0.3.4 (the editor 18:2x, on the marks the notices did not hold; approved to the changes): the
    # congress reports and the rolls' corrections, BINGO-LK-CHECK-2026-10-31.md § «The marks not in the notices»
    "talmey": [("change", "⭕", "1911", "⭕", "1912", f"«la Akademio devis konsideri kiel eksiĝintaj S-rojn Gaston Moch kaj Max Talmey», no reason given (Boirac's report to the Eighth Congress, {_OGE} vol. 5, PDF 78, Aug 1912)")],
    "bagnulo": [("add", "⭕", 1914, None, None, f"struck from the LK's list, «de tre longa tempo, ne donis signon de vivo» (Boirac's report to the Tenth Congress, {_OGE} vol. 7, PDF 43, Jul 1914); the ⭕ 1911 is UEA's")],
    "beauchemin": [],
    "asada": [("change", "⭕", "1909", "⭘", "1911", f"on the lists of 1910 and Feb 1911; then «petas, ke oni ne konsideru lin kiel anon de tiu Komitato», too busy for its duties (the July 1911 election's «Korektoj», {_OGE} vol. 4)")],
    "de-saussure": [("remove", "⭕", "1912", None, None, f"not struck: at the Kraków sitting the Academy «decidis ne konsideri lin, kiel eksiĝintan» ({_OGE} vol. 5, PDF 172, 1912); on the LK roll of 1 Jan 1920 ({_OGE} vol. 7, PDF 199)")],
    "michaux": [("add", "⭕", 1914, None, None, f"left off the 1914 re-election: «La Akademio konservis ĉiujn nomojn de malnovaj anoj, kun escepto de la nomo de S-ro Michaux» (Boirac's report to the Tenth Congress, {_OGE} vol. 7, PDF 43, Jul 1914); not on the roll of 1 Jan 1920")],
}
CORRECTIONS = {k: v for k, v in CORRECTIONS.items() if v}
SPAN_FIX = {"michaux": ("DOUBLE MEMBERSHIP 1909–1911", "DOUBLE MEMBERSHIP 1909–1914",
                        "to 1914: an LK voter in July 1909 and July 1911, at the Antwerp session of 1911 and on the Bern report of July 1913; left off the re-election of 1914"),
            "de-saussure": ("DOUBLE MEMBERSHIP 1910–1912", "DOUBLE MEMBERSHIP 1910–1920",
                            "to 1920 at least: not struck in 1912 (the Academy's decision at Kraków), on the LK roll of 1 Jan 1920; its end to be found")}

def correct(stem, seq, ev):
    """the CORRECTIONS and SPAN_FIX of a stem applied to its sequence and evidence"""
    toks = [t for t in seq.split(" → ") if t]
    for op, g, y, g2, y2, why in CORRECTIONS.get(stem, []):
        if op == "change":
            toks = [f"{g2} {y2}" if t == f"{g} {y}" else t for t in toks]
        elif op == "remove":
            toks = [t for t in toks if t != f"{g} {y}"]
        else:
            tok = g if y is None else f"{g} {y}"
            if tok in toks: continue
            dead = next((i for i, t in enumerate(toks) if DEATH_TOK.match(t)), len(toks))
            at = dead if y is None else next((i for i, t in enumerate(toks[:dead]) if not t.startswith("🟩")
                                              and re.search(r"(\d{4})", t) and int(re.search(r"(\d{4})", t).group(1)) > y), dead)
            toks.insert(at, tok)
        ev = f"{g2 or g}: RULED 2026-10-31: {why} [LK check]" + (" ‖ " + ev if ev else "")
    if stem in SPAN_FIX:
        a, b, why = SPAN_FIX[stem]
        ev = ev.replace(a, b) + f" ‖ ◐: RULED 2026-10-31: span {why} [LK check]"
    return " → ".join(toks), ev

def resequence(old, new):
    """--resequence OLD NEW (2026-10-31): the card of version OLD with its sequences rewritten by seq_text() and the
    ruled initial 🟩 (INITIAL_GREEN) put first, and nothing else, as version NEW (the card is hand-edited: a re-cut from today's profiles would change more than the order).
    Writes bingo-card-v<NEW>.csv, -supplement.csv, -lk1905.csv and .md; refuses if any exists."""
    out_dir = os.environ.get("BINGO_OUT", os.path.join(GEN, "bingo-card"))
    P = lambda v, suf: os.path.join(out_dir, f"bingo-card-v{v}{suf}")
    sufs = [".csv", "-supplement.csv", "-lk1905.csv", ".md"]
    there = [P(new, s) for s in sufs if os.path.exists(P(new, s))]
    if there: sys.exit("refusing, nothing written: exists: " + ", ".join(os.path.basename(p) for p in there))
    n, MAP = 0, {}   # (stem, the old sequence) → the new, from the CSVs, for the .md's rows
    for s in sufs[:3]:
        R = list(csv.DictReader(open(P(old, s), encoding="utf-8")))
        with open(P(new, s), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R[0].keys())); w.writeheader()
            for r in R:
                orig = r["tags_in_sequence"]
                t = green(r["stem"], seq_text(orig))
                if t.startswith("🟩 → ") and r["stem"] in INITIAL_GREEN and "🟩:" not in r["evidence"]:
                    r["evidence"] = f"🟩: {INITIAL_GREEN[r['stem']]} [] ‖ " + r["evidence"]
                t, ev = with_join(r["stem"], r.get("caption", ""), t)
                if ev: r["evidence"] = ev + " ‖ " + r["evidence"]
                t, r["evidence"] = correct(r["stem"], t, r["evidence"])
                MAP[(r["stem"], orig)] = t
                n += t != orig; r["tags_in_sequence"] = t
                w.writerow(r)
    L, col, table = [], None, None
    delta = collections.defaultdict(collections.Counter)   # table → glyph → people gained (lost: negative), for the totals
    # table → country → [Ido, other, any camp, struck, ‡] gained, for the «| country (1906 borders) |» tables
    cdelta = collections.defaultdict(lambda: collections.defaultdict(lambda: [0] * 5))
    person_cols = lambda g: [bool(g & {"🟦", "💙"}), bool(g & {"🟧", "🧡"}), bool(g & {"🟦", "💙", "🟧", "🧡"}),
                             bool(g & {"🔴", "⭕"}), "‡" in g]
    ccol = None
    has = lambda q: {w for t in q.split(" → ") for w in t.split(" ") if w and not re.match(r"^(\d{4}|≤)$", w)}   # «‡ † 1906»: both
    for line in open(P(old, ".md"), encoding="utf-8"):
        if line.startswith("|"):
            cells = line.rstrip("\n").split(" | ")
            hd = [c.strip().strip("|").strip() for c in cells]   # a header's last cell carries the closing «|»
            if "tags in sequence" in hd:
                col = hd.index("tags in sequence")
                ccol = hd.index("country") if "country" in hd else None
                table = {"| plate": "album", "| stem": "supplement"}.get(cells[0].strip(), "supplement")
                if "as the roll prints him" in hd: table = "table3"
            elif col is not None and len(cells) > col and cells[col].strip() and not cells[col].startswith("-"):
                st = next((m.group(1) for c in cells for m in [re.fullmatch(r"`([^`]+)`", c.strip().strip("|").strip())] if m), "")
                # the last cell of a row carries the closing « |» (the supplement's and table 3's sequence is their last)
                tail = " |" if cells[col].rstrip().endswith(" |") else ""
                orig = cells[col].rstrip()[:-2].strip() if tail else cells[col].strip(); was = seq_text(orig)
                cells[col] = (MAP.get((st, orig)) or correct(st, with_join(st, "", green(st, was))[0], "")[0]) + tail
                nw = cells[col][:-2] if tail else cells[col]
                for g_ in has(orig) | has(nw):
                    delta[table][g_] += (g_ in has(nw)) - (g_ in has(orig))
                if ccol is not None:   # the country tables' columns, per person (v0.3.4: they had not followed)
                    cty = cells[ccol].strip().strip("|").strip()
                    for k, v in enumerate(person_cols(has(nw))):
                        cdelta[table][cty][k] += v - person_cols(has(orig))[k]
                line = " | ".join(cells) + "\n"
        else:
            col = None if line.strip() else col
        if line.startswith("# The Schuck-album bingo card — v" + old):
            line = line.replace("— v" + old, "— v" + new, 1).rstrip("\n") + (f" · re-sequenced 2026-10-31 from v{old}: the death "
                   "last, «‡ †» written together; the ruled initial 🟩 (Privat, Schneeberger); the initial 🟩 dated by the "
                   "joining (the Adresaro's series year, a line stating it, else «≤» the earliest Esperanto act); the LK check's "
                   "corrections (geniza/BINGO-LK-CHECK-2026-10-31.md)\n")
        L.append(line)
    # the totals follow the marks put in or taken out (each «### Totals — …» table's «| <mark> | <label> | N |» rows)
    adds = {"the album's": ["album"], "the supplement's": ["supplement"], "both tables together": ["album", "supplement"],
            "table 3's": ["table3"], "all three tables": ["album", "supplement", "table3"]}
    head = None
    for i, line in enumerate(L):
        if line.startswith("### Totals"): head = next((k for k in adds if k in line), None)
        m = re.match(r"^\| (\S+) \| ([^|]+) \| (\d+) \|$", line.rstrip("\n"))
        if m and head and m.group(1) in ORDER:
            L[i] = f"| {m.group(1)} | {m.group(2)} | {int(m.group(3)) + sum(delta[t][m.group(1)] for t in adds[head])} |\n"
        c = re.match(r"^\| ([^|*]+?) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", line.rstrip("\n"))
        if c and head:
            v = [int(x) + sum(cdelta[t][c.group(1)][k] for t in adds[head]) for k, x in enumerate(c.groups()[2:])]
            L[i] = f"| {c.group(1)} | {c.group(2)} | " + " | ".join(map(str, v)) + " |\n"
    open(P(new, ".md"), "w", encoding="utf-8").write("".join(L))
    print(f"v{old} → v{new}: {n} sequences rewritten in the three CSVs; → {', '.join(os.path.basename(P(new, s)) for s in sufs)}")
    return 0

# v0.3.5 (2026-11-05; the editor 18:4x: the date of adherence to Volapük added where it applies, as a purple
# square, the old purple square (out of scope, dead before Ido) becoming a double
# dagger; an orange circle for those who invented auxiliary languages of their own; De Beaufront's joining in 1887
# as the case for using the Adresaro more, beside the Enciklopedio de Esperanto). Read from bingo-card/BINGO-EVIDENCE-2026-11-05.md
# (tools/bingo-evidence.py). A key is the stem, or (stem, country) where a stem is shared. An initial 🟩 for everyone, dated:
# the first own entry in the Adresaro's series, or the Enciklopedio's stated year, whichever is earlier.
_ADR_S = lambda y, s, n: f"Adresaro {y}, serio {s}, n-ro {n}"
JOIN_RULED = {
    "nylen": ("1892", "EdE, «E-isto de aŭg. 1892»"),
    "zamenhof": ("1887", "the editor 2026-11-06"),
    "de-beaufront": ("1888", "EdE, «aliĝis al E jam en 1888» (l. 2170; also l. 8031), and the album; Adresaro 1889, serio 1, n-ro 46, pins only «by 1889»"),   # was 1887 to 2026-11-08 (the editor)
    "rhodes": ("1900", _ADR_S(1900, 21, 5260)), "motteau": ("1901", "EdE, «E-istiĝis en 1901»; " + _ADR_S(1901, 22, 6266)),
    "schafer": ("1903", _ADR_S(1903, 24, 7778)), "talmey": ("1904", _ADR_S(1904, 25, 9777)),
    "beauchemin": ("1901", "the profile, April 1901; " + _ADR_S(1901, 22, 6358)), "kuhnl": ("1900", "EdE, «E-isto de 1900»"),
    "jamin": ("1898", _ADR_S(1898, 19, 4375)), ("lemaire", "Belgium"): ("1897", _ADR_S(1897, 18, 4020)),
    ("lemaire", "France"): ("1892", _ADR_S(1892, 11, 2026)), "coox": ("1903", _ADR_S(1903, 24, 7836)),
    "van-melckebeke": ("1902", _ADR_S(1902, 23, 7125)), "peltier": ("≤ 1895", "sending names to the Adresaro, 1895, serio 17, n-ro 3659"),
    "michaux": ("1901", _ADR_S(1901, 22, 6305)), "moch": ("1889", "EdE, «aliĝis al E en 1889»; his own account, Lingvo Internacia 1897"),
    "javal": ("1903", "EdE, «li praktikis ĝin nur de 1903»"), "lambert": ("1899", _ADR_S(1899, 20, 4731)),
    "zabilon-d-her": ("1895", _ADR_S(1895, 17, 3749)), "einstein": ("1888", "EdE, the Unua Libro received in 1888, «li tuj konvertiĝis»; " + _ADR_S(1889, 1, 205)),
    "trompeter": ("1889", _ADR_S(1889, 1, 918)), "meier": ("1889", "EdE, «jam en 1889 konatiĝis kun E»"), "wallon": ("1889", "EdE, «E-isto de 1889»"),
    "villanueva": ("1902", "EdE, «E-isto de 1902»"), "bicknell": ("1897", "EdE, «E-isto de 1897»"), "marich": ("1901", "EdE, «E-isto de 1901»"),
    "wasniewski": ("1893", _ADR_S(1893, 13, 2572)), "dambrauskas": ("1889", _ADR_S(1889, 1, 186)), "kofman": ("1892", "the profile, «E-iĝis: 1892» (Szerdahelyi 1979)"),
    "avilov": ("1889", _ADR_S(1889, 1, 30)), "dragoumis": ("1903", _ADR_S(1903, 24, 8800)), "krikortz": ("1893", _ADR_S(1893, 13, 2465)),
    "ahlberg": ("1892", _ADR_S(1892, 11, 1990)), "uitterdijk": ("1898", "EdE, «E-isto de 1898»"), "de-wahl": ("1888", "the profile, «aliĝi al Esperanto en 1888»; " + _ADR_S(1889, 1, 932)),
    "sentis": ("1898", "EdE, «E-isto de 1898»"), "kraus": ("1895", "EdE, «E-isto de 1895»"), "runeberg": ("1901", "EdE, «E-istiĝis en 1901»"),
    "bricard": ("1901", _ADR_S(1901, 22, 6489)), "saquet": ("1902", _ADR_S(1902, 23, 7566)), "krumpholc": ("1902", _ADR_S(1902, 23, 7025)),
    "huet": ("1901", _ADR_S(1901, 22, 6486)), "asada": ("1906", _ADR_S(1906, 27, 14522)),
    "zinoviev": ("1887", "his own word, «malnuva esperantisto» of 1887 (Progreso, 2-a yaro, PDF 570)"),
    "boulet": ("1902", "EdE, «E-iĝis en 1902»; born 2 Jan 1884, so the 1895 of the earlier cards, an Adresaro entry, is another Boulet"),
    "postnikov": ("1893", _ADR_S(1893, 14, 2817) + ", «F. A. Postnikov»"), "lojko": ("1889", _ADR_S(1889, 1, 569) + ", «Lojko, I.»"),
    "atanasov": ("1900", _ADR_S(1900, 21, 5204) + ", «Georgij Atanasov (lernanto de gimnazio)», Varna"), "morin": ("1903", "the Adresaro's series year, «Anselmo Morin», Santa Rosa, Veracruz"),
}
# 🟪: a date from a report is only a date by which he had adhered (the editor 19:0x, on Beauchemin's 1901: a date of
# reporting, not of joining, any joining of Volapük after 1890 suspect, so taken as a terminus ante quem)
VOLAPUK = {
    "wallon": ("≤ 1890", "Volapükabled zenodik 1890, no. 1251, «Wallon Paul in Gleiwitz» (volapukabled-1890-anno-0053, PDF 2, l. 120); Paul Polykarp Wallon the card's Karp Wallon (the editor 2026-11-08 02:2x)"),
    "einstein": ("1883", "began to study it, by his own count (Volapükabled talik 1888, PDF 7)"), "grabowski": ("1886", "the profile: about a year before Esperanto"),
    "de-wahl": ("≤ 1888", "teacher's diploma, May 1888"), "deligny": ("≤ 1887", "leading Volapük courses at Saint-Omer, end of 1887"),
    "lauren": ("≤ 1888", "Allmänna Svenska Volapükföreningen, 1887–1888"), "gustafsson": ("≤ 1888", "Allmänna Svenska Volapükföreningen, 1887–1888"),
    "marignoni": ("≤ 1889", "EdE, «Eksvolapükisto»"), "meier": ("≤ 1889", "EdE, «Volapükisto»"), "devjatnin": ("≤ 1891", "EdE, «Antaŭe li estis Volapükisto»"),
    "bicknell": ("≤ 1897", "EdE, «Eksvolapükisto»"), "bulthuis": ("≤ 1899", "EdE; diploma, 12 May 1899"), "midthus": ("≤ 1900", "EdE, «Studis Volapükon antaŭ 1900»"),
    "motteau": ("≤ 1901", "EdE, «Antaŭe Volapükisto»"), "beauchemin": ("≤ 1901", "«jam studietis Volapükon», reported late 1901; RULED a terminus ante quem"),
    "evstifejev": ("≤ 1904", "«konas kaj skribas Volapükon», reported 1904; a terminus ante quem, as Beauchemin"),
}
# from the Volapük directories and press themselves (the editor 2026-11-06, asking that the Volapük directories
# and press be searched for a terminus ante quem): every name on the card sought in them; these two the only new ones
VOLAPUK.update({
    "meier": ("≤ 1882", "«L. E. Meier, redakel», Munich, in the Volapükabled zenodik's list, 1882 (ANNO_e2s_18820061, l. 563, l. 584), by name and town"),
    # the editor 2026-11-06: Le Volapük's 26 issues had been left out of that search
    "krikortz": ("≤ 1888", "«L'Association française a accordé le diplôme de spodal à: [...] MM Krikortz de Nerikes Knista» (Le Volapük, Dec 1888, l. 392); he was born in Knista parish"),
    "nylen": ("≤ 1889", "«A. P. Nylen, Norrköping», Volapükisten 1889 (PDF 89, l. 12143; l. 9984), an inference: Adresaro 1893, n-ro 2255, «Nylén, A. P., studento. Gierdtorp, Hellestad» is La Esperantisto's «Nylen, Paul» at the same address, so the flipped initials are his; and he sends Adresaro names from Östergötland and Norrköping, 1897–1898"),
})
OWN_AUXLANG = {   # the year and the project, Dulichenko 1990 (the entry's number) unless said
    "zamenhof": ("1878", "Lingwe Universala, then Esperanto (Dulichenko 189, 210)"), "de-beaufront": ("≤ 1887", "Adjuvanto, by his own account before he read Esperanto; Dulichenko 268 files it under 1896"),
    "grabowski": ("1896", "Modern Latin, Linguo Moderna (Dulichenko 269, 271)"), "berthelot": ("1904", "Fonetiko Litera (Dulichenko 316)"), "de-saussure": ("1907", "Antido (Dulichenko 337)"),
    ("lemaire", "Belgium"): ("1908", "Ilo (Dulichenko 354)"), "jamin": ("1908", "Mez-Voio (Dulichenko 357)"), "de-wahl": ("1906", "Auli, «ekde 1906» (Manders 1950, PDF 22); Dulichenko 362 files it at 1909; then Occidental"),
    "michaux": ("1909", "Romanal (Dulichenko 372)"), "sentis": ("1910", "Esperanta evoluo, to 1928 (Dulichenko 538)"), "talmey": ("1924", "Arulo, also Gloro (Dulichenko 498)"),
    "meazzini": ("1928", "Idiom Di Omni (Dulichenko 532.1)"),
}

# 🟧 where the other auxlang was their own, so 🟠 says it already (the editor 2026-11-06: Michaux's orange square beside his orange
# circle possibly redundant, unless the square stands for Latino sine Flexione: Michaux's 1909 was his Romanal,
# but he did turn to the Academia pro Interlingua in 1912): stem → the mark to drop, the mark in its place or None, why
OWN_ORANGE = {
    "michaux": ("🟧 1909", "🟧 1912", "the 1909 mark was his own Romanal; 1912, the Academia pro Interlingua (La Belga Sonorilo 1910, PDF 150; the profile, May 1912)"),
    "talmey": ("🟧 1924", None, "his own Arulo"), "de-wahl": ("🟧 1922", "🟠 1922", "his own Occidental"), "de-saussure": ("🟧 1910", "🟠 1910", "his own Antido 2 (Dulichenko)"),
}

# The inventors who stayed (the editor 2026-11-06: the inventors who stayed told apart from those who left;
# one still active after inventing a language gets a green square back at the next recorded
# Esperanto activity, and the same for Ido). Those with a mark after 🟠 stayed: here, or Jamin and Ch. Lemaire's 🟦 1908. No later mark: left
BACK = {
    "berthelot": [("🟩 1905", "Vocabulaire Français-Esperanto, 3rd edition, with Cart and Merckens, Jan 1905")],
    # the editor 00:0x: not a stayer
    "grabowski": [("⬜ 1894", "left Esperanto after the vote of May 1894, «por preskaŭ dek jaroj» (Korĵenkov 2005)"),
                  ("🟢 1904", "returned, May 1904, after reading Couturat and Leau's Histoire (Lingvo Internacia; Sinjorino Twardowska, July 1904)")],
    "de-saussure": [("🟩 1908", "public letter in Paris-Esperanto, May 1908"), ("🟩 1910", "translated Naville's La Devo into Esperanto, 1910")],
    "michaux": [("🟩 1910", "greetings to the Sixth Universal Congress, 15 Aug 1910")],
    "sentis": [("🟩 1910", "the Lingva Komitato's grammar commission, 25 July 1910")],
    # the editor 2026-11-06: his last acts of his own, the vote of April 1896 and the
    # Princidino of August 1896, reviewed February 1897; then only the catalogues' reprints. Auli's 1906 then has the 🟦 1908 after it
    "de-wahl": [("⬜ 1897", "stayed away after 1897; Lingvo Internacia 1896-04, 1896-08, 1897-02 his last, the catalogues to 1904 only reprints (Manders 1950 has him leave in 1894)")],
}

# THE NAMESAKES THE HARVEST SPLIT (the editor 2026-11-06: Postnikov is Fjodor, Aleksandr too late for Bein's speech, hence
# no facts for him; the St. Atanasoff of Plovdiv and Lojko's zero both queried as wrong): the card read their
# shared profile, by then only an index, so no lines and no marks. stem → the sequence on his own profile, why, the hand-pass cell
NAMESAKE = {
    "postnikov": ("🟩 → † 1952", "Fjodor A. Postnikov, by the editor's ruling; † from fjodor-a-postnikov.md", ""),
    "lojko": ("🟩 → ‡ 1905", "Ivan Markoviĉ Lojko, as with Postnikov: the pioneer, Vsevolod the son too recent for «de longe» (Schuck p. 17); † 23 June 1905, ivan-markovic-lojko.md", ""),
    "atanasov": ("🟩", "Georgi Atanasov: the album's prose, «Sroj Oreŝkow kaj Atanasow en Plovidiv, la redaktoroj de Rondiranto», and every witness to the Plovdiv editing name G.; no St. in Plovdiv is held. The other reading, Sterio of Varna's portrait with Georgi's role (schuck-album-missing-three-2026-09-15.md)", ""),
    "morin": ("🟩 → † 1916", "Anselmo Morin; † from Amerika Esperantisto, Sept–Oct 1916, anselmo-morin.md. The tool's 🟦 1908 there not taken: the line is Boirac representing him at Dresden", ""),
    # the editor 2026-11-06. Not a namesake, a row re-read whole: the LK check took the garbled notice for a guess
    "twombley": ("🟩 ≤ 1904 → Ⓚ 1906 → 🟦 1909 → ◐ 1909 → ⭘ 1910 → 🧡 1911 → · 1934", "⭘: «sendis sian eksiĝon» (OGE vol. 3, 25 June 1910), the reason in Boirac's report (OGE, 25 Oct 1910): the LK not progressive enough. Ⓚ: the Boulogne roll, «Twombly (Brooklyn)». 🟦 and ◐, Miles's reading: «partiani di la reformo» (Progreso 2, PDF 87, March 1909), some ten signed pieces there 1909–1910, on the LK till June 1910. 🧡, Miles's reading: two pieces in Discussiones, Feb 1911", ""),
}
NAMESAKE["lloyd"] = ("🟩 1903 → ‡ 1906", "Richard John Lloyd drowned in the Rhône, 29 Aug 1906, at the Geneva congress (EdE s.v. Lloyd; the profile; Zamenhof's speech): the «·» 1908 and 1917 no acts of his", "")
NAMESAKE["davidov"] = ("🟩 1898", "the album's Jonko Davidov of Silistra, the merchant; the † 1967 and · 1921 of the earlier cards were Georgo Karpoviĉ Davidov's (the ÖNB, «Davidov, Georgo, 1879-1967»)", "")
NAMESAKE["blanc"] = ("🟩 1902 → ‡ ≤ 1906", "RULED 2026-11-06 19:3x, correcting 🟩 1898: Prof. G. Blanc of Perugia, then Rome, LK for Italy. 🟩 1902: L'Espérantiste 1902-6, PDF 14, l. 1018 (SFPE), and the Adresaro's series 23, no. 7553. ‡ ≤ 1906: his questionnaire came back marked «la adresato mortis», L'Espérantiste 1906-6, PDF 23, l. 2169. The 1898 and 1899 lines in the profile are Henri Blanc of Livron, France; the Blancs of Dijon and Lyon other people", "")
ROW_CAMP = {"twombley": (1, 1, 1), "hanauer": (1, 0, 1), "peltier": (1, 0, 1)}   # the country tables' gains of a re-read row: Ido, other, any camp
NAMESAKE["boulet"] = ("🟩 → · 1908 → Ⓚ 1909 → ⭘", "«LK, 1909; eksiĝis pro troa laboro» (Enciklopedio, PDF 101); still on the roll of 1 Jan 1920, so the resignation undated (the review of 2026-11-06, item 5)", "")

# THE REVIEW OF THE MARKS (bingo-card/REVIEW-2026-11-06-marks.md; the editor 2026-11-06, to its 14 recommendations).
# stem → the marks to add, each with why, and any mark they replace; ahead of: a mark of that year put before those glyphs
MARKS_REVIEWED = {
    "ellis": [("⭘ 1911", "«sendis al ni sian eksiĝon de Akademiano» (Oficiala Gazeto 3, PDF 387, 25 Feb 1911)")],
    "pollen": [("⭘ 1920", "his name struck at his own request (Oficiala Gazeto 7, PDF 197, 25 Jan 1920)")],
    "abesgus": [("⭘ 1906", "«kelkaj komitatanoj ĉu eksiĝis, nome Sroj» Abesgus and Oreskov (Dua Universala Kongreso, PDF 20)")],
    "oreskov": [("⭘ 1906", "«kelkaj komitatanoj ĉu eksiĝis, nome Sroj» Abesgus and Oreskov (Dua Universala Kongreso, PDF 20); Schuck 1906 still captions him L. K.")],
    "de-beaufront": [("🟦 1907", "«En 1907, kiam la aŭtoro fariĝis ‹ private › Idisto» (Lingvo Internacia 1908-5, PDF 23); in place of 🟦 1909"),
                     ("⭘ ≤ 1908", "«11 eksiĝis propravole (inter ili L de» Beaufront, before 2 Jan 1908 (Zakrzewski 1913, PDF 125)")],
    "hanauer": [("🟦 1912", "«So Hanauer, ex-Esp-isto», with the Ido lecture at Chemnitz (Progreso 5, PDF 609, Nov 1912)")],
    "peltier": [("💙 ≤ 1909", "one of the first and most fervent pioneers of the reform (L'Espérantiste, Nov 1909, PDF 1); Progreso 4, PDF 221: the Ido side's, after his death")],
    "de-wahl": [("🟧 ≤ 1906", "«aliĝis al Idiom Neutral, provante ankaŭ ĝin reformi» (Lingvo Internacia 1908-4, PDF 32); Dulichenko 328")],
    "michaux": [("⬜ 1911", "forced to leave the Esperantists after Antwerp (La Belga Sonorilo, May 1912, PDF 6); Korĵenkov 2005, PDF 56")],
    "holub": [("⬜ 1911", "struck for silence, as Allum and Emeric, with no exactly dated act after")],
}
MARK_REPLACES = {"de-beaufront": "🟦 1909"}
MARK_AHEAD = {"de-wahl": "🟠"}
# the second round, items 15–22 (the editor): Asnes corrected; the rest kept, the other year noted
# v0.4.4 (the editor 2026-11-06; dowse/onb-katalogo-2026-11-06/ONB-DIFFERENCES-VERDICTS-2026-11-06.md): item 22 of the review overturned, a 30 November on eo.wikipedia being a year-only Wikidata date of the year after
DEATH_CORRECT = {"asnes": ("† 1922", "Esperanto Wikipedia's «18xx — 1922» and the ÖNB's «1871-1922»; the card's 1921 came from a summary of the article, not the article"),
                 "meazzini": ("† 1939", "the ÖNB's 1939; Wikidata's 30 Nov 1938 reads as a year-only date of 1939, probably, as on Atanasov (ONB-DIFFERENCES-VERDICTS-2026-11-06)"),
                 "bricard": ("† 1943", "most likely 26 Nov 1943: Wikidata, from a Wikipedia, and the ÖNB on one record; 1944 from the GND and eo-Raoul_Bricard; no source of the time checked (ONB-DIFFERENCES-VERDICTS-2026-11-06)")}
MARK_NOTE = {"meier": "† 1916 kept: a notice of the time, 2 Jan 1916 (Amerika Esperantisto, April 1916, PDF 10); the ÖNB has 1919",
             "talmey": "⭕ kept: Privat's proposal to strike him for acting against Esperanto, Antwerp 1911 (Oficiala Gazeto 4, PDF 118; the name garbled), was one member's, and Boirac's report of 1912 gives no reason"}

# THE CANONICAL FULL NAME (the editor 2026-11-06; for example Evgenij Viktorovič Radvan-Rypinskij,
# as the ÖNB gives it): by his rule for a person's main form, of 2026-10-17 (NAMES-REGISTER.tsv's head), the title of the saved Esperanto Wikipedia page,
# else the Enciklopedio's heading, else the usual form as the sources print it; patronymics and middle names added where a source spells them
# out. stem, or (stem, country) where one stem is two people → the name; the source by the lists below
_NAME_EO = {
    "de-beaufront": "Louis de Beaufront", "geoghegan": "Richard Geoghegan", "talmey": "Max Talmey", "vargas": "Ambrosio Vargas", "beauchemin": "A. P. Beauchemin", "kuhnl": "Eduard Kühnl",
    "simon": "Otto Simon", "cejka": "Theodor Čejka", "jamin": "Joseph Jamin", "seynaeve": "Maurice Seynaeve", ("lemaire", "Belgium"): "Charles Lemaire", ("lemaire", "France"): "René Lemaire",
    "van-melckebeke": "Raymond Van Melckebeke", "matton": "Pierre Ernest Matton", "sebert": "Hippolyte Sebert", "peltier": "Émile Peltier", "boirac": "Émile Boirac", "meray": "Charles Méray",
    "michaux": "Alfred Michaux", "deligny": "Ernest Deligny", "moch": "Gaston Moch", "javal": "Emile Javal", "bourlet": "Carlo Bourlet", "lambert": "Charles Lambert",
    "zabilon-d-her": "Jeanne Zabilon d'her Ranfaing", "cart": "Théophile Cart", "verax": "Charles Verax", "fruictier": "Paul Fruictier", "einstein": "Leopold Einstein",
    "trompeter": "Wilhelm Heinrich Trompeter", "borel": "Jean Borel", "meier": "Ludwig Emil Meier", "christaller": "Paul Gottfried Christaller", "schmidt": "Adolf Schmidt", "ebner": "Adolf Ebner",
    "hanauer": "Julius Hanauer", "barthel": "Karl Barthel", "inglada": "Vicente Inglada Ors", "villanueva": "Antonio López Villanueva", "costa-e-almeida": "Manuel Ribeiro da Costa e Almeida",
    "sepulveda": "Luis Enrique Sepúlveda Cuadra", "junck": "Rosa Junck", "gallois": "Albert Gallois", "meazzini": "Giacomo Meazzini", "marignoni": "Daniele Marignoni", "bagnulo": "Raffaele Bagnulo",
    "sussmuth": "John Joseph Sussmuth", "lengyel": "Paŭlo Lengyel", "marich": "Ágoston Marich", "busuttil": "Gustavo Busuttil", "grabowski": "Antoni Grabowski", "bein": "Kazimierz Bein",
    "wasniewski": "Jozefo Wasniewski", "kofman": "Abram Kofman", "asnes": "Aleksandr Asnes", "oreskov": "Georgi Oreŝkov", "ahlberg": "Per Ahlberg", "nylen": "Paul Axel Nylén",
    "langlet": "Valdemar Langlet", "thorsteinsson": "Thorsteinn Thorsteinsson", "uitterdijk": "Dreves Uitterdijk", "bulthuis": "Hendrik Bulthuis", "hageler": "Alf Hageler", "renard": "Théodore Renard",
    "privat": "Edmond Privat", "schneeberger": "Friedrich Schneeberger", "kotzin": "Boris Kotzin", "boulet": "Paul Boulet", "bricard": "Raoul Bricard", "chavet": "Gabriel Chavet", "holub": "Jan Holub",
    "kraus": "Vojtěch Kraus", "krumpholc": "Josef Krumpholc", "coutinho": "Antonio Caetano Coutinho", "guillaume": "Jean Guillaume", "huet": "Horace Huet", "saint-martin": "Albert Saint-Martin",
    "evstifejev": "Nikolaj Evstifejev", "mann": "William W. Mann", "de-saussure": "René de Saussure", "millidge": "Edward Alfred Millidge", "allum": "Jean Allum",
}
_NAME_EDE = {
    "zamenhof": "Ludoviko Lazaro Zamenhof", "rhodes": "Joseph Rhodes", "pollen": "John Pollen", "mudie": "Harold Bolingbroke Mudie", "wackrill": "Alfred Edward Wackrill", "motteau": "Achille Motteau",
    "moscheles": "Felix Stone Moscheles", "schafer": "Louisa Frederica Adela Schafer", "villareal": "Frederiko Villareal", "schroder": "Johann Schröder", "fried": "Alfred Hermann Fried", "meyer": "Samuel Meyer",
    "berthelot": "Paul Berthelot", "mybs": "Eduard Mybs", "wallon": "Karl Wallon", "codorniu": "Ricardo Codorniu", "bicknell": "Clarence Bicknell", "miletz": "József Miletz", "midthus": "Haldor Midthus",
    "hodler": "Hector Hodler", "sentis": "Henri Sentis", "nalli": "Vitangelo Nalli", "runeberg": "Hjalmar Johannes Runeberg", "twombley": "John Fogg Twombly", "lloyd": "Richard John Lloyd",
    "evrot": "Joseph Evrot", "sabadell": "Alfons Sabadell", "dambrauskas": "Aleksandro Dambrauskas", "asada": "Eiĵi Asada", "atanasov": "Georgi Atanasov", "devjatnin": "Vasilij Nikolajeviĉ Devjatnin",
}
_NAME_PROFILE = {   # the fullest form its own profile prints; «brzostowski» and the patronymics on an Esperanto Wikipedia or Enciklopedio name
    "ellis": "John Ellis", "o-connor": "John Charles O'Connor", "hoveler": "Herbert Frederich Höveler", "chettiar": "T. Adinarayana Chettiar", "coox": "J. Coox", "cape": "Augusto Capé-Montrosier",
    "brzostowski": "Aleksandro Boleslavo Brzostowski", "blumenthal": "Leopold Blumental (Leo Belmont)", "avilov": "Fjodor Dmitriĉ Avilov", "ostrovskij": "Ilja Davidoviĉ Ostrovskij",
    "davidov": "Jonko Davidov", "gernet": "Vladimir Aleksandroviĉ Gernet", "dragoumis": "Emmanuel Dragoumis", "krikortz": "S. E. Krikortz", "skeel-giorling": "Frederik Skeel-Giörling", "lauren": "Augustinus Theodor Laurén",
    "de-wahl": "Edgar de Wahl", "zinoviev": "A. A. Zinoviev", "lojko": "Ivan Markoviĉ Lojko", "dor": "Henri Dor", "lallemant": "Félix Lallemant", "saquet": "Saquet", "postnikov": "Fjodor Aleksejeviĉ Postnikov",
    "emeric": "J. Emeric", "gustafsson": "F. W. Gustafsson", "benoit": "René Benoît", "guilbeau": "Edgard Guilbeau", "blanc": "G. Blanc", "gauntlett": "Edward Gauntlett", "mac-kenzie": "D. R. Mackenzie",
    "morin": "Anselmo Morin", "abesgus": "M. M. Abesgus", "cederblad": "Hilda Cederblad",
}
FULL_NAME = {k: (v, s) for t, s in ((_NAME_EO, "Esperanto Wikipedia"), (_NAME_EDE, "Enciklopedio de Esperanto"), (_NAME_PROFILE, "profile")) for k, v in t.items()}
FULL_NAME["radvan-ripinski"] = ("Evgenij Viktorovič Radvan-Rypinskij", "ÖNB, by the editor")
FULL_NAME["krikortz"] = ("Sven Erik Krikortz", "Esperanto Wikipedia")
FULL_NAME["cederblad"] = ("Hilda Karolina Fredrika Thisell, naskita Cederblad", "Esperanto Wikipedia")
FULL_NAME["atanasov"] = ("Georgi Atanasov", "Esperanto Wikipedia")
# the main forms ruled, v0.4.4 (the editor 2026-11-06: the Enciklopedio's headword is yielded to, and people's other names shown prominently): the headword's form leads, the other beside it
FULL_NAME.update({"de-wahl": ("Edgar von Wahl (de Wahl)", "Enciklopedio de Esperanto"), "blumenthal": ("Leo Belmont (Leopold Blumental)", "Enciklopedio de Esperanto"),
                  "kofman": ("Abram Kofman", "Enciklopedio de Esperanto"), "sebert": ("Hippolyte Sebert", "Enciklopedio de Esperanto"),   # 2026-11-07, Ezri: the print has «Kofman» and «Sebert»; «Koffman» and «Sébert» are the 2005 retyping's (failure map R108)
                  "cejka": ("Teodor Ĉejka (Theodor Čejka)", "Enciklopedio de Esperanto")})
# fuller by the ÖNB's author forms (bingo-card/ONB-NAMES-2026-11-06.tsv), each person checked by his records' titles; patronymics in č, as the ÖNB writes them
FULL_NAME.update({k: (v, "ÖNB") for k, v in {
    "benoit": "Jean René Benoît", "asnes": "Aleksandr Isaakovič Asnes", "avilov": "Fjodor Dmitrievič Avilov", "lojko": "Ivan Markovič Lojko", "postnikov": "Fjodor Alekseevič Postnikov", "zinoviev": "Aleksej Zinovjev",
    "coox": "Jean Coox", "saquet": "Donatien Saquet", "gauntlett": "George Edward Luckman Gauntlett", "bulthuis": "Hindrik Jan Bulthuis", "mann": "William Walter Mann",
    "cape": "Auguste Capé", "evrot": "Marie-Joseph Evrot", "codorniu": "Ricardo Codorníu y Stárico", "marich": "Ágoston H. de Marich", "geoghegan": "Richard H. Geoghegan", "oreskov": "Georgi P. Oreškov",
}.items()})
FULL_NAME.update({"kotzin": ("Boris Isidorovič Kotzin", "profile"), "ostrovskij": ("Ilja Davidovič Ostrovskij", "profile"), "gernet": ("Vladimir Aleksandrovič Gernet", "profile"), "devjatnin": ("Vasilij Nikolajevič Devjatnin", "Enciklopedio de Esperanto")})

# «†≥», A TERMINUS POST QUEM FOR THE DEATH, where none is held (the editor 2026-11-06: Radvan-Rypinskij was writing in Ondo de Esperanto
# in 1912; a terminus post quem is needed for every death not known): his latest dated act of his own, the
# spellings' profiles too; a roll counts, weakly; a mention in a rival organ does not, nor being struck for silence. Not a † in the totals
DEATH_TPQ = {
    "allum": ("1910", "in the Tutmonda Jarlibro's «Nomaro de ĉiuj anoj la 1ᵃ de Januaro 1910», a member of the LK, with a new address, «ALLUM, r. Dutertre, Boulogne-sur-Mer» (tutmonda-jarlibro-esperantista-1910-anno-0005, PDF 14, l. 590); struck for silence 1911"),   # was 1905 (the Boulogne comedy) to 2026-11-08, the rolls passed over (failure map R119; the editor) "atanasov": ("1933", "EdE 1933, «loĝas en Sofia»"),
    "avilov": ("1940", "taught in the postgraduate school of the Georgian Academy of Sciences, 1930s–1940s: Этюды и исследования, p. 212 (the editor, 2026-11-06)"), "benoit": ("1914", "did not stand again for the LK, 1914"),
    "boulet": ("1920", "LK roll of 1 Jan 1920 (OGE 7); EdE 1933 gives no death"),
    "busuttil": ("1929", "on the LK at least to 1929 (Vikipedio)"), "cederblad": ("1907", "Hilda Cederblad's course at Mariannelund, 1907"),
    "chettiar": ("1937", "The Christukula Ashram (Tirupattur, 1940), p. 243: «M. Rv Ry. Adinarayana Chettiar of Salem» lectured at the village-work training of 18 May–15 June 1937; p. 205, «Mr, T. Adinarayana Chettiar, Bar at-law, Salem» at the conference of 31 Dec. 1936–8 Jan. 1937 (https://archive.org/details/in.ernet.dli.2015.68754/, sources/web-2026-11-08-dli-68754/; Ezri 2026-11-08; the editor first gave «†≥ 1936» from it); before it 1934, his address at the All India Swadeshi Exhibition (The Covai Mail, 14 Aug 2025); the man ruled ours by the editor; was 1906, Tra la Mondo"), "coox": ("1909", "the Belgian philatelists' delegate, June 1909"),
    "costa-e-almeida": ("1920", "LK roll of 1 Jan 1920 (OGE 7); a candidate in 1914"),   # «dervaux» 1920 off: Lambert Delvaux of Charleroi's (the editor, 2026-11-09); ROW_SET holds the row
    "ebner": ("1914", "did not stand again for the LK, 1914; EdE 1933 gives no death"), "emeric": ("1908", "LK roll of 1 Jan 1908 with a new address (OGE 1); struck for silence 1911"),
    "evstifejev": ("1920", "elected to the Academy, May 1920 (OGE 7)"), "gauntlett": ("1913", "his resignation from the LK, for overwork (OGE 6)"),
    "guilbeau": ("1909", "named in Lingvo Internacia 1909-4"), "guillaume": ("1920", "at the Brussels congress for de Saussure, 1920"),
    "jamin": ("1914", "signed his history of Belgian Esperanto, La Belga Sonorilo, May 1914"), "krikortz": ("1930", "the ruled 🧡, the Swedish Occidental federation"),
    "lallemant": ("1920", "asked to resign from the LK for his health, 1920 (OGE 7)"), "mac-kenzie": ("1905", "Rev. D. R. Mackenzie of Kanazawa on the Boulogne roll; the delegate at Cupar in 1914 another man, by every sign"),
    "oreskov": ("1933", "EdE 1933, «loĝas en Burgas»"), "radvan-ripinski": ("1914", "selling his library, La Ondo de Esperanto, May 1914, at Lodejnoje Pole (radvan-ripinskij.md); his last piece there 1912"),
    "renard": ("1914", "a candidate for the LK, 1914 (OGE 6)"), "saquet": ("1910", "elected to the French society's committee, 1910"),
    "twombley": ("1911", "gave Lowell roses for the Boston society, Apr 1911; EdE 1933 gives no death"), "vargas": ("1920", "LK roll of 1 Jan 1920 (OGE 7); a candidate in 1914"),
    "zinoviev": ("1913", "his resignation from the LK, Dec 1913 (OGE 6)"), "davidov": ("1909", "secretary of the Silistra group, 1909"),
}

# DEATHS FROM THE LIVE PAGES (the editor 2026-11-06):
# our saved wikitext has an empty {{Informkesto homo}}, the dates coming from Wikidata when the page loads, so everyone with a †≥ was
# looked up live (sources/web-2026-11-06-eo-wikipedia/). The page's person checked each time against the card's by birth or office
DEATH_KNOWN = {
    "busuttil": ("1928", "31 Aug 1928, Esperanto Wikipedia's infobox and category, the same page's «ĝis minimume 1929» notwithstanding; confirmed by a University of Malta document, https://www.um.edu.mt/library/oar/handle/123456789/49495 (the editor)"),
    "atanasov": ("1960", "Esperanto Wikipedia's text and the ÖNB; its infobox's 30 Nov 1959 is a year-only Wikidata date, +1960 (ONB-DIFFERENCES-VERDICTS-2026-11-06)"), "boulet": ("1971", "28 June 1971, Vaucresson, Esperanto Wikipedia"),
    "cederblad": ("1939", "22 Jan 1939, Stockholm, Esperanto Wikipedia, s.v. Hilda Thisell, née Cederblad"), "krikortz": ("1931", "11 Jan 1931, Stockholm, Esperanto Wikipedia; the ÖNB's «1868-1931»"),
    "twombley": ("1959", "June 1959, Esperanto Wikipedia"),
    # the ÖNB's catalogue (tools/onb-card-names.py, bingo-card/ONB-NAMES-2026-11-06.tsv; the editor), the person checked by the records' titles
    "vargas": ("1951", "the ÖNB, «Vargas, Ambrosio, 1864-1951», author of the Mexican Esperanto lectures of 1904-1908"),
    "gauntlett": ("1956", "the ÖNB, «Gauntlett, Edward, 1868-1956» and «Gauntlett, George Edward Luckman, 1868-», of Okayama"),
    "benoit": ("1922", "the ÖNB, «Benoît, Jean René, 1844-1922»"),
    "guilbeau": ("1930", "the ÖNB, «Guilbeau, Edgar, 1850-1930», author of «L'Espéranto jugé par un aveugle»"),
}

def _ruled(table, stem, country):
    return table.get((stem, re.sub(r"\s*\(.*\)$", "", country))) or table.get(stem)

def volapuk_seq(stem, country, seq, ev):
    """v0.3.5 on one sequence: «🟪 †» to «‡»; the initial 🟩 ruled or found; 🟪 and 🟠 put in by their year"""
    year = lambda t: int(re.search(r"(\d{4})", t).group(1)) if re.search(r"(\d{4})", t) else None
    if stem in NAMESAKE:
        seq, ev = NAMESAKE[stem][0], f"RULED 2026-11-06: {NAMESAKE[stem][1]}"
    toks = [t for t in seq_text(seq).split(" → ") if t]
    dead = [t for t in toks if DEATH_TOK.match(t)]; toks = [t for t in toks if not DEATH_TOK.match(t)]
    def put(tok, before):   # before the first dated mark later than it, and before an equal year's marks in «before»
        y = year(tok)
        at = next((i for i, t in enumerate(toks) if year(t) is not None and (year(t) > y or (year(t) == y and t[0] in before))), len(toks))
        toks.insert(at, tok)
    j = _ruled(JOIN_RULED, stem, country)
    if j:
        toks[:] = [t for i, t in enumerate(toks) if not t.startswith("🟩") or i > 0]
        put(f"🟩 {j[0]}", "🟩💛💚🟨Ⓚ🟦")
        ev = f"🟩: RULED 2026-11-05: {j[1]} [BINGO-EVIDENCE-2026-11-05]" + (" ‖ " + ev if ev else "")
    elif not any(t.startswith("🟩") for t in toks):
        found = join_of(lines_of(stem, ""))
        if found:
            put(f"🟩 {found[0]}", "🟩💛💚🟨Ⓚ🟦")
            ev = f"🟩: {found[2]}" + (" ‖ " + ev if ev else "")
    x = OWN_ORANGE.get(stem)
    if x and x[0] in toks:
        toks.remove(x[0])
        if x[1]: put(x[1], "🟩💛💚🟨Ⓚ🟦")
        ev = f"🟧: RULED 2026-11-06: {x[2]} [BINGO-EVIDENCE-2026-11-05]" + (" ‖ " + ev if ev else "")
    o = _ruled(OWN_AUXLANG, stem, country)
    if o:
        put(f"🟠 {o[0]}", "🟩💛💚🟨Ⓚ🟦")
        ev = f"🟠: RULED 2026-11-05: {o[1]} [BINGO-EVIDENCE-2026-11-05]" + (" ‖ " + ev if ev else "")
    for tok, why in BACK.get(stem, []):
        put(tok, "")
        ev = f"{tok[0]}: RULED 2026-11-06: around his own auxlang: {why} [the profile]" + (" ‖ " + ev if ev else "")
    v = _ruled(VOLAPUK, stem, country)
    if v:
        if v[0].startswith("≤"): toks.insert(0, f"🟪 {v[0]}")   # a terminus ante quem: he had come to it first, whatever the date
        else: put(f"🟪 {v[0]}", "🟠🟩💛💚🟨Ⓚ🟦")
        ev = f"🟪: RULED 2026-11-05: {v[1]} [BINGO-EVIDENCE-2026-11-05]" + (" ‖ " + ev if ev else "")
    if MARK_REPLACES.get(stem) in toks: toks.remove(MARK_REPLACES[stem])
    for tok, why in MARKS_REVIEWED.get(stem, []):
        put(tok, MARK_AHEAD.get(stem, ""))
        ev = f"{tok[0]}: RULED 2026-11-06: {why} [REVIEW-2026-11-06-marks]" + (" ‖ " + ev if ev else "")
    if stem in DEATH_CORRECT:
        dead = [DEATH_CORRECT[stem][0]]
        ev = f"†: RULED 2026-11-06: {DEATH_CORRECT[stem][1]} [REVIEW-2026-11-06-marks]" + (" ‖ " + ev if ev else "")
    if stem in MARK_NOTE: ev = f"{MARK_NOTE[stem]} [REVIEW-2026-11-06-marks]" + (" ‖ " + ev if ev else "")
    if stem in DEATH_KNOWN and not dead:
        dead = [f"† {DEATH_KNOWN[stem][0]}"]
        ev = f"†: 2026-11-06: {DEATH_KNOWN[stem][1]}" + (" ‖ " + ev if ev else "")
    if stem in DEATH_TPQ and not dead:
        dead = [f"†≥ {DEATH_TPQ[stem][0]}"]
        ev = f"†≥: 2026-11-06: {DEATH_TPQ[stem][1]}" + (" ‖ " + ev if ev else "")
    return " → ".join(toks + dead), ev

GAP_DEATHS = {"vargas", "chettiar", "jamin", "coox", "dervaux", "ebner", "costa-e-almeida", "busuttil", "avilov", "oreskov", "atanasov", "krikortz", "renard"}   # v0.3's list of pressing gaps
def volapuk_step(old, new):
    """--volapuk-step OLD NEW (2026-11-05): the card of version OLD with volapuk_seq() on every sequence and the totals and
    legend following, and nothing else, as version NEW. Writes bingo-card-v<NEW>.csv, -supplement.csv, -lk1905.csv and .md; refuses if any exists."""
    out_dir = os.environ.get("BINGO_OUT", os.path.join(GEN, "bingo-card"))
    P = lambda v, suf: os.path.join(out_dir, f"bingo-card-v{v}{suf}")
    sufs = [".csv", "-supplement.csv", "-lk1905.csv", ".md"]
    there = [P(new, s) for s in sufs if os.path.exists(P(new, s))]
    if there: sys.exit("refusing, nothing written: exists: " + ", ".join(os.path.basename(p) for p in there))
    n, MAP, LINES = 0, {}, {}
    for s in sufs[:3]:
        R = list(csv.DictReader(open(P(old, s), encoding="utf-8")))
        with open(P(new, s), "w", newline="", encoding="utf-8") as fh:
            names = list(R[0].keys()); at = names.index("stem") + 1; names[at:at] = ["full_name", "name_source"]
            w = csv.DictWriter(fh, fieldnames=names); w.writeheader()
            for r in R:
                r["full_name"], r["name_source"] = (_ruled(FULL_NAME, r["stem"], r["country"]) or ("", "")) if r["stem"] else ("", "")
                if r["stem"] and not r["full_name"]: sys.exit(f"no full name: {r['stem']}, {r['country']}")
                orig = r["tags_in_sequence"]
                ev = r["evidence"].replace("🟪: ", "‡: ") if "🟪 †" in orig else r["evidence"]
                t, r["evidence"] = volapuk_seq(r["stem"], r["country"], orig, ev)
                MAP[(r["stem"], orig)] = t; n += t != orig; r["tags_in_sequence"] = t
                if r["stem"] in NAMESAKE and "hand_pass" in r: r["hand_pass"] = NAMESAKE[r["stem"]][2]
                # v0.4.0 (the editor, through Ezri, 2026-11-06: the card to read the new profiles): every row's count of lines as they now stand
                if os.path.exists(os.path.join(PROFILES, r["stem"] + ".md")) or r["stem"] in CARD_BUCKET:
                    r["n_fact_lines"] = str(len(lines_of(r["stem"], r.get("caption") or "")))
                    LINES[(r["stem"], orig)] = r["n_fact_lines"]
                w.writerow(r)
    L, col, table, ccol = [], None, None, None
    delta = collections.defaultdict(collections.Counter)
    # the editor 19:1x; 19:3x: ruled by the editor,
    # «other» counts only memberships after 1907, since it measures the impact of the Ido schism. So «other», and «any camp»,
    # which holds it, take 🟠 only from 1908. table → country → [other, any camp] gained; table → «any camp» gained, and 🟠 from 1908
    cdelta = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0])); anyd = collections.Counter(); late = collections.Counter()   # the third, ‡ gained; the fourth, Ido
    has = lambda q: {w for t in q.split(" → ") for w in t.split(" ") if w and not re.match(r"^(\d{4}|≤)$", w)}
    for line in open(P(old, ".md"), encoding="utf-8"):
        if line.startswith("|"):
            cells = line.rstrip("\n").split(" | ")
            hd = [c.strip().strip("|").strip() for c in cells]
            if "tags in sequence" in hd:
                col = hd.index("tags in sequence")
                ccol = hd.index("country") if "country" in hd else None
                table = {"| plate": "album", "| stem": "supplement"}.get(cells[0].strip(), "supplement")
                if "as the roll prints him" in hd: table = "table3"
                cells.insert(hd.index("stem") + 1, "full name"); line = " | ".join(cells) + "\n"
            elif line.startswith("|-") and col is not None:
                line = "|---" + line
            elif col is not None and len(cells) > col and cells[col].strip() and not cells[col].startswith("-"):
                st = next((m.group(1) for c in cells for m in [re.fullmatch(r"`([^`]+)`", c.strip().strip("|").strip())] if m), "")
                tail = " |" if cells[col].rstrip().endswith(" |") else ""
                orig = cells[col].rstrip()[:-2].strip() if tail else cells[col].strip()
                nw = MAP.get((st, orig))
                own = max((int(y) for y in re.findall(r"🟠 (?:≤ )?(\d{4})", nw or "")), default=0)
                if own >= 1908: late[table] += 1
                if own >= 1908 and ccol is not None:
                    cty = re.sub(r"\s*\(.*\)$", "", cells[ccol].strip().strip("|").strip()); g0 = has(orig)
                    cdelta[table][cty][0] += not (g0 & {"🟧", "🧡"}); gained = not (g0 & {"🟦", "💙", "🟧", "🧡"})
                    cdelta[table][cty][1] += gained; anyd[table] += gained
                if nw is None: sys.exit(f"a row of the .md not in the CSVs: {st}: {orig}")
                cells[col] = nw + tail
                was = {"‡" if g == "🟪" else g for g in has(orig)}   # the old 🟪 was the death
                if (st, orig) in LINES: cells[col - 1] = LINES[(st, orig)]
                if st in NAMESAKE:
                    if "‡" in has(nw) and "‡" not in was and ccol is not None:
                        cdelta[table][re.sub(r"\s*\(.*\)$", "", cells[ccol].strip().strip("|").strip())][2] += 1
                    if len(cells) > col + 1: cells[col + 1] = NAMESAKE[st][2] + " |"
                if st in ROW_CAMP and ccol is not None:
                    cd = cdelta[table][re.sub(r"\s*\(.*\)$", "", cells[ccol].strip().strip("|").strip())]
                    cd[3] += ROW_CAMP[st][0]; cd[0] += ROW_CAMP[st][1]; cd[1] += ROW_CAMP[st][2]; anyd[table] += ROW_CAMP[st][2]
                for g_ in was | has(nw):
                    delta[table][g_] += (g_ in has(nw)) - (g_ in was)
                at = next(i for i, c in enumerate(cells) if re.fullmatch(r"`[^`]+`", c.strip().strip("|").strip()))
                cells.insert(at + 1, _ruled(FULL_NAME, st, cells[ccol].strip().strip("|").strip())[0])
                line = " | ".join(cells) + "\n"
            line = line.replace("| struck 🔴/⭕ | 🟪 |", "| struck 🔴/⭕ | ‡ |").replace("| other 🟧+🧡 |", "| other 🟧+🧡+🟠 from 1908 |")
        else:
            col = None if line.strip() else col
        if line.startswith("- `atanasov` — no fact lines"):
            continue
        if any(line.startswith(f"- `{s}` — thin profile") for s in NAMESAKE): continue
        if any(line.startswith(f"- `{s}` — death year open") for s in DEATH_KNOWN): continue
        if line.startswith("## P-GAP v0.3 — cells a human must rule (2)"):
            line = line.replace("close (14;", f"close ({13 - sum(1 for g in GAP_DEATHS if g in DEATH_KNOWN)};").replace("must rule (2)", "must rule (1)")
        if line.startswith("### Totals") and "hand-pass cells: 2" in line: line = line.replace("hand-pass cells: 2", "hand-pass cells: 1")
        if line.startswith("# The Schuck-album bingo card — v" + old):
            line = line.replace("— v" + old, "— v" + new, 1).rstrip("\n") + (f" · v{new}, 2026-11-05, from v{old}: 🟪 now the date of "
                   "adherence to Volapük (a report's date only a terminus ante quem, «≤»); «‡» for died before end-1908, replacing «🟪 †»; "
                   "🟠 for the authors of their own auxlangs, in place of a 🟧 for the same language; the initial 🟩 for everyone, dated from the whole Adresaro and the "
                   "Enciklopedio de Esperanto (bingo-card/BINGO-EVIDENCE-2026-11-05.md); 2026-11-06: the namesakes read from their own profiles, "
                   "F. A. Postnikov, I. M. Lojko, G. Atanasov, A. Morin; de Wahl ⬜ 1897, Auli 🟠 1906; J. F. Twombly's row re-read, ⭘ 1910; R. J. Lloyd ‡ 1906, Blanc of Rome ‡ ≤ 1906; «†≥», a terminus post quem where no death is held; six deaths from the live Esperanto Wikipedia pages, two from the ÖNB's catalogue; Jonko Davidov's † taken off, it was Georgo's; a column of canonical full names; read against the profiles as they stood after the harvest of 2026-11-06, 09:27 (the line counts all refreshed); v0.4.2, the review of the marks (REVIEW-2026-11-06-marks.md), R. Benoît † 1922, Asnes † 1922, Krikortz 🟪 ≤ 1888; v0.4.3, Dambrauskas read from jakstas.md; v0.4.4, Atanasov † 1960, Meazzini † 1939, Bricard † 1943 (a 30 November on Esperanto Wikipedia being a year-only date), Dambrauskas read from dambrauskas.md, five names by the Enciklopedio's headwords with the other form beside them\n")
        if line.startswith("**Grammar of the card:**"):
            line = (line.replace("🟩 stayed", "🟩 joined Esperanto, dated; stayed unless a later square says otherwise")
                    .replace("🟪 died ≤ 1908", "🟪 Volapük, dated, «≤» where only reported")
                    .replace("⭘ resigned · 🟢 returned", "⭘ resigned · 🟢 returned · 🟠 invented an auxlang of their own (a 🟩 or 🟦 after it: stayed; none: left)")
                    .replace("◐ double membership · †", "◐ double membership · † · †≥ death not held, alive at that date · ‡ died ≤ 1908"))
        L.append(line)
    adds = {"the album's": ["album"], "the supplement's": ["supplement"], "both tables together": ["album", "supplement"],
            "table 3's": ["table3"], "all three tables": ["album", "supplement", "table3"]}
    head, out = None, []
    for line in L:
        if line.startswith("### Totals"): head = next((k for k in adds if k in line), None)
        c = re.match(r"^\| (\*\*total\*\*|[^|*]+?) \| (\**\d+\**) \| (\**\d+\**) \| \**(\d+)\** \| \**(\d+)\** \| (\**\d+\**) \| (\**\d+\**) \|$", line.rstrip("\n"))
        if c and head:
            gain = [sum(cdelta[t][k][j] for t in adds[head] for k in ([c.group(1)] if "total" not in c.group(1) else list(cdelta[t]))) for j in (0, 1, 2, 3)]
            b = "**" if "total" in c.group(1) else ""
            line = (f"| {c.group(1)} | {c.group(2)} | {b}{int(c.group(3).strip('*')) + gain[3]}{b} | {b}{int(c.group(4)) + gain[0]}{b} | {b}{int(c.group(5)) + gain[1]}{b} | {c.group(6)} | {b}{int(c.group(7).strip('*')) + gain[2]}{b} |\n")
        a = re.match(r"^\| 🟦💙🟧🧡 \| \*\*any camp — Ido or other auxlang, adherent or sympathiser\*\* \| \*\*(\d+)\*\* \|$", line.rstrip("\n"))
        if a and head:
            line = f"| 🟦💙🟧🧡🟠 | **any camp — Ido or other auxlang, adherent, sympathiser or author (🟠 from 1908)** | **{int(a.group(1)) + sum(anyd[t] for t in adds[head])}** |\n"
        m = re.match(r"^\| (\S+) \| ([^|]+) \| (\d+) \|$", line.rstrip("\n"))
        if m and head and m.group(1) in ORDER + ["🟪"]:
            d = lambda g: sum(delta[t][g] for t in adds[head])
            if m.group(1) == "🟪":   # the old row, the deaths: now ‡, after the two new marks
                out += [f"| 🟪 | {LEGEND['🟪']} | {d('🟪')} |\n", f"| 🟠 | invented an auxlang of their own, before 1908 | {d('🟠') - sum(late[t] for t in adds[head])} |\n", f"| 🟠 | invented an auxlang of their own, from 1908 | {sum(late[t] for t in adds[head])} |\n", f"| ‡ | {LEGEND['‡']} | {int(m.group(3)) + d('‡')} |\n"]
                continue
            line = f"| {m.group(1)} | {LEGEND.get(m.group(1), m.group(2)) if m.group(1) in ('🟩', '†') else m.group(2)} | {int(m.group(3)) + d(m.group(1))} |\n"
        out.append(line)
    open(P(new, ".md"), "w", encoding="utf-8").write("".join(out))
    print(f"v{old} → v{new}: {n} sequences rewritten in the three CSVs; → {', '.join(os.path.basename(P(new, s)) for s in sufs)}")
    return 0

# v0.4.7 (2026-11-07; the editor 13:3x; Ezri's
# bingo-card/LK-JOINING-2026-11-07.tsv, read from the rolls by eye). Each person's Ⓚ from her table; Sentis's Ⓚ and Ⓐ and Hodler's Ⓚ and ⭘ taken off.
# THE NAMES, as agreed with Ezri (the editor 13:5x): the column stops being its own source:
# the Enciklopedio's heading, initials standing; a register row overrides it; else the Esperanto Wikipedia's title; else what the column had, as a source prints it.
# A diacritic the OCR may have dropped from a heading is kept till the print is read (Emile, Theophile, Lopez, Sepulveda, Codorniu)
_E = "Enciklopedio de Esperanto"
LK_NAMES = {
    "o-connor": ("James Charles O'Connor", _E), "hoveler": ("Herbert F. Höveler", _E), "geoghegan": ("Richard H. Geoghegan", _E), "beauchemin": ("A. P. Beauchemin", _E),
    "kuhnl": ("Eduard Kühnl", _E), "simon": ("Otto Simon", _E), "jamin": ("Joseph Jamin", _E), "cape": ("Auguste Capé", _E), "matton": ("Pierre Ernest Matton", _E),
    "boirac": ("Émile Boirac", _E), "meray": ("Charles Méray", _E), "michaux": ("Alfred Michaux", _E), "deligny": ("Ernest Deligny", _E), "moch": ("Gaston Moch", _E),
    "javal": ("Emile Javal", _E), "bourlet": ("Carlo Bourlet", _E), "lambert": ("Charles Lambert", _E), "zabilon-d-her": ("Jeanne Zabilon D'her Ranfaing", _E),
    ("lemaire", "France"): ("René Lemaire", _E), "cart": ("Théophile Cart", _E), "verax": ("Charles Verax", _E), "fruictier": ("Paul Fruictier", _E), "einstein": ("Leopold Einstein", _E),
    "trompeter": ("W. H. Trompeter", _E), "borel": ("Jean Borel", _E), "meier": ("Ludwig Emil Meier", _E), "christaller": ("Paul Gottfried Christaller", _E), "schmidt": ("Adolf Schmidt", _E),
    "ebner": ("Adolf Ebner", _E), "hanauer": ("Julius Hanauer", _E), "barthel": ("Karl Barthel", _E), "inglada": ("Vicente Inglada Ors", _E), "villanueva": ("Antonio López Villanueva", _E),
    "codorniu": ("Ricardo Codorníu", _E), "sepulveda": ("Luis Enrique Sepúlveda Cuadra", _E), "junck": ("Rosa Junck, naskita Bílek", _E), "gallois": ("Albert Gallois", _E),
    "marignoni": ("Daniele Marignoni", _E), "bagnulo": ("Raffaele Bagnulo", _E), "sussmuth": ("John Joseph Sussmuth", _E), "lengyel": ("Pál Lengyel", _E), "marich": ("Ágoston Marich", _E),
    "grabowski": ("Antoni Grabowski", _E), "wasniewski": ("Jozefo Wasniewski", _E), "brzostowski": ("Aleksandro Brzostowski", _E), "kofman": ("A. Kofman", _E),
    "dambrauskas": ("Aleksandro Dambrauskas (Dombrovski)", _E), "ostrovskij": ("Ilja Ostrovskij", _E), "oreskov": ("Georgi Oreŝkov", _E), "gernet": ("Vladimir Gernet", _E),
    "ahlberg": ("Per Ahlberg", _E), "nylen": ("Paul Axel Nylén", _E), "langlet": ("Valdemar B. Langlet", _E), "thorsteinsson": ("Thorsteinn Thorsteinsson", "Esperanto Wikipedia"),
    "skeel-giorling": ("Frederik Skeel-Giörling", _E), "uitterdijk": ("Dreves Uitterdijk", _E), "bulthuis": ("Hindrik Jan Bulthuis", _E), "hageler": ("Alf Hageler", _E), "privat": ("Edmond Privat", _E),
    "schneeberger": ("Friedrich Schneeberger", _E), "kotzin": ("Boris Kotzin", _E), "boulet": ("Paul Boulet", _E), "bricard": ("Raoul Bricard", _E), "chavet": ("Gabriel Chavet", _E),
    "evrot": ("Joseph Evrot", _E), "kraus": ("Vojtěch Kraus", _E), "krumpholc": ("Josef Krumpholc", _E), "postnikov": ("Feodor A. Postnikov", _E), "coutinho": ("Antonio Caetano Coutinho", _E),
    "gauntlett": ("George Edward Luckman Gauntlett", _E), "huet": ("Horace Huet", _E), "allum": ("J. Allum", _E), "abesgus": ("M. Abesgus", _E),
    "cederblad": ("Hilda Thisell, naskita Cederblad", _E), "evstifejev": ("Nikolai Evstifejev", _E), "de-saussure": ("René de Saussure", _E), "millidge": ("Edward Alfred Millidge", _E), "talmey": ("Max Talmey", _E),
    "de-beaufront": ("Louis de Beaufront", _E), "atanasov": ("Georgi Atanasov", _E), "dor": ("Henri Dor", _E), "seynaeve": ("Maurice Seynaeve", "Esperanto Wikipedia"), "ellis": ("John Ellis", _E), "lloyd": ("Richard John Lloyd", _E),
    "bein": ("Kazimierz Bein (Kabe)", "the register"), "guillaume": ("Ch. Ed. Guillaume", "the register"),
    # the Enciklopedio's «Karl» set aside (the editor 2026-11-08 02:3x: «Karl» a clear error for Karp, short for Polykarp, as two
    # contemporary mentions in Germana Esperantisto show): Germana Esperantisto 1921 No 8/9 p. 191 and 1932 No. 8-9 p. 138
    "wallon": ("Karp Wallon", "Germana Esperantisto"),
}
# Ezri's table, and hers of 2026-11-07 through the editor: the marks that fall with it, and Guillaume, who is the Nobel physicist; his 🟩 stays, by the editor, as a bound
LK_OFF = {"sentis": {"Ⓐ 1909"}, "hodler": {"⭘"}, "guillaume": {"🟩 1903", "†≥ 1920"}, "mac-kenzie": {"🟩", "· 1914"}}
LK_EV_OFF = {"sentis": ("Ⓐ:",), "hodler": ("⭘:",), "guillaume": ("†≥:", "🟩:"), "mac-kenzie": ("🟩:", "·:")}
LK_ON = {"guillaume": ("† 1938", "†: Charles-Édouard Guillaume, 1861-1938, physics prize of 1920 (Jean Amouroux, Esperanto 1067 (2), Feb 1995, p. 29, sources/web-2026-11-07-uea-1995-guillaume/, PDF 11; de.wikipedia, 13 June 1938, Sèvres); †≥ 1920 was a S-ro Guillaume at Brussels")}
# v0.4.8 (the editor 2026-11-07 16:4x): a supporter who never learned the language, so a leaning, not an act
LK_FIRST = {"guillaume": ("💚 ≤ 1903", "💚: RULED 2026-11-07, the editor, a one-off: a supporter, who never joined: named as «Guillaume, (Svisujo) subdirektoro de internacia laborejo de pesiloj kaj mezuriloj» (Lingvo Internacia 1903-7, PDF 4); Amouroux, Esperanto 1067 (2), p. 29: his work kept him from learning Esperanto, and he stayed a firm supporter; 🟩 1903 was P. Guillaume of Chaumont"),
            "mac-kenzie": ("🟩 ≤ 1903", "🟩: Enciklopedio de Esperanto, our text's p. 668, «En la printempo de 1903 Mac Kenzie, skota pastro, Kanazawa» (Ezri, 2026-11-07); Saiko Gauntlett 2007, «At that time McKenzie was reading a text for students in Esperanto», summer 1903 (gauntlett-2007-edward-gauntlett, PDF 5, p. 303)")}
# Ⓐ by the Akademio's own lists, as Ⓚ by the Komitato's (Ezri, bingo-card/AKADEMIO-CHECK-2026-11-07.tsv, her nine; Michaux's off pending one more line of hers, Waringhien at no. 367)
AK_SET = {"millidge": ("Ⓐ 1923", "elected June 1923, ROLL 11; in none of the lists before it, a candidate in 1911 and 1912"), "michaux": (None, ""), "ostrovskij": (None, ""), "sebert": (None, ""), "bourlet": (None, ""), "chavet": (None, ""),
          "inglada": ("Ⓐ 1910", "elected 1 Aug 1910, oge-3 PDF 221; Enciklopedio PDF 403"), "christaller": ("Ⓐ 1911", "elected 1 Aug 1911, oge-4 PDF 104; Enciklopedio PDF 141"),
          "hoveler": ("Ⓐ 1911", "elected 1 Aug 1911, as Ĉefeĉ, oge-4 PDF 104; the Enciklopedio, PDF 375, says 1912")}
LK_COUNTRY_SET = {"guillaume": "France (Swiss)", "dor": "France (Swiss)"}   # «dervaux» «France (Belgian)» off 2026-11-09, Lambert Delvaux's, not the caption's Maurice of Boulogne; Swiss, living in France at the album's date: counted under France as before; Dor: «Dor Henri, sviso, d-ro, kuracisto», the editor's print, 2026-11-07

# a card row whose profile the sinter renamed (Ezri, 2026-11-07 21:5x): the Kanazawa missionary's lines are in mac-kenzie.md, MAC KENZIE
# the Enciklopedio's form; mac-kensie.md now holds only Arthur Mackenzie of Cupar. The older cards and Ezri's table keep the old key
STEM_NOW = {"mac-kensie": "mac-kenzie"}
# his «· 1914» (six mentions in Progreso) was other men's: Dr W. Mackenzie of the Archives de Psychologie (Progreso 7, 1914), «Sri. Mackenzie
# ed Pannell» of the USA (Progreso 8, 1915), a Mackenzie Street in North Sydney (Progreso 14); his own lines end in 1908 (Ezri, 2026-11-07 22:0x)

def lk_seq(stem, seq, ev, mark, why):
    year = lambda t: int(re.search(r"(\d{4})", t).group(1)) if re.search(r"(\d{4})", t) else None
    last = lambda t: t[0] in "†‡" or t.startswith("🟪 †")
    toks = [t for t in seq.split(" → ") if t and not t.startswith("Ⓚ") and t not in LK_OFF.get(stem, ())]
    parts = [p for p in ev.split(" ‖ ") if p and not p.startswith("Ⓚ:") and not p.startswith(LK_EV_OFF.get(stem, ("\0",)))]
    if stem in LK_ON: toks.append(LK_ON[stem][0]); parts.insert(0, LK_ON[stem][1])
    if stem in LK_FIRST: toks.insert(0, LK_FIRST[stem][0]); parts.insert(0, LK_FIRST[stem][1])
    if mark:
        y = year(mark)
        at = next((i for i, t in enumerate(toks) if last(t) or (year(t) is not None and (year(t) > y or (year(t) == y and t[0] not in "🟪🟠🟩💛💚🟨")))), len(toks))
        toks.insert(at, mark); parts.insert(0, f"Ⓚ: {why} [LK-JOINING-2026-11-07.tsv]")
    if stem in AK_SET:
        toks = [t for t in toks if not t.startswith("Ⓐ")]; parts = [p for p in parts if not p.startswith("Ⓐ:")]
        am, awhy = AK_SET[stem]
        if am:
            y = year(am)
            at = next((i for i, t in enumerate(toks) if last(t) or (year(t) is not None and (year(t) > y or (year(t) == y and t[0] not in "🟪🟠🟩💛💚🟨Ⓚ")))), len(toks))
            toks.insert(at, am); parts.insert(0, f"Ⓐ: {awhy} [AKADEMIO-CHECK-2026-11-07.tsv]")
    return " → ".join(toks), " ‖ ".join(parts)

def lk_step(old, new, tsv):
    """--lk-step OLD NEW TSV (2026-11-07): the card of version OLD with Ⓚ from Ezri's table, the names by LK_NAMES, the marks that fall with it, and the
    tag totals following; nothing else. Writes bingo-card-v<NEW>.csv, -supplement.csv, -lk1905.csv and .md; refuses if any exists."""
    out_dir = os.environ.get("BINGO_OUT", os.path.join(GEN, "bingo-card"))
    P = lambda v, suf: os.path.join(out_dir, f"bingo-card-v{v}{suf}")
    sufs = [".csv", "-supplement.csv", "-lk1905.csv", ".md"]
    there = [P(new, s) for s in sufs if os.path.exists(P(new, s))]
    if there: sys.exit("refusing, nothing written: exists: " + ", ".join(os.path.basename(p) for p in there))
    T = {}
    for l in open(tsv, encoding="utf-8"):
        if l.startswith("#") or l.startswith("stem\t"): continue
        x = l.rstrip("\n").split("\t") + [""] * 5
        T[STEM_NOW.get(x[0], x[0])] = (x[2].strip(), x[3].strip())
    n, MAP = 0, {}
    tag = lambda q: {w for t in q.split(" → ") for w in t.split(" ") if w and not re.match(r"^(\d{4}|≤|≥)$", w)}
    for s in sufs[:3]:
        R = list(csv.DictReader(open(P(old, s), encoding="utf-8")))
        with open(P(new, s), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R[0].keys())); w.writeheader()
            for r in R:
                if not r["stem"]: w.writerow(r); continue
                r["stem"] = STEM_NOW.get(r["stem"], r["stem"])
                if r["stem"] not in T: sys.exit(f"not in the table: {r['stem']}")
                orig, cty0, name0 = r["tags_in_sequence"], r["country"], r["full_name"]
                t, r["evidence"] = lk_seq(r["stem"], orig, r["evidence"], *T[r["stem"]])
                r["full_name"], r["name_source"] = _ruled(LK_NAMES, r["stem"], r["country"]) or (r["full_name"], r["name_source"])
                r["country"] = LK_COUNTRY_SET.get(r["stem"], r["country"])
                MAP[(r["stem"], orig)] = (t, r["full_name"], r["country"])
                n += t != orig; r["tags_in_sequence"] = t; w.writerow(r)
    L, col, table, ccol, delta = [], None, None, None, collections.defaultdict(collections.Counter)
    for line in open(P(old, ".md"), encoding="utf-8"):
        if line.startswith("|"):
            cells = line.rstrip("\n").split(" | ")
            hd = [c.strip().strip("|").strip() for c in cells]
            if "tags in sequence" in hd:
                col = hd.index("tags in sequence"); ccol = hd.index("country") if "country" in hd else None
                table = {"| plate": "album", "| stem": "supplement"}.get(cells[0].strip(), "supplement")
                if "as the roll prints him" in hd: table = "table3"
            elif col is not None and len(cells) > col and cells[col].strip() and not cells[col].startswith("-"):
                at = next((i for i, c in enumerate(cells) if re.fullmatch(r"`[^`]+`", c.strip().strip("|").strip())), None)
                st = cells[at].strip().strip("|").strip().strip("`") if at is not None else ""
                if st in STEM_NOW: cells[at] = cells[at].replace(st, STEM_NOW[st]); st = STEM_NOW[st]
                tail = " |" if cells[col].rstrip().endswith(" |") else ""
                orig = cells[col].rstrip()[:-2].strip() if tail else cells[col].strip()
                got = MAP.get((st, orig))
                if got is None and st: sys.exit(f"a row of the .md not in the CSVs: {st}: {orig}")
                if got:
                    cells[col] = got[0] + tail; cells[at + 1] = got[1]
                    if ccol is not None: cells[ccol] = got[2]
                    for g_ in tag(orig) | tag(got[0]):
                        delta[table][g_] += (g_ in tag(got[0])) - (g_ in tag(orig))
                line = " | ".join(cells) + "\n"
        else:
            col = None if line.strip() else col
        if line.startswith("# The Schuck-album bingo card — v" + old):
            line = line.replace("— v" + old, "— v" + new, 1).rstrip("\n") + (f" · v{new}, 2026-11-07, from v{old}: Ⓚ by the date of joining in our records, not the album's "
                   "mark (Ezri, bingo-card/LK-JOINING-2026-11-07.tsv); Sentis and Hodler not members; Ch. Ed. Guillaume the physicist; nine Ⓐ by the Akademio's own lists (bingo-card/AKADEMIO-CHECK-2026-11-07.tsv); the names by the Enciklopedio's heading, then the register, then the Esperanto Wikipedia\n")
        L.append(line)
    adds = {"the album's": ["album"], "the supplement's": ["supplement"], "both tables together": ["album", "supplement"],
            "table 3's": ["table3"], "all three tables": ["album", "supplement", "table3"]}
    head, out = None, []
    for line in L:
        if line.startswith("### Totals"): head = next((k for k in adds if k in line), None)
        m = re.match(r"^\| (\S+) \| ([^|]+) \| (\d+) \|$", line.rstrip("\n"))
        if m and head and m.group(1) in ORDER + ["Ⓚ", "Ⓐ"]:
            line = f"| {m.group(1)} | {m.group(2)} | {int(m.group(3)) + sum(delta[t][m.group(1)] for t in adds[head])} |\n"
        if m and m.group(1) == "💚":
            line = line.replace("before the 1894 vote", "before the 1894 vote; dated later, one person only: Guillaume, a supporter who never learned the language")
        if m and head == "table 3's" and m.group(1) == "🟦" and delta["table3"]["💚"]:   # the first 💚 of that table: no row to add to
            out.append(f"| 💚 | green heart — sympathy for the language as it was, before the 1894 vote; dated later, one person only: Guillaume, a supporter who never learned the language | {delta['table3']['💚']} |\n")
        if line.startswith("**Grammar of the card:**"):
            line = line.replace("💚 for the language as it was, before 1894", "💚 for the language as it was, before 1894; one later date, Guillaume, a supporter who never learned it")
        out.append(line)
    open(P(new, ".md"), "w", encoding="utf-8").write("".join(out))
    print(f"v{old} → v{new}: {n} sequences rewritten in the three CSVs; → {', '.join(os.path.basename(P(new, s)) for s in sufs)}")
    return 0

# --row-step (2026-11-08, Miles; the editor): the rows ruled since v0.4.9, one by one
ROW_JOIN = {"de-beaufront"}   # the 🟩 now JOIN_RULED's (1887 → 1888, the editor)
ROW_VOLAPUK = {"wallon"}      # a 🟪 new since v0.4.9, from VOLAPUK
# Dervaux: the album's caption is Maurice of Boulogne (Ezri, the editor 2026-11-08); the row held Lambert of Charleroi's name, country and marks
ROW_SET = {"dervaux": ("Maurice Dervaux", "profile", "France", "🟩 1903 → †≥ 1908",
                       "🟩: Adresaro 1903, serio 24, n-ro 8789, «Maurice Derveaux», Boulogne-sur-Mer (adresaro-1903-serio-24, ¶ 1090) ‖ †≥: his last dated act, the Esperanto festival of Amiens, 26 Apr 1908 (lesperantiste-1908-5, PDF 9, l. 597) ‖ the row was Lambert Dervaux's to v0.4.9 (Ⓚ 1913, †≥ 1920, «France (Belgian)», and a «· 1908» from a surname search): Maurice of the caption ruled the card's man (the editor, through Ezri, 2026-11-08); profiles/dervaux.md, Lambert «(Lambert)»")}


def row_seq(stem, name, seq, ev, births):
    """one row's sequence and evidence with the rulings made since v0.4.9; (seq, ev, what changed)"""
    toks = [t for t in seq.split(" → ") if t]
    parts = [p for p in ev.split(" ‖ ") if p]
    did = []
    if stem in ROW_JOIN:
        y, why = JOIN_RULED[stem]
        i = next((k for k, t in enumerate(toks) if t.startswith("🟩")), None)
        if i is not None and toks[i] != f"🟩 {y}":
            did.append(f"{toks[i]} → 🟩 {y}"); toks[i] = f"🟩 {y}"
            parts = [p for p in parts if not p.startswith("🟩: RULED")]; parts.insert(0, f"🟩: RULED 2026-11-08: {why}")
    if stem in ROW_VOLAPUK and not any(t.startswith("🟪") for t in toks):
        y, why = VOLAPUK[stem]
        toks.insert(0, f"🟪 {y}"); parts.insert(0, f"🟪: RULED 2026-11-08: {why}"); did.append(f"+🟪 {y}")
    if stem in DEATH_TPQ:
        i = next((k for k, t in enumerate(toks) if t.startswith("†≥")), None)
        if i is not None and toks[i] != f"†≥ {DEATH_TPQ[stem][0]}":
            did.append(f"{toks[i]} → †≥ {DEATH_TPQ[stem][0]}"); toks[i] = f"†≥ {DEATH_TPQ[stem][0]}"
            parts = [p for p in parts if not p.startswith("†≥:")]; parts.insert(0, f"†≥: RULED 2026-11-08: {DEATH_TPQ[stem][1]}")
    b = births.get((stem, name))
    if b and b[0] and not any(t.startswith("*") for t in toks):
        toks.insert(0, f"* {b[0]}"); parts.insert(0, f"*: {b[1]}: {b[2]}" + (f" ({b[3]})" if b[3] else "") + " [BIRTHS-PROPOSED-2026-11-08.tsv]"); did.append(f"+* {b[0]}")
    return " → ".join(toks), " ‖ ".join(parts), did


def row_step(old, new, births_tsv):
    """--row-step OLD NEW BIRTHS.tsv (2026-11-08): the card of version OLD with the births as «* year» (the reviewed list), the death floors,
    joinings and Volapük dates ruled since (DEATH_TPQ, ROW_JOIN, ROW_VOLAPUK), the names by LK_NAMES, the rows set whole (ROW_SET); the tag
    totals following. Writes bingo-card-v<NEW>.csv, -supplement.csv, -lk1905.csv and .md; refuses if any exists."""
    out_dir = os.environ.get("BINGO_OUT", os.path.join(GEN, "bingo-card"))
    P = lambda v, suf: os.path.join(out_dir, f"bingo-card-v{v}{suf}")
    sufs = [".csv", "-supplement.csv", "-lk1905.csv", ".md"]
    there = [P(new, s) for s in sufs if os.path.exists(P(new, s))]
    if there: sys.exit("refusing, nothing written: exists: " + ", ".join(os.path.basename(p) for p in there))
    births = {}
    for r in csv.DictReader(open(births_tsv, encoding="utf-8"), delimiter="\t"):
        births[(r["stem"], r["card_name"])] = (r["proposed_birth"], r["source"], r["locator"], r["flag"])
    MAP, log = {}, []
    tag = lambda q: {w for t in q.split(" → ") for w in t.split(" ") if w and not re.match(r"^(\d{4}|≤|≥|\*)$", w)}
    for s in sufs[:3]:
        R = list(csv.DictReader(open(P(old, s), encoding="utf-8")))
        with open(P(new, s), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R[0].keys())); w.writeheader()
            for r in R:
                if not r["stem"]: w.writerow(r); continue
                orig, name0 = r["tags_in_sequence"], r["full_name"]
                if r["stem"] in ROW_SET:
                    r["full_name"], r["name_source"], r["country"], t, r["evidence"] = ROW_SET[r["stem"]]; did = [f"row set: {orig} ⇒ {t}"]
                else:
                    t, r["evidence"], did = row_seq(r["stem"], name0, orig, r["evidence"], births)
                    r["full_name"], r["name_source"] = _ruled(LK_NAMES, r["stem"], r["country"]) or (r["full_name"], r["name_source"])
                if r["full_name"] != name0: did.append(f"name {name0} → {r['full_name']}")
                MAP[(r["stem"], orig)] = (t, r["full_name"], r["country"])
                if did: log.append(f"{s}: {r['stem']}: " + "; ".join(did))
                r["tags_in_sequence"] = t; w.writerow(r)
    L, col, table, ccol, delta = [], None, None, None, collections.defaultdict(collections.Counter)
    for line in open(P(old, ".md"), encoding="utf-8"):
        if line.startswith("|"):
            cells = line.rstrip("\n").split(" | ")
            hd = [c.strip().strip("|").strip() for c in cells]
            if "tags in sequence" in hd:
                col = hd.index("tags in sequence"); ccol = hd.index("country") if "country" in hd else None
                table = {"| plate": "album", "| stem": "supplement"}.get(cells[0].strip(), "supplement")
                if "as the roll prints him" in hd: table = "table3"
            elif col is not None and len(cells) > col and cells[col].strip() and not cells[col].startswith("-"):
                at = next((i for i, c in enumerate(cells) if re.fullmatch(r"`[^`]+`", c.strip().strip("|").strip())), None)
                st = cells[at].strip().strip("|").strip().strip("`") if at is not None else ""
                tail = " |" if cells[col].rstrip().endswith(" |") else ""
                orig = cells[col].rstrip()[:-2].strip() if tail else cells[col].strip()
                got = MAP.get((st, orig))
                if got is None and st: sys.exit(f"a row of the .md not in the CSVs: {st}: {orig}")
                if got:
                    cells[col] = got[0] + tail; cells[at + 1] = got[1]
                    if ccol is not None: cells[ccol] = got[2]
                    for g_ in tag(orig) | tag(got[0]):
                        delta[table][g_] += (g_ in tag(got[0])) - (g_ in tag(orig))
                line = " | ".join(cells) + "\n"
        else:
            col = None if line.strip() else col
        if line.startswith("# The Schuck-album bingo card — v" + old):
            line = line.replace("— v" + old, "— v" + new, 1).rstrip("\n") + (f" · v{new}, 2026-11-08, from v{old}: the births as «* year» where known (bingo-card/BIRTHS-REVIEW-2026-11-08.md: the Enciklopedio, then the ÖNB, then Wikipedia, then a period source; never «≤»); "
                   "Allum †≥ 1910, Chettiar †≥ 1937; de Beaufront 🟩 1888; Karp Wallon, 🟪 ≤ 1890; the Dervaux of the caption, Maurice of Boulogne\n")
        if line.startswith("**Grammar of the card:**"):
            line = line.replace("tags (Ⓚ Lingva Komitato", "the birth first, «* year», where known; tags (Ⓚ Lingva Komitato", 1)
        L.append(line)
    adds = {"the album's": ["album"], "the supplement's": ["supplement"], "both tables together": ["album", "supplement"],
            "table 3's": ["table3"], "all three tables": ["album", "supplement", "table3"]}
    head, out = None, []
    for line in L:
        if line.startswith("### Totals"): head = next((k for k in adds if k in line), None)
        m = re.match(r"^\| (\S+) \| ([^|]+) \| (\d+) \|$", line.rstrip("\n"))
        if m and head and m.group(1) in ORDER + ["Ⓚ", "Ⓐ"]:
            line = f"| {m.group(1)} | {m.group(2)} | {int(m.group(3)) + sum(delta[t][m.group(1)] for t in adds[head])} |\n"
        out.append(line)
    open(P(new, ".md"), "w", encoding="utf-8").write("".join(out))
    print("\n".join(log))
    print(f"v{old} → v{new}: {len(log)} rows changed; the totals' deltas: " + "; ".join(f"{t} {dict((k, v) for k, v in c.items() if v)}" for t, c in delta.items() if any(c.values())))
    return 0


def compare(a, b):
    """--compare A.csv B.csv (2026-10-20): the cards' sequences person by person (plate, position): every cell that
    differs, and the counts of † and of each camp glyph in both. Reads only."""
    def load(p):
        return {(r["plate"], r["pos"]): r for r in csv.DictReader(open(p, encoding="utf-8"))}
    A, B = load(a), load(b)
    glyphs = ["†", "‡", "🟦", "💙", "🟧", "🧡", "🟩", "🟢", "🔴", "⭕", "⭘", "⬜", "⬛", "🟨", "Ⓚ", "Ⓐ"]
    count = lambda D, g: sum(1 for r in D.values() if g in r["tags_in_sequence"])
    print("glyph: people in A → in B")
    print("  " + "; ".join(f"{g} {count(A, g)} → {count(B, g)}" for g in glyphs))
    n = 0
    for k in sorted(set(A) | set(B), key=lambda k: (int(re.sub(r"\D", "", k[0]) or 0), k[1])):
        sa, sb = (A.get(k) or {}).get("tags_in_sequence", "—"), (B.get(k) or {}).get("tags_in_sequence", "—")
        if sa != sb:
            n += 1; who = (A.get(k) or B.get(k))["stem"] or (A.get(k) or B.get(k))["caption"][:30]
            print(f"  {k[0]} {k[1]} {who}: {sa}  ⇒  {sb}")
    print(f"{n} cells differ")
    return 0

def main():
    if "--compare" in sys.argv:
        i = sys.argv.index("--compare"); return compare(sys.argv[i + 1], sys.argv[i + 2])
    if "--resequence" in sys.argv:
        i = sys.argv.index("--resequence"); return resequence(sys.argv[i + 1], sys.argv[i + 2])
    if "--lk-step" in sys.argv:
        i = sys.argv.index("--lk-step"); return lk_step(sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3])
    if "--volapuk-step" in sys.argv:
        i = sys.argv.index("--volapuk-step"); return volapuk_step(sys.argv[i + 1], sys.argv[i + 2])
    if "--row-step" in sys.argv:
        i = sys.argv.index("--row-step"); return row_step(sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3])
    allstems = stems()
    rows, unmatched = [], []
    for raw in open(CAPTIONS, encoding="utf-8"):
        raw = raw.rstrip("\n")
        if not raw or raw.startswith("#"): continue
        parts = raw.split(" · ", 2)
        if len(parts) < 3: continue
        page, pos, caption = parts
        stem, how = stem_of(caption, allstems)
        if not stem:
            unmatched.append((page, pos, caption)); rows.append(dict(page=page, pos=pos, caption=caption, stem="", how=how, tags=[], n=0, country=country_of(caption, ""))); continue
        L, tags = propose(stem, caption)
        if stem in HAND_CONFIRMED_HEARTS:
            tags = [(g, y, loc, ("RULED 2026-09-20: " + why) if (g in "💛💚🟨" and not why.startswith("RULED") and (g, y) in HAND_CONFIRMED_HEARTS[stem]) else why) for g, y, loc, why in tags]
        rows.append(dict(page=page, pos=pos, caption=caption, stem=stem, how=how, tags=tags, n=len(L), country=country_of(caption, stem)))
    # outputs: CREATE-ONLY (2026-10-20: a re-cut once overwrote the hand-edited card, restored from the backup and git;
    # the default version 0.1 would overwrite v0.1): BINGO_OUT names the folder (default the geniza root), and every
    # file a run writes must not exist, or nothing is written
    out_dir = os.environ.get("BINGO_OUT", os.path.join(GEN, "bingo-card"))
    out_csv = os.path.join(out_dir, f"bingo-card-v{VER}.csv"); out_md = os.path.join(out_dir, f"bingo-card-v{VER}.md")
    planned = [out_csv, out_md, out_csv.replace(".csv", "-supplement.csv"), out_csv.replace(".csv", "-lk1905.csv"),
               os.path.join(out_dir, f"bingo-card-v{VER}-sources.csv"), os.path.join(out_dir, f"bingo-card-v{VER}-gaps.csv")]
    there = [p for p in planned if os.path.exists(p)]
    if there: sys.exit("refusing, nothing written: exists: " + ", ".join(os.path.basename(p) for p in there) + " (BINGO_VER names a new version, BINGO_OUT another folder)")
    srcs = OrderedDict(); gaps = []
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["plate", "pos", "caption", "stem", "country", "match", "n_fact_lines", "tags_in_sequence", "evidence", "hand_pass"])
        for r in rows:
            seq = seq_of(r["tags"])
            ev = " ‖ ".join(f"{g}: {why} [{loc}]" for g, y, loc, why in r["tags"] if loc or why)
            hand = []
            if not r["stem"]: hand.append("UNMATCHED caption")
            if r["stem"] and r["n"] == 0: hand.append("no fact lines")
            if any(("hand-confirm" in why or "hand-date" in why or "HAND-ONLY" in why) and not why.startswith("RULED") and not (g == "·" and r["stem"] in HAND_RETURN_DISMISSED) for g, y, loc, why in r["tags"]) and r["stem"] not in HAND_CONFIRMED_CAMP: hand.append("proposal to confirm/date")
            # 2026-09-19 21:05 — witness dots (a rival organ merely naming the man) are NOT a hand question («rival organs cite
            # Esperantists all the time», circles never from bylines); only adhesion-shaped or return-shaped dots go to the human
            if any(g == "·" and ("return-shaped" in why or "Esperanto-marked lines after" in why) for g, y, loc, why in r["tags"]) and r["stem"] not in HAND_RETURN_DISMISSED: hand.append("return-shaped line(s) after a camp square — 🟢 or not? (a movement act, not kin or a citation)")
            if any(g == "·" and "Ido-adhesion-shaped" in why for g, y, loc, why in r["tags"]) and r["stem"] not in HAND_RETURN_DISMISSED: hand.append("Ido-adhesion-shaped line outside the roster runs — 🟦/💙 or dismiss")
            if any(g == "·" and "other-auxlang-adherence-shaped" in why for g, y, loc, why in r["tags"]) and r["stem"] not in HAND_RETURN_DISMISSED: hand.append("other-auxlang-shaped line outside the roster runs — 🟧/🧡 or dismiss")
            if any(g in "🔴⭕" for g, *_ in r["tags"]) and r["stem"] not in HAND_RESOLVED_STRIKE: hand.append("strike — colour the man separately (⬜ hand-only)")
            if any(g in "💙🧡" and not why.startswith("RULED") for g, y, loc, why in r["tags"]): hand.append("sympathiser cell — degree to confirm")
            w.writerow([r["page"], r["pos"], r["caption"], r["stem"], r["country"], r["how"], r["n"], seq, ev, "; ".join(hand)])
            for g, y, loc, why in r["tags"]:
                if loc:
                    src = re.sub(r"\s+l\.?\s*[\dL–\-, ]+.*$", "", loc).strip("`  ").strip(); src = src.split(" (")[0]
                    srcs[src] = srcs.get(src, 0) + 1
            if hand: gaps.append((r["stem"] or r["caption"][:40], "; ".join(hand)))
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(f"# The Schuck-album bingo card — v{VER} ({len(rows)} portraits; cut {__import__('datetime').date.today().isoformat()})\n\n")
        if VER != "0.1":
            fh.write("**Grammar of the card:** squares are ACTS (🟩 stayed · 🟨 voted for reform 1894 · 🟦 Ido · 🟧 other auxlang · ⬜ lapse · ⬛ renounced · ‡ died ≤ 1908); circles are SEATS (🔴 struck for disloyalty · ⭕ struck for silence · ⭘ resigned · 🟢 returned); hearts are LEANINGS (💛 for reform before 1894 · 💚 for the language as it was, before 1894 · 💙 Ido sympathiser · 🧡 other-auxlang sympathiser); tags (Ⓚ Lingva Komitato · Ⓐ Akademio · ◈ unifier · ◐ double membership · †). v0.1 was the mechanical proposal; this version carries the hand pass — every cell a human had to rule is ruled, and the rulings are listed at the end.\n\n")
            # v0.3 (2026-10-20; the editor): what changed against v0.2, and the witness marks left out
            if VER.startswith("0.3"):
                fh.write("**v0.3, re-cut 2026-10-20 from the profiles as they now stand** (the facts rewritten in Esperanto with event kinds; "
                         "the tool reads the kinds, a «morto» line counting only when its subject is the card's own person). Against v0.2, the corrections: "
                         "Lambert † 1959, not 1920 (the 1920 line is his wife's death); Cart † 1931, not 1930; Hodler † 1920, not 1910 (v0.2's year came from EdE s.v. «Berthelot»); "
                         "Ellis Ⓐ 1908, not 1911 (elected by the LK at Dresden, 1908); Privat's «·» 1912 dropped (a false return: «Reveninte Ĝenevon», back in Geneva for New Year). "
                         "**Witness marks left out for the namesakes** (Charles and René Lemaire, Schmidt, Kühnl): the roster runs of 2026-09-13 counted the surname alone "
                         "and wrote one line per surname and organ, now in the surname's ambiguous file; v0.2 gave both Lemaires the same counts. Their marks return "
                         "when Progreso, Mondo and Cosmoglotta are dowsed and each man's own lines are counted (the dowse runbook, D6 point 7). "
                         "The «·» counts of Esperanto-marked lines after a camp move with the wording of the lines: a prompt for a look, nothing more.\n\n")
        fh.write(f"### Totals — the album's 106 portraits (a person can carry several tags; hand-pass cells: {len(gaps)})\n\n")
        fh.write(tag_table([r["tags"] for r in rows]) + "\n")
        fh.write(country_table([(r["country"], r["tags"]) for r in rows]) + "\n")
        fh.write("`[cut by tools/bingo-card.py from profiles/*.md; every tag carries the year and locator of the fact line that earned it; ⬛ is never proposed; HAND-PASS = the cells a human must rule. Palette: QUEUE U11-B.]`\n\n")
        fh.write("| plate | pos | caption | stem | country | lines | tags in sequence | hand-pass |\n|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            seq = seq_of(r["tags"])
            hand = "; ".join(h for h in [
                "UNMATCHED" if not r["stem"] else "", "no lines" if r["stem"] and r["n"] == 0 else "",
                "confirm?" if any(("hand-confirm" in why or "hand-date" in why or "HAND-ONLY" in why) and not why.startswith("RULED") and not (g == "·" and r["stem"] in HAND_RETURN_DISMISSED) for g, y, loc, why in r["tags"]) and r["stem"] not in HAND_CONFIRMED_CAMP else "", "strike" if any(g in "🔴⭕" for g, *_ in r["tags"]) and r["stem"] not in HAND_RESOLVED_STRIKE else "",
                "degree?" if any(g in "💙🧡" and not why.startswith("RULED") for g, y, loc, why in r["tags"]) else ""] if h)
            fh.write(f"| {r['page']} | {r['pos']} | {name_of(r['caption'])} | `{r['stem']}` | {r['country']} | {r['n']} | {seq} | {hand} |\n")
        # Bein's roll on the main table
        fh.write("\n**Bein's Boulogne roll (Aug 1905) among the portraits:** " + ", ".join(sorted(r["stem"] for r in rows if r["stem"] in BEIN_1905)) + "\n")
        # the supplement
        supp = []
        album = {r["stem"] for r in rows}
        for st in list(SCHUCK_PROSE) + sorted(BEIN_1905 - album - set(SCHUCK_PROSE)):
            if st in album or st not in allstems: continue
            L2, tags2 = propose(st, "")
            canon = []
            if st in SCHUCK_PROSE: canon.append(f"Schuck prose p. {SCHUCK_PROSE[st][0]}")
            if st in BEIN_1905: canon.append("Bein 1905")
            supp.append((st, canon, tags2, len(L2)))
        fh.write(f"\n## Supplement — the canon not pictured ({len(supp)}): the names Schuck's own prose calls pioneers but does not portray, plus Bein's Boulogne roll (Aug 1905)\n\n")
        fh.write("`[Inclusion is principled: a name must be in the album's prose (pp. 8–18 of the OCR) or in Bein's platform speech of Aug 1905 — two in-house canons dated before the split. Same tags, same rules, same script.]`\n\n")
        fh.write("*Noted, not tabled (editor 2026-09-18 15:50): **Frans Swagers** (Antwerp) is a unifier by the same test — the Feb 1909 «Interkonsento» in* Belga Esperantisto*, «kontentigu la progresemulojn kaj renasku la ĝeneralan konkordon», refused by Cart in* Lingvo Internacia *— but he is in no canon (not the album, not its prose, not ROLL 1, not Bein), and the canon is not to be stretched to admit him. Hector Hodler's Dec 1907* Belga Sonorilo *plea to examine novelties before refusing them is too mild to count.*\n\n")
        fh.write(f"### Totals — the supplement's {len(supp)}\n\n")
        fh.write(tag_table([t for _, _, t, _ in supp]) + "\n")
        fh.write(country_table([(SUPP_COUNTRY.get(st, "?"), t) for st, _, t, _ in supp]) + "\n")
        fh.write(f"### Totals — both tables together ({len(rows) + len(supp)})\n\n")
        fh.write(tag_table([r["tags"] for r in rows] + [t for _, _, t, _ in supp]) + "\n")
        fh.write(country_table([(r["country"], r["tags"]) for r in rows] + [(SUPP_COUNTRY.get(st, "?"), t) for st, _, t, _ in supp]) + "\n")
        fh.write("| stem | canon | country | lines | tags in sequence |\n|---|---|---|---|---|\n")
        for st, canon, tags2, n2 in supp:
            seq = seq_of(tags2)
            fh.write(f"| `{st}` | {' + '.join(canon)} | {SUPP_COUNTRY.get(st, '?')} | {n2} | {seq} |\n")
        with open(out_csv.replace('.csv', '-supplement.csv'), "w", newline="", encoding="utf-8") as fs:
            w2 = csv.writer(fs); w2.writerow(["stem", "canon", "country", "n_fact_lines", "tags_in_sequence", "evidence"])
            for st, canon, tags2, n2 in supp:
                w2.writerow([st, " + ".join(canon), SUPP_COUNTRY.get(st, "?"), n2,
                             seq_of(tags2),
                             " ‖ ".join(f"{g}: {why} [{loc}]" for g, y, loc, why in tags2 if loc or why)])
        # TABLE 3
        roll = lk_roll1(allstems)
        seen3 = set(); lk3 = []; unmatched3 = []
        in12 = album | {st for st, *_ in supp}
        for stem3, printed, c3, l3 in roll:
            if not stem3: unmatched3.append((printed, c3, l3)); continue
            if stem3 in in12 or stem3 in seen3: continue
            seen3.add(stem3)
            L3, t3 = propose(stem3, "")
            lk3.append((stem3, printed, c3, f"ROLL 1 l.{l3}", t3, len(L3)))
        for stem3, c3 in LK_1907.items():
            if stem3 in in12 or stem3 in seen3 or stem3 not in allstems: continue
            seen3.add(stem3); L3, t3 = propose(stem3, "")
            lk3.append((stem3, stem3, c3, "Cirk. 9a/10a, Dec 1907", t3, len(L3)))
        fh.write(f"\n## Table 3 — the Lingva Komitato before the 1909 stacking, not in the two tables above ({len(lk3)})\n\n")
        fh.write("`[ROLL 1 = the first LK as read out at Boulogne, 9 Aug 1905, printed in Esperantista Dokumentaro 1 (Aug 1906) pp. 21–23, transcribed in BK-IV (profiles/by-source/bk-iv-lingva-komitato-rolls-2026-09-08.md); plus the four admitted by Cirk. 9a/10a (Dec 1907). Everyone here is Ⓚ by construction. Country = the roll's own heading.]`\n\n")
        fh.write(f"### Totals — table 3's {len(lk3)}\n\n")
        fh.write(tag_table([t for *_, t, _ in lk3]) + "\n")
        fh.write(country_table([(c, t) for _, _, c, _, t, _ in lk3]) + "\n")
        fh.write(f"### Totals — all three tables ({len(rows) + len(supp) + len(lk3)})\n\n")
        alltags = [r["tags"] for r in rows] + [t for _, _, t, _ in supp] + [t for *_, t, _ in lk3]
        fh.write(tag_table(alltags) + "\n")
        fh.write(country_table([(r["country"], r["tags"]) for r in rows] + [(SUPP_COUNTRY.get(st, "?"), t) for st, _, t, _ in supp] + [(c, t) for _, _, c, _, t, _ in lk3]) + "\n")
        fh.write("| stem | as the roll prints him | country | source | lines | tags in sequence |\n|---|---|---|---|---|---|\n")
        for stem3, printed, c3, src3, t3, n3 in lk3:
            seq = seq_of(t3)
            fh.write(f"| `{stem3}` | {printed} | {c3} | {src3} | {n3} | {seq} |\n")
        if unmatched3:
            fh.write("\n**ROLL 1 names with no profile stem (not on the roster — add to LK_HAND if a profile exists under another spelling):** " + "; ".join(f"{p} ({c}, l.{l})" for p, c, l in unmatched3) + "\n")
        with open(out_csv.replace('.csv', '-lk1905.csv'), "w", newline="", encoding="utf-8") as f3:
            w3 = csv.writer(f3); w3.writerow(["stem", "printed", "country", "source", "n_fact_lines", "tags_in_sequence", "evidence"])
            for stem3, printed, c3, src3, t3, n3 in lk3:
                w3.writerow([stem3, printed, c3, src3, n3, seq_of(t3), " ‖ ".join(f"{g}: {why} [{loc}]" for g, y, loc, why in t3 if loc or why)])
        # ---- publication components (v0.2, 2026-09-20 «go»): P-SRC and P-GAP as CSVs beside the card, and the rulings as the changelog ----
        def src_kind(x):
            xl = x.lower()
            if "ruled" in xl or "hand" in xl or "editor" in xl: return "hand ruling"
            if "album" in xl or "schuck" in xl: return "the Schuck album"
            if "oge" in xl or "cirkulero" in xl or "lingva komitato" in xl or "akademio" in xl: return "OGE / LK rolls and protocols"
            if "progreso" in xl or "mondo" in xl or "ido." in xl or "ido (" in xl or "cosmoglotta" in xl or "kosmoglott" in xl or "novialiste" in xl or "svensk" in xl: return "the rival organs (Progreso, Mondo, Ido, Cosmoglotta, Novialiste, Svensk)"
            if "esperanto 189" in xl or "esperanto.189" in xl or "adresaro" in xl or "roll" in xl: return "La Esperantisto 1889–95 and the Adresaro"
            if "lesperantiste" in xl or "lingvo internacia" in xl or "belga" in xl or "esperantouea" in xl or "brita" in xl or "amerika" in xl or "larevuo" in xl or "bohema" in xl or "ruslanda" in xl or "germana" in xl or "pola" in xl: return "the Esperanto organs 1898–1922"
            if "ede" in xl or "enciklopedio" in xl or "ora libro" in xl or "oralibro" in xl or "zakrzewski" in xl or "privat" in xl or "sikosek" in xl or "künzli" in xl or "kunzli" in xl or "forster" in xl or "garvía" in xl or "dyer" in xl or "ludovikito" in xl or "waringhien" in xl or "leteroj" in xl or "neves" in xl or "bucek" in xl or "bibliografio" in xl: return "histories, encyclopaedias, letters (secondary)"
            if "wikipedia" in xl or "wikitext" in xl or "commons" in xl: return "Wikipedia / Commons"
            return "other by-source evidence"
        src_csv = os.path.join(out_dir, f"bingo-card-v{VER}-sources.csv")
        with open(src_csv, "w", newline="", encoding="utf-8") as sh:
            w = csv.writer(sh); w.writerow(["kind", "source (as the evidence line cites it)", "cells"])
            for x, n in sorted(srcs.items(), key=lambda kv: (src_kind(kv[0]), -kv[1])): w.writerow([src_kind(x), x, n])
        fh.write(f"\n## P-SRC v{VER} — sources cited by the evidence lines ({len(srcs)} distinct; also `bingo-card-v{VER}-sources.csv`, grouped by kind)\n\n")
        kinds = defaultdict(int)
        for x, n in srcs.items(): kinds[src_kind(x)] += n
        fh.write("| kind | cells cited |\n|---|---|\n")
        for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]): fh.write(f"| {k} | {n} |\n")
        fh.write("\n")
        for x, n in sorted(srcs.items(), key=lambda kv: -kv[1])[:40]: fh.write(f"- {n} · {x}\n")
        fh.write(f"- … the rest in the CSV\n")
        # P-GAP: not the cells a human must rule (that is 0 after the hand pass) but the PRESSING GAPS a historian could close
        pg = []
        for r in rows:
            if not r["stem"]: pg.append((r["caption"][:40], "unmatched caption", "identify the sitter")); continue
            g = [t[0] for t in r["tags"]]
            if r["n"] < 12: pg.append((r["stem"], f"thin profile ({r['n']} lines)", "any dated act 1908–1914 (roll, congress, organ)"))
            if "†" not in g and "‡" not in g: pg.append((r["stem"], "death year open", "an obituary or a register entry"))
            for gl, y, loc, why in r["tags"]:
                if "⚠" in why and gl in "🟨🟦🟧⬜⬛💛💚": pg.append((r["stem"], f"{gl} {y} carries a ⚠", re.sub(r"^.*?⚠\s*", "", why).strip(" ()—")[:140] or why[:140]))
            if r["stem"] not in HAND_RESOLVED_STRIKE and "⭕" in g and "⬜" not in g and "⬛" not in g and not any(t[0] in "🟦🟧🟢" and t[1] and t[1] > [x[1] for x in r["tags"] if x[0] == "⭕"][0] for t in r["tags"]):
                pg.append((r["stem"], "struck, outcome unknown", "any act after the strike — a return (🟢), a camp, or nothing (⬜)"))
        gap_csv = os.path.join(out_dir, f"bingo-card-v{VER}-gaps.csv")
        with open(gap_csv, "w", newline="", encoding="utf-8") as gh:
            w = csv.writer(gh); w.writerow(["stem", "gap", "what would close it"])
            for row in pg: w.writerow(row)
        fh.write(f"\n## P-GAP v{VER} — cells a human must rule ({len(gaps)}) · pressing gaps a historian could close ({len(pg)}; also `bingo-card-v{VER}-gaps.csv`)\n\n")
        for s2, h in gaps: fh.write(f"- `{s2}` — {h}\n")
        if gaps: fh.write("\n")
        for st2, gp, cl in pg: fh.write(f"- `{st2}` — {gp} → {cl}\n")
        # the changelog: every hand ruling in force, as the record of v0.1 → v0.2
        fh.write(f"\n## Rulings in force (the hand pass of 2026-09-19/20 — `bingo-card-hand-pass-2026-09-19.md` is the narrative changelog; `profiles/by-source/editor-adjudications-2026-09-18.md` the fact lines)\n\n")
        fh.write("| stem | mark | year | ruling |\n|---|---|---|---|\n")
        for st2 in sorted(HAND_RULINGS):
            for gl, y, loc, why in HAND_RULINGS[st2]: fh.write(f"| `{st2}` | {gl} | {y} | {why[:220]} |\n")
        sup_rows = [(st2, "".join(sorted(gl))) for st2, gl in sorted(HAND_SUPPRESS.items())]
        fh.write("\nScript proposals overruled by hand (suppressed): " + "; ".join(f"`{a}` {b}" for a, b in sup_rows) + "\n")
        if unmatched:
            fh.write("\n## Unmatched captions (add to HAND in the script)\n\n")
            for p, pos, c in unmatched: fh.write(f"- {p} · {pos} · {c}\n")
    tally = defaultdict(int)
    for r in rows:
        for g, *_ in r["tags"]: tally[g] += 1
    print(f"portraits {len(rows)} · matched {sum(1 for r in rows if r['stem'])} · unmatched {len(unmatched)} · gaps {len(gaps)}")
    print("tags:", dict(tally)); print("wrote", out_csv, out_md)

if __name__ == "__main__":
    main()
