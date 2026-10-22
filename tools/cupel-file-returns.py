#!/usr/bin/env python3
r"""cupel-file-returns — readers' returns filed VERBATIM from their task outputs (a reader's final message).

    python3 tools/cupel-file-returns.py slices --batch <batch dir> --tasks <tasks dir> --returns <slices folder>
               --brief <brief file> --words "<WORD|WORD>" [--title "C2 look"] [--date YYYY-MM-DD] [--out-root <dir>]
               <k>=<agentId>[+<agentId>] …
    python3 tools/cupel-file-returns.py look --look-dir <dir> --tasks <tasks dir> --brief <brief file> --title "<title>"
               [--date YYYY-MM-DD] [--out <file>] <agentId> …
    python3 tools/cupel-file-returns.py final --tasks <tasks dir> --out <new file> [--header "<text>"] <agentId>[=<label>] …

Folded into tools/ 2026-10-13 (on the editor's approval of folding the recurring scratchpad scripts) from cupel10's
scratch scripts for the slices and the one look (internal records, 2026-10-13, not published) and the filing done
inline all evening (final). A reader's return is the LAST assistant text block of
<tasks>/<agentId>.output (the harness's transcript of a background agent).

slices   a look cut by tools/cupel-look-slices.py: for each slice k, its reader's (or readers', joined in order) final
         text; table rows (leading pipe optional; header and rule rows skipped) matched to the slice's images by
         order — the row count must equal the image count, else it stops before writing anything. Writes
         <returns>/SLICE-kk.return.md (brief, image list, return verbatim), each item's rows verbatim with its
         look/KEY.tsv into <batch>/<stem>/look/RETURN.md, and <returns>/VERDICTS.tsv (slice, stem, image, the verdict
         word matched by --words at the start of the row's second cell). --out-root: write all of it under that
         folder instead (<out-root>/<returns name>/…, <out-root>/<stem>/look/RETURN.md): for tests.
look     one look's readers into <look-dir>/RETURN.md (or --out): heading, the brief, each reader verbatim, KEY.tsv.
final    each agent's final text verbatim into --out, after an optional header; several agents each under «## <label>»
         (the label after «=», else the agent's id).
WRITES only new files (refuses any that exists).
"""
import argparse, datetime, json, os, re, sys
from collections import Counter


def final_text(tasks, agent):
    last = None
    for line in open(os.path.join(tasks, agent + ".output"), encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") == "assistant":
            c = d.get("message", {}).get("content")
            if isinstance(c, list):
                t = [b["text"] for b in c if b.get("type") == "text" and b.get("text", "").strip()]
                if t:
                    last = t[-1]
    if last is None:
        sys.exit(f"{agent}: no final text")
    return last


def table_rows(text):
    out = []
    for l in text.splitlines():
        if l.count("|") < 2:
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].lower() == "image":
            continue
        out.append((l, cells[1]))
    return out


