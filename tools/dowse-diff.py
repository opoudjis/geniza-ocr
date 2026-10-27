#!/usr/bin/env python3
"""Compare two dowse runs of the same source: old and new <record>.hits.tsv, person by person and page by page.

Ruled 2026-10-08 (the dowse runbook, D6a, «One dowse per source»): a redowse is a diff before it is a
replacement. Run the new dowse to a scratch path, run this, write its report into the source's LOG.md,
and only then let the new outputs replace the old.

LOSSES COME FIRST (the rule after the W fixes: diff for what silently disappeared). The report, in order:
  1. scope: items searched in one run and not the other; items now read from a different text file;
  2. losses: persons with no hit at all in the new run; pages lost, per person; pages where a person's
     best tier got weaker;
  3. gains: the same three, the other way;
  4. a table, one row per person: pages before, pages after, lost, gained, tier changes.

A «page» is (item, page) for one person; its tier is the strongest tier among that person's hits on it.
Tiers are read from tools/ocr-dowse.py (TIERS, strongest first), so the two tools cannot drift apart.

Read-only on its inputs. Prints the report; with --write PATH writes it there instead, and refuses an
existing file.

  python3 tools/dowse-diff.py OLD.hits.tsv NEW.hits.tsv [--write report.md]
"""
import argparse
import ast
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def tiers():
    """TIERS from ocr-dowse.py, without importing it (the name has a hyphen, and importing runs nothing we need)."""
    tree = ast.parse(open(os.path.join(HERE, 'ocr-dowse.py'), encoding='utf-8').read())
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                consts[name] = node.value.value
            elif name == 'TIERS' and isinstance(node.value, ast.Tuple):
                out = []
                for e in node.value.elts:
                    if isinstance(e, ast.Constant):
                        out.append(e.value)
                    elif isinstance(e, ast.Name) and e.id in consts:
                        out.append(consts[e.id])
                    else:
                        sys.exit(f'dowse-diff: cannot read TIERS in ocr-dowse.py (element {ast.dump(e)})')
                return out
    sys.exit('dowse-diff: TIERS not found in ocr-dowse.py')


TIERS = tiers()


def rank(t):
    return TIERS.index(t) if t in TIERS else len(TIERS)   # an unknown tier counts as weakest


def load(path):
    """-> header line, {person: {(item, page): best tier}}, {item: set of text files}, hit count"""
    header, pages, texts, n = '', defaultdict(dict), defaultdict(set), 0
    with open(path, encoding='utf-8') as fh:
        first = fh.readline()
        if first.startswith('#'):
            header = first.lstrip('# ').strip()
        else:
            fh.seek(0)
        # ocr-dowse.py writes plain tab-joined lines, no quoting: an OCR «"» must not open a quoted field
        for r in csv.DictReader(fh, delimiter='\t', quoting=csv.QUOTE_NONE):
            if not r.get('person'):
                continue
            n += 1
            key = (r['item'], r['page'])
            old = pages[r['person']].get(key)
            if old is None or rank(r['tier']) < rank(old):
                pages[r['person']][key] = r['tier']
            texts[r['item']].add(r['text'])
    return header, pages, texts, n


def pagekey(k):
    item, page = k
    return (item, int(page) if page.isdigit() else 10**9, page)


