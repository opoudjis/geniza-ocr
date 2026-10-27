#!/usr/bin/env python3
"""dowse-context.py: the input for a dowse's context reading (the dowse runbook, D3), built from its hits table.

A dowse record says where a name occurs, not what is true of the person; the context reading (a reader sorts each
roster entry into NAMED, NOISE or MIXED, says who is meant and what the passage says) is what turns it into facts.
This builds the reader's input: per roster entry, the pages it was hit on (by item) and up to N snippets cut from
the very text the hit was read in, around the word as read. Entries with the most pages come first.

The Waringhien 1959 input (2026-10-07) was made by a one-off script; this is that step as a tool (2026-10-08, for the
Neves dowse, the first in the one-folder-per-source layout of runbook D6a).

  python3 tools/dowse-context.py dowse/<source>/record.hits.tsv --write dowse/<source>/context-input.md
        [--tiers exact] [--snippets 4] [--width 110] [--root geniza/sources] [--title "…"]

Text paths in the hits table are relative to --root (default: the geniza's sources/). Pages are found by the
«=== page N ===» markers. Refuses an existing --write file. Reads the table as plain tab-split lines (an OCR «"» must
not open a quoted field: see dowse-diff.py)."""
import argparse
import csv
import os
import re
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(REPO, 'published', 'heterophony-resources', 'geniza', 'sources')


def pages_of(path, cache={}):
    if path not in cache:
        txt = open(path, encoding='utf-8', errors='replace').read()
        parts = re.split(r'^=== page (\d+) ===\s*$', txt, flags=re.M)
        cache[path] = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    return cache[path]


def snippet(text, word, width):
    flat = re.sub(r'\s+', ' ', text)
    i = flat.find(word)
    if i < 0:
        i = flat.lower().find(word.lower())
    if i < 0:
        return None
    return '…' + flat[max(0, i - width):i + len(word) + width].strip() + '…'


# Words too common to place a body by (2026-10-13, the editor's to the token-economy measurements,
# ocr/method/DOWSE-TOKEN-ECONOMY-MEASUREMENTS-2026-10-13.md): «Akademio de Esperanto» was read on every «Esperanto».
# For a roster entry of two or more words, a page whose only hits are such words is kept only if the entry's full
# name stands on the page.
GENERIC = {'esperanto', 'ido', 'lingvo', 'internacia', 'internaciona', 'akademio', 'revuo', 'ondo', 'scienca',
           'ligo', 'unuiĝo', 'societo', 'grupo', 'kongreso', 'universala', 'gazeto', 'oficiala', 'komitato',
           'lingva', 'esperantista', 'esperantisto', 'esperantistoj', 'la', 'de', 'kaj', 'por'}


def short_forms():
    """Confirmed «short form» rows of the names register (the editor 2026-10-13): roster entry (slug of the main
    form) -> [(forms, side or None, main form)]. A form with a capital is matched with its case («la Revuo»)."""
    p = os.path.join(REPO, 'published', 'heterophony-resources', 'geniza', 'profiles', 'NAMES-REGISTER.tsv')
    out = defaultdict(list)
    if not os.path.exists(p):
        return out
    for l in open(p, encoding='utf-8'):
        f = l.rstrip('\n').split('\t')
        if len(f) < 9 or not f[3].startswith('short form') or f[7] != 'confirmed':
            continue
        name, main = f[0], f[2].split(' (')[0]
        forms = [name.split(' (')[0].strip()] + re.findall(r'«([^«»]+)»', name)
        forms += [x.strip() for x in re.findall(r'also ([^)]*)', name)[0].split(',')] if 'also ' in name else []
        forms += [x for x in re.findall(r'\(([A-Z][^)]*)\)', name) if ' ' in x or x.isupper()]
        side = 'Ido' if 'Ido-side' in name else 'Esperanto' if 'Esperanto-side' in name else None
        slug = re.sub(r'[^\w]+', '-', main.lower()).strip('-')
        out[slug].append(([x for x in dict.fromkeys(forms) if x], side, main))
    return out


def side_of(item, cache={}):
    """The side of an item from the item table's bpeape column («none: Ido» …); Esperanto otherwise."""
    if not cache:
        p = os.path.join(REPO, 'published', 'heterophony-resources', 'geniza', 'OCR-ITEM-TABLE.tsv')
        for l in open(p, encoding='utf-8'):
            f = l.split('\t')
            if len(f) > 3 and not l.startswith('#'):
                cache[f[0]] = 'Ido' if 'Ido' in f[3] else 'Occidental' if 'Occidental' in f[3] else 'Esperanto'
    return cache.get(item, 'Esperanto')


def short_form_on(text, forms):
    flat = re.sub(r'\s+', ' ', text)
    def rx(x):                                  # «la Revuo» also at a sentence's start: «La Revuo»
        r = re.escape(x).replace(r'\ ', r'\s*')
        return ('[Ll]' + r[1:] if x[:1] in 'lL' and x[1:3].lower() == 'a ' else r)
    return next((x for x in forms if re.search(r'(?<!\w)' + rx(x) + r'(?!\w)', flat,
                                                0 if any(c.isupper() for c in x) else re.I)), None)


