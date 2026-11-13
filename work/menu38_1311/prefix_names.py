"""PD / TruMenu 0.22.38 (2026-11-13): the co_ / fx_ label filter against the real object names.

Reads every objectlist of work/generic/lists (PC, Xbox, Xbox TU, DLC packs; read only), takes the distinct names and
applies the 0.22.37 rule (name start only) and the 0.22.38 rule (P5PrefixKind: a "dlc_" / "dlc<digits>_" in front
skipped first; exceptions co_rock*, *_grab_prompt) - a Python copy of the C function, compared with it by
tools/trumenu_ini_check.py check_02238. Prints the counts per rule, every name the new rule adds, the exceptions and the
names that contain co_ / fx_ elsewhere (not filtered, listed for review). Exit 0.

Usage (from trudlcport): ../bin/pyt -t 120 work/menu38_1311/prefix_names.py [OUT.txt]
"""
import glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LISTS = os.path.join(ROOT, 'work', 'generic', 'lists')


def kind_0237(low):
    if low.startswith('co_') and not low.startswith('co_rock'): return 1
    if low.startswith('fx_') and '_grab_prompt' not in low: return 2
    return 3


def kind_0238(low):                          # = P5PrefixKind (TruMenu.cpp, section "co_ / fx_ filter")
    s = low
    m = re.match(r'dlc[0-9]*_', s)
    if m: s = s[m.end():]
    if s.startswith('co_') and not s.startswith('co_rock'): return 1
    if s.startswith('fx_') and '_grab_prompt' not in s: return 2
    return 3


def names():
    seen = {}
    for path in sorted(glob.glob(os.path.join(LISTS, '*objectlist.txt'))):
        lines = open(path, encoding='latin1').read().splitlines()
        for line in lines[1:]:
            if ',' in line:
                name = line.split(',', 1)[1].strip().lower()
                seen.setdefault(name, os.path.basename(path))
    return seen


def main(argv):
    seen = names()
    out = []
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(LISTS, '*objectlist.txt')))
    out.append('object lists: %s' % ', '.join(files))
    out.append('distinct names: %d' % len(seen))
    for label, fn in (('0.22.37', kind_0237), ('0.22.38', kind_0238)):
        k = [fn(n) for n in seen]
        out.append('%s rule: co_ hidden %d, fx_ hidden %d, kept %d' % (label, k.count(1), k.count(2), k.count(3)))
    added = sorted(n for n in seen if kind_0238(n) != kind_0237(n))
    groups = {}
    for n in added:
        groups.setdefault(re.match(r'dlc[0-9]*_(co|fx)_', n).group(0), []).append(n)
    out.append('added by 0.22.38: %d (%s)' % (len(added), ', '.join('%s* %d' % (g, len(v)) for g, v in sorted(groups.items()))))
    for n in added: out.append('  + %s (%s)' % (n, seen[n]))
    exc = sorted(n for n in seen if re.match(r'(dlc[0-9]*_)?(co_rock|fx_.*_grab_prompt)', n))
    out.append('exceptions kept (co_rock*, *_grab_prompt): %s' % ', '.join(exc))
    other = sorted(n for n in seen if kind_0238(n) == 3 and ('co_' in n or 'fx_' in n or 'fx' in n.split('_')[0])
                   and n not in exc)
    out.append('co_ / fx_ elsewhere in the name (kept, review only): %d' % len(other))
    for n in other: out.append('  = %s' % n)
    dlc_co = [n for n in seen if re.match(r'dlc[0-9]*_co_', n)]
    out.append('dlc*_co_* names: %d' % len(dlc_co))
    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if argv:
        open(argv[0], 'w', encoding='utf-8', newline='\n').write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
