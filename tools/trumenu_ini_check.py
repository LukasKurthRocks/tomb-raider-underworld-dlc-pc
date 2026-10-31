"""Check that the shipped src/asi/TruMenu/TruMenu.ini is exactly the text TruMenu writes from its defaults table
(kOpts in TruMenu.cpp, DefaultIniText) - read-only.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_ini_check.py            compare, print the first difference; exit 1 on a mismatch
  ../bin/pyt -t 60 tools/trumenu_ini_check.py --print    print the text generated from the table
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
INI = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.ini')
LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')


def unescape(s):
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')


def table(src):
    block = src[src.index('const OptDef kOpts[] = {'):]
    block = block[:block.index('\n};')]
    rows = []
    for entry in re.findall(r'\{("(?:[^{}])*?)\},', block, re.S):
        lits = [unescape(x) for x in LIT.findall(entry)]
        rows.append((lits[0], lits[1], lits[2], ''.join(lits[3:])))
    header = unescape(LIT.search(src[src.index('kIniHeader ='):]).group(1))
    return header, rows


def text(header, rows):
    out = ['; %s\n' % header]
    section = None
    for sec, key, default, comment in rows:
        if sec != section:
            out.append(('\n[%s]\n' if section else '[%s]\n') % sec)
            section = sec
        for line in comment.split('\n'):
            if line: out.append('; %s\n' % line)
        out.append('%s=%s\n' % (key, default))
    return ''.join(out)


def main(argv):
    header, rows = table(open(CPP, encoding='utf-8').read())
    want = text(header, rows)
    if argv and argv[0] == '--print':
        sys.stdout.write(want)
        return 0
    have = open(INI, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    if have == want:
        print('ok: TruMenu.ini = defaults table (%d keys)' % len(rows))
        return 0
    a, b = have.split('\n'), want.split('\n')
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else '<end>'
        y = b[i] if i < len(b) else '<end>'
        if x != y:
            print('MISMATCH line %d\n  ini:   %s\n  table: %s' % (i + 1, x, y))
            break
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
