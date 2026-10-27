#!/usr/bin/env python3
"""Anchors under six words in a source's returns, lengthened from the page as «quote_fixes» (made a tool 2026-10-14
from the stage-1 helper extend_anchors.py; since the six-words rule of 2026-10-14 a fallback, for returns that still
have short anchors).

    tools/dowse-anchor-extend.py <source> [--dry-run]

For each line of the returns listed in dowse/<source>/facts-config.json whose anchor has under six words, the anchor is
found on its page (the harvest's quotation finder) and extended with the source's own neighbouring words, after it,
then before it, to six; the fix [fact key, old, new] is added to «quote_fixes». Prints each fix. Ezri, 2026-10-14."""
import argparse, importlib.util, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "published", "heterophony-resources", "geniza")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("hf", os.path.join(ROOT, "tools", "harvest-facts.py")); hf = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["x"]; spec.loader.exec_module(hf); sys.argv = saved
    fid = hf._fid()
    cp = os.path.join(G, "dowse", a.source, "facts-config.json"); cfg = json.load(open(cp, encoding="utf-8"))
    have = {(f[0], f[1]) for f in cfg.get("quote_fixes", []) if len(f) == 3}
    fixes, cache, seen = [], {}, set()
    for ret in cfg["returns"]:
        for line in open(os.path.join(G, "dowse", a.source, ret), encoding="utf-8"):
            if not line.startswith("- $$$") or line in seen: continue
            seen.add(line)
            ps = line.rstrip("\n").split(" · ")
            if len(ps) < 6: continue
            anchor, fact, loc = ps[-4], ps[-5], ps[-3]
            segs = [x for x in re.split(r"…|\.\.\.", anchor) if x.strip()]
            if max((len(x.split()) for x in segs), default=0) >= 6 or "⟨fino⟩" in anchor: continue
            ms = hf.locators(loc)
            if not ms: print("SKIP (locator):", line[:90]); continue
            item = ms[0].group("item").strip(); page = int(ms[0].group("pdf") or ms[0].group("para"))
            if item not in cache: cache[item] = hf.item_pages(item, fid)
            pages = cache[item] or {}
            # an anchor broken by an ellipsis («Fariĝinte privata instruisto (...) en 1877 post»: seven words, no part
            # of six) is extended from its longest part, not as a whole (2026-10-17, found in Jossinet's redowse: the
            # whole had seven words, so nothing was added, and the fix wrote the anchor back unchanged)
            base = max(segs, key=lambda x: len(x.split())).strip(" ()[]") if len(segs) > 1 else anchor
            words = [fid.norm(w) for w in base.split() if fid.norm(w)]
            hit = fid.find(pages, page, words) if words else None
            if not hit: print(f"NOT FOUND: «{anchor}» | {item} {page}"); continue
            p, i = hit[0], hit[1]; toks = pages[p]; n = len(base.split())
            after = toks[i + n: i + n + max(0, 6 - n)]
            new = toks[i: i + n + len(after)]
            if len(new) < 6: new = toks[max(0, i - (6 - len(new))): i] + new
            key = fact[:50]
            if (key, anchor) in have: continue
            if " ".join(new) == anchor or len(new) < 6: print(f"NOT EXTENDED: «{anchor}» | {item} {page}"); continue
            fixes.append([key, anchor, " ".join(new)]); print(f"+ «{anchor}» → «{' '.join(new)}»")
    if fixes and not a.dry_run:
        cfg.setdefault("quote_fixes", []).extend(fixes)
        json.dump(cfg, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(fixes)} fixes{' (dry run, not written)' if a.dry_run else ' added to ' + os.path.relpath(cp, G)}")

if __name__ == "__main__":
    main()
