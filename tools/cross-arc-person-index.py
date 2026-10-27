#!/usr/bin/env python3
"""cross-arc-person-index.py — who appears in BOTH the geniza and Interglossa arcs.

WHY THIS EXISTS
---------------
The two arcs of the venture were built independently and share people: Jacob,
Hogben, Pankhurst, Ogden, Morris, Palmer, Jespersen, Manders, the NEF. Neither
arc knew the other's holdings, and that cost real time four times in three days
(the Jacob identification already made in mica-U; the 1944 NEF conference
flagged as "not dispatched" while sitting on disk in the other arc).

This is the fix, and it is a GENERATOR rather than a document because the
editor's standing note is that it "will need to be refreshed a lot". Re-run it;
never hand-edit the output.

WHAT IT DOES
------------
Builds a roster of persons and entities, then scans every .md file in both arcs
for each one, and reports:

  1. BOTH ARCS  — the prize. Anyone here is a cross-arc figure.
  2. GENIZA ONLY
  3. INTERGLOSSA ONLY
  4. NOISE-FLAGGED — roster keys that collide with common words.

ROSTER SOURCES
--------------
  (a) geniza/profiles/*.md basenames — the curated canonical persons.
  (b) tools/cross-arc-roster-extra.txt — one key per line, for Interglossa-side
      figures and entities that have no geniza profile. Edit that file to add
      names; do not edit this script for roster changes.

WHAT IT IS NOT
--------------
It is an INDEX, not a prosopography. A hit means the name occurs in the file,
not that the file says anything substantive. Counts are a triage aid; the
entries are pointers to read, not findings.

Corpus files under sources/ are EXCLUDED by design: this indexes what the
venture has WRITTEN, not the raw material it read. Searching the corpus is what
extract-hits.py and space-tolerant-grep.py are for.

USAGE
    python3 tools/cross-arc-person-index.py            # write the index
    python3 tools/cross-arc-person-index.py --check    # report drift, write nothing
    python3 tools/cross-arc-person-index.py --name jacob   # one name, verbose
"""

import argparse
import datetime
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESOURCES = REPO / "published" / "heterophony-resources"
ARCS = {
    "geniza": RESOURCES / "geniza",
    "interglossa": RESOURCES / "interglossa",
}
PROFILES = ARCS["geniza"] / "profiles"
EXTRA_ROSTER = REPO / "tools" / "cross-arc-roster-extra.txt"
OUTPUT = RESOURCES / "CROSS-ARC-PERSON-INDEX.md"

# Directories never scanned. sources/ is third-party copyright material and is
# gitignored; scans/ and ocr/ are raw corpus; __pycache__ is noise.
SKIP_DIRS = {"sources", "scans", "ocr", "__pycache__", ".git", "pass3-chunks", "pass3-out"}

# Name-particles that must not be taken as the surname key.
PARTICLES = {"de", "van", "von", "der", "den", "la", "le", "du", "di", "da", "y", "el", "al"}

# Roster keys that are also ordinary words in English, Esperanto or Ido, and so
# produce false hits. Flagged rather than dropped: the person may be real and
# the editor should see the collision rather than have the name silently vanish.
NOISY = {
    "mondo": "Esperanto/Ido for 'world'",
    "nemo": "Latin/Ido 'nobody'; also a pseudonym",
    "roze": "Esperanto 'rosily'; also a surname",
    "stor": "substring-prone",
    "moch": "substring-prone",
    "baren": "substring-prone",
    "gross": "German 'gross'; common adjective",
    "noll": "substring-prone",
    "kodr": "abbreviation",
    "klava": "Esperanto 'key-' adjective",
    "titov": "substring-prone",
    "marget": "substring-prone",
    "kombato": "Ido 'combat'",
    "nield": "substring-prone",
    "balod": "substring-prone",
    "bata": "Esperanto 'beating'",
    "uli": "abbreviation (Uniono por la Linguo Internaciona) and a name-fragment",
    "rmu": "abbreviation",
    "emch": "short",
    "gasse": "German 'lane'",
    "moret": "substring-prone",
    "kabe": "pseudonym; also a fragment",
    "juste": "Ido/French 'just'; the surname is real (Andreas Juste)",
    "morris": "common surname; disambiguate Alice Vanderbilt Morris vs Charles Morris",
    "palmer": "common surname",
    "baker": "common noun and surname",
    "richards": "common surname",
    "wilson": "common surname",
    "chandler": "common noun and surname",
    "schmidt": "the venture has a three-Schmidts problem; see profiles/schmidt.md",
    "meier": "multiple bearers; see profiles/meier-ludwig-emil.md",
}


