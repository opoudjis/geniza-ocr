#!/usr/bin/env python3
"""The bingo card's visual form: its marks laid over the portraits (the editor, 2026-09-13; 2026-11-06, the card in release 0.1).

    bingo-visual.py VERSION --plates [--only PDFPAGE,PDFPAGE]    the album's plates, each portrait with its marks
    bingo-visual.py VERSION --rest                               the people outside the album, as a page of tiles; a blank tile
                                                                 where no picture is held
    bingo-visual.py --cut                                        bingo-card/visual/PORTRAITS.tsv's pictures, cut to rest/<stem>.jpg
    bingo-visual.py --legend                                     the key to the marks, in Esperanto

Reads: the card's CSVs; the album's pages from sources/web-2026-11-06-onb-iiif/10019B14/10019B14/ (the IIIF page is the PDF page
less 1, the PDF having the ÖNB's sheet in front). Portraits are found on the page as the album's neutral grey rectangles on warm
paper, and checked against the card's count and position letters for the plate: a plate that disagrees is refused and named.
Marks are drawn, not set in an emoji font. «·» is left out: it notes a mention in an organ, no act (tools/bingo-card.py).
Writes, overwriting (generated, like a render): bingo-card/visual/plate-<printed page>.jpg, rest-<n>.jpg, rest/<stem>.jpg, key.png."""
import argparse, csv, glob, math, os, re, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
ALBUM = os.path.join(GEN, "sources", "web-2026-11-06-onb-iiif", "10019B14", "10019B14")
CARD = os.path.join(GEN, "bingo-card")
OUT = os.path.join(CARD, "visual")
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
SCALE = 3   # the page is drawn on at this enlargement, so the marks stay sharp; the result is reduced to WIDTH
WIDTH = 1400
PAPER = (243, 236, 216)
FIGURES = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"   # the years: a serif (the editor, 2026-11-06), with lining figures, which Georgia has not
DATE = (112, 112, 112)   # the years and codes, grey (the editor, 2026-11-06)
BAND, INK = (255, 253, 244), (18, 18, 18)   # the band is pale, the marks and years dark (the editor, 2026-11-06)

GREEN, YELLOW, BLUE, ORANGE, PURPLE, RED = (46, 160, 67), (245, 205, 40), (45, 110, 215), (240, 130, 30), (140, 80, 200), (215, 45, 45)
MARKS = {"🟩": ("square", GREEN), "🟨": ("square", YELLOW), "🟦": ("square", BLUE), "🟧": ("square", ORANGE), "🟪": ("square", PURPLE), "⬜": ("square", (205, 205, 205)), "⬛": ("square", (15, 15, 15)),
         "🔴": ("disc", RED), "🟢": ("disc", (135, 225, 140)), "🟠": ("disc", ORANGE), "⭕": ("ring", RED), "⭘": ("ring", (80, 80, 80)),
         "💛": ("heart", YELLOW), "💚": ("heart", GREEN), "💙": ("heart", BLUE), "🧡": ("heart", ORANGE),
         "Ⓚ": ("letter", "K"), "Ⓐ": ("letter", "A"), "◈": ("diamond", (40, 40, 40)), "◐": ("half", (40, 40, 40)), "†": ("text", "†"), "‡": ("text", "‡"),
         "*": ("text", "*")}   # the birth, «* year», first in the sequence (the card v0.4.10, 2026-11-08)
KEY = [("*", "naskiĝis"), ("🟩", "aliĝis al Esperanto"), ("🟪", "volapukisto"), ("🟨", "voĉdonis por reformo, 1894"), ("💛", "inklinis al reformo antaŭ 1894"), ("💚", "inklinis al la lingvo senŝanĝa antaŭ 1894; poste nur Guillaume, apoganto sen lerni ĝin"),
       ("🟦", "idisto"), ("💙", "simpatiis kun Ido"), ("🟧", "aliĝis al alia planlingvo"), ("🧡", "simpatiis kun alia planlingvo"), ("🟠", "kreis propran planlingvon"),
       ("⬜", "forlasis, laŭ la Lingva Komitato"), ("⬛", "publike rezignis pri mondlingvoj"), ("🔴", "forstrekita de la Lingva Komitato pro nelojaleco"), ("⭕", "forstrekita de la Lingva Komitato pro silento"), ("⭘", "eksiĝis de la Lingva Komitato"), ("🟢", "revenis al Esperanto"),
       ("Ⓚ", "membro de la Lingva Komitato"), ("Ⓐ", "membro de la Akademio"), ("◈", "proponis reunuiĝon inter Ido kaj Esperanto"), ("◐", "duobla membreco en Ido kaj Esperanto"), ("†", "mortis"), ("‡", "mortis ĝis fino de 1908")]


def tokens(seq):
    """the marks of a card cell, in order: (mark, what is printed under it)"""
    out = []
    for t in filter(None, (x.strip() for x in seq.split("→"))):
        year = re.search(r"\d{4}", t)
        y = year.group(0) if year else ""
        if "≤" in t: y = "≤" + y
        if "≥" in t: y = "≥" + y
        code = re.search(r"\b[a-z]{3}\b", t)   # a language's code beside an orange mark: none after 1908 means Occidental (the editor, 2026-11-06)
        code = code.group(0) if code else ""
        marks = [c for c in t if c in MARKS]
        if not marks: continue   # «·»
        for i, m in enumerate(marks): out.append((m, y if i == len(marks) - 1 else "", code))
    return out


def font(path, size): return ImageFont.truetype(path, size)


