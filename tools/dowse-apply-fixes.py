#!/usr/bin/env python3
"""dowse-apply-fixes.py: merge a repair reader's fixes into the sources' facts-config.json (runbook D6).

The editor, 2026-10-11 (): repair passes over the facts files
(lines that lean on other lines; derived sources without a year; refuted claims) return their fixes as JSON pairs or
triples in code blocks. This tool copies them, unchanged, into each source's settings file, so the assembly applies them
and the fixes stay on record beside the source; the readers' returns are never edited.

    tools/dowse-apply-fixes.py <return.md>:<kind>[:<source>] ... [--dry-run]      kind: fact | label | lines

reads   the filed returns (under geniza/dowse/); a heading «## <source>-dowse.md» switches the source for the blocks
        after it, otherwise the spec's <source> names it;
writes  geniza/dowse/<source>/facts-config.json: appends to «fact_fixes» (kind fact), «label_fixes» (kind label) or
        «extra_lines» (kind lines: every line of a code block that starts «- $$$»); an entry already there is not added
        twice; each new entry is first tried on the facts and refused if it matches no line or is already in effect, and
        one landing on a line an earlier fix changes is listed as an overlap (check_on_arrival, runbook D6 11a,
        2026-10-12). Writes nothing on --dry-run (the check still runs). Then rebuild with tools/dowse-facts-assemble.py <source> --replace, which
        reports any fix that matched no line.

In a block, a line starting «[» is one entry (a trailing comma is allowed); «//» lines and the brackets that open and
close a JSON list are skipped. (Ezri, 2026-10-11)"""
import argparse, importlib.util, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")
_spec = importlib.util.spec_from_file_location("assemble", os.path.join(ROOT, "tools", "dowse-facts-assemble.py"))
ASM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ASM)      # its main() runs only as a script
KEY = {"fact": "fact_fixes", "label": "label_fixes", "lines": "extra_lines", "date": "date_fixes", "drop": "drop_keys"}

def entries(path, kind, default):
    """-> {(source, kind): [entries]}. kind «auto»: a line «KIND: <kind>» outside the code blocks sets the kind of the
    blocks after it (a return carrying several kinds of fix, the combined pass of 2026-10-11)."""
    out, src, inblock, cur = {}, default, False, kind
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        h = re.match(r"(?:#+ |\*\*).*?([a-z0-9-]+)-dowse\.md", line)    # a heading, or a bold line naming the file
        if h and not inblock: src = h.group(1); continue
        k = re.match(r"\W*KIND:\s*(\w+)", line)
        if k and not inblock: cur = k.group(1).lower(); continue
        if line.startswith("```"): inblock = not inblock; continue
        if not inblock or cur not in KEY: continue
        s = line.strip()
        if cur == "lines":
            if s.startswith("- $$$"): out.setdefault((src, cur), []).append(s)
            continue
        if not s.startswith("[") or s in ("[", "[]"): continue
        e = json.loads(s.rstrip(","))
        if cur == "drop" and isinstance(e, list) and len(e) == 1: e = e[0]
        elif not (isinstance(e, list) and len(e) in (2, 3) and all(isinstance(x, str) for x in e)):
            sys.exit(f"not a pair or triple: {s[:120]}")
        out.setdefault((src, cur), []).append(e)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="<return.md>:<kind>[:<source>], several in one run (one approval)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for spec in a.specs:
        ret, kind, *rest = spec.split(":")
        if kind not in KEY and kind != "auto": sys.exit(f"kind must be one of {list(KEY)} or auto: {spec}")
        found = entries(ret, kind, rest[0] if rest else None)
        if any(s is None for s, _ in found): sys.exit(f"{ret}: entries before any «## <source>-dowse.md» heading and no source given")
        for (src, k), es in found.items(): apply({src: es}, k, a.dry_run)

def miss_prefix(kind, e):
    """The assembly's report for an entry that matched nothing (tools/dowse-facts-assemble.py)."""
    if kind == "drop": return f"DROP KEY MATCHED NO LINE: {e}"
    if kind == "date": return f"DATE FIX MATCHED NO LINE: {e[0]}"
    key, a = (e[0], e[1]) if len(e) == 3 else ("", e[0])
    return f"{'LABEL ' if kind == 'label' else ''}FIX MATCHED NO LINE: {key} | {a}"

def check_on_arrival(src, S, kind, new):
    """CHECKED ON ARRIVAL (P2; the editor 2026-10-12,: of 21 fixes left unmatched by the
    combined pass, most had an old string not copied verbatim or a line another fix had changed first). Each new entry
    is tried on the facts as they will be assembled, before it is written: one that matches no line, or is already in
    effect, is refused and listed, to go back to its reader; one that lands on a line another entry also changes is
    applied and listed as an overlap (P3), for a decision. -> the entries to write."""
    S2 = json.loads(json.dumps(S)); S2.setdefault(KEY[kind], []).extend(new)
    _, _, _, bad, notes = ASM.assemble(src, S2)
    keep = []
    batch = {((x[0], x[1]) if len(x) == 3 else ("", x[0])) for x in new} if kind == "fact" else set()
    for e in new:
        pre = miss_prefix(kind, e)
        miss = next((b for b in bad if b.startswith(pre)), None)
        key, a = ((e[0], e[1]) if len(e) == 3 else ("", e[0])) if kind in ("fact", "label") else (None, None)
        spent = kind == "fact" and f"SPENT (already in the line): {key} | {a}" in notes["spent"]
        if miss: print("  REFUSED, back to the reader:", miss[:300])
        elif spent: print("  REFUSED, already in effect:", f"{key} | {a}"[:200])
        else:
            keep.append(e)
            if kind == "fact":
                for view, ap, raw in notes["applied"]:
                    others = [x for x in ap if x not in batch]    # earlier fixes only: a return's own fixes on one line are one reader's
                    if (key, a) in ap and others:
                        print(f"  OVERLAP, for a decision: «{a[:60]}» and {'; '.join(f'«{x[1][:60]}»' for x in others)} on «{view[:90]}»")
    print(f"  checked on arrival: {len(keep)} accepted, {len(new) - len(keep)} refused")
    return keep

def apply(found, kind, dry):
    for src, es in found.items():
        cfg = os.path.join(G, "dowse", src, "facts-config.json")
        if not os.path.exists(cfg): sys.exit(f"no settings file: {cfg}")
        S = json.load(open(cfg, encoding="utf-8"))
        have = S.setdefault(KEY[kind], [])
        new = []                         # not twice, neither against the settings nor within one return (2026-10-12:
        for e in es:                     # four identical repairs for four twin lines applied four times to each)
            if e not in have and e not in new: new.append(e)
        print(f"{src}: {len(es)} entries in the return, {len(new)} new → {KEY[kind]}")
        if kind != "lines": new = check_on_arrival(src, S, kind, new)
        if dry or not new: continue
        have.extend(new)
        open(cfg, "w", encoding="utf-8").write(json.dumps(S, ensure_ascii=False, indent=2) + "\n")
        print("  wrote", os.path.relpath(cfg, ROOT))

if __name__ == "__main__":
    main()
