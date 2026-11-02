"""Census of Xenos ALU opcodes in Xbox pixel-shader libs (test 50h, arms / gloves).

Which scalar / vector opcodes (and modifiers: scalar / vector saturate, export) the microcode of given libs uses, and
how often the clamped / flushed scalar variants (logc, rcpc, rcpf, rsqc, rsqf) and the IEEE ones (log, rcp, rsq)
occur in all base Xbox libs (X) and the DLC / TU libs (D) of work/render/shaderlibs.pkl.

Usage (from the repository root):
  ../bin/pyt -t 600 tools/xenos_op_census.py libs D:2682 D:2685 D:2688 D:2679 [X:658 ...] [--slots 0,1]
      per lib / slot: count of every scalar and vector opcode, saturate counts
  ../bin/pyt -t 900 tools/xenos_op_census.py all [--slots 0,1]
      number of libs (and instructions) per scalar opcode in X and D
"""
import sys, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'shader4')); sys.path.insert(0, os.path.join(ROOT, 'work', 'ws', 'xenos'))
from f3_common import libs
import xenos_xlat as XL

CLAMPED = ('logc', 'log', 'rcpc', 'rcpf', 'rcp', 'rsqc', 'rsqf', 'rsq', 'sqrt', 'exp')


def census(blob):
    sh = XL.parse(blob)
    sc, vc = collections.Counter(), collections.Counter()
    ssat = vsat = 0
    for e in XL.walk(sh):
        if e[0] != 'alu': continue
        f = e[2]
        if f['sopc'] != 50:
            s = XL.SOP.get(f['sopc'], '?%d' % f['sopc']); sc[s] += 1
            if f['ssat']: ssat += 1
        if f['vmask'] or XL.VOP[f['vopc']].startswith('kill'):
            v = XL.VOP[f['vopc']]; vc[v] += 1
            if f['vsat']: vsat += 1
    return sc, vc, ssat, vsat


def cmd_libs(specs, slots):
    L = libs()
    for spec in specs:
        k, i = spec.split(':'); lib = L[k][int(i)]
        for s in slots:
            if lib['slots'][s] == 0xffffffff: continue
            sc, vc, ssat, vsat = census(lib['entries'][lib['slots'][s]]['blob'])
            print('%s slot %d: scalar %s' % (spec, s, dict(sorted(sc.items()))))
            print('%s slot %d: vector %s' % (spec, s, dict(sorted(vc.items()))))
            print('%s slot %d: saturate scalar %d vector %d; clamped/IEEE scalar %s'
                  % (spec, s, ssat, vsat, {c: sc[c] for c in CLAMPED if sc[c]}))


def cmd_all(slots):
    L = libs()
    for k in ('X', 'D'):
        nlib = collections.Counter(); nins = collections.Counter(); total = 0
        for i, lib in L[k].items():
            seen = set()
            for s in slots:
                if s >= len(lib['slots']) or lib['slots'][s] == 0xffffffff: continue
                try: sc, vc, _, _ = census(lib['entries'][lib['slots'][s]]['blob'])
                except Exception: continue
                for c, n in sc.items():
                    nins[c] += n; seen.add(c)
            for c in seen: nlib[c] += 1
            total += 1
        print('%s: %d libs' % (k, total))
        for c in CLAMPED:
            print('   %-5s libs %5d  instructions %6d' % (c, nlib[c], nins[c]))


def main(a):
    if not a: sys.exit(__doc__)
    slots = (0, 1)
    if '--slots' in a:
        j = a.index('--slots'); slots = tuple(int(x) for x in a[j + 1].split(',')); a = a[:j] + a[j + 2:]
    if a[0] == 'libs': cmd_libs(a[1:], slots)
    elif a[0] == 'all': cmd_all(slots)
    else: sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
