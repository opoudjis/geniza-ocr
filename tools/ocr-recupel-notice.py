#!/usr/bin/env python3
r"""ocr-recupel-notice — the cupel's side of the selective redowse: keep a signed item's old text, and tell Ezri what changed.

    python3 tools/ocr-recupel-notice.py snapshot --suffix <chain suffix>          (by tools/ocr-chain.sh, before the rebuild)
    python3 tools/ocr-recupel-notice.py notice   --suffix <chain suffix> [--why "<text>"] [--why-items <item⇥why tsv>]   (by the chain, after it)

WHY (the editor 2026-10-24 13:2x; 13:3x approved building it). The form is Ezri's, agreed by relay 2026-10-24
(`geniza/ocr/method/REDOWSE-PAGES-PROPOSAL-2026-10-24.md`): a dowse reads `sources/ocr-preferred/<item>.txt` and every fact
line cites a line of it, so a signed item whose preferred text changes needs its old text kept until it is redowsed, and
a notice; a reading added to the SEARCH text only («search-only reading added») moves no line and needs no copy.

snapshot  For every SIGNED item (`tools/ocr-dowse.py` signed_lines()) with a reading in `sources/ocr-rendersearch/<item>/`
          newer than its `sources/ocr-preferred/<item>.txt` (the rebuild rewrites that file at every chain, so a newer
          reading came after the last chain): the preferred text copied to
          `sources/ocr-preferred/_superseded/<item>@<suffix>.txt` (refused where it exists), and the reading files
          listed in `_superseded/<item>@<suffix>.new` (the search-only notice reads it).
notice    For each snapshot of the suffix: page by page against the preferred text the chain wrote. Pages whose text
          changed: one row in `geniza/ocr/RECUPEL-NOTICES.tsv` (append-only), its kind from the page's new preferred
          file (`PREFERRED.tsv`): «vision page», «columns re-cut» (.cols / .blocks / .frk), «page added, dropped or split»
          (the page count changed: every PDF N after it shifts), else «re-read». No page changed: the snapshot (this
          tool's own copy, the same text) is removed; and if the new readings were search-only ones (`.names`, `.sc3x`,
          `.layout`, `.cols-add`, `.frk-add`), one row of kind «search-only reading added», no superseded path.
          Columns (Ezri's): notice (RN-<date>-<n>), date, item, PDF pages changed, kind, superseded text, why, Ezri's
          status (left empty, hers). The superseded text is kept until her status reads «redowsed ‹commit›».
    python3 tools/ocr-recupel-notice.py bdfix --suffix <s> --why "<text>" <item>…   (a signed born-digital text corrected)

WRITE-SET: snapshot: new files in `sources/ocr-preferred/_superseded/`; bdfix: the items' texts moved into
`sources/born-digital-text/_superseded/`, rows appended to RECUPEL-NOTICES.tsv; notice: rows appended to RECUPEL-NOTICES.tsv
(its header written if the file is new), and removing only this tool's own snapshot of an unchanged item.
"""
import argparse, datetime, glob, importlib.util, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
S = os.path.join(G, "sources"); R = os.path.join(S, "ocr-rendersearch"); P = os.path.join(S, "ocr-preferred")
SUP = os.path.join(P, "_superseded"); NOTICES = os.path.join(G, "ocr", "RECUPEL-NOTICES.tsv")
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
SEARCH_ONLY = (".names.txt", ".sc3x.txt", ".layout.txt", ".cols-add.txt", ".frk-add.txt")
HEAD = "notice\tdate\titem\tPDF pages changed\tkind\tsuperseded text\twhy\tEzri's status\n"


def signed():
    sp = importlib.util.spec_from_file_location("ocr_dowse", os.path.join(HERE, "ocr-dowse.py"))
    D = importlib.util.module_from_spec(sp); sp.loader.exec_module(D)
    return set(D.signed_lines())