def bare(w):
    return re.sub(r'[^\w-]', '', w.lower()).strip('-')


def full_name_on(text, entry):
    words = [w for w in re.split(r'[-\s]+', entry.lower()) if w]
    if all(w in GENERIC for w in words):        # a name of common words only («La Revuo»): its content words capitalised
        pat = r'\W+'.join(f'[{w[0].upper()}{w[0]}]{re.escape(w[1:])}' if w in ('la', 'de', 'kaj', 'por')
                          else re.escape(w.capitalize()) for w in words)
        return re.search(pat, re.sub(r'\s+', ' ', text)) is not None
    return re.search(r'\W+'.join(re.escape(w) for w in words), re.sub(r'\s+', ' ', text.lower())) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hits')
    ap.add_argument('--write', required=True)
    ap.add_argument('--tiers', default='exact', help='comma list of tiers to include (default: exact)')
    ap.add_argument('--snippets', type=int, default=4)
    ap.add_argument('--width', type=int, default=110)
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    if os.path.exists(a.write):
        sys.exit(f'dowse-context: {a.write} exists; not overwriting it')
    keep = set(t.strip() for t in a.tiers.split(','))
    hits = defaultdict(lambda: defaultdict(set))       # person -> (item, page) -> words as read
    forms = defaultdict(set)
    texts = {}
    with open(a.hits, encoding='utf-8') as fh:
        head = fh.readline()
        if not head.startswith('#'):
            fh.seek(0)
        for r in csv.DictReader(fh, delimiter='\t', quoting=csv.QUOTE_NONE):
            if not r.get('person') or r['tier'] not in keep:
                continue
            hits[r['person']][(r['item'], r['page'])].add(r['as_read'])
            forms[r['person']].add(r['as_read'])
            texts[r['item']] = os.path.join(a.root, r['text'])
    L = [f'# Context reading input{": " + a.title if a.title else ""}\n',
         f'`[GENERATED by tools/dowse-context.py from {a.hits} ({head.lstrip("# ").strip()}); tiers: {", ".join(sorted(keep))}; '
         f'{len(hits)} roster entries; per entry the pages (by item) and up to {a.snippets} snippets from the text each hit was read in.]`\n',
         'Items: ' + '; '.join(f'`{i}` ({os.path.relpath(t, a.root)})' for i, t in sorted(texts.items())) + '\n']
    dropped, by_short = {}, defaultdict(lambda: defaultdict(int))
    SF = short_forms()
    for p in list(hits):
        if len([w for w in re.split(r'[-\s]+', p) if w]) < 2:
            continue
        gone = []
        for k, ws in hits[p].items():
            if not all(bare(w) in GENERIC for w in ws):
                continue
            text = pages_of(texts[k[0]]).get(k[1], '')
            if full_name_on(text, p):
                continue
            side = side_of(k[0])          # a confirmed short form for this entry, on this item's side, keeps the page
            sf = next(((x, main) for forms, sd, main in SF.get(p, []) if sd in (None, side)
                       for x in [short_form_on(text, forms)] if x), None)
            if sf:
                by_short[p][f'«{sf[0]}» ({side} side: {sf[1]})'] += 1
            else:
                gone.append(k)
        for k in gone:
            del hits[p][k]
        if gone:
            dropped[p] = len(gone)
        if not hits[p]:
            del hits[p]
    whole = sorted(p for p in dropped if p not in hits)
    if whole:
        L.append(f'Left out entirely, every page matched only by common words and the full name on none: {", ".join(whole)}.\n')
    seen = {}                                           # (item, page, snippet) -> the entry it was first shown under
    for p in sorted(hits, key=lambda p: (-len(hits[p]), p)):
        ks = sorted(hits[p], key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else 10**9))
        note = f' ({dropped[p]} pages matched only by common words left out)' if p in dropped else ''
        if p in by_short:
            note += (' (by a short form only, the names register\'s default for that side, which the reader overrides '
                     'where the passage means another body: ' + '; '.join(f'{n} pages {s}' for s, n in by_short[p].items()) + ')')
        L.append(f'## {p} — {len(ks)} pages{note}; forms read: {", ".join(sorted(forms[p]))[:300]}')
        by_item = defaultdict(list)
        for it, pg in ks:
            by_item[it].append(pg)
        L.append('pages: ' + '; '.join(f'{it} p. {", ".join(pgs)}' for it, pgs in by_item.items()))
        shown = 0
        for it, pg in ks:
            if shown >= a.snippets:
                break
            text = pages_of(texts[it]).get(pg, '')
            for w in sorted(hits[p][(it, pg)]):
                s = snippet(text, w, a.width)
                if s:
                    if (it, pg, s) in seen:                 # shown once; here only pointed to
                        L.append(f'- {it} p. {pg}: the same passage as under «{seen[(it, pg, s)]}»')
                    else:
                        seen[(it, pg, s)] = p
                        L.append(f'- {it} p. {pg}: {s}')
                    shown += 1
                    break
        L.append('')
    os.makedirs(os.path.dirname(os.path.abspath(a.write)), exist_ok=True)
    open(a.write, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print(f'dowse-context: {len(hits)} entries → {a.write}')


if __name__ == '__main__':
    main()
