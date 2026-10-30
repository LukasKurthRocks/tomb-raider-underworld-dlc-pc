"""Summarise a cdb log of the cloth-stepper breakpoint (tru.exe +0x601ca, `JobHarness_JobClothSimulate` sub-steps,
finding 43). Every sample prints CLOTH, the hit number, the simulation object (esi), `dd esi+3c L2`,
`df esi+24 L1` and (newer logs) `dd esi+18 L3`. The stepper runs [+0x3c] x [+0x40] sub-steps of [+0x24] / n;
[+0x40] follows the elapsed time [+0x24], so slow frames mean more sub-steps. Reports per simulation object: the
sizes at +0x18 / +0x1c / +0x20 (particles, constraints, ...), [+0x3c], the histogram of [+0x40] and the range of
[+0x24]; then the overall histogram of sub-steps per call. Read-only.

Usage (from the repository root):
  ../bin/pyt -t 60 tools/cdb_cloth_summary.py LOG [LOG ...]
"""
import sys, re, collections

EVAL = re.compile(r'^Evaluate expression: (-?\d+) = ([0-9a-f]{8})')
DD = re.compile(r'^([0-9a-f]{8})((?:  ?[0-9a-f]{8})+)\s*$')
DF1 = re.compile(r'^([0-9a-f]{8})\s+(\S+)\s*$')


def words(line):
    m = DD.match(line)
    return [int(x, 16) for x in m.group(2).split()] if m else None


def parse(path):
    """-> list of dicts (hit, sim, n3c, n40, f24, sizes or None)"""
    out = []; lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() != 'CLOTH': i += 1; continue
        try:
            hit = int(EVAL.match(lines[i + 1]).group(1))
            sim = int(EVAL.match(lines[i + 2]).group(2), 16)
            n3c, n40 = words(lines[i + 3])[:2]
            f24 = float(DF1.match(lines[i + 4]).group(2))
        except (AttributeError, IndexError, ValueError, TypeError):
            i += 1; continue
        m = DD.match(lines[i + 5]) if i + 5 < len(lines) else None      # only `dd esi+18 L3`, not a later dump
        w = words(lines[i + 5]) if m and int(m.group(1), 16) == sim + 0x18 else None
        sizes = tuple(w[:3]) if w and len(w) >= 3 else None
        out.append(dict(hit=hit, sim=sim, n3c=n3c, n40=n40, f24=f24, sizes=sizes))
        i += 6 if sizes else 5
    return out


def main(argv):
    for p in argv:
        s = parse(p)
        objs = collections.OrderedDict()
        for r in s: objs.setdefault(r['sim'], []).append(r)
        print('== %s: %d samples (hits %s-%s), %d simulation objects' % (
            p, len(s), s[0]['hit'] if s else '-', s[-1]['hit'] if s else '-', len(objs)))
        prod = collections.Counter()
        for sim, rs in objs.items():
            sizes = collections.Counter(r['sizes'] for r in rs)
            n3c = collections.Counter(r['n3c'] for r in rs)
            n40 = collections.Counter(r['n40'] for r in rs)
            f = [r['f24'] for r in rs]
            for r in rs: prod[r['n3c'] * r['n40']] += 1
            print('  sim %08x  samples %3d  sizes(+18,+1c,+20) %s  [+3c] %s  [+40] %s  [+24] %.3g..%.3g' % (
                sim, len(rs), dict(sizes), dict(n3c), dict(sorted(n40.items())), min(f), max(f)))
        print('  sub-steps per call (samples): %s' % dict(sorted(prod.items())))


if __name__ == '__main__':
    main(sys.argv[1:])
