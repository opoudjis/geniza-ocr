#!/usr/bin/env python3
r"""ocr-psm-adjudicate — did the --psm 4 reading actually beat the --psm 6 one, on THIS page?

    tools/ocr-psm-adjudicate.py <root>              # measure and report; writes nothing
    tools/ocr-psm-adjudicate.py <root> --write      # record the verdicts (still rewrites no text)

WHY THIS IS MEASURED AND NOT ASSUMED. `--psm 4` is the right mode for a list and the prior is
strong — one Kongresa Libro volume went from 977 page-level errors to 77. **A prior is not a
measurement**, and the whole week's lesson is that plausible beliefs about OCR are wrong about a
fifth of the time in ways nothing downstream catches.

AND THE OBVIOUS MEASURE IS THE WRONG ONE. «Keep the longer text» would have REJECTED the
reading that mattered most: on Belga Esperantisto the `--psm 4` repass recovered **266 more
complete roster entries out of 1.5% LESS text.** The characters were always there; what changed
is that they became attached to each other again —

    psm 6:   155.        156.        157.       ← a column of bare numbers
             Harvey, William, civila servisto, Comiston Drive, 31, Edinburg, (Skotl.)
    psm 4:   157. D-ro Staniŝiĉ, Paŭlo, advokato, Vinkovci, (Hung.)

So the measure is STRUCTURAL, not volumetric: how many lines are a complete entry — an index
or a name followed by the fields belonging to it. A roster's value is the ASSOCIATION between a
number, a person, a place and a trade; text that has the same characters with the associations
severed is not 98.5% as good, it is worthless for the only question anyone asks of a roster.

RULE E — IN FORCE FROM 2026-09-26 (approved by the editor). Supersedes the rule below it.

    PROSE pages (84%): the reading with the MOST RECOGNISED WORDS wins, by > max(2, 2%) over
                       psm 6; otherwise psm 6 holds. Entry-form lines play no part.
    LIST pages (16%, shape ≥ 0.55 — the G3 test): among readings within that margin of the best
                       word count, the one with MORE ENTRY-FORM LINES wins; psm 6 holds a tie.

  Editor's principle: structure is not to take priority over words, since missed structure is
  more remediable than missed words; but a more contained subcorpus was needed. The evidence:
    · «Entries first» let a FOREIGN reading win on its line breaks: the PDF text layer took 9,514
      pages with fewer words (−395,053). The entry pattern also matches prose (`Sed, kiel ni
      vidis, …`): 34,873 prose pages had been decided on it.
    · Re-run on the recorded figures: prose words +522,255 (+2%); lists keep all but 430 of the
      words-only total and 41% of the extra structure.
    · Blind looks: 14 list pages E 8 · A 5 · tie 1; then 40 pages from 40 titles E 26 · A 13 ·
      tie 1 (an internal record, 2026-09-26, not published). The «content count» (words + numbers + names) did not
      beat the plain count at 40 pages, so the plain count stays.

THE RULE BEFORE 2026-09-26, in order:
  1. more ENTRY-FORM lines wins — the association is the content
  2. on a tie, MORE RECOGNISED WORDS wins (a clear margin: > max(2, 2%))
  3. on a tie, KEEP psm 6 — the incumbent holds unless displaced, because it is the reading the
     rest of the corpus was measured against

RULE 2 WAS «HIGHER HIT-RATE» UNTIL 2026-09-25, AND THAT WAS A TRAP (change approved by the editor). A
rate ignores HOW MUCH was read: *Internacia Socia Revuo* 1907 p.11 read 214 characters at 93.8%
and 1,019 at 61.3% — the rate crowns the reading that barely saw the page. The COUNT of words the
lexicons recognise rewards reading more and still punishes noise, which adds no recognised words.
Recognised = in ANY planned lexicon (Esperanto, Ido, Occidental), since both readings of a page
are the same language and only the comparison matters.

UP TO FOUR READINGS PER PAGE (2026-09-25). Besides `page-NNNN.txt` (psm 6) and `.psm4.txt`,
a page stored as a low-ppi colour layer + sharp text mask has `.hr.txt` / `.hr.psm4.txt` — the
same two modes at the MASK's resolution (tools/ocr-mask-reread.py). All present readings compete
under the same rule; `winner` is one of psm6 · psm4 · hr6 · hr4.

WRITES NOTHING BUT A VERDICT FILE. The combined text is rebuilt in a separate, deliberate step
on the editor's word. Both readings stay on disk either way; this only records which won and why.
"""
import os, re, sys, glob, json, argparse, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
LEXES = [os.path.join(HERE, "lexicons", n + ".txt") for n in ("esperanto", "ido", "occidental")]
import importlib.util as _ilu
_s = _ilu.spec_from_file_location("ocr_accept", os.path.join(HERE, "ocr-accept.py"))
_acc = _ilu.module_from_spec(_s); _s.loader.exec_module(_acc)
SHAPE, SHAPE_CUT = _acc.shape_score, 0.55    # the G3 list test

