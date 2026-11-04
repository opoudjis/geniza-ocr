#!/usr/bin/env python3
"""The Ido name roster: the Idists the dowse roster should know, from sources that are not OCR of small capitals (2026-10-27;
the editor: the roster built, its names from Wikipedia and other born-digital sources; the 1909–1910
Ido address book and the Ido-Zürich directories not a basis, being OCR of small capitals, which would be circular).

    tools/ido-name-roster.py [--write]

Reads, and merges by surname:
  - io.wikipedia's «Kategorio:Idisti» (profiles/SCOPE-REGISTER-CANDIDATES-IOWIKI-2026-10-14.tsv, harvested from the dump
    sources/web-2026-10-14-scope-register/iowiki-20261001-pages-articles.xml.bz2: name, birth, death);
  - eo.wikipedia's «Kategorio:Idistoj» (the eo dump of the same day: each page's title, its birth and death years);
  - Miles's eye-decoded Progreso roster (tools/progreso-roster/progreso_curated.py, 2026-09-13: OFFICES, the Uniono's
    Direktanta Komitato, Akademio, riprezentanti by period; EVENTS, elections and the like), the names as its keys;
  - the scope register's Idists (profiles/SCOPE-REGISTER.tsv, movement Ido), for their verdict and joining date.
For each surname: its forms and forenames, birth and death, which sources name it, an office in Progreso if any, the scope
verdict, and whether the dowse roster (the latest dowse/ROSTER-FULL-CROSS-ARC-*.txt) already has it.
Writes, with --write, dowse/IDO-NAMES-<tag>.tsv and dowse/IDO-NAMES-<tag>.md (the counts, and the names the roster
lacks), refusing to overwrite; --tag defaults to today. Ido-vivo's born-digital PDFs are not read yet.

Left out, and listed as left out: a person born after 1912 (too young to join before 1931, the dowse's Ido scope; the
wikis' modern Idists), and a «name» with no surname of letters (the io.wikipedia row «edito (1981»).

    tools/ido-name-roster.py --measure FACTS-FILE [--write]

Measures what the roster accounts for in a dowse facts file (profiles/by-source/<source>-dowse.md): every head («$$$ HEAD
$$$») not on the dowse roster is (a) an Ido surname the roster lacks, (b) near an Ido surname (the ratio of difflib's
SequenceMatcher ≥ 0.75 on the surnames, raw or with the OCR's small-capital confusions undone: 0→O, 1→I, 5→S, 6→G, 8→B,
X→N), or (c) neither. With --write, dowse/IDO-NAMES-<tag>-MEASURE-<source>.md, every head of (a) and (b) with its Ido
name and line count, refusing to overwrite. A measure only: nothing is changed in the file (that is the ungarbler's job,
after its dry run and review). Ezri."""
import argparse, bz2, collections, csv, datetime, difflib, glob, importlib.util, os, re, sys, unicodedata
BORN_MAX = 1912
OCR_SC = str.maketrans({"0": "o", "1": "i", "5": "s", "6": "g", "8": "b", "x": "n"})
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
PARTICLES = {"de", "di", "van", "von", "la", "le", "du", "del", "der", "den", "ten", "ter", "da", "dos", "des"}

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).strip("-")

def surname(display):
    """The surname of a display name, with its particle («Louis de Beaufront» → «de Beaufront»; «BAUDOUIN-DE-COURTENAY» as is)."""
    d = re.sub(r"\s*\(.*?\)", "", display).strip()
    if d.isupper() or " " not in d: return d.replace("-", " ").title() if d.isupper() else d
    ws = d.split()
    out = [ws[-1]]
    i = len(ws) - 2
    while i > 0 and ws[i].lower() in PARTICLES: out.insert(0, ws[i]); i -= 1
    return " ".join(out)

def eowiki_idists():
    """(title, born, died) of every eo.wikipedia page in «Kategorio:Idistoj»."""
    p = os.path.join(G, "sources", "web-2026-10-14-scope-register", "eowiki-20261001-pages-articles.xml.bz2")
    out, title, buf = [], None, []
    with bz2.open(p, "rt", encoding="utf-8") as fh:
        for l in fh:
            if "<title>" in l: title = re.sub(r".*<title>(.*)</title>.*", r"\1", l.strip()); buf = []; continue
            buf.append(l)
            if "</page>" in l:
                t = "".join(buf)
                if "[[Kategorio:Idistoj" in t and ":" not in title:
                    b = re.search(r"(?:naskiĝ\w*|naskita)[^\n|]{0,40}?(1[789]\d\d)", t); d = re.search(r"(?:mort\w*)[^\n|]{0,40}?(1[89]\d\d|20\d\d)", t)
                    out.append((title, b.group(1) if b else "", d.group(1) if d else ""))
                buf = []
    return out