def pages(text):
    parts = PAGE.split(text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def snapshot(a):
    os.makedirs(SUP, exist_ok=True); n = 0
    for it in sorted(signed()):
        pf = os.path.join(P, it + ".txt"); d = os.path.join(R, it)
        if not (os.path.exists(pf) and os.path.isdir(d)):
            continue
        t = os.path.getmtime(pf)
        new = [f for f in glob.glob(os.path.join(d, "page-*.txt")) if os.path.getmtime(f) > t]
        if not new:
            continue
        dst = os.path.join(SUP, f"{it}@{a.suffix}.txt")
        if os.path.exists(dst):
            continue
        shutil.copy2(pf, dst)
        with open(dst[:-len(".txt")] + ".new", "x", encoding="utf-8") as fh:
            fh.write("".join(os.path.basename(f) + "\n" for f in sorted(new)))
        n += 1
    print(f"snapshot {a.suffix}: {n} signed items with new readings")


def kind_of(it, changed):
    pt = os.path.join(R, it, "PREFERRED.tsv"); pref = {}
    if os.path.exists(pt):
        for l in open(pt, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if f[0].isdigit():
                pref[int(f[0])] = f[1]
    ks = set()
    for p in changed:
        x = pref.get(p, "")
        ks.add("vision page" if "vision" in x else "columns re-cut" if re.search(r"\.(cols|blocks|frk)\b", x) else "re-read")
    return ", ".join(sorted(ks))


def notice(a):
    rows, today = [], datetime.date.today().isoformat()
    n0 = 0
    if os.path.exists(NOTICES):
        n0 = sum(1 for l in open(NOTICES, encoding="utf-8") if l.startswith(f"RN-{today}-"))
    for old in sorted(glob.glob(os.path.join(SUP, f"*@{a.suffix}.txt"))):
        it = os.path.basename(old)[:-len(f"@{a.suffix}.txt")]
        new_t = open(os.path.join(P, it + ".txt"), encoding="utf-8", errors="ignore").read()
        old_t = open(old, encoding="utf-8", errors="ignore").read()
        po, pn = pages(old_t), pages(new_t)
        listed = old[:-len(".txt")] + ".new"
        newf = [l.strip() for l in open(listed, encoding="utf-8")] if os.path.exists(listed) else []
        if set(po) != set(pn):
            ch = sorted(set(po) ^ set(pn) | {p for p in set(po) & set(pn) if po[p] != pn[p]})
            kind = "page added, dropped or split"
        else:
            ch = sorted(p for p in pn if po[p] != pn[p]); kind = kind_of(it, ch) if ch else ""
        if ch:
            rows.append((it, ",".join(map(str, ch)), kind, os.path.relpath(old, G)))
        else:
            os.remove(old)
            if os.path.exists(listed):
                os.remove(listed)
            so = sorted({int(f[5:9]) for f in newf if f.endswith(SEARCH_ONLY) and f[5:9].isdigit()})
            if so:
                rows.append((it, ",".join(map(str, so)), "search-only reading added", "-"))
    if not rows:
        print(f"notice {a.suffix}: no signed item changed"); return
    # --why-items (2026-10-26, dowse runbook D4b, Ezri 15:1x: the vision request's id in «why»): item⇥why rows; such an
    # item's notice carries its own why, then the chain's suffix, in place of the chain's --why
    wi = dict(l.rstrip("\n").split("\t", 1) for l in open(a.why_items, encoding="utf-8")
              if "\t" in l and not l.startswith("#")) if a.why_items else {}
    new = not os.path.exists(NOTICES)
    with open(NOTICES, "a", encoding="utf-8") as fh:
        if new:
            fh.write(HEAD)
        for i, (it, pp, kind, sup) in enumerate(rows, n0 + 1):
            why = f"{wi[it]}; chain {a.suffix}" if it in wi else a.why or f"chain {a.suffix}"
            fh.write(f"RN-{today}-{i}\t{today}\t{it}\t{pp}\t{kind}\t{sup}\t{why}\t\n")
    print(f"notice {a.suffix}: {len(rows)} rows → {NOTICES}")


BD = os.path.join(G, "sources", "born-digital-text"); BDSUP = os.path.join(BD, "_superseded")


def bdfix(a):
    """«bdfix» (2026-10-26, the editor; Ezri 2026-10-26 00:2x: «A correction to a signed text, if one is ever
    needed, comes as a recupel notice, and the selective redowse re-pins the lines»): a SIGNED born-digital text about to
    be corrected (its line unchanged) is moved to `sources/born-digital-text/_superseded/<item>@<suffix>.txt` (refused
    where that exists), so tools/born-digital-convert.py writes the corrected one in its place; one notice row each,
    kind «born-digital text corrected», pages «all» (an unpaged text's ¶ / line numbers may all move) or the PDF pages
    of a paged one. Run it, then the converter; the old text is kept until Ezri's status reads «redowsed ‹commit›»."""
    os.makedirs(BDSUP, exist_ok=True)
    rows, today = [], datetime.date.today().isoformat()
    for it in a.items:
        src, dst = os.path.join(BD, it + ".txt"), os.path.join(BDSUP, f"{it}@{a.suffix}.txt")
        if not os.path.exists(src): sys.exit(f"no born-digital text {src}")
        if os.path.exists(dst): sys.exit(f"refusing: {dst} exists")
        pp = ",".join(re.findall(r"^=== page (\d+) ===$", open(src, encoding="utf-8").read(), re.M)) or "all"
        shutil.move(src, dst); rows.append((it, pp, os.path.relpath(dst, G)))
    n0 = sum(1 for l in open(NOTICES, encoding="utf-8") if l.startswith(f"RN-{today}-")) if os.path.exists(NOTICES) else 0
    new = not os.path.exists(NOTICES)
    with open(NOTICES, "a", encoding="utf-8") as fh:
        if new:
            fh.write(HEAD)
        for i, (it, pp, sup) in enumerate(rows, n0 + 1):
            fh.write(f"RN-{today}-{i}\t{today}\t{it}\t{pp}\tborn-digital text corrected\t{sup}\t{a.why or a.suffix}\t\n")
    print(f"bdfix {a.suffix}: {len(rows)} texts moved to {os.path.relpath(BDSUP, G)}, {len(rows)} notices → {NOTICES}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("snapshot", "notice", "bdfix")); ap.add_argument("--suffix", required=True); ap.add_argument("--why")
    ap.add_argument("--why-items", help="notice: a TSV of item⇥why, for items whose notice needs its own why (a vision request's id)")
    ap.add_argument("items", nargs="*", help="bdfix: the born-digital items whose signed texts are corrected")
    a = ap.parse_args()
    if a.mode == "bdfix" and not a.items: sys.exit("bdfix needs the items")
    {"snapshot": snapshot, "notice": notice, "bdfix": bdfix}[a.mode](a)
