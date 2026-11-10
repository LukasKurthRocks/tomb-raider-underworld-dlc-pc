"""List the static quick bar layout of TruMenu.cpp: every `const QbRow kQb...[]` array with its rows (kind, German
label, item id, argument) and the page table kQbPages with the array each page shows and its row count (read-only;
menu plan 2026-11-10, Plan-TruMenu-Einstellungen-1011.md). Groups (kQbGroup) are shown as '== <label>'.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_qb_layout.py [src/asi/TruMenu/TruMenu.cpp] [--brief]
      --brief: only the page table and the rows / groups per array
"""
import sys, re

ROW = re.compile(r'^\s*\{\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
                 r'"((?:[^"\\]|\\.)*)"\s*,\s*(kQb[A-Za-z]+)')
ARR = re.compile(r'^const QbRow (kQb[A-Za-z0-9_]+)\[\]\s*=\s*\{')
PAGE = re.compile(r'^\s*(?:QB_PAGE\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*(kQb[A-Za-z0-9_]+)\s*,\s*(kQs[A-Za-z]+)'
                  r'|\{\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*nullptr\s*,\s*0\s*,\s*(kQs[A-Za-z]+))')


def unescape(s):
    # the labels hold octal UTF-8 escapes (\303\244); turn them back into text for the listing
    b = bytearray()
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 3 < len(s) + 1 and re.match(r'[0-7]{3}', s[i + 1:i + 4]):
            b.append(int(s[i + 1:i + 4], 8)); i += 4
        elif s[i] == '\\' and i + 1 < len(s):
            b += s[i + 1].encode(); i += 2
        else:
            b += s[i].encode('utf-8'); i += 1
    return b.decode('utf-8', 'replace')


def main(argv):
    path = 'src/asi/TruMenu/TruMenu.cpp'
    brief = '--brief' in argv
    args = [a for a in argv if not a.startswith('--')]
    if args: path = args[0]
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    arrays, cur, pages, in_pages = {}, None, [], False
    for ln in lines:
        m = ARR.match(ln)
        if m:
            cur = m.group(1); arrays[cur] = []; continue
        if ln.startswith('const QbPage kQbPages[]'):
            in_pages = True; cur = None; continue
        if in_pages:
            if ln.startswith('};'): in_pages = False; continue
            p = PAGE.match(ln)
            if p:
                if p.group(1) is not None: pages.append((unescape(p.group(1)), p.group(2), p.group(3), p.group(4)))
                else: pages.append((unescape(p.group(5)), p.group(6), None, p.group(7)))
            continue
        if cur:
            if ln.startswith('};'): cur = None; continue
            r = ROW.match(ln)
            if r: arrays[cur].append((r.group(5), unescape(r.group(1)), r.group(3), r.group(4)))
    print('pages: %d' % len(pages))
    for k, (de, en, arr, sp) in enumerate(pages):
        rows = arrays.get(arr, []) if arr else []
        groups = sum(1 for r in rows if r[0] == 'kQbGroup')
        print('%2d  %-24s %-22s %-14s %-15s rows %3d  groups %d' % (k, de, en, arr or '-', sp, len(rows) - groups, groups))
    for name, rows in arrays.items():
        groups = sum(1 for r in rows if r[0] == 'kQbGroup')
        print('\n%s: %d rows, %d groups' % (name, len(rows) - groups, groups))
        if brief:
            for kind, de, item, arg in rows:
                if kind == 'kQbGroup': print('  == %s' % de)
            continue
        for kind, de, item, arg in rows:
            if kind == 'kQbGroup': print('  == %s  [%s]' % (de, arg))
            else: print('     %-10s %-42s %s %s' % (kind[3:], de, item, arg))


if __name__ == '__main__':
    main(sys.argv[1:])