def slices(a):
    pairs = [x.split("=") for x in a.agents]
    lr = os.path.join(a.batch, a.returns) if not os.path.isabs(a.returns) else a.returns
    name = os.path.basename(lr.rstrip("/"))
    out_lr = os.path.join(a.out_root, name) if a.out_root else lr
    brief = open(a.brief, encoding="utf-8").read().strip()
    wre = r"\**\s*(" + a.words + ")"
    sl = {}
    for k, agent in pairs:
        imgs = open(os.path.join(lr, f"SLICE-{int(k):02d}.list")).read().split()
        parts = [final_text(a.tasks, x) for x in agent.split("+")]
        text = "\n\n".join((f"### Reader {i + 1} of {len(parts)}\n\n" if len(parts) > 1 else "") + p.rstrip()
                           for i, p in enumerate(parts))
        r = table_rows(text)
        if len(r) != len(imgs):
            sys.exit(f"slice {k}: {len(r)} rows for {len(imgs)} images; nothing written")
        sl[int(k)] = (imgs, text, r)
    items = {}
    for k in sorted(sl):
        imgs, text, r = sl[k]
        for p, (line, v) in zip(imgs, r):
            rel = os.path.relpath(os.path.realpath(p), os.path.realpath(a.batch))
            if rel.startswith("..") or os.path.isabs(rel):   # an image outside the batch: never write outside it
                sys.exit(f"slice {k}: image outside the batch: {p}; nothing written")
            stem = rel.split(os.sep)[0]
            items.setdefault(stem, []).append((k, p, line, v))
    item_out = (lambda s: os.path.join(a.out_root, s, "look", "RETURN.md")) if a.out_root else \
               (lambda s: os.path.join(a.batch, s, "look", "RETURN.md"))
    targets = [os.path.join(out_lr, f"SLICE-{k:02d}.return.md") for k in sl] + [os.path.join(out_lr, "VERDICTS.tsv")]
    targets += [item_out(s) for s in items]
    clash = [t for t in targets if os.path.exists(t)]
    if clash:
        sys.exit("refusing, exist: " + ", ".join(clash))
    os.makedirs(out_lr, exist_ok=True)
    for k in sorted(sl):
        imgs, text, r = sl[k]
        with open(os.path.join(out_lr, f"SLICE-{k:02d}.return.md"), "x", encoding="utf-8") as f:
            f.write(f"# {a.title} — slice {k:02d} ({len(imgs)} images)\n\n"
                    f"Reader: file-reader agent (Read tool only), {a.date}. Brief word for word, these paths filled in:\n\n"
                    + "".join(f"- `{p}`\n" for p in imgs)
                    + "\n## Brief\n\n> " + brief + "\n\n## Return, verbatim\n\n" + text.rstrip() + "\n")
    verd = ["slice\tstem\timage\tverdict"]
    for stem, rs in items.items():
        key = open(os.path.join(a.batch, stem, "look", "KEY.tsv"), encoding="utf-8").read().rstrip()
        os.makedirs(os.path.dirname(item_out(stem)), exist_ok=True)
        with open(item_out(stem), "x", encoding="utf-8") as f:
            f.write(f"# {stem}: C2 look, the rows verbatim ({len(rs)} images)\n\n"
                    f"From `../../{name}/SLICE-*.return.md` (brief as in the slice return); rows matched to images by order.\n\n"
                    "One line per image: slice · image file · the reader's row, verbatim.\n\n"
                    + "".join(f"- {k:02d} · {os.path.basename(p)} · {line}\n" for k, p, line, v in rs)
                    + "\n## KEY.tsv\n\n```\n" + key + "\n```\n")
        for k, p, line, v in rs:
            w = re.match(wre, v)
            verd.append(f"{k:02d}\t{stem}\t{os.path.basename(p)}\t{w.group(1) if w else 'UNREAD:' + v}")
    with open(os.path.join(out_lr, "VERDICTS.tsv"), "x", encoding="utf-8") as f:
        f.write("\n".join(verd) + "\n")
    for stem, rs in items.items():
        c = Counter(re.match(wre, v).group(1) if re.match(wre, v) else "?" for _, _, _, v in rs)
        print(stem, len(rs), dict(c))
    print("slices", len(sl), "rows", sum(len(v[2]) for v in sl.values()))


def look(a):
    out = a.out or os.path.join(a.look_dir, "RETURN.md")
    if os.path.exists(out):
        sys.exit(f"refusing: {out} exists")
    texts = [final_text(a.tasks, x) for x in a.agents]
    rows = sum(1 for t in texts for l in t.splitlines() if l.count("|") >= 2 and ".png" in l)
    key = open(os.path.join(a.look_dir, "KEY.tsv"), encoding="utf-8").read().rstrip()
    with open(out, "x", encoding="utf-8") as f:
        f.write(f"# {a.title}\n\nReaders: {len(texts)} file-reader agents (Read tool only), {a.date}. The brief, word for word "
                "(the paths filled in, a slice each):\n\n> " + open(a.brief, encoding="utf-8").read().strip() + "\n\n"
                + "".join(f"## Reader {i + 1}, verbatim\n\n{t.rstrip()}\n\n" for i, t in enumerate(texts))
                + "## KEY.tsv (never shown to the readers)\n\n```\n" + key + "\n```\n")
    print(rows, "rows →", out)


def final(a):
    if os.path.exists(a.out):
        sys.exit(f"refusing: {a.out} exists")
    specs = [(x.split("=", 1) + [None])[:2] for x in a.agents]
    parts = [(lab or ag, final_text(a.tasks, ag).rstrip()) for ag, lab in specs]
    body = parts[0][1] + "\n" if len(parts) == 1 else "".join(f"## {lab}\n\n{t}\n\n" for lab, t in parts)
    with open(a.out, "x", encoding="utf-8") as f:
        f.write((a.header.rstrip() + "\n\n" if a.header else "") + body)
    print(len(parts), "return(s) →", a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    today = str(datetime.date.today())
    s = sub.add_parser("slices")
    for k in ("--batch", "--tasks", "--returns", "--brief", "--words"):
        s.add_argument(k, required=True)
    s.add_argument("--title", default="C2 look"); s.add_argument("--date", default=today); s.add_argument("--out-root")
    s.add_argument("agents", nargs="+", help="<k>=<agentId>[+<agentId>]")
    lk = sub.add_parser("look")
    for k in ("--look-dir", "--tasks", "--brief", "--title"):
        lk.add_argument(k, required=True)
    lk.add_argument("--date", default=today); lk.add_argument("--out"); lk.add_argument("agents", nargs="+")
    fn = sub.add_parser("final"); fn.add_argument("--tasks", required=True); fn.add_argument("--out", required=True)
    fn.add_argument("--header"); fn.add_argument("agents", nargs="+", help="<agentId>[=<label>]")
    a = ap.parse_args()
    {"slices": slices, "look": look, "final": final}[a.mode](a)


if __name__ == "__main__":
    main()
