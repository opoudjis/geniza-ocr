#!/usr/bin/env python3
"""Each item's side, for the hostile-witness label (ocr/method/HOSTILE-WITNESS-LABEL-PROPOSAL-2026-10-13.md; the editor,
2026-10-15).

    tools/item-sides.py [--out FILE]

The side of an item is the auxiliary language it is written in, by the language table (geniza/OCR-TEXT-LANGUAGES-
<latest>.tsv): only a language with strong evidence counts (the gate, a declaration or a ruling; a weak «look» hit
alone does not). Esperanto or Ido gives that side; Occidental, Novial, Latino sine flexione (and «interlingua», Peano's
name for it before 1939) give the side «hostile», which is the other side to everyone. Both Esperanto and Ido: «mixed»,
no side, listed for a ruling. No auxiliary language: «neutral», no label. The side is by item, not by run: a run can
change language (L'Espérantiste goes over to Ido issue by issue from 1912; Mondo is Esperanto in 1912, Ido from 1915,
Novial from 1930). The born-digital texts are not in the language table: their side comes from BD_LANG below, by run,
checked by hand. Prints the counts; --out writes item → side (TSV), create-only. Ezri, 2026-10-15."""
import argparse, glob, os, re, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
HOSTILE = {"occidental", "novial", "latino-sine-flexione", "interlingua"}
SIDE = {"esperanto": "Esperanto", "ido": "Ido"}
# born-digital runs, by the item key's start (checked by hand 2026-10-15): the language of the run
BD_LANG = {"cosmoglotta": "hostile", "kosmoglott": "hostile", "tekstaro-": "Esperanto", "bd-tekstaro": "Esperanto"}

def override(item, side):
    """The editor's rulings on items the language cannot decide. La Belga Sonorilo printed both languages after its turn
    (2026-10-15: approved to, the turn announced in no. 92 of
    13 Sept 1908; belga-sonorilo-fullread-1908turn-2026-09-10.md § 0c, § 2)."""
    m = re.match(r"LaBelgaSonorilo_\d{4}_n(\d+)_", item)
    if m and side == "mixed": return ("Esperanto" if int(m.group(1)) < 92 else "Ido"), "the editor's ruling: Ido from no. 92 (13 Sept 1908)"
    # the year volumes (2026-10-16, Ezri, checking the «year volume spanning a turn» fault of D6 point 8): the volume
    # named «1908» is the seventh year, opening with no. 92 itself («13 Septembre 1908 … 92ª NUMERO … SEPESMA YARO,
    # Unesma numero», its page 1), so wholly after the turn; the language table had given it Esperanto
    if item == "belgaSonorilo.1908": return "Ido", "the editor's ruling (Ido from no. 92): the volume opens with no. 92, the seventh year"
    return side, None

EO_W = re.compile(r"\b(estas|kaj|estis|ankaŭ|ĉar|tiu|kiu|ĝi|ŝi|al la|de la)\b", re.I)
IO_W = re.compile(r"\b(esas|ed|esis|anke|nam|ca|qua|olu|elu|dil|al la)\b", re.I)
def bd_side(path):
    """A born-digital text's language by its marker words (2026-10-16): Esperanto where its words outnumber Ido's three
    to one and there are at least 50, Ido the reverse; else none (a Russian text, a short one, or a mixed one)."""
    try: t = open(path, encoding="utf-8", errors="replace").read()
    except OSError: return None
    eo, io = len(EO_W.findall(t)) + t.count("ĉ") + t.count("ŝ") + t.count("ŭ"), len(IO_W.findall(t))
    if eo >= 50 and eo >= 3 * io: return "Esperanto"
    if io >= 50 and io >= 3 * eo: return "Ido"
    return None

def strong(ev):
    """The languages of an evidence field with strong evidence: «x[gate…]», «x[…declared…]», «x[…ruling…]»."""
    out = set()
    for m in re.finditer(r"([a-z-]+)\[([^\]]*)\]", ev):
        if re.search(r"gate|declared|ruling", m.group(2)): out.add(m.group(1))
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out"); a = ap.parse_args()
    if a.out and os.path.exists(a.out): sys.exit(f"{a.out} exists: not overwritten")
    lt = sorted(p for p in glob.glob(os.path.join(G, "OCR-TEXT-LANGUAGES-2026-*.tsv")) if re.search(r"-\d{4}-\d\d-\d\d[a-z]?\.tsv$", p))[-1]
    rows = []
    seen = set()
    for l in open(lt, encoding="utf-8"):
        if l.startswith("#") or l.startswith("item\t"): continue
        f = l.rstrip("\n").split("\t")
        if len(f) < 4: continue
        item, ev = f[0], f[3]
        st = strong(ev)
        aux = {SIDE[x] for x in st if x in SIDE}
        if st & HOSTILE: aux.add("hostile")
        side = "mixed" if len(aux) > 1 else next(iter(aux)) if aux else "neutral"
        side, why = override(item, side)
        rows.append((item, side, ",".join(sorted(st)), why or "language table, strong evidence")); seen.add(item)
    # born-digital items (in the item table, not in the language table)
    for l in open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8"):
        if l.startswith("#") or l.startswith("item\t"): continue
        item = l.split("\t")[0]
        if item in seen: continue
        side = next((s for k, s in BD_LANG.items() if item.startswith(k)), None)
        if side: rows.append((item, side, "", "born-digital, by run (BD_LANG)")); seen.add(item); continue
        side = bd_side(os.path.join(G, "sources", "born-digital-text", item + ".txt"))
        if side: rows.append((item, side, "", "born-digital, by its marker words")); seen.add(item)
    c = Counter(r[1] for r in rows)
    print(f"{len(rows)} items with a side from {os.path.relpath(lt, ROOT)} and BD_LANG: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    mixed = [r for r in rows if r[1] == "mixed"]
    byrun = Counter(re.split(r"[ ._-]?(?:1[89]\d\d|n\d|\d)", r[0], maxsplit=1)[0] for r in mixed)
    print(f"  mixed (Esperanto and Ido, both strong; no side until ruled): {len(mixed)}, by run: " + "; ".join(f"{k} {v}" for k, v in byrun.most_common()))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(f"# GENERATED by tools/item-sides.py from {os.path.basename(lt)} and its BD_LANG (born-digital runs). Do not hand-edit: re-run it. "
                     "The side of an item is its auxiliary language with strong evidence (the editor, 2026-10-15); «hostile» = Occidental, Novial, Latino sine flexione, the other side to everyone; «mixed» and «neutral» give no label.\n")
            fh.write("item\tside\tstrong languages\tfrom\n")
            for r in rows: fh.write("\t".join(r) + "\n")
        print(f"wrote {os.path.relpath(a.out, ROOT)}")

if __name__ == "__main__":
    main()
