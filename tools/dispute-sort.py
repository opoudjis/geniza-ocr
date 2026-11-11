#!/usr/bin/env python3
"""dispute-sort.py: sort the far pairs of chosen classes of `tools/same_act.py` into easy folds, easy rejections and the
rest, as a review document for the editor (the editor, 2026-11-07 23:1x; made a tool 2026-11-08 on his choice of both, from Ezri's
scratch class_d4.py, which sorted class D).

    python3 tools/dispute-sort.py --classes B C [--out dowse/DISPUTES-SORT-<tag>.md]

Read-only on the facts: it reads the by-source facts files through same_act.py's pairs() and sift(), and writes only
the review document (create-only; without --out it prints the counts and writes nothing).

- EASY FOLD: nearly the same sentence once each head's name is masked (0.8 or more), surnames alike (0.45 or more) with
  the same first letter, and no clash of given names or initials: one man, a garbled head. For the editor's marks;
  written later by `tools/fold-by-line.py`.
- EASY REJECTION, ONE PAGE: both lines from the same page of the same item (a list, a programme, one event).
- EASY REJECTION, ONE ROLE TWICE: the same sentence (0.85 or more) about two plainly different people: successive or
  joint holders.
- THE REST: possible disputes, to read.
Kinds shared by nature, joint work, different times and indefinite objects are already out of A-D (same_act.py's S, J, T,
I classes). It rules on nothing.
THE RULED PAIRS (2026-11-08 21:0x, the editor): a pair already ruled «two people» or rejected, by a page read or
the editor's mark, is kept in `dowse/SINTER-VERDICTS.tsv` (head_a, head_b, kind, object, year, verdict, source; the object as
the review documents print it, its first 40 characters) and counted here as «ruled» instead of listed again. A pair matches a
row by its two heads (either order), kind, object (first 40 characters) and year. Folded pairs need no row: their heads are one
after the next harvest. A row goes stale when a head is renamed; it then simply matches nothing."""
import argparse, collections, difflib, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
TIT = {"S-ro", "S-ino", "F-ino", "D-ro", "Sro", "Dro", "La", "Laŭ", "Ĉe", "De", "Kun", "Prof.", "Profesoro", "Frato", "Pastro", "Abato", "Kapitano", "Generalo", "Sinjoro"}

def sur(h): return re.sub(r"\s*\(.*", "", h).split()[-1]
def mask(f, h): return re.sub(r"\s+", " ", re.sub(rf"(?i)\b(?:[A-ZĈĜĤĴŜŬ][\w-]*\.?\s+){{0,2}}{re.escape(sur(h))}\w*", "§", f)).strip().lower()
def given(f, h):
    m = re.search(rf"((?:[A-ZĈĜĤĴŜŬ][\w-]*\.?\s+){{1,3}}){re.escape(sur(h)[:3])}", f, re.I)
    return [x for x in (m.group(1).split() if m else []) if x not in TIT]