def glyph(d, m, x, y, s):
    """one mark in the s×s square at (x, y), on a pale band"""
    kind, val = MARKS[m]
    edge = INK
    if kind == "square": d.rectangle([x, y, x + s, y + s], fill=val, outline=edge, width=max(2, s // 16))
    elif kind == "disc": d.ellipse([x, y, x + s, y + s], fill=val, outline=edge, width=max(2, s // 16))
    elif kind == "ring": d.ellipse([x + s * .06, y + s * .06, x + s * .94, y + s * .94], outline=val, width=max(4, s // 6))
    elif kind == "heart":
        pts = []
        for i in range(60):
            t = 2 * math.pi * i / 60
            pts.append((x + s / 2 + s * .48 * (16 * math.sin(t) ** 3) / 16, y + s * .46 - s * .48 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16))
        d.polygon(pts, fill=val, outline=edge)
    elif kind == "letter":
        d.ellipse([x + s * .03, y + s * .03, x + s * .97, y + s * .97], outline=INK, width=max(3, s // 12))
        d.text((x + s / 2, y + s / 2), val, font=font(BOLD, int(s * .6)), fill=INK, anchor="mm")
    elif kind == "diamond":
        d.polygon([(x + s / 2, y), (x + s, y + s / 2), (x + s / 2, y + s), (x, y + s / 2)], outline=val, width=max(3, s // 12))
        d.polygon([(x + s / 2, y + s * .3), (x + s * .7, y + s / 2), (x + s / 2, y + s * .7), (x + s * .3, y + s / 2)], fill=val)
    elif kind == "half":
        d.ellipse([x, y, x + s, y + s], outline=val, width=max(3, s // 12))
        d.pieslice([x, y, x + s, y + s], 90, 270, fill=val)
    elif kind == "text":
        d.text((x + s / 2, y + s / 2), val, font=font(BOLD, int(s * 1.05)), fill=INK, anchor="mm")


def band_rows(toks, width, s):
    """the marks in rows, each mark with the width it needs"""
    yf, cf = font(FIGURES, int(s * .64)), font(FIGURES, int(s * .56))
    rows, row, used = [], [], int(s * .2)
    for t in toks:
        over = max(0, (yf.getlength(t[1]) - s) / 2)   # how far the year runs past its mark on each side
        w = int(over + s + max(over, int(s * .1) + cf.getlength(t[2]) if t[2] else 0)) + int(s * .22)
        if row and used + w > width: rows.append(row); row, used = [], int(s * .2)
        row.append((t, w)); used += w
    if row: rows.append(row)
    if len(rows) > 1 and len(rows[-1]) == 1: rows[-1].insert(0, rows[-2].pop())   # never one mark alone on a row (the editor, 2026-11-06)
    return rows, yf, cf


def band_height(seq, width, s):
    rows = band_rows(tokens(seq), width, s)[0]
    return (s + int(s * .72)) * len(rows) + int(s * .2)


def place(frames, seqs, s, lo, hi, gap, below=0):
    """where each band runs across: one row of marks where it can be had, the band wider than its picture if it must be, so long as it meets no other picture or band (the editor, 2026-11-06). frames: the pictures' boxes; lo, hi: the page's limits; below: the room a picture's caption takes under it"""
    n, spans = len(frames), []
    for i, (f, q) in enumerate(zip(frames, seqs)):
        x0, y0, x1, y1 = f
        toks = tokens(q)
        need = sum(w for _, w in band_rows(toks, 10 ** 6, s)[0][0]) + int(s * .3)
        h = band_height(q, 10 ** 6, s)
        l, r = lo, hi
        for j, g in enumerate(frames):
            if j != i and g[1] < y1 and g[3] + below > y1 - h:
                if g[2] <= (x0 + x1) / 2: l = max(l, g[2] + gap)
                else: r = min(r, g[0] - gap)
        base = x1 - x0
        w = max(base, min(need, r - l))
        a = max(l, min((x0 + x1 - w) // 2, r - w))
        spans.append(dict(a=a, b=a + w, l=l, r=r, base=base, h=h, foot=y1))
    for _ in range(3):   # two bands in one row that meet: apart first, then each cut back, and it takes another row
        for p, q in ((p, q) for p in sorted(spans, key=lambda t: t["a"]) for q in sorted(spans, key=lambda t: t["a"])):
            if p is q or p["a"] >= q["a"] or not (p["foot"] - p["h"] < q["foot"] and q["foot"] - q["h"] < p["foot"]): continue
            over = p["b"] + gap - q["a"]
            if over <= 0: continue
            d = min(over, p["a"] - p["l"]); p["a"] -= d; p["b"] -= d; over -= d
            d = min(over, q["r"] - q["b"]); q["a"] += d; q["b"] += d; over -= d
            if over > 0:
                d = min((over + 1) // 2, p["b"] - p["a"] - p["base"]); p["b"] -= max(d, 0); over -= max(d, 0)
                d = min(over, q["b"] - q["a"] - q["base"]); q["a"] += max(d, 0)
    return [(t["a"], t["b"]) for t in spans]


def band(img, box, seq, s, span=None):
    """the marks across the foot of a picture: a pale band, the marks in order, centred, each with its year under it. span: its left and right, where it runs wider than the box"""
    toks = tokens(seq)
    if not toks: return
    x0, y0, x1, y1 = box
    s0 = s
    if span: x0, x1 = span
    rows, yf, cf = band_rows(toks, x1 - x0, s)
    while len(rows) > 2:   # never three rows (the editor, 2026-11-06); the last resort, smaller marks
        s = int(s * .93); rows, yf, cf = band_rows(toks, x1 - x0, s)
    if len(rows) > 1 or s != s0: print(f"  band: {len(rows)} rows, marks at {s} of {s0}, {len(toks)} marks in {x1 - x0}: {seq}", flush=True)
    line = s + int(s * .72)
    h = line * len(rows) + int(s * .2)
    d = ImageDraw.Draw(img)
    d.rectangle([x0, y1 - h, x1, y1], fill=BAND, outline=INK, width=max(1, s // 22))
    for r, row in enumerate(rows):
        left = x0 + (x1 - x0 - sum(w for _, w in row)) // 2
        top = y1 - h + int(s * .12) + r * line
        for (m, y, code), w in row:
            mx = left + int(s * .11) + int(max(0, (yf.getlength(y) - s) / 2))
            glyph(d, m, mx, top, s)
            if code: d.text((mx + s + int(s * .1), top + s // 2), code, font=cf, fill=DATE, anchor="lm")
            if y: d.text((mx + s // 2, top + s + int(s * .05)), y, font=yf, fill=DATE, anchor="ma")
            left += w


def straightened(page):
    """the page turned to square: the scans lean by up to a degree, and a band is square to the image. The angle is the one at which the page's dark print lines up best across and down"""
    g = np.asarray(page.convert("L").resize((page.width // 3, page.height // 3))).astype(float)
    m = (g < 150).astype(float)
    m[:, :int(.08 * m.shape[1])] = 0; m[:, int(.92 * m.shape[1]):] = 0; m[:int(.06 * m.shape[0])] = 0; m[int(.95 * m.shape[0]):] = 0
    score = lambda a: (lambda r: r.sum(0).var() + r.sum(1).var())(ndi.rotate(m, a, reshape=False, order=0))
    best = max(np.arange(-1.5, 1.51, .1), key=score)
    return page.rotate(float(best), resample=Image.BICUBIC, fillcolor=PAPER)


def portraits(page):
    """the page's grey rectangles, as fractions of the page, top to bottom"""
    a = np.asarray(page.convert("RGB")).astype(int)
    H, W, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (abs(r - g) < 16) & ((r - b) < 26) & (a.max(2) < 222) & (g <= r + 6)
    m[:, :int(.05 * W)] = False; m[:, int(.97 * W):] = False
    m = ndi.binary_opening(ndi.binary_fill_holes(ndi.binary_closing(m, iterations=4)), iterations=10)
    lab, _ = ndi.label(m)
    out = []
    for s in ndi.find_objects(lab):
        h, w = s[0].stop - s[0].start, s[1].stop - s[1].start
        if .14 * W < w < .6 * W and h > .08 * H: out.append((s[1].start / W, s[0].start / H, s[1].stop / W, s[0].stop / H))
    return sorted(out, key=lambda b: (b[1], b[0]))


def letters(box):
    """the card's position letters for a portrait, from where it lies"""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return ("T" if cy < .35 else "M" if cy < .6 else "B") + ("L" if cx < .38 else "R" if cx > .55 else "C")


def read_card(version, suf=""):
    return list(csv.DictReader(open(os.path.join(CARD, f"bingo-card-v{version}{suf}.csv"), encoding="utf-8")))


def paper_span(page):
    """the printed leaf's left and right edges: the gutter and the dark backing left off"""
    g = np.asarray(page.convert("L")).astype(float)
    mid = g[int(.3 * g.shape[0]):int(.7 * g.shape[0])]
    light = np.percentile(mid, 80, axis=0) > 170
    W = len(light)
    left = next((x for x in range(int(.12 * W)) if light[x:x + 12].all()), 0)
    right = next((x for x in range(W - 1, int(.8 * W), -1) if light[max(0, x - 12):x].all()), W)
    return left, right


def plates(version, only):
    os.makedirs(OUT, exist_ok=True)
    by = {}
    for r in read_card(version):
        p = re.match(r"(\d+) \(PDF (\d+)\)", r["plate"])
        by.setdefault((int(p.group(2)), p.group(1)), []).append(r)
    failed = []
    for (pdf, printed), rows in sorted(by.items()):
        if only and pdf not in only: continue
        raw = Image.open(os.path.join(ALBUM, f"10019B14-{pdf - 1:04d}.jpg")).convert("RGB")
        page = straightened(raw)
        boxes = portraits(page)
        if len(boxes) < len(rows): page, boxes = raw, portraits(raw)   # a pale plate can lose its rectangle in the turn
        if len(rows) == 1: boxes = [tuple(boxes[0][:3]) + (boxes[0][3] - .011,)]   # a single portrait above a tailpiece; the photographer's credit, which the search takes in, left off its foot
        if len(boxes) != len(rows): failed.append(f"PDF {pdf}: {len(boxes)} found, {len(rows)} on the card"); continue
        left, right = paper_span(page)
        W, H = page.size
        big = page.resize((W * SCALE, H * SCALE), Image.LANCZOS)
        s = 66 if len(rows) > 1 else 84
        if len(rows) == 1: slots = {"C": boxes[0]}
        else: slots = {letters(b): b for b in boxes}
        if set(slots) != {r["pos"] for r in rows}:
            failed.append(f"PDF {pdf}: positions {sorted(slots)} against the card's {sorted(r['pos'] for r in rows)}"); continue
        if len(rows) == 1: lo, hi = .07, .84
        else: lo, hi = min(b[0] for b in boxes) - .075, max(b[2] for b in boxes) + .085
        frames = []
        for r in rows:
            b = slots[r["pos"]]
            inset = .006 * (b[2] - b[0])   # the band just inside the frame, where it fits
            frames.append((int((b[0] + inset) * W * SCALE), int(b[1] * H * SCALE), int((b[2] - inset) * W * SCALE), int((b[3] - .002) * H * SCALE)))
        spans = place(frames, [r["tags_in_sequence"] for r in rows], s, int(max(left / W, lo + .02) * W * SCALE), int(min(right / W, hi - .02) * W * SCALE), int(.008 * W * SCALE), below=int(.035 * H * SCALE))
        for f_, r, sp in zip(frames, rows, spans): band(big, f_, r["tags_in_sequence"], s, sp)
        big = big.crop((max(left, int(lo * W)) * SCALE, int(.05 * H) * SCALE, min(right, int(hi * W)) * SCALE, int(.955 * H) * SCALE))
        big = big.resize((WIDTH, round(big.height * WIDTH / big.width)), Image.LANCZOS)
        f = os.path.join(OUT, f"plate-{int(printed):02d}.jpg")
        big.save(f, quality=86, optimize=True)
        print(f, big.size, os.path.getsize(f) // 1024, "KB", flush=True)
    if failed: sys.exit("not made:\n  " + "\n  ".join(failed))


def picture(spec):
    """a source named in PORTRAITS.tsv: FILE.jpg, or FILE.pdf:PAGE, relative to sources/"""
    path, _, pg = spec.partition(":")
    full = os.path.join(GEN, "sources", path)
    if not pg: return Image.open(full).convert("RGB")
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(["pdftoppm", "-f", pg, "-l", pg, "-r", "300", "-jpeg", "-jpegopt", "quality=95", "-singlefile", full, os.path.join(t, "p")], check=True)
        return Image.open(os.path.join(t, "p.jpg")).convert("RGB").copy()


def aged(im):
    """the editor's own portrait, made to look of the album's time (2026-09-13): small and soft as the album's halftones are, flat in contrast, a mottled ground, a dot screen"""
    im = im.convert("L")
    im = im.resize((500, round(im.height * 500 / im.width)), Image.LANCZOS)
    a = ndi.gaussian_filter(np.asarray(im).astype(float), 1.1)
    h, w = a.shape
    rng = np.random.default_rng(1905)
    mottle = ndi.zoom(rng.normal(0, 1, (h // 40 + 2, w // 40 + 2)), 40, order=3)[:h, :w]
    a = 62 + a * (150 / 255) + 7 * mottle * (a / 255)
    yy, xx = np.mgrid[0:h, 0:w]
    a = a + 7 * np.sin(2 * np.pi * (xx + yy) / 5) * np.sin(2 * np.pi * (xx - yy) / 5) + rng.normal(0, 3, a.shape)
    vign = 1 - .22 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    return Image.fromarray(np.clip(a * vign, 0, 255).astype("uint8")).convert("RGB")


def cut():
    rest = os.path.join(OUT, "rest"); os.makedirs(rest, exist_ok=True)
    for r in csv.DictReader(open(os.path.join(OUT, "PORTRAITS.tsv"), encoding="utf-8"), delimiter="\t"):
        im = picture(r["source"])
        W, H = im.size
        x0, y0, x1, y1 = (float(r[k]) for k in ("x0", "y0", "x1", "y1"))
        c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
        if r["rotate"]: c = c.rotate(-int(r["rotate"]), expand=True)   # the column's degrees are clockwise
        if r["stem"] == "redaktoro": c = aged(c)
        elif r["rotate"]: c = ImageOps.autocontrast(c, cutoff=1)   # a face cut from a group, foggy beside the album's own
        f = os.path.join(rest, r["stem"] + ".jpg")
        c.save(f, quality=90)
        print(f, c.size, flush=True)


def placeholder(w, h):
    """the tile of someone with no picture: an empty head and shoulders and a question mark (the editor, 2026-11-06)"""
    k = 3
    img = Image.new("RGB", (w * k, h * k), (214, 207, 188))
    d = ImageDraw.Draw(img)
    cx, cy, rx, ry = w * k // 2, int(h * k * .36), int(w * k * .22), int(h * k * .205)
    d.ellipse([cx - int(w * k * .42), int(h * k * .62), cx + int(w * k * .42), int(h * k * 1.3)], fill=(176, 168, 148))
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(176, 168, 148))
    d.text((cx, cy), "?", font=font(SERIF, int(h * k * .24)), fill=(84, 78, 66), anchor="mm")
    return img.resize((w, h), Image.LANCZOS)


def rest(version):
    """the people outside the album, on pages of the album's own size: six to a page, each picture the size of an album portrait, a placeholder where there is none (the editor, 2026-11-06)"""
    held = os.path.join(OUT, "rest")
    last = {"stem": "redaktoro", "full_name": "Nick Nicholas", "country": "Australia", "tags_in_sequence": "* 1971 → 🟩 1985 → 🟧 jbo 1991 → 🟧 tlh 1995 → 🟧 jbo 2000 → ⬜ 2003 → 🟢 2026"}   # the card's close, the editor's order (2026-11-06; his dates, 19:2x)
    groups = [("La komitatanoj nomitaj de Schuck, sen portreto en la albumo", read_card(version, "-supplement")), ("La Lingva Komitato ĝis 1907, ekster la albumo", read_card(version, "-lk1905")), ("La kompilinto", [last])]
    # the roll of 1905 and the four of Dec. 1907 (the editor, 2026-11-08 14:0x); the editor's own tile on a page of its
    # own (14:3x: ruled by the editor: the editor's own tile alone on a page of its own)
    W, TW, TH, COLS, PER, S, TOP, PITCH = WIDTH, 480, 720, 2, 6, 53, 130, 1090   # the plates' final size: 1400 wide, portraits about 480 × 720, marks about 53
    GUT = (W - COLS * TW) // (COLS + 1)
    nf, cf = font(SERIF, 36), font(SERIF, 38)
    for old in glob.glob(os.path.join(OUT, "rest-*.jpg")): os.remove(old)
    n = 0
    for head, rows in groups:
        for start in range(0, len(rows), PER):
            page = rows[start:start + PER]
            n += 1
            img = Image.new("RGB", (W, TOP + PITCH * math.ceil(len(page) / COLS)), PAPER)
            d = ImageDraw.Draw(img)
            d.text((W / 2, 62), head, font=cf, fill=(60, 80, 50), anchor="mm")
            frames = []
            for i, r in enumerate(page):
                inrow = min(COLS, len(page) - i // COLS * COLS)
                gut = (W - inrow * TW) // (inrow + 1)
                x, y = gut + (i % COLS) * (TW + gut), TOP + (i // COLS) * PITCH
                f = os.path.join(held, r["stem"] + ".jpg")
                if os.path.exists(f):   # the whole cut, from the top of the frame: the band at the foot then lies on the empty part where it can
                    p = Image.open(f).convert("L").convert("RGB")
                    k = TW / p.width if p.height * TW / p.width >= TH - 100 else TH / p.height   # the whole width where the band hides what is left at the foot, else the height, the sides cut
                    p = p.resize((round(p.width * k), round(p.height * k)), Image.LANCZOS)
                    if k > 1.3 or r["stem"] == "mann": p = p.filter(ImageFilter.GaussianBlur(min(2.2, max(k, 1.6) * .7)))   # the halftone of a small source, not its blocks
                    d.rectangle([x, y, x + TW, y + TH], fill=(120, 116, 106))
                    l, t = (p.width - TW) // 2, max(0, (p.height - TH) // 4)
                    img.paste(p.crop((l, t, l + TW, min(t + TH, p.height))), (x, y))
                else: img.paste(placeholder(TW, TH), (x, y))
                d.rectangle([x, y, x + TW, y + TH], outline=(70, 90, 60), width=2)
                out, line = [], ""
                for w in r["full_name"].split():
                    if nf.getlength(line + " " + w) > TW + GUT - 30 and line: out.append(line); line = w
                    else: line = (line + " " + w).strip()
                out.append(line)
                for k_, s_ in enumerate(out[:2]): d.text((x + TW / 2, y + TH + 16 + k_ * 44), s_, font=nf, fill=(30, 30, 30), anchor="ma")
                if CITY.get(r["stem"]):   # the city under the name, in capitals, as Schuck's captions have it
                    cf_ = font(SERIF, 30); c_ = CITY[r["stem"]]
                    lines_ = [c_] if cf_.getlength(c_) <= TW + 40 else [c_.split(" (")[0], "(" + c_.split(" (", 1)[1]]   # a long one on two lines
                    for k2, t2 in enumerate(lines_): d.text((x + TW / 2, y + TH + 16 + len(out[:2]) * 44 + 2 + k2 * 36), t2, font=cf_, fill=DATE, anchor="ma")
                frames.append((x, y, x + TW, y + TH))
            for f_, r, sp in zip(frames, page, place(frames, [r["tags_in_sequence"] for r in page], S, 16, W - 16, 14)): band(img, f_, r["tags_in_sequence"], S, sp)
            out_f = os.path.join(OUT, f"rest-{n:02d}.jpg")
            img.save(out_f, quality=86, optimize=True)
            print(out_f, img.size, os.path.getsize(out_f) // 1024, "KB", [r["stem"] for r in page], flush=True)


# THE CITY under each name outside the album, as Schuck's captions give it (the editor, 2026-11-08 15:3x
#): in capitals; the Esperanto name
# where the period gave one (Parizo, Varsovio, Prago), else the local one (Lyon, Dijon), as Schuck wrote both; the country in brackets
# outside Europe, as his «LIMA (Peruo)», «EASTSOUND (Usono)». The LK of 1905 by the roll's own place; the others by their profile's
# residence nearest 1905; the four of 1907 and Zakrzewski by the list of 1 Jan 1909; the period's name with today's in brackets where a
# reader would not know it (the editor, 15:3x
#); a small place with its country (15:3x: the editor found Lysestvelter, Öfverselo, Bystřice pod Hostýnem and Loučka too obscure without their country)
CITY = {"twombley": "BOSTONO (Usono)", "holub": "LOUČKA (Aŭstrio-Hungario)", "kraus": "PRAGO", "krumpholc": "BYSTŘICE POD HOSTÝNEM (Aŭstrio-Hungario)", "boulet": "BOULOGNE-SUR-MER",
        "bricard": "PARIZO", "chavet": "NEUILLY-SUR-SEINE", "dor": "LYON", "evrot": "BOURG-EN-BRESSE", "lallemant": "DIJON", "saquet": "NANTES",
        "sentis": "GRENOBLE", "nalli": "PALERMO", "de-wahl": "REVAL (Tallinn)", "zinoviev": "POLTAVA", "lojko": "VILNO (Vilnius)", "devjatnin": "VILNO (Vilnius)",
        "kotzin": "KOVNO (Kaunas)", "radvan-ripinski": "PETERBURGO", "postnikov": "VLADIVOSTOK", "runeberg": "HELSINGFORS (Helsinki)",
        "emeric": "LIPIS (Malajo)", "lloyd": "LIVERPOOL", "coutinho": "RIO-DE-JANEIRO (Brazilo)", "gustafsson": "HELSINGFORS (Helsinki)", "benoit": "PARIZO",
        "guilbeau": "PARIZO", "guillaume": "PARIZO", "huet": "PARIZO", "sabadell": "BARCELONO", "blanc": "ROMO", "gauntlett": "OKAYAMA (Japanio)",
        "mac-kenzie": "KANAZAWA (Japanio)", "saint-martin": "MONTREALO (Kanado)", "morin": "SANTA-ROSA (Meksiko)", "allum": "LYSESTVELTER (Norvegio)",
        "abesgus": "TEHERANO (Persio)", "cederblad": "ÖFVERSELO (Svedio)", "zakrzewski": "VARSOVIO", "asada": "TOKIO (Japanio)", "evstifejev": "SOFIO",
        "mann": "LONDONO", "de-saussure": "ĜENEVO", "redaktoro": "MELBURNO (Aŭstralio)"}
SUB_EO = {"Poland": "Pollando", "Lithuania": "Litovio", "Estonia": "Estonio", "Ukraine": "Ukrainio", "Caucasus": "Kaŭkazio", "Crimea": "Krimeo",
          "Swiss": "sviso", "Brit.": "brita"}   # the parts of the empires of 1906, under the country
COUNTRY_EO = {"Australia": "Aŭstralio", "France": "Francio", "Russia": "Rusio", "Britain": "Britio", "Austria-Hungary": "Aŭstrio-Hungario", "Germany": "Germanio", "Italy": "Italio", "Belgium": "Belgio", "Sweden": "Svedio",
              "Switzerland": "Svislando", "Spain": "Hispanio", "Bulgaria": "Bulgario", "Finland": "Finnlando", "Japan": "Japanio", "Norway": "Norvegio", "USA": "Usono", "Canada": "Kanado", "Mexico": "Meksiko",
              "Netherlands": "Nederlando", "Brazil": "Brazilo", "Chile": "Ĉilio", "Denmark": "Danio", "Greece": "Grekio", "Iceland": "Islando", "India": "Barato", "Malta": "Malto", "Persia": "Persio", "Peru": "Peruo", "Portugal": "Portugalio"}


# THE FLAGS OF 1906 (the editor, 2026-11-08
#): drawn here, simplified, the arms left out or reduced to a mark, each as flown in 1906, the country by the card's
# borders of 1906: Russia's tricolour for Poland, Lithuania, Finland and the rest of the empire; the Union Flag for Britain; the Blue
# Ensign with its badge for Malta and the Star of India Red Ensign for India (the editor, 2026-11-08 15:2x;
#); the Red Ensign for Canada; the Dannebrog for Iceland; the German Empire's black-white-red; Austria-Hungary's civil
# flag of 1869; Italy with the shield of Savoy; Portugal's blue and white of the monarchy; the United States with 45 stars
# (1896-1908); Persia's tricolour with the lion and sun as a disc; Greece's land flag, the white cross on blue
RED, WHITE, BLUE, GREEN, YELLOW, BLACK = (200, 16, 46), (255, 255, 255), (0, 40, 120), (0, 130, 60), (250, 200, 0), (0, 0, 0)


def flag(img, country, x, y, w=48, h=32):
    c = re.sub(r" \(.*", "", country)
    f = Image.new("RGB", (w * 4, h * 4), WHITE); d = ImageDraw.Draw(f); W_, H_ = f.size

    def hbands(*cols, weights=None):
        ws = weights or [1] * len(cols); t = sum(ws); y0 = 0
        for col, k in zip(cols, ws):
            d.rectangle([0, y0, W_, y0 + H_ * k / t], fill=col); y0 += H_ * k / t

    def vbands(*cols):
        for i, col in enumerate(cols): d.rectangle([W_ * i / len(cols), 0, W_ * (i + 1) / len(cols), H_], fill=col)

    def nordic(field, cross, inner=None):
        d.rectangle([0, 0, W_, H_], fill=field); t = H_ / 5 if inner else H_ / 7; cx = W_ * 0.36
        d.rectangle([cx - t, 0, cx + t, H_], fill=cross); d.rectangle([0, H_ / 2 - t, W_, H_ / 2 + t], fill=cross)
        if inner:
            t2 = t / 2; d.rectangle([cx - t2, 0, cx + t2, H_], fill=inner); d.rectangle([0, H_ / 2 - t2, W_, H_ / 2 + t2], fill=inner)

    def union(box):
        x0, y0, x1, y1 = box; ww, hh = x1 - x0, y1 - y0
        d.rectangle(box, fill=BLUE)
        d.line([x0, y0, x1, y1], fill=WHITE, width=int(hh / 5)); d.line([x0, y1, x1, y0], fill=WHITE, width=int(hh / 5))
        d.line([x0, y0, x1, y1], fill=RED, width=int(hh / 15)); d.line([x0, y1, x1, y0], fill=RED, width=int(hh / 15))
        d.rectangle([x0 + ww / 2 - hh / 6, y0, x0 + ww / 2 + hh / 6, y1], fill=WHITE); d.rectangle([x0, y0 + hh / 3, x1, y1 - hh / 3], fill=WHITE)
        d.rectangle([x0 + ww / 2 - hh / 10, y0, x0 + ww / 2 + hh / 10, y1], fill=RED); d.rectangle([x0, y0 + hh * 0.4, x1, y1 - hh * 0.4], fill=RED)

    def disc(col, r, cx=None, cy=None):
        cx, cy = cx if cx is not None else W_ / 2, cy if cy is not None else H_ / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

    if c == "France": vbands(BLUE, WHITE, RED)
    elif c in ("Russia", "Finland"): hbands(WHITE, BLUE, RED)
    elif c == "Britain": union([0, 0, W_, H_])
    elif c == "Malta":   # the State Ensign of 1898–1923: the Blue Ensign, the badge a white and red shield on a white disc (Commons, Flag of Malta (1898–1923).svg)
        d.rectangle([0, 0, W_, H_], fill=BLUE); union([0, 0, W_ / 2, H_ / 2]); cx, cy, r = W_ * 0.74, H_ * 0.55, H_ * 0.30
        disc(WHITE, r, cx, cy); sw, sh = r * 0.62, r * 0.78
        shield = [(cx - sw, cy - sh), (cx + sw, cy - sh), (cx + sw, cy + sh * 0.2), (cx, cy + sh), (cx - sw, cy + sh * 0.2)]
        d.polygon(shield, fill=WHITE, outline=YELLOW, width=int(H_ / 40) + 1)
        d.polygon([(cx, cy - sh), (cx + sw, cy - sh), (cx + sw, cy + sh * 0.2), (cx, cy + sh)], fill=RED)
        d.line(shield + [shield[0]], fill=YELLOW, width=int(H_ / 40) + 1)
    elif c == "India":   # the Star of India Red Ensign, 1858–1947 (Commons, British Raj Red Ensign.svg): the badge drawn large, to be seen at this size
        d.rectangle([0, 0, W_, H_], fill=RED); union([0, 0, W_ / 2, H_ / 2]); cx, cy = W_ * 0.74, H_ * 0.55
        R, r0 = H_ * 0.32, H_ * 0.20   # the gold sunburst, a ring of rays, round the blue garter and the white star
        d.polygon([(cx + (R if k % 2 == 0 else r0) * math.cos(math.pi * k / 16), cy + (R if k % 2 == 0 else r0) * math.sin(math.pi * k / 16)) for k in range(32)], fill=(240, 180, 20))
        disc((30, 70, 160), H_ * 0.16, cx, cy)
        d.polygon([(cx + (H_ * 0.12 if k % 2 == 0 else H_ * 0.05) * math.cos(math.pi * k / 5 - math.pi / 2), cy + (H_ * 0.12 if k % 2 == 0 else H_ * 0.05) * math.sin(math.pi * k / 5 - math.pi / 2)) for k in range(10)], fill=WHITE)
    elif c == "Canada": d.rectangle([0, 0, W_, H_], fill=RED); union([0, 0, W_ / 2, H_ / 2]); disc((235, 225, 200), H_ / 7, W_ * 0.75, H_ * 0.6)
    elif c == "Austria-Hungary":
        d.rectangle([0, 0, W_ / 2, H_], fill=RED); d.rectangle([0, H_ / 3, W_ / 2, H_ * 2 / 3], fill=WHITE)
        d.rectangle([W_ / 2, 0, W_, H_ / 3], fill=RED); d.rectangle([W_ / 2, H_ * 2 / 3, W_, H_], fill=GREEN)
    elif c == "Germany": hbands(BLACK, WHITE, RED)
    elif c == "Italy":
        vbands(GREEN, WHITE, RED); sw = W_ / 9
        d.rectangle([W_ / 2 - sw, H_ / 2 - sw * 1.1, W_ / 2 + sw, H_ / 2 + sw * 1.1], fill=RED)
        d.rectangle([W_ / 2 - sw / 4, H_ / 2 - sw * 0.9, W_ / 2 + sw / 4, H_ / 2 + sw * 0.9], fill=WHITE); d.rectangle([W_ / 2 - sw * 0.8, H_ / 2 - sw / 4, W_ / 2 + sw * 0.8, H_ / 2 + sw / 4], fill=WHITE)
    elif c == "Belgium": vbands(BLACK, YELLOW, RED)
    elif c == "Sweden": nordic((0, 90, 160), YELLOW)
    elif c in ("Denmark", "Iceland"): nordic(RED, WHITE)
    elif c == "Norway": nordic(RED, WHITE, BLUE)
    elif c == "Switzerland":
        d.rectangle([0, 0, W_, H_], fill=RED); a, b = H_ * 0.12, H_ * 0.38
        d.rectangle([W_ / 2 - a, H_ / 2 - b, W_ / 2 + a, H_ / 2 + b], fill=WHITE); d.rectangle([W_ / 2 - b, H_ / 2 - a, W_ / 2 + b, H_ / 2 + a], fill=WHITE)
    elif c == "Spain": hbands(RED, YELLOW, RED, weights=[1, 2, 1])
    elif c == "Bulgaria": hbands(WHITE, GREEN, RED)
    elif c == "Japan": disc(RED, H_ * 0.3)
    elif c == "USA":
        for i in range(13): d.rectangle([0, H_ * i / 13, W_, H_ * (i + 1) / 13], fill=RED if i % 2 == 0 else WHITE)
        d.rectangle([0, 0, W_ * 0.4, H_ * 7 / 13], fill=BLUE)
        for i in range(5):
            for j in range(6): disc(WHITE, H_ / 60, W_ * 0.4 * (j + 0.5) / 6, H_ * 7 / 13 * (i + 0.5) / 5)
    elif c == "Mexico": vbands(GREEN, WHITE, RED); disc((140, 90, 40), H_ / 8)
    elif c == "Netherlands": hbands(RED, WHITE, BLUE)
    elif c == "Brazil":
        d.rectangle([0, 0, W_, H_], fill=GREEN); m = H_ * 0.1
        d.polygon([(m, H_ / 2), (W_ / 2, m), (W_ - m, H_ / 2), (W_ / 2, H_ - m)], fill=YELLOW); disc(BLUE, H_ * 0.25)
    elif c == "Chile":
        hbands(WHITE, RED); d.rectangle([0, 0, H_ / 2, H_ / 2], fill=BLUE); disc(WHITE, H_ / 12, H_ / 4, H_ / 4)
    elif c == "Greece":
        d.rectangle([0, 0, W_, H_], fill=(13, 94, 175)); t = H_ / 10
        d.rectangle([W_ / 2 - t, 0, W_ / 2 + t, H_], fill=WHITE); d.rectangle([0, H_ / 2 - t, W_, H_ / 2 + t], fill=WHITE)
    elif c == "Persia": hbands(GREEN, WHITE, RED); disc((210, 160, 30), H_ / 8)
    elif c == "Peru": vbands(RED, WHITE, RED)
    elif c == "Portugal":
        d.rectangle([0, 0, W_ / 2, H_], fill=BLUE); d.rectangle([W_ / 2, 0, W_, H_], fill=WHITE)
        d.rectangle([W_ / 2 - H_ / 7, H_ / 2 - H_ / 6, W_ / 2 + H_ / 7, H_ / 2 + H_ / 6], fill=(230, 230, 230), outline=RED, width=int(H_ / 25))
    else: return False
    f = f.resize((w, h), Image.LANCZOS)
    img.paste(f, (int(x), int(y)))
    ImageDraw.Draw(img).rectangle([x, y, x + w - 1, y + h - 1], outline=(150, 150, 150), width=1)
    return True


def people(version):
    """the people by their lines in the profiles, most first (the editor, 2026-11-08), with
    who has searched the web on whom; read from bingo-card/PEOPLE-LINES-vVERSION.tsv (tools/bingo-people-lines.py)"""
    rows = list(csv.DictReader(open(os.path.join(CARD, f"PEOPLE-LINES-v{version}.tsv"), encoding="utf-8"), delimiter="\t"))
    W, MAXH = WIDTH, 2300
    head, body, small, tiny = font(SERIF, 40), font(SERIF, 25), font(SERIF, 22), font(SERIF, 19)
    # Georgia has no polytonic Greek («Ἐμμανουὴλ Δραγούμης», the editor, 2026-11-09): a line of other names holding one is set in Times
    tiny_poly = font("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 19)
    num = font(FIGURES, 26)
    XN, XF, XNAME, XALT, XE, XM = 190, 206, 266, 640, 1370, 1370   # no web-search columns (the editor, 2026-11-08 15:2x)
    NAMEW, ALTW, LH = XALT - XNAME - 20, XE - 50 - XALT, 25

    def wrap(text, f, width, cap):
        out, cur = [], ""
        for wd in text.split(" "):
            t = (cur + " " + wd).strip()
            if f.getlength(t) <= width: cur = t
            else: out.append(cur); cur = wd
        if cur: out.append(cur)
        if len(out) > cap: out = out[:cap]; out[-1] = out[-1] + " …"
        return out
    def new_page(first):
        img = Image.new("RGB", (W, MAXH + 200), BAND); d = ImageDraw.Draw(img); y = 50
        if first:
            d.text((70, y), f"Kiuj havas kiom da linioj en la profiloj: {len(rows)} personoj", font=head, fill=(60, 80, 50)); y += 52
            for t in ("Laŭ la nombro de la propraj linioj de ĉiu en la profiloj (la linioj de alia samnomulo forlasitaj); ĉe la aliaj nomformoj",
                      "tiuj el la registroj kaj tiuj, per kiuj la linioj nomas lin.",
                      "«+N ambig.»: la linioj de la ambigua dosiero de la familia nomo, eble liaj. Flagoj de 1906, simpligitaj."):
                d.text((70, y), t, font=small, fill=DATE); y += 30
            y += 14
        d.text((XN, y), "linioj", font=small, fill=DATE, anchor="ra"); d.text((XNAME, y), "nomo", font=small, fill=DATE)
        d.text((XALT, y), "aliaj nomformoj", font=small, fill=DATE)
        y += 36; d.line([70, y, W - 40, y], fill=(150, 150, 150), width=2)
        return img, d, y + 12
    pages, (img, d, y) = [], new_page(True)
    for r in rows:
        name = wrap(r["name"], body, NAMEW, 3)
        alts = [re.sub(r" \[[^\]]*\]$", "", a) for a in r["alt"].split(" | ") if a]
        alt = wrap(" · ".join(alts), tiny, ALTW, 3) if alts else []
        h = max(len(name) * 30, len(alt) * LH, 62 if int(r.get("ambiguous") or 0) else 34) + 12
        if y + h > MAXH:
            pages.append(img.crop((0, 0, W, y + 30))); img, d, y = new_page(False)
        d.text((XN, y), f"{int(r['lines']):,}".replace(",", " "), font=num, fill=INK, anchor="ra")
        if int(r.get("ambiguous") or 0):   # the surname's ambiguous lines, which may be his (2026-11-08)
            d.text((XN, y + 32), f"+{r['ambiguous']} ambig.", font=tiny, fill=DATE, anchor="ra")
        flag(img, r["country"], XF, y + 2, 44, 29)
        for i, t in enumerate(name): d.text((XNAME, y + i * 30), t, font=body, fill=INK)
        for i, t in enumerate(alt): d.text((XALT, y + 3 + i * LH), t, font=tiny_poly if re.search("[ἀ-῿]", t) else tiny, fill=DATE)
        y += h
        d.line([70, y - 6, W - 40, y - 6], fill=(225, 222, 210), width=1)
    pages.append(img.crop((0, 0, W, y + 30)))
    for i, pg in enumerate(pages, 1):
        f = os.path.join(OUT, f"nombroj-5-{i}.jpg"); pg.save(f, quality=90, optimize=True); print(f, pg.size, flush=True)


def counted(rows):
    """the people carrying each mark, a person once; the two 🟠 apart by year; a † only where no ‡"""
    out = {}
    def n(test): return sum(1 for r in rows if test(tokens(r["tags_in_sequence"])))
    def has(*ms): return lambda t: any(m in ms for m, _, _ in t)
    def own(pred): return lambda t: any(m == "🟠" and pred(int(re.sub(r"\D", "", y) or 0)) for m, y, _ in t)
    for m, _ in KEY:
        if m not in ("🟠", "†", "‡"): out[m] = n(has(m))
    out["🟠<"], out["🟠>"] = n(own(lambda y: y < 1908)), n(own(lambda y: y >= 1908))
    out["‡"] = n(has("‡"))
    # returned before 1908: away and back between 1894 and the schism (the editor, 2026-11-08 14:4x
    #)
    # counted as back: a 🟢 before 1908, or a 🟩 before 1908 after a going-away mark (⬜ ⬛ 🟠 🟧 🟦) that followed the first 🟩 (Berthelot's
    # «🟩 1899 → 🟠 1904 → 🟩 1905»)
    def back_before_1908(t):
        joined = away = False
        for m, y, _ in t:
            Y = int(re.sub(r"\D", "", y)[:4] or 0)
            if m == "🟢" and 0 < Y < 1908: return True
            if m == "🟩":
                if away and 0 < Y < 1908: return True
                joined = True
            elif joined and m in ("⬜", "⬛", "🟠", "🟧", "🟦") and 0 < Y < 1908: away = True
        return False
    out["🟢<"] = n(back_before_1908)
    out["†"] = n(lambda t: any(m == "†" and not y.startswith("≥") for m, y, _ in t) and not any(m == "‡" for m, _, _ in t))
    out["†≥"] = n(lambda t: any(m == "†" and y.startswith("≥") for m, y, _ in t))
    camp = lambda t: has("🟦", "💙", "🟧", "🧡")(t) or own(lambda y: y >= 1908)(t)
    out["camp"] = n(camp)
    by = {}
    for r in rows:
        c = re.sub(r" \(.*", "", r["country"])
        t = tokens(r["tags_in_sequence"])
        d = by.setdefault(c, [0, 0, 0, 0, 0, 0])
        for i, v in enumerate((True, has("🟦", "💙")(t), has("🟧", "🧡")(t) or own(lambda y: y >= 1908)(t), camp(t), has("🔴", "⭕")(t), has("‡")(t))): d[i] += bool(v)
    return out, by


def tables(version):
    """the card's counts, one page a list, the marks drawn as on the plates (the editor, 2026-11-06). Counted from the card itself, so a hand edit to a mark is counted"""
    album, supp, lk = read_card(version), read_card(version, "-supplement"), read_card(version, "-lk1905")
    sets = [("La albumo de Schuck", album), ("La suplemento: nomitaj de Schuck kaj de Bein, sen portreto", supp), ("La Lingva Komitato ĝis 1907, ekster la aliaj listoj", lk), ("Ĉiuj kvar listoj kune", album + supp + lk)]
    LABEL = dict(KEY)
    ORDER = ["🟩", "🟢", "🟢<", "🟪", "💛", "💚", "🟨", "🟦", "💙", "🟧", "🧡", "🟠<", "🟠>", "⬜", "⬛", "🔴", "⭕", "⭘", "Ⓚ", "Ⓐ", "◈", "◐", "‡", "†", "†≥"]
    S, W, ROW = 32, WIDTH, 48
    head, body, small = font(SERIF, 40), font(SERIF, 28), font(SERIF, 24)
    num = font(FIGURES, 30)
    for n, (title, rows) in enumerate(sets, 1):
        out, by = counted(rows)
        countries = sorted(by, key=lambda c: (-by[c][0], COUNTRY_EO.get(c, c)))
        h = 150 + ROW * (len(ORDER) + 1) + 120 + 44 * (len(countries) + 1) + 90
        img = Image.new("RGB", (W, h), BAND); d = ImageDraw.Draw(img)
        d.text((70, 60), f"{title}: {len(rows)} personoj", font=head, fill=(60, 80, 50))
        d.text((70, 104), "Persono povas porti plurajn signojn.", font=small, fill=DATE)
        y = 150
        for k in ORDER:
            m = k[0]
            glyph(d, m, 70, y + 4, S)
            label = {"🟢<": "revenis antaŭ 1908", "🟠<": "kreis propran planlingvon, antaŭ 1908", "🟠>": "kreis propran planlingvon, ekde 1908", "‡": "mortis ĝis fino de 1908", "†": "mortis post 1908, jaro konata", "†≥": "vivis almenaŭ ĝis tiu jaro, morto ne trovita"}.get(k, LABEL.get(k, ""))
            d.text((130, y + 6), label, font=body, fill=INK)
            d.text((W - 90, y + 4), str(out[k]), font=num, fill=INK, anchor="ra")
            y += ROW
        d.line([70, y + 4, W - 70, y + 4], fill=(120, 120, 120), width=2)
        d.text((70, y + 12), "ĉe iu ajn alia lingvo: Ido aŭ alia, aliĝinte, simpatiante aŭ kreinte (ekde 1908)", font=body, fill=INK)
        d.text((W - 90, y + 10), str(out["camp"]), font=num, fill=INK, anchor="ra")
        y += ROW + 70
        cols = [(620, "personoj"), (760, "Ido"), (910, "alia lingvo"), (1060, "iu ajn"), (1200, "forstrekitaj"), (1320, "‡")]
        d.text((70, y), "lando (limoj de 1906)", font=small, fill=DATE)
        for cx, c in cols: d.text((cx, y), c, font=small, fill=DATE, anchor="ra")
        y += 40
        for c in countries:
            flag(img, c, 70, y + 2, 42, 28)   # the flag of 1906 (the editor, 2026-11-08)
            d.text((126, y), COUNTRY_EO.get(c, c), font=body, fill=INK)
            for (cx, _), v in zip(cols, by[c]): d.text((cx, y), str(v), font=num, fill=INK, anchor="ra")
            y += 44
        f = os.path.join(OUT, f"nombroj-{n}.jpg")
        img.crop((0, 0, W, y + 50)).save(f, quality=90, optimize=True)
        print(f, title, {k: out[k] for k in ("🟢", "🟦", "💙", "🟧", "🧡", "🟠<", "🟠>", "⬜", "⬛", "🔴", "⭕", "⭘", "🟪", "‡", "†", "Ⓚ", "Ⓐ", "◈", "◐", "camp")}, flush=True)


def legend():
    s, rowh = 40, 64
    img = Image.new("RGB", (1400, 220 + rowh * ((len(KEY) + 1) // 2)), BAND)
    d = ImageDraw.Draw(img)
    size = 30
    while max(font(SERIF, size).getlength(t) for _, t in KEY) > 690 - s - 40: size -= 1   # the longest meaning stays in its column
    f = font(SERIF, size)
    for i, (m, t) in enumerate(KEY):
        x, y = 30 + (i % 2) * 690, 24 + (i // 2) * rowh
        glyph(d, m, x, y, s)
        d.text((x + s + 22, y + s / 2), t, font=f, fill=INK, anchor="lm")
    # qls (the editor 2026-11-11 03:1x): the
    # ConLang Code Registry's code for Latino sine Flexione, from ISO 639's range for local use (qaa–qtz); credited in the preface
    d.text((30, img.height - 118), "oranĝa kvadrato aŭ koro post 1908 sen kodo: Occidental  ·  nov Novial  ·  qls Latino sine Flexione", font=f, fill=INK)
    d.text((30, img.height - 62), "idn Idiom Neutral  ·  jbo Loĵbano  ·  tlh Klingona  ·  (qls: ConLang Code Registry)", font=f, fill=INK)
    d.text((30, img.height - 174), "≤ ĝis tiu jaro  ·  ≥ almenaŭ ĝis tiu jaro  ·  sen jaro: la dato ne estas trovita", font=f, fill=INK)
    img.save(os.path.join(OUT, "key.png"), optimize=True)
    print(os.path.join(OUT, "key.png"), img.size)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("version", nargs="?"); ap.add_argument("--plates", action="store_true"); ap.add_argument("--rest", action="store_true")
    ap.add_argument("--cut", action="store_true"); ap.add_argument("--legend", action="store_true"); ap.add_argument("--tables", action="store_true"); ap.add_argument("--people", action="store_true"); ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.cut: cut()
    if a.legend: legend()
    if a.plates: plates(a.version, {int(x) for x in a.only.split(",") if x})
    if a.rest: rest(a.version)
    if a.tables: tables(a.version)
    if a.people: people(a.version)


if __name__ == "__main__":
    main()
