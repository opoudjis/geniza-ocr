#!/usr/bin/env python3
"""Smelt: the pictures at the head of a biography and of its gist (the editor, 2026-11-10; on the album's faces: the photograph
alone).

    tools/smelt-portraits.py faces                      the album's portraits of the card's people, bare (no marks), cut to
                                                        smelt/portretoj/<card stem>.jpg (generated, overwriting, like a render)
    tools/smelt-portraits.py table                      smelt/PORTRETOJ.tsv: a row added for every smelt folder's card picture
                                                        not yet in it (the album face, or bingo-card/visual/rest/<stem>.jpg);
                                                        rows already there are never changed; more photos and the caricatures
                                                        are added by hand
    tools/smelt-portraits.py gist STEM TAG [--replace]  smelt/STEM/S4-GIST-VIEW-TAG.md: the pictures, then the gist (create-only;
                                                        the gist is the writer's return and is not changed)

As a module: heading(stem, d) -> the pictures' block for a file in folder d, or "" (tools/smelt-s4-view.py puts it under the
biography's title).
PORTRETOJ.tsv: stem (the smelt folder), order, kind («foto» or «karikaturo»), file (relative to geniza/; «../caricatures/…»
for the drawings), caption (Esperanto), credit (a siglum and place where there is one), how. The photos in order, at most five,
then the caricature beside them, all one height.
Reads: bingo-card/bingo-card-v<CARD>.csv and -supplement.csv, bingo-card/visual/PORTRAITS.tsv, the album's pages (through
tools/bingo-visual.py's own finders, so a face is cut where the card's plates find it). Ezri, 2026-11-10."""
import csv, importlib.util, os, re, sys, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
CARD = "0.5.3"
TABLE = os.path.join(G, "smelt", "PORTRETOJ.tsv")
FACES = os.path.join(G, "smelt", "portretoj")
COLS = ["stem", "order", "kind", "file", "caption", "credit", "how"]
HEIGHT = 260
MAXPHOTOS = 5