SUFFIX = {"psm6": ".txt", "psm4": ".psm4.txt", "hr6": ".hr.txt", "hr4": ".hr.psm4.txt",
          "tl": ".tl.txt"}   # tl = the PDF's own text layer (tools/ocr-textlayer.py), 2026-09-26
WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

# A line that carries an ENTRY: an index number or a surname, followed by its fields.
NUMBERED = re.compile(r"^\s*\d{1,4}\s*[.,)]\s*\S.*?,")          # «157. Staniŝiĉ, Paŭlo, advokato,»
SURNAME  = re.compile(r"^\s*[^\W\d_][\w'’\-]{1,}\s*,\s*\S.*?,", re.UNICODE)  # «Harvey, William, …,»
BARE_NUM = re.compile(r"^\s*\d{1,4}\s*[.,)]?\s*$")              # «155.» alone — the severed form


def profile(text):
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    entries = sum(1 for l in lines if NUMBERED.match(l) or SURNAME.match(l))
    orphans = sum(1 for l in lines if BARE_NUM.match(l))
    toks = [m.group(0).lower() for m in WORD.finditer(text)]
    return {"chars": len(text), "lines": len(lines), "entries": entries,
            "orphans": orphans, "tokens": len(toks)}


LIST_KEEP = 0.95   # list pages: share of the best word count a reading must keep to be in contention (2026-10-04)
# Items whose list pages keep the choice as it was before 2026-10-04 (the old margin only). The editor ruled, 2026-10-04 21:5x,
# on La Revuo 1913.0.1 (signed 2 Oct; the new rule took it from G4 65.2 to 64.8, under the list bar of 65), that it be
# kept admissible as an exception.
LIST_RULE_EXEMPT = {"larevuo.1913.0.1"}


def choose(cand, is_list, exempt=False):
    """The choice, from per-reading counts {reading: (entries, recognised, …)}; psm6 must be present.
    exempt: an item in LIST_RULE_EXEMPT — its list pages are judged by the old margin only."""
    inc = cand["psm6"][1]
    bw = max(c[1] for c in cand.values())
    margin = max(2, 0.02 * max(bw, 1))
    if is_list:
        near = {k: v for k, v in cand.items() if (v[1] >= LIST_KEEP * bw and not exempt) or bw - v[1] <= margin}
        top_e = max(v[0] for v in near.values())
        top = [k for k, v in near.items() if v[0] == top_e]
        best_top = max(top, key=lambda k: cand[k][1])
        # among readings with the most entries, the one with most words wins; psm 6 holds only if it is level on
        # words within the old margin (else the widened field would let psm 6 win ties it loses on words)
        if "psm6" in top and cand[best_top][1] - cand["psm6"][1] <= margin:
            return "psm6", ("list: tie — incumbent holds" if len(near) > 1 else "list: words")
        return best_top, ("list: entries break a near-tie" if len(near) > 1 else "list: words")
    best = max(cand, key=lambda k: cand[k][1])
    win = best if cand[best][1] - inc > max(2, 0.02 * max(inc, 1)) else "psm6"
    return win, ("prose: words" if win != "psm6" else "prose: tie — incumbent holds")