def fmt(keys, tiers_of=None):
    by_item = defaultdict(list)
    for k in sorted(keys, key=pagekey):
        by_item[k[0]].append(k[1] + (f' ({tiers_of[k]})' if tiers_of else ''))
    return '; '.join(f'`{it}` p. {", ".join(ps)}' for it, ps in by_item.items())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--write', help='write the report here (refuses an existing file)')
    a = ap.parse_args()
    if a.write and os.path.exists(a.write):
        sys.exit(f'dowse-diff: {a.write} exists; not overwriting it')
    oh, old, otext, on = load(a.old)
    nh, new, ntext, nn = load(a.new)
    L = []
    w = L.append
    w(f'# dowse diff: {os.path.basename(a.old)} → {os.path.basename(a.new)}\n')
    w(f'Old: `{a.old}`, {on} hits, {len(old)} persons ({oh or "no header"}).  ')
    w(f'New: `{a.new}`, {nn} hits, {len(new)} persons ({nh or "no header"}).  ')
    w(f'Tiers, strongest first (from tools/ocr-dowse.py): {", ".join(TIERS)}. A page is one person on one page of one item, at the strongest tier of their hits there.\n')

    w('## 1. Scope\n')
    gone, came = sorted(set(otext) - set(ntext)), sorted(set(ntext) - set(otext))
    reread = sorted(i for i in set(otext) & set(ntext) if otext[i] != ntext[i])
    w('Items with hits in the old run and none in the new (searched no longer, or no hits now): ' + (', '.join(f'`{i}`' for i in gone) or 'none') + '.  ')
    w('Items with hits in the new run and none in the old: ' + (', '.join(f'`{i}`' for i in came) or 'none') + '.  ')
    w('Items read from a different text file: ' + ('; '.join(f'`{i}`: {sorted(otext[i])} → {sorted(ntext[i])}' for i in reread) or 'none') + '.\n')

    persons = sorted(set(old) | set(new))
    stats = {}
    lost_p, lost_pg, weaker, gain_p, gain_pg, stronger = [], [], [], [], [], []
    for p in persons:
        o, n = old.get(p, {}), new.get(p, {})
        lp, gp = set(o) - set(n), set(n) - set(o)
        wk = {k for k in set(o) & set(n) if rank(n[k]) > rank(o[k])}
        st = {k for k in set(o) & set(n) if rank(n[k]) < rank(o[k])}
        stats[p] = (len(o), len(n), len(lp), len(gp), len(wk) + len(st))
        if o and not n:
            lost_p.append(p)
        elif lp:
            lost_pg.append((p, lp, o))
        if wk:
            weaker.append((p, wk, o, n))
        if n and not o:
            gain_p.append(p)
        elif gp:
            gain_pg.append((p, gp, n))
        if st:
            stronger.append((p, st, o, n))

    w('## 2. Losses (read these first)\n')
    w(f'### Persons with no hit at all in the new run ({len(lost_p)})\n')
    for p in lost_p:
        w(f'- **{p}**: had {len(old[p])} pages: {fmt(old[p], old[p])}')
    w('' if lost_p else 'None.')
    w(f'\n### Pages lost, per person ({sum(len(x[1]) for x in lost_pg)} pages, {len(lost_pg)} persons)\n')
    for p, ks, o in sorted(lost_pg, key=lambda x: -len(x[1])):
        w(f'- **{p}** ({len(ks)} of {len(o)}): {fmt(ks, o)}')
    w('' if lost_pg else 'None.')
    w(f'\n### Pages where the best tier got weaker ({sum(len(x[1]) for x in weaker)})\n')
    for p, ks, o, n in weaker:
        w(f'- **{p}**: ' + '; '.join(f'`{k[0]}` p. {k[1]} {o[k]} → {n[k]}' for k in sorted(ks, key=pagekey)))
    w('' if weaker else 'None.')

    w('\n## 3. Gains\n')
    w(f'### Persons new in this run ({len(gain_p)})\n')
    for p in gain_p:
        w(f'- **{p}**: {len(new[p])} pages: {fmt(new[p], new[p])}')
    w('' if gain_p else 'None.')
    w(f'\n### Pages gained, per person ({sum(len(x[1]) for x in gain_pg)} pages, {len(gain_pg)} persons)\n')
    for p, ks, n in sorted(gain_pg, key=lambda x: -len(x[1])):
        w(f'- **{p}** ({len(ks)}): {fmt(ks, n)}')
    w('' if gain_pg else 'None.')
    w(f'\n### Pages where the best tier got stronger ({sum(len(x[1]) for x in stronger)})\n')
    for p, ks, o, n in stronger:
        w(f'- **{p}**: ' + '; '.join(f'`{k[0]}` p. {k[1]} {o[k]} → {n[k]}' for k in sorted(ks, key=pagekey)))
    w('' if stronger else 'None.')

    w('\n## 4. Per person\n')
    w('| person | pages before | pages after | lost | gained | tier changed |')
    w('|---|---|---|---|---|---|')
    for p in sorted(persons, key=lambda p: (-stats[p][2], -stats[p][4], -stats[p][3], p)):
        s = stats[p]
        if s[2] or s[3] or s[4]:
            w(f'| {p} | {s[0]} | {s[1]} | {s[2]} | {s[3]} | {s[4]} |')
    same = sum(1 for p in persons if not any(stats[p][2:]))
    w(f'\nUnchanged: {same} of {len(persons)} persons (not listed).')
    out = '\n'.join(L) + '\n'
    if a.write:
        open(a.write, 'w', encoding='utf-8').write(out)
        print(f'dowse-diff: wrote {a.write}')
    else:
        sys.stdout.write(out)


if __name__ == '__main__':
    main()