def bv():
    spec = importlib.util.spec_from_file_location("bingo_visual", os.path.join(ROOT, "tools", "bingo-visual.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def card_rows():
    rows = list(csv.DictReader(open(os.path.join(G, "bingo-card", f"bingo-card-v{CARD}.csv"), encoding="utf-8")))
    sup = list(csv.DictReader(open(os.path.join(G, "bingo-card", f"bingo-card-v{CARD}-supplement.csv"), encoding="utf-8")))
    return rows, sup


def faces():
    """each album plate's portraits found as bingo-visual.py's plates() finds them, and cut bare"""
    from PIL import Image
    v = bv()
    os.makedirs(FACES, exist_ok=True)
    by = {}
    for r in card_rows()[0]:
        p = re.match(r"(\d+) \(PDF (\d+)\)", r["plate"])
        if p: by.setdefault((int(p.group(2)), p.group(1)), []).append(r)
    failed, n = [], 0
    for (pdf, printed), rows in sorted(by.items()):
        raw = Image.open(os.path.join(v.ALBUM, f"10019B14-{pdf - 1:04d}.jpg")).convert("RGB")
        page = v.straightened(raw)
        boxes = v.portraits(page)
        if len(boxes) < len(rows): page, boxes = raw, v.portraits(raw)
        if len(rows) == 1 and boxes: boxes = [tuple(boxes[0][:3]) + (boxes[0][3] - .011,)]
        if len(boxes) != len(rows): failed.append(f"PDF {pdf}: {len(boxes)} found, {len(rows)} on the card"); continue
        slots = {"C": boxes[0]} if len(rows) == 1 else {v.letters(b): b for b in boxes}
        if set(slots) != {r["pos"] for r in rows}:
            failed.append(f"PDF {pdf}: positions {sorted(slots)} against the card's {sorted(r['pos'] for r in rows)}"); continue
        W, H = page.size
        for r in rows:
            b = slots[r["pos"]]
            c = page.crop((int(b[0] * W), int(b[1] * H), int(b[2] * W), int(b[3] * H)))
            c.save(os.path.join(FACES, r["stem"] + ".jpg"), quality=90)
            n += 1
    print(f"{n} faces cut to {os.path.relpath(FACES, ROOT)}/")
    if failed: print("not cut:\n  " + "\n  ".join(failed))


def read_table():
    if not os.path.exists(TABLE): return []
    return list(csv.DictReader(open(TABLE, encoding="utf-8"), delimiter="\t"))


def card_stem(stem, stems):
    return stem if stem in stems else next((k for k in stems if stem.endswith("-" + k)), None)


def table():
    rows, sup = card_rows()
    album = {r["stem"]: r for r in rows if re.match(r"\d+ \(PDF \d+\)", r["plate"])}
    por = {r["stem"]: r for r in csv.DictReader(open(os.path.join(G, "bingo-card", "visual", "PORTRAITS.tsv"), encoding="utf-8"), delimiter="\t")}
    rest = {f[:-4] for f in os.listdir(os.path.join(G, "bingo-card", "visual", "rest")) if f.endswith(".jpg")}
    stems = {r["stem"] for r in rows} | {r["stem"] for r in sup}
    have = read_table()
    held = {r["stem"] for r in have}
    new = []
    for stem in sorted(os.listdir(os.path.join(G, "smelt"))):
        if not os.path.isdir(os.path.join(G, "smelt", stem)) or stem in held or stem == "portretoj": continue
        k = card_stem(stem, stems | rest)   # rest/ holds pictures of people neither on the card nor in its supplement (Asada, Benoît, Gauntlett, Guillaume)
        if not k: continue
        if k in album:
            r = album[k]; pg = re.match(r"(\d+)", r["plate"]).group(1)
            if not os.path.exists(os.path.join(FACES, k + ".jpg")): print(f"{stem}: no face cut yet (run «faces»)"); continue
            cap = " / ".join(s.strip() for s in r["caption"].split("/"))
            new.append({"stem": stem, "order": "1", "kind": "foto", "file": f"smelt/portretoj/{k}.jpg", "caption": f"la albumo de Schuck: «{cap}»",
                        "credit": f"SchuAlb:{pg}", "how": f"the card's album face (smelt-portraits.py faces), plate {r['plate']}, {r['pos']}"})
        elif k in rest:
            p = por.get(k, {})
            new.append({"stem": stem, "order": "1", "kind": "foto", "file": f"bingo-card/visual/rest/{k}.jpg", "caption": p.get("caption", ""),
                        "credit": p.get("credit", ""), "how": "the card's picture outside the album (bingo-visual.py --cut, PORTRAITS.tsv)"})
    exists = os.path.exists(TABLE)
    with open(TABLE, "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, COLS, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\", lineterminator="\n")
        if not exists: w.writeheader()
        for r in new: w.writerow(r)
    print(f"{os.path.relpath(TABLE, ROOT)}: {len(new)} rows added, {len(have)} kept: " + ", ".join(r["stem"] for r in new))


def heading(stem, d):
    """the pictures of smelt/<stem>/ as a row of images, one height, and a line of captions under them; "" if none"""
    rows = [r for r in read_table() if r["stem"] == stem]
    photos = sorted((r for r in rows if r["kind"] == "foto"), key=lambda r: int(r["order"]))[:MAXPHOTOS]
    cars = sorted((r for r in rows if r["kind"] == "karikaturo"), key=lambda r: int(r["order"]))[:1]
    pics = photos + cars
    if not pics: return ""
    imgs, caps = [], []
    for i, r in enumerate(pics, 1):
        src = urllib.parse.quote(os.path.relpath(os.path.normpath(os.path.join(G, r["file"])), d))
        alt = r["caption"].replace('"', "'")
        imgs.append(f'<img src="{src}" alt="{alt}" height="{HEIGHT}">')
        what = "karikaturo" if r["kind"] == "karikaturo" else "foto"
        caps.append(f"{i}. {what}: {r['caption']}" + (f" ({r['credit']})" if r["credit"] else ""))
    return "<p>" + " ".join(imgs) + "</p>\n\n*" + "; ".join(caps) + ".*\n"


def gist(stem, tag):
    d = os.path.join(G, "smelt", stem)
    src = open(os.path.join(d, f"S4-GIST-{tag}.md"), encoding="utf-8").read()
    h = heading(stem, d)
    m = re.search(r"^# La (?:mallonga|skiza) biografio de (.+)$", src, re.M)
    if m: first, rest_ = f"# La skiza biografio de {m.group(1).strip()}", src[m.end():]
    else:
        # a gist of the periods route is filed under «# Return: …» with no title of its own: the title from smelt/TITOLOJ.tsv
        tp = os.path.join(G, "smelt", "TITOLOJ.tsv")
        name = next((r[1] for r in (l.split("\t") for l in open(tp, encoding="utf-8").read().split("\n")[1:] if l.strip())
                     if r[0] == stem), None) if os.path.exists(tp) else None
        if not name: sys.exit(f"{stem}: the gist has no title and smelt/TITOLOJ.tsv no row; no gist view made")
        first = f"# La skiza biografio de {name}"
        rest_ = "\n" + re.sub(r"\A# Return: [^\n]*\n+(`\[[^\n]*\]`\n+)?", "", src)
    # A «Post la morto» part that tells the death itself was the parts tool's fault, fixed 2026-11-10 (smelt_parts: «Post 1914»
    # read as after the death; Krumpholc and Georgi Atanasov, whose gists were briefed with it): its heading dropped in the
    # reading copy, so the last years stay in «La vivo»; the gist itself is not changed
    pm = re.search(r"^## Post la morto\s*\n(.*?)(?=^## |\Z)", rest_, re.M | re.S)
    if pm and re.search(r"\bmortis\b", pm.group(1)) and not re.search(r"\bpost (?:lia|ŝia) morto\b", pm.group(1)):
        rest_ = rest_[:pm.start()] + pm.group(1) + rest_[pm.end():]
    out = (f"`[tools/smelt-portraits.py el S4-GIST-{tag}.md: la titolo «La skiza biografio de …» (la redaktoro, 2026-11-10), kaj la bildoj de "
           f"{os.path.relpath(TABLE, G)} sub ĝi, kie ili estas; la teksto mem senŝanĝa.]`\n\n" + first + "\n\n" + h + rest_)
    p = os.path.join(d, f"S4-GIST-VIEW-{tag}.md")
    with open(p, "w" if "--replace" in sys.argv else "x", encoding="utf-8") as fh: fh.write(out)
    print(f"{os.path.relpath(p, ROOT)}: «{first[2:]}», {h.count('<img ')} pictures")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if a == ["faces"]: faces()
    elif a == ["table"]: table()
    elif len(a) == 3 and a[0] == "gist": gist(a[1], a[2])
    else: sys.exit(__doc__)
