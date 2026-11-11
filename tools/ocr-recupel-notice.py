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
    python3 tools/ocr-recupel-notice.py signed --suffix <batch> --lines <SIGNED file> [--dry-run]   (run sheet C12, after
          the signature: one row per item the file newly accepts, kind «signed: ready to dowse»)
    python3 tools/ocr-recupel-notice.py normalised --suffix <s> --why "<text>" <item>…   (a signed item's text changed by
          the apostrophe normalisation, with no new reading: one row per item, kind «apostrophes normalised», no superseded text)

WRITE-SET: snapshot: new files in `sources/ocr-preferred/_superseded/`; bdfix: the items' texts moved into
`sources/born-digital-text/_superseded/`, rows appended to RECUPEL-NOTICES.tsv; notice, normalised and signed: rows appended to
RECUPEL-NOTICES.tsv (its header written if the file is new); notice also removes only this tool's own snapshot of an
unchanged item; signed --dry-run writes nothing.
"""
import argparse, datetime, glob, importlib.util, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import onb_footer as OF

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "published", "heterophony-resources", "geniza")
S = os.path.join(G, "sources"); R = os.path.join(S, "ocr-rendersearch"); P = os.path.join(S, "ocr-preferred")
SUP = os.path.join(P, "_superseded"); NOTICES = os.path.join(G, "ocr", "RECUPEL-NOTICES.tsv")
PAGE = re.compile(r"^=== page (\d+) ===\s*$", re.M)
SEARCH_ONLY = (".names.txt", ".sc3x.txt", ".layout.txt", ".cols-add.txt", ".frk-add.txt", ".tl-add.txt")
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
        # the readings, and the markers that empty a page's text (2026-10-29, cupel19b: a `.setoff` mark of 2026-10-28 emptied
        # ANNO_e1k_19080062 PDF 8 and was not seen here, so the chain wrote no notice)
        new = [f for g in ("page-*.txt", "page-*.setoff", "page-*.blank") for f in glob.glob(os.path.join(d, g))
               if os.path.getmtime(f) > t]
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
        # pages compared without the ÖNB footer (2026-11-03, the editor: the footer out of the texts): its removal is no
        # change to the source's text, so it raises no notice
        po, pn = ({k: OF.key(v) for k, v in pages(t_).items()} for t_ in (old_t, new_t))
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
            # any new reading that did not change the preferred text joins the search text only (2026-10-29, cupel19b:
            # Idowoti's `.gutter.txt` under a vision page went unnoticed, the list naming only the usual search-only kinds)
            so = sorted({int(f[5:9]) for f in newf if f.endswith(".txt") and f[5:9].isdigit()})
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


def normalised(a):
    # A TEXT CHANGED WITH NO NEW READING (2026-11-07, cupel23, failure map R111): `snapshot` looks for a reading newer than the
    # preferred text, so the apostrophe normalisation (tools/apostrophe_supersign.py), which the rebuild applies to the texts
    # and leaves the readings untouched, raised no notice. The pages are those whose chosen reading it alters. It changes
    # letters only, so no line moves and a fact line's citation stands: no superseded text is kept.
    import csv
    import apostrophe_supersign as AS
    today, rows = datetime.date.today().isoformat(), []
    n0 = sum(1 for l in open(NOTICES, encoding="utf-8") if l.startswith(f"RN-{today}-"))
    for it in a.items:
        if not AS.applies(it): sys.exit(f"{it}: not a title apostrophe_supersign.py names")
        ch = []
        for r in csv.DictReader(open(os.path.join(R, it, "PREFERRED.tsv"), encoding="utf-8"), delimiter="\t"):
            t = "".join(open(os.path.join(R, it, f), encoding="utf-8", errors="ignore").read() for f in r["files"].split(",") if f.strip())
            if AS.normalise(t) != t:
                ch.append(int(r["page"]))
        rows.append((it, ",".join(map(str, ch))))
    with open(NOTICES, "a", encoding="utf-8") as fh:
        for i, (it, pp) in enumerate(rows, n0 + 1):
            fh.write(f"RN-{today}-{i}\t{today}\t{it}\t{pp}\tapostrophes normalised\t-\t{a.why}; chain {a.suffix}\t\n")
    print(f"normalised {a.suffix}: {len(rows)} rows → {NOTICES}")
    for it, pp in rows: print(f"  {it}: {len(pp.split(','))} pages")


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


SIGNED_KIND = "signed: ready to dowse"


def accepted(path):
    """item → the pages field of each of its ACCEPTED lines, in the file's order."""
    out = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("ACCEPTED: "):
            f = [x.strip() for x in l[len("ACCEPTED: "):].split(" | ")]
            out.setdefault(f[0], []).append(f[1] if len(f) > 1 else "")
    return out


