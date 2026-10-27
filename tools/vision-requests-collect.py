#!/usr/bin/env python3
"""The OCR damage the dowse's readers named, collected as rows for ocr/VISION-REQUESTS.tsv (2026-10-27; the editor:
, on; the runbook D4b, whose request rows were written by hand until now).

    tools/vision-requests-collect.py --kept-tag TAGPREFIX [--kept-tag …] [--accuracy DATE] [--write]

Two inputs:
  - every dowse/<source>/UNDATED-KEPT.tsv row with the verdict PAĜO whose tag starts with a --kept-tag prefix and whose
    reason names OCR damage («OCR difektita», «misa», «nelegebla» …: dowse-undated.py's OCR_WORDS);
  - with --accuracy DATE, every dowse/<source>/accuracy-return-DATE.md row with a cell «OCR difektita», and the numbers a
    return lists under «vida legado», each line's locator taken from accuracy-sample-DATE.md.
One row a (locator key, PDF page), the lines and reasons of that page together; a page already in the file (any row) is
left out. The «what the OCR prints» field holds the readers' words, which quote it; «why» their judgement in short. Without
--write it prints the rows; with it, it appends them, ids VR-<today>-<n> after the file's last of the day. Ezri."""
import argparse, csv, datetime, glob, importlib.util, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
VR = os.path.join(G, "ocr", "VISION-REQUESTS.tsv")
spec = importlib.util.spec_from_file_location("du", os.path.join(ROOT, "tools", "dowse-undated.py"))
DU = importlib.util.module_from_spec(spec); argv, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(DU); sys.argv = argv
LOC = re.compile(r"([a-z0-9][a-z0-9.-]*), PDF (\d+)(?: \(prese ([^)]*)\))?(?:, l\. (\d+))?")

def item_names():
    k2n = {}
    with open(os.path.join(G, "OCR-ITEM-TABLE.tsv"), encoding="utf-8") as fh:
        for r in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            if (r.get("key") or "").strip(): k2n[r["key"].strip()] = r["item"]
    return k2n

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kept-tag", action="append", default=[]); ap.add_argument("--accuracy"); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    found = {}   # (key, pdf) -> {"printed", "lines": [], "words": [], "by": []}
    def add(src, loc, why, by):
        m = LOC.search(loc or "")
        if not m: return
        f = found.setdefault((m.group(1), int(m.group(2))), {"printed": m.group(3) or "", "lines": [], "words": [], "by": [], "src": src})
        if m.group(4) and m.group(4) not in f["lines"]: f["lines"].append(m.group(4))
        f["words"].append(re.sub(r"\s+", " ", why).strip()); f["by"].append(by)
    for kp in sorted(glob.glob(os.path.join(G, "dowse", "*", "UNDATED-KEPT.tsv"))):
        src = kp.split(os.sep)[-2]
        for r in csv.reader((l for l in open(kp, encoding="utf-8") if not l.startswith("#")), delimiter="\t"):
            if len(r) > 5 and r[3] == "PAĜO" and any(r[5].startswith(t) for t in a.kept_tag) and DU.OCR_WORDS.search(r[4]):
                add(src, r[0], r[4], f"the undated pass, tag {r[5]}: dowse/{src}/UNDATED-KEPT.tsv")
    if a.accuracy:
        for rp in sorted(glob.glob(os.path.join(G, "dowse", "*", f"accuracy-return-{a.accuracy}.md"))):
            src = rp.split(os.sep)[-2]
            sp = os.path.join(os.path.dirname(rp), f"accuracy-sample-{a.accuracy}.md")
            if not os.path.exists(sp): continue
            sample = {int(m.group(1)): m.group(2) for m in re.finditer(r"^(\d+)\. \(linio \d+\) (.*)$", open(sp, encoding="utf-8").read(), re.M)}
            t = open(rp, encoding="utf-8").read()
            nums = {}
            for row in re.finditer(r"^\|\s*(\d+)\s*\|(.*)\|\s*$", t, re.M):
                cells = [c.strip() for c in row.group(2).split("|")]
                if any(c.lower().startswith("ocr difektita") for c in cells[:-1]): nums[int(row.group(1))] = cells[-1]
            for m in re.finditer(r"vida legado[^:\n]*:([^\n]*)", t, re.I):
                for n in re.findall(r"\b(\d{1,2})\b", m.group(1)): nums.setdefault(int(n), m.group(1))
            for n, why in sorted(nums.items()):
                if n in sample:
                    loc = next((p.strip() for p in sample[n].split(" · ") if LOC.match(p.strip())), "")
                    add(src, loc, why or "OCR difektita", f"the accuracy check {a.accuracy}, line {n}: dowse/{src}/accuracy-return-{a.accuracy}.md")
    have = set(); last = 0; today = datetime.date.today().isoformat()
    rows = [r for r in csv.reader(open(VR, encoding="utf-8"), delimiter="\t") if r]
    for r in rows[1:]:
        if len(r) > 4 and (m := re.match(r"\s*(\d+)", r[4])): have.add((r[2].strip(), int(m.group(1))))
        if r[0].startswith(f"VR-{today}-"): last = max(last, int(r[0].rsplit("-", 1)[1]))
    k2n = item_names(); new = []
    for (key, pdf), f in sorted(found.items()):
        if (key, pdf) in have: continue
        last += 1
        words = " | ".join(dict.fromkeys(f["words"]))
        new.append([f"VR-{today}-{last}", today, key, k2n.get(key, key), f"{pdf}" + (f" (prese {f['printed']})" if f["printed"] else ""),
                    ", ".join(f["lines"]) or "?", words[:500], "named by the reader as OCR damage (the brief's «Difektita OCR» rule)",
                    "; ".join(dict.fromkeys(f["by"])), "requested", "held: no judgement until the vision text and the redowse"])
    for r in new: print("\t".join(r[:6]), "\n   ", r[6][:200])
    print(f"{len(found)} pages named; {len(new)} new, {len(found) - len(new)} already in the file")
    if a.write and new:
        with open(VR, "a", encoding="utf-8", newline="") as fh:
            csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(new)
        print(f"appended {len(new)} rows to {os.path.relpath(VR, ROOT)}")

if __name__ == "__main__":
    main()
