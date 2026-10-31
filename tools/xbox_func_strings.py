"""Strings referenced by given functions of an Xbox 360 image dumped from Xenia (read-only; finding 43, rock vein).

For each function start (from a file or a comma list, e.g. the "new:" list of tools/xbox_func_diff.py output) it
prints the printable C strings the function builds addresses of (lis/addi pairs found by tools/ppc_xrefs.py) and
its direct callees. Useful to name the new title-update functions (state names, animation / markup names, asserts).

Usage (from the repository root):
  ../bin/pyt -t 600 tools/xbox_func_strings.py IMAGE.bin FUNCS [--grep WORD,...] [--min N]
  FUNCS   file with one 0x8xxxxxxx per line (others ignored) or a comma list
  --grep  only print functions whose strings contain one of the words (case-insensitive)
  --min   minimum string length (default 4)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ppc_xrefs as P

BASE = 0x82000000


def cstr(d, a, minimum):
    o = a - BASE
    if not 0 <= o < len(d):
        return None
    end = d.find(b'\0', o, o + 300)
    if end < 0 or end - o < minimum:
        return None
    s = d[o:end]
    if all(32 <= c < 127 for c in s):
        return s.decode('ascii')
    return None


def main(argv):
    words = None; minimum = 4
    if '--grep' in argv:
        k = argv.index('--grep'); words = [w.lower() for w in argv[k + 1].split(',')]; del argv[k:k + 2]
    if '--min' in argv:
        k = argv.index('--min'); minimum = int(argv[k + 1]); del argv[k:k + 2]
    path, spec = argv[0], argv[1]
    if os.path.isfile(spec):
        starts = [int(x, 16) for x in re.findall(r'0x82[0-9a-fA-F]{6}', open(spec).read())]
    else:
        starts = [int(x, 16) for x in spec.split(',')]
    d, _ = P.load(path)
    funcs, res = P.cached(path)
    ends = dict(funcs)
    for fs in starts:
        items = res.get(fs, [])
        strs = []
        for _, kind, v in items:
            if kind == 'addr':
                s = cstr(d, v, minimum)
                if s and s not in strs:
                    strs.append(s)
        if words and not any(w in s.lower() for s in strs for w in words):
            continue
        calls = sorted(set(v for _, k, v in items if k == 'call'))
        print('0x%08x %5d B  calls %d' % (fs, ends.get(fs, fs) - fs, len(calls)))
        for s in strs:
            print('    "%s"' % s[:150])


if __name__ == '__main__':
    main(sys.argv[1:])
