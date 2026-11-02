"""Check that the shipped src/asi/TruMenu/TruMenu.ini is exactly the text TruMenu writes from its defaults table
(kOpts in TruMenu.cpp, DefaultIniText) - read-only. Since TruMenu 0.8 also the regression lists tests/regress/*.txt
(TruMenu.tests.txt row format, 8 tab-separated columns; step ids step<n> = number; ids unique; every check id named in
backticks in its source doc docs/Regression-DLC1.md / docs/Regression-Schattenlara.md; ASCII only).

Usage (from the repository root):
  ../bin/pyt -t 60 tools/trumenu_ini_check.py            compare + list check, print the first difference / every
                                                         list problem; exit 1 on a mismatch
  ../bin/pyt -t 60 tools/trumenu_ini_check.py --print    print the text generated from the table
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.cpp')
INI = os.path.join(ROOT, 'src', 'asi', 'TruMenu', 'TruMenu.ini')
REGRESS = {'dlc1.txt': 'Regression-DLC1.md', 'dlc2.txt': 'Regression-Schattenlara.md'}
LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')


def check_lists():
    """problems of tests/regress/*.txt (empty list = fine) and a summary per file"""
    problems, summary = [], []
    for name, doc in sorted(REGRESS.items()):
        path = os.path.join(ROOT, 'tests', 'regress', name)
        if not os.path.exists(path):
            problems.append('%s missing' % name)
            continue
        raw = open(path, 'rb').read()
        if any(b > 126 or (b < 32 and b not in (9, 10, 13)) for b in raw):
            problems.append('%s: non-ASCII bytes (the menu font has no umlauts)' % name)
        doc_text = open(os.path.join(ROOT, 'docs', doc), encoding='utf-8').read()
        doc_ids = set(re.findall(r'`([a-z0-9][a-z0-9-]+)`', doc_text))
        seen, steps, checks = set(), 0, 0
        for n, line in enumerate(raw.decode('ascii', 'replace').splitlines(), 1):
            if not line or line.startswith('#'): continue
            f = line.split('\t')
            if len(f) != 8:
                problems.append('%s:%d: %d columns, want 8' % (name, n, len(f)))
                continue
            rid, state, hint, note, when, kind, target, num = f
            if rid in seen: problems.append('%s:%d: id %s twice' % (name, n, rid))
            seen.add(rid)
            if kind not in ('step', 'check'): problems.append('%s:%d: kind %s' % (name, n, kind))
            if state != 'open' or note or when: problems.append('%s:%d: state / note / time must be open / empty' % (name, n))
            if not hint or len(hint) > 239: problems.append('%s:%d: hint empty or longer than 239' % (name, n))
            if kind == 'step':
                steps += 1
                if rid != 'step%s' % num: problems.append('%s:%d: step id %s vs number %s' % (name, n, rid, num))
            else:
                checks += 1
                if target or num != '0': problems.append('%s:%d: a check has no target / number' % (name, n))
                if rid not in doc_ids: problems.append('%s:%d: check id %s not in docs/%s' % (name, n, rid, doc))
        summary.append('%s %d steps + %d checks' % (name, steps, checks))
    return problems, summary


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
    problems, summary = check_lists()
    for p in problems: print('LIST %s' % p)
    if not problems: print('ok: regression lists (%s)' % ', '.join(summary))
    have = open(INI, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    if have == want:
        print('ok: TruMenu.ini = defaults table (%d keys)' % len(rows))
        return 1 if problems else 0
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