def rechoose(src, dst):
    """Re-apply the choice to the counts stored in a verdicts file (no OCR, no reading of pages): the list-page
    rule changed on 2026-10-04. Writes a NEW file (refuses an existing one); every other field is kept."""
    if os.path.exists(dst):
        sys.exit(f"exists: {dst}")
    v = json.load(open(src, encoding="utf-8")); moved = collections.Counter()
    for x in v:
        cand = {k: (x["entries_" + k], x["recognised_" + k]) for k in ("psm6", "psm4", "hr6", "hr4", "tl")
                if x.get("entries_" + k) is not None and x.get("recognised_" + k) is not None}
        if "psm6" not in cand or len(cand) < 2:
            continue
        win, why = choose(cand, x.get("why", "").startswith("list"), x["page"].split("/")[0] in LIST_RULE_EXEMPT)
        if win != x["winner"]:
            moved[(x["winner"], win)] += 1
            x["winner_before_2026_10_04"] = x["winner"]
        x["winner"], x["why"] = win, why
    json.dump(v, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(v)} verdicts; {sum(moved.values())} winners changed → {dst}")
    for (a_, b_), n in moved.most_common():
        print(f"  {a_} → {b_}: {n}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--write", default=None, help="path for the verdict file")
    ap.add_argument("--rechoose", default=None, help="re-apply the choice to this verdicts file (root is then ignored); --write is the new file")
    a = ap.parse_args()
    if a.rechoose:
        if not a.write:
            sys.exit("--rechoose needs --write <new file>")
        return rechoose(a.rechoose, a.write)

    lex = set()
    for p in LEXES:
        if os.path.exists(p):
            lex |= {w.strip().lower() for w in open(p, encoding="utf-8") if w.strip()}

    def recognised(text):
        return sum(1 for m in WORD.finditer(text) if m.group(0).lower() in lex)

    verdicts, tally, why_t = [], collections.Counter(), collections.Counter()
    agg = collections.Counter()
    for base in sorted(glob.glob(os.path.join(a.root, "*", "page-*.txt"))):
        if not re.search(r"page-\d+\.txt$", base):
            continue                                   # a .psm4 / .hr variant, not a base page
        stem = base[:-len(".txt")]
        cand = {}
        for k, suf in SUFFIX.items():
            p = stem + suf
            if os.path.exists(p):
                t = open(p, encoding="utf-8", errors="ignore").read()
                pr = profile(t)
                cand[k] = (pr["entries"], recognised(t), pr["orphans"], pr["chars"])
        if len(cand) < 2:
            continue
        # RULE E (approved by the editor, 2026-09-26). WORDS FIRST EVERYWHERE; structure only breaks
        # near-ties, and only on LIST-SHAPED pages. See the docstring for the evidence.
        is_list = SHAPE(open(base, encoding="utf-8", errors="ignore").read()) >= SHAPE_CUT
        win, why = choose(cand, is_list, os.path.basename(os.path.dirname(base)) in LIST_RULE_EXEMPT)   # RULE E, with the list-page amendment of 2026-10-04 (choose(), above)
        tally[win] += 1; why_t[why] += 1
        agg["entries_6"] += cand["psm6"][0]; agg["entries_w"] += cand[win][0]
        agg["orphans_6"] += cand["psm6"][2]; agg["orphans_w"] += cand[win][2]
        agg["chars_6"] += cand["psm6"][3];   agg["chars_w"] += cand[win][3]
        agg["rec_6"] += cand["psm6"][1];     agg["rec_w"] += cand[win][1]
        v = {"page": os.path.relpath(base, a.root), "winner": win, "why": why,
             "entries_psm6": cand["psm6"][0], "entries_psm4": cand.get("psm4", (0,))[0]}
        for k, c in cand.items():
            v["entries_" + k] = c[0]; v["recognised_" + k] = c[1]
        verdicts.append(v)

    n = len(verdicts)
    print(f"\n{n:,} pages adjudicated\n")
    for k, v in tally.most_common():
        print(f"  {v:>6,}  {k} wins   ({100*v/max(n,1):.0f}%)")
    print("  decided by: " + " · ".join(f"{k} {v:,}" for k, v in why_t.most_common()))
    for lab, k in (("ENTRY-FORM LINES", "entries"), ("RECOGNISED WORDS", "rec"),
                   ("ORPHANED BARE NUMBERS", "orphans"), ("characters", "chars")):
        b, w = agg[k + "_6"], agg[k + "_w"]
        print(f"  {lab:<22} psm6 {b:>9,}  →  chosen {w:>9,}   ({w-b:+,})")
    if a.write:
        json.dump(verdicts, open(a.write, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"\nwrote {a.write}")


if __name__ == "__main__":
    main()