def on_roster(k, labels):
    return k if k in labels else next((x for x in sorted(labels) if x.startswith(k + "-")), "")

def measure(path, rows, labels, rp, tag, write):
    """Sort the heads of a facts file the dowse roster lacks into (a) an Ido surname the roster lacks, (b) near one, (c) neither."""
    heads = collections.Counter()
    for l in open(path, encoding="utf-8"):
        m = re.match(r"- \$\$\$ (.+?) \$\$\$", l)
        if m: heads[m.group(1).strip()] += 1
    ido = {x[0]: x for x in rows}
    lacking = {x[0] for x in rows if not x[9]}
    cls = {"a": [], "b": [], "c": []}
    for h, n in heads.items():
        k = slug(re.sub(r"\s*\(.*?\)", "", h))
        if not k or on_roster(k, labels): continue
        if k in lacking: cls["a"].append((h, n, ido[k][2], 1.0)); continue
        best, who = 0.0, None
        for i in ido:
            if abs(len(i) - len(k)) > 2: continue
            r = max(difflib.SequenceMatcher(None, k, i).ratio(), difflib.SequenceMatcher(None, k.translate(OCR_SC), i).ratio())
            if r > best: best, who = r, i
        (cls["b"] if best >= 0.75 else cls["c"]).append((h, n, ido[who][2] if who else "", best))
    src = re.sub(r"-dowse\.md$", "", os.path.basename(path))
    tot = lambda c: (len(cls[c]), sum(x[1] for x in cls[c]))
    nh, nl = sum(tot(c)[0] for c in cls), sum(tot(c)[1] for c in cls)
    summary = (f"{src}: {nh} heads not on the dowse roster ({os.path.basename(rp)}), {nl} lines; "
               f"(a) an Ido surname the roster lacks: {tot('a')[0]} heads, {tot('a')[1]} lines; "
               f"(b) near an Ido surname: {tot('b')[0]} heads, {tot('b')[1]} lines; (c) neither: {tot('c')[0]} heads, {tot('c')[1]} lines")
    print(summary)
    if not write: return
    out = os.path.join(G, "dowse", f"IDO-NAMES-{tag}-MEASURE-{src}.md")
    if os.path.exists(out): sys.exit("refusing to overwrite: " + out)
    with open(out, "x", encoding="utf-8") as fh:
        fh.write(f"# The Ido name roster against {src} ({tag})\n\n`[GENERATED by tools/ido-name-roster.py --measure. Do not hand-edit — re-run it.]`\n\n")
        fh.write(summary + f". The roster: `IDO-NAMES-{tag}.tsv`. A measure only: no line is changed.\n\n")
        for c, title in (("a", "(a) An Ido surname the dowse roster lacks"), ("b", "(b) Near an Ido surname (ratio ≥ 0.75)")):
            fh.write(f"## {title}\n\n| head | lines | Ido name | ratio |\n|---|---|---|---|\n")
            for h, n, full, r in sorted(cls[c], key=lambda x: (-x[1], x[0])):
                fh.write(f"| {h} | {n} | {full.replace(' | ', ' / ')} | {r:.2f} |\n")
            fh.write("\n")
        fh.write(f"## (c) Neither: the {tot('c')[0]} heads with the most lines (the rest in the count above)\n\n| head | lines |\n|---|---|\n")
        for h, n, _, _ in sorted(cls["c"], key=lambda x: (-x[1], x[0]))[:100]: fh.write(f"| {h} | {n} |\n")
    print("wrote", os.path.relpath(out, ROOT))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true"); ap.add_argument("--tag", default=datetime.date.today().isoformat())
    ap.add_argument("--measure", metavar="FACTS-FILE"); a = ap.parse_args()
    outs = [os.path.join(G, "dowse", f"IDO-NAMES-{a.tag}.{x}") for x in ("tsv", "md")]
    if a.write and not a.measure and any(os.path.exists(p) for p in outs): sys.exit("refusing to overwrite: " + ", ".join(p for p in outs if os.path.exists(p)))
    rec = collections.defaultdict(lambda: {"forms": set(), "full": set(), "born": "", "died": "", "src": set(), "office": [], "verdict": "", "joined": ""})
    dropped = []
    def add(display, src, born="", died=""):
        s = surname(display); k = slug(s)
        if not k or len(k) < 3 or not re.fullmatch(r"[^\W\d_][^\W\d_'’ .-]*(?:[ '’.-]+[^\W\d_]+)*", s):
            dropped.append((display, src, "no surname of letters")); return None
        r = rec[k]; r["forms"].add(s); r["full"].add(re.sub(r"\s*\(.*?\)", "", display).strip()); r["src"].add(src)
        r["born"] = r["born"] or (born or ""); r["died"] = r["died"] or (died or "")
        return r
    for row in csv.DictReader((l for l in open(os.path.join(G, "profiles", "SCOPE-REGISTER-CANDIDATES-IOWIKI-2026-10-14.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        add(row["name"], "io.wikipedia", row.get("born", ""), row.get("died", ""))
    for title, b, d in eowiki_idists(): add(title, "eo.wikipedia", b, d)
    spec = importlib.util.spec_from_file_location("pc", os.path.join(ROOT, "tools", "progreso-roster", "progreso_curated.py"))
    pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
    for body, office, key, d0, d1, *_ in pc.OFFICES:
        r = add(key, "Progreso (Miles, by eye)")
        if r is not None: r["office"].append(f"{office}, {body}, {d0}–{d1}")
    for ev in pc.EVENTS:
        if len(ev) > 1 and isinstance(ev[1], str): add(ev[1], "Progreso (Miles, by eye)")
    for row in csv.DictReader((l for l in open(os.path.join(G, "profiles", "SCOPE-REGISTER.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
        if "Ido" not in (row.get("movement") or ""): continue
        r = add(row["name"], "the scope register")
        if r is not None: r["verdict"] = row.get("verdict", ""); r["joined"] = (row.get("joined_io") or "").strip()
    rp = sorted(glob.glob(os.path.join(G, "dowse", "ROSTER-FULL-CROSS-ARC-*.txt")))[-1]
    labels = {l.split(" | ")[0].strip() for l in open(rp, encoding="utf-8") if l.strip() and not l.startswith("#")}
    rows = []
    for k, r in sorted(rec.items()):
        if r["born"].isdigit() and int(r["born"]) > BORN_MAX and not r["office"]:
            dropped.append((" / ".join(sorted(r["full"])), "; ".join(sorted(r["src"])), f"born {r['born']}")); continue
        full = sorted(r["full"]); mixed = [f for f in full if not f.isupper()]
        rows.append([k, " | ".join(sorted(r["forms"])), " | ".join(mixed or full), r["born"], r["died"], "; ".join(sorted(r["src"])),
                     "; ".join(r["office"]), r["verdict"], r["joined"], on_roster(k, labels)])
    if a.measure: return measure(a.measure, rows, labels, rp, a.tag, a.write)
    n = len(rows); lack = [x for x in rows if not x[9]]
    by = collections.Counter(s for x in rows for s in x[5].split("; "))
    print(f"{n} surnames; on the dowse roster {n - len(lack)}, not on it {len(lack)}; left out {len(dropped)}; by source: " + ", ".join(f"{s} {c}" for s, c in by.most_common()))
    if not a.write: return
    with open(outs[0], "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["key", "surname forms", "full names", "born", "died", "sources", "office in Progreso", "scope verdict", "joined Ido", "on the dowse roster"])
        w.writerows(rows)
    with open(outs[1], "x", encoding="utf-8") as fh:
        fh.write(f"# The Ido name roster ({a.tag})\n\n`[GENERATED by tools/ido-name-roster.py. Do not hand-edit — re-run it.]`\n\n")
        fh.write(f"**{n} surnames;** on the dowse roster ({os.path.basename(rp)}) {n - len(lack)}, **not on it {len(lack)}**; left out {len(dropped)} (below). By source: " + ", ".join(f"{s} {c}" for s, c in by.most_common()) + f". Every row: `{os.path.basename(outs[0])}`.\n\n")
        fh.write("## Not on the dowse roster\n\n| surname | full names | born–died | sources | office in Progreso |\n|---|---|---|---|---|\n")
        for x in lack: fh.write(f"| {x[1].replace(' | ', ' / ')} | {x[2].replace(' | ', ' / ')} | {x[3]}–{x[4]} | {x[5]} | {x[6]} |\n")
        fh.write(f"\n## Left out\n\nBorn after {BORN_MAX} (too young to join Ido before 1931) with no office in *Progreso*, or no surname of letters.\n\n| name | sources | why |\n|---|---|---|\n")
        for d, s, why in sorted(dropped): fh.write(f"| {d} | {s} | {why} |\n")
    for p in outs: print("wrote", os.path.relpath(p, ROOT))

if __name__ == "__main__":
    main()
