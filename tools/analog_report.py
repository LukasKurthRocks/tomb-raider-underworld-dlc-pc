"""Summarise the 'analog' fixes of a stage-2b run (read-only): what kind of byte-order change each fix is, how many
were skipped as re-authored, per file / DTP / base analog. Reads <tree>/../fixes_report.json (dlc_fixes_build.py).

The kind is the byte permutation that maps our converted word to the analog's PC word (both encode the same Xbox
value): e.g. u16u16->u32 means the learned table treated a 32-bit field as two 16-bit values.

Usage (from the repository root):
  ..\\bin\\venv\\Scripts\\python.exe -I -X utf8 tools/analog_report.py work/rebuild/dlc2_asm_stage2b
"""
import sys, os, json, re, itertools, collections

NAMED = {(0, 1, 2, 3): 'same', (3, 2, 1, 0): 'reverse4', (1, 0, 3, 2): 'swap16x2', (2, 3, 0, 1): 'swap-halves',
         (0, 1, 3, 2): 'swap-low16', (1, 0, 2, 3): 'swap-high16'}
LINE = re.compile(r'^(\S+) DTP (\d+) \+(0x[0-9a-f]+): ([0-9a-f]{8}) -> ([0-9a-f]{8}) (\S+) \(analog xbox (\d+) / pc (\d+)\)')


def kind(old, new):
    o, n = bytes.fromhex(old), bytes.fromhex(new)
    for pm in itertools.permutations(range(4)):
        if bytes(o[i] for i in pm) == n: return NAMED.get(pm, 'perm%s' % ''.join(map(str, pm)))
    return 'not-a-permutation'


def main(argv):
    rep = json.load(open(os.path.join(argv[0], 'fixes_report.json')))['analog']['log']
    rows = [m.groups() for m in (LINE.match(l) for l in rep) if m]
    print('analog log lines %d, parsed %d' % (len(rep), len(rows)))
    print('by action:', dict(collections.Counter(r[5] for r in rows)))
    print('by kind (fixes):', dict(collections.Counter(kind(r[3], r[4]) for r in rows if r[5] == 'fix').most_common()))
    print('files:', dict(collections.Counter(r[0] for r in rows).most_common()))
    per = collections.Counter((r[0], r[1], r[6]) for r in rows)
    print('DTPs fixed %d, distinct base analogs %d; largest (file, DTP, base analog xbox id): %s' % (
        len(per), len({r[6] for r in rows}), per.most_common(6)))
    offs = collections.Counter(r[2] for r in rows)
    print('most frequent offsets (same field in many DTPs):', offs.most_common(8))


if __name__ == '__main__':
    main(sys.argv[1:])