def signed_rows(a):
    """«signed» (2026-11-02; Ezri by relay: a signed batch reached her only when someone sent word, and cupel20a's 25
    items had not; the editor 11:1x: built, and run once for cupel20a): after the editor signs a batch (run sheet C12),
    one row per item the signed file --lines newly accepts, kind «signed: ready to dowse», so that Ezri's own read of this
    file finds it. «Newly»: no ACCEPTED line for it in a signed file whose name sorts before this one (an item signed
    again has had its notice), and no row of this kind for it here already (run twice, it writes nothing more). PDF
    pages: the lines' page fields; why: the batch, the signed file, the item key (OCR-ITEM-KEYS.tsv) and the preferred
    text the dowse reads."""
    me = os.path.basename(a.lines)
    files = glob.glob(os.path.join(G, "ocr", "lines", "*SIGNED*")) + glob.glob(os.path.join(G, "*SIGNED*"))
    if not os.path.exists(a.lines) or "SIGNED" not in me: sys.exit(f"not a signed file: {a.lines}")
    before = set()
    for f in files:
        if os.path.basename(f) < me:
            before |= set(accepted(f))
    had = set()
    if os.path.exists(NOTICES):
        for l in open(NOTICES, encoding="utf-8"):
            f = l.rstrip("\n").split("\t")
            if len(f) > 4 and f[4] == SIGNED_KIND:
                had.add(f[2])
    keys = {}
    for l in open(os.path.join(G, "OCR-ITEM-KEYS.tsv"), encoding="utf-8"):
        f = l.rstrip("\n").split("\t")
        if len(f) > 1 and not l.startswith("#") and f[0] != "item":
            keys[f[0]] = f[1]
    rows, skipped = [], 0
    for it, pp in accepted(a.lines).items():
        if it in before or it in had:
            skipped += 1; continue
        pref = os.path.join(P, it + ".txt")
        why = (f"{a.suffix} signed, {me}; key {keys.get(it, '(none yet)')}; preferred text "
               + (os.path.relpath(pref, G) if os.path.exists(pref) else "(none yet)"))
        rows.append((it, "; ".join(pp), why))
    today = datetime.date.today().isoformat()
    n0 = sum(1 for l in open(NOTICES, encoding="utf-8") if l.startswith(f"RN-{today}-")) if os.path.exists(NOTICES) else 0
    out = [f"RN-{today}-{i}\t{today}\t{it}\t{pp}\t{SIGNED_KIND}\t-\t{why}\t\n" for i, (it, pp, why) in enumerate(rows, n0 + 1)]
    if a.dry_run:
        sys.stdout.write("".join(out))
        print(f"signed {a.suffix} (dry run): {len(rows)} rows; {skipped} items accepted before or noticed already"); return
    new = not os.path.exists(NOTICES)
    with open(NOTICES, "a", encoding="utf-8") as fh:
        if new:
            fh.write(HEAD)
        fh.write("".join(out))
    print(f"signed {a.suffix}: {len(rows)} rows → {NOTICES}; {skipped} items accepted before or noticed already")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("snapshot", "notice", "bdfix", "signed", "normalised")); ap.add_argument("--suffix", required=True); ap.add_argument("--why")
    ap.add_argument("--why-items", help="notice: a TSV of item⇥why, for items whose notice needs its own why (a vision request's id)")
    ap.add_argument("--lines", help="signed: the signed acceptance-lines file just written")
    ap.add_argument("--dry-run", action="store_true", help="signed: print the rows, write nothing")
    ap.add_argument("items", nargs="*", help="bdfix: the born-digital items whose signed texts are corrected; normalised: the signed items the apostrophe normalisation changed")
    a = ap.parse_args()
    if a.mode == "bdfix" and not a.items: sys.exit("bdfix needs the items")
    if a.mode == "normalised" and not (a.items and a.why): sys.exit("normalised needs the items and --why")
    if a.mode == "signed" and not a.lines: sys.exit("signed needs --lines")
    {"snapshot": snapshot, "notice": notice, "bdfix": bdfix, "signed": signed_rows, "normalised": normalised}[a.mode](a)
