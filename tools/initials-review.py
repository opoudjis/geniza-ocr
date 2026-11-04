#!/usr/bin/env python3
"""The initials' review document for the editor's rulings (the dress runbook's step 10f.3; 2026-11-04, after the reading
pass wf_5a0ec5d3-8f7, the editor).

    tools/initials-review.py TAG [--write]          e.g. 2026-11-04b

Reads dowse/initials/INITIALS-INPUT-<TAG>-N.md (each head: «### N. «A. Z.» en <source> (n linioj)», its lines «N.k»,
its candidates «**Kandidato X**») and the readers' returns initials-return-<TAG>-N.md («N.k · X|neniu|necerta ·
kial»). Each head's lines are grouped by verdict; each group naming a candidate is one proposal, numbered P1, P2 … in
document order, so the editor can rule in one line. Every line is given in full (the fact, its
quotation, its locator) with the reader's reason. Heads whose lines found no candidate are listed briefly at the end:
they stay as printed. With --write: dowse/initials/INITIALS-RULINGS-<TAG>.md (the document) and
INITIALS-PROPOSALS-<TAG>.tsv (P, head, initials, source, candidate, line ids: what step 10f.4 writes once ruled),
create-only. Without it, the counts. Ezri."""
import argparse, csv, glob, os, re, sys
from collections import OrderedDict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "published", "heterophony-resources", "geniza", "dowse", "initials")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag"); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    heads, lines = OrderedDict(), {}
    for f in sorted(glob.glob(os.path.join(D, f"INITIALS-INPUT-{a.tag}-*.md")), key=lambda p: int(re.search(r"-(\d+)\.md$", p).group(1))):
        cur = None
        for l in open(f, encoding="utf-8"):
            m = re.match(r"### (\d+)\. «(.+?)» en (\S+) \((\d+) linioj\)", l)
            if m:
                cur = int(m.group(1)); heads[cur] = {"init": m.group(2), "src": m.group(3), "n": int(m.group(4)), "cands": [], "ids": []}
                continue
            m = re.match(r"\*\*Kandidato (.+?)\*\*", l)
            if m and cur is not None: heads[cur]["cands"].append(m.group(1)); continue
            m = re.match(r"- (\d+\.\d+) - (.*)$", l.rstrip("\n"))
            if m and cur is not None and m.group(1).split(".")[0] == str(cur):
                lines[m.group(1)] = re.sub(r"\$\$\$ (.+?) \$\$\$", r"«\1»", m.group(2)); heads[cur]["ids"].append(m.group(1))
    verdict = {}
    for f in glob.glob(os.path.join(D, f"initials-return-{a.tag}-*.md")):
        for l in open(f, encoding="utf-8"):
            m = re.match(r"\s*`?(\d+\.\d+)\s*·\s*([^·]+?)\s*·\s*(.*?)`?\s*$", l)
            if m: verdict[m.group(1)] = (m.group(2).strip(), m.group(3).strip())
    missing = [i for i in lines if i not in verdict]
    props, out, quiet = [], [], []
    for h, d in heads.items():
        groups = OrderedDict()
        for i in d["ids"]:
            v = verdict.get(i, ("(sen respondo)", ""))[0]
            k = v.lower() if v.lower() in ("neniu", "necerta") else v
            groups.setdefault(k, []).append(i)
        named = [k for k in groups if k not in ("neniu", "necerta", "(sen respondo)")]
        if not named:
            quiet.append(f"- **{h}. «{d['init']}»** in `{d['src']}`: {len(d['ids'])} lines, " +
                         ", ".join(f"{k} {len(v)}" for k, v in groups.items()) + f" (candidates were {', '.join(d['cands']) or 'none'})")
            continue
        out.append(f"\n## {h}. «{d['init']}» in `{d['src']}`: {len(d['ids'])} lines\n")
        out.append(f"Candidates put to the readers: {', '.join(d['cands'])}. The readers: " +
                   ", ".join(f"{k} {len(v)}" for k, v in groups.items()) + ".\n")
        for k in named:
            p = len(props) + 1
            props.append([f"P{p}", h, d["init"], d["src"], k, ",".join(groups[k])])
            out.append(f"\n### P{p}. «{d['init']}» = **{k}**, {len(groups[k])} line{'s' if len(groups[k]) > 1 else ''}\n")
            for i in groups[k]:
                out.append(f"- **{i}** {lines[i]}\n  - *the reader:* {verdict[i][1]}")
        for k in ("neniu", "necerta", "(sen respondo)"):
            if k in groups:
                out.append(f"\n**{k}** ({len(groups[k])}), stay as printed unless the editor rules otherwise:\n")
                for i in groups[k]:
                    out.append(f"- **{i}** {lines[i]}\n  - *the reader:* {verdict.get(i, ('', ''))[1]}")
    print(f"{a.tag}: {len(heads)} heads, {len(lines)} lines, {len(verdict)} answered, {len(missing)} without an answer")
    print(f"  proposals: {len(props)} (over {len({p[1] for p in props})} heads, {sum(len(p[5].split(',')) for p in props)} lines); heads with no candidate: {len(quiet)}")
    if not a.write: print("(dry run: nothing written)"); return
    rp, tp = os.path.join(D, f"INITIALS-RULINGS-{a.tag}.md"), os.path.join(D, f"INITIALS-PROPOSALS-{a.tag}.tsv")
    for p in (rp, tp):
        if os.path.exists(p): sys.exit(f"refusing to overwrite {p}")
    head = (f"# The initials: proposals for the editor's rulings ({a.tag})\n\n"
            f"`[GENERATED by tools/initials-review.py {a.tag}. Do not hand-edit; re-run it. The dress runbook's step 10f.3.]`\n\n"
            f"The reading pass judged {len(lines)} lines under {len(heads)} initials-only heads, line by line, each against its "
            f"candidates' own lines in the same source. **{len(props)} proposals** follow, each an identification of some of a head's "
            f"lines, with every line in full and the reader's reason. A ruling per proposal is enough («P1–P12 yes, P7 no»). "
            f"Lines judged «neniu» or «necerta» are shown under their head, and stay as printed. {len(quiet)} heads found no candidate "
            f"at all; they are listed at the end.\n")
    open(rp, "x", encoding="utf-8").write(head + "\n".join(out) + "\n\n## The heads with no candidate found\n\n" + "\n".join(quiet) + "\n")
    with open(tp, "x", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["proposal", "head", "initials", "source", "candidate", "lines"]); w.writerows(props)
    print(f"wrote {os.path.relpath(rp, ROOT)} and {os.path.relpath(tp, ROOT)}")

if __name__ == "__main__":
    main()
