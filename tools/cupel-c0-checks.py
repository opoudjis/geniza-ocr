#!/usr/bin/env python3
r"""cupel-c0-checks — the run sheet's C0 checks on a batch's sources, as one box-free call (2026-10-28).

    python3 tools/cupel-c0-checks.py --full-list <full PDF list> --out <report.md>
        [--folder <dir> …] [--pdf <file> …] [--images <dir> …]
        [--title "<words>" …] [--lacuna "<term>" …]

WHY (the editor, 2026-10-28 22:0x, before cupel19b's C0: the checks built as a tool rather than run with a box each;
the run sheet's at C0). The batch's PDFs are every *.pdf in each --folder, and each --pdf. For each:
  registered    its file name in a .md under geniza/ or interglossa/, or its folder named in sources/_INVENTORY.md
                («`<folder>/…»);
  name          no spaces at the ends of the stem; the stem not on the full list, not a folder in sources/ocr-rendersearch/;
                «X (k).pdf» flagged as a browser piece (C0's ÖNB/ANNO pieces: tools/anno-pieces.py);
  duplicate     not on the full list by name; then by size, then SHA-1, against every PDF on the full list; and within
                the batch (two files the same, as Lublin's two edition numbers);
and once for the batch:
  lacunae       every row of ocr/method/LACUNAE.tsv holding a --lacuna term (case folded);
  title         each --title as a phrase (its words in order, case folded, across line breaks) in page-0001.txt and
                page-0002.txt of every reading folder; all its words in a file name of the full list: hits to look at
                (rule 15); a library cover sheet withdrawn from the readings (2026-11-03) is read from the store,
                `ocr_withdrawn.library_texts()` (2026-11-04, the editor: the metadata retained);
  frames        (A) placed scans: each --images folder's image files and their frames (PIL), for C2's count.
Reads only; writes --out, created new (refused if it exists). Exit 1 if a PDF is unregistered, a stem collides, or a
duplicate is found (a stop for the editor); 0 otherwise. Disk and locks stay their own calls (C0).
"""
import argparse, collections, hashlib, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr_withdrawn as WD   # the withdrawn library pages' metadata (2026-11-04)

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.normpath(os.path.join(HERE, "..", "published", "heterophony-resources", "geniza"))
IG = os.path.normpath(os.path.join(G, "..", "interglossa"))
R = os.path.join(G, "sources", "ocr-rendersearch")
PIECE = re.compile(r"^(.*) \((\d+)\)\.pdf$")


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def md_text():
    out = []
    for root in (G, IG):
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if not x.endswith(".noindex") and x not in ("ocr-rendersearch", "ocr-rendersearch-all",
                                                                                 "ocr-preferred", "ocr-work")]
            out += [os.path.join(d, f) for f in files if f.endswith(".md")]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full-list", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--folder", action="append", default=[]); ap.add_argument("--pdf", action="append", default=[])
    ap.add_argument("--images", action="append", default=[])
    ap.add_argument("--title", action="append", default=[]); ap.add_argument("--lacuna", action="append", default=[])
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"exists: {a.out}")
    pdfs = list(a.pdf)
    for d in a.folder:
        pdfs += sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".pdf"))
    full = [l.strip() for l in open(a.full_list, encoding="utf-8") if l.strip()]
    full_abs = [p if os.path.isabs(p) else os.path.join(HERE, "..", p) for p in full]
    full_names = collections.Counter(os.path.basename(p) for p in full)
    full_stems = {os.path.basename(p)[:-4] for p in full}
    rfolders = set(os.listdir(R))
    inv = open(os.path.join(G, "sources", "_INVENTORY.md"), encoding="utf-8").read()
    mds = md_text()
    names = {os.path.basename(p) for p in pdfs}
    named_in = collections.defaultdict(list)
    for m in mds:
        try:
            t = open(m, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n in names:
            if n in t:
                named_in[n].append(os.path.relpath(m, G))
    stops, lines = [], [f"# C0 checks: {len(pdfs)} PDFs", "", f"Full list `{a.full_list}` ({len(full)} PDFs).", ""]
    # per PDF
    by_size = collections.defaultdict(list)
    for p in full_abs:
        try:
            by_size[os.path.getsize(p)].append(p)
        except OSError:
            pass
    batch_sha = collections.defaultdict(list)
    lines += ["## Per PDF", "", "| PDF | registered | name | duplicate |", "|---|---|---|---|"]
    pieces = collections.defaultdict(list)
    STOP_NAME = ("SPACES AT THE ENDS", "STEM ON THE FULL LIST", "STEM A FOLDER IN ocr-rendersearch")
    for p in pdfs:
        n, folder = os.path.basename(p), os.path.basename(os.path.dirname(p))
        stem = n[:-4]
        # the census lists every file on disk, so naming a file there registers nothing
        named = [m for m in named_in[n] if "HOLDINGS-CENSUS" not in m]
        reg = (f"folder `{folder}/` in _INVENTORY.md" if f"`{folder}/" in inv else
               f"named in {named[0]}" if named else "NO")
        nm = [x for x, bad in zip(STOP_NAME, (stem != stem.strip(), stem in full_stems, stem in rfolders)) if bad]
        m = PIECE.match(n)
        if m:
            nm.append(f"browser piece {m.group(2)} of «{m.group(1)}.pdf»")
            pieces[os.path.join(folder, m.group(1))].append(n)
        dup = ["NAME ON THE FULL LIST"] if full_names[n] else []
        sz, h = os.path.getsize(p), sha1(p)
        batch_sha[h].append(n)
        dup += [f"SHA-1 = {os.path.relpath(q, G)}" for q in by_size.get(sz, [])
                if os.path.abspath(q) != os.path.abspath(p) and sha1(q) == h]
        if reg == "NO" or dup or any(x in STOP_NAME for x in nm):
            stops.append(n)
        lines.append(f"| {folder}/{n} | {reg} | {'; '.join(nm) or 'ok'} | {'; '.join(dup) or 'none'} |")
    twins = [v for v in batch_sha.values() if len(v) > 1]
    lines += ["", "## Within the batch, the same file twice", ""] + ([f"- {', '.join(v)}" for v in twins] or ["none"])
    stops += [x for v in twins for x in v]
    lines += ["", "## Browser pieces (C0: `anno-pieces.py rename`, then `join`)", ""]
    lines += [f"- `{k}.pdf`: {', '.join(sorted(v))}" for k, v in sorted(pieces.items())] or ["none"]
    # lacunae
    lac = [l.rstrip("\n") for l in open(os.path.join(G, "ocr", "method", "LACUNAE.tsv"), encoding="utf-8") if not l.startswith("#")]
    lines += ["", "## Lacunae register rows", ""]
    for term in a.lacuna:
        hits = [l for l in lac[1:] if term.lower() in l.lower()]
        lines += [f"**{term}**: {len(hits)} row(s)"] + [f"- {h[:300]}" for h in hits] + [""]
    # titles
    lines += ["## Titles (rule 15: a hit that is the same work is a second copy; a mention is not)", ""]
    for title in a.title:
        words = [w.lower() for w in title.split()]
        # the title as a phrase (its words in order, across line breaks), not its words anywhere on the page:
        # «Esperanto» and «monthly» apart are on the cover of every American monthly
        phrase = re.compile(r"\W+".join(map(re.escape, words)), re.I)
        hits = []
        for f in sorted(rfolders):
            lib = WD.library_texts(f)   # an ÖNB cover sheet withdrawn 2026-11-03: its metadata read from the store
            for n_, pg in ((1, "page-0001.txt"), (2, "page-0002.txt")):
                fp = os.path.join(R, f, pg)
                if os.path.isfile(fp) or n_ in lib:
                    t = open(fp, encoding="utf-8", errors="replace").read() if os.path.isfile(fp) else ""
                    if not t.strip() and n_ in lib: t = lib[n_]
                    m = phrase.search(t)
                    if m:    # with 70 characters either side, to tell a copy from a mention
                        ctx = re.sub(r"\s+", " ", t[max(0, m.start() - 70):m.end() + 70])
                        hits.append(f"{f}/{pg}: «…{ctx}…»")
        fn = [os.path.basename(p) for p in full if all(w in os.path.basename(p).lower() for w in words)]
        lines += [f"**{title}**: {len(hits)} reading page(s), {len(fn)} file name(s)"]
        lines += [f"- page: {h}" for h in hits[:60]] + [f"- name: {x}" for x in fn[:60]] + [""]
    # frames
    if a.images:
        from PIL import Image
        lines += ["## (A) frames", ""]
        for d in a.images:
            fs = sorted(f for f in os.listdir(d) if f.lower().endswith((".tif", ".tiff", ".png", ".jpg", ".jpeg")))
            n = sum(getattr(Image.open(os.path.join(d, f)), "n_frames", 1) for f in fs)  # a JPEG has no n_frames: one frame (2026-11-06, failure map R106)
            lines.append(f"- `{d}`: {len(fs)} files, {n} frames")
    lines += ["", f"**Stops: {len(set(stops))}**" + (f": {', '.join(sorted(set(stops)))}" if stops else "")]
    open(a.out, "x", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"{len(pdfs)} PDFs; stops {len(set(stops))}; pieces {sum(len(v) for v in pieces.values())} in {len(pieces)}; "
          f"lacunae terms {len(a.lacuna)}; titles {len(a.title)} → {a.out}")
    sys.exit(1 if stops else 0)


if __name__ == "__main__":
    main()