def clash(a, b): return bool(a and b) and a[0][0].upper() != b[0][0].upper()
def page(w): return re.sub(r"\s*\(prese[^)]*\)|, l\. \d+.*", "", w).strip()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--classes", nargs="+", required=True, choices=list("ABCD"))
    ap.add_argument("--out", help="the review document, relative to geniza/ (create-only)")
    a = ap.parse_args()
    s = importlib.util.spec_from_file_location("same_act", os.path.join(ROOT, "tools", "same_act.py"))
    SA = importlib.util.module_from_spec(s); s.loader.exec_module(SA)
    HF, NG = SA.tools()
    rows = []
    for p in SA.pairs(HF, NG):
        if p["near"]: continue
        c = SA.sift(p)
        if c not in a.classes: continue
        rows.append(dict(c=c, kind=p["kind"], obj=p["obj"], year=p["year"], ha=p["fa"], hb=p["fb"], fa=SA.fact(p["la"]), fb=SA.fact(p["lb"]),
                         wa=SA.where(p["la"]), wb=SA.where(p["lb"]), same_page=p["sa"] == p["sb"] and page(SA.where(p["la"])) == page(SA.where(p["lb"])) != ""))
    out = collections.OrderedDict((k, []) for k in ("ruled", "fold", "reject-page", "reject-role", "rest"))
    ruled = set()
    vp = os.path.join(G, "dowse", "SINTER-VERDICTS.tsv")
    if os.path.exists(vp):
        for ln in open(vp, encoding="utf-8").read().splitlines()[1:]:
            f = ln.split("\t")
            if len(f) >= 6 and not ln.startswith("#"): ruled.add((frozenset((f[0], f[1])), f[2], f[3][:40], f[4]))
    for r in rows:
        if (frozenset((r["ha"], r["hb"])), r["kind"], r["obj"][:40], r["year"]) in ruled: out["ruled"].append(r); continue
        r["sent"] = round(difflib.SequenceMatcher(None, mask(r["fa"], r["ha"]), mask(r["fb"], r["hb"])).ratio(), 2)
        r["name"] = round(difflib.SequenceMatcher(None, sur(r["ha"]).lower(), sur(r["hb"]).lower()).ratio(), 2)
        same_letter = sur(r["ha"])[:1].lower() == sur(r["hb"])[:1].lower()
        if r["sent"] >= 0.8 and r["name"] >= 0.45 and same_letter and not clash(given(r["fa"], r["ha"]), given(r["fb"], r["hb"])): out["fold"].append(r)
        elif r["same_page"]: out["reject-page"].append(r)
        elif r["sent"] >= 0.85: out["reject-role"].append(r)
        else: out["rest"].append(r)
    cls = collections.Counter(r["c"] for r in rows)
    print(f"{len(rows)} pairs of classes {' '.join(a.classes)} ({dict(sorted(cls.items()))}): " + ", ".join(f"{k} {len(v)}" for k, v in out.items()))
    if not a.out: return
    def row(r): return f"| {r['c']} | {r['ha']} | {r['hb']} | {r['kind']}: {r['obj'][:40]} | {r['year']} | {r['fa']} | {r['fb']} | {r['wa'][:45]} / {r['wb'][:45]} |"
    H = ["| class | head A | head B | kind: object | year | A says | B says | where |", "|---|---|---|---|---|---|---|---|"]
    rej = len(out["reject-page"]) + len(out["reject-role"])
    L = [f"# Dispute candidates of classes {', '.join(a.classes)}, sorted", "",
         "*For the editor. GENERATED by `tools/dispute-sort.py` from `tools/same_act.py`'s pairs, read-only; nothing written to any facts file or register. "
         "Each group is a lead: the folds want your marks, as the class D sort's did.*", "",
         f"**{len(rows)} pairs:** {len(out['ruled'])} ruled before (dowse/SINTER-VERDICTS.tsv), not listed; {len(out['fold'])} easy folds; {rej} easy rejections ({len(out['reject-page'])} on one page, {len(out['reject-role'])} one role filled twice); {len(out['rest'])} left to read.", "",
         "## How they were sorted", "",
         "- **Easy fold:** nearly the same sentence once each head's name is masked (0.8 or more), surnames alike (0.45 or more) with the same first letter, no given name or initial clashing: one man, one head garbled.",
         "- **Easy rejection, one page:** both lines from the same page of the same item: a list, a programme, one event with several people.",
         "- **Easy rejection, one role twice:** the same sentence about two plainly different people: successive or joint holders.",
         "- **Left:** the rest: possible disputes, or joint work the tool cannot see.", "",
         f"## The easy folds ({len(out['fold'])}), for your marks", ""] + H + [row(r) for r in sorted(out["fold"], key=lambda r: -r["name"])]
    for k, title in (("reject-page", "one page"), ("reject-role", "one role filled twice")):
        L += ["", f"## Easy rejections: {title} ({len(out[k])})", ""] + H + [row(r) for r in sorted(out[k], key=lambda r: (r["c"], r["kind"], r["year"]))]
    L += ["", f"## Left to read ({len(out['rest'])})", ""] + H + [row(r) for r in sorted(out["rest"], key=lambda r: (r["c"], r["kind"], r["year"]))]
    p = os.path.join(G, a.out)
    open(p, "x", encoding="utf-8").write("\n".join(L).replace("\u0000", "") + "\n")
    print("wrote", a.out)

if __name__ == "__main__":
    main()