def fold(s: str) -> str:
    """Lowercase and strip diacritics so Hoveler matches Höveler."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def key_from_basename(stem: str) -> str:
    """de-beaufront -> beaufront; baudouin-de-courtenay -> baudouin; o-keeffe -> keeffe."""
    for part in stem.split("-"):
        if len(part) >= 4 and part not in PARTICLES:
            return part
    # fall back to the longest component
    return max(stem.split("-"), key=len)


def load_roster():
    """Returns {key: {'label': str, 'origin': str}} — origin is 'profile' or 'extra'."""
    roster = {}
    if PROFILES.is_dir():
        for p in sorted(PROFILES.glob("*.md")):
            k = key_from_basename(p.stem)
            roster.setdefault(k, {"label": p.stem, "origin": "profile"})
    if EXTRA_ROSTER.is_file():
        for line in EXTRA_ROSTER.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            label, _, key = line.partition("|")
            label = label.strip()
            key = (key.strip() or key_from_basename(fold(label).replace(" ", "-"))).lower()
            if key in roster:
                roster[key]["label"] = f"{roster[key]['label']} / {label}"
            else:
                roster[key] = {"label": label, "origin": "extra"}
    return roster


def md_files(root: Path):
    for p in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.resolve() == OUTPUT.resolve():
            continue
        yield p


def scan(roster):
    """Returns hits[key][arc] = {relpath: count} and a per-arc file tally."""
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(roster, key=len, reverse=True)) + r")\b")
    hits = {k: {a: defaultdict(int) for a in ARCS} for k in roster}
    scanned = {a: 0 for a in ARCS}
    for arc, root in ARCS.items():
        if not root.is_dir():
            print(f"WARNING: {root} not found; arc skipped", file=sys.stderr)
            continue
        for path in md_files(root):
            try:
                text = fold(path.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                print(f"WARNING: could not read {path}: {exc}", file=sys.stderr)
                continue
            scanned[arc] += 1
            rel = path.relative_to(RESOURCES).as_posix()
            for m in pattern.finditer(text):
                hits[m.group(1)][arc][rel] += 1
    return hits, scanned


def top_files(d, n=4):
    return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def fmt_files(d, n=4):
    items = top_files(d, n)
    if not items:
        return "—"
    out = " · ".join(f"`{f}` ({c})" for f, c in items)
    if len(d) > n:
        out += f" · *+{len(d) - n} more*"
    return out


def build(hits, roster, scanned):
    both, geniza_only, ig_only, absent = [], [], [], []
    for key, arcs in hits.items():
        g, i = arcs["geniza"], arcs["interglossa"]
        row = (key, roster[key]["label"], g, i)
        if g and i:
            both.append(row)
        elif g:
            geniza_only.append(row)
        elif i:
            ig_only.append(row)
        else:
            absent.append(row)

    # Cross-arc weight: the SMALLER of the two file counts. A name in 40 geniza
    # files and 1 Interglossa file is weaker evidence of a shared figure than one
    # in 6 and 6.
    both.sort(key=lambda r: (-min(len(r[2]), len(r[3])), -len(r[2]) - len(r[3]), r[0]))
    geniza_only.sort(key=lambda r: (-len(r[2]), r[0]))
    ig_only.sort(key=lambda r: (-len(r[3]), r[0]))

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    A = L.append
    A("# CROSS-ARC PERSON INDEX — geniza ↔ Interglossa")
    A("")
    A(f"**GENERATED by `tools/cross-arc-person-index.py` on {ts}. DO NOT HAND-EDIT — re-run it.**")
    A("")
    A(f"**Scanned:** {scanned['geniza']} geniza `.md` · {scanned['interglossa']} Interglossa `.md` · "
      f"**roster {len(roster)}** ({sum(1 for k in roster if roster[k]['origin'] == 'profile')} from "
      f"`geniza/profiles/`, {sum(1 for k in roster if roster[k]['origin'] == 'extra')} from "
      f"`tools/cross-arc-roster-extra.txt`).")
    A("")
    A("⚠ **This is an INDEX, not a prosopography.** A hit means the name occurs in the file, not that the "
      "file says anything substantive about them. Counts are triage. ⛔ **Corpus files under `sources/` are "
      "excluded by design** — this indexes what the venture has *written*, not what it read.")
    A("")
    A("▶ **To add an Interglossa-side name, edit `tools/cross-arc-roster-extra.txt` and re-run.** "
      "Geniza-side names come from `geniza/profiles/*.md` automatically.")
    A("")
    A("---")
    A("")
    A(f"# ⇒ ★★★★★★ 1. IN BOTH ARCS — {len(both)} names")
    A("")
    A("**These are the figures the venture holds twice over, and did not know it.** *Ordered by the smaller "
      "of the two file counts: a name in 6 geniza files and 6 Interglossa files is a stronger shared figure "
      "than one in 40 and 1.*")
    A("")
    for key, label, g, i in both:
        flag = f" ⚠ *{NOISY[key]}*" if key in NOISY else ""
        A(f"## `{key}` — **{label}**{flag}")
        A("")
        A(f"- **geniza** — {len(g)} files, {sum(g.values())} hits: {fmt_files(g)}")
        A(f"- **Interglossa** — {len(i)} files, {sum(i.values())} hits: {fmt_files(i)}")
        A("")
    A("---")
    A("")
    A(f"# 2. GENIZA ONLY — {len(geniza_only)} names")
    A("")
    A("*Absent from the Interglossa arc. Expected for most of the schism cast; worth a glance for anyone "
      "with a 1940s British connection.*")
    A("")
    A("| key | label | files | top file |")
    A("|---|---|---|---|")
    for key, label, g, _ in geniza_only:
        t = top_files(g, 1)
        A(f"| `{key}` | {label} | {len(g)} | `{t[0][0]}` ({t[0][1]}) |")
    A("")
    A("---")
    A("")
    A(f"# 3. INTERGLOSSA ONLY — {len(ig_only)} names")
    A("")
    A("*From the extra roster, and not found in the geniza arc. ⚠ If one of these SHOULD be in the geniza "
      "arc, that is a gap in the geniza arc, not in this index.*")
    A("")
    A("| key | label | files | top file |")
    A("|---|---|---|---|")
    for key, label, _, i in ig_only:
        t = top_files(i, 1)
        A(f"| `{key}` | {label} | {len(i)} | `{t[0][0]}` ({t[0][1]}) |")
    A("")
    if absent:
        A("---")
        A("")
        A(f"# 4. ⚠ ON THE ROSTER, FOUND IN NEITHER ARC — {len(absent)} names")
        A("")
        A("*Either the key is wrong (check the surname rule in `key_from_basename`), or the profile is a stub "
          "whose subject is never named outside its own filename.*")
        A("")
        A("".join(f"`{k}` · " for k, _, _, _ in sorted(absent)).rstrip(" ·"))
        A("")
    A("---")
    A("")
    A("*Regenerate: `python3 tools/cross-arc-person-index.py`*")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report the cross-arc count; write nothing")
    ap.add_argument("--name", help="report one roster key in detail and exit")
    args = ap.parse_args()

    roster = load_roster()
    if not roster:
        sys.exit("ERROR: empty roster — is geniza/profiles/ present?")
    hits, scanned = scan(roster)

    if args.name:
        k = args.name.lower()
        if k not in hits:
            sys.exit(f"'{k}' is not a roster key. Add it to {EXTRA_ROSTER.name} or check the spelling.")
        for arc in ARCS:
            d = hits[k][arc]
            print(f"\n{arc}: {len(d)} files, {sum(d.values())} hits")
            for f, c in top_files(d, 30):
                print(f"  {c:5d}  {f}")
        return

    both = sum(1 for k in hits if hits[k]["geniza"] and hits[k]["interglossa"])
    if args.check:
        print(f"roster {len(roster)} · both-arc {both} · "
              f"scanned {scanned['geniza']}+{scanned['interglossa']} files")
        return

    OUTPUT.write_text(build(hits, roster, scanned), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO)}")
    print(f"roster {len(roster)} · BOTH ARCS {both} · "
          f"scanned {scanned['geniza']} geniza + {scanned['interglossa']} Interglossa files")


if __name__ == "__main__":
    main()
