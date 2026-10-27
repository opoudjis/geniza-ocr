#!/usr/bin/env python3
"""The alignment pass for restored lines: put the aligned lines back (the editor, 2026-10-14 10:0x, 10:1x). The runbook, D6, point 8.

    tools/dowse-align-apply.py <date> <source>[@K][:n,n,…] ...     (@K: the returns cover the lines from K on)

For each source: reads every dowse/<source>/align-return-<date>*.md, takes the numbered lines of part (1) («N. - $$$ …»,
«N. JAM: …», «N. FORIGU: …»), requires exactly one for each restored line, and replaces «restore» in facts-config.json
with the aligned lines (JAM and FORIGU dropped; «:n,n,…» drops those numbers too, for a return whose brief predates
«JAM»; «:+n,n,…» keeps those numbers as they were restored, for a JAM whose new line stands under another person
and names this one only in the fact, so the harvest makes no copy for them). A kept line whose reader left the anchor inside the fact («…» at its end, one field short) gets the anchor in
its own field, the words unchanged. Then the facts file is reset to git and rebuilt by tools/dowse-facts-assemble.py
--replace, and tools/harvest-facts.py --check runs. Write-set: the settings and the facts file of each source.
Ezri, 2026-10-14."""
import glob, json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join("published", "heterophony-resources", "geniza")

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    os.chdir(ROOT)
    date, args = sys.argv[1], sys.argv[2:]
    for a in args:
        ma = re.fullmatch(r"([^:@]+)(?:@(\d+))?(?::(.*))?", a)   # «@K»: the returns cover the lines from K on; those
        s, frm, extra = ma.group(1), int(ma.group(2) or 1), ma.group(3) or ""   # before K stay as aligned (2026-10-15)
        keepjam = extra.startswith("+"); extra = {int(x) for x in extra.lstrip("+").split(",") if x}
        p = os.path.join(G, "dowse", s, "facts-config.json"); cfg = json.load(open(p, encoding="utf-8"))
        orig = list(cfg["restore"])
        n = len(cfg["restore"])
        rets = sorted(glob.glob(os.path.join(G, "dowse", s, f"align-return-{date}*.md")))
        ret = "\n".join(open(f, encoding="utf-8").read().split("## (2)")[0] for f in rets)
        got = {}
        for m in re.finditer(r"^\s*(\d+)\\?\.\s+(- \$\$\$ .*|FORIGU:.*|JAM:.*|NOMO:.*)$", ret, re.M):   # «70\.»: a reader's markdown escape
            k = int(m.group(1))
            if k in got: sys.exit(f"{s}: number {k} twice; nothing changed")
            got[k] = m.group(2).strip()
        if sorted(got) != list(range(frm, n + 1)):
            sys.exit(f"{s}: {len(got)} numbered lines for {n - frm + 1} restored; missing {sorted(set(range(frm, n + 1)) - set(got))[:10]}; nothing changed")
        for k in range(1, frm): got[k] = orig[k - 1]   # aligned before
        for k in extra:   # «:n,…» drops those numbers; «:+n,…» keeps them as restored, where the reader's JAM would keep
            got[k] = orig[k - 1] if keepjam else "JAM: (dropped by number)"   # the fact from a person's profile
        moved = 0
        for k, l in got.items():
            if not l.startswith("- $$$"): continue
            ps = l.split(" · ")
            if len(ps) == 6 and ps[1].startswith("{"):
                m = re.match(r"^(.*?)\s*«([^«»]+)»\s*$", ps[2])
                if m and m.group(1):
                    got[k] = " · ".join(ps[:2] + [m.group(1).rstrip(), m.group(2)] + ps[3:]); moved += 1
        keep = [got[k] for k in range(1, n + 1) if got[k].startswith("- $$$")]
        drop = [(k, got[k]) for k in range(1, n + 1) if not got[k].startswith("- $$$")]
        noms = [(k, w) for k, w in drop if w.startswith("NOMO")]
        if noms:   # name identifications: proposed rows for the names register and the alias table, for the editor's sign-off
            np_ = os.path.join(G, "dowse", s, f"align-names-{date}.md")
            open(np_, "w", encoding="utf-8").write(f"# {s}: name identifications from the alignment of {date}, proposed for the names register\n\n"
                + "\n".join(f"- {k}. {w[5:].strip()}  ⟵ restored line: {orig[k - 1][:200]}" for k, w in noms) + "\n")
            print(f"  {len(noms)} name identifications → {os.path.relpath(np_, ROOT)}")
        cfg["restore"] = keep
        cfg["_restore_note"] = (cfg.get("_restore_note", "") + f" Aligned to the current form on {date} "
                                f"(dowse/{s}/align-return-{date}*.md): {len(keep)} kept, {len(drop)} dropped.")
        json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        f = os.path.join(G, "profiles", "by-source", f"{s}-dowse.md")
        subprocess.run(["git", "checkout", "--", f], check=True)
        r = subprocess.run([sys.executable, "tools/dowse-facts-assemble.py", s, "--replace"], capture_output=True, text=True)
        print(f"{s}: {len(rets)} returns; kept {len(keep)}, already in the new reading {sum(1 for _, w in drop if w.startswith('JAM'))}, "
              f"unalignable {sum(1 for _, w in drop if w.startswith('FORIGU'))}; anchors moved {moved}")
        print("  ", (r.stdout + r.stderr).strip().split("\n")[-1])
    r = subprocess.run([sys.executable, "tools/harvest-facts.py", "--check"], capture_output=True, text=True)
    print("\n".join(l for l in (r.stdout + r.stderr).split("\n") if re.search(r"· \d+ errors|dowse\.md:\d+ format|event kinds", l)))

if __name__ == "__main__":
    main()
